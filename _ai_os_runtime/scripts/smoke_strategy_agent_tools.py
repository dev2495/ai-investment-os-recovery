#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = RUNTIME_ROOT / "mcp_server" / "ai_os_mcp_server.py"
MARKER = "CODEX-STRATEGY-MCP-SMOKE"


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
    WITH smoke_strategy_ids AS (
        SELECT id FROM strategy.strategy_candidates
        WHERE name ILIKE '%{MARKER}%'
           OR source_ref ILIKE '%{MARKER}%'
           OR structured_spec::text ILIKE '%{MARKER}%'
    ),
    smoke_idea_ids AS (
        SELECT id FROM strategy.generated_ideas
        WHERE idea_key ILIKE '%{MARKER}%'
           OR title ILIKE '%{MARKER}%'
           OR thesis ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
    ),
    smoke_intake_ids AS (
        SELECT id FROM strategy.strategy_intakes
        WHERE intake_key ILIKE '%{MARKER}%'
           OR intake_text ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
    ),
    deleted_validation AS (
        DELETE FROM strategy.validation_reviews
        WHERE strategy_id IN (SELECT id FROM smoke_strategy_ids)
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_optimization AS (
        DELETE FROM strategy.optimization_runs
        WHERE strategy_id IN (SELECT id FROM smoke_strategy_ids)
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_backtests AS (
        DELETE FROM strategy.backtest_runs
        WHERE strategy_id IN (SELECT id FROM smoke_strategy_ids)
           OR diagnostics::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_candidates AS (
        DELETE FROM strategy.strategy_candidates
        WHERE id IN (SELECT id FROM smoke_strategy_ids)
           OR generated_idea_id IN (SELECT id FROM smoke_idea_ids)
           OR intake_id IN (SELECT id FROM smoke_intake_ids)
        RETURNING id
    ),
    deleted_ideas AS (
        DELETE FROM strategy.generated_ideas
        WHERE id IN (SELECT id FROM smoke_idea_ids)
           OR intake_id IN (SELECT id FROM smoke_intake_ids)
        RETURNING id
    ),
    deleted_intakes AS (
        DELETE FROM strategy.strategy_intakes
        WHERE id IN (SELECT id FROM smoke_intake_ids)
        RETURNING id
    ),
    deleted_inbox AS (
        DELETE FROM agent.inbox_items
        WHERE title ILIKE '%{MARKER}%'
           OR recommended_action ILIKE '%{MARKER}%'
           OR evidence::text ILIKE '%{MARKER}%'
        RETURNING id
    ),
    deleted_tasks AS (
        DELETE FROM agent.tasks
        WHERE title ILIKE '%{MARKER}%'
           OR objective ILIKE '%{MARKER}%'
           OR source_ref ILIKE '%{MARKER}%'
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
        'validations', (SELECT count(*) FROM deleted_validation),
        'optimizations', (SELECT count(*) FROM deleted_optimization),
        'backtests', (SELECT count(*) FROM deleted_backtests),
        'candidates', (SELECT count(*) FROM deleted_candidates),
        'ideas', (SELECT count(*) FROM deleted_ideas),
        'intakes', (SELECT count(*) FROM deleted_intakes),
        'inbox', (SELECT count(*) FROM deleted_inbox),
        'tasks', (SELECT count(*) FROM deleted_tasks),
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
            "ai_os_create_strategy_intake",
            "ai_os_strategy_intakes",
            "ai_os_create_generated_strategy_idea",
            "ai_os_strategy_lab",
            "ai_os_queue_strategy_backtest",
            "ai_os_record_strategy_optimization",
            "ai_os_record_strategy_validation",
        }
        missing = sorted(required - tool_names)
        if missing:
            raise RuntimeError(f"Missing strategy MCP tools: {missing}")

        intake = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_strategy_intake",
                    "arguments": {
                        "intake_key": f"{MARKER}-intake",
                        "intake_text": f"{MARKER}: test strategy intake for NIFTY breakout after opening range.",
                        "strategy_name": f"{MARKER} opening range",
                        "strategy_family": "technical_intraday",
                        "symbols": ["NIFTY"],
                        "timeframe": "5m",
                        "intent_tags": [MARKER, "intraday"],
                        "requested_outputs": ["structured_spec", "backtest_request"],
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        idea = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_create_generated_strategy_idea",
                    "arguments": {
                        "idea_key": f"{MARKER}-idea",
                        "intake_key": intake["intake_key"],
                        "title": f"{MARKER} NIFTY ORB variant",
                        "symbols": ["NIFTY"],
                        "timeframe": "5m",
                        "thesis": f"{MARKER}: opening range breakouts may show directional continuation after volume confirmation.",
                        "entry_rules": {"after_minutes": 30, "breakout": "range_high"},
                        "exit_rules": {"stop": "range_mid", "time_exit": "15:15"},
                        "risk_rules": {"max_loss_r": 1},
                        "data_requirements": ["trading.ohlcv", "trading.ticks"],
                        "assumptions": ["transaction costs included"],
                        "invalidation_tests": ["walk_forward", "slippage_sensitivity"],
                        "candidate_key": f"{MARKER}-candidate",
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        backtest = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_queue_strategy_backtest",
                    "arguments": {
                        "strategy_id": idea["strategy_id"],
                        "data_start": "2026-01-01",
                        "data_end": "2026-06-30",
                        "universe": "NIFTY",
                        "timeframe": "5m",
                        "diagnostics": {"marker": MARKER, "lineage_required": True},
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        optimization = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_record_strategy_optimization",
                    "arguments": {
                        "strategy_id": idea["strategy_id"],
                        "backtest_run_id": backtest["id"],
                        "run_name": f"{MARKER} parameter grid",
                        "status": "done",
                        "objective": "maximize out-of-sample expectancy after costs",
                        "parameter_space": {"opening_minutes": [15, 30], "atr_filter": [1, 1.5]},
                        "diagnostics": {"marker": MARKER},
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        validation = parse_tool_content(
            call(
                "tools/call",
                {
                    "name": "ai_os_record_strategy_validation",
                    "arguments": {
                        "strategy_id": idea["strategy_id"],
                        "backtest_run_id": backtest["id"],
                        "optimization_run_id": optimization["id"],
                        "review_status": "done",
                        "decision": "needs_more_data",
                        "leakage_risk": "low",
                        "overfit_risk": "medium",
                        "transaction_cost_notes": f"{MARKER}: costs must be modeled.",
                        "required_fixes": ["add live spread model"],
                        "issues": [{"marker": MARKER, "issue": "smoke"}],
                        "evidence": [{"marker": MARKER}],
                    },
                },
            )
        )
        lab = parse_tool_content(call("tools/call", {"name": "ai_os_strategy_lab", "arguments": {"limit": 20}}))
        intakes = parse_tool_content(call("tools/call", {"name": "ai_os_strategy_intakes", "arguments": {"limit": 20}}))

        if not intake.get("id") or not idea.get("strategy_id") or not backtest.get("id"):
            raise RuntimeError("Strategy lifecycle create path failed")
        if validation.get("decision") != "needs_more_data":
            raise RuntimeError(f"Validation decision mismatch: {validation}")
        if not (lab or {}).get("strategy_candidates"):
            raise RuntimeError("Strategy lab did not return candidates")
        if not intakes:
            raise RuntimeError("Strategy intakes readback is empty")

        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        cleanup_after = cleanup_smoke_rows()

        print(json.dumps({
            "tool_count": len(tool_names),
            "intake_id": intake["id"],
            "idea_id": idea["id"],
            "strategy_id": idea["strategy_id"],
            "backtest_id": backtest["id"],
            "optimization_id": optimization["id"],
            "validation_id": validation["id"],
            "validation_decision": validation["decision"],
            "lab_candidate_rows": len((lab or {}).get("strategy_candidates", [])),
            "intake_rows": len(intakes or []),
            "cleanup_before": cleanup_before,
            "cleanup_after": cleanup_after,
        }, indent=2, sort_keys=True))
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
