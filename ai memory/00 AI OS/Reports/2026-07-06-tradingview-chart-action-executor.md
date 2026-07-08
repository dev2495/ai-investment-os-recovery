# TradingView Chart Action Executor - Evidence Report

Date: 2026-07-06
Status: verified open-chart and screenshot artifact workflow; full production controller remains partial

## What Changed

Implemented dependency-free TradingView CDP executor:

- `_ai_os_runtime/scripts/execute_tradingview_chart_action.mjs`
- Uses local TradingView Desktop CDP on `127.0.0.1:9222`.
- Opens TradingView chart URLs with symbol and interval.
- Captures screenshot PNG artifacts under the SSD runtime:
  - `_ai_os_runtime/artifacts/tradingview/YYYYMMDD/`
- Does not place broker orders.

Implemented API action:

- `_ai_os_runtime/api/ai_os_api_server.py`
- New route:
  - `POST /api/tradingview/chart-actions`
- Behavior:
  - creates a TradingView task if no `task_id` is supplied
  - runs the local CDP executor
  - stores screenshot in `core.raw_artifacts`
  - stores browser execution in `ops.browser_runs`
  - updates `ops.tradingview_tasks`
  - writes audit evidence through the API audit path

Implemented MCP tool exposure:

- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- New MCP tool:
  - `ai_os_execute_tradingview_chart_action`
- The MCP tool calls the same local API route, so dashboard/API/MCP actions share the same persistence path.

Implemented AI Office UI action:

- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`
- TradingView task rows now show a `Capture` action when CDP is online.

Implemented registry migration:

- `_ai_os_runtime/postgres/init/069_tradingview_chart_action_executor.sql`
- Registered `ai_os_execute_tradingview_chart_action`.
- Updated TradingView MCP registry metadata.
- Updated TradingView data-source metadata.
- Updated control-plane module next actions.

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

HTTP route smoke:

```text
POST /api/tradingview/chart-actions
symbol: USHAMART
exchange: NSE
timeframe: D
result: done
artifact_id: 139
browser_run_id: 3
```

MCP handler smoke:

```text
tool: ai_os_execute_tradingview_chart_action
symbol: USHAMART
exchange: NSE
timeframe: D
result: done
artifact_id: 141
browser_run_id: 5
```

Latest verified artifact:

```text
_ai_os_runtime/artifacts/tradingview/20260706/2026-07-06T12-17-08-077Z-ushamart.png
size: 200K
content: Usha Martin daily TradingView chart with candles and OHLC visible
```

Database verification:

```json
{
  "latest_task": {
    "id": 5,
    "status": "done",
    "summary": "Opened TradingView chart for USHAMART (NSE, D) and captured screenshot evidence.",
    "symbols": ["USHAMART"],
    "artifact_id": 141,
    "browser_run_id": 5
  },
  "browser_runs": 4,
  "tool_registered": 1,
  "tradingview_tasks": 4,
  "done_chart_actions": 4,
  "screenshot_artifacts": 4
}
```

Snapshot verification:

```text
tradingview_cdp.available = true
tradingview_tasks = 4
latest task id = 5
latest task status = done
latest task artifact = 141
issues = []
```

Build checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py
python3 -m py_compile _ai_os_runtime/mcp_server/ai_os_mcp_server.py
node --check _ai_os_runtime/scripts/execute_tradingview_chart_action.mjs
npm run build
```

All passed.

## Checklist Updates

Marked done:

- TradingView chart open workflow.
- TradingView screenshot artifact capture.
- TradingView CDP connection verified and chart-action executor added.
- TradingView screenshot artifact API.

Marked partial:

- TradingView production controller.
- TradingView layout/chart action API.
- Immediate sprint: TradingView production chart actions.

## Important Limits

This is not yet the full TradingView production controller.

Verified now:

- open one chart URL
- set symbol and timeframe through URL
- capture screenshot artifact
- write task, browser run, raw artifact, and audit evidence
- invoke through API, dashboard, and MCP handler

Still open:

- multi-pane layouts
- four-chart option layouts
- straddle/strangle chart templates
- indicator add/remove controls
- alert creation/deletion gates
- Pine script push/pull/compile workflows
- chart annotation workflows
- robust retry/wait logic for slow chart data loads
- screenshot quality checks that automatically reject blank chart canvases

## Next Recommended Build Step

Build TradingView action templates:

- `open_symbol_chart`
- `open_multi_symbol_layout`
- `open_option_straddle_layout`
- `capture_chart_snapshot`
- `capture_symbol_watchlist`
- `create_alert_request` as human-gated only

Then connect those actions into Symbol Intelligence so each symbol can trigger chart evidence directly from the portfolio context.
