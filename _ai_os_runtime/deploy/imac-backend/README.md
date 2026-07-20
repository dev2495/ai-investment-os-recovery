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
- TradingView: optional governed read/capture browser on the iMac; disabled until one-time sign-in and verification

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
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac browser-enable
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac browser-verify
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac stop
```

`browser-enable` opens a separate managed Chromium profile stored on the SSD.
Sign into TradingView in that window once, then run `browser-verify`. The existing
TradingView desktop app can remain open, but it is not the agent-controlled session.
Chart opening, indicators, screenshots, and evidence capture are permitted. Broker
orders and autonomous live execution remain disabled.

Always run `stop` and wait for `SAFE_TO_EJECT` before disconnecting the SSD.
