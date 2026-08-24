BEGIN;

-- Durable, owner-scoped lineage for scheduled Research Following refreshes.
-- This migration does not register or fetch a source.

CREATE TABLE IF NOT EXISTS research.followed_source_refresh_runs (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    run_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    followed_source_id BIGINT NOT NULL,
    source_version_id BIGINT NOT NULL,
    trigger_kind TEXT NOT NULL DEFAULT 'scheduled_due',
    status TEXT NOT NULL DEFAULT 'running',
    due_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    items_upserted INTEGER NOT NULL DEFAULT 0,
    quarantined_items INTEGER NOT NULL DEFAULT 0,
    error_class TEXT,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Research Source Monitor',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_followed_source_refresh_runs_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_followed_source_refresh_runs_key UNIQUE (scope_key, run_key),
    CONSTRAINT uq_followed_source_refresh_runs_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_followed_source_refresh_runs_source_scope FOREIGN KEY (scope_key, followed_source_id)
        REFERENCES research.followed_sources(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_followed_source_refresh_runs_version_scope FOREIGN KEY (scope_key, followed_source_id, source_version_id)
        REFERENCES research.followed_source_versions(scope_key, followed_source_id, id) ON DELETE RESTRICT,
    CONSTRAINT chk_followed_source_refresh_runs_status CHECK (status IN ('running', 'completed', 'failed', 'skipped')),
    CONSTRAINT chk_followed_source_refresh_runs_trigger CHECK (trigger_kind IN ('scheduled_due', 'manual', 'repair')),
    CONSTRAINT chk_followed_source_refresh_runs_counts CHECK (items_upserted >= 0 AND quarantined_items >= 0),
    CONSTRAINT chk_followed_source_refresh_runs_time CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT chk_followed_source_refresh_runs_error_length CHECK (error_message IS NULL OR length(error_message) <= 4000),
    CONSTRAINT chk_followed_source_refresh_runs_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE INDEX IF NOT EXISTS idx_followed_source_refresh_runs_source
    ON research.followed_source_refresh_runs (scope_key, followed_source_id, started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_followed_source_refresh_runs_failures
    ON research.followed_source_refresh_runs (scope_key, status, started_at DESC)
    WHERE status = 'failed';

ALTER TABLE research.followed_source_refresh_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.followed_source_refresh_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rd_scope_select ON research.followed_source_refresh_runs;
DROP POLICY IF EXISTS rd_scope_insert ON research.followed_source_refresh_runs;
DROP POLICY IF EXISTS rd_scope_update ON research.followed_source_refresh_runs;
CREATE POLICY rd_scope_select ON research.followed_source_refresh_runs
    FOR SELECT TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key());
CREATE POLICY rd_scope_insert ON research.followed_source_refresh_runs
    FOR INSERT TO ai_os_research_runtime WITH CHECK (scope_key = core.ai_os_scope_key());
CREATE POLICY rd_scope_update ON research.followed_source_refresh_runs
    FOR UPDATE TO ai_os_research_runtime
    USING (scope_key = core.ai_os_scope_key()) WITH CHECK (scope_key = core.ai_os_scope_key());

REVOKE ALL ON research.followed_source_refresh_runs FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON research.followed_source_refresh_runs TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.followed_source_refresh_runs_id_seq TO ai_os_research_runtime;

CREATE OR REPLACE VIEW research.v_followed_source_refresh_status
WITH (security_barrier = true, security_invoker = true)
AS
SELECT
    source.scope_key,
    source.id AS followed_source_id,
    source.source_key,
    source.status AS source_status,
    source.last_refresh_at,
    source.next_refresh_at,
    run.id AS latest_run_id,
    run.status AS latest_run_status,
    run.items_upserted,
    run.quarantined_items,
    run.error_class,
    run.error_message,
    run.started_at AS latest_run_started_at,
    run.finished_at AS latest_run_finished_at
FROM research.followed_sources source
LEFT JOIN LATERAL (
    SELECT selected.*
    FROM research.followed_source_refresh_runs selected
    WHERE selected.scope_key = source.scope_key
      AND selected.followed_source_id = source.id
    ORDER BY selected.started_at DESC, selected.id DESC
    LIMIT 1
) run ON true;

GRANT SELECT ON research.v_followed_source_refresh_status TO ai_os_research_runtime;

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    247,
    '247_research_following_refresh_runs_v1',
    'a6f4624475d5d49d6004a608253a7754cb3ea85aaad308b609d3a0a7df45b59d',
    'Durable owner-scoped scheduled Research Following refresh lineage and repair status',
    '{"fetches_started":false,"private_storage":"external_ssd","broker_write_allowed":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.schema_migrations
        WHERE migration_number = 247
          AND migration_key = '247_research_following_refresh_runs_v1'
          AND definition_checksum_sha256 = 'a6f4624475d5d49d6004a608253a7754cb3ea85aaad308b609d3a0a7df45b59d'
    ) THEN
        RAISE EXCEPTION 'migration 247 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
