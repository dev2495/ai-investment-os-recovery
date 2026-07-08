# MCP Server and Agent Runner

## Current State

MCP server:

```text
_ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Agent runner:

```text
_ai_os_runtime/agents/agent_runner.py
```

Both are local-first and use the Postgres warehouse as their source of truth.

## MCP Tools

Current callable surface:

- 36 callable `ai_os_*` MCP tools.
- 10 internal tool-layer capabilities in `agent.tool_registry`.
- Tool discovery: `ai_os_mcp_capabilities`
- Audit trail: `agent.mcp_audit_log` and `ai_os_mcp_audit_log`

Tool groups:

- Capability/audit: `ai_os_mcp_capabilities`, `ai_os_mcp_audit_log`
- Control/agents: `ai_os_control_plane_snapshot`, `ai_os_orchestration_stack`, `ai_os_list_active_agents`
- Tasks/inbox/approvals: `ai_os_list_open_tasks`, `ai_os_create_task`, `ai_os_update_task_status`, `ai_os_list_inbox`, `ai_os_update_inbox_status`, `ai_os_create_approval`, `ai_os_decide_approval`
- Portfolio/manual holdings: `ai_os_upsert_client`, `ai_os_stage_holding_update`, `ai_os_apply_holding_update`, `ai_os_latest_positions`
- Client import reads: `ai_os_client_3081282_summary`, `ai_os_client_3081282_symbol_dates`, `ai_os_client_3081282_trade_timeline`
- Research/artifacts/Obsidian: `ai_os_research_outputs`, `ai_os_research_output_detail`, `ai_os_create_research_idea`, `ai_os_record_raw_artifact`, `ai_os_search_obsidian_notes`, `ai_os_write_obsidian_note`, `ai_os_reindex_obsidian`
- Browser run logging: `ai_os_start_browser_run`, `ai_os_complete_browser_run`, `ai_os_browser_runs`
- Source/component reads: `ai_os_p2cursor_source_summary`, `ai_os_algo_import_summary`, `ai_os_component_inventory`, `ai_os_source_requirements`
- Trading/Fincept reads: `ai_os_recent_trading_signals`, `ai_os_fincept_component_review`, `ai_os_fincept_install_status`

Guardrail:

- No broker order placement tools.
- No external posting tools.
- Write behavior is limited to local warehouse operations and structured Obsidian write-back.
- Manual portfolio writes do not touch broker accounts and do not place orders.
- Browser MCP behavior is logged through `ops.browser_runs`; actual browser control remains with the host browser/Playwright MCP client.
- All local write/browser tools write audit rows to `agent.mcp_audit_log`.
- Fincept install status is read-only and reports the local external component build, paths, and installed component map.

## Agent Runner

Current supported command:

```bash
_ai_os_runtime/agents/agent_runner.py --agent 'Charlie Munger'
```

The runner:

- reads safe warehouse views,
- writes a structured note to `ai memory/00 AI OS/Agent Outputs`,
- logs the run in `agent.run_log`,
- can be extended to call local/cloud model routes.

Verified output:

```text
ai memory/00 AI OS/Agent Outputs/20260701T181301Z-charlie-munger-tick.md
```

Stack naming:

- `Charlie Munger`: main orchestrator.
- `Jarvis`: runtime/tool layer.
- Specialist agents: role-scoped execution and evidence.

Smoke test:

```bash
_ai_os_runtime/scripts/smoke_mcp_tools.py
_ai_os_runtime/scripts/smoke_manual_portfolio_tools.py
_ai_os_runtime/scripts/smoke_mcp_write_browser_tools.py
```

Latest verification:

- MCP tools listed: `36`
- Callable MCP tools in registry: `36`
- Internal tool-layer capabilities: `10`
- Control-plane metrics: `13`
- Control-plane modules: `11`
- Control-plane data sources: `10`
- Control-plane strategies: `6`
- Control-plane workflows: `7`
- Orchestration stack rows: `15`
- Client summary metrics: `7`
- Client open symbol sample rows: `3`
- Research search sample rows: `3`
- Fincept components: `9`
- Fincept install rows: `1`
- Fincept installed components: `6`
- Manual portfolio write smoke: upserted temporary client/account, staged one holding update, applied it into `portfolio.positions`, and cleaned up the temporary rows.
- Full read/write/browser smoke: created task, approval, research idea, raw artifact, browser run, Obsidian note, inbox update, task completion, audit rows, then cleaned all smoke rows/files.

Docker recovery note:

- During this build Docker Desktop had inconsistent container metadata and `input/output error` on container image/blob files.
- `docker desktop restart` fixed the daemon state without resetting volumes.
- Postgres, Redis, and Qdrant were restarted and validated after the Docker restart.

## Next Steps

- Create a local model adapter for Ollama, LM Studio, and MLX.
- Let Charlie Munger choose the route from `agent.model_routes` and use Jarvis runtime to execute it.
- Connect the AI Office UI to the warehouse through a small local API adapter.
- Add real NSE/BSE/browser collectors that use browser MCP plus `ops.browser_runs`.
- Keep live trading write tools disabled until paper mode, risk checks, and approval audit are complete.
