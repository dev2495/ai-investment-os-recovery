# Sprint 01 - AI Office MVP

## Status

Started.

## Built

First runnable AI Office GUI:

- Runtime path: `_ai_os_runtime/ai-office-ui`
- Local URL: `http://127.0.0.1:5177/`
- Design reference: `_ai_os_runtime/ai-office-ui/design/ai-office-command-center-concept.png`

Core surface:

- Workspace navigation
- Charlie Munger command bar
- Jarvis runtime/tool layer behind the command bar
- Quick command templates
- Agent Inbox
- Approval Queue
- Portfolio Alerts
- Active Signals
- Agent Team status
- System Health rail
- Next scheduled runs

Local interactions:

- Quick command selection populates the command bar.
- Assign creates a routed Agent Inbox row.
- Trading and signal commands route to Trading Desk.
- Portfolio/client commands route to Portfolio Manager.
- Research/thesis/valuation commands route to Equity Research.
- Quant/backtest/strategy commands route to Quant Agent.
- Approval buttons update queue state and pending count.

## Verification

Commands run:

```bash
cd "_ai_os_runtime/ai-office-ui"
npm install
npm run build
npm audit --audit-level=moderate
```

Results:

- Production build passed.
- Dependency audit reported zero vulnerabilities.
- Browser opened at `http://127.0.0.1:5177/`.
- Desktop viewport checked at 1440 x 1000.
- Mobile viewport checked at 390 x 844.
- Mobile horizontal overflow was found and fixed.
- Command routing was tested with a TradingView signal request.
- Approval queue state was tested by approving a report draft.

Screenshots:

- `_ai_os_runtime/ai-office-ui/design/qa/ai-office-desktop-v2.png`
- `_ai_os_runtime/ai-office-ui/design/qa/ai-office-mobile-v2.png`

## Important Constraint

Docker is not available in the current shell:

```text
zsh:1: command not found: docker
```

Do not make the next step depend on Docker unless Docker Desktop, OrbStack, Colima, or another Postgres runtime is installed.

## Next Step

Build the read-only local data adapter.

Target:

1. Define the runtime adapter interface for Agent Inbox, approvals, signals, portfolio alerts, and health checks.
2. Store MVP state in local JSON or SQLite first.
3. Add importer stubs for old trading DBs and the `ps 2 cursor.zip` archive.
4. Add MCP read tools over the adapter.
5. Add Obsidian write-back for completed inbox items.

The app should remain usable while the data spine is being wired.
