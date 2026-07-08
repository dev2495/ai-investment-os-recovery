---
title: Strategy Dossier Action Workflow v1
type: implementation_report
date: 2026-07-07
status: completed
owner: Charlie Munger
tags:
  - ai-os
  - strategy-dossiers
  - agent-workflows
  - committee
  - mcp
  - ai-office
---

# Strategy Dossier Action Workflow v1

## Outcome

Persistent strategy dossiers can now be converted into gated workflow actions from the live AI Office, API, MCP, or command line.

Supported actions:

- `request_more_evidence`
- `route_quant_lab`
- `route_special_situation`
- `open_committee_review`
- `generate_committee_memo`

This is not an execution layer. Every action explicitly records:

- `paper_monitor_allowed = false`
- `live_execution_allowed = false`
- `human_decision_required = true`

## Files Added

- `_ai_os_runtime/postgres/init/097_strategy_dossier_action_workflow_v1.sql`
- `_ai_os_runtime/scripts/run_strategy_dossier_action.py`
- `ai memory/00 AI OS/Reports/2026-07-07-strategy-dossier-action-workflow-v1.md`

## Files Updated

- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v8.0.md`

## Warehouse Objects

- `strategy.idea_dossier_actions`
- `strategy.v_idea_dossier_actions`

Each action stores:

- dossier id/key/title
- action key/type
- target agent
- target table/id
- output payload
- actor
- timestamp
- execution guardrail booleans

## API

Endpoint:

```text
POST /api/strategy/idea-dossiers/action
```

Example payload:

```json
{
  "dossier_id": 3,
  "action": "open_committee_review",
  "run_key": "dossier_action_api_committee_smoke_20260707",
  "actor": "Charlie Munger",
  "notes": "Open committee review from linked optimizer runs."
}
```

## MCP

Tools added:

```text
ai_os_run_strategy_dossier_action
ai_os_strategy_dossier_actions
```

Verified MCP behavior:

- `tools/list` includes both tools.
- `ai_os_run_strategy_dossier_action` routed dossier `4` to Special Situations.
- `ai_os_strategy_dossier_actions` read back recent actions with `broker_order_allowed=false` and `autonomous_live_execution_allowed=false`.

## UI

The Strategy Discovery / Dossier operating surface now shows action controls on both semantic search results and persistent dossier rows:

- `Evidence`
- `Quant`
- `Special`
- `Committee`
- `Memo`

The same panel now includes recent dossier actions with:

- action type
- target agent
- target table
- status
- broker/live guardrail state

Playwright verified:

- `Evidence`
- `Committee`
- `Memo`
- `request_more_evidence`
- `broker false`
- `live false`

## Live Evidence

Database evidence after verification:

```text
strategy.idea_dossier_actions count = 5
```

Recent actions:

```text
dossier_action_ui_request_more_evidence_20260706231751 | request_more_evidence       | Research Analyst             | agent.inbox_items          | 189 | live=false | paper=false
dossier_action_api_committee_smoke_20260707          | open_committee_review       | Strategy Committee Secretary | strategy.committee_reviews | 3   | live=false | paper=false
dossier_action_mcp_special_smoke_20260707            | route_special_situation     | Special Situations Agent     | agent.inbox_items          | 187 | live=false | paper=false
dossier_action_api_memo_smoke_20260707               | generate_committee_memo     | Strategy Committee Secretary | strategy.committee_reviews | 2   | live=false | paper=false
dossier_action_script_quant_smoke_20260707           | route_quant_lab             | Quant Researcher             | agent.inbox_items          | 185 | live=false | paper=false
```

Committee review evidence:

```text
review 3 | needs_review | memo not generated | paper_monitor_allowed=false | live_execution_allowed=false
review 2 | needs_review | memo generated     | paper_monitor_allowed=false | live_execution_allowed=false
```

Memo written:

```text
ai memory/03 Strategies/Committee Reviews/20260706T231705Z-committee-review-2-research-sourced-strategy--tatasteel-long-idea--discovery_scheduler_mcp_smoke_20260707_discovery--1.md
```

## Verification Commands

```bash
docker exec -i ai_os_postgres psql -q -U ai_os -d ai_os -v ON_ERROR_STOP=1 -f /dev/stdin < _ai_os_runtime/postgres/init/097_strategy_dossier_action_workflow_v1.sql
python3 -m py_compile _ai_os_runtime/scripts/run_strategy_dossier_action.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
env AI_OS_START_OLLAMA_LAUNCHD=1 bash _ai_os_runtime/scripts/start_ai_office_live.sh
python3 _ai_os_runtime/scripts/run_strategy_dossier_action.py --dossier-id 3 --action route_quant_lab --run-key dossier_action_script_quant_smoke_20260707 --actor "Charlie Munger"
curl -s -X POST http://127.0.0.1:8765/api/strategy/idea-dossiers/action -H 'Content-Type: application/json' -d '{"dossier_id":5,"action":"generate_committee_memo","run_key":"dossier_action_api_memo_smoke_20260707","actor":"Charlie Munger"}'
curl -s -X POST http://127.0.0.1:8765/api/strategy/idea-dossiers/action -H 'Content-Type: application/json' -d '{"dossier_id":3,"action":"open_committee_review","run_key":"dossier_action_api_committee_smoke_20260707","actor":"Charlie Munger"}'
```

## Implementation Note

The first run exposed a PostgreSQL issue: data-modifying CTEs cannot be hidden inside a generic subquery wrapper. The worker now uses top-level `WITH ... SELECT COALESCE(json_agg(...))` statements for write operations.

Reference used: PostgreSQL documentation, `WITH` queries, section `Data-Modifying Statements in WITH`.

## Guardrails

- No paper-monitor approval is created by this workflow.
- No live execution approval is created by this workflow.
- No broker order path is added.
- Committee memo generation does not finalize a decision.
- Final committee decisions still require the existing committee decision workflow.

## Remaining Work

- Add dossier detail drawer with full evidence timeline.
- Add direct "Generate memo" action for newly opened committee review `3`.
- Add duplicate dossier merge controls.
- Add automated suggested action recommendation per dossier.
- Add queue filters by target agent and action state.
