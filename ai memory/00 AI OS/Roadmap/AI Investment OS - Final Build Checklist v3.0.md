# AI Investment OS - Final Build Checklist v3.0

Date: 2026-07-06
Canonical blueprint: [[AI Investment OS - Final Master Blueprint v3.0]]
Purpose: execution tracker for building the complete AI hedge fund operating system.

Status legend:

- `[x]` done and verified in the current stack.
- `[~]` partially implemented or prototype exists.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without database, code, UI, report, runtime, or smoke-test evidence.

## 0. Constitution And Operating Rules

- [x] Create AI OS master blueprint v1.0.
- [x] Create AI OS master blueprint v2.0.
- [x] Create final master blueprint v3.0.
- [x] Create final build checklist v3.0.
- [ ] Add document versioning policy.
- [ ] Add decision log template.
- [ ] Add committee minutes template.
- [ ] Add sprint acceptance criteria template.
- [ ] Add evidence standard for checklist completion.
- [ ] Add change-control policy for architecture changes.

## 1. Foundation Runtime

- [x] Runtime workspace on external SSD.
- [x] Postgres warehouse.
- [x] Redis.
- [x] Qdrant.
- [x] API server.
- [x] AI Office dashboard shell.
- [x] Obsidian vault indexed.
- [~] Qdrant retrieval available; embedding fallback still needs hardening.
- [~] Local model/Ollama manually available; background reliability still open.
- [ ] Durable backup job.
- [ ] Restore test.
- [ ] System health dashboard.
- [ ] Data-source freshness monitor.
- [ ] Worker daemon health monitor.
- [ ] Model route and cost ledger.
- [~] Secrets registry policy using secret references only.

## 2. Core Data Spine

- [x] Client/account/holding foundation imported.
- [x] Broker transaction import routing foundation.
- [x] Manual trade capture foundation.
- [x] Paper trade capture foundation.
- [x] Post-trade review foundation.
- [~] Mark-to-market foundation exists for provided holdings.
- [ ] Full p2cursor extraction for all client buy/sell dates.
- [ ] Full algo trading DB import.
- [ ] Import old equity curves and strategy artifacts.
- [ ] Import old trade journals from 2018-19 onward.
- [ ] Import old Codex/Claude/Cowork research outputs.
- [ ] Live Zerodha read-only connector.
- [ ] Live Dhan read-only connector.
- [ ] Crypto/commodity exchange read-only connector.
- [ ] Full daily OHLCV ingestion.
- [ ] Intraday OHLCV ingestion.
- [ ] Options chain/OI/IV ingestion.
- [ ] Reconciliation dashboard across broker, old systems, and manual entries.

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
- [~] Portfolio Intelligence Engine foundation exists; full analytics still open.
- [ ] Add hedge ratio.
- [ ] Add capital used by book.
- [ ] Add risk budget used by book.
- [ ] Add current trades by book into symbol intelligence.
- [ ] Add thesis links into symbol intelligence.
- [ ] Add catalyst links into symbol intelligence.
- [ ] Add quant signal links into symbol intelligence.
- [ ] Add trading setup links into symbol intelligence.
- [ ] Add latest news/filing/tasks/committee notes into symbol intelligence.
- [ ] Build full Symbol Intelligence page.

## 4. Long-Term Investing Office

- [ ] Company thesis schema.
- [ ] Thesis version history.
- [ ] Business model checklist.
- [ ] Industry structure checklist.
- [ ] Moat scorecard.
- [ ] Management scorecard.
- [ ] Governance scorecard.
- [ ] Capital allocation scorecard.
- [ ] Financial statement quality scorecard.
- [ ] Forensic accounting checklist.
- [ ] Valuation model registry.
- [ ] DCF module.
- [ ] Reverse DCF module.
- [ ] Sum-of-parts module.
- [ ] Bull/base/bear scenario builder.
- [ ] Expected CAGR calculator.
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

- [ ] Tactical idea schema.
- [ ] Catalyst schema.
- [ ] Event calendar connector.
- [ ] Tactical setup schema.
- [ ] Stop/target/time-exit fields.
- [ ] Tactical risk/reward calculator.
- [ ] Long-Term overlap check.
- [ ] Hedge vs independent alpha flag.
- [ ] Options overlay support.
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
- [ ] Regime split performance.
- [ ] Factor attribution.
- [ ] Capacity/liquidity model.
- [ ] Strategy correlation matrix.
- [ ] Strategy portfolio optimizer.
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
- [ ] TradingView CDP relaunch and verified connection.
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

