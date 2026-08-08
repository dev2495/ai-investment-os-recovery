#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/common.sh"
load_env

LOG_ROOT="${AI_OS_RUNTIME_LOG_ROOT:-${HOME}/Library/Logs/AIOS/runtime}"
RUN_ROOT="${AI_OS_RUNTIME_RUN_ROOT:-${HOME}/Library/Application Support/AIOS/run}"
mkdir -p "${LOG_ROOT}" "${RUN_ROOT}"

SUPERVISOR_LOCK="${RUN_ROOT}/supervisor.lock"
if ! mkdir "${SUPERVISOR_LOCK}" 2>/dev/null; then
  existing_pid="$(cat "${SUPERVISOR_LOCK}/pid" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    die "AI OS supervisor is already running as PID ${existing_pid}"
  fi
  rm -f "${SUPERVISOR_LOCK}/pid"
  rmdir "${SUPERVISOR_LOCK}" 2>/dev/null || die "Cannot recover stale supervisor lock"
  mkdir "${SUPERVISOR_LOCK}"
fi
printf '%s\n' "$$" > "${SUPERVISOR_LOCK}/pid"

children=()
colima_start_pid=""
nanbeige_pid=""

stop_children() {
  local pid
  if [[ -n "${colima_start_pid}" ]]; then
    kill -TERM "${colima_start_pid}" 2>/dev/null || true
  fi
  if [[ -n "${nanbeige_pid}" ]]; then
    kill "${nanbeige_pid}" 2>/dev/null || true
  fi
  for pid in "${children[@]:-}"; do
    [[ -n "${pid}" ]] || continue
    kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  rm -f "${RUN_ROOT}/api.pid" "${RUN_ROOT}/ui.pid" "${RUN_ROOT}/agent-daemon.pid"
  rm -f "${SUPERVISOR_LOCK}/pid"
  rmdir "${SUPERVISOR_LOCK}" 2>/dev/null || true
}
trap stop_children EXIT INT TERM

stop_stale_pidfile() {
  local pidfile="$1" expected="$2" label="$3" pid command_line
  [[ -f "${pidfile}" ]] || return 0
  pid="$(cat "${pidfile}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || { rm -f "${pidfile}"; return 0; }
  if ! kill -0 "${pid}" 2>/dev/null; then
    rm -f "${pidfile}"
    return 0
  fi
  command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
  [[ "${command_line}" == *"${expected}"* ]] || die "${label} PID file points to unrelated process ${pid}"
  log "Stopping stale ${label} process ${pid}"
  kill "${pid}" 2>/dev/null || true
  for _ in {1..20}; do
    kill -0 "${pid}" 2>/dev/null || break
    sleep 0.25
  done
  kill -KILL "${pid}" 2>/dev/null || true
  rm -f "${pidfile}"
}

stop_stale_listener() {
  local port="$1" expected="$2" label="$3" pid command_line
  command -v lsof >/dev/null 2>&1 || return 0
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    [[ "${command_line}" == *"${expected}"* ]] || die "${label} port ${port} is owned by unrelated process ${pid}"
    log "Stopping stale ${label} listener ${pid} on ${port}"
    kill "${pid}" 2>/dev/null || true
  done < <(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)
  for _ in {1..20}; do
    lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.25
  done
  die "${label} port ${port} did not clear after stopping the stale AI OS process"
}

# Keep the always-on backend awake while allowing the display to sleep and lock.
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -is -w "$$" &
  children+=("$!")
fi

while [[ ! -d "${AI_OS_SSD_ROOT}" ]]; do
  log "Waiting for ${AI_OS_SSD_ROOT}"
  sleep 10
done
ensure_ssd

start_colima_with_timeout() {
  local timeout_seconds="$1" i
  shift

  colima start "$@" &
  colima_start_pid="$!"

  for ((i=1; i<=timeout_seconds; i++)); do
    if docker info >/dev/null 2>&1; then
      for _ in {1..15}; do
        kill -0 "${colima_start_pid}" 2>/dev/null || break
        sleep 1
      done
      if kill -0 "${colima_start_pid}" 2>/dev/null; then
        log "Colima CLI remained active after Docker became ready; detaching it"
        kill -TERM "${colima_start_pid}" 2>/dev/null || true
      fi
      wait "${colima_start_pid}" 2>/dev/null || true
      colima_start_pid=""
      return 0
    fi

    if ! kill -0 "${colima_start_pid}" 2>/dev/null; then
      wait "${colima_start_pid}" 2>/dev/null || true
      colima_start_pid=""
      return 1
    fi
    sleep 1
  done

  log "Colima start exceeded ${timeout_seconds}s; terminating the stuck CLI"
  kill -TERM "${colima_start_pid}" 2>/dev/null || true
  sleep 2
  kill -KILL "${colima_start_pid}" 2>/dev/null || true
  wait "${colima_start_pid}" 2>/dev/null || true
  colima_start_pid=""
  return 1
}

colima_args=(
  --profile ai-os
  --runtime docker
  --cpu 2
  --memory 3
  --disk 32
  --vm-type vz
  --mount-type virtiofs
)

