/**
 * Fundamental Research Terminal — Buffett school
 *
 * Routes:  /fundamental/theses | /scorecards | /valuation | /coverage | /ideas
 *
 * The deep long-term investment research workspace. Built around the
 * holding thesis as the atomic unit, with 11 specialist scorecards,
 * valuation suite (DCF / multiples / reverse DCF / Monte Carlo),
 * coverage queue, and a fundamental idea generator.
 *
 * This is NOT the quant lab — it's the slow-money, deep-research home.
 */

import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  BookOpen, Microscope, Calculator, ClipboardCheck, Lightbulb,
  FlaskConical, TrendingUp, AlertTriangle, ChevronRight, Sparkles,
  Send, GitBranch, Target, FileText,
} from "lucide-react";
import { useResearchIdeas, usePortfolioOffice } from "../../data/queries";
import {
  useRunMonteCarlo, useGenerateThesisMemo, useGenerateResearchPacket,
  useUpdateChecklist, useUpdateValuation, useDispatchSpecialists,
  useOpenLongTermCommittee, useUpsertWatchlist,
} from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, ScrollList, KeyValue, Field, TextInput, TextArea, Select,
} from "../../system/primitives";
import { AreaSeriesChart, DonutChart } from "../../system/charts";
import { text, num, bool, timestamp, formatRelative, formatCompact, formatPercent, formatCurrency } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "theses", label: "Long-Term Theses", icon: BookOpen },
  { key: "scorecards", label: "Scorecards", icon: Microscope },
  { key: "valuation", label: "Valuation Suite", icon: Calculator },
  { key: "coverage", label: "Coverage", icon: ClipboardCheck },
  { key: "ideas", label: "Idea Generator", icon: Lightbulb },
];

export default function FundamentalResearch({ defaultTab = "theses" }: { defaultTab?: string }) {
  const params = useParams();
  const navigate = useNavigate();
  const tab = params.tab ?? defaultTab;

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
          Long-term investment theses, 11 specialist scorecards, valuation suite, and idea generation.
          Separated from quant — this is about business quality, not signal noise.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "theses" && <ThesesView />}
      {tab === "scorecards" && <ScorecardsView />}
      {tab === "valuation" && <ValuationView />}
      {tab === "coverage" && <CoverageView />}
      {tab === "ideas" && <IdeasView />}
    </div>
  );
}

/* ============================================================
 * THESES VIEW — the master list + detail drawer
 * ============================================================ */
