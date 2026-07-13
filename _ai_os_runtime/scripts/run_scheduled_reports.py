#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT", Path(__file__).resolve().parents[1]))
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT", RUNTIME_ROOT.parent))
API_URL = os.environ.get("AI_OS_API_URL", "http://127.0.0.1:8765").rstrip("/")
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
PSQL_BIN = os.environ.get("AI_OS_PSQL_BIN", "/opt/homebrew/opt/postgresql@15/bin/psql")
DOCKER_BIN = os.environ.get("AI_OS_DOCKER_BIN", "/usr/local/bin/docker")
IST = ZoneInfo("Asia/Kolkata")


REPORT_SOURCES: dict[str, list[tuple[str, str, str, int]]] = {
    "daily_market_brief": [
        ("trading-quant-risk", "signals", "Signals", 12),
        ("trading-quant-risk", "tradingview_tasks", "TradingView Work", 12),
        ("trading-quant-risk", "paper_monitors", "Paper Strategy Monitors", 12),
        ("trading-quant-risk", "alerts", "Open Trading Alerts", 12),
        ("trading-quant-risk", "risk_limits", "Risk Limits", 12),
        ("system-health", "source_freshness", "Data Freshness", 12),
        ("trading-quant-risk", "execution_control", "Execution Guard", 1),
    ],
    "daily_portfolio_brief": [
        ("portfolio-office", "portfolio_intelligence", "Portfolio Intelligence", 20),
        ("portfolio-office", "latest_positions", "Current Positions", 30),
        ("portfolio-office", "symbol_book_exposure", "Book Exposure", 20),
        ("portfolio-office", "cross_book_conflicts", "Cross-Book Conflicts", 20),
        ("portfolio-office", "position_gap_summary", "Position Readiness", 20),
    ],
    "daily_agent_activity": [
        ("office", "live_office_agent_activity", "Employee Activity", 36),
        ("office", "priority_tasks", "Priority Tasks", 24),
        ("office", "agent_messages", "Durable Handoffs", 20),
        ("office", "committee_room_items", "Committee Matters", 12),
        ("office", "execution_control", "Execution Guard", 1),
    ],
    "data_source_freshness": [
        ("system-health", "source_freshness", "Freshness Status", 40),
        ("system-health", "data_source_checks", "Recent Source Checks", 30),
        ("system-health", "source_freshness_scheduler_runs", "Scheduler Runs", 10),
        ("system-health", "connector_health_checks", "Connector Checks", 30),
    ],
    "provider_readiness": [
        ("system-health", "provider_readiness_board", "Provider Board", 50),
        ("system-health", "model_endpoints", "Model Endpoints", 30),
        ("system-health", "connector_health_checks", "Connector Health", 30),
        ("system-health", "browser_session_checks", "Browser Sessions", 20),
    ],
    "model_cost": [
        ("system-health", "model_routes", "Enabled Model Routes", 30),
        ("system-health", "model_endpoints", "Model Endpoint State", 30),
        ("system-health", "model_cost_summary", "Recorded Model Cost", 30),
    ],
    "full_system_status": [
        ("system-health", "metrics", "Control Plane", 30),
        ("system-health", "blueprint_summary", "Blueprint Coverage", 30),
        ("system-health", "data_sources", "Data Sources", 30),
        ("system-health", "provider_readiness_summary", "Provider Readiness", 30),
        ("system-health", "pipeline_readiness", "Pipeline Inventory", 30),
        ("system-health", "execution_control", "Execution Safety", 1),
    ],
    "weekly_risk": [
        ("trading-quant-risk", "risk_summary", "Risk Dashboard", 30),
        ("trading-quant-risk", "risk_limits", "Limit Checks", 40),
        ("trading-quant-risk", "alerts", "Open Alerts", 30),
        ("trading-quant-risk", "order_intents", "Order Intent Gates", 30),
        ("trading-quant-risk", "execution_control", "Execution Guard", 1),
    ],
    "weekly_research_digest": [
        ("research-ideas", "long_term_theses", "Long-Term Theses", 30),
        ("research-ideas", "coverage_summary", "Research Coverage", 30),
        ("research-ideas", "corporate_filings", "Corporate Filings", 30),
        ("research-ideas", "special_situations", "Special Situations", 30),
        ("research-ideas", "output_artifacts", "Research Outputs", 30),
    ],
    "monthly_client_report": [
        ("portfolio-office", "clients", "Clients", 20),
        ("portfolio-office", "client_accounts", "Accounts", 30),
        ("portfolio-office", "latest_positions", "Current Positions", 100),
        ("portfolio-office", "client_book_exposure", "Client Book Exposure", 60),
        ("portfolio-office", "p2cursor_reconciliation", "P2Cursor Reconciliation", 30),
        ("portfolio-office", "portfolio_intelligence", "Portfolio Intelligence", 30),
    ],
}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def psql_candidates() -> list[list[str]]:
    return [
        [PSQL_BIN, "-h", "127.0.0.1", "-p", POSTGRES_PORT, "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        [DOCKER_BIN, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
    ]


def psql_text(sql: str) -> str:
    errors: list[str] = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    for command in psql_candidates():
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((completed.stderr or completed.stdout).strip())
    raise RuntimeError(" | ".join(errors))


def psql_json(query: str) -> list[dict[str, Any]]:
    sql = f"SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM ({query}) rows;"
    return json.loads(psql_text(sql) or "[]")


def api_snapshot(endpoint: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if endpoint in cache:
        return cache[endpoint]
    request = urllib.request.Request(f"{API_URL}/api/{endpoint}/snapshot", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    cache[endpoint] = payload
    return payload


def period_key(cadence: str, now: datetime) -> str:
    if cadence == "daily":
        return now.strftime("%Y-%m-%d")
    if cadence == "weekly":
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"
    if cadence == "monthly":
        return now.strftime("%Y-%m")
    return now.strftime("%Y-%m-%dT%H%M%S")


def compact(value: object, max_length: int = 180) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, sort_keys=True, default=str)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= max_length else text[: max_length - 1] + "..."


def render_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No warehouse-backed rows were returned for this section."]
    lines: list[str] = []
    for row in rows:
        values = [(key.replace("_", " "), compact(value)) for key, value in row.items() if value not in (None, "", [], {})]
        primary = values[:6]
        lines.append("- " + " | ".join(f"**{key}:** {value}" for key, value in primary))
    return lines


def build_report(schedule: dict[str, Any], now: datetime) -> tuple[str, dict[str, Any], str]:
    cache: dict[str, dict[str, Any]] = {}
    source_snapshot: dict[str, Any] = {"endpoints": {}, "sections": {}}
    lines = [
        f"# {schedule['report_name']}",
        "",
        f"Generated: {now.isoformat(timespec='seconds')}",
        f"Owner: {schedule['owner_agent']}",
        f"Cadence: {schedule['cadence']}",
        "Status: Draft for review; no capital action, broker action, or external send is authorized.",
        "",
        "## Evidence Contract",
        "",
        "This report renders bounded live API rows only. Empty sections are shown as missing evidence, not filled with estimates. Timestamps are the source snapshot timestamps.",
        "",
    ]
    total_rows = 0
    for endpoint, key, title, limit in REPORT_SOURCES[schedule["report_key"]]:
        payload = api_snapshot(endpoint, cache)
        raw_rows = payload.get(key) or []
        rows = raw_rows[:limit] if isinstance(raw_rows, list) else []
        total_rows += len(rows)
        source_snapshot["endpoints"][endpoint] = {
            "generated_at": payload.get("generated_at"),
            "data_mode": payload.get("data_mode"),
            "issues": payload.get("issues", []),
        }
        source_snapshot["sections"][key] = {"available_rows": len(raw_rows) if isinstance(raw_rows, list) else 0, "rendered_rows": len(rows)}
        lines.extend([f"## {title}", "", *render_rows(rows), ""])
    if schedule.get("approval_required"):
        lines.extend(["## Approval Gate", "", "This client-facing draft must be reviewed and explicitly approved before any recommendation or external delivery.", ""])
    lines.extend(["## Next Review", "", "Review stale or missing sources, open risk/approval items, and any report section with no rows before relying on this output.", ""])
    summary = f"{schedule['report_name']} rendered {total_rows} rows from {len(cache)} scoped API snapshots."
    return "\n".join(lines), source_snapshot, summary


def schedule_rows(report_key: str = "") -> list[dict[str, Any]]:
    clause = f"WHERE report_key = {sql_literal(report_key)}" if report_key else "WHERE enabled = true"
    return psql_json(f"SELECT * FROM ops.v_report_schedule_status {clause} ORDER BY report_key")


def claim_run(schedule: dict[str, Any], period: str, force: bool, now: datetime) -> dict[str, Any] | None:
    effective_period = f"{period}-{now.strftime('%H%M%S')}" if force else period
    run_key = f"{schedule['report_key']}:{effective_period}"
    payload = psql_text(
        f"""
        WITH inserted AS (
            INSERT INTO ops.report_runs (schedule_id, run_key, period_key, status, started_at)
            VALUES ({int(schedule['id'])}, {sql_literal(run_key)}, {sql_literal(effective_period)}, 'running', now())
            ON CONFLICT DO NOTHING
            RETURNING id, run_key, period_key
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted;
        """
    )
    rows = json.loads(payload or "[]")
    return rows[0] if rows else None


def fail_run(run_id: int, error: Exception) -> None:
    psql_text(
        f"UPDATE ops.report_runs SET status='failed', error_message={sql_literal(f'{type(error).__name__}: {error}')}, finished_at=now(), updated_at=now() WHERE id={run_id};"
    )


def complete_run(schedule: dict[str, Any], run: dict[str, Any], note_path: str, source_snapshot: dict[str, Any], summary: str, content_hash: str) -> dict[str, Any]:
    approval_required = bool(schedule.get("approval_required"))
    task_status = "needs_review" if approval_required else "completed"
    approval_cte = """
        , approval AS (
            INSERT INTO agent.approvals (task_id, approval_type, title, owner_agent, risk_level, status, requested_action, rationale)
            SELECT id, 'client_report_send', 'Review and approve ' || title, owner_agent, 'high', 'pending',
                   jsonb_build_object('output_note_path', {note_path}, 'external_send_allowed', false),
                   'Draft report generation is complete. External delivery and recommendations remain blocked until human approval.'
            FROM task
            RETURNING id
        )
    """.format(note_path=sql_literal(note_path)) if approval_required else ", approval AS (SELECT NULL::BIGINT AS id WHERE false)"
    result = psql_text(
        f"""
        WITH task AS (
            INSERT INTO agent.tasks (title, objective, owner_agent, status, priority, approval_required, source_kind, source_ref, output_format, output_note_path, evidence)
            VALUES (
                {sql_literal(schedule['report_name'])}, {sql_literal(schedule['description'])}, {sql_literal(schedule['owner_agent'])},
                {sql_literal(task_status)}, 'medium', {str(approval_required).lower()}, 'scheduled_report', {sql_literal(run['run_key'])},
                'obsidian_markdown', {sql_literal(note_path)},
                {sql_jsonb([{'source': 'ops.report_runs', 'run_id': run['id']}, {'source': 'obsidian_note', 'path': note_path, 'sha256': content_hash}])}
            ) RETURNING id, title, owner_agent
        ), inbox AS (
            INSERT INTO agent.inbox_items (task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace)
            SELECT id, 'Review ' || title, {sql_literal(schedule['owner_agent'])}, {sql_literal('needs_review' if approval_required else 'new')}, 'medium',
                   'Review source freshness, exceptions, and evidence gaps before acting on this report.',
                   {sql_jsonb([{'source': 'ops.report_runs', 'run_id': run['id']}, {'source': 'obsidian_note', 'path': note_path}])}, 'reports'
            FROM task RETURNING id
        ), worker AS (
            INSERT INTO agent.worker_runs (task_id, agent_name, skill_key, run_mode, status, input_snapshot, output_summary, output_note_path, evidence, started_at, finished_at)
            SELECT id, {sql_literal(schedule['owner_agent'])}, {sql_literal(schedule.get('skill_key'))}, 'scheduled', 'completed',
                   {sql_jsonb(source_snapshot)}, {sql_literal(summary)}, {sql_literal(note_path)},
                   {sql_jsonb([{'source': 'ops.report_runs', 'run_id': run['id']}, {'source': 'obsidian_note', 'path': note_path, 'sha256': content_hash}])}, now(), now()
            FROM task RETURNING id, task_id
        )
        {approval_cte}, updated AS (
            UPDATE ops.report_runs
            SET status='completed', task_id=(SELECT id FROM task), worker_run_id=(SELECT id FROM worker),
                output_note_path={sql_literal(note_path)}, summary={sql_literal(summary)}, source_snapshot={sql_jsonb(source_snapshot)},
                evidence={sql_jsonb([{'source': 'obsidian_note', 'path': note_path, 'sha256': content_hash}, {'capital_action_allowed': False, 'live_execution_allowed': False}])},
                finished_at=now(), updated_at=now()
            WHERE id={int(run['id'])}
            RETURNING id, run_key, status, task_id, worker_run_id, output_note_path
        )
        SELECT json_build_object(
            'run', (SELECT row_to_json(updated) FROM updated),
            'inbox_id', (SELECT id FROM inbox),
            'approval_id', (SELECT id FROM approval)
        )::text;
        """
    )
    return json.loads(result)


def run_report(schedule: dict[str, Any], force: bool, now: datetime) -> dict[str, Any]:
    period = period_key(str(schedule["cadence"]), now)
    if not force and not schedule.get("due_now"):
        return {"report_key": schedule["report_key"], "status": "not_due", "period_key": period}
    run = claim_run(schedule, period, force, now)
    if not run:
        return {"report_key": schedule["report_key"], "status": "already_claimed", "period_key": period}
    output: Path | None = None
    temporary_output: Path | None = None
    try:
        content, source_snapshot, summary = build_report(schedule, now)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        folder = VAULT_ROOT / str(schedule["target_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{now.strftime('%Y-%m-%d')} {schedule['report_name']} {run['period_key']}.md".replace("/", "-")
        output = folder / filename
        temporary_output = output.with_name(f".{output.name}.tmp-{os.getpid()}")
        temporary_output.write_text(content, encoding="utf-8")
        os.replace(temporary_output, output)
        temporary_output = None
        relative_note = str(output.relative_to(VAULT_ROOT))
        completed = complete_run(schedule, run, relative_note, source_snapshot, summary, content_hash)
        return {"report_key": schedule["report_key"], "status": "completed", **completed}
    except Exception as error:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)
        if output is not None:
            output.unlink(missing_ok=True)
        fail_run(int(run["id"]), error)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate due AI OS reports from bounded live API snapshots.")
    parser.add_argument("--report-key", default="")
    parser.add_argument("--all", action="store_true", help="Process every enabled schedule.")
    parser.add_argument("--force", action="store_true", help="Generate a new run even when the current period is complete.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.all and not args.report_key:
        args.all = True
    now = datetime.now(IST)
    schedules = schedule_rows(args.report_key)
    if args.report_key and not schedules:
        raise ValueError(f"unknown report key: {args.report_key}")
    results: list[dict[str, Any]] = []
    for schedule in schedules:
        try:
            results.append(run_report(schedule, args.force, now))
        except (RuntimeError, OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            results.append({"report_key": schedule["report_key"], "status": "failed", "error": f"{type(error).__name__}: {error}"})
    payload = {"generated_at": now.isoformat(timespec="seconds"), "count": len(results), "results": results}
    print(json.dumps(payload, indent=2, default=str) if args.json else "\n".join(f"{row['report_key']}: {row['status']}" for row in results))
    return 1 if any(row["status"] == "failed" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
