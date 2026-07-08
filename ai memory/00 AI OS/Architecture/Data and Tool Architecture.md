# Data and Tool Architecture

## Storage

### Obsidian

Use for:

- Research notes
- Investment memos
- Meeting notes
- Daily briefs
- Decision logs
- Runbooks
- Agent outputs

### SQLite

Use first for:

- Holdings
- Transactions
- Watchlists
- Company master data
- Prices
- Fundamental snapshots
- Research task status
- Source document metadata

Move to PostgreSQL later if the system needs concurrent users, server deployment, or heavier analytics.

### Vector Database

Use for semantic retrieval over:

- Obsidian notes
- Annual reports
- Earnings transcripts
- Research PDFs
- Code documentation

Recommended first choices:

- Chroma for fast local setup
- LanceDB if you want file-based local storage and analytical workflows
- Qdrant if you want a more service-like vector database

## Tool Layer

### Finance

Initial:

- Yahoo Finance or equivalent price source
- NSE/BSE data source
- Company filings and annual reports
- Earnings call transcripts
- Manual CSV imports where APIs are unreliable

Later:

- Zerodha Kite Connect
- TradingView alerts
- Broker reconciliation
- Paid market data

### Development

- Terminal
- Git
- GitHub
- Python
- Docker when needed
- Browser automation for web workflows

### Knowledge

- Obsidian filesystem
- PDF parser
- Markdown parser
- Vector indexer
- SQLite database

### Automation

- Scheduled daily brief
- Filing/transcript ingestion
- Watchlist event monitor
- Portfolio risk check
- Research note updater

## Safety Boundary

Do not automate order placement in phase 1. The system can research, alert, simulate, and draft actions, but actual trading requires explicit human approval.

