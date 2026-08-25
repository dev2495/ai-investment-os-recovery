BEGIN;

-- Research Desk v1 / milestone 5.
-- Additive and rerunnable. Legacy knowledge rows are preserved; RLS is enabled
-- only on the new graph/index tables in this migration.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS knowledge;

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

GRANT USAGE ON SCHEMA core, knowledge TO ai_os_research_runtime;
GRANT EXECUTE ON FUNCTION core.ai_os_scope_key() TO ai_os_research_runtime;

CREATE TABLE IF NOT EXISTS knowledge.index_runs (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    run_key TEXT NOT NULL,
    run_kind TEXT NOT NULL,
    run_mode TEXT NOT NULL DEFAULT 'incremental',
    status TEXT NOT NULL DEFAULT 'queued',
    collection_name TEXT,
    embedding_model TEXT,
    embedding_revision TEXT,
    input_hash TEXT,
    counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_knowledge_index_runs_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_knowledge_index_runs_scope_key UNIQUE (scope_key, run_key),
    CONSTRAINT chk_knowledge_index_run_kind CHECK (run_kind IN ('obsidian', 'qdrant', 'graph', 'hybrid')),
    CONSTRAINT chk_knowledge_index_run_mode CHECK (run_mode IN ('incremental', 'rebuild')),
    CONSTRAINT chk_knowledge_index_run_status CHECK (status IN ('queued', 'running', 'completed', 'partial', 'failed', 'cancelled')),
    CONSTRAINT chk_knowledge_index_run_time CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT chk_knowledge_index_run_input_hash CHECK (input_hash IS NULL OR input_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_knowledge_index_run_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(counts)
        AND NOT core.jsonb_contains_raw_secret(errors)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE INDEX IF NOT EXISTS idx_knowledge_index_runs_status
    ON knowledge.index_runs (scope_key, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_index_runs_task
    ON knowledge.index_runs (task_id) WHERE task_id IS NOT NULL;

-- Forward-compatible metadata for the existing vault and vector ledgers.
-- Defaults identify legacy rows honestly; RLS is deliberately not enabled here.
ALTER TABLE knowledge.obsidian_notes
    ADD COLUMN IF NOT EXISTS note_key TEXT,
    ADD COLUMN IF NOT EXISTS scope_key TEXT NOT NULL DEFAULT 'legacy:local',
    ADD COLUMN IF NOT EXISTS privacy_class TEXT NOT NULL DEFAULT 'local_private',
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_index_run_id BIGINT;

ALTER TABLE knowledge.vector_documents
    ADD COLUMN IF NOT EXISTS scope_key TEXT NOT NULL DEFAULT 'legacy:local',
    ADD COLUMN IF NOT EXISTS privacy_class TEXT NOT NULL DEFAULT 'local_private',
    ADD COLUMN IF NOT EXISTS index_run_id BIGINT,
    ADD COLUMN IF NOT EXISTS heading_path TEXT[] NOT NULL DEFAULT '{}'::text[],
    ADD COLUMN IF NOT EXISTS source_modified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS embedding_revision TEXT,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

DO $constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'knowledge.obsidian_notes'::regclass
          AND conname = 'obsidian_notes_last_index_run_id_fkey'
    ) THEN
        ALTER TABLE knowledge.obsidian_notes
            ADD CONSTRAINT obsidian_notes_last_index_run_id_fkey
            FOREIGN KEY (last_index_run_id) REFERENCES knowledge.index_runs(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'knowledge.vector_documents'::regclass
          AND conname = 'vector_documents_index_run_id_fkey'
    ) THEN
        ALTER TABLE knowledge.vector_documents
            ADD CONSTRAINT vector_documents_index_run_id_fkey
            FOREIGN KEY (index_run_id) REFERENCES knowledge.index_runs(id) ON DELETE SET NULL;
    END IF;
END
$constraints$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_obsidian_notes_scope_note_key
    ON knowledge.obsidian_notes (scope_key, note_key)
    WHERE note_key IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_obsidian_notes_scope_id
    ON knowledge.obsidian_notes (scope_key, id);
CREATE INDEX IF NOT EXISTS idx_obsidian_notes_scope_type_active
    ON knowledge.obsidian_notes (scope_key, note_type, last_modified_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_vector_documents_scope_source_active
    ON knowledge.vector_documents (scope_key, source_table, source_id, chunk_index)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_vector_documents_index_run
    ON knowledge.vector_documents (index_run_id) WHERE index_run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS knowledge.graph_nodes (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    node_key TEXT NOT NULL,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    source_schema TEXT,
    source_table TEXT,
    source_pk TEXT,
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    privacy_class TEXT NOT NULL DEFAULT 'local_private',
    authority TEXT NOT NULL DEFAULT 'unknown',
    effective_at TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_graph_nodes_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_graph_nodes_scope_key UNIQUE (scope_key, node_key),
    CONSTRAINT chk_graph_nodes_source_identity CHECK (
        num_nonnulls(source_schema, source_table, source_pk) IN (0, 3)
    ),
    CONSTRAINT chk_graph_nodes_privacy CHECK (privacy_class IN ('public', 'local_private', 'client_private')),
    CONSTRAINT chk_graph_nodes_authority CHECK (authority IN ('primary', 'regulatory', 'company', 'user_supplied', 'secondary', 'agent_interpretation', 'unknown')),
    CONSTRAINT chk_graph_nodes_content_hash CHECK (content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_graph_nodes_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_nodes_source_identity
    ON knowledge.graph_nodes (scope_key, source_schema, source_table, source_pk)
    WHERE source_schema IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type_label
    ON knowledge.graph_nodes (scope_key, node_type, label) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_graph_nodes_company_type
    ON knowledge.graph_nodes (scope_key, company_id, node_type) WHERE company_id IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS knowledge.graph_edges (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    edge_key TEXT NOT NULL,
    from_node_id BIGINT NOT NULL REFERENCES knowledge.graph_nodes(id) ON DELETE RESTRICT,
    to_node_id BIGINT NOT NULL REFERENCES knowledge.graph_nodes(id) ON DELETE RESTRICT,
    edge_type TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    evidence_id BIGINT REFERENCES research.fundamental_evidence(id) ON DELETE RESTRICT,
    citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence NUMERIC(5,4),
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    superseded_by_edge_id BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_graph_edges_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_graph_edges_scope_key UNIQUE (scope_key, edge_key),
    CONSTRAINT chk_graph_edges_distinct_nodes CHECK (from_node_id <> to_node_id),
    CONSTRAINT chk_graph_edges_type CHECK (edge_type ~ '^[A-Z][A-Z0-9_]*$'),
    CONSTRAINT chk_graph_edges_validity CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_graph_edges_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT chk_graph_edges_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(citation_locator)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

DO $edge_fk$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'knowledge.graph_edges'::regclass
          AND conname = 'graph_edges_superseded_by_edge_id_fkey'
    ) THEN
        ALTER TABLE knowledge.graph_edges
            ADD CONSTRAINT graph_edges_superseded_by_edge_id_fkey
            FOREIGN KEY (superseded_by_edge_id) REFERENCES knowledge.graph_edges(id) ON DELETE SET NULL;
    END IF;
END
$edge_fk$;

CREATE INDEX IF NOT EXISTS idx_graph_edges_from
    ON knowledge.graph_edges (scope_key, from_node_id, edge_type, available_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_graph_edges_to
    ON knowledge.graph_edges (scope_key, to_node_id, edge_type, available_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_graph_edges_evidence
    ON knowledge.graph_edges (evidence_id) WHERE evidence_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS knowledge.unresolved_links (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    link_key TEXT NOT NULL,
    from_note_id BIGINT NOT NULL REFERENCES knowledge.obsidian_notes(id) ON DELETE CASCADE,
    raw_target TEXT NOT NULL,
    normalized_target TEXT NOT NULL,
    link_text TEXT,
    heading_path TEXT[] NOT NULL DEFAULT '{}'::text[],
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_node_id BIGINT REFERENCES knowledge.graph_nodes(id) ON DELETE SET NULL,
    resolved_note_id BIGINT REFERENCES knowledge.obsidian_notes(id) ON DELETE SET NULL,
    index_run_id BIGINT REFERENCES knowledge.index_runs(id) ON DELETE SET NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_unresolved_links_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_unresolved_links_scope_key UNIQUE (scope_key, link_key),
    CONSTRAINT chk_unresolved_links_status CHECK (status IN ('open', 'resolved', 'ignored')),
    CONSTRAINT chk_unresolved_links_resolution CHECK (
        status <> 'resolved' OR num_nonnulls(resolved_node_id, resolved_note_id) = 1
    ),
    CONSTRAINT chk_unresolved_links_occurrences CHECK (occurrence_count > 0),
    CONSTRAINT chk_unresolved_links_time CHECK (last_seen_at >= first_seen_at),
    CONSTRAINT chk_unresolved_links_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE INDEX IF NOT EXISTS idx_unresolved_links_open_queue
    ON knowledge.unresolved_links (scope_key, status, last_seen_at DESC)
    WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_unresolved_links_from_note
    ON knowledge.unresolved_links (scope_key, from_note_id, status);

CREATE OR REPLACE FUNCTION knowledge.enforce_graph_edge_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
    from_scope TEXT;
    to_scope TEXT;
    superseding_scope TEXT;
BEGIN
    SELECT scope_key INTO from_scope FROM knowledge.graph_nodes WHERE id = NEW.from_node_id;
    SELECT scope_key INTO to_scope FROM knowledge.graph_nodes WHERE id = NEW.to_node_id;

    IF from_scope IS NULL OR to_scope IS NULL THEN
        RAISE EXCEPTION 'graph edge references a missing node';
    END IF;
    IF from_scope <> NEW.scope_key OR to_scope <> NEW.scope_key THEN
        RAISE EXCEPTION 'cross-scope graph edge rejected';
    END IF;

    IF NEW.superseded_by_edge_id IS NOT NULL THEN
        SELECT scope_key INTO superseding_scope
        FROM knowledge.graph_edges
        WHERE id = NEW.superseded_by_edge_id;
        IF superseding_scope IS NULL OR superseding_scope <> NEW.scope_key THEN
            RAISE EXCEPTION 'cross-scope superseding edge rejected';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_graph_edges_scope ON knowledge.graph_edges;
CREATE TRIGGER trg_graph_edges_scope
BEFORE INSERT OR UPDATE OF scope_key, from_node_id, to_node_id, superseded_by_edge_id
ON knowledge.graph_edges
FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_graph_edge_scope();

CREATE OR REPLACE FUNCTION knowledge.enforce_unresolved_link_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, knowledge
AS $fn$
DECLARE
    note_scope TEXT;
    resolved_scope TEXT;
BEGIN
    SELECT scope_key INTO note_scope FROM knowledge.obsidian_notes WHERE id = NEW.from_note_id;
    IF note_scope IS NULL OR note_scope <> NEW.scope_key THEN
        RAISE EXCEPTION 'unresolved link scope does not match source note';
    END IF;
    IF NEW.resolved_node_id IS NOT NULL THEN
        SELECT scope_key INTO resolved_scope FROM knowledge.graph_nodes WHERE id = NEW.resolved_node_id;
        IF resolved_scope IS NULL OR resolved_scope <> NEW.scope_key THEN
            RAISE EXCEPTION 'cross-scope unresolved-link resolution rejected';
        END IF;
    END IF;
    IF NEW.resolved_note_id IS NOT NULL THEN
        SELECT scope_key INTO resolved_scope FROM knowledge.obsidian_notes WHERE id = NEW.resolved_note_id;
        IF resolved_scope IS NULL OR resolved_scope <> NEW.scope_key THEN
            RAISE EXCEPTION 'cross-scope note resolution rejected';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_unresolved_links_scope ON knowledge.unresolved_links;
CREATE TRIGGER trg_unresolved_links_scope
BEFORE INSERT OR UPDATE OF scope_key, from_note_id, resolved_node_id, resolved_note_id
ON knowledge.unresolved_links
FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_unresolved_link_scope();

REVOKE ALL ON FUNCTION knowledge.enforce_unresolved_link_scope() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION knowledge.enforce_unresolved_link_scope() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION knowledge.touch_research_graph_updated_at()
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
    FOREACH table_name IN ARRAY ARRAY['index_runs', 'graph_nodes', 'graph_edges', 'unresolved_links']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_touch_updated_at ON knowledge.%I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER trg_%I_touch_updated_at BEFORE UPDATE ON knowledge.%I FOR EACH ROW EXECUTE FUNCTION knowledge.touch_research_graph_updated_at()',
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
    FOREACH table_name IN ARRAY ARRAY['index_runs', 'graph_nodes', 'graph_edges', 'unresolved_links']
    LOOP
        EXECUTE format('ALTER TABLE knowledge.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE knowledge.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_select ON knowledge.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_insert ON knowledge.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_update ON knowledge.%I', table_name);
        EXECUTE format(
            'CREATE POLICY rd_scope_select ON knowledge.%I FOR SELECT TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key())',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_insert ON knowledge.%I FOR INSERT TO ai_os_research_runtime WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_update ON knowledge.%I FOR UPDATE TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key()) WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
    END LOOP;
END
$rls$;

REVOKE ALL ON knowledge.index_runs, knowledge.graph_nodes, knowledge.graph_edges, knowledge.unresolved_links FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON knowledge.index_runs, knowledge.graph_nodes, knowledge.graph_edges, knowledge.unresolved_links TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE knowledge.index_runs_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE knowledge.graph_nodes_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE knowledge.graph_edges_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE knowledge.unresolved_links_id_seq TO ai_os_research_runtime;

CREATE OR REPLACE VIEW knowledge.v_note_entity_links
WITH (security_barrier = true, security_invoker = true)
AS
SELECT
    e.scope_key,
    n.source_pk::BIGINT AS note_id,
    e.edge_type,
    target.id AS entity_node_id,
    target.node_key AS entity_key,
    target.node_type AS entity_type,
    target.label AS entity_label,
    e.evidence_id,
    e.citation_locator,
    e.available_at,
    e.confidence
FROM knowledge.graph_edges e
JOIN knowledge.graph_nodes n ON n.id = e.from_node_id AND n.scope_key = e.scope_key
JOIN knowledge.graph_nodes target ON target.id = e.to_node_id AND target.scope_key = e.scope_key
WHERE n.source_schema = 'knowledge'
  AND n.source_table = 'obsidian_notes'
  AND n.source_pk ~ '^[0-9]+$'
  AND target.node_type IN ('company', 'person', 'sector', 'industry', 'concept', 'entity', 'research_case')
  AND e.deleted_at IS NULL
  AND n.deleted_at IS NULL
  AND target.deleted_at IS NULL;

CREATE OR REPLACE VIEW knowledge.v_note_case_links
WITH (security_barrier = true, security_invoker = true)
AS
SELECT *
FROM knowledge.v_note_entity_links
WHERE entity_type = 'research_case';

CREATE OR REPLACE VIEW knowledge.v_note_evidence_links
WITH (security_barrier = true, security_invoker = true)
AS
SELECT
    e.scope_key,
    n.source_pk::BIGINT AS note_id,
    e.edge_type,
    e.evidence_id,
    e.citation_locator,
    e.available_at,
    e.confidence
FROM knowledge.graph_edges e
JOIN knowledge.graph_nodes n ON n.id = e.from_node_id AND n.scope_key = e.scope_key
WHERE n.source_schema = 'knowledge'
  AND n.source_table = 'obsidian_notes'
  AND n.source_pk ~ '^[0-9]+$'
  AND e.evidence_id IS NOT NULL
  AND e.deleted_at IS NULL
  AND n.deleted_at IS NULL;

GRANT SELECT ON knowledge.v_note_entity_links, knowledge.v_note_case_links, knowledge.v_note_evidence_links TO ai_os_research_runtime;

INSERT INTO core.schema_migrations (
    migration_number,
    migration_key,
    definition_checksum_sha256,
    description,
    metadata
)
VALUES (
    244,
    '244_research_knowledge_graph_v1',
    'd102cad78cd3f9f48bb36966558d5e69bf64f107988adaaddb10650105970d38',
    'Scoped incremental knowledge graph, unresolved link queue and index-run lineage',
    '{"legacy_rows_preserved":true,"legacy_rls_unchanged":true,"private_storage":"external_ssd"}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.schema_migrations
        WHERE migration_number = 244
          AND migration_key = '244_research_knowledge_graph_v1'
          AND definition_checksum_sha256 = 'd102cad78cd3f9f48bb36966558d5e69bf64f107988adaaddb10650105970d38'
    ) THEN
        RAISE EXCEPTION 'migration 244 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
