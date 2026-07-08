# Multi-Book Portfolio Brain Implementation

Date: 2026-07-06
Status: implemented foundation slice

## What Changed

- Added the `books` schema through `_ai_os_runtime/postgres/init/032_multi_book_portfolio_brain.sql`.
- Created six default books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, and Hedges.
- Added mandates, risk limits, capital-allocation defaults, purpose taxonomy, book positions, theses, exit criteria, exposure snapshots, cross-book exposure, conflicts, book performance, staging, and audit tables.
- Seeded 34 position purposes across Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, and Hedges.
- Backfilled 71 client-linked live holdings into the Long-Term book from `portfolio.v_latest_positions`.
- Left the unlinked personal account outside client portfolio decisions.
- Created live views for book positions, investment books, symbol exposure, client exposure, account exposure, strategy exposure, purpose exposure, cross-book conflicts, unbooked positions, assignment gaps, portfolio summary, and `portfolio.v_symbol_intelligence`.
- Added API snapshot sections for investment books, book positions, symbol book exposure, client/account/strategy/purpose exposure, cross-book conflicts, assignment gaps, symbol intelligence, and portfolio intelligence summary.
- Added AI Office dashboard panels for Investment Books, Symbol Intelligence By Book, Client Book Exposure, and Book Risk And Assignment Gaps.
- Updated Charlie chat context so deterministic replies can reference the Portfolio Intelligence Brain before a local LLM is plugged in.

## Verified Evidence

- `books.v_investment_books` shows 6 books, 71 Long-Term positions, 3 clients, 34 active purpose rows, and INR 23,470,281.79 gross/net exposure.
- `books.v_unbooked_positions` returns 0 client-linked unbooked holdings.
- `books.v_book_assignment_gaps` returns 213 honest gaps: 71 thesis gaps, 71 exit-criteria review gaps, and 71 review-due gaps.
- `books.v_cross_book_conflicts` currently returns 0 rows because no Quant/Tactical/Active/Hedge short exposure exists yet.
- `portfolio.v_symbol_intelligence` shows live symbol exposure by book and gap counts.
- API Python compile passed.
- React/Vite production build passed.

## Current Interpretation

All imported client holdings are now treated as Long-Term by default. This is correct for the starting state because the historical holdings were client folio holdings, not separately tagged quant/tactical/active trades. The system does not pretend the research work is complete: every migrated holding is flagged for thesis completion, reviewed exit criteria, and review scheduling.

## Open Items

- Add broker transaction routing into the correct books.
- Add book capital-used and risk-budget-used calculations against allocation limits.
- Add full long-term thesis engine, committee workflow, and research report generation for each holding.

## Update: Assignment Control And Trade Router

Status: implemented and smoke-tested

### Added

- Added `_ai_os_runtime/postgres/init/033_book_assignment_trade_router.sql`.
- Added database functions:
  - `books.default_book_for_trade`
  - `books.default_purpose_for_trade`
  - `books.route_trade_activity_to_book`
  - `books.update_book_position_assignment`
- Added `books.v_position_purpose_options` so the UI can offer only valid book/purpose combinations.
- Updated `/api/trades/manual` and `/api/trades/paper` so recorded trades route into `books.book_positions`.
- Added `/api/portfolio/book-assignments` for human book/purpose edits.
- Added AI Office dashboard control: Book Assignment Control.

### Verified

- API snapshot exposes 34 `position_purpose_options`, 6 books, 71 book positions, and 0 snapshot issues.
- Assignment endpoint smoke-tested on book position 58 without changing exposure: LIQUIDBEES remained `long_term` / `core_compounder`.
- Rolled-back opposing-exposure smoke test:
  - Inserted temporary paper Quant short on Tushit LIQUIDBEES inside a transaction.
  - Routed it through `books.route_trade_activity_to_book`.
  - `books.v_cross_book_conflicts` produced one `cross_book_offset` row with affected books `{long_term,quant}`.
  - Rolled back the transaction.
  - Confirmed `persisted_smoke_trades = 0`.

### Still Open

- The first real Quant/Tactical/Active trade should be recorded by user intent or a validated strategy, not by smoke-test seed data.
- Book capital-used and risk-budget-used calculations remain open.
- Full thesis engine and committee workflow remain open.

## Update: Strategy Arsenal Intake Workflow

Status: implemented and smoke-tested without seed pollution

### Added

- Added `_ai_os_runtime/postgres/init/036_strategy_arsenal_intake_workflow.sql`.
- Added `strategy.create_strategy_arsenal_intake`, which creates:
  - `strategy.strategy_intakes`
  - `strategy.generated_ideas`
  - `strategy.strategy_candidates`
  - `agent.tasks`
  - `agent.inbox_items`
