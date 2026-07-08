# Long-Term Investment Committee Workflow

Date: 2026-07-06
Owner: Long-Term Office
Status: Live foundation complete

## What Was Built

- Added `portfolio.long_term_committee_reviews`.
- Added `portfolio.long_term_committee_decisions`.
- Added `portfolio.v_long_term_committee_queue`.
- Added database functions:
  - `portfolio.open_long_term_committee_review`
  - `portfolio.resolve_long_term_committee_decision`
- Added tool registry entries:
  - `ai_os_open_long_term_committee_review`
  - `ai_os_generate_long_term_committee_memo`
  - `ai_os_resolve_long_term_committee_decision`
- Added memo generator:
  - `_ai_os_runtime/scripts/generate_long_term_committee_memo.py`
- Added API routes:
  - `POST /api/portfolio/long-term-committee/open`
  - `POST /api/portfolio/long-term-committee/memo`
  - `POST /api/portfolio/long-term-committee/decision`
- Added live snapshot key:
  - `long_term_committee_queue`
- Extended the AI Office Long-Term Thesis Control panel with:
  - `Committee` button per thesis,
  - committee queue rows,
  - memo generation action,
  - no-trade decisions: research, monitor, hold, reject.

## Guardrail

This workflow does not authorize buy, add, trim, sell, hedge, broker order, or live strategy action.

Every review and decision stores:

- `capital_action_allowed = false`
- `live_execution_allowed = false`

Capital action must be a separate future workflow with human approval and Risk Office review.

## Live Proof

- Python compile passed:
  - `_ai_os_runtime/scripts/generate_long_term_committee_memo.py`
  - `_ai_os_runtime/api/ai_os_api_server.py`
- UI production build passed: `npm run build`.
- Migration applied:
  - `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/060_long_term_committee_workflow.sql`
- AI OS services restarted with `_ai_os_runtime/scripts/start_ai_office_live.sh`.
- API health returned `ok: true`.
- TradingView CDP remained available on port `9222`.

## Real Committee Proof

### USHAMART

- Opened committee review id `1`.
- Source gaps found: `3`.
- Recommended decision: `research_more`.
- Memo generated:
  - `ai memory/02 Portfolio/Long-Term Committee Reviews/20260706T072317Z-ushamart-committee-memo.md`
- Charlie decision:
  - `research_more`
  - approval status `rejected`
  - thesis status `under_research`
  - thesis decision status `committee_research_required`
  - capital action `false`
  - live execution `false`

### LIQUIDBEES

- Opened committee review through HTTP route.
- Review id `2`.
- Memo generated through HTTP route:
  - `ai memory/02 Portfolio/Long-Term Committee Reviews/20260706T075641Z-liquidbees-committee-memo.md`
- Decision resolved through HTTP route:
  - `research_more`
  - capital action `false`
  - live execution `false`

## Snapshot Proof

The live API snapshot returned committee queue rows:

- `LIQUIDBEES`: `research_required`, memo `generated`, decision `final`, capital action `false`, live execution `false`
- `USHAMART`: `research_required`, memo `generated`, decision `final`, capital action `false`, live execution `false`

The DB decision table confirmed:

- decision id `1`, thesis `2`, `research_more`, capital action `false`, live execution `false`, decided by `Charlie Munger`
- decision id `2`, thesis `1`, `research_more`, capital action `false`, live execution `false`, decided by `Charlie Munger`

## Remaining Gaps

- Specialist analyst workflows still need to fill actual company, industry, management, financial, forensic, valuation, bear-case, and risk modules.
- Committee can currently make no-trade thesis-state decisions only.
- Separate future workflows are needed for buy/add/trim/sell approvals.
- Full valuation calculators and long-term Monte Carlo remain open.
- Annual report/transcript ingestion remains required before high-conviction thesis approval.
