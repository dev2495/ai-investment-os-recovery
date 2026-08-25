BEGIN;

-- Research Desk v1 / milestone 7.
-- Fundamental scanner factory only. Seeded scanners are non-executable drafts;
-- this migration runs no scanner, creates no alert, and touches no broker data.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS core.schema_migrations (
    migration_number INTEGER PRIMARY KEY,
    migration_key TEXT NOT NULL UNIQUE,
    definition_checksum_sha256 TEXT NOT NULL,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by TEXT NOT NULL DEFAULT current_user,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT schema_migrations_positive_number CHECK (migration_number > 0),
    CONSTRAINT schema_migrations_checksum_shape CHECK (definition_checksum_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT schema_migrations_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_os_research_runtime') THEN
        EXECUTE 'CREATE ROLE ai_os_research_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT';
    END IF;
END
$role$;

CREATE OR REPLACE FUNCTION core.ai_os_scope_key()
RETURNS TEXT
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $fn$
    SELECT COALESCE(NULLIF(current_setting('ai_os.scope_key', true), ''), '__deny__')
$fn$;

GRANT USAGE ON SCHEMA core, market TO ai_os_research_runtime;
GRANT EXECUTE ON FUNCTION core.ai_os_scope_key() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION market.scanner_dsl_is_safe(payload JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
AS $fn$
DECLARE
    item RECORD;
    element JSONB;
    normalized_key TEXT;
    op_value TEXT;
BEGIN
    IF payload IS NULL THEN
        RETURN false;
    END IF;
    IF core.jsonb_contains_raw_secret(payload) THEN
        RETURN false;
    END IF;

    CASE jsonb_typeof(payload)
        WHEN 'object' THEN
            FOR item IN SELECT key, value FROM jsonb_each(payload)
            LOOP
                normalized_key := lower(regexp_replace(item.key, '[^a-z0-9]+', '_', 'g'));
                IF normalized_key IN (
                    'sql', 'query', 'raw_query', 'python', 'code', 'script',
                    'command', 'shell', 'raw_expression', 'eval', 'exec'
                ) THEN
                    RETURN false;
                END IF;
                IF normalized_key = 'op' THEN
                    IF jsonb_typeof(item.value) <> 'string' THEN
                        RETURN false;
                    END IF;
                    op_value := trim(both '"' from item.value::text);
                    IF op_value NOT IN (
                        'and', 'or', 'not', 'eq', 'neq', 'gt', 'gte', 'lt', 'lte',
                        'between', 'in', 'not_in', 'is_missing', 'is_present',
                        'add', 'sub', 'mul', 'div', 'min', 'max', 'coalesce',
                        'rank', 'zscore', 'percentile'
                    ) THEN
                        RETURN false;
                    END IF;
                END IF;
                IF NOT market.scanner_dsl_is_safe(item.value) THEN
                    RETURN false;
                END IF;
            END LOOP;
        WHEN 'array' THEN
            FOR element IN SELECT value FROM jsonb_array_elements(payload)
            LOOP
                IF NOT market.scanner_dsl_is_safe(element) THEN
                    RETURN false;
                END IF;
            END LOOP;
        ELSE
            RETURN true;
    END CASE;
    RETURN true;
END
$fn$;

CREATE TABLE IF NOT EXISTS market.scanner_definitions (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    scanner_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    current_published_version_id BIGINT,
    tags TEXT[] NOT NULL DEFAULT '{}'::text[],
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_definitions_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_definitions_scope_key UNIQUE (scope_key, scanner_key),
    CONSTRAINT chk_scanner_definitions_status CHECK (status IN ('draft', 'active', 'paused', 'retired')),
    CONSTRAINT chk_scanner_definitions_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE TABLE IF NOT EXISTS market.scanner_metric_definitions (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    version INTEGER NOT NULL,
    label TEXT NOT NULL,
    value_type TEXT NOT NULL,
    unit TEXT,
    implementation_key TEXT NOT NULL,
    formula_definition_id BIGINT REFERENCES research.financial_formula_definitions(id) ON DELETE RESTRICT,
    source_kind TEXT NOT NULL,
    point_in_time_required BOOLEAN NOT NULL DEFAULT true,
    required_history_periods INTEGER NOT NULL DEFAULT 1,
    required_lag_days INTEGER NOT NULL DEFAULT 0,
    sector_applicability JSONB NOT NULL DEFAULT '{}'::jsonb,
    exclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
    definition_hash TEXT NOT NULL,
    code_revision TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_metric_definitions_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_metric_definitions_key_version UNIQUE (scope_key, metric_key, version),
    CONSTRAINT chk_scanner_metric_definitions_version CHECK (version > 0),
    CONSTRAINT chk_scanner_metric_definitions_value_type CHECK (value_type IN ('numeric', 'boolean', 'text', 'date')),
    CONSTRAINT chk_scanner_metric_definitions_source CHECK (source_kind IN ('statement_fact', 'ratio', 'price_quote', 'governance', 'filing', 'universe')),
    CONSTRAINT chk_scanner_metric_definitions_history CHECK (required_history_periods > 0 AND required_lag_days >= 0),
    CONSTRAINT chk_scanner_metric_definitions_hash CHECK (definition_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_metric_definitions_status CHECK (status IN ('draft', 'active', 'retired')),
    CONSTRAINT chk_scanner_metric_definitions_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(sector_applicability)
        AND NOT core.jsonb_contains_raw_secret(exclusions)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_scanner_metric_definitions_active
    ON market.scanner_metric_definitions (scope_key, metric_key)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS market.scanner_versions (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    scanner_definition_id BIGINT NOT NULL,
    version INTEGER NOT NULL,
    api_version TEXT NOT NULL DEFAULT 'v1',
    dsl_version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'draft',
    definition_json JSONB NOT NULL,
    definition_hash TEXT NOT NULL,
    universe_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    filter_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    score_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculation_revision TEXT NOT NULL,
    source_request_text TEXT,
    created_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    model_usage_event_id BIGINT REFERENCES agent.model_usage_events(id) ON DELETE SET NULL,
    publish_approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE RESTRICT,
    published_at TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_versions_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_versions_definition_id UNIQUE (scope_key, scanner_definition_id, id),
    CONSTRAINT uq_scanner_versions_number UNIQUE (scope_key, scanner_definition_id, version),
    CONSTRAINT uq_scanner_versions_hash UNIQUE (scope_key, scanner_definition_id, definition_hash),
    CONSTRAINT fk_scanner_versions_definition_scope FOREIGN KEY (scope_key, scanner_definition_id)
        REFERENCES market.scanner_definitions(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_scanner_versions_positive CHECK (version > 0),
    CONSTRAINT chk_scanner_versions_status CHECK (status IN ('draft', 'validated', 'published', 'retired', 'rejected')),
    CONSTRAINT chk_scanner_versions_hash CHECK (definition_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_versions_safe_dsl CHECK (market.scanner_dsl_is_safe(definition_json)),
    CONSTRAINT chk_scanner_versions_publish_fields CHECK (
        status <> 'published' OR (publish_approval_id IS NOT NULL AND published_at IS NOT NULL)
    ),
    CONSTRAINT chk_scanner_versions_retired_fields CHECK (
        status <> 'retired' OR retired_at IS NOT NULL
    ),
    CONSTRAINT chk_scanner_versions_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(universe_config)
        AND NOT core.jsonb_contains_raw_secret(filter_config)
        AND NOT core.jsonb_contains_raw_secret(score_config)
        AND NOT core.jsonb_contains_raw_secret(output_config)
    )
);

DO $current_version_fk$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'market.scanner_definitions'::regclass
          AND conname = 'scanner_definitions_current_version_scope_fkey'
    ) THEN
        ALTER TABLE market.scanner_definitions
            ADD CONSTRAINT scanner_definitions_current_version_scope_fkey
            FOREIGN KEY (scope_key, current_published_version_id)
            REFERENCES market.scanner_versions(scope_key, id)
            ON DELETE SET NULL (current_published_version_id);
    END IF;
END
$current_version_fk$;

CREATE TABLE IF NOT EXISTS market.scanner_validations (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    validation_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    scanner_version_id BIGINT NOT NULL,
    validation_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    as_of_date DATE,
    date_range_start DATE,
    date_range_end DATE,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE RESTRICT,
    artifact_hash TEXT,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    model_usage_event_id BIGINT REFERENCES agent.model_usage_events(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_validations_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_validations_key UNIQUE (scope_key, validation_key),
    CONSTRAINT uq_scanner_validations_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_scanner_validations_version_scope FOREIGN KEY (scope_key, scanner_version_id)
        REFERENCES market.scanner_versions(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_scanner_validations_kind CHECK (validation_kind IN (
        'schema', 'metric_availability', 'duplicate_filters', 'point_in_time',
        'survivor_bias', 'sector_bias', 'turnover', 'missing_sensitivity',
        'rank_stability', 'known_fixture', 'historical_replay'
    )),
    CONSTRAINT chk_scanner_validations_status CHECK (status IN ('queued', 'running', 'passed', 'warning', 'failed', 'cancelled')),
    CONSTRAINT chk_scanner_validations_dates CHECK (date_range_end IS NULL OR date_range_start IS NULL OR date_range_end >= date_range_start),
    CONSTRAINT chk_scanner_validations_time CHECK (completed_at IS NULL OR completed_at >= started_at),
    CONSTRAINT chk_scanner_validations_hash CHECK (artifact_hash IS NULL OR artifact_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_validations_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(report)
        AND NOT core.jsonb_contains_raw_secret(coverage)
    )
);

CREATE INDEX IF NOT EXISTS idx_scanner_validations_version
    ON market.scanner_validations (scope_key, scanner_version_id, status, validation_kind, created_at DESC);

CREATE TABLE IF NOT EXISTS market.scanner_schedules (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    schedule_key TEXT NOT NULL,
    scanner_version_id BIGINT NOT NULL,
    workflow_schedule_key TEXT REFERENCES agent.workflow_schedules(schedule_key) ON DELETE RESTRICT,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    enabled BOOLEAN NOT NULL DEFAULT false,
    publish_approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE RESTRICT,
    alert_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_schedules_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_schedules_key UNIQUE (scope_key, schedule_key),
    CONSTRAINT fk_scanner_schedules_version_scope FOREIGN KEY (scope_key, scanner_version_id)
        REFERENCES market.scanner_versions(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT chk_scanner_schedules_enabled_gate CHECK (
        NOT enabled OR (workflow_schedule_key IS NOT NULL AND publish_approval_id IS NOT NULL)
    ),
    CONSTRAINT chk_scanner_schedules_time CHECK (next_run_at IS NULL OR last_run_at IS NULL OR next_run_at >= last_run_at),
    CONSTRAINT chk_scanner_schedules_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(alert_config))
);

CREATE INDEX IF NOT EXISTS idx_scanner_schedules_due
    ON market.scanner_schedules (scope_key, enabled, next_run_at)
    WHERE enabled;

CREATE TABLE IF NOT EXISTS market.scanner_runs (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    run_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    scanner_version_id BIGINT NOT NULL,
    as_of_date DATE NOT NULL,
    as_of_cutoff_at TIMESTAMPTZ NOT NULL,
    universe_key TEXT NOT NULL,
    universe_hash TEXT NOT NULL,
    engine_revision TEXT NOT NULL,
    code_revision TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    total_symbols INTEGER NOT NULL DEFAULT 0,
    eligible_symbols INTEGER NOT NULL DEFAULT 0,
    excluded_symbols INTEGER NOT NULL DEFAULT 0,
    missing_symbols INTEGER NOT NULL DEFAULT 0,
    stale_symbols INTEGER NOT NULL DEFAULT 0,
    provider_failure_count INTEGER NOT NULL DEFAULT 0,
    coverage_report JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    model_usage_event_id BIGINT REFERENCES agent.model_usage_events(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_runs_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_runs_key UNIQUE (scope_key, run_key),
    CONSTRAINT uq_scanner_runs_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT uq_scanner_runs_deterministic UNIQUE (scope_key, scanner_version_id, as_of_date, universe_hash, engine_revision),
    CONSTRAINT fk_scanner_runs_version_scope FOREIGN KEY (scope_key, scanner_version_id)
        REFERENCES market.scanner_versions(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT chk_scanner_runs_hash CHECK (universe_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_runs_status CHECK (status IN ('queued', 'running', 'completed', 'partial', 'failed', 'cancelled')),
    CONSTRAINT chk_scanner_runs_counts CHECK (
        total_symbols >= 0 AND eligible_symbols >= 0 AND excluded_symbols >= 0
        AND missing_symbols >= 0 AND stale_symbols >= 0 AND provider_failure_count >= 0
        AND eligible_symbols + excluded_symbols <= total_symbols
    ),
    CONSTRAINT chk_scanner_runs_cutoff CHECK (as_of_cutoff_at::date >= as_of_date),
    CONSTRAINT chk_scanner_runs_time CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT chk_scanner_runs_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(coverage_report)
        AND NOT core.jsonb_contains_raw_secret(warnings)
    )
);

CREATE INDEX IF NOT EXISTS idx_scanner_runs_history
    ON market.scanner_runs (scope_key, scanner_version_id, as_of_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_scanner_runs_status
    ON market.scanner_runs (scope_key, status, started_at DESC);

CREATE TABLE IF NOT EXISTS market.scanner_run_universe (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    scanner_run_id BIGINT NOT NULL,
    universe_membership_id BIGINT NOT NULL REFERENCES market.universe_memberships(id) ON DELETE RESTRICT,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE RESTRICT,
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    eligibility_status TEXT NOT NULL,
    exclusion_code TEXT,
    exclusion_reason TEXT,
    data_completeness NUMERIC(5,4),
    data_cutoff_at TIMESTAMPTZ,
    provider_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_snapshot_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_run_universe_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_run_universe_symbol UNIQUE (scope_key, scanner_run_id, symbol_id),
    CONSTRAINT fk_scanner_run_universe_run_scope FOREIGN KEY (scope_key, scanner_run_id)
        REFERENCES market.scanner_runs(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_scanner_run_universe_eligibility CHECK (eligibility_status IN ('eligible', 'excluded', 'missing', 'stale', 'provider_failed')),
    CONSTRAINT chk_scanner_run_universe_exclusion CHECK (
        eligibility_status = 'eligible' OR (exclusion_code IS NOT NULL AND exclusion_reason IS NOT NULL)
    ),
    CONSTRAINT chk_scanner_run_universe_completeness CHECK (data_completeness IS NULL OR (data_completeness >= 0 AND data_completeness <= 1)),
    CONSTRAINT chk_scanner_run_universe_hash CHECK (input_snapshot_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_run_universe_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(provider_warnings))
);

CREATE INDEX IF NOT EXISTS idx_scanner_run_universe_status
    ON market.scanner_run_universe (scope_key, scanner_run_id, eligibility_status, symbol_id);

CREATE TABLE IF NOT EXISTS market.scanner_results (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    scanner_run_id BIGINT NOT NULL,
    scanner_run_universe_id BIGINT NOT NULL,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE RESTRICT,
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    rank INTEGER,
    passed BOOLEAN NOT NULL,
    score NUMERIC,
    data_completeness NUMERIC(5,4),
    reason_codes TEXT[] NOT NULL DEFAULT '{}'::text[],
    reason_summary TEXT,
    watchlist_ref TEXT,
    research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
    artifact_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_results_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_results_symbol UNIQUE (scope_key, scanner_run_id, symbol_id),
    CONSTRAINT fk_scanner_results_run_scope FOREIGN KEY (scope_key, scanner_run_id)
        REFERENCES market.scanner_runs(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_scanner_results_universe_scope FOREIGN KEY (scope_key, scanner_run_universe_id)
        REFERENCES market.scanner_run_universe(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_scanner_results_rank CHECK (rank IS NULL OR rank > 0),
    CONSTRAINT chk_scanner_results_completeness CHECK (data_completeness IS NULL OR (data_completeness >= 0 AND data_completeness <= 1)),
    CONSTRAINT chk_scanner_results_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(artifact_refs))
);

CREATE INDEX IF NOT EXISTS idx_scanner_results_rank
    ON market.scanner_results (scope_key, scanner_run_id, rank NULLS LAST, id);
CREATE INDEX IF NOT EXISTS idx_scanner_results_company
    ON market.scanner_results (scope_key, company_id, created_at DESC)
    WHERE company_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS market.scanner_result_metrics (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    scanner_result_id BIGINT NOT NULL,
    metric_definition_id BIGINT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_version INTEGER NOT NULL,
    calculation_status TEXT NOT NULL,
    value_numeric NUMERIC,
    value_text TEXT,
    unit TEXT,
    as_of_date DATE NOT NULL,
    available_at TIMESTAMPTZ,
    formula_hash TEXT,
    calculation_hash TEXT,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_result_metrics_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_result_metrics_metric UNIQUE (scope_key, scanner_result_id, metric_key, metric_version),
    CONSTRAINT fk_scanner_result_metrics_result_scope FOREIGN KEY (scope_key, scanner_result_id)
        REFERENCES market.scanner_results(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_scanner_result_metrics_definition_scope FOREIGN KEY (scope_key, metric_definition_id)
        REFERENCES market.scanner_metric_definitions(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT chk_scanner_result_metrics_version CHECK (metric_version > 0),
    CONSTRAINT chk_scanner_result_metrics_status CHECK (calculation_status IN ('calculated', 'validated', 'not_computable', 'missing', 'stale', 'excluded')),
    CONSTRAINT chk_scanner_result_metrics_value CHECK (
        (calculation_status IN ('calculated', 'validated') AND num_nonnulls(value_numeric, value_text) = 1)
        OR (calculation_status NOT IN ('calculated', 'validated') AND num_nonnulls(value_numeric, value_text) = 0)
    ),
    CONSTRAINT chk_scanner_result_metrics_formula_hash CHECK (formula_hash IS NULL OR formula_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_result_metrics_calculation_hash CHECK (calculation_hash IS NULL OR calculation_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_result_metrics_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(warnings))
);

CREATE INDEX IF NOT EXISTS idx_scanner_result_metrics_result
    ON market.scanner_result_metrics (scope_key, scanner_result_id, metric_key);

CREATE TABLE IF NOT EXISTS market.scanner_result_metric_inputs (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    result_metric_id BIGINT NOT NULL,
    input_role TEXT NOT NULL,
    company_statement_fact_id BIGINT REFERENCES research.company_statement_facts(id) ON DELETE RESTRICT,
    financial_ratio_result_id BIGINT REFERENCES research.financial_ratio_results(id) ON DELETE RESTRICT,
    price_quote_id BIGINT REFERENCES market.price_quotes(id) ON DELETE RESTRICT,
    governance_observation_id BIGINT REFERENCES research.governance_forensic_observations(id) ON DELETE RESTRICT,
    corporate_filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE RESTRICT,
    universe_membership_id BIGINT REFERENCES market.universe_memberships(id) ON DELETE RESTRICT,
    source_available_at TIMESTAMPTZ NOT NULL,
    source_row_hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_scanner_result_metric_inputs_scope_id UNIQUE (scope_key, id),
    CONSTRAINT fk_scanner_result_metric_inputs_metric_scope FOREIGN KEY (scope_key, result_metric_id)
        REFERENCES market.scanner_result_metrics(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_scanner_result_metric_inputs_one_source CHECK (
        num_nonnulls(
            company_statement_fact_id,
            financial_ratio_result_id,
            price_quote_id,
            governance_observation_id,
            corporate_filing_id,
            universe_membership_id
        ) = 1
    ),
    CONSTRAINT chk_scanner_result_metric_inputs_hash CHECK (source_row_hash IS NULL OR source_row_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_scanner_result_metric_inputs_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_scanner_result_metric_inputs_reference
    ON market.scanner_result_metric_inputs (
        scope_key,
        result_metric_id,
        input_role,
        COALESCE(company_statement_fact_id, 0),
        COALESCE(financial_ratio_result_id, 0),
        COALESCE(price_quote_id, 0),
        COALESCE(governance_observation_id, 0),
        COALESCE(corporate_filing_id, 0),
        COALESCE(universe_membership_id, 0)
    );

CREATE TABLE IF NOT EXISTS market.scanner_alerts (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    alert_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    scanner_run_id BIGINT NOT NULL,
    scanner_result_id BIGINT,
    scanner_schedule_id BIGINT,
    alert_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    materiality TEXT NOT NULL DEFAULT 'informational',
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    trigger_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    watchlist_ref TEXT,
    research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    CONSTRAINT uq_scanner_alerts_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_scanner_alerts_key UNIQUE (scope_key, alert_key),
    CONSTRAINT uq_scanner_alerts_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_scanner_alerts_run_scope FOREIGN KEY (scope_key, scanner_run_id)
        REFERENCES market.scanner_runs(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_scanner_alerts_result_scope FOREIGN KEY (scope_key, scanner_result_id)
        REFERENCES market.scanner_results(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_scanner_alerts_schedule_scope FOREIGN KEY (scope_key, scanner_schedule_id)
        REFERENCES market.scanner_schedules(scope_key, id) ON DELETE SET NULL (scanner_schedule_id),
    CONSTRAINT chk_scanner_alerts_type CHECK (alert_type IN ('new_match', 'dropped_match', 'rank_change', 'metric_change', 'coverage_debt', 'validation_failure')),
    CONSTRAINT chk_scanner_alerts_status CHECK (status IN ('draft', 'pending_review', 'acknowledged', 'dismissed', 'linked_to_research')),
    CONSTRAINT chk_scanner_alerts_materiality CHECK (materiality IN ('informational', 'low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_scanner_alerts_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(trigger_payload))
);

CREATE INDEX IF NOT EXISTS idx_scanner_alerts_inbox
    ON market.scanner_alerts (scope_key, status, materiality, created_at DESC);

CREATE OR REPLACE FUNCTION market.validate_scanner_version_publication()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, market, research, agent
AS $fn$
DECLARE
    approval_status TEXT;
    approval_kind TEXT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status IN ('published', 'retired') THEN
        IF NEW.scope_key IS DISTINCT FROM OLD.scope_key
           OR NEW.scanner_definition_id IS DISTINCT FROM OLD.scanner_definition_id
           OR NEW.version IS DISTINCT FROM OLD.version
           OR NEW.api_version IS DISTINCT FROM OLD.api_version
           OR NEW.dsl_version IS DISTINCT FROM OLD.dsl_version
           OR NEW.definition_json IS DISTINCT FROM OLD.definition_json
           OR NEW.definition_hash IS DISTINCT FROM OLD.definition_hash
           OR NEW.universe_config IS DISTINCT FROM OLD.universe_config
           OR NEW.filter_config IS DISTINCT FROM OLD.filter_config
           OR NEW.score_config IS DISTINCT FROM OLD.score_config
           OR NEW.output_config IS DISTINCT FROM OLD.output_config
           OR NEW.calculation_revision IS DISTINCT FROM OLD.calculation_revision
        THEN
            RAISE EXCEPTION 'published scanner versions are immutable';
        END IF;
        IF OLD.status = 'retired' AND NEW.status <> 'retired' THEN
            RAISE EXCEPTION 'retired scanner versions cannot be reactivated';
        END IF;
        IF OLD.status = 'published' AND NEW.status NOT IN ('published', 'retired') THEN
            RAISE EXCEPTION 'published scanner versions may only remain published or retire';
        END IF;
    END IF;

    IF NEW.status = 'published' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'published') THEN
        SELECT a.status, a.approval_type INTO approval_status, approval_kind
        FROM agent.approvals a
        WHERE a.id = NEW.publish_approval_id;
        IF approval_status IS DISTINCT FROM 'approved' OR approval_kind IS DISTINCT FROM 'scanner_publish' THEN
            RAISE EXCEPTION 'scanner publication requires an approved scanner_publish approval';
        END IF;
        NEW.published_at := COALESCE(NEW.published_at, now());
    END IF;

    IF NEW.status = 'retired' THEN
        NEW.retired_at := COALESCE(NEW.retired_at, now());
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_versions_publication ON market.scanner_versions;
CREATE TRIGGER trg_scanner_versions_publication
BEFORE INSERT OR UPDATE ON market.scanner_versions
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_version_publication();

REVOKE ALL ON FUNCTION market.validate_scanner_version_publication() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION market.validate_scanner_version_publication() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION market.validate_scanner_current_version()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
    version_definition_id BIGINT;
    version_status TEXT;
BEGIN
    IF NEW.current_published_version_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT scanner_definition_id, status
      INTO version_definition_id, version_status
      FROM market.scanner_versions
     WHERE scope_key = NEW.scope_key AND id = NEW.current_published_version_id;
    IF version_definition_id IS NULL OR version_definition_id <> NEW.id OR version_status <> 'published' THEN
        RAISE EXCEPTION 'current scanner version must be a published version of this definition';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_definitions_current_version ON market.scanner_definitions;
CREATE TRIGGER trg_scanner_definitions_current_version
BEFORE INSERT OR UPDATE OF scope_key, current_published_version_id
ON market.scanner_definitions
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_current_version();

CREATE OR REPLACE FUNCTION market.validate_scanner_run_gate()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
    version_status TEXT;
    definition_current_version_id BIGINT;
BEGIN
    SELECT v.status, d.current_published_version_id
      INTO version_status, definition_current_version_id
      FROM market.scanner_versions v
      JOIN market.scanner_definitions d
        ON d.scope_key = v.scope_key AND d.id = v.scanner_definition_id
     WHERE v.scope_key = NEW.scope_key AND v.id = NEW.scanner_version_id;

    IF version_status IS DISTINCT FROM 'published'
       OR definition_current_version_id IS DISTINCT FROM NEW.scanner_version_id
    THEN
        RAISE EXCEPTION 'scanner runs require the current published scanner version';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_runs_gate ON market.scanner_runs;
CREATE TRIGGER trg_scanner_runs_gate
BEFORE INSERT OR UPDATE OF scope_key, scanner_version_id
ON market.scanner_runs
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_run_gate();

CREATE OR REPLACE FUNCTION market.validate_scanner_schedule_gate()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, market, research, agent
AS $fn$
DECLARE
    version_status TEXT;
    approval_status TEXT;
    approval_kind TEXT;
BEGIN
    IF NOT NEW.enabled THEN
        RETURN NEW;
    END IF;
    SELECT status INTO version_status
      FROM market.scanner_versions
     WHERE scope_key = NEW.scope_key AND id = NEW.scanner_version_id;
    SELECT a.status, a.approval_type INTO approval_status, approval_kind
      FROM agent.approvals a
     WHERE a.id = NEW.publish_approval_id;

    IF version_status IS DISTINCT FROM 'published' THEN
        RAISE EXCEPTION 'enabled scanner schedule requires a published version';
    END IF;
    IF approval_status IS DISTINCT FROM 'approved' OR approval_kind IS DISTINCT FROM 'scanner_schedule_publish' THEN
        RAISE EXCEPTION 'enabled scanner schedule requires an approved scanner_schedule_publish approval';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_schedules_gate ON market.scanner_schedules;
CREATE TRIGGER trg_scanner_schedules_gate
BEFORE INSERT OR UPDATE OF enabled, scanner_version_id, publish_approval_id
ON market.scanner_schedules
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_schedule_gate();

REVOKE ALL ON FUNCTION market.validate_scanner_schedule_gate() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION market.validate_scanner_schedule_gate() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION market.validate_scanner_universe_point_in_time()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, market, research
AS $fn$
DECLARE
    run_as_of DATE;
    membership_symbol BIGINT;
    member_from DATE;
    member_to DATE;
BEGIN
    SELECT as_of_date INTO run_as_of
      FROM market.scanner_runs
     WHERE scope_key = NEW.scope_key AND id = NEW.scanner_run_id;
    SELECT symbol_id, valid_from, valid_to
      INTO membership_symbol, member_from, member_to
      FROM market.universe_memberships
     WHERE id = NEW.universe_membership_id;

    IF run_as_of IS NULL OR membership_symbol IS NULL THEN
        RAISE EXCEPTION 'scanner universe row references a missing run or membership';
    END IF;
    IF membership_symbol <> NEW.symbol_id THEN
        RAISE EXCEPTION 'scanner universe symbol does not match membership';
    END IF;
    IF member_from > run_as_of OR (member_to IS NOT NULL AND member_to < run_as_of) THEN
        RAISE EXCEPTION 'universe membership is not valid at scanner as-of date';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_run_universe_pit ON market.scanner_run_universe;
CREATE TRIGGER trg_scanner_run_universe_pit
BEFORE INSERT OR UPDATE OF scope_key, scanner_run_id, universe_membership_id, symbol_id
ON market.scanner_run_universe
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_universe_point_in_time();

REVOKE ALL ON FUNCTION market.validate_scanner_universe_point_in_time() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION market.validate_scanner_universe_point_in_time() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION market.validate_scanner_metric_input_cutoff()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, market, research
AS $fn$
DECLARE
    run_cutoff TIMESTAMPTZ;
    run_as_of DATE;
    actual_available_at TIMESTAMPTZ;
    source_period_end DATE;
    member_from DATE;
    member_to DATE;
BEGIN
    SELECT r.as_of_cutoff_at, r.as_of_date
      INTO run_cutoff, run_as_of
      FROM market.scanner_result_metrics m
      JOIN market.scanner_results sr
        ON sr.scope_key = m.scope_key AND sr.id = m.scanner_result_id
      JOIN market.scanner_runs r
        ON r.scope_key = sr.scope_key AND r.id = sr.scanner_run_id
     WHERE m.scope_key = NEW.scope_key AND m.id = NEW.result_metric_id;

    IF run_cutoff IS NULL THEN
        RAISE EXCEPTION 'scanner metric input references a missing scoped result';
    END IF;

    IF NEW.company_statement_fact_id IS NOT NULL THEN
        SELECT available_at, period_end
          INTO actual_available_at, source_period_end
          FROM research.company_statement_facts
         WHERE id = NEW.company_statement_fact_id;
    ELSIF NEW.financial_ratio_result_id IS NOT NULL THEN
        SELECT
            GREATEST(
                rr.created_at,
                COALESCE(
                    max(COALESCE(cf.filed_at, pr.completed_at, pr.started_at, fs.created_at)),
                    rr.created_at
                )
            ),
            rr.period_end
          INTO actual_available_at, source_period_end
          FROM research.financial_ratio_results rr
          LEFT JOIN research.financial_ratio_inputs ri ON ri.ratio_result_id = rr.id
          LEFT JOIN research.financial_source_facts fs ON fs.id = ri.fact_id
          LEFT JOIN research.financial_production_runs pr ON pr.id = fs.production_run_id
          LEFT JOIN research.corporate_filings cf ON cf.id = pr.filing_id
         WHERE rr.id = NEW.financial_ratio_result_id
         GROUP BY rr.created_at, rr.period_end;
    ELSIF NEW.price_quote_id IS NOT NULL THEN
        SELECT quote_ts INTO actual_available_at
          FROM market.price_quotes WHERE id = NEW.price_quote_id;
    ELSIF NEW.governance_observation_id IS NOT NULL THEN
        SELECT available_at, period_end
          INTO actual_available_at, source_period_end
          FROM research.governance_forensic_observations
         WHERE id = NEW.governance_observation_id;
    ELSIF NEW.corporate_filing_id IS NOT NULL THEN
        SELECT COALESCE(filed_at, created_at)
          INTO actual_available_at
          FROM research.corporate_filings
         WHERE id = NEW.corporate_filing_id;
    ELSIF NEW.universe_membership_id IS NOT NULL THEN
        SELECT created_at, valid_from, valid_to
          INTO actual_available_at, member_from, member_to
          FROM market.universe_memberships
         WHERE id = NEW.universe_membership_id;
        IF member_from > run_as_of OR (member_to IS NOT NULL AND member_to < run_as_of) THEN
            RAISE EXCEPTION 'scanner metric uses universe membership outside the as-of date';
        END IF;
    END IF;

    IF actual_available_at IS NULL THEN
        RAISE EXCEPTION 'scanner metric input source is missing an availability timestamp';
    END IF;
    IF actual_available_at > run_cutoff THEN
        RAISE EXCEPTION 'point-in-time cutoff violation: source became available after scanner cutoff';
    END IF;
    IF source_period_end IS NOT NULL AND source_period_end > run_as_of THEN
        RAISE EXCEPTION 'point-in-time cutoff violation: source period ends after scanner as-of date';
    END IF;

    NEW.source_available_at := actual_available_at;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_scanner_metric_inputs_pit ON market.scanner_result_metric_inputs;
CREATE TRIGGER trg_scanner_metric_inputs_pit
BEFORE INSERT OR UPDATE OF
    scope_key,
    result_metric_id,
    company_statement_fact_id,
    financial_ratio_result_id,
    price_quote_id,
    governance_observation_id,
    corporate_filing_id,
    universe_membership_id
ON market.scanner_result_metric_inputs
FOR EACH ROW EXECUTE FUNCTION market.validate_scanner_metric_input_cutoff();

REVOKE ALL ON FUNCTION market.validate_scanner_metric_input_cutoff() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION market.validate_scanner_metric_input_cutoff() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION market.touch_scanner_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END
$fn$;

DO $triggers$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['scanner_definitions', 'scanner_schedules']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_touch_updated_at ON market.%I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER trg_%I_touch_updated_at BEFORE UPDATE ON market.%I FOR EACH ROW EXECUTE FUNCTION market.touch_scanner_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END
$triggers$;

DO $rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'scanner_definitions',
        'scanner_metric_definitions',
        'scanner_versions',
        'scanner_validations',
        'scanner_schedules',
        'scanner_runs',
        'scanner_run_universe',
        'scanner_results',
        'scanner_result_metrics',
        'scanner_result_metric_inputs',
        'scanner_alerts'
    ]
    LOOP
        EXECUTE format('ALTER TABLE market.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE market.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_select ON market.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_insert ON market.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_update ON market.%I', table_name);
        EXECUTE format(
            'CREATE POLICY rd_scope_select ON market.%I FOR SELECT TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key() OR scope_key = ''global:public'')',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_insert ON market.%I FOR INSERT TO ai_os_research_runtime WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_update ON market.%I FOR UPDATE TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key()) WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
    END LOOP;
END
$rls$;

REVOKE ALL ON
    market.scanner_definitions,
    market.scanner_metric_definitions,
    market.scanner_versions,
    market.scanner_validations,
    market.scanner_schedules,
    market.scanner_runs,
    market.scanner_run_universe,
    market.scanner_results,
    market.scanner_result_metrics,
    market.scanner_result_metric_inputs,
    market.scanner_alerts
FROM PUBLIC;

GRANT SELECT, INSERT, UPDATE ON
    market.scanner_definitions,
    market.scanner_metric_definitions,
    market.scanner_versions,
    market.scanner_validations,
    market.scanner_schedules,
    market.scanner_runs,
    market.scanner_run_universe,
    market.scanner_results,
    market.scanner_result_metrics,
    market.scanner_result_metric_inputs,
    market.scanner_alerts
TO ai_os_research_runtime;

GRANT USAGE, SELECT ON SEQUENCE market.scanner_definitions_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_metric_definitions_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_versions_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_validations_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_schedules_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_runs_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_run_universe_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_results_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_result_metrics_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_result_metric_inputs_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE market.scanner_alerts_id_seq TO ai_os_research_runtime;

-- Global, read-only templates. They are deliberately draft/non-executable.
WITH seed(scanner_key, name, description) AS (
    VALUES
        ('buffett_munger_compounders', 'Buffett-Munger Compounders', 'Durable business quality, reinvestment runway, stewardship and valuation discipline.'),
        ('damodaran_value', 'Damodaran Value', 'Intrinsic-value and reverse-DCF candidate set with explicit risk and growth assumptions.'),
        ('garp_peg', 'GARP / PEG', 'Growth at a reasonable price with compatible growth, quality and valuation bases.'),
        ('earnings_acceleration', 'Earnings Acceleration', 'PIT earnings and operating-driver acceleration with revision and quality checks.'),
        ('graham_defensive_value', 'Graham Defensive Value', 'Balance-sheet resilience, earnings history and conservative valuation constraints.'),
        ('magic_formula', 'Magic Formula', 'Earnings yield and return-on-capital ranking with consistent capital definitions.'),
        ('piotroski_f_score', 'Piotroski F-Score', 'Nine-signal financial-strength framework with complete input lineage.'),
        ('quality_momentum', 'Quality Momentum', 'Quality, revisions and price momentum with explicit turnover and bias checks.'),
        ('governance_red_flags', 'Governance Red Flags', 'Auditor, related-party, control, pledge and disclosure-risk screen.')
)
INSERT INTO market.scanner_definitions (
    scope_key,
    scanner_key,
    name,
    description,
    owner_agent,
    status,
    tags,
    created_by
)
SELECT
    'global:public',
    scanner_key,
    name,
    description,
    'Fundamental Research Analyst',
    'draft',
    ARRAY['template', 'fundamental', 'requires_validation']::text[],
    'migration:246'
FROM seed
ON CONFLICT (scope_key, scanner_key) DO NOTHING;

WITH seed(scanner_key, definition_hash) AS (
    VALUES
        ('buffett_munger_compounders', '61b96aea698ee3eac80860e016771ea61bc88cb3a79cc115191e74d8adf6a38b'),
        ('damodaran_value', 'cedefa86c0744787adb652398c90971ef0b0ddd4af3a7513b26e618bf287d87a'),
        ('garp_peg', 'ae53cccf08053180d96a3bf871dad18fcd4a2c9620f8e36f28a54b54b2896943'),
        ('earnings_acceleration', 'f36bcf47fe266dda84967f117d08dc84b25c669682191c64cf0ec2ce373c20a4'),
        ('graham_defensive_value', '9f7528f7be1e18dcda37c7c68e364a25c78581b8a0a197179b96fae9252677ae'),
        ('magic_formula', 'd2cbb271cc6a14f808f5d96c1a9de785af94008bac78ad055404efc7dde267ec'),
        ('piotroski_f_score', 'dd89a57ab8b1a02ca7e768a24515c142c3255bf6607776c0331c61514abd3882'),
        ('quality_momentum', '9512830f2921a27c3563f71c8e705ee6044fe7a44ef5c59d9724fc780ce21c85'),
        ('governance_red_flags', '89c5eb06882e089911f741b19fdbffad672bd05bf75ec8cf8237282050e48c7f')
)
INSERT INTO market.scanner_versions (
    scope_key,
    scanner_definition_id,
    version,
    api_version,
    dsl_version,
    status,
    definition_json,
    definition_hash,
    universe_config,
    filter_config,
    score_config,
    output_config,
    calculation_revision,
    source_request_text,
    created_by
)
SELECT
    d.scope_key,
    d.id,
    1,
    'v1',
    'v1',
    'draft',
    '{"state":"draft_template","executable":false,"root":null,"coverage_requirements":["metric definitions","PIT validation","known-fixture validation","human publication approval"]}'::jsonb,
    seed.definition_hash,
    '{"state":"unconfigured"}'::jsonb,
    '{"state":"unconfigured"}'::jsonb,
    '{"state":"unconfigured"}'::jsonb,
    '{"state":"unconfigured"}'::jsonb,
    'unimplemented',
    'System template only; clone into an operator scope, configure, validate and explicitly publish.',
    'migration:246'
FROM seed
JOIN market.scanner_definitions d
  ON d.scope_key = 'global:public' AND d.scanner_key = seed.scanner_key
ON CONFLICT (scope_key, scanner_definition_id, version) DO NOTHING;

INSERT INTO core.schema_migrations (
    migration_number,
    migration_key,
    definition_checksum_sha256,
    description,
    metadata
)
VALUES (
    246,
    '246_fundamental_scanner_factory_v1',
    '5faffe4e2b473e95dd70ffb1170d0c16b5b5a28b0559cb2cfb5a24c6d78b40f6',
    'Scoped PIT scanner definitions, immutable publication, validations, result lineage and alerts',
    '{"scanner_runs_started":false,"alerts_created":false,"broker_writes":false,"seed_status":"draft_only"}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.schema_migrations
        WHERE migration_number = 246
          AND migration_key = '246_fundamental_scanner_factory_v1'
          AND definition_checksum_sha256 = '5faffe4e2b473e95dd70ffb1170d0c16b5b5a28b0559cb2cfb5a24c6d78b40f6'
    ) THEN
        RAISE EXCEPTION 'migration 246 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
