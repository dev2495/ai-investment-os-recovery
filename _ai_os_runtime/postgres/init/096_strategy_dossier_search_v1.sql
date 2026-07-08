CREATE TABLE IF NOT EXISTS strategy.idea_dossier_search_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    query_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    search_mode TEXT,
    embedding_model TEXT,
    qdrant_available BOOLEAN NOT NULL DEFAULT false,
    fallback_used BOOLEAN NOT NULL DEFAULT false,
    match_count INTEGER NOT NULL DEFAULT 0,
    results JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_by TEXT NOT NULL DEFAULT 'Strategy Dossier Search Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_idea_dossier_search_runs_created
ON strategy.idea_dossier_search_runs (created_at DESC);

CREATE OR REPLACE VIEW strategy.v_idea_dossier_search_runs AS
SELECT
    id,
    run_key,
    query_text,
    status,
    search_mode,
    embedding_model,
    qdrant_available,
    fallback_used,
    match_count,
    results,
    error_message,
    started_at,
    finished_at,
    duration_ms,
    created_by,
    created_at
FROM strategy.idea_dossier_search_runs
ORDER BY started_at DESC, id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_search_strategy_idea_dossiers', 'mcp_tool', 'Strategy Dossier Search Agent', 'read_db_and_vector_search', true,
     'Search persistent strategy idea dossiers through Qdrant vector retrieval with a SQL lexical fallback. This reads memory and does not approve trades.',
     '{"script":"_ai_os_runtime/scripts/search_strategy_idea_dossiers.py","reads":["strategy.v_idea_dossiers","knowledge.vector_documents","qdrant:strategy_artifacts_mxbai_embed_large"],"writes":["strategy.idea_dossier_search_runs"],"fallback":"sql_lexical","live_execution_allowed":false,"seed_data_allowed":false}'::jsonb)
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
            'strategy.idea_dossier_search_runs',
            'strategy.v_idea_dossier_search_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_search_strategy_idea_dossiers'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use dossier semantic search before creating duplicate strategy ideas or committee packets.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'trading_desk', 'runtime');
