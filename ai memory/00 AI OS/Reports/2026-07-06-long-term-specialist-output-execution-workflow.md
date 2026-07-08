# Long-Term Specialist Output Execution Workflow

Generated: 2026-07-06

## What Is Live

The Long-Term Office now has an execution layer after specialist assignment. A queued specialist assignment can be run from the CLI or dashboard/API and produces:

- a durable `portfolio.long_term_specialist_outputs` row,
- an Obsidian output note under `ai memory/02 Portfolio/Long-Term Specialist Outputs/`,
- a `portfolio.holding_thesis_research_updates` audit row,
- updated assignment status,
- updated task output path,
- updated inbox status,
- updated agent message processing status,
- checklist or valuation module status updates where applicable.

This remains research-only. The worker writes `capital_action_allowed = false` and `live_execution_allowed = false` into the output evidence and API response.

## Files Added Or Changed

- `_ai_os_runtime/postgres/init/062_long_term_specialist_output_workflow.sql`
- `_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Master Build Checklist v5.0.md`

## API And Dashboard

New snapshot table:

- `long_term_specialist_outputs`

New API route:

- `POST /api/portfolio/long-term-specialists/execute`

Dashboard update:

- Long-Term specialist assignment rows now have an `Execute` action.
- Recent specialist outputs are visible in the Long-Term panel.

## Verification Evidence

Migration applied:

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE VIEW
INSERT 0 1
UPDATE 2
```

Compile and frontend build:

```bash
python3 -m py_compile _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py _ai_os_runtime/api/ai_os_api_server.py
npm run build
```

CLI execution proof:

```json
{
  "assignment_id": 1,
  "symbol": "USHAMART",
  "module_key": "business_model",
  "output_status": "source_required",
  "source_status": "source_required",
  "missing_sources": [
    "company_filings",
    "annual_report_or_investor_presentation"
  ],
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

HTTP execution proof:

```json
{
  "assignment_id": 2,
  "symbol": "USHAMART",
  "module_key": "moat_scorecard",
  "output_status": "source_required",
  "source_status": "source_required",
  "missing_sources": [
    "company_filings"
  ],
  "capital_action_allowed": false,
  "live_execution_allowed": false
}
```

Database output view proof:

```text
USHAMART|business_model|source_required|source_required|blocked|needs_review
USHAMART|moat_scorecard|source_required|source_required|blocked|needs_review
```

Columns:

```text
symbol | module_key | output_status | source_status | task_status | inbox_status
```

Assignment state proof:

```text
1|business_model|needs_review|source_required|blocked|needs_review|read
2|moat_scorecard|needs_review|source_required|blocked|needs_review|read
```

Columns:

```text
assignment_id | module_key | assignment_status | source_status | task_status | inbox_status | message_status
```

Snapshot proof:

```text
long_term_specialist_outputs = 2
```

Health proof:

```json
{
  "ok": true,
  "tradingview_cdp": {
    "available": true,
    "port": 9222
  }
}
```

## Important Behavior

The worker checks the live warehouse before writing the output. For USHAMART it found:

- live positions,
- latest quote rows,
- prior research updates,
- no corporate filing rows for the symbol.

Because filings and annual report evidence are missing, the worker correctly kept the outputs in `source_required` instead of pretending the analyst modules are complete.

## What Remains

- Add a filings/transcripts/source acquisition workflow for Long-Term modules.
- Execute the remaining USHAMART and LIQUIDBEES assignments after source ingestion.
- Feed specialist outputs into the Long-Term committee memo generator.
- Add valuation assumption tables, reverse DCF, scenario builder, and Monte Carlo engines.
- Add Command Center v2 around Charlie inbox, approvals, risks, and today changes.
- Add animated AI office state backed by tasks, inboxes, messages, and worker runs.

