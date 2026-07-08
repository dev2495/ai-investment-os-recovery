# AI Investment OS - Execution Checklist v7.0

Date: 2026-07-06
Blueprint: [[AI Investment OS - Institutional Master Blueprint v7.0]]
Purpose: track the build from current foundation to full AI hedge fund operating system.

Status legend:

- `[x]` done and verified by code, database, UI, report, runtime check, or smoke test.
- `[~]` partially implemented, prototype exists, or needs hardening.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without evidence. Add evidence note path, command, table, API check, UI screenshot, or report link before closing.

## 0. Canonical Docs And Governance

- [x] Create institutional master blueprint v7.0. Evidence: this file pair.
- [x] Create execution checklist v7.0. Evidence: this file.
- [x] Mark v7.0 as canonical in top-level AI OS index. Evidence: [[AI OS Master Blueprint]].
- [x] Create architecture change-control policy. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create decision log template. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create committee minutes template. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create sprint acceptance criteria template. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create evidence standard for checklist completion. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create production data vs test data separation policy. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create investment disclaimer and human-control policy. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create source freshness standard. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [x] Create broker execution safety constitution. Evidence: [[AI Investment OS - Governance Pack v1.0]].

## 1. Foundation Runtime

- [~] Runtime workspace on external SSD.
- [~] Docker services on external SSD.
- [~] Postgres warehouse.
- [~] Redis.
- [~] Qdrant.
- [~] API server.
- [~] AI Office dashboard shell.
- [~] Obsidian vault memory surface.
- [~] MCP server foundation.
- [~] Model endpoint registry.
- [~] Data-source connector registry.
- [~] Connector health-check dashboard.
- [~] Browser profile registry.
- [~] Data-source freshness monitor.
- [ ] Durable backup job.
- [ ] Restore test.
- [ ] Worker daemon health monitor.
- [ ] System health dashboard v2.
- [x] Model route and cost ledger. Evidence: [[2026-07-06-model-cost-ledger-v1]]; `agent.model_usage_events`, `agent.model_cost_rates`, `agent.v_model_cost_ledger_events`, `agent.v_model_cost_summary`, and `agent.v_model_route_cost_summary` track local/cloud route usage, estimated/actual tokens, zero-cost local usage, and cost-control status with API/MCP/dashboard verification.
- [x] Per-agent cost caps. Evidence: [[2026-07-06-model-cost-ledger-v1]]; `agent.model_cost_caps` and `agent.v_agent_model_cost_cap_status` expose 32 active agent caps, daily/monthly limits, cloud approval flags, and cap status, with all 32 verified `ok`.
- [ ] Cloud escalation approval workflow.
- [ ] Runtime disaster recovery runbook.

## 2. Data Spine

- [~] Client/account/holding import foundation.
- [~] Broker transaction import foundation.
- [~] Manual trade capture foundation.
- [~] Paper trade capture foundation.
- [~] Mark-to-market foundation for provided holdings.
- [ ] Full p2cursor extraction for all client buy/sell dates.
- [~] Full p2cursor reconciliation against broker files. Evidence: first-client Tushit reconciliation in [[2026-07-06-p2cursor-first-client-reconciliation]]; all-client reconciliation still open.
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
- [~] Reconciliation dashboard across broker, p2cursor, algo systems, and manual entries. Evidence: broker and p2cursor panels exist; algo/manual combined reconciliation still open.
- [x] Source lineage view for every portfolio row. Evidence: [[2026-07-06-source-lineage-artifact-visibility]]; `core.v_source_artifact_lineage` covers raw artifacts, p2cursor files/rows, attached broker files, portfolio positions, and p2cursor reconciliation issues.
- [x] Raw artifact store for every tracked file import. Evidence: [[2026-07-06-raw-artifact-import-coverage]]; `core.v_import_artifact_coverage` shows 100% coverage for `client_data.source_files`, `client_data.attached_transaction_files`, and imported broker/PDF source-system file locations, with zero rows in `core.v_import_artifact_gaps`.

## 3. Multi-Book Portfolio Brain

