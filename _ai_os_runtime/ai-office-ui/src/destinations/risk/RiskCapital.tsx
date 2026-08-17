import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, BarChart3, Gauge, LockKeyhole, Play,
  RefreshCw, ShieldAlert, ShieldCheck, Wallet,
} from "lucide-react";
import { usePortfolioOffice, useTradingQuantRisk, useEngageKillSwitch } from "../../data/queries";
import { useRefreshPortfolioRisk, useRunInstitutionalRisk } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Badge, Button, DataTable, Empty, Metric, MetricTile, Panel,
  Skeleton, StatusPill, Tabs,
} from "../../system/primitives";
import { formatCompact, formatPercent, num, text } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "dashboard", label: "Risk Dashboard", icon: ShieldAlert },
  { key: "limits", label: "Limits", icon: Gauge },
  { key: "institutional", label: "Institutional Risk", icon: BarChart3 },
  { key: "capital", label: "Capital Allocation", icon: Wallet },
];

function metricName(row: LiveRow): string {
  return text(row, "metric_name", text(row, "metric", text(row, "name", "Metric")));
}

function metricValue(row: LiveRow): string {
  const unit = text(row, "unit", "");
  const value = num(row, "metric_value", num(row, "value", num(row, "current_value", 0)));
  if (unit.includes("%") || unit.toLowerCase().includes("percent")) {
    return formatPercent(value, { alreadyPercent: true });
  }
  if (unit.toLowerCase().includes("inr")) return formatCompact(value, "INR");
  return Number.isFinite(value) ? value.toLocaleString("en-IN", { maximumFractionDigits: 3 }) : "Unavailable";
}

export default function RiskCapital() {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] || "dashboard";
  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <ShieldAlert size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--status-risk)" }} />
            Risk and Capital
          </div>
          <Badge tone="risk">RISK</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
            independent challenge, limits, stress, liquidity, and allocation
          </span>
        </div>
        <div className="aios-destination__subtitle">
          Live risk evidence and governed capital decisions. Analytics can refresh; broker authority remains separately locked.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={(key) => navigate(`/risk/${key}`)} />
      </div>
      {tab === "dashboard" && <Dashboard />}
      {tab === "limits" && <Limits />}
      {tab === "institutional" && <Institutional />}
      {tab === "capital" && <Capital />}
    </div>
  );
}

function useRiskActions() {
  const pushToast = useUIStore((state) => state.pushToast);
  const refresh = useRefreshPortfolioRisk();
  const run = useRunInstitutionalRisk();
  return {
    refresh: () => refresh.mutate(
      { actor: "Devarsh via Risk Center" },
      {
        onSuccess: () => pushToast({ title: "Risk refresh recorded", tone: "ok", duration: 3000 }),
        onError: (error) => pushToast({ title: "Risk refresh failed", message: error.message, tone: "risk", duration: 5000 }),
      },
    ),
    run: () => run.mutate(
      { actor: "Devarsh via Risk Center" },
      {
        onSuccess: () => pushToast({ title: "Institutional risk run complete", tone: "ok", duration: 3500 }),
        onError: (error) => pushToast({ title: "Risk run failed", message: error.message, tone: "risk", duration: 5000 }),
      },
    ),
    refreshing: refresh.isPending,
    running: run.isPending,
  };
}

function Dashboard() {
  const risk = useTradingQuantRisk();
  const actions = useRiskActions();
  const summary = risk.data?.risk_summary ?? [];
  const institutional = risk.data?.institutional_risk_summary ?? [];
  const limits = risk.data?.risk_limits ?? [];
  const breaches = limits.filter((row) => /breach|critical|blocked|fail/i.test(text(row, "status", "")));
  const execution = risk.data?.execution_control ?? [];
  const locked = execution.length === 0 || execution.every((row) => !Boolean(row.broker_writes_enabled));
  if (risk.isLoading) return <Loading />;
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(175px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Risk Checks" value={summary.length + institutional.length} /></MetricTile>
        <MetricTile><Metric label="Limits" value={limits.length} /></MetricTile>
        <MetricTile tone={breaches.length ? "risk" : "ok"}><Metric label="Breaches" value={breaches.length} /></MetricTile>
        <MetricTile tone={locked ? "ok" : "warn"}><Metric label="Broker Execution" value={locked ? "Locked" : "Review"} /></MetricTile>
      </div>
      <Panel icon={ShieldCheck} title="Independent Risk Summary" actions={
        <div style={{ display: "flex", gap: 8 }}>
          <Button size="sm" icon={RefreshCw} onClick={actions.refresh} disabled={actions.refreshing}>Refresh</Button>
          <Button size="sm" variant="primary" icon={Play} onClick={actions.run} disabled={actions.running}>Run Risk</Button>
        </div>
      }>
        {summary.length + institutional.length === 0 ? (
          <Empty icon={Activity} title="No risk summary" description="Run institutional risk to create a source-backed portfolio assessment." />
        ) : (
          <DataTable rows={[...summary, ...institutional]} rowKey={(row, index) => String(text(row, "id", index))} columns={[
            { key: "metric", header: "Metric", render: (row) => <strong>{metricName(row)}</strong> },
            { key: "scope", header: "Scope", render: (row) => text(row, "scope", text(row, "book_key", "portfolio")) },
            { key: "value", header: "Value", align: "right", render: metricValue },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "measured")} /> },
          ]} />
        )}
      </Panel>
      <Panel icon={LockKeyhole} title="Execution Boundary">
        <div style={{ display: "grid", gap: 10 }}>
          <div><strong>Global execution:</strong> {locked ? "Locked" : "Requires immediate review"}</div>
          <div style={{ color: "var(--text-muted)" }}>Risk analytics and paper workflows cannot create broker orders. Every order intent needs separate limits, approval, and execution checks.</div>
        </div>
      </Panel>
    </>
  );
}

