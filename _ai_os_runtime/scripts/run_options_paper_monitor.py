#!/usr/bin/env python3
"""Create an idempotent, source-backed options benchmark in the paper ledger."""

from __future__ import annotations

import argparse
import json
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal


ATTRIBUTION_VERSION = "options_paper_attribution_v1"


def rows(query: str) -> list[dict[str, Any]]:
    return run_psql_json(
        "SELECT coalesce(json_agg(row_to_json(source_rows)), '[]'::json)::text "
        f"FROM ({query}) source_rows"
    )


def write_returning(statement: str) -> list[dict[str, Any]]:
    return run_psql_json(
        "WITH changed AS (" + statement + ") "
        "SELECT coalesce(json_agg(row_to_json(changed)), '[]'::json)::text FROM changed"
    )


def latest_benchmark_legs(exchange: str, underlying: str, expiry: str | None) -> list[dict[str, Any]]:
    expiry_filter = (
        f"AND batch.expiry={sql_literal(expiry)}::date" if expiry else ""
    )
    return rows(
        f"""
        WITH eligible_batch AS (
            SELECT batch.*,observation.id AS observation_id,
                   observation.observation_key,observation.headline,
                   observation.evidence_refs,observation.assumptions AS observation_assumptions
            FROM trading.option_chain_snapshot_batches batch
            JOIN trading.option_specialist_observations observation ON observation.batch_id=batch.id
            WHERE batch.exchange={sql_literal(exchange)}
              AND upper(batch.underlying)={sql_literal(underlying)}
              {expiry_filter}
              AND batch.quality_status IN ('passed','warning')
              AND observation.observation_status='published'
              AND observation.quality_status IN ('passed','warning')
              AND jsonb_array_length(observation.evidence_refs)>0
            ORDER BY batch.minute_ts DESC,batch.id DESC
            LIMIT 1
        ), nearest_strike AS (
            SELECT contract.strike
            FROM eligible_batch batch
            JOIN trading.option_chain_contract_snapshots contract ON contract.batch_id=batch.id
            JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
            WHERE result.calculation_status='validated'
              AND result.quality_status IN ('passed','warning')
              AND contract.liquidity_status='liquid'
              AND contract.staleness_status<>'stale'
            ORDER BY abs(contract.strike-batch.spot_price),contract.strike
            LIMIT 1
        )
        SELECT batch.id AS batch_id,batch.provider,batch.exchange,batch.underlying,
               batch.expiry::text,batch.minute_ts::text,batch.source_timestamp::text,
               batch.spot_price::float8,batch.observation_id,batch.observation_key,
               batch.headline,batch.evidence_refs,batch.observation_assumptions,
               contract.id AS contract_snapshot_id,contract.trading_symbol,
               contract.strike::float8,contract.option_type,contract.last_price::float8,
               contract.bid_price::float8,contract.ask_price::float8,
               contract.open_interest::float8,contract.volume::float8,
               result.id AS source_result_id,result.implied_volatility::float8,
               result.delta::float8,result.gamma::float8,result.theta::float8,
               result.vega::float8
        FROM eligible_batch batch
        JOIN nearest_strike strike ON true
        JOIN trading.option_chain_contract_snapshots contract
          ON contract.batch_id=batch.id AND contract.strike=strike.strike
        JOIN trading.option_iv_greeks_results result ON result.contract_snapshot_id=contract.id
        WHERE contract.option_type IN ('CE','PE')
          AND result.calculation_status='validated'
          AND result.quality_status IN ('passed','warning')
          AND contract.liquidity_status='liquid'
          AND contract.staleness_status<>'stale'
        ORDER BY contract.option_type
        """
    )


