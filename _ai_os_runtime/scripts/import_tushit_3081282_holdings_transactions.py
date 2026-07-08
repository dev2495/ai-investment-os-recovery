#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
HOLDINGS_PATH = Path("/Users/devarshthakkar/Downloads/3081282_portfolioholdings_22321.xls")
TRANSACTIONS_PATH = Path("/Users/devarshthakkar/Downloads/3081282_Transactions.xls")
HOLDINGS_SOURCE_KEY = "tushit_3081282_holdings_2026_07_01"
TRANSACTIONS_SOURCE_KEY = "tushit_3081282_transactions_2026_h1"
ACCOUNT_CODE = "tushit_3081282_statement"
REPORT_AS_OF = "2026-07-01 00:00:00+05:30"


HOLDING_SYMBOLS: dict[str, dict[str, Any]] = {
    "AARON INDUSTRIES": {"symbol": "AARON", "aliases": ["AARON INDUSTRIES LIM"]},
    "C D S L": {"symbol": "CDSL", "aliases": ["CDSL"]},
    "DEEPAK NITRITE": {"symbol": "DEEPAKNTR", "aliases": ["DEEPAK NITRATE"]},
    "EQUITAS SMA. FIN": {"symbol": "EQUITASBNK", "aliases": ["EQUITAS SMALL FIN"]},
    "FAIRCHEM ORGANIC": {"symbol": "FAIRCHEMOR", "aliases": ["FAIRCHEM ORGANICS"]},
    "HDFC BANK": {"symbol": "HDFCBANK", "aliases": ["HDFC BANK LTD"]},
    "ICICI BANK": {"symbol": "ICICIBANK", "aliases": ["ICICI BANK LTD"]},
    "IIFL-RE": {"symbol": "IIFL-RE", "instrument_type": "rights", "aliases": ["IIFL HOLDINGS LIMITE", "IIFL FINANCE LIM RE"]},
    "INDIAN ENERGY EX": {"symbol": "IEX", "aliases": ["INDIAN ENERGY EXCHANGE"]},
    "ITC HOTELS": {"symbol": "ITCHOTELS", "aliases": ["ITC HOTELS"]},
    "JIO FINANCIAL": {"symbol": "JIOFIN", "aliases": ["JIO FINANCIAL SERVICES"]},
    "KAMA HOLDINGS": {"symbol": "KAMAHOLD", "aliases": ["KAMA HOLDINGS"]},
    "LAURUS LABS": {"symbol": "LAURUSLABS", "aliases": ["LAURUS LABS"]},
    "NHPC LTD": {"symbol": "NHPC", "aliases": ["NHPC LTD"]},
    "NIPPON ETF LIQ.": {"symbol": "LIQUIDBEES", "instrument_type": "etf", "aliases": ["R*SHARES LIQUID BEES", "NIPPON INDIA ETF LIQUID BEES"]},
    "PDS": {"symbol": "PDSL", "aliases": ["PDS"]},
    "PINE LABS": {"symbol": "PINELABS", "exchange": "UNLISTED", "aliases": ["PINE LABS LIMITED"]},
    "PIRAMAL PHARMA": {"symbol": "PPLPHARMA", "aliases": ["PIRAMAL PHARMA"]},
    "SAMHI HOTELS": {"symbol": "SAMHI", "aliases": ["SAMHI HOTELS"]},
    "SG MART": {"symbol": "SGMART", "aliases": ["SG MART"]},
    "SHIVALIK BIMETAL": {"symbol": "SBCL", "aliases": ["SHIVALIK BIMETAL"]},
    "SJS ENTERPRISES": {"symbol": "SJS", "aliases": ["SJS ENTERPRISES"]},
    "SRESTHA FINVEST": {"symbol": "SRESTHA", "exchange": "BSE", "aliases": ["SRESTHA FINVEST"]},
    "TATA STEEL": {"symbol": "TATASTEEL", "aliases": ["TATA IRON u0026 STEEL CO", "TATA IRON & STEEL CO"]},
    "USHA MARTIN": {"symbol": "USHAMART", "aliases": ["USHA MARTIN"]},
    "WINDLAS BIOTECH": {"symbol": "WINDLAS", "aliases": ["WINDLAS BIOTECH LIMI"]},
    "ZAGGLE PREPAID": {"symbol": "ZAGGLE", "aliases": ["ZAGGLE PREPAID"]},
}


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def key(value: object) -> str:
    text = clean_text(value).upper().replace("U0026", "AND").replace("&", "AND")
    return re.sub(r"[^A-Z0-9]", "", text)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float) and pd.isna(value):
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(clean_json(value), sort_keys=True, default=str))}::jsonb"