- [~] Investment book schema.
- [~] Core books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges.
- [~] Position purpose taxonomy.
- [~] Current holdings mapped to Long-Term by default.
- [~] Book exposure views.
- [~] Cross-book conflict view.
- [~] Dashboard panels for book exposure and symbol rollup.
- [~] Manual/paper trade routing into book positions.
- [ ] Hedge ratio.
- [ ] Offset-cost calculation.
- [ ] Capital used by book.
- [ ] Risk budget used by book.
- [ ] Book P&L attribution.
- [ ] Strategy attribution.
- [ ] Catalyst links in Symbol Intelligence.
- [ ] Trading setup links in Symbol Intelligence.
- [ ] Latest news/filing/task/committee notes in Symbol Intelligence.
- [ ] Full Symbol Intelligence page.
- [ ] Client folio book exposure page.
- [ ] Cross-book conflict action workflow.

## 4. Long-Term Investing Office

- [~] Company thesis schema.
- [~] Thesis version history.
- [~] Thesis killer table.
- [~] Exit criteria linked to holdings.
- [~] Quarterly review schedule.
- [~] Long-Term Office dashboard foundation.
- [~] Research packet generator.
- [~] Source acquisition request workflow.
- [~] Official source registration workflow.
- [~] Source text extraction workflow.
- [~] Source-backed checklist update workflow.
- [~] Source-backed structured checklist scoring.
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
- [ ] Reverse DCF module.
- [ ] Sum-of-parts module.
- [ ] Peer comparison module.
- [ ] Historical valuation module.
- [ ] Bull/base/bear scenario builder.
- [ ] Expected CAGR calculator.
- [~] Long-term Monte Carlo engine.
- [ ] Long-term Monte Carlo UI and committee integration.
- [ ] Sell discipline checklist.
- [ ] Thesis drift alerts.
- [ ] Quarterly review automation.
- [~] Long-Term Portfolio Manager agent.
- [~] Company Analyst agent.
- [~] Industry Analyst agent.
- [~] Management Analyst agent.
- [~] Financial Statement Analyst agent.
- [~] Valuation Agent.
- [~] Forensic Accounting Agent.
- [~] Filings and Transcript Analyst.
- [~] Bear Case Agent.
- [~] Quality Score Agent.
- [~] Portfolio Fit Agent.
- [~] Long-Term Investment Committee workflow.
- [ ] Full Long-Term committee room UI.
- [ ] Human buy/hold/add/trim/sell decision UI.

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

- [~] Strategy intake workflow.
- [~] Strategy candidate creation.
- [~] Paper-first activation gate.
- [~] Deterministic OHLCV backtest runner.
- [~] Cost/slippage model foundation.
- [~] Backtest API endpoint.
- [~] Persisted backtest metrics and artifacts.
- [~] Model validation review after backtest.
- [~] Parameter optimizer.
- [~] Train/test split.
- [~] Walk-forward diagnostics.
- [~] Sensitivity rows.
- [~] Monte Carlo/bootstrap diagnostics.
- [~] Strategy Committee review gate.
- [~] Strategy Committee memo generation.
- [~] Paper-monitor approval guard.
- [~] Drift monitor.
- [~] Strategy kill-switch enforcement.
- [~] Limited-live approval workflow.
- [x] Deterministic strategy rule parser.
- [x] User-defined strategy DSL.
- [x] Data-quality gate before every backtest.
- [x] Regime split performance.
- [x] Factor attribution.
- [x] Capacity/liquidity model.
- [x] Strategy correlation matrix.
- [x] Strategy portfolio optimizer.
- [x] Portfolio-level strategy allocation.
- [x] Probability-of-ruin metric.
- [ ] Strategy retirement workflow.
- [ ] Strategy Generator agent.
- [ ] Data Scientist agent.
- [ ] Feature Engineer agent.
- [ ] Regime Analyst agent.
- [ ] Capacity/Liquidity Analyst agent.
- [ ] Quant Lab dashboard v2.

## 7. Active Trading Desk

