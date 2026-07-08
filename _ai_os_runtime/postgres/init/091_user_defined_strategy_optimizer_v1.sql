CREATE TABLE IF NOT EXISTS strategy.user_defined_optimizer_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    strategy_name TEXT NOT NULL,
    intake_id BIGINT REFERENCES strategy.strategy_intakes(id) ON DELETE SET NULL,
    candidate_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    backtest_run_id BIGINT REFERENCES strategy.backtest_runs(id) ON DELETE SET NULL,
    optimization_run_id BIGINT REFERENCES strategy.optimization_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'started',
    current_stage TEXT NOT NULL DEFAULT 'intake',
    requested_template TEXT,
    requested_timeframe TEXT,
    requested_symbols TEXT[] NOT NULL DEFAULT '{}',
    stage_results JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    artifact_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_defined_optimizer_runs_created
ON strategy.user_defined_optimizer_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_defined_optimizer_runs_status
ON strategy.user_defined_optimizer_runs (status);

CREATE OR REPLACE VIEW strategy.v_user_defined_optimizer_runs AS
SELECT
    run.id,
    run.run_key,
    run.strategy_name,
    run.intake_id,
    intake.intake_key,
    run.candidate_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS candidate_name,
    run.backtest_run_id,
    run.optimization_run_id,
    run.status,
    run.current_stage,
    run.requested_template,
    run.requested_timeframe,
    run.requested_symbols,
    run.stage_results,
    run.failure_reason,
    run.artifact_path,
    run.created_by,
    run.started_at,
    run.finished_at,
    run.created_at,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed
FROM strategy.user_defined_optimizer_runs run
LEFT JOIN strategy.strategy_intakes intake ON intake.id = run.intake_id
LEFT JOIN strategy.strategy_candidates candidate ON candidate.id = run.candidate_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_user_defined_strategy_optimizer', 'mcp_tool', 'Optimizer Agent', 'write_with_approval', true,
     'Create a strategy from user input and run parser, data gate, baseline backtest, and optimizer using real OHLCV. This never enables live execution.',
     '{"script":"_ai_os_runtime/scripts/run_user_defined_strategy_optimizer.py","reads":["trading.ohlcv"],"writes":["strategy.strategy_intakes","strategy.strategy_candidates","strategy.backtest_runs","strategy.optimization_runs","strategy.user_defined_optimizer_runs"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_user_defined_strategy_optimizer_runs', 'mcp_tool', 'Optimizer Agent', 'read_only', true,
     'Read user-defined strategy optimizer workflow runs and stage results.',
     '{"reads":["strategy.v_user_defined_optimizer_runs"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
