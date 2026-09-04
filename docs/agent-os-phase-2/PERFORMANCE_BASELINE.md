# Performance evidence — local increment

Recorded 2026-09-04. These are test observations on the MacBook, not iMac production benchmarks.

| Check | Observed |
|---|---|
| Original backend regression | 654 passed, 1 skipped, 178 subtests; 3.87 seconds |
| Extended backend + actual disposable PostgreSQL/HTTP/process tests | 678 passed, 1 skipped, 178 subtests; 6.28 seconds |
| UI | TypeScript + production build passes; pre-existing vendor chunk around 1.12 MB emits size warning |
| Browser | Production build with actual local runtime API/PG; desktop 1440×1000 and mobile 390×844; recorded separately in acceptance report |

Implemented resource ceilings: worker/agent concurrency 1 by default and capped at 4; 45-second active lease; 15-second worker heartbeat; at most one persisted heartbeat/second/worker; replay 200 events, 64 cached cursors for two seconds, 16 simultaneous 25-second SSE connections; 262 KiB browser event buffer; coalesced snapshot/detail refresh; existing snapshot fallback polling.

Event allocation uses a transaction advisory lock to preserve commit-order replay. This favors correctness at the initial bounded-worker scale; contention/latency under the full target population is **not measured**. [PostgreSQL locking behavior](https://www.postgresql.org/docs/current/explicit-locking.html) informed the consistent lock order and transaction boundary.

Not yet run: 100 logical agents, 4 workers, 1,000 tasks, 10,000 events, 100 reconnecting SSE clients, real M4 CPU/GPU and frame-time budgets, event retention growth, API latency percentiles, 24-hour routine/worker soak. The 16-stream cap intentionally falls back to snapshots; it is not evidence that the 100-client target has passed.
