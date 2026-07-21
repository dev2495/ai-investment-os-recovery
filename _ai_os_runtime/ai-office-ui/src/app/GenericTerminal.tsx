/**
 * Generic Terminal Renderer
 *
 * Renders any terminal function that doesn't have a dedicated component.
 * Pulls the most relevant snapshot(s) for the function's group, shows
 * metric tiles, a primary data table, and a side panel of related queues.
 *
 * This is the "good enough" Bloomberg-style screen: dense, scannable,
 * evidence-linked. Specialized functions (Today, Office, etc.) get their
 * own components; the rest use this until they're promoted.
 */

import React from "react";
import { useLocation } from "react-router-dom";
import {
  Panel,
  MetricTile,
  Metric,
  DataTable,
  StatusPill,
  Badge,
  Empty,
  Skeleton,
  Button,
} from "../system/primitives";
import { functionForPath } from "./destinations";
import { text, num, formatRelative } from "../data/liveRow";
import type { LiveRow } from "../data/liveRow";
import {
  useTradingQuantRisk,
  usePortfolioOffice,
  useResearchIdeas,
  useStrategyArsenal,
  useReports,
  useSystemHealth,
  useMissionControl,
} from "../data/queries";

interface GenericTerminalProps {
  path?: string;
}

export function GenericTerminal({ path }: GenericTerminalProps) {
  const location = useLocation();
  const fn = functionForPath(path ?? location.pathname);

  if (!fn) {
    return (
      <div className="aios-destination">
        <Empty title="Function not found" description="This terminal function isn't registered." />
      </div>
    );
  }

  // Pick the snapshot based on group
  const snapshot = useSnapshotForGroup(fn.group);

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <fn.icon size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            {fn.label}
          </div>
          <Badge tone="accent">{fn.code}</Badge>
          {fn.status === "preview" && <Badge tone="warn" dot>preview</Badge>}
          {fn.status === "beta" && <Badge tone="info" dot>beta</Badge>}
        </div>
        <div className="aios-destination__subtitle">{fn.description}</div>
      </div>

      <TerminalContent fn={fn} snapshot={snapshot} />
    </div>
  );
}

/** Minimal common shape all snapshots satisfy (for the generic renderer). */
interface SnapshotResult {
  data: Record<string, unknown> | undefined;
  isLoading: boolean;
  error: Error | null;
}

