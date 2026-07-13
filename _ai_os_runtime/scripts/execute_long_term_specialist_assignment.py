#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
OUTPUT_DIR = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Long-Term Specialist Outputs"


CHECKLIST_MODULES = {
    "business_model",
    "moat_scorecard",
    "industry_structure",
    "management_scorecard",
    "governance_scorecard",
    "capital_allocation",
    "financial_quality",
    "forensic_accounting",
}

VALUATION_MODEL_KEYS = [
    "dcf",
    "reverse_dcf",
    "sum_of_parts",
    "peer_comparison",
    "historical_valuation",
    "scenario_builder",
    "expected_cagr",
    "long_term_monte_carlo",
]


CHECKLIST_RULES = {
    "business_model": [
        {
            "key": "core_activity",
            "label": "Core activity and value proposition",
            "terms": ["wire rope", "specialty wire rope", "engineering solutions"],
            "question": "What does the company sell and why do customers use it?",
        },
        {
            "key": "end_markets",
            "label": "End-market diversity",
            "terms": ["oil & gas", "mining", "elevators", "ports", "construction", "renewable energy"],
            "question": "Which end markets drive demand?",
        },
        {
            "key": "operating_model",
            "label": "Operating model and transformation",
            "terms": ["one usha martin", "unified enterprise", "operational excellence", "sap s/4hana"],
            "question": "Is the operating model coherent and improving?",
        },
        {
            "key": "financial_model",
            "label": "Revenue, margin, cash conversion",
            "terms": ["revenue", "ebitda", "pat", "operating cash flow", "margin"],
            "question": "Does the source show the economic engine?",
        },
    ],
    "moat_scorecard": [
        {
            "key": "specialized_product",
            "label": "Specialized product capability",
            "terms": ["high-performance steel ropes", "specialty wire rope", "advanced products"],
            "question": "Is there evidence of differentiated capability?",
        },
        {
            "key": "global_presence",
            "label": "Global footprint and customers",
            "terms": ["global", "international", "customers", "worldwide"],
            "question": "Is there evidence of reach beyond a local commodity producer?",
        },
        {
            "key": "innovation",
            "label": "R&D and product innovation",
            "terms": ["r&d", "product innovation", "technology", "advanced analytics"],
            "question": "Is there reinvestment into capability?",
        },
        {
            "key": "switching_or_mission_criticality",
            "label": "Mission-critical use cases",
            "terms": ["critical sectors", "offshore drilling", "cranes", "elevators", "mining"],
            "question": "Do use cases imply reliability requirements?",
        },
    ],
    "industry_structure": [
        {
            "key": "served_industries",
            "label": "Served industry breadth",
            "terms": ["oil & gas", "mining", "elevators", "ports", "construction", "renewable energy"],
            "negative_terms": ["single customer", "single segment"],
            "question": "Does the company serve multiple durable end markets?",
        },
        {
            "key": "global_competition",
            "label": "Global competitive arena",
            "terms": ["global", "international market", "worldwide", "global presence"],
            "negative_terms": ["regional silos", "competitive pressure"],
            "question": "Is the business competing and selling beyond a local market?",
        },
        {
            "key": "demand_drivers",
            "label": "Demand drivers",
            "terms": ["infrastructure", "offshore drilling", "renewable energy", "cranes", "elevators"],
            "negative_terms": ["cyclical", "slowdown", "weak demand"],
            "question": "Are demand drivers identifiable from source evidence?",
        },
        {
            "key": "technology_change",
            "label": "Technology and capability change",
            "terms": ["technology", "r&d", "product innovation", "advanced analytics", "sap s/4hana"],
            "negative_terms": ["obsolete", "substitution"],
            "question": "Does industry positioning require and show capability investment?",
        },
    ],
    "management_scorecard": [
        {
            "key": "strategic_clarity",
            "label": "Strategic clarity",
            "terms": ["one usha martin", "unified enterprise", "vision", "mission", "purpose"],
            "negative_terms": ["frequent changes", "uncertain"],
            "question": "Does management explain a coherent strategic direction?",
        },
        {
            "key": "execution_focus",
            "label": "Execution and operating discipline",
            "terms": ["operational excellence", "sap s/4hana", "streamlining decision-making", "cross-functional integration"],
            "negative_terms": ["delay", "cost overrun"],
            "question": "Is there evidence of operational execution, not only narrative?",
        },
        {
            "key": "stakeholder_language",
            "label": "Stakeholder orientation",
            "terms": ["customers", "employees", "partners", "shareholders", "long-term value"],
            "negative_terms": ["minority", "dispute"],
            "question": "Does management frame value creation broadly and responsibly?",
        },
        {
            "key": "capital_discipline",
            "label": "Financial discipline",
            "terms": ["net debt", "operating cash flow", "roce", "dividend", "capex"],
            "negative_terms": ["high debt", "default", "qualified opinion"],
            "question": "Is there source evidence of financial discipline?",
        },
    ],
    "governance_scorecard": [
        {
            "key": "board_reporting",
            "label": "Board and statutory reporting",
            "terms": ["report of the board of directors", "corporate governance", "notice to shareholders"],
            "negative_terms": ["non-compliance", "penalty"],
            "question": "Are statutory governance materials present in the annual report?",
        },
        {
            "key": "audit_presence",
            "label": "Auditor coverage",
            "terms": ["independent auditor", "standalone financial statements", "consolidated financial statements"],
            "negative_terms": ["qualified opinion", "emphasis of matter", "material weakness"],
            "question": "Is auditor coverage present for standalone and consolidated accounts?",
        },
        {
            "key": "sustainability_and_responsibility",
            "label": "Sustainability and responsibility reporting",
            "terms": ["business responsibility", "sustainability report", "esg", "solar rooftop"],
            "negative_terms": ["environmental penalty", "show cause"],
            "question": "Is responsibility reporting available for review?",
        },
        {
            "key": "shareholder_process",
            "label": "Shareholder process",
            "terms": ["agm", "e-voting", "cut-off date", "dividend"],
            "negative_terms": ["delayed agm", "shareholder complaint"],
            "question": "Are shareholder process details clearly disclosed?",
        },
    ],
    "capital_allocation": [
        {
            "key": "reinvestment",
            "label": "Reinvestment and capex",
            "terms": ["capex", "r&d", "product innovation", "sap s/4hana", "solar rooftop"],
            "negative_terms": ["underinvestment", "abandoned project"],
            "question": "Is reinvestment visible and tied to capability?",
        },
        {
            "key": "cash_generation",
            "label": "Cash generation",
            "terms": ["operating cash flow", "ocf", "ebitda conversion", "free cash flow"],
            "negative_terms": ["negative cash flow", "cash loss"],
            "question": "Does the business convert accounting profit into cash?",
        },
        {
            "key": "balance_sheet",
            "label": "Balance-sheet discipline",
            "terms": ["net debt", "debt", "financial discipline", "liquidity"],
            "negative_terms": ["default", "debt restructuring", "breach"],
            "question": "Is balance-sheet discipline visible?",
        },
        {
            "key": "shareholder_returns",
            "label": "Shareholder returns",
            "terms": ["dividend", "shareholders", "roce", "return on capital"],
            "negative_terms": ["dilution", "preferential allotment"],
            "question": "Is capital allocation linked to shareholder value?",
        },
    ],
    "financial_quality": [
        {
            "key": "revenue_growth",
            "label": "Revenue and volume growth",
            "terms": ["revenue grew", "sales volumes", "revenue", "wire rope continued"],
            "negative_terms": ["revenue declined", "volume declined"],
            "question": "Is growth visible and source-backed?",
        },
        {
            "key": "profitability",
            "label": "Profitability and margin",
            "terms": ["ebitda", "healthy margin", "profit after tax", "ebitda per tonne"],
            "negative_terms": ["margin pressure", "loss"],
            "question": "Is profitability visible and not only revenue growth?",
        },
        {
            "key": "cash_conversion",
            "label": "Cash conversion",
            "terms": ["operating cash flow", "ebitda conversion", "ocf", "cash flow"],
            "negative_terms": ["negative operating cash", "working capital stretch"],
            "question": "Does cash conversion support earnings quality?",
        },
        {
            "key": "leverage",
            "label": "Leverage and debt",
            "terms": ["net debt", "reduced net debt", "financial discipline"],
            "negative_terms": ["high leverage", "default", "debt restructuring"],
            "question": "Is leverage controlled?",
        },
    ],
    "forensic_accounting": [
        {
            "key": "auditor_coverage",
            "label": "Auditor coverage",
            "terms": ["independent auditor", "auditor", "standalone financial statements", "consolidated financial statements"],
            "negative_terms": ["qualified opinion", "adverse opinion", "disclaimer of opinion"],
            "question": "Are audited statements present and are obvious adverse terms absent?",
        },
        {
            "key": "cash_vs_profit",
            "label": "Cash versus profit",
            "terms": ["profit after tax", "operating cash flow", "ebitda conversion"],
            "negative_terms": ["negative operating cash", "cash loss"],
            "question": "Does cash flow broadly corroborate profit?",
        },
        {
            "key": "debt_risk",
            "label": "Debt and solvency risk",
            "terms": ["net debt", "financial discipline", "liquidity"],
            "negative_terms": ["default", "breach of covenant", "debt restructuring"],
            "question": "Are obvious debt-risk terms absent while debt metrics are disclosed?",
        },
        {
            "key": "related_party_and_contingent_review",
            "label": "Related-party and notes review",
            "terms": ["notes to", "related party", "contingent", "corporate governance"],
            "negative_terms": ["fraud", "investigation", "material weakness"],
            "question": "Are notes/governance sections available for deeper manual forensic review?",
        },
    ],
}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def clean(value: object, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    text = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return text or fallback


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug[:90] or "long-term-specialist-output"


def fetch_one(sql: str, error: str) -> dict[str, Any]:
    rows = run_psql_json(sql)
    if not rows:
        raise ValueError(error)
    return rows[0]


def fetch_assignment(assignment_id: int | None, assignment_key: str | None) -> dict[str, Any]:
    where = ""
    if assignment_id:
        where = f"WHERE id = {int(assignment_id)}"
    elif assignment_key:
        where = f"WHERE assignment_key = {sql_literal(assignment_key)}"
    else:
        where = "WHERE status = 'queued'"
    return fetch_one(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_specialist_assignments
            {where}
            ORDER BY updated_at ASC, id ASC
            LIMIT 1
        ) rows
        """,
        "No matching Long-Term specialist assignment found.",
    )


def fetch_context(assignment: dict[str, Any]) -> dict[str, Any]:
    thesis_id = int(assignment["holding_thesis_id"])
    symbol = clean(assignment.get("symbol")).upper()
    exchange = clean(assignment.get("exchange"))
    query_symbol = sql_literal(symbol)
    return {
        "thesis": fetch_one(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT *
                FROM portfolio.v_long_term_thesis_control
                WHERE id = {thesis_id}
            ) rows
            """,
            f"holding thesis {thesis_id} not found",
        ),
        "positions": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT client_name, client_code, book_key, symbol, exchange,
                       quantity, market_value, purpose_name, owner_agent, thesis,
                       exit_criteria, as_of
                FROM books.v_book_positions
                WHERE upper(symbol) = {query_symbol}
                ORDER BY market_value DESC NULLS LAST
                LIMIT 25
            ) rows
            """
        ),
        "symbol_exposure": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT *
                FROM books.v_symbol_book_exposure
                WHERE upper(symbol) = {query_symbol}
                ORDER BY gross_exposure DESC NULLS LAST
                LIMIT 25
            ) rows
            """
        ),
        "quotes": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT symbol, exchange, price, change_percent, provider, provider_symbol,
                       quote_ts, created_at
                FROM market.v_latest_price_quotes
                WHERE upper(symbol) = {query_symbol}
                   OR (upper(symbol) = {query_symbol} AND exchange = {sql_literal(exchange)})
                ORDER BY quote_ts DESC NULLS LAST, created_at DESC NULLS LAST
                LIMIT 5
            ) rows
            """
        ),
        "filings": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id, exchange, symbol, filing_type, event_type, title, filed_at,
                       source_url, attachment_url, extraction_status, local_path
                FROM research.corporate_filings
                WHERE upper(symbol) = {query_symbol}
                ORDER BY filed_at DESC NULLS LAST, created_at DESC
                LIMIT 20
            ) rows
            """
        ),
        "source_documents": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id, document_key, source_request_id, request_key, symbol,
                       document_type, document_title, source_url, local_path,
                       source_name, provenance_status, http_status,
                       raw_artifact_id, obsidian_note_id, note_path, updated_at
                FROM portfolio.v_long_term_source_documents
                WHERE upper(symbol) = {query_symbol}
                  AND provenance_status IN ('verified','registered')
                ORDER BY updated_at DESC, id DESC
                LIMIT 20
            ) rows
            """
        ),
        "source_extractions": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id, source_document_id, raw_artifact_id, symbol,
                       document_type, document_title, source_url,
                       local_text_path, parser_name, page_count,
                       extracted_chars, text_excerpt, key_snippets,
                       extraction_status, extracted_at
                FROM portfolio.v_long_term_source_document_extractions
                WHERE upper(symbol) = {query_symbol}
                  AND extraction_status = 'extracted'
                ORDER BY extracted_at DESC, id DESC
                LIMIT 10
            ) rows
            """
        ),
        "research_updates": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id, update_kind, checklist_key, model_key, status,
                       score, note_path, source_summary, created_by, created_at
                FROM portfolio.v_long_term_research_updates
                WHERE holding_thesis_id = {thesis_id}
                ORDER BY created_at DESC
                LIMIT 30
            ) rows
            """
        ),
        "checklists": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT checklist_key, checklist_name, status, score, owner_agent, updated_at
                FROM portfolio.v_long_term_thesis_checklists
                WHERE holding_thesis_id = {thesis_id}
                ORDER BY checklist_key
            ) rows
            """
        ),
        "valuations": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT model_key, model_name, status, fair_value_base,
                       expected_cagr_pct, owner_agent, updated_at
                FROM portfolio.v_long_term_valuation_models
                WHERE holding_thesis_id = {thesis_id}
                ORDER BY model_key
            ) rows
            """
        ),
        "risk_limits": run_psql_json(
            """
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT *
                FROM books.book_risk_limits
                WHERE enabled = true
                  AND book_key IN ('long_term','hedges','tactical','quant','active_trading')
                ORDER BY book_key, severity DESC, limit_key
                LIMIT 50
            ) rows
            """
        ),
        "source_gaps": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT checklist_key, checklist_name, status, score, owner_agent
                FROM portfolio.v_long_term_thesis_checklists
                WHERE holding_thesis_id = {thesis_id}
                  AND status IN ('not_started','source_required','in_progress','red_flag_review')
                ORDER BY checklist_key
            ) rows
            """
        ),
        "notes": run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT note_path, title, note_type, body_summary, indexed_at
                FROM knowledge.obsidian_notes
                WHERE title ILIKE {sql_literal('%' + symbol + '%')}
                   OR body_summary ILIKE {sql_literal('%' + symbol + '%')}
                ORDER BY indexed_at DESC NULLS LAST
                LIMIT 20
            ) rows
            """
        ),
    }


def source_available(source_name: str, context: dict[str, Any]) -> bool:
    normalized = source_name.lower()
    filings = context["filings"]
    source_documents = context["source_documents"]
    source_extractions = context["source_extractions"]
    updates = context["research_updates"]
    checklists = context["checklists"]
    valuations = context["valuations"]
    if normalized == "research_packet":
        return any(update.get("update_kind") == "research_packet" for update in updates)
    if normalized in {"company_filings", "corporate_filings"}:
        return bool(filings) or bool(source_documents)
    if normalized in {"annual_report", "annual_reports", "annual_report_or_investor_presentation", "audited_financials", "financial_history", "cash_flow_statement", "balance_sheet_history", "notes_to_accounts", "auditor_notes"}:
        return any("annual" in clean(filing.get("title"), "").lower() or "annual" in clean(filing.get("filing_type"), "").lower() for filing in filings) or any(
            "annual" in clean(document.get("document_title"), "").lower() or "annual" in clean(document.get("document_type"), "").lower()
            for document in source_documents
        )
    if normalized in {"promoter_governance_sources", "related_party_disclosures", "corporate_action_history", "competitor_or_industry_sources", "industry_sources"}:
        return bool(filings) or bool(source_documents) or bool(context["notes"]) or bool(source_extractions)
    if normalized == "latest_price":
        return bool(context["quotes"])
    if normalized in {"book_positions", "client_exposure", "symbol_book_exposure", "portfolio_exposure"}:
        return bool(context["positions"]) or bool(context["symbol_exposure"])
    if normalized == "checklist_findings":
        return any(row.get("status") in {"complete", "reviewed", "needs_review"} for row in checklists)
    if normalized == "valuation_findings":
        return any(row.get("status") in {"complete", "reviewed", "needs_review"} for row in valuations)
    if normalized == "risk_evidence":
        return bool(context["symbol_exposure"]) or bool(context["positions"])
    if normalized == "committee_review":
        return True
    if normalized == "risk_limits":
        return bool(context.get("risk_limits"))
    if normalized == "source_gaps":
        return True
    if normalized == "growth_margin_reinvestment_assumptions":
        return bool(source_extractions) or any(row.get("status") in {"complete", "reviewed", "needs_review"} for row in valuations)
    return False


def extraction_evidence_text(context: dict[str, Any]) -> str:
    parts: list[str] = []
    for extraction in context.get("source_extractions") or []:
        parts.append(clean(extraction.get("text_excerpt"), ""))
        for snippet in extraction.get("key_snippets") or []:
            parts.append(clean(snippet.get("snippet"), ""))
    return "\n".join(part for part in parts if part)


def find_term_snippet(text: str, term: str) -> str | None:
    lowered = text.lower()
    index = lowered.find(term.lower())
    if index < 0:
        return None
    start = max(0, index - 220)
    end = min(len(text), index + 520)
    return clean(text[start:end])


def negative_context_is_mitigated(snippet: str) -> bool:
    lowered = snippet.lower()
    mitigators = [
        "moving away from",
        "reduced",
        "reducing",
        "absence of",
        "no material",
        "not material",
        "without",
        "resolved",
    ]
    return any(term in lowered for term in mitigators)


def build_structured_checklist(module_key: str, context: dict[str, Any]) -> dict[str, Any] | None:
    rules = CHECKLIST_RULES.get(module_key)
    if not rules:
        return None
    text = extraction_evidence_text(context)
    items: list[dict[str, Any]] = []
    total_hits = 0
    for rule in rules:
        matched: list[dict[str, str]] = []
        for term in rule["terms"]:
            snippet = find_term_snippet(text, term)
            if snippet:
                matched.append({"term": term, "snippet": snippet[:700]})
        negative_matched: list[dict[str, str]] = []
        for term in rule.get("negative_terms", []):
            snippet = find_term_snippet(text, term)
            if snippet and not negative_context_is_mitigated(snippet):
                negative_matched.append({"term": term, "snippet": snippet[:700]})
        total_hits += len(matched)
        item_score = min(10, 3 + len(matched) * 2) if matched else 0
        item_score = max(0, item_score - len(negative_matched) * 2)
        items.append(
            {
                "key": rule["key"],
                "label": rule["label"],
                "question": rule["question"],
                "status": "red_flag_review" if negative_matched else ("evidence_found" if matched else "evidence_missing"),
                "score": item_score,
                "matched_terms": [row["term"] for row in matched],
                "negative_terms": [row["term"] for row in negative_matched],
                "evidence": matched[:4],
                "negative_evidence": negative_matched[:4],
            }
        )
    possible_score = len(rules) * 10
    score = round(sum(float(item["score"]) for item in items) / possible_score * 100, 1) if possible_score else None
    missing = [item["key"] for item in items if item["status"] == "evidence_missing"]
    red_flags = [item["key"] for item in items if item["status"] == "red_flag_review"]
    return {
        "module_key": module_key,
        "score": score,
        "status": "red_flag_review" if red_flags else ("needs_review" if not missing else "in_progress"),
        "items": items,
        "missing_items": missing,
        "red_flag_items": red_flags,
        "source_extraction_count": len(context.get("source_extractions") or []),
        "total_term_hits": total_hits,
        "method": "deterministic_source_term_score_v1",
    }


def first_number_near(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    raw = next((group for group in match.groups() if group), match.group(0))
    raw = raw.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    number_match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", raw)
    if not number_match:
        return None
    try:
        return float(number_match.group(0))
    except ValueError:
        return None


def financial_snapshot_from_text(context: dict[str, Any]) -> dict[str, Any]:
    text = extraction_evidence_text(context)
    return {
        "revenue_crore": first_number_near(text, r"revenue(?:\s+grew[^\n]{0,80}?to)?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)\s*crore"),
        "ebitda_crore": first_number_near(text, r"ebitda(?:\s+was)?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)\s*crore"),
        "pat_crore": first_number_near(text, r"profit after tax stood at\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)\s*crore|pat\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)"),
        "ocf_crore": first_number_near(text, r"operating cash flow[^\n]{0,120}?(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)\s*crore|ocf\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)"),
        "net_debt_crore": first_number_near(text, r"net debt(?:\s+to)?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+(?:\.[0-9]+)?)\s*c"),
        "roce_pct": first_number_near(text, r"([0-9]+(?:\.[0-9]+)?)%\s*ROCE|ROCE\s*([0-9]+(?:\.[0-9]+)?)%"),
        "revenue_growth_pct": first_number_near(text, r"revenue grew\s*([0-9]+(?:\.[0-9]+)?)%"),
        "volume_growth_pct": first_number_near(text, r"([0-9]+(?:\.[0-9]+)?)%\s+increase in sales volumes"),
    }


def latest_price(context: dict[str, Any]) -> float | None:
    for quote in context.get("quotes") or []:
        try:
            return float(quote.get("price"))
        except (TypeError, ValueError):
            continue
    for position in context.get("positions") or []:
        try:
            return float(position.get("market_price"))
        except (TypeError, ValueError):
            continue
    return None


def build_structured_decision_module(module_key: str, context: dict[str, Any], missing_sources: list[str]) -> dict[str, Any] | None:
    financials = financial_snapshot_from_text(context)
    price = latest_price(context)
    checklist_rows = context.get("checklists") or []
    valuation_rows = context.get("valuations") or []
    positions = context.get("positions") or []
    exposure = context.get("symbol_exposure") or []
    risk_limits = context.get("risk_limits") or []
    source_gaps = context.get("source_gaps") or []
    if module_key == "valuation_suite":
        ebitda = financials.get("ebitda_crore")
        pat = financials.get("pat_crore")
        revenue = financials.get("revenue_crore")
        assumptions = {
            "current_price": price,
            "financial_snapshot": financials,
            "source_extraction_count": len(context.get("source_extractions") or []),
            "model_scope": "preliminary_source_backed_assumption_set",
            "fair_value_policy": "No final fair value produced until share count, normalized FCF, discount rate, and terminal assumptions are explicitly reviewed.",
        }
        sanity = []
        if revenue and ebitda:
            sanity.append({"metric": "ebitda_margin_pct", "value": round(ebitda / revenue * 100, 1)})
        if pat and financials.get("ocf_crore"):
            sanity.append({"metric": "ocf_to_pat", "value": round(financials["ocf_crore"] / pat, 2)})
        return {
            "module_key": module_key,
            "status": "needs_review" if not missing_sources else "source_required",
            "score": None,
            "items": [
                {"key": "current_price", "status": "available" if price else "missing", "value": price},
                {"key": "financial_snapshot", "status": "available" if any(v is not None for v in financials.values()) else "missing", "value": financials},
                {"key": "sanity_metrics", "status": "available" if sanity else "missing", "value": sanity},
                {"key": "valuation_models", "status": "assumption_ready_not_fair_value", "value": VALUATION_MODEL_KEYS},
            ],
            "assumptions": assumptions,
            "red_flags": [],
            "missing_sources": missing_sources,
            "method": "source_backed_preliminary_valuation_context_v1",
        }
    if module_key == "bear_case":
        weak = [row for row in checklist_rows if row.get("score") is not None and float(row.get("score") or 0) < 80]
        red_flags = [row for row in checklist_rows if row.get("status") == "red_flag_review"]
        thesis_killers = [
            "Wire-rope demand weakens across mining, elevators, cranes, oil & offshore, or infrastructure.",
            "Operating cash flow stops supporting reported PAT.",
            "Net debt rises materially while capex or working capital absorbs cash.",
            "Moat evidence proves commodity-like pricing rather than differentiated specialty ropes.",
            "Governance, related-party, auditor, or contingent-liability review surfaces a material red flag.",
        ]
        return {
            "module_key": module_key,
            "status": "needs_review" if not missing_sources else "source_required",
            "score": max(0, 100 - len(weak) * 8 - len(red_flags) * 15 - len(source_gaps) * 5),
            "items": [
                {"key": "weak_checklists", "status": "review", "value": weak},
                {"key": "red_flag_checklists", "status": "review", "value": red_flags},
                {"key": "thesis_killers", "status": "required_monitoring", "value": thesis_killers},
            ],
            "red_flags": red_flags,
            "missing_sources": missing_sources,
            "method": "source_backed_bear_case_v1",
        }
    if module_key == "portfolio_fit":
        total_exposure = sum(float(row.get("gross_exposure") or 0) for row in positions)
        client_count = len({row.get("client_code") or row.get("client_name") for row in positions})
        return {
            "module_key": module_key,
            "status": "needs_review" if not missing_sources else "source_required",
            "score": 85 if positions and risk_limits else 60,
            "items": [
                {"key": "position_rows", "status": "available" if positions else "missing", "value": len(positions)},
                {"key": "client_count", "status": "available" if client_count else "missing", "value": client_count},
                {"key": "gross_exposure", "status": "available", "value": total_exposure},
                {"key": "risk_limits", "status": "available" if risk_limits else "missing", "value": risk_limits},
                {"key": "book_exposure", "status": "available" if exposure else "missing", "value": exposure[:5]},
            ],
            "red_flags": [],
            "missing_sources": missing_sources,
            "method": "portfolio_fit_source_context_v1",
        }
    if module_key == "risk_review":
        unresolved = source_gaps
        risk_flags = []
        if unresolved:
            risk_flags.append({"flag": "open_source_gaps", "rows": unresolved})
        if not risk_limits:
            risk_flags.append({"flag": "risk_limits_missing"})
        return {
            "module_key": module_key,
            "status": "needs_review" if not missing_sources else "source_required",
            "score": max(0, 90 - len(risk_flags) * 15),
            "items": [
                {"key": "risk_limits", "status": "available" if risk_limits else "missing", "value": risk_limits},
                {"key": "source_gaps", "status": "review" if unresolved else "clear", "value": unresolved},
                {"key": "positions", "status": "available" if positions else "missing", "value": len(positions)},
                {"key": "symbol_exposure", "status": "available" if exposure else "missing", "value": exposure[:5]},
            ],
            "red_flags": risk_flags,
            "missing_sources": missing_sources,
            "method": "independent_risk_review_context_v1",
        }
    return None


def build_analysis(assignment: dict[str, Any], context: dict[str, Any], actor: str) -> dict[str, Any]:
    required_sources = assignment.get("required_sources") or []
    missing_sources = [source for source in required_sources if not source_available(str(source), context)]
    source_status = "source_ready" if not missing_sources else "source_required"
    output_status = "needs_review" if not missing_sources else "source_required"
    confidence = "medium" if not missing_sources else "low"
    symbol = clean(assignment.get("symbol")).upper()
    module_key = clean(assignment.get("module_key"))
    filings = context["filings"]
    source_documents = context["source_documents"]
    source_extractions = context["source_extractions"]
    quotes = context["quotes"]
    positions = context["positions"]
    exposure = context["symbol_exposure"]
    updates = context["research_updates"]
    structured_checklist = None if missing_sources else build_structured_checklist(module_key, context)
    structured_decision = build_structured_decision_module(module_key, context, missing_sources)
    if structured_checklist and structured_checklist["missing_items"]:
        output_status = "in_progress"
    elif structured_checklist:
        output_status = "needs_review"
    elif structured_decision:
        output_status = structured_decision["status"]
    findings = [
        {
            "finding": f"{assignment['agent_name']} executed {assignment['module_name']} for {symbol}.",
            "status": output_status,
            "source_status": source_status,
        },
        {
            "finding": "Live warehouse context was checked before writing this output.",
            "positions": len(positions),
            "symbol_exposure_rows": len(exposure),
            "latest_quotes": len(quotes),
            "corporate_filings": len(filings),
            "source_documents": len(source_documents),
            "source_extractions": len(source_extractions),
            "research_updates": len(updates),
        },
    ]
    if missing_sources:
        findings.append(
            {
                "finding": "Module cannot be marked complete because required source evidence is missing.",
                "missing_sources": missing_sources,
            }
        )
    if structured_checklist:
        findings.append(
            {
                "finding": f"Structured {module_key} checklist generated from extracted source text.",
                "method": structured_checklist["method"],
                "score": structured_checklist["score"],
                "missing_items": structured_checklist["missing_items"],
                "red_flag_items": structured_checklist["red_flag_items"],
                "source_extraction_count": structured_checklist["source_extraction_count"],
            }
        )
    if structured_decision:
        findings.append(
            {
                "finding": f"Structured {module_key} decision module generated.",
                "method": structured_decision["method"],
                "score": structured_decision.get("score"),
                "red_flag_count": len(structured_decision.get("red_flags") or []),
                "missing_sources": structured_decision.get("missing_sources") or [],
            }
        )
    if module_key == "valuation_suite":
        findings.append(
            {
                "finding": "Valuation suite remains blocked from fair-value output until audited financials and assumptions are available.",
                "valuation_models_checked": VALUATION_MODEL_KEYS,
            }
        )
    elif module_key in {"portfolio_fit", "risk_review"} and positions:
        findings.append(
            {
                "finding": "Portfolio/risk context exists and can be reviewed, but no capital action is authorized by this output.",
                "position_rows": len(positions),
                "exposure_rows": len(exposure),
            }
        )
    evidence = [
        {"table": "portfolio.long_term_specialist_assignments", "id": assignment.get("id")},
        {"view": "portfolio.v_long_term_specialist_assignments", "id": assignment.get("id")},
        {"table": "portfolio.holding_theses", "id": assignment.get("holding_thesis_id")},
        {"table": "books.v_book_positions", "rows": len(positions)},
        {"table": "books.v_symbol_book_exposure", "rows": len(exposure)},
        {"table": "market.v_latest_price_quotes", "rows": len(quotes)},
        {"table": "research.corporate_filings", "rows": len(filings)},
        {"view": "portfolio.v_long_term_source_documents", "rows": len(source_documents)},
        {"view": "portfolio.v_long_term_source_document_extractions", "rows": len(source_extractions)},
        {"table": "portfolio.v_long_term_research_updates", "rows": len(updates)},
        {"capital_action_allowed": False},
        {"live_execution_allowed": False},
    ]
    recommendations = []
    for source in missing_sources:
        recommendations.append(
            {
                "action": f"Collect or ingest required source: {source}",
                "owner": "Filings and Transcript Analyst" if "filing" in source or "annual" in source or "financial" in source else "Long-Term Portfolio Manager",
                "blocks_completion": True,
            }
        )
    recommendations.append(
        {
            "action": "Return completed source evidence to Long-Term Investment Committee before any capital decision.",
            "owner": "Long-Term Portfolio Manager",
            "blocks_completion": False,
        }
    )
    return {
        "output_status": output_status,
        "source_status": source_status,
        "confidence": confidence,
        "findings": findings,
        "source_gaps": [{"source": source, "status": "missing"} for source in missing_sources],
        "evidence": evidence,
        "recommendations": recommendations,
        "metrics": {
            "positions": len(positions),
            "symbol_exposure_rows": len(exposure),
            "latest_quotes": len(quotes),
            "corporate_filings": len(filings),
            "source_documents": len(source_documents),
            "source_extractions": len(source_extractions),
            "research_updates": len(updates),
            "notes": len(context["notes"]),
            "missing_source_count": len(missing_sources),
            "structured_score": structured_checklist.get("score") if structured_checklist else None,
            "structured_missing_items": len(structured_checklist.get("missing_items") or []) if structured_checklist else None,
            "structured_red_flag_items": len(structured_checklist.get("red_flag_items") or []) if structured_checklist else None,
            "structured_decision_score": structured_decision.get("score") if structured_decision else None,
            "structured_decision_red_flags": len(structured_decision.get("red_flags") or []) if structured_decision else None,
            "generated_by": actor,
        },
        "structured_checklist": structured_checklist,
        "structured_decision": structured_decision,
    }


def build_note(assignment: dict[str, Any], context: dict[str, Any], analysis: dict[str, Any], actor: str) -> str:
    symbol = clean(assignment.get("symbol")).upper()
    lines = [
        f"# Long-Term Specialist Output - {symbol} - {assignment['module_name']}",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Generated by: {actor}",
        f"Agent: {assignment['agent_name']}",
        f"Assignment: `{assignment['assignment_key']}`",
        f"Thesis id: `{assignment['holding_thesis_id']}`",
        f"Committee review id: `{clean(assignment.get('committee_review_id'))}`",
        "",
        "## Guardrail",
        "",
        "This output is research-only. It does not authorize buy, add, trim, sell, hedge, broker order, or live strategy action.",
        "",
        "## Status",
        "",
        f"- Output status: `{analysis['output_status']}`",
        f"- Source status: `{analysis['source_status']}`",
        f"- Confidence: `{analysis['confidence']}`",
        "",
        "## Evidence Counts",
        "",
    ]
    metrics = analysis["metrics"]
    for key in ["positions", "symbol_exposure_rows", "latest_quotes", "corporate_filings", "source_documents", "source_extractions", "research_updates", "notes", "missing_source_count"]:
        lines.append(f"- {key}: `{metrics.get(key, 0)}`")
    lines.extend(["", "## Findings", ""])
    for item in analysis["findings"]:
        lines.append(f"- {clean(item.get('finding'))}")
        if item.get("missing_sources"):
            lines.append(f"  Missing: `{', '.join(item['missing_sources'])}`")
    lines.extend(["", "## Source Gaps", ""])
    if analysis["source_gaps"]:
        for gap in analysis["source_gaps"]:
            lines.append(f"- `{gap['source']}` -> `{gap['status']}`")
    else:
        lines.append("- No required source gaps detected by this worker.")
    if analysis.get("structured_checklist"):
        structured = analysis["structured_checklist"]
        lines.extend(["", "## Structured Checklist", ""])
        lines.append(f"- Method: `{structured['method']}`")
        lines.append(f"- Score: `{structured['score']}`")
        lines.append(f"- Status: `{structured['status']}`")
        if structured["missing_items"]:
            lines.append(f"- Missing items: `{', '.join(structured['missing_items'])}`")
        if structured.get("red_flag_items"):
            lines.append(f"- Red-flag review items: `{', '.join(structured['red_flag_items'])}`")
        for item in structured["items"]:
            lines.extend(["", f"### {clean(item.get('label'))}", ""])
            lines.append(f"- Question: {clean(item.get('question'))}")
            lines.append(f"- Status: `{clean(item.get('status'))}`")
            lines.append(f"- Score: `{clean(item.get('score'))}`")
            if item.get("matched_terms"):
                lines.append(f"- Matched terms: `{', '.join(item['matched_terms'])}`")
            if item.get("negative_terms"):
                lines.append(f"- Negative terms: `{', '.join(item['negative_terms'])}`")
            for evidence in item.get("evidence") or []:
                lines.append(f"  - `{clean(evidence.get('term'))}`: {clean(evidence.get('snippet'))[:700]}")
            for evidence in item.get("negative_evidence") or []:
                lines.append(f"  - Red flag `{clean(evidence.get('term'))}`: {clean(evidence.get('snippet'))[:700]}")
    if analysis.get("structured_decision"):
        structured = analysis["structured_decision"]
        lines.extend(["", "## Structured Decision Module", ""])
        lines.append(f"- Method: `{structured['method']}`")
        lines.append(f"- Status: `{structured['status']}`")
        lines.append(f"- Score: `{clean(structured.get('score'))}`")
        if structured.get("missing_sources"):
            lines.append(f"- Missing sources: `{', '.join(structured['missing_sources'])}`")
        for item in structured.get("items") or []:
            lines.extend(["", f"### {clean(item.get('key'))}", ""])
            lines.append(f"- Status: `{clean(item.get('status'))}`")
            value = item.get("value")
            if isinstance(value, (dict, list)):
                lines.append("```json")
                lines.append(json.dumps(value, indent=2, sort_keys=True, default=str)[:4000])
                lines.append("```")
            else:
                lines.append(f"- Value: `{clean(value)}`")
        if structured.get("red_flags"):
            lines.extend(["", "### Red Flags", ""])
            lines.append("```json")
            lines.append(json.dumps(structured["red_flags"], indent=2, sort_keys=True, default=str)[:4000])
            lines.append("```")
    lines.extend(["", "## Next Actions", ""])
    for item in analysis["recommendations"]:
        lines.append(f"- {clean(item.get('owner'))}: {clean(item.get('action'))}")
    lines.extend(["", "## Source Samples", ""])
    for filing in context["filings"][:5]:
        lines.append(f"- Filing: {clean(filing.get('filed_at'))} · {clean(filing.get('filing_type'))} · {clean(filing.get('title'))}")
    for document in context["source_documents"][:5]:
        lines.append(
            f"- Source document: {clean(document.get('document_type'))} · {clean(document.get('document_title'))} · {clean(document.get('source_url'))}"
        )
    for extraction in context["source_extractions"][:3]:
        lines.append(
            f"- Extracted text: {clean(extraction.get('document_title'))} · {clean(extraction.get('page_count'))} pages · {clean(extraction.get('extracted_chars'))} chars · {clean(extraction.get('local_text_path'))}"
        )
        snippets = extraction.get("key_snippets") or []
        for snippet in snippets[:3]:
            lines.append(f"  - `{clean(snippet.get('term'))}`: {clean(snippet.get('snippet'))[:600]}")
    for update in context["research_updates"][:5]:
        lines.append(f"- Research update: {clean(update.get('created_at'))} · {clean(update.get('update_kind'))} · {clean(update.get('status'))} · {clean(update.get('note_path'))}")
    return "\n".join(lines) + "\n"


def insert_obsidian_note(note_path: Path, title: str, summary: str) -> None:
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO knowledge.obsidian_notes (
                vault_path, note_path, title, note_type, tags, frontmatter,
                content_hash, body_summary, last_modified_at, indexed_at
            )
            VALUES (
                {sql_literal(str(VAULT_ROOT))},
                {sql_literal(rel_path)},
                {sql_literal(title)},
                'long_term_specialist_output',
                ARRAY['ai-os','long-term','specialist-output']::text[],
                {sql_jsonb({'source': 'execute_long_term_specialist_assignment.py'})},
                md5({sql_literal(note_path.read_text())}),
                {sql_literal(summary)},
                now(),
                now()
            )
            ON CONFLICT (note_path) DO UPDATE SET
                title = EXCLUDED.title,
                note_type = EXCLUDED.note_type,
                tags = EXCLUDED.tags,
                frontmatter = EXCLUDED.frontmatter,
                content_hash = EXCLUDED.content_hash,
                body_summary = EXCLUDED.body_summary,
                last_modified_at = EXCLUDED.last_modified_at,
                indexed_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def persist_output(assignment: dict[str, Any], analysis: dict[str, Any], note_path: Path, actor: str) -> dict[str, Any]:
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    output_key = f"lt-output-{assignment['id']}-{safe_slug(assignment['module_key'])}"
    assignment_status = "needs_review"
    task_status = "blocked" if analysis["source_status"] == "source_required" else "needs_review"
    structured_score = (analysis.get("structured_checklist") or {}).get("score")
    rows = run_psql_json(
        f"""
        WITH output_upsert AS (
            INSERT INTO portfolio.long_term_specialist_outputs (
                output_key, assignment_id, holding_thesis_id, committee_review_id,
                module_key, module_name, assignment_type, agent_name, skill_key,
                output_status, source_status, findings, source_gaps, evidence,
                recommendations, metrics, confidence, note_path, generated_by, updated_at
            )
            VALUES (
                {sql_literal(output_key)},
                {int(assignment['id'])},
                {int(assignment['holding_thesis_id'])},
                {sql_literal(assignment.get('committee_review_id'))},
                {sql_literal(assignment['module_key'])},
                {sql_literal(assignment['module_name'])},
                {sql_literal(assignment['assignment_type'])},
                {sql_literal(assignment['agent_name'])},
                {sql_literal(assignment.get('skill_key'))},
                {sql_literal(analysis['output_status'])},
                {sql_literal(analysis['source_status'])},
                {sql_jsonb(analysis['findings'])},
                {sql_jsonb(analysis['source_gaps'])},
                {sql_jsonb(analysis['evidence'])},
                {sql_jsonb(analysis['recommendations'])},
                {sql_jsonb(analysis['metrics'])},
                {sql_literal(analysis['confidence'])},
                {sql_literal(rel_path)},
                {sql_literal(actor)},
                now()
            )
            ON CONFLICT (assignment_id) DO UPDATE SET
                output_status = EXCLUDED.output_status,
                source_status = EXCLUDED.source_status,
                findings = EXCLUDED.findings,
                source_gaps = EXCLUDED.source_gaps,
                evidence = EXCLUDED.evidence,
                recommendations = EXCLUDED.recommendations,
                metrics = EXCLUDED.metrics,
                confidence = EXCLUDED.confidence,
                note_path = EXCLUDED.note_path,
                generated_by = EXCLUDED.generated_by,
                updated_at = now()
            RETURNING *
        ),
        assignment_update AS (
            UPDATE portfolio.long_term_specialist_assignments
            SET status = {sql_literal(assignment_status)},
                source_status = {sql_literal(analysis['source_status'])},
                note_path = {sql_literal(rel_path)},
                updated_at = now()
            WHERE id = {int(assignment['id'])}
            RETURNING id
        ),
        task_update AS (
            UPDATE agent.tasks
            SET status = {sql_literal(task_status)},
                output_note_path = {sql_literal(rel_path)},
                evidence = {sql_jsonb(analysis['evidence'])},
                updated_at = now()
            WHERE id = {sql_literal(assignment.get('task_id'))}
            RETURNING id
        ),
        inbox_update AS (
            UPDATE agent.inbox_items
            SET status = 'needs_review',
                recommended_action = {sql_literal('Review specialist output and collect source gaps before committee action.')},
                evidence = {sql_jsonb(analysis['evidence'])},
                updated_at = now()
            WHERE id = {sql_literal(assignment.get('inbox_id'))}
            RETURNING id
        ),
        message_update AS (
            UPDATE agent.agent_messages
            SET status = 'read',
                read_at = COALESCE(read_at, now()),
                processing_status = 'processed',
                processed_at = now(),
                metadata = COALESCE(metadata, '{{}}'::jsonb) || {sql_jsonb({'specialist_output_note_path': rel_path, 'source_status': analysis['source_status']})}
            WHERE id = {sql_literal(assignment.get('message_id'))}
            RETURNING id
        ),
        audit AS (
            INSERT INTO portfolio.holding_thesis_research_updates (
                holding_thesis_id, update_kind, checklist_key, model_key, status,
                score, findings, evidence, source_summary, note_path, created_by
            )
            VALUES (
                {int(assignment['holding_thesis_id'])},
                'specialist_output',
                {sql_literal(assignment['module_key'] if assignment['module_key'] in CHECKLIST_MODULES else None)},
                {sql_literal('valuation_suite' if assignment['module_key'] == 'valuation_suite' else None)},
                {sql_literal(analysis['output_status'])},
                {sql_literal(structured_score)},
                {sql_jsonb(analysis['findings'])},
                {sql_jsonb(analysis['evidence'])},
                {sql_jsonb({'source': 'execute_long_term_specialist_assignment.py', 'source_status': analysis['source_status'], 'missing_source_count': len(analysis['source_gaps']), 'structured_checklist': analysis.get('structured_checklist')})},
                {sql_literal(rel_path)},
                {sql_literal(actor)}
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(output_upsert)), '[]'::json)::text FROM output_upsert
        """
    )
    if not rows:
        raise ValueError("specialist output was not persisted")
    return rows[0]


def update_module_rows(assignment: dict[str, Any], analysis: dict[str, Any], note_path: Path, actor: str) -> None:
    module_key = assignment["module_key"]
    thesis_id = int(assignment["holding_thesis_id"])
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    structured = analysis.get("structured_checklist")
    structured_decision = analysis.get("structured_decision")
    row_status = "source_required" if analysis["source_status"] == "source_required" else (
        structured.get("status") if structured else (structured_decision.get("status") if structured_decision else "in_progress")
    )
    row_score = structured.get("score") if structured else None
    row_findings = analysis["findings"]
    if structured:
        row_findings = [
            *analysis["findings"],
            {"structured_checklist": structured},
        ]
    if module_key in CHECKLIST_MODULES:
        run_psql_json(
            f"""
            WITH updated AS (
                UPDATE portfolio.holding_thesis_checklists
                SET status = {sql_literal(row_status)},
                    score = {sql_literal(row_score)},
                    findings = {sql_jsonb(row_findings)},
                    evidence = {sql_jsonb(analysis['evidence'])},
                    owner_agent = {sql_literal(assignment['agent_name'])},
                    updated_at = now()
                WHERE holding_thesis_id = {thesis_id}
                  AND checklist_key = {sql_literal(module_key)}
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
            """
        )
    if module_key == "valuation_suite":
        structured_decision = analysis.get("structured_decision") or {}
        valuation_outputs = {
            'specialist_output_note_path': rel_path,
            'source_status': analysis['source_status'],
            'missing_sources': analysis['source_gaps'],
            'structured_decision': structured_decision,
            'capital_action_allowed': False,
            'live_execution_allowed': False,
        }
        valuation_assumptions = structured_decision.get("assumptions") or {}
        run_psql_json(
            f"""
            WITH updated AS (
                UPDATE portfolio.holding_valuation_models
                SET status = {sql_literal(row_status)},
                    assumptions = COALESCE(assumptions, '{{}}'::jsonb) || {sql_jsonb(valuation_assumptions)},
                    outputs = COALESCE(outputs, '{{}}'::jsonb) || {sql_jsonb(valuation_outputs)},
                    note_path = {sql_literal(rel_path)},
                    owner_agent = {sql_literal(assignment['agent_name'])},
                    updated_at = now()
                WHERE holding_thesis_id = {thesis_id}
                  AND model_key = ANY (ARRAY[{','.join(sql_literal(key) for key in VALUATION_MODEL_KEYS)}]::text[])
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
            """
        )


def execute_assignment(assignment_id: int | None, assignment_key: str | None, actor: str) -> dict[str, Any]:
    assignment = fetch_assignment(assignment_id, assignment_key)
    context = fetch_context(assignment)
    analysis = build_analysis(assignment, context, actor)
    symbol = clean(assignment.get("symbol")).upper()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    note_path = OUTPUT_DIR / f"{stamp}-{safe_slug(symbol)}-{safe_slug(assignment['module_key'])}.md"
    note_path.write_text(build_note(assignment, context, analysis, actor))
    insert_obsidian_note(
        note_path,
        f"Long-Term Specialist Output - {symbol} - {assignment['module_name']}",
        f"{assignment['agent_name']} output for {symbol} {assignment['module_name']}; source status {analysis['source_status']}.",
    )
    output = persist_output(assignment, analysis, note_path, actor)
    update_module_rows(assignment, analysis, note_path, actor)
    return {
        "assignment_id": assignment["id"],
        "assignment_key": assignment["assignment_key"],
        "specialist_output_id": output["id"],
        "symbol": symbol,
        "module_key": assignment["module_key"],
        "module_name": assignment["module_name"],
        "agent_name": assignment["agent_name"],
        "output_status": analysis["output_status"],
        "source_status": analysis["source_status"],
        "missing_sources": [gap["source"] for gap in analysis["source_gaps"]],
        "note_path": str(note_path.relative_to(VAULT_ROOT)),
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one Long-Term specialist assignment.")
    parser.add_argument("--assignment-id", type=int)
    parser.add_argument("--assignment-key")
    parser.add_argument("--actor", default="Jarvis")
    args = parser.parse_args()
    try:
        result = execute_assignment(args.assignment_id, args.assignment_key, args.actor)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
