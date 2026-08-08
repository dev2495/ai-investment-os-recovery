/**
 * Institutional Options Desk beta.
 *
 * Routes: /options/desk | /chain | /surface | /oi-analysis | /strategies | /agent
 *
 * Calculated analytics are displayed only when their deterministic result has
 * passed the institutional validation contract. Broker data remains read-only.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  TrendingDown, BarChart3, LineChart, Brain, Activity, Plus,
  AlertTriangle, Layers, Flame, Play, RefreshCw, Database, ShieldCheck,
} from "lucide-react";
import { useTradingQuantRisk } from "../../data/queries";
import {
  useMaterializeInstitutionalOptions, useRecordManualTrade,
  useRefreshOptionValuationSources, useRunInstitutionalOptionsAnalytics,
  useRunOptionAcceptance, useUpsertOptionValuationPolicy,
} from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select, Checkbox,
} from "../../system/primitives";
import { BarSeriesChart, LineSeriesChart, AreaSeriesChart } from "../../system/charts";
import { text, num, raw, formatCurrency, formatCompact, formatPercent, formatRelative } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "desk", label: "Options Desk", icon: TrendingDown },
  { key: "chain", label: "Option Chain", icon: BarChart3 },
  { key: "surface", label: "Vol Surface", icon: LineChart },
  { key: "oi-analysis", label: "OI Analysis", icon: Flame },
  { key: "strategies", label: "Strategy Builder", icon: Layers },
  { key: "agent", label: "Options Agent", icon: Brain },
];

export default function OptionsDesk({ defaultTab = "desk" }: { defaultTab?: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;
  function setTab(key: string) { navigate(`/options/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <TrendingDown size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Options Desk
          </div>
          <Badge tone="accent">OPTS</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>manual trading · full OI analytics · strategy builder</span>
        </div>
        <div className="aios-destination__subtitle">
          Real-time option chain, OI buildup analysis, provider-qualified vol analytics, straddle curves, max pain,
          strategy builder with payoff. NSE index + equity options via Zerodha.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>
      {tab === "desk" ? <OptionsDataOperationsControl /> : null}
      {tab === "desk" ? <OptionsAcceptanceControl /> : null}
      <OptionsAnalyticsControl />

      {tab === "desk" && <DeskView />}
      {tab === "chain" && <ChainView />}
      {tab === "surface" && <SurfaceView />}
      {tab === "oi-analysis" && <OiAnalysisView />}
      {tab === "strategies" && <StrategiesView />}
      {tab === "agent" && <AgentView />}
    </div>
  );
}

function OptionsAcceptanceControl() {
  const { underlyings, expiries } = useChain();
  const mutation = useRunOptionAcceptance();
  const pushToast = useUIStore((state) => state.pushToast);
  const defaultEnd = React.useMemo(() => optionsLocalDateTimeInputValue(), []);
  const defaultStart = React.useMemo(() => {
    const value = new Date();
    value.setMinutes(value.getMinutes() - 30 - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  }, []);
  const [form, setForm] = React.useState({
    exchange: "NFO" as "NFO" | "BFO",
    underlying: "",
    expiry_date: "",
    window_start: defaultStart,
    window_end: defaultEnd,
  });

  React.useEffect(() => {
    setForm((current) => ({
      ...current,
      underlying: current.underlying || underlyings[0] || "",
      expiry_date: current.expiry_date || expiries[0]?.slice(0, 10) || "",
    }));
  }, [underlyings, expiries]);

  const ready = Boolean(form.underlying && form.expiry_date && form.window_start && form.window_end && new Date(form.window_start) < new Date(form.window_end));
  function run() {
    if (!ready) return;
    mutation.mutate({
      exchange: form.exchange,
      underlying: form.underlying.trim().toUpperCase(),
      expiry_date: form.expiry_date,
      window_start: new Date(form.window_start).toISOString(),
      window_end: new Date(form.window_end).toISOString(),
      actor: "Devarsh",
    }, {
      onSuccess: (result) => pushToast({
        title: `Options acceptance ${text(result, "status", "complete")}`,
        message: `${num(result, "passed_count")} of ${num(result, "gate_count")} gates passed`,
        tone: text(result, "status") === "passed" ? "ok" : "warn",
        duration: 6500,
      }),
      onError: (error) => pushToast({ title: "Options acceptance failed", message: error.message, tone: "risk", duration: 7500 }),
    });
  }

  return (
    <Panel icon={ShieldCheck} title="Run Live-Window Acceptance" actions={<Badge tone={mutation.isError ? "risk" : mutation.isPending ? "warn" : "accent"}>{mutation.isPending ? "Checking" : "11 gates"}</Badge>}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
        <Field label="Underlying" required><TextInput value={form.underlying} onChange={(event) => setForm({ ...form, underlying: event.target.value.toUpperCase() })} placeholder="NIFTY" /></Field>
        <Field label="Exchange" required><Select value={form.exchange} onChange={(event) => setForm({ ...form, exchange: event.target.value as typeof form.exchange })}><option value="NFO">NFO</option><option value="BFO">BFO</option></Select></Field>
        <Field label="Expiry" required><TextInput type="date" value={form.expiry_date} onChange={(event) => setForm({ ...form, expiry_date: event.target.value })} /></Field>
        <Field label="Window start" required><TextInput type="datetime-local" value={form.window_start} onChange={(event) => setForm({ ...form, window_start: event.target.value })} /></Field>
        <Field label="Window end" required><TextInput type="datetime-local" value={form.window_end} onChange={(event) => setForm({ ...form, window_end: event.target.value })} /></Field>
        <Button variant="primary" icon={ShieldCheck} onClick={run} disabled={!ready || mutation.isPending}>{mutation.isPending ? "Evaluating…" : "Run acceptance"}</Button>
      </div>
      <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Evaluates only immutable stored batches inside the selected window. Missing analytics remain blocked; broker writes remain zero.</div>
      {!underlyings.length ? <div role="status" style={{ marginTop: "var(--space-3)", color: "var(--status-warn)", fontSize: "var(--text-sm)" }}>Materialize real Zerodha option snapshots before running acceptance.</div> : null}
      {mutation.isError ? <div role="alert" style={{ marginTop: "var(--space-3)", color: "var(--status-risk)", fontSize: "var(--text-sm)" }}>{mutation.error.message}</div> : null}
    </Panel>
  );
}

/* ============================================================
 * Shared: parse the chain
 * ============================================================ */
interface ParsedContract {
  symbol: string; expiry: string; strike: number; type: "CE" | "PE";
  ltp: number; oi: number; oiChange: number | null; iv: number | null; volume: number; spot: number;
  delta: number | null; gamma: number | null; theta: number | null; vega: number | null;
}

function optionalNum(row: LiveRow, key: string): number | null {
  const source = raw(row, key);
  if (source === null || source === undefined || source === "") return null;
  const parsed = typeof source === "number" ? source : Number(source);
  return Number.isFinite(parsed) ? parsed : null;
}

function booleanValue(row: LiveRow, key: string): boolean {
  const value = raw(row, key);
  return value === true || value === "true" || value === 1 || value === "1";
}

function ivPercent(iv: number): number {
  return iv > 3 ? iv : iv * 100;
}

