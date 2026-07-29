
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from run_agent_worker_once import psql_json, psql_one, psql_text, sql_jsonb, sql_literal
from kronos_inference_worker import (
    KRONOS_CODE_REPO,
    KRONOS_CODE_REVISION,
    KRONOS_MODEL_REPO,
    KRONOS_MODEL_REVISION,
    KRONOS_MODEL_SHA256,
    KRONOS_TOKENIZER_REPO,
    KRONOS_TOKENIZER_REVISION,
    KRONOS_TOKENIZER_SHA256,
    runtime_home,
)

IST = ZoneInfo("Asia/Kolkata")


def isolated_python() -> Path:
    return Path(
        os.environ.get("AI_OS_KRONOS_PYTHON")
        or runtime_home() / "venv" / "bin" / "python"
    )


def inference_worker() -> Path:
    return Path(__file__).resolve().with_name("kronos_inference_worker.py")


def parse_json_output(output: str) -> dict[str, Any]:
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError("Kronos worker did not return a JSON object.")


def run_isolated(*arguments: str, timeout: int = 7200) -> dict[str, Any]:
    python_bin = isolated_python()
    if not python_bin.is_file():
        raise RuntimeError(
            f"Kronos runtime is not installed at {python_bin}. "
            "Run scripts/setup_kronos_runtime.sh on the iMac."
        )
    completed = subprocess.run(
        [str(python_bin), str(inference_worker()), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "HF_HOME": str(runtime_home() / "huggingface"),
            "HF_HUB_CACHE": str(runtime_home() / "huggingface" / "hub"),
            "HF_HUB_OFFLINE": "0" if "--prepare" in arguments else "1",
        },
    )
    result = parse_json_output(completed.stdout)
    if completed.returncode != 0 or not result.get("ready", True):
        detail = result.get("error") or completed.stderr.strip() or "Kronos worker failed."
        raise RuntimeError(str(detail))
    return result


def readiness(*, activate_tool: bool = False) -> dict[str, Any]:
    try:
        result = run_isolated("--readiness", timeout=120)
    except Exception as exc:
        result = {
            "ready": False,
            "error": f"{type(exc).__name__}: {exc}",
            "runtime_home": str(runtime_home()),
            "research_only": True,
            "broker_order_allowed": False,
        }
    if activate_tool:
        config_patch = {
            "runtime_status": "ready" if result.get("ready") else "unavailable",
            "last_readiness_check": datetime.now(timezone.utc).isoformat(),
            "readiness": result,
            "research_only": True,
            "live_execution_allowed": False,
            "broker_order_allowed": False,
        }
        psql_text(
            f"""
            UPDATE agent.tool_registry
            SET enabled={str(bool(result.get('ready'))).lower()},
                config=coalesce(config,'{{}}'::jsonb) || {sql_jsonb(config_patch)}
            WHERE tool_name='kronos_inference_adapter';
            UPDATE core.control_plane_modules
            SET status={sql_literal('active' if result.get('ready') else 'degraded')},
                next_action={sql_literal(
                    'Run research forecasts through Graph Studio; every output remains human-gated.'
                    if result.get('ready')
                    else 'Repair the pinned Kronos runtime, then rerun readiness activation.'
                )},
                metadata=coalesce(metadata,'{{}}'::jsonb) || {sql_jsonb(config_patch)},
                updated_at=now()
            WHERE module_key='kronos_research_adapter';
            """
        )
        result["registry_activated"] = bool(result.get("ready"))
    return result


def parse_as_of(value: str) -> datetime:
    raw = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        local = datetime.combine(date.fromisoformat(raw), time(23, 59, 59), tzinfo=IST)
        return local.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(timezone.utc)


def timeframe_delta(value: str) -> timedelta:
    normalized = value.strip().lower()
    aliases = {"daily": "1d", "day": "1d", "weekly": "1w", "week": "1w"}
    normalized = aliases.get(normalized, normalized)
    match = re.fullmatch(r"(\d+)(m|h|d|w)", normalized)
    if not match:
        raise ValueError(f"Unsupported timeframe: {value}")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(weeks=amount)


