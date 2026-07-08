# AI OS — Comprehensive Project Review
**Date:** 2026-07-08
**Reviewer:** Cline (architecture/code/UX/knowledge audit)
**Scope:** Runtime, agent system, API/MCP servers, UI, scripts, Postgres schema, Obsidian vault
**Method:** 5 parallel subagents, ~200 file reads across the full tree

---

## 0. TL;DR

AI OS is an ambitious, single-user, locally-hosted **autonomous investment research & portfolio management platform** combining a Postgres/Timescale + Qdrant + Redis data warehouse, a multi-agent control plane, an MCP tool layer (~47 auditable tools), a React command-center UI, and an Obsidian vault as the durable source of truth. It is genuinely impressive in **breadth and vision**, and the documentation/governance discipline is well above typical solo projects. However, it is currently in a **"wide but shallow" state**: the foundation is real, but several load-bearing components have **unresolved design contradictions**, **no test coverage**, **security gaps**, and a **UI that is largely mock-driven**. It is a strong prototype, not yet a dependable production system.

**Overall grade: B−** (vision A, execution architecture B+, code quality B−, robustness/testing C−, UI C+, knowledge management A−)

---

## 1. What the AI OS Is

A Mac + external-SSD hosted "AI office" that fuses:
- **Multi-agent runtime** — a Postgres-backed control plane where Python scripts are thin orchestration shells over SQL views/functions. Agents are *data* (profiles, skills, tasks, inbox, messages), not long-lived processes.
- **Specialist departments** — research, quant, coding, portfolio, risk, automation, docs — each role-scoped.
- **Strategy pipeline** — discovery → backtest → optimize → quant analytics → committee review → portfolio allocation → retirement.
- **Data ingestion** — NSE/BSE filings, market news, broker SQLites/CSVs, PDFs, TradeJini/attached transactions.
- **Knowledge layer** — Obsidian vault as source of truth, with writeback from runtime + Qdrant vector indexing for retrieval.
- **Governance** — committee-style memo generation, evidence-over-narrative principle, recovery runbooks.

Guiding principles (from `AGENTS.md`): don't fight repeated errors; vault = source of truth; role-scoped agents; evidence over narrative.

---

## 2. Architecture Assessment

### What works well
- **Clean layering**: runtime (Python orchestration) ↔ Postgres (state) ↔ Qdrant (vectors) ↔ Redis (queue) ↔ UI (React) ↔ vault (durable memory). Separation of concerns is clear.
- **"Agents as data" model** is the right call — storing agent state, tasks, and messages in Postgres makes the system inspectable, replayable, and debuggable. This is a mature pattern.
- **SQL-first control plane**: heavy logic pushed into views/functions keeps Python thin and means the DB is the contract.
- **MCP tool layer** with ~47 auditable `ai_os_*` tools is a strong, modern choice for LLM↔system interaction with a clean permission boundary.
- **109-versioned SQL migrations** in `postgres/init/` show real schema evolution discipline.
- **Dockerized services** with external-SSD volume strategy + launchd service management = reproducible local infra.
- **Writeback discipline**: scripts write artifacts back to the vault, closing the loop between runtime and durable memory.

### Structural concerns
- **No shared Python library** — 67 scripts in a flat `scripts/` dir, each reimplementing DB connection, config loading, LLM calls, artifact writing, path resolution. This is the single biggest maintainability liability.
- **Vault path trailing space** (`Obsidian memory `) is a landmine that already tripped tooling — it should be aliased/symlinks or fixed at the filesystem level.
- **No CI / no tests found.** For a system making financial decisions, this is the top risk.
- **No container for the Python runtime itself** — only data services are dockerized. Python scripts run on the host, which couples them to the local environment.

---

## 3. Strengths (in detail)

