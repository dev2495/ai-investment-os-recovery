CREATE TABLE IF NOT EXISTS agent.mcp_audit_log (
    id BIGSERIAL PRIMARY KEY,
    tool_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    actor TEXT NOT NULL DEFAULT 'Jarvis',
    status TEXT NOT NULL DEFAULT 'success',
    target_table TEXT,
    target_id TEXT,
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_audit_tool ON agent.mcp_audit_log (tool_name);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_created ON agent.mcp_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_status ON agent.mcp_audit_log (status);

ALTER TABLE ops.browser_runs
    ADD COLUMN IF NOT EXISTS actor TEXT NOT NULL DEFAULT 'Browser Research Runner',
    ADD COLUMN IF NOT EXISTS page_title TEXT,
    ADD COLUMN IF NOT EXISTS extracted_text_preview TEXT,
    ADD COLUMN IF NOT EXISTS source_kind TEXT,
    ADD COLUMN IF NOT EXISTS source_ref TEXT;

CREATE INDEX IF NOT EXISTS idx_browser_runs_created ON ops.browser_runs (id DESC);
CREATE INDEX IF NOT EXISTS idx_browser_runs_actor ON ops.browser_runs (actor);

CREATE OR REPLACE VIEW ops.v_browser_runs AS
SELECT
    br.id,
    br.task_id,
    br.run_type,
    br.target_url,
    br.status,
    br.actor,
    br.page_title,
    br.screenshot_path,
    br.extracted_artifact_id,
    br.source_kind,
    br.source_ref,
    br.started_at,
    br.finished_at,
    br.notes,
    br.metadata
FROM ops.browser_runs br
ORDER BY br.id DESC;

CREATE OR REPLACE VIEW agent.v_recent_mcp_audit AS
SELECT
    id,
    tool_name,
    action_type,
    permission_level,
    actor,
    status,
    target_table,
    target_id,
    left(error_message, 500) AS error_message,
    created_at
FROM agent.mcp_audit_log
ORDER BY created_at DESC, id DESC;

CREATE OR REPLACE VIEW agent.v_mcp_capability_matrix AS
SELECT
    tool_name,
    tool_type,
    owning_agent,
    permission_level,
    enabled,
    description,
    config
FROM agent.tool_registry
WHERE enabled = true
ORDER BY
    CASE permission_level
        WHEN 'read_only' THEN 1
        WHEN 'write_db_manual_only' THEN 2
        WHEN 'write_with_approval' THEN 3
        WHEN 'browser_read' THEN 4
        WHEN 'browser_capture' THEN 5
        ELSE 6
    END,
    tool_name;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_mcp_capabilities', 'mcp_tool', 'Jarvis', 'read_only', true, 'List current MCP tools, permissions, owners, and guardrails.', '{"surface":"mcp"}'::jsonb),
    ('ai_os_mcp_audit_log', 'mcp_tool', 'Risk Agent', 'read_only', true, 'Read recent MCP write/read audit events.', '{"surface":"mcp"}'::jsonb),
    ('ai_os_create_task', 'mcp_tool', 'Jarvis', 'write_with_approval', true, 'Create an agent task and optional inbox item.', '{"writes":["agent.tasks","agent.inbox_items"]}'::jsonb),
    ('ai_os_update_task_status', 'mcp_tool', 'Jarvis', 'write_with_approval', true, 'Update agent task status, evidence, and output path.', '{"writes":["agent.tasks"]}'::jsonb),
    ('ai_os_list_inbox', 'mcp_tool', 'Jarvis', 'read_only', true, 'List agent inbox items with task linkage and evidence.', '{"reads":["agent.inbox_items"]}'::jsonb),
    ('ai_os_update_inbox_status', 'mcp_tool', 'Jarvis', 'write_with_approval', true, 'Update one inbox item status and action text.', '{"writes":["agent.inbox_items"]}'::jsonb),
    ('ai_os_create_approval', 'mcp_tool', 'Risk Agent', 'write_with_approval', true, 'Create a human approval request for reports, strategy, data imports, or system changes.', '{"writes":["agent.approvals"]}'::jsonb),
    ('ai_os_decide_approval', 'mcp_tool', 'Risk Agent', 'write_with_approval', true, 'Approve or reject a pending approval with audit trail.', '{"writes":["agent.approvals"]}'::jsonb),
    ('ai_os_create_research_idea', 'mcp_tool', 'Research Lead', 'write_with_approval', true, 'Create a research idea with symbols, thesis, catalyst, scores, and evidence.', '{"writes":["research.ideas"]}'::jsonb),
    ('ai_os_record_raw_artifact', 'mcp_tool', 'Data Steward', 'write_db_manual_only', true, 'Register a raw artifact or browser/public source output in core.raw_artifacts.', '{"writes":["core.raw_artifacts"]}'::jsonb),
    ('ai_os_write_obsidian_note', 'mcp_tool', 'Knowledge Librarian', 'write_with_approval', true, 'Write approved markdown output into structured Obsidian folders and reindex.', '{"writes":["knowledge.obsidian_notes","filesystem:ai memory"]}'::jsonb),
    ('ai_os_start_browser_run', 'mcp_tool', 'Browser Research Runner', 'browser_read', true, 'Create a browser run request/log row for public-source research or UI inspection.', '{"writes":["ops.browser_runs"],"external_browser_control":false}'::jsonb),
    ('ai_os_complete_browser_run', 'mcp_tool', 'Browser Research Runner', 'browser_capture', true, 'Complete a browser run with title, preview, screenshot path, artifact link, and notes.', '{"writes":["ops.browser_runs","core.raw_artifacts"]}'::jsonb),
    ('ai_os_browser_runs', 'mcp_tool', 'Browser Research Runner', 'read_only', true, 'List browser run queue/history.', '{"reads":["ops.browser_runs"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_mcp_capabilities',
            'ai_os_mcp_audit_log',
            'ai_os_create_task',
            'ai_os_update_task_status',
            'ai_os_list_inbox',
            'ai_os_update_inbox_status',
            'ai_os_write_obsidian_note'
        ]::TEXT[]) AS tool
    ),
    updated_at = now()
