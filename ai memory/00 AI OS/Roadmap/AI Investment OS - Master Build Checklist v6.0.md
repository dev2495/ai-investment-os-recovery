# AI Investment OS - Master Build Checklist v6.0

Date: 2026-07-06
Blueprint: [[AI Investment OS - Master Blueprint v6.0]]
Purpose: track the build from current foundation to full AI hedge fund operating system.

Status legend:

- `[x]` done and verified in current stack or prior evidence report.
- `[~]` partially implemented, prototype exists, or needs hardening.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without database, code, UI, report, runtime, or smoke-test evidence.

## 0. Constitution And Governance

- [x] Create master blueprint v6.0.
- [x] Create master build checklist v6.0.
- [ ] Create document versioning policy.
- [ ] Create architecture change-control policy.
- [ ] Create decision log template.
- [ ] Create committee minutes template.
- [ ] Create sprint acceptance criteria template.
- [ ] Create evidence standard for checklist completion.
- [ ] Create production data vs test data separation policy.
- [ ] Create investment disclaimer and human-control policy.
- [ ] Create source freshness standard.
- [ ] Create broker execution safety constitution.

## 1. Foundation Runtime

- [x] Runtime workspace on external SSD.
- [x] Docker available and external SSD storage enforced.
- [x] Postgres warehouse.
- [x] Redis.
- [x] Qdrant.
- [x] API server.
- [x] AI Office dashboard shell.
- [x] Obsidian vault as memory surface.
- [x] MCP server foundation.
- [x] Model endpoint registry.
- [x] Data-source connector registry.
- [x] Connector health-check dashboard.
- [x] Browser profile registry.
- [x] Browser connector link registry.
- [x] Browser session health checks.
- [x] Data-source freshness monitor.
- [x] Scheduled data-source freshness cadence.
- [~] Qdrant retrieval available; embedding reliability still needs hardening.
- [~] Local model/Ollama available; 24/7 reliability still open.
- [~] Secrets policy uses references; formal audit still open.
- [ ] Durable backup job.
- [ ] Restore test.
- [ ] Worker daemon health monitor.
- [ ] System health dashboard v2.
- [ ] Model route and cost ledger.
- [ ] Per-agent cost caps.
- [ ] Cloud escalation approval workflow.
- [ ] Runtime disaster recovery runbook.

## 2. Core Data Spine

- [x] Client/account/holding foundation imported.
- [x] Broker transaction import routing foundation.
- [x] Manual trade capture foundation.
- [x] Paper trade capture foundation.
- [x] Post-trade review foundation.
- [~] Mark-to-market foundation exists for provided holdings.
- [ ] Full p2cursor extraction for all client buy/sell dates.
- [ ] Full p2cursor reconciliation against imported broker files.
- [ ] Full algo trading DB import.
- [ ] Import historical equity curves.
- [ ] Import old strategy artifacts.
- [ ] Import old trade journals from 2018-19 onward.
- [ ] Import old Codex research outputs.
- [ ] Import old Claude/Cowork research outputs.
- [ ] Live Zerodha read-only connector.
- [ ] Live Dhan read-only connector.
- [ ] Crypto/commodity exchange read-only connector.
- [ ] Full daily OHLCV ingestion.
- [ ] Full intraday OHLCV ingestion.
- [ ] Options chain/OI/IV ingestion.
- [ ] Futures basis ingestion.
- [ ] Volatility index ingestion.
- [ ] Corporate action adjustment pipeline.
- [ ] Reconciliation dashboard across broker, p2cursor, old algo systems, and manual entries.
- [ ] Source lineage view for every portfolio row.
- [ ] Raw artifact store for every file import.

## 3. Multi-Book Portfolio Brain

