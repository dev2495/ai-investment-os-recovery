ALTER TABLE portfolio.holding_theses
    ADD COLUMN IF NOT EXISTS company_name TEXT,
    ADD COLUMN IF NOT EXISTS thesis_title TEXT,
    ADD COLUMN IF NOT EXISTS thesis_version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS primary_owner_agent TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    ADD COLUMN IF NOT EXISTS investment_book_key TEXT NOT NULL DEFAULT 'long_term',
    ADD COLUMN IF NOT EXISTS purpose_key TEXT,
    ADD COLUMN IF NOT EXISTS thesis_summary TEXT,
    ADD COLUMN IF NOT EXISTS business_model TEXT,
    ADD COLUMN IF NOT EXISTS industry_structure TEXT,
    ADD COLUMN IF NOT EXISTS moat_score NUMERIC,
    ADD COLUMN IF NOT EXISTS management_score NUMERIC,
    ADD COLUMN IF NOT EXISTS governance_score NUMERIC,
    ADD COLUMN IF NOT EXISTS capital_allocation_score NUMERIC,
    ADD COLUMN IF NOT EXISTS financial_quality_score NUMERIC,
    ADD COLUMN IF NOT EXISTS forensic_accounting_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS valuation_status TEXT NOT NULL DEFAULT 'not_started',
    ADD COLUMN IF NOT EXISTS base_case_fair_value NUMERIC,
    ADD COLUMN IF NOT EXISTS bear_case_fair_value NUMERIC,
    ADD COLUMN IF NOT EXISTS bull_case_fair_value NUMERIC,
    ADD COLUMN IF NOT EXISTS expected_cagr_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS monte_carlo_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS thesis_killers JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS exit_criteria TEXT,
    ADD COLUMN IF NOT EXISTS review_frequency TEXT NOT NULL DEFAULT 'quarterly',
    ADD COLUMN IF NOT EXISTS decision_status TEXT NOT NULL DEFAULT 'research_required',
    ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'AI OS',
    ADD COLUMN IF NOT EXISTS updated_by TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_holding_theses_status ON portfolio.holding_theses (thesis_status, decision_status);
CREATE INDEX IF NOT EXISTS idx_holding_theses_review_due ON portfolio.holding_theses (next_review_due_at);
CREATE INDEX IF NOT EXISTS idx_holding_theses_owner ON portfolio.holding_theses (primary_owner_agent);

CREATE TABLE IF NOT EXISTS portfolio.holding_thesis_versions (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    exchange TEXT,
    version_number INTEGER NOT NULL,
    note_path TEXT,
    change_type TEXT NOT NULL DEFAULT 'memo_generated',
    thesis_status TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    thesis_summary TEXT,
    business_model TEXT,
    industry_structure TEXT,
    score_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    valuation_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    thesis_killers JSONB NOT NULL DEFAULT '[]'::jsonb,
    exit_criteria TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'AI OS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_holding_thesis_versions_symbol ON portfolio.holding_thesis_versions (symbol, exchange, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.holding_thesis_checklists (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    checklist_key TEXT NOT NULL,
    checklist_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    score NUMERIC,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_agent TEXT NOT NULL DEFAULT 'Research Analyst',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id, checklist_key)
);

CREATE TABLE IF NOT EXISTS portfolio.holding_valuation_models (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    model_key TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    fair_value_low NUMERIC,
    fair_value_base NUMERIC,
    fair_value_high NUMERIC,
    expected_cagr_pct NUMERIC,
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    note_path TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Valuation Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id, model_key)
);

