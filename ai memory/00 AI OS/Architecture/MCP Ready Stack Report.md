---
type: implementation_report
tags:
  - ai-os
  - mcp
  - browser
  - agents
  - portfolio
created: 2026-07-02
---

# MCP Ready Stack Report

## Status

The AI OS MCP layer is now useful as a real agent tool layer.

Current callable surface:

- 47 callable `ai_os_*` MCP tools.
- 10 internal runtime/tool-layer capabilities.
- 19 control-plane metrics.
- Full local write audit through `agent.mcp_audit_log`.
- Browser run queue/capture logging through `ops.browser_runs`.
- Obsidian write-back into structured `ai memory` folders.
- External MCP candidate registry through `core.mcp_integration_registry`.
- TradingView chart/screener task queue through `ops.tradingview_tasks`.
- Manual/paper trade activity ledger through `trading.trade_activity_ledger`.
- Research hub indexing for Codex/Claude/cowork outputs through `core.raw_artifacts`.
- SEC/NSE/BSE connectivity checks through `core.data_source_checks`.

No broker order placement or external posting tools were added.

## Runtime Fix

During this build, Docker Desktop returned inconsistent container state:

```text
docker ps: ai_os_postgres Up
docker inspect: ai_os_postgres exited
docker exec: container is not running
```

Then Docker surfaced an I/O error against container image/blob metadata.

Fix applied:

```bash
docker desktop restart
docker compose -f _ai_os_runtime/docker-compose.yml up -d
```

After restart:

- Postgres accepted connections.
- Redis returned `PONG`.
- Qdrant returned `all shards are ready`.

The MCP server was also hardened so SQL calls try `docker exec` first and then fall back to local Postgres on `127.0.0.1:54329`.

## New Migrations

```text
_ai_os_runtime/postgres/init/019_mcp_read_write_browser_foundation.sql
_ai_os_runtime/postgres/init/020_complete_mcp_tool_registry.sql
_ai_os_runtime/postgres/init/021_mcp_connectors_tradingview_trade_research_hub.sql
```

New table:

```text
agent.mcp_audit_log
```

Updated browser table:

```text
ops.browser_runs
```

New or updated views:

```text
ops.v_browser_runs
agent.v_recent_mcp_audit
agent.v_mcp_capability_matrix
core.v_control_plane_snapshot
core.v_mcp_integration_registry
ops.v_tradingview_tasks
trading.v_trade_activity_ledger
trading.v_paper_trade_summary
research.v_research_hub_summary
core.v_recent_data_source_checks
```

## MCP Tool Groups

Capability and audit:

- `ai_os_mcp_capabilities`
- `ai_os_mcp_audit_log`
- `ai_os_mcp_candidate_shortlist`

Control and agents:

- `ai_os_control_plane_snapshot`
- `ai_os_orchestration_stack`
- `ai_os_list_active_agents`

Tasks, inbox, and approvals:

- `ai_os_list_open_tasks`
- `ai_os_create_task`
- `ai_os_update_task_status`
- `ai_os_list_inbox`
- `ai_os_update_inbox_status`
- `ai_os_create_approval`
- `ai_os_decide_approval`

Portfolio and manual holdings:

- `ai_os_upsert_client`
- `ai_os_stage_holding_update`
- `ai_os_apply_holding_update`
- `ai_os_latest_positions`

Research, artifacts, and Obsidian:

- `ai_os_research_outputs`
- `ai_os_research_output_detail`
- `ai_os_refresh_research_hub`
- `ai_os_research_hub_summary`
- `ai_os_create_research_idea`
- `ai_os_record_raw_artifact`
- `ai_os_search_obsidian_notes`
- `ai_os_write_obsidian_note`
- `ai_os_reindex_obsidian`

Browser workflow:

- `ai_os_start_browser_run`
- `ai_os_complete_browser_run`
- `ai_os_browser_runs`

TradingView and trade ledger:

- `ai_os_create_tradingview_task`
- `ai_os_update_tradingview_task`
- `ai_os_tradingview_tasks`
- `ai_os_record_manual_trade`
- `ai_os_record_paper_trade`
- `ai_os_trade_activity`

