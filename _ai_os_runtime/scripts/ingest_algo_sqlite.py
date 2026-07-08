#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ALGO_ROOT = Path("/Volumes/Devarsh SSD/algo based trading software 2")
TRADES_DB = ALGO_ROOT / "data" / "trades.db"
APP_DB = ALGO_ROOT / "data" / "storage" / "app.db"
PRICES_DB = ALGO_ROOT / "data" / "storage" / "prices.db"
OUTPUT_PATH = RUNTIME_ROOT / "imports" / "algo_import_summary.json"


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(sanitize_json(value), sort_keys=True, default=str, allow_nan=False)) + "::jsonb"


def sanitize_json(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    return value


def sqlite_rows(path: Path, table_name: str) -> list[dict]:
    if not path.exists():
        return []
    uri = f"file:{path}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(f'select * from "{table_name}"').fetchall()
        except sqlite3.DatabaseError:
            return []
        return [dict(row) for row in rows]


def table_count(path: Path, table_name: str) -> int:
    if not path.exists():
        return 0
    uri = f"file:{path}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=10) as connection:
        try:
            return int(connection.execute(f'select count(*) from "{table_name}"').fetchone()[0])
        except sqlite3.DatabaseError:
            return 0


def parse_json_maybe(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def run_psql(sql: str, quiet: bool = True) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    if quiet:
        command.insert(5, "-q")
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    return completed.stdout


def run_scalar(sql: str) -> int:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    text = completed.stdout.strip()
    return int(text or "0")


def copy_rows(
    setup_sql: str,
    copy_sql: str,
    rows: Iterable[list[object]],
    transform_sql: str,
) -> int:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdin is not None
    process.stdin.write("BEGIN;\n")
    process.stdin.write(setup_sql.rstrip() + "\n")
    process.stdin.write(copy_sql.rstrip() + "\n")
    writer = csv.writer(process.stdin, lineterminator="\n")
    count = 0
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
        count += 1
    process.stdin.write("\\.\n")
    process.stdin.write(transform_sql.rstrip() + "\n")
    process.stdin.write("COMMIT;\n")
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        sys.stderr.write(stdout)
        sys.stderr.write(stderr)
        raise SystemExit(process.returncode)
    return count


def import_small_tables() -> dict:
    app_accounts = sqlite_rows(APP_DB, "accounts")
    app_holdings = sqlite_rows(APP_DB, "holdings")
    app_snapshots = sqlite_rows(APP_DB, "portfolio_snapshots")
    app_trades = sqlite_rows(APP_DB, "trades")
    tradebook_trades = sqlite_rows(TRADES_DB, "trades")
    app_journal = sqlite_rows(APP_DB, "journal")
    app_signals = sqlite_rows(APP_DB, "tradingview_signals")
    app_ideas = sqlite_rows(APP_DB, "ideas")
    app_watchlist = sqlite_rows(APP_DB, "watchlist")
    backtests = sqlite_rows(PRICES_DB, "backtest_runs")
    regimes = sqlite_rows(PRICES_DB, "regime_runs")
    token_map = sqlite_rows(PRICES_DB, "token_map")

    statements = ["BEGIN;"]

    for row in app_accounts:
        statements.append(
            f"""
INSERT INTO portfolio.accounts (account_code, account_name, account_type, broker, base_currency, active)
VALUES (
    {sql_quote(row.get("code"))},
    {sql_quote(row.get("name") or row.get("code"))},
    {sql_quote(row.get("kind"))},
    'legacy_algo',
    'INR',
    true
)
ON CONFLICT (account_code) DO UPDATE SET
    account_name = EXCLUDED.account_name,
    account_type = EXCLUDED.account_type,
    broker = EXCLUDED.broker,
    active = true;
"""
        )

    for row in token_map:
        statements.append(
            f"""
INSERT INTO trading.symbols (symbol, exchange, instrument_type, active)
VALUES ({sql_quote(row.get("symbol"))}, 'NSE', 'equity', true)
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;
"""
        )

    for row in app_holdings:
        payload = {**row, "__source_table": "app.holdings"}
        statements.append(
            f"""
INSERT INTO trading.symbols (symbol, exchange, instrument_type, active)
VALUES ({sql_quote(row.get("symbol"))}, {sql_quote(row.get("exchange") or "NSE")}, 'equity', true)
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;
"""
        )
        statements.append(
            f"""
WITH account_lookup AS (
    SELECT acct.id
    FROM portfolio.accounts acct
    JOIN (
        SELECT code FROM (
            SELECT code, id FROM (VALUES {','.join(f"({sql_quote(a.get('code'))},{a.get('id')})" for a in app_accounts) if app_accounts else "(NULL,NULL)"}) AS a(code, id)
        ) legacy
        WHERE legacy.id = {sql_quote(row.get("account_id"))}
    ) legacy_account ON legacy_account.code = acct.account_code
    LIMIT 1
),
source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
)
INSERT INTO portfolio.positions (
    account_id,
    symbol,
    exchange,
    instrument_type,
    quantity,
    average_price,
    market_price,
    market_value,
    unrealized_pnl,
    as_of,
    source_system_id,
    payload
)
SELECT
    account_lookup.id,
    {sql_quote(row.get("symbol"))},
    {sql_quote(row.get("exchange") or "NSE")},
    'equity',
    {sql_quote(row.get("quantity"))}::numeric,
    {sql_quote(row.get("avg_price"))}::numeric,
    {sql_quote(row.get("last_price"))}::numeric,
    ({sql_quote(row.get("quantity"))}::numeric * {sql_quote(row.get("last_price"))}::numeric),
    (({sql_quote(row.get("last_price"))}::numeric - {sql_quote(row.get("avg_price"))}::numeric) * {sql_quote(row.get("quantity"))}::numeric),
    coalesce({sql_quote(row.get("opened_at"))}::timestamptz, now()),
    source_lookup.id,
    {jsonb_quote(payload)}
FROM account_lookup, source_lookup
ON CONFLICT (account_id, symbol, exchange, instrument_type, as_of) DO UPDATE SET
    quantity = EXCLUDED.quantity,
    average_price = EXCLUDED.average_price,
    market_price = EXCLUDED.market_price,
    market_value = EXCLUDED.market_value,
    unrealized_pnl = EXCLUDED.unrealized_pnl,
    payload = EXCLUDED.payload;
"""
        )

    account_values = ",".join(f"({a.get('id')},{sql_quote(a.get('code'))})" for a in app_accounts) or "(NULL,NULL)"

    for row in app_snapshots:
        payload = {**row, "__source_table": "app.portfolio_snapshots"}
        statements.append(
            f"""
WITH legacy_accounts(legacy_id, account_code) AS (VALUES {account_values}),
account_lookup AS (
    SELECT acct.id
    FROM legacy_accounts legacy
    JOIN portfolio.accounts acct ON acct.account_code = legacy.account_code
    WHERE legacy.legacy_id = {sql_quote(row.get("account_id"))}::bigint
    LIMIT 1
)
INSERT INTO portfolio.snapshots (
    ts,
    account_id,
    equity,
    cash,
    margin_used,
    pnl_day,
    pnl_total,
    payload
)
SELECT
    coalesce({sql_quote(row.get("ts"))}::timestamptz, {sql_quote(row.get("d"))}::date::timestamptz, now()),
    account_lookup.id,
    {sql_quote(row.get("total_equity"))}::numeric,
    {sql_quote(row.get("cash_balance"))}::numeric,
    NULL,
    {sql_quote(row.get("realized_pnl"))}::numeric,
    ({sql_quote(row.get("realized_pnl"))}::numeric + {sql_quote(row.get("unrealized_pnl"))}::numeric),
    {jsonb_quote(payload)}
FROM account_lookup
ON CONFLICT (ts, account_id) DO UPDATE SET
    equity = EXCLUDED.equity,
    cash = EXCLUDED.cash,
    pnl_day = EXCLUDED.pnl_day,
    pnl_total = EXCLUDED.pnl_total,
    payload = EXCLUDED.payload;
"""
        )

    def insert_trade(row: dict, source_system: str, external_prefix: str, side_key: str, price_key: str, ts_key: str) -> str:
        payload = {**row, "__source_table": external_prefix}
        return f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = {sql_quote(source_system)}
),
legacy_accounts(legacy_id, account_code) AS (VALUES {account_values}),
account_lookup AS (
    SELECT acct.id
    FROM legacy_accounts legacy
    JOIN portfolio.accounts acct ON acct.account_code = legacy.account_code
    WHERE legacy.legacy_id = {sql_quote(row.get("account_id"))}::bigint
    LIMIT 1
)
INSERT INTO portfolio.trades (
    source_system_id,
    account_id,
    symbol,
    exchange,
    instrument_type,
    side,
    quantity,
    price,
    trade_ts,
    strategy,
    raw_payload,
    external_ref
)
SELECT
    source_lookup.id,
    account_lookup.id,
    {sql_quote(row.get("symbol"))},
    {sql_quote(row.get("exchange") or "NSE")},
    {sql_quote(row.get("instrument_type") or row.get("product") or "equity")},
    {sql_quote(row.get(side_key))},
    {sql_quote(row.get("quantity"))}::numeric,
    {sql_quote(row.get(price_key))}::numeric,
    {sql_quote(row.get(ts_key))}::timestamptz,
    {sql_quote(row.get("strategy"))},
    {jsonb_quote(payload)},
    {sql_quote(f"{external_prefix}:{row.get('id')}")}
FROM source_lookup
LEFT JOIN account_lookup ON true
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

    for row in app_trades:
        statements.append(insert_trade(row, "algo app db", "algo_app_trades", "side", "price", "executed_at"))
    for row in tradebook_trades:
        statements.append(insert_trade(row, "algo trades db", "algo_trades_db", "trade_type", "entry_price", "entry_time"))

    for row in app_journal:
        payload = {**row, "__source_table": "app.journal"}
        statements.append(
            f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
)
INSERT INTO trading.trade_journals (
    source_system_id,
    journal_ts,
    symbol,
    strategy,
    pnl,
    raw_text,
    extracted_features,
    external_ref
)
SELECT
    source_lookup.id,
    {sql_quote(row.get("ts"))}::timestamptz,
    {sql_quote(row.get("symbol"))},
    {sql_quote(row.get("strategy"))},
    {sql_quote(row.get("pnl"))}::numeric,
    concat_ws(E'\\n\\n', {sql_quote(row.get("title"))}, {sql_quote(row.get("body"))}),
    {jsonb_quote(payload)},
    {sql_quote(f"algo_journal:{row.get('id')}")}
FROM source_lookup
ON CONFLICT (source_system_id, external_ref) DO UPDATE SET
    journal_ts = EXCLUDED.journal_ts,
    symbol = EXCLUDED.symbol,
    strategy = EXCLUDED.strategy,
    pnl = EXCLUDED.pnl,
    raw_text = EXCLUDED.raw_text,
    extracted_features = EXCLUDED.extracted_features;
"""
        )

    for row in app_signals:
        payload = parse_json_maybe(row.get("payload"))
        if not isinstance(payload, dict):
            payload = {"raw_payload": payload}
        payload["__source_table"] = "app.tradingview_signals"
        statements.append(
            f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
)
INSERT INTO trading.signals (
    ts,
    source_system_id,
    strategy,
    symbol,
    exchange,
    action,
    price,
    quantity,
    confidence,
    payload,
    status,
    external_ref
)
SELECT
    {sql_quote(row.get("ts"))}::timestamptz,
    source_lookup.id,
    {sql_quote(row.get("strategy"))},
    {sql_quote(row.get("symbol"))},
    'NSE',
    {sql_quote(row.get("action"))},
    {sql_quote(row.get("price"))}::numeric,
    {sql_quote(row.get("size"))}::numeric,
    NULL,
    {jsonb_quote(payload)},
    'observed',
    {sql_quote(f"algo_tradingview_signals:{row.get('id')}")}
FROM source_lookup
ON CONFLICT (source_system_id, external_ref) DO UPDATE SET
    ts = EXCLUDED.ts,
    strategy = EXCLUDED.strategy,
    symbol = EXCLUDED.symbol,
    exchange = EXCLUDED.exchange,
    action = EXCLUDED.action,
    price = EXCLUDED.price,
    quantity = EXCLUDED.quantity,
    payload = EXCLUDED.payload,
    status = EXCLUDED.status;
"""
        )

    for row in app_ideas:
        payload = {**row, "__source_table": "app.ideas"}
        title = f"{row.get('symbol') or 'Unknown'} {row.get('direction') or ''} idea".strip()
        statements.append(
            f"""
INSERT INTO research.ideas (
    idea_type,
    title,
    symbols,
    source_kind,
    source_ref,
    thesis,
    catalyst,
    expected_timeframe,
    opportunity_score,
    risk_score,
    status,
    owner_agent,
    evidence
)
VALUES (
    'legacy_algo_idea',
    {sql_quote(title)},
    ARRAY[{sql_quote(row.get("symbol"))}]::text[],
    'algo_app_db.ideas',
    {sql_quote(f"algo_ideas:{row.get('id')}")},
    {sql_quote(row.get("rationale"))},
    {sql_quote(row.get("source"))},
    {sql_quote(row.get("horizon"))},
    {sql_quote(row.get("confidence"))}::numeric,
    NULL,
    coalesce({sql_quote(row.get("status"))}, 'captured'),
    'Portfolio Manager',
    jsonb_build_array({jsonb_quote(payload)})
)
ON CONFLICT (source_kind, source_ref) DO UPDATE SET
    title = EXCLUDED.title,
    symbols = EXCLUDED.symbols,
    thesis = EXCLUDED.thesis,
    catalyst = EXCLUDED.catalyst,
    expected_timeframe = EXCLUDED.expected_timeframe,
    opportunity_score = EXCLUDED.opportunity_score,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence,
    updated_at = now();
"""
        )

    for row in app_watchlist:
        payload = {**row, "__source_table": "app.watchlist"}
        statements.append(
            f"""
INSERT INTO research.ideas (
    idea_type,
    title,
    symbols,
    source_kind,
    source_ref,
    thesis,
    opportunity_score,
    status,
    owner_agent,
    evidence
)
VALUES (
    'legacy_watchlist',
    {sql_quote((row.get("symbol") or "Unknown") + " watchlist")},
    ARRAY[{sql_quote(row.get("symbol"))}]::text[],
    'algo_app_db.watchlist',
    {sql_quote(f"algo_watchlist:{row.get('id')}")},
    {sql_quote(row.get("rationale"))},
    {sql_quote(row.get("score"))}::numeric,
    'captured',
    'Portfolio Manager',
    jsonb_build_array({jsonb_quote(payload)})
)
ON CONFLICT (source_kind, source_ref) DO UPDATE SET
    title = EXCLUDED.title,
    symbols = EXCLUDED.symbols,
    thesis = EXCLUDED.thesis,
    opportunity_score = EXCLUDED.opportunity_score,
    evidence = EXCLUDED.evidence,
    updated_at = now();
"""
        )

    def backtest_statement(row: dict, source_table: str) -> str:
        strategy_name = row.get("strategy") or f"legacy_{source_table}"
        external_ref = f"algo_{source_table}:{row.get('id')}"
        metrics = parse_json_maybe(row.get("metrics_json"))
        diagnostics = {
            "source_table": source_table,
            "equity": parse_json_maybe(row.get("equity_json")),
            "bench": parse_json_maybe(row.get("bench_json")),
            "buyhold": parse_json_maybe(row.get("buyhold_json")),
            "monthly": parse_json_maybe(row.get("monthly_json")),
            "holdings": parse_json_maybe(row.get("holdings_json")),
            "live": parse_json_maybe(row.get("live_json")),
            "transition": parse_json_maybe(row.get("transition_json")),
        }
        return f"""
INSERT INTO strategy.strategy_candidates (
    name,
    source_kind,
    source_ref,
    hypothesis,
    universe,
    status,
    owner_agent
)
VALUES (
    {sql_quote(strategy_name)},
    'algo_prices_db.{source_table}',
    {sql_quote(external_ref)},
    {sql_quote('Legacy imported strategy/backtest candidate. Review assumptions before reuse.')},
    {sql_quote(row.get("universe"))},
    'imported',
    'Strategy Research Agent'
)
ON CONFLICT (name) DO UPDATE SET
    source_kind = EXCLUDED.source_kind,
    hypothesis = EXCLUDED.hypothesis,
    universe = EXCLUDED.universe,
    status = EXCLUDED.status,
    updated_at = now();

WITH strategy_lookup AS (
    SELECT id FROM strategy.strategy_candidates WHERE name = {sql_quote(strategy_name)}
),
source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo prices db'
)
INSERT INTO strategy.backtest_runs (
    strategy_id,
    run_status,
    universe,
    metrics,
    diagnostics,
    started_at,
    finished_at,
    external_ref,
    source_system_id
)
SELECT
    strategy_lookup.id,
    'imported',
    {sql_quote(row.get("universe"))},
    {jsonb_quote(metrics if isinstance(metrics, dict) else {"raw": metrics})},
    {jsonb_quote(diagnostics)},
    {sql_quote(row.get("run_at"))}::timestamptz,
    {sql_quote(row.get("run_at"))}::timestamptz,
    {sql_quote(external_ref)},
    source_lookup.id
FROM strategy_lookup, source_lookup
ON CONFLICT (source_system_id, external_ref) DO UPDATE SET
    strategy_id = EXCLUDED.strategy_id,
    run_status = EXCLUDED.run_status,
    universe = EXCLUDED.universe,
    metrics = EXCLUDED.metrics,
    diagnostics = EXCLUDED.diagnostics,
    started_at = EXCLUDED.started_at,
    finished_at = EXCLUDED.finished_at;
"""

    for row in backtests:
        statements.append(backtest_statement(row, "backtest_runs"))
    for row in regimes:
        statements.append(backtest_statement(row, "regime_runs"))

    statements.append("COMMIT;")
    run_psql("\n".join(statements))

    return {
        "accounts": len(app_accounts),
        "holdings": len(app_holdings),
        "portfolio_snapshots": len(app_snapshots),
        "app_trades": len(app_trades),
        "tradebook_trades": len(tradebook_trades),
        "journal_entries": len(app_journal),
        "tradingview_signals": len(app_signals),
        "ideas": len(app_ideas),
        "watchlist": len(app_watchlist),
        "backtest_runs": len(backtests),
        "regime_runs": len(regimes),
        "token_map": len(token_map),
    }


