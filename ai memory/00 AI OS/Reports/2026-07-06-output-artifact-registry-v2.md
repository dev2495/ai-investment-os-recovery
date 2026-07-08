# Output Artifact Registry v2

Date: 2026-07-06
Owner: Knowledge Librarian
Status: Verified

## What Changed

Built a standalone generated-output registry for the AI Investment OS. This gives Charlie, Jarvis, and the Live AI Office one place to inspect reports, memos, worker outputs, model outputs, indexed AI research files, and traceability gaps.

## Database Objects

- `agent.v_output_artifact_registry_v2`
- `agent.v_output_artifact_summary`
- `agent.v_output_artifact_gaps`

The registry is read-only and aggregates existing real records from:

- `agent.v_recent_worker_runs`
- `strategy.v_strategy_committee_queue`
- `portfolio.v_long_term_committee_queue`
- `portfolio.v_long_term_specialist_outputs`
- `portfolio.v_long_term_research_updates`
- `portfolio.v_long_term_monte_carlo_runs`
- `research.v_special_situation_memos`
- `research.v_ai_output_inventory`

## Verified Counts

Total generated artifacts visible to the office: 159

| Family | Count |
|---|---:|
| worker_output | 23 |
| committee_memo | 3 |
| specialist_output | 12 |
| research_note | 26 |
| risk_model | 3 |
| special_situation_memo | 1 |
| indexed_ai_output | 91 |

Location coverage:

- Obsidian note rows: 68
- Local file rows: 91
- Source URL rows: 1

Traceability gaps:

- `long_term_research_update_missing_note`: 4

## API

Added snapshot keys:

- `output_artifact_summary`
- `output_artifact_registry`
- `output_artifact_gaps`

API smoke result:

```json
{
  "ok": true,
  "summary_rows": 8,
  "registry_rows": 150,
  "gap_rows": 4,
  "issues": [],
  "total_artifacts": "159"
}
```

## MCP

Added tool:

- `ai_os_output_artifact_registry`

Tool supports filters:

- `artifact_family`
- `owner_agent`
- `symbol`
- `query`
- `gaps_only`
- `limit`

MCP JSON-RPC smoke result:

```json
{
  "initialized": true,
  "tool_registered": true,
  "summary_rows": 8,
  "artifact_rows": 3,
  "gap_rows": 4,
  "first_family": "committee_memo"
}
```

## Dashboard

Added Live AI Office panel:

- `Output Artifact Registry`
- Summary tiles
- Latest office outputs
- Traceability gaps

Browser render smoke:

```json
{
  "visible": true,
  "hasRegistryTitle": true,
  "hasLatestOutputs": true,
  "hasTraceabilityGaps": true,
  "hasTotal159": true
}
```

## Files Changed

- `_ai_os_runtime/postgres/init/082_output_artifact_registry_v2.sql`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v7.0.md`

## Verification

- Applied migration to `ai_os_postgres`: passed.
- SQL summary counts: passed.
- Python compile for API and MCP server: passed.
- API snapshot smoke: passed with `issues: []`.
- MCP JSON-RPC smoke: passed.
- Frontend production build: passed.
- Live browser render check using system Chrome: passed.

## Remaining Gaps

- Four long-term research updates need `note_path` backfill or explicit no-note justification.
- Registry detail drill-down page is still open.
- Artifact comments and review annotations are still open.
- Artifact-to-approval full audit timeline can be hardened after the next approval/audit slice.
