CREATE TABLE IF NOT EXISTS client_data.attached_transaction_files (
    id BIGSERIAL PRIMARY KEY,
    source_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    client_code TEXT,
    client_name TEXT,
    period_start DATE,
    period_end DATE,
    row_count BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sha256, file_kind)
);

CREATE TABLE IF NOT EXISTS client_data.attached_broker_transactions (
    id BIGSERIAL PRIMARY KEY,
    source_file_id BIGINT NOT NULL REFERENCES client_data.attached_transaction_files(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    client_code TEXT,
    client_name TEXT,
    trade_date DATE,
    trade_time TIME,
    exchange TEXT,
    trading_symbol TEXT,
    side TEXT,
    quantity NUMERIC,
    market_rate NUMERIC,
    net_rate NUMERIC,
    amount NUMERIC,
    settlement_no TEXT,
    trade_no TEXT,
    expiry_date DATE,
    option_type TEXT,
    strike_price NUMERIC,
    instrument_type TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_file_id, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_attached_broker_client_date ON client_data.attached_broker_transactions (client_code, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_attached_broker_symbol ON client_data.attached_broker_transactions (trading_symbol);

CREATE TABLE IF NOT EXISTS client_data.attached_option_log_transactions (
    id BIGSERIAL PRIMARY KEY,
    source_file_id BIGINT NOT NULL REFERENCES client_data.attached_transaction_files(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    trade_id TEXT,
    trade_status TEXT,
    trade_type TEXT,
    no_of_trades NUMERIC,
    client_code TEXT,
    entry_date DATE,
    stock_ticker TEXT,
    lot_size NUMERIC,
    contracts NUMERIC,
    entry_stock_price NUMERIC,
    side TEXT,
    call_put TEXT,
    strike_price NUMERIC,
    delta_value NUMERIC,
    option_value NUMERIC,
    entry_credit_debit NUMERIC,
    entry_volatility NUMERIC,
    margin_required NUMERIC,
    stop_loss_price NUMERIC,
    exit_date DATE,
    exit_stock_price NUMERIC,
    exit_option_value NUMERIC,
    exit_credit_debit NUMERIC,
    exit_volatility NUMERIC,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_file_id, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_attached_option_client_entry ON client_data.attached_option_log_transactions (client_code, entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_attached_option_symbol ON client_data.attached_option_log_transactions (stock_ticker);

CREATE OR REPLACE VIEW client_data.v_attached_client_trade_ledger AS
SELECT
    'broker' AS source_type,
    f.file_name,
    b.client_code,
    b.client_name,
    b.trade_date AS entry_date,
    NULL::date AS exit_date,
    b.trade_time,
    b.exchange,
    b.trading_symbol AS symbol,
    b.instrument_type,
    b.side,
    b.quantity,
    b.market_rate AS entry_price,
    NULL::numeric AS exit_price,
    b.net_rate,
    b.amount,
    b.expiry_date,
    b.option_type,
    b.strike_price,
    b.trade_no AS external_trade_ref,
    b.payload
FROM client_data.attached_broker_transactions b
JOIN client_data.attached_transaction_files f ON f.id = b.source_file_id
UNION ALL
SELECT
    'option_log' AS source_type,
    f.file_name,
    o.client_code,
    NULL::text AS client_name,
    o.entry_date,
    o.exit_date,
    NULL::time AS trade_time,
    'OPTION_LOG' AS exchange,
    o.stock_ticker AS symbol,
    'option' AS instrument_type,
    o.side,
    o.contracts,
    o.option_value AS entry_price,
    o.exit_option_value AS exit_price,
    NULL::numeric AS net_rate,
    o.entry_credit_debit AS amount,
    NULL::date AS expiry_date,
    o.call_put AS option_type,
    o.strike_price,
    o.trade_id AS external_trade_ref,
    o.payload
FROM client_data.attached_option_log_transactions o
JOIN client_data.attached_transaction_files f ON f.id = o.source_file_id;

CREATE OR REPLACE VIEW client_data.v_attached_client_positions_by_symbol AS
SELECT
    client_code,
    symbol,
    instrument_type,
    coalesce(option_type, '') AS option_type,
    strike_price,
    sum(
        CASE
            WHEN upper(side) IN ('B', 'BUY') THEN quantity
            WHEN upper(side) IN ('S', 'SELL') THEN -quantity
            ELSE 0
        END
    ) AS net_quantity,
    sum(CASE WHEN upper(side) IN ('B', 'BUY') THEN quantity ELSE 0 END) AS bought_quantity,
    sum(CASE WHEN upper(side) IN ('S', 'SELL') THEN quantity ELSE 0 END) AS sold_quantity,
    min(entry_date) AS first_trade_date,
    max(coalesce(exit_date, entry_date)) AS last_trade_date,
    count(*) AS trade_rows
FROM client_data.v_attached_client_trade_ledger
WHERE symbol IS NOT NULL
GROUP BY client_code, symbol, instrument_type, coalesce(option_type, ''), strike_price
ORDER BY last_trade_date DESC, symbol;
