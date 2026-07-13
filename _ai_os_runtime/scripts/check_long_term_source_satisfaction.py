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
CHECK_DIR = VAULT_ROOT / "ai memory" / "05 Filings and Transcripts" / "Long-Term Source Checks"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_int(value: object) -> str:
    if value in (None, ""):
        return "NULL"
    return str(int(value))


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
    return slug[:90] or "source-check"


def fetch_requests(request_id: int | None, holding_thesis_id: int | None, limit: int) -> list[dict[str, Any]]:
    if request_id:
        where = [f"id = {int(request_id)}"]
    else:
        where = ["status IN ('queued','collecting','needs_review')"]
    if holding_thesis_id:
        where.append(f"holding_thesis_id = {int(holding_thesis_id)}")
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM portfolio.v_long_term_source_requests
            WHERE {' AND '.join(where)}
            ORDER BY updated_at DESC
            LIMIT {max(1, int(limit))}
        ) rows
        """
    )


def source_terms(source_name: str, source_category: str) -> list[str]:
    text = f"{source_name} {source_category}".lower()
    terms = []
    if "annual" in text:
        terms.extend(["annual", "annual report"])
    if "presentation" in text:
        terms.extend(["presentation", "investor presentation", "earnings presentation"])
    if "transcript" in text:
        terms.extend(["transcript", "conference call"])
    if "financial" in text or "audited" in text:
        terms.extend(["financial", "audited", "results"])
    if "filing" in text:
        terms.extend(["filing", "announcement", "disclosure"])
    return sorted(set(terms))


def match_title_for_source(row: dict[str, Any], source_name: str, source_category: str) -> bool:
    terms = source_terms(source_name, source_category)
    if source_name == "company_filings":
        return True
    haystack = " ".join(
        clean(row.get(key), "")
        for key in ["title", "filing_type", "artifact_type", "source_url", "note_type", "body_summary"]
    ).lower()
    return any(term in haystack for term in terms)


def find_corporate_filing_matches(request: dict[str, Any]) -> list[dict[str, Any]]:
    symbol = clean(request.get("symbol")).upper()
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, source_name, exchange, symbol, company_name, filing_type,
                   event_type, title, filed_at, source_url, attachment_url,
                   extraction_status
            FROM research.corporate_filings
            WHERE upper(symbol) = {sql_literal(symbol)}
            ORDER BY filed_at DESC NULLS LAST, created_at DESC
            LIMIT 50
        ) rows
        """
    )
    return [
        {"source_table": "research.corporate_filings", "id": row["id"], "title": row.get("title"), "source_url": row.get("source_url"), "attachment_url": row.get("attachment_url")}
        for row in rows
        if match_title_for_source(row, clean(request.get("source_name")), clean(request.get("source_category")))
    ]


def find_artifact_matches(request: dict[str, Any]) -> list[dict[str, Any]]:
    symbol = clean(request.get("symbol")).upper()
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, artifact_type, title, source_url, local_path, metadata, captured_at
            FROM core.raw_artifacts
            WHERE upper(coalesce(title, '')) LIKE {sql_literal('%' + symbol + '%')}
               OR metadata::text ILIKE {sql_literal('%' + symbol + '%')}
            ORDER BY captured_at DESC
            LIMIT 50
        ) rows
        """
    )
    matches = []
    for row in rows:
        if match_title_for_source(row, clean(request.get("source_name")), clean(request.get("source_category"))):
            matches.append(
                {
                    "source_table": "core.raw_artifacts",
                    "id": row["id"],
                    "title": row.get("title"),
                    "source_url": row.get("source_url"),
                    "local_path": row.get("local_path"),
                }
            )
    return matches


def note_has_source_provenance(row: dict[str, Any]) -> bool:
    text = json.dumps(row.get("frontmatter") or {}, sort_keys=True).lower()
    summary = clean(row.get("body_summary"), "").lower()
    tags = [str(tag).lower() for tag in row.get("tags") or []]
    if row.get("note_type") in {"source_document", "long_term_source_document", "filing_source_note", "annual_report_source"}:
        return True
    if any(tag in {"source-document", "source", "filing-source", "annual-report"} for tag in tags):
        return True
    return "source_url" in text or "source_urls" in text or "http://" in summary or "https://" in summary


def find_obsidian_source_matches(request: dict[str, Any]) -> list[dict[str, Any]]:
    symbol = clean(request.get("symbol")).upper()
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, note_path, title, note_type, tags, frontmatter, body_summary, indexed_at
            FROM knowledge.obsidian_notes
            WHERE (title ILIKE {sql_literal('%' + symbol + '%')} OR body_summary ILIKE {sql_literal('%' + symbol + '%')})
              AND note_type NOT IN ('long_term_source_request_batch','long_term_source_check_batch')
            ORDER BY indexed_at DESC
            LIMIT 50
        ) rows
        """
    )
    matches = []
    for row in rows:
        if note_has_source_provenance(row) and match_title_for_source(row, clean(request.get("source_name")), clean(request.get("source_category"))):
            matches.append(
                {
                    "source_table": "knowledge.obsidian_notes",
                    "id": row["id"],
                    "title": row.get("title"),
                    "note_path": row.get("note_path"),
                }
            )
    return matches


