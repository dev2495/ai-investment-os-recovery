import {
  AlertTriangle,
  CalendarClock,
  Clipboard,
  DatabaseZap,
  ExternalLink,
  FileCheck2,
  FileSearch,
  FileUp,
  History,
  PlayCircle,
  RefreshCw,
  ScrollText,
  Workflow
} from "lucide-react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import type { LiveRow } from "../api/live";
import { fetchReportsSnapshot, runScheduledReports, uploadLocalArtifact, type ReportsSnapshot } from "../api/reports";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";
interface Props { onStatusChange: (status: ConnectionStatus) => void; }

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (typeof raw === "object") {
    if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
    return Object.entries(raw).map(([label, detail]) => `${label.replace(/_/g, " ")}: ${String(detail)}`).join(" · ") || fallback;
  }
  return String(raw);
}

function date(raw: unknown): string {
  if (!raw) return "not recorded";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["active", "complete", "completed", "indexed", "linked", "ready", "stored"].includes(normalized)) return "active";
  if (["blocked", "critical", "error", "failed", "missing", "rejected"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) { return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>; }
function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) { return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>; }
function Empty({ children }: { children: ReactNode }) { return <div className="empty-state">{children}</div>; }

export default function ReportsWorkspace({ onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<ReportsSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("all");
  const [artifactStatus, setArtifactStatus] = useState("all");
  const [localFile, setLocalFile] = useState<File | null>(null);
  const [localFileInputKey, setLocalFileInputKey] = useState(0);
  const [localTitle, setLocalTitle] = useState("");
  const [localSensitivity, setLocalSensitivity] = useState<"public" | "internal" | "private" | "client_private" | "restricted">("private");
  const [localDestination, setLocalDestination] = useState("");
  const [localConfirmed, setLocalConfirmed] = useState(false);
  const [localIngesting, setLocalIngesting] = useState(false);
  const [reportBusy, setReportBusy] = useState("");
  const [evidenceSelection, setEvidenceSelection] = useState<EvidenceSelection | null>(null);

  const refresh = useCallback(async () => {
    setStatus("loading"); onStatusChange("loading");
    try { const next = await fetchReportsSnapshot(); setSnapshot(next); setError(""); setStatus("online"); onStatusChange("online"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Reports API unavailable"); setStatus("offline"); onStatusChange("offline"); }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:reports-refresh", handleRefresh);
    return () => { window.clearInterval(timer); window.removeEventListener("aios:reports-refresh", handleRefresh); };
  }, [refresh]);

  const families = useMemo(() => [...new Set((snapshot?.artifacts ?? []).map((row) => value(row, "artifact_family")))].sort(), [snapshot]);
  const statuses = useMemo(() => [...new Set((snapshot?.artifacts ?? []).map((row) => value(row, "status")))].sort(), [snapshot]);
  const normalized = query.trim().toLowerCase();
  const artifacts = (snapshot?.artifacts ?? []).filter((row) => {
    const searchable = ["title", "summary", "owner_agent", "department", "symbol", "company_name", "strategy_name", "note_path", "local_path"].map((key) => value(row, key, "").toLowerCase()).join(" ");
    return (!normalized || searchable.includes(normalized)) && (family === "all" || value(row, "artifact_family") === family) && (artifactStatus === "all" || value(row, "status") === artifactStatus);
  });
  const execution = snapshot?.execution_control[0];
  const scheduler = snapshot?.report_scheduler_health[0];
  const blueprintDone = value(snapshot?.blueprint_summary.find((row) => value(row, "metric") === "done_requirements"), "value", "-");
  const dueReports = (snapshot?.report_schedules ?? []).filter((row) => value(row, "due_now", "false") === "true").length;
  const localNeedsAction = (snapshot?.local_artifact_ingestions ?? []).filter((row) => ["needs_mapping", "needs_review", "blocked"].includes(value(row, "promotion_status"))).length;

  const submitLocalArtifact = async () => {
    if (!localFile || !localConfirmed) return;
    setLocalIngesting(true); setError(""); setNotice("");
    try {
      const response = await uploadLocalArtifact(localFile, {
        title: localTitle.trim(),
        sensitivity: localSensitivity,
        suggested_destination: localDestination.trim(),
        actor: "Devarsh via Reports Terminal",
      });
      setNotice(`${value(response.result, "file_name", "Artifact")} registered · task ${value(response.result, "task_id", "queued")}`);
      setLocalFile(null); setLocalFileInputKey((key)=>key+1); setLocalTitle(""); setLocalDestination(""); setLocalConfirmed(false);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Local artifact intake failed");
    } finally { setLocalIngesting(false); }
  };

  const runReports = async (reportKey = "", force = false) => {
    setReportBusy(reportKey || "all"); setError(""); setNotice("");
    try {
      const result = await runScheduledReports({ report_key: reportKey || undefined, force, actor: "Devarsh via Reports Terminal" });
      const rows = Array.isArray(result.results) ? result.results as LiveRow[] : [];
      const completed = rows.filter((row) => value(row, "status") === "completed").length;
      const failed = rows.filter((row) => value(row, "status") === "failed").length;
      setNotice(`Report scheduler finished · ${completed} completed · ${failed} failed · invocation ${value(result, "invocation_id", "recorded")}`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Scheduled report run failed");
    } finally { setReportBusy(""); }
  };

  const copyPath = async (row: LiveRow) => {
    const path = value(row, "note_path", value(row, "local_path", ""));
    if (!path) return;
    try { await navigator.clipboard.writeText(path); setNotice(`Copied: ${path}`); }
    catch { setError("Browser clipboard permission denied. The full path remains visible in the artifact row."); }
  };

  const openEvidence = (selection: EvidenceSelection) => setEvidenceSelection(selection);
  const evidenceKeyDown = (event: ReactKeyboardEvent<HTMLElement>, selection: EvidenceSelection) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openEvidence(selection);
    }
  };

  return <div className="reports-workspace">
    <div className="workspace-filter-bar reports-filter-bar">
      <label><span>Search artifacts</span><input aria-label="Search artifacts" onChange={(event)=>setQuery(event.target.value)} placeholder="Title, agent, symbol, strategy, note, or path" value={query}/></label>
      <label><span>Family</span><select aria-label="Artifact family" onChange={(event)=>setFamily(event.target.value)} value={family}><option value="all">All families</option>{families.map((item)=><option key={item}>{item}</option>)}</select></label>
      <label><span>Status</span><select aria-label="Artifact status" onChange={(event)=>setArtifactStatus(event.target.value)} value={artifactStatus}><option value="all">All statuses</option>{statuses.map((item)=><option key={item}>{item}</option>)}</select></label>
      <div><button className="mini-action-button" disabled={status === "loading"} onClick={()=>void refresh()} type="button"><RefreshCw size={14}/>{status === "loading" ? "Checking" : "Refresh"}</button></div>
    </div>
    <section className="metric-grid" aria-label="Reports metrics">
      <div className="metric-tile"><span>Scoped API</span><strong>{status === "online" ? "Online" : status}</strong><p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p></div>
      <div className="metric-tile"><span>Output Artifacts</span><strong>{snapshot?.artifacts.length ?? 0}</strong><p className="tone-neutral">{artifacts.length} in current filter</p></div>
      <div className="metric-tile"><span>Raw Imports</span><strong>{snapshot?.raw_artifacts.length ?? 0}</strong><p className="tone-neutral">checksum-backed</p></div>
      <div className="metric-tile"><span>Scheduled Reports</span><strong>{snapshot?.report_schedules.length ?? 0}</strong><p className={dueReports ? "tone-warn" : "tone-good"}>{dueReports ? `${dueReports} due` : "cadence current"}</p></div>
      <div className="metric-tile"><span>Scheduler Runtime</span><strong>{value(scheduler,"latest_status","never run")}</strong><p className={value(scheduler,"latest_failed_count","0") === "0" ? "tone-good" : "tone-warn"}>{date(scheduler?.latest_finished_at)}</p></div>
      <div className="metric-tile"><span>Artifact Gaps</span><strong>{snapshot?.artifact_gaps.length ?? 0}</strong><p className={snapshot?.artifact_gaps.length ? "tone-warn" : "tone-good"}>missing durable outputs</p></div>
      <div className="metric-tile"><span>Blueprint Done</span><strong>{blueprintDone}</strong><p className="tone-good">execution {value(execution,"global_execution_locked","true") === "true" ? "locked" : "review"}</p></div>
    </section>
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status}/>
    {error ? <div className="error-strip">{error}</div> : null}{notice ? <div className="success-strip">{notice}</div> : null}
    <section className="dashboard-grid">
      <Panel className="span-12" icon={<FileUp size={17}/>} title="Governed File Intake" action={<span>{localNeedsAction} awaiting review</span>}>
        <form className="artifact-intake-form" onSubmit={(event)=>{event.preventDefault();void submitLocalArtifact();}}>
          <label className="artifact-path-field"><span>Local file</span><input accept=".csv,.tsv,.xls,.xlsx,.pdf,.docx,.txt,.md,.json,.png,.jpg,.jpeg,.webp" aria-label="Local file" key={localFileInputKey} onChange={(event)=>setLocalFile(event.target.files?.[0] ?? null)} type="file"/></label>
          <label><span>Title</span><input aria-label="Artifact title" onChange={(event)=>setLocalTitle(event.target.value)} placeholder="Optional display title" value={localTitle}/></label>
          <label><span>Sensitivity</span><select aria-label="Artifact sensitivity" onChange={(event)=>setLocalSensitivity(event.target.value as typeof localSensitivity)} value={localSensitivity}><option value="public">Public</option><option value="internal">Internal</option><option value="private">Private</option><option value="client_private">Client private</option><option value="restricted">Restricted</option></select></label>
          <label><span>Suggested destination</span><input aria-label="Suggested destination" onChange={(event)=>setLocalDestination(event.target.value)} placeholder="Auto-detect" value={localDestination}/></label>
          <label className="artifact-confirm-field"><input aria-label="Confirm local file intake" checked={localConfirmed} onChange={(event)=>setLocalConfirmed(event.target.checked)} type="checkbox"/><span>I confirm this file may be read and registered</span></label>
          <button className="mini-action-button" disabled={!localFile || !localConfirmed || localIngesting} type="submit"><FileUp size={14}/>{localIngesting ? "Registering" : "Register file"}</button>
        </form>
      </Panel>
      <Panel className="span-12" icon={<DatabaseZap size={17}/>} title="Local Intake Queue" action={<span>{snapshot?.local_artifact_ingestions.length ?? 0} checksum-backed files</span>}>
        <div className="source-check-list scoped-scroll-list local-artifact-queue">{snapshot?.local_artifact_ingestions.map((row)=><article className="source-check-row" key={value(row,"ingestion_key")}><div><strong>{value(row,"file_name")}</strong><p>{value(row,"artifact_family")} · {value(row,"parser_name")} · {value(row,"suggested_destination","mapping required")}</p><small>{value(row,"row_count","0")} rows · {value(row,"sheet_count","0")} sheets · {value(row,"page_count","0")} pages · checksum {value(row,"content_hash").slice(0,12)}</small></div><StatusPill status={value(row,"promotion_status")}/><span>task {value(row,"task_id","-")}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.local_artifact_ingestions.length?<Empty>No local artifacts registered.</Empty>:null}</div>
      </Panel>
      <Panel className="span-6" icon={<CalendarClock size={17}/>} title="Report Schedule" action={<button className="mini-action-button" disabled={Boolean(reportBusy)} onClick={()=>void runReports()} type="button"><PlayCircle size={14}/>{reportBusy === "all" ? "Running" : "Run due"}</button>}>
        <div className="source-check-list scoped-scroll-list">{snapshot?.report_schedules.map((row)=>{const key=value(row,"report_key");return <article className="source-check-row" key={key}><div><strong>{value(row,"report_name")}</strong><p>{value(row,"description")} · owner {value(row,"owner_agent")}{value(row,"approval_required","false") === "true" ? " · human approval required" : ""}</p><small>{value(row,"due_reason","-").replace(/_/g," ")} · {value(row,"latest_output_note_path","No completed output yet")}</small></div><StatusPill status={value(row,"due_now","false") === "true" ? "due" : value(row,"latest_status","waiting")}/><button className="mini-action-button" disabled={Boolean(reportBusy)} onClick={()=>void runReports(key,true)} type="button">{reportBusy === key ? "Running" : "Run now"}</button><time>{date(row.latest_finished_at)}</time></article>})}{!snapshot?.report_schedules.length?<Empty>No report schedules are configured.</Empty>:null}</div>
      </Panel>
      <Panel className="span-6" icon={<History size={17}/>} title="Recent Report Runs" action={<span>{snapshot?.report_runs.length ?? 0} runs</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.report_runs.map((row)=>{const taskId=value(row,"task_id","");const selection:EvidenceSelection={kind:"task",key:taskId,title:value(row,"report_name"),subtitle:`Scheduled report · ${value(row,"owner_agent")}`,record:row};return <article className={`source-check-row${taskId ? " evidence-open-row" : ""}`} key={value(row,"id")} onClick={taskId ? ()=>openEvidence(selection) : undefined} onKeyDown={taskId ? (event)=>evidenceKeyDown(event,selection) : undefined} role={taskId ? "button" : undefined} tabIndex={taskId ? 0 : undefined}><div><strong>{value(row,"report_name")}</strong><p>{value(row,"summary",value(row,"error_message","No summary recorded"))}</p><small>{value(row,"output_note_path",value(row,"run_key"))}</small></div><StatusPill status={value(row,"status")}/><span>{value(row,"period_key")}</span><time>{date(row.finished_at)}</time></article>;})}{!snapshot?.report_runs.length?<Empty>No scheduled report run has been recorded.</Empty>:null}</div></Panel>
      <Panel className="span-12" icon={<Workflow size={17}/>} title="Scheduler Invocation Evidence" action={<span>{snapshot?.report_scheduler_invocations.length ?? 0} attempts</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.report_scheduler_invocations.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"trigger_type")} · {value(row,"report_key","all enabled reports")}</strong><p>{value(row,"completed_count","0")} completed · {value(row,"failed_count","0")} failed · {value(row,"due_count","0")} processed</p><small>{value(row,"error_message",value(row,"invocation_key"))}</small></div><StatusPill status={value(row,"status")}/><span>#{value(row,"id")}</span><time>{date(row.finished_at)}</time></article>)}{!snapshot?.report_scheduler_invocations.length?<Empty>No scheduler invocation has been recorded.</Empty>:null}</div></Panel>
      <Panel className="span-8" icon={<ScrollText size={17}/>} title="Output Registry" action={<span>{artifacts.length} records</span>}><div className="report-artifact-list scoped-scroll-list">{artifacts.map((row)=>{const selection: EvidenceSelection={kind:"artifact",key:value(row,"artifact_key"),title:value(row,"title"),subtitle:`${value(row,"artifact_family")} · ${value(row,"owner_agent")}`,record:row};return <article className="report-artifact-row evidence-open-row" key={value(row,"artifact_key")}><div className="evidence-open-cell" onClick={()=>openEvidence(selection)} onKeyDown={(event)=>evidenceKeyDown(event,selection)} role="button" tabIndex={0}><strong>{value(row,"title")}</strong><p>{value(row,"summary")} · {value(row,"owner_agent")} · {value(row,"artifact_family")}</p><small>{value(row,"note_path",value(row,"local_path",value(row,"source_url","No location")))}</small></div><StatusPill status={value(row,"status","stored")}/><div className="artifact-actions">{value(row,"source_url","") ? <a href={value(row,"source_url")} rel="noreferrer" target="_blank" title="Open source"><ExternalLink size={14}/></a> : null}{value(row,"note_path",value(row,"local_path","")) ? <button onClick={()=>void copyPath(row)} title="Copy artifact path" type="button"><Clipboard size={14}/></button> : null}</div><time>{date(row.latest_activity_at)}</time></article>;})}{!artifacts.length?<Empty>No artifact matches the current filter.</Empty>:null}</div></Panel>
      <Panel className="span-4" icon={<FileCheck2 size={17}/>} title="Artifact Summary"><div className="portfolio-intelligence-list scoped-scroll-list">{snapshot?.artifact_summary.map((row)=><article className="portfolio-intelligence-row" key={value(row,"metric")}><div><strong>{value(row,"metric").replace(/_/g," ")}</strong><p>{value(row,"interpretation")}</p></div><span>{value(row,"value")}</span></article>)}</div></Panel>
      <Panel className="span-6" icon={<Workflow size={17}/>} title="Agent Outputs" action={<span>{snapshot?.worker_runs.length ?? 0} runs</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.worker_runs.map((row)=>{const selection:EvidenceSelection={kind:"task",key:value(row,"task_id"),title:value(row,"task_title"),subtitle:`Worker output · ${value(row,"agent_name")}`,record:row};return <article className="source-check-row evidence-open-row" key={value(row,"id")} onClick={()=>openEvidence(selection)} onKeyDown={(event)=>evidenceKeyDown(event,selection)} role="button" tabIndex={0}><div><strong>{value(row,"task_title")}</strong><p>{value(row,"output_summary")} · {value(row,"agent_name")}</p></div><StatusPill status={value(row,"status","stored")}/><span>{value(row,"skill_name","-")}</span><time>{date(row.finished_at)}</time></article>;})}</div></Panel>
      <Panel className="span-6" icon={<AlertTriangle size={17}/>} title="Artifact Gaps" action={<span>{snapshot?.artifact_gaps.length ?? 0} gaps</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.artifact_gaps.map((row)=><article className="source-check-row" key={`${value(row,"gap_type")}-${value(row,"source_id")}`}><div><strong>{value(row,"title")}</strong><p>{value(row,"gap_reason")} · {value(row,"source_view")}</p></div><StatusPill status={value(row,"status","open")}/><span>{value(row,"owner_agent")}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.artifact_gaps.length?<Empty>No artifact gaps.</Empty>:null}</div></Panel>
      <Panel className="span-6" icon={<DatabaseZap size={17}/>} title="Raw Artifact Inventory" action={<span>{snapshot?.raw_artifacts.length ?? 0} rows</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.raw_artifacts.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"title")}</strong><p>{value(row,"source_system")} · {value(row,"artifact_type")} · {value(row,"mime_type")}</p></div><StatusPill status={value(row,"sensitivity","internal")}/><span>{value(row,"content_hash").slice(0,10)}</span><time>{date(row.captured_at)}</time></article>)}</div></Panel>
      <Panel className="span-6" icon={<FileSearch size={17}/>} title="Source Lineage" action={<span>{snapshot?.artifact_lineage.length ?? 0} rows</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.artifact_lineage.map((row)=>{const selection:EvidenceSelection={kind:"lineage",key:value(row,"row_ref"),title:value(row,"title",value(row,"row_ref")),subtitle:`${value(row,"source_system")} · ${value(row,"lineage_type")}`,record:row};return <article className="source-check-row evidence-open-row" key={`${value(row,"lineage_type")}-${value(row,"row_ref")}`} onClick={()=>openEvidence(selection)} onKeyDown={(event)=>evidenceKeyDown(event,selection)} role="button" tabIndex={0}><div><strong>{value(row,"title",value(row,"row_ref"))}</strong><p>{value(row,"source_system")} · {value(row,"lineage_type")} · {value(row,"symbol","-")}</p></div><StatusPill status={value(row,"reconciliation_status","linked")}/><span>{value(row,"artifact_type")}</span><time>{date(row.event_at)}</time></article>;})}</div></Panel>
      <Panel className="span-12" icon={<FileCheck2 size={17}/>} title="Import Coverage"><div className="coverage-grid">{snapshot?.import_coverage.map((row)=><article key={value(row,"import_surface")}><strong>{value(row,"import_surface").replace(/_/g," ")}</strong><span>{value(row,"coverage_pct","0")}%</span><p>{value(row,"linked_rows","0")} linked · {value(row,"missing_rows","0")} missing · {value(row,"description")}</p></article>)}</div></Panel>
    </section>
    <EvidenceDrawer onChanged={refresh} onClose={()=>setEvidenceSelection(null)} selection={evidenceSelection}/>
  </div>;
}
