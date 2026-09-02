# Research Desk Live Acceptance Checklist — 2 September 2026

This dated checklist supplements `docs/research-desk/ACCEPTANCE_CHECKLIST.md`. A checked item has live iMac, browser, API, database, artifact or test evidence. An unchecked item is a real remaining data, publication, model-cost or human-acceptance gate.

## Runtime and recovery

- [x] Canonical iMac release `a02ee0f-live` is started and responds over Tailscale.
- [x] `/api/health` reports application and Postgres health.
- [x] Postgres and Redis are healthy; Qdrant is running on loopback.
- [x] External SSD is mounted at `/Volumes/Devarsh SSD` with 786 GiB available.
- [x] Database verification reports 3 clients, 72 positions, 1,346 agent tasks and `execution_locked=true`.
- [x] Critical backup and a dated disposable restore-drill receipt exist.
- [x] UI/API exposure remains tailnet-only with the backend bound to loopback.
- [x] Live checkout and tested UI asset hashes match before final documentation publication.
- [ ] Final Safari operator acceptance is recorded.

## Code, migration and quality gates

- [x] Migrations 250–255 are present; live scanner/tool-registry compatibility and terminal-state repairs were applied.
- [x] Full backend suite passes: 654 passed, 1 skipped, 178 subtests.
- [x] Production TypeScript/Vite build passes: 755 modules transformed.
- [x] Production dependency audit reports zero vulnerabilities.
- [x] Git whitespace validation passes.
- [x] Final live browser console has zero errors and zero warnings.
- [x] Observed live Research Desk, Charlie, Zerodha and report requests return 200/201.
- [x] Local/iMac `dist/index.html` and ResearchCases JS hashes are identical.
- [x] Release code through `e24a1cf` is pushed to the GitHub release branch.
- [ ] Final documentation commit is pushed and the live deployment marker equals that remote head. This is completed in the publication step after this file is committed.

## Zerodha guardrail

- [x] Existing Zerodha scripts, daily-auth flow, Keychain use, LaunchAgent supervision and reconnect behavior are preserved.
- [x] All seven protected Zerodha files retain their accepted hashes and have no release diff.
- [x] Account binding/profile and current daily token are validated without exposing credentials.
- [x] Stream process is running/connected and writes canonical live quote rows/snapshots.
- [x] Provider, exchange/symbol mapping, timestamps, freshness and delay state are visible.
- [x] Delayed/no-recent-tick state is labelled and does not silently become a fresh valuation price.
- [x] `broker_write_allowed=false` remains enforced across auth, stream, warehouse, API/UI and Research Cases.
- [x] Research Desk exposes no place, modify or cancel order action.
- [ ] Recheck a genuinely live/fresh quote during NSE market hours; the 18:25 IST acceptance snapshot was outside market hours and correctly labelled delayed.

## Research intake, workflow and repair

- [x] Company name, ticker and natural-language Research Desk intake render in the live UI.
- [x] Natural-language Shivalik/latest-filings intake resolves the existing entity/case and does not create a duplicate company.
- [x] Research Cases remain durable and visible after service restart.
- [x] Case status, specialist progress, costs, blockers, events and reports are visible from live rows.
- [x] Technical failure blobs are replaced by user-readable stage, impact, stack action and next action.
- [x] Late filing/source refreshes do not reopen terminal independent-review or cost-ceiling states.
- [x] Terminal reconciliation preserves evidence, completed work, failures and cost history.
- [x] Report-delivery repair is isolated from source/model reruns.
- [x] Missing or stale valuation inputs fail closed instead of being inferred or zero-filled.
- [x] Desktop and 390 × 844 browser layouts retain core actions.

## Wipro

- [x] Wipro Case 12 is visible in Research Workstreams and Charlie.
- [x] Seven of seven specialist lanes are complete and zero agents/models are running.
- [x] One high independent-review blocker is visible with a bounded next action.
- [x] Evidence-debt HTML report v3 returns HTTP 200.
- [x] Evidence-debt PDF report v3 returns HTTP 200 as `application/pdf`.
- [x] Case state remains `blocked/independent_review_blocked` after late source refresh.
- [ ] Independent review passes on a new bounded correction iteration.
- [ ] The pack reaches `ready_for_review` or `decision_ready` with all critical evidence/calculation gates passed.

