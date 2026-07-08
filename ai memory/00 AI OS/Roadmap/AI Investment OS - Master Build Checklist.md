# AI Investment OS - Master Build Checklist

Date: 2026-07-06
Purpose: Track implementation of the AI Investment OS master blueprint.
Canonical blueprint: [[AI Investment OS - Master Blueprint v1.0]]

Status legend:

- `[x]` done and verified
- `[ ]` not started
- `[~]` in progress or partially implemented

## 0. Current Foundation

- [x] SSD-backed runtime workspace exists.
- [x] Postgres warehouse running.
- [x] Redis running.
- [x] Qdrant running.
- [x] API health endpoint running.
- [x] AI Office dashboard running.
- [x] Obsidian memory vault connected and indexed.
- [x] Agent roster created.
- [x] Agent departments created.
- [x] Agent skill matrix created.
- [x] Agent model routing matrix created.
- [x] Agent hierarchy created.
- [x] Agent character cards created.
- [x] Agent mailboxes created.
- [x] Agent message API created.
- [x] Agent message daemon running as LaunchAgent.
- [x] Message -> task -> inbox -> worker note flow verified.
- [x] Live AI office floor first panel created.
- [x] Full stack PDF report generated and verified.
- [~] TradingView integration planned but CDP currently unavailable.
- [~] Ollama local model available manually but not reliable as background LaunchAgent.
- [~] Fincept/OpenAlgo/Vibe skill registry added; direct adapters not live.
- [x] Multi-book portfolio schema.
- [~] Portfolio Intelligence Engine.

## 1. Master Blueprint And Governance

- [x] Create canonical master blueprint v1.0.
- [x] Create master build checklist.
- [x] Add blueprint link to AI OS Master Blueprint index.
- [x] Add checklist link to roadmap index.
- [ ] Define document versioning policy.
- [ ] Define decision log format.
- [ ] Define committee minutes format.
- [ ] Define acceptance criteria for every future sprint.

## 2. Multi-Book Portfolio Schema

Goal: every position belongs to a book, purpose, owner, thesis, horizon, and exit rule.

### 2.1 Core Book Tables

- [x] Create `books` schema.
- [x] Create `books.investment_books`.
- [x] Create default books:
  - [x] Long-Term.
  - [x] Tactical.
  - [x] Quant.
  - [x] Active Trading.
  - [x] Cash/Treasury.
  - [x] Hedges.
- [x] Create `books.book_mandates`.
- [x] Create `books.book_capital_allocations`.
- [x] Create `books.book_risk_limits`.
- [x] Create `books.position_purposes`.
- [x] Create `books.book_positions`.
- [x] Create `books.position_theses`.
- [x] Create `books.exit_criteria`.
- [x] Create `books.exposure_snapshots`.
- [x] Create `books.cross_book_exposure`.
- [x] Create `books.book_conflicts`.
- [x] Create `books.book_performance`.

### 2.2 Position Purpose Taxonomy

- [x] Add Long-Term purposes:
  - [x] Core compounder.
  - [x] Quality at reasonable price.
  - [x] Dividend/income.
  - [x] Recovery thesis.
  - [x] Watchlist starter.
  - [x] Special situation long-term.
- [x] Add Tactical purposes:
  - [x] Earnings trade.
  - [x] Sector rotation.
  - [x] Swing trade.
  - [x] Event-driven.
  - [x] Hedge around core position.
  - [x] Covered call overlay.
  - [x] Cash-secured put.
- [x] Add Quant purposes:
  - [x] Momentum.
  - [x] Mean reversion.
  - [x] Factor exposure.
  - [x] Pairs trade.
  - [x] Market neutral.
  - [x] Volatility signal.
  - [x] ML signal.
  - [x] Regime signal.
- [x] Add Active Trading purposes:
  - [x] Intraday setup.
  - [x] Breakout.
  - [x] Breakdown.
  - [x] Scalping.
  - [x] Volatility trade.
  - [x] Options directional.
  - [x] Futures hedge.
  - [x] Event risk trade.

### 2.3 Migration Of Existing Positions

- [x] Map current client holdings to default Long-Term book unless explicitly marked otherwise.
- [x] Add staging table for manual book assignment.
- [x] Add UI to edit book/purpose for each holding.
- [x] Add import rule for broker transactions.
- [x] Add import rule for manual trades.
- [x] Add import rule for paper trades.
- [x] Add import rule for quant strategy trades.
- [x] Add audit log for book assignment changes.
- [x] Add validation for missing book.
- [x] Add validation for missing purpose.
- [x] Add validation for missing exit criteria.

