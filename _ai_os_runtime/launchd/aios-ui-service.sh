#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "/Users/devarshthakkar/Library/Application Support/AIOS/ui-dist"
exec python3 -m http.server "${AI_OS_UI_PORT:-5177}" --bind 127.0.0.1
