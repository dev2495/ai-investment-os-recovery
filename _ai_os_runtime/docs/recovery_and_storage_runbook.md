# AI OS Recovery and Storage Runbook

## Current Storage Contract

- Primary runtime: `/Volumes/Devarsh SSD/Obsidian memory `
- Internal recovery copy: `/Users/devarshthakkar/AI_OS_RECOVERY_BACKUP_20260708/Obsidian memory `
- GitHub repo: private recovery source repo

The SSD contains runtime data and large local caches. GitHub contains source, configuration, docs, and Obsidian markdown memory. Internal recovery contains both.

## Before Starting AI OS

Run:

```bash
/Volumes/Devarsh\ SSD/Obsidian\ memory\ /_ai_os_runtime/scripts/verify_external_storage.sh
```

This verifies:

- the runtime root is on `/Volumes/Devarsh SSD`
- Docker Compose config is valid
- Docker Desktop is not silently using the internal disk image
- an external Docker disk image is present

## After Important Changes

Run:

```bash
/Volumes/Devarsh\ SSD/Obsidian\ memory\ /_ai_os_runtime/scripts/recovery_snapshot.sh
```

This refreshes the internal recovery copy while excluding generated dependency folders and volatile runtime folders.

## If The SSD Light Is On But The Volume Is Missing

1. Stop touching the cable and ports for 30 seconds.
2. Check whether macOS sees the bridge:

```bash
system_profiler SPUSBDataType
diskutil list
```

3. If the disk appears but is unmounted:

```bash
diskutil mountDisk /dev/diskN
```

4. If the volume mounts, immediately run the recovery snapshot before starting services.
5. If the disk does not appear in `diskutil list`, try a different short USB-C cable and direct Mac port before assuming filesystem damage.

## Hardware Prevention

- Use a short high-quality USB-C data cable, not a charging-only cable.
- Avoid hubs for the AI OS runtime drive.
- Do not let the laptop sleep while Docker or rsync is writing to the SSD.
- Eject `/Volumes/Devarsh SSD` before unplugging.
- Keep one internal recovery copy and one private GitHub copy.

## What Not To Put In GitHub

- `.env`
- Docker volume data
- Qdrant/Postgres/Redis data folders
- browser profiles and cookies
- raw broker statements
- large Qt/Fincept build artifacts
- generated dependency folders
