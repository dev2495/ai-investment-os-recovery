CREATE OR REPLACE VIEW agent.v_employee_profiles_v1 AS
WITH base AS (
    SELECT
        active.agent_name,
        active.display_title,
        active.department,
        active.department_name,
        active.role_scope,
        active.persona,
        active.operating_style,
        active.mental_models,
        active.default_model_route,
        active.default_tools,
        active.permission_level,
        active.output_targets,
        active.guardrails,
        active.escalation_rules,
        active.daily_cadence,
        active.cost_policy,
        active.human_interface,
        active.skill_count,
        active.primary_skills,
        org.reports_to_agent,
        org.reports_to_title,
        org.role_rank,
        org.hierarchy_level,
        org.authority_scope,
        org.decision_rights,
        org.must_consult,
        org.can_delegate_to,
        org.approval_required_for,
        org.character_name,
        org.avatar_role,
        org.visual_traits,
        org.voice_style,
        org.office_location,
        org.animation_state,
        org.color_token,
        org.icon_hint,
        org.mailbox_address,
        org.mailbox_key
    FROM agent.v_active_agents active
    LEFT JOIN agent.v_agent_org_chart org ON org.agent_name = active.agent_name
),
activity AS (
    SELECT *
    FROM agent.v_live_office_agent_activity
),
model AS (
    SELECT *
    FROM agent.v_agent_model_matrix
),
skill_rollup AS (
    SELECT
        assigned.agent_name,
        count(*)::BIGINT AS assigned_skill_count,
        count(*) FILTER (WHERE skill.status = 'active')::BIGINT AS active_skill_count,
        jsonb_agg(
            jsonb_build_object(
                'skill_key', skill.skill_key,
                'skill_name', skill.skill_name,
                'skill_family', skill.skill_family,
                'skill_type', skill.skill_type,
                'status', skill.status,
                'execution_mode', skill.execution_mode,
                'permission_level', skill.permission_level,
                'risk_notes', skill.risk_notes
            )
            ORDER BY
                CASE WHEN assigned.is_primary THEN 1 ELSE 2 END,
                CASE skill.status WHEN 'active' THEN 1 WHEN 'planned' THEN 2 ELSE 3 END,
                skill.skill_family,
                skill.skill_key
        ) AS skills
    FROM agent.agent_skill_map assigned
    JOIN agent.skills skill ON skill.skill_key = assigned.skill_key
    GROUP BY assigned.agent_name
),
tool_rollup AS (
    SELECT
        tool.owning_agent AS agent_name,
        count(*) FILTER (WHERE tool.enabled)::BIGINT AS enabled_tool_count,
        count(*) FILTER (WHERE tool.permission_level = 'read_only' AND tool.enabled)::BIGINT AS read_only_tool_count,
        count(*) FILTER (WHERE tool.permission_level <> 'read_only' AND tool.enabled)::BIGINT AS write_or_browser_tool_count,
        jsonb_agg(
            jsonb_build_object(
                'tool_name', tool.tool_name,
                'tool_type', tool.tool_type,
                'permission_level', tool.permission_level,
                'enabled', tool.enabled,
                'description', tool.description,
                'config', tool.config
            )
            ORDER BY
                CASE tool.permission_level WHEN 'read_only' THEN 1 WHEN 'write_db_manual_only' THEN 2 WHEN 'write_with_approval' THEN 3 WHEN 'browser_read' THEN 4 ELSE 5 END,
                tool.tool_name
        ) FILTER (WHERE tool.enabled) AS tools
    FROM agent.tool_registry tool
    WHERE tool.owning_agent IS NOT NULL
    GROUP BY tool.owning_agent
),
task_rollup AS (
    SELECT
        task.owner_agent AS agent_name,
        count(*) FILTER (WHERE task.status IN ('queued','in_progress','blocked'))::BIGINT AS open_task_count,
        count(*) FILTER (WHERE task.status = 'blocked')::BIGINT AS blocked_task_count,
        jsonb_agg(
            jsonb_build_object(
                'id', task.id,
                'title', task.title,
                'objective', task.objective,
                'status', task.status,
                'priority', task.priority,
                'source_kind', task.source_kind,
                'source_ref', task.source_ref,
                'output_note_path', task.output_note_path,
                'updated_at', task.updated_at
            )
            ORDER BY
                CASE task.status WHEN 'blocked' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'queued' THEN 3 ELSE 4 END,
                CASE task.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                task.updated_at DESC
        ) FILTER (WHERE task.status IN ('queued','in_progress','blocked')) AS open_tasks
    FROM agent.tasks task
    GROUP BY task.owner_agent
),
inbox_rollup AS (
    SELECT
        inbox.owner_agent AS agent_name,
        count(*) FILTER (WHERE inbox.status IN ('new','open','in_progress'))::BIGINT AS open_inbox_count,
        count(*) FILTER (WHERE inbox.priority IN ('critical','high') AND inbox.status IN ('new','open','in_progress'))::BIGINT AS urgent_inbox_count,
        jsonb_agg(
            jsonb_build_object(
                'id', inbox.id,
                'title', inbox.title,
                'status', inbox.status,
                'priority', inbox.priority,
                'recommended_action', inbox.recommended_action,
                'target_workspace', inbox.target_workspace,
                'updated_at', inbox.updated_at
            )
            ORDER BY
                CASE inbox.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                inbox.updated_at DESC
        ) FILTER (WHERE inbox.status IN ('new','open','in_progress')) AS open_inbox_items
    FROM agent.inbox_items inbox
    GROUP BY inbox.owner_agent
),
message_rollup AS (
    SELECT
        agent_name,
        count(*) FILTER (WHERE direction = 'received' AND status = 'unread')::BIGINT AS unread_received_count,
        count(*) FILTER (WHERE direction = 'received')::BIGINT AS received_message_count,
        count(*) FILTER (WHERE direction = 'sent')::BIGINT AS sent_message_count,
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'direction', direction,
                'thread_key', thread_key,
                'from_agent', from_agent,
                'to_agent', to_agent,
                'subject', subject,
                'priority', priority,
                'status', status,
                'created_at', created_at
            )
            ORDER BY created_at DESC
        ) FILTER (WHERE row_rank <= 5) AS recent_messages
    FROM (
        SELECT
            msg.to_agent AS agent_name,
            'received'::TEXT AS direction,
            msg.id,
            msg.thread_key,
            msg.from_agent,
            msg.to_agent,
            msg.subject,
            msg.priority,
            msg.status,
            msg.created_at,
            row_number() OVER (PARTITION BY msg.to_agent ORDER BY msg.created_at DESC, msg.id DESC) AS row_rank
        FROM agent.agent_messages msg
        UNION ALL
        SELECT
            msg.from_agent AS agent_name,
            'sent'::TEXT AS direction,
            msg.id,
            msg.thread_key,
            msg.from_agent,
            msg.to_agent,
            msg.subject,
            msg.priority,
            msg.status,
            msg.created_at,
            row_number() OVER (PARTITION BY msg.from_agent ORDER BY msg.created_at DESC, msg.id DESC) AS row_rank
        FROM agent.agent_messages msg
    ) messages
    GROUP BY agent_name
),
run_rollup AS (
    SELECT
        runs.agent_name,
        count(*)::BIGINT AS worker_run_count,
        count(*) FILTER (WHERE runs.status = 'completed')::BIGINT AS completed_worker_run_count,
        count(*) FILTER (WHERE nullif(runs.output_note_path, '') IS NOT NULL)::BIGINT AS output_artifact_count,
        max(coalesce(runs.finished_at, runs.started_at, runs.created_at)) AS latest_worker_activity_at,
        jsonb_agg(
            jsonb_build_object(
                'id', runs.id,
                'task_id', runs.task_id,
                'task_title', runs.task_title,
                'skill_key', runs.skill_key,
                'skill_name', runs.skill_name,
                'status', runs.status,
                'output_summary', runs.output_summary,
                'output_note_path', runs.output_note_path,
                'finished_at', runs.finished_at
            )
            ORDER BY runs.created_at DESC
        ) FILTER (WHERE runs.row_rank <= 5) AS recent_outputs
    FROM (
        SELECT
            wr.*,
            row_number() OVER (PARTITION BY wr.agent_name ORDER BY wr.created_at DESC, wr.id DESC) AS row_rank
        FROM agent.v_recent_worker_runs wr
    ) runs
    GROUP BY runs.agent_name
),
approval_rollup AS (
    SELECT
        board.owner_agent AS agent_name,
        count(*)::BIGINT AS approval_count,
        count(*) FILTER (WHERE board.approval_status = 'pending')::BIGINT AS pending_approval_count,
        jsonb_agg(
            jsonb_build_object(
                'approval_id', board.approval_id,
                'board_lane', board.board_lane,
                'title', board.title,
                'risk_level', board.risk_level,
                'approval_status', board.approval_status,
                'linked_source', board.linked_source,
                'recommended_next_action', board.recommended_next_action,
                'latest_activity_at', board.latest_activity_at
            )
            ORDER BY board.status_rank, board.risk_rank, board.latest_activity_at DESC
        ) FILTER (WHERE board.row_rank <= 5) AS approvals
    FROM (
        SELECT
            approval.*,
            row_number() OVER (PARTITION BY approval.owner_agent ORDER BY approval.status_rank, approval.risk_rank, approval.latest_activity_at DESC) AS row_rank
        FROM agent.v_approval_board_items approval
    ) board
    GROUP BY board.owner_agent
)
SELECT
    base.agent_name,
    base.display_title,
    base.department,
    base.department_name,
    base.role_scope,
    base.persona,
    base.operating_style,
    base.mental_models,
    base.default_model_route,
    base.default_tools,
    base.permission_level,
    base.output_targets,
    base.guardrails,
    base.escalation_rules,
    base.daily_cadence,
    base.cost_policy,
    base.human_interface,
    base.reports_to_agent,
    base.reports_to_title,
    base.role_rank,
    base.hierarchy_level,
    base.authority_scope,
    base.decision_rights,
    base.must_consult,
    base.can_delegate_to,
    base.approval_required_for,
    base.character_name,
    base.avatar_role,
    base.visual_traits,
    base.voice_style,
    base.office_location,
    base.animation_state,
    base.color_token,
    base.icon_hint,
    base.mailbox_address,
    base.mailbox_key,
    coalesce(model.primary_route, base.default_model_route) AS primary_route,
    model.route_provider,
    model.route_default_model,
    model.model_key,
    model.assigned_provider,
    model.assigned_model,
    model.model_family,
    model.deployment_target,
    model.estimated_disk_gb,
    model.model_status,
    model.fallback_route,
    model.escalation_route,
    model.context_policy,
    model.cost_policy AS model_cost_policy,
    model.max_autonomous_cost_tier,
    model.escalation_triggers,
    model.notes AS model_notes,
    coalesce(skill_rollup.assigned_skill_count, 0)::BIGINT AS assigned_skill_count,
    coalesce(skill_rollup.active_skill_count, 0)::BIGINT AS active_skill_count,
    coalesce(tool_rollup.enabled_tool_count, 0)::BIGINT AS enabled_tool_count,
    coalesce(tool_rollup.read_only_tool_count, 0)::BIGINT AS read_only_tool_count,
    coalesce(tool_rollup.write_or_browser_tool_count, 0)::BIGINT AS write_or_browser_tool_count,
    coalesce(task_rollup.open_task_count, 0)::BIGINT AS open_task_count,
    coalesce(task_rollup.blocked_task_count, 0)::BIGINT AS blocked_task_count,
    coalesce(inbox_rollup.open_inbox_count, 0)::BIGINT AS open_inbox_count,
    coalesce(inbox_rollup.urgent_inbox_count, 0)::BIGINT AS urgent_inbox_count,
    coalesce(message_rollup.unread_received_count, 0)::BIGINT AS unread_received_count,
    coalesce(message_rollup.received_message_count, 0)::BIGINT AS received_message_count,
    coalesce(message_rollup.sent_message_count, 0)::BIGINT AS sent_message_count,
    coalesce(run_rollup.worker_run_count, 0)::BIGINT AS worker_run_count,
    coalesce(run_rollup.completed_worker_run_count, 0)::BIGINT AS completed_worker_run_count,
    coalesce(run_rollup.output_artifact_count, 0)::BIGINT AS output_artifact_count,
    coalesce(approval_rollup.approval_count, 0)::BIGINT AS approval_count,
    coalesce(approval_rollup.pending_approval_count, 0)::BIGINT AS pending_approval_count,
    activity.live_state,
    activity.current_work_title,
    activity.current_work_detail,
    activity.workload_score,
    activity.latest_activity_at,
    coalesce(skill_rollup.skills, '[]'::jsonb) AS skills,
    coalesce(tool_rollup.tools, '[]'::jsonb) AS tools,
    coalesce(task_rollup.open_tasks, '[]'::jsonb) AS open_tasks,
    coalesce(inbox_rollup.open_inbox_items, '[]'::jsonb) AS open_inbox_items,
    coalesce(message_rollup.recent_messages, '[]'::jsonb) AS recent_messages,
    coalesce(run_rollup.recent_outputs, '[]'::jsonb) AS recent_outputs,
    coalesce(approval_rollup.approvals, '[]'::jsonb) AS approvals,
    jsonb_build_object(
        'profile', 'agent.v_employee_profiles_v1',
        'agent_name', base.agent_name,
        'source_views', jsonb_build_array(
            'agent.v_active_agents',
            'agent.v_agent_org_chart',
            'agent.v_live_office_agent_activity',
            'agent.v_agent_model_matrix',
            'agent.v_agent_skill_matrix',
            'agent.tool_registry',
            'agent.v_recent_worker_runs',
            'agent.v_approval_board_items'
        )
    ) AS evidence
