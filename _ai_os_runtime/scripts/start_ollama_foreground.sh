#!/usr/bin/env bash
set -euo pipefail

cd "/Users/devarshthakkar"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="${HOME:-/Users/devarshthakkar}"
export USER="${USER:-devarshthakkar}"
export LOGNAME="${LOGNAME:-devarshthakkar}"
export TMPDIR="${TMPDIR:-/tmp}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${AI_OS_OLLAMA_MODELS:-/Volumes/Devarsh SSD/AI OS Data/ollama/models}"
export OLLAMA_NOHISTORY="${OLLAMA_NOHISTORY:-true}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-8192}"
export OLLAMA_NO_CLOUD="${OLLAMA_NO_CLOUD:-1}"

exec /opt/homebrew/bin/ollama serve
