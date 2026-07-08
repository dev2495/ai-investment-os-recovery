# 2026-07-06 Agent Employee Profiles v1

## Outcome

Agent Employee Profiles v1 is live.

The AI Office now has source-backed employee profile cards showing each agent's role, personality, hierarchy, model route, tool permissions, skills, open work, mailbox/message pressure, worker outputs, and approvals.

## Implemented

- Added migration: `_ai_os_runtime/postgres/init/081_agent_employee_profiles_v1.sql`
- Added read model: `agent.v_employee_profiles_v1`
- Added read model: `agent.v_employee_profile_summary`
- Added MCP registry row: `ai_os_employee_profiles`
- Added API snapshot keys:
  - `employee_profile_summary`
  - `employee_profiles`
- Added MCP handler and tool schema in `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Added frontend snapshot fields in `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- Added dashboard panel: `Employee Profiles`
- Added CSS for profile summary, employee cards, model rows, counters, skill tags, tool tags, output paths, and responsive collapse.

## Data Contract

`agent.v_employee_profiles_v1` is backed by:

- `agent.v_active_agents`
- `agent.v_agent_org_chart`
- `agent.v_live_office_agent_activity`
- `agent.v_agent_model_matrix`
- `agent.agent_skill_map`
- `agent.skills`
- `agent.tool_registry`
- `agent.tasks`
- `agent.inbox_items`
- `agent.agent_messages`
- `agent.v_recent_worker_runs`
- `agent.v_approval_board_items`

Each employee row exposes:

- role, department, hierarchy, reporting line
- persona, operating style, mental models, voice style, visual traits
- model route, assigned model, provider, fallback route, escalation route, cost tier
- enabled tool counts by permission type
- assigned/active skill counts and skill JSON
- open task counts and task JSON
- inbox/message counts and recent message JSON
- worker run counts, output artifact count, recent output JSON
- approval counts and approval JSON
- current work and live office state

No seed or fake production rows were added.

## Verified Evidence

Migration:

- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/081_agent_employee_profiles_v1.sql`
- Result: `CREATE VIEW`, `CREATE VIEW`, `INSERT 0 1`

Database summary:

- employee profiles: `32`
- enabled tools: `109`
- active skills: `85`
- open tasks: `28`
- output artifacts: `23`
- pending approvals: `4`
- model routes: `32`

API snapshot:

- `issues`: `[]`
- `employee_profiles`: `32`
- `employee_profile_summary.agents`: `32`
- `employee_profile_summary.enabled_tools`: `109`
- `employee_profile_summary.model_routes`: `32`
- `employee_profile_summary.open_tasks`: `28`
- `employee_profile_summary.output_artifacts`: `23`
- `employee_profile_summary.pending_approvals`: `4`

MCP JSON-RPC smoke:

- `ai_os_employee_profiles`: listed
- filtered call for `Charlie Munger` returned `1` profile and `6` summary rows

Build checks:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `npm run build` in `_ai_os_runtime/ai-office-ui`
- Vite output:
  - `/assets/index-BrJ-FpHB.js`
  - `/assets/index-CYO39e0g.css`

Served UI check:

- `curl -s http://127.0.0.1:5177/`
- HTML references the new JS and CSS bundle.

## Current Live Profile Facts

Top profiles by role order:

- Charlie Munger
- Jarvis
- Portfolio Manager
- Research Analyst
- News Analyst

Charlie Munger profile currently shows:

- model route: `charlie_munger_orchestration`
- enabled tools: `7`
- active skills: `4`
- output artifacts: `1`
- pending approvals: `2`
- live state: `needs_attention`

Jarvis profile currently shows:

- model route: `jarvis_runtime`
- enabled tools: `23`
- active skills: `7`
- output artifacts: `7`
- live state: `needs_attention`

## Remaining Gaps

- Agent comments remain open.
- Full click-through agent profile pages remain open; this slice provides rich dashboard cards and MCP/API read models, not routed detail pages.
- Standalone Agent Output Artifact Registry v2 remains partial; profile cards expose output paths/counts, but not a dedicated artifact browser.
- Per-agent tool/model editing is not implemented; this is read-only visibility.
- Reliability/productivity scoring is still open.

## Checklist Updates

- Marked `Per-agent tool permissions UI` done.
- Marked `Per-agent model route UI` done.
- Marked `Character/personality cards` done.
- Marked `Per-agent model route table complete` done.
- Marked `Agent Office shows real tasks, inbox, runs, messages, model routes, outputs, and approvals` done.
- Kept `Agent output artifacts registry v2` partial.
