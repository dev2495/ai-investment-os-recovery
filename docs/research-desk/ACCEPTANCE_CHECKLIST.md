# Research Desk v1 Acceptance Checklist

This checklist is the release gate for the Research Desk vertical slice. It maps the stored [Institutional Master Blueprint v11](../AI_Investment_OS_Institutional_Master_Blueprint_v11.md) and [Master Build Prompt](./MASTER_BUILD_PROMPT.md) to milestones M0-M10.

## How to use this checklist

- `[x]` means the item has direct evidence from this checkout or an isolated test run listed below.
- `[ ]` means acceptance is not yet proven. Replace its `Evidence: pending` marker with a dated command, durable receipt, API payload, database query, artifact hash, or screenshot before checking it.
- Code presence, HTTP 200, a generated draft, or mocked-browser success does not prove live acceptance.
- Do not mark a milestone complete while any required item in that milestone remains unchecked.

## Evidence currently available

| ID | Verified evidence | Scope and limitation |
|---|---|---|
| E1 | The stored blueprint SHA-256 is `7642b19f...391c10`, exactly matching the supplied Downloads file. The stored master prompt SHA-256 is `b7dbc7af...409fb`, exactly matching the supplied attachment. | Exact checkout copies; external Obsidian managed-block writeback still needs live-host verification. |
| E2 | Branch `codex/research-desk-knowledge-scanners-v1`, starting from tested upstream HEAD `d764db2`. | Checkout identity only; it does not prove the live iMac release commit. |
| E3 | `npm run build` passed on 2026-09-01 after a clean `npm ci`; Vite produced the production bundle. | Local release checkout; deployed asset equality remains unproven while the iMac is unreachable. |
| E4 | `research-desk-v1.spec.ts` passed 7/7 in installed Google Chrome against isolated Vite, including 390 px layout, actionable/redacted failures, HTML-ready/PDF-pending delivery and four-gate GLM promotion. | The browser was real; API responses were deterministic fixtures, not the authenticated production database. |
| E5 | `git diff --check` passed; changed-line credential-pattern scan found no private keys or common API-token formats. | Focused delta scan, not a historical repository secret audit. |
| E6 | Full backend suite: `645 passed, 1 skipped, 178 subtests passed` on 2026-09-01. | Isolated checkout tests; the single existing skip was not converted into evidence. |
| E7 | Migrations 250, 251 and 252 parsed through `pglast`; the full Python suite also passed migration/contract assertions. | Syntax and contract proof; disposable production-schema replay remains a live release gate. |
| E8 | All seven protected Zerodha scripts/services have the recorded baseline SHA-256 values and no diff. | Proves this delta preserves those files; authenticated stream health still requires the iMac. |
| E9 | `npm audit` and `npm audit --omit=dev` both report `0 vulnerabilities`. | The build still emits a non-security chunk-size advisory. |
| E10 | Focused unit/contract tests cover stale-stream valuation blocking, exact-symbol dashboard selection, report-only repair, natural-language URL rejection, scanner clone/approval/run gates and named GLM human promotion. | Deterministic code-contract evidence; production rows and artifacts remain to be exercised. |

## 2026-09-01 implementation delta

