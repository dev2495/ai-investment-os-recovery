# System stand review — 7 September 2026

Evidence date: 2026-09-07 (Cloud Agent on `github.com/dev2495/ai-investment-os-recovery`).
No runtime code was changed in this pass. Live iMac Tailscale health could not be verified from this VM (MagicDNS does not resolve here). Cursor fetch of `https://devarshs-imac.tail8dd383.ts.net/api/health` returned HTTP 500 without a body.

## One-line verdict

The **live office** Codex accepted on 2 September is a **governed Research Desk on an unmerged branch**, deployed to the iMac under a local release tag. **GitHub `main` is still 25 July 2026** and still shows the old filings tables. That split is why Research Desk “was completed” in Codex and still feels unfinished in the repo, Cursor Cloud, and any UI served from `main`.

Phase 2 Agent OS is a **local increment on top of that desk**, not a finished Living Investment Office, and collaboration/M258 work visible in Codex on 7 September is still in `/private/tmp/aios-agent-os-phase2`, not on `origin`.

## Git topology (authoritative)

| Ref | Tip | vs `origin/main` | Role |
|---|---|---|---|
| `origin/main` | `1147206` (2026-07-25) “Make Charlie and department workflows operational” | — | Default GitHub / Cloud clone. Charlie briefs, GLM UI, iMac backend package **without** Research Desk v1. |
| `codex/research-desk-knowledge-scanners-v1` | `b42cc5d` | **186 commits ahead** | Research Desk v1 + 2 Sep live acceptance docs. |
| `codex/live-agent-operating-system-v1` | `2dcbbce` (2026-09-04) | research-desk **+4 commits** | Phase 2 leases/policy (migrations 256–257). Local-verified, **not live-accepted**. |
| `codex/live-ai-os-research-stack-20260817` | `d764db2` | 174 ahead; **draft PR #2** | Older “company research platform” (Aug 17). Not the latest desk. |
| `codex/operator-workflows-20260725` | `d0ed5c7` | diverged | Options/sector/operator gateway. Not an ancestor of Research Desk v1. |
| `codex/glm-ui-completion` | 1 behind `main` | stale | Merged into `main` except one commit. |
| Codex temp checkout (screenshot 2026-09-07) | `/private/tmp/aios-agent-os-phase2` | **not on origin** | Further Phase 2: `257` already on remote; `agent_collaboration.py`, `phase2-m258.patch` seen only in Codex session. |

Draft PRs on GitHub: #1 Cloud Agent env bootstrap; #2 older research stack. **Research Desk v1 and Agent OS Phase 2 have no merged PR.**

### Why Research Desk feels broken

On **`main`** (this checkout):

- `/research` redirects to `/research/filings`.
- UI is `ResearchFilings.tsx`: filings / special situations / papers / ingest tables over `useResearchIdeas()`.
- Function codes FIL/SPEC/PAPER/ING are all `beta`.
- There is **no** `ResearchDesk.tsx`, no `/research/desk|cases|following|scanners|knowledge`.

On **Codex Research Desk branch**:

- `/research` redirects to `/research/desk`.
- Live codes: RDESK, RCASE, RFOLLOW, RFSCAN, RKNOW.
- Natural-language cases, workstreams, Following, fundamental scanners, knowledge, HTML/PDF reports, Charlie named-case status.

If the iMac is serving the Codex release (`a02ee0f-live` / `e24a1cf` family) you should see the desk. If Cursor/GitHub/`main`/an old LaunchAgent `dist` is what you are looking at, you will see empty beta filings — correctly.

Operator-visible incompleteness **on the live desk itself** (Codex 2 Sep, still open): Wipro Case 12 and Shivalik Case 15 are **evidence-debt packs**, not independent-review/decision-ready; 13 scanner definitions, **zero published**; **zero** approved public Following sources; GLM 5.3 Flash disabled canary; Safari/user acceptance unchecked; after-hours quote labelled delayed, market-hours recheck open.

## What Codex actually completed (by layer)

### A. GitHub `main` (July 2026) — control-plane office

Present: warehouse-backed AI Office UI (no seed), API, MCP, 160+ SQL init files through ~162, Charlie/department workflows, OpenRouter spend gates, Zerodha reconnect UI, iMac backend package (Tailscale Serve, supervisor), execution lock.

Absent: Research Desk v1 surfaces, scanner factory, durable research cases, v11/v13 blueprints in `docs/`, Agent OS leases.

### B. Research Desk v1 (branch `codex/research-desk-knowledge-scanners-v1`)

**Code + tests (1 Sep):** release candidate. Backend ~645–654 passed; UI build; 7 Chrome Research Desk tests; migrations 250–255; Zerodha protected files unchanged.

**Live iMac (2 Sep):** Codex labelled this **live operational Research Desk, ready for operator testing**. Evidence they recorded (not re-verified today):

- SSD mounted, Postgres/Redis healthy, Qdrant running, Tailscale UI/API, `execution_locked=true`.
- Warehouse snapshot: 3 clients, 72 positions, 1,346 agent tasks.
- Wipro Case 12: 7/7 specialists done, independent-review **blocked**, HTML/PDF report v3 served.
- Shivalik Case 15: pypdf extraction working, 31 official sources, 284 facts, **cost-ceiling blocked**, report v5 served.
- Six companies monitored; filing refresh does not reopen terminal review/cost states.
- Charlie warehouse-backed named-case status.

**Not closed:** decision-ready packs, Following publication, scanner runs on NSE/BSE universe, GLM canary, Safari, market-hours quote proof, blueprint-complete declaration.

