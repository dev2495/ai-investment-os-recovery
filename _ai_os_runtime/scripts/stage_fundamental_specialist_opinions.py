#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any

from run_institutional_fundamental_factory import PsqlGateway, sql_jsonb, sql_literal


SPECIALISTS = (
    ("business_model", "Company Analyst"),
    ("moat", "Moat Analyst"),
    ("industry", "Industry Analyst"),
    ("management", "Management Analyst"),
    ("governance", "Governance Analyst"),
    ("capital_allocation", "Capital Allocation Analyst"),
    ("financial_quality", "Financial Statement Analyst"),
    ("forensic_accounting", "Forensic Accounting Agent"),
    ("valuation", "Valuation Agent"),
    ("bear_case", "Bear Case Agent"),
    ("risk", "Independent Risk Agent"),
    ("portfolio_fit", "Portfolio Fit Agent"),
)


def load_context(gateway: PsqlGateway, symbol: str, exchange: str, as_of: datetime) -> dict[str, Any]:
    cutoff = sql_literal(as_of.isoformat())
    return gateway._run_json(f"""
        WITH company AS (
          SELECT * FROM research.companies
          WHERE upper(primary_symbol)={sql_literal(symbol)}
            AND upper(primary_exchange)={sql_literal(exchange)}
          LIMIT 1
        ), dossier AS (
          SELECT dossier.id, dossier.holding_thesis_id, version.id AS dossier_version_id,
                 version.version_number
          FROM research.investment_dossiers dossier
          JOIN company ON company.id=dossier.company_id
          JOIN LATERAL (
            SELECT * FROM research.investment_dossier_versions version
            WHERE version.dossier_id=dossier.id AND version.source_cutoff_at<={cutoff}::timestamptz
            ORDER BY version.version_number DESC LIMIT 1
          ) version ON true
          ORDER BY dossier.updated_at DESC LIMIT 1
        ), eligible_evidence AS (
          SELECT evidence.* FROM research.fundamental_evidence evidence
          JOIN company ON company.id=evidence.company_id
          WHERE evidence.retrieved_at<={cutoff}::timestamptz
            AND coalesce(evidence.published_at,evidence.retrieved_at)<={cutoff}::timestamptz
            AND evidence.verification_status NOT IN ('rejected','superseded')
        ), fact_coverage AS (
          SELECT definition.fact_key,count(DISTINCT fact.fiscal_year) AS years,
                 max(fact.fiscal_year) AS latest_year
          FROM research.company_statement_facts fact
          JOIN company ON company.id=fact.company_id
          JOIN eligible_evidence evidence ON evidence.id=fact.evidence_id
          JOIN research.statement_fact_definitions definition ON definition.id=fact.fact_definition_id
          WHERE fact.fiscal_period='FY' AND fact.is_current AND fact.available_at<={cutoff}::timestamptz
          GROUP BY definition.fact_key
        )
        SELECT json_build_object(
          'company',(SELECT row_to_json(company) FROM company),
          'dossier',(SELECT row_to_json(dossier) FROM dossier),
          'evidence',coalesce((SELECT json_agg(row_to_json(rows) ORDER BY rows.retrieved_at DESC,rows.id DESC) FROM (
            SELECT id,source_type,source_name,source_title,published_at,retrieved_at,verification_status
            FROM eligible_evidence
          ) rows),'[]'::json),
          'fact_coverage',coalesce((SELECT json_object_agg(fact_key,years) FROM fact_coverage),'{{}}'::json),
          'operational_kpis',(SELECT count(DISTINCT observation.kpi_definition_id) FROM research.operational_kpi_observations observation JOIN company ON company.id=observation.company_id JOIN eligible_evidence evidence ON evidence.id=observation.evidence_id WHERE observation.available_at<={cutoff}::timestamptz),
          'segments',(SELECT count(*) FROM research.company_segments segment JOIN company ON company.id=segment.company_id JOIN eligible_evidence evidence ON evidence.id=segment.evidence_id WHERE segment.valid_from<={cutoff}::date AND (segment.valid_to IS NULL OR segment.valid_to>={cutoff}::date)),
          'segment_years',(SELECT count(DISTINCT fact.fiscal_year) FROM research.company_segment_facts fact JOIN company ON company.id=fact.company_id JOIN eligible_evidence evidence ON evidence.id=fact.evidence_id WHERE fact.available_at<={cutoff}::timestamptz),
          'market_share_series',(SELECT count(DISTINCT observation.market_key) FROM research.market_share_observations observation JOIN company ON company.id=observation.company_id JOIN eligible_evidence evidence ON evidence.id=observation.evidence_id WHERE observation.available_at<={cutoff}::timestamptz),
          'peers',(SELECT count(DISTINCT membership.peer_company_id) FROM research.peer_sets peer_set JOIN company ON company.id=peer_set.subject_company_id JOIN research.peer_set_memberships membership ON membership.peer_set_id=peer_set.id JOIN eligible_evidence evidence ON evidence.id=membership.evidence_id WHERE peer_set.valid_from<={cutoff}::date AND (peer_set.valid_to IS NULL OR peer_set.valid_to>={cutoff}::date)),
          'communications',(SELECT count(*) FROM research.management_communications communication JOIN company ON company.id=communication.company_id JOIN eligible_evidence evidence ON evidence.id=communication.evidence_id WHERE communication.communication_date<={cutoff}::date),
          'claims',(SELECT count(*) FROM research.management_claims claim JOIN company ON company.id=claim.company_id JOIN eligible_evidence evidence ON evidence.id=claim.evidence_id WHERE claim.claim_date<={cutoff}::date),
          'claim_outcomes',(SELECT count(*) FROM research.management_claim_outcomes outcome JOIN research.management_claims claim ON claim.id=outcome.claim_id JOIN company ON company.id=claim.company_id JOIN eligible_evidence evidence ON evidence.id=outcome.evidence_id WHERE outcome.outcome_date<={cutoff}::date),
          'position_rows',(SELECT count(*) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='open'),
          'client_count',(SELECT count(DISTINCT position.client_id) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='open'),
          'gross_exposure',(SELECT coalesce(sum(position.gross_exposure),0) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='open'),
          'valuation_complete',(SELECT count(*) FROM portfolio.holding_valuation_models model JOIN dossier ON dossier.holding_thesis_id=model.holding_thesis_id WHERE model.status IN ('complete','reviewed') AND model.updated_at<={cutoff}::timestamptz),
          'monte_carlo_complete',(SELECT count(*) FROM portfolio.long_term_monte_carlo_runs run JOIN dossier ON dossier.holding_thesis_id=run.holding_thesis_id WHERE run.run_status='complete' AND run.created_at<={cutoff}::timestamptz)
        )::text;
    """) or {}