- Added `strategy.v_strategy_arsenal_queue`.
- Added `strategy.v_strategy_arsenal_summary`.
- Added API snapshot sections:
  - `strategy_intakes`
  - `generated_strategy_ideas`
  - `strategy_arsenal_queue`
  - `strategy_arsenal_summary`
- Added API endpoint:
  - `POST /api/strategy/intakes`
- Added AI Office dashboard panels:
  - Strategy Intake
  - Strategy Arsenal Queue

### Guardrails

- Every new strategy candidate is created with `activation_gate = paper_first_backtest_required`.
- The workflow explicitly sets `live_execution_allowed = false`.
- The queued Backtest Engineer task requires rule structuring, data lineage, baseline backtest, costs, and validation before alerts or execution.
- No fake live strategy result was inserted.

### Verified

- Database migration applied successfully.
- API Python compile passed.
- React/Vite production build passed.
- Rolled-back smoke test created one temporary intake, generated idea, candidate, task, and inbox row.
- The smoke candidate appeared in `strategy.v_strategy_arsenal_queue` inside the transaction.
- The smoke candidate count returned to 0 after rollback.
- Live stack restarted at `http://127.0.0.1:5177/`.
- Health endpoint returned `ok = true`.
- Snapshot returned `issues = 0`.
- Snapshot returned:
  - `strategy_intakes = 0`
  - `generated_strategy_ideas = 0`
  - `strategy_arsenal_queue = 10`
  - `strategy_arsenal_summary = 6`

### Still Open

- Real first strategy intake should come from Devarsh or a journal/research artifact, not from a smoke test.
- The local backtest runner and optimizer now consume queued candidates, but user-defined rule parsing is still basic.
- Full multi-window walk-forward, regime split, factor attribution, capacity/liquidity, and live/backtest drift remain open.
- TradingView CDP remains unavailable until TradingView is relaunched with remote debugging on port 9222.

## Update: Local Strategy Backtest Runner

Status: implemented with one real diagnostic run

### Added

- Added `_ai_os_runtime/scripts/run_strategy_backtest.py`.
- Added a local deterministic OHLCV backtest engine using `trading.ohlcv`.
- Added strategy templates:
  - momentum
  - mean reversion
  - breakout
  - low volatility
- Added transaction cost and slippage assumptions on position changes.
- Added JSON and markdown artifact output under `_ai_os_runtime/artifacts/backtests`.
- Added API snapshot section:
  - `strategy_backtest_runs`
- Added API endpoint:
  - `POST /api/strategy/backtests/run`
- Added AI Office dashboard action:
  - Backtest button in Strategy Arsenal Queue.
- Added automatic Model Validation review creation after a local backtest.

### Verified

- Python compile passed for:
  - `_ai_os_runtime/api/ai_os_api_server.py`
  - `_ai_os_runtime/scripts/run_strategy_backtest.py`
- React/Vite production build passed.
- Dry-run backtest against real candidate `trend_following` and real `trading.ohlcv` completed without database writes.
- API-triggered real diagnostic backtest completed for strategy candidate `7` / `trend_following`.
- Stored backtest run:
  - `strategy.backtest_runs.id = 19`
  - status `completed`
  - timeframe `5m`
  - symbols tested `14`
  - bars tested `1431`
  - trades counted `202`
  - total return `-0.11050508522616387`
  - artifact `_ai_os_runtime/artifacts/backtests/20260705T215405Z-candidate_7.json`
- Created Model Validation review:
  - `strategy.validation_reviews.id = 3`
  - status `needs_review`
- Live snapshot after restart:
  - `issues = 0`
  - `strategy_backtest_runs = 17`
  - `strategy_arsenal_queue = 10`
  - `inbox = 19`

### Guardrails

- The runner writes diagnostics only; it does not create paper trades or live trades.
- Every result records `paper_first = true` and `live_execution_allowed = false`.
- Validation review remains required before any paper alert or execution promotion.

### Still Open

- This is a deterministic first runner, not yet a full VectorBT/Backtrader research harness.
- Full multi-window walk-forward, regime split, factor attribution, capacity/liquidity, and live/backtest drift remain open.
- Current OHLCV coverage is useful for pipeline proof but thin for institutional-grade conclusions.

## Update: Strategy Optimizer And Robustness Diagnostics

Status: implemented with one real diagnostic optimization

### Added

- Added `_ai_os_runtime/scripts/run_strategy_optimizer.py`.
- Added local parameter optimization for the same strategy templates as the backtest runner.
- Added rolling chronological walk-forward diagnostics:
  - multiple train/test windows
  - fold-level train metrics
  - fold-level out-of-sample metrics
  - consistency score across positive test folds
- Added heatmap-ready parameter sensitivity rows in optimizer diagnostics.
- Added deterministic bootstrap diagnostics for the best parameter return stream.
- Added optimizer guardrail:
  - a baseline backtest must exist before optimization can be persisted.
