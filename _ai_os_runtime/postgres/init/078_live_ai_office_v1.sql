CREATE OR REPLACE VIEW agent.v_live_office_agent_activity AS
WITH org AS (
    SELECT
        chart.agent_name,
        chart.display_title,
        chart.reports_to_agent,
        chart.department_key,
        chart.department_name,
        chart.role_rank,
        chart.hierarchy_level,
        chart.authority_scope,
        chart.decision_rights,
        chart.character_name,
        chart.avatar_role,
        chart.visual_traits,
        chart.voice_style,
        chart.office_location,
        chart.animation_state,
        chart.color_token,
        chart.icon_hint,
        chart.mailbox_address,
        chart.mailbox_key,
        chart.updated_at
    FROM agent.v_agent_org_chart chart
),
task_rollup AS (
    SELECT
        owner_agent AS agent_name,
        count(*) FILTER (WHERE status IN ('queued','in_progress','blocked'))::BIGINT AS open_task_count,
        count(*) FILTER (WHERE status = 'queued')::BIGINT AS queued_task_count,
        count(*) FILTER (WHERE status = 'in_progress')::BIGINT AS in_progress_task_count,
        count(*) FILTER (WHERE status = 'blocked')::BIGINT AS blocked_task_count,
        max(updated_at) FILTER (WHERE status IN ('queued','in_progress','blocked')) AS latest_task_at,
        coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'title', title,
                    'objective', objective,
                    'status', status,
                    'priority', priority,
                    'source_kind', source_kind,
                    'source_ref', source_ref,
                    'updated_at', updated_at
                )
                ORDER BY
                    CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                    updated_at DESC
            ) FILTER (WHERE status IN ('queued','in_progress','blocked')),
            '[]'::jsonb
        ) AS open_tasks
    FROM agent.tasks
    GROUP BY owner_agent
),
inbox_rollup AS (
    SELECT
        owner_agent AS agent_name,
        count(*) FILTER (WHERE status IN ('new','open','in_progress'))::BIGINT AS open_inbox_count,
        count(*) FILTER (WHERE priority IN ('critical','high') AND status IN ('new','open','in_progress'))::BIGINT AS urgent_inbox_count,
        max(updated_at) FILTER (WHERE status IN ('new','open','in_progress')) AS latest_inbox_at
    FROM agent.inbox_items
    GROUP BY owner_agent
),
latest_worker AS (
    SELECT DISTINCT ON (wr.agent_name)
        wr.agent_name,
        wr.id AS latest_worker_run_id,
        wr.skill_key AS latest_worker_skill_key,
        sk.skill_name AS latest_worker_skill_name,
        wr.status AS latest_worker_status,
        wr.output_summary AS latest_worker_summary,
        wr.output_note_path AS latest_worker_output_note_path,
        wr.started_at AS latest_worker_started_at,
        wr.finished_at AS latest_worker_finished_at
    FROM agent.worker_runs wr
    LEFT JOIN agent.skills sk ON sk.skill_key = wr.skill_key
    ORDER BY wr.agent_name, coalesce(wr.finished_at, wr.started_at) DESC, wr.id DESC
),
latest_message AS (
    SELECT DISTINCT ON (msg.to_agent)
        msg.to_agent AS agent_name,
        msg.id AS latest_message_id,
        msg.thread_key AS latest_message_thread_key,
        msg.from_agent AS latest_message_from_agent,
        msg.subject AS latest_message_subject,
        msg.priority AS latest_message_priority,
        msg.status AS latest_message_status,
        msg.created_at AS latest_message_at
    FROM agent.agent_messages msg
    ORDER BY msg.to_agent, msg.created_at DESC, msg.id DESC
),
risk_rollup AS (
    SELECT
        count(*) FILTER (WHERE status IN ('new','acknowledged'))::BIGINT AS open_risk_event_count,
        count(*) FILTER (WHERE severity = 'critical' AND status IN ('new','acknowledged'))::BIGINT AS critical_risk_event_count,
        count(*) FILTER (WHERE severity = 'high' AND status IN ('new','acknowledged'))::BIGINT AS high_risk_event_count,
        max(ts) FILTER (WHERE status IN ('new','acknowledged')) AS latest_risk_event_at
    FROM risk.events
),
top_task AS (
    SELECT DISTINCT ON (owner_agent)
        owner_agent AS agent_name,
        id AS current_task_id,
        title AS current_task_title,
        objective AS current_task_objective,
        status AS current_task_status,
        priority AS current_task_priority,
        updated_at AS current_task_updated_at
    FROM agent.tasks
    WHERE status IN ('blocked','in_progress','queued')
    ORDER BY
        owner_agent,
        CASE status WHEN 'blocked' THEN 1 WHEN 'in_progress' THEN 2 ELSE 3 END,
        CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
        updated_at DESC
)
SELECT
    org.agent_name,
    org.display_title,
    org.reports_to_agent,
    org.department_key,
    org.department_name,
    org.role_rank,
    org.hierarchy_level,
    org.authority_scope,
    org.decision_rights,
    org.character_name,
    org.avatar_role,
    org.visual_traits,
    org.voice_style,
    org.office_location,
    org.animation_state,
    org.color_token,
    org.icon_hint,
    org.mailbox_address,
    org.mailbox_key,
    coalesce(mb.unread_count, 0)::BIGINT AS unread_message_count,
    mb.latest_message_at AS mailbox_latest_message_at,
    coalesce(task_rollup.open_task_count, 0)::BIGINT AS open_task_count,
    coalesce(task_rollup.queued_task_count, 0)::BIGINT AS queued_task_count,
    coalesce(task_rollup.in_progress_task_count, 0)::BIGINT AS in_progress_task_count,
    coalesce(task_rollup.blocked_task_count, 0)::BIGINT AS blocked_task_count,
    coalesce(inbox_rollup.open_inbox_count, 0)::BIGINT AS open_inbox_count,
    coalesce(inbox_rollup.urgent_inbox_count, 0)::BIGINT AS urgent_inbox_count,
    CASE WHEN org.department_key = 'risk' THEN coalesce(risk_rollup.open_risk_event_count, 0) ELSE 0 END::BIGINT AS open_risk_event_count,
    CASE WHEN org.department_key = 'risk' THEN coalesce(risk_rollup.critical_risk_event_count, 0) ELSE 0 END::BIGINT AS critical_risk_event_count,
    CASE WHEN org.department_key = 'risk' THEN coalesce(risk_rollup.high_risk_event_count, 0) ELSE 0 END::BIGINT AS high_risk_event_count,
    top_task.current_task_id,
    top_task.current_task_title,
    top_task.current_task_objective,
    top_task.current_task_status,
    top_task.current_task_priority,
    coalesce(top_task.current_task_title, latest_message.latest_message_subject, latest_worker.latest_worker_skill_name, replace(org.animation_state, '_', ' ')) AS current_work_title,
    coalesce(top_task.current_task_objective, latest_worker.latest_worker_summary, org.authority_scope, array_to_string(org.decision_rights, ', ')) AS current_work_detail,
    latest_message.latest_message_id,
    latest_message.latest_message_thread_key,
    latest_message.latest_message_from_agent,
    latest_message.latest_message_subject,
    latest_message.latest_message_priority,
    latest_message.latest_message_status,
    latest_message.latest_message_at,
    latest_worker.latest_worker_run_id,
    latest_worker.latest_worker_skill_key,
    latest_worker.latest_worker_skill_name,
    latest_worker.latest_worker_status,
    latest_worker.latest_worker_summary,
    latest_worker.latest_worker_output_note_path,
    latest_worker.latest_worker_started_at,
    latest_worker.latest_worker_finished_at,
    coalesce(task_rollup.open_tasks, '[]'::jsonb) AS open_tasks,
    (
        coalesce(task_rollup.open_task_count, 0) * 2
        + coalesce(inbox_rollup.open_inbox_count, 0)
        + coalesce(mb.unread_count, 0)
        + CASE WHEN org.department_key = 'risk' THEN coalesce(risk_rollup.open_risk_event_count, 0) * 3 ELSE 0 END
    )::BIGINT AS workload_score,
    CASE
        WHEN coalesce(task_rollup.blocked_task_count, 0) > 0 THEN 'blocked'
        WHEN org.department_key = 'risk' AND coalesce(risk_rollup.critical_risk_event_count, 0) > 0 THEN 'critical_risk'
        WHEN org.department_key = 'risk' AND coalesce(risk_rollup.open_risk_event_count, 0) > 0 THEN 'risk_review'
        WHEN coalesce(task_rollup.in_progress_task_count, 0) > 0 OR latest_worker.latest_worker_status = 'running' THEN 'executing'
        WHEN coalesce(mb.unread_count, 0) > 0 OR coalesce(inbox_rollup.urgent_inbox_count, 0) > 0 THEN 'needs_attention'
        WHEN coalesce(task_rollup.queued_task_count, 0) > 0 THEN 'queued'
        ELSE 'available'
    END AS live_state,
    greatest(
        coalesce(task_rollup.latest_task_at, 'epoch'::timestamptz),
        coalesce(inbox_rollup.latest_inbox_at, 'epoch'::timestamptz),
        coalesce(mb.latest_message_at, 'epoch'::timestamptz),
        coalesce(latest_worker.latest_worker_finished_at, latest_worker.latest_worker_started_at, 'epoch'::timestamptz),
        CASE WHEN org.department_key = 'risk' THEN coalesce(risk_rollup.latest_risk_event_at, 'epoch'::timestamptz) ELSE 'epoch'::timestamptz END,
        org.updated_at
    ) AS latest_activity_at
