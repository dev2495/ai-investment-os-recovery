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
MODEL="nanbeige/nanbeige4.2:3b-Q4_K_M"

[[ -x "${OLLAMA_BIN}" ]] || { echo "Ollama is not installed at ${OLLAMA_BIN}." >&2; exit 2; }
[[ -x "${DOCKER_BIN}" ]] || { echo "Docker is not installed at ${DOCKER_BIN}." >&2; exit 2; }
[[ -f "${RUNTIME_ROOT}/postgres/init/173_nanbeige42_local_assistant.sql" ]] || {
  echo "Nanbeige4.2 model migration is missing from ${RUNTIME_ROOT}." >&2
  exit 3
}

export OLLAMA_MODELS="${OLLAMA_MODELS:-${DATA_ROOT}/ollama/models}"
export AI_OS_DOCKER_BIN="${DOCKER_BIN}"
mkdir -p "${OLLAMA_MODELS}" "${DATA_ROOT}/evals/local_models"

"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
  < "${RUNTIME_ROOT}/postgres/init/173_nanbeige42_local_assistant.sql"

"${OLLAMA_BIN}" pull "${MODEL}"

python3 "${RUNTIME_ROOT}/scripts/run_local_model_evals.py" \
  --model "${MODEL}" \
  --provider ollama \
  --base-url "http://127.0.0.1:11434" \
  --artifact-root "${DATA_ROOT}/evals/local_models" \
  --persist \
  --promote

"${DOCKER_BIN}" exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM agent.local_model_registry
    WHERE model_name='nanbeige/nanbeige4.2:3b-Q4_K_M'
      AND eval_suite='conversation_v1'
      AND promotion_status='approved'
      AND coalesce(last_eval_score,0) >= 0.8
  ) THEN
    RAISE EXCEPTION 'Nanbeige4.2 activation refused: exact conversation_v1 promotion evidence is missing';
  END IF;
END $$;

UPDATE agent.model_routes
SET enabled=true,
    updated_at=now()
WHERE route_name='nanbeige42_local_assistant';

UPDATE agent.model_endpoints
SET status='active',
    health_status='healthy',
    last_checked_at=now(),
    last_error=NULL,
    updated_at=now()
WHERE endpoint_key='ollama_nanbeige42_3b_q4_imac';

UPDATE agent.agent_model_assignments
SET fallback_route='nanbeige42_local_assistant',
    updated_at=now()
WHERE agent_name='Charlie Munger';
SQL

echo "Nanbeige4.2 passed conversation_v1 and is active as Charlie's private local fallback."
