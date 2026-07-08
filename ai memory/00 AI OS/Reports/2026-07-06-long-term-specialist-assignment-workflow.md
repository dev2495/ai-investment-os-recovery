# Long-Term Specialist Assignment Workflow

Generated: 2026-07-06

## What Is Live

The Long-Term Office now has a working specialist assignment layer. Charlie/Jarvis can dispatch a long-term thesis or committee review into specialist research modules, and each module creates:

- a `portfolio.long_term_specialist_assignments` row,
- an `agent.tasks` work item,
- an `agent.inbox_items` item for the assigned specialist,
- an `agent.agent_messages` handoff message,
- an Obsidian dispatch note under `ai memory/02 Portfolio/Long-Term Specialist Dispatches/`.

This is research-only. The workflow explicitly stores `capital_action_allowed = false` and `live_execution_allowed = false`.

## Specialist Team Wired

- Long-Term Portfolio Manager
- Company Analyst
- Industry Analyst
- Management Analyst
- Financial Statement Analyst
- Forensic Accounting Agent
- Valuation Agent
- Bear Case Agent
- Portfolio Fit Agent
- Risk Agent

Registered but not fully executed yet:

- Quality Score Agent
- Filings and Transcript Analyst

## Modules Dispatched Per Thesis

- Business Model Checklist
- Moat Scorecard
- Industry Structure Checklist
- Management Scorecard
- Governance Scorecard
- Capital Allocation Scorecard
- Financial Statement Quality Scorecard
- Forensic Accounting Checklist
- Valuation Model Suite
- Bear Case And Thesis Killers
- Portfolio Fit And Suitability
- Independent Risk Review

## Files Added Or Changed

- `_ai_os_runtime/postgres/init/061_long_term_specialist_assignment_workflow.sql`
- `_ai_os_runtime/scripts/dispatch_long_term_specialists.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Master Build Checklist v5.0.md`

## Verification Evidence

Compile checks:

```bash
python3 -m py_compile _ai_os_runtime/scripts/dispatch_long_term_specialists.py _ai_os_runtime/api/ai_os_api_server.py
npm run build
```

Migration applied:

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
INSERT 0 10
INSERT 0 9
INSERT 0 11
CREATE VIEW
INSERT 0 1
UPDATE 2
```

CLI dispatch proof for `USHAMART`:

```json
{
  "symbol": "USHAMART",
  "committee_review_id": 1,
  "holding_thesis_id": 2,
  "assignment_count": 12,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

HTTP dispatch proof for `LIQUIDBEES`:

```json
{
  "symbol": "LIQUIDBEES",
  "committee_review_id": 2,
  "holding_thesis_id": 1,
  "assignment_count": 12,
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

Database view proof:

```text
LIQUIDBEES|12|12|12|12
USHAMART|12|12|12|12
```

Columns above are:

```text
symbol | assignments | linked_task_ids | linked_inbox_ids | linked_message_ids
```

Snapshot API proof:

```text
24
['LIQUIDBEES', 'USHAMART']
```

Health check:

```json
{
  "ok": true,
  "runtime_root": "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime",
  "tradingview_cdp": {
    "available": true,
    "port": 9222
  }
}
```

## Implementation Note

The first implementation attempted a large all-in-one data-modifying CTE. PostgreSQL data-modifying CTE statements use one snapshot and communicate changes through `RETURNING`, which made the assignment/task/message link-back brittle. The workflow was changed to sequential writes: assignment upsert, task upsert, inbox insert, message insert, assignment link update. This is simpler, auditable, and verified.

## What Remains

- Execute each specialist module into source-backed analyst outputs.
- Add source collectors for annual reports, filings, transcript links, investor presentations, and industry sources.
- Build assumption tables for valuation, reverse DCF, scenarios, and Monte Carlo.
- Add quality-score execution, not only registration.
- Surface specialist inbox and assignment status in Command Center v2 and the animated AI office.
- Add escalation from completed specialist outputs into the Long-Term Investment Committee memo.

