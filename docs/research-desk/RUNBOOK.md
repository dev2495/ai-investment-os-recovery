# Research Desk v1 — Operator Runbook

## Preconditions

1. `Devarsh SSD` is mounted and writable.
2. API, Postgres, Redis and Qdrant are healthy.
3. Zerodha login is current when live price-dependent work is requested.
4. `broker_write_allowed=false` remains enforced.
5. A verified critical backup and restore-drill receipt exist before migrations.

## Start research

1. Enter a company name, exchange ticker or ISIN in Charlie or Research Desk.
2. Review resolved identity, mandate, evidence/source plan, privacy boundary and estimated model cost.
3. Explicitly start.
4. Open the returned durable case link to watch sources, extraction, analysis, review, report and decision readiness.

Blocked older cases never prevent a distinct mandate. Use View, Repair or New mandate. Repairs retry the exact failed stage with bounded attempts and preserve prior evidence.

## Quotes

If price freshness is stale/unavailable, reconnect Zerodha through its existing login flow. Do not paste credentials into chat. Research can continue on non-price sections, but current valuation remains blocked.

## Recovery

Run the checked-in critical backup and restore verifier. A successful drill must reproduce vault bytes, Git commit, Postgres inventory and Qdrant collection point counts in disposable storage. Failure evidence stays on the SSD.
