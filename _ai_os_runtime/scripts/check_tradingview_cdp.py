#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


SOURCE_KEY = "tradingview_mcp"
DEFAULT_PORT = 9222


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


def probe_cdp(port: int, timeout: float) -> tuple[str, int | None, int, dict[str, Any], str | None]:
    url = f"http://127.0.0.1:{port}/json/version"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return "ok", response.status, latency_ms, payload, None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return "error", None, latency_ms, {"url": url, "port": port}, str(exc)


def store_check(
    *,
    port: int,
    status: str,
    http_status: int | None,
    latency_ms: int,
    sample_payload: dict[str, Any],
    error_message: str | None,
    actor: str,
) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO core.data_source_checks (
                source_key, check_name, check_type, target_url, status,
                http_status, latency_ms, rows_seen, sample_payload, error_message
            )
            VALUES (
                {sql_literal(SOURCE_KEY)},
                'TradingView Desktop CDP controller',
                'local_http',
                {sql_literal(f'http://127.0.0.1:{port}/json/version')},
                {sql_literal(status)},
                {http_status if http_status is not None else 'NULL'},
                {int(latency_ms)},
                {1 if status == 'ok' else 0},
                {sql_jsonb({**sample_payload, 'checked_by': actor})},
                {sql_literal(error_message)}
            )
            RETURNING id, source_key, check_name, status, http_status,
                      latency_ms, rows_seen, sample_payload, error_message,
                      checked_at
        ),
        seen AS (
            UPDATE core.data_source_registry
            SET last_seen_at = CASE WHEN {sql_literal(status)} = 'ok' THEN now() ELSE last_seen_at END,
                updated_at = now()
            WHERE source_key = {sql_literal(SOURCE_KEY)}
            RETURNING source_key
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check TradingView Desktop CDP controller and record a data-source check.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--actor", default="Automation Engineer")
    args = parser.parse_args()

    status, http_status, latency_ms, payload, error_message = probe_cdp(args.port, args.timeout)
    result = store_check(
        port=args.port,
        status=status,
        http_status=http_status,
        latency_ms=latency_ms,
        sample_payload=payload,
        error_message=error_message,
        actor=args.actor,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": type(exc).__name__ + ": " + str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
