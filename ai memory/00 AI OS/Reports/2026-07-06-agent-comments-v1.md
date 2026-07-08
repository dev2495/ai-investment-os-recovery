# Agent Comments v1

Date: 2026-07-06
Owner: Jarvis
Status: Verified

## What Changed

Built an auditable comment and review-annotation layer for the AI Investment OS. Agents can now attach comments, objections, follow-ups, source gaps, and decision notes to real office targets such as generated output artifacts, tasks, approvals, agents, message threads, strategies, symbols, clients, committee reviews, risk events, and system objects.

## Database Objects

- `agent.comments`
- `agent.v_agent_comments`
- `agent.v_agent_comment_summary`
- `agent.v_agent_comment_target_summary`

Comment targets are flexible through:

- `target_kind`
- `target_ref`
- optional `target_title`

Known targets are enriched through existing live views and tables:

- `agent.v_output_artifact_registry_v2`
- `agent.tasks`
- `agent.approvals`
- `agent.v_employee_profiles_v1`
- `agent.agent_messages`
- `strategy.v_strategy_registry`

## API

Added routes:

- `POST /api/agents/comments`
- `POST /api/agents/comments/resolve`

Both routes write audit rows through the existing API audit path.

## MCP

Added tools:

- `ai_os_agent_comments`
- `ai_os_create_agent_comment`
- `ai_os_resolve_agent_comment`

MCP JSON-RPC smoke result:

```json
{
  "initialized": true,
  "tools_registered": true,
  "created_id": 6,
  "created_status": "open",
  "resolved_status": "resolved",
  "comment_rows_for_target": 6,
  "summary_rows": 5
}
```

## Dashboard

Added Live AI Office panel:

- `Agent Comments`
- Comment composer
- Latest review notes
- Commented targets
- Resolve action

Browser render smoke:

```json
{
  "visible": true,
  "hasComposer": true,
  "hasCommentedTargets": true,
  "hasResolve": true,
  "formCount": 1
}
```

## Verified Counts

API snapshot:

```json
{
  "issues": [],
  "comment_rows": 6,
  "target_rows": 1,
  "summary": {
    "total_comments": "6",
    "open_comments": "1",
    "high_priority_comments": "0",
    "commented_targets": "1",
    "output_artifact_comments": "6"
  }
}
```

Warehouse status:

| Status | Count |
|---|---:|
| open | 1 |
| resolved | 5 |

The one open comment is a real verification note attached to output artifact `worker_run:23`.

## Implementation Note

During verification, the first API response returned `{}` even though the comment row was inserted. Root cause: the insert statement tried to read the just-inserted row through a view inside the same data-modifying CTE. PostgreSQL data-modifying CTE sub-statements share one snapshot and do not see each other's table effects except through `RETURNING`. The fix is now two-step:

1. Insert/update with `RETURNING id`.
2. Read `agent.v_agent_comments` by that id in a second query.

## Files Changed

- `_ai_os_runtime/postgres/init/083_agent_comments_v1.sql`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v7.0.md`

## Verification

- Migration applied to `ai_os_postgres`: passed.
- SQL summary/count checks: passed.
- Python compile for API/MCP: passed.
- Frontend production build: passed.
- API direct create/resolve smoke: passed.
- MCP JSON-RPC read/create/resolve smoke: passed.
- API snapshot smoke: passed with `issues: []`.
- Live browser render check using system Chrome: passed.

## Remaining Gaps

- Comment threads are supported by `parent_comment_id`, but the dashboard does not yet render nested thread detail.
- Comment filters/search are available through MCP but not yet exposed as UI controls.
- Artifact-detail pages remain open; comments currently show in the dashboard-level panel.
