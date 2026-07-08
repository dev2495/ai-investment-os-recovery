# Source Lineage And Artifact Visibility

Date: 2026-07-06
Blueprint: [[AI Investment OS - Institutional Master Blueprint v7.0]]
Checklist: [[AI Investment OS - Execution Checklist v7.0]]
Owner agent: Data Steward
Runtime operator: Jarvis

## Objective

Build the next foundation slice from v7: every production-facing portfolio/import row must become traceable to source systems, source files, raw artifacts, or reconciliation evidence.

## Runtime Recovery First

Before implementing, the external SSD and Docker runtime were verified:

- `diskutil verifyVolume "/Volumes/Devarsh SSD"` returned APFS exit code `0` and reported the volume appears OK.
- Docker Desktop was restarted after repeated daemon API `500` errors.
- `docker version` returned Docker Desktop `4.80.0`, engine `29.6.1`.
- `docker ps -a` showed `ai_os_postgres`, `ai_os_redis`, and `ai_os_qdrant` running.

## Database Objects Added

Migration:

- `_ai_os_runtime/postgres/init/074_source_lineage_artifact_visibility.sql`

Views:

- `core.v_source_artifact_lineage`
- `core.v_source_lineage_summary`

Control-plane module:

- `source_lineage`

MCP tool registry rows:

- `ai_os_source_lineage`
- `ai_os_source_lineage_summary`

## Coverage

`core.v_source_artifact_lineage` currently covers:

- `core.raw_artifacts`
- `client_data.source_files`
- `client_data.attached_transaction_files`
- `client_data.p2cursor_csv_rows`
- `portfolio.positions`
- `portfolio.p2cursor_reconciliation_issues`

This makes source visibility available for:

- AI/Codex/Claude/Cowork research outputs,
- NSE filing artifacts,
- p2cursor source files,
- p2cursor CSV staged rows,
- attached broker transaction files,
- current portfolio positions,
- p2cursor-vs-statement reconciliation issues.

## Live Evidence

Database count check:

```text
lineage_type                    rows
p2cursor_reconciliation_issue   180
p2cursor_csv_row                139
raw_artifact                    134
portfolio_position              72
p2cursor_source_file            6
attached_transaction_file       3
```

Sample lineage query showed CDSL reconciliation evidence for client `3081832`:

- p2cursor account: `p2cursor_account_2`
- comparison account: `tushit_3081282_statement`
- p2 quantity: `100`
- statement quantity: `200`
- issue type: `quantity_mismatch`
- severity: `high`

API verification:

```text
GET /api/health -> ok=true, db status ok, TradingView CDP available=true
GET /api/snapshot -> source_lineage_summary rows=18, source_artifact_lineage rows=150
```

MCP verification:

```text
tools/list included:
- ai_os_source_lineage_summary
- ai_os_source_lineage

tools/call ai_os_source_lineage_summary returned live summary rows.
tools/call ai_os_source_lineage with client_code=3081832 and symbol=CDSL returned live reconciliation evidence rows.
```

Build verification:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm run build
```

Both passed.

## UI Change

The AI Office dashboard now has a `Source Lineage` panel backed by the API snapshot:

- `source_lineage_summary`
- `source_artifact_lineage`

It shows lineage counts and recent source rows next to reconciliation and data-source surfaces.

## Checklist Updates

Marked done:

- `Source lineage view for every portfolio row`
- `Build source lineage/artifact view`

Marked partial:

- `Raw artifact store for every file import`

Reason: `core.raw_artifacts` is live and visible, but older attached transaction file imports are currently lineage-visible through `client_data.attached_transaction_files`; not every historical file import has a corresponding raw artifact row yet.

## Remaining Work

Next data-governance improvements:

1. Enforce raw artifact registration during every new Excel/PDF/CSV/browser import.
2. Add a lineage detail drawer in the UI so every dashboard row can reveal its exact source evidence.
3. Link `books.v_book_positions` and `portfolio.v_symbol_intelligence` directly to lineage references.
4. Add source-lineage checks to import acceptance gates.
5. Add raw artifact backfill for attached transaction files and Sanjana/Tushit PDFs.
