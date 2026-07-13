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
REQUEST_DIR = VAULT_ROOT / "ai memory" / "05 Filings and Transcripts" / "Long-Term Source Requests"
OWNER_AGENT = "Filings and Transcript Analyst"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def sql_int(value: object) -> str:
    if value in (None, ""):
        return "NULL"
    return str(int(value))


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
    return slug[:90] or "source-request"


def source_category(source_name: str) -> str:
    text = source_name.lower()
    if "transcript" in text:
        return "transcript"
    if "presentation" in text:
        return "investor_presentation"
    if "price" in text or "quote" in text:
        return "market_data"
    if "book" in text or "client" in text or "portfolio" in text or "risk_limit" in text:
        return "portfolio_data"
    if "financial" in text or "cash_flow" in text or "balance_sheet" in text or "annual" in text or "audited" in text:
        return "financial_filing"
    return "filing"


def collection_plan(symbol: str, exchange: str, source_name: str) -> dict[str, Any]:
    category = source_category(source_name)
    source_lower = source_name.lower()
    official_targets = []
    if exchange.upper() == "NSE":
        official_targets.append("NSE corporate announcements")
    if exchange.upper() == "BSE":
        official_targets.append("BSE corporate announcements")
    official_targets.extend(["company investor relations", "annual report / financial results", "PDF extraction pipeline"])
    plan = {
        "symbol": symbol,
        "exchange": exchange,
        "source_name": source_name,
        "source_category": category,
        "official_sources_first": official_targets,
        "collector_commands": [
            "python3 _ai_os_runtime/scripts/collect_nse_bse_filings.py --source all --from-date YYYY-MM-DD --to-date YYYY-MM-DD --limit 100 --actor 'Filings and Transcript Analyst'",
            "python3 _ai_os_runtime/scripts/extract_filing_pdfs.py --limit 25 --actor 'Filings and Transcript Analyst'",
        ],
        "manual_browser_hint": f"Search official exchange/company IR pages for {symbol} {source_name}; store source_url, attachment_url, filed_at, and local_path.",
        "completion_rule": "Request is satisfied only when the source is present in research.corporate_filings, core.raw_artifacts, or a linked Obsidian source note with URL provenance.",
    }
    if "annual" in source_lower or "audited" in source_lower or "financial" in source_lower:
        plan["required_document_types"] = ["annual_report", "audited_financial_statement", "results_pdf"]
    if "presentation" in source_lower:
        plan["required_document_types"] = ["investor_presentation", "earnings_presentation"]
    if "transcript" in source_lower:
        plan["required_document_types"] = ["earnings_call_transcript", "conference_call_transcript"]
    return plan


