#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"


def parse_content(response: dict) -> dict:
    content = (response.get("result") or {}).get("content") or []
    if not content:
        raise AssertionError("MCP tool returned no content")
    return json.loads(content[0]["text"])


def main() -> int:
    process = subprocess.Popen(
        [str(SERVER_PATH)], cwd=RUNTIME_ROOT.parent,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert process.stdin is not None and process.stdout is not None
    request_id = 0

    def call(method: str, params: dict | None = None) -> dict:
        nonlocal request_id
        request_id += 1
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
        if "error" in response:
            raise RuntimeError(response["error"])
        return response

    call("initialize", {"protocolVersion": "2024-11-05"})
    tools = call("tools/list")["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    required = {
        "ai_os_capital_allocation_control_board",
        "ai_os_propose_capital_policy",
        "ai_os_run_capital_allocation_analysis",
        "ai_os_capital_committee_decision",
    }
    assert required <= tool_names, f"missing capital MCP tools: {sorted(required - tool_names)}"
    board = parse_content(call("tools/call", {
        "name": "ai_os_capital_allocation_control_board", "arguments": {"limit": 120},
    }))
    assert len(board["control_board"]) == 18
    assert len({row["client_code"] for row in board["control_board"]}) == 3
    assert all(row["legacy_policy_status"] == "legacy_unverified" for row in board["control_board"])
    assert all(row["capital_action_allowed"] is False for row in board["control_board"])
    assert all(row["live_execution_allowed"] is False for row in board["control_board"])
    assert board["capital_action_allowed"] is False
    assert board["live_execution_allowed"] is False

    process.stdin.close()
    process.terminate()
    process.wait(timeout=5)
    print(json.dumps({
        "status": "passed",
        "tool_count": len(tool_names),
        "capital_tools": len(required),
        "control_rows": len(board["control_board"]),
        "clients": len({row["client_code"] for row in board["control_board"]}),
        "analysis_rows": len(board["analysis"]),
        "committee_rows": len(board["committee"]),
        "execution_locked": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
