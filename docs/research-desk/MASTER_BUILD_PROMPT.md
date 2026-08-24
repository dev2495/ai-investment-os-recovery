# AI Investment OS — Master Build Prompt: Research Desk, Obsidian Knowledge Graph, Investor Watch and Fundamental Scanner Factory

**Use this as the first implementation prompt in Codex, Claude Code, Cursor, or another repository-aware coding agent. Run it from the root of `dev2495/ai-investment-os-recovery`.**

---

## COPY-PASTE PROMPT STARTS HERE

You are the principal architect, staff engineer, data engineer, AI-agent engineer, quantitative developer, product engineer, and test owner for my **AI Investment OS**.

Your task is not to write another architecture document or build another shallow dashboard. Your task is to inspect the existing repository and runtime, preserve the substantial work already present, and implement the first production-quality vertical slice of the system: a **complete institutional Research Desk** that can start research on any company, reuse and extend the existing Obsidian knowledge graph, follow selected investors and research sources, convert new ideas into evidence-backed research cases, and run a versioned, extensible fundamental-scanner factory.

Work step by step, keep the application runnable after every milestone, and continue automatically until the exit gates below are satisfied or you encounter a genuine external blocker such as a missing credential, inaccessible licensed source, or destructive action requiring approval.

Do not stop after planning. Implement code, migrations, tests, UI, tools, documentation, and a verified end-to-end demonstration.

---

# 1. Repository and runtime context

Repository:

```text
dev2495/ai-investment-os-recovery
```

The substantive current implementation is on or descended from:

```text
codex/live-ai-os-research-stack-20260817
```

Create a new focused feature branch from the actual live source commit after first verifying which commit is currently running. Suggested branch:

```text
codex/research-desk-knowledge-scanners-v1
```

The canonical product specification is:

```text
AI_Investment_OS_Institutional_Master_Blueprint_v11.md
```

Find it in the workspace or place it under:

```text
docs/AI_Investment_OS_Institutional_Master_Blueprint_v11.md
```

Treat that blueprint and the existing Obsidian vault as product truth. Treat Postgres as structured operational truth. Do not invent a new greenfield architecture that discards existing migrations, evidence, reports, tools, notes, UI, or domain knowledge.

Before modifying code, inspect at least the following existing areas:

```text
AGENTS.md
_ai_os_runtime/README.md
_ai_os_runtime/docker-compose.yml
_ai_os_runtime/.env.example

_ai_os_runtime/api/ai_os_api_server.py
_ai_os_runtime/api/ai_os_api_runtime.py
_ai_os_runtime/api/research_case_agent_runtime.py
_ai_os_runtime/api/research_case_source_runtime.py
_ai_os_runtime/api/research_case_helpers.py
_ai_os_runtime/api/research_case_report.py
_ai_os_runtime/api/research_model_runtime.py
_ai_os_runtime/api/research_monitor_runtime.py
_ai_os_runtime/api/long_term_thesis_workspace.py
_ai_os_runtime/api/market_research_workflow.py
_ai_os_runtime/api/financial_quality.py
_ai_os_runtime/api/valuation_workbench.py
_ai_os_runtime/api/graph_control_plane.py
_ai_os_runtime/api/reporting_helpers.py

_ai_os_runtime/scripts/manage_long_term_research.py
_ai_os_runtime/scripts/manage_thesis_source_pipeline.py
_ai_os_runtime/scripts/run_institutional_fundamental_factory.py
_ai_os_runtime/scripts/dispatch_long_term_specialists.py
_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
_ai_os_runtime/scripts/collect_nse_bse_filings.py
_ai_os_runtime/scripts/collect_company_ir_reports.py
_ai_os_runtime/scripts/collect_governed_research_source.py
_ai_os_runtime/scripts/extract_filing_pdfs.py
_ai_os_runtime/scripts/extract_long_term_source_document.py
_ai_os_runtime/scripts/normalize_annual_report_financials.py
_ai_os_runtime/scripts/normalize_annual_report_operating_intelligence.py
_ai_os_runtime/scripts/extract_governance_forensics.py
_ai_os_runtime/scripts/extract_industry_competitive_evidence.py
_ai_os_runtime/scripts/extract_valuation_inputs.py
_ai_os_runtime/scripts/build_fundamental_valuation_suite.py
_ai_os_runtime/scripts/run_long_term_monte_carlo.py
_ai_os_runtime/scripts/check_long_term_source_satisfaction.py
_ai_os_runtime/scripts/create_long_term_source_requests.py
_ai_os_runtime/scripts/register_long_term_source_document.py
_ai_os_runtime/scripts/index_obsidian_vault.py
_ai_os_runtime/scripts/index_qdrant_documents.py
_ai_os_runtime/scripts/create_qdrant_collections.py
_ai_os_runtime/scripts/run_agent_worker_once.py
_ai_os_runtime/scripts/run_agent_message_daemon.py
_ai_os_runtime/scripts/run_research_case_agent_once.py
_ai_os_runtime/scripts/run_research_case_agent_daemon.py
_ai_os_runtime/scripts/start_ai_office_live.sh

_ai_os_runtime/mcp_server/README.md
_ai_os_runtime/mcp_server/ai_os_mcp_server.py

_ai_os_runtime/postgres/init/
_ai_os_runtime/migrations/
_ai_os_runtime/config/
_ai_os_runtime/agents/

_ai_os_runtime/ai-office-ui/src/
_ai_os_runtime/ai-office-ui/src/assistant/
_ai_os_runtime/ai-office-ui/src/evidence/
_ai_os_runtime/ai-office-ui/src/office3d/
_ai_os_runtime/ai-office-ui/src/system/

ai memory/
ai memory/00 AI OS/
ai memory/02 Portfolio/
ai memory/03 Strategies/
ai memory/05 Filings and Transcripts/
ai memory/Templates/
```

The existing stack already includes Postgres/Timescale-style storage, Qdrant, Redis, Obsidian, a React/TypeScript application, a 3D office, agent/task infrastructure, research scripts, model routing, MCP tools, reports, data collectors, and local runtime services. Extend those components rather than duplicating them.

---

# 2. Primary objective

Deliver a **working Research Desk v1** with four fully connected capabilities:

1. **Start complete research on any public company** by name, ticker, exchange, ISIN, or existing portfolio/watchlist selection.
2. **Use the existing Obsidian vault as durable human-readable knowledge and graph memory**, while keeping facts, evidence lineage, tasks, and state in Postgres and semantic retrieval in Qdrant/pgvector.
3. **Follow investors, publications, ValuePickr threads, Substacks, blogs, newsletters, podcasts, videos, and selected social feeds** in read-only mode; convert relevant new content into structured idea cards and research tasks, never directly into facts or trades.
4. **Run and extend a fundamental-scanner factory** with point-in-time universes, deterministic metrics, versioned definitions, scheduled runs, alerts, backtests, coverage reporting, and an easy route for adding new scanners safely.

This must be connected to Charlie, the agent control plane, the UI, the 3D office, Obsidian, Postgres, Qdrant, audit logs, and reports.

The first golden path is Wipro, but the architecture must work for a company that is not already held and does not already have a thesis record.

---

# 3. Non-negotiable operating rules

## 3.1 Evidence before narrative

Every material claim must point to source evidence, a deterministic calculation, a stored assumption, or an explicitly labeled analyst opinion. Missing evidence must create acquisition or review tasks. It must not merely produce a disclaimer inside a polished report.

## 3.2 Deterministic numbers

LLMs may plan, extract into typed schemas, synthesize, critique, and explain. They may not be the source of truth for:

- financial arithmetic;
- ratios;
- growth rates;
- valuation;
- market prices;
- share counts;
- corporate-action adjustments;
- scanner results;
- portfolio accounting;
- risk;
- performance;
- options Greeks;
- backtest statistics.

Use Python, SQL, DuckDB, pricing libraries, and tested calculation services.

## 3.3 Point-in-time truth

Every source and fact must retain:

- event/economic date;
- published date and time;
- retrieved date and time;
- `known_at` or market-availability timestamp;
- source version and hash;
- parser/extractor/normalizer version;
- restatement or supersession information;
- unit, scale, currency, period, and scope;
- confidence and verification state.

No scanner, valuation, historical test, or report may silently mix future-restated data with prior periods.

## 3.4 No fake production data

Do not create demo agents, fake filings, fake prices, fake financials, fake tasks, fake reports, or fake scanner results in any production path. Test fixtures must be explicitly isolated under `fixtures/` or test directories and visibly labeled as fixtures.

## 3.5 Separate truth layers

- Postgres: entities, facts, lineage, cases, tasks, approvals, scanners, source registry, scorecards, state.
- External SSD/object directories: raw PDFs, HTML, screenshots, API responses, full transcripts, Parquet, workbooks, large reports, logs.
- Obsidian: human-readable research, decisions, summaries, runbooks, committee minutes, monitoring notes, graph links, and references to evidence/artifacts.
- Qdrant/pgvector: semantic retrieval only, never accounting or final facts.
- Redis: cache, leases, queue acceleration, pub/sub; never the sole durable record.

## 3.6 Preserve human edits in Obsidian

Generated writebacks must be atomic and idempotent. Never overwrite a human-edited note wholesale. Use managed blocks such as:

