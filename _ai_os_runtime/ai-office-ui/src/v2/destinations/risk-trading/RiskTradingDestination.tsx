import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, Beaker, BookOpen, Bot, ClipboardPlus, ExternalLink, Gauge, Link2, Radar, RefreshCw, ShieldAlert, ShieldCheck, Siren, Workflow } from "lucide-react";
import { get } from "../../data/client";
import { queryKeys, useAction, useOfficeSnapshot, useTradingQuantRisk } from "../../data/queries";
import type { LiveRow } from "../../data/liveRow";
import { formatCompact, formatCurrency, formatRelative, num, primaryText, text } from "../../data/liveRow";
import { Freshness, LiveTable, MetricCell, MetricStrip, RowTitle, StatusCell, WorkspaceError, WorkspaceGrid, countStatus } from "../../data/WorkspaceKit";
import { Badge, Button, Field, Panel, Select, StatusPill, Tabs, TextArea, TextInput } from "../../system/primitives";
import { BarSeriesChart, LineSeriesChart } from "../../system/charts";
import { useUIStore } from "../../store";

const TABS = [
  { key: "dashboard", label: "Risk Dashboard" },
  { key: "options", label: "Options Desk" },
  { key: "scanners", label: "Scanners & Alerts" },
  { key: "trading", label: "Trading Desk" },
  { key: "quant", label: "Quant Lab" },
  { key: "limits", label: "Limits" },
  { key: "safety", label: "Execution Safety" },
];

type TradingData = NonNullable<ReturnType<typeof useTradingQuantRisk>["data"]>;
type ZerodhaStatus = { status?: LiveRow; session?: LiveRow; callback_url?: string; broker_write_allowed?: boolean };

export default function RiskTradingDestination() {
  const query = useTradingQuantRisk();
  const [tab, setTab] = React.useState("dashboard");
  const data = query.data;
  const execution = data?.execution_control[0];
  const breaches = data?.risk_limits.filter((row) => text(row, "check_status").toLowerCase() === "breach").length ?? 0;
  const warnings = data?.risk_limits.filter((row) => text(row, "check_status").toLowerCase() === "warning").length ?? 0;
  const alerts = data?.alerts.length ?? 0;
  const locked = execution ? !Boolean(execution.live_broker_writes_allowed) : true;

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row"><div className="aios-destination__title">Risk & Trading</div><Freshness generatedAt={data?.generated_at} />{locked ? <StatusPill tone="ok">Broker writes locked</StatusPill> : <StatusPill tone="risk">Broker writes enabled</StatusPill>}</div>
        <div className="aios-destination__subtitle">Read-only market intelligence, options analytics, technical scanners, strategy validation and human-gated execution controls.</div>
        <Tabs tabs={TABS.map((item) => item.key === "options" ? { ...item, count: data?.option_chain.length ?? 0 } : item.key === "scanners" ? { ...item, count: alerts, countTone: alerts ? "risk" as const : "default" as const } : item)} active={tab} onChange={setTab} />
      </div>
      <WorkspaceError error={query.error} />
      <MetricStrip>
        <MetricCell label="Risk breaches" value={breaches} tone={breaches ? "risk" : "ok"} />
        <MetricCell label="Warnings" value={warnings} tone={warnings ? "warn" : "ok"} />
        <MetricCell label="Live signals" value={data?.signals.length ?? 0} detail={`${alerts} open alerts`} />
        <MetricCell label="Option contracts" value={data?.option_chain.length ?? 0} detail={`${data?.options_surface.length ?? 0} surfaces`} />
        <MetricCell label="Quant candidates" value={data?.quant_lab.length ?? 0} detail={`${data?.paper_monitors.length ?? 0} monitors`} />
        <MetricCell label="Execution" value={locked ? "LOCKED" : "REVIEW"} detail={text(execution, "lock_reason", "human approval required")} tone={locked ? "ok" : "risk"} />
      </MetricStrip>
      {data ? <TradingTab tab={tab} data={data} /> : null}
    </div>
  );
}

function TradingTab({ tab, data }: { tab: string; data: TradingData }) {
  if (tab === "dashboard") return <RiskDashboard data={data} />;
  if (tab === "options") return <OptionsDesk data={data} />;
  if (tab === "scanners") return <Scanners data={data} />;
  if (tab === "trading") return <TradingDesk data={data} />;
  if (tab === "quant") return <QuantLab data={data} />;
  if (tab === "limits") return <Limits data={data} />;
  return <Safety data={data} />;
}

