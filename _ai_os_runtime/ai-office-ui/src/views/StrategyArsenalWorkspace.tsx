import {
  Beaker,
  BookOpenCheck,
  FileSearch,
  FlaskConical,
  Layers3,
  Play,
  Plus,
  RefreshCw,
  Route,
  Search,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import {
  applyStrategyTemplate,
  createStrategyIntake,
  resolveStrategyDiscoveryTriage,
  runModelValidationSweep,
  runStrategyDiscovery,
  runUserDefinedStrategyOptimizer,
  type LiveRow,
  type ResolveStrategyDiscoveryTriageInput
} from "../api/live";
import { fetchStrategyArsenalSnapshot, type StrategyArsenalSnapshot } from "../api/strategyArsenal";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";
type TriageDecision = ResolveStrategyDiscoveryTriageInput["decision"];

interface Props { onStatusChange: (status: ConnectionStatus) => void; }

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
  if (typeof raw === "object") return JSON.stringify(raw);
  return String(raw);
}

function date(raw: unknown): string {
  if (!raw) return "not recorded";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["passed", "approved", "active", "complete", "completed", "ready"].some((token) => normalized.includes(token))) return "active";
  if (["blocked", "failed", "rejected", "error", "not_passed"].some((token) => normalized.includes(token))) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>;
}

function metric(snapshot: StrategyArsenalSnapshot | null, key: string): number {
  const row = snapshot?.summary.find((item) => value(item, "metric") === key);
  return Number(row?.value ?? 0);
}

const gateLabels: Array<[string, string]> = [
  ["dsl_parse", "DSL"],
  ["data_quality", "Data"],
  ["baseline_backtest", "Test"],
  ["optimization", "Opt"],
  ["model_validation", "Validate"],
  ["committee", "Committee"],
  ["paper_monitor", "Paper"],
  ["limited_live", "Limited"]
];

function gateFlags(row: LiveRow): Record<string, boolean> {
  const flags = row.gate_flags;
  return flags && typeof flags === "object" && !Array.isArray(flags) ? flags as Record<string, boolean> : {};
}

