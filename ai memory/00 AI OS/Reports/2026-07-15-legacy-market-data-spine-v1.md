# Legacy Market Data Spine v1

Date: 2026-07-15
Status: verified research-data checkpoint

## Outcome

The AI Investment OS now imports the recovered algo terminal market databases through a checksum-preserved, idempotent, quality-gated pipeline. Daily OHLCV is deep enough for research preflight, while intraday and options evidence remain explicitly insufficient. Historical data never grants broker or capital-execution authority.

## Verified Data

| Dataset | Source rows | Canonical rows | Symbols | Coverage | Readiness |
|---|---:|---:|---:|---|---|
| Daily OHLCV | 1,038,186 | 1,038,186 | 502 source / 516 warehouse | 2016-01-01 to 2026-06-12 | Research-ready with bias audit required |
| Ticks | 318,066 | 197,595 | 14 | 2026-05-14 to 2026-05-15 | Insufficient depth |
| Straddle snapshots | 4,367 | 4,367 | 1 | 2026-05-13 to 2026-05-16 | Insufficient depth |

All three SQLite files returned `PRAGMA quick_check = ok`. Daily rows had zero missing fields, nonpositive prices, hard OHLC-bound failures, negative volume, or future dates. Four floating-point boundary deviations were corrected within `1e-9`. Tick deduplication records 120,471 duplicate source keys rather than counting them as new observations.

## Contracts

- `market.dataset_contracts` records adjustment, point-in-time, survivorship, research, and execution policy.
- `market.market_data_import_runs` records immutable path/hash, source/canonical/inserted rows, corrections, deduplication, coverage, and status.
- `market.market_data_quality_checks` records five hard checks plus the mandatory research-bias warning per run.
- `trading.option_strategy_snapshots` stores straddle observations with raw-artifact lineage.
- `market.v_strategy_market_data_readiness` exposes coverage, staleness, readiness, and next action.
- Seven legacy/client schema mappings validate against canonical warehouse relations.
- The six P2Cursor archive files now have explicit promoted, duplicate, excluded, empty, or reference resolution states.

## Operating Surface

- Scoped Gateway snapshot: 11 query groups, including readiness, contracts, import ledger, and quality checks.
- Fixed API job: `legacy_market_data_manual_ingestion` completed through the live service with 1,240,148 canonical rows reported.
- MCP: 146 callable tools; `ai_os_market_data_readiness` returns five readiness rows, three contracts, and persisted imports; `ai_os_run_legacy_market_data_ingestion` invokes only the fixed job.
- UI: Strategy Data Readiness panel shows coverage, staleness, caveats, deduplication, corrections, quality, and bounded revalidation.

## Strategy Gate

The canonical-symbol fix prevents `TCS` and `NSE:TCS` aliases from becoming false under-coverage failures. Candidate 1 passed the real daily gate for RELIANCE and TCS with 5,164 total rows, a minimum 2,581 rows per symbol, no missing symbols, and 2016-01-01 through 2026-06-12 coverage.

## Verification

- Migration 119 passed a rollback transaction test, then applied idempotently.
- Importer completed directly and through the live API job executor.
- Second import produced zero new daily/straddle rows and stable canonical counts, proving idempotency.
- MCP smoke passed with 146 tools.
- TypeScript compilation and Vite production build passed using a temporary writable output directory; dependencies/cache remain on SSD.
- Focused Gateway browser suite passed 5/5, including mobile overflow.
- Accessibility suite passed all 37 WCAG A/AA cases after making the import ledger keyboard focusable.
- Live API returns five readiness rows, three contracts, nine import runs after direct/API verification passes, and persisted quality evidence.

## Open Gates

- Verify corporate-action adjustment provenance and build a canonical adjustment pipeline.
- Add point-in-time universe membership and delisted securities to remove survivorship bias.
- Refresh the daily tail beyond 2026-06-12 from an approved recurring provider.
- Expand intraday coverage beyond two days and 14 symbols.
- Add full option chains, contract master, OI, Greeks, broader underlyings/expiries, futures basis, and VIX.
- Complete historical equity curves, old strategy artifacts, journals, and explicit disposition of remaining legacy tables.
- Keep all live/broker execution locked until paper, risk, reconciliation, security, compliance, and approval gates pass.

## Evidence Paths

- Migration: `_ai_os_runtime/postgres/init/119_legacy_market_data_spine_v1.sql`
- Importer: `_ai_os_runtime/scripts/ingest_algo_sqlite.py`
- API: `_ai_os_runtime/api/ai_os_api_server.py`
- MCP: `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- UI: `_ai_os_runtime/ai-office-ui/src/views/IntegrationGatewayWorkspace.tsx`
- Import summary: `ai memory/00 AI OS/Reports/Evidence/algo_import_summary.json`
- Checklist: [[AI Investment OS - Execution Checklist v10.0]]
- Blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]
