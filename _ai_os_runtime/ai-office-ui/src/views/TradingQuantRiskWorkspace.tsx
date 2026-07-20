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
  executeTradingViewTemplateAction,
  recordManualTrade,
  recordPaperTrade,
  refreshPortfolioRiskEvents,
  runInstitutionalPortfolioRisk,
  runModelValidationSweep,
  runStrategyQuantAnalytics,
  resolveTradingViewTemplateApproval,
  type LiveRow
} from "../api/live";
import { fetchTradingQuantRiskSnapshot, type TradingQuantRiskSnapshot } from "../api/tradingQuantRisk";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";
type Mode = "trading" | "quant" | "risk";

interface Props { mode: Mode; onStatusChange: (status: ConnectionStatus) => void; }

const deterministicTradingViewTemplates = new Set([
  "open_symbol_chart", "capture_chart_snapshot", "capture_symbol_watchlist",
  "relative_strength_ratio_chart", "spread_pair_formula_chart",
  "open_option_straddle_layout", "option_straddle_four_pane",
  "technical_indicator_stack", "fundamental_ratio_dashboard"
]);

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

function percent(raw: unknown, digits = 2): string {
  const numeric = Number(raw);
  if (!Number.isFinite(numeric)) return "-";
  return `${numeric.toFixed(digits)}%`;
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
  const [templateRequest, setTemplateRequest] = useState({
    templateKey: "relative_strength_ratio_chart", symbol: "", benchmark: "NSE:NIFTY",
    legA: "", legB: "", hedgeRatio: "1", underlying: "", expiry: "", strike: "",
    callSymbol: "", putSymbol: "", timeframe: "D",
    indicators: "VWAP, Supertrend, RSI, MACD, ATR",
    fundamentalFields: "TOTAL_REVENUE, NET_INCOME, OPERATING_MARGIN, RETURN_ON_INVESTED_CAPITAL, TOTAL_DEBT, PRICE_EARNINGS, PRICE_BOOK"
  });
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
  const institutionalRun = snapshot?.institutional_risk_run[0];
  const portfolioRisk = snapshot?.institutional_risk_metrics.find((row) => value(row, "scope_type") === "portfolio");
  const portfolioStress = snapshot?.institutional_stress.filter((row) => value(row, "scope_type") === "portfolio") ?? [];
  const portfolioFactors = snapshot?.institutional_factors.filter((row) => value(row, "scope_type") === "portfolio") ?? [];
  const portfolioLiquidity = snapshot?.institutional_liquidity.filter((row) => value(row, "scope_type") === "portfolio") ?? [];
  const unavailableLiquidity = portfolioLiquidity.filter((row) => value(row, "liquidity_bucket") === "unavailable").length;
  const blockedStrategies = snapshot?.promotion_board.filter((row) => value(row, "broker_order_allowed", "false") !== "true").length ?? 0;
  const riskBreaches = snapshot?.risk_limits.filter((row) => value(row, "check_status", "") === "breach").length ?? 0;
  const warnings = snapshot?.risk_limits.filter((row) => value(row, "check_status", "") === "warning").length ?? 0;
  const realizedPaperPnl = useMemo(() => snapshot?.paper_trade_summary.reduce((sum, row) => sum + Number(row.realized_pnl ?? 0), 0) ?? 0, [snapshot]);
  const pendingTemplateApprovals = useMemo(() => (snapshot?.tradingview_template_approvals ?? []).filter((row) => value(row, "status") === "pending"), [snapshot]);

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

  const submitTemplate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const symbol = templateRequest.symbol || templateRequest.legA || templateRequest.underlying;
    await runSafeAction("template", () => executeTradingViewTemplateAction({
      template_key: templateRequest.templateKey,
      actor: "Devarsh",
      requested_by: "Devarsh",
      symbol: symbol.toUpperCase(),
      symbols: symbol ? [symbol.toUpperCase()] : [],
      exchange: "NSE",
      timeframe: templateRequest.timeframe,
      source_ref: "trading_quant_risk_chart_workflow_builder",
      metadata: {
        benchmark: templateRequest.benchmark.toUpperCase(),
        leg_a: templateRequest.legA.toUpperCase(),
        leg_b: templateRequest.legB.toUpperCase(),
        hedge_ratio: templateRequest.hedgeRatio,
        underlying: templateRequest.underlying.toUpperCase(),
        expiry: templateRequest.expiry,
        strike: templateRequest.strike,
        call_symbol: templateRequest.callSymbol.toUpperCase(),
        put_symbol: templateRequest.putSymbol.toUpperCase()
        ,indicators: templateRequest.indicators.split(",").map((item) => item.trim()).filter(Boolean)
        ,fields: templateRequest.fundamentalFields.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean)
      }
    }), "TradingView workflow compiled. Deterministic actions were executed or queued for dedicated approval; no broker order was created.");
  };

  const resolveTemplate = (approvalId: string, decision: "approved" | "rejected") => runSafeAction(
    `template-${approvalId}`,
    () => resolveTradingViewTemplateApproval({ approval_id: approvalId, status: decision, decided_by: "Devarsh" }),
    decision === "approved" ? "Approved TradingView plan executed and evidence captured." : "TradingView plan rejected without changing chart state."
  );

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
      <Panel className="span-7" icon={<Workflow size={17}/>} title="Chart Workflow Builder" action={<span>{snapshot?.tradingview_templates.length ?? 0} templates</span>}><form className="operator-form" onSubmit={submitTemplate}><label className="span-form"><span>Workflow</span><select value={templateRequest.templateKey} onChange={(event)=>setTemplateRequest({...templateRequest,templateKey:event.target.value})}>{snapshot?.tradingview_templates.map((row)=>{const key=value(row,"template_key");return <option disabled={!deterministicTradingViewTemplates.has(key)} key={key} value={key}>{value(row,"template_name")} {!deterministicTradingViewTemplates.has(key)?"(manual capability pending)":""}</option>;})}</select></label><label><span>Primary symbol</span><input value={templateRequest.symbol} onChange={(event)=>setTemplateRequest({...templateRequest,symbol:event.target.value.toUpperCase()})}/></label><label><span>Timeframe</span><select value={templateRequest.timeframe} onChange={(event)=>setTemplateRequest({...templateRequest,timeframe:event.target.value})}><option value="5">5m</option><option value="15">15m</option><option value="60">1H</option><option value="D">1D</option><option value="W">1W</option></select></label>{templateRequest.templateKey==="relative_strength_ratio_chart"?<label className="span-form"><span>Benchmark or peer</span><input required value={templateRequest.benchmark} onChange={(event)=>setTemplateRequest({...templateRequest,benchmark:event.target.value.toUpperCase()})}/></label>:null}{templateRequest.templateKey==="spread_pair_formula_chart"?<><label><span>Leg A</span><input required value={templateRequest.legA} onChange={(event)=>setTemplateRequest({...templateRequest,legA:event.target.value.toUpperCase()})}/></label><label><span>Leg B</span><input required value={templateRequest.legB} onChange={(event)=>setTemplateRequest({...templateRequest,legB:event.target.value.toUpperCase()})}/></label><label className="span-form"><span>Hedge ratio</span><input inputMode="decimal" min="0.0001" required step="0.0001" type="number" value={templateRequest.hedgeRatio} onChange={(event)=>setTemplateRequest({...templateRequest,hedgeRatio:event.target.value})}/></label></>:null}{templateRequest.templateKey==="technical_indicator_stack"?<label className="span-form"><span>Approved built-in studies</span><input required value={templateRequest.indicators} onChange={(event)=>setTemplateRequest({...templateRequest,indicators:event.target.value})}/></label>:null}{templateRequest.templateKey==="fundamental_ratio_dashboard"?<label className="span-form"><span>Financial fields</span><textarea required rows={3} value={templateRequest.fundamentalFields} onChange={(event)=>setTemplateRequest({...templateRequest,fundamentalFields:event.target.value})}/></label>:null}{["open_option_straddle_layout","option_straddle_four_pane"].includes(templateRequest.templateKey)?<><label><span>Underlying</span><input required value={templateRequest.underlying} onChange={(event)=>setTemplateRequest({...templateRequest,underlying:event.target.value.toUpperCase()})}/></label><label><span>Expiry</span><input placeholder="2026-07-30" required value={templateRequest.expiry} onChange={(event)=>setTemplateRequest({...templateRequest,expiry:event.target.value})}/></label><label><span>Strike</span><input required value={templateRequest.strike} onChange={(event)=>setTemplateRequest({...templateRequest,strike:event.target.value})}/></label><label><span>Call symbol</span><input required value={templateRequest.callSymbol} onChange={(event)=>setTemplateRequest({...templateRequest,callSymbol:event.target.value.toUpperCase()})}/></label><label className="span-form"><span>Put symbol</span><input required value={templateRequest.putSymbol} onChange={(event)=>setTemplateRequest({...templateRequest,putSymbol:event.target.value.toUpperCase()})}/></label></>:null}<button className="primary-button span-form" disabled={Boolean(actionBusy)||!deterministicTradingViewTemplates.has(templateRequest.templateKey)} type="submit"><Workflow size={15}/>{actionBusy==="template"?"Compiling":"Compile and run / request approval"}</button><p className="form-guard span-form">Formula charts, approved built-in study stacks, and a four-chart option evidence board execute after validation and human approval. Interactive TradingView pane synchronization and account alerts remain human-controlled.</p></form></Panel>
      <Panel className="span-12" icon={<BarChart3 size={17}/>} title="Advanced Chart Templates" action={<span>{snapshot?.tradingview_templates.length ?? 0} registered</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.tradingview_templates.map((row)=>{const key=value(row,"template_key");return <article className="source-check-row" key={key}><div><strong>{value(row,"template_name")}</strong><p>{value(row,"description")} · {value(row,"risk_notes")}</p></div><StatusPill status={deterministicTradingViewTemplates.has(key)?value(row,"status","gated"):"partial"}/><span>{value(row,"category")}</span><time>{deterministicTradingViewTemplates.has(key)?(value(row,"approval_required","false") === "true" ? "approval then execute" : "deterministic capture"):"manual capability pending"}</time></article>;})}{!snapshot?.tradingview_templates.length?<Empty>No TradingView templates registered.</Empty>:null}</div></Panel>
      <Panel className="span-12" icon={<ShieldCheck size={17}/>} title="Chart Plan Approvals" action={<span>{pendingTemplateApprovals.length} pending</span>}><div className="source-check-list scoped-scroll-list">{pendingTemplateApprovals.map((row)=>{const requested=row.requested_action&&typeof row.requested_action==="object"&&!Array.isArray(row.requested_action)?row.requested_action as Record<string,unknown>:{};const plan=requested.compiled_plan&&typeof requested.compiled_plan==="object"&&!Array.isArray(requested.compiled_plan)?requested.compiled_plan as Record<string,unknown>:{};const ready=String(plan.execution_ready)==="true";return <article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"title")}</strong><p>{String(plan.fulfillment??"manual review")} · {String(plan.symbol_expression??value(row,"symbols"))}</p></div><StatusPill status={ready?"ready":"partial"}/><div className="panel-action-group"><button className="mini-action-button" disabled={Boolean(actionBusy)||!ready} onClick={()=>void resolveTemplate(value(row,"id"),"approved")} type="button">Approve and run</button><button className="danger-button" disabled={Boolean(actionBusy)} onClick={()=>void resolveTemplate(value(row,"id"),"rejected")} type="button">Reject</button></div></article>;})}{!pendingTemplateApprovals.length?<Empty>No TradingView chart plan awaits a decision.</Empty>:null}</div></Panel>
      <Panel className="span-7" icon={<BarChart3 size={17}/>} title="Options Surface" action={<span>{snapshot?.options_surface.length ?? 0} expiries</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.options_surface.map((row)=><article className="source-check-row" key={`${value(row,"provider")}-${value(row,"underlying")}-${value(row,"expiry")}`}><div><strong>{value(row,"underlying")} · {value(row,"expiry")}</strong><p>{value(row,"provider")} · spot {amount(row.spot_price)} · strikes {value(row,"min_strike")} to {value(row,"max_strike")}</p></div><StatusPill status="read only"/><span>{value(row,"contract_count","0")} contracts</span><time>{date(row.observed_at)}</time></article>)}{!snapshot?.options_surface.length?<Empty>No option-chain snapshot yet. Complete Zerodha API setup and daily interactive login, then run the read-only sync.</Empty>:null}</div></Panel>\n      <Panel className="span-5" icon={<ShieldCheck size={17}/>} title="Broker Read Snapshots" action={<span>{snapshot?.broker_snapshots.length ?? 0} datasets</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.broker_snapshots.map((row)=><article className="source-check-row" key={`${value(row,"provider")}-${value(row,"dataset")}`}><div><strong>{value(row,"provider")} · {value(row,"dataset")}</strong><p>{value(row,"source_connector_key")} · account {value(row,"account_ref")}</p></div><StatusPill status="read only"/><span>{value(row,"row_count","0")} rows</span><time>{date(row.retrieved_at)}</time></article>)}{!snapshot?.broker_snapshots.length?<Empty>Zerodha has not been authenticated and synced yet. Broker writes remain unavailable.</Empty>:null}</div></Panel>\n      <Panel className="span-7" icon={<Activity size={17}/>} title="Live Signals" action={<span>{snapshot?.signals.length ?? 0} signals</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.signals.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"strategy")}</strong><p>{value(row,"exchange")} · confidence {value(row,"confidence","-")}</p></div><StatusPill status={value(row,"action","watch")}/><span>{amount(row.price)}</span><time>{date(row.ts)}</time></article>)}{!snapshot?.signals.length?<Empty>No live signal rows.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<ClipboardPlus size={17}/>} title="Trade Journal"><form className="operator-form" onSubmit={submitTrade}><label><span>Record type</span><select value={trade.mode} onChange={(event)=>setTrade({...trade,mode:event.target.value})}><option value="manual">Manual trade</option><option value="paper">Paper trade</option></select></label><label><span>Symbol</span><input required value={trade.symbol} onChange={(event)=>setTrade({...trade,symbol:event.target.value.toUpperCase()})}/></label><label><span>Side</span><select value={trade.side} onChange={(event)=>setTrade({...trade,side:event.target.value})}><option value="buy">Buy</option><option value="sell">Sell</option><option value="long">Long</option><option value="short">Short</option><option value="exit">Exit</option></select></label><label><span>Quantity</span><input inputMode="decimal" value={trade.quantity} onChange={(event)=>setTrade({...trade,quantity:event.target.value})}/></label><label><span>Price</span><input inputMode="decimal" value={trade.price} onChange={(event)=>setTrade({...trade,price:event.target.value})}/></label><label><span>Strategy</span><input value={trade.strategy} onChange={(event)=>setTrade({...trade,strategy:event.target.value})}/></label><label className="span-form"><span>Thesis</span><input value={trade.thesis} onChange={(event)=>setTrade({...trade,thesis:event.target.value})}/></label><button className="primary-button span-form" disabled={Boolean(actionBusy)} type="submit"><ClipboardPlus size={15}/>{actionBusy === "trade" ? "Recording" : "Record journal entry"}</button><p className="form-guard span-form">Journal only. This route cannot submit a broker order.</p></form></Panel>
      <Panel className="span-7" icon={<BarChart3 size={17}/>} title="TradingView Controller" action={<span>{snapshot?.tradingview_cdp.available ? "CDP online" : "CDP offline"}</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.tradingview_tasks.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"task_title")}</strong><p>{value(row,"symbols")} · {value(row,"timeframe")} · {value(row,"result_summary")}</p></div><StatusPill status={value(row,"status","queued")}/><span>#{value(row,"id")}</span><time>{date(row.updated_at)}</time></article>)}</div></Panel>
      <Panel className="span-7" icon={<Workflow size={17}/>} title="Trade Activity"><div className="source-check-list scoped-scroll-list">{snapshot?.trade_activity.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"side")}</strong><p>{value(row,"execution_mode")} · {value(row,"strategy_key")}</p></div><StatusPill status={value(row,"status","recorded")}/><span>{value(row,"quantity")} @ {amount(row.price)}</span><time>{date(row.trade_ts)}</time></article>)}{!snapshot?.trade_activity.length?<Empty>No journal trades recorded.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<Beaker size={17}/>} title="Paper Monitor"><div className="source-check-list scoped-scroll-list">{snapshot?.paper_monitors.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")}</strong><p>{value(row,"heartbeat_status")} · {value(row,"total_events","0")} events</p></div><StatusPill status={value(row,"status","idle")}/><span>{value(row,"live_execution_allowed","false") === "true" ? "live" : "paper"}</span><time>{date(row.last_heartbeat_at)}</time></article>)}{!snapshot?.paper_monitors.length?<Empty>No active paper-monitor session.</Empty>:null}</div></Panel>
    </section> : null}

    {mode === "risk" ? <section className="dashboard-grid">
      <Panel className="span-12" icon={<ShieldAlert size={17}/>} title="Risk Controls" action={<div className="panel-action-group"><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={()=>void runSafeAction("full-risk",()=>runInstitutionalPortfolioRisk({actor:"Portfolio Risk Analyst",lookback_days:756,simulations:20000}),"Institutional risk cycle completed without capital or execution authority.")} type="button">{actionBusy === "full-risk" ? "Running paths" : "Run full risk"}</button><button className="mini-action-button" disabled={Boolean(actionBusy)} onClick={()=>void runSafeAction("risk-refresh",()=>refreshPortfolioRiskEvents({actor:"Chief Risk Officer"}),"Portfolio risk events refreshed.")} type="button">{actionBusy === "risk-refresh" ? "Running" : "Refresh checks"}</button><button className="danger-button" disabled={Boolean(actionBusy)} onClick={()=>{if(window.confirm("Engage the global kill switch and keep broker writes locked?")) void runSafeAction("kill",()=>engageGlobalKillSwitch({actor:"Chief Risk Officer",trigger_source:"risk_center",trigger_reason:"Manual emergency stop from Risk Center"}),"Global kill switch engaged; broker writes remain locked.");}} type="button"><Siren size={14}/>{actionBusy === "kill" ? "Engaging" : "Global kill switch"}</button></div>}><div className="quant-control-strip"><span>{riskBreaches} breaches</span><span>{warnings} warnings</span><span>{value(execution,"broker_execution_policy","blocked")}</span><span>{value(institutionalRun,"run_status","not run")}</span></div></Panel>
      <Panel className="span-12" icon={<Gauge size={17}/>} title="Institutional Portfolio Risk" action={<StatusPill status={value(institutionalRun,"run_status","not run")}/>}><div className="quant-control-strip"><span>Gross {amount(portfolioRisk?.gross_exposure)}</span><span>Coverage {percent(portfolioRisk?.coverage_pct)}</span><span>1D VaR 99 {percent(portfolioRisk?.bootstrap_var_99_1d_pct)}</span><span>10D VaR 99 {percent(portfolioRisk?.bootstrap_var_99_10d_pct)}</span><span>Max drawdown {percent(portfolioRisk?.maximum_drawdown_pct)}</span><span>Beta {value(portfolioRisk,"market_beta")}</span></div><p className="form-guard">Provisional analytics only. {value(institutionalRun,"covered_symbol_count","0")} of {value(institutionalRun,"source_symbol_count","0")} symbols have usable history; capital changes and broker execution remain blocked.</p><div className="portfolio-intelligence-list scoped-scroll-list">{snapshot?.institutional_risk_metrics.map((row)=><article className="portfolio-intelligence-row" key={`${value(row,"scope_type")}-${value(row,"scope_ref")}`}><div><strong>{value(row,"scope_name")}</strong><p>{value(row,"scope_type")} · coverage {percent(row.coverage_pct)} · {value(row,"observation_count","0")} observations</p></div><span>{percent(row.bootstrap_var_99_10d_pct)} 10D VaR</span></article>)}{!snapshot?.institutional_risk_metrics.length?<Empty>Run the institutional risk cycle to calculate real portfolio metrics.</Empty>:null}</div></Panel>
      <Panel className="span-7" icon={<Siren size={17}/>} title="Stress Scenarios"><div className="source-check-list scoped-scroll-list">{portfolioStress.map((row)=><article className="source-check-row" key={value(row,"scenario_key")}><div><strong>{value(row,"scenario_name")}</strong><p>{value(row,"description")}</p></div><StatusPill status={value(row,"severity","review")}/><span>{amount(row.stressed_pnl_value)} · {percent(row.stressed_return_pct)}</span><time>{value(row,"calculation_status")}</time></article>)}{!portfolioStress.length?<Empty>No completed portfolio stress scenarios.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<Activity size={17}/>} title="Factor Attribution"><div className="source-check-list scoped-scroll-list">{portfolioFactors.map((row)=><article className="source-check-row" key={value(row,"factor_key")}><div><strong>{value(row,"factor_name")}</strong><p>{value(row,"methodology")}</p></div><StatusPill status={value(row,"calculation_status","review")}/><span>{percent(row.contribution_pct)}</span><time>input {value(row,"exposure_value")}</time></article>)}{!portfolioFactors.length?<Empty>No factor attribution rows.</Empty>:null}</div></Panel>
      <Panel className="span-12" icon={<BarChart3 size={17}/>} title="Position Liquidity" action={<span>{unavailableLiquidity} unavailable · {portfolioLiquidity.length} positions</span>}><div className="source-check-list scoped-scroll-list">{portfolioLiquidity.map((row)=><article className="source-check-row" key={value(row,"symbol")}><div><strong>{value(row,"symbol")}</strong><p>{value(row,"liquidity_bucket")} · median traded value {amount(row.median_daily_traded_value)}</p></div><StatusPill status={value(row,"calculation_status","review")}/><span>{value(row,"estimated_days_to_liquidate","-")} days</span><time>{amount(row.gross_exposure)}</time></article>)}{!portfolioLiquidity.length?<Empty>No position-liquidity assessments.</Empty>:null}</div></Panel>
      <Panel className="span-5" icon={<Gauge size={17}/>} title="Risk Summary"><div className="portfolio-intelligence-list scoped-scroll-list">{snapshot?.risk_summary.map((row)=><article className="portfolio-intelligence-row" key={value(row,"metric")}><div><strong>{value(row,"metric").replace(/_/g," ")}</strong><p>{value(row,"interpretation")}</p></div><span>{value(row,"value")}</span></article>)}</div></Panel>
      <Panel className="span-7" icon={<ShieldCheck size={17}/>} title="Limit Checks" action={<span>{snapshot?.risk_limits.length ?? 0} checks</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.risk_limits.map((row)=><article className="source-check-row" key={value(row,"check_key")}><div><strong>{value(row,"limit_name")} · {value(row,"symbol",value(row,"book_name"))}</strong><p>{value(row,"check_message")} · {value(row,"recommended_action")}</p></div><StatusPill status={value(row,"check_status","review")}/><span>{value(row,"utilization_pct","-")}%</span><time>{date(row.latest_as_of)}</time></article>)}</div></Panel>
      <Panel className="span-6" icon={<Siren size={17}/>} title="Limited-Live Requests"><div className="source-check-list scoped-scroll-list">{snapshot?.limited_live_requests.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")} · {value(row,"symbol")}</strong><p>{value(row,"rationale")}</p></div><StatusPill status={value(row,"request_status","review")}/><span>{amount(row.max_notional)}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.limited_live_requests.length?<Empty>No limited-live requests.</Empty>:null}</div></Panel>
      <Panel className="span-6" icon={<ClipboardPlus size={17}/>} title="Order Intents"><div className="source-check-list scoped-scroll-list">{snapshot?.order_intents.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"symbol")} · {value(row,"side")}</strong><p>{value(row,"strategy_name")} · {value(row,"rationale")}</p></div><StatusPill status={value(row,"gate_status","blocked")}/><span>{amount(row.notional)}</span><time>{date(row.updated_at)}</time></article>)}{!snapshot?.order_intents.length?<Empty>No order intents.</Empty>:null}</div></Panel>
      <Panel className="span-12" icon={<Activity size={17}/>} title="Drift Checks"><div className="source-check-list scoped-scroll-list">{snapshot?.drift_checks.map((row)=><article className="source-check-row" key={value(row,"id")}><div><strong>{value(row,"strategy_name")} · {value(row,"instance_name")}</strong><p>{value(row,"findings")}</p></div><StatusPill status={value(row,"drift_level","review")}/><span>score {value(row,"drift_score","-")}</span><time>{date(row.checked_at)}</time></article>)}{!snapshot?.drift_checks.length?<Empty>No drift checks.</Empty>:null}</div></Panel>
    </section> : null}
  </div>;
}
