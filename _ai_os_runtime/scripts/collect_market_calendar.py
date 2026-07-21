#!/usr/bin/env python3
"""Collect the official NSE corporate event calendar into the local warehouse."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from sync_zerodha_read_only import psql, sql_literal


PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-event-calendar"
API_URL = "https://www.nseindia.com/api/event-calendar?"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def classify_event(purpose: str) -> str:
    normalized = purpose.lower()
    if "financial result" in normalized:
        return "financial_results"
    if "dividend" in normalized:
        return "dividend"
    if "buyback" in normalized:
        return "buyback"
    if "fund raising" in normalized or "fundraising" in normalized:
        return "fund_raising"
    if "bonus" in normalized:
        return "bonus"
    if "split" in normalized:
        return "stock_split"
    return "board_meeting"


def fetch_events(date_from: date, date_to: date, timeout: int) -> tuple[list[dict], int, str]:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    page_request = urllib.request.Request(
        PAGE_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    with opener.open(page_request, timeout=timeout):
        pass
    query = urllib.parse.urlencode(
        {
            "index": "equities",
            "from_date": date_from.strftime("%d-%m-%Y"),
            "to_date": date_to.strftime("%d-%m-%Y"),
        }
    )
    target = API_URL + query
    request = urllib.request.Request(
        target,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Referer": PAGE_URL,
        },
    )
    with opener.open(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200))
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("NSE event calendar did not return a list")
    return [row for row in payload if isinstance(row, dict)], status, target


def insert_events(events: list[dict], target_url: str) -> int:
    inserted = 0
    seen: set[tuple[str, str, str, str]] = set()
    for offset in range(0, len(events), 75):
        values: list[str] = []
        for item in events[offset : offset + 75]:
            symbol = str(item.get("symbol") or "").strip().upper()
            company = str(item.get("company") or "").strip()
            purpose = str(item.get("purpose") or "Board meeting").strip()
            description = str(item.get("bm_desc") or purpose).strip()
            raw_date = str(item.get("date") or "").strip()
            if not symbol or not raw_date:
                continue
            event_date = datetime.strptime(raw_date, "%d-%b-%Y").date().isoformat()
            event_type = classify_event(purpose)
            unique_key = (symbol, event_date, event_type, purpose)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            payload = json.dumps(item, sort_keys=True, separators=(",", ":"))
            values.append(
                "("
                f"'nse_event_calendar','NSE',{sql_literal(symbol)},{sql_literal(company)},"
                f"{sql_literal(event_date)}::date,{sql_literal(event_type)},"
                f"{sql_literal(purpose)},{sql_literal(description)},{sql_literal(target_url)},"
                f"{sql_literal(payload)}::jsonb"
                ")"
            )
        if not values:
            continue
        psql(
            "INSERT INTO market.corporate_event_calendar "
            "(source_key,exchange,symbol,company_name,event_date,event_type,purpose,description,source_url,source_payload) VALUES "
            + ",".join(values)
            + " ON CONFLICT (source_key,exchange,symbol,event_date,event_type,purpose) DO UPDATE SET "
              "company_name=EXCLUDED.company_name,description=EXCLUDED.description,"
              "source_url=EXCLUDED.source_url,source_payload=EXCLUDED.source_payload,captured_at=now()"
        )
        inserted += len(values)
    return inserted


def collect(date_from: date, date_to: date, timeout: int, actor: str) -> dict:
    run_key = "nse-calendar-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    psql(
        "INSERT INTO market.market_calendar_runs "
        "(run_key,source_key,status,date_from,date_to,target_url,created_by) VALUES ("
        f"{sql_literal(run_key)},'nse_event_calendar','started',"
        f"{sql_literal(date_from.isoformat())}::date,{sql_literal(date_to.isoformat())}::date,"
        f"{sql_literal(PAGE_URL)},{sql_literal(actor)})"
    )
    try:
        events, http_status, target_url = fetch_events(date_from, date_to, timeout)
        rows_upserted = insert_events(events, target_url)
        sample = json.dumps(events[:3], sort_keys=True, separators=(",", ":"))
        psql(
            "UPDATE market.market_calendar_runs SET status='completed',"
            f"rows_seen={len(events)},rows_upserted={rows_upserted},http_status={http_status},"
            f"target_url={sql_literal(target_url)},sample_payload={sql_literal(sample)}::jsonb,"
            "finished_at=now() "
            f"WHERE run_key={sql_literal(run_key)}"
        )
        psql(
            "INSERT INTO core.connector_health_checks "
            "(target_kind,target_key,check_name,check_type,status,rows_seen,sample_payload,checked_by) VALUES "
            "('data_source_connector','nse_filings_connector','nse_event_calendar','live_read','healthy',"
            f"{len(events)},'{{\"execution_allowed\":false}}'::jsonb,{sql_literal(actor)})"
        )
        return {
            "status": "completed",
            "run_key": run_key,
            "rows_seen": len(events),
            "rows_upserted": rows_upserted,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "source_url": target_url,
            "execution_allowed": False,
        }
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:1000]
        psql(
            "UPDATE market.market_calendar_runs SET status='failed',"
            f"error_message={sql_literal(error)},finished_at=now() WHERE run_key={sql_literal(run_key)}"
        )
        return {"status": "failed", "run_key": run_key, "error": error, "execution_allowed": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--lookback-days", type=int, default=1)
    parser.add_argument("--lookahead-days", type=int, default=45)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--actor", default="Corporate Events Analyst")
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    date_from = date.fromisoformat(args.from_date) if args.from_date else today - timedelta(days=max(0, args.lookback_days))
    date_to = date.fromisoformat(args.to_date) if args.to_date else today + timedelta(days=max(1, args.lookahead_days))
    if date_to < date_from:
        parser.error("to-date must be on or after from-date")
    result = collect(date_from, date_to, max(5, min(args.timeout, 60)), args.actor)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
