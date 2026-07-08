# Strategy Discovery Triage v1

Date: 2026-07-07
Owner: Charlie Munger / Jarvis / Strategy Discovery Agent
Status: completed for foundation v1

## Outcome

The AI OS now has a real triage layer for discovered strategy ideas. Charlie/Jarvis can decide what happens to each discovered candidate instead of leaving generated ideas as passive rows.

Supported decisions:

- `reject`
- `request_more_evidence`
- `route_quant_lab`
- `route_special_situation`
- `open_committee_review`

Every decision is auditable and keeps broker/autonomous live execution disabled.

## What Was Built

- Migration: `_ai_os_runtime/postgres/init/094_strategy_discovery_triage_v1.sql`
- Worker: `_ai_os_runtime/scripts/resolve_strategy_discovery_triage.py`
- API: `POST /api/strategy/discovery/triage/resolve`
- MCP:
  - `ai_os_resolve_strategy_discovery_triage`
  - `ai_os_strategy_discovery_triage_queue`
- AI Office UI:
  - triage queue rows
  - latest triage decisions
  - `Evidence`
  - `Quant`
  - `Special`
  - `Committee`
  - `Reject`

## Database Objects

- `strategy.strategy_discovery_triage_decisions`
- `strategy.v_strategy_discovery_triage_queue`
- `strategy.v_strategy_discovery_triage_decisions`

The queue links discovery candidates to generated ideas, optimizer runs, inbox items, approvals, and committee reviews.

## Routing Behavior

`reject`

- Updates discovery candidate status to `triage_rejected`
- Updates generated idea status to `rejected`
- Creates an inbox item for Strategy Discovery Agent

`request_more_evidence`

- Updates discovery candidate status to `triage_more_evidence`
- Updates generated idea status to `needs_more_evidence`
- Routes to Research Analyst, Software Engineer, or Strategy Research Agent depending on source type

`route_quant_lab`

- Updates discovery candidate status to `triage_quant_lab`
- Updates generated idea status to `quant_lab_queue`
- Creates a Quant Researcher inbox item

`route_special_situation`

- Updates discovery candidate status to `triage_special_situation`
- Updates generated idea status to `special_situation_queue`
- Creates a Special Situations Agent inbox item

`open_committee_review`

- Requires a completed optimizer path with an `optimization_run_id`
- Calls `strategy.open_strategy_committee_review`
- Links the triage decision to committee review and approval rows
- Does not approve paper or live execution

## Verification Evidence

Migration applied successfully.

Compile checks passed:

- `_ai_os_runtime/scripts/resolve_strategy_discovery_triage.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`

React build passed:

- `npm run build`

Services restarted successfully:

- API: `http://127.0.0.1:8765/api/health`
- UI: `http://127.0.0.1:5177/`

API health returned `ok: true`.

## Smoke Decisions

Direct worker:

- Candidate `51`: `request_more_evidence`
- Result: inbox item `180`, broker false

Direct worker:

- Candidate `49`: `route_quant_lab`
- Result: inbox item `179`, routed to Quant Researcher, broker false

Direct worker:

- Candidate `47`: `open_committee_review`
- Result: committee review `2`, approval `13`, recommended decision `reject_or_retest`, broker false

API:

- Candidate `50`: `reject`
- Result: inbox item `182`, broker false

MCP:

- Candidate `48`: `route_special_situation`
- Result: inbox item `183`, routed to Special Situations Agent, broker false

## Live Database Counts

As of verification:

- Triage decisions: 5
- Discovery triage inbox items: 4
- Committee-linked triage decisions: 1
- Approval-linked triage decisions: 1

Decision coverage:

| Decision | Routed agent | Count |
|---|---|---:|
| `open_committee_review` | none | 1 |
| `reject` | Strategy Discovery Agent | 1 |
| `request_more_evidence` | Software Engineer | 1 |
| `route_quant_lab` | Quant Researcher | 1 |
| `route_special_situation` | Special Situations Agent | 1 |

## UI Verification

Playwright loaded the AI Office UI and confirmed:

- `Strategy Discovery Agent`
- `Evidence`
- `Quant`
- `Special`
- `Committee`
- `Reject`
- visible triage decision state
- `broker false`

## Safety Gates

- `broker_order_allowed = false`
- `autonomous_live_execution_allowed = false`
- `open_committee_review` creates review/approval state only; it does not approve paper monitoring or live execution.
- Committee final decisions still require the existing strategy committee workflow and memo rules.

## Remaining Gaps

- Need a richer triage note editor in the UI instead of fixed dashboard-generated notes.
- Need bulk triage for duplicate discoveries from repeated scheduler runs.
- Need automatic grouping/deduplication by symbol/source idea so repeated TATASTEEL ideas become one persistent research thread.
- Need scheduled Qdrant indexing after news/discovery/triage so Charlie can retrieve these decisions semantically.

## Recommended Next Slice

Build the persistent idea dossier:

- One dossier per strategy idea across repeated discoveries
- Deduplication by source, symbol, title, and generated idea lineage
- Evidence timeline from news, filings, journal patterns, optimizer runs, validation, triage, and committee
- UI dossier drawer from each triage row
- Qdrant indexing of the dossier for Charlie/Jarvis retrieval
