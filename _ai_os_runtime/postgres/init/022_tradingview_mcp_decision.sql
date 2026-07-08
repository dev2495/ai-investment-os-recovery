UPDATE core.mcp_integration_registry
SET
    install_mode = 'self_host_or_pypi',
    status = 'approved_candidate',
    trust_level = 'reviewed_open_source',
    permission_level = 'market_data_read',
    risk_notes = 'Preferred data connector for screeners, technical analysis, Yahoo-backed prices/options, and backtests. It does not log into or automate the user TradingView account. Validate upstream data terms and never treat outputs as trade execution authority.',
    evidence_refs = ARRAY[
        'https://github.com/atilaahmettaner/tradingview-mcp',
        '_ai_os_runtime/external_components/mcp_candidates/atilaahmettaner-tradingview-mcp',
        'local_review_commit:121d22e'
    ],
    config = config || '{
        "decision": "preferred_tradingview_data_connector",
        "local_clone": "_ai_os_runtime/external_components/mcp_candidates/atilaahmettaner-tradingview-mcp",
        "review_commit": "121d22e",
        "tool_count_seen": 34,
        "account_login_required": false,
        "execution_allowed": false
    }'::jsonb,
    updated_at = now()
WHERE integration_key = 'tradingview_data_mcp_candidate';

UPDATE core.mcp_integration_registry
SET
    install_mode = 'local_cdp_mcp',
    status = 'approved_candidate',
    trust_level = 'reviewed_gated_component',
    permission_level = 'browser_desktop_control_gated',
    risk_notes = 'Preferred desktop controller for the user own TradingView Desktop workspace: panes, symbols, screenshots, Pine compile, chart reading, and local chart workflow automation. Must run only on localhost CDP port 9222. Do not expose CDP to network. Keep broker execution disabled. Use human approval for alert creation/deletion, replay_trade, raw ui_evaluate, and any destructive chart state change.',
    evidence_refs = ARRAY[
        'https://github.com/tradesdontlie/tradingview-mcp',
        '_ai_os_runtime/external_components/mcp_candidates/tradesdontlie-tradingview-mcp',
        'local_review_commit:4795784',
        'TradingView Desktop visible via Computer Use on 2026-07-02; CDP port 9222 was not listening'
    ],
    config = config || '{
        "decision": "preferred_tradingview_desktop_controller",
        "local_clone": "_ai_os_runtime/external_components/mcp_candidates/tradesdontlie-tradingview-mcp",
        "review_commit": "4795784",
        "tool_count_seen": 78,
        "cdp_host": "127.0.0.1",
        "cdp_port": 9222,
        "execution_allowed": false,
        "requires_human_gate_for": ["alert_create", "alert_delete", "replay_trade", "ui_evaluate", "draw_clear", "tab_close"]
    }'::jsonb,
    updated_at = now()
WHERE integration_key = 'tradingview_desktop_mcp_candidate';

UPDATE core.mcp_integration_registry
SET
    status = 'reference_only',
    trust_level = 'proprietary_reference',
    permission_level = 'none_reference',
    risk_notes = 'Not selected for install. The reviewed package declares Proprietary license, stores state under user home, and introduces OpenAI/Anthropic/Supabase configuration. Keep as reference only because the MIT desktop TradingView MCP already covers Pine Script development.',
    evidence_refs = ARRAY[
        'https://github.com/cklose2000/pinescript-mcp-server',
        '_ai_os_runtime/external_components/mcp_candidates/cklose2000-pinescript-mcp-server',
        'local_review_commit:1f62389',
        'package_json_license:Proprietary'
    ],
    config = config || '{
        "decision": "do_not_install_reference_only",
        "local_clone": "_ai_os_runtime/external_components/mcp_candidates/cklose2000-pinescript-mcp-server",
        "review_commit": "1f62389",
        "reason": "proprietary_license_and_extra_cloud_key_surface"
    }'::jsonb,
    updated_at = now()
WHERE integration_key = 'pinescript_mcp_candidate';
