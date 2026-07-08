# Agent Hierarchy, Communications, Models, And External Skill Stack Report

Date: 2026-07-06

## What changed

The AI Office now has a first-class hedge-team operating layer in Postgres and the dashboard:

- `agent.org_hierarchy`: reporting lines, authority scopes, approval boundaries, delegation rules.
- `agent.agent_characters`: character cards for the live AI office view.
- `agent.mailboxes`: one internal mailbox/email address per active agent.
- `agent.agent_messages`: inter-agent handoff messages and operating protocol threads.
- `agent.model_catalog`: local/cloud model inventory and intended use.
- `agent.agent_model_assignments`: per-agent primary model, fallback route, escalation route, and cost policy.
- External skill bundles added from FinceptTerminal, OpenAlgo OKF, and Vibe-Trading.

## Live verification

API/UI verification after restart:

- API health: `ok`
- UI: `http://127.0.0.1:5177/`
- Snapshot issues: `0`
- Active agents: `20`
- Agent hierarchy rows: `20`
- Agent mailboxes: `20`
- Agent messages: `5`
- Agent model rows: `20`
- External repo-backed skills: `27`
- Agent skill matrix rows exposed in API: `57`
- Active skills in office overview: `52`

External skill counts:

- FinceptTerminal skills: `10`
- OpenAlgo skills: `7`
- Vibe-Trading skills: `10`

## Fincept status

FinceptTerminal is installed locally as a reference/component checkout:

- Source: `_ai_os_runtime/external_components/FinceptTerminal`
- Install status in warehouse: `installed`
- Build status in warehouse: `build_success`
- Runtime mode: `local_development_install`

Important boundary: the AI Office is not yet delegating live agent work into the Fincept Qt runtime. Today we imported Fincept skills and component patterns into our agent skill registry. Direct runtime adapters are marked as `adapter_planned`.

Fincept skill bundles now registered:

- Fincept Tool RAG Catalog
- Fincept Equity Research Tools
- Fincept Report Builder
- Fincept News And RSS Analysis
- Fincept Options IV/OI Suite
- Fincept Alpha Arena Research
- Fincept Historical Data Store
- Fincept Agent Chat Sessions
- Fincept MCP Bridge
- Fincept Government And Macro Data

Decision: Fincept should be used as a component/reference layer for research UI, MCP/tool registry patterns, report builder, news/RSS schema, options data structures, alpha arena, and historical data store. It should not replace the AI OS warehouse, Obsidian memory, or Charlie/Jarvis operating layer.

## OpenAlgo OKF decision

OpenAlgo OKF is useful for execution, indicators, backtesting, options analytics, market data, streaming, and alert concepts.

OpenAlgo skills now registered:

- OpenAlgo Market Data API
- OpenAlgo Execution Guarded
- OpenAlgo Indicator Scanner
- OpenAlgo VectorBT Backtesting
- OpenAlgo Options Analytics Suite
- OpenAlgo WebSocket Streaming
- OpenAlgo WhatsApp Alerts

Decision: use OpenAlgo as a future local API/skill adapter, but keep live execution blocked by `Execution Safety Agent` until explicit approval, risk pass, connector proof, and kill switch exist.

## Vibe-Trading decision

Vibe-Trading is useful for MCP tool exposure, research autopilot, swarm/investment committee patterns, shadow-account learning, journal analysis, run library reports, market screening, options analysis, channel adapters, and safety patterns.

Vibe-Trading skills now registered:

- Vibe-Trading MCP Tool Catalog
- Vibe Research Autopilot
- Vibe Swarm Investment Committee
- Vibe Shadow Account Learning
- Vibe Trade Journal Analysis
- Vibe Market Screening
- Vibe Options Analysis
- Vibe Run Library Reports
- Vibe IM Channel Runtime
- Vibe Safety Runtime Patterns

Decision: use Vibe-Trading as a reference and possible MCP-backed component, especially for research autopilot and trade-journal/shadow-account workflows. Do not run it as the main OS.

## How agents talk now

Agents now have two communication layers:

1. Durable work layer:
   - `agent.tasks`
   - `agent.inbox_items`
   - `agent.worker_runs`
   - dashboard widgets
   - Obsidian output notes

2. Internal message layer:
   - `agent.mailboxes`
   - `agent.agent_messages`
   - `agent.v_agent_mailboxes`
   - `agent.v_agent_message_threads`

Seeded message threads:

- Charlie Munger to Jarvis: evidence-first operating protocol.
- Portfolio Manager to Research Analyst: holdings thesis maintenance.
- News Analyst to Filings Analyst: exchange/news items become filing facts.
- Strategy Generator to Model Validation Agent: no generated strategy goes live without challenge.
- Trading Desk Agent to Execution Safety Agent: live execution remains gated.

## Hierarchy

Top structure:

- Devarsh: human owner and final approval authority.
- Charlie Munger: chief investment orchestrator.
- Jarvis: chief of staff/runtime operator.
- Portfolio Manager: portfolio office lead.
- Research Analyst: research office lead.
- Strategy Generator: quant lab lead.
- Trading Desk Agent: trading desk lead.
- Risk Agent: independent challenge function.

Specialist desks:

- News Analyst
- Filings Analyst
- Special Situations Agent
- Strategy Intake Agent
- Strategy Research Agent
- Backtest Engineer
- Optimizer Agent
- Model Validation Agent
- Execution Safety Agent
- Trade Journal Learning Agent
- Data Steward
- Librarian Agent
- Browser Research Runner
- Automation Engineer

## Model plan

The default model policy is local-first:

- Daily cheap work: `llama3.2:3b`
- Light reasoning upgrade: `qwen3:4b`
- Optional workhorse: `qwen3:8b`
- Optional heavy local reasoning: `qwen3:14b`
- Retrieval embeddings: `mxbai-embed-large`
- Code/system escalation: `gpt-5-codex` by approval
- High-stakes investment/client/legal escalation: frontier model by approval

Per-agent assignments are in `agent.agent_model_assignments` and exposed through `agent.v_agent_model_matrix`.

## Dashboard/API changes

New snapshot keys:

- `agent_office_overview`
- `agent_org_chart`
- `agent_mailboxes`
- `agent_messages`
- `agent_models`
- `external_skills`

New dashboard panels:

- Hedge Team Hierarchy
- Agent Mailboxes
- Agent Messages
- Agent Model Routing
- External Skill Stack

## Remaining work

The next correct implementation step is to make communication actionable:

1. Add `POST /api/agents/messages` so Charlie/Jarvis can send messages between agents from chat/tool calls.
2. Build the always-on worker daemon so messages can trigger tasks without pressing a UI button.
3. Add direct adapters in this order:
   - OpenAlgo market-data read-only adapter.
   - Vibe-Trading MCP read-only adapter.
   - Fincept component bridge for tool catalog/report references.
4. Keep broker execution disabled until `Execution Safety Agent` and `Risk Agent` enforce the full gate.

## Sources reviewed

- FinceptTerminal local checkout: `_ai_os_runtime/external_components/FinceptTerminal`
- Fincept MCP/tool files: `fincept-qt/src/mcp`
- Fincept agent chat/session files: `fincept-qt/src/screens/agent_config`, `fincept-qt/src/storage/repositories`
- OpenAlgo OKF: `https://github.com/marketcalls/openalgo/tree/main/okf`
- OpenAlgo skills docs: `https://docs.openalgo.in/skills/backtesting`
- Vibe-Trading: `https://github.com/HKUDS/Vibe-Trading`
