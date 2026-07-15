BEGIN;

WITH resolved_catalog AS (
    SELECT
        assignment.agent_name,
        catalog.model_key
    FROM agent.agent_model_assignments assignment
    JOIN agent.model_routes route
      ON route.route_name = assignment.primary_route
    JOIN agent.model_catalog catalog
      ON lower(catalog.provider) = lower(route.default_provider)
     AND catalog.model_name = route.default_model
    WHERE assignment.primary_model_key IS NULL
), unique_resolution AS (
    SELECT agent_name, min(model_key) AS model_key
    FROM resolved_catalog
    GROUP BY agent_name
    HAVING count(*) = 1
)
UPDATE agent.agent_model_assignments assignment
SET primary_model_key = resolution.model_key,
    notes = concat_ws(' ', nullif(assignment.notes, ''),
        'Primary model catalog key synchronized from the governed route contract.'),
    updated_at = now()
FROM unique_resolution resolution
WHERE assignment.agent_name = resolution.agent_name
  AND assignment.primary_model_key IS NULL;

CREATE OR REPLACE VIEW agent.v_agent_model_assignment_completeness AS
SELECT
    count(*)::bigint AS active_agents,
    count(*) FILTER (WHERE matrix.primary_route IS NOT NULL)::bigint AS routed_agents,
    count(*) FILTER (WHERE matrix.model_key IS NOT NULL)::bigint AS explicitly_assigned_agents,
    count(*) FILTER (WHERE matrix.model_status = 'installed_local')::bigint AS installed_local_assignments,
    count(*) FILTER (WHERE matrix.model_status IN ('planned_or_optional', 'available_on_request'))::bigint AS gated_or_optional_assignments,
    count(*) FILTER (WHERE matrix.primary_route IS NULL OR matrix.model_key IS NULL)::bigint AS incomplete_assignments,
    count(*) FILTER (
        WHERE matrix.model_status IN ('planned_or_optional', 'available_on_request')
          AND matrix.fallback_route IS NOT NULL
    )::bigint AS gated_assignments_with_fallback
FROM agent.v_agent_model_matrix matrix;

CREATE OR REPLACE VIEW agent.v_model_runtime_control_summary AS
SELECT 'active_agents'::text AS metric,
       count(*)::text AS value,
       'Role-scoped agents requiring an enforceable model assignment.'::text AS interpretation
FROM agent.profiles WHERE status = 'active'
UNION ALL
SELECT 'complete_assignments', count(*)::text,
       'Active agents with explicit primary/fallback/escalation and context policy records.'
FROM agent.agent_model_assignments assignment
JOIN agent.profiles profile USING (agent_name)
WHERE profile.status = 'active'
UNION ALL
SELECT 'explicit_model_assignments', explicitly_assigned_agents::text,
       'Active agents whose primary route resolves to an explicit model-catalog key.'
FROM agent.v_agent_model_assignment_completeness
UNION ALL
SELECT 'incomplete_model_assignments', incomplete_assignments::text,
       'Must remain zero; active agents missing a route or explicit model-catalog key.'
FROM agent.v_agent_model_assignment_completeness
UNION ALL
SELECT 'ready_routes', count(*) FILTER (WHERE runtime_status = 'ready')::text,
       'Routes currently usable before privacy, cost, and task-specific checks.'
FROM agent.v_model_route_runtime_control
UNION ALL
SELECT 'unavailable_routes', count(*) FILTER (WHERE runtime_status IN ('model_unavailable','endpoint_missing'))::text,
       'Routes needing an installed model or registered endpoint.'
FROM agent.v_model_route_runtime_control
UNION ALL
SELECT 'pending_escalations', count(*) FILTER (WHERE status = 'pending')::text,
       'Cloud or higher-cost requests awaiting privacy, cost, and human approval.'
FROM agent.model_escalation_requests
UNION ALL
SELECT 'cache_entries', count(*) FILTER (WHERE expires_at > now())::text,
       'Non-private deterministic response entries still within retention.'
FROM agent.model_response_cache
UNION ALL
SELECT 'autonomous_cloud_agents', count(*) FILTER (WHERE autonomous_cloud_allowed)::text,
       'Must remain zero; every cloud or higher-cost route requires human approval.'
FROM agent.v_agent_model_cost_cap_status;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled,
    description, config
)
VALUES (
    'ai_os_agent_model_assignment_completeness', 'mcp_tool',
    'AI Runtime Engineer', 'read_only', true,
    'Read active-agent route and explicit model-catalog assignment completeness without exposing credentials.',
    '{"reads":["agent.v_agent_model_assignment_completeness","agent.v_agent_model_matrix"],"raw_secrets_allowed":false,"autonomous_cloud_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

COMMIT;
