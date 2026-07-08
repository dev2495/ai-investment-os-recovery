# AI OS Agent Runner

Local agent runner skeleton over the AI OS warehouse.

Run:

```bash
_ai_os_runtime/agents/agent_runner.py --agent Jarvis
_ai_os_runtime/agents/agent_runner.py --agent "Data Steward"
_ai_os_runtime/agents/agent_runner.py --agent "Trading Desk Agent"
```

Current behavior:

- Reads from safe warehouse views.
- Produces scoped, evidence-backed status notes.
- Writes notes to `ai memory/00 AI OS/Agent Outputs`.
- Logs each run in `agent.run_log`.

This is not yet an autonomous LLM loop. It is the execution shell that local/cloud models can plug into next.
