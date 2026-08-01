/**
 * Portfolio & Clients Terminal
 *
 * Routes: /portfolio/overview | /positions | /books | /clients |
 *         /nav | /reconciliation | /trackers
 *
 * Multi-client portfolio intelligence — NAV, exposure, allocation, positions
 * with thesis links, investment books, client registry + onboarding, NAV &
 * cash ledgers, reconciliation, and ongoing folio trackers.
 */

import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Briefcase, PieChart, BookOpen, Users, DollarSign, GitBranch, Activity,
  Plus, Save,
} from "lucide-react";
import { usePortfolioOffice } from "../../data/queries";
import { useStageClientOnboarding, useStageHoldingUpdate } from "../../data/actions";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select, KeyValue,
} from "../../system/primitives";
import { DonutChart, Treemap } from "../../system/charts";
import { text, num, bool, formatRelative, formatCurrency, formatCompact, formatPercent } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "overview", label: "Overview", icon: Briefcase },
  { key: "positions", label: "Positions", icon: PieChart },
  { key: "books", label: "Books", icon: BookOpen },
  { key: "clients", label: "Clients", icon: Users },
  { key: "nav", label: "NAV & Cash", icon: DollarSign },
  { key: "reconciliation", label: "Reconciliation", icon: GitBranch },
  { key: "trackers", label: "Folio Trackers", icon: Activity },
];

export default function PortfolioTerminal({ defaultTab = "overview" }: { defaultTab?: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = location.pathname.split("/").filter(Boolean).slice(-1)[0] ?? defaultTab;
  function setTab(key: string) { navigate(`/portfolio/${key}`); }

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">
            <Briefcase size={26} style={{ verticalAlign: "middle", marginRight: 10, color: "var(--accent)" }} />
            Portfolio & Clients
          </div>
          <Badge tone="accent">PORT</Badge>
        </div>
        <div className="aios-destination__subtitle">
          Multi-client portfolio intelligence — NAV, positions, books, accounting, reconciliation.
        </div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "overview" && <OverviewView />}
      {tab === "positions" && <PositionsView />}
      {tab === "books" && <BooksView />}
      {tab === "clients" && <ClientsView />}
      {tab === "nav" && <NavView />}
      {tab === "reconciliation" && <ReconView />}
      {tab === "trackers" && <TrackersView />}
    </div>
  );
}

/* ============================================================
 * OVERVIEW
 * ============================================================ */
