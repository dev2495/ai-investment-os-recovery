UPDATE core.integration_jobs
SET schedule_cron = '*/15 * * * *',
    run_mode = 'daemon',
    parameters = parameters || '{"daemon_interval_seconds":900,"freshness_source_key":"global_news","seed_data_allowed":false}'::jsonb,
    notes = 'Dedicated 15-minute daemon ingestion keeps the 15-minute global-news SLA aligned; hourly strategy discovery may re-read the same idempotent items.',
    updated_at = now()
WHERE job_key = 'global_news_hourly_ingestion';

UPDATE core.data_source_registry
SET status = 'active',
    freshness_target_minutes = 15,
    notes = coalesce(notes, '') || ' Dedicated 15-minute daemon ingestion records aggregate global_news checks.',
    updated_at = now()
WHERE source_key = 'global_news';

UPDATE agent.tool_registry
SET config = config || '{"daemon_interval_seconds":900,"aggregate_freshness_source_key":"global_news"}'::jsonb
WHERE tool_name = 'ai_os_ingest_market_news';
