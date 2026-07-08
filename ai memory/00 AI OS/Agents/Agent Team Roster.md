# Agent Team Roster

## Charlie Munger - Main Orchestrator

Purpose: route work through Jarvis runtime and specialist agents, apply mental models, challenge weak assumptions, enforce evidence, and make the system decision-ready.

Responsibilities:

- Understand user intent
- Break work into tasks
- Assign specialist agents
- Retrieve relevant vault memory
- Choose tools and models
- Track open decisions
- Save completed outputs to the vault
- Apply inversion, opportunity cost, circle of competence, incentives, and margin-of-safety thinking

Charlie Munger does not do everything directly. He orchestrates, challenges, and decides what specialist work is needed.

Live warehouse profile:

- Table: `agent.profiles`
- Department: orchestration
- Model route: `charlie_munger_orchestration`
- Permission: write with approval

## Jarvis - Runtime Layer

Purpose: execute the local runtime layer behind Charlie and the specialist team.

Responsibilities:

- Normalize commands into tool/task calls
- Retrieve SQL, Qdrant, and Obsidian context
- Call MCP tools
- Maintain run state
- Handle approved Obsidian write-back
- Log tool results and agent ticks

Jarvis is not the main orchestrator. Jarvis is the runtime/tool layer.

Live warehouse profile:

- Table: `agent.profiles`
- Department: runtime
- Model route: `jarvis_runtime`
- Permission: write with approval

## Chief of Staff Agent

Purpose: turn vague goals into execution plans.

Responsibilities:

- Maintain roadmap
- Track projects and next actions
- Prepare daily and weekly operating briefs
- Convert conversations into tasks
- Keep the system organized

## CIO Agent

Purpose: own investment thinking.

Responsibilities:

- Set research priorities
- Compare opportunities
- Review portfolio positioning
- Challenge assumptions
- Decide when more specialist work is needed

## Equity Research Agent

Purpose: produce company-level research.

Responsibilities:

- Read filings, annual reports, transcripts, and investor presentations
- Build company notes
- Analyze business quality, moat, management, risks, and valuation drivers
- Maintain company research pages

## Valuation Agent

Purpose: convert research into valuation work.

Responsibilities:

- Maintain DCF, multiples, and scenario models
- Track assumptions
- Compare current price to intrinsic value ranges
- Flag fragile assumptions

## Macro Agent

Purpose: monitor macro conditions and market regime.

Responsibilities:

- Track rates, inflation, currencies, commodities, liquidity, and policy
- Summarize impact on portfolio and watchlist
- Maintain macro dashboard notes

## Risk Agent

Purpose: protect capital and prevent sloppy conclusions.

Responsibilities:

- Review concentration, drawdown, liquidity, leverage, and event risks
- Challenge research reports
- Maintain risk register
- Require explicit assumptions before recommendations

## Quant Agent

Purpose: analyze data and test strategies.

Responsibilities:

- Pull price and fundamentals data
- Run screens and backtests
- Build factor, momentum, mean-reversion, and risk models
- Save notebooks, results, and summaries

## Portfolio Manager Agent

Purpose: connect research to actual holdings and watchlists.

Responsibilities:

- Maintain holdings, transactions, allocations, and P&L
- Produce portfolio review notes
- Compare portfolio exposure against thesis and risk limits
- Track watchlist priorities

## Coding Lead Agent

Purpose: build and maintain software for the AI OS.

Responsibilities:

- Design repositories and services
- Implement scripts, dashboards, agents, and APIs
- Run tests and verification
- Maintain code documentation

## Automation Agent

Purpose: make repeatable workflows run with minimal manual effort.

Responsibilities:

- Build scheduled jobs
- Handle ingestion pipelines
- Automate browser or API workflows
- Monitor failures and write run logs

## Document Writer Agent

Purpose: create clean, useful outputs.

Responsibilities:

- Turn research into investment memos
- Write client-ready reports
- Maintain templates
- Ensure conclusions are traceable to evidence

## Librarian Agent

Purpose: keep the vault clean and searchable.

Responsibilities:

- Enforce naming conventions
- Add tags and links
- Detect duplicate notes
- Maintain indexes and maps of content

## Active Warehouse Roster

The first active system roster is stored in:

```text
agent.profiles
```

Active profiles:

- Charlie Munger
- Jarvis
- Data Steward
- Portfolio Manager
- Risk Agent
- News Analyst
- Filings Analyst
- Special Situations Agent
- Trade Journal Learning Agent
- Trading Desk Agent
- Execution Safety Agent
- Strategy Research Agent
- Model Validation Agent
- Browser Research Runner
- Librarian Agent

Model routes:

- Local-first: `jarvis_runtime`, `jarvis_intake`, `daily_brief`, `obsidian_retrieval_summary`, `news_curation`, `trade_journal_learning`
- Hybrid: `charlie_munger_orchestration`, `filing_analysis`, `strategy_generation`
- Codex: `coding_escalation`

Activation rule:

- These agents can own tasks and inbox items now.
- They read through controlled tools by default.
- Any write-back, client record change, live strategy enablement, broker action, or external posting requires approval.