- [~] Active Trading book mapping foundation.
- [~] Manual trade entry UI with book/purpose.
- [~] Paper trade entry UI with book/purpose.
- [~] Trade setup taxonomy foundation.
- [~] TradingView CDP connection.
- [~] TradingView chart open workflow.
- [~] TradingView screenshot artifact capture.
- [~] TradingView action template registry.
- [~] TradingView template execution API.
- [~] Symbol Intelligence chart/snapshot buttons.
- [x] Human-gated TradingView alert request template. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
- [~] TradingView screenshot visual-quality rejection gate.
- [ ] Options payoff dashboard.
- [ ] IV/OI dashboard.
- [ ] Straddle/strangle chart workflow.
- [x] Alert inbox completion. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
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
- [ ] Trade Journal Coach.

## 8. Research Factory And Special Situations

- [~] NSE/BSE filing collector foundation.
- [~] Filing PDF extraction pipeline.
- [~] Special situation memo workflow.
- [~] Special situation terms extraction.
- [~] Special situation spread decision workflow.
- [~] Event-symbol quote refresh from TradingView scanner.
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
- [ ] News and Filings dashboard.
- [ ] Special Situations dashboard.
- [ ] Research Director agent.
- [ ] Corporate Actions Analyst agent.
- [ ] Arbitrage Analyst agent.
- [ ] Research Librarian agent.

## 9. Cash, Treasury, Hedges, Crypto, Commodities

- [ ] Cash/Treasury dashboard.
- [ ] Cash drag calculation.
- [ ] Liquid fund/cash equivalent tracking.
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

- [~] Risk approval gate.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
- [x] Risk limits table across books/accounts/clients. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; `risk.v_portfolio_risk_limit_checks` evaluates 108 live checks across book, client, symbol, quality-gate, and allocation scopes.
- [x] Risk limits dashboard. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; AI Office shows live risk checks, summary counts, and refreshes breached checks into `risk.events`.
- [~] Concentration engine. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; single-name concentration checks are live for current book exposure, but liquidity/correlation/factor-adjusted concentration is still open.
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
- [ ] Compliance/Audit Agent.

## 12. Agent Office And Communication

- [~] Agent profiles foundation.
- [~] Agent departments foundation.
- [~] Agent skills foundation.
- [~] Agent task queue foundation.
- [~] Agent inbox foundation.
- [~] Agent messages foundation.
- [~] Agent approvals foundation. Evidence: [[2026-07-06-approval-board-v1]]; approval rows, unified board, MCP read tool, and dashboard actions exist, but domain-specific committee decision sync and full approval audit UX still need hardening.
- [~] Agent run logging foundation.
- [~] Charlie profile.
- [~] Jarvis profile.
- [x] Agent comments. Evidence: [[2026-07-06-agent-comments-v1]]; `agent.comments`, `agent.v_agent_comments`, `agent.v_agent_comment_summary`, and `agent.v_agent_comment_target_summary` provide auditable comments on output artifacts/tasks/approvals/agents/strategies, with API create/resolve, MCP read/create/resolve, dashboard composer/list/resolve controls, 6 verified runtime comments, 1 open review note, and 5 resolved smoke comments.
- [x] Agent output artifacts registry v2. Evidence: [[2026-07-06-output-artifact-registry-v2]]; `agent.v_output_artifact_registry_v2`, `agent.v_output_artifact_summary`, and `agent.v_output_artifact_gaps` expose 159 real generated artifacts across worker outputs, committee memos, specialist outputs, research notes, Monte Carlo notes, special-situation memos, and indexed AI outputs, with API, MCP, dashboard panel, and 4 traceability gaps verified.
- [x] Per-agent tool permissions UI. Evidence: [[2026-07-06-agent-employee-profiles-v1]]; Employee Profiles dashboard cards expose enabled/read-only/write-or-browser tool counts and top tool permissions from `agent.tool_registry`.
- [x] Per-agent model route UI. Evidence: [[2026-07-06-agent-employee-profiles-v1]]; Employee Profiles dashboard cards expose primary route, provider, model, fallback/escalation model metadata from `agent.v_employee_profiles_v1`.
- [x] Agent mailbox UI. Evidence: [[2026-07-06-agent-mailbox-research-queue]]; dashboard shows `agent.v_agent_mailboxes`, `agent.v_agent_message_threads`, per-message Ack/Task controls, and verified message `60` routed through task `96` and inbox `147`.
- [~] Agent handoff threads. Evidence: [[2026-07-06-agent-mailbox-research-queue]]; message triage and task routing are live, but full threaded conversation detail view is still open.
- [x] Committee room view. Evidence: [[2026-07-06-committee-room-v1]]; dashboard shows unified room from `agent.v_committee_room_items` across Strategy, Long-Term, and Special Situation committees with 4 live reviews, 2 pending approvals, 2 pending decisions, memo/evidence/follow-up counters, and action guard flags.
- [x] Approval board view. Evidence: [[2026-07-06-approval-board-v1]]; dashboard shows unified approval board from `agent.v_approval_board_items` with 8 live records, 4 high-risk pending decisions, lane/source classification, risk/gate counters, and live/broker guard flags.
- [x] Character/personality cards. Evidence: [[2026-07-06-agent-employee-profiles-v1]]; Employee Profiles cards show character/personality voice, role, hierarchy, office location, model route, tools, skills, work, outputs, and approvals.
- [x] Agent hover cards. Evidence: [[2026-07-06-live-ai-office-v1]]; each live-office desk now exposes current work, task/inbox/unread counts, location, and workload through hover detail from `agent.v_live_office_agent_activity`.
- [ ] Agent reliability score.
- [ ] Agent productivity metrics.
- [~] Live AI Office animated room. Evidence: [[2026-07-06-live-ai-office-v1]]; v1 room grid is backed by live rooms/agents/tasks/messages/risk state with animated status dots, but final graphic/3D office scene and task arrows remain open.
- [ ] Task arrows between agents.
- [ ] Click-through agent profile pages.

