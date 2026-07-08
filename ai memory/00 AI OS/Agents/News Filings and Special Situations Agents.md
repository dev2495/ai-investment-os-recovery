# News Filings and Special Situations Agents

## Goal

Add a research-intelligence layer that monitors filings, news, and curated social sources to generate actionable research leads.

This is an add-on layer over the core portfolio/trading OS.

## Agents

### News Analyst

Responsibilities:

- Curate market, company, sector, macro, and global news.
- Tag symbols, sectors, countries, and topics.
- Score relevance to current holdings, watchlist, and client folios.
- Produce daily and intraday alert summaries.

Sources:

- Global market news providers.
- Company announcements.
- Curated RSS/news feeds.
- Curated public X/Twitter lists where permitted.

### Filings Analyst

Responsibilities:

- Track NSE/BSE corporate announcements and filings.
- Extract filing type, dates, entities, numbers, and event terms.
- Summarize filings into facts, assumptions, risks, and follow-ups.
- Link filings to holdings, watchlists, and ideas.

### Special Situations Agent

Responsibilities:

- Detect event-driven opportunities:
  - Demergers
  - Reverse mergers
  - Mergers
  - Buybacks
  - Delistings
  - Rights issues
  - Open offers
  - Pledges and pledge release
  - Preferential allotments
  - Scheme of arrangement
  - Holding company discounts
  - Stub-value opportunities
- Generate research tasks, not final trade orders.
- Send high-risk or money-related actions to Approval Center.

## Database Tables

- `research.corporate_filings`
- `research.filing_events`
- `research.ideas`
- `market.news_items`
- `market.social_items`
- `ops.browser_runs`

## Output Standard

Every idea must include:

- Source filing/news link.
- Extracted facts.
- Why it may matter.
- Possible trade/investment thesis.
- What could be wrong.
- Required follow-up research.
- Approval status if any action is proposed.

