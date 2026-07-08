# Raw Artifact Import Coverage - 2026-07-06

## Outcome

The tracked file-import surfaces now have raw-artifact lineage in the live warehouse. This closes the immediate gap where client/import rows could exist without a durable `core.raw_artifacts` pointer.

## Implemented

- Added migration `_ai_os_runtime/postgres/init/075_raw_artifact_import_coverage.sql`.
- Added `raw_artifact_id` to `client_data.source_files`.
- Added `raw_artifact_id` to `client_data.attached_transaction_files`.
- Backfilled p2cursor profiled files into `core.raw_artifacts`.
- Backfilled attached broker/option-log files into `core.raw_artifacts`.
- Backfilled imported broker/PDF source-system file locations into `core.raw_artifacts`.
- Added `core.v_import_artifact_coverage`.
- Added `core.v_import_artifact_gaps`.
- Registered MCP tools in `agent.tool_registry`:
  - `ai_os_import_artifact_coverage`
  - `ai_os_import_artifact_gaps`
- Exposed API snapshot keys:
  - `import_artifact_coverage`
  - `import_artifact_gaps`
- Added an AI Office dashboard panel named `Artifact Coverage`.
- Patched `_ai_os_runtime/scripts/ingest_attached_transactions.py` so future attached transaction imports create/link raw artifacts.
- Patched `_ai_os_runtime/scripts/register_p2cursor_profiles.py` so future p2cursor profiling runs create/link raw artifacts.

## Live Evidence

Database coverage:

```text
client_data.attached_transaction_files      total=3 linked=3 missing=0 coverage=100.00
client_data.source_files                    total=6 linked=6 missing=0 coverage=100.00
core.source_systems.imported_file_locations total=6 linked=6 missing=0 coverage=100.00
```

Gap view:

```text
core.v_import_artifact_gaps rows = 0
```

Raw artifact inventory:

```text
core.raw_artifacts total rows = 146
import-specific raw artifacts = 12
```

Source lineage alignment:

```text
attached_transaction_file rows = 3, rows_with_raw_artifact = 3
p2cursor_source_file rows = 6, rows_with_raw_artifact = 6
raw_artifact rows = 146, rows_with_raw_artifact = 146
```

API verification:

```text
GET http://127.0.0.1:8765/api/health -> ok=true, db=ok, TradingView CDP available
GET http://127.0.0.1:8765/api/snapshot -> import_artifact_coverage rows=3, import_artifact_gaps rows=0
```

MCP verification:

```text
tools/list contains ai_os_import_artifact_coverage = true
tools/list contains ai_os_import_artifact_gaps = true
tools/call ai_os_import_artifact_coverage -> 3 coverage rows, all 100%
tools/call ai_os_import_artifact_gaps -> 0 rows
```

Script verification:

```text
python3 -m py_compile:
  _ai_os_runtime/api/ai_os_api_server.py
  _ai_os_runtime/mcp_server/ai_os_mcp_server.py
  _ai_os_runtime/scripts/ingest_attached_transactions.py
  _ai_os_runtime/scripts/register_p2cursor_profiles.py

npm run build in _ai_os_runtime/ai-office-ui -> passed

Bundled Python rerun of ingest_attached_transactions.py:
  attached_transaction_files = 3
  attached_broker_transactions = 1696
  attached_option_log_transactions = 531
  attached_client_trade_ledger = 2227
```

## Current Boundary

This verifies the current tracked file-import surfaces. New future import classes must either use the same raw-artifact contract or add themselves to `core.v_import_artifact_coverage` and `core.v_import_artifact_gaps`.

This change does not approve live trading, broker order placement, or autonomous capital action.
