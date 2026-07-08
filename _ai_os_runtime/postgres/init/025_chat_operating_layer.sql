CREATE TABLE IF NOT EXISTS agent.chat_turns (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT NOT NULL DEFAULT 'default',
    actor TEXT NOT NULL DEFAULT 'Devarsh',
    assistant_name TEXT NOT NULL DEFAULT 'Charlie Munger',
    user_message TEXT NOT NULL,
    assistant_message TEXT NOT NULL,
    route_name TEXT,
    model_provider TEXT,
    model_name TEXT,
    model_status TEXT NOT NULL DEFAULT 'not_called',
    retrieval_hits JSONB NOT NULL DEFAULT '[]'::jsonb,
    widget_intents JSONB NOT NULL DEFAULT '[]'::jsonb,
    tool_intents JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_turns_session_time ON agent.chat_turns (session_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_turns_assistant ON agent.chat_turns (assistant_name, created_at DESC);

CREATE TABLE IF NOT EXISTS ops.dashboard_widget_intents (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT NOT NULL DEFAULT 'default',
    source_chat_turn_id BIGINT REFERENCES agent.chat_turns(id) ON DELETE SET NULL,
    widget_key TEXT NOT NULL,
    widget_title TEXT NOT NULL,
    widget_type TEXT NOT NULL,
    workspace TEXT NOT NULL DEFAULT 'command',
    status TEXT NOT NULL DEFAULT 'suggested',
    priority TEXT NOT NULL DEFAULT 'medium',
    owner_agent TEXT NOT NULL DEFAULT 'Jarvis',
    query_ref TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dashboard_widget_intents_status ON ops.dashboard_widget_intents (status);
CREATE INDEX IF NOT EXISTS idx_dashboard_widget_intents_workspace ON ops.dashboard_widget_intents (workspace, created_at DESC);

CREATE OR REPLACE VIEW agent.v_recent_chat_turns AS
SELECT
    id,
    session_key,
    actor,
    assistant_name,
    user_message,
    assistant_message,
    route_name,
    model_provider,
    model_name,
    model_status,
    retrieval_hits,
    widget_intents,
    tool_intents,
    metadata,
    created_at
FROM agent.chat_turns
ORDER BY created_at DESC, id DESC
LIMIT 100;

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

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'charlie_chat_endpoint',
        'api_chat',
        'Charlie Munger',
        'read_write_gated',
        true,
        'Chat endpoint that retrieves from Qdrant/Postgres, returns dashboard widget intents, and persists chat turns.',
        '{"api_route":"/api/chat","execution_allowed":false}'::jsonb
    ),
    (
        'dashboard_widget_intent_writer',
        'dashboard_control',
        'Jarvis',
        'write_with_approval',
        true,
        'Writes suggested dashboard widgets from chat/orchestrator output for the UI to render or queue.',
        '{"target":"ops.dashboard_widget_intents","default_status":"suggested"}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model, escalation_provider,
    escalation_model, max_cost_tier, notes, enabled
)
VALUES
    (
        'local_embedding_retrieval',
        'embedding_and_retrieval',
        'ollama',
        'mxbai-embed-large',
        NULL,
        NULL,
        'local',
        'Local embedding model for Qdrant semantic retrieval over Obsidian, research reports, trade journals, and strategy artifacts.',
        true
    ),
    (
        'always_on_daily_driver',
        'chat_routing_and_light_synthesis',
        'ollama',
        'qwen3:8b',
        'codex_or_cloud',
        'frontier_on_approval',
        'hybrid',
        'Recommended always-on local driver once downloaded. Handles normal chat, routing, summaries, widget intents, and light portfolio questions. Escalate heavy reasoning, coding, long filings, and critical decisions.',
        true
    )
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;
