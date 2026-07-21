import React from "react";
import { AlertTriangle, Database, ExternalLink } from "lucide-react";
import type { LiveRow } from "./liveRow";
import { formatRelative, primaryText, text, truncate } from "./liveRow";
import { Badge, DataTable, Empty, Panel, StatusPill } from "../system/primitives";

export type LiveColumn = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  render?: (row: LiveRow) => React.ReactNode;
};

export function WorkspaceGrid({ children, columns = "2" }: { children: React.ReactNode; columns?: "2" | "3" }) {
  return <div className={`aios-workspace-grid aios-workspace-grid--${columns}`}>{children}</div>;
}

export function MetricStrip({ children }: { children: React.ReactNode }) {
  return <div className="aios-metric-strip">{children}</div>;
}

export function MetricCell({ label, value, detail, tone = "default" }: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: "default" | "ok" | "warn" | "risk";
}) {
  return (
    <div className={`aios-metric-cell aios-metric-cell--${tone}`}>
      <span className="micro">{label}</span>
      <strong className="tnum">{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function LiveTable({ rows, columns, emptyTitle, limit = 80, onRowClick }: {
  rows: LiveRow[];
  columns: LiveColumn[];
  emptyTitle: string;
  limit?: number;
  onRowClick?: (row: LiveRow) => void;
}) {
  return (
    <div className="aios-table-scroll">
      <DataTable<LiveRow>
        dense
        rows={rows.slice(0, limit)}
        rowKey={(row, index) => primaryText(row, ["id", "check_key", "candidate_key", "filing_id", "symbol", "title", "name", "agent_id"]) || String(index)}
        onRowClick={onRowClick}
        columns={columns.map((column) => ({
          key: column.key,
          header: column.label,
          align: column.align,
          render: column.render ?? ((row) => formatCell(row[column.key])),
        }))}
        empty={<Empty icon={Database} title={emptyTitle} description="No source-backed rows are available for this view." />}
      />
    </div>
  );
}

export function StatusCell({ row, keys = ["status"] }: { row: LiveRow; keys?: string[] }) {
  const status = primaryText(row, keys) || "recorded";
  return <StatusPill status={status}>{status.replace(/_/g, " ")}</StatusPill>;
}

export function SourceLink({ row }: { row: LiveRow }) {
  const href = primaryText(row, ["attachment_url", "source_url", "url"]);
  if (!href) return <span className="micro">stored</span>;
  return (
    <a className="aios-source-link" href={href} rel="noreferrer" target="_blank" onClick={(event) => event.stopPropagation()}>
      Source <ExternalLink size={12} />
    </a>
  );
}

export function RowTitle({ row, titleKeys, detailKeys }: { row: LiveRow; titleKeys: string[]; detailKeys?: string[] }) {
  const title = primaryText(row, titleKeys) || "Untitled record";
  const detail = detailKeys ? primaryText(row, detailKeys) : "";
  return (
    <div className="aios-row-title">
      <strong>{truncate(title, 72)}</strong>
      {detail ? <small>{truncate(detail, 96)}</small> : null}
    </div>
  );
}

export function Freshness({ generatedAt }: { generatedAt?: string }) {
  return <Badge tone="ok" dot pulse>{generatedAt ? `Live ${formatRelative(generatedAt)}` : "Connecting"}</Badge>;
}

export function WorkspaceError({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <Panel variant="risk" icon={AlertTriangle} title="Live data unavailable">
      <p className="aios-workspace-error">{error.message}</p>
    </Panel>
  );
}

export function formatCell(value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === "") return <span className="aios-muted">-</span>;
  if (typeof value === "boolean") return <StatusPill tone={value ? "ok" : "neutral"}>{value ? "Yes" : "No"}</StatusPill>;
  if (Array.isArray(value)) return value.length ? <span>{value.slice(0, 3).map(String).join(", ")}</span> : "-";
  if (typeof value === "object") return truncate(JSON.stringify(value), 80);
  const raw = String(value);
  if (/^\d{4}-\d\d-\d\d[T ]/.test(raw)) return new Date(raw).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  return truncate(raw.replace(/_/g, " "), 96);
}

export function countStatus(rows: LiveRow[], words: string[]): number {
  return rows.filter((row) => {
    const haystack = Object.values(row).filter((value) => typeof value === "string").join(" ").toLowerCase();
    return words.some((word) => haystack.includes(word));
  }).length;
}

export function numberFrom(row: LiveRow | undefined, keys: string[]): number {
  for (const key of keys) {
    const value = Number(row?.[key]);
    if (Number.isFinite(value)) return value;
  }
  return 0;
}

export function labelFrom(row: LiveRow | undefined, keys: string[], fallback = "-"): string {
  for (const key of keys) {
    const value = text(row, key, "").trim();
    if (value) return value;
  }
  return fallback;
}
