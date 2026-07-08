# Strategy Discovery Scheduler And External Sources v1

Date: 2026-07-07
Owner: Strategy Discovery Agent / News Analyst
Status: completed for foundation v1

## Outcome

The AI OS now has a scheduled external-source discovery loop. It can ingest public RSS/news feeds into the live warehouse, create source-backed news catalyst ideas, run automatic strategy discovery, and expose the full run history to API, MCP, and the AI Office dashboard.

Broker execution and autonomous live execution remain disabled.

## What Was Built

- Migration: `_ai_os_runtime/postgres/init/093_strategy_discovery_scheduler_external_sources_v1.sql`
- News ingestion worker: `_ai_os_runtime/scripts/ingest_market_news.py`
- Scheduler worker: `_ai_os_runtime/scripts/run_strategy_discovery_scheduler.py`
- Daemon hook: `_ai_os_runtime/scripts/run_agent_message_daemon.py`
- API:
  - `POST /api/market/news/ingest`
  - `POST /api/strategy/discovery/scheduler/run`
- MCP:
  - `ai_os_ingest_market_news`
  - `ai_os_run_strategy_discovery_scheduler`
  - `ai_os_strategy_discovery_scheduler_runs`
- AI Office UI:
  - `Ingest News`
  - `Source + Discovery`
  - scheduler status
  - news upserted count
  - latest RSS/news items
  - X/Twitter credential-blocked status

## Database Objects

- `market.news_ingestion_runs`
- `market.v_news_ingestion_runs`
- `market.v_latest_news_items`
- `strategy.strategy_discovery_scheduler_runs`
- `strategy.v_strategy_discovery_scheduler_runs`

The migration also activates public RSS feed rows in `research.feed_registry` and marks `x_curated_handles` as `blocked_credentials` until authenticated browser/API access is connected.

## Live Source Adapters

Active RSS feeds registered:

- Business Standard Markets RSS
- Economic Times Economy RSS
- Economic Times Markets RSS
- Livemint Markets RSS
- Moneycontrol Business RSS
- Moneycontrol IPO RSS
- Moneycontrol Markets RSS

Blocked adapter:

- X/Twitter curated handles: `blocked_credentials`

Reason: it requires authenticated browser control or API credentials. The system records this explicitly instead of pretending the source is live.

## Verification Evidence

Migration applied successfully.

Compile checks passed:

- `_ai_os_runtime/scripts/ingest_market_news.py`
- `_ai_os_runtime/scripts/run_strategy_discovery_scheduler.py`
- `_ai_os_runtime/scripts/run_agent_message_daemon.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`

React build passed:

- `npm run build`

Services restarted successfully:

- API: `http://127.0.0.1:8765/api/health`
- UI: `http://127.0.0.1:5177/`

API health returned `ok: true`.

## Smoke Runs

Direct RSS ingestion:

- Run key: `news_smoke_20260707`
- Status: completed
- Feeds checked: 3
- Items seen: 9
- Items upserted: 9
- Research ideas created: 1
- Seed data allowed: false

Direct scheduler:

- Run key: `discovery_scheduler_smoke_20260707`
- Status: completed
- News status: completed
- News items upserted: 9
- Discovery run: `discovery_scheduler_smoke_20260707_discovery`
- Discovered: 8
- Generated ideas: 8
- Optimizer routed: 1
- X/Twitter: `blocked_credentials`

API scheduler:

- Run key: `discovery_scheduler_api_smoke_20260707`
- Status: completed
- News status: completed
- News items upserted: 4
- Discovery generated ideas: 6
- Optimizer routed: 1

MCP scheduler:

- Run key: `discovery_scheduler_mcp_smoke_20260707`
- Status: completed
- Tools present:
  - `ai_os_ingest_market_news`
  - `ai_os_run_strategy_discovery_scheduler`
  - `ai_os_strategy_discovery_scheduler_runs`
- News status: completed
- Discovery generated ideas: 5
- Optimizer routed: 1

Direct news API:

- Run key: `news_api_smoke_20260707`
- Status: completed
- Feeds checked: 1
- Items upserted: 2

## Live Database Counts

As of verification:

- `market.news_items`: 9
- `market.news_ingestion_runs`: 5
- `strategy.strategy_discovery_scheduler_runs`: 3
- `strategy.strategy_discovery_runs`: 7
- `strategy.strategy_discovery_candidates`: 51
- `research.ideas` where `idea_type = 'news_catalyst'`: 1

Latest scheduler runs:

| Run key | Status | Discovered | Generated ideas | Optimizer routed | News | X/Twitter |
|---|---:|---:|---:|---:|---|---|
| `discovery_scheduler_mcp_smoke_20260707` | completed | 5 | 5 | 1 | completed | blocked_credentials |
| `discovery_scheduler_api_smoke_20260707` | completed | 6 | 6 | 1 | completed | blocked_credentials |
| `discovery_scheduler_smoke_20260707` | completed | 8 | 8 | 1 | completed | blocked_credentials |

## UI Verification

Playwright loaded the AI Office UI and confirmed:

- `Strategy Discovery Agent`
- `Ingest News`
- `Source + Discovery`
- `NEWS UPSERTED`
- `X/TWITTER` with `blocked`
- Live RSS/news rows from Economic Times / Business Standard style feeds
- `broker false`

## Safety Gates

- `seed_data_allowed = false`
- `live_execution_allowed = false`
- No broker orders
- No autonomous live strategy activation
- X/Twitter/social ingestion blocked until credentials/browser approval exists
- News-sourced ideas are hypotheses requiring source validation, price reaction checks, portfolio impact review, model validation, committee review, and paper monitoring.

## Remaining Gaps

- NSE/BSE filing collection is already implemented but not enabled by default inside the scheduler because public sites can block or slow the daemon; it can be enabled with `--enable-filings` or `AI_OS_STRATEGY_DISCOVERY_ENABLE_FILINGS=1`.
- X/Twitter requires authenticated browser/API setup before it can become a live adapter.
- Feed quality scoring is deterministic v1; later versions should add source reliability, duplicate clustering, and position-impact scoring.
- Qdrant indexing should be scheduled after news ingestion so news/social rows become semantic-memory searchable automatically.

## Recommended Next Slice

Build the triage and promotion inbox:

- Charlie/Jarvis review queue for scheduler-generated ideas
- News Analyst materiality scorecard
- Special Situations handoff for filings/news catalysts
- Quant Lab handoff from discovered idea to paper portfolio
- scheduled Qdrant indexing after source ingestion
- UI action to approve, reject, or request more evidence for each discovered idea
