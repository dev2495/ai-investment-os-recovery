#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export VITE_AI_OS_API_URL="${VITE_AI_OS_API_URL:-http://127.0.0.1:8765}"

cd "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/ai-office-ui"
exec npm run dev -- --host 127.0.0.1 --port "${AI_OS_UI_PORT:-5177}"
