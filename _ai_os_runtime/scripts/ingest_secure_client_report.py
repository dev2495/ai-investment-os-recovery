#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


PARSER_KEY = "secure_client_report_v1"
PARSER_VERSION = "1.0.0"
PSQL_BIN = os.environ.get("AI_OS_PSQL_BIN", "/opt/homebrew/opt/postgresql@15/bin/psql")
DOCKER_BIN = os.environ.get("AI_OS_DOCKER_BIN", "/opt/homebrew/bin/docker")
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "symbol": ("symbol", "tradingsymbol", "scripcode", "securitycode", "stockticker"),
    "isin": ("isin", "isincode"),
    "instrument_name": ("scripname", "scriptname", "securityname", "companyname", "instrumentname", "particulars"),
    "transaction_type": ("transactiontype", "tradetype", "buysell", "side", "type", "mode", "markettype"),
    "purchase_date": ("purchasedate", "buydate", "dateofpurchase", "acquisitiondate"),
    "sale_date": ("saledate", "selldate", "dateofsale", "transferdate"),
    "transaction_date": ("transactiondate", "tradedate", "date"),
    "quantity": ("quantity", "qty", "units", "netquantity", "salequantity"),
    "average_price": ("averageprice", "avgprice", "averagecost", "avgcost", "averagebuyprice"),
    "market_price": ("ltp", "lastprice", "marketprice", "currentprice", "lasttradedprice"),
    "market_value": ("marketvalue", "currentvalue", "presentvalue", "holdingvalue"),
    "cash_balance": ("cashbalance", "cashavailable", "availablecash", "ledgerbalance"),
    "available_funds": ("availablefunds", "fundsavailable", "withdrawablebalance", "availablemargin"),
    "collateral_value": ("collateralvalue", "collateralmargin", "pledgedcollateral"),
    "buy_price": ("buyprice", "purchaserate", "buyrate", "acquisitionprice", "costperunit"),
    "buy_value": ("buyvalue", "purchasevalue", "costvalue", "costofacquisition", "totalcost", "buyamount"),
    "sell_price": ("sellprice", "salerate", "sellrate", "saleprice", "realisationprice"),
    "sell_value": ("sellvalue", "salevalue", "netdealvalue", "saleamount", "realisationvalue"),
    "holding_period_days": ("holdingperiod", "holdingdays", "periodofholding", "daysheld"),
    "realized_gain": ("realizedgain", "realisedgain", "profitloss", "gainloss", "netgain", "totalgain"),
    "speculative_gain": ("speculativegain", "speculativegainlose", "speculativegainloss", "speculationgain", "speculativeprofit"),
    "taxable_gain": ("taxablegain", "taxableprofit"),
    "short_term_gain": ("shortterm", "shorttermgain", "stcg", "shorttermcapitalgain"),
    "long_term_gain": ("longterm", "longtermgain", "ltcg", "longtermcapitalgain"),
    "tax_period": ("taxperiod", "financialyear", "assessmentyear"),
    "rate": ("netrate", "marketrate", "rate", "price"),
    "amount": ("amount", "netamount", "tradevalue"),
    "brokerage": ("brokerage", "brokeragecharges"),
    "stt": ("stt", "securitytransactiontax", "securitiestransactiontax"),
    "exchange_charges": ("exchangecharges", "transactioncharges", "exchangetransactioncharges"),
    "gst": ("gst", "servicetax", "goodsandservicetax"),
    "stamp_duty": ("stampduty", "stampcharges"),
    "sebi_charges": ("sebicharges", "sebiturnoverfees"),
    "dp_charges": ("dpcharges", "depositorycharges"),
    "other_charges": ("othercharges", "misccharges", "totalcharges", "charges"),
}

CHARGE_FIELDS = ("brokerage", "stt", "exchange_charges", "gst", "stamp_duty", "sebi_charges", "dp_charges", "other_charges")


