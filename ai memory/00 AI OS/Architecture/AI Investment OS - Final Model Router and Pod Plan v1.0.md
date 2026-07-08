# AI Investment OS - Final Model Router and Pod Plan v1.0

Date: 2026-07-07
Owner: Devarsh
Status: planning document only; no runtime/router changes made
Budget target: local-first, JarvisLabs pod burst cap around INR 5,000/month, frontier/cloud only on approved escalation
Related blueprint: [[AI Investment OS - Institutional Master Blueprint v8.0]]

## 1. Final Decision

Use a three-layer intelligence stack:

1. Local always-on intelligence
   - M1 iMac runs Jarvis-lite all day.
   - MacBook runs stronger local Charlie sessions when Devarsh is working.
   - This keeps cost near zero and keeps the office alive.

2. Burst open-model pods
   - JarvisLabs pods run stronger 32B/70B open models only for serious jobs.
   - Pods must be job-based: start, load model, process queue, write result, shut down.
   - Hard monthly target: around INR 5,000.

3. Premium cloud/frontier escalation
   - GLM-5.2 for long-context, deep code, deep research, and committee synthesis.
   - Frontier models such as Claude/OpenAI/Fable-class models only for highest-stakes review and final judgement.
   - Every cloud call must log cost, agent, task, reason, and privacy class.

This is the correct balance: the system feels alive every day, can perform serious hedge-fund research and quant work on demand, and does not burn GPU money while idle.

## 2. Runtime Roles

### 2.1 M1 iMac - Always-On Control Tower

Role:

- Jarvis-lite runtime assistant.
- Background monitors.
- Queue manager.
- Dashboard refresh worker.
- News/filing/source freshness triage.
- Agent inbox triage.
- Lightweight Obsidian/Qdrant retrieval.

Allowed tasks:

- classify incoming source,
- summarize short artifact,
- route task to department,
- prepare dashboard widget text,
- draft daily brief bullets,
- detect stale data,
- create agent tasks,
- check reminders,
- run deterministic scripts,
- queue pod/cloud jobs.

Not allowed:

- final investment conclusion,
- trade approval,
- live order action,
- high-stakes client report without review,
- autonomous broker mutation.

### 2.2 MacBook - Interactive Workbench

Role:

- Charlie normal daily chat.
- Devarsh's interactive research and coding station.
- Prompt engineering and workflow design.
- Review of pod/cloud outputs.

Allowed tasks:

- normal portfolio Q&A,
- medium research memos,
- strategy idea shaping,
- code drafts,
- agent prompt edits,
- dashboard/product planning,
- committee pre-reads.

### 2.3 JarvisLabs Pods - Burst Open-Model Workers

Role:

- Run higher-end local/open models when local machines are too small.
- Process queued high-value jobs.
- Keep sensitive jobs off general cloud APIs when needed.

Allowed tasks:

- deep company research,
- long trade journal mining,
- strategy generation,
- strategy critique,
- code generation,
- factor/regime commentary,
- risk/bear-case review,
- committee memo drafts,
- large batch extraction,
- model/prompt evaluations.

### 2.4 Premium Cloud And Frontier

Role:

- Last-mile reasoning.
- Large-context review.
- High-stakes committee critique.
- Complex architecture/coding review.

Allowed tasks:

- final investment committee synthesis,
- final risk challenge,
- critical code/architecture review,
- huge annual report/concall bundle,
- hard legal/compliance-style summarization,
- high-value client-ready report review.

## 3. Model Router Levels

| Level | Route | Cost | Purpose |
| --- | --- | ---: | --- |
| L0 | Deterministic tools | Near zero | SQL, Python, backtests, reconciliations, risk math, portfolio math |
| L1 | M1 local tiny | Near zero | Always-on routing, classification, inbox, short summaries |
| L2 | M1/MacBook local small-medium | Near zero | Normal assistant work, research, prompt drafting |
| L3 | MacBook local strong | Near zero | Charlie normal reasoning, local coding help, medium memos |
| L4 | JarvisLabs 24GB pod | Low | Batch extraction, coding helper, small/medium open models |
| L5 | JarvisLabs A100 40GB | Medium | Main 32B reasoning/coding/research worker |
| L6 | JarvisLabs A100 80GB / RTX Pro 6000 | Medium-high | 70B review, committee drafts, deep open-model jobs |
| L7 | GLM-5.2 / frontier APIs | Controlled high | Extreme context, final synthesis, highest-value work |

