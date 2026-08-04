#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CALCULATION_VERSION = "sector-engine-v1"
WEIGHTING_METHODS = {
    "equal",
    "market_cap",
    "free_float_market_cap",
    "quality",
    "momentum",
    "custom",
}
HORIZONS = ("1D", "1W", "1M", "3M", "6M", "1Y", "cycle")
HORIZON_DAYS = {"1D": 1, "1W": 7, "1M": 30, "3M": 91, "6M": 182, "1Y": 365}


class EvidenceError(ValueError):
    """Raised when a point-in-time calculation lacks required observed evidence."""


def parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise EvidenceError("missing date")
    return date.fromisoformat(text[:10])


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip().replace("Z", "+00:00")
        if not text:
            raise EvidenceError("missing observation timestamp")
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def stable_fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _has_evidence(row: dict[str, Any]) -> bool:
    evidence = row.get("evidence")
    return bool(evidence) and evidence not in ({}, [], "")


def _validate_observed_at(row: dict[str, Any], as_of: date, label: str) -> None:
    observed_at = parse_datetime(row.get("observed_at"))
    if observed_at.date() > as_of:
        raise EvidenceError(f"{label} uses lookahead evidence observed at {observed_at.isoformat()}")


def active_memberships(rows: Iterable[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        valid_from = parse_date(row.get("valid_from"))
        valid_to = parse_date(row["valid_to"]) if row.get("valid_to") else None
        if valid_from <= as_of and (valid_to is None or valid_to >= as_of):
            symbol_id = int(row["symbol_id"])
            if symbol_id in seen:
                raise EvidenceError(f"duplicate active membership for symbol_id={symbol_id}")
            if not _has_evidence(row):
                raise EvidenceError(f"membership evidence missing for symbol_id={symbol_id}")
            _validate_observed_at(row, as_of, f"membership symbol_id={symbol_id}")
            seen.add(symbol_id)
            active.append(dict(row))
    if not active:
        raise EvidenceError(f"no evidenced memberships active on {as_of.isoformat()}")
    return sorted(active, key=lambda item: int(item["symbol_id"]))


def _raw_score(row: dict[str, Any], method: str, as_of: date) -> float:
    if method == "equal":
        return 1.0
    required = {
        "market_cap": ("market_cap",),
        "free_float_market_cap": ("market_cap", "free_float_factor"),
        "quality": ("quality_score",),
        "momentum": ("momentum_score",),
        "custom": ("custom_score",),
    }[method]
    missing = [key for key in required if row.get(key) is None]
    if missing:
        raise EvidenceError(
            f"{method} evidence missing {','.join(missing)} for symbol_id={int(row['symbol_id'])}"
        )
    _validate_observed_at(row, as_of, f"{method} symbol_id={int(row['symbol_id'])}")
    if method == "free_float_market_cap":
        score = float(row["market_cap"]) * float(row["free_float_factor"])
    else:
        score = float(row[required[0]])
    if not math.isfinite(score) or score <= 0:
        raise EvidenceError(f"{method} score must be finite and positive for symbol_id={int(row['symbol_id'])}")
    return score


def cap_and_normalize(raw_weights: dict[int, float], cap: float | None) -> dict[int, float]:
    if not raw_weights:
        raise EvidenceError("cannot normalize an empty weight set")
    if any(not math.isfinite(value) or value <= 0 for value in raw_weights.values()):
        raise EvidenceError("all raw weights must be finite and positive")
    count = len(raw_weights)
    if cap is None:
        cap = 1.0
    cap = float(cap)
    if not 0 < cap <= 1:
        raise EvidenceError("weight_cap must be in (0, 1]")
    if cap * count < 1.0 - 1e-12:
        raise EvidenceError(f"weight_cap={cap} cannot fully allocate {count} constituents")

    remaining = set(raw_weights)
    result: dict[int, float] = {}
    remaining_mass = 1.0
    while remaining:
        raw_total = sum(raw_weights[symbol_id] for symbol_id in remaining)
        proposed = {
            symbol_id: remaining_mass * raw_weights[symbol_id] / raw_total
            for symbol_id in remaining
        }
        capped = [symbol_id for symbol_id, weight in proposed.items() if weight > cap + 1e-14]
        if not capped:
            result.update(proposed)
            break
        for symbol_id in sorted(capped):
            result[symbol_id] = cap
            remaining.remove(symbol_id)
            remaining_mass -= cap
        if remaining_mass < -1e-12:
            raise EvidenceError("weight cap allocation became infeasible")

    total = sum(result.values())
    if not math.isclose(total, 1.0, abs_tol=1e-10):
        raise EvidenceError(f"normalized weights sum to {total}, expected 1")
    return {symbol_id: weight / total for symbol_id, weight in sorted(result.items())}


def compute_weights(
    memberships: Iterable[dict[str, Any]],
    method: str,
    as_of: date,
    weight_cap: float | None = None,
) -> list[dict[str, Any]]:
    if method not in WEIGHTING_METHODS:
        raise EvidenceError(f"unsupported weighting method: {method}")
    active = active_memberships(memberships, as_of)
    scores = {int(row["symbol_id"]): _raw_score(row, method, as_of) for row in active}
    total = sum(scores.values())
    uncapped = {symbol_id: score / total for symbol_id, score in scores.items()}
    normalized = cap_and_normalize(scores, weight_cap)
    by_symbol = {int(row["symbol_id"]): row for row in active}
    return [
        {
            "symbol_id": symbol_id,
            "symbol": by_symbol[symbol_id].get("symbol"),
            "raw_score": scores[symbol_id],
            "target_weight": normalized[symbol_id],
            "capped_weight": normalized[symbol_id] if normalized[symbol_id] < uncapped[symbol_id] - 1e-12 else None,
            "calculation_evidence": {
                "method": method,
                "as_of_date": as_of.isoformat(),
                "membership_reference": by_symbol[symbol_id].get("source_reference"),
                "observed_at": by_symbol[symbol_id].get("observed_at"),
                "broker_writes_allowed": False,
            },
        }
        for symbol_id in sorted(normalized)
    ]


def _validated_price_rows(
    rows: Iterable[dict[str, Any]], as_of: date, eligible: set[int]
) -> dict[int, list[tuple[datetime, float]]]:
    output: dict[int, list[tuple[datetime, float]]] = {symbol_id: [] for symbol_id in eligible}
    for row in rows:
        symbol_id = int(row["symbol_id"])
        if symbol_id not in eligible:
            continue
        ts = parse_datetime(row.get("ts"))
        if ts.date() > as_of:
            continue
        if not _has_evidence(row):
            raise EvidenceError(f"price evidence missing for symbol_id={symbol_id} at {ts.isoformat()}")
        close = float(row["close"])
        if not math.isfinite(close) or close <= 0:
            raise EvidenceError(f"invalid close for symbol_id={symbol_id} at {ts.isoformat()}")
        output[symbol_id].append((ts, close))
    for symbol_id, values in output.items():
        values.sort()
        if not values:
            raise EvidenceError(f"no point-in-time price evidence for symbol_id={symbol_id}")
    return output


def compute_index_history(
    index_id: int,
    weights: Iterable[dict[str, Any]],
    price_rows: Iterable[dict[str, Any]],
    effective_date: date,
    as_of: date,
    base_value: float,
    rebalance_id: int | None = None,
    calculation_version: str = CALCULATION_VERSION,
) -> list[dict[str, Any]]:
    weights_by_symbol = {int(row["symbol_id"]): float(row["target_weight"]) for row in weights}
    if not math.isclose(sum(weights_by_symbol.values()), 1.0, abs_tol=1e-10):
        raise EvidenceError("index history requires weights summing to one")
    prices = _validated_price_rows(price_rows, as_of, set(weights_by_symbol))
    common_timestamps = sorted(
        ts
        for ts in set.intersection(*(set(ts for ts, _ in values) for values in prices.values()))
        if effective_date <= ts.date() <= as_of
    )
    if not common_timestamps:
        raise EvidenceError("no common point-in-time timestamps in the rebalance window")
    price_maps = {symbol_id: dict(values) for symbol_id, values in prices.items()}
    reference = {symbol_id: price_maps[symbol_id][common_timestamps[0]] for symbol_id in prices}
    history: list[dict[str, Any]] = []
    for ts in common_timestamps:
        value = float(base_value) * sum(
            weights_by_symbol[symbol_id] * price_maps[symbol_id][ts] / reference[symbol_id]
            for symbol_id in weights_by_symbol
        )
        evidence = {
            "index_id": index_id,
            "ts": ts.isoformat(),
            "weights": weights_by_symbol,
            "prices": {symbol_id: price_maps[symbol_id][ts] for symbol_id in weights_by_symbol},
        }
        history.append(
            {
                "index_id": index_id,
                "ts": ts.isoformat(),
                "index_value": value,
                "total_return_value": value,
                "divisor": None,
                "constituent_market_value": None,
                "rebalance_id": rebalance_id,
                "input_fingerprint": stable_fingerprint(evidence),
                "calculation_version": calculation_version,
                "quality_status": "calculated",
            }
        )
    return history


def point_in_time_return(rows: Iterable[dict[str, Any]], as_of: date, days: int) -> float:
    values: list[tuple[datetime, float]] = []
    for row in rows:
        ts = parse_datetime(row.get("ts"))
        if ts.date() <= as_of:
            if not _has_evidence(row):
                raise EvidenceError(f"return evidence missing at {ts.isoformat()}")
            close = float(row["close"])
            if close <= 0 or not math.isfinite(close):
                raise EvidenceError(f"invalid return price at {ts.isoformat()}")
            values.append((ts, close))
    values.sort()
    if not values:
        raise EvidenceError("no point-in-time prices for return calculation")
    end_ts, end_value = values[-1]
    target = end_ts.date().toordinal() - days
    eligible = [(ts, value) for ts, value in values if ts.date().toordinal() <= target]
    if not eligible:
        raise EvidenceError(f"insufficient history for {days}-day return")
    return end_value / eligible[-1][1] - 1.0


def compute_relative_strength(
    sector_series: dict[int, list[dict[str, Any]]],
    benchmark_series: list[dict[str, Any]],
    as_of: date,
    horizon: str,
    calculation_version: str = CALCULATION_VERSION,
) -> list[dict[str, Any]]:
    if horizon not in HORIZON_DAYS:
        raise EvidenceError(f"relative strength requires one of {tuple(HORIZON_DAYS)}")
    benchmark_return = point_in_time_return(benchmark_series, as_of, HORIZON_DAYS[horizon])
    values = []
    for taxonomy_node_id, rows in sorted(sector_series.items()):
        absolute_return = point_in_time_return(rows, as_of, HORIZON_DAYS[horizon])
        values.append((taxonomy_node_id, absolute_return, absolute_return - benchmark_return))
    ordered = sorted(values, key=lambda item: (-item[2], item[0]))
    rank_by_id = {item[0]: rank for rank, item in enumerate(ordered, 1)}
    return [
        {
            "taxonomy_node_id": node_id,
            "as_of_date": as_of.isoformat(),
            "horizon": horizon,
            "absolute_return": absolute_return,
            "benchmark_return": benchmark_return,
            "relative_return": relative_return,
            "rank_value": rank_by_id[node_id],
            "universe_size": len(values),
            "calculation_version": calculation_version,
            "input_fingerprint": stable_fingerprint(
                {"node": node_id, "as_of": as_of, "horizon": horizon, "series": sector_series[node_id], "benchmark": benchmark_series}
            ),
        }
        for node_id, absolute_return, relative_return in sorted(values)
    ]


def compute_breadth(
    taxonomy_node_id: int,
    constituent_returns: Iterable[dict[str, Any]],
    as_of: date,
    horizon: str,
    calculation_version: str = CALCULATION_VERSION,
) -> dict[str, Any]:
    if horizon not in HORIZONS:
        raise EvidenceError(f"unsupported breadth horizon: {horizon}")
    rows = list(constituent_returns)
    if not rows:
        raise EvidenceError("breadth requires constituent return evidence")
    values: list[float] = []
    for row in rows:
        _validate_observed_at(row, as_of, f"breadth symbol_id={row.get('symbol_id')}")
        if not _has_evidence(row) or row.get("return") is None:
            raise EvidenceError(f"breadth evidence missing for symbol_id={row.get('symbol_id')}")
        values.append(float(row["return"]))
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    unchanged = len(values) - positive - negative
    breadth_value = (positive - negative) / len(values)
    return {
        "taxonomy_node_id": taxonomy_node_id,
        "as_of_date": as_of.isoformat(),
        "horizon": horizon,
        "breadth_type": "advance_decline_ratio",
        "positive_count": positive,
        "negative_count": negative,
        "unchanged_count": unchanged,
        "eligible_count": len(values),
        "breadth_value": breadth_value,
        "calculation_version": calculation_version,
        "input_fingerprint": stable_fingerprint(rows),
    }


def compute_rankings(
    scores: Iterable[dict[str, Any]], as_of: date, ranking_type: str, horizon: str
) -> list[dict[str, Any]]:
    if horizon not in HORIZONS:
        raise EvidenceError(f"unsupported ranking horizon: {horizon}")
    rows = list(scores)
    if not rows:
        raise EvidenceError("ranking requires score evidence")
    for row in rows:
        _validate_observed_at(row, as_of, f"ranking taxonomy_node_id={row.get('taxonomy_node_id')}")
        if not _has_evidence(row) or row.get("score") is None:
            raise EvidenceError(f"ranking evidence missing for taxonomy_node_id={row.get('taxonomy_node_id')}")
    ordered = sorted(rows, key=lambda row: (-float(row["score"]), int(row["taxonomy_node_id"])))
    return [
        {
            "taxonomy_node_id": int(row["taxonomy_node_id"]),
            "as_of_date": as_of.isoformat(),
            "ranking_universe": str(row.get("ranking_universe") or "india_sector_universe"),
            "ranking_type": ranking_type,
            "horizon": horizon,
            "rank_value": rank,
            "universe_size": len(ordered),
            "score": float(row["score"]),
            "calculation_version": CALCULATION_VERSION,
            "input_fingerprint": stable_fingerprint(row),
        }
        for rank, row in enumerate(ordered, 1)
    ]


def generate_tradingview_artifacts(
    index: dict[str, Any], weights: Iterable[dict[str, Any]], as_of: date
) -> list[dict[str, Any]]:
    weighted = list(weights)
    symbols = [str(row.get("symbol") or "").strip().upper() for row in weighted]
    if not symbols or any(not symbol for symbol in symbols):
        raise EvidenceError("TradingView artifacts require evidenced symbol codes")
    formula = "+".join(
        f"({float(row['target_weight']):.10f}*{str(row['symbol']).strip().upper()})" for row in weighted
    )
    pine_lines = [
        "//@version=5",
        f'indicator("{index["index_name"]}", overlay=false)',
    ]
    terms = []
    for position, row in enumerate(weighted):
        variable = f"s{position}"
        symbol = str(row["symbol"]).strip().upper()
        pine_lines.append(f'{variable} = request.security("{symbol}", timeframe.period, close)')
        terms.append(f"{float(row['target_weight']):.10f} * {variable}")
    pine_lines.extend((f"basket = {' + '.join(terms)}", 'plot(basket, title="Deterministic basket")'))
    fingerprint = stable_fingerprint({"index": index, "weights": weighted, "as_of": as_of})
    key = str(index["index_key"])
    common = {
        "target_workspace": "tradingview_desktop",
        "taxonomy_node_id": index.get("taxonomy_node_id"),
        "index_id": int(index["index_id"]),
        "source_state_fingerprint": fingerprint,
        "generation_version": CALCULATION_VERSION,
        "broker_order_allowed": False,
        "authoritative": False,
    }
    return [
        {**common, "artifact_key": f"{key}:{as_of}:formula", "artifact_type": "formula", "generated_expression": formula, "pine_source": None, "chart_layout": {}},
        {**common, "artifact_key": f"{key}:{as_of}:pine", "artifact_type": "pine_script", "generated_expression": None, "pine_source": "\n".join(pine_lines), "chart_layout": {}},
        {**common, "artifact_key": f"{key}:{as_of}:layout", "artifact_type": "leader_laggard_pack", "generated_expression": None, "pine_source": None, "chart_layout": {"symbols": symbols, "panes": min(8, len(symbols)), "consumer_only": True}},
    ]


def run_engine(payload: dict[str, Any]) -> dict[str, Any]:
    as_of = parse_date(payload.get("as_of_date"))
    index = dict(payload.get("index") or {})
    required_index = ("index_id", "index_key", "index_name", "weighting_method", "base_value")
    missing_index = [field for field in required_index if index.get(field) in (None, "")]
    if missing_index:
        return _blocked(as_of, [f"index.{field}" for field in missing_index])
    try:
        effective_date = parse_date(index.get("effective_date") or as_of)
        if effective_date > as_of:
            raise EvidenceError("index effective_date cannot be after as_of_date")
        weights = compute_weights(
            payload.get("memberships") or [],
            str(index["weighting_method"]),
            effective_date,
            index.get("weight_cap"),
        )
        history = compute_index_history(
            int(index["index_id"]),
            weights,
            payload.get("prices") or [],
            effective_date,
            as_of,
            float(index["base_value"]),
        )
        relative_strength = []
        if payload.get("sector_series"):
            relative_strength = compute_relative_strength(
                {int(key): value for key, value in payload["sector_series"].items()},
                payload.get("benchmark_series") or [],
                as_of,
                str(payload.get("horizon") or "1M"),
            )
        breadth = [
            compute_breadth(int(item["taxonomy_node_id"]), item.get("returns") or [], as_of, str(item.get("horizon") or payload.get("horizon") or "1M"))
            for item in payload.get("breadth_inputs") or []
        ]
        rankings = compute_rankings(
            payload.get("ranking_inputs") or [], as_of, str(payload.get("ranking_type") or "composite"), str(payload.get("horizon") or "1M")
        ) if payload.get("ranking_inputs") else []
        artifacts = generate_tradingview_artifacts(index, weights, as_of)
    except (EvidenceError, KeyError, TypeError, ValueError) as exc:
        return _blocked(as_of, [str(exc)])

    fingerprint = stable_fingerprint({
        "as_of_date": as_of,
        "index": index,
        "memberships": payload.get("memberships"),
        "prices": payload.get("prices"),
    })
    return {
        "status": "completed",
        "as_of_date": as_of.isoformat(),
        "calculation_version": CALCULATION_VERSION,
        "input_fingerprint": fingerprint,
        "rebalance": {
            "index_id": int(index["index_id"]),
            "effective_date": effective_date.isoformat(),
            "status": "calculated",
            "methodology_version": str(index.get("methodology_version") or CALCULATION_VERSION),
            "input_fingerprint": fingerprint,
            "constituent_count": len(weights),
            "turnover_percent": None,
            "calculation_run_reference": f"sector-engine:{fingerprint[:16]}",
        },
        "weights": weights,
        "history": history,
        "relative_strength": relative_strength,
        "breadth": breadth,
        "rankings": rankings,
        "tradingview_artifacts": artifacts,
        "governance": {
            "point_in_time": True,
            "seed_or_fabricated_data": False,
            "tradingview_authoritative": False,
            "tradingview_execution_allowed": False,
            "broker_writes_allowed": False,
            "capital_action_allowed": False,
        },
    }


def _blocked(as_of: date, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": "blocked_missing_evidence",
        "as_of_date": as_of.isoformat(),
        "blocking_reasons": reasons,
        "weights": [],
        "history": [],
        "relative_strength": [],
        "breadth": [],
        "rankings": [],
        "tradingview_artifacts": [],
        "governance": {
            "point_in_time": True,
            "seed_or_fabricated_data": False,
            "tradingview_authoritative": False,
            "tradingview_execution_allowed": False,
            "broker_writes_allowed": False,
            "capital_action_allowed": False,
        },
    }


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def build_persistence_sql(result: dict[str, Any]) -> str:
    if result.get("status") != "completed":
        raise EvidenceError("blocked results cannot be persisted")
    payload = json.dumps(result, separators=(",", ":"), default=str).replace("'", "''")
    return f"""
BEGIN;
DO $$
DECLARE
    doc JSONB := '{payload}'::JSONB;
    rebalance_pk BIGINT;
BEGIN
    IF coalesce((doc #>> '{{governance,broker_writes_allowed}}')::BOOLEAN, false) THEN
        RAISE EXCEPTION 'sector engine broker-write guard violated';
    END IF;
    INSERT INTO sector_intelligence.custom_index_rebalances (
        index_id, effective_date, status, methodology_version, input_fingerprint,
        constituent_count, turnover_percent, calculation_run_reference
    ) SELECT
        (doc #>> '{{rebalance,index_id}}')::BIGINT,
        (doc #>> '{{rebalance,effective_date}}')::DATE,
        doc #>> '{{rebalance,status}}',
        doc #>> '{{rebalance,methodology_version}}',
        doc #>> '{{rebalance,input_fingerprint}}',
        (doc #>> '{{rebalance,constituent_count}}')::INTEGER,
        nullif(doc #>> '{{rebalance,turnover_percent}}', '')::NUMERIC,
        doc #>> '{{rebalance,calculation_run_reference}}'
    ON CONFLICT (index_id, effective_date, methodology_version) DO UPDATE SET
        input_fingerprint = EXCLUDED.input_fingerprint,
        constituent_count = EXCLUDED.constituent_count,
        calculation_run_reference = EXCLUDED.calculation_run_reference
    RETURNING id INTO rebalance_pk;

    DELETE FROM sector_intelligence.custom_index_weights WHERE rebalance_id = rebalance_pk;
    INSERT INTO sector_intelligence.custom_index_weights (
        rebalance_id, symbol_id, raw_score, target_weight, capped_weight, calculation_evidence
    ) SELECT rebalance_pk, (item->>'symbol_id')::BIGINT, (item->>'raw_score')::NUMERIC,
             (item->>'target_weight')::NUMERIC, nullif(item->>'capped_weight','')::NUMERIC,
             item->'calculation_evidence'
      FROM jsonb_array_elements(doc->'weights') item;

    INSERT INTO sector_intelligence.custom_index_history (
        index_id, ts, index_value, total_return_value, divisor, constituent_market_value,
        rebalance_id, input_fingerprint, calculation_version, quality_status
    ) SELECT (item->>'index_id')::BIGINT, (item->>'ts')::TIMESTAMPTZ,
             (item->>'index_value')::NUMERIC, (item->>'total_return_value')::NUMERIC,
             nullif(item->>'divisor','')::NUMERIC, nullif(item->>'constituent_market_value','')::NUMERIC,
             rebalance_pk, item->>'input_fingerprint', item->>'calculation_version', item->>'quality_status'
      FROM jsonb_array_elements(doc->'history') item
    ON CONFLICT (index_id, ts) DO UPDATE SET
        index_value = EXCLUDED.index_value, total_return_value = EXCLUDED.total_return_value,
        rebalance_id = EXCLUDED.rebalance_id, input_fingerprint = EXCLUDED.input_fingerprint,
        calculation_version = EXCLUDED.calculation_version, quality_status = EXCLUDED.quality_status;

    DELETE FROM sector_intelligence.relative_strength_observations existing
     USING jsonb_array_elements(doc->'relative_strength') item
     WHERE existing.taxonomy_node_id = (item->>'taxonomy_node_id')::BIGINT
       AND existing.benchmark_symbol_id IS NOT DISTINCT FROM nullif(item->>'benchmark_symbol_id','')::BIGINT
       AND existing.as_of_date = (item->>'as_of_date')::DATE
       AND existing.horizon = item->>'horizon'
       AND existing.calculation_version = item->>'calculation_version';

    INSERT INTO sector_intelligence.relative_strength_observations (
        taxonomy_node_id, benchmark_symbol_id, as_of_date, horizon, absolute_return,
        benchmark_return, relative_return, rank_value, universe_size, calculation_version, input_fingerprint
    ) SELECT (item->>'taxonomy_node_id')::BIGINT, nullif(item->>'benchmark_symbol_id','')::BIGINT,
             (item->>'as_of_date')::DATE, item->>'horizon', (item->>'absolute_return')::NUMERIC,
             (item->>'benchmark_return')::NUMERIC, (item->>'relative_return')::NUMERIC,
             (item->>'rank_value')::INTEGER, (item->>'universe_size')::INTEGER,
             item->>'calculation_version', item->>'input_fingerprint'
      FROM jsonb_array_elements(doc->'relative_strength') item;

    INSERT INTO sector_intelligence.breadth_observations (
        taxonomy_node_id, as_of_date, horizon, breadth_type, positive_count, negative_count,
        unchanged_count, eligible_count, breadth_value, calculation_version, input_fingerprint
    ) SELECT (item->>'taxonomy_node_id')::BIGINT, (item->>'as_of_date')::DATE,
             item->>'horizon', item->>'breadth_type', (item->>'positive_count')::INTEGER,
             (item->>'negative_count')::INTEGER, (item->>'unchanged_count')::INTEGER,
             (item->>'eligible_count')::INTEGER, (item->>'breadth_value')::NUMERIC,
             item->>'calculation_version', item->>'input_fingerprint'
      FROM jsonb_array_elements(doc->'breadth') item
    ON CONFLICT (taxonomy_node_id, as_of_date, horizon, breadth_type, calculation_version)
    DO UPDATE SET positive_count = EXCLUDED.positive_count, negative_count = EXCLUDED.negative_count,
                  unchanged_count = EXCLUDED.unchanged_count, eligible_count = EXCLUDED.eligible_count,
                  breadth_value = EXCLUDED.breadth_value, input_fingerprint = EXCLUDED.input_fingerprint;

    INSERT INTO sector_intelligence.sector_rankings (
        taxonomy_node_id, as_of_date, ranking_universe, ranking_type, horizon,
        rank_value, universe_size, score, calculation_version, input_fingerprint
    ) SELECT (item->>'taxonomy_node_id')::BIGINT, (item->>'as_of_date')::DATE,
             item->>'ranking_universe', item->>'ranking_type', item->>'horizon',
             (item->>'rank_value')::INTEGER, (item->>'universe_size')::INTEGER,
             (item->>'score')::NUMERIC, item->>'calculation_version', item->>'input_fingerprint'
      FROM jsonb_array_elements(doc->'rankings') item
    ON CONFLICT (taxonomy_node_id, as_of_date, ranking_universe, ranking_type, horizon, calculation_version)
    DO UPDATE SET rank_value = EXCLUDED.rank_value, universe_size = EXCLUDED.universe_size,
                  score = EXCLUDED.score, input_fingerprint = EXCLUDED.input_fingerprint;

    INSERT INTO sector_intelligence.generated_chart_artifacts (
        artifact_key, artifact_type, target_workspace, taxonomy_node_id, index_id,
        generated_expression, pine_source, chart_layout, source_state_fingerprint, generation_version
    ) SELECT item->>'artifact_key', item->>'artifact_type', item->>'target_workspace',
             nullif(item->>'taxonomy_node_id','')::BIGINT, (item->>'index_id')::BIGINT,
             item->>'generated_expression', item->>'pine_source', item->'chart_layout',
             item->>'source_state_fingerprint', item->>'generation_version'
      FROM jsonb_array_elements(doc->'tradingview_artifacts') item
    ON CONFLICT (artifact_key) DO UPDATE SET
        generated_expression = EXCLUDED.generated_expression, pine_source = EXCLUDED.pine_source,
        chart_layout = EXCLUDED.chart_layout, source_state_fingerprint = EXCLUDED.source_state_fingerprint,
        generation_version = EXCLUDED.generation_version, generated_at = now();
END $$;
COMMIT;
""".strip()


def persist_result(result: dict[str, Any]) -> None:
    completed = subprocess.run(
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "ai_os", "-d", "ai_os"],
        input=build_persistence_sql(result),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())


def read_json(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic point-in-time Sector Intelligence calculations.")
    parser.add_argument("--input", required=True, help="JSON input path, or - for stdin.")
    parser.add_argument("--dry-run", action="store_true", help="Calculate and print JSON without database writes.")
    args = parser.parse_args(argv)
    result = run_engine(read_json(args.input))
    if not args.dry_run and result["status"] == "completed":
        persist_result(result)
        result["database"] = {"persisted": True}
    else:
        result["database"] = {"persisted": False, "dry_run": bool(args.dry_run)}
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
