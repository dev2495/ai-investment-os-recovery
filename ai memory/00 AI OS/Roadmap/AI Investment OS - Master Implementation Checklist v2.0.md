# AI Investment OS - Master Implementation Checklist v2.0

Date: 2026-07-06
Canonical blueprint: [[AI Investment OS - Master Blueprint v2.0]]
Purpose: track the real build toward the complete AI hedge fund OS.

Status legend:

- `[x]` done and verified in the current stack.
- `[~]` partially implemented or prototype exists.
- `[ ]` not yet implemented.

Rule: do not mark `[x]` unless there is database, code, UI, report, or runtime evidence.

## 0. Constitution And Governance

- [x] Create canonical master blueprint v1.0.
- [x] Create canonical master blueprint v2.0.
- [x] Create master implementation checklist v2.0.
- [ ] Define document versioning policy.
- [ ] Define decision log template.
- [ ] Define committee minutes template.
- [ ] Define sprint acceptance criteria template.
- [ ] Define evidence standard for marking checklist items done.

## 1. Foundation Runtime

- [x] Runtime workspace on external SSD.
- [x] Postgres warehouse.
- [x] Redis.
- [x] Qdrant.
- [x] API server.
- [x] AI Office dashboard.
- [x] Obsidian vault indexed.
- [~] Qdrant index available, but embedding fallback must be hardened.
- [~] Ollama/local model manually available, background reliability still open.
- [ ] Backup job.
- [ ] Restore test.
- [ ] Source freshness monitor.
- [ ] Worker daemon health dashboard.
- [ ] Cost and model route ledger.

## 2. Core Data Spine

- [x] Client/account/holding foundation imported.
- [x] Broker transaction import routing foundation.
- [x] Manual trade and paper trade capture foundation.
- [x] Post-trade review foundation.
- [~] Mark-to-market foundation exists for provided holdings.
- [ ] Full p2cursor extraction for all client buy/sell dates.
- [ ] Full algo trading DB import.
- [ ] Live Zerodha/Dhan read-only connector.
- [ ] Crypto/commodity exchange read-only connector.
- [ ] Full daily/intraday OHLCV ingestion.
- [ ] Reconciliation dashboard across old systems, broker statements, and manual entries.

## 3. Multi-Book Portfolio Brain

- [x] Create investment book schema.
- [x] Seed default books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges.
- [x] Create position purpose taxonomy.
- [x] Map existing linked holdings to default Long-Term book.
- [x] Create book exposure views.
- [x] Create cross-book conflict view.
- [x] Add dashboard panels for book exposure and symbol rollup.
- [x] Add missing purpose/exit criteria flags.
- [x] Prove one symbol can carry opposing book exposures in smoke test.
- [~] Portfolio Intelligence Engine exists as foundation, still needs full analytics.
- [ ] Add hedge ratio.
- [ ] Add capital used by book.
- [ ] Add risk budget used by book.
- [ ] Add current trades by book into symbol intelligence.
- [ ] Add thesis links, catalyst links, quant signal links, and trading setup links.
- [ ] Add latest news/filings/tasks/committee notes into symbol intelligence.

## 4. Long-Term Investing Office

- [ ] Company thesis table.
- [ ] Thesis version history.
- [ ] Moat scorecard.
- [ ] Management scorecard.
- [ ] Capital allocation scorecard.
- [ ] Financial quality scorecard.
- [ ] Valuation model registry.
- [ ] Reverse DCF module.
- [ ] Bull/base/bear scenarios.
- [ ] Long-term Monte Carlo module.
- [ ] Thesis killer table.
- [ ] Exit criteria table linked to holdings.
- [ ] Quarterly review schedule.
- [ ] Sell discipline checklist.
- [ ] Long-Term Office dashboard.
- [ ] Long-Term Portfolio Manager agent.
- [ ] Company Analyst agent.
- [ ] Industry Analyst agent.
- [ ] Management Analyst agent.
- [ ] Financial Statement Analyst agent.
- [ ] Valuation Agent.
- [ ] Forensic Accounting Agent.
- [ ] Filings and Transcript Analyst.
- [ ] Bear Case Agent.
- [ ] Quality Score Agent.
- [ ] Portfolio Fit Agent.
- [ ] Long-Term Investment Committee workflow.
- [ ] Long-Term committee memo template.
- [ ] Charlie final long-term decision gate.

