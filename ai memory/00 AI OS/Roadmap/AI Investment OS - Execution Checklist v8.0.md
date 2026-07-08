# AI Investment OS - Execution Checklist v8.0

Date: 2026-07-06
Blueprint: [[AI Investment OS - Institutional Master Blueprint v8.0]]
Purpose: track the build from current foundation to complete AI hedge fund operating system.

Status legend:

- `[x]` done and verified by code, database, UI, report, runtime check, or smoke test.
- `[~]` partially implemented, prototype exists, or needs hardening.
- `[ ]` not implemented yet.

Rule: do not mark `[x]` without evidence. Add evidence note path, command, table, API check, UI screenshot, or report link before closing.

## 0. Canonical Docs And Governance

- [x] Create institutional master blueprint v8.0. Evidence: [[AI Investment OS - Institutional Master Blueprint v8.0]].
- [x] Create execution checklist v8.0. Evidence: this file.
- [x] Mark v8.0 as canonical in top-level AI OS index. Evidence: [[AI OS Master Blueprint]].
- [~] Architecture change-control policy. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [~] Decision log template. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [~] Committee minutes template. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [~] Evidence standard for checklist completion. Evidence: [[AI Investment OS - Governance Pack v1.0]].
- [ ] Architecture decision record table/API.
- [ ] Production data vs test data enforcement check.
- [ ] Investment disclaimer and human-control visible in UI.
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
- [~] Connector health-check dashboard.
- [~] Browser profile registry.
- [~] Data-source freshness monitor.
- [x] Model route and cost ledger. Evidence: [[2026-07-06-model-cost-ledger-v1]].
- [x] Per-agent cost caps. Evidence: [[2026-07-06-model-cost-ledger-v1]].
- [ ] Worker daemon health monitor.
- [ ] System health dashboard v2.
- [ ] Durable backup job.
- [ ] Restore test.
- [ ] Cloud escalation approval workflow.
- [ ] Local model daily-driver benchmark.
- [ ] Remote access plan and security model.

## 2. Data Spine

- [~] Client/account/holding import foundation.
- [~] Broker transaction import foundation.
- [~] Manual trade capture foundation.
- [~] Paper trade capture foundation.
- [~] Mark-to-market foundation for provided holdings.
- [~] Full p2cursor reconciliation against broker files. Evidence: [[2026-07-06-p2cursor-first-client-reconciliation]].
- [x] Source lineage view for portfolio rows. Evidence: [[2026-07-06-source-lineage-artifact-visibility]].
- [x] Raw artifact store for tracked imports. Evidence: [[2026-07-06-raw-artifact-import-coverage]].
- [ ] Full p2cursor extraction for all clients and buy/sell dates.
- [ ] Full algo trading DB import.
- [ ] Import historical equity curves.
- [ ] Import old strategy artifacts.
- [ ] Import old trade journals from 2018-19 onward.
- [ ] Import old Codex research outputs.
- [ ] Import old Claude/Cowork research outputs.
- [ ] Excel/CSV importer MCP.
- [ ] PDF/document extraction MCP.
- [ ] Live Zerodha read-only connector.
- [ ] Live Dhan read-only connector.
- [ ] Crypto exchange read-only connector.
- [ ] Daily OHLCV ingestion.
- [ ] Intraday OHLCV ingestion.
- [ ] Options chain/OI/IV ingestion.
- [ ] Futures basis ingestion.
- [ ] VIX/volatility ingestion.
- [ ] Gold/silver/commodity ingestion.
- [ ] Corporate action adjustment pipeline.
- [ ] Full reconciliation dashboard across broker, p2cursor, algo systems, and manual entries.
- [ ] Data quality score per source.
- [ ] Source freshness SLA per source.

## 3. Multi-Book Portfolio Brain

