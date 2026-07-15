import { BarChart3, CircleDot, ExternalLink } from "lucide-react";
import type { CSSProperties } from "react";
import type { LiveRow } from "../api/live";

interface Props {
  columns: number;
  widgets: LiveRow[];
  workspaceLabel: string;
}

function text(row: LiveRow, key: string, fallback = "-"): string {
  const value = row[key];
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function order(row: LiveRow): number {
  const layout = row.layout && typeof row.layout === "object" ? row.layout as Record<string, unknown> : {};
  const value = Number(layout.order ?? 100);
  return Number.isFinite(value) ? value : 100;
}

export default function WorkspaceWidgetRail({ columns, widgets, workspaceLabel }: Props) {
  const active = widgets
    .filter((widget) => text(widget, "status", "active") === "active")
    .sort((left, right) => order(left) - order(right));
  if (!active.length) return null;

  return <section aria-label={`${workspaceLabel} live widgets`} className="workspace-live-widget-rail">
    <header><div><BarChart3 size={14}/><h2>Live workspace widgets</h2></div><strong>{active.length} source-bound</strong></header>
    <div className="workspace-live-widget-grid" style={{ "--widget-columns": Math.max(1, Math.min(columns, 3)) } as CSSProperties}>
      {active.map((widget) => <article key={text(widget, "id")}>
        <div className="workspace-widget-signal"><CircleDot size={12}/><span>{text(widget, "widget_type", "live view").replace(/_/g, " ")}</span></div>
        <strong>{text(widget, "widget_title", "Workspace widget")}</strong>
        <p>{text(widget, "query_ref", "Bound live read model")}</p>
        <footer><span>{text(widget, "owner_agent", "Jarvis")}</span><b>{text(widget, "task_status", text(widget, "status", "active")).replace(/_/g, " ")}</b><ExternalLink size={12}/></footer>
      </article>)}
    </div>
  </section>;
}
