#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"
MARKER = "CODEX-MCP-CONNECTORS-SMOKE"


def parse_tool_content(response: dict) -> object:
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return None
    return json.loads(content[0]["text"])


def run_sql_json(sql: str) -> dict:
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql",
        "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "{}")


def cleanup_smoke_rows() -> dict:
    sql = f"""
    WITH deleted_tv_tasks AS (
        DELETE FROM ops.tradingview_tasks
        WHERE task_title ILIKE '%{MARKER}%'
           OR instruction ILIKE '%{MARKER}%'
           OR source_ref ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
           OR metadata::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_trades AS (
        DELETE FROM trading.trade_activity_ledger
        WHERE source_ref ILIKE '%{MARKER}%'
           OR thesis ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
           OR payload::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_inbox AS (
        DELETE FROM agent.inbox_items
        WHERE title ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_audit AS (
        DELETE FROM agent.mcp_audit_log
        WHERE request_payload::text ILIKE '%{MARKER}%'
           OR result_payload::text ILIKE '%{MARKER}%'
           OR target_id ILIKE '%{MARKER}%'
        RETURNING id
    )
    SELECT json_build_object(
        'tradingview_tasks', (SELECT count(*) FROM deleted_tv_tasks),
        'trades', (SELECT count(*) FROM deleted_trades),
        'inbox', (SELECT count(*) FROM deleted_inbox),
        'audit', (SELECT count(*) FROM deleted_audit)
    )::text;
    """
    return run_sql_json(sql)


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
        tools = call("tools/list")["result"]["tools"]
        tool_names = {tool["name"] for tool in tools}
        required = {
            "ai_os_mcp_candidate_shortlist",
            "ai_os_create_tradingview_task",
            "ai_os_update_tradingview_task",
            "ai_os_tradingview_tasks",
            "ai_os_record_manual_trade",
            "ai_os_record_paper_trade",
            "ai_os_trade_activity",
            "ai_os_refresh_research_hub",
            "ai_os_research_hub_summary",
            "ai_os_run_public_data_source_check",
            "ai_os_data_source_checks",
        }
        missing = sorted(required - tool_names)
        if missing:
            raise RuntimeError(f"Missing MCP tools: {missing}")

        shortlist = parse_tool_content(
            call("tools/call", {"name": "ai_os_mcp_candidate_shortlist", "arguments": {"category": "tradingview"}})
        )
        tv_task = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_tradingview_task",
                    "arguments": {
                        "task_title": f"{MARKER} NIFTY straddle chart",
                        "task_type": "options_chart",
                        "symbols": ["NIFTY", "NIFTYCE", "NIFTYPE"],
                        "exchange": "NSE",
                        "timeframe": "5m",
                        "chart_layout": "4-pane options straddle",
                        "instruction": f"{MARKER}: open four charts and inspect straddle behavior.",
                        "source_ref": MARKER,
                        "evidence": [{"marker": MARKER}],
                        "metadata": {"marker": MARKER},
                    },
                },
            )
        )
        tv_update = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_update_tradingview_task",
                    "arguments": {
                        "task_id": tv_task["id"],
                        "status": "done",
                        "result_summary": f"{MARKER} task update smoke passed.",
                        "evidence": [{"marker": MARKER, "phase": "updated"}],
                        "metadata": {"marker": MARKER, "phase": "updated"},
                    },
                },
            )
        )
        manual_trade = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_record_manual_trade",
                    "arguments": {
                        "symbol": "SMOKE",
                        "side": "BUY",
                        "quantity": 1,
                        "price": 100,
                        "strategy_key": "manual_smoke",
                        "source_ref": MARKER,
                        "thesis": f"{MARKER} manual trade smoke.",
                        "tags": [MARKER, "manual"],
                        "evidence": [{"marker": MARKER}],
                        "payload": {"marker": MARKER},
                    },
                },
            )
        )
        paper_trade = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_record_paper_trade",
                    "arguments": {
                        "symbol": "SMOKE",
                        "side": "SELL",
                        "quantity": 1,
                        "price": 101,
                        "strategy_key": "paper_smoke",
                        "source_ref": MARKER,
                        "thesis": f"{MARKER} paper trade smoke.",
                        "tags": [MARKER, "paper"],
                        "realized_pnl": 1,
                        "evidence": [{"marker": MARKER}],
                        "payload": {"marker": MARKER},
                    },
                },
            )
        )
        trade_rows = parse_tool_content(
            call("tools/call", {"name": "ai_os_trade_activity", "arguments": {"symbol": "SMOKE", "limit": 10}})
        )
        research_summary = parse_tool_content(call("tools/call", {"name": "ai_os_research_hub_summary", "arguments": {}}))
        data_check = parse_tool_content(call("tools/call", {"name": "ai_os_data_source_checks", "arguments": {"limit": 10}}))
        capabilities = parse_tool_content(call("tools/call", {"name": "ai_os_mcp_capabilities", "arguments": {}}))

        if not shortlist:
            raise RuntimeError("TradingView MCP shortlist is empty")
        if tv_update.get("status") != "done":
            raise RuntimeError(f"TradingView task did not update to done: {tv_update}")
        if not manual_trade.get("id") or not paper_trade.get("id"):
            raise RuntimeError("Trade activity rows were not created")
        if len((trade_rows or {}).get("rows", [])) < 2:
            raise RuntimeError("Trade activity readback returned fewer than two smoke rows")
        if not (research_summary or {}).get("summary"):
            raise RuntimeError("Research hub summary is empty")
        if not data_check:
            raise RuntimeError("Data source checks readback is empty")

        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        cleanup_after = cleanup_smoke_rows()

        summary = {
            "tool_count": len(tool_names),
            "capability_mcp_tools": len((capabilities or {}).get("mcp_tools", [])),
            "shortlist_rows": len(shortlist or []),
            "tradingview_task_status": tv_update.get("status"),
            "manual_trade_id": manual_trade.get("id"),
            "paper_trade_id": paper_trade.get("id"),
            "trade_rows": len((trade_rows or {}).get("rows", [])),
            "research_summary_rows": len((research_summary or {}).get("summary", [])),
            "data_check_rows": len(data_check or []),
            "cleanup_before": cleanup_before,
            "cleanup_after": cleanup_after,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