function Limits() {
  const { data, isLoading } = useTradingQuantRisk();
  const kill = useEngageKillSwitch();
  const pushToast = useUIStore((state) => state.pushToast);
  const limits = data?.risk_limits ?? [];
  const execution = data?.execution_control ?? [];
  const locked = execution.length === 0 || execution.every((row) => !Boolean(row.broker_writes_enabled));
  if (isLoading) return <Loading />;
  return (
    <>
      <Panel icon={Gauge} title="Risk Limits" actions={
        <Button
          size="sm"
          variant="danger"
          icon={LockKeyhole}
          disabled={locked || kill.isPending}
          onClick={() => kill.mutate(
            { actor: "Devarsh via Risk Center", reason: "Operator engaged global safety lock" },
            {
              onSuccess: () => pushToast({ title: "Global execution locked", tone: "ok", duration: 3500 }),
              onError: (error) => pushToast({ title: "Kill switch failed", message: error.message, tone: "risk", duration: 5000 }),
            },
          )}
        >{locked ? "Execution Locked" : "Engage Kill Switch"}</Button>
      }>
        {limits.length === 0 ? (
          <Empty icon={Gauge} title="No configured limits" description="Limit configuration must be created through the governed risk-policy workflow." />
        ) : (
          <DataTable rows={limits} rowKey={(row, index) => String(text(row, "id", index))} columns={[
            { key: "limit", header: "Limit", render: (row) => <strong>{text(row, "limit_name", metricName(row))}</strong> },
            { key: "scope", header: "Scope", render: (row) => text(row, "scope", "portfolio") },
            { key: "current", header: "Current", align: "right", render: metricValue },
            { key: "threshold", header: "Threshold", align: "right", render: (row) => num(row, "threshold", num(row, "limit_value", 0)).toLocaleString("en-IN") },
            { key: "status", header: "State", render: (row) => <StatusPill status={text(row, "status", "configured")} /> },
          ]} />
        )}
      </Panel>
      <Panel icon={AlertTriangle} title="Limited-Live Requests">
        <DataTable rows={data?.limited_live_requests ?? []} rowKey={(row, index) => String(text(row, "id", index))} columns={[
          { key: "request", header: "Request", render: (row) => text(row, "request_name", text(row, "strategy_name", "Limited-live request")) },
          { key: "owner", header: "Owner", render: (row) => text(row, "requested_by", text(row, "owner_agent", "Unknown")) },
          { key: "status", header: "State", render: (row) => <StatusPill status={text(row, "status", "pending")} /> },
        ]} />
      </Panel>
    </>
  );
}

