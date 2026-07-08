#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal
from run_strategy_quant_analytics import sql_text_array


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = RUNTIME_ROOT / "artifacts" / "strategy_retirement"


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


def latest_analytics(run_key: str | None) -> dict[str, Any]:
    where = f"WHERE run_key = {sql_literal(run_key)}" if run_key else "WHERE status = 'completed'"
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, run_key, strategy_ids, timeframe, metrics, diagnostics, quality_flags, finished_at
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


def latest_allocation(allocation_key: str | None, analytics_run_id: int) -> dict[str, Any] | None:
    where = f"WHERE allocation_key = {sql_literal(allocation_key)}" if allocation_key else f"WHERE analytics_run_id = {analytics_run_id} AND status = 'completed'"
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT id, allocation_key, analytics_run_id, optimizer_run_id, quality_flags, constraints,
                   diagnostics, created_at
            FROM strategy.strategy_portfolio_allocation_runs
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ) rows
        """
    )
    return rows[0] if rows else None


def fetch_rows(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def fetch_candidate_evidence(analytics_run_id: int, allocation_run_id: int | None) -> dict[int, dict[str, Any]]:
    candidates = fetch_rows(
        f"""
        SELECT candidate.id AS strategy_id,
               coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
               candidate.name AS strategy_name,
               candidate.status AS candidate_status,
               candidate.validation_status,
               candidate.activation_gate,
               dsl.parse_status,
               dsl.data_quality_status,
               dsl.data_quality_reasons,
               dsl.total_rows,
               dsl.min_symbol_rows
        FROM strategy.strategy_candidates candidate
        JOIN strategy.quant_analytics_runs run ON candidate.id = ANY(run.strategy_ids)
        LEFT JOIN strategy.v_strategy_dsl_readiness_summary dsl ON dsl.candidate_id = candidate.id
        WHERE run.id = {analytics_run_id}
        ORDER BY candidate.id
        """
    )
    evidence = {int(row["strategy_id"]): dict(row) for row in candidates}
    series_rows = fetch_rows(
        f"""
        SELECT strategy_id,
               count(*)::INTEGER AS return_bars,
               avg(return_value)::FLOAT8 AS average_return,
               stddev_pop(return_value)::FLOAT8 AS volatility,
               (sum(CASE WHEN return_value > 0 THEN 1 ELSE 0 END)::FLOAT8 / nullif(count(*), 0))::FLOAT8 AS win_rate,
               min(return_value)::FLOAT8 AS worst_bar_return,
               max(return_value)::FLOAT8 AS best_bar_return
        FROM strategy.strategy_return_series
        WHERE analytics_run_id = {analytics_run_id}
        GROUP BY strategy_id
        """
    )
    for row in series_rows:
        evidence.setdefault(int(row["strategy_id"]), {})["return_series"] = row
    regime_rows = fetch_rows(
        f"""
        SELECT DISTINCT ON (strategy_id)
               strategy_id, regime_type, regime_label, bars, total_return::FLOAT8 AS total_return,
               max_drawdown::FLOAT8 AS max_drawdown, win_rate::FLOAT8 AS win_rate
        FROM strategy.regime_performance_splits
        WHERE analytics_run_id = {analytics_run_id}
        ORDER BY strategy_id, total_return ASC NULLS LAST, bars DESC
        """
    )
    for row in regime_rows:
        evidence.setdefault(int(row["strategy_id"]), {})["weakest_regime"] = row
    capacity_rows = fetch_rows(
        f"""
        SELECT DISTINCT ON (strategy_id)
               strategy_id, symbol, liquidity_status, average_traded_value::FLOAT8 AS average_traded_value,
               capacity_notional::FLOAT8 AS capacity_notional, participation_rate::FLOAT8 AS participation_rate
        FROM strategy.capacity_liquidity_checks
        WHERE analytics_run_id = {analytics_run_id}
        ORDER BY strategy_id,
            CASE liquidity_status WHEN 'thin' THEN 1 WHEN 'limited' THEN 2 WHEN 'ok' THEN 3 ELSE 4 END,
            capacity_notional ASC NULLS LAST
        """
    )
    for row in capacity_rows:
        evidence.setdefault(int(row["strategy_id"]), {})["capacity"] = row
    if allocation_run_id:
        allocation_rows = fetch_rows(
            f"""
            SELECT strategy_id, target_weight::FLOAT8 AS target_weight, target_notional::FLOAT8 AS target_notional,
                   expected_return::FLOAT8 AS expected_return, expected_volatility::FLOAT8 AS expected_volatility,
                   risk_contribution::FLOAT8 AS risk_contribution, allocation_status, diagnostics
            FROM strategy.strategy_portfolio_allocations
            WHERE allocation_run_id = {allocation_run_id}
            """
        )
        for row in allocation_rows:
            evidence.setdefault(int(row["strategy_id"]), {})["allocation"] = row
        ruin_rows = fetch_rows(
            f"""
            SELECT strategy_id, ruin_probability::FLOAT8 AS ruin_probability,
                   max_drawdown_p95::FLOAT8 AS max_drawdown_p95,
                   quality_flags
            FROM strategy.probability_of_ruin_metrics
            WHERE allocation_run_id = {allocation_run_id}
              AND strategy_id IS NOT NULL
            """
        )
        for row in ruin_rows:
            evidence.setdefault(int(row["strategy_id"]), {})["ruin"] = row
    return evidence


def classify_review(row: dict[str, Any], analytics_flags: list[str], allocation_flags: list[str]) -> dict[str, Any]:
    reasons: list[str] = []
    assignments: set[str] = set()
    series = row.get("return_series") or {}
    allocation = row.get("allocation") or {}
    ruin = row.get("ruin") or {}
    capacity = row.get("capacity") or {}
    weakest_regime = row.get("weakest_regime") or {}

    parse_status = str(row.get("parse_status") or "not_parsed")
    data_quality_status = str(row.get("data_quality_status") or "not_checked")
    return_bars = int(series.get("return_bars") or 0)
    average_return = series.get("average_return")
    win_rate = series.get("win_rate")
    target_weight = float(allocation.get("target_weight") or 0)
    ruin_probability = ruin.get("ruin_probability")
    liquidity_status = str(capacity.get("liquidity_status") or "")
    weakest_total_return = weakest_regime.get("total_return")

    if parse_status != "passed":
        reasons.append("missing_passed_dsl")
        assignments.add("Feature Engineer")
    if data_quality_status not in {"passed", "ok"}:
        reasons.append("data_quality_not_passed")
        assignments.add("Data Scientist")
    if "thin_return_history" in analytics_flags or return_bars < 250:
        reasons.append("thin_return_history")
        assignments.add("Data Scientist")
    if "some_strategies_missing_passed_dsl" in analytics_flags:
        assignments.add("Feature Engineer")
    if target_weight <= 0:
        reasons.append("zero_target_weight")
        assignments.add("Capacity/Liquidity Analyst")
    if isinstance(average_return, (int, float)) and average_return < 0:
        reasons.append("negative_average_return")
        assignments.add("Data Scientist")
    if isinstance(win_rate, (int, float)) and win_rate < 0.45:
        reasons.append("low_win_rate")
        assignments.add("Data Scientist")
    if isinstance(weakest_total_return, (int, float)) and weakest_total_return < 0:
        reasons.append("regime_underperformance")
        assignments.add("Regime Analyst")
    if liquidity_status in {"thin", "limited"}:
        reasons.append(f"{liquidity_status}_liquidity")
        assignments.add("Capacity/Liquidity Analyst")
    if isinstance(ruin_probability, (int, float)) and ruin_probability > 0.05:
        reasons.append("ruin_probability_above_limit")
        assignments.update({"Data Scientist", "Regime Analyst", "Capacity/Liquidity Analyst"})
    if "thin_portfolio_return_history" in allocation_flags:
        assignments.add("Data Scientist")

    if "ruin_probability_above_limit" in reasons:
        recommended_action = "pause_paper"
        severity = "high"
    elif "missing_passed_dsl" in reasons or "data_quality_not_passed" in reasons:
        recommended_action = "needs_more_data"
        severity = "medium"
    elif "zero_target_weight" in reasons and ("negative_average_return" in reasons or "low_win_rate" in reasons):
        recommended_action = "pause_paper"
        severity = "high"
    elif "zero_target_weight" in reasons:
        recommended_action = "watch"
        severity = "medium"
    elif "thin_return_history" in reasons:
        recommended_action = "watch"
        severity = "low"
    elif reasons:
        recommended_action = "watch"
        severity = "medium"
    else:
        recommended_action = "keep"
        severity = "low"

    if recommended_action in {"pause_paper", "retire"}:
        assignments.add("Strategy Generator")
        reasons.append("replacement_or_research_needed")

    if not assignments:
        assignments.add("Data Scientist")

    unique_reasons = list(dict.fromkeys(reasons or ["routine_retirement_review"]))
    return {
        "recommended_action": recommended_action,
        "severity": severity,
        "trigger_reasons": unique_reasons,
        "assigned_agents": sorted(assignments),
    }


def create_or_update_review(
    review_key: str,
    row: dict[str, Any],
    analytics_run: dict[str, Any],
    allocation_run: dict[str, Any] | None,
    classification: dict[str, Any],
    actor: str,
) -> int:
    evidence = {
        "strategy": {
            "candidate_key": row.get("candidate_key"),
            "strategy_name": row.get("strategy_name"),
            "candidate_status": row.get("candidate_status"),
            "validation_status": row.get("validation_status"),
            "activation_gate": row.get("activation_gate"),
        },
        "dsl": {
            "parse_status": row.get("parse_status"),
            "data_quality_status": row.get("data_quality_status"),
            "data_quality_reasons": row.get("data_quality_reasons"),
            "total_rows": row.get("total_rows"),
            "min_symbol_rows": row.get("min_symbol_rows"),
        },
        "return_series": row.get("return_series"),
        "weakest_regime": row.get("weakest_regime"),
        "capacity": row.get("capacity"),
        "allocation": row.get("allocation"),
        "ruin": row.get("ruin"),
        "analytics_run": {"id": analytics_run["id"], "run_key": analytics_run["run_key"], "quality_flags": analytics_run.get("quality_flags")},
        "allocation_run": allocation_run,
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    allocation_id = int(allocation_run["id"]) if allocation_run else None
    optimizer_id = int(allocation_run["optimizer_run_id"]) if allocation_run and allocation_run.get("optimizer_run_id") else None
    rows = run_psql_json(
        f"""
        WITH upserted AS (
            INSERT INTO strategy.strategy_retirement_reviews (
                review_key, strategy_id, analytics_run_id, allocation_run_id, optimizer_run_id,
                review_status, recommended_action, severity, trigger_source, trigger_reasons,
                assigned_agents, evidence, created_by, updated_at
            )
            VALUES (
                {sql_literal(review_key)}, {int(row["strategy_id"])}, {int(analytics_run["id"])},
                {allocation_id if allocation_id else 'NULL'}, {optimizer_id if optimizer_id else 'NULL'},
                'open', {sql_literal(classification["recommended_action"])}, {sql_literal(classification["severity"])},
                'quant_lab_retirement_review', {sql_text_array(classification["trigger_reasons"])},
                {sql_text_array(classification["assigned_agents"])}, {sql_jsonb(evidence)}, {sql_literal(actor)}, now()
            )
            ON CONFLICT (review_key) DO UPDATE SET
                strategy_id = EXCLUDED.strategy_id,
                analytics_run_id = EXCLUDED.analytics_run_id,
                allocation_run_id = EXCLUDED.allocation_run_id,
                optimizer_run_id = EXCLUDED.optimizer_run_id,
                review_status = CASE
                    WHEN strategy.strategy_retirement_reviews.human_decision IS NOT NULL THEN strategy.strategy_retirement_reviews.review_status
                    ELSE 'open'
                END,
                recommended_action = EXCLUDED.recommended_action,
                severity = EXCLUDED.severity,
                trigger_source = EXCLUDED.trigger_source,
                trigger_reasons = EXCLUDED.trigger_reasons,
                assigned_agents = EXCLUDED.assigned_agents,
                evidence = EXCLUDED.evidence,
                created_by = EXCLUDED.created_by,
                updated_at = now()
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
        """
    )
    if not rows:
        raise RuntimeError(f"Failed to upsert retirement review {review_key}")
    return int(rows[0]["id"])


def assignment_type_for_agent(agent_name: str, classification: dict[str, Any]) -> str:
    if agent_name == "Data Scientist":
        return "data_science_review"
    if agent_name == "Feature Engineer":
        return "feature_engineering_review"
    if agent_name == "Regime Analyst":
        return "regime_review"
    if agent_name == "Capacity/Liquidity Analyst":
        return "capacity_liquidity_review"
    if agent_name == "Strategy Generator":
        return "replacement_strategy_research"
    return "specialist_review"


def upsert_assignments(
    review_id: int,
    review_key: str,
    row: dict[str, Any],
    analytics_run: dict[str, Any],
    allocation_run: dict[str, Any] | None,
    classification: dict[str, Any],
    actor: str,
) -> list[dict[str, Any]]:
    output = []
    for agent_name in classification["assigned_agents"]:
        assignment_type = assignment_type_for_agent(agent_name, classification)
        assignment_key = f"{review_key}_{assignment_type}".replace(" ", "_").replace("/", "_").lower()
        priority = "high" if classification["severity"] == "high" else "medium"
        input_payload = {
            "strategy_id": row["strategy_id"],
            "candidate_key": row.get("candidate_key"),
            "strategy_name": row.get("strategy_name"),
            "recommended_action": classification["recommended_action"],
            "trigger_reasons": classification["trigger_reasons"],
            "assignment_type": assignment_type,
        }
        findings = {
            "data_science_review": ["Review sample depth, leakage risk, stationarity, and metric stability."],
            "feature_engineering_review": ["Repair DSL/data gaps and define deterministic feature requirements."],
            "regime_review": ["Identify regimes where this strategy should stand down or require filters."],
            "capacity_liquidity_review": ["Check traded value, participation, capacity ceiling, and liquidity status."],
            "replacement_strategy_research": ["Generate replacement hypotheses or variants if pause/retire is confirmed."],
        }.get(assignment_type, ["Review strategy evidence."])
        allocation_id = int(allocation_run["id"]) if allocation_run else None
        rows = run_psql_json(
            f"""
            WITH upserted AS (
                INSERT INTO strategy.quant_specialist_assignments (
                    assignment_key, review_id, strategy_id, analytics_run_id, allocation_run_id,
                    specialist_agent, assignment_type, status, priority, input_payload,
                    findings, recommended_action, evidence, created_by, updated_at
                )
                VALUES (
                    {sql_literal(assignment_key)}, {review_id}, {int(row["strategy_id"])},
                    {int(analytics_run["id"])}, {allocation_id if allocation_id else 'NULL'},
                    {sql_literal(agent_name)}, {sql_literal(assignment_type)}, 'open',
                    {sql_literal(priority)}, {sql_jsonb(input_payload)}, {sql_text_array(findings)},
                    {sql_literal(classification["recommended_action"])},
                    {sql_jsonb({"review_key": review_key, "source": "strategy_retirement_review"})},
                    {sql_literal(actor)}, now()
                )
                ON CONFLICT (assignment_key) DO UPDATE SET
                    review_id = EXCLUDED.review_id,
                    strategy_id = EXCLUDED.strategy_id,
                    analytics_run_id = EXCLUDED.analytics_run_id,
                    allocation_run_id = EXCLUDED.allocation_run_id,
                    specialist_agent = EXCLUDED.specialist_agent,
                    assignment_type = EXCLUDED.assignment_type,
                    status = CASE
                        WHEN strategy.quant_specialist_assignments.status = 'completed' THEN 'completed'
                        ELSE 'open'
                    END,
                    priority = EXCLUDED.priority,
                    input_payload = EXCLUDED.input_payload,
                    findings = EXCLUDED.findings,
                    recommended_action = EXCLUDED.recommended_action,
                    evidence = EXCLUDED.evidence,
                    created_by = EXCLUDED.created_by,
                    updated_at = now()
                RETURNING id, assignment_key, specialist_agent, assignment_type, status, priority
            )
            SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
            """
        )
        output.extend(rows)
    return output


def run_review(args: argparse.Namespace) -> dict[str, Any]:
    analytics = latest_analytics(args.analytics_run_key)
    allocation = latest_allocation(args.allocation_key, int(analytics["id"]))
    evidence = fetch_candidate_evidence(int(analytics["id"]), int(allocation["id"]) if allocation else None)
    analytics_flags = [str(item) for item in analytics.get("quality_flags") or []]
    allocation_flags = [str(item) for item in (allocation or {}).get("quality_flags") or []]
    reviewed = []
    assignments = []
    for strategy_id, row in sorted(evidence.items()):
        classification = classify_review(row, analytics_flags, allocation_flags)
        review_key = f"{args.review_key_prefix}_{analytics['run_key']}_{row.get('candidate_key') or strategy_id}"
        review_id = create_or_update_review(review_key, row, analytics, allocation, classification, args.actor)
        row_assignments = upsert_assignments(review_id, review_key, row, analytics, allocation, classification, args.actor)
        assignments.extend(row_assignments)
        reviewed.append(
            {
                "review_id": review_id,
                "review_key": review_key,
                "strategy_id": strategy_id,
                "candidate_key": row.get("candidate_key"),
                "strategy_name": row.get("strategy_name"),
                **classification,
                "assignment_count": len(row_assignments),
            }
        )

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_run": {"id": analytics["id"], "run_key": analytics["run_key"]},
        "allocation_run": {"id": allocation["id"], "allocation_key": allocation["allocation_key"]} if allocation else None,
        "review_count": len(reviewed),
        "assignment_count": len(assignments),
        "reviews": reviewed,
        "live_execution_allowed": False,
        "seed_data_allowed": False,
    }
    path = ARTIFACT_ROOT / f"{args.review_key_prefix}_{analytics['run_key']}.json"
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8")
    artifact["artifact_path"] = str(path.relative_to(RUNTIME_ROOT))
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strategy retirement review and dispatch Quant specialist assignments.")
    parser.add_argument("--analytics-run-key")
    parser.add_argument("--allocation-key")
    parser.add_argument("--review-key-prefix", default="retire")
    parser.add_argument("--actor", default="Strategy Retirement Agent")
    args = parser.parse_args()
    print(json.dumps(run_review(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
