# Governed Model Runtime Control Plane v1

Date: 2026-07-15
Status: implemented and verified foundation
Scope: model assignment, privacy, cache, escalation, API, MCP, and production Gateway UI

## Outcome

The AI OS now routes model work through a database-backed control plane. All 49 active agents have explicit primary, fallback, escalation, context, and cost policies. Local fallback is enforced before any escalation. Cloud or higher-cost use cannot occur automatically.

## Runtime Contract

- Installed local chat model: `llama3.2:3b`, stored on the external SSD.
- Installed embedding model: `mxbai-embed-large`, stored on the external SSD.
- Governed model routes: 21.
- Ready routes: 14.
- Unavailable-model routes: 5.
- Blocked-secret routes: 2.
- Active agents with complete assignments: 49 of 49.
- Active agents with cost caps: 49 of 49.
- Autonomous cloud agents: 0.
- Unapproved cloud events today: 0.

## Privacy And Cache

The four privacy policies are `public`, `internal`, `client_private`, and `restricted`.

- Client-private and restricted contexts are local-only and never cached.
- Public/internal cache eligibility requires explicit exclusion of client context.
- Non-private chat context omits clients, holdings, books, and symbol intelligence.
- Unscoped vault retrieval is disabled for non-private cacheable chat.
- Decisions retain prompt hash and character count; no raw-prompt column exists.
- Database constraints reject private/restricted cache rows.

## Escalation

`POST /api/models/escalations/request` and MCP tool `ai_os_request_model_escalation` bind a request to an existing model-call decision.

- Private/restricted request: rejected at privacy review; no approval row is created.
- Public/internal non-client request: creates a high-risk human approval.
- Approval resolution synchronizes escalation and cost-review state.
- Approval never invokes a cloud model automatically.
- Capital and live-execution authority remain false.

## Interfaces

- Migration: `_ai_os_runtime/postgres/init/126_model_call_control_plane_v1.sql`.
- API: governed Charlie chat plus `/api/models/escalations/request`.
- MCP: `ai_os_model_runtime_control`, `ai_os_request_model_escalation`.
- UI: Data & Model Gateway panels for runtime metrics, route readiness, privacy/cache policy, all-agent assignment matrix, recent decisions, and escalation queue.
- Validators: `validate_model_call_control_plane.py`, `smoke_model_runtime_mcp.py`.

## Verification Evidence

- Python compile: passed.
- Database invariant validator: passed.
- MCP protocol/read smoke: passed with 158 tools.
- UI production build: passed.
- Gateway browser regression: 6 of 6 passed on clean production state.
- Department terminal regression: 17 of 17 passed.
- WCAG A/AA automation: 39 of 39 passed.
- Desktop and 390px mobile screenshots: visually inspected; no overlap or page-level horizontal overflow.
- Public cache test: first call stored, second call hit in 195 ms.
- Unknown route test: safely fell back to `always_on_daily_driver` with no foreign-key failure.
- Privacy mismatch test: public chat plus client context returned HTTP 400 before retrieval and created zero decision rows.
- Private escalation test: rejected without approval.
- Public escalation test: created approval and rejection synchronized with `cloud_call_executed=false`.
- Cleanup: zero validation chats, model decisions, escalation requests, and cache rows remain; append-only API audit evidence remains.
- Global broker execution remains locked and live broker writes remain false.

## Remaining Gates

- Build a representative model-quality evaluation set by department/task class.
- Measure sustained throughput, cold/warm latency, memory pressure, and thermals.
- Add collection-level Qdrant sensitivity ACLs and retrieval-quality tests.
- Install, resize, or retire the five unavailable Qwen routes after benchmark review.
- Configure cloud provider secret references only when needed.
- Build separately approved provider invocation and budget alerts; approval alone must remain non-executing.
- Add machine-aware routing for MacBook versus future 24/7 host.

This slice is production-safe foundation, not completion of the full AI Investment OS.
