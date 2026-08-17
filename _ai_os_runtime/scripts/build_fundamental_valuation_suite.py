#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from statistics import median
from typing import Any

from extract_long_term_source_document import run_psql_json, sql_jsonb, sql_literal


SCENARIOS = {
    "low": {"growth": 0.03, "discount": 0.14, "terminal_growth": 0.03},
    "base": {"growth": 0.08, "discount": 0.12, "terminal_growth": 0.04},
    "high": {"growth": 0.12, "discount": 0.11, "terminal_growth": 0.05},
}


def dcf_equity_value(start_fcf: float, net_debt: float, years: int, growth: float, discount: float, terminal_growth: float) -> float:
    if start_fcf <= 0 or years < 1 or discount <= terminal_growth:
        raise ValueError("invalid DCF inputs")
    fcf = start_fcf
    present_value = 0.0
    for year in range(1, years + 1):
        fcf *= 1 + growth
        present_value += fcf / ((1 + discount) ** year)
    terminal_value = fcf * (1 + terminal_growth) / (discount - terminal_growth)
    return present_value + terminal_value / ((1 + discount) ** years) - net_debt


def implied_growth(target_equity_value: float, start_fcf: float, net_debt: float, years: int, discount: float, terminal_growth: float) -> float:
    low, high = -0.20, 0.60
    for _ in range(100):
        midpoint = (low + high) / 2
        value = dcf_equity_value(start_fcf, net_debt, years, midpoint, discount, terminal_growth)
        if value < target_equity_value:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def crore(value: object, unit: str) -> float:
    number = float(value)
    normalized = unit.strip().lower()
    if normalized == "lakh":
        return number / 100.0
    if normalized == "crore":
        return number
    raise ValueError(f"unsupported financial unit: {unit}")


def build_models(context: dict[str, Any]) -> list[dict[str, Any]]:
    facts_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in context["facts"]:
        facts_by_key.setdefault(str(row["fact_key"]), []).append(row)
    fcf_history = []
    ocf_by_year = {int(row["fiscal_year"]): crore(row["value_numeric"], row["unit"]) for row in facts_by_key.get("operating_cash_flow", [])}
    capex_by_year = {int(row["fiscal_year"]): crore(row["value_numeric"], row["unit"]) for row in facts_by_key.get("capital_expenditure", [])}
    for year in sorted(set(ocf_by_year) & set(capex_by_year)):
        fcf_history.append({"fiscal_year": year, "fcf_crore": ocf_by_year[year] + capex_by_year[year]})
    positive_recent = [row["fcf_crore"] for row in fcf_history[-3:] if row["fcf_crore"] > 0]
    if len(positive_recent) < 2:
        raise ValueError("at least two positive recent source-backed FCF observations are required")
    normalized_fcf = median(positive_recent)
    latest = lambda key: max(facts_by_key[key], key=lambda row: int(row["fiscal_year"]))
    cash = crore(latest("cash_and_cash_equivalents")["value_numeric"], latest("cash_and_cash_equivalents")["unit"])
    current_debt = crore(latest("current_borrowings")["value_numeric"], latest("current_borrowings")["unit"])
    noncurrent_debt = crore(latest("non_current_borrowings")["value_numeric"], latest("non_current_borrowings")["unit"])
    revenue = crore(latest("revenue_from_operations")["value_numeric"], latest("revenue_from_operations")["unit"])
    pat = crore(latest("profit_after_tax")["value_numeric"], latest("profit_after_tax")["unit"])
    net_debt = current_debt + noncurrent_debt - cash
    inputs = {row["input_key"]: row for row in context["valuation_inputs"]}
    shares = float(inputs["diluted_weighted_average_shares"]["value_numeric"])
    shares_crore = shares / 10_000_000.0
    diluted_eps = float(inputs["diluted_eps_continuing"]["value_numeric"])
    current_price = float(context["quote"]["price"])
    quote_source = {key: context["quote"].get(key) for key in (
        "provider", "provider_symbol", "symbol", "exchange", "price", "quote_ts", "source_key"
    )}
    evidence = context["evidence"]
    evidence_ref = {
        "source": evidence["source_url"], "evidence_id": evidence["id"],
        "source_title": evidence["source_title"], "source_page": inputs["diluted_eps_continuing"]["source_page"],
    }
    common_assumptions = {
        "calculation_status": "complete_unreviewed",
        "financial_snapshot": {"revenue_crore": revenue, "pat_crore": pat, "ocf_crore": ocf_by_year[max(ocf_by_year)], "normalized_fcf_crore": normalized_fcf, "net_debt_crore": net_debt},
        "fcf_history": fcf_history[-5:], "normalization": "median of latest three positive OCF less capex observations",
        "diluted_shares": shares, "diluted_eps_continuing": diluted_eps,
        "current_price": current_price, "current_price_source": quote_source,
        "source_evidence": [evidence_ref], "operator_review_required_for_investment_decision": True,
    }
    dcf_values = {}
    for key, assumptions in SCENARIOS.items():
        equity = dcf_equity_value(normalized_fcf, net_debt, 10, **assumptions)
        dcf_values[key] = round(equity / shares_crore, 2)
    market_cap = current_price * shares_crore
    reverse_growth = implied_growth(market_cap, normalized_fcf, net_debt, 10, 0.12, 0.04)
    multiple_values = {"low": round(diluted_eps * 18, 2), "base": round(diluted_eps * 25, 2), "high": round(diluted_eps * 32, 2)}
    return [
        {
            "model_key": "dcf", "model_name": "Source-Backed 10-Year DCF", "model_type": "dcf",
            "values": dcf_values, "assumptions": {**common_assumptions, "years": 10, "scenarios": SCENARIOS},
            "outputs": {"fair_values_per_share": dcf_values, "normalized_fcf_crore": normalized_fcf, "net_debt_crore": round(net_debt, 2)},
        },
        {
            "model_key": "reverse_dcf", "model_name": "Market-Implied Reverse DCF", "model_type": "reverse_dcf",
            "values": {"low": current_price, "base": current_price, "high": current_price},
            "assumptions": {**common_assumptions, "years": 10, "discount_rate": 0.12, "terminal_growth": 0.04},
            "outputs": {"market_cap_crore": round(market_cap, 2), "implied_annual_fcf_growth": round(reverse_growth, 6), "interpretation": "growth required for modeled equity value to equal the current market price"},
        },
        {
            "model_key": "earnings_multiples", "model_name": "Earnings Multiple Sensitivity", "model_type": "multiples",
            "values": multiple_values,
            "assumptions": {**common_assumptions, "pe_multiples": {"low": 18, "base": 25, "high": 32}, "scope_warning": "subject-company earnings sensitivity; not a completed peer-comparable valuation"},
            "outputs": {"fair_values_per_share": multiple_values, "current_pe": round(current_price / diluted_eps, 2)},
        },
    ]


