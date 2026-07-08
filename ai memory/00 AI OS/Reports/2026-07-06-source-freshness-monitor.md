# Source Freshness Monitor

Date: 2026-07-06
Status: done and verified
Owner: Data Steward / Risk Agent

## What Was Added

- Added freshness table:
  - `core.data_source_freshness_checks`
- Added freshness views:
  - `core.v_data_source_freshness_checks`
  - `core.v_latest_data_source_freshness`
- Added checker:
  - `_ai_os_runtime/scripts/check_source_freshness.py`
- Added API route:
  - `POST /api/data-sources/freshness/check`
- Added snapshot keys:
  - `source_freshness`
  - `risk_events`
- Added dashboard panels:
  - Source Freshness Monitor
  - Open Risk Events
- Added tool registry entry:
  - `ai_os_check_source_freshness`

## Real Verification Case

Source:

- `tradingview_scanner_quotes`
- Freshness target: `15` minutes
- Latest quote: ROLEXRINGS quote id `92`
- Latest quote timestamp: `2026-07-06T06:18:23.419039+00:00`

Fresh path:

- API returned freshness row id `4`.
- Status: `fresh`
- Target: `15` minutes
- Staleness: about `7.64` minutes at verification time.
- Risk event: null.
- Snapshot showed `source_freshness[0].status = fresh`.
- Snapshot showed `issues = 0`.

Stale path:

- Ran the checker with strict verification target `1` minute.
- It created risk event id `8`.
- Risk event status was initially stale/new via the freshness check result.
- Reran with the real source target.
- Risk event id `8` was closed.
- Latest freshness returned to `fresh`.

## Guardrails

- The monitor uses source registry targets and actual stored source/quote timestamps.
- It does not fetch data itself.
- It creates risk events only for stale, error, or missing source checks.
- It closes source-risk events when the source recovers.
- It is manual/API-triggered for now; scheduled cadence remains a separate open item.

## Verification Evidence

- `python3 -m py_compile _ai_os_runtime/scripts/check_source_freshness.py _ai_os_runtime/api/ai_os_api_server.py` passed.
- `npm run build` in `_ai_os_runtime/ai-office-ui` passed.
- Migration `postgres/init/054_source_freshness_monitor.sql` applied successfully.
- Live API `POST /api/data-sources/freshness/check` returned fresh row id `4`.
- Strict-target stale test created risk event id `8`.
- Normal-target rerun closed risk event id `8`.
- `core.v_latest_data_source_freshness` shows `tradingview_scanner_quotes` as `fresh`.
- `risk.events` shows event id `8` as `closed`.
- API snapshot shows `issues = 0` and no open risk events.
- UI served successfully at `http://127.0.0.1:5177/`.

## Still Open

- Add launchd or worker-daemon scheduled cadence.
- Add notification routing for stale critical sources.
- Add reconciliation dashboard across broker files, source checks, quote freshness, and imports.
- Add freshness policies per data class: quotes, filings, broker, news, crypto, and model routes.
