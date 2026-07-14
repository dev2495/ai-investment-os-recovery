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

- Verified 2026-07-15: Holdings Research now includes a live Source Intelligence terminal and Collector Runs rail backed by the hourly research scheduler. The scoped contract exposes 15 registered feeds, 10 current RSS health checks, 16 news runs, 20 filing runs, 24 extraction runs, 100 bounded filings, 80 current news rows, 60 special-situation rows, 80 generated ideas, and 98 output artifacts without seed fallback. The operator can launch the bounded source loop from the workspace; the action refreshes news, NSE/BSE filings, four material-first PDF extractions, strategy discovery, and one agent route while broker execution remains locked. Desktop, mobile, and full-page browser artifacts confirm the dense terminal layout. Evidence: [[2026-07-15-research-intelligence-v1]].
- Verified 2026-07-13: Holdings Research now includes a Long-Term Decision Lab over the existing deterministic Monte Carlo engine. A 19-query scoped contract exposes 46 theses, 16 checklist rows, 16 valuation models, five Monte Carlo runs, 32 research updates, committee state, and artifacts without broad polling. The form blocks unsourced explicit starting multiples, forwards source evidence, and cannot grant capital or broker authority. UI run `#5` completed with no warnings and wrote directly to the external Obsidian vault. Three permanent desktop/mobile/source-gate tests and all 23 WCAG A/AA cases passed. Evidence: [[2026-07-13-long-term-decision-lab-v1]].
- Verified 2026-07-13: Reports now renders ten live schedules and recent run history from a 14-query scoped contract; System Health renders two backup generations, checksum state, Postgres/Qdrant archive sizes, installed schedules, and the passed isolated restore artifact from file-backed recovery evidence. Four permanent desktop/mobile scheduler and recovery tests passed, the 23-case WCAG A/AA gate remained green, and neither route requested compatibility `/api/snapshot`. Evidence: [[2026-07-13-backup-restore-and-scheduled-reports-v1]].
- Verified 2026-07-13: the production root now mounts a compact scoped-only Command Center shell while retaining the legacy function as an unreferenced source comparison. Vite tree-shaking reduced main JS from 464.25 KB to 250.16 KB (46.1%). A full 18-test matrix across every workspace at 1440 x 1000 and 390 x 844 passed with one scoped request per route, zero broad requests, no stale rail, no layout defects, and zero console/page errors. Evidence: [[2026-07-13-scoped-command-shell-v2]].
- Verified 2026-07-13: a reusable deep evidence/action drawer is live across Mission Control tasks/messages/approvals/provider gates, Research committee packets and artifacts, Reports artifacts/worker tasks/source lineage, and the Live Office committee packet. The bounded `/api/evidence/entity/{kind}/{key}` contract whitelists six entity kinds and returns live task, inbox, message, approval, worker, artifact, committee, and lineage relationships without enlarging workspace snapshots. Pending approvals can be approved or rejected with a recorded human identity; the action does not grant capital or broker authority. The expanded 22-test desktop/mobile matrix passed in 20.1 seconds with keyboard open/Escape close, viewport geometry, scoped request counts, and zero runtime/layout errors. Evidence: [[2026-07-13-deep-evidence-and-approval-actions-v2]].
- Verified 2026-07-13: frontend production hardening adds a live generated-at/stale/offline strip to all ten workspaces, render-error boundaries around every workspace and Live Office, evidence-dialog focus trapping/restoration, keyboard labels for actual overflow regions, reduced-motion handling, and an AA contrast palette. Playwright and axe are checked into the UI package with external `/tmp` test output and a four-process runner. All 23 WCAG A/AA automation cases passed across every workspace desktop/mobile, the approval drawer, and both Live Office static fallbacks; the existing 22 responsive/request checks also passed. `npm audit` found zero vulnerabilities. Evidence: [[2026-07-13-frontend-production-hardening-v2]].
- Verified 2026-07-13: Live Office operations v3 separates department focus from workspace navigation, animates the WebGL camera to the selected room, makes room floors directly selectable, and keeps the same interaction available in static mode. The employee inspector now shows current-work detail plus open task, inbox, unread-message, and risk counts. A 14-query `/api/office/snapshot` contract adds 24 priority tasks, 6 open risk events, 2 stale/missing source alerts, and the locked execution state; no broad snapshot or seed fallback is used. Four new browser cases passed, including room routing, mobile interaction, and a nonblank WebGL buffer test; the 23 WCAG and 22 responsive/evidence suites also remained green. Evidence: [[2026-07-13-live-office-operations-v3]].
- Verified 2026-07-13: Reports is independently mounted from `/api/reports/snapshot` (605 KB/0.23 s, 603 production rows, 12 queries). It unifies 164 durable outputs, 27 worker runs, 146 raw artifacts, 180 lineage rows, 5 output gaps, import coverage, chat history, blueprint progress, and execution lock with search/filter, source links, and path copy. Desktop/mobile checks proved one scoped request, no broad request, no stale rail, no clipping/collisions/overflow, and zero console/page errors. Reports closes the last broad-poll route; `/api/snapshot` remains compatibility-only and is no longer requested by the UI. Evidence: [[2026-07-13-reports-v2]].
- Verified 2026-07-13: Trading Desk, Quant Lab, and Risk Center are independently mounted from `/api/trading-quant-risk/snapshot` (228 KB/0.13 s warm, 209 production rows, 18 queries). Live state includes 20 quant/validation/promotion rows, 108 risk checks, 14 TradingView tasks, one signal, committee/paper/drift/limited-live/order state, TradingView CDP, and global execution lock. Safe controls cover model validation, quant analytics, chart-task queueing, manual/paper journals, risk refresh, and guarded kill switch; no broker-write route is exposed. Six desktop/mobile checks proved one scoped request, no broad request, no stale rail, no clipping/vertical pills/collisions/overflow, and zero console/page errors. Evidence: [[2026-07-13-trading-quant-risk-v2]].
- Verified 2026-07-13: Holdings Research and Ideas are independently mounted from `/api/research-ideas/snapshot` (about 319 KB/0.60 s, 322 production rows, 15 queries). The shared model exposes 46 theses, 28 filings, 9 news items, 3 special situations, 64 generated ideas, 51 discovery candidates, 10 dossiers, 73 outputs, and committee state. Ideas includes a durable research/backtest/risk intake with no broker authority. Four desktop/mobile checks proved one scoped request, no broad request, no stale rail, no clipped metadata, no vertical status pills, no collisions/overflow, and zero console/page errors. Evidence: [[2026-07-13-holdings-research-and-ideas-v2]].
- Verified 2026-07-13: Portfolio Office and Client Folios are independently mounted from one scoped `/api/portfolio-office/snapshot` read model (about 196 KB/0.30 s, 313 production rows, 15 queries). The workspace exposes 3 clients, 4 accounts, 71 current positions, 6 investment books, 69 symbol exposures, client-book attribution, cross-book coordination, position readiness, P2Cursor reconciliation, and approval-gated manual holding staging. Four desktop/mobile route checks proved one scoped request, no broad request, no stale right rail, no clipped financial metadata, no row collisions, no horizontal overflow, and zero console/page errors. Evidence: [[2026-07-13-portfolio-office-and-client-folios-v2]].
- Verified 2026-07-13: Mission Control is the second extracted Command Center workspace. Direct `?mode=command&workspace=command` routing mounts `MissionControlWorkspace`, suppresses the broad snapshot and stale right rail, and reads `/api/mission-control/snapshot` (about 204 KB/0.27 s, 167 production rows, 14 bounded queries). Charlie chat, durable delegation, inbox, approval visibility, execution/provider gates, widget materialization, worker launch, and freshness alerts use existing audited APIs. Desktop/mobile checks proved one scoped request, no broad request, zero console/page errors, zero row collisions, and zero horizontal overflow. Evidence: [[2026-07-13-mission-control-v2-scoped-workspace]].
- Verified 2026-07-13: System Health is the first extracted Command Center workspace. Direct `?mode=command&workspace=system` routing mounts `SystemHealthWorkspace`, stops the 7.6 MB global poll, removes the stale broad-snapshot right rail, and uses `/api/system-health/snapshot` (about 83 KB, 209 live rows, 16 bounded queries). Desktop/mobile browser checks proved one scoped request, zero console errors, zero panel overlap, and zero horizontal overflow. Evidence: [[2026-07-13-system-health-v2-and-docker-runtime-recovery]].
- Verified 2026-07-11: the supplied two-world frontend proposal is now an explicit blueprint v10 operating contract. The canonical checklist is synchronized into Postgres as 21 domains and 521 requirements; the live 36-agent registry is authoritative over the historical 16-agent count.
- Canonical blueprint reads are live through `/api/blueprint/summary`, `/api/blueprint/requirements`, `ai_os_blueprint_summary`, `ai_os_blueprint_requirements`, and the Command Center `Blueprint v10 Coverage` panel. Browser checks found zero console errors; desktop/mobile Live Office canvas and overflow checks passed. Evidence: [[2026-07-11-ssd-recovery-blueprint-v10-frontend-contract]].

