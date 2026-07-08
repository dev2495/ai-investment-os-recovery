---
type: implementation_report
tags:
  - ai-os
  - control-plane
  - portfolio
  - mcp
  - fincept
created: 2026-07-02
---

# Control Plane and Manual Portfolio Workflow

## What Changed

The AI OS foundation now has a real control-plane layer in the external-SSD runtime.

Implemented migration:

```text
_ai_os_runtime/postgres/init/018_control_plane_and_manual_portfolio.sql
```

New warehouse registries:

- `core.control_plane_modules`
- `core.data_source_registry`
- `research.feed_registry`
- `strategy.strategy_registry`
- `agent.workflow_registry`
- `portfolio.manual_client_intake`
- `portfolio.manual_holding_updates`

New read models:

- `core.v_control_plane_overview`
- `core.v_data_source_registry`
- `core.v_control_plane_snapshot`
- `research.v_feed_registry`
- `strategy.v_strategy_registry`
- `agent.v_workflow_registry`
- `portfolio.v_client_control_plane`
- `portfolio.v_manual_holding_update_queue`

Seeded operating map:

- 11 control-plane modules
- 10 data sources
- 6 strategy registry entries
- 7 workflows
- 5 research/news/feed registry entries

## MCP Tools

Updated server:

```text
_ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

New tools:

- `ai_os_control_plane_snapshot`
- `ai_os_upsert_client`
- `ai_os_stage_holding_update`
- `ai_os_apply_holding_update`

The server now exposes 22 tools total.

Manual client and holding write policy:

- Writes are local warehouse writes only.
- No broker orders are placed.
- No broker account state is changed.
- A staged holding update must exist before it can be applied into `portfolio.positions`.

## Manual Portfolio Workflow

Add or update a client/account:

```text
ai_os_upsert_client
```

Stage a holding:

```text
ai_os_stage_holding_update
```

Apply a staged holding into live warehouse positions:

```text
ai_os_apply_holding_update
```

The review queue is visible through:

```sql
SELECT * FROM portfolio.v_manual_holding_update_queue;
```

Client control state is visible through:

```sql
SELECT * FROM portfolio.v_client_control_plane;
```

## AI Office UI

Updated app:

```text
_ai_os_runtime/ai-office-ui
```

Added visible operating panels:

- Control Plane
- Manual Portfolio Updates
- Data Sources
- Strategy Registry
- Client Folios right rail
- Workflows right rail
- Fincept Bridge right rail

Important current limitation:

- The UI is still seed/local-state driven.
- Durable client and holding writes are live through MCP now.
- The next UI step is a small local API adapter so the dashboard reads/writes the warehouse directly.

## Fincept Role

FinceptTerminal remains an installed sidecar/component bridge, not the AI OS source of truth.

Related note:

```text
[[FinceptTerminal Installed Component]]
```

Use Fincept for reusable analytics, data-source, research, market-data, and quant workflow patterns. Keep the AI OS spine as:

```text
Postgres warehouse -> MCP tools -> agents -> Obsidian output
```

## Verification

Database migration:

```bash
python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/018_control_plane_and_manual_portfolio.sql
```

Control-plane counts:

```text
active_modules: 9
active_workflows: 4
clients: 0
control_modules: 11
data_sources: 10
mapped_or_online_sources: 4
paper_or_mapped_strategies: 2
registered_strategies: 6
registered_workflows: 7
staged_holding_updates: 0
```

MCP read smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_tools.py
```

Result:

```text
tool_count: 22
control_plane_metrics: 10
control_plane_modules: 11
control_plane_data_sources: 10
control_plane_strategies: 6
control_plane_workflows: 7
orchestration_rows: 15
client_summary_metrics: 7
open_symbol_rows: 3
research_rows: 3
fincept_components: 9
fincept_install_rows: 1
fincept_installed_components: 6
```

Manual portfolio write smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_manual_portfolio_tools.py
```

Result:

```text
temporary client/account created
holding update staged
holding update applied into portfolio.positions
temporary rows cleaned up
applied_status: applied
```

UI build:

```bash
cd _ai_os_runtime/ai-office-ui
npm run build
```

Result:

```text
tsc passed
vite build passed
```

Browser render:

```text
http://127.0.0.1:5177/
```

Checked:

- 1440px desktop with right rail visible
- 1200px desktop with right rail collapsed
- 390px mobile with one-column main content and horizontal workspace navigation

Temporary screenshots were removed after visual inspection.

## Next Build Step

The correct next step is not more agent names. It is wiring the dashboard to the warehouse and then giving agents controlled task tools.

Recommended next sprint:

1. Add local API adapter for AI Office UI.
2. Connect UI panels to `core.v_control_plane_snapshot`, `portfolio.v_client_control_plane`, and `portfolio.v_manual_holding_update_queue`.
3. Add task-create/update MCP tools for Charlie/Jarvis.
4. Add NSE/BSE filings collector.
5. Add TradingView MCP bridge adapter.
6. Add broker read-only holdings connector after credentials are stored safely.

Related notes:

- [[MCP Server and Agent Runner]]
- [[Data and Tool Architecture]]
- [[FinceptTerminal Installed Component]]
- [[Full Portfolio Intelligence OS Product Plan]]
