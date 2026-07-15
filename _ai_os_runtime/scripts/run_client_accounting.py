#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT", Path(__file__).resolve().parents[1]))
POSTGRES_PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
POSTGRES_PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
PSQL_BIN = os.environ.get("AI_OS_PSQL_BIN", "/opt/homebrew/opt/postgresql@15/bin/psql")
DOCKER_BIN = os.environ.get("AI_OS_DOCKER_BIN", "/usr/local/bin/docker")


def psql_candidates() -> list[list[str]]:
    return [
        [PSQL_BIN, "-h", "127.0.0.1", "-p", POSTGRES_PORT, "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        [DOCKER_BIN, "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
    ]


def psql_text(sql: str) -> str:
    errors: list[str] = []
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", POSTGRES_PASSWORD)
    for command in psql_candidates():
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, env=env)
        if completed.returncode == 0:
            return completed.stdout.strip()
        errors.append((completed.stderr or completed.stdout).strip())
    raise RuntimeError(" | ".join(errors))


def psql_json(query: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM ({query}) rows;"
    return json.loads(psql_text(wrapped) or "[]")


def psql_json_statement(statement: str) -> list[dict[str, Any]]:
    """Execute a top-level data-modifying CTE whose final SELECT emits one JSON array."""
    return json.loads(psql_text(statement) or "[]")


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: Any) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def sql_numeric(value: Decimal | int | float | None) -> str:
    return "NULL" if value is None else str(value)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def contract_key(trade: dict[str, Any]) -> str:
    payload = trade.get("raw_payload") or {}
    parsed = payload.get("parsed") or {}
    expiry = payload.get("expiry_date") or payload.get("Expiry Date") or parsed.get("expiry_date") or ""
    strike = payload.get("strike_price") or payload.get("Strike Price") or parsed.get("strike_price") or ""
    option_type = payload.get("option_type") or payload.get("Option Type") or parsed.get("option_type") or ""
    components = [
        str(trade.get("symbol") or "").upper(),
        str(trade.get("exchange") or "").upper(),
        str(trade.get("instrument_type") or "").lower(),
        str(expiry), str(strike), str(option_type).upper(),
    ]
    return "|".join(components)


@dataclass
class Lot:
    opening_trade_id: int
    symbol: str
    contract_key: str
    exchange: str
    instrument_type: str
    direction: str
    opened_at: datetime
    original_quantity: Decimal
    remaining_quantity: Decimal
    unit_cost: Decimal


def assess_lot_coverage(run_id: int, account_id: int) -> dict[str, Any]:
    breaks = int(psql_text(
        f"""
        WITH lots AS (
            SELECT symbol,sum(CASE direction WHEN 'long' THEN remaining_quantity ELSE -remaining_quantity END) quantity
            FROM portfolio.tax_lots WHERE run_id={run_id} AND status='open' GROUP BY symbol
        ), positions AS (
            SELECT DISTINCT ON(symbol) symbol,quantity
            FROM portfolio.positions WHERE account_id={account_id}
            ORDER BY symbol,as_of DESC,id DESC
        ), compared AS (
            SELECT coalesce(l.symbol,p.symbol) symbol,coalesce(l.quantity,0)-coalesce(p.quantity,0) difference
            FROM lots l FULL JOIN positions p USING(symbol)
        ) SELECT count(*) FROM compared WHERE abs(difference)>0.000001;
        """
    ) or 0)
    status = "incomplete" if breaks else "completed"
    missing = ["transaction_history_for_current_positions"] if breaks else []
    psql_text(
        f"UPDATE portfolio.tax_lot_runs SET status={sql_literal(status)},position_break_count={breaks},"
        f"missing_inputs=ARRAY[{','.join(sql_literal(item) for item in missing)}]::text[],completed_at=coalesce(completed_at,now()) WHERE id={run_id};"
    )
    return {"status": status, "position_break_count": breaks, "missing_inputs": missing}