## Shivalik Bimetal

- [x] Shivalik Case 15 is visible in Research Workstreams, dashboard/report surfaces and Charlie.
- [x] The governed `pypdf` runtime extracts the official filings that previously failed.
- [x] The live UI shows 31 official sources and 284 validated financial facts.
- [x] Zero agents/models are running after the approved ceiling was exhausted.
- [x] Two high review/cost blockers are visible with explicit operator actions.
- [x] Evidence-debt HTML report v5 returns HTTP 200.
- [x] Evidence-debt PDF report v5 returns HTTP 200 as `application/pdf`.
- [x] Case state remains `blocked/cost_ceiling_blocked` after late source refresh.
- [ ] Operator approves a new bounded cost plan, if further paid research is desired.
- [ ] Independent review and decision-readiness gates pass.

## Charlie and autonomous monitoring

- [x] Charlie sidebar opens in the live Research Desk.
- [x] Fast stack status is database-backed and reports runtime, safety, graph, monitoring, scanners and Zerodha state.
- [x] A named Wipro/Shivalik status question returns both named cases rather than only a generic recent-case sample.
- [x] Charlie reports exact status, blockers, specialist progress, report version and zero-running-model truth.
- [x] Six followed companies are under monitoring; filing/news changes appear in the current status surface.
- [x] New official filings can be captured/extracted and mapped to the correct company automatically.
- [x] Terminal cases remain stopped when monitoring finds a later update.
- [ ] At least one public Following source is operator-approved; the current source registry has zero active approvals.
- [ ] Daily cited brief publication to Today and Obsidian is accepted with a dated run receipt.

## Research depth and valuation

- [x] The report schema/UI includes business/segments, industry/Porter/supply-demand, TAM/value chain/profit pools, moat, management, financial story, valuation, catalysts/risks and decision sections.
- [x] Evidence-debt sections remain explicitly draft/blocked when evidence is insufficient.
- [x] Report text explains the story behind available numbers and distinguishes missing evidence.
- [x] Valuation price provenance and freshness are visible and fail closed when stale/unavailable.
- [x] HTML/PDF delivery works for both live test companies.
- [ ] Wipro has a fully accepted source pack, complete ratios and decision-grade valuation.
- [ ] Shivalik has a fully accepted source pack and reviewed price/share/forecast inputs.
- [ ] Interactive DCF, multiples, SOTP and Monte Carlo are enabled only for a case whose validated inputs pass every required gate.
- [ ] A complete non-held-company golden case passes independent review end to end.

## Model routing and scanners

- [x] Economical specialist routing, explicit cost estimates, hard ceilings and no-private-egress policy remain enforced.
- [x] GLM 5.3 Flash is registered as a disabled public-only canary with conservative cost ceilings.
- [x] Promotion requires a fixed packet, exact response hash, quantitative thresholds and named human review.
- [x] DeepSeek V4 Pro remains the lead/review escalation route.
- [x] Thirteen scanner definitions are visible to Charlie/the stack.
- [ ] GLM 5.3 Flash completes an approved canary and is promoted by a named human reviewer.
- [ ] At least five scanners are validated, published and run on the real eligible NSE/BSE universe; current published/validated count is zero.
- [ ] Scanner scheduling, replay and entry/exit alerts receive live acceptance.

## Final decision

- [x] The live Research Desk runtime, repair mechanics, report delivery, Charlie named-case status and Zerodha safety contract are ready for operator testing.
- [ ] Research Desk v1 is declared fully blueprint-complete. This remains unchecked because decision-ready company packs, public Following approval, live scanner publication, model canary review and Safari/user acceptance are still open.

The correct release label is: **live operational Research Desk; company evidence and governed publication gates remain**.
