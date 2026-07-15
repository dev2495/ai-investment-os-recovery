---
title: Client Office Control Plane v1
date: 2026-07-15
status: verified
system: AI Investment OS
owners:
  - Charlie Munger
  - Portfolio Manager
  - Data Steward
evidence_class: production_runtime
---

# Client Office Control Plane v1

## Outcome

The Client Office now has one governed lifecycle for new-client onboarding, suitability, account maintenance, manual holding updates, and multi-source holding reconciliation. Existing imported production state was preserved: three clients, six accounts, and 74 position rows. No sample client, holding, market, or broker record was retained.

## Operating Flow

1. Devarsh or Charlie stages a client case with objectives, constraints, horizon, liquidity, risk tolerance, risk capacity, suitability, account scope, and source evidence.
2. Charlie receives a high-risk approval and Client Office inbox item.
3. The generic approval endpoint refuses the case. Only the dedicated resolver can atomically resolve approval and activate the client, account, and suitability review.
4. Portfolio Manager stages account create, update, deactivate, or reactivate requests with evidence. Dedicated human resolution applies the local account change; broker writes are absent.
5. Manual holdings create a dedicated approval and do not alter `portfolio.positions` before evidence-backed human resolution.
6. Data Steward records normalized broker, P2Cursor, algo, or manual source observations and reconciles the latest source snapshot against the latest warehouse snapshot.
7. Reconciliation writes symbol-level source-only, warehouse-only, quantity, and average-price breaks. It never auto-applies a position.

## Production Contract

Migration: `_ai_os_runtime/postgres/init/127_client_office_control_plane_v1.sql`

New tables:

- `portfolio.client_onboarding_cases`
- `portfolio.client_suitability_reviews`
- `portfolio.account_change_requests`
- `portfolio.holding_source_observations`
- `portfolio.holding_reconciliation_runs`
- `portfolio.holding_reconciliation_breaks`

Operating views and function:

- `portfolio.v_client_onboarding_queue`
- `portfolio.v_client_suitability_control`
- `portfolio.v_holding_reconciliation_control`
- `portfolio.v_manual_holding_update_queue`
- `portfolio.run_holding_reconciliation(account_code, source_label, actor)`

API routes:

- `POST /api/client-office/onboarding/stage`
- `POST /api/client-office/onboarding/resolve`
- `POST /api/client-office/accounts/stage`
- `POST /api/client-office/accounts/resolve`
- `POST /api/portfolio/holding-updates/stage`
- `POST /api/portfolio/holding-updates/resolve`
- `POST /api/client-office/holding-observations`
- `POST /api/client-office/reconciliation/run`
- `GET /api/portfolio-office/snapshot`

MCP tools:

- `ai_os_client_onboarding_control`
- `ai_os_client_account_change_control`
- `ai_os_holding_reconciliation_control`

Legacy `ai_os_upsert_client`, `ai_os_stage_holding_update`, and `ai_os_apply_holding_update` now route to the governed API and cannot bypass approval with direct SQL.

## Agent Ownership

- Charlie Munger: final onboarding and suitability approval.
- Portfolio Manager: prepares onboarding, owns account lifecycle and holding review.
- Data Steward: source normalization and reconciliation.
- Portfolio Risk Analyst: reviews material reconciliation breaks.
- Client Reporting Agent: consumes approved client/account scope for draft reporting.

New skills:

- `client_onboarding_governance`
- `client_account_lifecycle`
- `multi_source_holding_reconciliation`

## Terminal

Client Folios at `http://127.0.0.1:5177/?mode=command&workspace=clients` now includes:

- governed client onboarding form;
- onboarding approval queue;
- client registry and live holdings;
- suitability and mandate gap control;
- account maintenance and request queue;
- staged holding approval queue;
- client-book attribution;
- P2Cursor reconciliation;
- normalized multi-source reconciliation.

The UI continues to display broker execution as locked. It is responsive and uses scoped API data with no seed mode.

## Verification

`validate_client_office_control_plane.py` passed seven lifecycle checks:

- stage without activation;
- generic approval bypass blocked;
- atomic client/account/suitability activation;
- approval-gated account maintenance;
- holding book unchanged before approval;
- symbol-level source-only break detection;
- Client Office snapshot visibility.

The validator removed its temporary client, account, position, observations, reconciliation, and proposal records. Production counts returned to three clients, six accounts, 74 positions, zero validation clients, zero validation observations, and zero validation reconciliation runs. Append-only operational audit evidence remains.

Additional gates:

- migration replay passed;
- Python syntax passed;
- UI production build passed;
- MCP protocol listed 161 tools and all three Client Office tools;
- complete Playwright suite passed 83/83;
- WCAG A/AA automation passed all 39 desktop/mobile cases;
- desktop and mobile Client Folios screenshots showed no overlap or horizontal overflow;
- TradingView CDP and local API remained healthy;
- global broker execution remained locked.

## Remaining Work

- Capture retrospective suitability, restrictions, communication preferences, and mandates for Naval, Sanjana, and Tushit. They intentionally show `missing` until reviewed.
- Add complete cash, liabilities, fees, tax lots, realized P&L, and client NAV accounting.
- Add client concentration policies and order-time suitability enforcement.
- Build performance attribution, monthly report review/delivery, and consolidated client action timeline.
- Feed normalized observations automatically from future Zerodha, Dhan, and legacy algo connectors.
- Work and resolve real multi-source break queues; do not auto-apply them.

## Related

- [[AI Investment OS - Institutional Master Blueprint v10.0]]
- [[AI Investment OS - Execution Checklist v10.0]]
- [[2026-07-13-portfolio-office-and-client-folios-v2]]
- [[2026-07-15-capital-allocation-control-plane-v1]]
- [[2026-07-15-governance-and-production-safety-v1]]
