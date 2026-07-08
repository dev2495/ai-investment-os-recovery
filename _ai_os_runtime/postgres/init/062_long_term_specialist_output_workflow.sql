CREATE TABLE IF NOT EXISTS portfolio.long_term_specialist_outputs (
    id BIGSERIAL PRIMARY KEY,
    output_key TEXT NOT NULL UNIQUE,
    assignment_id BIGINT NOT NULL REFERENCES portfolio.long_term_specialist_assignments(id) ON DELETE CASCADE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    committee_review_id BIGINT REFERENCES portfolio.long_term_committee_reviews(id) ON DELETE SET NULL,
    module_key TEXT NOT NULL,
    module_name TEXT NOT NULL,
    assignment_type TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE SET NULL,
    output_status TEXT NOT NULL DEFAULT 'draft',
    source_status TEXT NOT NULL DEFAULT 'source_required',
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence TEXT NOT NULL DEFAULT 'low',
    note_path TEXT,
    generated_by TEXT NOT NULL DEFAULT 'AI OS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assignment_id)
);

CREATE INDEX IF NOT EXISTS idx_long_term_specialist_outputs_thesis
    ON portfolio.long_term_specialist_outputs (holding_thesis_id, module_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_specialist_outputs_agent
    ON portfolio.long_term_specialist_outputs (agent_name, output_status, updated_at DESC);

CREATE OR REPLACE VIEW portfolio.v_long_term_specialist_outputs AS
SELECT
    output.id,
    output.output_key,
    output.assignment_id,
    assignment.assignment_key,
    output.holding_thesis_id,
    thesis.symbol,
    thesis.exchange,
    thesis.company_name,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients,
    output.committee_review_id,
    committee.review_status AS committee_review_status,
    committee.decision_status AS committee_decision_status,
    output.module_key,
    output.module_name,
    output.assignment_type,
    output.agent_name,
    profile.display_title,
    profile.department,
    output.skill_key,
    skill.skill_name,
    output.output_status,
    output.source_status,
    output.findings,
    output.source_gaps,
    output.evidence,
    output.recommendations,
    output.metrics,
    output.confidence,
    output.note_path,
    assignment.status AS assignment_status,
    assignment.task_id,
    task.status AS task_status,
    task.output_note_path AS task_output_note_path,
    assignment.inbox_id,
    inbox.status AS inbox_status,
    assignment.message_id,
    message.status AS message_status,
    output.generated_by,
    output.created_at,
    output.updated_at
FROM portfolio.long_term_specialist_outputs output
JOIN portfolio.long_term_specialist_assignments assignment ON assignment.id = output.assignment_id
JOIN portfolio.holding_theses thesis ON thesis.id = output.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = thesis.id
LEFT JOIN portfolio.long_term_committee_reviews committee ON committee.id = output.committee_review_id
LEFT JOIN agent.profiles profile ON profile.agent_name = output.agent_name
LEFT JOIN agent.skills skill ON skill.skill_key = output.skill_key
LEFT JOIN agent.tasks task ON task.id = assignment.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = assignment.inbox_id
LEFT JOIN agent.agent_messages message ON message.id = assignment.message_id
ORDER BY output.updated_at DESC, output.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_execute_long_term_specialist_assignment',
        'mcp_tool',
        'Jarvis',
        'write_with_approval',
        true,
        'Execute a queued Long-Term specialist assignment into an auditable source-backed output note and update task/inbox/message state.',
        '{"script":"_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py","writes":["portfolio.long_term_specialist_outputs","portfolio.long_term_specialist_assignments","portfolio.holding_thesis_research_updates","portfolio.holding_thesis_checklists","portfolio.holding_valuation_models","agent.tasks","agent.inbox_items","agent.agent_messages","knowledge.obsidian_notes"],"reads":["portfolio.v_long_term_specialist_assignments","portfolio.v_long_term_thesis_control","books.v_book_positions","books.v_symbol_book_exposure","market.v_latest_price_quotes","research.corporate_filings","knowledge.obsidian_notes"],"capital_action_allowed":false,"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'portfolio.long_term_specialist_outputs',
            'portfolio.v_long_term_specialist_outputs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_execute_long_term_specialist_assignment']::TEXT[]) AS tool
    ),
    next_action = 'Long-Term specialist execution workflow is registered; run assignments to produce source-backed analyst outputs.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox');
