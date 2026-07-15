import { BarChart3, CircleDot, ExternalLink } from "lucide-react";
import type { CSSProperties } from "react";
import type { LiveRow } from "../api/live";

interface Props {
  columns: number;
  data: Record<string, LiveRow[]>;
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

function size(row: LiveRow): string {
  const layout = row.layout && typeof row.layout === "object" ? row.layout as Record<string, unknown> : {};
  const value = String(layout.size ?? "standard");
  return ["standard", "wide", "full"].includes(value) ? value : "standard";
}

function number(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value ?? "-");
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(parsed);
}

function preview(widgetKey: string, row: LiveRow): { title: string; detail: string; value: string } {
  if (widgetKey === "portfolio_latest_positions") return {
    title: `${text(row, "symbol")} · ${text(row, "display_name", text(row, "client_code"))}`,
    detail: `${number(row.quantity)} shares · ${text(row, "account_code")}`,
    value: `INR ${number(row.market_value)}`
  };
  if (widgetKey === "portfolio_book_intelligence") return {
    title: `${text(row, "symbol")} · ${text(row, "client_name")}`,
    detail: `${text(row, "book_count", "0")} books · ${text(row, "overall_bias", "flat")}`,
    value: `INR ${number(row.net_exposure)}`
  };
  if (widgetKey === "strategy_lab_queue") return {
    title: text(row, "strategy_name", text(row, "candidate_key")),
    detail: `${text(row, "validation_status", "pending")} · ${text(row, "owner_agent")}`,
    value: text(row, "activation_gate", text(row, "candidate_status")).replace(/_/g, " ")
  };
  if (widgetKey === "research_filings_inbox") return {
    title: text(row, "company_name", text(row, "symbol", "Filing")),
    detail: text(row, "title", text(row, "filing_type")),
    value: text(row, "extraction_status", text(row, "urgency", "queued")).replace(/_/g, " ")
  };
  if (widgetKey === "model_runtime_status") return {
    title: text(row, "route_name", "Model route").replace(/_/g, " "),
    detail: `${text(row, "default_provider")} · ${text(row, "default_model")}`,
    value: text(row, "runtime_status", text(row, "health_status", "unknown")).replace(/_/g, " ")
  };
  if (widgetKey === "market_signal_monitor") return {
    title: `${text(row, "symbol", "Market")} · ${text(row, "action", "observe")}`,
    detail: text(row, "strategy", "signal"),
    value: row.price === null || row.price === undefined ? text(row, "status") : `INR ${number(row.price)}`
  };
  const entries = Object.entries(row).filter(([, value]) => ["string", "number", "boolean"].includes(typeof value)).slice(0, 3);
  return {
    title: entries[0] ? `${entries[0][0].replace(/_/g, " ")}: ${String(entries[0][1])}` : "Live row",
    detail: entries[1] ? `${entries[1][0].replace(/_/g, " ")}: ${String(entries[1][1])}` : "Source-backed preview",
    value: entries[2] ? String(entries[2][1]) : "live"
  };
}

export default function WorkspaceWidgetRail({ columns, data, widgets, workspaceLabel }: Props) {
  const active = widgets
    .filter((widget) => text(widget, "status", "active") === "active")
    .sort((left, right) => order(left) - order(right));
  if (!active.length) return null;

  return <section aria-label={`${workspaceLabel} live widgets`} className="workspace-live-widget-rail">
    <header><div><BarChart3 size={14}/><h2>Live workspace widgets</h2></div><strong>{active.length} source-bound</strong></header>
    <div className="workspace-live-widget-grid" style={{ "--widget-columns": Math.max(1, Math.min(columns, 3)) } as CSSProperties}>
      {active.map((widget) => {
        const widgetKey = text(widget, "widget_key", "");
        const rows = data[widgetKey] ?? [];
        return <article className={`workspace-widget-${size(widget)}`} key={text(widget, "id")}>
          <div className="workspace-widget-signal"><CircleDot size={12}/><span>{text(widget, "widget_type", "live view").replace(/_/g, " ")}</span></div>
          <strong>{text(widget, "widget_title", "Workspace widget")}</strong>
          <p>{text(widget, "query_ref", "Bound live read model")} · {rows.length} live rows</p>
          <div className="workspace-widget-preview">
            {rows.slice(0, 3).map((row, index) => {
              const item = preview(widgetKey, row);
              return <div key={`${widgetKey}-${index}`}><div><strong>{item.title}</strong><span>{item.detail}</span></div><b>{item.value}</b></div>;
            })}
            {!rows.length ? <span className="workspace-widget-empty">No live rows currently match this binding.</span> : null}
          </div>
          <footer><span>{text(widget, "owner_agent", "Jarvis")}</span><b>{text(widget, "task_status", text(widget, "status", "active")).replace(/_/g, " ")}</b><ExternalLink size={12}/></footer>
        </article>;
      })}
    </div>
  </section>;
}
