import React from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  ExternalLink,
  FileText,
  Library,
  LoaderCircle,
  Radar,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import {
  useFundamentalScanner,
  useCreateFundamentalScanner,
  useFollowResearchSource,
  useResearchCases,
  useResearchFollowingSources,
  useResearchKnowledge,
  useResearchMonitoring,
  useResearchUpdates,
  useRefreshResearchSource,
  useScannerAction,
} from "../../data/queries";
import { formatRelative, num, text } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";
import { Badge, Skeleton, StatusPill } from "../../system/primitives";
import { useUIStore } from "../../store";
import { ResearchDeskNav } from "./ResearchDeskNav";
import { ResearchDeskCss } from "./ResearchDesk.css";

function toneFor(status: string): "ok" | "warn" | "risk" | "accent" | "default" {
  const value = status.toLowerCase();
  if (["completed", "accepted", "reviewed", "ready"].includes(value)) return "ok";
  if (["blocked", "failed", "critical", "high"].includes(value)) return "risk";
  if (["active", "running", "review"].includes(value)) return "accent";
  if (["proposed", "collecting", "medium", "stale"].includes(value)) return "warn";
  return "default";
}

type FailureCopy = { summary: string; nextAction: string; technical: string };

function rawFailure(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try { return JSON.stringify(error); } catch { return ""; }
}

