# Model Validation Dashboard And Strategy Promotion Board v1

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v8.0]]
Checklist: [[AI Investment OS - Execution Checklist v8.0]]
Status: implemented and smoke verified

## What Was Built

This slice adds the missing Quant Lab control surface between strategy evidence and strategy promotion.

Built runtime assets:

- Migration: `_ai_os_runtime/postgres/init/089_model_validation_promotion_board_v1.sql`
- Script: `_ai_os_runtime/scripts/run_model_validation_sweep.py`
- API route: `POST /api/strategy/model-validation/sweep`
- MCP tools:
  - `ai_os_run_model_validation_sweep`
  - `ai_os_model_validation_dashboard`
  - `ai_os_strategy_promotion_board`
- AI Office panels:
  - `Model Validation Agent`
  - `Strategy Promotion Board`
- UI screenshot:
  - `_ai_os_runtime/artifacts/model_validation/model_validation_promotion_board_ui_smoke.png`
- Sweep artifacts:
  - `_ai_os_runtime/artifacts/model_validation/modelval_smoke_20260707.json`
  - `_ai_os_runtime/artifacts/model_validation/modelval_api_smoke_20260707.json`

## Database Objects

Updated table:

- `strategy.validation_reviews`
  - added nullable `validation_key`
  - added unique index `uq_validation_reviews_validation_key`

New views:

- `strategy.v_model_validation_dashboard`
- `strategy.v_strategy_promotion_board`

New/updated tools in `agent.tool_registry`:

- `ai_os_run_model_validation_sweep`
- `ai_os_model_validation_dashboard`
- `ai_os_strategy_promotion_board`

## Runtime Evidence

Script smoke:

- Command: `python3 _ai_os_runtime/scripts/run_model_validation_sweep.py --validation-key-prefix modelval_smoke_20260707 --actor "Model Validation Agent" --limit 12`
- Result:
  - 10 keyed validation reviews
  - 1 `approve_for_committee_review`
  - 9 `reject_or_retest`
  - `live_execution_allowed: false`
  - `seed_data_allowed: false`

API smoke:

- Route: `POST /api/strategy/model-validation/sweep`
- Prefix: `modelval_api_smoke_20260707`
- Result:
  - 10 keyed validation reviews
  - artifact written to `artifacts/model_validation/modelval_api_smoke_20260707.json`

MCP smoke:

- Tool: `ai_os_strategy_promotion_board`
- Returned promotion board rows with:
  - strategy names,
  - validation gate status,
  - next required action,
  - `broker_order_allowed: false`,
  - `autonomous_live_execution_allowed: false`.

Snapshot verification:

- API snapshot contains:
  - `model_validation_dashboard`
  - `strategy_promotion_board`

Frontend verification:

- `npm run build`: passed
- Playwright UI smoke: passed
- Verified page text:
  - `Model Validation Agent`
  - `Run Validation Sweep`
  - `Strategy Promotion Board`
  - `committee_review_required`

## Current Live Gate State

Model validation dashboard:

- `dsl_not_passed`: 9
- `validation_passed`: 1

Strategy promotion board:

- `dsl_not_passed`: 9
- `committee_review_required`: 1

Keyed validation reviews:

- `20` total after script and API smoke runs.

## Decision Logic

The deterministic validation sweep reads:

- `strategy.v_model_validation_dashboard`
- latest backtest rows,
- latest optimization rows,
- DSL readiness,
- data-quality status,
- retirement review action,
- optimizer warnings,
- walk-forward consistency,
- test Sharpe.

It writes:

- `strategy.validation_reviews`

Possible decisions currently include:

- `approve_for_committee_review`
- `reject_or_retest`
- `blocked_until_broader_sample`

The promotion board then derives a stage from real gates:

- backtest required,
- DSL not passed,
- data quality not passed,
- validation missing,
- validation blocking,
- committee review required,
- committee pending,
- paper monitor ready,
- paper monitor running,
- limited-live pending or blocked.

It does not grant execution authority.

## Safety State

Both of these remain false in the promotion board:

- `broker_order_allowed`
- `autonomous_live_execution_allowed`

This is intentional. The board is an operating and evidence surface, not an execution bypass.

## Checklist Items Closed

Closed in [[AI Investment OS - Execution Checklist v8.0]]:

- Model Validation Agent dashboard
- Strategy paper/live promotion board

Still open in the Quant Lab section:

- Strategy idea generator from trade journals
- Strategy optimizer from user-defined strategy

## Next Build Slice

The next correct Quant Lab slice is:

1. Strategy idea generator from old trade journals and manual trade history.
2. User-defined strategy optimizer flow that starts from Devarsh's strategy description and runs DSL, data-quality, backtest, optimizer, validation, and promotion board in sequence.
