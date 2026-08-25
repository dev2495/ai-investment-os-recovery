#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    psql_bin = os.environ.get("AI_OS_PSQL_BIN") or "/opt/homebrew/opt/postgresql@15/bin/psql"
    password = os.environ.get("AI_OS_POSTGRES_PASSWORD")
    if Path(psql_bin).exists() and password:
        command = [psql_bin, f"host={os.environ.get('AI_OS_POSTGRES_HOST') or '127.0.0.1'} port={os.environ.get('AI_OS_POSTGRES_PORT') or '54329'} dbname={os.environ.get('AI_OS_POSTGRES_DB') or 'ai_os'} user={os.environ.get('AI_OS_POSTGRES_USER') or 'ai_os'} connect_timeout=3 options='-c statement_timeout=30000 -c lock_timeout=5000'", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql]
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=35)
    else:
        command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"]
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, timeout=35)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def source_rows(source_key: str | None, limit: int) -> list[dict[str, Any]]:
    where = f"WHERE ds.source_key = {sql_literal(source_key)}" if source_key else "WHERE ds.status IN ('active','installed','imported','mapped')"
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            WITH latest_check AS (
                SELECT DISTINCT ON (source_key)
                    source_key, checked_at, status, rows_seen, error_message, sample_payload
                FROM core.data_source_checks
                ORDER BY source_key, checked_at DESC, id DESC
            ),
            latest_ok AS (
                SELECT source_key, max(checked_at) AS latest_ok_at
                FROM core.data_source_checks
                WHERE status = 'ok'
                GROUP BY source_key
            ),
            latest_quote AS (
                SELECT source_key, max(quote_ts) AS latest_quote_at
                FROM market.price_quotes
                GROUP BY source_key
            )
            SELECT
                ds.source_key,
                ds.source_name,
                ds.source_type,
                ds.provider,
                ds.status AS registry_status,
                ds.freshness_target_minutes,
                ds.owner_agent,
                latest_check.checked_at AS latest_check_at,
                latest_check.status AS latest_check_status,
                latest_check.rows_seen,
                latest_check.error_message,
                latest_check.sample_payload,
                latest_ok.latest_ok_at,
                latest_quote.latest_quote_at,
                CASE
                    WHEN latest_quote.latest_quote_at IS NOT NULL
                      OR lower(ds.source_type) ~ '(quote|broker_api|price_feed)'
                    THEN 'quote'
                    ELSE 'check'
                END AS freshness_basis,
                CASE
                    WHEN latest_quote.latest_quote_at IS NOT NULL
                      OR lower(ds.source_type) ~ '(quote|broker_api|price_feed)'
                    THEN CASE WHEN latest_quote.latest_quote_at IS NULL THEN NULL
                      ELSE EXTRACT(EPOCH FROM (now()-latest_quote.latest_quote_at))/60 END
                    WHEN latest_ok.latest_ok_at IS NULL AND latest_check.checked_at IS NULL THEN NULL
                    ELSE EXTRACT(EPOCH FROM (now()-GREATEST(
                        coalesce(latest_ok.latest_ok_at,'-infinity'::timestamptz),
                        coalesce(latest_check.checked_at,'-infinity'::timestamptz))))/60
                END AS staleness_minutes
            FROM core.data_source_registry ds
            LEFT JOIN latest_check ON latest_check.source_key = ds.source_key
            LEFT JOIN latest_ok ON latest_ok.source_key = ds.source_key
            LEFT JOIN latest_quote ON latest_quote.source_key = ds.source_key
            {where}
            ORDER BY ds.source_key
            LIMIT {limit}
        ) rows
        """
    )
    return rows


def classify(row: dict[str, Any], target_override: int | None) -> tuple[str, str]:
    target = target_override or row.get("freshness_target_minutes")
    if not target:
        return "not_targeted", "low"
    if row.get("freshness_basis") == "quote":
        if not row.get("latest_quote_at"):
            return "missing_quote", "high"
    else:
        if not row.get("latest_check_at"):
            return "missing_check", "high"
        if row.get("latest_check_status") not in {"ok", None}:
            return "error", "high"
    staleness = Decimal(str(row.get("staleness_minutes") or "0"))
    if staleness > Decimal(str(target)):
        return "stale", "high" if staleness > Decimal(str(target)) * Decimal("2") else "medium"
    return "fresh", "low"


def upsert_risk_event(row: dict[str, Any], freshness_status: str, severity: str, evidence: dict[str, Any]) -> int | None:
    source_key = str(row["source_key"])
    if freshness_status in {"fresh", "not_targeted"}:
        run_psql_json(
            f"""
            WITH closed AS (
                UPDATE risk.events
                SET status = 'closed',
                    message = coalesce(message, '') || ' Freshness recovered at ' || now()::text || '.'
                WHERE scope_type = 'data_source'
                  AND scope_ref = {sql_literal(source_key)}
                  AND status IN ('new','acknowledged')
                RETURNING id
            )
            SELECT coalesce(json_agg(row_to_json(closed)), '[]'::json)::text FROM closed
            """
        )
        return None

    title = f"Data source freshness issue: {source_key}"
    message = (
        f"{source_key} is {freshness_status}. "
        f"Target={row.get('freshness_target_minutes')} minutes; "
        f"staleness={row.get('staleness_minutes')} minutes."
    )
    rows = run_psql_json(
        f"""
        WITH existing AS (
            SELECT id
            FROM risk.events
            WHERE scope_type = 'data_source'
              AND scope_ref = {sql_literal(source_key)}
              AND status IN ('new','acknowledged')
            ORDER BY ts DESC
            LIMIT 1
        ),
        updated AS (
            UPDATE risk.events
            SET ts = now(),
                severity = {sql_literal(severity)},
                title = {sql_literal(title)},
                message = {sql_literal(message)},
                evidence = {sql_jsonb(evidence)}
            WHERE id IN (SELECT id FROM existing)
            RETURNING id
        ),
        inserted AS (
            INSERT INTO risk.events (
                scope_type, scope_ref, severity, status, title, message, evidence
            )
            SELECT
                'data_source',
                {sql_literal(source_key)},
                {sql_literal(severity)},
                'new',
                {sql_literal(title)},
                {sql_literal(message)},
                {sql_jsonb(evidence)}
            WHERE NOT EXISTS (SELECT 1 FROM existing)
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(output)), '[]'::json)::text
        FROM (
            SELECT id FROM updated
            UNION ALL
            SELECT id FROM inserted
        ) output
        """
    )
    if rows:
        return int(rows[0]["id"])
    return None


def store_result(row: dict[str, Any], status: str, severity: str, risk_event_id: int | None, actor: str, target_override: int | None) -> dict[str, Any]:
    target = target_override or row.get("freshness_target_minutes")
    evidence = {
        "source_key": row.get("source_key"),
        "latest_check_status": row.get("latest_check_status"),
        "latest_check_at": row.get("latest_check_at"),
        "latest_ok_at": row.get("latest_ok_at"),
        "latest_quote_at": row.get("latest_quote_at"),
        "freshness_basis": row.get("freshness_basis"),
        "staleness_minutes": row.get("staleness_minutes"),
        "target_minutes": target,
        "sample_payload": row.get("sample_payload"),
        "error_message": row.get("error_message"),
    }
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.data_source_freshness_checks (
                source_key, source_name, freshness_target_minutes, latest_check_at,
                latest_ok_at, latest_quote_at, staleness_minutes, status, severity,
                rows_seen, risk_event_id, evidence, created_by
            )
            VALUES (
                {sql_literal(row.get('source_key'))},
                {sql_literal(row.get('source_name'))},
                {int(target) if target else 'NULL'},
                {sql_literal(row.get('latest_check_at'))}::timestamptz,
                {sql_literal(row.get('latest_ok_at'))}::timestamptz,
                {sql_literal(row.get('latest_quote_at'))}::timestamptz,
                {row.get('staleness_minutes') if row.get('staleness_minutes') is not None else 'NULL'},
                {sql_literal(status)},
                {sql_literal(severity)},
                {row.get('rows_seen') if row.get('rows_seen') is not None else 'NULL'},
                {risk_event_id if risk_event_id is not None else 'NULL'},
                {sql_jsonb(evidence)},
                {sql_literal(actor)}
            )
            RETURNING id, source_key, status, severity, staleness_minutes,
                      freshness_target_minutes, risk_event_id, created_at
        ),
        seen AS (
            UPDATE core.data_source_registry ds
            SET last_seen_at = coalesce(
                    {sql_literal(row.get('latest_quote_at'))}::timestamptz,
                    {sql_literal(row.get('latest_ok_at'))}::timestamptz,
                    {sql_literal(row.get('latest_check_at'))}::timestamptz,
                    ds.last_seen_at
                ),
                updated_at = now()
            WHERE ds.source_key = {sql_literal(row.get('source_key'))}
            RETURNING source_key
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate data-source freshness and create/close risk events.")
    parser.add_argument("--source-key")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--target-minutes", type=int)
    parser.add_argument("--actor", default="Data Steward")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for row in source_rows(args.source_key, args.limit):
        status, severity = classify(row, args.target_minutes)
        evidence = {
            "source_key": row.get("source_key"),
            "status": status,
            "latest_check_status": row.get("latest_check_status"),
            "latest_check_at": row.get("latest_check_at"),
            "latest_ok_at": row.get("latest_ok_at"),
            "latest_quote_at": row.get("latest_quote_at"),
            "staleness_minutes": row.get("staleness_minutes"),
            "target_minutes": args.target_minutes or row.get("freshness_target_minutes"),
        }
        risk_event_id = upsert_risk_event(row, status, severity, evidence)
        results.append(store_result(row, status, severity, risk_event_id, args.actor, args.target_minutes))

    summary = {
        "checked": len(results),
        "fresh": sum(1 for result in results if result["status"] == "fresh"),
        "stale_or_error": sum(1 for result in results if result["status"] in {"stale", "error", "missing_check"}),
        "results": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
