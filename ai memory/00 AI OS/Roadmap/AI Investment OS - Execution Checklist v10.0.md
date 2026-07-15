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

- [x] Recovery storage layout: source code plus Git history on the Mac; vault, Docker disk image/volumes, model files, generated dependency cache, runtime logs/state, heavy-data mirrors, and both critical-backup generations on the external SSD. `~/AI_OS_CRITICAL_BACKUP` is now a compatibility symlink to `/Volumes/Devarsh SSD/AI OS Data/backups/critical`, and the storage verifier fails if the resolved backup root is internal. Evidence: [[2026-07-11-runtime-command-model-readiness-v2]], [[2026-07-15-critical-backup-externalization]].
- [x] Docker services use the external SSD disk image. Verified again 2026-07-13 at `/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw`; a recurring containerd blob I/O state was recovered through a full Desktop stop/start after preserving `/Volumes/Devarsh SSD/AI OS Data/backups/docker-recovery-20260713/Docker.raw.pre-restart-clone`. Postgres, Qdrant, and Redis data remained intact. Evidence: [[External SSD and AI OS Runtime Recovery Runbook]].
- [x] Postgres warehouse foundation. Verified 2026-07-11 through `/api/health` and container health.
- [x] Redis foundation. Verified 2026-07-11 through the healthy `ai_os_redis` container.
- [x] Qdrant foundation. Verified 2026-07-11 with six live collections from `/collections`.
- [x] API server foundation. Verified 2026-07-11 at `http://127.0.0.1:8765/api/health` with Postgres and TradingView CDP checks passing.
- [x] AI Office dashboard shell. Verified 2026-07-11 at `http://127.0.0.1:5177/` through the deployed LaunchAgent build.
- [x] Obsidian vault memory surface. Verified 2026-07-11 at `/Volumes/Devarsh SSD/Obsidian memory ` with the runtime symlink preserved.
- [x] MCP server foundation. Verified 2026-07-15 with 174 callable tools, including canonical strategy-discovery governance and explicit agent-model assignment completeness in addition to model runtime, integration Gateway, strategy Arsenal, governance, evidence, provider, source, portfolio, research, task, approval, browser, schedule, committee, and workspace controls. Broad MCP smoke returned `tool_count=174`, `incomplete_model_assignments=0`, 39 integration plug-ins, 12 mappings, 6 jobs, and 95 orchestration rows. Evidence: [[2026-07-15-alpha-factory-and-plugin-readiness-v1]].
- [x] Model endpoint registry. Twenty-one synchronized model-provider plug-ins retain route, endpoint, readiness, cost, capability, and credential-reference contracts; absent models remain non-assignable. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Data-source connector registry. Eighteen source plug-ins synchronize from the connector registry into one readiness contract with health, freshness, mapping, schedule, access, and evidence gates. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Provider readiness board foundation with live model availability checks. Verified 2026-07-11 by readiness run `live-model-readiness-v2-20260711`; installed models are assignable and five absent Qwen routes are degraded/non-assignable.
- [x] Provider assignment gate foundation. Verified 2026-07-11 by Command Center task `#327` and provider gate inbox `#413`; approval policy held the task at `needs_review`.
- [x] Department-level provider policy controls. All 95 active role-scoped agents have a governed route and explicit model-catalog assignment; 83 resolve to installed-local models and 12 remain gated/optional with fallbacks. `agent.v_agent_model_assignment_completeness` reports zero incomplete assignments and autonomous cloud remains zero. Evidence: [[2026-07-15-alpha-factory-and-plugin-readiness-v1]].
- [x] Blueprint v9 operating-model registry. Evidence: [[2026-07-07-blueprint-v9-operating-model-registry-v1]].
- [x] Blueprint v10 operating-model registry. Verified 2026-07-11 through `core.v_os_blueprint_summary`, `core.v_os_blueprint_domains`, `core.v_os_blueprint_requirements`, API blueprint routes, and MCP tools `ai_os_blueprint_summary` and `ai_os_blueprint_requirements`.
- [x] Worker daemon health monitor. The 24/7 agent daemon persists instance, PID, host, cadence, enabled workloads, last-pass status, error, and heartbeat age. Every enabled startup workload now uses bounded direct PostgreSQL connections when the local 0600 runtime env is present; Docker CLI fallback cannot silently hang the production LaunchAgent. Live verification showed `running`, `healthy`, TradingView `ok`, no last error, and no Docker psql child after a complete pass. Evidence: [[2026-07-15-runtime-source-intelligence-and-bias-controls-v1]], [[2026-07-15-research-paper-operator-and-daemon-hardening-v1]].
- [x] System health dashboard v2. Verified 2026-07-13 through scoped `GET /api/system-health/snapshot`: 222 live rows across 18 bounded warehouse queries plus file-backed recovery evidence. The deployed UI exposes external storage, execution lock, blueprint v10, model/provider/source/connector state, two critical-backup generations, checksum presence, a 5.9 MB Postgres archive, a 2.11 GB Qdrant full snapshot, 327 copied vault files, both installed schedules, and the passed isolated restore artifact. Desktop/mobile browser checks used one scoped API request, no broad snapshot, no horizontal overflow, and the 23-case WCAG gate passed. Evidence: [[2026-07-13-system-health-v2-and-docker-runtime-recovery]], [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [~] Durable backup job. Both format-v2 generations were byte-compared after migration to `/Volumes/Devarsh SSD/AI OS Data/backups/critical`; the current generation's recorded checksums passed, the internal 4 GB duplicate was removed, and `~/AI_OS_CRITICAL_BACKUP` now resolves externally. The signed 03:20 helper and installed LaunchAgent both carry the external root. Remaining gate: complete one fresh unattended backup through the helper after granting removable-volume access; a manual fresh full-Qdrant attempt was stopped after long snapshot creation and did not replace the verified current generation. Evidence: [[2026-07-13-backup-restore-and-scheduled-reports-v1]], [[2026-07-15-critical-backup-externalization]].
- [x] Restore test. The current backup was restored into isolated temporary services without modifying production: vault bytes matched, Git bundle verified, Timescale/Postgres row counts reconciled across 21 schemas and 457 tables, and all six Qdrant collections matched point counts. Evidence artifact: `/Volumes/Devarsh SSD/AI OS Data/artifacts/restore-drills/restore-drill-20260713T052952Z-33333.json`; note: [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- [ ] Remote access plan and security model.
- [~] Local model daily-driver benchmark. `llama3.2:3b` is selected, installed on the SSD, GPU-loaded, returned `LOCAL MODEL READY`, and completed persisted chat turn `#44` with `model_status=called`; a comparative quality/throughput eval set remains open.
- [x] Cloud escalation approval workflow. Every request binds to a hashed model-call decision. Client-private/restricted requests are rejected without creating approval; public/internal requests create a high-risk human approval, and approval resolution synchronizes state without executing a cloud call. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].

## 2. Data Spine

- [x] Client/account/holding import foundation. Existing production state is preserved and the accounting runner scopes four real imported client accounts with transactions; no validation or seed accounts remain. Evidence: [[2026-07-15-client-office-control-plane-v1]], [[2026-07-15-client-accounting-performance-reporting-v1]].
- [x] Broker transaction import foundation. The live accounting path consumes 848 real transactions across four accounts and posts 744 non-zero broker-statement settlement amounts as immutable cash evidence. Missing history is flagged rather than synthesized. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Manual trade capture foundation.
- [~] Paper trade capture foundation.
- [~] Mark-to-market foundation.
- [~] Source lineage for portfolio rows.
- [x] Raw artifact store for imports. Verified in scoped Reports with 146 checksum-backed raw artifacts and 180 lineage rows. Evidence: [[2026-07-13-reports-v2]].
- [x] Legacy source extraction readiness board. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]]; migration `107_legacy_source_extraction_readiness.sql`, API snapshot keys, POST `/api/legacy-source-readiness/run`, MCP tools `ai_os_legacy_source_readiness` and `ai_os_run_legacy_source_readiness`, and AI Office dashboard panels verified.
- [x] Full p2cursor archive extraction and explicit resolution for the six available files. Canonical Tushit and Naval trade exports are promoted; the duplicate CARERATING export, frontend sample, empty archived SQLite database, and benchmark reference are explicitly classified rather than silently imported. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [~] Full buy/sell date extraction from p2cursor and broker reports. Normalized dates now drive deterministic FIFO over 848 real trades and two accounts complete without breaks. Sanjana and the Tushit broker statement still expose one and 27 source-history position breaks, respectively, so historical coverage is not complete. Evidence: [[2026-07-07-legacy-source-extraction-readiness-v1]], [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Full old algo trading DB import. The immutable external-SSD databases pass SQLite integrity checks; 1,038,186 daily bars, 197,595 canonical ticks, 4,367 straddle snapshots, and bounded account/trade/holding/signal/idea/backtest tables are imported with hashes and run lineage. Historical equity curves, old strategy artifacts, complete journals, and all remaining low-volume tables still require explicit promotion or exclusion. Evidence: [[2026-07-15-legacy-market-data-spine-v1]].
- [ ] Historical equity curve import.
- [ ] Old strategy artifact import.
- [ ] Old trade journal import from 2018-19 onward.
- [x] Codex research output collector. Bounded local output roots are checksum-indexed into `core.raw_artifacts` with private sensitivity, family/topic metadata, summary, and Research Hub visibility. Evidence: [[2026-07-15-research-paper-operator-and-daemon-hardening-v1]].
- [x] Claude/Cowork research output collector. Bounded Claude/Cowork output roots share the same idempotent checksum registry and one-place Research Hub/MCP search; the live registry contains 91 AI research, dashboard, and model outputs in total. Evidence: [[2026-07-15-research-paper-operator-and-daemon-hardening-v1]].
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
- [~] Full reconciliation dashboard across broker, p2cursor, algo systems, and manual entries. A normalized source-observation ledger, account-scoped reconciliation function, symbol-level break ledger, bounded API/MCP read-write paths, and Client Folio control board are live without auto-apply. P2Cursor remains separately visible. Remaining: connect recurring Zerodha/Dhan/algo feeds and resolve their real break queues. Evidence: [[2026-07-15-client-office-control-plane-v1]].
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
- [x] Client folio book exposure page. Client Folios exposes account-scoped positions, book attribution, gross/net exposure, opposite-book conflicts, accounting state, and source evidence. Evidence: [[2026-07-15-client-office-control-plane-v1]], [[2026-07-15-client-accounting-performance-reporting-v1]].
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
- [~] Client-level long-term suitability review. The governed onboarding path creates evidence-backed suitability records and blocks activation unless status is suitable or conditionally suitable with risk tolerance, risk capacity, and horizon present. All three imported clients remain visibly `missing`, so retrospective mandate capture and long-term book-fit review remain open. Evidence: [[2026-07-15-client-office-control-plane-v1]].

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
- [x] Automatic strategy discovery engine. Research, journal, signal, and component discovery runs now canonicalize stable opportunity and source identities, retain every historical observation, suppress repeated scheduler rows from the operating queue, and reuse unchanged optimizer evidence inside the configured cooldown. Live acceptance retained 787 candidate-history rows as evidence while exposing 17 canonical opportunities and suppressing 770 duplicates; two distinct runs created no new candidate rows and routed zero redundant optimizer runs. Evidence: [[2026-07-15-alpha-factory-and-plugin-readiness-v1]].
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
- [x] Unified Strategy Arsenal lifecycle board v1. Provenance, DSL, data, baseline backtest, optimization, model validation, committee, paper-monitor, and limited-live gates are visible in one scoped terminal with evidence drill-down, canonical discovery identity, seen/suppressed counts, and real operator controls for each permitted next gate. The full snapshot returns 15 unique lifecycle candidates, one validation-passed candidate, zero paper monitors, and zero broker-authorized candidates. Six desktop/mobile Playwright cases passed under four-worker load. Evidence: [[2026-07-15-alpha-factory-and-plugin-readiness-v1]].
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
- [x] Research paper ingestion foundation. Public or approved-local PDFs are validated, stored on the external SSD, extracted, hashed, registered as raw artifacts, and routed into one idempotent review task. The Research terminal now provides governed URL/local-path intake and source-linked hypothesis forms; neither route can promote a backtest or trade. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]], [[2026-07-15-research-paper-operator-and-daemon-hardening-v1]].
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

