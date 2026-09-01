\set ON_ERROR_STOP on

BEGIN;

-- GLM 5.3 Flash is registered as an approval-gated public-research canary.
-- Normal Research Cases continue on the current selected route until this
-- candidate has a completed structured-output canary and named human review.
INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier,
    input_usd_per_1m_tokens, output_usd_per_1m_tokens,
    rate_source, status, effective_at, notes, metadata
)
VALUES (
    'openrouter', 'z-ai/glm-5.3-flash', 'cloud_low',
    0.150000, 0.500000,
    'openrouter_model_page_2026_09_01_conservative_ceiling',
    'active', '2026-09-01 00:00:00+00',
    'Conservative non-promotional ceiling for the public-only research canary. Every run remains ZDR, cost-capped and explicitly approved.',
    '{"catalog_checked_at":"2026-09-01","public_only":true,"zdr_required":true,"data_collection":"deny","promotional_price_not_relied_on":true}'::jsonb
)
ON CONFLICT (provider, model_name, effective_at) DO UPDATE SET
    cost_tier = EXCLUDED.cost_tier,
    input_usd_per_1m_tokens = EXCLUDED.input_usd_per_1m_tokens,
    output_usd_per_1m_tokens = EXCLUDED.output_usd_per_1m_tokens,
    rate_source = EXCLUDED.rate_source,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
)
VALUES (
    'openrouter_public_lead_glm53_flash_canary',
    'public_company_lead_canary',
    'openrouter',
    'z-ai/glm-5.3-flash',
    'openrouter',
    'deepseek/deepseek-v4-pro-0813',
    'cloud_low',
    'GLM 5.3 Flash public-research daily-driver candidate. Disabled for normal routing; runnable only through explicit public canary preflight and confirmation.',
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
    enabled = false;

INSERT INTO agent.model_alias_registry (
    alias_key, route_name, provider_binding, model_binding, secret_ref,
    data_boundary, approval_required, fallback_alias, escalation_alias,
    status, notes, config
)
VALUES (
    'research.public.lead.glm53_flash',
    'openrouter_public_lead_glm53_flash_canary',
    'openrouter',
    'z-ai/glm-5.3-flash',
    'AI_OS_OPENROUTER_API_KEY',
    'public_only',
    true,
    'research.public.lead.deepseek_v4_pro',
    'research.public.lead.deepseek_v4_pro',
    'canary_only',
    'Cost-efficient public Research Desk candidate. Promotion requires a completed canary plus named citation and numeric review.',
    '{"zdr_required":true,"data_collection":"deny","public_only":true,"role":"research_daily_driver_candidate","broker_write_allowed":false,"external_write_allowed":false}'::jsonb
)
ON CONFLICT (alias_key) DO UPDATE SET
    route_name = EXCLUDED.route_name,
    provider_binding = EXCLUDED.provider_binding,
    model_binding = EXCLUDED.model_binding,
    secret_ref = EXCLUDED.secret_ref,
    data_boundary = EXCLUDED.data_boundary,
    approval_required = true,
    fallback_alias = EXCLUDED.fallback_alias,
    escalation_alias = EXCLUDED.escalation_alias,
    status = 'canary_only',
    notes = EXCLUDED.notes,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    251,
    '251_glm53_flash_research_canary_v1',
    'd7d8f8de4c972594508dc6f94e4f817b2e8d86554c327b2285a4f2f6c5936e41',
    'Approval-gated GLM 5.3 Flash public-research daily-driver canary',
    '{"public_only":true,"zdr_required":true,"private_data_egress_allowed":false,"broker_write_allowed":false,"normal_routing_enabled":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
