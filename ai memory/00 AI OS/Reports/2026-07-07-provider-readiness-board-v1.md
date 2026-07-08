# 2026-07-07 Provider Readiness Board v1

## Outcome

Built and verified a provider readiness board that tells Charlie, Jarvis, and specialist agents which model endpoints and data-source connectors are actually usable, which ones need approval, and which ones are blocked by missing secrets, inactive connectors, or browser/CDP state.

This is the control layer needed before agents start freely selecting models, market data sources, TradingView, broker connectors, crypto gateways, news feeds, or filing collectors.

## What Was Added

- Database migration: `_ai_os_runtime/postgres/init/098_provider_readiness_board_v1.sql`
- Sweep script: `_ai_os_runtime/scripts/run_provider_readiness_sweep.py`
- API route: `POST /api/providers/readiness/run`
- Snapshot keys:
  - `provider_readiness_board`
  - `provider_readiness_summary`
  - `provider_readiness_runs`
- MCP tools:
  - `ai_os_run_provider_readiness_sweep`
  - `ai_os_provider_readiness_board`
- AI Office UI panel:
  - `System Health` -> `Provider Readiness Board`

## Database Objects

- `core.provider_readiness_runs`
- `core.v_provider_readiness_board`
- `core.v_provider_readiness_summary`
- `core.v_provider_readiness_runs`
- `agent.tool_registry` rows for the two provider readiness MCP tools

The board combines:

- `agent.v_model_endpoint_control`
- `core.v_source_connector_control`

## Current Live Readiness State

Latest verified counts:

| Status | Count |
|---|---:|
| ready | 23 |
| approval_required | 6 |
| blocked_secret | 4 |
| blocked_browser | 2 |
| needs_activation | 4 |
| needs_check | 0 |
| total providers | 39 |

## Important Blockers Detected

The board correctly flags the following as not freely assignable:

- Cloud/frontier model endpoints that need `secret_ref` before use.
- Zerodha and Dhan live connectors that need credential references.
- TradingView MCP bridge, blocked until TradingView Desktop is relaunched with `--remote-debugging-port=9222`.
- X curated watchlist connector, blocked until a browser session check is recorded.
- Binance, CCXT, Dhan MCX commodity gateway, and global news basket connectors, which still need activation/configuration.

## Verification Evidence

### Direct Script

Command:

```bash
python3 _ai_os_runtime/scripts/run_provider_readiness_sweep.py --run-key provider_readiness_script_smoke_20260707 --actor Jarvis --model-limit 80 --source-limit 120
```

Result:

- Status: `completed`
- Model checks: `21`
- Source checks: `18`
- Ready providers: `23`
- Blocked providers: `6`

### API

Command:

```bash
curl -s -X POST http://127.0.0.1:8765/api/providers/readiness/run \
  -H 'Content-Type: application/json' \
  -d '{"run_key":"provider_readiness_api_smoke_20260707","actor":"Jarvis","model_limit":80,"source_limit":120}'
```

Result:

- Status: `completed`
- Duration: `3912ms`
- Model checks: `21`
- Source checks: `18`
- Ready providers: `23`
- Blocked providers: `6`

### Snapshot

Bounded snapshot check confirmed:

- `provider_readiness_summary`: 5 rows
- `provider_readiness_board`: 39 rows
- `provider_readiness_runs`: 2+ rows

### MCP

MCP verification confirmed:

- `ai_os_provider_readiness_board` is listed and returns summary, board, and run rows.
- `ai_os_run_provider_readiness_sweep` is listed and completed a bounded smoke run.
- Latest bounded MCP sweep:
  - Run key: `provider_readiness_mcp_smoke_20260707b`
  - Status: `completed`
  - Model checks: `5`
  - Source checks: `5`
  - Ready providers: `23`
  - Blocked providers: `6`

### UI

Playwright/Chrome UI smoke verified:

- Page: `http://127.0.0.1:5177/`
- Workspace: `System Health`
- Panel present: `Provider Readiness Board`
- Button present: `Run readiness sweep`
- Live text present:
  - `23 ready`
  - `39 total providers`
  - `coding_escalation default endpoint`
  - `TradingView MCP bridge connector`
  - `Relaunch TradingView Desktop with --remote-debugging-port=9222 before desktop MCP control.`

### Build And Compile

Passed:

```bash
python3 -m py_compile _ai_os_runtime/scripts/run_provider_readiness_sweep.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
```

React build output:

- `dist/index.html`
- `dist/assets/index-DAv6xFsv.css`
- `dist/assets/index-Cm6Dxahd.js`

## Guardrails

- No raw secrets are stored.
- Missing credentials are represented as `blocked_secret`.
- Browser-dependent connectors are not marked ready unless browser checks exist.
- TradingView remains blocked until CDP is available.
- Approval-required cloud/frontier endpoints are not marked freely assignable.
- The board is readiness/control evidence, not market evidence.

## What This Unlocks

Agents can now route work through a real provider control layer:

- Jarvis can ask which model or data connector is usable before assigning work.
- Charlie can see why a task cannot use TradingView, broker APIs, frontier models, or crypto connectors yet.
- Quant, Research, Portfolio, News, and Trading agents can be prevented from using blocked providers.
- The next model/data-source plug-in can be added as a provider row, swept, exposed to MCP, and shown in UI without rebuilding the whole dashboard.

## Remaining Work

- Relaunch TradingView Desktop with CDP on port `9222`, then rerun browser/session checks.
- Add secret references for approved broker/cloud providers without storing raw keys.
- Activate/configure crypto and commodity connectors only after exchange/broker choice is finalized.
- Add scheduled provider readiness sweeps through the daemon.
- Add alerting when a previously ready provider becomes blocked.
- Add assignment gating so agent task creation can reject blocked providers automatically.

