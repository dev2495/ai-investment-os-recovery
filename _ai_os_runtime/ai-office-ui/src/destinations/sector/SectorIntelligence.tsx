import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Activity, BarChart3, Database, Gavel, Layers, LineChart,
  ShieldCheck, Workflow, RefreshCw, Upload, FileCheck2,
} from "lucide-react";
import { useSectorIntelligence } from "../../data/queries";
import { useImportSectorIntelligencePackage, useRunSectorIntelligence } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Badge, Button, DataTable, Empty, Field, Metric, MetricTile, Panel, Select, Skeleton, StatusPill, Tabs, TextArea, TextInput,
} from "../../system/primitives";
import { formatCompact, formatRelative, num, text } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "overview", label: "Overview", icon: Layers },
  { key: "indices", label: "Custom Indices", icon: LineChart },
  { key: "flows", label: "Flows & Strength", icon: Activity },
  { key: "committee", label: "Committee", icon: Gavel },
];

export default function SectorIntelligence() {
  const location = useLocation();
  const navigate = useNavigate();
  const parts = location.pathname.split("/").filter(Boolean); const tab = parts[parts.length - 1] ?? "overview";
  const query = useSectorIntelligence();
  const data = query.data;

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Layers size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Sector Intelligence
          </div>
          <Badge tone="accent">SECT</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
            deterministic taxonomy, indices, breadth, flows and committee work
          </span>
        </div>
        <div className="aios-destination__subtitle">
          Postgres owns classifications, constituents, weights, calculations and history. TradingView Desktop receives chart artifacts only.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={(key) => navigate(`/sector/${key}`)} />
      </div>
      <SectorRunControl indices={data?.custom_indices ?? []} />
      {tab === "overview" ? <SectorSourceImportControl /> : null}


      {query.isLoading ? <Loading /> : null}
      {query.isError ? (
        <Panel icon={Database} title="Sector warehouse unavailable">
          <Empty icon={Database} title="Cannot read Sector Intelligence" description={query.error.message} />
        </Panel>
      ) : null}
      {!query.isLoading && !query.isError && tab === "overview" ? <Overview data={data} /> : null}
      {!query.isLoading && !query.isError && tab === "indices" ? <Indices data={data} /> : null}
      {!query.isLoading && !query.isError && tab === "flows" ? <Flows data={data} /> : null}
      {!query.isLoading && !query.isError && tab === "committee" ? <Committee data={data} /> : null}
    </div>
  );
}

function SectorSourceImportControl() {
  const mutation = useImportSectorIntelligencePackage();
  const pushToast = useUIStore((state) => state.pushToast);
  const [packageText, setPackageText] = React.useState("");
  const [fileName, setFileName] = React.useState("");
  const [mode, setMode] = React.useState<"validate" | "persist">("validate");
  const parsed = React.useMemo(() => {
    if (!packageText.trim()) return { value: null as Record<string, unknown> | null, error: "" };
    try {
      const value = JSON.parse(packageText);
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        return { value: null, error: "Package root must be a JSON object." };
      }
      return { value: value as Record<string, unknown>, error: "" };
    } catch (error) {
      return { value: null, error: error instanceof Error ? error.message : "Invalid JSON." };
    }
  }, [packageText]);

  function submit() {
    if (!parsed.value) return;
    mutation.mutate({ package: parsed.value, persist: mode === "persist", actor: "Devarsh" }, {
      onSuccess: (result) => pushToast({
        title: mode === "persist" ? "Sector package imported" : "Sector package validated",
        message: text(result, "package_hash", text(result, "status", "completed")),
        tone: "ok",
        duration: 5000,
      }),
      onError: (error) => pushToast({ title: "Sector package rejected", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  return (
    <Panel
      icon={Upload}
      title="Import Sector Evidence Package"
      actions={<Badge tone={mutation.isError ? "risk" : mutation.isSuccess ? "ok" : "accent"}>{mutation.isPending ? "Checking" : fileName || "JSON"}</Badge>}
    >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "var(--space-3)", alignItems: "start" }}>
        <Field label="Evidence package" hint="Taxonomy, effective memberships, metrics and custom indices are validated as one transaction." required>
          <TextArea rows={8} value={packageText} onChange={(event) => setPackageText(event.target.value)} placeholder='{"source": {...}, "taxonomy": [...], "memberships": [...], "metrics": [...], "indices": [...]}' />
        </Field>
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          <Field label="Load JSON file">
            <input
              className="aios-input"
              type="file"
              accept="application/json,.json"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                setFileName(file.name);
                setPackageText(await file.text());
              }}
            />
          </Field>
          <Field label="Operation" required>
            <Select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
              <option value="validate">Validate only</option>
              <option value="persist">Import validated package</option>
            </Select>
          </Field>
          <Button variant="primary" icon={FileCheck2} onClick={submit} disabled={!parsed.value || mutation.isPending}>
            {mutation.isPending ? "Validating…" : mode === "persist" ? "Validate and import" : "Validate package"}
          </Button>
        </div>
      </div>
      {parsed.error ? <div role="alert" style={{ color: "var(--status-risk)", fontSize: "var(--text-sm)", marginTop: "var(--space-2)" }}>{parsed.error}</div> : null}
      {mutation.isError ? <div role="alert" style={{ color: "var(--status-risk)", fontSize: "var(--text-sm)", marginTop: "var(--space-2)" }}>{mutation.error.message}</div> : null}
      {mutation.isSuccess ? <div role="status" style={{ color: "var(--status-ok)", fontSize: "var(--text-sm)", marginTop: "var(--space-2)" }}>{text(mutation.data, "status")} · {text(mutation.data, "package_hash")}</div> : null}
    </Panel>
  );
}

