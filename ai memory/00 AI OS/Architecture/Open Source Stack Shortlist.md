# Open Source Stack Shortlist

## Decision

Use open-source projects as components, not as the whole AI OS.

The core system should be:

- Live data warehouse from existing client/trading systems
- Read-only MCP tools first
- Jarvis orchestration
- Specialist agent teams
- Obsidian as memory and decision log
- Portfolio, quant, and client reporting agents built around our schemas

## Dexter

Repo:

`https://github.com/virattt/dexter`

Fit:

- Good reference for a financial research agent.
- Useful ideas: task planning, tool execution, scratchpad, financial data tools, evals, skills, multi-provider LLM support.
- Not sufficient as the full AI office foundation.

Use it for:

- Research agent loop design
- Skill pattern
- Scratchpad/logging pattern
- Financial research workflow inspiration

Do not use it for:

- Client data source of truth
- Portfolio database
- Live trading execution
- Full multi-agent office orchestration

Why:

- It is primarily a TypeScript/Bun CLI financial research agent.
- It depends on external finance/search APIs.
- It is explicitly positioned for informational/educational use, not live trading or direct investment decisions.

## FinceptTerminal

Repo:

`https://github.com/Fincept-Corporation/FinceptTerminal`

Fit:

- Strong reference for the eventual AI office GUI and portfolio/research workbench.
- Useful ideas: native dense terminal layout, equity research modules, portfolio analytics, broker connector map, AI agent catalog, MCP/node workflow pattern, local and multi-provider LLM pattern.
- Not safe to fork or merge into the AI OS yet because of the repo's AGPL-3.0 plus commercial-license boundary.

Use it for:

- Product architecture reference.
- Portfolio and research dashboard patterns.
- Agent roster inspiration.
- Connector prioritization.
- Later workflow/node-editor design.

Do not use it for:

- Direct code reuse without license approval.
- Client/internal business deployment through a fork.
- Data source of truth.
- Live trading execution.

Why:

- The repo README states commercial/internal business use requires a commercial license.
- Our AI OS has client/private data and business use, so the clean path is to rebuild needed surfaces around our own warehouse and MCP layer.

## LangGraph

Repo:

`https://github.com/langchain-ai/langgraph`

Fit:

- Best candidate for long-running, stateful agent orchestration.
- Useful for Jarvis plus specialist-agent routing.

Use it for:

- Jarvis state machine
- Supervisor-worker agent flows
- Human approval gates
- Retry and failure states
- Daily/weekly workflow orchestration

## MCP Python SDK

Repo:

`https://github.com/modelcontextprotocol/python-sdk`

Fit:

- Best fit for exposing local databases, trading tools, and client-data adapters to AI agents.

Use it for:

- `trading.*` tools
- `portfolio.*` tools
- `client_data.*` tools
- `vault.*` tools
- Read-only adapters first

Important:

- Use stable v1.x until v2 is stable.

## TimescaleDB

Repo:

`https://github.com/timescale/timescaledb`

Fit:

- Best candidate for the live market-data database because it is PostgreSQL plus time-series features.

Use it for:

- Ticks
- OHLCV candles
- TradingView signals
- Strategy events
- Portfolio snapshots over time
- Risk snapshots over time

Why:

- Keeps SQL/Postgres compatibility.
- Adds hypertables, time buckets, compression, and continuous aggregates.

## Apache Superset

Repo:

`https://github.com/apache/superset`

Fit:

- Good dashboard layer after the data warehouse is stable.

Use it for:

- Client dashboards
- Portfolio dashboards
- Research dashboards
- Trading performance dashboards

Do not make this the agent brain. It is a visualization layer.

## OpenBB

Repo:

`https://github.com/OpenBB-finance/OpenBB`

Fit:

- Strong candidate for market-data and research-data ingestion.

Use it for:

- Public market data
- Fundamentals
- Macro data
- REST/API layer for financial data
- Possible MCP integration

Watch:

- License and provider-data limitations.
- Indian market coverage may still require NSE/BSE/Zerodha/custom adapters.

## Qlib

Repo:

`https://github.com/microsoft/qlib`

Fit:

- Strong candidate for the quant research lab.

Use it for:

- Alpha research
- ML factor modeling
- Backtesting research pipelines
- Model training and evaluation
- Future quant R&D agents

Do not start here first. Qlib is powerful but heavier than the first live-db milestone.

## VectorBT

Repo:

`https://github.com/polakowo/vectorbt`

Fit:

- Strong candidate for fast strategy research and parameter sweeps.

Use it for:

- Backtesting many strategy variations
- Signal experimentation
- Walk-forward testing
- Visualization of performance and trades

## PyPortfolioOpt

Repo:

`https://github.com/PyPortfolio/PyPortfolioOpt`

Fit:

- Good first portfolio optimization library.

Use it for:

- Efficient frontier
- Black-Litterman
- Hierarchical Risk Parity
- Simple allocation experiments

## Riskfolio-Lib

Repo:

`https://github.com/dcajasn/Riskfolio-Lib`

Fit:

- Stronger advanced portfolio/risk engine.

Use it for:

- CVaR
- drawdown risk
- risk parity
- factor risk
- constraints
- more institutional portfolio analytics

## Recommended Start

1. Build live data warehouse and schema registry with PostgreSQL plus TimescaleDB.
2. Build ETL from existing trading/client systems into the live warehouse.
3. Build read-only MCP tools over trading and client data.
4. Use LangGraph for Jarvis orchestration.
5. Use Dexter patterns for the Equity Research Agent.
6. Use OpenBB for external financial data where coverage is useful.
7. Use VectorBT for fast strategy testing.
8. Add PyPortfolioOpt first, then Riskfolio-Lib for advanced portfolio analytics.
9. Add Qlib only after clean data and basic backtesting are working.
10. Add Superset dashboards after core schemas are stable.
