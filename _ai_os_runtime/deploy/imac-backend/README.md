# AI OS iMac Backend Package

This package converts the M1 iMac into the nearly-always-on AI OS backend while
the MacBook remains the authoritative development, approval, and operator node.

## Node Contract

- SSD: `/Volumes/Devarsh SSD`
- Vault: `/Volumes/Devarsh SSD/Obsidian memory /ai memory`
- Runtime data: `/Volumes/Devarsh SSD/AI OS Data/imac-runtime`
- Model storage: `/Volumes/Devarsh SSD/AI OS Data/ollama/models`
- Deployed iMac code: `~/AI_OS_NODE/ai-investment-os`
- Independent compact backup: `~/AI_OS_BACKUPS/critical`
- UI/API: loopback only, published privately with Tailscale Serve
- PostgreSQL/Qdrant/Redis/Ollama: loopback only and never exposed publicly
- Trading execution: remains locked and approval-gated
- TradingView: the user-managed native Desktop app; chart handoff only, never canonical data or execution

The recovered raw database directories are never modified. PostgreSQL is restored
from the verified custom dump into `imac-runtime/postgres`; Qdrant is restored from
the verified full snapshot into `imac-runtime/qdrant` and can then be reindexed with
the approved embedding model.

## MacBook: Build The Transfer Package

```bash
cd /Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os
bash _ai_os_runtime/deploy/imac-backend/bin/build-package.sh
```

This writes the self-contained package to:

`/Volumes/Devarsh SSD/AI OS Data/imac-backend-package`

## iMac: Install

1. Attach `Devarsh SSD` directly to the iMac.
2. Install the Tailscale Standalone app and sign into the same tailnet as the MacBook.
3. Enable Tailscale CLI integration from Tailscale Settings.
4. Open the SSD package and run `INSTALL_ON_IMAC.command`.
5. Approve the macOS prompts for Homebrew/Tailscale as requested.

The installer verifies package checksums, installs lean dependencies, deploys the
code, authorizes the dedicated MacBook SSH key, restores the databases, installs
LaunchAgents, starts the backend, configures private Tailscale Serve endpoints, and
runs acceptance checks.

## Operations

On the iMac:

```bash
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac status
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac verify
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac backup
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac reindex
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac desktop-status
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac stop
```

`desktop-status` checks the installed, user-managed TradingView Desktop app. The AI OS can prepare and open chart links in that existing signed-in app. It does not create a second browser profile, treat TradingView as canonical market data, capture unverified evidence automatically, or place broker orders.

Always run `stop` and wait for `SAFE_TO_EJECT` before disconnecting the SSD.
