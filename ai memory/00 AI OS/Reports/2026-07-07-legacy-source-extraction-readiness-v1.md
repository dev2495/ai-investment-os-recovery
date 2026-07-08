# Legacy Source Extraction Readiness v1

Date: 2026-07-07

## What Was Added

The AI OS now has a real readiness layer for legacy data extraction from:

- p2cursor client archive
- old algo trading SQLite databases

This does not pretend extraction is complete. It separates:

- profiled source files/tables,
- staged p2cursor CSV rows,
- promoted/imported destination rows,
- partially promoted old algo tables,
- high-value unpromoted old algo tables,
- open Data Steward review issues.

## Warehouse Objects

Migration:

- `_ai_os_runtime/postgres/init/107_legacy_source_extraction_readiness.sql`

New tables:

- `core.legacy_source_extraction_runs`
- `core.legacy_source_extraction_issues`

New views:

- `client_data.v_p2cursor_extraction_readiness`
- `core.v_algo_extraction_readiness`
- `core.v_legacy_source_readiness_summary`
- `core.v_legacy_source_extraction_runs`
- `core.v_legacy_source_extraction_issues`

New function:

- `core.run_legacy_source_extraction_readiness(actor)`

## API

New POST route:

- `POST /api/legacy-source-readiness/run`

New snapshot keys:

- `legacy_source_readiness_summary`
- `p2cursor_extraction_readiness`
- `algo_extraction_readiness`
- `legacy_source_extraction_runs`
- `legacy_source_extraction_issues`

## MCP

New tools:

- `ai_os_legacy_source_readiness`
- `ai_os_run_legacy_source_readiness`

Broad MCP smoke now reports `tool_count: 126`.

## AI Office UI

Added dashboard panels:

- `Legacy Source Readiness`
- `P2/Algo Extraction Coverage`

The UI can now run a readiness sweep and show p2/algo extraction gaps without leaving the dashboard.

## Live Evidence

Latest verified sweep:

- Status: `needs_review`
- p2cursor source files: `6`
- p2cursor CSV files: `4`
- p2cursor staged rows: `139`
- p2cursor files needing mapping/promotion: `5`
- old algo profiled tables: `21`
- old algo profiled source rows: `1,361,017`
- old algo promoted/imported rows: `197,703`
- old algo partial tables: `5`
- old algo unpromoted tables: `5`
- high-priority extraction gaps: `6`
- issue count per latest run: `15`

High-value old algo gaps include:

- `daily_bars`: `1,038,186` source rows, `0` promoted rows.
- `straddle_snapshots`: `4,367` source rows, `0` promoted rows.
- `ticks`: `318,066` source rows, `197,595` promoted rows.
- `portfolio_snapshots`: `22` source rows, `11` promoted rows.
- `trades`: partial promotion.
- `holdings`: partial promotion.

p2cursor readiness:

- 4 CSV files are staged but still need mapping/promotion.
- 1 SQLite database is profiled but still needs table-level mapping.
- 1 JSON reference artifact is profiled.

## Verification

Commands/checks passed:

- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/107_legacy_source_extraction_readiness.sql`
- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `npm --prefix _ai_os_runtime/ai-office-ui run build`
- `POST /api/legacy-source-readiness/run`
- `GET /api/snapshot`
- direct MCP calls for `ai_os_legacy_source_readiness` and `ai_os_run_legacy_source_readiness`
- `python3 _ai_os_runtime/scripts/smoke_mcp_tools.py`
- `GET /api/health`

Runtime:

- API health: `ok: true`
- External SSD runtime root: `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`
- UI bundle served: `/assets/index-kBP5HSA2.js`

Known external gap:

- TradingView CDP remains unavailable on port `9222`; unrelated to this extraction work.

## Remaining Work

This completes the readiness/control layer, not full extraction.

Next required work:

- Map p2cursor staged CSV rows into normalized client/account/trade-history tables.
- Map p2cursor SQLite tables or explicitly exclude empty/non-useful tables.
- Promote old algo `daily_bars` into canonical OHLCV or mark excluded with rationale.
- Promote or archive old algo `straddle_snapshots` for options strategy research.
- Reconcile partial tick, snapshot, trade, and holding imports.
- Add source-level data quality scores once promotion rules are defined.