- [x] Capital allocation schema. Governed policy proposals, six-book rules, analysis runs/lines, committee reviews, approvals, and bounded operating views are live without policy seed. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Capital budget by book. Operator-entered target/min/max contracts and current observed percentages are live; all three clients still require Devarsh to define policy. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Risk budget by book. Ten-day 99% VaR budget fields, observed-risk comparison, and block state are live; real user budgets and broader factor/tail budgets remain open. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [x] Capital drift dashboard. The Capital terminal exposes 18 real client/book rows, policy readiness, drift, risk coverage, analysis, and committee state. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Book-level rebalance suggestions. Target-notional and increase/decrease previews are calculated only after policy/risk review and cannot create orders; cash, tax, suitability, and complete capital basis remain open. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Client-level allocation guardrails. All-book coverage, 100% totals, min/target/max ranges, data coverage, risk budgets, committee review, and Devarsh approval are enforced; client suitability, restrictions, cash, and tax records remain open. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Strategy allocation engine. Existing strategy portfolio analytics remain separate from the new client/book capital policy; governed strategy-to-book budget integration remains open.
- [~] Cross-book allocation review. All six books are analyzed together with committee routing; economic-offset and opportunity-cost logic remains open. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Drawdown-aware sizing. Maximum drawdown budget fields and observed client drawdown are available; sizing rules are not yet implemented.
- [~] Liquidity-aware sizing. Institutional risk coverage gates policy analysis and blocks inadequate data; position-level capacity and proposed-order sizing integration remain open. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [ ] Cash deployment queue.
- [ ] Opportunity-cost ranking.
- [x] Capital Allocation Officer agent. Active as `Capital Allocation Agent` with Charlie reporting line, approval-only capital authority, mailbox, persona, guardrails, and terminal visibility. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Portfolio Optimizer agent.
- [x] Performance Attribution Analyst agent. Active as `Performance Attribution Agent` with durable profile and reporting line. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [ ] Client Suitability Analyst agent.
- [ ] Cash/Treasury Analyst agent.
- [~] Capital Allocation Committee workflow. Independent risk must pass before Charlie's committee recommendation can create a separate Devarsh approval; approved policy cannot authorize capital movement or broker orders. No real policy has entered committee yet. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].

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

