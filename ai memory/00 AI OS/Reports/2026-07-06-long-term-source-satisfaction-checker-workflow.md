# Long-Term Source Satisfaction Checker Workflow

Generated: 2026-07-06

## What Is Live

Long-Term source requests can now be checked against real source stores:

- `research.corporate_filings`
- `core.raw_artifacts`
- `knowledge.obsidian_notes` only when notes carry explicit source-document provenance

The checker writes:

- `portfolio.long_term_source_request_checks`
- `portfolio.v_long_term_source_request_checks`
- updated satisfaction fields on `portfolio.long_term_source_requests`
- Obsidian check notes under `ai memory/05 Filings and Transcripts/Long-Term Source Checks/`

If all source requests for a specialist output are satisfied, the workflow can mark the blocked specialist output as source-ready and queue the specialist assignment for rerun.

## Files Added Or Changed

- `_ai_os_runtime/postgres/init/064_long_term_source_satisfaction_workflow.sql`
- `_ai_os_runtime/scripts/check_long_term_source_satisfaction.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Master Build Checklist v5.0.md`

## API And Dashboard

New snapshot table:

- `long_term_source_request_checks`

Updated snapshot table:

- `long_term_source_requests` now includes satisfaction status, match count, last checked time, and satisfaction evidence.

New API route:

- `POST /api/portfolio/long-term-source-requests/check`

Dashboard update:

- Each source request row now has a `Check` action.
- Long-Term panel now shows recent source checks.

## Verification Evidence

Migration applied after preserving existing view column order:

```text
ALTER TABLE
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE VIEW
CREATE VIEW
INSERT 0 1
UPDATE 3
```

Compile and frontend build:

```bash
python3 -m py_compile _ai_os_runtime/scripts/check_long_term_source_satisfaction.py _ai_os_runtime/api/ai_os_api_server.py
npm run build
```

CLI check proof:

```json
{
  "checked_count": 3,
  "satisfied_count": 0,
  "missing_count": 3,
  "rerun_queued_count": 0,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

HTTP check proof:

```json
{
  "checked_count": 1,
  "satisfied_count": 0,
  "missing_count": 1,
  "rerun_queued_count": 0,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

Live source request state:

```text
lt-src-2-moat-scorecard-company-filings|queued|missing|0
lt-src-2-business-model-company-filings|queued|missing|0
lt-src-2-business-model-annual-report-or-investor-presentation|queued|missing|0
```

Columns:

```text
request_key | status | satisfaction_status | matched_source_count
```

Check history:

```text
missing|4
```

Snapshot proof:

```text
long_term_source_requests = 3
long_term_source_request_checks = 4
```

Health proof:

```json
{
  "ok": true,
  "tradingview_cdp": {
    "available": true,
    "port": 9222
  }
}
```

## Current Truth

The system found ordinary USHAMART notes in Obsidian, but did not treat them as source satisfaction because they do not carry source-document provenance. There are still no USHAMART rows in `research.corporate_filings` or `core.raw_artifacts`.

That is the correct behavior. The source requests remain queued and missing until official source documents are collected.

## What Remains

- Build symbol-specific official-source collection for annual reports, investor presentations, and filings.
- Add source-document note writer for manually captured URLs/PDFs.
- Run satisfaction checker after collection.
- Rerun blocked specialist modules once requests are satisfied.
- Feed completed outputs into Long-Term committee memos.

