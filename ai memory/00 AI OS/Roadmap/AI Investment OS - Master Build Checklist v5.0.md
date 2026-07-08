# AI Investment OS - Master Build Checklist v5.0

Date: 2026-07-06
Blueprint: [[AI Investment OS - Master Blueprint v5.0]]
Purpose: track the complete build from current foundation to full AI hedge fund operating system.

Status legend:

- `[x]` done and verified in the current stack.
- `[~]` partially implemented or prototype exists.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without database, code, UI, report, runtime, or smoke-test evidence.

## 0. Constitution And Governance

- [x] Create master blueprint v1.0.
- [x] Create master blueprint v2.0.
- [x] Create final master blueprint v3.0.
- [x] Create institutional master blueprint v4.0.
- [x] Create master blueprint v5.0.
- [x] Create institutional build checklist v4.0.
- [x] Create master build checklist v5.0.
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
- [ ] Add current trades by book into symbol intelligence.
- [ ] Add thesis links into symbol intelligence.
- [ ] Add catalyst links into symbol intelligence.
- [ ] Add quant signal links into symbol intelligence.
- [ ] Add trading setup links into symbol intelligence.
- [ ] Add latest news/filing/tasks/committee notes into symbol intelligence.
- [ ] Build full Symbol Intelligence page.
- [ ] Build client folio book exposure page.
- [ ] Build cross-book conflict action workflow.

## 4. Long-Term Investing Office

- [x] Company thesis schema.
- [x] Thesis version history.
- [x] Thesis killer table.
- [x] Exit criteria table linked to holdings.
- [x] Quarterly review schedule.
- [x] Long-Term Office dashboard foundation.
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
- [~] Long-term Monte Carlo module.
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
- [~] Business model analyst workflow.
- [~] Industry analyst workflow.
- [~] Moat analyst workflow.
- [~] Management analyst workflow.
- [~] Financial statement analyst workflow.
- [~] Forensic accounting workflow.
- [~] Valuation workflow with assumptions table.
- [ ] Reverse DCF workflow.
- [ ] Scenario builder with bull/base/bear probabilities.
- [ ] Long-term Monte Carlo simulation engine.
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
- [ ] Data Scientist agent.
- [ ] Feature Engineer agent.
- [ ] Regime Analyst agent.
- [ ] Capacity/Liquidity Analyst agent.

## 7. Active Trading Desk

- [x] Active Trading book mapping foundation.
- [x] Manual trade entry UI with book/purpose.
- [x] Paper trade entry UI with book/purpose.
- [x] Trade setup taxonomy foundation.
- [x] Stop/target/time-exit foundation.
- [x] Post-trade review workflow.
- [x] Execution safety gate foundation.
- [x] TradingView CDP relaunch and verified connection.
- [ ] TradingView chart open workflow.
- [ ] TradingView screenshot artifact capture.
- [ ] NIFTY/BANKNIFTY/VIX/options layout task.
- [ ] Straddle/strangle chart workflow.
- [ ] Options chain analytics.
- [ ] IV/OI dashboard.
- [ ] Payoff chart.
- [ ] Trade journal learning loop.
- [ ] Overnight risk check.
- [ ] Active Trading dashboard.
- [ ] Technical Analyst agent.
- [ ] Options Analyst agent.
- [ ] Futures Analyst agent.
- [ ] Volatility Agent.
- [ ] Market Microstructure Agent.
- [ ] Trade Journal Coach.

## 8. Cash, Treasury, Hedges, Crypto, Commodities

- [x] Cash/Treasury book seeded.
- [x] Hedges book seeded.
- [ ] Cash balance ingestion.
- [ ] Margin/collateral tracking.
- [ ] Cash deployment dashboard.
- [ ] Treasury yield options.
- [ ] Hedge table.
- [ ] Hedge intent field.
- [ ] Hedge ratio calculator.
- [ ] Hedge cost/carry monitor.
- [ ] Hedge expiry and unwind alerts.
- [ ] Crypto exchange read-only connector.
- [ ] Commodity instrument registry.
- [ ] Gold/silver price ingestion.
- [ ] BTC/ETH price ingestion.
- [ ] Crypto/commodity strategy book rules.
- [ ] Cash/Treasury Agent.
- [ ] Hedge Manager Agent.
- [ ] Margin Analyst.
- [ ] Liquidity Analyst.

## 9. Capital Allocation Office

