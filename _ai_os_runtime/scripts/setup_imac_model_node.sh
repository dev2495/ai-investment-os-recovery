#!/usr/bin/env bash
set -euo pipefail

model_root="${AI_OS_IMAC_MODEL_ROOT:-/Volumes/AI OS iMac/ollama/models}"
ollama_bin="${AI_OS_OLLAMA_BIN:-/opt/homebrew/bin/ollama}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This package is for an Apple Silicon iMac." >&2
  exit 2
fi
if [[ ! -x "${ollama_bin}" ]]; then
  echo "Ollama is missing at ${ollama_bin}. Install Ollama, then rerun." >&2
  exit 3
fi
if [[ "${model_root}" != /Volumes/* && "${AI_OS_ALLOW_INTERNAL_MODEL_STORE:-0}" != "1" ]]; then
  echo "Attach a dedicated external SSD named 'AI OS iMac', or explicitly allow internal storage." >&2
  exit 4
fi

mkdir -p "${model_root}"
export OLLAMA_MODELS="${model_root}"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_CONTEXT_LENGTH="8192"
export OLLAMA_NUM_PARALLEL="1"
export OLLAMA_KEEP_ALIVE="5m"
export OLLAMA_NOHISTORY="true"
export OLLAMA_NO_CLOUD="1"

if ! curl --max-time 2 -fsS "http://127.0.0.1:11434/api/version" >/dev/null; then
  "${ollama_bin}" serve > /tmp/aios-imac-ollama-bootstrap.log 2>&1 &
  ollama_pid=$!
  trap 'kill "${ollama_pid}" 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    curl --max-time 2 -fsS "http://127.0.0.1:11434/api/version" >/dev/null && break
    sleep 0.5
  done
fi

curl --max-time 2 -fsS "http://127.0.0.1:11434/api/version" >/dev/null
"${ollama_bin}" pull "qwen3-embedding:0.6b"

echo "iMac deterministic worker installed. Run the retrieval evaluation before enabling scheduled workers."
"${ollama_bin}" list
