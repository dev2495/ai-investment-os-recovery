#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = RUNTIME_ROOT.parent
MEMO_DIR = VAULT_ROOT / "ai memory" / "05 Filings and Transcripts" / "Special Situations"


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
    return slug[:80] or "special-situation"


def fetch_terms(special_terms_id: int) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM research.v_special_situation_terms
            WHERE id = {special_terms_id}
        ) rows
        """
    )
    if not rows:
        raise ValueError(f"special situation terms {special_terms_id} not found")
    return rows[0]


def fetch_existing_memo(special_terms_id: int) -> dict[str, Any] | None:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, note_path, task_id, approval_id
            FROM research.special_situation_memos
            WHERE special_terms_id = {special_terms_id}
            LIMIT 1
        ) rows
        """
    )
    return rows[0] if rows else None


def build_terms_payload(row: dict[str, Any]) -> dict[str, str]:
    keys = [
        "event_type",
        "offer_price",
        "issue_price",
        "cash_consideration",
        "record_date",
        "ex_date",
        "meeting_date",
        "opening_date",
        "closing_date",
        "swap_ratio",
        "entitlement_ratio",
        "buyback_size",
        "aggregate_amount",
        "timeline_text",
        "conditions_text",
    ]
    return {key: clean(row.get(key), "") for key in keys if clean(row.get(key), "")}


def risk_flags_for(row: dict[str, Any], terms: dict[str, str]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    event_type = clean(row.get("event_type"), "").lower()
    if event_type in {"buyback", "open_offer", "delisting"}:
        flags.append({"risk": "tender_acceptance_uncertain", "detail": "Final economics depend on acceptance ratio, liquidity, taxes, and market price."})
    if not terms.get("record_date"):
        flags.append({"risk": "record_date_missing", "detail": "Record date was not extracted; verify filing manually before any action."})
    if event_type in {"merger", "demerger", "scheme_arrangement", "reverse_merger"}:
        flags.append({"risk": "scheme_conditions", "detail": "Scheme events can require tribunal, shareholder, creditor, exchange, and regulator approvals."})
    if clean(row.get("confidence"), "0") not in {"0.95", "1", "1.0"}:
        flags.append({"risk": "extraction_confidence_review", "detail": f"Extraction confidence is {clean(row.get('confidence'), '0')}."})
    flags.append({"risk": "human_approval_required", "detail": "This memo is research routing only; no trade, alert-to-execution, or client recommendation is authorized."})
    return flags


def followups_for(row: dict[str, Any], terms: dict[str, str]) -> list[dict[str, str]]:
    event_type = clean(row.get("event_type"), "event")
    followups = [
        {"owner": "Special Situations Agent", "action": "Verify extracted terms against source filing attachment."},
        {"owner": "Risk Office", "action": "Check liquidity, concentration, execution risk, and whether this conflicts with existing books."},
        {"owner": "Charlie Munger", "action": "Decide reject, monitor, research more, or escalate to Investment Committee."},
    ]
    if event_type == "buyback":
        followups.insert(1, {"owner": "Event Arbitrage Analyst", "action": "Calculate spread, tender probability, acceptance ratio scenarios, taxes, and downside mark-to-market."})
    if terms.get("opening_date") or terms.get("closing_date"):
        followups.append({"owner": "Jarvis", "action": "Add calendar/watchlist reminders for event window after human approval."})
    return followups


def build_memo(row: dict[str, Any], terms: dict[str, str], risk_flags: list[dict[str, str]], followups: list[dict[str, str]], actor: str) -> str:
    symbol = clean(row.get("symbol"), clean(row.get("company_name"), "Special situation"))
    event_type = clean(row.get("event_type"), "event").replace("_", " ")
    source_url = clean(row.get("attachment_url"), clean(row.get("source_url"), "n/a"))
    title = clean(row.get("title"), "Corporate filing")
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Special Situation Memo - {symbol} {event_type.title()}",
        "",
        f"Generated: {generated_at}",
        f"Generated by: {actor}",
        f"Company: {clean(row.get('company_name'), symbol)}",
        f"Symbol: `{symbol}`",
        f"Event type: `{clean(row.get('event_type'), 'event')}`",
        f"Special terms id: `{row.get('id')}`",
        f"Filing id: `{row.get('filing_id')}`",
        f"Source: {source_url}",
        "",
        "## Filing Summary",
        "",
        f"- Filing title: {title}",
        f"- Exchange/source: `{clean(row.get('exchange'))}` / `{clean(row.get('source_name'))}`",
        f"- Source URL: {clean(row.get('source_url'))}",
        f"- Attachment URL: {clean(row.get('attachment_url'))}",
        "",
        "## Extracted Terms",
        "",
        "| Term | Value |",
        "| --- | --- |",
    ]
    for key, value in terms.items():
        lines.append(f"| {key.replace('_', ' ').title()} | {value} |")
    if not terms:
        lines.append("| Extracted terms | n/a |")
    lines.extend(
        [
            "",
            "## Initial Interpretation",
            "",
            f"- This is a `{clean(row.get('event_type'), 'event')}` candidate captured from a real exchange filing.",
            "- The system has extracted structured dates/prices/ratios where available, but the filing must still be checked before any action.",
            "- Treat this memo as an event research packet and routing object, not as an instruction to trade.",
            "",
            "## Risk Flags",
            "",
        ]
    )
    lines.extend([f"- `{flag['risk']}`: {flag['detail']}" for flag in risk_flags])
    lines.extend(["", "## Required Follow-Ups", ""])
    lines.extend([f"- {item['owner']}: {item['action']}" for item in followups])
    lines.extend(
        [
            "",
            "## Committee Gate",
            "",
            "- Allowed decisions: `reject`, `monitor`, `research_more`, `committee_review`.",
            "- Any trade alert, paper trade, live trade, or client-facing recommendation requires a separate approval record.",
            "- Charlie Munger and Risk Office review are mandatory before this becomes an actionable idea.",
        ]
    )
    return "\n".join(lines) + "\n"