- [~] Investment book schema.
- [~] Core books: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges.
- [~] Position purpose taxonomy.
- [~] Current holdings mapped to Long-Term by default.
- [~] Book exposure views.
- [~] Cross-book conflict view.
- [~] Manual/paper trade routing into book positions.
- [x] Portfolio Intelligence dashboard v2. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]].
- [ ] Position object complete: purpose, owner, horizon, thesis/setup, source, review cadence, exit logic.
- [ ] Hedge ratio calculation.
- [ ] Offset-cost calculation.
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
- [~] Long-term Monte Carlo engine.
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
- [ ] Reverse DCF module.
- [ ] Sum-of-parts module.
- [ ] Peer comparison module.
- [ ] Historical valuation module.
- [ ] Bull/base/bear scenario builder.
- [ ] Expected CAGR calculator.
- [ ] Long-term Monte Carlo UI and committee integration.
- [ ] Sell discipline checklist.
- [ ] Thesis drift alerts.
- [ ] Quarterly review automation.
- [ ] Full Long-Term committee room UI.
- [ ] Human buy/hold/add/trim/sell decision UI.
- [ ] Long-Term Office dashboard v2.
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
- [x] Strategy retirement workflow. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; migration `088_strategy_retirement_quant_specialists_v1.sql`, script `run_strategy_retirement_review.py`, API `/api/strategy/retirement/run`, MCP `ai_os_run_strategy_retirement_review` / `ai_os_strategy_retirement_queue`, and dashboard panel verified with 10 real review rows and 38 specialist assignment rows from latest quant analytics/allocation evidence.
- [x] Strategy Generator agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; `agent.profiles` active with model route `strategy_generation`, present in Quant hierarchy and retirement workflow routing.
- [x] Strategy Research Agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; `agent.profiles` active with model route `strategy_generation`.
- [x] Strategy Intake Agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; `agent.profiles` active with model route `strategy_intake`.
- [x] Backtesting Engineer agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; `agent.profiles` active as `Backtest Engineer` with model route `strategy_backtest`.
- [x] Data Scientist agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; new active profile, mailbox, hierarchy, character `Dr. Sigma`, model assignment, skill map, and retirement assignment rows.
- [x] Feature Engineer agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; new active profile, mailbox, hierarchy, character `Ada Features`, model assignment, skill map, and retirement assignment rows.
- [x] Optimizer Agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; `agent.profiles` active with model route `strategy_optimizer`.
- [x] Regime Analyst agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; new active profile, mailbox, hierarchy, character `Morgan Regime`, model assignment, skill map, and retirement assignment rows.
- [x] Capacity/Liquidity Analyst agent. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; new active profile, mailbox, hierarchy, character `Casey Capacity`, model assignment, skill map, and retirement assignment rows.
- [x] Model Validation Agent dashboard. Evidence: [[2026-07-07-model-validation-promotion-board-v1]]; migration `089_model_validation_promotion_board_v1.sql`, script `run_model_validation_sweep.py`, API `/api/strategy/model-validation/sweep`, MCP `ai_os_run_model_validation_sweep` / `ai_os_model_validation_dashboard`, API snapshot key `model_validation_dashboard`, and AI Office panel verified with 20 keyed validation reviews, 9 `dsl_not_passed` rows, and 1 `validation_passed` row.
- [x] Quant Lab dashboard v2. Evidence: [[2026-07-07-strategy-retirement-quant-specialists-v1]]; API snapshot keys `strategy_retirement_queue`, `quant_specialist_assignments`, and `quant_lab_dashboard_v2` verified; React build passed; Playwright UI smoke found `Quant Lab v2 - Retirement & Specialists`, `Run Retirement Review`, `Data Scientist`, and `Regime Analyst`.
- [x] Strategy idea generator from trade journals. Evidence: [[2026-07-07-trade-journal-strategy-miner-v1]]; migration `090_trade_journal_strategy_mining_v1.sql`, script `run_trade_journal_strategy_mining.py`, API `/api/strategy/trade-journal-mining/run`, MCP tools `ai_os_run_trade_journal_strategy_mining` and `ai_os_trade_journal_strategy_ideas`, and AI Office panel `Trade Journal Strategy Miner` verified. Current source data is one real NIFTY short-straddle journal row, so generated ideas are gated as `thin_sample_backtest_required` with broker/autonomous live execution disabled.
- [x] Strategy optimizer from user-defined strategy. Evidence: [[2026-07-07-user-defined-strategy-optimizer-v1]]; migration `091_user_defined_strategy_optimizer_v1.sql`, script `run_user_defined_strategy_optimizer.py`, API `/api/strategy/user-defined-optimizer/run`, MCP tools `ai_os_run_user_defined_strategy_optimizer` and `ai_os_user_defined_strategy_optimizer_runs`, and AI Office panel `User Strategy Optimizer` verified. Smoke runs created candidates from user text, parsed DSL, passed real `trading.ohlcv` data quality over 1,431 `5m` rows, ran baseline backtests, ran optimizers with walk-forward/Monte Carlo diagnostics, and kept broker/autonomous live execution disabled.
- [x] Automatic strategy discovery engine from research, journals, signals, and component patterns. Evidence: [[2026-07-07-strategy-discovery-engine-v1]]; migration `092_strategy_discovery_engine_v1.sql`, script `run_strategy_discovery.py`, API `/api/strategy/discovery/run`, MCP tools `ai_os_run_strategy_discovery` and `ai_os_strategy_discovery_runs`, and AI Office panel `Strategy Discovery Agent` verified. Smoke runs scanned real `research.ideas`, journal-derived patterns, `trading.signals`, and `core.source_components`, created 32 `automatic_strategy_discovery` ideas across 4 runs, routed 4 candidates into the optimizer, and kept broker/autonomous live execution disabled.
- [x] Scheduled external-source strategy discovery loop. Evidence: [[2026-07-07-strategy-discovery-scheduler-external-sources-v1]]; migration `093_strategy_discovery_scheduler_external_sources_v1.sql`, scripts `ingest_market_news.py` and `run_strategy_discovery_scheduler.py`, daemon hook in `run_agent_message_daemon.py`, API `/api/market/news/ingest` and `/api/strategy/discovery/scheduler/run`, MCP tools `ai_os_ingest_market_news`, `ai_os_run_strategy_discovery_scheduler`, and `ai_os_strategy_discovery_scheduler_runs`, and AI Office controls `Ingest News` / `Source + Discovery` verified. Live smoke runs ingested public RSS rows into `market.news_items`, created source-backed news catalyst ideas, ran discovery scheduler through script/API/MCP, and kept X/Twitter marked `blocked_credentials` until authenticated browser/API access is connected.
- [x] Charlie/Jarvis discovered-idea triage and routing inbox. Evidence: [[2026-07-07-strategy-discovery-triage-v1]]; migration `094_strategy_discovery_triage_v1.sql`, script `resolve_strategy_discovery_triage.py`, API `/api/strategy/discovery/triage/resolve`, MCP tools `ai_os_resolve_strategy_discovery_triage` and `ai_os_strategy_discovery_triage_queue`, and AI Office triage buttons `Evidence`, `Quant`, `Special`, `Committee`, and `Reject` verified. Live smoke decisions covered all five lanes: reject, request more evidence, route Quant Lab, route Special Situations, and open committee review; 5 triage decisions, 4 triage inbox items, 1 linked committee review, and 1 linked approval were created with broker/autonomous live execution disabled.
- [x] Persistent strategy idea dossiers and semantic-memory indexing. Evidence: [[2026-07-07-strategy-idea-dossiers-v1]]; migration `095_strategy_idea_dossiers_v1.sql`, script `build_strategy_idea_dossiers.py`, Qdrant indexer update in `index_qdrant_documents.py`, API `/api/strategy/idea-dossiers/build`, MCP tools `ai_os_build_strategy_idea_dossiers` and `ai_os_strategy_idea_dossiers`, and AI Office `Build Dossiers` control verified. Live runs grouped 51 repeated discovery candidates into 10 persistent dossiers, wrote 10 Obsidian dossier notes, created 117 dossier links, and indexed 23 `strategy.idea_dossiers` chunks into `strategy_artifacts_mxbai_embed_large`; all 10 dossiers show `qdrant_index_status = indexed` with broker/autonomous live execution disabled.
- [x] Dossier semantic search and operating view. Evidence: [[2026-07-07-strategy-dossier-semantic-search-v1]]; migration `096_strategy_dossier_search_v1.sql`, script `search_strategy_idea_dossiers.py`, API `/api/strategy/idea-dossiers/search`, MCP tool `ai_os_search_strategy_idea_dossiers`, AI Office `Dossier Search` control, and Ollama LaunchAgent-backed `mxbai-embed-large` reindex verified. Live evidence: 2,212 Qdrant points indexed with `mxbai-embed-large`, 23 `strategy.idea_dossiers` chunks in the vector registry, and script/API/MCP/UI searches all returned Qdrant vector matches with `fallback_used = false`.
- [x] Dossier-to-workflow action bridge. Evidence: [[2026-07-07-strategy-dossier-action-workflow-v1]]; migration `097_strategy_dossier_action_workflow_v1.sql`, script `run_strategy_dossier_action.py`, API `/api/strategy/idea-dossiers/action`, MCP tools `ai_os_run_strategy_dossier_action` and `ai_os_strategy_dossier_actions`, and AI Office buttons `Evidence`, `Quant`, `Special`, `Committee`, `Memo` verified. Live evidence: 5 persisted dossier actions covering script/API/MCP/UI paths, Quant Lab routing, Special Situations routing, committee review creation, committee memo generation, and more-evidence routing; all action payloads show `paper_monitor_allowed=false` and `live_execution_allowed=false`.
- [x] Provider readiness board for plug-in models and data sources. Evidence: [[2026-07-07-provider-readiness-board-v1]]; migration `098_provider_readiness_board_v1.sql`, script `run_provider_readiness_sweep.py`, API `/api/providers/readiness/run`, MCP tools `ai_os_run_provider_readiness_sweep` and `ai_os_provider_readiness_board`, snapshot keys `provider_readiness_board`, `provider_readiness_summary`, and `provider_readiness_runs`, and AI Office `Provider Readiness Board` verified. Live evidence: 39 providers tracked, 23 ready, 6 approval-required, 4 blocked-secret, 2 blocked-browser, 4 needs-activation, 0 needs-check; TradingView remains correctly blocked until CDP is relaunched on port 9222.
- [x] Provider assignment gate for agent model/data-source use. Evidence: [[2026-07-07-provider-assignment-gate-v1]]; migration `099_provider_assignment_gate_v1.sql`, function `core.evaluate_provider_assignment_gate`, view `core.v_provider_assignment_gate_checks`, API `/api/providers/assignment-gate/evaluate`, MCP tools `ai_os_evaluate_provider_assignment_gate` and `ai_os_provider_assignment_gates`, snapshot key `provider_assignment_gates`, and AI Office `Gate` controls verified. Live evidence: 5 persisted gate checks across direct SQL, API, MCP, and UI paths; 2 ready/local provider assignments passed; 3 blocked provider assignments created inbox items for missing secret or TradingView CDP/browser block; live execution remains disabled.
- [x] Automatic task and worker provider-gate enforcement. Evidence: [[2026-07-07-task-provider-gate-automation-v1]]; migration `100_task_provider_gate_automation_v1.sql`, trigger `trg_auto_gate_task_providers_after_insert`, function `core.evaluate_task_provider_assignment_gates`, view `agent.v_task_provider_gate_status`, API `/api/tasks/provider-gates/evaluate`, MCP tools `ai_os_evaluate_task_provider_gates` and `ai_os_task_provider_gate_status`, AI Office task gate ledger, and worker preflight claim in `run_agent_worker_once.py` verified. Live evidence: new task `111` auto-passed local Jarvis route; task `112` auto-blocked explicit TradingView provider and created inbox `195`; API/MCP task gate rechecks persisted rows; worker preflight completed task `114` exactly once after atomic claim; task `112` stayed blocked while TradingView CDP remains offline.
- [x] Strategy paper/live promotion board. Evidence: [[2026-07-07-model-validation-promotion-board-v1]]; `strategy.v_strategy_promotion_board`, MCP `ai_os_strategy_promotion_board`, API snapshot key `strategy_promotion_board`, and UI panel verified; current live board shows 1 `committee_review_required`, 9 `dsl_not_passed`, and both `broker_order_allowed` and `autonomous_live_execution_allowed` remain false.

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
- [x] Alert inbox completion. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
- [~] TradingView screenshot visual-quality rejection gate.
- [ ] TradingView production controller hardening.
- [ ] Options payoff dashboard.
- [ ] IV/OI dashboard.
- [ ] Straddle/strangle chart workflow.
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

