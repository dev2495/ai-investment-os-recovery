# Phase 2 baseline — 2026-09-04

Start: `b42cc5d028f37ec2ead6b10296235d19bc9a5fd6`. Local starting worktree was clean. Remote Research Desk branch matches. New isolated branch: `codex/live-agent-operating-system-v1`. Other worktrees and historical submodule pins are preserved.

## Verified locally

- Backend: **654 passed, 1 skipped, 178 subtests passed** in 3.87 seconds, using a fresh temporary Python environment.
- UI: TypeScript and production Vite build passed; pre-existing large-chunk warning remains.
- Runtime dependency audit: **one moderate fflate advisory** in the existing lockfile, [GHSA-px8p-9vwx-vf98](https://github.com/advisories/GHSA-px8p-9vwx-vf98). This is new relative to the September 2 acceptance; do not report the old zero-vulnerability result as current.
- User blueprint and prompt copied without modification. SHA-256: v13 `dd295d316864138278ac2e8b4d44e7da9f7bfa1cc5a6b2ff6644f4f953b6b7a0`; prompt `9fd419cf18589164658825373c8427706b7d21c66b8a7208f75ef83974cfec1c`.

## Unverified live gates

SSH timed out twice, including outside the sandbox. API connection timed out. The local Tailscale client is running and healthy; the iMac peer reports `Online=false`, last seen `2026-09-04T00:03:34.1Z`. Current live SHA/marker, schema hash and migrations, processes, backup age, storage, API/MCP inventory, private scoped smoke tests and browser acceptance cannot be refreshed. No production write or private-data copy was attempted.

Checked alternatives: local Tailscale health, peer status and current address, SSH, API service port. These follow the [Tailscale device-connectivity checks](https://tailscale.com/docs/reference/troubleshooting/connectivity/connect-device-failure). No authentication, ACL or firewall changes are justified by an offline peer.

## Baseline preserved separately

The September 2 Research Desk report remains historical acceptance evidence. Wipro and Shivalik evidence debt, price freshness, Following/scanner approvals, GLM qualification and Safari acceptance are still separate Research gates, not Phase 2 completion claims.
