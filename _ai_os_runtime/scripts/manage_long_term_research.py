#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = RUNTIME_ROOT.parent
PACKET_DIR = VAULT_ROOT / "ai memory" / "02 Portfolio" / "Long-Term Research Packets"


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
    return slug[:90] or "long-term-research"


def compact_inr(value: object) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"INR {amount:,.0f}"


def parse_json_arg(raw: str | None, fallback: object) -> object:
    if raw is None or raw == "":
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON argument: {raw}") from exc


def fetch_thesis(holding_thesis_id: int | None, symbol: str | None, exchange: str | None) -> dict[str, Any]:
    if holding_thesis_id:
        where = f"id = {int(holding_thesis_id)}"
    elif symbol:
        exchange_filter = f"AND exchange IS NOT DISTINCT FROM {sql_literal(exchange)}" if exchange else ""
        where = f"upper(symbol) = {sql_literal(symbol.upper())} {exchange_filter}"
    else:
        raise ValueError("holding_thesis_id or symbol is required")
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_thesis_control
            WHERE {where}
            ORDER BY long_term_gross_exposure DESC NULLS LAST
            LIMIT 1
        ) rows
        """
    )
    if not rows or rows[0].get("id") is None:
        raise ValueError("No existing long-term thesis found. Generate a thesis memo first.")
    return rows[0]


def fetch_packet_sources(thesis: dict[str, Any]) -> dict[str, Any]:
    symbol = clean(thesis.get("symbol")).upper()
    exchange = thesis.get("exchange")
    exposure = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, client_code, client_name, account_code, broker, symbol, exchange,
                   book_key, purpose_key, purpose_name, direction, quantity, average_price,
                   market_price, market_value, gross_exposure, net_exposure, thesis,
                   exit_criteria, evidence, as_of, updated_at
            FROM books.v_book_positions
            WHERE book_key = 'long_term'
              AND status = 'active'
              AND upper(symbol) = {sql_literal(symbol)}
              AND exchange IS NOT DISTINCT FROM {sql_literal(exchange)}
            ORDER BY gross_exposure DESC NULLS LAST
            LIMIT 50
        ) rows
        """
    )
    quotes = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT source_key, provider, provider_symbol, symbol, exchange, price,
                   change_percent, quote_ts, created_at
            FROM market.v_latest_price_quotes
            WHERE upper(symbol) = {sql_literal(symbol)}
              AND exchange IS NOT DISTINCT FROM {sql_literal(exchange)}
            ORDER BY quote_ts DESC NULLS LAST, created_at DESC
            LIMIT 5
        ) rows
        """
    )
    filings = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, source_name, exchange, symbol, company_name, filing_type,
                   event_type, title, filed_at, source_url, attachment_url,
                   extraction_status, pdf_extracted_at,
                   CASE
                       WHEN extracted_text IS NULL THEN NULL
                       ELSE left(regexp_replace(extracted_text, '\\s+', ' ', 'g'), 700)
                   END AS text_excerpt
            FROM research.corporate_filings
            WHERE upper(coalesce(symbol, '')) = {sql_literal(symbol)}
               OR upper(coalesce(company_name, '')) LIKE {sql_literal('%' + symbol + '%')}
            ORDER BY filed_at DESC NULLS LAST, created_at DESC
            LIMIT 12
        ) rows
        """
    )
    notes = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT note_path, title, note_type, tags, body_summary, last_modified_at, indexed_at
            FROM knowledge.obsidian_notes
            WHERE upper(title) LIKE {sql_literal('%' + symbol + '%')}
               OR upper(note_path) LIKE {sql_literal('%' + symbol + '%')}
            ORDER BY indexed_at DESC
            LIMIT 12
        ) rows
        """
    )
    return {"positions": exposure, "quotes": quotes, "filings": filings, "notes": notes}


def build_packet_markdown(thesis: dict[str, Any], sources: dict[str, Any], actor: str) -> str:
    symbol = clean(thesis.get("symbol")).upper()
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Long-Term Research Packet - {symbol}",
        "",
        f"Generated: {generated_at}",
        f"Generated by: {actor}",
        f"Thesis id: `{thesis.get('id')}`",
        f"Exchange: `{clean(thesis.get('exchange'))}`",
        f"Current thesis status: `{clean(thesis.get('thesis_status'))}`",
        f"Decision status: `{clean(thesis.get('decision_status'))}`",
        "",
        "## Exposure",
        "",
        f"- Long-term gross exposure: {compact_inr(thesis.get('long_term_gross_exposure'))}",
        f"- Long-term net exposure: {compact_inr(thesis.get('long_term_net_exposure'))}",
        f"- Clients: {', '.join(thesis.get('clients') or []) or 'n/a'}",
        f"- Position count: {thesis.get('position_count')}",
        "",
        "### Position Rows",
        "",
    ]
    for row in sources["positions"][:12]:
        lines.append(
            f"- {clean(row.get('client_name'))} / {clean(row.get('account_code'))}: "
            f"qty `{clean(row.get('quantity'))}`, value {compact_inr(row.get('market_value'))}, "
            f"purpose `{clean(row.get('purpose_key'))}`, as of `{clean(row.get('as_of'))}`"
        )
    if not sources["positions"]:
        lines.append("- No active long-term position rows found for this thesis.")
    lines.extend(["", "## Latest Quotes", ""])
    for row in sources["quotes"]:
        lines.append(
            f"- {clean(row.get('provider'))} `{clean(row.get('provider_symbol'))}`: "
            f"{clean(row.get('price'))} {clean(row.get('source_key'))}, quote `{clean(row.get('quote_ts'))}`"
        )
    if not sources["quotes"]:
        lines.append("- No latest quote row found. Valuation work must source a current price before completion.")
    lines.extend(["", "## Recent Filings", ""])
    for row in sources["filings"]:
        lines.append(
            f"- `{row.get('id')}` {clean(row.get('filed_at'))}: {clean(row.get('title'))} "
            f"({clean(row.get('source_name'))}, {clean(row.get('event_type'))}, {clean(row.get('extraction_status'))})"
        )
        if row.get("text_excerpt"):
            lines.append(f"  - Excerpt: {clean(row.get('text_excerpt'))}")
    if not sources["filings"]:
        lines.append("- No company-specific filing rows found yet. Filings Analyst must collect/attach source filings before final thesis completion.")
    lines.extend(["", "## Existing Obsidian Notes", ""])
    for row in sources["notes"]:
        lines.append(f"- [[{clean(row.get('note_path'))}]] - {clean(row.get('title'))} ({clean(row.get('note_type'))})")
    if not sources["notes"]:
        lines.append("- No indexed Obsidian note match found beyond this packet.")
    lines.extend(
        [
            "",
            "## Required Follow-Ups",
            "",
            "- Company Analyst: fill business model and segment economics with cited sources.",
            "- Industry Analyst: fill industry structure and competitive intensity.",
            "- Management Analyst: fill promoter/governance/capital allocation evidence.",
            "- Financial Statement Analyst: attach revenue, margin, cash conversion, debt, working capital, and accounting-quality checks.",
            "- Forensic Accounting Agent: review related-party, receivables, inventory, auditor, pledge, and cash-flow flags.",
            "- Valuation Agent: create valuation model only after source financials and current price are attached.",
            "- Bear Case Agent: write disconfirming evidence and thesis-killer tests.",
            "- Risk Agent: review concentration, liquidity, client suitability, and cross-book conflicts.",
            "",
            "## Decision Guardrail",
            "",
            "This packet is evidence assembly only. It does not approve buy, add, trim, sell, hedge, or live-trading action.",
        ]
    )
    return "\n".join(lines) + "\n"


def insert_obsidian_note(note_path: Path, title: str, note_type: str, tags: list[str], summary: str) -> None:
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
                {sql_literal(note_type)},
                ARRAY[{','.join(sql_literal(tag) for tag in tags)}]::text[],
                {sql_jsonb({'source': 'manage_long_term_research.py'})},
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


def create_agent_followups(thesis: dict[str, Any], actor: str, note_path: str, sources: dict[str, Any]) -> None:
    symbol = clean(thesis.get("symbol")).upper()
    evidence = [
        {"table": "portfolio.holding_theses", "id": thesis.get("id")},
        {"note_path": note_path},
        {"positions": len(sources["positions"]), "quotes": len(sources["quotes"]), "filings": len(sources["filings"]), "notes": len(sources["notes"])},
    ]
    run_psql_json(
        f"""
        WITH task_insert AS (
            INSERT INTO agent.tasks (
                title, objective, status, priority, owner_agent, source_kind,
                source_ref, output_format, output_note_path, evidence
            )
            VALUES (
                {sql_literal(f'Complete source-backed long-term research checks for {symbol}')},
                {sql_literal('Use the research packet to fill checklist rows, valuation modules, bear case, and risk review. Do not mark complete without cited sources.')},
                'queued',
                'high',
                'Long-Term Portfolio Manager',
                'holding_thesis_research_packet',
                {sql_literal(str(thesis['id']))},
                'long_term_research_packet',
                {sql_literal(note_path)},
                {sql_jsonb(evidence)}
            )
            ON CONFLICT (title, owner_agent, source_kind, source_ref)
            WHERE status = ANY (ARRAY['queued'::text, 'in_progress'::text, 'blocked'::text])
              AND source_kind IS NOT NULL
              AND source_ref IS NOT NULL
            DO UPDATE SET
                objective = EXCLUDED.objective,
                output_note_path = EXCLUDED.output_note_path,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING id
        ),
        inbox_insert AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action,
                target_workspace, evidence, task_id
            )
            VALUES (
                {sql_literal(f'{symbol} long-term research packet ready')},
                'Charlie Munger',
                'new',
                'high',
                {sql_literal('Route Company Analyst, Valuation Agent, Bear Case Agent, and Risk Agent to complete sourced long-term thesis work.')},
                'Long-Term Office',
                {sql_jsonb(evidence)},
                (SELECT id FROM task_insert)
            )
            RETURNING id
        )
        SELECT json_build_array(json_build_object('task_id', (SELECT id FROM task_insert), 'inbox_id', (SELECT id FROM inbox_insert)))::text
        """
    )


def action_packet(args: argparse.Namespace) -> dict[str, Any]:
    thesis = fetch_thesis(args.holding_thesis_id, args.symbol, args.exchange)
    sources = fetch_packet_sources(thesis)
    symbol = clean(thesis.get("symbol")).upper()
    generated_at = datetime.now(timezone.utc)
    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    note_path = PACKET_DIR / f"{generated_at.strftime('%Y%m%dT%H%M%SZ')}-{safe_slug(symbol)}-research-packet.md"
    note_body = build_packet_markdown(thesis, sources, args.actor)
    note_path.write_text(note_body)
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    source_summary = {
        "positions": len(sources["positions"]),
        "quotes": len(sources["quotes"]),
        "filings": len(sources["filings"]),
        "notes": len(sources["notes"]),
        "symbol": symbol,
        "exchange": thesis.get("exchange"),
    }
    evidence = [
        {"table": "portfolio.v_long_term_thesis_control", "id": thesis.get("id")},
        {"table": "books.v_book_positions", "rows": len(sources["positions"])},
        {"table": "market.v_latest_price_quotes", "rows": len(sources["quotes"])},
        {"table": "research.corporate_filings", "rows": len(sources["filings"])},
        {"table": "knowledge.obsidian_notes", "rows": len(sources["notes"])},
    ]
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO portfolio.holding_thesis_research_updates (
                holding_thesis_id, update_kind, status, findings, evidence,
                source_summary, note_path, created_by
            )
            VALUES (
                {int(thesis['id'])},
                'research_packet',
                'evidence_packet_created',
                {sql_jsonb([{'finding': 'Research packet created from live warehouse evidence. Checklist and valuation rows remain incomplete until specialist review.'}])},
                {sql_jsonb(evidence)},
                {sql_jsonb(source_summary)},
                {sql_literal(rel_path)},
                {sql_literal(args.actor)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    insert_obsidian_note(
        note_path,
        f"Long-Term Research Packet - {symbol}",
        "long_term_research_packet",
        ["ai-os", "long-term", "research-packet", symbol.lower()],
        f"Source-backed research packet for {symbol}; positions {source_summary['positions']}, quotes {source_summary['quotes']}, filings {source_summary['filings']}.",
    )
    create_agent_followups(thesis, args.actor, rel_path, sources)
    return {"action": "packet", "research_update_id": rows[0]["id"], "holding_thesis_id": thesis["id"], "symbol": symbol, "note_path": rel_path, "source_summary": source_summary}


def action_checklist(args: argparse.Namespace) -> dict[str, Any]:
    if not args.holding_thesis_id or not args.checklist_key:
        raise ValueError("holding_thesis_id and checklist_key are required for checklist updates")
    findings = parse_json_arg(args.findings_json, [])
    evidence = parse_json_arg(args.evidence_json, [])
    rows = run_psql_json(
        f"""
        WITH updated AS (
            UPDATE portfolio.holding_thesis_checklists
            SET status = {sql_literal(args.status)},
                score = {sql_literal(args.score)},
                findings = {sql_jsonb(findings)},
                evidence = {sql_jsonb(evidence)},
                owner_agent = {sql_literal(args.actor)},
                updated_at = now()
            WHERE holding_thesis_id = {int(args.holding_thesis_id)}
              AND checklist_key = {sql_literal(args.checklist_key)}
            RETURNING *
        ),
        audit AS (
            INSERT INTO portfolio.holding_thesis_research_updates (
                holding_thesis_id, update_kind, checklist_key, status, score,
                findings, evidence, source_summary, created_by
            )
            SELECT
                holding_thesis_id,
                'checklist_update',
                checklist_key,
                status,
                score,
                findings,
                evidence,
                {sql_jsonb({'source': 'manage_long_term_research.py', 'mode': 'checklist'})},
                {sql_literal(args.actor)}
            FROM updated
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(audit)), '[]'::json)::text FROM audit
        """
    )
    if not rows:
        raise ValueError("No checklist row updated. Check holding_thesis_id and checklist_key.")
    return {"action": "checklist", "research_update_id": rows[0]["id"], "holding_thesis_id": args.holding_thesis_id, "checklist_key": args.checklist_key, "status": args.status}


def action_valuation(args: argparse.Namespace) -> dict[str, Any]:
    if not args.holding_thesis_id or not args.model_key:
        raise ValueError("holding_thesis_id and model_key are required for valuation updates")
    assumptions = parse_json_arg(args.assumptions_json, {})
    outputs = parse_json_arg(args.outputs_json, {})
    evidence = parse_json_arg(args.evidence_json, [])
    rows = run_psql_json(
        f"""
        WITH updated AS (
            UPDATE portfolio.holding_valuation_models
            SET status = {sql_literal(args.status)},
                fair_value_low = {sql_literal(args.fair_value_low)},
                fair_value_base = {sql_literal(args.fair_value_base)},
                fair_value_high = {sql_literal(args.fair_value_high)},
                expected_cagr_pct = {sql_literal(args.expected_cagr_pct)},
                assumptions = {sql_jsonb(assumptions)},
                outputs = {sql_jsonb(outputs)},
                note_path = COALESCE({sql_literal(args.note_path)}, note_path),
                owner_agent = {sql_literal(args.actor)},
                updated_at = now()
            WHERE holding_thesis_id = {int(args.holding_thesis_id)}
              AND model_key = {sql_literal(args.model_key)}
            RETURNING *
        ),
        thesis_update AS (
            UPDATE portfolio.holding_theses ht
            SET valuation_status = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM portfolio.holding_valuation_models vm
                        WHERE vm.holding_thesis_id = ht.id
                          AND vm.status IN ('in_progress','source_required','complete','reviewed')
                    )
                    THEN 'in_progress'
                    ELSE ht.valuation_status
                END,
                base_case_fair_value = COALESCE((SELECT fair_value_base FROM updated), ht.base_case_fair_value),
                bear_case_fair_value = COALESCE((SELECT fair_value_low FROM updated), ht.bear_case_fair_value),
                bull_case_fair_value = COALESCE((SELECT fair_value_high FROM updated), ht.bull_case_fair_value),
                expected_cagr_pct = COALESCE((SELECT expected_cagr_pct FROM updated), ht.expected_cagr_pct),
                updated_by = {sql_literal(args.actor)},
                updated_at = now()
            WHERE ht.id = {int(args.holding_thesis_id)}
            RETURNING ht.id
        ),
        audit AS (
            INSERT INTO portfolio.holding_thesis_research_updates (
                holding_thesis_id, update_kind, model_key, status,
                fair_value_low, fair_value_base, fair_value_high, expected_cagr_pct,
                assumptions, outputs, evidence, note_path, source_summary, created_by
            )
            SELECT
                holding_thesis_id,
                'valuation_update',
                model_key,
                status,
                fair_value_low,
                fair_value_base,
                fair_value_high,
                expected_cagr_pct,
                assumptions,
                outputs,
                {sql_jsonb(evidence)},
                note_path,
                {sql_jsonb({'source': 'manage_long_term_research.py', 'mode': 'valuation'})},
                {sql_literal(args.actor)}
            FROM updated
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(audit)), '[]'::json)::text FROM audit
        """
    )
    if not rows:
        raise ValueError("No valuation row updated. Check holding_thesis_id and model_key.")
    return {"action": "valuation", "research_update_id": rows[0]["id"], "holding_thesis_id": args.holding_thesis_id, "model_key": args.model_key, "status": args.status}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage source-backed long-term research workflows.")
    sub = parser.add_subparsers(dest="action", required=True)
    packet = sub.add_parser("packet")
    packet.add_argument("--holding-thesis-id", type=int)
    packet.add_argument("--symbol")
    packet.add_argument("--exchange")
    packet.add_argument("--actor", default="Long-Term Portfolio Manager")
    checklist = sub.add_parser("checklist")
    checklist.add_argument("--holding-thesis-id", type=int, required=True)
    checklist.add_argument("--checklist-key", required=True)
    checklist.add_argument("--status", default="in_progress")
    checklist.add_argument("--score")
    checklist.add_argument("--findings-json")
    checklist.add_argument("--evidence-json")
    checklist.add_argument("--actor", default="Research Analyst")
    valuation = sub.add_parser("valuation")
    valuation.add_argument("--holding-thesis-id", type=int, required=True)
    valuation.add_argument("--model-key", required=True)
    valuation.add_argument("--status", default="in_progress")
    valuation.add_argument("--fair-value-low")
    valuation.add_argument("--fair-value-base")
    valuation.add_argument("--fair-value-high")
    valuation.add_argument("--expected-cagr-pct")
    valuation.add_argument("--assumptions-json")
    valuation.add_argument("--outputs-json")
    valuation.add_argument("--evidence-json")
    valuation.add_argument("--note-path")
    valuation.add_argument("--actor", default="Valuation Agent")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "packet":
            result = action_packet(args)
        elif args.action == "checklist":
            result = action_checklist(args)
        elif args.action == "valuation":
            result = action_valuation(args)
        else:
            raise ValueError(f"Unsupported action {args.action}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
