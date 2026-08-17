# Model Router Decision

Status: current architecture, superseding the 25 July route matrix
Contract sources: `config/model_routes.yml`, migrations 176-179, and live PostgreSQL runtime views

## Decision

Charlie is a natural conversational orchestrator, but language models do not own calculations, market state, portfolio state, backtests, risk limits, approvals, or execution. Those remain deterministic tool and database responsibilities.

The operator-facing routes are:

| UI mode | Route | Intended use | Privacy |
|---|---|---|---|
| Private | `charlie_munger_orchestration` | Natural conversation, task intake, delegation, evidence-bound summaries | Client/private context allowed locally |
| Fast | `openrouter_luna_volume` | High-volume public/internal drafting and routine synthesis | No client data |
| Research | `openrouter_gemini36_research` | Explicit multimodal public/internal research | No client data |
| Deep | `openrouter_terra_research` | Explicit deep research and synthesis | No client data |
| Review | `openrouter_sol_review` | Rare independent committee or architecture review | No client data |

Deterministic pipelines are not chat modes. They own filings extraction, document OCR, numerical analytics, backtests, portfolio calculations, risk, capital allocation, approval state, and broker safety.

## Local Fleet

1. MacBook primary: `mlx-community/Qwen3.5-9B-4bit`.
   - Qualified only for `conversation_v1`, task intake, tool selection, and evidence-bound summaries.
   - It is not a research-calculation or investment-authority model.
2. iMac fallback 1: `nanbeige/nanbeige4.2:3b-Q4_K_M`.
   - Preferred always-on fallback only after exact-revision `conversation_v1` promotion and endpoint health.
   - Suitable for conversation intake, business-review drafts, and deck outlines.
3. iMac fallback 2: `mlx-community/Qwen3.5-2B-4bit`.
   - Secondary always-on fallback under the same promotion and health gates.
4. MacBook rollback: `prism-ml/Bonsai-27B-Q1_0`.
   - Used only when the qualified Qwen primary is unavailable and Bonsai remains evaluated.
5. Embeddings: `qwen3-embedding:0.6b` through the iMac Ollama node.

Migration 179 enforces fallback precedence: Nanbeige, Qwen 2B, then Bonsai when Qwen 9B is the active primary. If no qualified private model is healthy, Charlie fails closed to the deterministic router.

## Cloud Ladder

- Luna is the capped routine volume route.
- Gemini 3.6 Flash is explicit multimodal research.
- Terra is explicit deep research.
- Sol is explicit independent review.
- Cloud requests must pass privacy and budget gates.
- Client-private content cannot be sent to cloud routes.
- Availability is determined by live database route/endpoint health, not YAML alone.

## Budget

- Monthly soft cap: INR 3,000.
- Monthly hard cap: INR 4,500.
- Daily hard cap: INR 150.
- Heavy-route reserve: 20%.
- Hard stop on breach: enabled.
- Autonomous heavy/frontier selection: disabled.

## Safety

- Broker writes remain disabled.
- TradingView Desktop is a user-managed chart workspace, not authoritative market data or an execution surface.
- Zerodha read-only data and the canonical warehouse own portfolio and market state.
- Devarsh retains final investment, approval, and execution authority.
