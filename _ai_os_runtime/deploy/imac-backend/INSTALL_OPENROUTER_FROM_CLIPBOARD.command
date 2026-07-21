#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/SET_OPENROUTER_KEY_FROM_MACBOOK.command" --clipboard
printf '\nYou can close this window.\n'
