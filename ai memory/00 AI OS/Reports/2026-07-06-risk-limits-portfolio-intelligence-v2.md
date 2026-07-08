# Risk Limits And Portfolio Intelligence v2 - 2026-07-06

## Outcome

The AI OS now has a live portfolio risk limit evaluation layer and Portfolio Intelligence v2 dashboard surface. Risk Agent can evaluate current book/client/symbol/allocation risk, materialize breaches into `risk.events`, and inspect the same data through API, MCP, and the AI Office dashboard.

## Implemented

- Added migration `_ai_os_runtime/postgres/init/077_risk_limits_portfolio_intelligence_v2.sql`.
- Added risk limit rows:
  - `long_term.exit_criteria_zero`
  - `long_term.review_due_zero`
- Added read models:
  - `risk.v_portfolio_risk_limit_checks`
  - `risk.v_portfolio_risk_dashboard_summary`
  - `books.v_portfolio_intelligence_v2`
- Added function:
  - `risk.refresh_portfolio_risk_events(actor)`
- Added tool registry rows and MCP tools:
  - `ai_os_portfolio_risk_limit_checks`
  - `ai_os_refresh_portfolio_risk_events`
  - `ai_os_portfolio_intelligence_v2`
- Added API snapshot keys:
  - `risk_limit_checks`
  - `risk_dashboard_summary`
  - `portfolio_intelligence_v2`
- Added API route:
  - `POST /api/risk/portfolio/refresh-events`
- Added AI Office panels:
  - `Portfolio Intelligence v2`
  - live risk checks inside `Book Risk And Assignment Gaps`
- Added dashboard action:
  - `Refresh events`, which materializes breached checks into `risk.events`.

## Live Risk Evidence

Evaluated checks:

```text
risk_limit_checks = 108
risk_limit_breaches = 4
risk_limit_warnings = 4
critical_breaches = 1
portfolio_assignment_gaps = 213
```

Current breach examples:

```text
No Active Thesis: 71 open Long-Term thesis gaps, critical
Exit Criteria Must Exist: 71 open Long-Term exit criteria gaps, high
No Overdue Or Soon Reviews: 71 open Long-Term review gaps, medium
Single Name Max: Naval / USHAMART = 28.2547% vs 25% threshold, high
```

Risk event refresh:

```text
POST /api/risk/portfolio/refresh-events
inserted_events = 4
breach_count = 4
warning_count = 4
live_execution_allowed = false
```

Materialized risk events:

```text
risk.events id 36 = Single Name Max breach
risk.events id 37 = No Active Thesis breach
risk.events id 38 = Exit Criteria Must Exist breach
risk.events id 39 = No Overdue Or Soon Reviews breach
```

Portfolio Intelligence:

```text
portfolio_intelligence_v2 rows in API snapshot = 73
MCP portfolio top-symbol rows = 25
gross_book_exposure = 23,470,281.79
net_book_exposure = 23,470,281.79
book_positions = 71
booked_clients = 3
```

## Verification

Build checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm run build in _ai_os_runtime/ai-office-ui
```

API smoke:

```text
GET /api/health -> ok=true
GET /api/snapshot -> issues=[]
risk_dashboard_summary rows = 6
risk_limit_checks rows = 108
portfolio_intelligence_v2 rows = 73
visible breaches = 4
```

MCP smoke:

```text
tools/list contains ai_os_portfolio_risk_limit_checks = true
tools/list contains ai_os_refresh_portfolio_risk_events = true
tools/list contains ai_os_portfolio_intelligence_v2 = true
ai_os_portfolio_risk_limit_checks breach rows = 4
ai_os_portfolio_intelligence_v2 summary rows = 73
ai_os_portfolio_intelligence_v2 top_symbols rows = 25
ai_os_refresh_portfolio_risk_events breach_count = 4
```

Runtime:

```text
API: http://127.0.0.1:8765/api/health
UI:  http://127.0.0.1:5177/
```

## Remaining Boundary

This completes the first live risk limit dashboard and Portfolio Intelligence v2 surface. It does not yet complete:

- Liquidity risk engine.
- VaR engine.
- Expected shortfall engine.
- Stress test engine.
- Correlation/factor concentration engine.
- Crypto/commodity risk limits.
- Full capital allocation optimizer.
- Human-approved rebalance workflow.

This slice does not authorize live trading, broker order placement, or autonomous capital action.
