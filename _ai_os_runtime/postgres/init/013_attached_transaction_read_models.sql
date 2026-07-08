CREATE OR REPLACE VIEW client_data.v_client_3081282_trade_timeline AS
SELECT
    source_type,
    file_name,
    client_code,
    client_name,
    entry_date,
    exit_date,
    trade_time,
    exchange,
    symbol,
    instrument_type,
    side,
    quantity,
    entry_price,
    exit_price,
    net_rate,
    amount,
    expiry_date,
    option_type,
    strike_price,
    external_trade_ref
FROM client_data.v_attached_client_trade_ledger
WHERE client_code = '3081282'
   OR client_code ILIKE '%3081282%'
ORDER BY entry_date DESC NULLS LAST, trade_time DESC NULLS LAST, symbol;

CREATE OR REPLACE VIEW client_data.v_client_3081282_symbol_dates AS
SELECT
    symbol,
    instrument_type,
    option_type,
    strike_price,
    min(entry_date) FILTER (WHERE upper(side) IN ('B', 'BUY')) AS first_buy_date,
    max(entry_date) FILTER (WHERE upper(side) IN ('B', 'BUY')) AS last_buy_date,
    min(entry_date) FILTER (WHERE upper(side) IN ('S', 'SELL')) AS first_sell_date,
    max(entry_date) FILTER (WHERE upper(side) IN ('S', 'SELL')) AS last_sell_date,
    sum(CASE WHEN upper(side) IN ('B', 'BUY') THEN quantity ELSE 0 END) AS bought_quantity,
    sum(CASE WHEN upper(side) IN ('S', 'SELL') THEN quantity ELSE 0 END) AS sold_quantity,
    sum(CASE WHEN upper(side) IN ('B', 'BUY') THEN quantity WHEN upper(side) IN ('S', 'SELL') THEN -quantity ELSE 0 END) AS net_quantity,
    count(*) AS trade_rows,
    max(entry_date) AS last_trade_date
FROM client_data.v_client_3081282_trade_timeline
WHERE symbol IS NOT NULL
GROUP BY symbol, instrument_type, option_type, strike_price
ORDER BY max(entry_date) DESC NULLS LAST, symbol;

CREATE OR REPLACE VIEW client_data.v_client_3081282_dashboard_summary AS
SELECT 'ledger_rows' AS metric, count(*)::numeric AS value FROM client_data.v_client_3081282_trade_timeline
UNION ALL SELECT 'broker_rows', count(*)::numeric FROM client_data.v_client_3081282_trade_timeline WHERE source_type = 'broker'
UNION ALL SELECT 'option_log_rows', count(*)::numeric FROM client_data.v_client_3081282_trade_timeline WHERE source_type = 'option_log'
UNION ALL SELECT 'symbols', count(DISTINCT symbol)::numeric FROM client_data.v_client_3081282_trade_timeline
UNION ALL SELECT 'gross_buy_amount', coalesce(sum(abs(amount)), 0)::numeric FROM client_data.v_client_3081282_trade_timeline WHERE upper(side) IN ('B', 'BUY')
UNION ALL SELECT 'gross_sell_amount', coalesce(sum(abs(amount)), 0)::numeric FROM client_data.v_client_3081282_trade_timeline WHERE upper(side) IN ('S', 'SELL')
UNION ALL SELECT 'open_symbol_rows', count(*)::numeric FROM client_data.v_client_3081282_symbol_dates WHERE coalesce(net_quantity, 0) <> 0;
