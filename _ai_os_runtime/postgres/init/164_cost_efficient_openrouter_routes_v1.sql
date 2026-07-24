BEGIN;

-- Verified against the OpenRouter public catalog on 2026-07-25. Cloud routes
-- remain explicit, ZDR-only, client-data-blocked, and subject to hard caps.
INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, effective_at, notes, metadata
) VALUES
    ('openrouter', 'deepseek/deepseek-v4-flash', 'cloud_low', 0.0980, 0.1960,
     'openrouter_models_api_2026_07_25', 'active', '2026-07-25 00:00:00+00',
     'Economical tool-capable route for public/internal summaries and bounded office work.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-25","live_execution_allowed":false}'::jsonb),
    ('openrouter', 'qwen/qwen3.7-plus', 'cloud_low', 0.3200, 1.2800,
     'openrouter_models_api_2026_07_25', 'active', '2026-07-25 00:00:00+00',
     'Fallback for explicit public/internal research when the cheapest route is unavailable.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-25","live_execution_allowed":false}'::jsonb),
    ('openrouter', 'minimax/minimax-m3', 'cloud_medium', 0.3000, 1.2000,
     'openrouter_models_api_2026_07_25', 'active', '2026-07-25 00:00:00+00',
     'Long-context synthesis route for explicitly approved public/internal research.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-25","live_execution_allowed":false}'::jsonb),
    ('openrouter', 'z-ai/glm-5.2', 'cloud_medium', 0.7756, 2.4376,
     'openrouter_models_api_2026_07_25', 'active', '2026-07-25 00:00:00+00',
     'Independent review route; not used for routine chat.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-25","live_execution_allowed":false}'::jsonb)
ON CONFLICT (provider, model_name, effective_at) DO UPDATE SET
    cost_tier=EXCLUDED.cost_tier,
    input_usd_per_1m_tokens=EXCLUDED.input_usd_per_1m_tokens,
    output_usd_per_1m_tokens=EXCLUDED.output_usd_per_1m_tokens,
    rate_source=EXCLUDED.rate_source,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes,
    metadata=EXCLUDED.metadata,
    updated_at=now();

UPDATE agent.model_routes
SET default_provider='openrouter',
    default_model='deepseek/deepseek-v4-flash',
    escalation_provider='openrouter',
    escalation_model='qwen/qwen3.7-plus',
    max_cost_tier='cloud_low',
    notes='Explicit public/internal fast route. Cheapest provider selected with ZDR; client data is blocked; cost hard stops apply.',
    enabled=true
WHERE route_name='openrouter_research_fast';

UPDATE agent.model_routes
SET default_provider='openrouter',
    default_model='minimax/minimax-m3',
    escalation_provider='openrouter',
    escalation_model='z-ai/glm-5.2',
    max_cost_tier='cloud_medium',
    notes='Explicit long-context public/internal synthesis. ZDR and hard cost stops apply.',
    enabled=true
WHERE route_name='openrouter_research_deep';

UPDATE agent.model_routes
SET default_provider='openrouter',
    default_model='z-ai/glm-5.2',
    escalation_provider=NULL,
    escalation_model=NULL,
    max_cost_tier='cloud_medium',
    notes='Explicit independent review of public/internal material. Never used for broker execution.',
    enabled=true
WHERE route_name='openrouter_research_review';

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, cost_tier, capabilities,
    requires_api_key, secret_ref, health_status, owner_agent, notes, config
) VALUES
    ('openrouter_deepseek_v4_flash', 'OpenRouter DeepSeek V4 Flash economy route', 'openrouter',
     'deepseek/deepseek-v4-flash', 'openrouter_research_fast', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_explicit_request', 'configured', 1000000,
     'cloud_low', ARRAY['text','structured_outputs','tools','research_summary'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Public/internal only. Provider selection is price-sorted and ZDR constrained.',
     '{"approval_required":true,"zdr_required":true,"raw_prompt_storage":false,"client_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_qwen3_7_plus', 'OpenRouter Qwen 3.7 Plus fallback', 'openrouter',
     'qwen/qwen3.7-plus', 'openrouter_research_fast', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_explicit_request', 'configured', 1000000,
     'cloud_low', ARRAY['text','structured_outputs','tools','research_summary'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Fallback for the economy route; client-private material is blocked.',
     '{"approval_required":true,"zdr_required":true,"raw_prompt_storage":false,"client_data_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    context_window=EXCLUDED.context_window,
    cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();

UPDATE agent.model_cost_caps
SET daily_cap_usd=1.00,
    monthly_cap_usd=25.00,
    max_cost_tier='cloud_medium',
    cloud_requires_approval=true,
    autonomous_cloud_allowed=false,
    hard_stop_on_breach=true,
    alert_threshold_pct=80,
    notes='Local/private by default. Cloud is explicit, public/internal only, USD 1 daily and USD 25 monthly hard stops.',
    evidence=coalesce(evidence, '[]'::jsonb) || jsonb_build_array(
        jsonb_build_object('source','openrouter_models_api','verified_at','2026-07-25'),
        jsonb_build_object('source','operator_budget','monthly_inr_ceiling','3000-5000')
    ),
    updated_by='AI Engineering',
    updated_at=now()
WHERE agent_name='Charlie Munger';

COMMIT;
