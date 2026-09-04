# Security review — first increment

Date: 2026-09-04. Local code/test review only; production authorization and client-scope acceptance remain pending.

## Preserved

- Seven protected Zerodha scripts/service wrapper are unchanged. No market-price pipeline, instrument/account sync or broker API is replaced or added.
- `broker_write_allowed=false`; no order placement, paid model call, provider promotion or financial approval is added.
- No credentials, account records, customer inputs, research data or model weights were copied to the local test environment or Git.
- Existing API authorization, private/public Research routing and source/review gates remain in use.

## New safeguards and observed tests

- Random 256-bit worker token; only SHA-256 digest stored. Token is excluded from object repr, shared projections and URLs. HTTP heartbeat requires operator authentication plus exact owner/lease/token validation, including on loopback.
- Bounded IDs, request bodies, response rows, SQL/lock/socket durations, replay buffer and connections. Duplicate heartbeat IDs do not prolong a lease twice; rapid new IDs do not create unbounded heartbeat persistence.
- Fenced task SQL; old owners fail after expiry/reassignment. Existing task/profile/approval/dependency checks precede enrollment. Worker cannot newly self-certify completed research through the finish operation.
- Append-only event updates/deletes fail. State/event/task changes share the database transaction. Uncertain output steps block replay; cancellation preserves evidence.
- Runtime shared projection omits objectives, narrative, inputs, node/PID, local paths and token hashes. New task-detail/control scope is managed/internal only.
- MCP accepts only explicit operator-confirmed pause/resume/cancel and calls the same API. It is not an arbitrary shell or generic SQL tool.

## Remaining release gates

1. Dedicated least-privilege database roles and exhaustive client/permission scope mapping. The transaction-local fence is an accidental-write guard, not protection against the trusted DB owner bypassing it.
2. Full role/version/tool/model-policy snapshots, task-class adapter review, receipt reconciliation and cross-process side-effect testing. Already-started filesystem/provider operations cannot be undone by expiring a lease.
3. Full event metadata classification, long-term retention, concurrent-SSE stress and supervisor shutdown/drain testing.
4. Existing UI lockfile has one moderate [fflate advisory, GHSA-px8p-9vwx-vf98](https://github.com/advisories/GHSA-px8p-9vwx-vf98). Lockfile/dependency versions were not changed. Resolve or explicitly disposition it before release acceptance.
5. Current live authorization, backups, real private-scope tests, Safari and market freshness are unverified while the iMac is offline.

The synthetic browser fixture is guarded by explicit opt-in, a temporary Unix-socket PostgreSQL target and a dedicated test user. It binds only loopback, creates uniquely named synthetic databases and has no provider/broker calls. It must never be deployed or used as a production health endpoint.
