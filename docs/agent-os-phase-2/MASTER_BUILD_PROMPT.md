# AI Investment OS — Master Build Prompt
## Phase 2: Living Agent Operating System, Charlie, Model Fabric, Doctor, and Truthful Live Office

**Use this prompt from the repository root of `dev2495/ai-investment-os-recovery`.**  
**Do not substitute it for the completed Research Desk specification. This phase builds on that accepted vertical slice.**

---

# COPY-PASTE PROMPT STARTS HERE

You are the principal architect, staff backend engineer, database engineer, distributed-systems engineer, AI-agent engineer, model-runtime engineer, security engineer, product engineer, frontend engineer, SRE, and test owner for my **AI Investment OS**.

The Research Desk vertical slice is now live operational and ready for operator testing. Your next task is to turn the existing collection of registered agents, workers, messages, tasks, model routes, 3D-office components, and research workflows into a **real Living Agent Operating System**.

Do not return another high-level plan. Inspect the current repository and live runtime, preserve everything that already works, then implement this phase step by step with migrations, backend services, worker behavior, model-routing controls, user interfaces, tests, operational documentation, Obsidian writeback, live deployment, and end-to-end proof.

The goal is not decorative avatars. The goal is that Charlie and every specialist agent become durable, visible, interruptible, recoverable coworkers who own real tasks, communicate through audited threads and handoffs, use explicitly qualified models, and show their true state in the 2D and 3D office.

Continue automatically until the exit gates in this prompt pass or a genuine external blocker requires a human decision, credential, paid-model approval, licensed-data entitlement, destructive action, or financial approval.

---

# 1. Current verified baseline

Repository:

```text
dev2495/ai-investment-os-recovery
```

The current accepted Research Desk release work is on:

```text
codex/research-desk-knowledge-scanners-v1
```

At the time this phase prompt was prepared, the branch head was:

```text
b42cc5d028f37ec2ead6b10296235d19bc9a5fd6
```

Do not blindly assume that SHA is still current. Verify the actual branch, live deployment marker, remotes, working tree, and latest accepted release before branching.

The live Research Desk acceptance record is:

```text
docs/research-desk/RESEARCH_DESK_LIVE_ACCEPTANCE_REPORT_2026-09-02.md
```

The Research Desk implementation ledger is:

```text
docs/research-desk/IMPLEMENTATION_STATUS.md
```

The new canonical target blueprint for the full system is:

```text
docs/AI_Investment_OS_Living_Investment_Office_Master_Blueprint_v13.md
```

The preceding architecture documents remain historical context:

```text
docs/AI_Investment_OS_Institutional_Master_Blueprint_v11.md
docs/AI_Investment_OS_Final_Goal_Stack_v12_Agent_Native.md
```

The accepted Research Desk is a working platform, not proof that every company is already decision-ready. Preserve these residual gates as an explicit backlog instead of falsely closing them:

- Wipro and Shivalik currently have evidence-debt packs rather than independent-review-passed investment recommendations.
- The live system has scanner definitions, but production publication and scheduling still require operator approval and real-universe acceptance.
- Public investor/publication Following sources still require operator approval.
- Paid-model canaries remain approval- and human-review-gated.
- Market-hours quote freshness and Safari operator acceptance remain separate live gates.
- Broker writes remain disabled.

These residual Research Desk gates must not derail the next phase, but they must stay visible and must never be relabelled “complete” without evidence.

---

# 2. Branch and change-management rules

First identify the exact accepted source commit and deployed release. Then create a focused branch from that accepted point.

Suggested branch:

```text
codex/live-agent-operating-system-v1
```

Before changing code:

1. Print repository path, branch, HEAD, remotes, working-tree status, submodules, and recent commits.
2. Identify the live iMac checkout, `DEPLOYED_COMMIT`, running API/UI process, and active database migration level.
3. Preserve all uncommitted user work.
4. Verify a current backup of Postgres, Obsidian, runtime configuration, and critical external-SSD artifacts.
5. Run the existing backend test suite, UI build, relevant Playwright suites, dependency audit, and existing smoke checks.
6. Record the baseline in Git and Obsidian.
7. Never force-reset, rebase away user work, drop tables, truncate production state, or rewrite human Obsidian content.
8. Use additive migrations and compatibility views. Remove or rename legacy structures only in a separately approved cleanup after all callers are migrated.
9. Keep the application runnable after each milestone.
10. Use focused commits rather than one giant change.

Create and maintain:

```text
docs/agent-os-phase-2/BASELINE_AUDIT.md
docs/agent-os-phase-2/IMPLEMENTATION_STATUS.md
docs/agent-os-phase-2/DATA_CONTRACTS.md
docs/agent-os-phase-2/AGENT_RUNTIME_STANDARD.md
docs/agent-os-phase-2/MODEL_FABRIC_STANDARD.md
docs/agent-os-phase-2/MESSAGE_AND_HANDOFF_STANDARD.md
docs/agent-os-phase-2/ROUTINE_STANDARD.md
docs/agent-os-phase-2/OFFICE_TRUTH_CONTRACT.md
docs/agent-os-phase-2/DOCTOR_RUNBOOK.md
docs/agent-os-phase-2/SECURITY_REVIEW.md
docs/agent-os-phase-2/ACCEPTANCE_CHECKLIST.md
docs/agent-os-phase-2/LIVE_ACCEPTANCE_REPORT.md
```

Write corresponding implementation and decision notes under a structured Obsidian path such as:

```text
ai memory/00 AI OS/Implementation/Agent OS Phase 2/
```

Use managed blocks and preserve human-authored note content.

---

# 3. Existing components that must be inspected and extended

Do not create a parallel greenfield control plane. Inventory and evolve what already exists.

Inspect at least:

```text
AGENTS.md
STATUS.md
_ai_os_runtime/README.md
_ai_os_runtime/docker-compose.yml
_ai_os_runtime/.env.example

_ai_os_runtime/api/ai_os_api_server.py
_ai_os_runtime/api/ai_os_api_runtime.py
_ai_os_runtime/api/graph_control_plane.py
_ai_os_runtime/api/research_case_agent_runtime.py
_ai_os_runtime/api/research_model_runtime.py
_ai_os_runtime/api/research_monitor_runtime.py
_ai_os_runtime/api/reporting_helpers.py

_ai_os_runtime/agents/agent_runner.py

_ai_os_runtime/scripts/run_agent_worker_once.py
_ai_os_runtime/scripts/run_agent_message_daemon.py
_ai_os_runtime/scripts/run_research_case_agent_once.py
_ai_os_runtime/scripts/run_research_case_agent_daemon.py
_ai_os_runtime/scripts/start_ai_office_live.sh
_ai_os_runtime/scripts/index_obsidian_vault.py
_ai_os_runtime/scripts/index_qdrant_documents.py

_ai_os_runtime/mcp_server/README.md
_ai_os_runtime/mcp_server/ai_os_mcp_server.py

_ai_os_runtime/config/
_ai_os_runtime/postgres/init/
_ai_os_runtime/migrations/
_ai_os_runtime/launchd/

_ai_os_runtime/ai-office-ui/src/app/
_ai_os_runtime/ai-office-ui/src/assistant/
_ai_os_runtime/ai-office-ui/src/data/
_ai_os_runtime/ai-office-ui/src/office3d/
_ai_os_runtime/ai-office-ui/src/system/
_ai_os_runtime/ai-office-ui/src/store.ts
```

