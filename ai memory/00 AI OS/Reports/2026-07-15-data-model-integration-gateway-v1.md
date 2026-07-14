# Data And Model Integration Gateway v1

Date: 2026-07-15
Status: verified foundation checkpoint

## Outcome

The AI Investment OS now has one operational control plane for adding, validating, monitoring, and assigning data sources and model providers. It replaces passive registry panels with a real Data & Model Gateway backed by Postgres, scoped API contracts, audited writes, MCP tools, bounded executors, durable evidence, and a production terminal.

This checkpoint makes the stack plug-in ready. It does not claim that every future source, model, broker, dataset, or production-execution gate is complete.

## Live State

| Control | Verified state |
|---|---:|
| Canonical plug-ins | 39 |
| Data-source plug-ins | 18 |
| Model-provider plug-ins | 21 |
| Validated schema mappings | 5 of 5 |
| Enabled bounded jobs | 5 |
| Model routes | 21 |
| Ready plug-ins | 21 |
| Missing credential references | 4 |
| Missing legacy/import mappings | 5 |
| Unavailable model endpoints | 5 |
| Freshness-SLA failures | 0 |
| MCP tools | 144 |

The verified TradingView job requested the live portfolio/event universe and persisted 44 quotes. Its integration job and source-check records completed without granting execution authority.

## Implemented Contracts

- Canonical plug-in manifests synchronize from existing source connectors and model endpoints.
- Data-source contracts retain health, freshness, access mode, credentials, schema mapping, schedule, owner, and evidence.
- Model contracts retain provider readiness, route, capabilities, cost tier, context, credentials, owner, and evidence.
- Schema mappings validate target relations and retain field, key, timestamp, transformation, and idempotency contracts.
- Integration jobs persist configuration, bounded parameters, run state, row counts, errors, and result summaries.
- Integration evidence resolves health checks, mappings, jobs, job runs, provider readiness, and model routes.
- The live daemon refreshes TradingView portfolio and active-event quotes every 15 minutes.

## Safety Boundaries

- No seed data is used by the Gateway.
- Recursive checks reject raw keys, passwords, tokens, client secrets, and private keys.
- Only approved credential-reference prefixes may be stored.
- The API and Postgres independently reject unknown executor keys.
- Six code-owned executor families are allowed; arbitrary shell commands are impossible through the contract.
- Approval-required jobs cannot run through the unrestricted job endpoint.
- Broker writes remain globally locked and separate from connector readiness.

## Operator Surface

The Data & Model Gateway supports:

- source registration,
- model-provider registration,
- plug-in search and readiness filters,
- per-plug-in health checks and full provider sweeps,
- warehouse mapping creation and validation,
- bounded ingestion-job configuration and manual runs,
- route inspection,
- source/model evidence review,
- persisted freshness and run status.

The terminal is responsive and keyboard accessible. It uses a scoped seven-query live snapshot and never requests the broad compatibility snapshot.

## Verification

- Postgres migration applied and reapplied with `ON_ERROR_STOP=1`.
- Database bypass probe rejected executor `shell` through `integration_jobs_executor_allowlist`.
- API probe rejected executor `shell` with HTTP 400.
- Raw-secret API probe rejected nested `config.api_key` and inserted no record.
- Real TradingView refresh completed with 44 quotes written.
- Python compilation passed for API, MCP, daemon, and quote-refresh modules.
- Frontend TypeScript and production build passed.
- MCP smoke passed with 144 tools and all Gateway collections present.
- External-storage verification passed for vault, Ollama, logs, run state, dependencies, Docker image, and browser cache.
- All 37 WCAG A/AA cases passed across 17 workspaces at desktop/mobile widths plus dialog and Live Office fallbacks.
- The complete Playwright suite passed 71 of 71 cases, including WebGL canvas-pixel verification.
- Loaded desktop/mobile screenshots were visually inspected; no page-level overflow or incoherent overlap was observed.

## Open Gates

- Map the five legacy and user-import connectors into canonical warehouse relations.
- Install or revise the five routes that currently point to unavailable Qwen models.
- Add approved references for Zerodha, Dhan, and any cloud providers when credentials are intentionally supplied.
- Build research-grade historical daily, intraday, options, futures, volatility, commodity, and corporate-action datasets.
- Add crypto-exchange read-only connectors before proposing any crypto execution adapter.
- Complete provider-policy editor, simulator, quality evals, caching, escalation approval, and local-versus-cloud routing tests.
- Keep broker execution locked until risk, compliance, security, reconciliation, paper monitoring, and limited-live gates pass.

## Evidence Paths

- Migration: `_ai_os_runtime/postgres/init/118_integration_plugin_gateway_v1.sql`
- API: `_ai_os_runtime/api/ai_os_api_server.py`
- MCP: `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`
- Terminal: `_ai_os_runtime/ai-office-ui/src/views/IntegrationGatewayWorkspace.tsx`
- Browser tests: `_ai_os_runtime/ai-office-ui/tests/integration-gateway.spec.ts` and `tests/a11y.spec.ts`
- Canonical blueprint: [[AI Investment OS - Institutional Master Blueprint v10.0]]
- Execution tracker: [[AI Investment OS - Execution Checklist v10.0]]