- The Command Center and Live Office world toggle is live. Every workspace now has a scoped read model; `/api/snapshot` is compatibility-only and unused by the UI.
- `LiveOffice` is a lazy-loaded React Three Fiber module, keeping the existing Command Center bundle independent from the 3D renderer.
- The office maps 36 configured agents, 10 live rooms, live task/message state, and committee queues from Postgres with no client-side seed fallback.
- The database recovery gap that prevented snapshot reads was closed by applying checked-in migrations `108_strategy_template_library_v1.sql` and `109_long_term_coverage_board_v1.sql`.
- `npm run build` passes. Browser checks confirmed no console errors, a nonblank WebGL canvas, responsive framing at 1440x1000 and 390x844, a keyboard-accessible employee selector, and a 23-case WCAG A/AA automation gate.
- The Live Office mailbox action is audited end to end. Validation message `#61` from Charlie Munger to Risk Agent created task `#294` and inbox item `#379` through the existing agent-message daemon; it has no capital-action permission.
- `useLiveSnapshot` now owns the 30-second snapshot poll, reconnect status, and empty/offline reset outside `App.tsx`; existing action handlers still force focused refresh after writes.
- Performance measurement: bounded `/api/snapshot` took 9.20 seconds and returned 7.40 MB. Reports now reads 605 KB in 0.23 seconds; every route is scoped. Deep evidence is loaded only when opened. The hardened main JS is 263.59 KB gzip 71.80 KB; Live Office remains isolated. Next: remaining domain-specific drill-downs, dead-code removal, Live Office room interaction, and production operations gates.
- URL routing is live for the two operating worlds and workspace context. Verified deep link: `?mode=office&workspace=risk` and return route `?mode=command&workspace=risk`.
- The office has an accessible static mode for reduced-motion or unavailable WebGL. Verified static mode removes the canvas and keeps 10 live rooms, 36 employee controls, task inspection, mailbox handoff, and the committee strip. Desktop/mobile static fallbacks pass the checked-in WCAG A/AA automation gate.
- The 3D office now renders deduplicated agent-message links as live handoff lines, priority-colored and counted in the office caption. Department selection focuses the corresponding room in the animated or static world while a separate icon opens its mapped workspace.
- Office agents now use their live character names, color tokens, visual traits, and work state. Hover cards surface the employee identity and current assignment rather than a seed persona.
- Deep evidence drawers now cover Office mailbox items plus Command Center task, approval, long-term committee, output artifact, worker-task, and source-lineage rows. Validation returned all six entity kinds from the live warehouse, including strategy committee `strategy:3`, approval `#14`, artifact `worker_run:27`, and lineage `client_data.source_files:1`.
- Committee strip items now open a live decision packet containing the source view/row, decision, approval, memo reference, and structured evidence, with a second-level deep evidence action. Mobile verification at 390 px found no horizontal overflow for the TATASTEEL strategy review packet.
- Gates A through D remain incomplete until the remaining work below is implemented and verified; this is an evidence checkpoint, not a completion claim. Live Office still needs character/art refinement, direct automated canvas-agent hit testing, richer committee collaboration, and chronological activity playback.

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
