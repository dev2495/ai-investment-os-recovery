CREATE TABLE IF NOT EXISTS market.price_quotes (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_symbol TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    description TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    price NUMERIC NOT NULL,
    change_percent NUMERIC,
    quote_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_key, provider_symbol, quote_ts)
);

CREATE INDEX IF NOT EXISTS idx_price_quotes_symbol_ts ON market.price_quotes (symbol, quote_ts DESC);
CREATE INDEX IF NOT EXISTS idx_price_quotes_source_ts ON market.price_quotes (source_key, quote_ts DESC);

CREATE OR REPLACE VIEW market.v_latest_price_quotes AS
SELECT DISTINCT ON (symbol)
    id,
    source_key,
    provider,
    provider_symbol,
    symbol,
    exchange,
    description,
    currency,
    price,
    change_percent,
    quote_ts,
    raw_payload,
    created_at
FROM market.price_quotes
ORDER BY symbol, quote_ts DESC, id DESC;

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    (
        'TradingView scanner quotes',
        'public_market_data_api',
        'https://scanner.tradingview.com/india/scan',
        'public',
        'active',
        'Batch quote source for local mark-to-market. Used read-only; no execution.'
    ),
    (
        'Sanjana Long Term Report 2025-09-17',
        'pdf_report',
        '/Users/devarshthakkar/Downloads/Sanjana_Long Term_Report_2025-09-17.pdf',
        'client_private',
        'imported',
        'Client Sanjana holdings and trade report extracted from PDF.'
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
        'tradingview_scanner_quotes',
        'TradingView scanner quotes',
        'market_quote_api',
        'TradingView',
        'http_read_only',
        'active',
        15,
        'Data Steward',
        'public',
        (SELECT id FROM core.source_systems WHERE name = 'TradingView scanner quotes'),
        'Batch mark-to-market quote endpoint for Indian equities. No broker execution.',
        '{"execution_allowed":false,"endpoint":"https://scanner.tradingview.com/india/scan"}'::jsonb
    ),
    (
        'sanjana_long_term_report_2025_09_17',
        'Sanjana Long Term Report 2025-09-17',
        'client_pdf_report',
        'local_pdf',
        'pdf_extract',
        'imported',
        NULL,
        'Portfolio Manager',
        'client_private',
        (SELECT id FROM core.source_systems WHERE name = 'Sanjana Long Term Report 2025-09-17'),
        'Sanjana holdings and all-trades report imported from user-provided PDF.',
        '{"client_code":"sanjana","report_date":"2025-09-17"}'::jsonb
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
