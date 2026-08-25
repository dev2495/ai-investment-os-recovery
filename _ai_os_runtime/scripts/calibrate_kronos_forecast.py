#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from statistics import mean, median
from typing import Any

from run_agent_worker_once import psql_json, psql_one, psql_text, sql_jsonb, sql_literal


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a quantile from an empty sample.")
    location = (len(ordered) - 1) * probability
    lower = int(math.floor(location))
    upper = int(math.ceil(location))
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def empirical_crps(samples: list[float], realized: float) -> float:
    if not samples:
        raise ValueError("CRPS requires at least one forecast sample.")
    ordered = sorted(samples)
    count = len(ordered)
    first_term = mean(abs(value - realized) for value in ordered)
    pairwise_sum = sum(
        (2 * index - count - 1) * value
        for index, value in enumerate(ordered, start=1)
    )
    mean_pairwise_distance = 2.0 * pairwise_sum / (count * count)
    return first_term - 0.5 * mean_pairwise_distance


def score_steps(
    *,
    predictions: list[dict[str, Any]],
    actuals: list[dict[str, Any]],
    last_close: float,
    expected_horizon: int,
) -> dict[str, Any]:
    actual_by_step = {
        int(row["step_index"]): row
        for row in actuals
        if row.get("actual_close") is not None
    }
    samples_by_step: dict[int, list[float]] = {}
    timestamps: dict[int, str] = {}
    for row in predictions:
        step = int(row["step_index"])
        samples_by_step.setdefault(step, []).append(float(row["close"]))
        timestamps[step] = str(row["forecast_ts"])

    step_scores: list[dict[str, Any]] = []
    for step in sorted(samples_by_step):
        actual = actual_by_step.get(step)
        if not actual:
            continue
        samples = samples_by_step[step]
        realized = float(actual["actual_close"])
        p10 = quantile(samples, 0.10)
        p90 = quantile(samples, 0.90)
        forecast_median = median(samples)
        predicted_direction = math.copysign(1, forecast_median - last_close) if forecast_median != last_close else 0
        realized_direction = math.copysign(1, realized - last_close) if realized != last_close else 0
        step_scores.append(
            {
                "step_index": step,
                "forecast_ts": timestamps[step],
                "actual_ts": str(actual["actual_ts"]),
                "timestamp_match": str(actual["actual_ts"]) == timestamps[step],
                "actual_close": realized,
                "path_count": len(samples),
                "p10_close": p10,
                "median_close": forecast_median,
                "p90_close": p90,
                "interval_covered": p10 <= realized <= p90,
                "direction_correct": predicted_direction == realized_direction,
                "crps": empirical_crps(samples, realized),
                "normalized_interval_width": (p90 - p10) / last_close,
                "actual_source_system_id": actual.get("source_system_id"),
            }
        )

    realized_points = len(step_scores)
    complete = realized_points == expected_horizon
    metrics = {
        "expected_horizon": expected_horizon,
        "realized_points": realized_points,
        "interval_coverage": mean(float(row["interval_covered"]) for row in step_scores) if step_scores else None,
        "directional_accuracy": mean(float(row["direction_correct"]) for row in step_scores) if step_scores else None,
        "crps": mean(float(row["crps"]) for row in step_scores) if step_scores else None,
        "mean_interval_width": mean(float(row["normalized_interval_width"]) for row in step_scores) if step_scores else None,
        "timestamp_match_rate": mean(float(row["timestamp_match"]) for row in step_scores) if step_scores else None,
        "complete_horizon": complete,
        "step_scores": step_scores,
    }
    return metrics


def load_run(forecast_run_id: int) -> dict[str, Any]:
    run = psql_one(
        f"""
        SELECT run.id,run.run_key,run.symbol_id,run.symbol,run.exchange,run.timeframe,
               run.source_end_ts,run.horizon,run.path_count,run.model_repo,
               run.model_revision,run.source_hash,run.output_hash,run.status,
               source.close AS last_close
        FROM strategy.kronos_forecast_runs run
        JOIN trading.ohlcv source
          ON source.symbol_id=run.symbol_id
         AND source.timeframe=run.timeframe
         AND source.ts=run.source_end_ts
        WHERE run.id={int(forecast_run_id)}
        """
    )
    if not run:
        raise ValueError(f"Kronos forecast run {forecast_run_id} was not found.")
    if str(run.get("status")) != "completed":
        raise ValueError("Only completed Kronos forecasts can be calibrated.")
    return run


def load_predictions(forecast_run_id: int) -> list[dict[str, Any]]:
    return psql_json(
        f"""
        SELECT path.step_index,path.forecast_ts,path.path_index,path.close
        FROM strategy.kronos_forecast_paths path
        WHERE path.forecast_run_id={int(forecast_run_id)}
        ORDER BY path.step_index,path.path_index
        """
    )


def load_actuals(run: dict[str, Any]) -> list[dict[str, Any]]:
    return psql_json(
        f"""
        WITH forecast_steps AS (
            SELECT path.step_index,min(path.forecast_ts) AS forecast_ts
            FROM strategy.kronos_forecast_paths path
            WHERE path.forecast_run_id={int(run['id'])}
            GROUP BY path.step_index
        ),
        realized_steps AS (
            SELECT row_number() OVER (ORDER BY actual.ts)::INTEGER AS step_index,
                   actual.ts AS actual_ts,actual.close AS actual_close,
                   actual.source_system_id
            FROM trading.ohlcv actual
            WHERE actual.symbol_id={int(run['symbol_id'])}
              AND actual.timeframe={sql_literal(str(run['timeframe']))}
              AND actual.ts>{sql_literal(str(run['source_end_ts']))}::timestamptz
            ORDER BY actual.ts
            LIMIT {int(run['horizon'])}
        )
        SELECT step.step_index,step.forecast_ts,
               actual.actual_ts,actual.actual_close,actual.source_system_id
        FROM forecast_steps step
        LEFT JOIN realized_steps actual ON actual.step_index=step.step_index
        ORDER BY step.step_index
        """
    )


