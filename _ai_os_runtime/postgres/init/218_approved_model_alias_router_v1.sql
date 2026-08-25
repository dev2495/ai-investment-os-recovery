BEGIN;

CREATE TABLE IF NOT EXISTS agent.model_alias_registry (
    alias_key TEXT PRIMARY KEY,
    route_name TEXT NOT NULL,
    provider_binding TEXT NOT NULL,
    model_binding TEXT NOT NULL,
    secret_ref TEXT,
    data_boundary TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    fallback_alias TEXT,
    escalation_alias TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.task_routing_registry (
    task_type TEXT PRIMARY KEY,
    risk TEXT NOT NULL,
    tools TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    context_need TEXT NOT NULL,
    latency TEXT NOT NULL,
    cost_ceiling_inr NUMERIC NOT NULL CHECK (cost_ceiling_inr >= 0),
    data_boundary TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    primary_alias TEXT NOT NULL,
    fallback_alias TEXT NOT NULL,
    escalation_alias TEXT,
    escalation_triggers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    max_attempts INTEGER NOT NULL DEFAULT 2 CHECK (max_attempts BETWEEN 1 AND 5),
    concurrency_limit INTEGER NOT NULL DEFAULT 1 CHECK (concurrency_limit BETWEEN 1 AND 16),
    batching_allowed BOOLEAN NOT NULL DEFAULT false,
    cache_policy TEXT NOT NULL DEFAULT 'none',
    degradation_behavior TEXT NOT NULL,
    trace_fields TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    status TEXT NOT NULL DEFAULT 'active',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.model_alias_agent_allowlist (
    alias_key TEXT NOT NULL REFERENCES agent.model_alias_registry(alias_key),
    agent_name TEXT NOT NULL,
    allowed_use TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT true,
    PRIMARY KEY (alias_key, agent_name)
);

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES
    (
        'cloud_volume_flash',
        'high_volume_public_or_redacted_internal_work',
        'openrouter', 'deepseek/deepseek-v4-flash',
        'openrouter', 'z-ai/glm-5.2', 'cloud_low',
        'Alias-backed default cloud route for extraction, classification, summaries, routing, research triage, document processing, and first-pass agent work. Never accepts client_private or restricted context.',
        true
    ),
    (
        'cloud_complex_glm',
        'complex_planning_long_context_tool_use_difficult_coding',
        'openrouter', 'z-ai/glm-5.2',
        'human_or_named_specialist', 'specialist_on_approval', 'cloud_medium',
        'Approval-gated escalation for complex planning, long context, difficult coding, and long multi-step work.',
        true
    ),
    (
        'heavy_specialist_lead_engineer',
        'named_first_class_lead_engineer',
        'operator_selected_heavy_llama', 'specialist.lead_engineer',
        'openrouter', 'z-ai/glm-5.2', 'frontier',
        'Reserved only for the named Lead Engineer. No routine or committee duplication.',
        false
    ),
    (
        'heavy_specialist_investment_reviewer',
        'named_first_class_senior_investment_review',
        'operator_selected_heavy_llama', 'specialist.senior_investment_reviewer',
        'openrouter', 'z-ai/glm-5.2', 'frontier',
        'Reserved only for the named Senior Investment Reviewer. Strong review does not grant capital authority.',
        false
    ),
    (
        'heavy_specialist_final_strategy_writer',
        'named_first_class_final_strategy_writing',
        'operator_selected_heavy_llama', 'specialist.final_strategy_writer',
        'openrouter', 'z-ai/glm-5.2', 'frontier',
        'Reserved only for the named Final Strategy Writer. No live execution authority.',
        false
    )
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

UPDATE agent.model_routes
SET escalation_provider = 'openrouter',
    escalation_model = 'z-ai/glm-5.2',
    notes = concat_ws(' ', notes, 'Approved fallback chain: DeepSeek V4 Flash to GLM 5.2.'),
    enabled = true
WHERE route_name = 'openrouter_research_fast';

UPDATE agent.model_routes
SET enabled = true,
    notes = concat_ws(' ', notes, 'Approved complex-work escalation; approval and budget gates remain mandatory.')
WHERE route_name = 'openrouter_research_review';

INSERT INTO agent.model_alias_registry (
    alias_key, route_name, provider_binding, model_binding, secret_ref,
    data_boundary, approval_required, fallback_alias, escalation_alias, status, notes, config
) VALUES
    ('local.private.default', 'charlie_munger_orchestration', 'local_tools', 'deterministic_router_v1', NULL,
     'client_private_local_only', false, 'local.private.default', NULL, 'active',
     'Default for client, portfolio, trading journal, credential-adjacent, and restricted work.',
     '{"cloud_allowed":false,"cache_allowed":false}'::jsonb),
    ('cloud.volume.default', 'cloud_volume_flash', 'openrouter', 'deepseek/deepseek-v4-flash', 'AI_OS_OPENROUTER_API_KEY',
     'public_or_redacted_internal_only', false, 'local.private.default', 'cloud.complex.escalation', 'active',
     'High-volume cloud default. Alias can be repointed without changing agents.',
     '{"max_attempts":2,"batching":true,"cache":"public_deterministic_only"}'::jsonb),
    ('cloud.complex.escalation', 'cloud_complex_glm', 'openrouter', 'z-ai/glm-5.2', 'AI_OS_OPENROUTER_API_KEY',
     'public_or_approved_redacted_internal_only', true, 'cloud.volume.default', NULL, 'active',
     'Complex planning, long-context tool use, difficult coding, and long multi-step tasks.',
     '{"max_attempts":2,"concurrency_limit":1}'::jsonb),
    ('specialist.lead_engineer', 'heavy_specialist_lead_engineer', 'operator_selected_heavy_llama', 'unbound_heavy_llama', NULL,
     'repository_only_no_secrets', true, 'cloud.complex.escalation', NULL, 'approval_only_unbound',
     'Named first-class specialist only; provider binding requires an explicit approved deployment.',
     '{"routine_use":false,"committee_duplication":false}'::jsonb),
    ('specialist.senior_investment_reviewer', 'heavy_specialist_investment_reviewer', 'operator_selected_heavy_llama', 'unbound_heavy_llama', NULL,
     'public_or_approved_redacted_internal_only', true, 'cloud.complex.escalation', NULL, 'approval_only_unbound',
     'Named first-class specialist only; human remains final investment authority.',
     '{"routine_use":false,"committee_duplication":false,"capital_authority":false}'::jsonb),
    ('specialist.final_strategy_writer', 'heavy_specialist_final_strategy_writer', 'operator_selected_heavy_llama', 'unbound_heavy_llama', NULL,
     'public_or_approved_redacted_internal_only', true, 'cloud.complex.escalation', NULL, 'approval_only_unbound',
     'Named first-class specialist only; outputs stop at draft/review without human confirmation.',
     '{"routine_use":false,"committee_duplication":false,"live_execution":false}'::jsonb)
ON CONFLICT (alias_key) DO UPDATE SET
    route_name = EXCLUDED.route_name,
    provider_binding = EXCLUDED.provider_binding,
    model_binding = EXCLUDED.model_binding,
    secret_ref = EXCLUDED.secret_ref,
    data_boundary = EXCLUDED.data_boundary,
    approval_required = EXCLUDED.approval_required,
    fallback_alias = EXCLUDED.fallback_alias,
    escalation_alias = EXCLUDED.escalation_alias,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.model_alias_agent_allowlist (alias_key, agent_name, allowed_use, approval_required) VALUES
    ('specialist.lead_engineer', 'Lead Engineer', 'difficult coding, architecture, and release-gate repair', true),
    ('specialist.senior_investment_reviewer', 'Senior Investment Reviewer', 'final evidence challenge before an investment recommendation reaches the human', true),
    ('specialist.final_strategy_writer', 'Final Strategy Writer', 'final strategy narrative after quantitative and risk review', true)
ON CONFLICT (alias_key, agent_name) DO UPDATE SET
    allowed_use = EXCLUDED.allowed_use,
    approval_required = EXCLUDED.approval_required;

INSERT INTO agent.task_routing_registry (
    task_type, risk, tools, context_need, latency, cost_ceiling_inr,
    data_boundary, approval_required, primary_alias, fallback_alias,
    escalation_alias, escalation_triggers, max_attempts, concurrency_limit,
    batching_allowed, cache_policy, degradation_behavior, trace_fields, status
) VALUES
    ('extraction', 'low', ARRAY['document_reader'], 'short_to_medium', 'fast', 20, 'public_or_redacted_internal_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['two_failed_attempts','schema_failure'], 2, 3, true, 'public_deterministic_only', 'queue locally when cloud unavailable', ARRAY['trace_id','alias','resolved_model','latency_ms','cost_inr'], 'active'),
    ('classification', 'low', ARRAY['structured_output'], 'short', 'fast', 15, 'public_or_redacted_internal_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['low_confidence','two_failed_attempts'], 2, 3, true, 'public_deterministic_only', 'use deterministic rules or local queue', ARRAY['trace_id','alias','confidence','cost_inr'], 'active'),
    ('summary', 'low', ARRAY['retrieval'], 'medium', 'fast', 25, 'public_or_redacted_internal_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['context_over_64000','reviewer_rejects'], 2, 3, true, 'public_deterministic_only', 'produce extractive summary locally', ARRAY['trace_id','alias','source_ids','cost_inr'], 'active'),
    ('research_triage', 'medium', ARRAY['public_research','source_scoring'], 'medium', 'fast', 35, 'public_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['conflicting_sources','tool_plan_over_8_steps'], 2, 2, true, 'public_deterministic_only', 'retain source list and queue synthesis', ARRAY['trace_id','alias','source_ids','decision_reason','cost_inr'], 'active'),
    ('document_processing', 'medium', ARRAY['document_reader','ocr','structured_output'], 'long', 'normal', 40, 'public_or_redacted_internal_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['ocr_quality_failure','context_over_64000'], 2, 2, true, 'public_deterministic_only', 'local OCR and human review queue', ARRAY['trace_id','alias','document_hash','cost_inr'], 'active'),
    ('first_pass_agent_work', 'medium', ARRAY['role_scoped_tools'], 'medium', 'normal', 35, 'public_or_redacted_internal_only', false,
     'cloud.volume.default', 'local.private.default', 'cloud.complex.escalation', ARRAY['reviewer_rejects','long_tool_chain'], 2, 2, true, 'public_deterministic_only', 'local draft with explicit limitations', ARRAY['trace_id','agent_name','alias','decision_reason','cost_inr'], 'active'),
    ('complex_planning', 'high', ARRAY['planning','role_scoped_tools'], 'long', 'normal', 120, 'public_or_approved_redacted_internal_only', true,
     'cloud.complex.escalation', 'cloud.volume.default', 'specialist.lead_engineer', ARRAY['glm_failure','release_gate_failure'], 2, 1, false, 'none', 'pause for human or named specialist', ARRAY['trace_id','approval_id','alias','decision_reason','cost_inr'], 'active'),
    ('long_context_tool_use', 'high', ARRAY['retrieval','role_scoped_tools'], 'very_long', 'slow', 120, 'public_or_approved_redacted_internal_only', true,
     'cloud.complex.escalation', 'cloud.volume.default', NULL, ARRAY['context_over_provider_limit','two_failed_attempts'], 2, 1, false, 'none', 'split context and queue reviewed continuation', ARRAY['trace_id','approval_id','alias','context_chars','cost_inr'], 'active'),
    ('difficult_coding', 'high', ARRAY['repository','tests','release_gate'], 'long', 'slow', 150, 'repository_only_no_secrets', true,
     'cloud.complex.escalation', 'cloud.volume.default', 'specialist.lead_engineer', ARRAY['tests_fail_twice','architecture_change'], 2, 1, false, 'none', 'stop at reviewed patch; never deploy automatically', ARRAY['trace_id','approval_id','alias','commit_ref','test_evidence','cost_inr'], 'active'),
    ('investment_research_draft', 'high', ARRAY['public_research','portfolio_read_only','risk_read_only'], 'long', 'normal', 100, 'public_or_local_private_split', true,
     'cloud.complex.escalation', 'local.private.default', 'specialist.senior_investment_reviewer', ARRAY['material_recommendation','conflicting_evidence'], 2, 1, false, 'none', 'retain research draft and require strong review plus human decision', ARRAY['trace_id','approval_id','alias','source_ids','review_status','cost_inr'], 'active'),
    ('client_private_work', 'critical', ARRAY['client_read_only','local_tools'], 'bounded', 'normal', 0, 'client_private_local_only', false,
     'local.private.default', 'local.private.default', NULL, ARRAY[]::TEXT[], 1, 1, false, 'none', 'local deterministic tools or human queue only', ARRAY['trace_id','data_boundary','local_only'], 'active'),
    ('live_trade_execution', 'critical', ARRAY['execution_gate'], 'bounded', 'human', 0, 'restricted', true,
     'local.private.default', 'local.private.default', NULL, ARRAY['always'], 1, 1, false, 'none', 'blocked unless staged-live controls and explicit human confirmation both pass', ARRAY['trace_id','approval_id','human_confirmation','execution_gate'], 'blocked_by_default')
ON CONFLICT (task_type) DO UPDATE SET
    risk = EXCLUDED.risk,
    tools = EXCLUDED.tools,
    context_need = EXCLUDED.context_need,
    latency = EXCLUDED.latency,
    cost_ceiling_inr = EXCLUDED.cost_ceiling_inr,
    data_boundary = EXCLUDED.data_boundary,
    approval_required = EXCLUDED.approval_required,
    primary_alias = EXCLUDED.primary_alias,
    fallback_alias = EXCLUDED.fallback_alias,
    escalation_alias = EXCLUDED.escalation_alias,
    escalation_triggers = EXCLUDED.escalation_triggers,
    max_attempts = EXCLUDED.max_attempts,
    concurrency_limit = EXCLUDED.concurrency_limit,
    batching_allowed = EXCLUDED.batching_allowed,
    cache_policy = EXCLUDED.cache_policy,
    degradation_behavior = EXCLUDED.degradation_behavior,
    trace_fields = EXCLUDED.trace_fields,
    status = EXCLUDED.status,
    updated_at = now();

UPDATE agent.system_model_budget_policies
SET monthly_soft_cap_inr = 3000,
    monthly_hard_cap_inr = 4000,
    daily_hard_cap_inr = 150,
    heavy_reserve_pct = 20,
    hard_stop_on_breach = true,
    notes = 'Approved operating band INR 3,000-4,000. Enforce per-agent caps, concurrency limits, local-first routing, batching, caching, and explicit escalation.',
    evidence = coalesce(evidence, '{}'::jsonb) || '{"approved_strategy":"deepseek_v4_flash_to_glm_5_2_to_named_heavy_specialist","approved_at":"2026-08-10"}'::jsonb,
    updated_at = now()
WHERE status = 'active';

CREATE OR REPLACE VIEW agent.v_model_router_registry AS
SELECT
    task.task_type,
    task.risk,
    task.tools,
    task.context_need,
    task.latency,
    task.cost_ceiling_inr,
    task.data_boundary,
    task.approval_required,
    task.primary_alias,
    primary_alias.route_name AS primary_route,
    primary_alias.provider_binding AS primary_provider,
    primary_alias.model_binding AS primary_model,
    task.fallback_alias,
    fallback_alias.route_name AS fallback_route,
    task.escalation_alias,
    escalation_alias.route_name AS escalation_route,
    task.escalation_triggers,
    task.max_attempts,
    task.concurrency_limit,
    task.batching_allowed,
    task.cache_policy,
    task.degradation_behavior,
    task.trace_fields,
    task.status
FROM agent.task_routing_registry task
JOIN agent.model_alias_registry primary_alias ON primary_alias.alias_key = task.primary_alias
JOIN agent.model_alias_registry fallback_alias ON fallback_alias.alias_key = task.fallback_alias
LEFT JOIN agent.model_alias_registry escalation_alias ON escalation_alias.alias_key = task.escalation_alias;

CREATE OR REPLACE VIEW agent.v_named_heavy_specialists AS
SELECT
    allowlist.agent_name,
    allowlist.alias_key,
    alias.route_name,
    alias.status,
    allowlist.allowed_use,
    allowlist.approval_required,
    alias.data_boundary
FROM agent.model_alias_agent_allowlist allowlist
JOIN agent.model_alias_registry alias USING (alias_key)
WHERE alias.provider_binding = 'operator_selected_heavy_llama';

COMMIT;
