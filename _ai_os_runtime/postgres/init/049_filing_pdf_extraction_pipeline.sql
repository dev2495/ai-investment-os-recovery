CREATE TABLE IF NOT EXISTS research.filing_pdf_extraction_runs (
    id BIGSERIAL PRIMARY KEY,
    filing_id BIGINT NOT NULL REFERENCES research.corporate_filings(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'started',
    source_url TEXT,
    local_pdf_path TEXT,
    parser_name TEXT,
    bytes_downloaded BIGINT,
    page_count INTEGER,
    extracted_chars BIGINT NOT NULL DEFAULT 0,
    event_type_before TEXT,
    event_type_after TEXT,
    classifier_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_by TEXT NOT NULL DEFAULT 'Filings Analyst'
);

CREATE INDEX IF NOT EXISTS idx_filing_pdf_extraction_runs_filing ON research.filing_pdf_extraction_runs (filing_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_filing_pdf_extraction_runs_status ON research.filing_pdf_extraction_runs (status);

ALTER TABLE research.corporate_filings
    ADD COLUMN IF NOT EXISTS pdf_page_count INTEGER,
    ADD COLUMN IF NOT EXISTS pdf_extracted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS pdf_extraction_run_id BIGINT REFERENCES research.filing_pdf_extraction_runs(id),
    ADD COLUMN IF NOT EXISTS classification_payload JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_corporate_filings_pdf_extracted_at ON research.corporate_filings (pdf_extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_corporate_filings_pdf_extraction_run ON research.corporate_filings (pdf_extraction_run_id);

CREATE OR REPLACE VIEW research.v_filing_pdf_extraction_runs AS
SELECT
    r.id,
    r.filing_id,
    cf.source_name,
    cf.exchange,
    cf.symbol,
    cf.company_name,
    cf.title,
    r.status,
    r.source_url,
    r.local_pdf_path,
    r.parser_name,
    r.bytes_downloaded,
    r.page_count,
    r.extracted_chars,
    r.event_type_before,
    r.event_type_after,
    r.classifier_payload,
    r.started_at,
    r.finished_at,
    r.error_message,
    r.created_by
FROM research.filing_pdf_extraction_runs r
JOIN research.corporate_filings cf ON cf.id = r.filing_id
ORDER BY r.started_at DESC, r.id DESC;

DROP VIEW IF EXISTS research.v_special_situation_inbox;
DROP VIEW IF EXISTS research.v_corporate_filing_inbox;

CREATE OR REPLACE VIEW research.v_corporate_filing_inbox AS
SELECT
    cf.id AS filing_id,
    cf.source_name,
    cf.exchange,
    cf.symbol,
    cf.company_name,
    cf.filing_type,
    cf.event_type AS filing_event_type,
    cf.title,
    cf.filed_at,
    cf.source_url,
    cf.attachment_url,
    cf.local_path,
    cf.extraction_status,
    cf.pdf_page_count,
    cf.pdf_extracted_at,
    cf.pdf_extraction_run_id,
    cf.classification_payload,
    cf.collector_run_id,
    fcr.run_key,
    fe.id AS event_id,
    fe.event_type,
    fe.opportunity_score,
    fe.risk_score,
    fe.urgency,
    fe.status AS event_status,
    fe.assigned_agent,
    fe.created_at AS event_created_at,
    cf.created_at AS filing_created_at
FROM research.corporate_filings cf
LEFT JOIN research.filing_collector_runs fcr ON fcr.id = cf.collector_run_id
LEFT JOIN research.filing_events fe ON fe.filing_id = cf.id
ORDER BY coalesce(cf.filed_at, cf.created_at) DESC, cf.id DESC, fe.id DESC;

CREATE OR REPLACE VIEW research.v_special_situation_inbox AS
SELECT *
FROM research.v_corporate_filing_inbox
WHERE event_type IN (
    'demerger',
    'merger',
    'reverse_merger',
    'scheme_arrangement',
    'buyback',
    'open_offer',
    'delisting',
    'rights_issue',
    'preferential_allotment',
    'asset_sale',
    'pledge_change',
    'insolvency',
    'arbitrage_watch',
    'board_action'
)
ORDER BY filed_at DESC NULLS LAST, filing_id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_extract_filing_pdf_text', 'mcp_tool', 'Filings Analyst', 'document_read', true, 'Download filing PDFs, extract text, update filing classification, and route special situations.', '{"runs":["scripts/extract_filing_pdfs.py"],"writes":["research.filing_pdf_extraction_runs","research.corporate_filings","research.filing_events","agent.inbox_items","core.raw_artifacts"],"reads":["research.v_corporate_filing_inbox"]}'::jsonb),
    ('ai_os_filing_pdf_extraction_runs', 'mcp_tool', 'Filings Analyst', 'read_only', true, 'Read filing PDF extraction run history.', '{"reads":["research.v_filing_pdf_extraction_runs"]}'::jsonb)
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
            'research.filing_pdf_extraction_runs',
            'research.v_filing_pdf_extraction_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_extract_filing_pdf_text',
            'ai_os_filing_pdf_extraction_runs'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Extract filing PDFs, update filing classifications, and route material events to research agents.',
    updated_at = now()
WHERE module_key = 'research_inbox';

UPDATE agent.skills
SET execution_mode = 'document_extraction_api',
    config = config || '{"pdf_extractor_status":"api_ready","pdf_extractor_script":"scripts/extract_filing_pdfs.py"}'::jsonb,
    input_sources = ARRAY(
        SELECT DISTINCT src
        FROM unnest(input_sources || ARRAY[
            'research.corporate_filings',
            'research.filing_pdf_extraction_runs'
        ]::TEXT[]) AS src
    ),
    output_targets = ARRAY(
        SELECT DISTINCT target
        FROM unnest(output_targets || ARRAY[
            'research.filing_events',
            'agent.inbox_items',
            'research.v_special_situation_inbox'
        ]::TEXT[]) AS target
    ),
    updated_at = now()
WHERE skill_key IN ('analyze_corporate_filing', 'detect_special_situation', 'corporate_action_detector');
