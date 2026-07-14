import {
  Activity,
  Cable,
  CheckCircle2,
  Cpu,
  DatabaseZap,
  FileJson2,
  FileSearch,
  Play,
  Plus,
  RefreshCw,
  Route,
  Search,
  ShieldCheck,
  TimerReset
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { EvidenceSelection } from "../api/evidence";
import {
  checkGatewayModel,
  checkGatewaySource,
  fetchIntegrationGateway,
  registerGatewayModel,
  registerGatewaySource,
  runGatewayJob,
  runGatewayReadiness,
  upsertGatewayJob,
  upsertGatewayMapping,
  validateGatewayMapping,
  type IntegrationGatewaySnapshot
} from "../api/integrationGateway";
import type { LiveRow } from "../api/live";
import EvidenceDrawer from "../components/EvidenceDrawer";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

type ConnectionStatus = "loading" | "online" | "offline";
interface Props { onStatusChange: (status: ConnectionStatus) => void; }

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
  if (typeof raw === "object") return JSON.stringify(raw);
  return String(raw);
}

function metric(snapshot: IntegrationGatewaySnapshot | null, key: string): number {
  return Number(snapshot?.summary.find((row) => value(row, "metric") === key)?.value ?? 0);
}

function tone(status: string): string {
  const normalized = status.toLowerCase();
  if (["ready", "active", "configured", "passed", "completed", "fresh"].some((item) => normalized.includes(item))) return "active";
  if (["blocked", "failed", "error", "critical", "missing", "stale", "credentials"].some((item) => normalized.includes(item))) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${tone(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>;
}

function parseObject(raw: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(raw || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} must be a JSON object`);
  return parsed as Record<string, unknown>;
}

export default function IntegrationGatewayWorkspace({ onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<IntegrationGatewaySnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [gatewayStatus, setGatewayStatus] = useState("all");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [source, setSource] = useState({
    name: "", sourceKey: "", sourceType: "market_data", connectorType: "api_read_only",
    provider: "", baseUrl: "", freshness: "5", secretRef: "", requiresApiKey: false,
    requiresBrowser: false, accessMode: "read_only"
  });
  const [model, setModel] = useState({
    name: "", endpointKey: "", provider: "ollama", modelName: "", routeName: "",
    endpointType: "local", baseUrl: "http://127.0.0.1:11434", contextWindow: "",
    costTier: "local", capabilities: "", secretRef: "", requiresApiKey: false
  });
  const [mapping, setMapping] = useState({
    pluginKey: "", datasetKey: "", targetRelation: "", fieldMappings: "{}",
    primaryKeys: "", timestampField: "", sourceSchema: "{}"
  });
  const [job, setJob] = useState({
    pluginKey: "", name: "", jobType: "poll", executorKey: "public_source_check",
    cron: "", runMode: "manual_or_schedule", timeout: "300", parameters: "{}", enabled: false
  });

  const refresh = useCallback(async () => {
    setStatus("loading"); onStatusChange("loading");
    try {
      const next = await fetchIntegrationGateway();
      setSnapshot(next); setStatus("online"); setError(""); onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Integration Gateway unavailable");
      setStatus("offline"); onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handler = () => void refresh();
    window.addEventListener("aios:integration-gateway-refresh", handler);
    return () => { window.clearInterval(timer); window.removeEventListener("aios:integration-gateway-refresh", handler); };
  }, [refresh]);

  const act = async (key: string, action: () => Promise<unknown>, success: string) => {
    setBusy(key); setError(""); setNotice("");
    try { await action(); setNotice(success); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : `${key} failed`); }
    finally { setBusy(""); }
  };

  const plugins = useMemo(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (snapshot?.plugins ?? []).filter((row) => {
      if (kind !== "all" && value(row, "plugin_kind") !== kind) return false;
      if (gatewayStatus !== "all" && value(row, "gateway_status") !== gatewayStatus) return false;
      if (!tokens.length) return true;
      const haystack = ["display_name", "plugin_key", "provider", "model_name", "source_key"]
        .map((key) => value(row, key, "").toLowerCase().replace(/_/g, " ")).join(" ");
      return tokens.every((token) => haystack.includes(token));
    });
  }, [gatewayStatus, kind, query, snapshot]);
  const dataPlugins = useMemo(() => (snapshot?.plugins ?? []).filter((row) => value(row, "plugin_kind") === "data_source"), [snapshot]);
  const gatewayStatuses = useMemo(() => Array.from(new Set((snapshot?.plugins ?? []).map((row) => value(row, "gateway_status")))).sort(), [snapshot]);
  const execution = snapshot?.execution_control[0];

  const submitSource = (event: FormEvent) => {
    event.preventDefault();
    const sourceKey = source.sourceKey.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    void act("source", () => registerGatewaySource({
      connector_key: `${sourceKey}_connector`, connector_name: source.name,
      source_key: sourceKey, source_name: source.name, source_type: source.sourceType,
      connector_type: source.connectorType, connection_mode: source.connectorType,
      provider: source.provider, base_url: source.baseUrl || undefined,
      access_mode: source.accessMode, status: "configured",
      freshness_target_minutes: source.freshness || undefined,
      requires_api_key: source.requiresApiKey, requires_browser_session: source.requiresBrowser,
      secret_ref: source.secretRef || undefined, owner_agent: "Data Steward", actor: "Devarsh"
    }), "Data-source plug-in registered; mapping and readiness gates now apply.");
  };

  const submitModel = (event: FormEvent) => {
    event.preventDefault();
    const endpointKey = (model.endpointKey || `${model.provider}_${model.modelName}_${model.routeName}`).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    void act("model", () => registerGatewayModel({
      endpoint_key: endpointKey, endpoint_name: model.name || `${model.provider} ${model.modelName}`,
      provider: model.provider, model_name: model.modelName, route_name: model.routeName || undefined,
      endpoint_type: model.endpointType, base_url: model.baseUrl || undefined,
      deployment_target: model.endpointType === "local" ? "local_machine" : "external_provider",
      status: "configured", context_window: model.contextWindow || undefined,
      cost_tier: model.costTier, capabilities: model.capabilities.split(",").map((item) => item.trim()).filter(Boolean),
      requires_api_key: model.requiresApiKey, secret_ref: model.secretRef || undefined,
      owner_agent: "AI Engineering", actor: "Devarsh"
    }), "Model-provider plug-in registered; live probe and route gates now apply.");
  };

  const submitMapping = (event: FormEvent) => {
    event.preventDefault();
    try {
      const fieldMappings = parseObject(mapping.fieldMappings, "Field mappings");
      const sourceSchema = parseObject(mapping.sourceSchema, "Source schema");
      void act("mapping", () => upsertGatewayMapping({
        plugin_key: mapping.pluginKey, dataset_key: mapping.datasetKey,
        target_relation: mapping.targetRelation, field_mappings: fieldMappings,
        source_schema: sourceSchema,
        primary_key_fields: mapping.primaryKeys.split(",").map((item) => item.trim()).filter(Boolean),
        timestamp_field: mapping.timestampField || undefined, status: "configured",
        owner_agent: "Data Steward", actor: "Devarsh"
      }), "Schema contract saved. Run validation before assignment.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Mapping JSON is invalid"); }
  };

  const submitJob = (event: FormEvent) => {
    event.preventDefault();
    try {
      const parameters = parseObject(job.parameters, "Job parameters");
      void act("job", () => upsertGatewayJob({
        plugin_key: job.pluginKey, job_name: job.name,
        job_type: job.jobType as "poll", executor_key: job.executorKey as "public_source_check",
        schedule_cron: job.cron || undefined, enabled: job.enabled,
        run_mode: job.runMode as "manual_or_schedule", timeout_seconds: Number(job.timeout || 300),
        parameters, approval_required: false, owner_agent: "Data Engineering Agent", actor: "Devarsh"
      }), "Bounded integration job saved.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Job parameters JSON is invalid"); }
  };

  const checkPlugin = (row: LiveRow) => act(`check-${value(row, "plugin_key")}`,
    () => value(row, "plugin_kind") === "model_provider" ? checkGatewayModel(value(row, "target_key")) : checkGatewaySource(value(row, "target_key")),
    "Plug-in health check completed.");

  return <div className="integration-gateway-workspace">
    <section className="gateway-masthead">
      <div><span>Integration control plane</span><h2>Data &amp; Model Gateway</h2><p>Source adapters · schema contracts · bounded jobs · model routes</p></div>
      <div className="gateway-policy"><ShieldCheck size={16}/><span>Secrets / broker</span><strong>REFERENCES ONLY · {value(execution,"global_execution_locked","true") === "true" ? "LOCKED" : "CHECK"}</strong></div>
      <button className="mini-action-button" disabled={status === "loading"} onClick={()=>void refresh()} type="button"><RefreshCw size={14}/>Refresh</button>
    </section>
    <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status}/>
    {error?<div className="error-strip">{error}</div>:null}{notice?<div className="success-strip">{notice}</div>:null}

    <section className="terminal-metric-strip gateway-metrics" aria-label="Integration Gateway metrics" tabIndex={0}>
      <div><span>Plug-ins</span><strong>{metric(snapshot,"total_plugins")}</strong><small>auto synchronized</small></div>
      <div><span>Sources</span><strong>{metric(snapshot,"data_source_plugins")}</strong><small>data adapters</small></div>
      <div><span>Models</span><strong>{metric(snapshot,"model_provider_plugins")}</strong><small>provider endpoints</small></div>
      <div><span>Ready</span><strong>{metric(snapshot,"ready_plugins")}</strong><small>role assignable</small></div>
      <div><span>Credentials</span><strong>{metric(snapshot,"needs_credentials")}</strong><small>reference missing</small></div>
      <div><span>Mappings</span><strong>{metric(snapshot,"needs_mapping")}</strong><small>contracts missing</small></div>
      <div><span>Freshness</span><strong>{metric(snapshot,"needs_freshness")}</strong><small>SLA blocked</small></div>
      <div><span>Commands</span><strong>0</strong><small>arbitrary allowed</small></div>
    </section>

    <section className="dashboard-grid">
      <Panel className="span-6" icon={<DatabaseZap size={17}/>} title="Register Data Source">
        <form className="gateway-form" onSubmit={submitSource}>
          <label><span>Name</span><input required value={source.name} onChange={(event)=>setSource({...source,name:event.target.value})}/></label>
          <label><span>Source key</span><input required value={source.sourceKey} onChange={(event)=>setSource({...source,sourceKey:event.target.value})}/></label>
          <label><span>Source type</span><input required value={source.sourceType} onChange={(event)=>setSource({...source,sourceType:event.target.value})}/></label>
          <label><span>Adapter</span><select value={source.connectorType} onChange={(event)=>setSource({...source,connectorType:event.target.value})}><option value="api_read_only">API read only</option><option value="rss_http">RSS / HTTP</option><option value="browser_agent">Browser agent</option><option value="file_import">File import</option><option value="database_read_only">Database read only</option><option value="custom_adapter">Custom adapter</option></select></label>
          <label><span>Provider</span><input required value={source.provider} onChange={(event)=>setSource({...source,provider:event.target.value})}/></label>
          <label><span>Freshness minutes</span><input min="1" type="number" value={source.freshness} onChange={(event)=>setSource({...source,freshness:event.target.value})}/></label>
          <label className="span-form"><span>Base URL</span><input value={source.baseUrl} onChange={(event)=>setSource({...source,baseUrl:event.target.value})}/></label>
          <label className="span-form"><span>Credential reference</span><input placeholder="env:PROVIDER_API_KEY" value={source.secretRef} onChange={(event)=>setSource({...source,secretRef:event.target.value})}/></label>
          <label className="gateway-toggle"><input checked={source.requiresApiKey} onChange={(event)=>setSource({...source,requiresApiKey:event.target.checked})} type="checkbox"/><span>API credential required</span></label>
          <label className="gateway-toggle"><input checked={source.requiresBrowser} onChange={(event)=>setSource({...source,requiresBrowser:event.target.checked})} type="checkbox"/><span>Browser session required</span></label>
          <button className="primary-button span-form" disabled={Boolean(busy)} type="submit"><Plus size={14}/>{busy==="source"?"Registering":"Register source"}</button>
        </form>
      </Panel>

      <Panel className="span-6" icon={<Cpu size={17}/>} title="Register Model Provider">
        <form className="gateway-form" onSubmit={submitModel}>
          <label><span>Name</span><input value={model.name} onChange={(event)=>setModel({...model,name:event.target.value})}/></label>
          <label><span>Endpoint key</span><input value={model.endpointKey} onChange={(event)=>setModel({...model,endpointKey:event.target.value})}/></label>
          <label><span>Provider</span><input required value={model.provider} onChange={(event)=>setModel({...model,provider:event.target.value})}/></label>
          <label><span>Model</span><input required value={model.modelName} onChange={(event)=>setModel({...model,modelName:event.target.value})}/></label>
          <label><span>Route</span><select required value={model.routeName} onChange={(event)=>setModel({...model,routeName:event.target.value})}><option value="">Select route</option>{snapshot?.model_routes.map((row)=><option key={value(row,"route_name")} value={value(row,"route_name")}>{value(row,"route_name")}</option>)}</select></label>
          <label><span>Endpoint type</span><select value={model.endpointType} onChange={(event)=>setModel({...model,endpointType:event.target.value})}><option value="local">Local</option><option value="cloud_or_external">Cloud / external</option><option value="deterministic">Deterministic</option></select></label>
          <label className="span-form"><span>Base URL</span><input value={model.baseUrl} onChange={(event)=>setModel({...model,baseUrl:event.target.value})}/></label>
          <label><span>Context window</span><input min="1" type="number" value={model.contextWindow} onChange={(event)=>setModel({...model,contextWindow:event.target.value})}/></label>
          <label><span>Cost tier</span><select value={model.costTier} onChange={(event)=>setModel({...model,costTier:event.target.value})}><option value="local">Local</option><option value="local_plus">Local plus</option><option value="hybrid">Hybrid</option><option value="cloud">Cloud</option></select></label>
          <label className="span-form"><span>Capabilities</span><input placeholder="research, reasoning, code" value={model.capabilities} onChange={(event)=>setModel({...model,capabilities:event.target.value})}/></label>
          <label className="span-form"><span>Credential reference</span><input placeholder="keychain:provider/model" value={model.secretRef} onChange={(event)=>setModel({...model,secretRef:event.target.value})}/></label>
          <label className="gateway-toggle span-form"><input checked={model.requiresApiKey} onChange={(event)=>setModel({...model,requiresApiKey:event.target.checked})} type="checkbox"/><span>Cloud credential required</span></label>
          <button className="primary-button span-form" disabled={Boolean(busy)} type="submit"><Plus size={14}/>{busy==="model"?"Registering":"Register model"}</button>
        </form>
      </Panel>

      <Panel className="span-12" icon={<Cable size={17}/>} title="Plug-in Readiness Board" action={<button className="mini-action-button" disabled={Boolean(busy)} onClick={()=>void act("sweep",()=>runGatewayReadiness({run_key:`gateway_${Date.now()}`,actor:"Jarvis"}),"Provider readiness sweep completed.")} type="button"><Activity size={13}/>{busy==="sweep"?"Checking":"Sweep all"}</button>}>
        <div className="gateway-filter-bar"><label><Search size={14}/><input aria-label="Search integration plugins" placeholder="Provider, model, source or key" value={query} onChange={(event)=>setQuery(event.target.value)}/></label><select aria-label="Filter plugin kind" value={kind} onChange={(event)=>setKind(event.target.value)}><option value="all">All plug-ins</option><option value="data_source">Data sources</option><option value="model_provider">Models</option></select><select aria-label="Filter gateway status" value={gatewayStatus} onChange={(event)=>setGatewayStatus(event.target.value)}><option value="all">All states</option>{gatewayStatuses.map((item)=><option key={item} value={item}>{item.replace(/_/g," ")}</option>)}</select></div>
        <div className="gateway-plugin-table" role="region" tabIndex={0} aria-label="Integration plug-in readiness">
          <div className="gateway-plugin-head"><span>Plug-in</span><span>Capabilities / contract</span><span>Gates</span><span>Status</span><span>Actions</span></div>
          {plugins.map((row)=><article className="gateway-plugin-row" key={value(row,"plugin_key")}><button className="gateway-plugin-main" onClick={()=>setEvidence({kind:"integration",key:value(row,"plugin_key"),title:value(row,"display_name"),subtitle:value(row,"next_required_action"),record:row})} type="button"><span>{value(row,"plugin_kind").replace(/_/g," ")}</span><strong>{value(row,"display_name")}</strong><small>{value(row,"provider")} · {value(row,"adapter_key")}</small></button><div><strong>{value(row,"model_name",value(row,"source_type"))}</strong><small>{value(row,"capabilities")} · {value(row,"access_mode")}</small></div><div className="gateway-gates"><span>M {value(row,"valid_mapping_count","0")}/{value(row,"mapping_count","0")}</span><span>J {value(row,"enabled_job_count","0")}/{value(row,"job_count","0")}</span><span>R {value(row,"route_count","0")}</span></div><div><StatusPill status={value(row,"gateway_status")}/><small>{value(row,"next_required_action")}</small></div><div className="gateway-row-actions"><button aria-label={`Inspect ${value(row,"display_name")} evidence`} onClick={()=>setEvidence({kind:"integration",key:value(row,"plugin_key"),title:value(row,"display_name"),subtitle:value(row,"next_required_action"),record:row})} title="Inspect evidence" type="button"><FileSearch size={14}/></button><button aria-label={`Check ${value(row,"display_name")}`} disabled={Boolean(busy)} onClick={()=>void checkPlugin(row)} title="Run health check" type="button"><RefreshCw size={14}/></button></div></article>)}
        </div>
      </Panel>

      <Panel className="span-6" icon={<FileJson2 size={17}/>} title="Schema Mapping">
        <form className="gateway-form" onSubmit={submitMapping}>
          <label className="span-form"><span>Data plug-in</span><select required value={mapping.pluginKey} onChange={(event)=>setMapping({...mapping,pluginKey:event.target.value})}><option value="">Select source</option>{dataPlugins.map((row)=><option key={value(row,"plugin_key")} value={value(row,"plugin_key")}>{value(row,"display_name")}</option>)}</select></label>
          <label><span>Dataset key</span><input required value={mapping.datasetKey} onChange={(event)=>setMapping({...mapping,datasetKey:event.target.value})}/></label>
          <label><span>Target relation</span><input placeholder="trading.ohlcv" required value={mapping.targetRelation} onChange={(event)=>setMapping({...mapping,targetRelation:event.target.value})}/></label>
          <label className="span-form"><span>Field mappings JSON</span><textarea required rows={4} value={mapping.fieldMappings} onChange={(event)=>setMapping({...mapping,fieldMappings:event.target.value})}/></label>
          <label><span>Idempotency fields</span><input placeholder="symbol, ts" required value={mapping.primaryKeys} onChange={(event)=>setMapping({...mapping,primaryKeys:event.target.value})}/></label>
          <label><span>Timestamp field</span><input value={mapping.timestampField} onChange={(event)=>setMapping({...mapping,timestampField:event.target.value})}/></label>
          <button className="primary-button span-form" disabled={Boolean(busy)} type="submit"><Plus size={14}/>{busy==="mapping"?"Saving":"Save mapping"}</button>
        </form>
        <div className="gateway-compact-list">{snapshot?.schema_mappings.map((row)=><article key={value(row,"mapping_key")}><div><strong>{value(row,"dataset_key")}</strong><small>{value(row,"plugin_name")} → {value(row,"target_relation")}</small></div><StatusPill status={value(row,"validation_status")}/><button aria-label={`Validate ${value(row,"mapping_key")}`} disabled={Boolean(busy)} onClick={()=>void act(`mapping-${value(row,"mapping_key")}`,()=>validateGatewayMapping(value(row,"mapping_key")),"Schema mapping validation completed.")} title="Validate mapping" type="button"><CheckCircle2 size={14}/></button></article>)}</div>
      </Panel>

      <Panel className="span-6" icon={<TimerReset size={17}/>} title="Bounded Ingestion Jobs">
        <form className="gateway-form" onSubmit={submitJob}>
          <label className="span-form"><span>Plug-in</span><select required value={job.pluginKey} onChange={(event)=>setJob({...job,pluginKey:event.target.value})}><option value="">Select source</option>{dataPlugins.map((row)=><option key={value(row,"plugin_key")} value={value(row,"plugin_key")}>{value(row,"display_name")}</option>)}</select></label>
          <label><span>Job name</span><input required value={job.name} onChange={(event)=>setJob({...job,name:event.target.value})}/></label>
          <label><span>Executor</span><select value={job.executorKey} onChange={(event)=>setJob({...job,executorKey:event.target.value})}><option value="public_source_check">Public source check</option><option value="market_news_ingestion">Market news ingestion</option><option value="filings_collection">Filings collection</option><option value="tick_ohlcv_aggregation">Tick aggregation</option><option value="tradingview_quote_refresh">TradingView quote refresh</option><option value="provider_readiness">Provider readiness</option></select></label>
          <label><span>Schedule</span><input placeholder="*/15 * * * *" value={job.cron} onChange={(event)=>setJob({...job,cron:event.target.value})}/></label>
          <label><span>Timeout seconds</span><input min="5" max="3600" type="number" value={job.timeout} onChange={(event)=>setJob({...job,timeout:event.target.value})}/></label>
          <label className="span-form"><span>Parameters JSON</span><textarea rows={3} value={job.parameters} onChange={(event)=>setJob({...job,parameters:event.target.value})}/></label>
          <label className="gateway-toggle span-form"><input checked={job.enabled} onChange={(event)=>setJob({...job,enabled:event.target.checked})} type="checkbox"/><span>Enable after configuration review</span></label>
          <button className="primary-button span-form" disabled={Boolean(busy)} type="submit"><Plus size={14}/>{busy==="job"?"Saving":"Save job"}</button>
        </form>
        <div className="gateway-compact-list">{snapshot?.jobs.map((row)=><article key={value(row,"job_key")}><div><strong>{value(row,"job_name")}</strong><small>{value(row,"executor_key")} · {value(row,"schedule_cron","manual")} · {value(row,"last_run_status","never run")}</small></div><StatusPill status={value(row,"enabled") === "true" ? "active" : "disabled"}/><button aria-label={`Run ${value(row,"job_name")}`} disabled={Boolean(busy) || value(row,"enabled")!=="true"} onClick={()=>void act(`job-${value(row,"job_key")}`,()=>runGatewayJob(value(row,"job_key")),"Integration job completed and persisted.")} title="Run job now" type="button"><Play size={14}/></button></article>)}</div>
      </Panel>

      <Panel className="span-12" icon={<Route size={17}/>} title="Model Route Matrix" action={<span>{snapshot?.model_routes.length ?? 0} routes</span>}>
        <div className="gateway-route-grid">{snapshot?.model_routes.map((row)=><article key={value(row,"route_name")}><span>{value(row,"task_class")}</span><strong>{value(row,"route_name")}</strong><p>{value(row,"default_provider")} / {value(row,"default_model")}</p><small>escalate {value(row,"escalation_provider","none")} · ceiling {value(row,"max_cost_tier")}</small></article>)}</div>
      </Panel>
    </section>
    <EvidenceDrawer onChanged={refresh} onClose={()=>setEvidence(null)} selection={evidence}/>
  </div>;
}