```markdown
<!-- AIOS:BEGIN AUTO company_summary v3 -->
...generated content...
<!-- AIOS:END AUTO company_summary v3 -->
```

Keep user-authored sections outside generated blocks intact. Before changing existing note layout, create a backup and document the migration.

## 3.7 Real agent states only

Every 3D-office agent state, speech bubble, movement, handoff, committee session, blocker, and completion signal must correspond to durable task/event rows. No agent may appear to be working unless an active task lease or run exists.

## 3.8 No live broker execution

This phase is research, monitoring, internal writes, and analytics only. Do not add or enable live order placement. Any future action must remain a proposal or paper action behind existing approval and policy gates.

## 3.9 Local-first and budget-aware

Optimize for the M4 16 GB Mac and external SSD:

- bounded concurrency;
- one resident local model route at a time;
- 8K default context;
- retrieval instead of huge prompts;
- incremental indexing;
- content-hash caching;
- DuckDB/Parquet for batch analytics;
- cloud escalation only for defined high-value cases;
- all heavy artifacts and caches on the external SSD.

## 3.10 Repeated error rule

Follow `AGENTS.md`: if the same error happens twice, stop repeating it, research plausible fixes, choose the most efficient supported fix, implement it, and verify it.

---

# 4. How you must work

## 4.1 Begin with a read-only baseline audit

Before coding:

1. Print repository path, branch, HEAD commit, working-tree status, remotes, and open changes.
2. Determine the exact live application commit and active runtime paths.
3. Do not discard or overwrite uncommitted user work.
4. Inventory existing database schemas, migrations, views, tools, agent registry, API routes, UI routes, Obsidian folders, Qdrant collections, and source connectors.
5. Run existing smoke tests and record pass/fail with commands and timestamps.
6. Back up or verify recent backups of Postgres, the Obsidian vault, and runtime configuration before migrations.
7. Write the audit to:

```text
docs/research-desk/BASELINE_AUDIT.md
```

and to a structured Obsidian note under:

```text
ai memory/00 AI OS/Implementation/Research Desk v1 - Baseline Audit.md
```

## 4.2 Create an implementation ledger

Create and keep current:

```text
docs/research-desk/IMPLEMENTATION_STATUS.md
docs/research-desk/DATA_CONTRACTS.md
docs/research-desk/RESEARCH_STANDARD.md
docs/research-desk/SCANNER_STANDARD.md
docs/research-desk/OBSIDIAN_GRAPH_CONTRACT.md
docs/research-desk/SOURCE_FOLLOWING_POLICY.md
docs/research-desk/RUNBOOK.md
```

The status file must list every milestone as `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, or `VERIFIED`, with evidence links and commands.

## 4.3 Incremental commits

Use focused commits. A suggested sequence is:

```text
chore: capture research desk baseline and contracts
feat(db): add generic research case and evidence-gap schema
feat(knowledge): add incremental Obsidian graph indexing
feat(research): add company onboarding and evidence planner
feat(research): add point-in-time facts and deterministic metrics
feat(research): add specialist workflow and decision readiness
feat(feeds): add investor and publication following pipeline
feat(scanners): add versioned fundamental scanner engine
feat(mcp): expose research, graph, following, and scanner tools
feat(ui): deliver research factory, following, scanners, and graph pages
feat(office): map research work to truthful live agents
feat(monitoring): add company, feed, and scanner schedules
feat(test): add Wipro and generic-company golden paths
```

Do not put the whole implementation into one giant commit or one huge new file.

## 4.4 Keep the current app runnable

After each milestone, run the relevant migrations, tests, API health checks, UI build, and smoke workflow. Fix regressions before continuing.

## 4.5 Continue without unnecessary confirmation

Do not ask me to approve routine architecture choices already resolved by this prompt and the blueprint. Ask only when blocked by:

- credentials or paid access;
- a destructive migration or data deletion;
- unclear ownership of private/client data;
- a licensing decision;
- a live financial action;
- a choice that materially conflicts with the canonical blueprint.

At each milestone, record what changed and continue to the next milestone automatically.

---

# 5. Target research lifecycle

Implement the following durable research state machine:

```text
DISCOVER
→ DEFINE_QUESTIONS
→ PLAN_EVIDENCE
→ INVENTORY_EXISTING_EVIDENCE
→ ACQUIRE_MISSING_SOURCES
→ VERIFY_SOURCE
→ PARSE
→ EXTRACT
→ NORMALIZE
→ RECONCILE
→ CALCULATE
→ ANALYZE
→ CONTRADICTION_CHECK
→ RED_TEAM
→ COMMITTEE
→ HUMAN_REVIEW
→ DECISION_READY
→ MONITOR
→ REOPEN_ON_CHANGE
```

Maintain separate statuses:

```yaml
orchestration_status:
  - queued
  - running
  - finished
  - failed
  - cancelled

research_readiness:
  - missing_data
  - partial
  - blocked
  - ready_for_review
  - decision_ready
  - stale

investment_status:
  - no_view
  - watch
  - avoid
  - hold
  - buy_candidate
  - sell_candidate
  - approved
  - rejected

approval_status:
  - not_required
  - pending
  - approved
  - rejected
  - expired
```

A finished agent run is not equivalent to a complete research case. A report may be generated in partial mode, but it must show critical gaps and must not expose a BUY/SELL verdict when the defined decision-readiness gate fails.

---

# 6. Milestone 0 — Safe baseline and refactor boundary

## Goal

Establish a safe starting point without disrupting the running application.

## Required work

1. Identify the current production/live commit and tag it if no reproducible tag exists.
2. Create the focused branch.
3. Add or update top-level `STATUS.md` with truthful feature states: working, partial, simulated, UI-only, planned.
4. Confirm secrets, client data, runtime databases, and licensed artifacts are not being newly committed.
5. Add first-party CI if absent, at minimum:
   - Python compile/lint/type checks appropriate to the current stack;
   - TypeScript lint/build;
   - migration application in an isolated test DB;
   - unit tests;
   - golden research-case tests;
   - secret scan;
   - dependency/security scan.
6. Introduce a compatibility boundary around the oversized API and MCP modules. Do not rewrite them in one step. New research-desk domain behavior must be implemented in smaller importable modules and registered through the compatibility layer.

## Exit gate

- Current application still starts.
- Existing smoke tests are recorded.
- Backups are verified.
- New branch exists.
- Baseline docs exist in both repository and Obsidian.
- No user data has been lost or moved silently.

---

# 7. Milestone 1 — Generic company and research-case domain

## Goal

Allow a research case to be created for any company, including a company that is not currently held and has no existing thesis record.

## First inspect and reuse

The repository already has research companies, evidence, dossiers, specialist opinions, corporate filings, thesis workflows, and related tables. Inspect all schemas before adding anything. Extend or normalize existing tables. Do not create duplicate concepts under different names.

## Required domain capabilities

### 7.1 Company identity

Support:

- legal name;
- display name;
- aliases and previous names;
- exchange and symbol;
- ISIN;
- BSE code;
- NSE symbol;
- CIN where available;
- LEI where available;
- country;
- currency;
- sector and industry;
- security type;
- active/delisted/suspended status;
- corporate-action history;
- source and verification state for every identifier.

Build a symbol/identity resolver that never guesses silently. When a name maps to multiple listings or companies, return candidates and create a `WAITING_FOR_INPUT` state.

### 7.2 Generic research case

A case request must support:

```yaml
company_input: Wipro
symbol: WIPRO
exchange: NSE
isin: optional
research_type: full_fundamental
book: long_term_core
client_id: optional
decision_question: Is Wipro attractive at the current price for a 5+ year horizon?
as_of: explicit timezone-aware timestamp
priority: normal
requested_by: devarsh
source_cutoff_policy: point_in_time
```

Case records need:

- immutable case id and human-readable key;
- company/entity id;
- requested question and scope;
- affected book/client/watchlist;
- state-machine status;
- readiness status;
- source cutoff;
- plan version;
- latest run id;
- assigned agents;
- evidence completeness;
- calculation completeness;
- contradictions;
- critical blockers;
- artifacts;
- monitoring policy;
- created/updated/closed timestamps;
- audit history.

### 7.3 Desired APIs

Reuse current route conventions, but expose equivalent capabilities to:

```text
POST /v1/research/cases
GET  /v1/research/cases
GET  /v1/research/cases/{case_id}
POST /v1/research/cases/{case_id}/run
POST /v1/research/cases/{case_id}/refresh
POST /v1/research/cases/{case_id}/cancel
GET  /v1/research/cases/{case_id}/timeline
GET  /v1/research/cases/{case_id}/readiness
GET  /v1/research/cases/{case_id}/artifacts
```

### 7.4 CLI

Provide a stable developer/operator CLI, for example:

```bash
python -m aios_research start \
  --company Wipro \
  --symbol WIPRO \
  --exchange NSE \
  --type full_fundamental \
  --question "Is Wipro attractive at the current price for a 5+ year horizon?" \
  --as-of "2026-08-24T16:00:00+05:30"
