# Symbol Intelligence v2

Date: 2026-07-07
Blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Owner: Portfolio Office
Runtime operator: Jarvis
Status: live and verified

## Outcome

Symbol Intelligence v2 is now live as the main per-instrument decision surface.

It combines:

- multi-book exposure,
- client-symbol exposure,
- long-term thesis state,
- Monte Carlo state,
- committee evidence,
- position remediation tasks,
- inbox/task links,
- risk breaches and warnings,
- cross-book coordination questions,
- latest filing/news fields,
- strategy candidates and dossiers,
- v2 decision flags,
- v2 decision state,
- recommended next action,
- a structured decision packet for Charlie/Jarvis.

This moves the OS closer to the "Bloomberg but smarter" goal: a symbol is no longer just a holding row. It is a decision object with books, evidence, risk, research, tasks, and agent actions attached.

## Runtime Objects

Migration:

- `_ai_os_runtime/postgres/init/105_symbol_intelligence_v2.sql`

Warehouse views:

- `portfolio.v_symbol_intelligence_v2`
- `portfolio.v_symbol_intelligence_v2_summary`

API snapshot keys:

- `symbol_intelligence_v2`
- `symbol_intelligence_v2_summary`

MCP tools:

- `ai_os_symbol_intelligence_v2`
- `ai_os_symbol_intelligence_v2_summary`

AI Office UI:

- `Symbol Intelligence v2`
- v2 summary metrics
- v2 decision state
- critical remediation count
- risk breach count
- cross-book coordination count
- remediation task count
- pending committee count
- strategy dossier count
- TradingView chart/snapshot buttons remain in the same panel

## Live Coverage

Current v2 summary:

| Metric | Value |
| --- | ---: |
| symbol_rows | 69 |
| symbols | 45 |
| critical_remediation_rows | 69 |
| risk_blocked_rows | 1 |
| committee_pending_rows | 0 |
| strategy_linked_rows | 1 |

Top live decision example:

- Client: `Naval`
- Symbol: `USHAMART`
- v2 decision state: `risk_blocked`
- v2 flags: `risk_breach`, `critical_position_remediation`
- Net exposure: INR `1,406,720`
- Risk breach: `USHAMART is 28.25% of Long-Term Investing for Naval`
- Remediation tasks: `2`
- Committee evidence: `Long-term committee decision: USHAMART`
- Thesis note: `ai memory/02 Portfolio/Long-Term Theses/20260706T065716Z-ushamart-long-term-thesis.md`
- Committee memo: `ai memory/02 Portfolio/Long-Term Committee Reviews/20260706T072317Z-ushamart-committee-memo.md`
- Monte Carlo note: `ai memory/02 Portfolio/Long-Term Monte Carlo/20260706T115307Z-ushamart-monte-carlo.md`
- Recommended action: Risk Office must resolve breached limits before any capital action.

Second live decision example:

- Client: `Tushit`
- Symbol: `LIQUIDBEES`
- v2 decision state: `position_remediation_required`
- v2 flags: `critical_position_remediation`
- Net exposure: INR `2,554,727.55`
- Risk warning: single-name exposure at `21.71%` of Long-Term Investing for Tushit
- Remediation tasks: `2`
- Recommended action: complete thesis and exit-criteria remediation before approval.

## Verification

Migration apply:

```bash
python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/105_symbol_intelligence_v2.sql
```

Result:

- `CREATE VIEW`
- `CREATE VIEW`
- `INSERT 0 2`

Database summary:

```sql
SELECT metric || '=' || value
FROM portfolio.v_symbol_intelligence_v2_summary
ORDER BY metric;
```

Result:

- `committee_pending_rows=0`
- `critical_remediation_rows=69`
- `risk_blocked_rows=1`
- `strategy_linked_rows=1`
- `symbol_rows=69`
- `symbols=45`

API health:

```bash
curl -s http://127.0.0.1:8765/api/health
```

Result:

- `ok = true`
- DB status `ok`
- runtime root on external SSD
- TradingView CDP still unavailable on port `9222`, which remains a known TradingView launch prerequisite.

API snapshot:

```bash
curl -s http://127.0.0.1:8765/api/snapshot
```

Result:

- `symbol_intelligence_v2` present,
- `symbol_intelligence_v2_summary` present,
- rows returned: `69`,
- snapshot issues: none.

Python compile:

```bash
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
```

Result: passed.

Frontend build:

```bash
npm --prefix _ai_os_runtime/ai-office-ui run build
```

Result: passed. Built bundle: `index-Cbk6JtlT.js`.

MCP smoke:

```bash
python3 _ai_os_runtime/scripts/smoke_mcp_tools.py
```

Result:

- `tool_count = 122`
- existing MCP smoke checks passed.

Direct MCP calls:

- `tools/list` includes `ai_os_symbol_intelligence_v2`.
- `tools/list` includes `ai_os_symbol_intelligence_v2_summary`.
- `ai_os_symbol_intelligence_v2_summary` returns the six live summary metrics.
- `ai_os_symbol_intelligence_v2` returns symbol decision packets with exposure, remediation, risk, committee, evidence, and next action.

## What This Enables Next

The next build should add action buttons from Symbol Intelligence v2:

- route remediation item to Long-Term Office execution,
- request thesis refresh,
- request exit-criteria review,
- route risk breach to Risk Committee,
- open linked committee memo,
- open linked thesis note,
- route latest filing/news into Research Factory,
- route strategy candidate/dossier to Quant Lab,
- open TradingView chart when CDP is available.

## Remaining Gaps

- Catalyst links are present in the data packet through filing/event fields, but need a richer UI drilldown.
- Trading setup links are present through signals, candidates, and strategy dossiers, but need explicit per-symbol action buttons.
- TradingView CDP remains unavailable until TradingView is relaunched with remote debugging on port `9222`.
- v2 currently consumes symbol-level long-term committee context; client-specific committee attribution should be added if separate client-level committee reviews are introduced.