- Added API snapshot section:
  - `strategy_optimization_runs`
- Added API endpoint:
  - `POST /api/strategy/optimizations/run`
- Added AI Office dashboard action:
  - Optimize button in Strategy Arsenal Queue.
- Added AI Office dashboard panel:
  - Robustness Runs.
- Added Strategy Committee Secretary inbox routing after optimization.

### Verified

- Python compile passed for:
  - `_ai_os_runtime/api/ai_os_api_server.py`
  - `_ai_os_runtime/scripts/run_strategy_optimizer.py`
- React/Vite production build passed.
- Dry-run optimization against real candidate `trend_following` and real `trading.ohlcv` completed without database writes.
- API-triggered real diagnostic optimization completed for strategy candidate `7` / `trend_following`.
- Stored optimization run:
  - `strategy.optimization_runs.id = 4`
  - status `completed`
  - optimizer type `parameter_search_walk_forward_bootstrap`
  - best params `{"lookback": 36}`
  - walk-forward folds `3`
  - walk-forward positive test folds `0`
  - walk-forward consistency `0.0`
  - walk-forward average test Sharpe `-17.612443958635637`
  - heatmap rows `5`
  - artifact `_ai_os_runtime/artifacts/optimizations/20260705T220501Z-candidate_7.json`
- Created Model Validation review:
  - `strategy.validation_reviews.id = 5`
  - status `needs_review`
  - overfit risk `high`
- Live snapshot after restart:
  - `issues = 0`
  - `strategy_optimization_runs = 2`

### Guardrails

- The optimizer does not promote candidates to paper or live trading.
- The optimizer rejected the diagnostic result for committee purposes because the best parameter set had negative walk-forward/test Sharpe and zero positive walk-forward folds.
- The result is explicitly routed to Model Validation and Strategy Committee Secretary before any paper-monitoring decision.

### Still Open

- Parameter heatmap is represented as heatmap-ready rows, not yet a visual heatmap.
- Regime split, factor attribution, capacity/liquidity, and live/backtest drift remain open.

## Update: Strategy Committee Risk Gate

Status: implemented with one real committee gate opened

### Added

- Added `_ai_os_runtime/postgres/init/037_strategy_committee_risk_gate.sql`.
- Added `strategy.committee_reviews`.
- Added `strategy.open_strategy_committee_review`.
- Added `strategy.v_strategy_committee_queue`.
- Added committee review linkage to:
  - `strategy.optimization_runs`
  - `strategy.validation_reviews`
  - `agent.approvals`
  - `risk.events`
  - `agent.inbox_items`
- Added kill-switch template fields:
  - daily loss limit
  - max drawdown stop
  - max open positions
  - disable on data gap
  - disable on model validation reject
  - manual re-enable requirement
- Added API snapshot section:
  - `strategy_committee_queue`
- Added API endpoint:
  - `POST /api/strategy/committee/open`
- Added AI Office dashboard panel:
  - Strategy Committee Gate
- Added committee memo generator:
  - `_ai_os_runtime/scripts/generate_strategy_committee_memo.py`
- Added committee memo API endpoint:
  - `POST /api/strategy/committee/memo`
- Added committee memo dashboard action:
  - Memo button inside Strategy Committee Gate
- Added Strategy Committee Secretary as an active agent profile, character, and primary skill.

### Verified

- Migration applied successfully.
- Python compile passed for `_ai_os_runtime/api/ai_os_api_server.py`.
- React/Vite production build passed.
- Opened a real committee review for optimization run `4`.
- Stored committee review:
  - `strategy.committee_reviews.id = 1`
  - strategy `trend_following`
  - optimization run `4`
  - status `needs_review`
  - recommended decision `reject_or_retest`
  - proposed mode `research`
  - risk level `high`
  - walk-forward consistency `0.0`
- Created approval:
  - `agent.approvals.id = 2`
  - type `strategy_committee_review`
  - status `pending`
  - `live_execution_allowed = false`
- Created risk event:
  - `risk.events.id = 1`
  - scope `strategy`
  - severity `high`
  - status `open`
- Live snapshot after restart:
  - `issues = 0`
  - `strategy_committee_queue = 1`
  - `approvals = 1`
- Generated committee memo:
  - `ai memory/03 Strategies/Committee Reviews/20260705T221639Z-committee-review-1-trend_following.md`
  - memo status `generated`
  - memo best params `{"lookback": 36}`
  - memo conclusion says no paper trade, live alert, broker order, or capital allocation is authorized.
- Added Strategy Committee Secretary:
  - `agent.profiles.agent_name = Strategy Committee Secretary`
  - skill `strategy_committee_memo`
  - character `strategy_committee_secretary`

### Guardrails

- Committee gate only creates a review, approval request, risk event, and inbox item.
- It does not approve paper monitoring.
- It does not create paper trades.
- It does not enable live execution.