def persist_score(run: dict[str, Any], metrics: dict[str, Any], actor: str) -> dict[str, Any]:
    realized = metrics["step_scores"]
    evaluation_end = (
        str(realized[-1]["actual_ts"])
        if realized
        else psql_one(
            f"SELECT max(forecast_ts) AS value FROM strategy.kronos_forecast_paths WHERE forecast_run_id={int(run['id'])}"
        )["value"]
    )
    actual_evidence = {
        "source": "trading.ohlcv",
        "symbol_id": int(run["symbol_id"]),
        "timeframe": str(run["timeframe"]),
        "rows": [
            {
                "step_index": row["step_index"],
                "actual_ts": row["actual_ts"],
                "actual_close": row["actual_close"],
                "source_system_id": row["actual_source_system_id"],
            }
            for row in realized
        ],
    }
    evidence = [
        {
            "forecast_run_id": int(run["id"]),
            "run_key": run["run_key"],
            "model_repo": run["model_repo"],
            "model_revision": run["model_revision"],
            "source_hash": run["source_hash"],
            "output_hash": run["output_hash"],
        },
        {**actual_evidence, "actual_hash": canonical_hash(actual_evidence)},
    ]
    status = "needs_review" if metrics["complete_horizon"] else "insufficient_evidence"
    feature_payload = {
        "metrics": metrics,
        "calibration_kind": "single_origin_realized",
        "point_in_time": True,
        "minimum_walk_forward_origins": 20,
        "automatic_strategy_promotion_allowed": False,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    psql_text(
        f"""
        INSERT INTO strategy.kronos_forecast_scores (
            forecast_run_id,score_kind,evaluation_start_ts,evaluation_end_ts,
            realized_points,interval_coverage,directional_accuracy,crps,
            mean_interval_width,ohlc_validity,volume_validity,validation_status,
            feature_payload,evidence,scored_by,scored_at
        )
        SELECT {int(run['id'])},'realized_calibration',min(path.forecast_ts),
               {sql_literal(str(evaluation_end))}::timestamptz,
               {int(metrics['realized_points'])},
               {metrics['interval_coverage'] if metrics['interval_coverage'] is not None else 'NULL'},
               {metrics['directional_accuracy'] if metrics['directional_accuracy'] is not None else 'NULL'},
               {metrics['crps'] if metrics['crps'] is not None else 'NULL'},
               {metrics['mean_interval_width'] if metrics['mean_interval_width'] is not None else 'NULL'},
               avg(path.ohlc_valid::int),avg(path.volume_valid::int),
               {sql_literal(status)},{sql_jsonb(feature_payload)},
               {sql_jsonb(evidence)},{sql_literal(actor)},now()
        FROM strategy.kronos_forecast_paths path
        WHERE path.forecast_run_id={int(run['id'])}
        GROUP BY path.forecast_run_id
        ON CONFLICT (forecast_run_id,score_kind,evaluation_end_ts) DO UPDATE SET
            realized_points=EXCLUDED.realized_points,
            interval_coverage=EXCLUDED.interval_coverage,
            directional_accuracy=EXCLUDED.directional_accuracy,
            crps=EXCLUDED.crps,
            mean_interval_width=EXCLUDED.mean_interval_width,
            validation_status=EXCLUDED.validation_status,
            feature_payload=EXCLUDED.feature_payload,
            evidence=EXCLUDED.evidence,
            scored_by=EXCLUDED.scored_by,
            scored_at=now();
        UPDATE strategy.kronos_forecast_runs
        SET validation=validation || {sql_jsonb({
            'realized_calibration_pending': not metrics['complete_horizon'],
            'realized_points': metrics['realized_points'],
            'expected_horizon': metrics['expected_horizon'],
            'automatic_strategy_promotion_allowed': False,
            'broker_order_allowed': False,
        })},
            updated_at=now()
        WHERE id={int(run['id'])};
        """
    )
    return {
        "forecast_run_id": int(run["id"]),
        "run_key": run["run_key"],
        "status": status,
        "metrics": metrics,
        "evidence": evidence,
        "research_only": True,
        "automatic_strategy_promotion_allowed": False,
        "broker_order_allowed": False,
    }


def calibrate(forecast_run_id: int, actor: str) -> dict[str, Any]:
    run = load_run(forecast_run_id)
    predictions = load_predictions(forecast_run_id)
    if not predictions:
        raise ValueError("The completed forecast has no persisted paths.")
    actuals = load_actuals(run)
    metrics = score_steps(
        predictions=predictions,
        actuals=actuals,
        last_close=float(run["last_close"]),
        expected_horizon=int(run["horizon"]),
    )
    return persist_score(run, metrics, actor)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a Kronos forecast against canonical realized bars.")
    parser.add_argument("--forecast-run-id", required=True, type=int)
    parser.add_argument("--actor", default="Model Validation Agent")
    arguments = parser.parse_args()
    try:
        print(json.dumps(calibrate(arguments.forecast_run_id, arguments.actor), sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "synthetic_fallback_used": False,
            "automatic_strategy_promotion_allowed": False,
            "broker_order_allowed": False,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
