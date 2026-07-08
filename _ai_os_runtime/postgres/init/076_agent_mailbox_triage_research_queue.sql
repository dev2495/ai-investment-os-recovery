CREATE OR REPLACE VIEW research.v_research_factory_queue_summary AS
SELECT
    'filing_collector_runs'::TEXT AS queue_key,
    'Filing Collector Runs'::TEXT AS queue_name,
    'News Analyst'::TEXT AS owner_agent,
    count(*)::BIGINT AS total_rows,
    count(*) FILTER (WHERE status IN ('started', 'running', 'queued'))::BIGINT AS open_rows,
    count(*) FILTER (WHERE status IN ('error', 'failed', 'blocked'))::BIGINT AS blocked_or_error_rows,
    max(coalesce(finished_at, started_at)) AS latest_activity_at,
    'Run or inspect NSE/BSE collector jobs and errors before filing analysis.'::TEXT AS next_action
FROM research.v_filing_collector_runs

UNION ALL

SELECT
    'corporate_filing_inbox',
    'Corporate Filing Inbox',
    'Filings Analyst',
    count(*)::BIGINT,
    count(*) FILTER (WHERE coalesce(extraction_status, 'captured') IN ('captured', 'pending', 'queued'))::BIGINT,
    count(*) FILTER (WHERE coalesce(extraction_status, '') IN ('error', 'failed', 'blocked'))::BIGINT,
    max(coalesce(filed_at, filing_created_at)),
    'Extract PDFs and classify material filings with source URLs attached.'
FROM research.v_corporate_filing_inbox

UNION ALL

SELECT
    'special_situation_inbox',
    'Special Situation Inbox',
    'Special Situations Agent',
    count(*)::BIGINT,
    count(*) FILTER (
        WHERE special_terms_id IS NULL
           OR special_memo_id IS NULL
           OR coalesce(special_memo_approval_status, 'pending') = 'pending'
    )::BIGINT,
    count(*) FILTER (WHERE coalesce(event_status, '') IN ('error', 'failed', 'blocked'))::BIGINT,
    max(coalesce(event_created_at, filing_created_at, filed_at)),
    'Extract terms, generate memo, calculate spread, and route decision without trade authorization.'
FROM research.v_special_situation_inbox

UNION ALL

SELECT
    'filing_pdf_extraction_runs',
    'Filing PDF Extraction Runs',
    'Filings Analyst',
    count(*)::BIGINT,
    count(*) FILTER (WHERE status IN ('started', 'running', 'queued', 'pending'))::BIGINT,
    count(*) FILTER (WHERE status IN ('error', 'failed', 'blocked'))::BIGINT,
    max(coalesce(finished_at, started_at)),
    'Review PDF extraction failures and rerun only when source artifacts are available.'
FROM research.v_filing_pdf_extraction_runs

UNION ALL

SELECT
    'special_situation_terms',
    'Special Situation Terms',
    'Special Situations Agent',
    count(*)::BIGINT,
    count(*) FILTER (WHERE status IN ('draft', 'extracted', 'needs_review', 'pending'))::BIGINT,
    count(*) FILTER (WHERE status IN ('error', 'failed', 'blocked'))::BIGINT,
    max(updated_at),
    'Turn extracted dates/prices/ratios into source-backed memos and spread checks.'
FROM research.v_special_situation_terms

UNION ALL

SELECT
    'special_situation_memos',
    'Special Situation Memos',
    'Special Situations Agent',
    count(*)::BIGINT,
    count(*) FILTER (WHERE coalesce(approval_status, 'pending') = 'pending')::BIGINT,
    count(*) FILTER (WHERE memo_status IN ('error', 'failed', 'blocked'))::BIGINT,
    max(updated_at),
    'Resolve committee-style monitor/research/reject decisions; no trade approval is implied.'
FROM research.v_special_situation_memos

UNION ALL

SELECT
    'research_agent_messages',
    'Research Agent Messages',
    'Research Analyst',
    count(*)::BIGINT,
    count(*) FILTER (WHERE status IN ('unread', 'acknowledged') OR processing_status IN ('pending', 'ready_for_task'))::BIGINT,
    count(*) FILTER (WHERE processing_status IN ('error', 'blocked'))::BIGINT,
    max(created_at),
    'Triage unread research-office messages into tasks, inbox items, or read acknowledgements.'
FROM agent.v_agent_message_threads
WHERE to_agent IN ('Research Analyst', 'News Analyst', 'Filings Analyst', 'Special Situations Agent')
   OR from_agent IN ('Research Analyst', 'News Analyst', 'Filings Analyst', 'Special Situations Agent');

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_research_factory_queue_summary', 'mcp_tool', 'Research Analyst', 'read_only', true, 'Summarize filings, special situations, and research-agent message queues.', '{"reads":["research.v_research_factory_queue_summary"]}'::jsonb),
    ('ai_os_triage_agent_message', 'mcp_tool', 'Jarvis', 'write_with_approval', true, 'Mark an agent message read/acknowledged or route it into a task and inbox item.', '{"writes":["agent.agent_messages","agent.tasks","agent.inbox_items"],"reads":["agent.v_agent_message_threads"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET
    warehouse_objects = (
        SELECT ARRAY(
            SELECT DISTINCT item
            FROM unnest(warehouse_objects || ARRAY['research.v_research_factory_queue_summary']::TEXT[]) AS item
            ORDER BY item
        )
    ),
    mcp_tools = (
        SELECT ARRAY(
            SELECT DISTINCT item
            FROM unnest(mcp_tools || ARRAY['ai_os_research_factory_queue_summary','ai_os_triage_agent_message']::TEXT[]) AS item
            ORDER BY item
        )
    ),
    next_action = 'Use research queue summary and mailbox triage to route filings/news/special situations into explicit tasks.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'agent_office');
