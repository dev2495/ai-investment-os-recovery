BEGIN;

WITH known_index(symbol,exchange) AS (VALUES
    ('NIFTY 50','NSE'),('NIFTY BANK','NSE'),('NIFTY FIN SERVICE','NSE'),
    ('NIFTY MID SELECT','NSE'),('SENSEX','BSE')
)
INSERT INTO trading.symbols (symbol,exchange,instrument_type,name,currency,active)
SELECT source.symbol,source.exchange,'index',source.name,source.currency,true
FROM trading.symbols source
JOIN known_index known
  ON upper(known.symbol)=upper(source.symbol) AND upper(known.exchange)=upper(source.exchange)
WHERE source.instrument_type='equity'
ON CONFLICT (symbol,exchange,instrument_type) DO UPDATE SET
    name=coalesce(EXCLUDED.name,trading.symbols.name),active=true;

WITH known_index(symbol,exchange) AS (VALUES
    ('NIFTY 50','NSE'),('NIFTY BANK','NSE'),('NIFTY FIN SERVICE','NSE'),
    ('NIFTY MID SELECT','NSE'),('SENSEX','BSE')
)
INSERT INTO trading.ohlcv (
    ts,symbol_id,timeframe,open,high,low,close,volume,source_system_id
)
SELECT bar.ts,canonical.id,bar.timeframe,bar.open,bar.high,bar.low,bar.close,bar.volume,bar.source_system_id
FROM trading.ohlcv bar
JOIN trading.symbols source ON source.id=bar.symbol_id AND source.instrument_type='equity'
JOIN known_index known
  ON upper(known.symbol)=upper(source.symbol) AND upper(known.exchange)=upper(source.exchange)
JOIN trading.symbols canonical
  ON upper(canonical.symbol)=upper(source.symbol)
 AND upper(canonical.exchange)=upper(source.exchange)
 AND canonical.instrument_type='index'
ON CONFLICT (ts,symbol_id,timeframe) DO UPDATE SET
    open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,
    volume=EXCLUDED.volume,source_system_id=EXCLUDED.source_system_id;

WITH known_index(symbol,exchange) AS (VALUES
    ('NIFTY 50','NSE'),('NIFTY BANK','NSE'),('NIFTY FIN SERVICE','NSE'),
    ('NIFTY MID SELECT','NSE'),('SENSEX','BSE')
)
DELETE FROM trading.ohlcv bar
USING trading.symbols source, known_index known
WHERE bar.symbol_id=source.id AND source.instrument_type='equity'
  AND upper(known.symbol)=upper(source.symbol) AND upper(known.exchange)=upper(source.exchange);

WITH known_index(symbol,exchange) AS (VALUES
    ('NIFTY 50','NSE'),('NIFTY BANK','NSE'),('NIFTY FIN SERVICE','NSE'),
    ('NIFTY MID SELECT','NSE'),('SENSEX','BSE')
)
UPDATE trading.symbols source SET active=false
FROM known_index known
WHERE source.instrument_type='equity'
  AND upper(known.symbol)=upper(source.symbol) AND upper(known.exchange)=upper(source.exchange);

COMMIT;
