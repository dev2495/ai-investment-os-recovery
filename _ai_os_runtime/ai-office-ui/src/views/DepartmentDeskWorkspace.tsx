import { Activity, BriefcaseBusiness, Clock3, FileSearch, Mail, Network, ShieldCheck, UsersRound, WalletCards } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import type { LiveRow } from "../api/live";
import { fetchDepartmentTerminal, type DepartmentTerminalSnapshot } from "../api/terminal";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";

interface Props {
  onStatusChange: (status: ConnectionStatus) => void;
}

function text(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const value = row?.[key];
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function date(value: unknown): string {
  if (!value) return "live";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime()) ? String(value) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function tone(value: unknown): string {
  const normalized = String(value ?? "").toLowerCase();
  if (["failed", "blocked", "critical", "error"].some((part) => normalized.includes(part))) return "blocked";
  if (["completed", "ready", "healthy", "active", "ok"].some((part) => normalized.includes(part))) return "active";
  return "waiting";
}

function taskEvidence(row: LiveRow): EvidenceSelection | null {
  const taskId = row.task_id ?? row.id;
  if (!taskId) return null;
  return {
    kind: "task",
    key: String(taskId),
    title: text(row, "title", "Department work item"),
    subtitle: `${text(row, "owner_agent")} department work`,
    record: row
  };
}

function DepartmentList({ departments, selected, onSelect, employeeCounts }: {
  departments: LiveRow[];
  selected: string;
  onSelect: (department: string) => void;
  employeeCounts: Map<string, number>;
}) {
  return <nav aria-label="Department desks" className="department-desk-nav">
    {departments.map((row) => {
      const key = text(row, "department_key", "");
      return <button className={key === selected ? "is-active" : ""} key={key} onClick={() => onSelect(key)} type="button">
        <span>{text(row, "department_name")}</span>
        <strong>{employeeCounts.get(key) ?? 0}</strong>
        <small>{text(row, "lead_agent")}</small>
      </button>;
    })}
  </nav>;
}

export default function DepartmentDeskWorkspace({ onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<DepartmentTerminalSnapshot | null>(null);
  const [connection, setConnection] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [department, setDepartment] = useState(() => new URLSearchParams(window.location.search).get("department") ?? "");
  const [employee, setEmployee] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);

  const refresh = useCallback(async () => {
    setConnection("loading");
    onStatusChange("loading");
    try {
      setSnapshot(await fetchDepartmentTerminal("agents"));
      setConnection("online");
      setError("");
      onStatusChange("online");
    } catch (reason) {
      setConnection("offline");
      setError(reason instanceof Error ? reason.message : "Department desks unavailable");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:department-terminal-refresh", handleRefresh);
    return () => { window.clearInterval(timer); window.removeEventListener("aios:department-terminal-refresh", handleRefresh); };
  }, [refresh]);

  const employees = snapshot?.primary ?? [];
  const departments = snapshot?.departments ?? [];
  const employeeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of employees) {
      const key = text(row, "department", "");
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [employees]);

  const selectedDepartment = department || text(departments[0], "department_key", "");
  const departmentRow = departments.find((row) => text(row, "department_key", "") === selectedDepartment);
  const team = employees.filter((row) => text(row, "department", "") === selectedDepartment);
  const teamNames = useMemo(() => new Set(team.map((row) => text(row, "agent_name", ""))), [team]);
  const selectedEmployeeName = employee && teamNames.has(employee) ? employee : text(team.find((row) => text(row, "agent_name", "") === text(departmentRow, "lead_agent", "")) ?? team[0], "agent_name", "");
  const selectedEmployee = team.find((row) => text(row, "agent_name", "") === selectedEmployeeName);
  const queue = (snapshot?.secondary ?? []).filter((row) => teamNames.has(text(row, "owner_agent", "")));
  const messages = (snapshot?.tertiary ?? []).filter((row) => teamNames.has(text(row, "from_agent", "")) || teamNames.has(text(row, "to_agent", "")));
  const schedules = (snapshot?.schedules ?? []).filter((row) => teamNames.has(text(row, "owner_agent", "")));
  const history = (snapshot?.worker_history ?? []).filter((row) => teamNames.has(text(row, "agent_name", "")));
  const costs = (snapshot?.cost_quality ?? []).filter((row) => teamNames.has(text(row, "agent_name", "")));
  const readyCount = team.filter((row) => text(row, "readiness_status", "").includes("ready")).length;
  const openTasks = team.reduce((total, row) => total + Number(row.open_task_count ?? 0), 0);
  const openInbox = team.reduce((total, row) => total + Number(row.open_inbox_count ?? 0), 0);

  const selectDepartment = (key: string) => {
    setDepartment(key);
    setEmployee("");
    const url = new URL(window.location.href);
    url.searchParams.set("department", key);
    window.history.replaceState({}, "", url);
  };

  const execution = snapshot?.execution_control?.[0];

  return <div className="department-desk-workspace">
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={connection} />
    <header className="department-desk-masthead">
      <div><span>Institutional operating desks</span><h2>{text(departmentRow, "department_name", "Department Desks")}</h2><p>{text(departmentRow, "mission", "Live department ownership, work, evidence, and model controls.")}</p></div>
      <div className="department-desk-control"><ShieldCheck size={15}/><span>Execution</span><strong>{text(execution, "global_execution_locked", "true") === "true" ? "Locked" : "Review"}</strong></div>
    </header>
    {error ? <div className="error-strip">{error}</div> : null}
    <section className="department-desk-frame">
      <DepartmentList departments={departments} employeeCounts={employeeCounts} onSelect={selectDepartment} selected={selectedDepartment}/>
      <div className="department-desk-main">
        <section aria-label="Department operating metrics" className="department-kpi-strip" tabIndex={0}>
          <div><span>Team</span><strong>{team.length}</strong><small>active employees</small></div>
          <div><span>Ready</span><strong>{readyCount}</strong><small>operating now</small></div>
          <div><span>Open work</span><strong>{openTasks}</strong><small>assigned tasks</small></div>
          <div><span>Inbox</span><strong>{openInbox}</strong><small>items requiring action</small></div>
          <div><span>Schedules</span><strong>{schedules.length}</strong><small>recurring workflows</small></div>
          <div><span>Completed</span><strong>{history.filter((row) => text(row, "status", "") === "completed").length}</strong><small>recent worker runs</small></div>
        </section>

        <div className="department-command-grid">
          <section className="terminal-pane department-mandate-pane"><header><div><BriefcaseBusiness size={15}/><h3>Department mandate</h3></div><strong>{text(departmentRow, "status", "active")}</strong></header><div className="department-mandate-copy"><p>{text(departmentRow, "mission")}</p><dl><div><dt>Lead</dt><dd>{text(departmentRow, "lead_agent")}</dd></div><div><dt>Core workflows</dt><dd>{list(departmentRow?.core_workflows).join(" · ") || "Evidence pending"}</dd></div><div><dt>Next builds</dt><dd>{list(departmentRow?.required_next_builds).join(" · ") || "No registered gap"}</dd></div></dl></div></section>
          <section className="terminal-pane department-manager-pane"><header><div><Network size={15}/><h3>Selected employee</h3></div><select aria-label="Department employee" onChange={(event) => setEmployee(event.target.value)} value={selectedEmployeeName}>{team.map((row) => <option key={text(row, "agent_name")} value={text(row, "agent_name")}>{text(row, "display_title")} · {text(row, "agent_name")}</option>)}</select></header>{selectedEmployee ? <div className="department-manager-profile"><div><span>{text(selectedEmployee, "character_name", selectedEmployeeName).slice(0, 2).toUpperCase()}</span><div><strong>{text(selectedEmployee, "display_title")}</strong><small>{selectedEmployeeName} · reports to {text(selectedEmployee, "reports_to_agent")}</small></div><b>{text(selectedEmployee, "operating_readiness_score")}%</b></div><p>{text(selectedEmployee, "role_scope")}</p><small>{text(selectedEmployee, "current_work_title", "No current work title")} · {text(selectedEmployee, "primary_route")} · {text(selectedEmployee, "assigned_model")}</small></div> : <div className="empty-state">No live employee is assigned to this department.</div>}</section>
        </div>

        <section className="terminal-pane"><header><div><UsersRound size={15}/><h3>Department team</h3></div><strong>{team.length}</strong></header><div className="department-team-grid">{team.map((row) => <button className={text(row, "agent_name") === selectedEmployeeName ? "is-selected" : ""} key={text(row, "agent_name")} onClick={() => setEmployee(text(row, "agent_name"))} type="button"><span className={`status-dot status-${tone(row.readiness_status)}`}/><div><strong>{text(row, "display_title")}</strong><small>{text(row, "agent_name")}</small><p>{text(row, "current_work_title", text(row, "role_scope"))}</p></div><b>{text(row, "operating_readiness_score")}%</b></button>)}</div></section>

        <div className="department-operations-grid">
          <section className="terminal-pane"><header><div><Activity size={15}/><h3>Live work queue</h3></div><strong>{queue.length}</strong></header><div aria-label="Department live work queue" className="department-compact-list" role="region" tabIndex={0}>{queue.map((row) => { const selection = taskEvidence(row); return <article key={text(row, "task_id")}><div><strong>{text(row, "title")}</strong><small>{text(row, "owner_agent")} · {text(row, "suggested_skill_name")}</small></div><span className={`status-pill status-${tone(row.task_status)}`}>{text(row, "task_status")}</span>{selection ? <button aria-label={`Inspect ${text(row, "title")} evidence`} onClick={() => setEvidence(selection)} title="Inspect evidence" type="button"><FileSearch size={14}/></button> : null}</article>; })}{!queue.length ? <p className="empty-state">No live work queue records for this department.</p> : null}</div></section>
          <section className="terminal-pane"><header><div><Clock3 size={15}/><h3>Recurring schedules</h3></div><strong>{schedules.length}</strong></header><div aria-label="Department recurring schedules" className="department-compact-list" role="region" tabIndex={0}>{schedules.map((row) => <article key={text(row, "schedule_key")}><div><strong>{text(row, "schedule_name")}</strong><small>{text(row, "owner_agent")} · {text(row, "skill_name")}</small></div><span className={`status-pill status-${tone(row.schedule_state)}`}>{text(row, "schedule_state")}</span><time>{date(row.next_run_at)}</time></article>)}{!schedules.length ? <p className="empty-state">No recurring schedule registered for this department.</p> : null}</div></section>
          <section className="terminal-pane"><header><div><Mail size={15}/><h3>Department mail</h3></div><strong>{messages.length}</strong></header><div aria-label="Department mail" className="department-compact-list" role="region" tabIndex={0}>{messages.map((row) => <article key={text(row, "id")}><div><strong>{text(row, "subject")}</strong><small>{text(row, "from_agent")} to {text(row, "to_agent")}</small></div><span className={`status-pill status-${tone(row.processing_status)}`}>{text(row, "processing_status", text(row, "status"))}</span><time>{date(row.created_at)}</time></article>)}{!messages.length ? <p className="empty-state">No recent department mail.</p> : null}</div></section>
          <section className="terminal-pane"><header><div><WalletCards size={15}/><h3>Model and cost controls</h3></div><strong>{costs.length}</strong></header><div aria-label="Department model and cost controls" className="department-compact-list" role="region" tabIndex={0}>{costs.map((row) => <article key={text(row, "agent_name")}><div><strong>{text(row, "agent_name")}</strong><small>{text(row, "primary_route")} · {text(row, "cost_policy")}</small></div><span className={`status-pill status-${tone(row.cap_status)}`}>{text(row, "cap_status")}</span><time>${text(row, "cost_month_usd", "0")}</time></article>)}{!costs.length ? <p className="empty-state">No model-cost records for this department.</p> : null}</div></section>
        </div>

        <section className="terminal-pane"><header><div><Activity size={15}/><h3>Recent output history</h3></div><strong>{history.length}</strong></header><div aria-label="Department recent output history" className="department-history-table" role="region" tabIndex={0}><div className="department-history-head"><span>Output</span><span>Agent</span><span>Skill</span><span>Status</span><span>Finished</span></div>{history.map((row) => <article key={text(row, "id")}><div><strong>{text(row, "task_title")}</strong><small>{text(row, "output_summary")}</small></div><span>{text(row, "agent_name")}</span><span>{text(row, "skill_name")}</span><span className={`status-pill status-${tone(row.status)}`}>{text(row, "status")}</span><time>{date(row.finished_at)}</time></article>)}{!history.length ? <p className="empty-state">No recent worker output for this department.</p> : null}</div></section>
      </div>
    </section>
    <EvidenceDrawer onChanged={refresh} onClose={() => setEvidence(null)} selection={evidence}/>
  </div>;
}