### Still Open

- Human decision UI can resolve the approval, but paper/live activation workflow is still intentionally blocked.
- Execution kill-switch is currently a committee rule template, not a live broker-side enforcement daemon.
- Human approval/rejection decision after memo review remains open.

## Update: Broker Import Router And Trade Ticket

Status: implemented and smoke-tested

### Added

- Added `_ai_os_runtime/postgres/init/034_broker_transaction_import_router.sql`.
- Added `books.broker_transaction_import_routes` for staged broker transaction classification.
- Added `books.trade_book_links` to connect historical/manual/paper trades to books without forcing them into active exposure.
- Added broker import functions:
  - `books.default_book_for_broker_transaction`
  - `books.default_purpose_for_broker_transaction`
  - `books.stage_broker_transaction_imports`
  - `books.promote_broker_transaction_route`
- Added broker import views:
  - `books.v_broker_transaction_import_queue`
  - `books.v_broker_transaction_import_summary`
  - `books.v_trade_book_links`
- Added API snapshot sections:
  - `broker_transaction_import_summary`
  - `broker_transaction_import_queue`
  - `trade_book_links`
- Added API endpoints:
  - `/api/broker-transactions/stage`
  - `/api/broker-transactions/promote`
- Added AI Office dashboard panels:
  - Trade Ticket for manual/paper trades with book and purpose.
  - Broker Transaction Import Queue.

### Verified

- Staged 1,696 attached broker transactions.
- Classification result:
  - 951 equity rows to Long-Term / Core Compounder history.
  - 745 option rows to Active Trading / Options Directional history.
- Confirmed no active exposure was created from broker imports by default.
- Rolled-back broker promotion smoke test:
  - Promoted one broker route into `trading.trade_activity_ledger`.
  - Created one `books.trade_book_links` row as `history_evidence`.
  - Rolled back the transaction.
  - Confirmed `persisted_smoke_trades = 0`.
- API snapshot after restart:
  - `issues = 0`
  - `broker_transaction_import_summary = 5`
  - `broker_transaction_import_queue = 100`
  - `book_positions = 71`
  - `position_purpose_options = 34`
- React/Vite production build passed.

### Still Open

- Promote the first real broker transaction into trade history after user approval.
- Record the first real user manual/paper trade from the dashboard.

## Update: Broker Reconciliation And Post-Trade Reviews

Status: implemented and smoke-tested

### Added

- Added `_ai_os_runtime/postgres/init/035_trade_reconciliation_and_reviews.sql`.
- Added broker reconciliation tables:
  - `books.broker_reconciliation_runs`
  - `books.broker_reconciliation_issues`
- Added post-trade review table:
  - `trading.post_trade_reviews`
- Added functions:
  - `books.run_broker_reconciliation`
  - `trading.ensure_post_trade_review`
- Added views:
  - `books.v_broker_reconciliation_latest`
  - `books.v_broker_reconciliation_issues`
  - `trading.v_post_trade_review_queue`
- Added agent skills:
  - `broker_import_reconciliation`
  - `post_trade_review`
- Added API snapshot sections:
  - `broker_reconciliation_latest`
  - `broker_reconciliation_issues`
  - `post_trade_reviews`
- Added `/api/broker-reconciliation/run`.
- Updated trade logging so future manual/paper trades create a post-trade review task and inbox item.
- Added dashboard panels:
  - Broker Reconciliation
  - Post-Trade Review Queue

### Verified

- Created broker reconciliation run #2 from live imported broker data.
- Reconciliation run #2 summary:
  - `total_broker_rows = 1696`
  - `staged_routes = 1696`
  - `promoted_routes = 0`
  - `unmapped_rows = 0`
  - `duplicate_trade_refs = 1`
  - `amount_mismatch_rows = 0`
- Broker reconciliation issue view shows one `duplicate_trade_reference` issue for NIFTY option trade reference `1759940`.
- Rolled-back post-trade review smoke test:
  - Inserted temporary paper trade.
  - Routed it to Active Trading / Intraday Setup.
  - Created `trading.post_trade_reviews` row.
  - Created linked task and inbox item.
  - Verified owner profile exists: `Strategy Generator`.
  - Rolled back the transaction.
  - Confirmed `persisted_smoke_trades = 0`.
- API snapshot after restart:
  - `issues = 0`
  - `broker_reconciliation_latest = 1`
  - `broker_reconciliation_issues = 1`
  - `post_trade_reviews = 0`
  - `broker_transaction_import_queue = 100`
- API Python compile passed.
- React/Vite production build passed.

### Still Open

- Promote the first real broker transaction into trade history after user approval.
- Record the first real user manual/paper trade from the dashboard.
- Add trade journal lesson extraction from completed post-trade reviews.

## Update: Strategy Committee Human Decision Workflow

Status: implemented and verified without making a real committee decision.