function SectorRunControl({ indices }: { indices: LiveRow[] }) {
  const mutation = useRunSectorIntelligence();
  const pushToast = useUIStore((state) => state.pushToast);
  const [form, setForm] = React.useState({
    index_id: "",
    as_of_date: new Date().toISOString().slice(0, 10),
    horizon: "1M" as "1D" | "1W" | "1M" | "3M" | "6M" | "1Y",
    mode: "dry_run",
  });

  React.useEffect(() => {
    if (!form.index_id && indices.length > 0) {
      setForm((current) => ({ ...current, index_id: text(indices[0], "index_id") }));
    }
  }, [form.index_id, indices]);

  const ready = Boolean(Number(form.index_id) > 0 && form.as_of_date);

  function run() {
    if (!ready) return;
    mutation.mutate({
      index_id: Number(form.index_id),
      as_of_date: form.as_of_date,
      horizon: form.horizon,
      dry_run: form.mode === "dry_run",
      actor: "Devarsh",
    }, {
      onSuccess: (result) => pushToast({
        title: form.mode === "dry_run" ? "Sector calculation validated" : "Sector index records refreshed",
        message: text(result, "status", "completed"),
        tone: "ok",
        duration: 4500,
      }),
      onError: (error) => pushToast({ title: "Sector engine failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  return (
    <Panel
      icon={RefreshCw}
      title="Run Sector Intelligence Engine"
      actions={<Badge tone={mutation.isPending ? "warn" : mutation.isError ? "risk" : mutation.isSuccess ? "ok" : "accent"}>{mutation.isPending ? "Running" : mutation.isError ? "Failed" : mutation.isSuccess ? "Complete" : "Operator"}</Badge>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
        <Field label="Custom index" required>
          <Select value={form.index_id} onChange={(event) => setForm({ ...form, index_id: event.target.value })}>
            <option value="">Select validated definition…</option>
            {indices.map((row, index) => <option key={text(row, "index_id", String(index))} value={text(row, "index_id")}>{text(row, "index_name", text(row, "index_key"))}</option>)}
          </Select>
        </Field>
        <Field label="As-of date" required><TextInput type="date" value={form.as_of_date} onChange={(event) => setForm({ ...form, as_of_date: event.target.value })} /></Field>
        <Field label="Strength horizon" required><Select value={form.horizon} onChange={(event) => setForm({ ...form, horizon: event.target.value as typeof form.horizon })}><option value="1D">1 day</option><option value="1W">1 week</option><option value="1M">1 month</option><option value="3M">3 months</option><option value="6M">6 months</option><option value="1Y">1 year</option></Select></Field>
        <Field label="Run mode" required><Select value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value })}><option value="dry_run">Dry run — calculate only</option><option value="persist">Persist validated analytics</option></Select></Field>
        <Button variant="primary" icon={RefreshCw} onClick={run} disabled={!ready || mutation.isPending}>{mutation.isPending ? "Running…" : form.mode === "dry_run" ? "Validate index" : "Run index"}</Button>
      </div>
      <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
        Uses effective-dated memberships and source-backed prices. Outputs are warehouse calculations and TradingView chart handoffs only; no broker execution is available.
      </div>
      {indices.length === 0 ? <div role="status" style={{ marginTop: "var(--space-3)", color: "var(--status-warn)", fontSize: "var(--text-sm)" }}>Create and validate a custom-index definition before running the engine.</div> : null}
      {mutation.isError ? <div role="alert" style={{ marginTop: "var(--space-3)", color: "var(--status-risk)", fontSize: "var(--text-sm)" }}>{mutation.error.message}</div> : null}
      {mutation.isSuccess ? <div role="status" style={{ marginTop: "var(--space-3)", color: "var(--status-ok)", fontSize: "var(--text-sm)" }}>{text(mutation.data, "status", "Completed")} · {text(mutation.data, "input_fingerprint", text(mutation.data, "message", form.mode === "dry_run" ? "No records were written." : "Validated analytics were persisted."))}</div> : null}
    </Panel>
  );
}

function Loading() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
      {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} height={140} />)}
    </div>
  );
}

