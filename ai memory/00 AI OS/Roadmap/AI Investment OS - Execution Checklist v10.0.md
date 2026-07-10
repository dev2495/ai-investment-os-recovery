# AI Investment OS - Execution Checklist v10.0

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Frontend specification: [[AI OS Command Center and 3D Office Frontend Plan]]
Purpose: track the build from foundation to complete AI hedge fund operating system.

Status legend:

- `[x]` done and verified by code, database, UI, report, runtime check, smoke test, or source evidence.
- `[~]` partially implemented, prototype exists, or needs hardening.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without evidence. Add note path, report, command, table, API check, UI check, screenshot, or live verification.

## 0. Canonical Docs And Governance

- [x] Create institutional master blueprint v10.0. Evidence: [[AI Investment OS - Institutional Master Blueprint v10.0]].
- [x] Create execution checklist v10.0. Evidence: this file.
- [x] Mark v10.0 as canonical in top-level AI OS index. Evidence: [[AI OS Master Blueprint]].
- [ ] Convert v10 domains and requirements into database-backed registry rows.
- [ ] Architecture decision record table/API.
- [ ] Architecture change-control workflow.
- [ ] Decision log template.
- [ ] Committee minutes template.
- [ ] Evidence standard visible in UI.
- [ ] Production data vs test data enforcement check.
- [ ] Investment disclaimer and human-control notice visible in UI.
- [ ] Broker execution safety constitution visible in UI.
- [ ] Runtime disaster recovery runbook.

## 1. Foundation Runtime

- [~] Runtime workspace on external SSD.
- [~] Docker services on external SSD.
- [~] Postgres warehouse.
- [~] Redis.
- [~] Qdrant.
- [~] API server.
- [~] AI Office dashboard shell.
- [~] Obsidian vault memory surface.
- [~] MCP server foundation. Evidence includes strategy template tools in [[2026-07-08-strategy-template-library-v1]]; `ai_os_strategy_template_library` and `ai_os_create_strategy_from_template` are registered and import-verified.
- [~] Model endpoint registry.
- [~] Data-source connector registry.
- [~] Provider readiness board.
- [~] Provider assignment gates.
- [~] Department-level provider policy controls.
- [x] Blueprint v9 operating-model registry. Evidence: [[2026-07-07-blueprint-v9-operating-model-registry-v1]].
- [ ] Blueprint v10 operating-model registry.
- [ ] Worker daemon health monitor.
- [ ] System health dashboard v2.
- [ ] Durable backup job.
- [ ] Restore test.
- [ ] Remote access plan and security model.
- [ ] Local model daily-driver benchmark.
- [ ] Cloud escalation approval workflow.

## 2. Data Spine

- [~] Client/account/holding import foundation.
- [~] Broker transaction import foundation.
- [~] Manual trade capture foundation.
- [~] Paper trade capture foundation.
- [~] Mark-to-market foundation.
- [~] Source lineage for portfolio rows.
- [~] Raw artifact store for imports.
- [x] Legacy source extraction readiness board. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; migration `107_legacy_source_extraction_readiness.sql`, API snapshot keys, POST `/api/legacy-source-readiness/run`, MCP tools `ai_os_legacy_source_readiness` and `ai_os_run_legacy_source_readiness`, and AI Office dashboard panels verified.
- [~] Full p2cursor extraction for all clients. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; 6 p2cursor files profiled and 139 CSV rows staged, but 5 p2cursor files still need mapping/promotion before full completion.
- [~] Full buy/sell date extraction from p2cursor and broker reports. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; p2cursor trade CSV rows are staged, but normalized buy/sell-date promotion and broker reconciliation remain open.
- [~] Full old algo trading DB import. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; 21 old algo tables and 1,361,017 source rows are profiled, with 197,703 promoted rows, but daily bars, straddle snapshots, and partial tick/snapshot/trade/holding coverage remain open.
- [ ] Historical equity curve import.
- [ ] Old strategy artifact import.
- [ ] Old trade journal import from 2018-19 onward.
- [ ] Codex research output collector.
- [ ] Claude/Cowork research output collector.
- [ ] Excel/CSV importer MCP.
- [ ] PDF/document extraction MCP.
- [ ] Screenshot/chart artifact registry.
- [ ] Zerodha read-only connector.
- [ ] Dhan read-only connector.
- [ ] Crypto exchange read-only connector.
- [ ] Daily OHLCV ingestion.
- [ ] Intraday OHLCV ingestion.
- [ ] Options chain/OI/IV/Greeks ingestion.
- [ ] Futures basis ingestion.
- [ ] VIX/volatility ingestion.
- [ ] Gold/silver/commodity ingestion.
- [ ] Corporate action adjustment pipeline.
- [ ] Full reconciliation dashboard across broker, p2cursor, algo systems, and manual entries.
- [ ] Data quality score per source.
- [ ] Source freshness SLA per source.

