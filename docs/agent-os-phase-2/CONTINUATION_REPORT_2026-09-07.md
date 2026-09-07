# Phase 2 continuation and release evidence — 7 September 2026

> Superseded checkpoint: use [the final deployed implementation and acceptance ledger](FINAL_ACCEPTANCE_2026-09-07.md) for current test counts, live receipts and remaining gates.

Verdict at this checkpoint: **PHASE_2_INCOMPLETE**. Implementation is ready for the remaining live acceptance gates; deployment and time-based acceptance are recorded below only after verification. Phase 3 has not started.

## Delivered behavior

| Area | What now works | Evidence / limitation |
|---|---|---|
| Durable runtime | Stable agent identities, role/policy snapshots, fenced ownership, configurable heartbeat/lease intervals, safe-boundary controls, receipt-preserving recovery, drain/cutover | Actual disposable PostgreSQL ownership, expiry, output, role, scope and migration tests |
| Events | Typed bounded metadata, private-scope filtering, PostgreSQL replay, reset/backpressure and retention | 100 HTTP event-stream clients recovered; database lock timeout stopped further writes |
| Messages and handoffs | Existing message authority gains threads, acknowledgements, handoff lifecycle, scoped recovery and validated evidence propagation into parent task, research case and committee | Wipro synthetic chain passes; case decision status is preserved |
| Charlie | Persisted commands/objectives/plans, evidence-debt repair plans, blocker explanations and specialist controls | Exact command regressions; queued work remains queued until performed |
| Model Fabric | Versioned bindings, exact identity probes, provider adaptation, qualification, named review, explicit fallback, disable and rollback | Local HTTP behavioral probes pass; no paid route auto-promoted; live model-switch demo remains required |
| Doctor | CLI/API/UI check registry, bounded component checks, drift evidence and allowlisted expired-lease repair | Positive/negative tests for stale quotes, missing routes, index lag, unknown evidence and denied unsafe repair |
| Routines | Five versioned routines on existing schedule authority, disabled by default | Health, index, company updates, stale lease reaper, Zerodha watch |
| Company following | Existing authorized stored update triggers one event/run/artifact and a managed Obsidian block | Real PostgreSQL duplicate/restart tests; human text preserved; path escape/symlink rejected; failed projection retried |
| Office | Shared 2D/3D inspector, pause/resume/cancel/primary-only redirect, real handoff connections, model history and reviewed promotion | 16 production-build browser tests; six desktop/mobile accessibility checks; rendered 3D pixels verified |

## Verification receipts

- Full backend suite: **768 passed, 178 subtests passed**, no skips, in 17.67 seconds with the restore-role integration enabled. Subsequent live-integration corrections have their own focused regressions and require a final full rerun.
- Restore-role integration passed after correcting its subprocess log destination. Its original captured pipe held the test open; the fix changes only the disposable test harness.
- Notes-root correction: four focused tests passed, including parent-root and already-vault-root configuration.
- UI: **16/16** browser tests passed; TypeScript/Vite production build passed (764 modules); production dependency audit found **zero vulnerabilities**.
- Stress: **100 agents, four workers, 1,000 exactly-once task claims, 10,000 typed events, 100 durable replay checks**, no provider/model/external writes; 1.062 seconds total on the isolated test host. This is not a 24-hour live soak.
- Seven protected Zerodha integration files have no diff from `b42cc5d`. Broker write authority remains false.
- The previously missing bundled Python runtime was replaced only for local testing with an isolated Python 3.12 environment under `/private/tmp`; no production Python was replaced.

## Live release record

- Canonical iMac rechecked on 7 September: reachable, SSD mounted, Postgres/Redis healthy, API `ok=true`.
- Previous release: `/Users/devarshthakkar/AI_OS_NODE/releases/a02ee0f-live`, commit and marker `b42cc5d028f37ec2ead6b10296235d19bc9a5fd6`.
- Its existing dirty files are generated import summaries, human vault edits and untracked QA/research artifacts. They remain in place; no tracked application source change was overwritten.
- Fresh backup regenerated with the deployed release's format-v2 tool. The older source-checkout backup command produced an obsolete manifest; rehearsal refused it before any production migration.
- Migration rehearsal passed: `restore-drill-20260907T123034Z-65119`, migrations 256–264 twice in a rolled-back transaction, vault byte-identical, 936 tables, 3 clients and 72 positions preserved.
- Release `7ba12e925ce81df494665217e8ce63b7dccc69a5` deployed at `/Users/devarshthakkar/AI_OS_NODE/releases/phase2-7ba12e9`; Git HEAD, deployment marker and API runtime root agree. Live build and `IMAC_BACKEND_VERIFIED` passed, execution remains locked.
- Live runtime lists 101 agents. Doctor/Routines/Model Fabric endpoints are available. Five routines are disabled and Model Fabric contains no activated bindings; this is not autonomous-work acceptance.
- Live canary exposed a legacy migration-100 provider-gate collision with fenced task insertion. Both failed attempts rolled back their synthetic tasks; cleanup confirmed disabled claims and zero active canary leases. Migration 265 is being verified against the actual legacy trigger.
- Live Office exposed excessive combined legacy-view query latency. A bounded partial-read correction is under verification; an HTTP health pass alone does not accept the UI.
- Unrun Doctor checks exposed missing registry labels; migration 266 is under verification. Observation soak has not started while these live corrections are pending.

## Remaining acceptance gates

- Exact migration replay/restore receipt, production migration and release marker equality.
- Canonical live lease canary, Research Desk regression, Redis restart/replay and Office/API/MCP checks.
- Real qualified model binding switch/run/stop/fallback demonstration; no paid invocation or promotion without its required approval and named review.
- Safari/operator workflow and real iMac CPU/GPU/memory/FPS/thermal measurements.
- Market-hours Zerodha freshness; stale quotes must remain visibly stale.
- All 12 required live demonstrations with record IDs and artifacts.
- 24-hour worker/routine endurance. The included read-only observation collector reports its scope explicitly and cannot certify active-workload endurance from idle samples.

The 1.12 MB 3D vendor bundle remains recorded optimization debt. It is code-split from the operator panels, and reduced-motion/low-power alternatives are available; no claim is made that target-hardware budgets have passed.

## Operator location and portability

The Phase 2 branch is `codex/live-agent-operating-system-v1` in `dev2495/ai-investment-os-recovery`. Pull that branch into a fresh checkout to test. Install the locked UI dependencies and Python runtime dependencies using the existing runbook; keep credentials, private databases, SSD artifacts, model weights and machine environment outside Git. Git contains the application and deployment tools, not a copy of private live data.

Use the existing Office, Models and System destinations for agent inspection, model controls and Doctor/routines. Research cases retain their evidence debt and review state; agent completion never grants investment or broker authority.
