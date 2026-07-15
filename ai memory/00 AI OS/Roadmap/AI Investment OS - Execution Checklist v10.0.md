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
- [x] Adopt the Command Center plus 3D Live AI Office frontend delivery contract. Evidence: [[AI OS Command Center and 3D Office Frontend Plan]] and blueprint section 6.1.
- [x] Convert v10 domains and requirements into database-backed registry rows. Verified 2026-07-11 through parser-backed sync run `blueprint-v10-live-sync-20260711`; zero seed rows were created.
- [x] Architecture decision record table/API. `core.architecture_decisions` is exposed through the scoped Governance terminal and MCP control board; accepted changes are retained rather than overwritten. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Architecture change-control workflow. Material changes require objective, alternatives, consequences, blast radius, rollback plan, task, inbox item, and human approval before synchronization into the decision log. Live ratification request `#1` created task `#391`, inbox `#894`, and pending approval `#18`. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Decision log template. Active database-backed `architecture_decision_template` requires context, decision, alternatives, consequences, approval, and evidence. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Committee minutes template. Active database-backed `committee_minutes_template` requires agenda, participants, evidence, challenge, decision, dissent, and follow-ups. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Evidence standard visible in UI. The Governance terminal exposes the active evidence policy and the persistent terminal strip identifies the system as research and decision support. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [~] Production data vs test data enforcement check. Every scoped terminal reports `seed_data_allowed=false`, the Governance safety matrix passes the production boundary check, and policy rejects unlabeled synthetic records. Remaining gate: database-level environment/provenance enforcement across every future ingest table. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Investment disclaimer and human-control notice visible in UI. Every Command Center workspace states that Devarsh retains final investment authority; the full policy is queryable in Governance. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Broker execution safety constitution visible in UI. The persistent lock notice and database-backed constitution are live; the current warehouse state remains `read_only_blocked`, globally locked, and broker writes false. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Runtime disaster recovery runbook. Evidence: [[External SSD and AI OS Runtime Recovery Runbook]] and [[2026-07-11-ssd-recovery-blueprint-v10-frontend-contract]].

## 1. Foundation Runtime