- [x] Client onboarding workflow. Intake captures objectives, constraints, horizon, liquidity, risk tolerance/capacity, suitability, account scope, and source evidence; Charlie/Devarsh approval atomically activates client/account/suitability records, while the generic approval route is blocked. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [x] Client holdings foundation. Seventy-four real position rows remain intact; manual updates stage a dedicated approval and cannot alter `portfolio.positions` until evidence-backed human resolution. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [x] Client transactions foundation. Eight hundred forty-eight real trades are normalized into account-scoped FIFO and cash-settlement processing with explicit source lineage. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Client-level NAV. NAV snapshots, cash/liability/accrual fields, source lineage, completeness gates, API/MCP control, and Client Folio UI are live. Tushit's broker statement has source-snapshot NAV of INR 10,766,939.34; the other current-holding accounts correctly remain incomplete pending opening cash evidence. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [x] Client-level book exposure. Live Client Folios exposes current multi-book attribution, symbol exposure, gross/net exposure, purposes, and cross-book conflicts over real holdings. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]], [[2026-07-15-client-office-control-plane-v1]].
- [~] Client-level concentration. Institutional risk supports client scope and the folio exposes current exposure; a dedicated client concentration policy/limit workflow is still open. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]], [[2026-07-15-client-office-control-plane-v1]].
- [~] Client-level realized/unrealized P&L. Deterministic long/short FIFO, open lots, realized matches, source-backed unrealized holdings, cash ledger, fee ledger, and realized attribution are live. Two accounts complete without lot breaks; Sanjana and the Tushit broker statement remain incomplete pending historical transactions, and explicit fee/tax evidence is not yet complete across brokers. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Client risk profile. The lifecycle schema and onboarding approval enforce risk-profile and suitability inputs; the three imported clients still require retrospective completion. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [~] Client restrictions. Structured constraints and restricted-asset fields are live in onboarding/suitability; imported-client population and enforcement at order-risk time remain open. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [~] Monthly client report. The July scheduler generated three separate source-backed Obsidian drafts and three independent pending delivery approvals; generic approval bypass is blocked and external send remains false. Client-ready formatting, richer narrative, recurring acceptance, and an approved delivery adapter remain open. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Portfolio change summary. Drafts expose current holdings, books, NAV/performance, FIFO coverage, reconciliation, and accounting gaps; a reconciled period-over-period change narrative is still open because complete recurring NAV and lot history are unavailable. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Client action log. Onboarding, account changes, holding changes, approvals, inbox routing, and append-only API/MCP audit events are retained; a consolidated human-readable timeline remains open. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [x] Client Folio dashboard. Responsive Bloomberg-style Client Folios now combines registry, suitability gaps, current holdings, governed intake, account maintenance, holding approvals, client-book attribution, P2Cursor reconciliation, and normalized multi-source reconciliation. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [~] Client Manager agent. Charlie owns final onboarding review and Portfolio Manager owns folio/account lifecycle with role-scoped skills; a separately named Client Manager profile and recurring cadence remain open. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [x] Reporting Analyst agent. Active `Client Reporting Agent` consumes client/account scope and owns draft-only reporting support; external send remains separately approved. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]], [[2026-07-15-client-office-control-plane-v1]].
- [~] Performance Reporter agent. The active Client Reporting Agent can consume deterministic NAV, Modified Dietz performance, NIFTY 50 benchmark, FIFO, and attribution views and creates draft-only reports. A dedicated recurring Performance Reporter profile and richer attribution narrative remain open. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Client Suitability Analyst agent. Charlie and Portfolio Manager have the governed onboarding skill and the deterministic suitability ledger is live; a dedicated specialist profile, retrospective imported-client reviews, and order-fit enforcement remain. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [ ] Communication Agent.
- [~] Onboarding Agent. The workflow, skill, inbox, approval, API, MCP, and terminal controls are live under Charlie and Portfolio Manager; a separately named scheduled Onboarding Agent remains open. Evidence: [[2026-07-15-client-office-control-plane-v1]].

