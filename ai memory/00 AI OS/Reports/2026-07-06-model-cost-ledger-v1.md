# Model Cost Ledger v1

Date: 2026-07-06
Owner: AI Engineering
Status: Verified

## What Changed

Built a model route and cost-control ledger for the AI Investment OS. The system can now track model usage across local and future cloud runtimes, keep per-agent cost caps, expose cost-control status, and prove that the daily driver remains local-first unless a paid/cloud route is explicitly approved.

## Database Objects

Tables:

- `agent.model_cost_rates`
- `agent.model_usage_events`
- `agent.model_cost_caps`

Views:

- `agent.v_model_cost_ledger_events`
- `agent.v_model_cost_summary`
- `agent.v_agent_model_cost_cap_status`
- `agent.v_model_route_cost_summary`

## Backfill And Runtime Logging

Existing `agent.chat_turns` rows were backfilled into `agent.model_usage_events`.

Future Charlie/Jarvis chat turns now automatically call the cost logger from `persist_chat_turn`, using:

- `source_kind = chat_turn`
- `source_ref = chat_turn.id`
- `estimate_method = chars_div_4_from_chat_turn`

Token counts are marked as estimates. Local runtimes are zero-metered unless a paid endpoint rate is explicitly registered.

## Verified Counts

API snapshot after verification:

```json
{
  "issues": [],
  "summary": {
    "agents_with_caps": "32",
    "cloud_usage_events": "0",
    "estimated_cost_month_usd": "0.000000",
    "estimated_cost_today_usd": "0.000000",
    "local_usage_events": "14",
    "rate_missing_events": "0",
    "total_usage_events": "14",
    "unapproved_cloud_events": "0"
  },
  "events": 14,
  "caps": 32,
  "routes": 3
}
```

Cap status:

| Status | Agents |
|---|---:|
| ok | 32 |

## API

Added snapshot keys:

- `model_cost_summary`
- `model_cost_events`
- `model_cost_caps`
- `model_route_costs`

Added route:

- `POST /api/models/usage`

Direct API smoke:

```json
{
  "id": 12,
  "total_tokens_est": 100,
  "estimated_cost_usd": 0,
  "actual_cost_usd": 0,
  "cost_control_status": "ok"
}
```

## MCP

Added tools:

- `ai_os_model_cost_ledger`
- `ai_os_record_model_usage`

MCP JSON-RPC smoke:

```json
{
  "initialized": true,
  "tools_registered": true,
  "created_id": 13,
  "created_cost": 0,
  "created_status": "ok",
  "summary_rows": 8,
  "cap_rows": 32,
  "event_rows": 3
}
```

## Dashboard

Added Live AI Office panel:

- `Model Cost Ledger`
- Summary metrics
- Agent cost caps
- Route usage
- Recent model usage events

Browser render smoke:

```json
{
  "visible": true,
  "hasRouteUsage": true,
  "hasRecentEvents": true,
  "hasZeroToday": true
}
```

## Automatic Chat Logging Smoke

Created a Charlie chat turn and confirmed a new ledger row:

```json
{
  "chat_turn_id": 43,
  "model_status": "model_unavailable",
  "auto_logged": true,
  "logged_status": "ok",
  "logged_cost": 0.0
}
```

The chat model was unavailable, but the turn still persisted and the ledger correctly recorded a local zero-cost event with status `ok`.

## Implementation Note

During API smoke, an explicit numeric zero was initially treated as missing because Python `or` drops `0`. Fixed by adding `first_present()` and using it for token/cost fields so zero-cost local model usage remains accurate.

## Files Changed

- `_ai_os_runtime/postgres/init/084_model_cost_ledger_v1.sql`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v7.0.md`

## Verification

- Migration applied to `ai_os_postgres`: passed.
- Backfilled existing chat turns: 10 events.
- Direct API model usage write: passed.
- MCP model usage write/read: passed.
- Automatic chat-turn model logging: passed.
- Python compile for API/MCP: passed.
- Frontend production build: passed.
- API snapshot smoke: passed with `issues: []`.
- Live browser render check using system Chrome: passed.

## Remaining Gaps

- Cloud escalation approval workflow is still open. The ledger flags unapproved cloud usage, but it does not yet create approval requests automatically.
- Model call cache is still open.
- Daily driver benchmark/eval set is still open.
- Cloud model pricing rates should be registered only when actual endpoints are connected and approved.