## 3. Portfolio Intelligence Engine

Goal: one symbol can have multiple independent exposures across books.

### 3.1 Exposure Rollups

- [x] Create symbol-level book exposure view.
- [x] Create client-level book exposure view.
- [x] Create account-level book exposure view.
- [x] Create strategy-level exposure view.
- [x] Create purpose-level exposure view.
- [x] Calculate gross long.
- [x] Calculate gross short.
- [x] Calculate net exposure.
- [x] Calculate overall bias.
- [x] Calculate book bias.
- [ ] Calculate hedge ratio.
- [x] Calculate offset ratio.
- [ ] Calculate book capital used.
- [ ] Calculate book risk budget used.

### 3.2 Symbol Intelligence

- [x] Create `portfolio.v_symbol_intelligence`.
- [x] Add current holdings by book.
- [ ] Add current trades by book.
- [ ] Add long-term thesis link.
- [ ] Add tactical catalyst link.
- [ ] Add quant signal link.
- [ ] Add active trading setup link.
- [ ] Add latest news.
- [ ] Add latest filings.
- [ ] Add open tasks.
- [x] Add risk flags.
- [ ] Add committee notes.
- [ ] Add exit criteria.

### 3.3 Reliance Example Acceptance Test

- [ ] Create test fixture or real sample for one symbol across multiple books.
- [ ] Show Long-Term +20L.
- [ ] Show Quant -3L.
- [ ] Show Active Trading -2L.
- [ ] Show Tactical 0.
- [ ] Show gross long 20L.
- [ ] Show gross short 5L.
- [ ] Show net exposure 15L.
- [ ] Show overall bias net long.
- [ ] Show offset risk flag.

## 4. Long-Term Investing Office

Goal: institutional long-term thesis engine.

### 4.1 Long-Term Data Model

- [ ] Create company thesis table.
- [ ] Create thesis version history.
- [ ] Create moat scorecard.
- [ ] Create management scorecard.
- [ ] Create capital allocation scorecard.
- [ ] Create financial quality scorecard.
- [ ] Create valuation model registry.
- [ ] Create thesis killer table.
- [ ] Create quarterly review schedule.
- [ ] Create sell discipline checklist.

### 4.2 Long-Term Checks

- [ ] Business model clarity.
- [ ] Industry structure.
- [ ] Moat durability.
- [ ] ROIC sustainability.
- [ ] Revenue growth quality.
- [ ] Margin durability.
- [ ] Unit economics.
- [ ] Management quality.
- [ ] Promoter/governance risk.
- [ ] Capital allocation.
- [ ] Related-party transactions.
- [ ] Balance sheet stress.
- [ ] Cash conversion.
- [ ] Free cash flow quality.
- [ ] Accounting quality.
- [ ] Cyclicality.
- [ ] Regulatory risk.
- [ ] Disruption risk.
- [ ] Customer/supplier concentration.
- [ ] Valuation versus history.
- [ ] Valuation versus peers.
- [ ] Reverse DCF.
- [ ] Bull/base/bear scenario.
- [ ] Monte Carlo for long-term drivers.
- [ ] Thesis killers.
- [ ] Exit criteria.
- [ ] Portfolio fit.
- [ ] Opportunity cost.

### 4.3 Long-Term Agents

- [ ] Long-Term Portfolio Manager.
- [ ] Company Analyst.
- [ ] Industry Analyst.
- [ ] Management Analyst.
- [ ] Financial Statement Analyst.
- [ ] Valuation Agent.
- [ ] Forensic Accounting Agent.
- [ ] Filings and Transcript Analyst.
- [ ] Bear Case Agent.
- [ ] Quality Score Agent.
- [ ] Capital Allocation Agent.
- [ ] Portfolio Fit Agent.

### 4.4 Long-Term Committee

- [ ] Define investment committee workflow.
- [ ] Define committee memo template.
- [ ] Define vote/decision fields.
- [ ] Define reject/watch/buy/add/trim/sell states.
- [ ] Add Charlie final review.
- [ ] Add Risk challenge.
- [ ] Add Obsidian note output.

## 5. Tactical Investing Office

Goal: medium-term event/swing/catalyst book.