```

Use the repository’s actual package structure rather than inventing an isolated script if a service module already exists.

## Exit gate

- Wipro can be created as a generic case.
- A second company not in the portfolio can be created.
- Ambiguous identity resolution produces candidates, not an incorrect match.
- The case appears in Postgres, the API, MCP, UI, and agent task list.
- No research conclusion is generated yet unless evidence requirements are met.

---

# 8. Milestone 2 — Evidence planner and acquisition loop

## Goal

Turn a company question into a typed evidence plan, reuse existing evidence first, and automatically create work for missing sources.

## 8.1 Evidence requirement templates

Create versioned templates by market, company type, and research purpose. The full India-listed-company template should require, where applicable:

### Identity and listing

- exchange master and security identifiers;
- current listing status;
- corporate actions and share-count history.

### Primary company sources

- at least ten annual reports when available;
- recent quarterly/annual results;
- investor presentations;
- earnings-call transcripts or permitted notes;
- annual letters;
- credit-rating reports;
- material subsidiaries;
- acquisition/divestiture documents;
- company IR announcements.

### Exchange and regulator

- NSE and BSE filings;
- shareholding disclosures;
- insider/promoter disclosures where legally available;
- auditor and governance disclosures;
- SEBI/regulatory actions where applicable.

### Market and industry

- current market quote with timestamp and provider;
- historical adjusted prices;
- peer set;
- industry reports or official industry statistics;
- market-share evidence;
- customer/supplier or capacity evidence where disclosed.

### Decision inputs

- diluted shares;
- net cash/debt;
- revenue, margins, PAT, OCF, capex, FCF;
- guidance and estimates when licensed/available;
- valuation inputs;
- risk and monitoring data.

## 8.2 Evidence inventory

Search in this order:

1. Existing immutable raw artifacts and registered evidence.
2. Existing parsed/extracted text.
3. Existing Obsidian notes and prior reports.
4. Existing corporate filings tables.
5. Existing external research artifacts imported from Codex/Claude/cowork.
6. Official source connectors.
7. Approved secondary providers.
8. User-supplied files.

Do not reacquire documents whose content hash and source version are already present unless freshness policy requires it.

## 8.3 Source authority

Implement a source hierarchy:

```text
PRIMARY_OFFICIAL
PRIMARY_COMPANY
REGULATORY_OR_EXCHANGE
LICENSED_DATA_PROVIDER
REPUTABLE_SECONDARY
ANALYST_COMMENTARY
SOCIAL_OR_FORUM
UNKNOWN
```

A secondary or social claim cannot satisfy a primary financial evidence requirement without corroboration.

## 8.4 Source request records

Each missing requirement becomes a durable source request containing:

- requirement id;
- case id;
- company id;
- requested source type;
- preferred providers;
- date range;
- why it is required;
- blocking/non-blocking status;
- assigned collector;
- attempts;
- latest error;
- retry time;
- completion evidence id;
- waiver and waiver authority when applicable.

## 8.5 Acquisition and immutable storage

Extend existing collectors rather than replacing them:

- `collect_nse_bse_filings.py`;
- `collect_company_ir_reports.py`;
- `collect_governed_research_source.py`;
- browser/MCP capture workflows;
- local artifact ingestion.

For every acquired object, store:

- original URL and final URL;
- response metadata;
- retrieved timestamp;
- publication timestamp;
- MIME type;
- content hash;
- file size;
- local immutable path;
- source authority;
- access/licensing class;
- parser status;
- case/company links.

Never overwrite a prior document version.

## 8.6 Parsing, extraction and anchors

Use existing PDF extraction and normalization work. Every extracted claim or fact must retain a source locator:

```text
document_id
page_number
section_heading
table_id
row_label
column_label
character_span or excerpt hash
```

OCR is a fallback, not the default. Preserve the original page image or PDF for validation.

## 8.7 Gap loop

After every acquisition/extraction pass:

1. Re-evaluate evidence requirements.
2. Mark each requirement as satisfied, partial, missing, waived, contradictory, or unobtainable.
3. Create follow-up tasks for unresolved critical fields.
4. Update case readiness.
5. Display the gap list in UI and Charlie.
6. Stop only when all critical requirements are satisfied, explicitly waived, or genuinely unobtainable.

## Exit gate

For Wipro, the system can show a complete evidence inventory and generate real acquisition tasks for missing current price, share count, OCF, capex, guidance, peer data, or other missing fields. The UI must distinguish validation success from completeness.

---

# 9. Milestone 3 — Point-in-time financial facts and deterministic calculations

## Goal

Build a reliable data spine for research and scanners.

## 9.1 Canonical fact model

Use or extend existing statement-fact tables. A canonical fact must support:

```yaml
company_id:
fact_definition_id:
metric_key: revenue
value:
unit: INR
scale:
currency:
fiscal_year:
fiscal_period:
period_start:
period_end:
period_type: annual|quarter|ttm
statement_scope: consolidated|standalone
reported_at:
known_at:
available_at:
recorded_at:
source_evidence_id:
source_anchor:
extraction_method:
normalization_version:
restatement_version:
is_restated:
supersedes_fact_id:
confidence:
verification_status:
```

## 9.2 Required statements and metrics

Normalize at least:

- revenue;
- operating profit/EBIT;
- EBITDA where valid;
- PAT and minority interest;
- EPS and diluted shares;
- OCF;
- capex;
- FCF;
- cash and investments;
- short- and long-term debt;
- working capital components;
- receivables;
- inventory;
- payables;
- fixed assets and CWIP;
- equity;
- dividends and buybacks;
- exceptional items;
- segment/geographic revenue and profit;
- employee count where disclosed;
- customer concentration where disclosed;
- capacity/utilization where disclosed.

## 9.3 Reconciliation gates

Implement deterministic checks for:

- balance-sheet equation;
- PAT-to-cash-flow bridge;
- OCF minus capex equals FCF using documented capex policy;
- consolidated versus standalone separation;
- annual totals versus quarterly sum/TTM;
- shares and corporate actions;
- currency and unit consistency;
- restatements;
- duplicate facts;
- missing periods;
- sign conventions;
- source discrepancies.

A reconciliation warning must not be hidden by a passing statement-check count.

## 9.4 Derived metric library

Create a versioned deterministic calculation package with tests for:

- revenue/PAT/EBITDA/FCF CAGRs;
- gross/EBITDA/EBIT/PAT/FCF margins;
- ROE, ROCE, ROIC, incremental ROIC;
- asset turns;
- reinvestment rate;
- cash conversion and OCF/PAT;
- FCF/PAT and FCF conversion;
- receivable, inventory, payable and cash-conversion cycles;
- net debt, leverage and interest coverage;
- working-capital intensity;
- capex intensity;
- dilution;
- per-share and per-employee economics;
- dividend and buyback yield;
- historical valuation bands;
- quality and forensic flags.

Every metric output carries the formula version and input fact ids.

## 9.5 Market quote and valuation inputs

Current price, currency, exchange, session, delay status, timestamp, shares, net cash/debt, and corporate-action adjustment are mandatory before a current fair-value comparison can be `decision_ready`.

## 9.6 Valuation

Reuse and strengthen existing valuation modules. Deterministically support:

- DCF/FCFF;
- reverse DCF;
- relative valuation;
- SOTP when segment data supports it;
- historical bands;
- normalized earnings;
- base/bull/bear scenarios;
- sensitivity matrices;
- Monte Carlo with seeded reproducibility;
- expected return and downside distribution.

Models must expose assumptions separately from reported facts.

## Exit gate

- Wipro has a reproducible ten-year history where sources permit.
- Current quote and share count are reconciled.
- Cash flow and FCF are calculated from cited facts.
- Ratios reproduce from input fact ids.
- A data-completeness score and critical-gap list are shown.
- Scanner engine can query the canonical metric views without using LLM output.

---

# 10. Milestone 4 — Full specialist research workflow

## Goal

Produce a complete institutional research case, not a shallow summary.

## 10.1 Specialist modules

Use focused agents or deterministic services for:

- Research Director;
- Company/Business Model Analyst;
- Industry and Value-Chain Analyst;
- TAM/SAM/SOM Analyst;
- Competition and Moat Analyst;
- Customer/Supplier Analyst;
- Financial Model Builder;
- Financial Quality Analyst;
- Management and Capital-Allocation Analyst;
- Governance Analyst;
- Forensic Accounting Analyst;
- Transcript and Guidance Analyst;
- Peer and Valuation Analyst;
- Scenario/Monte Carlo Analyst;
- Catalyst and Monitoring Analyst;
- Bear Case/Red Team Analyst;
- Risk and Portfolio-Fit Analyst;
- Research Editor.

Do not require uncontrolled debate among all agents. Use one planner, targeted specialists, and explicit handoffs.

## 10.2 Typed output contract

Every specialist output must include:

```yaml
case_id:
run_id:
specialist_key:
agent_id:
model_route:
prompt_version:
source_packet_ids:
tool_calls:
reported_facts:
derived_metrics:
assumptions:
claims:
citations:
contradictions:
disconfirming_evidence:
confidence:
missing_data:
required_followups:
validation_status:
artifact_ids:
```

Reject unsupported claims or store them as unverified hypotheses.

## 10.3 Research workspace content

The complete case must cover:

### Overview

- identity and listing;
- current price and timestamp;
- readiness and completeness;
- key financial and operating metrics;
- valuation range and implied return;
- top risks and catalysts;
- active monitoring triggers;
- next required actions.

### Business and industry

- business model;
- products/services;
- segments and geographies;
- value chain;
- customer and supplier structure;
- unit economics;
- capacity and utilization;
- industry structure;
- TAM/SAM/SOM;
- market share;
- competitive intensity;
- regulation;
- cyclicality;
- substitution/disruption.

### Moat and quality

- switching costs;
- scale economics;
- network effects;
- cost advantage;
- brand/distribution;
- IP;
- regulatory positioning;
- pricing power;
- retention/churn;
- concentration;
- reinvestment runway;
- incremental returns.

Every moat assertion must be quantitative where possible or clearly labeled qualitative.

### Management, governance and forensics

- promoter/management history;
- capital allocation;
- acquisitions/divestitures;
- related parties;
- auditor changes/qualifications;
- remuneration;
- promoter pledge;
- dilution;
- contingent liabilities;
- taxes and subsidiaries;
- cash-versus-profit conversion;
- receivable/inventory anomalies;
- exceptional items;
- regulatory or governance controversies.

### Valuation and scenarios

- DCF;
- reverse DCF;
- peers;
- SOTP when appropriate;
- historical ranges;
- base/bull/bear;
- Monte Carlo;
- implied expectations;
- expected return and downside.

### Thesis and red team

- base thesis;
- variant perception;
- market-implied view;
- catalysts;
- disconfirming evidence;
- failure modes;
- thesis-break conditions;
- sell discipline;
- monitoring triggers;
- position-sizing constraints.

## 10.4 Committee

Create a durable Research Committee packet containing:

- specialist conclusions;
- evidence quality;
- contradictions;
- red-team memo;
- risk opinion;
- portfolio-fit opinion;
- vote and dissent;
- required follow-ups;
- human decision/comments;
- review date.

Committee completion does not automatically approve an investment.

## 10.5 Outputs

Generate:

- executive memo;
- full report;
- machine-readable financial model;
- evidence appendix;
- source manifest;
- valuation/sensitivity files;
- red-team memo;
- committee minutes;
- monitoring checklist;
- HTML and PDF exports;
- version diff versus prior case.

## Exit gate

Wipro reaches `ready_for_review` or `decision_ready` only when the defined critical evidence and calculation gates pass. A second generic company follows the same state machine without requiring an existing portfolio holding.

---

# 11. Milestone 5 — Obsidian knowledge graph and memory

## Goal

Make the existing Obsidian vault a structured, searchable, human-editable research and decision graph connected to Postgres evidence and Qdrant retrieval.

## 11.1 Preserve the existing vault

Do not replace or flatten the current `ai memory` structure. Add a coherent research substructure and link old notes into it. Suggested layout:

```text
ai memory/
  00 AI OS/
    Architecture/
    Decisions/
    Implementation/
    Runbooks/
    System Health/

  01 Research/
    Companies/
      NSE/
        WIPRO/
          00 Company Hub.md
          01 Evidence Index.md
          02 Financial History.md
          03 Business and Industry.md
          04 Moat and Competition.md
          05 Management and Capital Allocation.md
          06 Governance and Forensics.md
          07 Valuation and Scenarios.md
          08 Thesis and Red Team.md
          09 Monitoring and Thesis Drift.md
          10 Committee and Decisions.md
    Industries/
    Themes/
    People and Investors/
    Publications and Sources/
    Idea Inbox/
    Scanner Results/

  02 Portfolio/
  03 Strategies/
  05 Filings and Transcripts/
  Templates/
