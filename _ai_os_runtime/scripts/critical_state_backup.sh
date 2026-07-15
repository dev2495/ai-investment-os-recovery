#!/usr/bin/env bash
set -euo pipefail

SSD_ROOT="${AI_OS_SSD_ROOT:-/Volumes/Devarsh SSD}"
VAULT_ROOT="${AI_OS_VAULT_ROOT:-${SSD_ROOT}/Obsidian memory }"
VAULT_SOURCE_ROOT="${AI_OS_BACKUP_VAULT_SOURCE:-${VAULT_ROOT}}"
RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-${VAULT_ROOT}/_ai_os_runtime}"
BACKUP_ROOT="${AI_OS_CRITICAL_BACKUP_ROOT:-${SSD_ROOT}/AI OS Data/backups/critical}"
QDRANT_URL="${AI_OS_QDRANT_URL:-http://127.0.0.1:6333}"
CURRENT_ROOT="${BACKUP_ROOT}/current"
PREVIOUS_ROOT="${BACKUP_ROOT}/previous"
LOCK_DIR="${BACKUP_ROOT}/.critical-backup.lock"
STAGING_ROOT=""
LOCK_ACQUIRED=0

cleanup() {
  local exit_code=$?
  if [[ -n "${STAGING_ROOT}" && -d "${STAGING_ROOT}" ]]; then
    rm -rf "${STAGING_ROOT}"
  fi
  if [[ "${LOCK_ACQUIRED}" == "1" && -d "${LOCK_DIR}" ]]; then
    rmdir "${LOCK_DIR}" || true
  fi
  exit "${exit_code}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "${VAULT_ROOT}" != "${SSD_ROOT}"/* ]]; then
  echo "ERROR: external vault is unavailable: ${VAULT_ROOT}" >&2
  exit 1
fi
if [[ ! -d "${VAULT_SOURCE_ROOT}" ]]; then
  echo "ERROR: backup vault source is unavailable: ${VAULT_SOURCE_ROOT}" >&2
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
LOCK_ACQUIRED=1

STAGING_ROOT="$(mktemp -d "${BACKUP_ROOT}/.staging.XXXXXX")"
mkdir -p "${STAGING_ROOT}/postgres" "${STAGING_ROOT}/qdrant" "${STAGING_ROOT}/vault" "${STAGING_ROOT}/code" "${STAGING_ROOT}/integrity"

rsync -a --delete --exclude '_ai_os_runtime/' "${VAULT_SOURCE_ROOT}/" "${STAGING_ROOT}/vault/"
docker exec ai_os_postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${STAGING_ROOT}/postgres/ai_os.dump"
docker exec ai_os_postgres sh -c 'pg_dumpall -U "$POSTGRES_USER" --globals-only' > "${STAGING_ROOT}/postgres/globals.sql"
docker exec -i ai_os_postgres pg_restore --list < "${STAGING_ROOT}/postgres/ai_os.dump" > "${STAGING_ROOT}/postgres/archive.list"
docker exec ai_os_postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "
SELECT jsonb_pretty(jsonb_build_object(
  '\''database_size_bytes'\'', pg_database_size(current_database()),
  '\''schema_count'\'', (SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT LIKE '\''pg_%'\''),
  '\''table_count'\'', (SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('\''pg_catalog'\'', '\''information_schema'\'')),
  '\''agent_tasks'\'', (SELECT count(*) FROM agent.tasks),
  '\''agent_messages'\'', (SELECT count(*) FROM agent.agent_messages),
  '\''clients'\'', (SELECT count(*) FROM portfolio.clients),
  '\''positions'\'', (SELECT count(*) FROM portfolio.positions),
  '\''vector_documents'\'', (SELECT count(*) FROM knowledge.vector_documents),
  '\''ohlcv_rows'\'', (SELECT count(*) FROM trading.ohlcv)
))::text;
"' > "${STAGING_ROOT}/postgres/inventory.json"

repo_root="$(git -C "${RUNTIME_ROOT}" rev-parse --show-toplevel 2>/dev/null || true)"
repo_commit=""
if [[ -n "${repo_root}" ]]; then
  repo_commit="$(git -C "${repo_root}" rev-parse HEAD)"
  git -C "${repo_root}" bundle create "${STAGING_ROOT}/code/ai-investment-os.bundle" --all
  git -C "${repo_root}" bundle verify "${STAGING_ROOT}/code/ai-investment-os.bundle" > "${STAGING_ROOT}/code/bundle-verify.txt" 2>&1
fi

echo "Creating Qdrant full-storage snapshot at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
snapshot_response="$(curl --connect-timeout 10 --max-time 10800 -fsS -X POST "${QDRANT_URL}/snapshots")"
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
echo "Downloaded and verified Qdrant snapshot ${snapshot_name}"

curl -fsS "${QDRANT_URL}/collections" > "${STAGING_ROOT}/qdrant/collections.json"
: > "${STAGING_ROOT}/qdrant/inventory.jsonl"
while IFS= read -r collection_name; do
  curl -fsS "${QDRANT_URL}/collections/${collection_name}" |
    jq -c --arg name "${collection_name}" '{name: $name, points_count: .result.points_count, vectors_count: .result.vectors_count, indexed_vectors_count: .result.indexed_vectors_count, status: .result.status}' >> "${STAGING_ROOT}/qdrant/inventory.jsonl"
done < <(jq -r '.result.collections[].name' "${STAGING_ROOT}/qdrant/collections.json")
jq -s 'sort_by(.name)' "${STAGING_ROOT}/qdrant/inventory.jsonl" > "${STAGING_ROOT}/qdrant/inventory.json"
rm -f "${STAGING_ROOT}/qdrant/inventory.jsonl"

(
  cd "${STAGING_ROOT}"
  find code postgres qdrant vault -type f -print0 | sort -z | xargs -0 shasum -a 256
) > "${STAGING_ROOT}/integrity/checksums.sha256"

{
  printf 'created_at=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'format_version=2\n'
  printf 'repo_commit=%s\n' "${repo_commit}"
  printf 'postgres_image=%s\n' "$(docker inspect ai_os_postgres --format '{{.Config.Image}}')"
  printf 'postgres_version=%s\n' "$(docker exec ai_os_postgres postgres --version | tr ' ' '_')"
  printf 'qdrant_image=%s\n' "$(docker inspect ai_os_qdrant --format '{{.Config.Image}}')"
  printf 'qdrant_version=%s\n' "$(docker exec ai_os_qdrant /qdrant/qdrant --version | tr ' ' '_')"
  printf 'postgres_archive=postgres/ai_os.dump\n'
  printf 'qdrant_snapshot=qdrant/%s\n' "${snapshot_name}"
  printf 'vault_root=vault\n'
  printf 'checksums=integrity/checksums.sha256\n'
} > "${STAGING_ROOT}/manifest.txt"

rm -rf "${PREVIOUS_ROOT}"
if [[ -d "${CURRENT_ROOT}" ]]; then
  mv "${CURRENT_ROOT}" "${PREVIOUS_ROOT}"
fi
mv "${STAGING_ROOT}" "${CURRENT_ROOT}"
STAGING_ROOT=""
sync

echo "Critical AI OS backup completed: ${CURRENT_ROOT}"
