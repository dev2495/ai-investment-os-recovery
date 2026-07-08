#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"


def parse_tool_content(response: dict) -> object:
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return None
    return json.loads(content[0]["text"])


def main() -> int:
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

    call("initialize", {"protocolVersion": "2024-11-05"})
    tools = call("tools/list")["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    required = {
        "ai_os_control_plane_snapshot",
        "ai_os_orchestration_stack",
        "ai_os_upsert_client",
        "ai_os_stage_holding_update",
        "ai_os_apply_holding_update",
        "ai_os_client_3081282_summary",
        "ai_os_client_3081282_symbol_dates",
        "ai_os_client_3081282_trade_timeline",
        "ai_os_research_outputs",
        "ai_os_research_output_detail",
        "ai_os_fincept_component_review",
        "ai_os_fincept_install_status",
    }
    missing = sorted(required - tool_names)
    if missing:
        raise RuntimeError(f"Missing MCP tools: {missing}")

    checks = {
        "control_plane": parse_tool_content(call("tools/call", {"name": "ai_os_control_plane_snapshot", "arguments": {}})),
        "orchestration_stack": parse_tool_content(call("tools/call", {"name": "ai_os_orchestration_stack", "arguments": {}})),
        "client_summary": parse_tool_content(call("tools/call", {"name": "ai_os_client_3081282_summary", "arguments": {}})),
        "open_symbols": parse_tool_content(call("tools/call", {"name": "ai_os_client_3081282_symbol_dates", "arguments": {"open_only": True, "limit": 3}})),
        "research_sjs": parse_tool_content(call("tools/call", {"name": "ai_os_research_outputs", "arguments": {"query": "SJS", "limit": 3}})),
        "fincept": parse_tool_content(call("tools/call", {"name": "ai_os_fincept_component_review", "arguments": {}})),
        "fincept_install": parse_tool_content(call("tools/call", {"name": "ai_os_fincept_install_status", "arguments": {}})),
    }

    process.stdin.close()
    process.terminate()
    process.wait(timeout=5)

    summary = {
        "tool_count": len(tool_names),
        "control_plane_metrics": len((checks["control_plane"] or {}).get("metrics", [])),
        "control_plane_modules": len((checks["control_plane"] or {}).get("modules", [])),
        "control_plane_data_sources": len((checks["control_plane"] or {}).get("data_sources", [])),
        "control_plane_strategies": len((checks["control_plane"] or {}).get("strategies", [])),
        "control_plane_workflows": len((checks["control_plane"] or {}).get("workflows", [])),
        "orchestration_rows": len(checks["orchestration_stack"] or []),
        "client_summary_metrics": len((checks["client_summary"] or {}).get("summary", [])),
        "open_symbol_rows": len(checks["open_symbols"] or []),
        "research_rows": len(checks["research_sjs"] or []),
        "fincept_components": len((checks["fincept"] or {}).get("components", [])),
        "fincept_install_rows": len((checks["fincept_install"] or {}).get("install", [])),
        "fincept_installed_components": len((checks["fincept_install"] or {}).get("installed_components", [])),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
