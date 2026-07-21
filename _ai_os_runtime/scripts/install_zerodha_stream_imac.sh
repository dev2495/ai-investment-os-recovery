#!/usr/bin/env bash
set -euo pipefail

runtime_root="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_NODE/ai-investment-os/_ai_os_runtime}"
venv_root="${AI_OS_ZERODHA_STREAM_VENV:-${HOME}/Library/Application Support/AIOS/venvs/zerodha-stream}"
pip_cache="${AI_OS_PIP_CACHE_DIR:-/Volumes/Devarsh SSD/AI OS Data/caches/pip}"
plist_source="${runtime_root}/launchd/com.devarsh.aios.zerodha-stream.plist"
plist_target="${HOME}/Library/LaunchAgents/com.devarsh.aios.zerodha-stream.plist"
launch_domain="gui/$(id -u)"

[[ -f "${runtime_root}/requirements-zerodha-stream.txt" ]] || {
  printf 'Missing stream requirements in %s\n' "${runtime_root}" >&2
  exit 1
}
[[ -f "${plist_source}" ]] || {
  printf 'Missing LaunchAgent plist: %s\n' "${plist_source}" >&2
  exit 1
}

mkdir -p "${venv_root%/*}" "${pip_cache}" "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs/AIOS"
if [[ ! -x "${venv_root}/bin/python" ]]; then
  /opt/homebrew/bin/python3.11 -m venv "${venv_root}"
fi
PIP_CACHE_DIR="${pip_cache}" "${venv_root}/bin/python" -m pip install --upgrade pip
PIP_CACHE_DIR="${pip_cache}" "${venv_root}/bin/python" -m pip install -r "${runtime_root}/requirements-zerodha-stream.txt"

# Zerodha's current client metadata pins autobahn 19.11.2, which is affected by
# PYSEC-2020-25. KiteTicker is verified against the fixed, API-compatible build.
PIP_CACHE_DIR="${pip_cache}" "${venv_root}/bin/python" -m pip install --no-deps --upgrade "autobahn==20.12.3"
PIP_CACHE_DIR="${pip_cache}" "${venv_root}/bin/python" -m pip install --upgrade "setuptools>=83.0.0" pip-audit
"${venv_root}/bin/python" -m pip_audit --local
"${venv_root}/bin/python" -c 'import autobahn; assert autobahn.__version__ == "20.12.3", autobahn.__version__'

cp -f "${plist_source}" "${plist_target}"
chmod 644 "${plist_target}"
chmod +x "${runtime_root}/launchd/aios-zerodha-stream-service.sh" "${runtime_root}/scripts/stream_zerodha_live.py"

launchctl bootout "${launch_domain}" "${plist_target}" 2>/dev/null || true
launchctl bootstrap "${launch_domain}" "${plist_target}"
printf 'Installed Zerodha read-only stream. Logs: %s\n' "${HOME}/Library/Logs/AIOS/zerodha_stream.launchd.log"
