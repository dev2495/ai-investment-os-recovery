#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_ROOT="${RUNTIME_ROOT}/backup-helper"
APP_ROOT="${HOME}/Applications/AI OS Backup.app"
CONTENTS_ROOT="${APP_ROOT}/Contents"
MACOS_ROOT="${CONTENTS_ROOT}/MacOS"
LAUNCHD_DOMAIN="gui/$(id -u)"
LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/com.devarsh.aios.critical-backup.plist"
REPORT_LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/com.devarsh.aios.scheduled-reports.plist"

mkdir -p "${MACOS_ROOT}" "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs/AIOS"
xcrun swiftc -O "${SOURCE_ROOT}/AIOSBackupHelper.swift" -o "${MACOS_ROOT}/AIOSBackupHelper"
cp -f "${SOURCE_ROOT}/Info.plist" "${CONTENTS_ROOT}/Info.plist"
codesign --force --sign - --identifier com.devarsh.aios.backup-helper "${APP_ROOT}"
cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.critical-backup.plist" "${LAUNCHD_PLIST}"
cp -f "${RUNTIME_ROOT}/launchd/com.devarsh.aios.scheduled-reports.plist" "${REPORT_LAUNCHD_PLIST}"

launchctl bootout "${LAUNCHD_DOMAIN}" "${LAUNCHD_PLIST}" 2>/dev/null || true
launchctl bootout "${LAUNCHD_DOMAIN}" "${REPORT_LAUNCHD_PLIST}" 2>/dev/null || true
launchctl bootstrap "${LAUNCHD_DOMAIN}" "${LAUNCHD_PLIST}"
launchctl bootstrap "${LAUNCHD_DOMAIN}" "${REPORT_LAUNCHD_PLIST}"

codesign --verify --deep --strict "${APP_ROOT}"
echo "Installed AI OS Backup helper: ${APP_ROOT}"
echo "Registered schedule: daily at 03:20 local time"
echo "Registered report scheduler: daily at 08:35 local time"
