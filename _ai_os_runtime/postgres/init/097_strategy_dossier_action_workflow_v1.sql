CREATE TABLE IF NOT EXISTS strategy.idea_dossier_actions (
    id BIGSERIAL PRIMARY KEY,
    dossier_id BIGINT NOT NULL REFERENCES strategy.idea_dossiers(id) ON DELETE CASCADE,
    action_key TEXT NOT NULL UNIQUE,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    target_agent TEXT,
    target_table TEXT,
    target_id TEXT,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_by TEXT NOT NULL DEFAULT 'Charlie Munger',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_idea_dossier_actions_dossier
ON strategy.idea_dossier_actions (dossier_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_idea_dossier_actions_type
ON strategy.idea_dossier_actions (action_type, created_at DESC);

CREATE OR REPLACE VIEW strategy.v_idea_dossier_actions AS
SELECT
    action.id,
    action.dossier_id,
    dossier.dossier_key,
    dossier.title AS dossier_title,
    dossier.symbols,
    dossier.status AS dossier_status,
    action.action_key,
    action.action_type,
    action.status,
    action.target_agent,
    action.target_table,
    action.target_id,
    action.output_payload,
    action.error_message,
    action.created_by,
    action.created_at,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed
FROM strategy.idea_dossier_actions action
JOIN strategy.idea_dossiers dossier ON dossier.id = action.dossier_id
ORDER BY action.created_at DESC, action.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_strategy_dossier_action', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true,
     'Convert a persistent strategy dossier into gated next work: more evidence, Quant Lab, Special Situations, committee review, or committee memo. Never approves broker/paper/live execution.',
     '{"script":"_ai_os_runtime/scripts/run_strategy_dossier_action.py","reads":["strategy.v_idea_dossiers","strategy.v_user_defined_optimizer_runs","strategy.v_strategy_committee_queue"],"writes":["strategy.idea_dossier_actions","agent.tasks","agent.inbox_items","strategy.committee_reviews","knowledge.obsidian_notes"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_strategy_dossier_actions', 'mcp_tool', 'Charlie Munger', 'read_only', true,
     'Read recent actions taken from persistent strategy dossiers into specialist or committee workflows.',
     '{"reads":["strategy.v_idea_dossier_actions"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'strategy.idea_dossier_actions',
            'strategy.v_idea_dossier_actions'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_run_strategy_dossier_action',
            'ai_os_strategy_dossier_actions'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use dossier actions to move persistent strategy ideas into specialist queues, committee reviews, or memo generation without approving execution.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'trading_desk', 'runtime');