## 3. Multi-Book Portfolio Brain

- [~] Investment book schema.
- [~] Core books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges, Crypto/Commodity Macro.
- [~] Position purpose taxonomy.
- [~] Current holdings mapped to Long-Term by default.
- [~] Book exposure views.
- [~] Cross-book conflict view.
- [~] Manual/paper trade routing into book positions.
- [~] Position object complete with purpose, owner, horizon, thesis/setup, source, review cadence, exit logic, and approval state. Evidence: [[2026-07-07-position-object-v9-readiness-v1]].
- [x] Position object v9 readiness ledger. Evidence: [[2026-07-07-position-object-v9-readiness-v1]].
- [x] Position readiness remediation queue verified in API, MCP, and UI. Evidence: [[2026-07-07-position-readiness-remediation-queue-v1]]; migration `104_position_readiness_remediation_queue.sql`, API snapshot keys `position_remediation_summary` and `position_remediation_queue`, POST `/api/portfolio/position-readiness/remediate`, MCP tools `ai_os_sync_position_remediation_queue`, `ai_os_position_remediation_queue`, `ai_os_position_remediation_summary`, and AI Office `Sync remediation queue` action verified. Current live queue: 142 open critical remediation items across 45 symbols, all routed into 142 tasks and inbox items.
- [ ] Hedge ratio calculation.
- [ ] Offset-cost and tax-impact calculation.
- [ ] Capital used by book.
- [ ] Risk budget used by book.
- [ ] Book P&L attribution.
- [ ] Strategy attribution.
- [ ] Client folio book exposure page.
- [x] Symbol Intelligence dashboard v2. Evidence: [[2026-07-07-symbol-intelligence-v2]]; view `portfolio.v_symbol_intelligence_v2`, summary view, API snapshot keys `symbol_intelligence_v2` and `symbol_intelligence_v2_summary`, MCP tools `ai_os_symbol_intelligence_v2` and `ai_os_symbol_intelligence_v2_summary`, and AI Office `Symbol Intelligence v2` panel verified.
- [x] Catalyst links in Symbol Intelligence. Evidence: [[2026-07-07-symbol-intelligence-v2]], [[2026-07-07-symbol-intelligence-action-router-v1]]; filing/event fields and source URLs are in the v2 decision packet, and per-symbol Research/Thesis/Exit/Risk/Committee-style routing is now backed by API, MCP, tasks, and inbox.
- [x] Trading setup links in Symbol Intelligence. Evidence: [[2026-07-07-symbol-intelligence-v2]], [[2026-07-07-symbol-intelligence-action-router-v1]]; signals, strategy candidates, and strategy dossiers are in the v2 decision packet, with per-symbol Quant/Trade/TV Prep action routing verified. TradingView production controller hardening remains separately open.
- [x] Latest news/filing/task/committee notes in Symbol Intelligence. Evidence: [[2026-07-07-symbol-intelligence-v2]]; v2 exposes latest news, latest filing, remediation task/inbox links, committee items, thesis note, committee memo, and Monte Carlo note through API/MCP/UI.
- [ ] Cross-book conflict action workflow.
- [ ] Reliance-style opposite-exposure explanation UI.

## 4. Long-Term Investing Office

