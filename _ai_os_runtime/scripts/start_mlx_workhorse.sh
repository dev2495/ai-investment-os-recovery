#!/usr/bin/env bash
set -euo pipefail

aios_root="${AI_OS_MACBOOK_ROOT:-${HOME}/Library/Application Support/AIOS}"
venv="${AI_OS_MLX_VLM_VENV:-${aios_root}/venvs/mlx-vlm}"
model_path="${AI_OS_MLX_MODEL_PATH:-${aios_root}/models/qwen3.5-9b-4bit-8b2b98c}"
host="${AI_OS_MLX_HOST:-100.75.156.32}"
port="${AI_OS_MLX_PORT:-11436}"

[[ -x "${venv}/bin/mlx_vlm.server" ]] || { echo "Pinned MLX-VLM runtime is not installed" >&2; exit 3; }
[[ -f "${model_path}/config.json" ]] || { echo "Pinned Qwen3.5 model is not installed at ${model_path}" >&2; exit 4; }

export HF_HOME="${AI_OS_HF_HOME:-${aios_root}/huggingface}"
export HF_HUB_CACHE="${HF_HOME}/hub"
export HF_XET_CACHE="${HF_HOME}/xet"
export TRANSFORMERS_CACHE="${HF_HOME}/transformers"
export TOKENIZERS_PARALLELISM=false
export APC_ENABLED=1
export APC_NUM_BLOCKS="${AI_OS_APC_NUM_BLOCKS:-512}"
mkdir -p "${HF_HUB_CACHE}" "${HF_XET_CACHE}" "${TRANSFORMERS_CACHE}"

server_args=(
  --model "${model_path}"
  --host "${host}"
  --port "${port}"
  --vision-cache-size 0
  --prefill-step-size 1024
  --max-tokens "${AI_OS_MLX_MAX_TOKENS:-1400}"
  --max-kv-size "${AI_OS_MLX_MAX_KV_SIZE:-8192}"
  --log-level INFO
)

# Qwen3.5 produced corrupt output with KV-cache quantization in qualification.
# Keep it opt-in until a pinned runtime/model combination passes the same gates.
if [[ "${AI_OS_MLX_ENABLE_KV_QUANT:-0}" == "1" ]]; then
  server_args+=(--kv-bits 8 --kv-group-size 64 --quantized-kv-start 2048)
fi

exec "${venv}/bin/mlx_vlm.server" "${server_args[@]}"
