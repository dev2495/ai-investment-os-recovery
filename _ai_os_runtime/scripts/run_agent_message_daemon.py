#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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


def daemon_pass(message_limit: int, worker_limit: int, include_completed: bool = False) -> dict[str, Any]:
    message_results = process_messages(message_limit)
    worker_results = run_once(max(1, worker_limit), include_completed)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "messages_processed": len(message_results),
        "message_results": message_results,
        "worker": worker_results,
    }


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


def run_tradingview_cdp_check(timeout_seconds: int) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "check_tradingview_cdp.py"),
        "--actor",
        "AI OS Agent Daemon",
        "--timeout",
        str(max(1, timeout_seconds)),
    ]
    completed = subprocess.run(
        command,
        cwd=str(RUNTIME_ROOT),
        text=True,
        capture_output=True,
        check=False,
        timeout=max(10, timeout_seconds + 5),
    )
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:2000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "TradingView CDP check failed").strip()[:2000]
    return payload


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


def main() -> int:
    parser = argparse.ArgumentParser(description="AI OS agent mailbox daemon.")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit.")
    parser.add_argument("--interval", type=int, default=30, help="Loop interval in seconds.")
    parser.add_argument("--message-limit", type=int, default=10)
    parser.add_argument("--worker-limit", type=int, default=5)
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--disable-source-freshness", action="store_true", help="Disable scheduled source freshness checks.")
    parser.add_argument(
        "--source-freshness-interval",
        type=int,
        default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS", "900")),
        help="Source freshness scheduler interval in seconds.",
    )
    parser.add_argument("--source-freshness-limit", type=int, default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_LIMIT", "100")))
    parser.add_argument("--source-freshness-timeout", type=int, default=int(os.environ.get("AI_OS_SOURCE_FRESHNESS_TIMEOUT_SECONDS", "180")))
    parser.add_argument("--disable-tradingview-cdp-check", action="store_true", help="Disable scheduled TradingView CDP heartbeat checks.")
    parser.add_argument(
        "--tradingview-cdp-check-interval",
        type=int,
        default=int(os.environ.get("AI_OS_TRADINGVIEW_CDP_CHECK_INTERVAL_SECONDS", "60")),
        help="TradingView CDP heartbeat interval in seconds.",
    )
    parser.add_argument("--tradingview-cdp-check-timeout", type=int, default=int(os.environ.get("AI_OS_TRADINGVIEW_CDP_CHECK_TIMEOUT_SECONDS", "3")))
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
    tradingview_cdp_enabled = not args.disable_tradingview_cdp_check and os.environ.get("AI_OS_ENABLE_TRADINGVIEW_CDP_CHECKER", "1") != "0"
    tradingview_cdp_interval = max(30, int(args.tradingview_cdp_check_interval))
    ohlcv_aggregation_enabled = not args.disable_ohlcv_aggregation and os.environ.get("AI_OS_ENABLE_OHLCV_AGGREGATION", "1") != "0"
    ohlcv_aggregation_interval = max(60, int(args.ohlcv_aggregation_interval))
    tradingview_quote_refresh_enabled = not args.disable_tradingview_quote_refresh and os.environ.get("AI_OS_ENABLE_TRADINGVIEW_QUOTE_REFRESH", "1") != "0"
    tradingview_quote_refresh_interval = max(300, int(args.tradingview_quote_refresh_interval))
    strategy_discovery_enabled = not args.disable_strategy_discovery_scheduler and os.environ.get("AI_OS_ENABLE_STRATEGY_DISCOVERY_SCHEDULER", "1") != "0"
    strategy_discovery_interval = max(300, int(args.strategy_discovery_scheduler_interval))
    last_source_freshness_run = 0.0
    last_tradingview_cdp_run = 0.0
    last_ohlcv_aggregation_run = 0.0
    last_tradingview_quote_refresh_run = 0.0
    last_strategy_discovery_run = 0.0

    while True:
        result = daemon_pass(args.message_limit, args.worker_limit, args.include_completed)
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
        if tradingview_cdp_enabled and (last_tradingview_cdp_run == 0.0 or time.monotonic() - last_tradingview_cdp_run >= tradingview_cdp_interval):
            try:
                result["tradingview_cdp_check"] = run_tradingview_cdp_check(max(1, int(args.tradingview_cdp_check_timeout)))
            except Exception as exc:  # noqa: BLE001
                result["tradingview_cdp_check"] = {"status": "failed", "error": type(exc).__name__ + ": " + str(exc)}
            last_tradingview_cdp_run = time.monotonic()
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
        if args.json:
            print(json.dumps(result, indent=2, default=str), flush=True)
        else:
            scheduler = result.get("source_freshness_scheduler") or {}
            tradingview_cdp = result.get("tradingview_cdp_check") or {}
            ohlcv_aggregation = result.get("ohlcv_aggregation") or {}
            tradingview_quotes = result.get("tradingview_quote_refresh") or {}
            strategy_discovery = result.get("strategy_discovery_scheduler") or {}
            print(
                f"{result['generated_at']} messages={result['messages_processed']} "
                f"worker_runs={result['worker']['count']} "
                f"ohlcv={ohlcv_aggregation.get('status', 'skipped')} "
                f"tradingview_quotes={tradingview_quotes.get('status', 'skipped')} "
                f"tradingview_cdp={tradingview_cdp.get('status', 'skipped')} "
                f"source_freshness={scheduler.get('status', 'skipped')} "
                f"strategy_discovery={strategy_discovery.get('status', 'skipped')}",
                flush=True,
            )
        if args.once:
            return 0
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
