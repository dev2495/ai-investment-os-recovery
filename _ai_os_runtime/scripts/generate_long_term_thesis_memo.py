#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
MEMO_DIR = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Long-Term Theses"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def sql_text_array(values: list[str]) -> str:
    if not values:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::text[]"


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
    return slug[:80] or "long-term-thesis"


def compact_inr(value: object) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"INR {amount:,.0f}"


def fetch_symbol_context(symbol: str | None, exchange: str | None) -> dict[str, Any]:
    symbol_filter = f"AND upper(symbol) = {sql_literal(symbol.upper())}" if symbol else ""
    exchange_filter = f"AND exchange IS NOT DISTINCT FROM {sql_literal(exchange)}" if exchange else ""
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT
                upper(symbol) AS symbol,
                exchange,
                count(*) AS position_count,
                count(DISTINCT client_code) AS client_count,
                array_remove(array_agg(DISTINCT client_name ORDER BY client_name), NULL) AS clients,
                sum(coalesce(gross_exposure, 0)) AS long_term_gross_exposure,
                sum(coalesce(net_exposure, 0)) AS long_term_net_exposure,
                max(as_of) AS latest_as_of,
                jsonb_agg(
                    jsonb_build_object(
                        'book_position_id', id,
                        'client_name', client_name,
                        'client_code', client_code,
                        'account_code', account_code,
                        'symbol', symbol,
                        'exchange', exchange,
                        'quantity', quantity,
                        'market_price', market_price,
                        'market_value', market_value,
                        'gross_exposure', gross_exposure,
                        'purpose_key', purpose_key,
                        'purpose_name', purpose_name,
                        'thesis', thesis,
                        'exit_criteria', exit_criteria,
                        'as_of', as_of
                    )
                    ORDER BY gross_exposure DESC NULLS LAST
                ) AS positions
            FROM books.v_book_positions
            WHERE book_key = 'long_term'
              AND status = 'active'
              {symbol_filter}
              {exchange_filter}
            GROUP BY upper(symbol), exchange
            ORDER BY sum(coalesce(gross_exposure, 0)) DESC NULLS LAST
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError("No active long-term book exposure found for requested symbol.")
    return rows[0]


