BEGIN;

-- Research Desk v1 / milestone 6.
-- Versioned public-source following and idea triage. No source is fetched and
-- no research case is started by this schema migration.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS research;

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

GRANT USAGE ON SCHEMA core, research, knowledge TO ai_os_research_runtime;
GRANT EXECUTE ON FUNCTION core.ai_os_scope_key() TO ai_os_research_runtime;

CREATE TABLE IF NOT EXISTS research.followed_sources (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    source_key TEXT NOT NULL,
    feed_registry_id BIGINT REFERENCES research.feed_registry(id) ON DELETE RESTRICT,
    data_source_registry_id BIGINT REFERENCES core.data_source_registry(id) ON DELETE RESTRICT,
    current_version_id BIGINT,
    status TEXT NOT NULL DEFAULT 'pending_review',
    priority TEXT NOT NULL DEFAULT 'normal',
    followed_by TEXT NOT NULL,
    followed_reason TEXT,
    last_refresh_at TIMESTAMPTZ,
    next_refresh_at TIMESTAMPTZ,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_followed_sources_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_followed_sources_scope_key UNIQUE (scope_key, source_key),
    CONSTRAINT chk_followed_sources_registry CHECK (num_nonnulls(feed_registry_id, data_source_registry_id) >= 1),
    CONSTRAINT chk_followed_sources_status CHECK (status IN ('active', 'paused', 'pending_review', 'blocked', 'retired')),
    CONSTRAINT chk_followed_sources_priority CHECK (priority IN ('low', 'normal', 'medium', 'high', 'critical')),
    CONSTRAINT chk_followed_sources_refresh_time CHECK (next_refresh_at IS NULL OR last_refresh_at IS NULL OR next_refresh_at >= last_refresh_at),
    CONSTRAINT chk_followed_sources_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_followed_sources_feed
    ON research.followed_sources (scope_key, feed_registry_id)
    WHERE feed_registry_id IS NOT NULL AND status <> 'retired';
CREATE UNIQUE INDEX IF NOT EXISTS uq_followed_sources_data_source
    ON research.followed_sources (scope_key, data_source_registry_id)
    WHERE data_source_registry_id IS NOT NULL AND status <> 'retired';
CREATE INDEX IF NOT EXISTS idx_followed_sources_refresh
    ON research.followed_sources (scope_key, status, next_refresh_at)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS research.followed_source_versions (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    followed_source_id BIGINT NOT NULL,
    version INTEGER NOT NULL,
    definition_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    adapter_key TEXT NOT NULL,
    source_url TEXT,
    auth_profile_ref TEXT,
    trust_tier TEXT NOT NULL DEFAULT 'unrated',
    authority TEXT NOT NULL DEFAULT 'secondary',
    topics TEXT[] NOT NULL DEFAULT '{}'::text[],
    sectors TEXT[] NOT NULL DEFAULT '{}'::text[],
    schedule_cron TEXT,
    ingestion_mode TEXT NOT NULL DEFAULT 'metadata_and_permitted_excerpt',
    entity_resolution_mode TEXT NOT NULL DEFAULT 'reviewed',
    idea_generation_enabled BOOLEAN NOT NULL DEFAULT true,
    portfolio_mapping_enabled BOOLEAN NOT NULL DEFAULT true,
    requires_login BOOLEAN NOT NULL DEFAULT false,
    copyright_policy TEXT NOT NULL,
    prompt_injection_policy TEXT NOT NULL DEFAULT 'quarantine_and_review',
    retention_policy TEXT NOT NULL DEFAULT 'local_ssd',
    public_model_eligible BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'draft',
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_followed_source_versions_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_followed_source_versions_source_id UNIQUE (scope_key, followed_source_id, id),
    CONSTRAINT uq_followed_source_versions_number UNIQUE (scope_key, followed_source_id, version),
    CONSTRAINT fk_followed_source_versions_source_scope FOREIGN KEY (scope_key, followed_source_id)
        REFERENCES research.followed_sources(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_followed_source_versions_positive CHECK (version > 0),
    CONSTRAINT chk_followed_source_versions_hash CHECK (definition_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_followed_source_versions_url CHECK (source_url IS NULL OR source_url ~* '^https://'),
    CONSTRAINT chk_followed_source_versions_status CHECK (status IN ('draft', 'reviewed', 'active', 'retired', 'rejected')),
    CONSTRAINT chk_followed_source_versions_trust CHECK (trust_tier IN ('primary', 'high', 'medium', 'low', 'unrated')),
    CONSTRAINT chk_followed_source_versions_authority CHECK (authority IN ('primary', 'regulatory', 'company', 'user_supplied', 'secondary')),
    CONSTRAINT chk_followed_source_versions_ingestion CHECK (ingestion_mode IN ('metadata_only', 'metadata_and_permitted_excerpt', 'authorized_full_text')),
    CONSTRAINT chk_followed_source_versions_approval CHECK (
        status NOT IN ('reviewed', 'active') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    CONSTRAINT chk_followed_source_versions_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(config))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_followed_source_versions_active
    ON research.followed_source_versions (scope_key, followed_source_id)
    WHERE status = 'active';

DO $current_version_fk$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'research.followed_sources'::regclass
          AND conname = 'followed_sources_current_version_scope_fkey'
    ) THEN
        ALTER TABLE research.followed_sources
            ADD CONSTRAINT followed_sources_current_version_scope_fkey
            FOREIGN KEY (scope_key, current_version_id)
            REFERENCES research.followed_source_versions(scope_key, id)
            ON DELETE SET NULL (current_version_id);
    END IF;
END
$current_version_fk$;

CREATE TABLE IF NOT EXISTS research.people_or_authors (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    person_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    aliases TEXT[] NOT NULL DEFAULT '{}'::text[],
    role_summary TEXT,
    biography_summary TEXT,
    sectors TEXT[] NOT NULL DEFAULT '{}'::text[],
    themes TEXT[] NOT NULL DEFAULT '{}'::text[],
    trust_status TEXT NOT NULL DEFAULT 'unrated',
    following_status TEXT NOT NULL DEFAULT 'proposed',
    conflicts JSONB NOT NULL DEFAULT '[]'::jsonb,
    disclosures JSONB NOT NULL DEFAULT '[]'::jsonb,
    obsidian_note_id BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_people_or_authors_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_people_or_authors_scope_key UNIQUE (scope_key, person_key),
    CONSTRAINT fk_people_or_authors_note_scope FOREIGN KEY (scope_key, obsidian_note_id)
        REFERENCES knowledge.obsidian_notes(scope_key, id) ON DELETE SET NULL (obsidian_note_id),
    CONSTRAINT chk_people_or_authors_trust CHECK (trust_status IN ('trusted', 'mixed', 'watch', 'unrated', 'blocked')),
    CONSTRAINT chk_people_or_authors_following CHECK (following_status IN ('proposed', 'following', 'paused', 'blocked', 'retired')),
    CONSTRAINT chk_people_or_authors_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(conflicts)
        AND NOT core.jsonb_contains_raw_secret(disclosures)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE TABLE IF NOT EXISTS research.person_source_profiles (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    person_id BIGINT NOT NULL,
    followed_source_id BIGINT NOT NULL,
    profile_key TEXT NOT NULL,
    profile_url TEXT,
    handle TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    first_observed_at TIMESTAMPTZ,
    last_observed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_person_source_profiles_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_person_source_profiles_key UNIQUE (scope_key, followed_source_id, profile_key),
    CONSTRAINT fk_person_source_profiles_person_scope FOREIGN KEY (scope_key, person_id)
        REFERENCES research.people_or_authors(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_person_source_profiles_source_scope FOREIGN KEY (scope_key, followed_source_id)
        REFERENCES research.followed_sources(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_person_source_profiles_url CHECK (profile_url IS NULL OR profile_url ~* '^https://'),
    CONSTRAINT chk_person_source_profiles_status CHECK (status IN ('active', 'paused', 'blocked', 'retired')),
    CONSTRAINT chk_person_source_profiles_time CHECK (last_observed_at IS NULL OR first_observed_at IS NULL OR last_observed_at >= first_observed_at),
    CONSTRAINT chk_person_source_profiles_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE TABLE IF NOT EXISTS research.followed_source_items (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    item_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    followed_source_id BIGINT NOT NULL,
    source_version_id BIGINT NOT NULL,
    provider_item_key TEXT,
    source_collection_capture_id BIGINT REFERENCES research.source_collection_captures(id) ON DELETE SET NULL,
    thesis_source_item_id BIGINT REFERENCES research.thesis_source_items(id) ON DELETE SET NULL,
    canonical_url TEXT,
    title TEXT NOT NULL,
    author_id BIGINT,
    published_at TIMESTAMPTZ,
    effective_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_sha256 TEXT,
    metadata_sha256 TEXT,
    permitted_excerpt TEXT,
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE RESTRICT,
    quarantine_status TEXT NOT NULL DEFAULT 'pending_scan',
    prompt_injection_status TEXT NOT NULL DEFAULT 'not_scanned',
    parser_status TEXT NOT NULL DEFAULT 'pending',
    authority TEXT NOT NULL DEFAULT 'secondary',
    trust_score NUMERIC(5,4),
    public_model_eligible BOOLEAN NOT NULL DEFAULT false,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_followed_source_items_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_followed_source_items_scope_key UNIQUE (scope_key, item_key),
    CONSTRAINT uq_followed_source_items_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_followed_source_items_version_scope FOREIGN KEY (scope_key, followed_source_id, source_version_id)
        REFERENCES research.followed_source_versions(scope_key, followed_source_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_followed_source_items_author_scope FOREIGN KEY (scope_key, author_id)
        REFERENCES research.people_or_authors(scope_key, id) ON DELETE SET NULL (author_id),
    CONSTRAINT chk_followed_source_items_url CHECK (canonical_url IS NULL OR canonical_url ~* '^https://'),
    CONSTRAINT chk_followed_source_items_content_hash CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_followed_source_items_metadata_hash CHECK (metadata_sha256 IS NULL OR metadata_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_followed_source_items_excerpt CHECK (permitted_excerpt IS NULL OR length(permitted_excerpt) <= 4000),
    CONSTRAINT chk_followed_source_items_quarantine CHECK (quarantine_status IN ('pending_scan', 'clear', 'quarantined', 'reviewed_safe', 'rejected')),
    CONSTRAINT chk_followed_source_items_injection CHECK (prompt_injection_status IN ('not_scanned', 'none_detected', 'suspected', 'confirmed', 'cleared_by_human')),
    CONSTRAINT chk_followed_source_items_parser CHECK (parser_status IN ('pending', 'metadata_only', 'parsed', 'partial', 'failed', 'not_permitted')),
    CONSTRAINT chk_followed_source_items_authority CHECK (authority IN ('primary', 'regulatory', 'company', 'user_supplied', 'secondary')),
    CONSTRAINT chk_followed_source_items_trust CHECK (trust_score IS NULL OR (trust_score >= 0 AND trust_score <= 1)),
    CONSTRAINT chk_followed_source_items_model_eligibility CHECK (
        NOT public_model_eligible OR quarantine_status IN ('clear', 'reviewed_safe')
    ),
    CONSTRAINT chk_followed_source_items_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_followed_source_items_provider_key
    ON research.followed_source_items (scope_key, followed_source_id, provider_item_key)
    WHERE provider_item_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_followed_source_items_content
    ON research.followed_source_items (scope_key, followed_source_id, content_sha256)
    WHERE content_sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_followed_source_items_feed
    ON research.followed_source_items (scope_key, followed_source_id, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_followed_source_items_author
    ON research.followed_source_items (scope_key, author_id, published_at DESC)
    WHERE author_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_followed_source_items_quarantine
    ON research.followed_source_items (scope_key, quarantine_status, captured_at DESC)
    WHERE quarantine_status NOT IN ('clear', 'reviewed_safe');

CREATE TABLE IF NOT EXISTS research.source_item_entities (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    source_item_id BIGINT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    graph_node_id BIGINT,
    mention_kind TEXT NOT NULL DEFAULT 'mentioned',
    confidence NUMERIC(5,4),
    resolver_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_item_entities_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_source_item_entities_identity UNIQUE (scope_key, source_item_id, entity_type, entity_key, mention_kind),
    CONSTRAINT fk_source_item_entities_item_scope FOREIGN KEY (scope_key, source_item_id)
        REFERENCES research.followed_source_items(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_source_item_entities_graph_scope FOREIGN KEY (scope_key, graph_node_id)
        REFERENCES knowledge.graph_nodes(scope_key, id) ON DELETE SET NULL (graph_node_id),
    CONSTRAINT chk_source_item_entities_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT chk_source_item_entities_status CHECK (status IN ('proposed', 'resolved', 'ambiguous', 'rejected')),
    CONSTRAINT chk_source_item_entities_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE INDEX IF NOT EXISTS idx_source_item_entities_company
    ON research.source_item_entities (scope_key, company_id, source_item_id)
    WHERE company_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_source_item_entities_graph
    ON research.source_item_entities (scope_key, graph_node_id)
    WHERE graph_node_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS research.source_item_claims (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    source_item_id BIGINT NOT NULL,
    claim_hash TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    claim_kind TEXT NOT NULL,
    citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    primary_corroboration_required BOOLEAN NOT NULL DEFAULT true,
    acceptance_status TEXT NOT NULL DEFAULT 'commentary_only',
    promoted_source_claim_candidate_id BIGINT REFERENCES research.source_claim_candidates(id) ON DELETE SET NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_item_claims_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_source_item_claims_hash UNIQUE (scope_key, source_item_id, claim_hash),
    CONSTRAINT fk_source_item_claims_item_scope FOREIGN KEY (scope_key, source_item_id)
        REFERENCES research.followed_source_items(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_source_item_claims_hash CHECK (claim_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_source_item_claims_text CHECK (length(btrim(claim_text)) BETWEEN 1 AND 4000),
    CONSTRAINT chk_source_item_claims_kind CHECK (claim_kind IN ('historical_fact', 'current_fact', 'management_guidance', 'estimate', 'opinion', 'hypothesis')),
    CONSTRAINT chk_source_item_claims_status CHECK (acceptance_status IN ('commentary_only', 'needs_primary', 'corroborated', 'contradicted', 'rejected')),
    CONSTRAINT chk_source_item_claims_promotion CHECK (
        acceptance_status <> 'corroborated' OR promoted_source_claim_candidate_id IS NOT NULL
    ),
    CONSTRAINT chk_source_item_claims_review CHECK (
        reviewed_at IS NULL OR reviewed_by IS NOT NULL
    ),
    CONSTRAINT chk_source_item_claims_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(citation_locator)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE INDEX IF NOT EXISTS idx_source_item_claims_review
    ON research.source_item_claims (scope_key, acceptance_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_item_claims_item
    ON research.source_item_claims (scope_key, source_item_id, acceptance_status);

CREATE TABLE IF NOT EXISTS research.source_scorecards (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    author_id BIGINT,
    followed_source_id BIGINT,
    methodology_version TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    component_scores JSONB NOT NULL,
    weighted_score NUMERIC(7,4),
    sample_count INTEGER NOT NULL DEFAULT 0,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    contradicted_count INTEGER NOT NULL DEFAULT 0,
    calculation_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE RESTRICT,
    calculation_hash TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_scorecards_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_source_scorecards_author UNIQUE (scope_key, author_id, methodology_version, as_of_date),
    CONSTRAINT uq_source_scorecards_source UNIQUE (scope_key, followed_source_id, methodology_version, as_of_date),
    CONSTRAINT fk_source_scorecards_author_scope FOREIGN KEY (scope_key, author_id)
        REFERENCES research.people_or_authors(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_source_scorecards_source_scope FOREIGN KEY (scope_key, followed_source_id)
        REFERENCES research.followed_sources(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_source_scorecards_subject CHECK (
        (subject_type = 'author' AND author_id IS NOT NULL AND followed_source_id IS NULL)
        OR (subject_type = 'source' AND followed_source_id IS NOT NULL AND author_id IS NULL)
    ),
    CONSTRAINT chk_source_scorecards_counts CHECK (
        sample_count >= 0 AND evidence_count >= 0 AND unresolved_count >= 0 AND contradicted_count >= 0
    ),
    CONSTRAINT chk_source_scorecards_score CHECK (weighted_score IS NULL OR (weighted_score >= 0 AND weighted_score <= 100)),
    CONSTRAINT chk_source_scorecards_hash CHECK (calculation_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_source_scorecards_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(component_scores)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE TABLE IF NOT EXISTS research.idea_cards (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    idea_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    source_item_id BIGINT NOT NULL,
    author_id BIGINT,
    primary_company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    core_claim TEXT NOT NULL,
    catalyst TEXT,
    horizon TEXT,
    claimed_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_evidence_found JSONB NOT NULL DEFAULT '[]'::jsonb,
    contradictions JSONB NOT NULL DEFAULT '[]'::jsonb,
    novelty_score NUMERIC(5,4),
    source_score NUMERIC(5,4),
    author_score NUMERIC(5,4),
    portfolio_overlap JSONB NOT NULL DEFAULT '{}'::jsonb,
    watchlist_overlap JSONB NOT NULL DEFAULT '{}'::jsonb,
    research_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'proposed',
    research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
    graph_node_id BIGINT,
    obsidian_note_id BIGINT,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    audit_id BIGINT REFERENCES agent.mcp_audit_log(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idea_cards_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_idea_cards_scope_key UNIQUE (scope_key, idea_key),
    CONSTRAINT uq_idea_cards_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_idea_cards_item_scope FOREIGN KEY (scope_key, source_item_id)
        REFERENCES research.followed_source_items(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT fk_idea_cards_author_scope FOREIGN KEY (scope_key, author_id)
        REFERENCES research.people_or_authors(scope_key, id) ON DELETE SET NULL (author_id),
    CONSTRAINT fk_idea_cards_graph_scope FOREIGN KEY (scope_key, graph_node_id)
        REFERENCES knowledge.graph_nodes(scope_key, id) ON DELETE SET NULL (graph_node_id),
    CONSTRAINT fk_idea_cards_note_scope FOREIGN KEY (scope_key, obsidian_note_id)
        REFERENCES knowledge.obsidian_notes(scope_key, id) ON DELETE SET NULL (obsidian_note_id),
    CONSTRAINT chk_idea_cards_status CHECK (status IN ('proposed', 'triage', 'researching', 'accepted', 'rejected', 'archived')),
    CONSTRAINT chk_idea_cards_novelty CHECK (novelty_score IS NULL OR (novelty_score >= 0 AND novelty_score <= 1)),
    CONSTRAINT chk_idea_cards_source_score CHECK (source_score IS NULL OR (source_score >= 0 AND source_score <= 1)),
    CONSTRAINT chk_idea_cards_author_score CHECK (author_score IS NULL OR (author_score >= 0 AND author_score <= 1)),
    CONSTRAINT chk_idea_cards_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(claimed_evidence)
        AND NOT core.jsonb_contains_raw_secret(primary_evidence_found)
        AND NOT core.jsonb_contains_raw_secret(contradictions)
        AND NOT core.jsonb_contains_raw_secret(portfolio_overlap)
        AND NOT core.jsonb_contains_raw_secret(watchlist_overlap)
        AND NOT core.jsonb_contains_raw_secret(research_questions)
        AND NOT core.jsonb_contains_raw_secret(risk_flags)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE INDEX IF NOT EXISTS idx_idea_cards_inbox
    ON research.idea_cards (scope_key, status, novelty_score DESC NULLS LAST, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_idea_cards_company
    ON research.idea_cards (scope_key, primary_company_id, status, created_at DESC)
    WHERE primary_company_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS research.idea_card_evidence (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    idea_card_id BIGINT NOT NULL,
    evidence_kind TEXT NOT NULL,
    fundamental_evidence_id BIGINT REFERENCES research.fundamental_evidence(id) ON DELETE RESTRICT,
    source_item_claim_id BIGINT,
    source_item_id BIGINT,
    relation TEXT NOT NULL,
    citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_status TEXT NOT NULL DEFAULT 'pending',
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idea_card_evidence_scope_id UNIQUE (scope_key, id),
    CONSTRAINT fk_idea_card_evidence_card_scope FOREIGN KEY (scope_key, idea_card_id)
        REFERENCES research.idea_cards(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT fk_idea_card_evidence_claim_scope FOREIGN KEY (scope_key, source_item_claim_id)
        REFERENCES research.source_item_claims(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT fk_idea_card_evidence_item_scope FOREIGN KEY (scope_key, source_item_id)
        REFERENCES research.followed_source_items(scope_key, id) ON DELETE RESTRICT,
    CONSTRAINT chk_idea_card_evidence_one_source CHECK (
        num_nonnulls(fundamental_evidence_id, source_item_claim_id, source_item_id) = 1
    ),
    CONSTRAINT chk_idea_card_evidence_relation CHECK (relation IN ('supports', 'contradicts', 'primary_search', 'context')),
    CONSTRAINT chk_idea_card_evidence_validation CHECK (validation_status IN ('pending', 'machine_checked', 'validated', 'rejected')),
    CONSTRAINT chk_idea_card_evidence_no_raw_secrets CHECK (
        NOT core.jsonb_contains_raw_secret(citation_locator)
        AND NOT core.jsonb_contains_raw_secret(metadata)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_idea_card_evidence_reference
    ON research.idea_card_evidence (
        scope_key,
        idea_card_id,
        relation,
        COALESCE(fundamental_evidence_id, 0),
        COALESCE(source_item_claim_id, 0),
        COALESCE(source_item_id, 0)
    );

CREATE TABLE IF NOT EXISTS research.idea_triage (
    id BIGSERIAL PRIMARY KEY,
    scope_key TEXT NOT NULL,
    triage_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    idea_card_id BIGINT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    resulting_research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_idea_triage_scope_id UNIQUE (scope_key, id),
    CONSTRAINT uq_idea_triage_scope_key UNIQUE (scope_key, triage_key),
    CONSTRAINT uq_idea_triage_idempotency UNIQUE (scope_key, idempotency_key),
    CONSTRAINT fk_idea_triage_card_scope FOREIGN KEY (scope_key, idea_card_id)
        REFERENCES research.idea_cards(scope_key, id) ON DELETE CASCADE,
    CONSTRAINT chk_idea_triage_decision CHECK (decision IN ('defer', 'dismiss', 'watch', 'request_evidence', 'propose_research_case', 'start_confirmed_case')),
    CONSTRAINT chk_idea_triage_case_gate CHECK (
        decision <> 'start_confirmed_case' OR (approval_id IS NOT NULL AND resulting_research_case_id IS NOT NULL)
    ),
    CONSTRAINT chk_idea_triage_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(metadata))
);

CREATE INDEX IF NOT EXISTS idx_idea_triage_card
    ON research.idea_triage (scope_key, idea_card_id, decided_at DESC);

CREATE OR REPLACE FUNCTION research.validate_followed_source_current_version()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
    version_source_id BIGINT;
    version_status TEXT;
BEGIN
    IF NEW.current_version_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT followed_source_id, status
      INTO version_source_id, version_status
      FROM research.followed_source_versions
     WHERE scope_key = NEW.scope_key AND id = NEW.current_version_id;
    IF version_source_id IS NULL OR version_source_id <> NEW.id THEN
        RAISE EXCEPTION 'current source version does not belong to followed source';
    END IF;
    IF version_status <> 'active' THEN
        RAISE EXCEPTION 'current source version must be active';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_followed_sources_current_version ON research.followed_sources;
CREATE TRIGGER trg_followed_sources_current_version
BEFORE INSERT OR UPDATE OF scope_key, current_version_id
ON research.followed_sources
FOR EACH ROW EXECUTE FUNCTION research.validate_followed_source_current_version();

CREATE OR REPLACE FUNCTION research.validate_source_item_claim_promotion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, research
AS $fn$
DECLARE
    candidate_status TEXT;
BEGIN
    IF NEW.promoted_source_claim_candidate_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT acceptance_status INTO candidate_status
    FROM research.source_claim_candidates
    WHERE id = NEW.promoted_source_claim_candidate_id;

    IF candidate_status IS NULL OR candidate_status NOT IN ('corroborated', 'validated') THEN
        RAISE EXCEPTION 'source commentary may be promoted only through a corroborated or validated claim candidate';
    END IF;
    IF NEW.acceptance_status <> 'corroborated' THEN
        RAISE EXCEPTION 'promoted source-item claim must be marked corroborated';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_source_item_claim_promotion ON research.source_item_claims;
CREATE TRIGGER trg_source_item_claim_promotion
BEFORE INSERT OR UPDATE OF acceptance_status, promoted_source_claim_candidate_id
ON research.source_item_claims
FOR EACH ROW EXECUTE FUNCTION research.validate_source_item_claim_promotion();

REVOKE ALL ON FUNCTION research.validate_source_item_claim_promotion() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION research.validate_source_item_claim_promotion() TO ai_os_research_runtime;

CREATE OR REPLACE FUNCTION research.touch_following_updated_at()
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
    FOREACH table_name IN ARRAY ARRAY[
        'followed_sources',
        'people_or_authors',
        'person_source_profiles',
        'followed_source_items',
        'source_item_entities',
        'source_item_claims',
        'idea_cards'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_touch_updated_at ON research.%I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER trg_%I_touch_updated_at BEFORE UPDATE ON research.%I FOR EACH ROW EXECUTE FUNCTION research.touch_following_updated_at()',
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
        'followed_sources',
        'followed_source_versions',
        'people_or_authors',
        'person_source_profiles',
        'followed_source_items',
        'source_item_entities',
        'source_item_claims',
        'source_scorecards',
        'idea_cards',
        'idea_card_evidence',
        'idea_triage'
    ]
    LOOP
        EXECUTE format('ALTER TABLE research.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE research.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_select ON research.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_insert ON research.%I', table_name);
        EXECUTE format('DROP POLICY IF EXISTS rd_scope_update ON research.%I', table_name);
        EXECUTE format(
            'CREATE POLICY rd_scope_select ON research.%I FOR SELECT TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key())',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_insert ON research.%I FOR INSERT TO ai_os_research_runtime WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY rd_scope_update ON research.%I FOR UPDATE TO ai_os_research_runtime USING (scope_key = core.ai_os_scope_key()) WITH CHECK (scope_key = core.ai_os_scope_key())',
            table_name
        );
    END LOOP;
END
$rls$;

REVOKE ALL ON
    research.followed_sources,
    research.followed_source_versions,
    research.people_or_authors,
    research.person_source_profiles,
    research.followed_source_items,
    research.source_item_entities,
    research.source_item_claims,
    research.source_scorecards,
    research.idea_cards,
    research.idea_card_evidence,
    research.idea_triage
FROM PUBLIC;

GRANT SELECT, INSERT, UPDATE ON
    research.followed_sources,
    research.followed_source_versions,
    research.people_or_authors,
    research.person_source_profiles,
    research.followed_source_items,
    research.source_item_entities,
    research.source_item_claims,
    research.source_scorecards,
    research.idea_cards,
    research.idea_card_evidence,
    research.idea_triage
TO ai_os_research_runtime;

GRANT USAGE, SELECT ON SEQUENCE research.followed_sources_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.followed_source_versions_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.people_or_authors_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.person_source_profiles_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.followed_source_items_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.source_item_entities_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.source_item_claims_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.source_scorecards_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.idea_cards_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.idea_card_evidence_id_seq TO ai_os_research_runtime;
GRANT USAGE, SELECT ON SEQUENCE research.idea_triage_id_seq TO ai_os_research_runtime;

CREATE OR REPLACE VIEW research.v_following_feed
WITH (security_barrier = true, security_invoker = true)
AS
SELECT
    i.scope_key,
    i.id AS source_item_id,
    s.id AS followed_source_id,
    s.source_key,
    i.title,
    i.canonical_url,
    i.author_id,
    p.display_name AS author_name,
    i.published_at,
    i.captured_at,
    i.authority,
    i.trust_score,
    i.quarantine_status,
    i.parser_status,
    i.permitted_excerpt
FROM research.followed_source_items i
JOIN research.followed_sources s
  ON s.scope_key = i.scope_key AND s.id = i.followed_source_id
LEFT JOIN research.people_or_authors p
  ON p.scope_key = i.scope_key AND p.id = i.author_id
WHERE s.status = 'active'
  AND i.quarantine_status IN ('clear', 'reviewed_safe');

CREATE OR REPLACE VIEW research.v_idea_inbox
WITH (security_barrier = true, security_invoker = true)
AS
SELECT
    i.scope_key,
    i.id,
    i.idea_key,
    i.title,
    i.core_claim,
    i.primary_company_id,
    c.display_name AS company_name,
    i.novelty_score,
    i.source_score,
    i.author_score,
    i.status,
    i.created_at,
    i.updated_at
FROM research.idea_cards i
LEFT JOIN research.companies c ON c.id = i.primary_company_id
WHERE i.status IN ('proposed', 'triage', 'researching');

GRANT SELECT ON research.v_following_feed, research.v_idea_inbox TO ai_os_research_runtime;

INSERT INTO core.schema_migrations (
    migration_number,
    migration_key,
    definition_checksum_sha256,
    description,
    metadata
)
VALUES (
    245,
    '245_research_source_following_v1',
    'dd311ae5083375091030387cd763fdb560c192a46af1f2c47f23a2c7436f387f',
    'Scoped versioned source following, author scorecards, claim quarantine and idea triage',
    '{"fetches_started":false,"research_cases_started":false,"private_storage":"external_ssd"}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM core.schema_migrations
        WHERE migration_number = 245
          AND migration_key = '245_research_source_following_v1'
          AND definition_checksum_sha256 = 'dd311ae5083375091030387cd763fdb560c192a46af1f2c47f23a2c7436f387f'
    ) THEN
        RAISE EXCEPTION 'migration 245 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