def next_business_day(day: date, holidays: set[date]) -> date:
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in holidays:
        candidate += timedelta(days=1)
    return candidate


def future_timestamps(
    last_timestamp: str,
    timeframe: str,
    exchange: str,
    horizon: int,
    holiday_values: list[str],
) -> list[str]:
    parsed = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(IST)
    holidays = {date.fromisoformat(value) for value in holiday_values}
    delta = timeframe_delta(timeframe)
    normalized = timeframe.lower()
    daily = normalized.endswith("d") or normalized in {"daily", "day"}
    weekly = normalized.endswith("w") or normalized in {"weekly", "week"}
    indian_exchange = exchange.upper() in {"NSE", "BSE", "NFO", "BFO", "MCX"}
    market_open = time(9, 0) if exchange.upper() == "MCX" else time(9, 15)
    market_close = time(23, 30) if exchange.upper() == "MCX" else time(15, 30)

    values: list[str] = []
    current = local
    for _ in range(horizon):
        if daily or weekly:
            steps = 5 if weekly else 1
            next_day = current.date()
            for _ in range(steps):
                next_day = next_business_day(next_day, holidays)
            current = datetime.combine(next_day, current.timetz().replace(tzinfo=None), tzinfo=IST)
        else:
            candidate = current + delta
            if indian_exchange:
                if candidate.date().weekday() >= 5 or candidate.date() in holidays:
                    next_day = candidate.date()
                    while next_day.weekday() >= 5 or next_day in holidays:
                        next_day += timedelta(days=1)
                    candidate = datetime.combine(next_day, market_open, tzinfo=IST)
                elif candidate.time() > market_close:
                    next_day = next_business_day(candidate.date(), holidays)
                    candidate = datetime.combine(next_day, market_open, tzinfo=IST)
                elif candidate.time() < market_open:
                    candidate = datetime.combine(candidate.date(), market_open, tzinfo=IST)
            current = candidate
        values.append(current.astimezone(timezone.utc).isoformat())
    return values


