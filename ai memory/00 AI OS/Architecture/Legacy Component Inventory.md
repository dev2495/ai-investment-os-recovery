# Legacy Component Inventory

## Current State

Component manifest:

```text
_ai_os_runtime/imports/source_components_manifest.json
```

Quarantine/reference folders:

```text
_ai_os_runtime/imports/quarantine/algo_components
_ai_os_runtime/imports/quarantine/p2cursor_components
```

Warehouse tables:

```text
core.source_code_files
core.source_requirements
core.source_table_profiles
```

## Extraction Results

- 284 reusable source files registered.
- 147 p2cursor files.
- 137 old algo software files.
- 81 parsed requirements.
- 21 SQLite source tables profiled.

## Key Reusable Components

From old algo software:

- TradingView webhook receiver.
- Portfolio/account/holdings/trades engine.
- Trade journal.
- Backtesting engine.
- Strategy library.
- Indicator library.
- Quant/regime/factor modules.
- Market data modules for NSE/BSE/quotes.
- News, sentiment, fundamentals, and screeners.
- Ideas/watchlist engine.
- Dashboard tab patterns.
- Existing assistant/agent loop.
- Telegram alert pipeline.

From p2cursor:

- Portfolio/client app patterns.
- Dashboard/frontend patterns.
- Client folio CSV schemas.
- Backend portfolio/trade schema.
- Package/runtime references.

## Rule

Use these as reference and import sources. Do not run either legacy software as the new production OS source of truth.