def import_ticks() -> int:
    if table_count(APP_DB, "ticks") == 0:
        return 0
    uri = f"file:{APP_DB}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    cursor = connection.execute('select ts, token, symbol, ltp, volume, oi, change_pct from ticks where symbol is not null and ts is not null')
    rows = ([row[0], row[1], row[2], row[3], row[4], row[5], row[6]] for row in cursor)
    count = copy_rows(
        setup_sql="""
CREATE TEMP TABLE tmp_algo_ticks (
    ts text,
    token text,
    symbol text,
    ltp numeric,
    volume numeric,
    oi numeric,
    change_pct numeric
) ON COMMIT DROP;
""",
        copy_sql="COPY tmp_algo_ticks (ts, token, symbol, ltp, volume, oi, change_pct) FROM STDIN WITH (FORMAT csv, NULL '');",
        rows=rows,
        transform_sql="""
INSERT INTO trading.symbols (symbol, exchange, instrument_type, active)
SELECT DISTINCT symbol, 'NSE', 'equity', true
FROM tmp_algo_ticks
WHERE symbol IS NOT NULL
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;

WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
),
dedup AS (
    SELECT DISTINCT ON (t.ts::timestamptz, t.symbol)
        t.*
    FROM tmp_algo_ticks t
    WHERE t.symbol IS NOT NULL
      AND t.ts IS NOT NULL
    ORDER BY t.ts::timestamptz, t.symbol
)
INSERT INTO trading.ticks (
    ts,
    symbol_id,
    symbol,
    exchange,
    price,
    volume,
    source_system_id,
    payload
)
SELECT
    t.ts::timestamptz,
    s.id,
    t.symbol,
    'NSE',
    t.ltp,
    t.volume,
    source_lookup.id,
    jsonb_build_object('token', t.token, 'oi', t.oi, 'change_pct', t.change_pct)
FROM dedup t
JOIN trading.symbols s
    ON s.symbol = t.symbol
    AND s.exchange = 'NSE'
    AND s.instrument_type = 'equity'
CROSS JOIN source_lookup
ON CONFLICT (ts, symbol, exchange) DO UPDATE SET
    price = EXCLUDED.price,
    volume = EXCLUDED.volume,
    source_system_id = EXCLUDED.source_system_id,
    payload = EXCLUDED.payload;
""",
    )
    connection.close()
    return count


