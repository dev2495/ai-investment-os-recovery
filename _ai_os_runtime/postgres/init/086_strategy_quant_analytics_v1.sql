CREATE TABLE IF NOT EXISTS strategy.quant_analytics_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    run_name TEXT NOT NULL DEFAULT 'Strategy Quant Analytics',
    strategy_ids BIGINT[] NOT NULL DEFAULT '{}',
    timeframe TEXT NOT NULL DEFAULT '5m',
    status TEXT NOT NULL DEFAULT 'queued',
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_flags TEXT[] NOT NULL DEFAULT '{}',
    artifact_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Quant Analytics Agent',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_analytics_runs_finished
    ON strategy.quant_analytics_runs (finished_at DESC NULLS LAST, started_at DESC);

CREATE TABLE IF NOT EXISTS strategy.strategy_return_series (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    timeframe TEXT NOT NULL,
    return_value NUMERIC NOT NULL,
    benchmark_return NUMERIC,
    regime_label TEXT,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (analytics_run_id, strategy_id, ts, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_strategy_return_series_strategy
    ON strategy.strategy_return_series (strategy_id, ts);

CREATE TABLE IF NOT EXISTS strategy.regime_performance_splits (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    regime_type TEXT NOT NULL,
    regime_label TEXT NOT NULL,
    bars BIGINT NOT NULL DEFAULT 0,
    total_return NUMERIC,
    average_return NUMERIC,
    volatility NUMERIC,
    win_rate NUMERIC,
    max_drawdown NUMERIC,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_regime_performance_run
    ON strategy.regime_performance_splits (analytics_run_id, strategy_id);

CREATE TABLE IF NOT EXISTS strategy.factor_attribution (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    factor_name TEXT NOT NULL,
    exposure NUMERIC,
    contribution NUMERIC,
    method TEXT NOT NULL DEFAULT 'deterministic_proxy',
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_factor_attribution_run
    ON strategy.factor_attribution (analytics_run_id, strategy_id);

CREATE TABLE IF NOT EXISTS strategy.capacity_liquidity_checks (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bars BIGINT NOT NULL DEFAULT 0,
    average_volume NUMERIC,
    average_traded_value NUMERIC,
    participation_rate NUMERIC NOT NULL DEFAULT 0.05,
    capacity_notional NUMERIC,
    liquidity_status TEXT NOT NULL DEFAULT 'unknown',
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_capacity_liquidity_run
    ON strategy.capacity_liquidity_checks (analytics_run_id, strategy_id);

CREATE TABLE IF NOT EXISTS strategy.strategy_correlation_matrix (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    strategy_id_a BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    strategy_id_b BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    correlation NUMERIC,
    overlap_bars BIGINT NOT NULL DEFAULT 0,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (analytics_run_id, strategy_id_a, strategy_id_b)
);

CREATE INDEX IF NOT EXISTS idx_strategy_correlation_run
    ON strategy.strategy_correlation_matrix (analytics_run_id, strategy_id_a, strategy_id_b);

CREATE TABLE IF NOT EXISTS strategy.strategy_portfolio_optimizer_runs (
    id BIGSERIAL PRIMARY KEY,
    analytics_run_id BIGINT NOT NULL REFERENCES strategy.quant_analytics_runs(id) ON DELETE CASCADE,
    optimizer_method TEXT NOT NULL DEFAULT 'inverse_volatility_sharpe_proxy',
    candidate_count INTEGER NOT NULL DEFAULT 0,
    weights JSONB NOT NULL DEFAULT '{}'::jsonb,
    expected_return NUMERIC,
    expected_volatility NUMERIC,
    sharpe_proxy NUMERIC,
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL DEFAULT 'Strategy Portfolio Optimizer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_portfolio_optimizer_run
    ON strategy.strategy_portfolio_optimizer_runs (analytics_run_id, created_at DESC);

CREATE OR REPLACE VIEW strategy.v_quant_analytics_runs AS
SELECT
    run.id,
    run.run_key,
    run.run_name,
    run.strategy_ids,
    run.timeframe,
    run.status,
    run.metrics,
    run.diagnostics,
    run.quality_flags,
    run.artifact_path,
    run.created_by,
    run.started_at,
    run.finished_at,
    run.created_at,
    coalesce(regime.regime_rows, 0) AS regime_rows,
    coalesce(factor.factor_rows, 0) AS factor_rows,
    coalesce(capacity.capacity_rows, 0) AS capacity_rows,
    coalesce(correlation.correlation_rows, 0) AS correlation_rows,
    coalesce(optimizer.optimizer_rows, 0) AS optimizer_rows
FROM strategy.quant_analytics_runs run
LEFT JOIN (
    SELECT analytics_run_id, count(*) AS regime_rows
    FROM strategy.regime_performance_splits
    GROUP BY analytics_run_id
) regime ON regime.analytics_run_id = run.id
LEFT JOIN (
    SELECT analytics_run_id, count(*) AS factor_rows
    FROM strategy.factor_attribution
    GROUP BY analytics_run_id
) factor ON factor.analytics_run_id = run.id
LEFT JOIN (
    SELECT analytics_run_id, count(*) AS capacity_rows
    FROM strategy.capacity_liquidity_checks
    GROUP BY analytics_run_id
) capacity ON capacity.analytics_run_id = run.id
LEFT JOIN (
    SELECT analytics_run_id, count(*) AS correlation_rows
    FROM strategy.strategy_correlation_matrix
    GROUP BY analytics_run_id
) correlation ON correlation.analytics_run_id = run.id
LEFT JOIN (
    SELECT analytics_run_id, count(*) AS optimizer_rows
    FROM strategy.strategy_portfolio_optimizer_runs
    GROUP BY analytics_run_id
) optimizer ON optimizer.analytics_run_id = run.id;

CREATE OR REPLACE VIEW strategy.v_regime_performance_splits AS
SELECT
    split.id,
    split.analytics_run_id,
    run.run_key,
    split.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    split.regime_type,
    split.regime_label,
    split.bars,
    split.total_return,
    split.average_return,
    split.volatility,
    split.win_rate,
    split.max_drawdown,
    split.diagnostics,
    split.created_at
FROM strategy.regime_performance_splits split
JOIN strategy.quant_analytics_runs run ON run.id = split.analytics_run_id
JOIN strategy.strategy_candidates candidate ON candidate.id = split.strategy_id;

CREATE OR REPLACE VIEW strategy.v_factor_attribution AS
SELECT
    factor.id,
    factor.analytics_run_id,
    run.run_key,
    factor.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    factor.factor_name,
    factor.exposure,
    factor.contribution,
    factor.method,
    factor.diagnostics,
    factor.created_at
FROM strategy.factor_attribution factor
JOIN strategy.quant_analytics_runs run ON run.id = factor.analytics_run_id
JOIN strategy.strategy_candidates candidate ON candidate.id = factor.strategy_id;

CREATE OR REPLACE VIEW strategy.v_capacity_liquidity_checks AS
SELECT
    check_row.id,
    check_row.analytics_run_id,
    run.run_key,
    check_row.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    check_row.symbol,
    check_row.timeframe,
    check_row.bars,
    check_row.average_volume,
    check_row.average_traded_value,
    check_row.participation_rate,
    check_row.capacity_notional,
    check_row.liquidity_status,
    check_row.diagnostics,
    check_row.created_at
FROM strategy.capacity_liquidity_checks check_row
JOIN strategy.quant_analytics_runs run ON run.id = check_row.analytics_run_id
JOIN strategy.strategy_candidates candidate ON candidate.id = check_row.strategy_id;

CREATE OR REPLACE VIEW strategy.v_strategy_correlation_matrix AS
SELECT
    matrix.id,
    matrix.analytics_run_id,
    run.run_key,
    matrix.strategy_id_a,
    coalesce(candidate_a.candidate_key, 'candidate_' || candidate_a.id::TEXT) AS candidate_key_a,
    candidate_a.name AS strategy_name_a,
    matrix.strategy_id_b,
    coalesce(candidate_b.candidate_key, 'candidate_' || candidate_b.id::TEXT) AS candidate_key_b,
    candidate_b.name AS strategy_name_b,
    matrix.correlation,
    matrix.overlap_bars,
    matrix.diagnostics,
    matrix.created_at
FROM strategy.strategy_correlation_matrix matrix
JOIN strategy.quant_analytics_runs run ON run.id = matrix.analytics_run_id
JOIN strategy.strategy_candidates candidate_a ON candidate_a.id = matrix.strategy_id_a
JOIN strategy.strategy_candidates candidate_b ON candidate_b.id = matrix.strategy_id_b;

CREATE OR REPLACE VIEW strategy.v_strategy_portfolio_optimizer_runs AS
SELECT
    optimizer.id,
    optimizer.analytics_run_id,
    run.run_key,
    optimizer.optimizer_method,
    optimizer.candidate_count,
    optimizer.weights,
    optimizer.expected_return,
    optimizer.expected_volatility,
    optimizer.sharpe_proxy,
    optimizer.constraints,
    optimizer.diagnostics,
    optimizer.status,
    optimizer.created_by,
    optimizer.created_at
FROM strategy.strategy_portfolio_optimizer_runs optimizer
JOIN strategy.quant_analytics_runs run ON run.id = optimizer.analytics_run_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_strategy_quant_analytics', 'mcp_tool', 'Quant Analytics Agent', 'write_with_approval', true, 'Run regime, factor, capacity, correlation, and portfolio optimizer analytics from real OHLCV/backtest data.', '{"script":"_ai_os_runtime/scripts/run_strategy_quant_analytics.py","writes":["strategy.quant_analytics_runs","strategy.regime_performance_splits","strategy.factor_attribution","strategy.capacity_liquidity_checks","strategy.strategy_correlation_matrix","strategy.strategy_portfolio_optimizer_runs"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_strategy_quant_analytics', 'mcp_tool', 'Quant Analytics Agent', 'read_only', true, 'Read latest strategy quant analytics runs and institutional diagnostics.', '{"reads":["strategy.v_quant_analytics_runs","strategy.v_regime_performance_splits","strategy.v_factor_attribution","strategy.v_capacity_liquidity_checks","strategy.v_strategy_correlation_matrix","strategy.v_strategy_portfolio_optimizer_runs"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