Default rule:

1. Try deterministic tools first.
2. Use local model if task is low/medium value.
3. Use pod 32B if task is deep but not final.
4. Use pod 70B if task needs broad judgement and privacy.
5. Use GLM-5.2/frontier only when context, difficulty, or importance justifies cost.

## 4. Local Model Plan

### 4.1 M1 iMac Always-On Models

Primary choices:

1. Qwen3 4B
   - Best default for Jarvis-lite if stable on the M1.
   - Good for routing, extraction, short reasoning, and structured output.
   - Use for always-on office tasks.

2. Qwen3 8B
   - Use if M1 RAM/latency is acceptable.
   - Better quality than 4B for agent routing and summaries.
   - May be too heavy for constant background use on a smaller M1.

3. Llama 3.2 3B
   - Fast fallback for simple assistant tasks.
   - Good when latency and low memory matter more than reasoning depth.

Recommended default:

- Start with Qwen3 4B for Jarvis-lite.
- Keep Llama 3.2 3B as fallback.
- Try Qwen3 8B only if the M1 remains responsive.

### 4.2 MacBook Local Models

Primary choices:

1. Qwen3 14B
   - Main Charlie local model for daily reasoning.
   - Good balance of quality and local cost.
   - Prefer MLX quantized version on Apple Silicon.

2. Gemma 3 12B
   - Strong alternate for writing, research summaries, and instruction following.
   - Good diversity against Qwen-family outputs.

3. Qwen coder model, 7B-14B class
   - Use for local code drafts, scripts, and prompt/code tooling.
   - Escalate larger coding tasks to pod Qwen coder 30B/32B.

Recommended default:

- Charlie local: Qwen3 14B MLX 4-bit if the MacBook handles it.
- Research alternate: Gemma 3 12B.
- Coding local: Qwen coder 7B-14B class.

### 4.3 Embeddings And Retrieval

Primary choices:

1. BGE-M3
   - Best default for multilingual, long document, hybrid retrieval use.
   - Good fit for Indian filings, reports, Obsidian notes, and mixed-language sources.

2. Nomic Embed Text
   - Simpler fallback.
   - Good local embedding choice for a low-friction Ollama setup.

3. Jina/Qwen embedding family
   - Keep as evaluation candidates when we benchmark retrieval quality.

Recommended default:

- Use BGE-M3 if stable in the local stack.
- Use Nomic Embed Text if we prioritize simplicity and reliability.

## 5. JarvisLabs Pod Model Plan

JarvisLabs published on-demand prices used for this plan:

- A30 24GB: INR 38.88/hour
- L4 24GB: INR 41.31/hour
- A100 40GB: INR 84.24/hour
- A100 80GB: INR 140.94/hour
- RTX Pro 6000 Blackwell 96GB: INR 179.01/hour
- H100 80GB: INR 255.15/hour
- H200 141GB: INR 360.45/hour

### 5.1 Cheap Pod - A30/L4 24GB

Use for cheap batch jobs and smaller model serving.

Best model options:

1. Qwen3-Coder-30B-A3B-Instruct, quantized, reduced context
   - Best candidate for coding/agentic tool work on a cheap pod because it is MoE-style with low active parameters.
   - Use for code generation, API tooling, report scripts, and prompt engineering.
   - Risk: total weights are still large; start with 4-bit and reduced context.

2. Qwen3 14B / Gemma 3 12B
   - Stable cheap-pod fallback for research and assistant batches.
   - Use when reliability is more important than squeezing a 30B MoE onto 24GB.

3. Gemma 3 27B IT, quantized
   - Candidate for document/report/image-adjacent work.
   - Risk: may need A100 for comfortable context and throughput.

Use cases:

- bulk source classification,
- batch summarization,
- code-helper jobs,
- report cleanup,
- strategy spec normalization,
- prompt testing,
- embedding/reranking experiments.

### 5.2 Main Pod - A100 40GB

This is the best value heavy-worker tier.

Best model options:

1. Qwen3 32B
   - Primary open-model heavy worker.
   - Use for general reasoning, research synthesis, agent planning, strategy explanation, and non-final committee drafts.
   - Strong default for the hedge-fund OS.

