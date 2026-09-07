# Phase 2 — deployed implementation and acceptance ledger

Date: 7 September 2026. Verdict: **PHASE_2_INCOMPLETE**.

The implemented runtime and operator features below are deployed and testable. This is not a claim that the entire Living Agent OS has passed its definition of done. Required named model-route approval, complete production demonstrations, active-workload endurance, Safari and hardware acceptance remain open. Phase 3 was not started.

## What was delivered

| Milestone | Implemented behavior | Verified boundary |
|---|---|---|
| M1 Runtime | Stable agent identities, role/policy snapshots, separate workers, fenced leases, heartbeats, safe pause/resume/cancel/redirect, receipt-preserving recovery and drain | PostgreSQL regressions and supervised live synthetic canaries; production claim mode remains disabled |
| M2 Events | Typed append-only metadata, scope filtering, commit-ordered replay, reconnect/reset/backpressure and bounded reads | 100 SSE clients; 10,000-event stress; actual Redis restart and PostgreSQL replay |
| M3 Collaboration | Durable messages, acknowledgements, handoffs, room/committee context and validated evidence propagation | Actual isolated PostgreSQL lifecycle tests; complete production specialist demonstration remains open |
| M4 Charlie | Durable objectives/plans, specialist controls, evidence-debt explanations, actual roster summaries and Office navigation | Live sidebar returned HTTP 201, 103 registered identities, zero live leases, observed timestamp and real names without model calls |
| M5 Model Fabric | Versioned bindings, provider contracts, exact identity probes, qualification, named review, explicit fallback and rollback | Local HTTP behavior and API/MCP tests; no live qualified binding was activated |
| M6 Doctor | CLI/API/UI registry, bounded diagnostics, drift evidence and allowlisted repair receipts | Live API/MCP pass; real safety and expired-lease checks pass; backlog check honestly fails |
| M7 Routines | Five versioned routines on existing schedule authority; company-update durable outbox, SSD artifacts and managed Obsidian projection | Company-following monitor enabled; actual stored updates projected. Other four routines remain disabled |
| M8 Office | Shared 2D/3D inspector, real states/connections, safe task controls, model history and reviewed promotion | 16 production-build browser tests plus two focused Charlie tests; six accessibility checks; actual live Office/Charlie smoke |
| M9 Integration | Cross-desk capability/status contracts, source/quote boundaries, release/restore tooling and acceptance ledger | Research Desk loads and preserves evidence debt; all 12 complete live demonstrations are not yet accepted |

## Fixes found by live testing

1. Migration 265 reconciles the existing migration-100 provider gate with fenced task insertion. The narrow zero-budget internal canary exemption does not grant model/provider authority to research tasks. Failed early canaries rolled back safely.
2. Migration 266 restores Doctor registry labels for checks that have never run; they remain `not_run`, not falsely healthy.
3. Office reads are bounded, batched and coalesced. Cold live response measured 1.512 seconds; cached response 8 ms. Partial data is explicitly labelled. A later fresh read had zero query issues; transient timeouts did occur during deployment.
4. Charlie displays actual observed roster data and a direct Office button. Service failures no longer incorrectly blame the model layer. An earlier HTTP 503 was not reproducible in two direct requests and a fresh actual sidebar request; its underlying cause is not proven eliminated.
5. The routine/Doctor daemon now JSON-encodes mutation receipt rows. Previously a successful database update could commit and then appear failed while parsing its plain-text receipt. The final live company dispatch completed with `errors: []` and zero model calls.

## Release and data safety

- Branch: `codex/live-agent-operating-system-v1`, repository `dev2495/ai-investment-os-recovery`.
- Starting commit: `b42cc5d028f37ec2ead6b10296235d19bc9a5fd6`.
- Tested deployed application commit: `f57f686a209ea4431d99106bd0b798db29d04a52`.
- Release root: `/Users/devarshthakkar/AI_OS_NODE/releases/phase2-f57f686`.
- Final documentation-only commit is the Git commit containing this ledger. The final reconciliation receipt records that commit and the live marker without a self-referential hash in this file.
- Migrations 256–266 installed. Fresh format-v2 backup and disposable restore passed before production migration. Latest receipt: `restore-drill-20260907T125701Z-75381`, verified at 13:03:56 UTC; migrations 256–266 replayed twice within a rolled-back rehearsal transaction.
- Rehearsal preserved the vault byte-for-byte, 936 tables, 3 clients, 72 positions, 36,538 artifacts, 17,163 OHLCV rows and 12 Qdrant collections.
- Existing dirty source/release and human vault work were preserved. Previous supervised releases and environment backups remain available for rollback.
- Final deployment build and `IMAC_BACKEND_VERIFIED` passed. Execution remains locked, production claims disabled, and no live broker write was enabled.
- All seven protected Zerodha integration files are unchanged from the starting commit. Keychain/authentication, supervision, subscriptions and the canonical quote pipeline remain intact.
- Git contains code, migrations, runbooks and public implementation evidence—not credentials, private databases, model weights or live SSD research data.

