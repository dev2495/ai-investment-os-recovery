CREATE TABLE IF NOT EXISTS research.special_situation_terms (
    id BIGSERIAL PRIMARY KEY,
    filing_id BIGINT NOT NULL REFERENCES research.corporate_filings(id) ON DELETE CASCADE,
    filing_event_id BIGINT REFERENCES research.filing_events(id) ON DELETE SET NULL,
    extraction_run_id BIGINT REFERENCES research.filing_pdf_extraction_runs(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    record_date TEXT,
    ex_date TEXT,
    meeting_date TEXT,
    opening_date TEXT,
    closing_date TEXT,
    offer_price TEXT,
    issue_price TEXT,
    cash_consideration TEXT,
    swap_ratio TEXT,
    entitlement_ratio TEXT,
    buyback_size TEXT,
    aggregate_amount TEXT,
    timeline_text TEXT,
    conditions_text TEXT,
    raw_terms JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence NUMERIC NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'needs_review',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (filing_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_special_situation_terms_event ON research.special_situation_terms (event_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_special_situation_terms_symbol ON research.special_situation_terms (symbol);
CREATE INDEX IF NOT EXISTS idx_special_situation_terms_status ON research.special_situation_terms (status);

CREATE OR REPLACE VIEW research.v_special_situation_terms AS
SELECT
    sst.id,
    sst.filing_id,
    sst.filing_event_id,
    sst.extraction_run_id,
    cf.source_name,
    cf.exchange,
    coalesce(sst.symbol, cf.symbol) AS symbol,
    coalesce(sst.company_name, cf.company_name) AS company_name,
    cf.title,
    cf.source_url,
    cf.attachment_url,
    cf.local_path,
    sst.event_type,
    sst.record_date,
    sst.ex_date,
    sst.meeting_date,
    sst.opening_date,
    sst.closing_date,
    sst.offer_price,
    sst.issue_price,
    sst.cash_consideration,
    sst.swap_ratio,
    sst.entitlement_ratio,
    sst.buyback_size,
    sst.aggregate_amount,
    sst.timeline_text,
    sst.conditions_text,
    sst.raw_terms,
    sst.confidence,
    sst.status,
    sst.created_at,
    sst.updated_at
FROM research.special_situation_terms sst
JOIN research.corporate_filings cf ON cf.id = sst.filing_id
ORDER BY sst.updated_at DESC, sst.id DESC;

CREATE OR REPLACE VIEW research.v_special_situation_inbox AS
SELECT
    inbox.*,
    terms.id AS special_terms_id,
    terms.record_date,
    terms.offer_price,
    terms.issue_price,
    terms.swap_ratio,
    terms.entitlement_ratio,
    terms.buyback_size,
    terms.aggregate_amount,
    terms.confidence AS terms_confidence,
    terms.status AS terms_status
FROM research.v_corporate_filing_inbox inbox
LEFT JOIN research.special_situation_terms terms
  ON terms.filing_id = inbox.filing_id
 AND terms.event_type = inbox.event_type
WHERE inbox.event_type IN (
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
AND coalesce(inbox.event_status, 'new') <> 'superseded'
ORDER BY inbox.filed_at DESC NULLS LAST, inbox.filing_id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_special_situation_terms', 'mcp_tool', 'Special Situations Agent', 'read_only', true, 'Read structured terms extracted from special situation filings.', '{"reads":["research.v_special_situation_terms","research.v_special_situation_inbox"]}'::jsonb)
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
            'research.special_situation_terms',
            'research.v_special_situation_terms'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_special_situation_terms']::TEXT[]) AS tool
    ),
    next_action = 'Use extracted special-situation terms to build event-driven memos and arbitrage spread tracking.',
    updated_at = now()
WHERE module_key = 'research_inbox';

UPDATE agent.skills
SET output_targets = ARRAY(
        SELECT DISTINCT target
        FROM unnest(output_targets || ARRAY['research.special_situation_terms','research.v_special_situation_terms']::TEXT[]) AS target
    ),
    config = config || '{"structured_terms_status":"deterministic_v1"}'::jsonb,
    updated_at = now()
WHERE skill_key IN ('detect_special_situation', 'corporate_action_detector', 'analyze_corporate_filing');
