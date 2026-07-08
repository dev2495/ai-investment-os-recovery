#!/usr/bin/env bash
set -euo pipefail

runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker_raw="${HOME}/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"

if [[ "${AI_OS_SKIP_STORAGE_GUARD:-0}" != "1" && -x "${runtime_root}/scripts/verify_external_storage.sh" ]]; then
  "${runtime_root}/scripts/verify_external_storage.sh" >/dev/null
fi

if [[ -e "${docker_raw}" && "${AI_OS_ALLOW_INTERNAL_DOCKER_IMAGE_STORE:-0}" != "1" ]]; then
  echo "Refusing to start: Docker Desktop disk image is still on internal storage."
  echo "${docker_raw}"
  echo
  echo "Move Docker Desktop Disk image location to the external SSD first:"
  echo "/Volumes/Devarsh SSD/Docker Desktop Data"
  echo
  echo "If you intentionally accept temporary internal image storage, run:"
  echo "AI_OS_ALLOW_INTERNAL_DOCKER_IMAGE_STORE=1 ${BASH_SOURCE[0]}"
  exit 2
fi

cd "${runtime_root}"
docker compose config >/dev/null
docker compose up -d
docker compose ps
