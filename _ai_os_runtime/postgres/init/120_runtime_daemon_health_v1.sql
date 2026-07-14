CREATE TABLE IF NOT EXISTS core.runtime_daemon_heartbeats (
    daemon_key TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    host_name TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('starting', 'running', 'degraded', 'stopped')),
    loop_interval_seconds INTEGER NOT NULL CHECK (loop_interval_seconds >= 5),
    enabled_workloads JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_pass_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_error TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runtime_daemon_heartbeat_at
ON core.runtime_daemon_heartbeats (heartbeat_at DESC);

CREATE OR REPLACE VIEW core.v_runtime_daemon_health AS
SELECT
    daemon_key,
    instance_id,
    host_name,
    process_id,
    status AS reported_status,
    CASE
        WHEN heartbeat_at < now() - make_interval(secs => greatest(loop_interval_seconds * 4, 180)) THEN 'stale'
        WHEN status = 'degraded' THEN 'degraded'
        WHEN status = 'stopped' THEN 'stopped'
        ELSE 'healthy'
    END AS health_status,
    loop_interval_seconds,
    enabled_workloads,
    last_pass_summary,
    last_error,
    started_at,
    heartbeat_at,
    EXTRACT(EPOCH FROM (now() - heartbeat_at))::INTEGER AS heartbeat_age_seconds,
    updated_at
FROM core.runtime_daemon_heartbeats
ORDER BY daemon_key;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_runtime_daemon_health',
    'runtime_health',
    'Jarvis',
    'read_only',
    true,
    'Reads persisted heartbeat and workload status for the 24/7 AI OS daemon.',
    '{"reads":["core.v_runtime_daemon_health"],"writer":"scripts/run_agent_message_daemon.py","seed_data_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT object_name
        FROM unnest(warehouse_objects || ARRAY[
            'core.runtime_daemon_heartbeats',
            'core.v_runtime_daemon_health'
        ]::TEXT[]) AS object_name
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool_name
        FROM unnest(mcp_tools || ARRAY['ai_os_runtime_daemon_health']::TEXT[]) AS tool_name
    ),
    next_action = 'Monitor persisted daemon heartbeat age and workload outcomes; alert on stale or degraded health.',
    updated_at = now()
WHERE module_key IN ('runtime', 'agent_office', 'system_health');
