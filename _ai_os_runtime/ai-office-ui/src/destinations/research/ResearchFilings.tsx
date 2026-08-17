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
  ExternalLink, Microscope, Newspaper, Activity, Star, RefreshCw,
  AlertTriangle, Plus, ShieldCheck,
} from "lucide-react";
import { useMissionControl, useResearchIdeas } from "../../data/queries";
import {
  useRunFilingCollector, useGenerateSpecialMemo,
  useIngestResearchPaper, useIngestResearchSource, useIngestMarketNews,
  useRegisterInvestorSource,
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
  const { data: mission } = useMissionControl();
  const ingest = useIngestResearchSource();
  const refreshFeeds = useIngestMarketNews();
  const registerSource = useRegisterInvestorSource();
  const [lastResult, setLastResult] = React.useState<LiveRow | null>(null);
  const [showSourceForm, setShowSourceForm] = React.useState(false);
  const [sourceForm, setSourceForm] = React.useState({
    feed_name: "", provider: "", url: "", geography: "India", topics: "", refresh_minutes: "60",
  });
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
  const feeds = data?.feed_registry ?? [];
  const watchlist = data?.watchlist ?? [];
  const quotes = data?.market_quotes ?? [];
  const latestNews = data?.latest_news ?? [];
  const filings = data?.filing_intelligence ?? [];
  const sourceChecks = data?.news_source_checks ?? [];
  const heartbeats = mission?.market_research_heartbeats ?? [];
  const sourceFreshness = mission?.source_freshness ?? [];
  const activeFeeds = feeds.filter((row) => text(row, "status") === "active");
  const sourceAttention = sourceFreshness.filter((row) => {
    const status = text(row, "status", text(row, "freshness_status")).toLowerCase();
    return ["stale", "missing", "error", "overdue"].some((flag) => status.includes(flag));
  });
  const sortedQuoteTimes = quotes.map((row) => text(row, "quote_ts")).filter(Boolean).sort();
  const latestQuoteAt = sortedQuoteTimes[sortedQuoteTimes.length - 1] ?? "";
  const quoteBySymbol = React.useMemo(() => new Map(
    quotes.map((row) => [text(row, "symbol").toUpperCase(), row]),
  ), [quotes]);
  const intelligenceTimeline = React.useMemo(() => {
    const combined = [
      ...latestNews.map((row) => ({ ...row, timeline_kind: "News", timeline_at: text(row, "published_at", text(row, "captured_at")) })),
      ...filings.map((row) => ({ ...row, timeline_kind: "Filing", timeline_at: text(row, "filed_at") })),
    ];
    const seen = new Set<string>();
    return combined
      .sort((left, right) => Date.parse(text(right, "timeline_at")) - Date.parse(text(left, "timeline_at")))
      .filter((row) => {
        const key = text(row, "source_url") || text(row, "title").toLowerCase();
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 24);
  }, [filings, latestNews]);
  const activeIntakes = papers.filter((row) => !["reviewed", "closed"].includes(text(row, "intake_status", text(row, "review_status")).toLowerCase()));

  function investigate(row: LiveRow) {
    const kind = text(row, "timeline_kind", "source").toLowerCase();
    setForm((current) => ({
      ...current,
      title: text(row, "title"),
      source_url: text(row, "source_url"),
      research_objective: "Verify the source claims, map affected companies and risks, and prepare a cited decision brief.",
      priority: kind === "filing" ? "high" : current.priority,
    }));
    document.getElementById("research-intake-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function refreshPublicFeeds() {
    refreshFeeds.mutate({ actor: "Devarsh" }, {
      onSuccess: (result) => pushToast({
        title: "Public research feeds refreshed",
        message: num(result, "items_upserted", 0) + " source-linked item(s) updated.",
        tone: "ok",
        duration: 4500,
      }),
      onError: (error) => pushToast({ title: "Feed refresh failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  function addInvestorSource() {
    if (!sourceForm.feed_name.trim() || !sourceForm.url.trim()) {
      pushToast({ title: "Investor or firm name and RSS URL are required", tone: "warn", duration: 3500 });
      return;
    }
    registerSource.mutate({
      feed_name: sourceForm.feed_name.trim(),
      provider: sourceForm.provider.trim() || sourceForm.feed_name.trim(),
      url: sourceForm.url.trim(),
      geography: sourceForm.geography.trim() || "Global",
      topics: sourceForm.topics.split(",").map((value) => value.trim()).filter(Boolean),
      refresh_minutes: Number(sourceForm.refresh_minutes) || 60,
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        pushToast({ title: "Source added for review", message: "It remains gated until its public feed and policy are reviewed.", tone: "ok", duration: 5000 });
        setSourceForm({ feed_name: "", provider: "", url: "", geography: "India", topics: "", refresh_minutes: "60" });
        setShowSourceForm(false);
      },
      onError: (error) => pushToast({ title: "Source registration rejected", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

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
      <Panel
        icon={Activity}
        title="Research & Market Heartbeat"
        actions={<Button size="sm" variant="ghost" icon={RefreshCw} onClick={refreshPublicFeeds} disabled={refreshFeeds.isPending}>{refreshFeeds.isPending ? "Refreshing public feeds…" : "Refresh public feeds"}</Button>}
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
          <MetricTile><Metric label="Watchlist" value={watchlist.length} sub="thesis-linked items" /></MetricTile>
          <MetricTile tone={quotes.length ? "default" : "warn"}><Metric label="Market quotes" value={quotes.length} sub={latestQuoteAt ? formatRelative(latestQuoteAt) : "No accepted quote"} /></MetricTile>
          <MetricTile><Metric label="Source-linked news" value={latestNews.length} sub={sourceChecks.length + " RSS checks"} /></MetricTile>
          <MetricTile><Metric label="Filing intelligence" value={filings.length} sub="exchange evidence" /></MetricTile>
          <MetricTile tone={sourceAttention.length ? "warn" : "ok"}><Metric label="Feed attention" value={sourceAttention.length} sub={sourceAttention.length ? "stale, missing, or failed" : "accepted checks healthy"} /></MetricTile>
          <MetricTile><Metric label="Autonomous heartbeats" value={heartbeats.length} sub="durable monitored runs" /></MetricTile>
        </div>
        <div style={{ marginTop: "var(--space-3)", display: "flex", gap: "var(--space-3)", flexWrap: "wrap", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          <span>{activeFeeds.length} active lawful feeds · {feeds.filter((row) => text(row, "status") !== "active").length} visibly gated</span>
          <strong style={{ color: "var(--status-ok)" }}>Research and drafts only · no automatic trading action</strong>
        </div>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Star} title="Source-backed Watchlist" actions={<Badge tone="ok">{watchlist.length} active</Badge>}>
          {watchlist.length === 0 ? <Empty icon={Star} title="No watchlist items" description="Add a thesis-linked item from Charlie or the watchlist workflow." /> : <DataTable dense columns={[
            { key: "symbol", header: "Security", render: (row) => <><strong>{text(row, "symbol")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "exchange", "NSE")} · {text(row, "priority", "medium")}</div></> },
            { key: "market", header: "Latest accepted quote", align: "right", render: (row) => {
              const quote = quoteBySymbol.get(text(row, "symbol").toUpperCase());
              return quote ? <><div>{num(quote, "price", 0).toLocaleString()}</div><div style={{ color: num(quote, "change_percent", 0) >= 0 ? "var(--status-ok)" : "var(--status-risk)", fontSize: "var(--text-xs)" }}>{num(quote, "change_percent", 0).toFixed(2)}% · {formatRelative(text(quote, "quote_ts"))}</div></> : <span style={{ color: "var(--status-warn)" }}>No matched quote</span>;
            } },
            { key: "thesis", header: "Thesis / catalyst", render: (row) => <><div>{text(row, "thesis", "No thesis recorded")}</div><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 3 }}>{text(row, "catalyst", "No catalyst recorded")}</div></> },
            { key: "review", header: "Review", render: (row) => text(row, "review_on", "Not scheduled") },
            { key: "evidence", header: "Evidence", render: (row) => <Button size="sm" variant="ghost" onClick={() => openEvidence({ kind: "artifact", key: String(text(row, "id")), title: text(row, "symbol") + " watchlist evidence" })}>Open</Button> },
          ]} rows={watchlist} rowKey={(row, index) => String(text(row, "id", index))} />}
        </Panel>

        <Panel icon={Newspaper} title="Deduplicated Intelligence Timeline" actions={<Badge tone="accent">source linked</Badge>}>
          {intelligenceTimeline.length === 0 ? <Empty icon={Newspaper} title="No accepted intelligence items" description="Public sources are empty or unavailable; no narrative has been invented." /> : <DataTable dense columns={[
            { key: "kind", header: "Type", render: (row) => <StatusPill status={text(row, "timeline_kind", "source").toLowerCase()} /> },
            { key: "item", header: "Item", render: (row) => <><strong>{text(row, "title")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 3 }}>{text(row, "publisher", text(row, "source_name", "Public source"))}</div></> },
            { key: "scope", header: "Companies / themes", render: (row) => text(row, "symbol", text(row, "symbols", text(row, "topics", "—"))) },
            { key: "when", header: "Source time", render: (row) => formatRelative(text(row, "timeline_at")) },
            { key: "source", header: "Original", render: (row) => text(row, "source_url") ? <a href={text(row, "source_url")} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Open <ExternalLink size={12} /></a> : <span style={{ color: "var(--status-warn)" }}>URL unavailable</span> },
            { key: "action", header: "Action", render: (row) => <Button size="sm" variant="ghost" icon={Sparkles} onClick={() => investigate(row)}>Investigate</Button> },
          ]} rows={intelligenceTimeline} rowKey={(row, index) => text(row, "source_url", text(row, "title", index))} />}
        </Panel>
      </div>

      <Panel icon={ShieldCheck} title="Investor & Public Source Registry" actions={<Button size="sm" variant="ghost" icon={Plus} onClick={() => setShowSourceForm((value) => !value)}>{showSourceForm ? "Close" : "Add source"}</Button>}>
        <div style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
          Only public RSS/Atom or explicitly authorized connectors are collected. Social or credential-bound sources remain visibly gated; claims require corroboration before investment use.
        </div>
        {showSourceForm ? <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "var(--space-3)", alignItems: "end", marginBottom: "var(--space-4)", padding: "var(--space-3)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}>
          <Field label="Investor / firm" required><TextInput value={sourceForm.feed_name} onChange={(event) => setSourceForm({ ...sourceForm, feed_name: event.target.value })} /></Field>
          <Field label="Provider"><TextInput value={sourceForm.provider} onChange={(event) => setSourceForm({ ...sourceForm, provider: event.target.value })} /></Field>
          <Field label="Public HTTPS RSS / Atom URL" required><TextInput value={sourceForm.url} onChange={(event) => setSourceForm({ ...sourceForm, url: event.target.value })} placeholder="https://example.com/feed" /></Field>
          <Field label="Topics"><TextInput value={sourceForm.topics} onChange={(event) => setSourceForm({ ...sourceForm, topics: event.target.value })} placeholder="value investing, results" /></Field>
          <Field label="Refresh minutes"><TextInput value={sourceForm.refresh_minutes} onChange={(event) => setSourceForm({ ...sourceForm, refresh_minutes: event.target.value })} /></Field>
          <Button variant="primary" icon={ShieldCheck} onClick={addInvestorSource} disabled={registerSource.isPending || !sourceForm.feed_name.trim() || !sourceForm.url.trim()}>{registerSource.isPending ? "Registering…" : "Add for policy review"}</Button>
          <div style={{ gridColumn: "1 / -1", color: "var(--status-warn)", fontSize: "var(--text-sm)" }}>New sources are saved as planned and are not fetched until their public endpoint and terms are reviewed.</div>
        </div> : null}
        {feeds.length === 0 ? <Empty icon={AlertTriangle} title="No source registry" description="No feed is collected until an approved source is registered." /> : <DataTable dense columns={[
          { key: "source", header: "Source", render: (row) => <><strong>{text(row, "feed_name")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "feed_type").replace(/_/g, " ")} · {text(row, "provider", "—")}</div></> },
          { key: "scope", header: "Scope", render: (row) => text(row, "topics", text(row, "geography", "—")) },
          { key: "status", header: "Collection", render: (row) => <StatusPill status={text(row, "status", "planned")} /> },
          { key: "check", header: "Latest check", render: (row) => {
            const check = sourceChecks.find((item) => text(item, "source_key") === text(row, "feed_key"));
            return check ? <><StatusPill status={text(check, "status", "unknown")} /><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{formatRelative(text(check, "checked_at"))}</div></> : <span style={{ color: "var(--status-warn)" }}>Not checked</span>;
          } },
          { key: "owner", header: "Accountable agent", render: (row) => text(row, "owner_agent", "Research Agent") },
          { key: "url", header: "Source", render: (row) => text(row, "url") ? <a href={text(row, "url")} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Open feed <ExternalLink size={12} /></a> : "Connector gated" },
        ]} rows={feeds} rowKey={(row, index) => text(row, "feed_key", index)} />}
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Sources" value={papers.length} /></MetricTile>
        <MetricTile tone={activeIntakes.length ? "warn" : "ok"}><Metric label="Active Intakes" value={activeIntakes.length} /></MetricTile>
        <MetricTile><Metric label="Hypotheses" value={hypotheses.length} /></MetricTile>
        <MetricTile><Metric label="Research Cycles" value={cycles.length} /></MetricTile>
      </div>
      <div id="research-intake-form" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))", gap: "var(--space-4)", alignItems: "start", scrollMarginTop: 88 }}>
        <Panel icon={Download} title="Start Research Cycle" actions={<Badge tone={ingest.isPending ? "warn" : "ok"}>{ingest.isPending ? "Extracting" : "Ready"}</Badge>}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            <Field label="Public article, blog, paper, or GitHub URL"><TextInput value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://…" /></Field>
            <Field label="Or paste the source text"><TextArea value={form.pasted_text} onChange={(event) => setForm({ ...form, pasted_text: event.target.value })} rows={5} placeholder="Paste article text, research notes, or a strategy description…" /></Field>
            <Field label="Title (auto-detected when blank)"><TextInput value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></Field>
            <Field label="What should the team determine?" required><TextArea value={form.research_objective} onChange={(event) => setForm({ ...form, research_objective: event.target.value })} rows={3} placeholder="Verify the claims, map affected companies or factors, and decide whether a testable edge exists…" /></Field>
            <Field label="Hypothesis to test (optional)"><TextArea value={form.hypothesis} onChange={(event) => setForm({ ...form, hypothesis: event.target.value })} rows={3} placeholder="Example: rising FPI sector allocation predicts relative 20-day outperformance after costs…" /></Field>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 150px), 1fr))", gap: "var(--space-3)" }}>
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
