INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_execute_tradingview_chart_action',
        'mcp_tool',
        'Trading Desk Agent',
        'browser_capture',
        true,
        'Open a TradingView chart through local CDP, capture a screenshot artifact, and update the TradingView task. This does not place trades.',
        '{"api_route":"/api/tradingview/chart-actions","script":"_ai_os_runtime/scripts/execute_tradingview_chart_action.mjs","writes":["ops.tradingview_tasks","ops.browser_runs","core.raw_artifacts","agent.mcp_audit_log"],"reads":["http://127.0.0.1:9222/json/list","TradingView Desktop page"],"execution_allowed":false,"broker_order_allowed":false,"requires_local_cdp":true}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.mcp_integration_registry
SET
    status = 'active_local',
    config = config || '{
        "chart_action_executor": "_ai_os_runtime/scripts/execute_tradingview_chart_action.mjs",
        "api_route": "/api/tradingview/chart-actions",
        "artifact_type": "tradingview_chart_screenshot",
        "broker_order_allowed": false,
        "current_capabilities": ["open_chart_capture", "task_update", "screenshot_artifact", "browser_run_evidence"]
    }'::jsonb,
    risk_notes = 'Preferred desktop controller for the user own TradingView Desktop workspace. Current production executor supports opening chart URLs through localhost CDP and capturing screenshot evidence. Broker execution remains disabled. Complex pane layout edits, alert creation/deletion, replay trading, and raw UI evaluation still require separate human-gated tools.',
    updated_at = now()
WHERE integration_key = 'tradingview_desktop_mcp_candidate';

UPDATE core.data_source_registry
SET metadata = coalesce(metadata, '{}'::jsonb) || '{
        "chart_action_executor": "_ai_os_runtime/scripts/execute_tradingview_chart_action.mjs",
        "chart_action_api": "/api/tradingview/chart-actions",
        "screenshot_artifacts": true,
        "broker_execution_allowed": false
    }'::jsonb,
    updated_at = now()
WHERE source_key = 'tradingview_mcp';

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'ops.tradingview_tasks',
            'ops.browser_runs',
            'core.raw_artifacts',
            'agent.mcp_audit_log'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_execute_tradingview_chart_action'
        ]::TEXT[]) AS tool
    ),
    next_action = 'TradingView chart-action execution is available for open-chart screenshot capture; next build multi-pane layouts, option straddle templates, and alert-management gates.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'data_sources');
