# iMac M1 8GB Local Model Node

## Role

The iMac is the nearly-always-on deterministic worker. It owns public ingestion,
scheduling, alerts, rule-based classification, and public research retrieval. It does not become the
authoritative writer for client portfolios, private journals, orders, or approvals.

## Storage

Use a separate external SSD named `AI OS iMac`. The Devarsh SSD cannot be attached to
the MacBook and iMac simultaneously, and SQLite/Qdrant files must not be network-mounted
between writers.

Expected model path:

`/Volumes/AI OS iMac/ollama/models`

The iMac keeps disposable public indexes and an encrypted read-only private snapshot.
The MacBook plus Devarsh SSD remain authoritative for client-private data.

## Installation

1. Install current Ollama on the iMac.
2. Copy or clone the AI OS repository to the iMac.
3. Attach the dedicated SSD and confirm it is mounted as `AI OS iMac`.
4. Run:

```bash
cd /path/to/ai-investment-os
bash _ai_os_runtime/scripts/setup_imac_model_node.sh
```

5. Start Ollama with these fixed bounds:

```bash
AI_OS_OLLAMA_MODELS="/Volumes/AI OS iMac/ollama/models" \
OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=5m \
bash _ai_os_runtime/scripts/start_ollama_foreground.sh
```

6. Apply database migrations `143_local_model_fleet_truth_evals_v1.sql` and
`148_deterministic_always_on_route.sql` to the iMac's
public-worker database, then run:

```bash
python3 _ai_os_runtime/scripts/run_local_model_evals.py \
  --model qwen3-embedding:0.6b --persist --promote
```

## Operating Limits

- No generative model is approved on the 8GB iMac; weak small-model output must not enter the evidence ledger.
- One embedding request at a time.
- Default context 8K; do not expose the advertised 256K context on an 8GB machine.
- Do not install Qwen3.5 9B, Gemma 4, Bonsai 27B, Docker Desktop, or rented-GPU clients on this node.
- Unload models after idle periods; run embedding batches outside chat bursts.
- Bind services to loopback. Add Tailscale later; never expose Ollama directly to the public internet.
- Queue writes while the MacBook is offline and label dashboard snapshots with their as-of time.
- Use a UPS for the iMac, router, and SSD. A cloud relay may carry heartbeat and public alerts only.

## Acceptance Checks

The node is usable only when the exact embedding model is installed, retrieval_v1 passes with
zero hard failures, no client-private data is present, the SSD guard passes, and restart
testing proves the queue resumes without duplicate work.
