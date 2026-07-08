CREATE TABLE IF NOT EXISTS agent.model_endpoints (
    id BIGSERIAL PRIMARY KEY,
    endpoint_key TEXT NOT NULL UNIQUE,
    endpoint_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    route_name TEXT REFERENCES agent.model_routes(route_name),
    endpoint_type TEXT NOT NULL DEFAULT 'local',
    base_url TEXT,
    deployment_target TEXT NOT NULL DEFAULT 'external_ssd_or_local_runtime',
    status TEXT NOT NULL DEFAULT 'configured',
    context_window INTEGER,
    estimated_disk_gb NUMERIC,
    cost_tier TEXT NOT NULL DEFAULT 'local',
    capabilities TEXT[] NOT NULL DEFAULT '{}',
    requires_api_key BOOLEAN NOT NULL DEFAULT false,
    secret_ref TEXT,
    health_status TEXT NOT NULL DEFAULT 'unchecked',
    last_checked_at TIMESTAMPTZ,
    last_latency_ms INTEGER,
    last_error TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'AI Engineering',
    notes TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_endpoints_provider ON agent.model_endpoints (provider);
CREATE INDEX IF NOT EXISTS idx_model_endpoints_route ON agent.model_endpoints (route_name);
CREATE INDEX IF NOT EXISTS idx_model_endpoints_health ON agent.model_endpoints (health_status);

CREATE TABLE IF NOT EXISTS core.source_connector_profiles (
    id BIGSERIAL PRIMARY KEY,
    connector_key TEXT NOT NULL UNIQUE,
    connector_name TEXT NOT NULL,
    source_key TEXT REFERENCES core.data_source_registry(source_key),
    connector_type TEXT NOT NULL,
    provider TEXT,
    access_mode TEXT NOT NULL DEFAULT 'read_only',
    status TEXT NOT NULL DEFAULT 'planned',
    freshness_target_minutes INTEGER,
    requires_api_key BOOLEAN NOT NULL DEFAULT false,
    requires_browser_session BOOLEAN NOT NULL DEFAULT false,
    secret_ref TEXT,
    base_url TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    sensitivity TEXT NOT NULL DEFAULT 'private',
    health_status TEXT NOT NULL DEFAULT 'unchecked',
    last_checked_at TIMESTAMPTZ,
    last_latency_ms INTEGER,
    last_rows_seen BIGINT,
    last_error TEXT,
    notes TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_connector_profiles_source ON core.source_connector_profiles (source_key);
CREATE INDEX IF NOT EXISTS idx_source_connector_profiles_status ON core.source_connector_profiles (status);
CREATE INDEX IF NOT EXISTS idx_source_connector_profiles_health ON core.source_connector_profiles (health_status);

CREATE TABLE IF NOT EXISTS core.connector_health_checks (
    id BIGSERIAL PRIMARY KEY,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('model_endpoint', 'data_source_connector')),
    target_key TEXT NOT NULL,
    check_name TEXT NOT NULL,
    check_type TEXT NOT NULL DEFAULT 'configuration',
    status TEXT NOT NULL,
    latency_ms INTEGER,
    rows_seen BIGINT,
    error_message TEXT,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_by TEXT NOT NULL DEFAULT 'Jarvis',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connector_health_checks_target ON core.connector_health_checks (target_kind, target_key, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_connector_health_checks_status ON core.connector_health_checks (status);

CREATE OR REPLACE FUNCTION agent.register_model_endpoint(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_endpoint_key TEXT := lower(regexp_replace(coalesce(nullif(payload->>'endpoint_key', ''), payload->>'route_name', payload->>'model_name', ''), '[^a-zA-Z0-9]+', '_', 'g'));
    v_result JSONB;
BEGIN
    v_endpoint_key := trim(both '_' FROM v_endpoint_key);
    IF v_endpoint_key = '' THEN
        RAISE EXCEPTION 'endpoint_key, route_name, or model_name is required';
    END IF;

    INSERT INTO agent.model_endpoints (
        endpoint_key,
        endpoint_name,
        provider,
        model_name,
        route_name,
        endpoint_type,
        base_url,
        deployment_target,
        status,
        context_window,
        estimated_disk_gb,
        cost_tier,
        capabilities,
        requires_api_key,
        secret_ref,
        owner_agent,
        notes,
        config,
        updated_at
    )
    VALUES (
        v_endpoint_key,
        coalesce(nullif(payload->>'endpoint_name', ''), v_endpoint_key),
        coalesce(nullif(payload->>'provider', ''), 'ollama'),
        coalesce(nullif(payload->>'model_name', ''), 'unknown_model'),
        nullif(payload->>'route_name', ''),
        coalesce(nullif(payload->>'endpoint_type', ''), 'local'),
        nullif(payload->>'base_url', ''),
        coalesce(nullif(payload->>'deployment_target', ''), 'external_ssd_or_local_runtime'),
        coalesce(nullif(payload->>'status', ''), 'configured'),
        nullif(payload->>'context_window', '')::INTEGER,
        nullif(payload->>'estimated_disk_gb', '')::NUMERIC,
        coalesce(nullif(payload->>'cost_tier', ''), 'local'),
        coalesce(
            ARRAY(SELECT jsonb_array_elements_text(payload->'capabilities')),
            ARRAY[]::TEXT[]
        ),
        coalesce((payload->>'requires_api_key')::BOOLEAN, false),
        nullif(payload->>'secret_ref', ''),
        coalesce(nullif(payload->>'owner_agent', ''), 'AI Engineering'),
        nullif(payload->>'notes', ''),
        coalesce(payload->'config', '{}'::jsonb),
        now()
    )
    ON CONFLICT (endpoint_key) DO UPDATE SET
        endpoint_name = EXCLUDED.endpoint_name,
        provider = EXCLUDED.provider,
        model_name = EXCLUDED.model_name,
        route_name = EXCLUDED.route_name,
        endpoint_type = EXCLUDED.endpoint_type,
        base_url = EXCLUDED.base_url,
        deployment_target = EXCLUDED.deployment_target,
        status = EXCLUDED.status,
        context_window = EXCLUDED.context_window,
        estimated_disk_gb = EXCLUDED.estimated_disk_gb,
        cost_tier = EXCLUDED.cost_tier,
        capabilities = EXCLUDED.capabilities,
        requires_api_key = EXCLUDED.requires_api_key,
        secret_ref = EXCLUDED.secret_ref,
        owner_agent = EXCLUDED.owner_agent,
        notes = EXCLUDED.notes,
        config = EXCLUDED.config,
        updated_at = now()
    RETURNING to_jsonb(agent.model_endpoints.*) INTO v_result;

    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION agent.run_model_endpoint_health_check(
    p_endpoint_key TEXT,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    endpoint agent.model_endpoints%ROWTYPE;
    v_status TEXT;
    v_error TEXT;
    v_sample JSONB;
    v_result JSONB;
BEGIN
    SELECT * INTO endpoint
    FROM agent.model_endpoints
    WHERE endpoint_key = p_endpoint_key;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'model endpoint not found: %', p_endpoint_key;
    END IF;

    IF endpoint.status IN ('disabled', 'inactive', 'retired') THEN
        v_status := 'inactive';
        v_error := 'Endpoint is not enabled for runtime use.';
    ELSIF endpoint.requires_api_key AND coalesce(endpoint.secret_ref, '') = '' THEN
        v_status := 'needs_secret';
        v_error := 'Endpoint requires an API key; store only a secret_ref, never the key value.';
    ELSIF endpoint.provider IN ('ollama', 'lm_studio', 'mlx', 'local_http') AND coalesce(endpoint.base_url, '') = '' THEN
        v_status := 'needs_endpoint';
        v_error := 'Local endpoint requires a base_url or runtime socket.';
    ELSE
        v_status := 'configured';
        v_error := NULL;
    END IF;

    v_sample := jsonb_build_object(
        'provider', endpoint.provider,
        'model_name', endpoint.model_name,
        'route_name', endpoint.route_name,
        'endpoint_type', endpoint.endpoint_type,
        'deployment_target', endpoint.deployment_target,
        'secret_policy', CASE WHEN endpoint.requires_api_key THEN 'secret_ref_only' ELSE 'no_secret_required' END
    );

    INSERT INTO core.connector_health_checks (
        target_kind, target_key, check_name, check_type, status,
        error_message, sample_payload, checked_by
    )
    VALUES (
        'model_endpoint', endpoint.endpoint_key, 'model endpoint configuration check',
        'configuration', v_status, v_error, v_sample, coalesce(nullif(p_actor, ''), 'Jarvis')
    )
    RETURNING to_jsonb(core.connector_health_checks.*) INTO v_result;

    UPDATE agent.model_endpoints
    SET health_status = v_status,
        last_checked_at = now(),
        last_latency_ms = NULL,
        last_error = v_error,
        updated_at = now()
    WHERE endpoint_key = endpoint.endpoint_key;

    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION core.register_source_connector(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_connector_key TEXT := lower(regexp_replace(coalesce(nullif(payload->>'connector_key', ''), payload->>'source_key', payload->>'connector_name', ''), '[^a-zA-Z0-9]+', '_', 'g'));
    v_result JSONB;
BEGIN
    v_connector_key := trim(both '_' FROM v_connector_key);
    IF v_connector_key = '' THEN
        RAISE EXCEPTION 'connector_key, source_key, or connector_name is required';
    END IF;

    INSERT INTO core.source_connector_profiles (
        connector_key,
        connector_name,
        source_key,
        connector_type,
        provider,
        access_mode,
        status,
        freshness_target_minutes,
        requires_api_key,
        requires_browser_session,
        secret_ref,
        base_url,
        owner_agent,
        sensitivity,
        notes,
        config,
        updated_at
    )
    VALUES (
        v_connector_key,
        coalesce(nullif(payload->>'connector_name', ''), v_connector_key),
        nullif(payload->>'source_key', ''),
        coalesce(nullif(payload->>'connector_type', ''), 'custom_adapter'),
        nullif(payload->>'provider', ''),
        coalesce(nullif(payload->>'access_mode', ''), 'read_only'),
        coalesce(nullif(payload->>'status', ''), 'configured'),
        nullif(payload->>'freshness_target_minutes', '')::INTEGER,
        coalesce((payload->>'requires_api_key')::BOOLEAN, false),
        coalesce((payload->>'requires_browser_session')::BOOLEAN, false),
        nullif(payload->>'secret_ref', ''),
        nullif(payload->>'base_url', ''),
        coalesce(nullif(payload->>'owner_agent', ''), 'Data Steward'),
        coalesce(nullif(payload->>'sensitivity', ''), 'private'),
        nullif(payload->>'notes', ''),
        coalesce(payload->'config', '{}'::jsonb),
        now()
    )
    ON CONFLICT (connector_key) DO UPDATE SET
        connector_name = EXCLUDED.connector_name,
        source_key = EXCLUDED.source_key,
        connector_type = EXCLUDED.connector_type,
        provider = EXCLUDED.provider,
        access_mode = EXCLUDED.access_mode,
        status = EXCLUDED.status,
        freshness_target_minutes = EXCLUDED.freshness_target_minutes,
        requires_api_key = EXCLUDED.requires_api_key,
        requires_browser_session = EXCLUDED.requires_browser_session,
        secret_ref = EXCLUDED.secret_ref,
        base_url = EXCLUDED.base_url,
        owner_agent = EXCLUDED.owner_agent,
        sensitivity = EXCLUDED.sensitivity,
        notes = EXCLUDED.notes,
        config = EXCLUDED.config,
        updated_at = now()
    RETURNING to_jsonb(core.source_connector_profiles.*) INTO v_result;

    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION core.run_source_connector_health_check(
    p_connector_key TEXT,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    connector core.source_connector_profiles%ROWTYPE;
    v_status TEXT;
    v_error TEXT;
    v_rows_seen BIGINT;
    v_sample JSONB;
    v_result JSONB;
BEGIN
    SELECT * INTO connector
    FROM core.source_connector_profiles
    WHERE connector_key = p_connector_key;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'source connector not found: %', p_connector_key;
    END IF;

    IF connector.status IN ('disabled', 'inactive', 'retired') THEN
        v_status := 'inactive';
        v_error := 'Connector is not enabled.';
        v_rows_seen := NULL;
    ELSIF connector.requires_api_key AND coalesce(connector.secret_ref, '') = '' THEN
        v_status := 'needs_secret';
        v_error := 'Connector requires credentials; store only secret_ref, never raw secrets.';
        v_rows_seen := NULL;
    ELSIF connector.requires_browser_session AND coalesce(connector.config->>'browser_profile', '') = '' THEN
        v_status := 'needs_browser';
        v_error := 'Connector requires a browser session/profile before live checks.';
        v_rows_seen := NULL;
    ELSIF connector.status IN ('planned', 'candidate', 'mapped') THEN
        v_status := 'needs_activation';
        v_error := 'Connector is registered but not marked configured/active yet.';
        v_rows_seen := NULL;
    ELSE
        v_status := 'configured';
        v_error := NULL;
        v_rows_seen := 1;
    END IF;

    v_sample := jsonb_build_object(
        'source_key', connector.source_key,
        'connector_type', connector.connector_type,
        'provider', connector.provider,
        'access_mode', connector.access_mode,
        'base_url_present', coalesce(connector.base_url, '') <> '',
        'secret_policy', CASE WHEN connector.requires_api_key THEN 'secret_ref_only' ELSE 'no_secret_required' END
    );

    INSERT INTO core.connector_health_checks (
        target_kind, target_key, check_name, check_type, status,
        rows_seen, error_message, sample_payload, checked_by
    )
    VALUES (
        'data_source_connector', connector.connector_key, 'source connector configuration check',
        'configuration', v_status, v_rows_seen, v_error, v_sample, coalesce(nullif(p_actor, ''), 'Jarvis')
    )
    RETURNING to_jsonb(core.connector_health_checks.*) INTO v_result;

    UPDATE core.source_connector_profiles
    SET health_status = v_status,
        last_checked_at = now(),
        last_latency_ms = NULL,
        last_rows_seen = v_rows_seen,
        last_error = v_error,
        updated_at = now()
    WHERE connector_key = connector.connector_key;

    RETURN v_result;
END;
$$;

INSERT INTO agent.model_endpoints (
    endpoint_key,
    endpoint_name,
    provider,
    model_name,
    route_name,
    endpoint_type,
    base_url,
    deployment_target,
    status,
    cost_tier,
    capabilities,
    requires_api_key,
    owner_agent,
    notes,
    config
)
SELECT
    trim(both '_' FROM lower(regexp_replace(route_name || '_' || default_provider || '_' || default_model, '[^a-zA-Z0-9]+', '_', 'g'))) AS endpoint_key,
    route_name || ' default endpoint' AS endpoint_name,
    default_provider,
    default_model,
    route_name,
    CASE WHEN default_provider IN ('ollama', 'mlx', 'lm_studio', 'local', 'local_python', 'local_http', 'python', 'deterministic') THEN 'local' ELSE 'cloud_or_external' END,
    CASE WHEN default_provider = 'ollama' THEN 'http://127.0.0.1:11434' ELSE NULL END,
    CASE WHEN default_provider IN ('ollama', 'mlx', 'lm_studio', 'local', 'local_python', 'local_http', 'python', 'deterministic') THEN 'local_machine' ELSE 'external_provider' END,
    CASE WHEN enabled THEN 'configured' ELSE 'inactive' END,
    max_cost_tier,
    ARRAY[task_class]::TEXT[],
    default_provider NOT IN ('ollama', 'mlx', 'lm_studio', 'local', 'local_python', 'local_http', 'python', 'deterministic'),
    'AI Engineering',
    'Derived from agent.model_routes; endpoint readiness is checked separately from route policy.',
    jsonb_build_object('source', 'agent.model_routes', 'escalation_provider', escalation_provider, 'escalation_model', escalation_model)
FROM agent.model_routes
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name = EXCLUDED.endpoint_name,
    provider = EXCLUDED.provider,
    model_name = EXCLUDED.model_name,
    route_name = EXCLUDED.route_name,
    endpoint_type = EXCLUDED.endpoint_type,
    base_url = EXCLUDED.base_url,
    deployment_target = EXCLUDED.deployment_target,
    status = EXCLUDED.status,
    cost_tier = EXCLUDED.cost_tier,
    capabilities = EXCLUDED.capabilities,
    requires_api_key = EXCLUDED.requires_api_key,
    owner_agent = EXCLUDED.owner_agent,
    notes = EXCLUDED.notes,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO core.source_connector_profiles (
    connector_key,
    connector_name,
    source_key,
    connector_type,
    provider,
    access_mode,
    status,
    freshness_target_minutes,
    requires_api_key,
    requires_browser_session,
    secret_ref,
    base_url,
    owner_agent,
    sensitivity,
    notes,
    config
)
SELECT
    source_key || '_connector',
    source_name || ' connector',
    source_key,
    connection_mode,
    provider,
    CASE
        WHEN source_type IN ('broker_api', 'crypto_exchange', 'commodity_gateway') THEN 'read_only'
        WHEN source_type = 'chart_signal_mcp' THEN 'browser_read_capture'
        ELSE 'read_only'
    END,
    CASE
        WHEN status IN ('active', 'installed', 'imported') THEN 'configured'
        WHEN status = 'mapped' THEN 'mapped'
        ELSE 'planned'
    END,
    freshness_target_minutes,
    source_type IN ('broker_api', 'crypto_exchange', 'commodity_gateway', 'vendor_api'),
    connection_mode ILIKE '%browser%' OR source_type IN ('social_browser', 'chart_signal_mcp'),
    NULL,
    CASE WHEN source_location LIKE 'http%' THEN source_location ELSE NULL END,
    owner_agent,
    sensitivity,
    'Derived from core.data_source_registry. This profile controls actual connector readiness and secret/browser requirements.',
    jsonb_build_object('source_registry_status', status, 'source_type', source_type, 'metadata', metadata)
FROM core.v_data_source_registry
ON CONFLICT (connector_key) DO UPDATE SET
    connector_name = EXCLUDED.connector_name,
    source_key = EXCLUDED.source_key,
    connector_type = EXCLUDED.connector_type,
    provider = EXCLUDED.provider,
    access_mode = EXCLUDED.access_mode,
    status = EXCLUDED.status,
    freshness_target_minutes = EXCLUDED.freshness_target_minutes,
    requires_api_key = EXCLUDED.requires_api_key,
    requires_browser_session = EXCLUDED.requires_browser_session,
    base_url = EXCLUDED.base_url,
    owner_agent = EXCLUDED.owner_agent,
    sensitivity = EXCLUDED.sensitivity,
    notes = EXCLUDED.notes,
    config = EXCLUDED.config,
    updated_at = now();

CREATE OR REPLACE VIEW agent.v_model_endpoint_control AS
SELECT
    me.id,
    me.endpoint_key,
    me.endpoint_name,
    me.provider,
    me.model_name,
    me.route_name,
    mr.task_class,
    me.endpoint_type,
    me.base_url,
    me.deployment_target,
    me.status,
    me.context_window,
    me.estimated_disk_gb,
    me.cost_tier,
    me.capabilities,
    me.requires_api_key,
    me.secret_ref IS NOT NULL AS has_secret_ref,
    me.health_status,
    me.last_checked_at,
    me.last_latency_ms,
    me.last_error,
    me.owner_agent,
    me.notes,
    me.config,
    me.updated_at
FROM agent.model_endpoints me
LEFT JOIN agent.model_routes mr ON mr.route_name = me.route_name
ORDER BY
    CASE me.health_status
        WHEN 'configured' THEN 1
        WHEN 'unchecked' THEN 2
        WHEN 'needs_endpoint' THEN 3
        WHEN 'needs_secret' THEN 4
        ELSE 5
    END,
    me.endpoint_key;

CREATE OR REPLACE VIEW core.v_source_connector_control AS
SELECT
    scp.id,
    scp.connector_key,
    scp.connector_name,
    scp.source_key,
    ds.source_name,
    ds.source_type,
    scp.connector_type,
    scp.provider,
    scp.access_mode,
    scp.status,
    scp.freshness_target_minutes,
    scp.requires_api_key,
    scp.requires_browser_session,
    scp.secret_ref IS NOT NULL AS has_secret_ref,
    scp.base_url,
    scp.owner_agent,
    scp.sensitivity,
    scp.health_status,
    scp.last_checked_at,
    scp.last_latency_ms,
    scp.last_rows_seen,
    scp.last_error,
    scp.notes,
    scp.config,
    scp.updated_at
FROM core.source_connector_profiles scp
LEFT JOIN core.data_source_registry ds ON ds.source_key = scp.source_key
ORDER BY
    CASE scp.health_status
        WHEN 'configured' THEN 1
        WHEN 'unchecked' THEN 2
        WHEN 'needs_activation' THEN 3
        WHEN 'needs_browser' THEN 4
        WHEN 'needs_secret' THEN 5
        ELSE 6
    END,
    scp.connector_key;

CREATE OR REPLACE VIEW core.v_connector_health_checks AS
SELECT DISTINCT ON (target_kind, target_key, check_name)
    target_kind,
    target_key,
    check_name,
    check_type,
    status,
    latency_ms,
    rows_seen,
    error_message,
    sample_payload,
    checked_by,
    checked_at
FROM core.connector_health_checks
ORDER BY target_kind, target_key, check_name, checked_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_register_model_endpoint', 'mcp_tool', 'AI Engineering', 'write_db_manual_only', true, 'Register or update a local/cloud model endpoint without storing secrets.', '{"writes":["agent.model_endpoints"],"secret_policy":"secret_ref_only"}'::jsonb),
    ('ai_os_check_model_endpoint', 'mcp_tool', 'AI Engineering', 'write_db_manual_only', true, 'Run model endpoint configuration health check and store evidence.', '{"writes":["core.connector_health_checks"],"reads":["agent.model_endpoints"]}'::jsonb),
    ('ai_os_register_source_connector', 'mcp_tool', 'Data Steward', 'write_db_manual_only', true, 'Register or update a source connector profile without storing secrets.', '{"writes":["core.source_connector_profiles"],"secret_policy":"secret_ref_only"}'::jsonb),
    ('ai_os_check_source_connector', 'mcp_tool', 'Data Steward', 'write_db_manual_only', true, 'Run source connector configuration health check and store evidence.', '{"writes":["core.connector_health_checks"],"reads":["core.source_connector_profiles"]}'::jsonb)
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
            'agent.model_endpoints',
            'agent.v_model_endpoint_control',
            'core.source_connector_profiles',
            'core.v_source_connector_control',
            'core.connector_health_checks',
            'core.v_connector_health_checks'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_register_model_endpoint',
            'ai_os_check_model_endpoint',
            'ai_os_register_source_connector',
            'ai_os_check_source_connector'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use endpoint and connector control views before plugging any new model or data source into agents.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'command_center', 'approval_center');
