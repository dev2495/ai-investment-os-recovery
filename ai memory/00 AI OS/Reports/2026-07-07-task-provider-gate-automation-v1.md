# 2026-07-07 Task Provider Gate Automation v1

## Outcome

Added automatic provider-gate enforcement for agent tasks and worker execution.

Previously, the system could manually check whether a provider was ready. Now the OS automatically checks provider readiness when a task is created and again immediately before worker execution. This prevents agents from quietly using blocked models, missing-secret cloud routes, inactive data connectors, or browser-dependent connectors such as TradingView while CDP is offline.

## What Was Added

- Migration: `_ai_os_runtime/postgres/init/100_task_provider_gate_automation_v1.sql`
- Updated provider gate key generation in `_ai_os_runtime/postgres/init/099_provider_assignment_gate_v1.sql`
- Function: `core.evaluate_task_provider_assignment_gates(task_id, actor, context)`
- Trigger: `agent.trg_auto_gate_task_providers_after_insert`
- Trigger function: `agent.auto_gate_task_providers_after_insert`
- View: `agent.v_task_provider_gate_status`
- API route: `POST /api/tasks/provider-gates/evaluate`
- Snapshot key: `task_provider_gate_status`
- MCP tools:
  - `ai_os_evaluate_task_provider_gates`
  - `ai_os_task_provider_gate_status`
- Worker preflight:
  - `_ai_os_runtime/scripts/run_agent_worker_once.py`
  - atomic task claim before execution
  - provider gate evaluation before output note creation
- AI Office UI:
  - task provider gate ledger under `System Health` -> `Provider Readiness Board`

## Gate Sources

Each task is checked against:

- The owner agent's default model route from `agent.profiles.default_model_route`
- The matching model endpoint in `core.v_provider_readiness_board`
- Any explicit `provider_key` entries in `agent.tasks.evidence`

This means a task can be blocked by:

- Missing default model route
- Missing model endpoint for an agent route
- Cloud/frontier model without secret reference
- Explicit source connector that is blocked, inactive, or browser-unavailable
- Explicit data source provider that needs activation

## Worker Claim Fix

During worker verification, a real concurrency weakness appeared: the daemon and a manual worker could race on the same queued task. I added an atomic task claim in `run_agent_worker_once.py`.

The worker now updates a task from `queued` to `in_progress` before provider preflight. If another worker already claimed it, the second worker skips it instead of creating a duplicate output.

The claim SQL uses a top-level writable CTE because PostgreSQL requires data-modifying CTEs to be attached to the top-level statement. Reference: PostgreSQL docs, `Data-Modifying Statements in WITH`.

## Live Verification

### Trigger: Ready Task

Task:

- ID: `111`
- Title: `Provider gate auto ready smoke 20260707`
- Owner: `Jarvis`

Result:

- Task status: `queued`
- Provider gate status: `passed`
- Gate count: `1`
- Provider: `jarvis_runtime_ollama_llama3_2_3b`
- Assignment allowed: `true`

### Trigger: Blocked TradingView Task

Task:

- ID: `112`
- Title: `Provider gate auto blocked TradingView smoke fixed 20260707`
- Owner: `Trading Desk Agent`
- Explicit provider: `tradingview_mcp_connector`

Result:

- Task status: `blocked`
- Provider gate status: `blocked`
- Gate count: `2`
- Passed gates: `1`
- Blocked gates: `1`
- Default model route passed: `daily_brief_ollama_llama3_2_3b`
- TradingView source connector blocked: `tradingview_mcp_connector`
- Inbox created: `195`
- Reason: TradingView CDP unavailable on port `9222`

### API Task Gate

Command:

```bash
curl -s -X POST http://127.0.0.1:8765/api/tasks/provider-gates/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"task_id":112,"actor":"Jarvis","context":"api_smoke"}'
```

Result:

- Overall status: `blocked`
- Gate IDs: `12`, `13`
- Default model route passed
- TradingView provider blocked
- Inbox created: `196`

### MCP Task Gate

MCP verification confirmed:

- `ai_os_evaluate_task_provider_gates` listed and callable
- `ai_os_task_provider_gate_status` listed and callable
- Task `111` recheck returned:
  - Overall status: `passed`
  - Gate ID: `14`

### Worker Preflight

Task:

- ID: `114`
- Title: `Provider gate worker claim smoke 20260707`

Result:

- Task status after worker: `needs_review`
- Worker run count: `1`
- Worker run ID: `26`
- Output note: `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-07 task-114 jarvis route-user-request.md`
- Provider gate status: `passed`
- Two parallel manual worker attempts found no claimable duplicate after daemon/claim handling.

### UI Smoke

Playwright/Chrome confirmed:

- `System Health` renders `Provider Readiness Board`
- Task gate ledger shows:
  - `Provider gate auto blocked TradingView smoke fixed 20260707`
  - `Provider gate worker claim smoke 20260707`
  - visible `blocked 1`
  - visible `passed 1`

## Build And Runtime Checks

Passed:

```bash
python3 -m py_compile _ai_os_runtime/scripts/run_agent_worker_once.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
curl -s http://127.0.0.1:8765/api/health
```

Runtime health:

- API: `ok`
- DB: `ok`
- UI: `http://127.0.0.1:5177/`
- TradingView CDP: unavailable, correctly blocks TradingView task/provider use

## Current Task Gate Summary

Latest task gate status counts:

| Status | Count |
|---|---:|
| blocked | 2 |
| passed | 3 |
| not_checked | 70 |

`not_checked` mostly represents older historical tasks created before this enforcement layer. New tasks are checked automatically.

## Guardrails

- A passed provider gate does not authorize broker execution.
- A blocked data source creates an inbox item instead of allowing silent failure.
- Cloud/frontier routes without secret references remain blocked.
- TradingView-dependent work remains blocked until CDP is available.
- Worker execution now claims tasks atomically before running.

## Remaining Work

- Backfill task provider gates for all older `not_checked` tasks.
- Add approval creation for `approval_required` task gates.
- Add department-level provider policy, for example Quant can use local backtest tools, Research can use filing/news connectors, Trading can use TradingView only after CDP is ready.
- Add dashboard filters for blocked task gates.
- Add alerts when a previously passed task/provider becomes blocked before execution.