def persist_leg(leg: dict[str, Any], actor: str) -> dict[str, Any]:
    source_ref = f"options-paper-monitor:{leg['observation_key']}:{leg['trading_symbol']}"
    entry_signal = {
        "kind": "published_options_observation_benchmark",
        "observation_id": leg["observation_id"],
        "observation_key": leg["observation_key"],
        "headline": leg["headline"],
        "batch_id": leg["batch_id"],
        "contract_snapshot_id": leg["contract_snapshot_id"],
        "source_timestamp": leg["source_timestamp"],
        "spot_price": leg["spot_price"],
        "implied_volatility": leg["implied_volatility"],
        "delta": leg["delta"],
        "gamma": leg["gamma"],
        "theta": leg["theta"],
        "vega": leg["vega"],
        "paper_only": True,
        "broker_write_allowed": False,
    }
    evidence = [
        {"table": "trading.option_specialist_observations", "id": leg["observation_id"]},
        {"table": "trading.option_chain_snapshot_batches", "id": leg["batch_id"]},
        {"table": "trading.option_chain_contract_snapshots", "id": leg["contract_snapshot_id"]},
        {"table": "trading.option_iv_greeks_results", "id": leg["source_result_id"]},
    ]
    payload = {
        "entry_batch_id": leg["batch_id"],
        "contract_snapshot_id": leg["contract_snapshot_id"],
        "observation_key": leg["observation_key"],
        "benchmark": "long_atm_straddle",
        "paper_only": True,
        "capital_action_allowed": False,
        "broker_write_allowed": False,
    }
    changed = write_returning(
        """
        INSERT INTO trading.trade_activity_ledger
            (activity_type,execution_mode,source_kind,source_ref,strategy_key,symbol,
             exchange,instrument_type,side,quantity,price,trade_ts,status,thesis,
             setup_type,timeframe,tags,evidence,payload,created_by)
        SELECT
        """
        f"'trade','paper','options_paper_monitor',{sql_literal(source_ref)},"
        f"{sql_literal('options_atm_straddle_benchmark')},{sql_literal(leg['trading_symbol'])},"
        f"{sql_literal(leg['exchange'])},'option','BUY',1,{float(leg['last_price'])},"
        f"{sql_literal(leg['source_timestamp'])}::timestamptz,'open',"
        f"{sql_literal('Monitor the published options observation as a one-unit ATM straddle benchmark; no capital or broker order is authorized.')},"
        f"'atm_straddle_benchmark','intraday',ARRAY['paper_only','options_monitor','source_backed']::text[],"
        f"{sql_jsonb(evidence)},{sql_jsonb(payload)},{sql_literal(actor)} "
        f"WHERE NOT EXISTS (SELECT 1 FROM trading.trade_activity_ledger WHERE execution_mode='paper' "
        f"AND source_kind='options_paper_monitor' AND source_ref={sql_literal(source_ref)}) "
        "RETURNING *"
    )
    trade = changed[0] if changed else rows(
        f"""
        SELECT * FROM trading.trade_activity_ledger
        WHERE execution_mode='paper' AND source_kind='options_paper_monitor'
          AND source_ref={sql_literal(source_ref)}
        ORDER BY id DESC LIMIT 1
        """
    )[0]
    source_ids = f"ARRAY[{int(leg['source_result_id'])}]::bigint[]"
    attribution = write_returning(
        """
        INSERT INTO trading.option_paper_trade_attributions
            (trade_activity_id,entry_batch_id,strategy_key,attribution_version,
             entry_signal,pnl_total,pnl_delta,pnl_gamma,pnl_vega,pnl_theta,
             pnl_residual,fees_and_slippage,source_result_ids,quality_status,
             quality_flags,assumptions,paper_only,broker_write_allowed)
        VALUES
        """
        f"({int(trade['id'])},{int(leg['batch_id'])},'options_atm_straddle_benchmark',"
        f"{sql_literal(ATTRIBUTION_VERSION)},{sql_jsonb(entry_signal)},0,0,0,0,0,0,0,"
        f"{source_ids},'passed','{{}}'::text[],"
        f"{sql_jsonb({'stage': 'entry_mark', 'position_size': 'one paper unit per leg', 'pnl_components_initialized_at_zero': True, 'exit_attribution_required': True})},true,false) "
        "ON CONFLICT (trade_activity_id,attribution_version) DO UPDATE SET "
        "entry_batch_id=EXCLUDED.entry_batch_id,entry_signal=EXCLUDED.entry_signal,"
        "source_result_ids=EXCLUDED.source_result_ids,quality_status=EXCLUDED.quality_status,"
        "assumptions=EXCLUDED.assumptions,updated_at=now() RETURNING *"
    )
    return {
        "trade_activity_id": trade["id"],
        "attribution_id": attribution[0]["id"],
        "symbol": leg["trading_symbol"],
        "option_type": leg["option_type"],
        "entry_batch_id": leg["batch_id"],
        "paper_only": True,
        "broker_write_allowed": False,
    }


def run(exchange: str, underlying: str, expiry: str | None, actor: str) -> dict[str, Any]:
    legs = latest_benchmark_legs(exchange, underlying, expiry)
    option_types = {str(leg["option_type"]) for leg in legs}
    if option_types != {"CE", "PE"}:
        return {
            "status": "blocked",
            "reason": "a liquid validated ATM call-put pair with published evidence is required",
            "underlying": underlying,
            "expiry": expiry,
            "paper_only": True,
            "broker_write_allowed": False,
        }
    persisted = [persist_leg(leg, actor) for leg in legs]
    return {
        "status": "completed",
        "strategy_key": "options_atm_straddle_benchmark",
        "underlying": underlying,
        "expiry": legs[0]["expiry"],
        "entry_batch_id": legs[0]["batch_id"],
        "legs": persisted,
        "paper_only": True,
        "capital_action_allowed": False,
        "broker_write_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", default="NFO")
    parser.add_argument("--underlying", required=True)
    parser.add_argument("--expiry")
    parser.add_argument("--actor", default="Options Analyst")
    args = parser.parse_args()
    result = run(args.exchange.strip().upper(), args.underlying.strip().upper(), args.expiry, args.actor)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