- [x] Preserve the existing Zerodha acquisition/authentication/stream scripts without modification. Evidence: E8.
- [x] Fail closed on a stale/missing Zerodha heartbeat during the live session and expose provider, exchange, symbol mapping, quote age, stream age, freshness, delay and fallback state. Evidence: E6, E10.
- [x] Keep `broker_write_allowed=false` and add no Research Desk order-placement path. Evidence: E6, E8, E10.
- [x] Repair a PDF-only/report-delivery failure without rerunning sources, analysis or paid models. Evidence: E4, E6, E10.
- [x] Return an actionable missing-artifact response instead of a broken file link. Evidence: E4, E6, E10.
- [x] Make exact exchange/symbol navigation prefer the requested company and expose completed Research Case output in the Company Thesis Dashboard. Evidence: E6, E10.
- [x] Register GLM 5.3 Flash as a disabled public-only canary with conservative non-promotional cost ceilings. Evidence: E6, E7, E10.
- [x] Require cost preflight, explicit spend approval, a fixed public packet, a completed structured-output canary, exact response-hash review, named reviewer, citation score >=90, numeric score >=95 and zero unsupported claims before daily-driver promotion. Evidence: E4, E6, E10.
- [x] Keep DeepSeek V4 Pro as lead/review escalation and retain per-run approval after promotion. Evidence: E6, E10.
- [x] Make executable scanner templates copy-only and idempotent; require deterministic validation, persistent publication approval and explicit run confirmation. Evidence: E6, E7, E10.
- [x] Prevent URL-led article commands from being misclassified as company names. Evidence: E6, E10.
- [x] Compile the production UI, pass the complete backend suite, pass real-Chrome interaction tests and clear the dependency audit. Evidence: E3, E4, E6, E9.
- [ ] Apply migrations 250-252 to the canonical iMac release and prove live API/database compatibility. Blocked: Tailscale reported the iMac peer offline and SSH timed out on 2026-09-01.
- [ ] Install/verify the governed external-SSD PDF runtime on the iMac and replay the Shivalik source-extraction repair. Blocked: live host unavailable.
- [ ] Run an approved GLM 5.3 Flash canary on a fixed public packet and record the required human review. This intentionally cannot be auto-approved by code.
- [ ] Prove an authenticated Wipro and Shivalik golden path in production Chrome/Safari with live Postgres, SSD artifacts and Zerodha freshness.
- [ ] Promote/deploy the tested commit to `a02ee0f-live` and verify asset hashes, worker health and zero unexpected browser/API failures. Blocked: live host unavailable.

## M0 - Safe baseline and refactor boundary

- [x] Canonical blueprint and Research Desk master prompt are stored in the checkout. Evidence: E1.
- [x] Focused feature branch and starting HEAD are identified. Evidence: E2.
- [x] Repository baseline audit, implementation ledger and operator runbook exist. Evidence: E1.
- [ ] Prove the exact live iMac release commit and asset mapping. Evidence: pending live process/release/asset receipt.
- [ ] Prove the current application starts with existing services and smoke tests passing. Evidence: pending dated runtime health and smoke-test output.
- [ ] Prove Postgres, Qdrant, Obsidian vault, runtime configuration and Git backup integrity. Evidence: pending SHA manifest and backup receipt.
- [ ] Complete a disposable restore drill for Postgres, Qdrant, vault and Git before any production migration. Evidence: pending restore receipt and count/hash comparison.
- [ ] Prove baseline documentation also exists in the external-SSD Obsidian vault without overwriting human content. Evidence: pending note path and hash.
- [ ] Prove no private/client/licensed data, credentials or runtime databases were newly committed. Evidence: pending secret scan and repository audit.
- [ ] Prove migration replay, unit/contract/golden tests, dependency scan and secret scan pass in isolated CI. Evidence: pending CI run.
- [ ] Prove no user data was lost, moved, or silently redirected to internal disk. Evidence: pending before/after storage inventory.

## M1 - Generic company and durable Research Case

- [ ] Resolve by company name, ticker, exchange and ISIN; return candidates for ambiguity instead of guessing. Evidence: pending Wipro, non-held-company and ambiguous-name API/browser receipts.
- [ ] Create Wipro and a non-held company through the same durable intake contract. Evidence: pending case IDs and Postgres/API/MCP/UI comparison.
- [ ] Persist immutable case key, entity, mandate, as-of/source cutoff, plan version, state, readiness, assignments, blockers, artifacts and audit history. Evidence: pending schema/query receipt.
- [ ] Make create/start/refresh/cancel/timeline/readiness/artifacts operations idempotent and bounded. Evidence: pending contract tests with repeated request keys.
- [ ] Show each case consistently in Postgres, API, MCP, Research Desk, agent task list, Today and Company Dashboard. Evidence: pending cross-surface ID reconciliation.
- [ ] Keep blocked older cases from preventing a distinct new mandate; expose View, Repair and New mandate. Evidence: pending live browser flow.
- [ ] Prevent a research conclusion until evidence and calculation gates are met. Evidence: pending negative/gating test.

