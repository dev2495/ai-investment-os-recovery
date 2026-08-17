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
          'governance_forensic',(SELECT json_build_object(
            'count',count(*),
            'categories',count(DISTINCT observation.category),
            'active_issues',count(*) FILTER (WHERE observation.observation_status IN ('active_issue','qualified','exception')),
            'high_severity',count(*) FILTER (WHERE observation.severity IN ('high','critical')),
            'evidence_id',min(observation.evidence_id)
          ) FROM research.governance_forensic_observations observation JOIN company ON company.id=observation.company_id JOIN eligible_evidence evidence ON evidence.id=observation.evidence_id WHERE observation.available_at<={cutoff}::timestamptz AND observation.verification_status NOT IN ('rejected','superseded')),
          'industry_observations',(SELECT json_build_object('count',count(*),'categories',count(DISTINCT observation.category),'quantified',count(*) FILTER (WHERE observation.metric_availability='quantified'),'market_share_not_disclosed',count(*) FILTER (WHERE observation.category='market_share' AND observation.metric_availability='not_disclosed'),'evidence_id',min(observation.evidence_id)) FROM research.industry_competitive_observations observation JOIN company ON company.id=observation.company_id JOIN eligible_evidence evidence ON evidence.id=observation.evidence_id WHERE observation.available_at<={cutoff}::timestamptz AND observation.verification_status NOT IN ('rejected','superseded')),
          'position_rows',(SELECT count(*) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='active'),
          'client_count',(SELECT count(DISTINCT position.client_id) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='active'),
          'portfolio_fit_context',(SELECT json_build_object(
            'risk_limit_clients',count(DISTINCT check_row.client_id),
            'breaches',count(*) FILTER (WHERE check_row.check_status='breach'),
            'warnings',count(*) FILTER (WHERE check_row.check_status='warning'),
            'latest_as_of',max(check_row.latest_as_of),
            'suitable_clients',(SELECT count(DISTINCT review.client_id) FROM portfolio.client_suitability_reviews review WHERE review.client_id IN (SELECT DISTINCT position.client_id FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.status='active' AND position.as_of<={cutoff}::timestamptz) AND review.status IN ('suitable','conditionally_suitable') AND review.reviewed_at<={cutoff}::timestamptz)
          ) FROM risk.v_portfolio_risk_limit_checks check_row JOIN company ON upper(check_row.symbol)=upper(company.primary_symbol) AND upper(check_row.exchange)=upper(company.primary_exchange) WHERE check_row.latest_as_of<={cutoff}::timestamptz),
          'gross_exposure',(SELECT coalesce(sum(position.gross_exposure),0) FROM books.v_book_positions position JOIN company ON upper(position.symbol)=upper(company.primary_symbol) AND upper(position.exchange)=upper(company.primary_exchange) WHERE position.as_of<={cutoff}::timestamptz AND position.status='active'),
          'valuation_complete',(SELECT count(*) FROM portfolio.holding_valuation_models model JOIN dossier ON dossier.holding_thesis_id=model.holding_thesis_id WHERE model.status IN ('complete','reviewed') AND model.updated_at<={cutoff}::timestamptz),
          'valuation_types',coalesce((SELECT json_agg(DISTINCT lower(model.model_type) ORDER BY lower(model.model_type)) FROM portfolio.holding_valuation_models model JOIN dossier ON dossier.holding_thesis_id=model.holding_thesis_id WHERE model.status IN ('complete','reviewed') AND model.updated_at<={cutoff}::timestamptz),'[]'::json),
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
    portfolio_fit_context = context.get("portfolio_fit_context") or {}
    risk_limit_clients = int(portfolio_fit_context.get("risk_limit_clients") or 0)
    risk_breaches = int(portfolio_fit_context.get("breaches") or 0)
    risk_warnings = int(portfolio_fit_context.get("warnings") or 0)
    suitable_clients = int(portfolio_fit_context.get("suitable_clients") or 0)
    portfolio_fit_review_complete = positions > 0 and clients > 0 and risk_limit_clients >= clients
    valuations = int(context.get("valuation_complete") or 0)
    monte_carlo = int(context.get("monte_carlo_complete") or 0)
    valuation_types = {str(value).lower().replace("-", "_").replace(" ", "_") for value in context.get("valuation_types") or []}
    valuation_suite_complete = (
        bool(valuation_types & {"dcf", "discounted_cash_flow"})
        and bool(valuation_types & {"reverse_dcf", "reverse_discounted_cash_flow"})
        and bool(valuation_types & {"multiples", "relative_valuation", "peer_comparison"})
        and monte_carlo > 0
    )
    governance_forensic = context.get("governance_forensic") or {}
    gf_count = int(governance_forensic.get("count") or 0)
    gf_categories = int(governance_forensic.get("categories") or 0)
    gf_active = int(governance_forensic.get("active_issues") or 0)
    gf_high = int(governance_forensic.get("high_severity") or 0)
    gf_evidence_id = governance_forensic.get("evidence_id")
    gf_evidence = next((row for row in evidence if int(row.get("id") or 0) == int(gf_evidence_id or 0)), annual)
    industry_observations = context.get("industry_observations") or {}
    industry_count = int(industry_observations.get("count") or 0)
    industry_categories = int(industry_observations.get("categories") or 0)
    industry_quantified = int(industry_observations.get("quantified") or 0)
    market_share_not_disclosed = int(industry_observations.get("market_share_not_disclosed") or 0)
    industry_evidence_id = industry_observations.get("evidence_id")
    industry_evidence = next((row for row in evidence if int(row.get("id") or 0) == int(industry_evidence_id or 0)), peer_evidence)
    industry_review_complete = peers >= 2 and industry_categories >= 4 and industry_quantified >= 1 and market_share_not_disclosed >= 1
    symbol = str(company.get("primary_symbol") or "company")
    common = {
        "company_id": int(company["id"]),
        "dossier_version_id": int(dossier["dossier_version_id"]),
        "holding_thesis_id": int(dossier["holding_thesis_id"]) if dossier.get("holding_thesis_id") else None,
        "opinion_as_of": as_of.isoformat(),
    }
    rows = {
        "business_model": ("evidence_complete", 78, annual, f"I find {symbol}'s stored business-model evidence covers {segments} operating segment(s), {segment_years} segment years and {operating_kpis} operating KPI series. I do not treat this as proof of pricing power or unit economics.", "Customer concentration, product-level margins and pricing-power evidence remain incomplete.", ["Add product and geography economics from verified presentation pages."]),
        "moat": (("evidence_complete" if industry_review_complete else "draft"), 58 if industry_review_complete else 45, industry_evidence, f"I completed the available moat evidence review using {peers} operating peers and {industry_count} primary-source industry observations. I do not certify a durable moat: numeric market share remains unavailable and management explicitly describes global share as small.", "Higher-value products, replacement cycles and application engineering are possible advantages, but they do not prove durable excess returns or share gains.", ["Add independent customer evidence, switching-cost evidence, return-on-incremental-capital history and numeric share when a primary source becomes available."]),
        "industry": (("evidence_complete" if industry_review_complete else "draft"), 67 if industry_review_complete else 50, industry_evidence, f"I completed a point-in-time industry review with {peers} operating peers and {industry_count} observations across {industry_categories} categories, including quantified capacity and explicit non-disclosure of numeric market share.", "Demand and value-chain statements are company disclosures; import/export, customer concentration, pricing and independent capacity data remain incomplete.", ["Add independent sector capacity, demand, pricing and import/export history; retain numeric market share as unavailable until sourced."]),
        "management": ("evidence_complete", 72, annual, f"I reviewed {communications} stored management communications, {claims} explicit claims and {outcomes} observed outcome(s).", "One observed outcome is insufficient to establish a durable forecasting record.", ["Continue claim-versus-outcome tracking after every results cycle."]),
        "governance": (("evidence_complete" if gf_categories >= 4 and gf_active >= 1 else "draft"), 64 if gf_categories >= 4 else 42, gf_evidence, f"I completed a page-cited review across {gf_categories} governance and forensic categories with {gf_count} observations. I retain {gf_active} active issue(s), including {gf_high} high-severity item(s); evidence completeness is not a clean-company clearance.", "The company disclosures include unresolved legal or audit emphasis items and remain machine-extracted until operator verification.", ["Review every high-severity source excerpt, monitor Note 38 and exchange/legal updates, and complete remuneration, pledge and minority-treatment checks where absent."]),
        "capital_allocation": ("evidence_complete", 70, annual, f"I can trace {facts.get('capital_expenditure', 0)} years of capex, {facts.get('dividends_paid', 0)} years of dividends and management commitment outcomes.", "Historical spending must still be tested against incremental returns and dilution.", ["Calculate incremental ROIC and reconcile capex commitments to commissioned capacity."]),
        "financial_quality": ("evidence_complete", 76, annual, f"I have {facts.get('revenue_from_operations', 0)} revenue years, {facts.get('profit_after_tax', 0)} PAT years, {facts.get('operating_cash_flow', 0)} operating-cash-flow years and {facts.get('total_assets', 0)} asset years.", "Normalized FCF, working-capital drivers and restatement review remain outstanding.", ["Build ratio history and flag OCF/PAT, receivable, inventory and leverage outliers."]),
        "forensic_accounting": (("evidence_complete" if gf_categories >= 4 and gf_active >= 1 else "draft"), 66 if gf_categories >= 4 else 38, gf_evidence, f"I completed a page-cited first-pass forensic review with {gf_count} observations across {gf_categories} categories. The review identifies {gf_active} active issue(s) and explicitly does not clear them.", "An Emphasis of Matter and unresolved legal disclosures are disconfirming evidence; no-adverse-remark statements do not cancel those issues.", ["Reconcile Note 38, contingencies, related parties, exceptional items and working-capital movements, then obtain operator review of each cited excerpt."]),
        "valuation": (("evidence_complete" if valuation_suite_complete else "draft"), 70 if valuation_suite_complete else 35, annual, f"I find {valuations} calculation-complete valuation model(s) across {sorted(valuation_types)} and {monte_carlo} completed Monte Carlo run(s). Calculation completeness does not mean the assumptions or investment conclusion are operator reviewed.", "The source-backed reverse DCF and scenario ranges may imply demanding expectations; unreviewed assumptions cannot authorize capital action.", ["Review normalized FCF, discount rates, terminal assumptions, earnings multiples and Monte Carlo distributions; add true peer comparables separately."]),
        "bear_case": ("dissent", 68, annual, "I dissent from any capital action while market share, forensic review and the full valuation suite remain incomplete.", "The central downside is mistaking cyclical wire-rope economics and capex-led growth for a durable moat.", ["Quantify downside under volume, margin and working-capital stress."]),
        "risk": ("evidence_complete", 73, annual, f"I observe {positions} open position row(s), {clients} client(s) and gross exposure of INR {exposure:,.0f}; execution remains locked.", "Research incompleteness and cross-client concentration are active risks even when the business performs.", ["Apply client suitability, concentration, liquidity and cross-book limits before any proposal."]),
        "portfolio_fit": (("evidence_complete" if portfolio_fit_review_complete else "draft"), 74 if portfolio_fit_review_complete else 48, annual, f"I completed the current portfolio-fit review across {positions} position row(s), {clients} client(s) and {risk_limit_clients} client risk-limit checks. I find {risk_breaches} breach(es), {risk_warnings} warning(s), and only {suitable_clients} client(s) with a completed suitable or conditionally suitable review. No add or sizing action is supportable.", "A sound company thesis does not establish client suitability; active concentration breaches and missing suitability records override a positive business view.", ["Resolve the Naval concentration breach, complete client suitability reviews, replace placeholder thesis and exit criteria, refresh stale limits, and compare opportunity cost before any action proposal."]),
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