Inventory the live database objects under at least:

```text
agent.*
research.*
knowledge.*
core.*
ops.*
market.*
portfolio.*
strategy.*
trading.*
execution.*
```

The repository already contains meaningful primitives, including:

- `agent.profiles`
- active-agent and orchestration views
- `agent.tasks`
- task queues
- `agent.agent_messages`
- `agent.mailboxes`
- committees
- approvals
- tool registry
- model routes
- model assignments
- model cost caps
- model-run preflights and canaries
- MCP audit logs
- graph runs
- research-case workers
- the 3D `LiveOffice`
- `/api/office/snapshot`
- the existing Charlie chat surface
- existing Research Desk agents and workflows

Do not duplicate them just because the desired names in this prompt differ. Map the current schema first, identify gaps, extend the existing objects, and add compatibility views where needed.

---

# 4. Primary objective

Deliver a production-quality **Living Agent Operating System v1** with these connected capabilities:

1. **Durable agent identity and presence**
   - Every active registered agent has a stable identity, role, department, office room, capability policy, model binding, owner/escalation path, workspace, and visible runtime state.
   - Agents remain durable when no worker process is active.
   - A worker process is not the agent identity.

2. **Heartbeat, task leases, recovery, and replay**
   - Workers heartbeat.
   - Active tasks have leases.
   - Dead workers become stale.
   - Leases expire safely.
   - Work is recovered idempotently without duplicate side effects.
   - Every state transition is replayable from durable events.

3. **Persistent messages, handoffs, rooms, and committees**
   - Devarsh can talk to Charlie or any specialist.
   - Agents can message and hand off to one another.
   - Threads retain company, case, portfolio, client, strategy, evidence, artifact, and task context.
   - Handoffs require acknowledgement and explicit ownership transfer.
   - Committee activity is durable and visible.

4. **Charlie as the real chief of staff**
   - Charlie interprets objectives, persists plans, assigns specialists, monitors work, explains blockers, accepts redirects, convenes committees, returns validated artifacts, and stops at approval boundaries.
   - Charlie never claims a queued action is complete.

5. **Per-agent Model Fabric inspired by OpenGrok**
   - Each logical agent or role selector has a versioned primary and fallback model binding by task class.
   - Provider-specific request behavior is explicit and tested.
   - Credentials stay outside bindings and prompts.
   - Routes are health-checked, identity-checked, budgeted, qualified, and fail closed.
   - Operators can test, compare, promote, and roll back model bindings.

6. **A truthful AI OS Doctor**
   - One command and one API surface show the real health of agents, workers, models, databases, Zerodha, Obsidian, Qdrant, Redis, SSD storage, launchd services, queues, routines, backups, and safety locks.
   - Doctor checks include real positive and negative controls.

7. **Skills and routines**
   - A verified workflow can become a versioned skill.
   - A qualified skill can become a scheduled or event-driven routine with ownership, idempotency, stale-data policy, run history, and approval boundaries.
   - Deliver a small real set of routines rather than a large untested catalog.

8. **Truthful 2D and 3D office**
   - The current 3D office is driven by real presence, task, message, model, cost, artifact, blocker, handoff, routine, committee, and approval events.
   - No fake work, seeded activity, decorative handoffs, or invented speech.
   - A complete 2D fallback offers functional parity.

9. **Cross-desk agent foundation**
   - Register and expose the core agents for Research, Portfolio/Clients, TradingView/Markets, Quant, Options, Macro, Corporate Actions, Risk/Capital, Reporting, Data, Engineering, and Operations.
   - This phase establishes identity and operating infrastructure; it does not falsely claim every domain desk is already feature-complete.

Use the existing Research Desk as the golden end-to-end workload for this phase.

---

# 5. Non-negotiable operating rules

## 5.1 Real agents only

An agent may appear as active or working only when:

- a valid worker heartbeat exists;
- a valid task lease exists where work is required;
- the current state comes from a durable row;
- the current task and step exist;
- the source/model/tool data shown is real.

No animation or status may invent activity.

## 5.2 Logical agents, pooled workers and pooled models

Do not launch one model server or permanent Python process per avatar.

On the M4 16 GB machine:

- maintain many durable logical agents;
- use a bounded worker pool;
- use one resident local 8–9B route at a time where practical;
- share qualified model endpoints;
- activate agent context per task;
- bound concurrency;
- avoid huge context windows;
- use retrieval and cached evidence;
- keep heavy artifacts on the external SSD.

## 5.3 Postgres is operational truth

Use Postgres for:

- agent identity;
- presence;
- task state;
- leases;
- messages;
- approvals;
- model bindings;
- costs;
- routines;
- events;
- replay;
- policy.

Redis may accelerate queues and pub/sub, but it is never the only durable record.

## 5.4 Obsidian is human-readable memory

Use Obsidian for:

- role charters;
- runbooks;
- implementation decisions;
- research and committee notes;
- incident reports;
- durable summaries;
- links to source and output artifacts.

Do not use Obsidian as the live lock manager, accounting ledger, task authority, or credential store.

## 5.5 No hidden chain-of-thought surface

Show:

- objective;
- plan;
- source packet;
- tools used;
- deterministic calculations;
- concise rationale;
- assumptions;
- contradictions;
- uncertainty;
- dissent;
- artifacts;
- approval state;
- final state.

Do not store or display private token-by-token chain of thought.

## 5.6 No arbitrary production shell

Agents use reviewed typed capabilities. Arbitrary shell execution is limited to a development sandbox and cannot become a production agent tool without explicit review, allowlisting, isolation, timeout, output limits, and audit.

## 5.7 No credential exposure

- No API keys, access tokens, cookies, passwords, OTPs, or broker secrets in model bindings, prompts, task rows, messages, logs, screenshots, Git, or Obsidian.
- Credentials remain in macOS Keychain, protected environment files, or scoped local services.
- Model provider shims inject credentials locally and redact headers and bodies from logs.
- Human login remains required where providers require it.

