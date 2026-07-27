/**
 * Research & Filings Terminal
 *
 * Routes: /research/filings | /special-situations | /papers | /ingest
 *
 * NSE/BSE/SEC filings, special situations (arbitrage, demergers, buybacks),
 * academic paper ingestion → strategy hypotheses, and a research-page
 * ingest pipeline that turns blogs/PDFs into strategy ideas.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  FileText, Target, BookOpen, Download, Play, Sparkles, ChevronRight,
  ExternalLink, Microscope,
} from "lucide-react";
import { useResearchIdeas } from "../../data/queries";
import {
  useRunFilingCollector, useGenerateSpecialMemo,
  useIngestResearchPaper, useIngestResearchSource,
} from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select,
} from "../../system/primitives";
import { text, num, formatRelative, formatCurrency, formatCompact } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "filings", label: "Filings", icon: FileText },
  { key: "special-situations", label: "Special Situations", icon: Target },
  { key: "papers", label: "Research Papers", icon: BookOpen },
  { key: "ingest", label: "Research Ingest", icon: Download },
];

export default function ResearchFilings({ defaultTab = "filings" }: { defaultTab?: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;
  function setTab(key: string) { navigate(`/research/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <FileText size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Research & Filings
          </div>
          <Badge tone="accent">FIL</Badge>
        </div>
        <div className="aios-destination__subtitle">
          NSE/BSE/SEC filings, special situations, academic papers, and a research ingest pipeline.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "filings" && <FilingsView />}
      {tab === "special-situations" && <SpecialSitView />}
      {tab === "papers" && <PapersView />}
      {tab === "ingest" && <IngestView />}
    </div>
  );
}

/* ============================================================
 * FILINGS
 * ============================================================ */
function FilingsView() {
  const { data, isLoading } = useResearchIdeas();
  const filings = data?.corporate_filings ?? [];
  const collectorRuns = data?.filing_collector_runs ?? [];
  const extractions = data?.filing_pdf_extraction_runs ?? [];
  const collectorMut = useRunFilingCollector();
  const pushToast = useUIStore((s) => s.pushToast);
  const openEvidence = useUIStore((s) => s.openEvidence);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Filings" value={filings.length} /></MetricTile>
        <MetricTile><Metric label="Collector Runs" value={collectorRuns.length} /></MetricTile>
        <MetricTile><Metric label="PDF Extractions" value={extractions.length} /></MetricTile>
      </div>

      <Panel icon={FileText} title="Corporate Filings"
        actions={<Button size="sm" variant="ghost" icon={Play} onClick={() => collectorMut.mutate({ actor: "Devarsh" }, { onSuccess: () => pushToast({ title: "Filing collector started", tone: "ok", duration: 3000 }), onError: (e) => pushToast({ title: "Collector failed", message: e.message, tone: "risk", duration: 5000 }) })} disabled={collectorMut.isPending}>Collect filings</Button>}
      >
        {isLoading ? <SkeletonGrid rows={6} /> : filings.length === 0 ? (
          <Empty icon={FileText} title="No filings collected" description="Run the collector to pull NSE/BSE/SEC filings." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "exchange", header: "Exchange", render: (r) => text(r, "exchange", text(r, "source_name", "—")) },
              { key: "type", header: "Filing Type", render: (r) => text(r, "filing_type", text(r, "document_type", "—")) },
              { key: "subject", header: "Subject", render: (r) => text(r, "title", text(r, "subject", text(r, "description", "—"))) },
              { key: "date", header: "Filed", render: (r) => text(r, "filed_at", text(r, "filing_date", text(r, "published_at", "—"))).slice(0, 10) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "extraction_status", text(r, "status", "collected"))} /> },
            ]}
            rows={filings}
            rowKey={(r, i) => String(text(r, "filing_id", text(r, "id", i)))}
            onRowClick={(r) => openEvidence({ kind: "artifact", key: String(text(r, "filing_id", text(r, "id"))), title: `${text(r, "symbol")} — ${text(r, "filing_type", "filing")}` })}
          />
        )}
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={FileText} title="Collector Runs">
          {collectorRuns.length === 0 ? <Empty icon={FileText} title="No runs" /> : (
            <DataTable
              columns={[
                { key: "source", header: "Source", render: (r) => text(r, "source", "NSE/BSE") },
                { key: "count", header: "Found", align: "right", render: (r) => num(r, "filings_found", 0) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "complete")} /> },
              ]}
              rows={collectorRuns}
              rowKey={(r, i) => String(text(r, "run_id", text(r, "id", i)))}
            />
          )}
        </Panel>
        <Panel icon={Microscope} title="PDF Extractions">
          {extractions.length === 0 ? <Empty icon={Microscope} title="No extractions" /> : (
            <DataTable
              columns={[
                { key: "filing", header: "Filing", render: (r) => text(r, "filing_id", "—") },
                { key: "pages", header: "Pages", align: "right", render: (r) => num(r, "pages_extracted", 0) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "complete")} /> },
              ]}
              rows={extractions}
              rowKey={(r, i) => String(text(r, "extraction_id", text(r, "id", i)))}
            />
          )}
        </Panel>
      </div>
    </>
  );
}

