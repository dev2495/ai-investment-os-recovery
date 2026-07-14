#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_API_HOST="${AI_OS_API_HOST:-127.0.0.1}"
export AI_OS_API_PORT="${AI_OS_API_PORT:-8765}"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os/_ai_os_runtime}"
export AI_OS_VAULT_ROOT="${AI_OS_VAULT_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
export AI_OS_WORKER_SCRIPT="${AI_OS_WORKER_SCRIPT:-/Users/devarshthakkar/Library/Application Support/AIOS/service/scripts/run_agent_worker_once.py}"
export AI_OS_PSQL_BIN="${AI_OS_PSQL_BIN:-/opt/homebrew/opt/postgresql@15/bin/psql}"
export AI_OS_DOCKER_BIN="${AI_OS_DOCKER_BIN:-/usr/local/bin/docker}"

cd "/Users/devarshthakkar/Library/Application Support/AIOS/service"
exec python3 -u api/ai_os_api_server.py
