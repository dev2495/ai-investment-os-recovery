# 2026-07-06 Live AI Office v1

## Outcome

Live AI Office v1 is now backed by real warehouse state instead of only the static org chart.

The AI Office dashboard now shows department rooms, room state, per-agent desks, current work, mailbox pressure, task pressure, worker output, and risk pressure from Postgres read models. The same state is exposed through read-only MCP tools for Charlie/Jarvis.

## Implemented

- Added migration: `_ai_os_runtime/postgres/init/078_live_ai_office_v1.sql`
- Added read model: `agent.v_live_office_agent_activity`
- Added read model: `agent.v_live_office_rooms`
- Added MCP registry rows:
  - `ai_os_live_office_rooms`
  - `ai_os_live_office_agent_activity`
- Added API snapshot keys:
  - `live_office_rooms`
  - `live_office_agent_activity`
- Added MCP handlers and tool schemas in `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Added frontend snapshot types in `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- Rebuilt the dashboard office panel in `_ai_os_runtime/ai-office-ui/src/App.tsx`
- Added room-grid, desk, hover-card, activity-feed, and responsive CSS in `_ai_os_runtime/ai-office-ui/src/styles.css`

## Data Contract

`agent.v_live_office_agent_activity` derives each employee state from:

- `agent.v_agent_org_chart`
- `agent.v_agent_mailboxes`
- `agent.tasks`
- `agent.inbox_items`
- `agent.agent_messages`
- `agent.worker_runs`
- `risk.events`

`agent.v_live_office_rooms` groups agents by department room and aggregates:

- agent count
- active agent count
- open task count
- blocked task count
- unread message count
- open inbox count
- open risk event count
- room workload score
- latest activity timestamp
- room state
- desk-level agent JSON

No seed or fake production rows were added.

## Verified Evidence

Migration:

- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/078_live_ai_office_v1.sql`
- Result: `CREATE VIEW`, `CREATE VIEW`, `INSERT 0 2`

Database smoke:

- `agent.v_live_office_rooms`
- Result: `10` rooms, `20` agents, `13` open tasks, `9` unread messages

API snapshot:

- `issues`: `[]`
- `live_office_rooms`: `10`
- `live_office_agent_activity`: `20`
- `risk_events`: `5`
- room states: `available`, `critical_risk`, `needs_attention`, `queued`
- critical risk room: `Risk and Compliance`
- top workload agents: `Risk Agent`, `Data Steward`, `Research Analyst`, `Charlie Munger`, `Portfolio Manager`

MCP JSON-RPC smoke:

- `ai_os_live_office_rooms`: listed and returned `10` room rows
- `ai_os_live_office_agent_activity`: listed and returned the Risk Agent row when filtered by `department_key = risk`

Build checks:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `npm run build` in `_ai_os_runtime/ai-office-ui`
- Vite output:
  - `/assets/index-7i_OgVso.js`
  - `/assets/index-DN-p14j7.css`

Served UI check:

- `curl -s http://127.0.0.1:5177/`
- HTML references the new JS and CSS bundle.

## Remaining Gaps

- Final graphic/3D animated office scene is still open.
- Task arrows between agents are still open.
- Full click-through agent profile pages are still open.
- Committee room view is still open.
- Approval board view is still open.
- Agent reliability/productivity metrics are still open.

## Checklist Updates

- Marked `Agent hover cards` done.
- Marked `Build Live AI Office v1 backed by real agent/task/message state` done.
- Marked `Live AI Office animated room` partial, because v1 is a live room-grid operating view with animated status dots, not the final graphic/3D office scene.
