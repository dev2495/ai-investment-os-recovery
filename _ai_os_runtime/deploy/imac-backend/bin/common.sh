#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_REPO_ROOT="$(cd "${DEPLOY_ROOT}/../../.." && pwd)"
CONFIG_ROOT="${HOME}/Library/Application Support/AIOS"
ENV_FILE="${AI_OS_IMAC_ENV:-${CONFIG_ROOT}/imac.env}"
LAUNCHD_ROOT="${HOME}/Library/LaunchAgents"
LAUNCHD_LOG_ROOT="${HOME}/Library/Logs/AIOS"
SUPERVISOR_LABEL="com.devarsh.aios.imac.supervisor"
BACKUP_LABEL="com.devarsh.aios.imac.backup"
SUPERVISOR_PLIST="${LAUNCHD_ROOT}/${SUPERVISOR_LABEL}.plist"
BACKUP_PLIST="${LAUNCHD_ROOT}/${BACKUP_LABEL}.plist"
LAUNCHD_DOMAIN="gui/$(id -u)"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

load_env() {
  [[ -f "${ENV_FILE}" ]] || die "Missing iMac environment file: ${ENV_FILE}"
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  export PATH="/opt/homebrew/opt/node@20/bin:/opt/homebrew/opt/postgresql@16/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
  export COLIMA_HOME="${AI_OS_COLIMA_HOME}"
  export OLLAMA_MODELS="${AI_OS_OLLAMA_MODELS}"
  export OLLAMA_HOST="127.0.0.1:${AI_OS_OLLAMA_PORT:-11434}"
  export OLLAMA_NUM_PARALLEL=1
  export OLLAMA_CONTEXT_LENGTH=8192
  export OLLAMA_KEEP_ALIVE=5m
  export OLLAMA_NOHISTORY=true
  export OLLAMA_NO_CLOUD=1
  export PLAYWRIGHT_BROWSERS_PATH="${AI_OS_PLAYWRIGHT_BROWSERS_PATH}"
  export AI_OS_TRADINGVIEW_CDP_PORT
}

ensure_ssd() {
  local volume_name mount_point
  [[ -d "${AI_OS_SSD_ROOT}" ]] || die "SSD is not mounted at ${AI_OS_SSD_ROOT}"
  mount_point="$(diskutil info "${AI_OS_SSD_ROOT}" 2>/dev/null | awk -F: '/Mount Point/{sub(/^[[:space:]]+/, "", $2); print $2; exit}')"
  volume_name="$(diskutil info "${AI_OS_SSD_ROOT}" 2>/dev/null | awk -F: '/Volume Name/{sub(/^[[:space:]]+/, "", $2); print $2; exit}')"
  [[ "${mount_point}" == "${AI_OS_SSD_ROOT}" ]] || die "Unexpected SSD mount point: ${mount_point:-missing}"
  [[ "${volume_name}" == "Devarsh SSD" ]] || die "Unexpected SSD volume: ${volume_name:-missing}"
  [[ -d "${AI_OS_VAULT_ROOT}/ai memory" ]] || die "Obsidian vault is missing"
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${AI_OS_REPO_ROOT}/_ai_os_runtime/deploy/imac-backend/docker-compose.yml" "$@"
}

wait_http() {
  local url="$1" label="$2" attempts="${3:-90}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl --max-time 3 -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "${label} did not become ready at ${url}"
}

wait_container_healthy() {
  local container="$1" attempts="${2:-120}" i status
  for ((i=1; i<=attempts; i++)); do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container}" 2>/dev/null || true)"
    if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
      return 0
    fi
    sleep 1
  done
  docker logs --tail 100 "${container}" 2>/dev/null || true
  die "Container ${container} did not become healthy"
}

tailnet_dns_name() {
  command -v tailscale >/dev/null 2>&1 || return 1
  tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//'
}

runtime_python() {
  command -v python3
}

psql_bin() {
  if [[ -x /opt/homebrew/opt/postgresql@16/bin/psql ]]; then
    printf '%s\n' /opt/homebrew/opt/postgresql@16/bin/psql
  else
    command -v psql
  fi
}
