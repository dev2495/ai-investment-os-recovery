#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from run_agent_worker_once import psql_json, psql_text, run_once, sql_jsonb, sql_literal

SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or SCRIPT_DIR.parent).resolve()
WORKLOAD_SCRIPT_DIR = RUNTIME_ROOT / "scripts"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from api import graph_control_plane  # noqa: E402


def record_daemon_heartbeat(
    *,
    instance_id: str,
    started_at: datetime,
    status: str,
    loop_interval_seconds: int,
    enabled_workloads: dict[str, bool],
    last_pass_summary: dict[str, Any],
    last_error: str | None = None,
) -> None:
    psql_text(
        f"""
        INSERT INTO core.runtime_daemon_heartbeats (
            daemon_key, instance_id, host_name, process_id, status,
            loop_interval_seconds, enabled_workloads, last_pass_summary,
            last_error, started_at, heartbeat_at, updated_at
        )
        VALUES (
            'agent_message_daemon', {sql_literal(instance_id)},
            {sql_literal(socket.gethostname())}, {os.getpid()}, {sql_literal(status)},
            {max(5, int(loop_interval_seconds))}, {sql_jsonb(enabled_workloads)},
            {sql_jsonb(last_pass_summary)},
            {sql_literal(last_error) if last_error else 'NULL'},
            {sql_literal(started_at.isoformat())}::timestamptz, now(), now()
        )
        ON CONFLICT (daemon_key) DO UPDATE SET
            instance_id = EXCLUDED.instance_id,
            host_name = EXCLUDED.host_name,
            process_id = EXCLUDED.process_id,
            status = EXCLUDED.status,
            loop_interval_seconds = EXCLUDED.loop_interval_seconds,
            enabled_workloads = EXCLUDED.enabled_workloads,
            last_pass_summary = EXCLUDED.last_pass_summary,
            last_error = EXCLUDED.last_error,
            started_at = CASE
                WHEN core.runtime_daemon_heartbeats.instance_id = EXCLUDED.instance_id
                THEN core.runtime_daemon_heartbeats.started_at
                ELSE EXCLUDED.started_at
            END,
            heartbeat_at = now(),
            updated_at = now();
        """
    )


def daemon_pass_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "generated_at": result.get("generated_at"),
        "messages_processed": result.get("messages_processed", 0),
        "worker_runs": (result.get("worker") or {}).get("count", 0),
    }
    for key in (
        "ohlcv_aggregation",
        "tradingview_quote_refresh",
        "source_freshness_scheduler",
        "strategy_discovery_scheduler",
        "market_news_ingestion",
        "research_hub_refresh",
        "workflow_schedule_materializer",
        "graph_control_plane",
    ):
        payload = result.get(key)
        if isinstance(payload, dict):
            summary[key] = {
                "status": payload.get("status", "unknown"),
                "run_key": payload.get("run_key"),
                "error": str(payload.get("error") or "")[:500] or None,
            }
    return summary


def sql_text_array(values: list[str]) -> str:
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::TEXT[]"


def pending_messages(limit: int) -> list[dict[str, Any]]:
    return psql_json(
        f"""
        SELECT message_id, thread_key, from_agent, to_agent, subject, body,
               priority, status, processing_status, related_skill_key,
               metadata, created_at
        FROM agent.v_message_daemon_backlog
        LIMIT {int(limit)}
        """
    )


def department_for(agent_name: str) -> str:
    rows = psql_json(
        f"""
        SELECT coalesce(nullif(department, ''), 'command') AS department
        FROM agent.profiles
        WHERE agent_name = {sql_literal(agent_name)}
        LIMIT 1
        """
    )
    return str(rows[0].get("department") or "command") if rows else "command"


