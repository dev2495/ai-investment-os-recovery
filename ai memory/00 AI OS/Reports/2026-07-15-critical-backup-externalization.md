---
title: Critical Backup Externalization
date: 2026-07-15
status: verified_migration
owner: Jarvis
---

# Critical Backup Externalization

The AI OS critical backup root no longer consumes internal Mac storage. Current and previous format-v2 generations now live at `/Volumes/Devarsh SSD/AI OS Data/backups/critical`, and `~/AI_OS_CRITICAL_BACKUP` is a compatibility symlink to that location.

## Evidence

- Internal source before migration: about 4 GB.
- External destination after migration: about 4 GB.
- External free capacity before migration: about 864 GB.
- Current generation: every entry in `integrity/checksums.sha256` passed.
- Current and previous generations: `diff -qr` returned no differences against the internal source.
- Internal available capacity increased from about 31 GB to 35 GB after verified duplicate removal.
- Installed LaunchAgent environment resolves `AI_OS_CRITICAL_BACKUP_ROOT` to the external path.
- Daily schedule remains 03:20 local time.
- Storage guard now checks that the critical backup root exists and resolves under `/Volumes/Devarsh SSD`.

## Source Changes

- `_ai_os_runtime/scripts/critical_state_backup.sh`
- `_ai_os_runtime/scripts/verify_critical_restore.sh`
- `_ai_os_runtime/scripts/verify_external_storage.sh`
- `_ai_os_runtime/launchd/aios-critical-backup-service.sh`
- `_ai_os_runtime/launchd/com.devarsh.aios.critical-backup.plist`

## Snapshot Note

A fresh manual backup was not promoted. Qdrant full-snapshot creation produced a 2.11 GB server-side snapshot and outlasted the interactive validation window. The backup and restore validation processes were terminated, their temporary restore container/volume was removed, and the orphan server-side snapshot was deleted through Qdrant's snapshot API. The last checksum-verified current and previous generations remain intact.

## Remaining Gate

Grant the signed backup helper removable-volume access and observe one unattended 03:20 run complete against the external root. Only then replace the current generation and repeat the isolated restore drill.

## Related

- [[External SSD and AI OS Runtime Recovery Runbook]]
- [[2026-07-13-backup-restore-and-scheduled-reports-v1]]
- [[AI Investment OS - Execution Checklist v10.0]]
