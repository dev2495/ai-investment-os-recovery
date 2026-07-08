#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


FILES = [
    Path("/Users/devarshthakkar/Downloads/3081282_Transactions (1).xls"),
    Path("/Users/devarshthakkar/Downloads/3081282_Transactions.xls"),
    Path("/Users/devarshthakkar/Desktop/option log.xlsx"),
]
RUNTIME_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = RUNTIME_ROOT / "imports" / "attached_transactions_import_summary.json"


def sql_quote(value: object) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    if isinstance(value, pd.Timestamp):
        value = value.isoformat()
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(clean_json(value), sort_keys=True, default=str)) + "::jsonb"


def clean_json(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(clean_json(payload), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def parse_number(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "nan", "NaN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def parse_time(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", text)
    return match.group(0) if match else None


def infer_period(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text)
    if not match:
        return None, None
    return parse_date(match.group(1)), parse_date(match.group(2))


def run_psql(sql: str) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout


def mime_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xls":
        return "application/vnd.ms-excel"
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".csv":
        return "text/csv"
    return "application/octet-stream"


def upsert_file(path: Path, file_kind: str, client_code: str | None, client_name: str | None, period_start: str | None, period_end: str | None, row_count: int, metadata: dict) -> str:
    digest = sha256_file(path)
    source_system_name = f"Attached file import - {path.name} - {file_kind}"
    sql = f"""
WITH upserted_file AS (
INSERT INTO client_data.attached_transaction_files (
    source_path, file_name, file_kind, sha256, client_code, client_name, period_start, period_end, row_count, metadata
)
VALUES (
    {sql_quote(str(path))},
    {sql_quote(path.name)},
    {sql_quote(file_kind)},
    {sql_quote(digest)},
    {sql_quote(client_code)},
    {sql_quote(client_name)},
    {sql_quote(period_start)}::date,
    {sql_quote(period_end)}::date,
    {row_count},
    {jsonb_quote(metadata)}
)
ON CONFLICT (sha256, file_kind) DO UPDATE SET
    source_path = EXCLUDED.source_path,
    file_name = EXCLUDED.file_name,
    client_code = EXCLUDED.client_code,
    client_name = EXCLUDED.client_name,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    row_count = EXCLUDED.row_count,
    metadata = EXCLUDED.metadata,
    imported_at = now()
RETURNING *
),
source_system AS (
    INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
    SELECT
        {sql_quote(source_system_name)},
        'attached_transaction_file',
        source_path,
        'client_private',
        'imported',
        'User-attached transaction or option-log file registered through the AI OS import pipeline.'
    FROM upserted_file
    ON CONFLICT (name) DO UPDATE SET
        source_type = EXCLUDED.source_type,
        location = EXCLUDED.location,
        sensitivity = EXCLUDED.sensitivity,
        status = EXCLUDED.status,
        notes = EXCLUDED.notes
    RETURNING id
),
artifact AS (
    INSERT INTO core.raw_artifacts (
        source_system_id,
        artifact_type,
        title,
        local_path,
        content_hash,
        mime_type,
        sensitivity,
        metadata
    )
    SELECT
        source_system.id,
        upserted_file.file_kind,
        upserted_file.file_name,
        upserted_file.source_path,
        upserted_file.sha256,
        {sql_quote(mime_type_for(path))},
        'client_private',
        jsonb_build_object(
            'source_table', 'client_data.attached_transaction_files',
            'attached_transaction_file_id', upserted_file.id,
            'file_kind', upserted_file.file_kind,
            'client_code', upserted_file.client_code,
            'client_name', upserted_file.client_name,
            'period_start', upserted_file.period_start,
            'period_end', upserted_file.period_end,
            'row_count', upserted_file.row_count,
            'metadata', upserted_file.metadata
        )
    FROM upserted_file
    CROSS JOIN source_system
    ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
        artifact_type = EXCLUDED.artifact_type,
        title = EXCLUDED.title,
        mime_type = EXCLUDED.mime_type,
        sensitivity = EXCLUDED.sensitivity,
        metadata = core.raw_artifacts.metadata || EXCLUDED.metadata
    RETURNING id
),
linked_file AS (
    UPDATE client_data.attached_transaction_files target
    SET
        raw_artifact_id = artifact.id,
        metadata = target.metadata || jsonb_build_object('raw_artifact_id', artifact.id)
    FROM artifact, upserted_file
    WHERE target.id = upserted_file.id
    RETURNING target.id
)
SELECT coalesce((SELECT id FROM linked_file), (SELECT id FROM upserted_file)) AS id;
"""
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def broker_rows(path: Path) -> tuple[dict, list[dict]]:
    df = pd.read_html(path)[0]
    client_text = str(df.iloc[2, 0])
    client_code = client_text.split(":", 1)[1].strip() if ":" in client_text else None
    client_name = str(df.iloc[3, 0]).strip()
    period_start, period_end = infer_period(str(df.iloc[5, 0]))
    header_idx = int(df.index[df.iloc[:, 0].astype(str).str.strip().eq("Date")][0])
    headers = [str(value).strip() for value in df.iloc[header_idx].tolist()]
    raw = df.iloc[header_idx + 1 :].copy()
    raw.columns = headers
    raw = raw[raw["Date"].notna()]
    rows = []
    for index, row in raw.iterrows():
        payload = {column: clean_json(row.get(column)) for column in raw.columns}
        trade_date = parse_date(row.get("Date"))
        if not trade_date:
            continue
        exchange = str(row.get("Exchange") or "").strip()
        option_type = row.get("Option Type") if "Option Type" in raw.columns else None
        instrument_type = "option" if option_type not in (None, "") or exchange in {"NSEF", "BSEF"} else "equity"
        rows.append(
            {
                "row_number": int(index) + 1,
                "row_hash": row_hash(payload),
                "client_code": client_code,
                "client_name": client_name,
                "trade_date": trade_date,
                "trade_time": parse_time(row.get("Trade Time")),
                "exchange": exchange,
                "trading_symbol": str(row.get("Trading Symbol") or "").strip(),
                "side": str(row.get("Buy/Sell") or "").strip(),
                "quantity": parse_number(row.get("Qty")),
                "market_rate": parse_number(row.get("Market")),
                "net_rate": parse_number(row.get("Net Rate")),
                "amount": parse_number(row.get("Amount")),
                "settlement_no": str(row.get("Settelment No") or "").strip(),
                "trade_no": str(row.get("Trade No") or "").strip(),
                "expiry_date": parse_date(row.get("Expiry Date")) if "Expiry Date" in raw.columns else None,
                "option_type": str(option_type).strip() if option_type is not None and not pd.isna(option_type) else None,
                "strike_price": parse_number(row.get("Strike Price")) if "Strike Price" in raw.columns else None,
                "instrument_type": instrument_type,
                "payload": payload,
            }
        )
    meta = {
        "client_code": client_code,
        "client_name": client_name,
        "period_start": period_start,
        "period_end": period_end,
        "headers": headers,
    }
    return meta, rows


def import_broker_file(path: Path, file_kind: str) -> int:
    meta, rows = broker_rows(path)
    source_file_id = upsert_file(
        path,
        file_kind,
        meta.get("client_code"),
        meta.get("client_name"),
        meta.get("period_start"),
        meta.get("period_end"),
        len(rows),
        meta,
    )
    statements = ["BEGIN;"]
    for row in rows:
        statements.append(
            f"""
INSERT INTO client_data.attached_broker_transactions (
    source_file_id, row_number, row_hash, client_code, client_name, trade_date, trade_time, exchange,
    trading_symbol, side, quantity, market_rate, net_rate, amount, settlement_no, trade_no,
    expiry_date, option_type, strike_price, instrument_type, payload
)
VALUES (
    {source_file_id},
    {row["row_number"]},
    {sql_quote(row["row_hash"])},
    {sql_quote(row["client_code"])},
    {sql_quote(row["client_name"])},
    {sql_quote(row["trade_date"])}::date,
    {sql_quote(row["trade_time"])}::time,
    {sql_quote(row["exchange"])},
    {sql_quote(row["trading_symbol"])},
    {sql_quote(row["side"])},
    {sql_quote(row["quantity"])}::numeric,
    {sql_quote(row["market_rate"])}::numeric,
    {sql_quote(row["net_rate"])}::numeric,
    {sql_quote(row["amount"])}::numeric,
    {sql_quote(row["settlement_no"])},
    {sql_quote(row["trade_no"])},
    {sql_quote(row["expiry_date"])}::date,
    {sql_quote(row["option_type"])},
    {sql_quote(row["strike_price"])}::numeric,
    {sql_quote(row["instrument_type"])},
    {jsonb_quote(row["payload"])}
)
ON CONFLICT (source_file_id, row_hash) DO UPDATE SET
    client_code = EXCLUDED.client_code,
    client_name = EXCLUDED.client_name,
    trade_date = EXCLUDED.trade_date,
    trade_time = EXCLUDED.trade_time,
    exchange = EXCLUDED.exchange,
    trading_symbol = EXCLUDED.trading_symbol,
    side = EXCLUDED.side,
    quantity = EXCLUDED.quantity,
    market_rate = EXCLUDED.market_rate,
    net_rate = EXCLUDED.net_rate,
    amount = EXCLUDED.amount,
    settlement_no = EXCLUDED.settlement_no,
    trade_no = EXCLUDED.trade_no,
    expiry_date = EXCLUDED.expiry_date,
    option_type = EXCLUDED.option_type,
    strike_price = EXCLUDED.strike_price,
    instrument_type = EXCLUDED.instrument_type,
    payload = EXCLUDED.payload;
"""
        )
    statements.append("COMMIT;")
    run_psql("\n".join(statements))
    return len(rows)


def option_log_rows(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name="DATA SHEET", engine="openpyxl")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed:")]
    df = df[df["TRADE ID"].notna()]
    rows = []
    for index, row in df.iterrows():
        payload = {str(column): clean_json(row.get(column)) for column in df.columns}
        rows.append(
            {
                "row_number": int(index) + 2,
                "row_hash": row_hash(payload),
                "trade_id": row.get("TRADE ID"),
                "trade_status": row.get("TRADE STATUS"),
                "trade_type": row.get("TRADE TYPE"),
                "no_of_trades": parse_number(row.get("NO. OF TRADES")),
                "client_code": str(row.get("CLIENT ID")).strip() if not pd.isna(row.get("CLIENT ID")) else None,
                "entry_date": parse_date(row.get("DATE OF ENTRY")),
                "stock_ticker": str(row.get("STOCK TICKER")).strip() if not pd.isna(row.get("STOCK TICKER")) else None,
                "lot_size": parse_number(row.get("LOT SIZE")),
                "contracts": parse_number(row.get("NO. OF CONT")),
                "entry_stock_price": parse_number(row.get("ENTRY STOCK PRICE")),
                "side": str(row.get("BUY/SELL")).strip() if not pd.isna(row.get("BUY/SELL")) else None,
                "call_put": str(row.get("CALL/PUT")).strip() if not pd.isna(row.get("CALL/PUT")) else None,
                "strike_price": parse_number(row.get("STRIKE PRICE")),
                "delta_value": parse_number(row.get("DELTA VALUE")),
                "option_value": parse_number(row.get("OPTION VALUE")),
                "entry_credit_debit": parse_number(row.get("CRED/DEB")),
                "entry_volatility": parse_number(row.get("ENTRY VOLATALITY")),
                "margin_required": parse_number(row.get("MARGIN REQD")),
                "stop_loss_price": parse_number(row.get("SL PRICE")),
                "exit_date": parse_date(row.get("DATE OF EXIT")),
                "exit_stock_price": parse_number(row.get("EXIT STOCK PRICE")),
                "exit_option_value": parse_number(row.get("EXIT OPTION VALUE")),
                "exit_credit_debit": parse_number(row.get("EXIT CRED/DEB")),
                "exit_volatility": parse_number(row.get("EXIT VOLATALITY")),
                "payload": payload,
            }
        )
    return rows


def import_option_log(path: Path) -> int:
    rows = option_log_rows(path)
    client_codes = sorted({row["client_code"] for row in rows if row.get("client_code")})
    source_file_id = upsert_file(
        path,
        "option_log",
        ",".join(client_codes[:10]) if client_codes else None,
        None,
        min((row["entry_date"] for row in rows if row.get("entry_date")), default=None),
        max((row["exit_date"] or row["entry_date"] for row in rows if row.get("exit_date") or row.get("entry_date")), default=None),
        len(rows),
        {"sheet": "DATA SHEET", "client_codes": client_codes},
    )
    statements = ["BEGIN;"]
    for row in rows:
        statements.append(
            f"""
INSERT INTO client_data.attached_option_log_transactions (
    source_file_id, row_number, row_hash, trade_id, trade_status, trade_type, no_of_trades, client_code,
    entry_date, stock_ticker, lot_size, contracts, entry_stock_price, side, call_put, strike_price,
    delta_value, option_value, entry_credit_debit, entry_volatility, margin_required, stop_loss_price,
    exit_date, exit_stock_price, exit_option_value, exit_credit_debit, exit_volatility, payload
)
VALUES (
    {source_file_id},
    {row["row_number"]},
    {sql_quote(row["row_hash"])},
    {sql_quote(row["trade_id"])},
    {sql_quote(row["trade_status"])},
    {sql_quote(row["trade_type"])},
    {sql_quote(row["no_of_trades"])}::numeric,
    {sql_quote(row["client_code"])},
    {sql_quote(row["entry_date"])}::date,
    {sql_quote(row["stock_ticker"])},
    {sql_quote(row["lot_size"])}::numeric,
    {sql_quote(row["contracts"])}::numeric,
    {sql_quote(row["entry_stock_price"])}::numeric,
    {sql_quote(row["side"])},
    {sql_quote(row["call_put"])},
    {sql_quote(row["strike_price"])}::numeric,
    {sql_quote(row["delta_value"])}::numeric,
    {sql_quote(row["option_value"])}::numeric,
    {sql_quote(row["entry_credit_debit"])}::numeric,
    {sql_quote(row["entry_volatility"])}::numeric,
    {sql_quote(row["margin_required"])}::numeric,
    {sql_quote(row["stop_loss_price"])}::numeric,
    {sql_quote(row["exit_date"])}::date,
    {sql_quote(row["exit_stock_price"])}::numeric,
    {sql_quote(row["exit_option_value"])}::numeric,
    {sql_quote(row["exit_credit_debit"])}::numeric,
    {sql_quote(row["exit_volatility"])}::numeric,
    {jsonb_quote(row["payload"])}
)
ON CONFLICT (source_file_id, row_hash) DO UPDATE SET
    trade_status = EXCLUDED.trade_status,
    trade_type = EXCLUDED.trade_type,
    client_code = EXCLUDED.client_code,
    entry_date = EXCLUDED.entry_date,
    exit_date = EXCLUDED.exit_date,
    stock_ticker = EXCLUDED.stock_ticker,
    side = EXCLUDED.side,
    call_put = EXCLUDED.call_put,
    strike_price = EXCLUDED.strike_price,
    option_value = EXCLUDED.option_value,
    exit_option_value = EXCLUDED.exit_option_value,
    payload = EXCLUDED.payload;
"""
        )
    statements.append("COMMIT;")
    run_psql("\n".join(statements))
    return len(rows)


def scalar_count(table: str) -> int:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os"]
    completed = subprocess.run(command, input=f"SELECT count(*) FROM {table};", text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return int(completed.stdout.strip() or "0")


def main() -> int:
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }
    results["files"][str(FILES[0])] = import_broker_file(FILES[0], "broker_equity_transactions")
    results["files"][str(FILES[1])] = import_broker_file(FILES[1], "broker_derivative_transactions")
    results["files"][str(FILES[2])] = import_option_log(FILES[2])
    results["warehouse_counts"] = {
        "attached_transaction_files": scalar_count("client_data.attached_transaction_files"),
        "attached_broker_transactions": scalar_count("client_data.attached_broker_transactions"),
        "attached_option_log_transactions": scalar_count("client_data.attached_option_log_transactions"),
        "attached_client_trade_ledger": scalar_count("client_data.v_attached_client_trade_ledger"),
        "attached_client_positions_by_symbol": scalar_count("client_data.v_attached_client_positions_by_symbol"),
    }
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
