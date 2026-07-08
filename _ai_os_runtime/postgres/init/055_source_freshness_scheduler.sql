CREATE TABLE IF NOT EXISTS core.source_freshness_scheduler_runs (
    id BIGSERIAL PRIMARY KEY,
    job_key TEXT NOT NULL DEFAULT 'source_freshness_monitor',
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    scheduler_interval_seconds INTEGER NOT NULL,
    checked_count INTEGER NOT NULL DEFAULT 0,
    fresh_count INTEGER NOT NULL DEFAULT 0,
    stale_or_error_count INTEGER NOT NULL DEFAULT 0,
    command TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    next_run_after TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'AI OS Agent Daemon',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_freshness_scheduler_job_time
    ON core.source_freshness_scheduler_runs (job_key, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_freshness_scheduler_status
    ON core.source_freshness_scheduler_runs (status);

CREATE OR REPLACE VIEW core.v_source_freshness_scheduler_runs AS
SELECT
    id,
    job_key,
    run_key,
    status,
    scheduler_interval_seconds,
    checked_count,
    fresh_count,
    stale_or_error_count,
    command,
    output_payload,
    error_message,
    started_at,
    finished_at,
    duration_ms,
    next_run_after,
    CASE
        WHEN finished_at IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (now() - finished_at)) / 60
    END AS minutes_since_finished,
    created_by,
    created_at
FROM core.source_freshness_scheduler_runs
ORDER BY started_at DESC, id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_source_freshness_scheduler',
        'daemon_scheduler',
        'Jarvis',
        'write_db_scheduled',
        true,
        'Runs the source freshness monitor on the AI OS daemon cadence and records auditable scheduler runs.',
        '{"daemon":"_ai_os_runtime/scripts/run_agent_message_daemon.py","scheduled_script":"_ai_os_runtime/scripts/check_source_freshness.py","writes":["core.source_freshness_scheduler_runs","core.data_source_freshness_checks","risk.events"],"default_interval_seconds":900,"execution_allowed":true}'::jsonb
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
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'core.source_freshness_scheduler_runs',
            'core.v_source_freshness_scheduler_runs',
            'core.data_source_freshness_checks',
            'risk.events'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_check_source_freshness',
            'ai_os_source_freshness_scheduler'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Source freshness now runs on the AI OS daemon cadence; monitor scheduler runs and stale-source risk events before adding external notifications.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'research_inbox', 'trading_desk', 'runtime');