CREATE TABLE IF NOT EXISTS portfolio.holding_review_schedule (
    id BIGSERIAL PRIMARY KEY,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    review_type TEXT NOT NULL DEFAULT 'quarterly_review',
    due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    owner_agent TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_holding_review_schedule_due ON portfolio.holding_review_schedule (status, due_at);

CREATE OR REPLACE VIEW portfolio.v_long_term_thesis_control AS
WITH exposure AS (
    SELECT
        upper(symbol) AS symbol,
        exchange,
        count(*) AS position_count,
        count(DISTINCT client_code) AS client_count,
        array_remove(array_agg(DISTINCT client_name ORDER BY client_name), NULL) AS clients,
        sum(coalesce(gross_exposure, 0)) AS long_term_gross_exposure,
        sum(coalesce(net_exposure, 0)) AS long_term_net_exposure,
        max(as_of) AS latest_as_of
    FROM books.v_book_positions
    WHERE book_key = 'long_term'
      AND status = 'active'
    GROUP BY upper(symbol), exchange
),
checklists AS (
    SELECT
        holding_thesis_id,
        count(*) AS checklist_count,
        count(*) FILTER (WHERE status IN ('complete','reviewed')) AS checklist_complete_count,
        jsonb_object_agg(checklist_key, jsonb_build_object('status', status, 'score', score, 'owner_agent', owner_agent)) AS checklist_status
    FROM portfolio.holding_thesis_checklists
    GROUP BY holding_thesis_id
),
valuations AS (
    SELECT
        holding_thesis_id,
        count(*) AS valuation_model_count,
        count(*) FILTER (WHERE status IN ('complete','reviewed')) AS valuation_complete_count,
        jsonb_object_agg(model_key, jsonb_build_object('status', status, 'type', model_type, 'fair_value_base', fair_value_base)) AS valuation_status_map
    FROM portfolio.holding_valuation_models
    GROUP BY holding_thesis_id
),
reviews AS (
    SELECT DISTINCT ON (holding_thesis_id)
        holding_thesis_id,
        due_at AS next_scheduled_review_at,
        status AS next_review_status,
        task_id AS next_review_task_id
    FROM portfolio.holding_review_schedule
    WHERE status IN ('scheduled','queued','in_progress')
    ORDER BY holding_thesis_id, due_at ASC
)
SELECT
    ht.id,
    coalesce(ht.symbol, exposure.symbol) AS symbol,
    coalesce(ht.exchange, exposure.exchange) AS exchange,
    ht.company_name,
    ht.thesis_title,
    ht.thesis_version,
    ht.thesis_status,
    ht.decision_status,
    ht.primary_owner_agent,
    ht.purpose_key,
    ht.thesis_summary,
    ht.business_model,
    ht.industry_structure,
    ht.moat_score,
    ht.management_score,
    ht.governance_score,
    ht.capital_allocation_score,
    ht.financial_quality_score,
    ht.valuation_status,
    ht.base_case_fair_value,
    ht.expected_cagr_pct,
    ht.thesis_note_path,
    ht.valuation_note_path,
    ht.risk_note_path,
    ht.last_reviewed_at,
    coalesce(reviews.next_scheduled_review_at, ht.next_review_due_at) AS next_review_due_at,
    reviews.next_review_status,
    reviews.next_review_task_id,
    ht.review_frequency,
    coalesce(exposure.position_count, 0) AS position_count,
    coalesce(exposure.client_count, 0) AS client_count,
    coalesce(exposure.clients, ARRAY[]::TEXT[]) AS clients,
    coalesce(exposure.long_term_gross_exposure, 0) AS long_term_gross_exposure,
    coalesce(exposure.long_term_net_exposure, 0) AS long_term_net_exposure,
    exposure.latest_as_of,
    coalesce(checklists.checklist_count, 0) AS checklist_count,
    coalesce(checklists.checklist_complete_count, 0) AS checklist_complete_count,
    coalesce(checklists.checklist_status, '{}'::jsonb) AS checklist_status,
    coalesce(valuations.valuation_model_count, 0) AS valuation_model_count,
    coalesce(valuations.valuation_complete_count, 0) AS valuation_complete_count,
    coalesce(valuations.valuation_status_map, '{}'::jsonb) AS valuation_status_map,
    ht.thesis_killers,
    ht.exit_criteria,
    ht.updated_by,
    ht.created_at,
    ht.updated_at
FROM portfolio.holding_theses ht
FULL OUTER JOIN exposure
  ON upper(ht.symbol) = exposure.symbol
 AND ht.exchange IS NOT DISTINCT FROM exposure.exchange
LEFT JOIN checklists ON checklists.holding_thesis_id = ht.id
LEFT JOIN valuations ON valuations.holding_thesis_id = ht.id
LEFT JOIN reviews ON reviews.holding_thesis_id = ht.id
ORDER BY coalesce(exposure.long_term_gross_exposure, 0) DESC, coalesce(ht.symbol, exposure.symbol);

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_generate_long_term_thesis_memo',
        'mcp_tool',
        'Long-Term Portfolio Manager',
        'write_with_approval',
        true,
        'Create or update a structured long-term holding thesis memo from real long-term book exposure. No buy/sell recommendation is authorized.',
        '{"script":"_ai_os_runtime/scripts/generate_long_term_thesis_memo.py","writes":["portfolio.holding_theses","portfolio.holding_thesis_versions","portfolio.holding_thesis_checklists","portfolio.holding_valuation_models","portfolio.holding_review_schedule","knowledge.obsidian_notes","agent.tasks","agent.inbox_items"],"reads":["books.v_book_positions","portfolio.v_long_term_thesis_control"],"seed_data_allowed":false}'::jsonb
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
            'portfolio.holding_theses',
            'portfolio.holding_thesis_versions',
            'portfolio.holding_thesis_checklists',
            'portfolio.holding_valuation_models',
            'portfolio.holding_review_schedule',
            'portfolio.v_long_term_thesis_control'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_generate_long_term_thesis_memo']::TEXT[]) AS tool
    ),
    next_action = 'Long-term thesis schema is installed; generate memos for core holdings, then fill scorecards and valuation modules with sourced research.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');
