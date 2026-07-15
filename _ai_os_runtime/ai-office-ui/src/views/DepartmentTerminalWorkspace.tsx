import { Activity, Clock3, FileSearch, Mail, Network, Play, RefreshCw, Scale, Send, ShieldAlert, Users } from "lucide-react";
import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import { createAgentMessage, runAgentWorker, type LiveRow } from "../api/live";
import { decideCapitalCommittee, fetchDepartmentTerminal, materializeAgentSchedules, proposeCapitalPolicy, runCapitalAllocationAnalysis, type DepartmentTerminalSnapshot, type TerminalWorkspace } from "../api/terminal";
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
  capital: { title: "Capital Allocation", purpose: "Client policy, book budgets, risk limits, drift previews, and human-governed decisions", primary: "Client and book policy control", secondary: "Allocation and risk analysis", tertiary: "Capital Allocation Committee" },
  treasury: { title: "Treasury & Macro", purpose: "Global market watch, commodity and crypto coverage, news, and source freshness", primary: "Crypto and commodity watch", secondary: "Latest macro news", tertiary: "" },
  models: { title: "Model Runtime", purpose: "Local-first routes, privacy policy, cost controls, cache, and escalation evidence", primary: "Model route readiness", secondary: "Privacy and retention policy", tertiary: "Recent model-call decisions" }
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
  return first(row, ["control_status", "proposal_status", "approval_status", "review_status", "risk_review_status", "decision_status", "runtime_status", "task_status", "readiness_status", "gate_status", "health_status", "status", "room_state", "severity"], "recorded");
}

function tone(value: string): string {
  const normalized = value.toLowerCase();
  if (["approved", "active", "ready", "healthy", "fresh", "passed", "locked", "completed"].some((item) => normalized.includes(item))) return "active";
  if (["blocked", "rejected", "failed", "critical", "stale", "error"].some((item) => normalized.includes(item))) return "blocked";
  return "waiting";
}

function rowTitle(row: LiveRow): string {
  return first(row, ["title", "agent_name", "book_name", "subject_name", "provider_name", "route_name", "privacy_class", "normalized_symbol", "source_name", "metric"], "Live record");
}

function rowDetail(row: LiveRow): string {
  return first(row, ["next_required_action", "recommended_action", "requested_action", "policy_statement", "proposed_change", "role_scope", "objective", "coordination_question", "next_action", "notes", "publisher", "interpretation", "rationale"], "Evidence available in the live warehouse.");
}

