# Strategy DSL and Data-Quality Gate v1

Date: 2026-07-06

## What Changed

- Added `strategy.strategy_rule_specs` for deterministic parsed strategy DSL specs.
- Added `strategy.backtest_data_quality_gates` for recorded OHLCV preflight checks.
- Added read views:
  - `strategy.v_strategy_rule_specs`
  - `strategy.v_backtest_data_quality_gates`
  - `strategy.v_strategy_dsl_readiness_summary`
- Added deterministic parser/gate runtime module:
  - `_ai_os_runtime/scripts/strategy_dsl_quality.py`
- Updated the backtest runner:
  - `_ai_os_runtime/scripts/run_strategy_backtest.py`
  - Backtests now parse/preserve DSL state and run the data-quality gate before execution.
  - A failed gate returns `blocked_data_quality` and does not create a backtest result.
- Added API routes:
  - `POST /api/strategy/dsl/parse`
  - `POST /api/strategy/data-quality/check`
  - Existing `POST /api/strategy/backtests/run` now includes mandatory gate enforcement.
- Added MCP tools:
  - `ai_os_parse_strategy_dsl`
  - `ai_os_strategy_data_quality_gate`
  - `ai_os_strategy_dsl_status`
- Added dashboard visibility in AI Office:
  - Strategy Arsenal rows now expose `Parse`, `Gate`, `Backtest`, and `Optimize`.
  - New `Strategy DSL & Data Gate` panel shows parse status, gate status, row counts, and templates.

## Verification

- Migration applied successfully after aligning with the existing `agent.tool_registry` schema.
- Python compile passed for:
  - `strategy_dsl_quality.py`
  - `run_strategy_backtest.py`
  - `ai_os_api_server.py`
  - `ai_os_mcp_server.py`
- Frontend build passed with `npm run build`.
- Live stack restarted and served:
  - API: `http://127.0.0.1:8765/api/health`
  - UI: `http://127.0.0.1:5177/`
- API snapshot includes:
  - `strategy_rule_specs`: 1 row
  - `strategy_data_quality_gates`: 8 rows
  - `strategy_dsl_readiness`: 10 rows
  - `issues`: 0
- Direct API parse returned `parse_status = passed` for `candidate_1`.
- Direct API gate returned `status = passed` for real OHLCV coverage:
  - Symbols: `NSE:NIFTY 50`, `NSE:TCS`, `NSE:TITAN`
  - Timeframe: `5m`
  - Total rows: 307
  - Minimum per-symbol rows: 102
  - Source table: `trading.ohlcv`
  - Seed data allowed: false
- Backtest enforcement verified:
  - Missing imported rules produced `blocked_data_quality`.
  - Explicit DSL plus real OHLCV produced completed backtest run `20`.
  - Backtest artifact: `_ai_os_runtime/artifacts/backtests/20260706T174900Z-candidate_1.json`
  - Validation review created: `6`
  - Inbox item created: `148`
- MCP status call returned the latest parse spec and latest passed gate through `ai_os_strategy_dsl_status`.
- Browser render check confirmed the served UI contains `Strategy DSL & Data Gate`.

## Current Limits

- DSL v1 validates and normalizes rules but does not yet execute arbitrary custom rule ASTs; the deterministic backtester still maps into approved local templates.
- The current OHLCV data window is thin: 2026-05-14 to 2026-05-15 for intraday bars. Results are pipeline proof, not tradable conclusions.
- Daily OHLCV has only 28 rows across 14 symbols and should not be used for research-grade long-horizon backtests yet.

## Checklist Updated

- Deterministic strategy rule parser.
- User-defined strategy DSL.
- Data-quality gate before every backtest.

## Next Quant Gaps

- Regime split performance.
- Factor attribution.
- Capacity/liquidity model.
- Strategy correlation matrix.
- Strategy portfolio optimizer.
- Walk-forward and Monte Carlo/bootstrap expansion beyond the current partial implementation.