/* ============================================================
 * SPECIAL SITUATIONS
 * ============================================================ */
function SpecialSitView() {
  const { data, isLoading } = useResearchIdeas();
  const situations = data?.special_situations ?? [];
  const memos = data?.special_memos ?? [];
  const spreads = data?.special_spreads ?? [];
  const memoMut = useGenerateSpecialMemo();
  const pushToast = useUIStore((s) => s.pushToast);
  const openEvidence = useUIStore((s) => s.openEvidence);
  const [symbol, setSymbol] = React.useState("");

  function genMemo() {
    if (!symbol) { pushToast({ title: "Enter a symbol", tone: "warn", duration: 2500 }); return; }
    memoMut.mutate({ symbol, actor: "Devarsh" }, {
      onSuccess: () => pushToast({ title: "Special situation memo generated", tone: "ok", duration: 3000 }),
      onError: (e) => pushToast({ title: "Memo failed", message: e.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <>
      <Panel icon={Target} title="Special Situations"
        actions={
          <>
            <TextInput placeholder="Symbol…" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} style={{ width: 120 }} />
            <Button size="sm" variant="primary" icon={Sparkles} onClick={genMemo} disabled={memoMut.isPending}>Generate Memo</Button>
          </>
        }
      >
        <div style={{ padding: "var(--space-3)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
          Arbitrage, demergers, mergers, buybacks, delistings, restructurings. Each with a committee gate.
        </div>
        {isLoading ? <SkeletonGrid rows={4} /> : situations.length === 0 ? (
          <Empty icon={Target} title="No special situations" description="Generate a memo for an event-driven opportunity." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "type", header: "Type", render: (r) => text(r, "situation_type", "—") },
              { key: "spread", header: "Spread", align: "right", render: (r) => `${num(r, "spread_pct", 0).toFixed(2)}%` },
              { key: "gate", header: "Committee Gate", render: (r) => <StatusPill status={text(r, "committee_gate", text(r, "status", "review"))} /> },
              { key: "deadline", header: "Deadline", render: (r) => text(r, "deadline_date", "—") },
            ]}
            rows={situations}
            rowKey={(r, i) => String(text(r, "situation_id", text(r, "id", i)))}
            onRowClick={(r) => openEvidence({ kind: "strategy", key: String(text(r, "situation_id", text(r, "id"))), title: `${text(r, "symbol")} — ${text(r, "situation_type", "special situation")}` })}
          />
        )}
      </Panel>

      {memos.length > 0 && (
        <Panel icon={FileText} title="Situation Memos">
          <div style={{ display: "flex", flexDirection: "column", padding: "var(--space-2)" }}>
            {memos.slice(0, 10).map((memo, i) => (
              <div key={i} style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--border-subtle)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <strong>{text(memo, "symbol")} — {text(memo, "situation_type", "memo")}</strong>
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{formatRelative(text(memo, "created_at"))}</span>
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  {text(memo, "summary", text(memo, "thesis", "")).slice(0, 200)}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}

/* ============================================================
 * RESEARCH PAPERS → strategy hypotheses
 * ============================================================ */
function PapersView() {
  const { data, isLoading } = useResearchIdeas();
  const papers = data?.research_papers ?? [];
  const hypotheses = data?.paper_strategy_hypotheses ?? [];
  const ingestMut = useIngestResearchPaper();
  const pushToast = useUIStore((s) => s.pushToast);
  const [showIngest, setShowIngest] = React.useState(false);

  return (
    <>
      <Panel icon={BookOpen} title="Research Papers"
        actions={<Button size="sm" variant="primary" icon={Download} onClick={() => setShowIngest(true)}>Ingest Paper</Button>}
      >
        {isLoading ? <SkeletonGrid rows={4} /> : papers.length === 0 ? (
          <Empty icon={BookOpen} title="No papers ingested" description="Ingest academic papers to extract strategy hypotheses." />
        ) : (
          <DataTable
            columns={[
              { key: "title", header: "Paper", render: (r) => <strong>{text(r, "title")}</strong> },
              { key: "source", header: "Source", render: (r) => text(r, "source_key", "—") },
              { key: "kind", header: "Kind", render: (r) => text(r, "source_kind", "paper").replace(/_/g, " ") },
              { key: "words", header: "Extracted", align: "right", render: (r) => `${formatCompact(num(r, "extraction_word_count", 0))} words` },
              { key: "topics", header: "Topics", render: (r) => text(r, "topics", "—") },
              { key: "hypotheses", header: "Hypotheses", align: "right", render: (r) => num(r, "hypothesis_count", 0) },
              { key: "status", header: "Pipeline", render: (r) => <StatusPill status={text(r, "intake_status", text(r, "review_status", "registered"))} /> },
              { key: "when", header: "Ingested", render: (r) => formatRelative(text(r, "ingested_at", text(r, "created_at"))) },
            ]}
            rows={papers}
            rowKey={(r, i) => String(text(r, "paper_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      {hypotheses.length > 0 && (
        <Panel icon={Sparkles} title="Strategy Hypotheses (from papers)">
          <DataTable
            columns={[
              { key: "title", header: "Hypothesis", render: (r) => <strong>{text(r, "title")}</strong> },
              { key: "edge", header: "Edge", render: (r) => text(r, "edge_hypothesis", "—") },
              { key: "timeframe", header: "Timeframe", render: (r) => text(r, "timeframe", "—") },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "hypothesis")} /> },
            ]}
            rows={hypotheses}
            rowKey={(r, i) => String(text(r, "hypothesis_id", text(r, "id", i)))}
          />
        </Panel>
      )}

      <PaperIngestDrawer open={showIngest} onClose={() => setShowIngest(false)} />
    </>
  );
}

function PaperIngestDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ingestMut = useIngestResearchPaper();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({ title: "", source_key: "arxiv", source_url: "", pdf_url: "", topics: "" });

  function submit() {
    if (!form.title) { pushToast({ title: "Title required", tone: "warn", duration: 2500 }); return; }
    ingestMut.mutate(
      { ...form, topics: form.topics ? form.topics.split(",").map((t) => t.trim()) : [], actor: "Devarsh" },
      { onSuccess: () => { pushToast({ title: "Paper ingested", message: form.title.slice(0, 50), tone: "ok", duration: 3000 }); onClose(); }, onError: (e) => pushToast({ title: "Ingest failed", message: e.message, tone: "risk", duration: 5000 }) }
    );
  }

  return (
    <Drawer open={open} onClose={onClose} title="Ingest Research Paper" icon={Download} width={520}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Download} onClick={submit} disabled={ingestMut.isPending}>Ingest</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <Field label="Title" required><TextInput value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
        <Field label="Source"><Select value={form.source_key} onChange={(e) => setForm({ ...form, source_key: e.target.value })}><option>arxiv</option><option>ssrn</option><option>blog</option><option>manual</option></Select></Field>
        <Field label="URL"><TextInput value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} placeholder="https://…" /></Field>
        <Field label="PDF URL (optional)"><TextInput value={form.pdf_url} onChange={(e) => setForm({ ...form, pdf_url: e.target.value })} placeholder="https://….pdf" /></Field>
        <Field label="Topics (comma-separated)"><TextInput value={form.topics} onChange={(e) => setForm({ ...form, topics: e.target.value })} placeholder="momentum, mean-reversion, options" /></Field>
      </div>
    </Drawer>
  );
}

/* ============================================================
 * RESEARCH INGEST — pages/blogs/PDFs → strategy ideas
 * ============================================================ */
function IngestView() {
  const pushToast = useUIStore((s) => s.pushToast);
  const openEvidence = useUIStore((s) => s.openEvidence);
  const { data, isLoading } = useResearchIdeas();
  const ingest = useIngestResearchSource();
  const [lastResult, setLastResult] = React.useState<LiveRow | null>(null);
  const [form, setForm] = React.useState({
    title: "",
    source_url: "",
    pasted_text: "",
    research_objective: "",
    hypothesis: "",
    target_universe: "NSE listed equities",
    timeframe: "",
    priority: "medium" as "low" | "medium" | "high" | "critical",
  });
  const papers = data?.research_papers ?? [];
  const hypotheses = data?.paper_strategy_hypotheses ?? [];
  const cycles = data?.research_cycles ?? [];
  const activeIntakes = papers.filter((row) => !["reviewed", "closed"].includes(text(row, "intake_status", text(row, "review_status")).toLowerCase()));

  function submit() {
    if (!form.source_url.trim() && !form.pasted_text.trim()) {
      pushToast({ title: "Add a URL or paste the article text", tone: "warn", duration: 3000 });
      return;
    }
    if (!form.research_objective.trim()) {
      pushToast({ title: "Research objective required", tone: "warn", duration: 3000 });
      return;
    }
    const sourceKey = form.source_url.includes("github.com") ? "github" : form.source_url ? "web" : "manual";
    ingest.mutate({
      ...form,
      source_url: form.source_url.trim() || undefined,
      pasted_text: form.pasted_text.trim() || undefined,
      title: form.title.trim() || undefined,
      hypothesis: form.hypothesis.trim() || undefined,
      timeframe: form.timeframe.trim() || undefined,
      source_key: sourceKey,
      source_kind: form.source_url ? "web_article" : "operator_note",
      desired_outputs: ["research_note", "hypothesis_review", "backtest_spec"],
      topics: ["operator_intake"],
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        setLastResult(result);
        setForm((current) => ({ ...current, title: "", source_url: "", pasted_text: "", research_objective: "", hypothesis: "", timeframe: "" }));
        const assignments = Array.isArray(result.assignments) ? result.assignments.length : 0;
        pushToast({ title: "Research cycle started", message: `${assignments} employees assigned`, tone: "ok", duration: 4500 });
      },
      onError: (error) => pushToast({ title: "Ingestion failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Sources" value={papers.length} /></MetricTile>
        <MetricTile tone={activeIntakes.length ? "warn" : "ok"}><Metric label="Active Intakes" value={activeIntakes.length} /></MetricTile>
        <MetricTile><Metric label="Hypotheses" value={hypotheses.length} /></MetricTile>
        <MetricTile><Metric label="Research Cycles" value={cycles.length} /></MetricTile>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(420px, 0.95fr) minmax(560px, 1.35fr)", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Download} title="Start Research Cycle" actions={<Badge tone={ingest.isPending ? "warn" : "ok"}>{ingest.isPending ? "Extracting" : "Ready"}</Badge>}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            <Field label="Public article, blog, paper, or GitHub URL"><TextInput value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://…" /></Field>
            <Field label="Or paste the source text"><TextArea value={form.pasted_text} onChange={(event) => setForm({ ...form, pasted_text: event.target.value })} rows={5} placeholder="Paste article text, research notes, or a strategy description…" /></Field>
            <Field label="Title (auto-detected when blank)"><TextInput value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
            <Field label="What should the team determine?" required><TextArea value={form.research_objective} onChange={(event) => setForm({ ...form, research_objective: event.target.value })} rows={3} placeholder="Verify the claims, map affected companies or factors, and decide whether a testable edge exists…" /></Field>
            <Field label="Hypothesis to test (optional)"><TextArea value={form.hypothesis} onChange={(event) => setForm({ ...form, hypothesis: event.target.value })} rows={3} placeholder="Example: rising FPI sector allocation predicts relative 20-day outperformance after costs…" /></Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 0.7fr 0.7fr", gap: "var(--space-3)" }}>
              <Field label="Universe"><TextInput value={form.target_universe} onChange={(event) => setForm({ ...form, target_universe: event.target.value })} /></Field>
              <Field label="Timeframe"><TextInput value={form.timeframe} onChange={(event) => setForm({ ...form, timeframe: event.target.value })} placeholder="20 days" /></Field>
              <Field label="Priority"><Select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value as typeof form.priority })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></Select></Field>
            </div>
            <Button variant="primary" icon={Sparkles} onClick={submit} disabled={ingest.isPending}>Extract, assign, and queue review</Button>
          </div>
        </Panel>
        <Panel icon={Microscope} title="Live Intake Pipeline" actions={<Badge tone={activeIntakes.length ? "warn" : "ok"}>{activeIntakes.length} active</Badge>}>
          {isLoading ? <SkeletonGrid rows={6} /> : papers.length === 0 ? <Empty icon={Microscope} title="No source intakes yet" description="The first submitted source will appear here with extraction and review status." /> : (
            <DataTable
              columns={[
                { key: "source", header: "Source", render: (r) => <div><strong>{text(r, "title")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 3 }}>{text(r, "research_objective", text(r, "source_url", "No objective recorded")).slice(0, 120)}</div></div> },
                { key: "words", header: "Words", align: "right", render: (r) => formatCompact(num(r, "extraction_word_count", 0)) },
                { key: "hypotheses", header: "Hypotheses", align: "right", render: (r) => num(r, "hypothesis_count", 0) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "intake_status", text(r, "review_status", "registered"))} /> },
                { key: "when", header: "Updated", render: (r) => formatRelative(text(r, "updated_at")) },
              ]}
              rows={papers}
              rowKey={(r, i) => String(text(r, "id", i))}
              onRowClick={(r) => openEvidence({ kind: "artifact", key: String(text(r, "id")), title: text(r, "title", "Research source") })}
            />
          )}
        </Panel>
      </div>
      {lastResult && (
        <Panel icon={Sparkles} title="Cycle Created" actions={<StatusPill status="queued" />}>
          <div style={{ padding: "var(--space-3)", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "var(--space-3)" }}>
            <MetricTile><Metric label="Employees Assigned" value={Array.isArray(lastResult.assignments) ? lastResult.assignments.length : 0} /></MetricTile>
            <MetricTile><Metric label="Draft Hypotheses" value={num((lastResult.hypothesis_result as LiveRow) ?? {}, "count", 0)} /></MetricTile>
            <MetricTile><Metric label="Execution" value="Locked" /></MetricTile>
          </div>
        </Panel>
      )}
    </>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
