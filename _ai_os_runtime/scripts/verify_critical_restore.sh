#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SCRIPT_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SSD_ROOT="${AI_OS_SSD_ROOT:-/Volumes/Devarsh SSD}"
BACKUP_ROOT="${AI_OS_CRITICAL_BACKUP_ROOT:-${SSD_ROOT}/AI OS Data/backups/critical}"
BACKUP_SET="${AI_OS_BACKUP_SET:-${BACKUP_ROOT}/current}"
DRILL_KEY="restore-drill-$(date -u '+%Y%m%dT%H%M%SZ')-$$"
DRILL_ROOT="${AI_OS_RESTORE_DRILL_ROOT:-${SSD_ROOT}/AI OS Data/restore-drills/${DRILL_KEY}}"
EVIDENCE_ROOT="${AI_OS_RESTORE_EVIDENCE_ROOT:-${SSD_ROOT}/AI OS Data/artifacts/restore-drills}"
PG_CONTAINER="ai_os_restore_postgres_$$"
PG_VOLUME="ai_os_restore_postgres_$$"
QDRANT_CONTAINER="ai_os_restore_qdrant_$$"
QDRANT_VOLUME="ai_os_restore_qdrant_$$"
QDRANT_SNAPSHOT_VOLUME="ai_os_restore_qdrant_snapshots_$$"
QDRANT_STAGER_CONTAINER="ai_os_restore_qdrant_stager_$$"
QDRANT_PORT="${AI_OS_RESTORE_QDRANT_PORT:-6335}"
QDRANT_RESTORE_TIMEOUT_SECONDS="${AI_OS_QDRANT_RESTORE_TIMEOUT_SECONDS:-900}"
POSTGRES_RESTORE_ROLES_SQL="${SCRIPT_ROOT}/restore_required_roles.sql"
POSTGRES_RESTORE_ACL_SQL="${SCRIPT_ROOT}/restore_required_acl.sql"

manifest_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${BACKUP_SET}/manifest.txt"
}

cleanup() {
  local exit_code=$?
  mkdir -p "${DRILL_ROOT}/evidence" 2>/dev/null || true
  docker logs "${PG_CONTAINER}" > "${DRILL_ROOT}/evidence/postgres-container.log" 2>&1 || true
  docker logs "${QDRANT_CONTAINER}" > "${DRILL_ROOT}/evidence/qdrant-container.log" 2>&1 || true
  docker rm -f "${PG_CONTAINER}" "${QDRANT_CONTAINER}" "${QDRANT_STAGER_CONTAINER}" >/dev/null 2>&1 || true
  docker volume rm "${PG_VOLUME}" "${QDRANT_VOLUME}" "${QDRANT_SNAPSHOT_VOLUME}" >/dev/null 2>&1 || true
  if [[ "${exit_code}" == "0" && "${AI_OS_KEEP_RESTORE_DRILL:-0}" != "1" ]]; then
    rm -rf "${DRILL_ROOT}"
  elif [[ "${exit_code}" != "0" ]]; then
    echo "Restore drill failed; evidence retained at ${DRILL_ROOT}" >&2
  fi
  trap - EXIT
  exit "${exit_code}"
}
trap cleanup EXIT

if [[ ! -f "${BACKUP_SET}/manifest.txt" || ! -f "${BACKUP_SET}/integrity/checksums.sha256" ]]; then
  echo "ERROR: verified backup format v2 is required at ${BACKUP_SET}" >&2
  exit 1
fi
if [[ "$(manifest_value format_version)" != "2" ]]; then
  echo "ERROR: unsupported backup format" >&2
  exit 2
fi
if [[ ! -f "${POSTGRES_RESTORE_ROLES_SQL}" || ! -r "${POSTGRES_RESTORE_ROLES_SQL}" ]]; then
  echo "ERROR: sanitized PostgreSQL restore-role contract is unavailable" >&2
  exit 4
fi
if [[ ! -f "${POSTGRES_RESTORE_ACL_SQL}" || ! -r "${POSTGRES_RESTORE_ACL_SQL}" ]]; then
  echo "ERROR: sanitized PostgreSQL restore ACL contract is unavailable" >&2
  exit 4
fi
if lsof -tiTCP:"${QDRANT_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: restore port ${QDRANT_PORT} is already in use" >&2
  exit 3
fi

mkdir -p "${DRILL_ROOT}/vault" "${DRILL_ROOT}/code" "${DRILL_ROOT}/evidence" "${EVIDENCE_ROOT}"
(
  cd "${BACKUP_SET}"
  shasum -a 256 -c integrity/checksums.sha256
) > "${DRILL_ROOT}/evidence/checksums.log"

