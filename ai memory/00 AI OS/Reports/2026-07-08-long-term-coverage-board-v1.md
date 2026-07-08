# Long-Term Coverage Board v1

Generated: 2026-07-08

## Outcome

The Long-Term Investing Office now has a live coverage board that turns every material Long-Term book exposure into explicit research work.

This closes the operational gap between having long-term thesis/checklist/valuation/Monte Carlo machinery and actually knowing which holdings still need thesis containers, checklist evidence, valuation work, Monte Carlo, exit criteria, or committee readiness.

No capital action, broker action, or live execution path was introduced.

## Implemented

- Database migration: `_ai_os_runtime/postgres/init/109_long_term_coverage_board_v1.sql`
- Table:
  - `portfolio.long_term_coverage_queue`
- Function:
  - `portfolio.sync_long_term_coverage_queue(...)`
- Views:
  - `portfolio.v_long_term_coverage_candidates`
  - `portfolio.v_long_term_coverage_queue`
  - `portfolio.v_long_term_coverage_summary`
- API snapshot keys:
  - `long_term_coverage_summary`
  - `long_term_coverage_queue`
- API route:
  - `POST /api/portfolio/long-term-coverage/sync`
- MCP tools:
  - `ai_os_sync_long_term_coverage_queue`
  - `ai_os_long_term_coverage_queue`
  - `ai_os_long_term_coverage_summary`
- MCP tool group:
  - `long_term_office_operator`
- AI Office UI:
  - `Coverage board` section inside `Long-Term Thesis Control`
  - summary strip for coverage counts
  - prioritized queue rows by exposure and gap severity
  - `Sync coverage` action
  - `Memo` action for missing thesis containers

## Live Data Result

The first sync used real `portfolio.v_long_term_thesis_control` and existing long-term evidence tables.

Sync result:

| Metric | Value |
| --- | ---: |
| candidate_count | 52 |
| synced_count | 52 |
| tasks_created | 52 |
| inbox_items_created | 52 |
| open_queue_count | 52 |

Current coverage summary after verification:

| Metric | Value |
| --- | ---: |
| candidate_gap_count | 52 |
| open_coverage_items | 52 |
| critical_coverage_items | 46 |
| coverage_symbols | 45 |
| missing_thesis_symbols | 43 |
| coverage_tasks | 52 |

Top live queue examples:

| Symbol | Gap | Severity | Owner | Exposure |
| --- | --- | --- | --- | ---: |
| LIQUIDBEES | checklist_incomplete | critical | Long-Term Portfolio Manager | 2,554,727.55 |
| SJS | missing_thesis_container | critical | Long-Term Portfolio Manager | 2,268,586.00 |
| USHAMART | checklist_incomplete | critical | Long-Term Portfolio Manager | 1,899,270.00 |
| LAURUSLABS | missing_thesis_container | critical | Long-Term Portfolio Manager | 1,606,514.00 |

## Verification

- Migration applied successfully against live SSD-backed Postgres.
- Direct SQL sync succeeded:
  - `SELECT portfolio.sync_long_term_coverage_queue(100, true, 'Charlie Munger')`
- API sync succeeded:
  - `POST /api/portfolio/long-term-coverage/sync`
- API snapshot includes:
  - 6 `long_term_coverage_summary` rows
  - 52 `long_term_coverage_queue` rows
- MCP import registration confirmed:
  - `ai_os_sync_long_term_coverage_queue`
  - `ai_os_long_term_coverage_queue`
  - `ai_os_long_term_coverage_summary`
- Python compile passed:
  - `api/ai_os_api_server.py`
  - `mcp_server/ai_os_mcp_server.py`
- React build passed:
  - `npm run build`
- Live office restarted:
  - API: `http://127.0.0.1:8765/api/health`
  - UI: `http://127.0.0.1:5177/`

## Safety Position

- The board creates research work only.
- The board does not approve buy, hold, add, trim, or sell decisions.
- The board does not place broker orders.
- Generated tasks are routed to Long-Term Portfolio Manager, Valuation Agent, or Quant Risk Analyst.
- Committee readiness remains separate from execution approval.

## Current Limits

- The board identifies and routes missing work; it does not complete research automatically.
- 43 symbols still need thesis containers.
- Checklist and valuation rows exist, but many rows remain incomplete.
- Client-level long-term suitability review is still open.
- Full human buy/hold/add/trim/sell decision UI is still open.
- Annual report/transcript ingestion must continue to improve before high-conviction thesis approval.

## Next Recommended Slice

Build Client Folio dashboard v1:

- per-client exposure,
- holdings by book,
- thesis readiness by client,
- coverage gaps by client,
- risk concentration,
- latest tasks and committee status,
- manual update path for new clients and holdings.
