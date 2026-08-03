#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import time
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_storage import artifact_reference, artifact_root

from strategy_dsl_quality import parse_strategy_dsl, parse_symbols, run_data_quality_gate


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = artifact_root("backtests")


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    psql_bin = os.environ.get("AI_OS_PSQL_BIN") or "/opt/homebrew/opt/postgresql@15/bin/psql"
    password = os.environ.get("AI_OS_POSTGRES_PASSWORD")
    use_host_psql = bool(Path(psql_bin).exists() and password)
    if use_host_psql:
        command = [
            psql_bin,
            f"host={os.environ.get('AI_OS_POSTGRES_HOST') or '127.0.0.1'} "
            f"port={os.environ.get('AI_OS_POSTGRES_PORT') or '54329'} "
            f"dbname={os.environ.get('AI_OS_POSTGRES_DB') or 'ai_os'} "
            f"user={os.environ.get('AI_OS_POSTGRES_USER') or 'ai_os'} "
            "connect_timeout=3 options='-c statement_timeout=30000 -c lock_timeout=5000'",
            "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql,
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=35)
    else:
        command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"]
        completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, timeout=35)
    transient_markers = (
        "timeout expired",
        "connection refused",
        "connection reset",
        "server closed the connection unexpectedly",
        "the database system is starting up",
        "the database system is shutting down",
    )
    retry_delays = (0.5, 1.5)
    for delay in retry_delays:
        if completed.returncode == 0:
            break
        error_text = (completed.stderr or completed.stdout or "").strip()
        if not any(marker in error_text.lower() for marker in transient_markers):
            break
        time.sleep(delay)
        if use_host_psql:
            completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env, timeout=35)
        else:
            completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, timeout=35)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    output = completed.stdout.strip()
    return json.loads(output or "[]")


@dataclass
class Bar:
    ts: str
    symbol: str
    close: float


