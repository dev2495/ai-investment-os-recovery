# Model And Source Connector Control Layer

Date: 2026-07-06
Status: implemented and verified foundation slice

## What Changed

- Added `_ai_os_runtime/postgres/init/046_model_source_onboarding_control.sql`.
- Added `agent.model_endpoints` for local/cloud model endpoint onboarding.
- Added `core.source_connector_profiles` for data-source connector onboarding.
- Added `core.connector_health_checks` as a unified model/source readiness ledger.
- Added database functions:
  - `agent.register_model_endpoint`
  - `agent.run_model_endpoint_health_check`
  - `core.register_source_connector`
  - `core.run_source_connector_health_check`
- Added views:
  - `agent.v_model_endpoint_control`
  - `core.v_source_connector_control`
  - `core.v_connector_health_checks`
- Derived initial endpoint rows from `agent.model_routes`.
- Derived initial connector rows from `core.data_source_registry`.
- Added tool registry entries for model endpoint registration/checks and source connector registration/checks.
- Added API snapshot keys:
  - `model_endpoints`
  - `source_connectors`
  - `connector_health_checks`
- Added API endpoints:
  - `POST /api/models/endpoints/register`
  - `POST /api/models/endpoints/check`
  - `POST /api/data-sources/connectors/register`
  - `POST /api/data-sources/connectors/check`
- Added AI Office dashboard panels:
  - Model Endpoint Control
  - Source Connector Control
  - Connector Health Ledger

## Guardrails

- No raw API keys or broker credentials are stored.
- Credentialed sources use `secret_ref` only.
- Broker/execution connectors remain read-only in this layer.
- Health checks are configuration/readiness checks unless a connector has a separate real runtime adapter.
- Test rows created through API smoke were removed after verification.

## Verified Evidence

- Migration applied successfully.
- `agent.model_endpoints` contains 21 real endpoint rows derived from current model routes.
- `core.source_connector_profiles` contains 18 source connector rows derived from current source registry.
- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py` passed.
- `npm run build` passed for the AI Office UI.
- Rollback smoke test proved:
  - local model endpoint check returns `configured`,
  - public filing source check returns `configured`,
  - broker connector without secret returns `needs_secret`,
  - rollback left 0 temporary model rows, 0 temporary source rows, and 0 temporary health rows.
- Live HTTP API smoke passed for all four new POST endpoints.
- API smoke cleanup confirmed:
  - `api_smoke` model rows: 0
  - `api_smoke` source rows: 0
  - `api_smoke` health rows: 0
  - `api_smoke` audit rows: 0
- Live API health returned `ok = true`.
- AI Office UI returned HTTP 200.
- Final snapshot returned:
  - `issues = []`
  - `seed_data_allowed = false`
  - `model_endpoints = 21`
  - `source_connectors = 18`
  - `connector_health_checks = 7`

## Current Real Readiness

- `always_on_daily_driver_ollama_llama3_2_3b`: `configured`
- `strategy_backtest_local_python_deterministic_tools`: `configured`
- `algo_trading_archive_connector`: `configured`
- `nse_filings_connector`: `needs_browser`
- `bse_filings_connector`: `needs_browser`
- `tradingview_mcp_connector`: `needs_browser`
- `zerodha_live_connector`: `needs_secret`

## Important Correction

The first snapshot showed `local_python` deterministic routes incorrectly marked as API-key-requiring external providers. The migration was corrected so `local_python`, `local_http`, `python`, `deterministic`, `ollama`, `mlx`, `lm_studio`, and `local` are classified as local/no-secret providers.

## Still Open

- This is not yet a live Zerodha/Dhan credentialed connector.
- TradingView still needs browser/CDP relaunch or production browser MCP wiring.
- NSE/BSE official pages need browser session/profile configuration before live scraping checks.
- Model checks are configuration checks; actual token-generation latency monitoring is still open.
- Secret manager integration is still open beyond the `secret_ref` database policy.

