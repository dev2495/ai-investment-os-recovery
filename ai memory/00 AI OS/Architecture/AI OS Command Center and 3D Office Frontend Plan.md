# AI OS Command Center and 3D Office Frontend Plan

Date: 2026-07-10
Status: canonical frontend delivery specification
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Tracking: [[AI Investment OS - Execution Checklist v10.0]]
Primary operator: Devarsh through Charlie Munger
Runtime operator: Jarvis

## 1. Purpose

Build one operating interface with two connected modes:

1. **Command Center**: the dense, data-first workspace for Charlie chat, portfolio work, research, strategies, risk, approvals, and systems health.
2. **Live AI Office**: a navigable 3D office that visualizes the same live agent, task, committee, inbox, and activity data. It is an interaction surface, never a static animation or alternate source of truth.

The UI must make the investment office more usable, not merely more attractive. Every displayed agent state, room metric, task arrow, chart, approval, and message must resolve to a live warehouse/API record with a visible evidence path.

## 2. Product Contract

### 2.1 Main workflows

- Ask Charlie for work, see the interpreted objective, assigned specialists, tool/data use, blockers, approvals, evidence, and resulting widgets.
- Review a client folio without mixing Long-Term, Tactical, Quant, Active Trading, Treasury, Hedge, or Crypto/Commodity books.
- Move from a symbol, position, filing, signal, or strategy to its research, risk, committee, and action records.
- Use the Quant Lab to move ideas through intake, data validation, backtest, optimization, validation, committee, paper monitor, and promotion gates.
- Inspect and route live trading, TradingView, intraday/OI, paper-trade, and execution-safety work.
- Enter an agent room, inspect its real activity, profile, mailbox, tool/model route, output history, and send it an auditable message.
- Enter a committee room, see the live agenda, participants, evidence, dissent, decision, follow-up tasks, and approvals.

### 2.2 Non-negotiables

- No fake counts, seed portfolios, placeholder agent work, or decorative task arrows.
- The 3D office never issues broker or destructive actions directly. It routes to the same reviewed APIs and approval gates as Command Center.
- Desktop data work remains fully usable with the 3D view disabled.
- The browser must remain responsive while a snapshot refreshes, a chart loads, or an office animation runs.
- Every command, message, widget request, and action uses the existing audit/event model.

## 3. Current System Facts

The existing UI is an 8,288-line `App.tsx`. It already reads a rich `LiveSnapshot` contract and must be reorganized rather than discarded.

Current live snapshot/API inputs include:

- `live_office_rooms`, `live_office_agent_activity`, `agent_org_chart`, `agent_departments`, `agents`, and `employee_profiles`;
- `committee_room_summary`, committee items, approvals, and inboxes;
- `agent_messages`, agent mailboxes, comments, tasks, and artifacts;
- `chat_turns`, `widget_intents`, `dashboard_widgets`, and Charlie's chat/action path;
- live portfolio, strategy, market, research, source, model, provider, and risk records.

Phase A uses these current read contracts. Missing read/write fields are added only after a contract test proves the gap; the frontend must not invent an endpoint or use client-side fake state.

## 4. Information Architecture

### 4.1 Global shell

- Persistent left navigation grouped by Executive, Investing, Trading, Research, Risk, Operations, and System.
- Top command bar with Charlie conversation entry, global search, live connection state, source freshness, approvals, and command palette.
- One world toggle: **Command Center** and **Live Office**. Selected entity, time range, and filters survive the switch.
- An evidence drawer opens the relevant source rows, artifacts, messages, tasks, and approval records for any metric or action.
- Mobile uses a data-first Command Center layout; 3D office becomes an optional, reduced-detail overview.

### 4.2 Command Center workspaces

| Workspace | Live decision surface |
| --- | --- |
| Mission Control | Charlie chat, daily brief, inbox, approvals, delegations, live widgets |
| Portfolio Office | Client folios, books, positions, exposure, thesis, drift, attribution |
| Quant Lab | Intake, discovery, backtests, optimization, validation, committee, paper/live gates |
| Trading Desk | Signals, TradingView actions, paper monitors, execution gates, OI/intraday launchers |
| Risk Center | Limits, kill switches, conflicts, concentration, stress, Monte Carlo, drift |
| Research Hub | Theses, filings, news, source documents, special situations, outputs |
| System Health | MCP tools, sources, workers, models, provider policy/readiness, cost, storage |

### 4.3 Live AI Office

The floor contains Executive, Research, Quant, Trading, Portfolio, Data Center, and Committee rooms. Layout is stable configuration; occupants, status, KPIs, tasks, paths, and meeting state come from the snapshot.

Each agent avatar exposes:

- current status, task, workload, and last output;
- a click target opening the real employee profile;
- a message action that uses the existing agent-message API;
- tool/model route, mailbox count, quality/cost history, and evidence links;
- an active pulse only when live activity data says it is working.

The committee room activates from live committee state. Participant positions and a discussion overlay are derived from agenda/message/decision data. It must never stage a meeting that does not exist.

## 5. Frontend Architecture

