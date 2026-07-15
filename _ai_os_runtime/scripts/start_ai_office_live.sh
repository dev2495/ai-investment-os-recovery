#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${RUNTIME_ROOT}/run"
LOG_DIR="${RUNTIME_ROOT}/logs"
API_HOST="${AI_OS_API_HOST:-127.0.0.1}"
API_PORT="${AI_OS_API_PORT:-8765}"
UI_PORT="${AI_OS_UI_PORT:-5177}"
LAUNCHD_API_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.api.plist"
LAUNCHD_UI_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.ui.plist"
LAUNCHD_AGENT_DAEMON_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.agent-daemon.plist"
LAUNCHD_OLLAMA_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.ollama.plist"
LAUNCHD_TRADINGVIEW_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.tradingview-browser.plist"
LAUNCHD_DOMAIN="gui/$(id -u)"
AIOS_SUPPORT_DIR="/Users/devarshthakkar/Library/Application Support/AIOS"
AIOS_BIN_DIR="${AIOS_SUPPORT_DIR}/bin"
AIOS_SERVICE_DIR="${AIOS_SUPPORT_DIR}/service"
AIOS_UI_DIST_DIR="${AIOS_SUPPORT_DIR}/ui-dist"
LAUNCHD_DIR="/Users/devarshthakkar/Library/LaunchAgents"
LAUNCHD_LOG_DIR="/Users/devarshthakkar/Library/Logs/AIOS"
OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://127.0.0.1:11434}"
AI_OS_START_OLLAMA_LAUNCHD="${AI_OS_START_OLLAMA_LAUNCHD:-1}"
TRADINGVIEW_CDP_PORT="${AI_OS_TRADINGVIEW_CDP_PORT:-9333}"
AI_OS_USE_LAUNCHD="${AI_OS_USE_LAUNCHD:-0}"

if [[ "${AI_OS_SKIP_STORAGE_GUARD:-0}" != "1" && -x "${RUNTIME_ROOT}/scripts/verify_external_storage.sh" ]]; then
  "${RUNTIME_ROOT}/scripts/verify_external_storage.sh" >/dev/null
fi

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

sync_launchd_payload() {
  mkdir -p "${LAUNCHD_DIR}" "${LAUNCHD_LOG_DIR}"
  mkdir -p "${AIOS_BIN_DIR}" "${AIOS_SERVICE_DIR}/api" "${AIOS_SERVICE_DIR}/scripts" "${AIOS_UI_DIST_DIR}"
  cp -f "${RUNTIME_ROOT}/launchd/aios-api-service.sh" "${AIOS_BIN_DIR}/aios-api-service.sh"
  cp -f "${RUNTIME_ROOT}/launchd/aios-ui-service.sh" "${AIOS_BIN_DIR}/aios-ui-service.sh"
  cp -f "${RUNTIME_ROOT}/launchd/aios-agent-daemon-service.sh" "${AIOS_BIN_DIR}/aios-agent-daemon-service.sh"
  cp -f "${RUNTIME_ROOT}/launchd/aios-ollama-service.sh" "${AIOS_BIN_DIR}/aios-ollama-service.sh"
  cp -f "${RUNTIME_ROOT}/launchd/aios-tradingview-browser-service.sh" "${AIOS_BIN_DIR}/aios-tradingview-browser-service.sh"
  cp -f "${RUNTIME_ROOT}/api/ai_os_api_server.py" "${AIOS_SERVICE_DIR}/api/ai_os_api_server.py"
  cp -f "${RUNTIME_ROOT}/scripts/run_agent_worker_once.py" "${AIOS_SERVICE_DIR}/scripts/run_agent_worker_once.py"
  cp -f "${RUNTIME_ROOT}/scripts/run_agent_message_daemon.py" "${AIOS_SERVICE_DIR}/scripts/run_agent_message_daemon.py"
  cp -f "${RUNTIME_ROOT}/scripts/run_client_accounting.py" "${AIOS_SERVICE_DIR}/scripts/run_client_accounting.py"
  cp -f "${RUNTIME_ROOT}/scripts/check_source_freshness.py" "${AIOS_SERVICE_DIR}/scripts/check_source_freshness.py"
  cp -f "${RUNTIME_ROOT}/scripts/check_tradingview_cdp.py" "${AIOS_SERVICE_DIR}/scripts/check_tradingview_cdp.py"
  cp -f "${RUNTIME_ROOT}/scripts/check_model_endpoint_live.py" "${AIOS_SERVICE_DIR}/scripts/check_model_endpoint_live.py"
  cp -f "${RUNTIME_ROOT}/scripts/aggregate_ticks_to_ohlcv.py" "${AIOS_SERVICE_DIR}/scripts/aggregate_ticks_to_ohlcv.py"
  cp -f "${RUNTIME_ROOT}/scripts/ingest_algo_sqlite.py" "${AIOS_SERVICE_DIR}/scripts/ingest_algo_sqlite.py"
  cp -f "${RUNTIME_ROOT}/scripts/refresh_event_quotes.py" "${AIOS_SERVICE_DIR}/scripts/refresh_event_quotes.py"
  rsync -a --delete "${RUNTIME_ROOT}/ai-office-ui/dist/" "${AIOS_UI_DIST_DIR}/"
  cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.api.plist" "${LAUNCHD_API_PLIST}"
  cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.ui.plist" "${LAUNCHD_UI_PLIST}"
  cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.agent-daemon.plist" "${LAUNCHD_AGENT_DAEMON_PLIST}"
  cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.ollama.plist" "${LAUNCHD_OLLAMA_PLIST}"
  cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.tradingview-browser.plist" "${LAUNCHD_TRADINGVIEW_PLIST}"
}

