# Deep Evidence And Approval Actions v2

Date: 2026-07-13
Status: verified implementation checkpoint
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Frontend: [[AI OS Command Center and 3D Office Frontend Plan]]

## Result

The Command Center and Live Office now share a reusable evidence drawer backed by a bounded production API. It drills from visible operating rows into durable task, inbox, message, approval, worker-run, committee, artifact, and source-lineage records without adding data to the 30-second workspace snapshots.

## API Contract

- Route: `GET /api/evidence/entity/{kind}/{key}`.
- Whitelisted kinds: `agent_message`, `task`, `approval`, `committee`, `artifact`, and `lineage`.
- Numeric kinds reject non-integer IDs. String keys are escaped and only used in fixed, whitelisted queries.
- Every relationship query is bounded; the browser cannot choose a table, view, or column.
- Live smoke records: message `94`, task `262`, approval `14`, committee `strategy:3`, artifact `worker_run:27`, and lineage `client_data.source_files:1`.

## Operating Surfaces

- Mission Control: message, task, provider-gate, and approval rows.
- Research: long-term committee packets and research/strategy artifacts.
- Reports: output artifacts, worker tasks, and source-lineage rows.
- Live Office: second-level evidence action from the committee decision packet.
- Approval drawers expose explicit approve/reject actions for pending records. The API records `Devarsh` as the human decider; capital allocation, committee final decisions, and broker execution remain independently gated.

## Verification

- TypeScript and Vite production build passed.
- Main JS: 259.32 KB, gzip 70.50 KB. Live Office remains lazy-loaded.
- Direct live-warehouse checks passed for all six entity kinds.
- API, Postgres, UI, Ollama, agent daemon, and TradingView CDP were restarted through the LaunchAgent runbook and returned healthy.
- Full Playwright matrix: 22/22 passed in 20.1 seconds.
- Drawer tests covered keyboard Enter opening, Escape closing, pending-decision visibility without mutation, artifact and lineage navigation, desktop/mobile viewport geometry, one scoped workspace request, zero broad requests, and zero console/page errors.
- Screenshots: `/Volumes/Devarsh SSD/AI OS Data/artifacts/browser-verification/2026-07-13-evidence-actions-v2`.

## Blueprint Registry

- Sync run: `blueprint-v10-deep-evidence-actions-v2-20260713`.
- Checklist SHA-256: `8d326c8f341f109c1c3db1d8a15e24cebf28985762a8339702f0d3fae5fa37ce`.
- Coverage: 21 domains, 522 requirements, 50 done, 175 partial, 297 planned, zero seed rows.

## Remaining Work

- Add position, cross-book conflict, thesis, filing, signal, model-validation, order-intent, and risk-check evidence adapters.
- Add specialized committee decision forms rather than treating approval resolution as the final committee decision.
- Add focus trapping, automated accessibility rules, stale-data timestamps, and route-level error boundaries.
