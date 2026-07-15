---
title: Department Terminals, TradingView, and Committee Operations v1
date: 2026-07-15
status: verified
system: AI Investment OS
tags:
  - ai-os
  - frontend
  - agents
  - committees
  - tradingview
  - production-checkpoint
---

# Department Terminals, TradingView, and Committee Operations v1

## Delivered Foundation

- 19 addressable Command Center workspaces, including 15 department desks.
- Scoped production data, freshness, execution-lock state, filters, and evidence paths; no seed fallback.
- Audited persistent widget visibility, order, density, and columns, manageable directly or through Charlie's workspace tools.
- 95 addressable employee profiles with hierarchy, persona, mental models, skills, model route, hard cost cap, readiness, reliability, mailbox, and recent worker history.
- A governed Committee Room for Strategy, Long-Term, and Special Situations.
- Approval-gated TradingView formula, technical-study, and fundamental-study workflows with screenshot and study-level verification.

## Agent And Department Operating Model

Charlie Munger remains Devarsh's chief orchestrator and decision partner. Jarvis is the runtime dispatcher. Fifteen role-scoped departments own executive coordination, portfolio, client, research, quant, trading, risk, data, knowledge, automation, model, software, treasury/macro, compliance/governance, and reporting work. The active organization remains 95 employees, 117 skills, 166 role-skill mappings, 95 mailboxes, 95 model assignments, 95 hard cost caps, 13 recurring schedules, and 11 committee constitutions. The MCP protocol exposes 172 callable tools, including eight committee operations; the broader warehouse registry contains 229 enabled capabilities.

The terminal now makes this organization operational. A selected employee has an addressable URL and a live inspector. Department desks expose bounded operational rows and a persistent widget rail rather than static role descriptions. The final live audit returned 59 bounded worker-history records and the cost/quality view spans all 95 governed model assignments.

## Committee Protocol

The new committee schema retains packets, member positions, discussion, sessions, and follow-ups. Its rules are enforced in Postgres:

1. A packet resolves the source matter and registered constitution.
2. Each member receives one durable role-scoped task, inbox item, and dispatch message.
3. Positions stay sealed until quorum.
4. Discussion requires quorum and the speaker's independent position.
5. Only the registered chair can synthesize the committee recommendation.
6. Minutes, dissent, conditions, and recommendation remain distinct from the named human final decision.
7. Follow-ups retain packet, owner, task, inbox, and message lineage.

Production acceptance used Rolex Rings buyback `special:1`:

- packet `#1`, key `committee-special_situations-20260715124441830`;
- five independent positions and quorum `5/5`;
- three challenges plus discussion `#1` for the risk objection;
- chair recommendation `more_research` with minutes, dissent, and conditions;
- Devarsh final decision `more_research`;
- follow-up `#1`, task `#435`, inbox `#1278`;
- five committee tasks completed and five dispatch messages retained.

## TradingView Controller

The native controller uses the chart's indicator shortcut, real keyboard events, accessibility discovery for virtualized search results, ArrowDown/Enter selection, and visible legend/undo assertions. A failed requested study changes the task to `needs_review`.

Verified production runs:

| Workflow | Approval | Task | Browser run | Artifact | Verified chart state |
|---|---:|---:|---:|---:|---|
| Formula/ratio | 43 | 19 | 14 | 33069 | governed formula-chart completion |
| Technical stack | 44 | 20 | 15 | 37356 | VWAP, Supertrend, RSI, MACD, ATR, Volume |
| Fundamental stack | 45 | 21 | 16 | 37357 | Revenue, Net Income, Operating Margin, ROIC, Total Debt, P/E, P/B |

Artifacts are stored under `/Volumes/Devarsh SSD/AI OS Data/artifacts/tradingview/20260715/`. The controller resolves `AI_OS_ARTIFACT_ROOT` and otherwise defaults to that external artifact root, keeping future captures out of the internal Git checkout. Broker execution remains unavailable. Four-pane synchronized options layouts and account-alert mutation remain partial and human-gated.

## Verification

```text
Production UI build: passed
Python source parse: passed
Migrations 131 and 132: applied and replayed idempotently
Command Center layouts: 19
Departments: 15
Agents: 95
Committee production packet: closed after named human decision
TradingView technical study assertion: passed
TradingView fundamental study assertion: passed
Browser regression: 93 unique cases covered in bounded passing shards
MCP protocol: 172 callable tools; 8 committee tools
Global broker execution lock: true
Seed/demo production fallback: absent
```

The environment terminates one long Playwright process near its duration ceiling, so the release suite was split into bounded shards. Every one of the 93 unique cases was covered; two tests were repeated during the split, for 95 passing executions and no failing shard.

## Explicit Next Phases

- Complete source-backed historical cash, liabilities, fees, tax lots, suitability, restrictions, and reconciliation breaks for every real client account.
- Add recurring read-only Zerodha/Dhan/algo, crypto/commodity, premium market-data, news, filing, and alternative-data adapters.
- Expand options, OI, intraday, factor, correlation, liquidity, and capacity models and complete synchronized four-pane options charts.
- Implement the other eight committee-family operating adapters on top of their existing constitutions.
- Deepen company, thesis, valuation, special-situation, strategy, backtest, optimization, model-validation, and committee report products.
- Build representative local-model quality, retrieval, throughput, thermal, and cost benchmarks before finalizing MacBook/iMac/cloud routing.
- Add authenticated remote deployment and authorized delivery channels.
- Refine the 3D office art, avatar interaction, chronological playback, and manual assistive-technology acceptance in the later visual pass.
- Keep live broker execution locked until independent security, compliance, risk, capital, limited-live, and per-order gates pass.