/** Pick the right snapshot hook for a function group. */
function useSnapshotForGroup(group: string): SnapshotResult {
  switch (group) {
    case "trading":
    case "options":
    case "risk": {
      const q = useTradingQuantRisk();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    case "portfolio": {
      const q = usePortfolioOffice();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    case "fundamental":
    case "research": {
      const q = useResearchIdeas();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    case "quant": {
      const q = useStrategyArsenal();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    case "macro": {
      const q = useMissionControl();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    case "firm": {
      const q = useSystemHealth();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
    default: {
      const q = useMissionControl();
      return { data: q.data as Record<string, unknown> | undefined, isLoading: q.isLoading, error: q.error };
    }
  }
}

/** Render metric tiles + data table + side panel from the snapshot. */
function TerminalContent({
  fn,
  snapshot,
}: {
  fn: NonNullable<ReturnType<typeof functionForPath>>;
  snapshot: SnapshotResult;
}) {
  const { data, isLoading, error } = snapshot;

  if (error) {
    return (
      <Panel variant="risk" title="Data unavailable">
        <div style={{ padding: "var(--space-4)", color: "var(--text-muted)" }}>
          {error.message}
          <div style={{ marginTop: "var(--space-3)" }}>
            <Button size="sm" onClick={() => window.location.reload()}>Retry</Button>
          </div>
        </div>
      </Panel>
    );
  }

  if (isLoading || !data) {
    return (
      <>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} style={{ height: 88 }} />)}
        </div>
        <Panel title="Loading">
          <Skeleton style={{ height: 200 }} />
        </Panel>
      </>
    );
  }

  // Heuristically pick the primary data array(s) for this function
  const primary = pickPrimaryArray(fn.path, data);
  const secondary = pickSecondaryArray(fn.path, data);

  const metrics = computeMetrics(primary, secondary);

  return (
    <>
      {/* Metric strip */}
      {metrics.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
          {metrics.map((m, i) => (
            <MetricTile key={i} tone={m.tone}>
              <Metric label={m.label} value={m.value} sub={m.sub} />
            </MetricTile>
          ))}
        </div>
      )}

      {/* Primary table + secondary panel */}
      <div style={{ display: "grid", gridTemplateColumns: secondary.length > 0 ? "2fr 1fr" : "1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel title={primary.label} icon={fn.icon}>
          {primary.rows.length === 0 ? (
            <Empty icon={fn.icon} title={`No ${primary.label.toLowerCase()} yet`} description={`This ${fn.label.toLowerCase()} will populate as the office produces data.`} />
          ) : (
            <DataTable
              columns={inferColumns(primary.rows, fn.path)}
              rows={primary.rows.slice(0, 50)}
              rowKey={(row, i) => String(text(row, "id", text(row, "key", i)))}
              hoverable
            />
          )}
        </Panel>

        {secondary.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            {secondary.map((sec, i) => (
              <Panel key={i} title={sec.label}>
                {sec.rows.length === 0 ? (
                  <div style={{ padding: "var(--space-3)", color: "var(--text-faint)", fontSize: "var(--text-sm)" }}>None.</div>
                ) : (
                  <DataTable
                    columns={inferColumns(sec.rows.slice(0, 10), fn.path).slice(0, 3)}
                    rows={sec.rows.slice(0, 10)}
                    rowKey={(row, idx) => String(text(row, "id", text(row, "key", idx)))}
                    dense
                  />
                )}
              </Panel>
            ))}
          </div>
        )}
      </div>

      {/* Snapshot freshness footer */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "var(--space-2)", color: "var(--text-faint)", fontSize: "var(--text-xs)" }}>
        <span>Snapshot</span>
        <StatusPill status={formatRelative(text(data, "generated_at"))} />
      </div>
    </>
  );
}

/* ============================================================
 * Heuristic data pickers — choose the most relevant arrays
 * for a given function path. Maps function → snapshot array keys.
 * ============================================================ */
type ArrayData = { label: string; rows: LiveRow[] };

function pickPrimaryArray(path: string, data: Record<string, unknown>): ArrayData {
  const map: Record<string, string> = {
    "/trading/blotter": "trade_activity",
    "/trading/journal": "paper_trade_summary",
    "/trading/signals": "signals",
    "/trading/alpha": "paper_trade_summary",
    "/trading/execution": "execution_control",
    "/options/desk": "options_surface",
    "/options/chain": "option_chain",
    "/options/surface": "options_surface",
    "/risk/dashboard": "risk_summary",
    "/risk/limits": "risk_limits",
    "/risk/institutional": "institutional_risk_metrics",
    "/risk/capital": "institutional_risk_summary",
    "/portfolio/overview": "portfolio_intelligence",
    "/portfolio/positions": "latest_positions",
    "/portfolio/books": "investment_books",
    "/portfolio/clients": "clients",
    "/portfolio/nav": "client_nav",
    "/portfolio/reconciliation": "holding_reconciliation",
    "/portfolio/trackers": "latest_positions",
    "/quant/lab": "quant_lab",
    "/quant/backtests": "quant_lab",
    "/quant/model-validation": "model_validation",
    "/quant/promotion": "promotion_board",
    "/macro/news": "signals",
    "/research/filings": "corporate_filings",
    "/research/special-situations": "special_situations",
    "/research/papers": "research_papers",
  };
  const key = map[path];
  const rows = (key && Array.isArray(data[key]) ? data[key] : []) as LiveRow[];
  return { label: key ? key.replace(/_/g, " ") : "Data", rows };
}

function pickSecondaryArray(path: string, data: Record<string, unknown>): ArrayData[] {
  const map: Record<string, string[]> = {
    "/trading/blotter": ["signals", "alerts"],
    "/risk/dashboard": ["risk_limits", "alerts"],
    "/portfolio/positions": ["symbol_book_exposure", "manual_updates"],
    "/portfolio/clients": ["client_nav", "client_performance"],
    "/quant/lab": ["promotion_board", "retirement_queue"],
  };
  const keys = map[path] ?? [];
  return keys
    .filter((k) => Array.isArray(data[k]))
    .map((k) => ({ label: k.replace(/_/g, " "), rows: data[k] as LiveRow[] }));
}

/* ============================================================
 * Metric computation — derive a few headline numbers from arrays
 * ============================================================ */
function computeMetrics(primary: ArrayData, secondary: ArrayData[]) {
  const metrics: Array<{ label: string; value: string | number; sub?: string; tone?: "default" | "risk" | "warn" | "ok" }> = [];

  metrics.push({ label: "Total", value: primary.rows.length, sub: primary.label });

  // Count by status if a status column exists
  const statusCounts = new Map<string, number>();
  for (const row of primary.rows) {
    const status = text(row, "status", text(row, "state", text(row, "freshness_status", ""))).toLowerCase();
    if (status) statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
  }
  const breach = statusCounts.get("breach") ?? statusCounts.get("critical") ?? 0;
  const pending = statusCounts.get("pending") ?? statusCounts.get("awaiting") ?? 0;
  const active = statusCounts.get("active") ?? statusCounts.get("running") ?? statusCounts.get("ok") ?? 0;

  if (breach > 0) metrics.push({ label: "Breaches / Critical", value: breach, tone: "risk", sub: "needs attention" });
  if (pending > 0) metrics.push({ label: "Pending", value: pending, tone: "warn", sub: "awaiting" });
  if (active > 0) metrics.push({ label: "Active / OK", value: active, tone: "ok" });

  // Sum a numeric column if one looks like a value
  const sample = primary.rows[0];
  if (sample) {
    const valueKey = Object.keys(sample).find((k) =>
      /^(value|amount|quantity|qty|nav|exposure|pnl|notional|price)$/i.test(k)
    );
    if (valueKey) {
      const sum = primary.rows.reduce((acc, r) => acc + num(r, valueKey, 0), 0);
      if (sum > 0) metrics.push({ label: `Sum ${valueKey}`, value: formatCompactSafe(sum), sub: `of ${primary.rows.length}` });
    }
  }

  for (const sec of secondary.slice(0, 1)) {
    metrics.push({ label: sec.label, value: sec.rows.length });
  }

  return metrics.slice(0, 6);
}

function formatCompactSafe(n: number): string {
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(1)}Cr`;
  if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(1)}L`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(Math.round(n));
}

/* ============================================================
 * Column inference — pick sensible columns from row keys
 * ============================================================ */
function inferColumns(rows: LiveRow[], _path: string) {
  if (rows.length === 0) {
    return [{ key: "empty", header: "No data", render: () => "—" }];
  }
  const sample = rows[0];
  const allKeys = Object.keys(sample).filter((k) => {
    const v = sample[k];
    return v !== null && v !== undefined && typeof v !== "object";
  });

  // Priority: name/title/symbol/code columns first, then status, then value/amount, then timestamps
  const priority = [
    "symbol", "ticker", "name", "title", "label", "client_name", "book_name", "strategy_name",
    "headline", "subject", "department_name", "agent_name",
  ];
  const statusKeys = ["status", "state", "freshness_status", "run_status", "approval_status"];
  const valueKeys = ["value", "amount", "quantity", "qty", "nav", "exposure", "pnl", "notional", "price", "weight", "score"];
  const timeKeys = ["created_at", "updated_at", "generated_at", "published_at", "event_date", "as_of", "checked_at", "last_check_at"];

  const cols: Array<{ key: string; header: string; align?: "left" | "right"; render?: (row: LiveRow) => React.ReactNode }> = [];

  for (const p of priority) {
    if (allKeys.includes(p)) {
      cols.push({
        key: p,
        header: p.replace(/_/g, " "),
        render: (row) => <strong>{text(row, p)}</strong>,
      });
      break;
    }
  }

  // Add up to 2 more descriptive columns
  const descKeys = allKeys.filter((k) => ![...priority, ...statusKeys, ...valueKeys, ...timeKeys].includes(k) && cols.length < 3);
  for (const k of descKeys.slice(0, 2)) {
    cols.push({ key: k, header: k.replace(/_/g, " "), render: (row) => truncateText(text(row, k), 40) });
  }

  // Value column (right-aligned)
  for (const vk of valueKeys) {
    if (allKeys.includes(vk)) {
      cols.push({ key: vk, header: vk.replace(/_/g, " "), align: "right", render: (row) => formatCompactSafe(num(row, vk, 0)) });
      break;
    }
  }

  // Status column
  for (const sk of statusKeys) {
    if (allKeys.includes(sk)) {
      cols.push({ key: sk, header: "status", render: (row) => <StatusPill status={text(row, sk)} /> });
      break;
    }
  }

  // Time column
  for (const tk of timeKeys) {
    if (allKeys.includes(tk)) {
      cols.push({ key: tk, header: "when", render: (row) => <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{formatRelative(text(row, tk))}</span> });
      break;
    }
  }

  return cols.length > 0 ? cols : allKeys.slice(0, 5).map((k) => ({ key: k, header: k.replace(/_/g, " ") }));
}

function truncateText(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}
