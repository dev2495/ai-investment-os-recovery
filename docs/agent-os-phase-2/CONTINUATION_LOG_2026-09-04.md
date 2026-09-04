# Phase 2 continuation — 4 September 2026

Starting commit: `8b9450dfbd021b9492fce5054e3f4021663b760f`.
Branch: `codex/live-agent-operating-system-v1` (same branch, clean at resumption).

The exact continuation request was read in full. Phase 3 is not in scope. An
offline iMac blocks live acceptance only; local implementation continues.
Tailscale reported the iMac offline and an 8-second key-only SSH attempt timed out.
No production data, process, migration or credentials were changed.

## Runtime policy and recovery increment

Migration 257 extends canonical profiles/tasks/leases with agent workspaces,
permission/model/budget snapshots, configurable active/idle/lease intervals,
dependency-cycle and scope guards, typed state edges, typed metadata events,
output receipts and no-replay reconciliation. Existing event rows are retained;
checkpoint projections do not delete audit history. Shared snapshot/replay/control
exclude client/book-scoped tasks, including events recorded before scope columns.

The general worker consumes the returned active heartbeat interval. Idle-heartbeat
API and drain contracts exist; pooled-daemon integration remains next work.
Approval, model/tool call, routine and execution edges are contracts for the
adapters, not a claim that all legacy writers have been migrated.

Verified locally: **684 passed, 1 skipped, 178 subtests**, full backend suite;
**30 passed**, targeted PostgreSQL/HTTP/worker/policy suite; production UI build
passed. Command: `PYTHONPATH=_ai_os_runtime/api:. AI_OS_TEST_PG_DSN=<isolated socket>
python -m pytest _ai_os_runtime/tests -q`. Tests use a guarded, uniquely named
database per module on the disposable local PostgreSQL cluster. The skipped test
is the separate restore drill, not proof of a production backup or restore.

A generic PostgreSQL trigger initially referenced a field absent on workers.
Considered table-specific triggers, nested branches, dynamic record access and
JSON record projection; used the latter to share a small guard without assuming
SQL expression evaluation order. Reference: [PostgreSQL JSON functions](https://www.postgresql.org/docs/15/functions-json.html)
and [expression evaluation](https://www.postgresql.org/docs/17/sql-expressions.html).

Remaining before completion: messaging/handoffs, Charlie orchestration, Model
Fabric, Doctor, routines, full office parity and all specified stress/acceptance
gates. No milestone is declared live accepted. The fflate dependency advisory and
vendor-size warning remain open. Canonical Obsidian writeback is pending SSD access.