- [~] Company thesis schema.
- [~] Thesis version history.
- [~] Thesis killer table.
- [~] Exit criteria linked to holdings.
- [~] Quarterly review schedule.
- [~] Long-Term Office dashboard foundation.
- [x] Long-Term coverage board v1. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; 52 live coverage gaps across 45 symbols synced from real Long-Term exposure, with API/MCP/UI and 52 tasks/inbox items verified.
- [~] Research packet generator.
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
- [~] Business model checklist. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Industry structure checklist. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Moat scorecard. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Management scorecard. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Governance scorecard. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Capital allocation scorecard. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Financial statement quality scorecard. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [~] Forensic accounting checklist. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; checklist table/UI exists, but coverage board shows many holdings still need source-backed completion.
- [ ] DCF module.
- [ ] Reverse DCF module.
- [ ] Sum-of-parts module.
- [ ] Peer comparison module.
- [ ] Historical valuation module.
- [ ] Bull/base/bear scenario builder.
- [ ] Expected CAGR calculator.
- [ ] Long-term Monte Carlo engine.
- [ ] Long-term Monte Carlo UI.
- [ ] Monte Carlo committee integration.
- [ ] Sell discipline checklist.
- [ ] Thesis drift alerts.
- [ ] Quarterly review automation.
- [ ] Full Long-Term committee room UI.
- [ ] Human buy/hold/add/trim/sell decision UI.
- [ ] Client-level long-term suitability review.

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
- [ ] Tactical Committee workflow.
- [ ] Tactical Committee memo template.

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
- [~] Paper-monitor approval guard.
- [~] Drift monitor.
- [~] Strategy kill-switch enforcement.
- [~] Limited-live approval workflow.
- [~] Strategy idea generator from trade journals.
- [~] Automatic strategy discovery engine.
- [~] Strategy idea dossiers.
- [~] Dossier semantic search.
- [~] Dossier-to-workflow action bridge.
- [~] Strategy hypothesis editor. Evidence: [[2026-07-08-strategy-template-library-v1]]; AI Office now has controlled template-to-strategy queueing, but the full free-form visual editor is still open.
- [ ] Strategy DSL visual builder.
- [~] Intraday strategy templates. Evidence: [[2026-07-08-strategy-template-library-v1]]; v1 includes intraday momentum, mean reversion, opening range, tactical breakout, and low-volatility templates, with live API smoke into the paper-first candidate path.
- [~] Options strategy templates. Evidence: [[2026-07-08-strategy-template-library-v1]]; v1 includes long-straddle and short-straddle research templates, but options chain/OI/IV/Greeks ingestion and payoff/risk gates remain open.
- [ ] OpenAlgo read-only bridge.
- [ ] Vibe-Trading pattern bridge.
- [ ] Full strategy portfolio optimizer UI.
- [ ] Probability-of-ruin dashboard.
- [ ] Strategy correlation dashboard.
- [ ] Strategy capacity dashboard.
- [ ] Strategy retirement dashboard v2.
- [ ] Strategy paper/live promotion board v2.
- [ ] Quant Lab committee room v2.

## 7. Active Trading Desk

- [~] Active Trading book mapping foundation.
- [~] Manual trade entry UI with book/purpose.
- [~] Paper trade entry UI with book/purpose.
- [~] Trade setup taxonomy foundation.
- [~] TradingView CDP connection foundation.
- [~] TradingView chart open workflow.
- [~] TradingView screenshot artifact capture.
- [~] TradingView action template registry.
- [x] Symbol Intelligence chart/snapshot/action buttons. Evidence: [[2026-07-07-symbol-intelligence-action-router-v1]]; Symbol Intelligence v2 now exposes Thesis, Exit, Risk, Research, Quant, Trade, and TV Prep action buttons plus existing TradingView Chart/Snapshot buttons. Actual TradingView execution still depends on CDP availability and remains tracked under controller hardening.
- [ ] TradingView production controller hardening.
- [ ] TradingView straddle/strangle action template.
- [ ] TradingView fundamental ratio chart workflow.
- [ ] Options payoff dashboard.
- [ ] IV/OI dashboard.
- [ ] Futures dashboard.
- [ ] Intraday alert monitor.
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
- [ ] Execution Safety Agent.
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
- [ ] Merger/spin-off detector.
- [ ] Open offer/tender offer detector.
- [ ] Auditor resignation detector.
- [ ] Rating change detector.
- [ ] Arbitrage spread monitor.
- [ ] Research Factory dashboard.
- [ ] News and Filings dashboard.
- [ ] Special Situations dashboard.
- [ ] Research Director agent.
- [ ] Corporate Actions Analyst agent.
- [ ] Arbitrage Analyst agent.
- [ ] News Analyst agent.
- [ ] Social/Twitter Triage Agent.
- [ ] Research Librarian agent.
- [ ] Document Extraction Agent.

## 9. Treasury, Hedges, Crypto, Commodities