def task_from_message(message: dict[str, Any]) -> dict[str, Any]:
    message_id = int(message["message_id"])
    to_agent = str(message.get("to_agent") or "Jarvis")
    from_agent = str(message.get("from_agent") or "Charlie Munger")
    subject = str(message.get("subject") or "Agent message")
    body = str(message.get("body") or "")
    priority = str(message.get("priority") or "medium")
    skill_key = str(message.get("related_skill_key") or (message.get("metadata") or {}).get("skill_key") or "route_user_request")
    workspace = department_for(to_agent)
    evidence = [
        {"source": "agent.agent_messages", "message_id": message_id},
        {"source": "agent.mailboxes", "to_agent": to_agent},
        {"source": "agent.skills", "skill_key": skill_key},
    ]
    metadata = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "thread_key": message.get("thread_key"),
        "message_created_at": message.get("created_at"),
        "related_skill_key": skill_key,
    }
    sql = f"""
    WITH msg AS (
        SELECT *
        FROM agent.agent_messages
        WHERE id = {message_id}
          AND generated_task_id IS NULL
        FOR UPDATE
    ), inserted_task AS (
        INSERT INTO agent.tasks (
            title, objective, owner_agent, status, priority, approval_required,
            source_kind, source_ref, output_format, evidence
        )
        SELECT
            {sql_literal('Message: ' + subject[:180])},
            {sql_literal(body)},
            {sql_literal(to_agent)},
            'queued',
            {sql_literal(priority)},
            false,
            'agent_message',
            {sql_literal(str(message_id))},
            'obsidian_note',
            {sql_jsonb(evidence)}
        FROM msg
        RETURNING id, title, objective, owner_agent, status, priority,
                  source_kind, source_ref, output_format, evidence,
                  created_at, updated_at
    ), inserted_inbox AS (
        INSERT INTO agent.inbox_items (
            task_id, title, owner_agent, status, priority,
            recommended_action, evidence, target_workspace
        )
        SELECT
            inserted_task.id,
            {sql_literal('Mailbox task: ' + subject[:170])},
            {sql_literal(to_agent)},
            'queued',
            {sql_literal(priority)},
            {sql_literal('Process the internal agent message, write an evidence-backed output note, then reply or escalate if needed.')},
            {sql_jsonb(evidence)},
            {sql_literal(workspace)}
        FROM inserted_task
        RETURNING id, task_id, title, owner_agent, status, priority,
                  recommended_action, target_workspace, created_at, updated_at
    ), updated_message AS (
        UPDATE agent.agent_messages
        SET processing_status = 'task_created',
            processed_at = now(),
            related_task_id = (SELECT id FROM inserted_task),
            generated_task_id = (SELECT id FROM inserted_task),
            generated_inbox_id = (SELECT id FROM inserted_inbox),
            metadata = coalesce(metadata, '{{}}'::jsonb) || {sql_jsonb(metadata)},
            error_message = NULL
        WHERE id = {message_id}
        RETURNING id, thread_key, from_agent, to_agent, subject, priority,
                  status, processing_status, generated_task_id,
                  generated_inbox_id, processed_at
    )
    SELECT json_build_object(
        'task', (SELECT row_to_json(inserted_task) FROM inserted_task),
        'inbox', (SELECT row_to_json(inserted_inbox) FROM inserted_inbox),
        'message', (SELECT row_to_json(updated_message) FROM updated_message)
    )::text;
    """
    output = psql_text(sql)
    payload = json.loads(output or "{}")
    if not payload.get("task"):
        return {"message_id": message_id, "status": "skipped"}
    return {
        "message_id": message_id,
        "status": "task_created",
        "task_id": payload["task"]["id"],
        "inbox_id": payload["inbox"]["id"],
        "to_agent": to_agent,
        "skill_key": skill_key,
    }


def mark_message_failed(message_id: int, error: Exception) -> None:
    psql_text(
        f"""
        UPDATE agent.agent_messages
        SET processing_status = 'failed_retry',
            error_message = {sql_literal(type(error).__name__ + ': ' + str(error))},
            processed_at = now()
        WHERE id = {int(message_id)}
        """
    )


