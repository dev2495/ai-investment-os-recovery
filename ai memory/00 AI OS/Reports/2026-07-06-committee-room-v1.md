# 2026-07-06 Committee Room v1

## Outcome

Committee Room v1 is live.

The AI Office now has one consolidated committee room across Strategy Committee, Long-Term Committee, and Special Situation reviews. It is backed by real warehouse views and exposes memo status, approval status, decision status, evidence gaps, follow-up counts, and action guard flags.

## Implemented

- Added migration: `_ai_os_runtime/postgres/init/080_committee_room_v1.sql`
- Added read model: `agent.v_committee_room_items`
- Added read model: `agent.v_committee_room_summary`
- Added MCP registry row: `ai_os_committee_room`
- Added API snapshot keys:
  - `committee_room_summary`
  - `committee_room_items`
- Added MCP handler and tool schema in `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Added frontend snapshot fields in `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- Added dashboard panel: `Committee Room`
- Added CSS for committee metrics, rows, guards, and responsive collapse in `_ai_os_runtime/ai-office-ui/src/styles.css`

## Data Contract

`agent.v_committee_room_items` normalizes:

- `strategy.v_strategy_committee_queue`
- `portfolio.v_long_term_committee_queue`
- `research.v_special_situation_memos`

Each row exposes:

- committee lane and scope
- source view and source id
- symbol / exchange / subject
- title
- review status
- decision status
- recommended decision
- final decision
- risk level
- memo status and note path
- approval id/status
- paper monitor, capital action, and live execution flags
- member count
- evidence gap count
- required follow-up count
- room state
- recommended next action
- evidence JSON

No seed or fake production rows were added.

## Verified Evidence

Migration:

- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/080_committee_room_v1.sql`
- Result: `CREATE VIEW`, `CREATE VIEW`, `INSERT 0 1`

Database room state:

- `agent.v_committee_room_items`: `4` rows
- lanes:
  - `Strategy Committee`
  - `Long-Term Committee`
  - `Special Situation Committee`
- room states:
  - `approval_pending`: `2`
  - `decided`: `2`

Committee summary:

- `total`: `4`
- `approval_pending`: `2`
- `decision_pending`: `2`
- `memo_missing`: `0`
- `action_allowed`: `0`

API snapshot:

- `issues`: `[]`
- `committee_room_items`: `4`
- `committee_room_summary`: `5` rows
- `approval_pending`: `2`
- `action_allowed`: `0`

MCP JSON-RPC smoke:

- `ai_os_committee_room`: listed
- returned `4` items and `5` summary rows

Build checks:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `npm run build` in `_ai_os_runtime/ai-office-ui`
- Vite output:
  - `/assets/index-BLtSR3kN.js`
  - `/assets/index-Y84nKKKI.css`

Served UI check:

- `curl -s http://127.0.0.1:5177/`
- HTML references the new JS and CSS bundle.

## Current Live Committee Room

Pending:

- Strategy Committee: `trend_following`
- Special Situation Committee: `ROLEXRINGS Buyback`

Decided:

- Long-Term Committee: `LIQUIDBEES`
- Long-Term Committee: `USHAMART`

Safety:

- capital action allowed: `0`
- live execution allowed: `0`

## Remaining Gaps

- Full Long-Term committee room UI remains open; this slice provides the unified room, not the full deep long-term committee workspace.
- Long-term Monte Carlo UI and committee integration remain open.
- Tactical committee workflow and memo template remain open.
- Domain-specific committee board actions can be improved so the unified room can call the exact strategy/long-term/special-situation decision endpoints.
- Committee room filters/search and click-through detail pages remain open.

## Checklist Updates

- Marked `Committee room view` done.
- Added `Build Committee Room v1` to immediate build evidence.
- Left workflow-specific committee items open where deeper domain UI is still required.
