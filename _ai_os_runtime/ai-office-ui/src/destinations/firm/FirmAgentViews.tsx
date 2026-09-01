/**
 * Firm views — Agents, Departments, Committees, Governance, Models, System, Library.
 *
 * Each is a real, data-backed screen (not a stub). They share the office +
 * system-health snapshots and render dense, evidence-linked tables.
 */

import React from "react";
import { useParams } from "react-router-dom";
import {
  Users, Building2, Gavel, ShieldCheck, Cpu, Activity, Library,
  Inbox, ChevronRight, MessageSquare, Play, Send, Search, RefreshCw,
  ClipboardList,
} from "lucide-react";
import { Panel, DataTable, StatusPill, Badge, Empty, MetricTile, Metric, Avatar, ScrollList, Button, Checkbox, Drawer, Field, Select, TextArea, TextInput } from "../../system/primitives";
import { useAction, useOfficeSnapshot, useSystemHealth, useDepartmentTerminal, useReports, useBlueprintRequirements } from "../../data/queries";
import { useApproveResearchModelPreflight, useConfigurePublicResearchCanary, useCreateAgentMessage, useDelegateAgentTask, usePreparePublicResearchCanary, useReconcileBlueprintEvidence, useResolveLongTermCommittee, useResolveSpecialSituationDecision, useResolveStrategyCommittee, useReviewBlueprintEvidence, useReviewPromotePublicResearchCanary, useRunAgentWorker, useRunPublicResearchCanary } from "../../data/actions";
import { useUIStore } from "../../store";
import { text, num, formatRelative, initials, value } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

/* ============================================================
 * AGENTS VIEW
 * ============================================================ */
