# NSE/BSE Filing Collector And Research Factory Inbox

Date: 2026-07-06
Status: implemented and verified foundation slice
Blueprint: [[AI Investment OS - Institutional Master Blueprint v4.0]]
Checklist: [[AI Investment OS - Institutional Build Checklist v4.0]]

## What Changed

- Added live NSE/BSE collector support through `_ai_os_runtime/scripts/collect_nse_bse_filings.py`.
- Connected the collector to the existing Research Factory warehouse tables:
  - `research.filing_collector_runs`
  - `research.corporate_filings`
  - `research.filing_events`
  - `agent.inbox_items` for non-routine filing events
  - `core.raw_artifacts`
- Exposed filing data through API snapshot keys:
  - `filing_collector_runs`
  - `corporate_filing_inbox`
  - `special_situation_inbox`
- Added API route:
  - `POST /api/research/filings/collect`
- Added dashboard panels:
  - NSE/BSE Filing Collector
  - Filing Collector Runs
  - Corporate Filing Inbox
  - Special Situations Inbox
- Added connector health promotion after successful collector runs:
  - `nse_filings_connector`
  - `bse_filings_connector`
- Updated the v4 checklist to mark the collector done and the special-situation classifier/dashboard as partial.

## Verified Evidence

- Python compile passed for:
  - `_ai_os_runtime/scripts/collect_nse_bse_filings.py`
  - `_ai_os_runtime/api/ai_os_api_server.py`
- React/Vite production build passed for AI Office UI.
- Dry-run live public source check passed for 2026-07-05 to 2026-07-06:
  - NSE HTTP 200, 5 rows seen.
  - BSE HTTP 200, 0 rows seen.
- Real limited collector run wrote production warehouse rows:
  - `research.filing_collector_runs`: 2 rows.
  - `research.corporate_filings` with collector run: 5 rows.
  - `research.filing_events`: 5 rows.
  - event type: `routine_filing = 5`.
- Connector status after collector run:
  - `nse_filings_connector`: `configured`, latest rows seen `5`.
  - `bse_filings_connector`: `configured`, latest rows seen `0`.
- Live stack restarted successfully:
  - API health: `ok = true`.
  - UI served at `http://127.0.0.1:5177/`.
  - Snapshot issues: `0`.
  - Snapshot `filing_collector_runs`: `2`.
  - Snapshot `corporate_filing_inbox`: `5`.
  - Snapshot `special_situation_inbox`: `0`.
- API collector route dry-run passed:
  - `POST /api/research/filings/collect`
  - source `bse`
  - HTTP source status `200`
  - `ok = true`

## Current Interpretation

The Research Factory now has a real public-source filing ingestion path. NSE/BSE runs are auditable, source-linked, and visible in the AI Office dashboard. The collector does not create fake special situations; the first verified window produced routine NSE filings and no BSE rows.

## Guardrails

- The collector writes public filing data and event classifications only.
- It does not place trades.
- Non-routine filing events can create agent inbox work for the appropriate research agent.
- PDF parsing is not yet complete; filing PDFs are linked through `attachment_url`.
- Special situation logic is keyword-based until the PDF/parser and event-term extraction are implemented.

## Still Open

- Build filing PDF parser and extraction pipeline.
- Add richer corporate action classifier from parsed filing text.
- Add arbitrage spread tracker for open offers, delistings, mergers, and demergers.
- Add scheduled collector runs with freshness alerts.
- Add special-situation memo generation and Investment Committee routing.
- Add Twitter/X and news source collectors.