- [ ] Cash/Treasury dashboard.
- [ ] Cash drag calculation.
- [ ] Liquid fund/cash equivalent tracking.
- [ ] Hedge position schema.
- [ ] Hedge intent field.
- [ ] Hedge ratio calculation.
- [ ] Hedge effectiveness review.
- [ ] Crypto exchange read-only connector.
- [ ] BTC/ETH watchlist and trade journal.
- [ ] Gold/silver/commodity instrument registry.
- [ ] Commodity OHLCV ingestion.
- [ ] Crypto/commodity risk limits.
- [ ] Crypto/Commodity Macro book.
- [ ] Treasury Analyst agent.
- [ ] Hedge Analyst agent.
- [ ] Crypto Analyst agent.
- [ ] Commodity Macro Analyst agent.

## 10. Capital Allocation Office

- [ ] Capital allocation schema.
- [ ] Capital budget by book.
- [ ] Risk budget by book.
- [ ] Capital drift dashboard.
- [ ] Book-level rebalance suggestions.
- [ ] Client-level allocation guardrails.
- [ ] Strategy allocation engine.
- [ ] Cross-book allocation review.
- [ ] Drawdown-aware sizing.
- [ ] Liquidity-aware sizing.
- [ ] Cash deployment queue.
- [ ] Opportunity-cost ranking.
- [ ] Capital Allocation Officer agent.
- [ ] Portfolio Optimizer agent.
- [ ] Performance Attribution Analyst agent.
- [ ] Client Suitability Analyst agent.
- [ ] Cash/Treasury Analyst agent.
- [ ] Capital Allocation Committee workflow.

## 11. Risk Office

- [~] Risk approval gate.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
- [~] Risk limits table across books/accounts/clients.
- [~] Risk limits dashboard.
- [~] Concentration engine.
- [ ] Liquidity risk engine.
- [ ] VaR engine.
- [ ] Expected shortfall engine.
- [ ] Stress test engine.
- [ ] Portfolio Monte Carlo paths.
- [ ] Options tail-risk model.
- [ ] Factor risk model.
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
- [ ] Kill Switch Agent.

## 12. Client Office

- [ ] Client onboarding workflow.
- [~] Client holdings foundation.
- [~] Client transactions foundation.
- [ ] Client-level NAV.
- [ ] Client-level book exposure.
- [ ] Client-level concentration.
- [ ] Client-level realized/unrealized P&L.
- [ ] Client risk profile.
- [ ] Client restrictions.
- [ ] Monthly client report.
- [ ] Portfolio change summary.
- [ ] Client action log.
- [ ] Client Folio dashboard.
- [ ] Client Manager agent.
- [ ] Reporting Analyst agent.
- [ ] Performance Reporter agent.
- [ ] Client Suitability Analyst agent.
- [ ] Communication Agent.
- [ ] Onboarding Agent.

## 13. Agent Office And Communication

- [~] Agent profiles foundation.
- [~] Agent departments foundation.
- [~] Agent skills foundation.
- [~] Agent task queue foundation.
- [~] Agent inbox foundation.
- [~] Agent messages foundation.
- [~] Agent approvals foundation.
- [~] Agent run logging foundation.
- [~] Charlie profile.
- [~] Jarvis profile.
- [~] Agent comments.
- [~] Agent output artifact registry.
- [~] Per-agent tool permissions UI.
- [~] Per-agent model route UI.
- [~] Agent mailbox UI.
- [~] Committee room view.
- [~] Approval board view.
- [~] Character/personality cards.
- [~] Agent hover cards.
- [~] Agent handoff threads.
- [~] Live AI Office room foundation.
- [ ] Agent reliability score.
- [ ] Agent productivity metrics.
- [ ] Task arrows between agents.
- [ ] Click-through agent profile pages.
- [ ] Agent discussion thread detail pages.
- [ ] Per-agent work history timeline.
- [ ] Per-agent cost and quality report.
- [ ] Department manager dashboards.
- [ ] Agent hiring/onboarding workflow.

## 14. Committees

- [~] Strategy Committee workflow.
- [~] Long-Term Investment Committee workflow.
- [~] Special Situations Committee workflow.
- [~] Committee room view.
- [ ] Executive Committee workflow.
- [ ] Tactical Committee workflow.
- [ ] Risk Committee workflow.
- [ ] Capital Allocation Committee workflow.
- [ ] Data and Tool Committee workflow.
- [ ] Client Review Committee workflow.
- [ ] Model Review Committee workflow.
- [ ] Execution Approval Committee workflow.
- [ ] Committee minutes generator.
- [ ] Evidence packet generator.
- [ ] Dissent capture.
- [ ] Decision audit trail.
- [ ] Follow-up task automation.