## 5. Tactical Investing Office

- [ ] Tactical idea table.
- [ ] Catalyst table.
- [ ] Event calendar connector.
- [ ] Tactical setup table.
- [ ] Stop/target/time-exit fields.
- [ ] Tactical risk/reward calculator.
- [ ] Long-Term overlap check.
- [ ] Options overlay support.
- [ ] Tactical dashboard.
- [ ] Tactical Portfolio Manager agent.
- [ ] Catalyst Analyst.
- [ ] Event Analyst.
- [ ] Technical Analyst.
- [ ] Macro Analyst.
- [ ] Sentiment Analyst.
- [ ] Options Overlay Agent.
- [ ] Sector Rotation Agent.
- [ ] Tactical committee workflow.

## 6. Quantitative Strategies Book

- [x] Strategy intake workflow.
- [x] Strategy candidate creation.
- [x] Paper-first activation gate.
- [x] Local deterministic OHLCV backtest runner.
- [x] Cost/slippage model foundation.
- [x] Backtest API endpoint.
- [x] Backtest dashboard action.
- [x] Persist backtest metrics and artifact path.
- [x] Model validation review after backtest.
- [x] Parameter optimizer.
- [x] Optimizer API endpoint.
- [x] Optimizer dashboard action.
- [x] Train/test split.
- [x] Walk-forward diagnostics.
- [x] Heatmap-ready sensitivity rows.
- [x] Monte Carlo/bootstrap diagnostics.
- [x] Strategy Committee review gate.
- [x] Strategy Committee memo generated to Obsidian.
- [x] Strategy Committee Secretary agent/profile/skill.
- [x] Strategy Committee human decision workflow.
- [x] Strategy Committee decision API endpoint.
- [x] Strategy Committee dashboard decision controls.
- [x] Paper-monitor approval guard blocks weak/rejected evidence.
- [ ] Deterministic strategy rule parser.
- [ ] Regime split performance.
- [ ] Factor attribution.
- [ ] Capacity/liquidity model.
- [x] Live/backtest drift monitor.
- [x] Drift monitor API endpoint.
- [x] Drift monitor dashboard panel.
- [x] Drift monitor Risk/Model Validation routing.
- [x] Paper monitor state machine.
- [x] Paper monitor start/heartbeat/stop API endpoints.
- [x] Paper monitor dashboard panel and controls.
- [x] Paper monitor safety gate requiring final committee paper approval.
- [x] Strategy kill-switch enforcement.
- [x] Strategy kill-switch API endpoint.
- [x] Strategy kill-switch dashboard controls.
- [x] Strategy kill-switch Risk/Execution Safety routing.
- [x] Limited-live approval workflow.
- [x] Limited-live approval API endpoints.
- [x] Limited-live dashboard controls.
- [x] Execution gate check ledger.
- [ ] Data Scientist agent.
- [ ] Feature Engineer agent.
- [ ] Regime Analyst agent.

## 7. Active Trading Desk

- [x] Active Trading book mapping foundation.
- [x] Manual trade entry UI with book/purpose.
- [x] Paper trade entry UI with book/purpose.
- [x] Trade setup taxonomy foundation.
- [x] Stop/target/time-exit foundation.
- [x] Post-trade review workflow.
- [ ] TradingView CDP relaunch and verified connection.
- [ ] TradingView chart open task.
- [ ] TradingView screenshot artifact capture.
- [ ] NIFTY/BANKNIFTY/VIX/options layout task.
- [ ] Straddle/strangle chart workflow.
- [ ] Options chain analytics.
- [ ] IV/OI dashboard.
- [ ] Payoff chart.
- [ ] Trade journal learning loop.
- [ ] Overnight risk check.
- [x] Execution safety gate.
- [ ] Active Trading dashboard.
- [ ] Options Analyst agent.
- [ ] Futures Analyst agent.
- [ ] Market Microstructure Agent.
- [ ] Volatility Agent.

