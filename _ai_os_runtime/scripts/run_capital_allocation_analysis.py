#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from runtime_storage import artifact_reference, artifact_root


ARTIFACT_ROOT = artifact_root("capital_allocation")


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def run_psql_json(query: str) -> list[dict]:
    sql = f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows;"
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


def money(value: object) -> Decimal:
    return Decimal(str(value or 0))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run advisory-only capital allocation drift and risk-budget analysis.")
    parser.add_argument("--proposal-id", type=int, required=True)
    parser.add_argument("--run-key")
    parser.add_argument("--minimum-coverage-pct", type=Decimal, default=Decimal("80"))
    parser.add_argument("--actor", default="Capital Allocation Agent")
    args = parser.parse_args()

    proposal_rows = run_psql_json(
        f"""
        SELECT proposal.*, client.client_code, client.display_name AS client_name
        FROM books.capital_policy_proposals proposal
        JOIN portfolio.clients client ON client.id = proposal.client_id
        WHERE proposal.id = {args.proposal_id}
        """
    )
    if not proposal_rows:
        raise ValueError("capital policy proposal not found")
    proposal = proposal_rows[0]
    if proposal["status"] not in {"draft", "pending_risk_review", "risk_blocked", "committee_review"}:
        raise ValueError(f"proposal status cannot be analyzed: {proposal['status']}")

    rules = run_psql_json(
        f"""
        SELECT rule.*, book.book_name
        FROM books.capital_policy_rules rule
        JOIN books.investment_books book ON book.book_key = rule.book_key
        WHERE rule.proposal_id = {args.proposal_id}
        ORDER BY book.book_name
        """
    )
    active_books = run_psql_json("SELECT book_key FROM books.investment_books WHERE status='active' ORDER BY book_key")
    if {row["book_key"] for row in rules} != {row["book_key"] for row in active_books}:
        raise ValueError("proposal rules must cover every active investment book")
    target_total = sum((money(row["target_pct"]) for row in rules), Decimal(0))
    if abs(target_total - Decimal("100")) > Decimal("0.0001"):
        raise ValueError(f"capital policy targets must total 100%, found {target_total}")

    risk_rows = run_psql_json(
        f"""
        SELECT run_id, gross_exposure, coverage_pct, bootstrap_var_99_10d_pct,
               maximum_drawdown_pct, data_freshness_days, warnings
        FROM risk.v_latest_portfolio_risk_metrics
        WHERE scope_type='client' AND scope_ref={sql_literal(proposal['client_code'])}
        LIMIT 1
        """
    )
    if not risk_rows:
        raise ValueError("latest institutional client risk metrics are required")
    risk = risk_rows[0]
    exposure_rows = run_psql_json(
        f"""
        SELECT book_key, sum(gross_exposure) AS current_exposure, max(as_of) AS position_as_of
        FROM books.book_positions
        WHERE status='active' AND client_id={int(proposal['client_id'])}
        GROUP BY book_key
        """
    )
    exposures = {row["book_key"]: money(row["current_exposure"]) for row in exposure_rows}
    current_gross = sum(exposures.values(), Decimal(0))
    capital_basis = money(proposal["total_capital_basis"])
    if proposal["capital_basis_type"] == "gross_exposure_only":
        capital_basis = current_gross
    if capital_basis <= 0:
        raise ValueError("capital basis is unavailable or zero")

    coverage = money(risk["coverage_pct"])
    observed_var = money(risk["bootstrap_var_99_10d_pct"])
    warnings: list[dict] = []
    if coverage < args.minimum_coverage_pct:
        warnings.append({
            "type": "risk_data_coverage_below_gate",
            "observed_pct": str(coverage),
            "required_pct": str(args.minimum_coverage_pct),
        })
    if proposal["capital_basis_type"] == "gross_exposure_only":
        warnings.append({
            "type": "cash_and_liability_basis_unavailable",
            "detail": "Targets are compared with gross invested exposure only; cash, liabilities, tax, and external assets are not inferred.",
        })

    now = datetime.now(timezone.utc)
    position_dates = [row["position_as_of"] for row in exposure_rows if row.get("position_as_of")]
    position_as_of = max(position_dates, default=None)
    run_key = args.run_key or f"capital-allocation-{args.proposal_id}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    run_id = int(psql_exec(
        f"""
        INSERT INTO books.capital_allocation_analysis_runs (
            run_key, proposal_id, risk_run_id, run_status, position_as_of,
            risk_data_coverage_pct, minimum_required_coverage_pct,
            assumptions, warnings, created_by
        ) VALUES (
            {sql_literal(run_key)}, {args.proposal_id}, {int(risk['run_id'])}, 'running',
            {sql_literal(position_as_of)}::timestamptz,
            {coverage}, {args.minimum_coverage_pct},
            {sql_jsonb({'capital_basis_type': proposal['capital_basis_type'], 'capital_basis': str(capital_basis), 'current_gross_exposure': str(current_gross), 'legacy_defaults_trusted': False})},
            {sql_jsonb(warnings)}, {sql_literal(args.actor)}
        ) RETURNING id
        """
    ))
    lines = []
    blocked = coverage < args.minimum_coverage_pct
    risk_budget_breaches = 0
    drift_reviews = 0
    try:
        for rule in rules:
            current = exposures.get(rule["book_key"], Decimal(0))
            current_pct = current / capital_basis * Decimal(100)
            target_pct = money(rule["target_pct"])
            target_exposure = capital_basis * target_pct / Decimal(100)
            rebalance = target_exposure - current
            drift = current_pct - target_pct
            minimum_coverage = money(rule.get("minimum_liquidity_coverage_pct") or args.minimum_coverage_pct)
            liquidity_status = "passed" if coverage >= minimum_coverage else "blocked_data_quality"
            risk_budget = money(rule.get("risk_budget_var_99_10d_pct")) if rule.get("risk_budget_var_99_10d_pct") is not None else None
            if current == 0:
                risk_budget_status = "not_applicable_no_current_exposure"
            elif risk_budget is None:
                risk_budget_status = "budget_missing"
                blocked = True
                risk_budget_breaches += 1
            elif observed_var > risk_budget:
                risk_budget_status = "breach"
                blocked = True
                risk_budget_breaches += 1
            else:
                risk_budget_status = "within_budget"
            outside_range = current_pct < money(rule["min_pct"]) or current_pct > money(rule["max_pct"])
            if outside_range:
                drift_reviews += 1
            if liquidity_status != "passed":
                gate_status = "blocked_data_quality"
                recommended = "Improve price/liquidity history before considering a capital-policy change."
            elif risk_budget_status in {"breach", "budget_missing"}:
                gate_status = "blocked_risk_budget"
                recommended = "Risk budget is missing or breached; revise policy or reduce modeled risk before committee review."
            elif outside_range:
                gate_status = "review_drift"
                direction = "increase" if rebalance > 0 else "decrease"
                recommended = f"Review a potential {direction} of INR {abs(rebalance):.2f}; verify cash, tax, suitability, thesis, and liquidity before any approval."
            else:
                gate_status = "within_policy"
                recommended = "No policy-range change indicated; continue monitoring risk and opportunity cost."
            evidence = [
                {"source": "books.book_positions", "current_exposure": str(current)},
                {"source": "risk.v_latest_portfolio_risk_metrics", "risk_run_id": risk["run_id"], "coverage_pct": str(coverage)},
                {"source": "books.capital_policy_rules", "rule_id": rule["id"]},
            ]
            psql_exec(
                f"""
                INSERT INTO books.capital_allocation_analysis_lines (
                    run_id, client_id, book_key, current_exposure, current_pct,
                    target_pct, min_pct, max_pct, drift_pct, target_exposure,
                    rebalance_preview_notional, risk_budget_var_99_10d_pct,
                    observed_var_99_10d_pct, risk_budget_status, liquidity_status,
                    gate_status, recommended_action, evidence
                ) VALUES (
                    {run_id}, {int(proposal['client_id'])}, {sql_literal(rule['book_key'])},
                    {current}, {current_pct}, {target_pct}, {money(rule['min_pct'])},
                    {money(rule['max_pct'])}, {drift}, {target_exposure}, {rebalance},
                    {risk_budget if risk_budget is not None else 'NULL'}, {observed_var},
                    {sql_literal(risk_budget_status)}, {sql_literal(liquidity_status)},
                    {sql_literal(gate_status)}, {sql_literal(recommended)}, {sql_jsonb(evidence)}
                )
                """
            )
            lines.append({
                "book_key": rule["book_key"], "book_name": rule["book_name"],
                "current_exposure": str(current), "current_pct": str(round(current_pct, 4)),
                "target_pct": str(target_pct), "drift_pct": str(round(drift, 4)),
                "rebalance_preview_notional": str(round(rebalance, 2)),
                "gate_status": gate_status, "recommended_action": recommended,
            })

        status = "blocked" if blocked else "completed"
        summary = {
            "client_code": proposal["client_code"], "capital_basis": str(capital_basis),
            "book_count": len(lines), "risk_data_coverage_pct": str(coverage),
            "risk_budget_breaches": risk_budget_breaches, "drift_reviews": drift_reviews,
            "capital_action_allowed": False, "live_execution_allowed": False,
        }
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
        artifact_path = ARTIFACT_ROOT / f"{run_key}.json"
        artifact_path.write_text(json.dumps({
            "run_id": run_id, "run_key": run_key, "status": status,
            "proposal": proposal, "risk": risk, "warnings": warnings,
            "summary": summary, "lines": lines,
            "capital_action_allowed": False, "live_execution_allowed": False,
        }, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        review_key = f"capital-review-{args.proposal_id}-{run_id}"
        risk_review_status = "blocked_data_quality" if coverage < args.minimum_coverage_pct else ("blocked_budget" if risk_budget_breaches else "passed")
        review_status = "risk_blocked" if status == "blocked" else "pending"
        psql_exec(
            f"""
            UPDATE books.capital_allocation_analysis_runs
            SET run_status={sql_literal(status)}, summary={sql_jsonb({**summary, 'artifact_path': artifact_reference(artifact_path)})}, finished_at=now()
            WHERE id={run_id};
            UPDATE books.capital_policy_proposals
            SET status={sql_literal('risk_blocked' if status == 'blocked' else 'committee_review')}, risk_run_id={int(risk['run_id'])}, updated_at=now()
            WHERE id={args.proposal_id};
            INSERT INTO books.capital_committee_reviews (
                review_key, proposal_id, analysis_run_id, review_status,
                risk_review_status, recommendation
            ) VALUES (
                {sql_literal(review_key)}, {args.proposal_id}, {run_id},
                {sql_literal(review_status)}, {sql_literal(risk_review_status)},
                {sql_literal('defer_and_close_data_gaps' if status == 'blocked' else 'review_policy_and_opportunity_cost')}
            )
            ON CONFLICT (review_key) DO UPDATE SET
                review_status=EXCLUDED.review_status,
                risk_review_status=EXCLUDED.risk_review_status,
                recommendation=EXCLUDED.recommendation,
                updated_at=now();
            """
        )
        print(json.dumps({
            "run_id": run_id, "run_key": run_key, "status": status,
            "proposal_id": args.proposal_id, "review_key": review_key,
            "risk_review_status": risk_review_status,
            "summary": summary, "artifact_path": artifact_reference(artifact_path),
            "capital_action_allowed": False, "live_execution_allowed": False,
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        psql_exec(
            f"UPDATE books.capital_allocation_analysis_runs SET run_status='failed', error_message={sql_literal(str(exc))}, finished_at=now() WHERE id={run_id}"
        )
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        raise SystemExit(1)