- [ ] Create tactical idea table.
- [ ] Create catalyst table.
- [ ] Create event calendar link.
- [ ] Create tactical trade setup table.
- [ ] Create stop/target/time-exit fields.
- [ ] Create tactical risk/reward calculator.
- [ ] Create overlap check with Long-Term book.
- [ ] Create options overlay support.
- [ ] Create tactical committee workflow.
- [ ] Add Tactical Portfolio Manager.
- [ ] Add Catalyst Analyst.
- [ ] Add Event Analyst.
- [ ] Add Technical Analyst.
- [ ] Add Macro Analyst.
- [ ] Add Options Overlay Agent.
- [ ] Add Sector Rotation Agent.

## 6. Quantitative Strategies Book

Goal: systematic strategy lab with validation.

### 6.1 Strategy Lifecycle

- [x] Strategy intake.
- [x] Strategy specification.
- [~] Data availability check.
- [x] Baseline backtest.
- [x] Cost/slippage model.
- [x] Walk-forward test.
- [x] Parameter sensitivity.
- [x] Monte Carlo/bootstrap.
- [ ] Regime split.
- [~] Drawdown analysis.
- [ ] Capacity/liquidity analysis.
- [~] Model validation.
- [x] Risk review.
- [ ] Paper trade.
- [ ] Limited live approval.
- [ ] Kill-switch rule.

### 6.1A Strategy Arsenal Intake Workflow

- [x] Create `strategy.create_strategy_arsenal_intake`.
- [x] Convert user/Charlie strategy idea into intake, generated idea, candidate, task, and inbox item.
- [x] Enforce `paper_first_backtest_required` activation gate.
- [x] Keep live execution disabled until backtest, validation, and human approval.
- [x] Expose `/api/strategy/intakes`.
- [x] Add dashboard Strategy Intake form.
- [x] Add dashboard Strategy Arsenal Queue.
- [x] Add strategy arsenal summary metrics.
- [x] Verify workflow with rolled-back database smoke test.
- [x] Add local deterministic OHLCV backtest runner.
- [x] Add strategy backtest API endpoint.
- [x] Add dashboard backtest action.
- [x] Persist backtest metrics, diagnostics, and artifact path.
- [x] Create Model Validation review after local backtest.
- [x] Add local parameter optimizer.
- [x] Add optimizer API endpoint.
- [x] Add dashboard Optimize action.
- [x] Persist optimization metrics, parameter grid, diagnostics, and artifact path.
- [x] Add simple chronological train/test split.
- [x] Add rolling multi-window walk-forward diagnostics.
- [x] Add heatmap-ready parameter sensitivity rows.
- [x] Add deterministic Monte Carlo/bootstrap diagnostics.
- [x] Route optimization result to Model Validation and Strategy Committee Secretary.
- [x] Add Strategy Committee review gate.
- [x] Link committee gate to `agent.approvals`.
- [x] Link committee gate to `risk.events`.
- [x] Add research/paper/live proposed-mode decision field.
- [x] Add strategy kill-switch rule template.
- [x] Add dashboard Strategy Committee Gate panel.
- [x] Generate Strategy Committee memo into Obsidian.
- [x] Link committee memo path/status back to committee review.
- [x] Add Strategy Committee Secretary agent profile, character, and memo skill.
- [x] Add Strategy Committee human decision workflow.
- [x] Add Strategy Committee decision API endpoint.
- [x] Add Strategy Committee dashboard decision controls.
- [x] Add safety guard blocking paper-monitor approval when evidence recommends reject/retest.
- [ ] Implement deterministic rule parser for entry/exit/risk text.
- [x] Connect candidate queue to local backtest runner.
- [x] Connect optimizer only after a baseline backtest exists.
- [x] Connect Model Validation review generation.

### 6.2 Quant Analytics

- [~] VectorBT/Backtrader runner.
- [x] Walk-forward harness.
- [x] Monte Carlo trade sequence simulator.
- [~] Parameter heatmap.
- [x] Bootstrap returns.
- [ ] Factor attribution.
- [x] Transaction cost model.
- [x] Slippage model.
- [ ] Capacity model.
- [ ] Regime model.
- [x] Live/backtest drift monitor.
- [x] Drift monitor API endpoint.
- [x] Drift monitor dashboard panel.
- [x] Drift monitor Risk/Model Validation routing.
- [x] Paper monitor state machine.
- [x] Paper monitor start/heartbeat/stop API endpoints.
- [x] Paper monitor dashboard panel and controls.
- [x] Strategy kill-switch enforcement.
- [x] Strategy kill-switch API endpoint.
- [x] Strategy kill-switch dashboard controls.
- [x] Strategy kill-switch Risk/Execution Safety routing.
- [x] Paper monitor safety gate requiring final committee paper approval.
- [x] Limited-live approval workflow.
- [x] Limited-live API endpoints.
- [x] Limited-live dashboard controls.
- [x] Execution gate check ledger.

