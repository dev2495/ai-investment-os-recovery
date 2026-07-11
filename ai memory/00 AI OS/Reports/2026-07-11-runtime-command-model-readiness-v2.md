---
title: 2026-07-11 Runtime Command And Model Readiness v2
date: 2026-07-11
status: verified
owners:
  - Jarvis
  - AI Engineering
evidence_standard: live_runtime
---

# 2026-07-11 Runtime Command And Model Readiness v2

## Decision

Keep lightweight source code on the Mac and all persistent heavy state on `Devarsh SSD`. Use `llama3.2:3b` as the always-on daily driver. Keep larger Qwen routes registered as optional escalation slots, but never mark them assignable unless the exact model is installed.

## Storage Evidence

- Canonical worktree: `/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os`.
- Stable vault runtime path: `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`.
- Runtime path resolves to the canonical internal worktree source.
- Docker disk image: `/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw`.
- Ollama models: `/Volumes/Devarsh SSD/OllamaModels`.
- Generated UI dependencies: `/Volumes/Devarsh SSD/AI OS Data/cache/ai-office-ui/node_modules`.
- SSD evidence mirrors: `/Volumes/Devarsh SSD/AI OS Data/artifacts` and `/Volumes/Devarsh SSD/AI OS Data/imports`; the 32 MB Git-tracked evidence snapshot and small manifests remain in the worktree for repository recovery.
- Runtime logs: `/Volumes/Devarsh SSD/AI OS Data/logs/runtime`.
- LaunchAgent supervisor logs remain in `~/Library/Logs/AIOS` because launchd cannot pre-open removable-volume log paths; startup trims each file above 8 MB down to its latest 1 MB.
- Runtime PID/state files: `/Volumes/Devarsh SSD/AI OS Data/run`.
- `scripts/verify_external_storage.sh` passed for vault, models, Docker disk image, and compose configuration.
- `ai_os_postgres`, `ai_os_qdrant`, and `ai_os_redis` were running; Postgres and Redis reported healthy.

## Command Routing Evidence

- UI: deployed Command Center at `http://127.0.0.1:5177/`.
- QA command explicitly prohibited investment or trading action.
- Durable message: `agent.agent_messages #94`, Charlie Munger to Research Analyst.
- Generated task: `agent.tasks #327`.
- Generated task inbox: `agent.inbox_items #412`.
- Provider-policy review inbox: `agent.inbox_items #413`.
- Final task state: `needs_review`; no capital action was executed.

## Local Model Evidence

- Installed models: `llama3.2:3b` (2.0 GB) and `mxbai-embed-large` (669 MB).
- Direct inference returned exactly `LOCAL MODEL READY`.
- Direct cold-load smoke duration: 9.73 seconds.
- Persisted Charlie chat: `agent.chat_turns #44` with provider `ollama`, model `llama3.2:3b`, and `model_status=called`.
- Ollama LaunchAgent is enabled by default at `127.0.0.1:11434` with SSD-backed models.

## Readiness Gate Evidence

- Readiness run: `core.provider_readiness_runs` key `live-model-readiness-v2-20260711`.
- Installed route health check: `core.connector_health_checks #773`, status `configured`.
- Missing route health check: `core.connector_health_checks #774`, status `model_unavailable` for `qwen3:14b`.
- Five absent Qwen endpoints are degraded and non-assignable.
- The health check now verifies Ollama `/api/tags`; configuration alone cannot pass readiness.

## Remaining Work

- Grant the critical-backup LaunchAgent explicit macOS removable-volume access, run a fresh snapshot, and complete an isolated restore test. The current daily run exits `23` because launchd cannot open the vault root; the last verified snapshot is dated 2026-07-10.
- Build a fixed quality and throughput evaluation set for local-vs-cloud routing.
- Decide whether to install one medium local workhorse after measuring memory pressure and concurrent office workload.
- Add cloud secret references only through the approved secret-management workflow.
- Complete provider policy editor/simulator and per-department route cleanup.