function useChain() {
  const { data, isLoading } = useTradingQuantRisk();
  return React.useMemo(() => {
    const institutional = data?.institutional_option_chain ?? [];
    const raw = institutional.length > 0 ? institutional : data?.option_chain ?? [];
    const oiChanges = new Map(
      (data?.option_oi_change ?? []).map((row) => {
        const key = [text(row, "underlying"), text(row, "expiry", text(row, "expiry_date")), num(row, "strike", 0), text(row, "option_type").toUpperCase()].join("|");
        return [key, optionalNum(row, "open_interest_change")] as const;
      }),
    );
    const parsed: ParsedContract[] = raw.map((r) => {
      const greeksValidated = booleanValue(r, "greeks_validated");
      return ({
      symbol: text(r, "underlying", text(r, "symbol", "")),
      expiry: text(r, "expiry", text(r, "expiry_date", "")),
      strike: num(r, "strike", 0),
      type: (text(r, "option_type", "CE").toUpperCase().startsWith("P") ? "PE" : "CE") as "CE" | "PE",
      ltp: num(r, "last_price", num(r, "ltp", 0)),
      oi: num(r, "open_interest", num(r, "oi", 0)),
      oiChange: oiChanges.get([text(r, "underlying", text(r, "symbol", "")), text(r, "expiry", text(r, "expiry_date")), num(r, "strike", 0), text(r, "option_type", "CE").toUpperCase()].join("|")) ?? null,
      iv: greeksValidated ? optionalNum(r, "implied_volatility") : null,
      volume: num(r, "volume", 0),
      spot: num(r, "spot_price", num(r, "reference_spot", 0)),
      delta: greeksValidated ? optionalNum(r, "delta") : null,
      gamma: greeksValidated ? optionalNum(r, "gamma") : null,
      theta: greeksValidated ? optionalNum(r, "theta") : null,
      vega: greeksValidated ? optionalNum(r, "vega") : null,
    });
    });
    return { parsed, isLoading, underlyings: Array.from(new Set(parsed.map((p) => p.symbol))).sort(), expiries: Array.from(new Set(parsed.map((p) => p.expiry))).sort() };
  }, [data?.institutional_option_chain, data?.option_chain, data?.option_oi_change, isLoading]);
}
function OptionsAnalyticsControl() {
  const { underlyings, expiries } = useChain();
  const mutation = useRunInstitutionalOptionsAnalytics();
  const pushToast = useUIStore((state) => state.pushToast);
  const [form, setForm] = React.useState({
    underlying: "",
    exchange: "NFO" as "NFO" | "BFO",
    expiry_date: "",
    as_of: optionsLocalDateTimeInputValue(),
    model: "black_scholes_merton" as "black_scholes_merton" | "black_76",
    max_age_seconds: 120,
    max_spread_bps: 500,
    min_open_interest: 1,
    min_volume: 0,
  });

  React.useEffect(() => {
    setForm((current) => ({
      ...current,
      underlying: current.underlying || underlyings[0] || "",
      expiry_date: current.expiry_date || expiries[0]?.slice(0, 10) || "",
    }));
  }, [underlyings, expiries]);

  const ready = Boolean(form.underlying.trim() && form.expiry_date && form.as_of);

  function run() {
    if (!ready) return;
    mutation.mutate({
      underlying: form.underlying.trim().toUpperCase(),
      exchange: form.exchange,
      expiry_date: form.expiry_date,
      as_of: new Date(form.as_of).toISOString(),
      model: form.model,
      filters: {
        max_age_seconds: form.max_age_seconds,
        max_spread_bps: form.max_spread_bps,
        min_open_interest: form.min_open_interest,
        min_volume: form.min_volume,
      },
      dry_run: true,
      actor: "Devarsh",
    }, {
      onSuccess: (result) => pushToast({
        title: "Options analytics dry run complete",
        message: text(result, "status", text(result, "engine", "completed")),
        tone: "ok",
        duration: 4500,
      }),
      onError: (error) => pushToast({ title: "Options analytics failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  return (
    <Panel
      icon={RefreshCw}
      title="Run Institutional Options Analytics"
      actions={<Badge tone={mutation.isPending ? "warn" : mutation.isError ? "risk" : mutation.isSuccess ? "ok" : "accent"}>{mutation.isPending ? "Running" : mutation.isError ? "Failed" : mutation.isSuccess ? "Complete" : "Operator"}</Badge>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
        <Field label="Underlying" hint={underlyings.length ? "Live: " + underlyings.slice(0, 4).join(", ") : "Use a symbol present in the stored chain"} required><TextInput value={form.underlying} onChange={(event) => setForm({ ...form, underlying: event.target.value.toUpperCase() })} placeholder="NIFTY" /></Field>
        <Field label="Exchange" required><Select value={form.exchange} onChange={(event) => setForm({ ...form, exchange: event.target.value as typeof form.exchange })}><option value="NFO">NFO</option><option value="BFO">BFO</option></Select></Field>
        <Field label="Expiry" required><TextInput type="date" value={form.expiry_date} onChange={(event) => setForm({ ...form, expiry_date: event.target.value })} /></Field>
        <Field label="Valuation cutoff" required><TextInput type="datetime-local" value={form.as_of} onChange={(event) => setForm({ ...form, as_of: event.target.value })} /></Field>
        <Field label="Pricing model" required><Select value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value as typeof form.model })}><option value="black_scholes_merton">Black-Scholes-Merton</option><option value="black_76">Black-76 futures options</option></Select></Field>
        <Field label="Max quote age (sec)" required><TextInput type="number" min="1" value={form.max_age_seconds} onChange={(event) => setForm({ ...form, max_age_seconds: Number(event.target.value) })} /></Field>
        <Field label="Max spread (bps)" required><TextInput type="number" min="0" value={form.max_spread_bps} onChange={(event) => setForm({ ...form, max_spread_bps: Number(event.target.value) })} /></Field>
        <Field label="Minimum OI" required><TextInput type="number" min="0" value={form.min_open_interest} onChange={(event) => setForm({ ...form, min_open_interest: Number(event.target.value) })} /></Field>
        <Field label="Minimum volume" required><TextInput type="number" min="0" value={form.min_volume} onChange={(event) => setForm({ ...form, min_volume: Number(event.target.value) })} /></Field>
        <Button variant="primary" icon={RefreshCw} onClick={run} disabled={!ready || mutation.isPending}>{mutation.isPending ? "Running…" : "Validate chain"}</Button>
      </div>
      <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
        Dry run is the default. The engine reads stored chain snapshots, rejects stale or illiquid contracts, and calculates paper analytics only. It never submits a broker order.
      </div>
      {mutation.isError ? <div role="alert" style={{ marginTop: "var(--space-3)", color: "var(--status-risk)", fontSize: "var(--text-sm)" }}>{mutation.error.message}</div> : null}
      {mutation.isSuccess ? <div role="status" style={{ marginTop: "var(--space-3)", color: "var(--status-ok)", fontSize: "var(--text-sm)" }}>{text(mutation.data, "status", text(mutation.data, "engine", "Completed"))} · {text(mutation.data, "message", "No records or orders were written.")}</div> : null}
    </Panel>
  );
}

function optionsLocalDateTimeInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

const SELECTABLE_CANDIDATE_STATUSES = new Set(["passed", "warning"]);

function valuationCandidateRows(source: unknown): LiveRow[] {
  if (!source || typeof source !== "object") return [];
  const row = source as LiveRow;
  const candidates = raw(row, "option_valuation_source_candidates") ?? raw(row, "candidates");
  return Array.isArray(candidates)
    ? candidates.filter((candidate): candidate is LiveRow => Boolean(candidate) && typeof candidate === "object")
    : [];
}

function valuationCandidateUsable(candidate: LiveRow): boolean {
  const validUntil = new Date(text(candidate, "candidate_valid_until")).getTime();
  return num(candidate, "rate_observation_id") > 0
    && num(candidate, "dividend_observation_id") > 0
    && optionalNum(candidate, "risk_free_rate") !== null
    && optionalNum(candidate, "dividend_yield") !== null
    && SELECTABLE_CANDIDATE_STATUSES.has(text(candidate, "rate_quality_status").toLowerCase())
    && SELECTABLE_CANDIDATE_STATUSES.has(text(candidate, "dividend_quality_status").toLowerCase())
    && Number.isFinite(validUntil) && validUntil > Date.now()
    && Boolean(text(candidate, "source_artifact_ref"));
}

function localDateTimeValue(value: string): string {
  const parsed = new Date(value);
  if (!value || Number.isNaN(parsed.getTime())) return "";
  parsed.setMinutes(parsed.getMinutes() - parsed.getTimezoneOffset());
  return parsed.toISOString().slice(0, 16);
}

function OptionsDataOperationsControl() {
  const { data } = useTradingQuantRisk();
  const materialize = useMaterializeInstitutionalOptions();
  const savePolicy = useUpsertOptionValuationPolicy();
  const refreshSources = useRefreshOptionValuationSources();
  const pushToast = useUIStore((state) => state.pushToast);
  const readiness = data?.option_analytics_readiness ?? [];
  const pipeline = data?.institutional_option_pipeline_runs ?? [];
  const snapshotCandidates = React.useMemo(() => valuationCandidateRows(data), [data]);
  const [refreshedCandidates, setRefreshedCandidates] = React.useState<LiveRow[] | null>(null);
  const candidates = refreshedCandidates ?? snapshotCandidates;
  const now = React.useMemo(() => optionsLocalDateTimeInputValue(), []);
  const tomorrow = React.useMemo(() => {
    const value = new Date();
    value.setDate(value.getDate() + 1);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  }, []);
  const [form, setForm] = React.useState({
    policy_key: "nifty-valuation-" + new Date().toISOString().slice(0, 10).replace(/-/g, ""),
    provider: "Zerodha",
    exchange: "NFO" as "NFO" | "BFO",
    underlying: "NIFTY",
    model_family: "black_scholes_merton" as "black_scholes_merton" | "black_76",
    risk_free_rate: "",
    dividend_yield: "",
    effective_from: now,
    expires_at: tomorrow,
  });
  const [selectedCandidate, setSelectedCandidate] = React.useState<LiveRow | null>(null);
  const [operatorConfirmed, setOperatorConfirmed] = React.useState(false);
  const visibleCandidates = candidates.filter((candidate) => text(candidate, "underlying").toUpperCase() === form.underlying.trim().toUpperCase());
  const selectedRateId = selectedCandidate ? num(selectedCandidate, "rate_observation_id") : 0;
  const selectedDividendId = selectedCandidate ? num(selectedCandidate, "dividend_observation_id") : 0;
  const policyReady = Boolean(
    form.policy_key && form.underlying && form.risk_free_rate !== "" && form.dividend_yield !== ""
    && form.effective_from && form.expires_at
    && selectedRateId > 0 && selectedDividendId > 0 && operatorConfirmed
    && new Date(form.effective_from) < new Date(form.expires_at)
  );

  function resetCandidateSelection(patch: Partial<typeof form>) {
    setSelectedCandidate(null);
    setOperatorConfirmed(false);
    setForm((current) => ({
      ...current,
      ...patch,
      risk_free_rate: "",
      dividend_yield: "",
    }));
  }

  function selectCandidate(candidate: LiveRow) {
    if (!valuationCandidateUsable(candidate)) return;
    setSelectedCandidate(candidate);
    setOperatorConfirmed(false);
    setForm((current) => ({
      ...current,
      underlying: text(candidate, "underlying").toUpperCase(),
      risk_free_rate: String(optionalNum(candidate, "risk_free_rate")),
      dividend_yield: String(optionalNum(candidate, "dividend_yield")),
      expires_at: localDateTimeValue(text(candidate, "candidate_valid_until")),
    }));
  }

  function refreshOfficialInputs() {
    refreshSources.mutate({ sources: ["rate", "dividends"], actor: "Devarsh" }, {
      onSuccess: (result) => {
        const refreshed = valuationCandidateRows(result);
        setRefreshedCandidates(refreshed);
        setSelectedCandidate(null);
        setOperatorConfirmed(false);
        pushToast({
          title: "Official valuation inputs refreshed",
          message: refreshed.length ? refreshed.length + " governed candidate pairs returned for review." : "No governed candidate pairs were returned. No values were assumed.",
          tone: refreshed.length ? "ok" : "warn",
          duration: 5500,
        });
      },
      onError: (error) => pushToast({ title: "Official input refresh failed", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  function storePolicy() {
    if (!policyReady) return;
    const payload = {
      policy_key: form.policy_key,
      provider: form.provider,
      exchange: form.exchange,
      underlying: form.underlying.trim().toUpperCase(),
      model_family: form.model_family,
      risk_free_rate: Number(form.risk_free_rate),
      dividend_yield: Number(form.dividend_yield),
      effective_from: new Date(form.effective_from).toISOString(),
      expires_at: new Date(form.expires_at).toISOString(),
      rate_observation_id: selectedRateId,
      dividend_observation_id: selectedDividendId,
      operator_confirmed: true as const,
      actor: "Devarsh",
    };
    savePolicy.mutate(payload, {
      onSuccess: () => pushToast({ title: "Valuation policy active", message: "Source-evidenced inputs are available to the deterministic options engine.", tone: "ok", duration: 5000 }),
      onError: (error) => pushToast({ title: "Policy rejected", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  function runMaterializer() {
    materialize.mutate({ limit: 20, interval_seconds: 300, actor: "Devarsh" }, {
      onSuccess: (result) => {
        const status = text(result, "status", "blocked");
        const rowsRead = num(result, "rows_read");
        pushToast({
          title: status === "completed" || status === "degraded" ? "Option warehouse refreshed" : "Option warehouse not ready",
          message: rowsRead ? `${rowsRead} source rows read · ${num(result, "calculations_completed")} analytics rows` : "No new real Zerodha option snapshots were available.",
          tone: status === "completed" ? "ok" : "warn",
          duration: 6500,
        });
      },
      onError: (error) => pushToast({ title: "Materializer failed", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  return (
    <Panel
      icon={Database}
      title="Institutional Data Operations"
      actions={<Button size="sm" icon={RefreshCw} onClick={runMaterializer} disabled={materialize.isPending}>{materialize.isPending ? "Refreshing…" : "Materialize snapshots"}</Button>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
        {readiness.length === 0 ? (
          <Empty icon={Database} title="No institutional batches" description="Sync Zerodha option quotes, then materialize snapshots. No synthetic chain is created." />
        ) : readiness.slice(0, 4).map((row, index) => (
          <MetricTile key={text(row, "underlying", String(index))} tone={text(row, "analytics_readiness") === "ready" ? "ok" : "warn"}>
            <Metric
              label={text(row, "underlying") + " " + text(row, "expiry")}
              value={<StatusPill status={text(row, "analytics_readiness")} />}
              sub={String(num(row, "contract_count")) + " contracts · " + text(row, "model_family", "policy missing")}
            />
          </MetricTile>
        ))}
        <MetricTile tone={pipeline[0] && text(pipeline[0], "status") === "completed" ? "ok" : "default"}>
          <Metric label="Latest materializer" value={pipeline.length ? text(pipeline[0], "status") : "Never run"} sub={pipeline.length ? String(num(pipeline[0], "calculations_completed")) + " analytics rows" : "awaiting source snapshots"} />
        </MetricTile>
      </div>
      <div style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--space-4)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-3)", fontWeight: 650 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)" }}><ShieldCheck size={16} /> Source-evidenced valuation policy</span>
          <Button size="sm" icon={RefreshCw} onClick={refreshOfficialInputs} disabled={refreshSources.isPending}>
            {refreshSources.isPending ? "Refreshing official inputs..." : "Refresh official inputs"}
          </Button>
        </div>
        <ValuationCandidateCards candidates={visibleCandidates} selectedRateId={selectedRateId} selectedDividendId={selectedDividendId} onSelect={selectCandidate} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
          <Field label="Policy key" required><TextInput value={form.policy_key} onChange={(event) => setForm({ ...form, policy_key: event.target.value })} /></Field>
          <Field label="Underlying" required><TextInput value={form.underlying} onChange={(event) => resetCandidateSelection({ underlying: event.target.value.toUpperCase() })} /></Field>
          <Field label="Exchange" required><Select value={form.exchange} onChange={(event) => resetCandidateSelection({ exchange: event.target.value as typeof form.exchange })}><option value="NFO">NFO</option><option value="BFO">BFO</option></Select></Field>
          <Field label="Model" required><Select value={form.model_family} onChange={(event) => resetCandidateSelection({ model_family: event.target.value as typeof form.model_family })}><option value="black_scholes_merton">Black-Scholes-Merton</option><option value="black_76">Black-76</option></Select></Field>
          <Field label="Risk-free rate" hint="Selected governed observation" required><TextInput aria-label="Risk-free rate" type="number" step="0.0001" value={form.risk_free_rate} readOnly /></Field>
          <Field label="Dividend yield" hint="Selected governed observation" required><TextInput aria-label="Dividend yield" type="number" step="0.0001" value={form.dividend_yield} readOnly /></Field>
          <Field label="Effective from" required><TextInput type="datetime-local" value={form.effective_from} onChange={(event) => setForm({ ...form, effective_from: event.target.value })} /></Field>
          <Field label="Expires at" hint="Cannot exceed candidate validity" required><TextInput type="datetime-local" value={form.expires_at} onChange={(event) => setForm({ ...form, expires_at: event.target.value })} /></Field>
          <Field label="Operator approval" required>
            <Checkbox checked={operatorConfirmed} onChange={setOperatorConfirmed} disabled={!selectedRateId || !selectedDividendId} label="I confirm these exact source observations." />
          </Field>
          <Button variant="primary" icon={ShieldCheck} onClick={storePolicy} disabled={!policyReady || savePolicy.isPending}>{savePolicy.isPending ? "Saving…" : "Validate policy"}</Button>
        </div>
      </div>
      {materialize.isError ? <div role="alert" style={{ color: "var(--status-risk)", marginTop: "var(--space-3)" }}>{materialize.error.message}</div> : null}
      {refreshSources.isError ? <div role="alert" style={{ color: "var(--status-risk)", marginTop: "var(--space-3)" }}>{refreshSources.error.message}</div> : null}
      {savePolicy.isError ? <div role="alert" style={{ color: "var(--status-risk)", marginTop: "var(--space-3)" }}>{savePolicy.error.message}</div> : null}
    </Panel>
  );
}

function ValuationCandidateCards({
  candidates,
  selectedRateId,
  selectedDividendId,
  onSelect,
}: {
  candidates: LiveRow[];
  selectedRateId: number;
  selectedDividendId: number;
  onSelect: (candidate: LiveRow) => void;
}) {
  return (
    <div aria-label="Governed valuation candidates" style={{ marginBottom: "var(--space-4)" }}>
      {candidates.length === 0 ? (
        <Empty icon={Database} title="No governed candidates" description="Refresh official inputs. No fallback value will be assumed." />
      ) : candidates.map((candidate, index) => {
        const rateId = num(candidate, "rate_observation_id");
        const dividendId = num(candidate, "dividend_observation_id");
        const rate = optionalNum(candidate, "risk_free_rate");
        const dividend = optionalNum(candidate, "dividend_yield");
        const usable = valuationCandidateUsable(candidate);
        const selected = selectedRateId === rateId && selectedDividendId === dividendId;
        return (
          <div key={rateId + "-" + dividendId + "-" + index} style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", marginTop: index ? "var(--space-3)" : 0, minWidth: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "var(--space-3)", alignItems: "flex-start" }}>
              <div style={{ minWidth: 0, flex: "1 1 220px" }}>
                <div style={{ fontWeight: 650 }}>{text(candidate, "underlying", "Unknown underlying")}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", overflowWrap: "anywhere" }}>
                  Valid until {text(candidate, "candidate_valid_until") || "unavailable"} | {text(candidate, "source_artifact_ref", "evidence reference unavailable")}
                </div>
              </div>
              <div style={{ minWidth: 160 }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Risk-free rate</div>
                <div style={{ fontWeight: 650 }}>{rate === null ? "Unavailable" : formatPercent(rate)}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Observation #{rateId || "unavailable"} | {text(candidate, "rate_instrument_identifier", "instrument unavailable")}</div>
                <StatusPill status={text(candidate, "rate_quality_status", "unreviewed")} />
              </div>
              <div style={{ minWidth: 160 }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Dividend yield</div>
                <div style={{ fontWeight: 650 }}>{dividend === null ? "Unavailable" : formatPercent(dividend)}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>Observation #{dividendId || "unavailable"}</div>
                <StatusPill status={text(candidate, "dividend_quality_status", "unreviewed")} />
              </div>
              <div style={{ minWidth: 200, flex: "1 1 240px" }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", overflowWrap: "anywhere" }}>Rate source: {text(candidate, "rate_source_url", "unavailable")}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", overflowWrap: "anywhere" }}>Dividend source: {text(candidate, "dividend_source_url", "unavailable")}</div>
                <Button size="sm" variant={selected ? "primary" : "default"} icon={ShieldCheck} onClick={() => onSelect(candidate)} disabled={!usable} style={{ marginTop: "var(--space-2)" }}>
                  {selected ? "Selected" : usable ? "Use candidate" : "Not selectable"}
                </Button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}



/* ============================================================
 * DESK — analytics overview per underlying
 * ============================================================ */
function DeskView() {
  const { parsed, underlyings, isLoading } = useChain();
  const { data: tradingData } = useTradingQuantRisk();
  const [showTicket, setShowTicket] = React.useState(false);
  const analytics = React.useMemo(() => computeAnalytics(parsed), [parsed]);
  const validIv = parsed.map((contract) => contract.iv).filter((iv): iv is number => iv !== null && iv > 0);
  const acceptance = tradingData?.option_acceptance ?? [];
  const openAnalyticsAlerts = (tradingData?.option_analytics_alerts ?? []).filter((row) => text(row, "status") === "open");
  const specialistObservations = tradingData?.option_specialist_observations ?? [];
  const replaySessions = tradingData?.option_replays ?? [];
  const optionTrades = React.useMemo(
    () => [
      ...(tradingData?.trade_activity ?? []).filter((row) => {
      const instrumentType = text(row, "instrument_type", text(row, "asset_class", "")).toLowerCase();
      const optionType = text(row, "option_type", "").toUpperCase();
      const notes = text(row, "notes", text(row, "thesis", "")).toUpperCase();
      return instrumentType.includes("option") || ["CE", "PE"].includes(optionType) || /\b(CE|PE)\b/.test(notes);
      }),
      ...(tradingData?.option_trade_log ?? []).map((row) => ({
        ...row,
        symbol: text(row, "stock_ticker"),
        strike: num(row, "strike_price"),
        option_type: text(row, "call_put"),
        quantity: num(row, "contracts") || num(row, "lot_size") * num(row, "no_of_trades"),
        price: num(row, "option_value"),
        trade_ts: text(row, "entry_date"),
        strategy_name: text(row, "trade_type", "legacy option log"),
        source_kind: "attached_option_log",
        quantity_unit: "lots",
        lot_count: num(row, "contracts"),
        contract_quantity: num(row, "contracts") * num(row, "lot_size"),
      })),
    ],
    [tradingData?.trade_activity, tradingData?.option_trade_log],
  );

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Underlyings" value={underlyings.length} /></MetricTile>
        <MetricTile><Metric label="Contracts" value={parsed.length} /></MetricTile>
        <MetricTile><Metric label="Total OI" value={formatCompact(parsed.reduce((a, c) => a + c.oi, 0))} /></MetricTile>
        <MetricTile><Metric label="Avg IV" value={validIv.length ? `${(validIv.reduce((sum, iv) => sum + ivPercent(iv), 0) / validIv.length).toFixed(1)}%` : "Unavailable"} sub={validIv.length ? undefined : "Kite quotes do not supply IV"} /></MetricTile>
      </div>

      <Panel icon={AlertTriangle} title="Institutional Analytics Readiness">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
          <MetricTile tone={acceptance.some((row) => text(row, "status") === "passed") ? "ok" : "warn"}>
            <Metric label="Acceptance Runs" value={acceptance.length} sub={acceptance.length ? text(acceptance[0], "status", "pending") : "not yet demonstrated"} />
          </MetricTile>
          <MetricTile tone={openAnalyticsAlerts.length ? "warn" : "default"}>
            <Metric label="Open Alerts" value={openAnalyticsAlerts.length} sub="evidence-backed analytics alerts" />
          </MetricTile>
          <MetricTile><Metric label="Replay Sessions" value={replaySessions.length} sub="point-in-time, paper only" /></MetricTile>
          <MetricTile><Metric label="Specialist Notes" value={specialistObservations.length} sub="human review required" /></MetricTile>
        </div>
        {acceptance.length === 0 && (
          <div style={{ marginTop: "var(--space-3)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
            IV, Greeks, exposure and replay capabilities remain unavailable until a real live-market acceptance run passes. No broker write is permitted.
          </div>
        )}
      </Panel>

      <Panel icon={Activity} title="Live Analytics per Underlying">
        {isLoading ? <SkeletonRows n={3} /> : analytics.length === 0 ? (
          <Empty icon={Activity} title="No option chain data" description="Run the Zerodha market data sync to populate the chain." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Underlying", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "spot", header: "Spot", align: "right", render: (r) => num(r, "spot", 0).toFixed(2) },
              { key: "atm", header: "ATM IV", align: "right", render: (r) => optionalNum(r, "atm_iv") === null ? "—" : `${ivPercent(optionalNum(r, "atm_iv")!).toFixed(1)}%` },
              { key: "pcr", header: "PCR", align: "right", render: (r) => <span style={{ color: num(r, "pcr", 0) > 1.2 ? "var(--status-warn)" : num(r, "pcr", 0) < 0.8 ? "var(--status-info)" : "var(--text)" }}>{num(r, "pcr", 0).toFixed(2)}</span> },
              { key: "maxpain", header: "Max Pain", align: "right", render: (r) => num(r, "max_pain", 0).toFixed(0) },
              { key: "callwall", header: "Call Wall", align: "right", render: (r) => num(r, "call_wall", 0).toFixed(0) },
              { key: "putwall", header: "Put Wall", align: "right", render: (r) => num(r, "put_wall", 0).toFixed(0) },
            ]}
            rows={analytics}
            rowKey={(r, i) => text(r, "symbol", `a-${i}`)}
          />
        )}
      </Panel>

      <Panel icon={TrendingDown} title="Options Blotter"
        actions={<Button size="sm" variant="primary" icon={Plus} onClick={() => setShowTicket(true)}>New Option Trade</Button>}
      >
        {optionTrades.length === 0 ? (
          <Empty icon={TrendingDown} title="No option trades recorded" description="Record a manual option trade - it flows into the blotter and journal." action={<Button size="sm" icon={Plus} onClick={() => setShowTicket(true)}>Record trade</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "contract", header: "Contract", render: (row) => {
                const parts = [
                  text(row, "symbol"),
                  text(row, "expiry_date"),
                  num(row, "strike", 0) || "",
                  text(row, "option_type"),
                ].filter(Boolean);
                return <><strong>{parts.join(" ")}</strong><div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{text(row, "strategy_name", text(row, "thesis", "manual option trade"))}</div></>;
              } },
              { key: "side", header: "Side", render: (row) => <StatusPill status={text(row, "side", text(row, "direction"))} /> },
              { key: "lots", header: "Lots", align: "right", render: (row) => text(row, "quantity_unit") === "lots" ? num(row, "lot_count", num(row, "quantity", num(row, "qty", 0))) : "—" },
              { key: "lot_size", header: "Lot size", align: "right", render: (row) => num(row, "lot_size") || "—" },
              { key: "quantity", header: "Units", align: "right", render: (row) => num(row, "contract_quantity", num(row, "quantity", num(row, "qty", 0))) },
              { key: "price", header: "Premium", align: "right", render: (row) => formatCurrency(num(row, "price", num(row, "trade_price", 0))) },
              { key: "book", header: "Book", render: (row) => text(row, "book_key", text(row, "book_name", "unassigned")) },
              { key: "when", header: "Recorded", render: (row) => formatRelative(text(row, "trade_ts", text(row, "created_at"))) },
            ]}
            rows={optionTrades}
            rowKey={(row, index) => text(row, "trade_id", text(row, "id", `option-trade-${index}`))}
            dense
          />
        )}
      </Panel>

      <OptionTicketDrawer open={showTicket} onClose={() => setShowTicket(false)} />
    </>
  );
}

function computeAnalytics(chain: ParsedContract[]): LiveRow[] {
  const bySymbol = new Map<string, ParsedContract[]>();
  for (const c of chain) {
    if (!bySymbol.has(c.symbol)) bySymbol.set(c.symbol, []);
    bySymbol.get(c.symbol)!.push(c);
  }
  const out: LiveRow[] = [];
  for (const [symbol, contracts] of bySymbol) {
    const spot = contracts[0]?.spot || 0;
    const calls = contracts.filter((c) => c.type === "CE");
    const puts = contracts.filter((c) => c.type === "PE");
    const totalCallOi = calls.reduce((a, c) => a + c.oi, 0);
    const totalPutOi = puts.reduce((a, c) => a + c.oi, 0);
    const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 0;
    const atm = spot > 0 ? contracts.reduce((best, c) => Math.abs(c.strike - spot) < Math.abs(best.strike - spot) ? c : best, contracts[0]) : undefined;
    const strikes = Array.from(new Set(contracts.map((c) => c.strike))).sort((a, b) => a - b);
    let maxPain = 0; let minPayout = Infinity;
    for (const s of strikes) {
      let payout = 0;
      for (const c of contracts) {
        const intrinsic = c.type === "CE" ? Math.max(0, s - c.strike) : Math.max(0, c.strike - s);
        payout += intrinsic * c.oi;
      }
      if (payout < minPayout) { minPayout = payout; maxPain = s; }
    }
    const callWall = calls.reduce((best, c) => c.oi > best.oi ? c : best, calls[0]);
    const putWall = puts.reduce((best, c) => c.oi > best.oi ? c : best, puts[0]);
    out.push({ symbol, spot, atm_iv: atm?.iv ?? null, pcr, max_pain: maxPain, call_wall: callWall?.strike ?? 0, put_wall: putWall?.strike ?? 0, total_call_oi: totalCallOi, total_put_oi: totalPutOi } as LiveRow);
  }
  return out;
}

/* ============================================================
 * CHAIN
 * ============================================================ */
function ChainView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => (!symbol || c.symbol === symbol) && (!expiry || c.expiry === expiry));
  const spot = filtered[0]?.spot ?? 0;
  const atmStrike = spot > 0 ? filtered.reduce((best, c) => Math.abs(c.strike - spot) < Math.abs(best.strike - spot) ? c : best, filtered[0])?.strike : 0;

  return (
    <>
      <Panel icon={BarChart3} title="Option Chain"
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        {isLoading ? <SkeletonRows n={6} /> : filtered.length === 0 ? (
          <Empty icon={BarChart3} title="No chain data for this selection" />
        ) : (
          <DataTable
            columns={[
              { key: "strike", header: "Strike", align: "right", render: (r) => <strong style={{ color: num(r, "strike", 0) === atmStrike ? "var(--accent)" : "var(--text)" }}>{num(r, "strike", 0)}</strong> },
              { key: "type", header: "Type", render: (r) => <StatusPill status={text(r, "type")} /> },
              { key: "ltp", header: "LTP", align: "right", render: (r) => formatCurrency(num(r, "ltp", 0)) },
              { key: "oi", header: "OI", align: "right", render: (r) => formatCompact(num(r, "oi", 0)) },
              { key: "oichg", header: "OI Chg", align: "right", render: (r) => optionalNum(r, "oiChange") === null ? "—" : <span style={{ color: optionalNum(r, "oiChange")! >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{optionalNum(r, "oiChange")! >= 0 ? "+" : ""}{formatCompact(optionalNum(r, "oiChange")!)}</span> },
              { key: "iv", header: "IV", align: "right", render: (r) => optionalNum(r, "iv") === null ? "—" : `${ivPercent(optionalNum(r, "iv")!).toFixed(1)}%` },
              { key: "delta", header: "Delta", align: "right", render: (r) => optionalNum(r, "delta")?.toFixed(3) ?? "—" },
              { key: "gamma", header: "Gamma", align: "right", render: (r) => optionalNum(r, "gamma")?.toFixed(4) ?? "—" },
              { key: "theta", header: "Theta", align: "right", render: (r) => optionalNum(r, "theta")?.toFixed(2) ?? "—" },
              { key: "vega", header: "Vega", align: "right", render: (r) => optionalNum(r, "vega")?.toFixed(2) ?? "—" },
              { key: "vol", header: "Vol", align: "right", render: (r) => formatCompact(num(r, "volume", 0)) },
            ]}
            rows={filtered as unknown as LiveRow[]}
            rowKey={(r, i) => `${text(r, "type")}-${num(r, "strike", 0)}-${i}`}
            dense
          />
        )}
      </Panel>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "right" }}>Spot: <strong>{spot.toFixed(2)}</strong> · {filtered.length} contracts · ATM strike highlighted</div>
    </>
  );
}

/* ============================================================
 * SURFACE — IV smile
 * ============================================================ */
function SurfaceView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => c.symbol === symbol && c.expiry === expiry && c.iv !== null && c.iv > 0);
  const spot = filtered[0]?.spot ?? 0;
  const aggregated = React.useMemo(() => {
    const map = new Map<number, { strike: number; ceIv?: number; peIv?: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike };
      if (c.type === "CE") ex.ceIv = ivPercent(c.iv!); else ex.peIv = ivPercent(c.iv!);
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);

  return (
    <>
      <Panel icon={LineChart} title={`Implied Volatility Smile — ${symbol} ${expiry}`}
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        {isLoading ? <Skeleton style={{ height: 280 }} /> : aggregated.length === 0 ? (
          <Empty icon={LineChart} title="No IV data" description="Sync the Zerodha option chain to see the vol smile." />
        ) : (
          <LineSeriesChart
            data={aggregated as unknown as Record<string, number | string>[]}
            series={[{ key: "ceIv", name: "Call IV", color: "#c94f49" }, { key: "peIv", name: "Put IV", color: "#2f78a7" }]}
            xKey="strike" height={300}
          />
        )}
      </Panel>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center" }}>
        Spot: <strong>{spot.toFixed(2)}</strong> · Steep put skew (left side elevated) = demand for downside protection.
      </div>
    </>
  );
}

/* ============================================================
 * OI ANALYSIS — OI by strike, OI buildup, straddle curve
 * ============================================================ */
function OiAnalysisView() {
  const { parsed, underlyings, expiries, isLoading } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  React.useEffect(() => {
    if (!symbol && underlyings.length) setSymbol(underlyings[0]);
    if (!expiry && expiries.length) setExpiry(expiries[0]);
  }, [underlyings, expiries, symbol, expiry]);

  const filtered = parsed.filter((c) => c.symbol === symbol && c.expiry === expiry);
  const oiByStrike = React.useMemo(() => {
    const map = new Map<number, { strike: number; CE: number; PE: number; ceChg: number; peChg: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike, CE: 0, PE: 0, ceChg: 0, peChg: 0 };
      if (c.type === "CE") { ex.CE = c.oi; ex.ceChg = c.oiChange ?? 0; } else { ex.PE = c.oi; ex.peChg = c.oiChange ?? 0; }
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);
  const oiChange = React.useMemo(() => parsed.some((contract) => contract.oiChange !== null) ? oiByStrike.map((d) => ({ strike: d.strike, CE: d.ceChg, PE: d.peChg })) : [], [oiByStrike, parsed]);
  const straddle = React.useMemo(() => {
    const map = new Map<number, { strike: number; straddle: number }>();
    for (const c of filtered) {
      const ex = map.get(c.strike) ?? { strike: c.strike, straddle: 0 };
      ex.straddle += c.ltp;
      map.set(c.strike, ex);
    }
    return Array.from(map.values()).sort((a, b) => a.strike - b.strike);
  }, [filtered]);

  const totalCallOi = oiByStrike.reduce((a, d) => a + d.CE, 0);
  const totalPutOi = oiByStrike.reduce((a, d) => a + d.PE, 0);
  const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 0;

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Total Call OI" value={formatCompact(totalCallOi)} /></MetricTile>
        <MetricTile><Metric label="Total Put OI" value={formatCompact(totalPutOi)} /></MetricTile>
        <MetricTile tone={pcr > 1.2 ? "warn" : pcr < 0.8 ? "ok" : "default"}><Metric label="Put/Call Ratio" value={pcr.toFixed(2)} sub={pcr > 1.2 ? "bearish tilt" : pcr < 0.8 ? "bullish tilt" : "balanced"} /></MetricTile>
      </div>

      <Panel icon={BarChart3} title={`Open Interest by Strike — ${symbol} ${expiry}`}
        actions={<><Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 120 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select><Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{expiries.map((e) => <option key={e}>{e}</option>)}</Select></>}
      >
        {isLoading || oiByStrike.length === 0 ? <Skeleton style={{ height: 300 }} /> : (
          <BarSeriesChart data={oiByStrike as unknown as Record<string, number | string>[]} bars={[{ key: "CE", name: "Call OI", color: "#c94f49" }, { key: "PE", name: "Put OI", color: "#2d8b69" }]} xKey="strike" height={300} />
        )}
      </Panel>

      <Panel icon={Flame} title="OI Buildup (Change in OI) — where money is flowing">
        {oiChange.length === 0 ? <Empty icon={Flame} title="No OI change data" /> : (
          <BarSeriesChart data={oiChange as unknown as Record<string, number | string>[]} bars={[{ key: "CE", name: "Call OI Chg", color: "#c94f49" }, { key: "PE", name: "Put OI Chg", color: "#2d8b69" }]} xKey="strike" height={260} />
        )}
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>Positive bars = OI being added. Call buildup = resistance forming; Put buildup = support forming.</div>
      </Panel>

      <Panel icon={Activity} title="Straddle Curve (CE + PE premium by strike)">
        {straddle.length === 0 ? <Empty icon={Activity} title="No straddle data" /> : (
          <AreaSeriesChart data={straddle as unknown as Record<string, number | string>[]} series={[{ key: "straddle", name: "Straddle" }]} xKey="strike" height={240} />
        )}
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>The straddle minimum marks the market's expected settlement — often near max pain.</div>
      </Panel>
    </>
  );
}

/* ============================================================
 * STRATEGY BUILDER
 * ============================================================ */
interface Leg { id: string; type: "CE" | "PE"; action: "buy" | "sell"; strike: number; qty: number; premium: number; }

function StrategiesView() {
  const { parsed, underlyings } = useChain();
  const [symbol, setSymbol] = React.useState("");
  const [expiry, setExpiry] = React.useState("");
  const [legs, setLegs] = React.useState<Leg[]>([]);
  const [showAdd, setShowAdd] = React.useState(false);

  const symbolExpiries = React.useMemo(
    () => Array.from(new Set(parsed.filter((contract) => contract.symbol === symbol).map((contract) => contract.expiry))).sort(),
    [parsed, symbol],
  );
  React.useEffect(() => {
    if (underlyings.length && !underlyings.includes(symbol)) setSymbol(underlyings[0]);
  }, [underlyings, symbol]);
  React.useEffect(() => {
    if (symbolExpiries.length && !symbolExpiries.includes(expiry)) setExpiry(symbolExpiries[0]);
  }, [symbolExpiries, expiry]);

  const activeContracts = React.useMemo(
    () => parsed.filter((contract) => contract.symbol === symbol && contract.expiry === expiry),
    [parsed, symbol, expiry],
  );
  const spot = activeContracts.find((contract) => contract.spot > 0)?.spot ?? 0;
  const strikes = Array.from(new Set(activeContracts.map((contract) => contract.strike))).sort((a, b) => a - b);
  const atmIndex = spot > 0 && strikes.length
    ? strikes.reduce((best, strike, index) => Math.abs(strike - spot) < Math.abs(strikes[best] - spot) ? index : best, 0)
    : -1;
  const atmStrike = atmIndex >= 0 ? strikes[atmIndex] : 0;

  const payoff = React.useMemo(() => {
    if (legs.length === 0 || spot <= 0) return [];
    const min = spot * 0.85; const max = spot * 1.15; const steps = 60;
    return Array.from({ length: steps }, (_, i) => {
      const s = min + ((max - min) * i) / (steps - 1);
      let pnl = 0;
      for (const leg of legs) {
        const intrinsic = leg.type === "CE" ? Math.max(0, s - leg.strike) : Math.max(0, leg.strike - s);
        const sign = leg.action === "buy" ? 1 : -1;
        pnl += sign * (intrinsic - leg.premium) * leg.qty;
      }
      return { spot: Math.round(s), pnl: Math.round(pnl) };
    });
  }, [legs, spot]);

  function addLeg(leg: Omit<Leg, "id">) { setLegs((prev) => [...prev, { ...leg, id: `leg-${Date.now()}` }]); setShowAdd(false); }
  function removeLeg(id: string) { setLegs((prev) => prev.filter((l) => l.id !== id)); }
  function loadPreset(name: string) {
    const contract = (type: "CE" | "PE", index: number) => {
      const strike = strikes[index];
      return strike === undefined
        ? undefined
        : activeContracts.find((item) => item.type === type && item.strike === strike && item.ltp > 0);
    };
    const leg = (item: ParsedContract, action: "buy" | "sell", id: string): Leg => ({
      id: `${id}-${Date.now()}`,
      type: item.type,
      action,
      strike: item.strike,
      qty: 1,
      premium: item.ltp,
    });

    if (name === "long-straddle") {
      const call = contract("CE", atmIndex);
      const put = contract("PE", atmIndex);
      if (call && put) setLegs([leg(call, "buy", "straddle-call"), leg(put, "buy", "straddle-put")]);
    }
    if (name === "iron-condor") {
      const shortCall = contract("CE", atmIndex + 1);
      const longCall = contract("CE", atmIndex + 2);
      const shortPut = contract("PE", atmIndex - 1);
      const longPut = contract("PE", atmIndex - 2);
      if (shortCall && longCall && shortPut && longPut) {
        setLegs([
          leg(shortCall, "sell", "condor-short-call"),
          leg(longCall, "buy", "condor-long-call"),
          leg(shortPut, "sell", "condor-short-put"),
          leg(longPut, "buy", "condor-long-put"),
        ]);
      }
    }
    if (name === "bull-call-spread") {
      const longCall = contract("CE", atmIndex);
      const shortCall = contract("CE", atmIndex + 1);
      if (longCall && shortCall) setLegs([leg(longCall, "buy", "spread-long-call"), leg(shortCall, "sell", "spread-short-call")]);
    }
  }

  const liveChainReady = spot > 0 && activeContracts.some((contract) => contract.ltp > 0);

  return (
    <>
      <Panel icon={Layers} title="Strategy Builder"
        actions={<>
          <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: 110 }}>{underlyings.map((u) => <option key={u}>{u}</option>)}</Select>
          <Select value={expiry} onChange={(e) => setExpiry(e.target.value)} style={{ width: 130 }}>{symbolExpiries.map((e) => <option key={e}>{e}</option>)}</Select>
        </>}
      >
        <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", flexWrap: "wrap" }}>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("long-straddle")} disabled={!liveChainReady}>Long Straddle</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("iron-condor")} disabled={!liveChainReady}>Iron Condor</Button>
          <Button size="sm" variant="ghost" onClick={() => loadPreset("bull-call-spread")} disabled={!liveChainReady}>Bull Call Spread</Button>
          <Button size="sm" variant="ghost" icon={Plus} onClick={() => setShowAdd(true)} disabled={!liveChainReady}>Add Leg</Button>
          <Button size="sm" variant="ghost" onClick={() => setLegs([])}>Clear</Button>
        </div>
        {legs.length === 0 ? (
          <Empty icon={Layers} title="No legs yet" description="Load a preset or add legs manually to see the payoff diagram." />
        ) : (
          <DataTable
            columns={[
              { key: "action", header: "Action", render: (r) => <StatusPill status={text(r, "action")} /> },
              { key: "type", header: "Type", render: (r) => text(r, "type") },
              { key: "strike", header: "Strike", align: "right", render: (r) => num(r, "strike", 0) },
              { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "qty", 0) },
              { key: "premium", header: "Premium", align: "right", render: (r) => formatCurrency(num(r, "premium", 0)) },
              { key: "x", header: "", render: (r) => <Button size="sm" variant="subtle" onClick={() => removeLeg(text(r, "id"))}>×</Button> },
            ]}
            rows={legs as unknown as LiveRow[]}
            rowKey={(r) => text(r, "id")}
            dense
          />
        )}
      </Panel>

      {legs.length > 0 && (
        <Panel icon={LineChart} title="Payoff at Expiry">
          <AreaSeriesChart data={payoff as unknown as Record<string, number | string>[]} series={[{ key: "pnl", name: "P&L", color: "#0f766e" }]} xKey="spot" height={300} yFormat={(v) => formatCompact(v)} />
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)", textAlign: "center", marginTop: "var(--space-2)" }}>Spot at <strong>{spot.toFixed(0)}</strong>. Breakevens where the curve crosses zero.</div>
        </Panel>
      )}

      <AddLegDrawer open={showAdd} onClose={() => setShowAdd(false)} onAdd={addLeg} defaultStrike={atmStrike} />
    </>
  );
}

function AddLegDrawer({ open, onClose, onAdd, defaultStrike }: { open: boolean; onClose: () => void; onAdd: (leg: Omit<Leg, "id">) => void; defaultStrike: number }) {
  const [leg, setLeg] = React.useState<Omit<Leg, "id">>({ type: "CE", action: "buy", strike: defaultStrike, qty: 1, premium: 0 });
  React.useEffect(() => {
    if (open) setLeg({ type: "CE", action: "buy", strike: defaultStrike, qty: 1, premium: 0 });
  }, [open, defaultStrike]);
  return (
    <Drawer open={open} onClose={onClose} title="Add Leg" icon={Plus} width={440}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Plus} onClick={() => onAdd(leg)} disabled={leg.strike <= 0 || leg.premium <= 0 || leg.qty <= 0}>Add</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Type"><Select value={leg.type} onChange={(e) => setLeg({ ...leg, type: e.target.value as "CE" | "PE" })}><option>CE</option><option>PE</option></Select></Field>
          <Field label="Action"><Select value={leg.action} onChange={(e) => setLeg({ ...leg, action: e.target.value as "buy" | "sell" })}><option value="buy">Buy</option><option value="sell">Sell</option></Select></Field>
        </div>
        <Field label="Strike"><TextInput type="number" value={leg.strike} onChange={(e) => setLeg({ ...leg, strike: Number(e.target.value) })} /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Quantity"><TextInput type="number" value={leg.qty} onChange={(e) => setLeg({ ...leg, qty: Number(e.target.value) })} /></Field>
          <Field label="Premium"><TextInput type="number" value={leg.premium} onChange={(e) => setLeg({ ...leg, premium: Number(e.target.value) })} /></Field>
        </div>
      </div>
    </Drawer>
  );
}

/* ============================================================
 * AGENT
 * ============================================================ */
function AgentView() {
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);
  const prompts = [
    "Analyze the NIFTY OI buildup — where is resistance and support forming?",
    "What's the max pain for this week's BANKNIFTY expiry?",
    "Build an iron condor thesis for NIFTY given current IV",
    "Is the put-call skew signaling a hedge?",
    "Which strikes have the biggest OI change today?",
  ];
  return (
    <Panel icon={Brain} title="Options Agent">
      <div style={{ padding: "var(--space-6)", textAlign: "center" }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", margin: "0 auto var(--space-4)", background: "var(--accent-soft)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}><Brain size={32} /></div>
        <h3 style={{ marginBottom: "var(--space-1)" }}>Options Specialist</h3>
        <p style={{ color: "var(--text-muted)", maxWidth: 420, margin: "0 auto var(--space-5)" }}>OI analysis, vol surface reading, strategy construction, and edge identification. Talks you through the Greeks and the flow.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", maxWidth: 480, margin: "0 auto" }}>
          {prompts.map((p) => (
            <button key={p} onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); sessionStorage.setItem("aios:pending-charlie-question", p); }}
              style={{ padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-sm)", color: "var(--text-secondary)", textAlign: "left" }}>{p}</button>
          ))}
        </div>
        <Button variant="primary" icon={Brain} style={{ marginTop: "var(--space-5)" }} onClick={() => { setAssistantScope({ agentKey: "options_agent", agentName: "Options Agent" }); setAssistantOpen(true); }}>Open options agent chat</Button>
      </div>
    </Panel>
  );
}

/* ============================================================
 * Manual ticket
 * ============================================================ */
function OptionTicketDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const tradeMut = useRecordManualTrade();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({ symbol: "", side: "buy" as "buy" | "sell", lot_count: 1, lot_size: 0, price: 0, option_type: "CE", strike: 0, expiry_date: "", notes: "" });

  function submit() {
    if (!form.symbol || !form.strike || !form.expiry_date || form.lot_count <= 0 || form.lot_size <= 0) { pushToast({ title: "Complete the option contract", message: "Symbol, strike, expiry, lots, and lot size are required.", tone: "warn", duration: 3500 }); return; }
    const contractQuantity = Number(form.lot_count) * Number(form.lot_size);
    tradeMut.mutate(
      {
        symbol: form.symbol,
        exchange: "NFO",
        instrument_type: "option",
        option_type: form.option_type as "CE" | "PE",
        strike: Number(form.strike),
        expiry_date: form.expiry_date,
        strategy_name: form.notes.trim() || undefined,
        setup_type: form.notes.trim() || "manual_option_trade",
        side: form.side,
        quantity: Number(form.lot_count),
        quantity_unit: "lots",
        lot_count: Number(form.lot_count),
        lot_size: Number(form.lot_size),
        contract_quantity: contractQuantity,
        price: Number(form.price),
        thesis: form.notes.trim() || undefined,
        notes: form.notes.trim() || undefined,
        tags: ["option", form.option_type.toLowerCase(), "manual_actual"],
        actor: "Devarsh",
      },
      { onSuccess: () => { pushToast({ title: "Option trade recorded", message: `${form.symbol} ${form.option_type} ${form.strike}`, tone: "ok", duration: 3000 }); onClose(); }, onError: (e) => pushToast({ title: "Record failed", message: e.message, tone: "risk", duration: 5000 }) }
    );
  }

  return (
    <Drawer open={open} onClose={onClose} title="Record Option Trade" icon={Plus} width={520}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Play} onClick={submit} disabled={tradeMut.isPending}>Record</Button></div>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <Field label="Underlying" required><TextInput value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} placeholder="e.g. NIFTY" /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Type"><Select value={form.option_type} onChange={(e) => setForm({ ...form, option_type: e.target.value })}><option>CE</option><option>PE</option></Select></Field>
          <Field label="Strike" required><TextInput type="number" value={form.strike} onChange={(e) => setForm({ ...form, strike: Number(e.target.value) })} /></Field>
          <Field label="Expiry" required><TextInput type="date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} /></Field>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Side"><Select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value as "buy" | "sell" })}><option value="buy">Buy</option><option value="sell">Sell</option></Select></Field>
          <Field label="Lots" required><TextInput type="number" min={1} value={form.lot_count} onChange={(e) => setForm({ ...form, lot_count: Number(e.target.value) })} /></Field>
          <Field label="Lot size" required><TextInput type="number" min={1} value={form.lot_size} onChange={(e) => setForm({ ...form, lot_size: Number(e.target.value) })} placeholder="From contract" /></Field>
          <Field label="Premium"><TextInput type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} /></Field>
        </div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{form.lot_count > 0 && form.lot_size > 0 ? `${form.lot_count} lot(s) × ${form.lot_size} = ${form.lot_count * form.lot_size} units` : "Enter the exchange contract lot size; it is stored with the trade."}</div>
        <Field label="Notes / Strategy"><TextArea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} placeholder="e.g. Bull call spread, earnings play, hedge..." /></Field>
        <div style={{ padding: "var(--space-3)", background: "var(--status-warn-soft)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", color: "var(--status-warn)" }}>
          <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} />Manual record only. No live order is placed.
        </div>
      </div>
    </Drawer>
  );
}

function SkeletonRows({ n = 3 }: { n?: number }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-2)" }}>{Array.from({ length: n }).map((_, i) => <Skeleton key={i} style={{ height: 44 }} />)}</div>;
}