## 9. Cash, Treasury, Hedges, Crypto, Commodities

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
- [ ] Commodity macro analyst agent.

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
- [ ] Capital Allocation Officer agent.
- [ ] Portfolio Optimizer agent.
- [ ] Performance Attribution Analyst agent.
- [ ] Client Suitability Analyst agent.
- [ ] Cash/Treasury Analyst agent.

## 11. Risk Office

- [~] Risk approval gate.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
- [x] Risk limits table across books/accounts/clients. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]].
- [x] Risk limits dashboard. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]].
- [~] Concentration engine. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]].
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
- [~] Agent approvals foundation. Evidence: [[2026-07-06-approval-board-v1]].
- [~] Agent run logging foundation.
- [~] Charlie profile.
- [~] Jarvis profile.
- [x] Agent comments. Evidence: [[2026-07-06-agent-comments-v1]].
- [x] Agent output artifacts registry v2. Evidence: [[2026-07-06-output-artifact-registry-v2]].
- [x] Per-agent tool permissions UI. Evidence: [[2026-07-06-agent-employee-profiles-v1]].
- [x] Per-agent model route UI. Evidence: [[2026-07-06-agent-employee-profiles-v1]].
- [x] Agent mailbox UI. Evidence: [[2026-07-06-agent-mailbox-research-queue]].
- [x] Committee room view. Evidence: [[2026-07-06-committee-room-v1]].
- [x] Approval board view. Evidence: [[2026-07-06-approval-board-v1]].
- [x] Character/personality cards. Evidence: [[2026-07-06-agent-employee-profiles-v1]].
- [x] Agent hover cards. Evidence: [[2026-07-06-live-ai-office-v1]].
- [~] Agent handoff threads. Evidence: [[2026-07-06-agent-mailbox-research-queue]].
- [~] Live AI Office animated room. Evidence: [[2026-07-06-live-ai-office-v1]].
- [ ] Agent reliability score.
- [ ] Agent productivity metrics.
- [ ] Task arrows between agents.
- [ ] Click-through agent profile pages.
- [ ] Agent discussion thread detail pages.
- [ ] Per-agent work history timeline.
- [ ] Per-agent cost and quality report.

