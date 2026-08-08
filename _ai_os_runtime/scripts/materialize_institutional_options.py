#!/usr/bin/env python3
"""Materialize source option snapshots into the institutional analytics store.

The workload is idempotent, point-in-time, and analytics-only. It never creates
valuation inputs unless a validated, unexpired, source-evidenced policy exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, time, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from run_institutional_options_engine import MODEL_VERSION, SOLVER_VERSION, analyze_chain
from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal


WORKLOAD_KEY = "institutional_options_materializer"


def rows(query: str) -> list[dict[str, Any]]:
    result = run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(source_rows)), '[]'::json)::text "
        f"FROM ({query}) source_rows"
    )
    return result if isinstance(result, list) else []


def write_returning(statement: str) -> list[dict[str, Any]]:
    return run_psql_json(
        "WITH changed AS (" + statement + ") "
        "SELECT coalesce(json_agg(row_to_json(changed)), '[]'::json)::text FROM changed"
    )


def text_array(values: list[str]) -> str:
    return "ARRAY[" + ",".join(sql_literal(value) for value in values) + "]::text[]"


def parse_timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def pending_groups(limit: int) -> list[dict[str, Any]]:
    return rows(
        f"""
        SELECT legacy.provider, legacy.source_connector_key, legacy.exchange,
               legacy.underlying, legacy.expiry::text, date_trunc('minute', legacy.observed_at)::text AS minute_ts,
               max(legacy.observed_at)::text AS source_timestamp,
               max(greatest(legacy.created_at, legacy.observed_at))::text AS received_at,
               count(*)::int AS contract_count,
               max(legacy.spot_price)::float8 AS spot_price
        FROM trading.option_chain_snapshots legacy
        WHERE NOT EXISTS (
            SELECT 1 FROM trading.option_chain_snapshot_batches batch
            WHERE batch.provider=legacy.provider AND batch.exchange=legacy.exchange
              AND batch.underlying=legacy.underlying AND batch.expiry=legacy.expiry
              AND batch.minute_ts=date_trunc('minute', legacy.observed_at)
        )
        GROUP BY legacy.provider, legacy.source_connector_key, legacy.exchange,
                 legacy.underlying, legacy.expiry, date_trunc('minute', legacy.observed_at)
        ORDER BY date_trunc('minute', legacy.observed_at)
        LIMIT {max(1, int(limit))}
        """
    )


def source_contracts(group: dict[str, Any]) -> list[dict[str, Any]]:
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
        WHERE legacy.provider={sql_literal(group['provider'])}
          AND legacy.exchange={sql_literal(group['exchange'])}
          AND legacy.underlying={sql_literal(group['underlying'])}
          AND legacy.expiry={sql_literal(group['expiry'])}::date
          AND date_trunc('minute', legacy.observed_at)={sql_literal(group['minute_ts'])}::timestamptz
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
        "ON CONFLICT (batch_key) DO UPDATE SET lineage=EXCLUDED.lineage RETURNING *"
    )
    if not changed:
        raise RuntimeError("batch upsert returned no row")
    return changed[0]


def create_contracts(batch: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    persisted: list[dict[str, Any]] = []
    for contract in contracts:
        quality = quality_for_contract(contract)
        previous = rows(
            f"""
            SELECT prior.open_interest::float8 AS open_interest
            FROM trading.option_chain_contract_snapshots prior
            JOIN trading.option_chain_snapshot_batches batch ON batch.id=prior.batch_id
            WHERE batch.provider={sql_literal(batch['provider'])}
              AND batch.exchange={sql_literal(batch['exchange'])}
              AND batch.underlying={sql_literal(batch['underlying'])}
              AND batch.expiry={sql_literal(str(batch['expiry']))}::date
              AND prior.strike={contract['strike']} AND prior.option_type={sql_literal(contract['option_type'])}
              AND batch.minute_ts < {sql_literal(str(batch['minute_ts']))}::timestamptz
            ORDER BY batch.minute_ts DESC LIMIT 1
            """
        )
        prior_oi = previous[0].get("open_interest") if previous else None
        source_fields = {
            "legacy_snapshot_id": contract["legacy_snapshot_id"],
            "source_payload": contract.get("source_payload") or {},
        }
        changed = write_returning(
            """
            INSERT INTO trading.option_chain_contract_snapshots
                (batch_id,instrument_token,trading_symbol,strike,option_type,contract_multiplier,
                 quote_source_timestamp,received_at,last_price,bid_price,ask_price,volume,open_interest,
                 previous_open_interest,source_age_seconds,spread_absolute,spread_bps,liquidity_score,
                 staleness_status,liquidity_status,liquidity_flags,source_fields,source_payload_hash,
                 broker_write_allowed)
            VALUES
            """
            f"({batch['id']},{sql_literal(contract.get('instrument_token'))},{sql_literal(contract['trading_symbol'])},"
            f"{contract['strike']},{sql_literal(contract['option_type'])},{contract['contract_multiplier']},"
            f"{sql_literal(contract['quote_source_timestamp'])}::timestamptz,{sql_literal(contract['received_at'])}::timestamptz,"
            f"{contract.get('last_price') if contract.get('last_price') is not None else 'NULL'},"
            f"{contract.get('bid_price') if contract.get('bid_price') is not None else 'NULL'},"
            f"{contract.get('ask_price') if contract.get('ask_price') is not None else 'NULL'},"
            f"{contract.get('volume') if contract.get('volume') is not None else 'NULL'},"
            f"{contract.get('open_interest') if contract.get('open_interest') is not None else 'NULL'},"
            f"{prior_oi if prior_oi is not None else 'NULL'},{quality['source_age_seconds']},"
            f"{quality['spread_absolute'] if quality['spread_absolute'] is not None else 'NULL'},"
            f"{quality['spread_bps'] if quality['spread_bps'] is not None else 'NULL'},"
            f"{quality['liquidity_score']},{sql_literal(quality['staleness_status'])},"
            f"{sql_literal(quality['liquidity_status'])},{text_array(quality['liquidity_flags'])},"
            f"{sql_jsonb(source_fields)},{sql_literal(contract['source_payload_hash'])},false) "
            "ON CONFLICT (batch_id,strike,option_type) DO UPDATE SET source_fields=EXCLUDED.source_fields RETURNING *"
        )
        persisted.extend(changed)
    return persisted


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


def create_valuation_input(batch: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    valuation_ts = parse_timestamp(batch["source_timestamp"])
    expiry_ts = expiry_timestamp(batch, policy)
    if valuation_ts >= expiry_ts:
        raise ValueError("batch source timestamp is at or after option expiry")
    year_fraction = (expiry_ts - valuation_ts).total_seconds() / (365.0 * 86400.0)
    input_key = f"policy:{policy['policy_key']}"
    assumptions = {
        "policy_id": policy["id"],
        "source_artifact_ref": policy["source_artifact_ref"],
        "expiry_timezone": policy["expiry_timezone"],
        "no_default_inputs": True,
    }
    input_hash = canonical_hash({
        "batch_id": batch["id"], "policy_id": policy["id"], "spot": batch["spot_price"],
        "rate": policy["risk_free_rate"], "dividend": policy["dividend_yield"],
        "valuation_ts": valuation_ts.isoformat(), "expiry_ts": expiry_ts.isoformat(),
    })
    changed = write_returning(
        """
        INSERT INTO trading.option_valuation_inputs
            (batch_id,input_key,model_family,valuation_timestamp,spot_price,risk_free_rate,dividend_yield,
             time_to_expiry_years,day_count_convention,expiry_timestamp,spot_source_timestamp,
             rate_source_timestamp,dividend_source_timestamp,forward_method,rate_source,dividend_source,
             input_quality_status,quality_flags,assumptions,input_hash,broker_write_allowed)
        VALUES
        """
        f"({batch['id']},{sql_literal(input_key)},{sql_literal(policy['model_family'])},"
        f"{sql_literal(valuation_ts.isoformat())}::timestamptz,{batch['spot_price']},{policy['risk_free_rate']},"
        f"{policy['dividend_yield']},{year_fraction},{sql_literal(policy['day_count_convention'])},"
        f"{sql_literal(expiry_ts.isoformat())}::timestamptz,{sql_literal(str(batch['source_timestamp']))}::timestamptz,"
        f"{sql_literal(str(policy['rate_source_timestamp']))}::timestamptz,"
        f"{sql_literal(str(policy['dividend_source_timestamp']))}::timestamptz,'spot_carry',"
        f"{sql_literal(policy['rate_source'])},{sql_literal(policy['dividend_source'])},'passed','{{}}'::text[],"
        f"{sql_jsonb(assumptions)},{sql_literal(input_hash)},false) "
        "ON CONFLICT (batch_id,input_key) DO UPDATE SET input_hash=EXCLUDED.input_hash RETURNING *"
    )
    return changed[0]


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
        "as_of": str(batch["received_at"]), "dry_run": True,
        "valuation": {
            "model": valuation["model_family"], "valuation_timestamp": str(valuation["valuation_timestamp"]),
            "spot_price": float(valuation["spot_price"]),
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
              "DO UPDATE SET calculation_hash=EXCLUDED.calculation_hash RETURNING id"
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

    run_psql_json(
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
            f"{sql_jsonb(assumptions)},{sql_literal(quality)},'{{}}'::text[],false) RETURNING id"
        )
        exposure_ids.extend(int(row["id"]) for row in changed)
    return {
        "greeks": len(greek_ids),
        "premium_series": len(premium_ids),
        "expected_moves": len(expected_ids),
        "exposures": len(exposure_ids),
    }


def record_run(run_key: str, status: str, *, rows_read: int, rows_written: int, batches: int,
               calculations: int, blocked: int, summary: dict[str, Any], error: str | None = None,
               interval_seconds: int = 300) -> None:
    run_psql_json(
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


def run(limit: int, interval_seconds: int = 300) -> dict[str, Any]:
    run_key = f"options-materializer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    groups = pending_groups(limit)
    read_count = written = batches = calculations = blocked = 0
    outcomes: list[dict[str, Any]] = []
    try:
        for group in groups:
            source = source_contracts(group)
            read_count += len(source)
            batch = create_batch(group, source)
            persisted = create_contracts(batch, source)
            batches += 1
            written += len(persisted)
            policy = active_policy(batch)
            if policy is None:
                blocked += 1
                outcomes.append({"batch_key": batch["batch_key"], "status": "blocked_missing_valuation_policy"})
                continue
            valuation = create_valuation_input(batch, policy)
            calculated = persist_analytics(batch, valuation, persisted)
            calculations += sum(calculated.values())
            outcomes.append({"batch_key": batch["batch_key"], "status": "completed", "analytics_rows": calculated})
        if not groups:
            status = "blocked"
            error = "no unmaterialized source option snapshots are available"
        else:
            status = "completed" if not blocked else "degraded" if calculations else "blocked"
            error = "validated, unexpired valuation policy required" if status == "blocked" else None
        summary = {"groups_seen": len(groups), "outcomes": outcomes, "paper_only": True, "broker_write_allowed": False}
        record_run(run_key, status, rows_read=read_count, rows_written=written, batches=batches,
                   calculations=calculations, blocked=blocked, summary=summary, error=error,
                   interval_seconds=interval_seconds)
        return {"run_key": run_key, "status": status, "rows_read": read_count, "rows_written": written,
                "batches_created": batches, "calculations_completed": calculations,
                "calculations_blocked": blocked, "outcomes": outcomes,
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
    args = parser.parse_args()
    print(json.dumps(run(max(1, args.limit), max(60, args.interval_seconds)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
