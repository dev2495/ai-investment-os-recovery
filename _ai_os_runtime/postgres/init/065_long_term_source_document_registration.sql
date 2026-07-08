CREATE TABLE IF NOT EXISTS portfolio.long_term_source_documents (
    id BIGSERIAL PRIMARY KEY,
    document_key TEXT NOT NULL UNIQUE,
    source_request_id BIGINT REFERENCES portfolio.long_term_source_requests(id) ON DELETE SET NULL,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    specialist_output_id BIGINT REFERENCES portfolio.long_term_specialist_outputs(id) ON DELETE SET NULL,
    assignment_id BIGINT REFERENCES portfolio.long_term_specialist_assignments(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    company_name TEXT,
    document_type TEXT NOT NULL,
    document_title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT,
    source_name TEXT NOT NULL DEFAULT 'official_company_source',
    provenance_status TEXT NOT NULL DEFAULT 'registered',
    http_status INTEGER,
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
    obsidian_note_id BIGINT REFERENCES knowledge.obsidian_notes(id) ON DELETE SET NULL,
    note_path TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Filings and Transcript Analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_request_id, source_url)
);

CREATE INDEX IF NOT EXISTS idx_long_term_source_documents_symbol
    ON portfolio.long_term_source_documents (symbol, document_type, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_source_documents_request
    ON portfolio.long_term_source_documents (source_request_id, updated_at DESC);

CREATE OR REPLACE VIEW portfolio.v_long_term_source_documents AS
SELECT
    doc.id,
    doc.document_key,
    doc.source_request_id,
    request.request_key,
    doc.holding_thesis_id,
    doc.specialist_output_id,
    doc.assignment_id,
    doc.symbol,
    doc.exchange,
    doc.company_name,
    doc.document_type,
    doc.document_title,
    doc.source_url,
    doc.local_path,
    doc.source_name,
    doc.provenance_status,
    doc.http_status,
    doc.raw_artifact_id,
    artifact.artifact_type,
    artifact.mime_type,
    doc.obsidian_note_id,
    doc.note_path,
    doc.evidence,
    doc.metadata,
    doc.created_by,
    doc.created_at,
    doc.updated_at
FROM portfolio.long_term_source_documents doc
LEFT JOIN portfolio.long_term_source_requests request ON request.id = doc.source_request_id
LEFT JOIN core.raw_artifacts artifact ON artifact.id = doc.raw_artifact_id
ORDER BY doc.updated_at DESC, doc.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_register_long_term_source_document',
        'mcp_tool',
        'Filings and Transcript Analyst',
        'write_with_approval',
        true,
        'Register an official source URL or local document against a Long-Term source request, write source-provenance note, and store raw artifact metadata.',
        '{"script":"_ai_os_runtime/scripts/register_long_term_source_document.py","writes":["portfolio.long_term_source_documents","core.raw_artifacts","knowledge.obsidian_notes"],"reads":["portfolio.v_long_term_source_requests"],"capital_action_allowed":false,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'portfolio.long_term_source_documents',
            'portfolio.v_long_term_source_documents'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_register_long_term_source_document']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term source document registration is available; register official URLs/documents before running satisfaction checks.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');
