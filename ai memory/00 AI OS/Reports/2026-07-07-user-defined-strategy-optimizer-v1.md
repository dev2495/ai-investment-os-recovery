# User-Defined Strategy Optimizer v1

Generated: 2026-07-07

## Outcome

The AI OS can now take a user-defined strategy idea and run it through a safe research pipeline:

1. Create strategy intake.
2. Create generated idea and strategy candidate.
3. Generate or accept deterministic DSL.
4. Parse DSL.
5. Run real OHLCV data-quality gate.
6. Run baseline backtest.
7. Run parameter optimizer.
8. Persist workflow run, artifacts, validation rows, and inbox tasks.

This workflow does not place trades, approve broker orders, or enable autonomous live execution.

## Implemented

- Database migration: `_ai_os_runtime/postgres/init/091_user_defined_strategy_optimizer_v1.sql`
- Script: `_ai_os_runtime/scripts/run_user_defined_strategy_optimizer.py`
- API route: `POST /api/strategy/user-defined-optimizer/run`
- API snapshot key: `user_defined_optimizer_runs`
- MCP tools:
  - `ai_os_run_user_defined_strategy_optimizer`
  - `ai_os_user_defined_strategy_optimizer_runs`
- AI Office dashboard:
  - Strategy Intake template selector
  - `Queue + Optimize` action
  - `User Strategy Optimizer` run panel
- Artifact directory: `_ai_os_runtime/artifacts/user_defined_optimizer/`

## Live Data Used

The smoke runs used the real `trading.ohlcv` table.

| Timeframe | Rows | Symbols | First Timestamp | Last Timestamp |
| --- | ---: | ---: | --- | --- |
| `5m` | 1,431 | 14 | 2026-05-14 03:50 UTC | 2026-05-15 12:05 UTC |

No seed data was introduced.

## Verified Smoke Runs

| Run | Surface | Strategy | Status | Backtest | Optimization |
| --- | --- | --- | --- | ---: | ---: |
| `useropt_smoke_20260707` | direct script | User Momentum Smoke | completed | 21 | 5 |
| `useropt_api_smoke_20260707` | API | API Breakout Smoke | completed | 22 | 6 |
| `useropt_mcp_smoke_20260707` | MCP | MCP Mean Reversion Smoke | completed | 23 | 7 |

Final database counts after verification:

| Metric | Count |
| --- | ---: |
| User-defined optimizer runs | 3 |
| Completed user-defined optimizer runs | 3 |
| Backtests | 21 |
| Optimizations | 5 |

All verified workflow rows expose:

- `broker_order_allowed = false`
- `autonomous_live_execution_allowed = false`

## Verification Commands

- Python compile: passed for `run_user_defined_strategy_optimizer.py`, `ai_os_api_server.py`, and `ai_os_mcp_server.py`
- React build: passed
- API health: passed
- API workflow smoke: passed
- MCP JSON-RPC workflow smoke: passed
- API snapshot: passed
- Playwright UI smoke: found `User Strategy Optimizer`, `Queue + Optimize`, latest MCP strategy name, and `completed`

## Current Limitations

- Current OHLCV sample is real but still small: only two trading days of `5m` data.
- The default DSL generator supports template families: momentum, mean reversion, breakout, and low volatility.
- Results are research evidence only. The optimizer can identify weak ideas too; negative walk-forward or Monte Carlo results are valid outputs and should block promotion.
- Strategy promotion still requires model validation, committee review, and paper-monitor workflow.

## Next Recommended Slice

Build the strategy search/generator from external sources and internal research:

- Scan journal-mined ideas, TradingView alerts, Fincept/OpenAlgo/Vibe patterns, and research notes.
- Produce candidate strategy ideas automatically.
- Route each idea into the same user-defined optimizer pipeline.
- Keep all live trading gates closed until committee approval.
