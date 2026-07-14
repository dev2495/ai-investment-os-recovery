# Terminal, Agent, And Research Foundation v1

Date: 2026-07-15
Owner: Devarsh
Orchestrator: Charlie Munger
Runtime operator: Jarvis
Status: verified foundation checkpoint, not final platform completion

## Outcome

The AI Investment OS now has a live, source-backed operating foundation for department terminals, operator customization, approval evidence, agent departments, research-paper ingestion, paper-derived strategy hypotheses, and advanced TradingView chart requests. All market and portfolio surfaces continue to prohibit seed data. Broker execution remains locked.

## Operating Surfaces Delivered

Six new Bloomberg-style terminal workspaces are live:

- Approval Board
- Agent Office
- Committee Rooms
- Capital Allocation
- Treasury and Macro
- Model Runtime

Each workspace uses a bounded department endpoint, displays its warehouse generation time, exposes evidence where a decision row supports it, and never requests the compatibility `/api/snapshot` endpoint.

The operator workspace manager can persist:

- dark or light terminal theme;
- compact or standard density;
- terminal column count;
- module order;
- hidden modules;
- widget visibility, order, and size.

Charlie and MCP use audited APIs for these changes. Widget data bindings and evidence lineage are preserved when layout metadata changes.

## Agent Office

The live warehouse contains 49 active agents across 11 departments:

| Department | Active agents |
| --- | ---: |
| Automation | 2 |
| Data | 4 |
| Executive | 1 |
| Knowledge | 1 |
| News | 4 |
| Portfolio | 6 |
| Quant | 11 |
| Research | 12 |
| Risk | 3 |
| Runtime | 2 |
| Trading | 3 |

The 13 roles added in this checkpoint are Automation Engineer, MCP Integration Engineer, Data Engineer, Data Quality Analyst, Macro Researcher, News Editor, Alternative Data Analyst, Capital Allocation Agent, Performance Attribution Agent, Portfolio Risk Analyst, Compliance Agent, Client Reporting Agent, and AI Runtime Engineer.

Every added role has a role scope, reporting line, permission level, tool set, guardrails, output targets, persona, operating style, mental models, escalation rules, cadence, cost policy, mailbox, office character, and human interaction contract. Agent mail uses durable warehouse records. It is not simulated UI dialogue.

Charlie remains the chief orchestrator and human-facing decision partner. Jarvis remains the runtime dispatcher. Specialists own scoped work. Capital actions, live execution, external sending, and policy exceptions require human approval.

## Research Paper Factory

The paper pipeline supports:

1. registration from arXiv, Crossref, SSRN, NBER, a public HTTPS PDF, or an allowed local file;
2. PDF validation and bounded download;
3. external-SSD PDF and text retention;
4. `pypdf` extraction;
5. content hashing and raw-artifact registration;
6. Postgres paper and ingestion-run records;
7. one idempotent review task and inbox item;
8. source-linked, falsifiable strategy hypotheses;
9. separate human review before strategy promotion.

Verified paper: [Trend-Following Strategies via Dynamic Momentum Learning](https://arxiv.org/abs/2106.08420), Bruno P. C. Levy and Hedibert F. Lopes.

Verified extraction evidence:

- 44 pages;
- 89,790 extracted characters;
- SHA-256 `635da97a5626d14f9cfa2185b634dce74d27be5040cd7ab73fb326eab095409d`;
- raw artifact `11251`;
- external PDF and text under `/Volumes/Devarsh SSD/AI OS Data/artifacts/research_papers`.

Repeated ingestion of the second registered paper produced one paper row, one open review task, and one open inbox item. No duplicate review work was created.

Paper-derived hypotheses are research records only. They cannot create a broker order, enable a live strategy, or allocate capital.

## TradingView Advanced Charts

Six reusable chart templates are registered:

- technical indicator stack;
- relative-strength ratio chart;
- spread or pair formula chart;
- four-pane option straddle workspace;
- fundamental-ratio dashboard;
- four-pane market-regime workspace.

Templates carry pane, symbol, formula, and indicator definitions. A live relative-strength request for TATASTEEL versus NIFTY created a pending approval and a `needs_approval` task. It did not mutate TradingView and did not create an order.

The current controller can inspect the live TradingView Desktop CDP session and run the existing guarded chart action path. Deterministic automation of every complex multi-pane template remains a separate production gate.

## Interfaces And Tools

New API surfaces:

- `GET /api/workspaces/config`
- `POST /api/workspaces/config/update`
- `POST /api/dashboard/widgets/update`
- `GET /api/department-terminal/snapshot`
- `POST /api/research/papers/ingest`
- `POST /api/research/papers/hypotheses`

New MCP tools:

- `ai_os_workspace_terminal_config`
- `ai_os_update_workspace_terminal`
- `ai_os_update_workspace_widget`
- `ai_os_ingest_research_paper`
- `ai_os_create_paper_strategy_hypotheses`

The permanent MCP smoke gate now requires these tools. The live MCP server exposes 138 tools, six workspace layouts, six current dashboard widgets, 49 orchestration rows, 18 data sources, and the existing Fincept component registry.

## Verification

- TypeScript and Vite production build: passed.
- Python compile for API, MCP, and paper ingestor: passed.
- Functional Playwright suite: 14 of 14 passed.
- Accessibility suite: 23 of 23 passed across four shards.
- Mobile document overflow: zero for the department terminal route.
- Desktop and mobile screenshots retained under `/Volumes/Devarsh SSD/AI OS Data/artifacts/output/playwright/2026-07-15-terminal-suite-v1`.
- API health: Postgres `ok`; TradingView CDP available on local port 9222.
- Local services: UI 5177, API 8765, Ollama 11434, TradingView CDP 9222.
- Seed data: prohibited on market, portfolio, research evidence, and department terminal reads.
- Broker execution: locked.

## Remaining Production Gates

This checkpoint does not claim the entire hedge-fund OS is complete. The next gates are:

- implement deterministic execution adapters for every approved advanced TradingView template;
- finish client onboarding, suitability, cash-flow, performance, and report-delivery workflows;
- complete cross-book factor, liquidity, stress, and portfolio Monte Carlo risk;
- turn capital-allocation recommendations into full committee packets and approved rebalance plans;
- add continuous paper discovery, citation parsing, replication checks, and research-quality scoring;
- complete strategy report, backtest v2, optimization, model-validation, and committee-minutes outputs;
- enforce broker read-only policy, order preview, kill switch, and backend live-execution gates;
- complete model routing evaluation, call cache, local/cloud escalation, privacy, and per-department policies;
- complete remote authenticated access and secrets management;
- refine the 3D office characters, direct canvas hit testing, committee discussion, and chronological activity playback.

## Evidence Links

- [[AI Investment OS - Institutional Master Blueprint v10.0]]
- [[AI Investment OS - Execution Checklist v10.0]]
- [[AI OS Command Center and 3D Office Frontend Plan]]
- [[Agent Team Roster]]
- [[2026-07-15-research-intelligence-v1]]