function RiskDashboard({ data }: { data: TradingData }) {
  const portfolio = data.institutional_risk_metrics.find((row) => text(row, "scope_type") === "portfolio");
  const stress = data.institutional_stress.filter((row) => text(row, "scope_type") === "portfolio");
  const factors = data.institutional_factors.filter((row) => text(row, "scope_type") === "portfolio");
  const factorChart = factors.slice(0, 12).map((row) => ({ factor: text(row, "factor_name"), contribution: num(row, "contribution_pct") }));
  const stressChart = stress.slice(0, 12).map((row) => ({ scenario: text(row, "scenario_name"), return: num(row, "stressed_return_pct") }));
  return <WorkspaceGrid><Panel icon={Gauge} title="Institutional portfolio risk"><MetricStrip><MetricCell label="Gross exposure" value={formatCompact(num(portfolio,"gross_exposure"),"INR")}/><MetricCell label="Coverage" value={`${num(portfolio,"coverage_pct").toFixed(1)}%`}/><MetricCell label="1D VaR 99" value={`${num(portfolio,"bootstrap_var_99_1d_pct").toFixed(2)}%`} tone="warn"/><MetricCell label="10D VaR 99" value={`${num(portfolio,"bootstrap_var_99_10d_pct").toFixed(2)}%`} tone="risk"/><MetricCell label="Max drawdown" value={`${num(portfolio,"maximum_drawdown_pct").toFixed(2)}%`}/></MetricStrip></Panel><Panel icon={Activity} title="Latest risk run"><LiveTable rows={data.institutional_risk_run} emptyTitle="No risk run" columns={[
    {key:"run_key",label:"Run",render:(row)=><RowTitle row={row} titleKeys={["run_key"]} detailKeys={["methodology"]}/>},{key:"simulation_count",label:"Paths",align:"right"},{key:"coverage_pct",label:"Coverage",align:"right"},{key:"run_status",label:"Status",render:(row)=><StatusCell row={row} keys={["run_status"]}/>},
  ]}/></Panel><Panel icon={Siren} title="Stress scenarios"><BarSeriesChart data={stressChart} xKey="scenario" bars={[{key:"return",name:"Stressed return",color:"#d05246"}]} height={270}/></Panel><Panel icon={BarChart3} title="Factor attribution"><BarSeriesChart data={factorChart} xKey="factor" bars={[{key:"contribution",name:"Contribution",color:"#2d8b69"}]} height={270}/></Panel><Panel className="aios-workspace-span" icon={ShieldAlert} title="Risk event queue"><LiveTable rows={data.risk_limits.filter((row)=>text(row,"check_status")!=="pass")} emptyTitle="No open risk events" columns={[
    {key:"limit_name",label:"Control",render:(row)=><RowTitle row={row} titleKeys={["limit_name"]} detailKeys={["check_message","recommended_action"]}/>},{key:"symbol",label:"Scope",render:(row)=>text(row,"symbol",text(row,"book_name"))},{key:"utilization_pct",label:"Utilisation",align:"right",render:(row)=>`${num(row,"utilization_pct").toFixed(1)}%`},{key:"severity",label:"Severity",render:(row)=><StatusCell row={row} keys={["check_status","severity"]}/>},
  ]}/></Panel></WorkspaceGrid>;
}

