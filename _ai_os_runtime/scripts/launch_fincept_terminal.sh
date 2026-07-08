#!/usr/bin/env bash
set -euo pipefail

APP_PATH="/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app"

if [[ ! -d "$APP_PATH" ]]; then
  echo "FinceptTerminal app bundle not found: $APP_PATH" >&2
  exit 1
fi

open "$APP_PATH"
