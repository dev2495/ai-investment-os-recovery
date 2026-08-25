# iMac AI OS Node Runbook

## Role

The M1 iMac is the nearly-always-on backend, durable storage host, embedding node, schedulers host, and promotion-gated compact conversation fallback. The MacBook is the portable operator workstation and stronger local conversation node.

Power or network downtime is tolerated. Durable queues, PostgreSQL, Qdrant, and scheduled collectors resume when the iMac returns.

## Storage

Canonical external storage:

```text
/Volumes/Devarsh SSD/
  Obsidian memory/
  AI OS Data/
    postgres/
    qdrant/
    ollama/models/
    models/
    caches/
    backups/
    research-inbox/
```

Application code and recoverable service packaging may stay on internal storage. Databases, model artifacts, document corpora, caches, and backups stay on `/Volumes/Devarsh SSD`.

The SSD should remain attached to the iMac. It is not a single copy: scheduled backups and the Git remote protect recoverable state.

## Network

- Tailscale provides private reachability.
- Standard macOS Remote Login provides SSH.
- PostgreSQL, Qdrant, Ollama, and local model endpoints remain loopback or Tailscale scoped.
- Do not expose database, model, or broker endpoints directly to the public internet.

## Install And Upgrade

1. Mount `/Volumes/Devarsh SSD`.
2. Run `deploy/imac-backend/INSTALL_ON_IMAC.command`.
3. Populate the runtime environment from `deploy/imac-backend/imac.env.example`.
4. Run migrations through 179.
5. Start or restart through the installed supervisor.
6. Verify authenticated API workflows, not only HTTP health.
7. Confirm broker execution remains locked.

Useful entry points:

```text
deploy/imac-backend/bin/aios-imac
deploy/imac-backend/bin/supervisor.sh
scripts/install_zerodha_stream_imac.sh
scripts/setup_imac_nanbeige42_assistant.sh
scripts/setup_imac_model_node.sh
```

## Model Services

Only one compact generative model should be resident on the 8 GB iMac at a time.

### Embeddings

- Runtime: Ollama.
- Model: `qwen3-embedding:0.6b`.
- Storage: `/Volumes/Devarsh SSD/AI OS Data/ollama/models`.
- Purpose: Qdrant indexing and retrieval.
- It has no chat, investment, capital, or execution authority.

### Nanbeige Candidate

- Model: `nanbeige/nanbeige4.2:3b-Q4_K_M`.
- Runtime: pinned isolated Nanbeige llama.cpp revision.
- Endpoint: loopback OpenAI-compatible API.
- Storage: `/Volumes/Devarsh SSD/AI OS Data/models/nanbeige42-runtime`.
- Purpose: conversation intake, governed tool selection, business-review drafts, and deck outlines.
- It is assignable only after the exact model and runtime revisions pass `conversation_v1` and the endpoint is healthy.

### Qwen 2B Candidate

- Model: `mlx-community/Qwen3.5-2B-4bit`.
- Purpose: secondary compact private conversation fallback.
- It is subject to the same exact-revision evaluation and endpoint-health gates.

Do not call either candidate active merely because its files exist.

## Promotion Procedure

1. Verify the pinned model and runtime digests.
2. Start the endpoint on loopback.
3. Run the local model evaluation suite.
4. Require `conversation_v1` score at least 0.8 with no hard failures.
5. Record endpoint health.
6. Mark the registry row approved only after review.
7. Call `agent.activate_final_local_model_fleet()`.
8. Confirm the live assignment and fallback route from PostgreSQL.
9. Run a natural Charlie conversation, tool-intake, retrieval, and durable delegation test.
10. Confirm no private prompt enters cloud audit rows.

## Always-On Workloads

The iMac supervisor owns:

- API and frontend.
- PostgreSQL and Qdrant.
- Jarvis mailbox and graph workers.
- Zerodha read-only sync and live stream.
- Canonical OHLCV aggregation.
- News, filings, market calendar, and research-hub indexing.
- Scheduled reports, source freshness, and backups.

TradingView Desktop remains user managed. No managed TradingView browser or CDP runtime is started. The TradingView public quote scanner is off by default.

## Recovery Checks

After restart:

1. SSD is mounted at the exact canonical path.
2. Containers and supervisor are healthy.
3. PostgreSQL and Qdrant volumes resolve to the SSD.
4. Zerodha session status is validated against the broker profile.
5. Live tick heartbeat and canonical OHLCV freshness advance.
6. News, filings, calendar, and research index heartbeats advance.
7. Charlie can converse, retrieve evidence, and queue work.
8. Broker writes and live execution remain disabled.

## Operational Boundaries

- Local models may handle private conversation but cannot calculate or approve investments.
- Cloud routes never receive client-private data.
- Live trading is human gated.
- A stopped or degraded feed must be shown as degraded; stale data must not be presented as live.
- Runtime health in PostgreSQL is authoritative over static configuration files.