### 6.3 Quant Agents

- [x] Strategy Generator.
- [x] Strategy Intake Agent.
- [x] Strategy Research Agent.
- [x] Backtest Engineer.
- [x] Optimizer Agent.
- [x] Model Validation Agent.
- [ ] Data Scientist.
- [ ] Feature Engineer.
- [ ] Regime Analyst.
- [x] Strategy Committee Secretary.

## 7. Active Trading Book

Goal: discretionary intraday/options/futures book with strict logging and safety.

- [x] Create active trading book schema mapping.
- [x] Create manual trade entry UI with book/purpose.
- [x] Create paper trade entry UI with book/purpose.
- [x] Create trade setup taxonomy.
- [x] Create stop/target/time-exit fields.
- [ ] Create TradingView task integration.
- [ ] Create options chain analytics.
- [ ] Create IV/OI dashboard.
- [ ] Create payoff chart.
- [ ] Create trade journal learning loop.
- [x] Create post-trade review.
- [ ] Create overnight risk check.
- [ ] Create execution safety gate.
- [ ] Create active trading dashboard.

## 8. Capital Allocation Office

Goal: central office controlling book capital and risk budgets.

- [ ] Create book capital allocation table.
- [ ] Create target capital by book.
- [ ] Create max exposure by book.
- [ ] Create max drawdown by book.
- [ ] Create max leverage by book.
- [ ] Create max single-name exposure.
- [ ] Create max sector exposure.
- [ ] Create capital drift view.
- [ ] Create book P&L attribution.
- [ ] Create capital increase/decrease recommendation.
- [ ] Create cross-book conflict review.
- [ ] Add Capital Allocation Officer agent.
- [ ] Add Book Controller agent.
- [ ] Add Cash/Treasury Agent.

## 9. Risk Engine

Goal: independent challenge and risk controls.

### 9.1 Risk Flags

- [ ] Single-name concentration.
- [ ] Sector concentration.
- [ ] Factor concentration.
- [ ] Gross exposure breach.
- [ ] Net exposure breach.
- [ ] Book risk breach.
- [ ] Strategy drawdown breach.
- [ ] Over-hedging.
- [ ] Self-offsetting trade.
- [ ] Missing thesis.
- [ ] Missing exit criteria.
- [ ] Missing approval.
- [ ] Stale price.
- [ ] Stale research.
- [ ] Client suitability flag.

### 9.2 Risk Analytics

- [ ] VaR.
- [ ] Expected shortfall.
- [ ] Stress tests.
- [ ] Scenario analysis.
- [ ] Monte Carlo portfolio paths.
- [ ] Drawdown simulation.
- [ ] Factor exposure.
- [ ] Correlation clusters.
- [ ] Liquidity risk.
- [ ] Gap risk.
- [ ] Options Greeks.
- [ ] Margin/leverage.
- [ ] Strategy correlation.
- [ ] Book attribution.

### 9.3 Risk Committees

- [ ] Define risk committee workflow.
- [ ] Define risk committee memo.
- [ ] Add risk approval states.
- [ ] Add risk override logging.
- [ ] Add risk block state.
- [ ] Add broker execution hard block until approved.

## 10. Research Factory

Goal: convert ideas, filings, news, and screens into evidence-backed decisions.

- [ ] Create idea intake schema.
- [ ] Create research pipeline states.
- [ ] Create company research note template.
- [ ] Create industry note template.
- [ ] Create filing note template.
- [ ] Create special situation memo template.
- [ ] Create valuation memo template.
- [ ] Create bear case template.
- [ ] Create committee memo template.
- [ ] Create thesis update workflow.
- [ ] Add NSE/BSE filing collector.
- [ ] Add filing PDF parser.
- [ ] Add annual report parser.
- [ ] Add transcript ingestion.
- [ ] Add news collector.
- [ ] Add social/Twitter watchlist triage.
- [ ] Add corporate action classifier.
- [ ] Add special situation detector.

## 11. MCP And External Adapters

### 11.1 TradingView

