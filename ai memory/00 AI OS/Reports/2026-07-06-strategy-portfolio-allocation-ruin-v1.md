# Strategy Portfolio Allocation and Probability-of-Ruin v1

Date: 2026-07-06

## What Changed

- Added paper-only strategy portfolio allocation tables:
  - `strategy.strategy_portfolio_allocation_runs`
  - `strategy.strategy_portfolio_allocations`
- Added probability-of-ruin metrics:
  - `strategy.probability_of_ruin_metrics`
- Added read views:
  - `strategy.v_strategy_portfolio_allocation_runs`
  - `strategy.v_strategy_portfolio_allocations`
  - `strategy.v_probability_of_ruin_metrics`
- Added deterministic runner:
  - `_ai_os_runtime/scripts/run_strategy_portfolio_allocation.py`
- Added API route:
  - `POST /api/strategy/portfolio-allocation/run`
- Added MCP tools:
  - `ai_os_run_strategy_portfolio_allocation`
  - `ai_os_strategy_portfolio_allocation`
- Added dashboard surface:
  - `Strategy Portfolio Risk`
  - Run button: `Run Allocation`
  - Shows allocation run status, probability of ruin, terminal P05, target weights, notional, and risk contribution.

## Verified Runs

### Script Smoke

- Allocation key: `alloc_smoke_20260706`
- Analytics source: `qa_api_smoke_20260706`
- Capital base: `1000000`
- Max strategy weight: `0.35`
- Ruin threshold: `20%`
- Horizon: `252` bars
- Simulations: `1000`
- Result:
  - Strategy `candidate_1` weight: `0.35`
  - Strategy notional: `350000`
  - Cash weight: `0.65`
  - Portfolio probability of ruin: `0.0`
  - Terminal P05: `991543.8024623347`
  - Terminal P50: `999797.911194346`
  - Terminal P95: `1008993.465939867`
  - Max drawdown P95: `0.01043723953037945`
  - Artifact: `_ai_os_runtime/artifacts/strategy_allocations/alloc_smoke_20260706.json`

### API Smoke

- Allocation key: `alloc_api_smoke_20260706`
- API route completed successfully.
- MCP read returned:
  - 1 allocation row
  - 2 ruin rows: portfolio scope and strategy scope
- Snapshot includes:
  - `strategy_portfolio_allocation_runs`
  - `strategy_portfolio_allocations`
  - `strategy_probability_of_ruin`
  - `issues = 0`
- Artifact: `_ai_os_runtime/artifacts/strategy_allocations/alloc_api_smoke_20260706.json`

## Important Guardrails

- This is paper-only allocation.
- `live_execution_allowed = false`.
- The allocator respects max strategy weight and leaves unallocated capital as cash.
- Probability-of-ruin uses deterministic bootstrap from `strategy.strategy_return_series`.
- The current result is not investment advice and not live-trading authority.

## Quality Flags

The allocation run inherits and adds:

- `thin_return_history`
- `some_strategies_missing_passed_dsl`
- `thin_portfolio_return_history`

These flags are correct. The current return series has only about 102 bars, so ruin metrics are plumbing validation and risk-screening diagnostics, not final capital approval evidence.

## Verification

- Migration applied successfully.
- Python compile passed:
  - `run_strategy_portfolio_allocation.py`
  - `ai_os_api_server.py`
  - `ai_os_mcp_server.py`
- Frontend build passed with `npm run build`.
- Live services restarted:
  - API: `http://127.0.0.1:8765/api/health`
  - UI: `http://127.0.0.1:5177/`
- API smoke completed through `POST /api/strategy/portfolio-allocation/run`.
- MCP filtered read completed through `ai_os_strategy_portfolio_allocation`.
- Browser render check found:
  - `Strategy Portfolio Risk`
  - `Run Allocation`
  - `probability of ruin`
- View fallback fixed:
  - Portfolio row uses `portfolio`
  - Strategy row uses `candidate_1`

## Checklist Updated

- Portfolio-level strategy allocation.
- Probability-of-ruin metric.

## Remaining Work

- Strategy retirement workflow.
- Strategy Generator agent.
- Data Scientist agent.
- Feature Engineer agent.
- Regime Analyst agent.
- Capacity/Liquidity Analyst agent.
- Quant Lab dashboard v2.

