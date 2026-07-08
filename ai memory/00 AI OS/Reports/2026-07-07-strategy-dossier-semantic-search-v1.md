---
title: Strategy Dossier Semantic Search v1
type: implementation_report
date: 2026-07-07
status: completed
owner: Strategy Dossier Search Agent
tags:
  - ai-os
  - strategy-dossiers
  - qdrant
  - ollama
  - mcp
  - ai-office
---

# Strategy Dossier Semantic Search v1

## Outcome

Persistent strategy idea dossiers are now searchable through the live AI OS stack.

The operating flow is:

1. Charlie/Jarvis or the UI submits a query.
2. `search_strategy_idea_dossiers.py` detects the embedding model used by indexed dossier chunks.
3. Query embedding is produced through Ollama `mxbai-embed-large` when the index is `mxbai-embed-large`.
4. Qdrant searches `strategy_artifacts_mxbai_embed_large` with `source_table = strategy.idea_dossiers`.
5. Results are joined back to `strategy.v_idea_dossiers`.
6. The run is persisted in `strategy.idea_dossier_search_runs`.
7. API, MCP, and AI Office UI all expose the same audited path.

SQL lexical fallback exists for Qdrant/API outages, but the verified path used Qdrant vector search with no fallback.

## Files Added

- `_ai_os_runtime/postgres/init/096_strategy_dossier_search_v1.sql`
- `_ai_os_runtime/scripts/search_strategy_idea_dossiers.py`
- `ai memory/00 AI OS/Reports/2026-07-07-strategy-dossier-semantic-search-v1.md`

## Files Updated

- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v8.0.md`

## Warehouse Objects

- `strategy.idea_dossier_search_runs`
- `strategy.v_idea_dossier_search_runs`

Fields captured per run:

- `run_key`
- `query_text`
- `status`
- `search_mode`
- `embedding_model`
- `qdrant_available`
- `fallback_used`
- `match_count`
- `results`
- timing and actor fields

## API

Endpoint:

```text
POST /api/strategy/idea-dossiers/search
```

Payload:

```json
{
  "query": "TATASTEEL optimizer committee",
  "run_key": "dossier_search_api_smoke_20260707",
  "limit": 5
}
```

Verified response:

- `status = completed`
- `search_mode = qdrant_vector`
- `embedding_model = mxbai-embed-large`
- `qdrant_available = true`
- `fallback_used = false`
- `match_count = 5`

Top matches included:

- `Research-sourced strategy: TATASTEEL long idea`
- `Research-sourced strategy: TATASTEEL watchlist`
- `Research-sourced strategy: TATASTEEL long idea`
- `Research-sourced strategy: HINDALCO long idea`
- `Component pattern: algo trading terminal - historical price data`

## MCP

Tool added:

```text
ai_os_search_strategy_idea_dossiers
```

MCP smoke verified:

- Tool present in `tools/list`.
- Tool call returned `qdrant_vector` results.
- Tool call used `mxbai-embed-large`.
- Tool call returned `fallback_used = false`.

## UI

AI Office dashboard now includes:

- `Dossier Search` input.
- `Search Dossiers` action.
- Latest search metadata:
  - search mode
  - match count
  - embedding model
  - Qdrant availability
  - fallback status
- Result cards with:
  - dossier title
  - recommended next action
  - note path
  - match source
  - vector score
  - Qdrant index status
  - symbols

Playwright live UI smoke verified these strings:

- `Dossier Search`
- `mxbai-embed-large`
- `qdrant true`
- `Research-sourced strategy: TATASTEEL`

## Ollama/Qdrant Recovery

Initial state:

- Qdrant was reachable.
- Ollama `/api/tags` returned connection refused.
- Existing vector registry for `strategy.idea_dossiers` used `local_hashing_1024`.

Fix applied:

- Started the existing Ollama LaunchAgent path with:

```bash
env AI_OS_START_OLLAMA_LAUNCHD=1 bash _ai_os_runtime/scripts/start_ai_office_live.sh
```

Verified:

- Ollama served from `127.0.0.1:11434`.
- `OLLAMA_MODELS` pointed to `/Volumes/Devarsh SSD/OllamaModels`.
- Installed models included:
  - `llama3.2:3b`
  - `qwen3:4b`
  - `mxbai-embed-large:latest`

Reindex command:

```bash
python3 _ai_os_runtime/scripts/index_qdrant_documents.py
```

Verified reindex result:

```json
{
  "documents_seen": 290,
  "documents_skipped_empty": 0,
  "points_indexed": 2212,
  "embedding_model": "mxbai-embed-large",
  "fallback_chunks": 0,
  "last_embedding_error": null,
  "collections": {
    "obsidian_notes_mxbai_embed_large": 532,
    "corporate_filings_mxbai_embed_large": 234,
    "trade_journals_mxbai_embed_large": 1,
    "news_social_mxbai_embed_large": 9,
    "research_reports_mxbai_embed_large": 1393,
    "strategy_artifacts_mxbai_embed_large": 43
  }
}
```

Registry proof:

- `strategy.idea_dossiers`: 23 chunks indexed with `mxbai-embed-large`.
- Search runs persisted: 5.
- Latest script/API/MCP/UI runs used `qdrant_vector`, `mxbai-embed-large`, `qdrant_available = true`, `fallback_used = false`.

## Verification Commands

```bash
docker exec -i ai_os_postgres psql -q -U ai_os -d ai_os -v ON_ERROR_STOP=1 -f /dev/stdin < _ai_os_runtime/postgres/init/096_strategy_dossier_search_v1.sql
python3 -m py_compile _ai_os_runtime/scripts/search_strategy_idea_dossiers.py _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
env AI_OS_START_OLLAMA_LAUNCHD=1 bash _ai_os_runtime/scripts/start_ai_office_live.sh
python3 _ai_os_runtime/scripts/index_qdrant_documents.py
python3 _ai_os_runtime/scripts/search_strategy_idea_dossiers.py --query "TATASTEEL optimizer committee" --run-key dossier_search_mxbai_script_smoke_20260707 --limit 5
curl -s -X POST http://127.0.0.1:8765/api/strategy/idea-dossiers/search -H 'Content-Type: application/json' -d '{"query":"TATASTEEL optimizer committee","run_key":"dossier_search_api_smoke_20260707","limit":5}'
```

## Guardrails

- No broker write path was added.
- No live execution approval was added.
- Search is read-only plus audit-write to `strategy.idea_dossier_search_runs`.
- SQL fallback is explicitly marked through `fallback_used = true` if Qdrant is unavailable.
- The query embedding model follows the indexed dossier embedding model to avoid cross-space search errors.

## Remaining Work

- Add scheduled embedding health monitor.
- Add automatic reindex retry policy after Ollama outages.
- Add dossier detail drawer with full evidence timeline.
- Add "create committee memo from dossier" action.
- Add "route result to Quant Lab / Special Situations / Committee" buttons from search results.
- Add cross-dossier duplicate merge controls.
- Add authentication before external network access.
