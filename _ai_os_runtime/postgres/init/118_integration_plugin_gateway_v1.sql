CREATE OR REPLACE FUNCTION core.jsonb_contains_raw_secret(payload JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    item RECORD;
    element JSONB;
    normalized_key TEXT;
BEGIN
    IF payload IS NULL THEN
        RETURN false;
    END IF;
    IF jsonb_typeof(payload) = 'object' THEN
        FOR item IN SELECT key, value FROM jsonb_each(payload)
        LOOP
            normalized_key := lower(regexp_replace(item.key, '[^a-z0-9]+', '_', 'g'));
            IF normalized_key IN (
                'api_key', 'access_token', 'refresh_token', 'password',
                'secret', 'client_secret', 'private_key', 'auth_token'
            ) THEN
                RETURN true;
            END IF;
            IF core.jsonb_contains_raw_secret(item.value) THEN
                RETURN true;
            END IF;
        END LOOP;
    ELSIF jsonb_typeof(payload) = 'array' THEN
        FOR element IN SELECT value FROM jsonb_array_elements(payload)
        LOOP
            IF core.jsonb_contains_raw_secret(element) THEN
                RETURN true;
            END IF;
        END LOOP;
    END IF;
    RETURN false;
END;
$$;

CREATE TABLE IF NOT EXISTS core.integration_plugins (
    id BIGSERIAL PRIMARY KEY,
    plugin_key TEXT NOT NULL UNIQUE,
    plugin_kind TEXT NOT NULL CHECK (plugin_kind IN ('data_source', 'model_provider')),
    target_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    adapter_key TEXT NOT NULL,
    adapter_version TEXT NOT NULL DEFAULT '1',
    lifecycle_status TEXT NOT NULL DEFAULT 'configured'
        CHECK (lifecycle_status IN ('draft', 'configured', 'active', 'disabled', 'retired')),
    access_mode TEXT NOT NULL DEFAULT 'read_only',
    capabilities TEXT[] NOT NULL DEFAULT '{}',
    config_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    credential_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    operational_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    owner_agent TEXT NOT NULL DEFAULT 'Integration Engineer',
    notes TEXT,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (plugin_kind, target_key),
    CONSTRAINT integration_plugins_no_raw_secrets
        CHECK (NOT core.jsonb_contains_raw_secret(configuration))
);

CREATE INDEX IF NOT EXISTS idx_integration_plugins_kind
    ON core.integration_plugins (plugin_kind, lifecycle_status, enabled);
CREATE INDEX IF NOT EXISTS idx_integration_plugins_capabilities
    ON core.integration_plugins USING GIN (capabilities);

CREATE TABLE IF NOT EXISTS core.integration_schema_mappings (
    id BIGSERIAL PRIMARY KEY,
    mapping_key TEXT NOT NULL UNIQUE,
    plugin_key TEXT NOT NULL REFERENCES core.integration_plugins(plugin_key) ON DELETE CASCADE,
    dataset_key TEXT NOT NULL,
    target_relation TEXT NOT NULL,
    source_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    field_mappings JSONB NOT NULL DEFAULT '{}'::jsonb,
    transformations JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_key_fields TEXT[] NOT NULL DEFAULT '{}',
    timestamp_field TEXT,
    schema_version TEXT NOT NULL DEFAULT '1',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'configured', 'active', 'disabled')),
    validation_status TEXT NOT NULL DEFAULT 'not_checked'
        CHECK (validation_status IN ('not_checked', 'passed', 'failed')),
    validation_errors TEXT[] NOT NULL DEFAULT '{}',
    last_validated_at TIMESTAMPTZ,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    notes TEXT,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT integration_mappings_no_raw_secrets
        CHECK (NOT core.jsonb_contains_raw_secret(source_schema)
           AND NOT core.jsonb_contains_raw_secret(field_mappings)
           AND NOT core.jsonb_contains_raw_secret(transformations))
);

CREATE INDEX IF NOT EXISTS idx_integration_schema_mappings_plugin
    ON core.integration_schema_mappings (plugin_key, status, validation_status);

CREATE TABLE IF NOT EXISTS core.integration_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_key TEXT NOT NULL UNIQUE,
    plugin_key TEXT NOT NULL REFERENCES core.integration_plugins(plugin_key) ON DELETE CASCADE,
    job_name TEXT NOT NULL,
    job_type TEXT NOT NULL CHECK (job_type IN ('poll', 'import', 'stream', 'aggregate', 'health_check', 'provider_probe')),
    executor_key TEXT NOT NULL,
    schedule_cron TEXT,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    enabled BOOLEAN NOT NULL DEFAULT false,
    run_mode TEXT NOT NULL DEFAULT 'manual_or_schedule'
        CHECK (run_mode IN ('manual', 'schedule', 'manual_or_schedule', 'daemon')),
    overlap_policy TEXT NOT NULL DEFAULT 'skip'
        CHECK (overlap_policy IN ('skip', 'queue', 'replace')),
    timeout_seconds INTEGER NOT NULL DEFAULT 300 CHECK (timeout_seconds BETWEEN 5 AND 3600),
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    last_run_status TEXT,
    last_started_at TIMESTAMPTZ,
    last_finished_at TIMESTAMPTZ,
    last_rows_written BIGINT,
    last_error TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Data Engineering Agent',
    notes TEXT,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT integration_jobs_no_raw_secrets
        CHECK (NOT core.jsonb_contains_raw_secret(checkpoint)
           AND NOT core.jsonb_contains_raw_secret(parameters))
);