- [x] Recovery storage layout: source code plus a small Git-tracked evidence snapshot on the Mac; vault, Docker disk image/volumes, model files, generated dependency cache, runtime logs/state, and heavy-data mirrors on the external SSD. Verified 2026-07-11 by `scripts/verify_external_storage.sh`; evidence: [[2026-07-11-runtime-command-model-readiness-v2]].
- [x] Docker services use the external SSD disk image. Verified again 2026-07-13 at `/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw`; a recurring containerd blob I/O state was recovered through a full Desktop stop/start after preserving `/Volumes/Devarsh SSD/AI OS Data/backups/docker-recovery-20260713/Docker.raw.pre-restart-clone`. Postgres, Qdrant, and Redis data remained intact. Evidence: [[External SSD and AI OS Runtime Recovery Runbook]].
- [x] Postgres warehouse foundation. Verified 2026-07-11 through `/api/health` and container health.
- [x] Redis foundation. Verified 2026-07-11 through the healthy `ai_os_redis` container.
- [x] Qdrant foundation. Verified 2026-07-11 with six live collections from `/collections`.
- [x] API server foundation. Verified 2026-07-11 at `http://127.0.0.1:8765/api/health` with Postgres and TradingView CDP checks passing.
- [x] AI Office dashboard shell. Verified 2026-07-11 at `http://127.0.0.1:5177/` through the deployed LaunchAgent build.
- [x] Obsidian vault memory surface. Verified 2026-07-11 at `/Volumes/Devarsh SSD/Obsidian memory ` with the runtime symlink preserved.
- [x] MCP server foundation. Verified 2026-07-15 with 150 importable tools, including scoped integration Gateway, strategy Arsenal, governance/change control, evidence, provider, source, portfolio, research, task, approval, browser, and workspace controls. Evidence: [[2026-07-15-data-model-integration-gateway-v1]], [[2026-07-15-governance-and-production-safety-v1]].
- [x] Model endpoint registry. Twenty-one synchronized model-provider plug-ins retain route, endpoint, readiness, cost, capability, and credential-reference contracts; absent models remain non-assignable. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Data-source connector registry. Eighteen source plug-ins synchronize from the connector registry into one readiness contract with health, freshness, mapping, schedule, access, and evidence gates. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Provider readiness board foundation with live model availability checks. Verified 2026-07-11 by readiness run `live-model-readiness-v2-20260711`; installed models are assignable and five absent Qwen routes are degraded/non-assignable.
- [x] Provider assignment gate foundation. Verified 2026-07-11 by Command Center task `#327` and provider gate inbox `#413`; approval policy held the task at `needs_review`.
- [~] Department-level provider policy controls.
- [x] Blueprint v9 operating-model registry. Evidence: [[2026-07-07-blueprint-v9-operating-model-registry-v1]].
- [x] Blueprint v10 operating-model registry. Verified 2026-07-11 through `core.v_os_blueprint_summary`, `core.v_os_blueprint_domains`, `core.v_os_blueprint_requirements`, API blueprint routes, and MCP tools `ai_os_blueprint_summary` and `ai_os_blueprint_requirements`.
- [x] Worker daemon health monitor. The 24/7 agent daemon now persists instance, PID, host, cadence, enabled workloads, last-pass status, error, and heartbeat age in `core.runtime_daemon_heartbeats`; SQL derives healthy/degraded/stale state for scoped System Health and MCP. Live LaunchAgent verification showed `running`, `healthy`, and a five-second heartbeat age after a complete source-intelligence pass. Evidence: [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].
- [x] System health dashboard v2. Verified 2026-07-13 through scoped `GET /api/system-health/snapshot`: 222 live rows across 18 bounded warehouse queries plus file-backed recovery evidence. The deployed UI exposes external storage, execution lock, blueprint v10, model/provider/source/connector state, two critical-backup generations, checksum presence, a 5.9 MB Postgres archive, a 2.11 GB Qdrant full snapshot, 327 copied vault files, both installed schedules, and the passed isolated restore artifact. Desktop/mobile browser checks used one scoped API request, no broad snapshot, no horizontal overflow, and the 23-case WCAG gate passed. Evidence: [[2026-07-13-system-health-v2-and-docker-runtime-recovery]], [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [~] Durable backup job. Format-v2 atomic backup completed at `~/AI_OS_CRITICAL_BACKUP/current` on 2026-07-13 with current/previous rotation, checksum manifest, Git bundle, Timescale/Postgres custom archive, full Qdrant snapshot, and vault copy. The signed helper and 03:20 LaunchAgent are installed without Full Disk Access. Remaining gate: unlock macOS once, open `~/Applications/AI OS Backup.app`, select the external vault, and pass the launchd scoped-access check. Evidence: [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [x] Restore test. The current backup was restored into isolated temporary services without modifying production: vault bytes matched, Git bundle verified, Timescale/Postgres row counts reconciled across 21 schemas and 457 tables, and all six Qdrant collections matched point counts. Evidence artifact: `/Volumes/Devarsh SSD/AI OS Data/artifacts/restore-drills/restore-drill-20260713T052952Z-33333.json`; note: [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [ ] Remote access plan and security model.
- [~] Local model daily-driver benchmark. `llama3.2:3b` is selected, installed on the SSD, GPU-loaded, returned `LOCAL MODEL READY`, and completed persisted chat turn `#44` with `model_status=called`; a comparative quality/throughput eval set remains open.
- [~] Cloud escalation approval workflow. A local-first, privacy/cost/provider-gated cloud escalation policy is active and visible. Remaining gate: dedicated request/simulation/approval/sync workflow per model call. Evidence: [[2026-07-15-governance-and-production-safety-v1]].

## 2. Data Spine

- [~] Client/account/holding import foundation.
- [~] Broker transaction import foundation.
- [~] Manual trade capture foundation.
- [~] Paper trade capture foundation.
- [~] Mark-to-market foundation.
- [~] Source lineage for portfolio rows.
- [x] Raw artifact store for imports. Verified in scoped Reports with 146 checksum-backed raw artifacts and 180 lineage rows. Evidence: [[2026-07-13-reports-v2]].
- [x] Legacy source extraction readiness board. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; migration `107_legacy_source_extraction_readiness.sql`, API snapshot keys, POST `/api/legacy-source-readiness/run`, MCP tools `ai_os_legacy_source_readiness` and `ai_os_run_legacy_source_readiness`, and AI Office dashboard panels verified.
- [x] Full p2cursor archive extraction and explicit resolution for the six available files. Canonical Tushit and Naval trade exports are promoted; the duplicate CARERATING export, frontend sample, empty archived SQLite database, and benchmark reference are explicitly classified rather than silently imported. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [~] Full buy/sell date extraction from p2cursor and broker reports. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; p2cursor trade CSV rows are staged, but normalized buy/sell-date promotion and broker reconciliation remain open.
- [~] Full old algo trading DB import. The immutable external-SSD databases pass SQLite integrity checks; 1,038,186 daily bars, 197,595 canonical ticks, 4,367 straddle snapshots, and bounded account/trade/holding/signal/idea/backtest tables are imported with hashes and run lineage. Historical equity curves, old strategy artifacts, complete journals, and all remaining low-volume tables still require explicit promotion or exclusion. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
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
- [~] Daily OHLCV ingestion. Real history covers 1,038,214 warehouse rows, 516 symbols, and 2016-01-01 through 2026-06-12; a representative strategy gate passed. A non-destructive corporate-action ledger, factor gate, adjusted view, and current-universe snapshot now exist, but zero factors and zero historical memberships are verified; stale-tail refresh and recurring live OHLCV ingestion remain open, so execution is blocked. Evidence: [[2026-07-15-legacy-market-data-spine-v1]], [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].
- [~] Intraday OHLCV ingestion. Real 5m/15m/1h bars and 197,595 canonical legacy ticks are live, but coverage is only about two trading days across 14 symbols and remains insufficient for validation. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [~] Options chain/OI/IV/Greeks ingestion. 4,367 real NIFTY straddle snapshots retain strike, call, put, net premium, spot, and average IV, but full chain, OI, Greeks, contract master, broader underlyings, expiries, and history remain open. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [ ] Futures basis ingestion.
- [ ] VIX/volatility ingestion.
- [ ] Gold/silver/commodity ingestion.
- [~] Corporate action adjustment pipeline. Real NSE/BSE filing events now populate 127 source-linked actions; 17 currently map to canonical symbols. Approved factor storage and a non-destructive adjusted-OHLCV view are live, but zero factors are verified/applied and 110 symbol mappings require review. Evidence: [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].
- [ ] Full reconciliation dashboard across broker, p2cursor, algo systems, and manual entries.
- [~] Data quality score per source. Legacy algo datasets now persist integrity checks, required-field/price/bounds/volume/future-row tests, canonical deduplication, bounded corrections, staleness, and research-bias contracts. Equivalent scoring remains to be applied to every live/provider dataset. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [~] Source freshness SLA per registered source. All 18 current source plug-ins expose targets. Global news now has a dedicated 15-minute daemon workload, aggregate source checks, and a verified fresh result over ten feeds and 56 real items. Seven other current source issues remain visible, and not-yet-onboarded connectors remain outside coverage. Evidence: [[2026-07-15-data-model-integration-gateway-v1]], [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].

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
- [x] Long-term Monte Carlo engine. Deterministic fundamental-driver simulation persists explicit assumptions, seed, distributions, probability summaries, warnings, valuation/thesis updates, audit lineage, and an Obsidian memo; no capital authority. Evidence: [[2026-07-06-long-term-monte-carlo-engine]], [[2026-07-13-long-term-decision-lab-v1]].
- [x] Long-term Monte Carlo UI. Holdings Research exposes a source-gated Decision Lab, live run evidence, valuation modules, checklists, artifact drill-down, and mobile-safe controls. Live UI run `#5` completed with no warnings and external-vault writeback. Evidence: [[2026-07-13-long-term-decision-lab-v1]].
- [~] Monte Carlo committee integration. Runs update thesis/valuation/research records and artifact lineage, and the committee queue is visible beside the Decision Lab. Remaining: embed distribution fields and explicit Monte Carlo challenge/follow-up actions in the committee decision packet. Evidence: [[2026-07-13-long-term-decision-lab-v1]].
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

- [x] Strategy intake workflow. The Strategy Arsenal provides an operator intake with hypothesis, family, asset class, symbols, universe, timeframe, constraints, and risk/invalidation fields; writes remain paper-first. Verified through the scoped API, live UI, database, MCP, and [[2026-07-15-strategy-arsenal-v1]].
- [x] Strategy candidate creation. Operator submissions, templates, and system discovery converge into the canonical candidate and promotion records; the control board currently covers every candidate without enabling broker orders. Evidence: [[2026-07-15-strategy-arsenal-v1]].
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
- [x] Automatic strategy discovery engine. Research, journal, signal, and component discovery runs create source-linked candidates and route only bounded top candidates into the paper-first optimizer path. Evidence: [[2026-07-07-strategy-discovery-engine-v1]], [[2026-07-07-strategy-discovery-scheduler-external-sources-v1]], and [[2026-07-15-strategy-arsenal-v1]].
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
- [x] Unified Strategy Arsenal lifecycle board v1. Provenance, DSL, data, baseline backtest, optimization, model validation, committee, paper-monitor, and limited-live gates are visible in one scoped terminal with evidence drill-down and an immutable broker-order false contract. Evidence: [[2026-07-15-strategy-arsenal-v1]].
- [ ] Quant Lab committee room v2.

## 7. Active Trading Desk

- [~] Active Trading book mapping foundation.
- [~] Manual trade entry UI with book/purpose.
- [~] Paper trade entry UI with book/purpose.
- [~] Trade setup taxonomy foundation.
- [~] TradingView CDP connection foundation. Verified 2026-07-10: guarded `_ai_os_runtime/scripts/relaunch_tradingview_cdp.sh` launches TradingView through macOS Launch Services with local-only CDP on `127.0.0.1:9222`; provider readiness marks `tradingview_mcp_connector` `ready`/assignable, and the 60-second daemon heartbeat mirrors CDP into browser-session check #8 and connector check #160. Broker execution remains disabled. Production chart-action hardening remains open.
- [~] TradingView chart open workflow.
- [~] TradingView screenshot artifact capture.
- [x] TradingView action template registry. Six advanced, approval-gated template contracts cover indicator stacks, ratio charts, spread formulas, four-pane straddles, fundamental ratios, and regime layouts. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Symbol Intelligence chart/snapshot/action buttons. Evidence: [[2026-07-07-symbol-intelligence-action-router-v1]]; Symbol Intelligence v2 now exposes Thesis, Exit, Risk, Research, Quant, Trade, and TV Prep action buttons plus existing TradingView Chart/Snapshot buttons. Actual TradingView execution still depends on CDP availability and remains tracked under controller hardening.
- [ ] TradingView production controller hardening.
- [~] TradingView straddle/strangle action template. Four-pane straddle contract and gated task/approval flow are live; deterministic TradingView mutation remains open. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] TradingView fundamental ratio chart workflow. Template and gated request contract are live; deterministic chart construction and evidence capture remain open. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
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

- [x] NSE/BSE filing collector foundation. Current exchange endpoints, pagination, India-time normalization, source checks, idempotent upserts, and scheduled two-day collection are live. Evidence: [[2026-07-15-research-intelligence-v1]].
- [x] Filing PDF extraction pipeline. Material-first selection, external artifact storage, bounded retries, extracted-text lineage, and scheduled runs are live. Evidence: [[2026-07-15-research-intelligence-v1]].
- [x] Research paper ingestion foundation. Public or approved-local PDFs are validated, stored on the external SSD, extracted, hashed, registered as raw artifacts, and routed into one idempotent review task. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Paper-derived strategy hypothesis foundation. Falsifiable hypotheses retain paper/hash/source lineage and cannot self-promote or execute. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Continuous paper discovery, citation graph, replication checks, and research-quality scoring.
- [~] Special situation memo workflow.
- [~] Special situation terms extraction.
- [~] Special situation spread decision workflow.
- [~] Event-symbol quote refresh from TradingView scanner.
- [x] News collector. Ten RSS feeds pass current health checks, including official RBI, Federal Reserve, and ECB sources; partial failures are recorded rather than hidden. Evidence: [[2026-07-15-research-intelligence-v1]].
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
- [~] Research Factory dashboard. Scoped thesis coverage, committee queue, outputs, filings, news, special situations, source health, and collector controls are live; detailed packet actions and the broader document-ingestion workflow remain open. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]], [[2026-07-15-research-intelligence-v1]].
- [~] News and Filings dashboard. Source Intelligence and Collector Runs expose feed health, scheduled runs, filing/news evidence, extraction state, and a guarded source-loop action. The production loop now separates 15-minute news freshness from hourly NSE/BSE filings, PDF extraction, and strategy discovery; source-document drill-down, X/Twitter credentials, and additional credentialed feeds remain open. Evidence: [[2026-07-15-research-intelligence-v1]], [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].
- [~] Special Situations dashboard. Live event inbox and memo visibility are deployed; full detector catalog, terms/spread actions, and arbitrage decisions remain open. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [ ] Research Director agent.
- [ ] Corporate Actions Analyst agent.
- [ ] Arbitrage Analyst agent.
- [~] News Analyst agent. The role owns scheduled RSS ingestion, health evidence, materiality scoring, research inbox routing, and dashboard alerts; quality evaluation and broader source coverage remain open. Evidence: [[2026-07-15-research-intelligence-v1]].
- [ ] Social/Twitter Triage Agent.
- [ ] Research Librarian agent.
- [~] Document Extraction Agent. Material-first filing PDF extraction is scheduled with external artifact lineage and bounded retries; general research-paper, annual-report, transcript, and OCR intake remains open. Evidence: [[2026-07-15-research-intelligence-v1]].

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
- [x] Capital Allocation Officer agent. Active as `Capital Allocation Agent` with Charlie reporting line, approval-only capital authority, mailbox, persona, guardrails, and terminal visibility. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Portfolio Optimizer agent.
- [x] Performance Attribution Analyst agent. Active as `Performance Attribution Agent` with durable profile and reporting line. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Client Suitability Analyst agent.
- [ ] Cash/Treasury Analyst agent.
- [ ] Capital Allocation Committee workflow.