if ! docker info >/dev/null 2>&1; then
  log "Starting lean Colima runtime"
  if ! start_colima_with_timeout 90 "${colima_args[@]}"; then
    log "Colima did not expose Docker; repairing stale VM state once"
    colima stop --profile ai-os --force || true
    if ! start_colima_with_timeout 180 "${colima_args[@]}"; then
      die "Docker did not become ready after Colima state repair"
    fi
  fi
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

nanbeige_state="disabled"
nanbeige_started_at=0
nanbeige_next_restart_at=0
nanbeige_last_warning_at=0
NANBEIGE_ROOT="${AI_OS_NANBEIGE_ROOT:-${AI_OS_DATA_ROOT}/models/nanbeige42-runtime}"
NANBEIGE_RUNTIME_REVISION="${AI_OS_NANBEIGE_RUNTIME_REVISION:-c6640a1c0cf7b38df342b67021a3900b04d092e7}"
NANBEIGE_RUNTIME_ROOT="${AI_OS_NANBEIGE_RUNTIME_ROOT:-${HOME}/AI_OS_NODE/model-runtimes/nanbeige42/${NANBEIGE_RUNTIME_REVISION}}"
NANBEIGE_RUNTIME_BIN="${NANBEIGE_RUNTIME_ROOT}/bin"
NANBEIGE_SERVER="${NANBEIGE_RUNTIME_BIN}/llama-server"
NANBEIGE_MODEL="${NANBEIGE_ROOT}/nanbeige4.2-3b-Q4_K_M.gguf"
NANBEIGE_PORT="${AI_OS_NANBEIGE_PORT:-11436}"
NANBEIGE_ALIAS="nanbeige/nanbeige4.2:3b-Q4_K_M"
NANBEIGE_START_GRACE_SECONDS="${AI_OS_NANBEIGE_START_GRACE_SECONDS:-240}"
NANBEIGE_RESTART_DELAY_SECONDS="${AI_OS_NANBEIGE_RESTART_DELAY_SECONDS:-60}"

start_nanbeige_runtime() {
  if curl --max-time 3 -fsS "http://127.0.0.1:${NANBEIGE_PORT}/v1/models" >/dev/null 2>&1; then
    nanbeige_state="ready"
    nanbeige_pid=""
    log "Reusing the isolated Nanbeige4.2 runtime"
    return 0
  fi

  log "Starting the isolated Nanbeige4.2 runtime without blocking mission control"
  DYLD_LIBRARY_PATH="${NANBEIGE_RUNTIME_BIN}" "${NANBEIGE_SERVER}" \
    --model "${NANBEIGE_MODEL}" --alias "${NANBEIGE_ALIAS}" \
    --host 127.0.0.1 --port "${NANBEIGE_PORT}" --ctx-size 8192 \
    --n-gpu-layers 99 --parallel 1 --jinja \
    --reasoning off --reasoning-budget 0 \
    >>"${LOG_ROOT}/nanbeige42.log" 2>>"${LOG_ROOT}/nanbeige42.err" &
  nanbeige_pid="$!"
  nanbeige_started_at="$(date +%s)"
  nanbeige_state="warming"
}

if [[ "${AI_OS_ENABLE_NANBEIGE42:-1}" == "1" ]]; then
  if [[ -x "${NANBEIGE_SERVER}" && -f "${NANBEIGE_MODEL}" ]]; then
    start_nanbeige_runtime
  else
    log "Nanbeige4.2 model or internal runtime bundle is missing; mission control will use another healthy route"
  fi
fi

export AI_OS_RUNTIME_ROOT="${AI_OS_REPO_ROOT}/_ai_os_runtime"
export AI_OS_ARTIFACT_ROOT="${AI_OS_DATA_ROOT}/artifacts"
export AI_OS_POSTGRES_HOST=127.0.0.1
export AI_OS_PSQL_BIN="$(psql_bin)"
export AI_OS_QDRANT_URL="http://127.0.0.1:${AI_OS_QDRANT_HTTP_PORT}"
export AI_OS_OLLAMA_URL="http://127.0.0.1:${AI_OS_OLLAMA_PORT}"
export AI_OS_MLX_URL="${AI_OS_MLX_URL:-http://100.75.156.32:11435/v1}"
export AI_OS_MLX_REQUEST_MODEL="${AI_OS_MLX_REQUEST_MODEL:-default_model}"
export AI_OS_LOCAL_OPENAI_URL="${AI_OS_LOCAL_OPENAI_URL:-http://100.75.156.32:11435/v1}"
export AI_OS_LOCAL_OPENAI_REQUEST_MODEL="${AI_OS_LOCAL_OPENAI_REQUEST_MODEL:-default_model}"
export AI_OS_API_HOST=127.0.0.1
export AI_OS_API_PORT
export AI_OS_ALLOWED_ORIGINS="${AI_OS_ALLOWED_ORIGINS:-http://127.0.0.1:${AI_OS_UI_PORT},http://localhost:${AI_OS_UI_PORT}}"
export AI_OS_ALLOW_TOKENLESS_LOOPBACK
export AI_OS_CHAT_MODEL_ROUTE="${AI_OS_CHAT_MODEL_ROUTE:-charlie_munger_orchestration}"

