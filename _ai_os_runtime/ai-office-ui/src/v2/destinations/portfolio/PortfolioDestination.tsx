import React from "react";
import { BookOpen, Briefcase, CircleDollarSign, Scale, Users, Wrench } from "lucide-react";
import { usePortfolioOffice } from "../../data/queries";
import type { LiveRow } from "../../data/liveRow";
import { formatCompact, formatCurrency, formatPercent, num, primaryText, text } from "../../data/liveRow";
import { Freshness, LiveTable, MetricCell, MetricStrip, RowTitle, StatusCell, WorkspaceError, WorkspaceGrid, countStatus } from "../../data/WorkspaceKit";
import { Badge, Panel, StatusPill, Tabs } from "../../system/primitives";
import { DonutChart, Treemap } from "../../system/charts";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "books", label: "Books" },
  { key: "positions", label: "Positions" },
  { key: "clients", label: "Clients" },
  { key: "accounting", label: "Accounting" },
  { key: "reconciliation", label: "Reconciliation" },
];

export default function PortfolioDestination() {
  const query = usePortfolioOffice();
  const [tab, setTab] = React.useState("overview");
  const data = query.data;
  const gross = (data?.latest_positions ?? []).reduce((sum, row) => sum + Math.abs(num(row, "market_value")), 0);
  const pnl = (data?.latest_positions ?? []).reduce((sum, row) => sum + num(row, "unrealized_pnl"), 0);
  const conflicts = data?.cross_book_conflicts.length ?? 0;
  const stale = countStatus(data?.holding_reconciliation ?? [], ["break", "stale", "mismatch"]);

  return (
    <div className="aios-destination">
      <div className="aios-destination__head">
        <div className="aios-destination__title-row">
          <div className="aios-destination__title">Portfolio Office</div>
          <Freshness generatedAt={data?.generated_at} />
        </div>
        <div className="aios-destination__subtitle">Every client, position and purpose kept separate across long-term, tactical, quant, active and hedge books.</div>
        <Tabs tabs={TABS} active={tab} onChange={setTab} />
      </div>
      <WorkspaceError error={query.error} />
      <MetricStrip>
        <MetricCell label="Assets observed" value={formatCompact(gross, "INR")} detail={`${data?.latest_positions.length ?? 0} positions`} />
        <MetricCell label="Unrealised P&L" value={formatCompact(pnl, "INR")} tone={pnl < 0 ? "risk" : "ok"} />
        <MetricCell label="Clients" value={data?.clients.length ?? 0} detail={`${data?.client_accounts.length ?? 0} accounts`} />
        <MetricCell label="Investment books" value={data?.investment_books.length ?? 0} detail="purpose-aware exposures" />
        <MetricCell label="Cross-book conflicts" value={conflicts} tone={conflicts ? "warn" : "ok"} />
        <MetricCell label="Reconciliation flags" value={stale} tone={stale ? "risk" : "ok"} />
      </MetricStrip>
      {data ? <PortfolioTab tab={tab} data={data} /> : null}
    </div>
  );
}

