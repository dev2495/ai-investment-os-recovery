#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


QUOTE_SOURCE_KEY = "tradingview_scanner_quotes"
QUOTE_ENDPOINT = "https://scanner.tradingview.com/india/scan"
USER_AGENT = "ai-os-local/0.1"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-t",
        "-A",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def run_psql_text(sql: str) -> None:
    command = [
        "docker",
        "exec",
        "-i",
        "ai_os_postgres",
        "psql",
        "-q",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "ai_os",
        "-d",
        "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def active_event_symbols(limit: int) -> list[str]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT DISTINCT upper(symbol) AS symbol
            FROM research.v_special_situation_memos
            WHERE symbol IS NOT NULL
              AND coalesce(memo_status, '') NOT IN ('rejected')
            ORDER BY upper(symbol)
            LIMIT {limit}
        ) rows
        """
    )
    return [str(row["symbol"]).upper() for row in rows if row.get("symbol")]


def fetch_quotes(symbols: list[str]) -> tuple[int | None, int, dict[str, dict[str, Any]], dict[str, Any]]:
    tickers = [f"NSE:{symbol}" for symbol in symbols]
    payload = {
        "symbols": {"tickers": tickers, "query": {"types": []}},
        "columns": ["name", "description", "close", "change", "currency", "exchange"],
    }
    request = urllib.request.Request(
        QUOTE_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", "user-agent": USER_AGENT},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            http_status = response.status
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        sample = {"symbols": symbols, "tickers": tickers, "body": exc.read(500).decode("utf-8", "replace")}
        raise RuntimeError(json.dumps({"http_status": exc.code, "sample": sample, "message": str(exc)})) from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    quotes: dict[str, dict[str, Any]] = {}
    for item in data.get("data", []):
        provider_symbol = item.get("s")
        values = item.get("d") or []
        if len(values) < 6:
            continue
        name, description, close, change, currency, exchange = values
        if close is None:
            continue
        symbol = str(name).upper()
        quotes[symbol] = {
            "source_key": QUOTE_SOURCE_KEY,
            "provider": "TradingView",
            "provider_symbol": provider_symbol,
            "symbol": symbol,
            "exchange": exchange,
            "description": description,
            "currency": currency or "INR",
            "price": Decimal(str(close)),
            "change_percent": Decimal(str(change)) if change is not None else None,
            "raw_payload": item,
        }
    return http_status, latency_ms, quotes, {"request_symbols": symbols, "response_rows": len(data.get("data", []))}


def store_quotes(quotes: dict[str, dict[str, Any]], quote_ts: str) -> None:
    if not quotes:
        return
    statements: list[str] = []
    for quote in quotes.values():
        statements.append(
            f"""
            INSERT INTO market.price_quotes (
                source_key, provider, provider_symbol, symbol, exchange, description,
                currency, price, change_percent, quote_ts, raw_payload
            )
            VALUES (
                {sql_literal(quote["source_key"])},
                {sql_literal(quote["provider"])},
                {sql_literal(quote["provider_symbol"])},
                {sql_literal(quote["symbol"])},
                {sql_literal(quote["exchange"])},
                {sql_literal(quote["description"])},
                {sql_literal(quote["currency"])},
                {quote["price"]},
                {quote["change_percent"] if quote["change_percent"] is not None else "NULL"},
                {sql_literal(quote_ts)}::timestamptz,
                {sql_jsonb(quote["raw_payload"])}
            )
            ON CONFLICT (source_key, provider_symbol, quote_ts) DO NOTHING;
            """
        )
    run_psql_text("\n".join(statements))


def store_check(
    *,
    status: str,
    http_status: int | None,
    latency_ms: int | None,
    rows_seen: int,
    sample_payload: dict[str, Any],
    error_message: str | None,
) -> None:
    sql = f"""
    INSERT INTO core.data_source_checks (
        source_key, check_name, check_type, target_url, status,
        http_status, latency_ms, rows_seen, sample_payload, error_message
    )
    VALUES (
        {sql_literal(QUOTE_SOURCE_KEY)},
        'Event symbol quote refresh',
        'http',
        {sql_literal(QUOTE_ENDPOINT)},
        {sql_literal(status)},
        {http_status if http_status is not None else 'NULL'},
        {latency_ms if latency_ms is not None else 'NULL'},
        {rows_seen},
        {sql_jsonb(sample_payload)},
        {sql_literal(error_message)}
    );
    """
    run_psql_text(sql)


def parse_symbols(raw_values: list[str]) -> list[str]:
    symbols: list[str] = []
    for raw in raw_values:
        for item in raw.split(","):
            symbol = item.strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh stored quotes for active special-situation event symbols.")
    parser.add_argument("--symbols", nargs="*", default=[], help="Optional symbol list. Defaults to active special-situation memo symbols.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols) or active_event_symbols(args.limit)
    if not symbols:
        store_check(status="no_symbols", http_status=None, latency_ms=None, rows_seen=0, sample_payload={}, error_message="No active special-situation symbols found.")
        print(json.dumps({"status": "no_symbols", "symbols": []}, indent=2, sort_keys=True))
        return 0

    quote_ts = datetime.now(timezone.utc).isoformat()
    try:
        http_status, latency_ms, quotes, sample = fetch_quotes(symbols)
        if not args.dry_run:
            store_quotes(quotes, quote_ts)
            missing = sorted(set(symbols) - set(quotes))
            check_status = "ok" if quotes else "no_rows"
            store_check(
                status=check_status,
                http_status=http_status,
                latency_ms=latency_ms,
                rows_seen=len(quotes),
                sample_payload={**sample, "stored_symbols": sorted(quotes), "missing_symbols": missing, "quote_ts": quote_ts},
                error_message=None if quotes else "TradingView scanner returned no usable quote rows.",
            )
        result = {
            "status": "ok" if quotes else "no_rows",
            "symbols_requested": symbols,
            "symbols_priced": sorted(quotes),
            "symbols_missing": sorted(set(symbols) - set(quotes)),
            "quotes_imported": 0 if args.dry_run else len(quotes),
            "quote_ts": quote_ts,
            "dry_run": args.dry_run,
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        if not args.dry_run:
            store_check(
                status="error",
                http_status=None,
                latency_ms=None,
                rows_seen=0,
                sample_payload={"symbols": symbols},
                error_message=str(exc),
            )
        print(json.dumps({"status": "error", "symbols_requested": symbols, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
