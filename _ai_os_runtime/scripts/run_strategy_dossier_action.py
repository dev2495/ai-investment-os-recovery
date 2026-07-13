#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(os.environ.get("AI_OS_RUNTIME_ROOT") or Path(__file__).absolute().parents[1])
VAULT_ROOT = Path(os.environ.get("AI_OS_VAULT_ROOT") or RUNTIME_ROOT.parent)

ALLOWED_ACTIONS = {
    "request_more_evidence",
    "route_quant_lab",
    "route_special_situation",
    "open_committee_review",
    "generate_committee_memo",
}


def run_psql(sql: str, tuples_only: bool = False) -> str:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        command.extend(["-t", "-A"])
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def fetch_json_rows(sql: str) -> list[dict[str, Any]]:
    wrapped = f"SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM ({sql}) q;"
    text = run_psql(wrapped, tuples_only=True)
    return json.loads(text) if text else []


def run_psql_json_statement(sql: str) -> list[dict[str, Any]]:
    text = run_psql(sql, tuples_only=True)
    return json.loads(text) if text else []


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps(value, sort_keys=True, default=str))}::jsonb"


def fetch_dossier(dossier_id: int) -> dict[str, Any]:
    rows = fetch_json_rows(
        f"""
        SELECT id, dossier_key, title, symbols, status, latest_triage_decision,
               recommended_next_action, summary, evidence_timeline,
               linked_candidate_ids, linked_optimizer_run_ids,
               linked_committee_review_ids, note_path
        FROM strategy.v_idea_dossiers
        WHERE id = {dossier_id}
        """
    )
    if not rows:
        raise ValueError(f"dossier_id {dossier_id} not found")
    return rows[0]


def create_task_and_inbox(dossier: dict[str, Any], action: str, actor: str, notes: str) -> dict[str, Any]:
    if action == "route_quant_lab":
        owner = "Quant Researcher"
        workspace = "quant"
        priority = "high"
        title = f"Quant Lab dossier review: {dossier['title']}"
        objective = "Repair or structure the strategy, check data requirements, run or queue backtest/optimizer/model validation, and return a recommendation."
        status = "quant_lab_queue"
        next_action = "Quant Lab must repair/validate rules, backtest, and run model validation."
    elif action == "route_special_situation":
        owner = "Special Situations Agent"
        workspace = "research"
        priority = "high"
        title = f"Special situation dossier review: {dossier['title']}"
        objective = "Validate event terms, filings/news evidence, catalyst dates, spread math, and whether this is an actionable special-situation research case."
        status = "special_situation_queue"
        next_action = "Special Situations Agent must validate event terms and evidence."
    else:
        owner = "Research Analyst"
        workspace = "research"
        priority = "normal"
        title = f"More evidence required: {dossier['title']}"
        objective = "Gather stronger source evidence, comparable cases, data availability, and falsification checks before routing this idea further."
        status = "needs_more_evidence"
        next_action = "More evidence required before optimizer, special-situation, or committee routing."

    evidence = [
        {"table": "strategy.idea_dossiers", "id": dossier["id"]},
        {"dossier_key": dossier["dossier_key"]},
        {"note_path": dossier.get("note_path")},
        {"live_execution_allowed": False},
        {"paper_monitor_allowed": False},
        {"actor_notes": notes},
    ]
    rows = run_psql_json_statement(
        f"""
        WITH task AS (
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                {sql_literal(title)},
                {sql_literal(objective)},
                {sql_literal(owner)},
                'queued',
                {sql_literal(priority)},
                false,
                'strategy.idea_dossiers',
                {sql_literal(str(dossier['id']))},
                'specialist_review_note',
                {sql_jsonb(evidence)}
            )
            RETURNING id
        ),
        inbox AS (
            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            SELECT
                task.id,
                {sql_literal(title)},
                {sql_literal(owner)},
                'needs_review',
                {sql_literal(priority)},
                {sql_literal(objective + ' No paper trade, live alert, broker order, or capital allocation is authorized.')},
                {sql_jsonb(evidence)},
                {sql_literal(workspace)}
            FROM task
            RETURNING id, task_id
        ),
        dossier_update AS (
            UPDATE strategy.idea_dossiers
            SET status = {sql_literal(status)},
                recommended_next_action = {sql_literal(next_action)},
                inbox_item_count = inbox_item_count + 1,
                updated_at = now()
            WHERE id = {int(dossier['id'])}
            RETURNING id, status, recommended_next_action
        )
        SELECT COALESCE(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT inbox.id AS inbox_item_id, inbox.task_id, dossier_update.status AS dossier_status,
                   dossier_update.recommended_next_action
            FROM inbox, dossier_update
        ) rows
        """
    )
    if not rows:
        raise RuntimeError("task/inbox creation failed")
    return {
        "target_agent": owner,
        "target_table": "agent.inbox_items",
        "target_id": str(rows[0]["inbox_item_id"]),
        "payload": {**rows[0], "task_owner": owner, "target_workspace": workspace},
    }