## 11. Risk Office

- [~] Risk approval gate.
- [~] Strategy kill-switch enforcement.
- [~] Execution gate check ledger.
- [~] Risk limits table across books/accounts/clients.
- [~] Risk limits dashboard.
- [x] Concentration engine. Portfolio, book, and client scopes retain HHI, largest-position, and top-five exposure metrics from real active positions. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] Liquidity risk engine. Position-level 60-day median traded value, participation-rate capacity, days-to-liquidate, unavailable-history disclosure, and scope reconciliation are live; 23 of 45 current symbols remain data-insufficient. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] VaR engine. Historical 95/99 and coverage-adjusted bootstrap 1-day/10-day 99% VaR are live across portfolio, book, and client scopes. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] Expected shortfall engine. Historical 95/99 and bootstrap 1-day/10-day 99% expected shortfall are live with repeatable ES >= VaR validation. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] Stress test engine. Five portfolio/book/client scenarios cover broad-market shocks, top-position shocks, liquidity gaps, and historical worst-day replay. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] Portfolio Monte Carlo paths. Deterministic bootstrap simulations run at 1-day and 10-day horizons with configurable path count and seed; the verified run used 20,000 paths. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [ ] Options tail-risk model.
- [~] Factor risk model. NIFTY 50 beta/correlation/R-squared, residual risk, concentration, missing-history, and liquidity factors are live; sector/style/rates/FX/commodity/options-Greeks and correlation-cluster models remain. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [ ] Book conflict escalation.
- [ ] Risk Committee workflow.
- [ ] Risk override logging.
- [x] Risk block state dashboard. The Risk Center combines breach/warning checks, institutional risk status, global execution lock, limited-live requests, order intents, and guarded kill switch. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]], [[2026-07-15-governance-and-production-safety-v1]].
- [~] Chief Risk Officer agent. The active `Risk Agent` is the independent read-only Risk Officer and can challenge/block through evidence gates; formal CRO hierarchy, committee chairing, and scheduled reporting remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [~] Quant Risk Analyst agent. The active `Portfolio Risk Analyst` owns stress, factor, liquidity, scenario, and cross-book risk and now owns the institutional engine; dedicated scheduled worker cadence and specialist skill pack remain. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [ ] Stress Testing Agent.
- [ ] Model Risk Agent.
- [x] Data Quality Risk Agent. Active as `Data Quality Analyst`, reporting to Data Steward with mandatory escalation of material data failures. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Compliance/Audit Agent. Active as `Compliance Agent`, reporting to Risk Agent with independent exception controls. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
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

