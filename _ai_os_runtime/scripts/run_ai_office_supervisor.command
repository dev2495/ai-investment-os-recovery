#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${RUNTIME_ROOT}/run"
LOG_DIR="${RUNTIME_ROOT}/logs"
VAULT_ROOT="/Volumes/Devarsh SSD/Obsidian memory "
TRADINGVIEW_PORT="${AI_OS_TRADINGVIEW_CDP_PORT:-9333}"

mkdir -p "${RUN_DIR}" "${LOG_DIR}" "/Volumes/Devarsh SSD/AI OS Data/ollama/models"
echo $$ > "${RUN_DIR}/supervisor.pid"

ollama_pid=""
tradingview_pid=""
api_pid=""
agent_pid=""
ui_pid=""

start_ollama() {
  OLLAMA_MODELS="/Volumes/Devarsh SSD/AI OS Data/ollama/models" OLLAMA_NO_CLOUD=1 \
    bash "${RUNTIME_ROOT}/scripts/start_ollama_foreground.sh" \
    > "${LOG_DIR}/ollama.user-session.log" 2>&1 &
  ollama_pid=$!
  echo "${ollama_pid}" > "${RUN_DIR}/ollama.pid"
}

start_tradingview() {
  AI_OS_TRADINGVIEW_BROWSER_PORT="${TRADINGVIEW_PORT}" \
    AI_OS_TRADINGVIEW_BROWSER_PROFILE="/Volumes/Devarsh SSD/AI OS Data/browser-profiles/tradingview-cft" \
    bash "${RUNTIME_ROOT}/launchd/aios-tradingview-browser-service.sh" \
    > "${LOG_DIR}/tradingview_browser.user-session.log" 2>&1 &
  tradingview_pid=$!
  echo "${tradingview_pid}" > "${RUN_DIR}/tradingview_browser.pid"
}

start_api() {
  AI_OS_API_HOST="127.0.0.1" AI_OS_API_PORT="8765" \
    AI_OS_RUNTIME_ROOT="${RUNTIME_ROOT}" AI_OS_VAULT_ROOT="${VAULT_ROOT}" \
    AI_OS_WORKER_SCRIPT="${RUNTIME_ROOT}/scripts/run_agent_worker_once.py" \
    AI_OS_TRADINGVIEW_CDP_PORT="${TRADINGVIEW_PORT}" \
    python3 -u "${RUNTIME_ROOT}/api/ai_os_api_server.py" \
    > "${LOG_DIR}/ai_os_api.log" 2>&1 &
  api_pid=$!
  echo "${api_pid}" > "${RUN_DIR}/ai_os_api.pid"
}

start_agent() {
  AI_OS_RUNTIME_ROOT="${RUNTIME_ROOT}" AI_OS_VAULT_ROOT="${VAULT_ROOT}" \
    AI_OS_TRADINGVIEW_CDP_PORT="${TRADINGVIEW_PORT}" \
    bash "${RUNTIME_ROOT}/launchd/aios-agent-daemon-service.sh" \
    > "${LOG_DIR}/agent_daemon.user-session.log" 2>&1 &
  agent_pid=$!
  echo "${agent_pid}" > "${RUN_DIR}/agent_daemon.pid"
}

start_ui() {
  cd "${RUNTIME_ROOT}/ai-office-ui/dist"
  python3 -m http.server 5177 --bind 127.0.0.1 \
    > "${LOG_DIR}/ai_office_ui.log" 2>&1 &
  ui_pid=$!
  echo "${ui_pid}" > "${RUN_DIR}/ai_office_ui.pid"
  cd "${RUNTIME_ROOT}"
}

stop_children() {
  trap - EXIT INT TERM
  for pid in "${ui_pid}" "${agent_pid}" "${api_pid}" "${tradingview_pid}" "${ollama_pid}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  rm -f "${RUN_DIR}/supervisor.pid"
  exit 0
}
trap stop_children EXIT INT TERM

start_ollama
start_tradingview
start_api
start_agent
start_ui

while true; do
  sleep 10
  if ! kill -0 "${ollama_pid}" 2>/dev/null; then start_ollama; fi
  if ! kill -0 "${tradingview_pid}" 2>/dev/null; then start_tradingview; fi
  if ! kill -0 "${api_pid}" 2>/dev/null; then start_api; fi
  if ! kill -0 "${agent_pid}" 2>/dev/null; then start_agent; fi
  if ! kill -0 "${ui_pid}" 2>/dev/null; then start_ui; fi
done
