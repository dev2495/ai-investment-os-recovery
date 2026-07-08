# FinceptTerminal Installed Component

## Status

FinceptTerminal is now installed as a local external component of the AI OS.

- Source repo: `https://github.com/Fincept-Corporation/FinceptTerminal`
- Local root: `_ai_os_runtime/external_components/FinceptTerminal`
- Git commit: `6d82e1f`
- App version from build: `4.1.0`
- Qt version: `6.8.3`
- Build preset: `macos-release`
- Build result: `752/752` steps completed
- Binary arch: `arm64`
- App bundle size: `91M`

## Paths

Install root:

```text
/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal
```

Qt prefix:

```text
/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/.qt/6.8.3/macos
```

App bundle:

```text
/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app
```

Binary:

```text
/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/external_components/FinceptTerminal/fincept-qt/build/macos-release/FinceptTerminal.app/Contents/MacOS/FinceptTerminal
```

Launch helper:

```text
_ai_os_runtime/scripts/launch_fincept_terminal.sh
```

## Build Notes

The local build required these major steps:

```bash
git clone --depth 1 https://github.com/Fincept-Corporation/FinceptTerminal.git _ai_os_runtime/external_components/FinceptTerminal
python3.11 -m venv .aqt-venv
.aqt-venv/bin/pip install --upgrade aqtinstall
env AQT_CONFIG=.aqt-settings.ini .aqt-venv/bin/aqt install-qt mac desktop 6.8.3 clang_64 --outputdir .qt --modules qtcharts qtwebsockets qtmultimedia qtspeech
cmake --preset macos-release -DCMAKE_PREFIX_PATH=/Volumes/Devarsh\ SSD/Obsidian\ memory\ /_ai_os_runtime/external_components/FinceptTerminal/.qt/6.8.3/macos -DOPENSSL_ROOT_DIR=/opt/homebrew/opt/openssl@3
cmake --build --preset macos-release --parallel 3
```

Important runtime/build fix:

- Qt tools aborted inside the Codex sandbox with `Incompatible processor. This Qt build requires the following features: neon`.
- Outside the sandbox, `sysctl hw.optional.neon` returned `1`.
- CMake configure/build therefore need to run outside the Codex sandbox when Qt tools are involved.
- Runtime/build assets stay on the external SSD. Homebrew toolchain dependencies such as CMake, Ninja, and OpenSSL remain system-level dependencies under `/opt/homebrew`.

## Registered Warehouse Objects

Migration:

```text
_ai_os_runtime/postgres/init/017_fincept_installed_component.sql
```

New table:

```text
core.external_component_installs
```

New views:

```text
core.v_external_component_installs
core.v_fincept_install_status
```

MCP tool:

```text
ai_os_fincept_install_status
```

## Installed Component Map

Registered installed components:

- Native terminal shell
- Portfolio and equity research workbench
- MCP and agent workflow stack
- Broker market data and live trading adapters
- Quant lab backtesting and strategy workbench
- News filings and research intelligence workbench

Built modules observed during compile include portfolio monitor, equity research, news/RSS, EDGAR tools, broker websockets, Indian broker adapters, F&O option analytics, backtesting, algo deploy dashboard, AI quant lab, node editor, agent config, MCP tools, dashboard widgets, report builder, and data source connectors.

## Integration Policy

Use FinceptTerminal as an installed sidecar and component library, not as the AI OS source of truth.

- AI OS Postgres remains the live data spine.
- Obsidian remains permanent memory and research output layer.
- Charlie Munger remains main orchestrator.
- Jarvis remains runtime/tool layer.
- Client data, broker credentials, and live trading permissions stay in AI OS-controlled storage and approval gates.
- Live broker order placement stays disabled until paper mode, risk checks, audit logs, and explicit approvals are implemented.

## Next Bridge Work

1. Add a UI launcher/status tile in AI Office for the Fincept sidecar.
2. Inventory Fincept MCP tool names and compare them to AI OS MCP schemas.
3. Map Fincept portfolio, research, news, F&O, and broker concepts onto AI OS warehouse tables.
4. Build read-only import/bridge tools first.
5. Only after shadow/paper verification, design approval-gated execution flows.
