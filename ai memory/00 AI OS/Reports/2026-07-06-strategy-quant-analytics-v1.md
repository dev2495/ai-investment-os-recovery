# Strategy Quant Analytics v1

Date: 2026-07-06

## What Changed

- Added analytics run ledger:
  - `strategy.quant_analytics_runs`
  - `strategy.strategy_return_series`
- Added institutional strategy diagnostics:
  - `strategy.regime_performance_splits`
  - `strategy.factor_attribution`
  - `strategy.capacity_liquidity_checks`
  - `strategy.strategy_correlation_matrix`
  - `strategy.strategy_portfolio_optimizer_runs`
- Added read views:
  - `strategy.v_quant_analytics_runs`
  - `strategy.v_regime_performance_splits`
  - `strategy.v_factor_attribution`
  - `strategy.v_capacity_liquidity_checks`
  - `strategy.v_strategy_correlation_matrix`
  - `strategy.v_strategy_portfolio_optimizer_runs`
- Added deterministic runner:
  - `_ai_os_runtime/scripts/run_strategy_quant_analytics.py`
- Added API route:
  - `POST /api/strategy/quant-analytics/run`
- Added MCP tools:
  - `ai_os_run_strategy_quant_analytics`
  - `ai_os_strategy_quant_analytics`
- Added dashboard surface:
  - `Quant Analytics` panel in AI Office
  - Run button: `Run Analytics`
  - Displays latest analytics run, optimizer status, regime rows, and factor rows.

## Verified Runs

### Full Smoke

- Run key: `qa_smoke_20260706`
- Timeframe: `5m`
- Source table: `trading.ohlcv`
- Seed data allowed: `false`
- Strategies analyzed: 10
- Regime rows: 40
- Factor rows: 40
- Capacity rows: 129
- Correlation rows: 100
- Optimizer rows: 1
- Artifact: `_ai_os_runtime/artifacts/quant_analytics/qa_smoke_20260706.json`

### API Smoke

- Run key: `qa_api_smoke_20260706`
- Timeframe: `5m`
- Source table: `trading.ohlcv`
- Seed data allowed: `false`
- Strategies analyzed: 5
- Regime rows: 20
- Factor rows: 20
- Capacity rows: 59
- Correlation rows: 25
- Optimizer rows: 1
- Artifact: `_ai_os_runtime/artifacts/quant_analytics/qa_api_smoke_20260706.json`

## Quality Flags

Both runs correctly recorded:

- `thin_return_history`
- `some_strategies_missing_passed_dsl`

This is intentional. The current warehouse has real OHLCV, but the intraday test window is only around 102 return bars for the active 5m sample. The analytics layer is ready, but the current evidence is not enough to approve live strategy capital.

## Optimizer Behavior

The first portfolio optimizer is a paper-only draft allocator using inverse-volatility and Sharpe proxy scoring. It writes optimizer diagnostics and weights, but it does not authorize live orders.

Latest API smoke optimizer:

- Candidate count: 5
- Status: `draft`
- Selected weight: strategy `1` at `1.0`
- Live allocation allowed: `false`

## Verification

- Migration applied successfully.
- Python compile passed:
  - `ai_os_api_server.py`
  - `ai_os_mcp_server.py`
  - `run_strategy_quant_analytics.py`
- Frontend build passed with `npm run build`.
- Live services restarted:
  - API: `http://127.0.0.1:8765/api/health`
  - UI: `http://127.0.0.1:5177/`
- API route `POST /api/strategy/quant-analytics/run` completed successfully.
- Snapshot includes:
  - `strategy_quant_analytics_runs`
  - `strategy_regime_performance`
  - `strategy_factor_attribution`
  - `strategy_capacity_liquidity`
  - `strategy_correlation_matrix`
  - `strategy_portfolio_optimizer_runs`
  - `issues = 0`
- MCP filtered read succeeded through `ai_os_strategy_quant_analytics`.
- Browser render check confirmed the AI Office dashboard contains `Quant Analytics`, `Run Analytics`, and `Strategy DSL & Data Gate`.

## Checklist Updated

- Regime split performance.
- Factor attribution.
- Capacity/liquidity model.
- Strategy correlation matrix.
- Strategy portfolio optimizer.

## Remaining Quant Work

- Make return-series storage richer by keeping per-symbol strategy returns, not only equal-weight strategy returns.
- Add proper walk-forward windows using larger historical data.
- Add Monte Carlo/bootstrap directly to the new analytics run object.
- Replace proxy factor attribution with a real factor library once longer and broader OHLCV/fundamental data is connected.
- Add optimizer constraints for book-level exposure, strategy crowding, drawdown budget, and client mandates.

