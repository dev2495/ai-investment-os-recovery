#!/usr/bin/env bash
set -euo pipefail

app_bundle="${AI_OS_TRADINGVIEW_APP_BUNDLE:-/Applications/TradingView.app}"
cdp_host="${AI_OS_TRADINGVIEW_CDP_HOST:-127.0.0.1}"
cdp_port="${AI_OS_TRADINGVIEW_CDP_PORT:-9222}"
status_url="http://${cdp_host}:${cdp_port}/json/version"

if [[ ! -d "${app_bundle}" ]]; then
  printf 'TradingView app bundle not found: %s\n' "${app_bundle}" >&2
  exit 1
fi

existing_pids="$(pgrep -x TradingView || true)"
if [[ -n "${existing_pids}" ]]; then
  # Do not force-kill: preserve the normal TradingView profile/layout shutdown path.
  kill -TERM ${existing_pids}
  for _ in {1..15}; do
    if ! pgrep -x TradingView >/dev/null; then
      break
    fi
    sleep 1
  done
  if pgrep -x TradingView >/dev/null; then
    printf 'TradingView did not close gracefully; aborting CDP relaunch. Close it manually, then rerun this script.\n' >&2
    exit 1
  fi
fi

# Launch Services keeps the desktop app alive after this script exits. `-n` matters
# only after a clean quit, and guarantees launch arguments reach the fresh instance.
open -na "${app_bundle}" --args \
  --remote-debugging-address="${cdp_host}" \
  --remote-debugging-port="${cdp_port}"

for _ in {1..20}; do
  if curl -fs --max-time 1 "${status_url}"; then
    printf '\nTradingView CDP is ready at %s\n' "${status_url}"
    exit 0
  fi
  sleep 1
done

printf 'TradingView launched but CDP did not answer at %s. Confirm the app stayed open, then rerun this script.\n' "${status_url}" >&2
exit 1