rsync -a --delete "${BACKUP_SET}/vault/" "${DRILL_ROOT}/vault/"
rsync -a --checksum --delete --dry-run --itemize-changes \
  "${BACKUP_SET}/vault/" "${DRILL_ROOT}/vault/" > "${DRILL_ROOT}/evidence/vault-diff.log"
if [[ -s "${DRILL_ROOT}/evidence/vault-diff.log" ]]; then
  echo "ERROR: restored vault differs from the backup" >&2
  exit 4
fi

git bundle verify "${BACKUP_SET}/code/ai-investment-os.bundle" > "${DRILL_ROOT}/evidence/git-bundle-verify.log" 2>&1
git clone --quiet "${BACKUP_SET}/code/ai-investment-os.bundle" "${DRILL_ROOT}/code/ai-investment-os"
restored_commit="$(git -C "${DRILL_ROOT}/code/ai-investment-os" rev-parse HEAD)"
if [[ "${restored_commit}" != "$(manifest_value repo_commit)" ]]; then
  echo "ERROR: restored Git commit does not match the manifest" >&2
  exit 4
fi

timescaledb_extension_version="$(manifest_value timescaledb_extension_version)"
if [[ ! "${timescaledb_extension_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: backup manifest is missing a valid TimescaleDB extension version" >&2
  exit 4
fi
postgres_major="$(manifest_value postgres_version | sed -E 's/.*_([0-9]+)\..*/\1/')"
if [[ ! "${postgres_major}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: backup manifest is missing a valid PostgreSQL major version" >&2
  exit 4
fi
postgres_image="$(manifest_value postgres_restore_image)"
postgres_image="${postgres_image:-timescale/timescaledb:${timescaledb_extension_version}-pg${postgres_major}}"
docker image inspect "${postgres_image}" >/dev/null
docker volume create "${PG_VOLUME}" >/dev/null
docker run -d --name "${PG_CONTAINER}" \
  -e POSTGRES_USER=ai_os \
  -e POSTGRES_PASSWORD=ai_os_restore_only \
  -e POSTGRES_DB=ai_os_restore \
  -v "${PG_VOLUME}:/var/lib/postgresql/data" \
  "${postgres_image}" >/dev/null
for _ in $(seq 1 120); do
  docker logs "${PG_CONTAINER}" > "${DRILL_ROOT}/evidence/postgres-readiness.log" 2>&1 || true
  if grep -Fq 'PostgreSQL init process complete; ready for start up.' "${DRILL_ROOT}/evidence/postgres-readiness.log" && \
     docker exec "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -tAc 'SELECT 1' 2>/dev/null | grep -Fxq '1'; then
    break
  fi
  sleep 1
done
grep -Fq 'PostgreSQL init process complete; ready for start up.' "${DRILL_ROOT}/evidence/postgres-readiness.log"
docker exec "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -tAc 'SELECT 1' | grep -Fxq '1'
docker exec -i "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -v ON_ERROR_STOP=1 -f - < "${POSTGRES_RESTORE_ROLES_SQL}" > "${DRILL_ROOT}/evidence/postgres-restore-roles.log" 2>&1
docker exec "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb VERSION '${timescaledb_extension_version}'; SELECT timescaledb_pre_restore();"
docker exec -i "${PG_CONTAINER}" pg_restore -U ai_os -d ai_os_restore --exit-on-error --no-owner --no-privileges < "${BACKUP_SET}/postgres/ai_os.dump"
docker exec "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -v ON_ERROR_STOP=1 -c 'SELECT timescaledb_post_restore(); ANALYZE;'
docker exec -i "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -v ON_ERROR_STOP=1 -f - < "${POSTGRES_RESTORE_ACL_SQL}" > "${DRILL_ROOT}/evidence/postgres-restore-acl.log" 2>&1
restore_verification_sql="${AI_OS_RESTORE_VERIFICATION_SQL:-}"
if [[ -n "${restore_verification_sql}" ]]; then
  if [[ ! -f "${restore_verification_sql}" || ! -r "${restore_verification_sql}" ]]; then
    echo "ERROR: AI_OS_RESTORE_VERIFICATION_SQL must name a readable host SQL file" >&2
    exit 4
  fi
  docker exec -i "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -v ON_ERROR_STOP=1 -f - < "${restore_verification_sql}" > "${DRILL_ROOT}/evidence/postgres-verification-sql.log" 2>&1
fi
docker exec "${PG_CONTAINER}" psql -U ai_os -d ai_os_restore -tAc "
SELECT jsonb_pretty(jsonb_build_object(
  'database_size_bytes', pg_database_size(current_database()),
  'schema_count', (SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%'),
  'table_count', (SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')),
  'agent_tasks', (SELECT count(*) FROM agent.tasks),
  'agent_messages', (SELECT count(*) FROM agent.agent_messages),
  'clients', (SELECT count(*) FROM portfolio.clients),
  'positions', (SELECT count(*) FROM portfolio.positions),
  'vector_documents', (SELECT count(*) FROM knowledge.vector_documents),
  'ohlcv_rows', (SELECT count(*) FROM trading.ohlcv)
))::text;
" > "${DRILL_ROOT}/evidence/postgres-restored-inventory.json"
jq -S 'del(.database_size_bytes)' "${BACKUP_SET}/postgres/inventory.json" > "${DRILL_ROOT}/evidence/postgres-expected.json"
jq -S 'del(.database_size_bytes)' "${DRILL_ROOT}/evidence/postgres-restored-inventory.json" > "${DRILL_ROOT}/evidence/postgres-actual.json"
diff -u "${DRILL_ROOT}/evidence/postgres-expected.json" "${DRILL_ROOT}/evidence/postgres-actual.json" > "${DRILL_ROOT}/evidence/postgres-inventory.diff"

qdrant_image="$(manifest_value qdrant_image)"
qdrant_snapshot="${BACKUP_SET}/$(manifest_value qdrant_snapshot)"
docker volume create "${QDRANT_VOLUME}" >/dev/null
docker volume create "${QDRANT_SNAPSHOT_VOLUME}" >/dev/null
# Colima file binds from the external SSD can materialize regular files as
# empty directories. docker cp streams the checksummed bytes into a disposable
# volume whose backing store remains inside the SSD-configured Colima runtime.
docker run -d --name "${QDRANT_STAGER_CONTAINER}" \
  -v "${QDRANT_SNAPSHOT_VOLUME}:/snapshots" \
  "${qdrant_image}" sh -lc 'sleep 600' >/dev/null
docker cp "${qdrant_snapshot}" "${QDRANT_STAGER_CONTAINER}:/snapshots/backup.snapshot"
docker rm -f "${QDRANT_STAGER_CONTAINER}" >/dev/null
docker run -d --name "${QDRANT_CONTAINER}" \
  -p "127.0.0.1:${QDRANT_PORT}:6333" \
  -v "${QDRANT_VOLUME}:/qdrant/storage" \
  -v "${QDRANT_SNAPSHOT_VOLUME}:/snapshots:ro" \
  "${qdrant_image}" ./qdrant --storage-snapshot /snapshots/backup.snapshot >/dev/null
qdrant_ready=0
for _ in $(seq 1 "${QDRANT_RESTORE_TIMEOUT_SECONDS}"); do
  if curl --max-time 2 -fsS "http://127.0.0.1:${QDRANT_PORT}/collections" >/dev/null 2>&1; then
    qdrant_ready=1
    break
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "${QDRANT_CONTAINER}" 2>/dev/null || true)" != "true" ]]; then
    break
  fi
  sleep 1
done
if [[ "${qdrant_ready}" != "1" ]]; then
  docker logs "${QDRANT_CONTAINER}" > "${DRILL_ROOT}/evidence/qdrant-full-restore.log" 2>&1 || true
  docker rm -f "${QDRANT_CONTAINER}" >/dev/null 2>&1 || true
  snapshot_unpack_root="${DRILL_ROOT}/qdrant-snapshot"
  mkdir -p "${snapshot_unpack_root}"
  if tar -tf "${qdrant_snapshot}" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
    echo "ERROR: Qdrant snapshot contains an unsafe archive path" >&2
    exit 5
  fi
  tar -xf "${qdrant_snapshot}" -C "${snapshot_unpack_root}"
  if [[ ! -f "${snapshot_unpack_root}/config.json" ]]; then
    echo "ERROR: Qdrant full snapshot has no collection mapping" >&2
    exit 5
  fi
  snapshot_args=()
  while IFS=$'\t' read -r collection_name snapshot_file; do
    if [[ ! "${collection_name}" =~ ^[A-Za-z0-9_.-]+$ || "${snapshot_file}" != "$(basename "${snapshot_file}")" || ! -f "${snapshot_unpack_root}/${snapshot_file}" ]]; then
      echo "ERROR: invalid Qdrant collection snapshot mapping" >&2
      exit 5
    fi
    snapshot_args+=(--snapshot "/snapshots/${snapshot_file}:${collection_name}")
  done < <(jq -r '.collections_mapping | to_entries[] | [.key,.value] | @tsv' "${snapshot_unpack_root}/config.json")
  if [[ "${#snapshot_args[@]}" == "0" ]]; then
    echo "ERROR: Qdrant full snapshot contains no collections" >&2
    exit 5
  fi
  docker volume rm "${QDRANT_VOLUME}" >/dev/null 2>&1 || true
  docker volume create "${QDRANT_VOLUME}" >/dev/null
  docker run -d --name "${QDRANT_STAGER_CONTAINER}" \
    -v "${QDRANT_SNAPSHOT_VOLUME}:/snapshots" \
    "${qdrant_image}" sh -lc 'sleep 600' >/dev/null
  while IFS=$'\t' read -r collection_name snapshot_file; do
    docker cp "${snapshot_unpack_root}/${snapshot_file}" "${QDRANT_STAGER_CONTAINER}:/snapshots/${snapshot_file}"
  done < <(jq -r '.collections_mapping | to_entries[] | [.key,.value] | @tsv' "${snapshot_unpack_root}/config.json")
  docker rm -f "${QDRANT_STAGER_CONTAINER}" >/dev/null
  docker run -d --name "${QDRANT_CONTAINER}" \
    -p "127.0.0.1:${QDRANT_PORT}:6333" \
    -v "${QDRANT_VOLUME}:/qdrant/storage" \
    -v "${QDRANT_SNAPSHOT_VOLUME}:/snapshots:ro" \
    "${qdrant_image}" ./qdrant "${snapshot_args[@]}" >/dev/null
  for _ in $(seq 1 "${QDRANT_RESTORE_TIMEOUT_SECONDS}"); do
    if curl --max-time 2 -fsS "http://127.0.0.1:${QDRANT_PORT}/collections" >/dev/null 2>&1; then
      qdrant_ready=1
      break
    fi
    if [[ "$(docker inspect -f '{{.State.Running}}' "${QDRANT_CONTAINER}" 2>/dev/null || true)" != "true" ]]; then
      break
    fi
    sleep 1
  done
fi
if [[ "${qdrant_ready}" != "1" ]]; then
  echo "ERROR: restored Qdrant did not become ready within ${QDRANT_RESTORE_TIMEOUT_SECONDS} seconds" >&2
  exit 5
fi
curl -fsS "http://127.0.0.1:${QDRANT_PORT}/collections" > "${DRILL_ROOT}/evidence/qdrant-collections.json"
: > "${DRILL_ROOT}/evidence/qdrant-restored.jsonl"
while IFS= read -r collection_name; do
  curl -fsS "http://127.0.0.1:${QDRANT_PORT}/collections/${collection_name}" |
    jq -c --arg name "${collection_name}" '{name: $name, points_count: .result.points_count, vectors_count: .result.vectors_count, indexed_vectors_count: .result.indexed_vectors_count, status: .result.status}' >> "${DRILL_ROOT}/evidence/qdrant-restored.jsonl"
done < <(jq -r '.result.collections[].name' "${DRILL_ROOT}/evidence/qdrant-collections.json")
jq -s 'sort_by(.name)' "${DRILL_ROOT}/evidence/qdrant-restored.jsonl" > "${DRILL_ROOT}/evidence/qdrant-restored-inventory.json"
jq -n -S \
  --slurpfile collections "${BACKUP_SET}/qdrant/collections.json" \
  --slurpfile inventory "${BACKUP_SET}/qdrant/inventory.json" \
  '$collections[0].result.collections | map(.name) as $names | $inventory[0] as $rows | [range(0; ($names | length)) as $index | {name: ($rows[$index].name // $names[$index]), points_count: $rows[$index].points_count}] | sort_by(.name)' > "${DRILL_ROOT}/evidence/qdrant-expected.json"
jq -S '[.[] | {name, points_count}]' "${DRILL_ROOT}/evidence/qdrant-restored-inventory.json" > "${DRILL_ROOT}/evidence/qdrant-actual.json"
diff -u "${DRILL_ROOT}/evidence/qdrant-expected.json" "${DRILL_ROOT}/evidence/qdrant-actual.json" > "${DRILL_ROOT}/evidence/qdrant-inventory.diff"

evidence_file="${EVIDENCE_ROOT}/${DRILL_KEY}.json"
jq -n \
  --arg drill_key "${DRILL_KEY}" \
  --arg verified_at "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  --arg backup_created_at "$(manifest_value created_at)" \
  --arg repo_commit "${restored_commit}" \
  --argjson postgres "$(cat "${DRILL_ROOT}/evidence/postgres-restored-inventory.json")" \
  --argjson qdrant "$(cat "${DRILL_ROOT}/evidence/qdrant-restored-inventory.json")" \
  '{drill_key: $drill_key, status: "passed", verified_at: $verified_at, backup_created_at: $backup_created_at, repo_commit: $repo_commit, vault_restore: "byte_identical", postgres: $postgres, qdrant: $qdrant}' > "${evidence_file}"

echo "Critical restore drill passed: ${evidence_file}"
