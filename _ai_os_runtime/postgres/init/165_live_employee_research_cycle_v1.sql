BEGIN;

INSERT INTO research.paper_sources (
    source_key, source_name, source_type, base_url, ingestion_method, config
) VALUES
    ('web', 'Public Web Research', 'web_page', 'https://', 'public_https_or_pasted_text',
     '{"public":true,"ssrf_guard":true,"source_lineage_required":true}'::jsonb),
    ('blog', 'Research Blog', 'research_blog', 'https://', 'public_https_or_pasted_text',
     '{"public":true,"ssrf_guard":true,"source_lineage_required":true}'::jsonb),
    ('github', 'GitHub Research Repository', 'source_repository', 'https://github.com', 'public_https',
     '{"public":true,"license_review_required":true,"source_lineage_required":true}'::jsonb),
    ('manual', 'Operator Research Note', 'pasted_text', 'file://operator-input', 'pasted_text',
     '{"public":false,"operator_supplied":true,"source_lineage_required":true}'::jsonb)
ON CONFLICT (source_key) DO UPDATE SET
    source_name=EXCLUDED.source_name,
    source_type=EXCLUDED.source_type,
    base_url=EXCLUDED.base_url,
    ingestion_method=EXCLUDED.ingestion_method,
    config=EXCLUDED.config,
    updated_at=now();

ALTER TABLE research.research_papers
    ADD COLUMN IF NOT EXISTS source_kind TEXT NOT NULL DEFAULT 'paper',
    ADD COLUMN IF NOT EXISTS research_objective TEXT,
    ADD COLUMN IF NOT EXISTS target_universe TEXT,
    ADD COLUMN IF NOT EXISTS desired_outputs TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS extraction_word_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS intake_status TEXT NOT NULL DEFAULT 'registered';

CREATE INDEX IF NOT EXISTS idx_research_papers_intake
    ON research.research_papers (intake_status, updated_at DESC);

CREATE OR REPLACE VIEW research.v_research_paper_queue AS
SELECT
    p.id, p.paper_key, p.source_key, s.source_name, p.title, p.authors,
    p.published_date, p.doi, p.source_url, p.pdf_url, p.local_pdf_path,
    p.local_text_path, left(p.abstract, 1200) AS abstract, p.page_count,
    p.topics, p.asset_classes, p.markets, p.methodology_tags,
    p.extraction_status, p.review_status, p.owner_agent,
    count(h.id) AS hypothesis_count,
    max(r.finished_at) AS latest_ingestion_at,
    p.evidence, p.metadata, p.created_at, p.updated_at,
    p.source_kind, p.research_objective, p.target_universe, p.desired_outputs,
    p.extraction_word_count, p.intake_status
FROM research.research_papers p
LEFT JOIN research.paper_sources s ON s.source_key = p.source_key
LEFT JOIN research.paper_strategy_hypotheses h ON h.paper_id = p.id
LEFT JOIN research.paper_ingestion_runs r ON r.paper_id = p.id
GROUP BY p.id, s.source_name
ORDER BY CASE p.review_status WHEN 'needs_review' THEN 1 WHEN 'unreviewed' THEN 2 ELSE 3 END, p.updated_at DESC;

