CREATE TABLE IF NOT EXISTS strategy.strategy_intakes (
    id BIGSERIAL PRIMARY KEY,
    intake_key TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    intake_text TEXT NOT NULL,
    strategy_name TEXT,
    strategy_family TEXT,
    asset_class TEXT,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    universe TEXT,
    timeframe TEXT,
    intent_tags TEXT[] NOT NULL DEFAULT '{}',
    constraints_text TEXT,
    risk_notes TEXT,
    requested_outputs TEXT[] NOT NULL DEFAULT '{}',
    source_kind TEXT,
    source_ref TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    owner_agent TEXT NOT NULL DEFAULT 'Strategy Intake Agent',
    assigned_agents TEXT[] NOT NULL DEFAULT ARRAY['Strategy Intake Agent','Strategy Research Agent','Model Validation Agent']::TEXT[],
    structured_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_intakes_status ON strategy.strategy_intakes (status);
CREATE INDEX IF NOT EXISTS idx_strategy_intakes_created ON strategy.strategy_intakes (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_intakes_symbols ON strategy.strategy_intakes USING GIN (symbols);

CREATE TABLE IF NOT EXISTS strategy.generated_ideas (
    id BIGSERIAL PRIMARY KEY,
    idea_key TEXT NOT NULL UNIQUE,
    intake_id BIGINT REFERENCES strategy.strategy_intakes(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    idea_type TEXT NOT NULL DEFAULT 'strategy_hypothesis',
    symbols TEXT[] NOT NULL DEFAULT '{}',
    universe TEXT,
    timeframe TEXT,
    thesis TEXT NOT NULL,
    edge_hypothesis TEXT,
    entry_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    exit_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_requirements TEXT[] NOT NULL DEFAULT '{}',
    assumptions TEXT[] NOT NULL DEFAULT '{}',
    invalidation_tests TEXT[] NOT NULL DEFAULT '{}',
    priority_score NUMERIC,
    risk_score NUMERIC,
    status TEXT NOT NULL DEFAULT 'candidate',
    owner_agent TEXT NOT NULL DEFAULT 'Strategy Generator',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_generated_ideas_status ON strategy.generated_ideas (status);
CREATE INDEX IF NOT EXISTS idx_generated_ideas_intake ON strategy.generated_ideas (intake_id);
CREATE INDEX IF NOT EXISTS idx_generated_ideas_symbols ON strategy.generated_ideas USING GIN (symbols);

ALTER TABLE strategy.strategy_candidates
    ADD COLUMN IF NOT EXISTS intake_id BIGINT REFERENCES strategy.strategy_intakes(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS generated_idea_id BIGINT REFERENCES strategy.generated_ideas(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS candidate_key TEXT,
    ADD COLUMN IF NOT EXISTS structured_spec JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS validation_status TEXT NOT NULL DEFAULT 'not_reviewed',
    ADD COLUMN IF NOT EXISTS activation_gate TEXT NOT NULL DEFAULT 'paper_first';

CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_candidates_candidate_key
ON strategy.strategy_candidates (candidate_key)
WHERE candidate_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_strategy_candidates_intake ON strategy.strategy_candidates (intake_id);
CREATE INDEX IF NOT EXISTS idx_strategy_candidates_generated_idea ON strategy.strategy_candidates (generated_idea_id);

CREATE TABLE IF NOT EXISTS strategy.optimization_runs (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    backtest_run_id BIGINT REFERENCES strategy.backtest_runs(id) ON DELETE SET NULL,
    run_name TEXT NOT NULL,
    optimizer_type TEXT NOT NULL DEFAULT 'parameter_search',
    status TEXT NOT NULL DEFAULT 'queued',
    objective TEXT,
    parameter_space JSONB NOT NULL DEFAULT '{}'::jsonb,
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_start DATE,
    data_end DATE,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Optimizer Agent',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_optimization_runs_strategy ON strategy.optimization_runs (strategy_id);
CREATE INDEX IF NOT EXISTS idx_optimization_runs_status ON strategy.optimization_runs (status);

CREATE TABLE IF NOT EXISTS strategy.validation_reviews (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    backtest_run_id BIGINT REFERENCES strategy.backtest_runs(id) ON DELETE SET NULL,
    optimization_run_id BIGINT REFERENCES strategy.optimization_runs(id) ON DELETE SET NULL,
    reviewer_agent TEXT NOT NULL DEFAULT 'Model Validation Agent',
    review_status TEXT NOT NULL DEFAULT 'draft',
    decision TEXT,
    leakage_risk TEXT,
    overfit_risk TEXT,
    transaction_cost_notes TEXT,
    sample_size_notes TEXT,
    required_fixes TEXT[] NOT NULL DEFAULT '{}',
    issues JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_validation_reviews_strategy ON strategy.validation_reviews (strategy_id);
CREATE INDEX IF NOT EXISTS idx_validation_reviews_status ON strategy.validation_reviews (review_status);

CREATE OR REPLACE VIEW strategy.v_strategy_intake_queue AS
SELECT
    si.id,
    si.intake_key,
    si.created_by,
    si.strategy_name,
    si.strategy_family,
    si.asset_class,
    si.symbols,
    si.universe,
    si.timeframe,
    si.intent_tags,
    si.status,
    si.owner_agent,
    si.assigned_agents,
    si.source_kind,
    si.source_ref,
    si.created_at,
    si.updated_at,
    count(DISTINCT gi.id) AS generated_ideas,
    count(DISTINCT sc.id) AS strategy_candidates
FROM strategy.strategy_intakes si
LEFT JOIN strategy.generated_ideas gi ON gi.intake_id = si.id
LEFT JOIN strategy.strategy_candidates sc ON sc.intake_id = si.id
GROUP BY si.id;

CREATE OR REPLACE VIEW strategy.v_generated_ideas AS
SELECT
    gi.id,
    gi.idea_key,
    gi.title,
    gi.idea_type,
    gi.symbols,
    gi.universe,
    gi.timeframe,
    gi.thesis,
    gi.edge_hypothesis,
    gi.status,
    gi.priority_score,
    gi.risk_score,
    gi.owner_agent,
    gi.created_at,
    si.intake_key,
    si.strategy_name AS intake_strategy_name
FROM strategy.generated_ideas gi
LEFT JOIN strategy.strategy_intakes si ON si.id = gi.intake_id;

CREATE OR REPLACE VIEW strategy.v_strategy_agent_lab AS
SELECT
    sc.id AS strategy_id,
    coalesce(sc.candidate_key, 'candidate_' || sc.id::TEXT) AS candidate_key,
    sc.name,
    sc.status,
    sc.validation_status,
    sc.activation_gate,
    sc.owner_agent,
    sc.timeframe,
    sc.universe,
    si.intake_key,
    gi.idea_key,
    count(DISTINCT br.id) AS backtest_runs,
    count(DISTINCT opt.id) AS optimization_runs,
    count(DISTINCT vr.id) AS validation_reviews,
    max(br.finished_at) AS latest_backtest_finished_at,
    max(opt.finished_at) AS latest_optimization_finished_at,
    max(vr.updated_at) AS latest_validation_at,
    sc.created_at,
    sc.updated_at
FROM strategy.strategy_candidates sc
LEFT JOIN strategy.strategy_intakes si ON si.id = sc.intake_id
LEFT JOIN strategy.generated_ideas gi ON gi.id = sc.generated_idea_id
LEFT JOIN strategy.backtest_runs br ON br.strategy_id = sc.id
LEFT JOIN strategy.optimization_runs opt ON opt.strategy_id = sc.id
LEFT JOIN strategy.validation_reviews vr ON vr.strategy_id = sc.id
GROUP BY sc.id, si.intake_key, gi.idea_key;

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model, escalation_provider,
    escalation_model, max_cost_tier, notes, enabled
)
VALUES
    ('strategy_intake', 'strategy_intake', 'ollama', 'qwen3:8b', 'codex_or_cloud', '', 'hybrid', 'Convert Devarsh natural-language strategy instructions into structured specs and tasks.', true),
    ('strategy_backtest', 'quant_backtest', 'local_python', 'deterministic_tools', 'codex_or_cloud', '', 'local', 'Use local Python/backtest components and warehouse data before any model summary.', true),
    ('strategy_optimizer', 'quant_optimization', 'local_python', 'deterministic_tools', 'codex_or_cloud', '', 'local', 'Run parameter search, walk-forward checks, and robustness diagnostics locally first.', true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets
)
VALUES
    ('Strategy Intake Agent', 'quant', 'Translate Devarsh strategy descriptions into structured specs, data requirements, tasks, and paper-first routing.', 'strategy_intake', ARRAY['postgres_read_model','obsidian_note_index','tradingview_task_queue'], 'write_with_approval', 'active', '{"no_live_execution":true,"must_create_structured_spec":true,"paper_first":true}'::jsonb, ARRAY['strategy.strategy_intakes','strategy.strategy_candidates','agent.tasks']),
    ('Strategy Generator', 'quant', 'Generate strategy hypotheses and variants from user ideas, trade journals, market structure, filings, and research evidence.', 'strategy_generation', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index'], 'write_with_approval', 'active', '{"hypothesis_not_recommendation":true,"evidence_required":true,"backtest_before_alert":true}'::jsonb, ARRAY['strategy.generated_ideas','strategy.strategy_candidates','research.ideas']),
    ('Backtest Engineer', 'quant', 'Run local backtests with explicit data lineage, transaction costs, and artifact output.', 'strategy_backtest', ARRAY['postgres_read_model','local_python_backtester','component_inventory_reader'], 'write_with_approval', 'active', '{"no_live_execution":true,"transaction_costs_required":true,"data_lineage_required":true}'::jsonb, ARRAY['strategy.backtest_runs','strategy.performance_snapshots','agent.inbox_items']),
    ('Optimizer Agent', 'quant', 'Run parameter search, walk-forward analysis, and robustness checks after a base strategy has evidence.', 'strategy_optimizer', ARRAY['postgres_read_model','local_python_backtester'], 'write_with_approval', 'active', '{"optimize_after_baseline_only":true,"walk_forward_required":true,"overfit_warning_required":true}'::jsonb, ARRAY['strategy.optimization_runs','strategy.validation_reviews','agent.inbox_items'])
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    updated_at = now();

UPDATE agent.profiles
SET
    permission_level = 'write_with_approval',
    default_tools = ARRAY['postgres_read_model','strategy_validation_review','agent_inbox_writer']::TEXT[],
    guardrails = '{"challenge_backtests":true,"transaction_costs_required":true,"no_live_execution":true,"must_record_required_fixes":true}'::jsonb,
    output_targets = ARRAY['strategy.validation_reviews','strategy.backtest_runs','agent.inbox_items']::TEXT[],
    updated_at = now()
WHERE agent_name = 'Model Validation Agent';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_create_strategy_intake', 'mcp_tool', 'Charlie Munger', 'write_with_approval', true, 'Create a structured strategy intake from Devarsh natural-language instructions and queue specialist work.', '{"writes":["strategy.strategy_intakes","agent.tasks","agent.inbox_items"],"execution_allowed":false}'::jsonb),
    ('ai_os_strategy_intakes', 'mcp_tool', 'Strategy Intake Agent', 'read_only', true, 'List strategy intakes with generated idea and candidate counts.', '{"reads":["strategy.v_strategy_intake_queue"]}'::jsonb),
    ('ai_os_create_generated_strategy_idea', 'mcp_tool', 'Strategy Generator', 'write_with_approval', true, 'Record a generated strategy idea or variant with evidence and optional intake linkage.', '{"writes":["strategy.generated_ideas","strategy.strategy_candidates"],"execution_allowed":false}'::jsonb),
    ('ai_os_strategy_lab', 'mcp_tool', 'Charlie Munger', 'read_only', true, 'Read strategy candidates, intakes, generated ideas, backtests, optimizations, and validation counts.', '{"reads":["strategy.v_strategy_agent_lab","strategy.v_generated_ideas"]}'::jsonb),
    ('ai_os_queue_strategy_backtest', 'mcp_tool', 'Backtest Engineer', 'write_with_approval', true, 'Queue a local backtest run for a strategy candidate. This does not execute trades.', '{"writes":["strategy.backtest_runs","agent.inbox_items"],"execution_allowed":false}'::jsonb),
    ('ai_os_record_strategy_optimization', 'mcp_tool', 'Optimizer Agent', 'write_with_approval', true, 'Record an optimization or walk-forward run for a strategy candidate.', '{"writes":["strategy.optimization_runs"],"execution_allowed":false}'::jsonb),
    ('ai_os_record_strategy_validation', 'mcp_tool', 'Model Validation Agent', 'write_with_approval', true, 'Record a validation review for a strategy/backtest/optimization.', '{"writes":["strategy.validation_reviews"],"execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET
    warehouse_objects = ARRAY[
        'strategy.strategy_registry',
        'strategy.strategy_intakes',
        'strategy.generated_ideas',
        'strategy.strategy_candidates',
        'strategy.strategy_instances'
    ]::TEXT[],
    mcp_tools = ARRAY[
        'ai_os_create_strategy_intake',
        'ai_os_strategy_intakes',
        'ai_os_create_generated_strategy_idea',
        'ai_os_strategy_lab'
    ]::TEXT[],
    next_action = 'Use Charlie to create strategy intakes, then route to generator, backtest, optimizer, validation, and paper monitoring.',
    updated_at = now()
WHERE module_key = 'strategy_registry';

UPDATE core.control_plane_modules
SET
    warehouse_objects = ARRAY[
        'strategy.backtest_runs',
        'strategy.optimization_runs',
        'strategy.validation_reviews',
        'strategy.performance_snapshots',
        'strategy.strategy_versions'
    ]::TEXT[],
    mcp_tools = ARRAY[
        'ai_os_queue_strategy_backtest',
        'ai_os_record_strategy_optimization',
        'ai_os_record_strategy_validation',
        'ai_os_strategy_lab'
    ]::TEXT[],
    status = 'active',
    next_action = 'Wrap local backtest and optimizer components behind these warehouse-backed queues.',
    updated_at = now()
WHERE module_key = 'quant_lab';