function OverviewView() {
  const { data, isLoading } = usePortfolioOffice();
  const positions = data?.latest_positions ?? [];
  const clients = data?.clients ?? [];
  const navRows = data?.client_nav ?? [];
  const intel = data?.portfolio_intelligence ?? [];

  const totalExposure = positions.reduce((acc, r) => acc + Math.abs(num(r, "exposure", num(r, "market_value", num(r, "notional", 0)))), 0);
  const completeNavRows = navRows.filter((row) => row.nav !== null && row.nav !== undefined);
  const completeNav = completeNavRows.reduce((acc, r) => acc + num(r, "nav", num(r, "nav_inr", 0)), 0);

  const clientSummaries = React.useMemo(() => {
    const holdings = new Map<string, { value: number; top: number; count: number }>();
    for (const position of positions) {
      const clientCode = text(position, "client_code", text(position, "display_name", "unassigned"));
      const marketValue = Math.abs(num(position, "market_value", num(position, "exposure", 0)));
      const summary = holdings.get(clientCode) ?? { value: 0, top: 0, count: 0 };
      summary.value += marketValue;
      summary.top = Math.max(summary.top, marketValue);
      summary.count += 1;
      holdings.set(clientCode, summary);
    }

    return clients.map((client) => {
      const clientCode = text(client, "client_code", text(client, "id"));
      const summary = holdings.get(clientCode) ?? { value: num(client, "latest_market_value", 0), top: 0, count: num(client, "latest_position_count", 0) };
      const latestAt = text(client, "latest_position_at");
      const latestTs = Date.parse(latestAt);
      const stale = !Number.isFinite(latestTs) || Date.now() - latestTs > 7 * 24 * 60 * 60 * 1000;
      return {
        client_code: clientCode,
        display_name: text(client, "display_name", clientCode),
        holdings_value: summary.value,
        position_count: summary.count,
        top_holding_weight: summary.value > 0 ? summary.top / summary.value : 0,
        latest_position_at: latestAt,
        status: stale ? "stale" : "current",
      } satisfies LiveRow;
    });
  }, [clients, positions]);

  const visibleHoldings = clientSummaries.reduce((acc, row) => acc + num(row, "holdings_value", 0), 0);

  // Allocation by symbol (for treemap)
  const allocation = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const p of positions) {
      const sym = text(p, "symbol");
      const val = Math.abs(num(p, "market_value", num(p, "exposure", num(p, "notional", 0))));
      map.set(sym, (map.get(sym) ?? 0) + val);
    }
    return Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 20);
  }, [positions]);

  // Cash evidence is incomplete for some accounts, so this allocation is based
  // on observable securities rather than presenting a partial NAV as complete.
  const clientAllocation = clientSummaries.map((r) => ({
    name: text(r, "display_name", text(r, "client_code")),
    value: num(r, "holdings_value", 0),
  }));

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
        <MetricTile><Metric label="Visible Holdings" value={visibleHoldings > 0 ? formatCompact(visibleHoldings, "INR") : "—"} size="lg" /></MetricTile>
        <MetricTile><Metric label="Calculated NAV" value={completeNav > 0 ? formatCompact(completeNav, "INR") : "—"} sub={`${completeNavRows.length}/${navRows.length} accounts have cash evidence`} /></MetricTile>
        <MetricTile><Metric label="Gross Exposure" value={totalExposure > 0 ? formatCompact(totalExposure, "INR") : "—"} /></MetricTile>
        <MetricTile><Metric label="Clients" value={clients.length} /></MetricTile>
        <MetricTile><Metric label="Positions" value={positions.length} /></MetricTile>
        <MetricTile><Metric label="Books" value={data?.investment_books?.length ?? 0} /></MetricTile>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "var(--space-4)", alignItems: "start" }}>
        <Panel icon={PieChart} title="Allocation by Symbol">
          {isLoading ? <Skeleton style={{ height: 280 }} /> : allocation.length === 0 ? (
            <Empty icon={PieChart} title="No positions to allocate" />
          ) : (
            <Treemap data={allocation} height={280} />
          )}
        </Panel>
        <Panel icon={Users} title="Visible Holdings by Client">
          {isLoading ? <Skeleton style={{ height: 280 }} /> : clientAllocation.length === 0 ? (
            <Empty icon={Users} title="No client holdings" />
          ) : (
            <>
              <DonutChart data={clientAllocation} height={220} />
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", marginTop: "var(--space-3)" }}>
                {clientAllocation.map((c, i) => (
                  <KeyValue key={i} label={c.name} value={formatCompact(c.value, "INR")} />
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>

      {clientSummaries.length > 0 && (
        <Panel icon={Users} title="Client Portfolio Summary">
          <DataTable
            columns={[
              { key: "client", header: "Client", render: (r) => <strong>{text(r, "display_name", text(r, "client_code"))}</strong> },
              { key: "holdings", header: "Visible Holdings", align: "right", render: (r) => formatCompact(num(r, "holdings_value", 0), "INR") },
              { key: "positions", header: "Positions", align: "right", render: (r) => num(r, "position_count", 0) },
              { key: "concentration", header: "Top Holding %", align: "right", render: (r) => formatPercent(num(r, "top_holding_weight", 0)) },
              { key: "asof", header: "Latest Snapshot", render: (r) => formatRelative(text(r, "latest_position_at")) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "ok")} /> },
            ]}
            rows={clientSummaries}
            rowKey={(r, i) => String(text(r, "client_code", i))}
          />
        </Panel>
      )}

      {intel.length > 0 && (
        <Panel icon={Briefcase} title="Portfolio Intelligence Facts">
          <DataTable
            columns={[
              { key: "section", header: "Section", render: (r) => text(r, "section", "portfolio") },
              { key: "fact", header: "Fact", render: (r) => <strong>{text(r, "item_name", text(r, "item_key"))}</strong> },
              { key: "value", header: "Value", align: "right", render: (r) => text(r, "item_value", "—") },
              { key: "interpretation", header: "Interpretation", render: (r) => text(r, "interpretation", "—") },
            ]}
            rows={intel.slice(0, 12)}
            rowKey={(r, i) => `${text(r, "section")}:${text(r, "item_key", i)}`}
          />
        </Panel>
      )}
    </>
  );
}

/* ============================================================
 * POSITIONS
 * ============================================================ */
function PositionsView() {
  const { data, isLoading } = usePortfolioOffice();
  const positions = data?.latest_positions ?? [];
  const openEvidence = useUIStore((s) => s.openEvidence);
  const [filter, setFilter] = React.useState("");
  const [showUpdate, setShowUpdate] = React.useState(false);

  const filtered = filter ? positions.filter((r) => text(r, "symbol").toLowerCase().includes(filter.toLowerCase())) : positions;
  const totalMarketValue = positions.reduce((sum, r) => sum + Math.abs(num(r, "market_value", 0)), 0);

  return (
    <>
      <Panel icon={PieChart} title="Positions"
        actions={<div style={{ display: "flex", gap: "var(--space-2)" }}><TextInput placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 160 }} /><Button size="sm" variant="primary" icon={Plus} onClick={() => setShowUpdate(true)}>Update holding</Button></div>}
      >
        {isLoading ? <SkeletonGrid rows={6} /> : filtered.length === 0 ? (
          <Empty icon={PieChart} title="No positions" description="Stage a verified holding snapshot to begin tracking this account." action={<Button size="sm" icon={Plus} onClick={() => setShowUpdate(true)}>Update holding</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
              { key: "client", header: "Client", render: (r) => text(r, "display_name", text(r, "client_name", "—")) },
              { key: "book", header: "Book", render: (r) => text(r, "book_key", "—") },
              { key: "qty", header: "Qty", align: "right", render: (r) => num(r, "quantity", 0) },
              { key: "avg", header: "Avg Cost", align: "right", render: (r) => formatCurrency(num(r, "average_cost", num(r, "average_price", 0))) },
              { key: "mv", header: "Mkt Value", align: "right", render: (r) => formatCompact(num(r, "market_value", 0), "INR") },
              { key: "weight", header: "Weight", align: "right", render: (r) => formatPercent(totalMarketValue > 0 ? Math.abs(num(r, "market_value", 0)) / totalMarketValue : 0) },
              { key: "purpose", header: "Purpose", render: (r) => text(r, "purpose", "—") },
            ]}
            rows={filtered}
            rowKey={(r, i) => String(text(r, "position_id", text(r, "id", i)))}
            onRowClick={(r) => openEvidence({ kind: "strategy", key: String(text(r, "thesis_id", text(r, "position_id", text(r, "id")))), title: `${text(r, "symbol")} — ${text(r, "display_name", text(r, "client_name", "position"))}` })}
          />
        )}
      </Panel>
      <HoldingUpdateDrawer open={showUpdate} onClose={() => setShowUpdate(false)} />
    </>
  );
}