function OptionsDesk({ data }: { data: TradingData }) {
  const surfaces = data.options_surface;
  const underlyings = [...new Set(surfaces.map((row) => text(row, "underlying")).filter(Boolean))];
  const [underlying, setUnderlying] = React.useState(underlyings[0] ?? "NIFTY");
  const expiries = [...new Set(surfaces.filter((row) => text(row,"underlying")===underlying).map((row)=>text(row,"expiry")).filter(Boolean))];
  const [expiry, setExpiry] = React.useState(expiries[0] ?? "");
  React.useEffect(() => { if (!expiries.includes(expiry)) setExpiry(expiries[0] ?? ""); }, [underlying, expiry, expiries.join("|")]);
  const chain = data.option_chain.filter((row) => text(row,"underlying")===underlying && (!expiry || text(row,"expiry")===expiry));
  const analytics = React.useMemo(() => optionAnalytics(chain), [chain]);
  const oiChanges = (data.option_oi_change ?? []).filter((row) => text(row,"underlying")===underlying && (!expiry || text(row,"expiry")===expiry));
  const oiChangeChart = groupOptionRows(oiChanges, "open_interest_change");
  const office = useOfficeSnapshot();
  const specialists = office.data?.agents.filter((row) => /option|volatil/i.test(`${text(row,"agent_name")} ${text(row,"display_title")} ${text(row,"role")}`)).slice(0,6) ?? [];
  const zerodha = useQuery<ZerodhaStatus>({ queryKey:["zerodha-stream-status"], queryFn:()=>get("/api/zerodha/stream/status"), refetchInterval:30_000 });
  const sync = useAction<Record<string,unknown>>("/api/zerodha/market/sync", { invalidate:[queryKeys.tradingQuantRisk] });
  const notify = useUIStore((state)=>state.pushToast);
  const ask = () => { useUIStore.getState().setAssistantScope({agentKey:"options_analyst",agentName:"Options Analyst"}); window.dispatchEvent(new CustomEvent("aios:assistant-prefill",{detail:`Review the live ${underlying} ${expiry} options surface. ATM ${analytics.atm}, straddle ${analytics.straddle.toFixed(2)}, PCR ${analytics.pcr.toFixed(2)}, max pain ${analytics.maxPain}. Explain OI shifts, volatility regime, defined-risk structures, invalidation and what needs monitoring. Do not place a trade.`})); };
  const loginUrl = typeof zerodha.data?.session?.login_url === "string" ? zerodha.data.session.login_url : "";
  const sessionReady = Boolean(zerodha.data?.session?.daily_access_token_available);
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Link2} title="Zerodha read-only market session" actions={<StatusPill status={sessionReady?"live":"login required"} dot>{sessionReady?"Session active":"Daily login required"}</StatusPill>}><div className="aios-toolbar"><Field label="Underlying"><Select value={underlying} onChange={(event)=>setUnderlying(event.target.value)}>{underlyings.map((item)=><option key={item}>{item}</option>)}</Select></Field><Field label="Expiry"><Select value={expiry} onChange={(event)=>setExpiry(event.target.value)}>{expiries.map((item)=><option key={item}>{item}</option>)}</Select></Field><Button icon={ExternalLink} onClick={()=>loginUrl&&window.open(loginUrl,"_blank","noopener,noreferrer")} disabled={!loginUrl}>Reconnect Zerodha</Button><Button icon={RefreshCw} onClick={()=>sync.mutate({actor:"Options Data Agent",modes:["quotes","options"],underlyings:[underlying],strike_pairs:40},{onSuccess:()=>notify({title:"Option chain refresh started",tone:"ok",duration:4500}),onError:(error)=>notify({title:"Option refresh failed",message:error.message,tone:"risk",duration:8000})})} disabled={sync.isPending}>Refresh chain</Button><Button variant="primary" icon={Bot} onClick={ask}>Ask Options Desk</Button></div></Panel><Panel className="aios-workspace-span" icon={Gauge} title={`${underlying} ${expiry} option surface`} actions={<Badge tone="accent">{chain.length} contracts</Badge>}><MetricStrip><MetricCell label="Spot" value={analytics.spot.toFixed(2)}/><MetricCell label="ATM" value={analytics.atm || "-"}/><MetricCell label="ATM straddle" value={analytics.straddle.toFixed(2)}/><MetricCell label="Put / Call OI" value={analytics.pcr.toFixed(2)} tone={analytics.pcr>1.2?"warn":"default"}/><MetricCell label="Average IV" value={`${analytics.averageIv.toFixed(2)}%`}/><MetricCell label="Max pain" value={analytics.maxPain||"-"}/><MetricCell label="Call wall" value={analytics.callWall||"-"}/><MetricCell label="Put wall" value={analytics.putWall||"-"}/></MetricStrip></Panel><div className="aios-chart-grid aios-workspace-span"><Panel icon={BarChart3} title="Open interest by strike"><BarSeriesChart data={analytics.byStrike} xKey="strike" bars={[{key:"CE",name:"Call OI",color:"#c94f49"},{key:"PE",name:"Put OI",color:"#2d8b69"}]} height={300}/></Panel><Panel icon={Activity} title="Implied volatility smile"><LineSeriesChart data={analytics.byStrike} xKey="strike" series={[{key:"ceIv",name:"Call IV",color:"#c58b23"},{key:"peIv",name:"Put IV",color:"#2f78a7"}]} height={300}/></Panel><Panel icon={Workflow} title="Straddle curve"><LineSeriesChart data={analytics.byStrike} xKey="strike" series={[{key:"straddle",name:"CE + PE",color:"#7e55a5"}]} height={300}/></Panel><Panel icon={Radar} title="Change in OI"><BarSeriesChart data={oiChangeChart} xKey="strike" bars={[{key:"CE",name:"Call OI change",color:"#c94f49"},{key:"PE",name:"Put OI change",color:"#2d8b69"}]} height={300}/></Panel></div><Panel className="aios-workspace-span" icon={BookOpen} title="Options chain"><LiveTable rows={chain} emptyTitle="No live option contracts" limit={400} columns={[
    {key:"strike",label:"Strike",align:"right"},{key:"option_type",label:"Type",render:(row)=><StatusPill tone={text(row,"option_type")==="CE"?"risk":"ok"}>{text(row,"option_type")}</StatusPill>},{key:"last_price",label:"LTP",align:"right"},{key:"bid_price",label:"Bid",align:"right"},{key:"ask_price",label:"Ask",align:"right"},{key:"open_interest",label:"OI",align:"right",render:(row)=>formatCompact(num(row,"open_interest"))},{key:"volume",label:"Volume",align:"right",render:(row)=>formatCompact(num(row,"volume"))},{key:"implied_volatility",label:"IV",align:"right"},{key:"delta",label:"Delta",align:"right"},{key:"gamma",label:"Gamma",align:"right"},{key:"theta",label:"Theta",align:"right"},{key:"vega",label:"Vega",align:"right"},
  ]}/></Panel><Panel icon={Bot} title="Options specialists"><LiveTable rows={specialists} emptyTitle="No options specialists registered" columns={[
    {key:"agent_name",label:"Specialist",render:(row)=><RowTitle row={row} titleKeys={["agent_name","name"]} detailKeys={["display_title","role"]}/>},{key:"activity_status",label:"State",render:(row)=><StatusCell row={row} keys={["live_state","activity_status","status"]}/>},{key:"current_work_title",label:"Current work"},
  ]}/></Panel><Panel icon={ClipboardPlus} title="Historical option journal"><LiveTable rows={data.option_trade_log ?? []} emptyTitle="No imported option trades" columns={[
    {key:"trade_id",label:"Trade",render:(row)=><RowTitle row={row} titleKeys={["trade_id","stock_ticker"]} detailKeys={["trade_type","trade_status"]}/>},{key:"stock_ticker",label:"Underlying"},{key:"side",label:"Side"},{key:"call_put",label:"Leg"},{key:"strike_price",label:"Strike",align:"right"},{key:"entry_date",label:"Entry"},{key:"exit_date",label:"Exit"},{key:"entry_credit_debit",label:"Entry premium",align:"right"},
  ]}/></Panel></WorkspaceGrid>;
}