- [x] Create investment book schema.
- [x] Seed books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges.
- [x] Create position purpose taxonomy.
- [x] Map existing client holdings to Long-Term book.
- [x] Create book exposure views.
- [x] Create cross-book conflict view.
- [x] Add dashboard panels for book exposure and symbol rollup.
- [x] Add missing purpose/exit criteria flags.
- [x] Prove opposing exposure support in rollback smoke test.
- [x] Add manual/paper trade routing into book positions.
- [~] Portfolio Intelligence Engine foundation exists; full analytics still open.
- [ ] Add hedge ratio.
- [ ] Add offset-cost calculation.
- [ ] Add capital used by book.
- [ ] Add risk budget used by book.
- [ ] Add book P&L attribution.
- [ ] Add strategy attribution.
- [x] Add current trades by book into symbol intelligence.
- [x] Add thesis links into symbol intelligence.
- [ ] Add catalyst links into symbol intelligence.
- [x] Add quant signal links into symbol intelligence.
- [ ] Add trading setup links into symbol intelligence.
- [~] Add latest news/filing/tasks/committee notes into symbol intelligence.
- [~] Build full Symbol Intelligence page.
- [x] Build Symbol Intelligence v2 warehouse/API/dashboard panel.
- [ ] Build client folio book exposure page.
- [ ] Build cross-book conflict action workflow.

## 4. Long-Term Investing Office

- [x] Company thesis schema.
- [x] Thesis version history.
- [x] Thesis killer table.
- [x] Exit criteria table linked to holdings.
- [x] Quarterly review schedule.
- [x] Long-Term Office dashboard foundation.
- [x] Long-term research packet generator.
- [x] Source-backed checklist update workflow.
- [x] Source-backed valuation update workflow.
- [x] Source-backed specialist output execution workflow.
- [x] Long-Term source acquisition request workflow.
- [x] Long-Term source satisfaction checker workflow.
- [x] Long-Term official source document registration workflow.
- [x] Long-Term source document text extraction workflow.
- [x] Source-backed structured checklist scoring workflow.
- [x] Source-backed structured scoring for core Long-Term checklist modules.
- [~] Business model checklist.
- [~] Industry structure checklist.
- [~] Moat scorecard.
- [~] Management scorecard.
- [~] Governance scorecard.
- [~] Capital allocation scorecard.
- [~] Financial statement quality scorecard.
- [~] Forensic accounting checklist.
- [~] Valuation model registry.
- [~] DCF module.
- [~] Reverse DCF module.
- [~] Sum-of-parts module.
- [~] Peer comparison module.
- [~] Historical valuation module.
- [~] Bull/base/bear scenario builder.
- [~] Expected CAGR calculator.
- [x] Long-term Monte Carlo module.
- [~] Business model analyst workflow.
- [~] Industry analyst workflow.
- [~] Moat analyst workflow.
- [~] Management analyst workflow.
- [~] Financial statement analyst workflow.
- [~] Forensic accounting workflow.
- [~] Valuation workflow with assumptions table.
- [x] Structured valuation, bear case, portfolio fit, and risk review workflows.
- [ ] Reverse DCF workflow.
- [ ] Scenario builder with bull/base/bear probabilities.
- [x] Long-term Monte Carlo simulation engine.
- [ ] Sell discipline checklist.
- [ ] Thesis drift alerts.
- [ ] Quarterly review automation.
- [x] Long-Term Portfolio Manager agent.
- [x] Company Analyst agent.
- [x] Industry Analyst agent.
- [x] Management Analyst agent.
- [x] Financial Statement Analyst agent.
- [x] Valuation Agent.
- [x] Forensic Accounting Agent.
- [x] Filings and Transcript Analyst.
- [x] Bear Case Agent.
- [~] Quality Score Agent.
- [x] Portfolio Fit Agent.
- [x] Long-Term Investment Committee workflow.
- [x] Long-Term committee memo template.
- [x] Charlie final long-term decision gate.

## 5. Tactical Investing Office

- [ ] Tactical idea schema.
- [ ] Catalyst schema.
- [ ] Event calendar connector.
- [ ] Tactical setup schema.
- [ ] Stop/target/time-exit fields.
- [ ] Tactical risk/reward calculator.
- [ ] Long-Term overlap check.
- [ ] Hedge vs independent alpha flag.
- [ ] Options overlay support.
- [ ] Sector rotation model.
- [ ] Tactical dashboard.
- [ ] Tactical Portfolio Manager agent.
- [ ] Catalyst Analyst agent.
- [ ] Event Analyst agent.
- [ ] Technical Analyst agent.
- [ ] Macro Analyst agent.
- [ ] Sentiment Analyst agent.
- [ ] Options Overlay Agent.
- [ ] Sector Rotation Agent.
- [ ] Tactical committee workflow.
- [ ] Tactical committee memo template.

