# TradingView Alert Inbox Live Verification

Date: 2026-07-06
Owner: Trading Desk Agent / Risk Agent / Jarvis
Blueprint: [[AI Investment OS - Institutional Master Blueprint v7.0]]
Checklist: [[AI Investment OS - Execution Checklist v7.0]]

## Result

The TradingView alert inbox is now live through the running API and dashboard snapshot.

The workflow is human gated:

1. A TradingView alert request is created through `/api/tradingview/template-actions`.
2. The request creates an `ops.tradingview_tasks` row with status `needs_approval`.
3. The request creates an `agent.approvals` row.
4. The dashboard snapshot exposes the request through `tradingview_alert_requests`.
5. A human/authorized resolver approves or rejects through `/api/tradingview/alert-requests/resolve`.
6. Approved requests move to `approved_pending_manual_alert`.
7. The system does not create the TradingView alert automatically.

## Live Runtime Evidence

Runtime service restart:

```text
bash _ai_os_runtime/scripts/start_ai_office_live.sh
```

Result:

```text
Started AI OS LaunchAgents:
  http://127.0.0.1:8765/api/health
  com.devarsh.aios.agent-daemon
  http://127.0.0.1:5177/
```

API health:

```json
{
  "ok": true,
  "runtime_root": "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime",
  "tradingview_cdp": {
    "available": true,
    "port": 9222,
    "browser": "Chrome/140.0.7339.133"
  }
}
```

UI health:

```text
HTTP/1.0 200 OK
http://127.0.0.1:5177/
```

## Database Evidence

The live database view exists and contains alert request rows:

```text
ops.v_tradingview_alert_requests|3
```

After the live smoke test, the snapshot showed four alert requests and approval `12` was visible.

Final database state for the smoke test:

```json
{
  "task_15": {
    "id": 15,
    "status": "approved_pending_manual_alert",
    "summary": "TradingView alert request approved for manual creation. The system did not create the alert automatically.",
    "decision": "approved",
    "evidence_count": 2,
    "auto_create_alert": "false"
  },
  "alert_row": {
    "state": "approved_for_manual_creation",
    "symbol": "USHAMART",
    "task_id": 15,
    "condition": "crosses 530",
    "approval_id": 12,
    "task_status": "approved_pending_manual_alert",
    "approval_status": "approved"
  },
  "approval_12": {
    "id": 12,
    "action": "alert_create_request",
    "status": "approved",
    "decided_by": "Codex Live Alert Inbox Smoke",
    "requested_task": "15"
  }
}
```

## API Smoke Test

Create request:

```text
POST /api/tradingview/template-actions
template_key=create_alert_request
symbol=USHAMART
condition=crosses 530
auto_create_alert=false
```

Create result:

```json
{
  "created_task_id": 15,
  "created_task_status": "needs_approval",
  "approval_id": 12,
  "approval_status": "pending",
  "template_key": "create_alert_request"
}
```

Resolve request:

```text
POST /api/tradingview/alert-requests/resolve
approval_id=12
status=approved
```

Resolve result:

```json
{
  "decision": "approved",
  "approval_id": 12,
  "approval_status": "approved",
  "task_id": 15,
  "task_status": "approved_pending_manual_alert",
  "auto_create_alert": false
}
```

## Snapshot Evidence

The live `/api/snapshot` response now includes `tradingview_alert_requests`.

Approval `12` appeared with:

```json
{
  "approval_id": 12,
  "tradingview_task_id": 15,
  "approval_status": "approved",
  "task_status": "approved_pending_manual_alert",
  "alert_request_state": "approved_for_manual_creation",
  "symbol": "USHAMART",
  "alert_condition": "crosses 530",
  "auto_create_alert": false
}
```

## Verification Commands

Python compile:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Result: passed.

Frontend build:

```text
npm run build
```

Result:

```text
✓ built in 563ms
```

## Files And Runtime Pieces

Database:

- `_ai_os_runtime/postgres/init/072_tradingview_alert_inbox.sql`
- `ops.v_tradingview_alert_requests`

API:

- `_ai_os_runtime/api/ai_os_api_server.py`
- `GET /api/snapshot`
- `POST /api/tradingview/template-actions`
- `POST /api/tradingview/alert-requests/resolve`

Frontend:

- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- TradingView Alert Inbox panel

Runtime:

- API: `http://127.0.0.1:8765/api/health`
- UI: `http://127.0.0.1:5177/`
- TradingView CDP: `127.0.0.1:9222`

## What This Does Not Yet Do

This does not automatically create TradingView alerts inside the user account.

That is intentional. Alert creation changes account state and can affect live monitoring, so the current approved state is:

```text
approved_pending_manual_alert
```

Remaining work:

- build the manual-alert-created evidence capture,
- add alert lifecycle tracking,
- add failed/stale alert monitoring,
- harden the broader TradingView production controller,
- add richer straddle/strangle and multi-chart workflows.

## Checklist Updates

Updated in [[AI Investment OS - Execution Checklist v7.0]]:

- `Alert inbox completion` marked done.
- `Human-gated TradingView alert request template` marked done.
- `TradingView gated alert request path` marked done.
- Immediate build order split into completed alert inbox and remaining production controller hardening.

