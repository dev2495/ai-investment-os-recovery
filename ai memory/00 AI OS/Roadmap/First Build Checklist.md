# First Build Checklist

## Objective

Build the smallest useful AI OS loop:

Research one company, save the output to Obsidian, store structured fields in SQLite, retrieve the note semantically, and generate a follow-up action.

## Step 1 - Vault Conventions

- Confirm folder structure
- Confirm note templates
- Confirm naming rules
- Confirm source citation style

## Step 2 - Database

- Create SQLite database
- Add company table
- Add source document table
- Add research note table
- Add watchlist table

## Step 3 - Ingestion

- Import one annual report or transcript
- Extract metadata
- Save raw source location
- Create summary note

## Step 4 - Retrieval

- Index markdown notes
- Index imported source text
- Test semantic search
- Return source-linked snippets

## Step 5 - Agent Run

- Ask Jarvis to research one company
- Route to Equity Research Agent
- Route to Valuation Agent
- Route to Risk Agent
- Save final memo

## Step 6 - Verification

- Confirm note exists
- Confirm database rows exist
- Confirm retrieval finds the note
- Confirm final memo cites sources

## Definition of Done

The system can answer:

"What do we know about this company, what is the current thesis, what evidence supports it, what risks matter, and what should I do next?"

