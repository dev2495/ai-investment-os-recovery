# Symbol Intelligence Action Router v1

Date: 2026-07-07

## What Was Added

Symbol Intelligence v2 is now actionable. From a symbol row, Charlie/Jarvis can route the symbol into the correct agent workspace instead of only reading the dashboard.

Implemented action types:

- `refresh_thesis` - Long-Term Portfolio Manager
- `review_exit_criteria` - Long-Term Portfolio Manager
- `route_risk_review` - Chief Risk Officer
- `route_research_update` - Research Director
- `route_quant_review` - Strategy Research Agent
- `route_trading_review` - Trading Desk Agent
- `request_committee_review` - Strategy Committee Secretary
- `prepare_tradingview` - Trading Desk Agent

## Warehouse Objects

Migration:

- `_ai_os_runtime/postgres/init/106_symbol_intelligence_actions_v1.sql`

Objects:

- `portfolio.symbol_intelligence_actions`
- `portfolio.route_symbol_intelligence_action(...)`
- `portfolio.v_symbol_intelligence_actions`
- `portfolio.v_symbol_intelligence_action_summary`

The router creates one idempotent daily action per client, exchange, symbol, and action type. It also creates the matching `agent.tasks` row and `agent.inbox` item so the action becomes real work for the agent office.

## API

New route:

- `POST /api/symbol-intelligence/actions`

New snapshot keys:

- `symbol_intelligence_action_summary`
- `symbol_intelligence_actions`

## MCP Tools

New MCP tools:

- `ai_os_route_symbol_intelligence_action`
- `ai_os_symbol_intelligence_actions`

These allow Charlie, Jarvis, and future specialist agents to route/review Symbol Intelligence actions from the MCP layer without touching the UI.

## AI Office UI

The `Symbol Intelligence v2` panel now includes action buttons:

- Thesis
- Exit
- Risk
- Research
- Quant
- Trade
- TV Prep

Existing TradingView Chart/Snapshot buttons remain in place. They still require the TradingView desktop CDP connection on port `9222`.

## Live Verification

Compile/build:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py` passed.
- `npm --prefix _ai_os_runtime/ai-office-ui run build` passed.
- `python3 _ai_os_runtime/scripts/smoke_mcp_tools.py` passed with `tool_count: 124`.

Health:

- `GET /api/health` returned `ok: true`.
- Runtime root is on the external SSD: `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`.
- TradingView CDP is still unavailable on port `9222`; the health endpoint reports the relaunch action required.

Snapshot:

- `GET /api/snapshot` returned zero issues.
- `symbol_intelligence_action_summary`:
  - `total_actions`: 3
  - `distinct_symbols`: 2
  - `critical_actions`: 1
  - `open_tasks`: 3

SQL smoke:

- Routed `USHAMART` for Naval into `route_risk_review`.
- Created action id `1`, task id `257`, inbox id `342`.
- The task status is `blocked`, which is expected because the existing risk/provider gate blocks risk-critical work until review is cleared.

API smoke:

- Routed `LIQUIDBEES` for Tushit into `refresh_thesis`.
- Created action id `2`, task id `258`, inbox id `343`.

MCP smoke:

- Verified tool registration for:
  - `ai_os_route_symbol_intelligence_action`
  - `ai_os_symbol_intelligence_actions`
- Routed `LIQUIDBEES` for Tushit into `review_exit_criteria`.
- Returned existing idempotent action id `3`, task id `259`, inbox id `344`.

Current live action rows:

| ID | Action | Client | Symbol | Owner | Priority | Task | Inbox |
|---:|---|---|---|---|---|---|---|
| 3 | review_exit_criteria | 3081832 | LIQUIDBEES | Long-Term Portfolio Manager | high | queued | queued |
| 2 | refresh_thesis | 3081832 | LIQUIDBEES | Long-Term Portfolio Manager | high | queued | queued |
| 1 | route_risk_review | naval | USHAMART | Chief Risk Officer | critical | blocked | queued |

## Remaining Gaps

- The router creates agent work, but the downstream specialist task executors still need to run the actual thesis/risk/quant/trading reviews.
- TradingView chart execution remains blocked until TradingView is relaunched with CDP remote debugging on port `9222`.
- Rich symbol drilldown pages are still separate future UI work; the current implementation wires the action buttons and decision packet.

