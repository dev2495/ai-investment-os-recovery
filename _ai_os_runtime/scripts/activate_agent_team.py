#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNTIME_ROOT = Path(__file__).resolve().parents[1]


def load_runtime_env() -> None:
    env_path = RUNTIME_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    os.environ.setdefault("AI_OS_RUNTIME_ROOT", str(RUNTIME_ROOT))
    if os.environ.get("AI_OS_VAULT_PATH"):
        os.environ.setdefault("AI_OS_VAULT_ROOT", os.environ["AI_OS_VAULT_PATH"])


load_runtime_env()

from run_agent_worker_once import psql_json, psql_one, psql_text, run_once, sql_jsonb, sql_literal  # noqa: E402


def candidates(include_operational: bool) -> list[dict[str, Any]]:
    status_filter = "" if include_operational else "AND readiness.readiness_status<>'operational'"
    return psql_json(
        f"""
        SELECT profile.agent_name,profile.display_title,profile.department,profile.role_scope,
               readiness.readiness_status,readiness.operating_mode,
               primary_skill.skill_key,skill.skill_name
        FROM agent.profiles profile
        JOIN agent.v_agent_operating_readiness readiness USING(agent_name)
        LEFT JOIN LATERAL (
            SELECT mapping.skill_key
            FROM agent.agent_skill_map mapping
            JOIN agent.skills active_skill USING(skill_key)
            WHERE mapping.agent_name=profile.agent_name AND active_skill.status='active'
            ORDER BY mapping.is_primary DESC,mapping.skill_key
            LIMIT 1
        ) primary_skill ON true
        LEFT JOIN agent.skills skill ON skill.skill_key=primary_skill.skill_key
        WHERE profile.status='active' {status_filter}
        ORDER BY profile.department,profile.agent_name
        """
    )


def create_activation_task(campaign_key: str, row: dict[str, Any]) -> dict[str, Any]:
    source_ref = f"{campaign_key}:{row['agent_name']}"
    objective = (
        f"Acceptance run for {row['agent_name']} ({row['display_title']}). "
        f"Demonstrate the primary skill {row.get('skill_name') or row.get('skill_key')} against current warehouse evidence; "
        "record sources, unresolved gaps, approval boundaries, and one accountable next action. "
        "Do not invoke a model, invent market facts, recommend live execution, or contact a client."
    )
    evidence = [
        {"source": "agent.v_agent_operating_readiness", "status_before": row.get("readiness_status")},
        {"source": "agent.v_agent_capability_readiness"},
        {"source": "agent.v_fund_function_coverage"},
        {"campaign_key": campaign_key, "acceptance_mode": "deterministic_evidence"},
    ]
    result = json.loads(psql_text(
        f"""
        WITH existing AS (
            SELECT id FROM agent.tasks
            WHERE source_kind='employee_activation' AND source_ref={sql_literal(source_ref)}
            ORDER BY id DESC LIMIT 1
        ), inserted_task AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            )
            SELECT {sql_literal('Employee acceptance - ' + row['agent_name'])},
                   {sql_literal(objective)},{sql_literal(row['agent_name'])},
                   'queued','normal',false,'employee_activation',{sql_literal(source_ref)},
                   'obsidian_note_and_worker_record',{sql_jsonb(evidence)}
            WHERE NOT EXISTS (SELECT 1 FROM existing)
            RETURNING id
        ), selected_task AS (
            SELECT id FROM inserted_task UNION ALL SELECT id FROM existing LIMIT 1
        ), requeued_task AS (
            UPDATE agent.tasks task
            SET status='queued',updated_at=now()
            FROM selected_task
            WHERE task.id=selected_task.id
              AND task.source_kind='employee_activation'
              AND task.source_ref={sql_literal(source_ref)}
              AND task.status IN ('in_progress','needs_review','blocked','failed')
              AND NOT EXISTS (
                  SELECT 1 FROM agent.worker_runs run
                  WHERE run.task_id=task.id AND run.status='completed'
              )
            RETURNING task.id
        ), inserted_inbox AS (
            INSERT INTO agent.inbox_items (
                task_id,title,owner_agent,status,priority,recommended_action,evidence,target_workspace
            )
            SELECT selected_task.id,{sql_literal('Acceptance work - ' + row['display_title'])},
                   {sql_literal(row['agent_name'])},'new','normal',
                   'Execute the bounded evidence-mode acceptance task and submit the output for review.',
                   {sql_jsonb(evidence)},{sql_literal(row['department'])}
            FROM selected_task
            WHERE NOT EXISTS (SELECT 1 FROM agent.inbox_items inbox WHERE inbox.task_id=selected_task.id)
            RETURNING id
        ), activation AS (
            INSERT INTO agent.employee_activation_records (
                campaign_key,agent_name,task_id,primary_skill_key,status,operating_mode,
                acceptance_checks,evidence,updated_at
            )
            SELECT {sql_literal(campaign_key)},{sql_literal(row['agent_name'])},selected_task.id,
                   {sql_literal(row.get('skill_key'))},'queued','deterministic_evidence',
                   '{{"structure":true,"tool_entitlements":true,"source_backed_output":false,"worker_completed":false}}'::jsonb,
                   {sql_jsonb(evidence)},now()
            FROM selected_task
            ON CONFLICT (campaign_key,agent_name) DO UPDATE SET
                task_id=EXCLUDED.task_id,primary_skill_key=EXCLUDED.primary_skill_key,
                status=CASE WHEN agent.employee_activation_records.status='completed' THEN 'completed' ELSE 'queued' END,
                evidence=agent.employee_activation_records.evidence || EXCLUDED.evidence,
                updated_at=now()
            RETURNING task_id,status
        )
        SELECT json_build_object(
            'task_id',activation.task_id,
            'status',activation.status,
            'inbox_id',(SELECT id FROM inserted_inbox LIMIT 1)
        )::text
        FROM activation
        """
    ))
    return result


