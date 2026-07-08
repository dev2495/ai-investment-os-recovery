INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_check_tradingview_cdp',
        'daemon_health_check',
        'Automation Engineer',
        'write_db_scheduled',
        true,
        'Checks the local TradingView Desktop CDP endpoint on 127.0.0.1:9222 and records a data-source health row.',
        '{"script":"_ai_os_runtime/scripts/check_tradingview_cdp.py","writes":["core.data_source_checks","core.data_source_registry"],"reads":["http://127.0.0.1:9222/json/version"],"default_interval_seconds":60,"execution_allowed":true}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.data_source_registry
SET status = 'active',
    freshness_target_minutes = 1,
    notes = 'TradingView Desktop controller is checked by the AI OS daemon through local CDP on 127.0.0.1:9222. Relaunch TradingView with --remote-debugging-port=9222 when unavailable. No broker execution is allowed from this connector.',
    metadata = coalesce(metadata, '{}'::jsonb) || '{"execution_allowed":false,"cdp_endpoint":"http://127.0.0.1:9222/json/version","daemon_heartbeat_seconds":60,"relaunch_command":"open -na /Applications/TradingView.app --args --remote-debugging-port=9222"}'::jsonb,
    updated_at = now()
WHERE source_key = 'tradingview_mcp';

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'core.data_source_checks',
            'core.v_recent_data_source_checks',
            'core.v_latest_data_source_freshness'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_check_tradingview_cdp',
            'ai_os_create_tradingview_task',
            'ai_os_update_tradingview_task',
            'ai_os_tradingview_tasks'
        ]::TEXT[]) AS tool
    ),
    next_action = 'TradingView CDP heartbeat is daemon-backed; next build chart-action execution and artifact capture on top of the live endpoint.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'data_sources');