## 13. Agent Office And Communication

- [x] Agent profiles foundation. Ninety-five active profiles carry role scope, hierarchy, model policy, tools, permissions, guardrails, outputs, persona, mental models, cadence, cost policy, and human interface. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
- [x] Agent departments foundation. Fifteen live departments are exposed in the Agent Office terminal. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
- [x] Agent skills foundation. The active team has 117 active skills and 166 role-to-skill mappings with scoped tools, decision rights, consultation rules, and approval boundaries. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
- [x] Agent task queue foundation. The deterministic worker queue, task state transitions, retries, and failure recovery are live.
- [x] Agent inbox foundation. Every active employee has one unique active mailbox and durable queue state.
- [x] Agent messages foundation. Internal assignments and handoffs are durable and Jarvis-routed.
- [x] Agent approvals foundation. The central Approval Board and dedicated atomic resolvers expose live pending/resolved decisions while capital, broker, client, cash, report, and architecture authorities remain separate. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] Agent run logging foundation. Completed and failed runs retain worker, task, evidence, model, timing, and recovery state.
- [x] Charlie profile. Charlie is the chief orchestrator and Devarsh-facing decision partner with explicit escalation and human-control boundaries.
- [x] Jarvis profile. Jarvis is the runtime operator and dispatcher; it routes work but does not replace specialist ownership.
- [~] Agent comments.
- [x] Agent output artifact registry. Scoped Reports exposes 164 durable outputs with search, family/status filters, owner/source/location, path copy, source links, safety flags, worker runs, and gap detection. Evidence: [[2026-07-13-reports-v2]].
- [~] Per-agent tool permissions UI.
- [x] Per-agent model route UI. Every active employee exposes its explicit primary/fallback/escalation route and hard cost policy.
- [x] Agent mailbox UI. The Agent Office renders durable warehouse mail and the active team has addressable mailboxes; message handoffs remain audited tasks/inbox records. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Committee constitution view. Eleven committee constitutions expose chair, quorum, membership, evidence, dissent, and human-final-decision rules. Strategy, Long-Term, and Special Situations now also have governed packet, position, discussion, synthesis, final-decision, and follow-up operations. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] Approval board view. Dedicated approval families and their safe resolvers are exposed in one live terminal; no generic status flip can bypass domain writes.
- [x] Character/personality cards. All active roles have warehouse-backed persona/operating-style data and office character identity; 3D art refinement remains separate. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [~] Agent hover cards.
- [~] Agent handoff threads.
- [~] Live AI Office room foundation.
- [x] Agent reliability foundation. Readiness and recent worker completion/failure evidence are available per employee; calibrated long-run confidence scoring remains open.
- [x] Agent productivity foundation. Open work, queue state, completed runs, schedules, and mailbox load are visible; normalized cross-role productivity scoring remains open.
- [ ] Task arrows between agents.
- [x] Click-through agent profile pages. Agent URLs open addressable profiles with reporting line, persona, role scope, tools/skills, model route, readiness, reliability, work history, mailbox, and cost/quality evidence. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [ ] Agent discussion thread detail pages.
- [x] Per-agent work history timeline. The scoped Agent terminal returns and renders bounded recent worker-history records against addressable employee profiles; the final live audit returned 59 rows.
- [x] Per-agent cost and quality report. All 95 employees expose governed cost caps, model-route policy, readiness, and observed quality/reliability evidence; calibrated long-run scoring remains separate.
- [x] Department manager dashboards. Fifteen source-backed department desks are live inside the 19-workspace Command Center, with filters, scoped operational tables, owner views, and persistent widget layout.
- [ ] Agent hiring/onboarding workflow.
- [x] Recurring agent schedules. Thirteen database-backed schedules materialize idempotent work and retain schedule-run evidence.
- [x] Agent model cost controls. All 95 active agents have hard caps; autonomous cloud use and cloud escalation without approval are both zero.

