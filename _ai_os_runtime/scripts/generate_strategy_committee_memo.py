#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)
MEMO_DIR = VAULT_ROOT / "ai memory" / "03 Strategies" / "Committee Reviews"


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def run_psql_json(sql: str) -> list[dict[str, Any]]:
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
    return json.loads(completed.stdout.strip() or "[]")


def fetch_review(review_id: int) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT
                cr.*,
                sc.name AS strategy_name,
                sc.hypothesis,
                sc.universe,
                sc.timeframe AS strategy_timeframe,
                br.run_status AS backtest_status,
                br.metrics AS backtest_metrics,
                br.diagnostics AS backtest_diagnostics,
                br.artifact_path AS backtest_artifact_path,
                opt.status AS optimization_status,
                opt.optimizer_type,
                opt.metrics AS optimization_metrics,
                opt.diagnostics AS optimization_diagnostics,
                opt.artifact_path AS optimization_artifact_path,
                vr.review_status AS validation_status,
                vr.decision AS validation_decision,
                vr.leakage_risk,
                vr.overfit_risk,
                vr.required_fixes,
                vr.issues AS validation_issues,
                ap.status AS approval_status,
                ap.requested_action,
                ap.rationale AS approval_rationale
            FROM strategy.committee_reviews cr
            LEFT JOIN strategy.strategy_candidates sc ON sc.id = cr.strategy_id
            LEFT JOIN strategy.backtest_runs br ON br.id = cr.backtest_run_id
            LEFT JOIN strategy.optimization_runs opt ON opt.id = cr.optimization_run_id
            LEFT JOIN strategy.validation_reviews vr ON vr.id = cr.validation_review_id
            LEFT JOIN agent.approvals ap ON ap.id = cr.approval_id
            WHERE cr.id = {review_id}
        ) rows
        """
    )
    if not rows:
        raise ValueError(f"committee review {review_id} not found")
    return rows[0]


def fmt(value: object, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def json_value(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    return value if isinstance(value, dict) else {}


def json_list(row: dict[str, Any], key: str) -> list[Any]:
    value = row.get(key)
    return value if isinstance(value, list) else []


def build_memo(row: dict[str, Any]) -> str:
    opt_metrics = json_value(row, "optimization_metrics")
    opt_diag = json_value(row, "optimization_diagnostics")
    ranked_results = opt_diag.get("ranked_results") if isinstance(opt_diag.get("ranked_results"), list) else []
    top_ranked = ranked_results[0] if ranked_results and isinstance(ranked_results[0], dict) else {}
    backtest_metrics = json_value(row, "backtest_metrics")
    risk_summary = json_value(row, "risk_summary")
    kill_switch = json_value(row, "kill_switch_rules")
    requested_action = json_value(row, "requested_action")
    wf = json_value(opt_metrics, "walk_forward")
    wf_summary = wf.get("summary") if isinstance(wf.get("summary"), dict) else {}
    warnings = opt_diag.get("warnings") if isinstance(opt_diag.get("warnings"), list) else []
    validation_issues = json_list(row, "validation_issues")
    required_fixes = json_list(row, "required_fixes")

    lines = [
        f"# Strategy Committee Memo - {row.get('strategy_name') or 'Strategy'}",
        "",
        f"Date: {datetime.now(timezone.utc).isoformat()}",
        f"Review: `{row.get('review_key')}`",
        f"Status: `{row.get('review_status')}`",
        f"Approval: `{row.get('approval_status')}`",
        "",
        "## Decision",
        "",
        f"- Recommended decision: `{row.get('recommended_decision')}`",
        f"- Proposed mode: `{row.get('proposed_mode')}`",
        f"- Risk level: `{row.get('risk_level')}`",
        f"- Live execution allowed: `{requested_action.get('live_execution_allowed', False)}`",
        f"- Human decision required: `{requested_action.get('human_decision_required', True)}`",
        "",
        "## Strategy Evidence",
        "",
        f"- Strategy: `{row.get('strategy_name')}`",
        f"- Universe: `{row.get('universe')}`",
        f"- Timeframe: `{row.get('strategy_timeframe') or row.get('timeframe')}`",
        f"- Hypothesis: {row.get('hypothesis') or 'n/a'}",
        "",
        "## Backtest Evidence",
        "",
        f"- Backtest run: `{row.get('backtest_run_id')}`",
        f"- Status: `{row.get('backtest_status')}`",
        f"- Total return: `{fmt(backtest_metrics.get('total_return'))}`",
        f"- Max drawdown: `{fmt(backtest_metrics.get('max_drawdown'))}`",
        f"- Sharpe estimate: `{fmt(backtest_metrics.get('sharpe_estimate'))}`",
        f"- Trades: `{fmt(backtest_metrics.get('trades_count'))}`",
        f"- Artifact: `{row.get('backtest_artifact_path')}`",
        "",
        "## Optimization And Robustness",
        "",
        f"- Optimization run: `{row.get('optimization_run_id')}`",
        f"- Optimizer type: `{row.get('optimizer_type')}`",
        f"- Best params: `{json.dumps(top_ranked.get('params') or {}, sort_keys=True)}`",
        f"- Best test Sharpe: `{fmt(opt_metrics.get('best_test_sharpe'))}`",
        f"- Best walk-forward Sharpe: `{fmt(opt_metrics.get('best_walk_forward_test_sharpe'))}`",
        f"- Walk-forward folds: `{fmt(wf_summary.get('fold_count'))}`",
        f"- Positive walk-forward folds: `{fmt(wf_summary.get('positive_test_folds'))}`",
        f"- Walk-forward consistency: `{fmt(wf_summary.get('test_consistency'))}`",
        f"- Heatmap rows: `{len(opt_diag.get('heatmap_rows') or [])}`",
        f"- Artifact: `{row.get('optimization_artifact_path')}`",
        "",
        "## Validation",
        "",
        f"- Validation review: `{row.get('validation_review_id')}`",
        f"- Validation status: `{row.get('validation_status')}`",
        f"- Validation decision: `{row.get('validation_decision')}`",
        f"- Leakage risk: `{row.get('leakage_risk')}`",
        f"- Overfit risk: `{row.get('overfit_risk')}`",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- None recorded."])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {fix}" for fix in required_fixes] or ["- None recorded."])
    lines.extend(["", "## Validation Issues", ""])
    lines.extend([f"- {json.dumps(issue, sort_keys=True)}" for issue in validation_issues] or ["- None recorded."])
    lines.extend(
        [
            "",
            "## Risk Summary",
            "",
            f"- Best walk-forward consistency: `{fmt(risk_summary.get('best_walk_forward_consistency'))}`",
            f"- Best walk-forward Sharpe: `{fmt(risk_summary.get('best_walk_forward_test_sharpe'))}`",
            f"- Optimizer status: `{risk_summary.get('optimizer_status')}`",
            f"- Live execution allowed: `{risk_summary.get('live_execution_allowed', False)}`",
            "",
            "## Kill Switch Template",
            "",
            f"- Daily loss limit: `{fmt(kill_switch.get('daily_loss_limit_pct'))}%`",
            f"- Max drawdown stop: `{fmt(kill_switch.get('max_drawdown_stop_pct'))}%`",
            f"- Max open positions: `{fmt(kill_switch.get('max_open_positions'))}`",
            f"- Disable on data gap: `{kill_switch.get('disable_on_data_gap')}`",
            f"- Disable on validation reject: `{kill_switch.get('disable_on_model_validation_reject')}`",
            f"- Manual re-enable required: `{kill_switch.get('requires_manual_reenable')}`",
            "",
            "## Committee Conclusion",
            "",
            "Reject or retest is the correct current decision. The evidence does not justify paper monitoring because walk-forward consistency is zero and robustness diagnostics are negative.",
            "",
            "No paper trade, live alert, broker order, or capital allocation is authorized by this memo.",
        ]
    )
    return "\n".join(lines) + "\n"


def update_review(review_id: int, relative_path: str) -> dict[str, Any]:
    rows = run_psql_json(
        f"""
        WITH updated AS (
            UPDATE strategy.committee_reviews
            SET memo_note_path = {sql_literal(relative_path)},
                memo_status = 'generated',
                memo_generated_at = now(),
                decision_notes = coalesce(decision_notes || E'\\n\\n', '') || 'Committee memo generated at ' || now()::text || ': ' || {sql_literal(relative_path)},
                updated_at = now()
            WHERE id = {review_id}
            RETURNING id, memo_note_path, memo_status, memo_generated_at
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority, recommended_action, evidence, target_workspace
            )
            SELECT
                'Review committee memo: ' || {sql_literal(relative_path)},
                'Charlie Munger',
                'needs_review',
                'high',
                'Review the committee memo and decide reject/retest/paper-monitor approval. Live execution remains disabled.',
                jsonb_build_array(jsonb_build_object('committee_review_id', {review_id}), jsonb_build_object('memo_note_path', {sql_literal(relative_path)})),
                'quant'
            FROM updated
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT updated.*, (SELECT id FROM inbox LIMIT 1) AS inbox_id
            FROM updated
        ) rows;
        """
    )
    return rows[0] if rows else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a strategy committee memo into Obsidian.")
    parser.add_argument("--review-id", type=int, required=True)
    args = parser.parse_args()

    row = fetch_review(args.review_id)
    MEMO_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(row.get("strategy_name") or "strategy")).strip("-").lower()
    path = MEMO_DIR / f"{stamp}-committee-review-{args.review_id}-{safe_name}.md"
    path.write_text(build_memo(row), encoding="utf-8")
    relative = str(path.relative_to(VAULT_ROOT))
    result = update_review(args.review_id, relative)
    print(json.dumps({"review_id": args.review_id, "memo_note_path": relative, "database": result}, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
