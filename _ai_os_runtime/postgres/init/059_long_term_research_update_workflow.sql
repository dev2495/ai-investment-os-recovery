CREATE TABLE IF NOT EXISTS portfolio.holding_thesis_research_updates (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    update_kind TEXT NOT NULL,
    checklist_key TEXT,
    model_key TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    score NUMERIC,
    fair_value_low NUMERIC,
    fair_value_base NUMERIC,
    fair_value_high NUMERIC,
    expected_cagr_pct NUMERIC,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    note_path TEXT,
    created_by TEXT NOT NULL DEFAULT 'AI OS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_holding_thesis_research_updates_thesis ON portfolio.holding_thesis_research_updates (holding_thesis_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_holding_thesis_research_updates_kind ON portfolio.holding_thesis_research_updates (update_kind, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_holding_thesis_research_updates_checklist ON portfolio.holding_thesis_research_updates (holding_thesis_id, checklist_key);
CREATE INDEX IF NOT EXISTS idx_holding_thesis_research_updates_model ON portfolio.holding_thesis_research_updates (holding_thesis_id, model_key);

CREATE OR REPLACE VIEW portfolio.v_long_term_thesis_checklists AS
SELECT
    c.id,
    c.holding_thesis_id,
    ht.symbol,
    ht.exchange,
    ht.company_name,
    c.checklist_key,
    c.checklist_name,
    c.status,
    c.score,
    c.findings,
    c.evidence,
    c.owner_agent,
    c.updated_at,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients
FROM portfolio.holding_thesis_checklists c
JOIN portfolio.holding_theses ht ON ht.id = c.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = ht.id;

CREATE OR REPLACE VIEW portfolio.v_long_term_valuation_models AS
SELECT
    vm.id,
    vm.holding_thesis_id,
    ht.symbol,
    ht.exchange,
    ht.company_name,
    vm.model_key,
    vm.model_name,
    vm.model_type,
    vm.status,
    vm.fair_value_low,
    vm.fair_value_base,
    vm.fair_value_high,
    vm.expected_cagr_pct,
    vm.assumptions,
    vm.outputs,
    vm.note_path,
    vm.owner_agent,
    vm.created_at,
    vm.updated_at,
    control.long_term_gross_exposure,
    control.client_count,
    control.clients
FROM portfolio.holding_valuation_models vm
JOIN portfolio.holding_theses ht ON ht.id = vm.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id = ht.id;

CREATE OR REPLACE VIEW portfolio.v_long_term_research_updates AS
SELECT
    u.id,
    u.holding_thesis_id,
    ht.symbol,
    ht.exchange,
    ht.company_name,
    u.update_kind,
    u.checklist_key,
    u.model_key,
    u.status,
    u.score,
    u.fair_value_low,
    u.fair_value_base,
    u.fair_value_high,
    u.expected_cagr_pct,
    u.findings,
    u.assumptions,
    u.outputs,
    u.evidence,
    u.source_summary,
    u.note_path,
    u.created_by,
    u.created_at
FROM portfolio.holding_thesis_research_updates u
JOIN portfolio.holding_theses ht ON ht.id = u.holding_thesis_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_generate_long_term_research_packet',
        'mcp_tool',
        'Long-Term Portfolio Manager',
        'write_with_approval',
        true,
        'Generate a source-backed long-term research packet from real exposure, latest quotes, filings, and Obsidian notes. Does not approve buy/sell decisions.',
        '{"script":"_ai_os_runtime/scripts/manage_long_term_research.py","action":"packet","writes":["portfolio.holding_thesis_research_updates","knowledge.obsidian_notes","agent.tasks","agent.inbox_items"],"reads":["portfolio.v_long_term_thesis_control","books.v_book_positions","market.v_latest_price_quotes","research.corporate_filings","knowledge.obsidian_notes"],"seed_data_allowed":false}'::jsonb
    ),
    (
        'ai_os_update_long_term_thesis_checklist',
        'mcp_tool',
        'Research Analyst',
        'write_with_approval',
        true,
        'Update a long-term thesis checklist row with sourced findings and evidence.',
        '{"script":"_ai_os_runtime/scripts/manage_long_term_research.py","action":"checklist","writes":["portfolio.holding_thesis_checklists","portfolio.holding_thesis_research_updates"],"reads":["portfolio.holding_thesis_checklists","portfolio.holding_theses"],"seed_data_allowed":false}'::jsonb
    ),
    (
        'ai_os_update_long_term_valuation_model',
        'mcp_tool',
        'Valuation Agent',
        'write_with_approval',
        true,
        'Update a long-term valuation module with explicit assumptions, outputs, evidence, and fair-value range.',
        '{"script":"_ai_os_runtime/scripts/manage_long_term_research.py","action":"valuation","writes":["portfolio.holding_valuation_models","portfolio.holding_theses","portfolio.holding_thesis_research_updates"],"reads":["portfolio.holding_valuation_models","portfolio.holding_theses"],"seed_data_allowed":false}'::jsonb
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
            'portfolio.holding_thesis_research_updates',
            'portfolio.v_long_term_thesis_checklists',
            'portfolio.v_long_term_valuation_models',
            'portfolio.v_long_term_research_updates'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_generate_long_term_research_packet',
            'ai_os_update_long_term_thesis_checklist',
            'ai_os_update_long_term_valuation_model'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Long-term research packet, checklist update, and valuation update workflows are registered; use them to replace placeholders with source-backed evidence.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');
