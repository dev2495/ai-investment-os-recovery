#!/usr/bin/env python3
"""Backfill a point-in-time sector basket through Zerodha's read-only candle API."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

from sync_zerodha_market_data import query_json, returned_id, sync_historical
from sync_zerodha_read_only import keychain_token, psql, sql_literal


def date_chunks(date_from: date, date_to: date, chunk_days: int) -> Iterator[tuple[date, date]]:
    cursor = date_from
    while cursor <= date_to:
        end = min(date_to, cursor + timedelta(days=chunk_days - 1))
        yield cursor, end
        cursor = end + timedelta(days=1)


def sector_members(taxonomy_key: str, as_of: date) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    nodes = query_json(
        "SELECT id,taxonomy_key,node_name FROM sector_intelligence.taxonomy_nodes "
        f"WHERE taxonomy_key={sql_literal(taxonomy_key)} AND valid_from<={sql_literal(as_of.isoformat())}::date "
        f"AND (valid_to IS NULL OR valid_to>={sql_literal(as_of.isoformat())}::date) LIMIT 2"
    )
    if len(nodes) != 1:
        raise ValueError("taxonomy_key must resolve to exactly one active sector node")
    members = query_json(
        "SELECT symbol.id AS symbol_id,symbol.symbol,symbol.exchange "
        "FROM sector_intelligence.instrument_membership_history membership "
        "JOIN trading.symbols symbol ON symbol.id=membership.symbol_id "
        f"WHERE membership.taxonomy_node_id={int(nodes[0]['id'])} "
        f"AND membership.valid_from<={sql_literal(as_of.isoformat())}::date "
        f"AND (membership.valid_to IS NULL OR membership.valid_to>={sql_literal(as_of.isoformat())}::date) "
        "AND symbol.instrument_type='equity' ORDER BY symbol.symbol"
    )
    if not members:
        raise ValueError("sector node has no active equity members")
    return nodes[0], members


def run_sync(args: argparse.Namespace) -> dict[str, Any]:
    date_from = date.fromisoformat(args.from_date)
    date_to = date.fromisoformat(args.to_date)
    if date_to < date_from:
        raise ValueError("to-date must not be before from-date")
    if args.chunk_days < 1 or args.chunk_days > 1900:
        raise ValueError("chunk-days must be between 1 and 1900")
    node, members = sector_members(args.taxonomy_key, date_to)
    windows = list(date_chunks(date_from, date_to, args.chunk_days))
    plan = {
        "taxonomy_key": args.taxonomy_key,
        "node_name": node["node_name"],
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "interval": args.interval,
        "member_count": len(members),
        "chunk_count_per_member": len(windows),
        "members": members,
        "paper_only": True,
        "broker_write_allowed": False,
    }
    if not args.persist:
        return {"status": "dry_run", **plan}

    api_key = os.environ.get("AI_OS_ZERODHA_API_KEY", "").strip()
    access_token = keychain_token()
    if not api_key or not access_token:
        raise RuntimeError("daily Zerodha login is required before sector history can be synchronized")
    run_key = args.run_key or (
        f"sector-history:{args.taxonomy_key}:{date_from}:{date_to}:"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_id = returned_id(
        psql(
            "INSERT INTO sector_intelligence.market_history_sync_runs "
            "(run_key,taxonomy_node_id,interval,date_from,date_to,member_count,requested_by) VALUES ("
            f"{sql_literal(run_key)},{int(node['id'])},{sql_literal(args.interval)},"
            f"{sql_literal(date_from.isoformat())}::date,{sql_literal(date_to.isoformat())}::date,"
            f"{len(members)},{sql_literal(args.actor)}) RETURNING id"
        ),
        "sector history run",
    )
    completed = failed = rows_written = 0
    results: list[dict[str, Any]] = []
    for member in members:
        item_id = returned_id(
            psql(
                "INSERT INTO sector_intelligence.market_history_sync_items "
                "(run_id,symbol_id,exchange,symbol,status,started_at) VALUES ("
                f"{run_id},{int(member['symbol_id'])},{sql_literal(member['exchange'])},"
                f"{sql_literal(member['symbol'])},'running',now()) RETURNING id"
            ),
            "sector history item",
        )
        item_rows = 0
        try:
            for chunk_from, chunk_to in windows:
                result = sync_historical(
                    api_key, access_token, str(member["exchange"]), str(member["symbol"]),
                    chunk_from.isoformat(), chunk_to.isoformat(), args.interval,
                )
                if int(result.get("symbol_id") or 0) != int(member["symbol_id"]):
                    raise RuntimeError(
                        f"canonical symbol mismatch for {member['exchange']}:{member['symbol']}: "
                        f"expected {member['symbol_id']}, wrote {result.get('symbol_id')}"
                    )
                item_rows += int(result.get("rows") or 0)
                if args.pause_seconds:
                    time.sleep(args.pause_seconds)
            completed += 1
            rows_written += item_rows
            psql(
                "UPDATE sector_intelligence.market_history_sync_items SET status='completed',"
                f"chunk_count={len(windows)},rows_written={item_rows},finished_at=now() WHERE id={item_id}"
            )
            results.append({"symbol": member["symbol"], "status": "completed", "rows": item_rows})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            message = f"{type(exc).__name__}: {exc}"[:1500]
            psql(
                "UPDATE sector_intelligence.market_history_sync_items SET status='failed',"
                f"error_message={sql_literal(message)},finished_at=now() WHERE id={item_id}"
            )
            results.append({"symbol": member["symbol"], "status": "failed", "error": message})
            if args.fail_fast:
                break
    status = "completed" if failed == 0 else "failed" if completed == 0 else "partial"
    psql(
        "UPDATE sector_intelligence.market_history_sync_runs SET "
        f"status={sql_literal(status)},completed_count={completed},failed_count={failed},"
        f"rows_written={rows_written},finished_at=now() WHERE id={run_id}"
    )
    return {"status": status, "run_id": run_id, "run_key": run_key, **plan, "results": results, "rows_written": rows_written}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-key", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--interval", default="day", choices=["day", "60minute", "15minute", "5minute"])
    parser.add_argument("--chunk-days", type=int, default=1500)
    parser.add_argument("--pause-seconds", type=float, default=0.4)
    parser.add_argument("--run-key")
    parser.add_argument("--actor", default="Sector Data Engineer")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()
    result = run_sync(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] in {"dry_run", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
