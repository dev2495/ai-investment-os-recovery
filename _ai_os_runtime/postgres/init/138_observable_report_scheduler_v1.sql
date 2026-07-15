BEGIN;

ALTER TABLE ops.report_runs
    ADD COLUMN IF NOT EXISTS scheduled_period_key TEXT,
    ADD COLUMN IF NOT EXISTS trigger_type TEXT NOT NULL DEFAULT 'scheduled';

UPDATE ops.report_runs run
SET scheduled_period_key = CASE schedule.cadence
        WHEN 'daily' THEN left(run.period_key, 10)
        WHEN 'weekly' THEN substring(run.period_key FROM '^[0-9]{4}-W[0-9]{2}')
        WHEN 'monthly' THEN left(run.period_key, 7)
        ELSE run.period_key
    END
FROM ops.report_schedules schedule
WHERE schedule.id = run.schedule_id
  AND run.scheduled_period_key IS NULL;

ALTER TABLE ops.report_runs
    ALTER COLUMN scheduled_period_key SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_report_runs_scheduled_period
    ON ops.report_runs (schedule_id, scheduled_period_key, status, finished_at DESC);

CREATE TABLE IF NOT EXISTS ops.report_scheduler_invocations (
    id BIGSERIAL PRIMARY KEY,
    invocation_key TEXT NOT NULL UNIQUE,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('launchd', 'api', 'operator', 'test')),
    report_key TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    due_count INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_scheduler_invocations_recent
    ON ops.report_scheduler_invocations (started_at DESC);

CREATE OR REPLACE VIEW ops.v_report_schedule_status AS
WITH clock AS (
    SELECT now() AT TIME ZONE 'Asia/Kolkata' AS local_now
)
SELECT
    schedule.id,
    schedule.report_key,
    schedule.report_name,
    schedule.report_family,
    schedule.cadence,
    schedule.owner_agent,
    schedule.skill_key,
    schedule.target_folder,
    schedule.approval_required,
    schedule.enabled,
    schedule.source_views,
    schedule.description,
    schedule.config,
    latest.id AS latest_run_id,
    latest.run_key AS latest_run_key,
    latest.period_key AS latest_period_key,
    latest.status AS latest_status,
    latest.output_note_path AS latest_output_note_path,
    latest.summary AS latest_summary,
    latest.finished_at AS latest_finished_at,
    CASE
        WHEN NOT schedule.enabled OR schedule.cadence = 'manual' THEN false
        WHEN schedule.cadence = 'daily' THEN
            coalesce(completed.scheduled_period_key, '') <> to_char(clock.local_now, 'YYYY-MM-DD')
            AND clock.local_now::time >= coalesce(nullif(schedule.config ->> 'run_after_local', ''), '00:00')::time
        WHEN schedule.cadence = 'weekly' THEN
            coalesce(completed.scheduled_period_key, '') <> to_char(clock.local_now, 'IYYY-"W"IW')
            AND (
                extract(isodow FROM clock.local_now)::integer > coalesce((schedule.config ->> 'weekday')::integer, 1)
                OR (
                    extract(isodow FROM clock.local_now)::integer = coalesce((schedule.config ->> 'weekday')::integer, 1)
                    AND clock.local_now::time >= coalesce(nullif(schedule.config ->> 'run_after_local', ''), '00:00')::time
                )
            )
        WHEN schedule.cadence = 'monthly' THEN
            coalesce(completed.scheduled_period_key, '') <> to_char(clock.local_now, 'YYYY-MM')
            AND (
                extract(day FROM clock.local_now)::integer > coalesce((schedule.config ->> 'month_day')::integer, 1)
                OR (
                    extract(day FROM clock.local_now)::integer = coalesce((schedule.config ->> 'month_day')::integer, 1)
                    AND clock.local_now::time >= coalesce(nullif(schedule.config ->> 'run_after_local', ''), '00:00')::time
                )
            )
        ELSE false
    END AS due_now,
    schedule.updated_at,
    completed.scheduled_period_key AS latest_completed_period_key,
    latest.trigger_type AS latest_trigger_type,
    CASE
        WHEN NOT schedule.enabled THEN 'disabled'
        WHEN schedule.cadence = 'manual' THEN 'manual_only'
        WHEN completed.scheduled_period_key IS NULL THEN 'no_completed_run'
        WHEN schedule.cadence = 'daily' AND completed.scheduled_period_key = to_char(clock.local_now, 'YYYY-MM-DD') THEN 'current'
        WHEN schedule.cadence = 'weekly' AND completed.scheduled_period_key = to_char(clock.local_now, 'IYYY-"W"IW') THEN 'current'
        WHEN schedule.cadence = 'monthly' AND completed.scheduled_period_key = to_char(clock.local_now, 'YYYY-MM') THEN 'current'
        ELSE 'awaiting_cadence_or_overdue'
    END AS due_reason