### Added

- Added `_ai_os_runtime/postgres/init/040_strategy_committee_decision_workflow.sql`.
- Added `strategy.committee_decisions` as the durable committee decision audit table.
- Added final decision fields to `strategy.committee_reviews`:
  - `final_decision`
  - `decision_status`
  - `paper_monitor_allowed`
  - `live_execution_allowed`
  - `decision_payload`
- Added `strategy.resolve_strategy_committee_decision`.
- Added API endpoint:
  - `POST /api/strategy/committee/decision`
- Added dashboard controls inside Strategy Committee Gate:
  - Retest
  - Research
  - Reject
  - Paper, only when the committee recommendation is `paper_monitor_candidate`

### Safety Rules

- Committee memo must be generated before a final decision.
- Paper-monitor approval is blocked unless `recommended_decision = paper_monitor_candidate`.
- Live execution remains false in every decision path.
- Paper-monitor approval creates only a `strategy.strategy_instances` row in `paper` mode with `status = ready`.
- Reject/retest/research-more decisions update the strategy gate but do not create paper/live activation.

### Verified

- Applied migration successfully:
  - `ALTER TABLE`
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API safety smoke test:
  - Tried to approve paper monitoring for committee review `1`.
  - API blocked it because `recommended_decision = reject_or_retest`.
- Rolled-back SQL smoke test:
  - `strategy.resolve_strategy_committee_decision(1, 'retest', ...)`
  - Verified it would set:
    - `review_status = retest_required`
    - `final_decision = retest`
    - `decision_status = final`
    - `approval_status = rejected`
    - `strategy_status = research`
    - `activation_gate = committee_retest_required`
    - `live_execution_allowed = false`
  - Rolled back the transaction.
- Post-rollback live state remains pending:
  - `review_status = needs_review`
  - `decision_status = pending`
  - `memo_status = generated`
  - `approval_status = pending`
  - `live_execution_allowed = false`
  - `strategy.committee_decisions` rows = `0`
- API snapshot:
  - `issues = 0`
  - `strategy_committee_queue = 1`
  - first review pending with memo generated and live execution false.

### Still Open

- Devarsh must make the real decision for committee review `1`: reject, retest, research more, or keep pending.
- Paper monitor can now start only after a real final committee paper approval.
- Limited-live approval workflow is now implemented, but live broker writes remain locked by global execution policy.

## Update: Strategy Paper Monitor State Machine

Status: implemented and verified without persisting fake paper sessions.

### Added

- Added `_ai_os_runtime/postgres/init/041_strategy_paper_monitor_state_machine.sql`.
- Added paper monitor tables:
  - `strategy.paper_monitor_sessions`
  - `strategy.paper_monitor_events`
- Added functions:
  - `strategy.start_paper_monitor`
  - `strategy.record_paper_monitor_heartbeat`
  - `strategy.stop_paper_monitor`
- Added views:
  - `strategy.v_paper_monitor_sessions`
  - `strategy.v_paper_monitor_events`
- Added API snapshot sections:
  - `strategy_paper_monitors`
  - `strategy_paper_monitor_events`
- Added API endpoints:
  - `POST /api/strategy/paper-monitor/start`
  - `POST /api/strategy/paper-monitor/heartbeat`
  - `POST /api/strategy/paper-monitor/stop`
- Added dashboard panel:
  - `Paper Monitor State`
- Added dashboard controls:
  - Start Monitor
  - Heartbeat
  - Stop

### Safety Rules

- A paper monitor cannot start until committee `final_decision = approve_paper_monitor`.
- The committee review must have `paper_monitor_allowed = true`.
- `live_execution_allowed` is constrained to false at the paper monitor session level.
- Paper monitor start/heartbeat/stop all preserve `live_execution_allowed = false`.
- Live broker execution remains outside this workflow and still requires a separate future approval system.

### Verified

- Applied migration successfully:
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Rolled-back SQL smoke test:
  - Temporarily set review `1` to `paper_monitor_candidate`.
  - Approved paper monitor inside transaction.
  - Started paper monitor.
  - Recorded heartbeat with `signal_count = 2`.
  - Stopped paper monitor.
  - Verified session state:
    - `status = stopped`
    - `heartbeat_status = stopped`
    - `live_execution_allowed = false`
    - `total_events = 3`
    - `heartbeat_events = 1`
  - Rolled back the transaction.
- Post-rollback live state:
  - `strategy.paper_monitor_sessions = 0`
  - `strategy.paper_monitor_events = 0`
  - committee review `1` still pending
  - `paper_monitor_allowed = false`
  - `live_execution_allowed = false`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API safety smoke test:
  - Tried to start paper monitor for committee review `1`.
  - API blocked it because final committee decision is not `approve_paper_monitor`.
