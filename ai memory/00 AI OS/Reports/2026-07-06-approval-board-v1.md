# 2026-07-06 Approval Board v1

## Outcome

Approval Board v1 is live.

The system now has one consolidated decision board across the existing approval surfaces instead of only scattered per-module approval rows.

## Implemented

- Added migration: `_ai_os_runtime/postgres/init/079_approval_board_v1.sql`
- Added read model: `agent.v_approval_board_items`
- Added read model: `agent.v_approval_board_summary`
- Added MCP registry row: `ai_os_approval_board`
- Added API snapshot keys:
  - `approval_board_summary`
  - `approval_board_items`
- Added MCP handler and tool schema in `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Added frontend snapshot types in `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- Replaced the narrow dashboard approval queue with a unified `Approval Board` panel in `_ai_os_runtime/ai-office-ui/src/App.tsx`
- Added board metric, row, guard, and responsive styling in `_ai_os_runtime/ai-office-ui/src/styles.css`

## Data Contract

`agent.v_approval_board_items` starts from `agent.approvals` and classifies linked approvals using:

- `strategy.v_strategy_committee_queue`
- `portfolio.v_long_term_committee_queue`
- `trading.v_limited_live_requests`
- `trading.v_order_intents`
- `ops.v_tradingview_alert_requests`
- `research.v_special_situation_memos`
- `risk.events`
- `trading.v_execution_gate_checks`
- `agent.tasks`

The board exposes:

- approval id/type/status/risk
- board lane
- owner
- linked source/view
- linked record id
- symbol/strategy/client/book context
- gate status
- live execution allowed flag
- broker order allowed flag
- open risk event count
- gate check count
- blocked gate count
- recommended next action
- evidence JSON

No seed or fake production rows were added.

## Verified Evidence

Migration:

- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/079_approval_board_v1.sql`
- Result: `CREATE VIEW`, `CREATE VIEW`, `INSERT 0 1`

Database board count:

- `agent.v_approval_board_items`: `8` rows
- lanes:
  - `TradingView`
  - `Special Situation`
  - `Strategy Committee`
  - `Long-Term Committee`
- pending high-risk approvals: `4`
- live execution allowed: `0`
- broker order allowed: `0`

API snapshot:

- `issues`: `[]`
- `approval_board_items`: `8`
- `approval_board_summary.total`: `8`
- `approval_board_summary.pending`: `4`
- `approval_board_summary.high_or_critical_pending`: `4`
- `approval_board_summary.live_execution_allowed`: `0`
- `approval_board_summary.broker_order_allowed`: `0`

MCP JSON-RPC smoke:

- `ai_os_approval_board`: listed
- pending board call returned `4` pending items
- summary returned `5` rows

Build checks:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `npm run build` in `_ai_os_runtime/ai-office-ui`
- Vite output:
  - `/assets/index-DZp_YhjI.js`
  - `/assets/index-DNt2Nj8U.css`

Served UI check:

- `curl -s http://127.0.0.1:5177/`
- HTML references the new JS and CSS bundle.

## Current Live Board State

Pending high-risk items:

- TradingView alert/template approval: `2`
- Special Situation approval: `1`
- Strategy Committee approval: `1`

Closed/decided items:

- TradingView approved: `2`
- Long-Term Committee rejected: `2`

## Remaining Gaps

- Domain-specific committee decision sync still needs a dedicated board action layer. Generic approval resolution exists, but strategy/long-term/special-situation decisions should ideally route through their specialized decision endpoints.
- Full approval audit UX is still open.
- Human-before-broker-order remains open until an order-intent approval board action is tested against a live order-intent row.
- Cloud model approval workflow remains open.
- Approval board filters/search are not yet implemented.

## Checklist Updates

- Marked `Approval board view` done.
- Added `Build Approval Board v1` to immediate build evidence.
- Kept broader `Agent approvals foundation` partial because specialized decision sync and audit UX still need hardening.
