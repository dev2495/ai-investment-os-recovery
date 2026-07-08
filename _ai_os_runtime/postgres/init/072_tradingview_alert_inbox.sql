CREATE OR REPLACE VIEW ops.v_tradingview_alert_requests AS
WITH alert_approvals AS (
    SELECT
        approval.id AS approval_id,
        approval.status AS approval_status,
        approval.owner_agent AS approval_owner_agent,
        approval.risk_level,
        approval.title AS approval_title,
        approval.requested_action,
        approval.rationale,
        approval.decided_by,
        approval.decided_at,
        approval.created_at AS approval_created_at,
        CASE
            WHEN (approval.requested_action->>'tradingview_task_id') ~ '^[0-9]+$'
            THEN (approval.requested_action->>'tradingview_task_id')::BIGINT
            ELSE NULL
        END AS linked_tradingview_task_id
    FROM agent.approvals approval
    WHERE approval.approval_type = 'tradingview_template_action'
      AND approval.requested_action->>'template_key' = 'create_alert_request'
)
SELECT
    approval.approval_id,
    coalesce(task.id, approval.linked_tradingview_task_id) AS tradingview_task_id,
    approval.approval_status,
    task.status AS task_status,
    approval.risk_level,
    approval.approval_title,
    approval.approval_owner_agent,
    coalesce(task.symbols, ARRAY(
        SELECT jsonb_array_elements_text(coalesce(approval.requested_action->'symbols', '[]'::jsonb))
    )) AS symbols,
    coalesce(task.symbols[1], approval.requested_action->'symbols'->>0) AS symbol,
    coalesce(task.exchange, approval.requested_action->>'exchange') AS exchange,
    coalesce(task.timeframe, approval.requested_action->>'timeframe') AS timeframe,
    coalesce(task.chart_layout, approval.requested_action->>'chart_layout') AS chart_layout,
    coalesce(task.instruction, approval.requested_action->>'instruction') AS instruction,
    approval.requested_action->'metadata'->>'condition' AS alert_condition,
    coalesce((approval.requested_action->>'auto_create_alert')::BOOLEAN, false) AS auto_create_alert,
    approval.rationale,
    approval.requested_action,
    task.evidence AS task_evidence,
    task.result_summary,
    task.created_at AS task_created_at,
    approval.approval_created_at,
    approval.decided_by,
    approval.decided_at,
    CASE
        WHEN approval.approval_status = 'pending' THEN 'awaiting_human_decision'
        WHEN approval.approval_status = 'approved' THEN 'approved_for_manual_creation'
        WHEN approval.approval_status = 'rejected' THEN 'rejected'
        ELSE approval.approval_status
    END AS alert_request_state
FROM alert_approvals approval
LEFT JOIN LATERAL (
    SELECT task.*
    FROM ops.tradingview_tasks task
    WHERE task.task_type = 'template_request'
      AND task.metadata->>'template_key' = 'create_alert_request'
      AND (
        task.id = approval.linked_tradingview_task_id
        OR (
            approval.linked_tradingview_task_id IS NULL
            AND task.requested_by = approval.requested_action->>'actor'
            AND task.created_at BETWEEN approval.approval_created_at - interval '5 seconds'
                                AND approval.approval_created_at + interval '5 seconds'
        )
      )
    ORDER BY
        CASE WHEN task.id = approval.linked_tradingview_task_id THEN 0 ELSE 1 END,
        abs(extract(epoch FROM (task.created_at - approval.approval_created_at)))
    LIMIT 1
) task ON true
ORDER BY
    CASE approval.approval_status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 ELSE 4 END,
    approval.approval_created_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_resolve_tradingview_alert_request',
        'api_tool',
        'Risk Agent',
        'write_with_approval',
        true,
        'Approve or reject a gated TradingView alert request and sync the linked TradingView task. This does not create an alert automatically.',
        '{"api_route":"/api/tradingview/alert-requests/resolve","writes":["agent.approvals","ops.tradingview_tasks"],"reads":["ops.v_tradingview_alert_requests"],"auto_create_alert":false}'::jsonb
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
            'ops.v_tradingview_alert_requests'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_resolve_tradingview_alert_request'
        ]::TEXT[]) AS tool
    ),
    next_action = 'TradingView alert request inbox is available; next build manual alert creation evidence capture and alert lifecycle tracking.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'approval_center');
