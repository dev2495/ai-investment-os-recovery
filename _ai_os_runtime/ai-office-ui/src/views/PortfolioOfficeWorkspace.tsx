import {
  AlertTriangle,
  BookOpenCheck,
  BriefcaseBusiness,
  ClipboardPlus,
  DatabaseZap,
  FileCheck2,
  GitCompareArrows,
  Landmark,
  LineChart,
  RefreshCw,
  ShieldCheck,
  UserPlus,
  WalletCards,
  Users
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  resolveClientOnboarding,
  resolveAccountChange,
  resolveHoldingUpdate,
  stageAccountChange,
  stageClientOnboarding,
  stageHoldingUpdate,
  syncPositionReadinessRemediation,
  type LiveRow
} from "../api/live";
import {
  fetchPortfolioOfficeSnapshot,
  resolveClientCashEntry,
  resolveClientReportDelivery,
  runClientAccounting,
  stageClientCashEntry,
  type PortfolioOfficeSnapshot
} from "../api/portfolioOffice";
import WorkspaceFreshness from "../components/WorkspaceFreshness";

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
  const [onboardingBusy, setOnboardingBusy] = useState(false);
  const [decisionBusy, setDecisionBusy] = useState("");
  const [accountBusy, setAccountBusy] = useState(false);
  const [remediationBusy, setRemediationBusy] = useState(false);
  const [accountingBusy, setAccountingBusy] = useState(false);
  const [cashBusy, setCashBusy] = useState(false);
  const [holding, setHolding] = useState({ accountCode: "", symbol: "", quantity: "", averagePrice: "", marketPrice: "", reason: "manual portfolio update" });
  const [onboarding, setOnboarding] = useState({ clientCode: "", displayName: "", riskProfile: "moderate", objective: "long-term capital compounding", horizon: "5-10 years", liquidityNeeds: "", riskTolerance: "moderate", riskCapacity: "moderate", suitabilityStatus: "suitable", accountCode: "", broker: "", evidence: "client intake confirmed by Devarsh" });
  const [accountChange, setAccountChange] = useState({ accountCode: "", changeType: "update", broker: "", accountName: "", reason: "client account details updated by Devarsh", evidence: "manual client instruction" });
  const [cashEntry, setCashEntry] = useState({ accountCode: "", entryType: "opening_balance", amount: "", description: "opening cash balance from client statement", sourceRef: "", evidence: "client statement reviewed by Devarsh" });

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
  const genericReconciliations = (snapshot?.holding_reconciliation ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const onboardingCases = snapshot?.client_onboarding ?? [];
  const suitability = (snapshot?.client_suitability ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const accountChanges = (snapshot?.account_changes ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const cashLedger = (snapshot?.cash_ledger ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const taxLots = (snapshot?.tax_lot_summary ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const navRows = (snapshot?.client_nav ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const performance = (snapshot?.client_performance ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const attribution = (snapshot?.performance_attribution ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const reportDelivery = (snapshot?.client_report_delivery ?? []).filter((row) => selectedClient === "all" || value(row, "client_code") === selectedClient);
  const totalValue = useMemo(() => positions.reduce((sum, row) => sum + Number(row.market_value ?? 0), 0), [positions]);
  const grossExposure = useMemo(() => symbolExposure.reduce((sum, row) => sum + Number(row.gross_exposure ?? 0), 0), [symbolExposure]);
  const netExposure = useMemo(() => symbolExposure.reduce((sum, row) => sum + Number(row.net_exposure ?? 0), 0), [symbolExposure]);
  const pendingUpdates = manualUpdates.filter((row) => !["applied", "rejected"].includes(value(row, "status", "").toLowerCase()));
  const execution = snapshot?.execution_control[0];

  const chooseClient = (clientCode: string) => {
    setSelectedClient(clientCode);
    const firstAccount = snapshot?.client_accounts.find((row) => value(row, "client_code") === clientCode);
    setHolding((current) => ({ ...current, accountCode: firstAccount ? value(firstAccount, "account_code", "") : "" }));
    setCashEntry((current) => ({ ...current, accountCode: firstAccount ? value(firstAccount, "account_code", "") : "" }));
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

  const submitOnboarding = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setOnboardingBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await stageClientOnboarding({
        actor: "Devarsh",
        client_code: onboarding.clientCode,
        display_name: onboarding.displayName,
        risk_profile: onboarding.riskProfile,
        objectives: [onboarding.objective],
        investment_horizon: onboarding.horizon,
        liquidity_needs: onboarding.liquidityNeeds,
        risk_tolerance: onboarding.riskTolerance,
        risk_capacity: onboarding.riskCapacity,
        suitability_status: onboarding.suitabilityStatus as "suitable" | "conditionally_suitable" | "needs_review" | "unsuitable",
        suitability_notes: "Initial suitability entered in Client Office and pending Charlie review.",
        tax_residency: "India",
        source_evidence: [{ source: "manual_client_intake", note: onboarding.evidence, actor: "Devarsh" }],
        account: onboarding.accountCode ? { account_code: onboarding.accountCode, account_name: `${onboarding.displayName} Account`, account_type: "investment", broker: onboarding.broker, base_currency: "INR" } : undefined
      });
      setNotice(`Onboarding case #${value(result, "id")} staged for Charlie approval; no client or account was activated.`);
      setOnboarding((current) => ({ ...current, clientCode: "", displayName: "", accountCode: "", broker: "" }));
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Client onboarding could not be staged");
    } finally {
      setOnboardingBusy(false);
    }
  };

  const decideOnboarding = async (caseId: string, decision: "approved" | "rejected") => {
    setDecisionBusy(`onboarding-${caseId}`);
    setError("");
    try {
      await resolveClientOnboarding({ case_id: caseId, decision, decided_by: "Devarsh", decision_notes: decision === "approved" ? "Suitability, identity mapping, account scope, and evidence reviewed in Client Office." : "Rejected by Devarsh during Client Office review." });
      setNotice(`Onboarding case #${caseId} ${decision}.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Onboarding decision failed");
    } finally {
      setDecisionBusy("");
    }
  };

  const decideHolding = async (updateId: string, decision: "approved" | "rejected") => {
    setDecisionBusy(`holding-${updateId}`);
    setError("");
    try {
      await resolveHoldingUpdate({ update_id: updateId, decision, decided_by: "Devarsh", decision_notes: decision === "approved" ? "Source row and account ownership reviewed in Client Office." : "Rejected by Devarsh during Client Office review.", evidence: decision === "approved" ? [{ table: "portfolio.manual_holding_updates", id: updateId, reviewed_in: "Client Office" }] : [] });
      setNotice(`Holding update #${updateId} ${decision}.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Holding decision failed");
    } finally {
      setDecisionBusy("");
    }
  };

  const submitAccountChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedClient === "all") return setError("Select one client before requesting an account change.");
    setAccountBusy(true);
    setError("");
    try {
      const result = await stageAccountChange({ actor: "Devarsh", client_code: selectedClient, account_code: accountChange.accountCode, change_type: accountChange.changeType as "create" | "update" | "deactivate" | "reactivate", requested_values: { account_name: accountChange.accountName || undefined, broker: accountChange.broker || undefined }, reason: accountChange.reason, source_evidence: [{ source: "manual_client_instruction", note: accountChange.evidence, actor: "Devarsh" }] });
      setNotice(`Account change #${value(result, "id")} staged for approval; the account is unchanged.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Account change could not be staged");
    } finally {
      setAccountBusy(false);
    }
  };

  const decideAccountChange = async (requestId: string, decision: "approved" | "rejected") => {
    setDecisionBusy(`account-${requestId}`);
    setError("");
    try {
      await resolveAccountChange({ request_id: requestId, decision, decided_by: "Devarsh", decision_notes: decision === "approved" ? "Account ownership, broker mapping, requested values, and evidence reviewed in Client Office." : "Rejected by Devarsh during Client Office review." });
      setNotice(`Account change #${requestId} ${decision}.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Account decision failed");
    } finally {
      setDecisionBusy("");
    }
  };

  const submitCashEntry = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedClient === "all") return setError("Select one client before staging a cash entry.");
    setCashBusy(true); setError(""); setNotice("");
    try {
      const result = await stageClientCashEntry({ actor: "Devarsh", client_code: selectedClient, account_code: cashEntry.accountCode, entry_type: cashEntry.entryType, amount: cashEntry.amount, description: cashEntry.description, source_ref: cashEntry.sourceRef || undefined, source_evidence: [{ source: "manual_client_accounting", note: cashEntry.evidence, actor: "Devarsh" }] });
      setNotice(`Cash entry #${value(result, "id")} staged; NAV remains unchanged until approval.`);
      setCashEntry((current) => ({ ...current, amount: "", sourceRef: "" }));
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Cash entry could not be staged"); }
    finally { setCashBusy(false); }
  };

  const decideCashEntry = async (entryId: string, decision: "approved" | "rejected") => {
    setDecisionBusy(`cash-${entryId}`); setError("");
    try {
      await resolveClientCashEntry({ entry_id: entryId, decision, actor: "Devarsh", decision_notes: decision === "approved" ? "Cash source, amount, account, and classification reviewed in Client Office." : "Cash entry rejected during Client Office review." });
      setNotice(`Cash entry #${entryId} ${decision}. Recalculate accounting to refresh NAV.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Cash-entry decision failed"); }
    finally { setDecisionBusy(""); }
  };

  const recalculateAccounting = async () => {
    setAccountingBusy(true); setError(""); setNotice("");
    try {
      await runClientAccounting({ actor: "Performance Attribution Agent", account_code: selectedClient === "all" ? undefined : cashEntry.accountCode || undefined });
      setNotice("FIFO lots, NAV evidence, benchmark links, performance, and attribution recalculated from warehouse facts.");
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Client accounting recalculation failed"); }
    finally { setAccountingBusy(false); }
  };

  const decideReportDelivery = async (queueId: string, decision: "approved" | "rejected") => {
    setDecisionBusy(`report-${queueId}`); setError("");
    try {
      await resolveClientReportDelivery({ queue_id: queueId, decision, actor: "Devarsh", decision_notes: decision === "approved" ? "Draft, evidence gaps, and client scope reviewed. Manual delivery may proceed." : "Client report draft rejected for revision." });
      setNotice(`Client report queue #${queueId} ${decision}; no external send was executed.`);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Client report decision failed"); }
    finally { setDecisionBusy(""); }
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

      <WorkspaceFreshness generatedAt={snapshot?.generated_at} status={status} />
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
          <Panel className="span-7" icon={<UserPlus size={17} />} title="Governed Client Onboarding" action={<span>Charlie approval</span>}><form className="holding-stage-form" onSubmit={submitOnboarding}><label><span>Client code</span><input required value={onboarding.clientCode} onChange={(event) => setOnboarding((current) => ({ ...current, clientCode: event.target.value }))} /></label><label><span>Display name</span><input required value={onboarding.displayName} onChange={(event) => setOnboarding((current) => ({ ...current, displayName: event.target.value }))} /></label><label><span>Risk profile</span><select value={onboarding.riskProfile} onChange={(event) => setOnboarding((current) => ({ ...current, riskProfile: event.target.value }))}><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></select></label><label><span>Suitability</span><select value={onboarding.suitabilityStatus} onChange={(event) => setOnboarding((current) => ({ ...current, suitabilityStatus: event.target.value }))}><option value="suitable">Suitable</option><option value="conditionally_suitable">Conditionally suitable</option><option value="needs_review">Needs review</option><option value="unsuitable">Unsuitable</option></select></label><label className="span-form"><span>Primary objective</span><input required value={onboarding.objective} onChange={(event) => setOnboarding((current) => ({ ...current, objective: event.target.value }))} /></label><label><span>Investment horizon</span><input required value={onboarding.horizon} onChange={(event) => setOnboarding((current) => ({ ...current, horizon: event.target.value }))} /></label><label><span>Liquidity needs</span><input value={onboarding.liquidityNeeds} onChange={(event) => setOnboarding((current) => ({ ...current, liquidityNeeds: event.target.value }))} /></label><label><span>Risk tolerance</span><input required value={onboarding.riskTolerance} onChange={(event) => setOnboarding((current) => ({ ...current, riskTolerance: event.target.value }))} /></label><label><span>Risk capacity</span><input required value={onboarding.riskCapacity} onChange={(event) => setOnboarding((current) => ({ ...current, riskCapacity: event.target.value }))} /></label><label><span>First account code</span><input value={onboarding.accountCode} onChange={(event) => setOnboarding((current) => ({ ...current, accountCode: event.target.value }))} /></label><label><span>Broker</span><input value={onboarding.broker} onChange={(event) => setOnboarding((current) => ({ ...current, broker: event.target.value }))} /></label><label className="span-form"><span>Source evidence</span><input required value={onboarding.evidence} onChange={(event) => setOnboarding((current) => ({ ...current, evidence: event.target.value }))} /></label><button className="primary-button span-form" disabled={onboardingBusy} type="submit"><UserPlus size={15} />{onboardingBusy ? "Staging" : "Stage onboarding"}</button><p className="form-guard span-form">Creates a suitability review and human approval. Client and account rows remain inactive until the dedicated approval action succeeds.</p></form></Panel>
          <Panel className="span-5" icon={<ShieldCheck size={17} />} title="Onboarding Approval Queue" action={<span>{onboardingCases.filter((row) => value(row, "status") === "pending_approval").length} pending</span>}><div className="source-check-list scoped-scroll-list">{onboardingCases.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "display_name")} · {value(row, "client_code")}</strong><p>{value(row, "risk_profile")} risk · {value(row, "investment_horizon")} · {value(row, "suitability_status")}</p>{value(row, "status") === "pending_approval" ? <div className="inline-decision-actions"><button disabled={decisionBusy === `onboarding-${value(row, "id")}`} onClick={() => void decideOnboarding(value(row, "id"), "approved")} type="button">Approve</button><button disabled={decisionBusy === `onboarding-${value(row, "id")}`} onClick={() => void decideOnboarding(value(row, "id"), "rejected")} type="button">Reject</button></div> : null}</div><StatusPill status={value(row, "status")} /><span>#{value(row, "approval_id")}</span><time>{date(row.created_at)}</time></article>)}{!onboardingCases.length ? <Empty>No onboarding cases. Existing clients were imported, not seeded through this queue.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<Users size={17} />} title="Client Registry" action={<span>{clients.length} clients</span>}><div className="client-registry-list scoped-scroll-list">{clients.map((client) => <button className={selectedClient === value(client, "client_code") ? "client-registry-row selected" : "client-registry-row"} key={value(client, "client_code")} onClick={() => chooseClient(value(client, "client_code"))} type="button"><div><strong>{value(client, "display_name")}</strong><p>{value(client, "client_code")} · {value(client, "risk_profile")} risk</p></div><span>{amount(client.latest_market_value)}</span><small>{value(client, "latest_position_count", "0")} positions</small></button>)}</div></Panel>
          <Panel className="span-7" icon={<BookOpenCheck size={17} />} title="Suitability & Mandate Control" action={<span>{suitability.filter((row) => value(row, "review_health") !== "current").length} gaps</span>}><div className="source-check-list scoped-scroll-list">{suitability.map((row) => <article className="source-check-row" key={value(row, "client_code")}><div><strong>{value(row, "display_name")} · {value(row, "client_code")}</strong><p>{value(row, "risk_tolerance")} tolerance · {value(row, "risk_capacity")} capacity · {value(row, "investment_horizon")}</p></div><StatusPill status={value(row, "review_health")} /><span>{value(row, "suitability_status")}</span><time>{date(row.next_review_due_at)}</time></article>)}{!suitability.length ? <Empty>No suitability rows for this client scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<BriefcaseBusiness size={17} />} title="Current Holdings" action={<span>{positions.length} rows</span>}><div className="source-check-list scoped-scroll-list">{positions.map((row) => <article className="source-check-row" key={`${value(row, "account_code")}-${value(row, "symbol")}`}><div><strong>{value(row, "symbol")} · {value(row, "display_name")}</strong><p>{value(row, "account_code")} · qty {value(row, "quantity")} · avg {amount(row.average_price)}</p></div><StatusPill status={Number(row.unrealized_pnl ?? 0) >= 0 ? "active" : "review"} /><span>{amount(row.market_value)}</span><time>{date(row.as_of)}</time></article>)}{!positions.length ? <Empty>No current holdings for this client scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<Landmark size={17} />} title="NAV & Cash Evidence" action={<button className="mini-action-button" disabled={accountingBusy} onClick={() => void recalculateAccounting()} type="button"><RefreshCw size={14} />{accountingBusy ? "Calculating" : "Recalculate"}</button>}><div className="source-check-list scoped-scroll-list">{navRows.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "display_name")} · {value(row, "account_code")}</strong><p>Securities {amount(row.securities_market_value)} · cash {amount(row.cash_balance)} · {value(row, "missing_inputs", "evidence complete")}</p></div><StatusPill status={value(row, "calculation_status")} /><span>{row.nav == null ? "NAV unavailable" : amount(row.nav)}</span><time>{value(row, "nav_date")}</time></article>)}{!navRows.length ? <Empty>No NAV evidence for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<LineChart size={17} />} title="Performance & Benchmark" action={<span>{performance.length} periods</span>}><div className="source-check-list scoped-scroll-list">{performance.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "display_name")} · {value(row, "period_type")}</strong><p>{value(row, "period_start")} to {value(row, "period_end")} · benchmark {value(row, "benchmark_key")} {value(row, "benchmark_return_pct", "unavailable")}% · {value(row, "missing_inputs", "evidence complete")}</p></div><StatusPill status={value(row, "calculation_status")} /><span>{row.twr_return_pct == null ? "Return unavailable" : `${Number(row.twr_return_pct).toFixed(2)}%`}</span><time>{amount(row.realized_pnl)} realized</time></article>)}{!performance.length ? <Empty>No performance period has been calculated.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<DatabaseZap size={17} />} title="FIFO Tax-Lot Control" action={<span>{taxLots.reduce((sum, row) => sum + Number(row.position_break_count ?? 0), 0)} breaks</span>}><div className="source-check-list scoped-scroll-list">{taxLots.map((row) => <article className="source-check-row" key={value(row, "run_id")}><div><strong>{value(row, "account_code")} · {value(row, "method")}</strong><p>{value(row, "trade_count")} trades · {value(row, "match_count")} closes · {value(row, "open_lot_count")} open lots · {value(row, "missing_inputs", "covered")}</p></div><StatusPill status={value(row, "status")} /><span>{amount(row.realized_pnl)}</span><time>{value(row, "position_break_count", "0")} position breaks</time></article>)}{!taxLots.length ? <Empty>No tax-lot calculation has been run.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<LineChart size={17} />} title="Realized Attribution" action={<span>{attribution.length} contributors</span>}><div className="source-check-list scoped-scroll-list">{attribution.map((row) => <article className="source-check-row" key={`${value(row, "id")}-${value(row, "attribution_key")}`}><div><strong>{value(row, "attribution_key")} · {value(row, "display_name")}</strong><p>{value(row, "attribution_type")} · {value(row, "period_start")} to {value(row, "period_end")}</p></div><StatusPill status={value(row, "calculation_status")} /><span>{amount(row.contribution_amount)}</span><time>{value(row, "contribution_pct", "-")}%</time></article>)}{!attribution.length ? <Empty>No attributable realized activity for this scope and period.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<WalletCards size={17} />} title="Stage Cash Evidence"><form className="holding-stage-form" onSubmit={submitCashEntry}><label><span>Account</span><select required value={cashEntry.accountCode} onChange={(event) => setCashEntry((current) => ({ ...current, accountCode: event.target.value }))}><option value="">Select account</option>{accounts.map((account) => <option key={value(account, "account_code")} value={value(account, "account_code")}>{value(account, "account_code")}</option>)}</select></label><label><span>Entry type</span><select value={cashEntry.entryType} onChange={(event) => setCashEntry((current) => ({ ...current, entryType: event.target.value }))}><option value="opening_balance">Opening balance</option><option value="contribution">Contribution</option><option value="withdrawal">Withdrawal</option><option value="dividend">Dividend</option><option value="interest">Interest</option><option value="fee">Fee</option><option value="tax">Tax</option><option value="cash_adjustment">Cash adjustment</option><option value="transfer">Transfer</option></select></label><label><span>Amount</span><input inputMode="decimal" required value={cashEntry.amount} onChange={(event) => setCashEntry((current) => ({ ...current, amount: event.target.value }))} /></label><label><span>Source reference</span><input value={cashEntry.sourceRef} onChange={(event) => setCashEntry((current) => ({ ...current, sourceRef: event.target.value }))} /></label><label className="span-form"><span>Description</span><input required value={cashEntry.description} onChange={(event) => setCashEntry((current) => ({ ...current, description: event.target.value }))} /></label><label className="span-form"><span>Evidence</span><input required value={cashEntry.evidence} onChange={(event) => setCashEntry((current) => ({ ...current, evidence: event.target.value }))} /></label><button className="primary-button span-form" disabled={cashBusy || selectedClient === "all"} type="submit"><WalletCards size={15} />{cashBusy ? "Staging" : "Stage cash entry"}</button><p className="form-guard span-form">Cash and NAV remain unchanged until this source-backed entry is approved.</p></form></Panel>
          <Panel className="span-7" icon={<ShieldCheck size={17} />} title="Cash Approval Queue" action={<span>{cashLedger.filter((row) => value(row, "status") === "pending_approval").length} pending</span>}><div className="source-check-list scoped-scroll-list">{cashLedger.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "entry_type")} · {value(row, "display_name")}</strong><p>{value(row, "account_code")} · {value(row, "description")} · {value(row, "source_ref", "embedded evidence")}</p>{value(row, "status") === "pending_approval" ? <div className="inline-decision-actions"><button disabled={decisionBusy === `cash-${value(row, "id")}`} onClick={() => void decideCashEntry(value(row, "id"), "approved")} type="button">Post</button><button disabled={decisionBusy === `cash-${value(row, "id")}`} onClick={() => void decideCashEntry(value(row, "id"), "rejected")} type="button">Reject</button></div> : null}</div><StatusPill status={value(row, "status")} /><span>{amount(row.amount)}</span><time>{date(row.entry_ts)}</time></article>)}{!cashLedger.length ? <Empty>No cash ledger entries for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<FileCheck2 size={17} />} title="Client Report Delivery" action={<span>{reportDelivery.filter((row) => value(row, "status") === "pending_approval").length} pending</span>}><div className="source-check-list scoped-scroll-list">{reportDelivery.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "display_name")} · {value(row, "report_period")}</strong><p>{value(row, "output_note_path")} · manual delivery only</p>{value(row, "status") === "pending_approval" ? <div className="inline-decision-actions"><button disabled={decisionBusy === `report-${value(row, "id")}`} onClick={() => void decideReportDelivery(value(row, "id"), "approved")} type="button">Approve</button><button disabled={decisionBusy === `report-${value(row, "id")}`} onClick={() => void decideReportDelivery(value(row, "id"), "rejected")} type="button">Reject</button></div> : null}</div><StatusPill status={value(row, "status")} /><span>#{value(row, "approval_id")}</span><time>{date(row.created_at)}</time></article>)}{!reportDelivery.length ? <Empty>No client report delivery queue has been generated.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<ClipboardPlus size={17} />} title="Stage Holding Update"><form className="holding-stage-form" onSubmit={submitHolding}><label><span>Account</span><select required value={holding.accountCode} onChange={(event) => setHolding((current) => ({ ...current, accountCode: event.target.value }))}><option value="">Select account</option>{accounts.map((account) => <option key={value(account, "account_code")} value={value(account, "account_code")}>{value(account, "account_code")} · {value(account, "broker")}</option>)}</select></label><label><span>Symbol</span><input required value={holding.symbol} onChange={(event) => setHolding((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))} /></label><label><span>Quantity</span><input inputMode="decimal" required value={holding.quantity} onChange={(event) => setHolding((current) => ({ ...current, quantity: event.target.value }))} /></label><label><span>Average price</span><input inputMode="decimal" value={holding.averagePrice} onChange={(event) => setHolding((current) => ({ ...current, averagePrice: event.target.value }))} /></label><label><span>Market price</span><input inputMode="decimal" value={holding.marketPrice} onChange={(event) => setHolding((current) => ({ ...current, marketPrice: event.target.value }))} /></label><label className="span-form"><span>Reason</span><input required value={holding.reason} onChange={(event) => setHolding((current) => ({ ...current, reason: event.target.value }))} /></label><button className="primary-button span-form" disabled={stageBusy || selectedClient === "all"} type="submit"><ClipboardPlus size={15} />{stageBusy ? "Staging" : "Stage for review"}</button><p className="form-guard span-form">This creates an approval item. It does not change live positions or place an order.</p></form></Panel>
          <Panel className="span-7" icon={<ShieldCheck size={17} />} title="Holding Update Queue" action={<span>{pendingUpdates.length} open</span>}><div className="source-check-list scoped-scroll-list">{manualUpdates.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "symbol")} · {value(row, "client_code")}</strong><p>{value(row, "account_code")} · qty {value(row, "quantity")} · {value(row, "update_reason")}</p>{value(row, "status") === "pending_approval" ? <div className="inline-decision-actions"><button disabled={decisionBusy === `holding-${value(row, "id")}`} onClick={() => void decideHolding(value(row, "id"), "approved")} type="button">Apply</button><button disabled={decisionBusy === `holding-${value(row, "id")}`} onClick={() => void decideHolding(value(row, "id"), "rejected")} type="button">Reject</button></div> : null}</div><StatusPill status={value(row, "status", "pending_approval")} /><span>{amount(row.effective_market_value)}</span><time>{date(row.created_at)}</time></article>)}{!manualUpdates.length ? <Empty>No holding updates for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<BriefcaseBusiness size={17} />} title="Account Maintenance"><form className="holding-stage-form" onSubmit={submitAccountChange}><label><span>Account code</span><input list="client-account-codes" required value={accountChange.accountCode} onChange={(event) => setAccountChange((current) => ({ ...current, accountCode: event.target.value }))} /><datalist id="client-account-codes">{accounts.map((row) => <option key={value(row, "account_code")} value={value(row, "account_code")} />)}</datalist></label><label><span>Change</span><select value={accountChange.changeType} onChange={(event) => setAccountChange((current) => ({ ...current, changeType: event.target.value }))}><option value="update">Update</option><option value="create">Create</option><option value="deactivate">Deactivate</option><option value="reactivate">Reactivate</option></select></label><label><span>Account name</span><input value={accountChange.accountName} onChange={(event) => setAccountChange((current) => ({ ...current, accountName: event.target.value }))} /></label><label><span>Broker</span><input value={accountChange.broker} onChange={(event) => setAccountChange((current) => ({ ...current, broker: event.target.value }))} /></label><label className="span-form"><span>Reason</span><input required value={accountChange.reason} onChange={(event) => setAccountChange((current) => ({ ...current, reason: event.target.value }))} /></label><label className="span-form"><span>Source evidence</span><input required value={accountChange.evidence} onChange={(event) => setAccountChange((current) => ({ ...current, evidence: event.target.value }))} /></label><button className="primary-button span-form" disabled={accountBusy || selectedClient === "all"} type="submit">{accountBusy ? "Staging" : "Stage account change"}</button><p className="form-guard span-form">Account creation, edits, and lifecycle changes are approval-gated and never write to a broker.</p></form></Panel>
          <Panel className="span-7" icon={<ShieldCheck size={17} />} title="Account Change Queue" action={<span>{accountChanges.filter((row) => value(row, "status") === "pending_approval").length} pending</span>}><div className="source-check-list scoped-scroll-list">{accountChanges.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "change_type")} · {value(row, "client_code")}</strong><p>{value(row, "reason")}</p>{value(row, "status") === "pending_approval" ? <div className="inline-decision-actions"><button disabled={decisionBusy === `account-${value(row, "id")}`} onClick={() => void decideAccountChange(value(row, "id"), "approved")} type="button">Approve</button><button disabled={decisionBusy === `account-${value(row, "id")}`} onClick={() => void decideAccountChange(value(row, "id"), "rejected")} type="button">Reject</button></div> : null}</div><StatusPill status={value(row, "status")} /><span>{value(row, "current_account_code", value(row, "requested_values"))}</span><time>{date(row.created_at)}</time></article>)}{!accountChanges.length ? <Empty>No account change requests for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<BookOpenCheck size={17} />} title="Client Book Attribution"><div className="source-check-list scoped-scroll-list">{clientExposure.map((row) => <article className="source-check-row" key={`${value(row, "client_code")}-${value(row, "book_key")}`}><div><strong>{value(row, "book_name")} · {value(row, "client_name")}</strong><p>{value(row, "symbol_count", "0")} symbols · gross long {amount(row.gross_long)} · gross short {amount(row.gross_short)}</p></div><StatusPill status={value(row, "book_bias", "flat")} /><span>{amount(row.net_exposure)}</span><time>{value(row, "position_count", "0")} positions</time></article>)}{!clientExposure.length ? <Empty>No client book-attribution rows.</Empty> : null}</div></Panel>
          <Panel className="span-5" icon={<DatabaseZap size={17} />} title="P2Cursor Reconciliation"><div className="source-check-list scoped-scroll-list">{reconciliations.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "client_name")} · {value(row, "client_code")}</strong><p>{value(row, "p2_position_count", "0")} source vs {value(row, "comparison_position_count", "0")} warehouse positions</p></div><StatusPill status={value(row, "status", "review")} /><span>{value(row, "matched_symbols", "0")} matched</span><time>{date(row.run_ts)}</time></article>)}{!reconciliations.length ? <Empty>No P2Cursor reconciliation run for this scope.</Empty> : null}</div></Panel>
          <Panel className="span-7" icon={<GitCompareArrows size={17} />} title="Multi-Source Reconciliation" action={<span>{genericReconciliations.reduce((sum, row) => sum + Number(row.break_count ?? 0), 0)} breaks</span>}><div className="source-check-list scoped-scroll-list">{genericReconciliations.map((row) => <article className="source-check-row" key={value(row, "id")}><div><strong>{value(row, "source_label")} · {value(row, "display_name")}</strong><p>{value(row, "source_position_count", "0")} source vs {value(row, "warehouse_position_count", "0")} warehouse · {value(row, "break_count", "0")} breaks</p></div><StatusPill status={value(row, "status")} /><span>{value(row, "matched_count", "0")} matched</span><time>{date(row.completed_at)}</time></article>)}{!genericReconciliations.length ? <Empty>No generic broker, algo, or manual-source reconciliation has been run yet.</Empty> : null}</div></Panel>
        </section>
      )}
    </div>
  );
}
