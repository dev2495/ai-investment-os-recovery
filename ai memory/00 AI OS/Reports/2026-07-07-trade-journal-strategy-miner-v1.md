# Trade Journal Strategy Miner v1

Generated: 2026-07-07

## Outcome

Trade journal strategy mining is now live across the AI OS foundation. The system can read real rows from `trading.trade_journals` and `trading.trade_activity_ledger`, create a mining run, create source-backed pattern rows, create strategy intakes, create generated strategy ideas, and expose the output through API, MCP, and the AI Office dashboard.

This is not a live-trading approval path. Every generated idea remains research-only and must still pass DSL translation, data-quality gate, backtest, optimizer, model validation, committee review, and paper monitoring before any capital action.

## Implemented

- Database migration: `_ai_os_runtime/postgres/init/090_trade_journal_strategy_mining_v1.sql`
- Script: `_ai_os_runtime/scripts/run_trade_journal_strategy_mining.py`
- API route: `POST /api/strategy/trade-journal-mining/run`
- API snapshot keys:
  - `trade_journal_mining_runs`
  - `trade_journal_strategy_patterns`
  - `trade_journal_idea_dashboard`
- MCP tools:
  - `ai_os_run_trade_journal_strategy_mining`
  - `ai_os_trade_journal_strategy_ideas`
- AI Office panel: `Trade Journal Strategy Miner`
- Artifact directory: `_ai_os_runtime/artifacts/trade_journal_mining/`

## Live Data Used

The current warehouse has:

| Source | Count |
| --- | ---: |
| `trading.trade_journals` | 1 |
| `trading.trade_activity_ledger` | 0 |

The mined source row is the real NIFTY short-straddle journal row from 2026-05-13 with PnL 2300. Because the sample is only one row, the system marks the idea as `thin_sample_backtest_required`.

## Verification

| Check | Result |
| --- | --- |
| SQL migration apply | Passed |
| Direct script smoke | Passed: `journal_smoke_20260707` |
| API smoke | Passed: `journal_api_smoke_20260707` |
| MCP smoke | Passed: `journal_mcp_smoke_20260707` |
| Python compile | Passed |
| React build | Passed |
| API health | Passed |
| API snapshot | Passed |
| Playwright UI smoke | Passed |

Final database counts:

| Metric | Count |
| --- | ---: |
| Mining runs | 3 |
| Pattern rows | 3 |
| Journal-mined ideas | 3 |
| Journal-mining intakes | 3 |

All generated rows have:

- `broker_order_allowed = false`
- `autonomous_live_execution_allowed = false`
- `research_gate = thin_sample_backtest_required`

## Agent Flow

1. Devarsh, Charlie, Jarvis, or the Strategy Generator triggers mining.
2. Miner reads real trade journals and trade activity ledger rows.
3. Miner groups rows by setup, timeframe, and execution mode.
4. Miner creates a strategy intake and generated idea.
5. Strategy Research Agent translates the idea into explicit rules/DSL.
6. Backtest Engineer runs data-quality and backtest checks.
7. Optimizer Agent runs robustness and parameter tests.
8. Model Validation Agent reviews leakage, overfit, costs, and sample risk.
9. Strategy Committee decides whether paper monitoring is allowed.

## Current Limitation

The miner is functional, but the data sample is thin. The next quality leap is not code; it is feeding more trade rows:

- Import old 2018-19 journals.
- Record manual trades through the manual trade tool.
- Record paper trades from strategy alerts.
- Connect live broker/TradingView alerts into `trading.trade_activity_ledger`.
- Add exit reason, stop, target, timeframe, and setup tags consistently.

## Next Recommended Slice

Build the strategy optimizer from user-defined strategy, then connect it to the existing backtest, allocation, model-validation, promotion, and journal-mined idea flow.
