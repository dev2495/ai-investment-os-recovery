# Special Situation Memo Workflow

Date: 2026-07-06
Status: done and verified
Owner: Special Situations Agent

## What Was Added

- Added `research.special_situation_memos` as the durable memo/routing table.
- Added `research.v_special_situation_memos` for dashboard/API reads.
- Extended `research.v_special_situation_inbox` with memo path, memo status, and approval status.
- Added MCP/tool registry rows:
  - `ai_os_generate_special_situation_memo`
  - `ai_os_special_situation_memos`
- Added deterministic memo generator:
  - `_ai_os_runtime/scripts/generate_special_situation_memo.py`
- Added API route:
  - `POST /api/research/special-situations/memo`
- Added API snapshot key:
  - `special_situation_memos`
- Added dashboard support:
  - Memo button on Special Situation Terms rows.
  - Special Situation Memos panel with memo, approval, task, and note status.

## Real Verification Case

Real source row:

- `research.special_situation_terms.id = 1`
- Symbol: `ROLEXRINGS`
- Event type: `buyback`
- Filing id: `27`
- Source: NSE PDF attachment
- Offer price: `Rs. 180`
- Record date: `July 03, 2026`
- Opening date: `July 09, 2026`
- Closing date: `July 15, 2026`
- Aggregate amount: `INR 1800.00 million`
- Entitlement ratio: `26 Equity Share for every 327 Equity Shares`

Generated memo:

- Memo id: `1`
- Task id: `23`
- Approval id: `6`
- Inbox id: `64`
- Memo status: `routed_for_review`
- Approval owner: `Charlie Munger`
- Approval status: `pending`
- Note path: `ai memory/05 Filings and Transcripts/Special Situations/20260706T055913Z-special-situation-1-rolexrings-buyback.md`

## Guardrails

- The memo is explicitly research routing only.
- It does not authorize a paper trade, live trade, alert-to-execution, or client-facing recommendation.
- Allowed decisions are `reject`, `monitor`, `research_more`, or `committee_review`.
- Charlie Munger/Risk review remains required before action.

## Fixes Made During Verification

- Buyback entitlement was initially displayed as both `Swap Ratio` and `Entitlement Ratio`.
- Fixed `_ai_os_runtime/scripts/extract_filing_pdfs.py` so non-merger/scheme events do not populate `swap_ratio`.
- Corrected the current ROLEXRINGS buyback row so `swap_ratio` is null and `entitlement_ratio` remains intact.
- Fixed memo generator idempotency so reruns reuse the existing Obsidian note and existing routing records.
- Fixed rerun status so existing routed memos remain `routed_for_review`.

## Verification Evidence

- `python3 -m py_compile _ai_os_runtime/scripts/generate_special_situation_memo.py _ai_os_runtime/scripts/extract_filing_pdfs.py _ai_os_runtime/api/ai_os_api_server.py` passed.
- `npm run build` in `_ai_os_runtime/ai-office-ui` passed.
- Migration `postgres/init/051_special_situation_memo_workflow.sql` applied successfully.
- Direct generator run returned memo id `1`, task id `23`, approval id `6`.
- `research.v_special_situation_memos` returned the ROLEXRINGS memo with `memo_status = routed_for_review`.
- `agent.tasks` row `23` exists for Special Situations Agent.
- `agent.approvals` row `6` exists for Charlie Munger with status `pending`.
- `agent.inbox_items` row `64` exists for Charlie Munger.
- `knowledge.obsidian_notes` indexed the memo note as `special_situation_memo`.
- API health returned `ok = true`.
- API snapshot returned `special_situation_memos` with one memo and `issues = 0`.
- `POST /api/research/special-situations/memo` returned the existing memo/routing IDs.
- UI served successfully at `http://127.0.0.1:5177/`.

## Still Open

- Add arbitrage spread tracker for buybacks, open offers, rights issues, mergers, and demergers.
- Add committee decision resolver for special situation memos.
- Add market price/liquidity/tax/acceptance-ratio scenario calculations.
- Add event calendar reminders after approval.
- Add source freshness scheduling for NSE/BSE collectors.
