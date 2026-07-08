# P2Cursor Data Ingestion

## Decision

Use p2cursor as an input source, not as the live system.

The archive should stay quarantined. Only data-shaped files are extracted into `_ai_os_runtime/imports/quarantine/p2cursor_selected`, profiled, and registered before any rows are mapped into the portfolio warehouse.

## Current State

Source:

```text
/Volumes/Devarsh SSD/ps 2 cursor.zip
```

Quarantine output:

```text
_ai_os_runtime/imports/quarantine/p2cursor_selected
```

Manifest and profile:

```text
_ai_os_runtime/imports/p2cursor_extract_manifest.json
_ai_os_runtime/imports/p2cursor_profile.json
```

Warehouse tables:

```text
client_data.source_files
client_data.p2cursor_csv_rows
```

Imported so far:

- 6 candidate source files registered.
- 4 CSV files staged.
- 139 raw CSV rows staged as JSONB.
- 1 SQLite file profiled. It has portfolio/trade schema tables but zero rows.
- 1 JSON benchmark/sector-style file profiled.

## Guardrails

- No full archive extraction.
- No running the old p2cursor app as production.
- No raw client rows in chat output.
- Generated folders, dependency folders, symlinks, Mac resource forks, and credential-like paths are skipped.
- Data Steward must approve the field mapping before raw rows are promoted into canonical portfolio tables.

## Next Mapping Targets

Canonical tables:

- `portfolio.clients`
- `portfolio.accounts`
- `portfolio.positions`
- `portfolio.trades`

Staging views to create next:

- p2 account and portfolio map.
- p2 holding/import row map.
- p2 trade row map.
- symbol normalization map.
- client-safe display views for agents.

## Agent Ownership

Data Steward:

- Owns lineage, staging, field mapping, and safe views.

Portfolio Manager:

- Reviews mapped holdings, positions, and account-level portfolio meaning.

Risk Agent:

- Reviews concentration and data quality issues before downstream analysis.

Librarian Agent:

- Links imported datasets to Obsidian notes and future research folders.

Jarvis:

- Routes user requests to the correct agent and keeps approvals visible.
