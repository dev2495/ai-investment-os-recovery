# Event Symbol Quote Refresh

Date: 2026-07-06
Status: done and verified
Owner: Data Steward / Event Arbitrage Analyst

## What Was Added

- Added event quote refresh worker:
  - `_ai_os_runtime/scripts/refresh_event_quotes.py`
- Added tool registry entry:
  - `ai_os_refresh_event_quotes`
- Added API route:
  - `POST /api/research/special-situations/refresh-quotes`
- Added dashboard control:
  - `Refresh event quotes` button inside Special Situation Spread Checks.
- Connected the workflow to:
  - `market.price_quotes`
  - `market.v_latest_price_quotes`
  - `core.data_source_checks`
  - `research.v_special_situation_memos`

## Real Verification Case

Real event:

- Symbol: `ROLEXRINGS`
- Event: buyback
- Memo id: `1`
- Offer price: `180`
- Source endpoint: `https://scanner.tradingview.com/india/scan`

Real quote refresh:

- Quote source: `tradingview_scanner_quotes`
- Provider: `TradingView`
- Latest quote id: `92`
- Price: `140.05`
- Quote timestamp: `2026-07-06T06:18:23.419039+00:00`
- Source check status: `ok`
- Rows seen: `1`
- Missing symbols: none

Real spread after quote refresh:

- Spread check id: `5`
- Status: `tracked`
- Target price: `180`
- Market price: `140.05`
- Gross spread: `28.525526597643697%`
- Days to close: `9`
- Annualized spread: `1156.8685786822166%`
- Data quality flags: none

The annualized spread is mechanically high because the extracted closing date is near. It should be treated as an event-arbitrage metric, not as a standalone recommendation.

## Guardrails

- No fake or seed quote was used.
- The refresh worker only stores returned TradingView scanner rows.
- Missing symbols are recorded in `core.data_source_checks.sample_payload`.
- Spread checks keep `trade_allowed = false` and `client_recommendation_allowed = false` in scenario payload.
- This does not authorize trade execution.

## Verification Evidence

- `python3 -m py_compile _ai_os_runtime/scripts/refresh_event_quotes.py _ai_os_runtime/api/ai_os_api_server.py` passed.
- `npm run build` in `_ai_os_runtime/ai-office-ui` passed.
- Migration `postgres/init/053_event_quote_refresh_tool.sql` applied successfully.
- Direct script run imported one ROLEXRINGS quote.
- Live API `POST /api/research/special-situations/refresh-quotes` imported one ROLEXRINGS quote.
- Live API `POST /api/research/special-situations/spread` calculated tracked spread using quote id `92`.
- `market.v_latest_price_quotes` shows ROLEXRINGS price `140.05`.
- `core.v_recent_data_source_checks` shows TradingView event quote refresh status `ok`.
- API snapshot shows latest spread check with `status = tracked` and `issues = 0`.
- UI served successfully at `http://127.0.0.1:5177/`.

## Still Open

- Add scheduled source freshness monitor.
- Add stale-quote alerts for event symbols.
- Add acceptance-ratio scenarios and liquidity/downside checks.
- Add quote adapters beyond TradingView scanner, such as OpenAlgo/local broker read-only feeds.
- Add calendar/event reminders after Charlie chooses `monitor`.