```

If introducing `01 Research` conflicts with an existing local folder, adapt the path but preserve the logical contract.

## 11.2 Company hub frontmatter

Use stable ids and aliases, not only file names:

```yaml
---
type: company_hub
entity_id: company_123
company_key: wipro
legal_name: Wipro Limited
display_name: Wipro
symbol: WIPRO
exchange: NSE
isin:
sector:
industry:
aliases:
  - Wipro Ltd
case_ids:
  - case_2026_...
research_readiness: partial
investment_status: watch
source_cutoff_at:
latest_facts_version:
latest_valuation_version:
last_reviewed_at:
next_review_at:
tags:
  - company
  - india-equity
  - research
managed_sections:
  - identity
  - current_snapshot
  - active_cases
  - monitoring
---
```

## 11.3 Generated note rules

- Use atomic temp-file writes and rename.
- Preserve human edits outside managed blocks.
- Store raw documents outside the vault and link them by artifact/evidence id.
- Keep large tables in Parquet/CSV/workbooks; put useful summaries in notes.
- Include stable links to case ids, evidence ids, calculation ids, source manifests, reports, and dashboards.
- Every automatic update records actor, run id, timestamp, and content hash.
- Re-running with unchanged inputs must produce no material diff.

## 11.4 Graph model

Create or extend Postgres graph tables/views for nodes and typed edges. Do not introduce Neo4j in this phase unless the existing system already depends on it.

Required node types:

```text
company
security
sector
industry
theme
person
investor_or_author
publication
source_item
research_case
document
evidence_anchor
claim
fact
metric
valuation_case
scenario
corporate_event
portfolio
client
watchlist
strategy
agent
task
artifact
obsidian_note
```

Required edge types include:

```text
LISTED_AS
HAS_ALIAS
OPERATES_IN
BELONGS_TO_SECTOR
COMPETES_WITH
PEER_OF
SUPPLIES
CUSTOMER_OF
MANAGED_BY
AUTHORED_BY
PUBLISHED_BY
MENTIONS
SUPPORTS_CLAIM
CONTRADICTS_CLAIM
DERIVED_FROM
CITED_BY
LINKED_TO_CASE
LINKED_TO_NOTE
HELD_IN
WATCHED_IN
TRIGGERED_BY
MONITORED_BY
RELATED_TO_THEME
GENERATED_BY_AGENT
PRODUCED_ARTIFACT
SUPERSEDES
```

Resolve Obsidian wikilinks and aliases into graph edges when possible. Preserve unresolved links as unresolved records rather than dropping them.

## 11.5 Incremental indexing

Extend `index_obsidian_vault.py` and `index_qdrant_documents.py` so normal indexing is incremental:

- compare content hash and modified time;
- upsert only changed notes/chunks;
- delete only points belonging to deleted notes;
- preserve collection state;
- use an explicit `--rebuild` mode for destructive full rebuilds;
- never recreate all Qdrant collections during an ordinary writeback;
- chunk by headings/semantic sections rather than raw fixed character windows where possible;
- store note path, heading path, entity ids, case ids, source cutoff, tags, and content hash in vector metadata;
- reject mixed fake/hash embeddings; use the approved embedding model only;
- record embedding model revision and index run.

## 11.6 Hybrid retrieval

Implement a retrieval service that combines:

1. Exact identity and SQL filters.
2. Point-in-time fact/evidence queries.
3. Qdrant semantic matches.
4. Graph expansion over relevant neighbors.
5. Authority/freshness/confidence ranking.

The result packet must keep primary evidence separate from Obsidian interpretation and social commentary.

## 11.7 Knowledge APIs and MCP tools

Expose capabilities equivalent to:

```text
GET /v1/knowledge/search
GET /v1/knowledge/graph
GET /v1/knowledge/companies/{company_id}/graph
GET /v1/knowledge/notes/{note_id}
POST /v1/knowledge/reindex
POST /v1/knowledge/notes/write-managed-section
```

MCP tools:

```text
ai_os_search_knowledge
ai_os_search_knowledge_graph
ai_os_company_knowledge_graph
ai_os_get_obsidian_note
ai_os_write_obsidian_managed_section
ai_os_reindex_knowledge_incremental
```

Extend the existing `ai_os_search_obsidian_notes`, `ai_os_write_obsidian_note`, and `ai_os_reindex_obsidian` safely rather than bypassing them.

## 11.8 Graph UI

Add a usable knowledge-graph view:

- filter by company, case, investor, source, theme, evidence type, date, authority, and portfolio overlap;
- click a node to open its details, Obsidian note, evidence, research case, or source item;
- distinguish fact/evidence nodes from analysis/commentary visually;
- display edge type and source;
- support graph-to-table fallback;
- do not attempt to render the whole vault at once;
- query bounded neighborhoods.

## Exit gate

Starting or refreshing Wipro research creates/updates a linked company hub and supporting notes without destroying human edits. Postgres graph edges and Qdrant chunks update incrementally. A graph query can trace:

```text
source document → evidence anchor → fact/claim → research case → valuation/thesis → Obsidian note → portfolio/watchlist
```

---

# 12. Milestone 6 — Investor, publication and idea following

## Goal

Let me follow favorite investors, operators, inventors, publications, newsletters and communities, monitor their new work, and turn relevant observations into research ideas without treating commentary as fact.

## 12.1 Source types

Support read-only registry entries for:

- Substack publications;
- ValuePickr threads and authors;
- investor and operator blogs;
- company and industry blogs;
- RSS/Atom feeds;
- selected newsletters and permitted email imports;
- X/Twitter lists or read-only feeds;
- Telegram channels;
- Reddit communities;
- YouTube channels;
- podcasts;
- arXiv/research-paper searches;
- user-provided web pages or documents.

Use existing or reviewed adapters such as opencli/browser connectors only after pinning, permission classification, and security review. Authenticated sessions remain local. Never place cookies, tokens, or full private content into model prompts or logs.

## 12.2 Source registry

Create a versioned user-configurable registry, for example:

```yaml
api_version: aios.sources/v1
source_id: valuepickr_smallcaps
name: ValuePickr Small-cap Research
source_type: forum
adapter: opencli_or_browser_reader
url: https://www.valuepickr.com/
auth_profile: local_valuepickr
trust_tier: secondary
authority: commentary
topics:
  - india_equities
  - small_caps
