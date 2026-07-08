# Source Manifest

## Sources

### ps 2 cursor archive

Path:

`/Volumes/Devarsh SSD/ps 2 cursor.zip`

Size:

`936 MB`

Observed contents:

- Portfolio/client app archive
- Frontend/backend files
- Docker compose files
- CSV imports
- Zerodha access token scripts
- Backend `.env`
- Node modules

Handling:

- Extract only into `_ai_os_runtime/imports/quarantine`.
- Do not copy secrets into Obsidian.
- Inventory schema and column names before importing rows.

### Algo trading terminal

Path:

`/Volumes/Devarsh SSD/algo based trading software 2`

Data files:

- `data/trades.db`
- `data/storage/app.db`
- `data/storage/prices.db`

Handling:

- Import historical rows into Postgres/TimescaleDB.
- Preserve original DBs read-only.
- Build MCP tools against the new warehouse, not directly against old DBs.