def import_trade_settlements(account: dict[str, Any], trades: list[dict[str, Any]]) -> int:
    rows: list[str] = []
    for trade in trades:
        payload = trade.get("raw_payload") or {}
        amount = decimal(payload.get("Amount"))
        if amount is None or amount == 0:
            continue
        side = str(trade.get("side") or "").lower()
        signed_amount = -abs(amount) if side == "buy" else abs(amount)
        rows.append(
            "(" + ",".join([
                sql_literal(f"trade-settlement-{trade['id']}"), str(account["client_id"]), str(account["account_id"]),
                f"{sql_literal(trade['trade_ts'])}::timestamptz", "'trade_settlement'", "'internal'", str(signed_amount),
                sql_literal(account.get("base_currency") or "INR"), sql_literal(f"Trade settlement {side} {trade['symbol']}"),
                str(trade["source_system_id"]) if trade.get("source_system_id") else "NULL", sql_literal(trade.get("external_ref") or f"portfolio.trades:{trade['id']}"),
                sql_jsonb([{"table": "portfolio.trades", "id": trade["id"], "source_ref": trade.get("external_ref")}]),
                "'posted'", "'Data Steward'", "now()"
            ]) + ")"
        )
    if not rows:
        return 0
    psql_text(
        "INSERT INTO portfolio.cash_ledger_entries(entry_key,client_id,account_id,entry_ts,entry_type,flow_class,amount,currency,description,source_system_id,source_ref,source_evidence,status,created_by,posted_at) VALUES\n"
        + ",\n".join(rows)
        + " ON CONFLICT(entry_key) DO UPDATE SET source_evidence=EXCLUDED.source_evidence,updated_at=now();"
    )
    return len(rows)


