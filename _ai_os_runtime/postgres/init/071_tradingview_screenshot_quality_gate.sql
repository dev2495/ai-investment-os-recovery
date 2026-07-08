UPDATE ops.tradingview_action_templates
SET default_payload = default_payload || '{"quality_check":true,"max_quality_attempts":3}'::jsonb,
    risk_notes = risk_notes || ' Screenshot artifacts are quality-checked and blank chart canvases are routed to needs_review.',
    updated_at = now()
WHERE template_key IN ('open_symbol_chart', 'capture_chart_snapshot', 'open_multi_symbol_layout', 'capture_symbol_watchlist');

UPDATE agent.tool_registry
SET config = config || '{
        "quality_gate": {
            "enabled": true,
            "default_max_attempts": 3,
            "failed_status": "needs_review",
            "method": "png_pixel_analysis_chart_region"
        }
    }'::jsonb,
    description = 'Open a TradingView chart through local CDP, capture a screenshot artifact, quality-check the chart canvas, and update the TradingView task. This does not place trades.'
WHERE tool_name = 'ai_os_execute_tradingview_chart_action';

UPDATE agent.tool_registry
SET config = config || '{
        "quality_gate": {
            "enabled": true,
            "default_max_attempts": 3,
            "failed_status": "needs_review",
            "method": "png_pixel_analysis_chart_region"
        }
    }'::jsonb
WHERE tool_name = 'ai_os_execute_tradingview_template_action';

UPDATE core.control_plane_modules
SET next_action = 'TradingView screenshot quality gate is active; next harden multi-pane, option straddle, and alert-management workflows.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'automation', 'data_sources');