function ThesesView() {
  const { data, isLoading } = useResearchIdeas();
  const openEvidence = useUIStore((s) => s.openEvidence);
  const theses = data?.long_term_theses ?? [];
  const [selected, setSelected] = React.useState<LiveRow | null>(null);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Active Theses" value={theses.length} /></MetricTile>
        <MetricTile><Metric label="Coverage Queue" value={data?.coverage_queue?.length ?? 0} /></MetricTile>
        <MetricTile><Metric label="Monte Carlo Runs" value={data?.long_term_monte_carlo_runs?.length ?? 0} /></MetricTile>
        <MetricTile tone="warn"><Metric label="Committee Queue" value={data?.committee_queue?.length ?? 0} /></MetricTile>
      </div>

      <Panel icon={BookOpen} title="Long-Term Theses" actions={theses.length > 0 ? <Badge dot>{theses.length}</Badge> : undefined}>
        {isLoading ? (
          <SkeletonGrid rows={4} />
        ) : theses.length === 0 ? (
          <Empty icon={BookOpen} title="No long-term theses yet" description="Theses are generated per holding once research packets are built. Use the Idea Generator to seed candidates." />
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
              Research packet bundles quotes, positions, filings, and notes. Specialists run 11 deep-dive modules (business model, moat, management, governance, capital allocation, financial quality, forensic accounting, valuation, bear case, portfolio fit, risk review).
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
 * SCORECARDS VIEW — the 11 specialist modules
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
  { key: "risk_review", label: "Risk Review", icon: AlertTriangle },
];

function ScorecardsView() {
  const { data, isLoading } = useResearchIdeas();
  const dispatchMut = useDispatchSpecialists();
  const pushToast = useUIStore((s) => s.pushToast);
  const outputs = data?.long_term_research_updates ?? [];
  const theses = data?.long_term_theses ?? [];
  const [selectedThesis, setSelectedThesis] = React.useState<string>("");

  function runAll() {
    if (!selectedThesis) {
      pushToast({ title: "Pick a thesis first", tone: "warn", duration: 2500 });
      return;
    }
    dispatchMut.mutate(
      { holding_thesis_id: Number(selectedThesis), actor: "Devarsh" },
      { onSuccess: () => pushToast({ title: "All 11 specialists dispatched", tone: "ok", duration: 3000 }), onError: (e: Error) => pushToast({ title: "Dispatch failed", message: e.message, tone: "risk", duration: 5000 }) }
    );
  }

  return (
    <>
      <Panel icon={Microscope} title="11 Specialist Scorecards"
        actions={
          <>
            <Select value={selectedThesis} onChange={(e) => setSelectedThesis(e.target.value)} style={{ width: 200 }}>
              <option value="">Pick a thesis…</option>
              {theses.map((t, i) => <option key={i} value={text(t, "holding_thesis_id", text(t, "id", i))}>{text(t, "symbol")} — {text(t, "company_name", text(t, "name"))}</option>)}
            </Select>
            <Button size="sm" icon={Sparkles} onClick={runAll} disabled={dispatchMut.isPending}>Dispatch All</Button>
          </>
        }
      >
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--space-3)", padding: "var(--space-3)" }}>
          {SPECIALIST_MODULES.map((mod) => {
            const found = outputs.find((o) => text(o, "module_key", text(o, "specialist_module")) === mod.key);
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
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>Not yet run</div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>

      <Panel icon={ClipboardCheck} title="Specialist Outputs">
        {isLoading ? <SkeletonGrid rows={3} /> : outputs.length === 0 ? (
          <Empty icon={Microscope} title="No specialist outputs yet" description="Pick a thesis above and dispatch the specialists to run all 11 deep-dive modules." />
        ) : (
          <DataTable
            columns={[
              { key: "thesis", header: "Thesis", render: (r) => <strong>{text(r, "symbol", text(r, "holding_symbol"))}</strong> },
              { key: "module", header: "Module", render: (r) => text(r, "module_key", text(r, "specialist_module")) },
              { key: "score", header: "Score", align: "right", render: (r) => num(r, "score", 0).toFixed(1) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "complete")} /> },
              { key: "when", header: "When", render: (r) => formatRelative(text(r, "completed_at", text(r, "updated_at"))) },
            ]}
            rows={outputs}
            rowKey={(r, i) => String(text(r, "output_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
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
                { key: "type", header: "Model Type", render: (r) => text(r, "model_type", "DCF") },
                { key: "fair", header: "Fair Value", align: "right", render: (r) => formatCurrency(num(r, "fair_value", 0)) },
                { key: "upside", header: "Upside", align: "right", render: (r) => <span style={{ color: num(r, "upside_pct", 0) >= 0 ? "var(--status-ok)" : "var(--status-risk)" }}>{formatPercent(num(r, "upside_pct", 0), { alreadyPercent: true })}</span> },
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
                <div key={i} style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{text(run, "symbol", text(run, "holding_symbol"))}</strong>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>{formatRelative(text(run, "ran_at", text(run, "created_at")))}</span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-2)", marginTop: "var(--space-2)", fontSize: "var(--text-xs)" }}>
                    <div><div className="micro">P10</div>{formatCompact(num(run, "p10_outcome", 0), "INR")}</div>
                    <div><div className="micro">Median</div>{formatCompact(num(run, "median_outcome", 0), "INR")}</div>
                    <div><div className="micro">P90</div>{formatCompact(num(run, "p90_outcome", 0), "INR")}</div>
                  </div>
                </div>
              ))}
            </ScrollList>
          )}
        </Panel>
      </div>
    </>
  );
}

/* ============================================================
 * COVERAGE VIEW — the coverage queue + checklists
 * ============================================================ */
function CoverageView() {
  const { data, isLoading } = useResearchIdeas();
  const queue = data?.coverage_queue ?? [];
  const checklists = data?.long_term_checklists ?? [];

  return (
    <>
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
              { key: "item", header: "Checklist Item", render: (r) => text(r, "item_text", text(r, "checklist_item", "—")) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "open")} /> },
              { key: "due", header: "Due", render: (r) => text(r, "due_date", "—") },
            ]}
            rows={checklists}
            rowKey={(r, i) => String(text(r, "checklist_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * IDEA GENERATOR VIEW
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

/* Lucide icons used only here, imported lazily to keep the chunk focused */
import { ShieldCheck, Users, Gavel, Wallet, BarChart3, Search, TrendingDown } from "lucide-react";
