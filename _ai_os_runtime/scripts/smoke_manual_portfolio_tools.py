#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"
CLIENT_CODE = "CODEX-SMOKE"
ACCOUNT_CODE = "CODEX-SMOKE-A1"


def parse_tool_content(response: dict) -> object:
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return None
    return json.loads(content[0]["text"])


def cleanup_smoke_rows() -> dict:
    sql = f"""
    WITH account_ids AS (
        SELECT id
        FROM portfolio.accounts
        WHERE account_code = '{ACCOUNT_CODE}'
    ),
    client_ids AS (
        SELECT id
        FROM portfolio.clients
        WHERE client_code = '{CLIENT_CODE}'
    ),
    deleted_positions AS (
        DELETE FROM portfolio.positions
        WHERE account_id IN (SELECT id FROM account_ids)
        RETURNING id
    ),
    deleted_updates AS (
        DELETE FROM portfolio.manual_holding_updates
        WHERE client_code = '{CLIENT_CODE}'
        RETURNING id
    ),
    deleted_intake AS (
        DELETE FROM portfolio.manual_client_intake
        WHERE client_code = '{CLIENT_CODE}'
        RETURNING id
    ),
    deleted_inbox AS (
        DELETE FROM agent.inbox_items
        WHERE title ILIKE '%CODEX-SMOKE%'
           OR evidence::text ILIKE '%CODEX-SMOKE%'
        RETURNING id
    ),
    deleted_accounts AS (
        DELETE FROM portfolio.accounts
        WHERE id IN (SELECT id FROM account_ids)
        RETURNING id
    ),
    deleted_clients AS (
        DELETE FROM portfolio.clients
        WHERE id IN (SELECT id FROM client_ids)
        RETURNING id
    )
    SELECT json_build_object(
        'positions', (SELECT count(*) FROM deleted_positions),
        'updates', (SELECT count(*) FROM deleted_updates),
        'intake', (SELECT count(*) FROM deleted_intake),
        'inbox', (SELECT count(*) FROM deleted_inbox),
        'accounts', (SELECT count(*) FROM deleted_accounts),
        'clients', (SELECT count(*) FROM deleted_clients)
    )::text;
    """
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql",
        "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "{}")


def main() -> int:
    cleanup_before = cleanup_smoke_rows()
    process = subprocess.Popen(
        [str(SERVER_PATH)],
        cwd=RUNTIME_ROOT.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    request_id = 0

    def call(method: str, params: dict | None = None) -> dict:
        nonlocal request_id
        request_id += 1
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"MCP server exited without response. stderr={stderr}")
        response = json.loads(line)
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    try:
        call("initialize", {"protocolVersion": "2024-11-05"})
        upsert = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_upsert_client",
                    "arguments": {
                        "client_code": CLIENT_CODE,
                        "display_name": "Codex Smoke Client",
                        "risk_profile": "test",
                        "broker": "manual",
                        "account_code": ACCOUNT_CODE,
                        "account_name": "Codex Smoke Account",
                        "notes": "Temporary smoke-test row, cleaned up by script.",
                    },
                },
            )
        )
        staged = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_stage_holding_update",
                    "arguments": {
                        "client_code": CLIENT_CODE,
                        "account_code": ACCOUNT_CODE,
                        "symbol": "SMOKETEST",
                        "exchange": "NSE",
                        "instrument_type": "equity",
                        "quantity": 1,
                        "average_price": 10,
                        "market_price": 11,
                        "as_of": "2026-07-02T00:00:00+05:30",
                        "update_reason": "MCP smoke test",
                    },
                },
            )
        )
        applied = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_apply_holding_update",
                    "arguments": {"update_id": staged["id"], "applied_by": "Codex smoke"},
                },
            )
        )
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        process.terminate()
        process.wait(timeout=5)
        cleanup_after = cleanup_smoke_rows()

    print(
        json.dumps(
            {
                "cleanup_before": cleanup_before,
                "cleanup_after": cleanup_after,
                "upsert_client_id": upsert.get("client_id"),
                "upsert_account_id": upsert.get("account_id"),
                "staged_update_id": staged.get("id"),
                "applied_position_id": applied.get("position_id"),
                "applied_status": applied.get("status"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