CREATE INDEX IF NOT EXISTS idx_integration_jobs_plugin
    ON core.integration_jobs (plugin_key, enabled, job_type);

ALTER TABLE core.integration_jobs
    DROP CONSTRAINT IF EXISTS integration_jobs_executor_allowlist;
ALTER TABLE core.integration_jobs
    ADD CONSTRAINT integration_jobs_executor_allowlist CHECK (
        executor_key IN (
            'market_news_ingestion',
            'filings_collection',
            'tick_ohlcv_aggregation',
            'tradingview_quote_refresh',
            'public_source_check',
            'provider_readiness'
        )
    );

CREATE TABLE IF NOT EXISTS core.integration_job_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    job_key TEXT NOT NULL REFERENCES core.integration_jobs(job_key) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    trigger_kind TEXT NOT NULL DEFAULT 'manual' CHECK (trigger_kind IN ('manual', 'schedule', 'daemon', 'api')),
    rows_read BIGINT,
    rows_written BIGINT,
    checkpoint_before JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_after JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    artifact_path TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    requested_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT integration_job_runs_no_raw_secrets
        CHECK (NOT core.jsonb_contains_raw_secret(checkpoint_before)
           AND NOT core.jsonb_contains_raw_secret(checkpoint_after)
           AND NOT core.jsonb_contains_raw_secret(result_summary))
);

CREATE INDEX IF NOT EXISTS idx_integration_job_runs_job
    ON core.integration_job_runs (job_key, created_at DESC);

CREATE OR REPLACE FUNCTION core.sync_integration_plugin_from_target()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_plugin_key TEXT;
    v_source_type TEXT;
BEGIN
    IF TG_TABLE_SCHEMA = 'core' AND TG_TABLE_NAME = 'source_connector_profiles' THEN
        SELECT source_type INTO v_source_type
        FROM core.data_source_registry
        WHERE source_key = NEW.source_key;

        v_plugin_key := 'data_source:' || NEW.connector_key;
        INSERT INTO core.integration_plugins (
            plugin_key, plugin_kind, target_key, display_name, adapter_key,
            lifecycle_status, access_mode, capabilities, config_schema,
            credential_contract, operational_contract, configuration,
            enabled, approval_required, owner_agent, notes, created_by, updated_at
        ) VALUES (
            v_plugin_key, 'data_source', NEW.connector_key, NEW.connector_name,
            lower(regexp_replace(coalesce(NEW.connector_type, 'connector'), '[^a-zA-Z0-9]+', '_', 'g')),
            CASE WHEN NEW.status IN ('active') THEN 'active'
                 WHEN NEW.status IN ('disabled', 'inactive', 'retired') THEN 'disabled'
                 WHEN NEW.status IN ('planned', 'candidate') THEN 'draft'
                 ELSE 'configured' END,
            NEW.access_mode,
            ARRAY_REMOVE(ARRAY[v_source_type, NEW.connector_type], NULL),
            jsonb_build_object(
                'source_key', NEW.source_key,
                'connector_type', NEW.connector_type,
                'base_url_allowed', true,
                'configuration_format', 'json_object'
            ),
            jsonb_build_object(
                'requires_api_key', NEW.requires_api_key,
                'secret_ref_configured', coalesce(NEW.secret_ref, '') <> '',
                'secret_storage_policy', 'reference_only_never_raw'
            ),
            jsonb_build_object(
                'freshness_target_minutes', NEW.freshness_target_minutes,
                'requires_browser_session', NEW.requires_browser_session,
                'mapping_required', NEW.connector_type NOT IN ('local_app_bridge', 'mcp_or_browser_task'),
                'scheduled_job_required', NEW.freshness_target_minutes IS NOT NULL
                    AND NEW.connector_type NOT IN ('mcp_or_browser_task', 'browser_agent')
            ),
            jsonb_build_object('base_url', NEW.base_url, 'source_key', NEW.source_key),
            NEW.status NOT IN ('disabled', 'inactive', 'retired'),
            NEW.access_mode NOT IN ('read_only', 'browser_read_capture'),
            NEW.owner_agent, NEW.notes, 'target_sync', now()
        )
        ON CONFLICT (plugin_kind, target_key) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            adapter_key = EXCLUDED.adapter_key,
            lifecycle_status = EXCLUDED.lifecycle_status,
            access_mode = EXCLUDED.access_mode,
            capabilities = EXCLUDED.capabilities,
            config_schema = EXCLUDED.config_schema,
            credential_contract = EXCLUDED.credential_contract,
            operational_contract = EXCLUDED.operational_contract,
            configuration = EXCLUDED.configuration,
            enabled = EXCLUDED.enabled,
            approval_required = EXCLUDED.approval_required,
            owner_agent = EXCLUDED.owner_agent,
            notes = EXCLUDED.notes,
            updated_at = now();
    ELSIF TG_TABLE_SCHEMA = 'agent' AND TG_TABLE_NAME = 'model_endpoints' THEN
        v_plugin_key := 'model_provider:' || NEW.endpoint_key;
        INSERT INTO core.integration_plugins (
            plugin_key, plugin_kind, target_key, display_name, adapter_key,
            lifecycle_status, access_mode, capabilities, config_schema,
            credential_contract, operational_contract, configuration,
            enabled, approval_required, owner_agent, notes, created_by, updated_at
        ) VALUES (
            v_plugin_key, 'model_provider', NEW.endpoint_key, NEW.endpoint_name,
            lower(regexp_replace(coalesce(NEW.provider, 'model'), '[^a-zA-Z0-9]+', '_', 'g')),
            CASE WHEN NEW.status IN ('active') THEN 'active'
                 WHEN NEW.status IN ('disabled', 'inactive', 'retired') THEN 'disabled'
                 ELSE 'configured' END,
            'inference_only', NEW.capabilities,
            jsonb_build_object(
                'provider', NEW.provider,
                'model_name', NEW.model_name,
                'endpoint_type', NEW.endpoint_type,
                'configuration_format', 'json_object'
            ),
            jsonb_build_object(
                'requires_api_key', NEW.requires_api_key,
                'secret_ref_configured', coalesce(NEW.secret_ref, '') <> '',
                'secret_storage_policy', 'reference_only_never_raw'
            ),
            jsonb_build_object(
                'route_name', NEW.route_name,
                'context_window', NEW.context_window,
                'cost_tier', NEW.cost_tier,
                'deployment_target', NEW.deployment_target,
                'mapping_required', false,
                'scheduled_job_required', false
            ),
            jsonb_build_object('base_url', NEW.base_url, 'model_name', NEW.model_name),
            NEW.status NOT IN ('disabled', 'inactive', 'retired'),
            NEW.endpoint_type NOT IN ('local', 'deterministic'),
            NEW.owner_agent, NEW.notes, 'target_sync', now()
        )
        ON CONFLICT (plugin_kind, target_key) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            adapter_key = EXCLUDED.adapter_key,
            lifecycle_status = EXCLUDED.lifecycle_status,
            access_mode = EXCLUDED.access_mode,
            capabilities = EXCLUDED.capabilities,
            config_schema = EXCLUDED.config_schema,
            credential_contract = EXCLUDED.credential_contract,
            operational_contract = EXCLUDED.operational_contract,
            configuration = EXCLUDED.configuration,
            enabled = EXCLUDED.enabled,
            approval_required = EXCLUDED.approval_required,
            owner_agent = EXCLUDED.owner_agent,
            notes = EXCLUDED.notes,
            updated_at = now();
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_source_connector_plugin ON core.source_connector_profiles;
CREATE TRIGGER trg_sync_source_connector_plugin
AFTER INSERT OR UPDATE ON core.source_connector_profiles
FOR EACH ROW EXECUTE FUNCTION core.sync_integration_plugin_from_target();