## M2 - Evidence planner and acquisition loop

- [ ] Generate a versioned, company/market/purpose-specific evidence plan with explicit critical and non-critical requirements. Evidence: pending plan artifact and version.
- [ ] Reuse immutable artifacts, parsed text, Obsidian knowledge, filings and imported reports before reacquisition. Evidence: pending reuse/dedup trace.
- [ ] Enforce source authority from primary official through untrusted commentary. Evidence: pending source-ranking tests.
- [ ] Store authorized acquisitions immutably on the external SSD with URLs, dates, MIME, SHA, size, authority, licensing and parser state. Evidence: pending artifact manifest.
- [ ] Preserve page/section/table/row/column or excerpt-hash locators for every accepted fact and claim. Evidence: pending drill-through sample.
- [ ] Re-evaluate requirements after extraction and create durable tasks for partial, missing, contradictory or unobtainable evidence. Evidence: pending gap-loop task records.
- [ ] Distinguish captured, parsed, machine-extracted, validated, human-reviewed, stale and missing from investment readiness. Evidence: pending API/UI semantics test.
- [ ] Produce Wipro's complete evidence inventory and real acquisition tasks for missing price, shares, cash flow, capex, guidance, peers and other critical inputs. Evidence: pending Wipro inventory.

## M3 - Point-in-time facts and deterministic calculations

- [ ] Store canonical facts with period, scope, currency, unit/scale, reported/known/available timestamps, source anchor, normalizer version, restatement and verification state. Evidence: pending schema and sampled rows.
- [ ] Build the fullest source-supported Wipro annual history, targeting ten years, and expose missing periods rather than omitting them. Evidence: pending year-range/coverage query.
- [ ] Reconcile P&L, balance sheet, cash flow, segment and share-count data with explicit exceptions. Evidence: pending tie-out report.
- [ ] Reproduce CAGR, margins, CFO/FCF conversion, working capital, leverage, liquidity, ROE, ROCE, ROIC and capital-efficiency bridges from cited fact IDs. Evidence: pending formula-version replay.
- [ ] Obtain current quote and share count from the canonical Zerodha path, with exchange and timezone-aware freshness. Evidence: pending quote/instrument IDs and timestamps.
- [ ] Block price-dependent valuation when quote or share count is stale, absent or unreconciled. Evidence: pending stale-price failure test.
- [ ] Separate historical facts, management guidance, external estimates and model scenarios. Evidence: pending API/report sample.
- [ ] Expose completeness scores and exact critical gaps. Evidence: pending Wipro dashboard/API receipt.
- [ ] Let scanners query deterministic point-in-time metric views without using LLM output as numeric truth. Evidence: pending SQL lineage and replay test.

## M4 - Full specialist workflow and company pack

- [ ] Dispatch durable role-scoped specialists for company/business, filings, financials, management/governance, industry/moat, valuation and bear/risk work. Evidence: pending task/run IDs.
- [ ] Preserve typed outputs, citations, calculations, contradictions, confidence, missing data, costs, retries and tool audit. Evidence: pending completed-run packet.
- [ ] Produce the complete company pack: conclusion/evolution; business/segments; industry/TAM/value chain; moat; management/governance; financial story/ratios; forecasts/valuation; catalysts/risks; decision; source appendix. Evidence: pending reviewed HTML/PDF artifacts.
- [ ] Keep all arithmetic and valuation deterministic and reproducible; use agents for planning, extraction review, synthesis and challenge. Evidence: pending formula/source manifest.
- [ ] Run independent red team and committee review with generation and approval separation. Evidence: pending reviewer/committee records.
- [ ] Mark Wipro `ready_for_review` or `decision_ready` only after critical evidence and calculation gates pass. Evidence: pending readiness receipt.
- [ ] Run the same state machine for a non-held company without a pre-existing thesis. Evidence: pending golden-case receipt.
- [ ] Reproduce versioned HTML/PDF from the stored source manifest and render without timeout. Evidence: pending artifact hashes and visual QA.

