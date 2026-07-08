# Long-Term Thesis Workflow

Date: 2026-07-06
Status: schema, memo workflow, API, and dashboard foundation done and verified
Owner: Long-Term Portfolio Manager / Research Analyst / Valuation Agent

## What Was Added

- Extended `portfolio.holding_theses` with institutional long-term thesis fields:
  - thesis title and version
  - owner agent
  - purpose/book link
  - business model and industry structure fields
  - moat, management, governance, capital allocation, and financial quality scores
  - forensic accounting flags
  - valuation status and scenario values
  - expected CAGR
  - Monte Carlo payload
  - thesis killers
  - exit criteria
  - quarterly review schedule fields
- Added version history:
  - `portfolio.holding_thesis_versions`
- Added research checklist tracker:
  - `portfolio.holding_thesis_checklists`
- Added valuation model tracker:
  - `portfolio.holding_valuation_models`
- Added review schedule:
  - `portfolio.holding_review_schedule`
- Added live read model:
  - `portfolio.v_long_term_thesis_control`
- Added memo generator:
  - `_ai_os_runtime/scripts/generate_long_term_thesis_memo.py`
- Added API route:
  - `POST /api/portfolio/long-term-thesis/memo`
- Added live snapshot key:
  - `long_term_theses`
- Added AI Office dashboard panel:
  - Long-Term Thesis Control
- Added tool registry entry:
  - `ai_os_generate_long_term_thesis_memo`

## What It Does

The workflow creates a durable long-term thesis control record from real long-term book exposure. It does not create a recommendation. It creates the research container, evidence links, checklist/valuation work queues, review schedule, task, inbox item, and Obsidian memo that specialist agents need before Charlie or Risk can make a decision.

## Verification Evidence

- Migration applied successfully:
  - `_ai_os_runtime/postgres/init/058_long_term_thesis_schema.sql`
- Python compile passed:
  - `_ai_os_runtime/scripts/generate_long_term_thesis_memo.py`
  - `_ai_os_runtime/api/ai_os_api_server.py`
- Frontend build passed:
  - `npm run build` in `_ai_os_runtime/ai-office-ui`
- Live stack restarted successfully:
  - API
  - agent daemon
  - UI
- Direct script run created thesis id `1`:
  - Symbol: `LIQUIDBEES`
  - Long-term gross exposure: `2554727.55`
  - Checklist count: `8`
  - Valuation model count: `8`
  - Note: `ai memory/02 Portfolio/Long-Term Theses/20260706T065413Z-liquidbees-long-term-thesis.md`
- API route created thesis id `2`:
  - Symbol: `USHAMART`
  - Exchange: `NSE`
  - Clients: `Naval`, `Tushit`
  - Long-term gross exposure: `1899270.00`
  - Checklist count: `8`
  - Valuation model count: `8`
  - Note: `ai memory/02 Portfolio/Long-Term Theses/20260706T065716Z-ushamart-long-term-thesis.md`
- Inbox tasks created:
  - `Research queue: LIQUIDBEES long-term thesis`
  - `Research queue: USHAMART long-term thesis`
- `GET /api/snapshot` returns `long_term_theses` with both generated rows.
- UI served successfully at:
  - `http://127.0.0.1:5177/`

## Current State

Done:

- Thesis schema.
- Version history.
- Thesis memo template.
- Thesis killer structure.
- Exit criteria field linked to the thesis.
- Quarterly review schedule.
- Long-Term Thesis Control dashboard.
- Agent/task/inbox routing for research completion.

Partially done:

- Business model, industry, moat, management, governance, capital allocation, financial quality, and forensic accounting modules now exist as tracked checklist rows, but their source-backed analysis is still open.
- DCF, reverse DCF, sum-of-parts, peer comparison, historical valuation, bull/base/bear, expected CAGR, and Monte Carlo modules now exist as tracked valuation rows, but their calculations are still open.

## Still Open

- Fill source-backed checklist findings for priority holdings.
- Build valuation calculators that write real assumptions and outputs into `portfolio.holding_valuation_models`.
- Add thesis drift alerts from filings, news, and price/valuation changes.
- Connect completed thesis reviews into Charlie/Risk committee decisions.