DROP TRIGGER IF EXISTS trg_sync_model_endpoint_plugin ON agent.model_endpoints;
CREATE TRIGGER trg_sync_model_endpoint_plugin
AFTER INSERT OR UPDATE ON agent.model_endpoints
FOR EACH ROW EXECUTE FUNCTION core.sync_integration_plugin_from_target();

UPDATE core.source_connector_profiles SET updated_at = updated_at;
UPDATE agent.model_endpoints SET updated_at = updated_at;

CREATE OR REPLACE FUNCTION core.upsert_integration_schema_mapping(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_plugin_key TEXT := nullif(payload->>'plugin_key', '');
    v_dataset_key TEXT := nullif(payload->>'dataset_key', '');
    v_mapping_key TEXT;
    v_result JSONB;
BEGIN
    IF v_plugin_key IS NULL OR NOT EXISTS (
        SELECT 1 FROM core.integration_plugins WHERE plugin_key = v_plugin_key AND plugin_kind = 'data_source'
    ) THEN
        RAISE EXCEPTION 'an existing data_source plugin_key is required';
    END IF;
    IF v_dataset_key IS NULL OR nullif(payload->>'target_relation', '') IS NULL THEN
        RAISE EXCEPTION 'dataset_key and target_relation are required';
    END IF;
    IF core.jsonb_contains_raw_secret(coalesce(payload->'source_schema', '{}'::jsonb))
       OR core.jsonb_contains_raw_secret(coalesce(payload->'field_mappings', '{}'::jsonb))
       OR core.jsonb_contains_raw_secret(coalesce(payload->'transformations', '[]'::jsonb)) THEN
        RAISE EXCEPTION 'raw secrets are forbidden; use connector secret_ref configuration';
    END IF;
    v_mapping_key := coalesce(nullif(payload->>'mapping_key', ''),
        lower(regexp_replace(v_plugin_key || '_' || v_dataset_key, '[^a-zA-Z0-9]+', '_', 'g')));

    INSERT INTO core.integration_schema_mappings (
        mapping_key, plugin_key, dataset_key, target_relation, source_schema,
        field_mappings, transformations, primary_key_fields, timestamp_field,
        schema_version, status, owner_agent, notes, created_by, updated_at
    ) VALUES (
        v_mapping_key, v_plugin_key, v_dataset_key, payload->>'target_relation',
        coalesce(payload->'source_schema', '{}'::jsonb),
        coalesce(payload->'field_mappings', '{}'::jsonb),
        coalesce(payload->'transformations', '[]'::jsonb),
        coalesce(ARRAY(SELECT jsonb_array_elements_text(payload->'primary_key_fields')), ARRAY[]::TEXT[]),
        nullif(payload->>'timestamp_field', ''), coalesce(nullif(payload->>'schema_version', ''), '1'),
        coalesce(nullif(payload->>'status', ''), 'configured'),
        coalesce(nullif(payload->>'owner_agent', ''), 'Data Steward'),
        nullif(payload->>'notes', ''), coalesce(nullif(payload->>'created_by', ''), 'Jarvis'), now()
    )
    ON CONFLICT (mapping_key) DO UPDATE SET
        plugin_key = EXCLUDED.plugin_key, dataset_key = EXCLUDED.dataset_key,
        target_relation = EXCLUDED.target_relation, source_schema = EXCLUDED.source_schema,
        field_mappings = EXCLUDED.field_mappings, transformations = EXCLUDED.transformations,
        primary_key_fields = EXCLUDED.primary_key_fields, timestamp_field = EXCLUDED.timestamp_field,
        schema_version = EXCLUDED.schema_version, status = EXCLUDED.status,
        validation_status = 'not_checked', validation_errors = '{}', last_validated_at = NULL,
        owner_agent = EXCLUDED.owner_agent, notes = EXCLUDED.notes, updated_at = now()
    RETURNING to_jsonb(core.integration_schema_mappings.*) INTO v_result;
    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION core.validate_integration_schema_mapping(
    p_mapping_key TEXT,
    p_actor TEXT DEFAULT 'Data Steward'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    mapping core.integration_schema_mappings%ROWTYPE;
    v_errors TEXT[] := '{}';
    v_result JSONB;
BEGIN
    SELECT * INTO mapping FROM core.integration_schema_mappings WHERE mapping_key = p_mapping_key;
    IF NOT FOUND THEN RAISE EXCEPTION 'mapping not found: %', p_mapping_key; END IF;
    IF to_regclass(mapping.target_relation) IS NULL THEN
        v_errors := array_append(v_errors, 'target relation does not exist: ' || mapping.target_relation);
    END IF;
    IF mapping.field_mappings = '{}'::jsonb THEN
        v_errors := array_append(v_errors, 'field_mappings must define at least one source-to-target field');
    END IF;
    IF cardinality(mapping.primary_key_fields) = 0 THEN
        v_errors := array_append(v_errors, 'primary_key_fields must define the idempotency contract');
    END IF;
    UPDATE core.integration_schema_mappings
    SET validation_status = CASE WHEN cardinality(v_errors) = 0 THEN 'passed' ELSE 'failed' END,
        validation_errors = v_errors, last_validated_at = now(),
        status = CASE WHEN cardinality(v_errors) = 0 AND status = 'configured' THEN 'active' ELSE status END,
        notes = concat_ws(' | ', notes, 'validated by ' || coalesce(nullif(p_actor, ''), 'Data Steward')),
        updated_at = now()
    WHERE mapping_key = p_mapping_key
    RETURNING to_jsonb(core.integration_schema_mappings.*) INTO v_result;
    RETURN v_result;
END;
$$;

CREATE OR REPLACE FUNCTION core.upsert_integration_job(payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_plugin_key TEXT := nullif(payload->>'plugin_key', '');
    v_job_key TEXT;
    v_result JSONB;
BEGIN
    IF v_plugin_key IS NULL OR NOT EXISTS (SELECT 1 FROM core.integration_plugins WHERE plugin_key = v_plugin_key) THEN
        RAISE EXCEPTION 'an existing plugin_key is required';
    END IF;
    IF nullif(payload->>'executor_key', '') IS NULL THEN RAISE EXCEPTION 'executor_key is required'; END IF;
    IF core.jsonb_contains_raw_secret(coalesce(payload->'parameters', '{}'::jsonb)) THEN
        RAISE EXCEPTION 'raw secrets are forbidden; use connector secret_ref configuration';
    END IF;
    v_job_key := coalesce(nullif(payload->>'job_key', ''),
        lower(regexp_replace(v_plugin_key || '_' || coalesce(payload->>'job_type', 'poll'), '[^a-zA-Z0-9]+', '_', 'g')));
    INSERT INTO core.integration_jobs (
        job_key, plugin_key, job_name, job_type, executor_key, schedule_cron,
        timezone, enabled, run_mode, overlap_policy, timeout_seconds,
        parameters, approval_required, owner_agent, notes, created_by, updated_at
    ) VALUES (
        v_job_key, v_plugin_key, coalesce(nullif(payload->>'job_name', ''), v_job_key),
        coalesce(nullif(payload->>'job_type', ''), 'poll'), payload->>'executor_key',
        nullif(payload->>'schedule_cron', ''), coalesce(nullif(payload->>'timezone', ''), 'Asia/Kolkata'),
        coalesce((payload->>'enabled')::BOOLEAN, false),
        coalesce(nullif(payload->>'run_mode', ''), 'manual_or_schedule'),
        coalesce(nullif(payload->>'overlap_policy', ''), 'skip'),
        coalesce(nullif(payload->>'timeout_seconds', '')::INTEGER, 300),
        coalesce(payload->'parameters', '{}'::jsonb),
        coalesce((payload->>'approval_required')::BOOLEAN, false),
        coalesce(nullif(payload->>'owner_agent', ''), 'Data Engineering Agent'),
        nullif(payload->>'notes', ''), coalesce(nullif(payload->>'created_by', ''), 'Jarvis'), now()
    )
    ON CONFLICT (job_key) DO UPDATE SET
        plugin_key = EXCLUDED.plugin_key, job_name = EXCLUDED.job_name,
        job_type = EXCLUDED.job_type, executor_key = EXCLUDED.executor_key,
        schedule_cron = EXCLUDED.schedule_cron, timezone = EXCLUDED.timezone,
        enabled = EXCLUDED.enabled, run_mode = EXCLUDED.run_mode,
        overlap_policy = EXCLUDED.overlap_policy, timeout_seconds = EXCLUDED.timeout_seconds,
        parameters = EXCLUDED.parameters, approval_required = EXCLUDED.approval_required,
        owner_agent = EXCLUDED.owner_agent, notes = EXCLUDED.notes, updated_at = now()
    RETURNING to_jsonb(core.integration_jobs.*) INTO v_result;
    RETURN v_result;
END;
$$;

DROP VIEW IF EXISTS core.v_integration_plugin_summary;
DROP VIEW IF EXISTS core.v_integration_plugin_gateway;

CREATE VIEW core.v_integration_plugin_gateway AS
SELECT
    plugin.id, plugin.plugin_key, plugin.plugin_kind, plugin.target_key,
    plugin.display_name, plugin.adapter_key, plugin.adapter_version,
    plugin.lifecycle_status, plugin.access_mode, plugin.capabilities,
    plugin.config_schema, plugin.credential_contract, plugin.operational_contract,
    plugin.configuration, plugin.enabled, plugin.approval_required,
    plugin.owner_agent, plugin.notes,
    coalesce(source.provider, endpoint.provider) AS provider,
    source.source_key,
    source.source_name,
    source.source_type,
    source.connector_type,
    endpoint.model_name,
    endpoint.route_name,
    endpoint.endpoint_type,
    coalesce(source.health_status, endpoint.health_status, 'unchecked') AS health_status,
    coalesce(source.last_checked_at, endpoint.last_checked_at) AS last_checked_at,
    coalesce(source.last_error, endpoint.last_error) AS last_error,
    freshness.status AS freshness_status,
    freshness.severity AS freshness_severity,
    freshness.staleness_minutes,
    freshness.rows_seen AS freshness_rows_seen,
    coalesce(readiness.readiness_status, 'not_evaluated') AS provider_readiness_status,
    coalesce(readiness.assignable, false) AS provider_assignable,
    coalesce(readiness.next_action, 'Run provider readiness check.') AS provider_next_action,
    coalesce(mappings.mapping_count, 0) AS mapping_count,
    coalesce(mappings.valid_mapping_count, 0) AS valid_mapping_count,
    coalesce(jobs.job_count, 0) AS job_count,
    coalesce(jobs.enabled_job_count, 0) AS enabled_job_count,
    coalesce(routes.route_count, 0) AS route_count,
    CASE
        WHEN NOT plugin.enabled OR plugin.lifecycle_status IN ('disabled', 'retired') THEN 'disabled'
        WHEN coalesce((plugin.credential_contract->>'requires_api_key')::BOOLEAN, false)
             AND NOT coalesce((plugin.credential_contract->>'secret_ref_configured')::BOOLEAN, false) THEN 'needs_credentials'
        WHEN plugin.plugin_kind = 'model_provider' AND NOT coalesce(readiness.assignable, false) THEN 'needs_provider_readiness'
        WHEN plugin.plugin_kind = 'model_provider' AND coalesce(routes.route_count, 0) = 0 THEN 'needs_route'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce(source.health_status, 'unchecked') NOT IN ('configured', 'active', 'healthy', 'ok') THEN 'needs_health_check'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'freshness_target_minutes')::INTEGER, 0) > 0
             AND coalesce(freshness.severity, 'low') IN ('high', 'critical') THEN 'needs_freshness'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'mapping_required')::BOOLEAN, false)
             AND coalesce(mappings.valid_mapping_count, 0) = 0 THEN 'needs_mapping'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'scheduled_job_required')::BOOLEAN, false)
             AND coalesce(jobs.enabled_job_count, 0) = 0 THEN 'needs_schedule'
        ELSE 'ready'
    END AS gateway_status,
    CASE
        WHEN NOT plugin.enabled OR plugin.lifecycle_status IN ('disabled', 'retired') THEN 'Enable the plug-in after review.'
        WHEN coalesce((plugin.credential_contract->>'requires_api_key')::BOOLEAN, false)
             AND NOT coalesce((plugin.credential_contract->>'secret_ref_configured')::BOOLEAN, false) THEN 'Add a secret reference; never store the raw credential.'
        WHEN plugin.plugin_kind = 'model_provider' AND NOT coalesce(readiness.assignable, false) THEN coalesce(readiness.next_action, 'Run provider readiness check.')
        WHEN plugin.plugin_kind = 'model_provider' AND coalesce(routes.route_count, 0) = 0 THEN 'Assign the endpoint to an approved model route.'
        WHEN plugin.plugin_kind = 'data_source' AND coalesce(source.health_status, 'unchecked') NOT IN ('configured', 'active', 'healthy', 'ok') THEN 'Run the connector health check and resolve its configuration.'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'freshness_target_minutes')::INTEGER, 0) > 0
             AND coalesce(freshness.severity, 'low') IN ('high', 'critical') THEN 'Restore the source freshness SLA before assignment.'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'mapping_required')::BOOLEAN, false)
             AND coalesce(mappings.valid_mapping_count, 0) = 0 THEN 'Define and validate a warehouse schema mapping.'
        WHEN plugin.plugin_kind = 'data_source'
             AND coalesce((plugin.operational_contract->>'scheduled_job_required')::BOOLEAN, false)
             AND coalesce(jobs.enabled_job_count, 0) = 0 THEN 'Configure and enable a bounded ingestion schedule.'
        ELSE 'Ready for role-scoped assignment.'
    END AS next_required_action,
    plugin.created_at, plugin.updated_at
