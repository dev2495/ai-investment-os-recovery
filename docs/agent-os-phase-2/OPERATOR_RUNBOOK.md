# Operator runbook — first Phase 2 increment

This is an opt-in feature branch, not the production release. Do not enable it across all workers before the pending contract and live compatibility gates pass.

## Isolated tests on another Mac

Use a fresh checkout of `codex/live-agent-operating-system-v1`, Python 3.12 with pytest, pytest-subtests and psycopg 3, PostgreSQL 15+, Node and the existing UI lockfile. Install dependencies into that checkout; do not reuse or mutate another worktree's node_modules.

The actual database tests require a **disposable, socket-only** PostgreSQL cluster whose socket directory begins `/private/tmp/aios-phase2-pg.` and whose superuser is `phase2_test`. Create the directory with `mktemp -d`, initialize that dedicated cluster, disable TCP listening, and use a distinct port. Never substitute a production DSN. Each test module creates/removes only its uniquely named `phase2_test_<uuid>` database.

From the repository root, with the temporary DSN set locally:

```sh
AI_OS_TEST_PG_DSN='host=/private/tmp/aios-phase2-pg.REPLACE port=55439 user=phase2_test dbname=postgres' \
PYTHONPATH=_ai_os_runtime:_ai_os_runtime/api:. python -m pytest -q -rs _ai_os_runtime/tests
```

For the browser test, start `_ai_os_runtime/tests/serve_agent_runtime_fixture.py` with the same test DSN/PYTHONPATH and `AI_OS_SYNTHETIC_BROWSER_FIXTURE=1`. It binds `127.0.0.1:18765`, creates synthetic tasks and cleans its database on SIGTERM. Start it fresh for each complete browser run because the test ends by cancelling its task.

In `_ai_os_runtime/ai-office-ui`, run:

```sh
VITE_AI_OS_API_URL=http://127.0.0.1:18765 npm run build
npm run preview -- --host 127.0.0.1 --port 15177 --strictPort
```

Then run `PLAYWRIGHT_BASE_URL=http://127.0.0.1:15177 npx playwright test tests/agent-runtime.spec.ts --workers=1`. If using installed Chrome on macOS, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its application binary. The test refuses to mutate tasks without the synthetic-fixture marker. Open `/firm/office` for manual checks. **Never deploy the fixture or this fixture-targeted dist build.**

Stop only the fixture/preview processes and temporary PostgreSQL cluster started for this test. Retain logs and reviewed screenshots as test evidence; no production cleanup is part of this procedure.

## Before iMac promotion

1. Reconnect to the canonical iMac. Read current source and deployed release SHA/dirty state; compare this branch without overwriting unrelated work.
2. Verify external SSD, current PostgreSQL/Obsidian/config/artifact backup and isolated restore. Refresh actual migrations/schema and system health.
3. Finish remaining M1/M2 privacy/policy/adapter contracts and review the full accepted Research worker/graph compatibility. Resolve or disposition dependency findings.
4. Apply additive migration 256 through the existing release process, first on an isolated restore. Migration presence alone does not enable worker leases.
5. Rebuild the UI with the real canonical API target. Include both new runtime modules in the current API service payload; do not add a second server.
6. Canary one supported internal, read-only, non-paid general task with `AI_OS_AGENT_LEASE_RUNTIME_ENABLED=true` using the existing configuration/supervisor path. Verify claim, heartbeat, state, controls, output receipt and old-owner rejection via real API/UI/MCP.
7. Prove drain/restart/rollback, Research regressions, private scopes and existing Zerodha health. Expand only after live evidence; perform required stress and 24-hour soak before acceptance.

No new model permission, paid budget, source entitlement, broker action or credential repair is authorized by enabling ownership.

## Safe fallback

Pause new dispatch and let current managed work reach a safe boundary. Disabling the feature flag stops **new enrollment**, but is not a database rollback: existing lease-managed tasks retain fences/history and must be drained or reconciled by the runtime. Do not put managed queued tasks back under an old unfenced worker, drop migration tables or rewrite statuses to force a retry.

Restore the previous API/UI/service code only after confirming task ownership is quiescent and historical compatibility. Retain additive records and receipts. An uncertain paid/tool/artifact step remains blocked for review; never replay it as a rollback convenience.

## Obsidian

After reconnection, mirror the ledger, acceptance report and decisions under `ai memory/00 AI OS/Implementation/Agent OS Phase 2/` using existing managed-block writers. Preserve human text and index lineage. This increment did not write to the unavailable canonical vault.
