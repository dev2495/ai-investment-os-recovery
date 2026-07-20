BEGIN;

CREATE TABLE IF NOT EXISTS trading.broker_read_snapshots (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    account_ref TEXT NOT NULL,
    dataset TEXT NOT NULL CHECK (dataset IN ('holdings','positions','orders','trades','funds')),
    source_connector_key TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL DEFAULT 'Dhan Read-Only Connector',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed = false),
    UNIQUE (provider, account_ref, dataset, payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_broker_read_snapshots_latest
    ON trading.broker_read_snapshots (provider, account_ref, dataset, retrieved_at DESC);

CREATE OR REPLACE VIEW trading.v_latest_broker_read_snapshots AS
SELECT DISTINCT ON (provider, account_ref, dataset)
       id, run_key, provider, account_ref, dataset, source_connector_key,
       row_count, payload_hash, retrieved_at, created_by, broker_write_allowed
FROM trading.broker_read_snapshots
ORDER BY provider, account_ref, dataset, retrieved_at DESC, id DESC;

UPDATE core.data_source_registry
SET connection_mode='api_read_only', freshness_target_minutes=5,
    owner_agent='Portfolio Manager',
    notes='Primary broker adapter selected for read-only holdings, positions, orders, trades, funds, derivatives, options, and MCX. Credentials are required; broker writes remain disabled.',
    metadata=metadata || '{"primary_broker_adapter":true,"execution_allowed":false,"credential_state":"required","datasets":["holdings","positions","orders","trades","funds"],"market_scope":["NSE","BSE","MCX"]}'::jsonb,
    updated_at=now()
WHERE source_key='dhan_live';

UPDATE core.data_source_registry
SET notes='Optional secondary read-only holdings and trade source. Dhan is the primary adapter for the first production connector.',
    metadata=metadata || '{"primary_broker_adapter":false,"execution_allowed":false}'::jsonb,
    updated_at=now()
WHERE source_key='zerodha_live';

UPDATE core.source_connector_profiles
SET connector_type='broker_api_read_only', access_mode='read_only',
    freshness_target_minutes=5, requires_api_key=true, requires_browser_session=false,
    base_url='https://api.dhan.co/v2',
    health_status=CASE WHEN secret_ref IS NULL THEN 'needs_secret' ELSE health_status END,
    last_error=CASE WHEN secret_ref IS NULL THEN 'Set AI_OS_DHAN_CLIENT_ID and AI_OS_DHAN_ACCESS_TOKEN in the protected iMac environment.' ELSE last_error END,
    notes='Primary read-only Dhan adapter. GET endpoints only; order placement and all broker writes are absent from the connector.',
    config='{"datasets":["holdings","positions","orders","trades","funds"],"execution_allowed":false,"secret_env_refs":["AI_OS_DHAN_CLIENT_ID","AI_OS_DHAN_ACCESS_TOKEN"]}'::jsonb,
    updated_at=now()
WHERE connector_key='dhan_live_connector';

UPDATE core.source_connector_profiles SET updated_at=updated_at
WHERE connector_key IN ('dhan_live_connector','zerodha_live_connector');

ALTER TABLE core.integration_jobs DROP CONSTRAINT IF EXISTS integration_jobs_executor_allowlist;
ALTER TABLE core.integration_jobs ADD CONSTRAINT integration_jobs_executor_allowlist CHECK (
    executor_key IN ('market_news_ingestion','filings_collection','tick_ohlcv_aggregation',
        'tradingview_quote_refresh','public_source_check','provider_readiness',
        'legacy_market_data_ingestion','dhan_read_sync')
);

INSERT INTO core.integration_jobs (
    job_key, plugin_key, job_name, job_type, executor_key, schedule_cron,
    timezone, enabled, run_mode, overlap_policy, timeout_seconds, parameters,
    approval_required, owner_agent, notes
) VALUES (
    'dhan_read_snapshot_5m', 'data_source:dhan_live_connector',
    'Dhan read-only account snapshot', 'poll', 'dhan_read_sync', '*/5 * * * 1-5',
    'Asia/Kolkata', false, 'manual_or_schedule', 'skip', 120,
    '{"datasets":["holdings","positions","orders","trades","funds"],"broker_write_allowed":false}'::jsonb,
    false, 'Data Engineering Agent', 'Disabled until protected credentials pass a live read-only health check.'
) ON CONFLICT (job_key) DO UPDATE SET
    plugin_key=EXCLUDED.plugin_key, executor_key=EXCLUDED.executor_key,
    schedule_cron=EXCLUDED.schedule_cron, enabled=false,
    parameters=EXCLUDED.parameters, notes=EXCLUDED.notes, updated_at=now();

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, cost_tier, capabilities,
    requires_api_key, secret_ref, health_status, owner_agent, notes, config
) VALUES
    ('openrouter_minimax_m2_5', 'OpenRouter MiniMax M2.5 low-cost escalation', 'openrouter',
     'minimax/minimax-m2.5', 'frontier_investment_review', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_approval', 'configured', 204800,
     'cloud_low', ARRAY['text','research_synthesis','long_context'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Low-cost cloud candidate. No client-private prompt leaves the local system without explicit approval.',
     '{"budget_inr_monthly":1000,"approval_required":true,"raw_prompt_storage":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_glm_5_2', 'OpenRouter GLM 5.2 heavy escalation', 'openrouter',
     'z-ai/glm-5.2', 'frontier_investment_review', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_approval', 'configured', 1048576,
     'cloud_high', ARRAY['text','deep_research','long_context'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Heavy cloud candidate for approved deep research only; never the daily driver.',
     '{"budget_inr_monthly":1500,"approval_required":true,"raw_prompt_storage":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    model_name=EXCLUDED.model_name, base_url=EXCLUDED.base_url,
    status=CASE WHEN agent.model_endpoints.secret_ref IS NULL THEN 'configured' ELSE agent.model_endpoints.status END,
    health_status=CASE WHEN agent.model_endpoints.secret_ref IS NULL THEN 'needs_secret' ELSE agent.model_endpoints.health_status END,
    notes=EXCLUDED.notes, config=EXCLUDED.config, updated_at=now();

UPDATE agent.model_routes
SET escalation_provider='openrouter', escalation_model='minimax/minimax-m2.5',
    notes='Local route remains default. Low-cost OpenRouter escalation is credential- and approval-gated.'
WHERE route_name IN ('daily_brief','news_curation','obsidian_retrieval_summary','research_company_analysis');

UPDATE agent.model_routes
SET default_provider='cloud_optional', default_model='frontier_on_approval',
    escalation_provider='openrouter', escalation_model='z-ai/glm-5.2',
    notes='Human-approved heavy research route. Local evidence assembly is mandatory before cloud use; client-private context is blocked by default.'
WHERE route_name='frontier_investment_review';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES ('ai_os_dhan_read_snapshot', 'script_adapter', 'Data Engineering Agent',
    'write_db_manual_only', true,
    'Fetch Dhan holdings, positions, orders, trades, and funds with GET-only calls and append immutable snapshots. Requires protected iMac credentials.',
    '{"script":"_ai_os_runtime/scripts/sync_dhan_read_only.py","writes":["trading.broker_read_snapshots","core.connector_health_checks"],"broker_write_allowed":false,"execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET description=EXCLUDED.description, config=EXCLUDED.config, enabled=true;

COMMIT;
