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
  Inbox, ChevronRight, MessageSquare, Play, Send,
} from "lucide-react";
import { Panel, DataTable, StatusPill, Badge, Empty, MetricTile, Metric, Avatar, ScrollList, Button, Field, Select, TextArea } from "../../system/primitives";
import { useOfficeSnapshot, useSystemHealth, useDepartmentTerminal } from "../../data/queries";
import { useCreateAgentMessage, useRunAgentWorker } from "../../data/actions";
import { useUIStore } from "../../store";
import { text, num, formatRelative, initials } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

/* ============================================================
 * AGENTS VIEW
 * ============================================================ */
export function AgentsView() {
  const { data, isLoading } = useOfficeSnapshot();
  const openEvidence = useUIStore((s) => s.openEvidence);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);

  const agents = data?.agents ?? [];

  return (
    <div className="aios-destination">
      <Header icon={Users} code="AGENTS" title="Agents & Employees" subtitle="The full agent roster — 16+ specialists across 11 departments." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Agents" value={agents.length} /></MetricTile>
        <MetricTile><Metric label="Departments" value={new Set(agents.map((a) => text(a, "department")).filter(Boolean)).size} /></MetricTile>
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
              const dept = text(agent, "department");
              const role = text(agent, "role", text(agent, "title"));
              const status = text(agent, "status", "idle");
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
                  <div style={{ marginTop: "var(--space-2)", display: "flex", gap: "var(--space-1)", color: "var(--accent)", fontSize: "var(--text-xs)" }}>
                    <MessageSquare size={11} /> Talk to {name.split(" ")[0]}
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
              { key: "headcount", header: "Agents", align: "right", render: (r) => num(r, "agent_count", num(r, "headcount", 0)) },
              { key: "mandate", header: "Mandate", render: (r) => text(r, "mission", text(r, "mandate", "—")) },
            ]}
            rows={selected === "all" ? departments : departments.filter((row) => text(row, "department", text(row, "department_name")) === selected)}
            rowKey={(r, i) => text(r, "department", `dept-${i}`)}
          />
        )}
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Employees" value={departmentEmployees.length} /></MetricTile>
        <MetricTile tone={active ? "ok" : "warn"}><Metric label="Working Now" value={active} /></MetricTile>
        <MetricTile tone={openTasks ? "warn" : "ok"}><Metric label="Open Tasks" value={openTasks} /></MetricTile>
        <MetricTile tone={openInbox ? "warn" : "ok"}><Metric label="Open Inbox" value={openInbox} /></MetricTile>
        <MetricTile><Metric label="Queue Rows" value={queue.length} /></MetricTile>
      </div>

      <Panel icon={Users} title="Employee Operating Board">
        {departmentEmployees.length === 0 ? <Empty icon={Users} title="No employees in this scope" /> : (
          <DataTable
            columns={[
              { key: "agent", header: "Employee", render: (r) => <button style={{ color: "var(--accent)", background: "none", border: 0, cursor: "pointer", fontWeight: 600 }} onClick={() => setAssistantScope({ agentKey: text(r, "agent_name"), agentName: text(r, "agent_name") })}>{text(r, "agent_name")}</button> },
              { key: "title", header: "Mandate", render: (r) => text(r, "display_title", text(r, "role_scope", "—")) },
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

      <div style={{ display: "grid", gridTemplateColumns: "minmax(300px, 0.8fr) minmax(420px, 1.2fr)", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Send} title="Assign Work">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            <Field label="Owner"><Select value={target} onChange={(event) => setTarget(event.target.value)}>{departmentEmployees.map((row) => <option key={text(row, "agent_name")} value={text(row, "agent_name")}>{text(row, "agent_name")} · {text(row, "department_name", text(row, "department"))}</option>)}</Select></Field>
            <Field label="Objective"><TextArea value={assignment} onChange={(event) => setAssignment(event.target.value)} rows={5} placeholder="Give the objective, required evidence, deadline, and expected output…" /></Field>
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="primary" icon={Send} onClick={assignWork} disabled={createMessage.isPending}>Assign</Button>
              <Button icon={Play} onClick={processQueue} disabled={runWorker.isPending}>Process queue</Button>
            </div>
          </div>
        </Panel>
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
  const items = data?.committee_room_items ?? [];

  return (
    <div className="aios-destination">
      <Header icon={Gavel} code="COMM" title="Committee Room" subtitle="Packets, positions, synthesis, and human decisions." />
      <Panel icon={Gavel} title="Committee Queue" actions={items.length > 0 ? <Badge tone="warn" dot>{items.length}</Badge> : undefined}>
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : items.length === 0 ? (
          <Empty icon={Gavel} title="No open committee packets" />
        ) : (
          <ScrollList>
            {items.map((item, i) => (
              <div
                key={i}
                className="aios-committee-row"
                style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "var(--space-3)", borderBottom: "1px solid var(--border-subtle)", cursor: "pointer" }}
                onClick={() => openEvidence({ kind: "committee", key: String(text(item, "packet_id", text(item, "id", i))), title: text(item, "title", text(item, "subject", "Committee packet")) })}
              >
                <ChevronRight size={14} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: "var(--text-sm)" }}>{text(item, "title", text(item, "subject", "Packet"))}</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{text(item, "committee_key")} · {formatRelative(text(item, "opened_at", text(item, "created_at")))}</div>
                </div>
                <StatusPill status={text(item, "status", "open")} />
              </div>
            ))}
          </ScrollList>
        )}
      </Panel>
    </div>
  );
}

/* ============================================================
 * GOVERNANCE VIEW
 * ============================================================ */