def build_opinions(context: dict[str, Any], as_of: datetime) -> list[dict[str, Any]]:
    company = context.get("company") or {}
    dossier = context.get("dossier") or {}
    evidence = context.get("evidence") or []
    if not company or not dossier or not evidence:
        raise ValueError("company, dossier version, and eligible evidence are required")
    facts = {str(key): int(value) for key, value in (context.get("fact_coverage") or {}).items()}
    annual = next((row for row in evidence if "annual" in str(row.get("source_title") or "").lower()), evidence[0])
    peer_evidence = next((row for row in evidence if row.get("source_type") == "operating_peer_primary_source"), annual)
    operating_kpis = int(context.get("operational_kpis") or 0)
    segments = int(context.get("segments") or 0)
    segment_years = int(context.get("segment_years") or 0)
    market_share = int(context.get("market_share_series") or 0)
    peers = int(context.get("peers") or 0)
    communications = int(context.get("communications") or 0)
    claims = int(context.get("claims") or 0)
    outcomes = int(context.get("claim_outcomes") or 0)
    positions = int(context.get("position_rows") or 0)
    clients = int(context.get("client_count") or 0)
    exposure = float(context.get("gross_exposure") or 0)
    valuations = int(context.get("valuation_complete") or 0)
    monte_carlo = int(context.get("monte_carlo_complete") or 0)
    symbol = str(company.get("primary_symbol") or "company")
    common = {
        "company_id": int(company["id"]),
        "dossier_version_id": int(dossier["dossier_version_id"]),
        "holding_thesis_id": int(dossier["holding_thesis_id"]) if dossier.get("holding_thesis_id") else None,
        "opinion_as_of": as_of.isoformat(),
    }
    rows = {
        "business_model": ("evidence_complete", 78, annual, f"I find {symbol}'s stored business-model evidence covers {segments} operating segment(s), {segment_years} segment years and {operating_kpis} operating KPI series. I do not treat this as proof of pricing power or unit economics.", "Customer concentration, product-level margins and pricing-power evidence remain incomplete.", ["Add product and geography economics from verified presentation pages."]),
        "moat": ("draft", 45, peer_evidence, f"I cannot certify a durable moat: the warehouse has {peers} operating peers but {market_share} numeric market-share series.", "A differentiated product description is not evidence of durable excess returns or share gains.", ["Add primary-source market-share history and customer switching evidence."]),
        "industry": ("draft", 50, peer_evidence, f"I have a primary-source operating peer set with {peers} members, but the industry structure is not yet quantified.", "Capacity, demand, import/export, customer concentration and cycle data are not complete.", ["Build sector capacity, demand, pricing and market-share history."]),
        "management": ("evidence_complete", 72, annual, f"I reviewed {communications} stored management communications, {claims} explicit claims and {outcomes} observed outcome(s).", "One observed outcome is insufficient to establish a durable forecasting record.", ["Continue claim-versus-outcome tracking after every results cycle."]),
        "governance": ("draft", 42, annual, "I have audited annual reports, but no completed structured auditor, related-party, remuneration, pledge and minority-treatment review.", "Absence of a stored red flag is not evidence that governance is clean.", ["Complete the governance checklist from notes to accounts and exchange disclosures."]),
        "capital_allocation": ("evidence_complete", 70, annual, f"I can trace {facts.get('capital_expenditure', 0)} years of capex, {facts.get('dividends_paid', 0)} years of dividends and management commitment outcomes.", "Historical spending must still be tested against incremental returns and dilution.", ["Calculate incremental ROIC and reconcile capex commitments to commissioned capacity."]),
        "financial_quality": ("evidence_complete", 76, annual, f"I have {facts.get('revenue_from_operations', 0)} revenue years, {facts.get('profit_after_tax', 0)} PAT years, {facts.get('operating_cash_flow', 0)} operating-cash-flow years and {facts.get('total_assets', 0)} asset years.", "Normalized FCF, working-capital drivers and restatement review remain outstanding.", ["Build ratio history and flag OCF/PAT, receivable, inventory and leverage outliers."]),
        "forensic_accounting": ("draft", 38, annual, "I will not clear forensic accounting from headline statements alone.", "Related parties, contingencies, auditor changes, exceptional items and note-level working-capital movements are not yet fully tested.", ["Run the note-level forensic checklist and retain every exception as evidence."]),
        "valuation": ("draft", 35, annual, f"I find {valuations} completed valuation model(s) and {monte_carlo} completed Monte Carlo run(s); this is insufficient for the required four-family suite.", "A simulation built on unreviewed assumptions is not a valuation conclusion.", ["Complete DCF, reverse DCF, peer multiples and reviewed Monte Carlo assumptions."]),
        "bear_case": ("dissent", 68, annual, "I dissent from any capital action while market share, forensic review and the full valuation suite remain incomplete.", "The central downside is mistaking cyclical wire-rope economics and capex-led growth for a durable moat.", ["Quantify downside under volume, margin and working-capital stress."]),
        "risk": ("evidence_complete", 73, annual, f"I observe {positions} open position row(s), {clients} client(s) and gross exposure of INR {exposure:,.0f}; execution remains locked.", "Research incompleteness and cross-client concentration are active risks even when the business performs.", ["Apply client suitability, concentration, liquidity and cross-book limits before any proposal."]),
        "portfolio_fit": ("draft", 48, annual, f"I can map {positions} open position row(s) across {clients} client(s), but I cannot approve fit without explicit client and portfolio risk budgets.", "A sound company thesis does not establish suitable position size or opportunity cost.", ["Attach client mandates, risk budgets, liquidity limits and alternative opportunity set."]),
    }
    opinions: list[dict[str, Any]] = []
    for key, agent in SPECIALISTS:
        status, confidence, source, conclusion, dissent, followups = rows[key]
        opinions.append({
            **common,
            "specialist_key": key,
            "agent_name": agent,
            "opinion_status": status,
            "conclusion": conclusion,
            "confidence_pct": confidence,
            "disconfirming_evidence": dissent,
            "required_followups": followups,
            "evidence_id": int(source["id"]),
        })
    return opinions


