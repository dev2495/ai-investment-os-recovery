# Source Freshness Scheduler

Date: 2026-07-06
Status: done and verified
Owner: Jarvis / Data Steward / Risk Agent

## What Was Added

- Added scheduler audit table:
  - `core.source_freshness_scheduler_runs`
- Added scheduler view:
  - `core.v_source_freshness_scheduler_runs`
- Added daemon scheduler behavior:
  - `_ai_os_runtime/scripts/run_agent_message_daemon.py`
  - First daemon pass runs freshness immediately.
  - Later passes run every `AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS`.
  - Default cadence is `900` seconds.
- Added launchd/service wiring:
  - `_ai_os_runtime/launchd/aios-agent-daemon-service.sh`
  - `_ai_os_runtime/launchd/com.devarsh.aios.agent-daemon.plist`
  - `_ai_os_runtime/scripts/start_ai_office_live.sh`
- Added API snapshot key:
  - `source_freshness_scheduler_runs`
- Added dashboard panel:
  - Scheduled Freshness Cadence
- Added tool registry entry:
  - `ai_os_source_freshness_scheduler`

## Runtime Behavior

The scheduler reuses the verified source freshness checker:

- `_ai_os_runtime/scripts/check_source_freshness.py`

That checker writes:

- `core.data_source_freshness_checks`
- `risk.events`

So scheduled stale-source alerts are not a separate fake notification path. They are the same audited risk events that the manual/API freshness monitor creates.

## Verification Evidence

- `python3 -m py_compile _ai_os_runtime/scripts/run_agent_message_daemon.py _ai_os_runtime/scripts/check_source_freshness.py _ai_os_runtime/api/ai_os_api_server.py` passed.
- Migration `postgres/init/055_source_freshness_scheduler.sql` applied successfully.
- Direct daemon pass succeeded with scheduler run id `1`.
- `npm run build` in `_ai_os_runtime/ai-office-ui` passed.
- `bash _ai_os_runtime/scripts/start_ai_office_live.sh` restarted API, agent daemon, and UI successfully.
- Launchd daemon created scheduler run ids `2` and `3` after restart.
- `GET /api/snapshot` includes `source_freshness_scheduler_runs`.
- UI served successfully at `http://127.0.0.1:5177/`.

## Latest Verified Scheduler Rows

At verification time, latest scheduler rows were:

- Run id `3`
  - Status: `success`
  - Checked sources: `9`
  - Fresh sources: `0`
  - Stale/error/missing sources: `3`
  - Cadence: `900` seconds
  - Next run after: `2026-07-06T06:49:01.087738+00:00`
- Run id `2`
  - Status: `success`
  - Checked sources: `9`
  - Stale/error/missing sources: `3`

## Open Risk Events Created By Scheduled Checks

The scheduled checker currently surfaces these open `risk.events`:

- `tradingview_scanner_quotes`
  - Severity: `medium`
  - Status: `new`
  - Reason: quote data crossed the 15-minute freshness target.
- `tradingview_mcp`
  - Severity: `high`
  - Status: `new`
  - Reason: TradingView MCP check is stale.
- `tick_ohlcv_aggregation`
  - Severity: `high`
  - Status: `new`
  - Reason: no freshness check found.

## Guardrails

- The scheduler does not authorize trades.
- It does not fabricate market data.
- It records scheduler health separately from source freshness results.
- Source-specific stale/missing/error conditions flow into `risk.events`.
- Recovery closes source-risk events through the same checker logic.

## Still Open

- Refresh or reconnect the TradingView scanner before relying on fresh intraday signals.
- Complete TradingView CDP/MCP control once TradingView is launched with remote debugging on port `9222`.
- Add external notification routing for critical stale sources after the risk event escalation policy is finalized.
- Add per-source class cadence policies for quotes, filings, broker imports, news, crypto, model endpoints, and browser sessions.