def fetch_outputs(output_id: int | None, assignment_id: int | None, holding_thesis_id: int | None, limit: int) -> list[dict[str, Any]]:
    where = ["jsonb_array_length(source_gaps) > 0"]
    if output_id:
        where.append(f"id = {int(output_id)}")
    if assignment_id:
        where.append(f"assignment_id = {int(assignment_id)}")
    if holding_thesis_id:
        where.append(f"holding_thesis_id = {int(holding_thesis_id)}")
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_specialist_outputs
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC
            LIMIT {max(1, int(limit))}
        ) rows
        """
    )
    return rows


def build_note(requests: list[dict[str, Any]], actor: str) -> str:
    symbols = sorted({clean(row.get("symbol")).upper() for row in requests})
    lines = [
        "# Long-Term Source Request Batch",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Generated by: {actor}",
        f"Symbols: `{', '.join(symbols) if symbols else 'n/a'}`",
        "",
        "## Guardrail",
        "",
        "These requests collect source evidence only. They do not authorize buy, sell, trim, add, hedge, broker order, or live strategy action.",
        "",
        "## Requests",
        "",
    ]
    for row in requests:
        lines.append(
            f"- `{row['request_key']}`: {row['symbol']} · {row['source_name']} · "
            f"{row['required_for_module']} · status `{row['status']}` · task `{row.get('task_id')}`"
        )
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
                'long_term_source_request_batch',
                ARRAY['ai-os','long-term','source-request']::text[],
                {sql_jsonb({'source': 'create_long_term_source_requests.py'})},
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


def create_request(output: dict[str, Any], gap: dict[str, Any], actor: str) -> dict[str, Any] | None:
    source_name = clean(gap.get("source") or gap.get("source_name"), "")
    if not source_name:
        return None
    symbol = clean(output.get("symbol")).upper()
    exchange = clean(output.get("exchange"), "NSE")
    module_key = clean(output.get("module_key"))
    request_key = f"lt-src-{output['holding_thesis_id']}-{safe_slug(module_key)}-{safe_slug(source_name)}"
    plan = collection_plan(symbol, exchange, source_name)
    evidence = [
        {"table": "portfolio.long_term_specialist_outputs", "id": output.get("id")},
        {"table": "portfolio.long_term_specialist_assignments", "id": output.get("assignment_id")},
        {"table": "portfolio.holding_theses", "id": output.get("holding_thesis_id")},
        {"missing_source": source_name},
        {"capital_action_allowed": False},
        {"live_execution_allowed": False},
    ]
    reason = f"{source_name} is required before {output['agent_name']} can complete {output['module_name']} for {symbol}."
    request_rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO portfolio.long_term_source_requests (
                    request_key, holding_thesis_id, specialist_output_id, assignment_id,
                    committee_review_id, symbol, exchange, company_name,
                    source_name, source_category, priority, status, owner_agent,
                    required_for_module, required_by_agent, request_reason,
                    collection_plan, evidence, created_by, updated_at
                )
                VALUES (
                    {sql_literal(request_key)},
                    {int(output['holding_thesis_id'])},
                    {int(output['id'])},
                    {int(output['assignment_id'])},
                    {sql_literal(output.get('committee_review_id'))},
                    {sql_literal(symbol)},
                    {sql_literal(exchange)},
                    {sql_literal(output.get('company_name'))},
                    {sql_literal(source_name)},
                    {sql_literal(plan['source_category'])},
                    'high',
                    'queued',
                    {sql_literal(OWNER_AGENT)},
                    {sql_literal(module_key)},
                    {sql_literal(output.get('agent_name'))},
                    {sql_literal(reason)},
                    {sql_jsonb(plan)},
                    {sql_jsonb(evidence)},
                    {sql_literal(actor)},
                    now()
                )
                ON CONFLICT (holding_thesis_id, source_name, required_for_module) DO UPDATE SET
                    specialist_output_id = EXCLUDED.specialist_output_id,
                    assignment_id = EXCLUDED.assignment_id,
                    committee_review_id = EXCLUDED.committee_review_id,
                    priority = EXCLUDED.priority,
                    status = CASE
                        WHEN portfolio.long_term_source_requests.status = 'satisfied' THEN 'satisfied'
                        ELSE 'queued'
                    END,
                    request_reason = EXCLUDED.request_reason,
                    collection_plan = EXCLUDED.collection_plan,
                    evidence = EXCLUDED.evidence,
                    updated_at = now()
                RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    if not request_rows:
        return None
    request = request_rows[0]
    task_rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                {sql_literal(f'{symbol}: collect {source_name} for {module_key}')},
                {sql_literal(reason + ' Use official exchange/company sources first and preserve provenance.')},
                {sql_literal(OWNER_AGENT)},
                'queued',
                'high',
                false,
                'portfolio.long_term_source_requests',
                {sql_literal(request_key)},
                'source_request',
                {sql_jsonb(evidence)}
            )
            ON CONFLICT (title, owner_agent, source_kind, source_ref)
            WHERE status = ANY (ARRAY['queued'::text, 'in_progress'::text, 'blocked'::text])
              AND source_kind IS NOT NULL
              AND source_ref IS NOT NULL
            DO UPDATE SET
                objective = EXCLUDED.objective,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    task_id = task_rows[0]["id"] if task_rows else None
    inbox_rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            SELECT
                {sql_int(task_id)},
                {sql_literal(f'{symbol}: source needed - {source_name}')},
                {sql_literal(OWNER_AGENT)},
                'new',
                'high',
                {sql_literal('Collect the required source, store URL/document provenance, then rerun the blocked specialist module.')},
                {sql_jsonb(evidence)},
                'Filings and Transcripts'
            WHERE NOT EXISTS (
                SELECT 1
                FROM agent.inbox_items inbox
                WHERE inbox.task_id = {sql_int(task_id)}
                  AND inbox.status IN ('new','queued','open','needs_review')
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    inbox_id = inbox_rows[0]["id"] if inbox_rows else request.get("inbox_id")
    if inbox_id is None and task_id is not None:
        existing_inbox_rows = run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT id
                FROM agent.inbox_items
                WHERE task_id = {sql_int(task_id)}
                  AND owner_agent = {sql_literal(OWNER_AGENT)}
                ORDER BY id DESC
                LIMIT 1
            ) rows
            """
        )
        inbox_id = existing_inbox_rows[0]["id"] if existing_inbox_rows else None
    linked_rows = run_psql_json(
        f"""
        WITH rows AS (
            UPDATE portfolio.long_term_source_requests
            SET task_id = COALESCE({sql_int(task_id)}, task_id),
                inbox_id = COALESCE({sql_int(inbox_id)}, inbox_id),
                updated_at = now()
            WHERE id = {int(request['id'])}
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    return linked_rows[0] if linked_rows else request


def create_requests(args: argparse.Namespace) -> dict[str, Any]:
    outputs = fetch_outputs(args.specialist_output_id, args.assignment_id, args.holding_thesis_id, args.limit)
    created: list[dict[str, Any]] = []
    for output in outputs:
        for gap in output.get("source_gaps") or []:
            request = create_request(output, gap if isinstance(gap, dict) else {"source": gap}, args.actor)
            if request:
                created.append(request)
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = safe_slug("-".join(sorted({clean(row.get("symbol")).upper() for row in created})) or "source-requests")
    note_path = REQUEST_DIR / f"{stamp}-{suffix}.md"
    note_path.write_text(build_note(created, args.actor))
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    insert_obsidian_note(note_path, "Long-Term Source Request Batch", f"Created or refreshed {len(created)} long-term source requests.")
    if created:
        keys = ",".join(sql_literal(row["request_key"]) for row in created)
        run_psql_json(
            f"""
            WITH updated AS (
                UPDATE portfolio.long_term_source_requests
                SET note_path = {sql_literal(rel_path)}, updated_at = now()
                WHERE request_key IN ({keys})
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
            """
        )
    return {
        "source_request_count": len(created),
        "specialist_output_count": len(outputs),
        "note_path": rel_path,
        "requests": [
            {
                "id": row["id"],
                "request_key": row["request_key"],
                "symbol": row["symbol"],
                "source_name": row["source_name"],
                "status": row["status"],
                "task_id": row.get("task_id"),
                "inbox_id": row.get("inbox_id"),
            }
            for row in created
        ],
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Long-Term source requests from specialist output gaps.")
    parser.add_argument("--specialist-output-id", type=int)
    parser.add_argument("--assignment-id", type=int)
    parser.add_argument("--holding-thesis-id", type=int)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--actor", default="Jarvis")
    args = parser.parse_args()
    try:
        result = create_requests(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
