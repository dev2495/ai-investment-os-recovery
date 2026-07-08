#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import (
    Bar,
    fetch_bars,
    fetch_candidate,
    infer_template,
    max_drawdown,
    normalize_timeframe,
    periods_per_year,
    rolling_mean,
    rolling_stdev,
    run_psql_json,
    sql_jsonb,
    sql_literal,
)


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = RUNTIME_ROOT / "artifacts" / "optimizations"


def parameter_grid(template: str) -> list[dict[str, float | int | str]]:
    if template == "mean_reversion":
        return [
            {"window": window, "z_entry": z_entry}
            for window in [12, 20, 30]
            for z_entry in [-0.75, -1.0, -1.5]
        ]
    if template == "breakout":
        return [
            {"window": window, "threshold": threshold}
            for window in [6, 12, 24]
            for threshold in [0.001, 0.002, 0.004]
        ]
    if template == "low_volatility":
        return [{"window": window, "quantile": quantile} for window in [6, 12, 24] for quantile in [0.35, 0.5, 0.65]]
    return [{"lookback": lookback} for lookback in [6, 12, 18, 24, 36]]


def positions_for_params(closes: list[float], template: str, params: dict[str, float | int | str]) -> list[int]:
    if template == "mean_reversion":
        window = int(params["window"])
        z_entry = float(params["z_entry"])
        mean = rolling_mean(closes, window)
        stdev = rolling_stdev(closes, window)
        return [
            1 if mean[index] is not None and stdev[index] and (closes[index] - float(mean[index])) / float(stdev[index]) < z_entry else 0
            for index in range(len(closes))
        ]
    if template == "breakout":
        window = int(params["window"])
        threshold = float(params["threshold"])
        mean = rolling_mean(closes, window)
        return [1 if mean[index] is not None and closes[index] > float(mean[index]) * (1.0 + threshold) else 0 for index in range(len(closes))]
    if template == "low_volatility":
        window = int(params["window"])
        quantile = float(params["quantile"])
        returns = [0.0] + [(closes[index] / closes[index - 1] - 1.0) for index in range(1, len(closes))]
        volatility = rolling_stdev(returns, window)
        valid_vols = sorted(float(value) for value in volatility if value is not None)
        if not valid_vols:
            return [0] * len(closes)
        threshold_index = min(len(valid_vols) - 1, max(0, int(len(valid_vols) * quantile)))
        threshold = valid_vols[threshold_index]
        return [1 if volatility[index] is not None and float(volatility[index]) <= threshold else 0 for index in range(len(closes))]
    lookback = int(params["lookback"])
    return [1 if index >= lookback and closes[index] > closes[index - lookback] else 0 for index in range(len(closes))]


def metrics_for_returns(returns: list[float], timeframe: str) -> dict[str, Any]:
    if not returns:
        return {
            "total_return": 0.0,
            "average_bar_return": 0.0,
            "bar_volatility": 0.0,
            "sharpe_estimate": None,
            "max_drawdown": 0.0,
            "win_rate_by_bar": 0.0,
            "bars": 0,
        }
    equity = [1.0]
    for value in returns:
        equity.append(equity[-1] * (1.0 + value))
    average = statistics.mean(returns)
    volatility = statistics.pstdev(returns)
    return {
        "total_return": equity[-1] - 1.0,
        "average_bar_return": average,
        "bar_volatility": volatility,
        "sharpe_estimate": average / volatility * math.sqrt(periods_per_year(timeframe)) if volatility else None,
        "max_drawdown": max_drawdown(equity),
        "win_rate_by_bar": sum(1 for value in returns if value > 0) / len(returns),
        "bars": len(returns),
    }


