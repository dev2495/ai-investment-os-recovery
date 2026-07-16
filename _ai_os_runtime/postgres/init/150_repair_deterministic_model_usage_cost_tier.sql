UPDATE agent.model_usage_events
SET cost_tier = 'local',
    estimated_cost_usd = COALESCE(estimated_cost_usd, 0),
    estimate_method = CASE
        WHEN estimate_method = 'unknown' THEN 'deterministic_local_zero_cost'
        ELSE estimate_method
    END,
    updated_at = now()
WHERE provider IN ('local_tools', 'local_python', 'deterministic')
  AND cost_tier <> 'local';
