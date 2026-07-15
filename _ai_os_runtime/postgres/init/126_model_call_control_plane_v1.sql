CREATE TABLE IF NOT EXISTS agent.model_privacy_policies (
    privacy_class TEXT PRIMARY KEY CHECK (privacy_class IN ('public','internal','client_private','restricted')),
    local_model_allowed BOOLEAN NOT NULL,
    cloud_model_allowed BOOLEAN NOT NULL,
    cloud_requires_approval BOOLEAN NOT NULL,
    cache_allowed BOOLEAN NOT NULL,
    redaction_required_for_cloud BOOLEAN NOT NULL,
    max_context_chars INTEGER NOT NULL CHECK (max_context_chars > 0),
    retention_days INTEGER NOT NULL CHECK (retention_days >= 0),
    policy_statement TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT 'AI Runtime Engineer',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO agent.model_privacy_policies (
    privacy_class, local_model_allowed, cloud_model_allowed,
    cloud_requires_approval, cache_allowed, redaction_required_for_cloud,
    max_context_chars, retention_days, policy_statement
) VALUES
    ('public', true, true, true, true, false, 24000, 30,
     'Public sourced context may use ready local models and approval-gated cloud models; deterministic cache is allowed.'),
    ('internal', true, true, true, true, true, 18000, 14,
     'Internal operating context stays local by default; any cloud escalation requires approval and redaction review.'),
    ('client_private', true, false, true, false, true, 12000, 0,
     'Client portfolio, holding, trade, journal, or suitability context is local-only and must never enter response cache.'),
    ('restricted', true, false, true, false, true, 8000, 0,
     'Secrets, credentials, privileged legal material, and restricted personal data are local deterministic or local-model only and never cached.')
ON CONFLICT (privacy_class) DO UPDATE SET
    local_model_allowed=EXCLUDED.local_model_allowed,
    cloud_model_allowed=EXCLUDED.cloud_model_allowed,
    cloud_requires_approval=EXCLUDED.cloud_requires_approval,
    cache_allowed=EXCLUDED.cache_allowed,
    redaction_required_for_cloud=EXCLUDED.redaction_required_for_cloud,
    max_context_chars=EXCLUDED.max_context_chars,
    retention_days=EXCLUDED.retention_days,
    policy_statement=EXCLUDED.policy_statement,
    updated_at=now();

CREATE TABLE IF NOT EXISTS agent.model_call_decisions (
    id BIGSERIAL PRIMARY KEY,
    decision_key TEXT NOT NULL UNIQUE,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    department_key TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'api_chat',
    source_ref TEXT,
    requested_route TEXT REFERENCES agent.model_routes(route_name) ON DELETE SET NULL,
    selected_route TEXT REFERENCES agent.model_routes(route_name) ON DELETE SET NULL,
    selected_provider TEXT,
    selected_model TEXT,
    privacy_class TEXT NOT NULL REFERENCES agent.model_privacy_policies(privacy_class) ON DELETE RESTRICT,
    contains_client_data BOOLEAN NOT NULL DEFAULT false,
    prompt_hash TEXT NOT NULL,
    prompt_chars INTEGER NOT NULL CHECK (prompt_chars >= 0),
    decision_status TEXT NOT NULL CHECK (decision_status IN ('allowed','blocked','approval_required','completed','failed')),
    cache_key TEXT,
    cache_status TEXT NOT NULL DEFAULT 'bypassed' CHECK (cache_status IN ('eligible','hit','miss','stored','bypassed','expired')),
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    block_reasons JSONB NOT NULL DEFAULT '[]'::JSONB,
    route_candidates JSONB NOT NULL DEFAULT '[]'::JSONB,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    response_hash TEXT,
    latency_ms INTEGER,
    error_message TEXT,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT chk_model_call_no_capital CHECK (capital_action_allowed=false),
    CONSTRAINT chk_model_call_no_execution CHECK (live_execution_allowed=false)
);

CREATE INDEX IF NOT EXISTS idx_model_call_decisions_created
    ON agent.model_call_decisions (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_call_decisions_agent
    ON agent.model_call_decisions (agent_name, created_at DESC);

CREATE TABLE IF NOT EXISTS agent.model_response_cache (
    cache_key TEXT PRIMARY KEY,
    route_name TEXT NOT NULL REFERENCES agent.model_routes(route_name) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    privacy_class TEXT NOT NULL REFERENCES agent.model_privacy_policies(privacy_class) ON DELETE RESTRICT,
    prompt_hash TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_hash TEXT NOT NULL,
    hit_count BIGINT NOT NULL DEFAULT 0,
    last_hit_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_model_cache_non_private CHECK (privacy_class IN ('public','internal'))
);

CREATE INDEX IF NOT EXISTS idx_model_response_cache_expiry
    ON agent.model_response_cache (expires_at);

CREATE TABLE IF NOT EXISTS agent.model_escalation_requests (
    id BIGSERIAL PRIMARY KEY,
    escalation_key TEXT NOT NULL UNIQUE,
    decision_id BIGINT NOT NULL UNIQUE REFERENCES agent.model_call_decisions(id) ON DELETE CASCADE,
    requested_provider TEXT NOT NULL,
    requested_model TEXT,
    requested_cost_tier TEXT NOT NULL,
    reason TEXT NOT NULL,
    privacy_review_status TEXT NOT NULL DEFAULT 'pending' CHECK (privacy_review_status IN ('pending','passed','blocked')),
    cost_review_status TEXT NOT NULL DEFAULT 'pending' CHECK (cost_review_status IN ('pending','passed','blocked')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired','cancelled')),
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    requested_by TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_model_escalation_no_capital CHECK (capital_action_allowed=false),
    CONSTRAINT chk_model_escalation_no_execution CHECK (live_execution_allowed=false)
);

INSERT INTO agent.agent_model_assignments (
    agent_name, primary_route, fallback_route, escalation_route,
    context_policy, cost_policy, max_autonomous_cost_tier,
    escalation_triggers, notes
)
SELECT
    profile.agent_name,
    profile.default_model_route,
    CASE
        WHEN route.default_provider='local_python' THEN 'agent_worker_deterministic'
        WHEN profile.default_model_route IN ('always_on_daily_driver','daily_brief','jarvis_intake','jarvis_runtime','news_curation','news_event_triage','obsidian_retrieval_summary','research_company_analysis','strategy_intake','trade_journal_learning') THEN NULL
        ELSE 'always_on_daily_driver'
    END,
    CASE WHEN profile.department IN ('automation','data','runtime') THEN 'coding_escalation' ELSE 'frontier_investment_review' END,
    'Retrieve only role-scoped evidence. Apply privacy classification before model context and retain source lineage.',
    'local_first_cloud_by_approval',
    CASE WHEN route.max_cost_tier IN ('local','local_plus') THEN route.max_cost_tier ELSE 'local' END,
    ARRAY['primary model unavailable','context exceeds local limit','independent high-stakes review required']::TEXT[],
    'Generated from the active role profile to close missing runtime assignment coverage; no model call or authority is created.'
FROM agent.profiles profile
JOIN agent.model_routes route ON route.route_name=profile.default_model_route
LEFT JOIN agent.agent_model_assignments assignment ON assignment.agent_name=profile.agent_name
WHERE profile.status='active' AND assignment.agent_name IS NULL;

INSERT INTO agent.model_cost_caps (
    agent_name, daily_cap_usd, monthly_cap_usd, max_cost_tier,
    cloud_requires_approval, autonomous_cloud_allowed, hard_stop_on_breach,
    alert_threshold_pct, notes, evidence, updated_by
)
SELECT profile.agent_name, 0, 0, 'local', true, false, true, 80,
       'Zero autonomous cloud budget. Any future cloud call requires a separate approved escalation and configured cost cap.',
       jsonb_build_array(jsonb_build_object('source','agent.profiles','default_model_route',profile.default_model_route)),
       'AI Runtime Engineer'
FROM agent.profiles profile
LEFT JOIN agent.model_cost_caps cap ON cap.agent_name=profile.agent_name
WHERE profile.status='active' AND cap.agent_name IS NULL;

CREATE OR REPLACE VIEW agent.v_model_route_runtime_control AS
WITH assignment_counts AS (
    SELECT primary_route AS route_name, count(*) AS primary_agent_count
    FROM agent.agent_model_assignments
    GROUP BY primary_route
), endpoint AS (
    SELECT DISTINCT ON (route_name)
           route_name, endpoint_key, endpoint_type, status AS endpoint_status,
           health_status, last_checked_at, last_latency_ms, last_error,
           requires_api_key, secret_ref
    FROM agent.model_endpoints
    ORDER BY route_name, updated_at DESC, id DESC
)
SELECT route.route_name, route.task_class, route.default_provider, route.default_model,
       route.escalation_provider, route.escalation_model, route.max_cost_tier,
       route.enabled, route.notes, coalesce(assignments.primary_agent_count,0) AS primary_agent_count,
       endpoint.endpoint_key, endpoint.endpoint_type, endpoint.endpoint_status,
       endpoint.health_status, endpoint.last_checked_at, endpoint.last_latency_ms,
       endpoint.last_error, endpoint.requires_api_key,
       CASE WHEN endpoint.requires_api_key THEN endpoint.secret_ref IS NOT NULL ELSE true END AS credential_ready,
       CASE
           WHEN NOT route.enabled THEN 'disabled'
           WHEN route.default_provider IN ('local_python','deterministic','local_tools') THEN 'ready'
           WHEN endpoint.endpoint_key IS NULL THEN 'endpoint_missing'
           WHEN endpoint.health_status IN ('configured','healthy','ready','active') THEN 'ready'
           WHEN endpoint.health_status='model_unavailable' THEN 'model_unavailable'
           WHEN endpoint.health_status='needs_secret' THEN 'blocked_secret'
           ELSE 'degraded'
       END AS runtime_status,
       CASE
           WHEN route.default_provider IN ('local_python','deterministic','local_tools') THEN 'Use deterministic local tool route.'
           WHEN endpoint.health_status='model_unavailable' THEN 'Use the agent fallback route or install this model after quality/capacity review.'
           WHEN endpoint.health_status='needs_secret' THEN 'Keep blocked until a secret reference and explicit approval exist.'
           WHEN endpoint.health_status IN ('configured','healthy','ready','active') THEN 'Ready subject to privacy, cost, and task assignment gates.'
           ELSE 'Run endpoint readiness check and inspect evidence.'
       END AS next_required_action
FROM agent.model_routes route
LEFT JOIN assignment_counts assignments ON assignments.route_name=route.route_name
LEFT JOIN endpoint ON endpoint.route_name=route.route_name;

CREATE OR REPLACE VIEW agent.v_model_call_control AS
SELECT decision.*, profile.display_title, profile.department,
       escalation.id AS escalation_id, escalation.status AS escalation_status,
       escalation.privacy_review_status, escalation.cost_review_status
FROM agent.model_call_decisions decision
JOIN agent.profiles profile ON profile.agent_name=decision.agent_name
LEFT JOIN agent.model_escalation_requests escalation ON escalation.decision_id=decision.id;

CREATE OR REPLACE VIEW agent.v_model_runtime_control_summary AS
SELECT 'active_agents'::TEXT AS metric, count(*)::TEXT AS value,
       'Role-scoped agents requiring an enforceable model assignment.'::TEXT AS interpretation
FROM agent.profiles WHERE status='active'
UNION ALL
SELECT 'complete_assignments', count(*)::TEXT,
       'Active agents with explicit primary/fallback/escalation and context policy records.'
FROM agent.agent_model_assignments assignment JOIN agent.profiles profile USING(agent_name) WHERE profile.status='active'
UNION ALL
SELECT 'ready_routes', count(*) FILTER (WHERE runtime_status='ready')::TEXT,
       'Routes currently usable before privacy, cost, and task-specific checks.'
FROM agent.v_model_route_runtime_control
UNION ALL
SELECT 'unavailable_routes', count(*) FILTER (WHERE runtime_status IN ('model_unavailable','endpoint_missing'))::TEXT,
       'Routes needing an installed model or registered endpoint.'
FROM agent.v_model_route_runtime_control
UNION ALL
SELECT 'pending_escalations', count(*) FILTER (WHERE status='pending')::TEXT,
       'Cloud or higher-cost requests awaiting privacy, cost, and human approval.'
FROM agent.model_escalation_requests
UNION ALL
SELECT 'cache_entries', count(*) FILTER (WHERE expires_at>now())::TEXT,
       'Non-private deterministic response entries still within retention.'
FROM agent.model_response_cache
UNION ALL
SELECT 'autonomous_cloud_agents', count(*) FILTER (WHERE autonomous_cloud_allowed)::TEXT,
       'Must remain zero; every cloud or higher-cost route requires human approval.'
FROM agent.v_agent_model_cost_cap_status;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
    ('ai_os_model_runtime_control', 'mcp_tool', 'AI Runtime Engineer', 'read_only', true,
     'Read route readiness, all-agent assignment coverage, privacy policy, cost caps, call decisions, cache status, and escalation queue.',
     '{"reads":["agent.v_model_route_runtime_control","agent.v_model_call_control","agent.model_privacy_policies","agent.v_agent_model_cost_cap_status"],"raw_prompt_exposed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type, owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level, enabled=EXCLUDED.enabled,
    description=EXCLUDED.description, config=EXCLUDED.config;
