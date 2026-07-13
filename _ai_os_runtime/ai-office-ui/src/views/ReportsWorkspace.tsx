import {
  AlertTriangle,
  Clipboard,
  DatabaseZap,
  ExternalLink,
  FileCheck2,
  FileSearch,
  RefreshCw,
  ScrollText,
  Workflow
} from "lucide-react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import type { LiveRow } from "../api/live";
import { fetchReportsSnapshot, type ReportsSnapshot } from "../api/reports";
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
  const blueprintDone = value(snapshot?.blueprint_summary.find((row) => value(row, "metric") === "done_requirements"), "value", "-");

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
      <div className="metric-tile"><span>Artifact Gaps</span><strong>{snapshot?.artifact_gaps.length ?? 0}</strong><p className={snapshot?.artifact_gaps.length ? "tone-warn" : "tone-good"}>missing durable outputs</p></div>
      <div className="metric-tile"><span>Blueprint Done</span><strong>{blueprintDone}</strong><p className="tone-good">execution {value(execution,"global_execution_locked","true") === "true" ? "locked" : "review"}</p></div>
    </section>
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status}/>
    {error ? <div className="error-strip">{error}</div> : null}{notice ? <div className="success-strip">{notice}</div> : null}
    <section className="dashboard-grid">
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
