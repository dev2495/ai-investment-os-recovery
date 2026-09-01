# Research Desk v1 — Operator Runbook

## Hard safety boundaries

1. `Devarsh SSD` must be mounted and writable before private artifacts, reports or PDF extraction run.
2. Zerodha remains the canonical private quote/instrument/account/options provider. Do not create a second price pipeline.
3. Preserve daily user authentication, macOS Keychain, LaunchAgent supervision and reconnect behavior.
4. Keep `broker_write_allowed=false`, `external_write_allowed=false` and `private_data_egress_allowed=false` for Research Desk.
5. Do not paste broker or model credentials into chat or commit them to Git.
6. A stale/unavailable quote blocks price-dependent valuation unless an explicitly labelled approved fallback is current.
7. No Research Desk, scanner, Charlie or coding-agent action may place a live order.

## Start a new company Research Case

1. In Charlie or Research Workstreams, enter a company name, exchange ticker, ISIN or a natural sentence such as “Research Shivalik Bimetal using latest filings and news.”
2. Inspect the resolved company, mandate, horizon, evidence plan, public/private boundary, estimated cost and hard ceiling.
3. Explicitly approve the cost plan and start.
4. Open the durable case. The normal progression is Sources → Extraction → Analysis → Synthesis → Independent review → Pack & decision.
5. Follow stage progress, agent/task IDs, costs, source freshness, blockers and the exact repair action in the case UI.
6. Open the completed pack from either Research Workstreams or the matching Company Thesis Dashboard.

An older blocked case does not prevent a distinct new mandate. Use View, Repair or New mandate. Repairs are bounded and preserve prior evidence.

## Source extraction and Shivalik-style PDF repair

The source worker uses only the governed interpreter:

```text
/Volumes/Devarsh SSD/AI OS Data/runtime/pdf-extraction/bin/python
```

Before replaying a failed source job on the live host:

1. Verify the SSD is mounted.
2. Verify the governed interpreter exists, is executable and can import `pypdf`.
3. Confirm the source job references a cached/authorized official filing.
4. Use the case Repair action. It retries the exact failed source stage with bounded cooldown.
5. Confirm the blocker resolves and the extraction event records parser, artifact and source identifiers.

There is deliberately no internal-disk Python fallback.

## Report delivery repair

Use **Repair report delivery** only for `report_pdf_render` or `research_pack_generation` blockers.

The repair contract:

1. Requires explicit operator confirmation.
2. Verifies that stored HTML/PDF paths are non-empty files under the mounted Devarsh SSD.
3. Resolves the blocker immediately when the PDF is already present.
4. Retries PDF rendering from the existing HTML when possible.
5. Rebuilds only the report delivery artifact when HTML is absent.
6. Creates no model preflight, model run or source job and permits no external/broker/capital action.

If a file is missing, the View/Download action must return an actionable error rather than a dead link.

## Zerodha quote health

The valuation UI must show provider, exchange, symbol/instrument mapping, quote timestamp, quote age, stream heartbeat age, freshness, delay status and fallback status.

During an NSE/BSE live session, the primary quote is unusable when:

- the canonical Zerodha stream is not connected;
- stream health is not live/connected;
- the heartbeat is missing or older than 90 seconds;
- the quote exceeds its approved freshness threshold;
- mapping/valuation approval is missing; or
- the broker-write lock is not false.

Reconnect only through the existing user-managed Zerodha login flow. Non-price research can continue while valuation stays blocked.

## GLM 5.3 Flash daily-driver promotion

GLM 5.3 Flash starts disabled for normal Research Cases. Use Models & Routes and complete four separate gates:

1. **Prepare cost plan** — calculate estimate/hard ceiling; no model call.
2. **Approve and configure** — explicit spend approval and fixed public packet; no model call.
3. **Run public canary** — explicitly confirm the paid canary; ZDR and data-collection denial are enforced.
4. **Review and promote** — inspect the exact response and citations, then provide:
   - named reviewer;
   - rationale of at least 20 characters;
   - exact 64-character response hash;
   - citations checked;
   - citation accuracy at least 90;
   - numeric accuracy at least 95;
   - zero unsupported claims;
   - explicit daily-driver approval.

Promotion invokes no model. It repoints only the public specialist daily-driver route. DeepSeek V4 Pro remains lead/review escalation, and every later paid run still requires its own preflight.

## Fundamental scanners

1. Copy an executable global template into the operator workspace.
2. Inspect the deterministic DSL, metric directions, completeness requirement and point-in-time universe.
3. Run validation/dry-run.
4. Request publication approval; repeated requests reuse the durable pending/approved record.
5. A human approves publication.
6. Explicitly confirm each durable run.

Templates never publish, schedule, alert, create research or trade merely by being installed. Unsupported older frameworks remain reference-only.

## Live release gate

Apply migrations in order:

```text
250_executable_fundamental_scanner_templates_v1.sql
251_glm53_flash_research_canary_v1.sql
252_zerodha_research_quote_health_v1.sql
```

Before promoting a release:

1. Record source checkout HEAD, dirty state and protected Zerodha hashes.
2. Capture/verify the current Postgres, Qdrant, Obsidian and Git recovery points.
3. Replay migrations in a disposable database and compare schema/object counts.
4. Run the Python suite, `npm ci`, production build, dependency audits and Chrome tests.
5. Deploy to the canonical iMac release only after confirming its actual source/release mapping.
6. Verify API/UI health, daemon/worker heartbeats, SSD paths, Zerodha stream state and broker-write lock.
7. Hard-refresh authenticated Chrome and Safari; exercise Wipro and Shivalik intake, progress, repair, completed report and valuation freshness.
8. Compare deployed asset hashes with the tested commit.

If the host, SSD, database, auth or recovery evidence is unavailable, stop before migration/deploy and report the exact gate.

## Fresh-machine verification

From the pushed branch on another machine:

```text
git fetch origin
git checkout codex/research-desk-knowledge-scanners-v1
cd _ai_os_runtime/ai-office-ui
npm ci
npm audit
npm run build
```

Backend tests must use the repository's governed test environment. Do not copy credentials between machines; configure secrets through the existing host mechanism.

## Rollback

- Repoint the public daily-driver alias/route to its last reviewed model; do not edit every agent.
- Disable the GLM canary route if its review is revoked.
- Preserve case events, approvals, reports and evidence; do not delete history.
- Roll back application assets to the previous verified release before changing database truth.
- Do not roll back or replace Zerodha authentication/streaming files as part of a Research Desk rollback.
