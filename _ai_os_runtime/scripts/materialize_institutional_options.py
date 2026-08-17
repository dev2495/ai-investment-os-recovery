#!/usr/bin/env python3
"""Materialize source option snapshots into the institutional analytics store.

The workload is idempotent, point-in-time, and analytics-only. It never creates
valuation inputs unless a validated, unexpired, source-evidenced policy exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time as monotonic_time
from datetime import datetime, time, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from run_institutional_options_engine import (
    MODEL_VERSION,
    SOLVER_VERSION,
    analyze_chain,
    classify_buildup,
    premium_series,
    replay_frames,
)
from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal


WORKLOAD_KEY = "institutional_options_materializer"
DEFAULT_PROVIDER = "Zerodha"
CURRENT_SOURCE_ROW_LIMIT = 768
CURRENT_CANDIDATE_ROW_LIMIT = 8192
MAX_DB_CALL_SECONDS = 4.0
MAX_DB_STATEMENT_MS = 3500
DB_CALL_DURATIONS_MS: list[float] = []


def materializer_psql_json(sql: str) -> list[dict[str, Any]]:
    started = monotonic_time.monotonic()
    try:
        return run_psql_json(
            sql,
            statement_timeout_ms=MAX_DB_STATEMENT_MS,
            timeout_seconds=MAX_DB_CALL_SECONDS,
        )
    finally:
        DB_CALL_DURATIONS_MS.append((monotonic_time.monotonic() - started) * 1000.0)


def rows(query: str) -> list[dict[str, Any]]:
    result = materializer_psql_json(
        "SELECT coalesce(json_agg(row_to_json(source_rows)), '[]'::json)::text "
        f"FROM ({query}) source_rows"
    )
    return result if isinstance(result, list) else []


def write_returning(statement: str) -> list[dict[str, Any]]:
    return materializer_psql_json(
        "WITH changed AS (" + statement + ") "
        "SELECT coalesce(json_agg(row_to_json(changed)), '[]'::json)::text FROM changed"
    )


def text_array(values: list[str]) -> str:
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::text[]"


def numeric_sql(value: Any) -> str:
    return "NULL" if value is None else repr(float(value))


def parse_timestamp(value: Any) -> datetime:
    timestamp_text = str(value).replace("Z", "+00:00")
    offset_at = max(timestamp_text.rfind("+"), timestamp_text.rfind("-"))
    core, offset = (timestamp_text[:offset_at], timestamp_text[offset_at:]) if offset_at > 10 else (timestamp_text, "")
    if len(offset) == 3 and offset[0] in "+-" and offset[1:].isdigit():
        offset += ":00"
    if "." in core:
        base, fraction = core.rsplit(".", 1)
        if fraction.isdigit():
            core = f"{base}.{fraction[:6].ljust(6, '0')}"
    parsed = datetime.fromisoformat(core + offset)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def current_pending_groups(
    limit: int,
    *,
    provider: str = DEFAULT_PROVIDER,
    source_row_limit: int = CURRENT_SOURCE_ROW_LIMIT,
    candidate_row_limit: int = CURRENT_CANDIDATE_ROW_LIMIT,
) -> list[dict[str, Any]]:
    return rows(
        f"""
        WITH candidate_source AS MATERIALIZED (
        SELECT legacy.*
        FROM trading.option_chain_snapshots legacy
        WHERE legacy.provider={sql_literal(provider)}
          AND legacy.observed_at <= now() + interval '5 minutes'
        ORDER BY legacy.observed_at DESC,legacy.id DESC
        LIMIT {max(768, min(32768, int(candidate_row_limit)))}
        ), recent_source AS MATERIALIZED (
        SELECT legacy.*
        FROM candidate_source legacy
        ORDER BY coalesce(
                     nullif(legacy.source_payload->>'collected_at','')::timestamptz,
                     legacy.created_at
                 ) DESC,legacy.id DESC
        LIMIT {max(288, min(4096, int(source_row_limit)))}
        ), source_groups AS (
        SELECT legacy.provider, legacy.source_connector_key, legacy.exchange,
               legacy.underlying, legacy.expiry::text,
               date_trunc('minute',coalesce(
                   nullif(legacy.source_payload->>'collected_at','')::timestamptz,
                   legacy.created_at
               ))::text AS minute_ts,
               max(legacy.observed_at)::text AS source_timestamp,
               max(greatest(
                   coalesce(nullif(legacy.source_payload->>'collected_at','')::timestamptz,legacy.created_at),
                   legacy.observed_at
               ))::text AS received_at,
               count(*)::int AS contract_count,
               array_agg(legacy.id ORDER BY legacy.strike,legacy.option_type) AS source_snapshot_ids,
               max(legacy.spot_price)::float8 AS spot_price
        FROM recent_source legacy
        GROUP BY legacy.provider, legacy.source_connector_key, legacy.exchange,
                 legacy.underlying,legacy.expiry,date_trunc('minute',coalesce(
                     nullif(legacy.source_payload->>'collected_at','')::timestamptz,
                     legacy.created_at
                 ))
        )
        SELECT source.*
        FROM source_groups source
        LEFT JOIN trading.option_chain_snapshot_batches batch
          ON batch.provider=source.provider AND batch.exchange=source.exchange
         AND batch.underlying=source.underlying AND batch.expiry=source.expiry::date
         AND batch.minute_ts=source.minute_ts::timestamptz
        WHERE batch.id IS NULL
           OR batch.contract_count IS DISTINCT FROM source.contract_count
           OR NOT EXISTS (
                SELECT 1 FROM trading.option_oi_heatmap_cells heatmap
                WHERE heatmap.batch_id=batch.id AND heatmap.calculation_version={sql_literal(MODEL_VERSION)}
           )
           OR (
                EXISTS (
                    SELECT 1 FROM trading.option_valuation_policies policy
                    WHERE policy.active=true AND policy.validation_status='validated'
                      AND policy.provider=source.provider AND policy.exchange=source.exchange
                      AND policy.underlying=source.underlying
                      AND policy.effective_from<=source.source_timestamp::timestamptz
                      AND policy.expires_at>source.source_timestamp::timestamptz
                )
                AND NOT EXISTS (
                    SELECT 1 FROM trading.option_valuation_inputs valuation
                    WHERE valuation.batch_id=batch.id
                )
           )
        -- Materialize newest qualified evidence first so a delayed historical
        -- backfill can never block the current read-only desk from reflecting
        -- the latest accepted broker batch.
        ORDER BY source.minute_ts::timestamptz DESC
        LIMIT {max(1, int(limit))}
        """
    )


def historical_pending_groups(limit: int) -> list[dict[str, Any]]:
    """Maintenance-only historical backlog selector; never used by supervised runs."""
    return rows(
        f"""
        WITH source_groups AS (
        SELECT legacy.provider, legacy.source_connector_key, legacy.exchange,
               legacy.underlying, legacy.expiry::text, date_trunc('minute', legacy.observed_at)::text AS minute_ts,
               max(legacy.observed_at)::text AS source_timestamp,
               max(greatest(legacy.created_at, legacy.observed_at))::text AS received_at,
               count(*)::int AS contract_count,max(legacy.spot_price)::float8 AS spot_price
        FROM trading.option_chain_snapshots legacy
        WHERE legacy.observed_at <= now() + interval '5 minutes'
        GROUP BY legacy.provider,legacy.source_connector_key,legacy.exchange,
                 legacy.underlying,legacy.expiry,date_trunc('minute',legacy.observed_at)
        )
        SELECT source.* FROM source_groups source
        LEFT JOIN trading.option_chain_snapshot_batches batch
          ON batch.provider=source.provider AND batch.exchange=source.exchange
         AND batch.underlying=source.underlying AND batch.expiry=source.expiry::date
         AND batch.minute_ts=source.minute_ts::timestamptz
        WHERE batch.id IS NULL
           OR NOT EXISTS (
                SELECT 1 FROM trading.option_oi_heatmap_cells heatmap
                WHERE heatmap.batch_id=batch.id AND heatmap.calculation_version={sql_literal(MODEL_VERSION)}
           )
        ORDER BY source.minute_ts::timestamptz DESC
        LIMIT {max(1, int(limit))}
        """
    )


def pending_groups(
    limit: int,
    *,
    provider: str = DEFAULT_PROVIDER,
    maintenance_backfill: bool = False,
) -> list[dict[str, Any]]:
    if maintenance_backfill:
        return historical_pending_groups(limit)
    return current_pending_groups(limit, provider=provider)


def recent_valued_batches(limit: int) -> list[dict[str, Any]]:
    """Return source-backed valued batches still missing replay or volatility outputs."""
    return rows(
        f"""
        SELECT valued.*
        FROM (
            SELECT DISTINCT batch.id,batch.batch_key,batch.provider,batch.exchange,batch.underlying,
                   batch.expiry::text AS expiry,batch.minute_ts::text AS minute_ts,
                   batch.source_timestamp::text AS source_timestamp,
                   batch.received_at::text AS received_at,batch.spot_price::float8 AS spot_price
            FROM trading.option_chain_snapshot_batches batch
            JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=batch.id
            JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
            WHERE result.calculation_status='validated'
              AND result.quality_status IN ('passed','warning')
              AND (
                  NOT EXISTS (
                      SELECT 1 FROM trading.option_volatility_metrics metric
                      WHERE metric.batch_id=batch.id AND metric.calculation_version={sql_literal(MODEL_VERSION)}
                  )
                  OR NOT EXISTS (
                      SELECT 1 FROM trading.option_replay_frames frame
                      WHERE frame.batch_id=batch.id
                  )
              )
        ) valued
        ORDER BY valued.minute_ts::timestamptz DESC,valued.id DESC
        LIMIT {max(1, int(limit))}
        """
    )


def source_contracts(group: dict[str, Any]) -> list[dict[str, Any]]:
    source_snapshot_ids = [int(value) for value in (group.get("source_snapshot_ids") or [])]
    if source_snapshot_ids:
        source_filter = (
            "legacy.id=ANY(ARRAY["
            + ",".join(str(value) for value in source_snapshot_ids)
            + "]::bigint[])"
        )
    else:
        source_filter = (
            f"legacy.provider={sql_literal(group['provider'])} "
            f"AND legacy.exchange={sql_literal(group['exchange'])} "
            f"AND legacy.underlying={sql_literal(group['underlying'])} "
            f"AND legacy.expiry={sql_literal(group['expiry'])}::date "
            f"AND date_trunc('minute', legacy.observed_at)="
            f"{sql_literal(group['minute_ts'])}::timestamptz"
        )
    return rows(
        f"""
        SELECT legacy.id AS legacy_snapshot_id, legacy.instrument_token, legacy.trading_symbol,
               legacy.strike::float8, legacy.option_type, legacy.observed_at::text AS quote_source_timestamp,
               greatest(legacy.created_at, legacy.observed_at)::text AS received_at,
               legacy.last_price::float8, legacy.bid_price::float8, legacy.ask_price::float8,
               legacy.volume::float8, legacy.open_interest::float8,
               legacy.payload_hash AS source_payload_hash, legacy.source_payload,
               coalesce(nullif(instrument.lot_size, 0), 1)::float8 AS contract_multiplier
        FROM trading.option_chain_snapshots legacy
        LEFT JOIN market.zerodha_instruments instrument
          ON instrument.instrument_token::text=legacy.instrument_token
        WHERE {source_filter}
        ORDER BY legacy.strike, legacy.option_type
        """
    )


def quality_for_contract(contract: dict[str, Any]) -> dict[str, Any]:
    observed = parse_timestamp(contract["quote_source_timestamp"])
    received = parse_timestamp(contract["received_at"])
    age = max(0, int((received - observed).total_seconds()))
    bid = contract.get("bid_price")
    ask = contract.get("ask_price")
    flags: list[str] = []
    spread_absolute = None
    spread_bps = None
    if bid is None or ask is None:
        flags.append("missing_two_sided_quote")
    elif float(bid) > float(ask):
        flags.append("crossed_quote")
    else:
        spread_absolute = float(ask) - float(bid)
        midpoint = (float(ask) + float(bid)) / 2.0
        spread_bps = spread_absolute / midpoint * 10000.0 if midpoint > 0 else None
        if midpoint <= 0:
            flags.append("empty_quote")
        elif spread_bps is not None and spread_bps > 500:
            flags.append("spread_too_wide")
    if float(contract.get("open_interest") or 0) <= 0:
        flags.append("missing_open_interest")
    freshness = "live" if age <= 120 else "delayed" if age <= 900 else "stale"
    liquid = not flags
    return {
        "source_age_seconds": age,
        "spread_absolute": spread_absolute,
        "spread_bps": spread_bps,
        "staleness_status": freshness,
        "liquidity_status": "liquid" if liquid else "illiquid",
        "liquidity_score": 1.0 if liquid else 0.0,
        "liquidity_flags": flags,
    }


def create_batch(group: dict[str, Any], contracts: list[dict[str, Any]]) -> dict[str, Any]:
    source_ts = parse_timestamp(group["source_timestamp"])
    received_at = parse_timestamp(group["received_at"])
    source_age = max(0, int((received_at - source_ts).total_seconds()))
    freshness = "live" if source_age <= 120 else "delayed" if source_age <= 900 else "stale"
    flags: list[str] = []
    if not group.get("spot_price"):
        flags.append("missing_spot")
    if len(contracts) < 4:
        flags.append("insufficient_contracts")
    quality = "passed" if not flags else "warning" if contracts else "failed"
    batch_key = ":".join([
        str(group["provider"]), str(group["exchange"]), str(group["underlying"]),
        str(group["expiry"]), parse_timestamp(group["minute_ts"]).strftime("%Y%m%dT%H%MZ"),
    ])
    lineage = {
        "source_table": "trading.option_chain_snapshots",
        "legacy_snapshot_ids": [contract["legacy_snapshot_id"] for contract in contracts],
        "materializer": "materialize_institutional_options.py",
    }
    payload_hash = canonical_hash([contract["source_payload_hash"] for contract in contracts])
    changed = write_returning(
        """
        INSERT INTO trading.option_chain_snapshot_batches
            (batch_key,provider,source_connector_key,exchange,underlying,expiry,minute_ts,
             source_timestamp,received_at,underlying_source_timestamp,spot_price,contract_count,
             expected_contract_count,staleness_threshold_seconds,source_age_seconds,freshness_status,
             completeness_ratio,quality_status,quality_flags,source_payload_hash,source_artifact_ref,lineage,
             broker_write_allowed)
        VALUES
        """
        f"({sql_literal(batch_key)},{sql_literal(group['provider'])},{sql_literal(group['source_connector_key'])},"
        f"{sql_literal(group['exchange'])},{sql_literal(group['underlying'])},{sql_literal(group['expiry'])}::date,"
        f"{sql_literal(group['minute_ts'])}::timestamptz,{sql_literal(group['source_timestamp'])}::timestamptz,"
        f"{sql_literal(group['received_at'])}::timestamptz,{sql_literal(group['source_timestamp'])}::timestamptz,"
        f"{group.get('spot_price') or 'NULL'},{len(contracts)},NULL,120,{source_age},{sql_literal(freshness)},NULL,"
        f"{sql_literal(quality)},{text_array(flags)},{sql_literal(payload_hash)},"
        f"{sql_literal('db://trading.option_chain_snapshots/' + batch_key)},{sql_jsonb(lineage)},false) "
        "ON CONFLICT (batch_key) DO UPDATE SET "
        "source_timestamp=EXCLUDED.source_timestamp,received_at=EXCLUDED.received_at,"
        "underlying_source_timestamp=EXCLUDED.underlying_source_timestamp,spot_price=EXCLUDED.spot_price,"
        "contract_count=EXCLUDED.contract_count,source_age_seconds=EXCLUDED.source_age_seconds,"
        "freshness_status=EXCLUDED.freshness_status,quality_status=EXCLUDED.quality_status,"
        "quality_flags=EXCLUDED.quality_flags,source_payload_hash=EXCLUDED.source_payload_hash,"
        "source_artifact_ref=EXCLUDED.source_artifact_ref,lineage=EXCLUDED.lineage RETURNING *"
    )
    if not changed:
        raise RuntimeError("batch upsert returned no row")
    return changed[0]


def create_contracts(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not contracts:
        return []
    values: list[str] = []
    for contract in contracts:
        quality = quality_for_contract(contract)
        source_fields = {
            "legacy_snapshot_id": contract["legacy_snapshot_id"],
            "source_payload": contract.get("source_payload") or {},
        }
        values.append(
            "(" + ",".join([
                sql_literal(contract.get("instrument_token")),
                sql_literal(contract["trading_symbol"]),
                numeric_sql(contract["strike"]),
                sql_literal(contract["option_type"]),
                numeric_sql(contract["contract_multiplier"]),
                sql_literal(contract["quote_source_timestamp"]),
                sql_literal(contract["received_at"]),
                numeric_sql(contract.get("last_price")),
                numeric_sql(contract.get("bid_price")),
                numeric_sql(contract.get("ask_price")),
                numeric_sql(contract.get("volume")),
                numeric_sql(contract.get("open_interest")),
                str(int(quality["source_age_seconds"])),
                numeric_sql(quality["spread_absolute"]),
                numeric_sql(quality["spread_bps"]),
                numeric_sql(quality["liquidity_score"]),
                sql_literal(quality["staleness_status"]),
                sql_literal(quality["liquidity_status"]),
                text_array(quality["liquidity_flags"]),
                sql_jsonb(source_fields),
                sql_literal(contract["source_payload_hash"]),
            ]) + ")"
        )
    return write_returning(
        """
        WITH input(instrument_token,trading_symbol,strike,option_type,contract_multiplier,
                   quote_source_timestamp,received_at,last_price,bid_price,ask_price,volume,
                   open_interest,source_age_seconds,spread_absolute,spread_bps,liquidity_score,
                   staleness_status,liquidity_status,liquidity_flags,source_fields,source_payload_hash) AS (
            VALUES
        """
        + ",".join(values)
        + """
        ), enriched AS (
            SELECT input.*,prior.open_interest AS previous_open_interest
            FROM input
            LEFT JOIN LATERAL (
                SELECT previous.open_interest
                FROM trading.option_chain_contract_snapshots previous
                JOIN trading.option_chain_snapshot_batches previous_batch
                  ON previous_batch.id=previous.batch_id
                WHERE previous_batch.provider="""
        + sql_literal(batch["provider"])
        + " AND previous_batch.exchange=" + sql_literal(batch["exchange"])
        + " AND previous_batch.underlying=" + sql_literal(batch["underlying"])
        + " AND previous_batch.expiry=" + sql_literal(str(batch["expiry"])) + "::date"
        + " AND previous.strike=input.strike::numeric AND previous.option_type=input.option_type::text"
        + " AND previous_batch.minute_ts < " + sql_literal(str(batch["minute_ts"])) + "::timestamptz"
        + """
                ORDER BY previous_batch.minute_ts DESC,previous.id DESC LIMIT 1
            ) prior ON true
        )
        INSERT INTO trading.option_chain_contract_snapshots
            (batch_id,instrument_token,trading_symbol,strike,option_type,contract_multiplier,
             quote_source_timestamp,received_at,last_price,bid_price,ask_price,volume,open_interest,
             previous_open_interest,source_age_seconds,spread_absolute,spread_bps,liquidity_score,
             staleness_status,liquidity_status,liquidity_flags,source_fields,source_payload_hash,
             broker_write_allowed)
        SELECT """
        + str(int(batch["id"]))
        + """,instrument_token::text,trading_symbol::text,strike::numeric,option_type::text,
               contract_multiplier::numeric,quote_source_timestamp::timestamptz,received_at::timestamptz,
               last_price::numeric,bid_price::numeric,ask_price::numeric,volume::numeric,
               open_interest::numeric,previous_open_interest::numeric,source_age_seconds::integer,
               spread_absolute::numeric,spread_bps::numeric,liquidity_score::numeric,
               staleness_status::text,liquidity_status::text,liquidity_flags::text[],
               source_fields::jsonb,source_payload_hash::text,false
        FROM enriched
        ON CONFLICT (batch_id,strike,option_type) DO UPDATE SET
            instrument_token=EXCLUDED.instrument_token,trading_symbol=EXCLUDED.trading_symbol,
            contract_multiplier=EXCLUDED.contract_multiplier,quote_source_timestamp=EXCLUDED.quote_source_timestamp,
            received_at=EXCLUDED.received_at,last_price=EXCLUDED.last_price,bid_price=EXCLUDED.bid_price,
            ask_price=EXCLUDED.ask_price,volume=EXCLUDED.volume,open_interest=EXCLUDED.open_interest,
            previous_open_interest=EXCLUDED.previous_open_interest,source_age_seconds=EXCLUDED.source_age_seconds,
            spread_absolute=EXCLUDED.spread_absolute,spread_bps=EXCLUDED.spread_bps,
            liquidity_score=EXCLUDED.liquidity_score,staleness_status=EXCLUDED.staleness_status,
            liquidity_status=EXCLUDED.liquidity_status,liquidity_flags=EXCLUDED.liquidity_flags,
            source_fields=EXCLUDED.source_fields,source_payload_hash=EXCLUDED.source_payload_hash
        RETURNING *
        """
    )


def persist_source_premium_series(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> int:
    source_contracts = [
        {
            **contract,
            "_premium_quality_flags": list(contract.get("liquidity_flags") or []),
            "_premium_price_field": (
                "mid" if contract.get("bid_price") not in (None, 0)
                and contract.get("ask_price") not in (None, 0) else "last"
            ),
        }
        for contract in contracts
    ]
    calculated = premium_series(source_contracts, float(batch["spot_price"]))
    by_strike_type = {
        (float(row["strike"]), "call" if row["option_type"] == "CE" else "put"): row
        for row in contracts
    }
    written = 0
    for series_type in ("atm_straddle", "strangle"):
        series = calculated.get(series_type)
        if not series:
            continue
        call = by_strike_type.get((float(series["call_strike"]), "call"))
        put = by_strike_type.get((float(series["put_strike"]), "put"))
        if not call or not put:
            continue
        changed = write_returning(
            """
            INSERT INTO trading.option_premium_series
                (batch_id,series_type,call_contract_snapshot_id,put_contract_snapshot_id,reference_spot,
                 call_strike,put_strike,call_premium,put_premium,combined_premium,selection_method,
                 calculation_version,quality_status,quality_flags,assumptions,broker_write_allowed)
            VALUES
            """
            f"({batch['id']},{sql_literal(series_type)},{call['id']},{put['id']},{series['reference_spot']},"
            f"{series['call_strike']},{series['put_strike']},{series['call_premium']},{series['put_premium']},"
            f"{series['combined_premium']},{sql_literal(series['selection_method'])},{sql_literal(MODEL_VERSION)},"
            f"{sql_literal(series['quality_status'])},{text_array(series.get('quality_flags') or [])},"
            f"{sql_jsonb(series.get('assumptions') or {})},false) "
            "ON CONFLICT (batch_id,series_type,call_strike,put_strike) DO UPDATE SET "
            "call_premium=EXCLUDED.call_premium,put_premium=EXCLUDED.put_premium,"
            "combined_premium=EXCLUDED.combined_premium,quality_status=EXCLUDED.quality_status,"
            "quality_flags=EXCLUDED.quality_flags,assumptions=EXCLUDED.assumptions RETURNING id"
        )
        written += len(changed)
    return written


def persist_market_structure(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> dict[str, int]:
    max_oi = max((float(row.get("open_interest") or 0) for row in contracts), default=0.0)
    heatmap = buildup = migrations = 0
    heatmap_values: list[str] = []
    for contract in contracts:
        oi = float(contract.get("open_interest") or 0)
        previous_oi = contract.get("previous_open_interest")
        oi_change = oi - float(previous_oi) if previous_oi is not None else None
        quality_flags = [] if contract.get("open_interest") is not None else ["missing_open_interest"]
        heatmap_values.append(
            f"({batch['id']},{numeric_sql(contract['strike'])},{sql_literal(contract['option_type'])},"
            f"{numeric_sql(oi)},{numeric_sql(oi_change)},{numeric_sql(contract.get('volume') or 0)},"
            f"{numeric_sql(oi / max_oi if max_oi > 0 else 0)},{sql_literal(MODEL_VERSION)},"
            f"{sql_literal('passed' if not quality_flags else 'warning')},{text_array(quality_flags)},false)"
        )
    if heatmap_values:
        changed = write_returning(
            """
            INSERT INTO trading.option_oi_heatmap_cells
                (batch_id,strike,option_type,open_interest,open_interest_change,volume,
                 normalized_intensity,calculation_version,quality_status,quality_flags,broker_write_allowed)
            VALUES
            """ + ",".join(heatmap_values) + " "
            "ON CONFLICT (batch_id,strike,option_type,calculation_version) DO UPDATE SET "
            "open_interest=EXCLUDED.open_interest,open_interest_change=EXCLUDED.open_interest_change,"
            "volume=EXCLUDED.volume,normalized_intensity=EXCLUDED.normalized_intensity,"
            "quality_status=EXCLUDED.quality_status,quality_flags=EXCLUDED.quality_flags RETURNING id"
        )
        heatmap += len(changed)

    prior_batches = rows(
        f"""
        SELECT id,minute_ts::text
        FROM trading.option_chain_snapshot_batches
        WHERE provider={sql_literal(batch['provider'])} AND exchange={sql_literal(batch['exchange'])}
          AND underlying={sql_literal(batch['underlying'])}
          AND expiry={sql_literal(str(batch['expiry']))}::date
          AND minute_ts < {sql_literal(str(batch['minute_ts']))}::timestamptz
        ORDER BY minute_ts DESC LIMIT 1
        """
    )
    if not prior_batches:
        return {"heatmap": heatmap, "buildup": 0, "migrations": 0}
    prior_batch = prior_batches[0]
    prior_contracts = rows(
        f"SELECT id,strike::float8,option_type,last_price::float8,open_interest::float8,volume::float8 "
        f"FROM trading.option_chain_contract_snapshots WHERE batch_id={prior_batch['id']}"
    )
    prior_map = {(float(row["strike"]), row["option_type"]): row for row in prior_contracts}
    prior_oi_changes = rows(
        f"SELECT strike::float8,option_type,open_interest_change::float8 "
        f"FROM trading.option_oi_heatmap_cells WHERE batch_id={prior_batch['id']} "
        f"AND calculation_version={sql_literal(MODEL_VERSION)} "
        "AND open_interest_change IS NOT NULL"
    )
    changes: list[dict[str, Any]] = []
    buildup_values: list[str] = []
    for contract in contracts:
        prior = prior_map.get((float(contract["strike"]), contract["option_type"]))
        if not prior or contract.get("last_price") is None or prior.get("last_price") is None:
            continue
        price_change = float(contract["last_price"]) - float(prior["last_price"])
        oi_change = float(contract.get("open_interest") or 0) - float(prior.get("open_interest") or 0)
        classification = classify_buildup(price_change, oi_change)
        buildup_values.append(
            f"({contract['id']},{prior['id']},{numeric_sql(price_change)},{numeric_sql(oi_change)},"
            f"{numeric_sql(oi_change / float(prior['open_interest']) * 100) if float(prior.get('open_interest') or 0) else 'NULL'},"
            f"{sql_literal(classification)},{sql_literal(MODEL_VERSION)},'passed','{{}}'::text[],"
            f"{sql_jsonb({'comparison': 'immediately_prior_source_batch', 'from_batch_id': prior_batch['id'], 'to_batch_id': batch['id']})},false)"
        )
        changes.append({**contract, "open_interest_change": oi_change})
    if buildup_values:
        changed = write_returning(
            """
            INSERT INTO trading.option_buildup_classifications
                (contract_snapshot_id,comparison_contract_snapshot_id,price_change,open_interest_change,
                 open_interest_change_percent,classification,classification_version,quality_status,
                 quality_flags,assumptions,broker_write_allowed)
            VALUES
            """ + ",".join(buildup_values) + " "
            "ON CONFLICT (contract_snapshot_id,comparison_contract_snapshot_id,classification_version) DO UPDATE SET "
            "price_change=EXCLUDED.price_change,open_interest_change=EXCLUDED.open_interest_change,"
            "open_interest_change_percent=EXCLUDED.open_interest_change_percent,"
            "classification=EXCLUDED.classification RETURNING id"
        )
        buildup += len(changed)

    def peak(source: list[dict[str, Any]], option_type: str, field: str) -> dict[str, Any] | None:
        candidates = [row for row in source if row.get("option_type") == option_type]
        return max(candidates, key=lambda row: abs(float(row.get(field) or 0)), default=None)

    for option_type in ("CE", "PE"):
        for metric_name, field in (
            ("max_open_interest", "open_interest"),
            ("volume_peak", "volume"),
            ("max_oi_change", "open_interest_change"),
        ):
            current_source = changes if field == "open_interest_change" else contracts
            previous_source = prior_oi_changes if field == "open_interest_change" else prior_contracts
            current = peak(current_source, option_type, field)
            previous = peak(previous_source, option_type, field)
            if not current or not previous:
                continue
            changed = write_returning(
                """
                INSERT INTO trading.option_strike_migrations
                    (from_batch_id,to_batch_id,option_type,metric_name,from_strike,to_strike,
                     migration_points,calculation_version,quality_status,assumptions,broker_write_allowed)
                VALUES
                """
                f"({prior_batch['id']},{batch['id']},{sql_literal(option_type)},{sql_literal(metric_name)},"
                f"{previous['strike']},{current['strike']},{float(current['strike']) - float(previous['strike'])},"
                f"{sql_literal(MODEL_VERSION)},'passed',"
                f"{sql_jsonb({'comparison': 'immediately_prior_source_batch', 'source_field': field})},false) "
                "ON CONFLICT (from_batch_id,to_batch_id,option_type,metric_name,calculation_version) DO UPDATE SET "
                "from_strike=EXCLUDED.from_strike,to_strike=EXCLUDED.to_strike,"
                "migration_points=EXCLUDED.migration_points RETURNING id"
            )
            migrations += len(changed)
        wall_name = "call_wall" if option_type == "CE" else "put_wall"
        current = peak(contracts, option_type, "open_interest")
        previous = peak(prior_contracts, option_type, "open_interest")
        if current and previous:
            changed = write_returning(
                """
                INSERT INTO trading.option_strike_migrations
                    (from_batch_id,to_batch_id,option_type,metric_name,from_strike,to_strike,
                     migration_points,calculation_version,quality_status,assumptions,broker_write_allowed)
                VALUES
                """
                f"({prior_batch['id']},{batch['id']},{sql_literal(option_type)},{sql_literal(wall_name)},"
                f"{previous['strike']},{current['strike']},{float(current['strike']) - float(previous['strike'])},"
                f"{sql_literal(MODEL_VERSION)},'passed',"
                f"{sql_jsonb({'definition': 'maximum observed open interest strike'})},false) "
                "ON CONFLICT (from_batch_id,to_batch_id,option_type,metric_name,calculation_version) DO UPDATE SET "
                "from_strike=EXCLUDED.from_strike,to_strike=EXCLUDED.to_strike,"
                "migration_points=EXCLUDED.migration_points RETURNING id"
            )
            migrations += len(changed)
    return {"heatmap": heatmap, "buildup": buildup, "migrations": migrations}


def persist_specialist_observation(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> int:
    calls = [row for row in contracts if row["option_type"] == "CE"]
    puts = [row for row in contracts if row["option_type"] == "PE"]
    if not calls or not puts:
        return 0
    call_wall = max(calls, key=lambda row: float(row.get("open_interest") or 0))
    put_wall = max(puts, key=lambda row: float(row.get("open_interest") or 0))
    evidence = [
        {"kind": "option_batch", "ref": f"db://trading.option_chain_snapshot_batches/{batch['id']}"},
        {"kind": "call_wall_contract", "ref": f"db://trading.option_chain_contract_snapshots/{call_wall['id']}"},
        {"kind": "put_wall_contract", "ref": f"db://trading.option_chain_contract_snapshots/{put_wall['id']}"},
    ]
    headline = f"{batch['underlying']} observed OI walls: call {call_wall['strike']}, put {put_wall['strike']}"
    observation = (
        f"At {batch['source_timestamp']}, maximum observed call OI was at {call_wall['strike']} "
        f"and maximum observed put OI was at {put_wall['strike']}. This is positioning evidence only; "
        "open interest does not identify trade direction or dealer ownership."
    )
    changed = write_returning(
        """
        INSERT INTO trading.option_specialist_observations
            (observation_key,batch_id,specialist_agent,observation_type,observation_status,as_of,
             headline,observation,confidence,evidence_refs,assumptions,limitations,quality_status,
             human_review_required,capital_action_allowed,broker_write_allowed)
        VALUES
        """
        f"({sql_literal('options-oi-walls:' + str(batch['id']))},{batch['id']},'Options Analyst',"
        f"'oi_walls','published',{sql_literal(str(batch['source_timestamp']))}::timestamptz,"
        f"{sql_literal(headline)},{sql_literal(observation)},0.55,{sql_jsonb(evidence)},"
        f"{sql_jsonb({'wall_definition': 'maximum observed open interest by option type'})},"
        f"{sql_jsonb(['No observed trade side', 'No dealer ownership data', 'Human review required before any decision'])},"
        "'warning',true,false,false) ON CONFLICT (observation_key) DO UPDATE SET "
        "headline=EXCLUDED.headline,observation=EXCLUDED.observation,evidence_refs=EXCLUDED.evidence_refs,"
        "assumptions=EXCLUDED.assumptions,limitations=EXCLUDED.limitations,updated_at=now() RETURNING id"
    )
    return len(changed)


def rebuild_point_in_time_replay(batch: dict[str, Any]) -> int:
    scope = rows(
        f"""
        SELECT id,batch_key,minute_ts::text,source_timestamp::text,received_at::text,
               spot_price::float8,quality_status,freshness_status
        FROM trading.option_chain_snapshot_batches
        WHERE provider={sql_literal(batch['provider'])} AND exchange={sql_literal(batch['exchange'])}
          AND underlying={sql_literal(batch['underlying'])}
          AND expiry={sql_literal(str(batch['expiry']))}::date
          AND quality_status IN ('passed','warning')
        ORDER BY source_timestamp,received_at,id
        """
    )
    if len(scope) < 2:
        return 0
    payload = [
        {
            **row,
            "frame_state": {
                "spot_price": row.get("spot_price"),
                "quality_status": row.get("quality_status"),
                "freshness_status": row.get("freshness_status"),
                "source_batch_id": row["id"],
            },
        }
        for row in scope
    ]
    frames: list[dict[str, Any]] = []
    for event in payload:
        event_frames = replay_frames([event], [event["received_at"]])
        if event_frames:
            frames.append(event_frames[0])
    if len(frames) < 2:
        return 0
    by_key = {row["batch_key"]: row for row in scope}
    replay_start = scope[0]["minute_ts"]
    replay_end = scope[-1]["received_at"]
    maximum_source = max(parse_timestamp(row["source_timestamp"]) for row in scope).isoformat()
    session_key = ":".join([
        "options-replay", str(batch["provider"]), str(batch["exchange"]),
        str(batch["underlying"]), str(batch["expiry"]), MODEL_VERSION,
    ])
    changed = write_returning(
        """
        INSERT INTO trading.option_replay_sessions
            (session_key,exchange,underlying,expiry,replay_start,replay_end,replay_clock,status,
             maximum_available_source_timestamp,speed_multiplier,point_in_time_enforced,created_by,
             metadata,paper_only,broker_write_allowed)
        VALUES
        """
        f"({sql_literal(session_key)},{sql_literal(batch['exchange'])},{sql_literal(batch['underlying'])},"
        f"{sql_literal(str(batch['expiry']))}::date,{sql_literal(replay_start)}::timestamptz,"
        f"{sql_literal(replay_end)}::timestamptz,{sql_literal(replay_end)}::timestamptz,'completed',"
        f"{sql_literal(maximum_source)}::timestamptz,1,true,'Options Data Quality Agent',"
        f"{sql_jsonb({'source': 'immutable_option_batches', 'lookahead_allowed': False})},true,false) "
        "ON CONFLICT (session_key) DO UPDATE SET replay_start=EXCLUDED.replay_start,"
        "replay_end=EXCLUDED.replay_end,replay_clock=EXCLUDED.replay_clock,status='completed',"
        "maximum_available_source_timestamp=EXCLUDED.maximum_available_source_timestamp,"
        "metadata=EXCLUDED.metadata,updated_at=now() RETURNING id"
    )
    if not changed:
        return 0
    session_id = int(changed[0]["id"])
    materializer_psql_json(
        f"DELETE FROM trading.option_replay_frames WHERE replay_session_id={session_id}; "
        "SELECT '[]'::json::text"
    )
    written = 0
    for frame_number, frame in enumerate(frames):
        source = by_key[str(frame["batch_key"])]
        changed_frame = write_returning(
            """
            INSERT INTO trading.option_replay_frames
                (replay_session_id,batch_id,frame_number,replay_timestamp,source_timestamp,
                 frame_state,broker_write_allowed)
            VALUES
            """
            f"({session_id},{source['id']},{frame_number},"
            f"{sql_literal(frame['replay_timestamp'])}::timestamptz,"
            f"{sql_literal(frame['source_timestamp'])}::timestamptz,"
            f"{sql_jsonb(frame['frame_state'])},false) RETURNING id"
        )
        written += len(changed_frame)
    return written


def active_policy(batch: dict[str, Any]) -> dict[str, Any] | None:
    found = rows(
        f"""
        SELECT * FROM trading.option_valuation_policies
        WHERE active=true AND validation_status='validated'
          AND provider={sql_literal(batch['provider'])}
          AND exchange={sql_literal(batch['exchange'])}
          AND underlying={sql_literal(batch['underlying'])}
          AND effective_from <= {sql_literal(str(batch['source_timestamp']))}::timestamptz
          AND expires_at > {sql_literal(str(batch['source_timestamp']))}::timestamptz
        ORDER BY effective_from DESC, id DESC LIMIT 1
        """
    )
    return found[0] if found else None


def expiry_timestamp(batch: dict[str, Any], policy: dict[str, Any]) -> datetime:
    local_time = time.fromisoformat(str(policy["expiry_local_time"]))
    local_date = datetime.fromisoformat(str(batch["expiry"])).date()
    return datetime.combine(local_date, local_time, ZoneInfo(str(policy["expiry_timezone"]))).astimezone(timezone.utc)


def valuation_reference(batch: dict[str, Any], policy: dict[str, Any], year_fraction: float) -> dict[str, Any]:
    spot = float(batch["spot_price"])
    if not math.isfinite(spot) or spot <= 0:
        raise ValueError("batch spot_price must be positive and finite")
    model = str(policy["model_family"])
    if model == "black_scholes_merton":
        return {
            "spot_price": spot,
            "forward_price": None,
            "reference_price": spot,
            "reference_kind": "spot",
            "forward_method": "spot_reference",
        }
    if model != "black_76":
        raise ValueError("unsupported option valuation model")
    rate = float(policy["risk_free_rate"])
    dividend = float(policy["dividend_yield"])
    forward = spot * math.exp((rate - dividend) * year_fraction)
    return {
        "spot_price": spot,
        "forward_price": forward,
        "reference_price": forward,
        "reference_kind": "derived_forward",
        "forward_method": "spot_rate_dividend_carry",
    }


def create_valuation_input(batch: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    valuation_ts = parse_timestamp(batch["source_timestamp"])
    expiry_ts = expiry_timestamp(batch, policy)
    if valuation_ts >= expiry_ts:
        raise ValueError("batch source timestamp is at or after option expiry")
    year_fraction = (expiry_ts - valuation_ts).total_seconds() / (365.0 * 86400.0)
    reference = valuation_reference(batch, policy, year_fraction)
    input_key = f"policy:{policy['policy_key']}"
    assumptions = {
        "policy_id": policy["id"],
        "source_artifact_ref": policy["source_artifact_ref"],
        "expiry_timezone": policy["expiry_timezone"],
        "no_default_inputs": True,
        "reference_kind": reference["reference_kind"],
        "forward_formula": "spot * exp((risk_free_rate - dividend_yield) * time_to_expiry)" if reference["forward_price"] is not None else None,
    }
    input_hash = canonical_hash({
        "batch_id": batch["id"], "policy_id": policy["id"], "spot": reference["spot_price"],
        "forward": reference["forward_price"], "reference": reference["reference_price"],
        "rate": policy["risk_free_rate"], "dividend": policy["dividend_yield"],
        "valuation_ts": valuation_ts.isoformat(), "expiry_ts": expiry_ts.isoformat(),
    })
    changed = write_returning(
        """
        INSERT INTO trading.option_valuation_inputs
            (batch_id,input_key,model_family,valuation_timestamp,spot_price,forward_price,risk_free_rate,dividend_yield,
             time_to_expiry_years,day_count_convention,expiry_timestamp,spot_source_timestamp,
             rate_source_timestamp,dividend_source_timestamp,forward_method,rate_source,dividend_source,
             input_quality_status,quality_flags,assumptions,input_hash,broker_write_allowed)
        VALUES
        """
        f"({batch['id']},{sql_literal(input_key)},{sql_literal(policy['model_family'])},"
        f"{sql_literal(valuation_ts.isoformat())}::timestamptz,{reference['spot_price']},"
        f"{reference['forward_price'] if reference['forward_price'] is not None else 'NULL'},{policy['risk_free_rate']},"
        f"{policy['dividend_yield']},{year_fraction},{sql_literal(policy['day_count_convention'])},"
        f"{sql_literal(expiry_ts.isoformat())}::timestamptz,{sql_literal(str(batch['source_timestamp']))}::timestamptz,"
        f"{sql_literal(str(policy['rate_source_timestamp']))}::timestamptz,"
        f"{sql_literal(str(policy['dividend_source_timestamp']))}::timestamptz,{sql_literal(reference['forward_method'])},"
        f"{sql_literal(policy['rate_source'])},{sql_literal(policy['dividend_source'])},'passed','{{}}'::text[],"
        f"{sql_jsonb(assumptions)},{sql_literal(input_hash)},false) "
        "ON CONFLICT (batch_id,input_key) DO UPDATE SET input_hash=EXCLUDED.input_hash RETURNING *"
    )
    return changed[0]


def analysis_as_of(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> datetime:
    """Return the first clock at which the complete captured batch was available.

    The batch header can be persisted a fraction of a second before its contract
    rows. Using the header timestamp made every contract look like future data
    even though the immutable quote timestamp preceded ingestion. Point-in-time
    analysis therefore uses the latest received timestamp in the batch while
    retaining exchange/source timestamps separately for lineage.
    """
    clocks = [parse_timestamp(batch["received_at"])]
    clocks.extend(parse_timestamp(row["received_at"]) for row in contracts)
    return max(clocks)


def persist_analytics(batch: dict[str, Any], valuation: dict[str, Any], contracts: list[dict[str, Any]]) -> dict[str, int]:
    payload_contracts = [
        {
            "trading_symbol": row["trading_symbol"], "strike": row["strike"],
            "option_type": row["option_type"], "contract_multiplier": row["contract_multiplier"],
            "quote_source_timestamp": row["quote_source_timestamp"], "received_at": row["received_at"],
            "last_price": row.get("last_price"), "bid_price": row.get("bid_price"),
            "ask_price": row.get("ask_price"), "volume": row.get("volume"),
            "open_interest": row.get("open_interest"),
        }
        for row in contracts
    ]
    result = analyze_chain({
        "as_of": analysis_as_of(batch, contracts).isoformat(), "dry_run": True,
        "valuation": {
            "model": valuation["model_family"], "valuation_timestamp": str(valuation["valuation_timestamp"]),
            "spot_price": float(valuation["spot_price"]),
            "forward_price": float(valuation["forward_price"]) if valuation.get("forward_price") is not None else None,
            "risk_free_rate": float(valuation["risk_free_rate"]),
            "dividend_yield": float(valuation["dividend_yield"] or 0),
            "time_to_expiry_years": float(valuation["time_to_expiry_years"]),
        },
        "contracts": payload_contracts,
    })
    by_symbol = {row["trading_symbol"]: row for row in contracts}
    greek_ids: list[int] = []
    for calculated in result["contracts"]:
        contract = by_symbol.get(calculated.get("trading_symbol"))
        if not contract:
            continue
        calc_status = calculated["calculation_status"]
        quality = calculated["quality_status"]
        calc_hash = canonical_hash({"contract_id": contract["id"], "valuation_id": valuation["id"], "result": calculated})
        changed = write_returning(
            """
            INSERT INTO trading.option_iv_greeks_results
                (contract_snapshot_id,valuation_input_id,price_field_used,option_price_used,model_name,
                 model_version,solver_name,solver_version,calculation_status,converged,iteration_count,residual,
                 implied_volatility,delta,gamma,theta,vega,rho,intrinsic_value,time_value,
                 no_arbitrage_lower_bound,no_arbitrage_upper_bound,quality_status,quality_flags,
                 calculation_hash,computed_at,validated_at,validated_by,broker_write_allowed)
            VALUES
            """
            f"({contract['id']},{valuation['id']},{sql_literal(calculated.get('price_field_used') or 'last')},"
            f"{calculated.get('option_price_used') or 0},{sql_literal(valuation['model_family'])},"
            f"{sql_literal(MODEL_VERSION)},'bounded_bisection',{sql_literal(SOLVER_VERSION)},"
            f"{sql_literal(calc_status)},{str(bool(calculated['converged'])).lower()},"
            f"{calculated.get('iteration_count') if calculated.get('iteration_count') is not None else 'NULL'},"
            f"{calculated.get('residual') if calculated.get('residual') is not None else 'NULL'},"
            + ",".join(
                str(calculated.get(field)) if calculated.get(field) is not None else "NULL"
                for field in ("implied_volatility","delta","gamma","theta","vega","rho","intrinsic_value","time_value","no_arbitrage_lower_bound","no_arbitrage_upper_bound")
            )
            + f",{sql_literal(quality)},{text_array(calculated.get('quality_flags') or [])},{sql_literal(calc_hash)},now(),"
            + ("now(),'Options Data Quality Agent'" if calc_status == "validated" else "NULL,NULL")
            + ",false) ON CONFLICT (contract_snapshot_id,valuation_input_id,model_version,solver_version,price_field_used) "
              "DO UPDATE SET price_field_used=EXCLUDED.price_field_used,"
              "option_price_used=EXCLUDED.option_price_used,calculation_status=EXCLUDED.calculation_status,"
              "converged=EXCLUDED.converged,iteration_count=EXCLUDED.iteration_count,residual=EXCLUDED.residual,"
              "implied_volatility=EXCLUDED.implied_volatility,delta=EXCLUDED.delta,gamma=EXCLUDED.gamma,"
              "theta=EXCLUDED.theta,vega=EXCLUDED.vega,rho=EXCLUDED.rho,"
              "intrinsic_value=EXCLUDED.intrinsic_value,time_value=EXCLUDED.time_value,"
              "no_arbitrage_lower_bound=EXCLUDED.no_arbitrage_lower_bound,"
              "no_arbitrage_upper_bound=EXCLUDED.no_arbitrage_upper_bound,"
              "quality_status=EXCLUDED.quality_status,quality_flags=EXCLUDED.quality_flags,"
              "calculation_hash=EXCLUDED.calculation_hash,computed_at=EXCLUDED.computed_at,"
              "validated_at=EXCLUDED.validated_at,validated_by=EXCLUDED.validated_by RETURNING id"
        )
        greek_ids.extend(int(row["id"]) for row in changed)

    by_strike_type = {
        (float(row["strike"]), "call" if row["option_type"] == "CE" else "put"): row
        for row in contracts
    }
    premium_ids: list[int] = []
    premium_id_by_type: dict[str, int] = {}
    for series_type in ("atm_straddle", "strangle"):
        series = result["premium_series"].get(series_type)
        if not series:
            continue
        call = by_strike_type.get((float(series["call_strike"]), "call"))
        put = by_strike_type.get((float(series["put_strike"]), "put"))
        if not call or not put:
            continue
        changed = write_returning(
            """
            INSERT INTO trading.option_premium_series
                (batch_id,series_type,call_contract_snapshot_id,put_contract_snapshot_id,reference_spot,
                 call_strike,put_strike,call_premium,put_premium,combined_premium,selection_method,
                 calculation_version,quality_status,quality_flags,assumptions,broker_write_allowed)
            VALUES
            """
            f"({batch['id']},{sql_literal(series_type)},{call['id']},{put['id']},{series['reference_spot']},"
            f"{series['call_strike']},{series['put_strike']},{series['call_premium']},{series['put_premium']},"
            f"{series['combined_premium']},{sql_literal(series['selection_method'])},{sql_literal(MODEL_VERSION)},"
            f"{sql_literal(series['quality_status'])},{text_array(series.get('quality_flags') or [])},"
            f"{sql_jsonb(series.get('assumptions') or {})},false) "
            "ON CONFLICT (batch_id,series_type,call_strike,put_strike) DO UPDATE SET "
            "combined_premium=EXCLUDED.combined_premium,calculation_version=EXCLUDED.calculation_version "
            "RETURNING id"
        )
        if changed:
            premium_id = int(changed[0]["id"])
            premium_ids.append(premium_id)
            premium_id_by_type[series_type] = premium_id

    expected_ids: list[int] = []
    for move in result["expected_moves"]:
        source_id = premium_id_by_type.get("atm_straddle")
        if source_id is None:
            continue
        changed = write_returning(
            """
            INSERT INTO trading.option_expected_move_bands
                (batch_id,horizon_timestamp,method,model_version,confidence_level,reference_price,
                 expected_move_absolute,expected_move_percent,lower_band,upper_band,probability_method,
                 source_result_ids,assumptions,quality_status,quality_flags,broker_write_allowed)
            VALUES
            """
            f"({batch['id']},{sql_literal(str(valuation['expiry_timestamp']))}::timestamptz,"
            f"{sql_literal(move['method'])},{sql_literal(MODEL_VERSION)},{move['confidence_level']},"
            f"{move['reference_price']},{move['expected_move_absolute']},{move['expected_move_percent']},"
            f"{move['lower_band']},{move['upper_band']},{sql_literal(move['probability_method'])},"
            f"ARRAY[{source_id}]::bigint[],{sql_jsonb(move['assumptions'])},{sql_literal(move['quality_status'])},"
            f"{text_array(move.get('quality_flags') or [])},false) "
            "ON CONFLICT (batch_id,horizon_timestamp,method,model_version,confidence_level) DO UPDATE SET "
            "expected_move_absolute=EXCLUDED.expected_move_absolute,expected_move_percent=EXCLUDED.expected_move_percent,"
            "lower_band=EXCLUDED.lower_band,upper_band=EXCLUDED.upper_band,source_result_ids=EXCLUDED.source_result_ids "
            "RETURNING id"
        )
        expected_ids.extend(int(row["id"]) for row in changed)

    materializer_psql_json(
        f"DELETE FROM trading.option_exposure_estimates WHERE batch_id={batch['id']} "
        f"AND calculation_version={sql_literal(MODEL_VERSION)}; SELECT '[]'::json::text"
    )
    exposure_ids: list[int] = []
    exposure = result["exposure_estimates"]
    units = {
        "gex": "currency_delta_change_per_1pct_underlying_move",
        "dex": "currency_delta_notional",
        "vanna": "currency_delta_notional_change_per_1_vol_point",
        "charm": "currency_delta_notional_change_per_calendar_day",
        "gamma_flip": "underlying_price",
    }
    metrics = {**exposure["metrics"], "gamma_flip": exposure.get("gamma_flip")}
    source_ids = "ARRAY[" + ",".join(str(value) for value in greek_ids) + "]::bigint[]" if greek_ids else "ARRAY[]::bigint[]"
    assumptions = exposure["assumptions"]
    for metric_name, metric_value in metrics.items():
        quality = exposure["quality_status"]
        metric_assumptions = dict(assumptions)
        if metric_name == "gamma_flip":
            metric_assumptions.update({
                "crossing_found": metric_value is not None,
                "result_interpretation": (
                    "interpolated_crossing_within_tested_grid"
                    if metric_value is not None
                    else "no_crossing_within_tested_grid"
                ),
            })
        if metric_value is None:
            quality = "not_computable"
        changed = write_returning(
            """
            INSERT INTO trading.option_exposure_estimates
                (batch_id,exposure_scope,metric_name,metric_value,unit,dealer_position_assumption,
                 open_interest_sign_method,contract_multiplier,shock_size,spot_grid,source_result_ids,
                 coverage_ratio,calculation_version,assumptions,quality_status,quality_flags,
                 broker_write_allowed)
            VALUES
            """
            f"({batch['id']},'expiry',{sql_literal(metric_name)},"
            f"{metric_value if metric_value is not None else 'NULL'},{sql_literal(units[metric_name])},"
            f"{sql_literal(assumptions['dealer_position_assumption'])},"
            f"{sql_literal(assumptions['open_interest_sign_method'])},1,"
            f"{0.01 if metric_name == 'gex' else 'NULL'},{sql_jsonb(exposure.get('spot_grid') or [])},"
            f"{source_ids},{exposure['coverage_ratio']},{sql_literal(MODEL_VERSION)},"
            f"{sql_jsonb(metric_assumptions)},{sql_literal(quality)},'{{}}'::text[],false) RETURNING id"
        )
        exposure_ids.extend(int(row["id"]) for row in changed)
    return {
        "greeks": len(greek_ids),
        "premium_series": len(premium_ids),
        "expected_moves": len(expected_ids),
        "exposures": len(exposure_ids),
    }


def persist_volatility_metrics(batch: dict[str, Any]) -> int:
    current = rows(
        f"""
        SELECT result.id,result.implied_volatility::float8,result.delta::float8,
               contract.strike::float8,contract.option_type
        FROM trading.option_iv_greeks_results result
        JOIN trading.option_chain_contract_snapshots contract
          ON contract.id=result.contract_snapshot_id
        WHERE contract.batch_id={batch['id']}
          AND result.calculation_status='validated'
          AND result.quality_status IN ('passed','warning')
        ORDER BY contract.strike,contract.option_type
        """
    )
    if not current:
        return 0
    materializer_psql_json(
        f"DELETE FROM trading.option_volatility_metrics WHERE batch_id={batch['id']} "
        f"AND calculation_version={sql_literal(MODEL_VERSION)}; SELECT '[]'::json::text"
    )
    spot = float(batch["spot_price"])
    atm_distance = min(abs(float(row["strike"]) - spot) for row in current)
    atm_rows = [row for row in current if abs(float(row["strike"]) - spot) == atm_distance]
    atm_iv = sum(float(row["implied_volatility"]) for row in atm_rows) / len(atm_rows)
    atm_ids = [int(row["id"]) for row in atm_rows]
    current_cutoff = max(
        parse_timestamp(batch["source_timestamp"]),
        parse_timestamp(batch["received_at"]),
    )
    historical = rows(
        f"""
        SELECT source_batch.id AS batch_id,source_batch.source_timestamp::text,
               source_batch.spot_price::float8,result.id,
               result.implied_volatility::float8,contract.strike::float8
        FROM trading.option_chain_snapshot_batches source_batch
        JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=source_batch.id
        JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
        WHERE source_batch.provider={sql_literal(batch['provider'])}
          AND source_batch.exchange={sql_literal(batch['exchange'])}
          AND source_batch.underlying={sql_literal(batch['underlying'])}
          AND source_batch.expiry={sql_literal(str(batch['expiry']))}::date
          AND source_batch.source_timestamp<={sql_literal(str(batch['source_timestamp']))}::timestamptz
          AND source_batch.received_at<={sql_literal(str(batch['received_at']))}::timestamptz
          AND result.calculation_status='validated'
          AND result.quality_status IN ('passed','warning')
        ORDER BY source_batch.source_timestamp,source_batch.id,contract.strike
        """
    )
    history_by_batch: dict[int, list[dict[str, Any]]] = {}
    for row in historical:
        history_by_batch.setdefault(int(row["batch_id"]), []).append(row)
    atm_history: list[tuple[float, list[int]]] = []
    for batch_rows in history_by_batch.values():
        source_spot = float(batch_rows[0]["spot_price"])
        distance = min(abs(float(row["strike"]) - source_spot) for row in batch_rows)
        selected = [row for row in batch_rows if abs(float(row["strike"]) - source_spot) == distance]
        atm_history.append((
            sum(float(row["implied_volatility"]) for row in selected) / len(selected),
            [int(row["id"]) for row in selected],
        ))

    metrics: list[dict[str, Any]] = []
    if len(atm_history) >= 20:
        values = [value for value, _ in atm_history]
        minimum = min(values)
        maximum = max(values)
        rank = 50.0 if maximum == minimum else (atm_iv - minimum) / (maximum - minimum) * 100.0
        percentile = sum(1 for value in values if value <= atm_iv) / len(values) * 100.0
        history_ids = list(dict.fromkeys(identifier for _, ids in atm_history for identifier in ids))
        metrics.extend([
            {
                "metric_type": "iv_rank", "value": max(0.0, min(100.0, rank)),
                "observation_count": len(values), "lookback_days": 252,
                "source_ids": history_ids,
                "assumptions": {"series": "nearest-strike mean call-put IV", "minimum_observations": 20},
            },
            {
                "metric_type": "iv_percentile", "value": max(0.0, min(100.0, percentile)),
                "observation_count": len(values), "lookback_days": 252,
                "source_ids": history_ids,
                "assumptions": {"series": "nearest-strike mean call-put IV", "minimum_observations": 20},
            },
        ])

    calls = [row for row in current if row["option_type"] == "CE" and row.get("delta") is not None]
    puts = [row for row in current if row["option_type"] == "PE" and row.get("delta") is not None]
    if calls and puts:
        call = min(calls, key=lambda row: abs(float(row["delta"]) - 0.25))
        put = min(puts, key=lambda row: abs(float(row["delta"]) + 0.25))
        metrics.append({
            "metric_type": "skew",
            "value": float(put["implied_volatility"]) - float(call["implied_volatility"]),
            "observation_count": 2, "delta_bucket": 0.25,
            "source_ids": [int(put["id"]), int(call["id"])],
            "assumptions": {"definition": "25-delta put IV minus 25-delta call IV"},
        })

    later_rows = rows(
        f"""
        SELECT DISTINCT ON (later.expiry)
               later.id AS batch_id,later.expiry::text,later.spot_price::float8,
               later.source_timestamp::text,later.received_at::text
        FROM trading.option_chain_snapshot_batches later
        WHERE later.provider={sql_literal(batch['provider'])}
          AND later.exchange={sql_literal(batch['exchange'])}
          AND later.underlying={sql_literal(batch['underlying'])}
          AND later.expiry>{sql_literal(str(batch['expiry']))}::date
          AND abs(extract(epoch FROM (
                later.minute_ts-{sql_literal(str(batch['minute_ts']))}::timestamptz
              )))<=60
        ORDER BY later.expiry,
                 abs(extract(epoch FROM (
                    later.minute_ts-{sql_literal(str(batch['minute_ts']))}::timestamptz
                 ))),later.received_at DESC,later.id DESC
        """
    )
    if later_rows:
        later = later_rows[0]
        later_greeks = rows(
            f"""
            SELECT result.id,result.implied_volatility::float8,contract.strike::float8
            FROM trading.option_chain_contract_snapshots contract
            JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
            WHERE contract.batch_id={later['batch_id']}
              AND result.calculation_status='validated'
              AND result.quality_status IN ('passed','warning')
            """
        )
        if later_greeks:
            later_spot = float(later["spot_price"])
            distance = min(abs(float(row["strike"]) - later_spot) for row in later_greeks)
            selected = [row for row in later_greeks if abs(float(row["strike"]) - later_spot) == distance]
            later_iv = sum(float(row["implied_volatility"]) for row in selected) / len(selected)
            information_cutoff = max(
                current_cutoff,
                parse_timestamp(later["source_timestamp"]),
                parse_timestamp(later["received_at"]),
            )
            metrics.append({
                "metric_type": "term_structure", "value": later_iv - atm_iv,
                "observation_count": len(atm_rows) + len(selected),
                "tenor_label": f"{later['expiry']}_minus_{batch['expiry']}",
                "source_ids": atm_ids + [int(row["id"]) for row in selected],
                "valid_from": information_cutoff.isoformat(),
                "assumptions": {
                    "definition": "later-expiry ATM IV minus near-expiry ATM IV",
                    "later_batch_id": later["batch_id"],
                    "no_lookahead": True,
                    "information_cutoff": information_cutoff.isoformat(),
                },
            })

    written = 0
    for metric in metrics:
        source_ids = "ARRAY[" + ",".join(str(value) for value in metric["source_ids"]) + "]::bigint[]"
        changed = write_returning(
            """
            INSERT INTO trading.option_volatility_metrics
                (batch_id,metric_type,tenor_label,delta_bucket,strike_moneyness,lookback_days,
                 metric_value,observation_count,valid_from,calculation_version,source_result_ids,
                 quality_status,quality_flags,assumptions,broker_write_allowed)
            VALUES
            """
            f"({batch['id']},{sql_literal(metric['metric_type'])},{sql_literal(metric.get('tenor_label'))},"
            f"{metric.get('delta_bucket') if metric.get('delta_bucket') is not None else 'NULL'},NULL,"
            f"{metric.get('lookback_days') if metric.get('lookback_days') is not None else 'NULL'},"
            f"{metric['value']},{metric['observation_count']},"
            f"{sql_literal(metric.get('valid_from') or current_cutoff.isoformat())}::timestamptz,{sql_literal(MODEL_VERSION)},"
            f"{source_ids},'passed','{{}}'::text[],{sql_jsonb(metric['assumptions'])},false) RETURNING id"
        )
        written += len(changed)
    return written


def volatility_refresh_batches(touched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return valued batches from every expiry captured in touched source minutes."""
    candidates: dict[int, dict[str, Any]] = {int(batch["id"]): batch for batch in touched}
    scopes: dict[tuple[str, str, str], set[str]] = {}
    for batch in touched:
        key = (str(batch["provider"]), str(batch["exchange"]), str(batch["underlying"]))
        scopes.setdefault(key, set()).add(str(batch["minute_ts"]))
    for (provider, exchange, underlying), minute_values in scopes.items():
        minute_sql = ",".join(f"{sql_literal(value)}::timestamptz" for value in sorted(minute_values))
        for candidate in rows(
            f"""
            SELECT DISTINCT batch.id,batch.batch_key,batch.provider,batch.exchange,batch.underlying,
                   batch.expiry::text,batch.minute_ts::text,batch.source_timestamp::text,
                   batch.received_at::text,batch.spot_price::float8
            FROM trading.option_chain_snapshot_batches batch
            JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=batch.id
            JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
            WHERE batch.provider={sql_literal(provider)} AND batch.exchange={sql_literal(exchange)}
              AND batch.underlying={sql_literal(underlying)}
              AND batch.minute_ts IN ({minute_sql})
              AND result.calculation_status='validated'
              AND result.quality_status IN ('passed','warning')
            """
        ):
            candidates[int(candidate["id"])] = candidate
    return sorted(candidates.values(), key=lambda row: (parse_timestamp(row["minute_ts"]), int(row["id"])))


