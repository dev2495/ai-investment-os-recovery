/**
 * Trading Desk Terminal
 *
 * Routes: /trading/blotter | /journal | /tradingview | /alpha | /signals | /execution
 *
 * The manual trading home — blotter, annotated journal, TradingView bridge
 * (chart actions, Pine indicators, alert requests), the alpha tracker
 * (P&L attribution + edge decay), live signals, and execution safety
 * (kill-switch, limited-live requests, gates).
 *
 * Live auto-execution is NOT here — only manual + paper trades, and
 * approval-gated controls.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  TrendingUp, Notebook, LineChart, Target, Zap, ShieldCheck,
  Plus, Play, AlertTriangle, Activity, ChevronRight,
} from "lucide-react";
import { useTradingQuantRisk } from "../../data/queries";
import { useRecordManualTrade, useRecordPaperTrade } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select, KeyValue,
} from "../../system/primitives";
import { AreaSeriesChart, BarSeriesChart } from "../../system/charts";
import { text, num, formatRelative, formatCurrency, formatCompact, formatPercent } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "blotter", label: "Blotter", icon: TrendingUp },
  { key: "journal", label: "Journal", icon: Notebook },
  { key: "tradingview", label: "TradingView", icon: LineChart },
  { key: "alpha", label: "Alpha Tracker", icon: Target },
  { key: "signals", label: "Signals", icon: Zap },
  { key: "execution", label: "Execution Safety", icon: ShieldCheck },
];

export default function TradingDesk({ defaultTab = "blotter" }: { defaultTab?: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;
  function setTab(key: string) { navigate(`/trading/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <TrendingUp size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Trading Desk
          </div>
          <Badge tone="accent">BLT</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>manual + paper · approval-gated</span>
        </div>
        <div className="aios-destination__subtitle">
          Blotter, annotated journal, TradingView bridge, alpha tracker, live signals, and execution safety.
          No auto-execution — by design.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "blotter" && <BlotterView />}
      {tab === "journal" && <JournalView />}
      {tab === "tradingview" && <TradingViewBridgeView />}
      {tab === "alpha" && <AlphaView />}
      {tab === "signals" && <SignalsView />}
      {tab === "execution" && <ExecutionView />}
    </div>
  );
}

/* ============================================================
 * BLOTTER
 * ============================================================ */