export default function StrategyArsenalWorkspace({ onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<StrategyArsenalSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [origin, setOrigin] = useState("all");
  const [stage, setStage] = useState("all");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [intake, setIntake] = useState({
    name: "", family: "quant", assetClass: "equity", symbols: "", universe: "NSE",
    timeframe: "daily", thesis: "", constraints: "", risk: "",
    engineTemplate: "momentum", costBps: "3", slippageBps: "2", minRows: "500"
  });

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchStrategyArsenalSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Strategy Arsenal API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    window.addEventListener("aios:strategy-arsenal-refresh", refresh);
    return () => window.removeEventListener("aios:strategy-arsenal-refresh", refresh);
  }, [refresh]);

  const stages = useMemo(() => Array.from(new Set((snapshot?.control_board ?? []).map((row) => value(row, "promotion_stage", "unclassified")))).sort(), [snapshot]);
  const candidates = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (snapshot?.control_board ?? []).filter((row) => {
      if (origin !== "all" && value(row, "origin_type") !== origin) return false;
      if (stage !== "all" && value(row, "promotion_stage") !== stage) return false;
      if (!normalized) return true;
      return ["strategy_name", "candidate_key", "symbols", "edge_hypothesis"].some((key) => value(row, key, "").toLowerCase().includes(normalized));
    });
  }, [origin, query, snapshot, stage]);
  const pendingDiscovery = useMemo(() => (snapshot?.discovery_triage ?? []).filter((row) => value(row, "triage_status") === "pending"), [snapshot]);
  const execution = snapshot?.execution_control[0];

  const runAction = async (key: string, action: () => Promise<unknown>, success: string) => {
    setBusy(key); setError(""); setNotice("");
    try { await action(); setNotice(success); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : `${key} failed`); }
    finally { setBusy(""); }
  };

  const submitIntake = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const symbols = intake.symbols.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean);
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const runFullPipeline = submitter?.value === "test";
    if (runFullPipeline) {
      await runAction("optimizer", () => runUserDefinedStrategyOptimizer({
        run_key: `operator_strategy_${Date.now()}`,
        actor: "Devarsh",
        strategy_name: intake.name || `Operator strategy ${new Date().toLocaleDateString("en-IN")}`,
        intake_text: intake.thesis,
        asset_class: intake.assetClass,
        symbols,
        universe: intake.universe,
        timeframe: intake.timeframe,
        template: intake.engineTemplate as "momentum" | "mean_reversion" | "breakout" | "low_volatility",
        constraints_text: intake.constraints || "Paper-first research only. No live execution.",
        risk_notes: intake.risk || "Parser, data, backtest, validation, committee, and paper gates required.",
        cost_bps: intake.costBps,
        slippage_bps: intake.slippageBps,
        min_total_rows: intake.minRows,
        min_rows_per_symbol: Math.min(500, Math.max(50, Number(intake.minRows) || 50))
      }), "Strategy research pipeline completed. Review the out-of-sample evidence and validation queue; no execution authority was granted.");
    } else {
      await runAction("intake", () => createStrategyIntake({
        intake_text: intake.thesis,
        strategy_name: intake.name || undefined,
        strategy_family: intake.family,
        asset_class: intake.assetClass,
        symbols,
        universe: intake.universe,
        timeframe: intake.timeframe,
        intent_tags: ["operator_submitted", "paper_first"],
        constraints_text: intake.constraints || undefined,
        risk_notes: intake.risk || "Parser, data, backtest, validation, committee, and paper gates required.",
        actor: "Devarsh"
      }), "Strategy intake added to the paper-first Arsenal.");
    }
    setIntake((current) => ({ ...current, name: "", symbols: "", thesis: "", constraints: "", risk: "" }));
  };

  const runDiscovery = () => runAction("discovery", () => runStrategyDiscovery({
    run_key: `arsenal_ui_${Date.now()}`,
    actor: "Strategy Discovery Agent",
    sources: "research,journals,signals,components",
    per_source_limit: 6,
    max_candidates: 16,
    route_top: 2
  }), "Source-backed discovery completed and routed through research gates.");

  const triage = (row: LiveRow, decision: TriageDecision) => runAction(`triage-${value(row, "id")}`, () => resolveStrategyDiscoveryTriage({
    discovery_candidate_id: value(row, "id"), decision, actor: "Devarsh",
    notes: "Decision recorded from the Strategy Arsenal terminal. Live execution remains disabled."
  }), `Discovery candidate routed: ${decision.replace(/_/g, " ")}.`);

  const applyTemplate = (row: LiveRow) => runAction(`template-${value(row, "template_key")}`, () => applyStrategyTemplate({
    template_key: value(row, "template_key"), actor: "Devarsh",
    strategy_name: `${value(row, "template_name")} - operator review`,
    symbols: Array.isArray(row.default_symbols) ? row.default_symbols.map(String) : undefined,
    universe: value(row, "default_universe", "NSE"), timeframe: value(row, "default_timeframe", "daily"),
    notes: "Applied from the Strategy Arsenal. Paper-first and human approval gates remain mandatory."
  }), `${value(row, "template_name")} added to the Arsenal.`);

  return <div className="strategy-arsenal-workspace">
    <div className="arsenal-masthead">
      <div><span>Strategy lifecycle control</span><h2>Strategy Arsenal</h2><p>Operator ideas · system discovery · independent promotion gates</p></div>
      <div className="arsenal-lock"><ShieldCheck size={17}/><span>Broker execution</span><strong>{value(execution, "global_execution_locked", "true") === "true" ? "LOCKED" : "REVIEW"}</strong></div>
      <button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button"><RefreshCw size={14}/>{status === "loading" ? "Checking" : "Refresh"}</button>
    </div>
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status}/>
    {error ? <div className="error-strip">{error}</div> : null}{notice ? <div className="success-strip">{notice}</div> : null}

    <section className="terminal-metric-strip arsenal-metrics" aria-label="Strategy Arsenal metrics" tabIndex={0}>
      <div><span>Total</span><strong>{metric(snapshot,"total_candidates")}</strong><small>candidate records</small></div>
      <div><span>Operator</span><strong>{metric(snapshot,"operator_submitted")}</strong><small>submitted ideas</small></div>
      <div><span>Discovered</span><strong>{metric(snapshot,"system_discovered")}</strong><small>system sourced</small></div>
      <div><span>Backtested</span><strong>{metric(snapshot,"backtested")}</strong><small>baseline evidence</small></div>
      <div><span>Validated</span><strong>{metric(snapshot,"validation_passed")}</strong><small>independent gate</small></div>
      <div><span>Paper</span><strong>{metric(snapshot,"paper_monitoring")}</strong><small>monitored only</small></div>
      <div><span>Orders</span><strong>{metric(snapshot,"broker_orders_allowed")}</strong><small>must remain zero</small></div>
    </section>

    <section className="dashboard-grid">
      <Panel className="span-5" icon={<Plus size={17}/>} title="Add Strategy Idea">
        <form className="operator-form arsenal-intake-form" onSubmit={submitIntake}>
          <label><span>Name</span><input value={intake.name} onChange={(event)=>setIntake({...intake,name:event.target.value})}/></label>
          <label><span>Family</span><select value={intake.family} onChange={(event)=>setIntake({...intake,family:event.target.value})}><option value="quant">Quant</option><option value="intraday">Intraday</option><option value="options">Options</option><option value="event_driven">Event driven</option><option value="long_short">Long short</option><option value="tactical">Tactical</option></select></label>
          <label><span>Asset</span><select value={intake.assetClass} onChange={(event)=>setIntake({...intake,assetClass:event.target.value})}><option value="equity">Equity</option><option value="index">Index</option><option value="futures">Futures</option><option value="options">Options</option><option value="crypto">Crypto</option><option value="commodity">Commodity</option></select></label>
          <label><span>Timeframe</span><select value={intake.timeframe} onChange={(event)=>setIntake({...intake,timeframe:event.target.value})}><option value="5m">5m</option><option value="15m">15m</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="event_driven">Event driven</option></select></label>
          <label><span>Symbols</span><input placeholder="RELIANCE, NIFTY" value={intake.symbols} onChange={(event)=>setIntake({...intake,symbols:event.target.value})}/></label>
          <label><span>Universe</span><input value={intake.universe} onChange={(event)=>setIntake({...intake,universe:event.target.value})}/></label>
          <label><span>Test engine</span><select value={intake.engineTemplate} onChange={(event)=>setIntake({...intake,engineTemplate:event.target.value})}><option value="momentum">Momentum</option><option value="mean_reversion">Mean reversion</option><option value="breakout">Breakout</option><option value="low_volatility">Low volatility</option></select></label>
          <label><span>Minimum OHLCV rows</span><input inputMode="numeric" min="50" type="number" value={intake.minRows} onChange={(event)=>setIntake({...intake,minRows:event.target.value})}/></label>
          <label><span>Costs (bps)</span><input inputMode="decimal" min="0" step="0.1" type="number" value={intake.costBps} onChange={(event)=>setIntake({...intake,costBps:event.target.value})}/></label>
          <label><span>Slippage (bps)</span><input inputMode="decimal" min="0" step="0.1" type="number" value={intake.slippageBps} onChange={(event)=>setIntake({...intake,slippageBps:event.target.value})}/></label>
          <label className="span-form"><span>Hypothesis and rules</span><textarea required rows={5} value={intake.thesis} onChange={(event)=>setIntake({...intake,thesis:event.target.value})}/></label>
          <label className="span-form"><span>Constraints</span><input value={intake.constraints} onChange={(event)=>setIntake({...intake,constraints:event.target.value})}/></label>
          <label className="span-form"><span>Risk and invalidation</span><input value={intake.risk} onChange={(event)=>setIntake({...intake,risk:event.target.value})}/></label>
          <div className="panel-action-group span-form"><button className="mini-action-button" disabled={Boolean(busy)} type="submit" value="save"><Plus size={15}/>{busy === "intake" ? "Adding" : "Save hypothesis"}</button><button className="primary-button" disabled={Boolean(busy)} type="submit" value="test"><Beaker size={15}/>{busy === "optimizer" ? "Testing" : "Run full research test"}</button></div>
          <p className="form-guard span-form">Testing uses warehouse OHLCV, transaction costs, timestamp-aligned returns, embargoed nested walk-forward selection, cost stress, and Monte Carlo diagnostics. It cannot promote, paper trade, or place an order.</p>
        </form>
      </Panel>

      <Panel className="span-12" icon={<Beaker size={17}/>} title="Operator Test Runs" action={<span>{snapshot?.user_optimizer_runs.length ?? 0} recent</span>}>
        <div className="arsenal-discovery-list scoped-scroll-list">
          {snapshot?.user_optimizer_runs.map((row)=><article className="arsenal-discovery-row" key={value(row,"id")}><div><span>{value(row,"requested_template")} · {value(row,"requested_timeframe")}</span><strong>{value(row,"strategy_name")}</strong><p>{value(row,"requested_symbols", "universe test")} · stage {value(row,"current_stage")} {value(row,"failure_reason","")}</p></div><StatusPill status={value(row,"status","review")}/><div><small>backtest #{value(row,"backtest_run_id","-")}</small><br/><small>optimization #{value(row,"optimization_run_id","-")}</small></div></article>)}
          {!snapshot?.user_optimizer_runs.length?<div className="empty-state">No operator test run has been recorded.</div>:null}
        </div>
      </Panel>

      <Panel className="span-7" icon={<Layers3 size={17}/>} title="Template Library" action={<span>{snapshot?.templates.length ?? 0} active</span>}>
        <div className="arsenal-template-grid scoped-scroll-list">
          {snapshot?.templates.map((row)=><article className="arsenal-template-row" key={value(row,"template_key")}><div><strong>{value(row,"template_name")}</strong><p>{value(row,"entry_rule")} · {value(row,"exit_rule")}</p><small>{value(row,"required_gates")}</small></div><StatusPill status={value(row,"execution_readiness","research")}/><button className="mini-action-button" disabled={Boolean(busy)} onClick={()=>void applyTemplate(row)} type="button"><Plus size={13}/>Add</button></article>)}
        </div>
      </Panel>

      <Panel className="span-12" icon={<FlaskConical size={17}/>} title="Lifecycle Control Board" action={<span>{candidates.length} shown</span>}>
        <div className="arsenal-filter-bar">
          <label><Search size={14}/><input aria-label="Search Strategy Arsenal" placeholder="Strategy, symbol, hypothesis" value={query} onChange={(event)=>setQuery(event.target.value)}/></label>
          <select aria-label="Filter by origin" value={origin} onChange={(event)=>setOrigin(event.target.value)}><option value="all">All origins</option><option value="operator_submitted">Operator</option><option value="system_discovery">System discovery</option><option value="template_library">Templates</option><option value="research_sourced">Research</option><option value="imported_or_other">Imported</option></select>
          <select aria-label="Filter by promotion stage" value={stage} onChange={(event)=>setStage(event.target.value)}><option value="all">All stages</option>{stages.map((item)=><option key={item} value={item}>{item.replace(/_/g," ")}</option>)}</select>
        </div>
        <div className="arsenal-board scoped-scroll-list" tabIndex={0} aria-label="Strategy lifecycle candidates">
          {candidates.map((row)=>{const flags=gateFlags(row);return <article className="arsenal-candidate-row" key={value(row,"candidate_id")}>
            <button className="arsenal-candidate-main" onClick={()=>setEvidence({kind:"strategy",key:value(row,"candidate_id"),title:value(row,"strategy_name"),subtitle:`${value(row,"origin_type")} · ${value(row,"promotion_stage")}`,record:row})} type="button">
              <span className="arsenal-origin">{value(row,"origin_type").replace(/_/g," ")}</span><strong>{value(row,"strategy_name")}</strong><small>{value(row,"symbols",value(row,"universe"))} · {value(row,"timeframe")} · owner {value(row,"owner_agent")}</small><p>{value(row,"next_required_action")}</p>
            </button>
            <div className="arsenal-gates" aria-label={`${value(row,"gates_passed","0")} of ${value(row,"gates_total","8")} gates passed`}>{gateLabels.map(([key,label])=><span className={flags[key]?"gate-pass":"gate-wait"} key={key}>{label}</span>)}</div>
            <div className="arsenal-stage"><StatusPill status={value(row,"promotion_stage","research")}/><strong>{value(row,"gates_passed","0")}/{value(row,"gates_total","8")}</strong><time>{date(row.updated_at)}</time></div>
          </article>;})}
          {!candidates.length?<div className="empty-state">No strategy candidates match the current filters.</div>:null}
        </div>
      </Panel>

      <Panel className="span-12" icon={<Sparkles size={17}/>} title="System Discovery Triage" action={<div className="panel-action-group"><button className="mini-action-button" disabled={Boolean(busy)} onClick={()=>void runDiscovery()} type="button"><Play size={13}/>{busy==="discovery"?"Running":"Run discovery"}</button><button className="mini-action-button" disabled={Boolean(busy)} onClick={()=>void runAction("validation",()=>runModelValidationSweep({actor:"Model Validation Agent",limit:50}),"Validation sweep completed; no execution authority granted.")} type="button"><BookOpenCheck size={13}/>{busy==="validation"?"Running":"Validate gates"}</button></div>}>
        <div className="arsenal-discovery-list scoped-scroll-list">
          {pendingDiscovery.slice(0,40).map((row)=><article className="arsenal-discovery-row" key={value(row,"id")}><div><span>{value(row,"source_kind")}</span><strong>{value(row,"title")}</strong><p>{value(row,"thesis")} · next: {value(row,"next_required_action")}</p></div><span className="arsenal-score">{value(row,"priority_score","-")}</span><div className="arsenal-triage-actions"><button disabled={Boolean(busy)} onClick={()=>void triage(row,"route_quant_lab")} type="button"><Route size={13}/>Quant</button><button disabled={Boolean(busy)} onClick={()=>void triage(row,"request_more_evidence")} type="button"><FileSearch size={13}/>Evidence</button><button disabled={Boolean(busy)} onClick={()=>void triage(row,"reject")} type="button">Reject</button></div></article>)}
          {!pendingDiscovery.length?<div className="empty-state">No unreviewed discovery candidates.</div>:null}
        </div>
      </Panel>
    </section>
    <EvidenceDrawer onChanged={refresh} onClose={()=>setEvidence(null)} selection={evidence}/>
  </div>;
}
