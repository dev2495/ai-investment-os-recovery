CREATE TABLE IF NOT EXISTS core.provider_readiness_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    model_checks_run INTEGER NOT NULL DEFAULT 0,
    source_checks_run INTEGER NOT NULL DEFAULT 0,
    ready_count INTEGER NOT NULL DEFAULT 0,
    needs_check_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    degraded_count INTEGER NOT NULL DEFAULT 0,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_provider_readiness_runs_created
ON core.provider_readiness_runs (created_at DESC);

CREATE OR REPLACE VIEW core.v_provider_readiness_board AS
WITH model_rows AS (
    SELECT
        'model_endpoint'::TEXT AS provider_kind,
        model.endpoint_key AS provider_key,
        model.endpoint_name AS provider_name,
        model.provider AS provider,
        model.model_name AS subject_name,
        model.route_name AS route_or_source,
        model.endpoint_type AS provider_type,
        model.status,
        model.health_status,
        model.requires_api_key,
        model.has_secret_ref,
        false AS requires_browser_session,
        true AS browser_ready,
        model.cost_tier,
        model.owner_agent,
        model.last_checked_at,
        model.last_error,
        model.updated_at,
        CASE
            WHEN model.status IN ('disabled', 'inactive', 'retired') THEN 'inactive'
            WHEN model.requires_api_key AND NOT model.has_secret_ref THEN 'blocked_secret'
            WHEN model.health_status = 'unchecked' THEN 'needs_check'
            WHEN model.health_status IN ('needs_endpoint', 'needs_secret') THEN 'blocked_configuration'
            WHEN model.health_status = 'configured' AND model.cost_tier IN ('local', 'local_plus') THEN 'ready'
            WHEN model.health_status = 'configured' THEN 'approval_required'
            ELSE 'degraded'
        END AS readiness_status,
        CASE
            WHEN model.status IN ('disabled', 'inactive', 'retired') THEN 'Endpoint inactive.'
            WHEN model.requires_api_key AND NOT model.has_secret_ref THEN 'Missing secret_ref. Store only secret references, never raw keys.'
            WHEN model.health_status = 'unchecked' THEN 'Run model endpoint health check.'
            WHEN model.health_status IN ('needs_endpoint', 'needs_secret') THEN coalesce(model.last_error, 'Model endpoint configuration incomplete.')
            WHEN model.health_status = 'configured' AND model.cost_tier NOT IN ('local', 'local_plus') THEN 'Usable only through explicit approval/cost policy.'
            WHEN model.health_status = 'configured' THEN 'Ready for local/approved agent routing.'
            ELSE coalesce(model.last_error, 'Endpoint degraded or unknown.')
        END AS next_action,
        CASE
            WHEN model.health_status = 'configured' AND NOT (model.requires_api_key AND NOT model.has_secret_ref) THEN true
            ELSE false
        END AS assignable
    FROM agent.v_model_endpoint_control model
),
source_rows AS (
    SELECT
        'source_connector'::TEXT AS provider_kind,
        source.connector_key AS provider_key,
        source.connector_name AS provider_name,
        source.provider AS provider,
        coalesce(source.source_name, source.source_key, source.connector_name) AS subject_name,
        source.source_key AS route_or_source,
        source.connector_type AS provider_type,
        source.status,
        source.health_status,
        source.requires_api_key,
        source.has_secret_ref,
        source.requires_browser_session,
        CASE
            WHEN source.requires_browser_session THEN source.health_status NOT IN ('needs_browser', 'needs_browser_check', 'browser_unavailable')
            ELSE true
        END AS browser_ready,
        'data'::TEXT AS cost_tier,
        source.owner_agent,
        source.last_checked_at,
        source.last_error,
        source.updated_at,
        CASE
            WHEN source.status IN ('disabled', 'inactive', 'retired') THEN 'inactive'
            WHEN source.requires_api_key AND NOT source.has_secret_ref THEN 'blocked_secret'
            WHEN source.requires_browser_session AND source.health_status IN ('needs_browser', 'needs_browser_check', 'browser_unavailable') THEN 'blocked_browser'
            WHEN source.status IN ('planned', 'candidate', 'mapped') OR source.health_status = 'needs_activation' THEN 'needs_activation'
            WHEN source.health_status = 'unchecked' THEN 'needs_check'
            WHEN source.health_status = 'configured' THEN 'ready'
            ELSE 'degraded'
        END AS readiness_status,
        CASE
            WHEN source.status IN ('disabled', 'inactive', 'retired') THEN 'Connector inactive.'
            WHEN source.requires_api_key AND NOT source.has_secret_ref THEN 'Missing secret_ref. Store only secret references, never raw keys.'
            WHEN source.requires_browser_session AND source.health_status IN ('needs_browser', 'needs_browser_check', 'browser_unavailable') THEN coalesce(source.last_error, 'Attach and verify browser profile/session.')
            WHEN source.status IN ('planned', 'candidate', 'mapped') OR source.health_status = 'needs_activation' THEN 'Activate/configure connector after confirming source access and permissions.'
            WHEN source.health_status = 'unchecked' THEN 'Run source connector health check.'
            WHEN source.health_status = 'configured' THEN 'Ready for read-only ingestion or retrieval.'
            ELSE coalesce(source.last_error, 'Connector degraded or unknown.')
        END AS next_action,
        CASE
            WHEN source.health_status = 'configured'
              AND NOT (source.requires_api_key AND NOT source.has_secret_ref)
              AND NOT (source.requires_browser_session AND source.health_status IN ('needs_browser', 'needs_browser_check', 'browser_unavailable'))
            THEN true
            ELSE false
        END AS assignable
    FROM core.v_source_connector_control source
)
SELECT
    row_number() OVER (
        ORDER BY
            CASE readiness_status
                WHEN 'blocked_secret' THEN 1
                WHEN 'blocked_browser' THEN 2
                WHEN 'blocked_configuration' THEN 3
                WHEN 'needs_activation' THEN 4
                WHEN 'needs_check' THEN 5
                WHEN 'degraded' THEN 6
                WHEN 'approval_required' THEN 7
                WHEN 'ready' THEN 8
                ELSE 9
            END,
            provider_kind,
            provider_key
    ) AS id,
    *