def check_request(request: dict[str, Any], actor: str) -> dict[str, Any]:
    matches = [
        *find_corporate_filing_matches(request),
        *find_artifact_matches(request),
        *find_obsidian_source_matches(request),
    ]
    check_status = "satisfied" if matches else "missing"
    missing_reason = None if matches else "No matching corporate filing, raw artifact, or source-provenance Obsidian note found."
    check_rows = run_psql_json(
        f"""
        WITH rows AS (
            INSERT INTO portfolio.long_term_source_request_checks (
                source_request_id, request_key, symbol, source_name,
                check_status, matched_source_count, matches, missing_reason, checked_by
            )
            VALUES (
                {int(request['id'])},
                {sql_literal(request['request_key'])},
                {sql_literal(request['symbol'])},
                {sql_literal(request['source_name'])},
                {sql_literal(check_status)},
                {len(matches)},
                {sql_jsonb(matches)},
                {sql_literal(missing_reason)},
                {sql_literal(actor)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    update_rows = run_psql_json(
        f"""
        WITH rows AS (
            UPDATE portfolio.long_term_source_requests
            SET satisfaction_status = {sql_literal(check_status)},
                matched_source_count = {len(matches)},
                satisfaction_evidence = {sql_jsonb(matches)},
                last_checked_at = now(),
                status = CASE WHEN {sql_literal(check_status)} = 'satisfied' THEN 'satisfied' ELSE status END,
                satisfied_at = CASE WHEN {sql_literal(check_status)} = 'satisfied' THEN now() ELSE satisfied_at END,
                satisfied_by = CASE WHEN {sql_literal(check_status)} = 'satisfied' THEN {sql_literal(actor)} ELSE satisfied_by END,
                updated_at = now()
            WHERE id = {int(request['id'])}
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM rows
        """
    )
    if matches:
        run_psql_json(
            f"""
            WITH task_update AS (
                UPDATE agent.tasks
                SET status = 'needs_review',
                    evidence = {sql_jsonb(matches)},
                    updated_at = now()
                WHERE id = {sql_int(request.get('task_id'))}
                RETURNING id
            ),
            inbox_update AS (
                UPDATE agent.inbox_items
                SET status = 'needs_review',
                    recommended_action = 'Source evidence has been matched. Review provenance and rerun the blocked specialist module.',
                    evidence = {sql_jsonb(matches)},
                    updated_at = now()
                WHERE id = {sql_int(request.get('inbox_id'))}
                RETURNING id
            )
            SELECT json_build_array(json_build_object('task_id', (SELECT id FROM task_update), 'inbox_id', (SELECT id FROM inbox_update)))::text
            """
        )
    return {
        "request_id": request["id"],
        "request_key": request["request_key"],
        "symbol": request["symbol"],
        "source_name": request["source_name"],
        "check_status": check_status,
        "matched_source_count": len(matches),
        "check_id": check_rows[0]["id"] if check_rows else None,
        "status_after": update_rows[0]["status"] if update_rows else request.get("status"),
        "matches": matches[:5],
    }


def queue_ready_specialist_reruns(actor: str) -> list[dict[str, Any]]:
    outputs = run_psql_json(
        """
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT output.id AS specialist_output_id,
                   output.assignment_id,
                   output.symbol,
                   output.module_key,
                   output.module_name,
                   assignment.task_id,
                   assignment.inbox_id
            FROM portfolio.v_long_term_specialist_outputs output
            JOIN portfolio.long_term_specialist_assignments assignment ON assignment.id = output.assignment_id
            WHERE output.source_status = 'source_required'
              AND EXISTS (
                  SELECT 1
                  FROM portfolio.long_term_source_requests request
                  WHERE request.specialist_output_id = output.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM portfolio.long_term_source_requests request
                  WHERE request.specialist_output_id = output.id
                    AND request.status <> 'satisfied'
              )
            LIMIT 25
        ) rows
        """
    )
    queued: list[dict[str, Any]] = []
    for output in outputs:
        run_psql_json(
            f"""
            WITH output_update AS (
                UPDATE portfolio.long_term_specialist_outputs
                SET source_status = 'source_ready',
                    output_status = 'needs_rerun',
                    updated_at = now()
                WHERE id = {int(output['specialist_output_id'])}
                RETURNING id
            ),
            assignment_update AS (
                UPDATE portfolio.long_term_specialist_assignments
                SET source_status = 'source_ready',
                    status = 'queued',
                    updated_at = now()
                WHERE id = {int(output['assignment_id'])}
                RETURNING id
            ),
            task_update AS (
                UPDATE agent.tasks
                SET status = 'queued',
                    objective = objective || ' Source requests are now satisfied; rerun specialist module with new evidence.',
                    updated_at = now()
                WHERE id = {sql_int(output.get('task_id'))}
                RETURNING id
            ),
            inbox_update AS (
                UPDATE agent.inbox_items
                SET status = 'new',
                    recommended_action = 'Source requests are satisfied. Rerun the specialist assignment and update the committee packet.',
                    updated_at = now()
                WHERE id = {sql_int(output.get('inbox_id'))}
                RETURNING id
            )
            SELECT json_build_array(json_build_object('specialist_output_id', (SELECT id FROM output_update)))::text
            """
        )
        queued.append(output)
    return queued


def build_note(results: list[dict[str, Any]], reruns: list[dict[str, Any]], actor: str) -> str:
    lines = [
        "# Long-Term Source Satisfaction Check",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Generated by: {actor}",
        "",
        "## Guardrail",
        "",
        "This check only verifies source availability. It does not authorize investment or trading action.",
        "",
        "## Results",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['request_key']}`: {result['symbol']} · {result['source_name']} · "
            f"`{result['check_status']}` · matches `{result['matched_source_count']}`"
        )
    lines.extend(["", "## Specialist Reruns Queued", ""])
    if reruns:
        for rerun in reruns:
            lines.append(f"- {rerun['symbol']} · {rerun['module_name']} · assignment `{rerun['assignment_id']}`")
    else:
        lines.append("- None.")
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
                'long_term_source_check_batch',
                ARRAY['ai-os','long-term','source-check']::text[],
                {sql_jsonb({'source': 'check_long_term_source_satisfaction.py'})},
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


def run_checks(args: argparse.Namespace) -> dict[str, Any]:
    requests = fetch_requests(args.source_request_id, args.holding_thesis_id, args.limit)
    results = [check_request(request, args.actor) for request in requests]
    reruns = queue_ready_specialist_reruns(args.actor)
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    symbols = "-".join(sorted({clean(result.get("symbol")).upper() for result in results})) or "source-check"
    note_path = CHECK_DIR / f"{stamp}-{safe_slug(symbols)}.md"
    note_path.write_text(build_note(results, reruns, args.actor))
    rel_path = str(note_path.relative_to(VAULT_ROOT))
    insert_obsidian_note(note_path, "Long-Term Source Satisfaction Check", f"Checked {len(results)} source requests; satisfied {sum(1 for item in results if item['check_status'] == 'satisfied')}.")
    return {
        "checked_count": len(results),
        "satisfied_count": sum(1 for item in results if item["check_status"] == "satisfied"),
        "missing_count": sum(1 for item in results if item["check_status"] == "missing"),
        "rerun_queued_count": len(reruns),
        "note_path": rel_path,
        "results": results,
        "capital_action_allowed": False,
        "live_execution_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Long-Term source request satisfaction.")
    parser.add_argument("--source-request-id", type=int)
    parser.add_argument("--holding-thesis-id", type=int)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--actor", default="Filings and Transcript Analyst")
    args = parser.parse_args()
    try:
        result = run_checks(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