- [~] Capital allocation tables partially represented in book foundation.
- [ ] Target capital by book.
- [ ] Actual capital by book.
- [ ] Risk budget by book.
- [ ] Max drawdown by book.
- [ ] Max leverage by book.
- [ ] Max single-name exposure.
- [ ] Max sector exposure.
- [ ] Max factor exposure.
- [ ] Book P&L attribution.
- [ ] Capital drift view.
- [ ] Opportunity ranking.
- [ ] Capital increase/decrease recommendation.
- [ ] Cross-book conflict review workflow.
- [ ] Portfolio rebalancing workflow.
- [ ] Capital Allocation Officer agent.
- [ ] Performance Attribution Agent.
- [ ] Book Controller agent.
- [ ] Client Suitability Agent.
- [ ] Rebalancing Agent.

## 10. Risk Office

- [x] Strategy gating risk foundation.
- [x] Global kill switch.
- [x] Per-strategy kill switch.
- [x] Execution safety gate.
- [x] Human approval gate.
- [x] Risk approval gate.
- [x] Per-order broker approval gate.
- [x] Max notional rule.
- [x] Max daily loss rule.
- [x] Max leverage rule.
- [ ] Risk limits table across books/accounts/clients.
- [ ] Risk limits dashboard.
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
- [ ] Risk block state dashboard.
- [ ] Chief Risk Officer agent.
- [ ] Quant Risk Analyst agent.
- [ ] Stress Testing Agent.
- [ ] Compliance Agent.
- [ ] Audit Agent.
- [ ] Kill Switch Agent.
- [ ] Model Risk Agent.
- [ ] Data Quality Risk Agent.

## 11. Research Factory

- [~] Research notes and output inventory exist.
- [x] NSE filing collector.
- [x] BSE filing collector.
- [x] Filing PDF parser.
- [x] Special situations memo template.
- [x] Structured special-situation terms extraction.
- [x] Special-situation memo generator and Charlie review routing.
- [x] Special-situation decision resolver with no-trade guardrail.
- [x] Real quote-only spread check foundation.
- [x] Event-symbol quote refresh from TradingView scanner.
- [~] Corporate action classifier.
- [~] Merger/demerger/reverse merger detector.
- [~] Buyback/delisting/rights/preferential issue detector.
- [~] Arbitrage spread tracker.
- [~] Research Factory dashboard.
- [ ] Idea intake schema.
- [ ] Research pipeline states.
- [ ] Company research template.
- [ ] Industry note template.
- [ ] Filing note template.
- [ ] Valuation memo template.
- [ ] Bear case template.
- [ ] Investment committee memo template.
- [ ] Annual report parser.
- [ ] Transcript ingestion.
- [ ] News collector.
- [ ] Twitter/X/social triage.
- [ ] Broker report ingestion.
- [ ] Research Director agent.
- [ ] News Analyst agent.
- [ ] Special Situations Analyst agent.
- [ ] Corporate Actions Analyst agent.
- [ ] Arbitrage Analyst agent.
- [ ] Research Librarian agent.

## 12. Agent Office And Communication

- [x] Agent roster.
- [x] Agent departments.
- [x] Agent skills.
- [x] Agent model routes.
- [x] Agent characters.
- [x] Agent mailboxes.
- [x] Agent messages.
- [x] Message-to-task-to-inbox-to-worker-run flow.
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
- [ ] Click-through task pages.
- [ ] Click-through output pages.
- [ ] Agent performance dashboard.
- [ ] Agent reliability dashboard.
- [ ] Agent cost dashboard.

## 13. MCP And External Adapters

- [x] MCP architecture planned.
- [x] Postgres/API tools foundation.
- [x] Obsidian writeback foundation.
- [x] Qdrant retrieval foundation.
- [x] Fincept local component installed.
- [x] Fincept skill registry added.
- [x] Vibe skill registry added.
- [x] TradingView CDP connection verified; production chart actions still open.
- [x] Model endpoint registry.
- [x] Data-source connector registry.
- [x] Connector health-check dashboard.
- [~] Browser MCP production workflow.
- [~] NSE scraper MCP.
- [~] BSE scraper MCP.
- [ ] TradingView production controller.
- [ ] News scraper MCP.
- [ ] Document/PDF scraper MCP.
- [ ] Excel/CSV importer MCP.
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
- [ ] Charlie Chat operating console.
- [ ] Portfolio Intelligence dashboard v2.
- [ ] Client Folios dashboard.
- [ ] Symbol Intelligence page.
- [ ] Long-Term Office dashboard v2.
- [ ] Tactical Office dashboard.
- [ ] Trading Desk dashboard.
- [ ] Risk Center dashboard.
- [ ] Capital Allocation dashboard.
- [ ] Research Factory dashboard.
- [ ] Reports dashboard.
- [ ] System Health dashboard.
- [ ] Data Sources dashboard.
- [ ] Model Runtime dashboard.
- [ ] Agent Office animated dashboard.
- [ ] Committee Room dashboard.
- [ ] Approval Board dashboard.