FROM core.integration_plugins plugin
LEFT JOIN core.v_source_connector_control source
  ON plugin.plugin_kind = 'data_source' AND source.connector_key = plugin.target_key
LEFT JOIN agent.model_endpoints endpoint
  ON plugin.plugin_kind = 'model_provider' AND endpoint.endpoint_key = plugin.target_key
LEFT JOIN core.v_latest_data_source_freshness freshness
  ON plugin.plugin_kind = 'data_source' AND freshness.source_key = source.source_key
LEFT JOIN core.v_provider_readiness_board readiness
  ON readiness.provider_kind = CASE WHEN plugin.plugin_kind = 'data_source' THEN 'data_source_connector' ELSE 'model_endpoint' END
 AND readiness.provider_key = plugin.target_key
LEFT JOIN LATERAL (
    SELECT count(*) AS mapping_count,
           count(*) FILTER (WHERE validation_status = 'passed' AND status = 'active') AS valid_mapping_count
    FROM core.integration_schema_mappings mapping
    WHERE mapping.plugin_key = plugin.plugin_key
) mappings ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS job_count,
           count(*) FILTER (WHERE enabled) AS enabled_job_count
    FROM core.integration_jobs job
    WHERE job.plugin_key = plugin.plugin_key
) jobs ON true
LEFT JOIN LATERAL (
    SELECT count(*) AS route_count
    FROM agent.model_routes route
    WHERE plugin.plugin_kind = 'model_provider'
      AND endpoint.route_name = route.route_name
      AND route.enabled
) routes ON true;

