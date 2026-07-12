# Holdings Research And Ideas v2

Date: 2026-07-13
Status: verified implementation checkpoint
Parent: [[AI Investment OS - Institutional Master Blueprint v10.0]]
Checklist: [[AI Investment OS - Execution Checklist v10.0]]
Frontend: [[AI OS Command Center and 3D Office Frontend Plan]]

## Result

Holdings Research and Ideas now share a production-data-only scoped read model. Their routes do not start the 7.6 MB broad snapshot or stale right rail. Research combines long-term coverage, committee state, filings, news, special situations, and outputs. Ideas combines durable intake, discovery candidates, generated ideas, dossiers, memos, and output artifacts.

## Live Evidence

- Endpoint: `GET /api/research-ideas/snapshot`.
- Policy: `seed_data_allowed=false`, source `scoped_research_ideas_read_model`.
- Response: 318,821 bytes in 0.603 seconds, HTTP `200`.
- Coverage: 322 rows across 15 bounded queries.
- Current rows: 46 theses, 2 committee reviews, 28 filings, 9 news items, 3 special situations, 1 special memo, 64 generated ideas, 51 discovery candidates, 10 dossiers, and 73 artifacts.
- Execution remained locked; live broker writes were disabled.

## Holdings Research

- Long-term thesis exposure, checklist coverage, review state, and due dates.
- Investment Committee review/memo/approval visibility.
- Corporate filing extraction/event/opportunity metadata.
- Curated news with symbol, sentiment, relevance, and timestamp.
- Special-situation event visibility and durable research outputs.

## Ideas

- New strategy intake creates durable research, backtest-spec, and risk-review work.
- The intake route has no broker-order authority.
- Idea dossiers expose triage, next action, score, and evidence state.
- Discovery and generated-idea queues show research/optimizer gates.
- Special-situation memos and research/strategy outputs remain linked.

## Verification

- TypeScript/Vite production build and Python source compilation passed.
- Research and Ideas passed at 1440 x 1000 and 390 x 844.
- Each fresh route issued one scoped request and zero broad requests.
- No stale rail, overflow, collision, clipped metadata, vertical status pill, console error, or page error.
- The repeated clipping failure was resolved after reviewing MDN grid/overflow guidance: bounded wrap-safe metadata tracks and growing rows preserve complete warehouse labels.
- Screenshots: `/Volumes/Devarsh SSD/AI OS Data/artifacts/browser-verification/2026-07-13-research-ideas-v2`.

## Blueprint Registry

- Sync run: `blueprint-v10-research-ideas-v2-20260713`.
- Checklist SHA-256: `13df88b4fdb61361d789c51ad52c910f0c1418897cfb64113c48261dec23be04`.
- Coverage: 21 domains, 521 requirements, 45 done, 174 partial, 302 planned, zero seed rows.

## Remaining Work

- Filing/news source expansion, drill-down, collection, and source-document actions.
- Full corporate-action detector catalog and terms/spread/decision controls.
- Thesis packet and committee decision drawers with evidence links.
- Dossier triage, semantic search, optimizer routing, and committee actions in the scoped UI.
- Alerts, scheduled briefs, and report-generation controls.