stop_stale_pidfile "${RUN_ROOT}/agent-daemon.pid" "run_agent_message_daemon.py" "agent message daemon"
stop_stale_listener "${AI_OS_API_PORT}" "ai_os_api_server.py" "AI OS API"
stop_stale_listener "${AI_OS_UI_PORT}" "serve_spa.py" "AI OS UI"

log "Starting AI OS API"
"$(runtime_python)" -u "${AI_OS_REPO_ROOT}/_ai_os_runtime/api/ai_os_api_server.py" \
  >>"${LOG_ROOT}/api.log" 2>>"${LOG_ROOT}/api.err" &
children+=("$!")
printf '%s\n' "$!" > "${RUN_ROOT}/api.pid"

log "Starting AI OS UI"
"$(runtime_python)" -u "${AI_OS_REPO_ROOT}/_ai_os_runtime/scripts/serve_spa.py" \
  --host 127.0.0.1 --port "${AI_OS_UI_PORT}" \
  --directory "${AI_OS_REPO_ROOT}/_ai_os_runtime/ai-office-ui/dist" \
  >>"${LOG_ROOT}/ui.log" 2>>"${LOG_ROOT}/ui.err" &
children+=("$!")
printf '%s\n' "$!" > "${RUN_ROOT}/ui.pid"

if [[ "${AI_OS_ENABLE_AGENT_DAEMON:-1}" == "1" ]]; then
  log "Starting role-scoped agent message daemon"
  AI_OS_WORKLOAD_PSQL_MODE="${AI_OS_WORKLOAD_PSQL_MODE:-docker}" \
  "$(runtime_python)" -u "${AI_OS_REPO_ROOT}/_ai_os_runtime/scripts/run_agent_message_daemon.py" \
    >>"${LOG_ROOT}/agent-daemon.log" 2>>"${LOG_ROOT}/agent-daemon.err" &
  children+=("$!")
  printf '%s\n' "$!" > "${RUN_ROOT}/agent-daemon.pid"
fi

wait_http "http://127.0.0.1:${AI_OS_API_PORT}/api/liveness" "AI OS API" 120
wait_http "http://127.0.0.1:${AI_OS_UI_PORT}/" "AI OS UI" 60
log "AI OS iMac backend is ready"

while true; do
  now="$(date +%s)"
  ensure_ssd
  for pid in "${children[@]:-}"; do
    if [[ -n "${pid}" ]] && ! kill -0 "${pid}" 2>/dev/null; then
      die "Supervised process ${pid} exited"
    fi
  done
  if [[ "${AI_OS_ENABLE_NANBEIGE42:-1}" == "1" && -x "${NANBEIGE_SERVER}" && -f "${NANBEIGE_MODEL}" ]]; then
    if curl --max-time 5 -fsS "http://127.0.0.1:${NANBEIGE_PORT}/v1/models" >/dev/null 2>&1; then
      if [[ "${nanbeige_state}" != "ready" ]]; then
        log "Nanbeige4.2 is ready"
      fi
      nanbeige_state="ready"
    elif [[ "${nanbeige_state}" == "warming" ]]; then
      if [[ -z "${nanbeige_pid}" ]] || ! kill -0 "${nanbeige_pid}" 2>/dev/null; then
        log "Nanbeige4.2 exited during warmup; retrying in ${NANBEIGE_RESTART_DELAY_SECONDS}s"
        nanbeige_pid=""
        nanbeige_state="unavailable"
        nanbeige_next_restart_at="$((now + NANBEIGE_RESTART_DELAY_SECONDS))"
      elif (( now - nanbeige_started_at >= NANBEIGE_START_GRACE_SECONDS )); then
        log "Nanbeige4.2 warmup exceeded ${NANBEIGE_START_GRACE_SECONDS}s; restarting it without affecting mission control"
        kill "${nanbeige_pid}" 2>/dev/null || true
        wait "${nanbeige_pid}" 2>/dev/null || true
        nanbeige_pid=""
        nanbeige_state="unavailable"
        nanbeige_next_restart_at="$((now + NANBEIGE_RESTART_DELAY_SECONDS))"
      elif (( now - nanbeige_last_warning_at >= 60 )); then
        log "Nanbeige4.2 is still warming; API and UI remain available"
        nanbeige_last_warning_at="${now}"
      fi
    else
      if [[ -n "${nanbeige_pid}" ]] && kill -0 "${nanbeige_pid}" 2>/dev/null; then
        kill "${nanbeige_pid}" 2>/dev/null || true
        wait "${nanbeige_pid}" 2>/dev/null || true
      fi
      nanbeige_pid=""
      nanbeige_state="unavailable"
      if (( now >= nanbeige_next_restart_at )); then
        start_nanbeige_runtime
      fi
    fi
  fi
  curl --max-time 5 -fsS "http://127.0.0.1:${AI_OS_API_PORT}/api/liveness" >/dev/null \
    || die "AI OS API heartbeat failed"
  sleep 20
done
