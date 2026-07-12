# External SSD and AI OS Runtime Recovery Runbook

Date: 2026-07-11
Owner: Jarvis
Applies to: `Devarsh SSD`, Docker Desktop, Postgres, Qdrant, Redis, Ollama, Obsidian, AI OS API/UI/agent daemon
Safety rule: never format, erase, reset Docker data, delete a named volume, or run a write repair until the physical disk identifier, volume UUID, backup state, and failure boundary are proven.

## Storage Contract

- Expected APFS volume name: `Devarsh SSD`
- Expected volume UUID: `62B2476D-FBD4-4A5C-93C0-21D54E36D600`
- Expected mount point: `/Volumes/Devarsh SSD`
- Vault: `/Volumes/Devarsh SSD/Obsidian memory `
- Docker disk image: `/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw`
- Ollama models: `/Volumes/Devarsh SSD/OllamaModels`
- Heavy runtime state: `/Volumes/Devarsh SSD/AI OS Data`
- Recoverable source worktree: `/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os`

## Recovery Sequence

1. Stop project writes. Do not start Docker, Ollama, the API, or workers while `/Volumes/Devarsh SSD` is absent.
2. Prove device enumeration with `diskutil list external physical`, `diskutil info`, and USB/I/O Registry checks. If the USB bridge appears but no block device exists, reseat or replace the cable/port/enclosure before attempting filesystem commands.
3. Verify the APFS volume and partition map with `diskutil verifyVolume` and `diskutil verifyDisk`. A repair is allowed only when verification reports a repairable error and a current backup exists.
4. Run `_ai_os_runtime/scripts/verify_external_storage.sh`. It must prove the vault, model directory, runtime symlinks, and Docker disk image are external.
5. Start Docker Desktop and verify `docker version` and `docker image ls` before starting Compose.
6. If Docker reports containerd blob I/O errors, fully stop Docker Desktop, create an APFS clone of `Docker.raw`, then restart the untouched original. Do not purge or factory-reset Docker before preserving `Docker.raw` and named-volume evidence.
7. Start Compose and inspect datastore logs. Let Postgres perform WAL recovery. Remove or rename `postmaster.pid` only when all Postgres containers/processes are stopped and the file is proven stale or invalid.
8. For Qdrant, prefer a compatible collection/full snapshot. If no snapshot exists, preserve every damaged file and repair only metadata that can be proven identical from healthy sibling segments in the same collection. Never synthesize vector or payload data.
9. Verify Postgres row counts, all Qdrant collections and point counts, Redis `PONG`, and container health.
10. Start `_ai_os_runtime/scripts/start_ai_office_live.sh`; verify API health, UI HTTP 200, Ollama model inventory, TradingView CDP, and all four LaunchAgents.
11. Run a final live APFS verification and record the incident, exact repairs, data counts, backup path, and remaining risks in Obsidian.

## 2026-07-11 Incident Evidence

- The JMicron USB bridge enumerated first without a block device; the Kingston SNV3S1000G later appeared as physical `disk4`, APFS container `disk5`, volume `disk5s1`.
- APFS and GUID partition verification both returned exit code `0`. The volume remained writable and mounted at the expected path.
- Pre-repair Docker disk clone: `/Volumes/Devarsh SSD/AI OS Data/backups/docker-recovery-20260711/Docker.raw.pre-recovery-clone`.
- Docker containerd blob I/O errors cleared after a full Desktop stop/start from the untouched original `Docker.raw`.
- PostgreSQL recovered after preserving the NUL-filled stale lock file as `postmaster.pid.corrupt-20260711`; WAL replay completed and the database became healthy.
- Two NUL-filled Qdrant `strategy_artifacts_mxbai_embed_large` segment metadata files were preserved as `.corrupt-20260711` and replaced with the checksum-identical valid metadata used by three healthy sibling segments. Qdrant recovered all six collections; the repaired strategy collection was green with 43 points.
- Redis returned `PONG`. API, UI, Ollama, agent daemon, and TradingView CDP returned healthy live checks.

## 2026-07-13 Recurrence Evidence

- APFS stayed mounted and `diskutil verifyVolume /dev/disk5s1` returned exit code `0`, but Docker containerd again returned blob `input/output error`; Redis health checks failed because `/usr/local/bin/redis-cli` could not be read, and API database probes returned no rows.
- AI OS LaunchAgents were stopped before Docker recovery. Named volumes remained listed and no volume was deleted, reset, or recreated.
- Docker Desktop was fully stopped. A fresh APFS clone was preserved at `/Volumes/Devarsh SSD/AI OS Data/backups/docker-recovery-20260713/Docker.raw.pre-restart-clone`.
- Starting the untouched original `Docker.raw` cleared the stale containerd state. Image inventory became readable; Postgres and Redis returned healthy, Redis returned `PONG`, Qdrant served all six collections, and `strategy_artifacts_mxbai_embed_large` remained green with 43 points.
- `/api/health` was hardened to return HTTP `503` and `ok: false` when its Postgres probe is empty; it can no longer claim health while the database is unreachable.

## Prevention And Remaining Risk

- Startup storage guards prevent the AI OS from intentionally starting against internal fallback paths.
- Docker, database volumes, models, and heavy runtime state remain external; source code and Git history remain recoverable internally.
- The physical disconnect itself cannot be prevented in software. Use a short certified USB 3.x cable, avoid loose hubs, do not move the SSD while active, and eject only after Docker/Ollama/AI OS services are stopped.
- The daily critical-backup LaunchAgent still needs macOS removable-volume permission before unattended vault backup can be marked complete.
- Qdrant needs scheduled snapshots, and the isolated Postgres/Qdrant restore test remains open.
- A recurring Docker containerd I/O state remains an operational risk even when APFS verifies cleanly. Until root cause is eliminated, treat any executable/blob I/O error as a stop-and-clone event and never attempt repeated container restarts against the stale VM state.