## 13. MCP And External Adapters

- [~] MCP server foundation.
- [~] Obsidian/vault read-write path.
- [~] Postgres API tool path.
- [~] Browser profile registry.
- [~] Fincept local component installed.
- [~] Fincept skill registry added.
- [~] Vibe skill registry added.
- [~] TradingView CDP/chart-action executor foundation.
- [~] TradingView screenshot artifact API.
- [~] TradingView action template registry/API/MCP.
- [x] TradingView gated alert request path. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
- [ ] TradingView production controller hardening.
- [ ] Browser research runner hardening.
- [ ] Web/document scraper MCP.
- [ ] PDF/doc extraction MCP.
- [ ] Excel/CSV importer MCP.
- [ ] Fincept tool catalog bridge.
- [ ] Fincept report-builder bridge.
- [ ] Fincept news/RSS bridge.
- [ ] Fincept options/IV/OI bridge.
- [ ] Vibe read-only adapter.
- [ ] OpenAlgo read-only bridge.
- [ ] Broker read-only MCP connector.
- [ ] Crypto/commodity read-only MCP connector.

## 14. Dashboards

- [~] Command Center foundation.
- [~] Portfolio widget foundation.
- [~] Book exposure widget.
- [~] Strategy Committee Gate panel.
- [~] Data-source freshness panel.
- [~] Agent task/inbox panels.
- [~] Long-Term Office dashboard foundation.
- [~] Quant Lab dashboard foundation.
- [~] AI Office live activity foundation.
- [x] Portfolio Intelligence dashboard v2. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; `books.v_portfolio_intelligence_v2`, API snapshot `portfolio_intelligence_v2`, MCP `ai_os_portfolio_intelligence_v2`, and AI Office panel verified.
- [ ] Client Folio dashboard.
- [ ] Symbol Intelligence dashboard v2.
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

- [~] Obsidian report writeback foundation.
- [~] Strategy Committee memo foundation.
- [~] Long-Term committee memo foundation.
- [~] Special situation memo foundation.
- [~] PDF report capability.
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