## 15. MCP And External Adapters

- [~] MCP server foundation. Evidence includes [[2026-07-08-strategy-template-library-v1]]; strategy template read/create tools are registered in API, MCP server, and `config/mcp_tools.yml`.
- [~] Obsidian/vault read-write path.
- [~] Postgres API tool path.
- [~] Browser profile registry.
- [~] Fincept local component installed.
- [~] Fincept skill registry added.
- [~] Vibe skill registry added.
- [~] TradingView CDP/chart-action executor foundation.
- [~] TradingView screenshot artifact API.
- [~] TradingView action template registry/API/MCP.
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
- [ ] TradingView straddle/strangle action template.
- [ ] TradingView fundamental ratio chart workflow.
- [ ] Provider policy editor UI.
- [ ] Provider policy simulator.

## 16. Dashboards And Live Office

- [~] Command Center foundation.
- [~] Portfolio widget foundation.
- [~] Book exposure widget.
- [~] Strategy Committee Gate panel.
- [~] Data-source freshness panel.
- [~] Agent task/inbox panels.
- [~] Long-Term Office dashboard foundation.
- [~] Quant Lab dashboard foundation.
- [~] AI Office live activity foundation.
- [~] Live snapshot/API contract for office, committee, chat, message, widget, portfolio, strategy, research, risk, and system surfaces. Evidence: `ai-office-ui/src/api/live.ts` and `/api/snapshot`.
- [x] Recovery schema parity for strategy templates and long-term coverage. Verified 2026-07-10: snapshot returned 36 agents, 10 rooms, 24 live activity records, 11 departments, 77 skills, 10 strategy templates, and no API query issues after applying migrations 108 and 109.
- [ ] Command Center shell extraction from monolithic `App.tsx` with no behavior loss.
- [~] Addressable Command Center / Live Office world routing with preserved context. Verified 2026-07-10: `?mode=office&workspace=risk` opens the office and the return action lands on `?mode=command&workspace=risk`; per-workspace module extraction remains outstanding.
- [~] Snapshot/UI/chat state layer. Verified 2026-07-10: `useLiveSnapshot` owns the 30-second warehouse poll, reconnect state, and initial empty/offline behavior; existing focused post-action refresh remains intact. Stale-data state and error boundary remain outstanding.
- [ ] Evidence drawer linking every displayed decision to source/task/artifact/message/approval rows.
- [ ] Mission Control v2: Charlie chat, delegation, inbox, approvals, daily brief, widget materialization.
- [ ] Quant Lab v2: intake through committee, paper/live promotion, validation, optimization, and evidence.
- [ ] Trading Desk v2: signals, TradingView, OI/intraday, paper monitor, and execution gates.
- [ ] Portfolio Office v2: client folios, books, positions, thesis, exposure, attribution, and remediation.
- [ ] Risk Center v2: limits, kill switches, conflicts, drift, stress, and Monte Carlo.
- [ ] Research Hub v2: long-term research, filings/news, special situations, source documents, and outputs.
- [ ] System Health v2: MCP, source, worker, provider, model, cost, storage, and recovery state.
- [ ] Portfolio Intelligence dashboard v3.
- [ ] Client Folio dashboard.
- [x] Symbol Intelligence dashboard v2. Evidence: [[2026-07-07-symbol-intelligence-v2]].
- [~] Long-Term Office dashboard v2. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; coverage board is now live inside Long-Term Thesis Control, but full client suitability and decision UI remain open.
- [ ] Tactical Office dashboard.
- [ ] Trading Desk dashboard.
- [ ] Risk Center dashboard.
- [ ] Capital Allocation dashboard.
- [ ] Research Factory dashboard.
- [ ] News and Filings dashboard.
- [ ] Special Situations dashboard.
- [ ] Treasury/Hedges/Crypto dashboard.
- [ ] Model Runtime dashboard.
- [ ] Provider Readiness dashboard v2.
- [ ] Committee Room dashboard v2.
- [~] 3D office scene with procedural rooms, stable camera controls, and live room placement. Verified 2026-07-10; room teleport remains outstanding.
- [~] Data-backed agent avatars: live status, current task, activity pulse, employee profile inspector, keyboard employee selector, and durable mailbox handoff. Verified 2026-07-10: Live Office message #61 created task #294 and inbox #379 for Risk Agent; profile pages and direct canvas hit testing remain outstanding.
- [~] Data-backed committee room: live agenda and decision state from committee queues. Participant, evidence, discussion, and follow-up drill-down remain outstanding.
- [~] Live handoff lines between agents. Verified 2026-07-10: the 3D office renders 11 deduplicated mailbox flows from `agent_messages`, with priority color and an auditable caption. Department KPI overlays, activity feed, risk wall, and alert wall remain outstanding.
- [~] Office non-WebGL and reduced-motion fallback. Verified 2026-07-10: static mode removes the canvas while retaining 10 live rooms, 36 selectable employee records, task inspection, mailbox handoff, and committee state. Automatic unsupported-WebGL fallback is present; broader assistive-technology review remains outstanding.
- [~] 3D office desktop/mobile pixel checks prove a nonblank, framed live canvas. Verified 2026-07-10 at 1440x1000 and 390x844; direct canvas-agent hit testing remains outstanding.
- [ ] Animated AI Office v1.
- [ ] Mobile/remote dashboard access.

