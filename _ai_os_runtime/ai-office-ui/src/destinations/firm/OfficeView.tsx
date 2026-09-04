import React from "react";
import {
  Activity,
  AlertTriangle,
  Boxes,
  GitBranch,
  Inbox,
  MessageSquare,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useOfficeSnapshot } from "../../data/queries";
import { useRunOfficeOperabilityAcceptance } from "../../data/actions";
import {
  Badge,
  Button,
  DataTable,
  Empty,
  Metric,
  MetricTile,
  Panel,
  Select,
  Skeleton,
  StatusPill,
  TextInput,
} from "../../system/primitives";
import { formatRelative, initials, num, text, value } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";
import { useUIStore } from "../../store";
import { hasLiveLease, runtimePresence, useLeaseClock } from "../../data/runtimePresence";
import { RuntimeControlPanel } from "./RuntimeControlPanel";

const LiveOffice = React.lazy(() => import("../../office3d/LiveOffice").then((module) => ({ default: module.LiveOffice })));

function mergedEmployees(data: ReturnType<typeof useOfficeSnapshot>["data"]): LiveRow[] {
  if (!data) return [];
  const profiles = new Map((data.agents ?? []).map((row) => [text(row, "agent_name"), row]));
  const activity = data.live_office_agent_activity ?? [];
  const rows = activity.map((row) => ({ ...(profiles.get(text(row, "agent_name")) ?? {}), ...row }));
  const seen = new Set(rows.map((row) => text(row, "agent_name")));
  for (const profile of data.agents ?? []) {
    if (!seen.has(text(profile, "agent_name"))) rows.push(profile);
  }
  return rows;
}

function employeeState(row: LiveRow): string {
  return runtimePresence(row);
}

function employeeDepartment(row: LiveRow): string {
  return text(row, "department_name", text(row, "department_key", text(row, "department", "Unassigned")));
}

