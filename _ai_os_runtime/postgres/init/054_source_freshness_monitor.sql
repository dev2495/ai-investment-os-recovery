CREATE TABLE IF NOT EXISTS core.data_source_freshness_checks (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL REFERENCES core.data_source_registry(source_key) ON DELETE CASCADE,
    source_name TEXT,
    freshness_target_minutes INTEGER,
    latest_check_at TIMESTAMPTZ,
    latest_ok_at TIMESTAMPTZ,
    latest_quote_at TIMESTAMPTZ,
    staleness_minutes NUMERIC,
    status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    rows_seen BIGINT,
    risk_event_id BIGINT REFERENCES risk.events(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Data Steward',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_source_freshness_key_time ON core.data_source_freshness_checks (source_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_source_freshness_status ON core.data_source_freshness_checks (status);
CREATE INDEX IF NOT EXISTS idx_data_source_freshness_risk ON core.data_source_freshness_checks (risk_event_id);

CREATE OR REPLACE VIEW core.v_data_source_freshness_checks AS
SELECT
    fc.id,
    fc.source_key,
    fc.source_name,
    ds.source_type,
    ds.provider,
    ds.connection_mode,
    ds.owner_agent,
    ds.sensitivity,
    fc.freshness_target_minutes,
    fc.latest_check_at,
    fc.latest_ok_at,
    fc.latest_quote_at,
    fc.staleness_minutes,
    fc.status,
    fc.severity,
    fc.rows_seen,
    fc.risk_event_id,
    re.status AS risk_event_status,
    re.title AS risk_event_title,
    fc.evidence,
    fc.created_by,
    fc.created_at
FROM core.data_source_freshness_checks fc
LEFT JOIN core.data_source_registry ds ON ds.source_key = fc.source_key
LEFT JOIN risk.events re ON re.id = fc.risk_event_id
ORDER BY fc.created_at DESC, fc.id DESC;

CREATE OR REPLACE VIEW core.v_latest_data_source_freshness AS
SELECT DISTINCT ON (source_key)
    *
FROM core.v_data_source_freshness_checks
ORDER BY source_key, created_at DESC, id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_check_source_freshness',
        'mcp_tool',
        'Data Steward',
        'write_db_manual_only',
        true,
        'Evaluate data-source freshness targets, create or close risk events for stale sources, and write auditable freshness rows.',
        '{"script":"_ai_os_runtime/scripts/check_source_freshness.py","writes":["core.data_source_freshness_checks","risk.events"],"reads":["core.data_source_registry","core.data_source_checks","market.price_quotes"],"execution_allowed":false}'::jsonb
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
            'core.data_source_freshness_checks',
            'core.v_latest_data_source_freshness',
            'risk.events'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_check_source_freshness']::TEXT[]) AS tool
    ),
    next_action = 'Run source freshness monitor after quote/filing collectors; add scheduled launchd cadence after policy approval.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'research_inbox', 'trading_desk');