```text
ai-office-ui/src/
  app/          shell, routing, providers, error boundaries
  config/       department layout, navigation, agent visual metadata
  api/          live contract, snapshot/chat hooks, action clients
  state/        snapshot, UI selection, and chat-thread stores
  office3d/     scene, rooms, avatars, camera, overlay, accessibility fallback
  views/        Mission Control, Quant, Portfolio, Trading, Risk, Research, Health
  components/   shell, data, forms, chat, visualization primitives
  lib/          mappers, formatters, evidence helpers, guards
  styles/       design tokens and responsive styles
```

### 5.1 Technology decisions

- Keep React, TypeScript, Vite, and the existing API client.
- Add React Router for addressable workspaces and browser history.
- Add Zustand only for client UI/snapshot selection state; Postgres remains the state of record.
- Add React Three Fiber, Three.js, and Drei for the 3D office.
- Add Recharts only for standard analytical charts; do not render decision-critical charts in WebGL.
- Keep Lucide icons and the existing terminal-oriented visual language.

### 5.2 Design rules

- Dark, restrained trading-terminal palette with accessible contrast and semantic status colors.
- Dense operational panels, not marketing cards. Numbers use stable monospace alignment.
- Room labels, charts, tooltips, and controls remain readable at desktop and mobile breakpoints.
- Low-poly abstract figures and office furniture, not realistic people or expensive generated avatars.
- No dependency on a 3D asset marketplace for core interaction. The first office is procedural and deterministic.

## 6. Data And Interaction Mapping

| UI need | Authoritative input/action |
| --- | --- |
| Room occupancy and KPI | `live_office_rooms`, department/agent views |
| Avatar state and activity | `live_office_agent_activity`, `agents`, `employee_profiles` |
| Reporting hierarchy | `agent_org_chart` |
| Talk to employee | existing agent-message create/read/triage API; durable `agent.agent_messages` record |
| Committee meeting | committee summary/items, messages, approvals, tasks, artifacts |
| Charlie delegation | chat turns, tool/widget intents, tasks, inbox, approvals |
| Workspace widgets | `dashboard_widgets` and widget-intent materialization |
| Evidence drawer | source lineage, artifacts, task/inbox/message/approval IDs |
| Portfolio / strategy / risk | current snapshot read models and existing action APIs only |

Polling begins at 30 seconds with focused refresh after a user action. A later event stream may replace polling, but only with ordered, replayable events and a snapshot reconciliation fallback.

## 7. Delivery Gates

### Verified Progress: 2026-07-10

- The Command Center and Live Office world toggle is live and uses the same `/api/snapshot` warehouse contract.
- `LiveOffice` is a lazy-loaded React Three Fiber module, keeping the existing Command Center bundle independent from the 3D renderer.
- The office maps 36 configured agents, 10 live rooms, live task/message state, and committee queues from Postgres with no client-side seed fallback.
- The database recovery gap that prevented snapshot reads was closed by applying checked-in migrations `108_strategy_template_library_v1.sql` and `109_long_term_coverage_board_v1.sql`.
- `npm run build` passes. Browser checks confirmed no console errors, a nonblank WebGL canvas, responsive framing at 1440x1000 and 390x844, and a keyboard-accessible employee selector.
- The Live Office mailbox action is audited end to end. Validation message `#61` from Charlie Munger to Risk Agent created task `#294` and inbox item `#379` through the existing agent-message daemon; it has no capital-action permission.
- Gates A through D remain incomplete until the remaining work below is implemented and verified; this is an evidence checkpoint, not a completion claim.

### Gate A: Command Center foundation

- Split `App.tsx` into shell, snapshot mapper, workspace modules, and shared primitives without behavior loss.
- Add addressable routing, world toggle, selection state, loading/error/empty states, and evidence drawer.
- Preserve every existing live action and snapshot refresh behavior.

### Gate B: Mission Control and core workspaces

- Deliver Mission Control, Portfolio Office, Quant Lab, Trading Desk, Risk Center, Research Hub, and System Health against live rows.
- Charlie chat shows delegation, source freshness, approvals, tool intents, and widget materialization.
- Every dashboard action remains audit-backed and approval-aware.

### Gate C: Live 3D Office

- Render procedural rooms, desks, avatars, active-state animation, camera teleport, and an HTML overlay.
- Support keyboard, mouse, reduced-motion, and non-WebGL fallback states.
- Agent selection, employee messaging, committee activity, and evidence links work from the same entities as the dashboards.

### Gate D: Production quality

- Verify nonblank WebGL canvas, correct framing, interaction, and live data at desktop and mobile sizes.
- Measure render performance with full agent/room data and guard unsupported GPUs.
- Verify action routes, errors, reconnect behavior, and stale-data indicators.
- Update Obsidian reports and checklist evidence only after browser/API checks pass.

## 8. Acceptance Criteria

The frontend is complete only when:

- a user can switch between a data-dense Command Center and the Live AI Office without losing context;
- all room, agent, task, committee, widget, and KPI displays are live-data backed;
- a selected agent can be inspected and messaged through a durable, auditable route;
- Charlie can create/review work and materialize widgets through the UI;
- every dashboard workspace operates on real portfolio, strategy, research, trading, risk, and system records;
- a non-WebGL and reduced-motion experience remains usable;
- automated browser checks confirm desktop/mobile layout, no blank canvas, no clipping, and no overlapping control surfaces;
- the UI does not bypass investment, provider, execution, or approval gates.
