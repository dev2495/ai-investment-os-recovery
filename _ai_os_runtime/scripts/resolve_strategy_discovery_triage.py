#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from run_strategy_backtest import run_psql_json, sql_jsonb, sql_literal


VALID_DECISIONS = {
    "reject",
    "request_more_evidence",
    "route_quant_lab",
    "route_special_situation",
    "open_committee_review",
}


def fetch_json(sql: str) -> list[dict[str, Any]]:
    return run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(rows)), '[]'::json)::text
        FROM (
            {sql}
        ) rows
        """
    )


def candidate_row(candidate_id: int) -> dict[str, Any]:
    rows = fetch_json(
        f"""
        SELECT *
        FROM strategy.v_strategy_discovery_triage_queue
        WHERE id = {int(candidate_id)}
        LIMIT 1
        """
    )
    if not rows:
        raise ValueError(f"discovery_candidate_id {candidate_id} not found")
    return rows[0]


def update_states(candidate: dict[str, Any], decision: str) -> None:
    status_map = {
        "reject": ("triage_rejected", "rejected"),
        "request_more_evidence": ("triage_more_evidence", "needs_more_evidence"),
        "route_quant_lab": ("triage_quant_lab", "quant_lab_queue"),
        "route_special_situation": ("triage_special_situation", "special_situation_queue"),
        "open_committee_review": ("triage_committee_review", "committee_review_queue"),
    }
    candidate_status, idea_status = status_map[decision]
    generated_idea_id = candidate.get("generated_idea_id")
    run_psql_json(
        f"""
        WITH candidate_update AS (
            UPDATE strategy.strategy_discovery_candidates
            SET status = {sql_literal(candidate_status)},
                next_required_action = {sql_literal(next_action_for(decision))}
            WHERE id = {int(candidate["id"])}
            RETURNING id
        ), idea_update AS (
            UPDATE strategy.generated_ideas
            SET status = {sql_literal(idea_status)},
                updated_at = now()
            WHERE id = {int(generated_idea_id) if generated_idea_id else 'NULL'}
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(candidate_update)), '[]'::json)::text
        FROM candidate_update
        """
    )


def next_action_for(decision: str) -> str:
    if decision == "reject":
        return "Archive this hypothesis unless new evidence appears."
    if decision == "request_more_evidence":
        return "Collect missing evidence, source links, data depth, and falsification tests before another triage."
    if decision == "route_quant_lab":
        return "Quant Lab must convert/repair rules, validate data quality, backtest, optimize, and run model validation before committee."
    if decision == "route_special_situation":
        return "Special Situations Agent must validate catalyst terms, downside, dates, probability, and filing/source evidence."
    if decision == "open_committee_review":
        return "Strategy Committee must review optimizer/model evidence. Live execution remains disabled."
    return "Review required."


def owner_for(candidate: dict[str, Any], decision: str) -> str | None:
    if decision == "request_more_evidence":
        if candidate.get("source_kind") in {"market.news_items", "research.corporate_filings", "research.ideas"}:
            return "Research Analyst"
        if candidate.get("source_kind") == "core.source_components":
            return "Software Engineer"
        return "Strategy Research Agent"
    if decision == "route_quant_lab":
        return "Quant Researcher"
    if decision == "route_special_situation":
        return "Special Situations Agent"
    if decision == "reject":
        return "Strategy Discovery Agent"
    return None


def create_inbox(candidate: dict[str, Any], decision: str, notes: str | None, actor: str) -> int | None:
    owner = owner_for(candidate, decision)
    if not owner:
        return None
    priority = "high" if decision in {"route_special_situation", "route_quant_lab"} else "medium"
    evidence = [
        {
            "table": "strategy.strategy_discovery_candidates",
            "id": candidate["id"],
            "discovery_key": candidate.get("discovery_key"),
            "source_kind": candidate.get("source_kind"),
            "source_ref": candidate.get("source_ref"),
            "generated_idea_id": candidate.get("generated_idea_id"),
            "optimizer_run_id": candidate.get("optimizer_run_id"),
            "decided_by": actor,
        }
    ]
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO agent.inbox_items (
                title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            VALUES (
                {sql_literal('Discovery triage: ' + str(candidate.get('title') or '')[:150])},
                {sql_literal(owner)},
                'queued',
                {sql_literal(priority)},
                {sql_literal(next_action_for(decision) + ((' Notes: ' + notes) if notes else ''))},
                {sql_jsonb(evidence)},
                'strategy'
            )
            RETURNING id
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return int(rows[0]["id"]) if rows else None


def open_committee(candidate: dict[str, Any], actor: str) -> dict[str, Any]:
    optimization_run_id = candidate.get("optimization_run_id")
    if not optimization_run_id:
        raise ValueError("open_committee_review requires candidate.optimization_run_id from a completed optimizer path")
    rows = fetch_json(
        f"""
        SELECT strategy.open_strategy_committee_review({int(optimization_run_id)}, {sql_literal(actor)}) AS payload
        """
    )
    payload = rows[0].get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    return payload


def record_decision(candidate: dict[str, Any], decision: str, notes: str | None, actor: str, inbox_id: int | None, committee_payload: dict[str, Any] | None) -> dict[str, Any]:
    committee_review_id = committee_payload.get("committee_review_id") if committee_payload else None
    approval_id = committee_payload.get("approval_id") if committee_payload else None
    routed = owner_for(candidate, decision)
    evidence = [
        {
            "table": "strategy.v_strategy_discovery_triage_queue",
            "id": candidate["id"],
            "discovery_key": candidate.get("discovery_key"),
            "decision": decision,
            "live_execution_allowed": False,
            "broker_order_allowed": False,
        }
    ]
    if committee_payload:
        evidence.append({"committee_payload": committee_payload})
    rows = run_psql_json(
        f"""
        WITH inserted AS (
            INSERT INTO strategy.strategy_discovery_triage_decisions (
                discovery_candidate_id, generated_idea_id, optimizer_run_id,
                decision, decision_status, routed_to_agent, inbox_item_id,
                approval_id, committee_review_id, decision_notes, evidence,
                decided_by
            )
            VALUES (
                {int(candidate["id"])},
                {int(candidate["generated_idea_id"]) if candidate.get("generated_idea_id") else 'NULL'},
                {int(candidate["optimizer_run_id"]) if candidate.get("optimizer_run_id") else 'NULL'},
                {sql_literal(decision)},
                'final',
                {sql_literal(routed)},
                {int(inbox_id) if inbox_id else 'NULL'},
                {int(approval_id) if approval_id else 'NULL'},
                {int(committee_review_id) if committee_review_id else 'NULL'},
                {sql_literal(notes)},
                {sql_jsonb(evidence)},
                {sql_literal(actor)}
            )
            RETURNING *
        )
        SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
        """
    )
    return rows[0]


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    decision = args.decision.strip().lower()
    if decision not in VALID_DECISIONS:
        raise ValueError("decision must be one of: " + ", ".join(sorted(VALID_DECISIONS)))
    candidate = candidate_row(args.discovery_candidate_id)
    committee_payload: dict[str, Any] | None = None
    if decision == "open_committee_review":
        committee_payload = open_committee(candidate, args.actor)
    inbox_id = create_inbox(candidate, decision, args.notes, args.actor)
    update_states(candidate, decision)
    decision_row = record_decision(candidate, decision, args.notes, args.actor, inbox_id, committee_payload)
    refreshed = candidate_row(args.discovery_candidate_id)
    return {
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "candidate": refreshed,
        "decision_row": decision_row,
        "inbox_item_id": inbox_id,
        "committee": committee_payload,
        "live_execution_allowed": False,
        "broker_order_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve Charlie/Jarvis triage for a discovered strategy idea.")
    parser.add_argument("--discovery-candidate-id", type=int, required=True)
    parser.add_argument("--decision", required=True, choices=sorted(VALID_DECISIONS))
    parser.add_argument("--actor", default="Charlie Munger")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    print(json.dumps(resolve(args), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