FROM ops.report_schedules schedule
CROSS JOIN clock
LEFT JOIN LATERAL (
    SELECT run.*
    FROM ops.report_runs run
    WHERE run.schedule_id = schedule.id
    ORDER BY run.created_at DESC
    LIMIT 1
) latest ON true
LEFT JOIN LATERAL (
    SELECT run.scheduled_period_key
    FROM ops.report_runs run
    WHERE run.schedule_id = schedule.id AND run.status = 'completed'
    ORDER BY run.finished_at DESC NULLS LAST, run.id DESC
    LIMIT 1
) completed ON true;

CREATE OR REPLACE VIEW ops.v_recent_report_runs AS
SELECT
    run.id,
    run.run_key,
    run.period_key,
    schedule.report_key,
    schedule.report_name,
    schedule.report_family,
    schedule.cadence,
    schedule.owner_agent,
    schedule.approval_required,
    run.status,
    run.task_id,
    run.worker_run_id,
    run.output_note_path,
    run.summary,
    run.source_snapshot,
    run.evidence,
    run.error_message,
    run.started_at,
    run.finished_at,
    run.updated_at,
    run.scheduled_period_key,
    run.trigger_type
FROM ops.report_runs run
JOIN ops.report_schedules schedule ON schedule.id = run.schedule_id
ORDER BY run.created_at DESC;

CREATE OR REPLACE VIEW ops.v_report_scheduler_health AS
SELECT
    count(*) FILTER (WHERE schedule.enabled) AS enabled_schedules,
    count(*) FILTER (WHERE schedule.enabled AND schedule.due_now) AS due_schedules,
    latest.id AS latest_invocation_id,
    latest.invocation_key AS latest_invocation_key,
    latest.trigger_type AS latest_trigger_type,
    latest.status AS latest_status,
    latest.due_count AS latest_due_count,
    latest.completed_count AS latest_completed_count,
    latest.failed_count AS latest_failed_count,
    latest.error_message AS latest_error_message,
    latest.started_at AS latest_started_at,
    latest.finished_at AS latest_finished_at,
    launchd.status AS latest_launchd_status,
    launchd.failed_count AS latest_launchd_failed_count,
    launchd.error_message AS latest_launchd_error_message,
    launchd.started_at AS latest_launchd_started_at,
    launchd.finished_at AS latest_launchd_finished_at
FROM ops.v_report_schedule_status schedule
LEFT JOIN LATERAL (
    SELECT invocation.*
    FROM ops.report_scheduler_invocations invocation
    ORDER BY invocation.started_at DESC
    LIMIT 1
) latest ON true
LEFT JOIN LATERAL (
    SELECT invocation.*
    FROM ops.report_scheduler_invocations invocation
    WHERE invocation.trigger_type = 'launchd'
    ORDER BY invocation.started_at DESC
    LIMIT 1
) launchd ON true
GROUP BY latest.id, latest.invocation_key, latest.trigger_type, latest.status,
         latest.due_count, latest.completed_count, latest.failed_count,
         latest.error_message, latest.started_at, latest.finished_at,
         launchd.status, launchd.failed_count, launchd.error_message,
         launchd.started_at, launchd.finished_at;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'ai_os_report_scheduler_status', 'mcp_read', 'Jarvis', 'read_db', true,
        'Read report cadence, due state, launchd proof, invocation history, and failures.',
        '{"views":["ops.v_report_schedule_status","ops.v_report_scheduler_health"],"execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_run_scheduled_reports', 'mcp_write', 'Jarvis', 'write_reports', true,
        'Run due reports or force one named report through the audited API without external delivery authority.',
        '{"api_route":"/api/reports/run","external_send_allowed":false,"capital_action_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

COMMIT;