function Overview({ data }: { data: ReturnType<typeof useSectorIntelligence>["data"] }) {
  const hierarchy = data?.hierarchy ?? [];
  const freshness = data?.freshness ?? [];
  const rankings = data?.rankings ?? [];
  const imports = data?.source_import_runs ?? [];
  const sectors = new Set(hierarchy.map((row) => text(row, "sector_key")).filter(Boolean)).size;
  const industries = new Set(hierarchy.map((row) => text(row, "industry_key")).filter(Boolean)).size;
  const stale = freshness.filter((row) =>
    !text(row, "latest_metric_at") || !text(row, "latest_market_monitor_at")
  ).length;

  return (
    <>
      <MetricStrip values={[
        ["Sectors", sectors],
        ["Industries", industries],
        ["Rankings", rankings.length],
        ["Coverage gaps", stale],
      ]} />
      <Panel icon={Workflow} title="Indian Sector Taxonomy" actions={<Badge dot>{hierarchy.length}</Badge>}>
        {hierarchy.length === 0 ? (
          <Empty icon={Workflow} title="No taxonomy ingested" description="Load source-backed Indian sector classifications and effective-dated memberships. No sample constituents are generated." />
        ) : (
          <DataTable rows={hierarchy} rowKey={(row, index) => text(row, "sub_industry_key", text(row, "industry_key", text(row, "sector_key", String(index))))} columns={[
            { key: "sector", header: "Sector", render: (row) => <strong>{text(row, "sector_name")}</strong> },
            { key: "industry", header: "Industry", render: (row) => text(row, "industry_name", "—") },
            { key: "sub", header: "Sub-industry", render: (row) => text(row, "sub_industry_name", "—") },
            { key: "from", header: "Effective", render: (row) => text(row, "valid_from", "—") },
            { key: "to", header: "Until", render: (row) => text(row, "valid_to", "Current") },
          ]} />
        )}
      </Panel>
      <Panel icon={Database} title="Data Freshness">
        {freshness.length === 0 ? (
          <Empty icon={Database} title="No sector observations" description="Financial, market, ownership and research observations have not been loaded into the deterministic warehouse." />
        ) : (
          <DataTable rows={freshness} rowKey={(row, index) => text(row, "taxonomy_key", String(index))} columns={[
            { key: "node", header: "Sector / Industry", render: (row) => <strong>{text(row, "node_name")}</strong> },
            { key: "metrics", header: "Financial metrics", render: (row) => freshnessCell(row, "latest_metric_at") },
            { key: "market", header: "Market monitor", render: (row) => freshnessCell(row, "latest_market_monitor_at") },
            { key: "flows", header: "Flows", render: (row) => freshnessCell(row, "latest_flow_at") },
            { key: "research", header: "Research", render: (row) => freshnessCell(row, "latest_research_review_at") },
          ]} />
        )}
      </Panel>
      <Panel icon={FileCheck2} title="Source Import Ledger" actions={<Badge dot>{imports.length}</Badge>}>
        {imports.length === 0 ? (
          <Empty icon={FileCheck2} title="No sector package imported" description="Use the evidence-package control above. Validation never creates sample taxonomy or constituents." />
        ) : (
          <DataTable rows={imports} rowKey={(row, index) => text(row, "run_key", String(index))} columns={[
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status")} /> },
            { key: "source", header: "Evidence", render: (row) => text(row, "source_artifact_ref") },
            { key: "taxonomy", header: "Taxonomy", align: "right", render: (row) => num(row, "taxonomy_rows") },
            { key: "members", header: "Memberships", align: "right", render: (row) => num(row, "membership_rows") },
            { key: "metrics", header: "Metrics", align: "right", render: (row) => num(row, "metric_rows") },
            { key: "indices", header: "Indices", align: "right", render: (row) => num(row, "index_rows") },
            { key: "when", header: "Imported", render: (row) => formatRelative(text(row, "imported_at")) },
          ]} />
        )}
      </Panel>
    </>
  );
}

