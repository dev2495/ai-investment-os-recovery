# Strategy Retirement And Quant Specialists v1

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v8.0]]
Checklist: [[AI Investment OS - Execution Checklist v8.0]]
Status: implemented and smoke verified

## What Was Built

This slice turns the Quant Lab from analytics-only into an operating workflow that can review strategies for retirement, pause, watch, or more-data states.

Built runtime assets:

- Migration: `_ai_os_runtime/postgres/init/088_strategy_retirement_quant_specialists_v1.sql`
- Script: `_ai_os_runtime/scripts/run_strategy_retirement_review.py`
- API route: `POST /api/strategy/retirement/run`
- MCP tools:
  - `ai_os_run_strategy_retirement_review`
  - `ai_os_strategy_retirement_queue`
- AI Office panel:
  - `Quant Lab v2 - Retirement & Specialists`
- UI screenshot:
  - `_ai_os_runtime/artifacts/strategy_retirement/quant_lab_v2_ui_smoke.png`
- Review artifacts:
  - `_ai_os_runtime/artifacts/strategy_retirement/retire_smoke_20260707_qa_api_smoke_20260706.json`
  - `_ai_os_runtime/artifacts/strategy_retirement/retire_api_smoke_20260707_qa_api_smoke_20260706.json`

## Database Objects

New tables:

- `strategy.strategy_retirement_reviews`
- `strategy.quant_specialist_assignments`

New views:

- `strategy.v_strategy_retirement_queue`
- `strategy.v_quant_specialist_assignments`
- `strategy.v_quant_lab_dashboard_v2`

New/updated tools in `agent.tool_registry`:

- `ai_os_run_strategy_retirement_review`
- `ai_os_strategy_retirement_queue`

New/updated skills:

- `strategy_retirement_review`
- `quant_data_science_review`
- `quant_feature_engineering_review`
- `quant_regime_review`
- `quant_capacity_liquidity_review`

## Quant Employees Made Live

The following Quant Lab employees are now active in `agent.profiles`:

- Strategy Generator
- Strategy Research Agent
- Strategy Intake Agent
- Backtest Engineer
- Optimizer Agent
- Model Validation Agent
- Data Scientist
- Feature Engineer
- Regime Analyst
- Capacity/Liquidity Analyst

New employee characters:

- Data Scientist: `Dr. Sigma`
- Feature Engineer: `Ada Features`
- Regime Analyst: `Morgan Regime`
- Capacity/Liquidity Analyst: `Casey Capacity`

Each new specialist has:

- profile,
- hierarchy row,
- mailbox,
- model assignment,
- character card,
- skill map,
- output targets,
- guardrails,
- Quant Lab office location.

## Runtime Evidence

Live script smoke:

- Command: `python3 _ai_os_runtime/scripts/run_strategy_retirement_review.py --review-key-prefix retire_smoke_20260707 --actor "Strategy Retirement Agent"`
- Result:
  - 5 strategy retirement reviews
  - 19 specialist assignments
  - source analytics run: `qa_api_smoke_20260706`
  - source allocation run: `alloc_api_smoke_20260706`
  - `live_execution_allowed: false`
  - `seed_data_allowed: false`

Live API smoke:

- Route: `POST /api/strategy/retirement/run`
- Prefix: `retire_api_smoke_20260707`
- Result:
  - 5 strategy retirement reviews
  - 19 specialist assignments

MCP smoke:

- Tool: `ai_os_strategy_retirement_queue`
- Returned:
  - retirement queue rows,
  - specialist assignment rows,
  - Quant Lab dashboard v2 rows.

Database evidence after both smoke runs:

- `strategy.v_strategy_retirement_queue`: 10 rows
- `strategy.v_quant_specialist_assignments`: 38 rows
- `strategy.v_quant_lab_dashboard_v2`: 10 rows

Action distribution:

- `needs_more_data`: 8 rows
- `watch`: 2 rows

Specialist assignments:

- Capacity/Liquidity Analyst: 8 open
- Data Scientist: 10 open
- Feature Engineer: 10 open
- Regime Analyst: 10 open

Frontend verification:

- `npm run build`: passed
- Playwright UI smoke: passed
- Verified page text:
  - `Quant Lab v2 - Retirement & Specialists`
  - `Run Retirement Review`
  - `Data Scientist`
  - `Regime Analyst`

## Decision Logic

The review script uses real strategy evidence:

- latest completed `strategy.quant_analytics_runs`,
- latest completed strategy allocation run,
- `strategy.strategy_return_series`,
- `strategy.v_strategy_dsl_readiness_summary`,
- `strategy.regime_performance_splits`,
- `strategy.capacity_liquidity_checks`,
- `strategy.probability_of_ruin_metrics`,
- `strategy.strategy_portfolio_allocations`.

Current triggers include:

- missing passed DSL,
- data quality not passed,
- thin return history,
- zero target allocation,
- negative average return,
- low win rate,
- regime underperformance,
- thin/limited liquidity,
- ruin probability above limit.

Current recommended actions:

- `keep`
- `watch`
- `needs_more_data`
- `pause_paper`

Live trading authority remains disabled.

## Checklist Items Closed

Closed in [[AI Investment OS - Execution Checklist v8.0]]:

- Strategy retirement workflow
- Strategy Generator agent
- Strategy Research Agent
- Strategy Intake Agent
- Backtesting Engineer agent
- Data Scientist agent
- Feature Engineer agent
- Optimizer Agent
- Regime Analyst agent
- Capacity/Liquidity Analyst agent
- Quant Lab dashboard v2

Still open:

- Model Validation Agent dashboard
- Strategy idea generator from trade journals
- Strategy optimizer from user-defined strategy
- Strategy paper/live promotion board

## Operational Note

Docker Desktop was offline at the start of this slice. The failed socket was:

- `unix:///Users/devarshthakkar/.docker/run/docker.sock`

Fix used:

- launched Docker Desktop,
- verified Docker server,
- confirmed containers were healthy,
- used the actual Postgres mapped port `54329`.

Current API health after recovery:

- `/api/health`: DB status `ok`
- TradingView CDP remains unavailable because port `9222` is not listening.

## Next Build Slice

The correct next slice is:

1. Model Validation Agent dashboard.
2. Strategy paper/live promotion board.
3. Strategy idea generator from trade journals.
4. Then connect those to committee decisions and risk approval gates.
