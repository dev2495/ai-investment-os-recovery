# Phase 2 synthetic live canary

This canary verifies the installed Phase 2 lease-runtime control plane against
the canonical local PostgreSQL database. It is an acceptance probe, not a
production task runner.

## Safety boundary

The harness:

- refuses to run without `--operator-confirmed`;
- requires migration 262, `claim_mode=disabled`, and zero active or unreaped
  leases before starting;
- creates one uniquely named internal/public synthetic task, one synthetic
  agent, and two synthetic workers;
- gives the agent no model route, no tools, a zero token budget, no client or
  book, and explicit model/provider/research/routine/external/broker denials;
- never enables a model binding, provider, routine, research route, broker, or
  legacy task;
- never calls a model or provider and never writes to client, market, trading,
  portfolio, research, or broker surfaces;
- keeps the complete lifecycle in one repeatable-read transaction under the
  migration-262 rollout/claim lock. Other workers cannot observe its temporary
  `enabled` mode;
- always attempts a second, synthetic-ID-scoped cleanup transaction and refuses
  to overwrite a non-disabled shared runtime state.

Synthetic audit records are retained rather than deleted: the task ends
`cancelled`, the agent ends `disabled`, both workers end `STOPPED`, and the
receipt, task events, leases, and rollout history remain available for audit.

## Run

From the repository root on the target host:

```bash
python3 _ai_os_runtime/scripts/run_phase2_live_canary.py --operator-confirmed
```

The script reuses the existing local runtime PostgreSQL adapter and its normal
environment. Do not pass credentials on the command line. Omitting the flag is
a zero-database-call refusal.

## What a passing receipt proves

A `status: passed` JSON receipt attests this ordered lifecycle:

1. disabled -> enabled under the rollout lock;
2. first claim and heartbeat;
3. pause at a safe boundary and safe resume;
4. second-owner claim and rejection of the stale first owner;
5. fenced step write and durable synthetic receipt;
6. rejection of the stale owner's fenced write;
7. confirmed cancel at a safe boundary;
8. enabled -> draining -> disabled;
9. terminal task/profile/worker state and unchanged legacy-task, model-call,
   and routine-run markers;
10. an idempotent disabled-state cleanup audit.

Output is bounded to redacted record IDs, timestamps, booleans, counts, and
terminal states. Database errors are reduced to a bounded error class; raw task
bodies, credentials, prompts, or provider responses are never emitted.

## Failure handling

Any lifecycle assertion rolls back the main transaction. Cleanup is still
attempted. A failed cleanup is reported as `claim_mode: unverified`; it never
forces a shared non-disabled runtime to another state. Inspect the local
PostgreSQL/operator logs before any retry.

This canary does not attest UI behavior, external providers, model quality,
long-duration soak behavior, live research acceptance, or broker operations.
