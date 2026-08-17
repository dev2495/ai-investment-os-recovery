BEGIN;

CREATE TABLE IF NOT EXISTS trading.option_valuation_source_observations (
    id BIGSERIAL PRIMARY KEY,
    observation_key TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('zerodha_tbill_zero_rate','nse_index_dashboard_dividend')),
    metric_kind TEXT NOT NULL CHECK (metric_kind IN ('risk_free_rate','dividend_yield')),
    provider TEXT NOT NULL,
    exchange TEXT,
    underlying TEXT,
    instrument_identifier TEXT,
    value_decimal NUMERIC NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    source_url TEXT NOT NULL,
    raw_artifact_id BIGINT NOT NULL REFERENCES core.raw_artifacts(id) ON DELETE RESTRICT,
    content_hash TEXT NOT NULL,
    calculation_method TEXT NOT NULL,
    calculation_inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed','warning','blocked','rejected')),
    quality_checks JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_by TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_valuation_source_window CHECK (observed_at < valid_until),
    CONSTRAINT option_valuation_source_hash_nonempty CHECK (btrim(content_hash) <> ''),
    CONSTRAINT option_valuation_source_value_range CHECK (value_decimal >= -0.20 AND value_decimal <= 1.00)
);

CREATE INDEX IF NOT EXISTS idx_option_valuation_source_latest
    ON trading.option_valuation_source_observations
    (metric_kind, underlying, observed_at DESC, id DESC)
    WHERE quality_status IN ('passed','warning');

ALTER TABLE trading.option_valuation_policies
    ADD COLUMN IF NOT EXISTS rate_observation_id BIGINT REFERENCES trading.option_valuation_source_observations(id),
    ADD COLUMN IF NOT EXISTS dividend_observation_id BIGINT REFERENCES trading.option_valuation_source_observations(id),
    ADD COLUMN IF NOT EXISTS operator_confirmed BOOLEAN NOT NULL DEFAULT false;

CREATE OR REPLACE VIEW trading.v_option_valuation_source_candidates AS
WITH rate AS (
    SELECT DISTINCT ON (metric_kind)
           id, value_decimal, observed_at, valid_until, source_url,
           raw_artifact_id, content_hash, calculation_method, calculation_inputs,
           quality_status, instrument_identifier
    FROM trading.option_valuation_source_observations
    WHERE metric_kind='risk_free_rate'
      AND quality_status IN ('passed','warning') AND valid_until > now()
    ORDER BY metric_kind, observed_at DESC, id DESC
), dividends AS (
    SELECT DISTINCT ON (underlying)
           id, underlying, value_decimal, observed_at, valid_until,
           source_url, raw_artifact_id, content_hash, quality_status
    FROM trading.option_valuation_source_observations
    WHERE metric_kind='dividend_yield'
      AND quality_status IN ('passed','warning') AND valid_until > now()
    ORDER BY underlying, observed_at DESC, id DESC
)
SELECT
    dividends.underlying,
    rate.id AS rate_observation_id,
    rate.value_decimal AS risk_free_rate,
    rate.observed_at AS rate_observed_at,
    rate.valid_until AS rate_valid_until,
    rate.instrument_identifier AS rate_instrument_identifier,
    rate.source_url AS rate_source_url,
    rate.content_hash AS rate_content_hash,
    rate.calculation_method AS rate_calculation_method,
    rate.calculation_inputs AS rate_calculation_inputs,
    rate.quality_status AS rate_quality_status,
    dividends.id AS dividend_observation_id,
    dividends.value_decimal AS dividend_yield,
    dividends.observed_at AS dividend_observed_at,
    dividends.valid_until AS dividend_valid_until,
    dividends.source_url AS dividend_source_url,
    dividends.content_hash AS dividend_content_hash,
    dividends.quality_status AS dividend_quality_status,
    concat('raw-artifact:',rate.raw_artifact_id,',raw-artifact:',dividends.raw_artifact_id) AS source_artifact_ref,
    least(rate.valid_until, dividends.valid_until) AS candidate_valid_until,
    false AS operator_confirmed,
    false AS broker_write_allowed
FROM dividends
CROSS JOIN rate;

COMMENT ON TABLE trading.option_valuation_source_observations IS
    'Immutable source observations for option valuation. Collection never activates a policy; explicit operator confirmation remains required.';
COMMENT ON VIEW trading.v_option_valuation_source_candidates IS
    'Latest unexpired source-backed rate/dividend pairs offered for human review. Candidates are not active valuation policies.';

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES (
    'ai_os_refresh_option_valuation_sources','deterministic_worker','Options Data Quality Agent',
    'write_db_scheduled',true,
    'Collect and retain official option-valuation inputs as review candidates without activating policy or allowing execution.',
    '{"api":"/api/options/valuation-sources/refresh","writes":["core.raw_artifacts","trading.option_valuation_source_observations"],"human_activation_required":true,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
