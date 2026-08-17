BEGIN;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
) VALUES (
    'ai_os_build_sector_membership_history',
    'deterministic_worker',
    'Sector Data Steward',
    'write_artifact_manual_only',
    true,
    'Validate dated full-basket NSE Indices snapshots and build non-overlapping point-in-time membership evidence for approval-gated import.',
    '{"script":"_ai_os_runtime/scripts/build_sector_membership_history_package.py","input_contract":{"artifact_type":"official_constituent_snapshot","minimum_snapshots":2,"minimum_span_days":365},"output":"sector intelligence import package","replacement_notice_inference_allowed":false,"backdating_current_snapshot_allowed":false,"seed_data_allowed":false,"broker_order_allowed":false,"capital_action_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,
    owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,
    enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,
    config=EXCLUDED.config;

COMMIT;
