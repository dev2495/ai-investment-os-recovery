# AI Office Operating Model

## Goal

Create an AI office where Charlie Munger coordinates specialist agents across client work, investing, trading, coding, research, and operations, using Jarvis as the runtime/tool layer.

## Office Structure

### Executive Layer

- Charlie Munger: main orchestrator
- Jarvis: runtime/tool layer
- Chief of Staff Agent: planning, priorities, execution tracking
- Librarian Agent: vault hygiene and knowledge organization

### Client and Business Layer

- Client Data Steward: maps client databases, protects sensitive data, prepares safe summaries
- Business Analyst Agent: extracts KPIs, issues, reports, and workflows from client data
- Client Report Writer: creates client-ready reports and explanations

### Investing Layer

- CIO Agent: investment judgment and prioritization
- Equity Research Agent: company research
- Valuation Agent: DCF, multiples, assumptions
- Risk Agent: thesis challenge, concentration, downside, compliance boundary
- Portfolio Manager Agent: holdings, P&L, allocation, watchlists

### Trading Layer

- Trading Desk Agent: monitors signals, charts, alerts, and setups
- Quant Agent: backtests, factors, regime, optimization
- Execution Safety Agent: prevents uncontrolled live trading and checks risk limits
- Market Data Agent: maintains prices, OHLCV, symbol maps, and corporate actions

### Engineering Layer

- Coding Lead Agent: builds the system
- MCP Toolsmith Agent: exposes internal tools through MCP
- Automation Agent: schedules jobs and monitors failures
- DevOps Agent: local services, dashboards, backups, deployments

## Start Order

1. Inventory existing systems and data boundaries.
2. Create read-only connectors.
3. Build a registry of tools agents are allowed to call.
4. Build Charlie Munger routing over those tools, with Jarvis runtime executing retrieval and MCP calls.
5. Add specialist agents one by one.
6. Add scheduled workflows.
7. Add write access only after audit logs and approval gates exist.

## Interaction Model

The canonical interaction model is defined in [[Agent Interaction Model]].

Daily work should happen through:

- Command Bar
- Agent Inbox
- Workspaces
- Approval Center

Charlie Munger is the visible coordinator. Jarvis, Hermes, local models, Codex, MCP servers, and other runtimes are backend components, not the permanent source of truth.

## First Three Agents To Activate

### 1. Charlie Munger

Routes work, challenges assumptions, chooses specialist agents, and uses Jarvis runtime to retrieve context and write approved outputs to Obsidian.

### 2. Jarvis

Runtime/tool layer for MCP calls, retrieval, run logging, and approved write-back.

### 3. Data Steward

Maps p2cursor, trading databases, client data, and safe read-only views.

### 4. Trading Desk Agent

Uses the existing algo trading repo to read signals, charts, portfolio state, watchlists, and TradingView webhook events.

Do not start with 20 agents. Start with these four, then add Quant, Risk, Portfolio Manager, and Client Report Writer.
