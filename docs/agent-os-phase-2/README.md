# Living Agent OS — Phase 2

Status on 2026-09-04: **first implementation increment tested locally; not deployed; full Phase 2 remains open.**

The supplied [v13 blueprint](../AI_Investment_OS_Living_Investment_Office_Master_Blueprint_v13.md) and [build prompt](MASTER_BUILD_PROMPT.md) are preserved unchanged. This branch extends the accepted Research Desk baseline; it does not replace its task, message, model, approval or market-data authorities.

Start with the [implementation ledger](IMPLEMENTATION_STATUS.md), [acceptance checklist](ACCEPTANCE_CHECKLIST.md) and [verification report](LIVE_ACCEPTANCE_REPORT.md). Use the [operator runbook](OPERATOR_RUNBOOK.md) for local tests and the gated iMac rollout.

## Delivered in this increment

- Migration 256: stable keys on existing profiles; workers, exclusive task leases, steps, dependency checks, heartbeat receipts and append-only events attached to existing task IDs.
- Opt-in ownership fencing around the current general worker, with safe-boundary pause/cancel and conservative recovery. No new research/model worker is started.
- Authenticated, bounded runtime API and MCP controls. Existing Office snapshots gain lease-derived presence and resumable events.
- Existing 2D/3D office working indicators use real lease evidence. The shared task panel shows stale/blocked states, step history, safe resume and confirmed cancellation.
- Real disposable-PostgreSQL, HTTP, killed-worker and production-build browser tests. Test data is explicitly synthetic; no company research or private account state is copied.

## Not delivered or accepted yet

M3 messaging/handoffs, M4 full Charlie orchestration, M5 Model Fabric upgrades, M6 Doctor, M7 new routine contracts and M9 cross-desk acceptance remain pending. M0, M1, M2 and M8 are partial. Existing functionality in those areas remains in place, but is not newly certified here.

The iMac is offline. Its current release, schema, backups, real UI, Safari, provider health and required 24-hour soak cannot be verified. No live agents have been migrated and no production service or database has been changed.

## Reference

- [Control plane](CURRENT_CONTROL_PLANE_MAP.md) · [Reuse matrix](REUSE_MATRIX.md)
- [Data contracts](DATA_CONTRACTS.md) · [Runtime standard](AGENT_RUNTIME_STANDARD.md)
- [Office truth](OFFICE_TRUTH_CONTRACT.md) · [Security review](SECURITY_REVIEW.md)
- [Performance evidence](PERFORMANCE_BASELINE.md) · [Research residual gates](RESEARCH_DESK_RESIDUAL_GATES.md)
- [Model Fabric](MODEL_FABRIC_STANDARD.md) · [Messages](MESSAGE_AND_HANDOFF_STANDARD.md) · [Routines](ROUTINE_STANDARD.md) · [Doctor](DOCTOR_RUNBOOK.md)