## Verification evidence

| Check | Result |
|---|---|
| Full backend suite | **776 passed; 178 subtests passed; no skips; 18.75 seconds**, including disposable PostgreSQL restore integration |
| UI | 16/16 production-build browser checks; focused roster and service-error checks each passed; TypeScript/Vite build passed, 764 modules |
| Accessibility | Six desktop/mobile checked-panel audits; no serious/critical findings in those checks, not an exhaustive screen-reader certification |
| Dependency audit | Zero production audit vulnerabilities; Three/postprocessing peer warning and deprecated mesh dependency remain recorded compatibility debt |
| Stress | 100 logical agents, four workers, 1,000 exactly-once claims, 10,000 events, 100 durable replay checks; isolated run 1.062 seconds; no paid/model/external writes |
| Live canary | `phase2-canary-20260907T131114Z-986ea6ee3d36`: task 1643, agent 157, leases 3/4, receipt 2; all 16 checks passed; terminal cleanup and disabled claims verified |
| Redis/replay | Actual Redis restart; persisted event replay from cursor 14 through IDs 15–28 to cursor 28 passed |
| API/MCP | Doctor, Routines and Model Fabric: all three GET endpoints HTTP 200/available and all three corresponding MCP overviews registered/available; zero mutations/model/broker calls |
| Doctor | Expired leases: pass, zero. Execution locks: pass. Queue backlog: failed with 296 attention items at the recorded check; no historical tasks were silently cleared |
| Company monitoring | Final bounded dispatch completed, one event, no errors. At subsequent verification 122 managed notes were projected; pending outbox rows remain visible and retryable, not falsely completed |
| Quote safety | Protected integration unchanged and broker writes false; fresh market-hours valuation acceptance remains open |

Live receipts are on the canonical SSD beneath `artifacts/phase2-acceptance/` (`live-20260907.json`, `company-monitor-20260907.json`) and `artifacts/restore-drills/`.

One actual managed-note proof:

- Path under the canonical `ai memory` vault: `00 AI OS/Managed/Company Updates/007927bfe5dc2b6a4b195ec16f74e07784cb991a90b531763e3a02a9c2a692cf.md`.
- SHA-256: `1cb89a562de1789b002fe218ea0b273fcad63a3659f51aa270f96f5e8877cad5`.
- Projection preserves human text outside its bounded managed block; symlink/path escape and duplicate/restart behavior are tested.

## Current acceptance checklist

- [x] Store supplied Phase 2 blueprint/prompt and preserve Research Desk/Zerodha constraints.
- [x] Implement and regression-test the M1–M8 control-plane features described above.
- [x] Verify canonical host, SSD, current release and unrelated dirty work before changes.
- [x] Fresh backup, disposable restore and twice-replayed migrations through 266.
- [x] Deploy through existing LaunchAgent-supervised release path; API/UI build and data invariants pass.
- [x] Live bounded lease/heartbeat/pause/resume/cancel/old-owner rejection/receipt/drain canary.
- [x] Actual Redis restart and durable event replay.
- [x] Live Doctor/Routines/Model Fabric API and MCP checks.
- [x] Enable existing-source company-following monitor and verify real SSD/Obsidian projection.
- [x] Actual Charlie sidebar roster, timestamp and Office link, without a paid call.
- [x] Target-scale isolated stress and browser reconnect/control tests.
- [x] Preserve broker-write prohibition and all seven protected Zerodha integrations.
- [x] Start bounded 24-hour observation collector and schedule a quiet follow-up.
- [ ] Qualify and obtain named approval for an actual model binding; execute live switch/stop/fallback/rollback demos. No paid model was invoked or route auto-promoted.
- [ ] Accept all 12 complete live demonstrations below, including case-aware specialist and handoff evidence.
- [ ] Complete 24-hour active worker/routine endurance. Idle observation is not a substitute.
- [ ] Safari/operator acceptance and actual iMac CPU/GPU/memory/FPS/thermal budgets.
- [ ] Market-hours Zerodha freshness/valuation acceptance.
- [ ] Resolve remaining Research Desk evidence debt and operational backlog through governed workflows.

