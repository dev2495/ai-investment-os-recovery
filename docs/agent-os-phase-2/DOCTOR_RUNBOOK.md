# AI OS Doctor — pending M6

No new Doctor executable, route or automatic repair agent is activated by this increment. Existing system-health and deployment checks remain available; this file is a handoff contract, not a claim that those requested Doctor features are implemented.

M6 must build one allowlisted check registry over existing authorities: database/migrations, SSD mount/capacity, API/UI/MCP, workers/leases, schedules, Obsidian/index drift, backups, qualified model routes, and the existing Zerodha session/stream/freshness. Each check needs bounded execution, observed timestamp, evidence reference, severity, last-known-good and an exact repair scope.

Safe repairs must record before/after evidence and reuse existing supervisors or idempotent APIs. Never execute arbitrary model-authored production shell, change auth/ACLs, delete evidence, replay uncertain outputs, approve paid calls or enable trading. Credentials and official daily login require the operator; they are never chat payloads or Git content.

Current blocker: the iMac peer is offline despite a healthy local Tailscale client. SSH/API timed out; repeated peer checks agree. Do not rewrite firewall rules, authentication or service configuration to treat an offline peer as an application failure. Reconnect the host, then run the existing deployment status/verify entry points before any Phase 2 promotion.

The [operator runbook](OPERATOR_RUNBOOK.md) describes this increment's local test and rollout gates; it is not a substitute for the requested Doctor CLI/API/UI demos.
