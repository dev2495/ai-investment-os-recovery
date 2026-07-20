#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_ROOT}/../../.." && pwd)"
SSD_ROOT="${AI_OS_SSD_ROOT:-/Volumes/Devarsh SSD}"
PACKAGE_ROOT="${AI_OS_IMAC_PACKAGE_ROOT:-${SSD_ROOT}/AI OS Data/imac-backend-package}"
STAGING_ROOT="${PACKAGE_ROOT}.staging.$$"
SSH_KEY="${HOME}/.ssh/aios_imac_ed25519"

[[ -d "${SSD_ROOT}" ]] || { echo "SSD is not mounted: ${SSD_ROOT}" >&2; exit 1; }
[[ -d "${SSD_ROOT}/Obsidian memory /ai memory" ]] || { echo "Recovered vault is missing" >&2; exit 1; }

if [[ ! -f "${SSH_KEY}" ]]; then
  mkdir -p "${HOME}/.ssh"
  chmod 700 "${HOME}/.ssh"
  ssh-keygen -q -t ed25519 -N '' -C 'ai-os-macbook-to-imac' -f "${SSH_KEY}"
fi

rm -rf "${STAGING_ROOT}"
mkdir -p "${STAGING_ROOT}/source"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '_ai_os_runtime/.env' \
  --exclude '**/node_modules/' \
  --exclude '**/__pycache__/' \
  --exclude '_ai_os_runtime/logs/' \
  --exclude '_ai_os_runtime/run/' \
  --exclude '_ai_os_runtime/artifacts/' \
  --exclude '_ai_os_runtime/imports/quarantine/' \
  "${REPO_ROOT}/" "${STAGING_ROOT}/source/"
git -C "${REPO_ROOT}" rev-parse HEAD > "${STAGING_ROOT}/source/DEPLOYED_COMMIT"

cp "${DEPLOY_ROOT}/INSTALL_ON_IMAC.command" "${STAGING_ROOT}/INSTALL_ON_IMAC.command"
cp "${SSH_KEY}.pub" "${STAGING_ROOT}/MACBOOK_SSH_PUBLIC_KEY.txt"
git -C "${REPO_ROOT}" bundle create "${STAGING_ROOT}/ai-investment-os.bundle" --all
git -C "${REPO_ROOT}" bundle verify "${STAGING_ROOT}/ai-investment-os.bundle" > "${STAGING_ROOT}/bundle-verify.txt" 2>&1

cat > "${STAGING_ROOT}/package.json" <<EOF
{
  "created_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "source_commit": "$(git -C "${REPO_ROOT}" rev-parse HEAD)",
  "source_branch": "$(git -C "${REPO_ROOT}" branch --show-current)",
  "source_host": "$(hostname)",
  "target_host": "Devarshs-iMac.local",
  "target_role": "imac_backend",
  "ssd_root": "/Volumes/Devarsh SSD"
}
EOF

cat > "${STAGING_ROOT}/IMAC_CONNECTION_AFTER_INSTALL.json" <<EOF
{
  "lan_host": "Devarshs-iMac.local",
  "ssh_key_on_macbook": "${SSH_KEY}",
  "ssh_user": "written by the iMac installer",
  "tailscale_ui": "written by the iMac installer",
  "tailscale_api": "written by the iMac installer"
}
EOF

chmod +x "${STAGING_ROOT}/INSTALL_ON_IMAC.command"
find "${STAGING_ROOT}/source/_ai_os_runtime/deploy/imac-backend/bin" -type f -exec chmod +x {} \;
chmod +x "${STAGING_ROOT}/source/_ai_os_runtime/deploy/imac-backend/INSTALL_ON_IMAC.command"

(
  cd "${STAGING_ROOT}"
  find source INSTALL_ON_IMAC.command MACBOOK_SSH_PUBLIC_KEY.txt ai-investment-os.bundle bundle-verify.txt package.json IMAC_CONNECTION_AFTER_INSTALL.json \
    -type f -print0 | sort -z | xargs -0 shasum -a 256
) > "${STAGING_ROOT}/SHA256SUMS"
(cd "${STAGING_ROOT}" && shasum -a 256 -c SHA256SUMS >/dev/null)

rm -rf "${PACKAGE_ROOT}"
mv "${STAGING_ROOT}" "${PACKAGE_ROOT}"
sync

echo "PACKAGE_READY=${PACKAGE_ROOT}"
du -sh "${PACKAGE_ROOT}"
cat "${PACKAGE_ROOT}/package.json"