function Scanners({ data }: { data: TradingData }) {
  const office = useOfficeSnapshot();
  const specialists = office.data?.agents.filter((row)=>/technical|microstructure|trading desk|market/i.test(`${text(row,"agent_name")} ${text(row,"display_title")} ${text(row,"role")}`)).slice(0,12) ?? [];
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Radar} title="Live technical alerts"><LiveTable rows={data.alerts} emptyTitle="No open alerts" columns={[
    {key:"title",label:"Alert",render:(row)=><RowTitle row={row} titleKeys={["title"]} detailKeys={["message"]}/>},{key:"symbol",label:"Symbol"},{key:"timeframe",label:"Timeframe"},{key:"severity",label:"Severity",render:(row)=><StatusCell row={row} keys={["severity","status"]}/>},{key:"ts",label:"Observed"},
  ]}/></Panel><Panel icon={Activity} title="Strategy signals"><LiveTable rows={data.signals} emptyTitle="No live signals" columns={[
    {key:"symbol",label:"Signal",render:(row)=><RowTitle row={row} titleKeys={["symbol"]} detailKeys={["strategy"]}/>},{key:"action",label:"Action",render:(row)=><StatusCell row={row} keys={["action","status"]}/>},{key:"confidence",label:"Confidence",align:"right"},{key:"price",label:"Price",align:"right"},{key:"ts",label:"Time"},
  ]}/></Panel><Panel icon={Bot} title="Monitoring desk"><LiveTable rows={specialists} emptyTitle="No monitoring agents" columns={[
    {key:"agent_name",label:"Agent",render:(row)=><RowTitle row={row} titleKeys={["agent_name","name"]} detailKeys={["display_title","role"]}/>},{key:"current_work_title",label:"Current assignment"},{key:"status",label:"State",render:(row)=><StatusCell row={row} keys={["live_state","activity_status","status"]}/>},
  ]}/></Panel><Panel className="aios-workspace-span" icon={BarChart3} title="TradingView automation queue"><LiveTable rows={data.tradingview_tasks} emptyTitle="No chart tasks" columns={[
    {key:"task_title",label:"Chart work",render:(row)=><RowTitle row={row} titleKeys={["task_title"]} detailKeys={["instruction","result_summary"]}/>},{key:"symbols",label:"Symbols"},{key:"timeframe",label:"Timeframe"},{key:"owner_agent",label:"Owner"},{key:"status",label:"Status",render:(row)=><StatusCell row={row}/>},{key:"updated_at",label:"Updated"},
  ]}/></Panel></WorkspaceGrid>;
}

