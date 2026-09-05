# M6/M7 Doctor and routines — implementation evidence

Date: 2026-09-05

Scope: migration 260, deterministic API helpers, operator CLIs, focused tests,
and runbooks only.

## Delivered

- `260_ai_os_doctor_and_routines_v1.sql`
  - 21-check Doctor registry, durable runs/results, last-known-good evidence,
    reviewed baselines and safe-fix receipts;
  - five routine definitions with immutable version history, durable run/control
    receipts and read views;
  - reuses `agent.workflow_schedules`; all five schedules and definitions start
    disabled; enabling an event routine keeps periodic materialization disabled;
  - zero autonomous model budget and database constraints keeping broker,
    external and client writes false;
  - event hash and durable artifact path constraints.
- `doctor_runtime.py`
  - fixed check handlers over canonical database views plus injected bounded
    local probes;
  - redaction of credential-shaped keys and values;
  - unknown evidence remains unknown;
  - config-baseline drift comparison;
  - model provider/model/endpoint identity, adapter/runtime version,
    qualification freshness, active-agent binding and cost-cap checks;
  - only `agent.reap_runtime_leases` is allowlisted as a safe fix.
- `routine_runtime.py`
  - fixed five-routine/tool allowlist;
  - explicit control confirmation;
  - disabled-state refusal for real runs;
  - exact-once event/schedule keys and fail-closed receipts;
  - reuse of Doctor, existing company monitor, existing Obsidian indexer and
    existing lease reaper.
- `ai_os_doctor.py` and `run_ai_os_routine.py`
  - first-class operator commands;
  - host/container Postgres adapter without returning credentials;
  - bounded local health probes and external-SSD-only routine artifacts;
  - stable safe filing fixture.

## Verified controls

Focused automated tests cover:

- secret value redaction while preserving boolean presence;
- missing probe is unknown, never healthy;
- config baseline missing/different/initialization states;
- optional Pythia skipped state;
- market-hours stale Zerodha quote failure with broker writes false;
- dead, unqualified and identity-drifted model route failures;
- Obsidian lag/unresolved link failure;
- expired lease detection and receipt-backed allowlisted recovery;
- disabled routine refusal and explicit enable confirmation;
- schedule-only materialization with event handling enabled independently;
- event hash requirement and stable canonical hashing;
- one handler/artifact for the first filing fixture and suppression of the
  duplicate event hash;
- company-monitor failure when no durable artifact writer exists;
- scheduled-run `due_at`, fixed tool allowlist and unknown routine refusal;
- migration reuse of the existing scheduler, immutable versions and zero-cost,
  no-broker/no-client/no-external-write constraints;
- CLI modes and refusal of an unrelated/internal artifact root.

The focused suite result is recorded at handoff as `25 passed`.

## Disposable PostgreSQL verification

Migration 260 was applied and replayed in an isolated local PostgreSQL database
with synthetic canonical prerequisites. The SQL verification transaction proved
21 checks, five routines, explicit control confirmation, immutable published
versions, zero-cost/no-write constraints, event-only enablement with its periodic
schedule disabled, and exact-once filing-event suppression. Replay preserved a
later routine version and operator control state. This is migration-level proof,
not canonical iMac deployment proof.

## Zerodha preservation

No protected Zerodha implementation, launch service, authentication flow or
credential storage file is edited. Doctor/routines read only the existing
canonical health/readiness views. They do not introduce market-data ingestion,
subscription management or any order capability.

## Not delivered or accepted by this isolated slice

- HTTP route wiring for `/api/v1/system/doctor` and `/api/v1/routines*`;
- MCP command wiring;
- daemon dispatch from materialized schedule work into `RoutineRuntime`;
- Doctor/routine panels in the 2D or 3D UI;
- a managed Obsidian note projection for the filing fixture;
- canonical iMac migration/deployment, runtime check, browser acceptance or
  24-hour worker/routine soak;
- any service restart, connector refresh, credential action, paid model call,
  client mutation or broker write.

Those items require shared integration work and live acceptance. This evidence
therefore supports completion of the isolated M6/M7 runtime slice, not a claim
that the full Phase 2 product milestone is live.
