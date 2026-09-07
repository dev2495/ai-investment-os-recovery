# Research Desk completion gap — 7 September 2026

Blueprints used:

- **v13.0 Living Investment Office** (4 Sep 2026, on `codex/live-agent-operating-system-v1`) — current *target architecture*. Says the Research Desk **platform is operational**; remaining items are **content and operator gates**, not a rebuild.
- **v11.0 Institutional Master Blueprint** (24 Aug 2026, on `codex/research-desk-knowledge-scanners-v1`) — still the *research product contract*: §10 Full research desk, §33.3 definition of done, Phase 2 Wipro golden path.
- **Research Desk v1 acceptance checklist** + **2 Sep live checklist** — release gates with dated evidence.
- **Institutional Company Research Standard** — what a *complete company pack* is.

Do not mix **completing Research Desk** with **completing the whole OS**. v13’s next phase is Agent OS / Charlie / Model Fabric. That is a different vertical.

## Two different “done” lines

| Label | Meaning | Status 7 Sep 2026 |
|---|---|---|
| **Platform operational** (v13 §2.2) | Durable cases, intake, official sources, extraction, specialists, fail-closed valuation, HTML/PDF, monitoring primitives, scanner *definitions*, Charlie named-case status, live Chrome, Zerodha GET-only | Codex live-accepted 2 Sep on iMac. **Not on GitHub `main`.** |
| **Research Desk v1 blueprint-complete** | Every M0–M10 item in `docs/research-desk/ACCEPTANCE_CHECKLIST.md` plus Zerodha/cross-cutting gates, Wipro + one non-held golden path, user Safari/desktop acceptance | **Not done.** Master checklist still has most live-evidence boxes open; 2 Sep only closed *runtime/repair* boxes. |
| **Decision-ready company pack** (v11 §10.4, Research Standard) | Cited IC memo, 10y statements, ratios, DCF/reverse DCF/multiples/SOTP when inputs pass, red team, committee, monitoring, reproducible HTML/PDF | **Not done.** Wipro Case 12 and Shivalik Case 15 are **evidence-debt**. |
| **Whole investment OS** (v11 Phases 3–10 / rest of v13) | TradingView, quant factory, options, macro, portfolio OS, execution | **Out of scope** for “finish the desk.” |

A finished specialist run or a 200 HTML report **does not** mean the case is complete (v11 §10.1).

## What v13 still lists as Research Desk backlog

From v13 §2.2 (canonical remaining gates):

1. Wipro independent-review evidence debt
2. Shivalik cost/evidence debt
3. First approved scanner publication and live NSE/BSE universe runs
4. First approved public Following sources
5. Approved paid-model canary and named review (GLM 5.3 Flash)
6. Fresh market-hours Zerodha quote acceptance
7. Safari user acceptance

## What v11 still requires for a *complete* desk

### Definition of done §33.3

- Missing evidence creates tasks (gap loop)
- Financials reconcile
- Market price and valuation are current
- Every material claim has a source
- Red team and committee are recorded
- Monitoring reopens stale cases
- Reports reproduce from source manifests

### Phase 2 exit gate (§36) — Wipro golden path

Complete source acquisition, PIT facts, cash-flow and share reconciliation, price and valuation, industry/TAM/moat, governance/forensics, scenario and red team, committee and report, continuous monitoring.

**Exit:** fully reproducible **decision-ready Wipro** with no critical missing data.

That gate is **failed today**: Case 12 is `blocked/independent_review_blocked`.

### Product contract §10 (still incomplete vs live packs)

Workspace depth: overview with fair-value range; 10+ year statements; moat with quantitative evidence; forensics; DCF/reverse DCF/SOTP/Monte Carlo only on validated inputs; committee minutes; version diffs.

Outputs still missing as *accepted* artifacts: financial model workbook, evidence appendix as IC-grade, red-team memo, committee minutes, client-safe summary, monitoring checklist with thesis-break conditions.

### Following and scanners (v11 §11 / v13 §25–26)

Following: ValuePickr/Substack/etc. as untrusted commentary → idea cards, never facts. **Zero public sources operator-approved** on 2 Sep.

Scanners: ≥5 published, point-in-time, real universe, schedule/replay/alerts. **13 definitions, 0 published.**

