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
  Plus, ChevronRight, TrendingUp, Wallet,
} from "lucide-react";
import { usePortfolioOffice } from "../../data/queries";
import { useStageHoldingUpdate } from "../../data/actions";
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

  const filtered = filter ? positions.filter((r) => text(r, "symbol").toLowerCase().includes(filter.toLowerCase())) : positions;
  const totalMarketValue = positions.reduce((sum, r) => sum + Math.abs(num(r, "market_value", 0)), 0);

  return (
    <Panel icon={PieChart} title="Positions"
      actions={<TextInput placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 160 }} />}
    >
      {isLoading ? <SkeletonGrid rows={6} /> : filtered.length === 0 ? (
        <Empty icon={PieChart} title="No positions" />
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

  return (
    <>
      <Panel icon={Users} title="Client Registry"
        actions={<Button size="sm" variant="primary" icon={Plus}>Onboard Client</Button>}
      >
        {isLoading ? <SkeletonGrid rows={3} /> : clients.length === 0 ? (
          <Empty icon={Users} title="No clients" description="Onboard a client to begin portfolio management." />
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
    </>
  );
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