def process_messages(limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for message in pending_messages(limit):
        try:
            results.append(task_from_message(message))
        except Exception as exc:  # noqa: BLE001
            mark_message_failed(int(message["message_id"]), exc)
            results.append({"message_id": message.get("message_id"), "status": "failed_retry", "error": str(exc)})
    return results


def psql_json_statement(sql: str) -> list[dict[str, Any]]:
    payload = json.loads(psql_text(sql) or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("graph statement did not return a JSON array")
    return payload


def advance_active_graph_runs(run_limit: int, max_steps: int) -> dict[str, Any]:
    runs = psql_json(
        f"""
        SELECT graph_run_id,graph_key,run_status,updated_at
        FROM agent.v_graph_run_status
        WHERE run_status IN ('queued','running','waiting_approval')
        ORDER BY updated_at,graph_run_id
        LIMIT {max(1, min(50, int(run_limit)))}
        """
    )
    advanced: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for run in runs:
        run_id = int(run["graph_run_id"])
        try:
            result = graph_control_plane.advance_graph_run(
                psql_json,
                psql_json_statement,
                {
                    "graph_run_id": run_id,
                    "actor": "Jarvis Agent Daemon",
                    "max_steps": max(1, min(100, int(max_steps))),
                },
            )
            advanced.append({
                "graph_run_id": run_id,
                "graph_key": result.get("graph_key") or run.get("graph_key"),
                "run_status": result.get("run_status"),
                "processed_steps": result.get("processed_steps", 0),
                "waiting": len(result.get("attention") or []),
            })
        except Exception as exc:  # noqa: BLE001
            errors.append({
                "graph_run_id": run_id,
                "graph_key": run.get("graph_key"),
                "error": type(exc).__name__ + ": " + str(exc),
            })
    return {
        "status": "failed" if errors else "success",
        "count": len(advanced),
        "active_runs_seen": len(runs),
        "runs": advanced,
        "errors": errors,
    }


def daemon_pass(
    message_limit: int,
    worker_limit: int,
    include_completed: bool = False,
    *,
    graph_control_enabled: bool = True,
    graph_run_limit: int = 20,
    graph_max_steps: int = 40,
) -> dict[str, Any]:
    message_results = process_messages(message_limit)
    worker_results = run_once(max(1, worker_limit), include_completed)
    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "messages_processed": len(message_results),
        "message_results": message_results,
        "worker": worker_results,
    }
    if graph_control_enabled:
        result["graph_control_plane"] = advance_active_graph_runs(
            graph_run_limit,
            graph_max_steps,
        )
    return result


def record_source_freshness_scheduler_run(
    *,
    run_key: str,
    status: str,
    interval_seconds: int,
    command: list[str],
    output_payload: dict[str, Any],
    error_message: str | None,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: int,
) -> dict[str, Any]:
    output = psql_text(
        f"""
        WITH inserted AS (
            INSERT INTO core.source_freshness_scheduler_runs (
                run_key, status, scheduler_interval_seconds, checked_count,
                fresh_count, stale_or_error_count, command, output_payload,
                error_message, started_at, finished_at, duration_ms,
                next_run_after, created_by
            )
            VALUES (
                {sql_literal(run_key)},
                {sql_literal(status)},
                {int(interval_seconds)},
                {int(output_payload.get('checked') or 0)},
                {int(output_payload.get('fresh') or 0)},
                {int(output_payload.get('stale_or_error') or 0)},
                {sql_text_array(command)},
                {sql_jsonb(output_payload)},
                {sql_literal(error_message) if error_message else 'NULL'},
                {sql_literal(started_at.isoformat())}::timestamptz,
                {sql_literal(finished_at.isoformat())}::timestamptz,
                {int(duration_ms)},
                {sql_literal(finished_at.isoformat())}::timestamptz + make_interval(secs => {int(interval_seconds)}),
                'AI OS Agent Daemon'
            )
            ON CONFLICT (run_key) DO UPDATE SET
                status = EXCLUDED.status,
                checked_count = EXCLUDED.checked_count,
                fresh_count = EXCLUDED.fresh_count,
                stale_or_error_count = EXCLUDED.stale_or_error_count,
                command = EXCLUDED.command,
                output_payload = EXCLUDED.output_payload,
                error_message = EXCLUDED.error_message,
                finished_at = EXCLUDED.finished_at,
                duration_ms = EXCLUDED.duration_ms,
                next_run_after = EXCLUDED.finished_at + make_interval(secs => EXCLUDED.scheduler_interval_seconds)
            RETURNING id, job_key, run_key, status, checked_count, fresh_count,
                      stale_or_error_count, started_at, finished_at, duration_ms,
                      next_run_after, error_message
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text
        FROM inserted
        """
    )
    rows = json.loads(output or "[]")
    return rows[0] if rows else {"run_key": run_key, "status": status}


def run_source_freshness_scheduler(interval_seconds: int, limit: int, timeout_seconds: int) -> dict[str, Any]:
    run_key = f"source-freshness-{datetime.now().astimezone().strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    command = [
        sys.executable,
        str(SCRIPT_DIR / "check_source_freshness.py"),
        "--actor",
        "AI OS Agent Daemon",
        "--limit",
        str(limit),
    ]
    started_at = datetime.now().astimezone()
    started_monotonic = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(30, timeout_seconds),
    )
    finished_at = datetime.now().astimezone()
    duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    output_payload: dict[str, Any] = {}
    error_message: str | None = None
    status = "success" if completed.returncode == 0 else "failed"
    if completed.stdout.strip():
        try:
            output_payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            output_payload = {"raw_stdout": completed.stdout.strip()[:4000]}
            if status == "success":
                status = "failed"
                error_message = "source freshness check returned non-JSON output"
    if completed.returncode != 0:
        error_message = (completed.stderr or completed.stdout or "source freshness scheduler failed").strip()[:4000]
    return record_source_freshness_scheduler_run(
        run_key=run_key,
        status=status,
        interval_seconds=interval_seconds,
        command=command,
        output_payload=output_payload,
        error_message=error_message,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
    )


