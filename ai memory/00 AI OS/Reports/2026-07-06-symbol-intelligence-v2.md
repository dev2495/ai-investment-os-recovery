# Symbol Intelligence v2 - Warehouse, API, And Dashboard Evidence

Date: 2026-07-06
Status: verified foundation upgrade, not yet the final full-page product

## What Changed

Symbol Intelligence was upgraded from a thin exposure rollup into an evidence-aware decision surface.

Implemented warehouse view:

- `_ai_os_runtime/postgres/init/068_symbol_intelligence_v2.sql`
- Replaced `portfolio.v_symbol_intelligence` while preserving the older exposure columns.
- Added thesis, valuation, Monte Carlo, committee, filing, news, signal, strategy, decision flag, readiness, and next-action fields.
- Updated `core.control_plane_modules` metadata for Symbol Intelligence.

Implemented API exposure:

- `_ai_os_runtime/api/ai_os_api_server.py`
- Synced into the launchd service copy:
  - `/Users/devarshthakkar/Library/Application Support/AIOS/service/api/ai_os_api_server.py`
- `/api/snapshot` now returns enriched `symbol_intelligence` rows.
- Chat/context queries now include decision readiness, next action, Monte Carlo, and committee status.

Implemented dashboard panel upgrade:

- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`
- The AI Office dashboard now shows each symbol row with:
  - recommended next action
  - decision readiness
  - book/conflict/gap context
  - Monte Carlo status and median CAGR
  - committee status
  - filing/news counts
  - signal/strategy counts
  - decision flags

## Live Verification

API health check:

```json
{
  "ok": true,
  "runtime_root": "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime",
  "tradingview_cdp": {
    "available": true,
    "port": 9222,
    "browser": "Chrome/140.0.7339.133"
  }
}
```

Database view count:

```json
{
  "rows": 69,
  "with_thesis": 3,
  "with_monte_carlo": 2,
  "readiness": {
    "research_required": 66,
    "valuation_work_required": 1,
    "committee_review_required": 2
  }
}
```

Live API Usha Martin evidence:

```json
[
  {
    "client_name": "Naval",
    "symbol": "USHAMART",
    "gross_exposure": 1406720.0,
    "decision_readiness": "committee_review_required",
    "recommended_next_action": "Committee should review Monte Carlo assumptions before capital decision.",
    "holding_thesis_id": 2,
    "latest_monte_carlo_run_id": 3,
    "monte_carlo_status": "needs_review",
    "monte_carlo_median_cagr": "-0.0412",
    "monte_carlo_negative_cagr_probability": "0.753",
    "latest_committee_status": "research_required",
    "recommended_decision": "research_more",
    "filing_count": 0,
    "news_count": 0,
    "symbol_strategy_candidate_count": 0,
    "broad_strategy_candidate_count": 10,
    "decision_flags": [
      "assignment_or_thesis_gap",
      "monte_carlo_needs_review"
    ]
  },
  {
    "client_name": "Tushit",
    "symbol": "USHAMART",
    "gross_exposure": 492550.0,
    "decision_readiness": "committee_review_required",
    "recommended_next_action": "Committee should review Monte Carlo assumptions before capital decision.",
    "holding_thesis_id": 2,
    "latest_monte_carlo_run_id": 3,
    "monte_carlo_status": "needs_review",
    "monte_carlo_median_cagr": "-0.0412",
    "monte_carlo_negative_cagr_probability": "0.753",
    "latest_committee_status": "research_required",
    "recommended_decision": "research_more",
    "filing_count": 0,
    "news_count": 0,
    "symbol_strategy_candidate_count": 0,
    "broad_strategy_candidate_count": 10,
    "decision_flags": [
      "assignment_or_thesis_gap",
      "monte_carlo_needs_review"
    ]
  }
]
```

Build and syntax checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py
npm run build
```

Both passed.

Live service:

```text
Python 82040 LISTEN 127.0.0.1:8765
```

## Checklist Updates

Marked verified:

- Add current trades by book into symbol intelligence.
- Add thesis links into symbol intelligence.
- Add quant signal links into symbol intelligence.
- Build Symbol Intelligence v2 warehouse/API/dashboard panel.

Marked partial:

- Latest news/filing/tasks/committee notes into symbol intelligence.
- Full Symbol Intelligence page.
- Symbol Intelligence dashboard.
- Immediate sprint Symbol Intelligence page item.

## Why Partial Remains

This is not yet the final Bloomberg-grade Symbol Intelligence page.

Remaining gaps:

- Dedicated full-page Symbol Intelligence UI, separate from the current dashboard panel.
- Explicit catalyst object links, not just filing/news/proxy signals.
- Explicit task links and agent assignment links.
- Trading setup links for active discretionary trades.
- Rich drill-down into thesis, Monte Carlo assumptions, committee memo, filings, news, strategies, and client exposure.
- Production-grade visual layout with filters, tabs, and action buttons.

## Next Recommended Build Step

Build TradingView production chart actions next, because Symbol Intelligence now has enough symbol-level context to ask TradingView to open charts, compare symbols, create option/straddle layouts, and attach chart artifacts back to the intelligence record.

After that, return to the dedicated Symbol Intelligence page and connect:

- chart actions
- catalyst/task links
- full thesis drill-down
- committee decision controls
- client/book exposure breakdowns
