import {
  Activity,
  BarChart3,
  Bot,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  Inbox,
  Newspaper,
  MessageSquareText,
  RefreshCw,
  ShieldCheck,
  Workflow
} from "lucide-react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  materializeDashboardWidgets,
  runAgentWorker,
  sendChat,
  type LiveRow
} from "../api/live";
import { fetchMissionControlSnapshot, type MissionControlSnapshot } from "../api/missionControl";
import type { EvidenceSelection } from "../api/evidence";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";

interface MissionControlWorkspaceProps {
  onStatusChange: (status: ConnectionStatus) => void;
}

function text(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const value = row?.[key];
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "object") {
    if (Array.isArray(value)) return value.map(String).join(", ") || fallback;
    return Object.entries(value)
      .map(([label, detail]) => `${label.replace(/_/g, " ")}: ${String(detail)}`)
      .join(" · ") || fallback;
  }
  return String(value);
}

function date(value: unknown): string {
  if (!value) return "not recorded";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["active", "approved", "completed", "done", "online", "ready", "passed", "fresh", "locked"].includes(normalized)) return "active";
  if (["blocked", "failed", "error", "rejected", "critical", "stale"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function MissionPanel({
  action,
  children,
  className,
  icon,
  title
}: {
  action?: ReactNode;
  children: ReactNode;
  className: string;
  icon: ReactNode;
  title: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>{icon}<h2>{title}</h2></div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export default function MissionControlWorkspace({ onStatusChange }: MissionControlWorkspaceProps) {
  const [snapshot, setSnapshot] = useState<MissionControlSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatRoute, setChatRoute] = useState<"local" | "fast" | "deep" | "review">("local");
  const [widgetBusy, setWidgetBusy] = useState(false);
  const [workerBusy, setWorkerBusy] = useState(false);
  const [evidenceSelection, setEvidenceSelection] = useState<EvidenceSelection | null>(null);

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchMissionControlSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mission Control API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:mission-control-refresh", handleRefresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("aios:mission-control-refresh", handleRefresh);
    };
  }, [refresh]);

  const submitChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatDraft.trim();
    if (!message || chatBusy) return;
    setChatDraft("");
    setChatBusy(true);
    setError("");
    try {
      const cloudRoute = chatRoute === "fast"
        ? "openrouter_research_fast"
        : chatRoute === "deep"
          ? "openrouter_research_deep"
          : "openrouter_research_review";
      const useCloud = chatRoute !== "local";
      await sendChat({
        actor: "Devarsh", message,
        metadata: { workspace: "command", source_surface: "mission_control", requested_mode: chatRoute },
        session_key: "ai-office-default", workspace: "command",
        route_name: useCloud ? cloudRoute : undefined,
        include_client_context: !useCloud,
        privacy_class: useCloud ? "internal" : "client_private",
        contains_client_data: !useCloud,
        cloud_approved: useCloud
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Charlie chat failed");
    } finally {
      setChatBusy(false);
    }
  };

  const materializeWidgets = async () => {
    if (widgetBusy) return;
    setWidgetBusy(true);
    setError("");
    try {
      await materializeDashboardWidgets({ actor: "Jarvis", limit: 20, session_key: "ai-office-default" });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Widget materialization failed");
    } finally {
      setWidgetBusy(false);
    }
  };

  const runWorkers = async () => {
    if (workerBusy) return;
    setWorkerBusy(true);
    setError("");
    try {
      await runAgentWorker({ actor: "Jarvis", limit: 5 });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Agent worker run failed");
    } finally {
      setWorkerBusy(false);
    }
  };

  const openInbox = snapshot?.inbox.filter((row) => !["done", "resolved", "closed"].includes(text(row, "status", "").toLowerCase())) ?? [];
  const pendingApprovals = snapshot?.approvals.filter((row) => text(row, "status", "") === "pending") ?? [];
  const openTasks = snapshot?.tasks.filter((row) => !["completed", "done", "cancelled"].includes(text(row, "status", "").toLowerCase())) ?? [];
  const blockedGates = snapshot?.task_provider_gates.filter((row) => text(row, "provider_gate_status", "") !== "passed") ?? [];
  const sourceIssues = snapshot?.source_freshness.filter((row) => text(row, "status", "fresh") !== "fresh") ?? [];
  const execution = snapshot?.execution_control[0];
  const latestBrief = snapshot?.chat_turns[0];
  const filingSummary = snapshot?.filing_summary[0];
  const delegatedCount = useMemo(
    () => snapshot?.agent_messages.filter((row) => text(row, "from_agent", "") === "Charlie Munger" && Boolean(row.generated_task_id)).length ?? 0,
    [snapshot]
  );

  const evidenceRow = (selection: EvidenceSelection) => ({
    className: "source-check-row evidence-open-row",
    onClick: () => setEvidenceSelection(selection),
    onKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setEvidenceSelection(selection);
      }
    },
    role: "button" as const,
    tabIndex: 0
  });

  return (
    <div className="mission-control-workspace">
      <section className="metric-grid" aria-label="Mission Control operating metrics">
        <div className="metric-tile"><span>Scoped API</span><strong>{status === "online" ? "Online" : status}</strong><p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p></div>
        <div className="metric-tile"><span>Open Inbox</span><strong>{openInbox.length}</strong><p className={openInbox.length ? "tone-warn" : "tone-good"}>durable work queue</p></div>
        <div className="metric-tile"><span>Pending Approvals</span><strong>{pendingApprovals.length}</strong><p className={pendingApprovals.length ? "tone-warn" : "tone-good"}>human decisions</p></div>
        <div className="metric-tile"><span>Charlie Delegations</span><strong>{delegatedCount}</strong><p className="tone-neutral">recent generated tasks</p></div>
        <div className="metric-tile"><span>Corporate Filings</span><strong>{text(filingSummary, "filing_count", "0")}</strong><p className="tone-neutral">{text(filingSummary, "special_situation_count", "0")} special situations</p></div>
        <div className="metric-tile"><span>News / Watchlist</span><strong>{snapshot?.latest_news.length ?? 0} / {snapshot?.watchlist.length ?? 0}</strong><p className="tone-neutral">source-linked live rows</p></div>
        <div className="metric-tile"><span>Execution</span><strong>{text(execution, "global_execution_locked", "true") === "true" ? "Locked" : "Review"}</strong><p className="tone-good">broker writes {text(execution, "live_broker_writes_allowed", "false") === "true" ? "enabled" : "disabled"}</p></div>
      </section>

      <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status} />
      {error ? <div className="error-strip">{error}</div> : null}

      <section className="dashboard-grid">
        <MissionPanel
          action={<button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button" title="Refresh Mission Control"><RefreshCw size={14} />{status === "loading" ? "Checking" : "Refresh"}</button>}
          className="span-7"
          icon={<MessageSquareText size={17} />}
          title="Charlie Daily Brief"
        >
          {latestBrief ? (
            <div className="mission-brief">
              <p>{text(latestBrief, "assistant_message", "No brief response recorded.")}</p>
              <div className="row-footer"><StatusPill status={text(latestBrief, "model_status", "stored")} /><span>{text(latestBrief, "model_name", "route")} · {date(latestBrief.created_at)}</span></div>
            </div>
          ) : <Empty>No Charlie brief or chat turn has been recorded.</Empty>}
          <form className="chat-form mission-chat-form" onSubmit={submitChat}>
            <label><span>Reasoning route</span><select aria-label="Charlie model route" value={chatRoute} onChange={(event) => setChatRoute(event.target.value as typeof chatRoute)}><option value="local">Local private</option><option value="fast">Cloud fast - public/internal only</option><option value="deep">Cloud deep - public/internal only</option><option value="review">Independent cloud review</option></select></label>
            <textarea aria-label="Chat with Charlie in Mission Control" onChange={(event) => setChatDraft(event.target.value)} placeholder="Ask Charlie what changed, what needs approval, or which work to delegate..." rows={3} value={chatDraft} />
            <button className="primary-button" disabled={chatBusy} type="submit"><MessageSquareText size={15} />{chatBusy ? "Thinking" : "Ask Charlie"}</button>
          </form>
        </MissionPanel>

        <MissionPanel className="span-5" icon={<ShieldCheck size={17} />} title="Decision Gates">
          <div aria-label="Decision gates" className="source-check-list mission-list" tabIndex={0}>
            <article className="source-check-row"><div><strong>Global execution</strong><p>{text(execution, "lock_reason", "Safety state unavailable")}</p></div><StatusPill status={text(execution, "global_execution_locked", "true") === "true" ? "locked" : "review"} /><span>{text(execution, "broker_execution_policy", "gated")}</span><time>{date(execution?.updated_at)}</time></article>
            {blockedGates.slice(0, 8).map((gate) => (
              <article {...evidenceRow({ kind: "task", key: text(gate, "task_id"), title: text(gate, "title"), subtitle: "Provider decision gates", record: gate })} key={text(gate, "task_id")}><div><strong>{text(gate, "title")}</strong><p>{text(gate, "owner_agent")} · task {text(gate, "task_id")}</p></div><StatusPill status={text(gate, "provider_gate_status", "needs_review")} /><span>{text(gate, "blocked_provider_gates", "0")} blocked</span><time>{date(gate.latest_provider_gate_at)}</time></article>
            ))}
          </div>
        </MissionPanel>

        <MissionPanel className="span-6" icon={<Workflow size={17} />} title="Charlie Delegations" action={<span>{snapshot?.agent_messages.length ?? 0} recent</span>}>
          <div aria-label="Charlie delegations" className="source-check-list mission-list" tabIndex={0}>
            {snapshot?.agent_messages.map((message) => (
              <article {...evidenceRow({ kind: "agent_message", key: text(message, "id"), title: text(message, "subject"), subtitle: `${text(message, "from_agent")} to ${text(message, "to_agent")}`, record: message })} key={text(message, "id")}><div><strong>{text(message, "subject")}</strong><p>{text(message, "from_agent")} → {text(message, "to_agent")} · task {text(message, "generated_task_id", "-")}</p></div><StatusPill status={text(message, "processing_status", text(message, "status", "queued"))} /><span>#{text(message, "id")}</span><time>{date(message.created_at)}</time></article>
            )) ?? <Empty>No durable agent handoffs recorded.</Empty>}
          </div>
        </MissionPanel>

        <MissionPanel className="span-6" icon={<Inbox size={17} />} title="Executive Inbox" action={<span>{openInbox.length} open</span>}>
          <div aria-label="Executive inbox" className="source-check-list mission-list" tabIndex={0}>
            {openInbox.map((item) => (
              <article className="source-check-row" key={text(item, "id")}><div><strong>{text(item, "title")}</strong><p>{text(item, "recommended_action", "No next action")}</p></div><StatusPill status={text(item, "status", "open")} /><span>{text(item, "owner_agent")}</span><time>{date(item.updated_at)}</time></article>
            ))}
            {!openInbox.length ? <Empty>No open command inbox items.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-6" icon={<CheckCircle2 size={17} />} title="Approval Queue" action={<span>{pendingApprovals.length} pending</span>}>
          <div aria-label="Approval queue" className="source-check-list mission-list" tabIndex={0}>
            {snapshot?.approvals.map((approval) => (
              <article {...evidenceRow({ kind: "approval", key: text(approval, "id"), title: text(approval, "title"), subtitle: `${text(approval, "risk_level", "medium")} risk approval`, record: approval })} key={text(approval, "id")}><div><strong>{text(approval, "title")}</strong><p>{text(approval, "requested_action", text(approval, "rationale", "Decision required"))}</p></div><StatusPill status={text(approval, "status", "pending")} /><span>{text(approval, "risk_level", "medium")}</span><time>{date(approval.created_at)}</time></article>
            )) ?? <Empty>No approval records.</Empty>}
          </div>
        </MissionPanel>

        <MissionPanel className="span-6" icon={<BarChart3 size={17} />} title="Live Widgets" action={<button className="mini-action-button" disabled={widgetBusy} onClick={() => void materializeWidgets()} type="button">{widgetBusy ? "Working" : "Materialize"}</button>}>
          <div aria-label="Live widgets" className="source-check-list mission-list" tabIndex={0}>
            {snapshot?.dashboard_widgets.map((widget) => (
              <article className="source-check-row" key={text(widget, "id")}><div><strong>{text(widget, "widget_title")}</strong><p>{text(widget, "widget_type")} · {text(widget, "query_ref")}</p></div><StatusPill status={text(widget, "status", "active")} /><span>{text(widget, "task_status", "-")}</span><time>{date(widget.updated_at)}</time></article>
            ))}
            {!snapshot?.dashboard_widgets.length ? <Empty>No command widgets materialized.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-7" icon={<ClipboardList size={17} />} title="Agent Work Queue" action={<button className="mini-action-button" disabled={workerBusy} onClick={() => void runWorkers()} type="button"><Bot size={14} />{workerBusy ? "Running" : "Run workers"}</button>}>
          <div aria-label="Agent work queue" className="source-check-list mission-list" tabIndex={0}>
            {openTasks.slice(0, 16).map((task) => (
              <article {...evidenceRow({ kind: "task", key: text(task, "id"), title: text(task, "title"), subtitle: `${text(task, "owner_agent")} work item`, record: task })} key={text(task, "id")}><div><strong>{text(task, "title")}</strong><p>{text(task, "owner_agent")} · {text(task, "source_kind")}</p></div><StatusPill status={text(task, "status", "queued")} /><span>{text(task, "priority", "normal")}</span><time>{date(task.updated_at)}</time></article>
            ))}
            {!openTasks.length ? <Empty>No open agent tasks.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-7" icon={<FileText size={17} />} title="Filing Intelligence" action={<span>{snapshot?.filing_intelligence.length ?? 0} ranked</span>}>
          <div className="source-check-list mission-list">
            {snapshot?.filing_intelligence.map((filing) => {
              const href = text(filing, "attachment_url", text(filing, "source_url", ""));
              return <article className="source-check-row" key={text(filing, "filing_id")}><div><strong>{text(filing, "symbol", text(filing, "company_name"))} · {text(filing, "title")}</strong><p>{text(filing, "why_it_matters")} · {text(filing, "evidence_state")}</p></div><StatusPill status={text(filing, "priority", "normal")} /><span>{text(filing, "event_type", "filing")}</span>{href && href !== "-" ? <a className="icon-button" href={href} rel="noreferrer" target="_blank" title="Open exchange filing"><ExternalLink size={14} /></a> : <time>{date(filing.filed_at)}</time>}</article>;
            })}
            {!snapshot?.filing_intelligence.length ? <Empty>No filing intelligence rows returned.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-5" icon={<Newspaper size={17} />} title="What Matters Now" action={<span>{snapshot?.news_brief.length ?? 0} ranked</span>}>
          <div className="source-check-list mission-list">
            {snapshot?.news_brief.slice(0, 8).map((item) => <article className="source-check-row" key={text(item, "id")}><div><strong>{text(item, "title")}</strong><p>{text(item, "why_it_matters")}</p></div><StatusPill status={Number(item.materiality_score ?? 0) >= 0.8 ? "high" : "review"} /><span>{text(item, "matched_symbols", text(item, "owner_agent"))}</span><a className="icon-button" href={text(item, "source_url")} rel="noreferrer" target="_blank" title="Open news source"><ExternalLink size={14} /></a></article>)}
            {!snapshot?.news_brief.length ? <Empty>No ranked news items returned.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-7" icon={<CalendarDays size={17} />} title="Results & Event Calendar" action={<span>{snapshot?.market_events.length ?? 0} upcoming</span>}>
          <div className="source-check-list mission-list">
            {snapshot?.market_events.slice(0, 12).map((event) => <article className="source-check-row" key={[text(event, "symbol"), text(event, "event_date"), text(event, "purpose")].join("-")}><div><strong>{text(event, "symbol")} · {text(event, "purpose")}</strong><p>{text(event, "description")}</p></div><StatusPill status={text(event, "relevance_scope", "market")} /><span>{text(event, "event_date")}</span><a className="icon-button" href={text(event, "source_url")} rel="noreferrer" target="_blank" title="Open NSE event source"><ExternalLink size={14} /></a></article>)}
            {!snapshot?.market_events.length ? <Empty>No upcoming company events stored.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-5" icon={<CalendarDays size={17} />} title="Market Holidays" action={<span>{snapshot?.market_holidays.length ?? 0} upcoming</span>}>
          <div className="source-check-list mission-list">
            {snapshot?.market_holidays.map((holiday) => <article className="source-check-row" key={[text(holiday, "exchange"), text(holiday, "segment"), text(holiday, "holiday_date")].join("-")}><div><strong>{text(holiday, "holiday_name")}</strong><p>{text(holiday, "exchange")} · {text(holiday, "segment")}</p></div><StatusPill status={text(holiday, "session_status", "closed")} /><span>{text(holiday, "holiday_date")}</span><a className="icon-button" href={text(holiday, "source_url")} rel="noreferrer" target="_blank" title="Open official holiday circular"><ExternalLink size={14} /></a></article>)}
            {!snapshot?.market_holidays.length ? <Empty>No upcoming exchange holidays stored.</Empty> : null}
          </div>
        </MissionPanel>

        <MissionPanel className="span-7" icon={<Newspaper size={17} />} title="Daily Intelligence" action={<span>{snapshot?.latest_reports.length ?? 0} reports</span>}>
          <div className="source-check-list mission-list">{snapshot?.latest_reports.slice(0, 6).map((report) => <article className="source-check-row" key={text(report, "id")}><div><strong>{text(report, "report_name")}</strong><p>{text(report, "summary", "Source-backed report run")}</p></div><StatusPill status={text(report, "status", "queued")} /><span>{text(report, "output_note_path", "pending")}</span><time>{date(report.finished_at ?? report.started_at)}</time></article>)}{!snapshot?.latest_reports.length ? <Empty>The daily investment letter has not run yet.</Empty> : null}</div>
        </MissionPanel>

        <MissionPanel className="span-5" icon={<Activity size={17} />} title="Freshness Alerts" action={<span>{sourceIssues.length} issues</span>}>
          <div aria-label="Freshness alerts" className="source-check-list mission-list" tabIndex={0}>
            {sourceIssues.map((source) => (
              <article className="source-check-row" key={text(source, "source_key")}><div><strong>{text(source, "source_name", text(source, "source_key"))}</strong><p>{text(source, "staleness_minutes", "-")} minutes stale</p></div><StatusPill status={text(source, "status", "unknown")} /><span>{text(source, "severity", "medium")}</span><time>{date(source.created_at)}</time></article>
            ))}
            {!sourceIssues.length ? <Empty>No source freshness issues.</Empty> : null}
          </div>
        </MissionPanel>
      </section>
      <EvidenceDrawer onChanged={refresh} onClose={() => setEvidenceSelection(null)} selection={evidenceSelection} />
    </div>
  );
}
