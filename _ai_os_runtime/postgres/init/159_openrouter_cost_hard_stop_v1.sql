BEGIN;

INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, effective_at, notes, metadata
) VALUES
    ('openrouter', 'z-ai/glm-4.7-flash', 'cloud_low', 0.0605, 0.4000,
     'openrouter_models_api_2026_07_21', 'active', '2026-07-21 00:00:00+00',
     'OpenRouter public model catalog rate. Refresh before changing production routing.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-21"}'::jsonb),
    ('openrouter', 'minimax/minimax-m3', 'cloud_medium', 0.3000, 1.2000,
     'openrouter_models_api_2026_07_21', 'active', '2026-07-21 00:00:00+00',
     'OpenRouter public model catalog rate. Refresh before changing production routing.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-21"}'::jsonb),
    ('openrouter', 'moonshotai/kimi-k2.6', 'cloud_medium', 0.6840, 3.4200,
     'openrouter_models_api_2026_07_21', 'active', '2026-07-21 00:00:00+00',
     'OpenRouter public model catalog rate. Refresh before changing production routing.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-21"}'::jsonb),
    ('openrouter', 'z-ai/glm-5.2', 'cloud_medium', 0.8176, 2.5696,
     'openrouter_models_api_2026_07_21', 'active', '2026-07-21 00:00:00+00',
     'OpenRouter public model catalog rate. Refresh before changing production routing.',
     '{"source_url":"https://openrouter.ai/api/v1/models","verified_at":"2026-07-21"}'::jsonb)
ON CONFLICT (provider, model_name, effective_at) DO UPDATE SET
    cost_tier=EXCLUDED.cost_tier,
    input_usd_per_1m_tokens=EXCLUDED.input_usd_per_1m_tokens,
    output_usd_per_1m_tokens=EXCLUDED.output_usd_per_1m_tokens,
    rate_source=EXCLUDED.rate_source,
    status=EXCLUDED.status,
    notes=EXCLUDED.notes,
    metadata=EXCLUDED.metadata,
    updated_at=now();

UPDATE agent.model_cost_caps
SET daily_cap_usd=1.00,
    monthly_cap_usd=25.00,
    max_cost_tier='cloud_medium',
    cloud_requires_approval=true,
    autonomous_cloud_allowed=false,
    hard_stop_on_breach=true,
    alert_threshold_pct=80,
    notes='Charlie cloud research budget: explicit approval per request, public/internal data only, USD 1 daily and USD 25 monthly hard stops.',
    evidence=jsonb_build_array(
        jsonb_build_object('source','operator_budget','budget_inr_monthly','3000-5000'),
        jsonb_build_object('source','openrouter_models_api','verified_at','2026-07-21')
    ),
    updated_by='AI Engineering',
    updated_at=now()
WHERE agent_name='Charlie Munger';

CREATE OR REPLACE VIEW agent.v_agent_model_cost_cap_status AS
WITH usage_rollup AS (
    SELECT
        agent_name,
        count(*) FILTER (WHERE event_ts >= current_date)::BIGINT AS events_today,
        count(*) FILTER (WHERE event_ts >= date_trunc('month', now()))::BIGINT AS events_month,
        coalesce(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= current_date), 0)::NUMERIC AS cost_today_usd,
        coalesce(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= date_trunc('month', now())), 0)::NUMERIC AS cost_month_usd,
        count(*) FILTER (
            WHERE event_ts >= current_date
              AND cost_tier <> 'local'
              AND approval_id IS NULL
              AND NOT coalesce((metadata->>'explicit_cloud_approval')::BOOLEAN, false)
        )::BIGINT AS unapproved_cloud_events_today,
        count(*) FILTER (
            WHERE event_ts >= current_date
              AND estimated_cost_usd IS NULL
              AND provider NOT IN ('ollama','mlx','local','lm_studio')
        )::BIGINT AS rate_missing_events_today
    FROM agent.model_usage_events
    GROUP BY agent_name
)
SELECT
    profile.agent_name,
    profile.display_title,
    profile.department,
    coalesce(assign.primary_route, profile.default_model_route) AS primary_route,
    assign.primary_model_key,
    assign.cost_policy,
    assign.max_autonomous_cost_tier,
    cap.daily_cap_usd,
    cap.monthly_cap_usd,
    cap.max_cost_tier,
    cap.cloud_requires_approval,
    cap.autonomous_cloud_allowed,
    cap.hard_stop_on_breach,
    cap.alert_threshold_pct,
    coalesce(usage_rollup.events_today, 0)::BIGINT AS events_today,
    coalesce(usage_rollup.events_month, 0)::BIGINT AS events_month,
    coalesce(usage_rollup.cost_today_usd, 0)::NUMERIC AS cost_today_usd,
    coalesce(usage_rollup.cost_month_usd, 0)::NUMERIC AS cost_month_usd,
    greatest(coalesce(cap.daily_cap_usd, 0) - coalesce(usage_rollup.cost_today_usd, 0), 0)::NUMERIC AS daily_remaining_usd,
    greatest(coalesce(cap.monthly_cap_usd, 0) - coalesce(usage_rollup.cost_month_usd, 0), 0)::NUMERIC AS monthly_remaining_usd,
    coalesce(usage_rollup.unapproved_cloud_events_today, 0)::BIGINT AS unapproved_cloud_events_today,
    coalesce(usage_rollup.rate_missing_events_today, 0)::BIGINT AS rate_missing_events_today,
    CASE
        WHEN coalesce(usage_rollup.rate_missing_events_today, 0) > 0 THEN 'rate_missing'
        WHEN coalesce(usage_rollup.unapproved_cloud_events_today, 0) > 0 THEN 'approval_required'
        WHEN coalesce(usage_rollup.cost_month_usd, 0) > coalesce(cap.monthly_cap_usd, 0) THEN 'monthly_cap_breach'
        WHEN coalesce(usage_rollup.cost_today_usd, 0) > coalesce(cap.daily_cap_usd, 0) THEN 'daily_cap_breach'
        WHEN coalesce(cap.monthly_cap_usd, 0) > 0
         AND coalesce(usage_rollup.cost_month_usd, 0) >= (coalesce(cap.monthly_cap_usd, 0) * coalesce(cap.alert_threshold_pct, 80) / 100) THEN 'near_monthly_cap'
        WHEN coalesce(cap.daily_cap_usd, 0) > 0
         AND coalesce(usage_rollup.cost_today_usd, 0) >= (coalesce(cap.daily_cap_usd, 0) * coalesce(cap.alert_threshold_pct, 80) / 100) THEN 'near_daily_cap'
        ELSE 'ok'
    END AS cap_status,
    cap.notes,
    cap.evidence,
    cap.updated_at
FROM agent.profiles profile
LEFT JOIN agent.agent_model_assignments assign ON assign.agent_name = profile.agent_name
LEFT JOIN agent.model_cost_caps cap ON cap.agent_name = profile.agent_name
LEFT JOIN usage_rollup ON usage_rollup.agent_name = profile.agent_name
WHERE profile.status = 'active';

COMMIT;
