# AI OS Agent Instructions

Do not fight repeated errors. Whenever the same error appears twice, pause implementation, research the web for 3-5 plausible fixes, choose the most efficient fix, then implement and verify it.

Work from the Obsidian vault as the source of truth. Important decisions, research outputs, runbooks, and completed workflows should be written back into structured notes.

Keep agents role-scoped. Jarvis routes work, but specialist agents should own research, quant, coding, portfolio, risk, automation, and documentation tasks.

Prefer evidence over narrative. Any market, portfolio, code, or operational claim should point to a source, command, dataset, note, or live check.

## Cursor Cloud specific instructions

This checkout is the recovered AI OS workspace: vault notes live in `ai memory/`, runnable code lives in `_ai_os_runtime/`.

Set these when running API, MCP, or scripts from a Cloud Agent VM:

```bash
export AI_OS_VAULT_ROOT="/workspace"
export AI_OS_RUNTIME_ROOT="/workspace/_ai_os_runtime"
export PYTHONPATH="/workspace"
```

Do not run `_ai_os_runtime/scripts/start_runtime.sh` or `_ai_os_runtime/scripts/start_ai_office_live.sh` here. Those assume macOS Docker Desktop on the external SSD, LaunchAgents, and hardcoded `/Volumes/Devarsh SSD/...` vault paths. Compose also requires pre-created external Docker volumes. Cloud Agents do not have that warehouse stack unless you add it explicitly.

Cloud-safe checks:

```bash
npm ci --prefix _ai_os_runtime/ai-office-ui
npm run build --prefix _ai_os_runtime/ai-office-ui
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py _ai_os_runtime/agents/agent_runner.py
PYTHONPATH=/workspace python3 -m unittest _ai_os_runtime.tests.test_serve_spa _ai_os_runtime.tests.test_openrouter_chat _ai_os_runtime.tests.test_charlie_operator_actions
python3 _ai_os_runtime/scripts/verify_vault_path_contract.py
```

Warehouse-backed MCP/API smoke tests (`smoke_mcp_tools.py` and similar) need local Postgres/Timescale, Qdrant, and Redis. Skip them in Cloud Agents unless those services are running.

Do not commit secrets, `.env`, broker credentials, or client statements. Do not place live orders. Write tools must stay limited to the local warehouse and structured vault folders.

