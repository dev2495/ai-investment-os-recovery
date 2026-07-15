---
title: Agent Operating System and Strategy Chart v2
date: 2026-07-15
status: verified
system: AI Investment OS
tags:
  - ai-os
  - agents
  - strategy
  - tradingview
  - production-checkpoint
---

# Agent Operating System and Strategy Chart v2

## Verified Production State

The operating system now has a database-backed institutional organization rather than a prompt-only agent list.

- 95 active role-scoped agents across 15 departments.
- 95 active unique mailboxes, 95 character/personality records, 95 explicit model assignments, and 95 hard model-cost caps.
- Zero autonomous-cloud agents and zero model assignments that permit cloud escalation without approval.
- 117 active skills with 166 role-to-skill mappings.
- 13 recurring schedules with idempotent materialization and run logging.
- 11 committee constitutions with chairs, quorum rules, member rosters, evidence requirements, dissent rules, and human-final-decision boundaries.
- 166 importable MCP tools, including `ai_os_materialize_agent_schedules`.

Charlie Munger remains the chief orchestrator and Devarsh-facing decision partner. Jarvis is the runtime operator and dispatcher. Specialists own research, portfolio, quant, trading, risk, data, automation, client, knowledge, model, and engineering work. No agent receives capital authority, broker-order authority, or permission to bypass a human approval.

## Agent Runtime

The queue now resolves one deterministic inbox row per task. A worker failure is durable: the failed run is logged and the task and inbox return to `needs_review` instead of remaining falsely active. Database command failures raise runtime errors rather than being treated as successful work.

The repaired production runs include:

- worker run 83: Risk Office risk-gate review;
- worker run 84: Trading Desk strategy-alert monitoring;
- worker run 86: Chief of Staff daily-office brief for recovered task 418.

The message daemon continuously runs message dispatch, worker execution, OHLCV maintenance, TradingView CDP health, source freshness, market news, workflow scheduling, and strategy discovery. The current daemon heartbeat reports each of those loops as healthy.

## Agent Office

The Agent Office is now an operational department terminal, not just a roster.

- filterable 95-person organization;
- selected employee inspector with role, reporting line, persona, mental models, skills, readiness, model route, and mailbox;
- Charlie assignment composer that writes a durable internal message and routes through Jarvis;
- live worker queue and mailbox state;
- due-schedule materialization and worker controls;
- recurring schedule board;
- committee constitution board;
- responsive desktop and mobile presentation.

The API returns 95 employees with 95 unique identities plus the complete schedule and committee sets. The MCP schedule tool was registered and passed a live protocol call. The affected Agent Office and Strategy Arsenal browser suite passed 24 of 24 desktop/mobile tests.

## Strategy And TradingView Control

The Strategy Arsenal supports governed human intake and system discovery, hypothesis fingerprinting, discovery cooldowns, baseline evaluation, robust optimization, validation, committee state, paper-monitor state, and locked execution boundaries.

The optimizer performs train/test evaluation, walk-forward analysis, sensitivity analysis, Monte Carlo path analysis, objective scoring, parameter stability checks, and deterministic evidence retention. Optimization remains analytical and cannot enable live execution.

TradingView requests now pass through a compiled action contract and one atomic approval resolver. The production ratio/formula-chart workflow completed through approval, execution, screenshot verification, and artifact registration:

- approval 43;
- task 19;
- execution run 14;
- artifact 33069;
- screenshot hash begins `c30801bf`.

This proves the governed formula-chart path. It does not yet prove every supported multi-pane straddle, indicator-stack, or fundamental-ratio mutation.

## Safety And Data Rules

- No seed or sample records were introduced into production operating tables.
- Production reads remain source-backed and missing evidence remains visibly incomplete.
- Strategy approval, committee approval, limited-live approval, and per-order approval remain separate transactions.
- Global execution lock and broker-order false contracts remain active.
- TradingView visual work is analysis and chart control, not broker execution.
- External SSD stores the vault, artifacts, model/cache payloads, and durable knowledge; active application code remains on the MacBook and is backed by Git.

## Remaining Gates

- Complete Bloomberg-style department terminals and cross-terminal action drill-downs.
- Add addressable agent profile/history/cost-quality pages, richer handoff threads, and task-flow arrows.
- Automate committee packet assembly, voting, minutes, dissent, and follow-up actions for every committee type.
- Verify all TradingView indicator, formula, four-pane straddle, options-combination, and fundamental-ratio mutations.
- Connect recurring read-only broker, crypto/commodity, premium market-data, filing, news, and alternative-data sources.
- Complete real reconciliation breaks, client suitability/restrictions, cash/liability/tax records, and governed reporting distribution.
- Benchmark and finalize the local daily-driver and escalation model matrix after the operating foundation is complete.
- Refine the data-backed 2D/3D live office art, direct agent interaction, chronological playback, and accessibility fallbacks in a later visual pass.

## Verification Commands

```text
production UI build: passed
Python compile: passed
Agent Office and Strategy Arsenal Playwright suite: 24 passed
API Agent Office snapshot: 95 employees, 95 unique employees, 13 schedules, 11 committees
MCP import/protocol smoke: 166 tools; schedule materializer callable
agent coverage: 95 profiles, 95 mailboxes, 95 model assignments, 95 cost caps
cloud autonomy: 0
```
