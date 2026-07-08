# Final Core Stack and Setup Plan

## Decision

Build a local-first AI office using OpenAlice-style workspaces, our own live database, MCP tools, and Obsidian memory.

Hermes can remain a model/agent experiment, but it should not be the main operating surface for the AI office. The main interaction layer should be a workspace UI plus Codex/Claude-style agent sessions with MCP tools.

## Where You Interact With Agents

Primary:

- OpenAlice-style Web UI for agent workspaces, inbox, portfolio dashboard, and scheduled runs.

Daily engineering and setup:

- Codex desktop/terminal for building and fixing the system.

Knowledge and decision memory:

- Obsidian vault for notes, roadmaps, research memos, source logs, runbooks, and graph view.

Optional:

- Hermes only as an experimental local agent/model shell, not the core operating system.

## Final Stack

### Interaction Layer

- OpenAlice as reference and possible base for workspace UI, Inbox, MCP surface, trading-as-git, and guard pipeline.
- Obsidian for knowledge graph, notes, and decision logs.
- Superset or custom dashboard later for management dashboards.

### Agent Orchestration

- LangGraph for Jarvis and multi-agent workflow orchestration.
- Native agent CLIs inside workspaces: Codex first, Claude/opencode optional.
- Agent roles: Jarvis, Data Steward, Trading Desk, Quant Team, Portfolio Manager, Risk, Research, Client Report Writer, MCP Toolsmith.

### Tool Layer

- MCP Python SDK for our internal tools.
- Read-only tools first:
  - `client_data.*`
  - `trading.*`
  - `portfolio.*`
  - `market_data.*`
  - `vault.*`

### Live Data Layer

- PostgreSQL plus TimescaleDB for live time-series and portfolio data.
- SQLite only as source/import format from old systems.
- DuckDB for fast local analytical staging if needed.

### Data Sources

- `ps 2 cursor.zip` from external SSD as client/portfolio app archive.
- Existing algo trading system:
  - `data/trades.db`
  - `data/storage/app.db`
  - `data/storage/prices.db`
- Zerodha/Kite collected live account data.
- TradingView webhook alerts.
- OpenBB and direct NSE/BSE/Yahoo/FRED adapters where useful.

### Quant and Portfolio Libraries

- VectorBT for fast signal/backtest research.
- PyPortfolioOpt for first portfolio optimization layer.
- Riskfolio-Lib for advanced risk and portfolio analytics.
- Qlib later for ML quant research after clean data exists.

### Charts

- TradingView webhooks for external chart-triggered alerts.
- TradingView Lightweight Charts or local chart components for internal UI.
- Stored OHLCV/tick data should be the chart source, not screenshots.

## OpenAlice Role

Use OpenAlice as a strong reference or base for:

- Web UI
- Workspace model
- Inbox
- MCP tool exposure
- Trading-as-git approval flow
- Guard pipeline
- UTA-style separation between decision layer and broker/execution layer

Do not blindly adopt:

- Broker stack without adapting to Zerodha/Kite
- Hosted TraderHub dependency
- Live execution until our own risk and approval gates exist

## Setup Requirements

Local tools:

- Git
- Node.js 22+
- pnpm 10+
- Python 3.11 or 3.12
- Docker Desktop
- PostgreSQL client tools
- Obsidian
- Codex CLI/Desktop

Python packages, first wave:

- `mcp`
- `fastapi`
- `uvicorn`
- `psycopg`
- `sqlalchemy`
- `pandas`
- `duckdb`
- `pyarrow`
- `pydantic`
- `vectorbt`
- `PyPortfolioOpt`
- `riskfolio-lib`

Database services:

- Postgres
- TimescaleDB extension

Secrets:

- Do not paste broker/API keys into chat.
- Existing `.env` files in the zip and trading systems must be quarantined and migrated manually.

## First Setup Milestone

Build a local read-only data spine:

1. Create import workspace outside the Obsidian notes vault.
2. Extract `ps 2 cursor.zip` into quarantine.
3. Inventory schemas and CSVs without exposing client rows.
4. Create Postgres/TimescaleDB schema.
5. Import historical live trading data from existing DBs.
6. Import p2/client portfolio data through safe staging.
7. Build first MCP server with read-only tools.
8. Connect Jarvis/Trading Desk/Data Steward to MCP tools.
9. Create first Obsidian-generated daily brief from live database data.

## Safety Gates

- Phase 1: read-only tools only.
- Phase 2: write notes and reports only.
- Phase 3: draft portfolio/trade plans only.
- Phase 4: paper trading approval flow.
- Phase 5: live order staging.
- Phase 6: live push execution only with human confirmation and guard checks.

