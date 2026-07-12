import {
  BookOpenText,
  BrainCircuit,
  FileSearch,
  Lightbulb,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createStrategyIntake, type LiveRow } from "../api/live";
import { fetchResearchIdeasSnapshot, type ResearchIdeasSnapshot } from "../api/researchIdeas";

type ConnectionStatus = "loading" | "online" | "offline";
type Mode = "research" | "ideas";

interface Props {
  mode: Mode;
  onStatusChange: (status: ConnectionStatus) => void;
}

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (typeof raw === "object") {
    if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
    return Object.entries(raw).map(([label, detail]) => `${label.replace(/_/g, " ")}: ${String(detail)}`).join(" · ") || fallback;
  }
  return String(raw);
}

function amount(raw: unknown): string {
  const numeric = Number(raw ?? 0);
  if (!Number.isFinite(numeric)) return "-";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(numeric);
}

function date(raw: unknown): string {
  if (!raw) return "not recorded";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["active", "approved", "complete", "completed", "extracted", "indexed", "ready"].includes(normalized)) return "active";
  if (["blocked", "critical", "error", "failed", "rejected", "source_required"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

function matches(row: LiveRow, query: string): boolean {
  if (!query) return true;
  return ["symbol", "company_name", "title", "thesis_title", "strategy_name", "memo_title"]
    .some((key) => value(row, key, "").toLowerCase().includes(query));
}

export default function ResearchIdeasWorkspace({ mode, onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<ResearchIdeasSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [intakeBusy, setIntakeBusy] = useState(false);
  const [intake, setIntake] = useState({ name: "", family: "", timeframe: "daily", text: "" });

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchResearchIdeasSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research and Ideas API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:research-ideas-refresh", handleRefresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("aios:research-ideas-refresh", handleRefresh);
    };
  }, [refresh]);

  const normalizedQuery = query.trim().toLowerCase();
  const theses = (snapshot?.long_term_theses ?? []).filter((row) => matches(row, normalizedQuery));
  const filings = (snapshot?.corporate_filings ?? []).filter((row) => matches(row, normalizedQuery));
  const news = (snapshot?.latest_news ?? []).filter((row) => matches(row, normalizedQuery));
  const special = (snapshot?.special_situations ?? []).filter((row) => matches(row, normalizedQuery));
  const artifacts = (snapshot?.output_artifacts ?? []).filter((row) => matches(row, normalizedQuery));
  const ideas = (snapshot?.generated_ideas ?? []).filter((row) => matches(row, normalizedQuery));
  const discoveries = (snapshot?.discovery_candidates ?? []).filter((row) => matches(row, normalizedQuery));
  const dossiers = (snapshot?.idea_dossiers ?? []).filter((row) => matches(row, normalizedQuery));
  const execution = snapshot?.execution_control[0];
  const thesisExposure = useMemo(() => theses.reduce((sum, row) => sum + Number(row.long_term_gross_exposure ?? 0), 0), [theses]);
  const sourceRequired = theses.filter((row) => value(row, "thesis_status", "") === "source_required").length;

  const submitIntake = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIntakeBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await createStrategyIntake({
        actor: "Devarsh",
        intake_text: intake.text,
        strategy_name: intake.name || undefined,
        strategy_family: intake.family || undefined,
        timeframe: intake.timeframe,
        requested_outputs: ["research_dossier", "backtest_spec", "risk_review"]
      });
      setNotice(`Strategy intake #${value(result, "id")} created for research and validation. Broker orders remain disabled.`);
      setIntake({ name: "", family: "", timeframe: "daily", text: "" });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Strategy intake failed");
    } finally {
      setIntakeBusy(false);
    }
  };

  return (
    <div className="research-ideas-workspace">
      <div className="workspace-filter-bar">
        <label><span>Research filter</span><input aria-label="Research filter" onChange={(event) => setQuery(event.target.value)} placeholder="Filter symbol, company, thesis, memo, or idea" value={query} /></label>
        <div><span>{mode === "research" ? "Research factory" : "Idea factory"}</span><button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button"><RefreshCw size={14} />{status === "loading" ? "Checking" : "Refresh"}</button></div>
      </div>

      <section className="metric-grid" aria-label="Research and Ideas metrics">
        <div className="metric-tile"><span>Scoped API</span><strong>{status === "online" ? "Online" : status}</strong><p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p></div>
        <div className="metric-tile"><span>{mode === "research" ? "Long-Term Theses" : "Generated Ideas"}</span><strong>{mode === "research" ? theses.length : ideas.length}</strong><p className="tone-neutral">source-backed registry</p></div>
        <div className="metric-tile"><span>{mode === "research" ? "Covered Exposure" : "Idea Dossiers"}</span><strong>{mode === "research" ? amount(thesisExposure) : dossiers.length}</strong><p className="tone-neutral">durable evidence</p></div>
        <div className="metric-tile"><span>{mode === "research" ? "Source Required" : "Discovery Queue"}</span><strong>{mode === "research" ? sourceRequired : discoveries.length}</strong><p className={sourceRequired ? "tone-warn" : "tone-good"}>{special.length} special situations</p></div>
        <div className="metric-tile"><span>Execution</span><strong>{value(execution, "global_execution_locked", "true") === "true" ? "Locked" : "Review"}</strong><p className="tone-good">broker writes disabled</p></div>
      </section>

      {error ? <div className="error-strip">{error}</div> : null}
      {notice ? <div className="success-strip">{notice}</div> : null}

      {mode === "research" ? (
        <section className="dashboard-grid">
          <Panel className="span-7" icon={<BookOpenText size={17} />} title="Long-Term Thesis Coverage" action={<span>{theses.length} theses</span>}><div className="source-check-list scoped-scroll-list">{theses.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "company_name")}</strong><p>{value(row, "thesis_title")} · {value(row, "checklist_complete_count", "0")}/{value(row, "checklist_count", "0")} checklists</p></div><StatusPill status={value(row, "thesis_status", "review")} /><span>{amount(row.long_term_gross_exposure)}</span><time>{date(row.next_review_due_at)}</time></article>)}{!theses.length ? <Empty>No thesis rows match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<ShieldCheck size={17} />} title="Investment Committee" action={<span>{snapshot?.committee_queue.length ?? 0} reviews</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.committee_queue.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "company_name")}</strong><p>{value(row, "recommended_decision")} · approval {value(row, "approval_status")}</p></div><StatusPill status={value(row, "review_status", "review")} /><span>{value(row, "memo_status")}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.committee_queue.length ? <Empty>No committee reviews.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<FileSearch size={17} />} title="Corporate Filings" action={<span>{filings.length} filings</span>}><div className="source-check-list scoped-scroll-list">{filings.map((row) => <article className="source-check-row" key={value(row, "filing_id")}><div><strong>{value(row, "symbol")} · {value(row, "title")}</strong><p>{value(row, "source_name")} · {value(row, "event_type", value(row, "filing_event_type"))} · {value(row, "pdf_page_count", "0")} pages</p></div><StatusPill status={value(row, "extraction_status", "pending")} /><span>opp {value(row, "opportunity_score", "-")}</span><time>{date(row.filed_at)}</time></article>)}{!filings.length ? <Empty>No filing rows match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<Newspaper size={17} />} title="Curated News" action={<span>{news.length} items</span>}><div className="source-check-list scoped-scroll-list">{news.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "title")}</strong><p>{value(row, "source_name")} · {value(row, "symbols", "broad market")}</p></div><StatusPill status={value(row, "sentiment", "neutral")} /><span>{value(row, "relevance_score", "-")}</span><time>{date(row.published_at ?? row.captured_at)}</time></article>)}{!news.length ? <Empty>No news rows match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-6" icon={<Sparkles size={17} />} title="Special Situations" action={<span>{special.length} events</span>}><div className="source-check-list scoped-scroll-list">{special.map((row) => <article className="source-check-row" key={value(row, "filing_id")}><div><strong>{value(row, "symbol")} · {value(row, "event_type")}</strong><p>{value(row, "title")}</p></div><StatusPill status={value(row, "urgency", "review")} /><span>opp {value(row, "opportunity_score", "-")}</span><time>{date(row.filed_at)}</time></article>)}{!special.length ? <Empty>No special-situation rows.</Empty> : null}</div></Panel>
          <Panel className="span-6" icon={<BrainCircuit size={17} />} title="Research Outputs" action={<span>{artifacts.length} artifacts</span>}><div className="source-check-list scoped-scroll-list">{artifacts.map((row) => <article className="source-check-row" key={value(row, "artifact_key")}><div><strong>{value(row, "title")}</strong><p>{value(row, "artifact_family")} · {value(row, "owner_agent")}</p></div><StatusPill status={value(row, "status", "stored")} /><span>{value(row, "symbol", value(row, "strategy_name", "-"))}</span><time>{date(row.latest_activity_at)}</time></article>)}{!artifacts.length ? <Empty>No output artifacts match this filter.</Empty> : null}</div></Panel>
        </section>
      ) : (
        <section className="dashboard-grid">
          <Panel className="span-5" icon={<Lightbulb size={17} />} title="New Strategy Intake"><form className="strategy-intake-form" onSubmit={submitIntake}><label><span>Name</span><input value={intake.name} onChange={(event) => setIntake((current) => ({ ...current, name: event.target.value }))} /></label><label><span>Family</span><input value={intake.family} onChange={(event) => setIntake((current) => ({ ...current, family: event.target.value }))} /></label><label><span>Timeframe</span><select value={intake.timeframe} onChange={(event) => setIntake((current) => ({ ...current, timeframe: event.target.value }))}><option value="intraday">Intraday</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="event_driven">Event driven</option></select></label><label className="span-form"><span>Strategy idea and rules</span><textarea required rows={6} value={intake.text} onChange={(event) => setIntake((current) => ({ ...current, text: event.target.value }))} /></label><button className="primary-button span-form" disabled={intakeBusy} type="submit"><Sparkles size={15} />{intakeBusy ? "Routing" : "Create research intake"}</button><p className="form-guard span-form">Creates research, backtest, and risk-review work. It cannot place broker orders.</p></form></Panel>
          <Panel className="span-7" icon={<BookOpenText size={17} />} title="Idea Dossiers" action={<span>{dossiers.length} dossiers</span>}><div className="source-check-list scoped-scroll-list">{dossiers.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "title")}</strong><p>{value(row, "summary")} · next: {value(row, "recommended_next_action")}</p></div><StatusPill status={value(row, "status", "research")} /><span>{value(row, "priority_score", "-")}</span><time>{date(row.updated_at)}</time></article>)}{!dossiers.length ? <Empty>No idea dossiers match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<BrainCircuit size={17} />} title="Discovery Candidates" action={<span>{discoveries.length} candidates</span>}><div className="source-check-list scoped-scroll-list">{discoveries.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "title")}</strong><p>{value(row, "template")} · {value(row, "timeframe")} · {value(row, "next_required_action")}</p></div><StatusPill status={value(row, "research_gate", value(row, "status", "research"))} /><span>score {value(row, "priority_score", "-")}</span><time>{date(row.created_at)}</time></article>)}{!discoveries.length ? <Empty>No discovery candidates match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<Lightbulb size={17} />} title="Generated Ideas" action={<span>{ideas.length} ideas</span>}><div className="source-check-list scoped-scroll-list">{ideas.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "title")}</strong><p>{value(row, "edge_hypothesis")}</p></div><StatusPill status={value(row, "status", "research")} /><span>{value(row, "symbols", value(row, "universe"))}</span><time>{date(row.created_at)}</time></article>)}{!ideas.length ? <Empty>No generated ideas match this filter.</Empty> : null}</div></Panel>
          <Panel className="span-6" icon={<Sparkles size={17} />} title="Special-Situation Memos" action={<span>{snapshot?.special_memos.length ?? 0} memos</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.special_memos.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "memo_title")}</strong><p>{value(row, "summary")} · latest spread {value(row, "latest_gross_spread_pct", "-")}%</p></div><StatusPill status={value(row, "memo_status", "review")} /><span>{value(row, "latest_decision", "pending")}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.special_memos.length ? <Empty>No special-situation memos.</Empty> : null}</div></Panel>
          <Panel className="span-6" icon={<FileSearch size={17} />} title="Research And Strategy Outputs" action={<span>{artifacts.length} artifacts</span>}><div className="source-check-list scoped-scroll-list">{artifacts.map((row) => <article className="source-check-row" key={value(row, "artifact_key")}><div><strong>{value(row, "title")}</strong><p>{value(row, "artifact_family")} · {value(row, "owner_agent")}</p></div><StatusPill status={value(row, "status", "stored")} /><span>{value(row, "strategy_name", value(row, "symbol", "-"))}</span><time>{date(row.latest_activity_at)}</time></article>)}{!artifacts.length ? <Empty>No artifacts match this filter.</Empty> : null}</div></Panel>
        </section>
      )}
    </div>
  );
}
