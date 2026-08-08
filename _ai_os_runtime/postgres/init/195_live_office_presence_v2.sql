BEGIN;

CREATE OR REPLACE VIEW agent.v_live_office_presence_v2 AS
WITH base AS (
    SELECT * FROM agent.v_live_office_agent_activity
),
fresh_task AS (
    SELECT DISTINCT ON (task.owner_agent)
        task.owner_agent AS agent_name,
        task.id,
        task.title,
        task.objective,
        task.status,
        task.priority,
        task.source_kind,
        task.source_ref,
        task.updated_at
    FROM agent.tasks task
    WHERE task.status = 'in_progress'
      AND task.updated_at >= now() - interval '30 minutes'
    ORDER BY task.owner_agent, task.updated_at DESC, task.id DESC
),
fresh_worker AS (
    SELECT DISTINCT ON (run.agent_name)
        run.agent_name,
        run.id,
        run.task_id,
        run.skill_key,
        skill.skill_name,
        run.status,
        run.output_summary,
        run.started_at,
        run.updated_at
    FROM agent.worker_runs run
    LEFT JOIN agent.skills skill ON skill.skill_key=run.skill_key
    WHERE run.status IN ('running','in_progress')
      AND coalesce(run.updated_at,run.started_at) >= now() - interval '2 hours'
    ORDER BY run.agent_name,coalesce(run.updated_at,run.started_at) DESC,run.id DESC
)
SELECT
    base.*,
    CASE
        WHEN base.blocked_task_count > 0 THEN 'blocked'
        WHEN base.department_key='risk' AND base.critical_risk_event_count > 0 THEN 'critical_risk'
        WHEN base.department_key='risk' AND base.open_risk_event_count > 0 THEN 'risk_review'
        WHEN fresh_worker.id IS NOT NULL OR fresh_task.id IS NOT NULL THEN 'executing'
        WHEN base.unread_message_count > 0 OR base.urgent_inbox_count > 0 THEN 'needs_attention'
        WHEN base.queued_task_count > 0 THEN 'queued'
        ELSE 'available'
    END AS presence_state,
    CASE
        WHEN base.blocked_task_count > 0 THEN 'blocked task requires resolution'
        WHEN base.department_key='risk' AND base.critical_risk_event_count > 0 THEN 'critical open risk event'
        WHEN base.department_key='risk' AND base.open_risk_event_count > 0 THEN 'open risk review'
        WHEN fresh_worker.id IS NOT NULL THEN 'fresh worker run'
        WHEN fresh_task.id IS NOT NULL THEN 'fresh in-progress task'
        WHEN base.unread_message_count > 0 OR base.urgent_inbox_count > 0 THEN 'mailbox or urgent inbox attention'
        WHEN base.queued_task_count > 0 THEN 'queued backlog; not executing'
        ELSE 'no fresh assignment'
    END AS presence_reason,
    CASE
        WHEN fresh_worker.id IS NOT NULL THEN 'agent.worker_runs'
        WHEN fresh_task.id IS NOT NULL THEN 'agent.tasks'
        WHEN base.blocked_task_count > 0 OR base.queued_task_count > 0 THEN 'agent.tasks'
        ELSE NULL
    END AS presence_source_kind,
    coalesce(fresh_worker.id,fresh_task.id,base.current_task_id) AS presence_source_id,
    CASE
        WHEN fresh_worker.id IS NOT NULL THEN fresh_worker.started_at
        WHEN fresh_task.id IS NOT NULL THEN fresh_task.updated_at
        ELSE NULL
    END AS presence_started_at,
    CASE
        WHEN fresh_worker.id IS NOT NULL THEN coalesce(fresh_worker.updated_at,fresh_worker.started_at) + interval '2 hours'
        WHEN fresh_task.id IS NOT NULL THEN fresh_task.updated_at + interval '30 minutes'
        ELSE NULL
    END AS presence_expires_at,
    (fresh_worker.id IS NOT NULL OR fresh_task.id IS NOT NULL) AS presence_is_fresh,
    CASE
        WHEN fresh_worker.id IS NOT NULL THEN coalesce(fresh_worker.skill_name,'Worker run')
        WHEN fresh_task.id IS NOT NULL THEN fresh_task.title
        WHEN base.blocked_task_count > 0 OR base.queued_task_count > 0 THEN base.current_task_title
        WHEN base.unread_message_count > 0 THEN base.latest_message_subject
        ELSE 'Available for assignment'
    END AS presence_title,
    CASE
        WHEN fresh_worker.id IS NOT NULL THEN coalesce(fresh_worker.output_summary,'Worker is executing.')
        WHEN fresh_task.id IS NOT NULL THEN fresh_task.objective
        WHEN base.blocked_task_count > 0 OR base.queued_task_count > 0 THEN base.current_task_objective
        WHEN base.unread_message_count > 0 THEN 'Unread inter-agent handoff requires attention.'
        ELSE 'No fresh task or worker run is active.'
    END AS presence_detail
FROM base
LEFT JOIN fresh_task USING(agent_name)
LEFT JOIN fresh_worker USING(agent_name);

CREATE OR REPLACE VIEW agent.v_live_office_rooms_v2 AS
SELECT
    department_key AS room_key,
    department_name AS room_name,
    min(role_rank) AS room_rank,
    count(*)::BIGINT AS agent_count,
    count(*) FILTER (WHERE presence_state='executing')::BIGINT AS executing_agent_count,
    count(*) FILTER (WHERE presence_state NOT IN ('available','queued'))::BIGINT AS active_agent_count,
    count(*) FILTER (WHERE presence_state='queued')::BIGINT AS queued_agent_count,
    sum(open_task_count)::BIGINT AS open_task_count,
    sum(blocked_task_count)::BIGINT AS blocked_task_count,
    sum(unread_message_count)::BIGINT AS unread_message_count,
    sum(open_inbox_count)::BIGINT AS open_inbox_count,
    sum(open_risk_event_count)::BIGINT AS open_risk_event_count,
    sum(workload_score)::BIGINT AS room_workload_score,
    max(latest_activity_at) AS latest_activity_at,
    CASE
        WHEN bool_or(presence_state='blocked') THEN 'blocked'
        WHEN bool_or(presence_state='critical_risk') THEN 'critical_risk'
        WHEN bool_or(presence_state='risk_review') THEN 'risk_review'
        WHEN bool_or(presence_state='executing') THEN 'executing'
        WHEN bool_or(presence_state='needs_attention') THEN 'needs_attention'
        WHEN bool_or(presence_state='queued') THEN 'queued'
        ELSE 'available'
    END AS room_state,
    jsonb_agg(jsonb_build_object(
        'agent_name',agent_name,'display_title',display_title,'office_location',office_location,
        'presence_state',presence_state,'presence_reason',presence_reason,
        'presence_title',presence_title,'presence_detail',presence_detail,
        'presence_source_kind',presence_source_kind,'presence_source_id',presence_source_id,
        'presence_expires_at',presence_expires_at,'open_task_count',open_task_count,
        'unread_message_count',unread_message_count,'open_inbox_count',open_inbox_count,
        'workload_score',workload_score,'color_token',color_token,'icon_hint',icon_hint
    ) ORDER BY role_rank,agent_name) AS agents
FROM agent.v_live_office_presence_v2
GROUP BY department_key,department_name;

COMMIT;
