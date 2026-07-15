#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os/_ai_os_runtime}"
export AI_OS_VAULT_ROOT="${AI_OS_VAULT_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
export AI_OS_CRITICAL_BACKUP_ROOT="${AI_OS_CRITICAL_BACKUP_ROOT:-${AI_OS_SSD_ROOT:-/Volumes/Devarsh SSD}/AI OS Data/backups/critical}"

exec "${AI_OS_RUNTIME_ROOT}/scripts/critical_state_backup.sh"