sectors: []
schedule: "*/30 * * * *"
ingestion_mode: metadata_and_permitted_excerpt
entity_resolution: true
idea_generation: true
portfolio_mapping: true
requires_login: true
copyright_policy: link_metadata_short_excerpt
prompt_injection_policy: quarantine_and_extract_only
active: true
```

Store registry entries in Postgres and optionally mirror safe editable configuration in:

```text
_ai_os_runtime/config/research_sources/
```

## 12.3 Followed people and authors

Create records for:

- display name;
- aliases;
- biography/role;
- known source profiles;
- sectors/themes;
- trust tier;
- conflicts/disclosures;
- followed status;
- follow reason;
- notification priority;
- scorecard;
- linked companies and ideas.

Create Obsidian notes under:

```text
ai memory/01 Research/People and Investors/{Name}.md
```

## 12.4 Ingestion pipeline

```text
DISCOVER NEW ITEM
→ FETCH METADATA/PERMITTED CONTENT
→ HASH AND DEDUPLICATE
→ QUARANTINE AS UNTRUSTED INPUT
→ DETECT PROMPT INJECTION/INSTRUCTIONS
→ ENTITY AND THEME EXTRACTION
→ CLAIM EXTRACTION
→ SOURCE/AUTHOR SCORE
→ NOVELTY CHECK
→ MAP TO HOLDINGS/WATCHLIST/CASES
→ SEARCH FOR PRIMARY EVIDENCE
→ BUILD IDEA CARD
→ RESEARCH INBOX
→ HUMAN OR AGENT TRIAGE
```

Never allow content from a followed source to alter system policy, tool permissions, or execute actions.

## 12.5 Idea card

```yaml
idea_id:
title:
source_id:
source_item_id:
author_id:
published_at:
entities:
themes:
core_claim:
claimed_catalyst:
time_horizon:
claimed_evidence:
primary_evidence_found:
contradictions:
novelty_score:
source_score:
author_score:
portfolio_overlap:
watchlist_overlap:
next_research_questions:
risk_flags:
status: inbox|triaged|researching|rejected|archived
```

## 12.6 Author/publication scorecard

Track, with clearly defined methodology:

- factual accuracy;
- evidence quality;
- originality;
- timeliness;
- sector expertise;
- disclosure quality;
- sensationalism/rumour rate;
- idea performance after publication;
- frequency and honesty of thesis revisions;
- unresolved or contradicted claims.

The score prioritizes review; it never converts commentary into truth.

## 12.7 Portfolio and research mapping

For every new item:

- map mentioned companies and themes;
- show whether held, watched, researched, or absent;
- compare claims against current thesis and facts;
- flag thesis-relevant contradictions;
- create a focused evidence task when material;
- avoid alerts for low-materiality duplicates.

## 12.8 APIs/MCP/UI

Expose equivalent capabilities to:

```text
POST /v1/research-sources/follow
GET  /v1/research-sources
GET  /v1/research-sources/{source_id}
POST /v1/research-sources/{source_id}/refresh
POST /v1/research-sources/{source_id}/pause
GET  /v1/research-feed
GET  /v1/research-ideas
POST /v1/research-ideas/{idea_id}/triage
POST /v1/research-ideas/{idea_id}/start-case
GET  /v1/investors/{investor_id}/scorecard
```

MCP tools:

```text
ai_os_follow_research_source
ai_os_list_followed_sources
ai_os_refresh_research_source
ai_os_list_research_feed
ai_os_list_idea_cards
ai_os_triage_idea_card
ai_os_start_research_from_idea
ai_os_investor_scorecard
```

UI pages:

- Following;
- Favorite Investors;
- Publications and Sources;
- New Items;
- Idea Inbox;
- Source/author scorecard;
- Holdings/watchlist overlap;
- Add Source wizard.

## 12.9 Copyright and retention

- Store URL, metadata, source id, hashes, and permitted excerpts.
- Do not republish paid newsletters or copyrighted full articles.
- Store user-permitted personal copies only in private local artifact storage.
- Keep a source-specific retention and access policy.
- Always link back to the original source.

## Exit gate

At least one public RSS/website source and one authenticated/local source can be followed in read-only mode. New items are deduplicated, mapped to companies, converted into idea cards, written into Obsidian, visible in UI, and auditable. No item is treated as a primary fact without corroboration.

---

# 13. Milestone 7 — Fundamental scanner factory

## Goal

Create a deterministic, point-in-time, extensible scanner platform that supports built-in scanners and safe creation of new fundamental scanners.

## 13.1 Scanner principles

Every scanner must be:

- versioned;
- immutable after publication;
- tied to a point-in-time universe;
- deterministic;
- replayable;
- testable;
- provider-aware;
- explicit about missing data;
- explicit about sector exclusions or sector-specific formulas;
- explicit about lookback and lag;
- explicit about ranking, thresholds, and weights;
- auditable from result to input fact ids;
- separated from LLM opinion.

A scanner run must never silently claim to cover the full market when only a subset has complete facts. Show total universe, eligible universe, excluded names, missing-data exclusions, stale data, and provider failures.

## 13.2 Canonical scanner definition

Implement a constrained YAML/JSON DSL similar to:

```yaml
api_version: aios.scanner/v1
kind: FundamentalScanner
metadata:
  scanner_id: india_quality_compounders
  version: 1
  name: India Quality Compounders
  description: Durable growth, high returns, cash conversion and conservative balance sheets
  owner: research.scanners
  status: draft
  tags: [quality, compounder, india]

universe:
  countries: [IN]
  exchanges: [NSE, BSE]
  security_types: [equity]
  active_only: true
  min_market_cap_inr_crore: 500
  min_median_adv_inr_crore_60d: 0.5
  exclude_industries: [Banks, Insurance, NBFC]
  as_of_policy: point_in_time
  universe_version: required

requirements:
  minimum_annual_history_years: 5
  minimum_quarter_history: 8
  max_fact_age_days: 550
  required_metrics:
    - revenue_cagr_5y
    - pat_cagr_5y
    - roic_median_5y
    - ocf_to_pat_5y
    - net_debt_to_ebitda
    - interest_coverage
    - dilution_5y
  missing_data_policy: exclude_and_report

filters:
  all:
    - metric: revenue_cagr_5y
      operator: gte
      value: 0.10
    - metric: pat_cagr_5y
      operator: gte
      value: 0.10
    - metric: roic_median_5y
      operator: gte
      value: 0.15
    - metric: ocf_to_pat_5y
      operator: gte
      value: 0.90
    - metric: net_debt_to_ebitda
      operator: lte
      value: 1.50
    - metric: interest_coverage
      operator: gte
      value: 4.0
    - metric: promoter_pledge_pct
      operator: lte
      value: 0.0

score:
  method: weighted_percentile
  components:
    - metric: roic_median_5y
      weight: 0.25
      direction: higher
    - metric: revenue_cagr_5y
      weight: 0.15
      direction: higher
    - metric: pat_cagr_5y
      weight: 0.15
      direction: higher
    - metric: ocf_to_pat_5y
      weight: 0.20
      direction: higher
    - metric: net_debt_to_ebitda
      weight: 0.10
      direction: lower
    - metric: fcf_margin_median_5y
      weight: 0.15
      direction: higher
  winsorize: [0.01, 0.99]
  sector_neutral: false

outputs:
  limit: 100
  columns:
    - symbol
    - company_name
    - market_cap_inr_crore
    - price
    - data_completeness_pct
    - revenue_cagr_5y
    - pat_cagr_5y
    - roic_median_5y
    - ocf_to_pat_5y
    - net_debt_to_ebitda
    - fcf_margin_median_5y
    - valuation_pe_ttm
    - valuation_ev_ebitda
    - scanner_score

schedule:
  enabled: false
  cron: "30 19 * * 1-5"

alerts:
  on_new_entry: true
  on_top_rank_change: 20
  minimum_data_completeness_pct: 85
