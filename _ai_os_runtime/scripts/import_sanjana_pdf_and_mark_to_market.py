#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = Path("/Users/devarshthakkar/Downloads/Sanjana_Long Term_Report_2025-09-17.pdf")
REPORT_DATE = "2025-09-17"
REPORT_SOURCE_KEY = "sanjana_long_term_report_2025_09_17"
QUOTE_SOURCE_KEY = "tradingview_scanner_quotes"
QUOTE_ENDPOINT = "https://scanner.tradingview.com/india/scan"

SYMBOL_OVERRIDES = {
    "SRESTHA": "BSE:SRESTHA",
}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def decimal_or_none(value: object) -> Decimal | None:
    text = str(value or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def run_psql(sql: str) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def clean_pdf_text(text: str) -> str:
    return text.replace("(cid:0)", "").replace("\x00", "")


def extract_pdf_text() -> str:
    chunks: list[str] = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return clean_pdf_text("\n".join(chunks))


def parse_holdings(text: str) -> list[dict[str, Any]]:
    holdings: list[dict[str, Any]] = []
    in_holdings = False
    pattern = re.compile(r"^([A-Z][A-Z0-9]+)\s+([0-9,]+)\s+¹?([0-9,.]+)\s+¹?([0-9,.]+)$")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "CURRENT HOLDINGS":
            in_holdings = True
            continue
        if in_holdings and line.startswith("ALL TRADES"):
            break
        if not in_holdings or not line or line.startswith("Symbol "):
            continue
        match = pattern.match(line)
        if not match:
            continue
        symbol, quantity, average_price, invested = match.groups()
        holdings.append(
            {
                "symbol": symbol,
                "quantity": decimal_or_none(quantity),
                "average_price": decimal_or_none(average_price),
                "invested": decimal_or_none(invested),
                "raw_line": line,
            }
        )
    if not holdings:
        raise RuntimeError("No Sanjana holdings parsed from PDF")
    return holdings


def repair_trade_lines(lines: list[str], holding_symbols: set[str]) -> list[str]:
    repaired: list[str] = []
    index = 0
    trade_start = re.compile(r"^([A-Z][A-Z0-9]+)\s+(buy|sell)\s+", re.IGNORECASE)
    while index < len(lines):
        line = lines[index].strip()
        match = trade_start.match(line)
        if match and match.group(1).upper() not in holding_symbols and index + 1 < len(lines):
            suffix = lines[index + 1].strip()
            if re.fullmatch(r"[A-Z]{1,3}", suffix):
                line = match.group(1).upper() + suffix + line[len(match.group(1)) :]
                index += 1
        repaired.append(line)
        index += 1
    return repaired


def parse_trades(text: str, holding_symbols: set[str]) -> list[dict[str, Any]]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip().startswith("ALL TRADES"))
    except StopIteration:
        return []
    trade_lines = repair_trade_lines([line.strip() for line in lines[start + 1 :]], holding_symbols)
    pattern = re.compile(r"^([A-Z][A-Z0-9]+)\s+(buy|sell)\s+([0-9.]+)\s+([0-9.\\-]+)\s+([0-9,]+)\s+([0-9.,\\-]+)\s+([0-9]{4}-[0-9]{2}-[0-9]{2})$", re.IGNORECASE)
    trades: list[dict[str, Any]] = []
    for line in trade_lines:
        if not line or line.startswith("Symbol ") or line.startswith("PERFORMANCE"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        symbol, side, entry, exit_price, quantity, pnl, trade_date = match.groups()
        price = exit_price if side.lower() == "sell" and exit_price != "-" else entry
        trades.append(
            {
                "symbol": symbol.upper(),
                "side": side.lower(),
                "entry_price": decimal_or_none(entry),
                "exit_price": decimal_or_none(exit_price),
                "quantity": decimal_or_none(quantity),
                "price": decimal_or_none(price),
                "pnl": decimal_or_none(pnl),
                "trade_date": trade_date,
                "raw_line": line,
            }
        )
    return trades


def fetch_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    tickers = [SYMBOL_OVERRIDES.get(symbol, f"NSE:{symbol}") for symbol in symbols]
    payload = {
        "symbols": {"tickers": tickers, "query": {"types": []}},
        "columns": ["name", "description", "close", "change", "currency", "exchange"],
    }
    request = urllib.request.Request(
        QUOTE_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", "user-agent": "ai-os-local/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    quotes: dict[str, dict[str, Any]] = {}
    for item in data.get("data", []):
        provider_symbol = item["s"]
        name, description, close, change, currency, exchange = item["d"]
        symbol = name.upper()
        quotes[symbol] = {
            "source_key": QUOTE_SOURCE_KEY,
            "provider": "TradingView",
            "provider_symbol": provider_symbol,
            "symbol": symbol,
            "exchange": exchange,
            "description": description,
            "currency": currency,
            "price": Decimal(str(close)),
            "change_percent": Decimal(str(change)) if change is not None else None,
            "raw_payload": item,
        }
    return quotes


def build_sql(holdings: list[dict[str, Any]], trades: list[dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> str:
    trade_dates: dict[str, list[str]] = defaultdict(list)
    trade_quantities: dict[str, Decimal] = defaultdict(Decimal)
    for trade in trades:
        if trade["side"] == "buy":
            trade_dates[trade["symbol"]].append(trade["trade_date"])
            if trade["quantity"] is not None:
                trade_quantities[trade["symbol"]] += trade["quantity"]

    statements = ["BEGIN;"]
    statements.append(
        f"""
INSERT INTO portfolio.clients (client_code, display_name, risk_profile, investment_policy, sensitivity, active)
VALUES (
    'sanjana',
    'Sanjana',
    NULL,
    {sql_jsonb({"source": REPORT_SOURCE_KEY, "report_path": str(PDF_PATH), "report_date": REPORT_DATE})},
    'client_private',
    true
)
ON CONFLICT (client_code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    investment_policy = portfolio.clients.investment_policy || EXCLUDED.investment_policy,
    active = true;

WITH client_lookup AS (
    SELECT id FROM portfolio.clients WHERE client_code = 'sanjana'
)
INSERT INTO portfolio.accounts (account_code, account_name, account_type, broker, base_currency, active, client_id)
SELECT 'sanjana_long_term', 'Sanjana Long Term', 'investment', 'pdf_report', 'INR', true, id
FROM client_lookup
ON CONFLICT (account_code) DO UPDATE SET
    account_name = EXCLUDED.account_name,
    account_type = EXCLUDED.account_type,
    broker = EXCLUDED.broker,
    base_currency = EXCLUDED.base_currency,
    active = true,
    client_id = EXCLUDED.client_id;
"""
    )

    for index, trade in enumerate(trades, start=1):
        price = trade["price"] if trade["price"] is not None else "NULL"
        payload = {
            "source": REPORT_SOURCE_KEY,
            "report_path": str(PDF_PATH),
            "report_date": REPORT_DATE,
            "raw_line": trade["raw_line"],
            "entry_price": trade["entry_price"],
            "exit_price": trade["exit_price"],
            "pnl": trade["pnl"],
        }
        statements.append(
            f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'Sanjana Long Term Report 2025-09-17'
),
account_lookup AS (
    SELECT id FROM portfolio.accounts WHERE account_code = 'sanjana_long_term'
)
INSERT INTO portfolio.trades (
    source_system_id, account_id, symbol, exchange, instrument_type, side,
    quantity, price, trade_ts, strategy, raw_payload, external_ref
)
SELECT
    source_lookup.id,
    account_lookup.id,
    {sql_literal(trade["symbol"])},
    'NSE',
    'equity',
    {sql_literal(trade["side"])},
    {trade["quantity"]},
    {price},
    {sql_literal(trade["trade_date"])}::date::timestamptz,
    'sanjana_long_term_report',
    {sql_jsonb(payload)},
    {sql_literal(f"{REPORT_SOURCE_KEY}:trade:{index}:{trade['symbol']}:{trade['side']}:{trade['trade_date']}")}
FROM source_lookup, account_lookup
ON CONFLICT (source_system_id, external_ref) DO UPDATE SET
    account_id = EXCLUDED.account_id,
    symbol = EXCLUDED.symbol,
    exchange = EXCLUDED.exchange,
    instrument_type = EXCLUDED.instrument_type,
    side = EXCLUDED.side,
    quantity = EXCLUDED.quantity,
    price = EXCLUDED.price,
    trade_ts = EXCLUDED.trade_ts,
    strategy = EXCLUDED.strategy,
    raw_payload = EXCLUDED.raw_payload;
"""
        )

    quote_ts = datetime.now(timezone.utc).isoformat()
    for quote in quotes.values():
        statements.append(
            f"""
INSERT INTO market.price_quotes (
    source_key, provider, provider_symbol, symbol, exchange, description, currency,
    price, change_percent, quote_ts, raw_payload
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

    for holding in holdings:
        quote = quotes.get(holding["symbol"])
        market_price = quote["price"] if quote else None
        market_value = holding["quantity"] * market_price if market_price is not None and holding["quantity"] is not None else None
        unrealized_pnl = market_value - holding["invested"] if market_value is not None and holding["invested"] is not None else None
        dates = sorted(trade_dates.get(holding["symbol"], []))
        payload = {
            "source": REPORT_SOURCE_KEY,
            "report_path": str(PDF_PATH),
            "report_date": REPORT_DATE,
            "raw_line": holding["raw_line"],
            "invested_from_report": holding["invested"],
            "first_buy_date": dates[0] if dates else None,
            "buy_dates": dates,
            "trade_quantity_seen": trade_quantities.get(holding["symbol"]),
            "quote_source": quote["provider_symbol"] if quote else None,
            "quote_ts": quote_ts if quote else None,
            "mark_to_market_status": "priced" if quote else "missing_quote",
        }
        statements.append(
            f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'Sanjana Long Term Report 2025-09-17'
),
account_lookup AS (
    SELECT id FROM portfolio.accounts WHERE account_code = 'sanjana_long_term'
)
INSERT INTO portfolio.positions (
    account_id, symbol, exchange, instrument_type, quantity, average_price,
    market_price, market_value, unrealized_pnl, as_of, source_system_id, payload
)
SELECT
    account_lookup.id,
    {sql_literal(holding["symbol"])},
    'NSE',
    'equity',
    {holding["quantity"]},
    {holding["average_price"]},
    {market_price if market_price is not None else "NULL"},
    {market_value if market_value is not None else "NULL"},
    {unrealized_pnl if unrealized_pnl is not None else "NULL"},
    {sql_literal(REPORT_DATE)}::date::timestamptz,
    source_lookup.id,
    {sql_jsonb(payload)}
FROM source_lookup, account_lookup
ON CONFLICT (account_id, symbol, exchange, instrument_type, as_of) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    average_price = EXCLUDED.average_price,
    market_price = EXCLUDED.market_price,
    market_value = EXCLUDED.market_value,
    unrealized_pnl = EXCLUDED.unrealized_pnl,
    source_system_id = EXCLUDED.source_system_id,
    payload = EXCLUDED.payload;
"""
        )

    statements.append(
        f"""
WITH latest_quotes AS (
    SELECT DISTINCT ON (symbol)
        symbol, provider_symbol, price, quote_ts, raw_payload
    FROM market.price_quotes
    WHERE source_key = {sql_literal(QUOTE_SOURCE_KEY)}
    ORDER BY symbol, quote_ts DESC, id DESC
)
UPDATE portfolio.positions p
SET
    market_price = latest_quotes.price,
    market_value = p.quantity * latest_quotes.price,
    unrealized_pnl = (p.quantity * latest_quotes.price) - (p.quantity * coalesce(p.average_price, 0)),
    payload = coalesce(p.payload, '{{}}'::jsonb) || jsonb_build_object(
        'mark_to_market_status', 'priced',
        'quote_source_key', {sql_literal(QUOTE_SOURCE_KEY)},
        'quote_provider_symbol', latest_quotes.provider_symbol,
        'quote_ts', latest_quotes.quote_ts
    )
FROM latest_quotes
WHERE p.symbol = latest_quotes.symbol
  AND p.instrument_type = 'equity';
"""
    )
    statements.append("COMMIT;")
    return "\n".join(statements)


def main() -> int:
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)
    text = extract_pdf_text()
    holdings = parse_holdings(text)
    trades = parse_trades(text, {holding["symbol"] for holding in holdings})
    position_symbols = sorted({holding["symbol"] for holding in holdings})
    existing_symbols_sql = """
    SELECT DISTINCT symbol
    FROM portfolio.positions
    WHERE instrument_type = 'equity'
    ORDER BY symbol;
    """
    existing_output = run_psql(existing_symbols_sql)
    existing_symbols = [
        line.strip()
        for line in existing_output.splitlines()
        if line.strip()
        and not line.startswith("-")
        and not line.strip().startswith("(")
        and line.strip() != "symbol"
    ]
    quote_symbols = sorted(set(position_symbols + existing_symbols))
    quotes = fetch_quotes(quote_symbols)
    sql = build_sql(holdings, trades, quotes)
    run_psql(sql)
    missing_quotes = sorted(set(quote_symbols) - set(quotes))
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf_path": str(PDF_PATH),
        "report_date": REPORT_DATE,
        "holdings_imported": len(holdings),
        "trades_imported": len(trades),
        "quote_symbols_requested": len(quote_symbols),
        "quotes_imported": len(quotes),
        "missing_quotes": missing_quotes,
        "sanjana_symbols": position_symbols,
    }
    output_path = RUNTIME_ROOT / "imports" / "sanjana_pdf_mark_to_market_summary.json"
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