def import_daily_bars() -> int:
    if table_count(PRICES_DB, "daily_bars") == 0:
        return 0
    uri = f"file:{PRICES_DB}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    cursor = connection.execute(
        'select symbol, date, open, high, low, close, volume from daily_bars where symbol is not null and date is not null'
    )
    rows = ([row[0], row[1], row[2], row[3], row[4], row[5], row[6]] for row in cursor)
    count = copy_rows(
        setup_sql="""
CREATE TEMP TABLE tmp_algo_daily_bars (
    symbol text,
    d text,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric
) ON COMMIT DROP;
""",
        copy_sql="COPY tmp_algo_daily_bars (symbol, d, open, high, low, close, volume) FROM STDIN WITH (FORMAT csv, NULL '');",
        rows=rows,
        transform_sql="""
INSERT INTO trading.symbols (symbol, exchange, instrument_type, active)
SELECT DISTINCT symbol, 'NSE', 'equity', true
FROM tmp_algo_daily_bars
WHERE symbol IS NOT NULL
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;

WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo prices db'
),
dedup AS (
    SELECT DISTINCT ON (b.d::date, b.symbol)
        b.*
    FROM tmp_algo_daily_bars b
    WHERE b.symbol IS NOT NULL
      AND b.d IS NOT NULL
    ORDER BY b.d::date, b.symbol
)
INSERT INTO trading.ohlcv (
    ts,
    symbol_id,
    timeframe,
    open,
    high,
    low,
    close,
    volume,
    source_system_id
)
SELECT
    d::date::timestamptz,
    s.id,
    '1d',
    b.open,
    b.high,
    b.low,
    b.close,
    b.volume,
    source_lookup.id
FROM dedup b
JOIN trading.symbols s
    ON s.symbol = b.symbol
    AND s.exchange = 'NSE'
    AND s.instrument_type = 'equity'
CROSS JOIN source_lookup
ON CONFLICT (ts, symbol_id, timeframe) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    source_system_id = EXCLUDED.source_system_id;
""",
    )
    connection.close()
    return count


def warehouse_counts() -> dict:
    queries = {
        "portfolio_accounts": "select count(*) from portfolio.accounts;",
        "portfolio_positions": "select count(*) from portfolio.positions;",
        "portfolio_snapshots": "select count(*) from portfolio.snapshots;",
        "portfolio_trades": "select count(*) from portfolio.trades;",
        "trade_journals": "select count(*) from trading.trade_journals;",
        "trading_signals": "select count(*) from trading.signals;",
        "ticks": "select count(*) from trading.ticks;",
        "ohlcv": "select count(*) from trading.ohlcv;",
        "research_ideas": "select count(*) from research.ideas;",
        "strategy_candidates": "select count(*) from strategy.strategy_candidates;",
        "backtest_runs": "select count(*) from strategy.backtest_runs;",
    }
    return {name: run_scalar(sql) for name, sql in queries.items()}


def main() -> int:
    small = import_small_tables()
    ticks = import_ticks()
    daily_bars = import_daily_bars()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(ALGO_ROOT),
        "small_table_rows_seen": small,
        "streamed_rows_seen": {
            "ticks": ticks,
            "daily_bars": daily_bars,
        },
        "warehouse_counts": warehouse_counts(),
    }
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