## 6. Quantitative Strategies Office

- [x] Strategy intake workflow.
- [x] Strategy candidate creation.
- [x] Paper-first activation gate.
- [x] Deterministic OHLCV backtest runner.
- [x] Cost/slippage model foundation.
- [x] Backtest API endpoint.
- [x] Backtest dashboard action.
- [x] Persist backtest metrics and artifacts.
- [x] Model validation review after backtest.
- [x] Parameter optimizer.
- [x] Optimizer API endpoint.
- [x] Optimizer dashboard action.
- [x] Train/test split.
- [x] Walk-forward diagnostics.
- [x] Heatmap-ready sensitivity rows.
- [x] Monte Carlo/bootstrap diagnostics.
- [x] Strategy Committee review gate.
- [x] Strategy Committee memo generation to Obsidian.
- [x] Strategy Committee Secretary agent/profile/skill.
- [x] Strategy Committee human decision workflow.
- [x] Paper-monitor approval guard.
- [x] Live/backtest drift monitor.
- [x] Paper monitor state machine.
- [x] Strategy kill-switch enforcement.
- [x] Limited-live approval workflow.
- [x] Execution gate check ledger.
- [ ] Deterministic strategy rule parser.
- [ ] User-defined strategy DSL.
- [ ] Data-quality gate before every backtest.
- [ ] Regime split performance.
- [ ] Factor attribution.
- [ ] Capacity/liquidity model.
- [ ] Strategy correlation matrix.
- [ ] Strategy portfolio optimizer.
- [ ] Portfolio-level strategy allocation.
- [ ] Probability-of-ruin metric.
- [ ] Strategy retirement workflow.
- [ ] Strategy Generator agent.
- [ ] Data Scientist agent.
- [ ] Feature Engineer agent.
- [ ] Regime Analyst agent.
- [ ] Capacity/Liquidity Analyst agent.

## 7. Active Trading Desk

- [x] Active Trading book mapping foundation.
- [x] Manual trade entry UI with book/purpose.
- [x] Paper trade entry UI with book/purpose.
- [x] Trade setup taxonomy foundation.
- [x] TradingView CDP relaunch and verified connection.
- [x] TradingView chart open workflow.
- [x] TradingView screenshot artifact capture.
- [x] TradingView action template registry.
- [x] TradingView template execution API.
- [x] TradingView template MCP tool.
- [x] Symbol Intelligence chart/snapshot action buttons.
- [x] Human-gated TradingView alert request template.
- [x] TradingView screenshot visual-quality rejection gate.
- [ ] Options payoff dashboard.
- [ ] IV/OI dashboard.
- [~] Straddle/strangle chart workflow.
- [~] Alert inbox.
- [ ] Trade journal v2.
- [ ] Post-trade review scoring.
- [ ] Overnight risk check.
- [ ] Active Trading dashboard.
- [ ] Trading Desk Agent.
- [ ] Technical Analyst agent.
- [ ] Options Analyst agent.
- [ ] Futures Analyst agent.
- [ ] Volatility Agent.
- [ ] Market Microstructure Agent.

## 8. Research Factory And Special Situations

- [x] NSE/BSE filing collector foundation.
- [x] Filing PDF extraction pipeline.
- [x] Special situation memo workflow.
- [x] Special situation terms extraction.
- [x] Special situation spread decision workflow.
- [x] Event-symbol quote refresh from TradingView scanner.
- [ ] News collector.
- [ ] Twitter/X triage collector.
- [ ] Annual report pipeline for watchlist.
- [ ] Concall transcript pipeline.
- [ ] Credit rating note pipeline.
- [ ] Corporate action classifier.
- [ ] Buyback detector.
- [ ] Demerger detector.
- [ ] Reverse merger detector.
- [ ] Delisting detector.
- [ ] Preferential issue detector.
- [ ] Rights issue detector.
- [ ] Arbitrage spread monitor.
- [ ] Research Factory dashboard.
- [ ] Research Director agent.
- [ ] Corporate Actions Analyst agent.
- [ ] Arbitrage Analyst agent.

## 9. Cash, Treasury, Hedges, Crypto, Commodities

