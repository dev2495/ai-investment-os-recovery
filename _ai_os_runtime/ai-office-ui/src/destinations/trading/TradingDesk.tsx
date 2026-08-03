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
import { useTradingQuantRisk, useTradingViewDesktopStatus } from "../../data/queries";
import { useOpenTradingViewDesktop, useRecordManualTrade, useRecordPaperTrade, useRunTradingViewTemplate } from "../../data/actions";
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
  const [showTicket, setShowTicket] = React.useState(false);
  const [showPaper, setShowPaper] = React.useState(false);

  return (
    <>
      <Panel icon={Notebook} title="Trade Journal" actions={<>
          <Button size="sm" variant="ghost" icon={Notebook} onClick={() => setShowPaper(true)}>Paper trade</Button>
          <Button size="sm" variant="primary" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>
        </>}>
        {isLoading ? <SkeletonGrid rows={4} /> : trades.length === 0 ? (
          <Empty icon={Notebook} title="No journal entries" description="Trades recorded with thesis text appear here as journal entries for later mining." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
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

      <TradeTicketDrawer open={showTicket} onClose={() => setShowTicket(false)} paper={false} />
      <TradeTicketDrawer open={showPaper} onClose={() => setShowPaper(false)} paper />
    </>
  );
}

/* ============================================================
 * TRADINGVIEW BRIDGE
 * ============================================================ */
function TradingViewBridgeView() {
  const { data, isLoading } = useTradingQuantRisk();
  const desktop = useTradingViewDesktopStatus();
  const openDesktop = useOpenTradingViewDesktop();
  const runTemplate = useRunTradingViewTemplate();
  const pushToast = useUIStore((state) => state.pushToast);
  const tasks = data?.tradingview_tasks ?? [];
  const templates = data?.tradingview_templates ?? [];
  const [symbol, setSymbol] = React.useState("NIFTY");
  const [exchange, setExchange] = React.useState("NSE");
  const [timeframe, setTimeframe] = React.useState("D");
  const [templateKey, setTemplateKey] = React.useState("");
  const [lastResult, setLastResult] = React.useState<LiveRow | null>(null);
  const [templateValues, setTemplateValues] = React.useState<Record<string, string>>({
    benchmark: "NSE:NIFTY",
    leg_a: "",
    leg_b: "",
    hedge_ratio: "1",
    expiry: "",
    strike: "",
    call_symbol: "",
    put_symbol: "",
    indicators: "VWAP, Volume, RSI, MACD, ATR, Supertrend",
    fields: "TOTAL_REVENUE, NET_INCOME, OPERATING_MARGIN, RETURN_ON_INVESTED_CAPITAL, TOTAL_DEBT, PRICE_EARNINGS, PRICE_BOOK",
    equity_index: "NSE:NIFTY",
    volatility_index: "NSE:INDIAVIX",
    bond_yield: "TVC:IN10Y",
    currency: "FX_IDC:USDINR",
    condition: "",
  });

  React.useEffect(() => {
    if (!templateKey && templates.length) {
      setTemplateKey(text(templates[0], "template_key", text(templates[0], "key")));
    }
  }, [templateKey, templates]);

  const desktopStatus = desktop.data ?? {};
  const desktopInstalled = Boolean(desktopStatus.installed);
  const desktopMode = text(desktopStatus, "interaction_mode", "unknown");
  const desktopReady = desktopInstalled && (desktopMode !== "clipboard_menu" || Boolean(desktopStatus.automation_permission));
  const desktopRunning = Boolean(desktopStatus.running);
  const busy = openDesktop.isPending || runTemplate.isPending;

  function updateTemplateValue(key: string, value: string) {
    setTemplateValues((current) => ({ ...current, [key]: value }));
  }

  function csvValues(key: string) {
    return (templateValues[key] ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
  }

  function templateParametersFor(key: string): Record<string, unknown> {
    if (key === "relative_strength_ratio_chart") {
      return { benchmark: templateValues.benchmark.trim() };
    }
    if (key === "spread_pair_formula_chart") {
      return {
        leg_a: templateValues.leg_a.trim() || symbol.trim(),
        leg_b: templateValues.leg_b.trim(),
        hedge_ratio: templateValues.hedge_ratio.trim(),
      };
    }
    if (key === "open_option_straddle_layout" || key === "option_straddle_four_pane") {
      return {
        underlying: symbol.trim(),
        expiry: templateValues.expiry.trim(),
        strike: templateValues.strike.trim(),
        call_symbol: templateValues.call_symbol.trim(),
        put_symbol: templateValues.put_symbol.trim(),
      };
    }
    if (key === "technical_indicator_stack") {
      return { indicators: csvValues("indicators") };
    }
    if (key === "fundamental_ratio_dashboard") {
      return { fields: csvValues("fields"), filing_cross_check_required: true };
    }
    if (key === "market_regime_four_pane") {
      return {
        equity_index: templateValues.equity_index.trim() || symbol.trim(),
        volatility_index: templateValues.volatility_index.trim(),
        bond_yield: templateValues.bond_yield.trim(),
        currency: templateValues.currency.trim(),
      };
    }
    if (key === "create_alert_request") {
      return { condition: templateValues.condition.trim() };
    }
    return {};
  }

  function templateParameterFields() {
    const gridStyle: React.CSSProperties = {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
      gap: "var(--space-3)",
      marginTop: "var(--space-3)",
    };
    const input = (key: string, label: string, placeholder: string) => (
      <Field key={key} label={label}>
        <TextInput
          value={templateValues[key] ?? ""}
          onChange={(event) => updateTemplateValue(key, event.target.value)}
          placeholder={placeholder}
        />
      </Field>
    );

    if (templateKey === "relative_strength_ratio_chart") {
      return <div style={gridStyle}>{input("benchmark", "Benchmark", "NSE:NIFTY")}</div>;
    }
    if (templateKey === "spread_pair_formula_chart") {
      return <div style={gridStyle}>{input("leg_a", "Leg A", "NSE:RELIANCE")}{input("leg_b", "Leg B", "NSE:NIFTY")}{input("hedge_ratio", "Hedge Ratio", "1")}</div>;
    }
    if (templateKey === "open_option_straddle_layout" || templateKey === "option_straddle_four_pane") {
      return <div style={gridStyle}>{input("expiry", "Expiry", "2026-08-27")}{input("strike", "Strike", "25000")}{input("call_symbol", "Call Symbol", "NFO:NIFTY...")}{input("put_symbol", "Put Symbol", "NFO:NIFTY...")}</div>;
    }
    if (templateKey === "technical_indicator_stack") {
      return <div style={gridStyle}>{input("indicators", "Indicators", "VWAP, Volume, RSI")}</div>;
    }
    if (templateKey === "fundamental_ratio_dashboard") {
      return <div style={gridStyle}>{input("fields", "Financial Fields", "TOTAL_REVENUE, NET_INCOME")}</div>;
    }
    if (templateKey === "market_regime_four_pane") {
      return <div style={gridStyle}>{input("equity_index", "Equity Index", "NSE:NIFTY")}{input("volatility_index", "Volatility", "NSE:INDIAVIX")}{input("bond_yield", "Bond Yield", "TVC:IN10Y")}{input("currency", "Currency", "FX_IDC:USDINR")}</div>;
    }
    if (templateKey === "create_alert_request") {
      return <div style={gridStyle}>{input("condition", "Alert Condition", "Crossing or indicator condition")}</div>;
    }
    return null;
  }

  function notify(title: string, tone: "ok" | "risk" | "warn", message?: string) {
    pushToast({ title, tone, message, duration: 6000 });
  }

  function directOpen() {
    if (!symbol.trim()) {
      notify("Symbol required", "warn");
      return;
    }
    openDesktop.mutate(
      { symbol: symbol.trim().toUpperCase(), exchange, timeframe, actor: "Devarsh" },
      {
        onSuccess: (result) => {
          setLastResult(result);
          const status = text(result, "status");
          const handedOff = status === "opened" || status === "handoff_requested";
          notify(
            handedOff ? "Sent to TradingView Desktop" : "Desktop action needs attention",
            handedOff ? "ok" : "warn",
            handedOff ? `${exchange}:${symbol.toUpperCase()} | ${timeframe}` : text(result, "fallback", text(result, "next_action"))
          );
        },
        onError: (error) => notify("TradingView Desktop action failed", "risk", error.message),
      }
    );
  }

  function executeTemplate() {
    if (!templateKey || !symbol.trim()) {
      notify("Template and symbol required", "warn");
      return;
    }
    runTemplate.mutate(
      {
        template_key: templateKey,
        symbol: symbol.trim().toUpperCase(),
        exchange,
        timeframe,
        parameters: templateParametersFor(templateKey),
        actor: "Devarsh",
      },
      {
        onSuccess: (result) => {
          setLastResult(result);
          const status = text(result, "status", text(result, "approval_status", "queued"));
          const approval = status.includes("approval") || status.includes("pending");
          notify(approval ? "Template queued for approval" : "Template dispatched", approval ? "warn" : "ok", templateKey);
        },
        onError: (error) => notify("Template dispatch failed", "risk", error.message),
      }
    );
  }

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile tone={desktopRunning ? "ok" : desktopInstalled ? "warn" : "risk"}><Metric label="Desktop App" value={desktopRunning ? "Running" : desktopInstalled ? "Installed" : "Unavailable"} sub={text(desktopStatus, "version", "not detected")} /></MetricTile>
        <MetricTile tone={desktopReady ? "ok" : desktopInstalled ? "warn" : "risk"}><Metric label="Native Handoff" value={desktopReady ? "Ready" : desktopInstalled ? "Manual" : "Unavailable"} sub={desktopMode.replace(/_/g, " ")} /></MetricTile>
        <MetricTile tone={desktopInstalled ? "ok" : "warn"}><Metric label="Desktop Workspace" value="User Managed" sub="existing signed-in app session" /></MetricTile>
        <MetricTile><Metric label="Broker Writes" value="Locked" sub="visual analysis only" /></MetricTile>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.25fr) minmax(300px, .75fr)", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={LineChart} title="Chart Workspace" actions={<Button size="sm" variant="ghost" icon={Activity} disabled={desktop.isFetching} onClick={() => desktop.refetch()}>Refresh</Button>}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(150px, 1fr) 120px 120px", gap: "var(--space-3)" }}>
            <Field label="Symbol"><TextInput value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="RELIANCE" /></Field>
            <Field label="Exchange"><Select value={exchange} onChange={(event) => setExchange(event.target.value)}><option>NSE</option><option>BSE</option><option>NFO</option><option>MCX</option><option>BINANCE</option></Select></Field>
            <Field label="Timeframe"><Select value={timeframe} onChange={(event) => setTimeframe(event.target.value)}><option value="5">5 min</option><option value="15">15 min</option><option value="60">1 hour</option><option value="D">Daily</option><option value="W">Weekly</option><option value="M">Monthly</option></Select></Field>
          </div>
          {!desktopReady && text(desktopStatus, "next_action") && (
            <div className="aios-inline-alert aios-inline-alert--warn" style={{ marginTop: "var(--space-3)" }}>
              <AlertTriangle size={16} />
              <span>{text(desktopStatus, "next_action")}</span>
            </div>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginTop: "var(--space-4)" }}>
            <Button variant="primary" icon={Play} disabled={busy || !desktopInstalled} onClick={directOpen}>{desktopReady ? (desktopRunning ? "Open in App" : "Launch & Open") : "Prepare App Link"}</Button>
          </div>
        </Panel>

        <Panel icon={Target} title="Desktop App Templates">
          <Field label="Template">
            <Select value={templateKey} onChange={(event) => setTemplateKey(event.target.value)}>
              {templates.map((row) => {
                const key = text(row, "template_key", text(row, "key"));
                return <option key={key} value={key}>{text(row, "template_name", text(row, "name", key))}</option>;
              })}
            </Select>
          </Field>
          {templateParameterFields()}
          <Button style={{ width: "100%", marginTop: "var(--space-3)" }} icon={Play} disabled={busy || !templateKey} onClick={executeTemplate}>Run Template</Button>
          {lastResult && (
            <div style={{ marginTop: "var(--space-4)" }}>
              <KeyValue label="Status" value={text(lastResult, "status", "recorded")} />
              <KeyValue label="Target" value={text(lastResult, "target_url", `${exchange}:${symbol}`)} />
            </div>
          )}
        </Panel>
      </div>

      <Panel icon={LineChart} title="TradingView Activity">
        {isLoading ? <SkeletonGrid rows={4} /> : tasks.length === 0 ? (
          <Empty icon={LineChart} title="No chart tasks" description="Open a chart or desktop template to create the first audited task." />
        ) : (
          <DataTable
            columns={[
              { key: "task", header: "Task", render: (row) => <strong>{text(row, "task_title", text(row, "title"))}</strong> },
              { key: "symbols", header: "Symbols", render: (row) => Array.isArray(row.symbols) ? row.symbols.join(", ") : text(row, "symbol", "-") },
              { key: "type", header: "Mode", render: (row) => text(row, "task_type", "chart action").replace(/_/g, " ") },
              { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "queued")} /> },
              { key: "when", header: "Updated", render: (row) => formatRelative(text(row, "updated_at", text(row, "created_at"))) },
            ]}
            rows={tasks}
            rowKey={(row, index) => String(text(row, "task_id", text(row, "id", index)))}
          />
        )}
      </Panel>
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