## 5.8 Preserve Zerodha exactly as the canonical read-only path

The current GET-only Zerodha integration remains the primary private Indian market/account connector.

Preserve and reuse:

```text
_ai_os_runtime/scripts/sync_zerodha_read_only.py
_ai_os_runtime/scripts/sync_zerodha_market_data.py
_ai_os_runtime/scripts/stream_zerodha_live.py
_ai_os_runtime/scripts/configure_zerodha_imac.sh
_ai_os_runtime/scripts/renew_zerodha_session_imac.sh
_ai_os_runtime/scripts/install_zerodha_stream_imac.sh
_ai_os_runtime/launchd/aios-zerodha-stream-service.sh
```

Preserve:

```text
broker_write_allowed=false
```

Do not create a second disconnected price pipeline. Do not expose place/modify/cancel. Doctor and agent presence may report Zerodha health but may not reveal credentials.

## 5.9 No social or agent-to-order shortcut

No message, scanner hit, challenge result, model response, TradingView action, or agent reputation can place a live trade.

## 5.10 Fail closed

When a required model, tool, source, or data gate fails:

- record the actual failure;
- retry only within policy;
- use only an explicitly qualified fallback;
- label fallback/degraded state;
- block consequential completion when the fallback lacks qualification;
- never silently substitute an unqualified route or stale fact.

---

# 6. Desired agent state model

Use or map onto the following canonical state model:

```text
OFFLINE
BOOTING
IDLE
PLANNING
CLAIMING_TASK
ACQUIRING_SOURCE
READING
PARSING
EXTRACTING
CALCULATING
ANALYZING
WRITING
CALLING_TOOL
WAITING_FOR_TOOL
HANDING_OFF
IN_GROUP_ROOM
IN_COMMITTEE
WAITING_FOR_INPUT
WAITING_FOR_APPROVAL
SIMULATING
EXECUTING_ALLOWED_INTERNAL_ACTION
RECONCILING
VALIDATING
COMPLETED
STALE
BLOCKED
RATE_LIMITED
BUDGET_EXHAUSTED
DEGRADED
RETRYING
PAUSED
CANCELLED
FAILED
QUARANTINED
```

Define legal transitions. Invalid transitions must fail with a clear error and audit event.

Separate at least:

```yaml
agent_presence_state:
task_status:
task_step_status:
research_readiness:
approval_status:
model_call_status:
tool_call_status:
routine_run_status:
execution_status:
reconciliation_status:
```

A completed task is not automatically a decision-ready research case or an approved action.

---

# 7. Milestone M0 — Baseline, compatibility map, and residual-gate registry

Before implementation:

1. Map every existing relevant table, view, function, API endpoint, MCP tool, worker, script, UI hook, and 3D-office field.
2. Produce a “reuse, extend, deprecate, do not touch” matrix.
3. Record the Research Desk residual gates separately.
4. Capture database row counts and schema hashes for relevant namespaces.
5. Capture current API OpenAPI or route inventory.
6. Capture the live MCP `tools/list`.
7. Capture all active agent profiles, model assignments, tool permissions, tasks, messages, committees, approvals, and office snapshot fields.
8. Capture process/launchd topology.
9. Capture performance and memory baseline on the iMac.
10. Prove the current Research Desk still passes before changing it.

Required artifacts:

```text
docs/agent-os-phase-2/CURRENT_CONTROL_PLANE_MAP.md
docs/agent-os-phase-2/REUSE_MATRIX.md
docs/agent-os-phase-2/RESEARCH_DESK_RESIDUAL_GATES.md
docs/agent-os-phase-2/PERFORMANCE_BASELINE.md
```

**M0 exit gate:** The agent can explain exactly which existing objects will be reused and can prove no competing task, message, model, or office subsystem is being created.

---

# 8. Milestone M1 — Durable identity, worker registry, presence, and task leases

## 8.1 Extend rather than duplicate

Prefer extending current objects such as `agent.profiles`, `agent.tasks`, `agent.agent_messages`, `agent.mailboxes`, `agent.model_routes`, and `agent.agent_model_assignments`.

Add only missing structures, conceptually including:

```text
agent.workers
agent.worker_heartbeats
agent.agent_presence
agent.task_leases
agent.task_steps
agent.task_dependencies
agent.task_events
agent.agent_workspaces
agent.agent_incidents
```

Names may differ if compatible current objects exist.

## 8.2 Stable identities

Every agent needs a stable machine identity independent of display name.

Minimum agent identity fields:

```yaml
agent_id:
agent_key:
display_name:
title:
department_key:
room_key:
role_version:
status:
owner_agent_id:
escalation_agent_id:
primary_model_binding:
allowed_books:
allowed_clients:
allowed_data_classes:
max_parallel_tasks:
daily_token_budget:
daily_cost_budget_usd:
permission_level:
created_at:
updated_at:
```

Do not use display name as the sole foreign key in new structures. Preserve compatibility for existing name-based rows through a mapped identifier.

## 8.3 Worker registry

A worker is a process or service capable of executing tasks.

Minimum worker fields:

```yaml
worker_id:
node_id:
process_id:
runtime_version:
supported_task_classes:
supported_tools:
max_parallel_tasks:
started_at:
last_heartbeat_at:
status:
shutdown_requested:
metadata:
```

## 8.4 Task leases

Implement atomic task claim with:

- `SELECT ... FOR UPDATE SKIP LOCKED` or equivalent safe transaction;
- a unique active lease per task;
- worker and agent identity;
- lease token;
- claimed timestamp;
- heartbeat timestamp;
- expiry timestamp;
- attempt number;
- recovery reason;
- idempotency key;
- cancellation and pause checks;
- provider/data preflight before claim where required.

Recommended defaults:

```text
active heartbeat interval: 15 seconds
idle heartbeat interval: 60 seconds
lease duration: 45 seconds
stale after: 3 missed active heartbeats
```

Make values configurable and test short TTLs with an accelerated clock.

## 8.5 Recovery

When a worker dies:

1. mark the worker stale;
2. expire its leases;
3. record a recovery event;
4. inspect side-effect receipts;
5. do not repeat completed irreversible work;
6. requeue only an idempotent task or resume from the last safe step;
7. preserve attempt history;
8. show the transition in the office;
9. alert after the configured retry threshold.

**M1 exit gate:** Two workers cannot own the same lease; killing one worker causes an honest stale state and safe idempotent recovery.

---

# 9. Milestone M2 — Heartbeat and event-stream runtime

## 9.1 Heartbeat endpoint

Implement an authenticated internal heartbeat contract similar to:

