# Browser Profile And Connector Control Layer

Date: 2026-07-06
Status: implemented and verified foundation slice

## What Changed

- Added `_ai_os_runtime/postgres/init/047_browser_profile_connector_control.sql`.
- Added browser profile registry:
  - `ops.browser_profiles`
- Added source connector links:
  - `ops.browser_profile_connector_links`
- Added browser runtime/profile check ledger:
  - `ops.browser_session_checks`
- Added database functions:
  - `ops.register_browser_profile`
  - `ops.attach_browser_profile_to_connector`
  - `ops.record_browser_session_check`
- Updated `core.run_source_connector_health_check` so browser-dependent connectors now distinguish:
  - `needs_browser`
  - `needs_browser_check`
  - `browser_unavailable`
  - `needs_activation`
  - `configured`
- Added views:
  - `ops.v_browser_profile_control`
  - `ops.v_browser_connector_links`
  - `ops.v_browser_session_checks`
- Seeded browser profiles:
  - `tradingview_desktop_cdp`
  - `public_research_playwright`
  - `x_watchlist_manual_profile`
- Linked browser profiles to connectors:
  - `tradingview_mcp_connector` -> `tradingview_desktop_cdp`
  - `nse_filings_connector` -> `public_research_playwright`
  - `bse_filings_connector` -> `public_research_playwright`
  - `x_watchlist_connector` -> `x_watchlist_manual_profile`
- Added browser profile directories under the external SSD runtime:
  - `_ai_os_runtime/browser_profiles/public_research`
  - `_ai_os_runtime/browser_profiles/x_watchlist_manual`
- Added API snapshot keys:
  - `browser_profiles`
  - `browser_connector_links`
  - `browser_session_checks`
- Added API endpoints:
  - `POST /api/browser/profiles/register`
  - `POST /api/browser/connectors/attach-profile`
  - `POST /api/browser/profiles/check`
- Added AI Office dashboard panels:
  - Browser Profile Control
  - Browser Connector Links
  - Browser Session Checks

## Guardrails

- Browser profiles are named and auditable before source connectors can depend on them.
- TradingView Desktop CDP is localhost-only and remains gated.
- TradingView broker/execution is still disabled.
- X/social profile is planned/manual-review because logged-in social browsing is private and rumor-prone.
- NSE/BSE profile readiness does not mean scraper production is complete; it only proves browser profile readiness.

## Verified Evidence

- API Python compile passed.
- Browser migration applied successfully.
- UI `npm run build` passed.
- Rollback smoke test proved:
  - temporary browser profile registration works,
  - temporary connector attachment works,
  - browser session check can set `profile_ready`,
  - source connector health can consume browser check state,
  - rollback left 0 temporary profiles, links, and checks.
- Live API smoke passed for:
  - browser profile register,
  - browser profile attach,
  - browser profile check,
  - browser-dependent source connector check.
- API smoke cleanup confirmed:
  - profiles: 0
  - links: 0
  - browser checks: 0
  - source rows: 0
  - connector checks: 0
  - audit rows: 0
- Live API health returned `ok = true`.
- AI Office UI returned HTTP 200.
- Final snapshot returned:
  - `issues = []`
  - `seed_data_allowed = false`
  - `browser_profiles = 3`
  - `browser_connector_links = 4`
  - `browser_session_checks = 3`
  - `source_connectors = 18`

## Current Real Readiness

- `public_research_playwright`: `profile_ready`
- `tradingview_desktop_cdp`: `cdp_unavailable`
- `x_watchlist_manual_profile`: `unchecked`
- `nse_filings_connector`: `needs_activation`
- `bse_filings_connector`: `needs_activation`
- `tradingview_mcp_connector`: `browser_unavailable`
- `zerodha_live_connector`: `needs_secret`

## Interpretation

The platform now knows why browser-dependent connectors are not live:

- TradingView is blocked by localhost CDP not listening on port `9222`.
- NSE/BSE browser profile exists and is ready, but the production scraper/collector is not activated yet.
- Zerodha is blocked by missing secret reference, not by browser profile state.
- X/social is intentionally manual/planned because logged-in social data requires privacy and rumor controls.

## Still Open

- Relaunch TradingView Desktop with `--remote-debugging-port=9222` and verify CDP.
- Build the production TradingView browser/controller worker.
- Build NSE/BSE filing collector using the public research profile.
- Add raw artifact capture for browser page snapshots and downloaded filing PDFs.
- Add scheduled freshness checks for browser-dependent connectors.