- [x] Agent profiles foundation. Forty-nine active profiles carry role scope, model policy, tools, permissions, guardrails, outputs, persona, cadence, cost policy, and human interface. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Agent departments foundation. Eleven live departments are exposed in the Agent Office terminal. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Agent skills foundation. Role-scoped tools, decision rights, consultation rules, and approval boundaries are registered for the active team. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] Agent task queue foundation.
- [~] Agent inbox foundation.
- [~] Agent messages foundation.
- [~] Agent approvals foundation.
- [~] Agent run logging foundation.
- [~] Charlie profile.
- [~] Jarvis profile.
- [~] Agent comments.
- [x] Agent output artifact registry. Scoped Reports exposes 164 durable outputs with search, family/status filters, owner/source/location, path copy, source links, safety flags, worker runs, and gap detection. Evidence: [[2026-07-13-reports-v2]].
- [~] Per-agent tool permissions UI.
- [~] Per-agent model route UI.
- [x] Agent mailbox UI. The Agent Office renders durable warehouse mail and the active team has addressable mailboxes; message handoffs remain audited tasks/inbox records. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] Committee room view.
- [~] Approval board view.
- [x] Character/personality cards. All active roles have warehouse-backed persona/operating-style data and office character identity; 3D art refinement remains separate. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
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

