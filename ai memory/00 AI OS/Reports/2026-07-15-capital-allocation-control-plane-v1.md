# Capital Allocation And Risk Budget Control Plane v1

Date: 2026-07-15

Blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]

Checklist: [[AI Investment OS - Execution Checklist v10.0]]

## Delivered

- Policy proposals and per-book capital/risk rules with database constraints.
- Real current client/book allocation read model for Naval, Sanjana, and Tushit.
- Legacy percentage defaults explicitly labeled `legacy_unverified`.
- Independent allocation drift, liquidity coverage, and 10-day VaR-budget analysis.
- Advisory target-notional and rebalance previews with no order authority.
- Capital Allocation Committee review and separate Devarsh approval routing.
- Scoped API, four MCP tools, and responsive Capital Allocation terminal.
- Validation scripts for client/book completeness, 100% allocation totals, and safety locks.

## Live Production State

| Metric | Value |
|---|---:|
| Active clients | 3 |
| Active investment books | 6 |
| Client/book control rows | 18 |
| Operator policies | 0 |
| Clients requiring policy | 3 |
| Analysis runs | 0 |
| Committee reviews | 0 |
| MCP tools | 156 total, 4 capital-specific |
| Global broker execution | Locked |

No policy was inferred from the old 80/10/5/3/2/0 allocation defaults. Current production state contains only observed positions and untrusted legacy reference values.

## Workflow And Authority

1. Devarsh enters targets, ranges, and risk budgets for all six books.
2. Capital Allocation Agent creates the proposal, task, and Portfolio Risk Analyst inbox item.
3. The analysis compares real book positions with the latest institutional client-risk run.
4. Coverage, liquidity, and risk-budget failures block committee approval.
5. Charlie may record committee reject, revise, defer, or approval recommendation.
6. Approval recommendation creates a separate pending Devarsh approval.
7. Policy approval does not authorize a rebalance, capital transfer, or broker order.

## Real-Data Gate Proof

A temporary validation-only policy used Naval's real INR 4,978,708.50 gross invested exposure. The latest institutional risk evidence covered 70.95635344%, below the required 80%. The run was blocked, all six book rows received `blocked_data_quality`, and an attempted committee approval returned HTTP 400. `capital_action_allowed`, `broker_order_allowed`, and `live_execution_allowed` remained false.

After proof, the validation proposal, six rules, run, six analysis lines, review, and SSD JSON artifact were deleted. The post-cleanup validator confirmed zero production policy/analysis/committee records and no unsafe analysis lines.

## Verification

- Migration replay and rollback check passed.
- Python AST checks and capital invariant validator passed.
- Invalid 0%-total API proposal returned HTTP 400 and created zero rows.
- MCP protocol/read smoke passed with 156 tools and 18 control rows.
- UI production build passed.
- Department-terminal browser suite passed 17/17.
- WCAG A/AA desktop/mobile suite passed 39/39.
- Desktop and 390x844 mobile screenshots were inspected with no page overflow or incoherent overlap.
- API, UI, Ollama, PostgreSQL, Redis, Qdrant, TradingView CDP, and agent daemon remained live after deployment.

## Open Gates

- Devarsh must define real client capital/risk policies.
- Client suitability, restrictions, taxes, liabilities, external assets, and complete cash balances.
- Portfolio Optimizer, Client Suitability Analyst, and Cash/Treasury Analyst roles.
- Strategy-to-book allocation integration and economic-offset detection.
- Drawdown-aware and liquidity-capacity sizing for proposed changes.
- Cash deployment queue and opportunity-cost ranking.
- Separate rebalance intent, order-risk preview, approval, and broker integration; live broker writes remain disabled.
