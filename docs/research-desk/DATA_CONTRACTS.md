# Research Desk v1 — Data Contracts

## Systems of record

- **Postgres/TimescaleDB:** entities, identifiers, facts, lineage, research state, tasks, approvals, scanners, following, decisions and audit.
- **External Devarsh SSD:** raw documents, extracted text, screenshots, Parquet, report HTML/PDF, large artifacts, backups and governed runtime assets.
- **Obsidian:** human-readable memory, research narrative, decisions and links. Generated content may update only managed blocks.
- **Qdrant:** scoped semantic retrieval. It never becomes numerical or transactional truth.
- **Redis:** transient queue/cache/lease acceleration only.

## Truth layers

Every material output is one of:

1. `fact` — primary/authorized evidence plus deterministic normalization and accepted validation;
2. `management_guidance` — attributed issuer statement, not a system forecast;
3. `external_estimate` — lawfully sourced and labelled;
4. `model_scenario` — explicit formula, inputs, version, as-of and uncertainty;
5. `analyst_opinion` — attributed interpretation with supporting and disconfirming evidence;
6. `commentary_untrusted` — followed article/post/thread that cannot promote itself to fact;
7. `missing` or `not_computable` — exact absent/incompatible inputs, never zero-filled.

## Current market price contract

- Primary provider: existing Zerodha Kite read-only integration.
- Selection key: exchange plus canonical symbol/instrument mapping.
- Required fields: provider, provider symbol, canonical symbol, exchange, instrument token/type, price, exchange/trade timestamp, receipt timestamp, source mode, delay and freshness state.
- `fresh`: within the exchange-calendar-aware threshold.
- `delayed`: received and labelled as delayed but still inside the configured analytical tolerance.
- `stale`: beyond threshold; cannot anchor current valuation.
- `unavailable`: no qualified quote; current price-dependent results are blocked.
- `secondary_fallback`: only when a separately authorized/licensed source is configured, and always labelled.
- No price parsed from agent prose is a market fact.

## Point-in-time contract

Every fact/metric/run retains event/effective date, publication time, capture time, `known_at`/availability time, source version/hash, parser/normalizer/formula revision, currency/unit/scale, period, consolidation/scope, restatement status, verification state and input lineage. Scanner and valuation inputs with `known_at > as_of_at` are rejected.

## Privacy and action contract

- API scope and actor are derived from validated server context, not trusted from arbitrary client JSON for new v1 domain writes.
- Private/client-private artifacts remain on the mounted SSD and are never sent to public model routes.
- Public-document cloud extraction may run only through the existing model router and approved cost/privacy preflight.
- Research Desk cannot place, stage or authorize a broker order.
