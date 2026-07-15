#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
SOURCE_KEY = "tick_ohlcv_aggregation"

TIMEFRAMES = [
    ("1d", "1 day", "date_trunc('day', t.ts)"),
    ("1h", "1 hour", "date_bin(INTERVAL '1 hour', t.ts, TIMESTAMPTZ '1970-01-01 00:00:00+00')"),
    ("15m", "15 minutes", "date_bin(INTERVAL '15 minutes', t.ts, TIMESTAMPTZ '1970-01-01 00:00:00+00')"),
    ("5m", "5 minutes", "date_bin(INTERVAL '5 minutes', t.ts, TIMESTAMPTZ '1970-01-01 00:00:00+00')"),
]


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value if value is not None else {}, sort_keys=True, default=str))}::jsonb"


def run_psql(sql: str, tuples_only: bool = False) -> str:
    psql_bin = os.environ.get("AI_OS_PSQL_BIN") or "/opt/homebrew/opt/postgresql@15/bin/psql"
    password = os.environ.get("AI_OS_POSTGRES_PASSWORD")
    if Path(psql_bin).exists() and password:
        command = [psql_bin, f"host={os.environ.get('AI_OS_POSTGRES_HOST') or '127.0.0.1'} port={os.environ.get('AI_OS_POSTGRES_PORT') or '54329'} dbname={os.environ.get('AI_OS_POSTGRES_DB') or 'ai_os'} user={os.environ.get('AI_OS_POSTGRES_USER') or 'ai_os'} connect_timeout=3 options='-c statement_timeout=30000 -c lock_timeout=5000'", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql]
        if tuples_only:
            command.extend(["-t", "-A"])
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=35)
    else:
        command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
        if tuples_only:
            command.extend(["-t", "-A"])
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, timeout=35)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def store_check(
    *,
    status: str,
    rows_seen: int,
    sample_payload: dict[str, Any],
    error_message: str | None,
) -> None:
    run_psql(
        f"""
        INSERT INTO core.data_source_checks (
            source_key, check_name, check_type, target_url, status,
            http_status, latency_ms, rows_seen, sample_payload, error_message
        )
        VALUES (
            {sql_literal(SOURCE_KEY)},
            'Tick to OHLCV aggregation',
            'postgres_job',
            'trading.ticks -> trading.ohlcv',
            {sql_literal(status)},
            NULL,
            NULL,
            {int(rows_seen)},
            {sql_jsonb(sample_payload)},
            {sql_literal(error_message)}
        );

        UPDATE core.data_source_registry
        SET last_seen_at = now(),
            updated_at = now()
        WHERE source_key = {sql_literal(SOURCE_KEY)};
        """
    )


def tick_profile() -> dict[str, Any]:
    output = run_psql(
        """
        SELECT json_build_object(
            'tick_rows', count(*),
            'tick_min_ts', min(ts),
            'tick_max_ts', max(ts),
            'symbol_count', count(DISTINCT symbol)
        )::text
        FROM trading.ticks;
        """,
        tuples_only=True,
    )
    return json.loads(output or "{}")


def bootstrap_source() -> None:
    run_psql(
        """
INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES (
    'AI OS tick OHLCV aggregation',
    'derived_market_data',
    'trading.ticks -> trading.ohlcv',
    'private_trading',
    'active',
    'Derived OHLCV bars aggregated from real imported tick data. No seed or synthetic market data.'
)
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
VALUES (
    'tick_ohlcv_aggregation',
    'Tick to OHLCV aggregation',
    'derived_market_data',
    'AI OS',
    'postgres_job',
    'active',
    5,
    'Data Steward',
    'private_trading',
    (SELECT id FROM core.source_systems WHERE name = 'AI OS tick OHLCV aggregation'),
    'Aggregates imported ticks into 1d, 1h, 15m, and 5m bars for strategy research and alerts.',
    '{"seed_data":false,"source_table":"trading.ticks","target_table":"trading.ohlcv"}'::jsonb
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
    last_seen_at = now(),
    updated_at = now();
"""
    )


def aggregate_timeframe(timeframe: str, interval_label: str, bucket_expression: str) -> int:
    sql = f"""
WITH source AS (
    SELECT id FROM core.source_systems WHERE name = 'AI OS tick OHLCV aggregation'
),
bucketed AS (
    SELECT
        {bucket_expression} AS bucket_ts,
        COALESCE(t.symbol_id, s.id) AS symbol_id,
        t.ts,
        t.price,
        COALESCE(t.volume, 0) AS volume
    FROM trading.ticks t
    JOIN trading.symbols s
      ON s.symbol = t.symbol
     AND s.exchange = t.exchange
    WHERE t.price IS NOT NULL
),
aggregated AS (
    SELECT
        bucket_ts,
        symbol_id,
        {timeframe!r}::text AS timeframe,
        (ARRAY_AGG(price ORDER BY ts ASC))[1] AS open,
        MAX(price) AS high,
        MIN(price) AS low,
        (ARRAY_AGG(price ORDER BY ts DESC))[1] AS close,
        SUM(volume) AS volume,
        (SELECT id FROM source) AS source_system_id
    FROM bucketed
    GROUP BY bucket_ts, symbol_id
),
upserted AS (
    INSERT INTO trading.ohlcv (ts, symbol_id, timeframe, open, high, low, close, volume, source_system_id)
    SELECT bucket_ts, symbol_id, timeframe, open, high, low, close, volume, source_system_id
    FROM aggregated
    ON CONFLICT (ts, symbol_id, timeframe) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume,
        source_system_id = EXCLUDED.source_system_id
    RETURNING 1
)
SELECT COUNT(*) FROM upserted;
"""
    output = run_psql(sql, tuples_only=True)
    return int(output or "0")


def main() -> int:
    bootstrap_source()
    results = []
    try:
        profile = tick_profile()
        for timeframe, interval_label, bucket_expression in TIMEFRAMES:
            rows = aggregate_timeframe(timeframe, interval_label, bucket_expression)
            results.append({"timeframe": timeframe, "interval": interval_label, "rows_upserted": rows})
        rows_seen = sum(int(row["rows_upserted"]) for row in results)
        summary = {"status": "ok", "tick_profile": profile, "ohlcv_aggregation": results, "rows_upserted_total": rows_seen}
        store_check(status="ok", rows_seen=rows_seen, sample_payload=summary, error_message=None)
        output_path = RUNTIME_ROOT / "imports" / "ohlcv_aggregation_summary.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        summary = {"status": "error", "ohlcv_aggregation": results, "error": type(exc).__name__ + ": " + str(exc)}
        try:
            store_check(status="error", rows_seen=0, sample_payload=summary, error_message=summary["error"])
        except Exception:  # noqa: BLE001
            pass
        print(json.dumps(summary, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
