# AI Investment OS - Governance Pack v1.0

Date: 2026-07-06
Blueprint: [[AI Investment OS - Institutional Master Blueprint v7.0]]
Checklist: [[AI Investment OS - Execution Checklist v7.0]]
Owner: Devarsh
Chair: Charlie Munger
Runtime operator: Jarvis

## 1. Purpose

This pack defines how the AI Investment OS changes, decisions, evidence, committees, data boundaries, source freshness, and broker safety are controlled.

The system is allowed to move fast, but it is not allowed to become unverifiable.

## 2. Architecture Change-Control Policy

Any meaningful architecture change must create a decision record before it is treated as canonical.

Meaningful changes include:

- new database schema,
- new source-of-truth table,
- new MCP/tool permission,
- new external data source,
- new model route,
- new agent role,
- new committee workflow,
- new broker or exchange connector,
- change from paper/read-only to live execution,
- dashboard change that changes decision logic,
- risk-limit change,
- checklist item marked complete.

Required fields:

- decision ID,
- date,
- proposer,
- approver,
- affected department,
- current state,
- proposed change,
- reason,
- alternatives considered,
- risk,
- rollback plan,
- evidence links,
- implementation owner,
- status.

Allowed states:

- proposed,
- under_review,
- approved,
- rejected,
- implemented,
- rolled_back,
- superseded.

No architecture change is final until the checklist evidence is updated.

## 3. Decision Log Template

```yaml
decision_id:
date:
title:
proposer:
approver:
department:
affected_systems:
status:
context:
decision:
alternatives_considered:
why_now:
risk:
rollback_plan:
evidence:
follow_up_tasks:
```

Decision categories:

- architecture,
- portfolio,
- strategy,
- data,
- model,
- tool,
- risk,
- broker_execution,
- client_reporting,
- governance.

## 4. Committee Minutes Template

```yaml
committee:
meeting_id:
date:
chair:
members:
symbols:
books:
client_accounts:
agenda:
source_materials:
open_questions:
agent_views:
  bull_case:
  bear_case:
  valuation:
  risk:
  portfolio_fit:
  capital_allocation:
decision:
decision_state:
approval_required:
approver:
next_review_date:
tasks_created:
evidence_links:
```

Committee minutes must include dissent. If every agent agrees, Charlie must ask what could be wrong.

## 5. Sprint Acceptance Criteria Template

Every build sprint must define:

- objective,
- user-facing outcome,
- database changes,
- API/MCP changes,
- UI changes,
- agent workflow changes,
- source data used,
- prohibited fake/demo data,
- test commands,
- smoke test,
- report path,
- checklist lines to update,
- rollback plan.

Acceptance states:

- not_started,
- in_progress,
- code_complete,
- smoke_passed,
- evidence_written,
- checklist_updated,
- accepted,
- rejected.

## 6. Evidence Standard For Checklist Completion

Checklist items can be marked `[x]` only when evidence proves the exact claim.

Acceptable evidence:

- database table/function/view exists and was queried,
- API endpoint was called with real output,
- MCP tool was called with real output,
- UI build passed,
- runtime smoke test passed,
- report was written to Obsidian,
- imported source file path is recorded,
- screenshot artifact exists,
- task/run/approval row exists,
- source URL/file/document is registered,
- test command output is captured.

Weak evidence that is not enough:

- code exists but was not run,
- generic "implemented" statement,
- mocked response,
- seed/demo data,
- screenshot without source trace,
- report with no query/tool evidence,
- passing test that does not cover the checklist item.

Completion note format:

```text
Evidence: [[report-name]]; command/API/table/tool: <specific proof>.
```

## 7. Production Data Vs Test Data Separation Policy

Production dashboards must never silently mix real and seed data.

Every table or artifact that can contain non-real data must carry one of:

- `production`,
- `user_imported`,
- `broker_export`,
- `paper_trade`,
- `manual_entry`,
- `sandbox`,
- `seed`,
- `test`.

Rules:

- Dashboard defaults exclude `seed`, `test`, and `sandbox`.
- Strategy research can use sandbox datasets only if labeled.
- Reports must disclose if any data is not production/user-imported.
- Agent outputs must state source confidence.
- No broker/order workflow may use seed/test data.

## 8. Investment Disclaimer And Human-Control Policy

The AI Investment OS is a decision-support system, not an autonomous fund manager.

Rules:

- Devarsh remains final decision maker.
- Agents may recommend, challenge, research, simulate, and prepare actions.
- Agents may not silently place orders.
- Broker execution requires explicit human approval.
- All investment decisions must record rationale, source evidence, risk review, and decision owner.
- Client-sensitive decisions require suitability review.
- Charlie must challenge overconfidence, missing data, and weak source quality.

## 9. Source Freshness Standard

Every important source must have:

- source name,
- source type,
- source owner,
- expected refresh cadence,
- last successful refresh,
- last failed refresh,
- stale-after threshold,
- raw artifact path,
- parser version,
- row count,
- quality checks,
- downstream dashboards affected.

Default freshness thresholds:

| Source | Freshness |
| --- | ---: |
| Client holdings | 1 business day after user/broker update |
| Broker transactions | 1 business day after import |
| Daily OHLCV | 1 market day |
| Intraday OHLCV | 5-15 minutes while market is open |
| Options chain/OI/IV | 5-15 minutes while market is open |
| NSE/BSE filings | 30-60 minutes during market/business hours |
| News | 15-60 minutes depending source |
| Long-term thesis notes | quarterly unless event-triggered |
| Strategy backtest datasets | before every backtest |
| Model endpoint health | daily |

Stale data must be visible in the UI and in agent outputs.

## 10. Broker Execution Safety Constitution

Live broker execution is disabled until all gates are proven.

Required gates:

1. Read-only broker connector verified.
2. Account mapping verified.
3. Instrument mapping verified.
4. Position reconciliation verified.
5. Risk limits table active.
6. Order preview object active.
7. Human approval UI active.
8. Kill switch active.
9. Execution audit trail active.
10. Post-trade reconciliation active.

Execution states:

- disabled,
- read_only,
- paper_only,
- preview_only,
- approved_manual_execution,
- limited_live,
- suspended,
- killed.

Rules:

- No strategy can jump from backtest to live.
- Paper monitoring is required before limited live.
- Risk Office can block limited-live activation.
- Human approval is required before every live order unless a later explicitly approved automation policy exists.
- Every broker action must have order intent, order preview, approval, execution receipt, and reconciliation.

## 11. Agent Output Standard

Every material agent output must include:

- task ID,
- agent,
- model route,
- input sources,
- tool calls,
- assumptions,
- findings,
- confidence,
- missing data,
- risks,
- recommended next action,
- approval need,
- artifact links.

## 12. Report Standard

Reports must be source-backed and decision-ready.

Required sections:

- objective,
- data used,
- current state,
- analysis,
- decision implications,
- risks,
- missing data,
- next actions,
- evidence.

## 13. Status

This governance pack is the first accepted governance baseline for the AI Investment OS. It should be split into separate operational templates later only when the UI can create these records directly.
