#!/usr/bin/env bash
set -euo pipefail

SSD_ROOT="${AI_OS_SSD_ROOT:-/Volumes/Devarsh SSD}"
VAULT_ROOT="${AI_OS_VAULT_ROOT:-${SSD_ROOT}/Obsidian memory }"
BACKUP_ROOT="${AI_OS_CRITICAL_BACKUP_ROOT:-${HOME}/AI_OS_CRITICAL_BACKUP}"
QDRANT_URL="${AI_OS_QDRANT_URL:-http://127.0.0.1:6333}"
CURRENT_ROOT="${BACKUP_ROOT}/current"
PREVIOUS_ROOT="${BACKUP_ROOT}/previous"
LOCK_DIR="${BACKUP_ROOT}/.critical-backup.lock"
STAGING_ROOT=""

cleanup() {
  local exit_code=$?
  if [[ -n "${STAGING_ROOT}" && -d "${STAGING_ROOT}" ]]; then
    rm -rf "${STAGING_ROOT}"
  fi
  if [[ -d "${LOCK_DIR}" ]]; then
    rmdir "${LOCK_DIR}" || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT

if [[ ! -d "${VAULT_ROOT}" || "${VAULT_ROOT}" != "${SSD_ROOT}"/* ]]; then
  echo "ERROR: external vault is unavailable: ${VAULT_ROOT}" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required to process Qdrant snapshot metadata" >&2
  exit 2
fi

for container in ai_os_postgres ai_os_qdrant; do
  if [[ "$(docker inspect -f '{{.State.Running}}' "${container}")" != "true" ]]; then
    echo "ERROR: ${container} is not running" >&2
    exit 3
  fi
done

mkdir -p "${BACKUP_ROOT}"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "ERROR: another critical backup is already running" >&2
  exit 4
fi

STAGING_ROOT="$(mktemp -d "${BACKUP_ROOT}/.staging.XXXXXX")"
mkdir -p "${STAGING_ROOT}/postgres" "${STAGING_ROOT}/qdrant" "${STAGING_ROOT}/vault"

rsync -a --delete --exclude '_ai_os_runtime/' "${VAULT_ROOT}/" "${STAGING_ROOT}/vault/"
docker exec ai_os_postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${STAGING_ROOT}/postgres/ai_os.dump"
docker exec ai_os_postgres sh -c 'pg_dumpall -U "$POSTGRES_USER" --globals-only' > "${STAGING_ROOT}/postgres/globals.sql"

snapshot_response="$(curl -fsS -X POST "${QDRANT_URL}/snapshots")"
snapshot_name="$(printf '%s' "${snapshot_response}" | jq -r '.result.name // empty')"
snapshot_checksum="$(printf '%s' "${snapshot_response}" | jq -r '.result.checksum // empty')"
if [[ -z "${snapshot_name}" ]]; then
  echo "ERROR: Qdrant did not return a snapshot name" >&2
  exit 5
fi

snapshot_path="${STAGING_ROOT}/qdrant/${snapshot_name}"
curl -fsS "${QDRANT_URL}/snapshots/${snapshot_name}" -o "${snapshot_path}"
if [[ -n "${snapshot_checksum}" ]]; then
  actual_checksum="$(shasum -a 256 "${snapshot_path}" | awk '{print $1}')"
  if [[ "${actual_checksum}" != "${snapshot_checksum}" ]]; then
    echo "ERROR: Qdrant snapshot checksum mismatch" >&2
    exit 6
  fi
fi
curl -fsS -X DELETE "${QDRANT_URL}/snapshots/${snapshot_name}" >/dev/null

{
  printf 'created_at=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'postgres_archive=postgres/ai_os.dump\n'
  printf 'qdrant_snapshot=qdrant/%s\n' "${snapshot_name}"
  printf 'vault_root=vault\n'
} > "${STAGING_ROOT}/manifest.txt"

rm -rf "${PREVIOUS_ROOT}"
if [[ -d "${CURRENT_ROOT}" ]]; then
  mv "${CURRENT_ROOT}" "${PREVIOUS_ROOT}"
fi
mv "${STAGING_ROOT}" "${CURRENT_ROOT}"
STAGING_ROOT=""
rm -rf "${PREVIOUS_ROOT}"

echo "Critical AI OS backup completed: ${CURRENT_ROOT}"
