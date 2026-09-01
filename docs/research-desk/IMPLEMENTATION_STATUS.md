# Research Desk v1 — Implementation Ledger

**Evidence date:** 1 September 2026
**Release branch:** `codex/research-desk-knowledge-scanners-v1`

Status meanings:

- `CODE_VERIFIED`: implemented and covered by the current checkout's automated tests/build.
- `INTEGRATED_CODE`: existing stack surface is wired into this milestone and regression tests pass, but this pass did not prove its full production dataset.
- `LIVE_BLOCKED`: requires the canonical iMac, authenticated browser, live Postgres/SSD/Zerodha state or a deliberate human approval.
- `NOT_STARTED`: no trustworthy implementation evidence.

| Milestone | Code status | Production acceptance | Evidence / remaining gate |
|---|---|---|---|
| M0 Safe baseline, blueprint and recovery | CODE_VERIFIED | LIVE_BLOCKED | Supplied blueprint and master prompt match stored files byte-for-byte; full backend/build/browser/audit gates pass. Canonical iMac release identity, backup and disposable restore remain unverified because SSH timed out. |
| M1 Generic company and durable Research Case | CODE_VERIFIED | LIVE_BLOCKED | Natural-language company extraction, exact exchange/symbol navigation, distinct mandates and durable case contracts have tests. Wipro and Shivalik still need one authenticated production replay. |
| M2 Evidence planner and acquisition loop | INTEGRATED_CODE | LIVE_BLOCKED | Source jobs are bounded/idempotent and use the governed external-SSD PDF runtime; UI errors are actionable and technical detail is redacted. The iMac runtime and real Shivalik filings must be replayed. |
| M3 Point-in-time facts, quote and calculations | CODE_VERIFIED | LIVE_BLOCKED | Valuation consumes the canonical Zerodha research-price view and now fails closed on stale websocket heartbeat/quote state while exposing provenance and delay. Live authenticated quote/share-count evidence remains required. |
| M4 Specialist workflow, valuation and report | CODE_VERIFIED | LIVE_BLOCKED | Existing seven specialists, synthesis/review gates and deterministic valuation contracts remain intact. Report-only repair can verify/re-render/rebuild delivery without rerunning sources or paid analysis. A live approved pack and rendered PDF must be checked. |
| M5 Obsidian knowledge graph | INTEGRATED_CODE | LIVE_BLOCKED | Existing managed-note/graph contracts pass the regression suite; no external-vault write was attempted while the canonical host was unavailable. |
| M6 Following and idea intake | INTEGRATED_CODE | LIVE_BLOCKED | Existing followed-source/update-feed/idea surfaces remain wired into Research Desk and independent UI loading states pass. Live scheduler, dedupe and current feed receipts remain required. |
| M7 Fundamental scanner factory | CODE_VERIFIED | LIVE_BLOCKED | Four safe executable templates, copy-to-workspace idempotency, direction-aware scoring, deterministic validation, persistent publish approval and explicit run confirmation are tested. Real NSE/BSE universe runs remain approval/live-data work. |
| M8 Charlie and model routing | CODE_VERIFIED | LIVE_BLOCKED | URL-led false intake is fixed; current-stack fast status is warehouse-backed. GLM 5.3 Flash is a public-only disabled canary with cost, spend, packet, structured output and named human-review gates; DeepSeek V4 Pro remains lead/review escalation. No canary spend or promotion was performed. |
| M9 Research Desk UI | CODE_VERIFIED | LIVE_BLOCKED | Production bundle builds; seven real-Chrome tests cover desktop, 390 px, independent states, failure repair, report delivery and GLM promotion. Production Chrome/Safari and deployed asset equality remain unverified. |
| M10 Monitoring and thesis drift | INTEGRATED_CODE | LIVE_BLOCKED | Existing company-monitoring/update-feed surfaces and regression tests pass. Live filing/news refresh, materiality, thesis-drift and idempotency receipts remain required. |
| Zerodha guardrail | CODE_VERIFIED | LIVE_BLOCKED | Seven protected scripts/services are byte-for-byte unchanged; no parallel quote pipeline or broker write was added. Live stream/login/reconnect health needs the iMac. |
| Dependency/security gate | CODE_VERIFIED | — | `npm audit` and `npm audit --omit=dev`: zero vulnerabilities. Focused changed-line credential scan found no private keys or common token forms. |
| Final commit/push | VERIFIED | — | The tested release candidate is committed and pushed to the named origin branch; the delivery response records the final Git SHA and remote comparison. |
| Canonical iMac migration/deploy | — | LIVE_BLOCKED | Tailscale reported the iMac peer `Online=false` (last seen `2026-08-30T05:55:45.1Z`), and `devarshs-imac.tail8dd383.ts.net:22` timed out on 2026-09-01. No production mutation or deployment claim was made. |

## Model operating policy

- Public Research Case specialists may use the selected `openrouter_research_fast` daily-driver route.
- GLM 5.3 Flash can become that route only after a cost preflight, explicit spend approval, fixed public packet canary and named human citation/numeric review bound to the exact response hash.
- Minimum promotion scores are citation accuracy 90, numeric accuracy 95 and zero unsupported claims.
- DeepSeek V4 Pro remains the lead/review escalation.
- Every paid Research Case run remains separately preflighted after promotion.
- OpenRouter calls require ZDR and `data_collection=deny`; private data, external writes and broker writes remain denied.

## Verified release commands

```text
python -m pytest _ai_os_runtime/tests -q
645 passed, 1 skipped, 178 subtests passed

npm run build
passed

npx playwright test tests/research-desk-v1.spec.ts --workers=1
7 passed

npm audit
found 0 vulnerabilities

npm audit --omit=dev
found 0 vulnerabilities

pglast parse migrations 250, 251, 252
passed
```

## Release decision

The branch is a tested release candidate and is safe to commit/push. It is **not yet a production-accepted Research Desk**: the canonical iMac, migrations, external-SSD PDF runtime, live data, human model approval and authenticated browser flow have not been verified in this pass.
