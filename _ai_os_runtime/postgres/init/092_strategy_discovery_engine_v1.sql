CREATE TABLE IF NOT EXISTS strategy.strategy_discovery_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    source_scope TEXT[] NOT NULL DEFAULT '{}',
    discovered_count INTEGER NOT NULL DEFAULT 0,
    generated_idea_count INTEGER NOT NULL DEFAULT 0,
    optimizer_routed_count INTEGER NOT NULL DEFAULT 0,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifact_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Strategy Discovery Agent',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_runs_created
ON strategy.strategy_discovery_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_runs_status
ON strategy.strategy_discovery_runs (status);

CREATE TABLE IF NOT EXISTS strategy.strategy_discovery_candidates (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES strategy.strategy_discovery_runs(id) ON DELETE CASCADE,
    discovery_key TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    title TEXT NOT NULL,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    universe TEXT,
    timeframe TEXT,
    template TEXT,
    thesis TEXT,
    catalyst TEXT,
    priority_score NUMERIC,
    risk_score NUMERIC,
    route_to_optimizer BOOLEAN NOT NULL DEFAULT false,
    generated_idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    optimizer_run_id BIGINT REFERENCES strategy.user_defined_optimizer_runs(id) ON DELETE SET NULL,
    optimizer_run_key TEXT,
    optimizer_status TEXT,
    research_gate TEXT NOT NULL DEFAULT 'discovered_research_only',
    next_required_action TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'discovered',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_candidates_run
ON strategy.strategy_discovery_candidates (run_id);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_candidates_status
ON strategy.strategy_discovery_candidates (status);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_candidates_symbols
ON strategy.strategy_discovery_candidates USING GIN (symbols);

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_runs AS
SELECT
    run.id,
    run.run_key,
    run.status,
    run.source_scope,
    run.discovered_count,
    run.generated_idea_count,
    run.optimizer_routed_count,
    run.summary,
    run.evidence,
    run.artifact_path,
    run.created_by,
    run.started_at,
    run.finished_at,
    run.created_at
FROM strategy.strategy_discovery_runs run;

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_candidates AS
SELECT
    candidate.id,
    run.run_key,
    candidate.discovery_key,
    candidate.source_kind,
    candidate.source_ref,
    candidate.title,
    candidate.symbols,
    candidate.universe,
    candidate.timeframe,
    candidate.template,
    candidate.thesis,
    candidate.catalyst,
    candidate.priority_score,
    candidate.risk_score,
    candidate.route_to_optimizer,
    candidate.generated_idea_id,
    idea.idea_key,
    idea.status AS generated_idea_status,
    candidate.optimizer_run_id,
    candidate.optimizer_run_key,
    candidate.optimizer_status,
    optimizer.candidate_id AS optimizer_candidate_id,
    optimizer.backtest_run_id,
    optimizer.optimization_run_id,
    candidate.research_gate,
    candidate.next_required_action,
    candidate.evidence,
    candidate.status,
    candidate.created_at,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed
FROM strategy.strategy_discovery_candidates candidate
JOIN strategy.strategy_discovery_runs run ON run.id = candidate.run_id
LEFT JOIN strategy.generated_ideas idea ON idea.id = candidate.generated_idea_id
LEFT JOIN strategy.user_defined_optimizer_runs optimizer ON optimizer.id = candidate.optimizer_run_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_strategy_discovery', 'mcp_tool', 'Strategy Discovery Agent', 'write_with_approval', true,
     'Scan internal research, legacy algo ideas, journal-mined patterns, signals, and component patterns into strategy ideas. Optionally routes top ideas through the safe optimizer pipeline.',
     '{"script":"_ai_os_runtime/scripts/run_strategy_discovery.py","reads":["research.ideas","trading.signals","strategy.v_trade_journal_strategy_patterns","core.source_components"],"writes":["strategy.strategy_discovery_runs","strategy.strategy_discovery_candidates","strategy.generated_ideas","strategy.user_defined_optimizer_runs"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_strategy_discovery_runs', 'mcp_tool', 'Strategy Discovery Agent', 'read_only', true,
     'Read automatic strategy discovery runs, candidates, generated ideas, and optimizer routing status.',
     '{"reads":["strategy.v_strategy_discovery_runs","strategy.v_strategy_discovery_candidates"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
