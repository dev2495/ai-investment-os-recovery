#!/usr/bin/env bash
set -euo pipefail

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/Volumes/Devarsh SSD/AI OS Data/caches/playwright}"
exec npx playwright test "$@"
