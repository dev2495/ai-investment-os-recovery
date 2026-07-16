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
    required = {"ai_os_model_runtime_control", "ai_os_request_model_escalation"}
    assert required <= tool_names, f"missing model MCP tools: {sorted(required - tool_names)}"
    control = parse_content(call("tools/call", {
        "name": "ai_os_model_runtime_control", "arguments": {"limit": 100},
    }))
    route_names = {route["route_name"] for route in control["routes"]}
    required_routes = {
        "always_on_daily_driver",
        "charlie_munger_orchestration",
        "filing_analysis",
        "jarvis_intake",
        "local_embedding_retrieval",
        "multimodal_document_analysis",
        "strategy_generation",
    }
    assert required_routes <= route_names, f"missing governed routes: {sorted(required_routes - route_names)}"
    assert len(control["privacy_policies"]) == 4
    assert len(control["agent_assignments"]) > 0
    assert len(control["cost_caps"]) == len(control["agent_assignments"])
    assert control["raw_prompt_exposed"] is False
    assert control["autonomous_cloud_allowed"] is False
    assert control["capital_action_allowed"] is False
    assert control["live_execution_allowed"] is False

    process.stdin.close()
    process.terminate()
    process.wait(timeout=5)
    print(json.dumps({
        "status": "passed",
        "tool_count": len(tool_names),
        "model_runtime_tools": len(required),
        "routes": len(control["routes"]),
        "privacy_policies": len(control["privacy_policies"]),
        "agent_assignments": len(control["agent_assignments"]),
        "cost_caps": len(control["cost_caps"]),
        "raw_prompt_exposed": False,
        "autonomous_cloud_allowed": False,
        "execution_locked": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
