#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = RUNTIME_ROOT.parent
OUTPUT_ROOT = VAULT_ROOT / "ai memory" / "00 AI OS" / "Agent Outputs"
ORCHESTRATOR_AGENTS = {"Charlie Munger"}
RUNTIME_AGENTS = {"Jarvis"}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb_literal(value: object) -> str:
    return sql_literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def run_psql_json(query: str) -> list[dict]:
    sql = f"COPY (SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json) FROM ({query}) result_rows) TO STDOUT;"
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql",
        "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr or completed.stdout)
        raise SystemExit(completed.returncode)
    return json.loads(completed.stdout.strip() or "[]")


def run_psql(sql: str) -> None:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr or completed.stdout)
        raise SystemExit(completed.returncode)


def slugify(value: str) -> str:
    output = []
    for char in value.lower():
        if char.isalnum():
            output.append(char)
        elif char in {" ", "-", "_"}:
            output.append("-")
    slug = "".join(output).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "agent"


def table_lines(rows: list[dict], columns: list[str]) -> list[str]:
    if not rows:
        return ["No rows."]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            values.append(str(value if value is not None else "").replace("\n", " ")[:180])
        lines.append("| " + " | ".join(values) + " |")
    return lines


def base_context() -> dict[str, list[dict]]:
    return {
        "active_agents": run_psql_json(
            "SELECT agent_name, department, default_model_route, permission_level FROM agent.v_active_agents ORDER BY department, agent_name"
        ),
        "open_tasks": run_psql_json(
            "SELECT id, title, owner_agent, status, priority, source_kind, source_ref FROM agent.v_open_tasks ORDER BY id"
        ),
        "algo_import_summary": run_psql_json("SELECT metric, value FROM core.v_algo_import_summary ORDER BY metric"),
        "p2cursor_summary": run_psql_json(
            "SELECT original_path, file_type, staged_row_count FROM client_data.v_p2cursor_source_summary ORDER BY file_type, original_path"
        ),
    }


def agent_context(agent_name: str) -> dict[str, Any]:
    context: dict[str, Any] = base_context()
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Data Steward"}:
        context["orchestration_stack"] = run_psql_json(
            "SELECT agent_name, stack_role, department, default_model_route, permission_level FROM agent.v_orchestration_stack"
        )
        context["component_inventory"] = run_psql_json(
            "SELECT source_system, component_name, file_count FROM core.v_source_component_inventory ORDER BY source_system, component_name"
        )
        context["source_tables"] = run_psql_json(
            "SELECT source_system, table_name, row_count, import_status FROM core.v_source_table_profiles ORDER BY source_system, table_name"
        )
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Portfolio Manager", "Risk Agent"}:
        context["latest_positions"] = run_psql_json(
            "SELECT symbol, exchange, quantity, average_price, market_price, market_value, unrealized_pnl FROM portfolio.v_latest_positions ORDER BY market_value DESC NULLS LAST LIMIT 25"
        )
        context["client_3081282_summary"] = run_psql_json(
            "SELECT metric, value FROM client_data.v_client_3081282_dashboard_summary ORDER BY metric"
        )
        context["client_3081282_open_symbols"] = run_psql_json(
            "SELECT symbol, instrument_type, net_quantity, last_buy_date, last_sell_date, last_trade_date FROM client_data.v_client_3081282_symbol_dates WHERE coalesce(net_quantity, 0) <> 0 ORDER BY last_trade_date DESC NULLS LAST, symbol LIMIT 25"
        )
        context["ideas_count"] = run_psql_json(
            "SELECT idea_type, count(*)::bigint AS count FROM research.ideas GROUP BY idea_type ORDER BY idea_type"
        )
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Trading Desk Agent", "Execution Safety Agent"}:
        context["recent_signals"] = run_psql_json(
            "SELECT ts, strategy, symbol, action, price, quantity, status FROM trading.v_recent_signals LIMIT 25"
        )
        context["open_alerts"] = run_psql_json(
            "SELECT ts, symbol, severity, status, title FROM strategy.v_open_alerts LIMIT 25"
        )
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Strategy Research Agent", "Model Validation Agent"}:
        context["backtests"] = run_psql_json(
            "SELECT strategy_id, run_status, universe, started_at, external_ref FROM strategy.backtest_runs ORDER BY started_at DESC NULLS LAST LIMIT 25"
        )
        context["requirements"] = run_psql_json(
            "SELECT source_system, package_manager, package_name, version_spec FROM core.v_source_requirements ORDER BY source_system, package_manager, package_name LIMIT 50"
        )
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Librarian Agent"}:
        context["obsidian_notes"] = run_psql_json(
            "SELECT note_type, count(*)::bigint AS count FROM knowledge.obsidian_notes GROUP BY note_type ORDER BY note_type"
        )
        context["ai_research_outputs"] = run_psql_json(
            "SELECT artifact_family, count(*)::bigint AS count FROM research.v_ai_output_inventory GROUP BY artifact_family ORDER BY count DESC, artifact_family"
        )
    if agent_name in ORCHESTRATOR_AGENTS | RUNTIME_AGENTS | {"Coding Lead Agent"}:
        context["fincept_components"] = run_psql_json(
            "SELECT sc.component_name, sc.reuse_mode, sc.priority, sc.status FROM core.source_components sc JOIN core.source_systems ss ON ss.id = sc.source_system_id WHERE ss.name = 'FinceptTerminal reference repo' ORDER BY sc.priority DESC, sc.component_name"
        )
    return context


