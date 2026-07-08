# TradingView Screenshot Quality Gate

Date: 2026-07-06
Status: verified

## What Changed

Added screenshot quality analysis inside:

- `_ai_os_runtime/scripts/execute_tradingview_chart_action.mjs`

The executor now:

- parses PNG screenshots with built-in Node APIs and `zlib`
- inspects the central chart canvas region
- counts saturated/chart-like pixels
- retries captures when the chart canvas looks blank
- returns:
  - `artifact_quality_status`
  - `artifact_quality`
  - `quality_attempts`

Updated API persistence:

- `_ai_os_runtime/api/ai_os_api_server.py`

The API now:

- sends `quality_check` and `max_quality_attempts` to the executor
- marks passed captures as `done`
- marks failed captures as `needs_review`
- stores quality metadata in:
  - `ops.tradingview_tasks.metadata.last_chart_action`
  - `ops.browser_runs.metadata`
  - `core.raw_artifacts.metadata`
  - task evidence

Updated registry metadata:

- `_ai_os_runtime/postgres/init/071_tradingview_screenshot_quality_gate.sql`

The quality gate is now recorded in:

- `agent.tool_registry`
- `ops.tradingview_action_templates`
- `core.control_plane_modules`

## Quality Method

The analyzer samples the central chart region and calculates:

- `chart_like_ratio`
- `saturated_ratio`
- `bright_ratio`

Current pass thresholds:

```json
{
  "chart_like_ratio": 0.0014,
  "saturated_ratio": 0.0022
}
```

If the chart canvas has no candle/line-like pixels, the artifact is rejected and routed to `needs_review`.

## Verification

Known valid TradingView chart screenshot:

```json
{
  "status": "passed",
  "reason": "chart_pixels_detected",
  "saturated_ratio": 0.029971,
  "chart_like_ratio": 0.016017
}
```

Known blank-canvas TradingView screenshot:

```json
{
  "status": "failed",
  "reason": "chart_canvas_likely_blank",
  "saturated_ratio": 0,
  "chart_like_ratio": 0
}
```

Direct executor smoke:

```json
{
  "artifact_quality_status": "passed",
  "quality_attempts": 2,
  "reason": "chart_pixels_detected"
}
```

Live HTTP template smoke with blank chart canvas:

```json
{
  "task_id": 13,
  "status": "needs_review",
  "artifact_id": 147,
  "artifact_quality_status": "failed",
  "summary": "Opened TradingView chart for USHAMART (NSE, D) but screenshot quality failed; artifact requires review."
}
```

Database evidence:

```json
{
  "latest_quality_task": {
    "id": 13,
    "status": "needs_review",
    "quality": "failed",
    "artifact": 147,
    "template": "capture_chart_snapshot"
  },
  "tool_quality_config": {
    "method": "png_pixel_analysis_chart_region",
    "enabled": true,
    "failed_status": "needs_review",
    "default_max_attempts": 3
  },
  "quality_failed_tasks": 1
}
```

Snapshot evidence:

```json
{
  "latest_task_id": 13,
  "latest_status": "needs_review",
  "latest_quality": "failed",
  "latest_artifact": 147,
  "issues": []
}
```

Build checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
node --check _ai_os_runtime/scripts/execute_tradingview_chart_action.mjs
```

Both passed.

## Checklist Update

Marked done:

- TradingView screenshot visual-quality rejection gate.

## Remaining TradingView Work

Still open:

- multi-pane chart layout control
- option straddle/strangle chart workflow
- alert inbox UI
- Pine script pull/push/compile workflow
- richer retry actions beyond wait/resize, such as pane focus or layout reload