def load_context(symbol: str, exchange: str, as_of: datetime) -> dict[str, Any]:
    result = run_psql_json(f"""
      WITH company AS (SELECT * FROM research.companies WHERE upper(primary_symbol)={sql_literal(symbol)} AND upper(primary_exchange)={sql_literal(exchange)} LIMIT 1),
      thesis AS (SELECT thesis.* FROM portfolio.holding_theses thesis JOIN company ON upper(thesis.symbol)=upper(company.primary_symbol) AND upper(thesis.exchange)=upper(company.primary_exchange) ORDER BY thesis.id LIMIT 1),
      evidence AS (SELECT evidence.* FROM research.fundamental_evidence evidence JOIN company ON company.id=evidence.company_id WHERE evidence.id=(SELECT evidence_id FROM research.company_valuation_inputs input JOIN company ON company.id=input.company_id WHERE input.fiscal_year=2026 AND input.verification_status NOT IN ('rejected','superseded') ORDER BY input.available_at DESC LIMIT 1)),
      quote AS (SELECT quote.* FROM market.v_latest_price_quotes quote JOIN company ON upper(quote.symbol)=upper(company.primary_symbol) WHERE quote.quote_ts<={sql_literal(as_of.isoformat())}::timestamptz ORDER BY quote.quote_ts DESC LIMIT 1)
      SELECT json_build_object(
        'company',(SELECT row_to_json(company) FROM company),'thesis',(SELECT row_to_json(thesis) FROM thesis),
        'evidence',(SELECT row_to_json(evidence) FROM evidence),'quote',(SELECT row_to_json(quote) FROM quote),
        'valuation_inputs',coalesce((SELECT json_agg(row_to_json(input) ORDER BY input.input_key) FROM research.company_valuation_inputs input JOIN company ON company.id=input.company_id WHERE input.fiscal_year=2026 AND input.available_at<={sql_literal(as_of.isoformat())}::timestamptz AND input.verification_status NOT IN ('rejected','superseded')),'[]'::json),
        'facts',coalesce((SELECT json_agg(row_to_json(row) ORDER BY row.fact_key,row.fiscal_year) FROM (SELECT definition.fact_key,fact.fiscal_year,fact.value_numeric,fact.unit,fact.evidence_id FROM research.company_statement_facts fact JOIN research.statement_fact_definitions definition ON definition.id=fact.fact_definition_id JOIN company ON company.id=fact.company_id WHERE fact.fiscal_period='FY' AND fact.is_current AND fact.available_at<={sql_literal(as_of.isoformat())}::timestamptz AND definition.fact_key IN ('operating_cash_flow','capital_expenditure','cash_and_cash_equivalents','current_borrowings','non_current_borrowings','revenue_from_operations','profit_after_tax')) row),'[]'::json)
      )::text
    """)
    if not isinstance(result, dict) or not all(result.get(key) for key in ("company", "thesis", "evidence", "quote", "valuation_inputs", "facts")):
        raise ValueError("company, thesis, primary evidence, quote, valuation inputs and statement facts are required")
    return result