## 15. Reports And Briefs

- [x] Full stack PDF report.
- [x] Multi-book portfolio brain report.
- [x] Strategy Committee memo foundation.
- [x] Special situation memo.
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
- [ ] Trade journal review.
- [ ] Strategy postmortem.
- [ ] Committee minutes report.

## 16. Model And Cost Controls

- [~] Local model plan defined.
- [~] Ollama installed/manual; reliability open.
- [x] Model endpoint registry.
- [~] Model availability monitor foundation.
- [ ] Confirm installed local models and sizes.
- [ ] Decide daily driver model per machine.
- [ ] Add model route cost ledger.
- [ ] Add per-agent cost caps.
- [ ] Add cloud escalation approval.
- [ ] Add fallback routes.
- [ ] Add retrieval-first prompt policy.
- [ ] Add daily model cost report.
- [ ] Add prompt/input privacy policy.
- [ ] Add model quality evaluation set.

## 17. Production Safety

- [x] Live execution disabled by default.
- [x] Strategy activation gated behind evidence.
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
- [x] Full execution audit dashboard foundation.
- [ ] Broker dry-run adapter.
- [ ] Limited-live broker sandbox workflow.
- [ ] Real-time kill-switch monitor.
- [ ] Order lifecycle dashboard.
- [ ] Execution postmortem workflow.
- [ ] Formal disaster drill.

## 18. Immediate Next Sprint

Recommended order:

- [ ] Harden local model/Ollama background reliability.
- [ ] Build backup and restore proof.
- [ ] Build production/test data separation guard.
- [ ] Complete p2cursor extraction for all client buy/sell dates.
- [ ] Import old algo trading DB data.
- [x] Build source-backed Long-Term research packet workflow.
- [x] Build source-backed Long-Term checklist/valuation update workflows.
- [x] Build Long-Term committee workflow.
- [x] Build Long-Term specialist assignment workflow.
- [x] Build Long-Term specialist output execution workflow.
- [x] Build Long-Term source acquisition request workflow.
- [x] Build Long-Term source satisfaction checker workflow.
- [x] Build Long-Term official source document registration workflow.
- [x] Build Long-Term source document text extraction workflow.
- [x] Build source-backed structured checklist scoring workflow.
- [x] Build source-backed structured scoring for core Long-Term checklist modules.
- [ ] Build Command Center v2 around Charlie inbox, approvals, risks, and today changes.
- [ ] Build TradingView production chart actions.
- [ ] Build Agent Office animated room backed by live task/message/run state.

## 19. Whole-System Definition Of Done

- [ ] Devarsh can talk to Charlie and trigger auditable workflows.
- [ ] Jarvis can retrieve memory, call tools, write approved outputs, and update dashboards.
- [ ] All clients/accounts/holdings/trades are in one reconciled warehouse.
- [ ] All positions have book, purpose, owner, thesis/setup, horizon, and exit criteria.
- [ ] Portfolio Intelligence shows gross/net/book/strategy/risk exposure.
- [ ] Research Factory can ingest filings/news and create committee-ready notes.
- [ ] Long-Term Office can produce complete thesis, valuation, bear case, Monte Carlo, and review memos.
- [ ] Quant Lab can intake, backtest, optimize, validate, paper-monitor, and committee-review strategies.
- [ ] Trading Desk can log manual/paper trades and control TradingView tasks.
- [ ] Risk Office can block unsafe actions.
- [ ] Capital Allocation can allocate capital across books and detect conflict.
- [ ] AI Office GUI shows live agent work, messages, approvals, reports, and widgets.
- [ ] Obsidian and Qdrant provide durable memory and retrieval.
- [ ] Local model runtime is reliable and cloud spend is controlled.
- [ ] Broker execution remains blocked unless all safety gates pass.
