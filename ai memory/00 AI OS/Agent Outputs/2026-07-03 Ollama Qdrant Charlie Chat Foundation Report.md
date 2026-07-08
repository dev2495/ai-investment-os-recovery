# Ollama Qdrant Charlie Chat Foundation Report

Date: 2026-07-03
Owner: Charlie Munger Orchestrator / Jarvis Runtime
Runtime root: `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`

## Outcome

The foundation loop is live:

1. Ollama model storage is on the external SSD at `/Volumes/Devarsh SSD/OllamaModels`.
2. Qdrant was rebuilt with real `mxbai-embed-large` embeddings, not hash fallback vectors.
3. The AI Office API has a working `POST /api/chat` endpoint.
4. Charlie chat can retrieve from Qdrant, call a local model, persist the turn, and write dashboard widget intents.
5. The dashboard UI is live at `http://127.0.0.1:5177/`.
6. The API is live at `http://127.0.0.1:8765/api/health`.

## Model Decision

Selected always-on daily driver: `llama3.2:3b`.

Reason:

- Direct Ollama test returned in about 5 seconds.
- Full `/api/chat` dashboard smoke returned in about 23 seconds after prompt-budget tuning.
- Runtime memory shown by `ollama ps`: `llama3.2:3b` about 2.5 GB, `mxbai-embed-large` about 685 MB.
- On-disk Ollama model store is about 4.8 GB because `qwen3:4b` is also installed.

Rejected as always-on default:

- `qwen3:4b` was installed but timed out over 120 seconds on a direct short chat test. Keep it out of the 24/7 path for now.

Escalation routes kept:

- `qwen3:8b` as planned local workhorse route. Not installed yet.
- `qwen3:14b` as planned local heavy route. Not installed yet.
- Codex/frontier models only for approved heavy reasoning, coding, long filings, and critical portfolio decisions.

## Data And Retrieval

Qdrant reindex result:

- `documents_seen`: 152
- `points_indexed`: 1,578
- `embedding_model`: `mxbai-embed-large`
- `fallback_chunks`: 0

Current Qdrant point counts:

- `obsidian_notes_mxbai_embed_large`: 174
- `research_reports_mxbai_embed_large`: 1,393
- `strategy_artifacts_mxbai_embed_large`: 10
- `trade_journals_mxbai_embed_large`: 1

Postgres registry confirms all 1,578 vector rows use `mxbai-embed-large`; no `local_hashing_1024` rows remain.

## Dashboard And Chat

Added and verified:

- `agent.chat_turns`
- `ops.dashboard_widget_intents`
- `agent.v_recent_chat_turns`
- `ops.v_dashboard_widget_intents`
- `POST /api/chat`
- Charlie chat panel in the AI Office dashboard
- Widget intent panel in the AI Office dashboard
- Snapshot exposure for `latest_positions`

Successful `/api/chat` smoke:

- `model_status`: `called`
- `route_model`: `llama3.2:3b`
- `retrieval_status`: `ok`
- `retrieval_hits`: 8
- `widget_intents`: portfolio latest positions, market signal monitor, strategy lab queue, research filings inbox, model runtime status
- Latest successful chat turn id: 4

## Portfolio Snapshot

Current top-level snapshot verification:

- `issues`: none
- `clients`: 3
- `latest_positions`: 71
- `model_routes`: 17
- `chat_turns`: 4
- `widget_intents`: 18

Client control plane:

- Naval market value visible.
- Sanjana market value visible.
- Tushit market value visible.

## TradingView And Browser Control

TradingView Desktop CDP remains reachable:

- Port: `9222`
- Browser: `Chrome/140.0.7339.133`
- App user agent includes `TradingView/3.2.0`.

This means the next TradingView controller work can use the existing CDP path instead of rebuilding browser control from scratch.

## Verification Commands

Passed:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py`
- `npm run build` in `_ai_os_runtime/ai-office-ui`
- `python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/027_llama_daily_driver_route.sql`
- `POST http://127.0.0.1:8765/api/chat`
- `GET http://127.0.0.1:8765/api/health`
- `GET http://127.0.0.1:8765/api/snapshot`
- `GET http://127.0.0.1:5177/`

## Sources

- Ollama embed API: https://docs.ollama.com/api/embed
- Ollama chat API: https://docs.ollama.com/api/chat
- Ollama qwen3 library page: https://ollama.com/library/qwen3
- Ollama llama3.2 library page: https://ollama.com/library/llama3.2

## Remaining Gaps

1. The dashboard can persist widget intents, but it does not yet dynamically create full custom widgets from arbitrary chat instructions.
2. `qwen3:8b` and `qwen3:14b` are route records only until explicitly installed and timed on this machine.
3. The next portfolio pass should render a real holdings table and client drilldown from the newly exposed `latest_positions` snapshot block.
4. The next agent pass should convert widget intents into runnable agent jobs with approval, status, and report outputs.
