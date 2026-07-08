# Long-Term Research Packet And Update Workflow

Date: 2026-07-06
Owner: Long-Term Office
Status: Live foundation complete

## What Was Built

- Added `portfolio.holding_thesis_research_updates` as the audit ledger for long-term packet, checklist, and valuation updates.
- Added read models:
  - `portfolio.v_long_term_thesis_checklists`
  - `portfolio.v_long_term_valuation_models`
  - `portfolio.v_long_term_research_updates`
- Registered tools:
  - `ai_os_generate_long_term_research_packet`
  - `ai_os_update_long_term_thesis_checklist`
  - `ai_os_update_long_term_valuation_model`
- Added `_ai_os_runtime/scripts/manage_long_term_research.py`.
- Added API routes:
  - `POST /api/portfolio/long-term-thesis/research-packet`
  - `POST /api/portfolio/long-term-thesis/checklist`
  - `POST /api/portfolio/long-term-thesis/valuation`
- Added AI Office snapshot keys:
  - `long_term_thesis_checklists`
  - `long_term_valuation_models`
  - `long_term_research_updates`
- Extended the Long-Term Thesis Control dashboard with:
  - research packet button per existing thesis,
  - open checklist rows,
  - valuation module rows,
  - research update ledger.

## Live Proof

- Migration applied: `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/059_long_term_research_update_workflow.sql`.
- Python compile passed:
  - `_ai_os_runtime/scripts/manage_long_term_research.py`
  - `_ai_os_runtime/api/ai_os_api_server.py`
- UI production build passed: `npm run build` in `_ai_os_runtime/ai-office-ui`.
- AI OS services restarted with `_ai_os_runtime/scripts/start_ai_office_live.sh`.
- API health returned `ok: true`.
- TradingView CDP remained available on port `9222`.

## Real Workflow Proof

### USHAMART

- Generated research packet:
  - `ai memory/02 Portfolio/Long-Term Research Packets/20260706T071353Z-ushamart-research-packet.md`
  - source summary: positions `2`, quotes `1`, filings `0`, notes `2`
- Updated checklist:
  - thesis id `2`
  - checklist `business_model`
  - status `source_required`
  - reason: position and quote evidence exist, but company filing evidence is missing.
- Updated valuation:
  - thesis id `2`
  - model `dcf`
  - status `source_required`
  - reason: audited financials, cash-flow history, growth/margin assumptions, and terminal assumptions are required before completion.

### LIQUIDBEES

- API generated research packet:
  - `ai memory/02 Portfolio/Long-Term Research Packets/20260706T071510Z-liquidbees-research-packet.md`
  - source summary: positions `1`, quotes `1`, filings `0`, notes `1`
- API updated checklist:
  - thesis id `1`
  - checklist `business_model`
  - status `source_required`
- API updated valuation:
  - thesis id `1`
  - model `dcf`
  - status `source_required`
  - guardrail: LIQUIDBEES needs a treasury/liquid ETF framework, not a fabricated DCF.

## Snapshot Proof

Live API snapshot returned:

- `long_term_theses`: `46`
- `long_term_thesis_checklists`: `16`
- `long_term_valuation_models`: `16`
- `long_term_research_updates`: `8`

Latest research update rows included:

- `LIQUIDBEES` valuation update, `source_required`
- `LIQUIDBEES` checklist update, `source_required`
- `LIQUIDBEES` research packet, `evidence_packet_created`
- `USHAMART` valuation update, `source_required`
- `USHAMART` checklist update, `source_required`

## Guardrails

- The workflow does not create buy, sell, add, trim, hedge, or live-trading recommendations.
- It does not fabricate scores, fair values, or expected CAGR.
- It can mark work as `source_required` when evidence is incomplete.
- It creates follow-up tasks and Charlie inbox items for specialist routing.

## Remaining Gaps

- Company filing coverage is still missing for the tested thesis packets.
- Annual report/transcript ingestion is still needed before complete long-term research.
- Full valuation calculators are still open.
- Long-Term Investment Committee workflow is still open.
- Bear Case Agent, Risk Agent, and Portfolio Fit Agent workflows still need implementation.
- Dashboard edit forms for checklist/valuation updates are not yet built; API routes are live.
