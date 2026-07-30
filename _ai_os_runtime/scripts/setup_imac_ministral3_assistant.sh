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
OLLAMA_BIN="${AI_OS_OLLAMA_BIN:-/opt/homebrew/bin/ollama}"
DOCKER_BIN="${AI_OS_DOCKER_BIN:-/opt/homebrew/bin/docker}"
MODEL="ministral-3:3b-instruct-2512-q4_K_M"

record_probe_state() {
  local endpoint_status="$1"
  local health_status="$2"
  local stage="$3"
  local message="$4"
  local runtime_version
  runtime_version="$("${OLLAMA_BIN}" --version 2>/dev/null | head -n 1 || printf 'unknown')"

  "${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
    -v endpoint_status="${endpoint_status}" \
    -v health_status="${health_status}" \
    -v probe_stage="${stage}" \
    -v probe_message="${message}" \
    -v runtime_version="${runtime_version}" <<'SQL'
UPDATE agent.model_endpoints
SET status=:'endpoint_status',
    health_status=:'health_status',
    last_checked_at=now(),
    last_error=NULLIF(:'probe_message', ''),
    config=config || jsonb_build_object(
      'last_probe_stage', :'probe_stage',
      'last_probe_at', now(),
      'runtime_version', :'runtime_version'
    ),
    updated_at=now()
WHERE endpoint_key='ollama_ministral3_3b_q4_imac';

INSERT INTO core.connector_health_checks (
    target_kind, target_key, check_name, check_type, status,
    error_message, sample_payload, checked_by
) VALUES (
    'model_endpoint', 'ollama_ministral3_3b_q4_imac',
    'Ministral 3 3B runtime compatibility', 'runtime_probe', :'health_status',
    NULLIF(:'probe_message', ''),
    jsonb_build_object('stage', :'probe_stage', 'model', 'ministral-3:3b-instruct-2512-q4_K_M'),
    'AI Runtime Engineer'
);
SQL
}

[[ -x "${OLLAMA_BIN}" ]] || { echo "Ollama is not installed at ${OLLAMA_BIN}." >&2; exit 2; }
[[ -x "${DOCKER_BIN}" ]] || { echo "Docker is not installed at ${DOCKER_BIN}." >&2; exit 2; }
[[ -f "${RUNTIME_ROOT}/postgres/init/174_ministral3_3b_local_assistant.sql" ]] || {
  echo "Ministral 3 model migration is missing from ${RUNTIME_ROOT}." >&2
  exit 3
}

export OLLAMA_MODELS="${OLLAMA_MODELS:-${DATA_ROOT}/ollama/models}"
export AI_OS_DOCKER_BIN="${DOCKER_BIN}"
mkdir -p "${OLLAMA_MODELS}" "${DATA_ROOT}/evals/local_models"

"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
  < "${RUNTIME_ROOT}/postgres/init/174_ministral3_3b_local_assistant.sql"

record_probe_state "probing" "checking" "manifest_pull" ""

if ! pull_output="$("${OLLAMA_BIN}" pull "${MODEL}" 2>&1)"; then
  printf '%s\n' "${pull_output}" >&2
  pull_message="$(printf '%s' "${pull_output}" | tail -n 8 | tr '\n' ' ' | cut -c1-700)"
  record_probe_state "blocked" "model_unavailable" "manifest_pull" "${pull_message}"
  echo "Ministral 3 remains disabled because the configured Ollama manifest is unavailable." >&2
  exit 4
fi

if ! python3 "${RUNTIME_ROOT}/scripts/run_local_model_evals.py" \
  --model "${MODEL}" \
  --provider ollama \
  --base-url "http://127.0.0.1:11434" \
  --artifact-root "${DATA_ROOT}/evals/local_models" \
  --persist \
  --promote; then
  record_probe_state "disabled" "eval_failed" "conversation_v1" \
    "The exact installed model did not pass the governed conversation_v1 promotion gate."
  echo "Ministral 3 remains disabled because conversation_v1 did not pass." >&2
  exit 5
fi

"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM agent.local_model_registry
    WHERE model_name='ministral-3:3b-instruct-2512-q4_K_M'
      AND eval_suite='conversation_v1'
      AND promotion_status='approved'
      AND coalesce(last_eval_score,0) >= 0.8
  ) THEN
    RAISE EXCEPTION 'Ministral 3 activation refused: exact conversation_v1 promotion evidence is missing';
  END IF;
END $$;

UPDATE agent.model_routes
SET enabled=true,
    updated_at=now()
WHERE route_name='ministral3_3b_local_assistant';

UPDATE agent.model_endpoints
SET status='active',
    health_status='healthy',
    last_checked_at=now(),
    last_error=NULL,
    updated_at=now()
WHERE endpoint_key='ollama_ministral3_3b_q4_imac';

UPDATE agent.agent_model_assignments
SET fallback_route='ministral3_3b_local_assistant',
    updated_at=now()
WHERE agent_name='Charlie Munger';
SQL

echo "Ministral 3 passed conversation_v1 and is active as Charlie's private local fallback."