2. DeepSeek-R1-Distill-Qwen-32B
   - Use for deliberate reasoning, quantitative explanation, math-heavy thinking, strategy critique, and model-risk style reviews.
   - Do not use for every task because it may be slower and more verbose.

3. Qwen2.5-Coder-32B-Instruct or Qwen3-Coder-30B-A3B-Instruct
   - Use for coding, refactors, backtest code, data pipelines, MCP tools, and prompt/tool schemas.
   - Prefer coder model for engineering tasks instead of asking the general research model.

Recommended A100 40GB model set:

- General reasoning: Qwen3 32B
- Quant/reasoning critic: DeepSeek-R1-Distill-Qwen-32B
- Engineering: Qwen coder 30B/32B

### 5.3 Deep Review Pod - A100 80GB / RTX Pro 6000 96GB

Use only for higher-value deep review.

Best model options:

1. Llama 3.3 70B Instruct
   - Broad, stable committee-style generalist.
   - Use for second-opinion reviews, risk challenge, agent output critique, and memo review.

2. Qwen3-Next-80B-A3B-Instruct, quantized/reduced context
   - Strong candidate for long-context agentic reasoning if deployment is stable.
   - Official deployment notes for full context recommend much more GPU than a casual single pod, so treat this as an experiment first.

3. Gemma 3 27B IT
   - Use when multimodal/report/image-adjacent understanding matters more than raw parameter count.
   - More practical than huge MoE models for some document and visual-analysis tasks.

Recommended A100 80GB / RTX Pro 6000 use:

- Llama 3.3 70B for committee review.
- Qwen3-Next 80B-A3B only after deployment test.
- Gemma 3 27B IT for visual/report-style analysis.

### 5.4 Extreme Pod - H100/H200

Use only with explicit approval.

Best model options:

1. Qwen3-Next-80B-A3B-Instruct
   - Long-context research/agentic reasoning candidate.

2. Qwen3-Coder-Next / high-end Qwen coder family
   - Deep coding and agentic software engineering.

3. Llama 3.3 70B high-context / high-throughput serving
   - Committee review at higher speed and context.

Use cases:

- one-off monthly deep research day,
- large-scale trade journal mining,
- high-value strategy generation sprint,
- full committee review batch,
- model evaluation benchmark run,
- private sensitive large-document work.

## 6. INR 5,000 Monthly Pod Budget

Recommended monthly allocation:

| Resource | Hours/month | Rate/hour | Approx cost |
| --- | ---: | ---: | ---: |
| A100 40GB | 35h | INR 84.24 | INR 2,948 |
| A100 80GB | 10h | INR 140.94 | INR 1,409 |
| A30 24GB | 15h | INR 38.88 | INR 583 |
| Total | 60h | - | INR 4,940 |

Operating rule:

- A100 40GB is the default deep worker.
- A100 80GB is only for 70B/deep review.
- A30/L4 is for cheap batches and experiments.
- Leave a small buffer for failed launches/storage/network/rounding.

Monthly practical capacity:

- 20-30 serious research/strategy jobs on A100 40GB.
- 5-8 deep 70B committee review jobs on A100 80GB.
- 10-20 cheap batch/helper jobs on A30/L4.

Hard kill rules:

- No pod left idle.
- Every pod job has a max runtime.
- Every pod job has a cost estimate before launch.
- Every pod job writes an output artifact.
- Every pod job logs model, GPU, tokens, runtime, cost, and result path.
- Pods are for queued jobs, not casual always-open chat.

## 7. Cloud And Frontier Plan

### 7.1 GLM Family

Use GLM as the main open-cloud escalation family.

Recommended usage:

1. Cheap GLM route
   - Use GLM-4.5-Air / GLM-4.7-FlashX style models for medium tasks when local/pod is unavailable or too slow.
   - Use for summaries, extraction, cheap code review, source triage, and general assistant escalation.

2. GLM-5.2
   - Use for deep code, deep research, long-context filings, and committee synthesis.
   - Useful because official docs position it as a strong coding model with up to 1M context.

Do not self-host GLM-5.2 by default. Use API unless a specific privacy or research reason justifies a large GPU experiment.

### 7.2 Frontier Models

Use Claude/OpenAI/Fable-class models only for extreme value tasks:

- final investment committee review,
- final risk challenge,
- large research synthesis,
- major codebase architecture review,
- client-ready report final critique,
- prompt/router eval calibration.

Rule:

- Frontier output is a reviewer or challenger, not an unchecked decision maker.
- Charlie still presents final answer with evidence and missing-data notes.
- Devarsh remains final human decision maker.

## 8. Agent-To-Model Assignment

### Executive Office

Charlie Munger:

- Default: MacBook Qwen3 14B local.
- Deep: pod Qwen3 32B.
- Review: pod Llama 3.3 70B.
- Extreme: GLM-5.2 or frontier.

Jarvis:

- Default: M1 Qwen3 4B or Llama 3.2 3B.
- Strong local: MacBook Qwen3 14B.
- Pod: only for queued batch orchestration or large planning jobs.

### Long-Term Office

Company Analyst:

- Default: local Qwen3 14B / Gemma 3 12B.
- Deep annual report: GLM-5.2 or pod Qwen3 32B.

Financial Statement Analyst:

- Deterministic calculations first.
- Deep commentary: DeepSeek-R1-Distill-Qwen-32B or GLM-5.2.

Valuation Agent:

- Deterministic valuation code first.
- Narrative and scenario review: Qwen3 32B / GLM-5.2.

Bear Case Agent:

- Pod Llama 3.3 70B or GLM-5.2 for important decisions.

### Quant Lab

Strategy Generator:

- Default: pod Qwen3 32B.
- Coding strategy: Qwen coder 30B/32B.
- Extreme idea sprint: GLM-5.2/frontier.

Data Scientist:

- Deterministic Python first.
- Reasoning review: DeepSeek-R1-Distill-Qwen-32B.

Feature Engineer:

- Qwen coder 30B/32B.

Model Validation Agent:

- DeepSeek-R1-Distill-Qwen-32B for quant critique.
- Frontier only for high-value strategy approval review.

### Research Factory

Filings Analyst:

- Local for extraction triage.
- GLM-5.2 for long filings.

News Analyst:

- Local Qwen3 4B/8B for triage.
- Qwen3 32B for thematic synthesis.

Special Situations Analyst:

- Qwen3 32B for memos.
- Llama 3.3 70B / GLM-5.2 for committee review.

### Trading Desk

Technical Analyst:

- Local models for chart notes and TradingView action summaries.
- No live execution authority.

Options Analyst:

- Deterministic options math first.
- Qwen3 32B / DeepSeek-R1-Distill-Qwen-32B for commentary.

Trade Journal Coach:

- Local model for daily notes.
- Pod 32B for mining old journals and extracting recurring patterns.

### Risk Office

Chief Risk Officer:

- Deterministic risk engine first.
- Pod Llama 3.3 70B / GLM-5.2 for high-stakes risk narrative.

Data Quality Risk Agent:

- Local for routine checks.
- Pod only for large incident analysis.

Model Risk Agent:

- DeepSeek-R1-Distill-Qwen-32B and frontier reviewer for serious strategy approvals.

## 9. Prompt Engineering Stack

Every agent prompt should be layered:

1. System constitution
   - human control,
   - no fake data,
   - no autonomous live orders,
   - evidence-first,
   - source freshness required.

2. Role/personality
   - agent role,
   - decision rights,
   - tone,
   - scope limits.

3. Task template
   - exact workflow,
   - required inputs,
   - required checks,
   - completion criteria.

4. Context pack
   - SQL facts,
   - retrieved Obsidian notes,
   - source snippets,
   - prior committee decisions,
   - relevant dashboard state.

5. Tool contract
   - allowed tools,
   - forbidden actions,
   - write permissions,
   - approval gates.

6. Output schema
   - conclusion,
   - evidence,
   - source freshness,
   - assumptions,
   - risks,
   - missing data,
   - action recommendation,
   - confidence,
   - next tasks.

7. Critic pass
   - bear case,
   - risk challenge,
   - data-quality check,
   - cost/privacy check.

## 10. Router Decision Rules

Use local when:

- the task is short,
- source data is already structured,
- answer does not need deep judgement,
- privacy is high,
- latency matters,
- cost should be zero.

Use A30/L4 pod when:

- batch task is too slow for local,
- model can fit in 24GB,
- task is not worth A100,
- code/helper task can use a smaller/quantized model.

Use A100 40GB when:

- strategy generation needs serious reasoning,
- company research needs deeper synthesis,
- code generation needs a 30B/32B model,
- trade journal mining is large,
- model validation needs stronger reasoning.

Use A100 80GB / RTX Pro 6000 when:

- 70B second opinion is needed,
- committee memo needs broad critique,
- risk review is high value,
- privacy rules make API escalation undesirable.

Use GLM-5.2/frontier when:

- context is too large for pod,
- reasoning is high stakes,
- final committee synthesis is needed,
- complex code architecture needs top-tier review,
- output will influence capital allocation.

## 11. Evaluation Before Wiring

Before making any model the default, run this eval pack:

1. Jarvis routing eval
   - classify 50 mixed tasks into departments/tools.
   - pass if routing accuracy is above 90%.

2. Structured output eval
   - produce JSON for 30 workflow tasks.
   - pass if valid JSON and required fields above 95%.

3. Company research eval
   - summarize one annual report, one filing, one concall transcript.
   - pass if source citations and missing-data handling are correct.

4. Strategy generation eval
   - turn five natural-language strategy ideas into deterministic strategy DSL candidates.
   - pass if no fabricated data and all assumptions are explicit.

5. Quant reasoning eval
   - critique backtest metrics, overfit risk, regime weakness, and capacity risk.
   - pass if it identifies known planted problems.

6. Coding eval
   - build/fix one API route, one SQL migration, one MCP tool, and one dashboard panel.
   - pass if code runs and style matches stack.

7. Risk critique eval
   - review a multi-book opposing exposure case like Reliance long-term long and quant/active short.
   - pass if it separates book intent, net/gross exposure, hedge intent, and risk question.

8. Cost/latency eval
   - log tokens, runtime, GPU hours, estimated INR cost, and quality score.

## 12. Implementation Plan When Approved

No implementation changes are made by this document. When approved, build in this order:

1. Add model registry rows for local, pod, GLM, and frontier routes.
2. Add provider cost table for JarvisLabs GPU-hours and API token costs.
3. Add model-router policy table.
4. Add per-agent default route and escalation route.
5. Add pod job queue table.
6. Add pod cost guardrails.
7. Add prompt template registry.
8. Add model eval harness.
9. Add dashboard panel for model usage, pod jobs, and monthly budget.
10. Run eval pack and choose actual defaults.

## 13. Final Recommended Default Set

Use these as the first production candidates:

| Layer | Primary | Backup | Purpose |
| --- | --- | --- | --- |
| M1 always-on | Qwen3 4B | Llama 3.2 3B | Jarvis-lite, routing, triage |
| MacBook daily | Qwen3 14B | Gemma 3 12B | Charlie local, research, prompts |
| Embeddings | BGE-M3 | Nomic Embed Text | Obsidian/source retrieval |
| A30/L4 pod | Qwen3-Coder-30B-A3B quantized | Qwen3 14B | cheap batch/coding helper |
| A100 40GB pod | Qwen3 32B | DeepSeek-R1-Distill-Qwen-32B | main open heavy worker |
| A100 40GB coding | Qwen coder 30B/32B | Qwen3 32B | code, MCP, scripts, dashboards |
| A100 80GB/RTX 6000 | Llama 3.3 70B | Qwen3-Next-80B-A3B test | committee review |
| Premium API | GLM-5.2 | cheap GLM route | long-context/deep research |
| Extreme frontier | Claude/OpenAI/Fable-class | GLM-5.2 | final challenge/review |

## 14. Source Links Checked

- JarvisLabs pricing: https://jarvislabs.ai/pricing
- Z.ai pricing: https://docs.z.ai/guides/overview/pricing
- Z.ai GLM quick start: https://docs.z.ai/guides/overview/quick-start
- Qwen3 32B model card: https://huggingface.co/Qwen/Qwen3-32B
- Qwen3-Coder-30B-A3B-Instruct model card: https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct
- Qwen3-Next-80B-A3B-Instruct model card: https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct
- Qwen2.5-Coder-32B-Instruct model card: https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct
- DeepSeek-R1-Distill-Qwen-32B model card: https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
- Llama 3.3 70B Instruct model card: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct
- Gemma 3 27B IT model card: https://huggingface.co/google/gemma-3-27b-it
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Nomic Embed Text model card: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