def best_optimization_run_id(dossier: dict[str, Any]) -> int:
    optimizer_ids = [str(int(item)) for item in dossier.get("linked_optimizer_run_ids") or [] if str(item).isdigit()]
    if not optimizer_ids:
        raise ValueError("dossier has no linked optimizer runs; route Quant Lab or request more evidence first")
    rows = fetch_json_rows(
        f"""
        SELECT run.id AS user_optimizer_run_id, run.optimization_run_id, run.status,
               opt.metrics, opt.diagnostics
        FROM strategy.v_user_defined_optimizer_runs run
        LEFT JOIN strategy.optimization_runs opt ON opt.id = run.optimization_run_id
        WHERE run.id IN ({",".join(optimizer_ids)})
          AND run.optimization_run_id IS NOT NULL
        ORDER BY
          CASE WHEN run.status = 'completed' THEN 0 ELSE 1 END,
          COALESCE(NULLIF(opt.metrics->>'best_walk_forward_test_sharpe', '')::NUMERIC, -999) DESC,
          run.id DESC
        LIMIT 1
        """
    )
    if not rows:
        raise ValueError("no completed optimization run is linked to this dossier")
    return int(rows[0]["optimization_run_id"])


def open_committee_review(dossier: dict[str, Any], actor: str) -> dict[str, Any]:
    existing_ids = [str(int(item)) for item in dossier.get("linked_committee_review_ids") or [] if str(item).isdigit()]
    if existing_ids:
        rows = fetch_json_rows(
            f"""
            SELECT id AS committee_review_id, approval_id, review_status,
                   recommended_decision, risk_level, true AS existing
            FROM strategy.committee_reviews
            WHERE id IN ({",".join(existing_ids)})
            ORDER BY id DESC
            LIMIT 1
            """
        )
        if rows:
            return {
                "target_agent": "Strategy Committee Secretary",
                "target_table": "strategy.committee_reviews",
                "target_id": str(rows[0]["committee_review_id"]),
                "payload": rows[0],
            }
    optimization_run_id = best_optimization_run_id(dossier)
    rows = run_psql_json_statement(
        f"""
        WITH opened AS (
            SELECT strategy.open_strategy_committee_review(
                {optimization_run_id},
                {sql_literal(actor)}
            ) AS result
        ),
        parsed AS (
            SELECT
                (result->>'committee_review_id')::BIGINT AS committee_review_id,
                (result->>'approval_id')::BIGINT AS approval_id,
                result->>'review_status' AS review_status,
                result->>'recommended_decision' AS recommended_decision,
                result->>'risk_level' AS risk_level,
                COALESCE((result->>'existing')::BOOLEAN, false) AS existing
            FROM opened
        ),
        dossier_update AS (
            UPDATE strategy.idea_dossiers
            SET status = 'committee_review',
                recommended_next_action = 'Committee review opened. Generate/verify memo before final decision.',
                linked_committee_review_ids = ARRAY(
                    SELECT DISTINCT value
                    FROM unnest(linked_committee_review_ids || ARRAY[(SELECT committee_review_id FROM parsed)]::BIGINT[]) AS value
                ),
                committee_review_count = GREATEST(committee_review_count, COALESCE(array_length(ARRAY(
                    SELECT DISTINCT value
                    FROM unnest(linked_committee_review_ids || ARRAY[(SELECT committee_review_id FROM parsed)]::BIGINT[]) AS value
                ), 1), 0)),
                updated_at = now()
            WHERE id = {int(dossier['id'])}
            RETURNING id, status, linked_committee_review_ids
        )
        SELECT COALESCE(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            SELECT parsed.*, dossier_update.status AS dossier_status,
                   dossier_update.linked_committee_review_ids
            FROM parsed, dossier_update
        ) rows
        """
    )
    if not rows:
        raise RuntimeError("committee review creation failed")
    return {
        "target_agent": "Strategy Committee Secretary",
        "target_table": "strategy.committee_reviews",
        "target_id": str(rows[0]["committee_review_id"]),
        "payload": {**rows[0], "optimization_run_id": optimization_run_id},
    }


