# Special Situation Spread And Decision Workflow

Date: 2026-07-06
Status: foundation done and verified
Owner: Event Arbitrage Analyst / Charlie Munger

## What Was Added

- Added `research.special_situation_spread_checks`.
- Added `research.special_situation_decisions`.
- Added views:
  - `research.v_special_situation_spread_checks`
  - `research.v_latest_special_situation_spread`
  - `research.v_special_situation_decisions`
  - extended `research.v_special_situation_memos`
  - extended `research.v_special_situation_inbox`
- Added SQL decision function:
  - `research.resolve_special_situation_decision(...)`
- Added deterministic spread calculator:
  - `_ai_os_runtime/scripts/calculate_special_situation_spread.py`
- Added API routes:
  - `POST /api/research/special-situations/spread`
  - `POST /api/research/special-situations/decision`
- Added API snapshot keys:
  - `special_situation_spread_checks`
  - `special_situation_decisions`
- Added dashboard controls:
  - `Spread` button on Special Situation Memos.
  - `Monitor`, `Research`, and `Reject` decision buttons.
  - Special Situation Spread Checks panel.
  - Special Situation Decisions panel.

## Real Verification Case

Real event:

- Memo id: `1`
- Special terms id: `1`
- Symbol: `ROLEXRINGS`
- Event: `buyback`
- Offer price parsed: `180`
- Days to close parsed: `9`

Spread check:

- API route returned spread check id `2`.
- Status: `missing_market_quote`
- Target price: `180`
- Market price: null
- Data quality flag: `missing_market_quote`

This is the correct result because `market.v_latest_price_quotes` currently has no stored ROLEXRINGS quote. No fake or seed price was used.

Decision resolver:

- Tested inside a Postgres transaction with `research_more`.
- Function returned:
  - `memo_status = research_required`
  - `approval_status = approved`
  - `trade_allowed = false`
  - `client_recommendation_allowed = false`
- Transaction was rolled back.
- After rollback:
  - persisted decision count for memo `1` remained `0`
  - memo status remained `routed_for_review`
  - approval status remained `pending`

## Guardrails

- Spread checks only use extracted filing terms and stored market quotes.
- Missing quote data is recorded as a data quality flag.
- No calculation invents market price.
- Special-situation decisions never authorize live trades.
- Special-situation decisions never authorize client recommendations.
- Trade action remains a separate future approval path.

## Verification Evidence

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/scripts/calculate_special_situation_spread.py` passed.
- `npm run build` in `_ai_os_runtime/ai-office-ui` passed.
- Migration `postgres/init/052_special_situation_spread_and_decisions.sql` applied successfully.
- Direct spread calculator run on memo `1` returned `missing_market_quote`.
- Live API `POST /api/research/special-situations/spread` returned spread check id `2`.
- Live API snapshot returned:
  - `special_situation_spread_checks`
  - `special_situation_decisions`
  - `issues = 0`
- Decision route validation rejects invalid decisions.
- SQL rollback verification proved decision workflow without mutating the live ROLEXRINGS decision state.
- UI served successfully at `http://127.0.0.1:5177/`.

## Still Open

- Add live quote ingestion/freshness for ROLEXRINGS and all event symbols.
- Add acceptance-ratio scenarios for tender buybacks.
- Add downside price, liquidity, tax, and capital lockup scenarios.
- Add automatic monitor reminders for approved monitored events.
- Add full Investment Committee packet builder for special situations.
- Add separate trade-intent path if Devarsh later wants to act on an approved event.