## M5 - Obsidian knowledge graph and memory

- [ ] Preserve the existing vault and update generated content only inside versioned managed blocks. Evidence: pending before/after human-edit survival test.
- [ ] Back up a note before layout migration and keep user-authored text unchanged. Evidence: pending backup/hash receipt.
- [ ] Maintain scoped graph nodes/edges for companies, cases, sources, evidence, claims, facts, valuation, thesis, people, themes, portfolios/watchlists and reports. Evidence: pending schema/API sample.
- [ ] Enforce cross-scope isolation, idempotent upsert and point-in-time availability. Evidence: pending RLS/invariant tests.
- [ ] Incrementally index changed notes/artifacts into Postgres and local Qdrant without rebuilding unrelated content. Evidence: pending incremental index receipt and point counts.
- [ ] Provide bounded hybrid retrieval and graph-neighborhood APIs/MCP/UI. Evidence: pending query/cursor/scope tests.
- [ ] Trace source document -> evidence anchor -> fact/claim -> case -> valuation/thesis -> Obsidian note -> portfolio/watchlist. Evidence: pending Wipro lineage walk.
- [ ] Keep Obsidian as human-readable memory, Postgres as fact/state truth and Qdrant as retrieval only. Evidence: pending architecture invariant tests.

## M6 - Investor, publication and idea following

- [ ] Register followed people/publications/ValuePickr/Substack/blog/RSS/podcast/video/social sources with authority, licensing, cadence and retention policy. Evidence: pending source records.
- [ ] Follow at least one public source and one authenticated/local source in read-only mode. Evidence: pending refresh receipts.
- [ ] Deduplicate by canonical URL/content hash and quarantine prompt injection or unsafe content. Evidence: pending failure-injection tests.
- [ ] Store only permitted excerpts and link to originals; do not republish paid or gated content. Evidence: pending retention/copyright audit.
- [ ] Keep commentary untrusted until primary-source corroboration; never promote it directly to accepted fact. Evidence: pending claim-state test.
- [ ] Map items to companies/themes/holdings/watchlists and create auditable idea cards and primary-evidence follow-ups. Evidence: pending item-to-idea lineage.
- [ ] Maintain source/author scorecards, pause controls, cooldowns, provider health and retry history. Evidence: pending API/UI receipts.
- [ ] Write bounded summaries to Obsidian and expose them in Following/Idea Inbox/Today without generic noise. Evidence: pending UI/note evidence.

## M7 - Fundamental scanner factory

- [ ] Use a safe allowlisted DSL; never execute arbitrary user Python, SQL or shell. Evidence: pending parser security tests.
- [ ] Make definitions versioned, immutable after publication, point-in-time, deterministic and replayable. Evidence: pending database invariant/replay tests.
- [ ] Run at least five built-in scanners on the real eligible NSE/BSE universe. Evidence: pending run IDs and universe versions.
- [ ] Show total/eligible universe, coverage, exclusions, stale data and provider failures honestly. Evidence: pending results API/UI.
- [ ] Trace every result to scanner/version, as-of, universe, metric version, fact/quote IDs and code revision. Evidence: pending result lineage.
- [ ] Convert natural language to a draft, resolve only allowlisted metrics, validate, dry-run and historically review it. Evidence: pending Charlie/scanner artifact.
- [ ] Require explicit approval before publication or scheduling. Evidence: pending approval audit.
- [ ] Start watchlist/research actions from a selected result with durable IDs and no broker action. Evidence: pending golden flow.
- [ ] Support schedule, pause, replay, alerts and run-history comparison. Evidence: pending scheduler/UI receipts.

