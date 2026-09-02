\set ON_ERROR_STOP on

BEGIN;

-- Older cases could be reopened by a late filing refresh after independent
-- review had already exhausted its bounded retries. Reconcile only cases with
-- a durable review blocker, a terminal review result, and no runnable model
-- call. Completed source and specialist work is preserved.
WITH terminal_reviews AS (
    SELECT case_row.id AS research_case_id,
           case_row.iteration_count AS iteration,
           case_row.graph_run_id
    FROM research.research_cases case_row
    WHERE EXISTS (
        SELECT 1
        FROM research.research_case_blockers blocker
        WHERE blocker.research_case_id=case_row.id
          AND blocker.blocker_key='independent_review'
          AND blocker.status IN ('open','retrying')
          AND blocker.severity IN ('critical','high')
    )
      AND NOT EXISTS (
        SELECT 1
        FROM research.research_case_blockers blocker
        WHERE blocker.research_case_id=case_row.id
          AND blocker.blocker_key='cost_ceiling'
          AND blocker.status IN ('open','retrying')
    )
      AND EXISTS (
        SELECT 1
        FROM research.research_case_model_runs model_run
        WHERE model_run.research_case_id=case_row.id
          AND model_run.iteration=case_row.iteration_count
          AND model_run.role_key='independent_review'
          AND model_run.status='needs_revision'
          AND model_run.attempt>=2
    )
      AND NOT EXISTS (
        SELECT 1
        FROM research.research_case_model_runs model_run
        WHERE model_run.research_case_id=case_row.id
          AND model_run.iteration=case_row.iteration_count
          AND model_run.status IN ('queued','running')
    )
      AND (case_row.status<>'blocked' OR case_row.lead_status<>'independent_review_blocked')
), model_runs_updated AS (
    UPDATE research.research_case_model_runs model_run
    SET status='blocked',
        exception_detail=concat_ws('; ',NULLIF(model_run.exception_detail,''),
          'terminal independent review requires a fresh explicitly approved iteration'),
        finished_at=coalesce(model_run.finished_at,now()),updated_at=now()
    FROM terminal_reviews terminal
    WHERE model_run.research_case_id=terminal.research_case_id
      AND model_run.iteration=terminal.iteration
      AND model_run.status='awaiting_dependencies'
    RETURNING model_run.research_case_id
), graph_runs_updated AS (
    UPDATE agent.graph_runs graph
    SET run_status='paused',finished_at=coalesce(graph.finished_at,now()),
        pending_decision='{"reason":"independent_review_attempts_exhausted","human_review_required":true,"capital_action_allowed":false}'::jsonb,
        updated_at=now()
    WHERE graph.id IN (SELECT graph_run_id FROM terminal_reviews WHERE graph_run_id IS NOT NULL)
    RETURNING graph.id
), cases_updated AS (
    UPDATE research.research_cases case_row
    SET status='blocked',lead_status='independent_review_blocked',
        current_goal='Review the evidence-debt pack before approving a fresh bounded research iteration',
        decision_readiness='needs_research',last_progress_at=now(),updated_at=now()
    FROM terminal_reviews terminal
    WHERE case_row.id=terminal.research_case_id
    RETURNING case_row.id
), events AS (
    INSERT INTO research.research_case_events (
        research_case_id,event_type,event_status,event_summary,actor,event_payload
    )
    SELECT id,'terminal_state_reconciled','recorded',
        'Late source updates were preserved without reopening the independently blocked research iteration; no model call is running.',
        'AI OS Runtime Guard',
        '{"terminal_reason":"independent_review_attempts_exhausted","capital_action_allowed":false,"external_write_allowed":false,"source_updates_preserved":true}'::jsonb
    FROM cases_updated
    RETURNING id
)
SELECT count(*) AS reconciled_cases FROM cases_updated;

INSERT INTO core.schema_migrations (
    migration_number,migration_key,definition_checksum_sha256,description,metadata
)
VALUES (
    255,
    '255_research_independent_review_terminal_repair_v1',
    'a27ef4f0ec0a1fce34b232344d315f62589b10e05ee28f54807828d06fe93f9c',
    'Restore terminal independent-review state after historical late-source refreshes',
    '{"preserves_source_updates":true,"paid_model_call":false,"capital_action_allowed":false,"broker_write_allowed":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