```

## 13.3 Safe DSL

The production scanner DSL must not execute arbitrary user Python or shell. Support allowlisted operations:

- comparison;
- boolean `all`, `any`, `not`;
- arithmetic over approved metrics;
- rolling/median/CAGR/trend/z-score/percentile;
- sector/industry relative rank;
- change over time;
- data-quality predicates;
- event predicates;
- score weights;
- neutralization.

Advanced Python/SQL plugins are allowed only as reviewed repository code with manifests and tests.

## 13.4 Built-in scanners

Implement at least the following scanner families as versioned definitions. Use sensible sector-specific exclusions and document the formulas.

### A. Quality Compounders

- durable revenue/PAT growth;
- high median and incremental ROIC;
- strong OCF/PAT and FCF conversion;
- conservative leverage;
- limited dilution;
- no severe governance flags.

### B. Growth at a Reasonable Price

- growth and return quality;
- valuation relative to growth and peers;
- positive cash conversion;
- earnings-revision support when licensed data exists;
- sector-aware valuation.

### C. Earnings and Margin Acceleration

- quarterly revenue/PAT acceleration;
- margin expansion;
- TTM versus prior TTM;
- guidance or estimate change where available;
- quality guardrails.

### D. Cash-Flow Quality

- OCF/PAT;
- FCF/PAT;
- working-capital stability;
- low exceptional-item dependence;
- accrual and cash-conversion flags.

### E. High ROIC and Reinvestment Runway

- sustained ROIC;
- incremental ROIC;
- reinvestment rate;
- growth without leverage/dilution;
- market runway evidence availability.

### F. Deleveraging and Balance-Sheet Inflection

- falling net debt;
- rising interest coverage;
- improving OCF;
- no material equity dilution;
- capex and maturity profile.

### G. Turnaround and Operating Leverage

- revenue recovery;
- margin inflection;
- loss-to-profit transition;
- working-capital improvement;
- debt and cash runway guardrails.

### H. Capital-Cycle / Capex Inflection

- capex and CWIP changes;
- utilization/capacity signals;
- leverage and funding;
- order-book or demand evidence;
- expected commissioning window.

### I. Deep Value / Balance-Sheet Value

- sector-appropriate valuation;
- net cash or asset support;
- normalized earnings;
- liquidity and governance guardrails;
- catalyst field.

### J. Governance and Forensic Red Flags

- auditor changes or qualifications;
- related-party intensity;
- promoter pledge;
- receivable/inventory days deterioration;
- OCF/PAT weakness;
- frequent exceptional items;
- dilution;
- contingent liabilities;
- tax/subsidiary complexity;
- unexplained cash or debt contradictions.

### K. Working-Capital Anomaly

- receivable/inventory/payable trend;
- cash-conversion-cycle deterioration;
- revenue versus receivable growth mismatch;
- CFO divergence from PAT;
- peer-relative anomaly.

### L. Shareholder Yield

- dividend yield;
- buyback yield;
- net debt reduction;
- dilution offset;
- cash-flow coverage.

### M. Ownership/Promoter Change

- promoter, institutional or insider changes where authoritative data is available;
- bulk/block activity where available;
- pledge changes;
- data authority and delay labels.

### N. Small/Mid-cap Quality and Liquidity

- market-cap range;
- minimum liquidity;
- quality and cash conversion;
- governance guardrails;
- concentration and free-float checks.

### O. Special Situations Candidates

- buybacks;
- open offers;
- demergers;
- rights;
- delistings;
- mergers;
- unusual corporate-action filings;
- event completeness and spread fields.

## 13.5 Scanner storage

Use or extend tables equivalent to:

```text
market.scanner_definition
market.scanner_version
market.scanner_schedule
market.scanner_run
market.scanner_run_universe
market.scanner_result
market.scanner_result_metric
market.scanner_alert
market.scanner_validation
```

Every result must be traceable to:

- scanner version;
- as-of time;
- universe version;
- metric version;
- input fact ids;
- quote ids;
- exclusions;
- calculation code revision;
- run environment;
- provider warnings.

## 13.6 Scanner validation and historical review

Before publication/scheduling:

- schema validation;
- metric availability check;
- duplicate/contradictory filter check;
- point-in-time replay on historical dates;
- survivor-bias check;
- sector bias report;
- turnover/stability report;
- missing-data sensitivity;
- rank correlation over time;
- outcome analysis clearly labeled as research, not guaranteed alpha;
- known-result fixture test.

## 13.7 Adding a new fundamental scanner

Implement two supported extension paths.

### Path 1 — Safe no-code/low-code scanner

A user or Charlie creates a draft YAML through a wizard or natural language:

```text
Create a scanner for Indian companies where five-year sales CAGR is above 12%,
ROIC is above 18%, OCF/PAT is above 1, net debt is below zero, and current P/E
is below its five-year median. Exclude banks and require at least 85% data coverage.
```

Charlie must:

1. Resolve requested concepts to approved metric keys.
2. Produce a draft scanner definition.
3. Show assumptions and unavailable metrics.
4. Validate the schema.
5. Run a dry-run on a small universe.
6. Run point-in-time historical checks.
7. Present coverage and bias.
8. Save as `draft`.
9. Require explicit publication/schedule approval.

### Path 2 — Reviewed advanced scanner plugin

Repository layout:

```text
skills/research/scanners/{scanner_slug}/
  SCANNER.md
  manifest.yaml
  scanner.yaml
  input.schema.json
  output.schema.json
  implementation/
  tests/
  fixtures/
  LICENSES.md
```

Manifest must declare:

- deterministic functions used;
- data requirements;
- source/provider requirements;
- risk class;
- owner;
- sector applicability;
- point-in-time behavior;
- test suite;
- output fields;
- schedule permission;
- version and changelog.

Do not dynamically load unreviewed code from the UI.

## 13.8 Scanner APIs and MCP tools

Expose equivalent capabilities to:

```text
GET  /v1/scanners
POST /v1/scanners
GET  /v1/scanners/{scanner_id}
POST /v1/scanners/{scanner_id}/validate
POST /v1/scanners/{scanner_id}/run
POST /v1/scanners/{scanner_id}/publish
POST /v1/scanners/{scanner_id}/schedule
GET  /v1/scanners/{scanner_id}/runs
GET  /v1/scanner-runs/{run_id}
GET  /v1/scanner-runs/{run_id}/results
POST /v1/scanner-results/{result_id}/watch
POST /v1/scanner-results/{result_id}/start-research
POST /v1/scanners/from-natural-language
```

MCP tools:

```text
ai_os_list_fundamental_scanners
ai_os_get_fundamental_scanner
ai_os_create_fundamental_scanner_draft
ai_os_validate_fundamental_scanner
ai_os_run_fundamental_scanner
ai_os_publish_fundamental_scanner
ai_os_schedule_fundamental_scanner
ai_os_scanner_run_results
ai_os_add_scanner_candidate_to_watchlist
ai_os_start_research_from_scanner_result
```

## 13.9 Scanner UI

Build:

- scanner catalog;
- scanner builder/wizard;
- definition editor with safe validation;
- run controls and as-of date;
- coverage summary;
- exclusion reasons;
- sortable result table;
- metric detail drawer showing formulas and source fact ids;
- version comparison;
- run comparison;
- schedule/alert settings;
- “Add to watchlist” and “Start full research” actions;
- Obsidian export/link.

## Exit gate

- At least five built-in fundamental scanners run on the available real universe.
- Results show coverage and exclusions honestly.
- One scanner is created through natural language, validated, saved as draft, run, and published only after approval.
- A result can create a watchlist entry and start a full research case.
- A scanner result is reproducible from its input fact ids and definition version.

---

# 14. Milestone 8 — Charlie and MCP integration

## Goal

Make Charlie the universal entry point for research, knowledge, following and scanners.

## 14.1 Charlie command contract

For significant commands, return:

```yaml
understood_objective:
affected_entities:
affected_books_or_clients:
plan:
agents_assigned:
tools_and_sources:
source_freshness:
calculations_run:
conclusion:
confidence:
bear_case:
contradictions:
missing_data:
risk_flags:
approvals_needed:
artifacts_created:
dashboards_updated:
memory_written:
next_recommended_action:
```

## 14.2 Required Charlie commands

Support commands such as:

```text
Start a complete long-term research case on Wipro using all existing warehouse and Obsidian evidence first. Acquire missing official sources, reconcile ten years of financials, analyze industry, moat, governance and forensics, build valuation and scenarios, run a red team, write the case into Obsidian, and show me decision readiness. Do not give an investment verdict if critical data is missing.

Research NSE:SHIVALIK even though it is not currently in a client portfolio. Create the company and research case if needed.

Show me every unresolved evidence gap across active research cases and assign the correct collectors.

Follow this investor and these two Substacks. Map new posts to holdings and watchlists, but require primary-source corroboration before adding facts.

Run the India Quality Compounder, Cash-Flow Quality, and Governance Red Flag scanners as of the latest complete market day. Show coverage, excluded names, top candidates and key reasons.

Create a draft scanner for high-ROIC net-cash companies trading below their own five-year median P/E. Validate it, run a historical replay, but do not schedule it until I approve.

Start full research on the top three selected scanner candidates.

