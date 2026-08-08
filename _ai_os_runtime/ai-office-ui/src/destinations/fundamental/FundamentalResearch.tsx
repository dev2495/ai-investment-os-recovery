/**
 * Fundamental Research Terminal — Buffett school
 *
 * Routes:  /fundamental/theses | /scorecards | /valuation | /coverage | /ideas
 *
 * The deep long-term investment research workspace. Built around the
 * holding thesis as the atomic unit, with 12 specialist scorecards,
 * valuation suite (DCF / multiples / reverse DCF / Monte Carlo),
 * coverage queue, and a fundamental idea generator.
 *
 * This is NOT the quant lab — it's the slow-money, deep-research home.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  BookOpen, Microscope, Calculator, ClipboardCheck, Lightbulb,
  FlaskConical, TrendingUp, AlertTriangle, ChevronRight, Sparkles,
  Users, Gavel, Wallet, BarChart3, Search, TrendingDown, ShieldCheck, Briefcase,
  Send, GitBranch, Target, FileText, Save, RefreshCw,
} from "lucide-react";
import { useResearchIdeas, usePortfolioOffice, useCompanyIRSources } from "../../data/queries";
import {
  useRunMonteCarlo, useGenerateThesisMemo, useGenerateResearchPacket,
  useUpdateChecklist, useUpdateValuation, useDispatchSpecialists,
  useOpenLongTermCommittee, useUpsertWatchlist,
  useRunInstitutionalFundamentalFactory,
  useReviewFundamentalEvidence,
  useReviewFundamentalOpinion,
  useSyncFundamentalRemediation,
  useSyncFundamentalCompanyIntake,
  useRegisterCompanyIRSource,
  useCollectCompanyIRSource,
} from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, ScrollList, KeyValue, Field, TextInput, TextArea, Select,
} from "../../system/primitives";
import { AreaSeriesChart, DonutChart } from "../../system/charts";
import { text, num, bool, timestamp, value, formatRelative, formatCompact, formatPercent, formatCurrency } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "theses", label: "Long-Term Theses", icon: BookOpen },
  { key: "scorecards", label: "Scorecards", icon: Microscope },
  { key: "valuation", label: "Valuation Suite", icon: Calculator },
  { key: "coverage", label: "Coverage", icon: ClipboardCheck },
  { key: "dossiers", label: "Company Dossiers", icon: FileText },
  { key: "ideas", label: "Idea Generator", icon: Lightbulb },
];

export default function FundamentalResearch({ defaultTab = "theses" }: { defaultTab?: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;

  function setTab(key: string) {
    navigate(`/fundamental/${key}`);
  }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <BookOpen size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Fundamental Research
          </div>
          <Badge tone="accent">LTF</Badge>
          <span style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
            Buffett school · slow money · deep theses
          </span>
        </div>
        <div className="aios-destination__subtitle">
          Long-term investment theses, 12 specialist scorecards, valuation suite, and idea generation.
          Separated from quant — this is about business quality, not signal noise.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      <FundamentalFactoryControl />

      {tab === "theses" && <ThesesView />}
      {tab === "scorecards" && <ScorecardsView />}
      {tab === "valuation" && <ValuationView />}
      {tab === "coverage" && <CoverageView />}
      {tab === "dossiers" && <DossiersView />}
      {tab === "ideas" && <IdeasView />}
    </div>
  );
}
function FundamentalFactoryControl() {
  const mutation = useRunInstitutionalFundamentalFactory();
  const intakeMutation = useSyncFundamentalCompanyIntake();
  const { data } = useResearchIdeas();
  const intake = data?.fundamental_intake ?? [];
  const pushToast = useUIStore((state) => state.pushToast);
  const [form, setForm] = React.useState({
    symbol: "",
    exchange: "NSE",
    as_of: localDateTimeInputValue(),
    mode: "dry_run",
  });
  const ready = Boolean(form.symbol.trim() && form.exchange && form.as_of);

  function run() {
    if (!ready) return;
    mutation.mutate({
      symbol: form.symbol.trim().toUpperCase(),
      exchange: form.exchange,
      as_of: new Date(form.as_of).toISOString(),
      dry_run: form.mode === "dry_run",
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        const acceptance = text(result, "acceptance_status", text(result, "status", "completed"));
        const failed = value<string[]>(result, "failed_gates", []);
        pushToast({
          title: acceptance === "passed" ? "Fundamental acceptance passed" : "Fundamental acceptance remains blocked",
          message: failed.length ? `${failed.length} gates need evidence: ${failed.slice(0, 4).join(", ")}` : acceptance,
          tone: acceptance === "passed" ? "ok" : "warn",
          duration: 6500,
        });
      },
      onError: (error) => pushToast({ title: "Fundamental factory failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  function syncIntake() {
    intakeMutation.mutate({
      symbol: form.symbol.trim().toUpperCase() || undefined,
      actor: "Devarsh",
    }, {
      onSuccess: (result) => pushToast({
        title: "Real-company intake synchronized",
        message: `${num(result, "holding_candidates")} holdings mapped; ${num(result, "filing_evidence_upserted")} new official filings linked. Missing financial history remains blocked.`,
        tone: "ok",
        duration: 6500,
      }),
      onError: (error) => pushToast({ title: "Company intake failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  return (
    <Panel
      icon={RefreshCw}
      title="Run Institutional Fundamental Factory"
      actions={<Badge tone={mutation.isPending ? "warn" : mutation.isError ? "risk" : mutation.isSuccess ? "ok" : "accent"}>{mutation.isPending ? "Running" : mutation.isError ? "Failed" : mutation.isSuccess ? "Complete" : "Operator"}</Badge>}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
        <Field label="Company symbol" required><TextInput value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value.toUpperCase() })} placeholder="RELIANCE" /></Field>
        <Field label="Exchange" required><Select value={form.exchange} onChange={(event) => setForm({ ...form, exchange: event.target.value })}><option value="NSE">NSE</option><option value="BSE">BSE</option></Select></Field>
        <Field label="Research cutoff" required><TextInput type="datetime-local" value={form.as_of} onChange={(event) => setForm({ ...form, as_of: event.target.value })} /></Field>
        <Field label="Run mode" required><Select value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value })}><option value="dry_run">Dry run — validate only</option><option value="persist">Persist validated research</option></Select></Field>
        <Button variant="ghost" icon={RefreshCw} onClick={syncIntake} disabled={intakeMutation.isPending}>{intakeMutation.isPending ? "Synchronizing…" : form.symbol.trim() ? "Sync company evidence" : "Sync holdings & filings"}</Button>
        <Button variant="primary" icon={RefreshCw} onClick={run} disabled={!ready || mutation.isPending}>{mutation.isPending ? "Running…" : form.mode === "dry_run" ? "Validate factory" : "Run factory"}</Button>
      </div>
      <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
        Dry run is the default. This assembles evidence, dossiers, specialist gates and committee readiness; it cannot place or propose a broker order.
      </div>
      {intake.length > 0 ? (
        <div style={{ marginTop: "var(--space-4)" }}>
          <DataTable
            rows={intake.slice(0, 8)}
            rowKey={(row, index) => text(row, "company_key", String(index))}
            columns={[
              { key: "company", header: "Portfolio company", render: (row) => <strong>{text(row, "legal_name")}</strong> },
              { key: "symbol", header: "Symbol", render: (row) => `${text(row, "primary_exchange")}:${text(row, "primary_symbol")}` },
              { key: "exposure", header: "Gross exposure", align: "right", render: (row) => formatCurrency(num(row, "gross_market_value")) },
              { key: "identity", header: "Identity", render: (row) => <StatusPill status={bool(row, "identity_verified") ? "verified" : "evidence required"} /> },
              { key: "filings", header: "Official filings", align: "right", render: (row) => num(row, "filing_evidence_count") },
              { key: "next", header: "Next required evidence", render: (row) => text(row, "next_required_action").replace(/_/g, " ") },
            ]}
          />
        </div>
      ) : null}
      {mutation.isError ? <div role="alert" style={{ marginTop: "var(--space-3)", color: "var(--status-risk)", fontSize: "var(--text-sm)" }}>{mutation.error.message}</div> : null}
      {mutation.isSuccess ? (() => {
        const acceptance = text(mutation.data, "acceptance_status", text(mutation.data, "status", "completed"));
        const gates = acceptanceGateRows(mutation.data);
        const failed = gates.filter((gate) => text(gate, "gate_status", text(gate, "status")) !== "passed");
        return (
          <div role="status" style={{ marginTop: "var(--space-3)" }}>
            <div style={{ color: acceptance === "passed" ? "var(--status-ok)" : "var(--status-warn)", fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
              <strong>{acceptance === "passed" ? "Institutional acceptance passed." : "Institutional acceptance not passed."}</strong>{" "}
              {failed.length ? `${failed.length} gates require work.` : text(mutation.data, "run_key", form.mode === "dry_run" ? "No records were written." : "Validated research records were refreshed.")}
            </div>
            {gates.length ? <AcceptanceGateTable gates={gates} /> : null}
          </div>
        );
      })() : null}
    </Panel>
  );
}


/* ============================================================
 * THESES VIEW — the master list + detail drawer
 * ============================================================ */
