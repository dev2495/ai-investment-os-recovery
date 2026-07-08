#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_trade_journal_strategy_mining import sql_text_array


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = RUNTIME_ROOT.parent
ARTIFACT_ROOT = RUNTIME_ROOT / "artifacts" / "user_defined_optimizer"


def parse_symbols(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def default_dsl(strategy_name: str, symbols: list[str], timeframe: str, template: str, intake_text: str) -> str:
    if template == "mean_reversion":
        entry = "zscore(close, 20) < -1.0"
        exit_rule = "zscore(close, 20) > 0 or holding_days >= 10"
    elif template == "breakout":
        entry = "close > sma(close, 12) * 1.002"
        exit_rule = "close < sma(close, 12) or holding_days >= 10"
    elif template == "low_volatility":
        entry = "atr(14) < sma(atr(14), 20) and close > sma(close, 20)"
        exit_rule = "close < sma(close, 20) or holding_days >= 10"
    else:
        entry = "close > sma(close, 12)"
        exit_rule = "close < sma(close, 12) or holding_days >= 10"
    lines = [
        f"Name: {strategy_name}",
        f"Template: {template}",
        f"Timeframe: {timeframe}",
    ]
    if symbols:
        lines.append("Symbols: " + ", ".join(symbols))
    lines.extend(
        [
            f"Entry: {entry}",
            f"Exit: {exit_rule}",
            "Risk: stop_loss_pct <= 2 and target_pct >= 3",
            f"Notes: {intake_text[:280]}",
        ]
    )
    return "\n".join(lines)


def create_workflow_run(args: argparse.Namespace, symbols: list[str]) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.user_defined_optimizer_runs (
                run_key, strategy_name, status, current_stage, requested_template,
                requested_timeframe, requested_symbols, created_by, started_at
            )
            VALUES (
                {sql_literal(args.run_key)},
                {sql_literal(args.strategy_name)},
                'running',
                'intake',
                {sql_literal(args.template)},
                {sql_literal(args.timeframe)},
                {sql_text_array(symbols)},
                {sql_literal(args.actor)},
                now()
            )
            ON CONFLICT (run_key) DO UPDATE SET
                strategy_name = EXCLUDED.strategy_name,
                status = 'running',
                current_stage = 'intake',
                requested_template = EXCLUDED.requested_template,
                requested_timeframe = EXCLUDED.requested_timeframe,
                requested_symbols = EXCLUDED.requested_symbols,
                stage_results = '{{}}'::jsonb,
                failure_reason = NULL,
                artifact_path = NULL,
                created_by = EXCLUDED.created_by,
                started_at = now(),
                finished_at = NULL
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    return rows[0]


def update_run(run_id: int, **fields: Any) -> None:
    assignments: list[str] = []
    if "status" in fields:
        assignments.append(f"status = {sql_literal(fields['status'])}")
    if "current_stage" in fields:
        assignments.append(f"current_stage = {sql_literal(fields['current_stage'])}")
    if "intake_id" in fields:
        assignments.append(f"intake_id = {int(fields['intake_id']) if fields['intake_id'] is not None else 'NULL'}")
    if "candidate_id" in fields:
        assignments.append(f"candidate_id = {int(fields['candidate_id']) if fields['candidate_id'] is not None else 'NULL'}")
    if "backtest_run_id" in fields:
        assignments.append(f"backtest_run_id = {int(fields['backtest_run_id']) if fields['backtest_run_id'] is not None else 'NULL'}")
    if "optimization_run_id" in fields:
        assignments.append(f"optimization_run_id = {int(fields['optimization_run_id']) if fields['optimization_run_id'] is not None else 'NULL'}")
    if "stage_results" in fields:
        assignments.append(f"stage_results = {sql_jsonb(fields['stage_results'])}")
    if "failure_reason" in fields:
        assignments.append(f"failure_reason = {sql_literal(fields['failure_reason'])}")
    if "artifact_path" in fields:
        assignments.append(f"artifact_path = {sql_literal(fields['artifact_path'])}")
    if fields.get("finished"):
        assignments.append("finished_at = now()")
    if not assignments:
        return
    run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.user_defined_optimizer_runs
            SET {', '.join(assignments)}
            WHERE id = {int(run_id)}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(updated)), '[]'::json)::text FROM updated
        """
    )


def create_intake(args: argparse.Namespace, symbols: list[str]) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT strategy.create_strategy_arsenal_intake(
                {sql_literal(args.actor)},
                {sql_literal(args.intake_text)},
                {sql_literal(args.strategy_name)},
                'user_defined_quant',
                {sql_literal(args.asset_class)},
                {sql_text_array(symbols)},
                {sql_literal(args.universe)},
                {sql_literal(args.timeframe)},
                ARRAY['user_defined','optimizer_workflow','paper_first']::TEXT[],
                {sql_literal(args.constraints_text)},
                {sql_literal(args.risk_notes)},
                ARRAY['parse_dsl','data_quality_gate','baseline_backtest','parameter_optimization','model_validation']::TEXT[],
                'user_defined_optimizer',
                {sql_literal(args.run_key)}
            ) AS result
        ) rows
        """
    )
    if not rows:
        raise RuntimeError("strategy intake creation returned no rows")
    return rows[0]["result"]


