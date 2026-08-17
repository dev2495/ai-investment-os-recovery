BEGIN;

-- Zero-retention routing must be priced at the eligible-provider ceiling,
-- never at the lower unrestricted catalogue rate.
UPDATE agent.model_cost_rates
SET input_usd_per_1m_tokens=1.740000,
    output_usd_per_1m_tokens=3.480000,
    rate_source='openrouter_zdr_provider_catalog_2026_08_14',
    notes='ZDR-compatible DeepSeek V4 Pro provider ceiling; replaces unrestricted catalogue price.',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('zdr_required',true,'data_collection','deny','catalog_checked_at','2026-08-14'),
    updated_at=now()
WHERE provider='openrouter' AND model_name='deepseek/deepseek-v4-pro-0813' AND status='active';

COMMIT;