## Required 12 demonstrations — honest coverage

| Demo | Evidence now | Still required |
|---|---|---|
| 1 Durable agents across restart | Supervised API/UI restart; persistent registry and database | Full named Research Director/Forensic identity, binding, conversation and history receipt |
| 2 Worker death/recovery | Isolated process-death tests; live fencing/lease control canary | Full bounded Research Desk worker-death and Office timeline recording |
| 3 Talk to specialist | Message/context contracts tested | Live cited case-aware Forensic response linked to Wipro task |
| 4 Handoff | Actual isolated DB acknowledgement/accept/return/validate propagation | Full production case lifecycle receipt |
| 5 Redirect | Real-browser primary-only redirect contract and persisted event tests | Production active research-task redirect recording |
| 6 Charlie repair plan | Durable exact-command regressions; real roster sidebar | Full live Wipro specialist repair-plan output with exact blockers |
| 7 Model switch | HTTP qualification/binding/rollback behavior tested | Named approved qualified live route and public-task run |
| 8 Fail closed | Negative adapter/fallback tests | Stop approved live bound route and record blocked/qualified fallback state |
| 9 Doctor | Live safety/lease/backlog checks; negative condition tests | Complete live dead-route/stale-quote/index-lag demonstration set |
| 10 Routine | Real company update creates stored artifact and managed note; duplicate/restart tests | Full end-to-end production duplicate/restart demonstration packet |
| 11 2D/3D truth | Shared inspector, active task/handoff/model state browser checks and rendered 3D pixels | Actual iMac/Safari full-state parity and performance evidence |
| 12 No broker path | Protected-file diff and API/MCP safety tests; live broker authority false | Accepted full tool inventory receipt retained with final demo packet |

## Endurance and remaining operating gates

Read-only collector `phase2-20260907` runs every 60 seconds for 24 hours. Receipt: `artifacts/phase2-soak/phase2-20260907.json`. At the recorded check it had 10 samples, zero failed samples, a 70.66-second maximum gap and zero active worker samples. Its scope is explicitly `runtime_observation_only`; `active_workload_endurance_accepted=false`.

The app follow-up `phase-2-imac-acceptance-follow-up` will inspect completion/failure and stay quiet while nothing actionable changes. It cannot authorize models or upgrade idle observation into active endurance.

Other four routines remain disabled pending their operational activation/acceptance. Model Fabric has no activated bindings. The 1.12 MB lazy 3D vendor bundle and Three peer/deprecation warnings are recorded optimization/compatibility debt; successful Chrome rendering does not establish Safari or thermal budgets.

Research Desk rechecked on 7 September: Wipro case 12 is **blocked**, report 6, with corrected-iteration review debt; Shivalik case 15 is **review**, report 9. These are not decision-ready investment recommendations. Task completion never validates missing financial facts or authorizes capital action.

## Where to test and how to pull

- Open `https://devarshs-imac.tail8dd383.ts.net/firm/office` for 2D/3D agent inspection and task controls.
- Open `/research/desk` for company research and evidence state. Use Charlie's sidebar to ask for the current live roster, then open its Office link.
- Use the existing Models and System destinations for Model Fabric, Doctor and Routines. Disabled/offline/blocked states are intentional truth labels, not simulated working agents.
- Pull branch `codex/live-agent-operating-system-v1` from `https://github.com/dev2495/ai-investment-os-recovery.git` into a fresh checkout. Follow `OPERATOR_RUNBOOK.md` for dependencies and isolated tests. Private machine configuration and SSD data must be provisioned separately; a Git pull alone does not replicate live data or Keychain credentials.

The next material authorization needed is a named qualified model-route choice and bounded public-task budget. Until that and the remaining measured acceptance gates are satisfied, the full milestone cannot honestly be called complete.