CREATE VIEW core.v_integration_plugin_summary AS
SELECT 'total_plugins'::TEXT AS metric, count(*)::BIGINT AS value, 'All source and model plug-ins.'::TEXT AS interpretation
FROM core.v_integration_plugin_gateway
UNION ALL SELECT 'data_source_plugins', count(*), 'Registered data-source adapters.' FROM core.v_integration_plugin_gateway WHERE plugin_kind = 'data_source'
UNION ALL SELECT 'model_provider_plugins', count(*), 'Registered model-provider adapters.' FROM core.v_integration_plugin_gateway WHERE plugin_kind = 'model_provider'
UNION ALL SELECT 'ready_plugins', count(*), 'Plug-ins with credentials, health, mappings/jobs or routes ready.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'ready'
UNION ALL SELECT 'needs_credentials', count(*), 'Plug-ins requiring a credential reference.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'needs_credentials'
UNION ALL SELECT 'needs_mapping', count(*), 'Data plug-ins missing a validated warehouse mapping.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'needs_mapping'
UNION ALL SELECT 'needs_schedule', count(*), 'Recurring data plug-ins missing an enabled bounded job.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'needs_schedule'
UNION ALL SELECT 'needs_freshness', count(*), 'Data plug-ins outside the current source-freshness SLA.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'needs_freshness'
UNION ALL SELECT 'needs_provider_readiness', count(*), 'Model endpoints not currently assignable.' FROM core.v_integration_plugin_gateway WHERE gateway_status = 'needs_provider_readiness';

