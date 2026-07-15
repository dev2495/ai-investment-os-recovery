#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from decimal import Decimal

from run_portfolio_risk_engine import run_psql_json as run_psql_json_result


TOLERANCE = Decimal("0.01")


def number(value: object) -> Decimal:
    return Decimal(str(value or 0))


def query_rows(query: str) -> list[dict]:
    return run_psql_json_result(
        f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows"
    )


def main() -> int:
    runs = query_rows(
        """
        SELECT id, run_key, run_status, gross_exposure, covered_exposure,
               uncovered_exposure, source_symbol_count, covered_symbol_count,
               uncovered_symbol_count, coverage_pct, artifact_path
        FROM risk.v_latest_portfolio_risk_run
        LIMIT 1
        """
    )
    if not runs:
        raise AssertionError("no completed or provisional institutional risk run")
    run = runs[0]
    metrics = query_rows(
        """
        SELECT scope_type, scope_ref, gross_exposure, covered_exposure,
               uncovered_exposure, historical_var_95_pct,
               historical_es_95_pct, historical_var_99_pct,
               historical_es_99_pct, bootstrap_var_99_1d_pct,
               bootstrap_es_99_1d_pct, bootstrap_var_99_10d_pct,
               bootstrap_es_99_10d_pct
        FROM risk.v_latest_portfolio_risk_metrics
        """
    )
    stress = query_rows(
        """
        SELECT scenario_key, stressed_pnl_value, stressed_return_pct
        FROM risk.v_latest_portfolio_stress_results
        WHERE scope_type = 'portfolio'
        """
    )
    liquidity = query_rows(
        """
        SELECT symbol, gross_exposure, liquidity_bucket, calculation_status
        FROM risk.v_latest_position_liquidity
        WHERE scope_type = 'portfolio'
        """
    )
    factors = query_rows(
        """
        SELECT factor_key
        FROM risk.v_latest_factor_risk_attribution
        WHERE scope_type = 'portfolio'
        """
    )
    execution = query_rows(
        """
        SELECT global_execution_locked, live_broker_writes_allowed
        FROM trading.v_execution_control_state
        LIMIT 1
        """
    )

    assert run["run_status"] in {"completed", "provisional"}
    assert run["artifact_path"], "latest run has no SSD artifact"
    assert number(run["gross_exposure"]) > 0
    assert abs(number(run["covered_exposure"]) + number(run["uncovered_exposure"]) - number(run["gross_exposure"])) <= TOLERANCE
    assert int(run["covered_symbol_count"]) + int(run["uncovered_symbol_count"]) == int(run["source_symbol_count"])
    assert metrics and any(row["scope_type"] == "portfolio" for row in metrics)

    pairs = [
        ("historical_var_95_pct", "historical_es_95_pct"),
        ("historical_var_99_pct", "historical_es_99_pct"),
        ("bootstrap_var_99_1d_pct", "bootstrap_es_99_1d_pct"),
        ("bootstrap_var_99_10d_pct", "bootstrap_es_99_10d_pct"),
    ]
    for row in metrics:
        assert abs(number(row["covered_exposure"]) + number(row["uncovered_exposure"]) - number(row["gross_exposure"])) <= TOLERANCE
        for var_key, es_key in pairs:
            assert number(row[var_key]) >= 0
            assert number(row[es_key]) >= number(row[var_key]), f"{row['scope_type']}:{row['scope_ref']} {es_key} < {var_key}"

    assert len(stress) == 5, f"expected 5 portfolio stress scenarios, found {len(stress)}"
    assert all(number(row["stressed_pnl_value"]) <= 0 for row in stress)
    assert len(liquidity) == int(run["source_symbol_count"])
    assert len({row["symbol"] for row in liquidity}) == len(liquidity)
    assert abs(sum((number(row["gross_exposure"]) for row in liquidity), Decimal(0)) - number(run["gross_exposure"])) <= TOLERANCE
    assert {row["factor_key"] for row in factors} == {
        "concentration_hhi", "liquidity_unavailable", "market_beta",
        "missing_history", "residual_risk",
    }
    assert execution and execution[0]["global_execution_locked"] is True
    assert execution[0]["live_broker_writes_allowed"] is False

    print(json.dumps({
        "status": "passed",
        "run_id": run["id"],
        "run_key": run["run_key"],
        "run_status": run["run_status"],
        "metric_scopes": len(metrics),
        "portfolio_stress_scenarios": len(stress),
        "portfolio_liquidity_symbols": len(liquidity),
        "coverage_pct": run["coverage_pct"],
        "execution_locked": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