FROM org
LEFT JOIN agent.v_agent_mailboxes mb ON mb.agent_name = org.agent_name
LEFT JOIN task_rollup ON task_rollup.agent_name = org.agent_name
LEFT JOIN inbox_rollup ON inbox_rollup.agent_name = org.agent_name
LEFT JOIN latest_worker ON latest_worker.agent_name = org.agent_name
LEFT JOIN latest_message ON latest_message.agent_name = org.agent_name
LEFT JOIN top_task ON top_task.agent_name = org.agent_name
CROSS JOIN risk_rollup;

CREATE OR REPLACE VIEW agent.v_live_office_rooms AS
SELECT
    department_key AS room_key,
    department_name AS room_name,
    min(role_rank) AS room_rank,
    count(*)::BIGINT AS agent_count,
    count(*) FILTER (WHERE live_state <> 'available')::BIGINT AS active_agent_count,
    sum(open_task_count)::BIGINT AS open_task_count,
    sum(blocked_task_count)::BIGINT AS blocked_task_count,
    sum(unread_message_count)::BIGINT AS unread_message_count,
    sum(open_inbox_count)::BIGINT AS open_inbox_count,
    sum(open_risk_event_count)::BIGINT AS open_risk_event_count,
    sum(workload_score)::BIGINT AS room_workload_score,
    max(latest_activity_at) AS latest_activity_at,
    CASE
        WHEN sum(blocked_task_count) > 0 THEN 'blocked'
        WHEN sum(critical_risk_event_count) > 0 THEN 'critical_risk'
        WHEN sum(open_risk_event_count) > 0 THEN 'risk_review'
        WHEN sum(in_progress_task_count) > 0 THEN 'executing'
        WHEN sum(unread_message_count) > 0 OR sum(open_inbox_count) > 0 THEN 'needs_attention'
        WHEN sum(queued_task_count) > 0 THEN 'queued'
        ELSE 'available'
    END AS room_state,
    jsonb_agg(
        jsonb_build_object(
            'agent_name', agent_name,
            'display_title', display_title,
            'office_location', office_location,
            'live_state', live_state,
            'current_work_title', current_work_title,
            'current_work_detail', current_work_detail,
            'open_task_count', open_task_count,
            'unread_message_count', unread_message_count,
            'open_inbox_count', open_inbox_count,
            'workload_score', workload_score,
            'color_token', color_token,
            'icon_hint', icon_hint
        )
        ORDER BY role_rank, agent_name
    ) AS agents
FROM agent.v_live_office_agent_activity
GROUP BY department_key, department_name
ORDER BY
    CASE department_key
        WHEN 'executive' THEN 1
        WHEN 'runtime' THEN 2
        WHEN 'portfolio' THEN 3
        WHEN 'research' THEN 4
        WHEN 'quant' THEN 5
        WHEN 'trading' THEN 6
        WHEN 'risk' THEN 7
        WHEN 'data' THEN 8
        WHEN 'knowledge' THEN 9
        ELSE 10
    END,
    room_name;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_live_office_rooms', 'mcp_tool', 'Jarvis', 'read_only', true, 'Read the Live AI Office v1 room map backed by agent tasks, inboxes, messages, worker runs, and risk events.', '{"reads":["agent.v_live_office_rooms"]}'::jsonb),
    ('ai_os_live_office_agent_activity', 'mcp_tool', 'Jarvis', 'read_only', true, 'Read per-agent live office activity, current work, mailbox pressure, tasks, and worker state.', '{"reads":["agent.v_live_office_agent_activity"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
