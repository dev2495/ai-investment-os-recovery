# Sprint 02 - Foundation Stack

## Status

Foundation running.

## Built

Runtime stack:

- Postgres + TimescaleDB
- Qdrant vector database
- Redis queue/cache

Runtime path:

```text
_ai_os_runtime
```

Compose file:

```text
_ai_os_runtime/docker-compose.yml
```

External Docker storage:

```text
/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw
```

Docker-managed named volumes:

```text
ai-os-runtime_ai_os_pgdata
ai-os-runtime_ai_os_qdrant_data
ai-os-runtime_ai_os_redis_data
```

Reason: Qdrant warned about macOS/FUSE bind mounts. Since Docker Desktop's disk image is now external, named volumes keep data on the SSD while using a Linux filesystem inside Docker.

## Schemas

Added:

- Obsidian graph and vector registry
- Portfolio clients, positions, and holding theses
- Corporate filings
- Filing-derived special-situation events
- News items
- Social/X items
- Research ideas
- Trade journals
- Strategy candidates and backtest runs
- Agent tasks, inbox, approvals, tool registry, and model routes
- Browser research runs

SQL files:

```text
_ai_os_runtime/postgres/init/001_core.sql
_ai_os_runtime/postgres/init/002_intelligence_os.sql
_ai_os_runtime/postgres/init/003_source_components.sql
_ai_os_runtime/postgres/init/004_strategy_alerting.sql
_ai_os_runtime/postgres/init/005_p2cursor_profiles.sql
_ai_os_runtime/postgres/init/006_p2cursor_csv_staging.sql
_ai_os_runtime/postgres/init/007_agent_profiles.sql
_ai_os_runtime/postgres/init/008_read_models.sql
_ai_os_runtime/postgres/init/009_task_idempotency.sql
_ai_os_runtime/postgres/init/010_source_components_and_algo_import.sql
_ai_os_runtime/postgres/init/011_component_read_models.sql
```

## Config

Added:

```text
_ai_os_runtime/config/model_routes.yml
_ai_os_runtime/config/agents.yml
_ai_os_runtime/config/mcp_tools.yml
```

These define:

- Jarvis model routing
- Agent departments
- MCP tool permissions
- Browser agent guardrails
- Approval-required actions

## Docker Storage Guard

Added:

```text
_ai_os_runtime/scripts/verify_external_storage.sh
_ai_os_runtime/scripts/start_runtime.sh
_ai_os_runtime/docs/docker_external_ssd_storage.md
```

Current verification result:

```text
OK: runtime root is on external SSD.
OK: compose config is valid.
OK: Docker Desktop disk image appears external: /Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw
OK: Docker-managed volumes will be stored inside the external Docker disk image.
```

Runtime started successfully.

Images:

```text
timescale/timescaledb:latest-pg16  2.08GB
qdrant/qdrant:latest               281MB
redis:7-alpine                     58.7MB
```

External Docker disk used:

```text
2.4G /Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw
```

## Health Checks

Verified:

```text
Postgres: healthy
TimescaleDB extension: installed
Qdrant: all shards ready
Redis: PONG
```

Schema table counts:

```text
agent: 7
client_data: 3
core: 4
knowledge: 3
market: 2
ops: 1
portfolio: 6
research: 3
risk: 2
strategy: 7
trading: 5
```

Timescale hypertables:

```text
portfolio.snapshots
strategy.performance_snapshots
trading.ohlcv
trading.ticks
```

Qdrant collections:

```text
obsidian_notes_mxbai_embed_large
corporate_filings_mxbai_embed_large
trade_journals_mxbai_embed_large
news_social_mxbai_embed_large
research_reports_mxbai_embed_large
strategy_artifacts_mxbai_embed_large
```

## Obsidian Vault Index

Added:

```text
_ai_os_runtime/scripts/index_obsidian_vault.py
```

Current result:

- 29 notes indexed into `knowledge.obsidian_notes`.
- 3 wikilinks indexed into `knowledge.note_links`.
- `_ai_os_runtime` and hidden/runtime folders are skipped.

## Source Inventory

Metadata-only inventory saved:

```text
_ai_os_runtime/imports/source_inventory.json
```

Findings:

- `ps 2 cursor.zip`: exists, about 981 MB, 187,071 entries, many app/node artifacts, 170 CSV files, sensitive paths flagged.
- Old algo system: 186 tracked files excluding heavy/generated folders, 163 Python files, 3 SQLite DBs.
- `trades.db`: table `trades`.
- `app.db`: accounts, holdings, journal, ideas, portfolio_snapshots, saved_strategies, ticks, trades, tradingview_signals, watchlist, and options snapshots.
- `prices.db`: backtest_runs, daily_bars, live_signals, regime_runs, token_map.

## Source Components Registered

Registered in `core.source_components`:

- p2 cursor client portfolio data
- p2 cursor equity charts and portfolio UI patterns
- algo historical price data
- algo trade history and journals
- algo strategy library and backtesting engine
- algo TradingView webhook bridge
- algo live strategy monitor and alerts

## Source Component Extraction

Added:

```text
_ai_os_runtime/scripts/inventory_source_components.py
_ai_os_runtime/imports/source_components_manifest.json
_ai_os_runtime/imports/quarantine/algo_components
_ai_os_runtime/imports/quarantine/p2cursor_components
```

Results:

- 284 reusable source files registered in `core.source_code_files`.
- 147 files from p2cursor.
- 137 files from old algo trading software.
- 81 package requirements registered in `core.source_requirements`.
- 21 SQLite source tables profiled in `core.source_table_profiles`.

Main component groups:

- dashboard UI
- portfolio engine
- strategy library
- quant lab
- market data
- news/research
- ideas/watchlist
- indicator library
- trade journal
- backtesting engine
- TradingView webhook
- agent loop
- alerts

## p2cursor Safe Extraction

Added scripts:

```text
_ai_os_runtime/scripts/p2cursor_extract_candidates.py
_ai_os_runtime/scripts/p2cursor_profile_candidates.py
_ai_os_runtime/scripts/register_p2cursor_profiles.py
_ai_os_runtime/scripts/ingest_p2cursor_csv_staging.py
```

Output files:

```text
_ai_os_runtime/imports/p2cursor_extract_manifest.json
_ai_os_runtime/imports/p2cursor_profile.json
_ai_os_runtime/imports/quarantine/p2cursor_selected
```

Results:

- Extracted 6 safe data candidates from p2cursor quarantine: 4 CSV, 1 SQLite, 1 JSON.
- Skipped generated/dependency paths, credential-like paths, symlinks, Mac resource forks, and non-data suffixes.
- Registered 6 files in `client_data.source_files`.
- Staged 139 CSV rows into `client_data.p2cursor_csv_rows`.
- Created a queued high-priority Data Steward task: `Map p2cursor client portfolio datasets`.

## Active Agent Profiles

Added:

```text
agent.profiles
```

Live profile count:

- 14 active agent profiles.

Departments:

- orchestration
- executive
- data
- portfolio
- research
- trading
- quant

Seeded model routes now include:

- `obsidian_retrieval_summary`
- `news_curation`
- `strategy_generation`

## Read Models

Added MCP/UI-friendly views:

- `agent.v_active_agents`
- `agent.v_open_tasks`
- `client_data.v_p2cursor_source_summary`
- `knowledge.v_obsidian_note_index`
- `portfolio.v_latest_positions`
- `trading.v_recent_signals`
- `strategy.v_open_alerts`
- `market.v_recent_news`
- `core.v_source_component_inventory`
- `core.v_source_requirements`
- `core.v_source_table_profiles`
- `core.v_algo_import_summary`

Current populated view checks:

- `agent.v_active_agents`: 14 rows.
- `agent.v_open_tasks`: 1 row.
- `client_data.v_p2cursor_source_summary`: 4 CSV files with 139 staged rows, plus 1 JSON and 1 SQLite profile.
- `knowledge.v_obsidian_note_index`: 30 rows.
- `core.v_algo_import_summary`: old algo import counts.

## Algo SQLite Import

Added:

```text
_ai_os_runtime/scripts/ingest_algo_sqlite.py
_ai_os_runtime/imports/algo_import_summary.json
```

Rows seen from old SQLite:

- ticks: 318,066 seen, 197,595 deduplicated imported.
- daily bars: 1,038,186 imported.
- accounts: 2.
- holdings/positions: 3.
- portfolio snapshots: 22.
- trades: 4 total across app/tradebook DBs.
- journal entries: 1.
- TradingView signals: 1.
- ideas/watchlist: 29.
- backtest/regime runs: 16.

Warehouse counts after import:

- `trading.ohlcv`: 1,038,186.
- `trading.ticks`: 197,595.
- `portfolio.accounts`: 2.
- `portfolio.positions`: 3.
- `portfolio.snapshots`: 22.
- `portfolio.trades`: 4.
- `research.ideas`: 29.
- `strategy.backtest_runs`: 16.

Repeated-error note:

- The importer hit the same PostgreSQL `ON CONFLICT` constraint error twice.
- Per project rule, implementation paused and the PostgreSQL `INSERT ... ON CONFLICT` docs were checked.
- Fix chosen: regular unique indexes matching the importer conflict targets instead of partial unique indexes.

## MCP Server

Added:

```text
_ai_os_runtime/mcp_server/ai_os_mcp_server.py
_ai_os_runtime/mcp_server/README.md
```

Smoke-tested tools:

- `initialize`
- `tools/list`
- `ai_os_algo_import_summary`
- `ai_os_component_inventory`

Available tools:

- `ai_os_list_active_agents`
- `ai_os_list_open_tasks`
- `ai_os_p2cursor_source_summary`
- `ai_os_algo_import_summary`
- `ai_os_component_inventory`
- `ai_os_source_requirements`
- `ai_os_search_obsidian_notes`
- `ai_os_recent_trading_signals`
- `ai_os_latest_positions`
- `ai_os_reindex_obsidian`

## Agent Runner

Added:

```text
_ai_os_runtime/agents/agent_runner.py
_ai_os_runtime/agents/README.md
```

Verified:

- Ran Jarvis agent tick.
- Wrote output note to `ai memory/00 AI OS/Agent Outputs/20260701T155048Z-jarvis-tick.md`.
- Logged run in `agent.run_log`.
- Reindexed Obsidian after the note write.
- Obsidian indexed notes increased from 29 to 30.

Added task idempotency:

- One open task per title, owner, source kind, and source reference.
- Removed one duplicate p2cursor Data Steward task created during registration testing.

## Next Build Step

Build the first read-only ingestion tools:

1. Map p2cursor raw CSV rows into safe portfolio/client staging views.
2. Build first real MCP client config for Codex/local Jarvis.
3. Add local model route adapter for Ollama/LM Studio/MLX.
4. Add UI API over read views.
5. Connect AI Office UI to Agent Inbox, Strategy Monitor, Portfolio, and Knowledge views.
6. Build browser research runner for NSE/BSE/news ingestion.
7. Add embeddings for Obsidian notes, journals, filings, and research artifacts.

Do not extract the p2 cursor zip fully. Continue with selective quarantine extraction only.
