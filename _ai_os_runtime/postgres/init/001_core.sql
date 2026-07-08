CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS trading;
CREATE SCHEMA IF NOT EXISTS portfolio;
CREATE SCHEMA IF NOT EXISTS client_data;
CREATE SCHEMA IF NOT EXISTS agent;

CREATE TABLE IF NOT EXISTS core.source_systems (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    location TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'private',
    status TEXT NOT NULL DEFAULT 'discovered',
    notes TEXT,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.import_runs (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    import_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    rows_seen BIGINT DEFAULT 0,
    rows_imported BIGINT DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS trading.symbols (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    exchange TEXT,
    instrument_type TEXT,
    name TEXT,
    currency TEXT DEFAULT 'INR',
    active BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (symbol, exchange, instrument_type)
);

CREATE TABLE IF NOT EXISTS trading.ohlcv (
    ts TIMESTAMPTZ NOT NULL,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id),
    timeframe TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    PRIMARY KEY (ts, symbol_id, timeframe)
);

SELECT create_hypertable('trading.ohlcv', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS trading.signals (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_system_id BIGINT REFERENCES core.source_systems(id),
    strategy TEXT,
    symbol TEXT,
    exchange TEXT,
    action TEXT,
    price NUMERIC,
    quantity NUMERIC,
    confidence NUMERIC,
    payload JSONB,
    status TEXT NOT NULL DEFAULT 'observed'
);

CREATE INDEX IF NOT EXISTS idx_trading_signals_ts ON trading.signals (ts DESC);
CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol ON trading.signals (symbol);

CREATE TABLE IF NOT EXISTS portfolio.accounts (
    id BIGSERIAL PRIMARY KEY,
    account_code TEXT NOT NULL UNIQUE,
    account_name TEXT NOT NULL,
    account_type TEXT,
    broker TEXT,
    base_currency TEXT DEFAULT 'INR',
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS portfolio.trades (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    account_id BIGINT REFERENCES portfolio.accounts(id),
    symbol TEXT NOT NULL,
    exchange TEXT,
    instrument_type TEXT,
    side TEXT,
    quantity NUMERIC,
    price NUMERIC,
    trade_ts TIMESTAMPTZ,
    strategy TEXT,
    raw_payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_portfolio_trades_ts ON portfolio.trades (trade_ts DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_trades_symbol ON portfolio.trades (symbol);

CREATE TABLE IF NOT EXISTS portfolio.snapshots (
    ts TIMESTAMPTZ NOT NULL,
    account_id BIGINT NOT NULL REFERENCES portfolio.accounts(id),
    equity NUMERIC,
    cash NUMERIC,
    margin_used NUMERIC,
    pnl_day NUMERIC,
    pnl_total NUMERIC,
    payload JSONB,
    PRIMARY KEY (ts, account_id)
);

SELECT create_hypertable('portfolio.snapshots', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS client_data.safe_dataset_registry (
    id BIGSERIAL PRIMARY KEY,
    dataset_name TEXT NOT NULL UNIQUE,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    sensitivity TEXT NOT NULL DEFAULT 'client_private',
    row_count BIGINT,
    columns_json JSONB,
    safe_view_name TEXT,
    notes TEXT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.run_log (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    output_note_path TEXT,
    metadata JSONB
);

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    ('ps 2 cursor archive', 'zip_archive', '/Volumes/Devarsh SSD/ps 2 cursor.zip', 'client_private', 'discovered', '936 MB archive; contains portfolio/client app files, CSVs, Zerodha scripts, backend .env. Do not extract into notes vault.'),
    ('algo trading terminal', 'local_repo', '/Volumes/Devarsh SSD/algo based trading software 2', 'private_trading', 'discovered', 'Existing trading terminal with SQLite DBs, live trading, backtesting, dashboard, TradingView webhook.'),
    ('algo trades db', 'sqlite', '/Volumes/Devarsh SSD/algo based trading software 2/data/trades.db', 'private_trading', 'discovered', 'Readable SQLite trades table.'),
    ('algo app db', 'sqlite', '/Volumes/Devarsh SSD/algo based trading software 2/data/storage/app.db', 'private_trading', 'discovered', 'Valid SQLite file; inspect through import runtime.'),
    ('algo prices db', 'sqlite', '/Volumes/Devarsh SSD/algo based trading software 2/data/storage/prices.db', 'private_trading', 'discovered', 'Valid SQLite file; likely historical price/live data store.')
ON CONFLICT (name) DO NOTHING;