function Institutional() {
  const { data, isLoading } = useTradingQuantRisk();
  const actions = useRiskActions();
  if (isLoading) return <Loading />;
  const metrics = data?.institutional_risk_metrics ?? [];
  return (
    <>
      <Panel icon={BarChart3} title="Institutional Metrics" actions={
        <Button size="sm" variant="primary" icon={Play} onClick={actions.run} disabled={actions.running}>Run Institutional Risk</Button>
      }>
        <DataTable rows={metrics} rowKey={(row, index) => String(text(row, "id", index))} columns={[
          { key: "metric", header: "Metric", render: (row) => <strong>{metricName(row)}</strong> },
          { key: "scope", header: "Scope", render: (row) => text(row, "scope", "portfolio") },
          { key: "value", header: "Value", align: "right", render: metricValue },
          { key: "method", header: "Method", render: (row) => text(row, "method", text(row, "calculation_method", "warehouse")) },
          { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "measured")} /> },
        ]} />
      </Panel>
      <Panel icon={AlertTriangle} title="Stress Scenarios">
        <DataTable rows={data?.institutional_stress ?? []} rowKey={(row, index) => String(text(row, "id", index))} columns={[
          { key: "scenario", header: "Scenario", render: (row) => <strong>{text(row, "scenario_name", text(row, "scenario", "Stress"))}</strong> },
          { key: "scope", header: "Scope", render: (row) => text(row, "scope", "portfolio") },
          { key: "loss", header: "Estimated Loss", align: "right", render: (row) => formatCompact(num(row, "estimated_loss", num(row, "loss_amount", num(row, "value", 0))), "INR") },
          { key: "status", header: "State", render: (row) => <StatusPill status={text(row, "status", "measured")} /> },
        ]} />
      </Panel>
      <Panel icon={Activity} title="Liquidity">
        <DataTable rows={data?.institutional_liquidity ?? []} rowKey={(row, index) => String(text(row, "id", index))} columns={[
          { key: "symbol", header: "Symbol", render: (row) => <strong>{text(row, "symbol", "Portfolio")}</strong> },
          { key: "value", header: "Position", align: "right", render: (row) => formatCompact(num(row, "position_value", num(row, "market_value", 0)), "INR") },
          { key: "days", header: "Days to Liquidate", align: "right", render: (row) => num(row, "days_to_liquidate", 0).toFixed(1) },
          { key: "status", header: "Coverage", render: (row) => <StatusPill status={text(row, "status", text(row, "coverage_status", "measured"))} /> },
        ]} />
      </Panel>
    </>
  );
}

function Capital() {
  const portfolio = usePortfolioOffice();
  const risk = useTradingQuantRisk();
  if (portfolio.isLoading || risk.isLoading) return <Loading />;
  const books = portfolio.data?.investment_books ?? [];
  const exposure = portfolio.data?.client_book_exposure ?? [];
  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(175px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Investment Books" value={books.length} /></MetricTile>
        <MetricTile><Metric label="Client/Book Rows" value={exposure.length} /></MetricTile>
        <MetricTile><Metric label="Order Intents" value={risk.data?.order_intents?.length ?? 0} /></MetricTile>
        <MetricTile tone="ok"><Metric label="Broker Authority" value="Locked" /></MetricTile>
      </div>
      <Panel icon={Wallet} title="Book Mandates and Capital">
        <DataTable rows={books} rowKey={(row, index) => String(text(row, "book_key", text(row, "id", index)))} columns={[
          { key: "book", header: "Book", render: (row) => <strong>{text(row, "book_name", text(row, "book_key", "Book"))}</strong> },
          { key: "mandate", header: "Mandate", render: (row) => text(row, "mandate", text(row, "objective", "Defined in book policy")) },
          { key: "horizon", header: "Horizon", render: (row) => text(row, "time_horizon", text(row, "horizon", "Defined")) },
          { key: "status", header: "State", render: (row) => <StatusPill status={text(row, "status", "active")} /> },
        ]} />
      </Panel>
      <Panel icon={BarChart3} title="Client and Book Exposure">
        <DataTable rows={exposure} rowKey={(row, index) => String(text(row, "id", index))} columns={[
          { key: "client", header: "Client", render: (row) => text(row, "client_name", text(row, "client_id", "Client")) },
          { key: "book", header: "Book", render: (row) => text(row, "book_name", text(row, "book_key", "Book")) },
          { key: "gross", header: "Gross Exposure", align: "right", render: (row) => formatCompact(num(row, "gross_exposure", num(row, "market_value", 0)), "INR") },
          { key: "net", header: "Net Exposure", align: "right", render: (row) => formatCompact(num(row, "net_exposure", num(row, "market_value", 0)), "INR") },
          { key: "status", header: "Risk State", render: (row) => <StatusPill status={text(row, "risk_status", text(row, "status", "measured"))} /> },
        ]} />
      </Panel>
      <Panel icon={ShieldCheck} title="Capital Decision Boundary">
        Allocation views are advisory. Rebalance previews cannot become orders without risk checks, committee approval, per-order approval, and an unlocked execution policy.
      </Panel>
    </>
  );
}

function Loading() {
  return (
    <div style={{ display: "grid", gap: "var(--space-3)", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
      {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} style={{ height: 150 }} />)}
    </div>
  );
}