def rebuild_tax_lots(account: dict[str, Any], trades: list[dict[str, Any]], actor: str) -> dict[str, Any]:
    fingerprint = hashlib.sha256(json.dumps([
        [row["id"], row.get("trade_ts"), row.get("side"), row.get("quantity"), row.get("price"), contract_key(row)]
        for row in trades
    ], sort_keys=True, default=str).encode()).hexdigest()[:20]
    run_key = f"fifo-{account['account_code']}-{fingerprint}"
    existing = psql_json(f"SELECT id,status,trade_count,open_lot_count,match_count,realized_pnl FROM portfolio.tax_lot_runs WHERE run_key={sql_literal(run_key)}")
    if existing:
        coverage = assess_lot_coverage(int(existing[0]["id"]), int(account["account_id"]))
        return {**existing[0], **coverage, "run_key": run_key, "reused": True}

    run = psql_json_statement(
        f"WITH inserted AS (INSERT INTO portfolio.tax_lot_runs(run_key,client_id,account_id,method,status,trade_count,evidence,created_by) "
        f"VALUES({sql_literal(run_key)},{account['client_id']},{account['account_id']},'FIFO','running',{len(trades)},"
        f"{sql_jsonb([{'table':'portfolio.trades','account_id':account['account_id'],'trade_count':len(trades),'fingerprint':fingerprint}])},{sql_literal(actor)}) RETURNING id) "
        "SELECT coalesce(json_agg(row_to_json(inserted)),'[]'::json)::text FROM inserted"
    )[0]
    run_id = int(run["id"])
    queues: dict[str, dict[str, deque[Lot]]] = defaultdict(lambda: {"long": deque(), "short": deque()})
    all_lots: list[Lot] = []
    matches: list[dict[str, Any]] = []

    for trade in trades:
        side = str(trade.get("side") or "").lower()
        quantity = decimal(trade.get("quantity"), Decimal("0")) or Decimal("0")
        price = decimal(trade.get("price"))
        if side not in {"buy", "sell"} or quantity <= 0 or price is None or price < 0 or not trade.get("trade_ts"):
            continue
        key = contract_key(trade)
        closing_direction = "short" if side == "buy" else "long"
        opening_direction = "long" if side == "buy" else "short"
        remaining = quantity
        opened_queue = queues[key][closing_direction]
        close_ts = parse_ts(str(trade["trade_ts"]))

        while remaining > 0 and opened_queue:
            lot = opened_queue[0]
            matched = min(remaining, lot.remaining_quantity)
            pnl = (price - lot.unit_cost) * matched if lot.direction == "long" else (lot.unit_cost - price) * matched
            holding_days = max(0, (close_ts.date() - lot.opened_at.date()).days)
            matches.append({
                "opening_trade_id": lot.opening_trade_id, "closing_trade_id": int(trade["id"]),
                "symbol": lot.symbol, "contract_key": key, "exchange": lot.exchange,
                "instrument_type": lot.instrument_type, "direction": lot.direction,
                "opened_at": lot.opened_at.isoformat(), "closed_at": close_ts.isoformat(),
                "matched_quantity": matched, "opening_price": lot.unit_cost, "closing_price": price,
                "gross_realized_pnl": pnl, "holding_days": holding_days,
                "tax_term": "intraday" if holding_days == 0 else ("long_term" if holding_days > 365 else "short_term"),
            })
            lot.remaining_quantity -= matched
            remaining -= matched
            if lot.remaining_quantity == 0:
                opened_queue.popleft()

        if remaining > 0:
            lot = Lot(
                opening_trade_id=int(trade["id"]), symbol=str(trade["symbol"]), contract_key=key,
                exchange=str(trade.get("exchange") or ""), instrument_type=str(trade.get("instrument_type") or "equity"),
                direction=opening_direction, opened_at=close_ts, original_quantity=remaining,
                remaining_quantity=remaining, unit_cost=price,
            )
            queues[key][opening_direction].append(lot)
            all_lots.append(lot)

    lot_values = []
    for lot in all_lots:
        lot_values.append(
            "(" + ",".join([
                str(run_id), str(account["client_id"]), str(account["account_id"]), str(lot.opening_trade_id),
                sql_literal(lot.symbol), sql_literal(lot.contract_key), sql_literal(lot.exchange), sql_literal(lot.instrument_type),
                sql_literal(lot.direction), f"{sql_literal(lot.opened_at.isoformat())}::timestamptz", str(lot.original_quantity),
                str(lot.remaining_quantity), str(lot.unit_cost), str(lot.remaining_quantity * lot.unit_cost),
                sql_literal("open" if lot.remaining_quantity > 0 else "closed"),
                sql_jsonb([{"table": "portfolio.trades", "id": lot.opening_trade_id}])
            ]) + ")"
        )
    if lot_values:
        psql_text("INSERT INTO portfolio.tax_lots(run_id,client_id,account_id,opening_trade_id,symbol,contract_key,exchange,instrument_type,direction,opened_at,original_quantity,remaining_quantity,unit_cost,cost_basis,status,source_evidence) VALUES\n" + ",\n".join(lot_values) + ";")

    match_values = []
    for match in matches:
        match_values.append(
            "(" + ",".join([
                str(run_id), str(account["client_id"]), str(account["account_id"]), str(match["opening_trade_id"]), str(match["closing_trade_id"]),
                sql_literal(match["symbol"]), sql_literal(match["contract_key"]), sql_literal(match["exchange"]), sql_literal(match["instrument_type"]),
                sql_literal(match["direction"]), f"{sql_literal(match['opened_at'])}::timestamptz", f"{sql_literal(match['closed_at'])}::timestamptz",
                str(match["matched_quantity"]), str(match["opening_price"]), str(match["closing_price"]), str(match["gross_realized_pnl"]),
                "0", str(match["gross_realized_pnl"]), str(match["holding_days"]), sql_literal(match["tax_term"]),
                sql_jsonb([{"table":"portfolio.trades","id":match["opening_trade_id"]},{"table":"portfolio.trades","id":match["closing_trade_id"]}])
            ]) + ")"
        )
    if match_values:
        psql_text("INSERT INTO portfolio.tax_lot_matches(run_id,client_id,account_id,opening_trade_id,closing_trade_id,symbol,contract_key,exchange,instrument_type,direction,opened_at,closed_at,matched_quantity,opening_price,closing_price,gross_realized_pnl,allocated_fees,net_realized_pnl,holding_days,tax_term,evidence) VALUES\n" + ",\n".join(match_values) + ";")

    realized = sum((match["gross_realized_pnl"] for match in matches), Decimal("0"))
    open_count = sum(1 for lot in all_lots if lot.remaining_quantity > 0)
    psql_text(
        f"UPDATE portfolio.tax_lot_runs SET status='completed',open_lot_count={open_count},match_count={len(matches)},"
        f"realized_pnl={realized},completed_at=now() WHERE id={run_id};"
    )
    coverage = assess_lot_coverage(run_id, int(account["account_id"]))
    return {"id": run_id, "run_key": run_key, **coverage, "trade_count": len(trades), "open_lot_count": open_count, "match_count": len(matches), "realized_pnl": str(realized), "reused": False}