## 14. Committees

- [~] Strategy Committee workflow.
- [~] Long-Term Investment Committee workflow.
- [~] Special Situation committee workflow.
- [x] Committee room view. Evidence: [[2026-07-06-committee-room-v1]].
- [ ] Executive Committee workflow.
- [ ] Tactical Committee workflow.
- [ ] Risk Committee workflow.
- [ ] Capital Allocation Committee workflow.
- [ ] Data and Tool Committee workflow.
- [ ] Client Review Committee workflow.
- [ ] Committee minutes generator.
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
- [x] TradingView gated alert request path. Evidence: [[2026-07-06-tradingview-alert-inbox-live-verification]].
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

## 16. Dashboards

- [~] Command Center foundation.
- [~] Portfolio widget foundation.
- [~] Book exposure widget.
- [~] Strategy Committee Gate panel.
- [~] Data-source freshness panel.
- [~] Agent task/inbox panels.
- [~] Long-Term Office dashboard foundation.
- [~] Quant Lab dashboard foundation.
- [~] AI Office live activity foundation.
- [x] Portfolio Intelligence dashboard v2. Evidence: [[2026-07-06-risk-limits-portfolio-intelligence-v2]].
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
- [ ] Strategy report.
- [ ] Backtest report v2.
- [ ] Optimization report.
- [ ] Model validation report.
- [ ] Committee minutes report.
- [ ] Data-source freshness report.
- [ ] Cost report.
- [ ] Full system status report.

