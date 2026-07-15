CREATE OR REPLACE VIEW ops.v_tradingview_template_approval_queue AS
SELECT
    approval.id,
    approval.title,
    approval.owner_agent,
    approval.risk_level,
    approval.status,
    approval.requested_action,
    approval.requested_action->'compiled_plan' AS compiled_plan,
    coalesce((approval.requested_action->'compiled_plan'->>'execution_ready')::BOOLEAN, false) AS execution_ready,
    approval.requested_action->'compiled_plan'->>'fulfillment' AS fulfillment,
    approval.rationale,
    approval.created_at,
    approval.decided_by,
    approval.decided_at,
    task.id AS tradingview_task_id,
    task.task_title,
    task.status AS task_status,
    task.symbols,
    task.timeframe,
    task.chart_layout,
    task.result_summary,
    false AS broker_order_allowed
FROM agent.approvals approval
LEFT JOIN ops.tradingview_tasks task
  ON task.id = (approval.requested_action->>'tradingview_task_id')::BIGINT
WHERE approval.approval_type = 'tradingview_template_action';

UPDATE ops.tradingview_action_templates
SET default_payload = default_payload || CASE template_key
        WHEN 'relative_strength_ratio_chart' THEN '{"deterministic_formula_execution":true,"fulfillment":"complete_formula_chart"}'::jsonb
        WHEN 'spread_pair_formula_chart' THEN '{"deterministic_formula_execution":true,"fulfillment":"complete_formula_chart"}'::jsonb
        WHEN 'option_straddle_four_pane' THEN '{"deterministic_formula_execution":true,"fulfillment":"straddle_formula_only_four_pane_pending"}'::jsonb
        WHEN 'open_option_straddle_layout' THEN '{"deterministic_formula_execution":true,"fulfillment":"straddle_formula_only_four_pane_pending"}'::jsonb
        ELSE '{"deterministic_formula_execution":false}'::jsonb
    END,
    updated_at = now()
WHERE template_key IN (
    'relative_strength_ratio_chart', 'spread_pair_formula_chart',
    'option_straddle_four_pane', 'open_option_straddle_layout',
    'technical_indicator_stack', 'fundamental_ratio_dashboard',
    'market_regime_four_pane', 'create_alert_request'
);

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_resolve_tradingview_template_approval',
    'mcp_tool',
    'Risk Agent',
    'human_approval_and_browser_capture',
    true,
    'Approve and execute or reject a compiled TradingView chart plan. Only deterministic plans execute; broker orders remain blocked.',
    '{"api_route":"/api/tradingview/template-approvals/resolve","reads":["agent.approvals","ops.tradingview_tasks","ops.tradingview_action_templates"],"writes":["agent.approvals","agent.inbox_items","ops.tradingview_tasks","ops.browser_runs","core.raw_artifacts"],"broker_order_allowed":false,"deterministic_formula_execution":true}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE agent.tool_registry
SET config = config || '{"engine":"local_strategy_optimizer_v2","timestamp_aligned_returns":true,"nested_walk_forward":true,"embargo":true,"parameter_stability":true,"cost_stress":[1.0,1.5,2.0],"live_execution_allowed":false}'::jsonb,
    description = 'Create a strategy from user input and run parser, data gate, baseline backtest, timestamp-aligned nested walk-forward optimization, cost stress, and model-validation routing using real OHLCV. This never enables live execution.'
WHERE tool_name = 'ai_os_run_user_defined_strategy_optimizer';

UPDATE agent.tool_registry
SET config = config || '{"source_fingerprint_deduplication":true,"optimizer_cooldown_hours":168,"unchanged_source_reuse":true,"live_execution_allowed":false}'::jsonb
WHERE tool_name IN ('ai_os_run_strategy_discovery', 'ai_os_run_strategy_discovery_scheduler');

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT object_name
        FROM unnest(warehouse_objects || ARRAY['ops.v_tradingview_template_approval_queue']::TEXT[]) object_name
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool_name
        FROM unnest(mcp_tools || ARRAY['ai_os_resolve_tradingview_template_approval']::TEXT[]) tool_name
    ),
    next_action = 'Use the Strategy Arsenal full-test control and execute deterministic TradingView formula plans through dedicated approval; pane and indicator mutation remain explicitly partial.',
    updated_at = now()
WHERE module_key IN ('trading_desk', 'quant_lab', 'automation');
