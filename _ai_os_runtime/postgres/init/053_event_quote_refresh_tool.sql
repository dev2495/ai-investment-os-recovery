INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_refresh_event_quotes',
        'mcp_tool',
        'Data Steward',
        'write_db_manual_only',
        true,
        'Refresh stored TradingView scanner quotes for active special-situation event symbols. No fake prices and no execution.',
        '{"script":"_ai_os_runtime/scripts/refresh_event_quotes.py","writes":["market.price_quotes","core.data_source_checks"],"reads":["research.v_special_situation_memos"],"execution_allowed":false,"seed_data_allowed":false}'::jsonb
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
            'market.price_quotes',
            'market.v_latest_price_quotes',
            'core.data_source_checks'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY['ai_os_refresh_event_quotes']::TEXT[]) AS tool
    ),
    next_action = 'Use event quote refresh before special-situation spread checks; add scheduler after source freshness policy is approved.',
    updated_at = now()
WHERE module_key IN ('research_inbox', 'trading_desk');

UPDATE core.data_source_registry
SET notes = 'Batch mark-to-market quote endpoint for Indian equities and active event symbols. No broker execution.',
    metadata = metadata || '{"event_symbol_refresh":"active","script":"_ai_os_runtime/scripts/refresh_event_quotes.py"}'::jsonb,
    status = 'active'
WHERE source_key = 'tradingview_scanner_quotes';
