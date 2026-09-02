\set ON_ERROR_STOP on

BEGIN;

-- A cost-ceiling stop is terminal for the current iteration. Reconcile older
-- rows that were left queued so the UI, Charlie and task counters never report
-- work as active after the model guard has stopped dispatch.
WITH terminal_cases AS (
    SELECT id AS research_case_id, iteration_count AS iteration
    FROM research.research_cases
    WHERE status = 'blocked'
      AND lead_status = 'cost_ceiling_blocked'
), reconciled AS (
    UPDATE research.research_case_agent_runs agent_run
    SET status = CASE WHEN EXISTS (
            SELECT 1
            FROM research.research_case_model_runs model_run
            WHERE model_run.research_case_id = terminal.research_case_id
              AND model_run.iteration = terminal.iteration
              AND model_run.role_key = agent_run.role_key
              AND model_run.status = 'completed'
        ) THEN 'completed' ELSE 'blocked' END,
        evidence = coalesce(agent_run.evidence, '{}'::jsonb) || jsonb_build_object(
            'terminal_reason', 'cost_ceiling',
            'iteration', terminal.iteration,
            'capital_action_allowed', false,
            'reconciled_by', '253_research_cost_ceiling_terminal_state_v1'
        ),
        updated_at = now()
    FROM terminal_cases terminal
    WHERE agent_run.research_case_id = terminal.research_case_id
      AND agent_run.status IN ('active', 'running', 'queued', 'awaiting_dependencies')
    RETURNING agent_run.research_case_id
), events AS (
    INSERT INTO research.research_case_events (
        research_case_id, event_type, event_status, event_summary, actor, event_payload
    )
    SELECT DISTINCT research_case_id,
        'terminal_state_reconciled',
        'recorded',
        'Stopped workstreams now match the approved cost-ceiling outcome; no agent or model call is still running.',
        'AI OS Runtime Guard',
        '{"capital_action_allowed":false,"external_write_allowed":false}'::jsonb
    FROM reconciled
    RETURNING id
)
SELECT count(*) AS reconciliation_events FROM events;

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    253,
    '253_research_cost_ceiling_terminal_state_v1',
    '35c4040ca0bcedf9f5f590eb38cb06b9de2ca0b4b29caa06393112bbb3b17540',
    'Reconcile agent workstream state when the governed research cost ceiling stops an iteration',
    '{"preserves_completed_work":true,"paid_model_call":false,"capital_action_allowed":false,"broker_write_allowed":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
