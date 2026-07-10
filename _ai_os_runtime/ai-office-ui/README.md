# AI Office UI

First local AI Office command-center surface.

## What It Does Now

- Shows the main AI Office workspaces.
- Provides a Jarvis command bar.
- Routes submitted commands into Postgres-backed Agent Inbox or TradingView task rows.
- Shows Agent Inbox, Approval Queue, Portfolio Alerts, Active Signals, Agent Team status, System Health, and Next Runs from the live warehouse only.
- Supports approval/reject writes through the API.
- Stages manual holding updates into `portfolio.manual_holding_updates`.
- Does not use seed/demo fallback data.
- Collapses to a single-column mobile work surface.
- Opens a lazy-loaded Live Office view backed by the same Postgres snapshot, including rooms, agents, tasks, mailboxes, and committee items.

## Commands

```bash
npm install
npm run dev
npm run build
npm audit --audit-level=moderate
```

Default local URL:

```text
http://127.0.0.1:5177/
```

## Design Reference

- `design/ai-office-command-center-concept.png`

## Verification

Last verified:

- `npm run build`: pass
- `npm audit --audit-level=moderate`: zero vulnerabilities
- Desktop viewport: 1440 x 1000
- Mobile viewport: 390 x 844
- Interaction: quick command -> API write -> Agent Inbox/TradingView task row
- Interaction: approval button -> API write -> approval decision persisted
- Interaction: Command Center -> Live Office -> agent inspection -> Command Center preserves the shared snapshot state
- Data mode: no seed fallback

## Live Wiring

The dashboard expects the local API bridge to be running:

```bash
../scripts/start_ai_office_live.sh
```

The API reads/writes only the local warehouse. If the API is offline, the UI shows empty/offline states rather than sample records.