## 8. Cash, Treasury, And Hedges

- [x] Cash/Treasury and Hedges books seeded.
- [ ] Cash balance ingestion.
- [ ] Margin/collateral tracking.
- [ ] Cash deployment dashboard.
- [ ] Hedge table.
- [ ] Hedge intent field.
- [ ] Hedge ratio calculator.
- [ ] Hedge cost/carry monitor.
- [ ] Hedge expiry and unwind alerts.
- [ ] Cash/Treasury Agent.

## 9. Capital Allocation Office

- [~] Capital allocation tables partially represented in book foundation.
- [ ] Target capital by book.
- [ ] Actual capital by book.
- [ ] Risk budget by book.
- [ ] Max drawdown by book.
- [ ] Max leverage by book.
- [ ] Max single-name/sector/factor exposure.
- [ ] Book P&L attribution.
- [ ] Capital drift view.
- [ ] Capital increase/decrease recommendation.
- [ ] Cross-book conflict review workflow.
- [ ] Capital Allocation Officer agent.
- [ ] Performance Attribution Agent.
- [ ] Book Controller agent.

## 10. Risk Office

- [~] Risk events and committee gating exist for strategy foundation.
- [ ] Risk limits table.
- [ ] Risk limit dashboard.
- [ ] VaR.
- [ ] Expected shortfall.
- [ ] Stress tests.
- [ ] Scenario analysis.
- [ ] Portfolio Monte Carlo paths.
- [ ] Factor exposure.
- [ ] Correlation clusters.
- [ ] Liquidity risk.
- [ ] Gap risk.
- [ ] Options Greeks.
- [ ] Strategy correlation.
- [ ] Client suitability flags.
- [ ] Risk Committee workflow.
- [ ] Risk override logging.
- [ ] Risk block state.
- [ ] Kill Switch Agent.
- [ ] Compliance Agent.
- [ ] Audit Agent.

## 11. Research Factory

- [~] Research notes and output inventory exist.
- [ ] Idea intake schema.
- [ ] Research pipeline states.
- [ ] Company research template.
- [ ] Industry note template.
- [ ] Filing note template.
- [ ] Special situations memo template.
- [ ] Valuation memo template.
- [ ] Bear case template.
- [ ] Investment committee memo template.
- [ ] NSE filing collector.
- [ ] BSE filing collector.
- [ ] Filing PDF parser.
- [ ] Annual report parser.
- [ ] Transcript ingestion.
- [ ] News collector.
- [ ] Twitter/X/social triage.
- [ ] Corporate action classifier.
- [ ] Special situation detector.
- [ ] Research Factory dashboard.
- [ ] Special Situations Agent production workflow.

## 12. Agent Office And Communication

- [x] Agent roster.
- [x] Agent departments.
- [x] Agent skills.
- [x] Agent model routes.
- [x] Agent characters.
- [x] Agent mailboxes.
- [x] Agent messages.
- [x] Message to task to inbox to worker-run flow.
- [x] Worker notes written to Obsidian.
- [x] Strategy Committee Secretary added.
- [~] First live office floor panel.
- [ ] Department rooms.
- [ ] Employee avatars.
- [ ] Agent hover cards.
- [ ] Current task per employee.
- [ ] Mailbox unread badges.
- [ ] Active run badges.
- [ ] Model route badges.
- [ ] Tool-use badges.
- [ ] Message arrows between agents.
- [ ] Committee room view.
- [ ] Approval board.
- [ ] Click-through agent profile pages.
- [ ] Click-through task/output pages.

## 13. MCP And External Adapters

- [x] MCP architecture planned.
- [x] Postgres/API tools foundation.
- [x] Obsidian writeback foundation.
- [x] Qdrant retrieval foundation.
- [x] Fincept local component installed.
- [x] Fincept skill registry added.
- [x] Vibe skill registry added.
- [~] TradingView MCP/controller planned, CDP unavailable until relaunch.
- [ ] Browser MCP production workflow.
- [ ] TradingView production controller.
- [ ] NSE/BSE scraper MCP.
- [ ] News scraper MCP.
- [ ] Document/PDF scraper MCP.
- [ ] OpenAlgo read-only adapter.
- [ ] Fincept tool catalog bridge.
- [ ] Fincept report-builder bridge.
- [ ] Fincept news/RSS bridge.
- [ ] Fincept options/IV/OI bridge.
- [ ] Vibe read-only adapter.
- [ ] Crypto/commodity exchange adapter.

