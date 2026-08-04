---
title: Sector Taxonomy and BSE Filing Intake v1
date: 2026-08-04
status: verified-milestone
programs:
  - Sector Intelligence, Custom Indices, And Flow Engine
  - Fundamental Research Factory And Long-Term Investment Committee
---

# Sector Taxonomy and BSE Filing Intake v1

## Claim Boundary

This closes a current-constituent and filing-ingestion milestone. It does not complete the Sector Intelligence office, Fundamental Research Factory, or Institutional Options Desk. Broker writes remain disabled.

## Official Nifty Sector Intake

Source: [Nifty sectoral indices](https://www.niftyindices.com/indices/equity/sectoral-indices).

- Effective date: 2026-07-31, the last trading day of the previous month.
- Official sector baskets: 11.
- Source constituent rows: 151.
- Taxonomy nodes: 24.
- Effective-dated memberships: 302.
- Membership roles: official index constituent and source-provided industry label.
- Instrument type: equity.
- Source artifact: `sha256://b5be15fa8d00ca69aa1804932b57e00f12b8e514ed5cb244a72797286017a120`.
- Import package: `9833a63f7b0a3c770c34c61fd9b53d4ec03f9ee89576ca57918d68e52a253ce5`.
- SSD evidence: `/Volumes/Devarsh SSD/AI OS Data/imports/nifty-sector/2026-08-04/`.
- Pre-import database backup: `ai_os-pre-sector-20260804T120237Z.dump`.
- Backup SHA-256: `8627eeac50ba3a882f989f101c29a49ed87f827e6162966ac899ad9aa31a2325`.

The Nifty IT acceptance run passed only current effective membership evidence. Nine gates remain blocked: point-in-time weights, reconciled history, aggregates and valuation breadth, relative strength and breadth, flows and ownership, sector dossier, committee dissent, portfolio fit, and TradingView handoff.

## BSE Corporate Filing Intake

The collector now uses bounded verified curl transport for BSE because the standalone macOS Python urllib transport repeatedly timed out while system curl succeeded. HTTP 200 payloads with `Status:false` are treated as failed source runs.

Accepted run 11:

- Raw source rows seen: 100.
- Durable unique filings: 99.
- Durable filing events: 99.
- Specialist inbox items created: 34.
- Durable event mix: 32 board actions, 1 insolvency, 1 merger, and 65 routine filings.
- HTTP status: 200.
- Run status: completed.

A later one-row health probe captured one newly arrived filing in run 13. Run 12 was corrected to failed after BSE returned `Status:false` with an exchange error message. Re-observation no longer overwrites the original collector-run ownership of existing filing evidence.

## Runtime and Tests

- Focused suite: 14 passed.
- API health: `ok=true`; Postgres status `ok`.
- UI: HTTP 200.
- TradingView Desktop: installed and running; user-managed session.
- TradingView authority: chart workspace only, not warehouse or execution.
- Broker writes: false.
- Git checkpoint: `ebf7a8c`.

## Remaining Institutional Gates

1. Add broad Indian sector and sub-industry taxonomy with historical constituent membership.
2. Add point-in-time free-float, market-cap, equal-weight, quality, momentum, and custom-index histories.
3. Add sector financial aggregates, valuation bands, revisions, breadth, delivery, derivatives, ownership, and flow datasets.
4. Run sector specialist work, sealed committee discussion, portfolio fit, dossier generation, and native TradingView handoff.
5. Populate 10-15 year company statements, segments, KPIs, peers, transcripts, management claims, and complete company dossiers.
6. Activate Zerodha minute option-chain capture, deterministic IV and Greeks, replay, surfaces, exposure analytics, specialist briefs, and paper attribution.
7. Pass all three real-data acceptance programs before describing the system as a complete autonomous hedge fund.
