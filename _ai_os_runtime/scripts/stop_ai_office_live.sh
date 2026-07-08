#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${RUNTIME_ROOT}/run"
LAUNCHD_API_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.api.plist"
LAUNCHD_UI_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.ui.plist"
LAUNCHD_AGENT_DAEMON_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.agent-daemon.plist"
LAUNCHD_OLLAMA_PLIST="/Users/devarshthakkar/Library/LaunchAgents/com.devarsh.aios.ollama.plist"
LAUNCHD_DOMAIN="gui/$(id -u)"

stop_launchd_services() {
  local stopped=1
  if [[ -f "${LAUNCHD_UI_PLIST}" ]]; then
    launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_UI_PLIST}" 2>/dev/null && stopped=0 || true
  fi
  if [[ -f "${LAUNCHD_API_PLIST}" ]]; then
    launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_API_PLIST}" 2>/dev/null && stopped=0 || true
  fi
  if [[ -f "${LAUNCHD_AGENT_DAEMON_PLIST}" ]]; then
    launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_AGENT_DAEMON_PLIST}" 2>/dev/null && stopped=0 || true
  fi
  if [[ -f "${LAUNCHD_OLLAMA_PLIST}" ]]; then
    launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_OLLAMA_PLIST}" 2>/dev/null && stopped=0 || true
  fi
  return "${stopped}"
}

stop_pid_file() {
  local label="$1"
  local pid_file="$2"
  if [[ ! -f "${pid_file}" ]]; then
    echo "${label} not running"
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}"
    echo "Stopped ${label} (${pid})"
  else
    echo "${label} pid file was stale (${pid})"
  fi
  rm -f "${pid_file}"
}

if stop_launchd_services; then
  echo "Stopped AI OS LaunchAgents"
else
  stop_pid_file "AI Office UI" "${RUN_DIR}/ai_office_ui.pid"
  stop_pid_file "AI OS API" "${RUN_DIR}/ai_os_api.pid"
fi
