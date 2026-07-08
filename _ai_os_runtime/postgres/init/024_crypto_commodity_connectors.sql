CREATE TABLE IF NOT EXISTS trading.exchange_venue_registry (
    id BIGSERIAL PRIMARY KEY,
    venue_key TEXT NOT NULL UNIQUE,
    venue_name TEXT NOT NULL,
    venue_type TEXT NOT NULL,
    provider TEXT,
    adapter TEXT NOT NULL,
    connection_mode TEXT NOT NULL DEFAULT 'api_read_only',
    status TEXT NOT NULL DEFAULT 'planned',
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    requires_api_key BOOLEAN NOT NULL DEFAULT true,
    execution_allowed BOOLEAN NOT NULL DEFAULT false,
    supported_asset_classes TEXT[] NOT NULL DEFAULT '{}',
    docs_url TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk',
    risk_notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_exchange_venue_registry_status ON trading.exchange_venue_registry (status);
CREATE INDEX IF NOT EXISTS idx_exchange_venue_registry_asset_classes ON trading.exchange_venue_registry USING GIN (supported_asset_classes);

CREATE TABLE IF NOT EXISTS trading.instrument_watchlist (
    id BIGSERIAL PRIMARY KEY,
    watch_key TEXT NOT NULL UNIQUE,
    venue_key TEXT REFERENCES trading.exchange_venue_registry(venue_key),
    provider_symbol TEXT NOT NULL,
    normalized_symbol TEXT NOT NULL,
    base_asset TEXT,
    quote_asset TEXT,
    asset_class TEXT NOT NULL,
    instrument_type TEXT NOT NULL DEFAULT 'spot',
    target_use TEXT NOT NULL DEFAULT 'watch',
    status TEXT NOT NULL DEFAULT 'planned',
    execution_allowed BOOLEAN NOT NULL DEFAULT false,
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_instrument_watchlist_asset_class ON trading.instrument_watchlist (asset_class);
CREATE INDEX IF NOT EXISTS idx_instrument_watchlist_status ON trading.instrument_watchlist (status);
CREATE INDEX IF NOT EXISTS idx_instrument_watchlist_symbol ON trading.instrument_watchlist (normalized_symbol);

CREATE OR REPLACE VIEW trading.v_exchange_connector_readiness AS
SELECT
    venue_key,
    venue_name,
    venue_type,
    provider,
    adapter,
    connection_mode,
    status,
    permission_level,
    requires_api_key,
    execution_allowed,
    supported_asset_classes,
    docs_url,
    owner_agent,
    risk_notes,
    metadata,
    updated_at
FROM trading.exchange_venue_registry
ORDER BY
    CASE status
        WHEN 'active' THEN 1
        WHEN 'candidate' THEN 2
        WHEN 'planned' THEN 3
        ELSE 4
    END,
    venue_name;

CREATE OR REPLACE VIEW trading.v_crypto_commodity_watchlist AS
SELECT
    watch_key,
    venue_key,
    provider_symbol,
    normalized_symbol,
    base_asset,
    quote_asset,
    asset_class,
    instrument_type,
    target_use,
    status,
    execution_allowed,
    owner_agent,
    metadata,
    updated_at
FROM trading.instrument_watchlist
WHERE asset_class IN ('crypto', 'tokenized_commodity', 'commodity_future', 'commodity_etf')
ORDER BY asset_class, normalized_symbol;

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    (
        'CCXT crypto gateway',
        'exchange_api_gateway',
        'external:ccxt',
        'private_trading',
        'planned',
        'Unified crypto exchange adapter for market data first. Execution remains disabled until keys, venue choice, and risk approvals exist.'
    ),
    (
        'Binance spot candidate',
        'crypto_exchange_api',
        'https://developers.binance.com/docs/binance-spot-api-docs/rest-api',
        'private_trading',
        'candidate',
        'Candidate market-data and crypto venue for BTC/ETH and tokenized commodity pairs where available. Use read-only first.'
    ),
    (
        'Dhan MCX commodity gateway',
        'broker_commodity_api',
        'https://dhanhq.co/docs/v2/',
        'client_private',
        'planned',
        'Indian broker/API path for MCX gold, silver, crude oil, and natural gas futures. Read-only/paper first.'
    )
ON CONFLICT (name) DO UPDATE SET
    source_type = EXCLUDED.source_type,
    location = EXCLUDED.location,
    sensitivity = EXCLUDED.sensitivity,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes;

INSERT INTO core.data_source_registry (
    source_key, source_name, source_type, provider, connection_mode, status,
    freshness_target_minutes, owner_agent, sensitivity, source_system_id, notes, metadata
)
VALUES
    (
        'ccxt_crypto_gateway',
        'CCXT crypto gateway',
        'exchange_api_gateway',
        'CCXT',
        'api_read_only',
        'planned',
        1,
        'Trading Desk',
        'private_trading',
        (SELECT id FROM core.source_systems WHERE name = 'CCXT crypto gateway'),
        'Unified crypto market-data and order-routing adapter. Execution is explicitly disabled until approval.',
        '{"execution_allowed":false,"paper_first":true,"adapter":"ccxt"}'::jsonb
    ),
    (
        'binance_spot_candidate',
        'Binance spot candidate',
        'crypto_exchange_api',
        'Binance',
        'api_read_only',
        'candidate',
        1,
        'Trading Desk',
        'private_trading',
        (SELECT id FROM core.source_systems WHERE name = 'Binance spot candidate'),
        'Candidate venue for BTC/ETH and available tokenized commodity pairs. Confirm jurisdiction, account access, and risk policy before live use.',
        '{"execution_allowed":false,"paper_first":true,"docs":"https://developers.binance.com/docs/binance-spot-api-docs/rest-api"}'::jsonb
    ),
    (
        'dhan_mcx_commodity_gateway',
        'Dhan MCX commodity gateway',
        'broker_commodity_api',
        'Dhan',
        'api_read_only',
        'planned',
        1,
        'Trading Desk',
        'client_private',
        (SELECT id FROM core.source_systems WHERE name = 'Dhan MCX commodity gateway'),
        'Preferred path for actual Indian commodity futures such as gold and silver; not a crypto exchange.',
        '{"execution_allowed":false,"paper_first":true,"docs":"https://dhanhq.co/docs/v2/"}'::jsonb
    )
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    provider = EXCLUDED.provider,
    connection_mode = EXCLUDED.connection_mode,
    status = EXCLUDED.status,
    freshness_target_minutes = EXCLUDED.freshness_target_minutes,
    owner_agent = EXCLUDED.owner_agent,
    sensitivity = EXCLUDED.sensitivity,
    source_system_id = EXCLUDED.source_system_id,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO trading.exchange_venue_registry (
    venue_key, venue_name, venue_type, provider, adapter, connection_mode, status,
    permission_level, requires_api_key, execution_allowed, supported_asset_classes,
    docs_url, owner_agent, risk_notes, metadata
)
VALUES
    (
        'ccxt_crypto_gateway',
        'CCXT Crypto Gateway',
        'exchange_gateway',
        'CCXT',
        'ccxt',
        'api_read_only',
        'planned',
        'read_only',
        true,
        false,
        ARRAY['crypto','tokenized_commodity']::TEXT[],
        'https://docs.ccxt.com/',
        'Trading Desk',
        'Use for unified market data and paper routing first. Do not enable execution without separate key vault, venue policy, and approval workflow.',
        '{"supports_multiple_exchanges":true,"execution_gate":"human_approval_required"}'::jsonb
    ),
    (
        'binance_spot_candidate',
        'Binance Spot Candidate',
        'crypto_exchange',
        'Binance',
        'binance_rest_or_ccxt',
        'api_read_only',
        'candidate',
        'read_only',
        true,
        false,
        ARRAY['crypto','tokenized_commodity']::TEXT[],
        'https://developers.binance.com/docs/binance-spot-api-docs/rest-api',
        'Trading Desk',
        'Candidate venue only. Confirm legal/account availability and tokenized commodity liquidity before use.',
        '{"market_data_public":true,"execution_gate":"human_approval_required"}'::jsonb
    ),
    (
        'dhan_mcx_commodity_gateway',
        'Dhan MCX Commodity Gateway',
        'broker_commodity_api',
        'Dhan',
        'dhanhq',
        'api_read_only',
        'planned',
        'read_only',
        true,
        false,
        ARRAY['commodity_future','equity','option','index']::TEXT[],
        'https://dhanhq.co/docs/v2/',
        'Trading Desk',
        'Use this for Indian gold/silver/commodity futures. Keep order placement disabled until broker auth, risk controls, and explicit approval are complete.',
        '{"market":"MCX","execution_gate":"human_approval_required"}'::jsonb
    ),
    (
        'tradingview_mcp',
        'TradingView MCP Bridge',
        'chart_market_data_bridge',
        'TradingView',
        'mcp_browser_bridge',
        'mcp_read_only',
        'active',
        'read_only',
        false,
        false,
        ARRAY['equity','commodity_etf','index','option']::TEXT[],
        NULL,
        'Trading Desk',
        'Charting and browser-assisted market context only. No broker execution is available through this connector.',
        '{"execution_allowed":false,"source_key":"tradingview_mcp"}'::jsonb
    )
ON CONFLICT (venue_key) DO UPDATE SET
    venue_name = EXCLUDED.venue_name,
    venue_type = EXCLUDED.venue_type,
    provider = EXCLUDED.provider,
    adapter = EXCLUDED.adapter,
    connection_mode = EXCLUDED.connection_mode,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    requires_api_key = EXCLUDED.requires_api_key,
    execution_allowed = EXCLUDED.execution_allowed,
    supported_asset_classes = EXCLUDED.supported_asset_classes,
    docs_url = EXCLUDED.docs_url,
    owner_agent = EXCLUDED.owner_agent,
    risk_notes = EXCLUDED.risk_notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO trading.instrument_watchlist (
    watch_key, venue_key, provider_symbol, normalized_symbol, base_asset, quote_asset,
    asset_class, instrument_type, target_use, status, execution_allowed, owner_agent, metadata
)
VALUES
    ('crypto_btc_usdt', 'ccxt_crypto_gateway', 'BTC/USDT', 'BTCUSDT', 'BTC', 'USDT', 'crypto', 'spot', 'market_data_and_paper', 'planned', false, 'Trading Desk', '{"priority":"core"}'::jsonb),
    ('crypto_eth_usdt', 'ccxt_crypto_gateway', 'ETH/USDT', 'ETHUSDT', 'ETH', 'USDT', 'crypto', 'spot', 'market_data_and_paper', 'planned', false, 'Trading Desk', '{"priority":"core"}'::jsonb),
    ('crypto_paxg_usdt', 'ccxt_crypto_gateway', 'PAXG/USDT', 'PAXGUSDT', 'PAXG', 'USDT', 'tokenized_commodity', 'spot', 'watch_and_paper', 'planned', false, 'Trading Desk', '{"commodity_proxy":"gold","notes":"Tokenized gold exposure; not equivalent to MCX gold futures."}'::jsonb),
    ('crypto_xaut_usdt', 'ccxt_crypto_gateway', 'XAUT/USDT', 'XAUTUSDT', 'XAUT', 'USDT', 'tokenized_commodity', 'spot', 'watch_and_paper', 'planned', false, 'Trading Desk', '{"commodity_proxy":"gold","notes":"Tokenized gold exposure; exchange availability varies."}'::jsonb),
    ('mcx_gold_future', 'dhan_mcx_commodity_gateway', 'MCX:GOLD', 'MCX:GOLD', 'GOLD', 'INR', 'commodity_future', 'future', 'market_data_and_paper', 'planned', false, 'Trading Desk', '{"commodity":"gold","exchange":"MCX"}'::jsonb),
    ('mcx_silver_future', 'dhan_mcx_commodity_gateway', 'MCX:SILVER', 'MCX:SILVER', 'SILVER', 'INR', 'commodity_future', 'future', 'market_data_and_paper', 'planned', false, 'Trading Desk', '{"commodity":"silver","exchange":"MCX"}'::jsonb),
    ('mcx_crudeoil_future', 'dhan_mcx_commodity_gateway', 'MCX:CRUDEOIL', 'MCX:CRUDEOIL', 'CRUDEOIL', 'INR', 'commodity_future', 'future', 'watch_and_paper', 'planned', false, 'Trading Desk', '{"commodity":"crude_oil","exchange":"MCX"}'::jsonb),
    ('mcx_naturalgas_future', 'dhan_mcx_commodity_gateway', 'MCX:NATURALGAS', 'MCX:NATURALGAS', 'NATURALGAS', 'INR', 'commodity_future', 'future', 'watch_and_paper', 'planned', false, 'Trading Desk', '{"commodity":"natural_gas","exchange":"MCX"}'::jsonb),
    ('nse_goldbees_proxy', 'tradingview_mcp', 'NSE:GOLDBEES', 'GOLDBEES', 'GOLDBEES', 'INR', 'commodity_etf', 'etf', 'portfolio_proxy', 'planned', false, 'Portfolio Manager', '{"commodity_proxy":"gold","exchange":"NSE"}'::jsonb),
    ('nse_silverbees_proxy', 'tradingview_mcp', 'NSE:SILVERBEES', 'SILVERBEES', 'SILVERBEES', 'INR', 'commodity_etf', 'etf', 'portfolio_proxy', 'planned', false, 'Portfolio Manager', '{"commodity_proxy":"silver","exchange":"NSE"}'::jsonb)
ON CONFLICT (watch_key) DO UPDATE SET
    venue_key = EXCLUDED.venue_key,
    provider_symbol = EXCLUDED.provider_symbol,
    normalized_symbol = EXCLUDED.normalized_symbol,
    base_asset = EXCLUDED.base_asset,
    quote_asset = EXCLUDED.quote_asset,
    asset_class = EXCLUDED.asset_class,
    instrument_type = EXCLUDED.instrument_type,
    target_use = EXCLUDED.target_use,
    status = EXCLUDED.status,
    execution_allowed = EXCLUDED.execution_allowed,
    owner_agent = EXCLUDED.owner_agent,
    metadata = EXCLUDED.metadata,
    updated_at = now();
