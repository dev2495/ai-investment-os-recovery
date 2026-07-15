CREATE TABLE IF NOT EXISTS risk.portfolio_risk_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    run_status TEXT NOT NULL DEFAULT 'running' CHECK (run_status IN ('running', 'completed', 'provisional', 'failed')),
    methodology TEXT NOT NULL DEFAULT 'historical_bootstrap_v1',
    lookback_days INTEGER NOT NULL DEFAULT 756 CHECK (lookback_days BETWEEN 60 AND 4000),
    simulation_count INTEGER NOT NULL DEFAULT 20000 CHECK (simulation_count BETWEEN 1000 AND 500000),
    random_seed INTEGER NOT NULL DEFAULT 20260715,
    position_as_of TIMESTAMPTZ,
    market_data_as_of TIMESTAMPTZ,
    source_position_count INTEGER NOT NULL DEFAULT 0,
    source_symbol_count INTEGER NOT NULL DEFAULT 0,
    covered_symbol_count INTEGER NOT NULL DEFAULT 0,
    uncovered_symbol_count INTEGER NOT NULL DEFAULT 0,
    gross_exposure NUMERIC NOT NULL DEFAULT 0,
    covered_exposure NUMERIC NOT NULL DEFAULT 0,
    uncovered_exposure NUMERIC NOT NULL DEFAULT 0,
    coverage_pct NUMERIC,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_lineage JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    error_message TEXT,
    created_by TEXT NOT NULL DEFAULT 'Portfolio Risk Analyst',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT chk_portfolio_risk_no_execution CHECK (live_execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_risk_runs_status ON risk.portfolio_risk_runs (run_status, created_at DESC);

CREATE TABLE IF NOT EXISTS risk.portfolio_risk_metrics (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES risk.portfolio_risk_runs(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('portfolio', 'client', 'book')),
    scope_ref TEXT NOT NULL,
    scope_name TEXT NOT NULL,
    calculation_status TEXT NOT NULL CHECK (calculation_status IN ('complete', 'provisional', 'insufficient')),
    gross_exposure NUMERIC NOT NULL DEFAULT 0,
    net_exposure NUMERIC NOT NULL DEFAULT 0,
    covered_exposure NUMERIC NOT NULL DEFAULT 0,
    uncovered_exposure NUMERIC NOT NULL DEFAULT 0,
    coverage_pct NUMERIC,
    observation_count INTEGER NOT NULL DEFAULT 0,
    annualized_volatility_pct NUMERIC,
    historical_var_95_pct NUMERIC,
    historical_var_95_value NUMERIC,
    historical_es_95_pct NUMERIC,
    historical_es_95_value NUMERIC,
    historical_var_99_pct NUMERIC,
    historical_var_99_value NUMERIC,
    historical_es_99_pct NUMERIC,
    historical_es_99_value NUMERIC,
    coverage_adjusted_var_99_pct NUMERIC,
    coverage_adjusted_var_99_value NUMERIC,
    bootstrap_var_99_1d_pct NUMERIC,
    bootstrap_var_99_1d_value NUMERIC,
    bootstrap_es_99_1d_pct NUMERIC,
    bootstrap_es_99_1d_value NUMERIC,
    bootstrap_var_99_10d_pct NUMERIC,
    bootstrap_var_99_10d_value NUMERIC,
    bootstrap_es_99_10d_pct NUMERIC,
    bootstrap_es_99_10d_value NUMERIC,
    probability_loss_5pct_10d NUMERIC,
    probability_loss_10pct_10d NUMERIC,
    maximum_drawdown_pct NUMERIC,
    market_beta NUMERIC,
    market_correlation NUMERIC,
    market_r_squared NUMERIC,
    residual_volatility_pct NUMERIC,
    concentration_hhi NUMERIC,
    top_5_exposure_pct NUMERIC,
    largest_position_pct NUMERIC,
    data_freshness_days NUMERIC,
    uncovered_shock_assumption_pct NUMERIC,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, scope_type, scope_ref)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_risk_metrics_scope ON risk.portfolio_risk_metrics (scope_type, scope_ref, run_id DESC);

CREATE TABLE IF NOT EXISTS risk.stress_scenario_definitions (
    scenario_key TEXT PRIMARY KEY,
    scenario_name TEXT NOT NULL,
    scenario_type TEXT NOT NULL,
    description TEXT NOT NULL,
    parameters JSONB NOT NULL,
    owner_agent TEXT NOT NULL DEFAULT 'Stress Testing Agent',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'retired')),
    approval_required BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO risk.stress_scenario_definitions (
    scenario_key, scenario_name, scenario_type, description, parameters, owner_agent, status, approval_required
)
VALUES
    ('market_down_5', 'Broad Market Down 5%', 'systematic', 'Apply current estimated market beta to covered exposure and beta 1.0 to uncovered exposure.', '{"market_return_pct":-5,"uncovered_beta":1.0}'::jsonb, 'Stress Testing Agent', 'active', false),
    ('market_down_10', 'Broad Market Down 10%', 'systematic', 'Apply current estimated market beta to covered exposure and beta 1.0 to uncovered exposure.', '{"market_return_pct":-10,"uncovered_beta":1.0}'::jsonb, 'Stress Testing Agent', 'active', false),
    ('top_three_down_20', 'Top Three Positions Down 20%', 'concentration', 'Shock the three largest gross positions by 20% with no diversification credit.', '{"position_count":3,"shock_pct":-20}'::jsonb, 'Portfolio Risk Analyst', 'active', false),
    ('liquidity_gap', 'Liquidity And Gap Shock', 'liquidity', 'Shock unavailable or slow-to-liquidate positions by 15% and liquid covered positions by 5%.', '{"slow_days":5,"slow_shock_pct":-15,"liquid_shock_pct":-5}'::jsonb, 'Liquidity Risk Agent', 'active', false),
    ('historical_worst_day', 'Historical Worst Covered Day', 'historical', 'Replay the worst observed covered-portfolio day and apply the configured uncovered-data shock to missing exposure.', '{"uncovered_penalty":"run_derived"}'::jsonb, 'Stress Testing Agent', 'active', false)
