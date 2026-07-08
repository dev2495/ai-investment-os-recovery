# Position Object v9 Readiness v1

Date: 2026-07-07
Owner: Portfolio Manager
Risk owner: Risk Agent
Status: implemented as readiness ledger; position completion remains partial

## Outcome

The multi-book portfolio brain now has an institutional position-object readiness layer.

Every active book position can now carry the v9 fields required for hedge-fund style reasoning:

- entry date,
- entry rationale,
- source kind,
- source reference,
- source freshness,
- approval state,
- approval link,
- risk budget,
- capital budget,
- stop price,
- target price,
- time exit,
- linked research note,
- linked committee review,
- linked trade journal,
- hedge group,
- hedge intent,
- linked hedged position,
- offset intent,
- review state,
- v9 metadata.

The system does not pretend the positions are complete. It scores each position and exposes exactly what remains missing.

## What Changed

Added migration:

- `_ai_os_runtime/postgres/init/103_position_object_v9_readiness.sql`

Extended table:

- `books.book_positions`

New/updated views:

- `books.v_position_objects_v9`
- `books.v_position_object_gap_summary`
- `books.v_cross_book_coordination_questions`
- `books.v_portfolio_intelligence_summary`

New API snapshot keys:

- `position_objects_v9`
- `position_object_gap_summary`
- `cross_book_coordination_questions`

New MCP tools:

- `ai_os_position_objects_v9`
- `ai_os_position_object_gap_summary`
- `ai_os_cross_book_coordination_questions`

New AI Office panel:

- `Position Object v9 Readiness`

## Live Evidence

Database verification:

```text
positions: 71
average v9 completeness score: 88.9
total v9 gap rows: 142
cross-book coordination questions: 0
```

Current gap types:

```text
exit_criteria_not_active: 71 positions, severity critical
long_term_thesis_not_active: 71 positions, severity critical
```

No cross-book coordination questions currently exist because the active imported positions are still mapped primarily to the Long-Term book and no opposing Quant/Active/Tactical short exposure is live in the book ledger.

## Verification

Migration:

```text
ALTER TABLE
UPDATE 71
CREATE VIEW
UPDATE 1
INSERT 0 3
```

Compile/build:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
```

Result:

```text
Python compile passed.
TypeScript/Vite build passed.
```

API snapshot:

```text
position_objects_v9: 71 rows
position_object_gap_summary: 2 rows
cross_book_coordination_questions: 0 rows
issues: 0
```

MCP:

```text
tools/list found ai_os_position_objects_v9: true
tools/list found ai_os_position_object_gap_summary: true
tools/list found ai_os_cross_book_coordination_questions: true
total MCP tools: 117
```

Health:

```text
http://127.0.0.1:8765/api/health ok=true
db status=ok
```

UI:

```text
AI Office served at http://127.0.0.1:5177/
Built bundle contains Position Object v9 Readiness panel.
```

## Current Interpretation

The system now knows exactly why the position object is not fully complete:

- migrated holdings have placeholder thesis rows,
- exit criteria exist but are not reviewed/active,
- thesis and exit workflows need real research approval before the positions become decision-ready.

This is the correct institutional state. A position should not become decision-ready just because a row exists.

## Remaining Work

- Promote researched long-term theses to active after source-backed review.
- Review and activate exit criteria per holding.
- Add stop/target/time-exit fields for Tactical and Active Trading positions.
- Add hedge ratio calculation.
- Add offset-cost and tax-impact calculation.
- Link future Quant/Active/Tactical positions to cross-book coordination questions.
- Add UI action for fixing each v9 position-object gap.
- Add committee routing from position readiness gaps.

