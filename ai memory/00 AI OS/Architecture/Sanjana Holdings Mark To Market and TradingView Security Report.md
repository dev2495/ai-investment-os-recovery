---
type: implementation_report
tags:
  - ai-os
  - portfolio
  - sanjana
  - mark-to-market
  - tradingview
  - qdrant
created: 2026-07-03
---

# Sanjana Holdings Mark To Market and TradingView Security Report

Date: 2026-07-03 01:23 IST

## What Changed

Imported Sanjana's holdings from:

- `/Users/devarshthakkar/Downloads/Sanjana_Long Term_Report_2025-09-17.pdf`

The report has:

- Report date: `2025-09-17`
- Current holdings parsed: 26
- Trade rows parsed: 30
- Client account created: `sanjana_long_term`
- Quote source: TradingView scanner endpoint
- Quote rows stored: 34
- Missing quotes: 0

New data objects:

- `market.price_quotes`
- `market.v_latest_price_quotes`
- `core.data_source_registry.source_key = tradingview_scanner_quotes`
- `core.data_source_registry.source_key = sanjana_long_term_report_2025_09_17`

Scripts:

- `_ai_os_runtime/scripts/import_sanjana_pdf_and_mark_to_market.py`

Migration:

- `_ai_os_runtime/postgres/init/023_market_price_quotes.sql`

## Portfolio Values

Current control-plane view after mark-to-market:

| Client | Accounts | Positions | Market Value |
| --- | ---: | ---: | ---: |
| Sanjana | 1 | 26 | 6,724,518.55 |
| Naval | 1 | 14 | 4,978,708.50 |
| Tushit | 1 | 4 | 1,000,115.40 |

Portfolio-level PnL from imported average prices:

| Client | Positions | Market Value | Unrealized PnL |
| --- | ---: | ---: | ---: |
| Tushit | 4 | 1,000,115.40 | 52,672.13 |
| Naval | 14 | 4,978,708.50 | 2,952,091.65 |
| Sanjana | 26 | 6,724,518.55 | 725,435.35 |

There is still one unlinked `personal` legacy-algo row with WIPRO. It was marked to market but remains outside client reporting until Devarsh confirms whether to promote or remove it.

## Sanjana Top Holdings After Pricing

| Symbol | Quantity | Avg Price | Market Price | Market Value | First Buy Date | Quote |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| ASIANPAINT | 215 | 2341.70 | 2744.50 | 590,067.50 | 2025-01-02 | NSE:ASIANPAINT |
| MSTCLTD | 700 | 580.60 | 695.15 | 486,605.00 | 2025-01-29 | NSE:MSTCLTD |
| LAURUSLABS | 313 | 320.00 | 1528.00 | 478,264.00 | 2023-03-24 | NSE:LAURUSLABS |
| AARON | 4000 | 161.97 | 117.57 | 470,280.00 | 2025-01-20 | NSE:AARON |
| SJS | 210 | 476.60 | 2226.80 | 467,628.00 | 2023-05-15 | NSE:SJS |
| SGMART | 760 | 396.50 | 603.15 | 458,394.00 | 2024-08-21 | NSE:SGMART |
| GRWRHITECH | 66 | 3843.00 | 6934.50 | 457,677.00 | 2025-02-19 | NSE:GRWRHITECH |
| IEX | 3700 | 135.50 | 123.50 | 456,950.00 | 2025-07-29 | NSE:IEX |
| SAMHI | 2030 | 245.60 | 175.62 | 356,508.60 | 2025-07-17 | NSE:SAMHI |
| SBCL | 440 | 581.10 | 763.20 | 335,808.00 | 2024-12-24 | NSE:SBCL |

`SRESTHA` was priced from `BSE:SRESTHA`; TradingView did not return it as an NSE symbol.

## Tushit Live Statement

The existing Tushit data is from P2Cursor and currently shows:

- Client code: `3081832`
- Positions: 4
- Latest position date: `2025-06-10`
- Market value after pricing: 1,000,115.40

Opening the live browser statement is useful if we need a newer source of truth for:

- current holdings,
- exact buy dates,
- lots,
- realized trades after `2025-06-10`,
- broker-confirmed average prices.

It was not required for this mark-to-market pass because Tushit already had imported positions, but it is the right next step if the browser statement is more current than P2Cursor.

## What Qdrant Is For

Postgres is the structured source of truth:

- clients,
- accounts,
- holdings,
- trades,
- prices,
- strategy runs,
- tasks,
- audit logs.

Qdrant is the semantic memory/search layer:

- "Find similar old trade journal entries."
- "Find all notes related to demerger/special situations."
- "Retrieve relevant research reports for ASIANPAINT."
- "Give Charlie the 8 most relevant notes before answering."
- "Search by meaning, not exact filename or ticker."

In short:

- Postgres answers exact questions.
- Qdrant helps agents retrieve relevant context from notes, PDFs, reports, journals, filings, and strategy artifacts.

Current Qdrant gap:

- Collections exist.
- Embeddings are not populated yet.
- Next step is to embed Obsidian notes, research reports, and trade journals into Qdrant.

## Why Daily OHLCV Matters

OHLCV means:

- Open
- High
- Low
- Close
- Volume

For portfolio mark-to-market, latest price is enough.

For strategy research and backtesting, OHLCV is required because agents need clean time bars:

- daily trend and momentum,
- swing strategy testing,
- intraday 5m/15m candles,
- stop-loss and target simulation,
- volatility and ATR,
- volume filters,
- drawdown and regime testing.

Raw ticks are too heavy for most strategy loops. OHLCV is the practical research format.

Current OHLCV gap:

- Tick import succeeded.
- Daily OHLCV aggregation/import is still incomplete.
- Need a chunked importer instead of rerunning the long daily aggregation blindly.

## TradingView MCP Vulnerability Fix

Before fix:

- npm audit reported 7 vulnerabilities:
  - 4 moderate
  - 3 high

Fix applied:

- Ran `npm audit fix --package-lock-only`.
- Ran `npm install` to sync installed dependencies.

After fix:

- `npm audit --json`: 0 vulnerabilities.
- `npm run tv -- status`: passed.
- `npm run test:unit`: passed 29/29 tests.

Full upstream E2E suite:

- 93/95 tests passed.
- 2 failed due current TradingView Desktop UI/replay runtime assumptions:
  - `window.TradingView.bottomWidgetBar.hideWidget` is not available in this build.
  - replay stop assertion failed because replay was already stopped.

Interpretation:

- Security vulnerabilities are fixed.
- TradingView controller remains usable.
- Chart/data/Pine/drawing/capture paths passed.
- The two E2E failures are feature/runtime compatibility issues, not npm vulnerability failures.

## Next Step

The correct next step is not more architecture.

Build the first usable Charlie workflow:

1. Natural-language Charlie intake.
2. Charlie routes to Jarvis MCP tools.
3. Portfolio Manager reads marked-to-market client folios.
4. Charlie can accept manual trades and strategy ideas.
5. Strategy Intake Agent converts user strategy descriptions into structured specs.
6. TradingView task adapter opens chart layouts/screenshots for evidence.
7. Qdrant embedding pipeline gives Charlie long-term memory retrieval.

Practical first task:

- Build "Charlie Command Center" around the existing MCP tools, starting with:
  - client folio summary,
  - manual trade entry,
  - strategy intake,
  - TradingView task request,
  - Obsidian report writeback.
