# Research Desk v1 — Implementation Ledger

Status values are `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, or `VERIFIED`. `VERIFIED` requires live data/API/UI evidence; code presence alone is insufficient.

| Milestone | Status | Evidence / remaining gate |
|---|---|---|
| M0 Safe baseline, branch, blueprint, recovery | IN_PROGRESS | Baseline and fresh backup captured; disposable restore drill must pass |
| M1 Generic company and Research Case | IN_PROGRESS | Existing durable proposal/start reused; identity/compatibility APIs and generic-company golden test pending |
| M2 Evidence planner and acquisition loop | IN_PROGRESS | Existing official-source queue reused; pypdf runtime repair and explicit gap records pending |
| M3 Point-in-time facts, quote and calculations | IN_PROGRESS | Existing validated facts/ratios reused; exchange-aware Zerodha freshness anchor and scanner metric lineage pending |
| M4 Specialist workflow and company pack | IN_PROGRESS | Existing agents/reports reused; generic report contract and Wipro/Shivalik acceptance pending |
| M5 Obsidian knowledge graph | IN_PROGRESS | Additive schema/indexer/API/UI/managed-write tests pending |
| M6 Investor/publication following | IN_PROGRESS | Existing feed/news/idea spine reused; source/item/claim/scorecard/triage additions pending |
| M7 Fundamental scanner factory | IN_PROGRESS | Point-in-time schema, deterministic engine, five real built-ins and result lineage pending |
| M8 Charlie and MCP integration | IN_PROGRESS | Compatibility tools and natural-language command tests pending |
| M9 Research Desk UI and truthful office | IN_PROGRESS | First-class routes, bounded states, global polling repair and desktop/mobile QA pending |
| M10 Monitoring, schedules and thesis drift | IN_PROGRESS | Existing company monitoring reused; feed/scanner schedules and Today digest QA pending |
| Production migration/deploy | BLOCKED | Requires passing restore drill and disposable migration replay |
| Final commit/push | NOT_STARTED | Only after live acceptance gates pass |

## Non-negotiable acceptance checks

- [ ] Zerodha remains the only canonical private live quote/instrument/account/options path.
- [ ] Stale or unavailable current price is visible and blocks price-dependent valuation.
- [ ] `broker_write_allowed=false`; no order or external-write capability is enabled.
- [ ] Wipro and a non-held company complete the same durable intake flow.
- [ ] Research work is visible in Today, Workstreams and the Company Dashboard.
- [ ] Knowledge graph retrieval is bounded, scoped and incremental.
- [ ] Human Obsidian edits survive managed-section updates.
- [ ] Followed commentary remains untrusted until primary corroboration.
- [ ] Five fundamental scanners run on the real eligible universe and expose exclusions.
- [ ] Scanner results reproduce from definition version and input fact/quote identifiers.
- [ ] Charlie returns durable ids/links and truthful queued/running/blocked/ready states.
- [ ] API, MCP list, Python tests, UI build, Chrome desktop, Safari desktop and 390px QA pass.
- [ ] Postgres, Qdrant, vault and Git restore drill passes from the current SSD backup.
- [ ] Final report, checklist, Obsidian implementation note and Git commit are current.