def existing_thesis(symbol: str, exchange: str | None) -> dict[str, Any] | None:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.holding_theses
            WHERE upper(symbol) = {sql_literal(symbol.upper())}
              AND exchange IS NOT DISTINCT FROM {sql_literal(exchange)}
            LIMIT 1
        ) rows
        """
    )
    return rows[0] if rows else None


def build_default_killers(symbol: str) -> list[dict[str, str]]:
    return [
        {"killer": "business_quality_deteriorates", "test": f"{symbol} loses durable economics, pricing power, or balance sheet strength."},
        {"killer": "management_capital_allocation_breaks", "test": "Capital allocation becomes value destructive or governance risk rises."},
        {"killer": "valuation_extreme_without_growth", "test": "Expected long-term return falls below hurdle after updated valuation work."},
        {"killer": "thesis_disconfirmed_by_filing_or_numbers", "test": "New filings or numbers contradict the core thesis."},
    ]


def build_memo(context: dict[str, Any], thesis: dict[str, Any], actor: str) -> str:
    symbol = clean(context.get("symbol"))
    generated_at = datetime.now(timezone.utc).isoformat()
    clients = ", ".join(context.get("clients") or []) or "n/a"
    positions = context.get("positions") or []
    lines = [
        f"# Long-Term Thesis Memo - {symbol}",
        "",
        f"Generated: {generated_at}",
        f"Generated by: {actor}",
        f"Symbol: `{symbol}`",
        f"Exchange: `{clean(context.get('exchange'))}`",
        f"Thesis id: `{thesis.get('id')}`",
        f"Thesis version: `{thesis.get('thesis_version')}`",
        "",
        "## Exposure Context",
        "",
        f"- Long-term gross exposure: {compact_inr(context.get('long_term_gross_exposure'))}",
        f"- Long-term net exposure: {compact_inr(context.get('long_term_net_exposure'))}",
        f"- Client count: {context.get('client_count')}",
        f"- Clients: {clients}",
        f"- Position count: {context.get('position_count')}",
        f"- Latest position timestamp: `{clean(context.get('latest_as_of'))}`",
        "",
        "## Initial Thesis State",
        "",
        f"- Status: `{clean(thesis.get('thesis_status'))}`",
        f"- Decision status: `{clean(thesis.get('decision_status'))}`",
        f"- Owner: {clean(thesis.get('primary_owner_agent'))}",
        f"- Purpose: `{clean(thesis.get('purpose_key'))}`",
        "",
        "This is an opening research memo built from live portfolio exposure. It is not a buy, sell, trim, add, or client-facing recommendation.",
        "",
        "## Current Holding Rows",
        "",
        "| Client | Account | Quantity | Market Value | Purpose | Current Thesis | Exit Criteria |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for position in positions:
        lines.append(
            "| "
            + " | ".join(
                [
                    clean(position.get("client_name")),
                    clean(position.get("account_code")),
                    clean(position.get("quantity"), "0"),
                    compact_inr(position.get("market_value") or position.get("gross_exposure")),
                    clean(position.get("purpose_name"), clean(position.get("purpose_key"))),
                    clean(position.get("thesis")).replace("|", "/"),
                    clean(position.get("exit_criteria")).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Required Research Blocks",
            "",
            "- Business model checklist",
            "- Industry structure checklist",
            "- Moat scorecard",
            "- Management scorecard",
            "- Governance scorecard",
            "- Capital allocation scorecard",
            "- Financial statement quality scorecard",
            "- Forensic accounting checklist",
            "- Valuation model registry: DCF, reverse DCF, sum-of-parts, peer comparison, historical valuation",
            "- Bull/base/bear scenario builder",
            "- Expected CAGR calculator",
            "- Long-term Monte Carlo module",
            "",
            "## Thesis Killers",
            "",
        ]
    )
    for item in thesis.get("thesis_killers") or []:
        lines.append(f"- `{item.get('killer')}`: {item.get('test')}")
    lines.extend(
        [
            "",
            "## Review Discipline",
            "",
            f"- Review frequency: `{clean(thesis.get('review_frequency'))}`",
            f"- Next review due: `{clean(thesis.get('next_review_due_at'))}`",
            "- Any new action must pass Portfolio Manager, Risk Office, and Charlie review.",
            "",
            "## Next Actions",
            "",
            "- Research Analyst: fill the required research blocks with source-backed evidence.",
            "- Valuation Agent: create first valuation model and expected CAGR range.",
            "- Risk Office: review concentration, liquidity, and downside against client portfolios.",
            "- Charlie Munger: challenge the thesis after evidence is complete.",
        ]
    )
    return "\n".join(lines) + "\n"


def upsert_note(note_path: str, title: str, body: str, context: dict[str, Any], thesis: dict[str, Any]) -> None:
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO knowledge.obsidian_notes (
                vault_path, note_path, title, note_type, tags, frontmatter,
                content_hash, body_summary, last_modified_at, indexed_at
            )
            VALUES (
                {sql_literal(str(VAULT_ROOT))},
                {sql_literal(note_path)},
                {sql_literal(title)},
                'long_term_thesis_memo',
                {sql_text_array(['ai-os', 'portfolio', 'long-term-thesis', clean(context.get('symbol')).lower()])},
                {sql_jsonb({'source': 'generate_long_term_thesis_memo.py', 'holding_thesis_id': thesis.get('id'), 'symbol': context.get('symbol'), 'exchange': context.get('exchange')})},
                {sql_literal(content_hash)},
                {sql_literal(f"Long-term thesis memo for {clean(context.get('symbol'))}; exposure {compact_inr(context.get('long_term_gross_exposure'))}.")},
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
                last_modified_at = now(),
                indexed_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def upsert_thesis(context: dict[str, Any], note_path: str, actor: str) -> dict[str, Any]:
    symbol = clean(context.get("symbol"))
    exchange = context.get("exchange")
    existing = existing_thesis(symbol, exchange)
    next_version = int(existing.get("thesis_version") or 1) + 1 if existing else 1
    purpose = "core_compounder"
    positions = context.get("positions") or []
    if positions:
        purpose = clean(positions[0].get("purpose_key"), "core_compounder")
    thesis_killers = build_default_killers(symbol)
    title = f"{symbol} Long-Term Thesis"
    summary = (
        f"{symbol} has active long-term exposure of {compact_inr(context.get('long_term_gross_exposure'))} "
        f"across {context.get('client_count')} client(s). Full source-backed thesis still requires research completion."
    )
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO portfolio.holding_theses (
                symbol, exchange, company_name, thesis_title, thesis_version,
                thesis_status, thesis_note_path, primary_owner_agent,
                investment_book_key, purpose_key, thesis_summary,
                thesis_killers, exit_criteria, review_frequency,
                next_review_due_at, decision_status, created_by, updated_by, updated_at
            )
            VALUES (
                {sql_literal(symbol)},
                {sql_literal(exchange)},
                {sql_literal(symbol)},
                {sql_literal(title)},
                {next_version},
                'draft',
                {sql_literal(note_path)},
                'Long-Term Portfolio Manager',
                'long_term',
                {sql_literal(purpose)},
                {sql_literal(summary)},
                {sql_jsonb(thesis_killers)},
                'Exit only after thesis killer, valuation excess, governance deterioration, or superior opportunity is reviewed.',
                'quarterly',
                now() + interval '90 days',
                'research_required',
                {sql_literal(actor)},
                {sql_literal(actor)},
                now()
            )
            ON CONFLICT (symbol, exchange) DO UPDATE SET
                thesis_title = EXCLUDED.thesis_title,
                thesis_version = portfolio.holding_theses.thesis_version + 1,
                thesis_status = 'draft',
                thesis_note_path = EXCLUDED.thesis_note_path,
                primary_owner_agent = EXCLUDED.primary_owner_agent,
                investment_book_key = EXCLUDED.investment_book_key,
                purpose_key = EXCLUDED.purpose_key,
                thesis_summary = EXCLUDED.thesis_summary,
                thesis_killers = EXCLUDED.thesis_killers,
                exit_criteria = EXCLUDED.exit_criteria,
                review_frequency = EXCLUDED.review_frequency,
                next_review_due_at = EXCLUDED.next_review_due_at,
                decision_status = EXCLUDED.decision_status,
                updated_by = EXCLUDED.updated_by,
                updated_at = now()
            RETURNING *
        ),
        versioned AS (
            INSERT INTO portfolio.holding_thesis_versions (
                holding_thesis_id, symbol, exchange, version_number, note_path,
                change_type, thesis_status, decision_status, thesis_summary,
                business_model, industry_structure, score_snapshot,
                valuation_snapshot, thesis_killers, exit_criteria, evidence, created_by
            )
            SELECT
                id, symbol, exchange, thesis_version, thesis_note_path,
                'memo_generated', thesis_status, decision_status, thesis_summary,
                business_model, industry_structure,
                jsonb_build_object(
                    'moat_score', moat_score,
                    'management_score', management_score,
                    'governance_score', governance_score,
                    'capital_allocation_score', capital_allocation_score,
                    'financial_quality_score', financial_quality_score
                ),
                jsonb_build_object(
                    'valuation_status', valuation_status,
                    'base_case_fair_value', base_case_fair_value,
                    'expected_cagr_pct', expected_cagr_pct
                ),
                thesis_killers,
                exit_criteria,
                {sql_jsonb({'source': 'books.v_book_positions', 'client_count': context.get('client_count'), 'position_count': context.get('position_count'), 'gross_exposure': context.get('long_term_gross_exposure')})},
                {sql_literal(actor)}
            FROM upserted
            ON CONFLICT (holding_thesis_id, version_number) DO NOTHING
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    if not rows:
        raise RuntimeError("holding thesis upsert returned no rows")
    thesis = rows[0]
    upsert_supporting_records(thesis, context, actor)
    return thesis


def upsert_supporting_records(thesis: dict[str, Any], context: dict[str, Any], actor: str) -> None:
    thesis_id = int(thesis["id"])
    checklists = [
        ("business_model", "Business Model Checklist", "Research Analyst"),
        ("industry_structure", "Industry Structure Checklist", "Industry Analyst"),
        ("moat_scorecard", "Moat Scorecard", "Company Analyst"),
        ("management_scorecard", "Management Scorecard", "Management Analyst"),
        ("governance_scorecard", "Governance Scorecard", "Governance Analyst"),
        ("capital_allocation", "Capital Allocation Scorecard", "Capital Allocation Analyst"),
        ("financial_quality", "Financial Statement Quality Scorecard", "Financial Statement Analyst"),
        ("forensic_accounting", "Forensic Accounting Checklist", "Forensic Accounting Agent"),
    ]
    values = ",\n".join(
        f"({thesis_id}, {sql_literal(key)}, {sql_literal(name)}, 'not_started', {sql_literal(owner)}, {sql_jsonb([{'source': 'generated_thesis_memo', 'symbol': thesis.get('symbol')}])})"
        for key, name, owner in checklists
    )
    valuation_values = ",\n".join(
        f"({thesis_id}, {sql_literal(key)}, {sql_literal(name)}, {sql_literal(model_type)}, 'not_started', {sql_literal(owner)})"
        for key, name, model_type, owner in [
            ("dcf", "DCF Module", "dcf", "Valuation Agent"),
            ("reverse_dcf", "Reverse DCF Module", "reverse_dcf", "Valuation Agent"),
            ("sum_of_parts", "Sum Of Parts Module", "sotp", "Valuation Agent"),
            ("peer_comparison", "Peer Comparison Module", "relative_valuation", "Valuation Agent"),
            ("historical_valuation", "Historical Valuation Module", "historical_multiple", "Valuation Agent"),
            ("scenario_builder", "Bull Base Bear Scenario Builder", "scenario", "Valuation Agent"),
            ("expected_cagr", "Expected CAGR Calculator", "return_model", "Valuation Agent"),
            ("long_term_monte_carlo", "Long-Term Monte Carlo Module", "monte_carlo", "Quant Risk Analyst"),
        ]
    )
    run_psql_json(
        f"""
        WITH checklist_upsert AS (
            INSERT INTO portfolio.holding_thesis_checklists (
                holding_thesis_id, checklist_key, checklist_name, status, owner_agent, evidence
            )
            VALUES {values}
            ON CONFLICT (holding_thesis_id, checklist_key) DO UPDATE SET
                checklist_name = EXCLUDED.checklist_name,
                owner_agent = EXCLUDED.owner_agent,
                updated_at = now()
            RETURNING id
        ),
        valuation_upsert AS (
            INSERT INTO portfolio.holding_valuation_models (
                holding_thesis_id, model_key, model_name, model_type, status, owner_agent
            )
            VALUES {valuation_values}
            ON CONFLICT (holding_thesis_id, model_key) DO UPDATE SET
                model_name = EXCLUDED.model_name,
                model_type = EXCLUDED.model_type,
                owner_agent = EXCLUDED.owner_agent,
                updated_at = now()
            RETURNING id
        ),
        review AS (
            INSERT INTO portfolio.holding_review_schedule (
                holding_thesis_id, review_type, due_at, status, owner_agent, evidence
            )
            VALUES (
                {thesis_id},
                'quarterly_review',
                now() + interval '90 days',
                'scheduled',
                'Long-Term Portfolio Manager',
                {sql_jsonb({'source': 'generate_long_term_thesis_memo.py', 'symbol': context.get('symbol')})}
            )
            RETURNING id
        ),
        task AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                {sql_literal('Complete long-term thesis research: ' + clean(context.get('symbol')))},
                {sql_literal('Fill business quality, management, governance, valuation, thesis killers, and review schedule for the long-term holding thesis.')},
                'Research Analyst',
                'queued',
                'medium',
                false,
                'holding_thesis',
                {sql_literal(str(thesis_id))},
                'obsidian_note',
                {sql_jsonb([{'table': 'portfolio.holding_theses', 'id': thesis_id}, {'view': 'portfolio.v_long_term_thesis_control', 'symbol': context.get('symbol')}])}
            )
            RETURNING id
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            SELECT
                task.id,
                {sql_literal('Research queue: ' + clean(context.get('symbol')) + ' long-term thesis')},
                'Research Analyst',
                'queued',
                'medium',
                'Complete the long-term thesis scorecards and valuation modules with source-backed evidence before any portfolio action.',
                {sql_jsonb([{'table': 'portfolio.holding_theses', 'id': thesis_id}])},
                'research'
            FROM task
            RETURNING id
        )
        SELECT json_build_object(
            'checklists', (SELECT count(*) FROM checklist_upsert),
            'valuations', (SELECT count(*) FROM valuation_upsert),
            'review_id', (SELECT id FROM review),
            'task_id', (SELECT id FROM task),
            'inbox_id', (SELECT id FROM inbox)
        )::text
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or refresh a long-term holding thesis memo from real book exposure.")
    parser.add_argument("--symbol", help="Optional symbol. Defaults to highest gross long-term exposure without a completed thesis.")
    parser.add_argument("--exchange")
    parser.add_argument("--actor", default="Long-Term Portfolio Manager")
    args = parser.parse_args()

    context = fetch_symbol_context(args.symbol, args.exchange)
    symbol = clean(context.get("symbol"))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    note_rel = Path("ai memory") / "02 Portfolio" / "Long-Term Theses" / f"{ts}-{safe_slug(symbol)}-long-term-thesis.md"
    note_abs = VAULT_ROOT / note_rel
    note_abs.parent.mkdir(parents=True, exist_ok=True)
    thesis_stub = {
        "id": "pending",
        "thesis_version": "pending",
        "thesis_status": "draft",
        "decision_status": "research_required",
        "primary_owner_agent": "Long-Term Portfolio Manager",
        "purpose_key": "core_compounder",
        "thesis_killers": build_default_killers(symbol),
        "review_frequency": "quarterly",
        "next_review_due_at": "pending",
    }
    thesis = upsert_thesis(context, str(note_rel), args.actor)
    memo = build_memo(context, {**thesis_stub, **thesis}, args.actor)
    note_abs.write_text(memo, encoding="utf-8")
    title = f"{symbol} Long-Term Thesis"
    upsert_note(str(note_rel), title, memo, context, thesis)
    result = {
        "status": "ok",
        "holding_thesis_id": thesis["id"],
        "symbol": symbol,
        "exchange": context.get("exchange"),
        "note_path": str(note_rel),
        "thesis_version": thesis.get("thesis_version"),
        "long_term_gross_exposure": context.get("long_term_gross_exposure"),
        "client_count": context.get("client_count"),
        "position_count": context.get("position_count"),
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": type(exc).__name__ + ": " + str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
