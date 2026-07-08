# Long-Term Source Document Registration Workflow

Date: 2026-07-06
Owner: Filings and Transcript Analyst
Status: Done and verified

## What Changed

Built the official source-document registration workflow for the Long-Term Investing Office. This lets the system register a real official company URL or local document against a pending source request, store it as a raw artifact, write a source-provenance Obsidian note, expose it in the live dashboard snapshot, and allow the source satisfaction checker to pass only from real evidence.

## Warehouse

- Added `portfolio.long_term_source_documents`.
- Added `portfolio.v_long_term_source_documents`.
- Registered tool `ai_os_register_long_term_source_document`.
- Updated control-plane modules for `portfolio_office`, `research_inbox`, and `data_sources`.

Migration:

```bash
python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/065_long_term_source_document_registration.sql
```

Result:

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE VIEW
INSERT 0 1
UPDATE 3
```

## Runtime Workflow

Script:

```bash
python3 _ai_os_runtime/scripts/register_long_term_source_document.py
```

Inputs:

- `--source-request-id`
- `--title`
- `--source-url`
- `--document-type`
- `--source-name`
- optional `--local-path`
- optional `--summary`
- `--actor`

Writes:

- `core.raw_artifacts`
- `knowledge.obsidian_notes`
- `portfolio.long_term_source_documents`

Guardrails:

- `capital_action_allowed = false`
- `live_execution_allowed = false`
- no broker order, portfolio action, recommendation, or client instruction is produced.

## API And Dashboard

Added API route:

```text
POST /api/portfolio/long-term-source-documents/register
```

Added snapshot key:

```text
long_term_source_documents
```

Added AI Office UI controls:

- source request selector
- document type selector
- title field
- official URL field
- register source document action
- registered source documents list with provenance status and HTTP status

The dashboard form registers the source, then runs the satisfaction checker for that request.

## Verification

Compiled backend scripts:

```bash
python3 -m py_compile _ai_os_runtime/scripts/register_long_term_source_document.py _ai_os_runtime/api/ai_os_api_server.py
python3 -m py_compile _ai_os_runtime/scripts/check_long_term_source_satisfaction.py
```

Built frontend:

```bash
npm run build
```

Result:

```text
tsc && vite build
49 modules transformed
built in 271ms
```

Restarted live stack:

```bash
bash _ai_os_runtime/scripts/start_ai_office_live.sh
```

Result:

```text
http://127.0.0.1:8765/api/health
http://127.0.0.1:5177/
```

## Real Source Proof

Registered official Usha Martin FY 2024-25 annual report:

- Official annual reports page: `https://ushamartin.com/investor-relations/annual-reports`
- Official PDF: `https://ushamartin.com/public/upload/investorrelations/annual-report-d-2024-25.pdf`

Command:

```bash
python3 _ai_os_runtime/scripts/register_long_term_source_document.py --source-request-id 3 --title "Usha Martin Annual Report 2024-25" --source-url "https://ushamartin.com/public/upload/investorrelations/annual-report-d-2024-25.pdf" --document-type annual_report --source-name official_company_ir --summary "Official Usha Martin FY 2024-25 annual report from the company annual reports page." --actor "Filings and Transcript Analyst"
```

Result:

```json
{
  "source_document_id": 1,
  "source_request_id": 3,
  "symbol": "USHAMART",
  "document_type": "annual_report",
  "http_status": 200,
  "provenance_status": "verified",
  "raw_artifact_id": 134,
  "obsidian_note_id": 1535,
  "note_path": "ai memory/05 Filings and Transcripts/Long-Term Source Documents/request-3-ushamart-annual-report-36c769d4e7e5.md",
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

## Satisfaction Check Proof

API check:

```bash
curl -s -X POST http://127.0.0.1:8765/api/portfolio/long-term-source-requests/check -H 'Content-Type: application/json' -d '{"source_request_id":3,"actor":"Filings and Transcript Analyst"}'
```

Result:

```json
{
  "checked_count": 1,
  "satisfied_count": 1,
  "missing_count": 0,
  "results": [
    {
      "request_id": 3,
      "request_key": "lt-src-2-business-model-annual-report-or-investor-presentation",
      "symbol": "USHAMART",
      "check_status": "satisfied",
      "matched_source_count": 3,
      "status_after": "satisfied"
    }
  ],
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

Database proof:

```sql
SELECT jsonb_pretty(jsonb_build_object(
  'source_documents',(SELECT count(*) FROM portfolio.long_term_source_documents),
  'request_3_status',(SELECT status FROM portfolio.long_term_source_requests WHERE id=3),
  'request_3_matches',(SELECT matched_source_count FROM portfolio.long_term_source_requests WHERE id=3),
  'latest_check',(SELECT check_status FROM portfolio.long_term_source_request_checks WHERE source_request_id=3 ORDER BY checked_at DESC LIMIT 1)
));
```

Result:

```json
{
  "latest_check": "satisfied",
  "request_3_status": "satisfied",
  "source_documents": 1,
  "request_3_matches": 3
}
```

Snapshot proof:

- `long_term_source_documents` exists in `/api/snapshot`.
- document count: `1`
- request 3 status: `satisfied`
- latest check status: `satisfied`

## Important Fix

Updated `check_long_term_source_satisfaction.py` so explicit `--source-request-id` can re-audit already satisfied requests. Batch checks still process only queued/collecting/needs-review requests.

Reason: direct audit should verify evidence freshness; queue mode should avoid wasting cycles on already satisfied requests.

## Remaining Gaps

- USHAMART source requests 1 and 2 still need official company/exchange filing evidence.
- Business Model and Moat specialist outputs are still not complete research conclusions; they remain source-gated until all required sources are satisfied and the specialist assignments are rerun.
- The old timestamped source note from the first registration test remains indexed as provenance evidence. Future registrations now use deterministic note paths per request/source URL.

## Checklist Updated

Marked complete:

- Long-Term official source document registration workflow.
- Build Long-Term official source document registration workflow.

