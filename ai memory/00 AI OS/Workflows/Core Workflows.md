# Core Workflows

## Daily Brief

Trigger: morning startup.

Steps:

1. Pull market calendar, news, watchlist changes, and portfolio movements.
2. Retrieve relevant existing notes.
3. Flag earnings, filings, price gaps, risk events, and pending tasks.
4. Produce a short daily brief.
5. Save the brief to `09 Journal/Daily Briefs`.

Output:

- Market overview
- Portfolio alerts
- Watchlist alerts
- Research priorities
- Coding or automation tasks

## Company Research

Trigger: "Research [company]".

Steps:

1. Find or create company note.
2. Pull existing vault notes.
3. Gather filings, annual reports, transcripts, presentations, and price history.
4. Summarize business, segments, management, moat, risks, and key financials.
5. Ask Valuation Agent for model assumptions.
6. Ask Risk Agent to challenge the thesis.
7. Write investment memo.
8. Save all outputs to the company folder.

Output:

- Company note
- Source log
- Investment memo
- Valuation assumptions
- Risk register entries

## Portfolio Review

Trigger: weekly or on demand.

Steps:

1. Load holdings and transactions.
2. Compare weights, P&L, risk exposure, and thesis status.
3. Check recent news and filings for each holding.
4. Flag broken theses and concentration risks.
5. Save review note.

Output:

- Portfolio summary
- Risk flags
- Action candidates
- Research follow-ups

## Coding Request

Trigger: "Build/fix/create [software task]".

Steps:

1. Clarify objective and existing repo state.
2. Inspect files before editing.
3. Make a scoped plan.
4. Implement.
5. Run tests or equivalent verification.
6. Save technical decision or runbook when useful.

Output:

- Code changes
- Test results
- Run notes
- Follow-up tasks

## Error Handling Rule

If the same error happens twice:

1. Stop repeating the same approach.
2. Research the web for 3-5 likely fixes.
3. Pick the fastest defensible fix.
4. Implement it.
5. Verify the result.