function redactTechnicalDetail(error: unknown): string {
  const raw = rawFailure(error) || "No additional diagnostic detail was returned.";
  return raw
    .replace(/file:\/\/\/(?:Volumes|Users|private|var|tmp|Applications)\/[^"'\]\}\n\r;,]+/gi, "[local path hidden]")
    .replace(/\/(?:Volumes|Users|private|var|tmp|Applications)\/[^"'\]\}\n\r;,]+/g, "[local path hidden]")
    .replace(/\b(?:authorization\s*:\s*bearer|api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*[^\s,;"'}]+/gi, "[credential hidden]")
    .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, "[credential hidden]");
}

function failureCopy(error: unknown): FailureCopy {
  const raw = rawFailure(error);
  const lower = raw.toLowerCase();
  const technical = raw ? redactTechnicalDetail(raw) : "";
  if (lower.includes("pypdf") || lower.includes("pdfreader") || lower.includes("pdf extraction")) {
    return { summary: "One or more filings could not be read.", nextAction: "Retry extraction; if it fails again, open the source and confirm that the PDF is readable.", technical };
  }
  if ((lower.includes("timeoutexpired") || lower.includes("timed out")) && (lower.includes("chrome") || lower.includes("print-to-pdf") || lower.includes("report"))) {
    return { summary: "The research pack was saved, but PDF export timed out.", nextAction: "Retry report export; completed analysis remains available.", technical };
  }
  if (lower.includes("postgres") || lower.includes("psycopg") || lower.includes("sqlstate") || lower.includes("relation does not exist")) {
    return { summary: "The research record could not be refreshed.", nextAction: "Retry once, then open System Health if the problem repeats.", technical };
  }
  if (lower.includes("unauthorized") || lower.includes("forbidden") || lower.includes("csrf") || /\b(?:401|403)\b/.test(lower)) {
    return { summary: "Your session could not authorize this action.", nextAction: "Refresh the page and retry; sign in again if the problem repeats.", technical };
  }
  if (lower.includes("network") || lower.includes("fetch") || lower.includes("http") || lower.includes("source")) {
    return { summary: "The public source could not be reached.", nextAction: "Check the source link, then retry the bounded request.", technical };
  }
  return { summary: "This research request did not finish.", nextAction: "Retry it; saved research and completed steps remain preserved.", technical };
}

function failureToast(error: unknown): string {
  const copy = failureCopy(error);
  return copy.summary + " " + copy.nextAction;
}

function ResearchShell(props: { eyebrow: string; title: string; description: string; command?: React.ReactNode; children: React.ReactNode }) {
  return (
    <main className="rd-page">
      <style>{ResearchDeskCss}</style>
      <header className={"rd-hero " + (props.command ? "" : "rd-hero--single")}>
        <div>
          <span className="rd-eyebrow">{props.eyebrow}</span>
          <h1>{props.title}</h1>
          <p>{props.description}</p>
        </div>
        {props.command}
      </header>
      <ResearchDeskNav />
      <div className="rd-safety">
        <span><ShieldCheck size={13} /> Durable research truth</span>
        <span>Public-source agents only after explicit start</span>
        <span>Private artifacts remain on Devarsh SSD</span>
        <span>No broker, client, external write or capital action</span>
      </div>
      {props.children}
    </main>
  );
}

function QueryState(props: { loading: boolean; fetching?: boolean; error: unknown; hasData: boolean; label: string; onRetry: () => unknown }) {
  if (props.loading && !props.hasData) {
    return <div className="rd-skeletons" aria-label={"Loading " + props.label}><Skeleton /><Skeleton /><Skeleton /></div>;
  }
  if (props.error && !props.hasData) {
    const copy = failureCopy(props.error);
    return (
      <div className="rd-state rd-state--error" role="alert">
        <AlertTriangle size={19} />
        <div><strong>{props.label} did not load</strong><p>{copy.summary} {copy.nextAction}</p><button onClick={props.onRetry}>Retry bounded request</button>{copy.technical ? <details className="rd-inline-detail"><summary>Technical detail</summary><code>{copy.technical}</code></details> : null}</div>
      </div>
    );
  }
  if (props.fetching) return <span className="rd-refresh"><LoaderCircle size={12} /> Refreshing</span>;
  return null;
}

function launchResearchCommand(raw: string, queue: (message: string) => void, setScope: (scope: "charlie") => void) {
  const request = raw.trim();
  if (!request) return;
  setScope("charlie");
  queue(/^start\b/i.test(request) ? request : "Start long-term research on " + request);
}

export function ResearchDeskHome() {
  const casesQuery = useResearchCases({ page: 1, pageSize: 8, refetchInterval: false });
  const monitoringQuery = useResearchMonitoring(1, 6);
  const updatesQuery = useResearchUpdates({ scope: "decision_required", status: "new", page: 1, pageSize: 6 });
  const queue = useUIStore((state) => state.queueAssistantMessage);
  const setScope = useUIStore((state) => state.setAssistantScope);
  const pushToast = useUIStore((state) => state.pushToast);
  const [request, setRequest] = React.useState("");
  const cases = casesQuery.data?.cases ?? [];
  const companies = monitoringQuery.data?.companies ?? [];
  const updates = updatesQuery.data?.items ?? [];
  const running = cases.filter((row) => ["active", "collecting", "running"].includes(text(row, "status").toLowerCase()));
  const attention = cases.filter((row) => ["blocked", "proposed", "review"].includes(text(row, "status").toLowerCase()));
  const caseTotal = num(casesQuery.data?.pagination as unknown as LiveRow, "total", cases.length);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!request.trim()) {
      pushToast({ title: "Add a company or question", message: "Enter a company name, ticker, or investment question so Charlie can prepare the research plan.", tone: "warn", duration: 4500 });
      return;
    }
    launchResearchCommand(request, queue, setScope);
    pushToast({ title: "Research request sent to Charlie", message: "Review the resolved company, source boundary and estimated cost in Charlie, then explicitly approve Start.", tone: "ok", duration: 6000 });
    setRequest("");
  }

  return (
    <ResearchShell
      eyebrow="Company research"
      title="One desk from question to decision-ready company pack."
      description="Start in natural language, approve the bounded plan, then track official-source collection, specialist analysis, independent review, the company dashboard and final report without hunting through system screens."
      command={<form className="rd-command" onSubmit={submit}><Search size={18} /><input value={request} onChange={(event) => setRequest(event.target.value)} aria-label="Company, ticker, or research question" placeholder="Company, ticker, or investment question…" required /><button type="submit"><Sparkles size={15} /> Review research plan</button></form>}
    >
      <div className="rd-body">
        <section className="rd-section" aria-label="Research desk status">
          <div className="rd-metrics">
            <div className="rd-metric"><span>Durable cases</span><strong>{caseTotal}</strong><small>stored research mandates</small></div>
            <div className="rd-metric"><span>Running</span><strong>{running.length}</strong><small>collection or analysis active</small></div>
            <div className={"rd-metric " + (attention.length ? "is-attention" : "")}><span>Your action</span><strong>{attention.length}</strong><small>start, repair or review</small></div>
            <div className="rd-metric"><span>Following</span><strong>{companies.length}</strong><small>in this bounded page</small></div>
          </div>
        </section>
      </div>
      <div className="rd-body rd-body--two">
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Workstreams</span><h2>Research requiring attention</h2><p>Blocked work stays separate from completed analysis; proposed cases still require explicit approval.</p></div><Link to="/research/cases">Open all <ArrowRight size={13} /></Link></header>
          <QueryState loading={casesQuery.isLoading} fetching={casesQuery.isFetching && Boolean(casesQuery.data)} error={casesQuery.error} hasData={Boolean(casesQuery.data)} label="Research workstreams" onRetry={() => casesQuery.refetch()} />
          {casesQuery.data && !attention.length ? <div className="rd-state"><Workflow size={19} /><div><strong>No case needs your action</strong><p>Running and completed work remains available in Workstreams.</p></div></div> : null}
          <div className="rd-list">{attention.slice(0, 6).map((row) => <Link className="rd-row" key={num(row, "id")} to={"/research/cases?case_id=" + num(row, "id")}><div><div className="rd-row__meta"><span>{text(row, "exchange")}:{text(row, "ticker")}</span><span>Case #{num(row, "id")}</span></div><h3>{text(row, "company_name")}</h3><p>{text(row, "next_action", text(row, "mandate"))}</p></div><div className="rd-row__aside"><StatusPill status={text(row, "status")} /><span>{formatRelative(text(row, "updated_at"))}</span></div></Link>)}</div>
        </section>
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Following</span><h2>Material company changes</h2><p>Only decision-impacting sourced changes appear here.</p></div><Link to="/research/following">Open feed <ArrowRight size={13} /></Link></header>
          <QueryState loading={updatesQuery.isLoading} fetching={updatesQuery.isFetching && Boolean(updatesQuery.data)} error={updatesQuery.error} hasData={Boolean(updatesQuery.data)} label="Company updates" onRetry={() => updatesQuery.refetch()} />
          {updatesQuery.data && !updates.length ? <div className="rd-state"><Radio size={19} /><div><strong>No new decision-impacting change</strong><p>The monitor has not recorded a new qualified filing or thesis change in this page.</p></div></div> : null}
          <div className="rd-list">{updates.map((row, index) => <a className="rd-row" key={text(row, "update_key", String(index))} href={text(row, "thesis_href", text(row, "case_href", "/research/following"))}><div><div className="rd-row__meta"><span>{text(row, "exchange")}:{text(row, "symbol")}</span><span>{text(row, "materiality", "unrated")}</span></div><h3>{text(row, "title", text(row, "update_type", "Research update"))}</h3><p>{text(row, "summary", "Open the linked company record for the qualified source and decision history.")}</p></div><div className="rd-row__aside"><StatusPill status={text(row, "decision_impact", text(row, "status"))} /><span>{formatRelative(text(row, "effective_at", text(row, "captured_at")))}</span></div></a>)}</div>
        </section>
      </div>
    </ResearchShell>
  );
}

export function ResearchFollowing() {
  const [page, setPage] = React.useState(1);
  const [status, setStatus] = React.useState("new");
  const [materiality, setMateriality] = React.useState("");
  const [sourceName, setSourceName] = React.useState("");
  const [sourceUrl, setSourceUrl] = React.useState("");
  const [sourceReason, setSourceReason] = React.useState("");
  const [sourceConfirmed, setSourceConfirmed] = React.useState(false);
  const monitoring = useResearchMonitoring(page, 20);
  const updates = useResearchUpdates({ scope: "followed", status, materiality, page, pageSize: 20 });
  const followed = useResearchFollowingSources(0, 30);
  const followSource = useFollowResearchSource();
  const refreshSource = useRefreshResearchSource();
  const pushToast = useUIStore((state) => state.pushToast);
  const companies = monitoring.data?.companies ?? [];
  const items = updates.data?.items ?? [];
  const sources = followed.data?.sources ?? [];
  const sourceItems = followed.data?.items ?? [];
  const quarantine = followed.data?.quarantine ?? [];
  const pages = num(monitoring.data?.pagination, "pages", 1);

  function submitSource(event: React.FormEvent) {
    event.preventDefault();
    if (!sourceConfirmed) return;
    followSource.mutate({
      feed_name: sourceName.trim(), provider: sourceName.trim(), url: sourceUrl.trim(),
      followed_reason: sourceReason.trim(), topics: ["public_equity_research"], refresh_minutes: 60,
      operator_confirmed: true,
    }, {
      onSuccess: () => {
        setSourceName(""); setSourceUrl(""); setSourceReason(""); setSourceConfirmed(false);
        pushToast({ title: "Source followed", message: "The public RSS/Atom source is stored locally and ready for a bounded refresh.", tone: "ok", duration: 4200 });
      },
      onError: (error) => pushToast({ title: "Source not followed", message: failureToast(error), tone: "risk", duration: 6000 }),
    });
  }

  return (
    <ResearchShell eyebrow="Ongoing coverage" title="Following" description="Every followed company keeps its latest qualified filing, thesis change, catalyst, risk, freshness and decision impact attached to one durable history.">
      <div className="rd-body">
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Approved public sources</span><h2>Follow a source without losing provenance</h2><p>Only a public HTTPS RSS or Atom URL is accepted. The stack stores metadata and a bounded permitted excerpt, quarantines prompt-like content, and requires corroboration before investment use.</p></div><QueryState loading={followed.isLoading} fetching={followed.isFetching && Boolean(followed.data)} error={followed.error} hasData={Boolean(followed.data)} label="Followed sources" onRetry={() => followed.refetch()} /></header>
          <form className="rd-source-form" onSubmit={submitSource}>
            <label>Source or author<input value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="Firm, newsletter or public author" required minLength={3} /></label>
            <label>Public RSS / Atom URL<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://…/feed" required /></label>
            <label className="rd-source-form__wide">Why follow it?<input value={sourceReason} onChange={(event) => setSourceReason(event.target.value)} placeholder="What company, sector or thesis should this inform?" required /></label>
            <label className="rd-check rd-source-form__wide"><input type="checkbox" checked={sourceConfirmed} onChange={(event) => setSourceConfirmed(event.target.checked)} /> I approve bounded public GET collection from this exact URL. No login, posting, messaging or broker action.</label>
            <button type="submit" disabled={!sourceConfirmed || followSource.isPending}>{followSource.isPending ? <LoaderCircle size={13} /> : <Radio size={13} />} Follow source</button>
          </form>
          {followed.data && !sources.length ? <div className="rd-state"><Radio size={19} /><div><strong>No public sources are followed yet</strong><p>Add an exact RSS/Atom URL above; plain profile pages are deliberately not scraped.</p></div></div> : null}
          <div className="rd-source-grid">{sources.map((row) => { const refreshStatus = text(row, "latest_refresh_status", text(row, "status", "ready")); const refreshFailed = refreshStatus === "failed"; const refreshFailure = failureCopy(text(row, "latest_error_message")); return <article className="rd-source-card" key={num(row, "id")}><div><strong>{text(row, "source_key")}</strong><span>{text(row, "source_type", "public feed").replace(/_/g, " ")} · {text(row, "trust_tier", "unrated")}</span></div><p>{text(row, "followed_reason", "Operator-confirmed public research source")}</p><div className="rd-row__meta"><Badge tone={refreshFailed ? "risk" : toneFor(refreshStatus)}>{refreshStatus.replace(/_/g, " ")}</Badge><span>{num(row, "latest_items_upserted")} latest items</span>{num(row, "latest_quarantined_items") ? <span>{num(row, "latest_quarantined_items")} quarantined</span> : null}</div>{refreshFailed ? <details className="rd-inline-detail"><summary>Why the refresh failed</summary><p>{refreshFailure.summary} {refreshFailure.nextAction}</p>{refreshFailure.technical ? <details><summary>Technical detail</summary><code>{refreshFailure.technical}</code></details> : null}</details> : null}<a href={text(row, "source_url")} target="_blank" rel="noreferrer">Open source <ExternalLink size={11} /></a><footer><span>Last refresh {formatRelative(text(row, "last_refresh_at"))}</span><button disabled={refreshSource.isPending} onClick={() => refreshSource.mutate({ followed_source_id: num(row, "id") }, { onSuccess: () => pushToast({ title: "Source refreshed", message: "New permitted items and quarantine results are stored locally.", tone: "ok", duration: 4200 }), onError: (error) => pushToast({ title: "Refresh failed", message: failureToast(error), tone: "risk", duration: 6000 }) })}><RefreshCw size={12} /> Refresh now</button></footer></article>; })}</div>
          {quarantine.length ? <details className="rd-method"><summary><AlertTriangle size={14} /> {quarantine.length} captured item{quarantine.length === 1 ? "" : "s"} require safe-content review</summary><div className="rd-list">{quarantine.map((row) => <article className="rd-row" key={num(row, "id")}><div><h3>{text(row, "title")}</h3><p>{text(row, "quarantine_status").replace(/_/g, " ")} · injection check {text(row, "prompt_injection_status")}</p></div><div className="rd-row__aside"><span>{text(row, "source_key")}</span><span>{formatRelative(text(row, "captured_at"))}</span></div></article>)}</div></details> : null}
          {sourceItems.length ? <details className="rd-method"><summary><BookOpen size={14} /> Latest permitted source captures ({sourceItems.length})</summary><div className="rd-list">{sourceItems.slice(0, 20).map((row, index) => <article className="rd-row" key={text(row, "item_key", String(index))}><div><h3>{text(row, "title")}</h3><p>{text(row, "permitted_excerpt", "No excerpt was permitted; use the original source link.")}</p></div><div className="rd-row__aside"><span>{text(row, "source_key")}</span><span>{formatRelative(text(row, "published_at", text(row, "captured_at")))}</span>{text(row, "canonical_url") ? <a className="rd-link" href={text(row, "canonical_url")} target="_blank" rel="noreferrer">Source</a> : null}</div></article>)}</div></details> : null}
        </section>
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Company monitor</span><h2>Followed companies</h2><p>Latest material state from the governed monitoring read model.</p></div><QueryState loading={monitoring.isLoading} fetching={monitoring.isFetching && Boolean(monitoring.data)} error={monitoring.error} hasData={Boolean(monitoring.data)} label="Following monitor" onRetry={() => monitoring.refetch()} /></header>
          {monitoring.data && !companies.length ? <div className="rd-state"><Radio size={19} /><div><strong>No followed companies in this page</strong><p>Follow a company from its dashboard after its identity is verified.</p></div></div> : null}
          <div className="rd-follow-grid">{companies.map((row, index) => <article className="rd-follow-card" key={text(row, "symbol", String(index))}><div className="rd-follow-card__top"><div><strong>{text(row, "symbol")}</strong><span>{text(row, "company_name", text(row, "legal_name"))}</span></div><Badge tone={toneFor(text(row, "latest_update_materiality", text(row, "priority")))}>{text(row, "latest_update_materiality", text(row, "priority", "monitored"))}</Badge></div><p>{text(row, "latest_update_title", "No new material update is recorded for this company.")}</p><div className="rd-row__meta"><span>{text(row, "latest_update_decision_impact", "no decision change")}</span><span>{formatRelative(text(row, "latest_update_at", text(row, "last_progress_at")))}</span><span>{num(row, "new_update_count")} new</span></div><div className="rd-follow-card__links"><a href={text(row, "thesis_href", "/fundamental/theses?symbol=" + encodeURIComponent(text(row, "symbol")))}>Company dashboard</a>{text(row, "case_href") ? <a href={text(row, "case_href")}>Workstream</a> : null}{text(row, "latest_update_source_url") ? <a href={text(row, "latest_update_source_url")} target="_blank" rel="noreferrer">Primary source <ExternalLink size={11} /></a> : null}</div></article>)}</div>
          <div className="rd-pages"><button disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button><span>Page {page} of {Math.max(1, pages)}</span><button disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button></div>
        </section>
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Change ledger</span><h2>Sourced update history</h2><p>Filtered independently from the company monitor; empty means no matching governed update, not no news on the internet.</p></div><QueryState loading={updates.isLoading} fetching={updates.isFetching && Boolean(updates.data)} error={updates.error} hasData={Boolean(updates.data)} label="Update history" onRetry={() => updates.refetch()} /></header>
          <div className="rd-filterbar"><label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="new">New</option><option value="reviewed">Reviewed</option><option value="dismissed">Dismissed</option><option value="all">All</option></select></label><label>Materiality<select value={materiality} onChange={(event) => { setMateriality(event.target.value); setPage(1); }}><option value="">All</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label></div>
          {updates.data && !items.length ? <div className="rd-state"><BookOpen size={19} /><div><strong>No matching governed updates</strong><p>Change the filters or wait for a qualified source capture.</p></div></div> : null}
          <div className="rd-list">{items.map((row, index) => <article className="rd-row" key={text(row, "update_key", String(index))}><div><div className="rd-row__meta"><span>{text(row, "exchange")}:{text(row, "symbol")}</span><span>{text(row, "source_kind", text(row, "update_type"))}</span></div><h3>{text(row, "title")}</h3><p>{text(row, "summary", "No accepted summary was stored; open the source and linked company record.")}</p></div><div className="rd-row__aside"><Badge tone={toneFor(text(row, "materiality"))}>{text(row, "materiality", "unrated")}</Badge><span>{formatRelative(text(row, "effective_at", text(row, "captured_at")))}</span>{text(row, "source_url") ? <a className="rd-link" href={text(row, "source_url")} target="_blank" rel="noreferrer">Source <ExternalLink size={11} /></a> : <span>Source link unavailable</span>}</div></article>)}</div>
        </section>
      </div>
    </ResearchShell>
  );
}

export function FundamentalScanners() {
  const scan = useFundamentalScanner();
  const createScanner = useCreateFundamentalScanner();
  const scannerAction = useScannerAction();
  const openEvidence = useUIStore((state) => state.openEvidence);
  const pushToast = useUIStore((state) => state.pushToast);
  const [instruction, setInstruction] = React.useState("Find NSE and BSE companies with 5-year revenue CAGR above 12, ROCE above 15, debt to equity below 0.5, and coverage above 80");
  const [pendingApprovals, setPendingApprovals] = React.useState<Record<number, number>>({});
  const scanners = scan.data?.items ?? [];

  function create(event: React.FormEvent) {
    event.preventDefault();
    createScanner.mutate({ instruction, name: "My fundamental quality screen" }, {
      onSuccess: () => pushToast({ title: "Scanner draft created", message: "Review its exact metrics, validation coverage and exclusions before publication.", tone: "ok", duration: 4500 }),
      onError: (error) => pushToast({ title: "Scanner draft rejected", message: failureToast(error), tone: "risk", duration: 6000 }),
    });
  }

  function act(scannerId: number, action: "validate" | "publish-request" | "publish" | "run") {
    const approvalId = pendingApprovals[scannerId];
    scannerAction.mutate({ scannerId, action, payload: action === "publish" ? { approval_id: approvalId } : {} }, {
      onSuccess: (result) => {
        if (action === "publish-request") {
          const approval = (result.approval ?? {}) as LiveRow;
          const id = num(approval, "id");
          if (id) {
            setPendingApprovals((current) => ({ ...current, [scannerId]: id }));
            openEvidence({ kind: "approval", key: String(id), title: "Approve fundamental scanner publication", subtitle: "Read-only deterministic screen" });
          }
        }
        pushToast({ title: action.replace(/-/g, " "), message: action === "publish-request" ? "Approval opened. Publication remains blocked until you explicitly approve it." : "The governed scanner state was updated.", tone: "ok", duration: 4500 });
      },
      onError: (error) => pushToast({ title: "Scanner action blocked", message: failureToast(error), tone: "risk", duration: 6500 }),
    });
  }

  return (
    <ResearchShell eyebrow="Fundamental discovery" title="Fundamental scanners" description="Build an auditable point-in-time screen in plain English, inspect the resolved formula and coverage, explicitly publish it, then run it against the stored NSE/BSE universe. Missing facts exclude a company and stay visible.">
      <div className="rd-body">
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Scanner builder</span><h2>Describe the companies you want to find</h2><p>The parser accepts only the displayed deterministic metric library. Unsupported requirements are returned as gaps, never silently approximated.</p></div><QueryState loading={scan.isLoading} fetching={scan.isFetching && Boolean(scan.data)} error={scan.error} hasData={Boolean(scan.data)} label="Scanner catalog" onRetry={() => scan.refetch()} /></header>
          <form className="rd-scanner-builder" onSubmit={create}><label>Plain-English screen<textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={3} /></label><button type="submit" disabled={createScanner.isPending}>{createScanner.isPending ? <LoaderCircle size={14} /> : <Sparkles size={14} />} Create reviewable draft</button></form>
          <div className="rd-formula-strip"><span>Available now</span><code>Revenue CAGR 5y</code><code>PAT CAGR 5y</code><code>ROCE proxy</code><code>ROE</code><code>CFO/PAT</code><code>Margins</code><code>D/E</code><code>Interest cover</code><code>DSO</code><code>Asset turns</code><code>Governance flags</code></div>
          {scan.data && !scanners.length ? <div className="rd-state"><Radar size={19} /><div><strong>No scanner is stored</strong><p>Create a draft above. Nothing runs or publishes until its separate gates are satisfied.</p></div></div> : null}
          <div className="rd-scan-list">{scanners.map((row) => { const scannerId = num(row, "id"); const versionStatus = text(row, "version_status", text(row, "status")); const validations = (row.validation_summary ?? {}) as Record<string, unknown>; return <article className="rd-scan rd-scan--workflow" key={scannerId}><div className="rd-scan__head"><div><strong>{text(row, "name")}</strong><span>v{num(row, "version", 1)} · {text(row, "scope_key") === "global:public" ? "template" : "your workspace"}</span></div><Badge tone={toneFor(versionStatus)}>{versionStatus.replace(/_/g, " ")}</Badge></div><p>{text(row, "description", "No description stored.")}</p><div className="rd-validation-line">{["schema", "metric_availability", "point_in_time", "known_fixture"].map((kind) => <span key={kind} className={String(validations[kind] ?? "pending") === "passed" ? "is-pass" : ""}>{kind.replace(/_/g, " ")}: {String(validations[kind] ?? "pending")}</span>)}</div><footer><span>{num(row, "run_count")} durable run{num(row, "run_count") === 1 ? "" : "s"} · last {formatRelative(text(row, "last_run_as_of"))}</span><span className="rd-actions">{versionStatus === "draft" ? <button onClick={() => act(scannerId, "validate")} disabled={scannerAction.isPending}>Validate</button> : null}{versionStatus === "validated" && !pendingApprovals[scannerId] ? <button onClick={() => act(scannerId, "publish-request")} disabled={scannerAction.isPending}>Request publication</button> : null}{versionStatus === "validated" && pendingApprovals[scannerId] ? <><button onClick={() => openEvidence({ kind: "approval", key: String(pendingApprovals[scannerId]), title: "Scanner publication approval" })}>Review approval</button><button onClick={() => act(scannerId, "publish")} disabled={scannerAction.isPending}>Publish after approval</button></> : null}{versionStatus === "published" ? <button onClick={() => act(scannerId, "run")} disabled={scannerAction.isPending}>Run point-in-time screen</button> : null}</span></footer></article>; })}</div>
        </section>
      </div>
    </ResearchShell>
  );
}

export function ResearchKnowledge() {
  const [draft, setDraft] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [family, setFamily] = React.useState("");
  const [page, setPage] = React.useState(1);
  const knowledge = useResearchKnowledge({ page, pageSize: 40, query, family });
  const openEvidence = useUIStore((state) => state.openEvidence);
  const data = knowledge.data;
  const families = React.useMemo(() => Array.from(new Set((data?.nodes ?? []).map((row) => text(row, "node_type")).filter(Boolean))).sort(), [data]);
  const nodes = data?.nodes ?? [];
  const notes = data?.notes ?? [];
  const lineage = (data?.edges ?? []).slice(0, 40);
  const unresolved = data?.unresolved_links ?? [];
  const hasNext = data?.page?.next_cursor != null;

  function submit(event: React.FormEvent) { event.preventDefault(); setPage(1); setQuery(draft.trim()); }

  return (
    <ResearchShell eyebrow="Durable memory" title="Knowledge" description="Search the scoped company, case and Obsidian knowledge graph without exporting private notes. The database stores provenance and graph truth; Qdrant remains local retrieval and Obsidian remains the human-readable memory surface.">
      <div className="rd-body rd-body--two">
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Scoped graph</span><h2>Companies, cases and durable notes</h2><p>A bounded 40-node page. Private text is summarized locally and never sent by this view.</p></div><QueryState loading={knowledge.isLoading} fetching={knowledge.isFetching && Boolean(data)} error={knowledge.error} hasData={Boolean(data)} label="Knowledge graph" onRetry={() => knowledge.refetch()} /></header>
          <form className="rd-filterbar" onSubmit={submit}><label>Search<input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Company, case, note or concept" /></label><label>Node type<select value={family} onChange={(event) => { setFamily(event.target.value); setPage(1); }}><option value="">All types</option>{families.map((item) => <option key={item} value={item}>{item.replace(/_/g, " ")}</option>)}</select></label><button type="submit"><Search size={13} /> Search</button></form>
          {data && !nodes.length && !notes.length ? <div className="rd-state"><Library size={19} /><div><strong>No matching scoped knowledge</strong><p>Change the search or run the incremental local indexer. No placeholder nodes were generated.</p></div></div> : null}
          <div className="rd-knowledge-list">{nodes.map((row) => <article className="rd-artifact" key={num(row, "id")}><div><h3>{text(row, "label")}</h3><p>{text(row, "node_type").replace(/_/g, " ")} from {text(row, "source_schema", "governed graph")}.{text(row, "source_table")}</p><div className="rd-artifact__meta"><span>{text(row, "authority")}</span><span>{text(row, "privacy_class").replace(/_/g, " ")}</span><span>available {formatRelative(text(row, "available_at"))}</span><span>updated {formatRelative(text(row, "updated_at"))}</span></div></div><button onClick={() => openEvidence({ kind: text(row, "node_type", "knowledge"), key: text(row, "source_pk", text(row, "node_key")), title: text(row, "label", "Knowledge record") })}>Open record</button></article>)}</div>
          {notes.length ? <details className="rd-method"><summary><BookOpen size={14} /> Human-readable Obsidian memory ({notes.length})</summary><div className="rd-knowledge-list">{notes.map((row) => <article className="rd-artifact" key={num(row, "id")}><div><h3>{text(row, "title")}</h3><p>{text(row, "body_summary", "No summary is stored for this note.")}</p><div className="rd-artifact__meta"><span>{text(row, "note_path")}</span><span>{text(row, "privacy_class").replace(/_/g, " ")}</span><span>{formatRelative(text(row, "last_modified_at"))}</span></div></div></article>)}</div></details> : null}
          <div className="rd-pages"><button disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button><span>Page {page}</span><button disabled={!hasNext} onClick={() => setPage((value) => value + 1)}>Next</button></div>
        </section>
        <section className="rd-section">
          <header className="rd-section__head"><div><span className="rd-kicker">Lineage</span><h2>How this page connects</h2><p>Deterministic database and Obsidian relationships only; agent hypotheses require their own cited artifact.</p></div><Badge>{lineage.length}</Badge></header>
          {data && !lineage.length ? <div className="rd-state"><FileText size={19} /><div><strong>No graph edge touches this page</strong><p>Nodes remain searchable; no relationship was fabricated.</p></div></div> : <div className="rd-lineage">{lineage.map((row, index) => <article key={text(row, "id", String(index))}><div><strong>{text(row, "from_label", "Source")} → {text(row, "to_label", "Target")}</strong><span>{text(row, "edge_type", "linked").replace(/_/g, " ")}</span></div><span>{text(row, "source_kind").replace(/_/g, " ")} · {formatRelative(text(row, "available_at"))}</span></article>)}</div>}
          {unresolved.length ? <details className="rd-method"><summary><AlertTriangle size={14} /> {unresolved.length} unresolved Obsidian link{unresolved.length === 1 ? "" : "s"}</summary><div className="rd-lineage">{unresolved.map((row) => <article key={num(row, "id")}><div><strong>{text(row, "raw_target")}</strong><span>{text(row, "reason")}</span></div><span>seen {formatRelative(text(row, "last_seen_at"))} · {num(row, "occurrence_count", 1)} occurrence(s)</span></article>)}</div></details> : null}
        </section>
      </div>
    </ResearchShell>
  );
}
