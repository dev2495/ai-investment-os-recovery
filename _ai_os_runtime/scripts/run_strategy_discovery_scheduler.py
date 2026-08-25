#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_trade_journal_strategy_mining import sql_text_array
from governed_pdf_runtime import governed_pdf_python


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)


def fetch_json(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def start_run(args: argparse.Namespace, command: list[str]) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_discovery_scheduler_runs (
                run_key, status, scheduler_interval_seconds, command,
                started_at, created_by
            )
            VALUES (
                {sql_literal(args.run_key)}, 'running', {int(args.interval_seconds)},
                {sql_text_array(command)}, now(), {sql_literal(args.actor)}
            )
            ON CONFLICT (run_key) DO UPDATE SET
                status = 'running',
                scheduler_interval_seconds = EXCLUDED.scheduler_interval_seconds,
                command = EXCLUDED.command,
                started_at = now(),
                finished_at = NULL,
                error_message = NULL,
                created_by = EXCLUDED.created_by
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=VAULT_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=max(30, timeout),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "error": f"TimeoutExpired after {max(30, timeout)} seconds",
            "stdout": str(exc.stdout or "")[:2000],
            "stderr": str(exc.stderr or "")[:2000],
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except OSError as exc:
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    payload: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": completed.stdout.strip()[:4000]}
    if completed.returncode != 0:
        payload["status"] = payload.get("status") or "failed"
        payload["error"] = (completed.stderr or completed.stdout or "command failed").strip()[:4000]
    payload["duration_ms"] = int((time.monotonic() - started) * 1000)
    return payload


def run_news_adapter(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        sys.executable,
        str(RUNTIME_ROOT / "scripts" / "ingest_market_news.py"),
        "--run-key",
        f"{args.run_key}_news",
        "--actor",
        "News Analyst",
        "--feed-limit",
        str(args.news_feed_limit),
        "--per-feed",
        str(args.news_per_feed),
        "--timeout",
        str(args.news_timeout),
    ]
    if args.news_feed_keys:
        command.extend(["--feed-keys", args.news_feed_keys])
    result = run_command(command, max(30, args.news_timeout * max(1, args.news_feed_limit) + 30))
    result["command"] = command
    return result


def run_filings_adapter(args: argparse.Namespace) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=max(0, int(args.filing_lookback_days)))
    command = [
        sys.executable,
        str(RUNTIME_ROOT / "scripts" / "collect_nse_bse_filings.py"),
        "--source",
        args.filing_source,
        "--from-date",
        date_from.isoformat(),
        "--to-date",
        today.isoformat(),
        "--limit",
        str(args.filing_limit),
        "--actor",
        "News Analyst",
    ]
    result = run_command(command, max(60, args.filing_timeout))
    result["command"] = command
    return result


def run_filing_extraction_adapter(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        governed_pdf_python(verify_import=True),
        str(RUNTIME_ROOT / "scripts" / "extract_filing_pdfs.py"),
        "--limit",
        str(args.filing_extraction_limit),
        "--actor",
        "Filings Analyst",
    ]
    result = run_command(command, max(60, args.filing_extraction_timeout))
    result["command"] = command
    return result


def run_discovery(args: argparse.Namespace) -> dict[str, Any]:
    discovery_run_key = f"{args.run_key}_discovery"
    command = [
        sys.executable,
        str(RUNTIME_ROOT / "scripts" / "run_strategy_discovery.py"),
        "--run-key",
        discovery_run_key,
        "--actor",
        "Strategy Discovery Agent",
        "--sources",
        args.sources,
        "--per-source-limit",
        str(args.per_source_limit),
        "--max-candidates",
        str(args.max_candidates),
        "--route-top",
        str(args.route_top),
    ]
    result = run_command(command, max(120, args.discovery_timeout))
    result["command"] = command
    result["discovery_run_key"] = discovery_run_key
    return result


