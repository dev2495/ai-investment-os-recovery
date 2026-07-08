# 2026-07-07 Provider Assignment Gate v1

## Outcome

Built and verified the provider assignment gate that prevents agents from using blocked model endpoints or data-source connectors. This turns the provider readiness board into an enforceable control: before Jarvis, Charlie, Quant, Research, Trading, Portfolio, or News agents assign a provider to work, the system can persist a pass/block decision and create an inbox item when the provider is not ready.

## What Was Added

- Database migration: `_ai_os_runtime/postgres/init/099_provider_assignment_gate_v1.sql`
- Table: `core.provider_assignment_gate_checks`
- Function: `core.evaluate_provider_assignment_gate(jsonb)`
- View: `core.v_provider_assignment_gate_checks`
- API route: `POST /api/providers/assignment-gate/evaluate`
- Snapshot key: `provider_assignment_gates`
- MCP tools:
  - `ai_os_evaluate_provider_assignment_gate`
  - `ai_os_provider_assignment_gates`
- AI Office UI:
  - `System Health` -> `Provider Readiness Board` -> per-provider `Gate` button
  - recent provider assignment gate ledger under the readiness panel

## Gate Rules

The gate reads `core.v_provider_readiness_board`.

| Provider state | Gate result | Agent assignment |
|---|---|---|
| `ready` and assignable | `passed` | allowed |
| `approval_required` | `approval_required` | blocked until approval/cost policy |
| `blocked_secret` | `blocked` | blocked, inbox created |
| `blocked_browser` | `blocked` | blocked, inbox created |
| `blocked_configuration` | `blocked` | blocked, inbox created |
| `needs_activation` | `blocked` | blocked, inbox created |
| missing provider | `blocked` | blocked, inbox created |

## Live Evidence

Current verified gate checks:

| ID | Provider | Status | Allowed | Path | Inbox |
|---:|---|---|---|---|---:|
| 1 | `agent_worker_deterministic_local_python_deterministic_tools` | `passed` | true | direct SQL ready provider smoke | - |
| 2 | `coding_escalation_codex_gpt_5_codex` | `blocked` | false | direct SQL blocked provider smoke | 190 |
| 3 | `tradingview_mcp_connector` | `blocked` | false | API smoke TradingView assignment | 191 |
| 4 | `agent_worker_deterministic_local_python_deterministic_tools` | `passed` | true | MCP ready provider assignment smoke | - |
| 5 | `coding_escalation_codex_gpt_5_codex` | `blocked` | false | AI Office dashboard provider assignment check | 192 |

Aggregate verified counts:

| Assignment status | Allowed | Count |
|---|---|---:|
| `blocked` | false | 3 |
| `passed` | true | 2 |

## API Verification

Command:

```bash
curl -s -X POST http://127.0.0.1:8765/api/providers/assignment-gate/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"provider_key":"tradingview_mcp_connector","provider_kind":"source_connector","requesting_agent":"Trading Desk","requested_use":"API smoke TradingView assignment","source_kind":"api_smoke","source_ref":"provider_assignment_api_blocked_20260707","target_workspace":"system","create_inbox_on_block":true,"actor":"Jarvis"}'
```

Result:

- `assignment_status`: `blocked`
- `assignment_allowed`: `false`
- `block_reasons`: `blocked_browser`
- `inbox_item_id`: `191`
- `next_action`: relaunch TradingView Desktop with `--remote-debugging-port=9222`

## MCP Verification

MCP smoke confirmed:

- `ai_os_evaluate_provider_assignment_gate` is listed.
- `ai_os_provider_assignment_gates` is listed.
- Ready local provider passed through MCP:
  - Provider: `agent_worker_deterministic_local_python_deterministic_tools`
  - Status: `passed`
  - Allowed: `true`
- Recent gate ledger returned 4+ rows.

## UI Verification

Playwright/Chrome smoke confirmed:

- Page: `http://127.0.0.1:5177/`
- Workspace: `System Health`
- Panel: `Provider Readiness Board`
- Per-provider button: `Gate`
- UI POST observed:
  - `POST http://127.0.0.1:8765/api/providers/assignment-gate/evaluate`
  - Response: `201`
- DB row created by UI:
  - ID: `5`
  - Provider: `coding_escalation_codex_gpt_5_codex`
  - Status: `blocked`
  - Inbox: `192`

## Build And Runtime Verification

Passed:

```bash
python3 -m py_compile _ai_os_runtime/scripts/run_provider_readiness_sweep.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
curl -s http://127.0.0.1:8765/api/health
```

Runtime health:

- API: `ok`
- DB: `ok`
- UI: `http://127.0.0.1:5177/`
- TradingView CDP: still unavailable on port `9222`, correctly represented as a provider block

## Guardrails

- No raw secrets are stored.
- Cloud/frontier providers with missing `secret_ref` are blocked.
- TradingView remains blocked until CDP is available.
- Blocked providers create inbox follow-ups instead of silently failing.
- Passed gates do not authorize broker execution or live trading.
- This gate controls provider assignment only; strategy execution, live broker writes, and capital actions still require separate risk/approval gates.

## What This Unlocks

- Jarvis can now evaluate a provider before assigning it to a task.
- Specialist agents can be forced to use ready/local providers unless approval is granted.
- Blocked data sources become visible work items instead of hidden runtime errors.
- The agent office can show which employee tried to use which provider and why it passed or failed.
- Future strategy, news, filing, broker, TradingView, crypto, and model-routing workflows can call this gate as a preflight.

## Remaining Work

- Add automatic provider assignment gate calls inside task creation and agent worker execution paths.
- Add approval-request creation for `approval_required` providers instead of only inbox routing.
- Add scheduled checks that alert when a previously passed provider becomes blocked.
- Relaunch TradingView Desktop with CDP port `9222` and rerun the TradingView provider gate.
- Add provider assignment policies per department so Quant, Trading, Research, Portfolio, News, and Software agents have different allowed provider sets.

