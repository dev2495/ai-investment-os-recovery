CREATE TABLE IF NOT EXISTS ops.tradingview_action_templates (
    template_key TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    category TEXT NOT NULL,
    action_kind TEXT NOT NULL,
    default_exchange TEXT NOT NULL DEFAULT 'NSE',
    default_timeframe TEXT NOT NULL DEFAULT 'D',
    default_chart_layout TEXT,
    requires_symbol BOOLEAN NOT NULL DEFAULT true,
    approval_required BOOLEAN NOT NULL DEFAULT false,
    execution_mode TEXT NOT NULL DEFAULT 'cdp_chart_action',
    status TEXT NOT NULL DEFAULT 'active',
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    description TEXT,
    risk_notes TEXT,
    default_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tradingview_action_templates_category ON ops.tradingview_action_templates (category);
CREATE INDEX IF NOT EXISTS idx_tradingview_action_templates_status ON ops.tradingview_action_templates (status);

CREATE OR REPLACE VIEW ops.v_tradingview_action_templates AS
SELECT
    template_key,
    template_name,
    category,
    action_kind,
    default_exchange,
    default_timeframe,
    default_chart_layout,
    requires_symbol,
    approval_required,
    execution_mode,
    status,
    owner_agent,
    description,
    risk_notes,
    default_payload,
    updated_at
FROM ops.tradingview_action_templates
ORDER BY
    CASE status WHEN 'active' THEN 1 WHEN 'partial' THEN 2 WHEN 'gated' THEN 3 ELSE 4 END,
    category,
    template_key;

INSERT INTO ops.tradingview_action_templates (
    template_key, template_name, category, action_kind, default_exchange,
    default_timeframe, default_chart_layout, requires_symbol, approval_required,
    execution_mode, status, owner_agent, description, risk_notes, default_payload
)
VALUES
    (
        'open_symbol_chart',
        'Open Symbol Chart',
        'chart',
        'open_chart_capture',
        'NSE',
        'D',
        'single_symbol',
        true,
        false,
        'cdp_chart_action',
        'active',
        'Trading Desk Agent',
        'Open one TradingView chart for a symbol/timeframe and capture screenshot evidence.',
        'Read/capture only. No orders, alerts, or destructive chart edits.',
        '{"capture_screenshot":true,"wait_ms":9000}'::jsonb
    ),
    (
        'capture_chart_snapshot',
        'Capture Chart Snapshot',
        'chart',
        'open_chart_capture',
        'NSE',
        'D',
        'single_symbol_snapshot',
        true,
        false,
        'cdp_chart_action',
        'active',
        'Trading Desk Agent',
        'Capture a screenshot artifact for the requested symbol chart.',
        'Read/capture only. Use for research packets and Symbol Intelligence evidence.',
        '{"capture_screenshot":true,"wait_ms":12000}'::jsonb
    ),
    (
        'open_multi_symbol_layout',
        'Open Multi-Symbol Layout',
        'layout',
        'open_chart_capture',
        'NSE',
        'D',
        'multi_symbol_reference',
        true,
        false,
        'cdp_chart_action_partial_layout',
        'partial',
        'Trading Desk Agent',
        'Open the primary symbol and persist secondary symbols in task metadata until true multi-pane UI automation is built.',
        'Current implementation captures the primary chart only; multi-pane layout editing remains open.',
        '{"capture_screenshot":true,"wait_ms":12000,"secondary_symbols":[]}'::jsonb
    ),
    (
        'open_option_straddle_layout',
        'Open Option Straddle Layout',
        'options',
        'option_straddle_layout_request',
        'NSE',
        '5',
        'option_straddle_four_chart',
        true,
        true,
        'human_gated_request',
        'gated',
        'Options Overlay Agent',
        'Request a four-chart option/straddle TradingView layout. Human-gated until option symbol mapping and pane control are hardened.',
        'Requires human confirmation because it may change chart layout and depends on exact option symbols/expiry.',
        '{"requires":["underlying","expiry","strike","call_symbol","put_symbol"],"broker_order_allowed":false}'::jsonb
    ),
    (
        'capture_symbol_watchlist',
        'Capture Symbol Watchlist',
        'watchlist',
        'open_chart_capture',
        'NSE',
        'D',
        'watchlist_context',
        true,
        false,
        'cdp_chart_action',
        'active',
        'Trading Desk Agent',
        'Open a symbol chart and capture the visible TradingView watchlist/sidebar context as screenshot evidence.',
        'Read/capture only. Depends on the current TradingView sidebar state.',
        '{"capture_screenshot":true,"wait_ms":9000,"include_watchlist_context":true}'::jsonb
    ),
    (
        'create_alert_request',
        'Create Alert Request',
        'alert',
        'alert_create_request',
        'NSE',
        'D',
        'alert_request',
        true,
        true,
        'human_gated_request',
        'gated',
        'Risk Agent',
        'Create a human approval request for a TradingView alert. The system does not create/delete alerts automatically yet.',
        'Alert creation/deletion is gated because it changes user account state and can affect live monitoring.',
        '{"requires":["symbol","condition","timeframe"],"auto_create_alert":false}'::jsonb
    )
ON CONFLICT (template_key) DO UPDATE SET
    template_name = EXCLUDED.template_name,
    category = EXCLUDED.category,
    action_kind = EXCLUDED.action_kind,
    default_exchange = EXCLUDED.default_exchange,
    default_timeframe = EXCLUDED.default_timeframe,
    default_chart_layout = EXCLUDED.default_chart_layout,
    requires_symbol = EXCLUDED.requires_symbol,
    approval_required = EXCLUDED.approval_required,
    execution_mode = EXCLUDED.execution_mode,
    status = EXCLUDED.status,
    owner_agent = EXCLUDED.owner_agent,
    description = EXCLUDED.description,
    risk_notes = EXCLUDED.risk_notes,
    default_payload = EXCLUDED.default_payload,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_execute_tradingview_template_action',
        'mcp_tool',
        'Trading Desk Agent',
        'browser_capture_or_approval',
        true,
        'Execute an approved TradingView action template or create a human-gated approval request for unsafe templates.',
        '{"api_route":"/api/tradingview/template-actions","writes":["ops.tradingview_tasks","ops.browser_runs","core.raw_artifacts","agent.approvals","agent.inbox_items"],"reads":["ops.tradingview_action_templates"],"broker_order_allowed":false}'::jsonb
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
            'ops.tradingview_action_templates',
            'ops.v_tradingview_action_templates'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_execute_tradingview_template_action'
        ]::TEXT[]) AS tool
    ),
    next_action = 'TradingView action templates are registered; next harden multi-pane and option straddle UI automation.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'data_sources');
