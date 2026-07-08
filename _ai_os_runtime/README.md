# AI OS Runtime

Local runtime workspace for the AI office.

This folder is separate from the Obsidian vault notes. Use it for databases, MCP servers, ETL scripts, quarantined imports, and local service configuration.

## Layout

- `postgres/init`: database initialization SQL
- `ai-office-ui`: first React command-center GUI
- `config`: model routing, agent roster, and MCP tool policy
- `mcp_server`: read/write/browser MCP tools for agents
- `scripts`: import and maintenance scripts
- `imports/quarantine`: extracted source archives and raw imports
- `docker_data`: reserved for external exports/backups and staged service data
- `docs`: runtime notes that are too operational for Obsidian

## Runtime Services

- `ai_os_postgres`: Postgres + TimescaleDB on port `54329`
- `ai_os_qdrant`: vector database on ports `6333` and `6334`
- `ai_os_redis`: queue/cache runtime on port `63799`

Persistent service data uses Docker-managed named volumes. Since Docker Desktop's disk image has been moved to the external SSD, those volumes live inside the external Docker disk image and avoid macOS bind-mount/FUSE issues for databases.

Important: Docker Desktop image layers and named volumes use Docker Desktop's disk image location. Keep that location on the external SSD.

Runbook:

```text
docs/docker_external_ssd_storage.md
```

## Current MVP

The first runnable GUI lives in `ai-office-ui`.

```bash
cd _ai_os_runtime/ai-office-ui
npm install
npm run dev
```

Local URL:

```text
http://127.0.0.1:5177/
```

The current app uses seed data for the command center, inbox, approvals, signals, portfolio alerts, agent status, system health, control-plane modules, data-source registry, strategy registry, Fincept bridge, and manual holding staging. The next step is replacing seed data with a local DB/API adapter.

MCP is now the useful agent tool layer:

- 47 callable `ai_os_*` tools.
- Read tools for agents, portfolios, trades, research, Fincept, signals, and control-plane state.
- Write tools for tasks, inbox, approvals, research ideas, artifacts, manual clients/holdings, and Obsidian write-back.
- Browser-run tools for queueing/logging/capturing source research and UI inspection.
- TradingView task tools for auditable chart/screener/options work requests.
- Manual and paper trade ledger tools for actual trades, system alerts, and paper/backtest follow-through.
- Research hub refresh tools for local Codex/Claude/cowork reports and dashboards.
- Public source check tools for SEC/NSE/BSE connectivity status.
- Audit log table: `agent.mcp_audit_log`.

Manual client and holding workflows are live through MCP:

```text
ai_os_upsert_client
ai_os_stage_holding_update
ai_os_apply_holding_update
```

Core smoke tests:

```bash
_ai_os_runtime/scripts/smoke_mcp_tools.py
_ai_os_runtime/scripts/smoke_manual_portfolio_tools.py
_ai_os_runtime/scripts/smoke_mcp_write_browser_tools.py
_ai_os_runtime/scripts/smoke_mcp_connectors_trade_research_tools.py
```

## Start Order

1. Move Docker Desktop disk image location to external SSD.
2. Validate Compose config.
3. Start Postgres/Timescale, Qdrant, and Redis.
4. Index Obsidian vault into `knowledge.*`.
5. Import old trade history and journals into `trading.*`.
6. Use MCP read/write/browser tools.
7. Add filings/news/browser collectors.
8. Connect Jarvis model router.
9. Connect the AI Office UI to MCP/DB state.

## Start Commands

Run only after Docker Desktop disk image location is external:

```bash
cd "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime"
cp .env.example .env
bash scripts/verify_external_storage.sh
bash scripts/start_runtime.sh
```

## Health Commands

```bash
docker compose ps
docker exec ai_os_postgres pg_isready -U ai_os -d ai_os
curl -s http://127.0.0.1:6333/readyz
docker exec ai_os_redis redis-cli ping
```

## Foundation Scripts

```bash
scripts/create_qdrant_collections.py
scripts/inventory_sources.py
```

## Safety

Do not commit secrets. Do not paste broker or client credentials into chat. Do not enable write/execution tools until read-only import and reporting are verified.