- API snapshot:
  - `issues = 0`
  - `strategy_paper_monitors = 0`
  - `strategy_paper_monitor_events = 0`
  - committee review `1` remains pending with live execution false.

### Still Open

- Devarsh must make a real committee decision before any real paper monitor session can start.
- Live/backtest drift monitor is now implemented and verified through rolled-back smoke tests.
- Strategy kill-switch enforcement is now implemented and verified.
- Limited-live approval workflow is now implemented, with broker writes still blocked by default.

## Update: Live/Backtest Drift Monitor

Status: implemented and verified without persisting fake paper-monitor data.

### Added

- Added `_ai_os_runtime/postgres/init/042_strategy_live_backtest_drift_monitor.sql`.
- Added drift check table:
  - `strategy.drift_checks`
- Added function:
  - `strategy.evaluate_paper_backtest_drift`
- Added view:
  - `strategy.v_drift_monitor_checks`
- Added API snapshot section:
  - `strategy_drift_checks`
- Added API endpoint:
  - `POST /api/strategy/drift/evaluate`
- Added dashboard panel:
  - `Live / Backtest Drift`
- Added `Drift` action to each paper monitor session.

### Behavior

- Compares paper monitor metrics against latest available optimization/backtest baseline.
- Uses available metrics defensively:
  - Sharpe
  - total return
  - P&L
  - max drawdown
  - heartbeat count
  - stale heartbeat state
- Returns `insufficient_data` when paper history or baseline metrics are too thin.
- Creates `risk.events` and `agent.inbox_items` for warning/breach drift.
- Routes warning-level drift to Model Validation.
- Routes breach-level drift to Risk Agent.
- Keeps `live_execution_allowed = false` on every drift check.

### Verified

- Applied migration successfully:
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Rolled-back drift smoke test:
  - Temporarily made committee review `1` paper-monitor eligible.
  - Approved paper monitor inside transaction.
  - Started paper monitor.
  - Recorded paper heartbeat with weak metrics:
    - `total_return = -0.25`
    - `max_drawdown = -0.05`
    - `sharpe = -5`
    - `signal_count = 3`
  - Ran `strategy.evaluate_paper_backtest_drift`.
  - Drift result:
    - `drift_level = breach`
    - `check_status = completed`
    - findings:
      - Paper return materially below baseline.
      - Paper drawdown breached committee kill-switch threshold.
    - Risk event created inside transaction.
    - Inbox item created inside transaction.
    - `live_execution_allowed = false`
  - Rolled back the transaction.
- Post-rollback live state:
  - `strategy.paper_monitor_sessions = 0`
  - `strategy.paper_monitor_events = 0`
  - `strategy.drift_checks = 0`
  - drift risk events = `0`
  - committee review `1` still pending
  - `paper_monitor_allowed = false`
  - `live_execution_allowed = false`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API snapshot:
  - `issues = 0`
  - `strategy_paper_monitors = 0`
  - `strategy_drift_checks = 0`
  - committee review `1` remains pending with live execution false.
- API negative test:
  - `POST /api/strategy/drift/evaluate` with nonexistent session id correctly returns an error.

### Still Open

- Real drift checks require a real approved paper monitor session.
- Limited-live approval workflow is now implemented, with broker writes still blocked by default.

## Update: Strategy Kill-Switch Enforcement

Status: implemented and verified without persisting fake paper-monitor, drift, or kill-switch data.

### Added

- Added `_ai_os_runtime/postgres/init/043_strategy_kill_switch_enforcement.sql`.
- Added kill-switch audit table:
  - `strategy.kill_switch_events`
- Added function:
  - `strategy.enforce_strategy_kill_switch`
- Added view:
  - `strategy.v_kill_switch_events`
- Added API snapshot section:
  - `strategy_kill_switch_events`
- Added API endpoint:
  - `POST /api/strategy/kill-switch/enforce`
- Added dashboard controls:
  - `Kill` action on paper monitor sessions.
  - `Kill` action on warning/breach drift checks.
  - `Strategy Kill Switches` event panel.

### Behavior

- Enforces paper-monitor stop and marks the session `killed`.
- Marks the strategy instance `killed`.
- Marks the strategy candidate `blocked`.
- Sets activation gate to `kill_switch_enforced`.
- Requires separate re-approval before any future reactivation.
- Creates a critical `risk.events` row.
- Creates an `agent.inbox_items` row for `Execution Safety Agent`.
- Preserves the hard guard that `live_execution_allowed = false`.

### Verified

- Applied migration successfully:
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Researched and fixed rollback smoke-test CTE issue:
  - PostgreSQL executes sibling CTEs with the same snapshot, so a CTE cannot reliably read table effects from another sibling CTE.
  - Replaced the smoke script with sequential statements and a temp table to mirror real API call order.
