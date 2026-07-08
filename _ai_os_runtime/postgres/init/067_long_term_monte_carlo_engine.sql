CREATE TABLE IF NOT EXISTS portfolio.long_term_monte_carlo_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    valuation_model_id BIGINT REFERENCES portfolio.holding_valuation_models(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    company_name TEXT,
    run_status TEXT NOT NULL DEFAULT 'needs_review',
    horizon_years INTEGER NOT NULL,
    simulation_count INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    start_price NUMERIC,
    starting_multiple NUMERIC,
    starting_metric TEXT NOT NULL DEFAULT 'earnings_proxy',
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    percentile_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    probability_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    note_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Quant Risk Analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_long_term_monte_carlo_runs_thesis ON portfolio.long_term_monte_carlo_runs (holding_thesis_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_long_term_monte_carlo_runs_symbol ON portfolio.long_term_monte_carlo_runs (symbol, exchange, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_long_term_monte_carlo_runs_status ON portfolio.long_term_monte_carlo_runs (run_status, created_at DESC);

CREATE OR REPLACE VIEW portfolio.v_long_term_monte_carlo_runs AS
SELECT
    run.id,
    run.run_key,
    run.holding_thesis_id,
    run.valuation_model_id,
    thesis.symbol,
    thesis.exchange,
    thesis.company_name,
    run.run_status,
    run.horizon_years,
    run.simulation_count,
    run.seed,
    run.start_price,
    run.starting_multiple,
    run.starting_metric,
    run.assumptions,
    run.input_snapshot,
    run.outputs,
    run.percentile_summary,
    run.probability_summary,
    run.warnings,
    run.evidence,
    run.note_path,
    run.created_by,
    run.created_at,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients
FROM portfolio.long_term_monte_carlo_runs run
JOIN portfolio.holding_theses thesis ON thesis.id = run.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = thesis.id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_run_long_term_monte_carlo',
        'mcp_tool',
        'Quant Risk Analyst',
        'write_with_approval',
        true,
        'Run a deterministic long-term Monte Carlo simulation for a holding thesis using explicit valuation assumptions. Does not approve buy/sell decisions.',
        '{"script":"_ai_os_runtime/scripts/run_long_term_monte_carlo.py","writes":["portfolio.long_term_monte_carlo_runs","portfolio.holding_valuation_models","portfolio.holding_theses","portfolio.holding_thesis_research_updates","knowledge.obsidian_notes"],"reads":["portfolio.v_long_term_thesis_control","portfolio.v_long_term_valuation_models","portfolio.v_long_term_source_document_extractions","market.v_latest_price_quotes","books.v_book_positions"],"seed_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    )
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
            'portfolio.long_term_monte_carlo_runs',
            'portfolio.v_long_term_monte_carlo_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_run_long_term_monte_carlo']::TEXT[]) AS tool
    ),
    next_action = 'Long-term Monte Carlo engine is registered; run source-backed simulations and route needs-review outputs to committee before any capital action.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');

