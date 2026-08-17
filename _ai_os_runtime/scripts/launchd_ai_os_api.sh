#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_API_HOST="${AI_OS_API_HOST:-127.0.0.1}"
export AI_OS_API_PORT="${AI_OS_API_PORT:-8765}"

cd "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime"
exec python3 -u api/ai_os_api_runtime.py