- [x] MCP server foundation. The importable 144-tool server now includes strategy, integration Gateway, provider, source, evidence, task, approval, browser, portfolio, research, and workspace contracts; smoke verification passed. Evidence: [[2026-07-08-strategy-template-library-v1]], [[2026-07-15-data-model-integration-gateway-v1]].
- [~] Obsidian/vault read-write path.
- [~] Postgres API tool path.
- [~] Browser profile registry.
- [~] Fincept local component installed.
- [~] Fincept skill registry added.
- [~] Vibe skill registry added.
- [~] TradingView CDP/chart-action executor foundation. Verified 2026-07-10: local Desktop CDP is available and provider-gated ready through the guarded relaunch script; native executor remains the runtime controller while the missing third-party candidate checkout is treated as optional, not a dependency.
- [~] TradingView screenshot artifact API.
- [x] TradingView action template registry/API/MCP. Six advanced chart contracts and approval-gated request flow are live; deterministic multi-pane mutation remains tracked under controller hardening. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Research paper ingestion/hypothesis MCP tools. Both source ingestion and source-linked hypothesis creation are registered in the permanent 138-tool MCP smoke gate. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
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
- [~] TradingView straddle/strangle action template. Contract and human gate are live; executor automation remains open. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] TradingView fundamental ratio chart workflow. Contract and human gate are live; executor automation remains open. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Provider policy editor UI.
- [ ] Provider policy simulator.

## 16. Dashboards And Live Office