- [~] Model endpoint registry foundation.
- [~] Local model route foundation.
- [~] Ollama/local model runtime foundation.
- [ ] Daily driver model selected and benchmarked.
- [ ] Embedding model reliability test.
- [x] Per-agent model route table complete. Evidence: [[2026-07-06-agent-employee-profiles-v1]]; API snapshot exposes 32 employee profiles and all 32 have model routes through `agent.v_employee_profiles_v1`.
- [x] Cost ledger. Evidence: [[2026-07-06-model-cost-ledger-v1]]; 14 model usage events are visible after backfilling chat turns, API/MCP smoke writes, and automatic Charlie chat logging, with 14 local usage events, 0 cloud usage events, 0 unapproved cloud events, and $0 estimated local cost.
- [ ] Model call cache.
- [ ] Escalation policy.
- [ ] Cloud model approval flow.
- [ ] Model quality eval set.
- [ ] Local-vs-cloud routing tests.
- [ ] Context/RAG compression policy.

## 17. Production Safety

- [~] Paper-first strategy activation gate.
- [~] Risk approval gate for limited-live requests.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
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

## 18. Immediate Build Order

- [x] Mark v7 docs as canonical and link them from AI OS index. Evidence: [[AI OS Master Blueprint]].
- [ ] Verify current runtime health against v7 foundation checklist.
- [x] Finish TradingView alert inbox. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
- [ ] Harden broader TradingView production controller.
- [x] Build p2cursor extraction plan and first client reconciliation. Evidence: [[2026-07-06-p2cursor-first-client-reconciliation]].
- [x] Build source lineage/artifact view. Evidence: [[2026-07-06-source-lineage-artifact-visibility]]; API snapshot and MCP tools `ai_os_source_lineage_summary` / `ai_os_source_lineage` verified.
- [x] Backfill and enforce raw artifact coverage for tracked file imports. Evidence: [[2026-07-06-raw-artifact-import-coverage]]; migration `075_raw_artifact_import_coverage.sql`, API snapshot keys `import_artifact_coverage` / `import_artifact_gaps`, and MCP tools `ai_os_import_artifact_coverage` / `ai_os_import_artifact_gaps` verified.
- [x] Build Agent mailbox UI. Evidence: [[2026-07-06-agent-mailbox-research-queue]]; API snapshot has 20 mailbox rows and 50 visible message rows, UI has mailbox/message panels and message triage actions.
- [x] Build Research Factory news and filing queue dashboard. Evidence: [[2026-07-06-agent-mailbox-research-queue]]; `research.v_research_factory_queue_summary` exposes seven live queue lanes and the AI Office shows the Research Factory Queue panel.
- [x] Build Risk limits table and dashboard. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; API snapshot has 108 risk checks, 6 summary rows, 4 live breaches, and event refresh produced risk events 36-39.
- [x] Build Portfolio Intelligence v2 dashboard. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]]; API snapshot has 73 Portfolio Intelligence v2 rows and MCP smoke returned 25 top-symbol rows.
- [x] Build Live AI Office v1 backed by real agent/task/message state. Evidence: [[2026-07-06-live-ai-office-v1]]; API snapshot exposes 10 live rooms, 20 live agents, 13 open room tasks, 9 unread room messages, and MCP tools `ai_os_live_office_rooms` / `ai_os_live_office_agent_activity` passed JSON-RPC smoke.
- [x] Build Approval Board v1. Evidence: [[2026-07-06-approval-board-v1]]; API snapshot exposes 8 board rows across TradingView, Special Situation, Strategy Committee, and Long-Term Committee lanes with 4 pending high-risk approvals and 0 live/broker allowed.
- [x] Build Committee Room v1. Evidence: [[2026-07-06-committee-room-v1]]; API snapshot exposes 4 committee rows across Strategy, Long-Term, and Special Situation lanes, with 2 pending approvals, 2 pending decisions, 0 memo gaps, and 0 capital/live action allowed.

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
- [x] Agent Office shows real tasks, inbox, runs, messages, model routes, outputs, and approvals. Evidence: [[2026-07-06-agent-employee-profiles-v1]]; API snapshot has 32 employee profiles, 109 mapped enabled tools, 85 active skills, 28 open tasks, 23 output artifacts, and 4 pending approvals in the employee profile surface.
- [ ] Reports can be generated from source-backed data.
- [ ] Live execution remains human-approved and audit-logged.