def run_ohlcv_aggregation(timeout_seconds: int) -> dict[str, Any]:
    command = [sys.executable, str(SCRIPT_DIR / "aggregate_ticks_to_ohlcv.py")]
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(30, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "OHLCV aggregation failed").strip()[:4000]
    return payload


def run_tradingview_quote_refresh(timeout_seconds: int, symbol_limit: int) -> dict[str, Any]:
    quote_script = WORKLOAD_SCRIPT_DIR / "refresh_event_quotes.py"
    if not quote_script.is_file():
        return {"status": "failed", "error": f"required workload script is missing: {quote_script}"}
    command = [
        sys.executable,
        str(quote_script),
        "--limit",
        str(max(1, min(200, symbol_limit))),
    ]
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(30, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "TradingView quote refresh failed").strip()[:4000]
    return payload


def run_strategy_discovery_scheduler(interval_seconds: int, timeout_seconds: int) -> dict[str, Any]:
    scheduler_script = WORKLOAD_SCRIPT_DIR / "run_strategy_discovery_scheduler.py"
    if not scheduler_script.is_file():
        return {
            "status": "failed",
            "error": f"required workload script is missing: {scheduler_script}",
        }
    command = [
        sys.executable,
        str(scheduler_script),
        "--interval-seconds",
        str(max(300, interval_seconds)),
        "--max-candidates",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_MAX_CANDIDATES", "12"),
        "--route-top",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_ROUTE_TOP", "1"),
        "--news-feed-limit",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_NEWS_FEED_LIMIT", "12"),
        "--news-per-feed",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_NEWS_PER_FEED", "5"),
        "--filing-lookback-days",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_FILING_LOOKBACK_DAYS", "2"),
        "--filing-limit",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_FILING_LIMIT", "250"),
        "--filing-timeout",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_FILING_TIMEOUT_SECONDS", "300"),
        "--filing-extraction-limit",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_FILING_EXTRACTION_LIMIT", "4"),
        "--filing-extraction-timeout",
        os.environ.get("AI_OS_STRATEGY_DISCOVERY_FILING_EXTRACTION_TIMEOUT_SECONDS", "300"),
    ]
    if os.environ.get("AI_OS_STRATEGY_DISCOVERY_ENABLE_FILINGS", "0") == "1":
        command.append("--enable-filings")
    if os.environ.get("AI_OS_STRATEGY_DISCOVERY_ENABLE_FILING_EXTRACTION", "0") == "1":
        command.append("--enable-filing-extraction")
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(120, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "strategy discovery scheduler failed").strip()[:4000]
    return payload


def run_market_news_ingestion(timeout_seconds: int) -> dict[str, Any]:
    script = WORKLOAD_SCRIPT_DIR / "ingest_market_news.py"
    if not script.is_file():
        return {"status": "failed", "error": f"required workload script is missing: {script}"}
    command = [
        sys.executable,
        str(script),
        "--run-key",
        f"market_news_daemon_{datetime.now().astimezone().strftime('%Y%m%dT%H%M%S')}",
        "--actor",
        "News Analyst",
        "--feed-limit",
        os.environ.get("AI_OS_MARKET_NEWS_FEED_LIMIT", "12"),
        "--per-feed",
        os.environ.get("AI_OS_MARKET_NEWS_PER_FEED", "6"),
        "--timeout",
        os.environ.get("AI_OS_MARKET_NEWS_HTTP_TIMEOUT_SECONDS", "15"),
    ]
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(60, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "market news ingestion failed").strip()[:4000]
    return payload


