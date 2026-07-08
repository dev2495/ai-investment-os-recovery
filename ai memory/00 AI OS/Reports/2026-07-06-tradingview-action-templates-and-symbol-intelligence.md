# TradingView Action Templates And Symbol Intelligence Integration

Date: 2026-07-06
Status: verified template registry/API/MCP/UI integration; visual-quality hardening still open

## What Changed

Added TradingView action template registry:

- `_ai_os_runtime/postgres/init/070_tradingview_action_templates.sql`
- New table:
  - `ops.tradingview_action_templates`
- New view:
  - `ops.v_tradingview_action_templates`
- Registered six templates:
  - `open_symbol_chart`
  - `capture_chart_snapshot`
  - `open_multi_symbol_layout`
  - `open_option_straddle_layout`
  - `capture_symbol_watchlist`
  - `create_alert_request`

Added API template execution:

- `_ai_os_runtime/api/ai_os_api_server.py`
- New snapshot section:
  - `tradingview_action_templates`
- New route:
  - `POST /api/tradingview/template-actions`
- Executable templates call the existing chart-action executor.
- Gated templates create:
  - `ops.tradingview_tasks` row with `needs_approval`
  - `agent.approvals` row
  - `agent.inbox_items` row
- No broker order or automatic alert creation is allowed.

Added MCP template tool:

- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- New MCP tool:
  - `ai_os_execute_tradingview_template_action`
- The MCP tool delegates to the same audited API route.

Added Symbol Intelligence buttons:

- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`
- Each Symbol Intelligence row now has:
  - `Chart`
  - `Snapshot`
- These call the template route with symbol/client/thesis context in metadata.

## Live Verification

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

Snapshot template registry:

```json
{
  "templates": 6,
  "template_keys": [
    "capture_chart_snapshot",
    "open_symbol_chart",
    "capture_symbol_watchlist",
    "open_multi_symbol_layout",
    "create_alert_request",
    "open_option_straddle_layout"
  ],
  "issues": []
}
```

Executable HTTP template smoke:

```text
POST /api/tradingview/template-actions
template_key: open_symbol_chart
symbol: USHAMART
result: done
artifact_id: 143
```

MCP template smoke:

```text
tool: ai_os_execute_tradingview_template_action
template_key: capture_symbol_watchlist
symbol: USHAMART
result: done
artifact_id: 144
```

Human-gated alert template smoke:

```text
POST /api/tradingview/template-actions
template_key: create_alert_request
symbol: USHAMART
result: approval_required
approval_id: 10
inbox_item_id: 135
task_status: needs_approval
auto_create_alert: false
```

Latest lineage check:

```json
{
  "template_count": 6,
  "template_artifacts": 1,
  "template_task_count": 6,
  "latest_template_task": {
    "id": 11,
    "status": "done",
    "symbols": ["USHAMART"],
    "artifact": 145,
    "template": "capture_chart_snapshot"
  },
  "pending_tv_approvals": 2,
  "latest_template_artifact": {
    "id": 145,
    "template": "capture_chart_snapshot"
  },
  "template_tool_registered": 1
}
```

Final snapshot check:

```json
{
  "cdp_available": true,
  "templates": 6,
  "tv_tasks": 10,
  "latest_task": {
    "id": 11,
    "status": "done",
    "template": "capture_chart_snapshot",
    "artifact": 145
  },
  "issues": []
}
```

Build checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm run build
```

Both passed.

## Checklist Updates

Marked done:

- TradingView action template registry.
- TradingView template execution API.
- TradingView template MCP tool.
- Symbol Intelligence chart/snapshot action buttons.
- Human-gated TradingView alert request template.
- TradingView action template registry/API/MCP.
- TradingView gated alert request approval path.

Marked partial:

- Straddle/strangle chart workflow.
- Alert inbox.
- TradingView production controller.
- TradingView layout/chart action API.
- Immediate sprint TradingView production chart actions.

Left open:

- TradingView screenshot visual-quality rejection gate.

## Important Limit

The template execution path is verified, but screenshot visual quality is not yet deterministic. Some captures show symbol/price/header correctly but the chart canvas is blank. Earlier captures did show Usha Martin candles and OHLC, so the CDP route works, but the system still needs an automatic quality check and retry loop before screenshots can be trusted in research packets.

## Next Recommended Build Step

Build `TradingView screenshot visual-quality rejection gate`:

- inspect screenshot pixels or canvas state
- reject blank chart canvases
- retry with longer waits or page focus
- persist `artifact_quality_status`
- show quality status in Symbol Intelligence

After that, build the deeper templates:

- multi-pane symbol layouts
- option straddle/strangle chart templates
- alert inbox UI
- Pine script read/push/compile workflow