def record_run(run_key: str, status: str, *, rows_read: int, rows_written: int, batches: int,
               calculations: int, blocked: int, summary: dict[str, Any], error: str | None = None,
               interval_seconds: int = 300) -> None:
    materializer_psql_json(
        """
        INSERT INTO ops.institutional_pipeline_runs
            (run_key,workload_key,status,rows_read,rows_written,batches_created,calculations_completed,
             calculations_blocked,quality_summary,error_message,finished_at,next_run_after,created_by,
             broker_write_allowed)
        VALUES
        """
        f"({sql_literal(run_key)},{sql_literal(WORKLOAD_KEY)},{sql_literal(status)},{rows_read},{rows_written},"
        f"{batches},{calculations},{blocked},{sql_jsonb(summary)},{sql_literal(error) if error else 'NULL'},"
        f"now(),now()+make_interval(secs=>{max(60, interval_seconds)}),'Options Data Quality Agent',false) "
        "ON CONFLICT (run_key) DO NOTHING; SELECT '[]'::json::text"
    )


def repair_batch_analytics(batch_id: int) -> dict[str, Any]:
    """Recalculate one named immutable batch outside the supervised source scan."""
    found = rows(
        f"""
        SELECT id,batch_key,provider,exchange,underlying,expiry::text,minute_ts::text,
               source_timestamp::text,received_at::text,spot_price::float8
        FROM trading.option_chain_snapshot_batches
        WHERE id={int(batch_id)}
        """
    )
    if not found:
        raise ValueError(f"option batch {batch_id} was not found")
    batch = found[0]
    contracts = rows(
        f"""
        SELECT id,instrument_token,trading_symbol,strike::float8,option_type,
               contract_multiplier::float8,quote_source_timestamp::text,received_at::text,
               last_price::float8,bid_price::float8,ask_price::float8,volume::float8,
               open_interest::float8,previous_open_interest::float8,liquidity_flags,
               liquidity_status,staleness_status
        FROM trading.option_chain_contract_snapshots
        WHERE batch_id={int(batch_id)}
        ORDER BY strike,option_type
        """
    )
    if not contracts:
        raise ValueError(f"option batch {batch_id} has no contract snapshots")
    policy = active_policy(batch)
    if policy is None:
        raise ValueError(f"option batch {batch_id} has no active validated valuation policy")
    valuation = create_valuation_input(batch, policy)
    analytics = persist_analytics(batch, valuation, contracts)
    volatility_rows = persist_volatility_metrics(batch)
    replay_rows = rebuild_point_in_time_replay(batch)
    return {
        "status": "completed",
        "batch_id": int(batch_id),
        "analytics_rows": analytics,
        "volatility_metrics_written": volatility_rows,
        "replay_frames_written": replay_rows,
        "source_timestamp": batch["source_timestamp"],
        "paper_only": True,
        "broker_write_allowed": False,
    }


