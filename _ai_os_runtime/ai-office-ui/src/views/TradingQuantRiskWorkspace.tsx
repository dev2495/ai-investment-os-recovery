import {
  Activity,
  BarChart3,
  Beaker,
  ClipboardPlus,
  Gauge,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Workflow
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createTradingViewTask,
  engageGlobalKillSwitch,
  recordManualTrade,
  recordPaperTrade,
  refreshPortfolioRiskEvents,
  runModelValidationSweep,
  runStrategyQuantAnalytics,
  type LiveRow
} from "../api/live";
import { fetchTradingQuantRiskSnapshot, type TradingQuantRiskSnapshot } from "../api/tradingQuantRisk";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";
type Mode = "trading" | "quant" | "risk";

interface Props { mode: Mode; onStatusChange: (status: ConnectionStatus) => void; }

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (typeof raw === "object") {
    if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
    return Object.entries(raw).map(([label, detail]) => `${label.replace(/_/g, " ")}: ${String(detail)}`).join(" · ") || fallback;
  }
  return String(raw);
}

function date(raw: unknown): string {
  if (!raw) return "not recorded";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function amount(raw: unknown): string {
  const numeric = Number(raw ?? 0);
  if (!Number.isFinite(numeric)) return "-";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(numeric);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["active", "allowed", "approved", "complete", "completed", "healthy", "ok", "passed", "ready", "locked"].includes(normalized)) return "active";
  if (["blocked", "breach", "critical", "error", "failed", "killed", "rejected", "stale"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>;
}

function Empty({ children }: { children: ReactNode }) { return <div className="empty-state">{children}</div>; }

export default function TradingQuantRiskWorkspace({ mode, onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<TradingQuantRiskSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionBusy, setActionBusy] = useState("");
  const [chart, setChart] = useState({ symbol: "", timeframe: "1D", instruction: "Open chart and capture a decision-ready screenshot" });
  const [trade, setTrade] = useState({ mode: "manual", symbol: "", side: "buy", quantity: "", price: "", strategy: "", thesis: "" });

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchTradingQuantRiskSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Trading, Quant, and Risk API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:trading-quant-risk-refresh", handleRefresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("aios:trading-quant-risk-refresh", handleRefresh);
    };
  }, [refresh]);

  const execution = snapshot?.execution_control[0];
  const blockedStrategies = snapshot?.promotion_board.filter((row) => value(row, "broker_order_allowed", "false") !== "true").length ?? 0;
  const riskBreaches = snapshot?.risk_limits.filter((row) => value(row, "check_status", "") === "breach").length ?? 0;
  const warnings = snapshot?.risk_limits.filter((row) => value(row, "check_status", "") === "warning").length ?? 0;
  const realizedPaperPnl = useMemo(() => snapshot?.paper_trade_summary.reduce((sum, row) => sum + Number(row.realized_pnl ?? 0), 0) ?? 0, [snapshot]);

  const runSafeAction = async (key: string, action: () => Promise<unknown>, success: string) => {
    setActionBusy(key); setError(""); setNotice("");
    try { await action(); setNotice(success); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : `${key} failed`); }
    finally { setActionBusy(""); }
  };

  const submitChart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runSafeAction("chart", () => createTradingViewTask({
      task_title: `TradingView review: ${chart.symbol} ${chart.timeframe}`,
      task_type: "chart_review", requested_by: "Devarsh", owner_agent: "Trading Desk Agent",
      priority: "medium", symbols: [chart.symbol.toUpperCase()], exchange: "NSE",
      timeframe: chart.timeframe, instruction: chart.instruction,
      source_ref: "trading_desk_scoped_workspace", evidence: [{ source: "Trading Desk" }]
    }), "TradingView task queued for the audited controller.");
    setChart((current) => ({ ...current, symbol: "" }));
  };

  const submitTrade = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const action = trade.mode === "paper" ? recordPaperTrade : recordManualTrade;
    await runSafeAction("trade", () => action({
      actor: "Devarsh", symbol: trade.symbol.toUpperCase(), side: trade.side,
      quantity: trade.quantity || undefined, price: trade.price || undefined,
      strategy_key: trade.strategy || undefined, thesis: trade.thesis || undefined,
      exchange: "NSE", instrument_type: "equity"
    }), `${trade.mode === "paper" ? "Paper" : "Manual"} trade journal entry recorded; no broker order was sent.`);
    setTrade((current) => ({ ...current, symbol: "", quantity: "", price: "", thesis: "" }));
  };

  const metricLabel = mode === "quant" ? "Quant Candidates" : mode === "trading" ? "Signals" : "Risk Breaches";
  const metricValue = mode === "quant" ? snapshot?.quant_lab.length ?? 0 : mode === "trading" ? snapshot?.signals.length ?? 0 : riskBreaches;

  return <div className="trading-quant-risk-workspace">
    <div className="workspace-filter-bar"><div><span>{mode === "quant" ? "Validation and allocation" : mode === "trading" ? "Signals and journal" : "Limits and execution safety"}</span><button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button"><RefreshCw size={14}/>{status === "loading" ? "Checking" : "Refresh"}</button></div></div>
    <section className="metric-grid" aria-label="Trading Quant Risk metrics">
      <div className="metric-tile"><span>Scoped API</span><strong>{status === "online" ? "Online" : status}</strong><p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p></div>
      <div className="metric-tile"><span>{metricLabel}</span><strong>{metricValue}</strong><p className="tone-neutral">warehouse state</p></div>
      <div className="metric-tile"><span>Broker-Gated</span><strong>{blockedStrategies}</strong><p className="tone-good">strategies blocked from orders</p></div>
      <div className="metric-tile"><span>{mode === "risk" ? "Warnings" : "Paper P&L"}</span><strong>{mode === "risk" ? warnings : amount(realizedPaperPnl)}</strong><p className="tone-neutral">review required</p></div>
      <div className="metric-tile"><span>Execution</span><strong>{value(execution, "global_execution_locked", "true") === "true" ? "Locked" : "Review"}</strong><p className="tone-good">broker writes disabled</p></div>
    </section>
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status} />
    {error ? <div className="error-strip">{error}</div> : null}{notice ? <div className="success-strip">{notice}</div> : null}

    {mode === "quant" ? <section className="dashboard-grid">
      <Panel className="span-12" icon={<Beaker size={17}/>} title="Quant Controls" action={<div className="panel-action-group"><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={() => void runSafeAction("validation", () => runModelValidationSweep({ actor: "Quant Research Lead", limit: 50 }), "Model-validation sweep completed without execution authority.")} type="button">{actionBusy === "validation" ? "Running" : "Validate models"}</button><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={() => void runSafeAction("analytics", () => runStrategyQuantAnalytics({ actor: "Quant Research Lead", limit: 50 }), "Quant analytics completed without execution authority.")} type="button">{actionBusy === "analytics" ? "Running" : "Run analytics"}</button></div>}><div className="quant-control-strip"><span>{snapshot?.model_validation.length ?? 0} validation rows</span><span>{snapshot?.promotion_board.length ?? 0} promotion rows</span><span>{snapshot?.strategy_committee.length ?? 0} committee reviews</span></div></Panel>
      <Panel className="span-7" icon={<Gauge size={17}/>} title="Quant Lab" action={<span>{snapshot?.quant_lab.length ?? 0} strategies</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.quant_lab.map((row) => <article className="source-check-row" key={value(row,"strategy_id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"timeframe")} · {value(row,"recommended_action")}</p></div><StatusPill status={value(row,"validation_status","review")}/><span>ruin {value(row,"ruin_probability","-")}</span><time>{date(row.updated_at)}</time></article>)}</div></Panel>
      <Panel className="span-5" icon={<ShieldCheck size={17}/>} title="Model Validation"><div className="source-check-list scoped-scroll-list">{snapshot?.model_validation.map((row) => <article className="source-check-row" key={value(row,"strategy_id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"validation_gate_reason")}</p></div><StatusPill status={value(row,"validation_gate_status","review")}/><span>overfit {value(row,"overfit_risk","-")}</span><time>{date(row.updated_at)}</time></article>)}</div></Panel>
      <Panel className="span-7" icon={<Workflow size={17}/>} title="Promotion Board"><div className="source-check-list scoped-scroll-list">{snapshot?.promotion_board.map((row) => <article className="source-check-row" key={value(row,"strategy_id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"promotion_stage")} · {value(row,"next_required_action")}</p></div><StatusPill status={value(row,"committee_decision_status","review")}/><span>{value(row,"broker_order_allowed","false") === "true" ? "orders allowed" : "orders blocked"}</span><time>{date(row.updated_at)}</time></article>)}</div></Panel>
      <Panel className="span-5" icon={<Activity size={17}/>} title="Retirement And Drift"><div className="source-check-list scoped-scroll-list">{snapshot?.retirement_queue.map((row) => <article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"trigger_reasons")}</p></div><StatusPill status={value(row,"severity","review")}/><span>{value(row,"recommended_action")}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.retirement_queue.length ? <Empty>No retirement rows.</Empty> : null}</div></Panel>
    </section> : null}

    {mode === "trading" ? <section className="dashboard-grid">
      <Panel className="span-5" icon={<BarChart3 size={17}/>} title="TradingView Request"><form className="operator-form" onSubmit={submitChart}><label><span>Symbol</span><input required value={chart.symbol} onChange={(event)=>setChart({...chart,symbol:event.target.value.toUpperCase()})}/></label><label><span>Timeframe</span><select value={chart.timeframe} onChange={(event)=>setChart({...chart,timeframe:event.target.value})}><option>5m</option><option>15m</option><option>1H</option><option>1D</option><option>1W</option></select></label><label className="span-form"><span>Instruction</span><input required value={chart.instruction} onChange={(event)=>setChart({...chart,instruction:event.target.value})}/></label><button className="primary-button span-form" disabled={Boolean(actionBusy)} type="submit"><BarChart3 size={15}/>{actionBusy === "chart" ? "Queueing" : "Queue chart task"}</button></form></Panel>
      <Panel className="span-7" icon={<Workflow size={17}/>} title="Advanced Chart Templates" action={<span>{snapshot?.tradingview_templates.length ?? 0} templates</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.tradingview_templates.map((row)=><article className="source-check-row" key={value(row,"template_key")}><div><strong>{value(row,"template_name")}</strong><p>{value(row,"description")} · {value(row,"default_chart_layout")}</p></div><StatusPill status={value(row,"status","gated")}/><span>{value(row,"category")}</span><time>{value(row,"approval_required","false") === "true" ? "approval" : "read only"}</time></article>)}{!snapshot?.tradingview_templates.length?<Empty>No TradingView templates registered.</Empty>:null}</div></Panel>
      <Panel className="span-7" icon={<Activity size={17}/>} title="Live Signals" action={<span>{snapshot?.signals.length ?? 0} signals</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.signals.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"strategy")}</strong><p>{value(row,"exchange")} · confidence {value(row,"confidence","-")}</p></div><StatusPill status={value(row,"action","watch")}/><span>{amount(row.price)}</span><time>{date(row.ts)}</time></article>)}{!snapshot?.signals.length?<Empty>No live signal rows.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<ClipboardPlus size={17}/>} title="Trade Journal"><form className="operator-form" onSubmit={submitTrade}><label><span>Record type</span><select value={trade.mode} onChange={(event)=>setTrade({...trade,mode:event.target.value})}><option value="manual">Manual trade</option><option value="paper">Paper trade</option></select></label><label><span>Symbol</span><input required value={trade.symbol} onChange={(event)=>setTrade({...trade,symbol:event.target.value.toUpperCase()})}/></label><label><span>Side</span><select value={trade.side} onChange={(event)=>setTrade({...trade,side:event.target.value})}><option value="buy">Buy</option><option value="sell">Sell</option><option value="long">Long</option><option value="short">Short</option><option value="exit">Exit</option></select></label><label><span>Quantity</span><input inputMode="decimal" value={trade.quantity} onChange={(event)=>setTrade({...trade,quantity:event.target.value})}/></label><label><span>Price</span><input inputMode="decimal" value={trade.price} onChange={(event)=>setTrade({...trade,price:event.target.value})}/></label><label><span>Strategy</span><input value={trade.strategy} onChange={(event)=>setTrade({...trade,strategy:event.target.value})}/></label><label className="span-form"><span>Thesis</span><input value={trade.thesis} onChange={(event)=>setTrade({...trade,thesis:event.target.value})}/></label><button className="primary-button span-form" disabled={Boolean(actionBusy)} type="submit"><ClipboardPlus size={15}/>{actionBusy === "trade" ? "Recording" : "Record journal entry"}</button><p className="form-guard span-form">Journal only. This route cannot submit a broker order.</p></form></Panel>
      <Panel className="span-7" icon={<BarChart3 size={17}/>} title="TradingView Controller" action={<span>{snapshot?.tradingview_cdp.available ? "CDP online" : "CDP offline"}</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.tradingview_tasks.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"task_title")}</strong><p>{value(row,"symbols")} · {value(row,"timeframe")} · {value(row,"result_summary")}</p></div><StatusPill status={value(row,"status","queued")}/><span>#{value(row,"id")}</span><time>{date(row.updated_at)}</time></article>)}</div></Panel>
      <Panel className="span-7" icon={<Workflow size={17}/>} title="Trade Activity"><div className="source-check-list scoped-scroll-list">{snapshot?.trade_activity.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"side")}</strong><p>{value(row,"execution_mode")} · {value(row,"strategy_key")}</p></div><StatusPill status={value(row,"status","recorded")}/><span>{value(row,"quantity")} @ {amount(row.price)}</span><time>{date(row.trade_ts)}</time></article>)}{!snapshot?.trade_activity.length?<Empty>No journal trades recorded.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<Beaker size={17}/>} title="Paper Monitor"><div className="source-check-list scoped-scroll-list">{snapshot?.paper_monitors.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"heartbeat_status")} · {value(row,"total_events","0")} events</p></div><StatusPill status={value(row,"status","idle")}/><span>{value(row,"live_execution_allowed","false") === "true" ? "live" : "paper"}</span><time>{date(row.last_heartbeat_at)}</time></article>)}{!snapshot?.paper_monitors.length?<Empty>No active paper-monitor session.</Empty>:null}</div></Panel>
    </section> : null}

    {mode === "risk" ? <section className="dashboard-grid">
      <Panel className="span-12" icon={<ShieldAlert size={17}/>} title="Risk Controls" action={<div className="panel-action-group"><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={()=>void runSafeAction("risk-refresh",()=>refreshPortfolioRiskEvents({actor:"Chief Risk Officer"}),"Portfolio risk events refreshed.")} type="button">{actionBusy === "risk-refresh" ? "Running" : "Refresh checks"}</button><button className="danger-button" disabled={Boolean(actionBusy)} onClick={()=>{if(window.confirm("Engage the global kill switch and keep broker writes locked?")) void runSafeAction("kill",()=>engageGlobalKillSwitch({actor:"Chief Risk Officer",trigger_source:"risk_center",trigger_reason:"Manual emergency stop from Risk Center"}),"Global kill switch engaged; broker writes remain locked.");}} type="button"><Siren size={14}/>{actionBusy === "kill" ? "Engaging" : "Global kill switch"}</button></div>}><div className="quant-control-strip"><span>{riskBreaches} breaches</span><span>{warnings} warnings</span><span>{value(execution,"broker_execution_policy","blocked")}</span></div></Panel>
      <Panel className="span-5" icon={<Gauge size={17}/>} title="Risk Summary"><div className="portfolio-intelligence-list scoped-scroll-list">{snapshot?.risk_summary.map((row)=><article className="portfolio-intelligence-row" key={value(row,"metric")}><div><strong>{value(row,"metric").replace(/_/g," ")}</strong><p>{value(row,"interpretation")}</p></div><span>{value(row,"value")}</span></article>)}</div></Panel>
      <Panel className="span-7" icon={<ShieldCheck size={17}/>} title="Limit Checks" action={<span>{snapshot?.risk_limits.length ?? 0} checks</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.risk_limits.map((row)=><article className="source-check-row" key={value(row,"check_key")}><div><strong>{value(row,"limit_name")} · {value(row,"symbol",value(row,"book_name"))}</strong><p>{value(row,"check_message")} · {value(row,"recommended_action")}</p></div><StatusPill status={value(row,"check_status","review")}/><span>{value(row,"utilization_pct","-")}%</span><time>{date(row.latest_as_of)}</time></article>)}</div></Panel>
      <Panel className="span-6" icon={<Siren size={17}/>} title="Limited-Live Requests"><div className="source-check-list scoped-scroll-list">{snapshot?.limited_live_requests.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")} · {value(row,"symbol")}</strong><p>{value(row,"rationale")}</p></div><StatusPill status={value(row,"request_status","review")}/><span>{amount(row.max_notional)}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.limited_live_requests.length?<Empty>No limited-live requests.</Empty>:null}</div></Panel>
      <Panel className="span-6" icon={<ClipboardPlus size={17}/>} title="Order Intents"><div className="source-check-list scoped-scroll-list">{snapshot?.order_intents.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"side")}</strong><p>{value(row,"strategy_name")} · {value(row,"rationale")}</p></div><StatusPill status={value(row,"gate_status","blocked")}/><span>{amount(row.notional)}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.order_intents.length?<Empty>No order intents.</Empty>:null}</div></Panel>
      <Panel className="span-12" icon={<Activity size={17}/>} title="Drift Checks"><div className="source-check-list scoped-scroll-list">{snapshot?.drift_checks.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")} · {value(row,"instance_name")}</strong><p>{value(row,"findings")}</p></div><StatusPill status={value(row,"drift_level","review")}/><span>score {value(row,"drift_score","-")}</span><time>{date(row.checked_at)}</time></article>)}{!snapshot?.drift_checks.length?<Empty>No drift checks.</Empty>:null}</div></Panel>
    </section> : null}
  </div>;
}
