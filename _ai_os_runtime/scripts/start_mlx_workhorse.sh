#!/usr/bin/env bash
set -euo pipefail

mlx_root="${AI_OS_MLX_ROOT:-/Volumes/Devarsh SSD/AI OS Data/mlx}"
venv="${AI_OS_MLX_VENV:-/Volumes/Devarsh SSD/AI OS Data/venvs/mlx}"
model_path="${AI_OS_MLX_MODEL_PATH:-${mlx_root}/models/qwen3.5-9b-4bit-20353927}"
port="${AI_OS_MLX_PORT:-11435}"

[[ "${mlx_root}" == /Volumes/* ]] || { echo "MLX runtime must be on an external volume" >&2; exit 2; }
[[ -x "${venv}/bin/mlx_lm.server" ]] || { echo "Pinned MLX-LM runtime is not installed" >&2; exit 3; }
[[ -f "${model_path}/config.json" ]] || { echo "Pinned MLX model is not installed at ${model_path}" >&2; exit 4; }

export HF_HOME="${AI_OS_HF_HOME:-/Volumes/Devarsh SSD/AI OS Data/huggingface}"
export HF_HUB_CACHE="${HF_HOME}/hub"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
export TOKENIZERS_PARALLELISM=false
mkdir -p "${HF_HUB_CACHE}" "${TRANSFORMERS_CACHE}"

exec "${venv}/bin/mlx_lm.server" \
  --model "${model_path}" \
  --host 127.0.0.1 \
  --port "${port}" \
  --decode-concurrency 1 \
  --prompt-concurrency 1 \
  --prompt-cache-size 2 \
  --prompt-cache-bytes 1073741824 \
  --prefill-step-size 1024 \
  --max-tokens 1400 \
  --chat-template-args '{"enable_thinking":false}'