## 18. Model And Cost Controls

- [~] Model endpoint registry foundation.
- [~] Local model route foundation.
- [~] Ollama/local model runtime foundation.
- [x] Per-agent model route table complete. Evidence: [[2026-07-06-agent-employee-profiles-v1]].
- [x] Cost ledger. Evidence: [[2026-07-06-model-cost-ledger-v1]].
- [ ] Daily driver model selected and benchmarked.
- [~] Embedding model reliability test. Current proof: [[2026-07-07-strategy-dossier-semantic-search-v1]] verified Ollama LaunchAgent startup from SSD model storage, `/api/tags`, Qdrant reindex with `mxbai-embed-large`, and dossier search with no fallback. Remaining: scheduled health check, alerting, and automatic reindex retry policy.
- [ ] Model call cache.
- [ ] Escalation policy.
- [ ] Cloud model approval flow.
- [ ] Model quality eval set.
- [ ] Local-vs-cloud routing tests.
- [ ] Context/RAG compression policy.
- [ ] Privacy restrictions per model route.

## 19. Production Safety

- [~] Paper-first strategy activation gate.
- [~] Risk approval gate for limited-live requests.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
- [ ] Broker read-only mode enforcement.
- [ ] Account mapping verification.
- [ ] Instrument mapping verification.
- [ ] Order preview object.
- [ ] Human approval before broker order.
- [ ] Emergency kill switch UI.
- [ ] Live execution audit trail.
- [ ] Secrets audit.
- [ ] Backup/restore test.
- [ ] Privacy policy for client data.
- [ ] PII redaction policy for model calls.
- [ ] External access authentication and network security.

