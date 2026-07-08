INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_run_ohlcv_aggregation',
        'daemon_market_data_job',
        'Data Steward',
        'write_db_scheduled',
        true,
        'Aggregates real imported ticks into 1d, 1h, 15m, and 5m OHLCV bars and records source health.',
        '{"script":"_ai_os_runtime/scripts/aggregate_ticks_to_ohlcv.py","writes":["trading.ohlcv","core.data_source_checks","core.data_source_registry"],"reads":["trading.ticks","trading.symbols"],"default_interval_seconds":300,"seed_data_allowed":false,"execution_allowed":true}'::jsonb
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
    freshness_target_minutes = 5,
    notes = 'Aggregates real imported ticks into 1d, 1h, 15m, and 5m bars for strategy research and alerts. The AI OS daemon runs it every 300 seconds. No seed or synthetic market data.',
    metadata = coalesce(metadata, '{}'::jsonb) || '{"seed_data":false,"source_table":"trading.ticks","target_table":"trading.ohlcv","daemon_interval_seconds":300}'::jsonb,
    updated_at = now()
WHERE source_key = 'tick_ohlcv_aggregation';

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'trading.ticks',
            'trading.ohlcv',
            'core.data_source_checks',
            'core.v_latest_data_source_freshness'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_run_ohlcv_aggregation',
            'ai_os_check_source_freshness'
        ]::TEXT[]) AS tool
    ),
    next_action = 'OHLCV aggregation is daemon-backed; next add broader live tick ingestion and per-strategy data readiness gates.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'data_sources', 'strategy_lab');
