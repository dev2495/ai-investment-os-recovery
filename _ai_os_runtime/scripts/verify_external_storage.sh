#!/usr/bin/env bash
set -euo pipefail

runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
external_prefix="/Volumes/Devarsh SSD"
docker_raw="${HOME}/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
external_docker_raw="$(find "${external_prefix}" -maxdepth 5 \( -name 'Docker.raw' -o -name '*.raw' \) -print 2>/dev/null | head -n 1 || true)"

echo "AI OS runtime root: ${runtime_root}"

if [[ "${runtime_root}" != "${external_prefix}"* ]]; then
  echo "ERROR: runtime root is not on external SSD: ${runtime_root}" >&2
  exit 1
fi

echo "OK: runtime root is on external SSD."

cd "${runtime_root}"
docker compose config >/dev/null
echo "OK: compose config is valid."

if [[ -e "${docker_raw}" ]]; then
  echo "WARNING: Docker Desktop disk image still exists on internal storage:"
  echo "${docker_raw}"
  echo "Do not pull/start images until Docker Desktop disk image location is moved to external SSD,"
  echo "or explicitly override with AI_OS_ALLOW_INTERNAL_DOCKER_IMAGE_STORE=1."
  exit 2
fi

if [[ -z "${external_docker_raw}" ]]; then
  echo "ERROR: no external Docker.raw/*.raw disk image found under ${external_prefix}" >&2
  echo "Move Docker Desktop disk image location to the external SSD before starting." >&2
  exit 3
fi

echo "OK: Docker Desktop disk image appears external: ${external_docker_raw}"
echo "OK: Docker-managed volumes will be stored inside the external Docker disk image."
