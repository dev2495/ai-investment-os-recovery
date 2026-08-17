BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_activity_options_paper_source
ON trading.trade_activity_ledger (execution_mode,source_kind,source_ref)
WHERE execution_mode='paper'
  AND source_kind='options_paper_monitor'
  AND source_ref IS NOT NULL;

INSERT INTO agent.tool_registry
    (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES (
    'ai_os_run_options_paper_monitor','scheduled_workload','Options Analyst',
    'write_db_paper_only',true,
    'Create an idempotent one-unit ATM straddle benchmark from published options evidence and initialize Greek attribution without broker or capital writes.',
    '{"script":"_ai_os_runtime/scripts/run_options_paper_monitor.py","reads":["trading.option_specialist_observations","trading.option_chain_snapshot_batches","trading.option_chain_contract_snapshots","trading.option_iv_greeks_results"],"writes":["trading.trade_activity_ledger","trading.option_paper_trade_attributions"],"paper_only":true,"capital_action_allowed":false,"broker_write_allowed":false,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
