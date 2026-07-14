# Research Intelligence v1

Date: 2026-07-15
Status: verified implementation checkpoint
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Frontend: [[AI OS Command Center and 3D Office Frontend Plan]]

## Result

The Research Factory now has a real scheduled source-intelligence loop rather than a static list of feeds. News ingestion, NSE/BSE announcements, material-first filing PDF extraction, strategy discovery, and one role-scoped agent route run through one auditable scheduler. Holdings Research exposes source health and collector history beside filings, curated news, special situations, generated ideas, and output artifacts. No source action can allocate capital, enable a strategy, or place a broker order.

## Live Source Contract

- 15 registered source rows, including exchange adapters and planned or credential-blocked sources.
- 10 current healthy RSS checks.
- Official macro sources include RBI, the Federal Reserve Board, and the European Central Bank.
- Each RSS check stores status, HTTP response, latency, rows seen, sample titles, and error details.
- News ingestion records completed, partial, or failed status without hiding feed-level errors.
- Twitter/X remains `blocked_credentials`; no unauthenticated workaround is used.

## Exchange Filings

- NSE announcements use the existing official exchange adapter.
- BSE moved from the retired `AnnGetData` response to `AnnSubCategoryGetData` with required page numbers.
- BSE collection requests each trading date separately and paginates within the date because multi-day API requests did not reliably return all records.
- Exchange timestamps are treated as India time and normalized to UTC.
- Final production pass processed 250 NSE and 250 BSE announcements with idempotent filing/event upserts.

## Filing Extraction

- Selection order is special event, held symbol, watched symbol, then routine filing.
- The scheduled loop extracts four material-first PDFs per run.
- Failed PDFs retry at most three times with a six-hour cooldown.
- PDFs and extracted text use `AI_OS_ARTIFACT_ROOT` on the external SSD.
- Clock-time values can no longer be misclassified as share or entitlement ratios; the affected live rows were repaired and the invalid-ratio check returned zero.
- Extracted terms remain research evidence requiring analyst and committee review.

## Scheduler And Agent Routing

- The launchd agent daemon runs the source loop hourly.
- The deployed daemon resolves workload scripts from the external runtime root rather than its service deployment directory.
- The loop enables two-day filing lookback, up to 250 announcements per exchange, four filing extractions, 12 configured news-feed slots, 16 discovery candidates, and one top candidate route.
- First unattended verified run `strategy_discovery_scheduler_20260713081752` completed with no scheduler error.
- The final full pass completed news, filings, extraction, discovery, and routing with zero pipeline errors and no seed data.

## Operator Surface

Holdings Research now shows:

- Source Intelligence with active feed count and current health checks;
- source links, latency, rows seen, and status;
- guarded `Run source loop` control;
- combined news, filing, and extraction run history;
- 100 bounded filing rows;
- 80 current news rows;
- 60 special-situation rows;
- 80 generated ideas;
- 98 research output artifacts;
- global broker execution lock.

The current scoped response contains 766 live rows. It does not request the compatibility broad snapshot and does not use client-side seed fallback.

## Verification

- API health passed with Postgres available and TradingView CDP live.
- The production research snapshot returned 15 feeds, 10 source checks, 16 news runs, 20 filing runs, 24 extraction runs, 100 filings, and 80 news rows.
- Python compilation, migration application, frontend production build, six targeted Research/Long-Term browser tests, the full 23-case WCAG A/AA suite, MCP smoke, and the 24-module vault-path contract all passed.
- Blueprint sync `blueprint-v10-research-intelligence-v1-20260715` completed with 21 domains, 523 requirements, 81 done, 168 partial, 274 planned, and zero seed rows.
- Source and deployed API, UI index, and agent-daemon checksums match after restart; the current daemon log records `strategy_discovery=completed`.
- Desktop, mobile, and full-page browser artifacts are retained under `/Volumes/Devarsh SSD/AI OS Data/artifacts/output/playwright/2026-07-15-research-intelligence-v1`.
- Generated backtest, optimizer, and discovery artifacts remain external runtime evidence and are excluded from the source commit.

## Safety

- `seed_data=false` throughout the source and discovery pass.
- Broker writes remain disabled.
- Research promotion, strategy activation, capital allocation, client communication, and order execution still require their separate approval gates.
- Source errors remain visible as collector evidence and cannot be converted into unsupported confidence.

## Remaining Research Work

- Build general research-paper, annual-report, concall, presentation, credit-rating, and OCR ingestion.
- Add authenticated Twitter/X collection only after credentials and collection policy approval.
- Complete the detector catalog and spread/arbitrage monitoring.
- Add document-level evidence drawers, annotation, extraction correction, and re-run controls.
- Add research-quality evaluations and promotion gates for agent-generated theses and strategy ideas.
