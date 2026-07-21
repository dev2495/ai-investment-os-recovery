#!/bin/bash
set -euo pipefail

IMAC_HOST="${AI_OS_IMAC_SSH_HOST:-devarshthakkar@100.83.144.69}"
SSH_KEY="${AI_OS_IMAC_SSH_KEY:-${HOME}/.ssh/aios_imac_ed25519}"
REMOTE_ENV='${HOME}/Library/Application Support/AIOS/imac.env'

usage() {
  cat <<'EOF'
Usage: SET_OPENROUTER_KEY_FROM_MACBOOK.command [--clipboard|--stdin|--check]

Run without arguments for a hidden prompt. Use --clipboard after copying the
OpenRouter key from Notes. The key is sent directly over SSH and is never
written to this MacBook, Git, Obsidian, or shell history.
EOF
}

ssh_args=(-i "${SSH_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=15 "${IMAC_HOST}")

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--check" ]]; then
  ssh "${ssh_args[@]}" "grep -Eq '^AI_OS_OPENROUTER_API_KEY=.+$' \"${REMOTE_ENV}\""
  echo "OpenRouter key is configured on the iMac (value not displayed)."
  exit 0
fi

if [[ "${1:-}" == "--clipboard" ]]; then
  command -v pbpaste >/dev/null 2>&1 || { echo "pbpaste is unavailable." >&2; exit 1; }
  key="$(pbpaste | tr -d '\r\n')"
elif [[ "${1:-}" == "--stdin" ]]; then
  IFS= read -r key
elif [[ -z "${1:-}" ]]; then
  printf 'Paste the OpenRouter key (input hidden), then press Return: '
  IFS= read -r -s key
  printf '\n'
else
  usage >&2
  exit 2
fi

if [[ ! "${key}" =~ ^sk-or-v1-[A-Za-z0-9_-]{20,}$ ]]; then
  echo "The value does not look like an OpenRouter API key." >&2
  exit 3
fi

printf '%s\n' "${key}" | ssh "${ssh_args[@]}" \
  'bash -lc '\''source "$HOME/Library/Application Support/AIOS/imac.env" && exec "$AI_OS_REPO_ROOT/_ai_os_runtime/deploy/imac-backend/bin/install-openrouter-key"'\'''

unset key
echo "OpenRouter key installed. The iMac runtime was restarted without displaying the secret."
