# Special Situation Terms Extraction

Date: 2026-07-06
Status: implemented and verified on real buyback filing
Blueprint: [[AI Investment OS - Institutional Master Blueprint v4.0]]
Checklist: [[AI Investment OS - Institutional Build Checklist v4.0]]

## What Changed

- Added `_ai_os_runtime/postgres/init/050_special_situation_terms.sql`.
- Added `research.special_situation_terms`.
- Added `research.v_special_situation_terms`.
- Extended `research.v_special_situation_inbox` with linked structured terms.
- Added tool registry entry:
  - `ai_os_special_situation_terms`
- Updated `_ai_os_runtime/scripts/extract_filing_pdfs.py` to extract:
  - record date
  - meeting date
  - opening date
  - closing date
  - offer price
  - issue price
  - cash consideration
  - swap ratio
  - entitlement ratio
  - buyback size
  - aggregate amount
  - timeline snippets
  - condition snippets
- Added API snapshot key:
  - `special_situation_terms`
- Added AI Office dashboard panel:
  - Special Situation Terms
- Fixed an important classifier false positive:
  - ESOP/employee stock option allotments are now routine filings, not preferential allotments.
  - Existing Federal Bank ESOP false-positive event and inbox item were marked `superseded`.

## Real Source Evidence

Official NSE query for 2026-07-05 found real event filings:

- `ROLEXRINGS`: Buyback letter of offer.
- `ASTRAL`: Composite scheme of arrangement.
- `PIRAMALFIN`: Amalgamation/merger petition filing.

The system ingested a bounded real NSE window instead of fake data:

- `python3 _ai_os_runtime/scripts/collect_nse_bse_filings.py --source nse --from-date 2026-07-05 --to-date 2026-07-05 --limit 22`

Collector result:

- rows seen: `22`
- rows upserted: `22`
- event rows upserted: `22`
- inbox items created: `3`
- event counts:
  - `buyback = 1`
  - `scheme_arrangement = 2`
  - `routine_filing = 18`
  - `preferential_allotment = 1` before the ESOP correction

After ESOP correction:

- Federal Bank ESOP preferential event marked `superseded`.
- New Federal Bank routine event created.
- Special Situations inbox shows:
  - `ROLEXRINGS` buyback.
  - `ASTRAL` scheme of arrangement.
  - `ASTRAL` scheme of arrangement.

## Verified Buyback Extraction

Real filing:

- filing ID: `27`
- company: Rolex Rings Limited
- symbol: `ROLEXRINGS`
- event: `buyback`
- source PDF: NSE archive URL
- parser: `pypdf`
- page count: `63`
- extracted characters: `258,448`

Extracted structured terms:

- offer price: `Rs. 180`
- record date: `July 03, 2026`
- opening date: `July 09, 2026`
- closing date: `July 15, 2026`
- aggregate amount: `INR 1800.00 million`
- entitlement ratio: `26 Equity Share for every 327 Equity Shares`
- confidence: `0.95`
- status: `needs_review`

Database evidence:

- `research.special_situation_terms.id = 1`
- `filing_id = 27`
- `event_type = buyback`
- `symbol = ROLEXRINGS`
- `offer_price = Rs. 180`
- `special_situation_terms = 1`
- `special_situation_inbox = 3`
- snapshot issues: `0`

## Guardrails

- The system does not make a trade recommendation from the buyback filing.
- The extracted terms are marked `needs_review`.
- Special Situations Agent gets the work item; Risk/Charlie review remains required before any portfolio action.
- ESOP allotments are no longer treated as special situations.

## Still Open

- Add event memo generation for buybacks/schemes.
- Add arbitrage spread tracker.
- Add term extraction tests on:
  - merger/amalgamation filings,
  - demerger filings,
  - open offers,
  - delistings,
  - rights issues,
  - preferential issues that are not ESOPs.
- Add structured probability/downside model.
- Add committee routing for material event ideas.
