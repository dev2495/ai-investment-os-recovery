#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
OUTPUT_DIR = VAULT_ROOT / "ai memory" / "00 AI OS" / "Agent Outputs" / "Worker Runs"


def load_runtime_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = RUNTIME_ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


RUNTIME_ENV = load_runtime_env()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return cleaned[:80] or "agent-run"


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def sql_jsonb(value: Any) -> str:
    return sql_literal(json.dumps(value, default=str)) + "::jsonb"


def psql_text(sql: str) -> str:
    psql_bin = RUNTIME_ENV.get("AI_OS_PSQL_BIN") or "/opt/homebrew/opt/postgresql@15/bin/psql"
    db_host = RUNTIME_ENV.get("AI_OS_POSTGRES_HOST") or "127.0.0.1"
    db_port = RUNTIME_ENV.get("AI_OS_POSTGRES_PORT") or "54329"
    db_user = RUNTIME_ENV.get("AI_OS_POSTGRES_USER") or "ai_os"
    db_name = RUNTIME_ENV.get("AI_OS_POSTGRES_DB") or "ai_os"
    db_password = RUNTIME_ENV.get("AI_OS_POSTGRES_PASSWORD")

    if Path(psql_bin).exists() and db_password:
        command = [
            psql_bin,
            "-h",
            db_host,
            "-p",
            db_port,
            "-U",
            db_user,
            "-d",
            db_name,
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = db_password
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
    else:
        command = [
            "docker",
            "exec",
            "ai_os_postgres",
            "psql",
            "-U",
            "ai_os",
            "-d",
            "ai_os",
            "-q",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "psql command failed").strip()
        raise RuntimeError(detail)
    return completed.stdout.strip()


def psql_json(query: str) -> list[dict[str, Any]]:
    sql = f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows;"
    output = psql_text(sql)
    return json.loads(output or "[]")


def psql_one(query: str) -> dict[str, Any]:
    rows = psql_json(query)
    return rows[0] if rows else {}


def get_queue(limit: int, include_completed: bool) -> list[dict[str, Any]]:
    completed_filter = "" if include_completed else "AND coalesce(latest_worker_status, '') <> 'completed'"
    return psql_json(
        f"""
        SELECT *
        FROM agent.v_live_agent_worker_queue
        WHERE task_status IN ('queued','in_progress','needs_review')
          {completed_filter}
        ORDER BY
            CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
            CASE task_status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 ELSE 4 END,
            updated_at DESC
        LIMIT {int(limit)}
        """
    )


def profile_for(agent_name: str) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT agent_name, display_title, department_name, role_scope, persona,
               operating_style, mental_models, primary_skills, cost_policy
        FROM agent.v_active_agents
        WHERE agent_name = {sql_literal(agent_name)}
        """
    )


def skill_for(skill_key: str) -> dict[str, Any]:
    return psql_one(
        f"""
        SELECT skill_key, skill_name, skill_family, execution_mode, input_sources,
               output_targets, required_tools, risk_notes, primary_agents,
               assigned_agents
        FROM agent.v_agent_skill_matrix
        WHERE skill_key = {sql_literal(skill_key)}
        """
    )


def routed_agent_for(job: dict[str, Any], skill: dict[str, Any]) -> str:
    owner = str(job.get("owner_agent") or "Jarvis")
    if job.get("source_kind") == "agent_message":
        return owner
    primary_agents = skill.get("primary_agents") or []
    assigned_agents = skill.get("assigned_agents") or []
    if owner == "Jarvis":
        for candidate in primary_agents:
            if candidate and candidate != "Jarvis":
                return str(candidate)
        if primary_agents:
            return str(primary_agents[0])
        for candidate in assigned_agents:
            if candidate and candidate != "Jarvis":
                return str(candidate)
    return owner


def evaluate_task_provider_gates(task_id: object, actor: str = "Jarvis", context: str = "agent_worker_preflight") -> dict[str, Any]:
    try:
        numeric_task_id = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required for provider gate preflight") from exc
    return psql_one(
        f"""
        SELECT core.evaluate_task_provider_assignment_gates(
            {numeric_task_id},
            {sql_literal(actor)},
            {sql_literal(context)}
        ) AS result
        """
    ).get("result") or {}


def claim_task(task_id: object, actor: str = "Jarvis") -> dict[str, Any]:
    try:
        numeric_task_id = int(task_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("task_id is required for worker claim") from exc
    sql = f"""
    WITH claimed AS (
        UPDATE agent.tasks
        SET status = 'in_progress',
            evidence = coalesce(evidence, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
                'source', 'run_agent_worker_once.claim_task',
                'claimed_by', {sql_literal(actor)},
                'claimed_at', now()
            )),
            updated_at = now()
        WHERE id = {numeric_task_id}
          AND status = 'queued'
        RETURNING id, status, updated_at
    )
    SELECT coalesce((SELECT row_to_json(claimed) FROM claimed), '{{}}'::json)::text;
    """
    return json.loads(psql_text(sql) or "{}")


def context_for(skill_key: str, widget_key: str | None, job: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "clients": psql_one("SELECT count(*)::INT AS count FROM portfolio.clients WHERE active = true"),
        "inbox": psql_one("SELECT count(*)::INT AS open_items FROM agent.inbox_items WHERE status IN ('new','queued','open','needs_review')"),
        "widgets": psql_one("SELECT count(*)::INT AS active_widgets FROM ops.dashboard_widgets WHERE status = 'active'"),
    }
    if job and job.get("source_kind") == "agent_message":
        source_ref = str(job.get("source_ref") or "")
        if source_ref.isdigit():
            base["agent_message"] = psql_one(
                f"""
                SELECT id, thread_key, from_agent, to_agent, subject, body,
                       priority, status, processing_status, related_skill_key,
                       created_at
                FROM agent.agent_messages
                WHERE id = {int(source_ref)}
                LIMIT 1
                """
            )
        base["office"] = {
            "mailboxes": psql_one("SELECT count(*)::INT AS count FROM agent.mailboxes WHERE status = 'active'"),
            "unread_messages": psql_one("SELECT count(*)::INT AS count FROM agent.agent_messages WHERE status = 'unread'"),
            "pending_messages": psql_one("SELECT count(*)::INT AS count FROM agent.agent_messages WHERE processing_status IN ('pending','failed_retry')"),
        }
    if skill_key == "portfolio_snapshot_review" or widget_key == "portfolio_latest_positions":
        base["portfolio"] = psql_one(
            """
            SELECT count(*)::INT AS latest_positions,
                   coalesce(round(sum(market_value), 2), 0) AS market_value,
                   count(*) FILTER (WHERE market_price IS NULL)::INT AS missing_market_prices
            FROM portfolio.v_latest_positions
            """
        )
        base["top_positions"] = psql_json(
            """
            SELECT c.display_name, a.account_code, p.symbol, p.exchange,
                   p.quantity, p.market_value, p.unrealized_pnl
            FROM portfolio.v_latest_positions p
            JOIN portfolio.accounts a ON a.id = p.account_id
            LEFT JOIN portfolio.clients c ON c.id = a.client_id
            ORDER BY p.market_value DESC NULLS LAST
            LIMIT 5
            """
        )
    elif skill_key == "monitor_strategy_alerts" or widget_key == "market_signal_monitor":
        base["trading"] = {
            "signals": psql_one("SELECT count(*)::INT AS count FROM trading.signals"),
            "open_alerts": psql_one("SELECT count(*)::INT AS count FROM strategy.v_open_alerts"),
            "tradingview_tasks": psql_one("SELECT count(*)::INT AS queued FROM ops.tradingview_tasks WHERE status IN ('queued','open','in_progress')"),
        }
        base["recent_signals"] = psql_json(
            """
            SELECT ts, strategy, symbol, exchange, action, confidence, status
            FROM trading.v_recent_signals
            ORDER BY ts DESC
            LIMIT 5
            """
        )
    elif skill_key == "strategy_lab_review" or widget_key == "strategy_lab_queue":
        base["strategy"] = {
            "registry": psql_one("SELECT count(*)::INT AS count FROM strategy.strategy_registry"),
            "intakes": psql_one("SELECT count(*)::INT AS count FROM strategy.strategy_intakes"),
            "generated_ideas": psql_one("SELECT count(*)::INT AS count FROM strategy.generated_ideas"),
            "backtests": psql_one("SELECT count(*)::INT AS count FROM strategy.backtest_runs"),
            "optimizations": psql_one("SELECT count(*)::INT AS count FROM strategy.optimization_runs"),
            "validations": psql_one("SELECT count(*)::INT AS count FROM strategy.validation_reviews"),
        }
    elif skill_key in {"analyze_corporate_filing", "news_to_dashboard_alert"} or widget_key == "research_filings_inbox":
        base["research"] = {
            "feed_registry": psql_one("SELECT count(*)::INT AS count FROM research.feed_registry"),
            "corporate_filings": psql_one("SELECT count(*)::INT AS count FROM research.corporate_filings"),
            "filing_events": psql_one("SELECT count(*)::INT AS count FROM research.filing_events"),
            "news_items": psql_one("SELECT count(*)::INT AS count FROM market.news_items"),
            "social_items": psql_one("SELECT count(*)::INT AS count FROM market.social_items"),
        }
        base["research_hub"] = psql_json(
            """
            SELECT root_label, artifact_family, artifact_count
            FROM research.v_research_hub_summary
            ORDER BY artifact_count DESC
            LIMIT 6
            """
        )
    elif skill_key == "model_runtime_check" or widget_key == "model_runtime_status":
        base["runtime"] = {
            "enabled_model_routes": psql_one("SELECT count(*)::INT AS count FROM agent.model_routes WHERE enabled = true"),
            "enabled_tools": psql_one("SELECT count(*)::INT AS count FROM agent.tool_registry WHERE enabled = true"),
            "active_agents": psql_one("SELECT count(*)::INT AS count FROM agent.v_active_agents"),
            "active_skills": psql_one("SELECT count(*)::INT AS count FROM agent.skills WHERE status = 'active'"),
        }
    return base


def summary_for(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str]]:
    skill_key = str(skill.get("skill_key") or job.get("suggested_skill_key") or "refresh_dashboard_widget")
    lines: list[str] = []
    next_actions: list[str] = []

    if job.get("source_kind") == "agent_message":
        message = context.get("agent_message", {})
        lines.append(
            f"Processed internal message '{message.get('subject', job.get('title'))}' "
            f"from {message.get('from_agent', 'unknown')} to {message.get('to_agent', profile.get('agent_name'))}."
        )
        lines.append(
            f"Routed work to {profile.get('agent_name', job.get('owner_agent'))} using "
            f"{skill.get('skill_name', skill_key)} with priority {job.get('priority', 'medium')}."
        )
        if message.get("body"):
            lines.append(f"Message objective: {str(message.get('body'))[:280]}")
        next_actions.append("Reply to the sending agent if more evidence, approval, or a specialist handoff is required.")
        next_actions.append("Escalate to Charlie Munger before any capital allocation, client-facing, or broker-execution action.")
    elif skill_key == "portfolio_snapshot_review":
        portfolio = context.get("portfolio", {})
        lines.append(
            f"Portfolio snapshot sees {portfolio.get('latest_positions', 0)} latest positions across {context.get('clients', {}).get('count', 0)} active clients."
        )
        lines.append(f"Visible latest market value totals about INR {portfolio.get('market_value', 0)}.")
        if portfolio.get("missing_market_prices"):
            next_actions.append(f"Resolve {portfolio.get('missing_market_prices')} missing market prices before client-facing output.")
        next_actions.append("Review top exposures and stale holding theses with Charlie before any rebalance action.")
    elif skill_key == "monitor_strategy_alerts":
        trading = context.get("trading", {})
        lines.append(
            f"Trading monitor sees {trading.get('signals', {}).get('count', 0)} stored signals and {trading.get('open_alerts', {}).get('count', 0)} open alerts."
        )
        lines.append(f"TradingView queued/open tasks: {trading.get('tradingview_tasks', {}).get('queued', 0)}.")
        next_actions.append("Keep this as paper/review mode until Risk approves any live execution path.")
    elif skill_key == "strategy_lab_review":
        strategy = context.get("strategy", {})
        lines.append(
            "Strategy lab has "
            f"{strategy.get('registry', {}).get('count', 0)} registered strategies, "
            f"{strategy.get('generated_ideas', {}).get('count', 0)} generated ideas, "
            f"{strategy.get('backtests', {}).get('count', 0)} backtests, and "
            f"{strategy.get('validations', {}).get('count', 0)} validation reviews."
        )
        next_actions.append("Prioritize candidates that have data lineage, transaction costs, and validation coverage.")
    elif skill_key == "analyze_corporate_filing":
        research = context.get("research", {})
        lines.append(
            "Research inbox has "
            f"{research.get('corporate_filings', {}).get('count', 0)} corporate filings, "
            f"{research.get('filing_events', {}).get('count', 0)} filing events, "
            f"{research.get('news_items', {}).get('count', 0)} news items, and "
            f"{research.get('social_items', {}).get('count', 0)} social items."
        )
        next_actions.append("Next build should enable NSE/BSE collectors and filing PDF parsing before opinion generation.")
    elif skill_key == "model_runtime_check":
        runtime = context.get("runtime", {})
        lines.append(
            "Runtime registry has "
            f"{runtime.get('active_agents', {}).get('count', 0)} active agents, "
            f"{runtime.get('active_skills', {}).get('count', 0)} active skills, "
            f"{runtime.get('enabled_model_routes', {}).get('count', 0)} enabled model routes, and "
            f"{runtime.get('enabled_tools', {}).get('count', 0)} enabled tools."
        )
        next_actions.append("Run the worker on a schedule after manual run outputs are reviewed.")
    else:
        lines.append(f"{profile.get('agent_name', job.get('owner_agent'))} processed the dashboard job using {skill.get('skill_name', skill_key)}.")
        next_actions.append("Review the output and assign a more specific skill if needed.")

    lines.append(f"Agent stance: {profile.get('display_title') or profile.get('agent_name')} uses {profile.get('cost_policy', 'local_first')} routing.")
    return " ".join(lines), next_actions


def write_note(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any], summary: str, next_actions: list[str]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    filename = (
        f"{today} task-{job.get('task_id')} "
        f"{slugify(str(profile.get('agent_name') or job.get('owner_agent') or 'agent'))} "
        f"{slugify(str(job.get('suggested_skill_key') or 'skill'))}.md"
    )
    path = OUTPUT_DIR / filename
    evidence = [
        "agent.v_live_agent_worker_queue",
        "agent.v_active_agents",
        "agent.v_agent_skill_matrix",
        str(job.get("source_kind") or ""),
        str(job.get("source_ref") or ""),
    ]
    body = [
        f"# Agent Worker Run - Task {job.get('task_id')}",
        "",
        f"Date: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Agent: {profile.get('agent_name', job.get('owner_agent'))}",
        f"Role: {profile.get('display_title') or profile.get('role_scope') or 'Agent'}",
        f"Skill: {skill.get('skill_name', job.get('suggested_skill_key'))}",
        f"Widget: {job.get('widget_key')} - {job.get('widget_title')}",
        f"Task status before run: {job.get('task_status')}",
        "",
        "## Output",
        "",
        summary,
        "",
        "## Next Actions",
        "",
    ]
    body.extend([f"- {action}" for action in next_actions])
    body.extend(
        [
            "",
            "## Evidence",
            "",
        ]
    )
    body.extend([f"- {item}" for item in evidence if item])
    body.extend(
        [
            "",
            "## Bounded Context Snapshot",
            "",
            "```json",
            json.dumps(context, indent=2, default=str),
            "```",
            "",
        ]
    )
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def complete_job(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], context: dict[str, Any], summary: str, note_path: Path) -> dict[str, Any]:
    relative_note = str(note_path.relative_to(VAULT_ROOT))
    evidence = [
        {"source": "agent.v_live_agent_worker_queue", "task_id": job.get("task_id")},
        {"source": "agent.v_agent_skill_matrix", "skill_key": skill.get("skill_key")},
        {"source": "obsidian_note", "path": relative_note},
    ]
    input_snapshot = {
        "job": job,
        "agent": profile,
        "skill": skill,
        "context_counts": context,
    }
    sql = f"""
    WITH inserted_run AS (
        INSERT INTO agent.worker_runs (
            task_id, widget_id, agent_name, skill_key, run_mode, status,
            input_snapshot, output_summary, output_note_path, evidence,
            started_at, finished_at
        )
        VALUES (
            {int(job.get('task_id'))},
            {int(job.get('widget_id')) if job.get('widget_id') is not None else 'NULL'},
            {sql_literal(profile.get('agent_name') or job.get('owner_agent') or 'Jarvis')},
            {sql_literal(skill.get('skill_key') or job.get('suggested_skill_key'))},
            'manual_once',
            'completed',
            {sql_jsonb(input_snapshot)},
            {sql_literal(summary)},
            {sql_literal(relative_note)},
            {sql_jsonb(evidence)},
            now(),
            now()
        )
        RETURNING id, task_id, widget_id, agent_name, skill_key, status,
                  output_summary, output_note_path, evidence, started_at, finished_at
    ),
    updated_task AS (
        UPDATE agent.tasks
        SET status = 'needs_review',
            output_note_path = {sql_literal(relative_note)},
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('task_id'))}
        RETURNING id, status, output_note_path, updated_at
    ),
    updated_widget AS (
        UPDATE ops.dashboard_widgets
        SET last_refreshed_at = now(),
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('widget_id')) if job.get('widget_id') is not None else -1}
        RETURNING id, widget_key, last_refreshed_at
    ),
    updated_inbox AS (
        UPDATE agent.inbox_items
        SET status = 'needs_review',
            recommended_action = 'Review the completed agent worker output note, then decide whether to close, rerun, or escalate.',
            evidence = coalesce(evidence, '[]'::jsonb) || {sql_jsonb(evidence)},
            updated_at = now()
        WHERE id = {int(job.get('inbox_item_id')) if job.get('inbox_item_id') is not None else -1}
        RETURNING id, status, updated_at
    )
    SELECT json_build_object(
        'worker_run', (SELECT row_to_json(inserted_run) FROM inserted_run),
        'task', (SELECT row_to_json(updated_task) FROM updated_task),
        'widget', (SELECT row_to_json(updated_widget) FROM updated_widget),
        'inbox', (SELECT row_to_json(updated_inbox) FROM updated_inbox)
    )::text;
    """
    return json.loads(psql_text(sql))


def record_worker_failure(job: dict[str, Any], profile: dict[str, Any], skill: dict[str, Any], error: Exception) -> dict[str, Any]:
    message = str(error)[:1200]
    task_id = int(job.get("task_id"))
    inbox_id = int(job.get("inbox_item_id")) if job.get("inbox_item_id") is not None else -1
    evidence = [
        {"source": "run_agent_worker_once", "task_id": task_id, "status": "failed"},
        {"error": message},
    ]
    return psql_one(
        f"""
        WITH inserted_run AS (
            INSERT INTO agent.worker_runs (
                task_id, widget_id, agent_name, skill_key, run_mode, status,
                input_snapshot, output_summary, evidence, started_at, finished_at
            ) VALUES (
                {task_id},
                {int(job.get('widget_id')) if job.get('widget_id') is not None else 'NULL'},
                {sql_literal(profile.get('agent_name') or job.get('owner_agent') or 'Jarvis')},
                {sql_literal(skill.get('skill_key') or job.get('suggested_skill_key'))},
                'manual_once', 'failed', {sql_jsonb({'job': job})},
                {sql_literal('Worker failure: ' + message)}, {sql_jsonb(evidence)}, now(), now()
            )
            RETURNING id,task_id,agent_name,skill_key,status,output_summary,finished_at
        ),
        updated_task AS (
            UPDATE agent.tasks
            SET status='needs_review',
                evidence=coalesce(evidence,'[]'::jsonb) || {sql_jsonb(evidence)},
                updated_at=now()
            WHERE id={task_id}
            RETURNING id,status
        ),
        updated_inbox AS (
            UPDATE agent.inbox_items
            SET status='needs_review',
                recommended_action='Worker failed. Review the recorded error, fix the bounded cause, then requeue.',
                evidence=coalesce(evidence,'[]'::jsonb) || {sql_jsonb(evidence)},
                updated_at=now()
            WHERE id={inbox_id}
            RETURNING id
        )
        SELECT inserted_run.*,updated_task.status AS task_status
        FROM inserted_run CROSS JOIN updated_task
        """
    )


def run_once(limit: int, include_completed: bool) -> dict[str, Any]:
    jobs = get_queue(limit, include_completed)
    results: list[dict[str, Any]] = []
    for job in jobs:
        skill_key = str(job.get("suggested_skill_key") or "refresh_dashboard_widget")
        skill = skill_for(skill_key)
        if not skill:
            skill = skill_for("refresh_dashboard_widget")
        routed_agent = routed_agent_for(job, skill)
        profile = profile_for(routed_agent)
        if not profile:
            profile = profile_for(str(job.get("owner_agent") or "Jarvis"))
        if not profile:
            profile = profile_for("Jarvis")
        claim = claim_task(job.get("task_id"), str(profile.get("agent_name") or "Jarvis"))
        if not claim:
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": None,
                    "worker_run_id": None,
                    "task_status": job.get("task_status"),
                    "skipped": "not_queued_or_already_claimed",
                }
            )
            continue
        try:
            gate_result = evaluate_task_provider_gates(job.get("task_id"), str(profile.get("agent_name") or "Jarvis"))
            if gate_result.get("overall_status") != "passed":
                results.append(
                    {
                        "task_id": job.get("task_id"),
                        "widget_key": job.get("widget_key"),
                        "agent_name": profile.get("agent_name"),
                        "skill_key": skill.get("skill_key"),
                        "output_note_path": None,
                        "worker_run_id": None,
                        "task_status": gate_result.get("next_task_status"),
                        "provider_gate_status": gate_result.get("overall_status"),
                        "provider_gate_ids": gate_result.get("gate_ids"),
                    }
                )
                continue
            context = context_for(skill_key, job.get("widget_key"), job)
            summary, next_actions = summary_for(job, profile, skill, context)
            note_path = write_note(job, profile, skill, context, summary, next_actions)
            completed = complete_job(job, profile, skill, context, summary, note_path)
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": completed.get("worker_run", {}).get("output_note_path"),
                    "worker_run_id": completed.get("worker_run", {}).get("id"),
                    "task_status": completed.get("task", {}).get("status"),
                }
            )
        except Exception as exc:
            failed = record_worker_failure(job, profile, skill, exc)
            results.append(
                {
                    "task_id": job.get("task_id"),
                    "widget_key": job.get("widget_key"),
                    "agent_name": profile.get("agent_name"),
                    "skill_key": skill.get("skill_key"),
                    "output_note_path": None,
                    "worker_run_id": failed.get("id"),
                    "task_status": failed.get("task_status", "needs_review"),
                    "error": str(exc),
                }
            )
    return {
        "count": len(results),
        "results": results,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded AI OS agent worker pass.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_once(max(1, args.limit), args.include_completed)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"processed={result['count']}")
        for row in result["results"]:
            if row.get("skipped"):
                print(f"- task {row['task_id']} skipped: {row['skipped']}")
            elif row.get("provider_gate_status") and row.get("provider_gate_status") != "passed":
                print(f"- task {row['task_id']} {row['agent_name']} {row['skill_key']} blocked by provider gate {row['provider_gate_status']}")
            else:
                print(f"- task {row['task_id']} {row['agent_name']} {row['skill_key']} -> {row['output_note_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
