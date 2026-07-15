import { Activity, FileSearch, RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import type { LiveRow } from "../api/live";
import { fetchDepartmentTerminal, type DepartmentTerminalSnapshot, type TerminalWorkspace } from "../api/terminal";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";

interface Props {
  mode: TerminalWorkspace;
  onStatusChange: (status: ConnectionStatus) => void;
}

const definitions: Record<TerminalWorkspace, { title: string; purpose: string; primary: string; secondary: string; tertiary: string }> = {
  approvals: { title: "Approval Board", purpose: "Human decisions, execution gates, and evidence-backed exceptions", primary: "Decision queue", secondary: "Execution gates", tertiary: "" },
  agents: { title: "Agent Office", purpose: "Department hierarchy, employee mandates, work queue, and internal communication", primary: "AI employee roster", secondary: "Worker queue", tertiary: "Agent mail" },
  committees: { title: "Committee Rooms", purpose: "Independent challenge, memos, votes, follow-ups, and capital-action boundaries", primary: "Open committee packets", secondary: "", tertiary: "" },
  governance: { title: "Governance & Safety", purpose: "Institutional policies, architecture change control, immutable audit, and production safety", primary: "Policies and operating constitution", secondary: "Architecture change control", tertiary: "Production safety readiness" },
  capital: { title: "Capital Allocation", purpose: "Book mandates, gross and net exposure, attribution, and cross-book coordination", primary: "Investment books", secondary: "Symbol exposure", tertiary: "Coordination questions" },
  treasury: { title: "Treasury & Macro", purpose: "Global market watch, commodity and crypto coverage, news, and source freshness", primary: "Crypto and commodity watch", secondary: "Latest macro news", tertiary: "" },
  models: { title: "Model Runtime", purpose: "Provider readiness, task routes, escalation policy, and assignment gates", primary: "Provider readiness", secondary: "Model routes", tertiary: "Assignment gates" }
};

function text(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const value = row?.[key];
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function first(row: LiveRow, keys: string[], fallback = "-"): string {
  for (const key of keys) {
    const value = text(row, key, "");
    if (value) return value;
  }
  return fallback;
}

function status(row: LiveRow): string {
  return first(row, ["approval_status", "review_status", "task_status", "readiness_status", "gate_status", "health_status", "status", "room_state", "severity"], "recorded");
}

function tone(value: string): string {
  const normalized = value.toLowerCase();
  if (["approved", "active", "ready", "healthy", "fresh", "passed", "locked", "completed"].some((item) => normalized.includes(item))) return "active";
  if (["blocked", "rejected", "failed", "critical", "stale", "error"].some((item) => normalized.includes(item))) return "blocked";
  return "waiting";
}

function rowTitle(row: LiveRow): string {
  return first(row, ["title", "agent_name", "book_name", "subject_name", "provider_name", "route_name", "normalized_symbol", "source_name", "metric"], "Live record");
}

function rowDetail(row: LiveRow): string {
  return first(row, ["requested_action", "policy_statement", "proposed_change", "role_scope", "objective", "coordination_question", "next_action", "notes", "publisher", "interpretation", "rationale"], "Evidence available in the live warehouse.");
}

function rowOwner(row: LiveRow): string {
  return first(row, ["owner_agent", "task_owner_agent", "lead_agent", "department_name", "provider", "created_by"], "AI Office");
}

function rowTime(row: LiveRow): string {
  const value = first(row, ["latest_activity_at", "updated_at", "checked_at", "published_at", "created_at"], "");
  if (!value) return "live";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function evidenceFor(mode: TerminalWorkspace, row: LiveRow): EvidenceSelection | null {
  if (mode === "approvals" && row.approval_id) return { kind: "approval", key: String(row.approval_id), title: rowTitle(row), subtitle: rowDetail(row), record: row };
  if (mode === "committees" && row.committee_item_key) return { kind: "committee", key: String(row.committee_item_key), title: rowTitle(row), subtitle: rowDetail(row), record: row };
  if (row.task_id) return { kind: "task", key: String(row.task_id), title: rowTitle(row), subtitle: rowDetail(row), record: row };
  return null;
}

function TerminalRows({ mode, rows, onEvidence }: { mode: TerminalWorkspace; rows: LiveRow[]; onEvidence: (selection: EvidenceSelection) => void }) {
  return (
    <div aria-label={`${mode} records`} className="terminal-table" role="region" tabIndex={0}>
      <div className="terminal-table-head"><span>Subject</span><span>Owner / scope</span><span>Status</span><span>Updated</span><span>Evidence</span></div>
      {rows.map((row, index) => {
        const selection = evidenceFor(mode, row);
        return (
          <article className="terminal-table-row" key={`${rowTitle(row)}-${first(row, ["id", "source_id", "book_key", "provider_key", "route_name"], String(index))}`}>
            <div><strong>{rowTitle(row)}</strong><p>{rowDetail(row)}</p></div>
            <span>{rowOwner(row)}</span>
            <span className={`status-pill status-${tone(status(row))}`}>{status(row).replace(/_/g, " ")}</span>
            <time>{rowTime(row)}</time>
            {selection ? <button aria-label={`Inspect ${rowTitle(row)} evidence`} className="terminal-evidence-button" onClick={() => onEvidence(selection)} title="Inspect evidence" type="button"><FileSearch size={14} /></button> : <span className="terminal-no-evidence">bound</span>}
          </article>
        );
      })}
      {!rows.length ? <div className="empty-state">No live records in this queue. No placeholder rows were inserted.</div> : null}
    </div>
  );
}

export default function DepartmentTerminalWorkspace({ mode, onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<DepartmentTerminalSnapshot | null>(null);
  const [connection, setConnection] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const definition = definitions[mode];

  const refresh = useCallback(async () => {
    setConnection("loading");
    onStatusChange("loading");
    try {
      setSnapshot(await fetchDepartmentTerminal(mode));
      setConnection("online");
      setError("");
      onStatusChange("online");
    } catch (reason) {
      setConnection("offline");
      setError(reason instanceof Error ? reason.message : "Department terminal unavailable");
      onStatusChange("offline");
    }
  }, [mode, onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:department-terminal-refresh", handleRefresh);
    return () => { window.clearInterval(timer); window.removeEventListener("aios:department-terminal-refresh", handleRefresh); };
  }, [refresh]);

  const execution = snapshot?.execution_control[0];
  const metrics = useMemo(() => {
    const summary = snapshot?.summary ?? [];
    return summary.slice(0, 6).map((row) => ({
      label: first(row, ["metric", "department_name", "source_name"], "Live metric"),
      value: first(row, ["value", "active_agents", "rows_seen", "staleness_minutes"], "-"),
      detail: first(row, ["interpretation", "mission", "status", "severity"], "warehouse")
    }));
  }, [snapshot]);

  return (
    <div className="department-terminal-workspace">
      <section className="terminal-masthead">
        <div><span>Department terminal</span><h2>{definition.title}</h2><p>{definition.purpose}</p></div>
        <div className="terminal-safety-state"><ShieldAlert size={16} /><span>Broker execution</span><strong>{text(execution, "global_execution_locked", "true") === "true" ? "LOCKED" : "CHECK"}</strong></div>
        <button className="mini-action-button" disabled={connection === "loading"} onClick={() => void refresh()} type="button"><RefreshCw size={14} />{connection === "loading" ? "Syncing" : "Refresh"}</button>
      </section>
      <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={connection} />
      {error ? <div className="error-strip">{error}</div> : null}
      <section className="terminal-metric-strip" aria-label={`${definition.title} metrics`} tabIndex={0}>
        <div><span>Live rows</span><strong>{snapshot?.payload_profile.row_count ?? 0}</strong><small>no seed data</small></div>
        {metrics.map((item) => <div key={item.label}><span>{item.label.replace(/_/g, " ")}</span><strong>{item.value}</strong><small>{item.detail}</small></div>)}
      </section>
      <section className="terminal-pane terminal-primary-pane">
        <header><div><Activity size={15} /><h3>{definition.primary}</h3></div><strong>{snapshot?.primary.length ?? 0}</strong></header>
        <TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.primary ?? []} />
      </section>
      {definition.secondary ? <section className="terminal-pane"><header><h3>{definition.secondary}</h3><strong>{snapshot?.secondary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.secondary ?? []} /></section> : null}
      {definition.tertiary ? <section className="terminal-pane"><header><h3>{definition.tertiary}</h3><strong>{snapshot?.tertiary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.tertiary ?? []} /></section> : null}
      <EvidenceDrawer onChanged={refresh} onClose={() => setEvidence(null)} selection={evidence} />
    </div>
  );
}
