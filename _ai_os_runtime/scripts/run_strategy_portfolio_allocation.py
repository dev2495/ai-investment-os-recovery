#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_storage import artifact_reference, artifact_root

from run_strategy_backtest import max_drawdown, run_psql_json, sql_jsonb, sql_literal


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = artifact_root("strategy_allocations")


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


def latest_analytics_run(run_key: str | None) -> dict[str, Any]:
    where = f"WHERE run_key = {sql_literal(run_key)}" if run_key else "WHERE status = 'completed'"
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, run_key, timeframe, status, metrics, diagnostics, quality_flags
            FROM strategy.quant_analytics_runs
            {where}
            ORDER BY finished_at DESC NULLS LAST, id DESC
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError("No completed quant analytics run found")
    return rows[0]


def latest_optimizer(analytics_run_id: int) -> dict[str, Any] | None:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, analytics_run_id, weights, expected_return, expected_volatility,
                   sharpe_proxy, diagnostics, status
            FROM strategy.strategy_portfolio_optimizer_runs
            WHERE analytics_run_id = {analytics_run_id}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ) rows
        """
    )
    return rows[0] if rows else None


def return_series(analytics_run_id: int) -> dict[int, dict[str, float]]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT strategy_id, ts::TEXT AS ts, return_value::FLOAT8 AS return_value
            FROM strategy.strategy_return_series
            WHERE analytics_run_id = {analytics_run_id}
            ORDER BY strategy_id, ts
        ) rows
        """
    )
    output: dict[int, dict[str, float]] = {}
    for row in rows:
        output.setdefault(int(row["strategy_id"]), {})[str(row["ts"])] = float(row["return_value"])
    return output