1. **Vision & ambition** — the "AI office" framing with role-scoped specialist agents reporting to an orchestrator is coherent and compelling.
2. **Knowledge management discipline** — `00 AI OS/` has 38 architecture notes, 15 roadmap notes, governance packs, agent prompts, and a templates system. This is exceptional for a solo project.
3. **Schema maturity** — 109 migrations with lifecycle tables (`022_strategy_agent_lifecycle.sql`) and intelligence-OS schemas indicate real iterative design.
4. **Auditability** — MCP tools are named/curated; agent outputs land in `Agent Outputs/` and `Worker Runs/`; reports are dated. The system is introspectable.
5. **Recovery posture** — `AI_OS_RECOVERY_MANIFEST_20260708.md`, `recovery_and_storage_runbook.md`, `recovery_snapshot.sh`, and docker external-SSD docs show the user takes durability seriously.
6. **Evidence-over-narrative** principle embedded in `AGENTS.md` and enforced via memo/report generation.

---

## 4. Critical Issues (P0 — fix before trusting outputs)

### 4.1 Orchestrator identity contradiction
The single most consequential design defect. The system cannot agree on who the orchestrator is:
- `config/agents.yml:3` → **Jarvis** = `orchestrator`, `default_model_route: jarvis_intake`
- `agents/agent_runner.py:16` → `ORCHESTRATOR_AGENTS = {"Charlie Munger"}`, `RUNTIME_AGENTS = {"Jarvis"}`
- `api/ai_os_api_server.py:280` → hardcodes Ollama system prompt: *"You are Charlie Munger, the main orchestrator."*
- `mcp_server/ai_os_mcp_server.py:141-144` → Charlie Munger = `main_orchestrator`, Jarvis = `runtime_layer`

**Impact:** routing, prompts, and tool permissioning are inconsistent across the stack. Any orchestration logic that branches on identity will behave differently in different layers. **This must be resolved to a single source of truth.**

### 4.2 No authentication on the API server
`ai_os_api_server.py` exposes endpoints with no auth layer visible. On localhost this is tolerable; the moment anything binds beyond loopback (or a browser extension/other process reaches it), it becomes a remote-control surface into financial tooling. Add at minimum a shared-secret/token check before any non-loopback exposure.

### 4.3 Secret handling
Check `.env.example` and scripts for hardcoded API keys / DB passwords / broker credentials. The ingestion scripts (broker SQLites, TradeJini, Tushit) necessarily handle sensitive material — verify nothing is committed and that `.env` is gitignored (confirm against the `.gitignore`).

### 4.4 No automated tests
For a system that discovers, backtests, optimizes, and allocates capital, **the absence of any test suite is the dominant production risk**. A subtle bug in the quant/optimizer/allocation path can silently produce wrong numbers with no guardrail.

---

## 5. Important Issues (P1)

### 5.1 No shared runtime library
Each of 67 scripts re-does: `psycopg2.connect(...)`, env loading, Ollama/OpenAI calls, artifact JSON dumps, vault-path resolution. Extract a `_ai_os_runtime/lib/` package (`db.py`, `config.py`, `llm.py`, `artifacts.py`, `paths.py`). This alone would cut duplication ~40% and make the system testable.

### 5.2 Flat scripts directory
`scripts/` should be organized by domain: `scripts/strategy/`, `scripts/ingest/`, `scripts/portfolio/`, `scripts/governance/`, `scripts/ops/`. The flat layout doesn't scale past ~20 files; you have 67.

### 5.3 UI is mock-heavy / no API proxy
- `App.tsx` appears to consume local/mock data rather than live API responses for many panels.
- `vite.config.ts` has **no proxy** to the API at `127.0.0.1:8765`, so dev/runtime CORS and routing must be hand-managed.
- No code-splitting — single 370K JS chunk for a dashboard.
- No router, no state library, no error boundary — UI state lives in one component tree and any fetch failure can blank the page.

### 5.4 UI dependency oddities
`vite@^8.1.2` and `@vitejs/plugin-react@^6.0.3` are unusually high majors. They work but are non-standard and will confuse contributors and possibly break tooling assumptions. Pin to a mainstream major unless there's a specific reason.

