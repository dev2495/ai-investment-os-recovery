# Research Desk v1 — Baseline Audit

**Audit date:** 2026-08-24
**Live host:** `Devarshs-iMac.local`
**Canonical release:** `/Users/devarshthakkar/AI_OS_NODE/releases/a02ee0f-live`
**Starting commit:** `f27b4e9a175381a77c5eef6eb45a8d6495b5bb28`
**Feature branch:** `codex/research-desk-knowledge-scanners-v1`

## Safety boundary verified before implementation

- Private data, raw evidence, reports, Qdrant persistence, database volumes and backups remain on the mounted external `Devarsh SSD`.
- Broker, client and external writes remain disabled. Research is read-only plus governed internal records.
- Zerodha Kite remains the canonical private live-price, instrument, account-position and supported options-data provider. This work consumes its existing tables and does not replace its authentication, Keychain, LaunchAgent, stream or reconnect paths.
- An unavailable or stale quote must block price-dependent analysis or be shown as an explicitly labelled secondary fallback.
- Historical first-party research is contextual evidence and requires fresh primary corroboration for current claims.

## Verified live inventory

| Area | Existing capability | Baseline debt |
|---|---|---|
| Research Cases | Durable proposal, cost plan, explicit start, specialist work, repair, review and report records | Some cases are blocked by extraction/runtime failures; readiness and orchestration completion are inconsistently presented |
| Company research | Reconciled company facts, ratios, evidence and report generation for selected companies | Company dashboard is special-cased; Wipro and Shivalik reports remain incomplete or draft |
| Sources | NSE/BSE/company IR collectors, feed registry, ValuePickr/Substack policy, immutable SSD artifacts | Filing extraction has a recurring wrong-Python failure; only a small fraction of stored filings are extracted |
| Market price | Zerodha live state, minute snapshots, price quotes, instruments, OHLCV and option snapshots | Current session/quotes were stale at audit time; timestamp normalization and exchange-aware quote selection require repair |
| Knowledge | Obsidian note index, note links, vector document registry and Qdrant collections | Indexing is rebuild-oriented; no bounded entity graph, unresolved-link queue or managed-section ledger |
| Following | Provider/source registries, feeds, news items, ideas and company monitoring | No first-class people/source scorecards, source-item claim lineage or idea triage workflow |
| Scanners | Technical/options scanner surfaces and real financial/ratio data for a limited company subset | No separate point-in-time fundamental scanner definition/run/result domain |
| Charlie | Natural-language Research Case proposal/start grammar and durable case links | Fast chat can omit stack context; research/following/scanner/knowledge tool coverage is incomplete |
| UI | Company dashboard, workstreams, filings, Today projection, evidence and reports | Large route-global polling causes long mobile skeletons; following/scanners/knowledge are not first-class research pages |
| Runtime | API, UI, Postgres, Redis, Qdrant and integrated agent-message daemon | External-volume LaunchAgent log permission remains a restart gate; duplicate worker assumptions are misleading |
| Recovery | New SSD critical backup contains Postgres dump, Qdrant snapshot, vault and Git bundle with checksums | Restore drill is being corrected and must pass before migrations are applied |

## Data reality at baseline

- 56 registered companies; 17 verified; many identifiers remain incomplete.
- 12 durable Research Cases across proposed, active, review, blocked and cancelled states.
- 16,031 stored filing rows; extraction coverage remains materially incomplete.
- 413 normalized statement facts across 9 companies, plus a newer validated source-fact/ratio layer for a smaller set.
- Knowledge index contains thousands of Obsidian notes, but SQL/Qdrant freshness and link resolution are not yet aligned.
- Existing live prices were stale at audit time. No valuation may silently treat them as current.

## Baseline user-visible defects reproduced

1. Research initiation can resolve to a dead or ambiguous flow instead of a durable case link.
2. Completed Wipro work is visible in Workstreams but not consistently promoted into the Company Dashboard selector.
3. Shivalik source extraction exposes raw runtime errors and can finish with no validated numerical report.
4. Company pages foreground research operations and gaps instead of a coherent investor report.
5. Closed Charlie and broker surfaces still cause unrelated global polling.

## Backup and rollback boundary

Before schema changes, a fresh critical backup was written to:

`/Volumes/Devarsh SSD/AI OS Data/backups/critical/current`

It includes a PostgreSQL custom-format dump, full Qdrant snapshot, vault copy, Git bundle, inventory and SHA-256 manifest. Migration is blocked until the disposable restore drill passes Postgres, Qdrant, vault and Git restoration checks.

## Audit conclusion

The live stack contains substantial reusable research infrastructure. The correct implementation is additive: repair the shared runtime/quote/report paths, add generic knowledge/following/fundamental-scanner domains, expose bounded compatibility APIs/MCP tools, and make the Research Desk discoverable without replacing the current research, Zerodha or safety systems.
