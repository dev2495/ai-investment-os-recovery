CREATE TABLE IF NOT EXISTS strategy.strategy_retirement_reviews (
    id BIGSERIAL PRIMARY KEY,
    review_key TEXT NOT NULL UNIQUE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    analytics_run_id BIGINT REFERENCES strategy.quant_analytics_runs(id) ON DELETE SET NULL,
    allocation_run_id BIGINT REFERENCES strategy.strategy_portfolio_allocation_runs(id) ON DELETE SET NULL,
    optimizer_run_id BIGINT REFERENCES strategy.strategy_portfolio_optimizer_runs(id) ON DELETE SET NULL,
    review_status TEXT NOT NULL DEFAULT 'open',
    recommended_action TEXT NOT NULL DEFAULT 'watch',
    severity TEXT NOT NULL DEFAULT 'medium',
    trigger_source TEXT NOT NULL DEFAULT 'quant_lab_retirement_review',
    trigger_reasons TEXT[] NOT NULL DEFAULT '{}',
    assigned_agents TEXT[] NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_notes TEXT,
    human_decision TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Strategy Retirement Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_retirement_reviews_strategy
    ON strategy.strategy_retirement_reviews (strategy_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_retirement_reviews_status
    ON strategy.strategy_retirement_reviews (review_status, severity, created_at DESC);

CREATE TABLE IF NOT EXISTS strategy.quant_specialist_assignments (
    id BIGSERIAL PRIMARY KEY,
    assignment_key TEXT NOT NULL UNIQUE,
    review_id BIGINT NOT NULL REFERENCES strategy.strategy_retirement_reviews(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    analytics_run_id BIGINT REFERENCES strategy.quant_analytics_runs(id) ON DELETE SET NULL,
    allocation_run_id BIGINT REFERENCES strategy.strategy_portfolio_allocation_runs(id) ON DELETE SET NULL,
    specialist_agent TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    assignment_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    findings TEXT[] NOT NULL DEFAULT '{}',
    recommended_action TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Strategy Retirement Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_specialist_assignments_agent
    ON strategy.quant_specialist_assignments (specialist_agent, status, priority, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_quant_specialist_assignments_review
    ON strategy.quant_specialist_assignments (review_id, assignment_type);

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department,
    status, execution_mode, permission_level, trigger_phrases,
    input_sources, output_targets, required_tools, risk_notes, prompt_template, config
)
VALUES
    ('strategy_retirement_review', 'Strategy Retirement Review', 'quant', 'workflow', 'quant', 'active', 'worker_deterministic', 'write_with_approval',
     ARRAY['retire strategy', 'pause strategy', 'strategy decay', 'strategy retirement'],
     ARRAY['strategy.quant_analytics_runs','strategy.strategy_portfolio_allocation_runs','strategy.probability_of_ruin_metrics'],
     ARRAY['strategy.strategy_retirement_reviews','strategy.quant_specialist_assignments'],
     ARRAY['ai_os_run_strategy_retirement_review','ai_os_strategy_retirement_queue'],
     'Retirement recommendations are paper/approval state only. No live execution authority.',
     'Review strategy evidence, isolate data weaknesses, decide keep/watch/pause/retire/needs_more_data, and dispatch specialists.',
     '{"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('quant_data_science_review', 'Quant Data Science Review', 'quant', 'analysis', 'quant', 'active', 'worker_deterministic', 'write_with_approval',
     ARRAY['data science review', 'thin return history', 'validate sample'],
     ARRAY['strategy.strategy_return_series','strategy.quant_analytics_runs'],
     ARRAY['strategy.quant_specialist_assignments'],
     ARRAY['ai_os_strategy_quant_analytics'],
     'Flags weak samples, leakage risk, and unstable statistics before committee use.',
     'Audit sample depth, stationarity, leakage, survivorship, and metric stability.',
     '{"source_required":true}'::jsonb),
    ('quant_feature_engineering_review', 'Quant Feature Engineering Review', 'quant', 'analysis', 'quant', 'active', 'worker_deterministic', 'write_with_approval',
     ARRAY['feature review', 'dsl repair', 'feature engineering'],
     ARRAY['strategy.strategy_rule_specs','strategy.v_strategy_dsl_readiness_summary'],
     ARRAY['strategy.quant_specialist_assignments'],
     ARRAY['ai_os_strategy_dsl_status'],
     'Feature proposals must remain paper-only until separately backtested.',
     'Identify missing rules, invalid features, parse failures, and data requirements.',
     '{"paper_first":true}'::jsonb),
    ('quant_regime_review', 'Quant Regime Review', 'quant', 'analysis', 'quant', 'active', 'worker_deterministic', 'write_with_approval',
     ARRAY['regime review', 'regime split', 'regime weakness'],
     ARRAY['strategy.regime_performance_splits'],
     ARRAY['strategy.quant_specialist_assignments'],
     ARRAY['ai_os_strategy_quant_analytics'],
     'Regime conclusions must cite actual split rows and bars.',
     'Find market regimes where the strategy fails, survives, or needs a filter.',
     '{"regime_evidence_required":true}'::jsonb),
    ('quant_capacity_liquidity_review', 'Quant Capacity Liquidity Review', 'quant', 'analysis', 'quant', 'active', 'worker_deterministic', 'write_with_approval',
     ARRAY['capacity review', 'liquidity review', 'market impact'],
     ARRAY['strategy.capacity_liquidity_checks'],
     ARRAY['strategy.quant_specialist_assignments'],
     ARRAY['ai_os_strategy_quant_analytics'],
     'Capacity output is an estimate, not execution permission.',
     'Check traded value, participation, capacity ceiling, and liquidity status.',
     '{"capacity_estimate_only":true}'::jsonb)
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

INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets,
    display_title, persona, operating_style, mental_models, escalation_rules,
    daily_cadence, cost_policy, human_interface
)
VALUES
    ('Data Scientist', 'quant', 'Audit strategy samples, return series, leakage risk, data sufficiency, and statistical reliability.', 'strategy_generation',
     ARRAY['ai_os_strategy_quant_analytics','ai_os_strategy_retirement_queue'], 'write_with_approval', 'active',
     '{"no_live_execution":true,"source_required":true}'::jsonb,
     ARRAY['strategy.quant_specialist_assignments','strategy.strategy_retirement_reviews'],
     'Senior Quant Data Scientist', 'Statistical skeptic who distrusts small samples, leakage, and pretty curves.',
     'Asks for sample depth, stationarity, leakage controls, and out-of-sample evidence before accepting alpha.',
     ARRAY['base rates','sample size','stationarity','leakage control','out of sample validation'],
     '{"cloud_allowed_for":"committee_or_large_document_only","human_required_for":"strategy_promotion"}'::jsonb,
     'Review new quant evidence after analytics and before committee promotion.', 'local_first', 'Quant Lab specialist card and assignment queue'),
    ('Feature Engineer', 'quant', 'Design, repair, and validate strategy features, DSL rules, symbols, and data requirements.', 'strategy_intake',
     ARRAY['ai_os_parse_strategy_dsl','ai_os_strategy_dsl_status','ai_os_strategy_data_quality_gate'], 'write_with_approval', 'active',
     '{"paper_first":true,"no_unbacktested_feature_live":true}'::jsonb,
     ARRAY['strategy.quant_specialist_assignments','strategy.strategy_rule_specs'],
     'Alpha Feature Engineer', 'Builder of clean features who turns vague trading ideas into testable rule inputs.',
     'Converts natural-language setup into deterministic fields, rejects ambiguous rules, and lists missing data.',
     ARRAY['feature hygiene','orthogonality','data availability','parseability','simplicity'],
     '{"human_required_for":"manual_strategy_acceptance"}'::jsonb,
     'Repair parse/data gaps whenever a strategy is blocked before backtest.', 'local_first', 'Quant Lab specialist card and assignment queue'),
    ('Regime Analyst', 'quant', 'Find which market regimes strengthen, weaken, or invalidate a strategy.', 'strategy_generation',
     ARRAY['ai_os_strategy_quant_analytics','ai_os_strategy_retirement_queue'], 'write_with_approval', 'active',
     '{"regime_evidence_required":true,"no_live_execution":true}'::jsonb,
     ARRAY['strategy.quant_specialist_assignments','strategy.regime_performance_splits'],
     'Market Regime Analyst', 'Market historian focused on when a strategy works and when it should stand down.',
     'Segments results by trend, volatility, liquidity, and drawdown context; proposes filters only with evidence.',
     ARRAY['regime dependency','conditional expectancy','drawdown clustering','volatility states','market microstructure'],
     '{"escalate_when":"strategy fails in dominant regime"}'::jsonb,
     'Review every strategy with weak or conflicting regime splits.', 'local_first', 'Quant Lab specialist card and assignment queue'),
    ('Capacity/Liquidity Analyst', 'quant', 'Estimate deployable capital, participation limits, liquidity status, and capacity decay.', 'strategy_optimizer',
     ARRAY['ai_os_strategy_quant_analytics','ai_os_strategy_portfolio_allocation','ai_os_strategy_retirement_queue'], 'write_with_approval', 'active',
     '{"capacity_estimate_only":true,"execution_requires_separate_approval":true}'::jsonb,
     ARRAY['strategy.quant_specialist_assignments','strategy.capacity_liquidity_checks'],
     'Capacity and Liquidity Analyst', 'Practical market-impact analyst who refuses alpha that cannot absorb real money.',
     'Checks volume, traded value, participation, slippage, capacity ceiling, and whether a strategy scales.',
     ARRAY['market impact','capacity ceiling','liquidity tiers','participation rate','slippage realism'],
     '{"human_required_for":"capacity_override"}'::jsonb,
     'Review all strategies before portfolio allocation or limited-live promotion.', 'local_first', 'Quant Lab specialist card and assignment queue')
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

INSERT INTO agent.org_hierarchy (
    agent_name, reports_to_agent, department_key, role_rank, hierarchy_level,
    authority_scope, decision_rights, must_consult, can_delegate_to, approval_required_for
)
VALUES
    ('Data Scientist', 'Strategy Generator', 'quant', 46, 'specialist',
     'Can challenge strategy evidence and request more data before committee review.',
     ARRAY['flag_data_risk','request_retest'], ARRAY['Model Validation Agent','Risk Agent'], ARRAY[]::text[], ARRAY['paper_activation','limited_live']),
    ('Feature Engineer', 'Strategy Generator', 'quant', 47, 'specialist',
     'Can define feature repair tasks and block ambiguous strategy DSL from backtest.',
     ARRAY['request_dsl_repair','request_data_gate'], ARRAY['Backtest Engineer','Strategy Intake Agent'], ARRAY[]::text[], ARRAY['new_feature_promotion']),
    ('Regime Analyst', 'Strategy Generator', 'quant', 48, 'specialist',
     'Can recommend regime filters, watch states, or pause states based on split evidence.',
     ARRAY['flag_regime_decay','request_regime_filter'], ARRAY['Data Scientist','Risk Agent'], ARRAY[]::text[], ARRAY['limited_live']),
    ('Capacity/Liquidity Analyst', 'Strategy Generator', 'quant', 49, 'specialist',
     'Can cap allocation, flag capacity decay, and request liquidity limits.',
     ARRAY['flag_capacity_limit','request_size_cap'], ARRAY['Optimizer Agent','Risk Agent'], ARRAY[]::text[], ARRAY['capital_allocation','limited_live'])
ON CONFLICT (agent_name) DO UPDATE SET
    reports_to_agent = EXCLUDED.reports_to_agent,
    department_key = EXCLUDED.department_key,
    role_rank = EXCLUDED.role_rank,
    hierarchy_level = EXCLUDED.hierarchy_level,
    authority_scope = EXCLUDED.authority_scope,
    decision_rights = EXCLUDED.decision_rights,
    must_consult = EXCLUDED.must_consult,
    can_delegate_to = EXCLUDED.can_delegate_to,
    approval_required_for = EXCLUDED.approval_required_for,
    updated_at = now();

INSERT INTO agent.mailboxes (
    mailbox_key, agent_name, display_name, channel_type, address, purpose, status, notification_policy
)
VALUES
    ('data-scientist-inbox', 'Data Scientist', 'Data Scientist Inbox', 'internal_email', 'data.scientist@ai-office.local', 'Statistical reliability and sample-quality reviews for Quant Lab.', 'active', '{"priority":"high","digest":"daily"}'::jsonb),
    ('feature-engineer-inbox', 'Feature Engineer', 'Feature Engineer Inbox', 'internal_email', 'feature.engineer@ai-office.local', 'Strategy DSL, feature, and data requirement repair work.', 'active', '{"priority":"medium","digest":"daily"}'::jsonb),
    ('regime-analyst-inbox', 'Regime Analyst', 'Regime Analyst Inbox', 'internal_email', 'regime.analyst@ai-office.local', 'Regime split reviews and market-state filters.', 'active', '{"priority":"medium","digest":"daily"}'::jsonb),
    ('capacity-liquidity-analyst-inbox', 'Capacity/Liquidity Analyst', 'Capacity/Liquidity Analyst Inbox', 'internal_email', 'capacity.liquidity@ai-office.local', 'Capacity, liquidity, participation, and market-impact reviews.', 'active', '{"priority":"high","digest":"daily"}'::jsonb)
ON CONFLICT (mailbox_key) DO UPDATE SET
    agent_name = EXCLUDED.agent_name,
    display_name = EXCLUDED.display_name,
    channel_type = EXCLUDED.channel_type,
    address = EXCLUDED.address,
    purpose = EXCLUDED.purpose,
    status = EXCLUDED.status,
    notification_policy = EXCLUDED.notification_policy,
    updated_at = now();

INSERT INTO agent.agent_model_assignments (
    agent_name, primary_route, primary_model_key, fallback_route, escalation_route,
    context_policy, cost_policy, max_autonomous_cost_tier, escalation_triggers, notes
)
VALUES
    ('Data Scientist', 'strategy_generation', 'ollama_qwen3_14b', 'local_workhorse_synthesis', 'frontier_investment_review',
     'Use retrieved strategy runs, return series summaries, and source lineage only.', 'local_first', 'local_plus',
     ARRAY['committee_deadlock','large_research_review','possible_data_leakage'], 'Local-first quant evidence review; cloud only on approval.'),
    ('Feature Engineer', 'strategy_intake', 'ollama_llama3_2_3b', 'local_workhorse_synthesis', 'coding_escalation',
     'Prefer deterministic DSL parser and data gate before free-form reasoning.', 'local_first', 'local',
     ARRAY['parser_bug','new_dsl_capability_needed'], 'Keeps feature work simple and testable.'),
    ('Regime Analyst', 'strategy_generation', 'ollama_qwen3_14b', 'local_workhorse_synthesis', 'frontier_investment_review',
     'Use regime split rows, factor rows, and market state labels.', 'local_first', 'local_plus',
     ARRAY['capital_decision','conflicting_regime_evidence'], 'Reviews conditional performance before strategy promotion.'),
    ('Capacity/Liquidity Analyst', 'strategy_optimizer', 'ollama_llama3_2_3b', 'local_workhorse_synthesis', 'frontier_investment_review',
     'Use capacity/liquidity rows and allocation constraints; no broker execution.', 'local_first', 'local',
     ARRAY['capacity_override','large_allocation_request'], 'Caps strategy scale before portfolio use.')
ON CONFLICT (agent_name) DO UPDATE SET
    primary_route = EXCLUDED.primary_route,
    primary_model_key = EXCLUDED.primary_model_key,
    fallback_route = EXCLUDED.fallback_route,
    escalation_route = EXCLUDED.escalation_route,
    context_policy = EXCLUDED.context_policy,
    cost_policy = EXCLUDED.cost_policy,
    max_autonomous_cost_tier = EXCLUDED.max_autonomous_cost_tier,
    escalation_triggers = EXCLUDED.escalation_triggers,
    notes = EXCLUDED.notes,
    updated_at = now();

INSERT INTO agent.agent_characters (
    agent_name, character_key, character_name, avatar_role, visual_traits,
    voice_style, office_location, animation_state, color_token, icon_hint, character_prompt
)
VALUES
    ('Data Scientist', 'quant_data_scientist', 'Dr. Sigma', 'Senior Quant Data Scientist',
     'Clean desk with return-series monitors, sample-size warnings, and statistical notebooks.',
     'Precise, skeptical, allergic to overfit and leakage.', 'Quant Lab - Data Science Desk', 'reviewing_metrics', '#0ea5e9', 'sigma',
     'You are Dr. Sigma. You challenge every strategy with sample depth, leakage, out-of-sample, stationarity, and metric stability.'),
    ('Feature Engineer', 'quant_feature_engineer', 'Ada Features', 'Alpha Feature Engineer',
     'Feature boards, parser status lights, and rule cards around the workstation.',
     'Concise builder who turns vague ideas into deterministic test inputs.', 'Quant Lab - Feature Bench', 'designing_features', '#22c55e', 'wrench',
     'You are Ada Features. You make strategy rules parseable, data-backed, simple, and testable before backtest.'),
    ('Regime Analyst', 'quant_regime_analyst', 'Morgan Regime', 'Market Regime Analyst',
     'Wall of trend, volatility, liquidity, and drawdown maps.',
     'Context-first analyst who asks when alpha works, not only whether it worked.', 'Quant Lab - Regime Wall', 'mapping_regimes', '#f97316', 'activity',
     'You are Morgan Regime. You split performance by market states and recommend filters or stand-down regimes.'),
    ('Capacity/Liquidity Analyst', 'quant_capacity_liquidity_analyst', 'Casey Capacity', 'Capacity and Liquidity Analyst',
     'Liquidity ladders, traded-value panels, and participation gauges.',
     'Practical, blunt, focused on whether alpha survives real sizing.', 'Quant Lab - Capacity Desk', 'checking_liquidity', '#a855f7', 'gauge',
     'You are Casey Capacity. You estimate deployable capital, capacity decay, participation limits, and liquidity constraints.')
ON CONFLICT (agent_name) DO UPDATE SET
    character_key = EXCLUDED.character_key,
    character_name = EXCLUDED.character_name,
    avatar_role = EXCLUDED.avatar_role,
    visual_traits = EXCLUDED.visual_traits,
    voice_style = EXCLUDED.voice_style,
    office_location = EXCLUDED.office_location,
    animation_state = EXCLUDED.animation_state,
    color_token = EXCLUDED.color_token,
    icon_hint = EXCLUDED.icon_hint,
    character_prompt = EXCLUDED.character_prompt,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Data Scientist', 'quant_data_science_review', 'lead', true, '{"activate_on":["thin_return_history","negative_sharpe_proxy","possible_leakage"]}'::jsonb),
    ('Data Scientist', 'strategy_retirement_review', 'working', false, '{"activate_on":["retirement_review"]}'::jsonb),
    ('Feature Engineer', 'quant_feature_engineering_review', 'lead', true, '{"activate_on":["missing_passed_dsl","parse_failed","missing_features"]}'::jsonb),
    ('Regime Analyst', 'quant_regime_review', 'lead', true, '{"activate_on":["regime_underperformance","watch","pause_paper"]}'::jsonb),
    ('Capacity/Liquidity Analyst', 'quant_capacity_liquidity_review', 'lead', true, '{"activate_on":["capacity_warning","zero_target_weight","large_allocation"]}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

CREATE OR REPLACE VIEW strategy.v_strategy_retirement_queue AS
SELECT
    review.id,
    review.review_key,
    review.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    review.analytics_run_id,
    analytics.run_key AS analytics_run_key,
    review.allocation_run_id,
    allocation.allocation_key,
    review.optimizer_run_id,
    review.review_status,
    review.recommended_action,
    review.severity,
    review.trigger_source,
    review.trigger_reasons,
    review.assigned_agents,
    review.evidence,
    review.decision_notes,
    review.human_decision,
    review.decided_by,
    review.decided_at,
    review.created_by,
    review.created_at,
    review.updated_at,
    coalesce(assignments.open_assignments, 0) AS open_assignments,
    coalesce(assignments.completed_assignments, 0) AS completed_assignments,
    coalesce(assignments.total_assignments, 0) AS total_assignments
FROM strategy.strategy_retirement_reviews review
JOIN strategy.strategy_candidates candidate ON candidate.id = review.strategy_id
LEFT JOIN strategy.quant_analytics_runs analytics ON analytics.id = review.analytics_run_id
LEFT JOIN strategy.strategy_portfolio_allocation_runs allocation ON allocation.id = review.allocation_run_id
LEFT JOIN (
    SELECT review_id,
           count(*) FILTER (WHERE status NOT IN ('completed','cancelled','archived')) AS open_assignments,
           count(*) FILTER (WHERE status = 'completed') AS completed_assignments,
           count(*) AS total_assignments
    FROM strategy.quant_specialist_assignments
    GROUP BY review_id
) assignments ON assignments.review_id = review.id;

CREATE OR REPLACE VIEW strategy.v_quant_specialist_assignments AS
SELECT
    assignment.id,
    assignment.assignment_key,
    assignment.review_id,
    review.review_key,
    assignment.strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    assignment.analytics_run_id,
    analytics.run_key AS analytics_run_key,
    assignment.allocation_run_id,
    allocation.allocation_key,
    assignment.specialist_agent,
    profile.display_title AS specialist_title,
    character.character_name,
    character.office_location,
    assignment.assignment_type,
    assignment.status,
    assignment.priority,
    assignment.input_payload,
    assignment.output_payload,
    assignment.findings,
    assignment.recommended_action,
    assignment.evidence,
    assignment.due_at,
    assignment.completed_at,
    assignment.created_by,
    assignment.created_at,
    assignment.updated_at
FROM strategy.quant_specialist_assignments assignment
JOIN strategy.strategy_retirement_reviews review ON review.id = assignment.review_id
JOIN strategy.strategy_candidates candidate ON candidate.id = assignment.strategy_id
LEFT JOIN strategy.quant_analytics_runs analytics ON analytics.id = assignment.analytics_run_id
LEFT JOIN strategy.strategy_portfolio_allocation_runs allocation ON allocation.id = assignment.allocation_run_id
LEFT JOIN agent.profiles profile ON profile.agent_name = assignment.specialist_agent
LEFT JOIN agent.agent_characters character ON character.agent_name = assignment.specialist_agent;

CREATE OR REPLACE VIEW strategy.v_quant_lab_dashboard_v2 AS
WITH latest_review AS (
    SELECT DISTINCT ON (strategy_id)
        strategy_id, review_key, review_status, recommended_action, severity,
        trigger_reasons, assigned_agents, open_assignments, total_assignments,
        created_at AS review_created_at
    FROM strategy.v_strategy_retirement_queue
    ORDER BY strategy_id, created_at DESC, id DESC
),
latest_allocation AS (
    SELECT DISTINCT ON (strategy_id)
        strategy_id, allocation_key, target_weight, target_notional,
        expected_return, expected_volatility, risk_contribution, allocation_status,
        created_at AS allocation_created_at
    FROM strategy.v_strategy_portfolio_allocations
    ORDER BY strategy_id, created_at DESC, id DESC
),
latest_ruin AS (
    SELECT DISTINCT ON (strategy_id)
        strategy_id, ruin_probability, max_drawdown_p95, quality_flags, created_at AS ruin_created_at
    FROM strategy.v_probability_of_ruin_metrics
    WHERE strategy_id IS NOT NULL
    ORDER BY strategy_id, created_at DESC, id DESC
)
SELECT
    candidate.id AS strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    candidate.status AS candidate_status,
    candidate.timeframe,
    candidate.validation_status,
    candidate.activation_gate,
    dsl.parse_status,
    dsl.data_quality_status,
    dsl.data_quality_reasons,
    allocation.allocation_key,
    allocation.target_weight,
    allocation.target_notional,
    allocation.expected_return,
    allocation.expected_volatility,
    allocation.risk_contribution,
    allocation.allocation_status,
    ruin.ruin_probability,
    ruin.max_drawdown_p95,
    ruin.quality_flags AS ruin_quality_flags,
    review.review_key,
    review.review_status,
    review.recommended_action,
    review.severity,
    review.trigger_reasons,
    review.assigned_agents,
    review.open_assignments,
    review.total_assignments,
    greatest(
        coalesce(review.review_created_at, 'epoch'::timestamptz),
        coalesce(allocation.allocation_created_at, 'epoch'::timestamptz),
        coalesce(ruin.ruin_created_at, 'epoch'::timestamptz),
        coalesce(candidate.updated_at, candidate.created_at)
    ) AS updated_at
FROM strategy.strategy_candidates candidate
LEFT JOIN strategy.v_strategy_dsl_readiness_summary dsl ON dsl.candidate_id = candidate.id
LEFT JOIN latest_allocation allocation ON allocation.strategy_id = candidate.id
LEFT JOIN latest_ruin ruin ON ruin.strategy_id = candidate.id
LEFT JOIN latest_review review ON review.strategy_id = candidate.id
WHERE candidate.status IN ('imported','idea','research','candidate','paper_monitor','limited_live','paused','retired')
   OR allocation.strategy_id IS NOT NULL
   OR review.strategy_id IS NOT NULL;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_strategy_retirement_review', 'mcp_tool', 'Strategy Generator', 'write_with_approval', true,
     'Create or refresh strategy retirement reviews and Quant specialist assignments from latest real quant analytics/allocation evidence.',
     '{"script":"_ai_os_runtime/scripts/run_strategy_retirement_review.py","writes":["strategy.strategy_retirement_reviews","strategy.quant_specialist_assignments"],"seed_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_strategy_retirement_queue', 'mcp_tool', 'Strategy Generator', 'read_only', true,
     'Read strategy retirement queue, recommended action, trigger reasons, and specialist assignments.',
     '{"reads":["strategy.v_strategy_retirement_queue","strategy.v_quant_specialist_assignments","strategy.v_quant_lab_dashboard_v2"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