```http
POST /api/v1/agents/{agent_id}/heartbeat
```

Request:

```yaml
worker_id:
lease_token:
presence_state:
task_id:
task_step_id:
model_route:
current_tool:
last_message_cursor:
progress:
health:
cost_delta:
runtime_version:
```

Response:

```yaml
server_time:
accepted:
agent_state:
lease:
new_tasks:
messages:
mentions:
approval_updates:
routine_triggers:
control_commands:
next_heartbeat_seconds:
```

The heartbeat must:

- never include credentials;
- validate worker and lease ownership;
- update presence and worker health transactionally;
- advance message receipts only when acknowledged;
- return bounded payloads;
- be idempotent;
- rate-limit abusive workers;
- preserve audit history.

## 9.2 Durable event log

Every material change emits an append-only event with:

```yaml
event_id:
event_type:
occurred_at:
recorded_at:
actor_type:
actor_id:
agent_id:
worker_id:
task_id:
task_step_id:
thread_id:
handoff_id:
committee_id:
approval_id:
research_case_id:
entity_ids:
book_id:
client_id:
model_route:
model_call_id:
tool_call_id:
artifact_ids:
status:
risk_class:
metadata:
```

Postgres is the replay authority. Redis may publish the same event for low-latency UI delivery.

## 9.3 Live stream

Add:

```http
GET /api/v1/office/events/stream?after_event_id=...
```

Use Server-Sent Events unless an existing WebSocket implementation is demonstrably better. Requirements:

- cursor/resume;
- heartbeat comments;
- bounded replay;
- authorization;
- backpressure;
- reconnect support;
- no PII leakage;
- snapshot fallback;
- no event loss when Redis restarts.

Keep the existing:

```text
GET /api/office/snapshot
```

as a compatibility and recovery snapshot. Replace the current 15-second-only experience with event-driven updates while retaining polling fallback.

**M2 exit gate:** Disconnect and reconnect the browser; it resumes from the last event or safely refreshes the snapshot without duplicate UI transitions.

---

# 10. Milestone M3 — Persistent messages, handoffs, rooms, and committees

## 10.1 Upgrade existing messaging

The existing `agent.agent_messages` and `agent.mailboxes` should be extended or wrapped rather than replaced.

Support:

- direct user-to-agent messages;
- agent-to-agent messages;
- Charlie delegation;
- department rooms;
- case rooms;
- strategy rooms;
- client-scoped rooms;
- committee rooms;
- incident rooms;
- approval threads;
- mentions;
- attachments;
- read and acknowledgement receipts;
- message cursoring;
- deduplication;
- retention and sensitivity classes.

## 10.2 Thread context

Every thread can link to:

```yaml
research_case_id:
company_id:
security_id:
portfolio_id:
book_id:
client_id:
strategy_id:
backtest_id:
options_case_id:
macro_scenario_id:
corporate_action_id:
approval_id:
incident_id:
```

Client-scoped threads must enforce isolation.

## 10.3 Handoffs

A handoff is not just a message.

State:

```text
REQUESTED
ACKNOWLEDGED
ACCEPTED
REJECTED
IN_PROGRESS
RETURNED
VALIDATED
CANCELLED
FAILED
```

Required fields:

```yaml
handoff_id:
from_agent_id:
to_agent_id:
parent_task_id:
child_task_id:
question:
expected_output_schema:
evidence_packet_ids:
artifact_ids:
due_at:
state:
acknowledged_at:
accepted_at:
returned_at:
validation_state:
```

Ownership changes only after acceptance. The parent plan waits on the child task or handles a rejection explicitly.

## 10.4 Committee rooms

Reuse existing committee records. Add real-time room/session projection:

- active members;
- required quorum;
- positions;
- evidence packets;
- dissent;
- pending questions;
- chair;
- human-final requirement;
- decision state;
- follow-ups;
- artifacts;
- start/end times.

## 10.5 Visible reasoning boundary

Messages may contain concise rationale and cited claims. They must not expose private hidden chain-of-thought.

**M3 exit gate:** A Company Analyst hands a cash-conversion question to the Forensic Analyst, which acknowledges, accepts, works, returns a cited artifact, and updates the parent Research Case and committee packet.

---

# 11. Milestone M4 — Charlie as chief of staff and universal control surface

## 11.1 Persisted command lifecycle

A significant Charlie request must create:

```text
OBJECTIVE
→ CONTEXT RESOLUTION
→ POLICY CLASSIFICATION
→ DURABLE PLAN
→ TASKS AND DEPENDENCIES
→ ASSIGNMENTS
→ HEARTBEAT-MONITORED EXECUTION
→ GAP CLOSURE
→ VALIDATION
→ OPTIONAL COMMITTEE
→ RESULT PACKET
→ OPTIONAL APPROVAL REQUEST
```

Persist:

- understood objective;
- entities;
- companies;
- portfolios/books/clients;
- plan version;
- tasks;
- dependencies;
- assigned agents;
- budgets;
- sources;
- calculations;
- approval class;
- result;
- uncertainty;
- missing data;
- next action.

## 11.2 Charlie commands

Implement and test natural commands such as:

```text
Charlie, show every live agent and what each is doing.
Charlie, ask the Forensic Analyst why Wipro cash conversion weakened.
Charlie, pause the Valuation Analyst.
Charlie, resume that task with primary sources only.
Charlie, redirect the Industry Analyst to compare Shivalik with its closest listed peers.
Charlie, invite Risk and Portfolio to the Wipro committee.
Charlie, stop all paid-model calls for this case.
Charlie, use the local research route for routine work and reserve the cloud route for red team.
Charlie, explain why this agent is blocked.
Charlie, show the artifact and citations produced by the last handoff.
```

## 11.3 User controls

Expose audited controls:

```http
POST /api/v1/agents/{agent_id}/message
POST /api/v1/tasks/{task_id}/pause
POST /api/v1/tasks/{task_id}/resume
POST /api/v1/tasks/{task_id}/redirect
POST /api/v1/tasks/{task_id}/cancel
POST /api/v1/handoffs
POST /api/v1/committees/{committee_id}/invite
```

Pause, redirect, cancel, and stop must respect safe points and side-effect state.

## 11.4 Charlie response contract

For significant work, Charlie returns:

```yaml
understood_objective:
context:
affected_entities:
affected_books_or_clients:
plan_id:
tasks:
agents:
current_state:
model_routes:
sources:
source_freshness:
calculations:
artifacts:
conclusion:
confidence:
bear_case:
dissent:
contradictions:
missing_data:
risk_flags:
approvals_needed:
memory_written:
next_action:
```