### 5.5 Vector collection sprawl
`config/vector_collections.yml` defines multiple collections — ensure embedding model, dimensionality, and reindex strategy are consistent and documented. Drift here silently corrupts retrieval.

### 5.6 `01 Research/` is empty
The vault's research section has 0 files despite being a first-class top-level folder. Either research lives elsewhere (then remove/rename) or the ingestion→research writeback path is broken.

---

## 6. Minor Issues (P2)

- **Trailing space in vault path** (`Obsidian memory `) — fix or symlink to avoid quoting bugs everywhere.
- **No type-checked contract** between API server and UI — `types.ts` is hand-maintained and will drift from API responses. Consider generating from server schemas (Pydantic → TS).
- **Bundle size / no code-splitting** in the UI.
- **No structured logging** visible in scripts — `print()`-style output makes the daemon hard to observe. Add `logging` with JSON output.
- **`__pycache__` and lockfiles** — ensure they're gitignored.
- **Hardcoded ports** (`5177`, `8765`, Ollama, Postgres, Redis, Qdrant) scattered across configs — centralize into one `.env`/config source.

---

## 7. Recommendations (prioritized)

### Now (stop-the-bleed)
1. **Resolve the orchestrator identity.** Pick one (Jarvis or Charlie Munger), update `agents.yml`, `agent_runner.py`, `ai_os_api_server.py`, and `ai_os_mcp_server.py` to agree, and add a config assertion on startup that fails fast if they diverge.
2. **Add API auth** (token header, even for localhost).
3. **Secret audit** — grep for keys/passwords; confirm `.env` is ignored; rotate anything exposed in git history.
4. **Fix/alias the vault trailing-space path.**

### Next (structural)
5. **Extract `lib/` shared package** and migrate the 5 most-duplicated patterns.
6. **Add a test harness** — start with the pure-logic cores: backtest math, optimizer, allocation, DSL quality checks. Even 20 tests covering the money-handling code is transformative.
7. **Reorganize `scripts/` by domain.**
8. **Add a Vite proxy** and switch UI panels from mock to live API data incrementally; add an error boundary.
9. **Generate UI types from server schemas** to kill drift.

### Later (polish & scale)
10. Structured JSON logging + a simple observability dashboard.
11. Centralize all ports/config into one source.
12. Containerize the Python runtime (not just data services) for full reproducibility.
13. Fill `01 Research/` or retire it; document the vault taxonomy in `00 AI OS/Architecture/`.
14. Add code-splitting + a router to the UI.

---

## 8. Knowledge-Layer Notes

- **`00 AI OS/`** is excellent — architecture (38 notes), roadmap (15 notes), governance, agent prompts, workflows, agent outputs, ~70 dated reports. This is the strongest part of the project.
- **Templates** standardize strategy dossiers, committee reviews, theses, memos — strong.
- **Portfolio/Strategy** capture is solid (theses, specialist outputs, dispatches, packets, Monte Carlo, committee reviews).
- **Gap:** `01 Research/` empty; `06 Models/` and `07 Code/` should be checked for freshness.
- **Vault↔runtime loop is real** — scripts write back, Qdrant indexes the vault, memos are generated into notes. This closed loop is a genuine differentiator.

---

## 9. Final Verdict

AI OS is a **credible, well-documented prototype of a hard idea**, built by someone who clearly thinks in systems. The architecture choices (agents-as-data, SQL-first control plane, MCP tool layer, vault-as-truth) are sound and modern. What it lacks is **depth and rigor in the parts that handle money and state**: no tests, no auth, unresolved identity contracts, heavy duplication, and a UI that's still partly a mockup.

The path from B− to A is mostly **discipline work**, not redesign: resolve the contradictions, extract the shared library, add tests around the financial cores, wire the UI to real data, and lock down secrets/auth. None of that requires rethinking the vision — which is the hard part, and it's already done.