CREATE OR REPLACE VIEW core.v_integration_schema_mapping_board AS
SELECT mapping.*, plugin.display_name AS plugin_name, plugin.target_key,
       to_regclass(mapping.target_relation) IS NOT NULL AS target_relation_exists
FROM core.integration_schema_mappings mapping
JOIN core.integration_plugins plugin ON plugin.plugin_key = mapping.plugin_key;

CREATE OR REPLACE VIEW core.v_integration_job_board AS
SELECT job.*, plugin.display_name AS plugin_name, plugin.plugin_kind,
       latest.run_key AS latest_run_key, latest.status AS latest_run_status,
       latest.rows_written AS latest_run_rows_written,
       latest.error_message AS latest_run_error,
       latest.started_at AS latest_run_started_at,
       latest.finished_at AS latest_run_finished_at
FROM core.integration_jobs job
JOIN core.integration_plugins plugin ON plugin.plugin_key = job.plugin_key
LEFT JOIN LATERAL (
    SELECT run.* FROM core.integration_job_runs run
    WHERE run.job_key = job.job_key
    ORDER BY run.created_at DESC LIMIT 1
) latest ON true;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
('ai_os_integration_plugin_gateway', 'mcp_tool', 'Integration Engineer', 'read_only', true,
 'Read source/model plug-in readiness, schemas, schedules, routes, and credential-reference gates.',
 '{"reads":["core.v_integration_plugin_gateway","core.v_integration_plugin_summary"],"raw_secrets_allowed":false}'::jsonb),
