# Live Agent Team And Skills Foundation Report

Date: 2026-07-05
Status: Completed

## What Changed

The AI OS now has a live agent-team foundation instead of only queued dashboard jobs.

New migration:

- `_ai_os_runtime/postgres/init/029_live_agent_team_and_skills.sql`

New worker:

- `_ai_os_runtime/scripts/run_agent_worker_once.py`

Updated surfaces:

- `_ai_os_runtime/api/ai_os_api_server.py`
- `_ai_os_runtime/ai-office-ui/src/api/live.ts`
- `_ai_os_runtime/ai-office-ui/src/App.tsx`
- `_ai_os_runtime/ai-office-ui/src/styles.css`

## Live Operating Loop

Current live loop:

1. Dashboard widget jobs exist in `agent.v_live_agent_worker_queue`.
2. Jarvis/worker chooses the correct specialist skill.
3. The job routes to the primary specialist agent for that skill.
4. The worker reads bounded live warehouse context.
5. The worker writes an Obsidian output note.
6. The worker logs the run in `agent.worker_runs`.
7. The source task moves to `needs_review`.
8. The dashboard widget gets a refreshed timestamp and evidence.

This is deterministic and evidence-backed for now. LLM-heavy reasoning can be added per skill after the manual worker loop is reviewed.

## Agent Departments

Departments registered:

- Executive Office
- Runtime Operations
- Portfolio Office
- Research Desk
- News Intelligence
- Quant Lab
- Trading Desk
- Risk and Compliance
- Data Engineering
- Knowledge and Memory
- Automation Engineering

Counts verified:

- departments: 11
- profiles: 21
- active agents: 20
- skills: 30
- skill mappings: 45

## Active Core Agents

Primary operating agents now represented in the live DB:

- Charlie Munger: Chief Investment Orchestrator
- Jarvis: Runtime Operator
- Portfolio Manager
- Research Analyst
- News Analyst
- Filings Analyst
- Special Situations Agent
- Strategy Generator
- Strategy Intake Agent
- Strategy Research Agent
- Backtest Engineer
- Model Validation Agent
- Optimizer Agent / Strategy Optimizer role
- Trading Desk Agent
- Trade Journal Learning Agent
- Execution Safety Agent
- Risk Agent / Risk Officer role
- Data Steward
- Librarian Agent / Knowledge Librarian role
- Browser Research Runner

Automation Engineer is registered as planned, not active.

## Key Skills Added

Core skills:

- `route_user_request`
- `refresh_dashboard_widget`
- `write_obsidian_note`
- `portfolio_snapshot_review`
- `portfolio_daily_brief`
- `manual_holding_update_review`
- `company_research_note`
- `analyze_corporate_filing`
- `detect_special_situation`
- `strategy_intake_structuring`
- `generate_strategy_hypothesis`
- `strategy_lab_review`
- `queue_backtest`
- `optimize_strategy_parameters`
- `validate_strategy_model`
- `tradingview_chart_task`
- `monitor_strategy_alerts`
- `manual_trade_log`
- `paper_trade_log`
- `trade_journal_learning`
- `risk_gate_review`
- `portfolio_concentration_check`
- `source_data_ingestion_review`
- `model_runtime_check`
- `daily_office_brief`

## News Skills

News and filings skills registered:

- `nse_bse_announcement_monitor`
- `corporate_action_detector`
- `global_market_news_digest`
- `twitter_x_watchlist_triage`
- `news_to_dashboard_alert`
- `analyze_corporate_filing`
- `detect_special_situation`

Recommended news stack build order:

1. NSE/BSE announcement collector.
2. Corporate action classifier.
3. Filing PDF/document parser.
4. Global market RSS/news digest.
5. Twitter/X watchlist triage with rumor/source labels.
6. Special situation screener for demerger, merger, buyback, open offer, delisting, restructuring, pledging, and block/bulk deals.
7. News-to-dashboard alert router.

## Worker Runs Produced

Latest specialist worker runs:

- task 10: Portfolio Manager, `portfolio_snapshot_review`
- task 9: Trading Desk Agent, `monitor_strategy_alerts`
- task 8: Strategy Generator, `strategy_lab_review`
- task 7: Filings Analyst, `analyze_corporate_filing`
- task 6: Jarvis, `model_runtime_check`

Latest output notes:

- `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-05 task-10 portfolio-manager portfolio-snapshot-review.md`
- `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-05 task-9 trading-desk-agent monitor-strategy-alerts.md`
- `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-05 task-8 strategy-generator strategy-lab-review.md`
- `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-05 task-7 filings-analyst analyze-corporate-filing.md`
- `ai memory/00 AI OS/Agent Outputs/Worker Runs/2026-07-05 task-6 jarvis model-runtime-check.md`

## UI Changes

AI Office now exposes:

- Agent Departments
- Agent Skill Matrix
- Agent Jobs with suggested skills
- Run agents button
- Worker Runs panel

The UI now reads:

- `agent.v_agent_departments`
- `agent.v_agent_skill_matrix`
- `agent.v_live_agent_worker_queue`
- `agent.v_recent_worker_runs`

## API Changes

New API endpoint:

- `POST /api/agents/worker/run`

Expanded `GET /api/snapshot`:

- `agent_departments`
- `agent_skills`
- `agent_worker_queue`
- `agent_worker_runs`

## Verification

Build/compile:

- `python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/scripts/run_agent_worker_once.py` passed.
- `npm run build` passed for `_ai_os_runtime/ai-office-ui`.

Runtime:

- API health: OK
- UI: HTTP 200 at `http://127.0.0.1:5177/`
- Worker endpoint: `POST /api/agents/worker/run` returned `count: 0` after the specialist worker pass, meaning no unprocessed dashboard jobs remained.
- Snapshot issues: 0

Snapshot counts:

- clients: 3
- latest positions: 71
- active agents: 20
- departments: 11
- skills: 30
- worker queue rows: 5
- worker runs: 15
- dashboard widgets: 5

TradingView CDP:

- currently unavailable on port 9222
- next action: relaunch TradingView Desktop with remote debugging enabled before desktop MCP control

## Team Still Needed

Next planned agents/departments to add after this foundation:

- Client Reporting Agent: generate client-ready portfolio/report packs.
- Broker Sync Agent: read-only Zerodha/Dhan holdings, orders, positions, and trades.
- Market Data Engineer: OHLCV/tick/option-chain/commodity/crypto data quality.
- Notification Agent: WhatsApp/email/desktop alerts after approval policy is defined.
- Compliance/QC Agent: checks client-facing reports and trade logs before sharing.
- Tax/Corporate Action Agent: dividend, split, bonus, rights, buyback, tax-impact workflow.
- Browser Execution Agent: safe browser automation for TradingView, NSE/BSE, broker statements, and evidence screenshots.

## Next Build Step

Turn the manual worker into a scheduled daemon:

1. Run `agent_worker_run_once` every 5-15 minutes.
2. Add per-skill LLM reasoning only where deterministic summaries are insufficient.
3. Add source collectors for NSE/BSE, news, filings, and Twitter/X.
4. Add agent output review/close buttons in the UI.
5. Add notification policy after Risk Agent rules are defined.

