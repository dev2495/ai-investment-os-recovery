#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from run_agent_worker_once import psql_json, psql_text, sql_jsonb, sql_literal


SCOPE_KEY = "owner:devarsh"
API_BASE_URL = os.environ.get("AI_OS_API_BASE_URL", "http://127.0.0.1:8765").rstrip("/")


def scoped_statement(statement: str) -> list[dict[str, Any]]:
    output = psql_text(
        "BEGIN;\n"
        "SET LOCAL ROLE ai_os_research_runtime;\n"
        f"SET LOCAL ai_os.scope_key={sql_literal(SCOPE_KEY)};\n"
        f"{statement}\n"
        "COMMIT;"
    )
    return json.loads(output or "[]")


def post_refresh(source_id: int, timeout: int) -> dict[str, Any]:
    data = json.dumps({
        "followed_source_id": source_id,
        "per_feed": 8,
        "timeout": min(30, max(5, timeout)),
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE_URL}/api/research/following/refresh",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(60, timeout + 30)) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"refresh API returned HTTP {exc.code}: {body[:1200]}") from exc


def due_sources(limit: int) -> list[dict[str, Any]]:
    return psql_json(
        f"""
        SELECT source.id,source.source_key,source.current_version_id,source.next_refresh_at,
               version.source_url,version.adapter_key,version.requires_login,version.status version_status
        FROM research.followed_sources source
        JOIN research.followed_source_versions version
          ON version.scope_key=source.scope_key AND version.id=source.current_version_id
        WHERE source.scope_key={sql_literal(SCOPE_KEY)}
          AND source.status='active'
          AND version.status='active'
          AND version.requires_login=false
          AND version.adapter_key='rss_http'
          AND version.source_url ~* '^https://'
          AND (source.next_refresh_at IS NULL OR source.next_refresh_at<=now())
          AND NOT EXISTS (
              SELECT 1 FROM research.followed_source_refresh_runs running
              WHERE running.scope_key=source.scope_key
                AND running.followed_source_id=source.id
                AND running.status='running'
                AND running.started_at>=now()-interval '20 minutes'
          )
        ORDER BY source.priority DESC,source.next_refresh_at NULLS FIRST,source.id
        LIMIT {max(1, min(25, limit))}
        """
    )


def create_run(source: dict[str, Any]) -> dict[str, Any]:
    source_id = int(source["id"])
    version_id = int(source["current_version_id"])
    run_bucket = datetime.now(timezone.utc).strftime("%Y%m%dT%H")
    idempotency_key = f"following:{source_id}:{version_id}:{run_bucket}"
    rows = scoped_statement(
        f"""
        WITH inserted AS (
          INSERT INTO research.followed_source_refresh_runs
            (scope_key,run_key,idempotency_key,followed_source_id,source_version_id,
             trigger_kind,status,due_at,metadata,created_by)
          VALUES ({sql_literal(SCOPE_KEY)},{sql_literal(idempotency_key)},{sql_literal(idempotency_key)},
                  {source_id},{version_id},'scheduled_due','running',
                  {sql_literal(source.get('next_refresh_at'))}::timestamptz,
                  {sql_jsonb({'source_url': source.get('source_url'), 'adapter_key': 'rss_http', 'bounded': True, 'private_data_egress': False})},
                  'Research Source Monitor')
          ON CONFLICT (scope_key,idempotency_key) DO UPDATE
          SET run_key=research.followed_source_refresh_runs.run_key
          RETURNING *
        )
        SELECT jsonb_build_array(to_jsonb(inserted))::text FROM inserted;
        """
    )
    return rows[0] if rows else {}


def finish_run(run_id: int, *, status: str, items: int = 0, quarantined: int = 0, error: Exception | None = None) -> None:
    error_class = type(error).__name__ if error else None
    error_message = str(error)[:4000] if error else None
    scoped_statement(
        f"""
        WITH updated AS (
          UPDATE research.followed_source_refresh_runs
          SET status={sql_literal(status)},items_upserted={max(0, items)},
              quarantined_items={max(0, quarantined)},finished_at=now(),
              error_class={sql_literal(error_class)},error_message={sql_literal(error_message)},
              metadata=metadata || {sql_jsonb({'broker_write_allowed': False, 'external_write_allowed': False})}
          WHERE id={int(run_id)} AND scope_key={sql_literal(SCOPE_KEY)}
          RETURNING id
        )
        SELECT coalesce(jsonb_agg(to_jsonb(updated)),'[]'::jsonb)::text FROM updated;
        """
    )


def schedule_cooldown(source_id: int, minutes: int = 15) -> None:
    scoped_statement(
        f"""
        WITH updated AS (
          UPDATE research.followed_sources
          SET next_refresh_at=now()+make_interval(mins=>{max(15, min(1440, minutes))}),
              metadata=metadata || '{{"last_refresh_failed":true}}'::jsonb,
              updated_at=now()
          WHERE id={int(source_id)} AND scope_key={sql_literal(SCOPE_KEY)}
          RETURNING id
        )
        SELECT coalesce(jsonb_agg(to_jsonb(updated)),'[]'::jsonb)::text FROM updated;
        """
    )


def run_monitor(limit: int, timeout: int) -> dict[str, Any]:
    selected = due_sources(limit)
    results: list[dict[str, Any]] = []
    for source in selected:
        run = create_run(source)
        run_id = int(run.get("id") or 0)
        if run_id <= 0 or str(run.get("status")) != "running":
            results.append({"source_id": source.get("id"), "status": "skipped", "reason": "idempotent run already exists"})
            continue
        try:
            refreshed = post_refresh(int(source["id"]), timeout)
            items = int(refreshed.get("items_upserted") or 0)
            quarantined = int(refreshed.get("quarantined") or 0)
            finish_run(run_id, status="completed", items=items, quarantined=quarantined)
            results.append({
                "source_id": source["id"], "source_key": source.get("source_key"),
                "status": "completed", "items_upserted": items, "quarantined": quarantined,
            })
        except Exception as exc:  # noqa: BLE001
            finish_run(run_id, status="failed", error=exc)
            schedule_cooldown(int(source["id"]))
            results.append({
                "source_id": source["id"], "source_key": source.get("source_key"),
                "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:1200],
            })
    failed = sum(1 for item in results if item["status"] == "failed")
    return {
        "status": "degraded" if failed else "success",
        "sources_due": len(selected),
        "sources_processed": len(results),
        "sources_failed": failed,
        "results": results,
        "scope_key": SCOPE_KEY,
        "broker_write_allowed": False,
        "external_write_allowed": False,
        "private_data_egress": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded operator-approved Research Following monitor")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = run_monitor(args.limit, args.timeout)
    print(json.dumps(payload, indent=2 if args.json else None, default=str))
    return 1 if payload["status"] == "degraded" else 0


if __name__ == "__main__":
    raise SystemExit(main())
