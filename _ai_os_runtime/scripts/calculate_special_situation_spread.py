#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


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


def clean(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip() or fallback


def decimal_from_text(value: object) -> Decimal | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def decimal_literal(value: Decimal | None) -> str:
    return "NULL" if value is None else str(value)


def fetch_memo(memo_id: int) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT
                memo.*,
                terms.offer_price,
                terms.issue_price,
                terms.cash_consideration,
                terms.closing_date,
                terms.opening_date,
                terms.record_date
            FROM research.v_special_situation_memos memo
            JOIN research.special_situation_terms terms ON terms.id = memo.special_terms_id
            WHERE memo.id = {memo_id}
        ) rows
        """
    )
    if not rows:
        raise ValueError(f"special situation memo {memo_id} not found")
    return rows[0]


def fetch_latest_quote(symbol: str) -> dict[str, Any] | None:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT *
            FROM market.v_latest_price_quotes
            WHERE upper(symbol) = upper({sql_literal(symbol)})
            LIMIT 1
        ) rows
        """
    )
    return rows[0] if rows else None


def target_price_for(row: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    event_type = clean(row.get("event_type")).lower()
    if event_type in {"buyback", "open_offer", "delisting"}:
        return decimal_from_text(row.get("offer_price")), "offer_price"
    if event_type in {"rights_issue", "preferential_allotment"}:
        return decimal_from_text(row.get("issue_price")), "issue_price"
    return decimal_from_text(row.get("cash_consideration")), "cash_consideration"


def days_to_close(row: dict[str, Any]) -> int | None:
    text = clean(row.get("closing_date"))
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            close_date = datetime.strptime(text, fmt).date()
            return max((close_date - datetime.now(timezone.utc).date()).days, 0)
        except ValueError:
            continue
    return None


def calculate(memo_id: int, actor: str) -> dict[str, Any]:
    memo = fetch_memo(memo_id)
    symbol = clean(memo.get("symbol"), clean(memo.get("company_name"), "")).upper()
    target_price, target_source = target_price_for(memo)
    quote = fetch_latest_quote(symbol) if symbol else None
    flags: list[dict[str, str]] = []
    market_price: Decimal | None = None
    gross_abs: Decimal | None = None
    gross_pct: Decimal | None = None
    annualized: Decimal | None = None
    check_status = "tracked"
    close_days = days_to_close(memo)

    if target_price is None:
        check_status = "missing_event_price"
        flags.append({"flag": "missing_event_price", "detail": "No numeric target/offer/issue/cash price is available from extracted terms."})
    if quote is None:
        check_status = "missing_market_quote" if check_status == "tracked" else check_status
        flags.append({"flag": "missing_market_quote", "detail": f"No stored latest quote found for {symbol} in market.v_latest_price_quotes."})
    else:
        market_price = decimal_from_text(quote.get("price"))
        if market_price is None:
            check_status = "invalid_market_quote"
            flags.append({"flag": "invalid_market_quote", "detail": "Latest quote exists but price is not numeric."})

    if target_price is not None and market_price is not None and market_price != 0:
        gross_abs = target_price - market_price
        gross_pct = ((target_price / market_price) - Decimal("1")) * Decimal("100")
        if close_days and close_days > 0:
            annualized = gross_pct * (Decimal("365") / Decimal(close_days))
        if close_days is None:
            flags.append({"flag": "closing_date_unparsed", "detail": "Closing date was missing or could not be parsed for annualized spread."})

    scenario = {
        "calculation": "target_price_minus_market_price",
        "event_type": memo.get("event_type"),
        "target_price_source": target_source,
        "monitor_only": True,
        "trade_allowed": False,
        "client_recommendation_allowed": False,
        "missing_inputs": [flag["flag"] for flag in flags],
    }
    quote_ts = quote.get("quote_ts") if quote else None
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO research.special_situation_spread_checks (
                special_memo_id, special_terms_id, filing_id, symbol, event_type,
                target_price, target_price_source, market_price, market_price_source,
                quote_id, quote_ts, quote_staleness_minutes, gross_spread_abs,
                gross_spread_pct, annualized_spread_pct, days_to_close,
                scenario_payload, status, data_quality_flags, created_by
            )
            VALUES (
                {memo['id']},
                {memo['special_terms_id']},
                {memo.get('filing_id') or 'NULL'},
                {sql_literal(symbol)},
                {sql_literal(clean(memo.get('event_type'), 'event'))},
                {decimal_literal(target_price)},
                {sql_literal(target_source)},
                {decimal_literal(market_price)},
                {sql_literal(clean(quote.get('source_key')) if quote else None)},
                {quote.get('id') if quote else 'NULL'},
                {sql_literal(quote_ts)},
                CASE WHEN {sql_literal(quote_ts)} IS NULL THEN NULL ELSE EXTRACT(EPOCH FROM (now() - {sql_literal(quote_ts)}::timestamptz)) / 60 END,
                {decimal_literal(gross_abs)},
                {decimal_literal(gross_pct)},
                {decimal_literal(annualized)},
                {close_days if close_days is not None else 'NULL'},
                {sql_jsonb(scenario)},
                {sql_literal(check_status)},
                {sql_jsonb(flags)},
                {sql_literal(actor)}
            )
            RETURNING id, special_memo_id, special_terms_id, symbol, event_type,
                      target_price, market_price, gross_spread_pct, annualized_spread_pct,
                      days_to_close, status, data_quality_flags, created_at
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    if not rows:
        raise RuntimeError("spread check insert did not return a row")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate special-situation spread from stored event terms and latest stored quote.")
    parser.add_argument("--special-memo-id", type=int, required=True)
    parser.add_argument("--actor", default="Event Arbitrage Analyst")
    args = parser.parse_args()
    result = calculate(args.special_memo_id, args.actor)
    print(json.dumps({"special_memo_id": args.special_memo_id, "spread_check": result}, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
