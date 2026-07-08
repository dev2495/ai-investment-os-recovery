CREATE TABLE IF NOT EXISTS portfolio.long_term_source_requests (
    id BIGSERIAL PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    specialist_output_id BIGINT REFERENCES portfolio.long_term_specialist_outputs(id) ON DELETE CASCADE,
    assignment_id BIGINT REFERENCES portfolio.long_term_specialist_assignments(id) ON DELETE SET NULL,
    committee_review_id BIGINT REFERENCES portfolio.long_term_committee_reviews(id) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    company_name TEXT,
    source_name TEXT NOT NULL,
    source_category TEXT NOT NULL DEFAULT 'filing',
    priority TEXT NOT NULL DEFAULT 'high',
    status TEXT NOT NULL DEFAULT 'queued',
    owner_agent TEXT NOT NULL DEFAULT 'Filings and Transcript Analyst',
    required_for_module TEXT,
    required_by_agent TEXT,
    request_reason TEXT,
    collection_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    note_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id, source_name, required_for_module)
);

CREATE INDEX IF NOT EXISTS idx_long_term_source_requests_status
    ON portfolio.long_term_source_requests (status, priority, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_source_requests_symbol
    ON portfolio.long_term_source_requests (symbol, status, updated_at DESC);

INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets, display_title,
    persona, operating_style, mental_models, escalation_rules, daily_cadence,
    cost_policy, human_interface
)
VALUES
    (
        'Filings and Transcript Analyst',
        'research',
        'Owns collection and verification of annual reports, exchange filings, transcripts, investor presentations, and source packets required by Long-Term specialist agents.',
        'filing_analysis',
        ARRAY['postgres_read_model','browser_research_runner','document_parser','filing_event_reader','obsidian_note_index'],
        'write_with_approval',
        'active',
        '{"source_urls_required":true,"no_investment_opinion":true,"preserve_original_documents":true}'::jsonb,
        ARRAY['portfolio.long_term_source_requests','research.corporate_filings','knowledge.obsidian_notes','agent.inbox_items'],
        'Filings and Transcript Analyst',
        'Precise, document-first, and provenance-obsessed. Turns missing evidence into source packets.',
        'Finds official documents, captures URL/date/source, routes PDF extraction, and tells specialists exactly what is still missing.',
        ARRAY['provenance','primary_sources','audit_trail','document_truth','date_discipline'],
        '{"escalate_to_browser_agent_for":["login_or_browser_required"],"escalate_to_charlie_for":["source_unavailable"],"block_if":["no_primary_source"]}'::jsonb,
        'Daily source gap queue and after every specialist output that has missing evidence.',
        'local_first_escalate_for_large_pdf',
        'Use when Long-Term modules need filings, annual reports, transcripts, or investor presentations.'
    )
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    display_title = EXCLUDED.display_title,
    persona = EXCLUDED.persona,
    operating_style = EXCLUDED.operating_style,
    mental_models = EXCLUDED.mental_models,
    escalation_rules = EXCLUDED.escalation_rules,
    daily_cadence = EXCLUDED.daily_cadence,
    cost_policy = EXCLUDED.cost_policy,
    human_interface = EXCLUDED.human_interface,
    updated_at = now();

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
)
VALUES
    (
        'long_term_source_acquisition',
        'Long-Term Source Acquisition',
        'long_term_research',
        'source_collection',
        'research',
        'active',
        'worker_deterministic',
        'write_with_approval',
        ARRAY['collect long term sources','source gaps','annual report needed','filings needed'],
        ARRAY['portfolio.v_long_term_specialist_outputs','portfolio.long_term_source_requests','research.corporate_filings'],
        ARRAY['portfolio.long_term_source_requests','agent.tasks','agent.inbox_items','knowledge.obsidian_notes'],
        ARRAY['postgres_read_model','browser_research_runner','document_parser'],
        'Source acquisition creates evidence requests and does not make investment recommendations.',
        'Convert specialist source gaps into concrete collection requests with official-source preference, owner, priority, and collector hints.',
        '{"capital_action_allowed":false,"live_execution_allowed":false,"official_sources_first":["NSE","BSE","company_website","annual_report","investor_relations"]}'::jsonb
    )
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name = EXCLUDED.skill_name,
    skill_family = EXCLUDED.skill_family,
    skill_type = EXCLUDED.skill_type,
    owner_department = EXCLUDED.owner_department,
    status = EXCLUDED.status,
    execution_mode = EXCLUDED.execution_mode,
    permission_level = EXCLUDED.permission_level,
    trigger_phrases = EXCLUDED.trigger_phrases,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    required_tools = EXCLUDED.required_tools,
    risk_notes = EXCLUDED.risk_notes,
    prompt_template = EXCLUDED.prompt_template,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Filings and Transcript Analyst','long_term_source_acquisition','expert',true,'{"default_for":"long-term source gaps"}'::jsonb),
    ('Filings and Transcript Analyst','analyze_corporate_filing','expert',false,'{"uses":"source packet verification"}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

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
    request.updated_at
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

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_create_long_term_source_requests',
        'mcp_tool',
        'Filings and Transcript Analyst',
        'write_with_approval',
        true,
        'Create source acquisition requests from Long-Term specialist output source gaps and route them to the filings/transcripts inbox.',
        '{"script":"_ai_os_runtime/scripts/create_long_term_source_requests.py","writes":["portfolio.long_term_source_requests","agent.tasks","agent.inbox_items","knowledge.obsidian_notes"],"reads":["portfolio.v_long_term_specialist_outputs","portfolio.v_long_term_specialist_assignments","research.corporate_filings"],"capital_action_allowed":false,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'portfolio.long_term_source_requests',
            'portfolio.v_long_term_source_requests'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_create_long_term_source_requests']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term source request workflow is registered; convert specialist source gaps into filings/transcripts collection work.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');
