\set ON_ERROR_STOP on

BEGIN;

-- A late filing/monitor completion may enrich a blocked case, but it must not
-- silently reopen paid analysis or claim that stopped workstreams are active.
WITH terminal_cases AS (
    SELECT case_row.id AS research_case_id, case_row.iteration_count AS iteration
    FROM research.research_cases case_row
    WHERE EXISTS (
        SELECT 1 FROM research.research_case_blockers blocker
        WHERE blocker.research_case_id=case_row.id
          AND blocker.blocker_key='cost_ceiling'
          AND blocker.status IN ('open','retrying')
    )
      AND NOT EXISTS (
        SELECT 1 FROM research.research_case_model_runs model_run
        WHERE model_run.research_case_id=case_row.id
          AND model_run.iteration=case_row.iteration_count
          AND model_run.status IN ('queued','running','awaiting_dependencies')
    )
), agent_runs_updated AS (
    UPDATE research.research_case_agent_runs agent_run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM research.research_case_model_runs model_run
            WHERE model_run.research_case_id=terminal.research_case_id
              AND model_run.iteration=terminal.iteration
              AND model_run.role_key=agent_run.role_key
              AND model_run.status='completed'
        ) THEN 'completed' ELSE 'blocked' END,
        evidence=coalesce(agent_run.evidence,'[]'::jsonb) || jsonb_build_array(jsonb_build_object(
            'terminal_reason','cost_ceiling',
            'iteration',terminal.iteration,
            'capital_action_allowed',false,
            'reconciled_by','254_research_terminal_state_race_repair_v1'
        )),
        updated_at=now()
    FROM terminal_cases terminal
    WHERE agent_run.research_case_id=terminal.research_case_id
    RETURNING agent_run.research_case_id,agent_run.graph_node_run_id,agent_run.task_id,agent_run.status
), node_runs_updated AS (
    UPDATE agent.graph_node_runs node
    SET status=CASE WHEN agent_run.status='completed' THEN 'completed' ELSE 'blocked' END,
        error=coalesce(node.error,'{}'::jsonb) || jsonb_build_object(
            'terminal_reason','cost_ceiling','capital_action_allowed',false
        ),
        finished_at=coalesce(node.finished_at,now()),updated_at=now()
    FROM agent_runs_updated agent_run
    WHERE node.id=agent_run.graph_node_run_id
    RETURNING node.graph_run_id,node.task_id,node.status
), tasks_updated AS (
    UPDATE agent.tasks task
    SET status=CASE WHEN node.status='completed' THEN 'completed' ELSE 'blocked' END,
        updated_at=now()
    FROM node_runs_updated node
    WHERE task.id=node.task_id
    RETURNING task.id
), graph_runs_updated AS (
    UPDATE agent.graph_runs graph
    SET run_status='paused',finished_at=now(),
        pending_decision='{"reason":"cost_ceiling","human_review_required":true,"capital_action_allowed":false}'::jsonb,
        updated_at=now()
    WHERE graph.id IN (SELECT DISTINCT graph_run_id FROM node_runs_updated)
    RETURNING graph.id
), cases_updated AS (
    UPDATE research.research_cases case_row
    SET status='blocked',lead_status='cost_ceiling_blocked',
        current_goal='Review the published evidence-debt pack before approving any additional model budget',
        decision_readiness='needs_research',last_progress_at=now(),updated_at=now()
    FROM terminal_cases terminal
    WHERE case_row.id=terminal.research_case_id
    RETURNING case_row.id
), events AS (
    INSERT INTO research.research_case_events (
        research_case_id,event_type,event_status,event_summary,actor,event_payload
    )
    SELECT id,'terminal_state_reconciled','recorded',
        'Late source updates were preserved without reopening the stopped research iteration; no agent or model call is running.',
        'AI OS Runtime Guard',
        '{"capital_action_allowed":false,"external_write_allowed":false,"source_updates_preserved":true}'::jsonb
    FROM cases_updated
    RETURNING id
)
SELECT count(*) AS reconciled_cases FROM cases_updated;

INSERT INTO core.schema_migrations (
    migration_number,migration_key,definition_checksum_sha256,description,metadata
)
VALUES (
    254,
    '254_research_terminal_state_race_repair_v1',
    '53fe2e30e8af065fe3a0cb992734691128c4fe52fc44f88678b123d4800b7df4',
    'Preserve terminal research state across late filing and monitor refreshes and reconcile task visibility',
    '{"preserves_source_updates":true,"paid_model_call":false,"capital_action_allowed":false,"broker_write_allowed":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