def refresh_benchmark() -> int:
    result = psql_text(
        """
        WITH inserted AS (
            INSERT INTO portfolio.benchmark_observations(
                benchmark_key,observation_date,close_value,currency,source_system_id,source_ref,evidence
            )
            SELECT 'NIFTY_50',o.ts::date,o.close,coalesce(s.currency,'INR'),o.source_system_id,
                   'trading.ohlcv:'||s.id||':'||o.ts::date,
                   jsonb_build_array(jsonb_build_object('table','trading.ohlcv','symbol_id',s.id,'ts',o.ts,'timeframe',o.timeframe))
            FROM trading.ohlcv o JOIN trading.symbols s ON s.id=o.symbol_id
            WHERE s.symbol='NIFTY 50' AND o.timeframe='1d' AND o.close>0
            ON CONFLICT(benchmark_key,observation_date,source_ref) DO UPDATE SET
                close_value=EXCLUDED.close_value,evidence=EXCLUDED.evidence,observed_at=now()
            RETURNING 1
        ) SELECT count(*) FROM inserted;
        """
    )
    return int(result or 0)


def rebuild_nav(account: dict[str, Any]) -> int:
    # Broker/account snapshots are authoritative. Current holdings without cash evidence remain explicitly incomplete.
    psql_text(
        f"""
        INSERT INTO portfolio.nav_snapshots(
            client_id,account_id,nav_date,securities_market_value,cash_balance,nav,
            external_flow,income_flow,expense_flow,realized_pnl,unrealized_pnl,
            calculation_status,missing_inputs,source_snapshot_id,evidence,calculated_at
        )
        SELECT {account['client_id']},{account['account_id']},s.ts::date,
               CASE WHEN s.equity IS NOT NULL AND s.cash IS NOT NULL THEN s.equity-s.cash ELSE NULL END,
               s.cash,s.equity,
               coalesce((SELECT sum(e.amount) FROM portfolio.cash_ledger_entries e WHERE e.account_id=s.account_id AND e.status='posted' AND e.flow_class='external' AND e.entry_ts::date=s.ts::date),0),
               coalesce((SELECT sum(e.amount) FROM portfolio.cash_ledger_entries e WHERE e.account_id=s.account_id AND e.status='posted' AND e.flow_class='income' AND e.entry_ts::date=s.ts::date),0),
               abs(coalesce((SELECT sum(e.amount) FROM portfolio.cash_ledger_entries e WHERE e.account_id=s.account_id AND e.status='posted' AND e.flow_class='expense' AND e.entry_ts::date=s.ts::date),0)),
               coalesce((SELECT sum(m.net_realized_pnl) FROM portfolio.tax_lot_matches m JOIN portfolio.tax_lot_runs r ON r.id=m.run_id WHERE m.account_id=s.account_id AND r.id=(SELECT id FROM portfolio.tax_lot_runs WHERE account_id=s.account_id AND status='completed' ORDER BY completed_at DESC LIMIT 1) AND m.closed_at::date=s.ts::date),0),
               s.pnl_total,
               'source_snapshot',CASE WHEN s.cash IS NULL THEN ARRAY['cash_breakdown']::text[] ELSE ARRAY[]::text[] END,
               'portfolio.snapshots:'||s.account_id||':'||s.ts,
               jsonb_build_array(jsonb_build_object('table','portfolio.snapshots','account_id',s.account_id,'ts',s.ts)),now()
        FROM portfolio.snapshots s WHERE s.account_id={account['account_id']} AND s.equity IS NOT NULL
        ON CONFLICT(account_id,nav_date) DO UPDATE SET
            cash_balance=EXCLUDED.cash_balance,nav=EXCLUDED.nav,external_flow=EXCLUDED.external_flow,
            income_flow=EXCLUDED.income_flow,expense_flow=EXCLUDED.expense_flow,
            realized_pnl=EXCLUDED.realized_pnl,unrealized_pnl=EXCLUDED.unrealized_pnl,
            calculation_status=EXCLUDED.calculation_status,missing_inputs=EXCLUDED.missing_inputs,
            source_snapshot_id=EXCLUDED.source_snapshot_id,evidence=EXCLUDED.evidence,calculated_at=now();
        """
    )
    current = psql_json(
        f"""
        WITH latest AS (
            SELECT DISTINCT ON (symbol,exchange,instrument_type) *
            FROM portfolio.positions WHERE account_id={account['account_id']}
            ORDER BY symbol,exchange,instrument_type,as_of DESC,id DESC
        ), values AS (
            SELECT max(as_of)::date nav_date,sum(market_value) securities_market_value,
                   sum(unrealized_pnl) unrealized_pnl,count(*) FILTER(WHERE market_value IS NULL) missing_prices
            FROM latest
        ), cash AS (
            SELECT sum(amount) FILTER(WHERE status='posted') cash_balance,
                   count(*) FILTER(WHERE status='posted' AND entry_type='opening_balance') opening_count
            FROM portfolio.cash_ledger_entries WHERE account_id={account['account_id']}
        ) SELECT * FROM values CROSS JOIN cash WHERE nav_date IS NOT NULL
        """
    )
    if current:
        row = current[0]
        cash = decimal(row.get("cash_balance")) if int(row.get("opening_count") or 0) > 0 else None
        securities = decimal(row.get("securities_market_value"))
        missing: list[str] = []
        if cash is None:
            missing.append("opening_cash_balance")
        if int(row.get("missing_prices") or 0):
            missing.append("position_market_values")
        nav = securities + cash if securities is not None and cash is not None and not missing else None
        psql_text(
            f"""
            INSERT INTO portfolio.nav_snapshots(client_id,account_id,nav_date,securities_market_value,cash_balance,nav,
                unrealized_pnl,calculation_status,missing_inputs,source_snapshot_id,evidence)
            VALUES({account['client_id']},{account['account_id']},{sql_literal(row['nav_date'])}::date,
                {sql_numeric(securities)},{sql_numeric(cash)},{sql_numeric(nav)},{sql_numeric(decimal(row.get('unrealized_pnl')))},
                {sql_literal('complete' if nav is not None else 'incomplete')},ARRAY[{','.join(sql_literal(item) for item in missing)}]::text[],
                {sql_literal('portfolio.positions:latest')},
                {sql_jsonb([{'view':'portfolio.v_latest_positions','account_id':account['account_id']}])})
            ON CONFLICT(account_id,nav_date) DO UPDATE SET securities_market_value=EXCLUDED.securities_market_value,
                cash_balance=coalesce(portfolio.nav_snapshots.cash_balance,EXCLUDED.cash_balance),
                nav=coalesce(portfolio.nav_snapshots.nav,EXCLUDED.nav),unrealized_pnl=EXCLUDED.unrealized_pnl,
                calculation_status=CASE WHEN portfolio.nav_snapshots.nav IS NOT NULL THEN portfolio.nav_snapshots.calculation_status ELSE EXCLUDED.calculation_status END,
                missing_inputs=CASE WHEN portfolio.nav_snapshots.nav IS NOT NULL THEN portfolio.nav_snapshots.missing_inputs ELSE EXCLUDED.missing_inputs END,
                evidence=portfolio.nav_snapshots.evidence||EXCLUDED.evidence,calculated_at=now();
            """
        )
    return int(psql_text(f"SELECT count(*) FROM portfolio.nav_snapshots WHERE account_id={account['account_id']};") or 0)