- [ ] Relaunch TradingView with remote debugging.
- [ ] Verify CDP available on port 9222.
- [ ] Build chart open task.
- [ ] Build screenshot artifact capture.
- [ ] Build option chart task.
- [ ] Build straddle chart task.
- [ ] Build indicator/chart layout task.
- [ ] Store TradingView artifacts in warehouse and Obsidian.

### 11.2 OpenAlgo

- [ ] Install/configure local OpenAlgo read-only adapter.
- [ ] Add market data API connector.
- [ ] Add historical OHLCV connector.
- [ ] Add options chain connector.
- [ ] Add indicator scanner connector.
- [ ] Add websocket stream connector.
- [ ] Keep execution connector blocked by default.
- [ ] Add execution safety approval path.

### 11.3 Fincept

- [x] Fincept local component installed.
- [x] Fincept skill registry added.
- [ ] Build Fincept tool catalog bridge.
- [ ] Build Fincept report-builder bridge.
- [ ] Build Fincept research component bridge.
- [ ] Build Fincept news/RSS component bridge.
- [ ] Build Fincept options/IV/OI component bridge.

### 11.4 Vibe-Trading

- [x] Vibe skill registry added.
- [ ] Install/configure Vibe MCP read-only adapter.
- [ ] Add research autopilot reference workflow.
- [ ] Add swarm/committee reference workflow.
- [ ] Add trade journal/shadow account learning flow.
- [ ] Add run library/reporting pattern.
- [ ] Keep any broker/execution feature disabled.

## 12. Live AI Office GUI

Goal: graphical hedge fund office with live employees and work state.

- [x] First live office floor panel.
- [ ] Department rooms.
- [ ] Employee avatars.
- [ ] Hover cards.
- [ ] Current task per employee.
- [ ] Mailbox unread badge.
- [ ] Active worker run badge.
- [ ] Model route badge.
- [ ] Tool-use badge.
- [ ] Task arrows between agents.
- [ ] Committee room view.
- [ ] Live activity feed.
- [ ] Approval board.
- [ ] Alerts board.
- [ ] Department productivity metrics.
- [ ] Click-through agent profile pages.
- [ ] Click-through task pages.
- [ ] Click-through output note pages.

## 13. Dashboards

- [ ] Command Center v2.
- [ ] Portfolio Intelligence dashboard.
- [ ] Book Exposure dashboard.
- [ ] Symbol Intelligence page.
- [ ] Long-Term Office dashboard.
- [ ] Tactical Office dashboard.
- [~] Quant Lab dashboard.
- [ ] Trading Desk dashboard.
- [ ] Risk Center dashboard.
- [ ] Research Factory dashboard.
- [ ] Client Office dashboard.
- [ ] System Health dashboard.
- [ ] Reports dashboard.

## 14. Reports

- [x] Full stack PDF report.
- [ ] Daily market brief.
- [ ] Daily portfolio brief.
- [ ] Daily agent activity brief.
- [ ] Weekly book performance report.
- [ ] Weekly research pipeline report.
- [ ] Weekly strategy lab report.
- [ ] Weekly risk report.
- [ ] Monthly client report.
- [ ] Monthly performance attribution.
- [ ] Monthly capital allocation review.
- [ ] Company research report.
- [ ] Symbol intelligence report.
- [ ] Strategy report.
- [ ] Special situation memo.
- [~] Trade journal review.

## 15. Model And Cost Controls

- [ ] Make Ollama background service reliable or choose alternate local model host.
- [ ] Confirm installed local models.
- [ ] Add model availability monitor.
- [ ] Add model route cost ledger.
- [ ] Add per-agent autonomous cost cap.
- [ ] Add cloud escalation approval.
- [ ] Add fallback route for unavailable local model.
- [ ] Add retrieval-first prompt policy.
- [ ] Add batch processing for low-priority work.
- [ ] Add daily model cost report.

## 16. Data Quality And Operations

- [ ] Add source freshness monitor.
- [ ] Add stale price monitor.
- [ ] Add stale research monitor.
- [ ] Add missing book/purpose monitor.
- [ ] Add missing exit criteria monitor.
- [ ] Add import reconciliation.
- [ ] Add backups.
- [ ] Add restore test.
- [ ] Add audit log dashboard.
- [ ] Add error dashboard.
- [ ] Add worker daemon health dashboard.
- [ ] Add Qdrant reindex schedule.
- [ ] Add Obsidian graph hygiene report.

## 17. Production Safety