function Indices({ data }: { data: ReturnType<typeof useSectorIntelligence>["data"] }) {
  const indices = data?.custom_indices ?? [];
  const artifacts = data?.chart_artifacts ?? [];
  return (
    <>
      <MetricStrip values={[
        ["Defined indices", indices.length],
        ["Active", indices.filter((row) => text(row, "status") === "active").length],
        ["Chart artifacts", artifacts.length],
        ["Broker authority", 0],
      ]} />
      <Panel icon={LineChart} title="Point-In-Time Custom Indices">
        {indices.length === 0 ? (
          <Empty icon={LineChart} title="No custom indices calculated" description="Create an index definition, validate effective-dated constituents, calculate weights, and reconcile history before activation." />
        ) : (
          <DataTable rows={indices} rowKey={(row, index) => text(row, "index_key", String(index))} columns={[
            { key: "index", header: "Index", render: (row) => <strong>{text(row, "index_name")}</strong> },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "draft")} /> },
            { key: "weighting", header: "Weighting", render: (row) => text(row, "weighting_method") },
            { key: "members", header: "Constituents", align: "right", render: (row) => num(row, "current_constituent_count") },
            { key: "level", header: "Latest level", align: "right", render: (row) => formatCompact(num(row, "latest_index_value")) },
            { key: "rebalance", header: "Last rebalance", render: (row) => text(row, "latest_rebalance_date", "—") },
          ]} />
        )}
      </Panel>
      <Panel icon={BarChart3} title="TradingView Desktop Handoffs">
        {artifacts.length === 0 ? (
          <Empty icon={BarChart3} title="No chart artifacts generated" description="Formula, Pine and layout artifacts appear only after deterministic index inputs pass validation." />
        ) : (
          <DataTable rows={artifacts} rowKey={(row, index) => text(row, "artifact_key", String(index))} columns={[
            { key: "type", header: "Artifact", render: (row) => text(row, "artifact_type") },
            { key: "target", header: "Workspace", render: (row) => text(row, "target_workspace") },
            { key: "asof", header: "Source as of", render: (row) => freshnessCell(row, "source_as_of") },
            { key: "version", header: "Calculation", render: (row) => text(row, "calculation_version") },
            { key: "generated", header: "Generated", render: (row) => freshnessCell(row, "generated_at") },
          ]} />
        )}
      </Panel>
    </>
  );
}