export function AgentsView() {
  const { data, isLoading } = useOfficeSnapshot();
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);

  const agents = React.useMemo(() => {
    const profiles = new Map((data?.agents ?? []).map((row) => [text(row, "agent_name"), row]));
    const rows = (data?.live_office_agent_activity ?? []).map((row) => ({
      ...(profiles.get(text(row, "agent_name")) ?? {}),
      ...row,
    }));
    const seen = new Set(rows.map((row) => text(row, "agent_name")));
    for (const profile of data?.agents ?? []) {
      if (!seen.has(text(profile, "agent_name"))) rows.push(profile);
    }
    return rows;
  }, [data]);
  const working = agents.filter((row) => ["active", "working", "running", "executing", "in_progress", "queued", "processing", "waiting_approval"]
    .some((state) => text(row, "live_state", text(row, "latest_worker_status", "idle")).toLowerCase().includes(state))).length;

  return (
    <div className="aios-destination">
      <Header icon={Users} code="AGENTS" title="Agents & Employees" subtitle="The full live roster, with every registered department, specialist, skill, and model route." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Agents" value={agents.length} /></MetricTile>
        <MetricTile tone={working ? "ok" : "warn"}><Metric label="Working Now" value={working} /></MetricTile>
        <MetricTile><Metric label="Departments" value={new Set(agents.map((a) => text(a, "department_key", text(a, "department"))).filter(Boolean)).size} /></MetricTile>
        <MetricTile><Metric label="Active Messages" value={data?.agent_messages?.length ?? 0} /></MetricTile>
      </div>
      <Panel icon={Users} title="Roster">
        {isLoading ? (
          <div style={{ padding: "var(--space-4)" }}>Loading…</div>
        ) : agents.length === 0 ? (
          <Empty icon={Users} title="No agents loaded" />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            {agents.map((agent, i) => {
              const name = text(agent, "agent_name", text(agent, "name", `Agent ${i}`));
              const dept = text(agent, "department_name", text(agent, "department_key", text(agent, "department")));
              const role = text(agent, "display_title", text(agent, "role_scope"));
              const status = text(agent, "live_state", text(agent, "latest_worker_status", "idle"));
              const currentWork = text(agent, "current_work_title", text(agent, "current_task_title", "No active assignment"));
              return (
                <div
                  key={i}
                  className="aios-agent-card"
                  style={{ padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer" }}
                  onClick={() => setAssistantScope({ agentKey: text(agent, "agent_key", name), agentName: name })}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                    <Avatar initials={initials(name)} size="md" ring={status.toLowerCase().includes("active") ? "ok" : "idle"} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: "var(--text-sm)", color: "var(--text)" }}>{name}</div>
                      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{dept}</div>
                    </div>
                    <StatusPill status={status} />
                  </div>
                  {role && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{role}</div>}
                  <div style={{ marginTop: "var(--space-2)", fontSize: "var(--text-xs)" }}>
                    <strong style={{ display: "block", color: "var(--text)", marginBottom: 3 }}>{currentWork}</strong>
                    <span style={{ color: "var(--text-muted)" }}>{num(agent, "open_task_count")} tasks · {num(agent, "open_inbox_count")} inbox</span>
                  </div>
                  <div style={{ marginTop: "var(--space-2)", display: "flex", gap: "var(--space-1)", color: "var(--accent)", fontSize: "var(--text-xs)" }}>
                    <MessageSquare size={11} /> Talk or assign work
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}

/* ============================================================
 * DEPARTMENTS VIEW
 * ============================================================ */
export function DepartmentsView() {
  const { data, isLoading } = useDepartmentTerminal("agents");
  const createMessage = useCreateAgentMessage();
  const runWorker = useRunAgentWorker();
  const pushToast = useUIStore((s) => s.pushToast);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const departments = data?.departments ?? [];
  const employees = data?.primary ?? [];
  const [selected, setSelected] = React.useState("all");
  const [target, setTarget] = React.useState("");
  const [assignment, setAssignment] = React.useState("");

  const departmentEmployees = React.useMemo(() => employees.filter((row) => {
    if (selected === "all") return true;
    return text(row, "department") === selected || text(row, "department_name") === selected;
  }), [employees, selected]);
  const employeeNames = React.useMemo(() => new Set(departmentEmployees.map((row) => text(row, "agent_name"))), [departmentEmployees]);
  const queue = (data?.secondary ?? []).filter((row) => selected === "all" || employeeNames.has(text(row, "agent_name", text(row, "owner_agent"))));
  const messages = (data?.tertiary ?? []).filter((row) => selected === "all" || employeeNames.has(text(row, "to_agent")) || employeeNames.has(text(row, "from_agent")));
  const active = departmentEmployees.filter((row) => text(row, "live_state", "idle") !== "idle").length;
  const openTasks = departmentEmployees.reduce((sum, row) => sum + num(row, "open_task_count", 0), 0);
  const openInbox = departmentEmployees.reduce((sum, row) => sum + num(row, "open_inbox_count", 0), 0);
  const departmentHeadcount = React.useCallback((department: LiveRow) => {
    const keys = new Set([
      text(department, "department"),
      text(department, "department_name"),
    ].filter(Boolean).map((value) => value.toLowerCase()));
    return employees.filter((employee) => [
      text(employee, "department"),
      text(employee, "department_name"),
    ].some((value) => keys.has(value.toLowerCase()))).length;
  }, [employees]);

  React.useEffect(() => {
    if (!target || !departmentEmployees.some((row) => text(row, "agent_name") === target)) {
      setTarget(text(departmentEmployees[0] ?? {}, "agent_name", ""));
    }
  }, [departmentEmployees, target]);

  function assignWork() {
    if (!target || !assignment.trim()) {
      pushToast({ title: "Agent and objective required", tone: "warn", duration: 2500 });
      return;
    }
    createMessage.mutate({
      to_agent: target,
      subject: assignment.trim().slice(0, 120),
      message: assignment.trim(),
      priority: "medium",
      workspace: "departments",
      metadata: { source: "department_cockpit", selected_department: selected },
    }, {
      onSuccess: () => { setAssignment(""); pushToast({ title: "Work assigned", message: target, tone: "ok", duration: 3000 }); },
      onError: (error) => pushToast({ title: "Assignment failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  }

  function processQueue() {
    runWorker.mutate({ actor: "Devarsh", limit: 5 }, {
      onSuccess: () => pushToast({ title: "Agent queue processed", tone: "ok", duration: 3000 }),
      onError: (error) => pushToast({ title: "Worker failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <div className="aios-destination">
      <Header icon={Building2} code="DEPTS" title="Department Operations" subtitle="Live employees, assignments, inbox traffic, worker state, readiness, and model accountability." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Send} title="Work Command" actions={<Badge tone={createMessage.isPending ? "warn" : "ok"}>{createMessage.isPending ? "Sending" : "Ready"}</Badge>}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            <Field label="Employee"><Select value={target} onChange={(event) => setTarget(event.target.value)}>{departmentEmployees.map((row) => <option key={text(row, "agent_name")} value={text(row, "agent_name")}>{text(row, "agent_name")} · {text(row, "display_title", text(row, "department_name", text(row, "department")))}</option>)}</Select></Field>
            <Field label="Objective"><TextArea value={assignment} onChange={(event) => setAssignment(event.target.value)} rows={4} placeholder="State the decision or output, required evidence, deadline, and handoff…" /></Field>
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="primary" icon={Send} onClick={assignWork} disabled={createMessage.isPending}>Assign real work</Button>
              <Button icon={Play} onClick={processQueue} disabled={runWorker.isPending}>Process queue</Button>
            </div>
          </div>
        </Panel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(130px, 1fr))", gap: "var(--space-3)" }}>
          <MetricTile><Metric label="Employees" value={departmentEmployees.length} /></MetricTile>
          <MetricTile tone={active ? "ok" : "warn"}><Metric label="Working Now" value={active} /></MetricTile>
          <MetricTile tone={openTasks ? "warn" : "ok"}><Metric label="Open Tasks" value={openTasks} /></MetricTile>
          <MetricTile tone={openInbox ? "warn" : "ok"}><Metric label="Open Inbox" value={openInbox} /></MetricTile>
          <MetricTile><Metric label="Queue Rows" value={queue.length} /></MetricTile>
          <MetricTile><Metric label="Messages" value={messages.length} /></MetricTile>
        </div>
      </div>
      <Panel icon={Building2} title="Operating Scope" actions={
        <Select value={selected} onChange={(event) => setSelected(event.target.value)} style={{ minWidth: 240 }}>
          <option value="all">All departments</option>
          {departments.map((row, index) => {
            const value = text(row, "department", text(row, "department_name", `dept-${index}`));
            return <option key={value} value={value}>{text(row, "department_name", value)}</option>;
          })}
        </Select>
      }>
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : departments.length === 0 ? <Empty icon={Building2} title="No live department rows" /> : (
          <DataTable
            columns={[
              { key: "name", header: "Department", render: (r) => <strong>{text(r, "department_name", text(r, "department"))}</strong> },
              { key: "lead", header: "Lead", render: (r) => text(r, "lead_agent", text(r, "department_lead", "—")) },
              { key: "headcount", header: "Employees", align: "right", render: (r) => departmentHeadcount(r) },
              { key: "mandate", header: "Mandate", render: (r) => text(r, "mission", text(r, "mandate", "—")) },
            ]}
            rows={selected === "all" ? departments : departments.filter((row) => text(row, "department", text(row, "department_name")) === selected)}
            rowKey={(r, i) => text(r, "department", `dept-${i}`)}
          />
        )}
      </Panel>

      <Panel icon={Users} title="Employee Operating Board">
        {departmentEmployees.length === 0 ? <Empty icon={Users} title="No employees in this scope" /> : (
          <DataTable
            columns={[
              { key: "agent", header: "Employee", render: (r) => <button style={{ color: "var(--accent)", background: "none", border: 0, cursor: "pointer", fontWeight: 600 }} onClick={() => setAssistantScope({ agentKey: text(r, "agent_name"), agentName: text(r, "agent_name") })}>{text(r, "agent_name")}</button> },
              { key: "title", header: "Role & Voice", render: (r) => <div><strong>{text(r, "display_title", text(r, "role_scope", "—"))}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 3 }}>{text(r, "persona", "Fact-first specialist").slice(0, 110)}</div></div> },
              { key: "work", header: "Current Work", render: (r) => text(r, "current_work_title", "No active assignment") },
              { key: "tasks", header: "Tasks", align: "right", render: (r) => num(r, "open_task_count", 0) },
              { key: "inbox", header: "Inbox", align: "right", render: (r) => num(r, "open_inbox_count", 0) },
              { key: "model", header: "Model", render: (r) => text(r, "assigned_model", text(r, "primary_route", "—")) },
              { key: "readiness", header: "Readiness", render: (r) => <StatusPill status={text(r, "readiness_status", text(r, "model_status", "unknown"))} /> },
            ]}
            rows={departmentEmployees}
            rowKey={(r, i) => text(r, "agent_name", `agent-${i}`)}
          />
        )}
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Activity} title="Live Work Queue" actions={<Badge tone={queue.length ? "warn" : "ok"}>{queue.length}</Badge>}>
          {queue.length === 0 ? <Empty icon={Activity} title="No queued work in this scope" /> : (
            <DataTable
              columns={[
                { key: "work", header: "Work", render: (r) => <strong>{text(r, "task_title", text(r, "subject", text(r, "title", "Queued task")))}</strong> },
                { key: "owner", header: "Owner", render: (r) => text(r, "agent_name", text(r, "owner_agent", text(r, "to_agent", "—"))) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", text(r, "processing_status", "queued"))} /> },
                { key: "updated", header: "Updated", render: (r) => formatRelative(text(r, "updated_at", text(r, "created_at"))) },
              ]}
              rows={queue.slice(0, 30)}
              rowKey={(r, i) => String(text(r, "task_id", text(r, "id", i)))}
            />
          )}
        </Panel>
      </div>

      <Panel icon={Inbox} title="Inter-agent Conversation" actions={<Badge>{messages.length}</Badge>}>
        {messages.length === 0 ? <Empty icon={Inbox} title="No messages in this scope" /> : (
          <DataTable
            columns={[
              { key: "subject", header: "Subject", render: (r) => <strong>{text(r, "subject", "Agent message")}</strong> },
              { key: "from", header: "From", render: (r) => text(r, "from_agent", "—") },
              { key: "to", header: "To", render: (r) => text(r, "to_agent", "—") },
              { key: "priority", header: "Priority", render: (r) => <StatusPill status={text(r, "priority", "medium")} /> },
              { key: "state", header: "State", render: (r) => <StatusPill status={text(r, "processing_status", text(r, "status", "unread"))} /> },
              { key: "time", header: "Sent", render: (r) => formatRelative(text(r, "created_at")) },
            ]}
            rows={messages.slice(0, 40)}
            rowKey={(r, i) => String(text(r, "id", i))}
          />
        )}
      </Panel>
    </div>
  );
}

/* ============================================================
 * COMMITTEES VIEW
 * ============================================================ */
export function CommitteesView() {
  const { data, isLoading } = useOfficeSnapshot();
  const openEvidence = useUIStore((s) => s.openEvidence);
  const pushToast = useUIStore((s) => s.pushToast);
  const longTermDecision = useResolveLongTermCommittee();
  const strategyDecision = useResolveStrategyCommittee();
  const specialDecision = useResolveSpecialSituationDecision();
  const [selected, setSelected] = React.useState<LiveRow | null>(null);
  const [decision, setDecision] = React.useState("research_more");
  const [notes, setNotes] = React.useState("");
  const items = data?.committee_room_items ?? [];
  const sourceView = selected ? text(selected, "source_view") : "";
  const sourceId = selected ? num(selected, "source_id", 0) : 0;
  const decisionOptions = sourceView.includes("strategy")
    ? ["reject", "retest", "research_more", "approve_paper_monitor"]
    : sourceView.includes("long_term")
      ? ["reject", "research_more", "monitor", "approve_watchlist", "approve_hold"]
      : ["reject", "monitor", "research_more", "committee_review"];
  const busy = longTermDecision.isPending || strategyDecision.isPending || specialDecision.isPending;

  const review = (item: LiveRow) => {
    const recommended = text(item, "recommended_decision", "research_more");
    const view = text(item, "source_view");
    const allowed = view.includes("strategy")
      ? ["reject", "retest", "research_more", "approve_paper_monitor"]
      : view.includes("long_term")
        ? ["reject", "research_more", "monitor", "approve_watchlist", "approve_hold"]
        : ["reject", "monitor", "research_more", "committee_review"];
    setSelected(item);
    setDecision(allowed.includes(recommended) ? recommended : "research_more");
    setNotes("");
  };

  const submitDecision = () => {
    if (!selected || !sourceId || !notes.trim()) {
      pushToast({ title: "Decision rationale is required", tone: "warn", duration: 3000 });
      return;
    }
    const callbacks = {
      onSuccess: () => { pushToast({ title: "Committee decision recorded", message: text(selected, "title"), tone: "ok", duration: 4000 }); setSelected(null); },
      onError: (error: Error) => pushToast({ title: "Committee decision failed", message: error.message, tone: "risk", duration: 5000 }),
    };
    if (sourceView.includes("strategy")) strategyDecision.mutate({ committee_review_id: sourceId, decision, notes, actor: "Devarsh" }, callbacks);
    else if (sourceView.includes("long_term")) longTermDecision.mutate({ review_id: sourceId, decision, notes, actor: "Devarsh" }, callbacks);
    else specialDecision.mutate({ special_memo_id: sourceId, decision, notes, actor: "Devarsh" }, callbacks);
  };

  return (
    <div className="aios-destination">
      <Header icon={Gavel} code="COMM" title="Committee Room" subtitle="Evidence-backed investment reviews, dissent, recommendations, and human decisions." />
      <Panel icon={Gavel} title="Committee Queue" actions={items.length > 0 ? <Badge tone="warn" dot>{items.length}</Badge> : undefined}>
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : items.length === 0 ? (
          <Empty icon={Gavel} title="No open committee reviews" />
        ) : (
          <DataTable
            columns={[
              { key: "title", header: "Review", render: (item) => <strong>{text(item, "title", "Committee review")}</strong> },
              { key: "lane", header: "Committee", render: (item) => text(item, "committee_lane", "—") },
              { key: "state", header: "State", render: (item) => <StatusPill status={text(item, "room_state", text(item, "review_status", "open"))} /> },
              { key: "recommendation", header: "Recommendation", render: (item) => text(item, "recommended_decision", "—") },
              { key: "gaps", header: "Evidence gaps", align: "right", render: (item) => num(item, "evidence_gap_count", 0) + num(item, "required_followup_count", 0) },
              { key: "updated", header: "Updated", render: (item) => formatRelative(text(item, "latest_activity_at", text(item, "updated_at"))) },
              { key: "actions", header: "Actions", render: (item) => <div style={{ display: "flex", gap: "var(--space-2)" }}><Button size="sm" variant="ghost" onClick={() => openEvidence({ kind: "committee", key: text(item, "committee_item_key"), title: text(item, "title", "Committee review") })}>Evidence</Button><Button size="sm" variant="primary" onClick={() => review(item)} disabled={Boolean(text(item, "final_decision"))}>Decide</Button></div> },
            ]}
            rows={items}
            rowKey={(item, index) => text(item, "committee_item_key", String(index))}
          />
        )}
      </Panel>

      <Drawer open={selected !== null} onClose={() => setSelected(null)} title={selected ? text(selected, "title", "Committee decision") : "Committee decision"} icon={Gavel} width={560}
        footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={() => setSelected(null)}>Cancel</Button><Button variant="primary" icon={Gavel} onClick={submitDecision} disabled={busy || !notes.trim()}>Record decision</Button></div>}>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div><StatusPill status={selected ? text(selected, "room_state", "review") : "review"} /> <span style={{ marginLeft: "var(--space-2)", color: "var(--text-muted)" }}>{selected ? text(selected, "committee_lane") : ""}</span></div>
          <Field label="Decision"><Select value={decision} onChange={(event) => setDecision(event.target.value)}>{decisionOptions.map((option) => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}</Select></Field>
          <Field label="Rationale" required><TextArea value={notes} onChange={(event) => setNotes(event.target.value)} rows={6} placeholder="State the evidence, dissent considered, conditions, and why this decision is appropriate." /></Field>
          <Button variant="ghost" onClick={() => selected && openEvidence({ kind: "committee", key: text(selected, "committee_item_key"), title: text(selected, "title", "Committee review") })}>Open full evidence</Button>
        </div>
      </Drawer>
    </div>
  );
}

/* ============================================================
 * GOVERNANCE VIEW
 * ============================================================ */
export function GovernanceView() {
  const [status, setStatus] = React.useState("");
  const [domainKey, setDomainKey] = React.useState("");
  const [priority, setPriority] = React.useState("");
  const registry = useBlueprintRequirements({ status, domainKey, priority });
  const delegate = useDelegateAgentTask();
  const reconcile = useReconcileBlueprintEvidence();
  const reviewEvidence = useReviewBlueprintEvidence();
  const pushToast = useUIStore((s) => s.pushToast);
  const openEvidence = useUIStore((s) => s.openEvidence);
  const [selectedRequirement, setSelectedRequirement] = React.useState<LiveRow | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = React.useState(0);
  const [deliveryStatus, setDeliveryStatus] = React.useState<"partial" | "done">("partial");
  const [reviewRationale, setReviewRationale] = React.useState("");
  const data = registry.data;
  const summary = new Map((data?.summary ?? []).map((row) => [text(row, "metric"), num(row, "value")]));
  const requirements = data?.requirements ?? [];
  const domains = data?.domains ?? [];

  const selectedEvidence = selectedRequirement
    ? value<LiveRow[]>(selectedRequirement, "evidence_links", [])
    : [];

  const scanEvidence = () => {
    reconcile.mutate({ actor: "Jarvis" }, {
      onSuccess: (result) => pushToast({
        title: "Evidence scan complete",
        message: `${num(result, "candidate_count", 0)} candidate links require review.`,
        tone: num(result, "candidate_count", 0) ? "warn" : "ok",
        duration: 3500,
      }),
      onError: (error) => pushToast({ title: "Evidence scan failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  };

  const openEvidenceReview = (row: LiveRow) => {
    const links = value<LiveRow[]>(row, "evidence_links", []);
    const firstCandidate = links.find((item) => text(item, "evidence_status") === "candidate") ?? links[0];
    setSelectedRequirement(row);
    setSelectedEvidenceId(num(firstCandidate ?? {}, "id", 0));
    setDeliveryStatus(text(row, "current_status") === "done" ? "done" : "partial");
    setReviewRationale("");
  };

  const submitEvidenceReview = (decision: "verified" | "rejected") => {
    if (!selectedEvidenceId || !reviewRationale.trim()) return;
    reviewEvidence.mutate({
      evidence_link_id: selectedEvidenceId,
      decision,
      delivery_status: deliveryStatus,
      rationale: reviewRationale.trim(),
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        pushToast({ title: decision === "verified" ? "Evidence verified" : "Evidence rejected", message: selectedRequirement ? text(selectedRequirement, "requirement_name") : "Blueprint requirement", tone: decision === "verified" ? "ok" : "warn", duration: 3500 });
        setSelectedRequirement(null);
        setReviewRationale("");
      },
      onError: (error) => pushToast({ title: "Evidence review failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  };

  const assignRequirement = (row: LiveRow) => {
    const owner = text(row, "owner_agent", "Jarvis");
    const requirement = text(row, "requirement_name", "Blueprint requirement");
    const acceptance = text(row, "acceptance_criteria", "Complete with production evidence.");
    const nextAction = text(row, "next_action", "Implement and attach live evidence.");
    delegate.mutate({
      to_agent: owner,
      subject: `Blueprint: ${requirement}`.slice(0, 120),
      objective: [
        `Complete canonical blueprint requirement: ${requirement}.`,
        `Acceptance: ${acceptance}`,
        `Next action: ${nextAction}`,
        `Requirement key: ${text(row, "requirement_key")}.`,
        "Use production data only, cite durable evidence, and keep any capital or broker action human-gated.",
      ].join("\n"),
      priority: ["critical", "high", "medium", "low"].includes(text(row, "priority"))
        ? text(row, "priority") as "critical" | "high" | "medium" | "low"
        : "high",
      workspace: text(row, "primary_workspace", "system"),
      actor: "Devarsh",
    }, {
      onSuccess: (result) => pushToast({ title: "Requirement assigned", message: `${owner} · task ${text(result, "task_id", "queued")}`, tone: "ok", duration: 3500 }),
      onError: (error) => pushToast({ title: "Assignment failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  };

  return (
    <div className="aios-destination">
      <Header icon={ShieldCheck} code="GOV" title="Governance & Delivery" subtitle="Canonical blueprint progress, requirement ownership, architecture controls, and production evidence." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Requirements" value={summary.get("requirements") ?? 0} /></MetricTile>
        <MetricTile tone="ok"><Metric label="Verified" value={summary.get("done_requirements") ?? 0} /></MetricTile>
        <MetricTile tone="warn"><Metric label="Partial" value={summary.get("partial_requirements") ?? 0} /></MetricTile>
        <MetricTile tone="risk"><Metric label="Planned" value={summary.get("planned_requirements") ?? 0} /></MetricTile>
        <MetricTile><Metric label="Progress" value={`${summary.get("progress_score") ?? 0}%`} /></MetricTile>
      </div>
      <Panel icon={ShieldCheck} title="Blueprint Domains" actions={<Badge tone={domains.length ? "ok" : "risk"}>{domains.length} domains</Badge>}>
        {registry.isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading blueprint registry…</div> : (
          <DataTable
            columns={[
              { key: "domain", header: "Domain", render: (r) => <strong>{text(r, "domain_name", text(r, "domain_key"))}</strong> },
              { key: "owner", header: "Owner", render: (r) => text(r, "owner_agent", "—") },
              { key: "coverage", header: "Verified", align: "right", render: (r) => `${num(r, "done_count", 0)}/${num(r, "requirement_count", 0)}` },
              { key: "progress", header: "Progress", align: "right", render: (r) => `${num(r, "progress_score", 0)}%` },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "info")} /> },
            ]}
            rows={domains}
            rowKey={(r, i) => text(r, "domain_key", `b-${i}`)}
            onRowClick={(row) => setDomainKey(text(row, "domain_key"))}
            dense
          />
        )}
      </Panel>
      <Panel icon={ClipboardList} title="Requirement Delivery Board" actions={<div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}><Badge tone={requirements.length ? "warn" : "ok"}>{requirements.length} shown</Badge><Button size="sm" icon={RefreshCw} onClick={scanEvidence} disabled={reconcile.isPending}>{reconcile.isPending ? "Scanning" : "Scan evidence"}</Button></div>}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(160px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
          <Field label="Status"><Select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="planned">Planned</option><option value="partial">Partial</option><option value="blocked">Blocked</option><option value="done">Verified</option></Select></Field>
          <Field label="Domain"><Select value={domainKey} onChange={(event) => setDomainKey(event.target.value)}><option value="">All domains</option>{domains.map((row) => <option key={text(row, "domain_key")} value={text(row, "domain_key")}>{text(row, "domain_name")}</option>)}</Select></Field>
          <Field label="Priority"><Select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="">All priorities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></Select></Field>
        </div>
        {registry.isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading requirements…</div> : (
          <DataTable
            columns={[
              { key: "requirement", header: "Requirement", render: (row) => <div><strong>{text(row, "requirement_name")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 3 }}>{text(row, "next_action", text(row, "acceptance_criteria")).slice(0, 170)}</div></div> },
              { key: "domain", header: "Domain", render: (row) => text(row, "domain_name", text(row, "domain_key")) },
              { key: "owner", header: "Owner", render: (row) => text(row, "owner_agent", "Jarvis") },
              { key: "priority", header: "Priority", render: (row) => <StatusPill status={text(row, "priority", "high")} /> },
              { key: "status", header: "State", render: (row) => <StatusPill status={text(row, "current_status", "planned")} /> },
              { key: "evidence", header: "Evidence", render: (row) => num(row, "verified_evidence_count") > 0 ? <Badge tone="ok">{num(row, "verified_evidence_count")} verified</Badge> : num(row, "candidate_evidence_count") > 0 ? <Badge tone="warn">{num(row, "candidate_evidence_count")} review</Badge> : <Badge>None</Badge> },
              { key: "action", header: "Action", render: (row) => num(row, "candidate_evidence_count") > 0 ? <Button size="sm" icon={ShieldCheck} onClick={() => openEvidenceReview(row)}>Review</Button> : text(row, "current_status") === "done" && num(row, "verified_evidence_count") > 0 ? <Badge tone="ok">Verified</Badge> : <Button size="sm" icon={Send} onClick={() => assignRequirement(row)} disabled={delegate.isPending}>Assign</Button> },
            ]}
            rows={requirements}
            rowKey={(row, index) => text(row, "requirement_key", `req-${index}`)}
            empty={<Empty icon={ClipboardList} title="No requirements match these filters" />}
          />
        )}
      </Panel>
      <Drawer
        open={selectedRequirement !== null}
        onClose={() => setSelectedRequirement(null)}
        title={selectedRequirement ? text(selectedRequirement, "requirement_name", "Evidence review") : "Evidence review"}
        icon={ShieldCheck}
        width={620}
        footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={() => setSelectedRequirement(null)}>Cancel</Button><Button variant="ghost" onClick={() => submitEvidenceReview("rejected")} disabled={!reviewRationale.trim() || reviewEvidence.isPending}>Reject</Button><Button variant="primary" icon={ShieldCheck} onClick={() => submitEvidenceReview("verified")} disabled={!selectedEvidenceId || !reviewRationale.trim() || reviewEvidence.isPending}>Verify evidence</Button></div>}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <div style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>{selectedRequirement ? text(selectedRequirement, "acceptance_criteria") : ""}</div>
          <Field label="Candidate evidence">
            <Select value={String(selectedEvidenceId || "")} onChange={(event) => setSelectedEvidenceId(Number(event.target.value))}>
              {selectedEvidence.map((item) => <option key={num(item, "id")} value={num(item, "id")}>{text(item, "evidence_status")} · {text(item, "evidence_type")} #{text(item, "evidence_key")}</option>)}
            </Select>
          </Field>
          {selectedEvidence.filter((item) => num(item, "id") === selectedEvidenceId).map((item) => <Panel key={num(item, "id")} icon={ClipboardList} title="Evidence detail" actions={<StatusPill status={text(item, "evidence_status", "candidate")} />}><div style={{ padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}><div>{text(item, "evidence_summary")}</div><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(item, "evidence_note_path", "No note path recorded")}</div>{text(item, "evidence_type") === "agent_task" && <Button size="sm" variant="ghost" onClick={() => openEvidence({ kind: "task", key: text(item, "evidence_key"), title: "Blueprint task evidence" })}>Open task evidence</Button>}</div></Panel>)}
          <Field label="Delivery state after verification"><Select value={deliveryStatus} onChange={(event) => setDeliveryStatus(event.target.value as "partial" | "done")}><option value="partial">Partial - more work remains</option><option value="done">Verified complete</option></Select></Field>
          <Field label="Review rationale" required><TextArea rows={5} value={reviewRationale} onChange={(event) => setReviewRationale(event.target.value)} placeholder="State what the evidence proves, what was checked, and why the selected delivery state is justified." /></Field>
          <div style={{ color: "var(--status-warn)", fontSize: "var(--text-xs)" }}>Agent output is candidate evidence only. Verification is a named human decision and never enables broker execution.</div>
        </div>
      </Drawer>
    </div>
  );
}

/* ============================================================
 * MODELS VIEW
 * ============================================================ */
export function ModelsView() {
  const health = useSystemHealth();
  const terminal = useDepartmentTerminal("models");
  const data = health.data;
  const routes = terminal.data?.primary?.length ? terminal.data.primary : data?.model_routes ?? [];
  const policies = terminal.data?.secondary ?? [];
  const calls = terminal.data?.tertiary ?? [];
  const canaries = terminal.data?.canaries ?? [];
  const isLoading = health.isLoading || terminal.isLoading;
  const readyRoutes = routes.filter((row) => ["ready", "available", "healthy", "active"].some((status) => text(row, "runtime_status", text(row, "status")).toLowerCase().includes(status))).length;
  const blockedCalls = calls.filter((row) => text(row, "decision_status", text(row, "status")).toLowerCase().includes("block")).length;
  const dailyDriver = routes.find((row) => text(row, "route_name") === "openrouter_research_fast");

  const prepareCanaryMutation = usePreparePublicResearchCanary();
  const approvePreflightMutation = useApproveResearchModelPreflight();
  const configureCanaryMutation = useConfigurePublicResearchCanary();
  const runCanaryMutation = useRunPublicResearchCanary();
  const promoteCanaryMutation = useReviewPromotePublicResearchCanary();
  const pushToast = useUIStore((state) => state.pushToast);

  const [preflight, setPreflight] = React.useState<LiveRow | null>(null);
  const [configuredCanary, setConfiguredCanary] = React.useState<LiveRow | null>(null);
  const [runResult, setRunResult] = React.useState<LiveRow | null>(null);
  const [runConfirmed, setRunConfirmed] = React.useState(false);
  const [reviewOpen, setReviewOpen] = React.useState(false);
  const [reviewer, setReviewer] = React.useState("Devarsh");
  const [citationScore, setCitationScore] = React.useState(100);
  const [numericScore, setNumericScore] = React.useState(100);
  const [unsupportedClaims, setUnsupportedClaims] = React.useState(0);
  const [citationsChecked, setCitationsChecked] = React.useState(false);
  const [reviewRationale, setReviewRationale] = React.useState("");

  const receipt = value<LiveRow>(runResult, "receipt", {});
  const reviewedResponseHash = text(receipt, "response_hash");
  const responseOutput = text(runResult, "response_output", text(runResult, "response_preview"));
  const canaryBusy = prepareCanaryMutation.isPending || approvePreflightMutation.isPending
    || configureCanaryMutation.isPending || runCanaryMutation.isPending || promoteCanaryMutation.isPending;

  const prepareGlm53Canary = async () => {
    try {
      const result = await prepareCanaryMutation.mutateAsync({
        request_kind: "canary",
        public_only: true,
        contains_private_data: false,
        actor: "Devarsh",
        estimated_duration_seconds: 120,
        runs: [{
          agent_name: "Company Analyst",
          route_name: "openrouter_public_lead_glm53_flash_canary",
          prompt_tokens_est: 1800,
          completion_tokens_max: 1400,
          max_calls: 1,
        }],
      });
      setPreflight(result);
      setConfiguredCanary(null);
      setRunResult(null);
      setRunConfirmed(false);
      pushToast({ title: "GLM 5.3 canary cost plan ready", message: "No model was called. Review the exact ceiling before approval.", tone: "ok", duration: 4000 });
    } catch (error) {
      pushToast({ title: "Canary cost plan failed", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 5000 });
    }
  };

  const approveAndConfigureCanary = async () => {
    const preflightId = num(preflight, "id");
    if (!preflightId) return;
    try {
      await approvePreflightMutation.mutateAsync({ preflight_id: preflightId, operator_confirmed: true, actor: "Devarsh" });
      const configured = await configureCanaryMutation.mutateAsync({
        preflight_id: preflightId,
        candidate_route: "openrouter_public_lead_glm53_flash_canary",
        actor: "Devarsh",
      });
      setConfiguredCanary(configured);
      pushToast({ title: "Bounded public canary configured", message: "Still no model call. Running it requires the separate confirmation below.", tone: "ok", duration: 4000 });
    } catch (error) {
      pushToast({ title: "Canary setup failed", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 5000 });
    }
  };

  const runGlm53Canary = async () => {
    const canaryId = num(configuredCanary, "id");
    if (!canaryId || !runConfirmed) return;
    try {
      const result = await runCanaryMutation.mutateAsync({ canary_id: canaryId, operator_confirmed: true, actor: "Devarsh" });
      setRunResult(result);
      setCitationsChecked(false);
      setReviewRationale("");
      setReviewOpen(true);
      pushToast({ title: "Canary completed", message: "Review the returned output before any daily-driver change.", tone: text(result, "status") === "completed" ? "ok" : "warn", duration: 4500 });
    } catch (error) {
      pushToast({ title: "Canary run failed", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 5000 });
    }
  };

  const promoteReviewedCanary = async () => {
    const canaryId = num(runResult, "id");
    if (!canaryId || !reviewedResponseHash) return;
    try {
      const result = await promoteCanaryMutation.mutateAsync({
        canary_id: canaryId,
        operator_confirmed: true,
        approve_for_daily_driver: true,
        reviewer,
        rationale: reviewRationale,
        reviewed_response_hash: reviewedResponseHash,
        source_citations_checked: true,
        citation_accuracy_score: citationScore,
        numeric_accuracy_score: numericScore,
        unsupported_claim_count: unsupportedClaims,
      });
      setReviewOpen(false);
      pushToast({ title: "Public research daily driver updated", message: text(result, "detail"), tone: "ok", duration: 6000 });
    } catch (error) {
      pushToast({ title: "Daily-driver promotion blocked", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 6000 });
    }
  };

  return (
    <div className="aios-destination">
      <Header icon={Cpu} code="MODELS" title="Model Router & Cost Control" subtitle="Private local default, explicit cloud escalation, privacy gates, runtime readiness, and audited calls." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Governed Routes" value={routes.length} /></MetricTile>
        <MetricTile tone={readyRoutes ? "ok" : "warn"}><Metric label="Runtime Ready" value={readyRoutes} /></MetricTile>
        <MetricTile><Metric label="Privacy Policies" value={policies.length} /></MetricTile>
        <MetricTile tone={blockedCalls ? "warn" : "ok"}><Metric label="Blocked Calls" value={blockedCalls} /></MetricTile>
        <MetricTile><Metric label="Canary Receipts" value={canaries.length} /></MetricTile>
        <MetricTile tone={dailyDriver ? "ok" : "warn"}><Metric label="Research Daily Driver" value={dailyDriver ? text(dailyDriver, "default_model") : "Not selected"} /></MetricTile>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Cpu} title="Model Routes">
          {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading...</div> : (
            <DataTable
              columns={[
                { key: "route", header: "Route", render: (row) => <strong>{text(row, "route_name", text(row, "name"))}</strong> },
                { key: "model", header: "Model", render: (row) => text(row, "default_model", text(row, "model_name", text(row, "preferred_model", "-"))) },
                { key: "provider", header: "Provider", render: (row) => text(row, "default_provider", text(row, "provider", "-")) },
                { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "runtime_status", text(row, "status", "info"))} /> },
              ]}
              rows={routes}
              rowKey={(row, index) => text(row, "route_name", `r-${index}`)}
            />
          )}
        </Panel>
        <Panel icon={Cpu} title="Model Endpoints">
          {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading...</div> : (
            <DataTable
              columns={[
                { key: "name", header: "Endpoint", render: (row) => <strong>{text(row, "endpoint_name", text(row, "name"))}</strong> },
                { key: "provider", header: "Provider", render: (row) => text(row, "provider", "-") },
                { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", text(row, "health", "info"))} /> },
              ]}
              rows={data?.model_endpoints ?? []}
              rowKey={(row, index) => text(row, "endpoint_name", `e-${index}`)}
            />
          )}
        </Panel>
      </div>

      <Panel icon={ShieldCheck} title="GLM 5.3 Flash public-research daily-driver gate" actions={<Badge>{canaries.length} receipts</Badge>}>
        <div style={{ padding: "var(--space-4)", display: "grid", gap: "var(--space-4)" }}>
          <div style={{ maxWidth: 900, color: "var(--text-muted)", fontSize: "var(--text-sm)", lineHeight: 1.6 }}>
            GLM 5.3 Flash may handle high-volume public Research Case specialist work only after a fixed public-packet canary and named citation/numeric review. DeepSeek V4 Pro remains lead and independent-review escalation. No step grants private-data access, broker writes, or automatic capital authority.
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
            <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-3)" }}>
              <strong>1 - Cost plan</strong>
              <p className="micro">Preparing a plan calls no model.</p>
              <Button size="sm" variant="ghost" onClick={prepareGlm53Canary} disabled={canaryBusy}>Prepare GLM 5.3 canary</Button>
            </div>
            <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-3)" }}>
              <strong>2 - Approve bounded setup</strong>
              {preflight ? (
                <>
                  <p className="micro">{`Estimate $${num(preflight, "estimated_cost_usd").toFixed(4)} | hard max $${num(preflight, "hard_max_cost_usd").toFixed(4)} | INR ${num(preflight, "hard_max_cost_inr").toFixed(2)}`}</p>
                  <Button size="sm" variant="ghost" onClick={approveAndConfigureCanary} disabled={canaryBusy || Boolean(configuredCanary)}>Approve and configure</Button>
                </>
              ) : <p className="micro">Waiting for a costed preflight.</p>}
            </div>
            <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-3)" }}>
              <strong>3 - Run once</strong>
              <p className="micro">This is the only paid step. It uses the fixed USHAMART public packet.</p>
              <Checkbox checked={runConfirmed} onChange={setRunConfirmed} disabled={!configuredCanary} label="I confirm this bounded paid canary" />
              <Button size="sm" variant="primary" onClick={runGlm53Canary} disabled={canaryBusy || !configuredCanary || !runConfirmed}>Run paid canary</Button>
            </div>
            <div style={{ border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "var(--space-3)" }}>
              <strong>4 - Human review</strong>
              <p className="micro">Promotion is bound to the exact response hash and cannot happen from an old or hidden response.</p>
              <Button size="sm" variant="ghost" onClick={() => setReviewOpen(true)} disabled={!runResult || !reviewedResponseHash}>Review current output</Button>
            </div>
          </div>
          {canaries.length === 0 ? <Empty icon={ShieldCheck} title="No public model canary receipts yet" /> : (
            <DataTable
              columns={[
                { key: "candidate", header: "Candidate", render: (row) => <><strong>{text(row, "candidate_model")}</strong><div className="micro">{text(row, "candidate_route")}</div></> },
                { key: "status", header: "Run", render: (row) => <StatusPill status={text(row, "status", "unknown")} /> },
                { key: "structured", header: "Structured", render: (row) => <StatusPill status={value<boolean>(row, "structured_output_valid", false) ? "passed" : "not_passed"} /> },
                { key: "review", header: "Selected", render: (row) => <StatusPill status={value<boolean>(row, "selected_for_role", false) ? "daily_driver" : "not_selected"} /> },
                { key: "cost", header: "Ceiling", align: "right", render: (row) => `$${num(row, "hard_max_cost_usd").toFixed(4)}` },
                { key: "updated", header: "Updated", render: (row) => formatRelative(text(row, "updated_at")) },
              ]}
              rows={canaries}
              rowKey={(row, index) => text(row, "canary_key", `canary-${index}`)}
            />
          )}
        </div>
      </Panel>

      <Panel icon={ShieldCheck} title="Privacy & Cloud Gates">
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading...</div> : policies.length === 0 ? <Empty icon={ShieldCheck} title="No model privacy policies returned" /> : (
          <DataTable
            columns={[
              { key: "class", header: "Data Class", render: (row) => <strong>{text(row, "privacy_class")}</strong> },
              { key: "cloud", header: "Cloud", render: (row) => <StatusPill status={String(row.cloud_model_allowed) === "true" ? "allowed" : "blocked"} /> },
              { key: "cache", header: "Cache", render: (row) => <StatusPill status={String(row.cache_allowed) === "true" ? "allowed" : "blocked"} /> },
              { key: "context", header: "Max Context", align: "right", render: (row) => num(row, "max_context_chars", 0).toLocaleString() },
              { key: "notes", header: "Control", render: (row) => text(row, "notes", text(row, "policy_statement", "-")) },
            ]}
            rows={policies}
            rowKey={(row, index) => text(row, "privacy_class", `policy-${index}`)}
          />
        )}
      </Panel>
      <Panel icon={Activity} title="Recent Routing Decisions" actions={<Badge>{calls.length}</Badge>}>
        {calls.length === 0 ? <Empty icon={Activity} title="No recent model calls" /> : (
          <DataTable
            columns={[
              { key: "route", header: "Route", render: (row) => <strong>{text(row, "selected_route", text(row, "requested_route", "-"))}</strong> },
              { key: "model", header: "Model", render: (row) => text(row, "selected_model", "-") },
              { key: "privacy", header: "Privacy", render: (row) => <StatusPill status={text(row, "privacy_class", "unknown")} /> },
              { key: "cache", header: "Cache", render: (row) => text(row, "cache_status", "-") },
              { key: "status", header: "Decision", render: (row) => <StatusPill status={text(row, "decision_status", "unknown")} /> },
              { key: "time", header: "Time", render: (row) => formatRelative(text(row, "created_at")) },
            ]}
            rows={calls.slice(0, 40)}
            rowKey={(row, index) => String(text(row, "decision_key", text(row, "id", index)))}
          />
        )}
      </Panel>

      <Drawer
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        title="Review GLM 5.3 Flash canary"
        subtitle={reviewedResponseHash ? `Response ${reviewedResponseHash.slice(0, 12)}...` : "No current response"}
        icon={ShieldCheck}
        width={640}
        footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={() => setReviewOpen(false)}>Cancel</Button><Button variant="primary" onClick={promoteReviewedCanary} disabled={canaryBusy || !citationsChecked || citationScore < 90 || numericScore < 95 || unsupportedClaims !== 0 || reviewRationale.trim().length < 20 || !reviewedResponseHash}>Select public daily driver</Button></div>}
      >
        <div style={{ display: "grid", gap: "var(--space-4)" }}>
          <div>
            <strong>Exact canary output</strong>
            <pre style={{ marginTop: "var(--space-2)", padding: "var(--space-3)", whiteSpace: "pre-wrap", overflowWrap: "anywhere", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", background: "var(--surface-soft)", fontSize: "var(--text-xs)" }}>{responseOutput || "The response is not present in this browser session. Run a fresh canary; promotion from an unseen stored hash is intentionally blocked."}</pre>
          </div>
          <Field label="Named reviewer" required><TextInput value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></Field>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "var(--space-3)" }}>
            <Field label="Citation accuracy" hint="Minimum 90"><TextInput type="number" min={0} max={100} value={citationScore} onChange={(event) => setCitationScore(Number(event.target.value))} /></Field>
            <Field label="Numeric accuracy" hint="Minimum 95"><TextInput type="number" min={0} max={100} value={numericScore} onChange={(event) => setNumericScore(Number(event.target.value))} /></Field>
            <Field label="Unsupported claims" hint="Must be zero"><TextInput type="number" min={0} value={unsupportedClaims} onChange={(event) => setUnsupportedClaims(Number(event.target.value))} /></Field>
          </div>
          <Checkbox checked={citationsChecked} onChange={setCitationsChecked} label="I checked every cited fact and numerical value against the fixed public packet." />
          <Field label="Review rationale" required hint="Explain what was checked and why the result is safe for bounded public specialist work."><TextArea rows={5} value={reviewRationale} onChange={(event) => setReviewRationale(event.target.value)} /></Field>
          <div style={{ color: "var(--status-warn)", fontSize: "var(--text-xs)", lineHeight: 1.5 }}>This selects only the public Research Case specialist route. Private context stays local; every paid run still needs a cost preflight; DeepSeek V4 Pro remains lead/review escalation; no broker or capital action is enabled.</div>
        </div>
      </Drawer>
    </div>
  );
}

/* ============================================================
 * SYSTEM VIEW
 * ============================================================ */
export function SystemView() {
  const { data, isLoading } = useSystemHealth();
  return (
    <div className="aios-destination">
      <Header icon={Activity} code="SYSTEM" title="System Health" subtitle="Daemons, data sources, freshness, connector health." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Runtime Daemons" value={data?.runtime_daemons?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Data Sources" value={data?.data_sources?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Source Checks" value={data?.data_source_checks?.length ?? 0} /></MetricTile>
        <MetricTile tone={(data?.source_freshness?.filter((r) => text(r, "status").includes("stale")).length ?? 0) > 0 ? "warn" : "ok"}>
          <Metric label="Stale Sources" value={data?.source_freshness?.filter((r) => text(r, "status").includes("stale")).length ?? 0} />
        </MetricTile>
      </div>
      <Panel icon={Activity} title="Runtime Daemons">
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
          <DataTable
            columns={[
              { key: "name", header: "Daemon", render: (r) => <strong>{text(r, "daemon_name", text(r, "name"))}</strong> },
              { key: "pid", header: "PID", align: "right", render: (r) => num(r, "pid", 0) || "—" },
              { key: "last", header: "Last Heartbeat", render: (r) => formatRelative(text(r, "last_heartbeat_at", text(r, "checked_at"))) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", text(r, "health", "info"))} /> },
            ]}
            rows={data?.runtime_daemons ?? []}
            rowKey={(r, i) => text(r, "daemon_name", `d-${i}`)}
          />
        )}
      </Panel>
    </div>
  );
}

/* ============================================================
 * LIBRARY VIEW (Obsidian vault)
 * ============================================================ */
export function LibraryView() {
  const reports = useReports();
  const refreshHub = useAction<{ actor: string }>("/api/research/hub/refresh", {
    invalidate: [["reports"], ["mission-control"]],
  });
  const openEvidence = useUIStore((s) => s.openEvidence);
  const pushToast = useUIStore((s) => s.pushToast);
  const [query, setQuery] = React.useState("");
  const [family, setFamily] = React.useState("all");

  const data = reports.data;
  const artifacts = data?.artifacts ?? [];
  const rawArtifacts = data?.raw_artifacts ?? [];
  const lineage = data?.artifact_lineage ?? [];
  const sourceCoverage = data?.research_hub ?? [];
  const gaps = data?.artifact_gaps ?? [];

  const families = React.useMemo(() => Array.from(new Set([
    ...artifacts.map((row) => text(row, "artifact_family", text(row, "artifact_type"))),
    ...rawArtifacts.map((row) => text(row, "artifact_type")),
  ].filter(Boolean))).sort(), [artifacts, rawArtifacts]);

  const searchable = React.useMemo(() => {
    const registryRows = artifacts.map((row) => ({ ...row, library_source: "Output registry" }));
    const rawRows = rawArtifacts.map((row) => ({ ...row, library_source: "Raw artifact" }));
    const needle = query.trim().toLowerCase();
    return [...registryRows, ...rawRows].filter((row) => {
      const rowFamily = text(row, "artifact_family", text(row, "artifact_type"));
      if (family !== "all" && rowFamily !== family) return false;
      if (!needle) return true;
      return [
        text(row, "title"), text(row, "summary"), rowFamily,
        text(row, "source_system"), text(row, "owner_agent"),
        text(row, "department"), text(row, "symbol"), text(row, "company_name"),
      ].some((value) => value.toLowerCase().includes(needle));
    }).slice(0, 200);
  }, [artifacts, rawArtifacts, family, query]);

  const refresh = async () => {
    try {
      const result = await refreshHub.mutateAsync({ actor: "Knowledge Librarian" });
      await reports.refetch();
      pushToast({ title: "Knowledge library refreshed", message: `${num(result, "records_upserted")} artifacts indexed.`, tone: "ok", duration: 2500 });
    } catch (error) {
      pushToast({ title: "Library refresh failed", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 5000 });
    }
  };

  const openArtifact = (row: LiveRow) => {
    const key = text(row, "artifact_key", text(row, "id", text(row, "content_hash", text(row, "row_ref"))));
    openEvidence({ kind: "artifact", key, title: text(row, "title", "Knowledge artifact") });
  };

  return (
    <div className="aios-destination">
      <Header icon={Library} code="LIBRARY" title="Knowledge Library" subtitle="Searchable research, decisions, reports, source lineage, and durable AI output inventory." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Registered Outputs" value={artifacts.length} /></MetricTile>
        <MetricTile><Metric label="Raw Artifacts" value={rawArtifacts.length} /></MetricTile>
        <MetricTile><Metric label="Lineage Records" value={lineage.length} /></MetricTile>
        <MetricTile><Metric label="Source Families" value={sourceCoverage.length} /></MetricTile>
        <MetricTile tone={gaps.length ? "warn" : "ok"}><Metric label="Artifact Gaps" value={gaps.length} /></MetricTile>
      </div>
      <Panel
        icon={Search}
        title="Search Knowledge"
        actions={<Button size="sm" icon={RefreshCw} onClick={refresh} disabled={refreshHub.isPending || reports.isFetching}>{refreshHub.isPending ? "Indexing" : reports.isFetching ? "Refreshing" : "Refresh"}</Button>}
      >
        <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 1fr) minmax(180px, 280px)", gap: "var(--space-3)", padding: "var(--space-3)" }}>
          <Field label="Title, company, symbol, owner, or topic">
            <TextInput value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the live artifact registry..." />
          </Field>
          <Field label="Artifact family">
            <Select value={family} onChange={(event) => setFamily(event.target.value)}>
              <option value="all">All families</option>
              {families.map((value) => <option key={value} value={value}>{value}</option>)}
            </Select>
          </Field>
        </div>
        {reports.isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading knowledge inventory...</div> : (
          <DataTable
            columns={[
              { key: "title", header: "Artifact", render: (row) => <div><strong>{text(row, "title", "Untitled artifact")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 2 }}>{text(row, "summary", text(row, "local_path", text(row, "source_url"))).slice(0, 150)}</div></div> },
              { key: "family", header: "Family", render: (row) => <Badge>{text(row, "artifact_family", text(row, "artifact_type", "artifact"))}</Badge> },
              { key: "source", header: "Source / owner", render: (row) => <div>{text(row, "source_system", text(row, "owner_agent", "Unassigned"))}<div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "library_source")}</div></div> },
              { key: "updated", header: "Updated", render: (row) => formatRelative(text(row, "latest_activity_at", text(row, "captured_at", text(row, "updated_at", text(row, "created_at"))))) },
              { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", text(row, "sensitivity", "indexed"))} /> },
            ]}
            rows={searchable}
            rowKey={(row, index) => `${text(row, "library_source")}-${text(row, "artifact_key", text(row, "id", text(row, "content_hash", index)))}`}
            onRowClick={openArtifact}
            empty={<Empty icon={Library} title={query || family !== "all" ? "No matching artifacts" : "No artifacts ingested"} description={query || family !== "all" ? "Change the search or artifact family filter." : "The live artifact registry returned no rows."} />}
          />
        )}
      </Panel>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(420px, 1.2fr) minmax(340px, 0.8fr)", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Library} title="Research Source Coverage">
          <DataTable
            columns={[
              { key: "root", header: "Source root", render: (row) => <strong>{text(row, "root_label", "Unknown source")}</strong> },
              { key: "family", header: "Family", render: (row) => text(row, "artifact_family", "-") },
              { key: "count", header: "Artifacts", align: "right", render: (row) => num(row, "artifact_count", 0) },
              { key: "latest", header: "Latest capture", render: (row) => formatRelative(text(row, "latest_captured_at", text(row, "latest_source_modified_at"))) },
            ]}
            rows={sourceCoverage}
            rowKey={(row, index) => `${text(row, "root_label", index)}-${text(row, "artifact_family")}`}
            empty={<Empty icon={Library} title="No research source coverage" description="The reports API returned no indexed research roots." />}
            dense
          />
        </Panel>
        <Panel icon={ShieldCheck} title="Lineage & Coverage Gaps" actions={<Badge tone={gaps.length ? "warn" : "ok"}>{gaps.length ? `${gaps.length} open` : "Complete"}</Badge>}>
          {gaps.length === 0 ? (
            <Empty icon={ShieldCheck} title="No artifact gaps reported" description={`${lineage.length} lineage records are visible in the current snapshot.`} />
          ) : (
            <div style={{ maxHeight: 360, overflow: "auto" }}><ScrollList>
              {gaps.slice(0, 30).map((row, index) => (
                <div key={`${text(row, "gap_type", index)}-${text(row, "source_id", index)}`} style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--border-subtle)", cursor: "pointer" }} onClick={() => openEvidence({ kind: "artifact", key: text(row, "source_id", String(index)), title: text(row, "title", text(row, "gap_type", "Artifact gap")) })}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--space-2)" }}><strong>{text(row, "title", text(row, "gap_type", "Artifact gap"))}</strong><StatusPill status={text(row, "status", "review")} /></div>
                  <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 4 }}>{text(row, "gap_reason", text(row, "source_view"))}</div>
                </div>
              ))}
            </ScrollList></div>
          )}
        </Panel>
      </div>
    </div>
  );
}
/* ============================================================
 * Shared header
 * ============================================================ */
function Header({ icon: Icon, code, title, subtitle }: { icon: typeof Users; code: string; title: string; subtitle: string }) {
  return (
    <div className="aios-destination__head">
      <div className="aios-destination__title-row">
        <div className="aios-destination__title">
          <Icon size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
          {title}
        </div>
        <Badge tone="accent">{code}</Badge>
      </div>
      <div className="aios-destination__subtitle">{subtitle}</div>
    </div>
  );
}
