# Skills and routines — M7 bounded runtime standard

Migration 260 adds five immutable, versioned routine contracts on the existing
`agent.workflow_schedules` authority. It creates no second scheduler. Every
routine and schedule is seeded disabled; migration replay preserves a later
explicit operator decision instead of silently resetting it.

The runtime uses a fixed routine-to-tool allowlist. It executes no arbitrary
natural-language schedule, paid model, provider fetch, credential action,
external/client write, or broker write.

## Routine contracts

| Routine | Owner | Trigger | Reviewed action |
| --- | --- | --- | --- |
| `daily_system_health` | Jarvis | schedule/manual | Run the same Doctor registry; return only actionable degradation. |
| `obsidian_incremental_index` | Librarian Agent | schedule/manual | Invoke the existing bounded indexer; preserve human-authored content. |
| `research_company_change_monitor` | Research Director | event only | Reuse the existing stored-source company monitor; no fetching or paid model. |
| `stale_task_and_lease_reaper` | DevOps Engineer | schedule/manual | Call the existing receipt-aware lease reaper. |
| `zerodha_session_and_stream_watch` | Jarvis | schedule/manual | Read canonical Zerodha health and freshness; daily login stays human-owned. |

Each version persists trigger/filter, input policy, idempotency template,
permission class, timeout, cooldown, retries, zero-dollar model budget,
stale/no-data policy, approval policy, outputs, allowed tool and immutable
definition hash. Control state and audit events are separate from immutable
version history.

## Operator controls

List definitions and run history:

```bash
python3 _ai_os_runtime/scripts/run_ai_os_routine.py --list
python3 _ai_os_runtime/scripts/run_ai_os_routine.py --history
python3 _ai_os_runtime/scripts/run_ai_os_routine.py --history --routine daily_system_health
```

Test mode persists a receipt but may run while disabled because all external and
paid actions remain blocked:

```bash
python3 _ai_os_runtime/scripts/run_ai_os_routine.py \
  --test --routine daily_system_health --json
```

Enabling, pausing or disabling requires the exact routine, an explicit
confirmation and an auditable reason:

```bash
python3 _ai_os_runtime/scripts/run_ai_os_routine.py \
  --enable --routine daily_system_health --confirm \
  --reason "Reviewed health schedule and alert ownership"
```

The control function updates the routine and its existing schedule atomically.
Schedule routines enable canonical scheduler materialization. Event routines
enable event handling while their periodic schedule row remains disabled, so a
filing cannot accidentally create a timer-driven monitor run.

## Idempotency and event fixtures

Event routines require a lowercase SHA-256 event hash in both Python and
Postgres. `agent.routine_runs` has a unique `(routine_key,idempotency_key)`
constraint. A duplicate receives the original receipt and does not invoke the
handler or write another artifact.

The stable safe filing fixture is:

```bash
python3 _ai_os_runtime/scripts/run_ai_os_routine.py --fixture-filing --json
```

Its result artifact is written atomically below:

```text
/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/research_company_change_monitor/
```

The script refuses an internal-disk or unrelated artifact root. Test the fixture
twice: the first call must show `handler_invoked=true`; the second must show
`duplicate_suppressed=true` and `handler_invoked=false`.

Scheduled routines require a stable `due_at`; manual routines derive a bounded
idempotency key from their redacted payload. The company monitor accepts only an
event trigger. Uncertain or failed work records a terminal failed receipt and is
not silently replayed.

## Hard boundaries

- model cost is exactly zero for every autonomous routine version and run;
- no routine promotes a route or makes an investment decision;
- no routine reads/changes Zerodha credentials or automates daily login;
- no routine places, modifies or cancels an order;
- no routine writes client data or any external system;
- stale/no-data states remain explicit; no value is inferred or zero-filled;
- published versions cannot be edited or deleted; changes require a new version.

## Remaining integration and live gates

The runtime helper and CLI are implemented and covered by exact-once and refusal
tests. The shared API routes, MCP tools, daemon dispatch from materialized
schedules, 2D/3D UI projections, fixture-to-managed-Obsidian-note adapter and
24-hour iMac soak are intentionally outside this isolated slice and remain
unaccepted. Until those are wired and verified, do not claim the full M7 product
milestone or its live demo complete.