Public data-source checks:

- `ai_os_run_public_data_source_check`
- `ai_os_data_source_checks`

Source, component, trading, and Fincept reads:

- `ai_os_p2cursor_source_summary`
- `ai_os_algo_import_summary`
- `ai_os_component_inventory`
- `ai_os_source_requirements`
- `ai_os_recent_trading_signals`
- `ai_os_fincept_component_review`
- `ai_os_fincept_install_status`

Client 3081282 import tools:

- `ai_os_client_3081282_summary`
- `ai_os_client_3081282_symbol_dates`
- `ai_os_client_3081282_trade_timeline`

## Browser MCP Model

Browser control and browser memory are separated.

Browser control:

- Use host browser/Playwright MCP to open pages, inspect pages, click, capture screenshots, and extract text.

AI OS memory:

- Use `ai_os_start_browser_run` before the browser session.
- Use `ai_os_record_raw_artifact` for captured source text or screenshots.
- Use `ai_os_complete_browser_run` when the browser task is done.
- Use `ai_os_create_research_idea`, `ai_os_create_task`, or `ai_os_write_obsidian_note` for follow-up output.

This keeps browser activity auditable without giving the AI OS MCP server unrestricted browser control.

## Verification

Syntax:

```bash
python3 -m py_compile _ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Read/control smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_tools.py
```

Result:

```text
tool_count: 47
control_plane_metrics: 19
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

Manual portfolio smoke:

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

Full read/write/browser smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_write_browser_tools.py
```

Result:

```text
tool_count: 47
capability_mcp_tools: 47
capability_internal_tools: 10
approval_status: approved
browser_run_status: done
task_status: done
inbox_status: done
audit_rows: 13
temporary task/approval/idea/artifact/browser/note rows cleaned up
```

Connector/trade/research smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_connectors_trade_research_tools.py
```

Result:

```text
tool_count: 47
capability_mcp_tools: 47
shortlist_rows: 2
tradingview_task_status: done
trade_rows: 2
research_summary_rows: 23
data_check_rows: 4
temporary TradingView/trade/audit/inbox rows cleaned up
```

Public data-source check:

```bash
python3 _ai_os_runtime/scripts/check_public_data_sources.py
```

Result:

```text
checks: 4
ok: 4
SEC submissions: HTTP 200, 1000 recent rows
SEC company facts: HTTP 200, 505 concept groups
NSE corporate announcements page: HTTP 200
BSE corporate announcements page: HTTP 200
```

Research hub refresh:

```bash
python3 _ai_os_runtime/scripts/inventory_ai_research_outputs.py
```

Result:

```text
records_seen: 91
records_upserted: 91
dashboard: 25
research_report: 36
financial_model: 11
data_pack: 6
```

Service checks:

```text
Postgres: accepting connections
Redis: PONG
Qdrant: all shards are ready
```

## How Agents Should Use This

Charlie Munger:

- Decide what work matters.
- Create tasks and approvals through MCP.
- Challenge weak assumptions before portfolio or strategy action.

Jarvis:

- Route commands.
- Call MCP tools.
- Write approved notes.
- Keep audit trail.

Specialist agents:

- Use read tools for evidence.
- Use write tools only in their owned lane.
- Log browser research through browser run tools.
- Never bypass approvals for client-facing outputs or live trading actions.

## Remaining Work

Next practical build:

1. Connect AI Office UI to these MCP/warehouse tools through a local API adapter.
2. Add NSE/BSE filings collectors using browser MCP plus `ops.browser_runs`.
3. Add TradingView MCP adapter and chart/signal capture.
4. Add broker read-only holdings connector after credentials are stored safely.
5. Keep execution disabled until paper mode, risk checks, and approvals are implemented.

Related notes:

- [[MCP Server and Agent Runner]]
- [[Control Plane and Manual Portfolio Workflow]]
- [[Data and Tool Architecture]]
- [[Full Portfolio Intelligence OS Product Plan]]
