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
MODEL="granite4:3b"

[[ -x "${OLLAMA_BIN}" ]] || { echo "Ollama is not installed at ${OLLAMA_BIN}." >&2; exit 2; }
[[ -f "${RUNTIME_ROOT}/postgres/init/160_granite4_imac_basic_assistant.sql" ]] || {
  echo "Granite model migration is missing from ${RUNTIME_ROOT}." >&2
  exit 3
}

export OLLAMA_MODELS="${OLLAMA_MODELS:-${DATA_ROOT}/ollama/models}"
mkdir -p "${OLLAMA_MODELS}" "${DATA_ROOT}/evals/local_models"

docker exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 \
  < "${RUNTIME_ROOT}/postgres/init/160_granite4_imac_basic_assistant.sql"

"${OLLAMA_BIN}" pull "${MODEL}"

if ! python3 "${RUNTIME_ROOT}/scripts/run_local_model_evals.py" \
  --model "${MODEL}" \
  --provider ollama \
  --base-url "http://127.0.0.1:11434" \
  --artifact-root "${DATA_ROOT}/evals/local_models" \
  --persist \
  --promote; then
  docker exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 <<'SQL'
UPDATE agent.model_endpoints
SET status='disabled', health_status='eval_failed', last_checked_at=now(),
    last_error='The exact installed model did not pass the governed conversation_v1 promotion gate.',
    updated_at=now()
WHERE endpoint_key='ollama_granite4_3b_imac';
SQL
  echo "Granite 4 remains disabled because conversation_v1 did not pass." >&2
  exit 1
fi

docker exec -i ai_os_postgres psql -U ai_os -d ai_os -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM agent.local_model_registry
    WHERE model_name='granite4:3b'
      AND eval_suite='conversation_v1'
      AND promotion_status='approved'
      AND coalesce(last_eval_score, 0) >= 0.8
  ) THEN
    RAISE EXCEPTION 'Granite activation refused: conversation_v1 promotion evidence is missing';
  END IF;
END $$;

UPDATE agent.model_endpoints
SET status='active', health_status='healthy', last_checked_at=now(),
    last_error=NULL, updated_at=now()
WHERE endpoint_key='ollama_granite4_3b_imac';

UPDATE agent.agent_model_assignments
SET fallback_route='imac_basic_assistant', updated_at=now()
WHERE agent_name='Charlie Munger';
SQL

echo "Granite 4 iMac assistant is evaluated, approved, and active as Charlie's private fallback."
