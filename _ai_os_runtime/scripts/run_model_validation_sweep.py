#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from runtime_storage import artifact_reference, artifact_root
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_strategy_quant_analytics import sql_text_array


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = artifact_root("model_validation")


def fetch_rows(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def classify(row: dict[str, Any]) -> dict[str, Any]:
    required_fixes: list[str] = []
    issues: list[dict[str, Any]] = []

    if not row.get("latest_backtest_run_id"):
        required_fixes.append("Run deterministic backtest")
        issues.append({"severity": "high", "issue": "missing_backtest"})
    if row.get("parse_status") != "passed":
        required_fixes.append("Repair strategy DSL until parser passes")
        issues.append({"severity": "high", "issue": "dsl_not_passed", "value": row.get("parse_status")})
    if row.get("data_quality_status") != "passed":
        required_fixes.append("Pass data-quality gate before model approval")
        issues.append({"severity": "high", "issue": "data_quality_not_passed", "value": row.get("data_quality_status")})

    optimization_metrics = row.get("latest_optimization_metrics") if isinstance(row.get("latest_optimization_metrics"), dict) else {}
    optimization_diagnostics = row.get("latest_optimization_diagnostics") if isinstance(row.get("latest_optimization_diagnostics"), dict) else {}
    warnings = optimization_diagnostics.get("warnings") if isinstance(optimization_diagnostics, dict) else None
    if isinstance(warnings, list) and warnings:
        required_fixes.append("Resolve optimizer warnings and rerun validation")
        issues.append({"severity": "medium", "issue": "optimizer_warnings", "warnings": warnings[:5]})

    wf_consistency = optimization_metrics.get("best_walk_forward_consistency") if isinstance(optimization_metrics, dict) else None
    if isinstance(wf_consistency, (int, float)) and wf_consistency <= 0:
        required_fixes.append("Improve walk-forward consistency above zero")
        issues.append({"severity": "high", "issue": "walk_forward_consistency_zero", "value": wf_consistency})

    best_sharpe = optimization_metrics.get("best_test_sharpe") if isinstance(optimization_metrics, dict) else None
    if isinstance(best_sharpe, (int, float)) and best_sharpe < 0:
        required_fixes.append("Reject or redesign negative test-Sharpe configuration")
        issues.append({"severity": "high", "issue": "negative_test_sharpe", "value": best_sharpe})

    retirement_action = row.get("retirement_recommended_action")
    if retirement_action in {"needs_more_data", "pause_paper", "retire"}:
        required_fixes.append(f"Resolve retirement review action: {retirement_action}")
        issues.append({"severity": "medium", "issue": "retirement_review_not_clear", "value": retirement_action})

    if not required_fixes:
        decision = "approve_for_committee_review"
        review_status = "completed"
        leakage_risk = "low"
        overfit_risk = "medium"
    elif any(issue["severity"] == "high" for issue in issues):
        decision = "reject_or_retest"
        review_status = "needs_review"
        leakage_risk = "unchecked" if row.get("data_quality_status") != "passed" else "medium"
        overfit_risk = "high"
    else:
        decision = "blocked_until_broader_sample"
        review_status = "needs_review"
        leakage_risk = "medium"
        overfit_risk = "medium"

    return {
        "decision": decision,
        "review_status": review_status,
        "leakage_risk": leakage_risk,
        "overfit_risk": overfit_risk,
        "required_fixes": list(dict.fromkeys(required_fixes)),
        "issues": issues,
    }


def upsert_validation(row: dict[str, Any], classification: dict[str, Any], key_prefix: str, actor: str) -> dict[str, Any]:
    validation_key = f"{key_prefix}_{row['candidate_key']}".replace(" ", "_").lower()
    evidence = [
        {"source": "strategy.v_model_validation_dashboard", "strategy_id": row.get("strategy_id")},
        {"source": "strategy.backtest_runs", "id": row.get("latest_backtest_run_id")},
        {"source": "strategy.optimization_runs", "id": row.get("latest_optimization_run_id")},
        {"source": "strategy.v_strategy_retirement_queue", "review_key": row.get("retirement_review_key")},
        {"live_execution_allowed": False, "seed_data_allowed": False},
    ]
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.validation_reviews (
                validation_key, strategy_id, backtest_run_id, optimization_run_id,
                reviewer_agent, review_status, decision, leakage_risk, overfit_risk,
                transaction_cost_notes, sample_size_notes, required_fixes,
                issues, evidence, updated_at
            )
            VALUES (
                {sql_literal(validation_key)},
                {int(row["strategy_id"])},
                {int(row["latest_backtest_run_id"]) if row.get("latest_backtest_run_id") else 'NULL'},
                {int(row["latest_optimization_run_id"]) if row.get("latest_optimization_run_id") else 'NULL'},
                {sql_literal(actor)},
                {sql_literal(classification["review_status"])},
                {sql_literal(classification["decision"])},
                {sql_literal(classification["leakage_risk"])},
                {sql_literal(classification["overfit_risk"])},
                {sql_literal("Costs/slippage must remain in backtest and optimizer evidence before promotion.")},
                {sql_literal("Sample depth, DSL, and data-quality gate reviewed by deterministic sweep.")},
                {sql_text_array(classification["required_fixes"])},
                {sql_jsonb(classification["issues"])},
                {sql_jsonb(evidence)},
                now()
            )
            ON CONFLICT (validation_key) DO UPDATE SET
                strategy_id = EXCLUDED.strategy_id,
                backtest_run_id = EXCLUDED.backtest_run_id,
                optimization_run_id = EXCLUDED.optimization_run_id,
                reviewer_agent = EXCLUDED.reviewer_agent,
                review_status = EXCLUDED.review_status,
                decision = EXCLUDED.decision,
                leakage_risk = EXCLUDED.leakage_risk,
                overfit_risk = EXCLUDED.overfit_risk,
                transaction_cost_notes = EXCLUDED.transaction_cost_notes,
                sample_size_notes = EXCLUDED.sample_size_notes,
                required_fixes = EXCLUDED.required_fixes,
                issues = EXCLUDED.issues,
                evidence = EXCLUDED.evidence,
                updated_at = now()
            RETURNING id, validation_key, strategy_id, review_status, decision, required_fixes, updated_at
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    result = rows[0]
    result["candidate_key"] = row.get("candidate_key")
    result["strategy_name"] = row.get("strategy_name")
    return result


def run_sweep(args: argparse.Namespace) -> dict[str, Any]:
    rows = fetch_rows(
        f"""
        SELECT *
        FROM strategy.v_model_validation_dashboard
        ORDER BY updated_at DESC, strategy_id DESC
        LIMIT {max(1, int(args.limit))}
        """
    )
    reviewed = []
    for row in rows:
        classification = classify(row)
        reviewed.append(upsert_validation(row, classification, args.validation_key_prefix, args.actor))

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_count": len(reviewed),
        "reviewed": reviewed,
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    path = ARTIFACT_ROOT / f"{args.validation_key_prefix}.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
    artifact["artifact_path"] = artifact_reference(path)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic model-validation sweep over strategy evidence.")
    parser.add_argument("--validation-key-prefix", default="modelval")
    parser.add_argument("--actor", default="Model Validation Agent")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(run_sweep(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