export function OfficeView() {
  useLeaseClock();
  const { data, isLoading, error } = useOfficeSnapshot();
  const navigate = useNavigate();
  const setAssistantScope = useUIStore((state) => state.setAssistantScope);
  const focusRoom = useUIStore((state) => state.focusRoom);
  const openEvidence = useUIStore((state) => state.openEvidence);
  const pushToast = useUIStore((state) => state.pushToast);
  const operability = useRunOfficeOperabilityAcceptance();
  const [department, setDepartment] = React.useState("all");
  const [search, setSearch] = React.useState("");

  if (error) {
    return (
      <div className="aios-destination">
        <Panel variant="risk" icon={AlertTriangle} title="Cannot reach office snapshot">
          <div style={{ padding: "var(--space-4)", color: "var(--text-muted)" }}>{error.message}</div>
        </Panel>
      </div>
    );
  }

  const employees = mergedEmployees(data);
  const departments = [...new Set(employees.map(employeeDepartment).filter(Boolean))].sort();
  const filtered = employees.filter((employee) => {
    const matchesDepartment = department === "all" || employeeDepartment(employee) === department;
    const haystack = [
      text(employee, "agent_name"),
      employeeDepartment(employee),
      text(employee, "display_title"),
      text(employee, "current_work_title"),
    ].join(" ").toLowerCase();
    return matchesDepartment && haystack.includes(search.trim().toLowerCase());
  });
  const working = employees.filter((row) => hasLiveLease(row)).length;
  const blocked = employees.filter((row) => employeeState(row).toLowerCase().includes("block") || num(row, "blocked_task_count") > 0).length;
  const rooms = data?.live_office_rooms ?? [];
  const graphRuns = data?.graph_runs ?? [];
  const graphAttention = data?.graph_attention ?? [];
  const messages = data?.agent_messages ?? [];
  const latestAcceptance = data?.office_operability_acceptance?.[0];
  const acceptanceGates = value<LiveRow[]>(latestAcceptance, "gates", []);
  const projectionMeta = (data?.projection_meta ?? {}) as LiveRow;
  const sourceStatus = text(projectionMeta, "source_status", isLoading ? "loading" : "no_activity");
  const projectionIssues = data?.issues ?? [];

  function runOperabilityAcceptance() {
    operability.mutate({ actor: "Devarsh" }, {
      onSuccess: (result) => pushToast({
        title: text(result, "status") === "passed" ? "AI Office operability passed" : "AI Office operability blocked",
        message: `${num(result, "passed_count")} of ${num(result, "gate_count")} gates passed`,
        tone: text(result, "status") === "passed" ? "ok" : "warn",
        duration: 6500,
      }),
      onError: (failure) => pushToast({ title: "Operability check failed", message: failure.message, tone: "risk", duration: 6500 }),
    });
  }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Boxes size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Live AI Office
          </div>
          {data && <StatusPill status={sourceStatus} dot>{sourceStatus.replace(/_/g, " ")} · snapshot {formatRelative(data.generated_at)}</StatusPill>}
        </div>
        <div className="aios-destination__subtitle">
          Source-backed departments, accountable work, governed handoffs and decisions. Client details are redacted from this shared surface.
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Employees" value={employees.length} /></MetricTile>
        <MetricTile tone={working ? "ok" : "warn"}><Metric label="Working Now" value={working} /></MetricTile>
        <MetricTile tone={blocked ? "risk" : "ok"}><Metric label="Blocked" value={blocked} /></MetricTile>
        <MetricTile><Metric label="Departments" value={rooms.length || departments.length} /></MetricTile>
        <MetricTile tone={graphRuns.length ? "ok" : "default"}><Metric label="Graph Runs" value={graphRuns.length} /></MetricTile>
        <MetricTile tone={graphAttention.length ? "warn" : "ok"}><Metric label="Graph Attention" value={graphAttention.length} /></MetricTile>
      </div>

      <RuntimeControlPanel runtime={(data?.runtime ?? {}) as LiveRow} />

      <Panel icon={LockKeyhole} title="Shared Office Contract">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "var(--space-3)", padding: "var(--space-1) 0" }}>
          <div>
            <div style={{ color: "var(--text-faint)", fontSize: "var(--text-2xs)", textTransform: "uppercase" }}>Underlying records</div>
            <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 8 }}>
              <StatusPill status={sourceStatus} />
              <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{formatRelative(text(projectionMeta, "latest_record_at"))}</span>
            </div>
          </div>
          <div>
            <div style={{ color: "var(--text-faint)", fontSize: "var(--text-2xs)", textTransform: "uppercase" }}>Privacy projection</div>
            <strong style={{ display: "block", marginTop: 4 }}>Shared-safe · {num(projectionMeta, "redacted_record_count")} records hidden</strong>
            <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>Private client details require the authorized workspace.</span>
          </div>
          <div>
            <div style={{ color: "var(--text-faint)", fontSize: "var(--text-2xs)", textTransform: "uppercase" }}>Financial actions</div>
            <strong style={{ display: "block", marginTop: 4, color: "var(--status-warn)" }}>Broker, capital and live writes locked</strong>
            <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>The Office can observe, delegate and prepare evidence only.</span>
          </div>
          <div>
            <div style={{ color: "var(--text-faint)", fontSize: "var(--text-2xs)", textTransform: "uppercase" }}>Snapshot queries</div>
            <strong style={{ display: "block", marginTop: 4 }}>{projectionIssues.length === 0 ? "Complete" : projectionIssues.length + " source issue" + (projectionIssues.length === 1 ? "" : "s")}</strong>
            <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{projectionIssues.length === 0 ? "No Office query failures." : "Affected sections degrade to explicit empty states."}</span>
          </div>
        </div>
      </Panel>

      <Panel icon={ShieldCheck} title="AI Office Operability" actions={<Button icon={ShieldCheck} onClick={runOperabilityAcceptance} disabled={operability.isPending}>{operability.isPending ? "Checking…" : "Run acceptance"}</Button>}>
        {!latestAcceptance ? (
          <Empty icon={ShieldCheck} title="No operability acceptance run" description="Run the evidence gate to test every active employee, department, model route, tool, worker output, and handoff." />
        ) : (
          <div style={{ display: "grid", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
              <StatusPill status={text(latestAcceptance, "status")} />
              <strong>{num(latestAcceptance, "passed_count")} / {num(latestAcceptance, "gate_count")} gates</strong>
              <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{num(latestAcceptance, "active_agent_count")} employees · {num(latestAcceptance, "active_department_count")} departments · {formatRelative(text(latestAcceptance, "finished_at"))}</span>
            </div>
            <DataTable
              dense
              columns={[
                { key: "gate", header: "Gate", render: (row) => <strong>{text(row, "gate_name", text(row, "gate_key"))}</strong> },
                { key: "observed", header: "Observed / required", align: "right", render: (row) => `${num(row, "observed_value")} / ${num(row, "required_value")}` },
                { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status")} /> },
                { key: "gap", header: "Gap", render: (row) => text(row, "failure_reason", "—") },
              ]}
              rows={acceptanceGates}
              rowKey={(row, index) => text(row, "gate_key", `gate-${index}`)}
            />
          </div>
        )}
      </Panel>

      <Panel icon={Boxes} title="The Firm · Live Floor View" bodyFlush>
        <React.Suspense
          fallback={
            <div style={{ height: 680, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "var(--space-3)", background: "var(--bg-sunken)" }}>
              <Boxes size={48} style={{ color: "var(--accent)", opacity: 0.45 }} />
              <div style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>Loading live office state…</div>
            </div>
          }
        >
          <LiveOffice height={680} />
        </React.Suspense>
      </Panel>

      {isLoading && !data ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)" }}>
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} style={{ height: 180 }} />)}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 360px), 1fr))", gap: "var(--space-3)", alignItems: "start" }}>
          <Panel icon={Users} title="Department Occupancy" bodyTabIndex={0} actions={<Badge>{rooms.length}</Badge>}>
            {rooms.length === 0 ? (
              <Empty icon={Users} title="No room telemetry" description="The live-office room view returned no department rows." />
            ) : (
              <DataTable
                dense
                columns={[
                  { key: "room", header: "Department", render: (row) => <strong>{text(row, "room_name", text(row, "room_key"))}</strong> },
                  { key: "agents", header: "Employees", align: "right", render: (row) => num(row, "agent_count") },
                  { key: "working", header: "Working", align: "right", render: (row) => num(row, "executing_agent_count") },
                  { key: "queued", header: "Queued", align: "right", render: (row) => num(row, "queued_agent_count") },
                  { key: "tasks", header: "Open Tasks", align: "right", render: (row) => num(row, "open_task_count") },
                  { key: "inbox", header: "Inbox", align: "right", render: (row) => num(row, "open_inbox_count") },
                  { key: "state", header: "State", render: (row) => <StatusPill status={text(row, "room_state", "idle")} /> },
                ]}
                rows={rooms}
                rowKey={(row, index) => text(row, "room_key", `room-${index}`)}
                onRowClick={(row) => focusRoom(text(row, "room_key"))}
              />
            )}
          </Panel>

          <Panel icon={GitBranch} title="Governed Workflow Activity" actions={<Badge tone={graphAttention.length ? "warn" : "ok"}>{graphRuns.length}</Badge>}>
            {graphRuns.length === 0 ? (
              <Empty icon={GitBranch} title="No open graph runs" />
            ) : (
              <div style={{ display: "grid", gap: "var(--space-2)" }}>
                {graphRuns.slice(0, 12).map((run) => (
                  <button
                    type="button"
                    key={num(run, "graph_run_id")}
                    onClick={() => navigate("/firm/graphs?run=" + num(run, "graph_run_id"))}
                    style={{ width: "100%", display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "var(--space-2)", padding: "var(--space-2) 0", color: "var(--text)", background: "none", border: 0, borderBottom: "1px solid var(--border-subtle)", textAlign: "left", cursor: "pointer" }}
                    aria-label={"Open evidence for " + text(run, "graph_name") + " run " + num(run, "graph_run_id")}
                  >
                    <span style={{ minWidth: 0 }}>
                      <strong style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "var(--text-sm)" }}>{text(run, "graph_name")}</strong>
                      <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>#{num(run, "graph_run_id")} · {text(run, "subject_ref", "firm-wide")} · {num(run, "completed_node_count")}/{num(run, "completed_node_count") + num(run, "active_node_count") + num(run, "waiting_node_count") + num(run, "failed_node_count")}</span>
                    </span>
                    <StatusPill status={text(run, "run_status")} />
                  </button>
                ))}
              </div>
            )}
            {graphAttention.length > 0 && (
              <div style={{ marginTop: "var(--space-3)", paddingTop: "var(--space-3)", borderTop: "1px solid var(--border-subtle)", display: "grid", gap: "var(--space-2)" }}>
                {graphAttention.slice(0, 8).map((item, index) => (
                  <div key={`${text(item, "attention_kind")}-${num(item, "id", index)}`} style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-2)", fontSize: "var(--text-xs)" }}>
                    <ShieldAlert size={14} style={{ color: "var(--status-warn)", flex: "0 0 auto" }} />
                    <div><strong>{text(item, "title")}</strong><div style={{ color: "var(--text-muted)", marginTop: 2 }}>{text(item, "detail")}</div></div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      )}

      <Panel
        icon={Users}
        title="Employee Operating Board"
        actions={
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            <TextInput aria-label="Search employees" placeholder="Search employees or work" value={search} onChange={(event) => setSearch(event.target.value)} style={{ minWidth: 210 }} />
            <Select aria-label="Filter department" value={department} onChange={(event) => setDepartment(event.target.value)} style={{ minWidth: 210 }}>
              <option value="all">All departments</option>
              {departments.map((name) => <option key={name} value={name}>{name}</option>)}
            </Select>
            <Badge>{filtered.length}</Badge>
          </div>
        }
      >
        {filtered.length === 0 ? (
          <Empty icon={Users} title="No employees in this scope" />
        ) : (
          <DataTable
            dense
            columns={[
              {
                key: "employee",
                header: "Employee",
                render: (row) => (
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      const name = text(row, "agent_name");
                      setAssistantScope({ agentKey: name, agentName: name });
                    }}
                    style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "var(--accent)", background: "none", border: 0, cursor: "pointer", textAlign: "left" }}
                  >
                    <span style={{ width: 28, height: 28, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center", background: "var(--accent-soft)", fontSize: "var(--text-xs)", fontWeight: 650 }}>{initials(text(row, "agent_name"))}</span>
                    <span><strong style={{ display: "block" }}>{text(row, "agent_name")}</strong><small style={{ color: "var(--text-muted)" }}>{text(row, "display_title")}</small></span>
                  </button>
                ),
              },
              { key: "department", header: "Department", render: employeeDepartment },
              { key: "work", header: "Current Work", render: (row) => <div><strong>{text(row, "presence_title", "Available for assignment")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 2 }}>{text(row, "presence_detail", text(row, "presence_reason")).slice(0, 130)}</div></div> },
              { key: "tasks", header: "Tasks", align: "right", render: (row) => num(row, "open_task_count") },
              { key: "inbox", header: "Inbox", align: "right", render: (row) => num(row, "open_inbox_count") },
              { key: "worker", header: "Last Worker", render: (row) => text(row, "latest_worker_skill_name", text(row, "default_model_route", "—")) },
              { key: "state", header: "State", render: (row) => <StatusPill status={employeeState(row)} /> },
            ]}
            rows={filtered}
            rowKey={(row, index) => text(row, "agent_name", `employee-${index}`)}
            onRowClick={(row) => focusRoom(text(row, "department_key", text(row, "department")))}
          />
        )}
      </Panel>

      <Panel icon={Inbox} title="Latest Inter-Agent Handoffs" actions={<Badge>{messages.length}</Badge>}>
        {messages.length === 0 ? (
          <Empty icon={MessageSquare} title="No recorded handoffs" />
        ) : (
          <DataTable
            dense
            columns={[
              { key: "subject", header: "Subject", render: (row) => <strong>{text(row, "subject", "Agent handoff")}</strong> },
              { key: "from", header: "From", render: (row) => text(row, "from_agent") },
              { key: "to", header: "To", render: (row) => text(row, "to_agent") },
              { key: "priority", header: "Priority", render: (row) => <StatusPill status={text(row, "priority", "medium")} /> },
              { key: "state", header: "State", render: (row) => <StatusPill status={text(row, "processing_status", text(row, "status"))} /> },
              { key: "sent", header: "Sent", render: (row) => formatRelative(text(row, "created_at")) },
              {
                key: "evidence",
                header: "",
                render: (row) => {
                  const redacted = text(row, "office_visibility") === "redacted";
                  return (
                    <Button
                      size="sm"
                      icon={redacted ? LockKeyhole : Activity}
                      disabled={redacted}
                      title={redacted ? "Private details are hidden on the shared Office surface." : undefined}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (redacted) return;
                        openEvidence({ kind: "agent-message", key: String(num(row, "id")), title: text(row, "subject", "Agent handoff") });
                      }}
                    >
                      {redacted ? "Private" : "Evidence"}
                    </Button>
                  );
                },
              },
            ]}
            rows={messages}
            rowKey={(row, index) => String(num(row, "id", index))}
          />
        )}
      </Panel>
    </div>
  );
}