Show the knowledge graph around Wipro, including evidence, investors who mentioned it, active cases, thesis claims, contradictions, peers and portfolio links.
```

## 14.3 Tool permission

- Research reads and deterministic calculations: automatic with audit.
- Internal task/case/note/scanner-draft writes: policy-allowed and audited.
- Authenticated source refresh: local connector policy.
- Publication/scheduling of a scanner: explicit approval or configured policy.
- Any external write or financial action: not enabled in this phase.

## 14.4 MCP quality

Register tools through the existing tool registry and MCP server. Every tool needs:

- typed schema;
- risk class;
- timeout;
- idempotency behavior;
- audit entry;
- error envelope;
- source freshness/warnings;
- tests;
- documentation.

Do not add more behavior directly into the already large MCP module than is necessary for registration. Put domain logic in smaller modules.

## Exit gate

One Charlie command creates a durable research plan, visible tasks, real specialist activity, source requests, calculations, Obsidian writebacks, UI updates, and a validated result packet. Charlie accurately distinguishes queued, running, finished, validated, blocked and decision-ready states.

---

# 15. Milestone 9 — Research Desk UI and truthful 3D office

## Goal

Make the workflow operable without shell commands and visible in the live office.

## 15.1 Research Factory pages

Create or complete:

```text
/research
/research/new
/research/cases
/research/cases/:caseId
/research/companies/:companyKey
/research/evidence
/research/following
/research/ideas
/research/scanners
/research/scanners/:scannerId
/research/knowledge-graph
```

Adapt to the existing routing and navigation conventions.

## 15.2 New research intake

The user can enter:

- company name/ticker/ISIN;
- exchange;
- research type;
- decision question;
- horizon;
- book/client/watchlist context;
- as-of date;
- urgency.

Show identity candidates before starting when ambiguous.

## 15.3 Company workspace tabs

- Overview;
- Sources and Evidence;
- Financial History;
- Business and Industry;
- Moat and Competition;
- Management and Capital Allocation;
- Governance and Forensics;
- Valuation and Scenarios;
- Thesis and Red Team;
- Committee and Decision;
- Monitoring;
- Knowledge Graph;
- Reports.

Every page shows:

- source cutoff;
- price timestamp;
- freshness;
- data completeness;
- reported versus derived versus estimated fields;
- active run/task state;
- blockers;
- citations;
- affected book/client.

## 15.4 Investor/following UI

- Add source/person;
- connection status;
- last successful refresh;
- new items;
- source score;
- author score;
- linked companies/themes;
- portfolio overlap;
- idea cards;
- primary-evidence status;
- pause/delete with confirmation and audit.

## 15.5 Scanner UI

Implement the catalog, builder, run, validation, history, results, schedule and research-start workflows defined above.

## 15.6 3D office integration

Map real research work to existing rooms and agents:

- Research Intake;
- Filings and Evidence Library;
- Fundamental Research;
- Financial Modelling;
- Governance and Forensics;
- Valuation Lab;
- Committee Room;
- Archive/Memory.

For each active agent display:

- current task;
- case/company;
- stage;
- model route;
- current tool;
- source count;
- progress;
- elapsed time;
- blocker;
- cost;
- latest output.

Clicking an agent must show task timeline, messages, sources, calculations, tool calls, artifacts, approvals and errors. Let me talk to, pause, resume or redirect the agent through audited APIs.

Use SSE or WebSocket events sourced from durable rows. The 3D scene has no independent authority. Provide full 2D fallback parity.

## Exit gate

A user can start Wipro research from the UI, watch real agents work in 2D/3D, inspect evidence gaps, open resulting Obsidian notes and graph, run a scanner, start a case from a scanner result, and inspect a followed investor’s idea card.

---

# 16. Milestone 10 — Monitoring, schedules and thesis drift

## Goal

Keep research alive after the initial report.

## 16.1 Company monitors

On each new filing, result, presentation, transcript, guidance change, price move, ownership change, management event, corporate action, rating action, or material news item:

1. map it to companies, cases, portfolios and watchlists;
2. compare it with prior facts and assumptions;
3. calculate materiality;
4. update evidence and facts;
5. run only relevant specialists;
6. create a thesis-drift report;
7. alert only when thresholds are crossed;
8. reopen review when a thesis-break condition triggers.

## 16.2 Followed-source monitors

- scheduled refresh with bounded concurrency;
- backoff and provider health;
- deduplication;
- high-priority author alerts;
- holdings/watchlist impact;
- daily digest;
- prompt-injection quarantine;
- copyright-safe storage.

## 16.3 Scanner schedules

- run after source/fact refresh;
- use the latest completed point-in-time snapshot;
- create alerts for new entries, exits, rank changes and material metric changes;
- suppress duplicates;
- retain run history;
- allow pause and replay.

## 16.4 Daily research brief

Produce a concise cited brief containing:

- new filings for holdings/watchlist/research cases;
- research gaps and blocked agents;
- thesis-drift events;
- followed-source items with high portfolio relevance;
- new scanner entrants;
- companies needing review;
- source or data-quality degradation.

Write it to UI and Obsidian. Do not include unsupported trade recommendations.

## Exit gate

A new source item, filing or scanner change updates the correct company/case, produces an auditable task or alert, updates Obsidian incrementally, and does not duplicate prior events.

---

# 17. Required database and event design

Inspect existing tables and adapt names, but the completed system must represent the following concepts without duplication.

## 17.1 Research

```text
research.company or existing research.companies
research.company_identifier
research.company_alias
research.case
research.case_question
research.case_run
research.case_step
research.evidence_requirement
research.source_request
research.case_evidence
research.claim
research.claim_evidence
research.contradiction
research.specialist_opinion
research.scenario
research.valuation_case
research.monitoring_trigger
research.committee_run
research.decision
research.case_artifact
research.thesis_version
research.thesis_diff
```

## 17.2 Sources and following

```text
research.source_registry
research.source_profile
research.person_or_author
research.person_source_profile
research.source_item
research.source_item_entity
research.source_item_claim
research.author_scorecard
research.publication_scorecard
research.idea_card
research.idea_card_evidence
research.idea_triage
```

## 17.3 Knowledge

```text
knowledge.obsidian_notes
knowledge.note_links
knowledge.note_entity_links
knowledge.note_case_links
knowledge.note_evidence_links
knowledge.graph_nodes or graph view
knowledge.graph_edges or graph view
knowledge.index_runs
knowledge.vector_chunks
knowledge.unresolved_links
```

## 17.4 Scanners

```text
market.scanner_definition
market.scanner_version
market.scanner_schedule
market.scanner_run
market.scanner_run_universe
market.scanner_result
market.scanner_result_metric
market.scanner_alert
market.scanner_validation
```

## 17.5 Agent/event links

Every case, source refresh, scanner run, note write, committee and report must link to:

- agent task;
- task steps;
- tool calls;
- model calls;
- artifacts;
- approvals where relevant;
- cost;
- event stream;
- audit entries.

Use migrations with reversible or well-documented forward-only behavior. Add indexes, uniqueness constraints, foreign keys, check constraints and idempotency keys.

---

# 18. Required service boundaries

Do not expand the monolith. Create focused modules or packages equivalent to:

```text
services/research-factory/
services/source-acquisition/
services/document-processing/
services/fact-normalization/
services/valuation-engine/
services/scanner-engine/
services/research-following/
services/knowledge-graph/
services/obsidian-writeback/
services/knowledge-retrieval/
services/research-monitoring/
```

Within the current repository layout, place them where they integrate cleanly. Each service exposes typed Python interfaces and is registered through the existing API/MCP compatibility layers.

Suggested internal interfaces:

```python
class CompanyResolver:
    def resolve(self, query, exchange=None, as_of=None): ...

class ResearchCaseService:
    def create_case(self, request): ...
    def run_case(self, case_id): ...
    def readiness(self, case_id): ...

class EvidencePlanner:
    def build_requirements(self, case_id): ...
    def inventory(self, case_id): ...
    def create_missing_requests(self, case_id): ...

class SourceAcquisitionService:
    def acquire(self, source_request_id): ...

class FactNormalizationService:
    def normalize_document(self, evidence_id): ...
    def reconcile_company(self, company_id, as_of): ...

class DeterministicResearchMetrics:
    def calculate_company_metrics(self, company_id, as_of): ...

class KnowledgeGraphService:
    def upsert_entity_links(self, ...): ...
    def neighborhood(self, node_id, depth=1, filters=None): ...

class ObsidianWritebackService:
    def update_managed_section(self, note_path, section_id, content, metadata): ...

class ResearchSourceFollowingService:
    def follow(self, source_definition): ...
    def refresh(self, source_id): ...
    def create_idea_cards(self, source_item_id): ...

class FundamentalScannerService:
    def validate(self, scanner_version): ...
    def run(self, scanner_version, as_of, universe_version): ...
    def replay(self, scanner_version, dates): ...