**M4 exit gate:** One Charlie command creates a durable multi-agent plan, the user redirects an active task, and Charlie returns a validated artifact without misreporting state.

---

# 12. Milestone M5 — Per-agent Model Fabric

Use OpenGrok as architectural inspiration only. Build the capability inside the existing AI OS model routes, assignments, cost caps, preflight, and audit system.

## 12.1 Canonical model request

Define one internal request:

```yaml
request_id:
agent_id:
task_id:
task_class:
model_binding_id:
messages:
retrieved_context_refs:
tools:
structured_output_schema:
reasoning_profile:
context_budget:
max_output_tokens:
temperature:
privacy_class:
contains_client_data:
public_only:
cloud_approved:
cost_ceiling:
prompt_version:
```

## 12.2 Model bindings

Bind by agent/role selector and task class:

```yaml
binding_id: research_forensics_default
agent_selector: research.forensics.*
task_classes:
  - filing_analysis
  - accounting_quality
primary_route: local_research
fallback_routes:
  - cloud_deep_research
reasoning_profile: high
context_budget: 8192
max_output_tokens: 1800
temperature: 0.1
required_evaluations:
  - finance_extraction_v2
  - citation_v2
  - missing_data_honesty_v2
  - prompt_injection_v2
fallback_policy: explicit_degraded
```

Do not put credentials in the binding.

## 12.3 Provider adapters

Implement a versioned provider adapter interface for the providers already used or actively approved in AI OS. At minimum support the actual local MLX/OpenAI-compatible route, Ollama where active, and the existing OpenRouter public-only route.

Adapter responsibilities:

- exact model slug;
- request-body transformation;
- reasoning/effort mapping;
- tool schema adaptation;
- structured-output handling;
- streaming parsing;
- usage parsing;
- error classification;
- identity probe;
- redaction;
- timeout;
- retry hints.

Do not claim a reasoning control works because the server returns HTTP 200. Prove the field or slug is behaviorally honored with a bounded test.

## 12.4 Secret shims

Where a provider needs credentials:

- bind on loopback;
- retrieve secret from Keychain or protected environment;
- inject authorization;
- redact headers and body;
- expose a safe `/healthz`;
- separate credential/trust domains;
- do not wake metered upstreams for every local health check;
- include a negative auth control.

## 12.5 Route qualification

A route is qualified per task class, not globally.

Record:

- model/version/revision;
- provider adapter version;
- runtime version;
- test packet;
- citation score;
- numeric score;
- structured-output score;
- unsupported-claim rate;
- tool-call accuracy;
- prompt-injection result;
- latency;
- memory;
- cost;
- human reviewer;
- approval state;
- expiration/retest date.

Preserve the Research Desk rule that no score automatically promotes a paid lead model without named human review.

## 12.6 Failover

On failure:

1. classify retryable versus non-retryable;
2. retry once when safe;
3. consult binding fallback;
4. verify fallback health and qualification;
5. enforce data/privacy/cost policy;
6. mark output degraded/fallback;
7. block high-consequence completion when requirements are not met;
8. never fall through to a generic global provider.

## 12.7 Model console

Build a System → Model Fabric page showing:

- agent or role selector;
- task class;
- binding version;
- primary and fallback route;
- provider/model;
- reasoning profile;
- context/output limits;
- privacy eligibility;
- cost cap;
- qualification;
- last health probe;
- median latency;
- active calls;
- failure rate;
- test button;
- compare button;
- promote/rollback;
- audit history.

Changes are versioned, atomic, validated, and approval-gated where required.

**M5 exit gate:** Change one Research Desk agent to another qualified route, run a bounded task, record the resolved route, then stop that route and prove explicit fail-closed or approved fallback behavior.

---

# 13. Milestone M6 — AI OS Doctor and drift detection

Deliver:

```text
_ai_os_runtime/scripts/ai_os_doctor.py
```

or an equivalent first-class command.

Modes:

```text
ai_os_doctor
ai_os_doctor --json
ai_os_doctor --quiet
ai_os_doctor --init-baseline
ai_os_doctor --safe-fix
ai_os_doctor --component zerodha
ai_os_doctor --component obsidian
ai_os_doctor --agent <agent_key>
ai_os_doctor --model-route <route>
```

Expose a read-only API and UI using the same checks.

Check:

- API liveness and readiness;
- Postgres connection and migration level;
- Redis;
- Qdrant;
- external SSD mount, free space, and expected directories;
- Obsidian vault, index lag, broken managed blocks, and unresolved links;
- current backup and restore-drill receipt;
- agent worker services;
- worker heartbeat age;
- stale leases;
- queue lag;
- failed/retrying tasks;
- message backlog;
- routine scheduler;
- last routine run;
- model endpoint liveness;
- model identity;
- provider adapter version;
- route binding integrity;
- qualification freshness;
- cost-cap configuration;
- Zerodha API key presence without revealing it;
- daily token state;
- account binding;
- WebSocket process and heartbeat;
- quote freshness;
- `broker_write_allowed=false`;
- TradingView connectors;
- Pythia where installed;
- UI asset equality;
- launchd services;
- watched-file hashes;
- configuration drift;
- kill switch;
- client isolation checks;
- secret-pattern scan of changed files.

A safe fix may:

- restart an approved dead local service;
- reindex Obsidian;
- recreate a cache;
- release an expired lease;
- reinstall a known launchd plist;
- refresh a safe read-only connector.

A safe fix may not:

- rotate credentials;
- approve a model;
- publish a scanner;
- alter client data;
- drop data;
- place a trade;
- disable safety locks.

Positive controls:

- kill a test listener and prove detection;
- create an expired fixture lease and prove detection;
- break a test binding and prove detection.

Negative controls:

- unauthenticated provider request must fail;
- broker-write check must remain false;
- a client-scope violation must be denied.

**M6 exit gate:** Doctor detects and correctly classifies at least one dead model route, one expired lease, one stale quote condition, and one Obsidian index lag, with actionable fixes and no secret leakage.

---

# 14. Milestone M7 — Skills and routines

## 14.1 Skill contract

Use or extend the existing skill registry.

A skill version contains:

```text
SKILL.md
manifest.yaml
input.schema.json
output.schema.json
policy.yaml
tests/
fixtures/
references/
implementation/
LICENSES.md
```

It records:

- owner;
- version;
- triggers/use cases;
- inputs;
- tools;
- sources;
- deterministic calculations;
- permissions;
- stale/no-data behavior;
- idempotency;
- outputs;
- approval class;
- evaluation;
- rollback.

## 14.2 Routine contract

A routine binds:

```yaml
routine_id:
owner_agent_id:
skill_version_id:
trigger:
input_policy:
schedule_or_event_filter:
idempotency_key:
timeout:
retry_policy:
cost_budget:
stale_data_policy:
approval_policy:
output_destinations:
enabled:
```

## 14.3 Deliver a small verified routine set

At minimum:

1. `daily_system_health`
   - owned by Jarvis/SRE;
   - runs Doctor;
   - creates alerts only for actionable degradation.

2. `obsidian_incremental_index`
   - reindexes changed notes and artifacts;
   - preserves human content;
   - records counts and failures.

3. `research_company_change_monitor`
   - uses existing Research Desk monitoring;
   - updates evidence and thesis drift;
   - no paid model without preflight.

4. `stale_task_and_lease_reaper`
   - safely detects and recovers expired leases;
   - never duplicates completed side effects.

5. `zerodha_session_and_stream_watch`
   - reports daily login requirement and freshness;
   - never accesses or exposes the secret itself.

Do not build uncontrolled natural-language schedules in this phase. Parse to a draft, show the resolved trigger and permission class, and require approval before enabling.

**M7 exit gate:** A real or fixture-safe filing event triggers exactly one company-monitor routine, writes a durable run and artifact, and does not retrigger on the same event hash.

---

# 15. Milestone M8 — Truthful 2D and 3D office

## 15.1 Preserve the current frontend

Extend:

```text
_ai_os_runtime/ai-office-ui/src/office3d/LiveOffice.tsx
_ai_os_runtime/ai-office-ui/src/office3d/LiveOffice.css.ts
_ai_os_runtime/ai-office-ui/src/office3d/officeLayout.ts
_ai_os_runtime/ai-office-ui/src/data/queries.ts
_ai_os_runtime/ai-office-ui/src/data/actions.ts
_ai_os_runtime/ai-office-ui/src/data/schemas.ts
```

Do not replace the office with another UI framework.

## 15.2 Data flow

Use:

- live event stream for low-latency updates;
- `/api/office/snapshot` for initial load and recovery;
- Postgres event log for replay;
- Redis only as optional event acceleration.

## 15.3 Agent hover card

Show real:

- display name;
- role;
- department;
- online/idle/working/stale/blocked state;
- active task;
- company/strategy/portfolio/client scope;
- exact current step;
- elapsed time;
- progress;
- model route and model;
- current tool;
- source count;
- task cost;
- blocker;
- last artifact;
- next routine.

## 15.4 Agent click panel

Provide:

- profile and role charter;
- current plan;
- task/step timeline;
- direct chat;
- messages;
- handoffs;
- sources and evidence;
- artifacts;
- model calls;
- tool calls;
- costs;
- approvals;
- incidents;
- routines;
- scorecard;
- pause/resume/redirect/cancel controls where allowed.

## 15.5 Visual truth

- Working animation requires a live lease.
- A handoff animation requires a handoff event.
- A committee light requires an active committee session.
- An approval badge requires an unresolved approval.
- Amber means waiting, stale data, or budget pressure.
- Red means failed, blocked, quarantined, or risk-rejected.
- Green completion appears only after validation.
- A model badge displays the resolved route, not merely the default profile route.
- Speech bubbles display actual concise messages, never invented commentary.
- Screens use sanitized data and no client PII.
- Scene state can be replayed from events.

## 15.6 2D parity

Deliver:

- department grid;
- agent directory;
- task table;
- live activity feed;
- committee panel;
- approvals panel;
- keyboard navigation;
- screen-reader labels;
- reduced motion;
- low-power mode;
- mobile office feed.

No decision-critical control may exist only in WebGL.

## 15.7 M4 performance

Measure:

- initial load;
- event latency;
- CPU/GPU;
- memory;
- FPS;
- battery/thermal impact;
- browser tab background behavior.

Use adaptive DPR, instancing where appropriate, bounded HTML overlays, lazy-loaded detail panels, and a low-power setting.

**M8 exit gate:** A user watches a real Research Desk handoff in the office, clicks both agents, sees the exact message, task, source, model, cost, and artifact, redirects the child task, and receives the updated result. The same flow works in 2D.

---

# 16. Milestone M9 — Cross-desk agent foundation

Create or normalize durable profiles, room mappings, and capability policies for the core organization.

At minimum:

## Executive and operations

- Charlie — Chief of Staff and universal assistant
- Jarvis — Runtime operator
- Chief Investment Officer
- Chief Risk Officer
- Chief Data Officer
- Chief Operating Officer
- Compliance/Policy Officer
- Platform SRE
- Incident Manager

## Research

- Research Director
- Company Analyst
- Filing/Evidence Analyst
- Financial Statement Analyst
- Industry/TAM Analyst
- Moat Analyst
- Management/Capital Allocation Analyst
- Governance/Forensics Analyst
- Valuation Analyst
- Bear/Red-Team Analyst
- Research Editor
- Monitoring Analyst

## Portfolio and clients

- Portfolio Manager
- Client Mandate Analyst
- Holdings/Cash Reconciler
- Tax-Lot Analyst
- Performance Analyst
- Attribution Analyst
- Exposure/Concentration Analyst
- Liquidity Analyst
- Capital Allocation Analyst
- Client Reporting Analyst

## Markets and TradingView

- Market Data Steward
- Technical Analyst
- TradingView Operator
- Scanner Operator

## Quant

- Head of Quant
- Alpha Researcher
- Feature Engineer
- Backtest Engineer
- Cost/Slippage Modeler
- Optimizer
- Walk-Forward Validator
- Overfit Auditor
- Paper Strategy Monitor

## Options

- Head of Volatility
- Chain/Surface Analyst
- Greeks/Risk Analyst
- Flow Analyst
- Strategy Designer
- Options Backtest Engineer
- Hedge Designer

## Macro

- Chief Economist
- India Macro Analyst
- Rates Analyst
- FX Analyst
- Commodities Analyst
- Credit/Liquidity Analyst
- Geopolitical/Pythia Analyst
- Macro-to-Portfolio Analyst

## Corporate actions

- Event Classifier
- Legal/Condition Analyst
- Entitlement Analyst
- Spread/IRR Analyst
- Completion Probability Analyst
- Event Monitor

## Trading and execution

- Market Monitor
- Order Intent Builder
- Pre-Trade Risk Agent
- Paper Broker Agent
- Fill/Reconciliation Agent
- Execution Quality Analyst

Register identity and permissions only where domain functionality is not yet implemented. An idle registered agent may appear as `IDLE`; it may not pretend to perform missing work.

**M9 exit gate:** Every active profile appears in the correct 2D/3D room, with truthful availability and capability status. No unimplemented desk is labelled complete.

---

# 17. APIs and MCP surface

Implement or adapt versioned endpoints similar to:

```text
GET  /api/v1/agents
GET  /api/v1/agents/{agent_id}
GET  /api/v1/agents/{agent_id}/presence
GET  /api/v1/agents/{agent_id}/tasks
GET  /api/v1/agents/{agent_id}/threads
GET  /api/v1/agents/{agent_id}/routines
GET  /api/v1/agents/{agent_id}/scorecard

POST /api/v1/agents/{agent_id}/heartbeat
POST /api/v1/agents/{agent_id}/message

GET  /api/v1/workers
GET  /api/v1/tasks
GET  /api/v1/tasks/{task_id}
POST /api/v1/tasks/{task_id}/claim
POST /api/v1/tasks/{task_id}/pause
POST /api/v1/tasks/{task_id}/resume
POST /api/v1/tasks/{task_id}/redirect
POST /api/v1/tasks/{task_id}/cancel

GET  /api/v1/threads/{thread_id}
POST /api/v1/threads
POST /api/v1/threads/{thread_id}/messages
POST /api/v1/messages/{message_id}/ack

POST /api/v1/handoffs
POST /api/v1/handoffs/{handoff_id}/acknowledge
POST /api/v1/handoffs/{handoff_id}/accept
POST /api/v1/handoffs/{handoff_id}/return
POST /api/v1/handoffs/{handoff_id}/validate

GET  /api/v1/committees/active
GET  /api/v1/approvals/open

GET  /api/v1/model-bindings
POST /api/v1/model-bindings/test
POST /api/v1/model-bindings/compare
POST /api/v1/model-bindings/promote
POST /api/v1/model-bindings/rollback

GET  /api/v1/routines
POST /api/v1/routines/{routine_id}/test
POST /api/v1/routines/{routine_id}/enable
POST /api/v1/routines/{routine_id}/pause

GET  /api/v1/system/doctor
GET  /api/v1/office/snapshot
GET  /api/v1/office/events/stream
```

Keep compatibility aliases for existing callers.

Expose a focused MCP surface for:

- list agents;
- inspect agent;
- send agent message;
- list tasks;
- pause/resume/redirect task;
- create handoff;
- inspect committee;
- inspect model binding;
- run a safe model route test;
- run Doctor;
- list routines;
- run a safe routine test;
- inspect office activity.

Every write is risk-classed, idempotent, audited, and cannot place a broker order.

---

# 18. Security and client isolation

## 18.1 Authorization

Use the existing authenticated local/Tailscale environment. Add explicit authorization context:

```yaml
user_id:
agent_id:
worker_id:
role:
allowed_books:
allowed_clients:
allowed_data_classes:
allowed_actions:
request_id:
```

## 18.2 Client isolation

Before client-facing expansion, make the Agent OS compatible with:

- row-level security or explicit policy-filtered views;
- client-scoped threads;
- client-scoped artifacts;
- redacted model packets;
- no cross-client semantic retrieval;
- per-client report permissions;
- audit of denied attempts.

Include a test client fixture. Never expose real client PII in repository fixtures or model-provider tests.

## 18.3 Browser and application automation

This phase may inspect or operate only already-approved internal/read-only connectors. It must not silently grant:

- email send;
- social posting;
- TradingView writes;
- broker writes;
- filesystem-wide access;
- credential access.

## 18.4 External project policy

Study but do not wholesale install:

- `OnlyTerp/opengrok`
- `HKUDS/AI-Trader`
- `xai-org/grok-build`
- Grok Bot product documentation

Record exact commit/revision, license, useful patterns, rejected patterns, network behavior, and copied-code status.

Do not copy AI-Trader source unless its license is independently verified and a license review explicitly permits it.

---

# 19. Testing requirements

## 19.1 Database and contract tests

Test:

- migration replay;
- no destructive schema change;
- stable agent identity;
- compatibility with existing name-based agents;
- unique active task lease;
- lease expiry;
- stale worker;
- safe recovery;
- legal and illegal state transitions;
- task dependency behavior;
- message dedupe;
- message cursors;
- acknowledgement;
- handoff ownership;
- committee projection;
- model binding versioning;
- route qualification;
- fallback;
- cost caps;
- routine idempotency;
- event ordering;
- replay;
- client isolation;
- `broker_write_allowed=false`.

## 19.2 Concurrency tests

- Two workers race for one task.
- One worker heartbeats late.
- Worker dies during a read-only step.
- Worker dies after an artifact is committed but before task completion.
- Duplicate heartbeat.
- Duplicate message.
- Duplicate event trigger.
- Browser reconnect.
- Redis restart.
- Database transaction rollback.

## 19.3 Model tests

- exact route resolution;
- model identity;
- reasoning-control adapter behavior;
- structured output;
- tool schema;
- citation packet;
- fail-closed fallback;
- provider timeout;
- 401/403;
- 429;
- 5xx;
- malformed stream;
- usage parsing;
- secret redaction;
- cost calculation;
- unqualified route denial.

## 19.4 UI and browser tests

Use real browser tests for:

- office initial snapshot;
- live SSE update;
- reconnect;
- 2D/3D parity;
- agent hover/click;
- direct chat;
- pause/resume/redirect;
- handoff;
- committee;
- model picker;
- Doctor;
- routine test;
- blocked/degraded state;
- 390 px layout;
- keyboard navigation;
- reduced motion;
- no console errors;
- no fake data.

## 19.5 Performance and soak

Test at least:

```text
100 logical agents
4 active workers
1–2 concurrent local model calls maximum
1,000 queued tasks
10,000 office events
100 concurrent browser/SSE reconnects in synthetic test where practical
24-hour routine/worker soak on the iMac
```

Keep the M4 16 GB machine usable.

## 19.6 Failure injection

Inject:

- dead worker;
- stale heartbeat;
- expired lease;
- model route down;
- model identity mismatch;
- Zerodha token expired;
- stale quote;
- Redis down;
- Qdrant down;
- external SSD unavailable;
- Obsidian index failure;
- malformed message;
- unauthorized client access;
- invalid state transition;
- duplicate trigger;
- approval mismatch.

---

# 20. Required end-to-end acceptance demonstrations

Do not claim completion until all demonstrations are recorded with IDs, timestamps, screenshots or browser traces, database queries, artifact hashes, and test commands.

## Demo 1 — Durable agent across restart

Restart API, worker, and UI. The same Research Director and Forensic Analyst retain:

- stable identities;
- role;
- model binding;
- conversation;
- tasks;
- routine ownership;
- artifacts;
- last presence;
- incident history.

## Demo 2 — Worker death and task recovery

Start a bounded Research Desk task. Kill the worker mid-step.

Expected:

- heartbeat expires;
- worker and agent state become stale/degraded;
- lease expires;
- task is safely reclaimed or blocked;
- no duplicate artifact or paid model call;
- event history explains the recovery;
- office shows the transition.

## Demo 3 — Talk to a specialist

From the office, message the Forensic Analyst:

```text
Explain what you are checking in Wipro cash conversion and show the source packet.
```

The reply must be case-aware, cited, and linked to the task.

## Demo 4 — Handoff

Company Analyst hands the question to Forensics, which acknowledges, accepts, works, returns, and gets validated.

## Demo 5 — Redirect

While a task is active:

```text
Use only primary filings and stop acquiring secondary commentary.
```

The plan changes safely and the office shows the redirect event.

## Demo 6 — Charlie chief-of-staff flow

```text
Charlie, review the current Wipro evidence debt, ask the right specialists for a bounded repair plan, use no paid model without approval, and return the plan with exact blockers.
```

Charlie creates a durable plan and returns actual state.

## Demo 7 — Model binding

Switch one safe public Research Desk task from the default local route to another qualified test route, run it, and record the exact resolved model. Roll back atomically.

## Demo 8 — Fail closed

Stop the bound model route. Prove the task either uses an explicitly qualified fallback with a degraded label or blocks. It must not silently use a global default.

## Demo 9 — Doctor

Prove Doctor detects:

- one dead route;
- one expired lease;
- one stale Zerodha condition;
- one Obsidian/Qdrant index lag;
- broker writes still disabled.

## Demo 10 — Routine

A unique test filing/event hash triggers exactly one monitor routine and produces one durable artifact and Obsidian update.

## Demo 11 — 3D/2D truth

The same active task, messages, handoff, model route, blocker, cost, and artifact appear in both views.

## Demo 12 — No broker path

Enumerate API and MCP tools and prove no place/modify/cancel live-order capability was introduced.

---

# 21. Definition of done

Phase 2 is complete only when:

## Agent runtime

- Stable machine agent IDs exist.
- Worker identity is separate from agent identity.
- Heartbeats and leases work.
- Worker death is recovered safely.
- State transitions are validated.
- Event replay reconstructs the current state.
- Messages and handoffs are durable.
- Agent chat works.
- Pause/resume/redirect/cancel work at safe points.
- Committees and approvals project into agent state.

## Model Fabric

- Per-agent/task-class bindings work.
- Existing model routes and cost policies are reused.
- Provider adapter behavior is tested.
- Credentials stay outside bindings.
- Route tests and identity checks work.
- Failover is explicit and fail closed.
- Model changes are versioned and rollbackable.
- No automatic promotion bypasses human review.

## Doctor

- One command and API expose real health.
- Positive and negative controls prove the checks are meaningful.
- Safe fixes cannot weaken policy or authorize financial action.
- Drift baselines work.

## Skills and routines

- At least five real bounded routines work.
- Every run has owner, input, idempotency, cost, output, and state.
- Duplicate triggers do not duplicate work.
- Stale/no-data behavior is explicit.

## Charlie

- One command creates a durable multi-agent plan.
- Charlie preserves company/case/book/client context.
- Charlie can monitor and redirect.
- Charlie reports actual state.
- Charlie stops at approval boundaries.

## Office

- Every active agent is mapped to a real profile.
- Working states require live leases.
- Model/tool/task/progress/cost/blocker data are real.
- Messages and handoffs are visible.
- 2D parity exists.
- The office performs acceptably on the M4.
- No fake activity exists.

## Regression and safety

- The accepted Research Desk remains operational.
- Zerodha remains read-only and healthy when authenticated.
- Postgres/Obsidian/Qdrant boundaries are preserved.
- Client isolation tests pass.
- Broker writes remain disabled.
- Full backend and frontend tests pass.
- Browser acceptance passes.
- Dependency and secret scans pass.
- Live deployment and asset equality are verified.
- Documentation and Obsidian notes are current.

---

# 22. Suggested commit sequence

Use focused commits resembling:

```text
chore(agent-os): capture accepted baseline and compatibility map
feat(db): add durable agent identity worker heartbeat and lease contracts
feat(runtime): implement worker heartbeat leases and stale recovery
feat(events): add append-only agent event stream and replay
feat(messages): add persistent threads receipts mentions and handoffs
feat(charlie): add durable chief-of-staff plans and task controls
feat(models): add per-agent model bindings and provider adapters
feat(models): add model route probes qualification and fail-closed fallback
feat(doctor): add AI OS doctor drift checks and safe repair
feat(routines): add versioned skills and bounded routine scheduler
feat(api): expose agent message model routine and office contracts
feat(mcp): expose audited Agent OS tools
feat(ui): add agent directory task message model and doctor surfaces
feat(office): project live presence handoffs and committees into 3D and 2D
feat(test): add concurrency recovery routing and browser acceptance
docs(agent-os): record live acceptance and operator runbook
```

Do not place the entire phase in one monolithic API file. Move domain logic behind modules/services while keeping compatibility routes.

---

# 23. How to report progress

After each milestone:

1. Update `IMPLEMENTATION_STATUS.md`.
2. Write a concise Obsidian implementation note.
3. List files changed.
4. List migrations.
5. Show exact tests and results.
6. Show live/runtime verification performed.
7. Show unresolved blockers.
8. Commit the milestone.
9. Continue to the next unverified milestone.

When finished, return:

```yaml
branch:
starting_commit:
final_commit:
live_deployed_commit:
migrations:
services_added_or_changed:
agents_migrated:
workers:
heartbeats:
leases:
messages:
handoffs:
model_bindings:
doctor_checks:
routines:
office_surfaces:
tests:
browser_acceptance:
performance:
zerodha_guardrail:
broker_write_allowed:
research_desk_regression:
residual_gates:
artifacts:
obsidian_notes:
```

Do not claim “complete” from code presence alone.

---

# 24. Stop conditions

Stop and ask for human input only when:

- a real credential or official login is required;
- a paid model run requires approval;
- a licensed source requires entitlement;
- a destructive data operation is unavoidable;
- a production deployment needs explicit approval;
- a model promotion requires named human review;
- a client-data policy decision is genuinely ambiguous;
- a financial action or broker write is requested.

Do not stop for routine implementation choices that can be resolved from this prompt, the blueprint, current code, tests, and existing conventions.

---

# 25. Final instruction

Begin now with the read-only baseline audit. Verify the accepted Research Desk branch and live deployment, create the focused feature branch, write the implementation ledger, then implement the first unverified milestone.

Do not return only a plan. Build, test, document, deploy safely, and prove the Living Agent Operating System end to end.

# COPY-PASTE PROMPT ENDS HERE
