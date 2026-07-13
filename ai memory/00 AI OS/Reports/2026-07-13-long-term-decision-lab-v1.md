# Long-Term Decision Lab v1

Date: 2026-07-13
Status: verified implementation checkpoint
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Frontend: [[AI OS Command Center and 3D Office Frontend Plan]]

## Result

The existing deterministic Long-Term Monte Carlo engine is now a complete operator workflow inside Holdings Research. The scoped workspace exposes live theses, valuation modules, checklists, research updates, Monte Carlo evidence, and committee state; Devarsh can select a thesis, provide explicit assumptions and source evidence, run a simulation, inspect the distribution, and open the durable artifact. The action creates research evidence only and cannot allocate capital, approve a recommendation, or place a broker order.

## Existing Engine Promoted

The audit confirmed that these production components already existed and were reused:

- `portfolio.long_term_monte_carlo_runs` and `portfolio.v_long_term_monte_carlo_runs`;
- deterministic `run_long_term_monte_carlo.py`;
- POST `/api/portfolio/long-term-thesis/monte-carlo`;
- MCP tool `ai_os_run_long_term_monte_carlo`;
- valuation/thesis/research-update persistence;
- Obsidian Monte Carlo memo generation;
- output artifact and Symbol Intelligence lineage.

The missing layer was the scoped Holdings Research read/action surface. No second engine was created.

## Scoped Research Contract

`GET /api/research-ideas/snapshot` now adds bounded rows for:

- 16 long-term checklist records;
- 16 valuation models;
- 5 Monte Carlo runs;
- 32 long-term research updates.

The final live profile is 19 queries, 416 rows, 514,757 bytes, and about 0.18 seconds warm. Full sample paths, input snapshots, model outputs, and update evidence were intentionally removed from the polling payload; they remain available through durable artifact evidence.

## Decision Lab

The deployed form requires:

- live holding thesis;
- horizon years;
- simulation count;
- deterministic seed;
- optional starting multiple;
- starting-multiple source whenever that explicit multiple is provided;
- terminal low/base/high multiples;
- annual volatility.

An unsourced starting multiple is rejected in the browser before an API call. The API now forwards `starting_multiple_source` to the deterministic runner. The interface states that committee review remains mandatory before capital action.

The workspace displays:

- P50 CAGR;
- negative-CAGR probability;
- permanent-loss probability;
- warnings;
- simulation count and seed;
- output note path;
- run status;
- valuation modules;
- source-backed checklist findings;
- investment committee state.

## Live Action Proof

Run `#5` was created through the deployed UI:

- symbol: `USHAMART`;
- thesis id: `2`;
- simulations: `100`;
- seed: `20260714`;
- starting multiple: `35`;
- source: Usha Martin Annual Report 2024-25 plus `market.v_latest_price_quotes id=33`;
- status: `complete`;
- warnings: none;
- median CAGR: `-0.0348`;
- negative-CAGR probability: `0.70`;
- audit row: `agent.mcp_audit_log #298`.

The note was written directly to the mounted source-of-truth vault:

`ai memory/02 Portfolio/Long-Term Monte Carlo/20260713T073323Z-ushamart-monte-carlo.md`

SHA-256:

`8976d5b7a56fe1a854b3ff8ab512d63379190c5dee07c12c49a3b09ea043974e`

No repository-mirror copy was created after the path fix.

## Vault Path Contract

The live action exposed a symlink bug: scripts using `Path(__file__).resolve()` followed `_ai_os_runtime` into the code repository before selecting `VAULT_ROOT`. A bounded audit found the same pattern in twenty vault-aware scripts.

Those scripts now:

1. honor `AI_OS_RUNTIME_ROOT`;
2. honor `AI_OS_VAULT_ROOT`;
3. otherwise use the invoked path without resolving the external symlink.

The API and MCP entrypoints use the same environment contract. All twenty scripts plus API and MCP compile successfully. Monte Carlo run `#4`, created before the fix, was synced to the external vault; its temporary repository note was removed.

An AST-backed release gate, `verify_vault_path_contract.py`, now discovers every module assigning `VAULT_ROOT`. It passed across 24 script/API/MCP modules with zero missing runtime or vault environment keys.

## Verification

- TypeScript and Vite production build passed.
- Main JS: 277.84 KB, gzip 74.95 KB.
- Live Office remains lazy-loaded at 859.43 KB, gzip 229.28 KB.
- Three permanent Decision Lab tests passed: live scoped read, unsourced-assumption block, and mobile overflow.
- The permanent 23-case WCAG A/AA gate passed.
- The deployed UI issued one scoped Research request and no compatibility `/api/snapshot` request.
- MCP read smoke passed with 133 tools, 36 orchestration rows, 21 blueprint domains, and the expected portfolio/research/Fincept surfaces.
- Desktop and 390-pixel mobile screenshots are retained at `/Volumes/Devarsh SSD/AI OS Data/artifacts/browser-verification/2026-07-13-long-term-decision-lab-v1`.

## Blueprint Registry

- Sync run: `blueprint-v10-long-term-decision-lab-v1-20260713`.
- Checklist SHA-256: `4362e0c4f097b4b06a466d98a9d8459c81670f41ada60414b2b4968a27ea2e05`.
- Coverage: 21 domains, 523 requirements, 77 done, 168 partial, 278 planned, zero seed rows.

## Remaining Long-Term Work

- Complete source-backed DCF, reverse DCF, sum-of-parts, peers, historical valuation, scenarios, and expected-CAGR calculators.
- Put Monte Carlo distribution fields directly into the Long-Term Investment Committee decision packet and follow-up workflow.
- Complete client suitability, portfolio-fit, sell-discipline, drift, and quarterly-review actions.
- Expand verified thesis/checklist/valuation coverage beyond the current USHAMART and LIQUIDBEES records.
