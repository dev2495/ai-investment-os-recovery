/**
 * Portfolio & Clients Terminal
 *
 * Routes: /portfolio/overview | /positions | /books | /clients | /imports |
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
  Plus, Save, Upload, FileSpreadsheet, ShieldCheck, Search, AlertTriangle,
} from "lucide-react";
import { usePortfolioOffice } from "../../data/queries";
import {
  useCaptureVisibleBrowserPortfolio, useReprocessSecureClientImport, useResolveSecureClientImportIdentity,
  useRunBrokerReconciliation, useRunP2CursorReconciliation,
  useStageClientOnboarding, useStageHoldingUpdate, useUploadSecureClientReport,
} from "../../data/actions";
import { get } from "../../data/client";
import { useUIStore } from "../../store";
import {
  Panel, MetricTile, Metric, DataTable, StatusPill, Badge, Empty, Skeleton,
  Button, Tabs, Drawer, Field, TextInput, TextArea, Select, KeyValue,
} from "../../system/primitives";
import { DonutChart, Treemap } from "../../system/charts";
import { text, num, bool, raw, formatRelative, formatCurrency, formatCompact, formatPercent } from "../../data/liveRow";
import type { LiveRow } from "../../data/liveRow";

const TABS = [
  { key: "overview", label: "Overview", icon: Briefcase },
  { key: "positions", label: "Positions", icon: PieChart },
  { key: "books", label: "Books", icon: BookOpen },
  { key: "clients", label: "Clients", icon: Users },
  { key: "imports", label: "Report Imports", icon: FileSpreadsheet },
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
      {tab === "imports" && <ClientImportsView />}
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

/* ============================================================
 * SECURE CLIENT REPORT IMPORTS
 * ============================================================ */