function PortfolioTab({ tab, data }: { tab: string; data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  if (tab === "overview") return <Overview data={data} />;
  if (tab === "books") return <Books data={data} />;
  if (tab === "positions") return <Positions data={data} />;
  if (tab === "clients") return <Clients data={data} />;
  if (tab === "accounting") return <Accounting data={data} />;
  return <Reconciliation data={data} />;
}

function Overview({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  const allocation = data.investment_books.map((row) => ({ name: text(row, "book_name", text(row, "book_key")), value: Math.abs(num(row, "gross_exposure")) })).filter((row) => row.value > 0);
  const exposure = data.symbol_book_exposure.slice(0, 25).map((row) => ({ name: text(row, "symbol"), value: Math.abs(num(row, "gross_exposure")) })).filter((row) => row.value > 0);
  return (
    <WorkspaceGrid>
      <Panel icon={Briefcase} title="Book allocation" actions={<Badge>{allocation.length} books</Badge>}><DonutChart data={allocation} height={260} /></Panel>
      <Panel icon={Scale} title="Largest exposures" actions={<Badge>{exposure.length} symbols</Badge>}><Treemap data={exposure} height={260} /></Panel>
      <Panel className="aios-workspace-span" icon={Wrench} title="Decision readiness">
        <LiveTable rows={data.portfolio_intelligence} emptyTitle="No portfolio intelligence" columns={[
          { key: "item_name", label: "Item", render: (row) => <RowTitle row={row} titleKeys={["item_name", "item_key"]} detailKeys={["interpretation"]} /> },
          { key: "section", label: "Section" }, { key: "item_value", label: "Value", align: "right" },
        ]} />
      </Panel>
      <Panel className="aios-workspace-span" icon={Scale} title="Book coordination questions" actions={<Badge tone={data.coordination_questions.length ? "warn" : "ok"}>{data.coordination_questions.length} open</Badge>}>
        <LiveTable rows={data.coordination_questions} emptyTitle="No cross-book coordination questions" columns={[
          { key: "symbol", label: "Exposure", render: (row) => <RowTitle row={row} titleKeys={["symbol"]} detailKeys={["coordination_question"]} /> },
          { key: "client_name", label: "Client" }, { key: "active_books", label: "Books" },
          { key: "gross_long", label: "Gross long", align: "right", render: (row) => formatCurrency(num(row, "gross_long")) },
          { key: "gross_short", label: "Gross short", align: "right", render: (row) => formatCurrency(num(row, "gross_short")) },
          { key: "offset_ratio", label: "Offset", align: "right", render: (row) => formatPercent(num(row, "offset_ratio"), { alreadyPercent: num(row, "offset_ratio") > 1 }) },
          { key: "severity", label: "Status", render: (row) => <StatusCell row={row} keys={["severity"]} /> },
        ]} />
      </Panel>
    </WorkspaceGrid>
  );
}

function Books({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={BookOpen} title="Independent investment books"><LiveTable rows={data.investment_books} emptyTitle="No books configured" columns={[
    { key: "book_name", label: "Book", render: (row) => <RowTitle row={row} titleKeys={["book_name"]} detailKeys={["mandate", "objective"]} /> },
    { key: "default_horizon", label: "Horizon" }, { key: "owner_agent", label: "Owner" },
    { key: "position_count", label: "Positions", align: "right" },
    { key: "gross_exposure", label: "Gross", align: "right", render: (row) => formatCurrency(num(row, "gross_exposure")) },
    { key: "net_exposure", label: "Net", align: "right", render: (row) => formatCurrency(num(row, "net_exposure")) },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel className="aios-workspace-span" icon={Scale} title="Symbol exposure across books"><LiveTable rows={data.symbol_book_exposure} emptyTitle="No book exposure" columns={[
    { key: "symbol", label: "Symbol", render: (row) => <RowTitle row={row} titleKeys={["symbol"]} detailKeys={["client_name"]} /> },
    { key: "long_term_exposure", label: "Long-term", align: "right", render: (row) => formatCurrency(num(row, "long_term_exposure")) },
    { key: "tactical_exposure", label: "Tactical", align: "right", render: (row) => formatCurrency(num(row, "tactical_exposure")) },
    { key: "quant_exposure", label: "Quant", align: "right", render: (row) => formatCurrency(num(row, "quant_exposure")) },
    { key: "active_trading_exposure", label: "Active", align: "right", render: (row) => formatCurrency(num(row, "active_trading_exposure")) },
    { key: "net_exposure", label: "Net", align: "right", render: (row) => formatCurrency(num(row, "net_exposure")) },
    { key: "overall_bias", label: "Bias", render: (row) => <StatusPill status={text(row, "overall_bias")}>{text(row, "overall_bias")}</StatusPill> },
  ]} /></Panel></WorkspaceGrid>;
}

function Positions({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Briefcase} title="Purpose-aware positions" actions={<Badge>{data.book_positions.length} rows</Badge>}><LiveTable rows={data.book_positions} emptyTitle="No positions" limit={200} columns={[
    { key: "symbol", label: "Position", render: (row) => <RowTitle row={row} titleKeys={["symbol"]} detailKeys={["thesis", "purpose_name"]} /> },
    { key: "client_name", label: "Client" }, { key: "book_name", label: "Book" }, { key: "direction", label: "Direction" },
    { key: "quantity", label: "Qty", align: "right" }, { key: "market_price", label: "Price", align: "right", render: (row) => formatCurrency(num(row, "market_price")) },
    { key: "market_value", label: "Value", align: "right", render: money }, { key: "time_horizon", label: "Horizon" },
  ]} /></Panel><Panel className="aios-workspace-span" icon={Scale} title="Raw broker positions"><LiveTable rows={data.latest_positions} emptyTitle="No broker positions" limit={250} columns={[
    { key: "symbol", label: "Holding", render: (row) => <RowTitle row={row} titleKeys={["symbol"]} detailKeys={["display_name", "account_code"]} /> },
    { key: "quantity", label: "Qty", align: "right" }, { key: "average_price", label: "Average", align: "right", render: (row) => formatCurrency(num(row, "average_price")) },
    { key: "market_price", label: "Market", align: "right", render: (row) => formatCurrency(num(row, "market_price")) },
    { key: "market_value", label: "Value", align: "right", render: money },
    { key: "unrealized_pnl", label: "P&L", align: "right", render: (row) => <span className={num(row, "unrealized_pnl") < 0 ? "aios-negative" : "aios-positive"}>{formatCurrency(num(row, "unrealized_pnl"))}</span> },
    { key: "as_of", label: "As of" },
  ]} /></Panel></WorkspaceGrid>;
}

function Clients({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Users} title="Client control plane"><LiveTable rows={data.clients} emptyTitle="No clients" columns={[
    { key: "display_name", label: "Client", render: (row) => <RowTitle row={row} titleKeys={["display_name"]} detailKeys={["client_code"]} /> },
    { key: "risk_profile", label: "Risk profile" }, { key: "account_count", label: "Accounts", align: "right" },
    { key: "latest_position_count", label: "Positions", align: "right" }, { key: "latest_market_value", label: "Market value", align: "right", render: money },
    { key: "active", label: "Active", render: (row) => <StatusCell row={row} keys={["active"]} /> },
  ]} /></Panel><Panel icon={Scale} title="Suitability reviews"><LiveTable rows={data.client_suitability} emptyTitle="No suitability reviews" columns={[
    { key: "display_name", label: "Client" }, { key: "suitability_status", label: "Status", render: (row) => <StatusCell row={row} keys={["suitability_status", "review_health"]} /> },
    { key: "investment_horizon", label: "Horizon" }, { key: "next_review_due_at", label: "Next review" },
  ]} /></Panel><Panel icon={Users} title="Report delivery"><LiveTable rows={data.client_report_delivery} emptyTitle="No client reports" columns={[
    { key: "display_name", label: "Client" }, { key: "report_period", label: "Period" }, { key: "delivery_channel", label: "Channel" },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} keys={["status", "approval_status"]} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function Accounting({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={CircleDollarSign} title="Client NAV"><LiveTable rows={data.client_nav} emptyTitle="No NAV calculations" columns={[
    { key: "display_name", label: "Client", render: (row) => <RowTitle row={row} titleKeys={["display_name"]} detailKeys={["account_code"]} /> },
    { key: "nav_date", label: "Date" }, { key: "securities_market_value", label: "Securities", align: "right", render: money },
    { key: "cash_balance", label: "Cash", align: "right", render: money }, { key: "nav", label: "NAV", align: "right", render: money },
    { key: "calculation_status", label: "Status", render: (row) => <StatusCell row={row} keys={["calculation_status"]} /> },
  ]} /></Panel><Panel icon={CircleDollarSign} title="Performance"><LiveTable rows={data.client_performance} emptyTitle="No performance periods" columns={[
    { key: "display_name", label: "Client" }, { key: "period_type", label: "Period" }, { key: "twr_return_pct", label: "TWR", align: "right", render: pct },
    { key: "active_return_pct", label: "Active", align: "right", render: pct }, { key: "calculation_status", label: "Status", render: (row) => <StatusCell row={row} keys={["calculation_status"]} /> },
  ]} /></Panel><Panel icon={CircleDollarSign} title="Cash ledger"><LiveTable rows={data.cash_ledger} emptyTitle="No cash entries" columns={[
    { key: "display_name", label: "Client" }, { key: "entry_type", label: "Type" }, { key: "amount", label: "Amount", align: "right", render: money },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel></WorkspaceGrid>;
}

function Reconciliation({ data }: { data: NonNullable<ReturnType<typeof usePortfolioOffice>["data"]> }) {
  return <WorkspaceGrid><Panel className="aios-workspace-span" icon={Wrench} title="Holding reconciliation"><LiveTable rows={data.holding_reconciliation} emptyTitle="No reconciliation runs" columns={[
    { key: "display_name", label: "Run", render: (row) => <RowTitle row={row} titleKeys={["display_name", "run_key"]} detailKeys={["source_label", "account_code"]} /> },
    { key: "matched_count", label: "Matched", align: "right" }, { key: "break_count", label: "Breaks", align: "right" },
    { key: "material_break_count", label: "Material", align: "right" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel icon={Wrench} title="P2Cursor comparisons"><LiveTable rows={data.p2cursor_reconciliation} emptyTitle="No P2Cursor comparison" columns={[
    { key: "client_name", label: "Client" }, { key: "p2_position_count", label: "P2", align: "right" }, { key: "comparison_position_count", label: "Warehouse", align: "right" },
    { key: "quantity_mismatch_symbols", label: "Mismatches" }, { key: "status", label: "Status", render: (row) => <StatusCell row={row} /> },
  ]} /></Panel><Panel icon={Wrench} title="Manual updates"><LiveTable rows={data.manual_updates} emptyTitle="No manual holding updates" columns={[
    { key: "symbol", label: "Holding" }, { key: "client_code", label: "Client" }, { key: "quantity", label: "Qty", align: "right" },
    { key: "status", label: "Status", render: (row) => <StatusCell row={row} keys={["approval_status", "status"]} /> },
  ]} /></Panel></WorkspaceGrid>;
}

const money = (row: LiveRow) => formatCurrency(num(row, "market_value", num(row, "gross_exposure", num(row, "net_exposure", num(row, "amount")))));
const pct = (row: LiveRow) => formatPercent(num(row, "twr_return_pct", num(row, "active_return_pct")), { alreadyPercent: true });
