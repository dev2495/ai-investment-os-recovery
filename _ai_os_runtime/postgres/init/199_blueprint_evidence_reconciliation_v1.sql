CREATE TABLE IF NOT EXISTS core.os_blueprint_evidence_links (
    id BIGSERIAL PRIMARY KEY,
    requirement_key TEXT NOT NULL REFERENCES core.os_blueprint_requirements(requirement_key) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    evidence_key TEXT NOT NULL,
    evidence_note_path TEXT,
    evidence_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (evidence_status IN ('candidate', 'verified', 'rejected')),
    evidence_summary TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_record JSONB NOT NULL DEFAULT '{}'::jsonb,
    review_rationale TEXT,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (requirement_key, evidence_type, evidence_key)
);

CREATE INDEX IF NOT EXISTS idx_os_blueprint_evidence_requirement
ON core.os_blueprint_evidence_links(requirement_key, evidence_status, updated_at DESC);

CREATE TABLE IF NOT EXISTS core.os_blueprint_reconciliation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'completed',
    candidate_count INTEGER NOT NULL DEFAULT 0,
    verified_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    actor TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW core.v_os_blueprint_evidence_links AS
SELECT
    evidence.id,
    evidence.requirement_key,
    requirement.requirement_name,
    requirement.domain_key,
    evidence.evidence_type,
    evidence.evidence_key,
    evidence.evidence_note_path,
    evidence.evidence_status,
    evidence.evidence_summary,
    evidence.source_system,
    evidence.source_record,
    evidence.review_rationale,
    evidence.verified_by,
    evidence.verified_at,
    evidence.metadata,
    evidence.created_at,
    evidence.updated_at
FROM core.os_blueprint_evidence_links evidence
JOIN core.os_blueprint_requirements requirement USING(requirement_key);

CREATE OR REPLACE VIEW core.v_os_blueprint_requirements AS
WITH evidence AS (
    SELECT
        requirement_key,
        count(*) FILTER (WHERE evidence_status = 'candidate')::BIGINT AS candidate_evidence_count,
        count(*) FILTER (WHERE evidence_status = 'verified')::BIGINT AS verified_evidence_count,
        count(*) FILTER (WHERE evidence_status = 'rejected')::BIGINT AS rejected_evidence_count,
        max(updated_at) AS latest_evidence_at,
        coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', id,
                    'evidence_type', evidence_type,
                    'evidence_key', evidence_key,
                    'evidence_note_path', evidence_note_path,
                    'evidence_status', evidence_status,
                    'evidence_summary', evidence_summary,
                    'source_system', source_system,
                    'source_record', source_record,
                    'review_rationale', review_rationale,
                    'verified_by', verified_by,
                    'verified_at', verified_at,
                    'updated_at', updated_at
                ) ORDER BY updated_at DESC, id DESC
            ),
            '[]'::jsonb
        ) AS evidence_links
    FROM core.os_blueprint_evidence_links
    GROUP BY requirement_key
)
SELECT
    version.blueprint_key,
    version.version_label,
    requirement.requirement_key,
    requirement.requirement_name,
    requirement.requirement_type,
    requirement.priority,
    requirement.current_status,
    requirement.owner_agent,
    requirement.owner_department,
    domain.domain_key,
    domain.domain_name,
    domain.section_number,
    domain.domain_type,
    domain.primary_workspace,
    requirement.mapped_object_type,
    requirement.mapped_object_key,
    CASE
        WHEN requirement.mapped_object_type = 'control_module' THEN module.status
        WHEN requirement.mapped_object_type = 'book' THEN book.status
        WHEN requirement.mapped_object_type = 'agent' THEN profile.status
        WHEN requirement.mapped_object_type = 'tool' THEN CASE WHEN tool.enabled THEN 'enabled' ELSE 'disabled' END
        WHEN requirement.mapped_object_type = 'data_source' THEN source.status
        WHEN requirement.mapped_object_type = 'note' THEN 'note_recorded'
        WHEN coalesce(evidence.verified_evidence_count, 0) > 0 THEN 'evidence_verified'
        ELSE NULL
    END AS mapped_object_status,
    (
        CASE
            WHEN requirement.mapped_object_type = 'control_module' AND module.module_key IS NOT NULL THEN true
            WHEN requirement.mapped_object_type = 'book' AND book.book_key IS NOT NULL THEN true
            WHEN requirement.mapped_object_type = 'agent' AND profile.agent_name IS NOT NULL THEN true
            WHEN requirement.mapped_object_type = 'tool' AND tool.tool_name IS NOT NULL THEN true
            WHEN requirement.mapped_object_type = 'data_source' AND source.source_key IS NOT NULL THEN true
            WHEN requirement.mapped_object_type = 'note' THEN true
            ELSE false
        END
        OR coalesce(evidence.verified_evidence_count, 0) > 0
    ) AS mapped_object_found,
    requirement.evidence_note_path,
    requirement.acceptance_criteria,
    requirement.next_action,
    requirement.metadata,
    requirement.updated_at,
    coalesce(evidence.candidate_evidence_count, 0) AS candidate_evidence_count,
    coalesce(evidence.verified_evidence_count, 0) AS verified_evidence_count,
    coalesce(evidence.rejected_evidence_count, 0) AS rejected_evidence_count,
    evidence.latest_evidence_at,
    coalesce(evidence.evidence_links, '[]'::jsonb) AS evidence_links,
    CASE
        WHEN coalesce(evidence.verified_evidence_count, 0) > 0 THEN 'verified'
        WHEN coalesce(evidence.candidate_evidence_count, 0) > 0 THEN 'needs_review'
        WHEN requirement.current_status = 'done' THEN 'evidence_missing'
        ELSE 'unmapped'
    END AS delivery_review_state
FROM core.os_blueprint_versions version
JOIN core.os_blueprint_domains domain ON domain.blueprint_key = version.blueprint_key
JOIN core.os_blueprint_requirements requirement ON requirement.domain_key = domain.domain_key
LEFT JOIN core.control_plane_modules module
    ON requirement.mapped_object_type = 'control_module'
   AND module.module_key = requirement.mapped_object_key
LEFT JOIN books.investment_books book
    ON requirement.mapped_object_type = 'book'
   AND book.book_key = requirement.mapped_object_key
LEFT JOIN agent.profiles profile
    ON requirement.mapped_object_type = 'agent'
   AND profile.agent_name = requirement.mapped_object_key
LEFT JOIN agent.tool_registry tool
    ON requirement.mapped_object_type = 'tool'
   AND tool.tool_name = requirement.mapped_object_key
LEFT JOIN core.data_source_registry source
    ON requirement.mapped_object_type = 'data_source'
   AND source.source_key = requirement.mapped_object_key
LEFT JOIN evidence ON evidence.requirement_key = requirement.requirement_key
WHERE version.status = 'canonical';

COMMENT ON TABLE core.os_blueprint_evidence_links IS
'Append-only candidate and human-reviewed evidence for canonical blueprint requirements. Agent output never verifies itself.';

COMMENT ON TABLE core.os_blueprint_reconciliation_runs IS
'Auditable scans that link task and worker evidence to blueprint requirements. These scans never permit broker writes.';
