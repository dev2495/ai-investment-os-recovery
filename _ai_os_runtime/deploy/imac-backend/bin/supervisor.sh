#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"
load_env

LOG_ROOT="${AI_OS_DATA_ROOT}/logs/imac-backend"
RUN_ROOT="${AI_OS_DATA_ROOT}/run/imac-backend"
mkdir -p "${LOG_ROOT}" "${RUN_ROOT}"

children=()

stop_children() {
  local pid
  for pid in "${children[@]:-}"; do
    [[ -n "${pid}" ]] || continue
    kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap stop_children EXIT INT TERM

while [[ ! -d "${AI_OS_SSD_ROOT}" ]]; do
  log "Waiting for ${AI_OS_SSD_ROOT}"
  sleep 10
done
ensure_ssd

if ! colima status --profile ai-os >/dev/null 2>&1; then
  log "Starting lean Colima runtime"
  colima start --profile ai-os --runtime docker --cpu 2 --memory 3 --disk 32 --vm-type vz --mount-type virtiofs
fi

compose up -d
wait_container_healthy ai_os_postgres
wait_container_healthy ai_os_redis
wait_http "http://127.0.0.1:${AI_OS_QDRANT_HTTP_PORT}/collections" Qdrant 120

if ! curl --max-time 2 -fsS "http://127.0.0.1:${AI_OS_OLLAMA_PORT}/api/version" >/dev/null 2>&1; then
  log "Starting Ollama"
  ollama serve >>"${LOG_ROOT}/ollama.log" 2>>"${LOG_ROOT}/ollama.err" &
  children+=("$!")
fi
wait_http "http://127.0.0.1:${AI_OS_OLLAMA_PORT}/api/version" Ollama 90

if [[ "${AI_OS_ENABLE_TRADINGVIEW_BROWSER:-0}" == "1" ]]; then
  log "Starting the governed TradingView browser worker"
  node "${AI_OS_REPO_ROOT}/_ai_os_runtime/scripts/launch_tradingview_browser.mjs" \
    --port "${AI_OS_TRADINGVIEW_CDP_PORT}" \
    --profile-dir "${AI_OS_TRADINGVIEW_BROWSER_PROFILE}" \
    >>"${LOG_ROOT}/tradingview-browser.log" 2>>"${LOG_ROOT}/tradingview-browser.err" &
  children+=("$!")
  wait_http "http://127.0.0.1:${AI_OS_TRADINGVIEW_CDP_PORT}/json/version" "TradingView browser" 120
fi

export AI_OS_RUNTIME_ROOT="${AI_OS_REPO_ROOT}/_ai_os_runtime"
export AI_OS_ARTIFACT_ROOT="${AI_OS_DATA_ROOT}/artifacts"
export AI_OS_POSTGRES_HOST=127.0.0.1
export AI_OS_PSQL_BIN="$(psql_bin)"
export AI_OS_QDRANT_URL="http://127.0.0.1:${AI_OS_QDRANT_HTTP_PORT}"
export AI_OS_OLLAMA_URL="http://127.0.0.1:${AI_OS_OLLAMA_PORT}"
export AI_OS_API_HOST=127.0.0.1
export AI_OS_API_PORT
export AI_OS_ALLOWED_ORIGINS="${AI_OS_ALLOWED_ORIGINS:-http://127.0.0.1:${AI_OS_UI_PORT},http://localhost:${AI_OS_UI_PORT}}"
export AI_OS_ALLOW_TOKENLESS_LOOPBACK
export AI_OS_CHAT_MODEL_ROUTE=always_on_daily_driver

log "Starting AI OS API"
"$(runtime_python)" -u "${AI_OS_REPO_ROOT}/_ai_os_runtime/api/ai_os_api_server.py" \
  >>"${LOG_ROOT}/api.log" 2>>"${LOG_ROOT}/api.err" &
children+=("$!")

log "Starting AI OS UI"
"$(runtime_python)" -m http.server "${AI_OS_UI_PORT}" --bind 127.0.0.1 \
  --directory "${AI_OS_REPO_ROOT}/_ai_os_runtime/ai-office-ui/dist" \
  >>"${LOG_ROOT}/ui.log" 2>>"${LOG_ROOT}/ui.err" &
children+=("$!")

if [[ "${AI_OS_ENABLE_AGENT_DAEMON:-1}" == "1" ]]; then
  log "Starting role-scoped agent message daemon"
  "$(runtime_python)" -u "${AI_OS_REPO_ROOT}/_ai_os_runtime/scripts/run_agent_message_daemon.py" \
    >>"${LOG_ROOT}/agent-daemon.log" 2>>"${LOG_ROOT}/agent-daemon.err" &
  children+=("$!")
fi

wait_http "http://127.0.0.1:${AI_OS_API_PORT}/api/health" "AI OS API" 120
wait_http "http://127.0.0.1:${AI_OS_UI_PORT}/" "AI OS UI" 60
log "AI OS iMac backend is ready"

while true; do
  ensure_ssd
  for pid in "${children[@]:-}"; do
    if [[ -n "${pid}" ]] && ! kill -0 "${pid}" 2>/dev/null; then
      die "Supervised process ${pid} exited"
    fi
  done
  curl --max-time 5 -fsS "http://127.0.0.1:${AI_OS_API_PORT}/api/health" >/dev/null
  sleep 20
done
