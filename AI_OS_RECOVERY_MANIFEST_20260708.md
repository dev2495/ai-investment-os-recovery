# AI OS Recovery Manifest - 2026-07-08

This repo snapshot was created after the external SSD temporarily disappeared from macOS and then remounted as:

- Volume: `/Volumes/Devarsh SSD`
- Runtime vault: `/Volumes/Devarsh SSD/Obsidian memory `
- Internal recovery copy: `/Users/devarshthakkar/AI_OS_RECOVERY_BACKUP_20260708/Obsidian memory `

## What Is Preserved

- Full recovered file copy is stored in the internal recovery folder above.
- Git tracks the reproducible AI OS stack: scripts, API, MCP server, UI source, agent configs, SQL init files, docs, manifests, and Obsidian memory markdown.
- Git intentionally excludes local secrets, Docker data volumes, browser profiles/cookies, generated logs, node modules, build output, raw broker/client statement files, and large vendored Qt runtime binaries.
- Third-party component repos are represented as Git submodules/component references:
  - FinceptTerminal: `Fincept-Corporation/FinceptTerminal` at `6d82e1f8d6e81c506efeec312414b5d472b437cb`
  - pinescript MCP candidate: `cklose2000/pinescript-mcp-server` at `1f623896126f76665ab5e8390c7684bab69de92f`
  - TradingView MCP candidate: `tradesdontlie/tradingview-mcp` at `4795784a19dd64ff4e2649d2499a536b01bd2d68`
  - TradingView MCP candidate: `atilaahmettaner/tradingview-mcp` at `121d22ebfadd3f7fe7461db7c1299ccdfc917e0b`

## Why Git Excludes Some Files

GitHub rejects files around 100 MB and is not the right place for secrets, cookies, Docker database volumes, or raw client statements. Those files remain in the internal recovery copy. The repo keeps the source stack rebuildable and reviewable.

## Recovery Rule

Before major work:

1. Run `_ai_os_runtime/scripts/verify_external_storage.sh`.
2. Run `_ai_os_runtime/scripts/recovery_snapshot.sh`.
3. Commit and push from the internal recovery repo.

Do not unplug the SSD while AI OS services, Docker, Obsidian, or rsync are active. Always eject the volume first.