def run_market_calendar_refresh(timeout_seconds: int) -> dict[str, Any]:
    script = WORKLOAD_SCRIPT_DIR / "collect_market_calendar.py"
    if not script.is_file():
        return {"status": "failed", "error": f"required workload script is missing: {script}"}
    completed = subprocess.run(
        [
            sys.executable, str(script),
            "--lookback-days", "1",
            "--lookahead-days", os.environ.get("AI_OS_MARKET_CALENDAR_LOOKAHEAD_DAYS", "45"),
            "--actor", "Corporate Events Analyst",
        ],
        cwd=str(RUNTIME_ROOT), text=True, capture_output=True, check=False,
        timeout=max(60, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "market calendar refresh failed").strip()[:4000]
    return payload


def run_research_hub_refresh(timeout_seconds: int) -> dict[str, Any]:
    script = WORKLOAD_SCRIPT_DIR / "inventory_ai_research_outputs.py"
    if not script.is_file():
        return {"status": "failed", "error": f"required workload script is missing: {script}"}
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(60, timeout_seconds),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    payload["status"] = "success" if completed.returncode == 0 else "failed"
    if completed.returncode != 0:
        payload["error"] = (
            completed.stderr or completed.stdout or "research hub refresh failed"
        ).strip()[:4000]
        return payload

    if os.environ.get("AI_OS_ENABLE_RESEARCH_HUB_VECTOR_REFRESH", "1") == "0":
        payload["vector_index"] = {"status": "disabled"}
        return payload

    vector_script = WORKLOAD_SCRIPT_DIR / "index_qdrant_documents.py"
    if not vector_script.is_file():
        payload["status"] = "failed"
        payload["vector_index"] = {
            "status": "failed",
            "error": f"required workload script is missing: {vector_script}",
        }
        return payload

    vector_completed = subprocess.run(
        [sys.executable, str(vector_script), "--incremental-research"],
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(
            300,
            int(os.environ.get("AI_OS_RESEARCH_HUB_VECTOR_TIMEOUT_SECONDS", "1800")),
        ),
    )
    vector_payload: dict[str, Any] = {}
    if vector_completed.stdout.strip():
        try:
            vector_payload = json.loads(vector_completed.stdout)
        except json.JSONDecodeError:
            vector_payload = {"raw_stdout": vector_completed.stdout.strip()[:4000]}
    vector_payload["status"] = "success" if vector_completed.returncode == 0 else "failed"
    if vector_completed.returncode != 0:
        vector_payload["error"] = (
            vector_completed.stderr
            or vector_completed.stdout
            or "incremental research vector refresh failed"
        ).strip()[:4000]
        payload["status"] = "failed"
        payload["error"] = vector_payload["error"]
    payload["vector_index"] = vector_payload
    return payload


def run_workflow_schedule_materializer(limit: int) -> dict[str, Any]:
    rows = psql_json(
        f"""
        SELECT agent.materialize_due_workflow_schedules(
            {max(1, min(50, int(limit)))},
            'Jarvis'
        ) AS result
        """
    )
    payload = rows[0].get("result") if rows else None
    if not isinstance(payload, dict):
        return {"status": "failed", "error": "workflow schedule materializer returned no result"}
    return {"status": "success", **payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="AI OS agent mailbox daemon.")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit.")
    parser.add_argument("--interval", type=int, default=30, help="Loop interval in seconds.")
    parser.add_argument("--message-limit", type=int, default=10)
    parser.add_argument("--worker-limit", type=int, default=5)
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--disable-graph-control", action="store_true", help="Disable automatic bounded graph progression.")
    parser.add_argument("--graph-run-limit", type=int, default=int(os.environ.get("AI_OS_GRAPH_RUN_LIMIT", "20")))
    parser.add_argument("--graph-max-steps", type=int, default=int(os.environ.get("AI_OS_GRAPH_MAX_STEPS", "40")))
    parser.add_argument("--disable-source-freshness", action="store_true", help="Disable scheduled source freshness checks.")
    parser.add_argument(
        "--source-freshness-interval",
        type=int,
        default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS", "900")),
        help="Source freshness scheduler interval in seconds.",
    )
    parser.add_argument("--source-freshness-limit", type=int, default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_LIMIT", "100")))
    parser.add_argument("--source-freshness-timeout", type=int, default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_TIMEOUT_SECONDS", "180")))
    parser.add_argument("--disable-ohlcv-aggregation", action="store_true", help="Disable scheduled tick-to-OHLCV aggregation.")
    parser.add_argument(
        "--ohlcv-aggregation-interval",
        type=int,
        default=int(os.environ.get("AI_OS_OHLCV_AGGREGATION_INTERVAL_SECONDS", "300")),
        help="Tick-to-OHLCV aggregation interval in seconds.",
    )
    parser.add_argument("--ohlcv-aggregation-timeout", type=int, default=int(os.environ.get("AI_OS_OHLCV_AGGREGATION_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--disable-tradingview-quote-refresh", action="store_true", help="Disable scheduled TradingView portfolio quote refresh.")
    parser.add_argument(
        "--tradingview-quote-refresh-interval",
        type=int,
        default=int(os.environ.get("AI_OS_TRADINGVIEW_QUOTE_REFRESH_INTERVAL_SECONDS", "900")),
        help="TradingView portfolio quote refresh interval in seconds.",
    )
    parser.add_argument("--tradingview-quote-refresh-timeout", type=int, default=int(os.environ.get("AI_OS_TRADINGVIEW_QUOTE_REFRESH_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--tradingview-quote-refresh-limit", type=int, default=int(os.environ.get("AI_OS_TRADINGVIEW_QUOTE_REFRESH_LIMIT", "100")))
    parser.add_argument("--disable-strategy-discovery-scheduler", action="store_true", help="Disable scheduled external-source strategy discovery.")
    parser.add_argument("--disable-market-news", action="store_true", help="Disable the dedicated market-news freshness workload.")
    parser.add_argument(
        "--market-news-interval",
        type=int,
        default=int(os.environ.get("AI_OS_MARKET_NEWS_INTERVAL_SECONDS", "900")),
        help="Dedicated market-news ingestion interval in seconds.",
    )
    parser.add_argument("--market-news-timeout", type=int, default=int(os.environ.get("AI_OS_MARKET_NEWS_TIMEOUT_SECONDS", "240")))
    parser.add_argument("--disable-market-calendar", action="store_true", help="Disable scheduled NSE results and holiday calendar refresh.")
    parser.add_argument("--market-calendar-interval", type=int, default=int(os.environ.get("AI_OS_MARKET_CALENDAR_INTERVAL_SECONDS", "21600")))
    parser.add_argument("--market-calendar-timeout", type=int, default=int(os.environ.get("AI_OS_MARKET_CALENDAR_TIMEOUT_SECONDS", "180")))
    parser.add_argument("--disable-research-hub-refresh", action="store_true", help="Disable scheduled AI research-output inventory refresh.")
    parser.add_argument(
        "--research-hub-refresh-interval",
        type=int,
        default=int(os.environ.get("AI_OS_RESEARCH_HUB_REFRESH_INTERVAL_SECONDS", "1800")),
        help="Research-output inventory refresh interval in seconds.",
    )
    parser.add_argument(
        "--research-hub-refresh-timeout",
        type=int,
        default=int(os.environ.get("AI_OS_RESEARCH_HUB_REFRESH_TIMEOUT_SECONDS", "600")),
    )
    parser.add_argument("--disable-workflow-scheduler", action="store_true", help="Disable governed agent workflow schedule materialization.")
    parser.add_argument(
        "--workflow-scheduler-interval",
        type=int,
        default=int(os.environ.get("AI_OS_WORKFLOW_SCHEDULER_INTERVAL_SECONDS", "60")),
        help="Agent workflow schedule materialization interval in seconds.",
    )
    parser.add_argument("--workflow-scheduler-limit", type=int, default=int(os.environ.get("AI_OS_WORKFLOW_SCHEDULER_LIMIT", "10")))
    parser.add_argument(
        "--strategy-discovery-scheduler-interval",
        type=int,
        default=int(os.environ.get("AI_OS_STRATEGY_DISCOVERY_SCHEDULER_INTERVAL_SECONDS", "3600")),
        help="External-source strategy discovery scheduler interval in seconds.",
    )
    parser.add_argument("--strategy-discovery-scheduler-timeout", type=int, default=int(os.environ.get("AI_OS_STRATEGY_DISCOVERY_SCHEDULER_TIMEOUT_SECONDS", "720")))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_freshness_enabled = not args.disable_source_freshness and os.environ.get("AI_OS_ENABLE_SOURCE_FRESHNESS_SCHEDULER", "1") != "0"
    source_freshness_interval = max(60, int(args.source_freshness_interval))
    ohlcv_aggregation_enabled = not args.disable_ohlcv_aggregation and os.environ.get("AI_OS_ENABLE_OHLCV_AGGREGATION", "1") != "0"
    ohlcv_aggregation_interval = max(60, int(args.ohlcv_aggregation_interval))
    tradingview_quote_refresh_enabled = not args.disable_tradingview_quote_refresh and os.environ.get("AI_OS_ENABLE_TRADINGVIEW_QUOTE_REFRESH", "0") != "0"
    tradingview_quote_refresh_interval = max(300, int(args.tradingview_quote_refresh_interval))
    strategy_discovery_enabled = not args.disable_strategy_discovery_scheduler and os.environ.get("AI_OS_ENABLE_STRATEGY_DISCOVERY_SCHEDULER", "1") != "0"
    strategy_discovery_interval = max(300, int(args.strategy_discovery_scheduler_interval))
    market_news_enabled = not args.disable_market_news and os.environ.get("AI_OS_ENABLE_MARKET_NEWS_SCHEDULER", "1") != "0"
    market_news_interval = max(300, int(args.market_news_interval))
    market_calendar_enabled = not args.disable_market_calendar and os.environ.get("AI_OS_ENABLE_MARKET_CALENDAR_SCHEDULER", "1") != "0"
    market_calendar_interval = max(1800, int(args.market_calendar_interval))
    research_hub_refresh_enabled = not args.disable_research_hub_refresh and os.environ.get("AI_OS_ENABLE_RESEARCH_HUB_REFRESH", "1") != "0"
    research_hub_refresh_interval = max(300, int(args.research_hub_refresh_interval))
    workflow_scheduler_enabled = not args.disable_workflow_scheduler and os.environ.get("AI_OS_ENABLE_WORKFLOW_SCHEDULER", "1") != "0"
    workflow_scheduler_interval = max(30, int(args.workflow_scheduler_interval))
    graph_control_enabled = not args.disable_graph_control and os.environ.get("AI_OS_ENABLE_GRAPH_CONTROL", "1") != "0"
    last_source_freshness_run = 0.0
    last_ohlcv_aggregation_run = 0.0
    last_tradingview_quote_refresh_run = 0.0
    last_strategy_discovery_run = 0.0
    last_market_news_run = 0.0
    last_market_calendar_run = 0.0
    last_research_hub_refresh_run = 0.0
    last_workflow_scheduler_run = 0.0
    daemon_started_at = datetime.now().astimezone()
    daemon_instance_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
    enabled_workloads = {
        "mailbox_worker": True,
        "source_freshness": source_freshness_enabled,
        "ohlcv_aggregation": ohlcv_aggregation_enabled,
        "tradingview_quote_refresh": tradingview_quote_refresh_enabled,
        "strategy_discovery": strategy_discovery_enabled,
        "market_news": market_news_enabled,
        "market_calendar": market_calendar_enabled,
        "research_hub_refresh": research_hub_refresh_enabled,
        "workflow_scheduler": workflow_scheduler_enabled,
        "graph_control": graph_control_enabled,
    }

    record_daemon_heartbeat(
        instance_id=daemon_instance_id,
        started_at=daemon_started_at,
        status="starting",
        loop_interval_seconds=args.interval,
        enabled_workloads=enabled_workloads,
        last_pass_summary={"phase": "starting"},
    )

    while True:
        try:
            result = daemon_pass(
                args.message_limit,
                args.worker_limit,
                args.include_completed,
                graph_control_enabled=graph_control_enabled,
                graph_run_limit=max(1, int(args.graph_run_limit)),
                graph_max_steps=max(1, int(args.graph_max_steps)),
            )
        except Exception as exc:  # noqa: BLE001
            result = {
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "messages_processed": 0,
                "message_results": [],
                "worker": {"count": 0, "status": "failed"},
                "graph_control_plane": {"status": "failed", "error": "daemon pass aborted before graph progression"},
                "daemon_pass": {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)},
            }
        if workflow_scheduler_enabled and (last_workflow_scheduler_run == 0.0 or time.monotonic() - last_workflow_scheduler_run >= workflow_scheduler_interval):
            try:
                result["workflow_schedule_materializer"] = run_workflow_schedule_materializer(max(1, int(args.workflow_scheduler_limit)))
            except Exception as exc:  # noqa: BLE001
                result["workflow_schedule_materializer"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_workflow_scheduler_run = time.monotonic()
        if market_news_enabled and (last_market_news_run == 0.0 or time.monotonic() - last_market_news_run >= market_news_interval):
            try:
                result["market_news_ingestion"] = run_market_news_ingestion(max(60, int(args.market_news_timeout)))
            except Exception as exc:  # noqa: BLE001
                result["market_news_ingestion"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_market_news_run = time.monotonic()
        if market_calendar_enabled and (last_market_calendar_run == 0.0 or time.monotonic() - last_market_calendar_run >= market_calendar_interval):
            try:
                result["market_calendar_refresh"] = run_market_calendar_refresh(max(60, int(args.market_calendar_timeout)))
            except Exception as exc:  # noqa: BLE001
                result["market_calendar_refresh"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_market_calendar_run = time.monotonic()
        if research_hub_refresh_enabled and (
            last_research_hub_refresh_run == 0.0
            or time.monotonic() - last_research_hub_refresh_run >= research_hub_refresh_interval
        ):
            try:
                result["research_hub_refresh"] = run_research_hub_refresh(
                    max(60, int(args.research_hub_refresh_timeout))
                )
            except Exception as exc:  # noqa: BLE001
                result["research_hub_refresh"] = {
                    "status": "failed",
                    "error": type(exc).__name__ + ": " + str(exc),
                }
            last_research_hub_refresh_run = time.monotonic()
        if ohlcv_aggregation_enabled and (last_ohlcv_aggregation_run == 0.0 or time.monotonic() - last_ohlcv_aggregation_run >= ohlcv_aggregation_interval):
            try:
                result["ohlcv_aggregation"] = run_ohlcv_aggregation(max(30, int(args.ohlcv_aggregation_timeout)))
            except Exception as exc:  # noqa: BLE001
                result["ohlcv_aggregation"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_ohlcv_aggregation_run = time.monotonic()
        if tradingview_quote_refresh_enabled and (last_tradingview_quote_refresh_run == 0.0 or time.monotonic() - last_tradingview_quote_refresh_run >= tradingview_quote_refresh_interval):
            try:
                result["tradingview_quote_refresh"] = run_tradingview_quote_refresh(
                    max(30, int(args.tradingview_quote_refresh_timeout)),
                    max(1, int(args.tradingview_quote_refresh_limit)),
                )
            except Exception as exc:  # noqa: BLE001
                result["tradingview_quote_refresh"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_tradingview_quote_refresh_run = time.monotonic()
        if source_freshness_enabled and (last_source_freshness_run == 0.0 or time.monotonic() - last_source_freshness_run >= source_freshness_interval):
            try:
                result["source_freshness_scheduler"] = run_source_freshness_scheduler(
                    source_freshness_interval,
                    max(1, int(args.source_freshness_limit)),
                    max(30, int(args.source_freshness_timeout)),
                )
            except Exception as exc:  # noqa: BLE001
                result["source_freshness_scheduler"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_source_freshness_run = time.monotonic()
        if strategy_discovery_enabled and (last_strategy_discovery_run == 0.0 or time.monotonic() - last_strategy_discovery_run >= strategy_discovery_interval):
            try:
                result["strategy_discovery_scheduler"] = run_strategy_discovery_scheduler(
                    strategy_discovery_interval,
                    max(120, int(args.strategy_discovery_scheduler_timeout)),
                )
            except Exception as exc:  # noqa: BLE001
                result["strategy_discovery_scheduler"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_strategy_discovery_run = time.monotonic()
        pass_summary = daemon_pass_summary(result)
        failures = [
            str(payload.get("error") or key)
            for key, payload in result.items()
            if isinstance(payload, dict) and payload.get("status") == "failed"
        ]
        try:
            record_daemon_heartbeat(
                instance_id=daemon_instance_id,
                started_at=daemon_started_at,
                status="degraded" if failures else "running",
                loop_interval_seconds=args.interval,
                enabled_workloads=enabled_workloads,
                last_pass_summary=pass_summary,
                last_error="; ".join(failures)[:2000] if failures else None,
            )
        except Exception as exc:  # noqa: BLE001
            result["daemon_heartbeat"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
        if args.json:
            print(json.dumps(result, indent=2, default=str), flush=True)
        else:
            scheduler = result.get("source_freshness_scheduler") or {}
            ohlcv_aggregation = result.get("ohlcv_aggregation") or {}
            tradingview_quotes = result.get("tradingview_quote_refresh") or {}
            strategy_discovery = result.get("strategy_discovery_scheduler") or {}
            market_news = result.get("market_news_ingestion") or {}
            market_calendar = result.get("market_calendar_refresh") or {}
            research_hub = result.get("research_hub_refresh") or {}
            workflow_scheduler = result.get("workflow_schedule_materializer") or {}
            graph_control = result.get("graph_control_plane") or {}
            print(
                f"{result['generated_at']} messages={result['messages_processed']} "
                f"worker_runs={result['worker']['count']} "
                f"ohlcv={ohlcv_aggregation.get('status', 'skipped')} "
                f"tradingview_quotes={tradingview_quotes.get('status', 'skipped')} "
                f"source_freshness={scheduler.get('status', 'skipped')} "
                f"market_news={market_news.get('status', 'skipped')} "
                f"market_calendar={market_calendar.get('status', 'skipped')} "
                f"research_hub={research_hub.get('status', 'skipped')} "
                f"workflow_scheduler={workflow_scheduler.get('status', 'skipped')} "
                f"graph_runs={graph_control.get('count', 0)}/{graph_control.get('active_runs_seen', 0)} "
                f"graph_status={graph_control.get('status', 'skipped')} "
                f"strategy_discovery={strategy_discovery.get('status', 'skipped')}",
                flush=True,
            )
        if args.once:
            return 0
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