function Flows({ data }: { data: ReturnType<typeof useSectorIntelligence>["data"] }) {
  const flows = data?.flows ?? [];
  const rankings = data?.rankings ?? [];
  const aggregates = data?.aggregates ?? [];
  const bands = data?.valuation_bands ?? [];
  return (
    <>
      <MetricStrip values={[
        ["Flow observations", flows.length],
        ["Strength ranks", rankings.length],
        ["Aggregates", aggregates.length],
        ["Valuation bands", bands.length],
      ]} />
      <Panel icon={Activity} title="Institutional And Ownership Flows">
        {flows.length === 0 ? (
          <Empty icon={Activity} title="No source-backed flows" description="FII, DII, mutual-fund, promoter, insider, bulk/block and derivative flow observations have not been ingested." />
        ) : (
          <DataTable rows={flows} rowKey={(row, index) => `${text(row, "observed_at")}:${index}`} columns={[
            { key: "time", header: "Observed", render: (row) => freshnessCell(row, "observed_at") },
            { key: "actor", header: "Actor", render: (row) => <strong>{text(row, "flow_actor")}</strong> },
            { key: "type", header: "Flow", render: (row) => text(row, "flow_type") },
            { key: "net", header: "Net", align: "right", render: (row) => formatCompact(num(row, "net_value"), text(row, "currency", "INR")) },
            { key: "source", header: "Source", render: (row) => text(row, "source_reference", "Warehouse lineage") },
          ]} />
        )}
      </Panel>
      <Panel icon={BarChart3} title="Relative Strength And Classification">
        {rankings.length === 0 ? (
          <Empty icon={BarChart3} title="No ranks calculated" description="Ranks require point-in-time sector membership and complete price/metric inputs; missing inputs are not imputed." />
        ) : (
          <DataTable rows={rankings} rowKey={(row, index) => text(row, "ranking_key", String(index))} columns={[
            { key: "type", header: "Ranking", render: (row) => text(row, "ranking_type") },
            { key: "horizon", header: "Horizon", render: (row) => text(row, "horizon") },
            { key: "rank", header: "Rank", align: "right", render: (row) => `${num(row, "rank_value")} / ${num(row, "universe_size")}` },
            { key: "score", header: "Score", align: "right", render: (row) => num(row, "score").toFixed(2) },
            { key: "asof", header: "As of", render: (row) => text(row, "as_of_date") },
          ]} />
        )}
      </Panel>
    </>
  );
}

function Committee({ data }: { data: ReturnType<typeof useSectorIntelligence>["data"] }) {
  const committee = data?.committee ?? [];
  const mandates = data?.portfolio_manager ?? [];
  const execution = data?.execution_control?.[0];
  return (
    <>
      <MetricStrip values={[
        ["Open packets", committee.filter((row) => !["decided", "closed"].includes(text(row, "status"))).length],
        ["PM mandates", mandates.length],
        ["Human final required", committee.filter((row) => text(row, "human_final_required") === "true").length],
        ["Broker writes", execution && text(execution, "live_broker_writes_allowed") === "true" ? 1 : 0],
      ]} />
      <Panel icon={ShieldCheck} title="Sector Portfolio Manager Mandates">
        {mandates.length === 0 ? (
          <Empty icon={ShieldCheck} title="No active sector mandate" description="Mandates require an explicit benchmark, eligible sector scope, risk limits and human approval policy." />
        ) : (
          <DataTable rows={mandates} rowKey={(row, index) => text(row, "mandate_key", String(index))} columns={[
            { key: "mandate", header: "Mandate", render: (row) => <strong>{text(row, "mandate_name")}</strong> },
            { key: "manager", header: "Manager", render: (row) => text(row, "manager_agent") },
            { key: "benchmark", header: "Benchmark", render: (row) => text(row, "benchmark_index_key", "Not assigned") },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status")} /> },
            { key: "packets", header: "Open packets", align: "right", render: (row) => num(row, "open_committee_packets") },
          ]} />
        )}
      </Panel>
      <Panel icon={Gavel} title="Sector Committee">
        {committee.length === 0 ? (
          <Empty icon={Gavel} title="No committee packets" description="A packet opens only from a source-backed sector underwrite. Capital action remains false until Devarsh decides separately." />
        ) : (
          <DataTable rows={committee} rowKey={(row, index) => text(row, "packet_key", String(index))} columns={[
            { key: "sector", header: "Sector", render: (row) => <strong>{text(row, "sector_name")}</strong> },
            { key: "question", header: "Decision question", render: (row) => text(row, "decision_question") },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status")} /> },
            { key: "asof", header: "As of", render: (row) => text(row, "as_of_date") },
            { key: "updated", header: "Updated", render: (row) => freshnessCell(row, "updated_at") },
          ]} />
        )}
      </Panel>
    </>
  );
}

function MetricStrip({ values }: { values: Array<[string, string | number]> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
      {values.map(([label, value]) => <MetricTile key={label}><Metric label={label} value={value} /></MetricTile>)}
    </div>
  );
}

function freshnessCell(row: LiveRow, key: string) {
  const value = text(row, key);
  return value ? <span title={value}>{formatRelative(value)}</span> : <span style={{ color: "var(--text-muted)" }}>Not available</span>;
}
