#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os/_ai_os_runtime}"
export AI_OS_TRADINGVIEW_BROWSER_PORT="${AI_OS_TRADINGVIEW_BROWSER_PORT:-9333}"
export AI_OS_TRADINGVIEW_BROWSER_PROFILE="${AI_OS_TRADINGVIEW_BROWSER_PROFILE:-/Volumes/Devarsh SSD/AI OS Data/browser-profiles/tradingview-cft}"

"${AI_OS_RUNTIME_ROOT}/scripts/verify_external_storage.sh" >/dev/null
exec node "${AI_OS_RUNTIME_ROOT}/scripts/launch_tradingview_browser.mjs" \
  --port "${AI_OS_TRADINGVIEW_BROWSER_PORT}" \
  --profile-dir "${AI_OS_TRADINGVIEW_BROWSER_PROFILE}"
