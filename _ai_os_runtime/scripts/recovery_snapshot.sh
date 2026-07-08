#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="${AI_OS_SOURCE_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
BACKUP_ROOT="${AI_OS_BACKUP_ROOT:-${HOME}/AI_OS_RECOVERY_BACKUP_20260708/Obsidian memory }"

if [[ ! -d "${SOURCE_ROOT}/_ai_os_runtime" ]]; then
  echo "ERROR: AI OS source is not mounted or incomplete: ${SOURCE_ROOT}" >&2
  exit 1
fi

if [[ "${SOURCE_ROOT}" != /Volumes/Devarsh\ SSD/* ]]; then
  echo "ERROR: refusing snapshot from a non-SSD source: ${SOURCE_ROOT}" >&2
  exit 2
fi

mkdir -p "${BACKUP_ROOT}"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.DS_Store' \
  --exclude '_ai_os_runtime/logs/' \
  --exclude '_ai_os_runtime/run/' \
  --exclude '_ai_os_runtime/docker_data/' \
  --exclude '_ai_os_runtime/browser_profiles/' \
  --exclude '_ai_os_runtime/ai-office-ui/node_modules/' \
  --exclude '_ai_os_runtime/ai-office-ui/dist/' \
  --exclude '_ai_os_runtime/external_components/**/.git/' \
  --exclude '_ai_os_runtime/external_components/**/node_modules/' \
  --exclude '_ai_os_runtime/external_components/FinceptTerminal/.qt/' \
  --exclude '_ai_os_runtime/external_components/FinceptTerminal/.aqt-venv/' \
  --exclude '_ai_os_runtime/external_components/FinceptTerminal/.aqt-cache/' \
  --exclude '_ai_os_runtime/external_components/FinceptTerminal/.aqt-tmp/' \
  --exclude '_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/' \
  "${SOURCE_ROOT}/" "${BACKUP_ROOT}/"

echo "Recovery snapshot refreshed:"
echo "  source: ${SOURCE_ROOT}"
echo "  backup: ${BACKUP_ROOT}"
