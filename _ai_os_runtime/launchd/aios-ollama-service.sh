#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="${HOME:-/Users/devarshthakkar}"
export USER="${USER:-devarshthakkar}"
export LOGNAME="${LOGNAME:-devarshthakkar}"
export TMPDIR="${TMPDIR:-/tmp}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/Volumes/Devarsh SSD/OllamaModels}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-4096}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-5m}"
export OLLAMA_NOHISTORY="${OLLAMA_NOHISTORY:-true}"

exec /opt/homebrew/bin/ollama serve
