/**
 * Office View — host for the 3D Live Office.
 *
 * Lazy-loads the R3F scene. Shows a loading state, then the full 3D office.
 * Below the canvas: live office data summary (agents, rooms, messages,
 * risk events, priority tasks).
 */

import React from "react";
import { Boxes, AlertTriangle, Users, MessageSquare, ShieldAlert, ListChecks } from "lucide-react";
import { useOfficeSnapshot } from "../../data/queries";
import { Panel, Empty, Metric, MetricTile, StatusPill, Skeleton } from "../../system/primitives";
import { text, num, formatRelative, initials } from "../../data/liveRow";
import { useUIStore } from "../../store";

// Lazy-load the heavy 3D scene (code-split)
const LiveOffice = React.lazy(() => import("../../office3d/LiveOffice").then((m) => ({ default: m.LiveOffice })));

export function OfficeView() {
  const { data, isLoading, error } = useOfficeSnapshot();
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);

  if (error) {
    return (
      <div className="aios-destination">
        <Panel variant="risk" icon={AlertTriangle} title="Cannot reach office snapshot">
          <div style={{ padding: "var(--space-4)", color: "var(--text-muted)" }}>{error.message}</div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Boxes size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            3D Live Office
          </div>
          {data && <StatusPill tone="ok" dot>{formatRelative(data.generated_at)}</StatusPill>}
        </div>
        <div className="aios-destination__subtitle">
          Walk a real investment firm. Click a room to fly in, hover for status, watch data flow.
        </div>
      </div>

      {/* 3D Office scene */}
      <Panel icon={Boxes} title="The Firm — Floor View" bodyFlush>
        <React.Suspense
          fallback={
            <div style={{ height: 520, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "var(--space-3)", background: "linear-gradient(135deg, var(--bg-sunken), var(--surface-soft))", borderRadius: "var(--radius-lg)", margin: "var(--space-3)" }}>
              <Boxes size={48} style={{ color: "var(--accent)", opacity: 0.4, animation: "aios-risk-pulse 1.5s ease-in-out infinite" }} />
              <div style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>Building the office…</div>
            </div>
          }
        >
          <LiveOffice height={560} />
        </React.Suspense>
      </Panel>

      {/* Live data summary */}
      {isLoading ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} style={{ height: 80 }} />)}
        </div>
      ) : data ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
            <MetricTile><Metric label="Agents Online" value={data.agents?.length ?? 0} /></MetricTile>
            <MetricTile><Metric label="Rooms Active" value={12} sub="3 floors" /></MetricTile>
            <MetricTile><Metric label="Messages" value={data.agent_messages?.length ?? 0} /></MetricTile>
            <MetricTile tone={(data.risk_events?.length ?? 0) > 0 ? "risk" : "ok"}>
              <Metric label="Risk Events" value={data.risk_events?.length ?? 0} sub={(data.risk_events?.length ?? 0) > 0 ? "active" : "within limits"} />
            </MetricTile>
            <MetricTile><Metric label="Priority Tasks" value={data.priority_tasks?.length ?? 0} /></MetricTile>
          </div>

          {/* Active agents grid */}
          <Panel icon={Users} title="Agents on the Floor">
            {(data.agents?.length ?? 0) === 0 ? (
              <Empty icon={Users} title="No agents loaded" description="The office is empty — check that the agent daemon is running." />
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
                {data.agents.slice(0, 12).map((agent, i) => {
                  const name = text(agent, "agent_name", text(agent, "name", `Agent ${i}`));
                  const dept = text(agent, "department");
                  const status = text(agent, "status", "active");
                  return (
                    <div
                      key={i}
                      onClick={() => setAssistantScope({ agentKey: text(agent, "agent_key", name), agentName: name })}
                      style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer" }}
                    >
                      <div style={{
                        width: 36, height: 36, borderRadius: "50%",
                        background: "var(--accent-soft)", color: "var(--accent)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontWeight: 600, fontSize: "var(--text-sm)",
                      }}>
                        {initials(name)}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, fontSize: "var(--text-sm)", color: "var(--text)" }}>{name}</div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{dept}</div>
                      </div>
                      <StatusPill status={status} />
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </>
      ) : null}
    </div>
  );
}
