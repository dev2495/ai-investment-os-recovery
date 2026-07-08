# Existing Systems Inventory

## External SSD Systems Found

### Algo Trading Terminal

Path:

`/Volumes/Devarsh SSD/algo based trading software 2`

Observed modules:

- `assistant`: existing always-on assistant loop
- `agents`: investor and trader personas
- `quant`: regime, factors, pairs, volatility, Monte Carlo, systematic runners
- `backtesting`: event-driven backtest engine
- `strategies`: base strategy layer
- `live_trading`: execution, signal engine, risk manager, tick stream, position tracker
- `portfolios`: accounts, holdings, trades, MTM, journal, analytics
- `options_tools`: straddle, strangle, option chain, Greeks, payoff tools
- `market_data`: NSE/BSE/quotes/session modules
- `fundamentals`: screener, Tijori, universe
- `ideas`: scanners, generator, watchlist, idea store
- `dashboard`: Dash app and charts
- `integrations/tradingview.py`: TradingView webhook receiver
- `alerts`: Telegram alert pipeline

Known databases:

- `data/trades.db`
- `data/storage/app.db`
- `data/storage/prices.db`

Current access note:

- `trades.db` schema was readable.
- `app.db` and `prices.db` exist and are valid SQLite files, but direct SQLite inspection from this workspace hit `SQLITE_CANTOPEN`. Treat this as an access/sandbox boundary until opened from the trading repo runtime or copied through an explicit safe export.

### Hermes / AI Trading Node

Path:

`/Volumes/Devarsh SSD/AI_Trading_Node`

Observed modules:

- Hermes data directory
- Hermes agent repo
- Provider/model caches
- State DB
- Logs
- Auth/config files

Do not read or expose auth/config contents unless explicitly needed.

## p2cursor

No directory named `p2cursor` was found in the first external SSD search.

Action needed:

- Confirm exact path.
- Identify whether it is a repo, database folder, app export, or Cursor workspace.
- Inventory schemas without dumping client rows.

## Integration Rule

Existing systems should be connected through read-only adapters first. Agents should not directly mutate client databases, live trading databases, or broker-connected systems until the AI OS has:

- Data map
- Access policy
- Audit log
- Human approval flow
- Backup/export path

