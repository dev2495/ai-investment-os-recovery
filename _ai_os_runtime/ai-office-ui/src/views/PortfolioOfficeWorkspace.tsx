import {
  AlertTriangle,
  BookOpenCheck,
  BriefcaseBusiness,
  ClipboardPlus,
  DatabaseZap,
  RefreshCw,
  ShieldCheck,
  Users
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { stageHoldingUpdate, syncPositionReadinessRemediation, type LiveRow } from "../api/live";
import { fetchPortfolioOfficeSnapshot, type PortfolioOfficeSnapshot } from "../api/portfolioOffice";

type ConnectionStatus = "loading" | "online" | "offline";
type PortfolioMode = "portfolio" | "clients";

interface Props {
  mode: PortfolioMode;
  onStatusChange: (status: ConnectionStatus) => void;
}

function value(row: LiveRow | undefined, key: string, fallback = "-"): string {
  const raw = row?.[key];
  if (raw === null || raw === undefined || raw === "") return fallback;
  if (typeof raw === "object") {
    if (Array.isArray(raw)) return raw.map(String).join(", ") || fallback;
    return Object.entries(raw).map(([label, detail]) => `${label.replace(/_/g, " ")}: ${String(detail)}`).join(" · ") || fallback;
  }
  return String(raw);
}

function amount(raw: unknown): string {
  const numeric = Number(raw ?? 0);
  if (!Number.isFinite(numeric)) return "-";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(numeric);
}

function date(raw: unknown): string {
  if (!raw) return "not recorded";
  const parsed = new Date(String(raw));
  return Number.isNaN(parsed.getTime()) ? String(raw) : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (["active", "applied", "complete", "completed", "fresh", "healthy", "matched", "ready"].includes(normalized)) return "active";
  if (["blocked", "breach", "critical", "error", "failed", "stale"].includes(normalized)) return "blocked";
  return "waiting";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${statusClass(status)}`}>{status.replace(/_/g, " ")}</span>;
}

function Panel({ action, children, className, icon, title }: { action?: ReactNode; children: ReactNode; className: string; icon: ReactNode; title: string }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div>{icon}<h2>{title}</h2></div>{action}</div>{children}</section>;
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export default function PortfolioOfficeWorkspace({ mode, onStatusChange }: Props) {
  const [snapshot, setSnapshot] = useState<PortfolioOfficeSnapshot | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedClient, setSelectedClient] = useState("all");
  const [stageBusy, setStageBusy] = useState(false);
  const [remediationBusy, setRemediationBusy] = useState(false);
  const [holding, setHolding] = useState({ accountCode: "", symbol: "", quantity: "", averagePrice: "", marketPrice: "", reason: "manual portfolio update" });

  const refresh = useCallback(async () => {
    setStatus("loading");
    onStatusChange("loading");
    try {
      const next = await fetchPortfolioOfficeSnapshot();
      setSnapshot(next);
      setError("");
      setStatus("online");
      onStatusChange("online");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Portfolio Office API unavailable");
      setStatus("offline");
      onStatusChange("offline");
    }
  }, [onStatusChange]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    const handleRefresh = () => void refresh();
    window.addEventListener("aios:portfolio-office-refresh", handleRefresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("aios:portfolio-office-refresh", handleRefresh);
    };
  }, [refresh]);

  const clients = snapshot?.clients ?? [];
  const accounts = (snapshot?.client_accounts ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const positions = (snapshot?.latest_positions ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const bookPositions = (snapshot?.book_positions ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const symbolExposure = (snapshot?.symbol_book_exposure ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const clientExposure = (snapshot?.client_book_exposure ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const conflicts = (snapshot?.cross_book_conflicts ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const manualUpdates = (snapshot?.manual_updates ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const reconciliations = (snapshot?.p2cursor_reconciliation ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const totalValue = useMemo(() => positions.reduce((sum, row) => sum + Number(row.market_value ?? 0), 0), [positions]);
  const grossExposure = useMemo(() => symbolExposure.reduce((sum, row) => sum + Number(row.gross_exposure ?? 0), 0), [symbolExposure]);
  const netExposure = useMemo(() => symbolExposure.reduce((sum, row) => sum + Number(row.net_exposure ?? 0), 0), [symbolExposure]);
  const pendingUpdates = manualUpdates.filter((row) => !["applied", "rejected"].includes(value(row, "status", "").toLowerCase()));
  const execution = snapshot?.execution_control[0];

  const chooseClient = (clientCode: string) => {
    setSelectedClient(clientCode);
    const firstAccount = snapshot?.client_accounts.find((row) => value(row, "client_code") === clientCode);
    setHolding((current) => ({ ...current, accountCode: firstAccount ? value(firstAccount, "account_code", "") : "" }));
  };

  const submitHolding = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedClient === "all") {
      setError("Select one client before staging a holding update.");
      return;
    }
    setStageBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await stageHoldingUpdate({
        actor: "Devarsh",
        client_code: selectedClient,
        account_code: holding.accountCode,
        symbol: holding.symbol,
        quantity: holding.quantity,
        average_price: holding.averagePrice || undefined,
        market_price: holding.marketPrice || undefined,
        update_reason: holding.reason
      });
      setNotice(`Holding update #${value(result, "id")} staged for human review; live positions were not changed.`);
      setHolding((current) => ({ ...current, symbol: "", quantity: "", averagePrice: "", marketPrice: "" }));
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Holding update could not be staged");
    } finally {
      setStageBusy(false);
    }
  };

  const runRemediation = async () => {
    setRemediationBusy(true);
    setError("");
    setNotice("");
    try {
      await syncPositionReadinessRemediation({ actor: "Jarvis", create_tasks: true, limit: 100 });
      setNotice("Position-readiness queue synchronized; no live holdings or orders were changed.");
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Remediation sync failed");
    } finally {
      setRemediationBusy(false);
    }
  };

  return (
    <div className="portfolio-office-workspace">
      <div className="workspace-filter-bar">
        <label><span>Client scope</span><select aria-label="Client scope" onChange={(event) => chooseClient(event.target.value)} value={selectedClient}><option value="all">All clients</option>{clients.map((client) => <option key={value(client, "client_code")} value={value(client, "client_code")}>{value(client, "display_name")} · {value(client, "client_code")}</option>)}</select></label>
        <div><span>{selectedClient === "all" ? "Consolidated office view" : clients.find((client) => value(client, "client_code") === selectedClient)?.display_name as string}</span><button className="mini-action-button" disabled={status === "loading"} onClick={() => void refresh()} type="button"><RefreshCw size={14} />{status === "loading" ? "Checking" : "Refresh"}</button></div>
      </div>

      <section className="metric-grid" aria-label="Portfolio Office metrics">
        <div className="metric-tile"><span>Scoped API</span><strong>{status === "online" ? "Online" : status}</strong><p className={status === "online" ? "tone-good" : "tone-warn"}>{snapshot?.payload_profile.row_count ?? 0} live rows</p></div>
        <div className="metric-tile"><span>Market Value</span><strong>{amount(totalValue)}</strong><p className="tone-neutral">{positions.length} current positions</p></div>
        <div className="metric-tile"><span>Gross Exposure</span><strong>{amount(grossExposure)}</strong><p className="tone-neutral">across active books</p></div>
        <div className="metric-tile"><span>Net Exposure</span><strong>{amount(netExposure)}</strong><p className={netExposure < 0 ? "tone-warn" : "tone-good"}>{conflicts.length} cross-book conflicts</p></div>
        <div className="metric-tile"><span>Execution</span><strong>{value(execution, "global_execution_locked", "true") === "true" ? "Locked" : "Review"}</strong><p className="tone-good">broker writes disabled</p></div>
      </section>

      {error ? <div className="error-strip">{error}</div> : null}
      {notice ? <div className="success-strip">{notice}</div> : null}

      {mode === "portfolio" ? (
        <section className="dashboard-grid">
          <Panel className="span-5" icon={<ShieldCheck size={17} />} title="Portfolio Intelligence"><div className="portfolio-intelligence-list scoped-scroll-list">{snapshot?.portfolio_intelligence.map((row) => <article className="portfolio-intelligence-row" key={`${value(row, "section")}-${value(row, "item_key")}-${value(row, "item_name")}`}><div><strong>{value(row, "item_name")}</strong><p>{value(row, "interpretation")}</p></div><span>{value(row, "item_value")}</span></article>)}{!snapshot?.portfolio_intelligence.length ? <Empty>No portfolio intelligence rows.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<BookOpenCheck size={17} />} title="Investment Books" action={<span>{snapshot?.investment_books.length ?? 0} books</span>}><div className="source-check-list scoped-scroll-list">{snapshot?.investment_books.map((book) => <article className="source-check-row" key={value(book, "book_key")}><div><strong>{value(book, "book_name")}</strong><p>{value(book, "objective", value(book, "mandate"))}</p></div><StatusPill status={value(book, "status", "active")} /><span>{amount(book.net_exposure)}</span><time>{value(book, "position_count", "0")} positions</time></article>)}</div></Panel>
          <Panel className="span-7" icon={<BriefcaseBusiness size={17} />} title="Multi-Book Symbol Exposure" action={<span>{symbolExposure.length} symbols</span>}><div className="source-check-list scoped-scroll-list">{symbolExposure.map((row) => <article className="source-check-row" key={`${value(row, "client_code")}-${value(row, "symbol")}`}><div><strong>{value(row, "symbol")} · {value(row, "client_name")}</strong><p>LT {amount(row.long_term_exposure)} · Quant {amount(row.quant_exposure)} · Trading {amount(row.active_trading_exposure)}</p></div><StatusPill status={value(row, "overall_bias", "flat")} /><span>{amount(row.net_exposure)}</span><time>{value(row, "book_count", "0")} books</time></article>)}{!symbolExposure.length ? <Empty>No active symbol exposure for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<AlertTriangle size={17} />} title="Cross-Book Coordination" action={<span>{conflicts.length} conflicts</span>}><div className="source-check-list scoped-scroll-list">{conflicts.map((row) => <article className="source-check-row" key={value(row, "synthetic_id")}><div><strong>{value(row, "symbol")} · {value(row, "client_name")}</strong><p>{value(row, "description")}</p></div><StatusPill status={value(row, "severity", "review")} /><span>{amount(row.net_exposure)}</span><time>{value(row, "offset_ratio", "0")}% offset</time></article>)}{!conflicts.length ? <Empty>No cross-book conflict rows for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<DatabaseZap size={17} />} title="Position Objects" action={<span>{bookPositions.length} rows</span>}><div className="source-check-list scoped-scroll-list">{bookPositions.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "client_name")}</strong><p>{value(row, "book_name")} · {value(row, "purpose_name")} · {value(row, "time_horizon")}</p></div><StatusPill status={value(row, "status", "active")} /><span>{amount(row.net_exposure)}</span><time>{date(row.as_of)}</time></article>)}{!bookPositions.length ? <Empty>No position objects for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<ClipboardPlus size={17} />} title="Readiness Gaps" action={<button className="mini-action-button" disabled={remediationBusy} onClick={() => void runRemediation()} type="button">{remediationBusy ? "Syncing" : "Sync queue"}</button>}><div className="source-check-list scoped-scroll-list">{snapshot?.position_gap_summary.map((row) => <article className="source-check-row" key={value(row, "gap_type")}><div><strong>{value(row, "gap_type").replace(/_/g, " ")}</strong><p>{value(row, "owner_agent")} · average completeness {value(row, "avg_completeness_score")}</p></div><StatusPill status={value(row, "severity", "review")} /><span>{value(row, "position_count", "0")}</span><time>{value(row, "client_count", "0")} clients</time></article>)}</div></Panel>
        </section>
      ) : (
        <section className="dashboard-grid">
          <Panel className="span-5" icon={<Users size={17} />} title="Client Registry" action={<span>{clients.length} clients</span>}><div className="client-registry-list scoped-scroll-list">{clients.map((client) => <button className={selectedClient === value(client, "client_code") ? "client-registry-row selected" : "client-registry-row"} key={value(client, "client_code")} onClick={() => chooseClient(value(client, "client_code"))} type="button"><div><strong>{value(client, "display_name")}</strong><p>{value(client, "client_code")} · {value(client, "risk_profile")} risk</p></div><span>{amount(client.latest_market_value)}</span><small>{value(client, "latest_position_count", "0")} positions</small></button>)}</div></Panel>
          <Panel className="span-7" icon={<BriefcaseBusiness size={17} />} title="Current Holdings" action={<span>{positions.length} rows</span>}><div className="source-check-list scoped-scroll-list">{positions.map((row) => <article className="source-check-row" key={`${value(row, "account_code")}-${value(row, "symbol")}`}><div><strong>{value(row, "symbol")} · {value(row, "display_name")}</strong><p>{value(row, "account_code")} · qty {value(row, "quantity")} · avg {amount(row.average_price)}</p></div><StatusPill status={Number(row.unrealized_pnl ?? 0) >= 0 ? "active" : "review"} /><span>{amount(row.market_value)}</span><time>{date(row.as_of)}</time></article>)}{!positions.length ? <Empty>No current holdings for this client scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<ClipboardPlus size={17} />} title="Stage Holding Update"><form className="holding-stage-form" onSubmit={submitHolding}><label><span>Account</span><select required value={holding.accountCode} onChange={(event) => setHolding((current) => ({ ...current, accountCode: event.target.value }))}><option value="">Select account</option>{accounts.map((account) => <option key={value(account, "account_code")} value={value(account, "account_code")}>{value(account, "account_code")} · {value(account, "broker")}</option>)}</select></label><label><span>Symbol</span><input required value={holding.symbol} onChange={(event) => setHolding((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))} /></label><label><span>Quantity</span><input inputMode="decimal" required value={holding.quantity} onChange={(event) => setHolding((current) => ({ ...current, quantity: event.target.value }))} /></label><label><span>Average price</span><input inputMode="decimal" value={holding.averagePrice} onChange={(event) => setHolding((current) => ({ ...current, averagePrice: event.target.value }))} /></label><label><span>Market price</span><input inputMode="decimal" value={holding.marketPrice} onChange={(event) => setHolding((current) => ({ ...current, marketPrice: event.target.value }))} /></label><label className="span-form"><span>Reason</span><input required value={holding.reason} onChange={(event) => setHolding((current) => ({ ...current, reason: event.target.value }))} /></label><button className="primary-button span-form" disabled={stageBusy || selectedClient === "all"} type="submit"><ClipboardPlus size={15} />{stageBusy ? "Staging" : "Stage for review"}</button><p className="form-guard span-form">This creates an approval item. It does not change live positions or place an order.</p></form></Panel>
          <Panel className="span-7" icon={<ShieldCheck size={17} />} title="Holding Update Queue" action={<span>{pendingUpdates.length} open</span>}><div className="source-check-list scoped-scroll-list">{manualUpdates.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "client_code")}</strong><p>{value(row, "account_code")} · qty {value(row, "quantity")} · {value(row, "update_reason")}</p></div><StatusPill status={value(row, "status", "staged")} /><span>{amount(row.effective_market_value)}</span><time>{date(row.created_at)}</time></article>)}{!manualUpdates.length ? <Empty>No staged holding updates for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<BookOpenCheck size={17} />} title="Client Book Attribution"><div className="source-check-list scoped-scroll-list">{clientExposure.map((row) => <article className="source-check-row" key={`${value(row, "client_code")}-${value(row, "book_key")}`}><div><strong>{value(row, "book_name")} · {value(row, "client_name")}</strong><p>{value(row, "symbol_count", "0")} symbols · gross long {amount(row.gross_long)} · gross short {amount(row.gross_short)}</p></div><StatusPill status={value(row, "book_bias", "flat")} /><span>{amount(row.net_exposure)}</span><time>{value(row, "position_count", "0")} positions</time></article>)}{!clientExposure.length ? <Empty>No client book-attribution rows.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<DatabaseZap size={17} />} title="P2Cursor Reconciliation"><div className="source-check-list scoped-scroll-list">{reconciliations.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "client_name")} · {value(row, "client_code")}</strong><p>{value(row, "p2_position_count", "0")} source vs {value(row, "comparison_position_count", "0")} warehouse positions</p></div><StatusPill status={value(row, "status", "review")} /><span>{value(row, "matched_symbols", "0")} matched</span><time>{date(row.run_ts)}</time></article>)}{!reconciliations.length ? <Empty>No P2Cursor reconciliation run for this scope.</Empty> : null}</div></Panel>
        </section>
      )}
    </div>
  );
}