CREATE TABLE IF NOT EXISTS strategy.research_cycles (
    id BIGSERIAL PRIMARY KEY,
    cycle_key TEXT NOT NULL UNIQUE,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    objective TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL DEFAULT now(),
    universe TEXT,
    strategy_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    point_in_time_marks JSONB NOT NULL DEFAULT '{}'::jsonb,
    signal_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_clamps JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_orders JSONB NOT NULL DEFAULT '[]'::jsonb,
    fills JSONB NOT NULL DEFAULT '[]'::jsonb,
    positions JSONB NOT NULL DEFAULT '[]'::jsonb,
    nav_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'research',
    owner_agent TEXT NOT NULL DEFAULT 'Head of Quant',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategy.alpha_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_key TEXT NOT NULL UNIQUE,
    cycle_id BIGINT NOT NULL REFERENCES strategy.research_cycles(id) ON DELETE CASCADE,
    strategy_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    direction SMALLINT CHECK (direction BETWEEN -1 AND 1),
    conviction NUMERIC(8,6) CHECK (conviction BETWEEN -1 AND 1),
    confidence NUMERIC(8,6) CHECK (confidence BETWEEN 0 AND 1),
    abstained BOOLEAN NOT NULL DEFAULT false,
    rationale TEXT,
    model_route TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (abstained OR direction IS NOT NULL),
    CHECK (NOT abstained OR direction IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_alpha_signals_cycle ON strategy.alpha_signals (cycle_id, strategy_key, symbol);
CREATE INDEX IF NOT EXISTS idx_alpha_signals_as_of ON strategy.alpha_signals (as_of DESC);

CREATE OR REPLACE FUNCTION strategy.reject_research_cycle_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'research cycle records are immutable; create a new cycle';
END;
$$;

DROP TRIGGER IF EXISTS trg_research_cycles_immutable ON strategy.research_cycles;
CREATE TRIGGER trg_research_cycles_immutable
BEFORE UPDATE OR DELETE ON strategy.research_cycles
FOR EACH ROW EXECUTE FUNCTION strategy.reject_research_cycle_update();

CREATE OR REPLACE VIEW agent.v_conversational_employee_profiles AS
SELECT
    profile.*,
    concat(
        'I am ', profile.agent_name, ', ', coalesce(profile.display_title, profile.role_scope), '. ',
        coalesce(profile.persona, ''), ' ', coalesce(profile.operating_style, ''),
        ' I speak in first person, lead with verified facts, label inference and uncertainty, ',
        'cite evidence, state what I actually did, and never claim another employee''s work as my own.'
    ) AS first_person_identity,
    jsonb_build_object(
        'identity', profile.agent_name,
        'title', profile.display_title,
        'department', profile.department_name,
        'reports_to', profile.reports_to_agent,
        'mandate', profile.role_scope,
        'mental_models', profile.mental_models,
        'preferred_route', profile.primary_route,
        'permission_level', profile.permission_level,
        'fact_first', true,
        'first_person', true,
        'must_distinguish_fact_inference_unknown', true,
        'may_claim_only_completed_actions', true,
        'live_execution_allowed', false
    ) AS conversation_contract
FROM agent.v_employee_profiles_v1 profile;

UPDATE agent.agent_characters
SET character_prompt = character_prompt ||
    ' Speak in first person as this employee. Lead with verified facts, distinguish inference from unknowns, cite evidence, and claim only work you personally completed.',
    updated_at = now()
WHERE character_prompt NOT LIKE '%Speak in first person as this employee%';

CREATE OR REPLACE VIEW research.v_research_intake_pipeline AS
SELECT
    paper.id AS paper_id,
    paper.paper_key,
    paper.title,
    paper.source_key,
    paper.source_kind,
    paper.source_url,
    paper.research_objective,
    paper.target_universe,
    paper.desired_outputs,
    paper.extraction_status,
    paper.extraction_word_count,
    paper.review_status,
    paper.intake_status,
    paper.owner_agent,
    count(DISTINCT hypothesis.id)::BIGINT AS hypothesis_count,
    count(DISTINCT task.id) FILTER (WHERE task.status IN ('queued','in_progress','blocked'))::BIGINT AS open_task_count,
    max(task.updated_at) AS latest_task_at,
    max(paper.updated_at) AS updated_at,
    paper.evidence
FROM research.research_papers paper
LEFT JOIN research.paper_strategy_hypotheses hypothesis ON hypothesis.paper_id=paper.id
LEFT JOIN agent.tasks task
  ON task.source_kind='research.research_papers' AND task.source_ref=paper.id::TEXT
GROUP BY paper.id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_ingest_research_source', 'mcp_tool', 'Research Librarian', 'write_db_and_artifact', true,
     'Extract a public HTTPS page, PDF, or operator-supplied text; preserve provenance; and create linked research and quant assignments.',
     '{"api_route":"/api/research/sources/ingest","writes":["research.research_papers","core.raw_artifacts","agent.agent_messages","agent.tasks"],"public_https_only":true,"auto_promote":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_research_cycle_ledger', 'mcp_tool', 'Head of Quant', 'write_db_and_artifact', true,
     'Record immutable point-in-time research cycles and abstain-aware alpha signals before risk review.',
     '{"writes":["strategy.research_cycles","strategy.alpha_signals"],"immutable":true,"broker_write_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,
    config=EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
) VALUES (
    'source_to_hypothesis_research_cycle', 'Source To Hypothesis Research Cycle',
    'research_factory', 'Research Director', 'operator_url_text_or_pdf', 'active',
    'write_db_and_artifact',
    ARRAY['public HTTPS URL','operator pasted text','research.research_papers']::TEXT[],
    ARRAY['research.paper_strategy_hypotheses','agent.tasks','strategy.research_cycles','knowledge.obsidian_notes']::TEXT[],
    false, 'operator initiated or approved research schedule',
    'Evidence extraction, independent research review, falsifiable hypothesis drafting, point-in-time validation, risk challenge, and paper monitoring. No source can become a live strategy directly.',
    '{"inspiration":["virattt/ai-hedge-fund v2 signal contract","MrChartist research and flow monitors"],"abstention_supported":true,"point_in_time_required":true,"transaction_costs_required":true,"human_review_before_backtest":true,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name=EXCLUDED.workflow_name,
    owner_agent=EXCLUDED.owner_agent,
    status=EXCLUDED.status,
    permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources,
    output_targets=EXCLUDED.output_targets,
    notes=EXCLUDED.notes,
    metadata=EXCLUDED.metadata,
    updated_at=now();

COMMIT;
