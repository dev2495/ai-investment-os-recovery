CREATE TABLE IF NOT EXISTS research.filing_collector_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL,
    connector_key TEXT,
    exchange TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    target_url TEXT,
    http_status INTEGER,
    rows_seen BIGINT NOT NULL DEFAULT 0,
    rows_upserted BIGINT NOT NULL DEFAULT 0,
    events_upserted BIGINT NOT NULL DEFAULT 0,
    inbox_items_created BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'News Analyst'
);

CREATE INDEX IF NOT EXISTS idx_filing_collector_runs_source ON research.filing_collector_runs (source_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_filing_collector_runs_status ON research.filing_collector_runs (status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_filing_events_unique_filing_event
    ON research.filing_events (filing_id, event_type);

ALTER TABLE research.corporate_filings
    ADD COLUMN IF NOT EXISTS collector_run_id BIGINT REFERENCES research.filing_collector_runs(id),
    ADD COLUMN IF NOT EXISTS attachment_url TEXT,
    ADD COLUMN IF NOT EXISTS raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id);

CREATE INDEX IF NOT EXISTS idx_corporate_filings_collector_run ON research.corporate_filings (collector_run_id);
CREATE INDEX IF NOT EXISTS idx_corporate_filings_attachment_url ON research.corporate_filings (attachment_url);

CREATE OR REPLACE VIEW research.v_filing_collector_runs AS
SELECT
    id,
    run_key,
    source_key,
    connector_key,
    exchange,
    status,
    date_from,
    date_to,
    target_url,
    http_status,
    rows_seen,
    rows_upserted,
    events_upserted,
    inbox_items_created,
    started_at,
    finished_at,
    error_message,
    sample_payload,
    created_by
FROM research.filing_collector_runs
ORDER BY started_at DESC, id DESC;

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
    cf.extraction_status,
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
    ('ai_os_run_nse_bse_filing_collector', 'mcp_tool', 'News Analyst', 'browser_read', true, 'Run NSE/BSE filing collector, store filing rows, classify events, and route special situations.', '{"runs":["scripts/collect_nse_bse_filings.py"],"writes":["research.filing_collector_runs","research.corporate_filings","research.filing_events","agent.inbox_items"],"sources":["NSE","BSE"]}'::jsonb),
    ('ai_os_filing_collector_runs', 'mcp_tool', 'News Analyst', 'read_only', true, 'Read NSE/BSE filing collector run history.', '{"reads":["research.v_filing_collector_runs"]}'::jsonb),
    ('ai_os_corporate_filing_inbox', 'mcp_tool', 'Filings Analyst', 'read_only', true, 'Read captured corporate filings and classified filing events.', '{"reads":["research.v_corporate_filing_inbox","research.v_special_situation_inbox"]}'::jsonb)
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
            'research.filing_collector_runs',
            'research.v_filing_collector_runs',
            'research.v_corporate_filing_inbox',
            'research.v_special_situation_inbox'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_run_nse_bse_filing_collector',
            'ai_os_filing_collector_runs',
            'ai_os_corporate_filing_inbox'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use the NSE/BSE filing collector to populate Research Factory and route special situations with source evidence.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'data_sources');

UPDATE agent.skills
SET execution_mode = 'collector_api',
    config = config || '{"collector_status":"api_ready","collector_script":"scripts/collect_nse_bse_filings.py"}'::jsonb,
    input_sources = ARRAY(
        SELECT DISTINCT src
        FROM unnest(input_sources || ARRAY[
            'research.filing_collector_runs',
            'research.corporate_filings',
            'research.filing_events'
        ]::TEXT[]) AS src
    ),
    output_targets = ARRAY(
        SELECT DISTINCT target
        FROM unnest(output_targets || ARRAY[
            'research.v_corporate_filing_inbox',
            'research.v_special_situation_inbox'
        ]::TEXT[]) AS target
    ),
    updated_at = now()
WHERE skill_key = 'nse_bse_announcement_monitor';

