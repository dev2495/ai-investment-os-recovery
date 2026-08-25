#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_API_HOST="${AI_OS_API_HOST:-127.0.0.1}"
export AI_OS_API_PORT="${AI_OS_API_PORT:-8765}"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os/_ai_os_runtime}"
export AI_OS_VAULT_ROOT="${AI_OS_VAULT_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
export AI_OS_WORKER_SCRIPT="${AI_OS_WORKER_SCRIPT:-/Users/devarshthakkar/Library/Application Support/AIOS/service/scripts/run_agent_worker_once.py}"
export AI_OS_PSQL_BIN="${AI_OS_PSQL_BIN:-/opt/homebrew/opt/postgresql@15/bin/psql}"
export AI_OS_DOCKER_BIN="${AI_OS_DOCKER_BIN:-/opt/homebrew/bin/docker}"
export AI_OS_EMBEDDING_MODEL="${AI_OS_EMBEDDING_MODEL:-qwen3-embedding:0.6b}"
export AI_OS_MLX_URL="${AI_OS_MLX_URL:-http://100.75.156.32:11435/v1}"
export AI_OS_MLX_REQUEST_MODEL="${AI_OS_MLX_REQUEST_MODEL:-default_model}"
export AI_OS_LOCAL_OPENAI_URL="${AI_OS_LOCAL_OPENAI_URL:-http://100.75.156.32:11436/v1}"
export AI_OS_LOCAL_OPENAI_REQUEST_MODEL="${AI_OS_LOCAL_OPENAI_REQUEST_MODEL:-/Users/devarshthakkar/Library/Application Support/AIOS/models/qwen3.5-9b-4bit-8b2b98c}"
export AI_OS_LOCAL_OPENAI_MAX_TOKENS="${AI_OS_LOCAL_OPENAI_MAX_TOKENS:-1200}"
export AI_OS_CHAT_MODEL_ROUTE="${AI_OS_CHAT_MODEL_ROUTE:-charlie_munger_orchestration}"

cd "/Users/devarshthakkar/Library/Application Support/AIOS/service"
exec python3 -u api/ai_os_api_runtime.py