def sql_numeric(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float) and pd.isna(value):
        return "NULL"
    return str(value)


def clean_json(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def decimal_or_none(value: object) -> Decimal | None:
    text = clean_text(value).replace(",", "")
    if not text or text in {"-", "nan", "NaN"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def parse_time(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", text)
    if not match:
        return None
    parts = match.group(0).split(":")
    if len(parts) == 2:
        return f"{parts[0].zfill(2)}:{parts[1]}:00"
    return f"{parts[0].zfill(2)}:{parts[1]}:{parts[2]}"


def row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(clean_json(payload), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def run_psql(sql: str) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def fetch_json_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM ({sql}) q;"
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=wrapped, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    text = completed.stdout.strip()
    return json.loads(text) if text else []


def find_col(columns: list[str], *needles: str) -> str:
    normalized = {key(column): column for column in columns}
    for needle in needles:
        target = key(needle)
        for norm, column in normalized.items():
            if target in norm:
                return column
    raise KeyError(f"Could not find column matching {needles}; columns={columns}")


def parse_holdings() -> list[dict[str, Any]]:
    tables = pd.read_html(HOLDINGS_PATH)
    holding_df: pd.DataFrame | None = None
    for table in tables:
        for row_index, row in table.iterrows():
            values = [clean_text(value) for value in row.tolist()]
            if any(value == "Company Name" for value in values) and any("Total Holding" in value for value in values):
                holding_df = table.iloc[row_index + 1 :].copy()
                holding_df.columns = values
                break
        if holding_df is not None:
            break
    if holding_df is None:
        for table in tables:
            if table.shape[1] == 12 and table.shape[0] > 1 and clean_text(table.iloc[0, 0]) == "Equity":
                holding_df = table.iloc[1:].copy()
                holding_df.columns = [
                    "Asset Class",
                    "Company Name",
                    "Total Holding",
                    "Average Price",
                    "Invested Amount",
                    "Last Price",
                    "Current Amount",
                    "Todays Gain Loss",
                    "Unrealized Gain/Loss",
                    "Rise Fall Percent",
                    "Weightage",
                    "Blank",
                ]
                break
    if holding_df is None:
        raise RuntimeError(f"No holdings table found in {HOLDINGS_PATH}")

    columns = [clean_text(column) for column in holding_df.columns]
    holding_df.columns = columns
    company_col = find_col(columns, "Company Name")
    qty_col = find_col(columns, "Total Holding")
    avg_col = find_col(columns, "Average Price")
    invested_col = find_col(columns, "Invested Amount")
    last_col = find_col(columns, "Last Price")
    market_value_col = find_col(columns, "Current Amount")
    pnl_col = find_col(columns, "Unrealized Gain/Loss")

    holdings: list[dict[str, Any]] = []
    for _, row in holding_df.iterrows():
        raw_name = clean_text(row.get(company_col))
        asset_class = clean_text(row.get("Asset Class")).upper()
        if (
            not raw_name
            or raw_name.upper().startswith("TOTAL")
            or raw_name.upper().startswith("GRAND")
            or asset_class.startswith("TOTAL")
            or asset_class.startswith("GRAND")
            or re.fullmatch(r"[0-9,.]+", raw_name)
        ):
            continue
        config = HOLDING_SYMBOLS.get(raw_name.upper(), {})
        symbol = config.get("symbol", re.sub(r"[^A-Z0-9]", "", raw_name.upper())[:20])
        quantity = decimal_or_none(row.get(qty_col))
        average_price = decimal_or_none(row.get(avg_col))
        invested_amount = decimal_or_none(row.get(invested_col))
        market_price = decimal_or_none(row.get(last_col))
        market_value = decimal_or_none(row.get(market_value_col))
        unrealized_pnl = decimal_or_none(row.get(pnl_col))
        holdings.append(
            {
                "raw_company_name": raw_name,
                "symbol": symbol,
                "exchange": config.get("exchange", "NSE"),
                "instrument_type": config.get("instrument_type", "equity"),
                "aliases": [raw_name, *config.get("aliases", [])],
                "quantity": quantity,
                "average_price": average_price,
                "invested_amount": invested_amount,
                "market_price": market_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "raw_payload": {column: clean_json(row.get(column)) for column in columns},
            }
        )
    if not holdings:
        raise RuntimeError(f"No holding rows parsed from {HOLDINGS_PATH}")
    return holdings


def parse_transactions() -> list[dict[str, Any]]:
    df = pd.read_html(TRANSACTIONS_PATH)[0]
    header_index = int(df.index[df.iloc[:, 0].astype(str).str.strip().eq("Date")][0])
    headers = [clean_text(value) for value in df.iloc[header_index].tolist()]
    raw = df.iloc[header_index + 1 :].copy()
    raw.columns = headers
    raw = raw[raw["Date"].notna()]
    transactions: list[dict[str, Any]] = []
    for index, row in raw.iterrows():
        payload = {column: clean_json(row.get(column)) for column in headers}
        trade_date = parse_date(row.get("Date"))
        if not trade_date:
            continue
        trade_time = parse_time(row.get("Trade Time")) or "15:30:00"
        option_type = clean_text(row.get("Option Type")) if "Option Type" in headers else ""
        exchange = clean_text(row.get("Exchange"))
        raw_side = clean_text(row.get("Buy/Sell")).upper()
        side = "buy" if raw_side in {"B", "BUY"} else "sell" if raw_side in {"S", "SELL"} else raw_side.lower()
        instrument_type = "option" if option_type else ("future" if exchange.endswith("F") else "equity")
        trade_no = clean_text(row.get("Trade No"))
        settlement_no = clean_text(row.get("Settelment No"))
        reference_payload = {
            "trade_no": trade_no,
            "settlement_no": settlement_no,
            "row_hash": row_hash(payload),
            "row_number": int(index) + 1,
        }
        external_ref = f"{TRANSACTIONS_SOURCE_KEY}:{trade_no or row_hash(payload)}:{int(index) + 1}"
        transactions.append(
            {
                "symbol": clean_text(row.get("Trading Symbol")),
                "exchange": exchange,
                "instrument_type": instrument_type,
                "side": side,
                "quantity": decimal_or_none(row.get("Qty")),
                "price": decimal_or_none(row.get("Net Rate")) or decimal_or_none(row.get("Market")),
                "trade_ts": f"{trade_date} {trade_time}+05:30",
                "external_ref": external_ref,
                "raw_payload": {
                    **payload,
                    "parsed": reference_payload,
                    "source_file": str(TRANSACTIONS_PATH),
                    "option_type": option_type or None,
                    "strike_price": clean_json(row.get("Strike Price")) if "Strike Price" in headers else None,
                    "expiry_date": parse_date(row.get("Expiry Date")) if "Expiry Date" in headers else None,
                },
            }
        )
    return transactions


def enrich_buy_dates(holdings: list[dict[str, Any]]) -> None:
    symbol_dates = fetch_json_rows(
        """
        SELECT symbol, first_buy_date, last_buy_date, bought_quantity, sold_quantity, net_quantity
        FROM client_data.v_client_3081282_symbol_dates
        WHERE instrument_type = 'equity'
        """
    )
    p2_dates = fetch_json_rows(
        """
        SELECT t.symbol,
               MIN(t.trade_ts::date) FILTER (WHERE lower(t.side) = 'buy') AS first_buy_date,
               MAX(t.trade_ts::date) FILTER (WHERE lower(t.side) = 'buy') AS last_buy_date,
               SUM(CASE WHEN lower(t.side) = 'buy' THEN t.quantity ELSE 0 END) AS bought_quantity,
               SUM(CASE WHEN lower(t.side) = 'sell' THEN t.quantity ELSE 0 END) AS sold_quantity
        FROM portfolio.trades t
        JOIN portfolio.accounts a ON a.id = t.account_id
        WHERE a.account_code = 'p2cursor_account_2'
        GROUP BY t.symbol
        """
    )

    attached_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in symbol_dates:
        attached_by_key[key(row.get("symbol"))].append(row)

    p2_by_symbol = {key(row.get("symbol")): row for row in p2_dates}

    for holding in holdings:
        candidates: list[dict[str, Any]] = []
        for alias in holding["aliases"]:
            candidates.extend(attached_by_key.get(key(alias), []))
        p2_match = p2_by_symbol.get(key(holding["symbol"]))
        if p2_match:
            candidates.append({**p2_match, "symbol": holding["symbol"], "source": "p2cursor_account_2"})

        first_dates = [row.get("first_buy_date") for row in candidates if row.get("first_buy_date")]
        last_dates = [row.get("last_buy_date") for row in candidates if row.get("last_buy_date")]
        holding["first_buy_date"] = min(first_dates) if first_dates else None
        holding["last_buy_date"] = max(last_dates) if last_dates else None
        holding["buy_date_evidence"] = [
            {
                "source_symbol": row.get("symbol"),
                "first_buy_date": row.get("first_buy_date"),
                "last_buy_date": row.get("last_buy_date"),
                "bought_quantity": row.get("bought_quantity"),
                "sold_quantity": row.get("sold_quantity"),
                "net_quantity": row.get("net_quantity"),
                "source": row.get("source", "attached_3081282_transactions"),
            }
            for row in candidates
        ]


def build_sql(holdings: list[dict[str, Any]], transactions: list[dict[str, Any]]) -> str:
    total_market_value = sum((h.get("market_value") or Decimal("0")) for h in holdings)
    total_unrealized = sum((h.get("unrealized_pnl") or Decimal("0")) for h in holdings)
    symbol_array = "ARRAY[" + ",".join(sql_literal(holding["symbol"]) for holding in holdings) + "]::text[]"
    provider_symbol_array = "ARRAY[" + ",".join(sql_literal(holding["raw_company_name"]) for holding in holdings) + "]::text[]"
    statements = ["BEGIN;"]
    statements.append(
        f"""
INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    ('Tushit 3081282 Holdings Statement 2026-07-01', 'broker_statement', {sql_literal(str(HOLDINGS_PATH))}, 'client_private', 'imported', 'Current holdings statement imported from user-provided broker export.'),
    ('Tushit 3081282 Transactions 2026 H1', 'broker_transaction_statement', {sql_literal(str(TRANSACTIONS_PATH))}, 'client_private', 'imported', 'Transactions statement imported from user-provided broker export.')
ON CONFLICT (name) DO UPDATE SET
    source_type = EXCLUDED.source_type,
    location = EXCLUDED.location,
    sensitivity = EXCLUDED.sensitivity,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes;

INSERT INTO core.data_source_registry (
    source_key, source_name, source_type, provider, connection_mode, status,
    freshness_target_minutes, owner_agent, sensitivity, source_system_id, notes, metadata
)
VALUES
    (
        {sql_literal(HOLDINGS_SOURCE_KEY)},
        'Tushit 3081282 Holdings 2026-07-01',
        'broker_statement_holdings',
        'local_broker_export',
        'file_import',
        'imported',
        NULL,
        'Portfolio Manager',
        'client_private',
        (SELECT id FROM core.source_systems WHERE name = 'Tushit 3081282 Holdings Statement 2026-07-01'),
        'Current holdings imported from attached 3081282 portfolio statement. Statement prices used for mark-to-market.',
        {sql_jsonb({"account_code": ACCOUNT_CODE, "report_as_of": REPORT_AS_OF, "path": str(HOLDINGS_PATH), "execution_allowed": False})}
    ),
    (
        {sql_literal(TRANSACTIONS_SOURCE_KEY)},
        'Tushit 3081282 Transactions 2026 H1',
        'broker_statement_transactions',
        'local_broker_export',
        'file_import',
        'imported',
        NULL,
        'Portfolio Manager',
        'client_private',
        (SELECT id FROM core.source_systems WHERE name = 'Tushit 3081282 Transactions 2026 H1'),
        'Current transaction ledger imported from attached 3081282 transaction export.',
        {sql_jsonb({"account_code": ACCOUNT_CODE, "path": str(TRANSACTIONS_PATH), "execution_allowed": False})}
    )
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    provider = EXCLUDED.provider,
    connection_mode = EXCLUDED.connection_mode,
    status = EXCLUDED.status,
    freshness_target_minutes = EXCLUDED.freshness_target_minutes,
    owner_agent = EXCLUDED.owner_agent,
    sensitivity = EXCLUDED.sensitivity,
    source_system_id = EXCLUDED.source_system_id,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

WITH existing_tushit AS (
    SELECT id FROM portfolio.clients
    WHERE lower(display_name) LIKE 'tushit%'
    ORDER BY id
    LIMIT 1
),
inserted_tushit AS (
    INSERT INTO portfolio.clients (client_code, display_name, risk_profile, investment_policy, sensitivity, active)
    SELECT '3081282', 'TUSHIT BANSAL', NULL, {sql_jsonb({"account_aliases": ["3081282"], "source": HOLDINGS_SOURCE_KEY})}, 'client_private', true
    WHERE NOT EXISTS (SELECT 1 FROM existing_tushit)
    ON CONFLICT (client_code) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        investment_policy = portfolio.clients.investment_policy || EXCLUDED.investment_policy,
        active = true
    RETURNING id
),
resolved_tushit AS (
    SELECT id FROM existing_tushit
    UNION ALL
    SELECT id FROM inserted_tushit
    LIMIT 1
)
INSERT INTO portfolio.accounts (account_code, account_name, account_type, broker, base_currency, active, client_id)
SELECT {sql_literal(ACCOUNT_CODE)}, 'TUSHIT BANSAL 3081282 Statement', 'investment', 'broker_statement', 'INR', true, id
FROM resolved_tushit
ON CONFLICT (account_code) DO UPDATE SET
    account_name = EXCLUDED.account_name,
    account_type = EXCLUDED.account_type,
    broker = EXCLUDED.broker,
    base_currency = EXCLUDED.base_currency,
    active = true,
    client_id = EXCLUDED.client_id;

UPDATE portfolio.clients c
SET investment_policy = c.investment_policy || {sql_jsonb({"account_aliases": ["3081282", "tushit_3081282_statement"], "latest_statement_source": HOLDINGS_SOURCE_KEY})}
FROM portfolio.accounts a
WHERE a.client_id = c.id AND a.account_code = {sql_literal(ACCOUNT_CODE)};

DELETE FROM portfolio.positions p
USING portfolio.accounts a
WHERE p.account_id = a.id
  AND a.account_code = {sql_literal(ACCOUNT_CODE)}
  AND p.as_of = {sql_literal(REPORT_AS_OF)}::timestamptz
  AND NOT (p.symbol = ANY({symbol_array}));

DELETE FROM market.price_quotes
WHERE source_key = {sql_literal(HOLDINGS_SOURCE_KEY)}
  AND quote_ts = {sql_literal(REPORT_AS_OF)}::timestamptz
  AND NOT (provider_symbol = ANY({provider_symbol_array}));
"""
    )

    for holding in holdings:
        payload = {
            "raw_company_name": holding["raw_company_name"],
            "source_file": str(HOLDINGS_PATH),
            "invested_amount": holding["invested_amount"],
            "first_buy_date": holding.get("first_buy_date"),
            "last_buy_date": holding.get("last_buy_date"),
            "buy_date_evidence": holding.get("buy_date_evidence", []),
            "raw_payload": holding["raw_payload"],
        }
        statements.append(
            f"""
INSERT INTO trading.symbols (symbol, exchange, instrument_type, name, currency, active)
VALUES ({sql_literal(holding["symbol"])}, {sql_literal(holding["exchange"])}, {sql_literal(holding["instrument_type"])}, {sql_literal(holding["raw_company_name"])}, 'INR', true)
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET
    name = EXCLUDED.name,
    currency = EXCLUDED.currency,
    active = true;

INSERT INTO portfolio.positions (
    account_id, symbol, exchange, instrument_type, quantity, average_price, market_price,
    market_value, unrealized_pnl, as_of, source_system_id, payload
)
SELECT
    a.id,
    {sql_literal(holding["symbol"])},
    {sql_literal(holding["exchange"])},
    {sql_literal(holding["instrument_type"])},
    {sql_numeric(holding["quantity"])},
    {sql_numeric(holding["average_price"])},
    {sql_numeric(holding["market_price"])},
    {sql_numeric(holding["market_value"])},
    {sql_numeric(holding["unrealized_pnl"])},
    {sql_literal(REPORT_AS_OF)}::timestamptz,
    s.id,
    {sql_jsonb(payload)}
FROM portfolio.accounts a
CROSS JOIN core.source_systems s
WHERE a.account_code = {sql_literal(ACCOUNT_CODE)}
  AND s.name = 'Tushit 3081282 Holdings Statement 2026-07-01'
ON CONFLICT (account_id, symbol, exchange, instrument_type, as_of) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    average_price = EXCLUDED.average_price,
    market_price = EXCLUDED.market_price,
    market_value = EXCLUDED.market_value,
    unrealized_pnl = EXCLUDED.unrealized_pnl,
    source_system_id = EXCLUDED.source_system_id,
    payload = EXCLUDED.payload;

INSERT INTO market.price_quotes (
    source_key, provider, provider_symbol, symbol, exchange, description, currency,
    price, change_percent, quote_ts, raw_payload
)
VALUES (
    {sql_literal(HOLDINGS_SOURCE_KEY)},
    'broker_statement',
    {sql_literal(holding["raw_company_name"])},
    {sql_literal(holding["symbol"])},
    {sql_literal(holding["exchange"])},
    {sql_literal(holding["raw_company_name"])},
    'INR',
    {sql_numeric(holding["market_price"])},
    NULL,
    {sql_literal(REPORT_AS_OF)}::timestamptz,
    {sql_jsonb(payload)}
)
ON CONFLICT (source_key, provider_symbol, quote_ts) DO UPDATE SET
    symbol = EXCLUDED.symbol,
    exchange = EXCLUDED.exchange,
    description = EXCLUDED.description,
    currency = EXCLUDED.currency,
    price = EXCLUDED.price,
    change_percent = EXCLUDED.change_percent,
    raw_payload = EXCLUDED.raw_payload;
"""
        )

    for trade in transactions:
        if not trade["symbol"]:
            continue
        statements.append(
            f"""
INSERT INTO portfolio.trades (
    source_system_id, account_id, symbol, exchange, instrument_type, side, quantity,
    price, trade_ts, strategy, raw_payload, external_ref
)
SELECT
    s.id,
    a.id,
    {sql_literal(trade["symbol"])},
    {sql_literal(trade["exchange"])},
    {sql_literal(trade["instrument_type"])},
    {sql_literal(trade["side"])},
    {sql_numeric(trade["quantity"])},
    {sql_numeric(trade["price"])},
    {sql_literal(trade["trade_ts"])}::timestamptz,
    NULL,
    {sql_jsonb(trade["raw_payload"])},
    {sql_literal(trade["external_ref"])}
FROM core.source_systems s
CROSS JOIN portfolio.accounts a
WHERE s.name = 'Tushit 3081282 Transactions 2026 H1'
  AND a.account_code = {sql_literal(ACCOUNT_CODE)}
ON CONFLICT (source_system_id, external_ref) DO UPDATE SET
    account_id = EXCLUDED.account_id,
    symbol = EXCLUDED.symbol,
    exchange = EXCLUDED.exchange,
    instrument_type = EXCLUDED.instrument_type,
    side = EXCLUDED.side,
    quantity = EXCLUDED.quantity,
    price = EXCLUDED.price,
    trade_ts = EXCLUDED.trade_ts,
    raw_payload = EXCLUDED.raw_payload;
"""
        )

    statements.append(
        f"""
INSERT INTO portfolio.snapshots (ts, account_id, equity, cash, margin_used, pnl_day, pnl_total, payload)
SELECT
    {sql_literal(REPORT_AS_OF)}::timestamptz,
    a.id,
    {sql_numeric(total_market_value)},
    NULL,
    NULL,
    NULL,
    {sql_numeric(total_unrealized)},
    {sql_jsonb({"source_key": HOLDINGS_SOURCE_KEY, "holding_count": len(holdings), "report_as_of": REPORT_AS_OF})}
FROM portfolio.accounts a
WHERE a.account_code = {sql_literal(ACCOUNT_CODE)}
ON CONFLICT (ts, account_id) DO UPDATE SET
    equity = EXCLUDED.equity,
    cash = EXCLUDED.cash,
    margin_used = EXCLUDED.margin_used,
    pnl_day = EXCLUDED.pnl_day,
    pnl_total = EXCLUDED.pnl_total,
    payload = EXCLUDED.payload;

INSERT INTO core.import_runs (source_system_id, import_type, status, started_at, finished_at, rows_seen, rows_imported, notes)
SELECT id, 'broker_holdings_and_transactions', 'completed', now(), now(), {len(holdings) + len(transactions)}, {len(holdings) + len(transactions)},
       'Imported 3081282 current holdings, broker statement quotes, account snapshot, and transaction ledger into portfolio tables.'
FROM core.source_systems
WHERE name = 'Tushit 3081282 Holdings Statement 2026-07-01';

COMMIT;
"""
    )
    return "\n".join(statements)


def main() -> int:
    if not HOLDINGS_PATH.exists():
        raise SystemExit(f"Missing holdings file: {HOLDINGS_PATH}")
    if not TRANSACTIONS_PATH.exists():
        raise SystemExit(f"Missing transactions file: {TRANSACTIONS_PATH}")

    holdings = parse_holdings()
    transactions = parse_transactions()
    enrich_buy_dates(holdings)
    sql = build_sql(holdings, transactions)
    run_psql(sql)

    missing_buy_dates = [holding["symbol"] for holding in holdings if not holding.get("first_buy_date")]
    summary = {
        "account_code": ACCOUNT_CODE,
        "holdings_imported": len(holdings),
        "transactions_imported": len(transactions),
        "report_as_of": REPORT_AS_OF,
        "missing_first_buy_date_symbols": missing_buy_dates,
        "market_value": str(sum((h.get("market_value") or Decimal("0")) for h in holdings)),
        "unrealized_pnl": str(sum((h.get("unrealized_pnl") or Decimal("0")) for h in holdings)),
    }
    output_path = RUNTIME_ROOT / "imports" / "tushit_3081282_import_summary.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
