CREATE TABLE IF NOT EXISTS strategy.trade_journal_mining_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    source_scope TEXT NOT NULL DEFAULT 'trade_journals_and_activity_ledger',
    min_trades INTEGER NOT NULL DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'started',
    generated_idea_count INTEGER NOT NULL DEFAULT 0,
    candidate_pattern_count INTEGER NOT NULL DEFAULT 0,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifact_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Trade Journal Strategy Miner',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_mining_runs_created
ON strategy.trade_journal_mining_runs (created_at DESC);

CREATE TABLE IF NOT EXISTS strategy.trade_journal_strategy_patterns (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES strategy.trade_journal_mining_runs(id) ON DELETE CASCADE,
    pattern_key TEXT NOT NULL UNIQUE,
    pattern_type TEXT NOT NULL DEFAULT 'journal_performance_cluster',
    symbol TEXT,
    setup_type TEXT,
    timeframe TEXT,
    execution_mode TEXT,
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    loss_count INTEGER NOT NULL DEFAULT 0,
    total_pnl NUMERIC,
    average_pnl NUMERIC,
    win_rate NUMERIC,
    idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    candidate_key TEXT,
    thesis TEXT,
    edge_hypothesis TEXT,
    entry_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    exit_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_strategy_patterns_run
ON strategy.trade_journal_strategy_patterns (run_id);

CREATE INDEX IF NOT EXISTS idx_trade_journal_strategy_patterns_status
ON strategy.trade_journal_strategy_patterns (status);

CREATE OR REPLACE VIEW strategy.v_trade_journal_mining_runs AS
SELECT
    run.id,
    run.run_key,
    run.source_scope,
    run.min_trades,
    run.status,
    run.generated_idea_count,
    run.candidate_pattern_count,
    run.summary,
    run.evidence,
    run.artifact_path,
    run.created_by,
    run.started_at,
    run.finished_at,
    run.created_at
FROM strategy.trade_journal_mining_runs run;

CREATE OR REPLACE VIEW strategy.v_trade_journal_strategy_patterns AS
SELECT
    pattern.id,
    run.run_key,
    pattern.pattern_key,
    pattern.pattern_type,
    pattern.symbol,
    pattern.setup_type,
    pattern.timeframe,
    pattern.execution_mode,
    pattern.trade_count,
    pattern.win_count,
    pattern.loss_count,
    pattern.total_pnl,
    pattern.average_pnl,
    pattern.win_rate,
    pattern.idea_id,
    idea.idea_key,
    idea.title AS idea_title,
    idea.status AS idea_status,
    pattern.candidate_key,
    pattern.thesis,
    pattern.edge_hypothesis,
    pattern.entry_rules,
    pattern.exit_rules,
    pattern.risk_rules,
    pattern.evidence,
    pattern.status,
    pattern.created_at
FROM strategy.trade_journal_strategy_patterns pattern
JOIN strategy.trade_journal_mining_runs run ON run.id = pattern.run_id
LEFT JOIN strategy.generated_ideas idea ON idea.id = pattern.idea_id;

CREATE OR REPLACE VIEW strategy.v_trade_journal_idea_generator_dashboard AS
SELECT
    pattern.id,
    pattern.run_key,
    pattern.pattern_key,
    pattern.symbol,
    pattern.setup_type,
    pattern.timeframe,
    pattern.execution_mode,
    pattern.trade_count,
    pattern.win_rate,
    pattern.average_pnl,
    pattern.status,
    pattern.idea_key,
    pattern.idea_title,
    pattern.idea_status,
    CASE
        WHEN pattern.trade_count < 3 THEN 'thin_sample_backtest_required'
        WHEN pattern.win_rate IS NULL THEN 'needs_trade_outcomes'
        WHEN pattern.average_pnl > 0 THEN 'positive_journal_pattern_research'
        ELSE 'negative_or_mixed_journal_pattern_research'
    END AS research_gate,
    CASE
        WHEN pattern.trade_count < 3 THEN 'Add more manual/paper/live trade rows before trusting this pattern.'
        WHEN pattern.idea_id IS NULL THEN 'Create or repair generated strategy idea for this pattern.'
        ELSE 'Translate generated idea into DSL, then run data-quality/backtest/optimizer/model-validation.'
    END AS next_required_action,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed,
    pattern.created_at
FROM strategy.v_trade_journal_strategy_patterns pattern
ORDER BY pattern.created_at DESC, pattern.trade_count DESC, pattern.average_pnl DESC NULLS LAST;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_trade_journal_strategy_mining', 'mcp_tool', 'Strategy Generator', 'write_with_approval', true,
     'Mine real trade journals and trade activity rows into low-to-high evidence strategy hypotheses. This never approves live execution.',
     '{"script":"_ai_os_runtime/scripts/run_trade_journal_strategy_mining.py","reads":["trading.trade_journals","trading.trade_activity_ledger"],"writes":["strategy.trade_journal_mining_runs","strategy.trade_journal_strategy_patterns","strategy.strategy_intakes","strategy.generated_ideas"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_trade_journal_strategy_ideas', 'mcp_tool', 'Strategy Generator', 'read_only', true,
     'Read journal-mined patterns and generated strategy ideas with sample-size gates.',
     '{"reads":["strategy.v_trade_journal_idea_generator_dashboard"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