def walk_forward_windows(returns: list[float], timeframe: str) -> list[dict[str, Any]]:
    if not returns:
        return []
    total = len(returns)
    train_size = max(40, int(total * 0.45))
    test_size = max(20, int(total * 0.15))
    step = max(20, int(total * 0.15))
    if train_size + test_size > total:
        split = max(1, int(total * 0.6))
        return [
            {
                "fold": 1,
                "train_start": 0,
                "train_end": split,
                "test_start": split,
                "test_end": total,
                "train_metrics": metrics_for_returns(returns[:split], timeframe),
                "test_metrics": metrics_for_returns(returns[split:], timeframe),
            }
        ]
    windows: list[dict[str, Any]] = []
    start = 0
    fold = 1
    while start + train_size + test_size <= total and fold <= 8:
        train_start = start
        train_end = start + train_size
        test_start = train_end
        test_end = test_start + test_size
        windows.append(
            {
                "fold": fold,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "train_metrics": metrics_for_returns(returns[train_start:train_end], timeframe),
                "test_metrics": metrics_for_returns(returns[test_start:test_end], timeframe),
            }
        )
        start += step
        fold += 1
    return windows


def walk_forward_summary(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if not folds:
        return {
            "fold_count": 0,
            "positive_test_folds": 0,
            "average_test_return": 0.0,
            "average_test_sharpe": None,
            "worst_test_drawdown": 0.0,
            "test_consistency": 0.0,
        }
    test_returns = [float(fold["test_metrics"]["total_return"]) for fold in folds]
    test_sharpes = [
        float(fold["test_metrics"]["sharpe_estimate"])
        for fold in folds
        if fold["test_metrics"]["sharpe_estimate"] is not None
    ]
    positive = sum(1 for value in test_returns if value > 0)
    return {
        "fold_count": len(folds),
        "positive_test_folds": positive,
        "average_test_return": statistics.mean(test_returns),
        "average_test_sharpe": statistics.mean(test_sharpes) if test_sharpes else None,
        "worst_test_drawdown": min(float(fold["test_metrics"]["max_drawdown"]) for fold in folds),
        "test_consistency": positive / len(folds),
    }


def simulate_params(bars: list[Bar], template: str, params: dict[str, float | int | str], timeframe: str, cost_bps: float, slippage_bps: float) -> dict[str, Any]:
    by_symbol: dict[str, list[Bar]] = {}
    for bar in bars:
        by_symbol.setdefault(bar.symbol, []).append(bar)
    all_returns: list[float] = []
    trade_count = 0
    total_cost = (cost_bps + slippage_bps) / 10000.0
    symbol_count = 0
    for symbol_bars in by_symbol.values():
        closes = [bar.close for bar in symbol_bars]
        if len(closes) < 20:
            continue
        symbol_count += 1
        positions = positions_for_params(closes, template, params)
        for index in range(1, len(closes)):
            raw_return = closes[index] / closes[index - 1] - 1.0
            turnover = abs(positions[index] - positions[index - 1])
            if turnover:
                trade_count += 1
            all_returns.append(positions[index - 1] * raw_return - turnover * total_cost)
    split = max(1, int(len(all_returns) * 0.6))
    train_returns = all_returns[:split]
    test_returns = all_returns[split:]
    metrics = metrics_for_returns(all_returns, timeframe)
    train_metrics = metrics_for_returns(train_returns, timeframe)
    test_metrics = metrics_for_returns(test_returns, timeframe)
    folds = walk_forward_windows(all_returns, timeframe)
    wf_summary = walk_forward_summary(folds)
    score = (
        (wf_summary["average_test_sharpe"] or test_metrics["sharpe_estimate"] or -99.0)
        + float(wf_summary["average_test_return"]) * 10.0
        - abs(float(wf_summary["worst_test_drawdown"])) * 4.0
        + float(wf_summary["test_consistency"])
    )
    return {
        "params": params,
        "metrics": metrics,
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "walk_forward_folds": folds,
        "walk_forward_summary": wf_summary,
        "score": score,
        "trades_count": trade_count,
        "symbols_tested": symbol_count,
        "returns": all_returns,
    }


def monte_carlo_summary(returns: list[float], runs: int = 200) -> dict[str, Any]:
    if not returns:
        return {"runs": 0, "p05_total_return": None, "p50_total_return": None, "p95_total_return": None, "worst_drawdown_p05": None}
    outcomes: list[float] = []
    drawdowns: list[float] = []
    sample_size = len(returns)
    for run_index in range(runs):
        equity = [1.0]
        for offset in range(sample_size):
            # Deterministic bootstrap offset keeps CI/re-runs stable without pretending randomness is signal.
            sampled = returns[(offset * 37 + run_index * 17) % sample_size]
            equity.append(equity[-1] * (1.0 + sampled))
        outcomes.append(equity[-1] - 1.0)
        drawdowns.append(max_drawdown(equity))
    outcomes.sort()
    drawdowns.sort()
    return {
        "runs": runs,
        "p05_total_return": outcomes[int(0.05 * (runs - 1))],
        "p50_total_return": outcomes[int(0.50 * (runs - 1))],
        "p95_total_return": outcomes[int(0.95 * (runs - 1))],
        "worst_drawdown_p05": drawdowns[int(0.05 * (runs - 1))],
    }


def optimize(candidate: dict[str, Any], symbols: list[str], timeframe: str, template: str, cost_bps: float, slippage_bps: float, max_symbols: int) -> dict[str, Any]:
    bars = fetch_bars(symbols, timeframe, max_symbols)
    grid = parameter_grid(template)
    results = [simulate_params(bars, template, params, timeframe, cost_bps, slippage_bps) for params in grid]
    ranked = sorted(results, key=lambda row: row["score"], reverse=True)
    best = ranked[0] if ranked else {
        "params": {},
        "metrics": metrics_for_returns([], timeframe),
        "train_metrics": metrics_for_returns([], timeframe),
        "test_metrics": metrics_for_returns([], timeframe),
        "walk_forward_folds": [],
        "walk_forward_summary": walk_forward_summary([]),
        "score": -99.0,
        "trades_count": 0,
        "symbols_tested": 0,
        "returns": [],
    }
    warnings = []
    if best["test_metrics"]["bars"] < 300:
        warnings.append("Out-of-sample split is too small for production confidence.")
    if (best["walk_forward_summary"]["average_test_sharpe"] or best["test_metrics"]["sharpe_estimate"] or -99) < 0:
        warnings.append("Best parameter set has negative walk-forward/test Sharpe; reject until broader data proves otherwise.")
    if best["walk_forward_summary"]["test_consistency"] < 0.5:
        warnings.append("Best parameter set is not consistent across walk-forward windows.")
    if best["trades_count"] < 20:
        warnings.append("Trade count is low; Monte Carlo and walk-forward results are weak evidence.")
    if len(bars) < 1000:
        warnings.append("OHLCV sample is thin; this run is a robustness pipeline proof.")
    heatmap_rows = [
        {
            "rank": rank + 1,
            "x_param": next(iter(row["params"].keys())) if row["params"] else "none",
            "x_value": next(iter(row["params"].values())) if row["params"] else "none",
            "y_param": list(row["params"].keys())[1] if len(row["params"]) > 1 else "single_axis",
            "y_value": list(row["params"].values())[1] if len(row["params"]) > 1 else "all",
            "score": row["score"],
            "test_return": row["test_metrics"]["total_return"],
            "test_sharpe": row["test_metrics"]["sharpe_estimate"],
            "walk_forward_test_return": row["walk_forward_summary"]["average_test_return"],
            "walk_forward_test_sharpe": row["walk_forward_summary"]["average_test_sharpe"],
            "walk_forward_consistency": row["walk_forward_summary"]["test_consistency"],
            "max_drawdown": row["metrics"]["max_drawdown"],
        }
        for rank, row in enumerate(ranked)
    ]
    compact_results = [
        {
            "rank": rank + 1,
            "params": row["params"],
            "score": row["score"],
            "total_return": row["metrics"]["total_return"],
            "test_total_return": row["test_metrics"]["total_return"],
            "test_sharpe": row["test_metrics"]["sharpe_estimate"],
            "walk_forward_test_return": row["walk_forward_summary"]["average_test_return"],
            "walk_forward_test_sharpe": row["walk_forward_summary"]["average_test_sharpe"],
            "walk_forward_consistency": row["walk_forward_summary"]["test_consistency"],
            "max_drawdown": row["metrics"]["max_drawdown"],
            "trades_count": row["trades_count"],
            "symbols_tested": row["symbols_tested"],
        }
        for rank, row in enumerate(ranked[:20])
    ]
    return {
        "candidate": {
            "id": candidate["id"],
            "candidate_key": candidate.get("candidate_key"),
            "name": candidate.get("name"),
            "activation_gate": candidate.get("activation_gate"),
        },
        "status": "completed" if ranked else "insufficient_data",
        "template": template,
        "timeframe": timeframe,
        "parameter_space": grid,
        "best_params": best["params"],
        "metrics": {
            "best_score": best["score"],
            "best_total_return": best["metrics"]["total_return"],
            "best_test_total_return": best["test_metrics"]["total_return"],
            "best_test_sharpe": best["test_metrics"]["sharpe_estimate"],
            "best_walk_forward_test_return": best["walk_forward_summary"]["average_test_return"],
            "best_walk_forward_test_sharpe": best["walk_forward_summary"]["average_test_sharpe"],
            "best_walk_forward_consistency": best["walk_forward_summary"]["test_consistency"],
            "best_max_drawdown": best["metrics"]["max_drawdown"],
            "grid_size": len(grid),
            "trades_count": best["trades_count"],
            "symbols_tested": best["symbols_tested"],
            "bars_seen": len(bars),
            "walk_forward": {
                "method": "rolling chronological train/test windows",
                "folds": best["walk_forward_folds"],
                "summary": best["walk_forward_summary"],
            },
            "monte_carlo": monte_carlo_summary(best["returns"]),
        },
        "diagnostics": {
            "engine": "local_strategy_optimizer_v1",
            "data_source": "trading.ohlcv",
            "cost_bps": cost_bps,
            "slippage_bps": slippage_bps,
            "walk_forward_method": "rolling chronological train/test windows",
            "monte_carlo_method": "deterministic bootstrap of best parameter return stream",
            "paper_first": True,
            "live_execution_allowed": False,
            "warnings": warnings,
            "ranked_results": compact_results,
            "heatmap_rows": heatmap_rows,
        },
    }


def write_artifact(result: dict[str, Any]) -> Path:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_key = str(result["candidate"].get("candidate_key") or f"candidate_{result['candidate']['id']}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ARTIFACT_ROOT / f"{timestamp}-{candidate_key}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path = path.with_suffix(".md")
    metrics = result["metrics"]
    mc = metrics["monte_carlo"]
    md_path.write_text(
        "\n".join(
            [
                f"# Optimization - {result['candidate'].get('name')}",
                "",
                f"- Candidate: `{result['candidate'].get('candidate_key')}`",
                f"- Template: `{result['template']}`",
                f"- Status: `{result['status']}`",
                f"- Best params: `{json.dumps(result['best_params'], sort_keys=True)}`",
                f"- Best test Sharpe: {metrics['best_test_sharpe'] if metrics['best_test_sharpe'] is not None else 'n/a'}",
                f"- Best test return: {metrics['best_test_total_return']:.6f}",
                f"- Walk-forward folds: {metrics['walk_forward']['summary']['fold_count']}",
                f"- Walk-forward consistency: {metrics['best_walk_forward_consistency']:.2f}",
                f"- Monte Carlo p05 return: {mc['p05_total_return'] if mc['p05_total_return'] is not None else 'n/a'}",
                "",
                "## Warnings",
                "",
                *(f"- {warning}" for warning in result["diagnostics"]["warnings"]),
                "",
                "Optimization output remains research-only until Model Validation and human approval.",
            ]
        ),
        encoding="utf-8",
    )
    result["artifact_path"] = str(path.relative_to(RUNTIME_ROOT.parent))
    result["note_path"] = str(md_path.relative_to(RUNTIME_ROOT.parent))
    return path


def latest_backtest_id(candidate_id: int) -> int | None:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id
            FROM strategy.backtest_runs
            WHERE strategy_id = {candidate_id}
            ORDER BY finished_at DESC NULLS LAST, started_at DESC
            LIMIT 1
        ) rows
        """
    )
    return int(rows[0]["id"]) if rows else None


def persist_result(candidate: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    candidate_id = int(candidate["id"])
    backtest_id = latest_backtest_id(candidate_id)
    if backtest_id is None:
        raise ValueError("A baseline backtest is required before optimization can be persisted.")
    warnings = result["diagnostics"]["warnings"]
    sql = f"""
    WITH inserted_opt AS (
        INSERT INTO strategy.optimization_runs (
            strategy_id, backtest_run_id, run_name, optimizer_type, status,
            objective, parameter_space, constraints, metrics, diagnostics,
            artifact_path, owner_agent, evidence, started_at, finished_at
        )
        VALUES (
            {candidate_id},
            {backtest_id if backtest_id is not None else 'NULL'},
            {sql_literal('Local optimization - ' + str(candidate.get("name")))},
            'parameter_search_walk_forward_bootstrap',
            {sql_literal(result["status"])},
            'Maximize out-of-sample risk-adjusted return while preserving paper-first guardrails.',
            {sql_jsonb(result["parameter_space"])},
            {sql_jsonb({"paper_first": True, "live_execution_allowed": False})},
            {sql_jsonb(result["metrics"])},
            {sql_jsonb(result["diagnostics"])},
            {sql_literal(result.get("artifact_path"))},
            'Optimizer Agent',
            jsonb_build_array(jsonb_build_object('candidate_id', {candidate_id}), jsonb_build_object('artifact_path', {sql_literal(result.get("artifact_path"))})),
            now(),
            now()
        )
        RETURNING id
    ),
    review AS (
        INSERT INTO strategy.validation_reviews (
            strategy_id, backtest_run_id, optimization_run_id, reviewer_agent,
            review_status, decision, leakage_risk, overfit_risk,
            transaction_cost_notes, sample_size_notes, required_fixes, issues, evidence
        )
        SELECT
            {candidate_id},
            {backtest_id if backtest_id is not None else 'NULL'},
            id,
            'Model Validation Agent',
            'needs_review',
            'blocked_until_strategy_committee_review',
            'unchecked',
            CASE WHEN {sql_jsonb(warnings)}::jsonb <> '[]'::jsonb THEN 'high' ELSE 'medium' END,
            {sql_literal('Optimizer included transaction cost and slippage in every parameter run.')},
            {sql_literal('Walk-forward is a simple chronological split; broader historical data is required.')},
            ARRAY['Review optimizer selection bias','Run broader data sample','Run independent walk-forward windows','Review Monte Carlo/bootstrap tails','Approve or reject paper monitoring']::text[],
            {sql_jsonb([{"severity": "high", "issue": warning} for warning in warnings])},
            jsonb_build_array(jsonb_build_object('optimization_artifact', {sql_literal(result.get("artifact_path"))}))
        FROM inserted_opt
        RETURNING id
    ),
    inbox AS (
        INSERT INTO agent.inbox_items (
            title, owner_agent, status, priority, recommended_action, evidence, target_workspace
        )
        SELECT
            'Review optimization: ' || {sql_literal(candidate.get("name"))},
            'Strategy Committee Secretary',
            'needs_review',
            'high',
            'Prepare strategy committee memo from optimizer, walk-forward split, Monte Carlo/bootstrap, and validation warnings.',
            jsonb_build_array(
                jsonb_build_object('strategy_id', {candidate_id}),
                jsonb_build_object('optimization_run_id', inserted_opt.id),
                jsonb_build_object('artifact_path', {sql_literal(result.get("artifact_path"))})
            ),
            'quant'
        FROM inserted_opt
        RETURNING id
    )
    SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
    FROM (
        SELECT inserted_opt.id AS optimization_run_id,
               (SELECT id FROM review LIMIT 1) AS validation_review_id,
               (SELECT id FROM inbox LIMIT 1) AS inbox_id
        FROM inserted_opt
    ) rows;
    """
    rows = run_psql_json(sql)
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local parameter optimization and robustness diagnostics for a strategy candidate.")
    parser.add_argument("--candidate-id", type=int)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--timeframe", default="")
    parser.add_argument("--template", choices=["momentum", "mean_reversion", "breakout", "low_volatility"])
    parser.add_argument("--cost-bps", type=float, default=3.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--max-symbols", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidate = fetch_candidate(args.candidate_id)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    timeframe = normalize_timeframe(args.timeframe or str(candidate.get("timeframe") or ""))
    template = infer_template(candidate, args.template)
    result = optimize(candidate, symbols, timeframe, template, args.cost_bps, args.slippage_bps, args.max_symbols)
    write_artifact(result)
    result["database"] = {"dry_run": True} if args.dry_run else persist_result(candidate, result)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] in {"completed", "insufficient_data"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
