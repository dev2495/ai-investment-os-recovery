# AI OS MCP Server

Local stdio MCP server over the AI OS warehouse.

Run:

```bash
_ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Client config example:

```text
_ai_os_runtime/mcp_server/mcp_config.example.json
```

Current verified surface (2026-07-15):

- 172 callable `ai_os_*` MCP tools returned by the live `tools/list` protocol.
- 229 enabled internal and external capabilities in `agent.tool_registry`; registry entries are not all directly importable MCP calls.
- DB access uses `docker exec` first and falls back to the published local Postgres port.

Tool groups:

- Capability/audit: `ai_os_mcp_capabilities`, `ai_os_mcp_audit_log`
- External MCP candidates: `ai_os_mcp_candidate_shortlist`
- Control plane and agents: `ai_os_control_plane_snapshot`, `ai_os_orchestration_stack`, `ai_os_list_active_agents`
- Tasks/inbox/approvals: `ai_os_list_open_tasks`, `ai_os_create_task`, `ai_os_update_task_status`, `ai_os_list_inbox`, `ai_os_update_inbox_status`, `ai_os_create_approval`, `ai_os_decide_approval`
- Portfolio/manual holdings: `ai_os_upsert_client`, `ai_os_stage_holding_update`, `ai_os_apply_holding_update`, `ai_os_latest_positions`
- Client 3081282 imports: `ai_os_client_3081282_summary`, `ai_os_client_3081282_symbol_dates`, `ai_os_client_3081282_trade_timeline`
- Research/artifacts/Obsidian: `ai_os_research_outputs`, `ai_os_research_output_detail`, `ai_os_refresh_research_hub`, `ai_os_research_hub_summary`, `ai_os_create_research_idea`, `ai_os_record_raw_artifact`, `ai_os_search_obsidian_notes`, `ai_os_write_obsidian_note`, `ai_os_reindex_obsidian`
- Browser run logging: `ai_os_start_browser_run`, `ai_os_complete_browser_run`, `ai_os_browser_runs`
- TradingView tasks and trade ledger: `ai_os_create_tradingview_task`, `ai_os_update_tradingview_task`, `ai_os_tradingview_tasks`, `ai_os_record_manual_trade`, `ai_os_record_paper_trade`, `ai_os_trade_activity`
- Governed committees: `ai_os_committee_room`, `ai_os_open_committee_packet`, `ai_os_submit_committee_position`, `ai_os_add_committee_discussion`, `ai_os_synthesize_committee_session`, `ai_os_record_committee_human_decision`, `ai_os_create_committee_followup`, `ai_os_capital_committee_decision`
- Public source checks: `ai_os_run_public_data_source_check`, `ai_os_data_source_checks`
- Source/component reads: `ai_os_p2cursor_source_summary`, `ai_os_algo_import_summary`, `ai_os_component_inventory`, `ai_os_source_requirements`
- Trading/Fincept reads: `ai_os_recent_trading_signals`, `ai_os_fincept_component_review`, `ai_os_fincept_install_status`

Stack naming:

- `Charlie Munger` is the main orchestrator.
- `Jarvis` is the runtime/tool layer.
- Specialist agents own research, portfolio, quant, risk, trading, data, and documentation tasks.

The server reads from safe warehouse views. Write tools are limited to local warehouse and structured vault operations:

- `ai_os_upsert_client` creates or updates `portfolio.clients` and optional `portfolio.accounts`.
- `ai_os_stage_holding_update` writes to `portfolio.manual_holding_updates`.
- `ai_os_apply_holding_update` applies one staged update into `portfolio.positions`.
- `ai_os_create_task`, `ai_os_update_task_status`, `ai_os_update_inbox_status`, `ai_os_create_approval`, and `ai_os_decide_approval` write only to `agent.*`.
- `ai_os_create_research_idea` writes to `research.ideas`.
- `ai_os_record_raw_artifact` writes to `core.raw_artifacts`.
- `ai_os_write_obsidian_note` writes markdown only inside structured `ai memory` folders, then reindexes.
- `ai_os_reindex_obsidian` writes note metadata into Postgres `knowledge.*`.
- `ai_os_start_browser_run` and `ai_os_complete_browser_run` log browser requests/captures in `ops.browser_runs`; actual browser control remains with the browser/Playwright MCP client.
- `ai_os_create_tradingview_task` and `ai_os_update_tradingview_task` write auditable chart/screener/browser work requests to `ops.tradingview_tasks`.
- `ai_os_record_manual_trade` and `ai_os_record_paper_trade` write local trade records to `trading.trade_activity_ledger`.
- `ai_os_refresh_research_hub` indexes local Codex/Claude/cowork reports and dashboards into `core.raw_artifacts`.
- `ai_os_run_public_data_source_check` records SEC/NSE/BSE connectivity checks in `core.data_source_checks`.

These write tools do not touch broker accounts and do not place orders. All local write/browser tools write audit rows to `agent.mcp_audit_log`.

Smoke tests:

```bash
_ai_os_runtime/scripts/smoke_mcp_tools.py
_ai_os_runtime/scripts/smoke_manual_portfolio_tools.py
_ai_os_runtime/scripts/smoke_mcp_write_browser_tools.py
_ai_os_runtime/scripts/smoke_mcp_connectors_trade_research_tools.py
```

FinceptTerminal is installed as a local external component under `_ai_os_runtime/external_components/FinceptTerminal`. Use `ai_os_fincept_install_status` for the current app bundle, binary path, build status, and installed component map. Launch/build actions that run Qt build tools should be executed outside the Codex sandbox because Qt needs access to macOS `hw.optional.neon`.

The grouped list above is representative. Treat the live `tools/list` response as the canonical callable surface.

Do not expose broker order placement through MCP until approval gates, paper trading, audit logs, and risk checks are complete.
