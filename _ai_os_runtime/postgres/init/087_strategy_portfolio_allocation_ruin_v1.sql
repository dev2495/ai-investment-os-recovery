CREATE TABLE IF NOT EXISTS strategy.strategy_portfolio_allocation_runs (
    id BIGSERIAL PRIMARY KEY,
    allocation_key TEXT NOT NULL UNIQUE,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    optimizer_run_id BIGINT REFERENCES strategy.strategy_portfolio_optimizer_runs(id) ON DELETE SET NULL,
    capital_base NUMERIC NOT NULL DEFAULT 1000000,
    timeframe TEXT NOT NULL DEFAULT '5m',
    status TEXT NOT NULL DEFAULT 'draft',
    allocation_method TEXT NOT NULL DEFAULT 'optimizer_weight_with_risk_budget',
    expected_return NUMERIC,
    expected_volatility NUMERIC,
    expected_max_drawdown NUMERIC,
    allocation_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    artifact_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Strategy Portfolio Manager',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_allocation_runs_created
    ON strategy.strategy_portfolio_allocation_runs (created_at DESC);

CREATE TABLE IF NOT EXISTS strategy.strategy_portfolio_allocations (
    id BIGSERIAL PRIMARY KEY,
    allocation_run_id BIGINT NOT NULL REFERENCES strategy.strategy_portfolio_allocation_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    target_weight NUMERIC NOT NULL DEFAULT 0,
    target_notional NUMERIC NOT NULL DEFAULT 0,
    expected_return NUMERIC,
    expected_volatility NUMERIC,
    risk_contribution NUMERIC,
    allocation_status TEXT NOT NULL DEFAULT 'paper_only',
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (allocation_run_id, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_allocations_run
    ON strategy.strategy_portfolio_allocations (allocation_run_id, strategy_id);

CREATE TABLE IF NOT EXISTS strategy.probability_of_ruin_metrics (
    id BIGSERIAL PRIMARY KEY,
    allocation_run_id BIGINT NOT NULL REFERENCES strategy.strategy_portfolio_allocation_runs(id) ON DELETE CASCADE,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    metric_scope TEXT NOT NULL DEFAULT 'portfolio',
    horizon_bars INTEGER NOT NULL DEFAULT 252,
    simulation_count INTEGER NOT NULL DEFAULT 1000,
    starting_capital NUMERIC NOT NULL DEFAULT 1000000,
    ruin_threshold_pct NUMERIC NOT NULL DEFAULT 0.2,
    ruin_probability NUMERIC,
    expected_terminal_value NUMERIC,
    terminal_p05 NUMERIC,
    terminal_p50 NUMERIC,
    terminal_p95 NUMERIC,
    max_drawdown_p95 NUMERIC,
    method TEXT NOT NULL DEFAULT 'deterministic_bootstrap',
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT 'Risk Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_probability_of_ruin_metrics_run
    ON strategy.probability_of_ruin_metrics (allocation_run_id, metric_scope, created_at DESC);

CREATE OR REPLACE VIEW strategy.v_strategy_portfolio_allocation_runs AS
SELECT
    run.id,
    run.allocation_key,
    run.analytics_run_id,
    analytics.run_key AS analytics_run_key,
    run.optimizer_run_id,
    run.capital_base,
    run.timeframe,
    run.status,
    run.allocation_method,
    run.expected_return,
    run.expected_volatility,
    run.expected_max_drawdown,
    run.allocation_payload,
    run.constraints,
    run.diagnostics,
    run.quality_flags,
    run.artifact_path,
    run.created_by,
    run.created_at,
    coalesce(allocations.allocation_rows, 0) AS allocation_rows,
    coalesce(ruin.ruin_metric_rows, 0) AS ruin_metric_rows
FROM strategy.strategy_portfolio_allocation_runs run
JOIN strategy.quant_analytics_runs analytics ON analytics.id = run.analytics_run_id
LEFT JOIN (
    SELECT allocation_run_id, count(*) AS allocation_rows
    FROM strategy.strategy_portfolio_allocations
    GROUP BY allocation_run_id
) allocations ON allocations.allocation_run_id = run.id
LEFT JOIN (
    SELECT allocation_run_id, count(*) AS ruin_metric_rows
    FROM strategy.probability_of_ruin_metrics
    GROUP BY allocation_run_id
) ruin ON ruin.allocation_run_id = run.id;

CREATE OR REPLACE VIEW strategy.v_strategy_portfolio_allocations AS
SELECT
    allocation.id,
    allocation.allocation_run_id,
    run.allocation_key,
    run.analytics_run_id,
    run.analytics_run_key,
    allocation.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    allocation.target_weight,
    allocation.target_notional,
    allocation.expected_return,
    allocation.expected_volatility,
    allocation.risk_contribution,
    allocation.allocation_status,
    allocation.diagnostics,
    allocation.created_at
FROM strategy.strategy_portfolio_allocations allocation
JOIN strategy.v_strategy_portfolio_allocation_runs run ON run.id = allocation.allocation_run_id
JOIN strategy.strategy_candidates candidate ON candidate.id = allocation.strategy_id;

CREATE OR REPLACE VIEW strategy.v_probability_of_ruin_metrics AS
SELECT
    ruin.id,
    ruin.allocation_run_id,
    allocation.allocation_key,
    ruin.analytics_run_id,
    analytics.run_key AS analytics_run_key,
    ruin.strategy_id,
    CASE
        WHEN candidate.id IS NULL THEN 'portfolio'
        ELSE coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT)
    END AS candidate_key,
    coalesce(candidate.name, 'Strategy Portfolio') AS strategy_name,
    ruin.metric_scope,
    ruin.horizon_bars,
    ruin.simulation_count,
    ruin.starting_capital,
    ruin.ruin_threshold_pct,
    ruin.ruin_probability,
    ruin.expected_terminal_value,
    ruin.terminal_p05,
    ruin.terminal_p50,
    ruin.terminal_p95,
    ruin.max_drawdown_p95,
    ruin.method,
    ruin.diagnostics,
    ruin.quality_flags,
    ruin.created_by,
    ruin.created_at
FROM strategy.probability_of_ruin_metrics ruin
JOIN strategy.strategy_portfolio_allocation_runs allocation ON allocation.id = ruin.allocation_run_id
JOIN strategy.quant_analytics_runs analytics ON analytics.id = ruin.analytics_run_id
LEFT JOIN strategy.strategy_candidates candidate ON candidate.id = ruin.strategy_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_strategy_portfolio_allocation', 'mcp_tool', 'Strategy Portfolio Manager', 'write_with_approval', true, 'Create paper-only portfolio strategy allocation and probability-of-ruin metrics from the latest quant analytics return series.', '{"script":"_ai_os_runtime/scripts/run_strategy_portfolio_allocation.py","writes":["strategy.strategy_portfolio_allocation_runs","strategy.strategy_portfolio_allocations","strategy.probability_of_ruin_metrics"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_strategy_portfolio_allocation', 'mcp_tool', 'Strategy Portfolio Manager', 'read_only', true, 'Read strategy portfolio allocation and probability-of-ruin metrics.', '{"reads":["strategy.v_strategy_portfolio_allocation_runs","strategy.v_strategy_portfolio_allocations","strategy.v_probability_of_ruin_metrics"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