('ai_os_upsert_integration_schema_mapping', 'mcp_tool', 'Data Steward', 'write_with_approval', true,
 'Create or update a source-to-warehouse schema mapping without storing credentials.',
 '{"writes":["core.integration_schema_mappings"],"raw_secrets_allowed":false}'::jsonb),
('ai_os_validate_integration_schema_mapping', 'mcp_tool', 'Data Quality Agent', 'write_with_approval', true,
 'Validate target relation, field map, and idempotency key contract for an integration mapping.',
 '{"writes":["core.integration_schema_mappings"],"raw_secrets_allowed":false}'::jsonb),
('ai_os_upsert_integration_job', 'mcp_tool', 'Data Engineering Agent', 'write_with_approval', true,
 'Configure a bounded allowlisted ingestion or provider job.',
 '{"writes":["core.integration_jobs"],"arbitrary_commands_allowed":false,"raw_secrets_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO ops.workspace_layouts (
    profile_id, workspace_key, module_order, hidden_modules,
    column_count, settings, updated_by
)
SELECT id, 'models',
       '["plugin_summary","register_source","register_model","plugin_board","schema_mappings","ingestion_jobs","model_routes","readiness"]'::jsonb,
       '[]'::jsonb, 2,
       '{"show_evidence":true,"show_freshness":true,"raw_secrets_allowed":false,"execution_lock_visible":true}'::jsonb,
       'Codex'
FROM ops.workspace_profiles WHERE profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO UPDATE SET
    module_order = EXCLUDED.module_order,
    settings = ops.workspace_layouts.settings || EXCLUDED.settings,
    updated_by = EXCLUDED.updated_by,
    updated_at = now();

UPDATE core.source_connector_profiles
SET status = 'active',
    health_status = 'active',
    last_checked_at = now(),
    last_rows_seen = (SELECT count(*) FROM market.news_items),
    last_error = NULL,
    updated_at = now()