## 14. Committees

- [x] Committee constitution registry. Eleven committees have durable chairs, quorum, member rosters, required evidence, dissent rules, and human-final-decision boundaries. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].

- [x] Strategy Committee workflow. Independent sealed positions, quorum, discussion, chair synthesis, human final decision, minutes, dissent, conditions, and follow-ups are live.
- [x] Long-Term Investment Committee workflow. The governed packet contract maps Long-Term evidence to its registered constitution and the same independent-position and human-final-decision controls.
- [x] Special Situations Committee workflow. Production acceptance used the real Rolex Rings buyback matter through five independent positions, quorum, challenge discussion, chair synthesis, human `more_research` decision, and follow-up task.
- [x] Committee room view. The live room exposes constitutions, packets, quorum, independent positions, discussion, chair synthesis, minutes, dissent, human decisions, and follow-up work without seed fallback. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [ ] Executive Committee workflow.
- [ ] Tactical Committee workflow.
- [ ] Risk Committee workflow.
- [ ] Capital Allocation Committee workflow.
- [ ] Data and Tool Committee workflow.
- [ ] Client Review Committee workflow.
- [ ] Model Review Committee workflow.
- [ ] Execution Approval Committee workflow.
- [x] Committee minutes generator for the three implemented investment committee families.
- [x] Evidence packet generator for the three implemented investment committee families.
- [x] Dissent capture with independent pre-quorum positions and post-quorum challenge messages.
- [x] Decision audit trail separating chair recommendation from the named human final decision.
- [x] Follow-up task automation with durable task, inbox, message, and committee linkage.

## 15. MCP And External Adapters

