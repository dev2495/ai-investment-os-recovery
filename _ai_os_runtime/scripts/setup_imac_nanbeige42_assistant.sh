#!/bin/bash
set -euo pipefail

ENV_FILE="${AI_OS_IMAC_ENV:-${HOME}/Library/Application Support/AIOS/imac.env}"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

REPO_ROOT="${AI_OS_REPO_ROOT:-${HOME}/AI_OS_NODE/current}"
RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-${REPO_ROOT}/_ai_os_runtime}"
DATA_ROOT="${AI_OS_DATA_ROOT:-/Volumes/Devarsh SSD/AI OS Data}"
DOCKER_BIN="${AI_OS_DOCKER_BIN:-/opt/homebrew/bin/docker}"
PYTHON_BIN="${AI_OS_PYTHON_BIN:-/opt/homebrew/bin/python3.13}"
MODEL="nanbeige/nanbeige4.2:3b-Q4_K_M"
MODEL_REVISION="f56ec5a9650268aa098496734743c25ea778bd2d"
RUNTIME_REVISION="c6640a1c0cf7b38df342b67021a3900b04d092e7"
ROOT="${AI_OS_NANBEIGE_ROOT:-${DATA_ROOT}/models/nanbeige42-runtime}"
SOURCE_ROOT="${ROOT}/source/llama.cpp"
BUILD_ROOT="${SOURCE_ROOT}/build"
MODEL_ROOT="${ROOT}/model-hf-f56ec5"
BF16_GGUF="${ROOT}/nanbeige4.2-3b-bf16.gguf"
QUANT_GGUF="${ROOT}/nanbeige4.2-3b-Q4_K_M.gguf"
VENV="${ROOT}/venv-convert"
PORT="${AI_OS_NANBEIGE_PORT:-11436}"
BASE_URL="http://127.0.0.1:${PORT}/v1"
LOG_ROOT="${AI_OS_RUNTIME_LOG_ROOT:-${HOME}/Library/Logs/AIOS/runtime}"
TEMP_SERVER_PID=""

record_probe_state() {
  local endpoint_status="$1" health_status="$2" stage="$3" message="$4"
  "${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
    -v endpoint_status="${endpoint_status}" -v health_status="${health_status}" \
    -v probe_stage="${stage}" -v probe_message="${message}" \
    -v runtime_revision="${RUNTIME_REVISION}" -v model_revision="${MODEL_REVISION}" <<'SQL'
UPDATE agent.model_endpoints
SET status=:'endpoint_status',
    health_status=:'health_status',
    last_checked_at=now(),
    last_error=NULLIF(:'probe_message', ''),
    config=config || jsonb_build_object(
      'last_probe_stage', :'probe_stage',
      'last_probe_at', now(),
      'runtime_revision', :'runtime_revision',
      'model_revision', :'model_revision'
    ),
    updated_at=now()
WHERE endpoint_key='nanbeige42_3b_q4_local_openai_imac';

INSERT INTO core.connector_health_checks (
    target_kind, target_key, check_name, check_type, status,
    error_message, sample_payload, checked_by
) VALUES (
    'model_endpoint', 'nanbeige42_3b_q4_local_openai_imac',
    'Nanbeige4.2 isolated runtime', 'runtime_probe', :'health_status',
    NULLIF(:'probe_message', ''),
    jsonb_build_object('stage', :'probe_stage', 'model', 'nanbeige/nanbeige4.2:3b-Q4_K_M'),
    'AI Runtime Engineer'
);
SQL
}

cleanup() {
  if [[ -n "${TEMP_SERVER_PID}" ]]; then
    kill "${TEMP_SERVER_PID}" 2>/dev/null || true
    wait "${TEMP_SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

[[ -x "${DOCKER_BIN}" ]] || { echo "Docker is not installed at ${DOCKER_BIN}." >&2; exit 2; }
[[ -x "${PYTHON_BIN}" ]] || { echo "Python is not installed at ${PYTHON_BIN}." >&2; exit 2; }
for command in git cmake shasum curl; do
  command -v "${command}" >/dev/null 2>&1 || { echo "${command} is required." >&2; exit 2; }
done
[[ -f "${RUNTIME_ROOT}/postgres/init/175_nanbeige42_isolated_local_openai.sql" ]] || {
  echo "Nanbeige4.2 isolated-runtime migration is missing." >&2
  exit 3
}

mkdir -p "${ROOT}" "${ROOT}/huggingface" "${ROOT}/pip-cache" "${ROOT}/tmp" "${LOG_ROOT}"
"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
  < "${RUNTIME_ROOT}/postgres/init/175_nanbeige42_isolated_local_openai.sql"
record_probe_state "probing" "checking" "runtime_prepare" ""

if [[ ! -d "${SOURCE_ROOT}/.git" ]]; then
  mkdir -p "${ROOT}/source"
  git clone --branch nanbeige42 --single-branch https://github.com/Nanbeige/llama.cpp.git "${SOURCE_ROOT}"
fi
git -C "${SOURCE_ROOT}" fetch origin nanbeige42
git -C "${SOURCE_ROOT}" checkout --detach "${RUNTIME_REVISION}"

if [[ ! -x "${BUILD_ROOT}/bin/llama-server" || ! -x "${BUILD_ROOT}/bin/llama-quantize" ]]; then
  CXX_INCLUDE="$(ls -d /Library/Developer/CommandLineTools/SDKs/MacOSX*.sdk/usr/include/c++/v1 2>/dev/null | tail -n 1)"
  [[ -d "${CXX_INCLUDE}" ]] || { record_probe_state "blocked" "build_failed" "runtime_build" "Apple C++ headers were not found."; exit 4; }
  cmake -S "${SOURCE_ROOT}" -B "${BUILD_ROOT}" \
    -DGGML_METAL=ON -DLLAMA_CURL=ON \
    -DCMAKE_CXX_FLAGS="-isystem ${CXX_INCLUDE}"
  cmake --build "${BUILD_ROOT}" --config Release --parallel 2 --target llama-server llama-quantize
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV}"
fi
PIP_CACHE_DIR="${ROOT}/pip-cache" TMPDIR="${ROOT}/tmp" "${VENV}/bin/python" -m pip install \
  "torch==2.13.0" "numpy==2.3.5" "transformers==4.57.6" \
  "sentencepiece>=0.1.98,<0.3.0" "protobuf>=4.21,<5" \
  "huggingface_hub==0.36.0" "safetensors==0.6.2"