FROM (
    SELECT * FROM model_rows
    UNION ALL
    SELECT * FROM source_rows
) combined;

CREATE OR REPLACE VIEW core.v_provider_readiness_summary AS
SELECT 'total_providers'::TEXT AS metric, count(*)::TEXT AS value, 'All model endpoints plus source connectors.'::TEXT AS detail
FROM core.v_provider_readiness_board
UNION ALL
SELECT 'ready_providers', count(*)::TEXT, 'Assignable providers with configured health.'
FROM core.v_provider_readiness_board
WHERE readiness_status = 'ready'
UNION ALL
SELECT 'blocked_providers', count(*)::TEXT, 'Providers blocked by missing secret/browser/configuration.'
FROM core.v_provider_readiness_board
WHERE readiness_status LIKE 'blocked%'
UNION ALL
SELECT 'needs_check', count(*)::TEXT, 'Providers needing health checks.'
FROM core.v_provider_readiness_board
WHERE readiness_status = 'needs_check'
UNION ALL
SELECT 'approval_required', count(*)::TEXT, 'Usable providers requiring cost or human approval.'
FROM core.v_provider_readiness_board
WHERE readiness_status = 'approval_required';

CREATE OR REPLACE VIEW core.v_provider_readiness_runs AS
SELECT
    id,
    run_key,
    status,
    model_checks_run,
    source_checks_run,
    ready_count,
    needs_check_count,
    blocked_count,
    degraded_count,
    summary,
    error_message,
    started_at,
    finished_at,
    duration_ms,
    created_by,
    created_at
FROM core.provider_readiness_runs
ORDER BY started_at DESC, id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_provider_readiness_sweep', 'mcp_tool', 'Jarvis', 'write_db_manual_only', true,
     'Run health checks for registered model endpoints and source connectors, then summarize which providers are ready, blocked, degraded, or approval-gated.',
     '{"script":"_ai_os_runtime/scripts/run_provider_readiness_sweep.py","reads":["agent.v_model_endpoint_control","core.v_source_connector_control"],"writes":["core.connector_health_checks","core.provider_readiness_runs"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_provider_readiness_board', 'mcp_tool', 'Jarvis', 'read_only', true,
     'Read model/data-source provider readiness board for plugging in models and data sources.',
     '{"reads":["core.v_provider_readiness_board","core.v_provider_readiness_summary","core.v_provider_readiness_runs"],"live_execution_allowed":false}'::jsonb)
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
            'core.provider_readiness_runs',
            'core.v_provider_readiness_board',
            'core.v_provider_readiness_summary',
            'core.v_provider_readiness_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_run_provider_readiness_sweep',
            'ai_os_provider_readiness_board'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use provider readiness board before assigning new model endpoints or data-source connectors to agents.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'runtime', 'automation');