- [x] MCP server foundation. The importable 172-tool server now includes strategy, integration Gateway, provider, source, evidence, task, approval, browser, schedule, portfolio, research, workspace, and eight governed committee contracts; live protocol verification passed. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [~] Obsidian/vault read-write path.
- [~] Postgres API tool path.
- [~] Browser profile registry.
- [~] Fincept local component installed.
- [~] Fincept skill registry added.
- [~] Vibe skill registry added.
- [x] TradingView CDP/chart-action executor foundation. The local Desktop CDP controller now uses real keyboard events, virtualized indicator result discovery, deterministic study insertion, legend/undo verification, screenshot capture, artifact registration, and needs-review fallback. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] TradingView screenshot artifact API. Approved chart tasks persist browser runs, image artifacts, checksums, and study-level verification state.
- [x] TradingView action template registry/API/MCP. Six advanced chart contracts and approval-gated request flow are live. Formula charts, technical indicator stacks, and fundamental-ratio stacks have production acceptance evidence; synchronized multi-pane options layouts remain partial. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] Research paper ingestion/hypothesis MCP tools. Both source ingestion and source-linked hypothesis creation remain registered in the permanent 172-tool MCP protocol gate. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]], [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
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
- [x] TradingView fundamental ratio chart workflow. Approval `#45`, task `#21`, browser run `#16`, and artifact `#37357` verified Revenue, Net Income, Operating Margin, ROIC, Total Debt, P/E, and P/B on the live chart. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [ ] Provider policy editor UI.
- [ ] Provider policy simulator.

## 16. Dashboards And Live Office

- [x] Canonical frontend delivery plan linked to blueprint and checklist. Evidence: [[AI OS Command Center and 3D Office Frontend Plan]]; the live 95-agent registry overrides historical proposal counts.
- [x] Command Center foundation with durable delegation. Verified 2026-07-11 through the deployed UI: Charlie message `#94` routed to Research Analyst, created task `#327`, task inbox `#412`, and provider-policy inbox `#413`; no investment or trading action was requested or executed.
- [x] Portfolio widget foundation. Verified 2026-07-13 in the scoped Portfolio Office with production holdings, market value, gross/net exposure, investment books, position objects, conflicts, and readiness gaps. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [x] Book exposure widget. Verified 2026-07-13 for symbol-level multi-book and client-book exposure with client filtering. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- [~] Strategy Committee Gate panel.
- [x] Data-source freshness panels. Mission Control and Live Office expose bounded live freshness rows; Live Office shows only stale/error/missing-check alerts. Evidence: [[2026-07-13-live-office-operations-v3]].
- [x] Agent task/inbox panels. Mission Control and Live Office expose durable priority tasks, current work, inbox, unread-message, blocked-work, and risk counts. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Long-Term Office dashboard foundation.
- [x] Quant Lab dashboard foundation. Scoped validation, promotion, committee, retirement/drift, and safe analytics controls are deployed against live strategy rows. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [x] Strategy Arsenal terminal v1. Operator intake, ten templates, source-backed discovery triage, validation sweep, origin/stage filters, eight promotion gates, next-required actions, and strategy evidence chains are deployed through a scoped endpoint. Broker orders remain zero and globally locked. Evidence: [[2026-07-15-strategy-arsenal-v1]].
- [x] AI Office live activity foundation. The office maps the 95-agent organization, live activity, rooms, mailbox handoffs, committee matters, priority work, risk events, freshness alerts, and execution control from the warehouse with no seed fallback. Evidence: [[2026-07-13-live-office-operations-v3]], [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
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
- [~] Portfolio Office v2: scoped production workspace now provides client filtering, books, positions, multi-book exposure, portfolio intelligence, cross-book conflicts, readiness remediation, NAV, cash evidence, Modified Dietz performance, benchmark comparison, FIFO tax lots, and realized attribution. Dedicated thesis packets, richer factor attribution, and decision drill-downs remain open. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]], [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Risk Center v2: live limits, breach/warning summary, execution lock, institutional VaR/ES, 20,000-path bootstrap risk, stress scenarios, concentration, liquidity, benchmark-factor attribution, limited-live requests, order intents, drift, refresh, and guarded global kill switch are deployed. Options tail risk, richer multi-factor/correlation models, conflict drill-downs, risk committee decisions, and order-risk evidence remain. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [~] Research Hub v2: scoped live long-term theses, committee review, filings/news, special situations, output artifacts, valuation models, checklists, and Long-Term Monte Carlo evidence/action are deployed. Long-term committee and output-artifact evidence drawers are live; filing/source-document actions, broader feeds, complete detectors, and remaining valuation calculators remain open. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]], [[2026-07-13-deep-evidence-and-approval-actions-v2]], [[2026-07-13-long-term-decision-lab-v1]].
- [x] System Health v2: scoped live MCP, source, worker, provider, model, cost, storage, pipeline, blueprint, execution-safety, and recovery state. Evidence: [[2026-07-13-system-health-v2-and-docker-runtime-recovery]].
- [~] Portfolio Intelligence dashboard v3. Portfolio overview, concentration, gross/net exposure, critical/risk-limit breach counts, books, conflicts, readiness, institutional VaR/ES, stress, liquidity, and benchmark-factor attribution are live; full sector/style/factor attribution and capital-allocation actions remain open. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]], [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [~] Client Folio dashboard. Live client registry, onboarding, suitability state, accounts, holdings, books, reconciliation, cash/NAV evidence, FIFO tax lots, performance/benchmark views, attribution, governed cash staging, and report-delivery approvals are deployed. Imported-client mandate completion, complete source history, richer report presentation, and real delivery adapters remain open. Evidence: [[2026-07-15-client-office-control-plane-v1]], [[2026-07-15-client-accounting-performance-reporting-v1]].
- [x] Symbol Intelligence dashboard v2. Evidence: [[2026-07-07-symbol-intelligence-v2]].
- [~] Long-Term Office dashboard v2. Evidence: [[2026-07-08-long-term-coverage-board-v1]]; coverage board is now live inside Long-Term Thesis Control, but full client suitability and decision UI remain open.
- [ ] Tactical Office dashboard.
- [~] Trading Desk dashboard. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [~] Risk Center dashboard. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- [x] Capital Allocation dashboard. Scoped live client/book policy control, editable budgets/ranges, drift and risk analysis, committee queue, legacy-default warning, freshness/customization, and execution lock are deployed. Real policy entry and downstream cash/tax/suitability workflows remain tracked separately. Evidence: [[2026-07-15-capital-allocation-control-plane-v1]].
- [~] Research Factory dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] News and Filings dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] Special Situations dashboard. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- [~] Treasury/Hedges/Crypto dashboard. Treasury and Macro terminal is live over source-backed macro/news/market records; dedicated hedge construction, collateral, cash ladder, and crypto execution connectors remain. Evidence: [[2026-07-15-terminal-agent-research-foundation-v1]].
- [x] Data & Model Gateway terminal v1. The scoped terminal registers sources and model endpoints, exposes plug-in readiness, validates warehouse mappings, configures allowlisted executor families, shows governed route states, privacy/cache policies, all 95 agent assignments, model-call decisions, and escalation queue state, and includes strategy-data coverage/import/quality ledgers. Raw prompts, raw secrets, arbitrary commands, seed fallback, autonomous cloud use, and broker authority are rejected. Evidence: [[2026-07-15-model-runtime-control-plane-v1]], [[2026-07-15-data-model-integration-gateway-v1]], [[2026-07-15-legacy-market-data-spine-v1]], [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
- [x] Provider Readiness dashboard v2. Model assignment readiness and source health/freshness are unified in the Gateway with filters, per-row checks, full sweeps, missing-credential/model actions, and evidence. Provider policy simulation and final department overrides remain separate open controls. Evidence: [[2026-07-15-data-model-integration-gateway-v1]].
- [x] Committee Room dashboard v3. Scoped live packet opening, independent positions, quorum, discussion, chair synthesis, minutes/dissent, named human final decisions, follow-up actions, constitution state, customization, and execution lock are deployed for Strategy, Long-Term, and Special Situations. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] 3D office scene with procedural rooms, stable camera controls, live room placement, room-floor selection, and animated department focus. Directory selection moves the camera without leaving the office; an explicit secondary action opens the mapped Command Center workspace. Evidence: [[2026-07-13-live-office-operations-v3]].
- [~] Data-backed agent avatars: live status, current task, activity pulse, live character name/color/visual traits, employee profile inspector, keyboard employee selector, and durable mailbox handoff. Verified 2026-07-10: Live Office message #61 created task #294 and inbox #379 for Risk Agent; profile pages and direct canvas hit testing remain outstanding.
- [x] Data-backed committee room: live agenda, packet, independent positions, quorum, challenge discussion, chair recommendation, minutes, dissent, human final decision, follow-up work, approval state, memo reference, and evidence drill-down are deployed. Production acceptance used `special:1` without seed data. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
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
- [x] Monthly client report artifact generation. Canonical period `2026-07` completed as source-backed draft run `#26`; client delivery queues `#4` through `#6` remain blocked behind independent approvals `#35` through `#37`, and no external send occurred. Product presentation and delivery remain partial under Client Office. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
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
- [x] Per-agent model route table. All 95 active agents have explicit primary, fallback, escalation, context, and cost-policy assignments; validation fails on incomplete coverage. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].
- [x] Cost ledger and per-agent hard caps. All 95 active agents have cost-cap rows; autonomous cloud agents and unapproved cloud events are both zero. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]], [[2026-07-06-model-cost-ledger-v1]].
- [x] Embedding model path. `mxbai-embed-large` is installed on the SSD and six Qdrant collections are registered against the embedding path.
- [x] Live model availability gate. API and readiness sweeps query Ollama `/api/tags`; installed `llama3.2:3b` is `configured`, while absent `qwen3:8b`/`qwen3:14b` routes are `model_unavailable` and non-assignable. Evidence: health checks `#773` and `#774`.
- [~] Daily driver model selected and smoke-benchmarked. `llama3.2:3b` direct cold-load verification completed in 9.73 seconds and Charlie chat turn `#44` used the model successfully; formal task-quality and sustained-throughput benchmarks remain open.
- [x] Model call cache. Only public/internal non-client prompts are eligible; cache identity uses route, model, and prompt hash. Client-private/restricted cache is disabled by policy and database constraint. The verified warm hit returned in 195 ms; validation cache rows were removed afterward. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].
- [x] Escalation policy. Higher-capability requests retain decision ID, prompt hash, privacy/cost reviews, approval, and explicit false capital/execution authority without storing raw prompts. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].
- [x] Cloud model approval flow. Public/internal requests create a human approval; private/restricted requests are privacy-blocked before approval. Approval resolution never invokes a provider automatically. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].
- [ ] Model quality eval set.
- [x] Local-vs-cloud routing tests. Missing Charlie/Qwen primary route fell back to installed `llama3.2:3b`; unknown routes were controlled rather than foreign-key failures; public cache miss/hit and both escalation privacy branches passed. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].
- [~] Context/RAG compression policy. Client-context inclusion is now authoritative, public/internal cacheable calls omit client/book/position context and disable unscoped vault retrieval, and private calls use bounded local retrieval. Remaining gate: collection-level sensitivity ACLs and retrieval-quality evaluation.
- [x] Privacy restrictions per model route. Four database policies enforce local/cloud/cache/context/retention rules; private and restricted classes cannot use cloud or cache. Raw prompt columns do not exist in the decision ledger. Evidence: [[2026-07-15-model-runtime-control-plane-v1]].
- [x] Per-department model policies. The 95-agent assignment and cost matrix is visible in the production Gateway and exposed through MCP. Evidence: [[2026-07-15-agent-operating-system-and-strategy-chart-v2]].

