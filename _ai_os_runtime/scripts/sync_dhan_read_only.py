#!/usr/bin/env python3
"""Fetch immutable Dhan account snapshots through GET-only API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = os.environ.get("AI_OS_DHAN_BASE_URL", "https://api.dhan.co/v2").rstrip("/")
ENDPOINTS = {
    "holdings": "/holdings",
    "positions": "/positions",
    "orders": "/orders",
    "trades": "/trades",
    "funds": "/fundlimit",
}


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def psql(sql: str) -> str:
    candidates = []
    configured = os.environ.get("AI_OS_PSQL_BIN", "").strip()
    if configured:
        candidates.append([configured, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql])
    candidates.extend([
        ["psql", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        ["/opt/homebrew/bin/docker", "exec", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
    ])
    errors = []
    for command in candidates:
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=30)
        except OSError as exc:
            errors.append(f"{command[0]}: {exc}")
            continue
        if result.returncode == 0:
            return result.stdout.strip()
        errors.append((result.stderr or result.stdout).strip())
    raise RuntimeError("; ".join(errors))


def fetch(dataset: str, client_id: str, access_token: str) -> object:
    request = urllib.request.Request(
        BASE_URL + ENDPOINTS[dataset],
        method="GET",
        headers={
            "Accept": "application/json",
            "client-id": client_id,
            "access-token": access_token,
            "User-Agent": "AI-Investment-OS/1.0 read-only connector",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def record_health(status: str, rows: int = 0, error: str | None = None) -> None:
    psql(
        "INSERT INTO core.connector_health_checks "
        "(target_kind,target_key,check_name,check_type,status,rows_seen,error_message,sample_payload,checked_by) VALUES ("
        "'data_source_connector','dhan_live_connector','dhan_read_sync','live_read',"
        f"{sql_literal(status)},{rows},{sql_literal(error) if error else 'NULL'},"
        "'{\"broker_write_allowed\":false}'::jsonb,'Dhan Read-Only Connector')"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--datasets", nargs="*", choices=sorted(ENDPOINTS), default=list(ENDPOINTS))
    args = parser.parse_args()

    client_id = os.environ.get("AI_OS_DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("AI_OS_DHAN_ACCESS_TOKEN", "").strip()
    if not client_id or not access_token:
        print(json.dumps({
            "status": "needs_credentials",
            "required_env": ["AI_OS_DHAN_CLIENT_ID", "AI_OS_DHAN_ACCESS_TOKEN"],
            "broker_write_allowed": False,
        }, indent=2))
        return 2
    if args.check_config:
        print(json.dumps({"status": "configured", "broker_write_allowed": False}, indent=2))
        return 0

    run_key = "dhan-read-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    account_ref = hashlib.sha256(client_id.encode()).hexdigest()[:16]
    summary = {"run_key": run_key, "provider": "Dhan", "account_ref": account_ref, "datasets": {}, "broker_write_allowed": False}
    total_rows = 0
    try:
        for dataset in args.datasets:
            payload = fetch(dataset, client_id, access_token)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
            row_count = len(payload) if isinstance(payload, list) else (1 if payload else 0)
            psql(
                "INSERT INTO trading.broker_read_snapshots "
                "(run_key,provider,account_ref,dataset,source_connector_key,row_count,payload_hash,payload) VALUES ("
                f"{sql_literal(run_key)},'Dhan',{sql_literal(account_ref)},{sql_literal(dataset)},"
                f"'dhan_live_connector',{row_count},{sql_literal(payload_hash)},{sql_literal(canonical)}::jsonb) "
                "ON CONFLICT (provider,account_ref,dataset,payload_hash) DO NOTHING"
            )
            total_rows += row_count
            summary["datasets"][dataset] = {"rows": row_count, "payload_hash": payload_hash}
        record_health("healthy", total_rows)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        try:
            record_health("failed", total_rows, error[:1000])
        except RuntimeError:
            pass
        summary.update({"status": "failed", "error": error})
        print(json.dumps(summary, indent=2))
        return 1
    summary["status"] = "completed"
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