def run(
    limit: int,
    interval_seconds: int = 300,
    *,
    provider: str = DEFAULT_PROVIDER,
    maintenance_backfill: bool = False,
) -> dict[str, Any]:
    run_started = monotonic_time.monotonic()
    DB_CALL_DURATIONS_MS.clear()
    run_key = f"options-materializer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    groups = pending_groups(
        limit,
        provider=provider,
        maintenance_backfill=maintenance_backfill,
    )
    read_count = written = batches = calculations = blocked = 0
    outcomes: list[dict[str, Any]] = []
    touched_scopes: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    valued_batches: dict[int, dict[str, Any]] = {}
    try:
        for group in groups:
            source = source_contracts(group)
            read_count += len(source)
            batch = create_batch(group, source)
            persisted = create_contracts(batch, source)
            batches += 1
            written += len(persisted)
            market_structure = persist_market_structure(batch, persisted)
            premium_rows = persist_source_premium_series(batch, persisted)
            specialist_rows = persist_specialist_observation(batch, persisted)
            non_valuation_rows = sum(market_structure.values()) + premium_rows + specialist_rows
            calculations += non_valuation_rows
            written += non_valuation_rows
            scope_key = (
                str(batch["provider"]), str(batch["exchange"]),
                str(batch["underlying"]), str(batch["expiry"]),
            )
            touched_scopes[scope_key] = batch
            policy = active_policy(batch)
            if policy is None:
                blocked += 1
                outcomes.append({
                    "batch_key": batch["batch_key"],
                    "status": "market_structure_completed_valuation_blocked",
                    "market_structure_rows": market_structure,
                    "premium_rows": premium_rows,
                    "specialist_rows": specialist_rows,
                })
                continue
            valuation = create_valuation_input(batch, policy)
            calculated = persist_analytics(batch, valuation, persisted)
            valued_batches[int(batch["id"])] = batch
            calculations += sum(calculated.values())
            outcomes.append({
                "batch_key": batch["batch_key"], "status": "completed",
                "market_structure_rows": market_structure,
                "premium_rows": premium_rows,
                "specialist_rows": specialist_rows,
                "analytics_rows": calculated,
            })
        refresh_seeds = list(valued_batches.values())
        if not refresh_seeds and not groups:
            refresh_seeds = recent_valued_batches(max(20, limit))
            for batch in refresh_seeds:
                valued_batches[int(batch["id"])] = batch
                scope_key = (
                    str(batch["provider"]), str(batch["exchange"]),
                    str(batch["underlying"]), str(batch["expiry"]),
                )
                touched_scopes[scope_key] = batch
        volatility_rows = 0
        for volatility_batch in volatility_refresh_batches(refresh_seeds):
            volatility_rows += persist_volatility_metrics(volatility_batch)
        calculations += volatility_rows
        written += volatility_rows
        replay_rows = 0
        for replay_batch in touched_scopes.values():
            replay_rows += rebuild_point_in_time_replay(replay_batch)
        calculations += replay_rows
        written += replay_rows
        if not groups and not refresh_seeds:
            status = "blocked"
            error = "no unmaterialized or refreshable valued option snapshots are available"
        elif not groups:
            status = "completed" if calculations else "blocked"
            error = None if calculations else "stored valued snapshots produced no missing analytics"
        else:
            status = "completed" if not blocked else "degraded" if calculations else "blocked"
            error = "validated, source-timed valuation policy required for IV and Greeks" if status == "blocked" else None
        duration_ms = round((monotonic_time.monotonic() - run_started) * 1000.0, 3)
        summary = {
            "groups_seen": len(groups), "outcomes": outcomes,
            "volatility_metrics_written": volatility_rows,
            "replay_frames_written": replay_rows,
            "source_mode": "maintenance_backfill" if maintenance_backfill else "bounded_current_provider",
            "provider": provider,
            "duration_ms": duration_ms,
            "db_calls": len(DB_CALL_DURATIONS_MS),
            "max_db_call_ms": round(max(DB_CALL_DURATIONS_MS, default=0.0), 3),
            "db_call_timeout_seconds": MAX_DB_CALL_SECONDS,
            "paper_only": True, "broker_write_allowed": False,
        }
        record_run(run_key, status, rows_read=read_count, rows_written=written, batches=batches,
                   calculations=calculations, blocked=blocked, summary=summary, error=error,
                   interval_seconds=interval_seconds)
        return {"run_key": run_key, "status": status, "rows_read": read_count, "rows_written": written,
                "batches_created": batches, "calculations_completed": calculations,
                "calculations_blocked": blocked, "replay_frames_written": replay_rows,
                "volatility_metrics_written": volatility_rows,
                "duration_ms": duration_ms,
                "db_calls": len(DB_CALL_DURATIONS_MS),
                "max_db_call_ms": round(max(DB_CALL_DURATIONS_MS, default=0.0), 3),
                "source_mode": summary["source_mode"],
                "outcomes": outcomes,
                "paper_only": True, "broker_write_allowed": False}
    except Exception as exc:
        record_run(run_key, "failed", rows_read=read_count, rows_written=written, batches=batches,
                   calculations=calculations, blocked=blocked, summary={"outcomes": outcomes},
                   error=f"{type(exc).__name__}: {exc}", interval_seconds=interval_seconds)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument(
        "--maintenance-backfill",
        action="store_true",
        help="Process the historical backlog; requires AI_OS_OPTIONS_MAINTENANCE_BACKFILL=1.",
    )
    parser.add_argument(
        "--repair-batch-id",
        type=int,
        help="Recalculate one immutable batch; requires AI_OS_OPTIONS_MAINTENANCE_REPAIR=1.",
    )
    args = parser.parse_args()
    if args.maintenance_backfill and os.environ.get("AI_OS_OPTIONS_MAINTENANCE_BACKFILL") != "1":
        parser.error(
            "--maintenance-backfill is disabled for supervised runs; set "
            "AI_OS_OPTIONS_MAINTENANCE_BACKFILL=1 in an explicit maintenance session"
        )
    if args.repair_batch_id is not None:
        if os.environ.get("AI_OS_OPTIONS_MAINTENANCE_REPAIR") != "1":
            parser.error(
                "--repair-batch-id requires AI_OS_OPTIONS_MAINTENANCE_REPAIR=1 "
                "in an explicit maintenance session"
            )
        print(json.dumps(repair_batch_analytics(args.repair_batch_id), indent=2, default=str))
        return 0
    print(json.dumps(run(
        max(1, args.limit),
        max(60, args.interval_seconds),
        provider=str(args.provider).strip() or DEFAULT_PROVIDER,
        maintenance_backfill=bool(args.maintenance_backfill),
    ), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