ON CONFLICT (scenario_key) DO UPDATE SET
    scenario_name = EXCLUDED.scenario_name,
    scenario_type = EXCLUDED.scenario_type,
    description = EXCLUDED.description,
    parameters = EXCLUDED.parameters,
    owner_agent = EXCLUDED.owner_agent,
    status = EXCLUDED.status,
    approval_required = EXCLUDED.approval_required,
    updated_at = now();

CREATE TABLE IF NOT EXISTS risk.portfolio_stress_results (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES risk.portfolio_risk_runs(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    scenario_key TEXT NOT NULL REFERENCES risk.stress_scenario_definitions(scenario_key),
    stressed_pnl_value NUMERIC NOT NULL,
    stressed_return_pct NUMERIC NOT NULL,
    covered_loss_value NUMERIC NOT NULL DEFAULT 0,
    uncovered_loss_value NUMERIC NOT NULL DEFAULT 0,
    severity TEXT NOT NULL,
    calculation_status TEXT NOT NULL,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, scope_type, scope_ref, scenario_key)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_stress_scope ON risk.portfolio_stress_results (scope_type, scope_ref, run_id DESC);

CREATE TABLE IF NOT EXISTS risk.position_liquidity_assessments (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES risk.portfolio_risk_runs(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    symbol TEXT NOT NULL,
    gross_exposure NUMERIC NOT NULL,
    latest_close NUMERIC,
    median_daily_volume NUMERIC,
    median_daily_traded_value NUMERIC,
    participation_rate_pct NUMERIC NOT NULL DEFAULT 10,
    estimated_days_to_liquidate NUMERIC,
    liquidity_bucket TEXT NOT NULL CHECK (liquidity_bucket IN ('same_day', 'one_to_three_days', 'four_to_ten_days', 'over_ten_days', 'unavailable')),
    market_data_observations INTEGER NOT NULL DEFAULT 0,
    market_data_as_of TIMESTAMPTZ,
    calculation_status TEXT NOT NULL,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, scope_type, scope_ref, symbol)
);

CREATE INDEX IF NOT EXISTS idx_liquidity_assessments_scope ON risk.position_liquidity_assessments (scope_type, scope_ref, run_id DESC);

CREATE TABLE IF NOT EXISTS risk.factor_risk_attribution (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES risk.portfolio_risk_runs(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL,
    scope_ref TEXT NOT NULL,
    factor_key TEXT NOT NULL,
    factor_name TEXT NOT NULL,
    exposure_value NUMERIC,
    contribution_pct NUMERIC,
    calculation_status TEXT NOT NULL,
    methodology TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, scope_type, scope_ref, factor_key)
);

CREATE INDEX IF NOT EXISTS idx_factor_risk_scope ON risk.factor_risk_attribution (scope_type, scope_ref, run_id DESC);

CREATE OR REPLACE VIEW risk.v_latest_portfolio_risk_run AS
SELECT *
FROM risk.portfolio_risk_runs
WHERE run_status IN ('completed', 'provisional')
ORDER BY finished_at DESC NULLS LAST, id DESC
LIMIT 1;

CREATE OR REPLACE VIEW risk.v_latest_portfolio_risk_metrics AS
SELECT metric.*
FROM risk.portfolio_risk_metrics metric
JOIN risk.v_latest_portfolio_risk_run run ON run.id = metric.run_id
ORDER BY CASE metric.scope_type WHEN 'portfolio' THEN 1 WHEN 'book' THEN 2 ELSE 3 END, metric.scope_name;

CREATE OR REPLACE VIEW risk.v_latest_portfolio_stress_results AS
SELECT result.*, definition.scenario_name, definition.scenario_type, definition.description
FROM risk.portfolio_stress_results result
JOIN risk.v_latest_portfolio_risk_run run ON run.id = result.run_id
JOIN risk.stress_scenario_definitions definition ON definition.scenario_key = result.scenario_key
ORDER BY result.scope_type, result.scope_ref, result.stressed_return_pct;

CREATE OR REPLACE VIEW risk.v_latest_position_liquidity AS
SELECT assessment.*
FROM risk.position_liquidity_assessments assessment
JOIN risk.v_latest_portfolio_risk_run run ON run.id = assessment.run_id
ORDER BY CASE assessment.liquidity_bucket
    WHEN 'unavailable' THEN 1 WHEN 'over_ten_days' THEN 2 WHEN 'four_to_ten_days' THEN 3
    WHEN 'one_to_three_days' THEN 4 ELSE 5 END,
    assessment.gross_exposure DESC;

CREATE OR REPLACE VIEW risk.v_latest_factor_risk_attribution AS
SELECT attribution.*
FROM risk.factor_risk_attribution attribution
JOIN risk.v_latest_portfolio_risk_run run ON run.id = attribution.run_id
ORDER BY attribution.scope_type, attribution.scope_ref, attribution.factor_key;

CREATE OR REPLACE VIEW risk.v_institutional_risk_summary AS
SELECT 'risk_run_status'::TEXT AS metric, coalesce((SELECT run_status FROM risk.v_latest_portfolio_risk_run), 'not_run')::TEXT AS value,
       'Latest institutional portfolio risk calculation state.'::TEXT AS interpretation
UNION ALL
SELECT 'historical_coverage_pct', coalesce(round(coverage_pct, 2)::TEXT, '0'), 'Gross exposure with usable daily return history.'
FROM risk.v_latest_portfolio_risk_run
UNION ALL
SELECT 'portfolio_var_99_1d_pct', coalesce(round(bootstrap_var_99_1d_pct, 2)::TEXT, '0'), 'Coverage-adjusted one-day 99% bootstrap VaR as percent of gross exposure.'
FROM risk.v_latest_portfolio_risk_metrics WHERE scope_type = 'portfolio'
UNION ALL
SELECT 'portfolio_es_99_1d_pct', coalesce(round(bootstrap_es_99_1d_pct, 2)::TEXT, '0'), 'Coverage-adjusted one-day 99% expected shortfall.'
FROM risk.v_latest_portfolio_risk_metrics WHERE scope_type = 'portfolio'
UNION ALL
SELECT 'portfolio_var_99_10d_pct', coalesce(round(bootstrap_var_99_10d_pct, 2)::TEXT, '0'), 'Coverage-adjusted ten-day 99% bootstrap VaR.'
FROM risk.v_latest_portfolio_risk_metrics WHERE scope_type = 'portfolio'
UNION ALL
SELECT 'worst_stress_loss_pct', coalesce(abs(round(min(stressed_return_pct), 2))::TEXT, '0'), 'Largest modeled portfolio stress loss.'
FROM risk.v_latest_portfolio_stress_results WHERE scope_type = 'portfolio'
UNION ALL
SELECT 'liquidity_unavailable_exposure', coalesce(round(sum(gross_exposure) FILTER (WHERE liquidity_bucket = 'unavailable'), 2)::TEXT, '0'), 'Exposure without usable traded-volume history.'
FROM risk.v_latest_position_liquidity WHERE scope_type = 'portfolio'
UNION ALL
SELECT 'slow_liquidity_exposure', coalesce(round(sum(gross_exposure) FILTER (WHERE liquidity_bucket IN ('four_to_ten_days','over_ten_days')), 2)::TEXT, '0'), 'Exposure estimated to require more than three days at the configured participation rate.'
FROM risk.v_latest_position_liquidity WHERE scope_type = 'portfolio';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_institutional_portfolio_risk', 'mcp_tool', 'Portfolio Risk Analyst', 'write_with_approval', true, 'Run evidence-backed historical VaR, expected shortfall, bootstrap Monte Carlo, stress, factor, concentration, and liquidity analytics. No execution authority.', '{"script":"_ai_os_runtime/scripts/run_portfolio_risk_engine.py","writes":["risk.portfolio_risk_runs","risk.portfolio_risk_metrics","risk.portfolio_stress_results","risk.position_liquidity_assessments","risk.factor_risk_attribution"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_institutional_portfolio_risk', 'mcp_tool', 'Chief Risk Officer', 'read_only', true, 'Read the latest portfolio/client/book risk metrics, stress losses, liquidity assessments, factor attribution, and explicit data coverage.', '{"reads":["risk.v_latest_portfolio_risk_run","risk.v_latest_portfolio_risk_metrics","risk.v_latest_portfolio_stress_results","risk.v_latest_position_liquidity","risk.v_latest_factor_risk_attribution"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES (
    'institutional_portfolio_risk_cycle', 'Institutional Portfolio Risk Cycle', 'risk_analytics',
    'Portfolio Risk Analyst', 'manual_or_scheduled', 'active', 'write_with_approval',
    ARRAY['books.v_book_positions','trading.ohlcv','trading.symbols','market.v_market_bias_control_readiness']::TEXT[],
    ARRAY['risk.portfolio_risk_runs','risk.portfolio_risk_metrics','risk.portfolio_stress_results','risk.position_liquidity_assessments','risk.factor_risk_attribution','agent.inbox_items']::TEXT[],
    false, 'post-close daily after positions and market data refresh',
    'Computes risk from real positions and market history. Missing history remains explicit, results are provisional while bias controls are incomplete, and no result grants capital or execution authority.',
    '{"seed_data_allowed":false,"live_execution_allowed":false,"benchmark":"NIFTY 50","human_risk_decision_required":true}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();
