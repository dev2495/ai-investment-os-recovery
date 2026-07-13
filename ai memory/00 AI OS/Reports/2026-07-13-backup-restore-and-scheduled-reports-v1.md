# Backup, Restore, And Scheduled Reports v1

Date: 2026-07-13
Status: verified implementation checkpoint
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Frontend: [[AI OS Command Center and 3D Office Frontend Plan]]

## Result

The AI OS now has a format-v2 critical-state backup, an isolated restore drill with exact data reconciliation, ten warehouse-backed recurring reports, period-level idempotence, approval-gated client drafts, and live recovery/report status in the Command Center. No seed rows, broker writes, client sends, or capital actions were introduced.

The only open gate in this checkpoint is macOS removable-volume consent for unattended vault access. The signed helper and both LaunchAgents are installed without Full Disk Access. After the Mac is unlocked, opening `~/Applications/AI OS Backup.app` and selecting the external Obsidian vault will create the narrow security-scoped bookmark needed for the final launchd access check.

## Critical Backup v2

Verified backup root: `~/AI_OS_CRITICAL_BACKUP/current`.

- Atomic staging, lock ownership, current/previous rotation, and signal cleanup are implemented.
- Vault copy excludes the runtime symlink and contains 327 files.
- Postgres uses a custom-format archive plus globals, archive list, and inventory.
- Qdrant uses a full storage snapshot and collection inventory.
- The Git repository is stored as a verified Git bundle.
- SHA-256 checksums cover the backup payload.
- The manifest records repository commit, database/vector images and versions, paths, and creation time.
- Current backup was created at `2026-07-13T05:11:17Z`.
- Postgres archive size: 5,946,151 bytes.
- Qdrant full snapshot size: 2,111,212,544 bytes.
- Current and previous generations both exist.

Installed schedules:

- `com.devarsh.aios.critical-backup`: daily 03:20 local.
- `com.devarsh.aios.scheduled-reports`: daily 08:35 local.

The signed helper uses one security-scoped bookmark for the selected vault. It stages the vault inside the internal backup root, explicitly removes staging before exit, and uses the same scoped access for report writeback. The launchd jobs pass explicit noninteractive modes, so they cannot display a permission dialog.

## Isolated Restore Drill

Proof artifact:

`/Volumes/Devarsh SSD/AI OS Data/artifacts/restore-drills/restore-drill-20260713T052952Z-33333.json`

The drill used temporary containers and Docker volumes and did not modify live services.

- Vault restore: byte-identical.
- Git bundle: clone and verification passed.
- Timescale/Postgres: extension initialization, pre-restore, `pg_restore`, post-restore, and `ANALYZE` passed.
- Reconciled database counts: 3 clients, 72 positions, 2,131 OHLCV rows, 225 tasks, 57 messages, 2,212 vector documents, 21 schemas, and 457 tables.
- Qdrant: six collections restored with exact source point counts.
- Temporary containers and volumes were removed after the successful drill.

Restore procedure follows the official operational contracts:

- PostgreSQL `pg_restore`: https://www.postgresql.org/docs/17/app-pgrestore.html
- Timescale logical restore: https://docs.timescale.com/self-hosted/latest/backup-and-restore/logical-backup/
- Qdrant snapshots: https://qdrant.tech/documentation/operations/snapshots/

## Scheduled Report Engine

Migration `111_scheduled_report_engine_v1.sql` adds:

- `ops.report_schedules`;
- `ops.report_runs`;
- `ops.v_report_schedule_status`;
- `ops.v_recent_report_runs`.

Configured recurring outputs:

1. Daily Agent Activity Brief.
2. Daily Market Brief.
3. Daily Portfolio Brief.
4. Data Source Freshness Report.
5. Full System Status Report.
6. Model Cost Report.
7. Monthly Client Report Drafts.
8. Provider Readiness Report.
9. Weekly Research Digest.
10. Weekly Risk Report.

Every report reads only bounded scoped APIs. Empty sections state missing evidence instead of inventing estimates. A successful run atomically creates the report run, Obsidian note, task, inbox item, worker run, source snapshot, output hash, and evidence lineage.

Canonical period runs completed as IDs `14` through `23`. Monthly run `#20` created pending client-report approval `#16`; the note states that external delivery, recommendation, capital, and broker authority remain blocked. An immediate second scheduler pass returned `not_due` for all ten schedules and created no duplicates.

The first bounded tests remain visible in `ops.report_runs` as audit evidence: one sandbox write failure and one approval-CTE failure. The unregistered draft file from the failed transaction was removed. Production canonical runs are completed.

## Command Center

Reports now exposes:

- ten live schedule rows with cadence, owner, due state, approval requirement, last completion, and output path;
- recent run history with task evidence drill-down;
- 185 output artifacts, 146 raw imports, lineage, gaps, coverage, and worker output;
- zero broad `/api/snapshot` requests.

System Health now exposes:

- current and previous backup generation presence;
- manifest format and creation time;
- vault file count;
- Postgres and Qdrant archive sizes;
- checksum presence;
- latest isolated restore status and artifact path;
- installed backup and report schedules.

The recovery status is file-backed so it remains inspectable even if Postgres is unavailable.

## Verification

- Python syntax validation passed for API and report scripts.
- TypeScript and Vite production build passed.
- Main JS: 269.40 KB, gzip 73.07 KB.
- Live Office remains lazy-loaded at 859.43 KB, gzip 229.28 KB.
- Four scheduler/recovery browser tests passed: live schedules and task evidence, Reports mobile fit, recovery-chain proof, and System Health mobile fit.
- The permanent 23-case WCAG A/AA gate passed in four clean-exit shards.
- Deployed API and UI checksums matched repository builds.
- Scoped Reports API: 14 queries, 678 rows, 10 schedules, 23 runs, zero due.
- Scoped System Health API: 18 queries, 222 warehouse rows plus file-backed recovery evidence.
- Screenshots: `/Volumes/Devarsh SSD/AI OS Data/artifacts/browser-verification/2026-07-13-scheduled-reports-and-restore-v1`.

## Blueprint Registry

- Sync run: `blueprint-v10-backup-restore-reports-v1-20260713`.
- Checklist SHA-256: `4385cd45c183c87c19b040754c15bcbd2fdbf424bacb331f4fd6d5a95a45b58b`.
- Coverage: 21 domains, 523 requirements, 73 done, 167 partial, 283 planned, zero seed rows.

## Remaining Gate

1. Unlock macOS.
2. Open `~/Applications/AI OS Backup.app`.
3. Select `/Volumes/Devarsh SSD/Obsidian memory ` and click `Use Vault`.
4. Kickstart both LaunchAgents in access-check/due mode.
5. Confirm the backup helper reads the scoped vault, the report helper writes to the live vault, no staging directory remains, and logs exit zero.

Until those five checks pass, the durable backup checklist item remains partial even though the backup payload and restore drill are verified.
