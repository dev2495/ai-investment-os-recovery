# TradingView MCP and No Seed Live Stack Report

Date: 2026-07-02

## Decision

Use a hybrid TradingView setup:

- `atilaahmettaner/tradingview-mcp` is the preferred read/data connector for screeners, indicators, backtest-style analysis, and market-data workflows.
- `tradesdontlie/tradingview-mcp` is the preferred gated desktop controller for TradingView Desktop chart actions, Pine work, drawings, alerts, replay, and layout control.
- `cklose2000/pinescript-mcp-server` stays reference-only because licensing/runtime assumptions are not suitable for the core stack.

TradingView Desktop is currently open, but CDP port `9222` is not enabled. Desktop chart-control MCP should not be activated until TradingView is relaunched with local remote debugging and the current layout is preserved.

## No Seed Gate

The AI Office dashboard now runs in no-seed mode:

- Frontend seed data file removed.
- No fallback mock portfolio, signal, alert, brief, or agent rows are displayed.
- Dashboard sections show warehouse-backed rows only.
- Empty states now mean the source is not connected or has no rows.
- `GET /api/snapshot` returns `data_mode.seed_data_allowed = false`.

## Live Services

macOS LaunchAgents now supervise:

- API: `com.devarsh.aios.api` on `http://127.0.0.1:8765`
- UI: `com.devarsh.aios.ui` on `http://127.0.0.1:5177`

Operational scripts:

- Start/restart: `_ai_os_runtime/scripts/start_ai_office_live.sh`
- Stop: `_ai_os_runtime/scripts/stop_ai_office_live.sh`

Runtime/data source of truth remains the external SSD:

- `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`

Because launchd was blocked from directly reading the removable volume, a tiny supervised runner bundle was installed under:

- `/Users/devarshthakkar/Library/Application Support/AIOS`

This internal bundle contains only the runnable API copy and static UI build. Docker/Postgres/Qdrant data and the vault brain remain on the external SSD.

## Verification Evidence

- API LaunchAgent: running.
- UI LaunchAgent: running.
- UI HTTP check: `HTTP/1.0 200 OK`.
- API health: `ok`, DB status `ok`, runtime root points to external SSD.
- Snapshot response: 3.97 seconds.
- Snapshot issues: 0.
- Metrics returned: 19.
- Pipeline readiness rows: 16.
- Frontend build: `npm run build` passed.
- API compile: `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py` passed.
- Seed scan: no active frontend/API seed fallback references.

## Current Real Data Counts

- AI research artifacts: 93.
- Attached broker transactions: 1,696.
- Attached option-log rows: 531.
- Attached transaction files: 3.
- p2cursor CSV rows: 139.
- p2cursor file profiles: 6.
- Public source checks: 8.
- MCP tool registry entries: 57.
- Control-plane modules: 11.
- TradingView tasks: 0.
- Trade activity rows: 0.
- Linked live clients: 0.
- Linked live client accounts: 0.
- Linked live portfolio positions: 0.
- Staged holding updates: 0.

Legacy algo holdings exist as imported residue but are unlinked to real client folios, so they are excluded from live portfolio readiness:

- Legacy algo unlinked holdings: 3.

## Next Step

Now build the first real agent loop:

1. Create/import real client records and link accounts/holdings.
2. Enable TradingView Desktop CDP and test the gated desktop controller.
3. Turn the approved MCPs into agent tools with audit logging.
4. Start worker agents for news/filings, portfolio monitoring, strategy monitoring, and research write-back.
