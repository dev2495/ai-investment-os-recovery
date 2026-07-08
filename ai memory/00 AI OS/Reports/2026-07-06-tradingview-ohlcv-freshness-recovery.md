# TradingView CDP And OHLCV Freshness Recovery

Date: 2026-07-06
Status: done and verified
Owner: Trading Desk Agent / Automation Engineer / Data Steward

## What Was Fixed

- Relaunched TradingView Desktop with local CDP enabled:
  - `--remote-debugging-port=9222`
- Added a TradingView CDP health checker:
  - `_ai_os_runtime/scripts/check_tradingview_cdp.py`
- Added daemon-backed TradingView CDP heartbeat:
  - every `60` seconds
- Added audited OHLCV aggregation health rows:
  - `_ai_os_runtime/scripts/aggregate_ticks_to_ohlcv.py`
- Added daemon-backed tick-to-OHLCV aggregation:
  - every `300` seconds
- Added control-plane migrations:
  - `_ai_os_runtime/postgres/init/056_tradingview_cdp_heartbeat.sql`
  - `_ai_os_runtime/postgres/init/057_ohlcv_aggregation_daemon.sql`
- Updated launchd service payload:
  - `_ai_os_runtime/launchd/aios-agent-daemon-service.sh`
  - `_ai_os_runtime/launchd/com.devarsh.aios.agent-daemon.plist`
  - `_ai_os_runtime/scripts/start_ai_office_live.sh`

## Why It Was Needed

The source freshness scheduler exposed three live risks:

- `tradingview_scanner_quotes` stale
- `tradingview_mcp` stale
- `tick_ohlcv_aggregation` missing/stale/error

The quote source was refreshed with real TradingView scanner data. TradingView Desktop was running, but not with the CDP debug port, so the local controller could not attach. OHLCV aggregation was producing bars but was not writing durable source-check rows; after launchd installation it also failed because the installed service copy lacked the `imports/` directory before writing its summary file.

## Repeated Error Handling

The repeated TradingView `127.0.0.1:9222` connection failure was resolved by checking Electron documentation and applying the efficient fix:

- Remote debugging must be enabled at app startup.
- A running single-instance Electron app can ignore second-launch arguments.
- TradingView was cleanly quit and relaunched with `--remote-debugging-port=9222`.

The repeated OHLCV `FileNotFoundError` was resolved by checking Python `pathlib` behavior and applying the efficient fix:

- `Path.write_text()` writes a file but does not create missing parent directories.
- The script now calls `output_path.parent.mkdir(parents=True, exist_ok=True)` before writing.

## Verification Evidence

- `curl http://127.0.0.1:9222/json/version` returned TradingView/Electron CDP metadata.
- `GET /api/tradingview/cdp-status` returned:
  - `available: true`
  - `browser: Chrome/140.0.7339.133`
- `python3 _ai_os_runtime/scripts/check_tradingview_cdp.py` wrote check id `13`.
- Direct daemon pass wrote TradingView CDP check id `24`.
- Direct daemon pass ran OHLCV aggregation over real ticks:
  - Tick rows: `197595`
  - Symbols: `14`
  - 1d bars: `28`
  - 1h bars: `168`
  - 15m bars: `504`
  - 5m bars: `1431`
  - Total OHLCV rows upserted: `2131`
- Direct daemon freshness run id `8` showed:
  - Checked sources: `9`
  - Fresh targeted sources: `3`
  - Stale/error/missing: `0`
- Launchd restart succeeded with:
  - API live
  - Agent daemon live
  - UI live
- Installed launchd daemon log shows:
  - `ohlcv=ok`
  - `tradingview_cdp=ok`
  - `source_freshness=success`
- Latest scheduler rows:
  - run id `9`: stale/error count `0`
  - run id `10`: stale/error count `0`
- Latest targeted source freshness:
  - `tradingview_scanner_quotes`: `fresh`
  - `tradingview_mcp`: `fresh`
  - `tick_ohlcv_aggregation`: `fresh`
- Open data-source risk events:
  - none
- UI served successfully at:
  - `http://127.0.0.1:5177/`

## Still Open

- Build TradingView chart open workflow.
- Build TradingView screenshot artifact capture.
- Build TradingView production controller actions on top of the verified CDP connection.
- Add broader live tick ingestion beyond the current imported tick dataset.
- Add options chain/OI/IV ingestion.
