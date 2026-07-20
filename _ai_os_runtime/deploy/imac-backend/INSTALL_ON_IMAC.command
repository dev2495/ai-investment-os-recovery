#!/bin/bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AI_OS_PACKAGE_ROOT="${PACKAGE_ROOT}"

if [[ ! -x "${PACKAGE_ROOT}/source/_ai_os_runtime/deploy/imac-backend/bin/aios-imac" ]]; then
  echo "Package source or installer is missing. Rebuild the package on the MacBook." >&2
  read -r -p "Press Return to close..." _
  exit 1
fi

"${PACKAGE_ROOT}/source/_ai_os_runtime/deploy/imac-backend/bin/aios-imac" install
echo
echo "iMac backend installation command completed. Review the status above."
read -r -p "Press Return to close..." _
