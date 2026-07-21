#!/bin/bash
set -euo pipefail

ENV_FILE="${AI_OS_IMAC_ENV:-${HOME}/Library/Application Support/AIOS/imac.env}"
RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_NODE/ai-investment-os/_ai_os_runtime}"
PYTHON_BIN="${AI_OS_PYTHON_BIN:-/opt/homebrew/bin/python3}"

[[ -f "${ENV_FILE}" ]] || { printf 'Missing protected iMac environment: %s\n' "${ENV_FILE}" >&2; exit 1; }

update_env() {
  local key="$1" value="$2" temp_file
  temp_file="$(mktemp)"
  awk -v target="${key}" 'index($0, target "=") != 1 { print }' "${ENV_FILE}" > "${temp_file}"
  printf '%s=%q\n' "${key}" "${value}" >> "${temp_file}"
  chmod 600 "${temp_file}"
  mv "${temp_file}" "${ENV_FILE}"
}

printf 'Zerodha API key: '
IFS= read -r api_key
printf 'Zerodha API secret (input hidden): '
IFS= read -r -s api_secret
printf '\n'
[[ -n "${api_key}" && -n "${api_secret}" ]] || { printf 'API key and secret are required.\n' >&2; exit 1; }

update_env AI_OS_ZERODHA_API_KEY "${api_key}"
update_env AI_OS_ZERODHA_API_SECRET "${api_secret}"
export AI_OS_ZERODHA_API_KEY="${api_key}"
export AI_OS_ZERODHA_API_SECRET="${api_secret}"

login_url="$("${PYTHON_BIN}" "${RUNTIME_ROOT}/scripts/sync_zerodha_read_only.py" --login-url | "${PYTHON_BIN}" -c 'import json,sys; print(json.load(sys.stdin)["login_url"])')"
printf 'Opening the official Zerodha login on the iMac. Complete login in Safari.\n'
/usr/bin/open "${login_url}"
printf 'After redirect, paste only the request_token value here (input hidden): '
IFS= read -r -s request_token
printf '\n'
[[ -n "${request_token}" ]] || { printf 'request_token is required.\n' >&2; exit 1; }

"${PYTHON_BIN}" "${RUNTIME_ROOT}/scripts/sync_zerodha_read_only.py" --exchange-request-token "${request_token}"
"${PYTHON_BIN}" "${RUNTIME_ROOT}/scripts/sync_zerodha_market_data.py" --modes instruments --exchanges ALL
"${PYTHON_BIN}" "${RUNTIME_ROOT}/scripts/sync_zerodha_read_only.py" --datasets holdings positions orders trades funds
"${PYTHON_BIN}" "${RUNTIME_ROOT}/scripts/sync_zerodha_market_data.py" --modes quotes options --underlyings NIFTY BANKNIFTY

pkill -f "${RUNTIME_ROOT}/api/ai_os_api_server.py" 2>/dev/null || true
printf 'Zerodha GET-only account and market data are connected. Broker writes remain disabled.\n'