trim_launchd_logs() {
  local max_bytes="${AI_OS_LAUNCHD_LOG_MAX_BYTES:-8388608}"
  local keep_bytes="${AI_OS_LAUNCHD_LOG_KEEP_BYTES:-1048576}"
  local log_file size tmp_file
  for log_file in "${LAUNCHD_LOG_DIR}"/*.log "${LAUNCHD_LOG_DIR}"/*.err; do
    [[ -f "${log_file}" ]] || continue
    size="$(stat -f '%z' "${log_file}" 2>/dev/null || printf '0')"
    if [[ "${size}" -gt "${max_bytes}" ]]; then
      tmp_file="${log_file}.trim.$$"
      tail -c "${keep_bytes}" "${log_file}" > "${tmp_file}"
      cat "${tmp_file}" > "${log_file}"
      rm -f "${tmp_file}"
    fi
  done
}

start_launchd_services() {
  if [[ ! -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.api.plist" || ! -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.ui.plist" || ! -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.agent-daemon.plist" || ! -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.ollama.plist" || ! -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.tradingview-browser.plist" ]]; then
    return 1
  fi

  sync_launchd_payload
  launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_UI_PLIST}" 2>/dev/null || true
  launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_API_PLIST}" 2>/dev/null || true
  launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_AGENT_DAEMON_PLIST}" 2>/dev/null || true
  launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_OLLAMA_PLIST}" 2>/dev/null || true
  launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_TRADINGVIEW_PLIST}" 2>/dev/null || true
  trim_launchd_logs
  if [[ "${AI_OS_START_OLLAMA_LAUNCHD}" == "1" ]]; then
    launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_OLLAMA_PLIST}" 2>/dev/null || true
    launchctl kickstart -k "${LAUNCHD_DOMAIN}/com.devarsh.aios.ollama"
    if ! wait_for_http "${OLLAMA_HOST_URL}/api/version" "Ollama" "${LAUNCHD_LOG_DIR}/ollama.launchd.err"; then
      echo "Ollama remains degraded; continuing because the governed deterministic foundation does not require a model call."
    fi
  else
    echo "Skipped Ollama LaunchAgent by explicit request; use scripts/start_ollama_foreground.sh for a temporary local model server."
  fi
  launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_TRADINGVIEW_PLIST}" 2>/dev/null || true
  launchctl kickstart -k "${LAUNCHD_DOMAIN}/com.devarsh.aios.tradingview-browser"
  wait_for_http "http://127.0.0.1:${TRADINGVIEW_CDP_PORT}/json/version" "TradingView managed browser" "${LAUNCHD_LOG_DIR}/tradingview_browser.launchd.err" || return 1
  launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_API_PLIST}" 2>/dev/null || true
  launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_AGENT_DAEMON_PLIST}" 2>/dev/null || true
  launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_UI_PLIST}" 2>/dev/null || true
  launchctl kickstart -k "${LAUNCHD_DOMAIN}/com.devarsh.aios.api"
  launchctl kickstart -k "${LAUNCHD_DOMAIN}/com.devarsh.aios.agent-daemon"
  launchctl kickstart -k "${LAUNCHD_DOMAIN}/com.devarsh.aios.ui"
  wait_for_http "http://${API_HOST}:${API_PORT}/api/health" "AI OS API" "${LAUNCHD_LOG_DIR}/ai_os_api.launchd.err" || return 1
  wait_for_http "http://127.0.0.1:${UI_PORT}/" "AI Office UI" "${LAUNCHD_LOG_DIR}/ai_office_ui.launchd.err" || return 1
  echo "Started AI OS LaunchAgents:"
  if [[ "${AI_OS_START_OLLAMA_LAUNCHD}" == "1" ]]; then
    echo "  ${OLLAMA_HOST_URL}/api/version"
  fi
  echo "  http://${API_HOST}:${API_PORT}/api/health"
  echo "  http://127.0.0.1:${TRADINGVIEW_CDP_PORT}/json/version"
  echo "  com.devarsh.aios.agent-daemon"
  echo "  http://127.0.0.1:${UI_PORT}/"
  return 0
}

pid_for_port() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local log_file="$3"
  local attempts=60

  for _ in $(seq 1 "${attempts}"); do
    if curl --max-time 2 -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done

  echo "${label} did not become ready at ${url}"
  echo "Last log lines from ${log_file}:"
  tail -n 80 "${log_file}" 2>/dev/null || true
  return 1
}

start_api() {
  if [[ -f "${RUN_DIR}/ai_os_api.pid" ]] && kill -0 "$(cat "${RUN_DIR}/ai_os_api.pid")" 2>/dev/null; then
    echo "AI OS API already running on http://${API_HOST}:${API_PORT}"
    return
  fi

  local existing_pid
  existing_pid="$(pid_for_port "${API_PORT}")"
  if [[ -n "${existing_pid}" ]]; then
    echo "${existing_pid}" > "${RUN_DIR}/ai_os_api.pid"
    echo "AI OS API port ${API_PORT} already has listener pid ${existing_pid}; recorded it"
    wait_for_http "http://${API_HOST}:${API_PORT}/api/health" "AI OS API" "${LOG_DIR}/ai_os_api.log"
    return
  fi

  AI_OS_API_HOST="${API_HOST}" AI_OS_API_PORT="${API_PORT}" AI_OS_RUNTIME_ROOT="${RUNTIME_ROOT}" \
    AI_OS_VAULT_ROOT="/Volumes/Devarsh SSD/Obsidian memory " AI_OS_WORKER_SCRIPT="${RUNTIME_ROOT}/scripts/run_agent_worker_once.py" \
    AI_OS_TRADINGVIEW_CDP_PORT="${TRADINGVIEW_CDP_PORT}" RUNTIME_ROOT="${RUNTIME_ROOT}" \
    nohup bash -c 'cd "$RUNTIME_ROOT"; python3 -u api/ai_os_api_server.py; code=$?; printf "AI OS API exited with code %s\n" "$code" >&2; exit "$code"' \
    > "${LOG_DIR}/ai_os_api.log" 2>&1 < /dev/null &
  echo $! > "${RUN_DIR}/ai_os_api.pid"
  wait_for_http "http://${API_HOST}:${API_PORT}/api/health" "AI OS API" "${LOG_DIR}/ai_os_api.log"
  echo "Started AI OS API on http://${API_HOST}:${API_PORT}"
}

start_ollama_user_session() {
  if curl --max-time 2 -fsS "${OLLAMA_HOST_URL}/api/version" >/dev/null 2>&1; then
    echo "Ollama already running at ${OLLAMA_HOST_URL}"
    return
  fi
  OLLAMA_MODELS="/Volumes/Devarsh SSD/AI OS Data/ollama/models" OLLAMA_NO_CLOUD=1 \
    nohup bash "${RUNTIME_ROOT}/scripts/start_ollama_foreground.sh" \
    > "${LOG_DIR}/ollama.user-session.log" 2>&1 < /dev/null &
  echo $! > "${RUN_DIR}/ollama.pid"
  wait_for_http "${OLLAMA_HOST_URL}/api/version" "Ollama" "${LOG_DIR}/ollama.user-session.log"
  echo "Started user-session Ollama with external-SSD model storage"
}

start_tradingview_browser_user_session() {
  local existing_pid
  existing_pid="$(pid_for_port "${TRADINGVIEW_CDP_PORT}")"
  if [[ -n "${existing_pid}" ]] && curl --max-time 2 -fsS "http://127.0.0.1:${TRADINGVIEW_CDP_PORT}/json/version" >/dev/null 2>&1; then
    echo "${existing_pid}" > "${RUN_DIR}/tradingview_browser.pid"
    echo "TradingView browser already running on CDP ${TRADINGVIEW_CDP_PORT}"
    return
  fi
  AI_OS_TRADINGVIEW_BROWSER_PORT="${TRADINGVIEW_CDP_PORT}" \
    AI_OS_TRADINGVIEW_BROWSER_PROFILE="/Volumes/Devarsh SSD/AI OS Data/browser-profiles/tradingview-cft" \
    nohup bash "${RUNTIME_ROOT}/launchd/aios-tradingview-browser-service.sh" \
    > "${LOG_DIR}/tradingview_browser.user-session.log" 2>&1 < /dev/null &
  echo $! > "${RUN_DIR}/tradingview_browser.pid"
  wait_for_http "http://127.0.0.1:${TRADINGVIEW_CDP_PORT}/json/version" "TradingView managed browser" "${LOG_DIR}/tradingview_browser.user-session.log"
  echo "Started user-session TradingView managed browser on CDP ${TRADINGVIEW_CDP_PORT}"
}

start_agent_daemon_user_session() {
  if [[ -f "${RUN_DIR}/agent_daemon.pid" ]] && kill -0 "$(cat "${RUN_DIR}/agent_daemon.pid")" 2>/dev/null; then
    echo "Agent daemon already running"
    return
  fi
  AI_OS_RUNTIME_ROOT="${RUNTIME_ROOT}" AI_OS_VAULT_ROOT="/Volumes/Devarsh SSD/Obsidian memory " \
    AI_OS_TRADINGVIEW_CDP_PORT="${TRADINGVIEW_CDP_PORT}" \
    nohup bash "${RUNTIME_ROOT}/launchd/aios-agent-daemon-service.sh" \
    > "${LOG_DIR}/agent_daemon.user-session.log" 2>&1 < /dev/null &
  echo $! > "${RUN_DIR}/agent_daemon.pid"
  sleep 2
  if ! kill -0 "$(cat "${RUN_DIR}/agent_daemon.pid")" 2>/dev/null; then
    echo "Agent daemon did not stay running"
    tail -n 80 "${LOG_DIR}/agent_daemon.user-session.log" 2>/dev/null || true
    return 1
  fi
  echo "Started user-session agent daemon"
}

stop_installed_launchd_services() {
  local plist
  for plist in "${LAUNCHD_UI_PLIST}" "${LAUNCHD_API_PLIST}" "${LAUNCHD_AGENT_DAEMON_PLIST}" "${LAUNCHD_OLLAMA_PLIST}" "${LAUNCHD_TRADINGVIEW_PLIST}"; do
    launchctl bootout "${LAUNCHD_DOMAIN}" "${plist}" 2>/dev/null || true
  done
}

start_terminal_supervisor() {
  local supervisor="${RUNTIME_ROOT}/scripts/run_ai_office_supervisor.command"
  local supervisor_pid_file="${RUN_DIR}/supervisor.pid"
  if [[ -f "${supervisor_pid_file}" ]] && kill -0 "$(cat "${supervisor_pid_file}")" 2>/dev/null; then
    echo "AI OS user-session supervisor already running"
  else
    rm -f "${supervisor_pid_file}"
    chmod +x "${supervisor}"
    /usr/bin/open -gj -a Terminal "${supervisor}"
  fi
  wait_for_http "${OLLAMA_HOST_URL}/api/version" "Ollama" "${LOG_DIR}/ollama.user-session.log"
  wait_for_http "http://127.0.0.1:${TRADINGVIEW_CDP_PORT}/json/version" "TradingView managed browser" "${LOG_DIR}/tradingview_browser.user-session.log"
  wait_for_http "http://${API_HOST}:${API_PORT}/api/health" "AI OS API" "${LOG_DIR}/ai_os_api.log"
  wait_for_http "http://127.0.0.1:${UI_PORT}/" "AI Office UI" "${LOG_DIR}/ai_office_ui.log"
  if [[ ! -f "${RUN_DIR}/agent_daemon.pid" ]] || ! kill -0 "$(cat "${RUN_DIR}/agent_daemon.pid")" 2>/dev/null; then
    echo "Agent daemon did not become ready under the user-session supervisor"
    tail -n 80 "${LOG_DIR}/agent_daemon.user-session.log" 2>/dev/null || true
    return 1
  fi
  echo "Started persistent user-session AI OS supervisor"
}

start_ui() {
  if [[ -f "${RUN_DIR}/ai_office_ui.pid" ]] && kill -0 "$(cat "${RUN_DIR}/ai_office_ui.pid")" 2>/dev/null; then
    echo "AI Office UI already running on http://127.0.0.1:${UI_PORT}"
    return
  fi

  local existing_pid
  existing_pid="$(pid_for_port "${UI_PORT}")"
  if [[ -n "${existing_pid}" ]]; then
    echo "${existing_pid}" > "${RUN_DIR}/ai_office_ui.pid"
    echo "AI Office UI port ${UI_PORT} already has listener pid ${existing_pid}; recorded it"
    wait_for_http "http://127.0.0.1:${UI_PORT}/" "AI Office UI" "${LOG_DIR}/ai_office_ui.log"
    return
  fi

  (
    cd "${RUNTIME_ROOT}/ai-office-ui"
    VITE_AI_OS_API_URL="http://${API_HOST}:${API_PORT}" \
      nohup npm run dev -- --host 127.0.0.1 --port "${UI_PORT}" \
      > "${LOG_DIR}/ai_office_ui.log" 2>&1 < /dev/null &
    echo $! > "${RUN_DIR}/ai_office_ui.pid"
  )
  wait_for_http "http://127.0.0.1:${UI_PORT}/" "AI Office UI" "${LOG_DIR}/ai_office_ui.log"
  echo "Started AI Office UI on http://127.0.0.1:${UI_PORT}"
}

if [[ "${AI_OS_USE_LAUNCHD}" == "1" ]] && start_launchd_services; then
  :
else
  sync_launchd_payload
  stop_installed_launchd_services
  start_terminal_supervisor
fi

echo "Logs:"
echo "  ${LOG_DIR}/ai_os_api.log"
echo "  ${LOG_DIR}/ai_office_ui.log"