```

---

# 19. Testing requirements

Do not call the work complete without tests.

## 19.1 Unit tests

- identity and symbol resolution;
- source hierarchy;
- evidence requirement satisfaction;
- period/unit/currency normalization;
- restatement handling;
- statement reconciliation;
- derived metrics;
- valuation;
- managed Obsidian block merging;
- wikilink/alias resolution;
- incremental Qdrant upsert/delete;
- source-item deduplication;
- idea-card extraction schema;
- scanner DSL parsing;
- scanner metric evaluation;
- missing-data policy;
- historical universe selection;
- scanner ranking;
- event idempotency;
- task state transitions.

## 19.2 Contract tests

- API request/response schemas;
- MCP tool schemas;
- source adapters;
- Obsidian writeback;
- Qdrant metadata;
- scanner definition versioning;
- agent event stream.

## 19.3 Golden cases

### Wipro

- identity resolved;
- evidence inventory;
- current quote;
- ten-year financials where available;
- OCF/capex/FCF reconciliation;
- share-count reconciliation;
- business/industry/moat;
- governance/forensics;
- valuation/scenarios;
- citations;
- red team;
- report reproducibility;
- Obsidian graph;
- monitoring trigger.

### Generic non-held company

Use a real company such as `NSE:SHIVALIK` or another verified symbol. It must start without a pre-existing holding thesis.

### Investor/source following

Use a public fixture/feed and one local authenticated connector when available. Verify deduplication, entity mapping, prompt-injection quarantine, copyright-safe storage and idea-card creation.

### Scanner

Create a tiny point-in-time fixture universe with known expected results. Verify the same scanner version and as-of date produce identical ranking and exclusions.

### Obsidian

- human text preserved;
- unchanged re-run produces no diff;
- changed managed block updates only that block;
- deleted note removes only its own vector points/edges;
- backlinks and graph edges resolve;
- full rebuild is explicit.

## 19.4 Failure injection

Test:

- unavailable external SSD;
- Postgres unavailable;
- Redis unavailable;
- Qdrant unavailable;
- embedding model unavailable;
- source timeout;
- corrupted PDF;
- incorrect ticker;
- restated filing;
- missing quote;
- stale quote;
- provider rate limit;
- authenticated source logged out;
- malicious instructions inside a source item;
- duplicate source webhook;
- duplicate scanner run request;
- failed note write;
- model endpoint down.

The system should fail clearly and preserve durable state, not silently return empty data as success.

---

# 20. Definition of done

The Research Desk v1 is done only when all of the following are verified.

## 20.1 Start any company research

- Company can be entered by name/ticker/ISIN.
- Identity is verified or ambiguity is surfaced.
- Existing evidence and Obsidian knowledge are reused first.
- Missing evidence creates tasks.
- Real source acquisition runs.
- Facts normalize and reconcile.
- Deterministic ratios and valuation run.
- Specialists produce cited outputs.
- Red team and committee are stored.
- Readiness is distinct from orchestration completion.
- Reports and source manifests reproduce.
- Monitoring is created.

## 20.2 Obsidian and knowledge graph

- Existing vault is preserved.
- Company notes use managed sections.
- Human edits survive updates.
- Notes link to cases, evidence, people, sources, themes, portfolios and reports.
- Incremental indexing works.
- Hybrid search works.
- Graph neighborhood works in API, MCP and UI.
- Obsidian is human memory; Postgres remains fact/state truth.

## 20.3 Investor following

- Sources/people can be followed and paused.
- Refreshes are read-only and auditable.
- New items deduplicate and map to entities/themes.
- Commentary is quarantined as untrusted.
- Idea cards require primary-evidence follow-up.
- Author/source scorecards work.
- Holdings/watchlist relevance works.
- Daily digest works.

## 20.4 Fundamental scanners

- Built-in scanner catalog exists.
- Scanners are versioned and point-in-time.
- Data coverage and exclusions are visible.
- Results trace to metric/fact ids.
- Scanner DSL cannot run arbitrary code.
- Natural-language scanner creation produces a draft and validation report.
- New scanner plugin path is documented and tested.
- Runs can be scheduled.
- Results can create watchlist entries and research cases.

## 20.5 Charlie and office

- Charlie can start and manage all workflows above.
- Every claimed action has a task/tool/artifact/database/note record.
- Research agents show real states in 3D and 2D.
- I can inspect and talk to agents.
- No fake activity appears.

## 20.6 Operational quality

- Migrations pass from a clean test database.
- Existing runtime still starts.
- UI builds.
- MCP `tools/list` works.
- New smoke tests pass.
- Backups and restore steps are documented.
- Source/provider/model failures are visible.
- No live broker action is enabled.

---

# 21. Required end-to-end demonstration

After implementation, perform and document this exact sequence.

## Demo A — Wipro full research

Command through Charlie:

```text
Start a complete long-term research case on NSE:WIPRO as of the current timestamp.
Reuse all existing Postgres, artifact, Qdrant and Obsidian evidence first. Acquire missing
primary sources, build and reconcile ten years of financial history, calculate deterministic
quality metrics and valuation, analyze industry, TAM, moat, management, capital allocation,
governance and forensic risks, run base/bull/bear and red-team reviews, convene the Research
Committee, write linked notes into Obsidian, update the knowledge graph, and create monitoring
triggers. Do not issue a BUY/SELL decision if any critical evidence requirement is unresolved.
Show me the live agents, progress, blockers, sources, costs, artifacts and final readiness.
```

Capture:

- case id;
- task graph;
- event timeline;
- source manifest;
- evidence-gap before/after;
- fact coverage;
- reconciliation results;
- valuation versions;
- Obsidian paths and diff;
- graph query result;
- report paths;
- UI screenshots;
- tests/commands.

## Demo B — Research a non-held company

```text
Start full research on NSE:SHIVALIK even if no holding thesis exists. Verify identity,
create the company and case if needed, and run the same evidence-first workflow.
```

Prove no pre-existing portfolio row is required.

## Demo C — Follow a source and create an idea

```text
Follow the configured ValuePickr source and one configured Substack or public RSS source.
Refresh them, show new items mapped to my holdings and watchlist, create idea cards for material
items, and find primary evidence before escalating any claim into a research case.
```

## Demo D — Run built-in scanners

```text
Run India Quality Compounders, Cash-Flow Quality, Earnings Acceleration, Deleveraging,
and Governance Red Flags using the latest complete point-in-time universe. Show universe size,
eligible coverage, exclusions, stale fields, top results, metric inputs, and result lineage.
```

## Demo E — Add a new scanner

```text
Create a draft scanner for non-financial Indian companies with five-year sales CAGR above 12%,
median ROIC above 18%, five-year OCF/PAT above 1.0, net cash, no promoter pledge, and current P/E
below the company’s own five-year median. Require at least 85% data completeness. Validate it,
run a dry run and historical replay, show sector bias and missing-data sensitivity, but do not
schedule it until I approve.
```

## Demo F — Start research from a scanner result

Select one real scanner candidate and execute:

```text
Add this candidate to the research watchlist and start a full evidence-backed research case.
```

## Demo G — Knowledge graph

```text
Show the Wipro knowledge graph with official sources, evidence anchors, facts, research claims,
contradictions, investors or publications that mentioned it, peers, active cases, Obsidian notes,
monitoring events, watchlists and portfolio links.
```

---

# 22. Final implementation report

When the exit gates pass, create:

```text
docs/research-desk/FINAL_IMPLEMENTATION_REPORT.md
```

and:

```text
ai memory/00 AI OS/Implementation/Research Desk v1 - Final Implementation Report.md
```

The report must contain:

- live commit and branch;
- architecture actually implemented;
- schema changes;
- APIs and MCP tools;
- Obsidian note/graph contract;
- source registry and adapters;
- scanner catalog and extension guide;
- UI routes;
- agent/3D-office mapping;
- model routes used;
- commands run;
- test results;
- performance and memory observations on the M4 16 GB Mac;
- data/source limitations;
- security/licensing notes;
- screenshots and artifact paths;
- unresolved blockers;
- exact next phase.

Also update top-level `STATUS.md` truthfully. Do not label the Research Desk complete unless the end-to-end demos and tests pass.

---

# 23. First actions to execute now

Begin immediately with this order:

1. Read `AGENTS.md` and the v11 blueprint.
2. Audit Git state and identify the live commit.
3. Inventory current research, knowledge, source, scanner, agent, MCP and UI capabilities.
4. Run existing smoke tests and health checks.
5. Back up/verify Postgres, Obsidian and artifacts.
6. Write the baseline audit and implementation status.
7. Create the focused feature branch.
8. Implement Milestone 1 generic company/research cases without breaking current thesis workflows.
9. Implement the evidence planner and gap loop.
10. Implement incremental Obsidian/Qdrant graph indexing.
11. Complete Wipro as the golden research path.
12. Add investor/source following.
13. Add the fundamental scanner factory and extension mechanism.
14. Expose APIs, MCP tools, UI and 3D-office states.
15. Run all end-to-end demos and produce the final implementation report.

Do not return only a plan. Start with the baseline audit, then implement and verify the first milestone in the same work session. At the end of each milestone, provide a compact progress summary, commands and test evidence, update the implementation ledger, commit the milestone, and continue unless a genuine external blocker requires my input.

## COPY-PASTE PROMPT ENDS HERE

---

# Useful operator commands after the feature exists

## Start a company research case

```text
Charlie, start a full fundamental research case on NSE:WIPRO for a five-year holding horizon. Reuse existing evidence first, close critical source gaps, update Obsidian and the graph, and show decision readiness rather than forcing a verdict.
```

## Follow an investor or publication

```text
Charlie, add this investor and publication to my followed research sources. Monitor new posts, map them to holdings and watchlists, create evidence-seeking idea cards, and include only material items in my daily research brief.
```

## Run fundamental scanners

```text
Charlie, run the Quality Compounder, Cash-Flow Quality and Governance Red Flag scanners on the latest complete NSE/BSE universe. Show data coverage, exclusions and source lineage.
```

## Create another scanner

```text
Charlie, draft a scanner for companies with improving asset turns, stable gross margins, falling working-capital intensity and rising incremental ROIC. Exclude financials, explain every metric, validate point-in-time availability, replay it historically, and leave it as a draft for approval.
```

---

# Compact continuation prompt for a later coding session

```text
Continue implementing Research Desk v1 in dev2495/ai-investment-os-recovery from the current branch and implementation ledger. Read AGENTS.md, docs/research-desk/IMPLEMENTATION_STATUS.md, the v11 blueprint, recent commits, test results, and Obsidian implementation notes before changing code. Resume the first unverified milestone. Preserve existing user work, use real data only, keep Postgres as system of record and Obsidian as human-readable graph memory, run tests, update the ledger and Obsidian after each milestone, commit focused changes, and continue automatically unless blocked by credentials, destructive changes, licensing, private-data ownership or live financial action. Do not return only a plan and do not claim completion without the defined end-to-end demos.
```