- [x] Define broker execution policy.
- [x] Keep broker writes disabled until policy engine exists.
- [x] Add risk approval gate for limited-live requests.
- [x] Add execution safety gate.
- [x] Add human approval gate for limited-live requests.
- [x] Add per-strategy kill switch.
- [x] Add global kill switch.
- [x] Add max notional rule for limited-live gate.
- [x] Add per-order broker approval gate.
- [x] Add max daily loss rules.
- [x] Add max leverage rules.
- [x] Add audit trail for every execution-related action.
- [x] Add dry-run/paper mode default.

## 18. Next Immediate Sprint

Sprint objective: implement the Multi-Book Portfolio Brain.

Required tasks:

- [x] Create `032_multi_book_portfolio_brain.sql`.
- [x] Seed default books and purposes.
- [x] Create book assignment staging for existing holdings.
- [x] Assign current linked portfolio positions to Long-Term by default.
- [x] Create `books.v_symbol_book_exposure`.
- [x] Create `books.v_client_book_exposure`.
- [x] Create `books.v_cross_book_conflicts`.
- [x] Add API snapshot keys:
  - [x] `investment_books`
  - [x] `book_positions`
  - [x] `symbol_book_exposure`
  - [x] `cross_book_conflicts`
- [x] Add dashboard panels:
  - [x] Book exposure.
  - [x] Symbol rollup.
  - [x] Conflict flags.
  - [x] Missing purpose/exit criteria.
- [x] Create Obsidian report for multi-book implementation.
- [x] Run smoke test with Reliance-style multi-book example or real holding.

## 19. Definition Of Done For Next Sprint

The next sprint is done only when:

- [x] every live position can be assigned a book.
- [x] every live position can be assigned a purpose.
- [x] the dashboard shows gross/net/book exposure.
- [x] one symbol can show opposing book exposures.
- [x] cross-book conflict flags are generated.
- [x] Charlie can use the new views in a response.
- [x] output is written to Obsidian.
- [x] no seed data is displayed as live production evidence.
- [x] API snapshot has zero issues.
- [x] UI build passes.
- [x] service restart succeeds.

## 20. Trade Capture And Broker Import Sprint

Sprint objective: move from portfolio-only books to live trade capture and broker-history routing.

Required tasks:

- [x] Create `034_broker_transaction_import_router.sql`.
- [x] Create broker transaction import route table.
- [x] Create trade-book link table.
- [x] Classify attached broker transactions into candidate books.
- [x] Keep broker-import active exposure disabled by default.
- [x] Add broker import summary view.
- [x] Add broker import queue view.
- [x] Add trade-book links view.
- [x] Add API snapshot keys:
  - [x] `broker_transaction_import_summary`
  - [x] `broker_transaction_import_queue`
  - [x] `trade_book_links`
- [x] Add API endpoint to stage broker transaction routes.
- [x] Add API endpoint to promote broker transaction route into trade ledger.
- [x] Add dashboard broker import queue panel.
- [x] Add dashboard trade ticket for manual/paper trades.
- [x] Verify broker promotion in rollback without persisting smoke data.
- [x] Verify API snapshot has zero issues after adding broker/trade sections.
- [ ] Promote first real broker transaction into history after user approval.
- [ ] Record first real user manual/paper trade from dashboard.
- [x] Add broker import reconciliation report.
- [x] Add post-trade review workflow.

## 21. Broker Reconciliation And Post-Trade Review Sprint

Sprint objective: make broker imports auditable and make every manual/paper trade create a review queue.

Required tasks:

- [x] Create `035_trade_reconciliation_and_reviews.sql`.
- [x] Create broker reconciliation run table.
- [x] Create broker reconciliation issue table.
- [x] Create post-trade review table.
- [x] Create broker reconciliation function.
- [x] Create post-trade review creation function.
- [x] Add duplicate trade-reference issue detection.
- [x] Add reconciliation task/inbox creation for Data Steward.
- [x] Add post-trade task/inbox creation for Trading Desk or Strategy Generator.
- [x] Add broker reconciliation agent skill.
- [x] Add post-trade review agent skill.
- [x] Add API snapshot keys:
  - [x] `broker_reconciliation_latest`
  - [x] `broker_reconciliation_issues`
  - [x] `post_trade_reviews`
- [x] Add API endpoint to run broker reconciliation.
- [x] Add dashboard broker reconciliation panel.
- [x] Add dashboard post-trade review queue panel.
- [x] Verify post-trade review in rollback without persisting smoke data.
- [x] Verify broker reconciliation run from live broker import data.
- [x] Verify API snapshot has zero issues.
- [x] Verify UI build passes.
