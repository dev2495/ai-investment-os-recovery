import {
  Activity,
  Bot,
  Database,
  Gauge,
  HardDrive,
  RefreshCw,
  ShieldCheck,
  Workflow
} from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { LiveRow } from "../api/live";
import { fetchSystemHealthSnapshot, type SystemHealthSnapshot } from "../api/systemHealth";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";

interface SystemHealthWorkspaceProps {
  onStatusChange: (status: ConnectionStatus) => void;
}

function text(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const value = row?.[key];
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function metric(rows: LiveRow[], key: string, fallback = "0"): string {
  return text(rows.find((row) => text(row, "metric", "") === key), "value", fallback);
}

function date(value: unknown): string {
  if (!value) return "not checked";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime())
    ? String(value)
    : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["ready", "healthy", "ok", "online", "active", "completed", "fresh", "passed", "green", "configured", "locked"].includes(normalized)) return "active";
  if (["blocked", "failed", "error", "offline", "critical", "stale"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function HealthPanel({
  action,
  children,
  className,
  icon,
  title
}: {
  action?: ReactNode;
  children: ReactNode;
  className: string;
  icon: ReactNode;
  title: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          {icon}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export default function SystemHealthWorkspace({ onStatusChange }: SystemHealthWorkspaceProps) {
  const [snapshot, setSnapshot] = useState<SystemHealthSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchSystemHealthSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "System Health API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:system-health-refresh", handleRefresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("aios:system-health-refresh", handleRefresh);
    };
  }, [refresh]);

  const storageReady = useMemo(
    () => snapshot ? Object.values(snapshot.storage).every(Boolean) : false,
    [snapshot]
  );
  const latestSync = snapshot?.blueprint_sync_runs[0];
  const execution = snapshot?.execution_control[0];
  const readyModels = snapshot?.provider_readiness_board.filter(
    (row) => text(row, "provider_kind", "") === "model_endpoint" && text(row, "assignable", "false") === "true"
  ).length ?? 0;
  const readyProviders = metric(snapshot?.provider_readiness_summary ?? [], "ready_providers");
  const sourceIssues = snapshot?.source_freshness.filter((row) => text(row, "status", "fresh") !== "fresh").length ?? 0;

  return (
    <div className="system-health-workspace">
      <section className="metric-grid" aria-label="System operating metrics">
        <div className="metric-tile">
          <span>Scoped API</span>
          <strong>{status === "online" ? "Online" : status}</strong>
          <p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p>
        </div>
        <div className="metric-tile">
          <span>External Storage</span>
          <strong>{storageReady ? "Ready" : "Check"}</strong>
          <p className={storageReady ? "tone-good" : "tone-warn"}>vault · Docker · models · state</p>
        </div>
        <div className="metric-tile">
          <span>Blueprint</span>
          <strong>{metric(snapshot?.blueprint_summary ?? [], "blueprint_version", "-")}</strong>
          <p className="tone-neutral">{metric(snapshot?.blueprint_summary ?? [], "requirements")} requirements</p>
        </div>
        <div className="metric-tile">
          <span>Local Models</span>
          <strong>{readyModels}</strong>
          <p className="tone-neutral">{snapshot?.model_endpoints.length ?? 0} endpoints</p>
        </div>
        <div className="metric-tile">
          <span>Source Issues</span>
          <strong>{sourceIssues}</strong>
          <p className={sourceIssues ? "tone-warn" : "tone-good"}>{snapshot?.data_sources.length ?? 0} sources tracked</p>
        </div>
      </section>

      <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status} />
      {error ? <div className="error-strip">{error}</div> : null}

      <section className="dashboard-grid">
        <HealthPanel
          action={
            <button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button" title="Refresh System Health">
              <RefreshCw size={14} aria-hidden="true" />
              {status === "loading" ? "Checking" : "Refresh"}
            </button>
          }
          className="span-7"
          icon={<ShieldCheck size={17} />}
          title="Runtime Safety"
        >
          <div className="source-check-list">
            <article className="source-check-row">
              <div><strong>Broker execution</strong><p>{text(execution, "lock_reason", "Safety state not loaded")}</p></div>
              <StatusPill status={text(execution, "global_execution_locked", "true") === "true" ? "locked" : "unlocked"} />
              <span>{text(execution, "broker_execution_policy", "approval gated")}</span>
              <time>{date(execution?.updated_at)}</time>
            </article>
            <article className="source-check-row">
              <div><strong>TradingView Desktop</strong><p>CDP-controlled chart workspace</p></div>
              <StatusPill status={snapshot?.tradingview_cdp.available ? "online" : "degraded"} />
              <span>:{snapshot?.tradingview_cdp.port ?? 9222}</span>
              <time>{date(snapshot?.generated_at)}</time>
            </article>
            {Object.entries(snapshot?.storage ?? {}).map(([key, value]) => (
              <article className="source-check-row" key={key}>
                <div><strong>{key.replace(/_/g, " ")}</strong><p>External storage contract</p></div>
                <StatusPill status={value ? "ready" : "blocked"} />
                <span>{value ? "external" : "missing"}</span>
                <time>{date(snapshot?.generated_at)}</time>
              </article>
            ))}
          </div>
        </HealthPanel>

        <HealthPanel className="span-5" icon={<Workflow size={17} />} title="Blueprint v10">
          <div className="employee-profile-summary">
            <div className="employee-profile-metric"><strong>{metric(snapshot?.blueprint_summary ?? [], "done_requirements")}</strong><span>done</span></div>
            <div className="employee-profile-metric"><strong>{metric(snapshot?.blueprint_summary ?? [], "partial_requirements")}</strong><span>partial</span></div>
            <div className="employee-profile-metric"><strong>{metric(snapshot?.blueprint_summary ?? [], "planned_requirements")}</strong><span>planned</span></div>
          </div>
          <div className="source-check-list">
            {snapshot?.blueprint_domains.map((domain) => (
              <article className="source-check-row" key={text(domain, "domain_key")}>
                <div><strong>{text(domain, "section_number")} · {text(domain, "domain_name")}</strong><p>{text(domain, "next_action", "No open action")}</p></div>
                <StatusPill status={text(domain, "status", "planned")} />
                <span>{text(domain, "progress_score", "0")}%</span>
              </article>
            )) ?? <Empty>No blueprint domains loaded.</Empty>}
          </div>
          <div className="source-check-row">
            <div><strong>{text(latestSync, "run_key", "No sync run")}</strong><p>{text(latestSync, "source_sha256", "No checklist hash")}</p></div>
            <StatusPill status={text(latestSync, "status", "unknown")} />
            <time>{date(latestSync?.finished_at)}</time>
          </div>
        </HealthPanel>

        <HealthPanel className="span-6" icon={<Bot size={17} />} title="Model Runtime" action={<span>{readyModels} ready</span>}>
          <div className="source-check-list system-health-list">
            {snapshot?.model_endpoints.map((endpoint) => (
              <article className="source-check-row" key={text(endpoint, "endpoint_key")}>
                <div><strong>{text(endpoint, "model_name")}</strong><p>{text(endpoint, "route_name")} · {text(endpoint, "provider")}</p></div>
                <StatusPill status={text(endpoint, "health_status", text(endpoint, "status", "unknown"))} />
                <span>{text(endpoint, "last_latency_ms", "-")} ms</span>
                <time>{date(endpoint.last_checked_at)}</time>
              </article>
            )) ?? <Empty>No model endpoints configured.</Empty>}
          </div>
        </HealthPanel>

        <HealthPanel className="span-6" icon={<Gauge size={17} />} title="Provider Readiness" action={<span>{readyProviders} ready</span>}>
          <div className="source-check-list system-health-list">
            {snapshot?.provider_readiness_board.slice(0, 16).map((provider) => (
              <article className="source-check-row" key={`${text(provider, "provider_kind")}-${text(provider, "provider_key")}`}>
                <div><strong>{text(provider, "provider_name", text(provider, "subject_name"))}</strong><p>{text(provider, "next_action", "No action required")}</p></div>
                <StatusPill status={text(provider, "readiness_status", "unknown")} />
                <span>{text(provider, "assignable", "false") === "true" ? "assignable" : "gated"}</span>
                <time>{date(provider.last_checked_at)}</time>
              </article>
            )) ?? <Empty>No provider readiness rows.</Empty>}
          </div>
        </HealthPanel>

        <HealthPanel className="span-7" icon={<Database size={17} />} title="Data Source Freshness">
          <div className="source-check-list system-health-list">
            {snapshot?.source_freshness.map((source) => (
              <article className="source-check-row" key={text(source, "source_key")}>
                <div><strong>{text(source, "source_name", text(source, "source_key"))}</strong><p>target {text(source, "freshness_target_minutes")} min · stale {text(source, "staleness_minutes")} min</p></div>
                <StatusPill status={text(source, "status", "unknown")} />
                <span>{text(source, "rows_seen", "0")} rows</span>
                <time>{date(source.created_at)}</time>
              </article>
            )) ?? <Empty>No freshness checks recorded.</Empty>}
          </div>
        </HealthPanel>

        <HealthPanel className="span-5" icon={<Activity size={17} />} title="Connector Ledger">
          <div className="source-check-list system-health-list">
            {snapshot?.connector_health_checks.slice(0, 16).map((check) => (
              <article className="source-check-row" key={`${text(check, "target_kind")}-${text(check, "target_key")}-${text(check, "checked_at")}`}>
                <div><strong>{text(check, "target_key")}</strong><p>{text(check, "target_kind")} · {text(check, "check_name")}</p></div>
                <StatusPill status={text(check, "status", "unknown")} />
                <span>{text(check, "latency_ms", "-")} ms</span>
                <time>{date(check.checked_at)}</time>
              </article>
            )) ?? <Empty>No connector checks recorded.</Empty>}
          </div>
        </HealthPanel>

        <HealthPanel className="span-12" icon={<HardDrive size={17} />} title="Pipeline Inventory" action={<span>no seed mode</span>}>
          <div className="pipeline-list">
            {snapshot?.pipeline_readiness.map((row) => (
              <article className="pipeline-row" key={text(row, "relation_name")}>
                <div><strong>{text(row, "area")}</strong><p>{text(row, "relation_name")}</p></div>
                <StatusPill status={text(row, "record_class", "unknown")} />
                <span>{text(row, "row_count", "0")}</span>
              </article>
            )) ?? <Empty>No pipeline rows loaded.</Empty>}
          </div>
        </HealthPanel>
      </section>
    </div>
  );
}
