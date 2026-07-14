# Runtime, Source Intelligence, And Market Bias Controls v1

Date: 2026-07-15

## Scope

This checkpoint closes the external-artifact path defect, adds a persisted 24/7 daemon heartbeat, separates fast news freshness from heavier discovery work, and establishes non-destructive corporate-action and point-in-time-universe controls. It does not claim that the complete Investment OS or market data is production-execution ready.

## Verified Outcomes

- Git-backed code runs from `/Users/devarshthakkar/AI_OS_ACTIVE_RECOVERY_20260710/ai-investment-os/_ai_os_runtime`.
- Vault and heavy/generated state remain on the external SSD.
- Research, filing, backtest, optimizer, validation, allocation, journal-mining, and strategy-discovery artifacts default to `/Volumes/Devarsh SSD/AI OS Data/artifacts`.
- Playwright Chromium 1228 and FFmpeg are installed under `/Volumes/Devarsh SSD/AI OS Data/caches/ms-playwright` (about 551 MB), not the internal browser cache.
- LaunchAgent daemon reported `running` and SQL-derived `healthy`; observed heartbeat age was five seconds.
- System Health scoped API reported the internal runtime root and the persisted daemon row.
- Broker execution remains locked and no new workflow grants live-order authority.

## Real Source Loop

Run: `source_intelligence_ssd_verify_20260715`

- News: 10 active feeds, 56 items seen/upserted, no feed errors.
- Filings: 100 NSE plus 100 BSE rows, 200 classified filing events.
- PDF extraction: 2/2 completed, 3,768 extracted characters, two structured special-situation terms.
- Discovery: 12 candidates, 12 generated ideas, one bounded optimizer route.
- Artifact paths: external SSD for both filing PDFs and strategy-discovery JSON.
- Safety: `live_execution_allowed=false`; `seed_data_allowed=false`.

Dedicated news run `market_news_freshness_fix_20260715` wrote an aggregate `global_news` check. The subsequent freshness result was `fresh`, severity `low`, with approximately zero minutes of staleness against the 15-minute target. The daemon now repeats this workload every 900 seconds; the filing/discovery loop remains hourly.

## Market Bias Controls

| Control | Observed | Mapped | Verified | Applied | Status |
|---|---:|---:|---:|---:|---|
| Corporate actions | 127 | 17 | 0 | 0 | needs_verification |
| Point-in-time universe | 530 | 530 | 0 | 0 | current_snapshot_only |

Raw OHLCV is never overwritten. `market.v_ohlcv_adjusted` currently returns the same prices as raw OHLCV because no adjustment factor is verified. The 530 universe rows start at the current capture date and do not imply historical membership.

## Interfaces

- Database: `core.v_runtime_daemon_health`, `market.v_market_bias_control_readiness`, `market.v_ohlcv_adjusted`.
- MCP: `ai_os_runtime_daemon_health`; `ai_os_market_data_readiness` now includes `bias_controls`.
- UI: System Health `24/7 Agent Runtime`; Gateway corporate-action and point-in-time cards.
- Live scoped API: System Health and Integration Gateway include the new bounded rows.

## Verification

- Migration 120 rollback test and idempotent live apply: passed.
- Migration 121 rollback test caught and corrected an aggregate syntax error; clean rollback and live apply then passed.
- Migration 122 rollback test and live apply: passed.
- Python AST parsing, Bash syntax, plist lint, TypeScript, and Vite production build: passed.
- MCP smoke: 147 tools, one daemon row, two market-bias rows.
- Integration Gateway Playwright: 5/5 passed.
- Reports/System Health Playwright: 4/4 passed.
- System Health desktop/mobile WCAG A/AA automation: 2/2 passed.
- Loaded desktop screenshots: visually inspected; no overlap or incoherent layout.

## Remaining Gates

- Verify and map the 110 filing actions that do not yet resolve to canonical symbols.
- Extract and human-verify split, bonus, rights, merger, demerger, dividend, and other adjustment terms.
- Approve factors only after duplicate-event and source reconciliation.
- Ingest historical index/tradable-universe constituent membership.
- Add a recurring live daily and deeper intraday/options provider.
- Resolve seven remaining source-freshness/readiness issues.
- Connect authenticated X/Twitter, Zerodha, Dhan, crypto, commodity, and cloud-model credentials through secret references.
- Keep paper/live broker execution blocked until the separate risk, compliance, reconciliation, and approval gates pass.
