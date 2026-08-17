BEGIN;

CREATE TABLE IF NOT EXISTS trading.option_valuation_policies (
    id BIGSERIAL PRIMARY KEY,
    policy_key TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    model_family TEXT NOT NULL CHECK (model_family IN ('black_scholes_merton','black_76')),
    risk_free_rate NUMERIC NOT NULL,
    dividend_yield NUMERIC NOT NULL,
    day_count_convention TEXT NOT NULL DEFAULT 'ACT/365F',
    expiry_local_time TIME NOT NULL DEFAULT TIME '15:30:00',
    expiry_timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    rate_source TEXT NOT NULL,
    rate_source_timestamp TIMESTAMPTZ NOT NULL,
    dividend_source TEXT NOT NULL,
    dividend_source_timestamp TIMESTAMPTZ NOT NULL,
    source_artifact_ref TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (validation_status IN ('pending','validated','rejected','expired')),
    validated_by TEXT,
    validated_at TIMESTAMPTZ,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT option_valuation_policy_window CHECK (effective_from < expires_at),
    CONSTRAINT option_valuation_policy_sources_nonempty CHECK (
        btrim(rate_source) <> '' AND btrim(dividend_source) <> '' AND btrim(source_artifact_ref) <> ''
    ),
    CONSTRAINT option_valuation_policy_validation_evidence CHECK (
        validation_status <> 'validated' OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_option_valuation_policy_lookup
    ON trading.option_valuation_policies (provider, exchange, underlying, effective_from DESC)
    WHERE active=true;

CREATE TABLE IF NOT EXISTS ops.institutional_pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    workload_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','degraded','failed','blocked')),
    source_cursor JSONB NOT NULL DEFAULT '{}'::jsonb,
    rows_read INTEGER NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
    rows_written INTEGER NOT NULL DEFAULT 0 CHECK (rows_written >= 0),
    batches_created INTEGER NOT NULL DEFAULT 0 CHECK (batches_created >= 0),
    calculations_completed INTEGER NOT NULL DEFAULT 0 CHECK (calculations_completed >= 0),
    calculations_blocked INTEGER NOT NULL DEFAULT 0 CHECK (calculations_blocked >= 0),
    quality_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    next_run_after TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    CONSTRAINT institutional_pipeline_finished_state CHECK (
        (status='running' AND finished_at IS NULL) OR (status<>'running' AND finished_at IS NOT NULL)
    ),
    CONSTRAINT institutional_pipeline_error_state CHECK (
        status NOT IN ('failed','blocked') OR error_message IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_institutional_pipeline_runs_latest
    ON ops.institutional_pipeline_runs (workload_key, started_at DESC);

CREATE TABLE IF NOT EXISTS sector_intelligence.source_import_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    package_hash TEXT NOT NULL UNIQUE,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id) ON DELETE RESTRICT,
    source_artifact_ref TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('validated','imported','rejected','failed')),
    taxonomy_rows INTEGER NOT NULL DEFAULT 0 CHECK (taxonomy_rows >= 0),
    membership_rows INTEGER NOT NULL DEFAULT 0 CHECK (membership_rows >= 0),
    metric_rows INTEGER NOT NULL DEFAULT 0 CHECK (metric_rows >= 0),
    index_rows INTEGER NOT NULL DEFAULT 0 CHECK (index_rows >= 0),
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    imported_by TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    CONSTRAINT sector_source_import_reference_nonempty CHECK (btrim(source_artifact_ref) <> '')
);

CREATE OR REPLACE VIEW trading.v_option_analytics_readiness AS
WITH latest_batch AS (
    SELECT DISTINCT ON (provider, exchange, underlying)
           id, provider, exchange, underlying, expiry, minute_ts,
           freshness_status, quality_status, contract_count
    FROM trading.option_chain_snapshot_batches
    ORDER BY provider, exchange, underlying, minute_ts DESC, id DESC
), active_policy AS (
    SELECT DISTINCT ON (provider, exchange, underlying)
           id, provider, exchange, underlying, policy_key, model_family,
           expires_at, validation_status
    FROM trading.option_valuation_policies
    WHERE active=true AND effective_from <= now()
    ORDER BY provider, exchange, underlying, effective_from DESC, id DESC
)
SELECT
    batch.provider,
    batch.exchange,
    batch.underlying,
    batch.expiry,
    batch.minute_ts,
    batch.freshness_status,
    batch.quality_status AS batch_quality_status,
    batch.contract_count,
    policy.policy_key,
    policy.model_family,
    policy.expires_at AS policy_expires_at,
    CASE
        WHEN policy.id IS NULL THEN 'blocked_missing_valuation_policy'
        WHEN policy.validation_status <> 'validated' THEN 'blocked_unvalidated_policy'
        WHEN policy.expires_at <= now() THEN 'blocked_expired_policy'
        WHEN batch.quality_status NOT IN ('passed','warning') THEN 'blocked_batch_quality'
        ELSE 'ready'
    END AS analytics_readiness,
    false AS broker_write_allowed
FROM latest_batch batch
LEFT JOIN active_policy policy
  ON policy.provider=batch.provider
 AND policy.exchange=batch.exchange
 AND policy.underlying=batch.underlying;

COMMENT ON TABLE trading.option_valuation_policies IS
    'Human-validated, source-evidenced, expiring point-in-time policy inputs. No default rate or dividend assumption is permitted.';
COMMENT ON TABLE ops.institutional_pipeline_runs IS
    'Durable status and evidence for institutional warehouse workloads; all workloads are analytics-only.';
COMMENT ON TABLE sector_intelligence.source_import_runs IS
    'Auditable imports of licensed exports or primary-source sector packages; package hashes prevent duplicate ingestion.';

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES
(
    'ai_os_materialize_institutional_options','deterministic_worker','Options Data Quality Agent',
    'write_db_scheduled',true,
    'Materialize immutable option-chain batches and run deterministic analytics only when validated source inputs exist.',
    '{"script":"_ai_os_runtime/scripts/materialize_institutional_options.py","reads":["trading.option_chain_snapshots","trading.option_valuation_policies"],"writes":["trading.option_chain_snapshot_batches","trading.option_chain_contract_snapshots","trading.option_valuation_inputs","trading.option_iv_greeks_results","ops.institutional_pipeline_runs"],"paper_only":true,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
),
(
    'ai_os_upsert_option_valuation_policy','mcp_tool','Options Data Quality Agent',
    'write_with_approval',true,
    'Record source-evidenced expiring rates and dividends used by deterministic option analytics.',
    '{"api":"/api/options/valuation-policy/upsert","writes":["trading.option_valuation_policies"],"human_validation_required":true,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
),
(
    'ai_os_import_sector_intelligence_package','mcp_tool','Sector Data Steward',
    'write_with_approval',true,
    'Validate or atomically import licensed or primary-source sector taxonomy, membership, metric and custom-index evidence.',
    '{"api":"/api/sector-intelligence/import","writes":["sector_intelligence.taxonomy_nodes","sector_intelligence.instrument_membership_history","sector_intelligence.metric_observations","sector_intelligence.custom_index_definitions","sector_intelligence.custom_index_constituents","sector_intelligence.source_import_runs"],"seed_data_allowed":false,"live_execution_allowed":false,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