def run_command(command: list[str], timeout: int = 240) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=VAULT_ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "command failed").strip()
        try:
            parsed = json.loads(message)
            message = parsed.get("message") or parsed.get("error") or message
        except json.JSONDecodeError:
            pass
        raise RuntimeError(message)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command returned invalid JSON: {completed.stdout[:500]}") from exc


def run_workflow(args: argparse.Namespace) -> dict[str, Any]:
    symbols = parse_symbols(args.symbols)
    run = create_workflow_run(args, symbols)
    run_id = int(run["id"])
    stage_results: dict[str, Any] = {}
    candidate_id: int | None = None
    artifact_rel: str | None = None
    try:
        intake = create_intake(args, symbols)
        candidate_id = int(intake["candidate_id"])
        stage_results["intake"] = intake
        update_run(run_id, current_stage="parse", intake_id=intake["intake_id"], candidate_id=candidate_id, stage_results=stage_results)

        dsl_text = args.dsl_text.strip() or default_dsl(args.strategy_name, symbols, args.timeframe, args.template, args.intake_text)
        parse = run_command(
            [
                sys.executable,
                str(RUNTIME_ROOT / "scripts" / "strategy_dsl_quality.py"),
                "--candidate-id",
                str(candidate_id),
                "--parse",
                "--dsl-text",
                dsl_text,
                "--actor",
                "Strategy Intake Agent",
            ],
            timeout=120,
        )
        stage_results["parse"] = parse
        update_run(run_id, current_stage="data_quality", stage_results=stage_results)

        min_total_rows = args.min_total_rows if args.min_total_rows is not None else (50 if symbols else 500)
        gate_command = [
            sys.executable,
            str(RUNTIME_ROOT / "scripts" / "strategy_dsl_quality.py"),
            "--candidate-id",
            str(candidate_id),
            "--gate",
            "--timeframe",
            args.timeframe,
            "--min-rows-per-symbol",
            str(args.min_rows_per_symbol),
            "--min-total-rows",
            str(min_total_rows),
            "--actor",
            "Backtest Engineer",
        ]
        if symbols:
            gate_command.extend(["--symbols", ",".join(symbols)])
        gate = run_command(gate_command, timeout=120)
        stage_results["data_quality"] = gate
        if (gate.get("gate") or {}).get("status") != "passed":
            raise RuntimeError("data-quality gate failed: " + "; ".join((gate.get("gate") or {}).get("reasons") or []))
        update_run(run_id, current_stage="backtest", stage_results=stage_results)

        backtest_command = [
            sys.executable,
            str(RUNTIME_ROOT / "scripts" / "run_strategy_backtest.py"),
            "--candidate-id",
            str(candidate_id),
            "--timeframe",
            args.timeframe,
            "--template",
            args.template,
            "--cost-bps",
            str(args.cost_bps),
            "--slippage-bps",
            str(args.slippage_bps),
            "--max-symbols",
            str(args.max_symbols),
            "--min-rows-per-symbol",
            str(args.min_rows_per_symbol),
            "--min-total-rows",
            str(min_total_rows),
        ]
        if symbols:
            backtest_command.extend(["--symbols", ",".join(symbols)])
        backtest = run_command(backtest_command, timeout=240)
        stage_results["backtest"] = {
            "status": backtest.get("status"),
            "database": backtest.get("database"),
            "metrics": backtest.get("metrics"),
            "artifact_path": backtest.get("artifact_path"),
            "note_path": backtest.get("note_path"),
            "diagnostics": {
                "warnings": (backtest.get("diagnostics") or {}).get("warnings"),
                "live_execution_allowed": (backtest.get("diagnostics") or {}).get("live_execution_allowed"),
            },
        }
        backtest_run_id = ((backtest.get("database") or {}).get("backtest_run_id"))
        update_run(run_id, current_stage="optimization", backtest_run_id=backtest_run_id, stage_results=stage_results)

        optimize_command = [
            sys.executable,
            str(RUNTIME_ROOT / "scripts" / "run_strategy_optimizer.py"),
            "--candidate-id",
            str(candidate_id),
            "--timeframe",
            args.timeframe,
            "--template",
            args.template,
            "--cost-bps",
            str(args.cost_bps),
            "--slippage-bps",
            str(args.slippage_bps),
            "--max-symbols",
            str(args.max_symbols),
        ]
        if symbols:
            optimize_command.extend(["--symbols", ",".join(symbols)])
        optimization = run_command(optimize_command, timeout=300)
        stage_results["optimization"] = {
            "status": optimization.get("status"),
            "database": optimization.get("database"),
            "metrics": optimization.get("metrics"),
            "best_params": optimization.get("best_params"),
            "artifact_path": optimization.get("artifact_path"),
            "note_path": optimization.get("note_path"),
            "diagnostics": {
                "warnings": (optimization.get("diagnostics") or {}).get("warnings"),
                "live_execution_allowed": (optimization.get("diagnostics") or {}).get("live_execution_allowed"),
            },
        }
        optimization_run_id = ((optimization.get("database") or {}).get("optimization_run_id"))

        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_key": args.run_key,
            "status": "completed",
            "candidate_id": candidate_id,
            "stage_results": stage_results,
            "live_execution_allowed": False,
            "seed_data_allowed": False,
        }
        artifact_path = ARTIFACT_ROOT / f"{args.run_key}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
        artifact_rel = str(artifact_path.relative_to(RUNTIME_ROOT))
        update_run(
            run_id,
            status="completed",
            current_stage="completed",
            optimization_run_id=optimization_run_id,
            stage_results=stage_results,
            artifact_path=artifact_rel,
            finished=True,
        )
        artifact["artifact_path"] = artifact_rel
        artifact["workflow_run_id"] = run_id
        return artifact
    except Exception as exc:  # noqa: BLE001
        stage_results["failure"] = {"stage": stage_results.keys().__repr__(), "message": str(exc)}
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_key": args.run_key,
            "status": "failed",
            "candidate_id": candidate_id,
            "stage_results": stage_results,
            "failure_reason": str(exc),
            "live_execution_allowed": False,
            "seed_data_allowed": False,
        }
        artifact_path = ARTIFACT_ROOT / f"{args.run_key}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
        artifact_rel = str(artifact_path.relative_to(RUNTIME_ROOT))
        update_run(
            run_id,
            status="failed",
            current_stage="failed",
            stage_results=stage_results,
            failure_reason=str(exc),
            artifact_path=artifact_rel,
            finished=True,
        )
        artifact["artifact_path"] = artifact_rel
        artifact["workflow_run_id"] = run_id
        return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and optimize a user-defined strategy through the safe research pipeline.")
    parser.add_argument("--run-key", default=f"user_strategy_opt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    parser.add_argument("--actor", default="Devarsh")
    parser.add_argument("--strategy-name", required=True)
    parser.add_argument("--intake-text", required=True)
    parser.add_argument("--dsl-text", default="")
    parser.add_argument("--asset-class", default="equity")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--universe", default="NSE")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--template", choices=["momentum", "mean_reversion", "breakout", "low_volatility"], default="momentum")
    parser.add_argument("--constraints-text", default="Paper-first research only. No live execution.")
    parser.add_argument("--risk-notes", default="Requires parser, data-quality, backtest, optimizer, model-validation, and committee approval.")
    parser.add_argument("--cost-bps", type=float, default=3.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--max-symbols", type=int, default=14)
    parser.add_argument("--min-rows-per-symbol", type=int, default=50)
    parser.add_argument("--min-total-rows", type=int)
    args = parser.parse_args()
    result = run_workflow(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
