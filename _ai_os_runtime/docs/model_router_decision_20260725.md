# Model Router Decision - 2026-07-25

## Decision

The AI Investment OS owns routing, privacy, evaluation, cost caps, and audit
records. Pioneer is not inserted as a second control plane. OpenRouter is only
the provider gateway for explicit public/internal cloud work.

## Route Matrix

| Work class | Primary route | Fallback or escalation | Guardrail |
|---|---|---|---|
| Private conversation and tool intake | Evaluated MacBook Bonsai route | Pinned iMac Nanbeige route after `conversation_v1` promotion | Client data stays local; exact model digest must pass `conversation_v1` |
| Deterministic office work | SQL/Python/tool worker | None | Calculations and writes use typed tools, not model prose |
| Volume public/internal work | `openrouter/openai/gpt-5.6-luna` | Direct `openai/gpt-5.6-luna` when configured | Explicit selection or policy escalation, no client data, ZDR, cost preflight |
| Long public/internal synthesis | `minimax/minimax-m3` | `z-ai/glm-5.2` | Explicit selection, no client data, cost preflight |
| Independent public/internal review | `z-ai/glm-5.2` | None | Explicit selection; no execution authority |

The office-wide cloud budget is INR 3,000/month soft, INR 4,500/month hard,
and INR 150/day hard, with 20% reserved for genuinely difficult work. Per-agent
caps are subordinate to these global gates. Cloud calls are blocked when the
API key, current rate, required approval, privacy policy, or remaining budget
is missing.

## Local Model Placement

- The M1 iMac with 8 GB RAM runs one light model at a time. Qwen3.5 4B Q4 is
  about 3.4 GB, but a catalog fit is not a production promotion: this project
  previously rejected its tested digest at `light_v1` score 0.50. It remains an
  evaluation candidate until a new exact digest passes the current suite.
- The pinned iMac Nanbeige4.2 3B Q4 runtime is the private fallback candidate.
  It is activated only after its exact digest passes `conversation_v1`.
- Bonsai is the evaluated MacBook private-conversation default while its pinned
  runtime is reachable. It handles natural dialogue and delegation, but it is
  not a research authority, calculation engine, or investment decision maker.
- Laguna S 2.1 is a 118B/8B-active coding model. Its published weight size and
  runtime requirements do not fit either workstation, and its task profile is
  not the default investment-office conversation workload.

## External Router Decision

Pioneer is deferred. It can optimize model selection, but the OS already has
task routes, privacy classes, provider readiness, exact-model evaluations,
usage records, and hard cost stops. Adding Pioneer now would duplicate policy
and add another paid dependency. Revisit only after measured OpenRouter spend
or quality data shows the in-house router is materially underperforming.

## Reference Repository Decision

The updated `virattt/ai-hedge-fund` is used as a reference contract, not as the
production runtime. Its useful boundary is preserved in this stack: alpha
models emit point-in-time directional views; portfolio construction sizes;
hard risk clamps; execution remains separate; every cycle writes a ledger.
The external project describes itself as an educational proof of concept and
does not perform real trades, so its personas and orchestration are not a
substitute for this system's data lineage, broker controls, or approval gates.

## Sources

- https://ollama.com/library/qwen3.5/tags
- https://huggingface.co/Qwen/Qwen3.5-4B
- https://poolside.ai/blog/introducing-laguna-s-2-1
- https://huggingface.co/poolside/Laguna-S-2.1
- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/api/v1/models
- https://pioneer.ai/model-router
- https://github.com/virattt/ai-hedge-fund
