#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from check_model_endpoint_live import check_endpoint


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def run_psql(sql: str, tuples_only: bool = False) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def fetch_json_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM ({sql}) q;"
    text = run_psql(wrapped, tuples_only=True)
    return json.loads(text) if text else []


def run_psql_json_statement(sql: str) -> list[dict[str, Any]]:
    text = run_psql(sql, tuples_only=True)
    return json.loads(text) if text else []


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def create_run(run_key: str, actor: str) -> None:
    run_psql(
        f"""
        INSERT INTO core.provider_readiness_runs (run_key, status, created_by, started_at)
        VALUES ({sql_literal(run_key)}, 'started', {sql_literal(actor)}, now())
        ON CONFLICT (run_key) DO UPDATE SET
            status = 'started',
            model_checks_run = 0,
            source_checks_run = 0,
            ready_count = 0,
            needs_check_count = 0,
            blocked_count = 0,
            degraded_count = 0,
            summary = '{{}}'::jsonb,
            error_message = NULL,
            started_at = now(),
            finished_at = NULL,
            duration_ms = NULL,
            created_by = EXCLUDED.created_by;
        """
    )


def finish_run(run_key: str, started: float, status: str, summary: dict[str, Any], error: str | None = None) -> dict[str, Any]:
    duration_ms = int((time.time() - started) * 1000)
    counts = {row["readiness_status"]: int(row["count"]) for row in fetch_json_rows("SELECT readiness_status, count(*) FROM core.v_provider_readiness_board GROUP BY readiness_status")}
    ready_count = counts.get("ready", 0)
    needs_check_count = counts.get("needs_check", 0)
    blocked_count = sum(count for key, count in counts.items() if str(key).startswith("blocked"))
    degraded_count = counts.get("degraded", 0) + counts.get("approval_required", 0) + counts.get("needs_activation", 0)
    rows = run_psql_json_statement(
        f"""
        WITH updated AS (
            UPDATE core.provider_readiness_runs
            SET status = {sql_literal(status)},
                model_checks_run = {int(summary.get("model_checks_run") or 0)},
                source_checks_run = {int(summary.get("source_checks_run") or 0)},
                ready_count = {ready_count},
                needs_check_count = {needs_check_count},
                blocked_count = {blocked_count},
                degraded_count = {degraded_count},
                summary = {sql_jsonb({**summary, "readiness_counts": counts})},
                error_message = {sql_literal(error)},
                finished_at = now(),
                duration_ms = {duration_ms}
            WHERE run_key = {sql_literal(run_key)}
            RETURNING *
        )
        SELECT COALESCE(json_agg(row_to_json(updated)), '[]'::json)::text
        FROM updated
        """
    )
    return rows[0] if rows else {}


def run_model_checks(actor: str, limit: int) -> list[dict[str, Any]]:
    endpoints = fetch_json_rows(
        f"""
        SELECT endpoint_key
        FROM agent.v_model_endpoint_control
        ORDER BY
            CASE health_status WHEN 'unchecked' THEN 0 ELSE 1 END,
            endpoint_key
        LIMIT {limit}
        """
    )
    results: list[dict[str, Any]] = []
    for row in endpoints:
        endpoint_key = str(row["endpoint_key"])
        results.append(check_endpoint(endpoint_key, actor))
    return results


def run_source_checks(actor: str, limit: int) -> list[dict[str, Any]]:
    connectors = fetch_json_rows(
        f"""
        SELECT connector_key
        FROM core.v_source_connector_control
        ORDER BY
            CASE health_status WHEN 'unchecked' THEN 0 ELSE 1 END,
            connector_key
        LIMIT {limit}
        """
    )
    results: list[dict[str, Any]] = []
    for row in connectors:
        connector_key = str(row["connector_key"])
        check = run_psql_json_statement(
            f"SELECT jsonb_build_array(core.run_source_connector_health_check({sql_literal(connector_key)}, {sql_literal(actor)}))::text"
        )
        if check:
            results.append(check[0])
    return results


def provider_samples() -> dict[str, Any]:
    return {
        "summary": fetch_json_rows("SELECT * FROM core.v_provider_readiness_summary ORDER BY metric"),
        "blocked": fetch_json_rows(
            """
            SELECT provider_kind, provider_key, provider_name, readiness_status, next_action, owner_agent
            FROM core.v_provider_readiness_board
            WHERE readiness_status LIKE 'blocked%' OR readiness_status IN ('needs_activation', 'needs_check')
            ORDER BY id
            LIMIT 12
            """
        ),
        "ready": fetch_json_rows(
            """
            SELECT provider_kind, provider_key, provider_name, readiness_status, owner_agent
            FROM core.v_provider_readiness_board
            WHERE readiness_status = 'ready'
            ORDER BY provider_kind, provider_key
            LIMIT 12
            """
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run provider readiness sweep across model endpoints and source connectors.")
    parser.add_argument("--run-key", default=f"provider_readiness_{int(time.time())}")
    parser.add_argument("--actor", default="Jarvis")
    parser.add_argument("--model-limit", type=int, default=50)
    parser.add_argument("--source-limit", type=int, default=80)
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()

    started = time.time()
    create_run(args.run_key, args.actor)
    try:
        model_results: list[dict[str, Any]] = []
        source_results: list[dict[str, Any]] = []
        if not args.sources_only:
            model_results = run_model_checks(args.actor, args.model_limit)
        if not args.models_only:
            source_results = run_source_checks(args.actor, args.source_limit)
        summary = {
            "model_checks_run": len(model_results),
            "source_checks_run": len(source_results),
            "samples": provider_samples(),
        }
        result = finish_run(args.run_key, started, "completed", summary)
        print(json.dumps({"run_key": args.run_key, "status": "completed", "result": result}, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        result = finish_run(args.run_key, started, "failed", {"model_checks_run": 0, "source_checks_run": 0}, f"{type(exc).__name__}: {exc}")
        print(json.dumps({"run_key": args.run_key, "status": "failed", "error": str(exc), "result": result}, indent=2, sort_keys=True, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