- Rolled-back kill-switch smoke test:
  - Temporarily made committee review `1` paper-monitor eligible.
  - Approved paper monitor inside transaction.
  - Started paper monitor.
  - Recorded weak paper heartbeat:
    - `total_return = -0.25`
    - `max_drawdown = -0.10`
    - `sharpe = -3.0`
    - `signal_count = 3`
  - Ran drift evaluation.
  - Drift result:
    - `drift_level = breach`
    - `check_status = completed`
  - Enforced kill switch from drift check.
  - Inside transaction:
    - paper monitor `status = killed`
    - heartbeat `status = stopped`
    - strategy `status = blocked`
    - activation gate `kill_switch_enforced`
    - validation status `kill_switch_review_required`
    - kill-switch event count `1`
    - risk event count `1`
    - inbox item count `1`
    - `live_execution_allowed = false`
  - Rolled back the transaction.
- Post-rollback live state:
  - `strategy.paper_monitor_sessions = 0`
  - `strategy.drift_checks = 0`
  - `strategy.kill_switch_events = 0`
  - committee review `1` remains pending
  - `paper_monitor_allowed = false`
  - `live_execution_allowed = false`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API snapshot:
  - `issues = 0`
  - `strategy_paper_monitors = 0`
  - `strategy_drift_checks = 0`
  - `strategy_kill_switch_events = 0`
  - seed data disabled
- API negative test:
  - `POST /api/strategy/kill-switch/enforce` with nonexistent session id correctly returns an error.

### Still Open

- Real kill-switch use requires a real paper monitor session or drift check.
- Per-order broker approval, daily-loss enforcement, and leverage enforcement are now implemented. Real broker adapters remain read-only/planned.

## Update: Global Execution Safety and Limited-Live Gate

Status: implemented and verified without persisting fake limited-live requests, global kill-switch events, or execution-gate checks.

### Added

- Added `_ai_os_runtime/postgres/init/044_execution_safety_global_and_limited_live.sql`.
- Added global execution state:
  - `trading.execution_control_state`
- Added global kill-switch audit:
  - `trading.global_kill_switch_events`
- Added limited-live request ledger:
  - `trading.limited_live_requests`
- Added execution gate audit ledger:
  - `trading.execution_gate_checks`
- Added functions:
  - `trading.engage_global_kill_switch`
  - `trading.request_limited_live_approval`
  - `trading.sync_limited_live_request_approval`
  - `trading.evaluate_execution_gate`
- Added views:
  - `trading.v_execution_control_state`
  - `trading.v_global_kill_switch_events`
  - `trading.v_limited_live_requests`
  - `trading.v_execution_gate_checks`
- Added API snapshot sections:
  - `execution_control`
  - `global_kill_switch_events`
  - `limited_live_requests`
  - `execution_gate_checks`
- Added API endpoints:
  - `POST /api/execution/global-kill-switch/engage`
  - `POST /api/execution/limited-live/request`
  - `POST /api/execution/limited-live/sync`
  - `POST /api/execution/gate/evaluate`
- Added dashboard controls:
  - `Live Req` action on paper monitor sessions.
  - `Execution Safety` panel.
  - `Engage Global Lock` action.
  - limited-live `Sync` and `Gate` actions.

### Behavior

- Global execution defaults to locked:
  - `global_execution_locked = true`
  - `broker_execution_policy = read_only_blocked`
  - `limited_live_allowed = false`
  - `live_broker_writes_allowed = false`
- Limited-live requests create:
  - an `agent.approvals` row owned by `Risk Agent`
  - a `trading.limited_live_requests` row
  - an `agent.inbox_items` row for `Execution Safety Agent`
- Approval alone does not enable broker writes.
- Syncing an approved limited-live request keeps it `approved_but_global_locked` while global execution remains locked.
- Gate checks block when any required safety condition fails.
- Max notional is enforced inside the limited-live gate.
- Every new execution safety write keeps `live_execution_allowed = false` unless a future global policy explicitly unlocks broker writes.

### Verified

- Applied migration successfully:
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Rolled-back execution safety smoke test:
  - Engaged global kill switch inside transaction.
  - Created limited-live request for `RELIANCE`.
  - Approved the linked `agent.approvals` row inside transaction.
  - Synced limited-live request.
  - Sync result:
    - `request_status = approved_but_global_locked`
    - `approval_status = approved`
    - `broker_execution_policy = read_only_blocked`
    - `global_execution_locked = true`
    - `live_execution_allowed = false`
  - Evaluated execution gate.
  - Gate result:
    - `gate_status = blocked`
    - block reasons:
      - `global_execution_locked`
      - `live_broker_writes_disabled`
      - `broker_policy_not_limited_live_approved`
      - `limited_live_request_not_active`
    - `live_execution_allowed = false`
  - Rolled back the transaction.