def upsert_note(note_path: str, title: str, body: str, row: dict[str, Any]) -> None:
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    summary = f"{clean(row.get('symbol'), clean(row.get('company_name')))} {clean(row.get('event_type'))} memo from filing {row.get('filing_id')}"
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
                'special_situation_memo',
                {sql_text_array(['ai-os', 'research', 'special-situation', clean(row.get('event_type'), 'event'), clean(row.get('symbol'), 'symbol')])},
                {sql_jsonb({'source': 'generate_special_situation_memo.py', 'filing_id': row.get('filing_id'), 'special_terms_id': row.get('id')})},
                {sql_literal(content_hash)},
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
                last_modified_at = now(),
                indexed_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )


def upsert_memo(row: dict[str, Any], terms: dict[str, str], risk_flags: list[dict[str, str]], followups: list[dict[str, str]], note_path: str, title: str, actor: str) -> dict[str, Any]:
    summary = f"{clean(row.get('symbol'), clean(row.get('company_name')))} {clean(row.get('event_type'))} memo generated from extracted filing terms; pending human committee review."
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO research.special_situation_memos (
                special_terms_id, filing_id, filing_event_id, event_type, symbol,
                company_name, memo_title, memo_status, note_path, summary,
                extracted_terms, risk_flags, required_followups, created_by, updated_at
            )
            VALUES (
                {row['id']},
                {row['filing_id']},
                {row.get('filing_event_id') or 'NULL'},
                {sql_literal(clean(row.get('event_type'), 'event'))},
                {sql_literal(clean(row.get('symbol'), ''))},
                {sql_literal(clean(row.get('company_name'), ''))},
                {sql_literal(title)},
                'generated',
                {sql_literal(note_path)},
                {sql_literal(summary)},
                {sql_jsonb(terms)},
                {sql_jsonb(risk_flags)},
                {sql_jsonb(followups)},
                {sql_literal(actor)},
                now()
            )
            ON CONFLICT (special_terms_id) DO UPDATE SET
                memo_title = EXCLUDED.memo_title,
                memo_status = 'generated',
                note_path = EXCLUDED.note_path,
                summary = EXCLUDED.summary,
                extracted_terms = EXCLUDED.extracted_terms,
                risk_flags = EXCLUDED.risk_flags,
                required_followups = EXCLUDED.required_followups,
                updated_at = now()
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    if not rows:
        raise RuntimeError("memo upsert did not return a row")
    return rows[0]