function BlotterView() {
  const { data, isLoading } = useTradingQuantRisk();
  const trades = data?.trade_activity ?? [];
  const [showTicket, setShowTicket] = React.useState(false);
  const [showPaper, setShowPaper] = React.useState(false);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Total Trades" value={trades.length} /></MetricTile>
        <MetricTile><Metric label="Paper Trades" value={trades.filter((r) => text(r, "trade_kind", "").includes("paper")).length} /></MetricTile>
        <MetricTile><Metric label="Live Signals" value={data?.signals?.length ?? 0} /></MetricTile>
        <MetricTile tone={data?.alerts?.length ? "warn" : "ok"}><Metric label="Active Alerts" value={data?.alerts?.length ?? 0} /></MetricTile>
      </div>

      <Panel icon={TrendingUp} title="Trade Blotter"
        actions={
          <>
            <Button size="sm" variant="ghost" icon={Notebook} onClick={() => setShowPaper(true)}>Paper Trade</Button>
            <Button size="sm" variant="primary" icon={Plus} onClick={() => setShowTicket(true)}>Manual Trade</Button>
          </>
        }
      >
        {isLoading ? <SkeletonGrid rows={6} /> : trades.length === 0 ? (
          <Empty icon={TrendingUp} title="No trades yet" description="Record a manual or paper trade to populate the blotter." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "side", header: "Side", render: (r) => <StatusPill status={text(r, "side", "buy")} /> },
              { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "quantity", 0) },
              { key: "price", header: "Price", align: "right", render: (r) => formatCurrency(num(r, "price", num(r, "avg_price", 0))) },
              { key: "kind", header: "Kind", render: (r) => text(r, "trade_kind", text(r, "source", "manual")) },
              { key: "date", header: "Date", render: (r) => text(r, "trade_date", text(r, "executed_at", "—")) },
              { key: "book", header: "Book", render: (r) => text(r, "book_key", "—") },
            ]}
            rows={trades}
            rowKey={(r, i) => String(text(r, "trade_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <TradeTicketDrawer open={showTicket} onClose={() => setShowTicket(false)} paper={false} />
      <TradeTicketDrawer open={showPaper} onClose={() => setShowPaper(false)} paper />
    </>
  );
}

function TradeTicketDrawer({ open, onClose, paper }: { open: boolean; onClose: () => void; paper: boolean }) {
  const manualMut = useRecordManualTrade();
  const paperMut = useRecordPaperTrade();
  const mut = paper ? paperMut : manualMut;
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({ symbol: "", side: "buy", quantity: 1, price: 0, book_key: "", purpose: "", thesis: "", notes: "" });

  function submit() {
    if (!form.symbol) { pushToast({ title: "Symbol required", tone: "warn", duration: 2500 }); return; }
    mut.mutate({ ...form, quantity: Number(form.quantity), price: Number(form.price), side: form.side as "buy" | "sell", actor: "Devarsh" } as any, {
      onSuccess: () => { pushToast({ title: `${paper ? "Paper" : "Manual"} trade recorded`, message: form.symbol, tone: "ok", duration: 3000 }); onClose(); },
      onError: (e) => pushToast({ title: "Record failed", message: e.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <Drawer open={open} onClose={onClose} title={paper ? "Record Paper Trade" : "Record Manual Trade"} icon={paper ? Notebook : Plus} width={520}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Play} onClick={submit} disabled={mut.isPending}>Record</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <Field label="Symbol" required><TextInput value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} placeholder="e.g. RELIANCE" /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Side"><Select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value })}><option value="buy">Buy</option><option value="sell">Sell</option></Select></Field>
          <Field label="Book"><Select value={form.book_key} onChange={(e) => setForm({ ...form, book_key: e.target.value })}><option value="">—</option><option>long_term</option><option>tactical</option><option>quant</option><option>active_trading</option></Select></Field>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Quantity"><TextInput type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} /></Field>
          <Field label="Price"><TextInput type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} /></Field>
        </div>
        <Field label="Thesis / Reasoning"><TextArea value={form.thesis} onChange={(e) => setForm({ ...form, thesis: e.target.value })} rows={3} placeholder="Why this trade? What's the edge? What invalidates it?" /></Field>
        {!paper && (
          <div style={{ padding: "var(--space-3)", background: "var(--status-warn-soft)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", color: "var(--status-warn)" }}>
            <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} />
            Manual record only. No live order is placed. This is for tracking trades you executed in your broker.
          </div>
        )}
      </div>
    </Drawer>
  );
}

/* ============================================================
 * JOURNAL — annotated trade reasoning
 * ============================================================ */
function JournalView() {
  const { data, isLoading } = useTradingQuantRisk();
  const trades = data?.trade_activity ?? [];
  const paperSummary = data?.paper_trade_summary ?? [];

  return (
    <>
      <Panel icon={Notebook} title="Trade Journal">
        {isLoading ? <SkeletonGrid rows={4} /> : trades.length === 0 ? (
          <Empty icon={Notebook} title="No journal entries" description="Trades recorded with thesis text appear here as journal entries for later mining." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            {trades.slice(0, 20).map((trade, i) => {
              const thesis = text(trade, "thesis", text(trade, "notes", ""));
              return (
                <div key={i} style={{ padding: "var(--space-4)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginBottom: "var(--space-2)" }}>
                    <strong style={{ fontSize: "var(--text-md)" }}>{text(trade, "symbol")}</strong>
                    <StatusPill status={text(trade, "side", "buy")} />
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{num(trade, "quantity", 0)} @ {formatCurrency(num(trade, "price", 0))}</span>
                    <span style={{ marginLeft: "auto", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{formatRelative(text(trade, "trade_date", text(trade, "executed_at")))}</span>
                  </div>
                  {thesis && <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", lineHeight: 1.6 }}>{thesis}</div>}
                </div>
              );
            })}
          </div>
        )}
      </Panel>

      {paperSummary.length > 0 && (
        <Panel icon={Activity} title="Paper Trade Summary">
          <DataTable
            columns={[
              { key: "strategy", header: "Strategy", render: (r) => text(r, "strategy_name", text(r, "name")) },
              { key: "trades", header: "Trades", align: "right", render: (r) => num(r, "trade_count", 0) },
              { key: "pnl", header: "P&L", align: "right", render: (r) => <span style={{ color: num(r, "pnl", 0) >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{formatCurrency(num(r, "pnl", 0))}</span> },
              { key: "winrate", header: "Win Rate", align: "right", render: (r) => formatPercent(num(r, "win_rate", 0), { alreadyPercent: true }) },
            ]}
            rows={paperSummary}
            rowKey={(r, i) => String(text(r, "strategy_id", text(r, "id", i)))}
          />
        </Panel>
      )}
    </>
  );
}

/* ============================================================
 * TRADINGVIEW BRIDGE
 * ============================================================ */
function TradingViewBridgeView() {
  const { data, isLoading } = useTradingQuantRisk();
  const tasks = data?.tradingview_tasks ?? [];
  const templates = data?.tradingview_templates ?? [];

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={LineChart} title="TradingView Chart Actions">
          {isLoading ? <SkeletonGrid rows={3} /> : tasks.length === 0 ? (
            <Empty icon={LineChart} title="No chart tasks" description="Chart actions dispatched via the TradingView CDP bridge appear here." />
          ) : (
            <DataTable
              columns={[
                { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
                { key: "action", header: "Action", render: (r) => text(r, "action_type", text(r, "chart_action", "—")) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "complete")} /> },
                { key: "when", header: "When", render: (r) => formatRelative(text(r, "executed_at", text(r, "created_at"))) },
              ]}
              rows={tasks}
              rowKey={(r, i) => String(text(r, "task_id", text(r, "id", i)))}
            />
          )}
        </Panel>
        <Panel icon={LineChart} title="Pine Indicators / Templates">
          {isLoading ? <SkeletonGrid rows={3} /> : templates.length === 0 ? (
            <Empty icon={LineChart} title="No templates" description="Reusable Pine indicator templates and chart layouts." />
          ) : (
            <DataTable
              columns={[
                { key: "name", header: "Template", render: (r) => <strong>{text(r, "template_name", text(r, "name"))}</strong> },
                { key: "indicators", header: "Indicators", align: "right", render: (r) => num(r, "indicator_count", 0) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "ready")} /> },
              ]}
              rows={templates}
              rowKey={(r, i) => String(text(r, "template_id", text(r, "id", i)))}
            />
          )}
        </Panel>
      </div>
    </>
  );
}

/* ============================================================
 * ALPHA TRACKER — P&L attribution + edge decay
 * ============================================================ */
function AlphaView() {
  const { data, isLoading } = useTradingQuantRisk();
  const summary = data?.paper_trade_summary ?? [];

  // Heuristic equity curve from trade activity
  const equityCurve = React.useMemo(() => {
    const trades = data?.trade_activity ?? [];
    let cum = 0;
    return trades.slice(-60).map((t, i) => {
      cum += num(t, "pnl", 0);
      return { label: `T${i}`, value: cum, pnl: num(t, "pnl", 0) };
    });
  }, [data?.trade_activity]);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile>
          <Metric label="Realized P&L" value={formatCurrency(equityCurve.length ? equityCurve[equityCurve.length - 1].value : 0)}
            delta={equityCurve.length > 1 ? { value: formatCurrency(equityCurve[equityCurve.length - 1].value - equityCurve[0].value), direction: equityCurve[equityCurve.length - 1].value >= equityCurve[0].value ? "up" : "down" } : undefined} />
        </MetricTile>
        <MetricTile><Metric label="Win Rate" value={formatPercent(summary.length ? num(summary[0], "win_rate", 0) : 0, { alreadyPercent: true })} /></MetricTile>
        <MetricTile><Metric label="Trades" value={data?.trade_activity?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Strategies" value={summary.length} /></MetricTile>
      </div>

      <Panel icon={Target} title="Equity Curve (realized)">
        {isLoading ? <Skeleton style={{ height: 240 }} /> : equityCurve.length === 0 ? (
          <Empty icon={Target} title="No P&L data yet" description="Record trades to build your equity curve and track edge." />
        ) : (
          <AreaSeriesChart data={equityCurve} series={[{ key: "value", name: "Cumulative P&L" }]} xKey="label" height={260} yFormat={(v) => formatCompact(v)} />
        )}
      </Panel>

      <Panel icon={Target} title="Strategy Attribution">
        {isLoading ? <SkeletonGrid rows={3} /> : summary.length === 0 ? (
          <Empty icon={Target} title="No strategy attribution" />
        ) : (
          <BarSeriesChart
            data={summary.map((s, i) => ({ name: text(s, "strategy_name", `S${i}`), value: num(s, "pnl", 0) }))}
            bars={[{ key: "value", name: "P&L" }]}
            xKey="name"
            height={220}
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * SIGNALS & ALERTS
 * ============================================================ */
function SignalsView() {
  const { data, isLoading } = useTradingQuantRisk();
  const signals = data?.signals ?? [];
  const alerts = data?.alerts ?? [];
  const monitors = data?.paper_monitors ?? [];
  const drift = data?.drift_checks ?? [];

  return (
    <>
      <Panel icon={Zap} title="Live Signals">
        {isLoading ? <SkeletonGrid rows={4} /> : signals.length === 0 ? (
          <Empty icon={Zap} title="No live signals" description="Signals from active paper monitors and strategy triggers appear here." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "type", header: "Signal", render: (r) => text(r, "signal_type", text(r, "name", "signal")) },
              { key: "direction", header: "Direction", render: (r) => <StatusPill status={text(r, "direction", text(r, "side", "neutral"))} /> },
              { key: "strategy", header: "Strategy", render: (r) => text(r, "strategy_name", "—") },
              { key: "strength", header: "Strength", align: "right", render: (r) => num(r, "strength", num(r, "confidence", 0)).toFixed(2) },
              { key: "when", header: "When", render: (r) => formatRelative(text(r, "generated_at", text(r, "created_at"))) },
            ]}
            rows={signals}
            rowKey={(r, i) => String(text(r, "signal_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={AlertTriangle} title="Alerts">
          {alerts.length === 0 ? <Empty icon={AlertTriangle} title="No active alerts" /> : (
            <DataTable
              columns={[
                { key: "alert", header: "Alert", render: (r) => text(r, "alert_text", text(r, "message")) },
                { key: "severity", header: "Severity", render: (r) => <StatusPill status={text(r, "severity", "warn")} /> },
              ]}
              rows={alerts}
              rowKey={(r, i) => String(text(r, "alert_id", text(r, "id", i)))}
            />
          )}
        </Panel>
        <Panel icon={Activity} title="Paper Monitors + Drift">
          {monitors.length === 0 && drift.length === 0 ? <Empty icon={Activity} title="No active monitors" /> : (
            <DataTable
              columns={[
                { key: "strategy", header: "Strategy", render: (r) => text(r, "strategy_name", text(r, "name")) },
                { key: "heartbeat", header: "Heartbeat", render: (r) => formatRelative(text(r, "last_heartbeat_at", text(r, "updated_at"))) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "active")} /> },
              ]}
              rows={[...monitors, ...drift]}
              rowKey={(r, i) => String(text(r, "monitor_id", text(r, "id", i)))}
            />
          )}
        </Panel>
      </div>
    </>
  );
}

/* ============================================================
 * EXECUTION SAFETY — kill-switch, gates, limited-live
 * ============================================================ */
function ExecutionView() {
  const { data, isLoading } = useTradingQuantRisk();
  const controls = data?.execution_control ?? [];
  const killSwitch = controls.find((r) => String(text(r, "control_key", text(r, "kind"))).includes("kill_switch"));
  const armed = killSwitch && String(text(killSwitch, "status", text(killSwitch, "state"))).toLowerCase().includes("armed");
  const limitedLive = data?.limited_live_requests ?? [];
  const orderIntents = data?.order_intents ?? [];

  return (
    <>
      {/* Kill-switch — prominent */}
      <Panel variant={armed ? "risk" : "default"} icon={ShieldCheck} title="Global Kill-Switch"
        actions={armed ? <Badge tone="risk" dot pulse>ARMED</Badge> : <Badge tone="ok" dot>SAFE</Badge>}
      >
        <div style={{ padding: "var(--space-4)" }}>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-3)" }}>
            {armed
              ? "🛑 Kill-switch is ARMED. All automated trading is halted. No new orders will be placed until you disengage it."
              : "Kill-switch is safe. Automated trading systems (when enabled) can operate within approved limits."}
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Engaging the kill-switch requires explicit confirmation and is audit-logged. Disengaging requires governance review.
          </div>
        </div>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={ShieldCheck} title="Limited-Live Requests">
          {isLoading ? <SkeletonGrid rows={3} /> : limitedLive.length === 0 ? (
            <Empty icon={ShieldCheck} title="No limited-live requests" description="Requests to enable limited live trading (paper → small live) appear here." />
          ) : (
            <DataTable
              columns={[
                { key: "strategy", header: "Strategy", render: (r) => text(r, "strategy_name", text(r, "name")) },
                { key: "size", header: "Size", align: "right", render: (r) => formatCurrency(num(r, "max_notional", 0)) },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "pending")} /> },
              ]}
              rows={limitedLive}
              rowKey={(r, i) => String(text(r, "request_id", text(r, "id", i)))}
            />
          )}
        </Panel>
        <Panel icon={ShieldCheck} title="Order Intents">
          {isLoading ? <SkeletonGrid rows={3} /> : orderIntents.length === 0 ? (
            <Empty icon={ShieldCheck} title="No order intents" description="Pre-execution order intents awaiting risk evaluation." />
          ) : (
            <DataTable
              columns={[
                { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
                { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "quantity", 0) },
                { key: "gate", header: "Gate", render: (r) => <StatusPill status={text(r, "gate_status", "review")} /> },
              ]}
              rows={orderIntents}
              rowKey={(r, i) => String(text(r, "intent_id", text(r, "id", i)))}
            />
          )}
        </Panel>
      </div>
    </>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
