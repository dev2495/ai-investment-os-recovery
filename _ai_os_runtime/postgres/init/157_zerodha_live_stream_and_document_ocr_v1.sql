BEGIN;

CREATE TABLE IF NOT EXISTS market.zerodha_stream_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'starting',
    connection_state TEXT NOT NULL DEFAULT 'disconnected',
    subscribed_instruments INTEGER NOT NULL DEFAULT 0,
    ticks_received BIGINT NOT NULL DEFAULT 0,
    rows_upserted BIGINT NOT NULL DEFAULT 0,
    snapshots_written BIGINT NOT NULL DEFAULT 0,
    reconnect_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    connected_at TIMESTAMPTZ,
    last_tick_at TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false)
);

CREATE INDEX IF NOT EXISTS idx_zerodha_stream_runs_latest
    ON market.zerodha_stream_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS market.live_quote_state (
    provider TEXT NOT NULL,
    instrument_token BIGINT NOT NULL,
    provider_symbol TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    instrument_type TEXT,
    last_price NUMERIC NOT NULL,
    last_quantity NUMERIC,
    average_price NUMERIC,
    volume NUMERIC,
    buy_quantity NUMERIC,
    sell_quantity NUMERIC,
    open_interest NUMERIC,
    open_interest_high NUMERIC,
    open_interest_low NUMERIC,
    bid_price NUMERIC,
    ask_price NUMERIC,
    day_open NUMERIC,
    day_high NUMERIC,
    day_low NUMERIC,
    previous_close NUMERIC,
    change_percent NUMERIC,
    exchange_timestamp TIMESTAMPTZ,
    last_trade_timestamp TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_mode TEXT NOT NULL DEFAULT 'websocket_full',
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    PRIMARY KEY (provider, instrument_token)
);

CREATE INDEX IF NOT EXISTS idx_live_quote_state_symbol
    ON market.live_quote_state (exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_live_quote_state_freshness
    ON market.live_quote_state (received_at DESC);

CREATE TABLE IF NOT EXISTS market.live_quote_minute_snapshots (
    provider TEXT NOT NULL,
    instrument_token BIGINT NOT NULL,
    minute_ts TIMESTAMPTZ NOT NULL,
    provider_symbol TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    open_price NUMERIC NOT NULL,
    high_price NUMERIC NOT NULL,
    low_price NUMERIC NOT NULL,
    close_price NUMERIC NOT NULL,
    volume NUMERIC,
    open_interest NUMERIC,
    tick_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    PRIMARY KEY (provider, instrument_token, minute_ts)
);

CREATE INDEX IF NOT EXISTS idx_live_quote_minute_symbol_ts
    ON market.live_quote_minute_snapshots (exchange, symbol, minute_ts DESC);

CREATE OR REPLACE VIEW market.v_live_prices AS
WITH held AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM portfolio.positions
    WHERE as_of >= (SELECT max(as_of)-interval '1 day' FROM portfolio.positions)
      AND coalesce(quantity,0) <> 0
), watched AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM research.v_watchlist_board
    WHERE status='active'
)
SELECT quote.provider, quote.instrument_token, quote.provider_symbol,
       quote.symbol, quote.exchange, quote.instrument_type,
       quote.last_price, quote.last_quantity, quote.average_price,
       quote.volume, quote.buy_quantity, quote.sell_quantity,
       quote.open_interest, quote.open_interest_high, quote.open_interest_low,
       quote.bid_price, quote.ask_price, quote.day_open, quote.day_high,
       quote.day_low, quote.previous_close, quote.change_percent,
       quote.exchange_timestamp, quote.last_trade_timestamp, quote.received_at,
       extract(epoch FROM (now()-quote.received_at))::integer AS age_seconds,
       CASE WHEN quote.received_at >= now()-interval '20 seconds' THEN 'live'
            WHEN quote.received_at >= now()-interval '5 minutes' THEN 'delayed'
            ELSE 'stale' END AS freshness,
       (held.symbol IS NOT NULL) AS in_portfolio,
       (watched.symbol IS NOT NULL) AS on_watchlist,
       quote.source_mode, false AS broker_write_allowed
FROM market.live_quote_state quote
LEFT JOIN held ON held.symbol=upper(quote.symbol)
LEFT JOIN watched ON watched.symbol=upper(quote.symbol)
ORDER BY CASE WHEN held.symbol IS NOT NULL THEN 0 WHEN watched.symbol IS NOT NULL THEN 1 ELSE 2 END,
         quote.exchange, quote.symbol;

CREATE OR REPLACE VIEW market.v_zerodha_stream_health AS
WITH latest_run AS (
    SELECT * FROM market.zerodha_stream_runs ORDER BY started_at DESC LIMIT 1
), quote_health AS (
    SELECT count(*) AS quote_count,
           count(*) FILTER (WHERE received_at>=now()-interval '20 seconds') AS live_count,
           max(received_at) AS latest_quote_at
    FROM market.live_quote_state WHERE provider='Zerodha'
)
SELECT run.id, run.run_key, run.status, run.connection_state,
       run.subscribed_instruments, run.ticks_received, run.rows_upserted,
       run.snapshots_written, run.reconnect_count, run.started_at,
       run.connected_at, run.last_tick_at, run.last_heartbeat_at,
       run.finished_at, run.error_message, run.metadata,
       quote.quote_count, quote.live_count, quote.latest_quote_at,
       CASE WHEN run.connection_state='connected' AND quote.latest_quote_at>=now()-interval '20 seconds'
            THEN 'live'
            WHEN run.status IN ('waiting_for_daily_login','token_expired') THEN 'login_required'
            WHEN run.connection_state='connected' THEN 'connected_no_recent_ticks'
            ELSE coalesce(run.status,'not_started') END AS health_status,
       false AS broker_write_allowed
