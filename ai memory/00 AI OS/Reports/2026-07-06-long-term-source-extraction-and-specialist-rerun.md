# Long-Term Source Extraction And Specialist Rerun

Date: 2026-07-06
Owner: Filings and Transcript Analyst / Company Analyst
Status: Done and verified

## What Changed

Added source-document text extraction for registered Long-Term source documents, exposed it through the API/dashboard snapshot, and reran the USHAMART Business Model and Moat specialist outputs using extracted annual-report text.

## Warehouse

Added:

- `portfolio.long_term_source_document_extractions`
- `portfolio.v_long_term_source_document_extractions`
- tool registry entry `ai_os_extract_long_term_source_document`

Migration:

```bash
python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/066_long_term_source_document_extraction.sql
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

## API And Dashboard

Added API route:

```text
POST /api/portfolio/long-term-source-documents/extract
```

Added snapshot key:

```text
long_term_source_document_extractions
```

Added dashboard actions:

- Extract button on registered source documents.
- Source extractions list showing parser, page count, and extracted character count.

## Extraction Proof

Source document:

- Usha Martin Annual Report 2024-25
- URL: `https://ushamartin.com/public/upload/investorrelations/annual-report-d-2024-25.pdf`
- Source document id: `1`

Command:

```bash
python3 _ai_os_runtime/scripts/extract_long_term_source_document.py --source-document-id 1 --actor "Filings and Transcript Analyst"
```

HTTP endpoint proof:

```bash
curl -s -X POST http://127.0.0.1:8765/api/portfolio/long-term-source-documents/extract -H 'Content-Type: application/json' -d '{"source_document_id":1,"actor":"Filings and Transcript Analyst"}'
```

Result:

```json
{
  "extraction_id": 1,
  "source_document_id": 1,
  "symbol": "USHAMART",
  "document_type": "annual_report",
  "page_count": 172,
  "extracted_chars": 1020683,
  "raw_artifact_id": 136,
  "snippet_count": 8,
  "local_pdf_path": "_ai_os_runtime/artifacts/source_documents/long_term/source-document-1-ushamart-36c769d4e7e5.pdf",
  "local_text_path": "_ai_os_runtime/artifacts/source_documents/long_term/source-document-1-ushamart-36c769d4e7e5.txt",
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

The PDF and extracted text are stored under `_ai_os_runtime/artifacts/source_documents/long_term` on the external SSD runtime.

## Specialist Rerun Proof

Reran:

```bash
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 1 --actor "Company Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 2 --actor "Company Analyst"
```

Results:

- Business Model output: `source_ready`, `needs_review`, no missing sources.
- Moat Scorecard output: `source_ready`, `needs_review`, no missing sources.
- Both outputs include one source document and one source extraction in metrics.
- Both outputs include snippets from the annual report text.

Latest output notes:

- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090155Z-ushamart-business-model.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090155Z-ushamart-moat-scorecard.md`

Database proof:

```json
{
  "extractions": [
    {
      "id": 1,
      "symbol": "USHAMART",
      "page_count": 172,
      "extracted_chars": 1020683,
      "raw_artifact_id": 136,
      "extraction_status": "extracted",
      "source_document_id": 1
    }
  ],
  "outputs": [
    {
      "module_key": "business_model",
      "output_status": "needs_review",
      "source_status": "source_ready",
      "metrics": {
        "source_documents": 1,
        "source_extractions": 1,
        "missing_source_count": 0
      }
    },
    {
      "module_key": "moat_scorecard",
      "output_status": "needs_review",
      "source_status": "source_ready",
      "metrics": {
        "source_documents": 1,
        "source_extractions": 1,
        "missing_source_count": 0
      }
    }
  ]
}
```

## Build Verification

Compiled:

```bash
python3 -m py_compile _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/scripts/extract_long_term_source_document.py
```

Built UI:

```bash
npm run build
```

Result:

```text
tsc && vite build
49 modules transformed
built in 273ms
```

Restarted stack:

```bash
bash _ai_os_runtime/scripts/start_ai_office_live.sh
```

Result:

```text
http://127.0.0.1:8765/api/health
http://127.0.0.1:5177/
```

## Important Fix

The first rerun failed twice with:

```text
name 'source_extractions' is not defined
```

Per the project rule, this was treated as a repeated error. The fix was to bind `source_extractions = context["source_extractions"]` inside `build_analysis()` before using it in metrics and evidence.

## Remaining Gaps

- Business Model and Moat outputs are source-ready and evidence-backed, but still need deeper structured scoring logic before they can be marked complete.
- The specialist worker currently includes snippets and counts; next step is to turn extracted annual-report text into structured checklist answers, scores, assumptions, and bear-case questions.
- `research.corporate_filings` is still empty for USHAMART. The official source-document path is working, but the exchange/company filing collector should also ingest this document into the filings inbox for unified filing history.

## Checklist Updated

Marked complete:

- Long-Term source document text extraction workflow.
- Build Long-Term source document text extraction workflow.