def source_rows(
    *,
    symbol: str,
    exchange: str,
    timeframe: str,
    as_of: datetime,
    lookback: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate = psql_one(
        f"""
        SELECT symbol.id AS symbol_id,symbol.symbol,symbol.exchange,
               count(bar.*)::INTEGER AS available_rows,max(bar.ts) AS latest_ts
        FROM trading.symbols symbol
        JOIN trading.ohlcv bar ON bar.symbol_id=symbol.id
        WHERE upper(symbol.symbol)=upper({sql_literal(symbol)})
          AND upper(symbol.exchange)=upper({sql_literal(exchange)})
          AND bar.timeframe={sql_literal(timeframe)}
          AND bar.ts<={sql_literal(as_of.isoformat())}::timestamptz
        GROUP BY symbol.id,symbol.symbol,symbol.exchange
        ORDER BY count(bar.*) DESC,max(bar.ts) DESC,symbol.id
        LIMIT 1
        """
    )
    if not candidate:
        raise ValueError(
            f"No canonical OHLCV exists for {exchange}:{symbol} at {timeframe} before {as_of.isoformat()}."
        )
    if int(candidate.get("available_rows") or 0) < lookback:
        raise ValueError(
            f"Requested lookback is {lookback}, but only {candidate.get('available_rows')} rows are available."
        )
    rows = psql_json(
        f"""
        SELECT sample.ts,sample.open,sample.high,sample.low,sample.close,sample.volume,
               sample.source_system_id
        FROM (
            SELECT bar.ts,bar.open,bar.high,bar.low,bar.close,bar.volume,
                   bar.source_system_id
            FROM trading.ohlcv bar
            WHERE bar.symbol_id={int(candidate['symbol_id'])}
              AND bar.timeframe={sql_literal(timeframe)}
              AND bar.ts<={sql_literal(as_of.isoformat())}::timestamptz
            ORDER BY bar.ts DESC
            LIMIT {lookback}
        ) sample
        ORDER BY sample.ts
        """
    )
    if len(rows) != lookback:
        raise RuntimeError("OHLCV snapshot changed while the research window was being frozen.")
    for index, row in enumerate(rows):
        for field in ("open", "high", "low", "close", "volume"):
            if row.get(field) is None:
                raise ValueError(f"Canonical OHLCV field {field} is missing at frozen row {index}.")
            number = float(row[field])
            if not math.isfinite(number):
                raise ValueError(f"Canonical OHLCV field {field} is non-finite at frozen row {index}.")
        if float(row["volume"]) < 0:
            raise ValueError(f"Canonical volume is negative at frozen row {index}.")
    return candidate, rows


def holiday_dates(exchange: str, after: str) -> list[str]:
    rows = psql_json(
        f"""
        SELECT holiday_date
        FROM market.exchange_holidays
        WHERE exchange={sql_literal(exchange.upper())}
          AND holiday_date>{sql_literal(after[:10])}::date
          AND holiday_date<={sql_literal(after[:10])}::date + interval '400 days'
          AND session_status='closed'
        ORDER BY holiday_date
        """
    )
    return [str(row["holiday_date"]) for row in rows]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_run(
    *,
    task_id: int | None,
    graph_run_id: int | None,
    graph_node_run_id: int | None,
    candidate: dict[str, Any],
    rows: list[dict[str, Any]],
    symbol: str,
    exchange: str,
    timeframe: str,
    as_of: datetime,
    lookback: int,
    horizon: int,
    path_count: int,
    model_revision: str,
    seed_base: int,
    temperature: float,
    top_p: float,
) -> dict[str, Any]:
    run_key = f"kronos-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:10]}"
    source_hash = canonical_hash(rows)
    input_contract = {
        "point_in_time": True,
        "required_columns": ["open", "high", "low", "close", "volume"],
        "missing_volume_rejected": True,
        "requested_lookback": lookback,
        "actual_rows": len(rows),
        "as_of": as_of.isoformat(),
        "research_only": True,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    return psql_one(
        f"""
        INSERT INTO strategy.kronos_forecast_runs (
            run_key,task_id,graph_run_id,graph_node_run_id,symbol_id,symbol,exchange,
            timeframe,as_of,lookback,horizon,path_count,model_variant,model_repo,
            model_revision,tokenizer_repo,tokenizer_revision,source_code_repo,
            source_code_revision,source_row_count,source_start_ts,source_end_ts,
            source_hash,seed_base,temperature,top_p,status,input_contract,started_at
        ) VALUES (
            {sql_literal(run_key)},{task_id if task_id else 'NULL'},
            {graph_run_id if graph_run_id else 'NULL'},
            {graph_node_run_id if graph_node_run_id else 'NULL'},
            {int(candidate['symbol_id'])},{sql_literal(symbol.upper())},
            {sql_literal(exchange.upper())},{sql_literal(timeframe)},
            {sql_literal(as_of.isoformat())}::timestamptz,{lookback},{horizon},{path_count},
            'mini',{sql_literal(KRONOS_MODEL_REPO)},{sql_literal(model_revision)},
            {sql_literal(KRONOS_TOKENIZER_REPO)},{sql_literal(KRONOS_TOKENIZER_REVISION)},
            {sql_literal(KRONOS_CODE_REPO)},{sql_literal(KRONOS_CODE_REVISION)},
            {len(rows)},{sql_literal(str(rows[0]['ts']))}::timestamptz,
            {sql_literal(str(rows[-1]['ts']))}::timestamptz,{sql_literal(source_hash)},
            {seed_base},{temperature},{top_p},'running',{sql_jsonb(input_contract)},now()
        )
        RETURNING id,run_key,source_hash,source_start_ts,source_end_ts
        """
    )


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a quantile from an empty list.")
    location = (len(ordered) - 1) * probability
    lower = int(math.floor(location))
    upper = int(math.ceil(location))
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def distribution_features(
    result: dict[str, Any],
    last_close: float,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    paths = result.get("paths")
    if not isinstance(paths, list) or len(paths) != int(result["path_count"]):
        raise RuntimeError("Kronos result path count does not match the requested contract.")
    flattened: list[dict[str, Any]] = []
    by_step: dict[int, list[float]] = {}
    ohlc_flags: list[bool] = []
    volume_flags: list[bool] = []
    terminal_returns: list[float] = []
    for path in paths:
        path_index = int(path["path_index"])
        points = path.get("points")
        if not isinstance(points, list) or len(points) != int(result["horizon"]):
            raise RuntimeError(f"Kronos path {path_index} has an incomplete horizon.")
        for point in points:
            close_value = float(point["close"])
            close_return = close_value / last_close - 1.0
            record = {
                **point,
                "path_index": path_index,
                "close_return": close_return,
            }
            flattened.append(record)
            by_step.setdefault(int(point["step_index"]), []).append(close_return)
            ohlc_flags.append(bool(point["ohlc_valid"]))
            volume_flags.append(bool(point["volume_valid"]))
        terminal_returns.append(float(points[-1]["close"]) / last_close - 1.0)

    step_features = []
    for step_index in sorted(by_step):
        returns = by_step[step_index]
        step_features.append(
            {
                "step_index": step_index,
                "mean_return": mean(returns),
                "p10_return": quantile(returns, 0.10),
                "p25_return": quantile(returns, 0.25),
                "median_return": quantile(returns, 0.50),
                "p75_return": quantile(returns, 0.75),
                "p90_return": quantile(returns, 0.90),
                "positive_path_share": sum(value > 0 for value in returns) / len(returns),
            }
        )
    features = {
        "feature_kind": "forecast_distribution",
        "interpretation": "Research feature only; not a trade signal.",
        "path_count": len(paths),
        "horizon": int(result["horizon"]),
        "terminal_return": {
            "mean": mean(terminal_returns),
            "p10": quantile(terminal_returns, 0.10),
            "p25": quantile(terminal_returns, 0.25),
            "median": quantile(terminal_returns, 0.50),
            "p75": quantile(terminal_returns, 0.75),
            "p90": quantile(terminal_returns, 0.90),
            "positive_path_share": sum(value > 0 for value in terminal_returns)
            / len(terminal_returns),
        },
        "steps": step_features,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    validation = {
        "path_contract_satisfied": len(paths) >= 20,
        "horizon_contract_satisfied": all(
            len(path.get("points") or []) == int(result["horizon"]) for path in paths
        ),
        "finite_output": all(
            math.isfinite(float(row[field]))
            for row in flattened
            for field in ("open", "high", "low", "close", "volume", "amount")
        ),
        "ohlc_validity": sum(ohlc_flags) / len(ohlc_flags),
        "volume_validity": sum(volume_flags) / len(volume_flags),
        "realized_calibration_pending": True,
        "independent_model_risk_review_required": True,
        "research_only": True,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    return features, validation, flattened


def persist_result(
    run: dict[str, Any],
    result: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    features, validation, flattened = distribution_features(result, float(rows[-1]["close"]))
    output_hash = canonical_hash(result)
    values = []
    for point in flattened:
        raw_output = {
            "model_open": point["open"],
            "model_high": point["high"],
            "model_low": point["low"],
            "model_close": point["close"],
            "model_volume": point["volume"],
            "model_amount": point["amount"],
        }
        values.append(
            "("
            + ",".join(
                [
                    str(int(run["id"])),
                    str(int(point["path_index"])),
                    str(int(point["step_index"])),
                    f"{sql_literal(str(point['forecast_ts']))}::timestamptz",
                    str(float(point["open"])),
                    str(float(point["high"])),
                    str(float(point["low"])),
                    str(float(point["close"])),
                    str(float(point["volume"])),
                    str(float(point["amount"])),
                    str(float(point["close_return"])),
                    str(bool(point["ohlc_valid"])).lower(),
                    str(bool(point["volume_valid"])).lower(),
                    sql_jsonb(raw_output),
                ]
            )
            + ")"
        )
    output_contract = {
        "stored_paths": int(result["path_count"]),
        "stored_points": len(flattened),
        "forecast_feature_kind": "distribution_only",
        "calibration_pending": True,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    evidence = [
        {
            "source": "trading.ohlcv",
            "source_hash": run["source_hash"],
            "source_start_ts": str(run["source_start_ts"]),
            "source_end_ts": str(run["source_end_ts"]),
        },
        {
            "source": KRONOS_CODE_REPO,
            "revision": KRONOS_CODE_REVISION,
        },
        {
            "source": f"https://huggingface.co/{KRONOS_MODEL_REPO}",
            "revision": KRONOS_MODEL_REVISION,
            "sha256": KRONOS_MODEL_SHA256,
        },
        {
            "source": f"https://huggingface.co/{KRONOS_TOKENIZER_REPO}",
            "revision": KRONOS_TOKENIZER_REVISION,
            "sha256": KRONOS_TOKENIZER_SHA256,
        },
    ]
    evaluation_end = flattened[-1]["forecast_ts"]
    psql_text(
        f"""
        BEGIN;
        INSERT INTO strategy.kronos_forecast_paths (
            forecast_run_id,path_index,step_index,forecast_ts,open,high,low,close,
            volume,amount,close_return,ohlc_valid,volume_valid,raw_output
        ) VALUES {','.join(values)};
        INSERT INTO strategy.kronos_forecast_scores (
            forecast_run_id,score_kind,evaluation_start_ts,evaluation_end_ts,
            realized_points,ohlc_validity,volume_validity,validation_status,
            feature_payload,evidence,scored_by
        ) VALUES (
            {int(run['id'])},'ex_ante_distribution',
            {sql_literal(str(flattened[0]['forecast_ts']))}::timestamptz,
            {sql_literal(str(evaluation_end))}::timestamptz,0,
            {float(validation['ohlc_validity'])},{float(validation['volume_validity'])},
            'needs_review',{sql_jsonb(features)},{sql_jsonb(evidence)},
            'kronos_inference_adapter'
        );
        UPDATE strategy.kronos_forecast_runs
        SET status='completed',device={sql_literal(str(result['device']))},
            output_hash={sql_literal(output_hash)},
            output_contract={sql_jsonb(output_contract)},
            validation={sql_jsonb(validation)},evidence={sql_jsonb(evidence)},
            error='{{}}'::jsonb,finished_at=now(),updated_at=now()
        WHERE id={int(run['id'])};
        COMMIT;
        """
    )
    return {
        "forecast_run_id": int(run["id"]),
        "run_key": run["run_key"],
        "status": "completed",
        "symbol": result.get("symbol"),
        "device": result["device"],
        "path_count": int(result["path_count"]),
        "horizon": int(result["horizon"]),
        "stored_points": len(flattened),
        "source_hash": run["source_hash"],
        "output_hash": output_hash,
        "features": features,
        "validation": validation,
        "evidence": evidence,
        "research_only": True,
        "direct_signal": False,
        "broker_order_allowed": False,
        "elapsed_seconds": result.get("elapsed_seconds"),
    }


def mark_failed(run_id: int, exc: Exception) -> None:
    failure = {
        "kind": type(exc).__name__,
        "message": str(exc)[:2000],
        "synthetic_fallback_used": False,
        "broker_order_allowed": False,
    }
    psql_text(
        f"""
        UPDATE strategy.kronos_forecast_runs
        SET status='failed',error={sql_jsonb(failure)},finished_at=now(),updated_at=now()
        WHERE id={int(run_id)}
        """
    )


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    payload = json.loads(arguments.payload_json) if arguments.payload_json else {}
    symbol = str(payload.get("symbol") or arguments.symbol or "").strip().upper()
    exchange = str(payload.get("exchange") or arguments.exchange or "NSE").strip().upper()
    timeframe = str(payload.get("timeframe") or arguments.timeframe or "1d").strip().lower()
    as_of_value = str(payload.get("as_of") or arguments.as_of or date.today().isoformat())
    lookback = int(payload.get("lookback") or arguments.lookback or 512)
    horizon = int(payload.get("horizon") or arguments.horizon or 5)
    path_count = int(payload.get("path_count") or payload.get("paths") or arguments.path_count or 20)
    model_revision = str(
        payload.get("model_revision") or arguments.model_revision or KRONOS_MODEL_REVISION
    )
    temperature = float(payload.get("temperature") or arguments.temperature or 1.0)
    top_p = float(payload.get("top_p") or arguments.top_p or 0.9)
    seed_base = int(payload.get("seed_base") or arguments.seed_base or 20260729)

    if not symbol:
        raise ValueError("symbol is required.")
    if model_revision != KRONOS_MODEL_REVISION:
        raise ValueError(
            f"model_revision must equal the pinned revision {KRONOS_MODEL_REVISION}."
        )
    if not 32 <= lookback <= 2048:
        raise ValueError("lookback must be between 32 and 2048.")
    if not 1 <= horizon <= 256:
        raise ValueError("horizon must be between 1 and 256.")
    if not 20 <= path_count <= 256:
        raise ValueError("path_count must be between 20 and 256.")
    if not 0 < top_p <= 1 or not 0 < temperature <= 5:
        raise ValueError("temperature and top_p are outside the allowed range.")

    as_of = parse_as_of(as_of_value)
    candidate, rows = source_rows(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        as_of=as_of,
        lookback=lookback,
    )
    holidays = holiday_dates(exchange, str(rows[-1]["ts"]))
    y_timestamps = future_timestamps(
        str(rows[-1]["ts"]), timeframe, exchange, horizon, holidays
    )
    run = create_run(
        task_id=arguments.task_id,
        graph_run_id=arguments.graph_run_id,
        graph_node_run_id=arguments.graph_node_run_id,
        candidate=candidate,
        rows=rows,
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        as_of=as_of,
        lookback=lookback,
        horizon=horizon,
        path_count=path_count,
        model_revision=model_revision,
        seed_base=seed_base,
        temperature=temperature,
        top_p=top_p,
    )
    request = {
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "as_of": as_of.isoformat(),
        "lookback": lookback,
        "horizon": horizon,
        "path_count": path_count,
        "model_revision": model_revision,
        "temperature": temperature,
        "top_p": top_p,
        "seed_base": seed_base,
        "rows": rows,
        "future_timestamps": y_timestamps,
        "research_only": True,
        "direct_signal": False,
        "broker_order_allowed": False,
    }
    temp_root = runtime_home() / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    request_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="kronos-request-",
            dir=temp_root,
            delete=False,
        ) as handle:
            json.dump(request, handle, sort_keys=True)
            request_path = Path(handle.name)
        inference = run_isolated("--request", str(request_path))
        inference["symbol"] = symbol
        return persist_result(run, inference, rows)
    except Exception as exc:
        mark_failed(int(run["id"]), exc)
        raise
    finally:
        if request_path and request_path.exists():
            request_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a governed Kronos research forecast.")
    parser.add_argument("--readiness", action="store_true")
    parser.add_argument("--activate-tool", action="store_true")
    parser.add_argument("--payload-json")
    parser.add_argument("--symbol")
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--as-of")
    parser.add_argument("--lookback", type=int, default=512)
    parser.add_argument("--horizon", type=int, default=5)
    parser.add_argument("--path-count", type=int, default=20)
    parser.add_argument("--model-revision", default=KRONOS_MODEL_REVISION)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--seed-base", type=int, default=20260729)
    parser.add_argument("--task-id", type=int)
    parser.add_argument("--graph-run-id", type=int)
    parser.add_argument("--graph-node-run-id", type=int)
    arguments = parser.parse_args()

    try:
        result = (
            readiness(activate_tool=arguments.activate_tool)
            if arguments.readiness
            else execute(arguments)
        )
        print(json.dumps(result, sort_keys=True, default=str))
        return 0 if result.get("ready", True) else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "research_only": True,
                    "synthetic_fallback_used": False,
                    "broker_order_allowed": False,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
