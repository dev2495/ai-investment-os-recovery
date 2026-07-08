CREATE TABLE IF NOT EXISTS strategy.idea_dossiers (
    id BIGSERIAL PRIMARY KEY,
    dossier_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    canonical_title TEXT,
    source_kind TEXT,
    source_ref TEXT,
    symbols TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    universe TEXT,
    timeframe TEXT,
    template TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    latest_triage_decision TEXT,
    recommended_next_action TEXT,
    discovery_count INTEGER NOT NULL DEFAULT 0,
    generated_idea_count INTEGER NOT NULL DEFAULT 0,
    optimizer_run_count INTEGER NOT NULL DEFAULT 0,
    triage_decision_count INTEGER NOT NULL DEFAULT 0,
    committee_review_count INTEGER NOT NULL DEFAULT 0,
    inbox_item_count INTEGER NOT NULL DEFAULT 0,
    priority_score NUMERIC,
    risk_score NUMERIC,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    latest_triaged_at TIMESTAMPTZ,
    summary TEXT,
    evidence_timeline JSONB NOT NULL DEFAULT '[]'::jsonb,
    linked_candidate_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
    linked_generated_idea_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
    linked_optimizer_run_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
    linked_committee_review_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[],
    note_path TEXT,
    qdrant_index_status TEXT NOT NULL DEFAULT 'pending',
    created_by TEXT NOT NULL DEFAULT 'Strategy Dossier Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_idea_dossiers_symbols
ON strategy.idea_dossiers USING GIN (symbols);

CREATE INDEX IF NOT EXISTS idx_idea_dossiers_status
ON strategy.idea_dossiers (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS strategy.idea_dossier_links (
    id BIGSERIAL PRIMARY KEY,
    dossier_id BIGINT NOT NULL REFERENCES strategy.idea_dossiers(id) ON DELETE CASCADE,
    source_table TEXT NOT NULL,
    source_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dossier_id, source_table, source_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_idea_dossier_links_source
ON strategy.idea_dossier_links (source_table, source_id);

CREATE TABLE IF NOT EXISTS strategy.idea_dossier_build_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    dossiers_seen INTEGER NOT NULL DEFAULT 0,
    dossiers_upserted INTEGER NOT NULL DEFAULT 0,
    links_upserted INTEGER NOT NULL DEFAULT 0,
    notes_written INTEGER NOT NULL DEFAULT 0,
    qdrant_index_requested BOOLEAN NOT NULL DEFAULT false,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_by TEXT NOT NULL DEFAULT 'Strategy Dossier Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_idea_dossier_build_runs_created
ON strategy.idea_dossier_build_runs (created_at DESC);

CREATE OR REPLACE VIEW strategy.v_idea_dossiers AS
SELECT
    dossier.id,
    dossier.dossier_key,
    dossier.title,
    dossier.canonical_title,
    dossier.source_kind,
    dossier.source_ref,
    dossier.symbols,
    dossier.universe,
    dossier.timeframe,
    dossier.template,
    dossier.status,
    dossier.latest_triage_decision,
    dossier.recommended_next_action,
    dossier.discovery_count,
    dossier.generated_idea_count,
    dossier.optimizer_run_count,
    dossier.triage_decision_count,
    dossier.committee_review_count,
    dossier.inbox_item_count,
    dossier.priority_score,
    dossier.risk_score,
    dossier.first_seen_at,
    dossier.last_seen_at,
    dossier.latest_triaged_at,
    dossier.summary,
    dossier.evidence_timeline,
    dossier.linked_candidate_ids,
    dossier.linked_generated_idea_ids,
    dossier.linked_optimizer_run_ids,
    dossier.linked_committee_review_ids,
    dossier.note_path,
    dossier.qdrant_index_status,
    dossier.created_by,
    dossier.created_at,
    dossier.updated_at,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed
FROM strategy.idea_dossiers dossier
ORDER BY
    dossier.updated_at DESC,
    dossier.priority_score DESC NULLS LAST,
    dossier.discovery_count DESC,
    dossier.id DESC;

CREATE OR REPLACE VIEW strategy.v_idea_dossier_links AS
SELECT
    link.id,
    dossier.dossier_key,
    dossier.title AS dossier_title,
    link.dossier_id,
    link.source_table,
    link.source_id,
    link.relation_type,
    link.evidence,
    link.created_at
FROM strategy.idea_dossier_links link
JOIN strategy.idea_dossiers dossier ON dossier.id = link.dossier_id
ORDER BY link.created_at DESC, link.id DESC;

CREATE OR REPLACE VIEW strategy.v_idea_dossier_build_runs AS
SELECT
    id,
    run_key,
    status,
    dossiers_seen,
    dossiers_upserted,
    links_upserted,
    notes_written,
    qdrant_index_requested,
    summary,
    error_message,
    started_at,
    finished_at,
    duration_ms,
    created_by,
    created_at
FROM strategy.idea_dossier_build_runs
ORDER BY started_at DESC, id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_build_strategy_idea_dossiers', 'mcp_tool', 'Strategy Dossier Agent', 'write_db_and_obsidian', true,
     'Group repeated discovered strategy ideas into persistent dossiers with evidence timelines and Obsidian writeback. This does not approve trading.',
     '{"script":"_ai_os_runtime/scripts/build_strategy_idea_dossiers.py","reads":["strategy.v_strategy_discovery_triage_queue","strategy.v_strategy_discovery_triage_decisions"],"writes":["strategy.idea_dossiers","strategy.idea_dossier_links","strategy.idea_dossier_build_runs","knowledge.obsidian_notes","filesystem:ai memory/03 Strategies/Dossiers"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_strategy_idea_dossiers', 'mcp_tool', 'Charlie Munger', 'read_only', true,
     'Read persistent strategy idea dossiers, evidence timelines, linked discoveries, triage, optimizer, and committee state.',
     '{"reads":["strategy.v_idea_dossiers","strategy.v_idea_dossier_links","strategy.v_idea_dossier_build_runs"],"live_execution_allowed":false}'::jsonb)
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
            'strategy.idea_dossiers',
            'strategy.idea_dossier_links',
            'strategy.idea_dossier_build_runs',
            'strategy.v_idea_dossiers',
            'strategy.v_idea_dossier_links',
            'strategy.v_idea_dossier_build_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_build_strategy_idea_dossiers',
            'ai_os_strategy_idea_dossiers'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use persistent strategy idea dossiers to deduplicate repeated discoveries and create durable evidence timelines for Charlie/Jarvis review.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'trading_desk', 'runtime');