def fetch_candidate(candidate_id: int | None) -> dict[str, Any]:
    where = f"WHERE sc.id = {candidate_id}" if candidate_id else """
        WHERE sc.status IN ('research', 'candidate', 'imported')
          AND coalesce(sc.activation_gate, 'paper_first') <> 'live_approved'
    """
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT sc.id, coalesce(sc.candidate_key, 'candidate_' || sc.id::text) AS candidate_key,
                   sc.name, sc.hypothesis, sc.universe, sc.timeframe, sc.entry_rules,
                   sc.exit_rules, sc.risk_rules, sc.status, sc.validation_status,
                   sc.activation_gate, sc.structured_spec, sc.owner_agent
            FROM strategy.strategy_candidates sc
            {where}
            ORDER BY
                CASE WHEN sc.candidate_key IS NOT NULL THEN 1 ELSE 2 END,
                sc.created_at DESC,
                sc.id DESC
            LIMIT 1
        ) rows
        """
    )
    if not rows:
        raise ValueError("No strategy candidate found for backtest")
    return rows[0]


def normalize_timeframe(value: str | None) -> str:
    value = (value or "").lower()
    if "5" in value or "intraday" in value:
        return "5m"
    if "15" in value:
        return "15m"
    if "hour" in value or "1h" in value:
        return "1h"
    if "day" in value or "daily" in value or "1d" in value:
        return "1d"
    return "5m"


def infer_template(candidate: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ["name", "hypothesis", "universe", "entry_rules", "structured_spec"]
    ).lower()
    if "mean" in text or "reversion" in text or "zscore" in text:
        return "mean_reversion"
    if "low_vol" in text or "low vol" in text or "volatility" in text:
        return "low_volatility"
    if "breakout" in text or "atr" in text:
        return "breakout"
    return "momentum"


def fetch_bars(symbols: list[str], timeframe: str, max_symbols: int) -> list[Bar]:
    symbol_filter = ""
    if symbols:
        cleaned = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        variants = sorted(set(cleaned + [f"NSE:{symbol}" for symbol in cleaned if ":" not in symbol]))
        symbol_filter = f"AND upper(s.symbol) = ANY(ARRAY[{','.join(sql_literal(v) for v in variants)}]::text[])"
    rows = run_psql_json(
        f"""
        WITH ranked_symbols AS (
            SELECT s.id, s.symbol, count(*) AS rows_seen
            FROM trading.ohlcv o
            JOIN trading.symbols s ON s.id = o.symbol_id
            WHERE o.timeframe = {sql_literal(timeframe)}
              AND o.close IS NOT NULL
              {symbol_filter}
            GROUP BY s.id, s.symbol
            ORDER BY rows_seen DESC, s.symbol
            LIMIT {max(1, max_symbols)}
        )
        SELECT coalesce(json_agg(row_to_json(rows) ORDER BY rows.symbol, rows.ts), '[]'::json)::text
        FROM (
            SELECT o.ts::text AS ts, rs.symbol, o.close::float8 AS close
            FROM trading.ohlcv o
            JOIN ranked_symbols rs ON rs.id = o.symbol_id
            WHERE o.timeframe = {sql_literal(timeframe)}
              AND o.close IS NOT NULL
        ) rows
        """
    )
    return [Bar(ts=str(row["ts"]), symbol=str(row["symbol"]), close=float(row["close"])) for row in rows]


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
        else:
            output.append(sum(values[index + 1 - window:index + 1]) / window)
    return output


def rolling_stdev(values: list[float], window: int) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            output.append(None)
        else:
            sample = values[index + 1 - window:index + 1]
            output.append(statistics.pstdev(sample) or None)
    return output


def positions_for_template(closes: list[float], template: str) -> list[int]:
    if template == "mean_reversion":
        mean = rolling_mean(closes, 20)
        stdev = rolling_stdev(closes, 20)
        return [
            1 if mean[index] is not None and stdev[index] and (closes[index] - float(mean[index])) / float(stdev[index]) < -1.0 else 0
            for index in range(len(closes))
        ]
    if template == "breakout":
        high = rolling_mean(closes, 12)
        return [1 if high[index] is not None and closes[index] > float(high[index]) * 1.002 else 0 for index in range(len(closes))]
    if template == "low_volatility":
        volatility = rolling_stdev([0.0] + [(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes))], 12)
        valid_vols = [float(value) for value in volatility if value is not None]
        threshold = statistics.median(valid_vols) if valid_vols else None
        return [1 if threshold is not None and volatility[index] is not None and float(volatility[index]) <= threshold else 0 for index in range(len(closes))]
    lookback = 12
    return [1 if index >= lookback and closes[index] > closes[index - lookback] else 0 for index in range(len(closes))]


def max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 1.0
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = value / peak - 1.0 if peak else 0.0
        worst = min(worst, drawdown)
    return worst


def periods_per_year(timeframe: str) -> float:
    return {
        "5m": 252 * 75,
        "15m": 252 * 25,
        "1h": 252 * 6,
        "1d": 252,
    }.get(timeframe, 252)


def run_backtest(candidate: dict[str, Any], symbols: list[str], timeframe: str, template: str, cost_bps: float, slippage_bps: float, max_symbols: int) -> dict[str, Any]:
    bars = fetch_bars(symbols, timeframe, max_symbols)
    by_symbol: dict[str, list[Bar]] = {}
    for bar in bars:
        by_symbol.setdefault(bar.symbol, []).append(bar)

    all_returns: list[float] = []
    returns_by_ts: dict[str, list[float]] = {}
    trade_count = 0
    symbol_results: list[dict[str, Any]] = []
    total_cost = (cost_bps + slippage_bps) / 10000.0

    for symbol, symbol_bars in sorted(by_symbol.items()):
        closes = [bar.close for bar in symbol_bars]
        if len(closes) < 20:
            symbol_results.append({"symbol": symbol, "bars": len(closes), "status": "insufficient_bars"})
            continue
        positions = positions_for_template(closes, template)
        returns: list[float] = []
        equity = [1.0]
        for index in range(1, len(closes)):
            raw_return = closes[index] / closes[index - 1] - 1.0
            turnover = abs(positions[index] - positions[index - 1])
            if turnover:
                trade_count += 1
            net_return = positions[index - 1] * raw_return - turnover * total_cost
            returns.append(net_return)
            returns_by_ts.setdefault(symbol_bars[index].ts, []).append(net_return)
            equity.append(equity[-1] * (1.0 + net_return))
        symbol_results.append(
            {
                "symbol": symbol,
                "bars": len(closes),
                "position_bars": sum(positions),
                "trades": sum(abs(positions[index] - positions[index - 1]) for index in range(1, len(positions))),
                "total_return": equity[-1] - 1.0,
                "max_drawdown": max_drawdown(equity),
                "first_ts": symbol_bars[0].ts,
                "last_ts": symbol_bars[-1].ts,
                "status": "tested",
            }
        )

    portfolio_returns = [
        (ts, statistics.mean(values))
        for ts, values in sorted(returns_by_ts.items())
        if values
    ]
    all_returns = [value for _, value in portfolio_returns]
    equity = [1.0]
    equity_curve: list[dict[str, Any]] = []
    for ts, value in portfolio_returns:
        equity.append(equity[-1] * (1.0 + value))
        equity_curve.append({"ts": ts, "equity": equity[-1], "return": value})

    if all_returns:
        average = statistics.mean(all_returns)
        stdev = statistics.pstdev(all_returns)
        sharpe = average / stdev * math.sqrt(periods_per_year(timeframe)) if stdev else None
        total_return = equity[-1] - 1.0
        win_rate = sum(1 for value in all_returns if value > 0) / len(all_returns)
        status = "completed"
    else:
        average = 0.0
        stdev = 0.0
        sharpe = None
        total_return = 0.0
        win_rate = 0.0
        status = "insufficient_data"

    curve_points_total = len(equity_curve)
    if curve_points_total > 500:
        step = math.ceil(curve_points_total / 499)
        sampled_curve = equity_curve[::step]
        if sampled_curve[-1] != equity_curve[-1]:
            sampled_curve.append(equity_curve[-1])
        equity_curve = sampled_curve

    bars_tested = sum(item["bars"] for item in symbol_results)
    warnings = []
    if bars_tested < 500:
        warnings.append("Dataset is thin; result is a pipeline proof, not a tradable conclusion.")
    if len(by_symbol) < 3:
        warnings.append("Symbol coverage is narrow; run broader universe data before committee review.")
    if status != "completed":
        warnings.append("No valid return stream was produced.")

    tested_results = [item for item in symbol_results if item.get("status") == "tested"]
    data_start = min((str(item["first_ts"])[:10] for item in tested_results), default=None)
    data_end = max((str(item["last_ts"])[:10] for item in tested_results), default=None)

    return {
        "candidate": {
            "id": candidate["id"],
            "candidate_key": candidate.get("candidate_key"),
            "name": candidate.get("name"),
            "activation_gate": candidate.get("activation_gate"),
        },
        "status": status,
        "template": template,
        "timeframe": timeframe,
        "symbols_requested": symbols,
        "symbols_tested": sorted(by_symbol),
        "data_start": data_start,
        "data_end": data_end,
        "metrics": {
            "total_return": total_return,
            "average_bar_return": average,
            "bar_volatility": stdev,
            "sharpe_estimate": sharpe,
            "max_drawdown": max_drawdown(equity),
            "win_rate_by_bar": win_rate,
            "trades_count": trade_count,
            "bars_tested": bars_tested,
            "symbols_tested": len(by_symbol),
        },
        "diagnostics": {
            "engine": "local_deterministic_ohlcv_backtester_v1",
            "data_source": "trading.ohlcv",
            "cost_bps": cost_bps,
            "slippage_bps": slippage_bps,
            "paper_first": True,
            "live_execution_allowed": False,
            "equity_curve": equity_curve,
            "equity_curve_points_total": curve_points_total,
            "equity_curve_method": "equal_weight_mean_of_available_symbol_returns_by_timestamp",
            "equity_curve_source": "trading.ohlcv",
            "warnings": warnings,
            "symbol_results": symbol_results,
            "method": "Close-to-close long/flat signal simulation with transaction cost on position changes; portfolio returns are equal-weighted by timestamp across available symbols.",
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
    md_path.write_text(
        "\n".join(
            [
                f"# Backtest - {result['candidate'].get('name')}",
                "",
                f"- Candidate: `{result['candidate'].get('candidate_key')}`",
                f"- Template: `{result['template']}`",
                f"- Status: `{result['status']}`",
                f"- Timeframe: `{result['timeframe']}`",
                f"- Symbols tested: {', '.join(result['symbols_tested']) or 'none'}",
                f"- Total return: {metrics['total_return']:.6f}",
                f"- Max drawdown: {metrics['max_drawdown']:.6f}",
                f"- Sharpe estimate: {metrics['sharpe_estimate'] if metrics['sharpe_estimate'] is not None else 'n/a'}",
                f"- Trades: {metrics['trades_count']}",
                "",
                "## Warnings",
                "",
                *(f"- {warning}" for warning in result["diagnostics"]["warnings"]),
                "",
                "This artifact is generated from local warehouse data and does not authorize live execution.",
            ]
        ),
        encoding="utf-8",
    )
    result["artifact_path"] = artifact_reference(path)
    result["note_path"] = artifact_reference(md_path)
    return path


def persist_result(candidate: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    artifact_path = result.get("artifact_path")
    metrics = result["metrics"]
    diagnostics = result["diagnostics"]
    run_status = result["status"]
    sql = f"""
    WITH inserted_run AS (
        INSERT INTO strategy.backtest_runs (
            strategy_id, run_status, data_start, data_end, universe, timeframe,
            metrics, diagnostics, artifact_path, started_at, finished_at, external_ref
        )
        VALUES (
            {int(candidate["id"])},
            {sql_literal(run_status)},
            {sql_literal(result.get("data_start"))}::date,
            {sql_literal(result.get("data_end"))}::date,
            {sql_literal(candidate.get("universe"))},
            {sql_literal(result["timeframe"])},
            {sql_jsonb(metrics)},
            {sql_jsonb(diagnostics)},
            {sql_literal(artifact_path)},
            now(),
            now(),
            {sql_literal('local_backtest:' + datetime.now(timezone.utc).isoformat())}
        )
        RETURNING id
    ),
    review AS (
        INSERT INTO strategy.validation_reviews (
            strategy_id, backtest_run_id, reviewer_agent, review_status, decision,
            leakage_risk, overfit_risk, transaction_cost_notes, sample_size_notes,
            required_fixes, issues, evidence
        )
        SELECT
            {int(candidate["id"])},
            id,
            'Model Validation Agent',
            'needs_review',
            'blocked_until_human_and_model_validation',
            'unchecked',
            CASE WHEN {int(metrics["bars_tested"])} < 500 THEN 'high' ELSE 'medium' END,
            {sql_literal(f"Cost {diagnostics['cost_bps']} bps and slippage {diagnostics['slippage_bps']} bps included on position changes.")},
            {sql_literal('Bars tested: ' + str(metrics["bars_tested"]) + '. Broader sample required before paper activation.')},
            ARRAY['Review data lineage','Run broader sample','Run walk-forward','Run Monte Carlo/bootstrap','Review slippage and capacity']::text[],
            {sql_jsonb([{"severity": "high", "issue": warning} for warning in diagnostics["warnings"]])},
            jsonb_build_array(jsonb_build_object('artifact_path', {sql_literal(artifact_path)}))
        FROM inserted_run
        RETURNING id
    ),
    task_update AS (
        UPDATE agent.tasks
        SET status = 'needs_review', updated_at = now()
        WHERE source_kind = 'strategy.strategy_candidates'
          AND source_ref = {sql_literal(str(candidate["id"]))}
          AND owner_agent = 'Backtest Engineer'
        RETURNING id
    ),
    validation_inbox AS (
        INSERT INTO agent.inbox_items (
            title, owner_agent, status, priority, recommended_action, evidence, target_workspace
        )
        SELECT
            'Validate backtest: ' || {sql_literal(candidate.get("name"))},
            'Model Validation Agent',
            'needs_review',
            'high',
            'Review local backtest diagnostics, data lineage, costs, and sample-size warnings before any paper alert.',
            jsonb_build_array(
                jsonb_build_object('strategy_id', {int(candidate["id"])}),
                jsonb_build_object('backtest_run_id', inserted_run.id),
                jsonb_build_object('artifact_path', {sql_literal(artifact_path)})
            ),
            'quant'
        FROM inserted_run
        RETURNING id
    )
    SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
    FROM (
        SELECT inserted_run.id AS backtest_run_id,
               (SELECT id FROM review LIMIT 1) AS validation_review_id,
               (SELECT count(*) FROM task_update) AS updated_tasks,
               (SELECT id FROM validation_inbox LIMIT 1) AS inbox_id
        FROM inserted_run
    ) rows;
    """
    rows = run_psql_json(sql)
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local OHLCV backtest for a strategy candidate.")
    parser.add_argument("--candidate-id", type=int)
    parser.add_argument("--symbols", default="", help="Comma-separated symbols. Defaults to available OHLCV universe.")
    parser.add_argument("--timeframe", default="")
    parser.add_argument("--template", choices=["momentum", "mean_reversion", "breakout", "low_volatility"])
    parser.add_argument("--cost-bps", type=float, default=3.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--max-symbols", type=int, default=14)
    parser.add_argument("--min-rows-per-symbol", type=int, default=50)
    parser.add_argument("--min-total-rows", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidate = fetch_candidate(args.candidate_id)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    timeframe = normalize_timeframe(args.timeframe or str(candidate.get("timeframe") or ""))
    template = infer_template(candidate, args.template)
    parse_result = parse_strategy_dsl(int(candidate["id"]), created_by="Backtest Engineer")
    gate = run_data_quality_gate(
        int(candidate["id"]),
        symbols=symbols or parse_symbols(parse_result.get("symbols")),
        timeframe=timeframe,
        min_rows_per_symbol=args.min_rows_per_symbol,
        min_total_rows=args.min_total_rows,
        created_by="Backtest Engineer",
    )
    if gate.get("status") != "passed":
        print(
            json.dumps(
                {
                    "candidate": {
                        "id": candidate["id"],
                        "candidate_key": candidate.get("candidate_key"),
                        "name": candidate.get("name"),
                    },
                    "status": "blocked_data_quality",
                    "parse": parse_result,
                    "data_quality_gate": gate,
                    "message": "Backtest blocked before execution because the real OHLCV preflight gate failed.",
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 2
    result = run_backtest(candidate, symbols, timeframe, template, args.cost_bps, args.slippage_bps, args.max_symbols)
    result["parse"] = parse_result
    result["data_quality_gate"] = gate
    result["diagnostics"]["data_quality_gate_id"] = gate.get("id")
    result["diagnostics"]["data_quality_gate_key"] = gate.get("gate_key")
    result["diagnostics"]["data_quality_status"] = gate.get("status")
    write_artifact(result)
    if not args.dry_run:
        result["database"] = persist_result(candidate, result)
    else:
        result["database"] = {"dry_run": True}
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] in {"completed", "insufficient_data"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
