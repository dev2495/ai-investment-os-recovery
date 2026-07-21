#!/usr/bin/env bash
set -euo pipefail

runtime_root="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_NODE/ai-investment-os/_ai_os_runtime}"
env_file="${AI_OS_IMAC_ENV:-${HOME}/Library/Application Support/AIOS/imac.env}"
[[ -f "${env_file}" ]] || { printf 'Missing protected iMac environment: %s\n' "${env_file}" >&2; exit 1; }

set -a
source "${env_file}"
set +a
[[ -n "${AI_OS_ZERODHA_API_KEY:-}" && -n "${AI_OS_ZERODHA_API_SECRET:-}" ]] || {
  printf 'Zerodha API key and secret are not configured. Run configure_zerodha_imac.sh once.\n' >&2
  exit 1
}

login_url="https://kite.zerodha.com/connect/login?v=3&api_key=${AI_OS_ZERODHA_API_KEY}"
printf 'Opening Zerodha. The configured redirect should return to AI OS and exchange the token automatically.\n'
/usr/bin/open "${login_url}"
printf 'Callback URL required in the Zerodha developer app:\n'
printf 'https://devarshs-imac.tail8dd383.ts.net:8443/api/zerodha/auth/callback\n'
