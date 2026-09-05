# Phase 2 synthetic runtime stress acceptance — 2026-09-05

## Verdict

`PASS` for the isolated M1/M2 target-scale lease, event, replay, idempotency,
presence-truth, and safety-lock workload.

This is local synthetic evidence. It is not the required 24-hour canonical iMac
soak, live browser/SSE acceptance, deployment proof, or a Phase 2 completion
verdict.

## Observable result

| Contract | Observed result |
|---|---:|
| Canonical agent profiles | 100 |
| Compatible worker processes | 4 |
| Canonical tasks claimed | 1,000 |
| Distinct task lease owners | 1,000 |
| Maximum lease attempt | 1 |
| Concurrent contenders for one task | 4 |
| Winners for the contested task | 1 |
| Peak active leases | 4 total; 1 per worker; 1 per agent |
| Typed append-only events | 10,000 |
| Event composition | 1,000 claimed; 8,000 steps; 999 released; 1 expired |
| Reconnect/cursor comparisons | 100, 37 events per page |
| Future-cursor reset | Empty page plus durable Postgres checkpoint recovery |
| Expired lease office truth | `STALE`, `has_live_lease=false` before reaping |
| Receipt-aware expiry result | 1 expired, 1 safely requeued, 0 blocked |
| Heartbeat retry | Duplicate response; no expiry extension |
| Broker write | `false` throughout |
| Provider/model/external calls | 0 / 0 / 0 |
| Synthetic database cleanup | Own uniquely named database dropped; 0 left behind |

The measured repeat run completed in 1.134 seconds: 0.073 seconds setup, 0.727
seconds task/event processing, 0.276 seconds verification and reconnects, and
the remainder in guarded cleanup. Timing is evidence for this Mac and disposable
PostgreSQL instance only; it is not a production performance promise.

## Test boundary and safety

The harness accepts only a Unix-socket DSN shaped as:

```text
phase2_test@postgres on /private/tmp/aios-phase2-pg.*
```

It refuses TCP/host-address targets, passwords, another user, another database,
another socket root, a symlinked socket directory, and a connected server whose
data directory is not the matching private-tmp test cluster. It creates a
`phase2_stress_<uuid>` database with `template0`, validates the cleanup name
again, terminates only connections to that exact database, and drops only it.

No production state, source archive, Obsidian note, report, model route,
credential, research decision, Zerodha surface, or broker surface is read or
written.

## Migration basis

The harness fingerprints migrations 256 through 261. It replays the directly
relevant runtime/collaboration/model/Charlie migrations 256, 257, 258, 259, and
261 twice on the isolated substrate, then runs the stress workload. Migration
260 owns Doctor and routine dependencies and remains covered by its separate
Doctor/routine acceptance tests; this stress run does not duplicate that test
fixture or claim its result.

## Reproduction

From the repository root, with the disposable local PostgreSQL cluster already
running:

```bash
AI_OS_TEST_PG_DSN='host=/private/tmp/aios-phase2-pg.AH4u2v port=55439 user=phase2_test dbname=postgres' \
  /private/tmp/aios-phase2-venv/bin/python -m _ai_os_runtime.tests.phase2_runtime_stress
```

Fast refusal-contract checks:

```bash
/private/tmp/aios-phase2-venv/bin/python -m pytest -q \
  _ai_os_runtime/tests/test_phase2_runtime_stress_contract.py
```

Observed: `7 passed`; the full harness returned `verdict=PASS`; a post-run
database query found zero `phase2_stress_%` databases.

## Residual acceptance gates

- Run the real SSE/browser multi-client reconnect checks on the deployed API.
- Run Safari acceptance against the canonical iMac release.
- Run the required 24-hour iMac worker/event soak and record restarts, latency,
  resource use, and zero-duplicate ownership evidence.
- Re-run this harness after the final migration set is frozen and before the
  live canary cutover.
