CREATE TABLE IF NOT EXISTS strategy.strategy_rule_specs (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    spec_source TEXT NOT NULL DEFAULT 'candidate',
    parser_version TEXT NOT NULL DEFAULT 'strategy_dsl_parser_v1',
    dsl_text TEXT NOT NULL DEFAULT '',
    parsed_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    normalized_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    parse_errors TEXT[] NOT NULL DEFAULT '{}',
    symbols TEXT[] NOT NULL DEFAULT '{}',
    timeframe TEXT,
    template TEXT,
    created_by TEXT NOT NULL DEFAULT 'Strategy Intake Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, parser_version)
);

CREATE INDEX IF NOT EXISTS idx_strategy_rule_specs_status
    ON strategy.strategy_rule_specs (parse_status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_rule_specs_symbols
    ON strategy.strategy_rule_specs USING GIN (symbols);

CREATE TABLE IF NOT EXISTS strategy.backtest_data_quality_gates (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL UNIQUE,
    timeframe TEXT NOT NULL,
    requested_symbols TEXT[] NOT NULL DEFAULT '{}',
    matched_symbols TEXT[] NOT NULL DEFAULT '{}',
    missing_symbols TEXT[] NOT NULL DEFAULT '{}',
    min_rows_per_symbol INTEGER NOT NULL DEFAULT 50,
    min_total_rows INTEGER NOT NULL DEFAULT 500,
    total_rows BIGINT NOT NULL DEFAULT 0,
    min_symbol_rows BIGINT NOT NULL DEFAULT 0,
    max_symbol_rows BIGINT NOT NULL DEFAULT 0,
    first_ts TIMESTAMPTZ,
    last_ts TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    severity TEXT NOT NULL DEFAULT 'info',
    reasons TEXT[] NOT NULL DEFAULT '{}',
    gate_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Backtest Engineer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_backtest_data_quality_gates_candidate
    ON strategy.backtest_data_quality_gates (candidate_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_data_quality_gates_status
    ON strategy.backtest_data_quality_gates (status, severity, created_at DESC);

CREATE OR REPLACE VIEW strategy.v_strategy_rule_specs AS
SELECT
    spec.id,
    spec.candidate_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    spec.spec_source,
    spec.parser_version,
    spec.parse_status,
    spec.parse_errors,
    spec.symbols,
    spec.timeframe,
    spec.template,
    spec.normalized_rules,
    spec.parsed_spec,
    spec.created_by,
    spec.created_at,
    spec.updated_at
FROM strategy.strategy_rule_specs spec
JOIN strategy.strategy_candidates candidate ON candidate.id = spec.candidate_id;

CREATE OR REPLACE VIEW strategy.v_backtest_data_quality_gates AS
SELECT
    gate.id,
    gate.gate_key,
    gate.candidate_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    gate.timeframe,
    gate.requested_symbols,
    gate.matched_symbols,
    gate.missing_symbols,
    gate.min_rows_per_symbol,
    gate.min_total_rows,
    gate.total_rows,
    gate.min_symbol_rows,
    gate.max_symbol_rows,
    gate.first_ts,
    gate.last_ts,
    gate.status,
    gate.severity,
    gate.reasons,
    gate.gate_payload,
    gate.created_by,
    gate.created_at
FROM strategy.backtest_data_quality_gates gate
JOIN strategy.strategy_candidates candidate ON candidate.id = gate.candidate_id;

CREATE OR REPLACE VIEW strategy.v_strategy_dsl_readiness_summary AS
WITH latest_specs AS (
    SELECT DISTINCT ON (candidate_id) *
    FROM strategy.strategy_rule_specs
    ORDER BY candidate_id, updated_at DESC, id DESC
),
latest_gates AS (
    SELECT DISTINCT ON (candidate_id) *
    FROM strategy.backtest_data_quality_gates
    ORDER BY candidate_id, created_at DESC, id DESC
)
SELECT
    candidate.id AS candidate_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    candidate.status AS candidate_status,
    candidate.timeframe AS candidate_timeframe,
    candidate.universe,
    coalesce(spec.parse_status, 'not_parsed') AS parse_status,
    coalesce(spec.parse_errors, ARRAY[]::TEXT[]) AS parse_errors,
    spec.template,
    spec.symbols,
    gate.gate_key,
    coalesce(gate.status, 'not_checked') AS data_quality_status,
    coalesce(gate.severity, 'info') AS data_quality_severity,
    coalesce(gate.reasons, ARRAY[]::TEXT[]) AS data_quality_reasons,
    gate.total_rows,
    gate.min_symbol_rows,
    gate.max_symbol_rows,
    gate.first_ts,
    gate.last_ts,
    greatest(coalesce(spec.updated_at, candidate.updated_at), coalesce(gate.created_at, candidate.updated_at)) AS updated_at
FROM strategy.strategy_candidates candidate
LEFT JOIN latest_specs spec ON spec.candidate_id = candidate.id
LEFT JOIN latest_gates gate ON gate.candidate_id = candidate.id;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    ('ai_os_parse_strategy_dsl', 'mcp_tool', 'Strategy Intake Agent', 'write_with_approval', true, 'Parse a user or candidate strategy DSL into deterministic normalized rules. Does not execute trades.', '{"writes":["strategy.strategy_rule_specs"],"execution_allowed":false,"arbitrary_code_allowed":false}'::jsonb),
    ('ai_os_strategy_data_quality_gate', 'mcp_tool', 'Backtest Engineer', 'write_with_approval', true, 'Run and record a real warehouse OHLCV data-quality preflight gate before a strategy backtest.', '{"writes":["strategy.backtest_data_quality_gates"],"reads":["trading.ohlcv"],"seed_data_allowed":false,"execution_allowed":false}'::jsonb),
    ('ai_os_strategy_dsl_status', 'mcp_tool', 'Quant Lab', 'read_only', true, 'Read strategy DSL parse and backtest data-quality readiness status.', '{"reads":["strategy.v_strategy_dsl_readiness_summary","strategy.v_strategy_rule_specs","strategy.v_backtest_data_quality_gates"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