Sources on that branch: `docs/research-desk/IMPLEMENTATION_STATUS.md`, `RESEARCH_DESK_LIVE_ACCEPTANCE_REPORT_2026-09-02.md`, dated checklist.

### C. Agent OS Phase 2 (branch `codex/live-agent-operating-system-v1`)

Additive on Research Desk tip `b42cc5d`. Codex 4 Sep: **first increment locally verified, not live-accepted**. iMac reported **offline** that day.

Landed on origin:

- M1/M2 partial: exclusive task leases, heartbeats, fencing, office pause/resume/cancel, migration **256**.
- Continuation: migration **257** policy/events/snapshots/output receipts (`2dcbbce`).
- Tests: 678 then 684 passed locally; Chrome synthetic office flow; **zero** live agents migrated; enrollment **opt-in/off**.

Explicitly **pending:** M3 messages/handoffs/committees, M4 Charlie durable orchestration, M5 model fabric, M6 Doctor, M7 skills/routines, M8 full 2D/3D parity, M9 cross-desk acceptance, 24h soak.

### D. Codex session 7 Sep (screenshot, not on GitHub)

Workspace: “AI OS Investment Thesis Workspace”, isolated tree `/private/tmp/aios-agent-os-phase2`.

Observed batches:

1. 11 files / +821 lines including `257_agent_runtime_policy_events_v1.sql` (already on origin as of `2dcbbce`) and policy-test patches.
2. 32 files / +2,213 lines including `phase2-m258.patch` and `_ai_os_runtime/api/agent_collaboration.py` (+279). **`agent_collaboration.py` is not on `origin/main` or `origin/codex/live-agent-operating-system-v1` as of this fetch.**

User asked Codex to complete, report in detail, and **live-commit**. User also said the **iMac is backup** (recovery node), which matches the deploy contract (iMac backend, MacBook operator) and the 4 Sep “do not mutate production while offline” constraint.

Until `git fetch` shows a commit after `2dcbbce` with `agent_collaboration.py` / 258, treat 7 Sep work as **unpushed local Phase 2**, not live.

## iMac / Tailscale (this Cloud Agent)

Documented live endpoints in code: `https://devarshs-imac.tail8dd383.ts.net` (UI) and `:8443` (API). Loopback-only Postgres/Qdrant/Redis/Ollama; Tailscale Serve for UI/API.

This VM is **not on the tailnet**, so it cannot SSH or curl MagicDNS. A proxied GET `/api/health` returned **500**. Do not use that as proof the office is down or up.

**First operator check on the MacBook (read-only):**

```bash
tailscale status | rg -i imac
curl -fsS https://devarshs-imac.tail8dd383.ts.net/api/health
# on iMac:
~/AI_OS_NODE/ai-investment-os/_ai_os_runtime/deploy/imac-backend/bin/aios-imac status
git -C ~/AI_OS_NODE/ai-investment-os rev-parse --short HEAD
git -C ~/AI_OS_NODE/ai-investment-os status -sb
cat ~/AI_OS_NODE/ai-investment-os/.aios-deployed-commit 2>/dev/null || true
```

Compare HEAD to `e24a1cf` / `b42cc5d` / `2dcbbce`. If HEAD is `1147206` or July, the live box is serving **pre-desk** software.

## What is left (ordered by honesty, not blueprint size)

1. **Reconcile three trees:** GitHub `main` vs iMac deployed SHA vs Codex `/tmp` Phase 2. Until that is one line, every “is it done?” answer will conflict.
2. **Merge or stop pretending `main` is the product.** Research Desk cannot be used from GitHub default without merging `codex/research-desk-knowledge-scanners-v1` (or deploying that SHA).
3. **Research Desk operator gates** (still open on 2 Sep live report): Wipro/Shivalik independent review; Following source approval; ≥5 scanners published on real universe; GLM canary + named review; Safari; market-hours quote; one non-held golden case.
4. **Do not relabel task/worker completion as investment-ready.** Phase 2 residual gates file says this explicitly.
5. **Phase 2 remaining:** M3–M9, production migration 256–257 (and 258 if Codex finishes), 24h soak, live Research Desk regression after deploy. Collaboration API is unfinished/unpushed.
6. **Do not merge `operator-workflows-20260725` blindly** into the desk line; histories diverged.
7. **Warehouse/connectors still `[ ]` or `[~]` on v10 checklist** if measuring the full OS: live OHLCV refresh, DCF/SOTP, remote access model, broker connectors as productized MCP, autonomous Charlie loop.

## Recommended next plan (implement later, not this pass)

1. Read-only iMac identity: deployed commit, dirty state, health, which UI `/research` serves.
2. If iMac is on Research Desk SHA: operator-test Wipro/Shivalik in Chrome; do not start paid runs until a bounded plan.
3. If iMac is on `main` or an old `dist`: that is the “desk not working” bug — deploy `b42cc5d` (or later accepted SHA) through existing `aios-imac` path, do not invent a second control plane.
4. Only after SHA agreement: decide whether to merge Research Desk → `main`, then Phase 2 as a follow-on PR, then Codex `/tmp` collaboration/258.
5. Keep Zerodha GET-only and `broker_write_allowed=false`.

## Evidence pointers

- `docs/research-desk/*` on `origin/codex/research-desk-knowledge-scanners-v1` (not on `main`).
- `docs/agent-os-phase-2/*` on `origin/codex/live-agent-operating-system-v1`.
- This Cloud Agent cannot see Codex `/private/tmp/aios-agent-os-phase2`.