if [[ ! -f "${MODEL_ROOT}/model-00001-of-00002.safetensors" || ! -f "${MODEL_ROOT}/model-00002-of-00002.safetensors" ]]; then
  HF_HOME="${ROOT}/huggingface" TMPDIR="${ROOT}/tmp" "${VENV}/bin/python" -c \
    "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Nanbeige/Nanbeige4.2-3B', revision='${MODEL_REVISION}', cache_dir='${ROOT}/huggingface', local_dir='${MODEL_ROOT}', ignore_patterns=['*.pdf','.eval_results/*','figures/*'])"
fi

if [[ ! -f "${BF16_GGUF}" ]]; then
  "${VENV}/bin/python" "${SOURCE_ROOT}/convert_hf_to_gguf.py" "${MODEL_ROOT}" \
    --outfile "${BF16_GGUF}" --outtype bf16
fi
if [[ ! -f "${QUANT_GGUF}" ]]; then
  "${BUILD_ROOT}/bin/llama-quantize" "${BF16_GGUF}" "${QUANT_GGUF}" Q4_K_M
fi

MODEL_SHA="$(shasum -a 256 "${QUANT_GGUF}" | awk '{print $1}')"
RUNTIME_VERSION="$(DYLD_LIBRARY_PATH="${BUILD_ROOT}/bin" "${BUILD_ROOT}/bin/llama-server" --version 2>&1 | head -n 1)"
record_probe_state "probing" "checking" "conversation_v1" ""

if ! curl --max-time 3 -fsS "${BASE_URL}/models" >/dev/null 2>&1; then
  DYLD_LIBRARY_PATH="${BUILD_ROOT}/bin" "${BUILD_ROOT}/bin/llama-server" \
    --model "${QUANT_GGUF}" --alias "${MODEL}" \
    --host 127.0.0.1 --port "${PORT}" --ctx-size 8192 \
    --n-gpu-layers 99 --parallel 1 --jinja \
    >>"${LOG_ROOT}/nanbeige42.log" 2>>"${LOG_ROOT}/nanbeige42.err" &
  TEMP_SERVER_PID="$!"
  for _ in {1..90}; do
    curl --max-time 3 -fsS "${BASE_URL}/models" >/dev/null 2>&1 && break
    kill -0 "${TEMP_SERVER_PID}" 2>/dev/null || {
      record_probe_state "blocked" "runtime_failed" "server_start" "Nanbeige llama-server exited during startup."
      exit 5
    }
    sleep 2
  done
fi
curl --max-time 3 -fsS "${BASE_URL}/models" >/dev/null || {
  record_probe_state "blocked" "runtime_failed" "server_start" "Nanbeige OpenAI endpoint did not become ready."
  exit 5
}

if ! python3 "${RUNTIME_ROOT}/scripts/run_local_model_evals.py" \
  --model "${MODEL}" --provider local_openai --base-url "${BASE_URL}" \
  --artifact-root "${DATA_ROOT}/evals/local_models" --persist --promote; then
  record_probe_state "disabled" "eval_failed" "conversation_v1" \
    "The exact Nanbeige GGUF did not pass conversation_v1."
  exit 6
fi

"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
  -v model_sha="${MODEL_SHA}" -v runtime_version="${RUNTIME_VERSION}" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM agent.local_model_registry
    WHERE model_name='nanbeige/nanbeige4.2:3b-Q4_K_M'
      AND eval_suite='conversation_v1'
      AND promotion_status='approved'
      AND coalesce(last_eval_score,0) >= 0.8
  ) THEN
    RAISE EXCEPTION 'Nanbeige4.2 activation refused: promotion evidence is missing';
  END IF;
END $$;

UPDATE agent.model_routes
SET enabled=true
WHERE route_name='nanbeige42_local_assistant';

UPDATE agent.model_endpoints
SET status='active', health_status='healthy', last_checked_at=now(), last_error=NULL,
    config=config || jsonb_build_object(
      'gguf_sha256', :'model_sha',
      'runtime_version', :'runtime_version'
    ),
    updated_at=now()
WHERE endpoint_key='nanbeige42_3b_q4_local_openai_imac';

UPDATE agent.agent_model_assignments
SET fallback_route='nanbeige42_local_assistant', updated_at=now()
WHERE agent_name='Charlie Munger';
SQL

echo "Nanbeige4.2 passed conversation_v1 and is active as Charlie's private local fallback."