## 19. Production Safety

- [x] Read-only broker connector policy enforced. Global execution policy is `read_only_blocked`; no current connector may write broker orders. A future broker adapter must pass the separate limited-live constitution. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Broker order execution disabled by default. Live warehouse verification: `global_execution_locked=true`, `limited_live_allowed=false`, and `live_broker_writes_allowed=false`. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Order preview schema. `trading.order_intents` and `trading.order_risk_checks` retain the proposed order, notional, risk result, approval, gate state, and explicit false-by-default broker authority. Evidence: [[2026-07-15-governance-and-production-safety-v1]], [[2026-07-13-trading-quant-risk-v2]].
- [x] Human approval before any live order. `broker_order_intent` approval is independent from strategy, memo, or committee approval and remains required per order. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Kill switch UI. The Risk Center exposes the guarded global kill-switch action while every terminal displays current execution lock state. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-governance-and-production-safety-v1]].
- [x] Kill switch backend enforcement. `trading.engage_global_kill_switch` locks global execution, disables live writes, stops live instances, opens a critical risk event, and creates review work. Evidence: [[2026-07-15-governance-and-production-safety-v1]].
- [x] Strategy live-enable approval policy. Strategy committee approval cannot enable execution; limited-live request, risk limits, expiry, global policy, per-order approval, and execution/risk checks remain separate gates. Evidence: [[2026-07-13-trading-quant-risk-v2]], [[2026-07-15-governance-and-production-safety-v1]].
- [x] Client-report send approval policy. Scheduled client output is draft-only; the verified July run created three client-specific pending delivery approvals. Generic resolution is blocked, dedicated resolution is atomic, and approval still records `external_send_executed=false` because no delivery adapter or broker authority is granted. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
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
- [~] Harden TradingView controller and straddle workflow. Desktop CDP is healthy; six advanced chart-template contracts, compiled actions, atomic approval resolution, screenshot quality validation, formula charts, technical indicator stacks, and fundamental-ratio stacks are verified in production. Four-pane synchronized options layouts and options-symbol assembly remain partial. Evidence: [[2026-07-15-department-terminals-tradingview-and-committee-operations-v1]].
- [x] Build Client Folio dashboard. Governed onboarding, account lifecycle, holdings approval, suitability gaps, client-book attribution, P2Cursor, and generic multi-source reconciliation are live and verified across desktop/mobile. Evidence: [[2026-07-15-client-office-control-plane-v1]].
- [x] Build client accounting and reporting control plane. Deterministic FIFO, cash/fee ledgers, NAV, Modified Dietz benchmark performance, realized attribution, approval-gated monthly drafts, API/MCP controls, and Client Folio terminal panels are live over real imported data with missing evidence explicitly incomplete. Evidence: [[2026-07-15-client-accounting-performance-reporting-v1]].
- [~] Build Risk Office v2 with stress tests and portfolio Monte Carlo. The institutional calculation, API, MCP, audited action, responsive terminal, validation, and SSD-artifact foundation are live; options tail risk, richer factor/correlation models, Risk Committee/override workflows, and automated specialist cadence remain. Evidence: [[2026-07-15-institutional-portfolio-risk-engine-v1]].
- [x] Build Animated AI Office v1 foundation. The procedural WebGL office, static fallback, live rooms, 95-agent directory, status/activity, handoff lines, committee state, employee inspection, room focus, and workspace routing are data-backed. Final art direction, direct avatar hit testing, and chronological playback remain the later refinement pass.
