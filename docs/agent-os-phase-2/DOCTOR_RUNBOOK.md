# AI OS Doctor — M6 runtime runbook

Migration 260 and the Doctor runtime provide one deterministic check registry,
one operator command, durable results, last-known-good timestamps, reviewed drift
baselines, and a single tightly allowlisted safe repair. Doctor does not call a
model, fetch provider data, inspect credential values, change client data, or
write to a broker.

This increment contains the API helper, but intentionally does not edit the
shared HTTP server, MCP server, or UI. Those integration surfaces must call the
same `DoctorRuntime`; they must not copy check logic.

## Operator commands

Run from the repository root after migration 260 has been applied through the
existing deployment process:

```bash
python3 _ai_os_runtime/scripts/ai_os_doctor.py
python3 _ai_os_runtime/scripts/ai_os_doctor.py --json
python3 _ai_os_runtime/scripts/ai_os_doctor.py --quiet
python3 _ai_os_runtime/scripts/ai_os_doctor.py --component zerodha
python3 _ai_os_runtime/scripts/ai_os_doctor.py --component obsidian
python3 _ai_os_runtime/scripts/ai_os_doctor.py --agent <agent_key>
python3 _ai_os_runtime/scripts/ai_os_doctor.py --model-route <route>
```

Exit code `0` means all selected evidence passed or was explicitly skipped.
Exit code `1` means degraded/unknown evidence. Exit code `2` means at least one
failed check. Unknown is never converted to healthy.

## Reviewed baseline

After the watched configuration list and current hashes have been reviewed:

```bash
python3 _ai_os_runtime/scripts/ai_os_doctor.py --init-baseline --component configuration
```

Future scans compare the current aggregate configuration digest with that
durable baseline. Missing baselines warn; different digests fail. Updating the
baseline is an explicit review action, never an automatic repair.

## Registered checks

The 21 checks cover:

- Postgres connectivity and migration level;
- external-SSD mount, write availability, capacity and required directories;
- API, Redis, Qdrant, workers, daemon heartbeats, queues and schedules;
- Obsidian index lag, unresolved links and local managed-block integrity;
- backup and disposable restore-drill receipts;
- expired task leases;
- model endpoint health, provider/model/endpoint identity, adapter/runtime
  version, active-agent binding, qualification freshness and cost-cap health;
- canonical Zerodha readiness, human login state, supervised stream and quote
  freshness with `broker_write_allowed=false`;
- TradingView and optional Pythia readiness;
- source/deployed UI asset equality, LaunchAgent presence, watched config hashes;
- global execution locks, forced client-scope RLS and changed-file secret scan.

Zerodha is observed only through `market.v_zerodha_stream_health` and
`core.v_provider_readiness_board`. The check reports key presence as a boolean;
it never returns or changes the key. A stale quote during market hours is a
failure. Outside market hours a non-live quote remains a visible warning, not a
fabricated live price.

## Safe repair boundary

The only currently enabled safe fix is receipt-aware expired-lease recovery:

```bash
python3 _ai_os_runtime/scripts/ai_os_doctor.py --safe-fix --component agents
```

It calls the existing `agent.reap_runtime_leases` function and records before
and after evidence in `ops.doctor_safe_fix_receipts`. It may requeue only work
that the existing lease policy classifies as safe. It cannot restart services,
reindex data, install plists, refresh connectors, rotate credentials, approve a
model, alter client data, weaken locks, or place a trade. Additional repairs
require separately reviewed handlers and tests before entering the allowlist.

## Verification and remaining acceptance

Focused tests prove the required negative classifications for a dead,
unqualified or identity-drifted route, expired lease, stale market-hours Zerodha
quote, Obsidian lag, missing probe, configuration drift, secret redaction and
safe-fix boundaries. Live iMac proof
still requires applying migration 260, running the command against the canonical
services, and verifying the shared API/UI adapters after they are wired. This
runbook does not claim that deployment or UI acceptance has happened.
