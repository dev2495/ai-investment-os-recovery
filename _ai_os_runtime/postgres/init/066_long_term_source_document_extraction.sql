CREATE TABLE IF NOT EXISTS portfolio.long_term_source_document_extractions (
    id BIGSERIAL PRIMARY KEY,
    source_document_id BIGINT NOT NULL REFERENCES portfolio.long_term_source_documents(id) ON DELETE CASCADE,
    source_request_id BIGINT REFERENCES portfolio.long_term_source_requests(id) ON DELETE SET NULL,
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_title TEXT NOT NULL,
    source_url TEXT,
    local_pdf_path TEXT,
    local_text_path TEXT,
    parser_name TEXT NOT NULL,
    page_count INTEGER,
    extracted_chars INTEGER NOT NULL DEFAULT 0,
    text_excerpt TEXT,
    key_snippets JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_status TEXT NOT NULL DEFAULT 'extracted',
    error TEXT,
    extracted_by TEXT NOT NULL DEFAULT 'Filings and Transcript Analyst',
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_document_id, parser_name)
);

CREATE INDEX IF NOT EXISTS idx_long_term_source_document_extractions_symbol
    ON portfolio.long_term_source_document_extractions (symbol, extracted_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_source_document_extractions_document
    ON portfolio.long_term_source_document_extractions (source_document_id, extracted_at DESC);

CREATE OR REPLACE VIEW portfolio.v_long_term_source_document_extractions AS
SELECT
    extraction.id,
    extraction.source_document_id,
    document.document_key,
    extraction.source_request_id,
    request.request_key,
    extraction.raw_artifact_id,
    extraction.symbol,
    document.exchange,
    document.company_name,
    extraction.document_type,
    extraction.document_title,
    extraction.source_url,
    extraction.local_pdf_path,
    extraction.local_text_path,
    extraction.parser_name,
    extraction.page_count,
    extraction.extracted_chars,
    extraction.text_excerpt,
    extraction.key_snippets,
    extraction.extraction_status,
    extraction.error,
    extraction.extracted_by,
    extraction.extracted_at,
    extraction.updated_at
FROM portfolio.long_term_source_document_extractions extraction
JOIN portfolio.long_term_source_documents document ON document.id = extraction.source_document_id
LEFT JOIN portfolio.long_term_source_requests request ON request.id = extraction.source_request_id
ORDER BY extraction.extracted_at DESC, extraction.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_extract_long_term_source_document',
        'mcp_tool',
        'Filings and Transcript Analyst',
        'document_read',
        true,
        'Download and extract text from registered Long-Term source documents for source-backed specialist research.',
        '{"script":"_ai_os_runtime/scripts/extract_long_term_source_document.py","writes":["portfolio.long_term_source_document_extractions","core.raw_artifacts"],"reads":["portfolio.v_long_term_source_documents"],"capital_action_allowed":false,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'portfolio.long_term_source_document_extractions',
            'portfolio.v_long_term_source_document_extractions'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_extract_long_term_source_document']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term source document extraction is available; extract registered source documents before rerunning research-heavy specialists.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');