def generate_committee_memo(dossier: dict[str, Any], actor: str) -> dict[str, Any]:
    review_payload = open_committee_review(dossier, actor)
    review_id = int(review_payload["target_id"])
    command = [sys.executable, str(RUNTIME_ROOT / "scripts" / "generate_strategy_committee_memo.py"), "--review-id", str(review_id)]
    completed = subprocess.run(command, cwd=VAULT_ROOT, text=True, capture_output=True, check=False, timeout=180)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "committee memo generation failed").strip())
    memo = json.loads(completed.stdout)
    run_psql(
        f"""
        UPDATE strategy.idea_dossiers
        SET status = 'committee_memo_generated',
            recommended_next_action = 'Committee memo generated. Charlie must make a final reject/retest/research/paper-monitor decision.',
            updated_at = now()
        WHERE id = {int(dossier['id'])};
        """
    )
    return {
        "target_agent": "Strategy Committee Secretary",
        "target_table": "strategy.committee_reviews",
        "target_id": str(review_id),
        "payload": {"committee_review": review_payload["payload"], "memo": memo},
    }


def record_action(dossier_id: int, action: str, run_key: str, actor: str, target: dict[str, Any]) -> dict[str, Any]:
    payload = {
        **target.get("payload", {}),
        "live_execution_allowed": False,
        "paper_monitor_allowed": False,
        "human_decision_required": True,
    }
    rows = run_psql_json_statement(
        f"""
        WITH action_row AS (
            INSERT INTO strategy.idea_dossier_actions (
                dossier_id, action_key, action_type, status, target_agent,
                target_table, target_id, output_payload, created_by
            )
            VALUES (
                {dossier_id},
                {sql_literal(run_key)},
                {sql_literal(action)},
                'completed',
                {sql_literal(target.get("target_agent"))},
                {sql_literal(target.get("target_table"))},
                {sql_literal(target.get("target_id"))},
                {sql_jsonb(payload)},
                {sql_literal(actor)}
            )
            ON CONFLICT (action_key) DO UPDATE SET
                status = EXCLUDED.status,
                target_agent = EXCLUDED.target_agent,
                target_table = EXCLUDED.target_table,
                target_id = EXCLUDED.target_id,
                output_payload = EXCLUDED.output_payload,
                error_message = NULL
            RETURNING id, dossier_id, action_key, action_type, status,
                      target_agent, target_table, target_id, output_payload,
                      created_by, created_at
        )
        SELECT COALESCE(json_agg(row_to_json(action_row)), '[]'::json)::text
        FROM action_row
        """
    )
    if not rows:
        raise RuntimeError("action record failed")
    return rows[0]


def run_action(args: argparse.Namespace) -> dict[str, Any]:
    action = args.action.strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action must be one of {', '.join(sorted(ALLOWED_ACTIONS))}")
    dossier = fetch_dossier(args.dossier_id)
    if action in {"request_more_evidence", "route_quant_lab", "route_special_situation"}:
        target = create_task_and_inbox(dossier, action, args.actor, args.notes)
    elif action == "open_committee_review":
        target = open_committee_review(dossier, args.actor)
    else:
        target = generate_committee_memo(dossier, args.actor)
    action_row = record_action(args.dossier_id, action, args.run_key, args.actor, target)
    return {
        "run_key": args.run_key,
        "status": "completed",
        "dossier_id": args.dossier_id,
        "dossier_key": dossier["dossier_key"],
        "dossier_title": dossier["title"],
        "action_type": action,
        "action": action_row,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a gated action from a persistent strategy idea dossier.")
    parser.add_argument("--dossier-id", type=int, required=True)
    parser.add_argument("--action", required=True, choices=sorted(ALLOWED_ACTIONS))
    parser.add_argument("--run-key", default=f"dossier_action_{int(time.time())}")
    parser.add_argument("--actor", default="Charlie Munger")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    try:
        result = run_action(args)
    except Exception as exc:
        print(json.dumps({"run_key": args.run_key, "status": "failed", "error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