def ensure_routing(memo: dict[str, Any], row: dict[str, Any], note_path: str, actor: str) -> dict[str, Any]:
    if memo.get("task_id") and memo.get("approval_id"):
        run_psql_json(
            f"""
            WITH updated AS (
                UPDATE research.special_situation_memos
                SET memo_status = 'routed_for_review',
                    updated_at = now()
                WHERE id = {memo['id']}
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
            """
        )
        return {"memo_id": memo["id"], "task_id": memo["task_id"], "approval_id": memo["approval_id"], "existing": True}
    title = f"Review special situation memo: {clean(row.get('symbol'), clean(row.get('company_name')))} {clean(row.get('event_type'))}"
    evidence = [
        {"source_table": "research.special_situation_terms", "id": row.get("id")},
        {"source_table": "research.corporate_filings", "id": row.get("filing_id")},
        {"memo_note_path": note_path},
        {"source_url": row.get("attachment_url") or row.get("source_url")},
    ]
    rows = run_psql_json(
        f"""
        WITH task AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, output_note_path, evidence
            )
            VALUES (
                {sql_literal(title)},
                'Verify special-situation terms, assess spread/risk/follow-ups, and route to Charlie or Investment Committee. No trade is authorized by this task.',
                'Special Situations Agent',
                'needs_review',
                'high',
                true,
                'research.special_situation_terms',
                {sql_literal(str(row.get('id')))},
                'special_situation_memo',
                {sql_literal(note_path)},
                {sql_jsonb(evidence)}
            )
            RETURNING id
        ),
        approval AS (
            INSERT INTO agent.approvals (
                task_id, approval_type, title, owner_agent, risk_level, status,
                requested_action, rationale
            )
            SELECT
                task.id,
                'investment_committee_review',
                {sql_literal('Investment Committee review required: ' + clean(row.get('symbol'), clean(row.get('company_name'))) + ' ' + clean(row.get('event_type')))},
                'Charlie Munger',
                'high',
                'pending',
                {sql_jsonb({'special_terms_id': row.get('id'), 'memo_id': memo.get('id'), 'note_path': note_path, 'allowed_decisions': ['reject', 'monitor', 'research_more', 'committee_review'], 'live_execution_allowed': False})},
                'Special-situation filing memo requires human review before any trade, alert-to-execution, or client-facing recommendation.'
            FROM task
            RETURNING id
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority, recommended_action,
                evidence, target_workspace
            )
            SELECT
                task.id,
                {sql_literal(title)},
                'Charlie Munger',
                'needs_review',
                'high',
                'Review memo and choose reject, monitor, research_more, or committee_review. No trade is authorized.',
                {sql_jsonb(evidence)},
                'research'
            FROM task
            RETURNING id
        ),
        updated AS (
            UPDATE research.special_situation_memos
            SET task_id = (SELECT id FROM task),
                approval_id = (SELECT id FROM approval),
                memo_status = 'routed_for_review',
                updated_at = now()
            WHERE id = {memo['id']}
            RETURNING id, task_id, approval_id, memo_status
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT updated.*, (SELECT id FROM inbox LIMIT 1) AS inbox_id
            FROM updated
        ) rows
        """
    )
    if not rows:
        raise RuntimeError("memo routing did not return a row")
    rows[0]["existing"] = False
    rows[0]["actor"] = actor
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a special-situation event memo into Obsidian and route review.")
    parser.add_argument("--special-terms-id", type=int, required=True)
    parser.add_argument("--actor", default="Special Situations Agent")
    args = parser.parse_args()

    row = fetch_terms(args.special_terms_id)
    existing_memo = fetch_existing_memo(args.special_terms_id)
    terms = build_terms_payload(row)
    risk_flags = risk_flags_for(row, terms)
    followups = followups_for(row, terms)
    symbol = clean(row.get("symbol"), clean(row.get("company_name"), "Special situation"))
    event_type = clean(row.get("event_type"), "event")
    memo_title = f"Special Situation Memo - {symbol} {event_type.replace('_', ' ').title()}"
    body = build_memo(row, terms, risk_flags, followups, args.actor)

    MEMO_DIR.mkdir(parents=True, exist_ok=True)
    if existing_memo and existing_memo.get("note_path"):
        path = VAULT_ROOT / clean(existing_memo["note_path"])
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = MEMO_DIR / f"{stamp}-special-situation-{args.special_terms_id}-{safe_slug(symbol)}-{safe_slug(event_type)}.md"
    path.write_text(body, encoding="utf-8")
    relative_path = str(path.relative_to(VAULT_ROOT))

    upsert_note(relative_path, memo_title, body, row)
    memo = upsert_memo(row, terms, risk_flags, followups, relative_path, memo_title, args.actor)
    routing = ensure_routing(memo, row, relative_path, args.actor)
    print(
        json.dumps(
            {
                "special_terms_id": args.special_terms_id,
                "memo_id": memo.get("id"),
                "memo_note_path": relative_path,
                "routing": routing,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
