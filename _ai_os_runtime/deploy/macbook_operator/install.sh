#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${HOME}/Library/Application Support/AIOS/operator-gateway"
LOG_ROOT="${HOME}/Library/Logs/AIOS"
PLIST="${HOME}/Library/LaunchAgents/com.devarsh.aios.api.plist"
UPSTREAM="${AI_OS_UPSTREAM_API:-https://devarshs-imac.tail8dd383.ts.net:8443}"
PYTHON_BIN="$(command -v python3)"

mkdir -p "${INSTALL_ROOT}" "${LOG_ROOT}" "${HOME}/Library/LaunchAgents"
install -m 700 "${SCRIPT_DIR}/macbook_operator_gateway.py" "${INSTALL_ROOT}/macbook_operator_gateway.py"

sed \
  -e "s|__PYTHON__|${PYTHON_BIN}|g" \
  -e "s|__GATEWAY__|${INSTALL_ROOT}/macbook_operator_gateway.py|g" \
  -e "s|__UPSTREAM__|${UPSTREAM}|g" \
  -e "s|__LOG_ROOT__|${LOG_ROOT}|g" \
  "${SCRIPT_DIR}/templates/com.devarsh.aios.api.plist.in" > "${PLIST}.new"
plutil -lint "${PLIST}.new"
mv "${PLIST}.new" "${PLIST}"

launchctl bootout "gui/$(id -u)/com.devarsh.aios.api" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST}"
launchctl kickstart -k "gui/$(id -u)/com.devarsh.aios.api"

for _ in {1..30}; do
  if curl --max-time 3 -fsS http://127.0.0.1:8765/api/node/health >/dev/null; then
    echo "MacBook operator gateway is ready at http://127.0.0.1:8765"
    exit 0
  fi
  sleep 1
done

echo "MacBook operator gateway did not become healthy" >&2
exit 1