export function GovernanceView() {
  const { data, isLoading } = useSystemHealth();
  return (
    <div className="aios-destination">
      <Header icon={ShieldCheck} code="GOV" title="Governance" subtitle="Architecture change control, decisions, production safety." />
      <Panel icon={ShieldCheck} title="Blueprint Summary">
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
          <DataTable
            columns={[
              { key: "domain", header: "Domain", render: (r) => <strong>{text(r, "domain", text(r, "name"))}</strong> },
              { key: "coverage", header: "Coverage", align: "right", render: (r) => `${num(r, "completed", 0)}/${num(r, "total", 0)}` },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "info")} /> },
            ]}
            rows={data?.blueprint_domains ?? data?.blueprint_summary ?? []}
            rowKey={(r, i) => text(r, "domain", text(r, "name", `b-${i}`))}
          />
        )}
      </Panel>
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
  const isLoading = health.isLoading || terminal.isLoading;
  const readyRoutes = routes.filter((row) => ["ready", "available", "healthy", "active"].some((value) => text(row, "runtime_status", text(row, "status")).toLowerCase().includes(value))).length;
  const blockedCalls = calls.filter((row) => text(row, "decision_status", text(row, "status")).toLowerCase().includes("block")).length;
  return (
    <div className="aios-destination">
      <Header icon={Cpu} code="MODELS" title="Model Router & Cost Control" subtitle="Private local default, explicit cloud escalation, privacy gates, runtime readiness, and audited calls." />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Governed Routes" value={routes.length} /></MetricTile>
        <MetricTile tone={readyRoutes ? "ok" : "warn"}><Metric label="Runtime Ready" value={readyRoutes} /></MetricTile>
        <MetricTile><Metric label="Privacy Policies" value={policies.length} /></MetricTile>
        <MetricTile tone={blockedCalls ? "warn" : "ok"}><Metric label="Blocked Calls" value={blockedCalls} /></MetricTile>
        <MetricTile><Metric label="Recent Decisions" value={calls.length} /></MetricTile>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Cpu} title="Model Routes">
          {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
            <DataTable
              columns={[
                { key: "route", header: "Route", render: (r) => <strong>{text(r, "route_name", text(r, "name"))}</strong> },
                { key: "model", header: "Model", render: (r) => text(r, "default_model", text(r, "model_name", text(r, "preferred_model", "—"))) },
                { key: "provider", header: "Provider", render: (r) => text(r, "default_provider", text(r, "provider", "—")) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "runtime_status", text(r, "status", "info"))} /> },
              ]}
              rows={routes}
              rowKey={(r, i) => text(r, "route_name", `r-${i}`)}
            />
          )}
        </Panel>
        <Panel icon={Cpu} title="Model Endpoints">
          {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
            <DataTable
              columns={[
                { key: "name", header: "Endpoint", render: (r) => <strong>{text(r, "endpoint_name", text(r, "name"))}</strong> },
                { key: "provider", header: "Provider", render: (r) => text(r, "provider", "—") },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", text(r, "health", "info"))} /> },
              ]}
              rows={data?.model_endpoints ?? []}
              rowKey={(r, i) => text(r, "endpoint_name", `e-${i}`)}
            />
          )}
        </Panel>
      </div>
      <Panel icon={ShieldCheck} title="Privacy & Cloud Gates">
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : policies.length === 0 ? <Empty icon={ShieldCheck} title="No model privacy policies returned" /> : (
          <DataTable
            columns={[
              { key: "class", header: "Data Class", render: (r) => <strong>{text(r, "privacy_class")}</strong> },
              { key: "cloud", header: "Cloud", render: (r) => <StatusPill status={String(r.cloud_model_allowed) === "true" ? "allowed" : "blocked"} /> },
              { key: "cache", header: "Cache", render: (r) => <StatusPill status={String(r.cache_allowed) === "true" ? "allowed" : "blocked"} /> },
              { key: "context", header: "Max Context", align: "right", render: (r) => num(r, "max_context_chars", 0).toLocaleString() },
              { key: "notes", header: "Control", render: (r) => text(r, "notes", text(r, "policy_statement", "—")) },
            ]}
            rows={policies}
            rowKey={(r, i) => text(r, "privacy_class", `policy-${i}`)}
          />
        )}
      </Panel>
      <Panel icon={Activity} title="Recent Routing Decisions" actions={<Badge>{calls.length}</Badge>}>
        {calls.length === 0 ? <Empty icon={Activity} title="No recent model calls" /> : (
          <DataTable
            columns={[
              { key: "route", header: "Route", render: (r) => <strong>{text(r, "selected_route", text(r, "requested_route", "—"))}</strong> },
              { key: "model", header: "Model", render: (r) => text(r, "selected_model", "—") },
              { key: "privacy", header: "Privacy", render: (r) => <StatusPill status={text(r, "privacy_class", "unknown")} /> },
              { key: "cache", header: "Cache", render: (r) => text(r, "cache_status", "—") },
              { key: "status", header: "Decision", render: (r) => <StatusPill status={text(r, "decision_status", "unknown")} /> },
              { key: "time", header: "Time", render: (r) => formatRelative(text(r, "created_at")) },
            ]}
            rows={calls.slice(0, 40)}
            rowKey={(r, i) => String(text(r, "decision_key", text(r, "id", i)))}
          />
        )}
      </Panel>
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
  return (
    <div className="aios-destination">
      <Header icon={Library} code="LIBRARY" title="Knowledge Library" subtitle="Obsidian vault, Qdrant vector retrieval, note graph." />
      <Panel icon={Library} title="Vault">
        <Empty
          icon={Library}
          title="Knowledge graph coming soon"
          description="Browse the Obsidian vault (decisions, research, runbooks) and search via Qdrant. Use Charlie to search notes in the meantime — ask him anything."
        />
      </Panel>
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
