ALTER TABLE agent.agent_messages
    ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS generated_task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS generated_inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS error_message TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_messages_processing_status
    ON agent.agent_messages(processing_status, created_at);

CREATE INDEX IF NOT EXISTS idx_agent_messages_generated_task
    ON agent.agent_messages(generated_task_id);

CREATE OR REPLACE VIEW agent.v_agent_message_threads AS
SELECT
    msg.id,
    msg.thread_key,
    msg.from_agent,
    fp.display_title AS from_title,
    msg.to_agent,
    tp.display_title AS to_title,
    msg.subject,
    msg.body,
    msg.priority,
    msg.status,
    msg.related_task_id,
    msg.related_skill_key,
    msg.metadata,
    msg.created_at,
    msg.read_at,
    msg.processing_status,
    msg.processed_at,
    msg.generated_task_id,
    msg.generated_inbox_id,
    msg.error_message
FROM agent.agent_messages msg
LEFT JOIN agent.profiles fp ON fp.agent_name = msg.from_agent
LEFT JOIN agent.profiles tp ON tp.agent_name = msg.to_agent
ORDER BY msg.created_at DESC;

CREATE OR REPLACE VIEW agent.v_live_agent_worker_queue AS
WITH dashboard_jobs AS (
    SELECT
        j.task_id,
        j.title,
        j.objective,
        j.owner_agent,
        j.status AS task_status,
        j.priority,
        j.source_kind,
        j.source_ref,
        j.output_note_path,
        j.widget_id,
        j.widget_key,
        j.widget_title,
        j.workspace,
        j.widget_type,
        CASE
            WHEN j.widget_key = 'portfolio_latest_positions' THEN 'portfolio_snapshot_review'
            WHEN j.widget_key = 'market_signal_monitor' THEN 'monitor_strategy_alerts'
            WHEN j.widget_key = 'strategy_lab_queue' THEN 'strategy_lab_review'
            WHEN j.widget_key = 'research_filings_inbox' THEN 'analyze_corporate_filing'
            WHEN j.widget_key = 'model_runtime_status' THEN 'model_runtime_check'
            WHEN j.widget_key = 'command_daily_brief' THEN 'daily_office_brief'
            ELSE 'refresh_dashboard_widget'
        END AS suggested_skill_key,
        j.inbox_item_id,
        j.inbox_status,
        j.created_at,
        j.updated_at
    FROM agent.v_dashboard_agent_jobs j
),
message_jobs AS (
    SELECT
        t.id AS task_id,
        t.title,
        t.objective,
        t.owner_agent,
        t.status AS task_status,
        t.priority,
        t.source_kind,
        t.source_ref,
        t.output_note_path,
        NULL::BIGINT AS widget_id,
        NULL::TEXT AS widget_key,
        'Agent Mailbox'::TEXT AS widget_title,
        coalesce(lower(nullif(p.department, '')), 'command') AS workspace,
        'agent_message'::TEXT AS widget_type,
        coalesce(msg.related_skill_key, msg.metadata ->> 'skill_key', 'route_user_request') AS suggested_skill_key,
        inbox.id AS inbox_item_id,
        inbox.status AS inbox_status,
        t.created_at,
        t.updated_at
    FROM agent.tasks t
    LEFT JOIN agent.agent_messages msg ON msg.generated_task_id = t.id
    LEFT JOIN agent.inbox_items inbox ON inbox.task_id = t.id
    LEFT JOIN agent.profiles p ON p.agent_name = t.owner_agent
    WHERE t.source_kind = 'agent_message'
),
queued AS (
    SELECT * FROM dashboard_jobs
    UNION ALL
    SELECT * FROM message_jobs
)
SELECT
    q.task_id,
    q.title,
    q.objective,
    q.owner_agent,
    q.task_status,
    q.priority,
    q.source_kind,
    q.source_ref,
    q.output_note_path,
    q.widget_id,
    q.widget_key,
    q.widget_title,
    q.workspace,
    q.widget_type,
    q.suggested_skill_key,
    s.skill_name AS suggested_skill_name,
    s.skill_family AS suggested_skill_family,
    s.execution_mode AS suggested_execution_mode,
    last_run.id AS latest_worker_run_id,
    last_run.status AS latest_worker_status,
    last_run.finished_at AS latest_worker_finished_at,
    last_run.output_note_path AS latest_output_note_path,
    q.inbox_item_id,
    q.inbox_status,
    q.created_at,
    q.updated_at
FROM queued q
LEFT JOIN agent.skills s ON s.skill_key = q.suggested_skill_key
LEFT JOIN LATERAL (
    SELECT wr.id,
           wr.task_id,
           wr.widget_id,
           wr.agent_name,
           wr.skill_key,
           wr.run_mode,
           wr.status,
           wr.input_snapshot,
           wr.output_summary,
           wr.output_note_path,
           wr.evidence,
           wr.started_at,
           wr.finished_at,
           wr.created_at,
           wr.updated_at
    FROM agent.worker_runs wr
    WHERE wr.task_id = q.task_id
    ORDER BY wr.created_at DESC
    LIMIT 1
) last_run ON true
ORDER BY
    CASE q.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE q.task_status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 WHEN 'completed' THEN 4 ELSE 5 END,
    q.updated_at DESC;

CREATE OR REPLACE VIEW agent.v_message_daemon_backlog AS
SELECT
    msg.id AS message_id,
    msg.thread_key,
    msg.from_agent,
    msg.to_agent,
    msg.subject,
    msg.body,
    msg.priority,
    msg.status,
    msg.processing_status,
    msg.related_skill_key,
    msg.metadata,
    msg.created_at
FROM agent.agent_messages msg
WHERE msg.processing_status IN ('pending', 'failed_retry')
  AND msg.generated_task_id IS NULL
ORDER BY
    CASE msg.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    msg.created_at ASC;
