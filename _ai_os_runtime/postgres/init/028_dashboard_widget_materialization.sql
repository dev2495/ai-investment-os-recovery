CREATE TABLE IF NOT EXISTS ops.dashboard_widgets (
    id BIGSERIAL PRIMARY KEY,
    widget_key TEXT NOT NULL,
    widget_title TEXT NOT NULL,
    widget_type TEXT NOT NULL,
    workspace TEXT NOT NULL DEFAULT 'command',
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'medium',
    owner_agent TEXT NOT NULL DEFAULT 'Jarvis',
    query_ref TEXT,
    source_intent_id BIGINT REFERENCES ops.dashboard_widget_intents(id) ON DELETE SET NULL,
    source_chat_turn_id BIGINT REFERENCES agent.chat_turns(id) ON DELETE SET NULL,
    linked_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    layout JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_binding JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_materialized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_refreshed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace, widget_key)
);

CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_workspace ON ops.dashboard_widgets (workspace, status, priority);
CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_owner ON ops.dashboard_widgets (owner_agent, status);
CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_task ON ops.dashboard_widgets (linked_task_id);

ALTER TABLE ops.dashboard_widget_intents
    ADD COLUMN IF NOT EXISTS materialized_widget_id BIGINT REFERENCES ops.dashboard_widgets(id) ON DELETE SET NULL;

DROP VIEW IF EXISTS ops.v_dashboard_widget_intents;

CREATE OR REPLACE VIEW ops.v_dashboard_widget_intents AS
SELECT
    id,
    session_key,
    source_chat_turn_id,
    widget_key,
    widget_title,
    widget_type,
    workspace,
    status,
    priority,
    owner_agent,
    query_ref,
    materialized_widget_id,
    config,
    evidence,
    created_at,
    updated_at
FROM ops.dashboard_widget_intents
ORDER BY
    CASE status
        WHEN 'active' THEN 1
        WHEN 'suggested' THEN 2
        WHEN 'queued' THEN 3
        ELSE 4
    END,
    created_at DESC;

CREATE OR REPLACE VIEW ops.v_dashboard_widgets AS
SELECT
    w.id,
    w.widget_key,
    w.widget_title,
    w.widget_type,
    w.workspace,
    w.status,
    w.priority,
    w.owner_agent,
    w.query_ref,
    w.source_intent_id,
    w.source_chat_turn_id,
    w.linked_task_id,
    t.status AS task_status,
    t.approval_required AS task_approval_required,
    i.id AS inbox_item_id,
    i.status AS inbox_status,
    w.config,
    w.layout,
    w.data_binding,
    w.evidence,
    w.last_materialized_at,
    w.last_refreshed_at,
    w.created_at,
    w.updated_at
FROM ops.dashboard_widgets w
LEFT JOIN agent.tasks t ON t.id = w.linked_task_id
LEFT JOIN LATERAL (
    SELECT id, status
    FROM agent.inbox_items
    WHERE task_id = w.linked_task_id
    ORDER BY created_at DESC, id DESC
    LIMIT 1
) i ON true
ORDER BY
    CASE w.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE w.status WHEN 'active' THEN 1 WHEN 'suggested' THEN 2 WHEN 'queued' THEN 3 ELSE 4 END,
    w.updated_at DESC;

CREATE OR REPLACE VIEW agent.v_dashboard_agent_jobs AS
SELECT
    t.id AS task_id,
    t.title,
    t.objective,
    t.owner_agent,
    t.status,
    t.priority,
    t.approval_required,
    t.source_kind,
    t.source_ref,
    t.output_format,
    t.output_note_path,
    t.evidence,
    w.id AS widget_id,
    w.widget_key,
    w.widget_title,
    w.workspace,
    w.widget_type,
    i.id AS inbox_item_id,
    i.status AS inbox_status,
    t.created_at,
    t.updated_at
FROM agent.tasks t
LEFT JOIN ops.dashboard_widgets w ON w.linked_task_id = t.id
LEFT JOIN LATERAL (
    SELECT id, status
    FROM agent.inbox_items
    WHERE task_id = t.id
    ORDER BY created_at DESC, id DESC
    LIMIT 1
) i ON true
WHERE t.source_kind IN ('ops.dashboard_widgets', 'ops.dashboard_widget_intents')
ORDER BY
    CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE t.status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'blocked' THEN 3 WHEN 'needs_review' THEN 4 ELSE 5 END,
    t.updated_at DESC;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'dashboard_widget_materializer',
        'dashboard_control',
        'Jarvis',
        'write_with_approval',
        true,
        'Materializes dashboard widget intents into live dashboard widgets, linked agent tasks, and inbox work items.',
        '{"api_route":"/api/dashboard/widgets/materialize","writes":["ops.dashboard_widgets","agent.tasks","agent.inbox_items"]}'::jsonb
    ),
    (
        'dashboard_agent_job_queue',
        'agent_queue',
        'Jarvis',
        'write_with_approval',
        true,
        'Queues dashboard-maintenance jobs for specialist agents after Charlie/Jarvis infer required widgets.',
        '{"view":"agent.v_dashboard_agent_jobs","source_kind":"ops.dashboard_widgets"}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES (
    'chat_to_live_dashboard_widgets',
    'Chat To Live Dashboard Widgets',
    'dashboard_materialization',
    'Jarvis',
    'chat_or_manual',
    'active',
    'write_with_approval',
    ARRAY['agent.chat_turns','ops.dashboard_widget_intents']::TEXT[],
    ARRAY['ops.dashboard_widgets','agent.tasks','agent.inbox_items']::TEXT[],
    false,
    'on every Charlie chat with widget intents and on manual materialize request',
    'Turns Charlie/Jarvis widget intents into live dashboard widgets and specialist agent work queue rows.',
    '{"foundation_layer":"interactive_operating_layer"}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();