## Ordered work to actually complete the desk

Do this **on the Research Desk SHA** (`b42cc5d` / iMac `a02ee0f-live`), not on GitHub `main`. Confirm iMac `HEAD` first.

### Gate 0 — Identity (operator, ~hours)

1. Prove iMac deployed commit equals `e24a1cf`/`b42cc5d` (or a later accepted SHA), not `1147206`.
2. If serving `main`, deploy the desk branch through existing `aios-imac` — the desk cannot be completed from July UI.
3. Merge `codex/research-desk-knowledge-scanners-v1` to `main` **after** live identity is confirmed (or keep `main` protected and tag the live SHA). v11 Phase 0 still wants a tagged live commit + CI.
4. Safari hard-refresh acceptance on the live UI (2 Sep left this open).
5. NSE market-hours quote: provider, mapping, freshness; valuation still fail-closed if stale.

### Gate 1 — Golden cases (the real “desk complete” work)

**Wipro Case 12**

- Bounded correction iteration to clear independent review (do not spend blindly).
- Close critical evidence: latest price, diluted shares, OCF, capex, net cash, guidance, peers (v11 §10.3 example).
- Ratios + cash-flow/share reconciliation.
- Enable interactive DCF/multiples/SOTP/MC **only after** inputs pass gates.
- Red team + committee recorded; readiness `ready_for_review` then `decision_ready`.
- Reproducible HTML/PDF from source manifest.

**One non-held company** (v11 + 2 Sep checklist)

- Same intake contract as Wipro, end-to-end independent review. Shivalik is **not** this golden path until cost ceiling and review pass.

**Shivalik Case 15** (optional until Wipro golden)

- Operator must approve a **new bounded cost plan** before more paid work (`cost_ceiling_blocked`).
- Then independent review + decision-readiness.

### Gate 2 — Publication surfaces

- Approve ≥1 public Following source; prove feed → idea card → Today/Obsidian without treating commentary as fact.
- Dated cited daily brief to Today + Obsidian (M10).
- Validate, publish, and run ≥5 fundamental scanners on real eligible NSE/BSE universe; then schedule/replay/alerts.
- Scanner result → research case; followed item → idea card (M9).

### Gate 3 — Model canary (human, not code)

- Approved GLM 5.3 Flash public packet canary.
- Named reviewer: citation ≥90, numeric ≥95, zero unsupported claims, bound to response hash.
- Promote only `openrouter_research_fast`; DeepSeek V4 Pro stays lead/review; every paid run still preflighted.
- ZDR + `data_collection=deny` remain.

### Gate 4 — Close the *live* boxes the master checklist still treats as pending

The 1 Sep master `ACCEPTANCE_CHECKLIST.md` still has almost every M0–M10 live-evidence item `[ ]`. 2 Sep **supersedes** several (migrations 250–255 applied, pypdf, Chrome, restart durability, named Charlie status). Remaining *honest* live work after Gate 0–3:

- Cross-surface ID reconciliation (Postgres/API/MCP/Desk/Today/Dashboard)
- Evidence plan versioning + reuse/dedup traces
- Thesis-drift: materiality, reopen review **only** on thesis-break
- Idempotency: same filing does not duplicate tasks/alerts/notes
- RLS / no cross-client leakage tests
- Restore drill current with post-desk schema
- Deployed asset hash = accepted commit
- Vault writeback of this ledger without overwriting human notes

### Explicitly not required to “finish the desk”

- Agent OS M3–M9 (messages, Doctor, Model Fabric, 24h soak) — v13 next *office* phase
- Codex `/tmp` `agent_collaboration.py` / M258
- Merging `operator-workflows-20260725` (diverged)
- TradingView desktop control, quant factory, options desk, live orders
- Rebuilding Research Desk UI from `main`

## Suggested sequence (implementation later)

1. iMac SHA + Safari + market-hours quote  
2. Merge/tag desk branch so GitHub matches live  
3. Wipro evidence iteration → independent review → decision-ready  
4. One non-held golden case  
5. One Following source + five scanners published  
6. GLM canary if you want cheaper specialists  
7. Only then tick “Research Desk v1 blueprint-complete”

Until step 3, the honest label stays: **live operational Research Desk; company evidence and governed publication gates remain.**
