# Filing PDF Extraction Pipeline

Date: 2026-07-06
Status: implemented and verified foundation slice
Blueprint: [[AI Investment OS - Institutional Master Blueprint v4.0]]
Checklist: [[AI Investment OS - Institutional Build Checklist v4.0]]

## What Changed

- Added `_ai_os_runtime/postgres/init/049_filing_pdf_extraction_pipeline.sql`.
- Added `research.filing_pdf_extraction_runs`.
- Extended `research.corporate_filings` with:
  - `pdf_page_count`
  - `pdf_extracted_at`
  - `pdf_extraction_run_id`
  - `classification_payload`
- Added `research.v_filing_pdf_extraction_runs`.
- Rebuilt `research.v_corporate_filing_inbox` and `research.v_special_situation_inbox` to include extraction fields.
- Added tool registry entries:
  - `ai_os_extract_filing_pdf_text`
  - `ai_os_filing_pdf_extraction_runs`
- Added `_ai_os_runtime/scripts/extract_filing_pdfs.py`.
- Added API route:
  - `POST /api/research/filings/extract-pdfs`
- Added snapshot key:
  - `filing_pdf_extraction_runs`
- Added AI Office dashboard panel:
  - Filing PDF Extractor
- Updated the v4 checklist:
  - Filing PDF parser marked done.
  - NSE/BSE collector plus PDF extraction foundation marked done.
  - Special Situations inbox remains partial until non-routine event extraction is proven on a real event.

## Verified Evidence

- Database migration applied successfully after fixing view replacement order.
- Python compile passed for:
  - `_ai_os_runtime/scripts/extract_filing_pdfs.py`
  - `_ai_os_runtime/scripts/collect_nse_bse_filings.py`
  - `_ai_os_runtime/api/ai_os_api_server.py`
- React/Vite production build passed.
- Dry-run extraction on real NSE filing `filing_id = 1`:
  - source PDF: Minda Corporation NSE filing.
  - parser: `pypdf`.
  - page count: `2`.
  - extracted chars: `920`.
  - classifier result: `routine_filing`.
- Real extraction wrote:
  - `research.filing_pdf_extraction_runs.id = 1`
  - status `completed`
  - parser `pypdf`
  - page count `2`
  - extracted chars `920`
  - local PDF path `_ai_os_runtime/artifacts/filings/nse/2026-07-06/filing-1-e8b703427093.pdf`
  - text artifact `core.raw_artifacts.id = 100`
- Filing row updated:
  - `research.corporate_filings.extraction_status = extracted`
  - `pdf_page_count = 2`
  - `raw_artifact_id = 100`
- Live stack restarted successfully:
  - API health `ok = true`
  - UI served at `http://127.0.0.1:5177/`
  - snapshot issues `0`
  - snapshot `filing_pdf_extraction_runs = 1`
- API route dry-run passed after restart:
  - `POST /api/research/filings/extract-pdfs`
  - `filing_id = 1`
  - `ok = true`

## Current Interpretation

The Research Factory can now move from exchange announcement rows to actual PDF text extraction. The first verified filing was routine, so no Special Situations inbox item was created. That is correct behavior: the system should not manufacture event-driven ideas from routine compliance filings.

## Guardrails

- The extractor reads public filing PDFs and writes local artifacts on the external SSD.
- It does not place trades.
- It does not make investment recommendations.
- Keyword classification is deterministic and source-bound.
- Non-routine events can route to `Special Situations Agent`, but this remains partial until verified on actual event filings.

## Still Open

- Test extraction on real merger, demerger, buyback, open offer, delisting, rights issue, or preferential allotment filings.
- Add structured term extraction:
  - record date
  - swap ratio
  - cash consideration
  - offer price
  - timelines
  - conditions
  - regulatory approvals
- Add arbitrage spread tracker.
- Add generated special-situation memo.
- Add committee routing for material events.
