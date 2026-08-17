BEGIN;

UPDATE agent.tool_registry
SET enabled = false,
    permission_level = 'retired',
    description = 'Retired: TradingView uses the user-managed native Desktop application only.',
    config = coalesce(config, '{}'::jsonb) || jsonb_build_object(
        'execution_allowed', false,
        'managed_browser_allowed', false,
        'cdp_allowed', false,
        'retired_reason', 'native_tradingview_desktop_only'
    )
WHERE tool_name IN ('ai_os_check_tradingview_cdp', 'ai_os_execute_tradingview_chart_action');

UPDATE core.mcp_integration_registry
SET status = 'retired',
    config = (coalesce(config, '{}'::jsonb) - 'chart_action_executor' - 'api_route' - 'artifact_type' - 'current_capabilities') || jsonb_build_object(
        'backend', 'native_desktop',
        'managed_browser_allowed', false,
        'cdp_allowed', false,
        'authoritative_market_data', false,
        'broker_order_allowed', false
    ),
    risk_notes = 'Native TradingView Desktop handoff only; no managed browser, CDP, screenshot extraction, market-data authority, or broker execution.',
    updated_at = now()
WHERE integration_key IN ('tradingview_data_mcp_candidate', 'tradingview_desktop_mcp_candidate');

UPDATE core.data_source_registry
SET status = 'retired',
    notes = 'Retired as a data source. TradingView Desktop is a user-managed chart workspace only; canonical prices come from the warehouse and broker feeds.',
    metadata = (coalesce(metadata, '{}'::jsonb) - 'chart_action_executor' - 'chart_action_api' - 'screenshot_artifacts' - 'cdp_endpoint' - 'relaunch_command') || jsonb_build_object(
        'authoritative_market_data', false,
        'managed_browser_allowed', false,
        'cdp_allowed', false,
        'execution_allowed', false,
        'broker_order_allowed', false
    ),
    updated_at = now()
WHERE source_key = 'tradingview_mcp';

UPDATE core.control_plane_modules
SET mcp_tools = array_remove(array_remove(mcp_tools, 'ai_os_check_tradingview_cdp'), 'ai_os_execute_tradingview_chart_action'),
    next_action = 'Use native TradingView Desktop handoff for charts; use canonical warehouse and broker feeds for calculations, risk, and execution.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'data_sources');

COMMIT;
