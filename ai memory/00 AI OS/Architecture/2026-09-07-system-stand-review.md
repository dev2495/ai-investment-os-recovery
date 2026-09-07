# System stand review — 7 September 2026

Evidence date: 2026-09-07 UTC (Cloud Agent checkout of `github.com/dev2495/ai-investment-os-recovery`).
Reviewer checkout: branch `cursor/system-stand-review-9eb2` at `1147206` (same tip as `origin/main`).
Scope: documentation only. No application/runtime code was changed. Mac runtime scripts were not started.

This note is the vault source of truth for **where the system stands today**, why Research Desk can look unfinished, what Codex completed versus what is leftover, and what must **not** be implemented until live SHA identity is known.

## 1. Where we stand (verdict)

There are **three different products** that people keep collapsing into one sentence:

1. **GitHub `main` / this Cloud clone** — Charlie/department office from **25 July 2026**. Research is still the beta filings terminal (`ResearchFilings.tsx` at `/research/filings`). `ResearchDesk.tsx` does not exist on this tree.
2. **Research Desk v1** — unmerged branch `origin/codex/research-desk-knowledge-scanners-v1` (`b42cc5d`, 2 Sep 2026). Codex live-accepted this on the iMac as **operational and ready for operator testing**, not as investment-decision-ready research.
3. **Agent OS Phase 2** — unmerged branch `origin/codex/live-agent-operating-system-v1` (`2dcbbce`, 4 Sep 2026), **four commits on top of the desk**. Local tests passed; **not live-accepted**. iMac was reported offline in that pass.

If you open GitHub, Cursor Cloud, or any UI built from `main`, Research Desk will not appear. That is expected, not a regression of the 2 Sep live work.

Codex 2 Sep is still the last **written live acceptance** of Research Desk. This Cloud VM **cannot** re-prove that the iMac is healthy today: MagicDNS does not resolve here. A proxied fetch of `/api/health` returned HTTP 500 without a usable body. Treat user reports that “the iMac is live on Tailscale” as plausible operator-side state, not as evidence this agent verified.

## 2. How this review was evidenced

Commands run on 2026-09-07 from `/workspace` (after `git fetch origin`):

| Claim | Source |
|---|---|
| `origin/main` tip | `git log -1 --format='%H %ci %s' origin/main` → `11472064096dd644458d075cc375c39e0fa4246c` 2026-07-25 02:18:22 +0530 |
| Desk / Phase 2 / older stack / operator / glm-ui tips | `git rev-parse` + `git log -1` on each `origin/codex/*` ref |
| Ahead/behind vs main | `git rev-list --left-right --count origin/main...<ref>` |
| Ancestry | `git merge-base --is-ancestor` |
| Desk vs main size | `git diff --shortstat origin/main...origin/codex/research-desk-knowledge-scanners-v1` → **406 files, +97229 / −5069** |
| Routes on desk vs main | `git show <ref>:_ai_os_runtime/ai-office-ui/src/app/{App,destinations}.tsx` |
| `ResearchDesk.tsx` missing on main | `git cat-file -e origin/main:.../ResearchDesk.tsx` → path does not exist |
| Live acceptance text | `git show origin/codex/research-desk-knowledge-scanners-v1:docs/research-desk/RESEARCH_DESK_LIVE_ACCEPTANCE_REPORT_2026-09-02.md` |
| Phase 2 leftover | `docs/agent-os-phase-2/{LIVE_ACCEPTANCE_REPORT,CONTINUATION_LOG_2026-09-04,IMPLEMENTATION_STATUS,RESEARCH_DESK_RESIDUAL_GATES}.md` on `origin/codex/live-agent-operating-system-v1` |
| GitHub PRs | `gh pr list` / `gh pr view` — #1 env-init (draft), #2 older research stack (draft, 100 listed commits), #3 this review (draft) |
| Tailscale from this VM | `getent hosts devarshs-imac.tail8dd383.ts.net` → NXDOMAIN; Python `urlopen` → same |
| Proxied health | Cursor `WebFetch` of `https://devarshs-imac.tail8dd383.ts.net/api/health` → **HTTP 500** |

Codex 7 Sep `/private/tmp/aios-agent-os-phase2` content (collaboration / M258) was recorded by a prior Cloud Agent from a Codex screenshot. This run **re-checked origin only**: `_ai_os_runtime/api/agent_collaboration.py` is **absent** from `origin/codex/live-agent-operating-system-v1`. Treat that work as unpushed unless a later fetch shows it.

