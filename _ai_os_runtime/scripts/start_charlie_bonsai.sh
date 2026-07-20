#!/usr/bin/env bash
set -euo pipefail

aios_root="${AI_OS_MACBOOK_ROOT:-${HOME}/Library/Application Support/AIOS}"
demo_root="${AI_OS_BONSAI_DEMO_ROOT:-${aios_root}/challengers/Bonsai-demo}"
server_bin="${AI_OS_BONSAI_SERVER_BIN:-${demo_root}/bin/mac/llama-server}"
model_path="${AI_OS_BONSAI_MODEL_PATH:-${aios_root}/models/bonsai-27b-gguf-f10afb3/Bonsai-27B-Q1_0.gguf}"
host="${AI_OS_LOCAL_MODEL_HOST:-100.75.156.32}"
port="${AI_OS_LOCAL_MODEL_PORT:-11435}"

[[ -x "${server_bin}" ]] || { echo "Pinned PrismML llama-server is not installed" >&2; exit 3; }
[[ -f "${model_path}" ]] || { echo "Pinned Bonsai model is not installed at ${model_path}" >&2; exit 4; }

exec "${server_bin}" \
  --model "${model_path}" \
  --alias default_model \
  --host "${host}" \
  --port "${port}" \
  --ctx-size 8192 \
  --cache-ram 512 \
  --parallel 1 \
  --n-gpu-layers 999 \
  --jinja \
  --reasoning off \
  --reasoning-budget 0 \
  --temp 0.7 \
  --top-p 0.95 \
  --top-k 20 \
  --no-ui \
  --no-slots
