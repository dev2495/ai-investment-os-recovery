# P2Cursor First Client Reconciliation

Date: 2026-07-06
Owner: Data Steward / Portfolio Manager / Jarvis
Blueprint: [[AI Investment OS - Institutional Master Blueprint v7.0]]
Checklist: [[AI Investment OS - Execution Checklist v7.0]]

## Result

Built and verified the first p2cursor-vs-current-statement reconciliation workflow for Tushit client `3081832`.

This turns p2cursor from a quarantined legacy archive into auditable portfolio evidence:

- p2cursor open positions are compared against the current Tushit statement account,
- differences are written to durable reconciliation tables,
- Data Steward task/inbox items are created,
- the live API snapshot exposes the run and issues,
- the AI Office dashboard has a P2Cursor Reconciliation panel,
- Charlie/Jarvis can trigger the workflow through MCP.

## New Warehouse Objects

Migration:

```text
_ai_os_runtime/postgres/init/073_p2cursor_reconciliation.sql
```

Created:

- `portfolio.p2cursor_reconciliation_runs`
- `portfolio.p2cursor_reconciliation_issues`
- `portfolio.run_p2cursor_reconciliation(actor, client_code)`
- `portfolio.v_p2cursor_reconciliation_latest`
- `portfolio.v_p2cursor_reconciliation_issues`

Registered:

- agent skill: `p2cursor_reconciliation`
- agent tool: `ai_os_run_p2cursor_reconciliation`
- primary owner: `Data Steward`
- supporting owner: `Portfolio Manager`

## API And Dashboard

API:

- `POST /api/p2cursor-reconciliation/run`
- `/api/snapshot` now includes:
  - `p2cursor_reconciliation_latest`
  - `p2cursor_reconciliation_issues`

Frontend:

- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- New dashboard panel: `P2Cursor Reconciliation`

MCP:

- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Tool: `ai_os_run_p2cursor_reconciliation`

## Live Evidence

Runtime restart:

```text
bash _ai_os_runtime/scripts/start_ai_office_live.sh
```

Result:

```text
Started AI OS LaunchAgents:
  http://127.0.0.1:8765/api/health
  com.devarsh.aios.agent-daemon
  http://127.0.0.1:5177/
```

Compile/build checks:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm run build
```

Result:

```text
Python compile passed.
Frontend build passed: built in 477ms.
```

## First Client Reconciliation

Client:

```text
Tushit / 3081832
```

Accounts compared:

```text
p2cursor_account_2
tushit_3081282_statement
```

Latest verified run:

```json
{
  "id": 7,
  "client_code": "3081832",
  "client_name": "Tushit",
  "p2_account_code": "p2cursor_account_2",
  "comparison_account_code": "tushit_3081282_statement",
  "status": "needs_review",
  "p2_position_count": 4,
  "comparison_position_count": 27,
  "matched_symbols": 2,
  "p2_only_symbols": 2,
  "comparison_only_symbols": 25,
  "quantity_mismatch_symbols": 2,
  "stale_days": 385,
  "issue_count": 30
}
```

## Issues Found

High severity:

| Issue | Symbol | P2Cursor Qty | Statement Qty | Meaning |
| --- | --- | ---: | ---: | --- |
| stale_p2cursor_source | n/a | n/a | n/a | p2cursor latest position date is 385 days older than statement |
| quantity_mismatch | CDSL | 100 | 200 | quantity differs |
| quantity_mismatch | DEEPAKNTR | 96 | 149 | quantity differs |

Medium severity:

| Issue | Symbol | P2Cursor Qty | Statement Qty | Meaning |
| --- | --- | ---: | ---: | --- |
| missing_in_comparison | ASIANPAINT | 100 | n/a | exists in p2cursor but not statement |
| missing_in_comparison | DMART | 105 | n/a | exists in p2cursor but not statement |

Low severity:

- 25 symbols exist in the current statement but not in p2cursor latest open positions.
- These are expected if p2cursor is stale or incomplete, but they must not be ignored.

## Endpoint Smoke

HTTP smoke:

```text
POST /api/p2cursor-reconciliation/run
client_code=3081832
```

Result:

```json
{
  "id": 6,
  "client_code": "3081832",
  "client_name": "Tushit",
  "status": "needs_review",
  "issue_count": 30,
  "stale_days": 385
}
```

Snapshot smoke:

```json
{
  "has_latest": true,
  "has_issues": true,
  "latest": {
    "id": 7,
    "client_name": "Tushit",
    "status": "needs_review",
    "issue_count": 30
  }
}
```

MCP smoke:

```text
ai_os_run_p2cursor_reconciliation
```

Result:

```json
{
  "id": 7,
  "client_code": "3081832",
  "client_name": "Tushit",
  "status": "needs_review",
  "issue_count": 30
}
```

## Interpretation

P2Cursor is useful for historical buy/sell evidence, but for Tushit it is not current portfolio truth.

The system now explicitly says:

- p2cursor account `p2cursor_account_2` is stale by 385 days,
- CDSL and DEEPAKNTR need quantity reconciliation,
- ASIANPAINT and DMART require review because they appear in p2cursor but not in the current statement,
- the current statement contains many newer positions not represented in p2cursor.

This is the correct behavior. The system should preserve p2cursor history without trusting it blindly.

## Remaining Work

Not complete yet:

- full p2cursor extraction for every available client,
- full p2cursor reconciliation for Naval and any other clients with current statements,
- browser/current statement capture for accounts that do not yet have a comparison file,
- reconciliation dashboard across p2cursor, broker statements, old algo systems, and manual entries,
- row-level source lineage page for every reconciled position.

## Checklist Updates

Updated in [[AI Investment OS - Execution Checklist v7.0]]:

- `Full p2cursor reconciliation against broker files` moved to partial.
- `Reconciliation dashboard across broker, p2cursor, algo systems, and manual entries` moved to partial.
- `Build p2cursor extraction plan and first client reconciliation` marked done.