- Post-rollback live state:
  - rolled-back global kill-switch events = `0`
  - rolled-back limited-live requests = `0`
  - rolled-back execution-gate checks = `0`
  - `global_execution_locked = true`
  - `broker_execution_policy = read_only_blocked`
  - `limited_live_allowed = false`
  - `live_broker_writes_allowed = false`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API snapshot:
  - `issues = 0`
  - `global_kill_switch_events = 0`
  - `limited_live_requests = 0`
  - `execution_gate_checks = 0`
  - `live_broker_writes_allowed = false`
  - seed data disabled
- API negative test:
  - `POST /api/execution/limited-live/sync` with nonexistent request id correctly returns an error.

### Still Open

- Per-order broker approval, daily-loss, leverage, and order audit dashboard are now implemented.
- Real broker adapters remain read-only/planned.

## Update: Per-Order Broker Approval and Pre-Trade Risk Gate

Status: implemented and verified without persisting fake order intents, risk checks, limited-live requests, execution-gate checks, or daily-loss trades.

### Added

- Added `_ai_os_runtime/postgres/init/045_order_intent_pretrade_risk_gate.sql`.
- Added order intent ledger:
  - `trading.order_intents`
- Added order risk check ledger:
  - `trading.order_risk_checks`
- Added functions:
  - `trading.create_order_intent`
  - `trading.evaluate_order_intent_risk`
- Added views:
  - `trading.v_order_intents`
  - `trading.v_order_risk_checks`
- Added API snapshot sections:
  - `order_intents`
  - `order_risk_checks`
- Added API endpoints:
  - `POST /api/execution/order-intents/create`
  - `POST /api/execution/order-intents/evaluate-risk`
- Added dashboard controls:
  - `Order` action on limited-live requests.
  - `Risk` action on order intents.
  - Recent order-intent and order-risk audit rows in the `Execution Safety` panel.

### Behavior

- Every potential broker order must first become an order intent.
- Every order intent creates a separate `agent.approvals` row of type `broker_order_intent`.
- Order intent approval alone does not place or allow a broker order.
- The order risk gate checks:
  - per-order approval status
  - linked limited-live request status
  - global execution policy
  - max notional
  - max daily loss
  - book mandate max leverage
  - account equity snapshot availability for leverage calculation
- The order risk gate writes an audit row every time.
- Broker order placement remains disabled:
  - `broker_order_allowed = false`
  - `live_execution_allowed = false`
  - no broker adapter call exists in this slice.

### Verified

- Applied migration successfully:
  - `CREATE TABLE`
  - `CREATE FUNCTION`
  - `CREATE VIEW`
- Backend compile passed:
  - `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- Frontend production build passed:
  - `npm run build`
- Rolled-back order-intent smoke test:
  - Temporarily unlocked global execution inside transaction to prove downstream gates.
  - Created limited-live request for `RELIANCE`.
  - Approved limited-live approval inside transaction.
  - Synced request to `limited_live_approved`.
  - Inserted rolled-back daily-loss trade:
    - `realized_pnl = -6000`
    - `max_daily_loss = 5000`
  - Created order intent:
    - `symbol = RELIANCE`
    - `book_key = active_trading`
    - `notional = 10000`
    - `estimated_loss = 1000`
  - First risk check before per-order approval blocked with:
    - `per_order_approval_not_approved`
    - `max_daily_loss_breached`
    - `leverage_equity_snapshot_missing`
  - Approved per-order approval inside transaction.
  - Second risk check blocked with:
    - `max_daily_loss_breached`
    - `leverage_equity_snapshot_missing`
  - Active trading mandate leverage limit was read:
    - `max_leverage = 2`
  - Order intent ended:
    - `status = blocked_by_risk`
    - `gate_status = blocked`
    - `broker_order_allowed = false`
    - `live_execution_allowed = false`
  - Rolled back the transaction.
- Post-rollback live state:
  - rolled-back order intents = `0`
  - rolled-back order risk checks = `0`
  - rolled-back daily-loss trade = `0`
  - `global_execution_locked = true`
  - `broker_execution_policy = read_only_blocked`
  - `limited_live_allowed = false`
  - `live_broker_writes_allowed = false`
- Restarted AI OS services:
  - `http://127.0.0.1:8765/api/health`
  - `http://127.0.0.1:5177/`
- API snapshot:
  - `issues = 0`
  - `order_intents = 0`
  - `order_risk_checks = 0`
  - `execution_gate_checks = 0`
  - `limited_live_requests = 0`
  - `live_broker_writes_allowed = false`
  - seed data disabled
- API negative test:
  - `POST /api/execution/order-intents/evaluate-risk` with nonexistent order id correctly returns an error.

### Still Open

- Real broker adapters remain read-only/planned.
- TradingView CDP remains unavailable until TradingView is relaunched with remote debugging.
- Real order placement must remain blocked until broker adapter review, credentials policy, notification policy, and production audit review are complete.
