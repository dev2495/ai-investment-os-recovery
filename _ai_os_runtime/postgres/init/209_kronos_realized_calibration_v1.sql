BEGIN;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
)
VALUES (
    'kronos_realized_calibration','deterministic_model_validation','Model Validation Agent',
    'write_scoped',true,
    'Scores persisted Kronos forecast distributions against canonical point-in-time OHLCV. It cannot promote a strategy or create an order.',
    '{
      "source":"trading.ohlcv",
      "score_table":"strategy.kronos_forecast_scores",
      "minimum_walk_forward_origins":20,
      "single_origin_can_pass":false,
      "automatic_strategy_promotion_allowed":false,
      "live_execution_allowed":false,
      "broker_order_allowed":false
    }'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=true,
    description=EXCLUDED.description,
    config=EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects=array_append(
        array_remove(warehouse_objects,'strategy.kronos_forecast_scores'),
        'strategy.kronos_forecast_scores'
    ),
    mcp_tools=array_append(
        array_remove(mcp_tools,'kronos_realized_calibration'),
        'kronos_realized_calibration'
    ),
    next_action='Accumulate at least 20 non-overlapping matured forecast origins, then run independent walk-forward model review.',
    metadata=metadata || '{
      "realized_calibration":true,
      "minimum_walk_forward_origins":20,
      "single_origin_can_pass":false,
      "automatic_strategy_promotion_allowed":false,
      "broker_writes":false
    }'::jsonb,
    updated_at=now()
WHERE module_key='kronos_research_adapter';

COMMIT;