def finish_run(run_id: int, args: argparse.Namespace, status: str, adapter_summary: dict[str, Any], discovery: dict[str, Any], error_message: str | None, duration_ms: int) -> None:
    discovery_run_key = discovery.get("discovery_run_key")
    discovery_id_rows = fetch_json(
        f"""
        SELECT id
        FROM strategy.strategy_discovery_runs
        WHERE run_key = {sql_literal(discovery_run_key)}
        LIMIT 1
        """
    ) if discovery_run_key else []
    discovery_run_id = discovery_id_rows[0]["id"] if discovery_id_rows else None
    summary = discovery.get("summary") or {}
    run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.strategy_discovery_scheduler_runs
            SET status = {sql_literal(status)},
                adapter_summary = {sql_jsonb(adapter_summary)},
                discovery_run_key = {sql_literal(discovery_run_key)},
                discovery_run_id = {int(discovery_run_id) if discovery_run_id else 'NULL'},
                discovered_count = {int(summary.get("discovered_count") or 0)},
                generated_idea_count = {int(summary.get("generated_idea_count") or 0)},
                optimizer_routed_count = {int(summary.get("optimizer_routed_count") or 0)},
                output_payload = {sql_jsonb(discovery)},
                error_message = {sql_literal(error_message) if error_message else 'NULL'},
                finished_at = now(),
                duration_ms = {int(duration_ms)},
                next_run_after = now() + make_interval(secs => {int(args.interval_seconds)})
            WHERE id = {int(run_id)}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )


def run_scheduler(args: argparse.Namespace) -> dict[str, Any]:
    command = [
        "run_strategy_discovery_scheduler.py",
        "--sources",
        args.sources,
        "--max-candidates",
        str(args.max_candidates),
        "--route-top",
        str(args.route_top),
    ]
    run = start_run(args, command)
    started = time.monotonic()
    adapters: dict[str, Any] = {
        "news": {"status": "skipped"},
        "filings": {"status": "skipped"},
        "filing_extraction": {"status": "skipped"},
        "x_twitter": {
            "status": "blocked_credentials",
            "next_action": "Connect authenticated browser/API credentials before social ingestion.",
        },
    }
    if not args.disable_news:
        adapters["news"] = run_news_adapter(args)
    if args.enable_filings:
        adapters["filings"] = run_filings_adapter(args)
    if args.enable_filing_extraction and adapters["filings"].get("status") != "failed":
        adapters["filing_extraction"] = run_filing_extraction_adapter(args)
    discovery = run_discovery(args)
    duration_ms = int((time.monotonic() - started) * 1000)
    errors: list[str] = []
    for name, payload in adapters.items():
        if payload.get("status") in {"failed", "completed_with_errors"}:
            detail = payload.get("error") or "; ".join(payload.get("errors") or []) or payload.get("status")
            errors.append(f"{name}: {detail}")
    if discovery.get("status") == "failed" or discovery.get("error"):
        errors.append(f"discovery: {discovery.get('error')}")
    discovery_completed = (discovery.get("summary") or {}).get("generated_idea_count") is not None
    status = "completed" if not errors and discovery_completed else ("completed_with_errors" if discovery_completed else "failed")
    finish_run(int(run["id"]), args, status, adapters, discovery, "; ".join(errors)[:4000] if errors else None, duration_ms)
    return {
        "run_key": args.run_key,
        "status": status,
        "adapter_summary": adapters,
        "discovery": {
            "run_key": discovery.get("discovery_run_key"),
            "summary": discovery.get("summary"),
            "artifact_path": discovery.get("artifact_path"),
            "status": discovery.get("status", "completed" if discovery.get("summary") else "unknown"),
        },
        "live_execution_allowed": False,
        "seed_data_allowed": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run source adapters and automatic strategy discovery as an auditable scheduler job.")
    parser.add_argument("--run-key", default=f"strategy_discovery_scheduler_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="AI OS Agent Daemon")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--disable-news", action="store_true")
    parser.add_argument("--news-feed-keys", default="")
    parser.add_argument("--news-feed-limit", type=int, default=12)
    parser.add_argument("--news-per-feed", type=int, default=6)
    parser.add_argument("--news-timeout", type=int, default=12)
    parser.add_argument("--enable-filings", action="store_true")
    parser.add_argument("--filing-source", default="all")
    parser.add_argument("--filing-lookback-days", type=int, default=1)
    parser.add_argument("--filing-limit", type=int, default=250)
    parser.add_argument("--filing-timeout", type=int, default=180)
    parser.add_argument("--enable-filing-extraction", action="store_true")
    parser.add_argument("--filing-extraction-limit", type=int, default=4)
    parser.add_argument("--filing-extraction-timeout", type=int, default=300)
    parser.add_argument("--sources", default="research,journals,signals,components")
    parser.add_argument("--per-source-limit", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=16)
    parser.add_argument("--route-top", type=int, default=1)
    parser.add_argument("--discovery-timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(run_scheduler(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
