#!/usr/bin/env bash
set -euo pipefail

aios_root="${AI_OS_MACBOOK_ROOT:-${HOME}/Library/Application Support/AIOS}"
venv="${AI_OS_MLX_VENV:-${aios_root}/venvs/mlx}"
model_path="${AI_OS_MLX_MODEL_PATH:-${aios_root}/models/qwen3-8b-mlx-4bit-383413e}"
host="${AI_OS_MLX_HOST:-100.75.156.32}"
port="${AI_OS_MLX_PORT:-11435}"

[[ -x "${venv}/bin/mlx_lm.server" ]] || { echo "Pinned MLX-LM runtime is not installed" >&2; exit 3; }
[[ -f "${model_path}/config.json" ]] || { echo "Pinned Charlie model is not installed at ${model_path}" >&2; exit 4; }

export HF_HOME="${AI_OS_HF_HOME:-${aios_root}/huggingface}"
export HF_HUB_CACHE="${HF_HOME}/hub"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
export TOKENIZERS_PARALLELISM=false
mkdir -p "${HF_HUB_CACHE}" "${TRANSFORMERS_CACHE}"

exec "${venv}/bin/mlx_lm.server" \
  --model "${model_path}" \
  --host "${host}" \
  --port "${port}" \
  --decode-concurrency 1 \
  --prompt-concurrency 1 \
  --prompt-cache-size 2 \
  --prompt-cache-bytes 536870912 \
  --prefill-step-size 1024 \
  --max-tokens 900 \
  --temp 0.7 \
  --top-p 0.8 \
  --top-k 20 \
  --min-p 0.0 \
  --chat-template-args '{"enable_thinking":false}'
