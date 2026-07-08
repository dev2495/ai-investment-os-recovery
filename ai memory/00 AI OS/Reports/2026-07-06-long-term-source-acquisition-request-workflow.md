# Long-Term Source Acquisition Request Workflow

Generated: 2026-07-06

## What Is Live

Long-Term specialist source gaps can now be converted into source acquisition work for the Filings and Transcript Analyst.

The workflow creates:

- `portfolio.long_term_source_requests` rows,
- `portfolio.v_long_term_source_requests` dashboard view,
- `agent.tasks` rows,
- `agent.inbox_items` rows,
- Obsidian batch notes under `ai memory/05 Filings and Transcripts/Long-Term Source Requests/`,
- collector hints for NSE/BSE filings, PDF extraction, company IR pages, annual reports, and investor presentations.

This layer does not collect or fabricate the missing filing itself. It turns a blocked analyst output into a tracked source request with provenance requirements and an assigned employee.

## Agent Added

`Filings and Transcript Analyst` is now an active profile.

Role:

- collect annual reports,
- collect exchange filings,
- collect investor presentations,
- collect transcripts,
- preserve source URLs and document provenance,
- route source evidence back to Long-Term specialist agents.

## Files Added Or Changed

- `_ai_os_runtime/postgres/init/063_long_term_source_request_workflow.sql`
- `_ai_os_runtime/scripts/create_long_term_source_requests.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Master Build Checklist v5.0.md`

## API And Dashboard

New snapshot table:

- `long_term_source_requests`

New API route:

- `POST /api/portfolio/long-term-source-requests/create`

Dashboard update:

- Specialist outputs now have a `Request sources` action.
- Long-Term panel now shows the source request queue.

## Verification Evidence

Migration applied:

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
INSERT 0 1
INSERT 0 1
INSERT 0 2
CREATE VIEW
INSERT 0 1
UPDATE 3
```

Compile and frontend build:

```bash
python3 -m py_compile _ai_os_runtime/scripts/create_long_term_source_requests.py _ai_os_runtime/api/ai_os_api_server.py
npm run build
```

CLI request generation from USHAMART specialist outputs:

```json
{
  "source_request_count": 3,
  "specialist_output_count": 2,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

HTTP request generation proof:

```json
{
  "source_request_count": 2,
  "specialist_output_count": 1,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

Live source request view:

```text
USHAMART|company_filings|moat_scorecard|queued|78|124
USHAMART|company_filings|business_model|queued|79|125
USHAMART|annual_report_or_investor_presentation|business_model|queued|80|126
```

Columns:

```text
symbol | source_name | required_for_module | status | task_id | inbox_id
```

Snapshot proof:

```text
long_term_source_requests = 3
```

Agent proof:

```text
Filings and Transcript Analyst|Filings and Transcript Analyst|active
```

Inbox proof:

```text
3 Filings and Transcript Analyst inbox items in target workspace Filings and Transcripts
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

## Current USHAMART Requests

- `company_filings` for `moat_scorecard`
- `company_filings` for `business_model`
- `annual_report_or_investor_presentation` for `business_model`

Each request includes collection commands and a manual browser hint. The completion rule requires real evidence in `research.corporate_filings`, `core.raw_artifacts`, or an Obsidian source note with URL provenance.

## What Remains

- Add a direct official-source collector for symbol-specific annual reports and investor presentations.
- Add source satisfaction checks that automatically mark requests as `satisfied` when matching filings/artifacts arrive.
- Rerun blocked specialist outputs after source requests are satisfied.
- Feed completed specialist outputs into the Long-Term Investment Committee memo.
- Continue with Command Center v2 and the animated AI office state.