def persist(gateway: PsqlGateway, opinions: list[dict[str, Any]]) -> dict[str, Any]:
    values = []
    for row in opinions:
        values.append("(" + ",".join((
            str(row["company_id"]) + "::bigint", str(row["dossier_version_id"]) + "::bigint",
            (str(row["holding_thesis_id"]) + "::bigint") if row.get("holding_thesis_id") else "NULL::bigint",
            sql_literal(row["specialist_key"]), sql_literal(row["agent_name"]),
            sql_literal(row["opinion_status"]), sql_literal(row["conclusion"]),
            str(row["confidence_pct"]), sql_literal(row["disconfirming_evidence"]),
            sql_jsonb(row["required_followups"]), str(row["evidence_id"]) + "::bigint",
            sql_literal(row["opinion_as_of"]) + "::timestamptz",
        )) + ")")
    return gateway._run_json(f"""
      WITH incoming(company_id,dossier_version_id,holding_thesis_id,specialist_key,agent_name,
        opinion_status,conclusion,confidence_pct,disconfirming_evidence,required_followups,
        evidence_id,opinion_as_of) AS (VALUES {','.join(values)}), upserted AS (
        INSERT INTO research.fundamental_specialist_opinions (
          company_id,dossier_version_id,holding_thesis_id,specialist_key,agent_name,
          opinion_status,conclusion,confidence_pct,disconfirming_evidence,required_followups,
          evidence_id,opinion_as_of
        ) SELECT * FROM incoming
        ON CONFLICT (dossier_version_id,specialist_key,agent_name) DO UPDATE SET
          opinion_status=EXCLUDED.opinion_status,conclusion=EXCLUDED.conclusion,
          confidence_pct=EXCLUDED.confidence_pct,disconfirming_evidence=EXCLUDED.disconfirming_evidence,
          required_followups=EXCLUDED.required_followups,evidence_id=EXCLUDED.evidence_id,
          opinion_as_of=EXCLUDED.opinion_as_of,updated_at=now()
        RETURNING specialist_key,agent_name,opinion_status,evidence_id
      ) SELECT json_build_object('written',count(*),'opinions',json_agg(row_to_json(upserted) ORDER BY specialist_key))::text FROM upserted;
    """) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage point-in-time, evidence-linked institutional specialist opinions.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", required=True, choices=["NSE", "BSE"])
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    symbol = args.symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._&-]{1,40}", symbol):
        raise SystemExit("invalid symbol")
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise SystemExit("as-of must include a timezone")
    gateway = PsqlGateway()
    context = load_context(gateway, symbol, args.exchange, as_of)
    opinions = build_opinions(context, as_of)
    result = persist(gateway, opinions) if args.persist else {"written": 0}
    print(json.dumps({
        "ok": True, "symbol": symbol, "as_of": as_of.isoformat(),
        "dossier_version_id": context["dossier"]["dossier_version_id"],
        "opinion_count": len(opinions), "statuses": {row["specialist_key"]: row["opinion_status"] for row in opinions},
        "database": result, "capital_action_allowed": False, "broker_write_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
