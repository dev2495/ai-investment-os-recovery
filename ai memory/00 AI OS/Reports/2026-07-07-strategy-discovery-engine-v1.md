# Strategy Discovery Engine v1

Date: 2026-07-07
Owner: Strategy Discovery Agent
Status: completed for foundation v1

## Outcome

The AI OS now has an automatic strategy discovery loop that reads the existing research, journal, signal, and component-pattern spine, turns those sources into structured strategy candidates, writes generated ideas to the strategy schema, and can route top testable ideas into the user-defined strategy optimizer.

This is still gated as research and paper-test infrastructure. Broker execution and autonomous live execution remain disabled.

## What Was Built

- Migration: `_ai_os_runtime/postgres/init/092_strategy_discovery_engine_v1.sql`
- Scanner: `_ai_os_runtime/scripts/run_strategy_discovery.py`
- API: `POST /api/strategy/discovery/run`
- MCP tools:
  - `ai_os_run_strategy_discovery`
  - `ai_os_strategy_discovery_runs`
- AI Office UI:
  - `Strategy Discovery Agent` dashboard panel
  - `Run Discovery` action
  - candidate stream with source, asset, horizon, confidence, gate, optimizer status, and rationale
- Report artifact output:
  - `artifacts/strategy_discovery/<run_key>.json`

## Source Coverage

The scanner currently uses only real system tables and reference components. It does not use seed data.

- Research ideas and watchlist entries from `research.ideas`
- Journal-derived strategy patterns from prior trade-journal mining output
- Trading signals from `trading.signals`
- Component patterns from `core.source_components`, including imported/reference systems such as Fincept/OpenAlgo/Vibe-style components where already registered in the stack

## Verification Evidence

Migration applied successfully against the live Postgres database on the external SSD runtime.

Python compile checks passed for:

- `_ai_os_runtime/scripts/run_strategy_discovery.py`
- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/mcp_server/ai_os_mcp_server.py`

React build passed for the AI Office UI.

API health passed at:

- `http://127.0.0.1:8765/api/health`

Direct script smoke:

- Run key: `discovery_smoke_20260707`
- Status: completed
- Discovered: 10
- Generated ideas: 10
- Optimizer routed: 2
- Artifact: `artifacts/strategy_discovery/discovery_smoke_20260707.json`

API smoke after duplicate-name fix:

- Run key: `discovery_api_smoke2_20260707`
- Status: completed
- Discovered: 8
- Generated ideas: 8
- Optimizer routed: 1
- First optimizer status: completed
- Artifact: `artifacts/strategy_discovery/discovery_api_smoke2_20260707.json`

MCP smoke:

- Tool discovery confirmed `ai_os_run_strategy_discovery`
- Tool discovery confirmed `ai_os_strategy_discovery_runs`
- Run key: `discovery_mcp_smoke_20260707`
- Status: completed
- Discovered: 6
- Generated ideas: 6
- Optimizer routed: 1
- Artifact: `artifacts/strategy_discovery/discovery_mcp_smoke_20260707.json`

UI smoke:

- AI Office page loaded at `http://127.0.0.1:5177/`
- `Strategy Discovery Agent` panel visible
- `Run Discovery` action visible
- Candidate rows visible
- Broker/autonomous execution indicator remained false

## Live Database Counts

As of verification:

- `strategy.strategy_discovery_runs`: 4
- `strategy.strategy_discovery_candidates`: 32
- `strategy.generated_ideas` where `idea_type = 'automatic_strategy_discovery'`: 32
- Discovery candidates with `optimizer_status = 'completed'`: 4

Latest run evidence:

| Run key | Status | Discovered | Generated ideas | Optimizer routed |
|---|---:|---:|---:|---:|
| `discovery_mcp_smoke_20260707` | completed | 6 | 6 | 1 |
| `discovery_api_smoke2_20260707` | completed | 8 | 8 | 1 |
| `discovery_api_smoke_20260707` | completed | 8 | 8 | 0 |
| `discovery_smoke_20260707` | completed | 10 | 10 | 2 |

## Bug Found And Fixed

The first API smoke exposed a real duplicate-name collision in the downstream optimizer path because multiple discovery runs could route the same source idea title into `strategy.strategy_candidates`.

Fix implemented:

- Discovery-routed optimizer strategy names now include the discovery run key and candidate index.
- This preserves source-title readability while making optimizer candidate names unique.

Verification after the fix:

- `discovery_api_smoke2_20260707` routed a candidate into the optimizer and completed.
- `discovery_mcp_smoke_20260707` routed a candidate into the optimizer and completed.

## Safety Gates

- `seed_data_allowed = false`
- `live_execution_allowed = false`
- No broker order placement
- No autonomous live strategy activation
- Candidates are research/optimization artifacts until they pass validation, promotion board review, and explicit human approval.

## Current Limits

- External web discovery adapters are not yet live in this scanner.
- Component patterns are reference inputs; most still need symbol-specific adapter code before they become robust strategy generators.
- Current OHLCV coverage is useful for smoke/backtest plumbing but still too thin for institutional validation.
- Strategy quality is intentionally conservative: many ideas will be rejected or gated until data depth improves.

## Recommended Next Slice

Build the scheduled discovery and external-source adapter layer:

- Scheduled daily strategy discovery job
- NSE/BSE filings and announcements adapter
- News and X/Twitter research ingestion adapter
- Fincept/OpenAlgo/Vibe component-to-strategy adapter
- Discovery triage inbox for Charlie/Jarvis/Quant Lab review
- Promotion-board handoff from discovered idea to paper portfolio

This makes the engine operate continuously instead of only on manual runs.
