CREATE TABLE IF NOT EXISTS agent.comments (
    id BIGSERIAL PRIMARY KEY,
    target_kind TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    target_title TEXT,
    parent_comment_id BIGINT REFERENCES agent.comments(id) ON DELETE CASCADE,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    comment_type TEXT NOT NULL DEFAULT 'review_note',
    severity TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open',
    body TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'AI Office',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    CONSTRAINT chk_agent_comments_target_kind CHECK (
        target_kind IN (
            'output_artifact',
            'task',
            'approval',
            'agent',
            'message_thread',
            'symbol',
            'strategy',
            'client',
            'committee_review',
            'risk_event',
            'system'
        )
    ),
    CONSTRAINT chk_agent_comments_type CHECK (
        comment_type IN (
            'review_note',
            'question',
            'objection',
            'risk_flag',
            'follow_up',
            'decision_note',
            'source_gap',
            'praise',
            'system_note'
        )
    ),
    CONSTRAINT chk_agent_comments_severity CHECK (
        severity IN ('low', 'normal', 'medium', 'high', 'critical')
    ),
    CONSTRAINT chk_agent_comments_status CHECK (
        status IN ('open', 'acknowledged', 'resolved', 'dismissed')
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_comments_target
    ON agent.comments (target_kind, target_ref, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_comments_from_agent
    ON agent.comments (from_agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_comments_to_agent
    ON agent.comments (to_agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_comments_status
    ON agent.comments (status, severity, created_at DESC);

CREATE OR REPLACE VIEW agent.v_agent_comments AS
WITH target_context AS (
    SELECT
        comment.id,
        CASE
            WHEN comment.target_kind = 'output_artifact' THEN artifact.title
            WHEN comment.target_kind = 'task' THEN task.title
            WHEN comment.target_kind = 'approval' THEN approval.title
            WHEN comment.target_kind = 'agent' THEN profile.display_title
            WHEN comment.target_kind = 'message_thread' THEN thread.subject
            WHEN comment.target_kind = 'strategy' THEN strategy.strategy_name
            ELSE NULL
        END AS resolved_target_title,
        CASE
            WHEN comment.target_kind = 'output_artifact' THEN artifact.owner_agent
            WHEN comment.target_kind = 'task' THEN task.owner_agent
            WHEN comment.target_kind = 'approval' THEN approval.owner_agent
            WHEN comment.target_kind = 'agent' THEN profile.agent_name
            WHEN comment.target_kind = 'message_thread' THEN thread.to_agent
            WHEN comment.target_kind = 'strategy' THEN strategy.owner_agent
            ELSE NULL
        END AS resolved_owner_agent,
        CASE
            WHEN comment.target_kind = 'output_artifact' THEN artifact.artifact_family
            WHEN comment.target_kind = 'task' THEN task.status
            WHEN comment.target_kind = 'approval' THEN approval.status
            WHEN comment.target_kind = 'agent' THEN profile.department
            WHEN comment.target_kind = 'message_thread' THEN thread.status
            WHEN comment.target_kind = 'strategy' THEN strategy.live_mode
            ELSE NULL
        END AS resolved_target_status,
        CASE
            WHEN comment.target_kind = 'output_artifact' THEN artifact.artifact_location
            WHEN comment.target_kind = 'task' THEN task.output_note_path
            WHEN comment.target_kind = 'approval' THEN approval.approval_type
            WHEN comment.target_kind = 'agent' THEN profile.mailbox_address
            WHEN comment.target_kind = 'message_thread' THEN thread.thread_key
            WHEN comment.target_kind = 'strategy' THEN strategy.strategy_key
            ELSE NULL
        END AS resolved_target_location
    FROM agent.comments comment
    LEFT JOIN agent.v_output_artifact_registry_v2 artifact
        ON comment.target_kind = 'output_artifact'
       AND artifact.artifact_key = comment.target_ref
    LEFT JOIN agent.tasks task
        ON comment.target_kind = 'task'
       AND task.id::TEXT = comment.target_ref
    LEFT JOIN agent.approvals approval
        ON comment.target_kind = 'approval'
       AND approval.id::TEXT = comment.target_ref
    LEFT JOIN agent.v_employee_profiles_v1 profile
        ON comment.target_kind = 'agent'
       AND profile.agent_name = comment.target_ref
    LEFT JOIN agent.agent_messages thread
        ON comment.target_kind = 'message_thread'
       AND thread.thread_key = comment.target_ref
    LEFT JOIN strategy.v_strategy_registry strategy
        ON comment.target_kind = 'strategy'
       AND strategy.strategy_key = comment.target_ref
)
SELECT
    comment.id,
    comment.target_kind,
    comment.target_ref,
    coalesce(nullif(comment.target_title, ''), context.resolved_target_title, comment.target_ref) AS target_title,
    context.resolved_owner_agent AS target_owner_agent,
    context.resolved_target_status AS target_status,
    context.resolved_target_location AS target_location,
    comment.parent_comment_id,
    parent.from_agent AS parent_from_agent,
    parent.body AS parent_body,
    comment.from_agent,
    sender.display_title AS from_agent_title,
    sender.department AS from_agent_department,
    comment.to_agent,
    recipient.display_title AS to_agent_title,
    recipient.department AS to_agent_department,
    comment.comment_type,
    comment.severity,
    comment.status,
    comment.body,
    comment.evidence,
    comment.metadata,
    comment.created_by,
    comment.created_at,
    comment.updated_at,
    comment.resolved_by,
    comment.resolved_at,
    CASE
        WHEN comment.status IN ('open', 'acknowledged')
         AND comment.severity IN ('high', 'critical') THEN true
        ELSE false
    END AS needs_attention
FROM agent.comments comment
LEFT JOIN target_context context ON context.id = comment.id
LEFT JOIN agent.comments parent ON parent.id = comment.parent_comment_id
LEFT JOIN agent.profiles sender ON sender.agent_name = comment.from_agent
LEFT JOIN agent.profiles recipient ON recipient.agent_name = comment.to_agent;

CREATE OR REPLACE VIEW agent.v_agent_comment_summary AS
SELECT
    'total_comments'::TEXT AS metric,
    count(*)::TEXT AS value,
    min(created_at) AS first_seen_at,
    max(updated_at) AS latest_seen_at,
    'All agent comments across artifacts, tasks, approvals, agents, strategies, and system targets.'::TEXT AS interpretation
FROM agent.comments
UNION ALL
SELECT
    'open_comments',
    count(*) FILTER (WHERE status IN ('open', 'acknowledged'))::TEXT,
    min(created_at),
    max(updated_at),
    'Comments that still need attention or follow-up.'::TEXT
FROM agent.comments
UNION ALL
SELECT
    'high_priority_comments',
    count(*) FILTER (WHERE status IN ('open', 'acknowledged') AND severity IN ('high', 'critical'))::TEXT,
    min(created_at),
    max(updated_at),
    'Open high/critical comments that should be visible to Charlie and Jarvis.'::TEXT
FROM agent.comments
UNION ALL
SELECT
    'commented_targets',
    count(DISTINCT target_kind || ':' || target_ref)::TEXT,
    min(created_at),
    max(updated_at),
    'Unique targets with at least one comment.'::TEXT
FROM agent.comments
UNION ALL
SELECT
    'output_artifact_comments',
    count(*) FILTER (WHERE target_kind = 'output_artifact')::TEXT,
    min(created_at),
    max(updated_at),
    'Comments attached to generated output artifacts.'::TEXT
FROM agent.comments;

CREATE OR REPLACE VIEW agent.v_agent_comment_target_summary AS
SELECT
    target_kind,
    target_ref,
    target_title,
    target_owner_agent,
    target_status,
    target_location,
    count(*)::BIGINT AS comment_count,
    count(*) FILTER (WHERE status IN ('open', 'acknowledged'))::BIGINT AS open_comment_count,
    count(*) FILTER (WHERE severity IN ('high', 'critical') AND status IN ('open', 'acknowledged'))::BIGINT AS high_priority_open_count,
    max(updated_at) AS latest_comment_at
FROM agent.v_agent_comments
GROUP BY target_kind, target_ref, target_title, target_owner_agent, target_status, target_location;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
    (
        'ai_os_agent_comments',
        'mcp_tool',
        'Jarvis',
        'read_only',
        true,
        'Read agent comments and review annotations across artifacts, tasks, approvals, agents, and strategy targets.',
        '{"reads":["agent.v_agent_comments","agent.v_agent_comment_summary","agent.v_agent_comment_target_summary"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_create_agent_comment',
        'mcp_tool',
        'Jarvis',
        'write_db_manual_only',
        true,
        'Create an auditable comment or review annotation on an AI Office target.',
        '{"writes":["agent.comments","agent.mcp_audit_log"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_resolve_agent_comment',
        'mcp_tool',
        'Jarvis',
        'write_db_manual_only',
        true,
        'Resolve, acknowledge, or dismiss an existing agent comment with audit evidence.',
        '{"writes":["agent.comments","agent.mcp_audit_log"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
