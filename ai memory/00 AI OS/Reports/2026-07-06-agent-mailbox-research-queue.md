# Agent Mailbox And Research Queue Slice - 2026-07-06

## Outcome

The AI office now has a working internal mailbox triage path and a live Research Factory queue summary. Agents can receive messages, acknowledge them, and route handoffs into task/inbox work items. Research queues now summarize filings, special situations, PDF extraction, memos, and research-agent messages from live warehouse views.

## Implemented

- Added migration `_ai_os_runtime/postgres/init/076_agent_mailbox_triage_research_queue.sql`.
- Added `research.v_research_factory_queue_summary`.
- Added tool registry rows:
  - `ai_os_research_factory_queue_summary`
  - `ai_os_triage_agent_message`
- Added API snapshot key:
  - `research_factory_queue_summary`
- Added API route:
  - `POST /api/agents/messages/triage`
- Added MCP handlers and tool schemas:
  - `ai_os_research_factory_queue_summary`
  - `ai_os_triage_agent_message`
- Added AI Office dashboard panel:
  - `Research Factory Queue`
- Extended `Agent Messages` dashboard rows with:
  - `Ack`
  - `Task`
- Added frontend API function:
  - `triageAgentMessage`

## Live Evidence

Research queue summary:

```text
corporate_filing_inbox     total=28 open=26 blocked_or_error=0
filing_collector_runs      total=5  open=0  blocked_or_error=0
filing_pdf_extraction_runs total=2  open=0  blocked_or_error=0
research_agent_messages    total=2  open=2  blocked_or_error=0
special_situation_inbox    total=3  open=3  blocked_or_error=0
special_situation_memos    total=1  open=1  blocked_or_error=0
special_situation_terms    total=1  open=1  blocked_or_error=0
```

API smoke:

```text
GET /api/health -> ok=true
GET /api/snapshot -> issues=[]
agent_mailboxes rows visible = 20
agent_messages rows visible = 50
research_factory_queue_summary rows = 7
```

Message triage smoke:

```text
Created message id = 60
From = Charlie Munger
To = Research Analyst
Subject = Verify research queue and mailbox triage slice
Triaged into generated_task_id = 96
Triaged into generated_inbox_id = 147
Final message status = acknowledged
```

MCP smoke:

```text
tools/list contains ai_os_research_factory_queue_summary = true
tools/list contains ai_os_triage_agent_message = true
ai_os_research_factory_queue_summary rows = 7
ai_os_triage_agent_message rows = 1
ai_os_triage_agent_message status = acknowledged
```

Build verification:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm run build in _ai_os_runtime/ai-office-ui
```

Runtime:

```text
API: http://127.0.0.1:8765/api/health
UI:  http://127.0.0.1:5177/
```

## Remaining Boundary

This completes the first operational mailbox UI and research queue dashboard. It does not yet complete:

- Full threaded conversation detail page.
- Agent comment annotations on reports/charts.
- Committee room view.
- Approval board view.
- Animated live office with hover cards and moving task state.

This slice does not authorize live trading, broker order placement, or autonomous capital action.