## 20. Immediate Build Order

- [x] Create v8 canonical blueprint and checklist. Evidence: [[AI Investment OS - Institutional Master Blueprint v8.0]] and this file.
- [ ] Verify current runtime health against v8 foundation checklist.
- [ ] Finish Strategy retirement workflow and Quant specialist agents.
- [ ] Build Quant Lab dashboard v2.
- [ ] Harden TradingView production controller.
- [ ] Complete p2cursor all-client extraction.
- [ ] Add algo DB import plan and first extraction.
- [ ] Build Client Folio dashboard.
- [ ] Build Symbol Intelligence dashboard v2.
- [ ] Add Long-Term Monte Carlo UI and committee integration.
- [ ] Build Research Factory news/filing dashboard.
- [ ] Add Fincept report/news/options bridge.
- [ ] Add OpenAlgo read-only bridge.
- [ ] Add Vibe workflow adapter.
- [ ] Add backup/restore and runtime health dashboard v2.

## 21. Whole-System Definition Of Done

- [ ] Devarsh can talk to Charlie and trigger auditable workflows.
- [ ] Jarvis can call approved tools, write outputs, and update dashboards.
- [ ] Every client, holding, transaction, trade, strategy, source, and report is traceable.
- [ ] Every position has book, purpose, owner, horizon, thesis/setup, and exit logic.
- [ ] Portfolio Intelligence shows gross/net/book/strategy/client/risk exposure.
- [ ] Symbol Intelligence explains why each exposure exists.
- [ ] Long-Term Office can produce complete thesis, valuation, bear case, Monte Carlo, and review memos.
- [ ] Tactical Office can manage events, catalysts, hedges, and options overlays.
- [ ] Research Factory can ingest filings/news/social data and create special-situation ideas.
- [ ] Quant Lab can intake, backtest, optimize, validate, paper-monitor, retire, and committee-review strategies.
- [ ] Trading Desk can log manual/paper trades and control TradingView tasks.
- [ ] Risk Office can block unsafe actions.
- [ ] Capital Allocation can allocate capital across books and detect conflicts.
- [x] Agent Office shows real tasks, inbox, runs, messages, model routes, outputs, and approvals. Evidence: [[2026-07-06-agent-employee-profiles-v1]].
- [ ] Live AI Office shows graphical employees, departments, work state, and task flow.
- [ ] Reports can be generated from source-backed data.
- [ ] Live execution remains human-approved and audit-logged.