def finalize(campaign_key: str, agent_name: str, task_id: int) -> dict[str, Any]:
    return json.loads(psql_text(
        f"""
        WITH latest_run AS (
            SELECT id,status,output_note_path,evidence,finished_at
            FROM agent.worker_runs WHERE task_id={int(task_id)}
            ORDER BY id DESC LIMIT 1
        ), readiness AS (
            SELECT * FROM agent.v_agent_operating_readiness
            WHERE agent_name={sql_literal(agent_name)}
        ), updated AS (
            UPDATE agent.employee_activation_records record
            SET worker_run_id=latest_run.id,
                status=CASE
                    WHEN latest_run.status='completed' AND readiness.tools_ready
                         AND readiness.readiness_status='operational' THEN 'completed'
                    ELSE 'failed'
                END,
                acceptance_checks=jsonb_build_object(
                    'structure',readiness.hierarchy_ready AND readiness.mailbox_ready AND readiness.character_ready,
                    'tool_entitlements',readiness.tools_ready,
                    'source_backed_output',nullif(latest_run.output_note_path,'') IS NOT NULL,
                    'worker_completed',latest_run.status='completed',
                    'model_invocation','deferred_until_model_stack',
                    'live_execution_allowed',false
                ),
                evidence=record.evidence || jsonb_build_array(
                    jsonb_build_object('source','agent.worker_runs','worker_run_id',latest_run.id,'output_note_path',latest_run.output_note_path),
                    jsonb_build_object('source','agent.v_agent_operating_readiness','readiness_status',readiness.readiness_status,'operating_mode',readiness.operating_mode)
                ),
                finished_at=coalesce(latest_run.finished_at,now()),updated_at=now()
            FROM latest_run,readiness
            WHERE record.campaign_key={sql_literal(campaign_key)}
              AND record.agent_name={sql_literal(agent_name)}
            RETURNING record.id,record.status,record.worker_run_id,record.acceptance_checks,record.finished_at
        ), closed_task AS (
            UPDATE agent.tasks task
            SET status='completed',updated_at=now()
            FROM updated
            WHERE task.id={int(task_id)} AND updated.status='completed'
            RETURNING task.id
        ), closed_inbox AS (
            UPDATE agent.inbox_items inbox
            SET status='resolved',resolved_by='Jarvis',resolved_at=now(),
                resolution_note='Employee activation acceptance checks passed.',updated_at=now()
            FROM updated
            WHERE inbox.task_id={int(task_id)} AND updated.status='completed'
            RETURNING inbox.id
        )
        SELECT coalesce((SELECT row_to_json(updated) FROM updated),'{{}}'::json)::text
        """
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description="Activate every AI OS employee with a bounded evidence-mode acceptance run.")
    parser.add_argument("--campaign", default=f"employee_activation_{datetime.now(timezone.utc).date().isoformat()}")
    parser.add_argument("--include-operational", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = candidates(args.include_operational)
    results: list[dict[str, Any]] = []
    for row in rows:
        created = create_activation_task(args.campaign, row)
        task_id = int(created["task_id"])
        worker = run_once(1, False, task_id)
        finalized = finalize(args.campaign, row["agent_name"], task_id)
        results.append({"agent_name": row["agent_name"], "task_id": task_id, "worker": worker, "activation": finalized})

    summary = psql_one(
        f"""
        SELECT count(*)::INT AS records,
               count(*) FILTER (WHERE status='completed')::INT AS completed,
               count(*) FILTER (WHERE status<>'completed')::INT AS non_completed
        FROM agent.employee_activation_records
        WHERE campaign_key={sql_literal(args.campaign)}
        """
    )
    payload = {"campaign_key": args.campaign, "summary": summary, "results": results}
    print(json.dumps(payload, indent=2 if args.json else None, default=str))
    return 0 if int(summary.get("non_completed") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
