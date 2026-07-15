# Client Accounting, Performance, And Reporting Control Plane v1

Date: 2026-07-15
Status: Production foundation live; source-completeness and external-delivery gates remain open
Canonical architecture: [[AI Investment OS - Institutional Master Blueprint v10.0#42. Client Accounting, Performance, And Reporting Control Plane - 2026-07-15]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]

## Outcome

The AI Investment OS now has a deterministic client accounting control plane over real imported data. FIFO tax lots, sourced cash evidence, NAV completeness, Modified Dietz performance, NIFTY 50 benchmarking, realized attribution, monthly Obsidian drafts, dedicated approval routing, API controls, MCP tools, and Client Folio terminal panels are live.

This release does not invent missing opening cash, historical transactions, prices, fees, taxes, or delivery authority. Incomplete evidence remains visible at account and report level.

## Production Evidence

| Control | Live result |
|---|---:|
| Accounts processed | 4 |
| Real trades processed | 848 |
| NIFTY 50 benchmark observations | 2,572 |
| Broker settlement cash rows | 744 |
| Imported fee rows | 0 |
| FIFO accounts complete | 2 |
| FIFO accounts incomplete | 2 |
| Client-specific July drafts | 3 |
| Pending delivery approvals | 3 |
| External sends | 0 |
| Validation clients/accounts/cash/report rows remaining | 0 |

Sources: `portfolio.v_tax_lot_summary`, `portfolio.v_client_nav_control`, `portfolio.benchmark_observations`, `portfolio.cash_ledger_entries`, `portfolio.fee_ledger`, and `ops.v_client_report_delivery_control` in production Postgres.

## Account Control State

| Client | Account | Trades | FIFO | Matches | Breaks | Realized P&L | NAV state |
|---|---|---:|---|---:|---:|---:|---|
| Tushit | `p2cursor_account_2` | 12 | completed | 2 | 0 | INR -89,384.58 | incomplete: opening cash |
| Naval | `p2cursor_account_3` | 61 | completed | 19 | 0 | INR 724,046.27 | incomplete: opening cash |
| Sanjana | `sanjana_long_term` | 30 | incomplete | 1 | 1 | INR 53,410.50 | incomplete: opening cash |
| Tushit | `tushit_3081282_statement` | 745 | incomplete | 575 | 27 | INR 610,819.77 | source snapshot: INR 10,766,939.34; cash breakdown missing |

Sanjana and the Tushit broker statement remain incomplete because current positions cannot all be reconstructed from the available transaction history. The engine records `transaction_history_for_current_positions`; it does not create artificial opening lots.

## Accounting Contract

- Cash evidence: `portfolio.cash_ledger_entries`
- Fee evidence: `portfolio.fee_ledger`
- FIFO runs: `portfolio.tax_lot_runs`
- Open lots: `portfolio.tax_lots`
- Realized matches: `portfolio.tax_lot_matches`
- NAV: `portfolio.nav_snapshots`
- Benchmark evidence: `portfolio.benchmark_observations`
- Performance: `portfolio.performance_periods`
- Attribution: `portfolio.performance_attribution`
- Delivery governance: `ops.client_report_delivery_queue`

FIFO supports long and short inventory. Derivative lot identity includes symbol, exchange, instrument type, expiry, strike, and option type so contracts cannot be matched only by display symbol. NAV uses a supplied broker snapshot when available; calculated NAV requires complete opening cash and price evidence. Performance uses Modified Dietz and remains incomplete without opening or closing NAV.

## Approval And Safety Contract

Manual cash entries and report delivery each require a dedicated linked approval. Generic approval resolution rejects `client_cash_entry` and `client_report_send`, preventing an approval status change that is not accompanied by the linked state transition. Dedicated resolvers lock and update the proposal and approval atomically.

The July report run is `ops.report_runs.id=26`. Delivery queues `4`, `5`, and `6` are pending approvals `35`, `36`, and `37` for Naval, Sanjana, and Tushit. Every queue uses `manual_review`; there is no recipient, no email or message adapter, no delivery timestamp, and no external send.

## User Surfaces

Client Folios now exposes:

- NAV and cash evidence with explicit missing inputs
- Account performance and NIFTY 50 comparison
- FIFO run, lot, match, realized P&L, and break coverage
- Realized attribution
- Approval-gated manual cash staging
- Cash approval queue
- Client report delivery queue
- Deterministic accounting recalculation

The central Approval Board routes client onboarding, account changes, holdings, cash entries, and report delivery through dedicated resolvers. It cannot use the generic route for those stateful decisions.

MCP now exposes 164 tools, including `ai_os_client_cash_ledger_control`, `ai_os_client_accounting_run`, and `ai_os_client_report_delivery_control`.

## Validation Evidence

The deterministic numerical validator passed eight checks:

| Check | Expected and observed |
|---|---|
| Accounting run | completed |
| Lot coverage | complete |
| Position breaks | 0 |
| FIFO matches | 2 |
| Realized P&L | 560 |
| Remaining quantity | 3 |
| Open cost basis | 360 |
| Modified Dietz return | 60% |

The fixture was buys of 10 at 100 and 5 at 120 followed by a sale of 12 at 150. The validator removes all fixture rows after checking production constraints.

Additional release gates passed: migration 128 replay with `ON_ERROR_STOP`; Python compilation; 164-tool MCP protocol/read smoke; API control reads; dedicated approval bypass rejection; atomic cash and report decisions; production TypeScript/Vite build; 83/83 complete Playwright checks; 39/39 desktop/mobile WCAG A/AA checks; nonblank WebGL office rendering; external-storage verification; live API/database health; UI HTTP 200; Ollama HTTP 200; and TradingView CDP HTTP 200. Final production residue checks returned zero validation clients, accounts, cash rows, and report rows, zero non-pending delivery rows, and zero delivered rows.

## Open Gates

1. Capture source-backed opening cash, liabilities, accrued income, and payables for every account.
2. Import missing historical transactions and opening lots for Sanjana and the Tushit broker statement.
3. Import explicit brokerage, taxes, duties, and other fees. The live fee ledger currently has zero rows.
4. Schedule recurring NAV and cash snapshots so multi-period returns are meaningful.
5. Add sector, factor, strategy, and book attribution beyond current realized instrument attribution.
6. Build a reconciled period-over-period portfolio change narrative.
7. Upgrade Markdown drafts into client-ready HTML/PDF presentation with review annotations.
8. Add an approved delivery adapter only after recipient, channel, consent, audit, and revocation controls exist.
9. Complete retrospective suitability, mandate, restriction, and communication evidence for imported clients.

## Decision

Use this control plane as the only client accounting and reporting foundation. LLM agents may explain, challenge, and draft from its evidence, but they must not calculate or overwrite accounting truth. Client reports remain drafts until a named human approves each client-specific output, and approval alone does not authorize external delivery.
