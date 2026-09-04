# Current control plane and reuse decisions

Inspected against `b42cc5d` on 2026-09-04. This is a source inventory; live schema, row counts and service topology require reconnection to the iMac.

| Concern | Existing authority | Phase 2 decision |
|---|---|---|
| Agent identity | `agent.profiles.id`, `agent_name`; hierarchy, departments, characters | Extend the existing numeric ID with an immutable machine key; no second identity registry |
| Work | `agent.tasks`, `v_live_agent_worker_queue`, `worker_runs` | Add fenced leases, steps, dependencies and events to these task IDs |
| General worker | `scripts/run_agent_worker_once.py`, dispatched by `run_agent_message_daemon.py` | Preserve skills and provider gates; add ownership at safe boundaries |
| Research execution | `research_case_agent_runtime.py`, `research_case_source_runtime.py`, Research Case daemon | Preserve approval/cost/independent-review state; no automatic replay of paid or uncertain side effects |
| Workflow plans | `agent.graph_definitions`, versions, nodes, runs, checkpoints and events | Reuse; task runtime does not replace graph or Research readiness |
| Communication | `agent.agent_messages`, mailboxes, generated task IDs | Extend later with acknowledged handoffs; no second message queue |
| Committees | `committee_registry`, memberships, packets, positions, sessions, followups | Preserve the existing deliberation and human-decision path |
| Model policy | model routes/catalog/assignments, alias registry, task routing registry, usage/caps; Research preflights/canaries | Extend qualification and binding versions later; no new default model or automatic promotion |
| Schedules | `agent.workflow_schedules`, schedule runs, materializer; company research monitor | Reuse and add explicit idempotent routine contracts later |
| Process supervision | Existing LaunchAgents; `core.runtime_daemon_heartbeats` | Keep process heartbeat; add per-worker/task leases, which process health alone cannot prove |
| Memory | Obsidian note/hash/link index; Qdrant document indexes | Keep source and privacy contracts; Obsidian is not a task lock or credential store |
| Office | `/api/office/snapshot`, shared-safe projection, `OfficeView`, `LiveOffice`, common schemas/queries/actions/store | Extend the same projection; real leases govern “working” states |
| API/MCP | `ai_os_api_server.py`, runtime wrapper; MCP delegates through current API/audit helpers | Add bounded compatibility routes through these servers, not a new service |
| Markets/accounts | Existing Zerodha scripts, canonical market/portfolio tables and health views | Do not touch; preserve GET-only, daily human auth and all execution locks |
| Agent tick | `agents/agent_runner.py` | Historical report generator, not proof of active ownership; do not turn it into a competing daemon |

At the starting commit, the source tree had no `agent.workers`, `task_leases`, or `task_steps` tables. Baseline general claims used a conditional status update without expiry or a fencing token. Migration 256 now adds linked ownership records, behind opt-in worker enrollment. The existing Research worker separately guards approved public model runs; it must not be absorbed into general retry logic without a receipt-aware adapter.

## Files inspected

`AGENTS.md`, `STATUS.md`, runtime README, Compose and example environment; API/runtime server, graph/research/model/monitor/report modules; agent tick and general/message/Research workers; source/index/start scripts; MCP README/server; configuration and migration definitions; existing LiveOffice, OfficeView, layout, data client/query/schema and system primitive paths.

## Privacy and rollout

Legacy task rows remain unchanged until a supported worker explicitly claims them through the lease adapter. New fields do not grant tools, client access or cloud egress. Database rollouts must be staged behind verified backups. Existing deployments continue running the accepted Research release until live Phase 2 acceptance.
