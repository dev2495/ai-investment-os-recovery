# AI Investment OS - Execution Checklist v9.0

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v9.0]]
Purpose: track the build from the current foundation to a complete AI hedge fund operating system.

Status legend:

- `[x]` done and verified by code, database, UI, report, runtime check, or smoke test.
- `[~]` partially implemented, prototype exists, or needs hardening.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without evidence. Add a note path, command, table, API check, UI check, screenshot, or report link before closing.

## 0. Canonical Docs And Governance

- [x] Create institutional master blueprint v9.0. Evidence: [[AI Investment OS - Institutional Master Blueprint v9.0]].
- [x] Create execution checklist v9.0. Evidence: this file.
- [x] Mark v9.0 as canonical in top-level AI OS index. Evidence: [[AI OS Master Blueprint]].
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
- [~] MCP server foundation.
- [~] Model endpoint registry.
- [~] Data-source connector registry.
- [~] Provider readiness board.
- [~] Provider assignment gates.
- [~] Department-level provider policy controls.
- [x] Blueprint v9 operating-model registry. Evidence: [[2026-07-07-blueprint-v9-operating-model-registry-v1]]; migration `102_blueprint_v9_operating_model.sql`, views `core.v_os_blueprint_v9_summary`, `core.v_os_blueprint_v9_domains`, `core.v_os_blueprint_v9_requirements`, API snapshot keys `blueprint_v9_summary`, `blueprint_v9_domains`, `blueprint_v9_requirements`, MCP tools `ai_os_blueprint_v9_summary` and `ai_os_blueprint_v9_requirements`, and AI Office `Blueprint v9 Coverage` panel verified.
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
- [ ] Full p2cursor extraction for all clients.
- [ ] Full buy/sell date extraction from p2cursor and broker reports.
- [ ] Full old algo trading DB import.
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
- [~] Position object complete with purpose, owner, horizon, thesis/setup, source, review cadence, exit logic, and approval state. Evidence: [[2026-07-07-position-object-v9-readiness-v1]]; table `books.book_positions` now has v9 fields for entry/source/approval/risk/capital/stop/target/time-exit/research/committee/journal/hedge/offset/review metadata, with readiness views showing remaining gaps.
- [x] Position object v9 readiness ledger. Evidence: [[2026-07-07-position-object-v9-readiness-v1]]; migration `103_position_object_v9_readiness.sql`, views `books.v_position_objects_v9`, `books.v_position_object_gap_summary`, `books.v_cross_book_coordination_questions`, API snapshot keys `position_objects_v9`, `position_object_gap_summary`, `cross_book_coordination_questions`, MCP tools `ai_os_position_objects_v9`, `ai_os_position_object_gap_summary`, `ai_os_cross_book_coordination_questions`, and AI Office panel `Position Object v9 Readiness` verified.
- [ ] Hedge ratio calculation.
- [ ] Offset-cost and tax-impact calculation.
- [ ] Capital used by book.
- [ ] Risk budget used by book.
- [ ] Book P&L attribution.
- [ ] Strategy attribution.
- [ ] Client folio book exposure page.
- [ ] Symbol Intelligence dashboard v2.
- [ ] Catalyst links in Symbol Intelligence.
- [ ] Trading setup links in Symbol Intelligence.
- [ ] Latest news/filing/task/committee notes in Symbol Intelligence.
- [ ] Cross-book conflict action workflow.
- [ ] Reliance-style opposite-exposure explanation UI.

## 4. Long-Term Investing Office

- [~] Company thesis schema.
- [~] Thesis version history.
- [~] Thesis killer table.
- [~] Exit criteria linked to holdings.
- [~] Quarterly review schedule.
- [~] Long-Term Office dashboard foundation.
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
- [ ] Business model checklist.
- [ ] Industry structure checklist.
- [ ] Moat scorecard.
- [ ] Management scorecard.
- [ ] Governance scorecard.
- [ ] Capital allocation scorecard.
- [ ] Financial statement quality scorecard.
- [ ] Forensic accounting checklist.
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
- [ ] Strategy hypothesis editor.
- [ ] Strategy DSL visual builder.
- [ ] Intraday strategy templates.
- [ ] Options strategy templates.
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
- [~] Symbol Intelligence chart/snapshot buttons.
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
- [ ] Portfolio Intelligence dashboard v3.
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
- [ ] Treasury/Hedges/Crypto dashboard.
- [ ] Model Runtime dashboard.
- [ ] Provider Readiness dashboard v2.
- [ ] Committee Room dashboard v2.
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

- [x] Update top-level AI OS index to v9. Evidence: [[AI OS Master Blueprint]].
- [ ] Reconcile v8 verified statuses into v9 with evidence links.
- [x] Convert v9 blueprint into database-backed department/book/committee metadata. Evidence: [[2026-07-07-blueprint-v9-operating-model-registry-v1]]; 21 operating domains and 35 core requirements are now warehouse-backed with owners, mapped runtime objects, acceptance criteria, and next actions.
- [~] Build complete position object and cross-book exposure ledger. Evidence: [[2026-07-07-position-object-v9-readiness-v1]]; institutional fields, gap scoring, readiness view, and coordination-question view are live; remaining work is to clear 142 thesis/exit gaps and add hedge ratio/cost/tax workflows.
- [ ] Build Symbol Intelligence v2 around multi-book exposure.
- [ ] Harden p2cursor and old algo system extraction.
- [ ] Implement Long-Term checklist tables and UI.
- [ ] Implement Long-Term Monte Carlo engine and report.
- [ ] Implement research/news/filing collector expansion.
- [ ] Harden TradingView controller and straddle workflow.
- [ ] Build Client Folio dashboard.
- [ ] Build Risk Office v2 with stress tests and Monte Carlo.
- [ ] Build Animated AI Office v1 after core room grid and task arrows are data-backed.
