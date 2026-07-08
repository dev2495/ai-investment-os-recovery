CREATE TABLE IF NOT EXISTS agent.model_cost_rates (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    cost_tier TEXT NOT NULL DEFAULT 'local',
    input_usd_per_1m_tokens NUMERIC,
    output_usd_per_1m_tokens NUMERIC,
    rate_source TEXT NOT NULL DEFAULT 'local_config',
    status TEXT NOT NULL DEFAULT 'active',
    effective_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, model_name, effective_at)
);

CREATE INDEX IF NOT EXISTS idx_model_cost_rates_provider_model
    ON agent.model_cost_rates (provider, model_name, effective_at DESC);

CREATE TABLE IF NOT EXISTS agent.model_usage_events (
    id BIGSERIAL PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_kind TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT,
    agent_name TEXT,
    route_name TEXT,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    endpoint_key TEXT,
    task_class TEXT,
    usage_kind TEXT NOT NULL DEFAULT 'chat',
    model_status TEXT NOT NULL DEFAULT 'unknown',
    prompt_tokens_est BIGINT,
    completion_tokens_est BIGINT,
    total_tokens_est BIGINT,
    actual_prompt_tokens BIGINT,
    actual_completion_tokens BIGINT,
    actual_total_tokens BIGINT,
    estimated_cost_usd NUMERIC,
    actual_cost_usd NUMERIC,
    cost_currency TEXT NOT NULL DEFAULT 'USD',
    cost_tier TEXT NOT NULL DEFAULT 'local',
    estimate_method TEXT NOT NULL DEFAULT 'unknown',
    rate_id BIGINT REFERENCES agent.model_cost_rates(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    chat_turn_id BIGINT REFERENCES agent.chat_turns(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'AI OS',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_model_usage_source_ref
    ON agent.model_usage_events (source_kind, source_ref)
    WHERE source_ref IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_model_usage_event_ts
    ON agent.model_usage_events (event_ts DESC);

CREATE INDEX IF NOT EXISTS idx_model_usage_agent
    ON agent.model_usage_events (agent_name, event_ts DESC);

CREATE INDEX IF NOT EXISTS idx_model_usage_route
    ON agent.model_usage_events (route_name, event_ts DESC);

CREATE INDEX IF NOT EXISTS idx_model_usage_provider_model
    ON agent.model_usage_events (provider, model_name, event_ts DESC);

CREATE TABLE IF NOT EXISTS agent.model_cost_caps (
    agent_name TEXT PRIMARY KEY REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    daily_cap_usd NUMERIC NOT NULL DEFAULT 0,
    monthly_cap_usd NUMERIC NOT NULL DEFAULT 0,
    max_cost_tier TEXT NOT NULL DEFAULT 'local',
    cloud_requires_approval BOOLEAN NOT NULL DEFAULT true,
    autonomous_cloud_allowed BOOLEAN NOT NULL DEFAULT false,
    hard_stop_on_breach BOOLEAN NOT NULL DEFAULT true,
    alert_threshold_pct NUMERIC NOT NULL DEFAULT 80,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_by TEXT NOT NULL DEFAULT 'AI Engineering',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, notes, metadata
)
SELECT DISTINCT
    lower(coalesce(endpoint.provider, route.default_provider, 'local')) AS provider,
    coalesce(endpoint.model_name, route.default_model) AS model_name,
    'local' AS cost_tier,
    0 AS input_usd_per_1m_tokens,
    0 AS output_usd_per_1m_tokens,
    'local_runtime_zero_metered_cost' AS rate_source,
    'active' AS status,
    'Local model runtime. Ledger records usage; metered API cost is zero unless a paid endpoint rate is explicitly registered.' AS notes,
    jsonb_build_object('source', 'agent.model_endpoints/model_routes', 'pricing_policy', 'local_zero_cost')
FROM agent.model_routes route
LEFT JOIN agent.model_endpoints endpoint ON endpoint.route_name = route.route_name
WHERE lower(coalesce(endpoint.provider, route.default_provider, 'local')) IN ('ollama', 'mlx', 'local', 'lm_studio')
  AND coalesce(endpoint.model_name, route.default_model) IS NOT NULL
ON CONFLICT (provider, model_name, effective_at) DO NOTHING;

INSERT INTO agent.model_cost_caps (
    agent_name, daily_cap_usd, monthly_cap_usd, max_cost_tier,
    cloud_requires_approval, autonomous_cloud_allowed, hard_stop_on_breach,
    alert_threshold_pct, notes, evidence, updated_by
)
SELECT
    profile.agent_name,
    CASE WHEN coalesce(assign.max_autonomous_cost_tier, 'local') = 'local' THEN 0 ELSE 1 END AS daily_cap_usd,
    CASE WHEN coalesce(assign.max_autonomous_cost_tier, 'local') = 'local' THEN 0 ELSE 20 END AS monthly_cap_usd,
    coalesce(assign.max_autonomous_cost_tier, 'local') AS max_cost_tier,
    true AS cloud_requires_approval,
    false AS autonomous_cloud_allowed,
    true AS hard_stop_on_breach,
    80 AS alert_threshold_pct,
    'Initial safety cap generated from active agent model assignment. Local-first agents have zero autonomous cloud budget.' AS notes,
    jsonb_build_array(jsonb_build_object('source', 'agent.agent_model_assignments', 'cost_policy', coalesce(assign.cost_policy, profile.cost_policy))),
    'AI Engineering'
FROM agent.profiles profile
LEFT JOIN agent.agent_model_assignments assign ON assign.agent_name = profile.agent_name
WHERE profile.status = 'active'
ON CONFLICT (agent_name) DO UPDATE SET
    max_cost_tier = EXCLUDED.max_cost_tier,
    cloud_requires_approval = EXCLUDED.cloud_requires_approval,
    autonomous_cloud_allowed = EXCLUDED.autonomous_cloud_allowed,
    hard_stop_on_breach = EXCLUDED.hard_stop_on_breach,
    alert_threshold_pct = EXCLUDED.alert_threshold_pct,
    updated_at = now();

WITH chat_usage AS (
    SELECT
        chat.id AS chat_turn_id,
        chat.created_at AS event_ts,
        'chat_turn'::TEXT AS source_kind,
        chat.id::TEXT AS source_ref,
        chat.assistant_name AS agent_name,
        chat.route_name,
        lower(coalesce(chat.model_provider, 'unknown')) AS provider,
        coalesce(chat.model_name, 'unknown') AS model_name,
        'chat'::TEXT AS usage_kind,
        chat.model_status,
        greatest(1, ceil(length(coalesce(chat.user_message, '')) / 4.0))::BIGINT AS prompt_tokens_est,
        greatest(1, ceil(length(coalesce(chat.assistant_message, '')) / 4.0))::BIGINT AS completion_tokens_est,
        greatest(2, ceil((length(coalesce(chat.user_message, '')) + length(coalesce(chat.assistant_message, ''))) / 4.0))::BIGINT AS total_tokens_est,
        jsonb_build_array(jsonb_build_object('source', 'agent.chat_turns', 'id', chat.id, 'model_status', chat.model_status)) AS evidence,
        jsonb_build_object('backfilled_from', 'agent.chat_turns', 'session_key', chat.session_key) AS metadata
    FROM agent.chat_turns chat
),
priced AS (
    SELECT
        chat_usage.*,
        rate.id AS rate_id,
        coalesce(rate.cost_tier, CASE WHEN chat_usage.provider IN ('ollama','mlx','local','lm_studio') THEN 'local' ELSE 'unknown' END) AS cost_tier,
        CASE
            WHEN rate.input_usd_per_1m_tokens IS NOT NULL AND rate.output_usd_per_1m_tokens IS NOT NULL THEN
                round(
                    ((chat_usage.prompt_tokens_est::NUMERIC * rate.input_usd_per_1m_tokens)
                    + (chat_usage.completion_tokens_est::NUMERIC * rate.output_usd_per_1m_tokens)) / 1000000,
                    8
                )
            WHEN chat_usage.provider IN ('ollama','mlx','local','lm_studio') THEN 0
            ELSE NULL
        END AS estimated_cost_usd
    FROM chat_usage
    LEFT JOIN LATERAL (
        SELECT rate.*
        FROM agent.model_cost_rates rate
        WHERE lower(rate.provider) = chat_usage.provider
          AND rate.model_name = chat_usage.model_name
          AND rate.status = 'active'
        ORDER BY rate.effective_at DESC
        LIMIT 1
    ) rate ON true
)
INSERT INTO agent.model_usage_events (
    event_ts, source_kind, source_ref, agent_name, route_name, provider,
    model_name, usage_kind, model_status, prompt_tokens_est,
    completion_tokens_est, total_tokens_est, estimated_cost_usd,
    cost_tier, estimate_method, rate_id, chat_turn_id, evidence, metadata,
    created_by
)
SELECT
    event_ts, source_kind, source_ref, agent_name, route_name, provider,
    model_name, usage_kind, model_status, prompt_tokens_est,
    completion_tokens_est, total_tokens_est, estimated_cost_usd,
    cost_tier, 'chars_div_4_from_chat_turn', rate_id, chat_turn_id, evidence,
    metadata, 'AI OS backfill'
FROM priced
ON CONFLICT (source_kind, source_ref) WHERE source_ref IS NOT NULL DO UPDATE SET
    model_status = EXCLUDED.model_status,
    prompt_tokens_est = EXCLUDED.prompt_tokens_est,
    completion_tokens_est = EXCLUDED.completion_tokens_est,
    total_tokens_est = EXCLUDED.total_tokens_est,
    estimated_cost_usd = EXCLUDED.estimated_cost_usd,
    rate_id = EXCLUDED.rate_id,
    updated_at = now();

CREATE OR REPLACE VIEW agent.v_model_cost_ledger_events AS
SELECT
    usage.id,
    usage.event_ts,
    usage.source_kind,
    usage.source_ref,
    usage.agent_name,
    profile.display_title AS agent_title,
    profile.department,
    usage.route_name,
    route.task_class,
    usage.provider,
    usage.model_name,
    usage.endpoint_key,
    usage.usage_kind,
    usage.model_status,
    usage.prompt_tokens_est,
    usage.completion_tokens_est,
    usage.total_tokens_est,
    usage.actual_total_tokens,
    usage.estimated_cost_usd,
    usage.actual_cost_usd,
    usage.cost_currency,
    usage.cost_tier,
    usage.estimate_method,
    usage.rate_id,
    usage.approval_id,
    usage.task_id,
    usage.chat_turn_id,
    usage.evidence,
    usage.metadata,
    cap.daily_cap_usd,
    cap.monthly_cap_usd,
    cap.max_cost_tier,
    cap.cloud_requires_approval,
    cap.autonomous_cloud_allowed,
    CASE
        WHEN usage.cost_tier = 'local' OR usage.provider IN ('ollama','mlx','local','lm_studio') THEN false
        ELSE true
    END AS is_cloud_usage,
    CASE
        WHEN usage.estimated_cost_usd IS NULL
         AND usage.provider NOT IN ('ollama','mlx','local','lm_studio') THEN 'rate_missing'
        WHEN usage.cost_tier <> 'local'
         AND coalesce(cap.cloud_requires_approval, true)
         AND usage.approval_id IS NULL THEN 'approval_required'
        ELSE 'ok'
    END AS cost_control_status,
    usage.created_at,
    usage.updated_at
FROM agent.model_usage_events usage
LEFT JOIN agent.profiles profile ON profile.agent_name = usage.agent_name
LEFT JOIN agent.model_routes route ON route.route_name = usage.route_name
LEFT JOIN agent.model_cost_caps cap ON cap.agent_name = usage.agent_name;

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
        WHEN coalesce(usage_rollup.cost_today_usd, 0) > coalesce(cap.daily_cap_usd, 0) THEN 'daily_cap_breach'
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

CREATE OR REPLACE VIEW agent.v_model_route_cost_summary AS
SELECT
    coalesce(usage.route_name, 'unrouted') AS route_name,
    coalesce(route.task_class, 'unknown') AS task_class,
    usage.provider,
    usage.model_name,
    usage.cost_tier,
    count(*)::BIGINT AS usage_events,
    count(*) FILTER (WHERE usage.event_ts >= current_date)::BIGINT AS usage_events_today,
    sum(coalesce(usage.total_tokens_est, usage.actual_total_tokens, 0))::BIGINT AS total_tokens_est,
    coalesce(sum(coalesce(usage.actual_cost_usd, usage.estimated_cost_usd, 0)), 0)::NUMERIC AS cost_usd,
    max(usage.event_ts) AS latest_event_ts,
    count(*) FILTER (WHERE usage.cost_control_status = 'approval_required')::BIGINT AS approval_required_events,
    count(*) FILTER (WHERE usage.cost_control_status = 'rate_missing')::BIGINT AS rate_missing_events
FROM agent.v_model_cost_ledger_events usage
LEFT JOIN agent.model_routes route ON route.route_name = usage.route_name
GROUP BY coalesce(usage.route_name, 'unrouted'), coalesce(route.task_class, 'unknown'),
         usage.provider, usage.model_name, usage.cost_tier;

CREATE OR REPLACE VIEW agent.v_model_cost_summary AS
SELECT
    'total_usage_events' AS metric,
    count(*)::TEXT AS value,
    min(event_ts) AS first_seen_at,
    max(event_ts) AS latest_seen_at,
    'All recorded local/cloud model usage events.' AS interpretation
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'local_usage_events',
    count(*) FILTER (WHERE is_cloud_usage = false)::TEXT,
    min(event_ts),
    max(event_ts),
    'Usage events routed through local or zero-metered runtimes.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'cloud_usage_events',
    count(*) FILTER (WHERE is_cloud_usage = true)::TEXT,
    min(event_ts),
    max(event_ts),
    'Usage events routed through paid/cloud runtimes.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'estimated_cost_today_usd',
    coalesce(round(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= current_date), 6), 0)::TEXT,
    min(event_ts),
    max(event_ts),
    'Estimated plus actual recorded model cost today.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'estimated_cost_month_usd',
    coalesce(round(sum(coalesce(actual_cost_usd, estimated_cost_usd, 0)) FILTER (WHERE event_ts >= date_trunc('month', now())), 6), 0)::TEXT,
    min(event_ts),
    max(event_ts),
    'Estimated plus actual recorded model cost this month.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'unapproved_cloud_events',
    count(*) FILTER (WHERE cost_control_status = 'approval_required')::TEXT,
    min(event_ts),
    max(event_ts),
    'Cloud usage events without linked human approval.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'rate_missing_events',
    count(*) FILTER (WHERE cost_control_status = 'rate_missing')::TEXT,
    min(event_ts),
    max(event_ts),
    'Non-local usage events without a registered model cost rate.'
FROM agent.v_model_cost_ledger_events
UNION ALL
SELECT
    'agents_with_caps',
    count(*)::TEXT,
    min(updated_at),
    max(updated_at),
    'Active agents with configured model cost caps.'
FROM agent.v_agent_model_cost_cap_status;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
    (
        'ai_os_model_cost_ledger',
        'mcp_tool',
        'AI Engineering',
        'read_only',
        true,
        'Read model usage events, route cost summaries, and per-agent cost cap status.',
        '{"reads":["agent.v_model_cost_ledger_events","agent.v_model_cost_summary","agent.v_agent_model_cost_cap_status","agent.v_model_route_cost_summary"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_record_model_usage',
        'mcp_tool',
        'AI Engineering',
        'write_db_manual_only',
        true,
        'Record a model usage event with estimated or actual token/cost metadata.',
        '{"writes":["agent.model_usage_events","agent.mcp_audit_log"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
