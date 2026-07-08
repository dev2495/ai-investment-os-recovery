#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
P2_SELECTED = RUNTIME_ROOT / "imports" / "quarantine" / "p2cursor_selected" / "ps 2 cursor"


@dataclass(frozen=True)
class FolioSource:
    client_code: str
    display_name: str
    account_code: str
    account_name: str
    csv_path: Path
    source_label: str


FOLIO_SOURCES = [
    FolioSource(
        client_code="3081832",
        display_name="Tushit",
        account_code="p2cursor_account_2",
        account_name="Tushit P2Cursor Account 2",
        csv_path=P2_SELECTED / "tushit_equity_bulk_upload.csv",
        source_label="p2cursor:tushit_equity_bulk_upload.csv",
    ),
    FolioSource(
        client_code="naval",
        display_name="Naval",
        account_code="p2cursor_account_3",
        account_name="Naval P2Cursor Account 3",
        csv_path=P2_SELECTED / "naval_equity_folio_trades.csv",
        source_label="p2cursor:naval_equity_folio_trades.csv",
    ),
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def normalize_decimal(value: object) -> Decimal | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    return Decimal(text)


def normalize_row(source: FolioSource, index: int, row: dict[str, str]) -> dict:
    symbol = (row.get("Symbol") or row.get("symbol") or "").strip().upper()
    side = (row.get("Trade Type") or row.get("trade_type") or "").strip().lower()
    quantity = normalize_decimal(row.get("Qty") or row.get("qty"))
    buy_price = normalize_decimal(row.get("Buy Avg Price") or row.get("entry_price"))
    sell_price = normalize_decimal(row.get("Sell Price") or row.get("exit_price"))
    trade_date = (
        row.get("Date")
        or (row.get("exit_date") if side == "sell" else row.get("entry_date"))
        or row.get("entry_date")
        or row.get("exit_date")
    )
    if not symbol or side not in {"buy", "sell"} or quantity is None or not trade_date:
        raise ValueError(f"Cannot normalize row {index} from {source.csv_path}")
    price = sell_price if side == "sell" and sell_price is not None else buy_price
    if price is None:
        raise ValueError(f"Missing price on row {index} from {source.csv_path}")
    return {
        "row_index": index,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "trade_date": trade_date,
        "instrument_type": (row.get("Asset Type") or "equity").strip().lower(),
        "raw": row,
        "external_ref": f"{source.source_label}:row:{index}",
    }


def read_trades(source: FolioSource) -> list[dict]:
    with source.csv_path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
        rows = [normalize_row(source, index, row) for index, row in enumerate(csv.DictReader(handle), start=2)]
    return sorted(rows, key=lambda item: (item["trade_date"], item["row_index"]))


def fifo_positions(trades: list[dict]) -> dict[str, dict]:
    lots: dict[str, list[list[Decimal]]] = defaultdict(list)
    for trade in trades:
        symbol = trade["symbol"]
        quantity = trade["quantity"]
        price = trade["price"]
        if trade["side"] == "buy":
            lots[symbol].append([quantity, price])
            continue
        remaining = quantity
        while remaining > 0 and lots[symbol]:
            lot_quantity, lot_price = lots[symbol][0]
            used = min(lot_quantity, remaining)
            lot_quantity -= used
            remaining -= used
            if lot_quantity == 0:
                lots[symbol].pop(0)
            else:
                lots[symbol][0] = [lot_quantity, lot_price]

    positions: dict[str, dict] = {}
    for symbol, symbol_lots in lots.items():
        quantity = sum(lot[0] for lot in symbol_lots)
        if quantity == 0:
            continue
        cost = sum(lot[0] * lot[1] for lot in symbol_lots)
        positions[symbol] = {
            "symbol": symbol,
            "quantity": quantity,
            "average_price": cost / quantity,
            "lots": [{"quantity": lot[0], "price": lot[1]} for lot in symbol_lots],
        }
    return positions


def run_psql(sql: str) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def build_sql() -> tuple[str, dict]:
    statements = ["BEGIN;"]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "folios": [],
        "sanjana": {
            "client_code": "sanjana",
            "display_name": "Sanjana",
            "holdings_source_found": False,
            "research_reports_found": [
                "/Users/devarshthakkar/Downloads/Sanjana_Long Term_Report.pdf",
                "/Users/devarshthakkar/Downloads/Sanjana_Long Term_Report_2025-09-17.pdf",
            ],
        },
    }

    for source in FOLIO_SOURCES:
        trades = read_trades(source)
        positions = fifo_positions(trades)
        as_of = max(trade["trade_date"] for trade in trades)
        statements.append(
            f"""
INSERT INTO portfolio.clients (client_code, display_name, risk_profile, investment_policy, sensitivity, active)
VALUES (
    {sql_literal(source.client_code)},
    {sql_literal(source.display_name)},
    NULL,
    {sql_jsonb({"source": source.source_label, "evidence": str(source.csv_path)})},
    'client_private',
    true
)
ON CONFLICT (client_code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    investment_policy = portfolio.clients.investment_policy || EXCLUDED.investment_policy,
    active = true;

WITH client_lookup AS (
    SELECT id FROM portfolio.clients WHERE client_code = {sql_literal(source.client_code)}
)
INSERT INTO portfolio.accounts (account_code, account_name, account_type, broker, base_currency, active, client_id)
SELECT
    {sql_literal(source.account_code)},
    {sql_literal(source.account_name)},
    'investment',
    'legacy_p2cursor',
    'INR',
    true,
    client_lookup.id
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
        for trade in trades:
            payload = {
                **trade["raw"],
                "__source_file": str(source.csv_path),
                "__source_label": source.source_label,
                "__client_code": source.client_code,
            }
            statements.append(
                f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'ps 2 cursor archive'
),
account_lookup AS (
    SELECT id FROM portfolio.accounts WHERE account_code = {sql_literal(source.account_code)}
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
    {sql_literal(trade["instrument_type"])},
    {sql_literal(trade["side"])},
    {trade["quantity"]},
    {trade["price"]},
    {sql_literal(trade["trade_date"])}::date::timestamptz,
    'legacy_p2cursor_folio',
    {sql_jsonb(payload)},
    {sql_literal(trade["external_ref"])}
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
        for position in positions.values():
            payload = {
                "source_label": source.source_label,
                "cost_method": "fifo_from_p2cursor_trades",
                "as_of_source_trade_date": as_of,
                "open_lots": position["lots"],
            }
            statements.append(
                f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'ps 2 cursor archive'
),
account_lookup AS (
    SELECT id FROM portfolio.accounts WHERE account_code = {sql_literal(source.account_code)}
)
INSERT INTO portfolio.positions (
    account_id, symbol, exchange, instrument_type, quantity, average_price,
    market_price, market_value, unrealized_pnl, as_of, source_system_id, payload
)
SELECT
    account_lookup.id,
    {sql_literal(position["symbol"])},
    'NSE',
    'equity',
    {position["quantity"]},
    {position["average_price"]},
    NULL,
    NULL,
    NULL,
    {sql_literal(as_of)}::date::timestamptz,
    source_lookup.id,
    {sql_jsonb(payload)}
FROM source_lookup, account_lookup
ON CONFLICT (account_id, symbol, exchange, instrument_type, as_of) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    average_price = EXCLUDED.average_price,
    source_system_id = EXCLUDED.source_system_id,
    payload = EXCLUDED.payload;
"""
            )
        summary["folios"].append(
            {
                "client_code": source.client_code,
                "display_name": source.display_name,
                "account_code": source.account_code,
                "source_file": str(source.csv_path),
                "trade_rows": len(trades),
                "open_positions": len(positions),
                "as_of": as_of,
            }
        )

    statements.append(
        f"""
INSERT INTO portfolio.clients (client_code, display_name, risk_profile, investment_policy, sensitivity, active)
VALUES (
    'sanjana',
    'Sanjana',
    NULL,
    {sql_jsonb(summary["sanjana"])},
    'client_private',
    true
)
ON CONFLICT (client_code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    investment_policy = portfolio.clients.investment_policy || EXCLUDED.investment_policy,
    active = true;

INSERT INTO agent.tasks (
    title, objective, owner_agent, status, priority, approval_required,
    source_kind, source_ref, output_format, evidence
)
SELECT
    'Collect Sanjana holdings source',
    'Sanjana has research reports indexed, but no holdings CSV or broker file was found in the current P2Cursor selected set. Attach or locate the holdings source before creating positions.',
    'Portfolio Manager',
    'queued',
    'high',
    true,
    'portfolio.clients',
    'sanjana',
    'holdings_source_request',
    jsonb_build_array(
        jsonb_build_object('client_code', 'sanjana'),
        jsonb_build_object('reports', {sql_jsonb(summary["sanjana"]["research_reports_found"])})
    )
WHERE NOT EXISTS (
    SELECT 1 FROM agent.tasks
    WHERE title = 'Collect Sanjana holdings source'
      AND source_ref = 'sanjana'
      AND status IN ('queued', 'in_progress', 'blocked')
);
"""
    )
    statements.append("COMMIT;")
    return "\n".join(statements), summary


def main() -> int:
    sql, summary = build_sql()
    run_psql(sql)
    output_path = RUNTIME_ROOT / "imports" / "p2cursor_folio_promotion_summary.json"
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