## 14. Dashboards

- [x] AI Office dashboard shell.
- [x] Strategy Arsenal Queue panel.
- [x] Strategy Committee Gate panel.
- [x] Book exposure panels.
- [x] Broker import and reconciliation panels.
- [~] Quant Lab dashboard foundation.
- [ ] Command Center v2.
- [ ] Portfolio Intelligence dashboard v2.
- [ ] Client Folios dashboard.
- [ ] Symbol Intelligence page.
- [ ] Long-Term Office dashboard.
- [ ] Tactical Office dashboard.
- [ ] Trading Desk dashboard.
- [ ] Risk Center dashboard.
- [ ] Research Factory dashboard.
- [ ] Reports dashboard.
- [ ] System Health dashboard.

## 15. Reports And Briefs

- [x] Full stack PDF report.
- [x] Multi-book portfolio brain report.
- [x] Strategy Committee memo.
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
- [ ] Special situation memo.
- [ ] Trade journal review.

## 16. Model And Cost Controls

- [~] Local model plan defined.
- [~] Ollama installed/manual, reliability open.
- [ ] Confirm installed local models and sizes.
- [ ] Decide daily driver model per machine.
- [ ] Add model availability monitor.
- [ ] Add model route cost ledger.
- [ ] Add per-agent cost caps.
- [ ] Add cloud escalation approval.
- [ ] Add fallback routes.
- [ ] Add retrieval-first prompt policy.
- [ ] Add daily model cost report.

## 17. Production Safety

- [x] Live execution disabled in current foundation.
- [x] Strategy activation gated behind backtest/validation/approval.
- [x] Broker execution policy.
- [x] Human approval gate for limited-live requests.
- [x] Risk approval gate for limited-live requests.
- [x] Execution safety gate.
- [x] Global kill switch.
- [x] Per-strategy kill switch.
- [x] Max notional rule for limited-live gate.
- [x] Per-order broker approval gate.
- [x] Max daily loss rules.
- [x] Max leverage rules.
- [x] Dry-run/paper mode default.
- [x] Full execution audit dashboard.

## 18. Immediate Next Sprint Candidates

Recommended order:

- [ ] Harden local model/Ollama background reliability.
- [x] Build human decision workflow for pending Strategy Committee memo.
- [ ] Build TradingView CDP/controller connection once browser is launched correctly.
- [ ] Build Long-Term company thesis schema and memo template.
- [ ] Build NSE/BSE filing collector and Special Situations workflow.
- [ ] Build active paper-monitor state machine for approved strategies.
- [ ] Build Command Center v2 dashboard around Charlie inbox, approvals, risks, and today changes.

## 19. Platform Definition Of Done

- [ ] Devarsh can talk to Charlie and trigger auditable workflows.
- [ ] Jarvis can retrieve memory, call tools, write approved outputs, and update dashboards.
- [ ] All clients/accounts/holdings/trades are in one warehouse.
- [ ] All positions have book, purpose, owner, thesis, horizon, and exit criteria.
- [ ] Portfolio Intelligence shows gross/net/book/strategy/risk exposure.
- [ ] Research Factory can ingest filings/news and create committee-ready notes.
- [ ] Quant Lab can intake, backtest, optimize, validate, and committee-review strategies.
- [ ] Trading Desk can log manual/paper trades and control TradingView tasks.
- [ ] Risk Office can block unsafe actions.
- [ ] Capital Allocation can allocate budget across books.
- [ ] AI Office GUI shows live agent work, messages, approvals, reports, and dashboard widgets.
- [ ] Obsidian and Qdrant provide durable memory and retrieval.
- [ ] Local model runtime is reliable and cloud spend is controlled.
- [ ] Broker execution remains blocked unless all safety gates pass.
