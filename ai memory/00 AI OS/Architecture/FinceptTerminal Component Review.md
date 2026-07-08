---
type: component_review
tags:
  - ai-os
  - open-source
  - fincept
  - component-review
created: 2026-07-01
source: https://github.com/Fincept-Corporation/FinceptTerminal
---

# FinceptTerminal Component Review

## Decision

Updated 2026-07-02: FinceptTerminal is now installed and built locally as an external AI OS component.

Use it as a sidecar terminal, component library, and workflow reference. Do not make it the AI OS source of truth. AI OS Postgres remains the data spine, Obsidian remains memory, Charlie Munger remains main orchestrator, and Jarvis remains runtime/tool layer.

Installation record:

```text
ai memory/00 AI OS/Architecture/FinceptTerminal Installed Component.md
```

## Why It Is Useful

FinceptTerminal maps closely to the target AI OS surface:

- Native finance terminal pattern
- Portfolio and equity research workbench
- AI agent catalog
- Local and multi-provider LLM pattern
- Data connector catalog
- Broker integration map
- Visual workflow and MCP node-editor pattern
- Quant lab and analytics modules

## Warehouse Registration

Source system:

`FinceptTerminal reference repo`

Registered components:

- `native terminal shell`
- `portfolio and equity research workbench`
- `mcp and agent workflow stack`
- `broker market data and live trading adapters`
- `quant lab backtesting and strategy workbench`
- `news filings and research intelligence workbench`

Installed status is available through:

```text
core.v_fincept_install_status
ai_os_fincept_install_status
```

## Practical Use In Our System

Use it to guide:

- Dense portfolio dashboard layout
- Agent role catalog
- Connector prioritization
- Portfolio/research workbench modules
- Later node-based automation UI

Do not use it for:

- Client data source of truth
- Ungated direct trading execution
- Broker credential storage outside AI OS controls
- Unsourced client-ready research conclusions
- Replacing the AI OS warehouse/MCP/Obsidian architecture

## Next

- Add a UI launcher/status tile in AI Office.
- Inventory Fincept MCP tool names and compare them to AI OS MCP schemas.
- Map Fincept portfolio, research, news, F&O, broker, and node-editor concepts to AI OS tables/tools.
- Keep live execution disabled until paper mode, risk checks, audit logs, and approvals exist.
