#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from run_strategy_backtest import (
    Bar,
    infer_template,
    normalize_timeframe,
    positions_for_template,
    run_psql_json,
    sql_jsonb,
    sql_literal,
)


def fetch_running_monitors(limit: int) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT monitor.id AS paper_monitor_session_id, monitor.session_key,
                   monitor.strategy_id, monitor.instance_id, monitor.status,
                   monitor.live_execution_allowed, candidate.candidate_key,
                   candidate.name, candidate.hypothesis, candidate.universe,
                   candidate.timeframe, candidate.entry_rules, candidate.exit_rules,
                   candidate.risk_rules, candidate.structured_spec,
                   coalesce(spec.symbols, ARRAY[]::text[]) AS symbols,
                   coalesce(spec.timeframe, candidate.timeframe) AS spec_timeframe,
                   spec.template, spec.parse_status
            FROM strategy.paper_monitor_sessions monitor
            JOIN strategy.strategy_candidates candidate ON candidate.id = monitor.strategy_id
            LEFT JOIN LATERAL (
                SELECT symbols, timeframe, template, parse_status
                FROM strategy.strategy_rule_specs
                WHERE candidate_id = candidate.id
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
            ) spec ON true
            WHERE monitor.status = 'running'
              AND monitor.monitor_mode = 'paper'
              AND monitor.live_execution_allowed = false
            ORDER BY monitor.last_heartbeat_at NULLS FIRST, monitor.id
            LIMIT {max(1, min(100, int(limit)))}
        ) rows
        """
    )


def fetch_recent_bars(symbols: list[str], timeframe: str, bars_per_symbol: int) -> list[Bar]:
    cleaned = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    if not cleaned:
        return []
    variants = sorted(set(cleaned + [f"NSE:{symbol}" for symbol in cleaned if ":" not in symbol]))
    return [
        Bar(ts=str(row["ts"]), symbol=str(row["symbol"]), close=float(row["close"]))
        for row in run_psql_json(
            f"""
            WITH ranked AS (
                SELECT o.ts, symbol.id AS symbol_id, symbol.symbol, o.close,
                       row_number() OVER (PARTITION BY symbol.id ORDER BY o.ts DESC) AS row_rank
                FROM trading.ohlcv o
                JOIN trading.symbols symbol ON symbol.id = o.symbol_id
                WHERE o.timeframe = {sql_literal(timeframe)}
                  AND o.close IS NOT NULL
                  AND upper(symbol.symbol) = ANY(ARRAY[{','.join(sql_literal(value) for value in variants)}]::text[])
            )
            SELECT coalesce(json_agg(row_to_json(rows) ORDER BY rows.symbol, rows.ts), '[]'::json)::text
            FROM (
                SELECT ts::text AS ts, symbol, close::float8 AS close
                FROM ranked
                WHERE row_rank <= {max(20, min(1000, int(bars_per_symbol)))}
            ) rows
            """
        )
    ]


def evaluate_symbol(bars: list[Bar], template: str) -> dict[str, Any]:
    if len(bars) < 20:
        return {"status": "insufficient_bars", "bars": len(bars)}
    closes = [bar.close for bar in bars]
    positions = positions_for_template(closes, template)
    previous_position = int(positions[-2])
    desired_position = int(positions[-1])
    action = "hold"
    if previous_position == 0 and desired_position == 1:
        action = "buy"
    elif previous_position == 1 and desired_position == 0:
        action = "exit"
    return {
        "status": "evaluated",
        "bars": len(bars),
        "bar_ts": bars[-1].ts,
        "price": bars[-1].close,
        "previous_position": previous_position,
        "desired_position": desired_position,
        "action": action,
    }


def persist_evaluation(monitor: dict[str, Any], symbol: str, timeframe: str, template: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    session_id = int(monitor["paper_monitor_session_id"])
    strategy_id = int(monitor["strategy_id"])
    instance_id = int(monitor["instance_id"])
    exchange = "NSE"
    canonical_symbol = symbol.split(":", 1)[-1].upper()
    raw_action = str(evaluation["action"])
    state_rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT count(*) FILTER (WHERE state = 'open')::int AS open_positions,
                   (SELECT max(payload->>'bar_ts') FROM strategy.paper_monitor_events
                    WHERE session_id = {session_id} AND event_type = 'evaluation'
                      AND symbol = {sql_literal(canonical_symbol)}) AS latest_evaluated_bar_ts
            FROM trading.paper_positions
            WHERE paper_monitor_session_id = {session_id}
              AND symbol = {sql_literal(canonical_symbol)}
              AND exchange = {sql_literal(exchange)}
        ) rows
        """
    )
    state = state_rows[0] if state_rows else {}
    open_positions = int(state.get("open_positions") or 0)
    if int(evaluation["desired_position"]) == 1 and open_positions == 0:
        action = "buy"
    elif int(evaluation["desired_position"]) == 0 and open_positions > 0:
        action = "exit"
    else:
        action = "hold"
    bar_ts = str(evaluation["bar_ts"])
    price = float(evaluation["price"])
    source_ref = f"paper-monitor:{session_id}:{canonical_symbol}:{timeframe}:{bar_ts}:{action}"
    payload = {
        "paper_monitor_session_id": session_id,
        "strategy_id": strategy_id,
        "instance_id": instance_id,
        "template": template,
        "timeframe": timeframe,
        "bar_ts": bar_ts,
        "desired_position": evaluation["desired_position"],
        "previous_position": evaluation["previous_position"],
        "deterministic": True,
        "live_execution_allowed": False,
    }
    rows = run_psql_json(
        f"""
        WITH existing_event AS (
            SELECT id
            FROM strategy.paper_monitor_events
            WHERE session_id = {session_id}
              AND event_type = 'evaluation'
              AND symbol = {sql_literal(canonical_symbol)}
              AND timeframe = {sql_literal(timeframe)}
              AND payload->>'bar_ts' = {sql_literal(bar_ts)}
            LIMIT 1
        ), signal AS (
            INSERT INTO trading.signals (
                ts, strategy, symbol, exchange, action, price, quantity,
                confidence, payload, status
            )
            SELECT {sql_literal(bar_ts)}::timestamptz,
                   {sql_literal(monitor.get('candidate_key') or str(strategy_id))},
                   {sql_literal(canonical_symbol)}, {sql_literal(exchange)},
                   {sql_literal(action.upper())}, {price}, 1, 1,
                   {sql_jsonb(payload)}, 'paper_observed'
            WHERE {sql_literal(action)} IN ('buy', 'exit')
              AND NOT EXISTS (SELECT 1 FROM existing_event)
            RETURNING id
        ), open_position AS (
            INSERT INTO trading.paper_positions (
                paper_monitor_session_id, strategy_id, instance_id, symbol,
                exchange, timeframe, side, quantity, state, entry_signal_id,
                entry_ts, entry_price, latest_mark_ts, latest_mark_price,
                unrealized_pnl, metadata
            )
            SELECT {session_id}, {strategy_id}, {instance_id},
                   {sql_literal(canonical_symbol)}, {sql_literal(exchange)},
                   {sql_literal(timeframe)}, 'long', 1, 'open',
                   (SELECT id FROM signal), {sql_literal(bar_ts)}::timestamptz,
                   {price}, {sql_literal(bar_ts)}::timestamptz, {price}, 0,
                   {sql_jsonb(payload)}
            WHERE {sql_literal(action)} = 'buy'
              AND NOT EXISTS (SELECT 1 FROM existing_event)
              AND NOT EXISTS (
                  SELECT 1 FROM trading.paper_positions
                  WHERE paper_monitor_session_id = {session_id}
                    AND symbol = {sql_literal(canonical_symbol)}
                    AND exchange = {sql_literal(exchange)}
                    AND state = 'open'
              )
            RETURNING id
        ), marked_position AS (
            UPDATE trading.paper_positions
            SET latest_mark_ts = {sql_literal(bar_ts)}::timestamptz,
                latest_mark_price = {price},
                unrealized_pnl = CASE side
                    WHEN 'long' THEN ({price} - entry_price) * quantity - fees
                    ELSE (entry_price - {price}) * quantity - fees
                END,
                metadata = metadata || {sql_jsonb({'last_evaluation': payload})},
                updated_at = now()
            WHERE paper_monitor_session_id = {session_id}
              AND symbol = {sql_literal(canonical_symbol)}
              AND exchange = {sql_literal(exchange)}
              AND state = 'open'
            RETURNING id
        ), closed_position AS (
            UPDATE trading.paper_positions
            SET state = 'closed', exit_signal_id = (SELECT id FROM signal),
                exit_ts = {sql_literal(bar_ts)}::timestamptz,
                exit_price = {price}, latest_mark_ts = {sql_literal(bar_ts)}::timestamptz,
                latest_mark_price = {price}, unrealized_pnl = 0,
                realized_pnl = CASE side
                    WHEN 'long' THEN ({price} - entry_price) * quantity - fees
                    ELSE (entry_price - {price}) * quantity - fees
                END,
                close_reason = 'strategy_exit_signal',
                metadata = metadata || {sql_jsonb({'exit_evaluation': payload})},
                updated_at = now()
            WHERE {sql_literal(action)} = 'exit'
              AND NOT EXISTS (SELECT 1 FROM existing_event)
              AND paper_monitor_session_id = {session_id}
              AND symbol = {sql_literal(canonical_symbol)}
              AND exchange = {sql_literal(exchange)}
              AND state = 'open'
            RETURNING id, realized_pnl
        ), trade_row AS (
            INSERT INTO trading.trade_activity_ledger (
                activity_type, execution_mode, source_kind, source_ref,
                strategy_key, symbol, exchange, instrument_type, side,
                quantity, price, trade_ts, status, thesis, setup_type,
                timeframe, realized_pnl, source_signal_id, tags, evidence,
                payload, created_by
            )
            SELECT 'trade', 'paper', 'paper_monitor', {sql_literal(source_ref)},
                   {sql_literal(monitor.get('candidate_key') or str(strategy_id))},
                   {sql_literal(canonical_symbol)}, {sql_literal(exchange)}, 'equity',
                   CASE {sql_literal(action)} WHEN 'buy' THEN 'BUY' ELSE 'SELL' END,
                   1, {price}, {sql_literal(bar_ts)}::timestamptz,
                   CASE {sql_literal(action)} WHEN 'buy' THEN 'open' ELSE 'closed' END,
                   {sql_literal(monitor.get('hypothesis'))}, {sql_literal(template)},
                   {sql_literal(timeframe)},
                   (SELECT realized_pnl FROM closed_position LIMIT 1),
                   (SELECT id FROM signal), ARRAY['paper_monitor','deterministic']::text[],
                   jsonb_build_array(jsonb_build_object('paper_monitor_session_id', {session_id})),
                   {sql_jsonb(payload)}, 'Paper Monitor Worker'
            WHERE {sql_literal(action)} IN ('buy', 'exit')
              AND NOT EXISTS (SELECT 1 FROM existing_event)
              AND (({sql_literal(action)} = 'buy' AND EXISTS (SELECT 1 FROM open_position))
                   OR ({sql_literal(action)} = 'exit' AND EXISTS (SELECT 1 FROM closed_position)))
            RETURNING id
        ), monitor_event AS (
            INSERT INTO strategy.paper_monitor_events (
                session_id, event_type, event_status, symbol, timeframe,
                signal_count, metrics, payload, created_by
            )
            SELECT {session_id}, 'evaluation', 'recorded',
                   {sql_literal(canonical_symbol)}, {sql_literal(timeframe)},
                   (SELECT count(*) FROM signal)::int,
                   jsonb_build_object(
                       'price', {price}, 'action', {sql_literal(action)},
                       'desired_position', {int(evaluation['desired_position'])},
                       'position_opened', EXISTS (SELECT 1 FROM open_position),
                       'position_closed', EXISTS (SELECT 1 FROM closed_position)
                   ),
                   {sql_jsonb(payload)}, 'Paper Monitor Worker'
            WHERE NOT EXISTS (SELECT 1 FROM existing_event)
            RETURNING id
        )
        SELECT json_build_array(json_build_object(
            'paper_monitor_session_id', {session_id},
            'symbol', {sql_literal(canonical_symbol)},
            'action', {sql_literal(action)},
            'bar_ts', {sql_literal(bar_ts)},
            'signal_id', (SELECT id FROM signal),
            'position_opened_id', (SELECT id FROM open_position),
            'position_closed_id', (SELECT id FROM closed_position),
            'trade_activity_id', (SELECT id FROM trade_row),
            'event_id', (SELECT id FROM monitor_event),
            'duplicate', EXISTS (SELECT 1 FROM existing_event),
            'live_execution_allowed', false
        ))::text
        """
    )
    result = rows[0] if rows else {"paper_monitor_session_id": session_id, "symbol": canonical_symbol, "status": "no_result"}
    performance_rows = run_psql_json(
        f"""
        WITH performance AS (
            SELECT count(*) FILTER (WHERE state = 'open')::int AS positions_open,
                   count(*) FILTER (WHERE state = 'closed')::int AS positions_closed,
                   coalesce(sum(unrealized_pnl) FILTER (WHERE state = 'open'), 0) AS unrealized_pnl,
                   coalesce(sum(realized_pnl) FILTER (WHERE state = 'closed'), 0) AS realized_pnl
            FROM trading.paper_positions
            WHERE paper_monitor_session_id = {session_id}
        ), updated AS (
            UPDATE strategy.paper_monitor_sessions
            SET last_heartbeat_at = now(), heartbeat_status = 'ok',
                metrics = metrics || jsonb_build_object(
                    'positions_open', performance.positions_open,
                    'positions_closed', performance.positions_closed,
                    'unrealized_pnl', performance.unrealized_pnl,
                    'realized_pnl', performance.realized_pnl,
                    'last_evaluated_bar_ts', {sql_literal(bar_ts)},
                    'live_execution_allowed', false
                ), updated_at = now()
            FROM performance
            WHERE id = {session_id}
            RETURNING metrics
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )
    if performance_rows:
        result["performance"] = performance_rows[0].get("metrics") or {}
    result["raw_action"] = raw_action
    return result


def evaluate_monitor(monitor: dict[str, Any], bars_per_symbol: int) -> dict[str, Any]:
    if monitor.get("live_execution_allowed") is not False:
        raise RuntimeError(f"paper monitor {monitor['paper_monitor_session_id']} is not paper-only")
    symbols = [str(value) for value in (monitor.get("symbols") or []) if str(value).strip()]
    if not symbols:
        return {"paper_monitor_session_id": monitor["paper_monitor_session_id"], "status": "blocked_missing_symbols", "results": []}
    timeframe = normalize_timeframe(str(monitor.get("spec_timeframe") or monitor.get("timeframe") or ""))
    template = infer_template(monitor, str(monitor.get("template") or "") or None)
    grouped: dict[str, list[Bar]] = defaultdict(list)
    for bar in fetch_recent_bars(symbols, timeframe, bars_per_symbol):
        grouped[bar.symbol].append(bar)
    results = []
    for symbol in symbols:
        variants = [symbol, symbol.split(":", 1)[-1], f"NSE:{symbol.split(':', 1)[-1]}"]
        symbol_bars = next((grouped[value] for value in variants if grouped.get(value)), [])
        evaluation = evaluate_symbol(symbol_bars, template)
        if evaluation["status"] != "evaluated":
            results.append({"symbol": symbol, **evaluation})
            continue
        results.append(persist_evaluation(monitor, symbol, timeframe, template, evaluation))
    return {
        "paper_monitor_session_id": monitor["paper_monitor_session_id"],
        "strategy_id": monitor["strategy_id"],
        "template": template,
        "timeframe": timeframe,
        "status": "evaluated",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate approved paper monitors from canonical stored OHLCV.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--bars-per-symbol", type=int, default=120)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    monitors = fetch_running_monitors(args.limit)
    results = []
    for monitor in monitors:
        try:
            results.append(evaluate_monitor(monitor, args.bars_per_symbol))
        except Exception as exc:  # noqa: BLE001
            results.append({
                "paper_monitor_session_id": monitor.get("paper_monitor_session_id"),
                "status": "failed",
                "error": type(exc).__name__ + ": " + str(exc),
            })
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "monitors_seen": len(monitors),
        "evaluated": sum(1 for result in results if result.get("status") == "evaluated"),
        "failed": sum(1 for result in results if result.get("status") == "failed"),
        "results": results,
        "data_source": "trading.ohlcv",
        "deterministic": True,
        "live_execution_allowed": False,
    }
    print(json.dumps(output, indent=2 if args.json else None, sort_keys=True, default=str))
    return 1 if output["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