function ClientImportsView() {
  const { data, isLoading } = usePortfolioOffice();
  const upload = useUploadSecureClientReport();
  const capture = useCaptureVisibleBrowserPortfolio();
  const reprocess = useReprocessSecureClientImport();
  const pushToast = useUIStore((state) => state.pushToast);
  const clients = data?.clients ?? [];
  const accounts = data?.client_accounts ?? [];
  const allImports = data?.client_imports ?? [];
  const allBrowserCaptures = data?.client_browser_captures ?? [];
  const allExceptions = data?.client_import_exceptions ?? [];
  const allDerivedHoldings = data?.client_import_derived_holdings ?? [];
  const allCrossReportReconciliation = data?.client_import_reconciliation ?? [];
  const allHoldingsComparison = data?.client_import_holdings_comparison ?? [];
  const workspaceStatuses = data?.client_import_workspace_status ?? [];
  const allRealizedSummaries = data?.client_import_realized_summary ?? [];
  const [file, setFile] = React.useState<File | null>(null);
  const [clientCode, setClientCode] = React.useState("");
  const [accountCode, setAccountCode] = React.useState("");
  const [reportKind, setReportKind] = React.useState<"aditya_birla_money_capital_gains" | "broker_transactions" | "holdings_statement" | "broker_ledger" | "contract_note" | "portfolio_snapshot" | "tax_report" | "other">("aditya_birla_money_capital_gains");
  const [evidenceKey, setEvidenceKey] = React.useState<string | null>(null);
  const [identityKey, setIdentityKey] = React.useState<string | null>(null);
  const [captureSource, setCaptureSource] = React.useState<"aditya_birla_money_authenticated_portfolio" | "zerodha_authenticated_portfolio" | "authorized_broker_portfolio" | "authorized_portfolio_tracker">("aditya_birla_money_authenticated_portfolio");
  const [captureTitle, setCaptureTitle] = React.useState("");
  const [captureContent, setCaptureContent] = React.useState("");
  const [captureContentType, setCaptureContentType] = React.useState<"text/html" | "text/plain">("text/plain");
  const [captureConsent, setCaptureConsent] = React.useState(false);
  React.useEffect(() => {
    if (clientCode || clients.length === 0) return;
    const importedClientCode = text(allImports[0] ?? {}, "client_code");
    const fallbackClientCode = text(clients[0] ?? {}, "client_code");
    setClientCode(importedClientCode || fallbackClientCode);
  }, [allImports, clientCode, clients]);
  const imports = clientCode ? allImports.filter((row) => text(row, "client_code") === clientCode) : [];
  const browserCaptures = clientCode ? allBrowserCaptures.filter((row) => text(row, "client_code") === clientCode) : [];
  const exceptions = clientCode ? allExceptions.filter((row) => text(row, "client_code") === clientCode) : [];
  const derivedHoldings = clientCode ? allDerivedHoldings.filter((row) => text(row, "client_code") === clientCode) : [];
  const crossReportReconciliation = clientCode ? allCrossReportReconciliation.filter((row) => text(row, "client_code") === clientCode) : [];
  const holdingsComparison = clientCode ? allHoldingsComparison.filter((row) => text(row, "client_code") === clientCode) : [];
  const realizedSummaries = clientCode ? allRealizedSummaries.filter((row) => text(row, "client_code") === clientCode) : [];
  const workspaceStatus = workspaceStatuses.find((row) => text(row, "client_code") === clientCode);
  const historicalTransactionRows = imports.filter((row) => text(row, "report_kind") === "broker_transactions").reduce((total, row) => total + num(row, "transaction_count", 0), 0);
  const historicalCapitalLots = imports.filter((row) => ["aditya_birla_money_capital_gains", "tax_report"].includes(text(row, "report_kind"))).reduce((total, row) => total + num(row, "lot_count", 0), 0);
  const historicalOpenLots = derivedHoldings.reduce((total, row) => total + num(row, "open_lot_count", 0), 0);
  const historicalStarts = imports.map((row) => text(row, "source_period_start", "")).filter(Boolean).sort();
  const historicalEnds = imports.map((row) => text(row, "source_period_end", "")).filter(Boolean).sort();
  const historicalWindow = historicalStarts.length && historicalEnds.length ? `${historicalStarts[0]} → ${historicalEnds[historicalEnds.length - 1]}` : "No imported period";
  const scopedAccounts = accounts.filter((row) => !clientCode || text(row, "client_code") === clientCode);

  function submit() {
    if (!file || !clientCode || !accountCode) {
      pushToast({ title: "Choose the report and folio", message: "A file, client, and account are required.", tone: "warn", duration: 4500 });
      return;
    }
    upload.mutate({ file, client_code: clientCode, account_code: accountCode, report_kind: reportKind, actor: "Devarsh" }, {
      onSuccess: (result) => {
        pushToast({
          title: "Report preserved and inspected",
          message: `${num(result, "normalized_rows", 0)} evidence rows · ${num(result, "exception_count", 0)} exception(s) · identity ${text(result, "identity_status", "review")}`,
          tone: num(result, "exception_count", 0) ? "warn" : "ok",
          duration: 7000,
        });
        setFile(null);
      },
      onError: (error) => pushToast({ title: "Report intake failed", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  function acceptBrowserPaste(event: React.ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    const rich = event.clipboardData.getData("text/html");
    const plain = event.clipboardData.getData("text/plain");
    if (rich && /<table[\s>]/i.test(rich)) {
      setCaptureContent(rich);
      setCaptureContentType("text/html");
    } else {
      setCaptureContent(plain);
      setCaptureContentType("text/plain");
    }
  }

  function submitBrowserCapture() {
    if (!clientCode || !accountCode || !captureContent || !captureConsent) {
      pushToast({ title: "Complete the governed capture", message: "Choose the authorized folio, paste the selected visible table, and confirm consent.", tone: "warn", duration: 5500 });
      return;
    }
    capture.mutate({
      client_code: clientCode,
      account_code: accountCode,
      source_key: captureSource,
      page_title: captureTitle,
      captured_at: new Date().toISOString(),
      content_type: captureContentType,
      content: captureContent,
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: (result) => {
        pushToast({
          title: "Visible portfolio evidence captured",
          message: `${num(result, "normalized_rows", 0)} normalized row(s) · ${num(result, "exception_count", 0)} exception(s) · read-only`,
          tone: num(result, "exception_count", 0) ? "warn" : "ok",
          duration: 7000,
        });
        setCaptureContent("");
        setCaptureConsent(false);
      },
      onError: (error) => pushToast({ title: "Browser capture rejected", message: error.message, tone: "risk", duration: 7000 }),
    });
  }

  function rerun(importKey: string) {
    reprocess.mutate({ import_key: importKey, operator_confirmed: true, actor: "Devarsh" }, {
      onSuccess: (result) => pushToast({ title: "Report rechecked", message: `${num(result, "normalized_rows", 0)} evidence rows · ${num(result, "exception_count", 0)} exception(s)`, tone: "ok", duration: 5000 }),
      onError: (error) => pushToast({ title: "Recheck failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }

  return (
    <>
      <Panel icon={ShieldCheck} title="Authorized Client Evidence Workspace" actions={<Badge tone="ok">Private scope · read only</Badge>}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(240px, 1.25fr) repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
          <Field label="Client workspace" required>
            <Select value={clientCode} onChange={(event) => { setClientCode(event.target.value); setAccountCode(""); }}>
              <option value="">Select authorized client</option>
              {clients.map((row, index) => <option key={text(row, "client_code", index)} value={text(row, "client_code")}>{text(row, "display_name", "Client")}</option>)}
            </Select>
          </Field>
          <MetricTile tone={text(workspaceStatus ?? {}, "historical_status") === "source_backed" ? "default" : "warn"}>
            <Metric label="Historical evidence" value={text(workspaceStatus ?? {}, "historical_status", "not loaded").replace(/_/g, " ")} sub={num(workspaceStatus ?? {}, "historical_transaction_rows", 0).toLocaleString() + " transactions · " + num(workspaceStatus ?? {}, "capital_gain_lot_rows", 0).toLocaleString() + " gain lots"} />
          </MetricTile>
          <MetricTile><Metric label="Period-derived lots" value={num(workspaceStatus ?? {}, "open_lot_rows", 0).toLocaleString()} sub="Buy dates and FIFO cost · not current" /></MetricTile>
          <MetricTile tone="warn"><Metric label="Current holdings" value={text(workspaceStatus ?? {}, "current_holdings_status", "pending").replace(/_/g, " ")} sub={text(workspaceStatus ?? {}, "latest_capture_at") ? formatRelative(text(workspaceStatus ?? {}, "latest_capture_at")) : "Awaiting authorized capture"} /></MetricTile>
          <MetricTile tone="warn"><Metric label="Current cash" value={text(workspaceStatus ?? {}, "current_cash_status", "pending").replace(/_/g, " ")} sub="No estimate is substituted" /></MetricTile>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
          <div style={{ padding: "var(--space-3)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}>
            <strong>Performance / CAGR</strong>
            <div style={{ color: "var(--status-warn)", marginTop: "var(--space-1)" }}>{text(workspaceStatus ?? {}, "performance_status", "not calculated").replace(/_/g, " ")}</div>
            <small style={{ color: "var(--text-muted)" }}>Calculated only after current holdings, cash, opening history, and corporate actions reconcile.</small>
          </div>
          <div style={{ padding: "var(--space-3)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}>
            <strong>Portfolio risk</strong>
            <div style={{ color: "var(--status-warn)", marginTop: "var(--space-1)" }}>{text(workspaceStatus ?? {}, "risk_status", "not calculated").replace(/_/g, " ")}</div>
            <small style={{ color: "var(--text-muted)" }}>Final exposure and risk require current positions and source-backed prices.</small>
          </div>
          <div style={{ padding: "var(--space-3)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}>
            <strong>Open evidence exceptions</strong>
            <div style={{ color: num(workspaceStatus ?? {}, "blocking_exception_count", 0) ? "var(--status-risk)" : "var(--status-warn)", marginTop: "var(--space-1)" }}>{num(workspaceStatus ?? {}, "open_exception_count", 0)} open · {num(workspaceStatus ?? {}, "blocking_exception_count", 0)} blocking</div>
            <small style={{ color: "var(--text-muted)" }}>Exceptions stay visible; derived values are never silently promoted.</small>
          </div>
        </div>
        <div style={{ marginTop: "var(--space-3)", display: "flex", justifyContent: "space-between", gap: "var(--space-3)", flexWrap: "wrap", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          <span>{text(workspaceStatus ?? {}, "methodology", "Select an authorized client to load its source contract.")}</span>
          <strong style={{ color: "var(--status-ok)" }}>Broker writes and client-record mutation locked</strong>
        </div>
      </Panel>

      <Panel icon={Upload} title="Secure Broker Report Intake" actions={<Badge tone="ok">Private · checksum locked</Badge>}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
          <Field label="Client" required>
            <Select value={clientCode} onChange={(event) => { setClientCode(event.target.value); setAccountCode(""); }}>
              <option value="">Select authorized client</option>
              {clients.map((row, index) => <option key={text(row, "client_code", index)} value={text(row, "client_code")}>{text(row, "display_name", "Client")}</option>)}
            </Select>
          </Field>
          <Field label="Folio / account" required>
            <Select value={accountCode} onChange={(event) => setAccountCode(event.target.value)}>
              <option value="">Select account</option>
              {scopedAccounts.map((row, index) => <option key={text(row, "account_code", index)} value={text(row, "account_code")}>{text(row, "account_name", "Broker account")} · {text(row, "broker", "Broker")}</option>)}
            </Select>
          </Field>
          <Field label="Report type" required>
            <Select value={reportKind} onChange={(event) => setReportKind(event.target.value as typeof reportKind)}>
              <option value="aditya_birla_money_capital_gains">Aditya Birla Money capital gains</option>
              <option value="broker_transactions">Transaction report</option>
              <option value="holdings_statement">Holdings statement</option>
              <option value="broker_ledger">Cash / fund ledger</option>
              <option value="contract_note">Contract note</option>
              <option value="portfolio_snapshot">Portfolio snapshot</option>
              <option value="tax_report">Tax report</option>
              <option value="other">Other broker report</option>
            </Select>
          </Field>
          <Field label="Excel, CSV, or PDF" required>
            <input
              aria-label="Choose broker report"
              type="file"
              accept=".xls,.xlsx,.csv,.tsv,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              style={{ width: "100%", color: "var(--text)", fontSize: "var(--text-sm)" }}
            />
          </Field>
          <Button variant="primary" icon={Upload} onClick={submit} disabled={!file || !clientCode || !accountCode || upload.isPending}>{upload.isPending ? "Preserving & checking…" : "Import report"}</Button>
        </div>
        <div style={{ marginTop: "var(--space-3)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          The original file is stored once with an immutable SHA-256 checksum. Excel/CSV rows are staged for identity review and reconciliation; nothing is promoted into final holdings, cash, NAV, or trades automatically.
        </div>
        {file?.name.toLowerCase().endsWith(".pdf") ? <div role="status" style={{ marginTop: "var(--space-2)", color: "var(--status-warn)", fontSize: "var(--text-sm)" }}>PDF will be preserved as evidence. Use the Excel export for deterministic lot-level import.</div> : null}
      </Panel>

      <Panel icon={FileSpreadsheet} title="Historical Broker Evidence" actions={<Badge tone="ok">Primary historical record · active</Badge>}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "var(--space-3)" }}>
          <MetricTile><Metric label="Imported transactions" value={historicalTransactionRows.toLocaleString()} sub={historicalWindow} /></MetricTile>
          <MetricTile><Metric label="Capital-gain lots" value={historicalCapitalLots.toLocaleString()} sub="Purchase/sale dates and realized-gain evidence" /></MetricTile>
          <MetricTile><Metric label="Period-derived open lots" value={historicalOpenLots.toLocaleString()} sub="FIFO cost and buy dates; not current-state confirmation" /></MetricTile>
          <MetricTile tone={browserCaptures.length > 0 ? "default" : "warn"}><Metric label="Current broker state" value={browserCaptures.length > 0 ? "Captured for review" : "Pending confirmation"} sub="Current holdings and cash are a separate freshness layer" /></MetricTile>
        </div>
        <div style={{ marginTop: "var(--space-3)", color: "var(--text-secondary)", fontSize: "var(--text-sm)" }}>
          The supplied broker transaction and capital-gain exports remain the primary historical evidence and are usable now for transaction history, lot dates, source cost, realized-gain evidence, and period FIFO analysis. Safari capture complements this record with current holdings or funds/cash; it does not replace or diminish the imported documents.
        </div>
        {realizedSummaries.length > 0 ? <div style={{ marginTop: "var(--space-4)" }}><DataTable dense columns={[
          { key: "period", header: "Capital-gain evidence period", render: (row) => text(row, "source_period_start", "—") + " → " + text(row, "source_period_end", "—") },
          { key: "lots", header: "Source lots", align: "right", render: (row) => num(row, "realized_lot_rows", 0) },
          { key: "realized", header: "Source-reported gain", align: "right", render: (row) => formatCurrency(num(row, "source_realized_gain", 0)) },
          { key: "dates", header: "Buy / sale evidence", render: (row) => text(row, "earliest_purchase_date", "—") + " → " + text(row, "latest_sale_date", "—") },
          { key: "proof", header: "Provenance", render: (row) => <><span style={{ fontFamily: "var(--font-mono)" }}>{text(row, "checksum_prefix", "—")}</span><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "methodology", "Source values")}</div></> },
        ]} rows={realizedSummaries} rowKey={(row, index) => text(row, "import_key", index)} /></div> : null}
      </Panel>

      <Panel icon={Search} title="Authenticated Browser Capture" actions={<Badge tone="ok">User-initiated · read only</Badge>}>
        <div style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}>
          In Safari, select and copy only the visible holdings, transactions, or funds table for the authorized folio. Paste it below. AI OS keeps a checksum-locked sanitized snapshot and excludes URLs, cookies, form fields, scripts, hidden content, and broker actions.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "var(--space-3)", alignItems: "end" }}>
          <Field label="Authenticated source" required>
            <Select value={captureSource} onChange={(event) => setCaptureSource(event.target.value as typeof captureSource)}>
              <option value="aditya_birla_money_authenticated_portfolio">Aditya Birla Money portfolio</option>
              <option value="zerodha_authenticated_portfolio">Zerodha portfolio</option>
              <option value="authorized_broker_portfolio">Other authorized broker</option>
              <option value="authorized_portfolio_tracker">Authorized portfolio tracker</option>
            </Select>
          </Field>
          <Field label="Page label (optional)"><TextInput value={captureTitle} onChange={(event) => setCaptureTitle(event.target.value)} placeholder="Holdings / Funds / Transactions" /></Field>
          <div
            role="textbox"
            aria-label="Paste copied visible portfolio table"
            tabIndex={0}
            onPaste={acceptBrowserPaste}
            style={{ minHeight: 74, padding: "var(--space-3)", border: "1px dashed var(--border)", borderRadius: "var(--radius-md)", background: "var(--surface-raised)", color: captureContent ? "var(--status-ok)" : "var(--text-muted)", cursor: "text" }}
          >
            {captureContent ? `Visible table received (${captureContent.length.toLocaleString()} characters). Raw content is not echoed here.` : "Click here, then paste the selected visible table from Safari."}
          </div>
          <label style={{ display: "flex", gap: "var(--space-2)", alignItems: "flex-start", fontSize: "var(--text-sm)" }}>
            <input type="checkbox" checked={captureConsent} onChange={(event) => setCaptureConsent(event.target.checked)} />
            <span>I selected this visible content for the chosen client and authorize a read-only evidence capture.</span>
          </label>
          <Button variant="primary" icon={ShieldCheck} onClick={submitBrowserCapture} disabled={!clientCode || !accountCode || !captureContent || !captureConsent || capture.isPending}>{capture.isPending ? "Sanitizing & reconciling…" : "Capture copied page read-only"}</Button>
        </div>
        {!clientCode || !accountCode ? <div role="status" style={{ marginTop: "var(--space-2)", color: "var(--status-warn)", fontSize: "var(--text-sm)" }}>Choose the authorized client and folio in Secure Broker Report Intake above before capturing.</div> : null}
        {browserCaptures.length > 0 ? <div style={{ marginTop: "var(--space-4)" }}><DataTable dense columns={[
          { key: "source", header: "Source", render: (row) => text(row, "source_key", "authorized source").replace(/_/g, " ") },
          { key: "folio", header: "Client / folio", render: (row) => <><strong>{text(row, "display_name", "Client")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "account_name", "Authorized account")}</div></> },
          { key: "captured", header: "Captured", render: (row) => formatRelative(text(row, "captured_at")) },
          { key: "checksum", header: "Evidence", render: (row) => <span style={{ fontFamily: "var(--font-mono)" }}>{text(row, "checksum_prefix", "—")}</span> },
          { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "needs_review")} /> },
          { key: "exceptions", header: "Exceptions", align: "right", render: (row) => num(row, "exception_count", 0) },
          { key: "safety", header: "Boundary", render: () => <Badge tone="ok">No credentials · no writes</Badge> },
          { key: "actions", header: "Review", render: (row) => <div style={{ display: "flex", gap: "var(--space-1)" }}>
            <Button size="sm" variant="ghost" icon={Search} onClick={() => setEvidenceKey(text(row, "import_key"))}>Preview</Button>
            <Button size="sm" variant="ghost" onClick={() => rerun(text(row, "import_key"))} disabled={reprocess.isPending}>Retry</Button>
          </div> },
        ]} rows={browserCaptures} rowKey={(row, index) => text(row, "capture_key", `capture-${index}`)} /></div> : null}
      </Panel>

      <Panel icon={FileSpreadsheet} title="Import & Reconciliation Ledger">
        {isLoading ? <SkeletonGrid rows={4} /> : imports.length === 0 ? (
          <Empty icon={FileSpreadsheet} title="No client reports imported" description="Export a broker report, choose the authorized folio above, and import it here." />
        ) : (
          <DataTable
            columns={[
              { key: "client", header: "Client / folio", render: (row) => <><strong>{text(row, "display_name", "Client")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "account_name", text(row, "broker", "Account"))}</div></> },
              { key: "source", header: "Source", render: (row) => <><span>{text(row, "broker", "Broker")}</span><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "report_kind").replace(/_/g, " ")}</div></> },
              { key: "period", header: "Source period", render: (row) => `${text(row, "source_period_start", "—")} → ${text(row, "source_period_end", "—")}` },
              { key: "rows", header: "Evidence", align: "right", render: (row) => `${num(row, "transaction_count", 0)} rows / ${num(row, "lot_count", 0)} lots` },
              { key: "exceptions", header: "Exceptions", align: "right", render: (row) => <span style={{ color: num(row, "exception_count", 0) ? "var(--status-warn)" : "var(--status-ok)" }}>{num(row, "exception_count", 0)}</span> },
              { key: "identity", header: "Identity", render: (row) => <StatusPill status={text(row, "identity_status", "unresolved")} /> },
              { key: "recon", header: "Reconciliation", render: (row) => <StatusPill status={text(row, "reconciliation_status", "not_run")} /> },
              { key: "status", header: "Status", render: (row) => <StatusPill status={text(row, "status", "quarantined")} /> },
              { key: "checksum", header: "Provenance", render: (row) => <><span style={{ fontFamily: "var(--font-mono)" }}>{text(row, "checksum_prefix", "—")}</span><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{formatRelative(text(row, "received_at"))}</div></> },
              { key: "actions", header: "Actions", render: (row) => <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
                <Button size="sm" variant="ghost" icon={Search} onClick={() => setEvidenceKey(text(row, "import_key"))}>Evidence</Button>
                {text(row, "identity_status") === "needs_review" ? <Button size="sm" variant="ghost" icon={ShieldCheck} onClick={() => setIdentityKey(text(row, "import_key"))}>Resolve</Button> : null}
                <Button size="sm" variant="ghost" onClick={() => rerun(text(row, "import_key"))} disabled={reprocess.isPending}>Recheck</Button>
              </div> },
            ]}
            rows={imports}
            rowKey={(row, index) => text(row, "import_key", `import-${index}`)}
          />
        )}
      </Panel>

      <Panel icon={ShieldCheck} title="Cross-report Reconciliation" actions={<Badge tone="warn">Review before promotion</Badge>}>
        {crossReportReconciliation.length === 0 ? (
          <Empty icon={ShieldCheck} title="No paired reports reconciled" description="Import a transaction report and capital-gain report for the same approved folio. Matching runs only after identity confirmation." />
        ) : <DataTable dense columns={[
          { key: "account", header: "Authorized folio", render: (row) => text(row, "client_code", "Client folio") },
          { key: "lots", header: "Capital-gain lots", align: "right", render: (row) => num(row, "capital_gain_lot_rows", 0) },
          { key: "matched", header: "Matched", align: "right", render: (row) => <span style={{ color: "var(--status-ok)" }}>{num(row, "matched_rows", 0)}</span> },
          { key: "ambiguous", header: "Ambiguous", align: "right", render: (row) => <span style={{ color: "var(--status-warn)" }}>{num(row, "ambiguous_rows", 0)}</span> },
          { key: "unmatched", header: "Unmatched", align: "right", render: (row) => <span style={{ color: num(row, "unmatched_rows", 0) ? "var(--status-risk)" : "var(--status-ok)" }}>{num(row, "unmatched_rows", 0)}</span> },
          { key: "difference", header: "Absolute difference", align: "right", render: (row) => formatCurrency(num(row, "absolute_value_difference", 0)) },
          { key: "method", header: "Method", render: (row) => <span style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "methodology", "Date, quantity, and value tolerance")}</span> },
        ]} rows={crossReportReconciliation} rowKey={(row, index) => `${text(row, "capital_gain_import_key", index)}:${text(row, "transaction_import_key", "none")}`} />}
      </Panel>

      <Panel icon={FileSpreadsheet} title="Derived Holdings for Imported Period" actions={<Badge tone="warn">Not broker-confirmed</Badge>}>
        <div style={{ marginBottom: "var(--space-3)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          These quantities and costs use FIFO over the report's covered period. Missing opening history, corporate actions, current prices, and cash are never estimated; resolve exceptions and compare a current holdings statement before treating this as the portfolio of record.
        </div>
        {derivedHoldings.length === 0 ? (
          <Empty icon={FileSpreadsheet} title="No period-derived holdings" description="A confirmed transaction export is required before FIFO lots can be derived." />
        ) : <DataTable dense columns={[
          { key: "client", header: "Client / source accounts", render: (row) => <><strong>{text(row, "display_name", "Client")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>Import: {text(row, "imported_accounts", "—")} · Warehouse: {text(row, "canonical_accounts", "—")}</div></> },
          { key: "security", header: "Security", render: (row) => <strong>{text(row, "symbol", "—")}</strong> },
          { key: "quantity", header: "Derived units", align: "right", render: (row) => num(row, "derived_quantity", 0) },
          { key: "basis", header: "Derived cost", align: "right", render: (row) => formatCurrency(num(row, "derived_cost_basis", 0)) },
          { key: "average", header: "Average cost", align: "right", render: (row) => formatCurrency(num(row, "derived_average_cost", 0)) },
          { key: "dates", header: "Open buy dates", render: (row) => `${text(row, "earliest_open_buy_date", "—")} → ${text(row, "latest_open_buy_date", "—")}` },
          { key: "period", header: "Source period", render: (row) => `${text(row, "source_period_start", "—")} → ${text(row, "source_period_end", "—")}` },
          { key: "quality", header: "Quality", render: (row) => <StatusPill status={text(row, "quality_status", "incomplete")} /> },
        ]} rows={derivedHoldings} rowKey={(row, index) => `${text(row, "import_key", index)}:${text(row, "symbol", index)}`} />}
      </Panel>

      <Panel icon={GitBranch} title="Imported vs Current Warehouse Holdings" actions={<Badge tone={holdingsComparison.some((row) => text(row, "comparison_status") !== "matched") ? "warn" : "ok"}>Read-only comparison</Badge>}>
        <div style={{ marginBottom: "var(--space-3)", color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          This compares source-period FIFO quantities with the latest existing warehouse snapshot. Breaks prove that more evidence or reconciliation is required; this view never changes either source.
        </div>
        {holdingsComparison.length === 0 ? <Empty icon={GitBranch} title="No comparable holdings" description="Import a confirmed transaction report and retain a current warehouse position snapshot for the same authorized account." /> : <DataTable dense columns={[
          { key: "client", header: "Client / folio", render: (row) => <><strong>{text(row, "display_name", "Client")}</strong><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>{text(row, "account_name", "Approved account")}</div></> },
          { key: "symbol", header: "Security", render: (row) => <strong>{text(row, "symbol", "—")}</strong> },
          { key: "imported", header: "Imported-period units", align: "right", render: (row) => row.derived_quantity === null || row.derived_quantity === undefined ? "—" : num(row, "derived_quantity", 0) },
          { key: "warehouse", header: "Warehouse units", align: "right", render: (row) => row.canonical_quantity === null || row.canonical_quantity === undefined ? "—" : num(row, "canonical_quantity", 0) },
          { key: "difference", header: "Difference", align: "right", render: (row) => row.quantity_difference === null || row.quantity_difference === undefined ? "—" : num(row, "quantity_difference", 0) },
          { key: "status", header: "Result", render: (row) => <StatusPill status={text(row, "comparison_status", "not_comparable")} /> },
          { key: "freshness", header: "Evidence dates", render: (row) => <><div>Import to {text(row, "source_period_end", "—")}</div><div style={{ color: "var(--text-muted)", fontSize: "var(--text-xs)" }}>Warehouse {formatRelative(text(row, "canonical_as_of"))}</div></> },
        ]} rows={holdingsComparison} rowKey={(row, index) => `${text(row, "client_code", index)}:${text(row, "symbol", index)}`} />}
      </Panel>

      {exceptions.length > 0 ? (
        <Panel variant="warn" icon={AlertTriangle} title="Open Import Exceptions">
          <DataTable columns={[
            { key: "client", header: "Client", render: (row) => text(row, "client_code", "Authorized client") },
            { key: "row", header: "Source row", align: "right", render: (row) => num(row, "row_number", 0) || "Report" },
            { key: "issue", header: "Issue", render: (row) => <strong>{text(row, "exception_code").replace(/_/g, " ")}</strong> },
            { key: "severity", header: "Severity", render: (row) => <StatusPill status={text(row, "severity", "warning")} /> },
            { key: "action", header: "Required review", render: (row) => text(row, "message", "Review source evidence") },
          ]} rows={exceptions.slice(0, 100)} rowKey={(row, index) => String(text(row, "id", index))} />
        </Panel>
      ) : null}

      <ClientImportEvidenceDrawer importKey={evidenceKey} onClose={() => setEvidenceKey(null)} />
      <ClientImportIdentityDrawer importKey={identityKey} onClose={() => setIdentityKey(null)} />
    </>
  );
}

function ClientImportEvidenceDrawer({ importKey, onClose }: { importKey: string | null; onClose: () => void }) {
  const [payload, setPayload] = React.useState<LiveRow | null>(null);
  const [error, setError] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const pageSize = 100;
  React.useEffect(() => setOffset(0), [importKey]);
  React.useEffect(() => {
    if (!importKey) { setPayload(null); setError(""); return; }
    const controller = new AbortController();
    setPayload(null);
    get<LiveRow>("/api/client-imports/evidence", { query: { import_key: importKey, limit: pageSize, offset }, signal: controller.signal })
      .then(setPayload)
      .catch((cause: Error) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [importKey, offset]);
  const rows = Array.isArray(raw(payload ?? {}, "rows")) ? raw(payload ?? {}, "rows") as LiveRow[] : [];
  const exceptions = Array.isArray(raw(payload ?? {}, "exceptions")) ? raw(payload ?? {}, "exceptions") as LiveRow[] : [];
  const totalRows = num(payload ?? {}, "total_rows", rows.length);
  const hasMore = bool(payload ?? {}, "has_more", false);
  return <Drawer open={Boolean(importKey)} onClose={onClose} title="Normalized Transaction Evidence" icon={Search} width={980}>
    {error ? <div role="alert" style={{ color: "var(--status-risk)" }}>{error}</div> : !payload ? <SkeletonGrid rows={5} /> : <>
      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
        <Badge tone="accent">Raw payload hidden</Badge><Badge tone="ok">Broker writes locked</Badge><Badge tone={exceptions.length ? "warn" : "ok"}>{exceptions.length} exceptions</Badge>
        <span style={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", marginLeft: "auto" }}>{totalRows ? (offset + 1) + "–" + Math.min(offset + rows.length, totalRows) + " of " + totalRows + " evidence rows" : "No evidence rows"}</span>
        <Button size="sm" variant="ghost" onClick={() => setOffset(Math.max(0, offset - pageSize))} disabled={offset === 0}>Previous</Button>
        <Button size="sm" variant="ghost" onClick={() => setOffset(offset + pageSize)} disabled={!hasMore}>Next</Button>
      </div>
      {rows.length === 0 ? <Empty icon={Search} title="No structured rows" description="The source is preserved, but a structured Excel/CSV export is required." /> : <DataTable dense columns={[
        { key: "row", header: "Row", align: "right", render: (row) => num(row, "row_number", 0) },
        { key: "security", header: "Security", render: (row) => <strong>{text(row, "symbol", text(row, "instrument_name", "—"))}</strong> },
        { key: "buy", header: "Purchase", render: (row) => `${text(row, "purchase_date", "—")} · ${formatCurrency(num(row, "buy_value", 0))}` },
        { key: "sale", header: "Sale", render: (row) => `${text(row, "sale_date", text(row, "transaction_date", "—"))} · ${formatCurrency(num(row, "sell_value", 0))}` },
        { key: "qty", header: "Units", align: "right", render: (row) => num(row, "quantity", 0) },
        { key: "gain", header: "Source gain", align: "right", render: (row) => formatCurrency(num(row, "realized_gain", num(row, "taxable_gain", 0))) },
        { key: "held", header: "Held", align: "right", render: (row) => num(row, "holding_period_days", 0) ? `${num(row, "holding_period_days", 0)}d` : "—" },
        { key: "proof", header: "Evidence hash", render: (row) => <span style={{ fontFamily: "var(--font-mono)" }}>{text(row, "evidence_hash", "—")}</span> },
      ]} rows={rows} rowKey={(row, index) => `${text(row, "evidence_hash", index)}:${text(row, "layer")}`} />}
    </>}
  </Drawer>;
}

function ClientImportIdentityDrawer({ importKey, onClose }: { importKey: string | null; onClose: () => void }) {
  const mutation = useResolveSecureClientImportIdentity();
  const pushToast = useUIStore((state) => state.pushToast);
  const [rationale, setRationale] = React.useState("");
  function decide(decision: "confirm" | "reject") {
    if (!importKey || rationale.trim().length < 10) {
      pushToast({ title: "Explain the identity check", message: "Record how the report was matched to this folio.", tone: "warn", duration: 4500 });
      return;
    }
    mutation.mutate({ import_key: importKey, decision, rationale: rationale.trim(), operator_confirmed: true, actor: "Devarsh" }, {
      onSuccess: () => { pushToast({ title: decision === "confirm" ? "Folio identity confirmed" : "Import rejected", message: "The decision and rationale were written to the audit trail.", tone: decision === "confirm" ? "ok" : "warn", duration: 5000 }); setRationale(""); onClose(); },
      onError: (error) => pushToast({ title: "Identity review failed", message: error.message, tone: "risk", duration: 6000 }),
    });
  }
  return <Drawer open={Boolean(importKey)} onClose={onClose} title="Resolve Report Identity" icon={ShieldCheck} width={560}
    footer={<div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)" }}><Button variant="ghost" onClick={() => decide("reject")} disabled={mutation.isPending}>Reject</Button><Button variant="primary" icon={ShieldCheck} onClick={() => decide("confirm")} disabled={mutation.isPending}>Confirm folio match</Button></div>}>
    <p style={{ color: "var(--text-muted)", marginTop: 0 }}>Confirm only after matching the broker report header to the selected client and folio. This unlocks reconciliation review, not trading or automatic promotion.</p>
    <Field label="Identity evidence and rationale" required><TextArea rows={5} value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Matched the broker account name and masked identifier to the approved client record…" /></Field>
  </Drawer>;
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
  const brokerRun = useRunBrokerReconciliation();
  const p2Run = useRunP2CursorReconciliation();
  const pushToast = useUIStore((state) => state.pushToast);
  const [clientCode, setClientCode] = React.useState("");
  const recon = data?.holding_reconciliation ?? [];
  const p2 = data?.p2cursor_reconciliation ?? [];

  const notify = (title: string, mutation: typeof brokerRun | typeof p2Run, payload: Record<string, unknown>) => {
    mutation.mutate(payload as never, {
      onSuccess: (result) => pushToast({ title, message: String(num(result, "issue_count", 0)) + " issue(s) require review", tone: num(result, "issue_count", 0) ? "warn" : "ok", duration: 4000 }),
      onError: (error) => pushToast({ title: "Reconciliation failed", message: error.message, tone: "risk", duration: 5000 }),
    });
  };

  return (
    <>
      <Panel icon={GitBranch} title="Reconciliation Controls" actions={
        <>
          <Button size="sm" variant="ghost" onClick={() => notify("Broker reconciliation complete", brokerRun, { actor: "Devarsh" })} disabled={brokerRun.isPending}>Run broker</Button>
          <Button size="sm" variant="primary" onClick={() => notify("P2Cursor reconciliation complete", p2Run, { actor: "Devarsh", client_code: clientCode || undefined })} disabled={p2Run.isPending}>Run P2Cursor</Button>
        </>
      }>
        <div style={{ padding: "var(--space-3)", maxWidth: 360 }}>
          <Field label="P2Cursor client code (optional)"><TextInput value={clientCode} onChange={(event) => setClientCode(event.target.value.trim().toUpperCase())} placeholder="All mapped clients" /></Field>
        </div>
      </Panel>

      <Panel icon={GitBranch} title="Holding Source Reconciliation">
        {isLoading ? <SkeletonGrid rows={3} /> : recon.length === 0 ? (
          <Empty icon={GitBranch} title="No holding reconciliation runs" description="Record holding observations and run reconciliation to compare broker and managed holdings." />
        ) : (
          <DataTable columns={[
            { key: "account", header: "Account", render: (r) => text(r, "account_code", text(r, "client_name", "—")) },
            { key: "source", header: "Source", render: (r) => text(r, "source_label", "—") },
            { key: "matched", header: "Matched", align: "right", render: (r) => num(r, "matched_count", 0) },
            { key: "breaks", header: "Breaks", align: "right", render: (r) => num(r, "break_count", num(r, "issue_count", 0)) },
            { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", text(r, "reconciliation_status", "review"))} /> },
          ]} rows={recon} rowKey={(r, i) => String(text(r, "run_key", text(r, "id", i)))} />
        )}
      </Panel>

      <Panel icon={GitBranch} title="P2Cursor vs Canonical Portfolio">
        {isLoading ? <SkeletonGrid rows={3} /> : p2.length === 0 ? (
          <Empty icon={GitBranch} title="No P2Cursor reconciliation runs" description="Run P2Cursor reconciliation for all mapped clients or enter one client code above." />
        ) : (
          <DataTable columns={[
            { key: "client", header: "Client", render: (r) => text(r, "client_name", text(r, "client_code", "—")) },
            { key: "account", header: "P2 account", render: (r) => text(r, "p2_account_code", "—") },
            { key: "matched", header: "Matched", align: "right", render: (r) => num(r, "matched_symbols", 0) },
            { key: "p2only", header: "P2 only", align: "right", render: (r) => num(r, "p2_only_symbols", 0) },
            { key: "canonicalonly", header: "Canonical only", align: "right", render: (r) => num(r, "comparison_only_symbols", 0) },
            { key: "qty", header: "Qty breaks", align: "right", render: (r) => num(r, "quantity_mismatch_symbols", 0) },
            { key: "status", header: "Status", render: (r) => <StatusPill status={text(r, "status", "review")} /> },
            { key: "asof", header: "Run", render: (r) => formatRelative(text(r, "created_at")) },
          ]} rows={p2} rowKey={(r, i) => String(text(r, "run_key", text(r, "id", i)))} />
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