## M8 - Charlie and MCP integration

- [ ] Accept natural-language research, knowledge, following and scanner commands while preserving company/book/client context. Evidence: pending conversation tests.
- [ ] Return understood objective, entities, plan, assigned agents, sources/freshness, calculations, conclusion, uncertainty, contradictions, missing data, approvals, artifacts, dashboards, memory and next action. Evidence: pending response-contract test.
- [ ] One Charlie command must create a durable plan, case ID/link, tasks, source requests, agent activity, calculations, writebacks and result packet. Evidence: pending live Wipro and non-held flows.
- [ ] Report queued, running, blocked, validated, ready and finished states truthfully; never silently no-op. Evidence: pending state-transition tests.
- [ ] Register typed, risk-classed, timed, idempotent and audited MCP tools through the compatibility layer. Evidence: pending `tools/list`, schemas and audit rows.
- [ ] Keep research reads/calculations automatic, internal writes audited, scanner publish/schedule approval-gated and all external/financial actions disabled. Evidence: pending permission tests.
- [ ] Make fast chat retrieve current stack context rather than hallucinating or claiming unavailable state. Evidence: pending Charlie fast-chat retrieval test.

## M9 - Research Desk UI and truthful office

- [x] Production UI bundle compiles. Evidence: E3.
- [x] Isolated mocked-browser checks cover bounded Research Desk loading, independent Following/Scanner/Knowledge states, 390 px layout, actionable repair copy and redacted technical details. Evidence: E4.
- [ ] Operate new research intake, case detail, company dashboard, evidence, following, ideas, scanners and knowledge graph without shell commands. Evidence: pending authenticated live route matrix.
- [ ] Show company-specific investor output first and keep extraction/audit/agent machinery behind Evidence, Method and Operations drawers. Evidence: pending desktop/mobile screenshots.
- [ ] Show source cutoff, price timestamp, freshness, completeness, fact/guidance/estimate/scenario status, blockers and citations accurately. Evidence: pending API-to-DOM comparison.
- [ ] Prove Wipro and a non-held company can be started, tracked, repaired and opened in the Company Dashboard. Evidence: pending live Chrome/Safari flows.
- [ ] Prove scanner result -> research case and followed item -> idea card flows. Evidence: pending live browser receipts.
- [ ] Map 2D/3D agent status, tool, task, progress, blocker and cost only from durable rows; provide interaction and accessibility parity. Evidence: pending event-to-office and 2D parity tests.
- [ ] Verify authenticated Chrome desktop, Safari desktop and 390 px mobile after hard refresh with zero unexpected console/request failures. Evidence: pending screenshots, HAR/request log and console log.
- [ ] Verify live deployed assets match the tested commit. Evidence: pending asset hash and release mapping.

## M10 - Monitoring, schedules and thesis drift

- [ ] Map new filings, results, presentations, transcripts, guidance, ownership, management, corporate actions, ratings, material news and price changes to the correct company/case/portfolio/watchlist. Evidence: pending monitor event matrix.
- [ ] Compare updates with prior facts/assumptions, calculate materiality and rerun only relevant specialists. Evidence: pending thesis-drift run.
- [ ] Reopen review only when a defined thesis-break condition triggers. Evidence: pending positive/negative tests.
- [ ] Refresh followed sources with bounded concurrency, dedupe, backoff, provider health, injection quarantine and copyright-safe retention. Evidence: pending scheduler receipts.
- [ ] Run scanners after completed point-in-time refresh; alert on entries, exits, rank and material metric changes without duplicates. Evidence: pending scheduled run history.
- [ ] Publish a concise cited daily brief to Today and Obsidian with filings, gaps, blockers, thesis drift, followed-source relevance, scanner entrants and data degradation. Evidence: pending dated brief/API/note.
- [ ] Prove replay and idempotency: the same source/filing/scanner event creates no duplicate task, alert or note block. Evidence: pending duplicate-event test.

