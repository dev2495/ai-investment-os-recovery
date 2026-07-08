# Position Readiness Remediation Queue v1

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Owner: Portfolio Office
Runtime operator: Jarvis
Status: live and verified

## Outcome

Position-object readiness gaps are now actionable work, not only dashboard warnings.

The system can:

- read v9 position-object thesis/exit gaps,
- create a remediation queue,
- route each gap to the owning agent,
- create agent tasks,
- create inbox items,
- expose the queue in the API snapshot,
- expose a dashboard action to sync the queue,
- expose MCP tools so agents can sync/read remediation work.

This closes the foundation gap between "positions have missing thesis/exit criteria" and "agents have concrete tasks to fix those gaps."

## Runtime Objects

Migration:

- `_ai_os_runtime/postgres/init/104_position_readiness_remediation_queue.sql`

Warehouse objects:

- `books.position_object_remediation_queue`
- `books.v_position_object_remediation_queue`
- `books.v_position_object_remediation_summary`
- `books.sync_position_object_remediation_queue(limit, create_tasks, actor)`

API:

- `GET /api/snapshot`
- `POST /api/portfolio/position-readiness/remediate`

Snapshot keys:

- `position_remediation_summary`
- `position_remediation_queue`

MCP tools:

- `ai_os_sync_position_remediation_queue`
- `ai_os_position_remediation_queue`
- `ai_os_position_remediation_summary`

AI Office UI:

- `Position Object v9 Readiness`
- `Sync remediation queue` dashboard action
- remediation summary list
- remediation queue rows with symbol, gap type, recommended action, owner agent, task id, inbox id, status, and severity

## Live Data Evidence

Current remediation summary:

| Metric | Value |
| --- | ---: |
| critical_remediation_items | 142 |
| open_remediation_items | 142 |
| remediation_symbols | 45 |
| remediation_tasks | 142 |

Queue state:

| Status | Count |
| --- | ---: |
| task_created | 142 |

API sync result:

```json
{
  "actor": "Portfolio Manager smoke",
  "inbox_items_created": 0,
  "open_queue_count": 142,
  "status": "ok",
  "synced_count": 142,
  "tasks_created": 0
}
```

The `tasks_created = 0` and `inbox_items_created = 0` result is expected on repeated sync because the 142 current gaps already have tasks and inbox items.

Example queue item:

- Remediation key: `position-gap:58:exit_criteria_not_active`
- Client: `Tushit`
- Symbol: `LIQUIDBEES`
- Book: `Long-Term Investing`
- Gap: `exit_criteria_not_active`
- Owner: `Long-Term Portfolio Manager`
- Skill: `long_term_portfolio_fit_review`
- Status: `task_created`
- Task id: `115`
- Inbox id: `199`
- Recommended action: review and activate explicit exit criteria before approving action.

## Verification

Python compile:

```bash
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Result: passed.

Frontend build:

```bash
npm --prefix _ai_os_runtime/ai-office-ui run build
```

Result: passed. Built bundle includes `Sync remediation queue`.

Live stack restart:

```bash
bash ./_ai_os_runtime/scripts/start_ai_office_live.sh
```

Result: API and UI LaunchAgents started.

API health:

```bash
curl -s http://127.0.0.1:8765/api/health
```

Result:

- `ok = true`
- DB status `ok`
- runtime root on external SSD
- TradingView CDP still unavailable on port `9222`, which is unrelated to this workflow and remains a known TradingView launch prerequisite.

API snapshot:

```bash
curl -s http://127.0.0.1:8765/api/snapshot
```

Result:

- `position_remediation_summary` present,
- `position_remediation_queue` present,
- summary rows: `4`,
- queue rows returned to dashboard: `100`,
- snapshot issues: none.

Database checks:

```sql
SELECT metric || '=' || value
FROM books.v_position_object_remediation_summary
ORDER BY metric;
```

Result:

- `critical_remediation_items=142`
- `open_remediation_items=142`
- `remediation_symbols=45`
- `remediation_tasks=142`

```sql
SELECT status, count(*)
FROM books.position_object_remediation_queue
GROUP BY status
ORDER BY status;
```

Result:

- `task_created | 142`

MCP smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_tools.py
```

Result:

- `tool_count = 120`
- control-plane, orchestration, client, research, and Fincept smoke checks passed.

Direct MCP calls:

- `tools/list` includes all three remediation MCP tools.
- `ai_os_position_remediation_summary` returns the 142-item summary.
- `ai_os_position_remediation_queue` returns queue rows with task and inbox ids.
- `ai_os_sync_position_remediation_queue` returns `status = ok`, `synced_count = 142`, `open_queue_count = 142`, and no duplicate tasks on repeated sync.

## Remaining Work

The remediation queue is live, but the work items are still open. Next required implementation:

- build one-click execution for a remediation task,
- generate or refresh long-term thesis notes from source-backed packets,
- activate explicit exit criteria for Long-Term positions,
- update readiness scores after remediation,
- add resolution/ignore workflow with audit reason,
- surface these tasks on agent profile pages and Long-Term Office v2,
- move readiness from `not_decision_ready` toward `decision_ready` only after actual thesis and exit criteria are present.
