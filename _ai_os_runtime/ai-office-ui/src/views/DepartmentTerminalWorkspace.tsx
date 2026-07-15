import { Activity, Clock3, FileSearch, Mail, Network, Play, RefreshCw, Scale, Send, ShieldAlert, Users } from "lucide-react";
import type { CSSProperties, FormEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import { createAgentMessage, runAgentWorker, type LiveRow } from "../api/live";
import { decideCapitalCommittee, fetchDepartmentTerminal, materializeAgentSchedules, openCommitteePacket, proposeCapitalPolicy, recordCommitteeHumanDecision, runCapitalAllocationAnalysis, synthesizeCommitteeSession, type DepartmentTerminalSnapshot, type TerminalWorkspace } from "../api/terminal";
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
  committees: { title: "Committee Rooms", purpose: "Independent challenge, sealed positions, quorum, minutes, follow-ups, and human-final boundaries", primary: "Source decision queue", secondary: "Active committee packets", tertiary: "Independent positions" },
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
  return first(row, ["next_required_action", "recommended_action", "decision_question", "requested_action", "policy_statement", "proposed_change", "role_scope", "objective", "thesis", "coordination_question", "next_action", "notes", "publisher", "interpretation", "rationale"], "Evidence available in the live warehouse.");
}

function rowOwner(row: LiveRow): string {
  return first(row, ["owner_agent", "chair_agent", "agent_name", "task_owner_agent", "lead_agent", "department_name", "provider", "created_by"], "AI Office");
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
  const [selectedAgent, setSelectedAgent] = useState(() => new URLSearchParams(window.location.search).get("agent") ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [skillKey, setSkillKey] = useState("");
  const [busy, setBusy] = useState("");
  const employees = useMemo(() => snapshot.primary.filter((row) => department === "all" || text(row, "department", "") === department), [department, snapshot.primary]);
  const selected = snapshot.primary.find((row) => text(row, "agent_name", "") === selectedAgent) ?? employees[0];
  const selectedName = text(selected, "agent_name", "");
  const selectedSkills = useMemo(() => jsonRows(selected?.skills), [selected]);
  const selectedHistory = useMemo(() => (snapshot.worker_history ?? []).filter((row) => text(row, "agent_name", "") === selectedName).slice(0, 8), [selectedName, snapshot.worker_history]);
  const selectedCost = useMemo(() => (snapshot.cost_quality ?? []).find((row) => text(row, "agent_name", "") === selectedName), [selectedName, snapshot.cost_quality]);

  const chooseAgent = useCallback((agentName: string) => {
    setSelectedAgent(agentName);
    const url = new URL(window.location.href);
    if (agentName) url.searchParams.set("agent", agentName);
    else url.searchParams.delete("agent");
    window.history.replaceState({}, "", url);
  }, []);

  useEffect(() => {
    if (!selectedName) return;
    if (selectedAgent !== selectedName) chooseAgent(selectedName);
  }, [chooseAgent, selectedAgent, selectedName]);

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
        <label><span>Department</span><select value={department} onChange={(event) => { setDepartment(event.target.value); chooseAgent(""); }}><option value="all">All departments</option>{(snapshot.departments ?? []).map((row) => <option key={text(row, "department_key")} value={text(row, "department_key")}>{text(row, "department_name")}</option>)}</select></label>
        <label><span>Employee</span><select value={selectedName} onChange={(event) => chooseAgent(event.target.value)}>{employees.map((row) => <option key={text(row, "agent_name")} value={text(row, "agent_name")}>{text(row, "display_title")} · {text(row, "agent_name")}</option>)}</select></label>
        <button className="mini-action-button" disabled={Boolean(busy)} onClick={() => void runSchedules()} type="button"><Clock3 size={14}/>{busy === "schedules" ? "Scheduling" : "Run due schedules"}</button>
        <button className="mini-action-button" disabled={Boolean(busy)} onClick={() => void runWorkers()} type="button"><Play size={14}/>{busy === "workers" ? "Working" : "Run workers"}</button>
      </div>
      {selected ? <div className="agent-office-selected" style={{ "--agent-color": text(selected, "color_token", "#0f766e") } as CSSProperties}>
        <div className="agent-profile-identity"><span>{text(selected, "character_name", selectedName).slice(0, 2).toUpperCase()}</span><div><small>{text(selected, "department_name")}</small><h3>{text(selected, "display_title")}</h3><p>{selectedName} · reports to {text(selected, "reports_to_agent")}</p></div></div>
        <div aria-label="Selected employee operating facts" className="agent-profile-facts" role="region" tabIndex={0}><div><span>Status</span><strong>{text(selected, "live_state").replace(/_/g, " ")}</strong></div><div><span>Readiness</span><strong>{text(selected, "operating_readiness_score")}%</strong></div><div><span>Model</span><strong>{text(selected, "assigned_model")}</strong></div><div><span>Route</span><strong>{text(selected, "primary_route").replace(/_/g, " ")}</strong></div><div><span>Mailbox</span><strong>{text(selected, "mailbox_address")}</strong></div></div>
        <p className="agent-profile-mandate">{text(selected, "role_scope")}</p>
        <p className="agent-profile-persona">{text(selected, "persona")}</p>
        <div className="agent-profile-tags">{textList(selected.mental_models).map((item) => <span key={item}>{item.replace(/_/g, " ")}</span>)}{selectedSkills.map((item) => <span key={text(item, "skill_key")}>{text(item, "skill_name")}</span>)}</div>
        <div className="agent-profile-control"><div><span>Reliability</span><strong>{text(selected, "reliability_score", "0")}%</strong><small>{text(selected, "reliability_confidence", "insufficient history").replace(/_/g, " ")}</small></div><div><span>Cost policy</span><strong>{text(selectedCost, "cap_status", "controlled")}</strong><small>${text(selectedCost, "cost_month_usd", "0")} this month · cloud approval {text(selectedCost, "cloud_requires_approval", "true")}</small></div><div><span>Recent output</span><strong>{selectedHistory.length}</strong><small>{text(selectedHistory[0], "task_title", "No completed output yet")}</small></div></div>
        <div className="agent-profile-history">{selectedHistory.map((row) => <article key={text(row, "id")}><div><strong>{text(row, "task_title")}</strong><small>{text(row, "skill_name")} · {rowTime(row)}</small></div><span className={`status-pill status-${tone(text(row, "status"))}`}>{text(row, "status")}</span></article>)}{!selectedHistory.length ? <p>No worker output has been recorded for this employee.</p> : null}</div>
      </div> : null}
      <form className="agent-assignment-form" onSubmit={assignWork}>
        <div><Mail size={15}/><strong>Assign through Charlie</strong><small>Creates an internal message, then Jarvis materializes the role-scoped task.</small></div>
        <input aria-label="Assignment subject" onChange={(event) => setSubject(event.target.value)} placeholder="Assignment subject" required value={subject}/>
        <textarea aria-label="Assignment objective" onChange={(event) => setBody(event.target.value)} placeholder="Objective, required evidence, output, deadline, and decision boundary" required rows={3} value={body}/>
        <div><select aria-label="Assignment skill" onChange={(event) => setSkillKey(event.target.value)} value={skillKey}><option value="">Automatic skill routing</option>{selectedSkills.map((item) => <option key={text(item, "skill_key")} value={text(item, "skill_key")}>{text(item, "skill_name")}</option>)}</select><select aria-label="Assignment priority" onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select><button className="primary-button" disabled={!selectedName || Boolean(busy)} type="submit"><Send size={14}/>{busy === "message" ? "Routing" : "Assign work"}</button></div>
      </form>
    </section>
    <section className="terminal-pane agent-roster-pane"><header><div><Users size={15}/><h3>AI employee roster</h3></div><strong>{employees.length} visible</strong></header><div className="agent-roster-grid">{employees.map((row) => <button className={`agent-roster-card ${text(row, "agent_name") === selectedName ? "is-selected" : ""}`} key={text(row, "agent_name")} onClick={() => chooseAgent(text(row, "agent_name"))} style={{ "--agent-color": text(row, "color_token", "#0f766e") } as CSSProperties} type="button"><span className={`status-dot status-${tone(text(row, "readiness_status"))}`}/><div><strong>{text(row, "display_title")}</strong><small>{text(row, "agent_name")} · {text(row, "department_name")}</small><p>{text(row, "current_work_title", text(row, "role_scope"))}</p></div><b>{text(row, "operating_readiness_score")}%</b></button>)}</div></section>
    <div className="agent-governance-grid">
      <section className="terminal-pane"><header><div><Clock3 size={15}/><h3>Operating schedules</h3></div><strong>{snapshot.schedules?.length ?? 0}</strong></header><div aria-label="Agent operating schedules" className="agent-schedule-list" role="region" tabIndex={0}>{(snapshot.schedules ?? []).map((row) => <article key={text(row, "schedule_key")}><div><strong>{text(row, "schedule_name")}</strong><small>{text(row, "owner_agent")} · {text(row, "skill_name")}</small></div><span className={`status-pill status-${tone(text(row, "schedule_state"))}`}>{text(row, "schedule_state").replace(/_/g, " ")}</span><time>{rowTime(row)}</time></article>)}</div></section>
      <section className="terminal-pane"><header><div><Scale size={15}/><h3>Committee constitution</h3></div><strong>{snapshot.committees?.length ?? 0}</strong></header><div aria-label="Committee constitutions" className="agent-committee-list" role="region" tabIndex={0}>{(snapshot.committees ?? []).map((row) => <article key={text(row, "committee_key")}><div><strong>{text(row, "committee_name")}</strong><small>Chair: {text(row, "chair_agent")} · quorum {text(row, "quorum")} · {text(row, "member_count")} members</small><p>{text(row, "mandate")}</p></div><span>{text(row, "human_final_required", "true") === "true" ? "human final" : "advisory"}</span></article>)}</div></section>
    </div>
  </>;
}

function CommitteeRoomControl({ snapshot, refresh, setError, setNotice }: {
  snapshot: DepartmentTerminalSnapshot;
  refresh: () => Promise<void>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
}) {
  const [itemKey, setItemKey] = useState(() => text(snapshot.primary[0], "committee_item_key", ""));
  const [packetId, setPacketId] = useState(() => text(snapshot.secondary?.[0], "id", ""));
  const [question, setQuestion] = useState("");
  const [recommendation, setRecommendation] = useState("");
  const [minutes, setMinutes] = useState("");
  const [dissent, setDissent] = useState("");
  const [humanDecision, setHumanDecision] = useState("");
  const [humanRationale, setHumanRationale] = useState("");
  const [busy, setBusy] = useState("");
  const selectedItem = snapshot.primary.find((row) => text(row, "committee_item_key", "") === itemKey) ?? snapshot.primary[0];
  const selectedPacket = snapshot.secondary?.find((row) => text(row, "id", "") === packetId) ?? snapshot.secondary?.[0];
  const decisionOptions = textList(selectedPacket?.decision_options);
  const packetPositions = (snapshot.tertiary ?? []).filter((row) => text(row, "packet_id", "") === text(selectedPacket, "id", ""));
  const packetFollowups = (snapshot.followups ?? []).filter((row) => text(row, "packet_id", "") === text(selectedPacket, "id", ""));

  useEffect(() => {
    if (!selectedItem) return;
    setQuestion((current) => current || `What decision should the ${text(selectedItem, "committee_lane")} make on ${text(selectedItem, "subject_name", text(selectedItem, "title"))}, under what conditions, and what evidence would invalidate it?`);
  }, [itemKey, selectedItem]);

  useEffect(() => {
    if (selectedPacket && packetId !== text(selectedPacket, "id", "")) setPacketId(text(selectedPacket, "id", ""));
    const firstDecision = decisionOptions[0] ?? "";
    setRecommendation(firstDecision);
    setHumanDecision(firstDecision);
  }, [packetId, selectedPacket?.id]);

  const runAction = async (key: string, action: () => Promise<unknown>, notice: string) => {
    setBusy(key); setError(""); setNotice("");
    try { await action(); setNotice(notice); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : `${key} failed`); }
    finally { setBusy(""); }
  };

  const openPacket = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedItem) return;
    await runAction("open", () => openCommitteePacket({
      committee_item_key: text(selectedItem, "committee_item_key"),
      title: text(selectedItem, "title"), decision_question: question,
      opened_by: "Charlie Munger", actor: "Charlie Munger",
      evidence: [{ source_view: text(selectedItem, "source_view"), source_id: selectedItem.source_id }]
    }), "Charlie opened the committee packet and dispatched sealed independent position assignments.");
  };

  const synthesize = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedPacket) return;
    await runAction("synthesize", () => synthesizeCommitteeSession({
      packet_id: Number(selectedPacket.id), chair_agent: text(selectedPacket, "chair_agent"),
      recommendation, minutes, dissent_summary: dissent,
      conditions: [{ condition: "No capital or execution action follows from this committee recommendation without its separate governed workflow." }]
    }), "Committee recommendation and minutes recorded. The packet now awaits Devarsh's separate final decision.");
  };

  const decide = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedPacket) return;
    await runAction("decision", () => recordCommitteeHumanDecision({
      packet_id: Number(selectedPacket.id), decision: humanDecision,
      decided_by: "Devarsh", rationale: humanRationale
    }), "Human final decision recorded. Capital and broker execution remain separately locked.");
  };

  return <section className="committee-operator-grid">
    <section className="terminal-pane committee-packet-builder">
      <header><div><Scale size={15}/><h3>Open decision packet</h3></div><strong>sealed first pass</strong></header>
      <form className="operator-form" onSubmit={openPacket}>
        <label className="span-form"><span>Source decision item</span><select value={text(selectedItem, "committee_item_key", "")} onChange={(event)=>{setItemKey(event.target.value);setQuestion("");}}>{snapshot.primary.map((row)=><option key={text(row,"committee_item_key")} value={text(row,"committee_item_key")}>{text(row,"committee_lane")} · {text(row,"subject_name",text(row,"title"))}</option>)}</select></label>
        <label className="span-form"><span>Decision question</span><textarea required rows={4} value={question} onChange={(event)=>setQuestion(event.target.value)}/></label>
        <button className="primary-button span-form" disabled={!selectedItem||Boolean(busy)} type="submit"><Send size={14}/>{busy==="open"?"Dispatching":"Open packet and dispatch members"}</button>
        <p className="form-guard span-form">Each required member receives a role-scoped task and mailbox request. Peer positions remain sealed until quorum.</p>
      </form>
    </section>
    <section className="terminal-pane committee-session-console">
      <header><div><Users size={15}/><h3>Session control</h3></div><strong>{snapshot.secondary?.length ?? 0} packets</strong></header>
      {selectedPacket ? <>
        <label className="terminal-select-label"><span>Packet</span><select value={text(selectedPacket,"id")} onChange={(event)=>setPacketId(event.target.value)}>{snapshot.secondary?.map((row)=><option key={text(row,"id")} value={text(row,"id")}>{text(row,"committee_name")} · {text(row,"title")}</option>)}</select></label>
        <div className="committee-session-metrics"><div><span>Status</span><strong>{text(selectedPacket,"packet_status").replace(/_/g," ")}</strong></div><div><span>Quorum</span><strong>{text(selectedPacket,"counted_positions","0")} / {text(selectedPacket,"quorum","0")}</strong></div><div><span>Challenges</span><strong>{text(selectedPacket,"challenge_count","0")}</strong></div><div><span>Follow-ups</span><strong>{text(selectedPacket,"open_followup_count","0")}</strong></div></div>
        {text(selectedPacket,"packet_status")==="deliberating"?<form className="operator-form committee-synthesis-form" onSubmit={synthesize}><label><span>Recommendation</span><select required value={recommendation} onChange={(event)=>setRecommendation(event.target.value)}>{decisionOptions.map((item)=><option key={item}>{item}</option>)}</select></label><label className="span-form"><span>Minutes and reasoning</span><textarea required rows={4} value={minutes} onChange={(event)=>setMinutes(event.target.value)}/></label><label className="span-form"><span>Dissent summary</span><textarea rows={2} value={dissent} onChange={(event)=>setDissent(event.target.value)}/></label><button className="primary-button span-form" disabled={Boolean(busy)} type="submit">{busy==="synthesize"?"Recording":"Record chair synthesis"}</button></form>:null}
        {text(selectedPacket,"packet_status")==="awaiting_human"?<form className="operator-form committee-synthesis-form" onSubmit={decide}><label><span>Devarsh decision</span><select required value={humanDecision} onChange={(event)=>setHumanDecision(event.target.value)}>{decisionOptions.map((item)=><option key={item}>{item}</option>)}</select></label><label className="span-form"><span>Final rationale</span><textarea required rows={3} value={humanRationale} onChange={(event)=>setHumanRationale(event.target.value)}/></label><button className="primary-button span-form" disabled={Boolean(busy)} type="submit">{busy==="decision"?"Recording":"Record human final"}</button></form>:null}
        <div className="committee-position-preview">{packetPositions.map((row)=><article key={text(row,"id")}><div><strong>{text(row,"display_title")} · {text(row,"stance").replace(/_/g," ")}</strong><p>{text(row,"recommendation").replace(/_/g," ")}</p></div><span>{text(row,"confidence")}%</span></article>)}{!packetPositions.length?<p>Independent position assignments are waiting in member inboxes.</p>:null}</div>
        {packetFollowups.length?<div className="committee-followup-preview">{packetFollowups.map((row)=><span key={text(row,"id")}>{text(row,"owner_title")} · {text(row,"title")} · {text(row,"status")}</span>)}</div>:null}
      </>:<p className="empty-state">Open a packet from the live source decision queue.</p>}
    </section>
  </section>;
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
      {mode === "committees" && snapshot ? <CommitteeRoomControl refresh={refresh} setError={setError} setNotice={setNotice} snapshot={snapshot}/> : mode === "agents" && snapshot ? <AgentOfficeControl refresh={refresh} setError={setError} setNotice={setNotice} snapshot={snapshot}/> : <section className="terminal-pane terminal-primary-pane">
        <header><div><Activity size={15} /><h3>{definition.primary}</h3></div><strong>{snapshot?.primary.length ?? 0}</strong></header>
        <TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.primary ?? []} />
      </section>}
      {definition.secondary ? <section className="terminal-pane"><header><h3>{definition.secondary}</h3><strong>{snapshot?.secondary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.secondary ?? []} /></section> : null}
      {definition.tertiary ? <section className="terminal-pane"><header><h3>{definition.tertiary}</h3><strong>{snapshot?.tertiary?.length ?? 0}</strong></header><TerminalRows mode={mode} onEvidence={setEvidence} rows={snapshot?.tertiary ?? []} /></section> : null}
      <EvidenceDrawer onChanged={refresh} onClose={() => setEvidence(null)} selection={evidence} />
    </div>
  );
}