WHERE module_key IN ('command_center', 'obsidian_graph', 'approval_center');

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_start_browser_run',
            'ai_os_complete_browser_run',
            'ai_os_browser_runs',
            'ai_os_record_raw_artifact'
        ]::TEXT[]) AS tool
    ),
    updated_at = now()
WHERE module_key IN ('research_inbox', 'data_sources');

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_create_research_idea',
            'ai_os_record_raw_artifact'
        ]::TEXT[]) AS tool
    ),
    updated_at = now()
WHERE module_key IN ('research_inbox', 'portfolio_office');

CREATE OR REPLACE VIEW core.v_control_plane_snapshot AS
SELECT 'control_modules' AS metric, count(*)::TEXT AS value FROM core.control_plane_modules
UNION ALL
SELECT 'active_modules', count(*)::TEXT FROM core.control_plane_modules WHERE status IN ('active','installed')
UNION ALL
SELECT 'data_sources', count(*)::TEXT FROM core.data_source_registry
UNION ALL
SELECT 'mapped_or_online_sources', count(*)::TEXT FROM core.data_source_registry WHERE status IN ('active','installed','imported','mapped')
UNION ALL
SELECT 'registered_strategies', count(*)::TEXT FROM strategy.strategy_registry
UNION ALL
SELECT 'paper_or_mapped_strategies', count(*)::TEXT FROM strategy.strategy_registry WHERE live_mode IN ('paper','shadow') OR status = 'mapped'
UNION ALL
SELECT 'registered_workflows', count(*)::TEXT FROM agent.workflow_registry
UNION ALL
SELECT 'active_workflows', count(*)::TEXT FROM agent.workflow_registry WHERE status IN ('active','installed')
UNION ALL
SELECT 'clients', count(*)::TEXT FROM portfolio.clients
UNION ALL
SELECT 'staged_holding_updates', count(*)::TEXT FROM portfolio.manual_holding_updates WHERE status = 'staged'
UNION ALL
SELECT 'mcp_enabled_tools', count(*)::TEXT FROM agent.tool_registry WHERE enabled = true
UNION ALL
SELECT 'browser_runs', count(*)::TEXT FROM ops.browser_runs
UNION ALL
SELECT 'mcp_audit_events', count(*)::TEXT FROM agent.mcp_audit_log;