def strategy_names(strategy_ids: list[int]) -> dict[int, dict[str, str]]:
    if not strategy_ids:
        return {}
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, coalesce(candidate_key, 'candidate_' || id::TEXT) AS candidate_key, name
            FROM strategy.strategy_candidates
            WHERE id = ANY(ARRAY[{','.join(str(item) for item in strategy_ids)}]::BIGINT[])
        ) rows
        """
    )
    return {int(row["id"]): {"candidate_key": str(row["candidate_key"]), "name": str(row["name"])} for row in rows}


def normalize_weights(raw_weights: dict[str, Any], series_by_strategy: dict[int, dict[str, float]], max_weight: float) -> dict[int, float]:
    weights = {int(key): float(value) for key, value in raw_weights.items() if int(key) in series_by_strategy and float(value) > 0}
    if not weights:
        strategy_ids = sorted(series_by_strategy)
        if not strategy_ids:
            return {}
        equal = min(max_weight, 1.0 / len(strategy_ids))
        return {strategy_id: equal for strategy_id in strategy_ids}
    total_raw = sum(weights.values())
    normalized = {strategy_id: weight / total_raw for strategy_id, weight in weights.items()} if total_raw else {}
    capped = {strategy_id: min(weight, max_weight) for strategy_id, weight in normalized.items()}
    total = sum(capped.values())
    if total > 1.0:
        return {strategy_id: weight / total for strategy_id, weight in capped.items()}
    return capped


def portfolio_returns(weights: dict[int, float], series_by_strategy: dict[int, dict[str, float]]) -> dict[str, float]:
    if not weights:
        return {}
    common_ts: set[str] | None = None
    for strategy_id in weights:
        timestamps = set(series_by_strategy.get(strategy_id, {}))
        common_ts = timestamps if common_ts is None else common_ts & timestamps
    if not common_ts:
        return {}
    output = {}
    for ts in sorted(common_ts):
        output[ts] = sum(series_by_strategy[strategy_id][ts] * weight for strategy_id, weight in weights.items())
    return output


def stddev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def compound(values: list[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, int(round((len(sorted_values) - 1) * p))))
    return sorted_values[index]


def bootstrap_ruin(
    returns: list[float],
    starting_capital: float,
    ruin_threshold_pct: float,
    horizon_bars: int,
    simulation_count: int,
    seed: int,
) -> dict[str, Any]:
    if not returns:
        return {
            "ruin_probability": None,
            "expected_terminal_value": None,
            "terminal_p05": None,
            "terminal_p50": None,
            "terminal_p95": None,
            "max_drawdown_p95": None,
            "terminal_values": [],
            "drawdowns": [],
        }
    rng = random.Random(seed)
    ruin_level = starting_capital * (1.0 - ruin_threshold_pct)
    terminal_values = []
    drawdowns = []
    ruin_count = 0
    for _ in range(simulation_count):
        equity = [starting_capital]
        ruined = False
        for _bar in range(horizon_bars):
            sampled = returns[rng.randrange(len(returns))]
            equity.append(equity[-1] * (1.0 + sampled))
            if equity[-1] <= ruin_level:
                ruined = True
        if ruined:
            ruin_count += 1
        terminal_values.append(equity[-1])
        drawdowns.append(abs(max_drawdown(equity)))
    return {
        "ruin_probability": ruin_count / simulation_count,
        "expected_terminal_value": statistics.mean(terminal_values),
        "terminal_p05": percentile(terminal_values, 0.05),
        "terminal_p50": percentile(terminal_values, 0.50),
        "terminal_p95": percentile(terminal_values, 0.95),
        "max_drawdown_p95": percentile(drawdowns, 0.95),
        "terminal_values": terminal_values,
        "drawdowns": drawdowns,
    }


def create_allocation_run(
    allocation_key: str,
    analytics_run_id: int,
    optimizer_run_id: int | None,
    capital_base: float,
    timeframe: str,
    created_by: str,
) -> int:
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.strategy_portfolio_allocation_runs (
                allocation_key, analytics_run_id, optimizer_run_id, capital_base,
                timeframe, status, created_by
            )
            VALUES (
                {sql_literal(allocation_key)}, {analytics_run_id},
                {optimizer_run_id if optimizer_run_id else 'NULL'}, {capital_base},
                {sql_literal(timeframe)}, 'running', {sql_literal(created_by)}
            )
            ON CONFLICT (allocation_key) DO UPDATE SET
                analytics_run_id = EXCLUDED.analytics_run_id,
                optimizer_run_id = EXCLUDED.optimizer_run_id,
                capital_base = EXCLUDED.capital_base,
                timeframe = EXCLUDED.timeframe,
                status = 'running',
                created_by = EXCLUDED.created_by,
                created_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    if not rows:
        raise RuntimeError("allocation run row was not created")
    run_id = int(rows[0]["id"])
    psql_exec(
        f"""
        DELETE FROM strategy.strategy_portfolio_allocations WHERE allocation_run_id = {run_id};
        DELETE FROM strategy.probability_of_ruin_metrics WHERE allocation_run_id = {run_id};
        """
    )
    return run_id


def insert_values(table: str, columns: list[str], rows: list[str]) -> None:
    if not rows:
        return
    psql_exec(f"INSERT INTO {table} ({', '.join(columns)}) VALUES\n" + ",\n".join(rows) + ";")


def write_artifact(result: dict[str, Any]) -> str:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_ROOT / f"{result['allocation_key']}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return artifact_reference(path)


def update_allocation_run(
    allocation_run_id: int,
    status: str,
    allocation_payload: dict[str, Any],
    constraints: dict[str, Any],
    diagnostics: dict[str, Any],
    quality_flags: list[str],
    artifact_path: str | None,
    expected_return: float | None,
    expected_volatility: float | None,
    expected_max_drawdown: float | None,
) -> None:
    psql_exec(
        f"""
        UPDATE strategy.strategy_portfolio_allocation_runs
        SET status = {sql_literal(status)},
            allocation_payload = {sql_jsonb(allocation_payload)},
            constraints = {sql_jsonb(constraints)},
            diagnostics = {sql_jsonb(diagnostics)},
            quality_flags = {sql_text_array(quality_flags)},
            artifact_path = {sql_literal(artifact_path)},
            expected_return = {"NULL" if expected_return is None else expected_return},
            expected_volatility = {"NULL" if expected_volatility is None else expected_volatility},
            expected_max_drawdown = {"NULL" if expected_max_drawdown is None else expected_max_drawdown}
        WHERE id = {allocation_run_id};
        """
    )


def run_allocation(args: argparse.Namespace) -> dict[str, Any]:
    analytics = latest_analytics_run(args.analytics_run_key or None)
    analytics_run_id = int(analytics["id"])
    optimizer = latest_optimizer(analytics_run_id)
    series_by_strategy = return_series(analytics_run_id)
    raw_weights = (optimizer or {}).get("weights") or {}
    weights = normalize_weights(raw_weights, series_by_strategy, args.max_weight)
    names = strategy_names(sorted(weights))
    portfolio_by_ts = portfolio_returns(weights, series_by_strategy)
    portfolio_values = list(portfolio_by_ts.values())
    allocation_key = args.allocation_key or "alloc_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    allocation_run_id = create_allocation_run(
        allocation_key,
        analytics_run_id,
        int(optimizer["id"]) if optimizer and optimizer.get("id") else None,
        args.capital_base,
        str(analytics.get("timeframe") or args.timeframe),
        args.actor,
    )

    quality_flags = list(analytics.get("quality_flags") or [])
    if len(portfolio_values) < 500:
        quality_flags.append("thin_portfolio_return_history")
    if not weights:
        quality_flags.append("no_strategy_weights_available")

    allocation_rows = []
    allocation_payload = []
    portfolio_vol = stddev(portfolio_values)
    for strategy_id, weight in sorted(weights.items()):
        values = list(series_by_strategy.get(strategy_id, {}).values())
        expected_return = statistics.mean(values) if values else None
        expected_vol = stddev(values) if values else None
        risk_contribution = None
        if portfolio_vol and expected_vol is not None:
            risk_contribution = weight * expected_vol / portfolio_vol
        target_notional = args.capital_base * weight
        details = {
            "strategy_id": strategy_id,
            "candidate_key": names.get(strategy_id, {}).get("candidate_key", f"candidate_{strategy_id}"),
            "strategy_name": names.get(strategy_id, {}).get("name", f"strategy_{strategy_id}"),
            "target_weight": weight,
            "target_notional": target_notional,
            "expected_return": expected_return,
            "expected_volatility": expected_vol,
            "risk_contribution": risk_contribution,
        }
        allocation_payload.append(details)
        allocation_rows.append(
            "("
            + ",".join(
                [
                    str(allocation_run_id),
                    str(strategy_id),
                    str(weight),
                    str(target_notional),
                    "NULL" if expected_return is None else str(expected_return),
                    "NULL" if expected_vol is None else str(expected_vol),
                    "NULL" if risk_contribution is None else str(risk_contribution),
                    sql_literal("paper_only"),
                    sql_jsonb({"source": "strategy_portfolio_optimizer", "live_execution_allowed": False}),
                ]
            )
            + ")"
        )
    insert_values(
        "strategy.strategy_portfolio_allocations",
        ["allocation_run_id", "strategy_id", "target_weight", "target_notional", "expected_return", "expected_volatility", "risk_contribution", "allocation_status", "diagnostics"],
        allocation_rows,
    )

    portfolio_ruin = bootstrap_ruin(
        portfolio_values,
        args.capital_base,
        args.ruin_threshold_pct,
        args.horizon_bars,
        args.simulation_count,
        args.seed,
    )
    ruin_rows = [
        "("
        + ",".join(
            [
                str(allocation_run_id),
                str(analytics_run_id),
                "NULL",
                sql_literal("portfolio"),
                str(args.horizon_bars),
                str(args.simulation_count),
                str(args.capital_base),
                str(args.ruin_threshold_pct),
                "NULL" if portfolio_ruin["ruin_probability"] is None else str(portfolio_ruin["ruin_probability"]),
                "NULL" if portfolio_ruin["expected_terminal_value"] is None else str(portfolio_ruin["expected_terminal_value"]),
                "NULL" if portfolio_ruin["terminal_p05"] is None else str(portfolio_ruin["terminal_p05"]),
                "NULL" if portfolio_ruin["terminal_p50"] is None else str(portfolio_ruin["terminal_p50"]),
                "NULL" if portfolio_ruin["terminal_p95"] is None else str(portfolio_ruin["terminal_p95"]),
                "NULL" if portfolio_ruin["max_drawdown_p95"] is None else str(portfolio_ruin["max_drawdown_p95"]),
                sql_literal("deterministic_bootstrap"),
                sql_jsonb({"seed": args.seed, "return_bars": len(portfolio_values), "source": "strategy.strategy_return_series"}),
                sql_text_array(quality_flags),
                sql_literal("Risk Agent"),
            ]
        )
        + ")"
    ]
    for strategy_id, values_by_ts in sorted(series_by_strategy.items()):
        if strategy_id not in weights:
            continue
        values = list(values_by_ts.values())
        strategy_ruin = bootstrap_ruin(
            values,
            args.capital_base * weights[strategy_id],
            args.ruin_threshold_pct,
            args.horizon_bars,
            args.simulation_count,
            args.seed + strategy_id,
        )
        ruin_rows.append(
            "("
            + ",".join(
                [
                    str(allocation_run_id),
                    str(analytics_run_id),
                    str(strategy_id),
                    sql_literal("strategy"),
                    str(args.horizon_bars),
                    str(args.simulation_count),
                    str(args.capital_base * weights[strategy_id]),
                    str(args.ruin_threshold_pct),
                    "NULL" if strategy_ruin["ruin_probability"] is None else str(strategy_ruin["ruin_probability"]),
                    "NULL" if strategy_ruin["expected_terminal_value"] is None else str(strategy_ruin["expected_terminal_value"]),
                    "NULL" if strategy_ruin["terminal_p05"] is None else str(strategy_ruin["terminal_p05"]),
                    "NULL" if strategy_ruin["terminal_p50"] is None else str(strategy_ruin["terminal_p50"]),
                    "NULL" if strategy_ruin["terminal_p95"] is None else str(strategy_ruin["terminal_p95"]),
                    "NULL" if strategy_ruin["max_drawdown_p95"] is None else str(strategy_ruin["max_drawdown_p95"]),
                    sql_literal("deterministic_bootstrap"),
                    sql_jsonb({"seed": args.seed + strategy_id, "return_bars": len(values), "source": "strategy.strategy_return_series"}),
                    sql_text_array(quality_flags),
                    sql_literal("Risk Agent"),
                ]
            )
            + ")"
        )
    insert_values(
        "strategy.probability_of_ruin_metrics",
        [
            "allocation_run_id",
            "analytics_run_id",
            "strategy_id",
            "metric_scope",
            "horizon_bars",
            "simulation_count",
            "starting_capital",
            "ruin_threshold_pct",
            "ruin_probability",
            "expected_terminal_value",
            "terminal_p05",
            "terminal_p50",
            "terminal_p95",
            "max_drawdown_p95",
            "method",
            "diagnostics",
            "quality_flags",
            "created_by",
        ],
        ruin_rows,
    )

    expected_return = statistics.mean(portfolio_values) if portfolio_values else None
    expected_volatility = portfolio_vol if portfolio_values else None
    expected_max_drawdown = max_drawdown([1.0] + [1.0 + value for value in portfolio_values]) if portfolio_values else None
    constraints = {
        "max_weight": args.max_weight,
        "capital_base": args.capital_base,
        "paper_only": True,
        "live_execution_allowed": False,
        "ruin_threshold_pct": args.ruin_threshold_pct,
        "horizon_bars": args.horizon_bars,
    }
    result = {
        "allocation_run_id": allocation_run_id,
        "allocation_key": allocation_key,
        "analytics_run_id": analytics_run_id,
        "analytics_run_key": analytics.get("run_key"),
        "optimizer_run_id": optimizer.get("id") if optimizer else None,
        "status": "completed",
        "capital_base": args.capital_base,
        "allocations": allocation_payload,
        "cash_weight": max(0.0, 1.0 - sum(weights.values())),
        "portfolio_return_bars": len(portfolio_values),
        "expected_return": expected_return,
        "expected_volatility": expected_volatility,
        "probability_of_ruin": portfolio_ruin["ruin_probability"],
        "expected_terminal_value": portfolio_ruin["expected_terminal_value"],
        "terminal_p05": portfolio_ruin["terminal_p05"],
        "terminal_p50": portfolio_ruin["terminal_p50"],
        "terminal_p95": portfolio_ruin["terminal_p95"],
        "max_drawdown_p95": portfolio_ruin["max_drawdown_p95"],
        "quality_flags": sorted(set(quality_flags)),
        "seed_data_allowed": False,
        "live_execution_allowed": False,
    }
    artifact_path = write_artifact(result)
    result["artifact_path"] = artifact_path
    update_allocation_run(
        allocation_run_id,
        "completed",
        {"allocations": allocation_payload},
        constraints,
        {
            "portfolio_return_bars": len(portfolio_values),
            "cash_weight": max(0.0, 1.0 - sum(weights.values())),
            "optimizer_weights": raw_weights,
            "source_table": "strategy.strategy_return_series",
            "simulation_seed": args.seed,
            "simulation_count": args.simulation_count,
        },
        sorted(set(quality_flags)),
        artifact_path,
        expected_return,
        expected_volatility,
        expected_max_drawdown,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Create paper strategy portfolio allocation and probability-of-ruin metrics.")
    parser.add_argument("--allocation-key", default="")
    parser.add_argument("--analytics-run-key", default="")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--capital-base", type=float, default=1_000_000.0)
    parser.add_argument("--max-weight", type=float, default=0.35)
    parser.add_argument("--ruin-threshold-pct", type=float, default=0.20)
    parser.add_argument("--horizon-bars", type=int, default=252)
    parser.add_argument("--simulation-count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=260706)
    parser.add_argument("--actor", default="Strategy Portfolio Manager")
    args = parser.parse_args()
    result = run_allocation(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), flush=True)
        raise SystemExit(1)