WHERE connector_key = 'global_news_connector'
  AND EXISTS (SELECT 1 FROM market.news_items);

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'global_news_to_market_news_items_v1',
    'plugin_key', 'data_source:global_news_connector',
    'dataset_key', 'market_news_items',
    'target_relation', 'market.news_items',
    'source_schema', jsonb_build_object('collector', 'scripts/ingest_market_news.py', 'format', 'rss_atom_http'),
    'field_mappings', jsonb_build_object(
        'source_name', 'source_name', 'source_url', 'source_url', 'title', 'title',
        'publisher', 'publisher', 'published_at', 'published_at', 'symbols', 'symbols',
        'topics', 'topics', 'geography', 'geography', 'raw_payload', 'raw_payload'
    ),
    'primary_key_fields', jsonb_build_array('source_url'),
    'timestamp_field', 'published_at', 'status', 'configured',
    'owner_agent', 'News Data Engineer', 'created_by', 'Codex',
    'notes', 'Existing source-backed RSS/HTTP collector contract.'
));
SELECT core.validate_integration_schema_mapping('global_news_to_market_news_items_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'nse_filings_to_corporate_filings_v1',
    'plugin_key', 'data_source:nse_filings_connector',
    'dataset_key', 'nse_corporate_filings',
    'target_relation', 'research.corporate_filings',
    'source_schema', jsonb_build_object('collector', 'scripts/collect_nse_bse_filings.py', 'source', 'nse'),
    'field_mappings', jsonb_build_object(
        'exchange', 'exchange', 'symbol', 'symbol', 'company_name', 'company_name',
        'filing_type', 'filing_type', 'event_type', 'event_type', 'title', 'title',
        'filed_at', 'filed_at', 'source_url', 'source_url', 'payload', 'payload'
    ),
    'primary_key_fields', jsonb_build_array('exchange', 'source_url'),
    'timestamp_field', 'filed_at', 'status', 'configured',
    'owner_agent', 'Filings Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('nse_filings_to_corporate_filings_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'bse_filings_to_corporate_filings_v1',
    'plugin_key', 'data_source:bse_filings_connector',
    'dataset_key', 'bse_corporate_filings',
    'target_relation', 'research.corporate_filings',
    'source_schema', jsonb_build_object('collector', 'scripts/collect_nse_bse_filings.py', 'source', 'bse'),
    'field_mappings', jsonb_build_object(
        'exchange', 'exchange', 'symbol', 'symbol', 'company_name', 'company_name',
        'filing_type', 'filing_type', 'event_type', 'event_type', 'title', 'title',
        'filed_at', 'filed_at', 'source_url', 'source_url', 'payload', 'payload'
    ),
    'primary_key_fields', jsonb_build_array('exchange', 'source_url'),
    'timestamp_field', 'filed_at', 'status', 'configured',
    'owner_agent', 'Filings Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('bse_filings_to_corporate_filings_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'tick_aggregation_to_ohlcv_v1',
    'plugin_key', 'data_source:tick_ohlcv_aggregation_connector',
    'dataset_key', 'market_ohlcv',
    'target_relation', 'trading.ohlcv',
    'source_schema', jsonb_build_object('aggregator', 'scripts/aggregate_ticks_to_ohlcv.py', 'source_relation', 'trading.ticks'),
    'field_mappings', jsonb_build_object(
        'ts', 'ts', 'symbol_id', 'symbol_id', 'timeframe', 'timeframe',
        'open', 'open', 'high', 'high', 'low', 'low', 'close', 'close',
        'volume', 'volume', 'source_system_id', 'source_system_id'
    ),
    'primary_key_fields', jsonb_build_array('ts', 'symbol_id', 'timeframe'),
    'timestamp_field', 'ts', 'status', 'configured',
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('tick_aggregation_to_ohlcv_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'tradingview_scanner_to_price_quotes_v1',
    'plugin_key', 'data_source:tradingview_scanner_quotes_connector',
    'dataset_key', 'market_price_quotes',
    'target_relation', 'market.price_quotes',
    'source_schema', jsonb_build_object('provider', 'TradingView', 'mode', 'http_read_only'),
    'field_mappings', jsonb_build_object(
        'provider_symbol', 'provider_symbol', 'symbol', 'symbol', 'exchange', 'exchange',
        'currency', 'currency', 'price', 'price', 'change_percent', 'change_percent',
        'quote_ts', 'quote_ts', 'raw_payload', 'raw_payload'
    ),
    'primary_key_fields', jsonb_build_array('provider', 'provider_symbol', 'quote_ts'),
    'timestamp_field', 'quote_ts', 'status', 'configured',
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('tradingview_scanner_to_price_quotes_v1', 'Data Quality Agent');

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'global_news_hourly_ingestion',
    'plugin_key', 'data_source:global_news_connector',
    'job_name', 'Global news ingestion', 'job_type', 'poll',
    'executor_key', 'market_news_ingestion', 'schedule_cron', '0 * * * *',
    'enabled', true, 'run_mode', 'daemon', 'timeout_seconds', 180,
    'parameters', jsonb_build_object('feed_limit', 12, 'per_feed', 8),
    'owner_agent', 'News Data Engineer', 'created_by', 'Codex',
    'notes', 'Executed by the hourly strategy-discovery scheduler.'
));

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'nse_filings_hourly_collection',
    'plugin_key', 'data_source:nse_filings_connector',
    'job_name', 'NSE filing collection', 'job_type', 'poll',
    'executor_key', 'filings_collection', 'schedule_cron', '5 * * * *',
    'enabled', true, 'run_mode', 'daemon', 'timeout_seconds', 300,
    'parameters', jsonb_build_object('source', 'nse', 'limit', 100),
    'owner_agent', 'Filings Data Engineer', 'created_by', 'Codex',
    'notes', 'Executed inside the source-backed research scheduler.'
));

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'bse_filings_hourly_collection',
    'plugin_key', 'data_source:bse_filings_connector',
    'job_name', 'BSE filing collection', 'job_type', 'poll',
    'executor_key', 'filings_collection', 'schedule_cron', '10 * * * *',
    'enabled', true, 'run_mode', 'daemon', 'timeout_seconds', 300,
    'parameters', jsonb_build_object('source', 'bse', 'limit', 100),
    'owner_agent', 'Filings Data Engineer', 'created_by', 'Codex',
    'notes', 'Executed inside the source-backed research scheduler.'
));

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'tick_to_ohlcv_five_minute_aggregation',
    'plugin_key', 'data_source:tick_ohlcv_aggregation_connector',
    'job_name', 'Tick to OHLCV aggregation', 'job_type', 'aggregate',
    'executor_key', 'tick_ohlcv_aggregation', 'schedule_cron', '*/5 * * * *',
    'enabled', true, 'run_mode', 'daemon', 'timeout_seconds', 120,
    'parameters', jsonb_build_object('source_relation', 'trading.ticks', 'target_relation', 'trading.ohlcv'),
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex',
    'notes', 'Executed by the live agent daemon at a 300 second interval.'
));

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'tradingview_portfolio_quotes_fifteen_minute_refresh',
    'plugin_key', 'data_source:tradingview_scanner_quotes_connector',
    'job_name', 'TradingView portfolio quote refresh', 'job_type', 'poll',
    'executor_key', 'tradingview_quote_refresh', 'schedule_cron', '*/15 * * * *',
    'enabled', true, 'run_mode', 'daemon', 'timeout_seconds', 120,
    'parameters', jsonb_build_object('limit', 100),
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex',
    'notes', 'Executed by the live agent daemon at a 900 second interval for portfolio and active-event symbols.'
));