def rebuild_performance(account: dict[str, Any]) -> int:
    psql_text(f"DELETE FROM portfolio.performance_periods WHERE account_id={account['account_id']};")
    navs = psql_json(f"SELECT nav_date,nav FROM portfolio.nav_snapshots WHERE account_id={account['account_id']} ORDER BY nav_date")
    if not navs:
        return 0
    periods: list[tuple[date, date, str]] = []
    for left, right in zip(navs, navs[1:]):
        periods.append((date.fromisoformat(str(left["nav_date"])), date.fromisoformat(str(right["nav_date"])), "day"))
    first = date.fromisoformat(str(navs[0]["nav_date"]))
    last = date.fromisoformat(str(navs[-1]["nav_date"]))
    if first != last:
        periods.append((first, last, "since_inception"))
    else:
        periods.append((first, last, "since_inception"))

    inserted = 0
    for start, end, period_type in periods:
        opening = next((decimal(row.get("nav")) for row in navs if str(row["nav_date"]) == start.isoformat()), None)
        closing = next((decimal(row.get("nav")) for row in navs if str(row["nav_date"]) == end.isoformat()), None)
        flows = psql_json(
            f"SELECT coalesce(sum(amount) FILTER(WHERE flow_class='external'),0) external_flows,"
            f"coalesce(sum(amount) FILTER(WHERE flow_class='income'),0) income,"
            f"abs(coalesce(sum(amount) FILTER(WHERE flow_class='expense'),0)) expenses "
            f"FROM portfolio.cash_ledger_entries WHERE account_id={account['account_id']} AND status='posted' AND entry_ts::date>{sql_literal(start)}::date AND entry_ts::date<={sql_literal(end)}::date"
        )[0]
        external = decimal(flows.get("external_flows"), Decimal("0")) or Decimal("0")
        income = decimal(flows.get("income"), Decimal("0")) or Decimal("0")
        expenses = decimal(flows.get("expenses"), Decimal("0")) or Decimal("0")
        realized = decimal(psql_text(
            f"SELECT coalesce(sum(m.net_realized_pnl),0) FROM portfolio.tax_lot_matches m WHERE m.run_id=(SELECT id FROM portfolio.tax_lot_runs WHERE account_id={account['account_id']} AND status='completed' ORDER BY completed_at DESC LIMIT 1) AND m.closed_at::date BETWEEN {sql_literal(start)}::date AND {sql_literal(end)}::date"
        ), Decimal("0")) or Decimal("0")
        missing: list[str] = []
        period_return: Decimal | None = None
        if opening is None or closing is None or opening == 0:
            missing.append("opening_or_closing_nav")
        else:
            denominator = opening + (external / Decimal("2"))
            if denominator == 0:
                missing.append("nonzero_return_denominator")
            else:
                period_return = ((closing - opening - external) / denominator) * Decimal("100")
        benchmark = psql_json(
            f"SELECT (SELECT close_value FROM portfolio.benchmark_observations WHERE benchmark_key='NIFTY_50' AND observation_date<={sql_literal(start)}::date ORDER BY observation_date DESC LIMIT 1) opening,"
            f"(SELECT close_value FROM portfolio.benchmark_observations WHERE benchmark_key='NIFTY_50' AND observation_date<={sql_literal(end)}::date ORDER BY observation_date DESC LIMIT 1) closing"
        )[0]
        benchmark_open = decimal(benchmark.get("opening"))
        benchmark_close = decimal(benchmark.get("closing"))
        benchmark_return = ((benchmark_close / benchmark_open) - 1) * 100 if benchmark_open and benchmark_close else None
        if benchmark_return is None:
            missing.append("benchmark_observations")
        status = "complete" if period_return is not None else "incomplete"
        active_return = period_return - benchmark_return if period_return is not None and benchmark_return is not None else None
        result = psql_json_statement(
            f"""
            WITH inserted AS (INSERT INTO portfolio.performance_periods(client_id,account_id,period_type,period_start,period_end,
                opening_nav,closing_nav,external_flows,income,expenses,realized_pnl,twr_return_pct,
                money_weighted_return_pct,benchmark_key,benchmark_return_pct,active_return_pct,
                calculation_status,missing_inputs,evidence)
            VALUES({account['client_id']},{account['account_id']},{sql_literal(period_type)},{sql_literal(start)}::date,{sql_literal(end)}::date,
                {sql_numeric(opening)},{sql_numeric(closing)},{external},{income},{expenses},{realized},
                {sql_numeric(period_return)},{sql_numeric(period_return)},'NIFTY_50',{sql_numeric(benchmark_return)},
                {sql_numeric(active_return)},{sql_literal(status)},ARRAY[{','.join(sql_literal(item) for item in missing)}]::text[],
                {sql_jsonb([{'table':'portfolio.nav_snapshots','account_id':account['account_id'],'start':start,'end':end},{'table':'portfolio.benchmark_observations','benchmark_key':'NIFTY_50'}])})
            RETURNING id) SELECT coalesce(json_agg(row_to_json(inserted)),'[]'::json)::text FROM inserted
            """
        )
        period_id = int(result[0]["id"])
        psql_text(
            f"""
            INSERT INTO portfolio.performance_attribution(performance_period_id,attribution_type,attribution_key,
                realized_pnl,income,fees,contribution_amount,contribution_pct,calculation_status,evidence)
            SELECT {period_id},'symbol',m.symbol,sum(m.net_realized_pnl),0,0,sum(m.net_realized_pnl),
                   CASE WHEN {sql_numeric(opening)} IS NOT NULL AND {sql_numeric(opening)}<>0 THEN sum(m.net_realized_pnl)/{sql_numeric(opening)}*100 ELSE NULL END,
                   CASE WHEN {sql_numeric(opening)} IS NOT NULL AND {sql_numeric(opening)}<>0 THEN 'complete' ELSE 'partial' END,
                   jsonb_agg(jsonb_build_object('table','portfolio.tax_lot_matches','id',m.id))
            FROM portfolio.tax_lot_matches m
            WHERE m.run_id=(SELECT id FROM portfolio.tax_lot_runs WHERE account_id={account['account_id']} AND status='completed' ORDER BY completed_at DESC LIMIT 1)
              AND m.closed_at::date BETWEEN {sql_literal(start)}::date AND {sql_literal(end)}::date
            GROUP BY m.symbol
            ON CONFLICT(performance_period_id,attribution_type,attribution_key) DO UPDATE SET
                realized_pnl=EXCLUDED.realized_pnl,contribution_amount=EXCLUDED.contribution_amount,
                contribution_pct=EXCLUDED.contribution_pct,evidence=EXCLUDED.evidence;
            """
        )
        inserted += 1
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild source-backed client cash, FIFO tax lots, NAV, and performance.")
    parser.add_argument("--account-code", default="")
    parser.add_argument("--actor", default="Performance Attribution Agent")
    args = parser.parse_args()

    where = f"AND a.account_code={sql_literal(args.account_code)}" if args.account_code else ""
    accounts = psql_json(
        f"SELECT a.id account_id,a.account_code,a.base_currency,a.client_id,c.client_code,c.display_name "
        f"FROM portfolio.accounts a JOIN portfolio.clients c ON c.id=a.client_id WHERE a.active=true {where} ORDER BY a.account_code"
    )
    if not accounts:
        raise SystemExit("No active client account matched the request.")

    benchmark_rows = refresh_benchmark()
    summaries: list[dict[str, Any]] = []
    for account in accounts:
        trades = psql_json(
            f"SELECT id,source_system_id,symbol,exchange,instrument_type,lower(side) side,quantity,price,trade_ts,external_ref,raw_payload "
            f"FROM portfolio.trades WHERE account_id={account['account_id']} ORDER BY trade_ts,id"
        )
        settlements = import_trade_settlements(account, trades)
        lot_run = rebuild_tax_lots(account, trades, args.actor)
        nav_count = rebuild_nav(account)
        performance_count = rebuild_performance(account)
        summaries.append({
            "client_code": account["client_code"], "account_code": account["account_code"],
            "trade_count": len(trades), "trade_settlements": settlements,
            "tax_lot_run": lot_run, "nav_snapshot_count": nav_count,
            "performance_period_count": performance_count,
        })

    result = {
        "status": "completed", "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_rows_refreshed": benchmark_rows, "account_count": len(accounts),
        "accounts": summaries,
        "methodology": "FIFO long/short tax lots; broker NAV preferred; Modified Dietz period return; missing inputs remain incomplete",
    }
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
