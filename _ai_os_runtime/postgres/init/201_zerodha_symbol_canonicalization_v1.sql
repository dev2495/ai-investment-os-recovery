BEGIN;

-- Zerodha calls cash equities EQ; the warehouse uses the stable type "equity".
-- Merge previously retained candles before retiring duplicate broker-labelled rows.
INSERT INTO trading.ohlcv (
    ts, symbol_id, timeframe, open, high, low, close, volume, source_system_id
)
SELECT bar.ts, canonical.id, bar.timeframe, bar.open, bar.high, bar.low,
       bar.close, bar.volume, bar.source_system_id
FROM trading.ohlcv bar
JOIN trading.symbols broker
  ON broker.id=bar.symbol_id AND upper(broker.instrument_type) IN ('EQ','BE','BZ','SM','ST')
JOIN trading.symbols canonical
  ON upper(canonical.symbol)=upper(broker.symbol)
 AND upper(canonical.exchange)=upper(broker.exchange)
 AND canonical.instrument_type='equity'
ON CONFLICT (ts,symbol_id,timeframe) DO UPDATE SET
    open=EXCLUDED.open,
    high=EXCLUDED.high,
    low=EXCLUDED.low,
    close=EXCLUDED.close,
    volume=EXCLUDED.volume,
    source_system_id=EXCLUDED.source_system_id;

DELETE FROM trading.ohlcv bar
USING trading.symbols broker, trading.symbols canonical
WHERE bar.symbol_id=broker.id
  AND upper(broker.instrument_type) IN ('EQ','BE','BZ','SM','ST')
  AND upper(canonical.symbol)=upper(broker.symbol)
  AND upper(canonical.exchange)=upper(broker.exchange)
  AND canonical.instrument_type='equity';

UPDATE trading.symbols broker
SET active=false
WHERE upper(broker.instrument_type) IN ('EQ','BE','BZ','SM','ST')
  AND EXISTS (
      SELECT 1 FROM trading.symbols canonical
      WHERE upper(canonical.symbol)=upper(broker.symbol)
        AND upper(canonical.exchange)=upper(broker.exchange)
        AND canonical.instrument_type='equity'
  );

COMMIT;