- [ ] Cash/Treasury dashboard.
- [ ] Cash drag calculation.
- [ ] Liquid fund / cash equivalent tracking.
- [ ] Hedge position schema.
- [ ] Hedge intent field.
- [ ] Hedge ratio calculation.
- [ ] Crypto exchange read-only connector.
- [ ] BTC/ETH watchlist and trade journal.
- [ ] Gold/silver/commodity instrument registry.
- [ ] Commodity OHLCV ingestion.
- [ ] Crypto/commodity risk limits.
- [ ] Crypto/Commodity Macro book.

## 10. Capital Allocation Office

- [ ] Capital allocation schema.
- [ ] Capital budget by book.
- [ ] Risk budget by book.
- [ ] Capital drift dashboard.
- [ ] Book-level rebalance suggestions.
- [ ] Client-level allocation guardrails.
- [ ] Strategy allocation engine.
- [ ] Cross-book allocation review.
- [ ] Capital Allocation Officer agent.
- [ ] Portfolio Optimizer agent.
- [ ] Performance Attribution Analyst agent.
- [ ] Client Suitability Analyst agent.

## 11. Risk Office

- [x] Risk approval gate.
- [x] Strategy kill-switch enforcement.
- [x] Execution gate check ledger.
- [ ] Risk limits table across books/accounts/clients.
- [ ] Risk limits dashboard.
- [ ] Concentration engine.
- [ ] Liquidity risk engine.
- [ ] VaR engine.
- [ ] Expected shortfall engine.
- [ ] Stress test engine.
- [ ] Portfolio Monte Carlo paths.
- [ ] Options tail-risk model.
- [ ] Book conflict escalation.
- [ ] Risk Committee workflow.
- [ ] Risk override logging.
- [ ] Risk block state dashboard.
- [ ] Chief Risk Officer agent.
- [ ] Quant Risk Analyst agent.
- [ ] Stress Testing Agent.
- [ ] Model Risk Agent.
- [ ] Data Quality Risk Agent.

## 12. Agent Office And Communication

- [x] Agent profiles foundation.
- [x] Agent departments foundation.
- [x] Agent skills foundation.
- [x] Agent task queue foundation.
- [x] Agent inbox foundation.
- [x] Agent messages foundation.
- [x] Agent approvals foundation.
- [x] Agent run logging foundation.
- [x] Charlie profile.
- [x] Jarvis profile.
- [x] Strategy Committee Secretary added.
- [ ] Agent comments.
- [ ] Agent output artifacts registry v2.
- [ ] Per-agent tool permissions UI.
- [ ] Per-agent model route UI.
- [ ] Agent mailbox UI.
- [ ] Agent handoff threads.
- [ ] Committee room view.
- [ ] Approval board view.
- [ ] Character/personality cards.
- [ ] Agent reliability score.
- [ ] Agent productivity metrics.

## 13. MCP And External Adapters

- [x] MCP server foundation.
- [x] Obsidian/vault read-write path.
- [x] Postgres API tool path.
- [x] Browser profile registry.
- [x] Fincept local component installed.
- [x] Fincept skill registry added.
- [x] Vibe skill registry added.
- [x] TradingView CDP connection verified and chart-action executor added.
- [~] TradingView production controller.
- [~] TradingView layout/chart action API.
- [x] TradingView screenshot artifact API.
- [x] TradingView action template registry/API/MCP.
- [x] TradingView gated alert request approval path.
- [ ] Browser research runner hardening.
- [ ] Web/document scraper MCP.
- [ ] PDF/doc extraction MCP.
- [ ] Fincept tool catalog bridge.
- [ ] Fincept report-builder bridge.
- [ ] Fincept news/RSS bridge.
- [ ] Fincept options/IV/OI bridge.
- [ ] Vibe read-only adapter.
- [ ] OpenAlgo read-only bridge.

## 14. Dashboards

- [x] Command Center foundation.
- [x] Portfolio widget foundation.
- [x] Book exposure widget.
- [x] Strategy Committee Gate panel.
- [x] Data-source freshness panel.
- [x] Agent task/inbox panels.
- [~] Long-Term Office dashboard foundation.
- [~] Quant Lab dashboard foundation.
- [~] AI Office live activity foundation.
- [ ] Portfolio Intelligence dashboard v2.
- [ ] Client Folio dashboard.
- [~] Symbol Intelligence dashboard.
- [ ] Long-Term Office dashboard v2.
- [ ] Tactical Office dashboard.
- [ ] Trading Desk dashboard.
- [ ] Risk Center dashboard.
- [ ] Capital Allocation dashboard.
- [ ] Research Factory dashboard.
- [ ] News and Filings dashboard.
- [ ] Special Situations dashboard.
- [ ] Model Runtime dashboard.
- [ ] Committee Room dashboard.
- [ ] Animated AI Office v1.