def normalized(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_json(value: object) -> str:
    return sql_literal(json.dumps(value, sort_keys=True, default=str)) + "::jsonb"


def sql_numeric(value: Decimal | int | None) -> str:
    return "NULL" if value is None else str(value)


def run_psql(sql: str, *, tuples_only: bool = False) -> str:
    suffix = ["-q", "-t", "-A"] if tuples_only else ["-q"]
    commands = [
        [PSQL_BIN, "-h", "127.0.0.1", "-p", POSTGRES_PORT, *suffix, "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        [DOCKER_BIN, "exec", "-i", "ai_os_postgres", "psql", *suffix, "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
    ]
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    errors: list[str] = []
    for command in commands:
        try:
            completed = subprocess.run(command, input=sql, text=True, capture_output=True, env=env, check=False)
        except FileNotFoundError:
            errors.append(f"database client unavailable: {command[0]}")
            continue
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((completed.stderr or completed.stdout or command[0]).strip())
    raise RuntimeError("database command failed: " + " | ".join(errors))


def fetch_json(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(result)), '[]'::json) FROM ({sql}) result;"
    value = run_psql(wrapped, tuples_only=True)
    return json.loads(value or "[]")


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table_stack: list[list[list[str]]] = []
        self.row_stack: list[list[str]] = []
        self.cell_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self.table_stack.append([])
        elif tag == "tr" and self.table_stack:
            self.row_stack.append([])
        elif tag in {"td", "th"} and self.row_stack:
            self.cell_stack.append([])

    def handle_data(self, data: str) -> None:
        if self.cell_stack:
            self.cell_stack[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self.cell_stack and self.row_stack:
            self.row_stack[-1].append(re.sub(r"\s+", " ", "".join(self.cell_stack.pop())).strip())
        elif tag == "tr" and self.row_stack and self.table_stack:
            row = self.row_stack.pop()
            if any(cell.strip() for cell in row):
                self.table_stack[-1].append(row)
        elif tag == "table" and self.table_stack:
            table = self.table_stack.pop()
            if table:
                self.tables.append(table)


def parse_html_tables(raw: bytes) -> list[list[list[str]]]:
    text = raw.decode("utf-8", errors="replace")
    if text.count("�") > max(5, len(text) // 100):
        text = raw.decode("latin-1", errors="replace")
    parser = TableParser()
    parser.feed(text)
    return parser.tables


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    value = 0
    for character in (letters.group(0) if letters else "A"):
        value = value * 26 + ord(character) - 64
    return value - 1


def parse_xlsx_tables(path: Path) -> list[list[list[str]]]:
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    tables: list[list[list[str]]] = []
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{namespace}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{namespace}t")))
        sheet_names = sorted(name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        for sheet_name in sheet_names:
            root = ElementTree.fromstring(archive.read(sheet_name))
            rows: list[list[str]] = []
            for xml_row in root.iter(f"{namespace}row"):
                row: list[str] = []
                for cell in xml_row.findall(f"{namespace}c"):
                    index = column_index(cell.attrib.get("r", "A1"))
                    while len(row) <= index:
                        row.append("")
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find(f"{namespace}v")
                    if cell_type == "inlineStr":
                        inline = cell.find(f"{namespace}is")
                        value = "".join(node.text or "" for node in inline.iter(f"{namespace}t")) if inline is not None else ""
                    else:
                        value = value_node.text if value_node is not None and value_node.text is not None else ""
                        if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                            value = shared[int(value)]
                    row[index] = re.sub(r"\s+", " ", value).strip()
                if any(row):
                    rows.append(row)
            if rows:
                tables.append(rows)
    return tables


def parse_csv_tables(path: Path) -> list[list[list[str]]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [[list(row) for row in csv.reader(text.splitlines(), dialect) if any(cell.strip() for cell in row)]]


def load_tables(path: Path) -> tuple[list[list[list[str]]], str | None]:
    prefix = path.read_bytes()[:16]
    if prefix.startswith(b"%PDF"):
        return [], "structured_excel_required"
    if prefix.startswith(b"PK\x03\x04"):
        return parse_xlsx_tables(path), None
    if prefix.startswith(b"\xd0\xcf\x11\xe0"):
        return [], "binary_xls_requires_xlsx_export"
    if path.suffix.lower() in {".csv", ".tsv"}:
        return parse_csv_tables(path), None
    raw = path.read_bytes()
    if b"<table" in raw[:200000].lower() or path.suffix.lower() == ".xls":
        return parse_html_tables(raw), None
    return [], "unsupported_structured_format"


def parse_decimal(value: object) -> Decimal | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"-", "na", "n/a", "nan", "null"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if cleaned in {"", "-", "."}:
        return None
    try:
        result = Decimal(cleaned)
        return -result if negative and result > 0 else result
    except InvalidOperation:
        return None


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    numeric = parse_decimal(text)
    if numeric is not None and numeric == numeric.to_integral() and 20000 <= numeric <= 80000:
        return date(1899, 12, 30) + timedelta(days=int(numeric))
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def header_mapping(row: list[str]) -> dict[str, int]:
    normalized_headers = [normalized(cell) for cell in row]
    mapping: dict[str, int] = {}
    for field, aliases in HEADER_ALIASES.items():
        for index, header in enumerate(normalized_headers):
            if header and any(header == alias or (len(alias) >= 6 and alias in header) for alias in aliases):
                mapping[field] = index
                break
    return mapping


def best_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    candidates: list[tuple[int, int, dict[str, int]]] = []
    for index, row in enumerate(table[:50]):
        mapping = header_mapping(row)
        evidence = sum(key in mapping for key in (
            "symbol", "instrument_name", "purchase_date", "sale_date", "transaction_date",
            "quantity", "buy_value", "sell_value", "realized_gain", "average_price",
            "market_price", "market_value", "cash_balance", "available_funds", "collateral_value",
        ))
        has_identity = "symbol" in mapping or "instrument_name" in mapping
        has_holding_values = "quantity" in mapping and any(
            key in mapping for key in ("average_price", "market_price", "market_value")
        )
        if (evidence >= 3 and ("quantity" in mapping or "realized_gain" in mapping)) or (has_identity and has_holding_values):
            candidates.append((evidence, -index, mapping))
    if not candidates:
        return None
    _, negative_index, mapping = max(candidates, key=lambda item: (item[0], item[1]))
    return -negative_index, mapping


def value_at(row: list[str], mapping: dict[str, int], field: str) -> str:
    index = mapping.get(field)
    return row[index].strip() if index is not None and index < len(row) else ""


@dataclass
class ParsedRow:
    row_number: int
    row_hash: str
    layer: str
    values: dict[str, Any]
    raw_payload: dict[str, str]


@dataclass
class ParseException:
    row_number: int | None
    row_hash: str | None
    code: str
    severity: str
    field: str | None
    message: str


def extract_identity(tables: list[list[list[str]]]) -> str | None:
    labels = ("clientcode", "clientid", "ucc", "accountnumber", "accountno", "clientname")
    for table in tables[:4]:
        for row in table[:35]:
            for index, cell in enumerate(row):
                compact = normalized(cell)
                capital_match = re.search(r"-\s*([A-Za-z0-9]{5,})\s*-\s*Capital\s+Gain\s+Report", cell, flags=re.IGNORECASE)
                if capital_match:
                    return hashlib.sha256(normalized(capital_match.group(1)).encode("utf-8")).hexdigest()
                for label in labels:
                    if compact == label and index + 1 < len(row) and row[index + 1].strip():
                        return hashlib.sha256(normalized(row[index + 1]).encode("utf-8")).hexdigest()
                    if compact.startswith(label) and ":" in cell:
                        value = cell.split(":", 1)[1].strip()
                        if value:
                            return hashlib.sha256(normalized(value).encode("utf-8")).hexdigest()
    return None


def parse_report(tables: list[list[list[str]]]) -> tuple[list[ParsedRow], list[ParseException]]:
    parsed_rows: list[ParsedRow] = []
    exceptions: list[ParseException] = []
    global_row_number = 0
    abm_capital_header_seen = False
    for table in tables:
        header = best_header(table)
        if not header:
            fund_values: dict[str, Decimal] = {}
            fund_raw: dict[str, str] = {}
            for candidate in table:
                if len(candidate) < 2:
                    continue
                label = normalized(candidate[0])
                for field in ("cash_balance", "available_funds", "collateral_value"):
                    if any(label == alias or (len(alias) >= 6 and alias in label) for alias in HEADER_ALIASES[field]):
                        value = parse_decimal(candidate[1])
                        if value is not None:
                            fund_values[field] = value
                            fund_raw[candidate[0].strip() or field] = candidate[1].strip()
                        break
            if fund_values:
                global_row_number += 1
                values: dict[str, Any] = {
                    "cash_balance": fund_values.get("cash_balance"),
                    "available_funds": fund_values.get("available_funds"),
                    "collateral_value": fund_values.get("collateral_value"),
                    "normalized_payload": {
                        "source_layer": "fund_balance",
                        "methodology": "Visible source fields normalized without estimating missing fund values.",
                    },
                }
                row_hash = hashlib.sha256(json.dumps({
                    **{key: str(value) for key, value in fund_values.items()},
                    "source_row_number": global_row_number,
                }, sort_keys=True).encode("utf-8")).hexdigest()
                parsed_rows.append(ParsedRow(global_row_number, row_hash, "fund_balance", values, fund_raw))
                continue
        if header:
            header_index, mapping = header
            header_cells = table[header_index]
            data_rows = table[header_index + 1:]
            if {"instrument_name", "purchase_date", "sale_date", "quantity", "buy_value", "sell_value"} <= set(mapping):
                abm_capital_header_seen = True
        elif abm_capital_header_seen and sum(1 for row in table if len(row) >= 16) >= 1:
            mapping = {
                "instrument_name": 0, "isin": 1, "purchase_date": 2, "sale_date": 3, "quantity": 4,
                "holding_period_days": 5, "buy_value": 6, "sell_value": 7,
                "buy_price": 8, "sell_price": 9, "speculative_gain": 10,
                "short_term_gain": 11, "long_term_gain": 14, "taxable_gain": 15,
            }
            header_cells = [
                "Scrip Name", "ISIN", "Purchase Date", "Sale Date", "Units", "Holding Period",
                "Buy Value", "Sell Value", "Buy Price", "Sell Price", "Speculative Gain",
                "Short Term Gain", "Reference High Price", "Reference Buy Value",
                "Long Term Gain", "Taxable Gain",
            ]
            data_rows = [row for row in table if len(row) >= 16]
        else:
            continue
        for row in data_rows:
            global_row_number += 1
            if not any(str(cell).strip() for cell in row):
                continue
            raw_payload = {str(header_cells[index] or f"column_{index + 1}"): row[index] if index < len(row) else "" for index in range(len(header_cells))}
            raw_values = {field: value_at(row, mapping, field) for field in mapping}
            label = (raw_values.get("instrument_name") or raw_values.get("symbol") or "").strip()
            is_total = normalized(label).startswith(("total", "grandtotal", "summary"))
            numeric_fields = {field: parse_decimal(raw_values.get(field)) for field in (
                "quantity", "buy_price", "buy_value", "sell_price", "sell_value", "holding_period_days",
                "realized_gain", "speculative_gain", "taxable_gain", "short_term_gain", "long_term_gain", "rate", "amount", *CHARGE_FIELDS,
                "average_price", "market_price", "market_value", "cash_balance", "available_funds", "collateral_value",
            )}
            purchase_date = parse_date(raw_values.get("purchase_date"))
            sale_date = parse_date(raw_values.get("sale_date"))
            transaction_date = parse_date(raw_values.get("transaction_date"))
            has_economic_value = any(value is not None for value in numeric_fields.values())
            if not has_economic_value and not (purchase_date or sale_date or transaction_date) and len(header_mapping(row)) >= 2:
                continue
            if not label and not has_economic_value and not (purchase_date or sale_date or transaction_date):
                continue
            holding_evidence = numeric_fields.get("quantity") is not None and any(
                numeric_fields.get(field) is not None for field in ("average_price", "market_price", "market_value")
            )
            fund_evidence = any(
                numeric_fields.get(field) is not None for field in ("cash_balance", "available_funds", "collateral_value")
            )
            layer = (
                "tax_summary" if is_total else
                "tax_lot" if purchase_date or sale_date else
                "holding" if holding_evidence and not transaction_date else
                "fund_balance" if fund_evidence and not transaction_date else
                "transaction"
            )
            charges = {field: value for field, value in numeric_fields.items() if field in CHARGE_FIELDS and value is not None}
            total_charges = sum(charges.values(), Decimal(0)) if charges else None
            holding_days = numeric_fields.get("holding_period_days")
            if holding_days is None and purchase_date and sale_date:
                holding_days = Decimal((sale_date - purchase_date).days)
            normalized_payload = {
                "source_layer": layer,
                "charge_categories": {key: str(value) for key, value in charges.items()},
                "methodology": "Source fields normalized without estimating missing broker values.",
            }
            transaction_type = raw_values.get("transaction_type") or None
            side = normalized(transaction_type)
            buy_price = numeric_fields.get("buy_price")
            buy_value = numeric_fields.get("buy_value")
            sell_price = numeric_fields.get("sell_price")
            sell_value = numeric_fields.get("sell_value")
            if side in {"b", "buy"}:
                buy_price = buy_price if buy_price is not None else numeric_fields.get("rate")
                buy_value = buy_value if buy_value is not None else numeric_fields.get("amount")
            elif side in {"s", "sell"}:
                sell_price = sell_price if sell_price is not None else numeric_fields.get("rate")
                sell_value = sell_value if sell_value is not None else numeric_fields.get("amount")
            realized_gain = numeric_fields.get("realized_gain")
            if realized_gain is None:
                gain_parts = [numeric_fields.get(field) for field in ("speculative_gain", "short_term_gain", "long_term_gain")]
                if any(value is not None for value in gain_parts):
                    realized_gain = sum((value or Decimal(0)) for value in gain_parts)
            values: dict[str, Any] = {
                "symbol": raw_values.get("symbol") or None,
                "isin": raw_values.get("isin") or None,
                "instrument_name": raw_values.get("instrument_name") or None,
                "transaction_type": transaction_type,
                "purchase_date": purchase_date,
                "sale_date": sale_date,
                "transaction_date": transaction_date,
                "quantity": numeric_fields.get("quantity"),
                "average_price": numeric_fields.get("average_price"),
                "market_price": numeric_fields.get("market_price"),
                "market_value": numeric_fields.get("market_value"),
                "cash_balance": numeric_fields.get("cash_balance"),
                "available_funds": numeric_fields.get("available_funds"),
                "collateral_value": numeric_fields.get("collateral_value"),
                "buy_price": buy_price,
                "buy_value": buy_value,
                "sell_price": sell_price,
                "sell_value": sell_value,
                "holding_period_days": int(holding_days) if holding_days is not None else None,
                "realized_gain": realized_gain,
                "speculative_gain": numeric_fields.get("speculative_gain"),
                "taxable_gain": numeric_fields.get("taxable_gain"),
                "short_term_gain": numeric_fields.get("short_term_gain"),
                "long_term_gain": numeric_fields.get("long_term_gain"),
                "total_charges": total_charges,
                "tax_period": raw_values.get("tax_period") or None,
                "normalized_payload": normalized_payload,
            }
            hash_payload = {key: str(value) if isinstance(value, (Decimal, date)) else value for key, value in values.items() if key != "normalized_payload"}
            hash_payload["source_row_number"] = global_row_number
            row_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            parsed_rows.append(ParsedRow(global_row_number, row_hash, layer, values, raw_payload))

            def add(code: str, severity: str, field: str | None, message: str) -> None:
                exceptions.append(ParseException(global_row_number, row_hash, code, severity, field, message))

            quantity = numeric_fields.get("quantity")
            transaction_type = normalized(raw_values.get("transaction_type"))
            if layer not in {"tax_summary", "fund_balance"} and quantity is None:
                add("unknown_quantity", "error", "quantity", "Quantity is missing or not numeric; the row cannot be promoted.")
            elif quantity is not None and quantity < 0:
                add("negative_quantity", "blocking", "quantity", "Quantity is negative; side and sign require operator review.")
            elif quantity == 0:
                add("zero_quantity", "error", "quantity", "Quantity is zero; the source row needs review.")
            if raw_values.get("purchase_date") and purchase_date is None:
                add("malformed_date", "error", "purchase_date", "Purchase date is not parseable.")
            if raw_values.get("sale_date") and sale_date is None:
                add("malformed_date", "error", "sale_date", "Sale date is not parseable.")
            if purchase_date and sale_date and sale_date < purchase_date:
                add("sale_before_purchase", "blocking", "sale_date", "Sale date precedes purchase date.")
            if layer == "tax_lot" and quantity is not None and quantity > 0 and (buy_value is None or buy_value == 0):
                add("zero_or_missing_cost", "warning", "buy_value", "Cost basis is zero or missing; do not treat it as final without corporate-action evidence.")
                add("missing_corporate_action", "warning", "buy_value", "Check bonus, split, merger, transfer, or other corporate-action history before accepting zero cost.")
            if any(token in transaction_type for token in ("offmarket", "manual", "transfer", "interdepository")):
                add("off_market_or_manual", "warning", "transaction_type", "Off-market, manual, or transfer row requires source evidence and identity review.")
    if not parsed_rows:
        exceptions.append(ParseException(None, None, "no_supported_rows", "blocking", None, "No supported transaction or tax-lot table was detected."))
    return parsed_rows, exceptions


def insert_rows(import_id: int, rows: list[ParsedRow]) -> None:
    for start in range(0, len(rows), 150):
        values_sql: list[str] = []
        for row in rows[start:start + 150]:
            value = row.values
            values_sql.append("(" + ",".join([
                str(import_id), str(row.row_number), sql_literal(row.row_hash), sql_literal(row.layer),
                sql_literal(value.get("symbol")), sql_literal(value.get("isin")), sql_literal(value.get("instrument_name")), sql_literal(value.get("transaction_type")),
                sql_literal(value.get("purchase_date")), sql_literal(value.get("sale_date")), sql_literal(value.get("transaction_date")),
                sql_numeric(value.get("quantity")), sql_numeric(value.get("buy_price")), sql_numeric(value.get("buy_value")),
                sql_numeric(value.get("sell_price")), sql_numeric(value.get("sell_value")), sql_numeric(value.get("holding_period_days")),
                sql_numeric(value.get("realized_gain")), sql_numeric(value.get("speculative_gain")), sql_numeric(value.get("taxable_gain")),
                sql_numeric(value.get("short_term_gain")), sql_numeric(value.get("long_term_gain")), sql_numeric(value.get("total_charges")),
                sql_numeric(value.get("average_price")), sql_numeric(value.get("market_price")), sql_numeric(value.get("market_value")),
                sql_numeric(value.get("cash_balance")), sql_numeric(value.get("available_funds")), sql_numeric(value.get("collateral_value")),
                sql_literal(value.get("tax_period")), sql_json(value.get("normalized_payload")), sql_json(row.raw_payload),
            ]) + ")")
        if not values_sql:
            continue
        run_psql("""
            INSERT INTO client_data.client_import_rows (
                import_id,row_number,row_hash,layer,symbol,isin,instrument_name,transaction_type,
                purchase_date,sale_date,transaction_date,quantity,buy_price,buy_value,
                sell_price,sell_value,holding_period_days,realized_gain,speculative_gain,taxable_gain,
                short_term_gain,long_term_gain,total_charges,average_price,market_price,market_value,
                cash_balance,available_funds,collateral_value,tax_period,normalized_payload,raw_payload
            ) VALUES
        """ + ",\n".join(values_sql) + " ON CONFLICT (import_id,layer,row_hash) DO NOTHING;")


def insert_exceptions(import_id: int, exceptions: list[ParseException]) -> None:
    if not exceptions:
        return
    values = []
    for item in exceptions:
        values.append("(" + ",".join([
            str(import_id), sql_numeric(item.row_number), sql_literal(item.row_hash), sql_literal(item.code),
            sql_literal(item.severity), sql_literal(item.field), sql_literal(item.message),
        ]) + ")")
    run_psql("""
        INSERT INTO client_data.client_import_exceptions (
            import_id,row_number,row_hash,exception_code,severity,field_name,message
        ) VALUES
    """ + ",\n".join(values) + " ON CONFLICT (import_id,row_number,exception_code,field_name) DO NOTHING;")


def derive_fifo_lots(rows: list[ParsedRow]) -> tuple[list[dict[str, Any]], list[ParseException]]:
    ledgers: dict[str, list[dict[str, Any]]] = {}
    exceptions: list[ParseException] = []
    transactions = sorted(
        (row for row in rows if row.layer == "transaction" and row.values.get("transaction_date")),
        key=lambda row: (row.values.get("transaction_date"), row.row_number),
    )
    for row in transactions:
        side = normalized(row.values.get("transaction_type"))
        if side not in {"b", "buy", "s", "sell"}:
            continue
        symbol = str(row.values.get("symbol") or row.values.get("instrument_name") or "").strip().upper()
        quantity = row.values.get("quantity")
        if not symbol or quantity is None or quantity <= 0:
            continue
        lots = ledgers.setdefault(symbol, [])
        if side in {"b", "buy"}:
            buy_value = row.values.get("buy_value")
            buy_price = row.values.get("buy_price")
            unit_cost = abs(buy_price) if buy_price is not None else (abs(buy_value) / quantity if buy_value is not None else None)
            lots.append({
                "symbol": symbol,
                "opening_row_hash": hashlib.sha256(f"{row.row_hash}:{row.row_number}".encode("utf-8")).hexdigest(),
                "purchase_date": row.values.get("transaction_date"),
                "original_quantity": quantity, "remaining_quantity": quantity,
                "unit_cost": unit_cost,
                "quality_status": "complete_for_covered_period" if unit_cost is not None else "missing_cost",
            })
            if unit_cost is None:
                exceptions.append(ParseException(row.row_number, row.row_hash, "missing_cost", "error", "buy_value", "Buy transaction has no usable rate or amount for FIFO cost basis."))
            continue
        remaining = quantity
        for lot in lots:
            if remaining <= 0:
                break
            available = lot["remaining_quantity"]
            if available <= 0:
                continue
            consumed = min(available, remaining)
            lot["remaining_quantity"] -= consumed
            remaining -= consumed
        if remaining > 0:
            exceptions.append(ParseException(
                row.row_number, row.row_hash, "opening_position_missing", "warning", "quantity",
                "Sell quantity exceeds buys inside the source period; earlier opening history or an off-market receipt is required.",
            ))
            for lot in lots:
                lot["quality_status"] = "opening_history_incomplete"
    open_lots = []
    for lots in ledgers.values():
        for lot in lots:
            if lot["remaining_quantity"] <= 0:
                continue
            unit_cost = lot["unit_cost"]
            lot["remaining_cost_basis"] = unit_cost * lot["remaining_quantity"] if unit_cost is not None else None
            open_lots.append(lot)
    return open_lots, exceptions


def insert_derived_lots(import_id: int, lots: list[dict[str, Any]]) -> None:
    run_psql(f"DELETE FROM client_data.client_import_derived_lots WHERE import_id={import_id};")
    if not lots:
        return
    values = []
    for lot in lots:
        values.append("(" + ",".join([
            str(import_id),sql_literal(lot["symbol"]),sql_literal(lot["opening_row_hash"]),
            sql_literal(lot["purchase_date"]),sql_numeric(lot["original_quantity"]),
            sql_numeric(lot["remaining_quantity"]),sql_numeric(lot["unit_cost"]),
            sql_numeric(lot["remaining_cost_basis"]),sql_literal(lot["quality_status"]),
        ]) + ")")
    run_psql("""
        INSERT INTO client_data.client_import_derived_lots (
            import_id,symbol,opening_row_hash,purchase_date,original_quantity,
            remaining_quantity,unit_cost,remaining_cost_basis,quality_status
        ) VALUES
    """ + ",\n".join(values) + " ON CONFLICT (import_id,symbol,opening_row_hash) DO UPDATE SET remaining_quantity=EXCLUDED.remaining_quantity,remaining_cost_basis=EXCLUDED.remaining_cost_basis,quality_status=EXCLUDED.quality_status;")


def reconcile_account_imports(account_id: int) -> None:
    run_psql(f"""
        DELETE FROM client_data.client_import_reconciliation_matches WHERE account_id={account_id};
        WITH capital_rows AS (
            SELECT row.id,row.import_id,row.sale_date,row.quantity,row.sell_price,row.sell_value
            FROM client_data.client_import_rows row
            JOIN client_data.secure_client_imports import ON import.id=row.import_id
            WHERE import.account_id={account_id} AND import.report_kind IN ('aditya_birla_money_capital_gains','tax_report')
              AND import.identity_status='resolved'
              AND row.layer='tax_lot'
        ),
        transaction_rows AS (
            SELECT row.id,row.import_id,row.transaction_date,row.quantity,row.sell_price,row.sell_value
            FROM client_data.client_import_rows row
            JOIN client_data.secure_client_imports import ON import.id=row.import_id
            WHERE import.account_id={account_id} AND import.report_kind='broker_transactions'
              AND import.identity_status='resolved'
              AND row.layer='transaction' AND upper(coalesce(row.transaction_type,'')) IN ('S','SELL')
        ),
        candidates AS (
            SELECT capital.id capital_row_id,capital.import_id capital_import_id,
                   transaction.id transaction_row_id,transaction.import_id transaction_import_id,
                   abs(abs(coalesce(capital.quantity,0))-abs(coalesce(transaction.quantity,0))) quantity_difference,
                   abs(abs(coalesce(capital.sell_price,0))-abs(coalesce(transaction.sell_price,0))) price_difference,
                   abs(abs(coalesce(capital.sell_value,0))-abs(coalesce(transaction.sell_value,0))) value_difference,
                   row_number() OVER (
                       PARTITION BY capital.id
                       ORDER BY abs(abs(coalesce(capital.sell_value,0))-abs(coalesce(transaction.sell_value,0))),
                                abs(abs(coalesce(capital.sell_price,0))-abs(coalesce(transaction.sell_price,0))),transaction.id
                   ) candidate_rank,
                   count(*) OVER (PARTITION BY capital.id) candidate_count
            FROM capital_rows capital
            JOIN transaction_rows transaction
              ON transaction.transaction_date=capital.sale_date
             AND abs(abs(coalesce(transaction.quantity,0))-abs(coalesce(capital.quantity,0))) <= 0.000001
             AND (
                  abs(abs(coalesce(transaction.sell_value,0))-abs(coalesce(capital.sell_value,0))) <= 2
                  OR abs(abs(coalesce(transaction.sell_price,0))-abs(coalesce(capital.sell_price,0))) <= 0.05
             )
        ),
        selected AS (
            SELECT * FROM candidates WHERE candidate_rank=1
        )
        INSERT INTO client_data.client_import_reconciliation_matches (
            account_id,capital_gain_import_id,transaction_import_id,capital_gain_row_id,
            transaction_row_id,match_status,confidence,quantity_difference,price_difference,value_difference,evidence
        )
        SELECT {account_id},capital.import_id,selected.transaction_import_id,capital.id,
               selected.transaction_row_id,
               CASE WHEN selected.transaction_row_id IS NULL THEN 'unmatched'
                    WHEN selected.candidate_count > 1 THEN 'ambiguous' ELSE 'matched' END,
               CASE WHEN selected.transaction_row_id IS NULL THEN 0
                    WHEN selected.candidate_count > 1 THEN 0.6
                    WHEN selected.value_difference <= 0.05 THEN 1 ELSE 0.9 END,
               selected.quantity_difference,selected.price_difference,selected.value_difference,
               jsonb_build_object('method','sale_date_quantity_price_value_v1','broker_write_allowed',false)
        FROM capital_rows capital LEFT JOIN selected ON selected.capital_row_id=capital.id;

        WITH status AS (
            SELECT capital_gain_import_id,
                   count(*) FILTER (WHERE match_status='unmatched') unmatched,
                   count(*) FILTER (WHERE match_status='ambiguous') ambiguous,
                   sum(abs(coalesce(value_difference,0))) difference
            FROM client_data.client_import_reconciliation_matches
            WHERE account_id={account_id}
            GROUP BY capital_gain_import_id
        )
        UPDATE client_data.secure_client_imports import
        SET reconciliation_status=CASE WHEN status.unmatched=0 AND status.ambiguous=0 THEN 'matched' ELSE 'breaks' END,
            reconciliation_difference=status.difference,reconciled_at=now(),updated_at=now()
        FROM status WHERE import.id=status.capital_gain_import_id;
    """)


def process_import(import_key: str, actor: str) -> dict[str, Any]:
    imports = fetch_json(f"""
        SELECT id,storage_path,sha256,broker,report_kind,client_id,account_id
        FROM client_data.secure_client_imports
        WHERE import_key={sql_literal(import_key)}
        LIMIT 1
    """)
    if not imports:
        raise ValueError("import_key not found")
    source = imports[0]
    path = Path(source["storage_path"])
    if not path.is_file():
        raise FileNotFoundError("immutable source file is not available")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != source["sha256"]:
        raise RuntimeError("immutable source checksum does not match the intake record")

    tables, format_issue = load_tables(path)
    identity_hash = extract_identity(tables)
    rows, exceptions = parse_report(tables) if tables else ([], [])
    fifo_lots, fifo_exceptions = derive_fifo_lots(rows)
    exceptions.extend(fifo_exceptions)
    if format_issue:
        message = {
            "structured_excel_required": "PDF is preserved as evidence, but the Excel export is required for deterministic row import.",
            "binary_xls_requires_xlsx_export": "This binary XLS format is preserved, but re-export as XLSX or CSV for deterministic import.",
            "unsupported_structured_format": "The file is preserved, but its structured format is not supported.",
        }[format_issue]
        exceptions.append(ParseException(None, None, format_issue, "blocking", None, message))

    identity_status = "not_present"
    status = "stored_unparsed" if format_issue else "needs_identity_review"
    if identity_hash:
        matches = fetch_json(f"""
            SELECT account_id FROM client_data.client_source_identities
            WHERE broker={sql_literal(source['broker'])}
              AND source_identity_hash={sql_literal(identity_hash)}
              AND status='verified'
            LIMIT 1
        """)
        if not matches:
            identity_status = "needs_review"
        elif int(matches[0]["account_id"]) == int(source["account_id"]):
            identity_status = "resolved"
            status = "parsed" if not format_issue else status
        else:
            identity_status = "mismatch"
            status = "blocked_identity_mismatch"

    run_psql(f"DELETE FROM client_data.client_import_exceptions WHERE import_id={int(source['id'])}; DELETE FROM client_data.client_import_rows WHERE import_id={int(source['id'])};")
    insert_rows(int(source["id"]), rows)
    insert_exceptions(int(source["id"]), exceptions)
    insert_derived_lots(int(source["id"]), fifo_lots)

    detail_rows = [row for row in rows if row.layer != "tax_summary"]
    transaction_rows = [row for row in rows if row.layer == "transaction"]
    holding_rows = [row for row in rows if row.layer == "holding"]
    fund_rows = [row for row in rows if row.layer == "fund_balance"]
    summary_rows = [row for row in rows if row.layer == "tax_summary"]
    lots = [row for row in rows if row.layer == "tax_lot"]
    charge_rows = [row for row in detail_rows if row.values.get("total_charges") is not None]
    detail_realized = sum((row.values.get("realized_gain") or Decimal(0)) for row in detail_rows)
    summary_realized = sum((row.values.get("realized_gain") or Decimal(0)) for row in summary_rows)
    reconciliation_status = "incomplete"
    reconciliation_difference: Decimal | None = None
    if summary_rows and any(row.values.get("realized_gain") is not None for row in summary_rows):
        reconciliation_difference = detail_realized - summary_realized
        tolerance = max(Decimal("1"), abs(summary_realized) * Decimal("0.0001"))
        reconciliation_status = "matched" if abs(reconciliation_difference) <= tolerance else "breaks"

    dates = [value for row in detail_rows for value in (row.values.get("transaction_date"), row.values.get("sale_date"), row.values.get("purchase_date")) if isinstance(value, date)]
    period_start = min(dates) if dates else None
    period_end = max(dates) if dates else None
    report_kind = str(source["report_kind"])
    coverage = {
        "transactions": "normalized" if detail_rows else "not_available",
        "tax_lots": "normalized" if lots else "not_available",
        "current_holdings": (
            "normalized_browser_capture_needs_reconciliation" if holding_rows
            else "derived_fifo_for_source_period_not_broker_confirmed" if report_kind == "broker_transactions" and fifo_lots
            else "requires_holdings_statement" if report_kind == "aditya_birla_money_capital_gains"
            else "source_dependent"
        ),
        "cash": (
            "normalized_browser_capture_needs_reconciliation" if fund_rows
            else "requires_broker_ledger" if report_kind not in {"broker_ledger", "portfolio_snapshot"}
            else "source_dependent"
        ),
        "performance": "realized_only_not_total_return" if report_kind in {"aditya_birla_money_capital_gains", "tax_report"} else "source_dependent",
        "risk": "blocked_until_current_holdings_and_prices_reconcile",
        "methodology": "Source values are preserved; missing cash, open holdings, prices, and corporate actions are never estimated as final.",
    }
    quality_flags = sorted({item.code for item in exceptions})
    parser_summary = {
        "structured_tables": len(tables),
        "normalized_rows": len(rows),
        "detail_rows": len(detail_rows),
        "transaction_rows": len(transaction_rows),
        "holding_rows": len(holding_rows),
        "fund_balance_rows": len(fund_rows),
        "summary_rows": len(summary_rows),
        "derived_open_lots": len(fifo_lots),
        "reconciliation_basis": "detail_realized_gain_vs_report_summary" if summary_rows else "report_summary_missing",
        "raw_rows_returned_by_api": False,
    }
    run_psql(f"""
        UPDATE client_data.secure_client_imports
        SET parser_key={sql_literal(PARSER_KEY)},parser_version={sql_literal(PARSER_VERSION)},
            status={sql_literal(status)},identity_status={sql_literal(identity_status)},
            source_identity_hash={sql_literal(identity_hash)},
            source_period_start={sql_literal(period_start)}::date,
            source_period_end={sql_literal(period_end)}::date,
            source_as_of={sql_literal(datetime.combine(period_end, datetime.max.time()) if period_end else None)}::timestamptz,
            transaction_count={len(transaction_rows)},lot_count={len(lots)},charge_count={len(charge_rows)},
            tax_summary_count={len(summary_rows)},exception_count={len(exceptions)},
            reconciliation_status={sql_literal(reconciliation_status)},
            reconciliation_difference={sql_numeric(reconciliation_difference)},
            quality_flags=ARRAY[{','.join(sql_literal(flag) for flag in quality_flags)}]::text[],
            coverage={sql_json(coverage)},parser_summary={sql_json(parser_summary)},
            parsed_at=now(),reconciled_at=CASE WHEN {sql_literal(reconciliation_status)} IN ('matched','breaks') THEN now() ELSE reconciled_at END,
            updated_at=now()
        WHERE id={int(source['id'])};
        INSERT INTO client_data.client_import_audit (import_id,event_type,actor,event_status,metadata)
        VALUES ({int(source['id'])},'parser_run',{sql_literal(actor)},{sql_literal(status)},
                jsonb_build_object('parser_key',{sql_literal(PARSER_KEY)},'parser_version',{sql_literal(PARSER_VERSION)},
                                   'normalized_rows',{len(rows)},'exception_count',{len(exceptions)},
                                   'reconciliation_status',{sql_literal(reconciliation_status)}));
        INSERT INTO agent.inbox_items (title,owner_agent,status,priority,recommended_action,evidence,target_workspace)
        SELECT
            'Review secure client report ' || {sql_literal(import_key)},
            'Client Portfolio Manager Agent',
            'open',
            CASE WHEN {sql_literal(status)} IN ('blocked_identity_mismatch','stored_unparsed') THEN 'high' ELSE 'medium' END,
            'Resolve client/account identity, import exceptions, and broker reconciliation before any canonical portfolio promotion.',
            jsonb_build_array(jsonb_build_object('import_key',{sql_literal(import_key)},'status',{sql_literal(status)},
                                                 'checksum_prefix',{sql_literal(digest[:12])},'broker_write_allowed',false)),
            'portfolio'
        WHERE NOT EXISTS (
            SELECT 1 FROM agent.inbox_items WHERE title='Review secure client report ' || {sql_literal(import_key)} AND status IN ('open','in_progress')
        );
    """)
    reconcile_account_imports(int(source["account_id"]))
    reconciled = fetch_json(f"SELECT reconciliation_status,reconciliation_difference FROM client_data.secure_client_imports WHERE id={int(source['id'])}")
    if reconciled:
        reconciliation_status = str(reconciled[0].get("reconciliation_status") or reconciliation_status)
    return {
        "ok": True,
        "import_key": import_key,
        "status": status,
        "identity_status": identity_status,
        "checksum_prefix": digest[:12],
        "normalized_rows": len(rows),
        "lot_count": len(lots),
        "derived_open_lot_count": len(fifo_lots),
        "exception_count": len(exceptions),
        "reconciliation_status": reconciliation_status,
        "current_holdings_status": coverage["current_holdings"],
        "cash_status": coverage["cash"],
        "broker_write_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse one checksum-addressed client report without exposing raw rows.")
    parser.add_argument("--import-key", required=True)
    parser.add_argument("--actor", default="Client Data Steward")
    args = parser.parse_args()
    try:
        result = process_import(args.import_key, args.actor)
    except Exception as exc:  # noqa: BLE001
        try:
            run_psql(f"""
                UPDATE client_data.secure_client_imports
                SET status='failed',quality_flags=array_append(quality_flags,'parser_failed'),updated_at=now()
                WHERE import_key={sql_literal(args.import_key)};
            """)
        except Exception:
            pass
        print(json.dumps({"ok": False, "import_key": args.import_key, "error": type(exc).__name__, "message": str(exc)}))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
