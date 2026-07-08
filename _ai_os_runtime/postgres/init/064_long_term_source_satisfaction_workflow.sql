ALTER TABLE portfolio.long_term_source_requests
    ADD COLUMN IF NOT EXISTS satisfied_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS satisfied_by TEXT,
    ADD COLUMN IF NOT EXISTS satisfaction_status TEXT NOT NULL DEFAULT 'unchecked',
    ADD COLUMN IF NOT EXISTS satisfaction_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS matched_source_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS portfolio.long_term_source_request_checks (
    id BIGSERIAL PRIMARY KEY,
    source_request_id BIGINT NOT NULL REFERENCES portfolio.long_term_source_requests(id) ON DELETE CASCADE,
    request_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    source_name TEXT NOT NULL,
    check_status TEXT NOT NULL,
    matched_source_count INTEGER NOT NULL DEFAULT 0,
    matches JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_reason TEXT,
    checked_by TEXT NOT NULL DEFAULT 'Filings and Transcript Analyst',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_long_term_source_request_checks_request
    ON portfolio.long_term_source_request_checks (source_request_id, checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_source_request_checks_status
    ON portfolio.long_term_source_request_checks (check_status, checked_at DESC);

CREATE OR REPLACE VIEW portfolio.v_long_term_source_requests AS
SELECT
    request.id,
    request.request_key,
    request.holding_thesis_id,
    thesis.exchange AS thesis_exchange,
    request.symbol,
    request.exchange,
    request.company_name,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients,
    request.specialist_output_id,
    output.output_status AS specialist_output_status,
    output.source_status AS specialist_source_status,
    request.assignment_id,
    assignment.assignment_key,
    request.committee_review_id,
    request.source_name,
    request.source_category,
    request.priority,
    request.status,
    request.owner_agent,
    request.required_for_module,
    request.required_by_agent,
    request.request_reason,
    request.collection_plan,
    request.evidence,
    request.task_id,
    task.status AS task_status,
    task.output_note_path AS task_output_note_path,
    request.inbox_id,
    inbox.status AS inbox_status,
    request.note_path,
    request.created_by,
    request.created_at,
    request.updated_at,
    request.satisfaction_status,
    request.matched_source_count,
    request.last_checked_at,
    request.satisfied_at,
    request.satisfied_by,
    request.satisfaction_evidence
FROM portfolio.long_term_source_requests request
JOIN portfolio.holding_theses thesis ON thesis.id = request.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = thesis.id
LEFT JOIN portfolio.long_term_specialist_outputs output ON output.id = request.specialist_output_id
LEFT JOIN portfolio.long_term_specialist_assignments assignment ON assignment.id = request.assignment_id
LEFT JOIN agent.tasks task ON task.id = request.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = request.inbox_id
ORDER BY
    CASE request.status WHEN 'queued' THEN 1 WHEN 'collecting' THEN 2 WHEN 'needs_review' THEN 3 WHEN 'satisfied' THEN 4 ELSE 5 END,
    CASE request.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    request.updated_at DESC;

CREATE OR REPLACE VIEW portfolio.v_long_term_source_request_checks AS
SELECT
    check_row.id,
    check_row.source_request_id,
    check_row.request_key,
    request.holding_thesis_id,
    request.specialist_output_id,
    request.assignment_id,
    check_row.symbol,
    request.exchange,
    request.company_name,
    check_row.source_name,
    request.source_category,
    request.required_for_module,
    request.required_by_agent,
    check_row.check_status,
    check_row.matched_source_count,
    check_row.matches,
    check_row.missing_reason,
    check_row.checked_by,
    check_row.checked_at,
    request.status AS request_status,
    request.task_id,
    task.status AS task_status,
    request.inbox_id,
    inbox.status AS inbox_status
FROM portfolio.long_term_source_request_checks check_row
JOIN portfolio.long_term_source_requests request ON request.id = check_row.source_request_id
LEFT JOIN agent.tasks task ON task.id = request.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = request.inbox_id
ORDER BY check_row.checked_at DESC, check_row.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_check_long_term_source_satisfaction',
        'mcp_tool',
        'Filings and Transcript Analyst',
        'write_with_approval',
        true,
        'Check whether queued Long-Term source requests have been satisfied by real filings, raw artifacts, or source-provenance Obsidian notes.',
        '{"script":"_ai_os_runtime/scripts/check_long_term_source_satisfaction.py","writes":["portfolio.long_term_source_request_checks","portfolio.long_term_source_requests","agent.tasks","agent.inbox_items"],"reads":["portfolio.v_long_term_source_requests","research.corporate_filings","core.raw_artifacts","knowledge.obsidian_notes"],"capital_action_allowed":false,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'portfolio.long_term_source_request_checks',
            'portfolio.v_long_term_source_request_checks'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_check_long_term_source_satisfaction']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term source satisfaction workflow is registered; check queued source requests after filings/artifacts arrive.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');
