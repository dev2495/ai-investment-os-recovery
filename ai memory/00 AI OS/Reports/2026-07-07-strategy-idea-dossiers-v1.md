# Strategy Idea Dossiers v1

Date: 2026-07-07
Owner: Strategy Dossier Agent / Charlie Munger / Jarvis
Status: completed for foundation v1

## Outcome

The AI OS now groups repeated discovered strategy ideas into persistent research dossiers. Repeated TATASTEEL, HINDALCO, Fincept, and component discoveries are no longer only separate scheduler rows; they are durable idea threads with evidence timelines, triage state, optimizer links, committee links, Obsidian notes, and Qdrant/semantic-memory registration.

Broker execution and autonomous live execution remain disabled.

## What Was Built

- Migration: `_ai_os_runtime/postgres/init/095_strategy_idea_dossiers_v1.sql`
- Builder: `_ai_os_runtime/scripts/build_strategy_idea_dossiers.py`
- Qdrant indexer update: `_ai_os_runtime/scripts/index_qdrant_documents.py`
- API: `POST /api/strategy/idea-dossiers/build`
- MCP:
  - `ai_os_build_strategy_idea_dossiers`
  - `ai_os_strategy_idea_dossiers`
- AI Office UI:
  - `Build Dossiers`
  - dossier count
  - dossier status
  - note path
  - discovery and triage counts
  - Qdrant index state

## Database Objects

- `strategy.idea_dossiers`
- `strategy.idea_dossier_links`
- `strategy.idea_dossier_build_runs`
- `strategy.v_idea_dossiers`
- `strategy.v_idea_dossier_links`
- `strategy.v_idea_dossier_build_runs`

Each dossier links back to:

- discovery candidates
- generated strategy ideas
- optimizer runs
- triage decisions
- committee reviews
- approvals where present
- Obsidian notes
- vector document rows

## Obsidian Writeback

Dossier notes are written under:

- `ai memory/03 Strategies/Dossiers/`

Each note includes:

- dossier key
- status
- symbols
- source kind/ref
- discovery count
- generated idea count
- optimizer count
- triage decision count
- committee review count
- current summary
- recommended next action
- evidence timeline
- safety flags

The notes are also upserted into `knowledge.obsidian_notes` with `note_type = 'strategy_idea_dossier'`.

## Verification Evidence

Migration applied successfully.

Compile checks passed:

- `_ai_os_runtime/scripts/build_strategy_idea_dossiers.py`
- `_ai_os_runtime/scripts/index_qdrant_documents.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`

React build passed:

- `npm run build`

Services restarted successfully:

- API: `http://127.0.0.1:8765/api/health`
- UI: `http://127.0.0.1:5177/`

API health returned `ok: true`.

## Smoke Runs

Direct builder:

- Run key: `dossier_smoke_20260707`
- Status: completed
- Dossiers seen: 10
- Dossiers upserted: 10
- Links upserted: 117
- Notes written: 10

API builder:

- Run key: `dossier_api_smoke_20260707`
- Status: completed
- Dossiers seen: 10
- Dossiers upserted: 10
- Links upserted: 117
- Notes written: 10

MCP builder:

- Run key: `dossier_mcp_smoke_20260707`
- Status: completed
- MCP tools present:
  - `ai_os_build_strategy_idea_dossiers`
  - `ai_os_strategy_idea_dossiers`

Qdrant/vector indexing:

- Documents seen: 290
- Points indexed: 2,212
- Strategy artifact chunks: 43
- Dossier chunks in `strategy_artifacts_mxbai_embed_large`: 23
- `strategy.idea_dossiers` rows with `qdrant_index_status = indexed`: 10

Note: Ollama embedding endpoint was not reachable during indexing, so the indexer used its deterministic local hashing fallback: `local_hashing_1024`. Indexing still completed and wrote Qdrant/vector registry rows, but ML embedding quality should improve once Ollama is running with `mxbai-embed-large`.

## Live Database Counts

As of verification:

- Dossiers: 10
- Dossier links: 117
- Dossier build runs: 3
- Obsidian dossier notes: 10
- Dossier vector chunks: 23

Status breakdown:

| Status | Dossiers | Discoveries | Triage decisions | Optimizer runs | Committee reviews |
|---|---:|---:|---:|---:|---:|
| `committee_review` | 1 | 7 | 1 | 1 | 1 |
| `needs_more_evidence` | 1 | 7 | 1 | 0 | 0 |
| `optimizer_route_available` | 2 | 10 | 0 | 0 | 0 |
| `quant_lab_queue` | 1 | 7 | 1 | 4 | 0 |
| `reference_only` | 3 | 6 | 0 | 0 | 0 |
| `rejected` | 1 | 7 | 1 | 0 | 0 |
| `special_situation_queue` | 1 | 7 | 1 | 3 | 0 |

## UI Verification

Playwright loaded the AI Office UI and confirmed:

- `Strategy Discovery Agent`
- `Build Dossiers`
- `DOSSIERS`
- visible dossier titles
- `qdrant indexed`
- `broker false`

## Safety Gates

- `broker_order_allowed = false`
- `autonomous_live_execution_allowed = false`
- Dossiers are memory/research objects, not approval objects.
- Committee, paper-monitor, and live execution approvals remain separate downstream gates.

## Remaining Gaps

- Ollama embedding server should be restored so Qdrant uses `mxbai-embed-large` rather than `local_hashing_1024`.
- Need a dossier drawer/page with full timeline, source links, and one-click actions.
- Need scheduled dossier rebuild after every discovery/triage run.
- Need semantic search endpoint over dossier chunks for Charlie/Jarvis chat.

## Recommended Next Slice

Build the dossier operating page and semantic search:

- dossier detail drawer/page in AI Office
- full evidence timeline with clickable source rows
- semantic search endpoint over `strategy.idea_dossiers`
- automatic dossier rebuild after scheduled discovery and triage
- restore Ollama embedding route for higher-quality retrieval
