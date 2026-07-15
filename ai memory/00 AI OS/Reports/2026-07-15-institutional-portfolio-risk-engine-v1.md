# Institutional Portfolio Risk Engine v1

Date: 2026-07-15

Status: implemented, live, validated, and deliberately provisional because market-history coverage is incomplete.

## Delivered

- Idempotent institutional-risk schema for runs, scoped metrics, stress results, position liquidity, factor attribution, and scenario definitions.
- Deterministic real-position engine with historical VaR/ES, 1-day and 10-day bootstrap paths, stress, concentration, liquidity, benchmark beta/correlation, residual risk, drawdown, and loss probabilities.
- Portfolio, Long-Term book, and Naval/Sanjana/Tushit client scopes.
- Bounded API snapshot plus audited `POST /api/risk/institutional/run` action.
- MCP run/read tools, bringing the callable surface to 152 tools.
- Responsive Risk Center panels for scope metrics, stress scenarios, factors, and position liquidity.
- Repeatable numerical validator and permanent desktop/mobile browser tests.
- External-SSD JSON artifacts with explicit source lineage, assumptions, warnings, and execution prohibition.

## Verified Live State

Run: `institutional_risk_v1_verified_20260715`, database run `#4`.

| Measure | Verified value |
|---|---:|
| Active positions | 71 |
| Clients | 3 |
| Books | 1 |
| Symbols | 45 |
| Gross exposure | INR 23,470,281.79 |
| Covered symbols | 22 |
| Uncovered symbols | 23 |
| Covered exposure | INR 10,613,817.89 |
| Uncovered exposure | INR 12,856,463.90 |
| Historical coverage | 45.22% |
| Return observations | 756 |
| 1-day bootstrap VaR 99 | 3.51% |
| 1-day bootstrap ES 99 | 4.28% |
| 10-day bootstrap VaR 99 | 8.27% |
| 10-day bootstrap ES 99 | 9.96% |
| Annualized volatility | 8.28% |
| Maximum drawdown | 8.27% |
| NIFTY 50 beta | 0.4371 |
| Top-five exposure | 39.48% |
| Worst stress loss | 10.48% |

The five portfolio stresses were liquidity/gap shock, market down 10%, historical worst covered day, top-three positions down 20%, and market down 5%. All produced losses rather than gains.

## Data Qualification

- Position as-of: 2026-06-30.
- Market history as-of: 2026-06-12.
- Freshness gap: 18 days.
- Daily OHLCV covers only 22 of the 45 current symbols.
- Twenty-three symbols have no usable traded-volume history and are explicitly `insufficient`/`unavailable` in liquidity output.
- Corporate-action readiness is `needs_verification`.
- Point-in-time universe readiness is `current_snapshot_only`.
- Missing-history exposure is proxy-modeled and separately disclosed; it is not presented as observed history.

For these reasons the run status is `provisional`. The estimates support risk review and data remediation, not capital authorization.

## Interfaces

- API read: `GET /api/trading-quant-risk/snapshot`.
- API action: `POST /api/risk/institutional/run`.
- MCP read: `ai_os_institutional_portfolio_risk`.
- MCP action: `ai_os_run_institutional_portfolio_risk`.
- UI: Command Center -> Risk Center.
- Validator: `_ai_os_runtime/scripts/validate_portfolio_risk_engine.py`.
- Artifact: `/Volumes/Devarsh SSD/AI OS Data/artifacts/portfolio_risk/institutional_risk_v1_verified_20260715.json`.
- Artifact SHA-256: `44d485f205f7c1c45ffe70f70fa1b3c694cac38655d927dccf9d2f7920edcd2c`.

## Safety

- No seed position, market, risk, or execution rows were created.
- `capital_action_allowed=false`.
- `live_execution_allowed=false`.
- `global_execution_locked=true`.
- `live_broker_writes_allowed=false`.
- API runs append to `agent.mcp_audit_log`.
- Failed runs are retained but excluded from latest operating views.

## Verification

- Migration rollback/application and idempotent reapplication passed.
- Python AST parsing passed for API, MCP, runner, and validator.
- Production TypeScript/Vite build passed.
- Numerical validator passed all five metric scopes, five portfolio stresses, 45 liquidity symbols, expected factor rows, exposure reconciliation, ES/VaR ordering, and execution locks.
- Live API read and 20,000-path run passed.
- MCP initialized with protocol `2024-11-05`, listed 152 tools, and returned the institutional read model with capital/execution false.
- Department-terminal Playwright suite passed 15/15.
- WCAG A/AA desktop/mobile suite passed 39/39.
- Desktop and 390 x 844 mobile screenshots showed no incoherent overlap or page-level horizontal overflow.

## Remaining Risk Office Work

- Options Greeks, volatility-surface, scenario, and tail-risk model.
- Sector/style/rates/FX/commodity factor models and correlation clusters.
- Verified corporate-action adjustment factors and dated point-in-time universes.
- Current daily-history tail and missing-symbol history remediation.
- Cross-book conflict escalation and netting-cost analysis.
- Formal Risk Committee decisions, override ledger, and follow-up actions.
- Per-order risk evidence drawer and pre-trade scenario packet.
- Scheduled CRO/Portfolio Risk Analyst/Stress Testing/Model Risk worker cadence.

No broker order was placed, no capital was reallocated, and no execution capability was enabled.
