# Blueprint v9 Operating Model Registry v1

Date: 2026-07-07
Owner: Charlie Munger
Runtime operator: Jarvis
Status: implemented and verified

## Outcome

The v9 AI Investment OS blueprint is now machine-readable in the live warehouse instead of existing only as Markdown.

This gives the system a runtime coverage board for the hedge-fund OS plan: domains, owners, requirements, mapped runtime objects, acceptance criteria, current status, and next actions.

## What Changed

Added migration:

- `_ai_os_runtime/postgres/init/102_blueprint_v9_operating_model.sql`

New warehouse tables:

- `core.os_blueprint_versions`
- `core.os_blueprint_domains`
- `core.os_blueprint_requirements`

New warehouse views:

- `core.v_os_blueprint_v9_summary`
- `core.v_os_blueprint_v9_domains`
- `core.v_os_blueprint_v9_requirements`

New control-plane module:

- `blueprint_v9_operating_model`

New API snapshot keys:

- `blueprint_v9_summary`
- `blueprint_v9_domains`
- `blueprint_v9_requirements`

New MCP tools:

- `ai_os_blueprint_v9_summary`
- `ai_os_blueprint_v9_requirements`

New AI Office panel:

- `Blueprint v9 Coverage`

## Live Registry Counts

Database verification:

```text
domains: 21
requirements: 35
done_requirements: 1
partial_requirements: 31
planned_requirements: 3
mapped_requirements: 35
```

The system is deliberately conservative. Existing live modules are marked partial unless the specific acceptance criteria are fully proven.

## Verification

Migration apply:

```text
CREATE TABLE
INSERT 0 1
INSERT 0 21
INSERT 0 35
CREATE VIEW
INSERT 0 1
INSERT 0 2
```

Compile/build:

```text
python3 -m py_compile _ai_os_runtime/api/ai_os_api_server.py _ai_os_runtime/mcp_server/ai_os_mcp_server.py
npm --prefix _ai_os_runtime/ai-office-ui run build
```

Result:

```text
TypeScript/Vite build passed.
Python compile passed.
```

API snapshot verification:

```text
blueprint_v9_summary: 6 rows
blueprint_v9_domains: 21 rows
blueprint_v9_requirements: 35 rows
issues: 0
```

MCP verification:

```text
tools/list found ai_os_blueprint_v9_summary: true
tools/list found ai_os_blueprint_v9_requirements: true
total MCP tools: 114
ai_os_blueprint_v9_summary returned domain coverage
ai_os_blueprint_v9_requirements returned planned requirements
```

Health:

```text
http://127.0.0.1:8765/api/health ok=true
db status=ok
```

TradingView remains correctly gated:

```text
tradingview_cdp.available=false
next_action=Relaunch TradingView Desktop with --remote-debugging-port=9222 before desktop MCP control.
```

## UI Verification

The AI Office React app now has a `Blueprint v9 Coverage` panel. The build passed.

Browser-level Playwright smoke was not run because Playwright is not installed in the UI package. This is not a runtime failure, but a test-harness gap. The API payload and TypeScript build verify that the panel is wired and compile-safe.

## Why This Matters

This prevents the project from drifting back into untracked planning. Charlie/Jarvis can now query the warehouse and answer:

- Which parts of the hedge-fund OS exist?
- Which are partial?
- Which are still planned?
- Who owns each domain?
- What runtime object maps to each requirement?
- What is the next implementation action?

## Remaining Work

- Reconcile every v8 verified evidence item into the v9 registry.
- Add a UI action to open the full requirement list by domain.
- Add status-update workflow for blueprint requirements.
- Add evidence-note attachment workflow.
- Add checklist-to-warehouse synchronization.
- Use the registry to drive the next implementation sprint: multi-book position object, Symbol Intelligence v2, p2cursor/algo extraction, Long-Term Monte Carlo UI, and Client Folios.

