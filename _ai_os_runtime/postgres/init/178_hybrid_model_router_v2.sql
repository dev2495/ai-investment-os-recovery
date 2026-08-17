BEGIN;

INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, effective_at, notes, metadata
)
SELECT row_values.*
FROM (
    VALUES
      ('openrouter','openai/gpt-5.6-luna','cloud_low',0.10::numeric,0.60::numeric,'openrouter_promo_2026_08_02','active','2026-08-02T00:00:00Z'::timestamptz,'Temporary OpenRouter promotional rate. Budget planning continues to use the official $0.20/$1.20 list rate.','{"zdr":true,"data_collection":"deny","autonomous_eligible":true,"temporary_promotion":true,"source":"https://openrouter.ai/openai/gpt-5.6-luna-20260709"}'::jsonb),
      ('openrouter','google/gemini-3.6-flash','cloud_medium',1.50::numeric,7.50::numeric,'openrouter_model_page_2026_08_02','active','2026-08-02T00:00:00Z'::timestamptz,'Explicit multimodal public/internal research route under the shared INR cap.','{"zdr":true,"data_collection":"deny","autonomous_eligible":false,"source":"https://openrouter.ai/google/gemini-3.6-flash"}'::jsonb)
) AS row_values(provider,model_name,cost_tier,input_usd_per_1m_tokens,output_usd_per_1m_tokens,rate_source,status,effective_at,notes,metadata)
WHERE NOT EXISTS (
    SELECT 1 FROM agent.model_cost_rates existing
    WHERE existing.provider=row_values.provider
      AND existing.model_name=row_values.model_name
      AND existing.effective_at=row_values.effective_at
);

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES (
    'openrouter_gemini36_research',
    'public_internal_multimodal_research_and_agentic_synthesis',
    'openrouter','google/gemini-3.6-flash',
    'openrouter','openai/gpt-5.6-terra','cloud_medium',
    'Explicit operator selection for public/internal research, PDFs, images, and evidence synthesis. No client-private context, autonomous capital action, or execution authority.',
    true
)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class,
    default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model,
    escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model,
    max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes,
    enabled=EXCLUDED.enabled;

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, secret_ref, health_status,
    owner_agent, notes, config
) VALUES (
    'openrouter_google_gemini_3_6_flash','OpenRouter Gemini 3.6 Flash',
    'openrouter','google/gemini-3.6-flash','openrouter_gemini36_research','cloud',
    'https://openrouter.ai/api/v1','managed_cloud','configured',1048576,0,
    'cloud_medium',ARRAY['text','image_input','pdf_input','video_input','audio_input','tools','structured_output','multimodal_research'],
    true,'AI_OS_OPENROUTER_API_KEY','configured','AI Runtime Engineer',
    'Explicit public/internal multimodal research route. Client-private material and broker actions are prohibited.',
    '{"api":"chat_completions","zdr":true,"data_collection":"deny","reasoning_effort":"medium","deprecated_sampling_parameters_omitted":true,"raw_prompt_stored":false,"client_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    base_url=EXCLUDED.base_url,
    context_window=EXCLUDED.context_window,
    cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    secret_ref=EXCLUDED.secret_ref,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();

UPDATE agent.agent_model_assignments
SET escalation_triggers=(
      SELECT ARRAY(
        SELECT DISTINCT trigger_name
        FROM unnest(
          coalesce(agent.agent_model_assignments.escalation_triggers,ARRAY[]::TEXT[])
          || ARRAY['operator_selected_multimodal_research']
        ) AS trigger_name
      )
    ),
    notes='Private/client context stays local. Luna is capped volume; Gemini 3.6 Flash and Terra are explicit public/internal research routes; Sol is rare review. All cloud routes share the global INR cap.',
    updated_at=now()
WHERE agent_name='Charlie Munger';

COMMIT;