## 8. Cash, Treasury, And Hedges

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
- [ ] Cash/Treasury Agent.
- [ ] Hedge Manager Agent.

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
- [ ] Capital increase/decrease recommendation.
- [ ] Cross-book conflict review workflow.
- [ ] Portfolio rebalancing workflow.
- [ ] Capital Allocation Officer agent.
- [ ] Performance Attribution Agent.
- [ ] Book Controller agent.
- [ ] Client Suitability Agent.

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
- [ ] Merger/demerger/reverse merger detector.
- [ ] Buyback/delisting/rights/preferential issue detector.
- [ ] Arbitrage spread tracker.
- [ ] Research Factory dashboard.
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
- [ ] Click-through task pages.
- [ ] Click-through output pages.
- [ ] Agent performance/reliability dashboard.

## 13. MCP And External Adapters

- [x] MCP architecture planned.
- [x] Postgres/API tools foundation.
- [x] Obsidian writeback foundation.
- [x] Qdrant retrieval foundation.
- [x] Fincept local component installed.
- [x] Fincept skill registry added.
- [x] Vibe skill registry added.
- [~] TradingView MCP/controller planned; CDP relaunch still required.
- [~] Browser MCP production workflow.
- [x] Browser profile registry.
- [x] Browser connector link registry.
- [x] Browser session health checks.
- [ ] TradingView production controller.
- [ ] NSE scraper MCP.
- [ ] BSE scraper MCP.
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
- [x] Model endpoint registry.
- [x] Data-source connector registry.
- [x] Connector health-check dashboard.

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
- [ ] Data Sources dashboard.
- [ ] Model Runtime dashboard.
- [ ] Agent Office animated dashboard.

## 15. Reports And Briefs

- [x] Full stack PDF report.
- [x] Multi-book portfolio brain report.
- [x] Strategy Committee memo foundation.
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
- [ ] Strategy postmortem.

## 16. Model And Cost Controls

- [~] Local model plan defined.
- [~] Ollama installed/manual; reliability open.
- [ ] Confirm installed local models and sizes.
- [ ] Decide daily driver model per machine.
- [~] Add model availability monitor.
- [x] Add model endpoint registry.
- [ ] Add model route cost ledger.
- [ ] Add per-agent cost caps.
- [ ] Add cloud escalation approval.
- [ ] Add fallback routes.
- [ ] Add retrieval-first prompt policy.
- [ ] Add daily model cost report.
- [ ] Add prompt/input privacy policy.

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

## 18. Immediate Next Sprint Candidates

Recommended order:

- [x] Harden model/source connector registry and health checks.
- [ ] Harden local model/Ollama background reliability.
- [ ] Build TradingView CDP/controller connection once browser is launched correctly.
- [x] Build browser profile/session gate for TradingView, NSE, BSE, and social connectors.
- [ ] Build Long-Term thesis schema and memo template.
- [ ] Build NSE/BSE filing collector and Special Situations workflow.
- [ ] Build source freshness and reconciliation dashboard.
- [ ] Build Command Center v2 around Charlie inbox, approvals, risks, and today changes.
- [ ] Build Agent Office animated room backed by live task/message/run state.

## 19. Whole-System Definition Of Done

- [ ] Devarsh can talk to Charlie and trigger auditable workflows.
- [ ] Jarvis can retrieve memory, call tools, write approved outputs, and update dashboards.
- [ ] All clients/accounts/holdings/trades are in one warehouse.
- [ ] All positions have book, purpose, owner, thesis/setup, horizon, and exit criteria.
- [ ] Portfolio Intelligence shows gross/net/book/strategy/risk exposure.
- [ ] Research Factory can ingest filings/news and create committee-ready notes.
- [ ] Long-Term Office can produce complete thesis, valuation, bear case, and review memos.
- [ ] Quant Lab can intake, backtest, optimize, validate, paper-monitor, and committee-review strategies.
- [ ] Trading Desk can log manual/paper trades and control TradingView tasks.
- [ ] Risk Office can block unsafe actions.
- [ ] Capital Allocation can allocate capital across books and detect conflict.
- [ ] AI Office GUI shows live agent work, messages, approvals, reports, and widgets.
- [ ] Obsidian and Qdrant provide durable memory and retrieval.
- [ ] Local model runtime is reliable and cloud spend is controlled.
- [ ] Broker execution remains blocked unless all safety gates pass.