function rowOwner(row: LiveRow): string {
  return first(row, ["owner_agent", "agent_name", "task_owner_agent", "lead_agent", "department_name", "provider", "created_by"], "AI Office");
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
          <article
            className="terminal-table-row"
            key={`${rowTitle(row)}-${first(row, ["client_code"], "global")}-${first(row, ["id", "source_id", "book_key", "provider_key", "route_name"], String(index))}`}
          >
            <div>
              <strong>{rowTitle(row)}</strong>
              <p>{rowDetail(row)}</p>
              {row.legacy_policy_status ? <small className="terminal-data-label">{text(row, "legacy_policy_status").replace(/_/g, " ")}</small> : null}
            </div>
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

function jsonRows(value: unknown): LiveRow[] {
  return Array.isArray(value) ? value.filter((item): item is LiveRow => Boolean(item) && typeof item === "object") : [];
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function AgentOfficeControl({ snapshot, refresh, setError, setNotice }: {
  snapshot: DepartmentTerminalSnapshot;
  refresh: () => Promise<void>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
}) {
  const [department, setDepartment] = useState("all");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [skillKey, setSkillKey] = useState("");
  const [busy, setBusy] = useState("");
  const employees = useMemo(() => snapshot.primary.filter((row) => department === "all" || text(row, "department", "") === department), [department, snapshot.primary]);
  const selected = snapshot.primary.find((row) => text(row, "agent_name", "") === selectedAgent) ?? employees[0];
  const selectedName = text(selected, "agent_name", "");
  const selectedSkills = useMemo(() => jsonRows(selected?.skills), [selected]);

  useEffect(() => {
    if (!selectedName) return;
    if (selectedAgent !== selectedName) setSelectedAgent(selectedName);
  }, [selectedAgent, selectedName]);

  useEffect(() => {
    const nextSkill = text(selectedSkills[0], "skill_key", "");
    setSkillKey(nextSkill);
  }, [selectedName]);

  const assignWork = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedName) return;
    setBusy("message"); setError(""); setNotice("");
    try {
      await createAgentMessage({ from_agent: "Charlie Munger", to_agent: selectedName, subject, body, priority, related_skill_key: skillKey || undefined, metadata: { source: "agent_office_operator", human_authority: "Devarsh" } });
      setSubject(""); setBody("");
      setNotice(`Charlie assigned work to ${selectedName}. Jarvis will create the durable task and inbox handoff.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Agent assignment failed"); }
    finally { setBusy(""); }
  };

  const runSchedules = async () => {
    setBusy("schedules"); setError(""); setNotice("");
    try {
      const result = await materializeAgentSchedules({ actor: "Jarvis", limit: 20 });
      setNotice(`Schedule pass completed. ${text(result, "processed", "0")} due workflows processed.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Schedule pass failed"); }
    finally { setBusy(""); }
  };

  const runWorkers = async () => {
    setBusy("workers"); setError(""); setNotice("");
    try {
      const result = await runAgentWorker({ actor: "Jarvis", limit: 5 });
      setNotice(`Worker pass completed. ${text(result, "count", "0")} queue records inspected.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Worker pass failed"); }
    finally { setBusy(""); }
  };

  return <>
    <section className="terminal-pane agent-office-command">
      <header><div><Network size={15}/><h3>Office command and delegation</h3></div><strong>Charlie leads · Jarvis runs</strong></header>
      <div className="agent-office-toolbar">
        <label><span>Department</span><select value={department} onChange={(event) => { setDepartment(event.target.value); setSelectedAgent(""); }}><option value="all">All departments</option>{(snapshot.departments ?? []).map((row) => <option key={text(row, "department_key")} value={text(row, "department_key")}>{text(row, "department_name")}</option>)}</select></label>
        <label><span>Employee</span><select value={selectedName} onChange={(event) => setSelectedAgent(event.target.value)}>{employees.map((row) => <option key={text(row, "agent_name")} value={text(row, "agent_name")}>{text(row, "display_title")} · {text(row, "agent_name")}</option>)}</select></label>
        <button className="mini-action-button" disabled={Boolean(busy)} onClick={() => void runSchedules()} type="button"><Clock3 size={14}/>{busy === "schedules" ? "Scheduling" : "Run due schedules"}</button>
        <button className="mini-action-button" disabled={Boolean(busy)} onClick={() => void runWorkers()} type="button"><Play size={14}/>{busy === "workers" ? "Working" : "Run workers"}</button>
      </div>
      {selected ? <div className="agent-office-selected" style={{ "--agent-color": text(selected, "color_token", "#0f766e") } as CSSProperties}>
        <div className="agent-profile-identity"><span>{text(selected, "character_name", selectedName).slice(0, 2).toUpperCase()}</span><div><small>{text(selected, "department_name")}</small><h3>{text(selected, "display_title")}</h3><p>{selectedName} · reports to {text(selected, "reports_to_agent")}</p></div></div>
        <div className="agent-profile-facts"><div><span>Status</span><strong>{text(selected, "live_state").replace(/_/g, " ")}</strong></div><div><span>Readiness</span><strong>{text(selected, "operating_readiness_score")}%</strong></div><div><span>Model</span><strong>{text(selected, "assigned_model")}</strong></div><div><span>Route</span><strong>{text(selected, "primary_route").replace(/_/g, " ")}</strong></div><div><span>Mailbox</span><strong>{text(selected, "mailbox_address")}</strong></div></div>
        <p className="agent-profile-mandate">{text(selected, "role_scope")}</p>
        <p className="agent-profile-persona">{text(selected, "persona")}</p>
        <div className="agent-profile-tags">{textList(selected.mental_models).map((item) => <span key={item}>{item.replace(/_/g, " ")}</span>)}{selectedSkills.map((item) => <span key={text(item, "skill_key")}>{text(item, "skill_name")}</span>)}</div>
      </div> : null}
      <form className="agent-assignment-form" onSubmit={assignWork}>
        <div><Mail size={15}/><strong>Assign through Charlie</strong><small>Creates an internal message, then Jarvis materializes the role-scoped task.</small></div>
        <input aria-label="Assignment subject" onChange={(event) => setSubject(event.target.value)} placeholder="Assignment subject" required value={subject}/>
        <textarea aria-label="Assignment objective" onChange={(event) => setBody(event.target.value)} placeholder="Objective, required evidence, output, deadline, and decision boundary" required rows={3} value={body}/>
        <div><select aria-label="Assignment skill" onChange={(event) => setSkillKey(event.target.value)} value={skillKey}><option value="">Automatic skill routing</option>{selectedSkills.map((item) => <option key={text(item, "skill_key")} value={text(item, "skill_key")}>{text(item, "skill_name")}</option>)}</select><select aria-label="Assignment priority" onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select><button className="primary-button" disabled={!selectedName || Boolean(busy)} type="submit"><Send size={14}/>{busy === "message" ? "Routing" : "Assign work"}</button></div>
      </form>
    </section>
    <section className="terminal-pane agent-roster-pane"><header><div><Users size={15}/><h3>AI employee roster</h3></div><strong>{employees.length} visible</strong></header><div className="agent-roster-grid">{employees.map((row) => <button className={`agent-roster-card ${text(row, "agent_name") === selectedName ? "is-selected" : ""}`} key={text(row, "agent_name")} onClick={() => setSelectedAgent(text(row, "agent_name"))} style={{ "--agent-color": text(row, "color_token", "#0f766e") } as CSSProperties} type="button"><span className={`status-dot status-${tone(text(row, "readiness_status"))}`}/><div><strong>{text(row, "display_title")}</strong><small>{text(row, "agent_name")} · {text(row, "department_name")}</small><p>{text(row, "current_work_title", text(row, "role_scope"))}</p></div><b>{text(row, "operating_readiness_score")}%</b></button>)}</div></section>
    <div className="agent-governance-grid">
      <section className="terminal-pane"><header><div><Clock3 size={15}/><h3>Operating schedules</h3></div><strong>{snapshot.schedules?.length ?? 0}</strong></header><div className="agent-schedule-list">{(snapshot.schedules ?? []).map((row) => <article key={text(row, "schedule_key")}><div><strong>{text(row, "schedule_name")}</strong><small>{text(row, "owner_agent")} · {text(row, "skill_name")}</small></div><span className={`status-pill status-${tone(text(row, "schedule_state"))}`}>{text(row, "schedule_state").replace(/_/g, " ")}</span><time>{rowTime(row)}</time></article>)}</div></section>
      <section className="terminal-pane"><header><div><Scale size={15}/><h3>Committee constitution</h3></div><strong>{snapshot.committees?.length ?? 0}</strong></header><div className="agent-committee-list">{(snapshot.committees ?? []).map((row) => <article key={text(row, "committee_key")}><div><strong>{text(row, "committee_name")}</strong><small>Chair: {text(row, "chair_agent")} · quorum {text(row, "quorum")} · {text(row, "member_count")} members</small><p>{text(row, "mandate")}</p></div><span>{text(row, "human_final_required", "true") === "true" ? "human final" : "advisory"}</span></article>)}</div></section>
    </div>
  </>;
}

export default function DepartmentTerminalWorkspace({ mode, onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<DepartmentTerminalSnapshot | null>(null);
  const [connection, setConnection] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [actionBusy, setActionBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [capitalClient, setCapitalClient] = useState("");
  const [capitalRules, setCapitalRules] = useState<Record<string, { target: string; min: string; max: string; risk: string }>>({});
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
  const capitalClients = useMemo(() => {
    const rows = snapshot?.primary ?? [];
    return Array.from(new Map(rows.map((row) => [text(row, "client_code", ""), text(row, "client_name", "")])).entries()).filter(([key]) => key);
  }, [snapshot]);
  const capitalBooks = useMemo(() => {
    const rows = snapshot?.primary ?? [];
    return Array.from(new Map(rows.map((row) => [text(row, "book_key", ""), text(row, "book_name", "")])).entries()).filter(([key]) => key);
  }, [snapshot]);
  const selectedProposalId = snapshot?.primary.find((row) => text(row, "client_code", "") === capitalClient && row.proposal_id)?.proposal_id;
  const selectedReviewId = snapshot?.tertiary?.find((row) => text(row, "client_code", "") === capitalClient)?.id;

  const loadObservedAllocation = useCallback((clientCode: string) => {
    if (!snapshot || !clientCode) return;
    const next: Record<string, { target: string; min: string; max: string; risk: string }> = {};
    for (const [bookKey] of capitalBooks) {
      const row = snapshot.primary.find((item) => text(item, "client_code", "") === clientCode && text(item, "book_key", "") === bookKey);
      const observed = Number(row?.current_pct ?? 0);
      next[bookKey] = {
        target: Number.isFinite(observed) ? observed.toFixed(2) : "0",
        min: "0",
        max: "100",
        risk: observed > 0 ? "12" : "0"
      };
    }
    setCapitalRules(next);
  }, [capitalBooks, snapshot]);

  useEffect(() => {
    if (mode !== "capital" || !capitalClients.length) return;
    const selected = capitalClient || capitalClients[0][0];
    if (!capitalClient) setCapitalClient(selected);
    if (!Object.keys(capitalRules).length) loadObservedAllocation(selected);
  }, [capitalClient, capitalClients, capitalRules, loadObservedAllocation, mode]);

  const submitCapitalPolicy = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionBusy("policy"); setError(""); setNotice("");
    try {
      const rules = capitalBooks.map(([bookKey]) => ({
        book_key: bookKey,
        target_pct: Number(capitalRules[bookKey]?.target ?? 0),
        min_pct: Number(capitalRules[bookKey]?.min ?? 0),
        max_pct: Number(capitalRules[bookKey]?.max ?? 100),
        risk_budget_var_99_10d_pct: Number(capitalRules[bookKey]?.risk ?? 0),
        minimum_liquidity_coverage_pct: 80,
        rationale: "Operator-entered policy routed through Capital Allocation terminal"
      }));
      await proposeCapitalPolicy({ client_code: capitalClient, rules, capital_basis_type: "gross_exposure_only", actor: "Devarsh" });
      setNotice("Capital policy proposal recorded and routed to independent risk review. No capital action or order was authorized.");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Capital policy proposal failed"); }
    finally { setActionBusy(""); }
  };

  const runCapitalAnalysis = async () => {
    if (!selectedProposalId) return;
    setActionBusy("analysis"); setError(""); setNotice("");
    try {
      await runCapitalAllocationAnalysis({ proposal_id: selectedProposalId, minimum_coverage_pct: 80, actor: "Capital Allocation Agent" });
      setNotice("Allocation drift and risk-budget analysis completed. Output remains an advisory preview.");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Capital analysis failed"); }
    finally { setActionBusy(""); }
  };

  const recordCapitalDecision = async (decision: "revise" | "defer") => {
    if (!selectedReviewId) return;
    setActionBusy("committee"); setError(""); setNotice("");
    try {
      await decideCapitalCommittee({ review_id: selectedReviewId, decision, decision_notes: "Recorded from Capital Allocation terminal; no capital action or broker order authorized.", actor: "Charlie Munger" });
      setNotice(`Committee decision recorded: ${decision}.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Committee decision failed"); }
    finally { setActionBusy(""); }
  };
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
      {notice ? <div className="success-strip">{notice}</div> : null}
      <section className="terminal-metric-strip" aria-label={`${definition.title} metrics`} tabIndex={0}>
        <div><span>Live rows</span><strong>{snapshot?.payload_profile.row_count ?? 0}</strong><small>no seed data</small></div>
        {metrics.map((item) => <div key={item.label}><span>{item.label.replace(/_/g, " ")}</span><strong>{item.value}</strong><small>{item.detail}</small></div>)}
      </section>
      {mode === "capital" ? <section className="terminal-pane capital-policy-editor">
        <header><div><Scale size={15}/><h3>Client Capital And Risk Policy</h3></div><strong>human governed</strong></header>
        <form className="capital-policy-form" onSubmit={submitCapitalPolicy}>
          <div className="capital-policy-toolbar"><label><span>Client</span><select value={capitalClient} onChange={(event) => { setCapitalClient(event.target.value); loadObservedAllocation(event.target.value); }}>{capitalClients.map(([key, name]) => <option key={key} value={key}>{name} · {key}</option>)}</select></label><button className="mini-action-button" onClick={() => loadObservedAllocation(capitalClient)} type="button"><RefreshCw size={14}/>Load observed allocation</button><p>Legacy defaults are reference only. Targets must total 100%; risk review and Devarsh approval remain separate.</p></div>
          <div className="capital-policy-rule-grid"><div className="capital-policy-rule-head"><span>Book</span><span>Target %</span><span>Min %</span><span>Max %</span><span>10D VaR budget %</span></div>{capitalBooks.map(([bookKey, bookName]) => { const rule=capitalRules[bookKey] ?? {target:"0",min:"0",max:"100",risk:"0"}; return <div className="capital-policy-rule" key={bookKey}><strong>{bookName}</strong>{(["target","min","max","risk"] as const).map((field)=><input aria-label={`${bookName} ${field}`} inputMode="decimal" key={field} min="0" max={field === "risk" ? undefined : "100"} required step="0.01" type="number" value={rule[field]} onChange={(event)=>setCapitalRules((current)=>({...current,[bookKey]:{...rule,[field]:event.target.value}}))}/>)}</div>; })}</div>
          <div className="capital-policy-actions"><button className="primary-button" disabled={Boolean(actionBusy)} type="submit"><Scale size={15}/>{actionBusy === "policy" ? "Routing" : "Propose policy"}</button><button className="mini-action-button" disabled={!selectedProposalId || Boolean(actionBusy)} onClick={() => void runCapitalAnalysis()} type="button"><Play size={14}/>{actionBusy === "analysis" ? "Analyzing" : "Run risk analysis"}</button>{selectedReviewId ? <><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={() => void recordCapitalDecision("defer")} type="button">Defer</button><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={() => void recordCapitalDecision("revise")} type="button">Request revision</button></> : null}</div>
        </form>
      </section> : null}
      {mode === "agents" && snapshot ? <AgentOfficeControl refresh={refresh} setError={setError} setNotice={setNotice} snapshot={snapshot}/> : <section className="terminal-pane terminal-primary-pane">
        <header><div><Activity size={15} /><h3>{definition.primary}</h3></div><strong>{snapshot?.primary.length ?? 0}</strong></header>
        <TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.primary ?? []} />
      </section>}
      {definition.secondary ? <section className="terminal-pane"><header><h3>{definition.secondary}</h3><strong>{snapshot?.secondary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.secondary ?? []} /></section> : null}
      {definition.tertiary ? <section className="terminal-pane"><header><h3>{definition.tertiary}</h3><strong>{snapshot?.tertiary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.tertiary ?? []} /></section> : null}
      <EvidenceDrawer onChanged={refresh} onClose={() => setEvidence(null)} selection={evidence} />
    </div>
  );
}
