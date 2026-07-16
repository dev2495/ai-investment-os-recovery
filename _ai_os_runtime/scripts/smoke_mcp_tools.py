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
        "ai_os_blueprint_summary",
        "ai_os_blueprint_requirements",
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
        "ai_os_ingest_research_paper",
        "ai_os_create_paper_strategy_hypotheses",
        "ai_os_ingest_local_artifact",
        "ai_os_local_artifact_ingestions",
        "ai_os_legacy_source_resolution_board",
        "ai_os_workspace_terminal_config",
        "ai_os_update_workspace_terminal",
        "ai_os_update_workspace_widget",
        "ai_os_strategy_arsenal_control_board",
        "ai_os_integration_plugin_gateway",
        "ai_os_agent_model_assignment_completeness",
        "ai_os_upsert_integration_schema_mapping",
        "ai_os_validate_integration_schema_mapping",
        "ai_os_upsert_integration_job",
        "ai_os_run_integration_job",
        "ai_os_market_data_readiness",
        "ai_os_run_legacy_market_data_ingestion",
        "ai_os_runtime_daemon_health",
        "ai_os_agent_capability_readiness",
        "ai_os_fund_function_coverage",
        "ai_os_macro_source_readiness",
        "ai_os_ingest_public_macro_data",
        "ai_os_client_cash_ledger_control",
        "ai_os_client_accounting_run",
        "ai_os_client_report_delivery_control",
    }
    missing = sorted(required - tool_names)
    if missing:
        raise RuntimeError(f"Missing MCP tools: {missing}")

    checks = {
        "control_plane": parse_tool_content(call("tools/call", {"name": "ai_os_control_plane_snapshot", "arguments": {}})),
        "orchestration_stack": parse_tool_content(call("tools/call", {"name": "ai_os_orchestration_stack", "arguments": {}})),
        "blueprint_summary": parse_tool_content(call("tools/call", {"name": "ai_os_blueprint_summary", "arguments": {}})),
        "blueprint_requirements": parse_tool_content(
            call("tools/call", {"name": "ai_os_blueprint_requirements", "arguments": {"domain_key": "v10_16_dashboards_and_live_office", "limit": 5}})
        ),
        "client_summary": parse_tool_content(call("tools/call", {"name": "ai_os_client_3081282_summary", "arguments": {}})),
        "open_symbols": parse_tool_content(call("tools/call", {"name": "ai_os_client_3081282_symbol_dates", "arguments": {"open_only": True, "limit": 3}})),
        "research_sjs": parse_tool_content(call("tools/call", {"name": "ai_os_research_outputs", "arguments": {"query": "SJS", "limit": 3}})),
        "fincept": parse_tool_content(call("tools/call", {"name": "ai_os_fincept_component_review", "arguments": {}})),
        "fincept_install": parse_tool_content(call("tools/call", {"name": "ai_os_fincept_install_status", "arguments": {}})),
        "workspace_terminal": parse_tool_content(call("tools/call", {"name": "ai_os_workspace_terminal_config", "arguments": {}})),
        "strategy_arsenal": parse_tool_content(call("tools/call", {"name": "ai_os_strategy_arsenal_control_board", "arguments": {"limit": 10}})),
        "integration_gateway": parse_tool_content(call("tools/call", {"name": "ai_os_integration_plugin_gateway", "arguments": {"limit": 50}})),
        "model_assignment_completeness": parse_tool_content(call("tools/call", {"name": "ai_os_agent_model_assignment_completeness", "arguments": {"limit": 100}})),
        "market_data": parse_tool_content(call("tools/call", {"name": "ai_os_market_data_readiness", "arguments": {"limit": 10}})),
        "runtime_daemons": parse_tool_content(call("tools/call", {"name": "ai_os_runtime_daemon_health", "arguments": {}})),
        "agent_capabilities": parse_tool_content(
            call("tools/call", {"name": "ai_os_agent_capability_readiness", "arguments": {"limit": 100}})
        ),
        "fund_functions": parse_tool_content(
            call("tools/call", {"name": "ai_os_fund_function_coverage", "arguments": {"limit": 100}})
        ),
        "macro_sources": parse_tool_content(
            call("tools/call", {"name": "ai_os_macro_source_readiness", "arguments": {"limit": 20}})
        ),
        "local_artifacts": parse_tool_content(call("tools/call", {"name": "ai_os_local_artifact_ingestions", "arguments": {"limit": 20}})),
        "legacy_source_resolutions": parse_tool_content(call("tools/call", {"name": "ai_os_legacy_source_resolution_board", "arguments": {"limit": 100}})),
        "client_accounting": parse_tool_content(call("tools/call", {"name": "ai_os_client_accounting_run", "arguments": {"account_code": "p2cursor_account_2", "actor": "MCP smoke validation"}})),
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
        "blueprint_summary_metrics": len((checks["blueprint_summary"] or {}).get("summary", [])),
        "blueprint_domains": len((checks["blueprint_summary"] or {}).get("domains", [])),
        "blueprint_sync_runs": len((checks["blueprint_summary"] or {}).get("sync_runs", [])),
        "blueprint_requirement_rows": len(checks["blueprint_requirements"] or []),
        "client_summary_metrics": len((checks["client_summary"] or {}).get("summary", [])),
        "open_symbol_rows": len(checks["open_symbols"] or []),
        "research_rows": len(checks["research_sjs"] or []),
        "fincept_components": len((checks["fincept"] or {}).get("components", [])),
        "fincept_install_rows": len((checks["fincept_install"] or {}).get("install", [])),
        "fincept_installed_components": len((checks["fincept_install"] or {}).get("installed_components", [])),
        "workspace_layouts": len((checks["workspace_terminal"] or {}).get("config", [])),
        "workspace_widgets": len((checks["workspace_terminal"] or {}).get("widgets", [])),
        "strategy_arsenal_rows": len((checks["strategy_arsenal"] or {}).get("control_board", [])),
        "strategy_arsenal_summary_metrics": len((checks["strategy_arsenal"] or {}).get("summary", [])),
        "integration_plugin_rows": len((checks["integration_gateway"] or {}).get("plugins", [])),
        "integration_summary_metrics": len((checks["integration_gateway"] or {}).get("summary", [])),
        "integration_mapping_rows": len((checks["integration_gateway"] or {}).get("schema_mappings", [])),
        "integration_job_rows": len((checks["integration_gateway"] or {}).get("jobs", [])),
        "incomplete_model_assignments": len((checks["model_assignment_completeness"] or {}).get("incomplete_assignments", [])),
        "market_data_readiness_rows": len((checks["market_data"] or {}).get("readiness", [])),
        "market_data_contract_rows": len((checks["market_data"] or {}).get("contracts", [])),
        "market_data_import_rows": len((checks["market_data"] or {}).get("imports", [])),
        "market_bias_control_rows": len((checks["market_data"] or {}).get("bias_controls", [])),
        "runtime_daemon_rows": len((checks["runtime_daemons"] or {}).get("runtime_daemons", [])),
        "agent_capability_rows": len((checks["agent_capabilities"] or {}).get("employees", [])),
        "agent_missing_tool_rows": sum(
            not row.get("tools_ready") for row in (checks["agent_capabilities"] or {}).get("employees", [])
        ),
        "fund_function_rows": len((checks["fund_functions"] or {}).get("coverage", [])),
        "fund_function_uncovered_rows": sum(
            row.get("coverage_status") != "covered" for row in (checks["fund_functions"] or {}).get("coverage", [])
        ),
        "macro_source_rows": len((checks["macro_sources"] or {}).get("readiness", [])),
        "local_artifact_rows": len((checks["local_artifacts"] or {}).get("ingestions", [])),
        "local_artifact_summary_metrics": len((checks["local_artifacts"] or {}).get("summary", [])),
        "legacy_source_resolution_rows": len(checks["legacy_source_resolutions"] or []),
        "legacy_source_unresolved_rows": sum(
            row.get("readiness_status") in {"profiled_not_promoted", "partially_promoted"}
            for row in (checks["legacy_source_resolutions"] or [])
        ),
        "client_accounting_status": (checks["client_accounting"] or {}).get("status"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