function ThesesView() {
  const { data, isLoading } = useResearchIdeas();
  const pushToast = useUIStore((s) => s.pushToast);
  const theses = data?.long_term_theses ?? [];
  const [selected, setSelected] = React.useState<LiveRow | null>(null);
  const memoMut = useGenerateThesisMemo();
  const [showStart, setShowStart] = React.useState(false);
  const [holdingForm, setHoldingForm] = React.useState({ symbol: "", exchange: "NSE" });

  const generateFromHolding = () => {
    const symbol = holdingForm.symbol.trim().toUpperCase();
    if (!symbol) {
      pushToast({ title: "Symbol is required", tone: "warn", duration: 3000 });
      return;
    }
    memoMut.mutate({ symbol, exchange: holdingForm.exchange.trim().toUpperCase() || "NSE", actor: "Devarsh" }, {
      onSuccess: () => { pushToast({ title: "Long-term thesis initialized", message: "The persisted memo, scorecards, valuation shell, review task, and inbox item were created from live long-term exposure.", tone: "ok", duration: 5000 }); setShowStart(false); setHoldingForm({ symbol: "", exchange: "NSE" }); },
      onError: (error) => pushToast({ title: "Thesis initialization failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  };

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Active Theses" value={theses.length} /></MetricTile>
        <MetricTile><Metric label="Coverage Queue" value={data?.coverage_queue?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Monte Carlo Runs" value={data?.long_term_monte_carlo_runs?.length ?? 0} /></MetricTile>
        <MetricTile tone="warn"><Metric label="Committee Queue" value={data?.committee_queue?.length ?? 0} /></MetricTile>
      </div>

      <Panel icon={BookOpen} title="Long-Term Theses" actions={<div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}><Button size="sm" variant="primary" icon={BookOpen} onClick={() => setShowStart(true)}>Generate from holding</Button>{theses.length > 0 ? <Badge dot>{theses.length}</Badge> : null}</div>}>
        {isLoading ? (
          <SkeletonGrid rows={4} />
        ) : theses.length === 0 ? (
          <Empty icon={BookOpen} title="No long-term theses yet" description="Theses are generated per holding once research packets are built. Use the Idea Generator to start coverage for a candidate." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "company", header: "Company", render: (r) => text(r, "company_name", text(r, "name")) },
              { key: "quality", header: "Quality", align: "right", render: (r) => <ScoreBar score={num(r, "quality_score", 0)} max={10} /> },
              { key: "moat", header: "Moat", align: "right", render: (r) => <ScoreBar score={num(r, "moat_score", 0)} max={10} /> },
              { key: "horizon", header: "Horizon", render: (r) => text(r, "horizon", "long-term") },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "active")} /> },
              { key: "updated", header: "Updated", render: (r) => <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{formatRelative(text(r, "updated_at", text(r, "last_review_at")))}</span> },
            ]}
            rows={theses}
            rowKey={(r, i) => String(text(r, "holding_thesis_id", text(r, "id", i)))}
            onRowClick={(r) => setSelected(r)}
          />
        )}
      </Panel>

      <ThesisDetailDrawer thesis={selected} onClose={() => setSelected(null)} />
      <Drawer open={showStart} onClose={() => setShowStart(false)} title="Generate thesis from live holding" subtitle="Initializes coverage from canonical long-term book exposure" icon={BookOpen} width={520}
        footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={() => setShowStart(false)}>Cancel</Button><Button variant="primary" icon={BookOpen} onClick={generateFromHolding} disabled={memoMut.isPending || !holdingForm.symbol.trim()}>Generate thesis</Button></div>}>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <Field label="Holding symbol" required><TextInput value={holdingForm.symbol} onChange={(event) => setHoldingForm({ ...holdingForm, symbol: event.target.value.toUpperCase() })} placeholder="RELIANCE" /></Field>
          <Field label="Exchange"><Select value={holdingForm.exchange} onChange={(event) => setHoldingForm({ ...holdingForm, exchange: event.target.value })}><option value="NSE">NSE</option><option value="BSE">BSE</option></Select></Field>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>The symbol must already have active long-term exposure in the canonical book. No position or recommendation is created.</div>
        </div>
      </Drawer>
    </>
  );
}

function ThesisDetailDrawer({ thesis, onClose }: { thesis: LiveRow | null; onClose: () => void }) {
  const thesisId = num(thesis, "holding_thesis_id", num(thesis, "id", 0));
  const symbol = text(thesis, "symbol", "");
  const company = text(thesis, "company_name", text(thesis, "name", ""));
  const memoMut = useGenerateThesisMemo();
  const packetMut = useGenerateResearchPacket();
  const dispatchMut = useDispatchSpecialists();
  const committeeMut = useOpenLongTermCommittee();
  const watchlistMut = useUpsertWatchlist();
  const pushToast = useUIStore((s) => s.pushToast);

  const [memoText, setMemoText] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);

  React.useEffect(() => {
    setMemoText(text(thesis, "thesis_memo", text(thesis, "memo", "")));
  }, [thesis]);

  function run(label: string, mut: { mutate: (input: any, opts?: any) => void }, input: Record<string, unknown>, okMsg: string) {
    setBusy(label);
    mut.mutate(input, {
      onSuccess: () => { pushToast({ title: okMsg, tone: "ok", duration: 3000 }); setBusy(null); },
      onError: (e: Error) => { pushToast({ title: `${label} failed`, message: e.message, tone: "risk", duration: 5000 }); setBusy(null); },
    });
  }

  return (
    <Drawer
      open={Boolean(thesis)}
      onClose={onClose}
      title={symbol ? `${symbol} — ${company}` : "Thesis"}
      subtitle="Long-term investment thesis"
      icon={BookOpen}
      width={620}
      actions={thesisId > 0 ? (
        <>
          <Button size="sm" variant="ghost" icon={Send} onClick={() => run("Watchlist", watchlistMut, { symbol, item_type: "research", priority: "medium", actor: "Devarsh" }, "Added to watchlist")}>Watchlist</Button>
          <Button size="sm" variant="ghost" icon={GitBranch} onClick={() => run("Committee", committeeMut, { holding_thesis_id: thesisId, actor: "Devarsh" }, "Opened committee review")} disabled={busy !== null}>Committee</Button>
        </>
      ) : undefined}
    >
      {!thesis ? null : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Thesis meta */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
            <MetricTile><Metric label="Quality" value={num(thesis, "quality_score", 0).toFixed(1)} size="sm" sub="of 10" /></MetricTile>
            <MetricTile><Metric label="Moat" value={num(thesis, "moat_score", 0).toFixed(1)} size="sm" sub="of 10" /></MetricTile>
          </div>

          {/* Thesis memo */}
          <Panel variant="soft" icon={FileText} title="Thesis Memo"
            actions={<Button size="sm" variant="ghost" icon={Sparkles} onClick={() => run("Memo", memoMut, { holding_thesis_id: thesisId, actor: "Devarsh" }, "Thesis memo generated")} disabled={busy !== null}>Generate</Button>}
          >
            <TextArea value={memoText} onChange={(e) => setMemoText(e.target.value)} rows={8} placeholder="The core investment thesis — what you own and why." />
          </Panel>

          {/* Killer risks */}
          <Panel variant="soft" icon={AlertTriangle} title="Thesis Killers">
            <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
              {text(thesis, "thesis_killers", text(thesis, "killers", "Not yet documented. Dispatch the Risk Review specialist to surface them."))}
            </div>
          </Panel>

          {/* Actions: build the full research packet */}
          <Panel variant="soft" icon={FlaskConical} title="Deep Research Actions">
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              <Button size="sm" icon={FileText} onClick={() => run("Packet", packetMut, { holding_thesis_id: thesisId, actor: "Devarsh" }, "Research packet building")} disabled={busy !== null}>Build Research Packet</Button>
              <Button size="sm" icon={Microscope} onClick={() => run("Specialists", dispatchMut, { holding_thesis_id: thesisId, actor: "Devarsh" }, "Specialists dispatched")} disabled={busy !== null}>Dispatch Specialists</Button>
            </div>
            <div style={{ marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
              Research packet bundles quotes, positions, filings, and notes. Twelve independent specialists cover business model, moat, industry, management, governance, capital allocation, financial quality, forensics, valuation, bear case, portfolio fit, and risk.
            </div>
          </Panel>

          {/* Monte Carlo shortcut */}
          <Panel variant="soft" icon={TrendingUp} title="Valuation Monte Carlo">
            <MonteCarloInline thesisId={thesisId} />
          </Panel>
        </div>
      )}
    </Drawer>
  );
}

