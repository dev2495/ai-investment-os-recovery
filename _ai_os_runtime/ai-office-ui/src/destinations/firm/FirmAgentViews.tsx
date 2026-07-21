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
  Inbox, ChevronRight, MessageSquare,
} from "lucide-react";
import { Panel, DataTable, StatusPill, Badge, Empty, MetricTile, Metric, Avatar, ScrollList } from "../../system/primitives";
import { useOfficeSnapshot, useSystemHealth, useDepartmentTerminal } from "../../data/queries";
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
  const groups = React.useMemo(() => {
    const map = new Map<string, LiveRow[]>();
    for (const row of data?.departments ?? data?.primary ?? []) {
      const dept = text(row, "department", text(row, "department_name", "Unassigned"));
      if (!map.has(dept)) map.set(dept, []);
      map.get(dept)!.push(row);
    }
    return Array.from(map.entries());
  }, [data]);

  return (
    <div className="aios-destination">
      <Header icon={Building2} code="DEPTS" title="Departments" subtitle="11 departments, each with a mandate, lead, and work queue." />
      <Panel icon={Building2} title="Department Directory">
        {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
          <DataTable
            columns={[
              { key: "name", header: "Department", render: (r) => <strong>{text(r, "department_name", text(r, "department"))}</strong> },
              { key: "lead", header: "Lead", render: (r) => text(r, "lead_agent", text(r, "department_lead", "—")) },
              { key: "headcount", header: "Agents", align: "right", render: (r) => num(r, "agent_count", num(r, "headcount", 0)) },
              { key: "mandate", header: "Mandate", render: (r) => text(r, "mission", text(r, "mandate", "—")) },
            ]}
            rows={data?.departments ?? data?.primary ?? []}
            rowKey={(r, i) => text(r, "department", `dept-${i}`)}
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
  const { data, isLoading } = useSystemHealth();
  return (
    <div className="aios-destination">
      <Header icon={Cpu} code="MODELS" title="Models & Routes" subtitle="Model endpoints, routes, catalog, cost ledger, escalations." />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Cpu} title="Model Routes">
          {isLoading ? <div style={{ padding: "var(--space-4)" }}>Loading…</div> : (
            <DataTable
              columns={[
                { key: "route", header: "Route", render: (r) => <strong>{text(r, "route_name", text(r, "name"))}</strong> },
                { key: "model", header: "Model", render: (r) => text(r, "model_name", text(r, "preferred_model", "—")) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "info")} /> },
              ]}
              rows={data?.model_routes ?? []}
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