/* ============================================================
 * BOOKS
 * ============================================================ */
function BooksView() {
  const { data, isLoading } = usePortfolioOffice();
  const books = data?.investment_books ?? [];
  const conflicts = data?.cross_book_conflicts ?? [];

  return (
    <>
      <Panel icon={BookOpen} title="Investment Books">
        {isLoading ? <SkeletonGrid rows={3} /> : books.length === 0 ? (
          <Empty icon={BookOpen} title="No books" description="Books separate capital by horizon — Long-Term, Tactical, Quant, Active, Cash." />
        ) : (
          <DataTable
            columns={[
              { key: "name", header: "Book", render: (r) => <strong>{text(r, "book_name", text(r, "name"))}</strong> },
              { key: "mandate", header: "Mandate", render: (r) => text(r, "mandate", "—") },
              { key: "horizon", header: "Horizon", render: (r) => text(r, "horizon", "—") },
              { key: "allocation", header: "Capital", align: "right", render: (r) => formatCompact(num(r, "capital_allocation", num(r, "target_capital", 0)), "INR") },
              { key: "positions", header: "Positions", align: "right", render: (r) => num(r, "position_count", 0) },
            ]}
            rows={books}
            rowKey={(r, i) => String(text(r, "book_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      {conflicts.length > 0 && (
        <Panel variant="warn" icon={GitBranch} title="Cross-Book Conflicts">
          <DataTable
            columns={[
              { key: "symbol", header: "Symbol", render: (r) => text(r, "symbol") },
              { key: "conflict", header: "Conflict", render: (r) => text(r, "conflict_description", text(r, "conflict_type", "—")) },
              { key: "books", header: "Books", render: (r) => text(r, "books_involved", "—") },
            ]}
            rows={conflicts}
            rowKey={(r, i) => String(text(r, "conflict_id", text(r, "id", i)))}
          />
        </Panel>
      )}
    </>
  );
}

/* ============================================================
 * CLIENTS
 * ============================================================ */
function ClientsView() {
  const { data, isLoading } = usePortfolioOffice();
  const clients = data?.clients ?? [];
  const onboarding = data?.client_onboarding ?? [];
  const [showOnboarding, setShowOnboarding] = React.useState(false);

  return (
    <>
      <Panel icon={Users} title="Client Registry"
        actions={<Button size="sm" variant="primary" icon={Plus} onClick={() => setShowOnboarding(true)}>Onboard Client</Button>}
      >
        {isLoading ? <SkeletonGrid rows={3} /> : clients.length === 0 ? (
          <Empty icon={Users} title="No clients" description="Stage a suitability-reviewed client onboarding case." action={<Button size="sm" icon={Plus} onClick={() => setShowOnboarding(true)}>Onboard client</Button>} />
        ) : (
          <DataTable
            columns={[
              { key: "name", header: "Client", render: (r) => <strong>{text(r, "display_name", text(r, "client_name", text(r, "name")))}</strong> },
              { key: "type", header: "Type", render: (r) => text(r, "client_type", "individual") },
              { key: "risk", header: "Risk Profile", render: (r) => text(r, "risk_profile", "—") },
              { key: "value", header: "Visible Holdings", align: "right", render: (r) => formatCompact(num(r, "latest_market_value", 0), "INR") },
              { key: "since", header: "Since", render: (r) => text(r, "onboarded_at", text(r, "created_at", "—")) },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", bool(r, "active", true) ? "active" : "inactive")} /> },
            ]}
            rows={clients}
            rowKey={(r, i) => String(text(r, "client_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      {onboarding.length > 0 && (
        <Panel variant="warn" icon={Users} title="Onboarding Queue">
          <DataTable
            columns={[
              { key: "name", header: "Prospect", render: (r) => text(r, "client_name", text(r, "name")) },
              { key: "stage", header: "Stage", render: (r) => <StatusPill status={text(r, "stage", text(r, "status", "pending"))} /> },
              { key: "since", header: "Started", render: (r) => formatRelative(text(r, "started_at", text(r, "created_at"))) },
            ]}
            rows={onboarding}
            rowKey={(r, i) => String(text(r, "onboarding_id", text(r, "id", i)))}
          />
        </Panel>
      )}
      <ClientOnboardingDrawer open={showOnboarding} onClose={() => setShowOnboarding(false)} />
    </>
  );
}

function ClientOnboardingDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const mutation = useStageClientOnboarding();
  const pushToast = useUIStore((s) => s.pushToast);
  const [form, setForm] = React.useState({
    client_code: "", display_name: "", risk_profile: "moderate", objectives: "", constraints: "",
    investment_horizon: "5-10 years", liquidity_needs: "", risk_tolerance: "moderate",
    risk_capacity: "moderate", suitability_status: "needs_review", suitability_notes: "",
    account_code: "", broker: "Zerodha", source_evidence: "",
  });
  function update(key: string, value: string) { setForm((current) => ({ ...current, [key]: value })); }
  function lines(value: string) { return value.split("\n").map((item) => item.trim()).filter(Boolean); }
  function submit() {
    const objectives = lines(form.objectives);
    const sourceEvidence = lines(form.source_evidence);
    if (!form.client_code.trim() || !form.display_name.trim() || objectives.length === 0 || sourceEvidence.length === 0) {
      pushToast({ title: "Complete required onboarding evidence", message: "Client code, name, at least one objective, and source evidence are required.", tone: "warn", duration: 5000 });
      return;
    }
    mutation.mutate({
      client_code: form.client_code.trim(), display_name: form.display_name.trim(), risk_profile: form.risk_profile,
      objectives, constraints: lines(form.constraints), investment_horizon: form.investment_horizon,
      liquidity_needs: form.liquidity_needs, risk_tolerance: form.risk_tolerance, risk_capacity: form.risk_capacity,
      suitability_status: form.suitability_status as "needs_review" | "suitable" | "conditionally_suitable" | "unsuitable",
      suitability_notes: form.suitability_notes, source_evidence: sourceEvidence,
      account: form.account_code.trim() ? { account_code: form.account_code.trim(), account_name: form.display_name.trim(), account_type: "investment", broker: form.broker.trim(), base_currency: "INR" } : undefined,
      actor: "Devarsh",
    }, {
      onSuccess: () => { pushToast({ title: "Onboarding staged", message: "Charlie and the Client Office must review suitability before activation.", tone: "ok", duration: 5000 }); onClose(); },
      onError: (error) => pushToast({ title: "Onboarding failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }
  return <Drawer open={open} onClose={onClose} title="Governed Client Onboarding" icon={Users} width={620}
    footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Save} onClick={submit} disabled={mutation.isPending}>Stage for approval</Button></div>}>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
      <Field label="Client code" required><TextInput value={form.client_code} onChange={(e) => update("client_code", e.target.value)} /></Field>
      <Field label="Display name" required><TextInput value={form.display_name} onChange={(e) => update("display_name", e.target.value)} /></Field>
      <Field label="Risk profile"><Select value={form.risk_profile} onChange={(e) => update("risk_profile", e.target.value)}><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></Select></Field>
      <Field label="Investment horizon"><TextInput value={form.investment_horizon} onChange={(e) => update("investment_horizon", e.target.value)} /></Field>
      <Field label="Risk tolerance"><Select value={form.risk_tolerance} onChange={(e) => update("risk_tolerance", e.target.value)}><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option></Select></Field>
      <Field label="Risk capacity"><Select value={form.risk_capacity} onChange={(e) => update("risk_capacity", e.target.value)}><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option></Select></Field>
      <Field label="Suitability"><Select value={form.suitability_status} onChange={(e) => update("suitability_status", e.target.value)}><option value="needs_review">Needs review</option><option value="suitable">Suitable</option><option value="conditionally_suitable">Conditionally suitable</option><option value="unsuitable">Unsuitable</option></Select></Field>
      <Field label="Liquidity needs"><TextInput value={form.liquidity_needs} onChange={(e) => update("liquidity_needs", e.target.value)} /></Field>
      <Field label="Account code"><TextInput value={form.account_code} onChange={(e) => update("account_code", e.target.value)} /></Field>
      <Field label="Broker"><TextInput value={form.broker} onChange={(e) => update("broker", e.target.value)} /></Field>
    </div>
    <Field label="Investment objectives (one per line)" required><TextArea rows={3} value={form.objectives} onChange={(e) => update("objectives", e.target.value)} /></Field>
    <Field label="Constraints (one per line)"><TextArea rows={2} value={form.constraints} onChange={(e) => update("constraints", e.target.value)} /></Field>
    <Field label="Suitability notes"><TextArea rows={2} value={form.suitability_notes} onChange={(e) => update("suitability_notes", e.target.value)} /></Field>
    <Field label="Source evidence (statement path, URL, or reference; one per line)" required><TextArea rows={3} value={form.source_evidence} onChange={(e) => update("source_evidence", e.target.value)} /></Field>
  </Drawer>;
}

function HoldingUpdateDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data } = usePortfolioOffice();
  const mutation = useStageHoldingUpdate();
  const pushToast = useUIStore((s) => s.pushToast);
  const clients = data?.clients ?? [];
  const accounts = data?.client_accounts ?? [];
  const [form, setForm] = React.useState({ client_code: "", account_code: "", symbol: "", exchange: "NSE", quantity: "", average_price: "", market_price: "", update_reason: "manual verified holding snapshot", source_evidence: "" });
  function update(key: string, value: string) { setForm((current) => ({ ...current, [key]: value })); }
  const scopedAccounts = accounts.filter((row) => !form.client_code || text(row, "client_code") === form.client_code);
  function submit() {
    const quantity = Number(form.quantity);
    if (!form.client_code || !form.account_code || !form.symbol.trim() || !Number.isFinite(quantity) || !form.source_evidence.trim()) {
      pushToast({ title: "Complete holding evidence", message: "Client, account, symbol, quantity, and a source reference are required.", tone: "warn", duration: 5000 });
      return;
    }
    const averagePrice = form.average_price ? Number(form.average_price) : undefined;
    const marketPrice = form.market_price ? Number(form.market_price) : undefined;
    mutation.mutate({ client_code: form.client_code, account_code: form.account_code, symbol: form.symbol.trim().toUpperCase(), exchange: form.exchange, quantity, average_price: averagePrice, market_price: marketPrice, update_reason: form.update_reason, payload: { source_evidence: [form.source_evidence.trim()], entered_from: "portfolio_positions_ui" }, actor: "Devarsh" }, {
      onSuccess: () => { pushToast({ title: "Holding update staged", message: "The Portfolio Manager must verify and approve it before the position book changes.", tone: "ok", duration: 5000 }); onClose(); },
      onError: (error) => pushToast({ title: "Holding update failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }
  return <Drawer open={open} onClose={onClose} title="Stage Holding Update" icon={PieChart} width={560}
    footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" icon={Save} onClick={submit} disabled={mutation.isPending}>Stage for approval</Button></div>}>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
      <Field label="Client" required><Select value={form.client_code} onChange={(e) => { update("client_code", e.target.value); update("account_code", ""); }}><option value="">Select client</option>{clients.map((row, index) => <option key={text(row, "client_code", index)} value={text(row, "client_code")}>{text(row, "display_name", text(row, "client_code"))}</option>)}</Select></Field>
      <Field label="Account" required><Select value={form.account_code} onChange={(e) => update("account_code", e.target.value)}><option value="">Select account</option>{scopedAccounts.map((row, index) => <option key={text(row, "account_code", index)} value={text(row, "account_code")}>{text(row, "account_name", text(row, "account_code"))}</option>)}</Select></Field>
      <Field label="Symbol" required><TextInput value={form.symbol} onChange={(e) => update("symbol", e.target.value)} /></Field>
      <Field label="Exchange"><Select value={form.exchange} onChange={(e) => update("exchange", e.target.value)}><option value="NSE">NSE</option><option value="BSE">BSE</option><option value="NFO">NFO</option><option value="MCX">MCX</option></Select></Field>
      <Field label="Quantity" required><TextInput type="number" value={form.quantity} onChange={(e) => update("quantity", e.target.value)} /></Field>
      <Field label="Average price"><TextInput type="number" value={form.average_price} onChange={(e) => update("average_price", e.target.value)} /></Field>
      <Field label="Market price"><TextInput type="number" value={form.market_price} onChange={(e) => update("market_price", e.target.value)} /></Field>
    </div>
    <Field label="Update reason"><TextArea rows={2} value={form.update_reason} onChange={(e) => update("update_reason", e.target.value)} /></Field>
    <Field label="Source statement or evidence reference" required><TextArea rows={2} value={form.source_evidence} onChange={(e) => update("source_evidence", e.target.value)} /></Field>
  </Drawer>;
}

/* ============================================================
 * NAV & CASH
 * ============================================================ */
function NavView() {
  const { data, isLoading } = usePortfolioOffice();
  const nav = data?.client_nav ?? [];
  const cash = data?.cash_ledger ?? [];

  return (
    <>
      <Panel icon={DollarSign} title="NAV Snapshots">
        {isLoading ? <SkeletonGrid rows={3} /> : nav.length === 0 ? (
          <Empty icon={DollarSign} title="No NAV data" />
        ) : (
          <DataTable
            columns={[
              { key: "client", header: "Client", render: (r) => <strong>{text(r, "display_name", text(r, "client_name", text(r, "name")))}</strong> },
              { key: "nav", header: "Complete NAV", align: "right", render: (r) => r.nav === null || r.nav === undefined ? "—" : formatCompact(num(r, "nav", num(r, "nav_inr", 0)), "INR") },
              { key: "cash", header: "Cash", align: "right", render: (r) => r.cash === null || r.cash_balance === null ? "—" : formatCompact(num(r, "cash", num(r, "cash_balance", 0)), "INR") },
              { key: "invested", header: "Securities", align: "right", render: (r) => formatCompact(num(r, "securities_market_value", num(r, "invested", 0)), "INR") },
              { key: "status", header: "Coverage", render: (r) => <StatusPill status={text(r, "calculation_status", "incomplete")} /> },
              { key: "asof", header: "As Of", render: (r) => text(r, "nav_date", text(r, "as_of_date", text(r, "snapshot_date", "—"))) },
            ]}
            rows={nav}
            rowKey={(r, i) => String(text(r, "nav_id", text(r, "id", i)))}
          />
        )}
      </Panel>

      <Panel icon={DollarSign} title="Cash Ledger">
        {cash.length === 0 ? <Empty icon={DollarSign} title="No cash entries" /> : (
          <DataTable
            columns={[
              { key: "client", header: "Client", render: (r) => text(r, "display_name", text(r, "client_name", text(r, "client_code", "—"))) },
              { key: "type", header: "Description", render: (r) => text(r, "description", text(r, "entry_type", "—")) },
              { key: "flow", header: "Flow", render: (r) => text(r, "flow_class", "—") },
              { key: "amount", header: "Amount", align: "right", render: (r) => formatCurrency(num(r, "amount", 0)) },
              { key: "date", header: "Date", render: (r) => text(r, "entry_ts", text(r, "entry_date", "—")) },
            ]}
            rows={cash}
            rowKey={(r, i) => String(text(r, "entry_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * RECONCILIATION
 * ============================================================ */
function ReconView() {
  const { data, isLoading } = usePortfolioOffice();
  const recon = data?.holding_reconciliation ?? [];
  const p2 = data?.p2cursor_reconciliation ?? [];

  return (
    <>
      <Panel icon={GitBranch} title="Broker Reconciliation">
        {isLoading ? <SkeletonGrid rows={3} /> : recon.length === 0 ? (
          <Empty icon={GitBranch} title="No reconciliation data" description="Broker statement reconciliation runs appear here." />
        ) : (
          <DataTable
            columns={[
              { key: "client", header: "Client", render: (r) => text(r, "client_name", "—") },
              { key: "symbol", header: "Symbol", render: (r) => text(r, "symbol") },
              { key: "break", header: "Break", align: "right", render: (r) => <span style={{ color: num(r, "break_qty", 0) !== 0 ? "var(--status-risk)" : "var(--status-ok)" }}>{num(r, "break_qty", 0)}</span> },
              { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "matched")} /> },
            ]}
            rows={recon}
            rowKey={(r, i) => String(text(r, "recon_id", text(r, "id", i)))}
          />
        )}
      </Panel>
    </>
  );
}

/* ============================================================
 * FOLIO TRACKERS
 * ============================================================ */
function TrackersView() {
  const { data, isLoading } = usePortfolioOffice();
  const positions = data?.latest_positions ?? [];

  return (
    <Panel icon={Activity} title="Folio Trackers">
      {isLoading ? <SkeletonGrid rows={4} /> : positions.length === 0 ? (
        <Empty icon={Activity} title="No folio trackers" description="Ongoing per-folio monitoring — thesis adherence, drift, review cadence." />
      ) : (
        <DataTable
          columns={[
            { key: "symbol", header: "Symbol", render: (r) => <strong>{text(r, "symbol")}</strong> },
            { key: "client", header: "Client", render: (r) => text(r, "client_name", "—") },
            { key: "review", header: "Next Review", render: (r) => text(r, "next_review_date", "—") },
            { key: "drift", header: "Drift", align: "right", render: (r) => <span style={{ color: Math.abs(num(r, "drift_pct", 0)) > 20 ? "var(--status-risk)" : "var(--status-ok)" }}>{formatPercent(num(r, "drift_pct", 0), { alreadyPercent: true })}</span> },
            { key: "thesis", header: "Thesis OK", render: (r) => <StatusPill status={num(r, "thesis_breached", 0) ? "risk" : "ok"} /> },
          ]}
          rows={positions}
          rowKey={(r, i) => String(text(r, "position_id", text(r, "id", i)))}
        />
      )}
    </Panel>
  );
}

function SkeletonGrid({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)" }}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} style={{ height: 40 }} />)}
    </div>
  );
}