## 15. Reports And Briefs

- [x] Obsidian report writeback foundation.
- [x] Strategy Committee memo foundation.
- [x] Long-Term committee memo foundation.
- [x] Special situation memo foundation.
- [x] PDF report capability proven.
- [ ] Daily market brief.
- [ ] Daily portfolio brief.
- [ ] Daily agent activity brief.
- [ ] Weekly risk report.
- [ ] Weekly research digest.
- [ ] Monthly client report.
- [ ] Company research report.
- [ ] Strategy report.
- [ ] Backtest report v2.
- [ ] Optimization report.
- [ ] Model validation report.
- [ ] Committee minutes report.
- [ ] Data-source freshness report.
- [ ] Cost report.

## 16. Model And Cost Controls

- [x] Model endpoint registry foundation.
- [x] Local model route foundation.
- [~] Ollama/local model runtime available; needs reliability hardening.
- [ ] Daily driver model selected and benchmarked.
- [ ] Embedding model reliability test.
- [ ] Per-agent model route table complete.
- [ ] Cost ledger.
- [ ] Model call cache.
- [ ] Escalation policy.
- [ ] Cloud model approval flow.
- [ ] Model quality eval set.
- [ ] Local-vs-cloud routing tests.
- [ ] Context/RAG compression policy.

## 17. Production Safety

- [x] Paper-first strategy activation gate.
- [x] Risk approval gate for limited-live requests.
- [x] Strategy kill-switch enforcement.
- [x] Execution gate check ledger.
- [ ] Broker read-only mode enforcement.
- [ ] Account mapping verification.
- [ ] Order preview object.
- [ ] Human approval before broker order.
- [ ] Emergency kill switch UI.
- [ ] Live execution audit trail.
- [ ] Secrets audit.
- [ ] Backup/restore test.
- [ ] Privacy policy for client data.
- [ ] PII redaction policy for model calls.

## 18. Immediate Next Sprint

- [ ] Verify current runtime health after v6.0 documentation.
- [x] Finish Long-Term valuation, bear case, portfolio fit, and risk review workflows to verified checklist status.
- [x] Build Long-Term Monte Carlo simulation engine.
- [~] Build Symbol Intelligence page with book/purpose/exposure/thesis/strategy/news links.
- [~] Build TradingView production chart actions.
- [ ] Build p2cursor extraction plan and first client reconciliation.
- [ ] Build data artifact/source lineage view.
- [ ] Build agent mailbox UI.
- [ ] Build Research Factory news and filing queue dashboard.
- [ ] Build Risk limits table and dashboard.

## 19. Whole-System Definition Of Done

- [ ] Devarsh can talk to Charlie and trigger auditable workflows.
- [ ] Jarvis can call approved tools, write outputs, and update dashboards.
- [ ] Every client, holding, transaction, trade, strategy, source, and report is traceable.
- [ ] Every position has book, purpose, owner, horizon, thesis/setup, and exit logic.
- [ ] Portfolio Intelligence shows gross/net/book/strategy/client/risk exposure.
- [ ] Symbol Intelligence explains why each exposure exists.
- [ ] Long-Term Office can produce complete thesis, valuation, bear case, Monte Carlo, and review memos.
- [ ] Research Factory can ingest filings/news and create special-situation ideas.
- [ ] Quant Lab can intake, backtest, optimize, validate, paper-monitor, and committee-review strategies.
- [ ] Trading Desk can log manual/paper trades and control TradingView tasks.
- [ ] Risk Office can block unsafe actions.
- [ ] Capital Allocation can allocate capital across books and detect conflicts.
- [ ] Agent Office shows real tasks, inbox, runs, model routes, and outputs.
- [ ] Reports can be generated from source-backed data.
- [ ] Live execution remains human-approved and audit-logged.
