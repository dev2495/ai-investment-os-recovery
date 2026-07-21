# Zerodha Live Backend Contract

## Safety boundary

- All Zerodha connectors are read-only.
- `broker_write_allowed` is always `false` in stream tables and API responses.
- No password, PIN, TOTP, API secret, request token, or access token is returned to the frontend.
- The access token is stored in the macOS Keychain.
- Zerodha's required daily human login is not bypassed.

## Session flow

1. Configure this redirect URL once in the Zerodha developer application:
   `https://devarshs-imac.tail8dd383.ts.net:8443/api/zerodha/auth/callback`
2. Open the `login_url` returned by `GET /api/zerodha/stream/status`.
3. Zerodha redirects to the callback.
4. The backend exchanges and stores the one-time token, refreshes account/market data, and restarts the stream.

The callback redacts `request_token` from access logs and returns an HTML completion page.

## Endpoints

### `GET /api/zerodha/stream/status`

Returns:

- Session configuration without secret values.
- Current stream run, connection state, subscriptions, tick totals, and freshness.
- The configured callback URL and broker-write lock.

### `GET /api/market/live-prices`

Query parameters:

- `scope`: `all`, `portfolio`, `watchlist`, `options`, or `indices`.
- `freshness`: optional `live`, `delayed`, or `stale`.
- `symbols`: optional comma-separated symbols.
- `limit`: 1-1000; default 250.

Freshness:

- `live`: received within 20 seconds.
- `delayed`: received within five minutes.
- `stale`: older than five minutes.

Use `age_seconds` and `freshness` visibly in any trading or portfolio surface.

### `GET /api/market/live-price-history`

Required parameters:

- `exchange`
- `symbol`

Optional:

- `minutes`: 1-64800; default 390.

Returns one-minute OHLC bars built from WebSocket ticks. History is retained for 45 days by default. Longer history should use Zerodha's historical-candle connector.

### Existing read-only refresh endpoints

- `POST /api/zerodha/sync`
- `POST /api/zerodha/market/sync`
- `GET /api/zerodha/market/status`

## Runtime behavior

- LaunchAgent: `com.devarsh.aios.zerodha-stream`
- Latest state: `market.live_quote_state`
- Minute bars: `market.live_quote_minute_snapshots`
- Stream health: `market.v_zerodha_stream_health`
- Frontend read model: `market.v_live_prices`
- Existing valuation compatibility: minute prices are also written to `market.price_quotes`.
- Holdings/account snapshots and the rolling NIFTY/BANKNIFTY option universe refresh every five minutes while the session is valid.
- Subscription changes are reloaded every five minutes.
- The service retries after power loss, logout, network failure, API restart, and token renewal.

## Runtime dependency exception

`kiteconnect==5.2.0` still declares `autobahn[twisted]==19.11.2`. That release is
affected by PYSEC-2020-25. The iMac installer replaces it with the compatible
fixed release `autobahn==20.12.3`, verifies the imported version, and runs
`pip-audit --local` before the LaunchAgent is installed. The resulting runtime
is clean even though `pip check` reports the stale upstream equality pin.
