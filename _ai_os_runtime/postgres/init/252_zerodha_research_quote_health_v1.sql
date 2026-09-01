\set ON_ERROR_STOP on

BEGIN;

-- Keep the canonical Zerodha stream surface and expose the age needed by
-- Research Desk. This changes no authentication, subscription, reconnect or
-- broker-write behavior.
CREATE OR REPLACE VIEW market.v_zerodha_stream_health AS
WITH latest_run AS (
    SELECT *
    FROM market.zerodha_stream_runs
    ORDER BY started_at DESC
    LIMIT 1
), quote_health AS (
    SELECT count(*) AS quote_count,
           count(*) FILTER (WHERE received_at >= now() - interval '20 seconds') AS live_count,
           max(received_at) AS latest_quote_at
    FROM market.live_quote_state
    WHERE provider = 'Zerodha'
)
SELECT run.id, run.run_key, run.status, run.connection_state,
       run.subscribed_instruments, run.ticks_received, run.rows_upserted,
       run.snapshots_written, run.reconnect_count, run.started_at,
       run.connected_at, run.last_tick_at, run.last_heartbeat_at,
       run.finished_at, run.error_message, run.metadata,
       quote.quote_count, quote.live_count, quote.latest_quote_at,
       CASE
         WHEN run.status IN ('waiting_for_daily_login','token_expired') THEN 'login_required'
         WHEN run.connection_state = 'connected'
          AND run.last_heartbeat_at >= now() - interval '90 seconds'
          AND quote.latest_quote_at >= now() - interval '20 seconds' THEN 'live'
         WHEN run.connection_state = 'connected'
          AND (run.last_heartbeat_at IS NULL OR run.last_heartbeat_at < now() - interval '90 seconds') THEN 'heartbeat_stale'
         WHEN run.connection_state = 'connected' THEN 'connected_no_recent_ticks'
         ELSE coalesce(run.status,'not_started')
       END AS health_status,
       false AS broker_write_allowed,
       CASE WHEN run.last_heartbeat_at IS NULL THEN NULL
            ELSE greatest(0, extract(epoch FROM (now() - run.last_heartbeat_at)))::integer
       END AS heartbeat_age_seconds,
       CASE WHEN quote.latest_quote_at IS NULL THEN NULL
            ELSE greatest(0, extract(epoch FROM (now() - quote.latest_quote_at)))::integer
       END AS latest_quote_age_seconds,
       CASE
         WHEN run.status IN ('waiting_for_daily_login','token_expired') THEN 'login_required'
         WHEN run.connection_state <> 'connected' OR run.connection_state IS NULL THEN 'disconnected'
         WHEN run.last_heartbeat_at IS NULL OR run.last_heartbeat_at < now() - interval '90 seconds' THEN 'stale_heartbeat'
         WHEN quote.latest_quote_at IS NULL OR quote.latest_quote_at < now() - interval '20 seconds' THEN 'delayed_quotes'
         ELSE 'healthy'
       END AS delay_status
FROM quote_health quote
LEFT JOIN latest_run run ON true;

UPDATE agent.tool_registry
SET config = coalesce(config, '{}'::jsonb) || jsonb_build_object(
        'reads', jsonb_build_array(
            'market.v_live_prices',
            'market.v_zerodha_stream_health',
            'market.live_quote_state',
            'market.zerodha_instruments'
        ),
        'research_quote_health_fields', jsonb_build_array(
            'provider',
            'exchange',
            'symbol',
            'quote_timestamp',
            'freshness',
            'mapping_status',
            'heartbeat_age_seconds',
            'delay_status'
        ),
        'broker_write_allowed', false
    ),
    updated_at = now()
WHERE tool_name = 'ai_os_zerodha_live_prices';

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    252,
    '252_zerodha_research_quote_health_v1',
    '95d630806ce2983369cc217fa7f3d75530223738320460560f0cf73b0ed6cc46',
    'Expose canonical Zerodha heartbeat and quote delay state to valuation research',
    '{"preserves_existing_pipeline":true,"daily_human_authentication_required":true,"broker_write_allowed":false,"order_placement_enabled":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
