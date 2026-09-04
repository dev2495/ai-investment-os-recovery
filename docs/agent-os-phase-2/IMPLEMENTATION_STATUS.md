# Agent OS Phase 2 — implementation ledger

Started 2026-09-04. Specification: the user-supplied v13 Living Investment Office blueprint and Phase 2 build prompt. This is an additive continuation of Research Desk, not a replacement control plane.

**Current checkpoint: first local implementation increment passed; not deployed; full Phase 2 is not complete.**

## Baseline

- Branch: `codex/live-agent-operating-system-v1`.
- Starting commit: `b42cc5d028f37ec2ead6b10296235d19bc9a5fd6`; matches the remote Research Desk branch on 2026-09-04.
- Isolated checkout: `/private/tmp/aios-agent-os-phase2`.
- Production connection: SSH and API timed out. Tailscale reports the iMac offline, last seen 2026-09-04 00:03:34 UTC. The September 2 live acceptance is historical evidence, not a current health assertion.
- No production migrations, restarts, paid model calls, broker changes, or private-data copies have been made.

## Milestones

| Milestone | Implementation | Acceptance |
|---|---|---|
| M0 baseline and compatibility | Partial | Local baseline/reuse audit passed; live inventory and current backup unavailable |
| M1 identities, workers and leases | Partial | Exclusive claims, killed-worker recovery, fencing, caps and controls passed locally; full policy/cutover pending |
| M2 heartbeats, events and replay | Partial | Auth, bounded persistence, cursor replay/reset and browser reconnect passed locally; full contracts/stress pending |
| M3 messages, handoffs and committees | Pending | Not accepted |
| M4 Charlie durable orchestration | Pending | Not accepted |
| M5 governed model fabric | Pending | Not accepted |
| M6 Doctor | Pending | Not accepted |
| M7 skills and routines | Pending | Not accepted |
| M8 truthful 2D/3D office | Partial | Lease-derived indicators and task controls tested; full parity, Safari and production performance pending |
| M9 cross-desk identities and final acceptance | Pending | Not accepted |

## Local verification and artifacts

- Migration 256 reapplied safely to synthetic databases using original checked-in profile/task/approval DDL.
- Backend: **678 passed, 1 skipped, 178 subtests passed** in 6.28 seconds. The skipped test is the opt-in disposable PostgreSQL restore-role integration; this is not a verified production restore.
- UI TypeScript/production build passed. Final real Chrome/HTTP/PostgreSQL scenario passed in 10.9 seconds, including worker resume, live step history, reconnect, confirmation and mobile panel accessibility.
- Review caught and fixed duplicate/rapid heartbeat behavior, null-token rejection, idle worker return, stale step inspection and two mobile keyboard/overflow issues. Regression assertions cover the corrected behavior.
- No live agents migrated; no production service, schema, source/model route or Zerodha file changed. Runtime enrollment is opt-in and disabled by default.
- Known baseline findings remain: one moderate fflate advisory and vendor chunk size warning. Full stress/soak, client-scope checks and production acceptance remain open.

See [acceptance checklist](ACCEPTANCE_CHECKLIST.md), [verification report](LIVE_ACCEPTANCE_REPORT.md), [security review](SECURITY_REVIEW.md), [operator runbook](OPERATOR_RUNBOOK.md) and [research residual gates](RESEARCH_DESK_RESIDUAL_GATES.md).

Git records this checkpoint on the dedicated Phase 2 branch. The canonical Obsidian mirror remains pending until the iMac/SSD reconnects; human vault content has not been overwritten.

## Deployment gate

Before promotion: reconnect to the canonical iMac; compare deployed SHA and dirty state; verify backup/restore and current schema; repeat Research Desk regressions; apply additive migrations through the existing deployment process; verify real UI/API/MCP; complete the required 24-hour worker/routine soak. Do not call Phase 2 complete before those gates pass.

## Preserved boundaries

Zerodha remains the existing canonical GET-only provider with `broker_write_allowed=false`. Daily human authentication, Keychain, LaunchAgent supervision and reconnect behavior remain unchanged. No credential is stored in this ledger. Research evidence debt and approval gates remain distinct from agent/task completion.
