#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from runtime_storage import artifact_reference, artifact_root


ARTIFACT_ROOT = artifact_root("portfolio_risk")
BENCHMARK_SYMBOL = "NIFTY 50"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
        "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def psql_exec(sql: str) -> str:
    command = [
        "docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A",
        "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os",
    ]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def number(value: object, fallback: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else fallback
    except (TypeError, ValueError):
        return fallback


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def loss_tail(returns: list[float], confidence: float) -> tuple[float, float]:
    losses = [-item for item in returns]
    var = max(0.0, percentile(losses, confidence))
    tail = [item for item in losses if item >= var]
    return var, statistics.mean(tail) if tail else var


def annualized_volatility(returns: list[float]) -> float:
    return statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0


def maximum_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for item in returns:
        equity *= max(0.000001, 1.0 + item)
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return abs(worst)


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 20 or len(left) != len(right):
        return None
    left_std = statistics.pstdev(left)
    right_std = statistics.pstdev(right)
    if not left_std or not right_std:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / len(left)
    return covariance / (left_std * right_std)


def beta(left: list[float], right: list[float]) -> float | None:
    if len(left) < 20 or len(left) != len(right):
        return None
    variance = statistics.pvariance(right)
    if not variance:
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right)) / len(left)
    return covariance / variance


def fetch_positions() -> list[dict[str, Any]]:
    return run_psql_json(
        """
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, client_id, client_code, client_name, account_id, account_code,
                   symbol, exchange, instrument_type, book_key, book_name, direction,
                   quantity, market_price, market_value, gross_exposure, net_exposure,
                   as_of, evidence
            FROM books.v_book_positions
            WHERE status = 'active'
              AND coalesce(gross_exposure, 0) > 0
            ORDER BY client_code, book_key, symbol, id
        ) rows
        """
    )


