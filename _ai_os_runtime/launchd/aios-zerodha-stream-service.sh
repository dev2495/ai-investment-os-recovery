#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
export AI_OS_ZERODHA_STREAM_VENV="${AI_OS_ZERODHA_STREAM_VENV:-${HOME}/Library/Application Support/AIOS/venvs/zerodha-stream}"
export AI_OS_ZERODHA_MINUTE_RETENTION_DAYS="${AI_OS_ZERODHA_MINUTE_RETENTION_DAYS:-45}"
export AI_OS_ZERODHA_STREAM_FLUSH_SECONDS="${AI_OS_ZERODHA_STREAM_FLUSH_SECONDS:-2}"
export AI_OS_ZERODHA_STREAM_HEARTBEAT_SECONDS="${AI_OS_ZERODHA_STREAM_HEARTBEAT_SECONDS:-30}"
export AI_OS_ZERODHA_STREAM_RELOAD_SECONDS="${AI_OS_ZERODHA_STREAM_RELOAD_SECONDS:-300}"

protected_env="${AI_OS_IMAC_ENV:-${HOME}/Library/Application Support/AIOS/imac.env}"
if [[ -f "${protected_env}" ]]; then
  set -a
  # This file is mode 600 and written by the AI OS credential helper.
  source "${protected_env}"
  set +a
fi

python_bin="${AI_OS_ZERODHA_STREAM_VENV}/bin/python"
if [[ ! -x "${python_bin}" ]]; then
  printf 'Zerodha stream runtime is unavailable: %s\n' "${python_bin}" >&2
  exit 2
fi

cd "${AI_OS_RUNTIME_ROOT}/scripts"
exec "${python_bin}" -u "${AI_OS_RUNTIME_ROOT}/scripts/stream_zerodha_live.py"
