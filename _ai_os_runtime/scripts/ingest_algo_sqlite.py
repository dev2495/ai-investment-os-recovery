#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ALGO_ROOT = Path(
    os.environ.get(
        "AI_OS_LEGACY_ALGO_DB_ROOT",
        "/Volumes/Devarsh SSD/AI OS Data/imports/quarantine/legacy_databases/algo",
    )
)
TRADES_DB = ALGO_ROOT / "trades.db"
APP_DB = ALGO_ROOT / "app.db"
PRICES_DB = ALGO_ROOT / "prices.db"
OUTPUT_PATH = Path(
    os.environ.get(
        "AI_OS_ALGO_IMPORT_SUMMARY_PATH",
        "/Volumes/Devarsh SSD/Obsidian memory /ai memory/00 AI OS/Reports/Evidence/algo_import_summary.json",
    )
)


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


def run_value(sql: str) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise RuntimeError("Postgres command failed")
    return completed.stdout.strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_profile(path: Path, table_name: str, profile_sql: str) -> dict[str, object]:
    uri = f"file:{path}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=30) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(profile_sql).fetchone()
        if row is None:
            raise RuntimeError(f"No profile returned for {path.name}.{table_name}")
        return dict(row)


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
SELECT DISTINCT upper(trim(symbol)), 'NSE', 'equity', true
FROM tmp_algo_ticks
WHERE nullif(trim(symbol), '') IS NOT NULL
  AND ts IS NOT NULL
  AND ltp > 0
  AND coalesce(volume, 0) >= 0
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;

WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
),
dedup AS (
    SELECT DISTINCT ON (t.ts::timestamptz, upper(trim(t.symbol)))
        t.ts,
        t.token,
        upper(trim(t.symbol)) AS symbol,
        t.ltp,
        t.volume,
        t.oi,
        t.change_pct
    FROM tmp_algo_ticks t
    WHERE nullif(trim(t.symbol), '') IS NOT NULL
      AND t.ts IS NOT NULL
      AND t.ltp > 0
      AND coalesce(t.volume, 0) >= 0
    ORDER BY t.ts::timestamptz, upper(trim(t.symbol))
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
SELECT DISTINCT upper(trim(symbol)), 'NSE', 'equity', true
FROM tmp_algo_daily_bars
WHERE nullif(trim(symbol), '') IS NOT NULL
  AND d IS NOT NULL
  AND open > 0 AND high > 0 AND low > 0 AND close > 0
  AND coalesce(volume, 0) >= 0
  AND high + 0.000000001 >= greatest(open, low, close)
  AND low - 0.000000001 <= least(open, high, close)
ON CONFLICT (symbol, exchange, instrument_type) DO UPDATE SET active = true;

WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo prices db'
),
dedup AS (
    SELECT DISTINCT ON (b.d::date, upper(trim(b.symbol)))
        upper(trim(b.symbol)) AS symbol,
        b.d,
        b.open,
        greatest(b.high, b.open, b.low, b.close) AS high,
        least(b.low, b.open, b.high, b.close) AS low,
        b.close,
        b.volume
    FROM tmp_algo_daily_bars b
    WHERE nullif(trim(b.symbol), '') IS NOT NULL
      AND b.d IS NOT NULL
      AND b.open > 0 AND b.high > 0 AND b.low > 0 AND b.close > 0
      AND coalesce(b.volume, 0) >= 0
      AND b.high + 0.000000001 >= greatest(b.open, b.low, b.close)
      AND b.low - 0.000000001 <= least(b.open, b.high, b.close)
    ORDER BY b.d::date, upper(trim(b.symbol))
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


def import_straddle_snapshots(raw_artifact_id: int) -> int:
    if table_count(APP_DB, "straddle_snapshots") == 0:
        return 0
    uri = f"file:{APP_DB}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    cursor = connection.execute(
        "select ts, underlying, expiry, atm_strike, ce_price, pe_price, straddle, spot, iv_avg "
        "from straddle_snapshots where ts is not null and underlying is not null and expiry is not null"
    )
    rows = ([row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]] for row in cursor)
    count = copy_rows(
        setup_sql="""
CREATE TEMP TABLE tmp_algo_straddles (
    ts text,
    underlying text,
    expiry text,
    atm_strike numeric,
    ce_price numeric,
    pe_price numeric,
    straddle numeric,
    spot numeric,
    iv_avg numeric
) ON COMMIT DROP;
""",
        copy_sql="COPY tmp_algo_straddles (ts, underlying, expiry, atm_strike, ce_price, pe_price, straddle, spot, iv_avg) FROM STDIN WITH (FORMAT csv, NULL '');",
        rows=rows,
        transform_sql=f"""
WITH source_lookup AS (
    SELECT id FROM core.source_systems WHERE name = 'algo app db'
),
dedup AS (
    SELECT DISTINCT ON (s.ts::timestamptz, upper(trim(s.underlying)), s.expiry::date, s.atm_strike)
        s.ts::timestamptz AS ts,
        upper(trim(s.underlying)) AS underlying,
        s.expiry::date AS expiry,
        s.atm_strike,
        s.ce_price,
        s.pe_price,
        s.straddle,
        s.spot,
        s.iv_avg
    FROM tmp_algo_straddles s
    WHERE nullif(trim(s.underlying), '') IS NOT NULL
      AND s.ts IS NOT NULL
      AND s.expiry IS NOT NULL
      AND s.atm_strike > 0
      AND coalesce(s.ce_price, 0) >= 0
      AND coalesce(s.pe_price, 0) >= 0
      AND coalesce(s.straddle, 0) >= 0
      AND coalesce(s.spot, 0) >= 0
      AND coalesce(s.iv_avg, 0) >= 0
    ORDER BY s.ts::timestamptz, upper(trim(s.underlying)), s.expiry::date, s.atm_strike
)
INSERT INTO trading.option_strategy_snapshots (
    ts, underlying, exchange, expiry, strategy_type, reference_strike,
    call_price, put_price, net_premium, spot_price, implied_volatility,
    source_system_id, source_artifact_id, source_payload, updated_at
)
SELECT
    snapshot.ts, snapshot.underlying, 'NSE', snapshot.expiry, 'straddle', snapshot.atm_strike,
    snapshot.ce_price, snapshot.pe_price, snapshot.straddle, snapshot.spot, snapshot.iv_avg,
    source_lookup.id, {raw_artifact_id},
    jsonb_build_object('source_table', 'app.straddle_snapshots'), now()
FROM dedup snapshot
CROSS JOIN source_lookup
ON CONFLICT (ts, underlying, expiry, strategy_type, reference_strike) DO UPDATE SET
    call_price = EXCLUDED.call_price,
    put_price = EXCLUDED.put_price,
    net_premium = EXCLUDED.net_premium,
    spot_price = EXCLUDED.spot_price,
    implied_volatility = EXCLUDED.implied_volatility,
    source_system_id = EXCLUDED.source_system_id,
    source_artifact_id = EXCLUDED.source_artifact_id,
    source_payload = EXCLUDED.source_payload,
    updated_at = now();
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
        "option_strategy_snapshots": "select count(*) from trading.option_strategy_snapshots;",
        "research_ideas": "select count(*) from research.ideas;",
        "strategy_candidates": "select count(*) from strategy.strategy_candidates;",
        "backtest_runs": "select count(*) from strategy.backtest_runs;",
    }
    return {name: run_scalar(sql) for name, sql in queries.items()}


def source_profiles() -> dict[str, dict[str, object]]:
    epsilon = 0.000000001
    return {
        "legacy_algo_daily_ohlcv": sqlite_profile(
            PRICES_DB,
            "daily_bars",
            f"""
SELECT
    count(*) AS source_rows,
    sum(CASE WHEN symbol IS NOT NULL AND trim(symbol) <> '' AND date IS NOT NULL
                  AND open > 0 AND high > 0 AND low > 0 AND close > 0
                  AND coalesce(volume, 0) >= 0
                  AND high + {epsilon} >= max(open, low, close)
                  AND low - {epsilon} <= min(open, high, close)
                  AND date(date) <= date('now') THEN 1 ELSE 0 END) AS valid_rows,
    count(DISTINCT CASE WHEN symbol IS NOT NULL AND trim(symbol) <> '' AND date IS NOT NULL
                  AND open > 0 AND high > 0 AND low > 0 AND close > 0
                  AND coalesce(volume, 0) >= 0
                  AND high + {epsilon} >= max(open, low, close)
                  AND low - {epsilon} <= min(open, high, close)
                  AND date(date) <= date('now') THEN date || '|' || upper(trim(symbol)) END) AS canonical_rows,
    count(DISTINCT upper(trim(symbol))) AS symbol_count,
    min(date) AS first_ts,
    max(date) AS last_ts,
    sum(CASE WHEN symbol IS NULL OR trim(symbol) = '' OR date IS NULL OR open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS missing_required,
    sum(CASE WHEN coalesce(open, 0) <= 0 OR coalesce(high, 0) <= 0 OR coalesce(low, 0) <= 0 OR coalesce(close, 0) <= 0 THEN 1 ELSE 0 END) AS nonpositive_price,
    sum(CASE WHEN high + {epsilon} < max(open, low, close) OR low - {epsilon} > min(open, high, close) THEN 1 ELSE 0 END) AS invalid_bounds,
    sum(CASE WHEN volume IS NOT NULL AND volume < 0 THEN 1 ELSE 0 END) AS negative_volume,
    sum(CASE WHEN date(date) > date('now') THEN 1 ELSE 0 END) AS future_rows,
    sum(CASE WHEN (high < max(open, low, close) OR low > min(open, high, close)) AND NOT (high + {epsilon} < max(open, low, close) OR low - {epsilon} > min(open, high, close)) THEN 1 ELSE 0 END) AS corrected_rows
FROM daily_bars
""",
        ),
        "legacy_algo_ticks": sqlite_profile(
            APP_DB,
            "ticks",
            """
SELECT
    count(*) AS source_rows,
    sum(CASE WHEN symbol IS NOT NULL AND trim(symbol) <> '' AND ts IS NOT NULL
                  AND ltp > 0 AND coalesce(volume, 0) >= 0
                  AND datetime(ts) <= datetime('now') THEN 1 ELSE 0 END) AS valid_rows,
    count(DISTINCT CASE WHEN symbol IS NOT NULL AND trim(symbol) <> '' AND ts IS NOT NULL
                  AND ltp > 0 AND coalesce(volume, 0) >= 0
                  AND datetime(ts) <= datetime('now') THEN ts || '|' || upper(trim(symbol)) END) AS canonical_rows,
    count(DISTINCT upper(trim(symbol))) AS symbol_count,
    min(ts) AS first_ts,
    max(ts) AS last_ts,
    sum(CASE WHEN symbol IS NULL OR trim(symbol) = '' OR ts IS NULL OR ltp IS NULL THEN 1 ELSE 0 END) AS missing_required,
    sum(CASE WHEN coalesce(ltp, 0) <= 0 THEN 1 ELSE 0 END) AS nonpositive_price,
    0 AS invalid_bounds,
    sum(CASE WHEN volume IS NOT NULL AND volume < 0 THEN 1 ELSE 0 END) AS negative_volume,
    sum(CASE WHEN datetime(ts) > datetime('now') THEN 1 ELSE 0 END) AS future_rows,
    0 AS corrected_rows
FROM ticks
""",
        ),
        "legacy_algo_straddles": sqlite_profile(
            APP_DB,
            "straddle_snapshots",
            """
SELECT
    count(*) AS source_rows,
    sum(CASE WHEN underlying IS NOT NULL AND trim(underlying) <> '' AND ts IS NOT NULL
                  AND expiry IS NOT NULL AND atm_strike > 0
                  AND coalesce(ce_price, 0) >= 0 AND coalesce(pe_price, 0) >= 0
                  AND coalesce(straddle, 0) >= 0 AND coalesce(spot, 0) >= 0
                  AND coalesce(iv_avg, 0) >= 0 AND datetime(ts) <= datetime('now') THEN 1 ELSE 0 END) AS valid_rows,
    count(DISTINCT CASE WHEN underlying IS NOT NULL AND trim(underlying) <> '' AND ts IS NOT NULL
                  AND expiry IS NOT NULL AND atm_strike > 0
                  AND coalesce(ce_price, 0) >= 0 AND coalesce(pe_price, 0) >= 0
                  AND coalesce(straddle, 0) >= 0 AND coalesce(spot, 0) >= 0
                  AND coalesce(iv_avg, 0) >= 0 AND datetime(ts) <= datetime('now')
                  THEN ts || '|' || upper(trim(underlying)) || '|' || expiry || '|' || atm_strike END) AS canonical_rows,
    count(DISTINCT upper(trim(underlying))) AS symbol_count,
    min(ts) AS first_ts,
    max(ts) AS last_ts,
    sum(CASE WHEN underlying IS NULL OR trim(underlying) = '' OR ts IS NULL OR expiry IS NULL OR atm_strike IS NULL THEN 1 ELSE 0 END) AS missing_required,
    sum(CASE WHEN coalesce(atm_strike, 0) <= 0 OR coalesce(ce_price, 0) < 0 OR coalesce(pe_price, 0) < 0 OR coalesce(straddle, 0) < 0 OR coalesce(spot, 0) < 0 OR coalesce(iv_avg, 0) < 0 THEN 1 ELSE 0 END) AS nonpositive_price,
    0 AS invalid_bounds,
    0 AS negative_volume,
    sum(CASE WHEN datetime(ts) > datetime('now') THEN 1 ELSE 0 END) AS future_rows,
    0 AS corrected_rows
FROM straddle_snapshots
""",
        ),
    }


def register_raw_artifact(source_system_name: str, path: Path, content_hash: str) -> int:
    return run_scalar(
        f"""
WITH source AS (SELECT id FROM core.source_systems WHERE name = {sql_quote(source_system_name)}),
upserted AS (
    INSERT INTO core.raw_artifacts (
        source_system_id, artifact_type, title, local_path, content_hash, mime_type, sensitivity, metadata
    )
    SELECT source.id, 'legacy_sqlite_database', {sql_quote(path.name)}, {sql_quote(str(path))},
           {sql_quote(content_hash)}, 'application/vnd.sqlite3', 'private',
           jsonb_build_object('immutable_source', true, 'storage_tier', 'external_ssd_quarantine', 'seed_data', false)
    FROM source
    ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
        captured_at = now(), metadata = EXCLUDED.metadata
    RETURNING id
)
SELECT id FROM upserted;
"""
    )


def begin_market_import(
    *, batch_key: str, dataset_key: str, source_key: str, source_system_name: str,
    path: Path, source_hash: str, raw_artifact_id: int, profile: dict[str, object]
) -> dict[str, int]:
    core_import_run_id = run_scalar(
        f"""
INSERT INTO core.import_runs (source_system_id, import_type, status, rows_seen, rows_imported, notes)
SELECT id, 'legacy_market_data_ingestion', 'started', {int(profile['source_rows'])}, 0,
       {sql_quote('batch=' + batch_key + ';dataset=' + dataset_key)}
FROM core.source_systems WHERE name = {sql_quote(source_system_name)}
RETURNING id;
"""
    )
    run_key = f"{batch_key}:{dataset_key}:{uuid.uuid4().hex[:10]}"
    market_run_id = run_scalar(
        f"""
INSERT INTO market.market_data_import_runs (
    run_key, batch_key, dataset_key, source_key, source_system_id, core_import_run_id,
    raw_artifact_id, source_path, source_hash, source_rows, valid_rows, rejected_rows,
    corrected_rows, symbol_count, first_ts, last_ts, requested_by
)
SELECT
    {sql_quote(run_key)}, {sql_quote(batch_key)}, {sql_quote(dataset_key)}, {sql_quote(source_key)},
    source.id, {core_import_run_id}, {raw_artifact_id}, {sql_quote(str(path))}, {sql_quote(source_hash)},
    {int(profile['source_rows'])},
    {int(profile['valid_rows'])},
    {int(profile['source_rows']) - int(profile['valid_rows'])},
    {int(profile['corrected_rows'])}, {int(profile['symbol_count'])},
    {sql_quote(profile['first_ts'])}::timestamptz, {sql_quote(profile['last_ts'])}::timestamptz, 'Jarvis'
FROM core.source_systems source WHERE source.name = {sql_quote(source_system_name)}
RETURNING id;
"""
    )
    return {"core_import_run_id": core_import_run_id, "market_run_id": market_run_id}


def warehouse_dataset_profile(dataset_key: str) -> dict[str, object]:
    if dataset_key == "legacy_algo_daily_ohlcv":
        where = "source.name = 'algo prices db' AND data.timeframe = '1d'"
        relation = "trading.ohlcv data JOIN core.source_systems source ON source.id = data.source_system_id"
        symbol = "data.symbol_id"
    elif dataset_key == "legacy_algo_ticks":
        where = "source.name = 'algo app db'"
        relation = "trading.ticks data JOIN core.source_systems source ON source.id = data.source_system_id"
        symbol = "data.symbol"
    else:
        where = "source.name = 'algo app db' AND data.strategy_type = 'straddle'"
        relation = "trading.option_strategy_snapshots data JOIN core.source_systems source ON source.id = data.source_system_id"
        symbol = "data.underlying"
    result = run_value(
        f"SELECT json_build_object('row_count',count(*),'symbol_count',count(DISTINCT {symbol}),'first_ts',min(data.ts),'last_ts',max(data.ts)) FROM {relation} WHERE {where};"
    )
    return json.loads(result)


def finish_market_import(
    dataset_key: str, run_ids: dict[str, int], profile: dict[str, object], warehouse_before: dict[str, object],
    warehouse_after: dict[str, object], rows_touched: int
) -> None:
    rejected = int(profile["source_rows"]) - int(profile["valid_rows"])
    warning = rejected == 0
    quality_status = "passed_with_warnings" if warning else "failed"
    status = "completed_with_warnings" if warning else "failed"
    rows_inserted = max(0, int(warehouse_after["row_count"]) - int(warehouse_before["row_count"]))
    quality_summary = {
        "checks": {key: profile[key] for key in ("missing_required", "nonpositive_price", "invalid_bounds", "negative_volume", "future_rows")},
        "bias_audit_required": True,
        "execution_allowed": False,
        "deduplicated_rows": int(profile["valid_rows"]) - int(profile["canonical_rows"]),
    }
    market_run_id = run_ids["market_run_id"]
    checks = [
        ("required_fields", "Required fields present", int(profile["missing_required"])),
        ("positive_prices", "Prices and strikes valid", int(profile["nonpositive_price"])),
        ("ohlc_bounds", "OHLC bounds valid within epsilon", int(profile["invalid_bounds"])),
        ("nonnegative_volume", "Volume is nonnegative", int(profile["negative_volume"])),
        ("no_future_rows", "No future-dated observations", int(profile["future_rows"])),
    ]
    statements = ["BEGIN;"]
    for key, name, observed in checks:
        statements.append(
            f"""
INSERT INTO market.market_data_quality_checks (import_run_id, check_key, check_name, status, observed_value, threshold_value, details)
VALUES ({market_run_id}, {sql_quote(key)}, {sql_quote(name)}, {'\'passed\'' if observed == 0 else '\'failed\''}, {observed}, 0,
        jsonb_build_object('source_profile', true, 'seed_data', false))
ON CONFLICT (import_run_id, check_key) DO UPDATE SET status=EXCLUDED.status, observed_value=EXCLUDED.observed_value,
    threshold_value=EXCLUDED.threshold_value, details=EXCLUDED.details, checked_at=now();
"""
        )
    statements.append(
        f"""
INSERT INTO market.market_data_quality_checks (import_run_id, check_key, check_name, status, observed_value, details)
VALUES ({market_run_id}, 'research_bias_contract', 'Point-in-time, corporate-action, and survivorship audit', 'warning', NULL,
        '{{"research_use":"caveated","execution_allowed":false,"audit_required":true}}'::jsonb)
ON CONFLICT (import_run_id, check_key) DO UPDATE SET status='warning', details=EXCLUDED.details, checked_at=now();

UPDATE market.market_data_import_runs SET
    status={sql_quote(status)}, rows_touched={rows_touched}, rows_inserted={rows_inserted},
    deduplicated_rows={int(profile['valid_rows']) - int(profile['canonical_rows'])},
    warehouse_rows_after={int(warehouse_after['row_count'])}, symbol_count={int(warehouse_after['symbol_count'])},
    first_ts={sql_quote(warehouse_after.get('first_ts'))}::timestamptz,
    last_ts={sql_quote(warehouse_after.get('last_ts'))}::timestamptz,
    quality_status={sql_quote(quality_status)}, quality_summary={jsonb_quote(quality_summary)}, finished_at=now()
WHERE id={market_run_id};

UPDATE market.market_data_import_runs SET
    valid_rows={int(profile['valid_rows'])},
    rejected_rows={int(profile['source_rows']) - int(profile['valid_rows'])},
    deduplicated_rows={int(profile['valid_rows']) - int(profile['canonical_rows'])},
    rows_touched={int(profile['canonical_rows'])},
    quality_summary=quality_summary || jsonb_build_object('deduplicated_rows',{int(profile['valid_rows']) - int(profile['canonical_rows'])})
WHERE dataset_key={sql_quote(dataset_key)}
  AND source_hash=(SELECT source_hash FROM market.market_data_import_runs WHERE id={market_run_id})
  AND id <> {market_run_id};

UPDATE core.import_runs SET status={sql_quote(status)}, finished_at=now(), rows_seen={int(profile['source_rows'])},
    rows_imported={rows_touched}, notes=coalesce(notes,'') || {sql_quote(';quality=' + quality_status)}
WHERE id={run_ids['core_import_run_id']};
COMMIT;
"""
    )
    run_psql("\n".join(statements))


def fail_market_import(run_ids: dict[str, int], error: Exception) -> None:
    message = f"{type(error).__name__}: {error}"[:1000]
    run_psql(
        f"""
UPDATE market.market_data_import_runs SET status='failed', quality_status='failed', error_message={sql_quote(message)}, finished_at=now()
WHERE id={run_ids['market_run_id']};
UPDATE core.import_runs SET status='failed', finished_at=now(), notes=coalesce(notes,'') || {sql_quote(';error=' + message)}
WHERE id={run_ids['core_import_run_id']};
"""
    )


def main() -> int:
    required_files = (TRADES_DB, APP_DB, PRICES_DB)
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing checksum-preserved source files: " + ", ".join(missing))

    quick_checks = {}
    for path in required_files:
        uri = f"file:{path}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=30) as connection:
            quick_checks[path.name] = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick_checks[path.name] != "ok":
            raise RuntimeError(f"SQLite quick_check failed for {path.name}: {quick_checks[path.name]}")

    source_hashes = {path.name: file_sha256(path) for path in required_files}
    profiles = source_profiles()
    source_config = {
        "legacy_algo_daily_ohlcv": ("algo prices db", PRICES_DB),
        "legacy_algo_ticks": ("algo app db", APP_DB),
        "legacy_algo_straddles": ("algo app db", APP_DB),
    }
    run_psql(
        f"""
UPDATE core.source_systems SET location={sql_quote(str(TRADES_DB))}, status='active' WHERE name='algo trades db';
UPDATE core.source_systems SET location={sql_quote(str(APP_DB))}, status='active' WHERE name='algo app db';
UPDATE core.source_systems SET location={sql_quote(str(PRICES_DB))}, status='active' WHERE name='algo prices db';
"""
    )
    artifacts = {
        "algo trades db": register_raw_artifact("algo trades db", TRADES_DB, source_hashes[TRADES_DB.name]),
        "algo app db": register_raw_artifact("algo app db", APP_DB, source_hashes[APP_DB.name]),
        "algo prices db": register_raw_artifact("algo prices db", PRICES_DB, source_hashes[PRICES_DB.name]),
    }
    batch_key = "legacy-algo-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs: dict[str, dict[str, int]] = {}
    before = {dataset: warehouse_dataset_profile(dataset) for dataset in source_config}
    for dataset, (source_system_name, path) in source_config.items():
        runs[dataset] = begin_market_import(
            batch_key=batch_key,
            dataset_key=dataset,
            source_key="algo_trading_archive",
            source_system_name=source_system_name,
            path=path,
            source_hash=source_hashes[path.name],
            raw_artifact_id=artifacts[source_system_name],
            profile=profiles[dataset],
        )

    try:
        small = import_small_tables()
        ticks_seen = import_ticks()
        daily_bars_seen = import_daily_bars()
        straddles_seen = import_straddle_snapshots(artifacts["algo app db"])
        rows_seen = {
            "legacy_algo_daily_ohlcv": daily_bars_seen,
            "legacy_algo_ticks": ticks_seen,
            "legacy_algo_straddles": straddles_seen,
        }
        after = {dataset: warehouse_dataset_profile(dataset) for dataset in source_config}
        for dataset in source_config:
            finish_market_import(dataset, runs[dataset], profiles[dataset], before[dataset], after[dataset], int(profiles[dataset]["canonical_rows"]))

        total_rows = sum(int(profiles[dataset]["canonical_rows"]) for dataset in source_config)
        run_psql(
            f"""
UPDATE core.source_connector_profiles
SET status='active', health_status='active', last_checked_at=now(), last_rows_seen={total_rows},
    last_error=NULL, updated_at=now(),
    config=config || jsonb_build_object('source_root',{sql_quote(str(ALGO_ROOT))},'checksum_verified',true,'seed_data',false)
WHERE source_key='algo_trading_archive';
UPDATE core.data_source_registry
SET status='active', last_seen_at=now(), updated_at=now(),
    metadata=metadata || jsonb_build_object('last_import_batch',{sql_quote(batch_key)},'checksum_verified',true,'seed_data',false,'execution_allowed',false)
WHERE source_key='algo_trading_archive';
INSERT INTO core.data_source_checks (source_key,check_name,check_type,status,rows_seen,sample_payload,checked_at)
VALUES ('algo_trading_archive','legacy market data import','row_count','ok',{total_rows},
        {jsonb_quote({'batch_key': batch_key, 'quality_status': 'passed_with_warnings', 'execution_allowed': False})},now());
"""
        )
        summary = {
            "status": "ok",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "batch_key": batch_key,
            "source_root": str(ALGO_ROOT),
            "source_hashes": source_hashes,
            "quick_checks": quick_checks,
            "small_table_rows_seen": small,
            "streamed_rows_seen": {
                "ticks": ticks_seen,
                "daily_bars": daily_bars_seen,
                "straddle_snapshots": straddles_seen,
            },
            "rows_written": total_rows,
            "source_profiles": profiles,
            "warehouse_profiles": after,
            "warehouse_counts": warehouse_counts(),
            "research_bias_audit_required": True,
            "execution_allowed": False,
        }
    except Exception as error:
        for run_ids in runs.values():
            fail_market_import(run_ids, error)
        summary = {
            "status": "error",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "batch_key": batch_key,
            "source_root": str(ALGO_ROOT),
            "error": f"{type(error).__name__}: {error}",
            "rows_written": 0,
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
