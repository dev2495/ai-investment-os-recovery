# Phase 2 acceptance checklist

Checked items mean the stated local check passed, not live acceptance. Unchecked items are required work, not waived requirements. Date: 2026-09-04.

## M0 — baseline and compatibility (partial)

- [x] Verify remote Research Desk branch at `b42cc5d028f37ec2ead6b10296235d19bc9a5fd6`; isolate this feature branch and preserve other worktrees.
- [x] Store supplied blueprint and prompt byte-for-byte; record hashes and reusable control-plane objects.
- [x] Run baseline backend tests, UI build and production dependency audit.
- [ ] Recheck live deployment marker, current source/release diff, schema, services, storage and private-scope contracts on the iMac.
- [ ] Verify current backup and isolated restore; write managed Obsidian notes on the canonical SSD.

## M1 — durable identities and workers (partial)

- [x] Add immutable machine key and bounded per-agent concurrency to existing profiles; retain numeric IDs.
- [x] Add worker registration, task-linked leases/steps, transaction fencing and bounded reaper without a second queue.
- [x] Prove competing claims, rollback, wrong owner/token, expired owner, duplicate heartbeat and concurrency caps against real PostgreSQL.
- [x] Kill a separate synthetic worker process; show STALE and reclaim only an explicitly idempotent read.
- [x] Preserve committed output; block uncertain side effects from automatic replay.
- [x] Opt-in current general worker; fail closed if migration is absent; test its database fence and output receipt.
- [ ] Finish the full role/permission/version snapshot and canonical state-transition contract, configurable intervals, idle-worker cadence and dependency-cycle validation.
- [ ] Prove production task-class/owner compatibility, receipt adapters, restart reconciliation and safe cutover with the existing dispatchers.

## M2 — heartbeats and events (partial)

- [x] Require operator authentication plus owned lease token for HTTP heartbeat, including loopback.
- [x] Reject unknown fields, terminal heartbeat claims and token-in-URL requests; throttle persisted heartbeats.
- [x] Append-only metadata events, commit-ordered IDs, cursor replay, burst reset and bounded finite SSE connections.
- [x] UI reconnect uses events to refresh the existing snapshot and open step inspector; snapshot polling remains the fallback.
- [ ] Add the complete requested event taxonomy, field/permission contracts and production client-scope review.
- [ ] Prove multiple-client stress, database latency, retention/compaction policy and 24-hour event/worker soak.

## M3–M7 — later milestones (not implemented in this increment)

- [ ] M3: persistent thread acknowledgements, complete handoff lifecycle, room/committee context and restart demos on existing message/committee tables.
- [ ] M4: full persisted Charlie command lifecycle, redirects, specialist allocation, receipts and evidence-backed explanations across existing entry points.
- [ ] M5: versioned per-agent/task-class bindings, provider adapter contract, route qualification and approved failover; no guessed model identity or automatic paid promotion.
- [ ] M6: Doctor CLI/API/UI check registry, drift evidence and allowlisted safe repair receipts.
- [ ] M7: versioned skills/routines on existing schedule authorities; five verified routines and filing/catalyst deduplication.

## M8 — truthful office (partial)

- [x] Preserve current shell, query client, tokens and 2D/3D office components.
- [x] Working counts and individual activity require an unexpired lease and healthy worker; old activity alone is UNVERIFIED.
- [x] Expire displayed lease truth locally during connection loss.
- [x] Add task inspection, pause, safe resume and cancel confirmation; uncertain output explains why replay is unavailable.
- [x] Real-browser flow: pause → persisted pause → resume → worker running → new step visible → reconnect → confirmed cancellation.
- [x] Production-build Chrome checks at 1440px and 390px; no horizontal page overflow; no serious/critical axe findings in the checked panels; no uncaught page errors.
- [ ] Complete specified agent hover/click details, handoff/committee projection, all state interactions, full keyboard/screen-reader audit and 2D/3D parity.
- [ ] Safari/operator acceptance and M4 CPU/GPU/reduced-motion/low-power budgets with the real population.

## M9 and final acceptance (pending)

- [ ] Cross-desk role/capability mapping without labelling unimplemented desks complete.
- [ ] All 12 required end-to-end demonstrations on the canonical system.
- [ ] 100 agents, 4 workers, 1,000 tasks, 10,000 events, 100 reconnecting SSE clients and 24-hour iMac soak.
- [ ] Re-run Research Desk regression and preserve evidence debt, source/publication and paid-model approvals.
- [ ] Market-hours Zerodha freshness and broker-write lock verified live; seven protected integrations remain unchanged.
- [ ] Resolve or explicitly disposition the pre-existing fflate advisory and build-size warning before release acceptance.
- [ ] Update live release marker, implementation ledger, Git and canonical Obsidian with accepted evidence.
