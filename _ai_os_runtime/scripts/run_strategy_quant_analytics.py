#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_storage import artifact_reference, artifact_root

from run_strategy_backtest import (
    Bar,
    fetch_bars,
    infer_template,
    max_drawdown,
    normalize_timeframe,
    positions_for_template,
    run_psql_json,
    sql_jsonb,
    sql_literal,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = artifact_root("quant_analytics")


@dataclass
class StrategySeries:
    strategy_id: int
    candidate_key: str
    name: str
    template: str
    timeframe: str
    symbols: list[str]
    returns_by_ts: dict[str, float]
    diagnostics: dict[str, Any]


def sql_text_array(values: object) -> str:
    if values is None:
        return "ARRAY[]::text[]"
    if isinstance(values, str):
        items = [item.strip() for item in values.split(",") if item.strip()]
    elif isinstance(values, list):
        items = [str(item).strip() for item in values if str(item).strip()]
    else:
        items = []
    if not items:
        return "ARRAY[]::text[]"
    return "ARRAY[" + ",".join(sql_literal(item) for item in items) + "]::text[]"


def psql_exec(sql: str) -> str:
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
    return completed.stdout.strip()


def fetch_candidates(strategy_ids: list[int], limit: int) -> list[dict[str, Any]]:
    if strategy_ids:
        where = "WHERE candidate.id = ANY(ARRAY[" + ",".join(str(int(item)) for item in strategy_ids) + "]::BIGINT[])"
    else:
        where = """
        WHERE candidate.status IN ('imported','idea','research','candidate')
           OR EXISTS (
                SELECT 1
                FROM strategy.backtest_runs run
                WHERE run.strategy_id = candidate.id
                  AND run.run_status IN ('completed','imported')
           )
        """
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT candidate.id,
                   coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
                   candidate.name,
                   candidate.hypothesis,
                   candidate.universe,
                   candidate.timeframe,
                   candidate.entry_rules,
                   candidate.exit_rules,
                   candidate.risk_rules,
                   candidate.structured_spec,
                   spec.symbols AS parsed_symbols,
                   spec.timeframe AS parsed_timeframe,
                   spec.template AS parsed_template,
                   spec.parse_status,
                   gate.status AS latest_gate_status,
                   gate.total_rows AS latest_gate_rows
            FROM strategy.strategy_candidates candidate
            LEFT JOIN LATERAL (
                SELECT symbols, timeframe, template, parse_status
                FROM strategy.strategy_rule_specs
                WHERE candidate_id = candidate.id
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
            ) spec ON true
            LEFT JOIN LATERAL (
                SELECT status, total_rows
                FROM strategy.backtest_data_quality_gates
                WHERE candidate_id = candidate.id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            ) gate ON true
            {where}
            ORDER BY
                CASE WHEN spec.parse_status = 'passed' THEN 1 ELSE 2 END,
                candidate.updated_at DESC,
                candidate.id DESC
            LIMIT {max(1, int(limit))}
        ) rows
        """
    )
    return rows


def symbol_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    return []


def returns_for_symbol(bars: list[Bar], template: str, total_cost: float) -> dict[str, float]:
    closes = [bar.close for bar in bars]
    if len(closes) < 20:
        return {}
    positions = positions_for_template(closes, template)
    output: dict[str, float] = {}
    for index in range(1, len(closes)):
        raw_return = closes[index] / closes[index - 1] - 1.0
        turnover = abs(positions[index] - positions[index - 1])
        output[bars[index].ts] = positions[index - 1] * raw_return - turnover * total_cost
    return output


def build_strategy_series(candidate: dict[str, Any], timeframe: str, max_symbols: int, total_cost: float) -> StrategySeries | None:
    template = str(candidate.get("parsed_template") or "").strip() or infer_template(candidate, None)
    candidate_timeframe = normalize_timeframe(timeframe or str(candidate.get("parsed_timeframe") or candidate.get("timeframe") or "5m"))
    symbols = symbol_list(candidate.get("parsed_symbols"))
    bars = fetch_bars(symbols, candidate_timeframe, max_symbols)
    by_symbol: dict[str, list[Bar]] = {}
    for bar in bars:
        by_symbol.setdefault(bar.symbol, []).append(bar)
    aggregate: dict[str, list[float]] = {}
    symbol_diagnostics: list[dict[str, Any]] = []
    for symbol, symbol_bars in sorted(by_symbol.items()):
        symbol_returns = returns_for_symbol(symbol_bars, template, total_cost)
        if not symbol_returns:
            symbol_diagnostics.append({"symbol": symbol, "bars": len(symbol_bars), "status": "insufficient_bars"})
            continue
        for ts, value in symbol_returns.items():
            aggregate.setdefault(ts, []).append(value)
        symbol_diagnostics.append({"symbol": symbol, "bars": len(symbol_bars), "return_bars": len(symbol_returns), "status": "used"})
    returns_by_ts = {ts: statistics.mean(values) for ts, values in aggregate.items() if values}
    if not returns_by_ts:
        return None
    return StrategySeries(
        strategy_id=int(candidate["id"]),
        candidate_key=str(candidate.get("candidate_key")),
        name=str(candidate.get("name")),
        template=template,
        timeframe=candidate_timeframe,
        symbols=sorted(by_symbol),
        returns_by_ts=returns_by_ts,
        diagnostics={
            "parse_status": candidate.get("parse_status"),
            "latest_gate_status": candidate.get("latest_gate_status"),
            "latest_gate_rows": candidate.get("latest_gate_rows"),
            "symbol_diagnostics": symbol_diagnostics,
            "source_table": "trading.ohlcv",
        },
    )


def build_benchmark(timeframe: str, max_symbols: int) -> dict[str, float]:
    bars = fetch_bars([], timeframe, max_symbols)
    by_symbol: dict[str, list[Bar]] = {}
    for bar in bars:
        by_symbol.setdefault(bar.symbol, []).append(bar)
    aggregate: dict[str, list[float]] = {}
    for symbol_bars in by_symbol.values():
        closes = [bar.close for bar in symbol_bars]
        for index in range(1, len(closes)):
            aggregate.setdefault(symbol_bars[index].ts, []).append(closes[index] / closes[index - 1] - 1.0)
    return {ts: statistics.mean(values) for ts, values in aggregate.items() if values}


def stddev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(right) < 2 or len(left) != len(right):
        return None
    left_std = stddev(left)
    right_std = stddev(right)
    if not left_std or not right_std:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / len(left)
    return covariance / (left_std * right_std)


def beta(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(right) < 2 or len(left) != len(right):
        return None
    variance = stddev(right) ** 2
    if not variance:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / len(left)
    return covariance / variance


def compound_return(values: list[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def summary_metrics(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"bars": 0, "total_return": None, "average_return": None, "volatility": None, "win_rate": None, "max_drawdown": None}
    equity = [1.0]
    for value in values:
        equity.append(equity[-1] * (1.0 + value))
    return {
        "bars": len(values),
        "total_return": compound_return(values),
        "average_return": statistics.mean(values),
        "volatility": stddev(values),
        "win_rate": sum(1 for value in values if value > 0) / len(values),
        "max_drawdown": max_drawdown(equity),
    }


def regime_labels(benchmark: dict[str, float]) -> dict[str, str]:
    values = list(benchmark.values())
    if not values:
        return {}
    abs_threshold = statistics.median(abs(value) for value in values)
    output = {}
    for ts, value in benchmark.items():
        trend = "up" if value >= 0 else "down"
        vol = "high_vol" if abs(value) >= abs_threshold else "low_vol"
        output[ts] = f"{trend}_{vol}"
    return output


def latest_run_id(run_key: str) -> int:
    rows = run_psql_json(f"SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (SELECT id FROM strategy.quant_analytics_runs WHERE run_key = {sql_literal(run_key)}) rows")
    if not rows:
        raise RuntimeError("analytics run row was not created")
    return int(rows[0]["id"])


def create_run(run_key: str, strategy_ids: list[int], timeframe: str, created_by: str) -> int:
    run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.quant_analytics_runs (
                run_key, run_name, strategy_ids, timeframe, status, created_by, started_at
            )
            VALUES (
                {sql_literal(run_key)}, 'Strategy Quant Analytics v1',
                ARRAY[{','.join(str(item) for item in strategy_ids)}]::BIGINT[],
                {sql_literal(timeframe)}, 'running', {sql_literal(created_by)}, now()
            )
            ON CONFLICT (run_key) DO UPDATE SET
                strategy_ids = EXCLUDED.strategy_ids,
                timeframe = EXCLUDED.timeframe,
                status = 'running',
                started_at = now(),
                finished_at = NULL,
                created_by = EXCLUDED.created_by
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    run_id = latest_run_id(run_key)
    psql_exec(
        f"""
        DELETE FROM strategy.strategy_return_series WHERE analytics_run_id = {run_id};
        DELETE FROM strategy.regime_performance_splits WHERE analytics_run_id = {run_id};
        DELETE FROM strategy.factor_attribution WHERE analytics_run_id = {run_id};
        DELETE FROM strategy.capacity_liquidity_checks WHERE analytics_run_id = {run_id};
        DELETE FROM strategy.strategy_correlation_matrix WHERE analytics_run_id = {run_id};
        DELETE FROM strategy.strategy_portfolio_optimizer_runs WHERE analytics_run_id = {run_id};
        """
    )
    return run_id


def insert_values(table: str, columns: list[str], rows: list[str]) -> None:
    if not rows:
        return
    psql_exec(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(rows) + ";")


def persist_return_series(run_id: int, series: list[StrategySeries], benchmark: dict[str, float], labels: dict[str, str]) -> None:
    rows = []
    for item in series:
        for ts, value in sorted(item.returns_by_ts.items()):
            rows.append(
                "("
                + ",".join(
                    [
                        str(run_id),
                        str(item.strategy_id),
                        f"{sql_literal(ts)}::timestamptz",
                        sql_literal(item.timeframe),
                        str(value),
                        "NULL" if ts not in benchmark else str(benchmark[ts]),
                        sql_literal(labels.get(ts)),
                        sql_jsonb({"template": item.template}),
                    ]
                )
                + ")"
            )
    insert_values(
        "strategy.strategy_return_series",
        ["analytics_run_id", "strategy_id", "ts", "timeframe", "return_value", "benchmark_return", "regime_label", "diagnostics"],
        rows,
    )


def persist_regime_splits(run_id: int, series: list[StrategySeries], labels: dict[str, str]) -> list[dict[str, Any]]:
    output = []
    rows = []
    for item in series:
        grouped: dict[str, list[float]] = {}
        for ts, value in item.returns_by_ts.items():
            grouped.setdefault(labels.get(ts, "unknown"), []).append(value)
        for label, values in sorted(grouped.items()):
            metrics = summary_metrics(values)
            output.append({"strategy_id": item.strategy_id, "strategy_name": item.name, "regime_label": label, **metrics})
            rows.append(
                "("
                + ",".join(
                    [
                        str(run_id),
                        str(item.strategy_id),
                        sql_literal("benchmark_trend_volatility"),
                        sql_literal(label),
                        str(metrics["bars"]),
                        "NULL" if metrics["total_return"] is None else str(metrics["total_return"]),
                        "NULL" if metrics["average_return"] is None else str(metrics["average_return"]),
                        "NULL" if metrics["volatility"] is None else str(metrics["volatility"]),
                        "NULL" if metrics["win_rate"] is None else str(metrics["win_rate"]),
                        "NULL" if metrics["max_drawdown"] is None else str(metrics["max_drawdown"]),
                        sql_jsonb({"method": "benchmark return sign plus median absolute return"}),
                    ]
                )
                + ")"
            )
    insert_values(
        "strategy.regime_performance_splits",
        ["analytics_run_id", "strategy_id", "regime_type", "regime_label", "bars", "total_return", "average_return", "volatility", "win_rate", "max_drawdown", "diagnostics"],
        rows,
    )
    return output


def persist_factor_attribution(run_id: int, series: list[StrategySeries], benchmark: dict[str, float]) -> list[dict[str, Any]]:
    output = []
    rows = []
    for item in series:
        common_ts = sorted(set(item.returns_by_ts) & set(benchmark))
        returns = [item.returns_by_ts[ts] for ts in common_ts]
        bench = [benchmark[ts] for ts in common_ts]
        factors = {
            "market_beta": beta(returns, bench),
            "market_correlation": correlation(returns, bench),
            "average_bar_alpha": statistics.mean([ret - b for ret, b in zip(returns, bench)]) if returns else None,
            "volatility_sensitivity": correlation(returns, [abs(value) for value in bench]) if returns else None,
        }
        for factor_name, exposure in factors.items():
            contribution = None if exposure is None else exposure * (statistics.mean(bench) if bench else 0.0)
            output.append({"strategy_id": item.strategy_id, "strategy_name": item.name, "factor_name": factor_name, "exposure": exposure, "contribution": contribution, "overlap_bars": len(common_ts)})
            rows.append(
                "("
                + ",".join(
                    [
                        str(run_id),
                        str(item.strategy_id),
                        sql_literal(factor_name),
                        "NULL" if exposure is None else str(exposure),
                        "NULL" if contribution is None else str(contribution),
                        sql_literal("deterministic_proxy"),
                        sql_jsonb({"overlap_bars": len(common_ts), "benchmark": "equal_weight_ohlcv_universe"}),
                    ]
                )
                + ")"
            )
    insert_values(
        "strategy.factor_attribution",
        ["analytics_run_id", "strategy_id", "factor_name", "exposure", "contribution", "method", "diagnostics"],
        rows,
    )
    return output


def persist_capacity(run_id: int, series: list[StrategySeries], participation_rate: float) -> list[dict[str, Any]]:
    output = []
    rows = []
    for item in series:
        symbols = item.symbols
        variants = sorted(set(symbols + [symbol.split(":", 1)[-1] for symbol in symbols if ":" in symbol]))
        symbol_filter = ""
        if variants:
            symbol_filter = f"AND upper(symbol.symbol) = ANY(ARRAY[{','.join(sql_literal(symbol.upper()) for symbol in variants)}]::TEXT[])"
        coverage = run_psql_json(
            f"""
            SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
            FROM (
                SELECT symbol.symbol,
                       count(*)::BIGINT AS bars,
                       avg(ohlcv.volume)::FLOAT8 AS average_volume,
                       avg(ohlcv.close * ohlcv.volume)::FLOAT8 AS average_traded_value
                FROM trading.ohlcv ohlcv
                JOIN trading.symbols symbol ON symbol.id = ohlcv.symbol_id
                WHERE ohlcv.timeframe = {sql_literal(item.timeframe)}
                  AND ohlcv.close IS NOT NULL
                  {symbol_filter}
                GROUP BY symbol.symbol
                ORDER BY symbol.symbol
            ) rows
            """
        )
        for row in coverage:
            avg_traded_value = row.get("average_traded_value")
            capacity = None if avg_traded_value is None else float(avg_traded_value) * participation_rate
            status = "missing_volume"
            if capacity and capacity > 10_000_000:
                status = "usable"
            elif capacity and capacity > 1_000_000:
                status = "thin"
            output.append({"strategy_id": item.strategy_id, "strategy_name": item.name, "symbol": row["symbol"], "capacity_notional": capacity, "liquidity_status": status})
            rows.append(
                "("
                + ",".join(
                    [
                        str(run_id),
                        str(item.strategy_id),
                        sql_literal(row["symbol"]),
                        sql_literal(item.timeframe),
                        str(int(row["bars"])),
                        "NULL" if row.get("average_volume") is None else str(row["average_volume"]),
                        "NULL" if avg_traded_value is None else str(avg_traded_value),
                        str(participation_rate),
                        "NULL" if capacity is None else str(capacity),
                        sql_literal(status),
                        sql_jsonb({"method": "average close times volume times participation_rate", "currency": "source_quote_currency"}),
                    ]
                )
                + ")"
            )
    insert_values(
        "strategy.capacity_liquidity_checks",
        ["analytics_run_id", "strategy_id", "symbol", "timeframe", "bars", "average_volume", "average_traded_value", "participation_rate", "capacity_notional", "liquidity_status", "diagnostics"],
        rows,
    )
    return output


def persist_correlations(run_id: int, series: list[StrategySeries]) -> list[dict[str, Any]]:
    output = []
    rows = []
    for left in series:
        for right in series:
            common_ts = sorted(set(left.returns_by_ts) & set(right.returns_by_ts))
            left_values = [left.returns_by_ts[ts] for ts in common_ts]
            right_values = [right.returns_by_ts[ts] for ts in common_ts]
            corr = correlation(left_values, right_values)
            output.append({"strategy_id_a": left.strategy_id, "strategy_id_b": right.strategy_id, "correlation": corr, "overlap_bars": len(common_ts)})
            rows.append(
                "("
                + ",".join(
                    [
                        str(run_id),
                        str(left.strategy_id),
                        str(right.strategy_id),
                        "NULL" if corr is None else str(corr),
                        str(len(common_ts)),
                        sql_jsonb({"method": "pearson_on_equal_weight_strategy_bar_returns"}),
                    ]
                )
                + ")"
            )
    insert_values(
        "strategy.strategy_correlation_matrix",
        ["analytics_run_id", "strategy_id_a", "strategy_id_b", "correlation", "overlap_bars", "diagnostics"],
        rows,
    )
    return output


def persist_optimizer(run_id: int, series: list[StrategySeries]) -> dict[str, Any]:
    scores = []
    for item in series:
        values = list(item.returns_by_ts.values())
        avg = statistics.mean(values) if values else 0.0
        vol = stddev(values)
        sharpe = avg / vol if vol else -999.0
        score = max(0.0, sharpe) / vol if vol else 0.0
        scores.append({"strategy_id": item.strategy_id, "candidate_key": item.candidate_key, "strategy_name": item.name, "average_return": avg, "volatility": vol, "sharpe_proxy": sharpe, "score": score})
    positive_total = sum(item["score"] for item in scores)
    if positive_total <= 0 and scores:
        ranked = sorted(scores, key=lambda item: item["sharpe_proxy"], reverse=True)
        selected = ranked[: min(3, len(ranked))]
        weights = {str(item["strategy_id"]): 1.0 / len(selected) for item in selected}
        status = "draft_least_bad"
    else:
        weights = {str(item["strategy_id"]): item["score"] / positive_total for item in scores if item["score"] > 0}
        status = "draft"
    expected_return = sum(next((score["average_return"] for score in scores if str(score["strategy_id"]) == strategy_id), 0.0) * weight for strategy_id, weight in weights.items())
    expected_vol = math.sqrt(sum((next((score["volatility"] for score in scores if str(score["strategy_id"]) == strategy_id), 0.0) * weight) ** 2 for strategy_id, weight in weights.items())) if weights else None
    sharpe = expected_return / expected_vol if expected_vol else None
    result = {
        "candidate_count": len(series),
        "weights": weights,
        "expected_return": expected_return,
        "expected_volatility": expected_vol,
        "sharpe_proxy": sharpe,
        "status": status,
        "scores": scores,
    }
    rows = [
        "("
        + ",".join(
            [
                str(run_id),
                sql_literal("inverse_volatility_sharpe_proxy"),
                str(len(series)),
                sql_jsonb(weights),
                "NULL" if expected_return is None else str(expected_return),
                "NULL" if expected_vol is None else str(expected_vol),
                "NULL" if sharpe is None else str(sharpe),
                sql_jsonb({"long_only": True, "max_weight": 1.0, "paper_only": True}),
                sql_jsonb({"scores": scores, "not_live_allocation": True}),
                sql_literal(status),
                sql_literal("Strategy Portfolio Optimizer"),
            ]
        )
        + ")"
    ]
    insert_values(
        "strategy.strategy_portfolio_optimizer_runs",
        ["analytics_run_id", "optimizer_method", "candidate_count", "weights", "expected_return", "expected_volatility", "sharpe_proxy", "constraints", "diagnostics", "status", "created_by"],
        rows,
    )
    return result


def write_artifact(result: dict[str, Any]) -> str:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_ROOT / f"{result['run_key']}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return artifact_reference(path)


def update_run(run_id: int, status: str, metrics: dict[str, Any], diagnostics: dict[str, Any], quality_flags: list[str], artifact_path: str | None) -> None:
    psql_exec(
        f"""
        UPDATE strategy.quant_analytics_runs
        SET status = {sql_literal(status)},
            metrics = {sql_jsonb(metrics)},
            diagnostics = {sql_jsonb(diagnostics)},
            quality_flags = {sql_text_array(quality_flags)},
            artifact_path = {sql_literal(artifact_path)},
            finished_at = now()
        WHERE id = {run_id};
        """
    )


def run_analytics(args: argparse.Namespace) -> dict[str, Any]:
    timeframe = normalize_timeframe(args.timeframe)
    strategy_ids = [int(item) for item in args.strategy_ids.split(",") if item.strip()] if args.strategy_ids else []
    candidates = fetch_candidates(strategy_ids, args.limit)
    total_cost = (args.cost_bps + args.slippage_bps) / 10000.0
    series = []
    skipped = []
    for candidate in candidates:
        built = build_strategy_series(candidate, timeframe, args.max_symbols, total_cost)
        if built is None:
            skipped.append({"strategy_id": candidate.get("id"), "strategy_name": candidate.get("name"), "reason": "insufficient OHLCV bars"})
        else:
            series.append(built)
    selected_ids = [item.strategy_id for item in series]
    run_key = args.run_key or "qa_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = create_run(run_key, selected_ids, timeframe, args.actor)
    quality_flags = []
    if not series:
        quality_flags.append("no_strategy_series_built")
        result = {"run_key": run_key, "status": "failed", "skipped": skipped}
        artifact_path = write_artifact(result)
        update_run(run_id, "failed", {"strategies": 0}, {"skipped": skipped}, quality_flags, artifact_path)
        return result
    benchmark = build_benchmark(timeframe, args.max_symbols)
    labels = regime_labels(benchmark)
    persist_return_series(run_id, series, benchmark, labels)
    regime = persist_regime_splits(run_id, series, labels)
    factor = persist_factor_attribution(run_id, series, benchmark)
    capacity = persist_capacity(run_id, series, args.participation_rate)
    correlations = persist_correlations(run_id, series)
    optimizer = persist_optimizer(run_id, series)
    min_bars = min(len(item.returns_by_ts) for item in series)
    if min_bars < 500:
        quality_flags.append("thin_return_history")
    if len(series) < 3:
        quality_flags.append("too_few_strategies_for_portfolio_optimization")
    if any(item.diagnostics.get("parse_status") not in {"passed"} for item in series):
        quality_flags.append("some_strategies_missing_passed_dsl")
    result = {
        "run_id": run_id,
        "run_key": run_key,
        "status": "completed",
        "timeframe": timeframe,
        "strategies": [
            {
                "strategy_id": item.strategy_id,
                "candidate_key": item.candidate_key,
                "strategy_name": item.name,
                "template": item.template,
                "return_bars": len(item.returns_by_ts),
                "symbols": item.symbols,
                "diagnostics": item.diagnostics,
            }
            for item in series
        ],
        "skipped": skipped,
        "regime_rows": len(regime),
        "factor_rows": len(factor),
        "capacity_rows": len(capacity),
        "correlation_rows": len(correlations),
        "optimizer": optimizer,
        "quality_flags": quality_flags,
        "seed_data_allowed": False,
        "source_table": "trading.ohlcv",
    }
    artifact_path = write_artifact(result)
    result["artifact_path"] = artifact_path
    update_run(
        run_id,
        "completed",
        {
            "strategy_count": len(series),
            "min_return_bars": min_bars,
            "regime_rows": len(regime),
            "factor_rows": len(factor),
            "capacity_rows": len(capacity),
            "correlation_rows": len(correlations),
            "optimizer_rows": 1,
        },
        {"skipped": skipped, "benchmark_bars": len(benchmark)},
        quality_flags,
        artifact_path,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strategy quant analytics from real OHLCV and candidate data.")
    parser.add_argument("--run-key", default="")
    parser.add_argument("--strategy-ids", default="")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-symbols", type=int, default=14)
    parser.add_argument("--cost-bps", type=float, default=3.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--participation-rate", type=float, default=0.05)
    parser.add_argument("--actor", default="Quant Analytics Agent")
    args = parser.parse_args()
    result = run_analytics(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), flush=True)
        raise SystemExit(1)