function TradingDesk({ data }: { data: TradingData }) {
  const [trade,setTrade]=React.useState({mode:"manual",symbol:"",side:"buy",quantity:"",price:"",strategy_key:"",thesis:""});
  const endpoint=trade.mode==="paper"?"/api/trades/paper":"/api/trades/manual";
  const record=useAction<Record<string,unknown>>(endpoint,{invalidate:[queryKeys.tradingQuantRisk]});
  const notify=useUIStore((state)=>state.pushToast);
  const submit=(event:React.FormEvent)=>{event.preventDefault();record.mutate({...trade,actor:"Devarsh",exchange:"NSE",instrument_type:"equity"},{onSuccess:()=>{notify({title:`${trade.mode} trade journalled`,message:"No broker order was sent.",tone:"ok",duration:5000});setTrade({...trade,symbol:"",quantity:"",price:"",thesis:""});},onError:(error)=>notify({title:"Trade journal failed",message:error.message,tone:"risk",duration:8000})});};
  return <WorkspaceGrid><Panel icon={ClipboardPlus} title="Journal a trade"><form className="aios-toolbar" onSubmit={submit}><Field label="Record"><Select value={trade.mode} onChange={(e)=>setTrade({...trade,mode:e.target.value})}><option value="manual">Manual</option><option value="paper">Paper</option></Select></Field><Field label="Symbol"><TextInput required value={trade.symbol} onChange={(e)=>setTrade({...trade,symbol:e.target.value.toUpperCase()})}/></Field><Field label="Side"><Select value={trade.side} onChange={(e)=>setTrade({...trade,side:e.target.value})}><option>buy</option><option>sell</option><option>long</option><option>short</option><option>exit</option></Select></Field><Field label="Quantity"><TextInput inputMode="decimal" value={trade.quantity} onChange={(e)=>setTrade({...trade,quantity:e.target.value})}/></Field><Field label="Price"><TextInput inputMode="decimal" value={trade.price} onChange={(e)=>setTrade({...trade,price:e.target.value})}/></Field><Field label="Strategy"><TextInput value={trade.strategy_key} onChange={(e)=>setTrade({...trade,strategy_key:e.target.value})}/></Field><Field label="Thesis"><TextArea rows={2} value={trade.thesis} onChange={(e)=>setTrade({...trade,thesis:e.target.value})}/></Field><Button type="submit" variant="primary" icon={ClipboardPlus} disabled={record.isPending}>Record only</Button></form></Panel><Panel icon={Workflow} title="Activity ledger"><LiveTable rows={data.trade_activity} emptyTitle="No manual or paper trades" columns={[
    {key:"symbol",label:"Trade",render:(row)=><RowTitle row={row} titleKeys={["symbol"]} detailKeys={["thesis","strategy_key"]}/>},{key:"execution_mode",label:"Mode"},{key:"side",label:"Side"},{key:"quantity",label:"Qty",align:"right"},{key:"price",label:"Price",align:"right"},{key:"realized_pnl",label:"Realised P&L",align:"right",render:(row)=>formatCurrency(num(row,"realized_pnl"))},{key:"status",label:"Status",render:(row)=><StatusCell row={row}/>},
  ]}/></Panel><Panel className="aios-workspace-span" icon={BarChart3} title="Approved chart workflows"><LiveTable rows={data.tradingview_templates} emptyTitle="No TradingView templates" columns={[
    {key:"template_name",label:"Workflow",render:(row)=><RowTitle row={row} titleKeys={["template_name"]} detailKeys={["description","risk_notes"]}/>},{key:"category",label:"Category"},{key:"default_timeframe",label:"Timeframe"},{key:"approval_required",label:"Approval"},{key:"execution_mode",label:"Mode"},{key:"status",label:"Status",render:(row)=><StatusCell row={row}/>},
  ]}/></Panel></WorkspaceGrid>;
}

