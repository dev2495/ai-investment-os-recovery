#!/usr/bin/env bash
set -euo pipefail

runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
external_prefix="/Volumes/Devarsh SSD"
vault_root="${AI_OS_VAULT_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
ollama_models="${AI_OS_OLLAMA_MODELS:-/Volumes/Devarsh SSD/AI OS Data/ollama/models}"
critical_backup_root="${AI_OS_CRITICAL_BACKUP_ROOT:-/Volumes/Devarsh SSD/AI OS Data/backups/critical}"
docker_raw="${HOME}/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw"
external_docker_raw="$(find "${external_prefix}" -maxdepth 5 \( -name 'Docker.raw' -o -name '*.raw' \) -print 2>/dev/null | head -n 1 || true)"

echo "AI OS runtime root: ${runtime_root}"

if [[ ! -d "${external_prefix}" ]]; then
  echo "ERROR: external SSD is not mounted at ${external_prefix}" >&2
  exit 1
fi

echo "OK: external SSD is mounted."

if [[ "${vault_root}" != "${external_prefix}"* || ! -d "${vault_root}" ]]; then
  echo "ERROR: vault root is not available on the external SSD: ${vault_root}" >&2
  exit 1
fi

if [[ "${ollama_models}" != "${external_prefix}"* || ! -d "${ollama_models}" ]]; then
  echo "ERROR: Ollama model storage is not available on the external SSD: ${ollama_models}" >&2
  exit 1
fi

echo "OK: vault data is external: ${vault_root}"
echo "OK: Ollama model data is external: ${ollama_models}"

if [[ ! -d "${critical_backup_root}" ]]; then
  echo "ERROR: critical backup root is missing: ${critical_backup_root}" >&2
  exit 1
fi
resolved_backup_root="$(cd "${critical_backup_root}" && pwd -P)"
if [[ "${resolved_backup_root}" != "${external_prefix}"* ]]; then
  echo "ERROR: critical backup root is not on the external SSD: ${critical_backup_root} -> ${resolved_backup_root}" >&2
  exit 1
fi
echo "OK: critical backup data is external: ${critical_backup_root} -> ${resolved_backup_root}"

persistent_paths=(
  "${runtime_root}/logs"
  "${runtime_root}/run"
  "${runtime_root}/ai-office-ui/node_modules"
)

for persistent_path in "${persistent_paths[@]}"; do
  if [[ ! -e "${persistent_path}" ]]; then
    echo "ERROR: required persistent path is missing: ${persistent_path}" >&2
    exit 1
  fi
  resolved_path="$(cd "${persistent_path}" && pwd -P)"
  if [[ "${resolved_path}" != "${external_prefix}"* ]]; then
    echo "ERROR: persistent path is not on the external SSD: ${persistent_path} -> ${resolved_path}" >&2
    exit 1
  fi
  echo "OK: persistent path is external: ${persistent_path} -> ${resolved_path}"
done

if [[ "${runtime_root}" == "${external_prefix}"* ]]; then
  echo "OK: runtime source is on the external SSD."
else
  echo "INFO: runtime source is on internal storage; persistent vault, model, and Docker data remain external."
fi

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