def fetch_market_rows(symbols: list[str], lookback_days: int) -> list[dict[str, Any]]:
    values = ",".join(sql_literal(item) for item in sorted(set(symbols + [BENCHMARK_SYMBOL])))
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT symbol, trading_date, close, volume, ts
            FROM (
                SELECT upper(source.symbol) AS symbol,
                       ohlcv.ts::date AS trading_date,
                       ohlcv.close,
                       ohlcv.volume,
                       ohlcv.ts,
                       row_number() OVER (PARTITION BY upper(source.symbol) ORDER BY ohlcv.ts DESC) AS row_rank
                FROM trading.ohlcv ohlcv
                JOIN trading.symbols source ON source.id = ohlcv.symbol_id
                WHERE ohlcv.timeframe = '1d'
                  AND upper(source.symbol) IN ({values})
                  AND ohlcv.close > 0
            ) ranked
            WHERE row_rank <= {max(120, int(lookback_days) + 65)}
            ORDER BY symbol, trading_date
        ) rows
        """
    )


def build_market_series(rows: list[dict[str, Any]], lookback_days: int) -> tuple[dict[str, dict[str, float]], dict[str, list[tuple[str, float, float]]], dict[str, int]]:
    bars: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        close = number(row.get("close"))
        if not symbol or close <= 0:
            continue
        bars[symbol].append((str(row.get("trading_date")), close, max(0.0, number(row.get("volume")))))

    returns: dict[str, dict[str, float]] = {}
    filtered_counts: dict[str, int] = {}
    for symbol, symbol_bars in bars.items():
        symbol_bars.sort(key=lambda item: item[0])
        values: dict[str, float] = {}
        filtered = 0
        for index in range(1, len(symbol_bars)):
            previous = symbol_bars[index - 1][1]
            current = symbol_bars[index][1]
            item = current / previous - 1.0
            if not math.isfinite(item) or abs(item) > 0.50:
                filtered += 1
                continue
            values[symbol_bars[index][0]] = item
        returns[symbol] = dict(list(sorted(values.items()))[-lookback_days:])
        filtered_counts[symbol] = filtered
    return returns, bars, filtered_counts


def scope_rows(positions: list[dict[str, Any]]) -> list[tuple[str, str, str, list[dict[str, Any]]]]:
    output: list[tuple[str, str, str, list[dict[str, Any]]]] = [("portfolio", "all", "All Portfolios", positions)]
    books: dict[str, list[dict[str, Any]]] = defaultdict(list)
    clients: dict[str, list[dict[str, Any]]] = defaultdict(list)
    client_names: dict[str, str] = {}
    for row in positions:
        book_key = str(row.get("book_key") or "unassigned")
        books[book_key].append(row)
        client_ref = str(row.get("client_code") or row.get("client_id") or "unassigned")
        clients[client_ref].append(row)
        client_names[client_ref] = str(row.get("client_name") or client_ref)
    for key, rows in sorted(books.items()):
        output.append(("book", key, str(rows[0].get("book_name") or key), rows))
    for key, rows in sorted(clients.items()):
        output.append(("client", key, client_names[key], rows))
    return output


def aggregate_exposures(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = defaultdict(lambda: {"gross": 0.0, "net": 0.0})
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        output[symbol]["gross"] += abs(number(row.get("gross_exposure"), abs(number(row.get("market_value")))))
        output[symbol]["net"] += number(row.get("net_exposure"), number(row.get("market_value")))
    return dict(output)


def portfolio_returns(
    exposures: dict[str, dict[str, float]],
    series: dict[str, dict[str, float]],
    gross: float,
) -> tuple[dict[str, float], float, float, list[str], list[str]]:
    covered = [symbol for symbol in exposures if series.get(symbol)]
    uncovered = [symbol for symbol in exposures if not series.get(symbol)]
    covered_exposure = sum(exposures[symbol]["gross"] for symbol in covered)
    dates = sorted({day for symbol in covered for day in series[symbol]})
    output: dict[str, float] = {}
    for day in dates:
        available = sum(exposures[symbol]["gross"] for symbol in covered if day in series[symbol])
        if not covered_exposure or available / covered_exposure < 0.90:
            continue
        output[day] = sum((exposures[symbol]["net"] / gross) * series[symbol][day] for symbol in covered if day in series[symbol])
    return output, covered_exposure, gross - covered_exposure, covered, uncovered


def bootstrap_paths(
    returns_by_day: dict[str, float],
    benchmark: dict[str, float],
    uncovered_share: float,
    uncovered_shock: float,
    simulations: int,
    seed: int,
) -> tuple[list[float], list[float]]:
    common = [(value, benchmark.get(day, 0.0)) for day, value in sorted(returns_by_day.items())]
    if not common:
        return [], []
    rng = random.Random(seed)

    def draw_day() -> float:
        covered_return, benchmark_return = common[rng.randrange(len(common))]
        proxy = uncovered_share * 1.25 * benchmark_return
        gap = -uncovered_share * uncovered_shock if rng.random() < 0.01 else 0.0
        return max(-0.95, covered_return + proxy + gap)

    one_day = [draw_day() for _ in range(simulations)]
    ten_day: list[float] = []
    for _ in range(simulations):
        compounded = 1.0
        for _day in range(10):
            compounded *= 1.0 + draw_day()
        ten_day.append(compounded - 1.0)
    return one_day, ten_day


def liquidity_rows(
    scope_type: str,
    scope_ref: str,
    exposures: dict[str, dict[str, float]],
    bars: dict[str, list[tuple[str, float, float]]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for symbol, exposure in sorted(exposures.items(), key=lambda item: item[1]["gross"], reverse=True):
        recent = bars.get(symbol, [])[-60:]
        traded_values = [close * volume for _day, close, volume in recent if close > 0 and volume > 0]
        median_value = statistics.median(traded_values) if traded_values else None
        median_volume = statistics.median([volume for _day, _close, volume in recent if volume > 0]) if traded_values else None
        days = exposure["gross"] / (median_value * 0.10) if median_value and median_value > 0 else None
        if days is None:
            bucket = "unavailable"
            status = "insufficient"
            warnings = ["No usable daily traded-volume history for this symbol."]
        elif days <= 1:
            bucket, status, warnings = "same_day", "complete", []
        elif days <= 3:
            bucket, status, warnings = "one_to_three_days", "complete", []
        elif days <= 10:
            bucket, status, warnings = "four_to_ten_days", "provisional", ["Position needs more than three sessions at 10% median daily traded value."]
        else:
            bucket, status, warnings = "over_ten_days", "provisional", ["Position needs more than ten sessions at 10% median daily traded value."]
        output.append({
            "scope_type": scope_type,
            "scope_ref": scope_ref,
            "symbol": symbol,
            "gross_exposure": exposure["gross"],
            "latest_close": recent[-1][1] if recent else None,
            "median_daily_volume": median_volume,
            "median_daily_traded_value": median_value,
            "days": days,
            "bucket": bucket,
            "observations": len(traded_values),
            "market_data_as_of": recent[-1][0] if recent else None,
            "status": status,
            "warnings": warnings,
        })
    return output


def calculate_scope(
    scope_type: str,
    scope_ref: str,
    scope_name: str,
    rows: list[dict[str, Any]],
    series: dict[str, dict[str, float]],
    bars: dict[str, list[tuple[str, float, float]]],
    benchmark: dict[str, float],
    all_abs_returns: list[float],
    simulations: int,
    seed: int,
    market_data_as_of: str | None,
    position_as_of: str | None,
) -> dict[str, Any]:
    exposures = aggregate_exposures(rows)
    gross = sum(item["gross"] for item in exposures.values())
    net = sum(item["net"] for item in exposures.values())
    returns_by_day, covered, uncovered, covered_symbols, uncovered_symbols = portfolio_returns(exposures, series, gross)
    returns = [value for _day, value in sorted(returns_by_day.items())]
    coverage = covered / gross if gross else 0.0
    uncovered_share = uncovered / gross if gross else 0.0
    uncovered_shock = min(0.10, max(0.03, percentile(all_abs_returns, 0.99))) if all_abs_returns else 0.05
    hist_var95, hist_es95 = loss_tail(returns, 0.95)
    hist_var99, hist_es99 = loss_tail(returns, 0.99)
    adjusted_var99 = hist_var99 + uncovered_share * uncovered_shock
    one_day, ten_day = bootstrap_paths(returns_by_day, benchmark, uncovered_share, uncovered_shock, simulations, seed)
    boot_var1, boot_es1 = loss_tail(one_day, 0.99)
    boot_var10, boot_es10 = loss_tail(ten_day, 0.99)

    common_dates = [day for day in returns_by_day if day in benchmark]
    portfolio_common = [returns_by_day[day] for day in common_dates]
    benchmark_common = [benchmark[day] for day in common_dates]
    beta_value = beta(portfolio_common, benchmark_common)
    correlation_value = correlation(portfolio_common, benchmark_common)
    r_squared = correlation_value ** 2 if correlation_value is not None else None
    residual = []
    if beta_value is not None:
        residual = [portfolio_common[index] - beta_value * benchmark_common[index] for index in range(len(common_dates))]

    weights = sorted((item["gross"] / gross for item in exposures.values()), reverse=True) if gross else []
    hhi = sum(item * item for item in weights)
    top5 = sum(weights[:5])
    freshness_days = None
    if market_data_as_of and position_as_of:
        try:
            freshness_days = abs((date.fromisoformat(position_as_of[:10]) - date.fromisoformat(market_data_as_of[:10])).days)
        except ValueError:
            freshness_days = None

    warnings: list[str] = []
    status = "complete"
    if coverage < 0.95:
        status = "provisional"
        warnings.append(f"Only {coverage:.1%} of gross exposure has usable daily history; uncovered risk is proxy-modeled and separately disclosed.")
    if len(returns) < 250:
        status = "insufficient" if len(returns) < 60 else "provisional"
        warnings.append(f"Only {len(returns)} aligned return observations are available.")
    if freshness_days is not None and freshness_days > 5:
        status = "provisional" if status == "complete" else status
        warnings.append(f"Position and market-history as-of dates differ by {freshness_days} days.")

    liquidity = liquidity_rows(scope_type, scope_ref, exposures, bars)
    unavailable_liquidity = sum(item["gross_exposure"] for item in liquidity if item["bucket"] == "unavailable")
    slow_liquidity = sum(item["gross_exposure"] for item in liquidity if item["bucket"] in {"four_to_ten_days", "over_ten_days"})

    market_beta_for_stress = beta_value if beta_value is not None else 1.0
    worst_return = min(returns) if returns else 0.0
    top_three = sum(item["gross"] for _symbol, item in sorted(exposures.items(), key=lambda pair: pair[1]["gross"], reverse=True)[:3])
    stress = [
        ("market_down_5", -(covered * market_beta_for_stress * 0.05 + uncovered * 0.05), {"market_beta": market_beta_for_stress}),
        ("market_down_10", -(covered * market_beta_for_stress * 0.10 + uncovered * 0.10), {"market_beta": market_beta_for_stress}),
        ("top_three_down_20", -(top_three * 0.20), {"top_three_exposure": top_three}),
        ("liquidity_gap", -(unavailable_liquidity * 0.15 + slow_liquidity * 0.15 + max(0.0, gross - unavailable_liquidity - slow_liquidity) * 0.05), {"unavailable_exposure": unavailable_liquidity, "slow_exposure": slow_liquidity}),
        ("historical_worst_day", gross * worst_return - uncovered * uncovered_shock, {"worst_covered_return": worst_return, "uncovered_shock": uncovered_shock}),
    ]
    stress_rows = []
    for scenario_key, pnl, assumption in stress:
        return_pct = pnl / gross if gross else 0.0
        stress_rows.append({
            "scope_type": scope_type, "scope_ref": scope_ref, "scenario_key": scenario_key,
            "pnl": pnl, "return_pct": return_pct, "covered_loss": min(0.0, pnl + uncovered * uncovered_shock),
            "uncovered_loss": -uncovered * uncovered_shock if uncovered else 0.0,
            "severity": "critical" if return_pct <= -0.15 else "high" if return_pct <= -0.10 else "medium",
            "status": status, "assumptions": assumption,
        })

    factors = [
        {"key": "market_beta", "name": "NIFTY 50 Market Beta", "value": beta_value, "contribution": (r_squared or 0.0) * 100, "method": "OLS beta on aligned daily returns"},
        {"key": "residual_risk", "name": "Residual Annualized Volatility", "value": annualized_volatility(residual) * 100 if residual else None, "contribution": (1.0 - (r_squared or 0.0)) * 100 if r_squared is not None else None, "method": "Portfolio return minus beta times NIFTY 50 return"},
        {"key": "concentration_hhi", "name": "Position Concentration HHI", "value": hhi, "contribution": top5 * 100, "method": "Current gross-exposure weights"},
        {"key": "missing_history", "name": "Missing Historical Coverage", "value": uncovered_share * 100, "contribution": uncovered_share * 100, "method": "Current gross exposure without usable daily history"},
        {"key": "liquidity_unavailable", "name": "Unavailable Liquidity Coverage", "value": unavailable_liquidity, "contribution": unavailable_liquidity / gross * 100 if gross else 0.0, "method": "No usable 60-session traded-value history"},
    ]

    metrics = {
        "scope_type": scope_type, "scope_ref": scope_ref, "scope_name": scope_name, "status": status,
        "gross": gross, "net": net, "covered": covered, "uncovered": uncovered, "coverage": coverage,
        "observations": len(returns), "annual_vol": annualized_volatility(returns),
        "hist_var95": hist_var95, "hist_es95": hist_es95, "hist_var99": hist_var99, "hist_es99": hist_es99,
        "adjusted_var99": adjusted_var99, "boot_var1": boot_var1, "boot_es1": boot_es1,
        "boot_var10": boot_var10, "boot_es10": boot_es10,
        "prob_loss5_10d": sum(value <= -0.05 for value in ten_day) / len(ten_day) if ten_day else 0.0,
        "prob_loss10_10d": sum(value <= -0.10 for value in ten_day) / len(ten_day) if ten_day else 0.0,
        "max_drawdown": maximum_drawdown(returns), "beta": beta_value, "correlation": correlation_value,
        "r_squared": r_squared, "residual_vol": annualized_volatility(residual) if residual else None,
        "hhi": hhi, "top5": top5, "largest": weights[0] if weights else 0.0,
        "freshness_days": freshness_days, "uncovered_shock": uncovered_shock, "warnings": warnings,
        "evidence": [{"covered_symbols": covered_symbols}, {"uncovered_symbols": uncovered_symbols}, {"benchmark": BENCHMARK_SYMBOL}],
    }
    return {"metrics": metrics, "stress": stress_rows, "liquidity": liquidity, "factors": factors}


def optional_numeric(value: float | int | None, multiplier: float = 1.0) -> str:
    if value is None or not math.isfinite(float(value)):
        return "NULL"
    return str(round(float(value) * multiplier, 8))


def persist_results(run_id: int, results: list[dict[str, Any]]) -> None:
    statements = ["BEGIN;"]
    for result in results:
        metric = result["metrics"]
        gross = metric["gross"]
        statements.append(
            f"""
            INSERT INTO risk.portfolio_risk_metrics (
                run_id, scope_type, scope_ref, scope_name, calculation_status,
                gross_exposure, net_exposure, covered_exposure, uncovered_exposure, coverage_pct,
                observation_count, annualized_volatility_pct,
                historical_var_95_pct, historical_var_95_value, historical_es_95_pct, historical_es_95_value,
                historical_var_99_pct, historical_var_99_value, historical_es_99_pct, historical_es_99_value,
                coverage_adjusted_var_99_pct, coverage_adjusted_var_99_value,
                bootstrap_var_99_1d_pct, bootstrap_var_99_1d_value, bootstrap_es_99_1d_pct, bootstrap_es_99_1d_value,
                bootstrap_var_99_10d_pct, bootstrap_var_99_10d_value, bootstrap_es_99_10d_pct, bootstrap_es_99_10d_value,
                probability_loss_5pct_10d, probability_loss_10pct_10d, maximum_drawdown_pct,
                market_beta, market_correlation, market_r_squared, residual_volatility_pct,
                concentration_hhi, top_5_exposure_pct, largest_position_pct, data_freshness_days,
                uncovered_shock_assumption_pct, warnings, evidence
            ) VALUES (
                {run_id}, {sql_literal(metric['scope_type'])}, {sql_literal(metric['scope_ref'])}, {sql_literal(metric['scope_name'])}, {sql_literal(metric['status'])},
                {gross}, {metric['net']}, {metric['covered']}, {metric['uncovered']}, {optional_numeric(metric['coverage'], 100)},
                {metric['observations']}, {optional_numeric(metric['annual_vol'], 100)},
                {optional_numeric(metric['hist_var95'], 100)}, {metric['hist_var95'] * gross}, {optional_numeric(metric['hist_es95'], 100)}, {metric['hist_es95'] * gross},
                {optional_numeric(metric['hist_var99'], 100)}, {metric['hist_var99'] * gross}, {optional_numeric(metric['hist_es99'], 100)}, {metric['hist_es99'] * gross},
                {optional_numeric(metric['adjusted_var99'], 100)}, {metric['adjusted_var99'] * gross},
                {optional_numeric(metric['boot_var1'], 100)}, {metric['boot_var1'] * gross}, {optional_numeric(metric['boot_es1'], 100)}, {metric['boot_es1'] * gross},
                {optional_numeric(metric['boot_var10'], 100)}, {metric['boot_var10'] * gross}, {optional_numeric(metric['boot_es10'], 100)}, {metric['boot_es10'] * gross},
                {optional_numeric(metric['prob_loss5_10d'], 100)}, {optional_numeric(metric['prob_loss10_10d'], 100)}, {optional_numeric(metric['max_drawdown'], 100)},
                {optional_numeric(metric['beta'])}, {optional_numeric(metric['correlation'])}, {optional_numeric(metric['r_squared'])}, {optional_numeric(metric['residual_vol'], 100)},
                {optional_numeric(metric['hhi'])}, {optional_numeric(metric['top5'], 100)}, {optional_numeric(metric['largest'], 100)}, {optional_numeric(metric['freshness_days'])},
                {optional_numeric(metric['uncovered_shock'], 100)}, {sql_jsonb(metric['warnings'])}, {sql_jsonb(metric['evidence'])}
            );
            """
        )
        for row in result["stress"]:
            statements.append(
                f"""
                INSERT INTO risk.portfolio_stress_results (
                    run_id, scope_type, scope_ref, scenario_key, stressed_pnl_value, stressed_return_pct,
                    covered_loss_value, uncovered_loss_value, severity, calculation_status, assumptions, evidence
                ) VALUES (
                    {run_id}, {sql_literal(row['scope_type'])}, {sql_literal(row['scope_ref'])}, {sql_literal(row['scenario_key'])},
                    {row['pnl']}, {row['return_pct'] * 100}, {row['covered_loss']}, {row['uncovered_loss']},
                    {sql_literal(row['severity'])}, {sql_literal(row['status'])}, {sql_jsonb(row['assumptions'])},
                    {sql_jsonb([{'source': 'run_portfolio_risk_engine.py'}])}
                );
                """
            )
        for row in result["liquidity"]:
            statements.append(
                f"""
                INSERT INTO risk.position_liquidity_assessments (
                    run_id, scope_type, scope_ref, symbol, gross_exposure, latest_close,
                    median_daily_volume, median_daily_traded_value, participation_rate_pct,
                    estimated_days_to_liquidate, liquidity_bucket, market_data_observations,
                    market_data_as_of, calculation_status, warnings, evidence
                ) VALUES (
                    {run_id}, {sql_literal(row['scope_type'])}, {sql_literal(row['scope_ref'])}, {sql_literal(row['symbol'])},
                    {row['gross_exposure']}, {optional_numeric(row['latest_close'])}, {optional_numeric(row['median_daily_volume'])},
                    {optional_numeric(row['median_daily_traded_value'])}, 10, {optional_numeric(row['days'])},
                    {sql_literal(row['bucket'])}, {row['observations']}, {sql_literal(row['market_data_as_of'])}::date,
                    {sql_literal(row['status'])}, {sql_jsonb(row['warnings'])},
                    {sql_jsonb([{'source': 'trading.ohlcv'}, {'participation_rate_pct': 10}])}
                );
                """
            )
        for factor in result["factors"]:
            statements.append(
                f"""
                INSERT INTO risk.factor_risk_attribution (
                    run_id, scope_type, scope_ref, factor_key, factor_name, exposure_value,
                    contribution_pct, calculation_status, methodology, evidence
                ) VALUES (
                    {run_id}, {sql_literal(metric['scope_type'])}, {sql_literal(metric['scope_ref'])},
                    {sql_literal(factor['key'])}, {sql_literal(factor['name'])}, {optional_numeric(factor['value'])},
                    {optional_numeric(factor['contribution'])}, {sql_literal(metric['status'])}, {sql_literal(factor['method'])},
                    {sql_jsonb([{'benchmark': BENCHMARK_SYMBOL}, {'run_id': run_id}])}
                );
                """
            )
    statements.append("COMMIT;")
    psql_exec("\n".join(statements))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run institutional portfolio risk analytics from live positions and daily OHLCV.")
    parser.add_argument("--lookback-days", type=int, default=756)
    parser.add_argument("--simulations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument("--actor", default="Portfolio Risk Analyst")
    parser.add_argument("--run-key", default="")
    args = parser.parse_args()

    lookback = max(60, min(args.lookback_days, 4000))
    simulations = max(1000, min(args.simulations, 500000))
    now = datetime.now(timezone.utc)
    run_key = args.run_key.strip() or f"portfolio-risk-{now.strftime('%Y%m%dT%H%M%SZ')}"
    run_id: int | None = None
    try:
        positions = fetch_positions()
        if not positions:
            raise RuntimeError("No active book positions are available; risk run was not fabricated.")
        symbols = sorted({str(row.get("symbol") or "").upper() for row in positions if row.get("symbol")})
        market_rows = fetch_market_rows(symbols, lookback)
        series, bars, filtered_counts = build_market_series(market_rows, lookback)
        benchmark = series.get(BENCHMARK_SYMBOL, {})
        if len(benchmark) < 60:
            raise RuntimeError("NIFTY 50 benchmark has fewer than 60 usable daily returns.")

        position_as_of = max((str(row.get("as_of") or "") for row in positions), default="") or None
        market_data_as_of = max((str(row.get("trading_date") or "") for row in market_rows), default="") or None
        exposures_all = aggregate_exposures(positions)
        gross = sum(item["gross"] for item in exposures_all.values())
        covered_symbols = [symbol for symbol in symbols if series.get(symbol)]
        covered_exposure = sum(exposures_all[symbol]["gross"] for symbol in covered_symbols)
        uncovered_symbols = [symbol for symbol in symbols if not series.get(symbol)]
        uncovered_exposure = gross - covered_exposure
        coverage_pct = covered_exposure / gross * 100 if gross else 0.0
        all_abs_returns = [abs(value) for symbol in covered_symbols for value in series[symbol].values()]
        bias_rows = run_psql_json("SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text FROM (SELECT * FROM market.v_market_bias_control_readiness ORDER BY control_key) rows")
        assumptions = {
            "benchmark": BENCHMARK_SYMBOL,
            "historical_return_outlier_filter_abs_pct": 50,
            "liquidity_participation_rate_pct": 10,
            "uncovered_proxy": "1.25x same-day NIFTY 50 return plus 1% gap event",
            "uncovered_shock_floor_pct": 3,
            "uncovered_shock_cap_pct": 10,
            "bootstrap_horizons_days": [1, 10],
            "current_exposure_historical_risk": True,
            "capital_action_allowed": False,
            "live_execution_allowed": False,
        }
        warnings = []
        if uncovered_symbols:
            warnings.append({"type": "missing_symbol_history", "symbols": uncovered_symbols, "exposure": uncovered_exposure})
        if any(str(row.get("readiness_status") or "") not in {"ready", "verified"} for row in bias_rows):
            warnings.append({"type": "market_bias_controls_incomplete", "controls": bias_rows})
        if sum(filtered_counts.values()):
            warnings.append({"type": "return_outliers_filtered", "counts": filtered_counts})

        run_row = run_psql_json(
            f"""
            WITH inserted AS (
                INSERT INTO risk.portfolio_risk_runs (
                    run_key, run_status, methodology, lookback_days, simulation_count, random_seed,
                    position_as_of, market_data_as_of, source_position_count, source_symbol_count,
                    covered_symbol_count, uncovered_symbol_count, gross_exposure, covered_exposure,
                    uncovered_exposure, coverage_pct, assumptions, warnings, source_lineage, created_by
                ) VALUES (
                    {sql_literal(run_key)}, 'running', 'historical_bootstrap_v1', {lookback}, {simulations}, {int(args.seed)},
                    {sql_literal(position_as_of)}::timestamptz, {sql_literal(market_data_as_of)}::timestamptz,
                    {len(positions)}, {len(symbols)}, {len(covered_symbols)}, {len(uncovered_symbols)},
                    {gross}, {covered_exposure}, {uncovered_exposure}, {coverage_pct},
                    {sql_jsonb(assumptions)}, {sql_jsonb(warnings)},
                    {sql_jsonb([{'view': 'books.v_book_positions'}, {'table': 'trading.ohlcv'}, {'benchmark': BENCHMARK_SYMBOL}])},
                    {sql_literal(args.actor.strip() or 'Portfolio Risk Analyst')}
                ) RETURNING id
            ) SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
            """
        )
        run_id = int(run_row[0]["id"])

        results = []
        for index, (scope_type, scope_ref, scope_name, scope_positions) in enumerate(scope_rows(positions)):
            results.append(calculate_scope(
                scope_type, scope_ref, scope_name, scope_positions, series, bars, benchmark,
                all_abs_returns, simulations, int(args.seed) + index * 101,
                market_data_as_of, position_as_of,
            ))
        persist_results(run_id, results)

        portfolio_metrics = results[0]["metrics"]
        run_status = "completed" if portfolio_metrics["status"] == "complete" and not warnings else "provisional"
        artifact = {
            "run_id": run_id, "run_key": run_key, "status": run_status, "generated_at": now.isoformat(),
            "positions": len(positions), "symbols": len(symbols), "covered_symbols": covered_symbols,
            "uncovered_symbols": uncovered_symbols, "coverage_pct": coverage_pct,
            "assumptions": assumptions, "warnings": warnings, "results": results,
            "live_execution_allowed": False,
        }
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        artifact_path = ARTIFACT_ROOT / f"{run_key}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        summary = {
            "portfolio_var_99_1d_pct": round(portfolio_metrics["boot_var1"] * 100, 4),
            "portfolio_es_99_1d_pct": round(portfolio_metrics["boot_es1"] * 100, 4),
            "portfolio_var_99_10d_pct": round(portfolio_metrics["boot_var10"] * 100, 4),
            "coverage_pct": round(coverage_pct, 4),
            "scope_count": len(results),
        }
        psql_exec(
            f"""
            UPDATE risk.portfolio_risk_runs
            SET run_status = {sql_literal(run_status)}, summary = {sql_jsonb(summary)},
                artifact_path = {sql_literal(artifact_reference(artifact_path))}, finished_at = now()
            WHERE id = {run_id};
            """
        )
        print(json.dumps({
            "run_id": run_id, "run_key": run_key, "status": run_status,
            "coverage_pct": round(coverage_pct, 4), "covered_symbols": len(covered_symbols),
            "uncovered_symbols": len(uncovered_symbols), "scope_count": len(results),
            "portfolio": summary, "artifact_path": artifact_reference(artifact_path),
            "capital_action_allowed": False, "live_execution_allowed": False,
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        if run_id is not None:
            try:
                psql_exec(
                    f"UPDATE risk.portfolio_risk_runs SET run_status='failed', error_message={sql_literal(str(exc))}, finished_at=now() WHERE id={run_id};"
                )
            except Exception:
                pass
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "run_id": run_id}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