def render_note(agent_name: str, context: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {agent_name} Agent Tick",
        "",
        f"Generated: {now}",
        "",
        "## Summary",
        "",
        f"- Active agents: {len(context.get('active_agents', []))}",
        f"- Open tasks: {len(context.get('open_tasks', []))}",
        "- Live execution remains disabled unless explicitly approved.",
        "",
        "## Open Tasks",
        "",
        *table_lines(context.get("open_tasks", []), ["id", "title", "owner_agent", "status", "priority"]),
        "",
        "## Algo Import Summary",
        "",
        *table_lines(context.get("algo_import_summary", []), ["metric", "value"]),
        "",
        "## P2Cursor Source Summary",
        "",
        *table_lines(context.get("p2cursor_summary", []), ["original_path", "file_type", "staged_row_count"]),
    ]
    if "component_inventory" in context:
        lines.extend(["", "## Orchestration Stack", "", *table_lines(context.get("orchestration_stack", []), ["agent_name", "stack_role", "department", "default_model_route", "permission_level"])])
        lines.extend(["", "## Component Inventory", "", *table_lines(context["component_inventory"], ["source_system", "component_name", "file_count"])])
    if "latest_positions" in context:
        lines.extend(["", "## Latest Positions", "", *table_lines(context["latest_positions"], ["symbol", "exchange", "quantity", "average_price", "market_price", "market_value", "unrealized_pnl"])])
    if "client_3081282_summary" in context:
        lines.extend(["", "## Client 3081282 Summary", "", *table_lines(context["client_3081282_summary"], ["metric", "value"])])
    if "client_3081282_open_symbols" in context:
        lines.extend(["", "## Client 3081282 Open Symbols", "", *table_lines(context["client_3081282_open_symbols"], ["symbol", "instrument_type", "net_quantity", "last_buy_date", "last_sell_date", "last_trade_date"])])
    if "recent_signals" in context:
        lines.extend(["", "## Recent Signals", "", *table_lines(context["recent_signals"], ["ts", "strategy", "symbol", "action", "price", "quantity", "status"])])
    if "backtests" in context:
        lines.extend(["", "## Backtest Imports", "", *table_lines(context["backtests"], ["strategy_id", "run_status", "universe", "started_at", "external_ref"])])
    if "obsidian_notes" in context:
        lines.extend(["", "## Obsidian Index", "", *table_lines(context["obsidian_notes"], ["note_type", "count"])])
    if "ai_research_outputs" in context:
        lines.extend(["", "## AI Research Outputs", "", *table_lines(context["ai_research_outputs"], ["artifact_family", "count"])])
    if "fincept_components" in context:
        lines.extend(["", "## Fincept Reference Components", "", *table_lines(context["fincept_components"], ["component_name", "reuse_mode", "priority", "status"])])
    lines.extend(["", "## Next Action", "", "- Route the open Data Steward task into p2cursor field mapping, then expose mapped client/portfolio safe views through Jarvis runtime for Charlie Munger and specialist agents."])
    return "\n".join(lines) + "\n"


def write_note(agent_name: str, body: str) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT_ROOT / f"{timestamp}-{slugify(agent_name)}-tick.md"
    path.write_text(body, encoding="utf-8")
    return path


def log_run(agent_name: str, note_path: Path, context: dict[str, Any]) -> None:
    relative_note = str(note_path.relative_to(VAULT_ROOT))
    metadata = {
        "open_tasks": len(context.get("open_tasks", [])),
        "active_agents": len(context.get("active_agents", [])),
        "output_note_path": relative_note,
    }
    run_psql(
        f"""
INSERT INTO agent.run_log (agent_name, task, status, finished_at, output_note_path, metadata)
VALUES (
    {sql_literal(agent_name)},
    'agent_tick',
    'completed',
    now(),
    {sql_literal(relative_note)},
    {jsonb_literal(metadata)}
);
"""
    )


def run_agent(agent_name: str) -> dict:
    context = agent_context(agent_name)
    body = render_note(agent_name, context)
    note_path = write_note(agent_name, body)
    log_run(agent_name, note_path, context)
    return {
        "agent_name": agent_name,
        "output_note_path": str(note_path),
        "open_tasks": len(context.get("open_tasks", [])),
        "active_agents": len(context.get("active_agents", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local AI OS agent tick.")
    parser.add_argument("--agent", default="Charlie Munger")
    args = parser.parse_args()
    print(json.dumps(run_agent(args.agent), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
