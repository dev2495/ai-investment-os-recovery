# Research Paper Operator And Daemon Hardening v1

Date: 2026-07-15
Status: Live and verified

## Outcome

The Research terminal now provides governed research-paper registration/extraction and source-linked strategy-hypothesis creation. A paper can enter through a public source URL, permitted PDF URL, or local document path. The system retains source, hash, parser, artifact, and review-task evidence. Hypotheses remain research-only and cannot skip data-leakage review, backtest approval, risk review, paper monitoring, or execution locks.

Live state contains two registered papers, one extracted 44-page arXiv paper, one metadata-only paper awaiting a permitted PDF, one source-linked strategy hypothesis, and 91 indexed AI outputs: 55 research outputs, 25 dashboards, and 11 financial models from bounded Codex/Claude/Cowork roots.

## Runtime Repair

Repeated Docker CLI attach hangs were isolated from PostgreSQL itself. Direct localhost `psql` showed no server blocker, while orphaned `docker exec -i ... psql` clients prevented the 24/7 daemon from completing its first pass. The production wrapper now reads only PostgreSQL keys from the local 0600 runtime env without evaluating the file as shell code.

The worker, market-news, OHLCV aggregation, event-quote, source-freshness, strategy DSL, strategy/backtest, and TradingView CDP persistence paths use direct local PostgreSQL when credentials are available, with three-second connection, five-second lock, 30-second statement, and 35-second subprocess bounds. Docker remains a fallback for manual environments without credentials.

## Verification

- TypeScript/Vite production build passed.
- Six hardened Python workloads compiled; the LaunchAgent wrapper passed `bash -n`.
- Research paper and hypothesis controls passed desktop/mobile terminal tests with no production fixture creation.
- Complete office regression passed 84/84, including 39 WCAG A/AA checks and WebGL office rendering.
- The live daemon reached `running` and `healthy` with a fresh heartbeat, no last error, TradingView status `ok`, and no Docker psql child.
- API, database, UI, Ollama, and TradingView CDP remained available; broker execution remained locked.

## Open Gates

Automated paper discovery by source policy, OCR for image-only documents, table/figure extraction, collection-level Qdrant sensitivity ACLs, methodology-quality scoring, duplicate/version clustering, citation graphs, and approved hypothesis-to-backtest promotion remain open.
