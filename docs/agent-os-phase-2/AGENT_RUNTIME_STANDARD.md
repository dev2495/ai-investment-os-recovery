# Agent runtime standard — implemented subset

Date: 2026-09-04. M1 remains partial; this document separates current behavior from the full build-prompt target.

## Ownership

The current general worker opts in with `AI_OS_AGENT_LEASE_RUNTIME_ENABLED=true`. Default is false. Enabling without migration 256 stops the worker instead of falling back to unfenced execution. Worker registration itself never renews an existing task lease.

Claim locks worker → profile → task → lease in a consistent order. The task row uses `FOR UPDATE SKIP LOCKED`, and a unique ACTIVE-lease index is the final exclusion constraint. Existing profile status, task class, dependencies, approval and dispatcher ownership are checked before enrollment. Expired leases must be reconciled before a replacement can claim.

The worker sends an active heartbeat every 15 seconds for a 45-second lease. Every task SQL transaction asserts current ownership; safe-boundary checkpoints run before evidence work, adapters and artifact output. A heartbeat error marks ownership uncertain and subsequent fenced writes fail closed. These checks do not forcibly cancel an already-running external call or filesystem write; a started side-effect marker prevents replay after uncertainty.

## Control and recovery

| Condition | Implemented result |
|---|---|
| Pause/cancel on active work | Persist request; worker applies it at the next safe boundary. |
| Safely paused, no side effects ever recorded | Resume queues the existing task for a new lease; retains prior steps/events. |
| Started or recorded output/tool step | No generic Resume/retry. Inspect and reconcile receipts first. |
| Expired lease on explicit `idempotent_read`, within attempt budget, no output/side effects | Reaper requeues the same task; late old owner cannot write. |
| Output persisted before worker loss | Preserve output and review state; do not rerun analysis. |
| Other expired lease | BLOCKED with receipt-reconciliation reason. |
| Worker result | Receipt-backed `needs_review`, or blocked/failed/paused/cancelled. No new worker API self-certifies research as completed. Existing graph completion semantics are preserved. |

The reaper handles at most 20 candidates per normal worker pass (hard cap 100). It does not reset paid model budgets, approve research, erase evidence or change capital authority.

## Remaining before general rollout

Full role/tool/privacy/model-policy snapshots, configurable lease/heartbeat values, 60-second idle heartbeat contract, all legal transition edges, dependency-cycle rejection, receipt-aware cross-process adapters, durable claim request keys, shutdown/drain controls and all legacy owner/task-class mappings remain to be completed or live-proven. The initial adapter is for controlled internal canaries, not blanket migration of all Research workers.