FROM base
LEFT JOIN activity ON activity.agent_name = base.agent_name
LEFT JOIN model ON model.agent_name = base.agent_name
LEFT JOIN skill_rollup ON skill_rollup.agent_name = base.agent_name
LEFT JOIN tool_rollup ON tool_rollup.agent_name = base.agent_name
LEFT JOIN task_rollup ON task_rollup.agent_name = base.agent_name
LEFT JOIN inbox_rollup ON inbox_rollup.agent_name = base.agent_name
LEFT JOIN message_rollup ON message_rollup.agent_name = base.agent_name
LEFT JOIN run_rollup ON run_rollup.agent_name = base.agent_name
LEFT JOIN approval_rollup ON approval_rollup.agent_name = base.agent_name
ORDER BY base.role_rank, base.agent_name;

CREATE OR REPLACE VIEW agent.v_employee_profile_summary AS
SELECT 'agents'::TEXT AS metric, count(*)::TEXT AS value, 'Active employee profiles in the AI Office.'::TEXT AS interpretation
FROM agent.v_employee_profiles_v1
UNION ALL
SELECT 'model_routes', count(*) FILTER (WHERE primary_route IS NOT NULL)::TEXT, 'Agents with an assigned primary model route.'
FROM agent.v_employee_profiles_v1
UNION ALL
SELECT 'enabled_tools', coalesce(sum(enabled_tool_count), 0)::TEXT, 'Enabled tools mapped to owning agents.'
FROM agent.v_employee_profiles_v1
UNION ALL
SELECT 'open_tasks', coalesce(sum(open_task_count), 0)::TEXT, 'Open tasks assigned to agents.'
FROM agent.v_employee_profiles_v1
UNION ALL
SELECT 'output_artifacts', coalesce(sum(output_artifact_count), 0)::TEXT, 'Worker runs with output note paths.'
FROM agent.v_employee_profiles_v1
UNION ALL
SELECT 'pending_approvals', coalesce(sum(pending_approval_count), 0)::TEXT, 'Pending approvals owned by agents.'
FROM agent.v_employee_profiles_v1;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_employee_profiles', 'mcp_tool', 'Jarvis', 'read_only', true, 'Read employee profile cards with role, personality, model route, tools, skills, tasks, messages, outputs, and approvals.', '{"reads":["agent.v_employee_profiles_v1","agent.v_employee_profile_summary"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