- [x] Canonical frontend delivery plan linked to blueprint and checklist. Evidence: [[AI OS Command Center and 3D Office Frontend Plan]]; the live 49-agent registry overrides historical proposal counts.
- [x] Command Center foundation with durable delegation. Verified 2026-07-11 through the deployed UI: Charlie message `#94` routed to Research Analyst, created task `#327`, task inbox `#412`, and provider-policy inbox `#413`; no investment or trading action was requested or executed.
- [x] Portfolio widget foundation. Verified 2026-07-13 in the scoped Portfolio Office with production holdings, market value, gross/net exposure, investment books, position objects, conflicts, and readiness gaps. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [x] Book exposure widget. Verified 2026-07-13 for symbol-level multi-book and client-book exposure with client filtering. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [~] Strategy Committee Gate panel.
- [x] Data-source freshness panels. Mission Control and Live Office expose bounded live freshness rows; Live Office shows only stale/error/missing-check alerts. Evidence: [[2026-07-13-live-office-operations-v3]].
- [x] Agent task/inbox panels. Mission Control and Live Office expose durable priority tasks, current work, inbox, unread-message, blocked-work, and risk counts. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Long-Term Office dashboard foundation.
- [x] Quant Lab dashboard foundation. Scoped validation, promotion, committee, retirement/drift, and safe analytics controls are deployed against live strategy rows. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [x] Strategy Arsenal terminal v1. Operator intake, ten templates, source-backed discovery triage, validation sweep, origin/stage filters, eight promotion gates, next-required actions, and strategy evidence chains are deployed through a scoped endpoint. Broker orders remain zero and globally locked. Evidence: [[2026-07-15-strategy-arsenal-v1]].
- [x] AI Office live activity foundation. The office maps 36 employee records, 24 live activity rows, 10 rooms, mailbox handoffs, committee matters, priority work, risk events, freshness alerts, and execution control from the warehouse with no seed fallback. Evidence: [[2026-07-13-live-office-operations-v3]].
- [x] Live snapshot/API contract for every Command Center workspace and Live Office. Reports now uses `/api/reports/snapshot`; no UI route requests broad `/api/snapshot`. Evidence: [[2026-07-13-reports-v2]].
- [x] Recovery schema parity for strategy templates and long-term coverage. Verified 2026-07-10: snapshot returned 36 agents, 10 rooms, 24 live activity records, 11 departments, 77 skills, 10 strategy templates, and no API query issues after applying migrations 108 and 109.
- [~] Command Center shell extraction from monolithic `App.tsx` with no behavior loss. The production root now uses a compact scoped-only shell; the legacy function is unreferenced and tree-shaken. Main JS fell from 464.25 KB to 250.16 KB (46.1%), and the 18-test full workspace matrix passed. Physical removal of the legacy source function remains. Evidence: [[2026-07-13-scoped-command-shell-v2]].
- [x] Addressable Command Center / Live Office world routing with preserved context. All ten workspaces are independently mounted from scoped contracts. Office department rows now separate camera focus from an explicit mapped workspace action; `Runtime Operations` opens System Health in the verified browser flow. Evidence: [[2026-07-13-live-office-operations-v3]].
- [x] Snapshot/UI/chat state and containment layer. Every scoped workspace shows its live generated-at age, fresh/stale/loading/offline state, and retains focused refresh after writes. Workspace and Live Office render failures are contained by reloadable error boundaries; stale age updates locally without adding API requests. Evidence: [[2026-07-13-frontend-production-hardening-v2]].
- [x] Automated accessibility and keyboard gate. Checked-in Playwright plus axe covers all 17 Command Center workspaces at 1440 x 1000 and 390 x 844, approval-dialog focus trap/restoration, and Live Office static desktop/mobile fallbacks. All 37 WCAG A/AA cases pass, including keyboard access for shared terminal and Gateway overflow regions; the complete browser regression is 71/71. Playwright's version-matched browser payload is stored on the external SSD. Evidence: [[2026-07-13-frontend-production-hardening-v2]], [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Focused workspace snapshot profile and payload budget. Reports is 605 KB/0.23 s for 603 rows/12 queries; every UI workspace now uses a scoped contract and broad `/api/snapshot` is never requested by fresh routes. Evidence: [[2026-07-13-reports-v2]].
- [~] Evidence drawer linking every displayed decision to source/task/artifact/message/approval rows. The reusable v2 drawer and bounded `/api/evidence/entity/{kind}/{key}` contract now cover agent messages, tasks/provider gates, approvals, long-term/strategy committee packets, output artifacts, worker tasks, and source lineage. The live warehouse smoke covered all six whitelisted entity kinds; desktop/mobile approval/artifact/lineage workflows passed inside the 22-test matrix. Portfolio position/conflict and trading/quant/risk-specific drill-downs remain open. Evidence: [[2026-07-13-deep-evidence-and-approval-actions-v2]].
- [~] Mission Control v2: scoped live workspace now shows Charlie chat, durable delegations, executive inbox, approval queue, latest brief/chat turn, execution/provider gates, widget materialization, worker launch, source-freshness alerts, and task/message/approval evidence drawers. Pending approval decisions are live and explicitly do not grant broker authority. Scheduled daily-brief generation remains open. Evidence: [[2026-07-13-mission-control-v2-scoped-workspace]], [[2026-07-13-deep-evidence-and-approval-actions-v2]].
- [x] Governance and Safety terminal v1. Eleven active policies/templates, approval-backed architecture change control, live production-safety checks, immutable audit evidence, workspace customization, and persistent human-control/execution notices are deployed from a six-query scoped read model. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [~] Quant Lab v2: scoped validation, promotion, committee, retirement/drift, allocation/ruin visibility, and safe validation/analytics controls are deployed. Optimizer configuration, paper-monitor lifecycle controls, and evidence drawers remain. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [~] Trading Desk v2: live signals, TradingView controller tasks, manual/paper journal intake, paper-monitor visibility, and execution lock are deployed. OI/intraday workbench, template execution controls, and broker-gated execution workflow remain. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [~] Portfolio Office v2: scoped production workspace now provides client filtering, books, positions, multi-book exposure, portfolio intelligence, cross-book conflicts, and readiness remediation. Dedicated thesis packets, performance/factor attribution, and decision drill-downs remain open. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [~] Risk Center v2: live limits, breach/warning summary, execution lock, institutional VaR/ES, 20,000-path bootstrap risk, stress scenarios, concentration, liquidity, benchmark-factor attribution, limited-live requests, order intents, drift, refresh, and guarded global kill switch are deployed. Options tail risk, richer multi-factor/correlation models, conflict drill-downs, risk committee decisions, and order-risk evidence remain. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [~] Research Hub v2: scoped live long-term theses, committee review, filings/news, special situations, output artifacts, valuation models, checklists, and Long-Term Monte Carlo evidence/action are deployed. Long-term committee and output-artifact evidence drawers are live; filing/source-document actions, broader feeds, complete detectors, and remaining valuation calculators remain open. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]], [[2026-07-13-deep-evidence-and-approval-actions-v2]], [[2026-07-13-long-term-decision-lab-v1]].
- [x] System Health v2: scoped live MCP, source, worker, provider, model, cost, storage, pipeline, blueprint, execution-safety, and recovery state. Evidence: [[2026-07-13-system-health-v2-and-docker-runtime-recovery]].
- [~] Portfolio Intelligence dashboard v3. Portfolio overview, concentration, gross/net exposure, critical/risk-limit breach counts, books, conflicts, readiness, institutional VaR/ES, stress, liquidity, and benchmark-factor attribution are live; full sector/style/factor attribution and capital-allocation actions remain open. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [~] Client Folio dashboard. Live client registry, account-filtered holdings, client-book attribution, P2Cursor reconciliation, and approval-gated manual holding staging are deployed. Client onboarding/editing, suitability, cash flows, performance, and report generation remain open. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [x] Symbol Intelligence dashboard v2. Evidence: [[2026-07-07-symbol-intelligence-v2]].
- [~] Long-Term Office dashboard v2. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; coverage board is now live inside Long-Term Thesis Control, but full client suitability and decision UI remain open.
- [ ] Tactical Office dashboard.
- [~] Trading Desk dashboard. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [~] Risk Center dashboard. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [~] Capital Allocation dashboard. Scoped live terminal, book exposure, portfolio intelligence, cross-book conflicts, evidence, freshness, customization, and execution lock are deployed; allocation proposal/committee/rebalance actions remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] Research Factory dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] News and Filings dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] Special Situations dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] Treasury/Hedges/Crypto dashboard. Treasury and Macro terminal is live over source-backed macro/news/market records; dedicated hedge construction, collateral, cash ladder, and crypto execution connectors remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Data & Model Gateway terminal v1. The scoped terminal registers sources and model endpoints, exposes 39 plug-in readiness rows, validates 12 warehouse mappings, configures/runs seven allowlisted executor families, shows 21 routes, resolves integration evidence, and now includes strategy-data coverage/import/quality ledgers. Raw secrets, arbitrary commands, seed fallback, and broker authority are rejected. Evidence: [[2026-07-15-data-model-integration-gateway-v1]], [[2026-07-15-legacy-market-data-spine-v1]].
- [x] Provider Readiness dashboard v2. Model assignment readiness and source health/freshness are unified in the Gateway with filters, per-row checks, full sweeps, missing-credential/model actions, and evidence. Provider policy simulation and final department overrides remain separate open controls. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [~] Committee Room dashboard v2. Scoped live committee packet, approval state, evidence drawer, workspace customization, and execution lock are deployed; participant discussion, specialized decisions, and follow-up action routes remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] 3D office scene with procedural rooms, stable camera controls, live room placement, room-floor selection, and animated department focus. Directory selection moves the camera without leaving the office; an explicit secondary action opens the mapped Command Center workspace. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Data-backed agent avatars: live status, current task, activity pulse, live character name/color/visual traits, employee profile inspector, keyboard employee selector, and durable mailbox handoff. Verified 2026-07-10: Live Office message #61 created task #294 and inbox #379 for Risk Agent; profile pages and direct canvas hit testing remain outstanding.
- [~] Data-backed committee room: live agenda, decision state, source row, approval state, memo reference, structured evidence packet, and deep source-review/approval drill-down from committee queues. Verified with the TATASTEEL strategy review (`strategy.v_strategy_committee_queue #3`, pending approval #14, `reject_or_retest`); participant discussion and specialized committee decision/follow-up actions remain outstanding. Evidence: [[2026-07-13-deep-evidence-and-approval-actions-v2]].
- [~] Live handoff lines between agents. The 3D office renders deduplicated mailbox flows from `agent_messages`, with priority color and an auditable caption. The operations band now shows global execution lock, open risk events, stale/missing data sources, and priority tasks; the directory and inspector expose room/employee KPIs. A richer chronological activity feed remains outstanding. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Office non-WebGL and reduced-motion fallback. Static mode removes the canvas while retaining 10 live rooms, 36 selectable employee records, task inspection, mailbox handoff, and committee state. Automatic fallback is present and both static viewports pass WCAG A/AA automation; manual screen-reader and switch-device review remains outstanding. Evidence: [[2026-07-13-frontend-production-hardening-v2]].
- [x] 3D office desktop/mobile pixel checks prove a nonblank, framed live canvas. The permanent Live Office test reads the deployed WebGL buffer and requires more than 1,000 opaque and colored samples; desktop animated and mobile static screenshots are retained externally. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Animated AI Office v1. Procedural live rooms, animated agents, room focus, handoff lines, committee strip, operating walls, employee inspector, durable handoff, and static fallback are live. Character/art-direction refinement, direct automated canvas-agent hit testing, richer committee discussion, and chronological activity playback remain.
- [ ] Mobile/remote dashboard access.

## 17. Reports And Briefs

- [x] Reports workspace v2. Output registry, worker outputs, raw imports, lineage, gaps, import coverage, search/filter, deep evidence, ten live schedule rows, and recent run history are deployed from a 14-query scoped API. Four permanent desktop/mobile scheduler and recovery tests plus the 23-case WCAG gate pass. Evidence: [[2026-07-13-reports-v2]], [[2026-07-13-deep-evidence-and-approval-actions-v2]], [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [x] Obsidian report writeback foundation. The scheduler writes evidence-backed Markdown notes, then atomically registers task, inbox, worker, source-snapshot, output hash, and approval lineage.
- [~] Strategy Committee memo foundation.
- [~] Long-Term committee memo foundation.
- [~] Special situation memo foundation.
- [~] PDF report capability.
- [x] Daily market brief. Canonical period `2026-07-13` completed as run `#15`.
- [x] Daily portfolio brief. Canonical period `2026-07-13` completed as run `#16`.
- [x] Daily agent activity brief. Canonical period `2026-07-13` completed as run `#14`.
- [x] Weekly risk report. Canonical period `2026-W29` completed as run `#23`.
- [x] Weekly research digest. Canonical period `2026-W29` completed as run `#22`.
- [x] Monthly client report. Canonical period `2026-07` completed as draft run `#20`; external delivery remains blocked behind approval `#16`.
- [ ] Company research report.
- [ ] Long-term thesis report.
- [ ] Valuation report.
- [x] Monte Carlo report. Deterministic runs write source-backed distribution and guardrail memos to the external Obsidian vault; live UI run `#5` produced a checksum-verified note. Evidence: [[2026-07-13-long-term-decision-lab-v1]].
- [ ] Special situation report.
- [ ] Strategy report.
- [ ] Backtest report v2.
- [ ] Optimization report.
- [ ] Model validation report.
- [ ] Committee minutes report.
- [x] Data-source freshness report. Canonical period run `#17`.
- [x] Provider readiness report. Canonical period run `#21`.
- [x] Cost report. Canonical period run `#19`; it states recorded local/cloud usage rather than estimating unlogged spend.
- [x] Full system status report. Canonical period run `#18`.

## 18. Model And Cost Controls

- [x] Model endpoint registry foundation. Twenty-one endpoints are synchronized into the canonical integration plug-in manifest and exposed through API, MCP, and the Gateway terminal. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Local model route foundation. `always_on_daily_driver`, `jarvis_intake`, `jarvis_runtime`, daily brief, research, news, strategy intake, and trade-journal routes can use installed `llama3.2:3b`.
- [x] Ollama/local model runtime foundation. LaunchAgent startup is enabled by default, bound to `127.0.0.1:11434`, and model files remain under `/Volumes/Devarsh SSD/OllamaModels`.
- [~] Per-agent model route table.
- [~] Cost ledger.
- [x] Embedding model path. `mxbai-embed-large` is installed on the SSD and six Qdrant collections are registered against the embedding path.
- [x] Live model availability gate. API and readiness sweeps query Ollama `/api/tags`; installed `llama3.2:3b` is `configured`, while absent `qwen3:8b`/`qwen3:14b` routes are `model_unavailable` and non-assignable. Evidence: health checks `#773` and `#774`.
- [~] Daily driver model selected and smoke-benchmarked. `llama3.2:3b` direct cold-load verification completed in 9.73 seconds and Charlie chat turn `#44` used the model successfully; formal task-quality and sustained-throughput benchmarks remain open.
- [ ] Model call cache.
- [ ] Escalation policy.
- [ ] Cloud model approval flow.
- [ ] Model quality eval set.
- [ ] Local-vs-cloud routing tests.
- [ ] Context/RAG compression policy.
- [ ] Privacy restrictions per model route.
- [ ] Per-department model policies.

## 19. Production Safety

- [x] Read-only broker connector policy enforced. Global execution policy is `read_only_blocked`; no current connector may write broker orders. A future broker adapter must pass the separate limited-live constitution. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Broker order execution disabled by default. Live warehouse verification: `global_execution_locked=true`, `limited_live_allowed=false`, and `live_broker_writes_allowed=false`. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Order preview schema. `trading.order_intents` and `trading.order_risk_checks` retain the proposed order, notional, risk result, approval, gate state, and explicit false-by-default broker authority. Evidence: [[2026-07-15-governance-and-production-safety-v1]], [[2026-07-13-trading-quant-risk-v2]].
- [x] Human approval before any live order. `broker_order_intent` approval is independent from strategy, memo, or committee approval and remains required per order. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Kill switch UI. The Risk Center exposes the guarded global kill-switch action while every terminal displays current execution lock state. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-governance-and-production-safety-v1]].
- [x] Kill switch backend enforcement. `trading.engage_global_kill_switch` locks global execution, disables live writes, stops live instances, opens a critical risk event, and creates review work. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Strategy live-enable approval policy. Strategy committee approval cannot enable execution; limited-live request, risk limits, expiry, global policy, per-order approval, and execution/risk checks remain separate gates. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-governance-and-production-safety-v1]].
- [x] Client-report send approval policy. Scheduled client output is draft-only and run `#20` created pending human approval `#16`; no external-send or broker authority is granted.
- [~] External-message approval policy. Active policy requires preview, named human approval, channel allowlist, retained payload, and immutable audit. Remaining gate: enforce it in future email/social/client-message adapters. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [~] Data deletion approval policy. Active policy requires scope preview, retention check, backup evidence, approval, quarantine, and audit. Remaining gate: one database-backed quarantine/delete executor. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [~] Secrets management policy. Active policy requires credential references, least privilege, rotation, and redacted health checks. Remaining gate: automated repository and audit-payload secret scanning. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Audit log immutability. PostgreSQL trigger `trg_mcp_audit_append_only` rejects UPDATE and DELETE on `agent.mcp_audit_log`; a live mutation probe failed with the expected append-only exception. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Backup/restore proof. Format-v2 backup and isolated restore drill passed with retained JSON evidence. Evidence: [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [~] Incident response runbook. The active governance runbook covers containment, evidence preservation, kill switches, impact assessment, verified restore, postmortem, and reapproval, linked to the SSD recovery runbook. Remaining gate: incident simulation and formal response-time acceptance. Evidence: [[2026-07-15-governance-and-production-safety-v1]], [[External SSD and AI OS Runtime Recovery Runbook]].

## 20. Immediate Next Implementation Order

- [x] Update top-level AI OS index to v10. Evidence: [[AI OS Master Blueprint]].
- [x] Convert v10 blueprint into database-backed operating-model metadata. Canonical registry exposes 21 domains and machine-readable requirements through API and MCP. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Finish position readiness remediation queue and verify API/MCP/UI. Evidence: [[2026-07-07-position-readiness-remediation-queue-v1]].
- [x] Build Symbol Intelligence v2 around multi-book exposure. Evidence: [[2026-07-07-symbol-intelligence-v2]].
- [x] Add Symbol Intelligence action router into agent tasks/inbox. Evidence: [[2026-07-07-symbol-intelligence-action-router-v1]].
- [~] Harden p2cursor and old algo system extraction. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; readiness/run/issues/API/MCP/UI are live, but full mapping/promotion gaps remain.
- [x] Build Strategy Template Library v1. Evidence: [[2026-07-08-strategy-template-library-v1]]; migration, API route, MCP tools, dashboard panel, live API smoke, and build checks passed.
- [x] Implement Long-Term checklist tables and UI. Evidence: [[2026-07-08-long-term-coverage-board-v1]] plus existing live `portfolio.v_long_term_thesis_checklists` dashboard rows; table/API/UI are live, while row completion remains tracked by the coverage board.
- [x] Implement Long-Term Monte Carlo engine and report. Engine/API/MCP/database/report existed and the scoped Decision Lab, source gate, external-vault contract, real UI run, and browser tests are now verified. Evidence: [[2026-07-13-long-term-decision-lab-v1]].
- [x] Implement research/news/filing collector expansion. Dedicated 15-minute RSS freshness plus hourly NSE/BSE, material-first PDF extraction, strategy discovery, daemon health evidence, UI control, and agent routing are live. Evidence: [[2026-07-15-research-intelligence-v1]], [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]].
- [~] Harden TradingView controller and straddle workflow. Desktop CDP is healthy and six advanced chart-template contracts are registered with approval-gated requests; deterministic execution and verification of every multi-pane/indicator/formula mutation remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Build Client Folio dashboard.
- [~] Build Risk Office v2 with stress tests and portfolio Monte Carlo. The institutional calculation, API, MCP, audited action, responsive terminal, validation, and SSD-artifact foundation are live; options tail risk, richer factor/correlation models, Risk Committee/override workflows, and automated specialist cadence remain. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [ ] Build Animated AI Office v1 after core room grid and task arrows are data-backed.
