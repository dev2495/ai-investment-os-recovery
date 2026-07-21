#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
prompt='display dialog "Paste your OpenRouter API key. It will be sent directly to the iMac and will not be stored on this MacBook." default answer "" with title "AI Investment OS Model Setup" with hidden answer buttons {"Cancel", "Install"} default button "Install"'

if ! key="$(osascript -e "text returned of (${prompt})" 2>/dev/null)"; then
  exit 0
fi

if [[ ! "${key}" =~ ^sk-or-v1-[A-Za-z0-9_-]{20,}$ ]]; then
  osascript -e 'display alert "Invalid OpenRouter key" message "The value must start with sk-or-v1-. Nothing was installed." as critical'
  exit 3
fi

log_file="$(mktemp)"
trap 'rm -f "${log_file}"' EXIT
if printf '%s\n' "${key}" | "${SCRIPT_DIR}/SET_OPENROUTER_KEY_FROM_MACBOOK.command" --stdin >"${log_file}" 2>&1; then
  unset key
  osascript -e 'display alert "OpenRouter is ready" message "The key is installed on the iMac and the AI OS runtime restarted. Charlie can now use Fast, Deep, and Review routes."'
  exit 0
fi

unset key
message="$(tail -8 "${log_file}" | tr '\n' ' ' | sed 's/"/\\"/g')"
osascript -e "display alert \"Setup failed\" message \"${message}\" as critical"
exit 1