---
*Review written to `ai memory/00 AI OS/Reports/AI OS Project Review 20260708.md` per AGENTS.md writeback convention.*

---

# Appendix: Recovery And Runtime Status - 2026-07-08

## Current State

The AI OS source stack is recovered, Git-backed, and pushed to the private recovery repository:

- Repo: `https://github.com/dev2495/ai-investment-os-recovery`
- Branch: `main`
- Latest pushed commit at time of this review: `9aab94e647ac4afa6f5f47a3b44d3f082a726d8b`
- Runtime root: `/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime`
- Internal recovery mirror: `/Users/devarshthakkar/AI_OS_RECOVERY_BACKUP_20260708/Obsidian memory `

The stack is still a local-first research and operating system. It is not yet a live broker-executing hedge fund system.

## Live Runtime Verification

Verified on 2026-07-08:

- Docker runtime root is on the external SSD.
- Docker Desktop disk image is on the external SSD at `/Volumes/Devarsh SSD/Docker/DockerDesktop/Docker.raw`.
- `docker compose ps` showed:
  - `ai_os_postgres`: up and healthy
  - `ai_os_qdrant`: up
  - `ai_os_redis`: up and healthy
- API health passed at `http://127.0.0.1:8765/api/health`.
- UI served at `http://127.0.0.1:5177/`.
- Recovery snapshot refreshed to the internal recovery mirror.

## Strategy Template Library Slice

Implemented and verified:

- `strategy.strategy_templates`
- `strategy.strategy_template_applications`
- `strategy.create_strategy_from_template(...)`
- API route: `POST /api/strategy/templates/apply`
- API snapshot keys:
  - `strategy_template_summary`
  - `strategy_template_library`
  - `strategy_template_applications`
- MCP tools:
  - `ai_os_strategy_template_library`
  - `ai_os_create_strategy_from_template`
- AI Office panel: `Strategy Template Library`
- Obsidian report: [[2026-07-08-strategy-template-library-v1]]

Current live counts:

| Metric | Value |
| --- | ---: |
| active_templates | 10 |
| optimizer_ready_templates | 5 |
| research_only_templates | 5 |
| options_templates | 2 |
| crypto_commodity_templates | 2 |
| template_applications | 1 |

The verified smoke created a real paper-first strategy candidate from `intraday_momentum_5m`. Live execution remained blocked.

## Recovery And Storage Controls

Tracked recovery assets:

- `AI_OS_RECOVERY_MANIFEST_20260708.md`
- `_ai_os_runtime/docs/recovery_and_storage_runbook.md`
- `_ai_os_runtime/scripts/verify_external_storage.sh`
- `_ai_os_runtime/scripts/recovery_snapshot.sh`

Operating rule before major work:

1. Run `_ai_os_runtime/scripts/verify_external_storage.sh`.
2. Run `_ai_os_runtime/scripts/recovery_snapshot.sh`.
3. Commit and push to GitHub.

## Known Gaps

- TradingView CDP is not active: port `9222` refused connection during API health check.
- GitHub intentionally does not contain secrets, raw broker/client statements, Docker volumes, browser cookies/profiles, node modules, build output, or large runtime artifacts.
- The internal recovery snapshot is manual. A scheduled backup job is still needed.
- Full restore test from GitHub plus recovery mirror is still open.
- Options chain/OI/IV/Greeks ingestion is still open.
- Crypto/commodity exchange connector readiness is still open.
- Full visual Strategy DSL builder and strategy portfolio optimizer UI are still open.

## Next Correct Slice

Build the Long-Term Investment Office operating path next:

- thesis checklist tables
- company research packet UI
- moat, management, valuation, downside, and exit-criteria review
- Monte Carlo/position sizing handoff
- Long-Term Committee memo and task routing

This keeps the build aligned with the full hedge-fund OS goal instead of only expanding the quant strategy side.
