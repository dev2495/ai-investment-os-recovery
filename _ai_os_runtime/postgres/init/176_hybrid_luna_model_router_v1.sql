BEGIN;

CREATE TABLE IF NOT EXISTS agent.system_model_budget_policies (
    policy_key TEXT PRIMARY KEY,
    currency TEXT NOT NULL DEFAULT 'INR',
    monthly_soft_cap_inr NUMERIC NOT NULL,
    monthly_hard_cap_inr NUMERIC NOT NULL,
    daily_hard_cap_inr NUMERIC NOT NULL,
    usd_inr_budget_rate NUMERIC NOT NULL,
    heavy_reserve_pct NUMERIC NOT NULL DEFAULT 20,
    hard_stop_on_breach BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'active',
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO agent.system_model_budget_policies (
    policy_key, currency, monthly_soft_cap_inr, monthly_hard_cap_inr,
    daily_hard_cap_inr, usd_inr_budget_rate, heavy_reserve_pct,
    hard_stop_on_breach, status, notes, evidence
) VALUES (
    'ai_os_cloud', 'INR', 3000, 4500, 150, 90, 20, true, 'active',
    'Global cloud-model budget. Luna is the autonomous low-cost volume tier; Terra and Sol require explicit escalation. Local and deterministic work is excluded.',
    '[{"source":"https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/","published":"2026-07-30","luna_input_usd_per_1m":0.20,"luna_output_usd_per_1m":1.20,"terra_input_usd_per_1m":2.00,"terra_output_usd_per_1m":12.00,"sol_input_usd_per_1m":5.00,"sol_output_usd_per_1m":30.00},{"source":"operator_budget","monthly_target_inr":"3000-5000","hard_cap_inr":4500,"daily_hard_cap_inr":150}]'::jsonb
)
ON CONFLICT (policy_key) DO UPDATE SET
    monthly_soft_cap_inr=EXCLUDED.monthly_soft_cap_inr,
    monthly_hard_cap_inr=EXCLUDED.monthly_hard_cap_inr,
    daily_hard_cap_inr=EXCLUDED.daily_hard_cap_inr,
    usd_inr_budget_rate=EXCLUDED.usd_inr_budget_rate,
    heavy_reserve_pct=EXCLUDED.heavy_reserve_pct,
    hard_stop_on_breach=EXCLUDED.hard_stop_on_breach,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes,
    evidence=EXCLUDED.evidence,
    updated_at=now();

INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, effective_at, notes, metadata
)
SELECT values_row.*
FROM (
    VALUES
      ('openai','gpt-5.6-luna','cloud_low',0.20::numeric,1.20::numeric,'openai_official_2026_07_30','active','2026-07-30T00:00:00Z'::timestamptz,'High-volume routine cloud model. Stateless Responses requests only.','{"store":false,"autonomous_eligible":true}'::jsonb),
      ('openrouter','openai/gpt-5.6-luna','cloud_low',0.50::numeric,3.00::numeric,'openrouter_model_page_2026_08_01','active','2026-08-01T00:00:00Z'::timestamptz,'Existing-credential Luna route at the current OpenRouter promotional rate. OpenAI direct remains cheaper when configured.','{"zdr":true,"data_collection":"deny","autonomous_eligible":true,"source":"https://openrouter.ai/openai/gpt-5.6-luna-20260709"}'::jsonb),
      ('openai','gpt-5.6-terra','cloud_medium',2.00::numeric,12.00::numeric,'openai_official_2026_07_30','active','2026-07-30T00:00:00Z'::timestamptz,'Deep research and complex synthesis. Explicit approval required.','{"store":false,"autonomous_eligible":false}'::jsonb),
      ('openai','gpt-5.6-sol','frontier',5.00::numeric,30.00::numeric,'openai_official_2026_07_30','active','2026-07-30T00:00:00Z'::timestamptz,'Rare frontier review and committee challenge. Explicit approval required.','{"store":false,"autonomous_eligible":false}'::jsonb)
) AS values_row(provider,model_name,cost_tier,input_usd_per_1m_tokens,output_usd_per_1m_tokens,rate_source,status,effective_at,notes,metadata)
WHERE NOT EXISTS (
    SELECT 1 FROM agent.model_cost_rates existing
    WHERE existing.provider=values_row.provider
      AND existing.model_name=values_row.model_name
      AND existing.effective_at=values_row.effective_at
);

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES
    ('openai_luna_volume','public_internal_routine_conversation_and_drafts','openai','gpt-5.6-luna','openai','gpt-5.6-terra','cloud_low','Autonomous only for public/internal non-client context under per-agent and global hard caps. Responses store=false.',true),
    ('openrouter_luna_volume','public_internal_routine_conversation_and_drafts','openrouter','openai/gpt-5.6-luna','openai','gpt-5.6-terra','cloud_low','Active Luna route using the existing OpenRouter credential with ZDR and data collection denied. Prefer direct OpenAI after its key is configured because direct pricing is lower.',true),
    ('openai_terra_research','deep_public_internal_research_and_synthesis','openai','gpt-5.6-terra','openai','gpt-5.6-sol','cloud_medium','Explicitly approved deep research route. Never receives client-private context.',true),
    ('openai_sol_review','rare_frontier_committee_review','openai','gpt-5.6-sol',NULL,NULL,'frontier','Explicitly approved frontier review route. Never receives client-private context.',true)
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
) VALUES
    ('openai_gpt_5_6_luna','OpenAI GPT-5.6 Luna','openai','gpt-5.6-luna','openai_luna_volume','cloud','https://api.openai.com/v1','managed_cloud','configured',NULL,0,'cloud_low',ARRAY['text','tools','structured_output','routine_synthesis'],true,'AI_OS_OPENAI_API_KEY','needs_secret','AI Runtime Engineer','Capped high-volume cloud fallback. Public/internal only.','{"api":"responses","store":false,"reasoning_effort":"none","raw_prompt_stored":false,"client_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_gpt_5_6_luna','OpenRouter GPT-5.6 Luna','openrouter','openai/gpt-5.6-luna','openrouter_luna_volume','cloud','https://openrouter.ai/api/v1','managed_cloud','configured',1050000,0,'cloud_low',ARRAY['text','tools','structured_output','routine_synthesis'],true,'AI_OS_OPENROUTER_API_KEY','configured','AI Runtime Engineer','Existing-credential capped Luna fallback. Public/internal only; ZDR required.','{"api":"chat_completions","zdr":true,"data_collection":"deny","raw_prompt_stored":false,"client_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('openai_gpt_5_6_terra','OpenAI GPT-5.6 Terra','openai','gpt-5.6-terra','openai_terra_research','cloud','https://api.openai.com/v1','managed_cloud','configured',NULL,0,'cloud_medium',ARRAY['text','tools','structured_output','deep_research'],true,'AI_OS_OPENAI_API_KEY','needs_secret','AI Runtime Engineer','Explicitly approved deep research route.','{"api":"responses","store":false,"raw_prompt_stored":false,"client_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('openai_gpt_5_6_sol','OpenAI GPT-5.6 Sol','openai','gpt-5.6-sol','openai_sol_review','cloud','https://api.openai.com/v1','managed_cloud','configured',NULL,0,'frontier',ARRAY['text','tools','structured_output','frontier_review'],true,'AI_OS_OPENAI_API_KEY','needs_secret','AI Runtime Engineer','Rare explicitly approved committee review route.','{"api":"responses","store":false,"raw_prompt_stored":false,"client_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    base_url=EXCLUDED.base_url,
    status=EXCLUDED.status,
    cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    requires_api_key=EXCLUDED.requires_api_key,
    secret_ref=EXCLUDED.secret_ref,
    owner_agent=EXCLUDED.owner_agent,
    notes=EXCLUDED.notes,
    config=agent.model_endpoints.config || EXCLUDED.config,
    updated_at=now();

UPDATE agent.agent_model_assignments
SET escalation_route='openrouter_luna_volume',
    cost_policy='local_first_luna_volume_heavy_explicit',
    max_autonomous_cost_tier='cloud_low',
    escalation_triggers=ARRAY['local_unavailable','local_eval_blocked','public_internal_volume','operator_selected_cloud'],
    notes='Private/client context stays local. Luna may run autonomously only for public/internal non-client context under per-agent and global caps; Terra/Sol require explicit selection.',
    updated_at=now()
WHERE agent_name='Charlie Munger';

INSERT INTO agent.model_cost_caps (
    agent_name, daily_cap_usd, monthly_cap_usd, max_cost_tier,
    cloud_requires_approval, autonomous_cloud_allowed, hard_stop_on_breach,
    alert_threshold_pct, notes, evidence, updated_by
) VALUES (
    'Charlie Munger', 1.666667, 50, 'frontier', false, true, true, 66.67,
    'OpenRouter Luna autonomous eligibility is limited by the assignment cloud_low tier and global INR caps. Terra/Sol still require explicit route selection and approval.',
    '[{"policy":"agent.system_model_budget_policies/ai_os_cloud","raw_prompt_stored":false,"client_private_cloud_allowed":false,"live_execution_allowed":false}]'::jsonb,
    'AI Engineering'
)
ON CONFLICT (agent_name) DO UPDATE SET
    daily_cap_usd=EXCLUDED.daily_cap_usd,
    monthly_cap_usd=EXCLUDED.monthly_cap_usd,
    max_cost_tier=EXCLUDED.max_cost_tier,
    cloud_requires_approval=EXCLUDED.cloud_requires_approval,
    autonomous_cloud_allowed=EXCLUDED.autonomous_cloud_allowed,
    hard_stop_on_breach=EXCLUDED.hard_stop_on_breach,
    alert_threshold_pct=EXCLUDED.alert_threshold_pct,
    notes=EXCLUDED.notes,
    evidence=EXCLUDED.evidence,
    updated_by=EXCLUDED.updated_by,
    updated_at=now();

CREATE OR REPLACE VIEW agent.v_system_model_budget_status AS
WITH usage_rollup AS (
    SELECT
        coalesce(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= current_date),0)::numeric AS daily_cost_usd,
        coalesce(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= date_trunc('month', now())),0)::numeric AS monthly_cost_usd,
        count(*) FILTER (WHERE event_ts >= current_date)::bigint AS daily_events,
        count(*) FILTER (WHERE event_ts >= date_trunc('month', now()))::bigint AS monthly_events
    FROM agent.model_usage_events
    WHERE lower(provider) NOT IN ('ollama','mlx','local','lm_studio','local_openai','local_python','local_tools','deterministic')
), status AS (
    SELECT policy.*, usage_rollup.*,
           policy.daily_hard_cap_inr / policy.usd_inr_budget_rate AS daily_cap_usd,
           policy.monthly_soft_cap_inr / policy.usd_inr_budget_rate AS monthly_soft_cap_usd,
           policy.monthly_hard_cap_inr / policy.usd_inr_budget_rate AS monthly_hard_cap_usd
    FROM agent.system_model_budget_policies policy
    CROSS JOIN usage_rollup
)
SELECT
    policy_key, currency, monthly_soft_cap_inr, monthly_hard_cap_inr,
    daily_hard_cap_inr, usd_inr_budget_rate, heavy_reserve_pct,
    hard_stop_on_breach, status,
    daily_events, monthly_events, daily_cost_usd, monthly_cost_usd,
    daily_cost_usd * usd_inr_budget_rate AS daily_cost_inr,
    monthly_cost_usd * usd_inr_budget_rate AS monthly_cost_inr,
    greatest(daily_cap_usd-daily_cost_usd,0)::numeric AS daily_remaining_usd,
    greatest(monthly_hard_cap_usd-monthly_cost_usd,0)::numeric AS monthly_remaining_usd,
    greatest(daily_hard_cap_inr-(daily_cost_usd*usd_inr_budget_rate),0)::numeric AS daily_remaining_inr,
    greatest(monthly_hard_cap_inr-(monthly_cost_usd*usd_inr_budget_rate),0)::numeric AS monthly_remaining_inr,
    CASE
      WHEN status <> 'active' THEN 'disabled'
      WHEN daily_cost_usd >= daily_cap_usd THEN 'daily_hard_cap_breach'
      WHEN monthly_cost_usd >= monthly_hard_cap_usd THEN 'monthly_hard_cap_breach'
      WHEN monthly_cost_usd >= monthly_soft_cap_usd THEN 'monthly_soft_cap_alert'
      WHEN monthly_cost_usd >= monthly_hard_cap_usd * (1-heavy_reserve_pct/100) THEN 'heavy_reserve_protected'
      ELSE 'ok'
    END AS budget_status,
    notes, evidence, updated_at
FROM status;

COMMIT;
