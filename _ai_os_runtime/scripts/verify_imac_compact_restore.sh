#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${AI_OS_CRITICAL_BACKUP_ROOT:-${AI_OS_OFFSITE_BACKUP_ROOT:-${HOME}/AI_OS_BACKUPS/critical}}"
BACKUP_SET="${AI_OS_BACKUP_SET:-${BACKUP_ROOT}/current}"
EVIDENCE_ROOT="${AI_OS_RESTORE_EVIDENCE_ROOT:-${AI_OS_DATA_ROOT}/artifacts/restore-drills}"
DRILL_KEY="restore-drill-$(date -u '+%Y%m%dT%H%M%SZ')-$$"
DRILL_WORK="${AI_OS_RUNTIME_LOG_ROOT}/restore-drills/${DRILL_KEY}"
RESTORE_DB="ai_os_restore_verify_$$"
VAULT_RESTORE="${DRILL_WORK}/vault-restored"

manifest_value() {
  awk -F= -v key="$1" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "${BACKUP_SET}/manifest.txt"
}

cleanup() {
  local exit_code=$?
  docker exec ai_os_postgres dropdb -U "${AI_OS_POSTGRES_USER}" --if-exists --force "${RESTORE_DB}" >/dev/null 2>&1 || true
  if [[ "${exit_code}" == "0" ]]; then
    rm -rf "${DRILL_WORK}"
  else
    printf 'Restore drill failed; evidence retained at %s\n' "${DRILL_WORK}" >&2
  fi
  trap - EXIT
  exit "${exit_code}"
}
trap cleanup EXIT

for required in manifest.txt integrity/checksums.sha256 postgres/ai_os.dump postgres/inventory.json; do
  [[ -f "${BACKUP_SET}/${required}" ]] || {
    printf 'ERROR: compact backup is missing %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(manifest_value format_version)" == "2" ]] || {
  echo "ERROR: compact backup format_version must be 2" >&2
  exit 3
}
[[ "$(manifest_value backup_profile)" == "imac_compact_rebuildable" ]] || {
  echo "ERROR: compact backup profile is not supported" >&2
  exit 4
}

source_version="$(manifest_value timescaledb_catalog_version)"
target_version="$(manifest_value timescaledb_extension_version)"
[[ "${source_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: invalid Timescale source catalog version" >&2
  exit 5
}
[[ "${target_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "ERROR: invalid Timescale target extension version" >&2
  exit 6
}

mkdir -p "${DRILL_WORK}" "${EVIDENCE_ROOT}" "${VAULT_RESTORE}"
(
  cd "${BACKUP_SET}"
  shasum -a 256 -c integrity/checksums.sha256
) > "${DRILL_WORK}/checksums.log"

repo_commit="$(manifest_value repo_commit)"
[[ "$(cat "${BACKUP_SET}/code/source/DEPLOYED_COMMIT")" == "${repo_commit}" ]] || {
  echo "ERROR: backed-up code commit does not match manifest" >&2
  exit 7
}

rsync -a --delete "${BACKUP_SET}/vault/" "${VAULT_RESTORE}/"
diff -qr "${BACKUP_SET}/vault" "${VAULT_RESTORE}" > "${DRILL_WORK}/vault.diff"

docker exec ai_os_postgres dropdb -U "${AI_OS_POSTGRES_USER}" --if-exists --force "${RESTORE_DB}" >/dev/null 2>&1 || true
docker exec ai_os_postgres createdb -U "${AI_OS_POSTGRES_USER}" -T template0 "${RESTORE_DB}"
docker exec ai_os_postgres psql -q -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION timescaledb VERSION '${source_version}'; SELECT timescaledb_pre_restore();" \
  > "${DRILL_WORK}/timescale-pre-restore.log"
docker exec -i ai_os_postgres pg_restore -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" \
  --no-owner --no-privileges --exit-on-error < "${BACKUP_SET}/postgres/ai_os.dump" \
  > "${DRILL_WORK}/pg-restore.log"
if [[ "${source_version}" != "${target_version}" ]]; then
  docker exec ai_os_postgres psql -q -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" -v ON_ERROR_STOP=1 \
    -c "ALTER EXTENSION timescaledb UPDATE TO '${target_version}';" \
    > "${DRILL_WORK}/timescale-upgrade.log"
fi
docker exec ai_os_postgres psql -q -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" -v ON_ERROR_STOP=1 \
  -c "SELECT timescaledb_post_restore();" > "${DRILL_WORK}/timescale-post-restore.log"

docker exec ai_os_postgres psql -q -t -A -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" \
  -v ON_ERROR_STOP=1 -c "
    SELECT json_build_object(
      'clients',(SELECT count(*) FROM portfolio.clients),
      'positions',(SELECT count(*) FROM portfolio.positions),
      'agent_tasks',(SELECT count(*) FROM agent.tasks),
      'raw_artifacts',(SELECT count(*) FROM core.raw_artifacts),
      'ohlcv_rows',(SELECT count(*) FROM trading.ohlcv),
      'tables',(SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema'))
    );
  " > "${DRILL_WORK}/postgres-restored-inventory.json"

jq -S . "${BACKUP_SET}/postgres/inventory.json" > "${DRILL_WORK}/postgres-expected.json"
jq -S . "${DRILL_WORK}/postgres-restored-inventory.json" > "${DRILL_WORK}/postgres-actual.json"
diff -u "${DRILL_WORK}/postgres-expected.json" "${DRILL_WORK}/postgres-actual.json" \
  > "${DRILL_WORK}/postgres-inventory.diff"

restored_extension="$(docker exec ai_os_postgres psql -q -t -A -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb'")"
restored_catalog="$(docker exec ai_os_postgres psql -q -t -A -U "${AI_OS_POSTGRES_USER}" -d "${RESTORE_DB}" -c "SELECT value FROM _timescaledb_catalog.metadata WHERE key='timescaledb_version'")"
[[ "${restored_extension}" == "${target_version}" && "${restored_catalog}" == "${target_version}" ]] || {
  echo "ERROR: restored Timescale extension and catalog versions are not aligned" >&2
  exit 8
}

qdrant_collections="$(curl --max-time 5 -fsS "http://127.0.0.1:${AI_OS_QDRANT_HTTP_PORT}/collections" | jq '.result.collections | length')"
evidence_file="${EVIDENCE_ROOT}/${DRILL_KEY}.json"
jq -n \
  --arg drill_key "${DRILL_KEY}" \
  --arg verified_at "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  --arg backup_created_at "$(manifest_value created_at)" \
  --arg backup_profile "$(manifest_value backup_profile)" \
  --arg repo_commit "${repo_commit}" \
  --arg postgres_image "$(manifest_value postgres_image)" \
  --arg timescaledb_extension "${restored_extension}" \
  --arg timescaledb_catalog "${restored_catalog}" \
  --argjson postgres "$(cat "${DRILL_WORK}/postgres-restored-inventory.json")" \
  --argjson qdrant_collections "${qdrant_collections}" \
  '{
    drill_key: $drill_key,
    status: "passed",
    verified_at: $verified_at,
    backup_created_at: $backup_created_at,
    backup_profile: $backup_profile,
    repo_commit: $repo_commit,
    vault_restore: "byte_identical",
    postgres_image: $postgres_image,
    timescaledb: {extension: $timescaledb_extension, catalog: $timescaledb_catalog},
    postgres: $postgres,
    qdrant: {restore_mode: "rebuild_from_source", source_collections_online: $qdrant_collections}
  }' > "${evidence_file}"

printf 'Compact restore drill passed: %s\n' "${evidence_file}"
cat "${evidence_file}"
