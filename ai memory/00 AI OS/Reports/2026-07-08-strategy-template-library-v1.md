# Strategy Template Library v1

Generated: 2026-07-08

## Outcome

The AI OS now has a live strategy template library that lets Devarsh, Charlie, Jarvis, or a specialist agent create a research candidate from a controlled template instead of starting from a blank strategy prompt.

This is part of the strategy arsenal foundation. It does not allow live execution, broker orders, or autonomous deployment. Every template-created strategy is gated as paper-first research.

## Implemented

- Database migration: `_ai_os_runtime/postgres/init/108_strategy_template_library_v1.sql`
- Tables:
  - `strategy.strategy_templates`
  - `strategy.strategy_template_applications`
- Function:
  - `strategy.create_strategy_from_template(...)`
- Views:
  - `strategy.v_strategy_template_library`
  - `strategy.v_strategy_template_summary`
  - `strategy.v_strategy_template_applications`
- API snapshot keys:
  - `strategy_template_summary`
  - `strategy_template_library`
  - `strategy_template_applications`
- API route:
  - `POST /api/strategy/templates/apply`
- MCP tools:
  - `ai_os_strategy_template_library`
  - `ai_os_create_strategy_from_template`
- AI Office dashboard:
  - `Strategy Template Library` panel
  - one-click queue from template into the strategy intake/candidate pipeline
- MCP tool group:
  - `strategy_arsenal_operator`

## Template Coverage

Current active templates:

| Family | Templates |
| --- | ---: |
| Intraday and tactical equity | 5 |
| Options/event volatility | 2 |
| Crypto and commodities | 2 |
| Long-term overlay | 1 |
| Total | 10 |

Template keys:

- `intraday_momentum_5m`
- `intraday_mean_reversion_5m`
- `opening_range_breakout_5m`
- `low_volatility_trend_filter`
- `options_event_long_straddle`
- `options_iv_mean_reversion_short_straddle`
- `tactical_event_breakout`
- `crypto_breakout_1h`
- `commodity_gold_trend`
- `long_term_momentum_overlay`

## Live Smoke Result

The API smoke created a real strategy application from the live template table:

| Field | Value |
| --- | --- |
| Template | `intraday_momentum_5m` |
| Strategy | `Template Smoke Intraday Momentum` |
| Symbol | `NSE:TATASTEEL` |
| Candidate | `strategy-candidate-20260708151320705-template-smoke-intraday-momentum` |
| Activation gate | `paper_first_backtest_required` |
| Live execution allowed | `false` |

Rows created:

- Template application: 1
- Strategy intake: 1
- Generated idea: 1
- Strategy candidate: 1
- Agent task: 1
- Agent inbox message: 1

## Verification Commands

- `npm run build` in `_ai_os_runtime/ai-office-ui`: passed
- `python3 -m py_compile api/ai_os_api_server.py mcp_server/ai_os_mcp_server.py`: passed
- `bash scripts/start_ai_office_live.sh`: passed
- `curl -s http://127.0.0.1:8765/api/health`: passed
- `curl -s http://127.0.0.1:5177/`: returned the current built AI Office bundle
- `docker exec -i ai_os_postgres psql ... strategy.v_strategy_template_summary`: passed
- MCP import check confirmed:
  - `ai_os_strategy_template_library`
  - `ai_os_create_strategy_from_template`

Live template summary after smoke:

| Metric | Value |
| --- | ---: |
| active_templates | 10 |
| optimizer_ready_templates | 5 |
| research_only_templates | 5 |
| options_templates | 2 |
| crypto_commodity_templates | 2 |
| template_applications | 1 |

## Safety Position

- No broker order path was introduced.
- No autonomous live execution path was introduced.
- Every template application writes `live_execution_allowed = false`.
- Every created candidate enters the existing strategy committee/backtest/paper-first workflow.
- Options, crypto, and commodity templates are treated as research templates until connector, pricing, liquidity, and risk gates are hardened.

## Current Limits

- The template library is a v1 controlled catalog, not a full visual strategy builder.
- Options templates exist, but options chain/OI/IV/Greeks ingestion is still incomplete.
- Crypto and commodity templates exist, but exchange/commodity connectors and historical depth are still incomplete.
- Current intraday OHLCV coverage is real but too thin for institutional validation.
- Strategy correlation, capacity, portfolio optimizer, and paper/live promotion boards remain separate roadmap items.

## Next Recommended Slice

Build the Long-Term Investment Office checklist and research packet path next:

- company thesis checklist
- moat and management checklist
- valuation and downside checklist
- Monte Carlo/position sizing report
- research committee memo
- per-position open task routing

That moves the system toward the full hedge-fund operating model instead of only expanding the quant strategy lab.