function QuantLab({ data }: { data: TradingData }) { return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Beaker} title="Quant research board"><LiveTable rows={data.quant_lab} emptyTitle="No quant candidates" columns={[
  {key:"strategy_name",label:"Strategy",render:(row)=><RowTitle row={row} titleKeys={["strategy_name"]} detailKeys={["recommended_action","trigger_reasons"]}/>},{key:"timeframe",label:"Timeframe"},{key:"validation_status",label:"Validation",render:(row)=><StatusCell row={row} keys={["validation_status"]}/>},{key:"expected_return",label:"Expected return",align:"right"},{key:"expected_volatility",label:"Volatility",align:"right"},{key:"max_drawdown_p95",label:"Drawdown p95",align:"right"},{key:"activation_gate",label:"Gate",render:(row)=><StatusCell row={row} keys={["activation_gate"]}/>},
]}/></Panel><Panel icon={ShieldCheck} title="Model validation"><LiveTable rows={data.model_validation} emptyTitle="No validation rows" columns={[
  {key:"strategy_name",label:"Model"},{key:"review_status",label:"Review",render:(row)=><StatusCell row={row} keys={["review_status","validation_status"]}/>},{key:"leakage_risk",label:"Leakage"},{key:"overfit_risk",label:"Overfit"},{key:"required_fixes",label:"Required fixes"},
]}/></Panel><Panel icon={Activity} title="Paper monitors"><LiveTable rows={data.paper_monitors} emptyTitle="No paper monitors" columns={[
  {key:"strategy_name",label:"Strategy"},{key:"heartbeat_status",label:"Heartbeat",render:(row)=><StatusCell row={row} keys={["heartbeat_status","status"]}/>},{key:"total_events",label:"Events",align:"right"},{key:"last_heartbeat_at",label:"Last heartbeat"},
]}/></Panel></WorkspaceGrid>; }

function Limits({ data }: { data: TradingData }) { return <WorkspaceGrid><Panel className="aios-workspace-span" icon={ShieldAlert} title="Portfolio and book limits"><LiveTable rows={data.risk_limits} emptyTitle="No risk limits" limit={180} columns={[
  {key:"limit_name",label:"Limit",render:(row)=><RowTitle row={row} titleKeys={["limit_name"]} detailKeys={["check_message","recommended_action"]}/>},{key:"scope_ref",label:"Scope",render:(row)=>primaryText(row,["symbol","book_name","client_name","scope_ref"])},{key:"actual_value",label:"Actual",align:"right"},{key:"threshold_value",label:"Threshold",align:"right"},{key:"utilization_pct",label:"Utilisation",align:"right",render:(row)=>`${num(row,"utilization_pct").toFixed(1)}%`},{key:"check_status",label:"Status",render:(row)=><StatusCell row={row} keys={["check_status","severity"]}/>},
]}/></Panel></WorkspaceGrid>; }