## 17. Reports And Briefs

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
- [ ] Long-term thesis report.
- [ ] Valuation report.
- [ ] Monte Carlo report.
- [ ] Special situation report.
- [ ] Strategy report.
- [ ] Backtest report v2.
- [ ] Optimization report.
- [ ] Model validation report.
- [ ] Committee minutes report.
- [ ] Data-source freshness report.
- [ ] Provider readiness report.
- [ ] Cost report.
- [ ] Full system status report.

## 18. Model And Cost Controls

- [~] Model endpoint registry foundation.
- [~] Local model route foundation.
- [~] Ollama/local model runtime foundation.
- [~] Per-agent model route table.
- [~] Cost ledger.
- [~] Embedding model path.
- [ ] Daily driver model selected and benchmarked.
- [ ] Model call cache.
- [ ] Escalation policy.
- [ ] Cloud model approval flow.
- [ ] Model quality eval set.
- [ ] Local-vs-cloud routing tests.
- [ ] Context/RAG compression policy.
- [ ] Privacy restrictions per model route.
- [ ] Per-department model policies.

## 19. Production Safety

- [ ] Read-only broker connector policy enforced.
- [ ] Broker order execution disabled by default.
- [ ] Order preview schema.
- [ ] Human approval before any live order.
- [ ] Kill switch UI.
- [ ] Kill switch backend enforcement.
- [ ] Strategy live-enable approval policy.
- [ ] Client-report send approval policy.
- [ ] External-message approval policy.
- [ ] Data deletion approval policy.
- [ ] Secrets management policy.
- [ ] Audit log immutability.
- [ ] Backup/restore proof.
- [ ] Incident response runbook.

## 20. Immediate Next Implementation Order

- [x] Update top-level AI OS index to v10. Evidence: [[AI OS Master Blueprint]].
- [ ] Convert v10 blueprint into database-backed operating-model metadata.
- [x] Finish position readiness remediation queue and verify API/MCP/UI. Evidence: [[2026-07-07-position-readiness-remediation-queue-v1]].
- [x] Build Symbol Intelligence v2 around multi-book exposure. Evidence: [[2026-07-07-symbol-intelligence-v2]].
- [x] Add Symbol Intelligence action router into agent tasks/inbox. Evidence: [[2026-07-07-symbol-intelligence-action-router-v1]].
- [~] Harden p2cursor and old algo system extraction. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; readiness/run/issues/API/MCP/UI are live, but full mapping/promotion gaps remain.
- [x] Build Strategy Template Library v1. Evidence: [[2026-07-08-strategy-template-library-v1]]; migration, API route, MCP tools, dashboard panel, live API smoke, and build checks passed.
- [x] Implement Long-Term checklist tables and UI. Evidence: [[2026-07-08-long-term-coverage-board-v1]] plus existing live `portfolio.v_long_term_thesis_checklists` dashboard rows; table/API/UI are live, while row completion remains tracked by the coverage board.
- [ ] Implement Long-Term Monte Carlo engine and report.
- [ ] Implement research/news/filing collector expansion.
- [ ] Harden TradingView controller and straddle workflow.
- [ ] Build Client Folio dashboard.
- [ ] Build Risk Office v2 with stress tests and portfolio Monte Carlo.
- [ ] Build Animated AI Office v1 after core room grid and task arrows are data-backed.
