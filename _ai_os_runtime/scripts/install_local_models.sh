#!/usr/bin/env bash
set -euo pipefail

profile="macbook"
include_specialists=0
ollama_url="${AI_OS_OLLAMA_URL:-http://127.0.0.1:11434}"
model_root="${AI_OS_OLLAMA_MODELS:-/Volumes/Devarsh SSD/AI OS Data/ollama/models}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      profile="$2"
      shift 2
      ;;
    --include-specialists)
      include_specialists=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "${profile}" != "macbook" && "${profile}" != "imac" ]]; then
  echo "--profile must be macbook or imac" >&2
  exit 2
fi

if [[ "${model_root}" != /Volumes/* && "${AI_OS_ALLOW_INTERNAL_MODEL_STORE:-0}" != "1" ]]; then
  echo "Refusing to install model weights outside external storage: ${model_root}" >&2
  exit 3
fi

if ! curl --max-time 3 -fsS "${ollama_url}/api/version" >/dev/null; then
  echo "Ollama is not reachable at ${ollama_url}. Start the governed Ollama service first." >&2
  exit 4
fi

mkdir -p "${model_root}"
export OLLAMA_MODELS="${model_root}"

models=("qwen3-embedding:0.6b")
if [[ "${profile}" == "macbook" ]]; then
  models+=("qwen3.5:9b")
fi
if [[ "${include_specialists}" == "1" && "${profile}" == "macbook" ]]; then
  models+=("gemma4:e2b")
fi

for model in "${models[@]}"; do
  echo "Installing ${model} into ${model_root}"
  /opt/homebrew/bin/ollama pull "${model}"
done

echo "Installed governed model inventory:"
/opt/homebrew/bin/ollama list