## Zerodha and execution guardrails

- [ ] Zerodha remains the only canonical private live quote, instrument, account/position and supported options-data path; no parallel provider silently replaces it. Evidence: pending connector/config/schema audit.
- [ ] Quote selection is exchange-aware and timezone-aware and exposes provider, instrument, captured time, market time and freshness. Evidence: pending live quote receipt.
- [ ] Stale/unavailable price or unreconciled shares visibly blocks price-dependent DCF, reverse DCF, multiples and expected-return output. Evidence: pending valuation gate tests.
- [ ] `broker_write_allowed=false`, `client_write_allowed=false` and `external_write_allowed=false` are enforced in database policy, API, MCP and UI. Evidence: pending cross-layer permission tests.
- [ ] No order, alert, login, account mutation or broker-side change is enabled by Research Desk, Charlie, scanners, monitoring or agents. Evidence: pending capability registry and negative tests.
- [ ] No credential, Keychain secret, private portfolio/client data or non-public note enters prompts, logs, diagnostics, Git or external models. Evidence: pending redaction/egress/secret-scan receipts.
- [ ] Zerodha reconnect uses the existing user-managed login flow and does not expose credentials. Evidence: pending authenticated reconnect observation.
- [ ] Trading remains read-only -> research/draft -> paper -> staged -> explicit human confirmation, with generation separate from approval. Evidence: pending state-machine/policy tests.
- [ ] Any future capital action remains outside this milestone and requires existing deterministic policy, risk, approval, broker acknowledgement and reconciliation gates. Evidence: pending policy audit.

## Cross-cutting release gates

- [ ] External SSD is mounted, writable and used for private artifacts, reports, logs/caches, model/runtime paths, backups, Qdrant and database persistence; the stack fails closed if it is absent. Evidence: pending mount/path/restart audit.
- [ ] Scoped roles/RLS prevent cross-client, cross-book and cross-workspace leakage. Evidence: pending role-policy tests.
- [ ] Model routing enforces public-only external calls, local-only private work, per-task model/cost trace, hard ceilings, retries and cooldowns. Evidence: pending router/canary receipts.
- [ ] API pagination, query counts and latency stay bounded for dashboard, operations, graph, feeds, scanners and Today. Evidence: pending profile/query/latency report.
- [ ] Source, parser, model and renderer failures are actionable in the UI while full redacted diagnostics remain optional. Evidence: pending live failure-injection browser matrix.
- [ ] Report HTML/PDF, source manifest, workbook/data export and version history are stored locally and reproducible. Evidence: pending artifact hashes and render comparison.
- [ ] Full Python/API/MCP/UI test suites pass from a clean checkout and isolated database. Evidence: pending command log.
- [ ] Disposable migration replay and rollback-safe verification pass without altering legacy or Zerodha tables. Evidence: pending migration test receipt.
- [ ] Postgres, Qdrant, Obsidian and Git restore drill passes from the current SSD backup. Evidence: pending restore receipt.
- [ ] Authenticated live browser acceptance passes on the user-relevant role after hard refresh. Evidence: pending Chrome/Safari screenshots and logs.
- [ ] Live release health, asset hashes and background-worker state match the accepted commit. Evidence: pending deployment receipt.
- [ ] Final implementation report, this checklist, Obsidian implementation note and Git commit/push are current. Evidence: pending commit SHA and remote comparison.

## Final acceptance

Research Desk v1 is accepted only when:

- [ ] Every M0-M10 required item above is checked with dated evidence.
- [ ] Every Zerodha and cross-cutting guardrail is checked.
- [ ] Wipro and one non-held-company golden path complete end to end.
- [ ] No unresolved P0/P1 defect remains in intake, extraction, calculations, valuation, report rendering, monitoring, repair or visibility.
- [ ] The user accepts the authenticated live desktop/mobile result.