def persist(context: dict[str, Any], models: list[dict[str, Any]], actor: str) -> dict[str, Any]:
    thesis_id = int(context["thesis"]["id"])
    evidence = [{"source": context["evidence"]["source_url"], "evidence_id": context["evidence"]["id"], "source_page": context["valuation_inputs"][0]["source_page"]}]
    values = []
    for model in models:
        values.append("(" + ",".join((
            str(thesis_id), sql_literal(model["model_key"]), sql_literal(model["model_name"]), sql_literal(model["model_type"]),
            str(model["values"]["low"]), str(model["values"]["base"]), str(model["values"]["high"]),
            sql_jsonb(model["assumptions"]), sql_jsonb(model["outputs"]), sql_literal(actor), sql_jsonb(evidence),
        )) + ")")
    result = run_psql_json(f"""
      WITH incoming(holding_thesis_id,model_key,model_name,model_type,fair_value_low,fair_value_base,
        fair_value_high,assumptions,outputs,owner_agent,evidence) AS (VALUES {','.join(values)}),
      upserted AS (
        INSERT INTO portfolio.holding_valuation_models (holding_thesis_id,model_key,model_name,model_type,status,
          fair_value_low,fair_value_base,fair_value_high,assumptions,outputs,owner_agent)
        SELECT holding_thesis_id,model_key,model_name,model_type,'complete',fair_value_low,fair_value_base,
          fair_value_high,assumptions,outputs,owner_agent FROM incoming
        ON CONFLICT (holding_thesis_id,model_key) DO UPDATE SET model_name=EXCLUDED.model_name,
          model_type=EXCLUDED.model_type,status='complete',fair_value_low=EXCLUDED.fair_value_low,
          fair_value_base=EXCLUDED.fair_value_base,fair_value_high=EXCLUDED.fair_value_high,
          assumptions=EXCLUDED.assumptions,outputs=EXCLUDED.outputs,owner_agent=EXCLUDED.owner_agent,updated_at=now()
        RETURNING *
      ), audit AS (
        INSERT INTO portfolio.holding_thesis_research_updates (holding_thesis_id,update_kind,model_key,status,
          fair_value_low,fair_value_base,fair_value_high,assumptions,outputs,evidence,source_summary,created_by)
        SELECT model.holding_thesis_id,'valuation_update',model.model_key,model.status,model.fair_value_low,
          model.fair_value_base,model.fair_value_high,model.assumptions,model.outputs,incoming.evidence,
          {sql_jsonb({'source': 'build_fundamental_valuation_suite.py', 'calculation_complete': True, 'operator_reviewed': False, 'capital_action_allowed': False})},
          {sql_literal(actor)} FROM upserted model JOIN incoming USING (holding_thesis_id,model_key)
        RETURNING id
      ) SELECT json_build_object('models',coalesce((SELECT json_agg(json_build_object('model_key',model_key,'model_type',model_type,'status',status,'fair_value_low',fair_value_low,'fair_value_base',fair_value_base,'fair_value_high',fair_value_high) ORDER BY model_key) FROM upserted),'[]'::json),'audit_rows',(SELECT count(*) FROM audit))::text
    """)
    if not isinstance(result, dict):
        raise RuntimeError("valuation suite persistence returned an invalid result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic source-backed DCF, reverse DCF and earnings-multiple calculations.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--actor", default="Valuation Agent")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        raise ValueError("as-of requires timezone")
    context = load_context(args.symbol.upper(), args.exchange.upper(), as_of)
    models = build_models(context)
    database = persist(context, models, args.actor) if args.persist else {"written": 0}
    print(json.dumps({"ok": True, "symbol": args.symbol.upper(), "models": models, "database": database,
                      "calculation_complete": True, "operator_reviewed": False,
                      "capital_action_allowed": False, "broker_write_allowed": False}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