function Safety({ data }: { data: TradingData }) { const control=data.execution_control[0]; return <WorkspaceGrid><Panel icon={ShieldCheck} title="Global execution state"><MetricStrip><MetricCell label="Global lock" value={String(control?.global_execution_locked??true)} tone="ok"/><MetricCell label="Broker policy" value={text(control,"broker_execution_policy","blocked")}/><MetricCell label="Paper trading" value={String(control?.paper_trading_allowed??false)}/><MetricCell label="Limited live" value={String(control?.limited_live_allowed??false)} tone="warn"/><MetricCell label="Broker writes" value={String(control?.live_broker_writes_allowed??false)} tone={control?.live_broker_writes_allowed?"risk":"ok"}/></MetricStrip></Panel><Panel icon={Siren} variant="risk" title="Emergency controls"><p style={{padding:16,color:"var(--text-secondary)"}}>Capital action and live execution remain human-gated. Emergency kill-switch actions are intentionally kept behind the approval board and a confirmation step.</p></Panel><Panel className="aios-workspace-span" icon={Workflow} title="Order intents"><LiveTable rows={data.order_intents} emptyTitle="No order intents" columns={[
  {key:"symbol",label:"Intent",render:(row)=><RowTitle row={row} titleKeys={["symbol"]} detailKeys={["strategy_name","rationale"]}/>},{key:"side",label:"Side"},{key:"notional",label:"Notional",align:"right",render:(row)=>formatCurrency(num(row,"notional"))},{key:"gate_status",label:"Gate",render:(row)=><StatusCell row={row} keys={["gate_status","approval_status"]}/>},{key:"broker_order_allowed",label:"Broker allowed"},
]}/></Panel><Panel className="aios-workspace-span" icon={ShieldAlert} title="Limited-live requests"><LiveTable rows={data.limited_live_requests} emptyTitle="No limited-live requests" columns={[
  {key:"strategy_name",label:"Request",render:(row)=><RowTitle row={row} titleKeys={["strategy_name"]} detailKeys={["rationale","symbol"]}/>},{key:"max_notional",label:"Max notional",align:"right",render:(row)=>formatCurrency(num(row,"max_notional"))},{key:"max_daily_loss",label:"Daily loss",align:"right",render:(row)=>formatCurrency(num(row,"max_daily_loss"))},{key:"request_status",label:"Status",render:(row)=><StatusCell row={row} keys={["request_status","approval_status"]}/>},
]}/></Panel></WorkspaceGrid>; }

function optionAnalytics(chain: LiveRow[]) {
  const spot = chain.reduce((value,row)=>num(row,"spot_price",value),0);
  const strikes=[...new Set(chain.map((row)=>num(row,"strike")).filter(Boolean))].sort((a,b)=>a-b);
  const atm=strikes.reduce((best,strike)=>Math.abs(strike-spot)<Math.abs(best-spot)?strike:best,strikes[0]??0);
  const byStrike=strikes.map((strike)=>{const ce=chain.find((row)=>num(row,"strike")===strike&&text(row,"option_type")==="CE");const pe=chain.find((row)=>num(row,"strike")===strike&&text(row,"option_type")==="PE");return {strike,CE:num(ce,"open_interest"),PE:num(pe,"open_interest"),ceIv:num(ce,"implied_volatility"),peIv:num(pe,"implied_volatility"),straddle:num(ce,"last_price")+num(pe,"last_price")};});
  const callOi=byStrike.reduce((sum,row)=>sum+row.CE,0);const putOi=byStrike.reduce((sum,row)=>sum+row.PE,0);
  const pain=strikes.map((settle)=>({strike:settle,pain:chain.reduce((sum,row)=>sum+(text(row,"option_type")==="CE"?Math.max(0,settle-num(row,"strike")):Math.max(0,num(row,"strike")-settle))*num(row,"open_interest"),0)})).sort((a,b)=>a.pain-b.pain)[0]?.strike??0;
  const averageIv=chain.length?chain.reduce((sum,row)=>sum+num(row,"implied_volatility"),0)/chain.length:0;
  const callWall=byStrike.sort((a,b)=>b.CE-a.CE)[0]?.strike??0;const putWall=[...byStrike].sort((a,b)=>b.PE-a.PE)[0]?.strike??0;
  const atmRow=byStrike.find((row)=>row.strike===atm);
  return {spot,atm,straddle:atmRow?.straddle??0,pcr:callOi?putOi/callOi:0,averageIv,maxPain:pain,callWall,putWall,byStrike:byStrike.sort((a,b)=>a.strike-b.strike)};
}

function groupOptionRows(rows: LiveRow[], valueKey: string) { const map=new Map<number,{strike:number;CE:number;PE:number}>();for(const row of rows){const strike=num(row,"strike");const current=map.get(strike)??{strike,CE:0,PE:0};current[text(row,"option_type")==="PE"?"PE":"CE"]+=num(row,valueKey);map.set(strike,current);}return [...map.values()].sort((a,b)=>a.strike-b.strike); }