FROM quote_health quote
LEFT JOIN latest_run run ON true;

INSERT INTO agent.model_catalog (
    model_key,provider,model_name,model_family,deployment_target,estimated_disk_gb,
    context_window_hint,current_status,best_for,avoid_for,cost_tier,notes
) VALUES (
    'baidu_unlimited_ocr_3_3b','huggingface','baidu/Unlimited-OCR','multimodal_document_ocr',
    'rented_cuda_gpu_on_demand',6.67,'32768 output-token ceiling','candidate_gpu_only',
    ARRAY['scanned filings','multi-page PDFs','tables','forms','long-horizon document parsing'],
    ARRAY['always-on iMac','Apple Silicon production until upstream MPS support merges','sensitive client PDFs without approval'],
    'cloud_low','MIT model. Official inference is CUDA-first; 3.336B BF16 parameters and custom code. Use only as an OCR escalation after deterministic text extraction fails.'
)
ON CONFLICT (model_key) DO UPDATE SET
    provider=EXCLUDED.provider,model_name=EXCLUDED.model_name,
    model_family=EXCLUDED.model_family,deployment_target=EXCLUDED.deployment_target,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,context_window_hint=EXCLUDED.context_window_hint,
    current_status=EXCLUDED.current_status,best_for=EXCLUDED.best_for,
    avoid_for=EXCLUDED.avoid_for,cost_tier=EXCLUDED.cost_tier,
    notes=EXCLUDED.notes,updated_at=now();

INSERT INTO agent.model_endpoints (
    endpoint_key,endpoint_name,provider,model_name,route_name,endpoint_type,
    base_url,deployment_target,status,context_window,estimated_disk_gb,cost_tier,
    capabilities,requires_api_key,secret_ref,health_status,owner_agent,notes,config
) VALUES (
    'baidu_unlimited_ocr_gpu','Unlimited-OCR on-demand document parser','huggingface_vllm',
    'baidu/Unlimited-OCR','multimodal_document_analysis','openai_compatible_cloud',NULL,
    'rented_cuda_gpu_on_demand','candidate',32768,6.67,'cloud_low',
    ARRAY['image_text_to_text','ocr','multi_page_pdf','table_parsing','multilingual'],
    true,'AI_OS_UNLIMITED_OCR_API_KEY','not_configured','Document Extraction Agent',
    'Do not assign until endpoint, privacy policy, benchmark set, and cost cap pass. Text-native PDFs continue through pypdf first.',
    '{"license":"MIT","official_runtime":"CUDA","trust_remote_code":true,"vllm_recipe":true,"apple_silicon_status":"upstream_support_unmerged","pdf_policy":"deterministic_text_first_then_ocr","client_private_requires_approval":true,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,provider=EXCLUDED.provider,model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,endpoint_type=EXCLUDED.endpoint_type,
    deployment_target=EXCLUDED.deployment_target,status=EXCLUDED.status,
    context_window=EXCLUDED.context_window,estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    cost_tier=EXCLUDED.cost_tier,capabilities=EXCLUDED.capabilities,
    requires_api_key=EXCLUDED.requires_api_key,secret_ref=EXCLUDED.secret_ref,
    owner_agent=EXCLUDED.owner_agent,notes=EXCLUDED.notes,config=EXCLUDED.config,
    updated_at=now();

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
    ('ai_os_zerodha_live_prices','mcp_tool','Market Data Engineer','read_only',true,
     'Read current Zerodha WebSocket prices and stream freshness for holdings, watchlists, indices and monitored options.',
     '{"api_routes":["/api/market/live-prices","/api/zerodha/stream/status"],"reads":["market.v_live_prices","market.v_zerodha_stream_health"],"broker_write_allowed":false}'::jsonb),
    ('ai_os_unlimited_ocr_escalation','model_adapter','Document Extraction Agent','network_read_with_approval',false,
     'Escalate scanned or low-text PDFs to Unlimited-OCR on a configured CUDA endpoint after deterministic extraction fails.',
     '{"model":"baidu/Unlimited-OCR","endpoint_key":"baidu_unlimited_ocr_gpu","text_first":true,"approval_required_for_client_private":true,"enabled_after_eval":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

UPDATE core.data_source_registry
SET connection_mode='websocket_and_http_read_only', status='active', freshness_target_minutes=1,
    notes='Primary read-only Zerodha account and market-data adapter. WebSocket ticks update current state; minute snapshots are retained for charts. Daily human authentication is required by Zerodha. Order writes are absent.',
    metadata=metadata||'{"websocket_stream":true,"live_price_view":"market.v_live_prices","minute_snapshots":true,"daily_human_authentication_required":true,"automatic_reconnect":true,"broker_write_allowed":false}'::jsonb,
    updated_at=now()
WHERE source_key='zerodha_live';

UPDATE core.source_connector_profiles
SET status='active',freshness_target_minutes=1,
    config=config||'{"websocket_stream":true,"stream_health_view":"market.v_zerodha_stream_health","automatic_reconnect":true,"daily_human_authentication_required":true,"broker_write_allowed":false}'::jsonb,
    notes='GET-only account data plus live WebSocket market data. Session expiry creates a single operator alert and waits for human re-authentication; credentials and tokens are never logged.',
    updated_at=now()
WHERE connector_key='zerodha_live_connector';

COMMIT;
