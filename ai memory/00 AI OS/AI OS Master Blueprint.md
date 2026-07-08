# AI OS Master Blueprint

## Canonical Investment OS v10 Update

The implementation reference for the investment platform is now:

- [[AI Investment OS - Institutional Master Blueprint v10.0]]
- [[AI Investment OS - Execution Checklist v10.0]]
- [[AI Investment OS - Institutional Master Blueprint v9.0]]
- [[AI Investment OS - Execution Checklist v9.0]]
- [[AI Investment OS - Institutional Master Blueprint v8.0]]
- [[AI Investment OS - Execution Checklist v8.0]]
- [[AI Investment OS - Institutional Master Blueprint v7.0]]
- [[AI Investment OS - Execution Checklist v7.0]]
- [[AI Investment OS - Master Blueprint v6.0]]
- [[AI Investment OS - Master Build Checklist v6.0]]
- [[AI Investment OS - Master Blueprint v5.0]]
- [[AI Investment OS - Master Build Checklist v5.0]]
- [[AI Investment OS - Master Blueprint v2.0]]
- [[AI Investment OS - Master Implementation Checklist v2.0]]
- [[AI Investment OS - Master Blueprint v1.0]]
- [[AI Investment OS - Master Build Checklist]]

The major architecture decision is now fixed:

- Build one shared AI Investment OS data, tool, model, risk, and knowledge backbone.
- Separate investment decisions by book and horizon: Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, and Hedges.
- Put Capital Allocation and Risk above the books.
- Require every position to carry a book, purpose, owner, thesis, horizon, exit criteria, and evidence.
- Keep Obsidian as durable memory and the AI Office GUI as the live operating surface.

Older notes remain useful background, but new implementation work should follow the canonical v10.0 blueprint and execution checklist above.

## Mission

Build a personal AI operating system for investing, research, coding, automation, and business execution.

This is not a chatbot. It is a coordinated agent system with:

- Obsidian as long-term memory and source of truth
- Structured databases for portfolio and operational data
- Vector search for retrieval over notes and documents
- Tool access through MCPs, scripts, browser automation, terminal, and APIs
- Charlie Munger as the main orchestrator, using Jarvis as the runtime/tool layer
- Repeatable workflows for research, coding, portfolio review, and daily execution

## Core Principle

Every important output should end in one of three places:

- A structured Obsidian note
- A database record
- A committed code or automation artifact

## System Layers

1. Knowledge layer: Obsidian markdown vault, templates, source documents, decisions, and research notes.
2. Retrieval layer: vector index over vault content and imported PDFs/transcripts.
3. Data layer: PostgreSQL warehouse for live structured data, with SQLite only for small local utilities when useful.
4. Tool layer: finance APIs, browser automation, terminal, GitHub, local filesystem, email, calendar, and document parsers.
5. Agent layer: Charlie Munger orchestrator, Jarvis runtime, and specialist agent teams.
6. Model layer: local models for fast/private tasks, cloud models for hard reasoning and long-document synthesis.
7. Interface layer: Obsidian, terminal, dashboards, scheduled briefings, and eventually a dedicated UI.

The detailed human-agent interaction contract is [[Agent Interaction Model]].

## Initial Build Choice

The current build is local-first but warehouse-backed:

- Obsidian vault for memory
- PostgreSQL for structured portfolio/research/trading data
- Qdrant for vector search
- Python scripts for ingestion and automation
- Codex/terminal for implementation
- Charlie Munger prompt/router as the first orchestrator, with Jarvis as runtime

Do not begin with a complex multi-agent runtime until the notes, schemas, and workflows are stable.

## Non-Negotiables

- Source citations for financial research
- Clear separation between facts, assumptions, and opinions
- No trade/order automation until research, risk checks, and approval flows are mature
- Every agent must write durable output back to the vault
- Repeated errors trigger research before more trial-and-error