/** Compact Monte Carlo runner embedded in the thesis drawer. */
function MonteCarloInline({ thesisId }: { thesisId: number }) {
  const mcMut = useRunMonteCarlo();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({
    horizon_years: 5,
    simulations: 5000,
    terminal_multiple_low: 12,
    terminal_multiple_base: 18,
    terminal_multiple_high: 25,
    annual_volatility: 0.28,
  });

  function run() {
    mcMut.mutate({ holding_thesis_id: thesisId, actor: "Devarsh", ...form }, {
      onSuccess: (r) => pushToast({ title: "Monte Carlo complete", message: `Median: ${formatCompact(num(r as LiveRow, "median_outcome", 0), "INR")}`, tone: "ok", duration: 4000 }),
      onError: (e) => pushToast({ title: "Monte Carlo failed", message: e.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-2)" }}>
        <Field label="Horizon (yrs)"><TextInput type="number" value={form.horizon_years} onChange={(e) => setForm({ ...form, horizon_years: Number(e.target.value) })} /></Field>
        <Field label="Simulations"><TextInput type="number" value={form.simulations} onChange={(e) => setForm({ ...form, simulations: Number(e.target.value) })} /></Field>
        <Field label="Volatility"><TextInput type="number" step="0.01" value={form.annual_volatility} onChange={(e) => setForm({ ...form, annual_volatility: Number(e.target.value) })} /></Field>
        <Field label="Mult Low"><TextInput type="number" value={form.terminal_multiple_low} onChange={(e) => setForm({ ...form, terminal_multiple_low: Number(e.target.value) })} /></Field>
        <Field label="Mult Base"><TextInput type="number" value={form.terminal_multiple_base} onChange={(e) => setForm({ ...form, terminal_multiple_base: Number(e.target.value) })} /></Field>
        <Field label="Mult High"><TextInput type="number" value={form.terminal_multiple_high} onChange={(e) => setForm({ ...form, terminal_multiple_high: Number(e.target.value) })} /></Field>
      </div>
      <Button size="sm" icon={TrendingUp} onClick={run} disabled={mcMut.isPending}>Run Monte Carlo</Button>
    </div>
  );
}

/* ============================================================
 * SCORECARDS VIEW — the 12 specialist modules
 * ============================================================ */
const SPECIALIST_MODULES = [
  { key: "business_model", label: "Business Model", icon: Target },
  { key: "moat_scorecard", label: "Moat Scorecard", icon: ShieldCheck },
  { key: "industry_structure", label: "Industry Structure", icon: GitBranch },
  { key: "management_scorecard", label: "Management", icon: Users },
  { key: "governance_scorecard", label: "Governance", icon: Gavel },
  { key: "capital_allocation", label: "Capital Allocation", icon: Wallet },
  { key: "financial_quality", label: "Financial Quality", icon: BarChart3 },
  { key: "forensic_accounting", label: "Forensic Accounting", icon: Search },
  { key: "valuation_suite", label: "Valuation Suite", icon: Calculator },
  { key: "bear_case", label: "Bear Case", icon: TrendingDown },
  { key: "portfolio_fit", label: "Portfolio Fit & Opportunity Cost", icon: Briefcase },
  { key: "risk_review", label: "Risk Review", icon: AlertTriangle },
];

function ScorecardsView() {
  const { data, isLoading } = useResearchIdeas();
  const dispatchMut = useDispatchSpecialists();
  const remediationMut = useSyncFundamentalRemediation();
  const pushToast = useUIStore((s) => s.pushToast);
  const outputs = data?.long_term_research_updates ?? [];
  const checklists = data?.long_term_checklists ?? [];
  const theses = data?.long_term_theses ?? [];
  const opinions = data?.fundamental_specialist_opinions ?? [];
  const governanceObservations = data?.governance_forensic_observations ?? [];
  const remediationTasks = data?.fundamental_remediation_tasks ?? [];
  const [selectedThesis, setSelectedThesis] = React.useState<string>("");
  const [selectedChecklist, setSelectedChecklist] = React.useState<LiveRow | null>(null);
  const [selectedOpinion, setSelectedOpinion] = React.useState<LiveRow | null>(null);

  function runAll() {
    if (!selectedThesis) {
      pushToast({ title: "Pick a thesis first", tone: "warn", duration: 2500 });
      return;
    }
    dispatchMut.mutate(
      { holding_thesis_id: Number(selectedThesis), actor: "Devarsh" },
      { onSuccess: () => pushToast({ title: "All 12 specialists dispatched", tone: "ok", duration: 3000 }), onError: (e: Error) => pushToast({ title: "Dispatch failed", message: e.message, tone: "risk", duration: 5000 }) }
    );
  }

  function createRemediationWork() {
    if (!selectedThesis) {
      pushToast({ title: "Pick a thesis first", tone: "warn", duration: 2500 });
      return;
    }
    remediationMut.mutate(
      { holding_thesis_id: Number(selectedThesis), operator_confirmed: true, actor: "Devarsh" },
      {
        onSuccess: (result) => pushToast({
          title: "Remediation work synchronized",
          message: `${num(result, "created_task_count")} new tasks across ${num(result, "unresolved_lane_count")} unresolved lanes.`,
          tone: "ok",
          duration: 4500,
        }),
        onError: (error) => pushToast({ title: "Remediation sync failed", message: error.message, tone: "risk", duration: 6000 }),
      }
    );
  }

  const selectedOpinions = selectedThesis
    ? opinions.filter((row) => num(row, "holding_thesis_id") === Number(selectedThesis))
    : opinions;
  const selectedThesisRow = theses.find((row) => num(row, "holding_thesis_id", num(row, "id")) === Number(selectedThesis));
  const selectedSymbol = selectedThesisRow ? text(selectedThesisRow, "symbol", text(selectedThesisRow, "holding_symbol")) : "";
  const selectedGovernanceObservations = selectedSymbol
    ? governanceObservations.filter((row) => text(row, "primary_symbol").toUpperCase() === selectedSymbol.toUpperCase())
    : governanceObservations;

  return (
    <>
      <Panel icon={Microscope} title="12 Specialist Scorecards"
        actions={
          <>
            <Select value={selectedThesis} onChange={(e) => setSelectedThesis(e.target.value)} style={{ width: 200 }}>
              <option value="">Pick a thesis…</option>
              {theses.map((t, i) => <option key={i} value={text(t, "holding_thesis_id", text(t, "id", i))}>{text(t, "symbol")} — {text(t, "company_name", text(t, "name"))}</option>)}
            </Select>
            <Button size="sm" icon={Sparkles} onClick={runAll} disabled={dispatchMut.isPending}>Dispatch All</Button>
            <Button size="sm" variant="subtle" icon={Send} onClick={createRemediationWork} disabled={remediationMut.isPending}>Assign Gaps</Button>
          </>
        }
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
          {SPECIALIST_MODULES.map((mod) => {
            const found = selectedThesis
              ? checklists.find((row) => num(row, "holding_thesis_id", 0) === Number(selectedThesis)
                  && text(row, "checklist_key") === mod.key)
              : null;
            return (
              <div key={mod.key} style={{ padding: "var(--space-3)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                  <mod.icon size={16} style={{ color: "var(--accent)" }} />
                  <strong style={{ fontSize: "var(--text-sm)" }}>{mod.label}</strong>
                </div>
                {found ? (
                  <>
                    <StatusPill status={text(found, "status", "complete")} />
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", marginTop: 4 }}>
                      {formatRelative(text(found, "completed_at", text(found, "updated_at")))}
                    </div>
                  </>
                ) : (
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{selectedThesis ? "Not yet initialized" : "Pick a thesis"}</div>
                )}
                {found ? <Button size="sm" variant="subtle" icon={ClipboardCheck} onClick={() => setSelectedChecklist(found)} style={{ marginTop: "var(--space-3)" }}>Review</Button> : null}
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel icon={ShieldCheck} title="Institutional Specialist Opinions" actions={<Badge tone={selectedOpinions.some((row) => ["draft", "rejected", "stale"].includes(text(row, "opinion_status"))) ? "warn" : "ok"}>{selectedOpinions.length} latest lanes</Badge>}>
        {selectedOpinions.length === 0 ? (
          <Empty icon={Microscope} title="No institutional opinions" description="Run the company factory after intake to stage the evidence-first 12-lane review." />
        ) : (
          <DataTable rows={selectedOpinions} rowKey={(row, index) => text(row, "id", String(index))} columns={[
            { key: "specialist", header: "Specialist", render: (row) => <div><strong>{text(row, "specialist_key").replace(/_/g, " ")}</strong><div className="micro">{text(row, "agent_name")}</div></div> },
            { key: "status", header: "Opinion", render: (row) => <StatusPill status={text(row, "opinion_status")} /> },
            { key: "conclusion", header: "Current conclusion", render: (row) => text(row, "conclusion") },
            { key: "followups", header: "Required follow-ups", render: (row) => compactJson(value(row, "required_followups", [])) },
            { key: "evidence", header: "Evidence", render: (row) => <StatusPill status={text(row, "evidence_verification_status")} /> },
          ]} onRowClick={setSelectedOpinion} />
        )}
      </Panel>

      <Panel icon={Gavel} title="Governance & Forensic Evidence" actions={<Badge tone={selectedGovernanceObservations.some((row) => ["high", "critical"].includes(text(row, "severity"))) ? "risk" : "ok"}>{selectedGovernanceObservations.length} cited observations</Badge>}>
        {selectedGovernanceObservations.length === 0 ? (
          <Empty icon={Search} title="No structured governance review" description="Run the annual-report governance extractor after a primary report is retained." />
        ) : (
          <DataTable rows={selectedGovernanceObservations} rowKey={(row, index) => text(row, "id", String(index))} columns={[
            { key: "issue", header: "Observation", render: (row) => <div><strong>{text(row, "observation_key").replace(/_/g, " ")}</strong><div className="micro">{text(row, "category").replace(/_/g, " ")}</div></div> },
            { key: "severity", header: "Severity", render: (row) => <StatusPill status={text(row, "severity")} /> },
            { key: "status", header: "Disclosure", render: (row) => <StatusPill status={text(row, "observation_status")} /> },
            { key: "conclusion", header: "Conclusion", render: (row) => text(row, "conclusion") },
            { key: "page", header: "Page", align: "right", render: (row) => num(row, "source_page") },
            { key: "source", header: "Source", render: (row) => {
              const url = text(row, "source_url");
              return /^https?:\/\//i.test(url) ? <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>Open report</a> : text(row, "source_title");
            } },
          ]} />
        )}
        {selectedGovernanceObservations.length > 0 ? (
          <div style={{ padding: "var(--space-3)", borderTop: "1px solid var(--border-subtle)", color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>
            Machine extraction completes the checklist but does not clear an issue. Open the cited report and use the evidence review workflow before marking evidence human verified.
          </div>
        ) : null}
      </Panel>

      <Panel icon={Send} title="Fundamental Remediation Queue" actions={<Badge tone={remediationTasks.some((row) => ["queued", "in_progress", "needs_review"].includes(text(row, "status"))) ? "warn" : "ok"}>{remediationTasks.length} tasks</Badge>}>
        {remediationTasks.length === 0 ? (
          <Empty icon={Send} title="No remediation tasks" description="Use Assign Gaps to route unresolved specialist evidence and calculations to their owning agents." />
        ) : (
          <DataTable rows={remediationTasks} rowKey={(row, index) => text(row, "id", String(index))} columns={[
            { key: "task", header: "Work", render: (row) => <strong>{text(row, "title")}</strong> },
            { key: "owner", header: "Owner", render: (row) => text(row, "owner_agent") },
            { key: "priority", header: "Priority", render: (row) => <StatusPill status={text(row, "priority")} /> },
            { key: "status", header: "Task", render: (row) => <StatusPill status={text(row, "status")} /> },
            { key: "inbox", header: "Inbox", render: (row) => <StatusPill status={text(row, "inbox_status", "new")} /> },
          ]} />
        )}
      </Panel>

      <Panel icon={ClipboardCheck} title="Specialist Outputs">
        {isLoading ? <SkeletonGrid rows={3} /> : outputs.length === 0 ? (
          <Empty icon={Microscope} title="No specialist outputs yet" description="Pick a thesis above and dispatch the 12 independent specialist lanes." />
        ) : (
          <DataTable
            columns={[
              { key: "thesis", header: "Thesis", render: (r) => <strong>{text(r, "symbol", text(r, "holding_symbol"))}</strong> },
              { key: "module", header: "Module", render: (r) => text(r, "checklist_key", text(r, "model_key", text(r, "update_kind"))) },
              { key: "score", header: "Score", align: "right", render: (r) => num(r, "score", 0).toFixed(1) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "complete")} /> },
              { key: "when", header: "When", render: (r) => formatRelative(text(r, "completed_at", text(r, "updated_at"))) },
            ]}
            rows={outputs}
            rowKey={(r, i) => String(text(r, "output_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <ChecklistReviewDrawer checklist={selectedChecklist} onClose={() => setSelectedChecklist(null)} />
      <FundamentalOpinionReviewDrawer opinion={selectedOpinion} onClose={() => setSelectedOpinion(null)} />
    </>
  );
}

function FundamentalOpinionReviewDrawer({ opinion, onClose }: { opinion: LiveRow | null; onClose: () => void }) {
  const mutation = useReviewFundamentalOpinion();
  const pushToast = useUIStore((state) => state.pushToast);
  const [rationale, setRationale] = React.useState("");

  React.useEffect(() => {
    setRationale("");
    mutation.reset();
  }, [opinion?.id]);

  function review(decision: "reviewed" | "dissent" | "rejected") {
    if (!opinion || rationale.trim().length < 12) return;
    mutation.mutate({
      opinion_id: num(opinion, "id"),
      decision,
      rationale: rationale.trim(),
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        pushToast({
          title: decision === "reviewed" ? "Specialist opinion reviewed" : decision === "dissent" ? "Dissent preserved" : "Specialist opinion rejected",
          message: text(opinion, "specialist_key").replace(/_/g, " "),
          tone: decision === "reviewed" ? "ok" : "warn",
          duration: 5000,
        });
        onClose();
      },
      onError: (error) => pushToast({ title: "Opinion review failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  const sourceUrl = opinion ? text(opinion, "source_url") : "";
  return (
    <Drawer open={Boolean(opinion)} onClose={onClose} title="Review Specialist Opinion" subtitle={opinion ? `${text(opinion, "primary_exchange")}:${text(opinion, "primary_symbol")} / ${text(opinion, "specialist_key").replace(/_/g, " ")}` : ""} icon={Microscope} width={760}>
      {opinion ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <Panel title={text(opinion, "agent_name")}>
            <KeyValue label="Opinion status" value={text(opinion, "opinion_status")} />
            <KeyValue label="Evidence status" value={text(opinion, "evidence_verification_status")} />
            <KeyValue label="Conclusion" value={text(opinion, "conclusion")} />
            <KeyValue label="Disconfirming evidence" value={text(opinion, "disconfirming_evidence", "None recorded")} />
            <KeyValue label="Required follow-ups" value={compactJson(value(opinion, "required_followups", []))} />
            {/^https?:\/\//i.test(sourceUrl) ? <a href={sourceUrl} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: "var(--text-sm)" }}>Open supporting source</a> : null}
          </Panel>
          <Field label="Operator review rationale" required>
            <TextArea rows={5} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Record whether the conclusion is supported, what remains unresolved, and why this review status is appropriate." />
          </Field>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button variant="ghost" icon={AlertTriangle} onClick={() => review("rejected")} disabled={rationale.trim().length < 12 || mutation.isPending}>Reject</Button>
            <Button variant="subtle" icon={TrendingDown} onClick={() => review("dissent")} disabled={rationale.trim().length < 12 || mutation.isPending}>Preserve dissent</Button>
            <Button variant="primary" icon={ShieldCheck} onClick={() => review("reviewed")} disabled={rationale.trim().length < 12 || mutation.isPending}>{mutation.isPending ? "Saving review..." : "Mark reviewed"}</Button>
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}

/* ============================================================
 * VALUATION VIEW — DCF, multiples, reverse DCF, Monte Carlo
 * ============================================================ */
function ValuationView() {
  const { data, isLoading } = useResearchIdeas();
  const mcRuns = data?.long_term_monte_carlo_runs ?? [];
  const models = data?.long_term_valuation_models ?? [];
  const [selected, setSelected] = React.useState<LiveRow | null>(null);
  const [selectedMonteCarlo, setSelectedMonteCarlo] = React.useState<LiveRow | null>(null);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Valuation Models" value={models.length} /></MetricTile>
        <MetricTile><Metric label="Monte Carlo Runs" value={mcRuns.length} /></MetricTile>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={Calculator} title="Valuation Models">
          {isLoading ? <SkeletonGrid rows={3} /> : models.length === 0 ? (
            <Empty icon={Calculator} title="No valuation models" description="Valuation models are created per thesis. Open a thesis to build one." />
          ) : (
            <DataTable
              columns={[
                { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
                { key: "type", header: "Model", render: (r) => text(r, "model_name", text(r, "model_type", "Valuation")) },
                { key: "range", header: "Fair Value Range", align: "right", render: (r) => `${formatCurrency(num(r, "fair_value_low", 0))} / ${formatCurrency(num(r, "fair_value_base", 0))} / ${formatCurrency(num(r, "fair_value_high", 0))}` },
                { key: "cagr", header: "Expected CAGR", align: "right", render: (r) => num(r, "expected_cagr_pct", 0) ? formatPercent(num(r, "expected_cagr_pct", 0), { alreadyPercent: true }) : "—" },
                { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "active")} /> },
              ]}
              rows={models}
              rowKey={(r, i) => String(text(r, "valuation_model_id", text(r, "id", i)))}
              onRowClick={setSelected}
            />
          )}
        </Panel>

        <Panel icon={TrendingUp} title="Monte Carlo Runs">
          {isLoading ? <Skeleton style={{ height: 200 }} /> : mcRuns.length === 0 ? (
            <Empty icon={TrendingUp} title="No Monte Carlo runs" description="Run a Monte Carlo from a thesis drawer to see distribution outcomes here." />
          ) : (
            <ScrollList>
              {mcRuns.slice(0, 10).map((run, i) => (
                <button key={i} type="button" onClick={() => setSelectedMonteCarlo(run)} style={{ width: "100%", textAlign: "left", color: "inherit", background: "transparent", padding: "var(--space-3)", border: 0, borderBottom: "1px solid var(--border-subtle)", cursor: "pointer" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{text(run, "symbol", text(run, "holding_symbol"))}</strong>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{formatRelative(text(run, "ran_at", text(run, "created_at")))}</span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-2)", marginTop: "var(--space-2)", fontSize: "var(--text-xs)" }}>
                    <div><div className="micro">P10</div>{formatCompact(monteCarloTerminalPrice(run, "p10"), "INR")}</div>
                    <div><div className="micro">Median</div>{formatCompact(monteCarloTerminalPrice(run, "p50"), "INR")}</div>
                    <div><div className="micro">P90</div>{formatCompact(monteCarloTerminalPrice(run, "p90"), "INR")}</div>
                  </div>
                  <div style={{ marginTop: "var(--space-2)", display: "flex", gap: "var(--space-2)" }}><StatusPill status={text(run, "run_status", "needs_review")} /> {value<unknown[]>(run, "warnings", []).length ? <Badge tone="warn">{value<unknown[]>(run, "warnings", []).length} warning</Badge> : null}</div>
                </button>
              ))}
            </ScrollList>
          )}
        </Panel>
      </div>

      <ValuationModelDrawer model={selected} onClose={() => setSelected(null)} />
      <MonteCarloReviewDrawer run={selectedMonteCarlo} onClose={() => setSelectedMonteCarlo(null)} />
    </>
  );
}

function MonteCarloReviewDrawer({ run, onClose }: { run: LiveRow | null; onClose: () => void }) {
  return (
    <Drawer open={Boolean(run)} onClose={onClose} title={`${text(run, "symbol")} — Monte Carlo Review`} subtitle="Deterministic simulation inputs, outputs, warnings and lineage" icon={TrendingUp} width={760}>
      {run ? <div style={{ display: "grid", gap: "var(--space-4)" }}>
        <Panel title="Run control">
          <KeyValue label="Status" value={text(run, "run_status")} />
          <KeyValue label="Simulations" value={String(num(run, "simulation_count"))} />
          <KeyValue label="Horizon" value={`${num(run, "horizon_years")} years`} />
          <KeyValue label="Starting multiple" value={text(run, "starting_multiple", "—")} />
        </Panel>
        <Panel title="Blocking warnings">
          {value<unknown[]>(run, "warnings", []).length ? value<unknown[]>(run, "warnings", []).map((warning, index) => <div key={index} style={{ color: "var(--risk)", marginBottom: "var(--space-2)" }}>{String(warning)}</div>) : <StatusPill status="clear" />}
        </Panel>
        <Panel title="Assumptions"><pre style={{ whiteSpace: "pre-wrap", fontSize: "var(--text-xs)", margin: 0 }}>{jsonText(value(run, "assumptions", {}))}</pre></Panel>
        <Panel title="Input snapshot"><pre style={{ whiteSpace: "pre-wrap", fontSize: "var(--text-xs)", margin: 0 }}>{jsonText(value(run, "input_snapshot", {}))}</pre></Panel>
        <Panel title="Evidence lineage"><pre style={{ whiteSpace: "pre-wrap", fontSize: "var(--text-xs)", margin: 0 }}>{jsonText(value(run, "evidence", []))}</pre></Panel>
      </div> : null}
    </Drawer>
  );
}

function ChecklistReviewDrawer({ checklist, onClose }: { checklist: LiveRow | null; onClose: () => void }) {
  const mutation = useUpdateChecklist();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({ status: "in_progress", score: "", findings: "", evidence: "" });

  React.useEffect(() => {
    const findings = value<unknown[]>(checklist, "findings", []);
    const evidence = value<unknown[]>(checklist, "evidence", []);
    setForm({
      status: text(checklist, "status", "in_progress"),
      score: text(checklist, "score", ""),
      findings: listToLines(findings, "finding"),
      evidence: listToLines(evidence, "source"),
    });
  }, [checklist]);

  function submit() {
    const holdingThesisId = num(checklist, "holding_thesis_id", 0);
    const checklistKey = text(checklist, "checklist_key");
    const evidence = linesToEvidence(form.evidence);
    if (!holdingThesisId || !checklistKey) {
      pushToast({ title: "Checklist identity is missing", tone: "risk", duration: 4000 });
      return;
    }
    if (["complete", "reviewed"].includes(form.status) && evidence.length === 0) {
      pushToast({ title: "Source evidence is required", message: "Add filing, transcript, note, or dataset references before completing a scorecard.", tone: "warn", duration: 5000 });
      return;
    }
    mutation.mutate({
      holding_thesis_id: holdingThesisId,
      checklist_key: checklistKey,
      status: form.status,
      score: optionalNumber(form.score),
      findings: form.findings.split("\n").map((item) => item.trim()).filter(Boolean).map((finding) => ({ finding })),
      evidence,
      actor: "Devarsh",
    }, {
      onSuccess: () => { pushToast({ title: "Scorecard persisted", tone: "ok", duration: 3000 }); onClose(); },
      onError: (error) => pushToast({ title: "Scorecard update failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <Drawer
      open={Boolean(checklist)}
      onClose={onClose}
      title={`${text(checklist, "symbol")} — ${text(checklist, "checklist_name", text(checklist, "checklist_key"))}`}
      subtitle="Evidence-backed specialist scorecard"
      icon={ClipboardCheck}
      width={620}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Save} onClick={submit} disabled={mutation.isPending}>Save review</Button></div>}
    >
      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Field label="Status" required><Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="source_required">Source required</option><option value="complete">Complete</option><option value="reviewed">Reviewed</option></Select></Field>
          <Field label="Score (0-10)"><TextInput type="number" min="0" max="10" step="0.1" value={form.score} onChange={(event) => setForm({ ...form, score: event.target.value })} /></Field>
        </div>
        <Field label="Findings" hint="One finding per line"><TextArea rows={8} value={form.findings} onChange={(event) => setForm({ ...form, findings: event.target.value })} /></Field>
        <Field label="Evidence references" hint="One filing URL, document path, note ID, or dataset reference per line" required><TextArea rows={6} value={form.evidence} onChange={(event) => setForm({ ...form, evidence: event.target.value })} /></Field>
      </div>
    </Drawer>
  );
}

function ValuationModelDrawer({ model, onClose }: { model: LiveRow | null; onClose: () => void }) {
  const mutation = useUpdateValuation();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({
    status: "in_progress", fair_value_low: "", fair_value_base: "", fair_value_high: "",
    expected_cagr_pct: "", assumptions: "{}", outputs: "{}", evidence: "",
  });

  React.useEffect(() => {
    setForm({
      status: text(model, "status", "in_progress"),
      fair_value_low: text(model, "fair_value_low", ""),
      fair_value_base: text(model, "fair_value_base", ""),
      fair_value_high: text(model, "fair_value_high", ""),
      expected_cagr_pct: text(model, "expected_cagr_pct", ""),
      assumptions: jsonText(value(model, "assumptions", {})),
      outputs: jsonText(value(model, "outputs", {})),
      evidence: "",
    });
  }, [model]);

  function submit() {
    const holdingThesisId = num(model, "holding_thesis_id", 0);
    const modelKey = text(model, "model_key");
    const evidence = linesToEvidence(form.evidence);
    const low = optionalNumber(form.fair_value_low);
    const base = optionalNumber(form.fair_value_base);
    const high = optionalNumber(form.fair_value_high);
    if (!holdingThesisId || !modelKey) {
      pushToast({ title: "Valuation identity is missing", tone: "risk", duration: 4000 });
      return;
    }
    if (low !== undefined && base !== undefined && high !== undefined && !(low <= base && base <= high)) {
      pushToast({ title: "Fair-value range is invalid", message: "Low must be less than or equal to base, and base less than or equal to high.", tone: "warn", duration: 5000 });
      return;
    }
    let assumptions: Record<string, unknown>;
    let outputs: Record<string, unknown>;
    try {
      assumptions = parseJsonObject(form.assumptions, "Assumptions");
      outputs = parseJsonObject(form.outputs, "Outputs");
    } catch (error) {
      pushToast({ title: "Invalid JSON", message: error instanceof Error ? error.message : String(error), tone: "risk", duration: 5000 });
      return;
    }
    if (["complete", "reviewed"].includes(form.status) && (base === undefined || evidence.length === 0)) {
      pushToast({ title: "Completion requires value and evidence", message: "Add a base fair value and at least one source reference.", tone: "warn", duration: 5000 });
      return;
    }
    mutation.mutate({
      holding_thesis_id: holdingThesisId,
      model_key: modelKey,
      status: form.status,
      fair_value_low: low,
      fair_value_base: base,
      fair_value_high: high,
      expected_cagr_pct: optionalNumber(form.expected_cagr_pct),
      assumptions,
      outputs,
      evidence,
      operator_confirmed: form.status === "reviewed",
      actor: "Devarsh",
    }, {
      onSuccess: () => { pushToast({ title: "Valuation model persisted", message: text(model, "model_name", modelKey), tone: "ok", duration: 3500 }); onClose(); },
      onError: (error) => pushToast({ title: "Valuation update failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  }

  return (
    <Drawer
      open={Boolean(model)}
      onClose={onClose}
      title={`${text(model, "symbol")} — ${text(model, "model_name", text(model, "model_key"))}`}
      subtitle="Source-backed valuation workbench"
      icon={Calculator}
      width={700}
      footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Save} onClick={submit} disabled={mutation.isPending}>Save model</Button></div>}
    >
      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        <Field label="Status" required><Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="source_required">Source required</option><option value="complete">Complete</option><option value="reviewed">Reviewed</option></Select></Field>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "var(--space-3)" }}>
          <Field label="Bear / Low"><TextInput type="number" value={form.fair_value_low} onChange={(event) => setForm({ ...form, fair_value_low: event.target.value })} /></Field>
          <Field label="Base"><TextInput type="number" value={form.fair_value_base} onChange={(event) => setForm({ ...form, fair_value_base: event.target.value })} /></Field>
          <Field label="Bull / High"><TextInput type="number" value={form.fair_value_high} onChange={(event) => setForm({ ...form, fair_value_high: event.target.value })} /></Field>
          <Field label="Expected CAGR %"><TextInput type="number" step="0.1" value={form.expected_cagr_pct} onChange={(event) => setForm({ ...form, expected_cagr_pct: event.target.value })} /></Field>
        </div>
        <Field label="Assumptions (JSON)" hint="Growth, margins, discount rate, terminal multiple, peer set, or scenario weights"><TextArea rows={8} value={form.assumptions} onChange={(event) => setForm({ ...form, assumptions: event.target.value })} style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }} /></Field>
        <Field label="Calculated outputs (JSON)" hint="Persist deterministic model outputs and sensitivities"><TextArea rows={6} value={form.outputs} onChange={(event) => setForm({ ...form, outputs: event.target.value })} style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }} /></Field>
        <Field label="Evidence references" hint="One filing URL, report path, price snapshot, or dataset reference per line" required><TextArea rows={5} value={form.evidence} onChange={(event) => setForm({ ...form, evidence: event.target.value })} /></Field>
      </div>
    </Drawer>
  );
}

/* ============================================================
 * COVERAGE VIEW — the coverage queue + checklists
 * ============================================================ */
function CoverageView() {
  const { data, isLoading } = useResearchIdeas();
  const queue = data?.coverage_queue ?? [];
  const checklists = data?.long_term_checklists ?? [];
  const [selectedChecklist, setSelectedChecklist] = React.useState<LiveRow | null>(null);

  return (
    <>
      <CompanyIRSourceRegistry />

      <Panel icon={ClipboardCheck} title="Coverage Queue">
        {isLoading ? <SkeletonGrid rows={3} /> : queue.length === 0 ? (
          <Empty icon={ClipboardCheck} title="Coverage queue empty" description="Symbols needing research coverage will appear here." />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "reason", header: "Reason", render: (r) => text(r, "coverage_reason", text(r, "reason", "—")) },
              { key: "priority", header: "Priority", render: (r) => <StatusPill status={text(r, "priority", "medium")} /> },
              { key: "age", header: "Age", align: "right", render: (r) => formatRelative(text(r, "queued_at", text(r, "created_at"))) },
            ]}
            rows={queue}
            rowKey={(r, i) => String(text(r, "coverage_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <Panel icon={ClipboardCheck} title="Review Checklists">
        {isLoading ? <SkeletonGrid rows={3} /> : checklists.length === 0 ? (
          <Empty icon={ClipboardCheck} title="No checklists" />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "item", header: "Checklist Item", render: (r) => text(r, "checklist_name", text(r, "checklist_key", "—")) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "open")} /> },
              { key: "score", header: "Score", align: "right", render: (r) => text(r, "score", "—") },
              { key: "owner", header: "Owner", render: (r) => text(r, "owner_agent", "Research Analyst") },
            ]}
            rows={checklists}
            rowKey={(r, i) => String(text(r, "checklist_id", text(r, "id", i)))}
            onRowClick={setSelectedChecklist}
          />
        )}
      </Panel>

      <ChecklistReviewDrawer checklist={selectedChecklist} onClose={() => setSelectedChecklist(null)} />
    </>
  );
}

function CompanyIRSourceRegistry() {
  const { data, isLoading } = useCompanyIRSources();
  const register = useRegisterCompanyIRSource();
  const collect = useCollectCompanyIRSource();
  const pushToast = useUIStore((state) => state.pushToast);
  const sources = value<LiveRow[]>(data, "sources", []);
  const [form, setForm] = React.useState({
    symbol: "",
    exchange: "NSE" as "NSE" | "BSE",
    company_name: "",
    source_kind: "ir_page" as "ir_page" | "annual_report_pdf",
    source_url: "",
    fiscal_year_end: String(new Date().getFullYear()),
  });
  const ready = Boolean(
    form.symbol.trim() && form.company_name.trim() && form.source_url.trim()
    && (form.source_kind === "ir_page" || /^20\d{2}$/.test(form.fiscal_year_end))
  );

  function submit() {
    if (!ready) return;
    register.mutate({
      symbol: form.symbol.trim().toUpperCase(),
      exchange: form.exchange,
      company_name: form.company_name.trim(),
      source_kind: form.source_kind,
      source_url: form.source_url.trim(),
      fiscal_year_end: form.source_kind === "annual_report_pdf" ? Number(form.fiscal_year_end) : undefined,
      verification_evidence: { registered_from: "fundamental_coverage", operator_reviewed: true },
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        pushToast({ title: "Official source registered", message: `${form.exchange}:${form.symbol.trim().toUpperCase()} is ready for collection.`, tone: "ok", duration: 4500 });
        setForm((current) => ({ ...current, symbol: "", company_name: "", source_url: "" }));
      },
      onError: (error) => pushToast({ title: "Source registration failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  function collectSource(source: LiveRow) {
    const sourceId = num(source, "id");
    if (!sourceId) return;
    collect.mutate({ source_id: sourceId, actor: "Devarsh", limit: 15 }, {
      onSuccess: (result) => {
        const collection = value<LiveRow>(result, "collection", {});
        pushToast({
          title: "Official reports collected",
          message: `${num(collection, "reports_upserted")} reports retained for ${text(source, "symbol")}.`,
          tone: num(collection, "reports_upserted") > 0 ? "ok" : "warn",
          duration: 6500,
        });
      },
      onError: (error) => pushToast({ title: "Report collection failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  return (
    <Panel icon={FileText} title="Official Company Sources" actions={<Badge tone={sources.length ? "ok" : "warn"}>{sources.length} registered</Badge>}>
      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
          <Field label="Symbol" required><TextInput value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value.toUpperCase() })} placeholder="INFY" /></Field>
          <Field label="Exchange" required><Select value={form.exchange} onChange={(event) => setForm({ ...form, exchange: event.target.value as "NSE" | "BSE" })}><option value="NSE">NSE</option><option value="BSE">BSE</option></Select></Field>
          <Field label="Company" required><TextInput value={form.company_name} onChange={(event) => setForm({ ...form, company_name: event.target.value })} placeholder="Infosys Limited" /></Field>
          <Field label="Source type" required><Select value={form.source_kind} onChange={(event) => setForm({ ...form, source_kind: event.target.value as "ir_page" | "annual_report_pdf" })}><option value="ir_page">Investor relations page</option><option value="annual_report_pdf">Annual report PDF</option></Select></Field>
          {form.source_kind === "annual_report_pdf" ? <Field label="Fiscal year end" required><TextInput type="number" min="2001" max="2100" value={form.fiscal_year_end} onChange={(event) => setForm({ ...form, fiscal_year_end: event.target.value })} /></Field> : null}
          <Field label="Official HTTPS URL" required><TextInput value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} placeholder="https://company.com/investors/…" /></Field>
          <Button variant="primary" icon={Save} onClick={submit} disabled={!ready || register.isPending}>{register.isPending ? "Registering…" : "Register source"}</Button>
        </div>

        {isLoading ? <SkeletonGrid rows={3} /> : sources.length === 0 ? (
          <Empty icon={FileText} title="No official company sources registered" description="Register a verified investor-relations page or annual-report PDF." />
        ) : (
          <DataTable rows={sources} rowKey={(row, index) => text(row, "id", String(index))} columns={[
            { key: "company", header: "Company", render: (row) => <><strong>{text(row, "symbol")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "company_name")}</div></> },
            { key: "kind", header: "Source", render: (row) => <><StatusPill status={text(row, "source_kind")} /><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)", marginTop: 4 }}>{sourceHost(text(row, "source_url"))}</div></> },
            { key: "year", header: "FY", align: "right", render: (row) => text(row, "fiscal_year_end", "Archive") },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "last_collection_status", text(row, "status"))} /> },
            { key: "reports", header: "Reports", align: "right", render: (row) => num(row, "last_reports_upserted") },
            { key: "checked", header: "Verified", render: (row) => formatRelative(text(row, "verified_at")) },
            { key: "action", header: "", align: "right", render: (row) => <Button icon={RefreshCw} onClick={(event) => { event.stopPropagation(); collectSource(row); }} disabled={collect.isPending || text(row, "status") !== "active"}>{collect.isPending ? "Collecting…" : "Collect"}</Button> },
          ]} />
        )}
      </div>
    </Panel>
  );
}

function sourceHost(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return "invalid source";
  }
}

/* ============================================================
 * IDEA GENERATOR VIEW
 * ============================================================ */
function DossiersView() {
  const { data, isLoading } = useResearchIdeas();
  const coverage = data?.fundamental_coverage ?? [];
  const evidence = data?.fundamental_evidence ?? [];
  const dossiers = data?.investment_dossiers ?? [];
  const refresh = data?.dossier_refresh_queue ?? [];
  const claims = data?.management_claims ?? [];
  const acceptance = data?.fundamental_acceptance ?? [];
  const [selectedAcceptance, setSelectedAcceptance] = React.useState<LiveRow | null>(null);
  const [selectedEvidence, setSelectedEvidence] = React.useState<LiveRow | null>(null);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Companies" value={coverage.length} /></MetricTile>
        <MetricTile><Metric label="Dossiers" value={dossiers.length} /></MetricTile>
        <MetricTile tone="warn"><Metric label="Refresh queue" value={refresh.length} /></MetricTile>
        <MetricTile><Metric label="Claims tracked" value={claims.length} /></MetricTile>
        <MetricTile tone={acceptance.some((row) => bool(row, "all_required_gates_passed")) ? "ok" : "warn"}><Metric label="Accepted companies" value={acceptance.filter((row) => bool(row, "all_required_gates_passed")).length} /></MetricTile>
      </div>

      <Panel icon={ClipboardCheck} title="Institutional Coverage">
        {isLoading ? <SkeletonGrid rows={4} /> : coverage.length === 0 ? (
          <Empty icon={ClipboardCheck} title="No normalized company coverage" description="A company appears only after real identity evidence and source-backed financial or operating history are registered." />
        ) : (
          <DataTable rows={coverage} rowKey={(row, index) => text(row, "company_key", String(index))} columns={[
            { key: "company", header: "Company", render: (row) => <strong>{text(row, "legal_name")}</strong> },
            { key: "symbol", header: "Symbol", render: (row) => `${text(row, "primary_exchange")}:${text(row, "primary_symbol")}` },
            { key: "years", header: "Annual history", align: "right", render: (row) => num(row, "annual_statement_years") },
            { key: "segments", header: "Segments / KPIs", align: "right", render: (row) => `${num(row, "segment_count")} / ${num(row, "operational_kpi_count")}` },
            { key: "peers", header: "Peers", align: "right", render: (row) => num(row, "peer_count") },
            { key: "claims", header: "Claims / outcomes", align: "right", render: (row) => `${num(row, "management_claim_count")} / ${num(row, "claims_with_outcomes")}` },
            { key: "verified", header: "Identity", render: (row) => <StatusPill status={bool(row, "real_company_verified") ? "verified" : "blocked"} /> },
          ]} />
        )}
      </Panel>

      <Panel icon={FileText} title="Versioned Investment Dossiers">
        {dossiers.length === 0 ? (
          <Empty icon={FileText} title="No dossier version ready" description="A dossier needs primary evidence, normalized history, all specialist lanes, valuation, independent risk and committee work." />
        ) : (
          <DataTable rows={dossiers} rowKey={(row, index) => text(row, "dossier_key", String(index))} columns={[
            { key: "company", header: "Company", render: (row) => <strong>{text(row, "legal_name")}</strong> },
            { key: "version", header: "Version", render: (row) => `v${num(row, "version_number")}` },
            { key: "sections", header: "Sections reviewed", align: "right", render: (row) => `${num(row, "reviewed_section_count")} / ${num(row, "section_count")}` },
            { key: "specialists", header: "Specialists", align: "right", render: (row) => num(row, "specialist_count") },
            { key: "fit", header: "Portfolio fit", render: (row) => <StatusPill status={bool(row, "has_portfolio_fit") ? "complete" : "missing"} /> },
            { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "version_status", text(row, "dossier_status"))} /> },
            { key: "asof", header: "Research as of", render: (row) => text(row, "research_as_of", "—") },
          ]} />
        )}
      </Panel>

      <Panel icon={ShieldCheck} title="Real-Company Acceptance">
        {acceptance.length === 0 ? (
          <Empty icon={ShieldCheck} title="No acceptance run completed" description="Institutional completion remains blocked until one real company passes every required gate with retained evidence." />
        ) : (
          <DataTable rows={acceptance} rowKey={(row, index) => text(row, "run_key", String(index))} columns={[
            { key: "company", header: "Company", render: (row) => <strong>{text(row, "legal_name")}</strong> },
            { key: "status", header: "Run", render: (row) => <StatusPill status={text(row, "run_status")} /> },
            { key: "gates", header: "Passed / total", align: "right", render: (row) => `${num(row, "passed_gate_count")} / ${num(row, "gate_count")}` },
            { key: "failed", header: "Failed / blocked", align: "right", render: (row) => `${num(row, "failed_gate_count")} / ${num(row, "blocked_gate_count")}` },
            { key: "decision", header: "Decision", render: (row) => text(row, "acceptance_decision", "Pending") },
            { key: "asof", header: "Data as of", render: (row) => text(row, "data_as_of", "—") },
          ]} onRowClick={setSelectedAcceptance} />
        )}
      </Panel>

      <Panel icon={ShieldCheck} title="Human Evidence Review" actions={<Badge tone={evidence.some((row) => ["unverified", "machine_extracted"].includes(text(row, "verification_status"))) ? "warn" : "ok"}>{evidence.filter((row) => ["unverified", "machine_extracted"].includes(text(row, "verification_status"))).length} pending</Badge>}>
        {evidence.length === 0 ? (
          <Empty icon={ShieldCheck} title="No retained fundamental evidence" description="Run company intake to register official filings and source locators." />
        ) : (
          <DataTable rows={evidence} rowKey={(row, index) => text(row, "id", String(index))} columns={[
            { key: "company", header: "Company", render: (row) => <strong>{text(row, "primary_symbol", text(row, "legal_name"))}</strong> },
            { key: "title", header: "Retained source", render: (row) => text(row, "source_title") },
            { key: "source", header: "Source", render: (row) => text(row, "source_name", text(row, "source_type")) },
            { key: "status", header: "Review", render: (row) => <StatusPill status={text(row, "verification_status")} /> },
            { key: "retrieved", header: "Retrieved", render: (row) => formatRelative(text(row, "retrieved_at")) },
          ]} onRowClick={setSelectedEvidence} />
        )}
      </Panel>

      <AcceptanceGateDrawer acceptance={selectedAcceptance} onClose={() => setSelectedAcceptance(null)} />
      <FundamentalEvidenceReviewDrawer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
    </>
  );
}

function AcceptanceGateTable({ gates }: { gates: LiveRow[] }) {
  return (
    <DataTable rows={gates} rowKey={(row, index) => text(row, "gate_key", String(index))} columns={[
      { key: "gate", header: "Gate", render: (row) => <strong>{text(row, "gate_name", text(row, "gate_key").replace(/_/g, " "))}</strong> },
      { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "gate_status", text(row, "status"))} /> },
      { key: "observed", header: "Observed", render: (row) => compactJson(value(row, "observed_value", value(row, "observed", {}))) },
      { key: "required", header: "Required", render: (row) => compactJson(value(row, "required_value", value(row, "required", {}))) },
      { key: "reason", header: "Failure reason", render: (row) => text(row, "failure_reason", "—") },
    ]} />
  );
}

function AcceptanceGateDrawer({ acceptance, onClose }: { acceptance: LiveRow | null; onClose: () => void }) {
  const gates = acceptance ? acceptanceGateRows(acceptance) : [];
  return (
    <Drawer open={Boolean(acceptance)} onClose={onClose} title="Acceptance Gate Detail" subtitle={acceptance ? `${text(acceptance, "primary_exchange")}:${text(acceptance, "primary_symbol")} · ${text(acceptance, "run_key")}` : ""} icon={ShieldCheck} width={900}>
      {acceptance ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
            <KeyValue label="Run status" value={text(acceptance, "run_status")} />
            <KeyValue label="Passed gates" value={`${num(acceptance, "passed_gate_count")} / ${num(acceptance, "gate_count")}`} />
            <KeyValue label="Research cutoff" value={text(acceptance, "data_as_of", "—")} />
          </div>
          <AcceptanceGateTable gates={gates} />
        </>
      ) : null}
    </Drawer>
  );
}

function FundamentalEvidenceReviewDrawer({ evidence, onClose }: { evidence: LiveRow | null; onClose: () => void }) {
  const mutation = useReviewFundamentalEvidence();
  const pushToast = useUIStore((state) => state.pushToast);
  const [rationale, setRationale] = React.useState("");

  React.useEffect(() => {
    setRationale("");
    mutation.reset();
  }, [evidence?.id]);

  function review(decision: "human_verified" | "rejected") {
    if (!evidence || rationale.trim().length < 12) return;
    mutation.mutate({
      evidence_id: num(evidence, "id"),
      decision,
      rationale: rationale.trim(),
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: () => {
        pushToast({ title: decision === "human_verified" ? "Evidence verified" : "Evidence rejected", message: text(evidence, "source_title"), tone: decision === "human_verified" ? "ok" : "warn", duration: 5000 });
        onClose();
      },
      onError: (error) => pushToast({ title: "Evidence review failed", message: error.message, tone: "risk", duration: 6500 }),
    });
  }

  const sourceUrl = evidence ? text(evidence, "source_url") : "";
  const validSourceUrl = /^https?:\/\//i.test(sourceUrl);
  return (
    <Drawer open={Boolean(evidence)} onClose={onClose} title="Review Fundamental Evidence" subtitle={evidence ? `${text(evidence, "primary_exchange")}:${text(evidence, "primary_symbol")}` : ""} icon={ShieldCheck} width={680}>
      {evidence ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <Panel title={text(evidence, "source_title")}>
            <KeyValue label="Source" value={text(evidence, "source_name", text(evidence, "source_type"))} />
            <KeyValue label="Published" value={text(evidence, "published_at", text(evidence, "source_as_of_date", "—"))} />
            <KeyValue label="Current status" value={text(evidence, "verification_status")} />
            <KeyValue label="Locator" value={compactJson(value(evidence, "source_locator", {}))} />
            {validSourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: "var(--text-sm)" }}>Open retained source</a> : null}
          </Panel>
          <Field label="Review rationale" required>
            <TextArea rows={5} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Record what you checked in the retained source, including the company, period and relevant page or section." />
          </Field>
          <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button variant="ghost" icon={AlertTriangle} onClick={() => review("rejected")} disabled={rationale.trim().length < 12 || mutation.isPending}>Reject evidence</Button>
            <Button variant="primary" icon={ShieldCheck} onClick={() => review("human_verified")} disabled={rationale.trim().length < 12 || mutation.isPending}>{mutation.isPending ? "Saving review…" : "Verify evidence"}</Button>
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}

/* ============================================================
 * IDEA GENERATOR
 * ============================================================ */
function IdeasView() {
  const { data } = useResearchIdeas();
  const watchlistMut = useUpsertWatchlist();
  const pushToast = useUIStore((s) => s.pushToast);
  const generated = data?.generated_ideas ?? [];
  const discovery = data?.discovery_candidates ?? [];

  const [filter, setFilter] = React.useState("");

  const filtered = [...generated, ...discovery].filter((r) => {
    if (!filter) return true;
    const t = text(r, "symbol", text(r, "name", text(r, "title", ""))).toLowerCase();
    return t.includes(filter.toLowerCase());
  });

  function watch(row: LiveRow) {
    watchlistMut.mutate(
      { symbol: text(row, "symbol"), item_type: "idea", priority: "medium", thesis: text(row, "thesis", text(row, "idea_thesis")), actor: "Devarsh" },
      { onSuccess: () => pushToast({ title: "Added to watchlist", message: text(row, "symbol"), tone: "ok", duration: 2500 }) }
    );
  }

  return (
    <>
      <Panel icon={Lightbulb} title="Fundamental Idea Generator"
        actions={<TextInput placeholder="Filter ideas…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 200 }} />}
      >
        <div style={{ padding: "var(--space-3)", fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
          Long-term fundamental ideas surfaced from theses, filings, screens, and the research desk.
          Add candidates to the watchlist to begin coverage.
        </div>
        {filtered.length === 0 ? (
          <Empty icon={Lightbulb} title="No generated ideas yet" description="Ask Charlie to generate fundamental ideas, or run the research discovery pipeline." />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
            {filtered.slice(0, 24).map((idea, i) => (
              <div key={i} style={{ padding: "var(--space-4)", background: "var(--surface-soft)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-2)" }}>
                  <strong style={{ fontSize: "var(--text-md)" }}>{text(idea, "symbol", text(idea, "name"))}</strong>
                  <StatusPill status={text(idea, "priority", text(idea, "source", "idea"))} />
                </div>
                <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "var(--space-3)", minHeight: 40 }}>
                  {text(idea, "thesis", text(idea, "idea_thesis", text(idea, "description", "—")))}
                </div>
                <Button size="sm" variant="ghost" icon={Target} onClick={() => watch(idea)}>Add to watchlist</Button>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * Shared helpers
 * ============================================================ */
function optionalNumber(input: string): number | undefined {
  const normalized = input.trim();
  if (!normalized) return undefined;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function jsonText(input: unknown): string {
  if (typeof input === "string") return input || "{}";
  try {
    return JSON.stringify(input ?? {}, null, 2);
  } catch {
    return "{}";
  }
}

function compactJson(input: unknown): string {
  if (input === null || input === undefined) return "—";
  if (typeof input === "string") return input || "—";
  try {
    const rendered = JSON.stringify(input);
    return rendered.length > 160 ? `${rendered.slice(0, 157)}…` : rendered;
  } catch {
    return String(input);
  }
}

function monteCarloTerminalPrice(row: LiveRow, percentile: "p10" | "p50" | "p90"): number {
  const summary = value<Record<string, unknown>>(row, "percentile_summary", {});
  const terminal = summary.terminal_price;
  if (!terminal || typeof terminal !== "object" || Array.isArray(terminal)) return 0;
  const raw = (terminal as Record<string, unknown>)[percentile];
  const parsed = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function acceptanceGateRows(row: LiveRow): LiveRow[] {
  const direct = value<LiveRow[]>(row, "acceptance_gates", []);
  if (direct.length) return direct;
  const stored = value<Record<string, LiveRow>>(row, "gates", {});
  return Object.entries(stored).map(([gateKey, gate]) => ({
    ...gate,
    gate_key: gateKey,
    gate_name: text(gate, "gate_name", gateKey.replace(/_/g, " ")),
    gate_status: text(gate, "status", text(gate, "gate_status", "blocked")),
    observed_value: value(gate, "observed", value(gate, "observed_value", {})),
    required_value: value(gate, "required", value(gate, "required_value", {})),
  }));
}

function parseJsonObject(input: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(input || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function listToLines(items: unknown[], preferredKey: string): string {
  return items.map((item) => {
    if (typeof item === "string") return item;
    if (item && typeof item === "object") {
      const row = item as Record<string, unknown>;
      return String(row[preferredKey] ?? row.source ?? row.finding ?? row.ref ?? "");
    }
    return "";
  }).filter(Boolean).join("\n");
}

function linesToEvidence(input: string): Array<{ source: string }> {
  return input.split("\n").map((source) => source.trim()).filter(Boolean).map((source) => ({ source }));
}

function localDateTimeInputValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}


function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (score / max) * 100) : 0;
  const color = pct >= 70 ? "var(--status-ok)" : pct >= 40 ? "var(--status-warn)" : "var(--status-risk)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <div style={{ width: 60, height: 5, background: "var(--bg-sunken)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color }} />
      </div>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)", minWidth: 24 }}>{score.toFixed(1)}</span>
    </div>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