## 3. Split-brain git topology

`origin/main` **is an ancestor** of the Research Desk branch, the Phase 2 branch, the Aug 17 research-stack branch, and the operator-workflows branch. Nothing on those lines has been merged back. Default clone therefore cannot see the desk.

```text
1147206  origin/main  (2026-07-25)  Charlie + department workflows
    |
    +-- 174 commits --> d764db2  origin/codex/live-ai-os-research-stack-20260817
    |                     (draft PR #2; 100 commits listed in GitHub UI; not the latest desk)
    |                     |
    |                     +-- 12 more commits --> b42cc5d  origin/codex/research-desk-knowledge-scanners-v1
    |                                               (186 ahead of main; 2 Sep live-acceptance docs)
    |                                               |
    |                                               +-- 4 commits --> 2dcbbce  origin/codex/live-agent-operating-system-v1
    |                                                                 (Phase 2; not live-accepted)
    |
    +-- ... --> d121d23  (2026-08-08 sector ownership — shared with desk)
                    |
                    +-- desk line continues to b42cc5d (18 unique vs operator)
                    +-- operator line continues to d0ed5c7 (29 unique vs desk)
                        origin/codex/operator-workflows-20260725
                        options / sector / MacBook operator gateway
```

### Refs (this fetch)

| Ref | Tip | vs `origin/main` | Role |
|---|---|---|---|
| `origin/main` | `1147206` 2026-07-25 “Make Charlie and department workflows operational” | — | GitHub default and this Cloud checkout. No Research Desk v1. |
| `origin/codex/research-desk-knowledge-scanners-v1` | `b42cc5d` 2026-09-02 “docs(research): record live iMac acceptance” | **0 behind / 186 ahead** | Canonical Research Desk v1 + live-acceptance report. Accepted code before the report commit: `e24a1cf`. |
| `origin/codex/live-agent-operating-system-v1` | `2dcbbce` 2026-09-04 “feat(agent-runtime): snapshot policies…” | desk **+4**; **0 / 190** vs main | Phase 2 leases/policy. Desk is an ancestor. **Not** live-accepted. |
| `origin/codex/live-ai-os-research-stack-20260817` | `d764db2` 2026-08-25 “feat(research): accept entity-first Charlie requests” | **0 / 174** | Older governed research platform. **Ancestor of the desk** (`d764db2` is in desk history). Draft **PR #2** against `main`. |
| `origin/codex/operator-workflows-20260725` | `d0ed5c7` 2026-08-10 “Recover option analytics from stored chains” | **0 / 197** | **Not** an ancestor of Research Desk v1. Merge-base with desk is `d121d23`. Contains OptionsDesk, SectorIntelligence, MacBook operator gateway. |
| `origin/codex/glm-ui-completion` | `027dddb` | **1 behind / 0 ahead** | Stale; `main` has one extra commit (`1147206`). |
| `origin/cursor/cloud-agent-env-init-9eb2` | (PR **#1**, draft) | separate | Cloud Agent environment bootstrap. **Do not mix this review into that PR.** |

Phase 2 commits **not** in the desk branch:

- `7402fef` docs(agent-os): preserve v13 phase two specs and compatibility baseline
- `9dd6c3c` feat(agent-runtime): fence task ownership and expose verified office controls
- `8b9450d` docs(agent-os): record verified increment and remaining live acceptance gates
- `2dcbbce` feat(agent-runtime): snapshot policies and reconcile durable outputs safely

Research Desk **does not have a merge PR**. Merging PR #2 would land the **August** stack (`d764db2`), missing the 12 later desk commits including live acceptance.

## 4. Why Research Desk “doesn’t feel working”

### 4.1 You are probably looking at `main`

On **this checkout / `origin/main`**:

- `_ai_os_runtime/ai-office-ui/src/destinations/research/` contains only `ResearchFilings.tsx`.
- `App.tsx` maps `/research` → `/research/filings`.
- Destinations (all `status: "beta"`): `/research/filings`, `/research/special-situations`, `/research/papers`, `/research/ingest`.
- Empty states in `ResearchFilings.tsx`: “No filings collected”, “No runs”, “No extractions”, “No special situations”, “No papers ingested”. Those tables are wired to `useResearchIdeas()` warehouse rows. A Cloud clone with no warehouse looks empty even when the code is “done” for 2025–07 filings.

On **`origin/codex/research-desk-knowledge-scanners-v1`**:

- `/research` → `/research/desk`.
- Live-marked functions: `RDESK` `/research/desk`, `RCASE` `/research/cases`, `RFOLLOW` `/research/following`, `RFSCAN` `/research/scanners`, `RKNOW` `/research/knowledge` (`status: "live"` in `destinations.ts`).
- UI files: `ResearchDesk.tsx`, `ResearchCases.tsx`, `ResearchDeskNav.tsx`, plus docs under `docs/research-desk/` (absent on `main`).

If the iMac is serving the Codex release (`a02ee0f-live` / code through `e24a1cf`, report commit `b42cc5d`), the operator should see the desk. If Cursor/GitHub/`main`/an old LaunchAgent `dist` is what is open, the filings empty-state is the correct UI for that tree.

### 4.2 Even the live desk is not “research completed”

Codex 2 Sep explicitly refused to call company packs investment-ready. Operator-visible incompleteness **on the accepted live desk**:

| Surface | 2 Sep live record |
|---|---|
| Wipro Case 12 | `blocked` / `independent_review_blocked`; 7/7 specialists complete; 0 running; evidence-debt report v3 (25 Aug 2026); `needs_research` |
| Shivalik Case 15 | `blocked` / `cost_ceiling_blocked`; 1/7 specialists complete; 31 official sources / 284 facts; evidence-debt report v5 (2 Sep); further paid work needs a new cost plan |
| Scanners | 13 definitions present; **0 published/validated**; production scheduling not accepted |
| Following sources | Company monitoring on six names; **0 operator-approved public Following sources** |
| GLM 5.3 Flash | Disabled public-only canary; not daily driver |
| Safari | Human visual/interaction acceptance still open (Chrome/Playwright used) |
| Legacy cases | Mphasis, HCL Technologies, Usha Martin retain historical blockers |
| Valuation | DCF/multiples/SOTP/Monte Carlo stay unavailable when inputs fail the gate; no zero-fill |

So “desk completed” and “I still can’t use research” can both be true: the **software path** was accepted; the **evidence and publication path** was not.

## 5. What Codex completed vs leftover

### 5.1 GitHub `main` (25 Jul 2026) — control-plane office

Present on this tree (high level): warehouse-backed AI Office UI, API, MCP, Charlie/department workflows, OpenRouter spend gates, filings collector UI, iMac backend packaging notes. Execution is supposed to stay locked.

Absent: Research Desk v1 routes/components, scanner factory, durable research-case UX, `docs/research-desk/`, Agent OS leases (migrations 256–257).

### 5.2 Research Desk v1 — 1 Sep RC, 2 Sep live accept

**1 September (release candidate, iMac offline that day):**

- Branch `codex/research-desk-knowledge-scanners-v1`.
- Backend ~645 passed; UI production build; 7 Chrome `research-desk-v1` tests; migrations 250–255 in code; seven protected Zerodha files unchanged.
- GLM 5.3 Flash registered as **disabled** canary with promotion gates; DeepSeek V4 Pro remains lead/review escalation.
- Ledger then marked most milestones `CODE_VERIFIED` / `LIVE_BLOCKED` because SSH/Tailscale to the iMac timed out (last seen 2026-08-30 in that report).

**2 September (live acceptance — historical, not re-verified today):**

- Codex verdict: **operational Research Desk, ready for operator testing**.
- Deployed marker recorded as `a02ee0f-live`; accepted code commit `e24a1cf`; publication commit `b42cc5d`.
- UI `https://devarshs-imac.tail8dd383.ts.net`; API `:8443`; `/api/health` then `ok: true`.
- Postgres/Redis healthy, Qdrant running; SSD mounted; `execution_locked=true`; `broker_write_allowed=false`.
- Warehouse snapshot they recorded: 3 clients, 72 positions, 1,346 agent tasks.
- Backend suite then 654 passed; live asset equality for `dist` claimed.
- Charlie named-case status for Wipro/Shivalik; terminal review/cost states survive filing refresh.

**Still leftover after that live pass** (product/data/approval, not “rewrite the desk”):

1. Independent review / cost plans for Wipro and Shivalik (and any new paid iteration).
2. Scanner publication + real NSE/BSE universe runs (checklist still wants ≥5 built-ins on the real universe).
3. Operator-approved Following source registry.
4. GLM canary on a fixed public packet + named human review (cannot be auto-approved).
5. Safari + operator workflow on the iMac.
6. Market-hours Zerodha freshness (2 Sep check was after hours; delay labelled, not a live tick proof).
7. Several `ACCEPTANCE_CHECKLIST.md` boxes remain unchecked (Obsidian following summaries, scanner lineage, daily brief, replay/idempotency proofs, live permission tests). Prefer the **2 Sep live report** for runtime truth; the checklist still mixes 1 Sep code-only items.

### 5.3 Agent OS Phase 2 — 4 Sep local increment

Branch starts at desk `b42cc5d`. Codex filename `LIVE_ACCEPTANCE_REPORT.md` is **explicitly not production acceptance**.

| Milestone | Status on origin (4 Sep docs) |
|---|---|
| M0 baseline | Partial; live inventory/backup unavailable (iMac offline) |
| M1 identities/workers/leases | Partial; exclusive claims, fencing, controls **local** |
| M2 heartbeats/events/replay | Partial; auth/replay **local** |
| M3 messages/handoffs/committees | **Pending** |
| M4 Charlie durable orchestration | **Pending** |
| M5 governed model fabric | **Pending** |
| M6 Doctor | **Pending** |
| M7 skills/routines | **Pending** |
| M8 2D/3D office | Partial (lease indicators + task panel); Safari/perf pending |
| M9 cross-desk + final acceptance | **Pending** |

Local evidence they recorded: **678** then **684** passed, 1 skipped (restore drill), 178 subtests; Chrome synthetic office flow; migrations **256–257** on disposable DBs only; **zero** live agents migrated; enrollment **opt-in/off**. iMac last seen `2026-09-04T00:03:34.1Z` in that report; SSH/API timed out. Residual research gates were **carried forward unchanged** (`RESEARCH_DESK_RESIDUAL_GATES.md`).

### 5.4 Operator-workflows line (do not treat as desk)

`d0ed5c7` adds options analytics, sector intelligence, and `deploy/macbook_operator/` gateway work that the desk line did not take. Blind-merging it onto Research Desk will fight history (29 vs 18 unique commits after `d121d23`). Plan a later rebase/port of **wanted** files only, after SHA agreement.

### 5.5 Prior-agent note on 7 Sep Codex `/tmp` (unverified here)

A previous Cloud Agent reported Codex working in `/private/tmp/aios-agent-os-phase2` with `agent_collaboration.py` / `phase2-m258.patch` not on origin. This run confirms those files are still missing from `origin/codex/live-agent-operating-system-v1`. Until `git fetch` shows a commit after `2dcbbce` containing them, that work is **unpushed local Phase 2**, not live.

## 6. iMac / Tailscale limits of this Cloud VM

Documented endpoints (from the 2 Sep report, not from a live probe that succeeded here):

- UI: `https://devarshs-imac.tail8dd383.ts.net` (tailnet only)
- API: `https://devarshs-imac.tail8dd383.ts.net:8443`
- Services bind loopback; Tailscale Serve for UI/API
- Vault/runtime on the Mac assume `/Volumes/Devarsh SSD/...` — **do not run** `_ai_os_runtime/scripts/start_runtime.sh` or `start_ai_office_live.sh` from Cloud Agents (`AGENTS.md`)

This VM:

- Is **not on tailnet** `tail8dd383`.
- **Cannot resolve** `devarshs-imac.tail8dd383.ts.net` (`Name or service not known`).
- Cursor WebFetch to `/api/health` returned **HTTP 500**. That may be a proxy/gateway error, an unhealthy process, or a TLS/SNI mismatch. It is **not** a JSON `{ok:true}` and **not** proof the machine is off.

User statement that the iMac is live on Tailscale and the project is running is **not contradicted** by this VM’s DNS failure. It is also **not confirmed**. Do not claim live health, quote freshness, or deployed SHA from this agent.

## 7. What not to implement yet

Do **not** in the next coding pass (wait for iMac SHA + a written plan):

1. Merge Research Desk or Phase 2 to `main` without comparing the **live checkout** to `e24a1cf` / `b42cc5d` / `2dcbbce`.
2. Merge draft **PR #2** as “the desk” — it stops at `d764db2`.
3. Mix this documentation into **PR #1** (`cursor/cloud-agent-env-init-9eb2`).
4. Blind-merge `codex/operator-workflows-20260725` into the desk line.
5. Start Mac Docker/LaunchAgent/runtime scripts from Cloud; they hardcode SSD paths and external volumes.
6. Place live orders, enable `broker_write_allowed`, or add a second quote pipeline. Zerodha stays GET-only.
7. Relaunch paid Wipro/Shivalik specialist/review work without a **new bounded cost plan**.
8. Promote GLM 5.3 Flash or any model route without the named canary review.
9. Publish scanners or Following sources from code; those are operator approval gates.
10. Relabel Phase 2 lease/task completion as investment-ready research (`RESEARCH_DESK_RESIDUAL_GATES.md`).
11. Declare Phase 2 complete: M3–M9, production migrations, 24h soak, and live Research Desk regression are open.
12. Commit secrets, `.env`, broker credentials, or client statements.
13. Implement M258/collaboration from a Codex `/tmp` tree until it exists on a fetched branch.

Warehouse-backed MCP smokes (`smoke_mcp_tools.py`) need local Postgres/Timescale, Qdrant, and Redis. Skip them in Cloud unless those services are actually running.

## 8. Recommended next plan (observe first, implement later)

**Step 0 — identity, on a Tailscale-connected Mac (read-only).** Do this before any merge or deploy:

```bash
tailscale status | rg -i imac
curl -fsS https://devarshs-imac.tail8dd383.ts.net/api/health
curl -fsS https://devarshs-imac.tail8dd383.ts.net:8443/api/health
# on the iMac, if reachable:
git -C ~/AI_OS_NODE/ai-investment-os rev-parse HEAD
git -C ~/AI_OS_NODE/ai-investment-os status -sb
git -C ~/AI_OS_NODE/ai-investment-os log -1 --oneline
cat ~/AI_OS_NODE/ai-investment-os/.aios-deployed-commit 2>/dev/null || true
```

Compare HEAD / deploy marker to:

| SHA | Meaning |
|---|---|
| `1147206` or July | Serving **pre-desk** `main`. Explains empty filings UI. |
| `e24a1cf` / `b42cc5d` / `a02ee0f-live` | Matches 2 Sep Research Desk acceptance family. Operator-test the desk; do not start paid runs. |
| `2dcbbce` or migrations 256–257 applied | Phase 2 code or schema may be on the box; still not live-accepted. |
| Dirty tree / unknown SHA | Stop. Diff before any pull or restart. |

**Step 1 — if the iMac is on the desk SHA:** operator-test Wipro Case 12 and Shivalik Case 15 in Chrome (and Safari). Confirm zero running paid agents. Download existing HTML/PDF. Ask Charlie the named-status prompt from the 2 Sep report.

**Step 2 — if the iMac is on `main` or an old `dist`:** that is the “desk not working” bug. Deploy the accepted desk SHA through the **existing** `aios-imac` path. Do not invent a second control plane.

**Step 3 — only after SHA agreement:** decide GitHub integration order: Research Desk → `main` (or a release branch), then Phase 2 as a follow-on PR, then any Codex `/tmp` collaboration/258 if it is fetched and reviewed. Keep operator-workflows as a separate port.

**Step 4 — leftover product gates** (after the UI you intend is the one on screen): Following approvals, scanner publication, GLM canary, Safari sign-off, market-hours quotes, bounded Wipro/Shivalik plans if more research is worth cost.

## 9. Open GitHub PRs (do not conflate)

| PR | Head | Base | State | Meaning |
|---|---|---|---|---|
| #1 | `cursor/cloud-agent-env-init-9eb2` | `main` | draft | Cloud Agent environment bootstrap. Separate. |
| #2 | `codex/live-ai-os-research-stack-20260817` | `main` | draft | Older research platform (`d764db2`), 100 commits listed / 174 ahead. Not Research Desk v1 tip. |
| #3 | `cursor/system-stand-review-9eb2` | `main` | draft | This documentation-only stand review. |

## 10. Evidence pointers on unmerged branches

Not present on `main`; read with `git show <branch>:<path>`:

- `docs/research-desk/RESEARCH_DESK_LIVE_ACCEPTANCE_REPORT_2026-09-02.md`
- `docs/research-desk/RESEARCH_DESK_RELEASE_REPORT_2026-09-01.md`
- `docs/research-desk/IMPLEMENTATION_STATUS.md`
- `docs/research-desk/ACCEPTANCE_CHECKLIST.md`
- `docs/agent-os-phase-2/LIVE_ACCEPTANCE_REPORT.md`
- `docs/agent-os-phase-2/CONTINUATION_LOG_2026-09-04.md`
- `docs/agent-os-phase-2/IMPLEMENTATION_STATUS.md`
- `docs/agent-os-phase-2/RESEARCH_DESK_RESIDUAL_GATES.md`

This Cloud Agent cannot see the iMac disk, Tailscale peers, or Codex `/private/tmp/aios-agent-os-phase2`.
