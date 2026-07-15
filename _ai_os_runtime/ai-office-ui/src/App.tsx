import {
  Activity,
  BarChart3,
  Bell,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronRight,
  CircleAlert,
  CircleDollarSign,
  ClipboardList,
  Clock3,
  Command as CommandIcon,
  DatabaseZap,
  Cpu,
  Crosshair,
  FileText,
  FlaskConical,
  Gauge,
  Globe2,
  GitBranch,
  Inbox,
  Landmark,
  LineChart,
  ListChecks,
  LockKeyhole,
  MessageSquareText,
  PanelLeft,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Scale,
  UsersRound,
  UserCheck,
  X
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  applyStrategyTemplate,
  calculateSpecialSituationSpread,
  checkStrategyDataQuality,
  createAgentMessage,
  createOrderIntent,
  createStrategyIntake,
  createTradingViewTask,
  createLongTermSourceRequests,
  dispatchLongTermSpecialists,
  extractLongTermSourceDocument,
  executeTradingViewChartAction,
  executeTradingViewTemplateAction,
  executeLongTermSpecialist,
  attachBrowserProfile,
  buildStrategyIdeaDossiers,
  checkSourceFreshness,
  checkBrowserProfile,
  checkLongTermSourceRequests,
  checkModelEndpoint,
  checkSourceConnector,
  createAgentComment,
  engageGlobalKillSwitch,
  enforceStrategyKillSwitch,
  evaluateProviderAssignmentGate,
  evaluateOrderIntentRisk,
  evaluateExecutionGate,
  evaluateStrategyDrift,
  fetchLiveSnapshot,
  fetchOfficeSnapshot,
  generateLongTermResearchPacket,
  generateLongTermCommitteeMemo,
  generateLongTermThesisMemo,
  generateSpecialSituationMemo,
  ingestMarketNews,
  generateStrategyCommitteeMemo,
  materializeDashboardWidgets,
  openStrategyCommitteeReview,
  openLongTermCommitteeReview,
  parseStrategyDsl,
  recordPaperMonitorHeartbeat,
  recordManualTrade,
  recordPaperTrade,
  refreshEventQuotes,
  refreshPortfolioRiskEvents,
  registerBrowserProfile,
  registerLongTermSourceDocument,
  registerModelEndpoint,
  registerSourceConnector,
  requestLimitedLiveApproval,
  resolveApproval,
  searchStrategyIdeaDossiers,
  resolveStrategyDiscoveryTriage,
  resolveAgentComment,
  resolveTradingViewAlertRequest,
  resolveSpecialSituationDecision,
  resolveStrategyCommitteeDecision,
  resolveLongTermCommitteeDecision,
  routeSymbolIntelligenceAction,
  runBrokerReconciliation,
  runLegacySourceReadiness,
  runModelValidationSweep,
  runP2CursorReconciliation,
  runAgentWorker,
  runStrategyDossierAction,
  runProviderReadinessSweep,
  runFilingCollector,
  runFilingPdfExtractor,
  runStrategyDiscovery,
  runStrategyDiscoveryScheduler,
  runStrategyBacktest,
  runStrategyOptimization,
  runStrategyPortfolioAllocation,
  runStrategyQuantAnalytics,
  runStrategyRetirementReview,
  runTradeJournalStrategyMining,
  runUserDefinedStrategyOptimizer,
  sendChat,
  stageBrokerTransactions,
  stageHoldingUpdate,
  startStrategyPaperMonitor,
  stopStrategyPaperMonitor,
  syncLimitedLiveRequest,
  syncLongTermCoverage,
  syncPositionReadinessRemediation,
  triageAgentMessage,
  updateInboxItem,
  updateBookAssignment
} from "./api/live";
import type {
  AgentStatus,
  ApprovalItem,
  BriefLine,
  ClientControlItem,
  ControlModule,
  DataSourceItem,
  FinceptBridgeItem,
  HealthCheck,
  InboxItem,
  ManualUpdateItem,
  Metric,
  PortfolioAlert,
  Severity,
  SignalItem,
  Status,
  StrategyRegistryItem,
  WorkflowItem,
  Workspace,
  WorkspaceId
} from "./types";
import type { LiveRow, LiveSnapshot, OfficeSnapshot } from "./api/live";
import { useLiveSnapshot } from "./app/useLiveSnapshot";
import { useWorkspaceRoute, type InterfaceMode } from "./app/useWorkspaceRoute";
import WorkspaceErrorBoundary from "./components/WorkspaceErrorBoundary";
import ScrollableRegionAccessibility from "./components/ScrollableRegionAccessibility";
import MissionControlWorkspace from "./views/MissionControlWorkspace";
import PortfolioOfficeWorkspace from "./views/PortfolioOfficeWorkspace";
import ResearchIdeasWorkspace from "./views/ResearchIdeasWorkspace";
import ReportsWorkspace from "./views/ReportsWorkspace";
import SystemHealthWorkspace from "./views/SystemHealthWorkspace";
import TradingQuantRiskWorkspace from "./views/TradingQuantRiskWorkspace";
import DepartmentTerminalWorkspace from "./views/DepartmentTerminalWorkspace";
import StrategyArsenalWorkspace from "./views/StrategyArsenalWorkspace";
import IntegrationGatewayWorkspace from "./views/IntegrationGatewayWorkspace";
import DepartmentDeskWorkspace from "./views/DepartmentDeskWorkspace";
import WorkspaceManager from "./components/WorkspaceManager";
import WorkspaceWidgetRail from "./components/WorkspaceWidgetRail";
import { fetchWorkspaceConfig, updateDashboardWidget, updateWorkspaceConfig, type TerminalWorkspace, type WorkspaceConfig } from "./api/terminal";

const LiveOffice = lazy(() => import("./office/LiveOffice"));

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
}

const baseWorkspaces: Workspace[] = [
  { id: "command", label: "Command Center" },
  { id: "approvals", label: "Approval Board" },
  { id: "agents", label: "Agent Office" },
  { id: "departments", label: "Department Desks" },
  { id: "committees", label: "Committee Rooms" },
  { id: "governance", label: "Governance & Safety" },
  { id: "portfolio", label: "Portfolio Office" },
  { id: "clients", label: "Client Folios" },
  { id: "tactical", label: "Tactical Office" },
  { id: "research", label: "Holdings Research" },
  { id: "ideas", label: "Idea Pipeline" },
  { id: "arsenal", label: "Strategy Arsenal" },
  { id: "trading", label: "Trading Desk" },
  { id: "quant", label: "Quant Lab" },
  { id: "risk", label: "Risk Center" },
  { id: "capital", label: "Capital Allocation" },
  { id: "treasury", label: "Treasury & Macro" },
  { id: "models", label: "Data & Model Gateway" },
  { id: "reports", label: "Reports" },
  { id: "system", label: "System Health" }
];

const workspaceIcons: Record<WorkspaceId, typeof CommandIcon> = {
  command: CommandIcon,
  approvals: ListChecks,
  agents: UsersRound,
  departments: BriefcaseBusiness,
  committees: Scale,
  governance: ShieldCheck,
  portfolio: BriefcaseBusiness,
  clients: Building2,
  tactical: Crosshair,
  research: Landmark,
  ideas: Sparkles,
  arsenal: GitBranch,
  trading: LineChart,
  quant: FlaskConical,
  risk: ShieldCheck,
  capital: CircleDollarSign,
  treasury: Globe2,
  models: Cpu,
  reports: FileText,
  system: DatabaseZap
};

const workspaceGroups: { label: string; workspaces: WorkspaceId[] }[] = [
  { label: "Executive", workspaces: ["command", "approvals", "agents", "departments", "committees", "governance"] },
  { label: "Investing", workspaces: ["portfolio", "clients", "tactical", "capital", "treasury"] },
  { label: "Research", workspaces: ["research", "ideas", "reports"] },
  { label: "Trading", workspaces: ["arsenal", "trading", "quant", "risk"] },
  { label: "System", workspaces: ["models", "system"] }
];

const statusLabel: Record<Status, string> = {
  queued: "Queued",
  running: "Running",
  needs_review: "Needs review",
  approved: "Approved",
  blocked: "Blocked",
  done: "Done"
};

const quickCommands = [
  "Review all client portfolios and flag action candidates.",
  "Check TradingView signals and explain which ones need attention.",
  "Open a thesis refresh for stale long-term holdings.",
  "Run a quant validation task for the ATR extension strategy."
];

const statusValues: Status[] = ["queued", "running", "needs_review", "approved", "blocked", "done"];
const severityValues: Severity[] = ["low", "medium", "high", "critical"];

function isoDateOffset(days: number): string {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function asText(row: LiveRow, key: string, fallback = ""): string {
  const value = row[key];
  if (value === null || value === undefined) {
    return fallback;
  }
  return String(value);
}

function asStringArray(row: LiveRow, key: string): string[] {
  const value = row[key];
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function asNumber(row: LiveRow, key: string, fallback = 0): number {
  const value = Number(row[key]);
  return Number.isFinite(value) ? value : fallback;
}

function asArray(row: LiveRow, key: string): string[] {
  const value = row[key];
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        if (record.table && record.id) {
          return `${String(record.table)} #${String(record.id)}`;
        }
        if (record.source) {
          return String(record.source);
        }
        if (record.url) {
          return String(record.url);
        }
        return JSON.stringify(record);
      }
      return String(item);
    });
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

function asRecordArray(row: LiveRow, key: string): LiveRow[] {
  const value = row[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is LiveRow => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asStatus(value: unknown, fallback: Status = "queued"): Status {
  const candidate = String(value ?? "");
  return statusValues.includes(candidate as Status) ? (candidate as Status) : fallback;
}

function asSeverity(value: unknown, fallback: Severity = "medium"): Severity {
  const candidate = String(value ?? "").toLowerCase();
  return severityValues.includes(candidate as Severity) ? (candidate as Severity) : fallback;
}

function statusForModule(value: unknown): ControlModule["status"] {
  const candidate = String(value ?? "");
  return candidate === "active" || candidate === "installed" || candidate === "mapped" || candidate === "planned"
    ? candidate
    : "mapped";
}

function statusForSource(value: unknown): DataSourceItem["status"] {
  const candidate = String(value ?? "");
  return candidate === "installed" || candidate === "imported" || candidate === "mapped" || candidate === "planned"
    ? candidate
    : "mapped";
}

function compactDate(value: unknown): string {
  if (!value) {
    return "waiting";
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  });
}

function compactNumber(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "0";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(numeric);
}

function compactInr(value: unknown): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "INR 0";
  }
  if (Math.abs(numeric) >= 10000000) {
    return `INR ${(numeric / 10000000).toFixed(2)} Cr`;
  }
  if (Math.abs(numeric) >= 100000) {
    return `INR ${(numeric / 100000).toFixed(2)} L`;
  }
  return `INR ${compactNumber(numeric)}`;
}

function metricValue(snapshot: LiveSnapshot | null, key: string, fallback = "0"): string {
  const found = snapshot?.metrics.find((metric) => asText(metric, "metric") === key);
  return found ? asText(found, "value", fallback) : fallback;
}

function portfolioSummaryValue(snapshot: LiveSnapshot | null, key: string, fallback = "0"): string {
  const found = snapshot?.portfolio_intelligence_summary.find((metric) => asText(metric, "metric") === key);
  return found ? asText(found, "value", fallback) : fallback;
}

function extractSymbols(text: string): string[] {
  const matches = text.toUpperCase().match(/\b[A-Z][A-Z0-9&.-]{1,14}\b/g) ?? [];
  const ignored = new Set(["CHECK", "TRADINGVIEW", "SIGNALS", "REVIEW", "OPEN", "CHART", "OPTIONS", "MAKE"]);
  return [...new Set(matches.filter((item) => !ignored.has(item)))].slice(0, 8);
}

function liveMetrics(snapshot: LiveSnapshot | null): Metric[] {
  if (!snapshot) {
    return [];
  }
  return [
    {
      label: "MCP Tools",
      value: metricValue(snapshot, "mcp_enabled_tools"),
      delta: `${metricValue(snapshot, "approved_mcp_candidates")} approved connectors`,
      tone: "good"
    },
    {
      label: "Research Hub",
      value: metricValue(snapshot, "research_hub_artifacts"),
      delta: "Codex/Claude outputs indexed",
      tone: "good"
    },
    {
      label: "TradingView Tasks",
      value: metricValue(snapshot, "tradingview_tasks"),
      delta: snapshot.tradingview_cdp.available ? "desktop MCP attachable" : "CDP port offline",
      tone: snapshot.tradingview_cdp.available ? "good" : "warn"
    },
    {
      label: "Trade Ledger",
      value: metricValue(snapshot, "trade_activity_rows"),
      delta: "manual + paper journal",
      tone: "neutral"
    },
    {
      label: "Book Positions",
      value: portfolioSummaryValue(snapshot, "book_positions"),
      delta: `${portfolioSummaryValue(snapshot, "investment_books")} books · ${portfolioSummaryValue(snapshot, "booked_clients")} clients`,
      tone: "good"
    }
  ];
}

function routeCommand(text: string): Pick<InboxItem, "agent" | "priority" | "recommendedAction"> {
  const normalized = text.toLowerCase();

  if (normalized.includes("quant") || normalized.includes("backtest") || normalized.includes("strategy")) {
    return {
      agent: "Strategy Intake Agent",
      priority: "medium",
      recommendedAction: "Run validation in paper/shadow mode and save results."
    };
  }

  if (normalized.includes("trade") || normalized.includes("signal") || normalized.includes("tradingview")) {
    return {
      agent: "Trading Desk",
      priority: "high",
      recommendedAction: "Classify setup, check risk, and keep execution gated."
    };
  }

  if (normalized.includes("client") || normalized.includes("portfolio") || normalized.includes("folio")) {
    return {
      agent: "Portfolio Manager",
      priority: "high",
      recommendedAction: "Compare holdings, risk, drift, and thesis state."
    };
  }

  if (normalized.includes("research") || normalized.includes("thesis") || normalized.includes("valuation")) {
    return {
      agent: "Research Analyst",
      priority: "medium",
      recommendedAction: "Create or update research note with evidence and assumptions."
    };
  }

  if (normalized.includes("risk") || normalized.includes("approval")) {
    return {
      agent: "Risk Agent",
      priority: "high",
      recommendedAction: "Challenge assumptions and check guardrails before approval."
    };
  }

  return {
    agent: "Jarvis",
    priority: "medium",
    recommendedAction: "Convert request into scoped tasks and route specialist agents."
  };
}

function liveControlModules(snapshot: LiveSnapshot | null): ControlModule[] {
  if (!snapshot?.modules.length) {
    return [];
  }
  return snapshot.modules.slice(0, 8).map((module) => ({
    key: asText(module, "module_key", asText(module, "module_name")),
    name: asText(module, "module_name", "Runtime module"),
    status: statusForModule(module.status),
    priority: asSeverity(module.priority, "medium"),
    owner: asText(module, "owner_agent", "Jarvis"),
    workspace: asText(module, "ui_workspace", "system"),
    nextAction: asText(module, "next_action", "Monitor")
  }));
}

function liveDataSources(snapshot: LiveSnapshot | null): DataSourceItem[] {
  if (!snapshot?.data_sources.length) {
    return [];
  }
  return snapshot.data_sources.slice(0, 10).map((source) => ({
    key: asText(source, "source_key", asText(source, "source_name")),
    name: asText(source, "source_name", "Data source"),
    type: asText(source, "source_type", "source"),
    provider: asText(source, "provider", "local"),
    status: statusForSource(source.status),
    cadence: asText(source, "freshness_target_minutes")
      ? `${asText(source, "freshness_target_minutes")} min`
      : asText(source, "connection_mode", "on demand"),
    owner: asText(source, "owner_agent", "Data Steward")
  }));
}

function liveStrategies(snapshot: LiveSnapshot | null): StrategyRegistryItem[] {
  if (!snapshot?.strategies.length) {
    return [];
  }
  return snapshot.strategies.slice(0, 8).map((strategy) => ({
    key: asText(strategy, "strategy_key", asText(strategy, "strategy_name")),
    name: asText(strategy, "strategy_name", "Strategy"),
    family: asText(strategy, "strategy_family", "research"),
    mode: asText(strategy, "live_mode") === "paper" ? "paper" : "research",
    status: asText(strategy, "status") === "planned" ? "planned" : asText(strategy, "status") === "research" ? "research" : "mapped",
    timeframe: asText(strategy, "timeframe", "mixed"),
    owner: asText(strategy, "owner_agent", "Quant Agent"),
    risk: asSeverity(strategy.risk_level, "medium")
  }));
}

function liveWorkflows(snapshot: LiveSnapshot | null): WorkflowItem[] {
  if (!snapshot?.workflows.length) {
    return [];
  }
  return snapshot.workflows.slice(0, 6).map((workflow) => ({
    key: asText(workflow, "workflow_key", asText(workflow, "workflow_name")),
    name: asText(workflow, "workflow_name", "Workflow"),
    status: statusForModule(workflow.status),
    owner: asText(workflow, "owner_agent", "Jarvis"),
    permission: asText(workflow, "permission_level", "read-only")
  }));
}

function liveAgents(snapshot: LiveSnapshot | null): AgentStatus[] {
  if (!snapshot?.agents.length) {
    return [];
  }
  return snapshot.agents.slice(0, 8).map((agent) => ({
    name: asText(agent, "agent_name", "Agent"),
    role: asText(agent, "display_title", asText(agent, "role_scope", asText(agent, "department_name", "Specialist"))),
    state: asText(agent, "latest_worker_status") === "failed"
      ? "blocked"
      : asText(agent, "latest_worker_status") === "completed" || asText(agent, "agent_name") === "Charlie Munger" || asText(agent, "agent_name") === "Jarvis"
        ? "running"
        : "waiting",
    currentTask: `${asText(agent, "skill_count", "0")} skills · ${asArray(agent, "primary_skills").slice(0, 2).join(", ") || asText(agent, "permission_level", "read")}`,
    costTier: asText(agent, "cost_policy", asText(agent, "default_model_route")).includes("cloud") ? "hybrid" : "local"
  }));
}

function liveHealth(snapshot: LiveSnapshot | null, apiStatus: string): HealthCheck[] {
  if (!snapshot) {
    return [
      {
        name: "Live API",
        status: apiStatus === "offline" ? "offline" : "degraded",
        detail: apiStatus === "loading" ? "connecting to warehouse API" : "warehouse API unavailable"
      },
      {
        name: "Display mode",
        status: "degraded",
        detail: "no seed fallback; waiting for live snapshot"
      }
    ];
  }
  return [
    { name: "Live API", status: "online", detail: `snapshot ${compactDate(snapshot.generated_at)}` },
    { name: "Postgres warehouse", status: "online", detail: `${metricValue(snapshot, "data_sources")} sources registered` },
    { name: "MCP tool layer", status: "online", detail: `${metricValue(snapshot, "mcp_enabled_tools")} tools visible` },
    {
      name: "TradingView Desktop MCP",
      status: snapshot.tradingview_cdp.available ? "online" : "degraded",
      detail: snapshot.tradingview_cdp.available ? "CDP 9222 online" : "TradingView open but CDP not enabled"
    },
    { name: "Research hub", status: "online", detail: `${metricValue(snapshot, "research_hub_artifacts")} artifacts indexed` }
  ];
}

function liveClients(snapshot: LiveSnapshot | null): ClientControlItem[] {
  if (!snapshot?.clients.length) {
    return [];
  }
  return snapshot.clients.slice(0, 6).map((client) => ({
    code: asText(client, "client_code", "CLIENT"),
    name: asText(client, "display_name", asText(client, "client_code", "Client")),
    accounts: asNumber(client, "account_count"),
    positions: asNumber(client, "latest_position_count"),
    staged: asNumber(client, "staged_holding_updates"),
    lastSync: compactDate(client.latest_position_at)
  }));
}

function liveManualUpdates(snapshot: LiveSnapshot | null): ManualUpdateItem[] {
  if (!snapshot?.manual_updates.length) {
    return [];
  }
  return snapshot.manual_updates.slice(0, 6).map((update) => ({
    id: asText(update, "id"),
    clientCode: asText(update, "client_code", "CLIENT"),
    accountCode: asText(update, "account_code", "Manual"),
    symbol: asText(update, "symbol", "SYMBOL"),
    quantity: asText(update, "quantity", "0"),
    status: asText(update, "status") === "applied" ? "applied" : "staged",
    source: asText(update, "created_by", "warehouse"),
    asOf: compactDate(update.as_of)
  }));
}

function liveSignals(snapshot: LiveSnapshot | null): SignalItem[] {
  if (!snapshot?.signals.length) {
    return [];
  }
  return snapshot.signals.slice(0, 6).map((signal) => ({
    id: asText(signal, "id"),
    symbol: asText(signal, "symbol", "SYMBOL"),
    strategy: asText(signal, "strategy", "Strategy"),
    timeframe: asText(signal, "timeframe", "live"),
    direction: asText(signal, "action") === "short" || asText(signal, "action") === "sell" ? "short" : asText(signal, "action") === "buy" || asText(signal, "action") === "long" ? "long" : "watch",
    confidence: Math.max(0, Math.min(100, asNumber(signal, "confidence", 50))),
    state: asText(signal, "status") === "approved" ? "approved" : "new"
  }));
}

function liveFincept(snapshot: LiveSnapshot | null): FinceptBridgeItem[] {
  if (!snapshot?.fincept.length) {
    return [];
  }
  return snapshot.fincept.slice(0, 6).map((item) => ({
    label: asText(item, "component_name", "Fincept"),
    status: asText(item, "install_status") === "installed" ? "installed" : "mapped",
    detail: `${asText(item, "build_status", "registered")} · ${asText(item, "runtime_mode", "sidecar")}`
  }));
}

function liveInbox(snapshot: LiveSnapshot | null): InboxItem[] {
  if (!snapshot?.inbox.length) {
    return [];
  }
  return snapshot.inbox.slice(0, 50).map((item) => ({
    id: asText(item, "id"),
    taskId: asText(item, "task_id"),
    title: asText(item, "title", "Inbox item"),
    agent: asText(item, "owner_agent", "Jarvis"),
    status: asStatus(asText(item, "status") === "in_progress" ? "running" : asText(item, "status"), "queued"),
    priority: asSeverity(item.priority, "medium"),
    evidence: asArray(item, "evidence").length ? asArray(item, "evidence") : ["agent.inbox_items"],
    recommendedAction: asText(item, "recommended_action", "Review"),
    claimedBy: asText(item, "claimed_by"),
    claimedAt: compactDate(item.claimed_at),
    resolvedBy: asText(item, "resolved_by"),
    resolutionNote: asText(item, "resolution_note"),
    updatedAt: compactDate(item.updated_at)
  }));
}

function liveApprovals(snapshot: LiveSnapshot | null): ApprovalItem[] {
  if (!snapshot?.approvals.length) {
    return [];
  }
  return snapshot.approvals.slice(0, 20).map((approval) => ({
    id: asText(approval, "id"),
    title: asText(approval, "title", "Approval"),
    owner: asText(approval, "owner_agent", "Risk Agent"),
    type: asText(approval, "approval_type") === "trade_action" ? "trade_action" : "system_change",
    risk: asSeverity(approval.risk_level, "medium"),
    status: asText(approval, "status") === "approved" ? "approved" : asText(approval, "status") === "rejected" ? "rejected" : "pending",
    summary: asText(approval, "rationale", "Requires review")
  }));
}

function livePortfolioAlerts(snapshot: LiveSnapshot | null): PortfolioAlert[] {
  if (!snapshot) {
    return [];
  }

  const openAlerts = snapshot.alerts.slice(0, 4).map((alert) => ({
    id: asText(alert, "id"),
    client: asText(alert, "exchange", "market"),
    symbol: asText(alert, "symbol", "SOURCE"),
    issue: asText(alert, "message", asText(alert, "title", "Open alert")),
    severity: asSeverity(alert.severity, "medium"),
    owner: "Strategy Alert"
  }));

  const staged = snapshot.clients
    .filter((client) => asNumber(client, "staged_holding_updates") > 0)
    .slice(0, 4)
    .map((client) => ({
      id: `client-${asText(client, "client_code")}`,
      client: asText(client, "display_name", asText(client, "client_code", "Client")),
      symbol: asText(client, "client_code", "CLIENT"),
      issue: `${asText(client, "staged_holding_updates", "0")} staged holding updates need review`,
      severity: "high" as Severity,
      owner: "Portfolio Manager"
    }));

  const conflicts = snapshot.cross_book_conflicts.slice(0, 4).map((conflict) => ({
    id: `book-conflict-${asText(conflict, "synthetic_id", asText(conflict, "symbol"))}`,
    client: asText(conflict, "client_name", asText(conflict, "client_code", "Client")),
    symbol: asText(conflict, "symbol", "SYMBOL"),
    issue: asText(conflict, "description", "Cross-book exposure needs review."),
    severity: asSeverity(conflict.severity, "high"),
    owner: "Risk Office"
  }));

  const bookGaps = snapshot.book_assignment_gaps.slice(0, 4).map((gap) => ({
    id: `book-gap-${asText(gap, "book_position_id")}-${asText(gap, "gap_type")}`,
    client: asText(gap, "client_name", asText(gap, "client_code", "Client")),
    symbol: asText(gap, "symbol", "SYMBOL"),
    issue: asText(gap, "gap_description", "Book assignment needs review."),
    severity: asSeverity(gap.severity, "medium"),
    owner: asText(gap, "owner_agent", "Portfolio Manager")
  }));

  return [...conflicts, ...staged, ...bookGaps, ...openAlerts].slice(0, 6);
}

function liveBriefLines(snapshot: LiveSnapshot | null): BriefLine[] {
  if (!snapshot) {
    return [];
  }

  const rows: BriefLine[] = [];
  if (snapshot.issues.length) {
    rows.push({
      time: compactDate(snapshot.generated_at),
      title: "Snapshot has query issues",
      detail: `${snapshot.issues.length} warehouse sections need inspection.`,
      tone: "bad"
    });
  }
  if (snapshot.data_source_checks.length) {
    const failed = snapshot.data_source_checks.filter((check) => asText(check, "status") !== "ok").length;
    rows.push({
      time: compactDate(snapshot.data_source_checks[0]?.checked_at),
      title: failed ? "Some public source checks need review" : "Public source checks have recent evidence",
      detail: `${snapshot.data_source_checks.length} checks visible from core.data_source_checks.`,
      tone: failed ? "warn" : "good"
    });
  }
  if (snapshot.research_hub.length) {
    rows.push({
      time: compactDate(snapshot.research_hub[0]?.latest_captured_at),
      title: "Research hub indexed",
      detail: `${metricValue(snapshot, "research_hub_artifacts")} local AI research artifacts are registered.`,
      tone: "good"
    });
  }
  if (snapshot.tradingview_tasks.length) {
    rows.push({
      time: compactDate(snapshot.tradingview_tasks[0]?.created_at),
      title: "TradingView task queue active",
      detail: `${snapshot.tradingview_tasks.length} chart/control tasks are in ops.tradingview_tasks.`,
      tone: snapshot.tradingview_cdp.available ? "good" : "warn"
    });
  }
  if (snapshot.inbox.length) {
    rows.push({
      time: compactDate(snapshot.inbox[0]?.updated_at),
      title: "Agent inbox has live work",
      detail: `${snapshot.inbox.length} visible inbox items from agent.inbox_items.`,
      tone: "neutral"
    });
  }
  if (snapshot.portfolio_intelligence_summary.length) {
    rows.push({
      time: compactDate(snapshot.generated_at),
      title: "Portfolio Intelligence Brain live",
      detail: `${portfolioSummaryValue(snapshot, "book_positions")} positions mapped across ${portfolioSummaryValue(snapshot, "investment_books")} books.`,
      tone: "good"
    });
  }
  return rows.slice(0, 5);
}

function liveWorkflowRuns(snapshot: LiveSnapshot | null): LiveRow[] {
  if (!snapshot?.workflows.length) {
    return [];
  }
  return snapshot.workflows
    .filter((workflow) => asText(workflow, "schedule_hint") || asText(workflow, "next_run_at"))
    .slice(0, 4);
}

function workspaceCounts(snapshot: LiveSnapshot | null): Record<WorkspaceId, number> {
  return {
    agents: snapshot?.agents.length ?? 0,
    departments: snapshot?.agent_departments.length ?? 0,
    approvals: snapshot?.approvals.length ?? 0,
    committees: snapshot?.approvals.length ?? 0,
    governance: snapshot?.approvals.filter((approval) => asText(approval, "approval_type") === "architecture_change").length ?? 0,
    capital: (snapshot?.book_positions.length ?? 0) + (snapshot?.cross_book_conflicts.length ?? 0),
    clients: snapshot?.clients.length ?? 0,
    tactical: snapshot?.agents.filter((agent) => asText(agent, "department") === "tactical").length ?? 0,
    command: (snapshot?.inbox.length ?? 0) + (snapshot?.agent_jobs.length ?? 0) + (snapshot?.agent_worker_queue.length ?? 0),
    ideas: snapshot?.approvals.length ?? 0,
    portfolio: (snapshot?.latest_positions.length ?? 0) + (snapshot?.book_positions.length ?? 0),
    quant: snapshot?.strategies.length ?? 0,
    reports: snapshot?.research_hub.length ?? 0,
    research: Number(metricValue(snapshot, "research_hub_artifacts", "0")),
    risk: (snapshot?.approvals.length ?? 0) + (snapshot?.alerts.length ?? 0) + (snapshot?.cross_book_conflicts.length ?? 0) + (snapshot?.book_assignment_gaps.length ?? 0),
    arsenal: snapshot?.strategies.length ?? 0,
    system: (snapshot?.mcp_candidates.length ?? 0) + (snapshot?.data_source_checks.length ?? 0) + (snapshot?.dashboard_widgets.length ?? 0) + (snapshot?.agent_skills.length ?? 0),
    treasury: snapshot?.data_source_checks.length ?? 0,
    models: snapshot?.model_routes.length ?? 0,
    trading: (snapshot?.signals.length ?? 0) + (snapshot?.tradingview_tasks.length ?? 0)
  };
}

interface CommandCenterAppProps {
  activeWorkspace: WorkspaceId;
  setActiveWorkspace: (workspace: WorkspaceId) => void;
  setInterfaceMode: (mode: InterfaceMode) => void;
}

interface OfficeWorkspaceProps {
  activeWorkspace: WorkspaceId;
  onExit: () => void;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

function OfficeWorkspace({ activeWorkspace, onExit, onSelectWorkspace }: OfficeWorkspaceProps) {
  const ignoreOfficeSnapshot = useCallback((_snapshot: OfficeSnapshot) => {}, []);
  const ignoreOfficeOffline = useCallback(() => {}, []);
  const { liveStatus, refresh, snapshot } = useLiveSnapshot<OfficeSnapshot>({
    fetchSnapshot: fetchOfficeSnapshot,
    onOffline: ignoreOfficeOffline,
    onSnapshot: ignoreOfficeSnapshot
  });

  return (
    <Suspense fallback={<div className="office-loading-state">Loading live office...</div>}>
      <LiveOffice
        liveStatus={liveStatus}
        onExit={onExit}
        onRefresh={() => {
          void refresh();
        }}
        onSelectWorkspace={onSelectWorkspace}
        onSendMessage={async ({ body, subject, toAgent }) => {
          await createAgentMessage({
            body,
            from_agent: "Charlie Munger",
            metadata: {
              source_surface: "live_office",
              workspace: activeWorkspace
            },
            priority: "medium",
            subject,
            thread_key: `live-office-${toAgent.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
            to_agent: toAgent
          });
          await refresh();
        }}
        snapshot={snapshot}
      />
    </Suspense>
  );
}

function LegacyCommandCenterApp({ activeWorkspace, setActiveWorkspace, setInterfaceMode }: CommandCenterAppProps) {
  const [command, setCommand] = useState("");
  const [items, setItems] = useState<InboxItem[]>([]);
  const [approvalItems, setApprovalItems] = useState<ApprovalItem[]>([]);
  const [manualUpdates, setManualUpdates] = useState<ManualUpdateItem[]>([]);
  const [commandBusy, setCommandBusy] = useState(false);
  const [holdingBusy, setHoldingBusy] = useState(false);
  const [bookAssignmentBusy, setBookAssignmentBusy] = useState(false);
  const [tradeTicketBusy, setTradeTicketBusy] = useState(false);
  const [strategyIntakeBusy, setStrategyIntakeBusy] = useState(false);
  const [strategyTemplateBusyKey, setStrategyTemplateBusyKey] = useState("");
  const [userStrategyOptimizerBusy, setUserStrategyOptimizerBusy] = useState(false);
  const [strategyDiscoveryBusy, setStrategyDiscoveryBusy] = useState(false);
  const [strategyDiscoverySchedulerBusy, setStrategyDiscoverySchedulerBusy] = useState(false);
  const [newsIngestionBusy, setNewsIngestionBusy] = useState(false);
  const [strategyTriageBusyId, setStrategyTriageBusyId] = useState("");
  const [strategyDossierBusy, setStrategyDossierBusy] = useState(false);
  const [strategyDossierSearchBusy, setStrategyDossierSearchBusy] = useState(false);
  const [strategyDossierSearchQuery, setStrategyDossierSearchQuery] = useState("TATASTEEL optimizer committee");
  const [strategyDossierSearchResults, setStrategyDossierSearchResults] = useState<LiveRow[]>([]);
  const [strategyDossierActionBusyId, setStrategyDossierActionBusyId] = useState("");
  const [strategyDslBusyId, setStrategyDslBusyId] = useState("");
  const [dataQualityBusyId, setDataQualityBusyId] = useState("");
  const [backtestBusyId, setBacktestBusyId] = useState("");
  const [optimizeBusyId, setOptimizeBusyId] = useState("");
  const [quantAnalyticsBusy, setQuantAnalyticsBusy] = useState(false);
  const [strategyAllocationBusy, setStrategyAllocationBusy] = useState(false);
  const [strategyRetirementBusy, setStrategyRetirementBusy] = useState(false);
  const [modelValidationBusy, setModelValidationBusy] = useState(false);
  const [tradeJournalMiningBusy, setTradeJournalMiningBusy] = useState(false);
  const [committeeBusyId, setCommitteeBusyId] = useState("");
  const [memoBusyId, setMemoBusyId] = useState("");
  const [committeeDecisionBusyId, setCommitteeDecisionBusyId] = useState("");
  const [paperMonitorBusyId, setPaperMonitorBusyId] = useState("");
  const [driftBusyId, setDriftBusyId] = useState("");
  const [killSwitchBusyId, setKillSwitchBusyId] = useState("");
  const [executionSafetyBusyId, setExecutionSafetyBusyId] = useState("");
  const [chartActionBusyId, setChartActionBusyId] = useState("");
  const [tradingViewAlertBusyId, setTradingViewAlertBusyId] = useState("");
  const [brokerStageBusy, setBrokerStageBusy] = useState(false);
  const [brokerReconBusy, setBrokerReconBusy] = useState(false);
  const [p2CursorReconBusy, setP2CursorReconBusy] = useState(false);
  const [legacySourceBusy, setLegacySourceBusy] = useState(false);
  const [widgetBusy, setWidgetBusy] = useState(false);
  const [agentWorkerBusy, setAgentWorkerBusy] = useState(false);
  const [inboxBusyId, setInboxBusyId] = useState("");
  const [modelEndpointBusyId, setModelEndpointBusyId] = useState("");
  const [sourceConnectorBusyId, setSourceConnectorBusyId] = useState("");
  const [providerReadinessBusy, setProviderReadinessBusy] = useState(false);
  const [providerAssignmentBusyId, setProviderAssignmentBusyId] = useState("");
  const [browserProfileBusyId, setBrowserProfileBusyId] = useState("");
  const [agentMessageBusyId, setAgentMessageBusyId] = useState("");
  const [agentCommentBusyId, setAgentCommentBusyId] = useState("");
  const [filingCollectorBusy, setFilingCollectorBusy] = useState(false);
  const [filingExtractorBusy, setFilingExtractorBusy] = useState(false);
  const [specialMemoBusyId, setSpecialMemoBusyId] = useState("");
  const [longTermCoverageBusy, setLongTermCoverageBusy] = useState(false);
  const [longTermCoverageMemoBusyKey, setLongTermCoverageMemoBusyKey] = useState("");
  const [longTermThesisBusy, setLongTermThesisBusy] = useState(false);
  const [longTermPacketBusyId, setLongTermPacketBusyId] = useState("");
  const [longTermCommitteeBusyId, setLongTermCommitteeBusyId] = useState("");
  const [longTermCommitteeMemoBusyId, setLongTermCommitteeMemoBusyId] = useState("");
  const [longTermCommitteeDecisionBusyId, setLongTermCommitteeDecisionBusyId] = useState("");
  const [longTermSpecialistBusyId, setLongTermSpecialistBusyId] = useState("");
  const [longTermSpecialistExecuteBusyId, setLongTermSpecialistExecuteBusyId] = useState("");
  const [longTermSourceRequestBusyId, setLongTermSourceRequestBusyId] = useState("");
  const [longTermSourceCheckBusyId, setLongTermSourceCheckBusyId] = useState("");
  const [longTermSourceDocumentBusy, setLongTermSourceDocumentBusy] = useState(false);
  const [longTermSourceExtractBusyId, setLongTermSourceExtractBusyId] = useState("");
  const [eventQuoteBusy, setEventQuoteBusy] = useState(false);
  const [sourceFreshnessBusy, setSourceFreshnessBusy] = useState(false);
  const [riskRefreshBusy, setRiskRefreshBusy] = useState(false);
  const [specialSpreadBusyId, setSpecialSpreadBusyId] = useState("");
  const [specialDecisionBusyId, setSpecialDecisionBusyId] = useState("");
  const [positionRemediationBusy, setPositionRemediationBusy] = useState(false);
  const [symbolActionBusyId, setSymbolActionBusyId] = useState("");
  const [uiError, setUiError] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [holdingDraft, setHoldingDraft] = useState({
    accountCode: "",
    clientCode: "",
    quantity: "",
    symbol: ""
  });
  const [bookAssignmentDraft, setBookAssignmentDraft] = useState({
    bookKey: "long_term",
    bookPositionId: "",
    exitCriteria: "",
    purposeKey: "core_compounder",
    thesis: ""
  });
  const [sourceDocumentDraft, setSourceDocumentDraft] = useState({
    documentType: "annual_report",
    sourceRequestId: "",
    sourceUrl: "",
    title: ""
  });
  const [longTermThesisDraft, setLongTermThesisDraft] = useState({
    exchange: "NSE",
    symbol: ""
  });
  const [tradeDraft, setTradeDraft] = useState({
    accountCode: "",
    bookKey: "active_trading",
    clientCode: "",
    mode: "paper",
    price: "",
    purposeKey: "intraday_setup",
    quantity: "",
    side: "buy",
    stopLoss: "",
    symbol: "",
    targetPrice: "",
    thesis: ""
  });
  const [strategyDraft, setStrategyDraft] = useState({
    assetClass: "equity",
    constraintsText: "",
    family: "quant",
    intakeText: "",
    name: "",
    riskNotes: "",
    symbols: "",
    template: "momentum",
    timeframe: "intraday_to_days",
    universe: "NSE"
  });
  const [filingCollectorDraft, setFilingCollectorDraft] = useState({
    dateFrom: isoDateOffset(-1),
    dateTo: isoDateOffset(0),
    limit: "25",
    source: "all"
  });
  const [filingExtractorDraft, setFilingExtractorDraft] = useState({
    filingId: "",
    force: false,
    limit: "3"
  });
  const [agentCommentDraft, setAgentCommentDraft] = useState({
    body: "",
    fromAgent: "Charlie Munger",
    severity: "normal",
    targetRef: "",
    toAgent: "Jarvis"
  });

  const applyLiveSnapshot = useCallback((nextSnapshot: LiveSnapshot) => {
    setItems(liveInbox(nextSnapshot));
    setApprovalItems(liveApprovals(nextSnapshot));
    setManualUpdates(liveManualUpdates(nextSnapshot));
    setUiError("");
  }, []);
  const clearLiveSnapshot = useCallback(() => {
    setItems([]);
    setApprovalItems([]);
    setManualUpdates([]);
  }, []);
  const { liveStatus, refresh: refreshLiveSnapshot, setLiveStatus, setSnapshot, snapshot } = useLiveSnapshot({
    enabled: false,
    onOffline: clearLiveSnapshot,
    onSnapshot: applyLiveSnapshot
  });

  const workspaceNav = useMemo(() => {
    const counts = workspaceCounts(snapshot);
    return baseWorkspaces.map((workspace) => ({ ...workspace, count: counts[workspace.id] }));
  }, [snapshot]);

  const activeWorkspaceLabel = useMemo(
    () => workspaceNav.find((workspace) => workspace.id === activeWorkspace)?.label ?? "Command Center",
    [activeWorkspace, workspaceNav]
  );

  const pendingApprovals = Number(
    asText((snapshot?.approval_board_summary ?? []).find((row) => asText(row, "metric") === "pending") ?? {}, "value", String(approvalItems.filter((item) => item.status === "pending").length))
  );
  const highPriorityItems = items.filter((item) => item.priority === "high" || item.priority === "critical").length;
  const inboxAgentOptions = useMemo(
    () => [...new Set((snapshot?.agents ?? []).map((agent) => asText(agent, "agent_name")).filter(Boolean))].sort(),
    [snapshot]
  );

  const refreshSnapshot = async () => {
    const nextSnapshot = await refreshLiveSnapshot();
    setUiError("");
    return nextSnapshot;
  };

  const dashboardMetrics = useMemo(() => liveMetrics(snapshot), [snapshot]);
  const dashboardModules = useMemo(() => liveControlModules(snapshot), [snapshot]);
  const dashboardBlueprintSummary = useMemo(
    () => snapshot?.blueprint_summary ?? snapshot?.blueprint_v9_summary ?? [],
    [snapshot]
  );
  const dashboardBlueprintDomains = useMemo(() => {
    const domains = snapshot?.blueprint_domains ?? snapshot?.blueprint_v9_domains ?? [];
    const frontend = domains.filter((domain) => asText(domain, "section_number") === "16");
    const remaining = domains.filter((domain) => asText(domain, "section_number") !== "16");
    return [...frontend, ...remaining].slice(0, 8);
  }, [snapshot]);
  const dashboardBlueprintRequirements = useMemo(
    () => (snapshot?.blueprint_requirements ?? snapshot?.blueprint_v9_requirements ?? []).slice(0, 8),
    [snapshot]
  );
  const latestBlueprintSync = useMemo(() => snapshot?.blueprint_sync_runs?.[0] ?? null, [snapshot]);
  const dashboardSources = useMemo(() => liveDataSources(snapshot), [snapshot]);
  const dashboardStrategies = useMemo(() => liveStrategies(snapshot), [snapshot]);
  const dashboardStrategyArsenal = useMemo(() => snapshot?.strategy_arsenal_queue.slice(0, 8) ?? [], [snapshot]);
  const dashboardStrategySummary = useMemo(() => snapshot?.strategy_arsenal_summary ?? [], [snapshot]);
  const dashboardStrategyTemplateSummary = useMemo(() => snapshot?.strategy_template_summary ?? [], [snapshot]);
  const dashboardStrategyTemplates = useMemo(() => snapshot?.strategy_template_library.slice(0, 10) ?? [], [snapshot]);
  const dashboardStrategyTemplateApplications = useMemo(() => snapshot?.strategy_template_applications.slice(0, 5) ?? [], [snapshot]);
  const dashboardStrategyDslReadiness = useMemo(() => snapshot?.strategy_dsl_readiness.slice(0, 8) ?? [], [snapshot]);
  const dashboardStrategyDataQualityGates = useMemo(() => snapshot?.strategy_data_quality_gates.slice(0, 6) ?? [], [snapshot]);
  const dashboardStrategyOptimizations = useMemo(() => snapshot?.strategy_optimization_runs.slice(0, 6) ?? [], [snapshot]);
  const dashboardUserOptimizerRuns = useMemo(() => snapshot?.user_defined_optimizer_runs.slice(0, 5) ?? [], [snapshot]);
  const dashboardStrategyDiscoveryRuns = useMemo(() => snapshot?.strategy_discovery_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardStrategyDiscoveryCandidates = useMemo(() => snapshot?.strategy_discovery_candidates.slice(0, 6) ?? [], [snapshot]);
  const dashboardStrategyDiscoveryTriage = useMemo(() => snapshot?.strategy_discovery_triage_queue.slice(0, 8) ?? [], [snapshot]);
  const dashboardStrategyDiscoveryTriageDecisions = useMemo(() => snapshot?.strategy_discovery_triage_decisions.slice(0, 4) ?? [], [snapshot]);
  const dashboardStrategyIdeaDossiers = useMemo(() => snapshot?.strategy_idea_dossiers.slice(0, 6) ?? [], [snapshot]);
  const dashboardStrategyIdeaDossierBuildRuns = useMemo(() => snapshot?.strategy_idea_dossier_build_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardStrategyIdeaDossierSearchRuns = useMemo(() => snapshot?.strategy_idea_dossier_search_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardStrategyIdeaDossierActions = useMemo(() => snapshot?.strategy_idea_dossier_actions.slice(0, 5) ?? [], [snapshot]);
  const dashboardStrategyDossierSearchResultRows = useMemo(() => {
    if (strategyDossierSearchResults.length) {
      return strategyDossierSearchResults;
    }
    const latest = dashboardStrategyIdeaDossierSearchRuns[0];
    const rows = latest && Array.isArray(latest.results) ? latest.results : [];
    return rows.filter((row): row is LiveRow => typeof row === "object" && row !== null).slice(0, 6);
  }, [dashboardStrategyIdeaDossierSearchRuns, strategyDossierSearchResults]);
  const dashboardStrategyDiscoverySchedulerRuns = useMemo(() => snapshot?.strategy_discovery_scheduler_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardNewsIngestionRuns = useMemo(() => snapshot?.news_ingestion_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardLatestNewsItems = useMemo(() => snapshot?.latest_news_items.slice(0, 5) ?? [], [snapshot]);
  const dashboardQuantAnalyticsRuns = useMemo(() => snapshot?.strategy_quant_analytics_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardQuantOptimizerRuns = useMemo(() => snapshot?.strategy_portfolio_optimizer_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardQuantRegimes = useMemo(() => snapshot?.strategy_regime_performance.slice(0, 4) ?? [], [snapshot]);
  const dashboardQuantFactors = useMemo(() => snapshot?.strategy_factor_attribution.slice(0, 4) ?? [], [snapshot]);
  const dashboardStrategyAllocationRuns = useMemo(() => snapshot?.strategy_portfolio_allocation_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardStrategyAllocations = useMemo(() => snapshot?.strategy_portfolio_allocations.slice(0, 5) ?? [], [snapshot]);
  const dashboardStrategyRuin = useMemo(() => snapshot?.strategy_probability_of_ruin.slice(0, 4) ?? [], [snapshot]);
  const dashboardStrategyRetirement = useMemo(() => snapshot?.strategy_retirement_queue.slice(0, 5) ?? [], [snapshot]);
  const dashboardQuantSpecialists = useMemo(() => snapshot?.quant_specialist_assignments.slice(0, 6) ?? [], [snapshot]);
  const dashboardQuantLabV2 = useMemo(() => snapshot?.quant_lab_dashboard_v2.slice(0, 6) ?? [], [snapshot]);
  const dashboardModelValidation = useMemo(() => snapshot?.model_validation_dashboard.slice(0, 6) ?? [], [snapshot]);
  const dashboardPromotionBoard = useMemo(() => snapshot?.strategy_promotion_board.slice(0, 6) ?? [], [snapshot]);
  const dashboardTradeJournalMiningRuns = useMemo(() => snapshot?.trade_journal_mining_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardTradeJournalIdeas = useMemo(() => snapshot?.trade_journal_idea_dashboard.slice(0, 6) ?? [], [snapshot]);
  const dashboardStrategyCommittee = useMemo(() => snapshot?.strategy_committee_queue.slice(0, 6) ?? [], [snapshot]);
  const dashboardPaperMonitors = useMemo(() => snapshot?.strategy_paper_monitors.slice(0, 6) ?? [], [snapshot]);
  const dashboardPaperMonitorEvents = useMemo(() => snapshot?.strategy_paper_monitor_events.slice(0, 6) ?? [], [snapshot]);
  const dashboardDriftChecks = useMemo(() => snapshot?.strategy_drift_checks.slice(0, 6) ?? [], [snapshot]);
  const dashboardKillSwitchEvents = useMemo(() => snapshot?.strategy_kill_switch_events.slice(0, 6) ?? [], [snapshot]);
  const dashboardExecutionControl = useMemo(() => snapshot?.execution_control[0] ?? null, [snapshot]);
  const dashboardGlobalKillSwitchEvents = useMemo(() => snapshot?.global_kill_switch_events.slice(0, 4) ?? [], [snapshot]);
  const dashboardLimitedLiveRequests = useMemo(() => snapshot?.limited_live_requests.slice(0, 6) ?? [], [snapshot]);
  const dashboardExecutionGateChecks = useMemo(() => snapshot?.execution_gate_checks.slice(0, 4) ?? [], [snapshot]);
  const dashboardOrderIntents = useMemo(() => snapshot?.order_intents.slice(0, 6) ?? [], [snapshot]);
  const dashboardOrderRiskChecks = useMemo(() => snapshot?.order_risk_checks.slice(0, 4) ?? [], [snapshot]);
  const dashboardWorkflows = useMemo(() => liveWorkflows(snapshot), [snapshot]);
  const dashboardAgents = useMemo(() => liveAgents(snapshot), [snapshot]);
  const dashboardHealth = useMemo(() => liveHealth(snapshot, liveStatus), [snapshot, liveStatus]);
  const dashboardClients = useMemo(() => liveClients(snapshot), [snapshot]);
  const dashboardSignals = useMemo(() => liveSignals(snapshot), [snapshot]);
  const dashboardFincept = useMemo(() => liveFincept(snapshot), [snapshot]);
  const dashboardBrief = useMemo(() => liveBriefLines(snapshot), [snapshot]);
  const dashboardAlerts = useMemo(() => livePortfolioAlerts(snapshot), [snapshot]);
  const dashboardRuns = useMemo(() => liveWorkflowRuns(snapshot), [snapshot]);
  const dashboardWidgetIntents = useMemo(() => snapshot?.widget_intents.slice(0, 5) ?? [], [snapshot]);
  const dashboardWidgets = useMemo(() => snapshot?.dashboard_widgets.slice(0, 8) ?? [], [snapshot]);
  const dashboardInvestmentBooks = useMemo(() => snapshot?.investment_books.slice(0, 6) ?? [], [snapshot]);
  const dashboardPositionObjectsV9 = useMemo(() => snapshot?.position_objects_v9.slice(0, 8) ?? [], [snapshot]);
  const dashboardPositionObjectGaps = useMemo(() => snapshot?.position_object_gap_summary.slice(0, 8) ?? [], [snapshot]);
  const dashboardPositionRemediationSummary = useMemo(() => snapshot?.position_remediation_summary ?? [], [snapshot]);
  const dashboardPositionRemediationQueue = useMemo(() => snapshot?.position_remediation_queue.slice(0, 8) ?? [], [snapshot]);
  const dashboardLongTermTheses = useMemo(() => snapshot?.long_term_theses.slice(0, 10) ?? [], [snapshot]);
  const dashboardLongTermCoverageSummary = useMemo(() => snapshot?.long_term_coverage_summary ?? [], [snapshot]);
  const dashboardLongTermCoverageQueue = useMemo(() => snapshot?.long_term_coverage_queue.slice(0, 12) ?? [], [snapshot]);
  const dashboardLongTermChecklistRows = useMemo(() => snapshot?.long_term_thesis_checklists.slice(0, 10) ?? [], [snapshot]);
  const dashboardLongTermValuationRows = useMemo(() => snapshot?.long_term_valuation_models.slice(0, 8) ?? [], [snapshot]);
  const dashboardLongTermMonteCarloRuns = useMemo(() => snapshot?.long_term_monte_carlo_runs.slice(0, 6) ?? [], [snapshot]);
  const dashboardLongTermResearchUpdates = useMemo(() => snapshot?.long_term_research_updates.slice(0, 6) ?? [], [snapshot]);
  const dashboardLongTermCommittee = useMemo(() => snapshot?.long_term_committee_queue.slice(0, 6) ?? [], [snapshot]);
  const dashboardLongTermSpecialists = useMemo(() => snapshot?.long_term_specialist_assignments.slice(0, 10) ?? [], [snapshot]);
  const dashboardLongTermSpecialistOutputs = useMemo(() => snapshot?.long_term_specialist_outputs.slice(0, 8) ?? [], [snapshot]);
  const dashboardLongTermSourceRequests = useMemo(() => snapshot?.long_term_source_requests.slice(0, 8) ?? [], [snapshot]);
  const dashboardLongTermSourceDocuments = useMemo(() => snapshot?.long_term_source_documents.slice(0, 6) ?? [], [snapshot]);
  const dashboardLongTermSourceExtractions = useMemo(() => snapshot?.long_term_source_document_extractions.slice(0, 6) ?? [], [snapshot]);
  const dashboardLongTermSourceChecks = useMemo(() => snapshot?.long_term_source_request_checks.slice(0, 6) ?? [], [snapshot]);
  const dashboardSymbolIntelligenceV2Summary = useMemo(() => snapshot?.symbol_intelligence_v2_summary ?? [], [snapshot]);
  const dashboardSymbolIntelligenceActionSummary = useMemo(() => snapshot?.symbol_intelligence_action_summary ?? [], [snapshot]);
  const dashboardSymbolIntelligence = useMemo(() => (snapshot?.symbol_intelligence_v2?.length ? snapshot.symbol_intelligence_v2 : snapshot?.symbol_intelligence ?? []).slice(0, 8), [snapshot]);
  const dashboardClientBookExposure = useMemo(() => snapshot?.client_book_exposure.slice(0, 8) ?? [], [snapshot]);
  const dashboardCrossBookConflicts = useMemo(() => snapshot?.cross_book_conflicts.slice(0, 6) ?? [], [snapshot]);
  const dashboardCrossBookCoordination = useMemo(() => snapshot?.cross_book_coordination_questions.slice(0, 6) ?? [], [snapshot]);
  const dashboardBookAssignmentGaps = useMemo(() => snapshot?.book_assignment_gaps.slice(0, 8) ?? [], [snapshot]);
  const dashboardPortfolioIntelligenceV2 = useMemo(() => snapshot?.portfolio_intelligence_v2.slice(0, 10) ?? [], [snapshot]);
  const dashboardRiskSummary = useMemo(() => snapshot?.risk_dashboard_summary ?? [], [snapshot]);
  const dashboardRiskLimitChecks = useMemo(() => snapshot?.risk_limit_checks.slice(0, 12) ?? [], [snapshot]);
  const dashboardBrokerQueue = useMemo(() => snapshot?.broker_transaction_import_queue.slice(0, 8) ?? [], [snapshot]);
  const dashboardBrokerSummary = useMemo(() => snapshot?.broker_transaction_import_summary ?? [], [snapshot]);
  const dashboardTradeBookLinks = useMemo(() => snapshot?.trade_book_links.slice(0, 8) ?? [], [snapshot]);
  const dashboardBrokerRecon = useMemo(() => snapshot?.broker_reconciliation_latest[0] ?? null, [snapshot]);
  const dashboardBrokerReconIssues = useMemo(() => snapshot?.broker_reconciliation_issues.slice(0, 6) ?? [], [snapshot]);
  const dashboardP2CursorRecon = useMemo(() => snapshot?.p2cursor_reconciliation_latest[0] ?? null, [snapshot]);
  const dashboardP2CursorReconIssues = useMemo(() => snapshot?.p2cursor_reconciliation_issues.slice(0, 8) ?? [], [snapshot]);
  const dashboardLegacySourceSummary = useMemo(() => snapshot?.legacy_source_readiness_summary ?? [], [snapshot]);
  const dashboardLegacySourceRun = useMemo(() => snapshot?.legacy_source_extraction_runs[0] ?? null, [snapshot]);
  const dashboardP2CursorExtraction = useMemo(() => snapshot?.p2cursor_extraction_readiness.slice(0, 6) ?? [], [snapshot]);
  const dashboardAlgoExtraction = useMemo(() => snapshot?.algo_extraction_readiness.slice(0, 8) ?? [], [snapshot]);
  const dashboardLegacySourceIssues = useMemo(() => snapshot?.legacy_source_extraction_issues.slice(0, 8) ?? [], [snapshot]);
  const dashboardSourceLineageSummary = useMemo(() => snapshot?.source_lineage_summary.slice(0, 8) ?? [], [snapshot]);
  const dashboardSourceArtifactLineage = useMemo(() => snapshot?.source_artifact_lineage.slice(0, 8) ?? [], [snapshot]);
  const dashboardImportArtifactCoverage = useMemo(() => snapshot?.import_artifact_coverage ?? [], [snapshot]);
  const dashboardImportArtifactGaps = useMemo(() => snapshot?.import_artifact_gaps.slice(0, 6) ?? [], [snapshot]);
  const dashboardPostTradeReviews = useMemo(() => snapshot?.post_trade_reviews.slice(0, 8) ?? [], [snapshot]);
  const selectedBookPurposes = useMemo(
    () => (snapshot?.position_purpose_options ?? []).filter((option) => asText(option, "book_key") === bookAssignmentDraft.bookKey),
    [bookAssignmentDraft.bookKey, snapshot]
  );
  const selectedTradePurposes = useMemo(
    () => (snapshot?.position_purpose_options ?? []).filter((option) => asText(option, "book_key") === tradeDraft.bookKey),
    [snapshot, tradeDraft.bookKey]
  );
  const dashboardAgentDepartments = useMemo(() => snapshot?.agent_departments.slice(0, 8) ?? [], [snapshot]);
  const dashboardAgentSkills = useMemo(() => snapshot?.agent_skills.slice(0, 12) ?? [], [snapshot]);
  const dashboardAgentOrg = useMemo(() => snapshot?.agent_org_chart.slice(0, 20) ?? [], [snapshot]);
  const dashboardLiveOfficeRooms = useMemo(() => snapshot?.live_office_rooms ?? [], [snapshot]);
  const dashboardLiveOfficeAgents = useMemo(
    () => [...(snapshot?.live_office_agent_activity ?? [])].sort((left, right) => asNumber(right, "workload_score") - asNumber(left, "workload_score")).slice(0, 8),
    [snapshot]
  );
  const dashboardAgentMailboxes = useMemo(() => snapshot?.agent_mailboxes.slice(0, 8) ?? [], [snapshot]);
  const dashboardAgentMessages = useMemo(() => snapshot?.agent_messages.slice(0, 6) ?? [], [snapshot]);
  const dashboardResearchFactoryQueue = useMemo(() => snapshot?.research_factory_queue_summary ?? [], [snapshot]);
  const dashboardAgentModels = useMemo(() => snapshot?.agent_models.slice(0, 10) ?? [], [snapshot]);
  const dashboardExternalSkills = useMemo(() => snapshot?.external_skills.slice(0, 14) ?? [], [snapshot]);
  const dashboardWorkerQueue = useMemo(() => snapshot?.agent_worker_queue.slice(0, 8) ?? [], [snapshot]);
  const dashboardWorkerRuns = useMemo(() => snapshot?.agent_worker_runs.slice(0, 6) ?? [], [snapshot]);
  const dashboardModelEndpoints = useMemo(() => snapshot?.model_endpoints.slice(0, 8) ?? [], [snapshot]);
  const dashboardModelCostSummary = useMemo(() => snapshot?.model_cost_summary ?? [], [snapshot]);
  const dashboardModelCostEvents = useMemo(() => snapshot?.model_cost_events.slice(0, 8) ?? [], [snapshot]);
  const dashboardModelCostCaps = useMemo(() => snapshot?.model_cost_caps.slice(0, 8) ?? [], [snapshot]);
  const dashboardModelRouteCosts = useMemo(() => snapshot?.model_route_costs.slice(0, 6) ?? [], [snapshot]);
  const dashboardSourceConnectors = useMemo(() => snapshot?.source_connectors.slice(0, 10) ?? [], [snapshot]);
  const dashboardProviderReadiness = useMemo(() => snapshot?.provider_readiness_board.slice(0, 16) ?? [], [snapshot]);
  const dashboardProviderReadinessSummary = useMemo(() => snapshot?.provider_readiness_summary ?? [], [snapshot]);
  const dashboardProviderReadinessRuns = useMemo(() => snapshot?.provider_readiness_runs.slice(0, 3) ?? [], [snapshot]);
  const dashboardProviderAssignmentGates = useMemo(() => snapshot?.provider_assignment_gates.slice(0, 8) ?? [], [snapshot]);
  const dashboardDepartmentProviderPolicies = useMemo(() => snapshot?.department_provider_policy_board.slice(0, 10) ?? [], [snapshot]);
  const dashboardTaskProviderGates = useMemo(() => snapshot?.task_provider_gate_status.slice(0, 8) ?? [], [snapshot]);
  const dashboardConnectorHealthChecks = useMemo(() => snapshot?.connector_health_checks.slice(0, 8) ?? [], [snapshot]);
  const dashboardTradingViewAlertRequests = useMemo(() => snapshot?.tradingview_alert_requests.slice(0, 6) ?? [], [snapshot]);
  const dashboardSourceFreshness = useMemo(() => snapshot?.source_freshness.slice(0, 8) ?? [], [snapshot]);
  const dashboardSourceFreshnessSchedulerRuns = useMemo(() => snapshot?.source_freshness_scheduler_runs.slice(0, 5) ?? [], [snapshot]);
  const dashboardRiskEvents = useMemo(() => snapshot?.risk_events.slice(0, 8) ?? [], [snapshot]);
  const dashboardApprovalBoardSummary = useMemo(() => snapshot?.approval_board_summary ?? [], [snapshot]);
  const dashboardApprovalBoardItems = useMemo(() => snapshot?.approval_board_items.slice(0, 20) ?? [], [snapshot]);
  const dashboardCommitteeRoomSummary = useMemo(() => snapshot?.committee_room_summary ?? [], [snapshot]);
  const dashboardCommitteeRoomItems = useMemo(() => snapshot?.committee_room_items.slice(0, 12) ?? [], [snapshot]);
  const dashboardEmployeeProfileSummary = useMemo(() => snapshot?.employee_profile_summary ?? [], [snapshot]);
  const dashboardEmployeeProfiles = useMemo(
    () => [...(snapshot?.employee_profiles ?? [])].sort((left, right) => asNumber(right, "workload_score") - asNumber(left, "workload_score")).slice(0, 12),
    [snapshot]
  );
  const dashboardOutputArtifactSummary = useMemo(() => snapshot?.output_artifact_summary ?? [], [snapshot]);
  const dashboardOutputArtifacts = useMemo(() => snapshot?.output_artifact_registry.slice(0, 10) ?? [], [snapshot]);
  const dashboardOutputArtifactGaps = useMemo(() => snapshot?.output_artifact_gaps.slice(0, 6) ?? [], [snapshot]);
  const dashboardAgentCommentSummary = useMemo(() => snapshot?.agent_comment_summary ?? [], [snapshot]);
  const dashboardAgentComments = useMemo(() => snapshot?.agent_comments.slice(0, 10) ?? [], [snapshot]);
  const dashboardAgentCommentTargets = useMemo(() => snapshot?.agent_comment_targets.slice(0, 6) ?? [], [snapshot]);
  const dashboardBrowserProfiles = useMemo(() => snapshot?.browser_profiles.slice(0, 8) ?? [], [snapshot]);
  const dashboardBrowserLinks = useMemo(() => snapshot?.browser_connector_links.slice(0, 8) ?? [], [snapshot]);
  const dashboardBrowserChecks = useMemo(() => snapshot?.browser_session_checks.slice(0, 8) ?? [], [snapshot]);
  const dashboardFilingCollectorRuns = useMemo(() => snapshot?.filing_collector_runs.slice(0, 6) ?? [], [snapshot]);
  const dashboardCorporateFilingInbox = useMemo(() => snapshot?.corporate_filing_inbox.slice(0, 8) ?? [], [snapshot]);
  const dashboardSpecialSituationInbox = useMemo(() => snapshot?.special_situation_inbox.slice(0, 6) ?? [], [snapshot]);
  const dashboardFilingPdfRuns = useMemo(() => snapshot?.filing_pdf_extraction_runs.slice(0, 6) ?? [], [snapshot]);
  const dashboardSpecialSituationTerms = useMemo(() => snapshot?.special_situation_terms.slice(0, 6) ?? [], [snapshot]);
  const dashboardSpecialSituationMemos = useMemo(() => snapshot?.special_situation_memos.slice(0, 6) ?? [], [snapshot]);
  const dashboardSpecialSituationSpreads = useMemo(() => snapshot?.special_situation_spread_checks.slice(0, 6) ?? [], [snapshot]);
  const dashboardSpecialSituationDecisions = useMemo(() => snapshot?.special_situation_decisions.slice(0, 6) ?? [], [snapshot]);

  const submitCommand = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const cleanCommand = command.trim();
    if (!cleanCommand || commandBusy) {
      return;
    }

    const routed = routeCommand(cleanCommand);
    const title = cleanCommand.length > 74 ? `${cleanCommand.slice(0, 71)}...` : cleanCommand;
    setCommand("");

    setCommandBusy(true);
    setUiError("");
    try {
      if (routed.agent === "Trading Desk") {
        await createTradingViewTask({
          task_title: title,
          task_type: "chart_review",
          requested_by: "Charlie Munger",
          owner_agent: "Trading Desk Agent",
          priority: routed.priority,
          symbols: extractSymbols(cleanCommand),
          instruction: cleanCommand,
          source_ref: "ai_office_command_bar",
          evidence: [{ source: "AI Office command bar", workspace: activeWorkspaceLabel }],
          metadata: { routed_agent: routed.agent }
        });
      } else {
        const handoff = await createAgentMessage({
          body: cleanCommand,
          from_agent: "Charlie Munger",
          metadata: {
            source_surface: "command_center",
            workspace: activeWorkspace
          },
          priority: routed.priority,
          subject: title,
          thread_key: `command-${Date.now()}`,
          to_agent: routed.agent
        });
        await triageAgentMessage({
          action: "create_task",
          actor: "Jarvis",
          message_id: asText(handoff, "id"),
          priority: routed.priority,
          recommended_action: routed.recommendedAction,
          target_workspace: activeWorkspace,
          task_objective: cleanCommand,
          task_title: title
        });
      }
      setLiveStatus("online");
      if (activeWorkspace === "command") {
        window.dispatchEvent(new Event("aios:mission-control-refresh"));
      } else if (activeWorkspace === "system") {
        window.dispatchEvent(new Event("aios:system-health-refresh"));
      } else if (["clients", "portfolio"].includes(activeWorkspace)) {
        window.dispatchEvent(new Event("aios:portfolio-office-refresh"));
      } else if (["ideas", "research"].includes(activeWorkspace)) {
        window.dispatchEvent(new Event("aios:research-ideas-refresh"));
      } else if (["quant", "risk", "trading"].includes(activeWorkspace)) {
        window.dispatchEvent(new Event("aios:trading-quant-risk-refresh"));
      } else if (activeWorkspace === "reports") {
        window.dispatchEvent(new Event("aios:reports-refresh"));
      } else {
        const nextSnapshot = await fetchLiveSnapshot();
        setSnapshot(nextSnapshot);
        setItems(liveInbox(nextSnapshot));
        setApprovalItems(liveApprovals(nextSnapshot));
        setManualUpdates(liveManualUpdates(nextSnapshot));
      }
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Command write failed");
      setLiveStatus("offline");
    } finally {
      setCommandBusy(false);
    }
  };

  const createAgentCommentFromDashboard = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const body = agentCommentDraft.body.trim();
    const defaultArtifact = dashboardOutputArtifacts[0];
    const targetRef = agentCommentDraft.targetRef.trim() || asText(defaultArtifact, "artifact_key");
    if (!body || !targetRef || agentCommentBusyId) {
      return;
    }
    setAgentCommentBusyId("create");
    setUiError("");
    try {
      await createAgentComment({
        actor: agentCommentDraft.fromAgent,
        body,
        comment_type: "review_note",
        evidence: [{ source: "AI Office dashboard", target_ref: targetRef }],
        from_agent: agentCommentDraft.fromAgent,
        metadata: { triggered_from: "agent_comments_panel" },
        severity: agentCommentDraft.severity,
        status: "open",
        target_kind: "output_artifact",
        target_ref: targetRef,
        target_title: asText(defaultArtifact, "title"),
        to_agent: agentCommentDraft.toAgent || undefined
      });
      setAgentCommentDraft((draft) => ({ ...draft, body: "", targetRef }));
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Agent comment create failed");
    } finally {
      setAgentCommentBusyId("");
    }
  };

  const resolveAgentCommentFromDashboard = async (comment: LiveRow, status: "acknowledged" | "resolved" | "dismissed" = "resolved") => {
    const commentId = asText(comment, "id");
    if (!commentId || agentCommentBusyId) {
      return;
    }
    setAgentCommentBusyId(`${commentId}:${status}`);
    setUiError("");
    try {
      await resolveAgentComment({
        actor: "Jarvis",
        comment_id: commentId,
        resolution_note: `Dashboard marked comment ${status}.`,
        status
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Agent comment update failed");
    } finally {
      setAgentCommentBusyId("");
    }
  };

  const runTradingViewChartAction = async (task: LiveRow) => {
    const taskId = asText(task, "id");
    if (!taskId || chartActionBusyId) {
      return;
    }
    setChartActionBusyId(taskId);
    setUiError("");
    try {
      await executeTradingViewChartAction({
        task_id: Number(taskId),
        actor: "Charlie Munger",
        symbols: asStringArray(task, "symbols"),
        exchange: asText(task, "exchange", "NSE"),
        timeframe: asText(task, "timeframe", "D"),
        chart_layout: asText(task, "chart_layout"),
        action: "open_chart_capture",
        wait_ms: 9000,
        metadata: { triggered_from: "ai_office_task_queue" }
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "TradingView chart action failed");
    } finally {
      setChartActionBusyId("");
    }
  };

  const runSymbolTradingViewTemplate = async (symbolRow: LiveRow, templateKey: string) => {
    const symbol = asText(symbolRow, "symbol");
    const clientCode = asText(symbolRow, "client_code");
    const busyKey = `${clientCode || "portfolio"}:${symbol}:${templateKey}`;
    if (!symbol || chartActionBusyId) {
      return;
    }
    setChartActionBusyId(busyKey);
    setUiError("");
    try {
      await executeTradingViewTemplateAction({
        template_key: templateKey,
        task_title: `${templateKey.replace(/_/g, " ")}: ${symbol}`,
        actor: "Charlie Munger",
        symbols: [symbol],
        exchange: asText(symbolRow, "exchange", "NSE"),
        timeframe: "D",
        instruction: `Run ${templateKey} from Symbol Intelligence for ${symbol}.`,
        source_ref: `symbol_intelligence:${clientCode || "portfolio"}:${symbol}`,
        metadata: {
          client_code: clientCode,
          client_name: asText(symbolRow, "client_name"),
          decision_readiness: asText(symbolRow, "decision_readiness"),
          recommended_next_action: asText(symbolRow, "recommended_next_action"),
          holding_thesis_id: asText(symbolRow, "holding_thesis_id"),
          triggered_from: "symbol_intelligence"
        }
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "TradingView template action failed");
    } finally {
      setChartActionBusyId("");
    }
  };

  const routeSymbolActionFromDashboard = async (symbolRow: LiveRow, actionType: string) => {
    const symbol = asText(symbolRow, "symbol");
    const clientCode = asText(symbolRow, "client_code");
    const busyKey = `${clientCode || "portfolio"}:${symbol}:${actionType}`;
    if (!symbol || symbolActionBusyId) {
      return;
    }
    setSymbolActionBusyId(busyKey);
    setUiError("");
    try {
      await routeSymbolIntelligenceAction({
        action_type: actionType,
        actor: "Charlie Munger",
        client_code: clientCode,
        exchange: asText(symbolRow, "exchange", "NSE"),
        notes: asText(symbolRow, "v2_recommended_next_action", asText(symbolRow, "recommended_next_action")),
        symbol
      });
      await refreshSnapshot();
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Symbol Intelligence action failed");
      setLiveStatus("offline");
    } finally {
      setSymbolActionBusyId("");
    }
  };

  const submitChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatDraft.trim();
    if (!message || chatBusy) {
      return;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      meta: activeWorkspaceLabel
    };
    setChatMessages((current) => [...current.slice(-5), userMessage]);
    setChatDraft("");
    setChatBusy(true);
    setUiError("");
    try {
      const response = await sendChat({
        actor: "Devarsh",
        message,
        metadata: { workspace: activeWorkspace },
        session_key: "ai-office-default",
        workspace: activeWorkspace
      });
      const assistantMessage: ChatMessage = {
        id: `assistant-${String(response.chat_turn.id ?? Date.now())}`,
        role: "assistant",
        content: response.message,
        meta: `${String(response.route.default_model ?? "local route")} · ${response.model_status}`
      };
      setChatMessages((current) => [...current.slice(-5), assistantMessage]);
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Charlie chat failed");
      setLiveStatus("offline");
    } finally {
      setChatBusy(false);
    }
  };

  const materializeWidgets = async () => {
    if (widgetBusy) {
      return;
    }
    setWidgetBusy(true);
    setUiError("");
    try {
      await materializeDashboardWidgets({
        actor: "Jarvis",
        limit: 50
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Widget materialization failed");
      setLiveStatus("offline");
    } finally {
      setWidgetBusy(false);
    }
  };

  const runAgentWorkers = async () => {
    if (agentWorkerBusy) {
      return;
    }
    setAgentWorkerBusy(true);
    setUiError("");
    try {
      await runAgentWorker({
        actor: "Jarvis",
        limit: 5
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Agent worker failed");
      setLiveStatus("offline");
    } finally {
      setAgentWorkerBusy(false);
    }
  };

  const handleInboxAction = async (
    item: InboxItem,
    action: "claim" | "reassign" | "resolve" | "block" | "reopen",
    ownerAgent?: string
  ) => {
    if (!item.id || inboxBusyId) {
      return;
    }
    setInboxBusyId(`${item.id}:${action}`);
    setUiError("");
    try {
      await updateInboxItem({
        action,
        actor: "Devarsh",
        inbox_id: item.id,
        owner_agent: ownerAgent,
        resolution_note:
          action === "resolve"
            ? "Resolved by Devarsh from the Command Center after reviewing the linked evidence."
            : action === "block"
              ? "Blocked by Devarsh pending missing evidence or dependency resolution."
              : undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Inbox update failed");
      setLiveStatus("offline");
    } finally {
      setInboxBusyId("");
    }
  };

  const syncPositionRemediationFromDashboard = async () => {
    if (positionRemediationBusy) {
      return;
    }
    setPositionRemediationBusy(true);
    setUiError("");
    try {
      await syncPositionReadinessRemediation({
        actor: "Portfolio Manager",
        create_tasks: true,
        limit: 200
      });
      await refreshSnapshot();
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Position remediation sync failed");
      setLiveStatus("offline");
    } finally {
      setPositionRemediationBusy(false);
    }
  };

  const handleRegisterModelEndpoint = async (row: LiveRow) => {
    const endpointKey = asText(row, "endpoint_key", asText(row, "route_name", "model_endpoint"));
    setModelEndpointBusyId(`register:${endpointKey}`);
    setUiError("");
    try {
      await registerModelEndpoint({
        endpoint_key: endpointKey,
        endpoint_name: asText(row, "endpoint_name", `${endpointKey} endpoint`),
        provider: asText(row, "provider", asText(row, "default_provider", "ollama")),
        model_name: asText(row, "model_name", asText(row, "default_model", "llama3.2:3b")),
        route_name: asText(row, "route_name"),
        endpoint_type: asText(row, "endpoint_type", "local"),
        base_url: asText(row, "base_url"),
        deployment_target: asText(row, "deployment_target", "local_machine"),
        status: "configured",
        cost_tier: asText(row, "cost_tier", asText(row, "max_cost_tier", "local")),
        owner_agent: asText(row, "owner_agent", "AI Engineering"),
        notes: asText(row, "notes", "Registered from AI Office endpoint control."),
        actor: "Jarvis"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Model endpoint registration failed");
      setLiveStatus("offline");
    } finally {
      setModelEndpointBusyId("");
    }
  };

  const handleCheckModelEndpoint = async (endpointKey: string) => {
    if (!endpointKey) {
      return;
    }
    setModelEndpointBusyId(`check:${endpointKey}`);
    setUiError("");
    try {
      await checkModelEndpoint({ endpoint_key: endpointKey, actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Model endpoint check failed");
      setLiveStatus("offline");
    } finally {
      setModelEndpointBusyId("");
    }
  };

  const handleRegisterSourceConnector = async (row: LiveRow) => {
    const connectorKey = asText(row, "connector_key", `${asText(row, "source_key", "source")}_connector`);
    setSourceConnectorBusyId(`register:${connectorKey}`);
    setUiError("");
    try {
      await registerSourceConnector({
        connector_key: connectorKey,
        connector_name: asText(row, "connector_name", `${connectorKey} connector`),
        source_key: asText(row, "source_key"),
        connector_type: asText(row, "connector_type", asText(row, "connection_mode", "custom_adapter")),
        provider: asText(row, "provider"),
        access_mode: asText(row, "access_mode", "read_only"),
        status: asText(row, "status", "configured") === "planned" ? "planned" : "configured",
        freshness_target_minutes: asText(row, "freshness_target_minutes"),
        requires_api_key: asText(row, "requires_api_key") === "true",
        requires_browser_session: asText(row, "requires_browser_session") === "true",
        base_url: asText(row, "base_url"),
        owner_agent: asText(row, "owner_agent", "Data Steward"),
        sensitivity: asText(row, "sensitivity", "private"),
        notes: asText(row, "notes", "Registered from AI Office connector control."),
        actor: "Jarvis"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Source connector registration failed");
      setLiveStatus("offline");
    } finally {
      setSourceConnectorBusyId("");
    }
  };

  const handleCheckSourceConnector = async (connectorKey: string) => {
    if (!connectorKey) {
      return;
    }
    setSourceConnectorBusyId(`check:${connectorKey}`);
    setUiError("");
    try {
      await checkSourceConnector({ connector_key: connectorKey, actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Source connector check failed");
      setLiveStatus("offline");
    } finally {
      setSourceConnectorBusyId("");
    }
  };

  const runProviderReadinessFromDashboard = async () => {
    if (providerReadinessBusy) {
      return;
    }
    setProviderReadinessBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await runProviderReadinessSweep({
        actor: "Jarvis",
        model_limit: 80,
        source_limit: 120,
        run_key: `provider_readiness_ui_${stamp}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Provider readiness sweep failed");
      setLiveStatus("offline");
    } finally {
      setProviderReadinessBusy(false);
    }
  };

  const evaluateProviderAssignmentFromDashboard = async (provider: LiveRow) => {
    const providerKey = asText(provider, "provider_key");
    const providerKind = asText(provider, "provider_kind");
    if (!providerKey || providerAssignmentBusyId) {
      return;
    }
    setProviderAssignmentBusyId(providerKey);
    setUiError("");
    try {
      await evaluateProviderAssignmentGate({
        provider_key: providerKey,
        provider_kind: providerKind,
        requesting_agent: asText(provider, "owner_agent", "Jarvis"),
        requested_use: "AI Office dashboard provider assignment check",
        source_kind: "ai_office_dashboard",
        source_ref: providerKey,
        target_workspace: "system",
        create_inbox_on_block: true,
        evidence: [{ source: "AI Office Provider Readiness Board", provider_key: providerKey, provider_kind: providerKind }],
        metadata: { ui_panel: "Provider Readiness Board" },
        actor: "Jarvis"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Provider assignment gate failed");
      setLiveStatus("offline");
    } finally {
      setProviderAssignmentBusyId("");
    }
  };

  const handleRegisterBrowserProfile = async (profile: LiveRow) => {
    const profileKey = asText(profile, "profile_key", "browser_profile");
    setBrowserProfileBusyId(`register:${profileKey}`);
    setUiError("");
    try {
      await registerBrowserProfile({
        profile_key: profileKey,
        profile_name: asText(profile, "profile_name", profileKey),
        browser_name: asText(profile, "browser_name", "chromium"),
        use_case: asText(profile, "use_case", "browser automation"),
        profile_path: asText(profile, "profile_path"),
        remote_debugging_host: asText(profile, "remote_debugging_host", "127.0.0.1"),
        remote_debugging_port: asText(profile, "remote_debugging_port"),
        target_base_url: asText(profile, "target_base_url"),
        status: asText(profile, "status", "configured"),
        owner_agent: asText(profile, "owner_agent", "Browser Research Runner"),
        sensitivity: asText(profile, "sensitivity", "private"),
        permission_level: asText(profile, "permission_level", "browser_read_capture"),
        notes: asText(profile, "notes", "Registered from AI Office browser profile control."),
        actor: "Jarvis"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Browser profile registration failed");
      setLiveStatus("offline");
    } finally {
      setBrowserProfileBusyId("");
    }
  };

  const handleCheckBrowserProfile = async (profileKey: string, connectorKey?: string) => {
    if (!profileKey) {
      return;
    }
    const busyKey = connectorKey ? `${profileKey}:${connectorKey}` : profileKey;
    setBrowserProfileBusyId(`check:${busyKey}`);
    setUiError("");
    try {
      await checkBrowserProfile({ profile_key: profileKey, connector_key: connectorKey, actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Browser profile check failed");
      setLiveStatus("offline");
    } finally {
      setBrowserProfileBusyId("");
    }
  };

  const handleAttachBrowserProfile = async (profileKey: string, connectorKey: string) => {
    if (!profileKey || !connectorKey) {
      return;
    }
    setBrowserProfileBusyId(`attach:${profileKey}:${connectorKey}`);
    setUiError("");
    try {
      await attachBrowserProfile({ profile_key: profileKey, connector_key: connectorKey, actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Browser profile attach failed");
      setLiveStatus("offline");
    } finally {
      setBrowserProfileBusyId("");
    }
  };

  const triageAgentMessageFromDashboard = async (message: LiveRow, action: "acknowledge" | "create_task") => {
    const messageId = asText(message, "id");
    if (!messageId) {
      return;
    }
    setAgentMessageBusyId(`${messageId}:${action}`);
    setUiError("");
    try {
      await triageAgentMessage({
        action,
        actor: "Jarvis",
        message_id: messageId,
        priority: asText(message, "priority", "normal") as "low" | "normal" | "medium" | "high" | "critical",
        recommended_action: "Review the agent handoff, gather evidence, and update the task before closing.",
        target_workspace: asText(message, "related_skill_key")?.includes("filing") ? "research" : "command",
        task_objective: asText(message, "body", "Review this agent handoff."),
        task_title: `Message handoff: ${asText(message, "subject", "Agent message")}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Agent message triage failed");
      setLiveStatus("offline");
    } finally {
      setAgentMessageBusyId("");
    }
  };

  const runFilingCollectorFromDashboard = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (filingCollectorBusy) {
      return;
    }
    setFilingCollectorBusy(true);
    setUiError("");
    try {
      await runFilingCollector({
        actor: "News Analyst",
        date_from: filingCollectorDraft.dateFrom,
        date_to: filingCollectorDraft.dateTo,
        limit: filingCollectorDraft.limit,
        source: filingCollectorDraft.source as "nse" | "bse" | "all"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Filing collector failed");
      setLiveStatus("offline");
    } finally {
      setFilingCollectorBusy(false);
    }
  };

  const runFilingPdfExtractorFromDashboard = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (filingExtractorBusy) {
      return;
    }
    setFilingExtractorBusy(true);
    setUiError("");
    try {
      await runFilingPdfExtractor({
        actor: "Filings Analyst",
        filing_id: filingExtractorDraft.filingId.trim() || undefined,
        force: filingExtractorDraft.force,
        limit: filingExtractorDraft.limit
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Filing PDF extraction failed");
      setLiveStatus("offline");
    } finally {
      setFilingExtractorBusy(false);
    }
  };

  const generateSpecialSituationMemoFromDashboard = async (specialTermsId: string) => {
    if (!specialTermsId || specialMemoBusyId) {
      return;
    }
    setSpecialMemoBusyId(specialTermsId);
    setUiError("");
    try {
      await generateSpecialSituationMemo({
        actor: "Special Situations Agent",
        special_terms_id: specialTermsId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Special situation memo generation failed");
      setLiveStatus("offline");
    } finally {
      setSpecialMemoBusyId("");
    }
  };

  const calculateSpecialSituationSpreadFromDashboard = async (specialMemoId: string) => {
    if (!specialMemoId || specialSpreadBusyId) {
      return;
    }
    setSpecialSpreadBusyId(specialMemoId);
    setUiError("");
    try {
      await calculateSpecialSituationSpread({
        actor: "Event Arbitrage Analyst",
        special_memo_id: specialMemoId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Special situation spread check failed");
      setLiveStatus("offline");
    } finally {
      setSpecialSpreadBusyId("");
    }
  };

  const refreshEventQuotesFromDashboard = async () => {
    if (eventQuoteBusy) {
      return;
    }
    setEventQuoteBusy(true);
    setUiError("");
    try {
      await refreshEventQuotes({
        actor: "Data Steward",
        limit: 50
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Event quote refresh failed");
      setLiveStatus("offline");
    } finally {
      setEventQuoteBusy(false);
    }
  };

  const checkSourceFreshnessFromDashboard = async () => {
    if (sourceFreshnessBusy) {
      return;
    }
    setSourceFreshnessBusy(true);
    setUiError("");
    try {
      await checkSourceFreshness({
        actor: "Data Steward",
        limit: 100
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Source freshness check failed");
      setLiveStatus("offline");
    } finally {
      setSourceFreshnessBusy(false);
    }
  };

  const generateLongTermThesisFromDashboard = async () => {
    if (longTermThesisBusy) {
      return;
    }
    setLongTermThesisBusy(true);
    setUiError("");
    try {
      await generateLongTermThesisMemo({
        actor: "Long-Term Portfolio Manager",
        exchange: longTermThesisDraft.exchange.trim() || undefined,
        symbol: longTermThesisDraft.symbol.trim().toUpperCase() || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term thesis memo generation failed");
      setLiveStatus("offline");
    } finally {
      setLongTermThesisBusy(false);
    }
  };

  const syncLongTermCoverageFromDashboard = async () => {
    if (longTermCoverageBusy) {
      return;
    }
    setLongTermCoverageBusy(true);
    setUiError("");
    try {
      await syncLongTermCoverage({
        actor: "Long-Term Portfolio Manager",
        create_tasks: true,
        limit: 120
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term coverage sync failed");
      setLiveStatus("offline");
    } finally {
      setLongTermCoverageBusy(false);
    }
  };

  const generateLongTermThesisFromCoverage = async (coverage: LiveRow) => {
    const coverageKey = asText(coverage, "coverage_key", "");
    const symbol = asText(coverage, "symbol", "").toUpperCase();
    if (!coverageKey || !symbol || longTermCoverageMemoBusyKey) {
      return;
    }
    setLongTermCoverageMemoBusyKey(coverageKey);
    setUiError("");
    try {
      await generateLongTermThesisMemo({
        actor: "Long-Term Portfolio Manager",
        exchange: asText(coverage, "exchange", "NSE"),
        symbol
      });
      await syncLongTermCoverage({
        actor: "Long-Term Portfolio Manager",
        create_tasks: true,
        limit: 120
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term thesis memo generation failed");
      setLiveStatus("offline");
    } finally {
      setLongTermCoverageMemoBusyKey("");
    }
  };

  const generateLongTermResearchPacketFromDashboard = async (thesis: LiveRow) => {
    const thesisId = asText(thesis, "id", "");
    if (!thesisId || longTermPacketBusyId) {
      return;
    }
    setLongTermPacketBusyId(thesisId);
    setUiError("");
    try {
      await generateLongTermResearchPacket({
        actor: "Long-Term Portfolio Manager",
        holding_thesis_id: thesisId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term research packet generation failed");
      setLiveStatus("offline");
    } finally {
      setLongTermPacketBusyId("");
    }
  };

  const openLongTermCommitteeFromDashboard = async (thesis: LiveRow) => {
    const thesisId = asText(thesis, "id", "");
    if (!thesisId || longTermCommitteeBusyId) {
      return;
    }
    setLongTermCommitteeBusyId(thesisId);
    setUiError("");
    try {
      await openLongTermCommitteeReview({
        actor: "Long-Term Portfolio Manager",
        holding_thesis_id: thesisId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term committee review failed");
      setLiveStatus("offline");
    } finally {
      setLongTermCommitteeBusyId("");
    }
  };

  const generateLongTermCommitteeMemoFromDashboard = async (review: LiveRow) => {
    const reviewId = asText(review, "id", "");
    if (!reviewId || longTermCommitteeMemoBusyId) {
      return;
    }
    setLongTermCommitteeMemoBusyId(reviewId);
    setUiError("");
    try {
      await generateLongTermCommitteeMemo({
        actor: "Long-Term Portfolio Manager",
        long_term_committee_review_id: reviewId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term committee memo failed");
      setLiveStatus("offline");
    } finally {
      setLongTermCommitteeMemoBusyId("");
    }
  };

  const resolveLongTermCommitteeFromDashboard = async (
    review: LiveRow,
    decision: "reject" | "research_more" | "monitor" | "approve_watchlist" | "approve_hold"
  ) => {
    const reviewId = asText(review, "id", "");
    const busyKey = `${reviewId}:${decision}`;
    if (!reviewId || longTermCommitteeDecisionBusyId) {
      return;
    }
    setLongTermCommitteeDecisionBusyId(busyKey);
    setUiError("");
    try {
      await resolveLongTermCommitteeDecision({
        actor: "Charlie Munger",
        decision,
        decision_notes: `Dashboard Long-Term committee decision: ${decision}. Capital action remains disabled.`,
        long_term_committee_review_id: reviewId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term committee decision failed");
      setLiveStatus("offline");
    } finally {
      setLongTermCommitteeDecisionBusyId("");
    }
  };

  const dispatchLongTermSpecialistsFromDashboard = async (record: LiveRow) => {
    const reviewId = asText(record, "id", "");
    const thesisId = asText(record, "holding_thesis_id", "") || asText(record, "id", "");
    const busyId = reviewId || thesisId;
    if (!busyId || longTermSpecialistBusyId) {
      return;
    }
    setLongTermSpecialistBusyId(busyId);
    setUiError("");
    try {
      await dispatchLongTermSpecialists({
        actor: "Long-Term Portfolio Manager",
        long_term_committee_review_id: asText(record, "review_key", "") ? reviewId : undefined,
        holding_thesis_id: asText(record, "review_key", "") ? undefined : thesisId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term specialist dispatch failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSpecialistBusyId("");
    }
  };

  const executeLongTermSpecialistFromDashboard = async (assignment: LiveRow) => {
    const assignmentId = asText(assignment, "id", "");
    if (!assignmentId || longTermSpecialistExecuteBusyId) {
      return;
    }
    setLongTermSpecialistExecuteBusyId(assignmentId);
    setUiError("");
    try {
      await executeLongTermSpecialist({
        actor: asText(assignment, "agent_name", "Jarvis"),
        assignment_id: assignmentId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term specialist execution failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSpecialistExecuteBusyId("");
    }
  };

  const createLongTermSourceRequestsFromDashboard = async (record: LiveRow) => {
    const outputId = asText(record, "id", "");
    const assignmentId = asText(record, "assignment_id", "");
    const thesisId = asText(record, "holding_thesis_id", "");
    const busyId = outputId || assignmentId || thesisId;
    if (!busyId || longTermSourceRequestBusyId) {
      return;
    }
    setLongTermSourceRequestBusyId(busyId);
    setUiError("");
    try {
      await createLongTermSourceRequests({
        actor: "Filings and Transcript Analyst",
        specialist_output_id: outputId || undefined,
        assignment_id: outputId ? undefined : assignmentId || undefined,
        holding_thesis_id: outputId || assignmentId ? undefined : thesisId || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term source request creation failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSourceRequestBusyId("");
    }
  };

  const checkLongTermSourceRequestFromDashboard = async (request: LiveRow) => {
    const requestId = asText(request, "id", "");
    if (!requestId || longTermSourceCheckBusyId) {
      return;
    }
    setLongTermSourceCheckBusyId(requestId);
    setUiError("");
    try {
      await checkLongTermSourceRequests({
        actor: "Filings and Transcript Analyst",
        source_request_id: requestId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term source satisfaction check failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSourceCheckBusyId("");
    }
  };

  const submitLongTermSourceDocument = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!sourceDocumentDraft.sourceRequestId || !sourceDocumentDraft.title.trim() || !sourceDocumentDraft.sourceUrl.trim()) {
      setUiError("Source request, title, and official URL are required.");
      return;
    }
    setLongTermSourceDocumentBusy(true);
    setUiError("");
    try {
      await registerLongTermSourceDocument({
        actor: "Filings and Transcript Analyst",
        document_type: sourceDocumentDraft.documentType,
        source_name: "official_company_ir",
        source_request_id: sourceDocumentDraft.sourceRequestId,
        source_url: sourceDocumentDraft.sourceUrl.trim(),
        title: sourceDocumentDraft.title.trim()
      });
      await checkLongTermSourceRequests({
        actor: "Filings and Transcript Analyst",
        source_request_id: sourceDocumentDraft.sourceRequestId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setSourceDocumentDraft({ documentType: "annual_report", sourceRequestId: "", sourceUrl: "", title: "" });
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term source document registration failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSourceDocumentBusy(false);
    }
  };

  const extractLongTermSourceDocumentFromDashboard = async (document: LiveRow) => {
    const documentId = asText(document, "id", "");
    if (!documentId || longTermSourceExtractBusyId) {
      return;
    }
    setLongTermSourceExtractBusyId(documentId);
    setUiError("");
    try {
      await extractLongTermSourceDocument({
        actor: "Filings and Transcript Analyst",
        source_document_id: documentId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Long-term source document extraction failed");
      setLiveStatus("offline");
    } finally {
      setLongTermSourceExtractBusyId("");
    }
  };

  const decideSpecialSituationFromDashboard = async (
    specialMemoId: string,
    decision: "reject" | "monitor" | "research_more" | "committee_review"
  ) => {
    if (!specialMemoId || specialDecisionBusyId) {
      return;
    }
    setSpecialDecisionBusyId(`${specialMemoId}:${decision}`);
    setUiError("");
    try {
      await resolveSpecialSituationDecision({
        actor: "Charlie Munger",
        decision,
        decision_notes: "Dashboard decision. Trade and client recommendation remain disabled.",
        special_memo_id: specialMemoId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Special situation decision failed");
      setLiveStatus("offline");
    } finally {
      setSpecialDecisionBusyId("");
    }
  };

  const handleResolveApproval = async (id: string, status: "approved" | "rejected") => {
    setUiError("");
    try {
      await resolveApproval({ approval_id: id, status, decided_by: "Devarsh" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setApprovalItems(liveApprovals(nextSnapshot));
      setItems(liveInbox(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Approval update failed");
      setLiveStatus("offline");
    }
  };

  const handleResolveTradingViewAlert = async (approvalId: string, status: "approved" | "rejected") => {
    if (!approvalId || tradingViewAlertBusyId) {
      return;
    }
    setTradingViewAlertBusyId(`${approvalId}:${status}`);
    setUiError("");
    try {
      await resolveTradingViewAlertRequest({
        approval_id: approvalId,
        status,
        decided_by: "Devarsh",
        decision_note: status === "approved" ? "Approved for manual TradingView alert creation." : "Rejected from AI Office alert inbox."
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setApprovalItems(liveApprovals(nextSnapshot));
      setItems(liveInbox(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "TradingView alert request update failed");
      setLiveStatus("offline");
    } finally {
      setTradingViewAlertBusyId("");
    }
  };

  const stageManualHolding = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const clientCode = holdingDraft.clientCode.trim();
    const accountCode = holdingDraft.accountCode.trim();
    const symbol = holdingDraft.symbol.trim().toUpperCase();
    const quantity = holdingDraft.quantity.trim();

    if (!clientCode || !accountCode || !symbol || !quantity) {
      return;
    }

    setHoldingBusy(true);
    setUiError("");
    try {
      await stageHoldingUpdate({
        account_code: accountCode,
        client_code: clientCode,
        quantity,
        symbol,
        actor: "Devarsh"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setItems(liveInbox(nextSnapshot));
      setLiveStatus("online");
      setHoldingDraft({ accountCode: "", clientCode: "", quantity: "", symbol: "" });
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Holding update write failed");
      setLiveStatus("offline");
    } finally {
      setHoldingBusy(false);
    }
  };

  const submitBookAssignment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!bookAssignmentDraft.bookPositionId || !bookAssignmentDraft.bookKey || !bookAssignmentDraft.purposeKey || bookAssignmentBusy) {
      return;
    }
    setBookAssignmentBusy(true);
    setUiError("");
    try {
      await updateBookAssignment({
        actor: "Devarsh",
        book_key: bookAssignmentDraft.bookKey,
        book_position_id: bookAssignmentDraft.bookPositionId,
        exit_criteria: bookAssignmentDraft.exitCriteria,
        purpose_key: bookAssignmentDraft.purposeKey,
        rationale: "AI Office manual book assignment edit",
        thesis: bookAssignmentDraft.thesis
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Book assignment update failed");
      setLiveStatus("offline");
    } finally {
      setBookAssignmentBusy(false);
    }
  };

  const submitTradeTicket = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const symbol = tradeDraft.symbol.trim().toUpperCase();
    if (!symbol || !tradeDraft.side || tradeTicketBusy) {
      return;
    }
    setTradeTicketBusy(true);
    setUiError("");
    try {
      const payload = {
        account_code: tradeDraft.accountCode.trim() || undefined,
        actor: "Devarsh",
        book_key: tradeDraft.bookKey,
        client_code: tradeDraft.clientCode.trim() || undefined,
        price: tradeDraft.price.trim() || undefined,
        purpose_key: tradeDraft.purposeKey,
        quantity: tradeDraft.quantity.trim() || undefined,
        setup_type: tradeDraft.purposeKey.replace(/_/g, " "),
        side: tradeDraft.side,
        stop_loss: tradeDraft.stopLoss.trim() || undefined,
        symbol,
        target_price: tradeDraft.targetPrice.trim() || undefined,
        thesis: tradeDraft.thesis.trim() || undefined,
        timeframe: tradeDraft.bookKey === "active_trading" ? "intraday_to_days" : "days_to_weeks"
      };
      if (tradeDraft.mode === "manual") {
        await recordManualTrade(payload);
      } else {
        await recordPaperTrade(payload);
      }
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setManualUpdates(liveManualUpdates(nextSnapshot));
      setLiveStatus("online");
      setTradeDraft((current) => ({ ...current, price: "", quantity: "", stopLoss: "", symbol: "", targetPrice: "", thesis: "" }));
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Trade ticket write failed");
      setLiveStatus("offline");
    } finally {
      setTradeTicketBusy(false);
    }
  };

  const submitStrategyIntake = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const intakeText = strategyDraft.intakeText.trim();
    if (!intakeText || strategyIntakeBusy) {
      return;
    }
    setStrategyIntakeBusy(true);
    setUiError("");
    try {
      await createStrategyIntake({
        actor: "Devarsh",
        asset_class: strategyDraft.assetClass,
        constraints_text: strategyDraft.constraintsText.trim() || undefined,
        intake_text: intakeText,
        intent_tags: ["user_defined", strategyDraft.family],
        risk_notes: strategyDraft.riskNotes.trim() || undefined,
        strategy_family: strategyDraft.family,
        strategy_name: strategyDraft.name.trim() || undefined,
        symbols: strategyDraft.symbols
          .split(",")
          .map((symbol) => symbol.trim().toUpperCase())
          .filter(Boolean),
        timeframe: strategyDraft.timeframe,
        universe: strategyDraft.universe.trim() || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
      setStrategyDraft((current) => ({ ...current, constraintsText: "", intakeText: "", name: "", riskNotes: "", symbols: "" }));
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy intake write failed");
      setLiveStatus("offline");
    } finally {
      setStrategyIntakeBusy(false);
    }
  };

  const runUserDefinedOptimizerFromDraft = async () => {
    const intakeText = strategyDraft.intakeText.trim();
    if (!intakeText || userStrategyOptimizerBusy) {
      return;
    }
    setUserStrategyOptimizerBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      const symbols = strategyDraft.symbols
        .split(",")
        .map((symbol) => symbol.trim().toUpperCase())
        .filter(Boolean);
      await runUserDefinedStrategyOptimizer({
        actor: "Devarsh",
        asset_class: strategyDraft.assetClass,
        constraints_text: strategyDraft.constraintsText.trim() || undefined,
        intake_text: intakeText,
        max_symbols: 14,
        min_rows_per_symbol: 50,
        risk_notes: strategyDraft.riskNotes.trim() || undefined,
        run_key: `useropt_ui_${stamp}`,
        strategy_name: strategyDraft.name.trim() || `User strategy ${stamp}`,
        symbols,
        template: strategyDraft.template as "momentum" | "mean_reversion" | "breakout" | "low_volatility",
        timeframe: strategyDraft.timeframe === "intraday_to_days" ? "5m" : strategyDraft.timeframe,
        universe: strategyDraft.universe.trim() || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
      setStrategyDraft((current) => ({ ...current, constraintsText: "", intakeText: "", name: "", riskNotes: "", symbols: "" }));
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "User-defined strategy optimization failed");
      setLiveStatus("offline");
    } finally {
      setUserStrategyOptimizerBusy(false);
    }
  };

  const queueStrategyTemplateFromDashboard = async (template: LiveRow) => {
    const templateKey = asText(template, "template_key");
    if (!templateKey || strategyTemplateBusyKey) {
      return;
    }
    setStrategyTemplateBusyKey(templateKey);
    setUiError("");
    try {
      await applyStrategyTemplate({
        actor: "Charlie Munger",
        notes: "Queued from AI Office strategy template library. Keep paper-first gates and no live execution.",
        strategy_name: `${asText(template, "template_name", "Strategy template")} - office queue`,
        symbols: asStringArray(template, "default_symbols"),
        template_key: templateKey,
        timeframe: asText(template, "default_timeframe") || undefined,
        universe: asText(template, "default_universe") || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy template queue failed");
      setLiveStatus("offline");
    } finally {
      setStrategyTemplateBusyKey("");
    }
  };

  const runStrategyDiscoveryFromDashboard = async () => {
    if (strategyDiscoveryBusy) {
      return;
    }
    setStrategyDiscoveryBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await runStrategyDiscovery({
        actor: "Strategy Discovery Agent",
        run_key: `discovery_ui_${stamp}`,
        sources: "research,journals,signals,components",
        per_source_limit: 5,
        max_candidates: 10,
        route_top: 2
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy discovery failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDiscoveryBusy(false);
    }
  };

  const ingestMarketNewsFromDashboard = async () => {
    if (newsIngestionBusy) {
      return;
    }
    setNewsIngestionBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await ingestMarketNews({
        actor: "News Analyst",
        run_key: `news_ui_${stamp}`,
        feed_limit: 8,
        per_feed: 6,
        timeout: 12
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Market news ingestion failed");
      setLiveStatus("offline");
    } finally {
      setNewsIngestionBusy(false);
    }
  };

  const runStrategyDiscoverySchedulerFromDashboard = async () => {
    if (strategyDiscoverySchedulerBusy) {
      return;
    }
    setStrategyDiscoverySchedulerBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await runStrategyDiscoveryScheduler({
        actor: "Strategy Discovery Agent",
        run_key: `discovery_scheduler_ui_${stamp}`,
        interval_seconds: 3600,
        sources: "research,journals,signals,components",
        per_source_limit: 6,
        max_candidates: 12,
        route_top: 1,
        news_feed_limit: 8,
        news_per_feed: 5,
        enable_filings: false
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy discovery scheduler failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDiscoverySchedulerBusy(false);
    }
  };

  const resolveDiscoveryTriageFromDashboard = async (
    row: LiveRow,
    decision: "reject" | "request_more_evidence" | "route_quant_lab" | "route_special_situation" | "open_committee_review"
  ) => {
    const candidateId = asText(row, "id");
    if (!candidateId || strategyTriageBusyId) {
      return;
    }
    setStrategyTriageBusyId(`${candidateId}:${decision}`);
    setUiError("");
    try {
      await resolveStrategyDiscoveryTriage({
        actor: "Charlie Munger",
        decision,
        discovery_candidate_id: candidateId,
        notes: `Dashboard triage decision ${decision} for ${asText(row, "title", "discovered strategy")}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy discovery triage failed");
      setLiveStatus("offline");
    } finally {
      setStrategyTriageBusyId("");
    }
  };

  const buildStrategyDossiersFromDashboard = async () => {
    if (strategyDossierBusy) {
      return;
    }
    setStrategyDossierBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await buildStrategyIdeaDossiers({
        actor: "Strategy Dossier Agent",
        limit: 250,
        max_dossiers: 100,
        run_key: `dossier_ui_${stamp}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy dossier build failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDossierBusy(false);
    }
  };

  const searchStrategyDossiersFromDashboard = async () => {
    const query = strategyDossierSearchQuery.trim();
    if (strategyDossierSearchBusy || !query) {
      return;
    }
    setStrategyDossierSearchBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      const result = await searchStrategyIdeaDossiers({
        actor: "Strategy Dossier Search Agent",
        limit: 6,
        query,
        run_key: `dossier_search_ui_${stamp}`
      });
      const rows = Array.isArray(result.results) ? result.results : [];
      setStrategyDossierSearchResults(rows.filter((row): row is LiveRow => typeof row === "object" && row !== null));
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy dossier search failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDossierSearchBusy(false);
    }
  };

  const runDossierActionFromDashboard = async (
    row: LiveRow,
    action: "request_more_evidence" | "route_quant_lab" | "route_special_situation" | "open_committee_review" | "generate_committee_memo"
  ) => {
    const dossierId = asText(row, "id") || asText(row, "dossier_id");
    const busyKey = `${dossierId}:${action}`;
    if (!dossierId || strategyDossierActionBusyId) {
      return;
    }
    setStrategyDossierActionBusyId(busyKey);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await runStrategyDossierAction({
        action,
        actor: "Charlie Munger",
        dossier_id: dossierId,
        notes: `Dashboard action from dossier ${asText(row, "dossier_key", dossierId)}`,
        run_key: `dossier_action_ui_${action}_${stamp}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy dossier action failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDossierActionBusyId("");
    }
  };

  const parseCandidateDsl = async (candidate: LiveRow) => {
    const candidateId = asText(candidate, "candidate_id");
    if (!candidateId || strategyDslBusyId) {
      return;
    }
    setStrategyDslBusyId(candidateId);
    setUiError("");
    try {
      await parseStrategyDsl({
        actor: "Strategy Intake Agent",
        candidate_id: candidateId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy DSL parse failed");
      setLiveStatus("offline");
    } finally {
      setStrategyDslBusyId("");
    }
  };

  const checkCandidateDataQuality = async (candidate: LiveRow) => {
    const candidateId = asText(candidate, "candidate_id");
    if (!candidateId || dataQualityBusyId) {
      return;
    }
    setDataQualityBusyId(candidateId);
    setUiError("");
    try {
      await checkStrategyDataQuality({
        actor: "Backtest Engineer",
        candidate_id: candidateId,
        timeframe: asText(candidate, "timeframe") || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy data-quality gate failed");
      setLiveStatus("offline");
    } finally {
      setDataQualityBusyId("");
    }
  };

  const runCandidateBacktest = async (candidate: LiveRow) => {
    const candidateId = asText(candidate, "candidate_id");
    if (!candidateId || backtestBusyId) {
      return;
    }
    setBacktestBusyId(candidateId);
    setUiError("");
    try {
      await runStrategyBacktest({
        actor: "Backtest Engineer",
        candidate_id: candidateId,
        max_symbols: 14,
        timeframe: asText(candidate, "timeframe") || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy backtest failed");
      setLiveStatus("offline");
    } finally {
      setBacktestBusyId("");
    }
  };

  const runCandidateOptimization = async (candidate: LiveRow) => {
    const candidateId = asText(candidate, "candidate_id");
    if (!candidateId || optimizeBusyId) {
      return;
    }
    setOptimizeBusyId(candidateId);
    setUiError("");
    try {
      await runStrategyOptimization({
        actor: "Optimizer Agent",
        candidate_id: candidateId,
        max_symbols: 14,
        timeframe: asText(candidate, "timeframe") || undefined
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy optimization failed");
      setLiveStatus("offline");
    } finally {
      setOptimizeBusyId("");
    }
  };

  const runQuantAnalyticsFromDashboard = async () => {
    if (quantAnalyticsBusy) {
      return;
    }
    setQuantAnalyticsBusy(true);
    setUiError("");
    try {
      await runStrategyQuantAnalytics({
        actor: "Quant Analytics Agent",
        timeframe: "5m",
        limit: 10,
        max_symbols: 14,
        cost_bps: 3,
        slippage_bps: 2,
        participation_rate: 0.05
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy quant analytics failed");
      setLiveStatus("offline");
    } finally {
      setQuantAnalyticsBusy(false);
    }
  };

  const runStrategyAllocationFromDashboard = async () => {
    if (strategyAllocationBusy) {
      return;
    }
    setStrategyAllocationBusy(true);
    setUiError("");
    try {
      await runStrategyPortfolioAllocation({
        actor: "Strategy Portfolio Manager",
        capital_base: 1000000,
        max_weight: 0.35,
        ruin_threshold_pct: 0.2,
        horizon_bars: 252,
        simulation_count: 1000,
        seed: 260706
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy allocation failed");
      setLiveStatus("offline");
    } finally {
      setStrategyAllocationBusy(false);
    }
  };

  const runStrategyRetirementFromDashboard = async () => {
    if (strategyRetirementBusy) {
      return;
    }
    setStrategyRetirementBusy(true);
    setUiError("");
    try {
      await runStrategyRetirementReview({
        actor: "Strategy Retirement Agent",
        review_key_prefix: "retire_ui"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Strategy retirement review failed");
      setLiveStatus("offline");
    } finally {
      setStrategyRetirementBusy(false);
    }
  };

  const runModelValidationFromDashboard = async () => {
    if (modelValidationBusy) {
      return;
    }
    setModelValidationBusy(true);
    setUiError("");
    try {
      await runModelValidationSweep({
        actor: "Model Validation Agent",
        validation_key_prefix: "modelval_ui",
        limit: 25
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Model validation sweep failed");
      setLiveStatus("offline");
    } finally {
      setModelValidationBusy(false);
    }
  };

  const runTradeJournalMiningFromDashboard = async () => {
    if (tradeJournalMiningBusy) {
      return;
    }
    setTradeJournalMiningBusy(true);
    setUiError("");
    try {
      const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
      await runTradeJournalStrategyMining({
        actor: "Strategy Generator",
        run_key: `journal_ui_${stamp}`,
        min_trades: 1,
        max_patterns: 10,
        allow_thin_sample: true
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Trade journal strategy mining failed");
      setLiveStatus("offline");
    } finally {
      setTradeJournalMiningBusy(false);
    }
  };

  const openCommitteeReview = async (optimization: LiveRow) => {
    const optimizationId = asText(optimization, "id");
    if (!optimizationId || committeeBusyId) {
      return;
    }
    setCommitteeBusyId(optimizationId);
    setUiError("");
    try {
      await openStrategyCommitteeReview({
        actor: "Strategy Committee Secretary",
        optimization_run_id: optimizationId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Committee review creation failed");
      setLiveStatus("offline");
    } finally {
      setCommitteeBusyId("");
    }
  };

  const generateCommitteeMemo = async (review: LiveRow) => {
    const reviewId = asText(review, "id");
    if (!reviewId || memoBusyId) {
      return;
    }
    setMemoBusyId(reviewId);
    setUiError("");
    try {
      await generateStrategyCommitteeMemo({
        actor: "Strategy Committee Secretary",
        committee_review_id: reviewId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Committee memo generation failed");
      setLiveStatus("offline");
    } finally {
      setMemoBusyId("");
    }
  };

  const decideCommitteeReview = async (
    review: LiveRow,
    decision: "reject" | "retest" | "research_more" | "approve_paper_monitor"
  ) => {
    const reviewId = asText(review, "id");
    const busyKey = `${reviewId}:${decision}`;
    if (!reviewId || committeeDecisionBusyId) {
      return;
    }
    setCommitteeDecisionBusyId(busyKey);
    setUiError("");
    try {
      await resolveStrategyCommitteeDecision({
        actor: "Devarsh",
        committee_review_id: reviewId,
        decision,
        decision_notes: `Dashboard committee decision: ${decision}. Live execution remains disabled.`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Committee decision failed");
      setLiveStatus("offline");
    } finally {
      setCommitteeDecisionBusyId("");
    }
  };

  const startPaperMonitor = async (review: LiveRow) => {
    const reviewId = asText(review, "id");
    const busyKey = `start:${reviewId}`;
    if (!reviewId || paperMonitorBusyId) {
      return;
    }
    setPaperMonitorBusyId(busyKey);
    setUiError("");
    try {
      await startStrategyPaperMonitor({
        actor: "Trading Desk Agent",
        committee_review_id: reviewId,
        notes: "Dashboard start. Paper monitoring only; live execution remains disabled."
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Paper monitor start failed");
      setLiveStatus("offline");
    } finally {
      setPaperMonitorBusyId("");
    }
  };

  const heartbeatPaperMonitor = async (session: LiveRow) => {
    const sessionId = asText(session, "id");
    const busyKey = `heartbeat:${sessionId}`;
    if (!sessionId || paperMonitorBusyId) {
      return;
    }
    setPaperMonitorBusyId(busyKey);
    setUiError("");
    try {
      await recordPaperMonitorHeartbeat({
        actor: "Trading Desk Agent",
        heartbeat_status: "ok",
        metrics: { live_execution_allowed: false, source: "dashboard_manual_heartbeat" },
        paper_monitor_session_id: sessionId,
        payload: { source: "ai_office_dashboard" },
        signal_count: 0
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Paper monitor heartbeat failed");
      setLiveStatus("offline");
    } finally {
      setPaperMonitorBusyId("");
    }
  };

  const stopPaperMonitor = async (session: LiveRow) => {
    const sessionId = asText(session, "id");
    const busyKey = `stop:${sessionId}`;
    if (!sessionId || paperMonitorBusyId) {
      return;
    }
    setPaperMonitorBusyId(busyKey);
    setUiError("");
    try {
      await stopStrategyPaperMonitor({
        actor: "Trading Desk Agent",
        paper_monitor_session_id: sessionId,
        reason: "dashboard_manual_stop"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Paper monitor stop failed");
      setLiveStatus("offline");
    } finally {
      setPaperMonitorBusyId("");
    }
  };

  const evaluatePaperDrift = async (session: LiveRow) => {
    const sessionId = asText(session, "id");
    if (!sessionId || driftBusyId) {
      return;
    }
    setDriftBusyId(sessionId);
    setUiError("");
    try {
      await evaluateStrategyDrift({
        actor: "Model Validation Agent",
        paper_monitor_session_id: sessionId,
        thresholds: {
          min_heartbeats: 1,
          return_warn_delta: -0.03,
          sharpe_warn_delta: -1.0
        }
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Drift evaluation failed");
      setLiveStatus("offline");
    } finally {
      setDriftBusyId("");
    }
  };

  const enforceKillSwitchFromSession = async (session: LiveRow) => {
    const sessionId = asText(session, "id");
    const busyKey = `session:${sessionId}`;
    if (!sessionId || killSwitchBusyId) {
      return;
    }
    setKillSwitchBusyId(busyKey);
    setUiError("");
    try {
      await enforceStrategyKillSwitch({
        actor: "Risk Agent",
        paper_monitor_session_id: sessionId,
        trigger_reason: "dashboard_manual_kill_switch"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Kill switch enforcement failed");
      setLiveStatus("offline");
    } finally {
      setKillSwitchBusyId("");
    }
  };

  const enforceKillSwitchFromDrift = async (check: LiveRow) => {
    const checkId = asText(check, "id");
    const sessionId = asText(check, "paper_monitor_session_id");
    const busyKey = `drift:${checkId}`;
    if (!checkId || killSwitchBusyId) {
      return;
    }
    setKillSwitchBusyId(busyKey);
    setUiError("");
    try {
      await enforceStrategyKillSwitch({
        actor: "Risk Agent",
        drift_check_id: checkId,
        paper_monitor_session_id: sessionId || undefined,
        trigger_reason: `dashboard_drift_${asText(check, "drift_level", "warning")}`
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Drift kill switch failed");
      setLiveStatus("offline");
    } finally {
      setKillSwitchBusyId("");
    }
  };

  const requestLimitedLiveFromSession = async (session: LiveRow) => {
    const sessionId = asText(session, "id");
    const busyKey = `request:${sessionId}`;
    if (!sessionId || executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId(busyKey);
    setUiError("");
    try {
      await requestLimitedLiveApproval({
        actor: "Devarsh",
        instance_id: asText(session, "instance_id"),
        max_daily_loss: 5000,
        max_notional: 25000,
        max_orders_per_day: 1,
        rationale: "Dashboard limited-live review request from paper monitor. This does not enable broker writes.",
        strategy_id: asText(session, "strategy_id"),
        symbol: asText(session, "symbol")
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Limited-live request failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const refreshPortfolioRiskEventsFromDashboard = async () => {
    if (riskRefreshBusy) {
      return;
    }
    setRiskRefreshBusy(true);
    setUiError("");
    try {
      await refreshPortfolioRiskEvents({ actor: "Risk Agent" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Portfolio risk event refresh failed");
      setLiveStatus("offline");
    } finally {
      setRiskRefreshBusy(false);
    }
  };

  const engageGlobalKillSwitchFromDashboard = async () => {
    if (executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId("global-kill");
    setUiError("");
    try {
      await engageGlobalKillSwitch({
        actor: "Execution Safety Agent",
        trigger_reason: "dashboard_global_kill_switch",
        trigger_source: "ai_office_dashboard"
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Global kill switch failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const syncLimitedLiveFromDashboard = async (request: LiveRow) => {
    const requestId = asText(request, "id");
    const busyKey = `sync:${requestId}`;
    if (!requestId || executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId(busyKey);
    setUiError("");
    try {
      await syncLimitedLiveRequest({
        actor: "Execution Safety Agent",
        limited_live_request_id: requestId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Limited-live sync failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const evaluateGateFromDashboard = async (request: LiveRow) => {
    const requestId = asText(request, "id");
    const busyKey = `gate:${requestId}`;
    if (!requestId || executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId(busyKey);
    setUiError("");
    try {
      await evaluateExecutionGate({
        actor: "Execution Safety Agent",
        limited_live_request_id: requestId,
        order_intent: {
          notional: 10000,
          source: "dashboard_gate_probe",
          symbol: asText(request, "symbol")
        }
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Execution gate check failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const createOrderIntentFromDashboard = async (request: LiveRow) => {
    const requestId = asText(request, "id");
    const busyKey = `order:${requestId}`;
    if (!requestId || executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId(busyKey);
    setUiError("");
    try {
      await createOrderIntent({
        actor: "Devarsh",
        limited_live_request_id: requestId,
        order_intent: {
          book_key: asText(request, "book_key", "active_trading"),
          estimated_loss: 1000,
          exchange: "NSE",
          instrument_type: "equity",
          notional: 10000,
          price: 1000,
          quantity: 10,
          side: "buy",
          symbol: asText(request, "symbol", "RELIANCE")
        },
        rationale: "Dashboard per-order intent probe. This does not place a broker order."
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setApprovalItems(liveApprovals(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Order intent create failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const evaluateOrderRiskFromDashboard = async (order: LiveRow) => {
    const orderId = asText(order, "id");
    const busyKey = `order-risk:${orderId}`;
    if (!orderId || executionSafetyBusyId) {
      return;
    }
    setExecutionSafetyBusyId(busyKey);
    setUiError("");
    try {
      await evaluateOrderIntentRisk({
        actor: "Execution Safety Agent",
        order_intent_id: orderId
      });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Order risk check failed");
      setLiveStatus("offline");
    } finally {
      setExecutionSafetyBusyId("");
    }
  };

  const stageBrokerQueue = async () => {
    if (brokerStageBusy) {
      return;
    }
    setBrokerStageBusy(true);
    setUiError("");
    try {
      await stageBrokerTransactions({ actor: "Jarvis", limit: 2000 });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Broker transaction staging failed");
      setLiveStatus("offline");
    } finally {
      setBrokerStageBusy(false);
    }
  };

  const runBrokerRecon = async () => {
    if (brokerReconBusy) {
      return;
    }
    setBrokerReconBusy(true);
    setUiError("");
    try {
      await runBrokerReconciliation({ actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Broker reconciliation failed");
      setLiveStatus("offline");
    } finally {
      setBrokerReconBusy(false);
    }
  };

  const runP2CursorRecon = async () => {
    if (p2CursorReconBusy) {
      return;
    }
    setP2CursorReconBusy(true);
    setUiError("");
    try {
      await runP2CursorReconciliation({ actor: "Jarvis", client_code: "3081832" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "P2Cursor reconciliation failed");
      setLiveStatus("offline");
    } finally {
      setP2CursorReconBusy(false);
    }
  };

  const runLegacySourceSweep = async () => {
    if (legacySourceBusy) {
      return;
    }
    setLegacySourceBusy(true);
    setUiError("");
    try {
      await runLegacySourceReadiness({ actor: "Jarvis" });
      const nextSnapshot = await fetchLiveSnapshot();
      setSnapshot(nextSnapshot);
      setItems(liveInbox(nextSnapshot));
      setLiveStatus("online");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Legacy source readiness sweep failed");
      setLiveStatus("offline");
    } finally {
      setLegacySourceBusy(false);
    }
  };

  return (
    <div className="app-shell app-shell-focused">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <CommandIcon size={18} aria-hidden="true" />
          </div>
          <div>
            <p>AI Office</p>
            <span>Charlie orchestrator</span>
          </div>
        </div>

        <nav className="workspace-nav" aria-label="AI Office workspaces">
          {workspaceNav.map((workspace) => {
            const Icon = workspaceIcons[workspace.id];
            const active = workspace.id === activeWorkspace;
            return (
              <button
                className={active ? "workspace-link active" : "workspace-link"}
                key={workspace.id}
                onClick={() => setActiveWorkspace(workspace.id)}
                type="button"
                title={workspace.label}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{workspace.label}</span>
                {workspace.count ? <strong>{workspace.count}</strong> : null}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div>
            <span className="mini-label">Local mode</span>
            <p>{liveStatus === "online" ? "Live DB linked" : "Warehouse required"}</p>
          </div>
          <ShieldCheck size={18} aria-hidden="true" />
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="icon-button" type="button" title="Toggle sidebar">
            <PanelLeft size={18} aria-hidden="true" />
          </button>
          <div className="workspace-title">
            <span>AI Office</span>
            <h1>{activeWorkspaceLabel}</h1>
          </div>
          <div className="topbar-actions">
            <span className={`live-status live-${liveStatus}`}>
              {liveStatus === "online" ? "Live warehouse" : liveStatus === "loading" ? "Connecting" : "Warehouse offline"}
            </span>
            <button className="ghost-button" onClick={() => setInterfaceMode("office")} type="button">
              <Building2 size={16} aria-hidden="true" />
              Live Office
            </button>
            <button className="ghost-button" type="button">
              <Search size={16} aria-hidden="true" />
              Search memory
            </button>
            <button className="icon-button alert" type="button" title={`${pendingApprovals} pending approvals`}>
              <Bell size={18} aria-hidden="true" />
              <span>{pendingApprovals}</span>
            </button>
          </div>
        </header>

        <section className="command-panel" aria-label="Charlie Munger command bar">
          <div className="command-copy">
            <div className="jarvis-avatar">
              <Sparkles size={18} aria-hidden="true" />
            </div>
            <div>
              <p>Charlie Munger</p>
              <span>Routes work through Jarvis runtime, agents, SQL, and Obsidian write-back.</span>
            </div>
          </div>
          <form className="command-form" onSubmit={submitCommand}>
            <input
              aria-label="Command Charlie Munger"
              onChange={(event) => setCommand(event.target.value)}
              placeholder="Ask Charlie to review portfolios, research holdings, inspect signals, or open a task..."
              value={command}
            />
            <button className="primary-button" disabled={commandBusy} type="submit">
              <Plus size={16} aria-hidden="true" />
              {commandBusy ? "Queueing" : "Assign"}
            </button>
          </form>
          {uiError ? <div className="error-strip">{uiError}</div> : null}
          <div className="quick-command-row">
            {quickCommands.map((quickCommand) => (
              <button
                key={quickCommand}
                onClick={() => setCommand(quickCommand)}
                type="button"
                title={quickCommand}
              >
                {quickCommand}
              </button>
            ))}
          </div>
        </section>

        {activeWorkspace === "system" ? (
          <SystemHealthWorkspace onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "command" ? (
          <MissionControlWorkspace onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "tactical" ? (
          <DepartmentDeskWorkspace initialDepartment="tactical" onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "portfolio" || activeWorkspace === "clients" ? (
          <PortfolioOfficeWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "research" || activeWorkspace === "ideas" ? (
          <ResearchIdeasWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "trading" || activeWorkspace === "quant" || activeWorkspace === "risk" ? (
          <TradingQuantRiskWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />
        ) : activeWorkspace === "reports" ? (
          <ReportsWorkspace onStatusChange={setLiveStatus} />
        ) : (
          <>
        <section className="metric-grid" aria-label="Portfolio operating metrics">
          {dashboardMetrics.length ? (
            dashboardMetrics.map((metric) => (
              <div className="metric-tile" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <p className={`tone-${metric.tone}`}>{metric.delta}</p>
              </div>
            ))
          ) : (
            <div className="metric-tile metric-empty">
              <span>Warehouse Required</span>
              <strong>0</strong>
              <p className="tone-warn">No seed metrics are displayed.</p>
            </div>
          )}
        </section>

        <section className="dashboard-grid">
          <Panel className="span-12" icon={<BarChart3 size={17} />} title="Live Dashboard Widgets" action={`${dashboardWidgets.length} active`}>
            <div className="live-widget-grid">
              {dashboardWidgets.length ? (
                dashboardWidgets.map((widget) => (
                  <LiveDashboardWidget
                    key={`${asText(widget, "workspace")}-${asText(widget, "widget_key")}`}
                    snapshot={snapshot}
                    widget={widget}
                  />
                ))
              ) : (
                <EmptyState message="No active dashboard widgets yet. Ask Charlie to show or monitor something, then materialize the widget intent." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<BriefcaseBusiness size={17} />} title="Investment Books" action={`${portfolioSummaryValue(snapshot, "book_positions")} positions`}>
            <div className="book-grid">
              {dashboardInvestmentBooks.length ? (
                dashboardInvestmentBooks.map((book) => (
                  <article className="book-card" key={asText(book, "book_key")}>
                    <div className="row-title">
                      <strong>{asText(book, "book_name", "Book")}</strong>
                      <StatusPill status={asText(book, "status", "active")} />
                    </div>
                    <p>{asText(book, "mandate", "Mandate pending.")}</p>
                    <div className="book-metrics">
                      <span>{asText(book, "position_count", "0")} positions</span>
                      <span>{compactInr(book.gross_exposure)}</span>
                      <span>{asText(book, "active_purpose_count", "0")} purposes</span>
                    </div>
                    <small>{asText(book, "owner_agent", "Portfolio Manager")} · {asText(book, "default_horizon", "mixed").replace(/_/g, " ")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No book rows loaded from books.v_investment_books." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<Gauge size={17} />} title="Portfolio Intelligence v2" action={`${dashboardPortfolioIntelligenceV2.length} signals`}>
            <div className="source-check-list">
              {dashboardPortfolioIntelligenceV2.length ? (
                dashboardPortfolioIntelligenceV2.map((item, index) => (
                  <article className="source-check-row" key={`${asText(item, "section")}-${asText(item, "item_key")}-${asText(item, "item_name")}-${index}`}>
                    <div>
                      <strong>{asText(item, "item_name", "Metric")}</strong>
                      <p>{asText(item, "interpretation", "Portfolio Intelligence signal.")}</p>
                    </div>
                    <StatusPill status={asText(item, "section", "portfolio")} />
                    <span>{asText(item, "item_value", "-")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No Portfolio Intelligence v2 rows loaded from books.v_portfolio_intelligence_v2." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<ListChecks size={17} />} title="Position Object v9 Readiness" action={`${dashboardPositionObjectGaps.length} gap types`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={positionRemediationBusy} onClick={() => void syncPositionRemediationFromDashboard()} type="button">
                {positionRemediationBusy ? "Routing..." : "Sync remediation queue"}
              </button>
            </div>
            <div className="source-check-list">
              {dashboardPositionRemediationSummary.length ? (
                dashboardPositionRemediationSummary.map((metric) => (
                  <article className="source-check-row" key={asText(metric, "metric")}>
                    <div>
                      <strong>{asText(metric, "metric", "metric").replace(/_/g, " ")}</strong>
                      <p>{asText(metric, "interpretation", "Position remediation metric.")}</p>
                    </div>
                    <span>{asText(metric, "value", "0")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No remediation summary loaded from books.v_position_object_remediation_summary." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardPositionRemediationQueue.length ? (
                dashboardPositionRemediationQueue.map((item) => (
                  <article className="source-check-row" key={asText(item, "remediation_key", asText(item, "id"))}>
                    <div>
                      <strong>{asText(item, "symbol", "SYMBOL")} · {asText(item, "gap_type", "gap").replace(/_/g, " ")}</strong>
                      <p>{asText(item, "recommended_action", "Route this gap to the owning agent.")}</p>
                      <small>{asText(item, "client_name", "Client")} · {asText(item, "owner_agent", "Portfolio Manager")} · task {asText(item, "task_id", "pending")} · inbox {asText(item, "inbox_id", "pending")}</small>
                    </div>
                    <StatusPill status={asText(item, "status", "queued")} />
                    <SeverityBadge severity={asSeverity(item.severity, "medium")} />
                  </article>
                ))
              ) : null}
            </div>
            <div className="source-check-list">
              {dashboardPositionObjectGaps.length ? (
                dashboardPositionObjectGaps.map((gap) => (
                  <article className="source-check-row" key={asText(gap, "gap_type")}>
                    <div>
                      <strong>{asText(gap, "gap_type", "gap").replace(/_/g, " ")}</strong>
                      <p>{asText(gap, "position_count", "0")} positions · {asText(gap, "symbol_count", "0")} symbols · avg score {asText(gap, "avg_completeness_score", "0")}</p>
                    </div>
                    <SeverityBadge severity={asSeverity(gap.severity, "medium")} />
                    <span>{asText(gap, "owner_agent", "Portfolio Manager")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No v9 position-object gaps loaded." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardPositionObjectsV9.length ? (
                dashboardPositionObjectsV9.map((position) => (
                  <article className="source-check-row" key={asText(position, "book_position_id")}>
                    <div>
                      <strong>{asText(position, "symbol", "SYMBOL")} · {asText(position, "book_name", "Book")}</strong>
                      <p>{asText(position, "client_name", "Client")} · {asText(position, "v9_gap_count", "0")} gaps · {asText(position, "v9_gap_types", "").slice(0, 120)}</p>
                    </div>
                    <StatusPill status={asText(position, "v9_decision_readiness", "review_required")} />
                    <span>{asText(position, "v9_completeness_score", "0")}%</span>
                  </article>
                ))
              ) : null}
            </div>
          </Panel>

          <Panel className="span-7" icon={<LineChart size={17} />} title="Symbol Intelligence v2" action={`${portfolioSummaryValue(snapshot, "gross_book_exposure")} gross`}>
            <div className="source-check-list">
              {[...dashboardSymbolIntelligenceV2Summary, ...dashboardSymbolIntelligenceActionSummary].length ? (
                [...dashboardSymbolIntelligenceV2Summary, ...dashboardSymbolIntelligenceActionSummary].map((metric, index) => (
                  <article className="source-check-row" key={`${asText(metric, "metric")}-${index}`}>
                    <div>
                      <strong>{asText(metric, "metric", "metric").replace(/_/g, " ")}</strong>
                      <p>{asText(metric, "interpretation", "Symbol Intelligence v2 metric.")}</p>
                    </div>
                    <span>{asText(metric, "value", "0")}</span>
                  </article>
                ))
              ) : null}
            </div>
            <div className="symbol-intelligence-list">
              {dashboardSymbolIntelligence.length ? (
                dashboardSymbolIntelligence.map((symbol) => {
                  const decisionFlags = asArray(symbol, "v2_decision_flags").length ? asArray(symbol, "v2_decision_flags") : asArray(symbol, "decision_flags");
                  const symbolKey = `${asText(symbol, "client_code") || "portfolio"}:${asText(symbol, "symbol")}`;
                  return (
                    <article className="symbol-intelligence-row" key={`${asText(symbol, "client_code")}-${asText(symbol, "symbol")}`}>
                      <div>
                        <strong>{asText(symbol, "symbol", "SYMBOL")}</strong>
                        <p>{asText(symbol, "client_name", "Client")} · {asArray(symbol, "active_books").join(", ") || "unbooked"}</p>
                        <small>{asText(symbol, "v2_recommended_next_action", asText(symbol, "recommended_next_action", "Monitor with current evidence."))}</small>
                      </div>
                      <div className="book-exposure-stack">
                        <span>LT {compactInr(symbol.long_term_exposure)}</span>
                        <span>Tac {compactInr(symbol.tactical_exposure)}</span>
                        <span>Quant {compactInr(symbol.quant_exposure)}</span>
                        <span>Active {compactInr(symbol.active_trading_exposure)}</span>
                      </div>
                      <div className="symbol-decision-stack">
                        <StatusPill status={asText(symbol, "v2_decision_state", asText(symbol, "decision_readiness", asText(symbol, "overall_bias", "monitor")))} />
                        <small>{asText(symbol, "critical_remediation_count", "0")} critical fixes · {asText(symbol, "risk_breach_count", "0")} breaches · {asText(symbol, "coordination_question_count", "0")} coordination</small>
                        <small>{asText(symbol, "gap_count", "0")} gaps · {asText(symbol, "conflict_count", "0")} conflicts · {asText(symbol, "overall_bias", "flat")}</small>
                        <small>MC {asText(symbol, "monte_carlo_status", "missing")} · CAGR {asText(symbol, "monte_carlo_median_cagr", "n/a")}</small>
                      </div>
                      <div className="symbol-evidence-stack">
                        <span>Committee {asText(symbol, "latest_committee_status", "not opened")}</span>
                        <span>Filings {asText(symbol, "filing_count", "0")} · News {asText(symbol, "news_count", "0")}</span>
                        <span>Signals {asText(symbol, "latest_signal_action", "none")} · Strategies {asText(symbol, "symbol_strategy_candidate_count", "0")}/{asText(symbol, "strategy_dossier_count", "0")} dossiers</span>
                        <span>Tasks {asText(symbol, "remediation_task_count", "0")} · Committees {asText(symbol, "pending_committee_item_count", "0")} pending</span>
                        {decisionFlags.length ? <small>{decisionFlags.slice(0, 3).join(", ")}</small> : <small>No decision flags</small>}
                        <div className="symbol-action-row">
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "refresh_thesis")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:refresh_thesis` ? "Routing" : "Thesis"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "review_exit_criteria")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:review_exit_criteria` ? "Routing" : "Exit"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "route_risk_review")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:route_risk_review` ? "Routing" : "Risk"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "route_research_update")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:route_research_update` ? "Routing" : "Research"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "route_quant_review")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:route_quant_review` ? "Routing" : "Quant"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "route_trading_review")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:route_trading_review` ? "Routing" : "Trade"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={Boolean(symbolActionBusyId)}
                            onClick={() => void routeSymbolActionFromDashboard(symbol, "prepare_tradingview")}
                            type="button"
                          >
                            {symbolActionBusyId === `${symbolKey}:prepare_tradingview` ? "Routing" : "TV Prep"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={!snapshot?.tradingview_cdp.available || chartActionBusyId === `${symbolKey}:open_symbol_chart`}
                            onClick={() => void runSymbolTradingViewTemplate(symbol, "open_symbol_chart")}
                            type="button"
                          >
                            {chartActionBusyId === `${symbolKey}:open_symbol_chart` ? "Opening" : "Chart"}
                          </button>
                          <button
                            className="mini-action-button"
                            disabled={!snapshot?.tradingview_cdp.available || chartActionBusyId === `${symbolKey}:capture_chart_snapshot`}
                            onClick={() => void runSymbolTradingViewTemplate(symbol, "capture_chart_snapshot")}
                            type="button"
                          >
                            {chartActionBusyId === `${symbolKey}:capture_chart_snapshot` ? "Capturing" : "Snapshot"}
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No symbol book exposure rows loaded from portfolio.v_symbol_intelligence." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<FileText size={17} />} title="Long-Term Thesis Control" action="research / valuation">
            <div className="panel-action-row">
              <select
                onChange={(event) => {
                  const [symbol, exchange] = event.target.value.split("|");
                  setLongTermThesisDraft({ symbol: symbol || "", exchange: exchange || "NSE" });
                }}
                value={`${longTermThesisDraft.symbol}|${longTermThesisDraft.exchange}`}
              >
                <option value="|NSE">Highest exposure needing memo</option>
                {dashboardLongTermTheses.map((thesis) => (
                  <option key={`${asText(thesis, "symbol")}-${asText(thesis, "exchange")}`} value={`${asText(thesis, "symbol")}|${asText(thesis, "exchange", "NSE")}`}>
                    {asText(thesis, "symbol", "SYMBOL")} · {compactInr(thesis.long_term_gross_exposure)} · {asText(thesis, "thesis_status", "needs memo")}
                  </option>
                ))}
              </select>
              <button className="mini-action-button" disabled={longTermThesisBusy} onClick={() => void generateLongTermThesisFromDashboard()} type="button">
                {longTermThesisBusy ? "Generating..." : "Generate thesis memo"}
              </button>
              <button className="mini-action-button" disabled={longTermCoverageBusy} onClick={() => void syncLongTermCoverageFromDashboard()} type="button">
                {longTermCoverageBusy ? "Syncing..." : "Sync coverage"}
              </button>
            </div>
            <div className="strategy-summary-strip">
              {dashboardLongTermCoverageSummary.slice(0, 6).map((metric) => (
                <div className="strategy-summary-cell" key={asText(metric, "metric")}>
                  <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                  <strong>{asText(metric, "value", "0")}</strong>
                </div>
              ))}
              {!dashboardLongTermCoverageSummary.length ? (
                <div className="strategy-summary-cell">
                  <span>coverage items</span>
                  <strong>0</strong>
                </div>
              ) : null}
            </div>
            <div className="source-check-list">
              <h4>Coverage board</h4>
              {dashboardLongTermCoverageQueue.length ? (
                dashboardLongTermCoverageQueue.map((coverage) => {
                  const coverageKey = asText(coverage, "coverage_key", asText(coverage, "id"));
                  const canGenerateMemo = asText(coverage, "gap_type") === "missing_thesis_container";
                  return (
                    <article className="source-check-row" key={coverageKey}>
                      <div>
                        <strong>{asText(coverage, "symbol", "SYMBOL")} · {asText(coverage, "gap_type", "gap").replace(/_/g, " ")}</strong>
                        <p>
                          {asText(coverage, "owner_agent", "Long-Term Portfolio Manager")} · {compactInr(coverage.long_term_gross_exposure)} · {asText(coverage, "client_count", "0")} clients
                        </p>
                      </div>
                      <StatusPill status={asText(coverage, "severity", "medium")} />
                      <span>{asText(coverage, "status", "queued")}</span>
                      {canGenerateMemo ? (
                        <button
                          className="mini-action-button"
                          disabled={Boolean(longTermCoverageMemoBusyKey)}
                          onClick={() => void generateLongTermThesisFromCoverage(coverage)}
                          type="button"
                        >
                          {longTermCoverageMemoBusyKey === coverageKey ? "Memo..." : "Memo"}
                        </button>
                      ) : (
                        <small>{asText(coverage, "task_status", "task")}</small>
                      )}
                      <time>{compactDate(coverage.updated_at)}</time>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No Long-Term coverage gaps loaded. Sync coverage after holdings or research updates." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardLongTermTheses.length ? (
                dashboardLongTermTheses.map((thesis) => (
                  <article className="source-check-row" key={`${asText(thesis, "symbol")}-${asText(thesis, "exchange")}-${asText(thesis, "id", "pending")}`}>
                    <div>
                      <strong>{asText(thesis, "symbol", "SYMBOL")}</strong>
                      <p>
                        {asText(thesis, "client_count", "0")} clients · {compactInr(thesis.long_term_gross_exposure)} · checklists {asText(thesis, "checklist_complete_count", "0")}/{asText(thesis, "checklist_count", "0")}
                      </p>
                    </div>
                    <StatusPill status={asText(thesis, "thesis_status", "needs_memo")} />
                    <span>{asText(thesis, "valuation_complete_count", "0")}/{asText(thesis, "valuation_model_count", "0")} models</span>
                    {asText(thesis, "id", "") ? (
                      <button
                        className="mini-action-button"
                        disabled={longTermPacketBusyId === asText(thesis, "id", "")}
                        onClick={() => void generateLongTermResearchPacketFromDashboard(thesis)}
                        type="button"
                      >
                        {longTermPacketBusyId === asText(thesis, "id", "") ? "Packet..." : "Research packet"}
                      </button>
                    ) : (
                      <small>memo first</small>
                    )}
                    {asText(thesis, "id", "") ? (
                      <button
                        className="mini-action-button"
                        disabled={longTermCommitteeBusyId === asText(thesis, "id", "")}
                        onClick={() => void openLongTermCommitteeFromDashboard(thesis)}
                        type="button"
                      >
                        {longTermCommitteeBusyId === asText(thesis, "id", "") ? "Opening..." : "Committee"}
                      </button>
                    ) : null}
                    {asText(thesis, "id", "") ? (
                      <button
                        className="mini-action-button"
                        disabled={longTermSpecialistBusyId === asText(thesis, "id", "")}
                        onClick={() => void dispatchLongTermSpecialistsFromDashboard(thesis)}
                        type="button"
                      >
                        {longTermSpecialistBusyId === asText(thesis, "id", "") ? "Dispatch..." : "Specialists"}
                      </button>
                    ) : null}
                    <time>{compactDate(thesis.next_review_due_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No long-term thesis rows loaded from portfolio.v_long_term_thesis_control." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Open checklist rows</h4>
              {dashboardLongTermChecklistRows.length ? (
                dashboardLongTermChecklistRows.map((row) => (
                  <article className="source-check-row" key={`lt-check-${asText(row, "id")}`}>
                    <div>
                      <strong>{asText(row, "symbol", "SYMBOL")} · {asText(row, "checklist_name", "Checklist")}</strong>
                      <p>{asText(row, "owner_agent", "Research Analyst")} · {compactInr(row.long_term_gross_exposure)}</p>
                    </div>
                    <StatusPill status={asText(row, "status", "not_started")} />
                    <span>{asText(row, "score", "no score")}</span>
                    <time>{compactDate(row.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No checklist rows loaded yet. Generate a thesis memo, then a source research packet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Valuation modules</h4>
              {dashboardLongTermValuationRows.length ? (
                dashboardLongTermValuationRows.map((row) => (
                  <article className="source-check-row" key={`lt-val-${asText(row, "id")}`}>
                    <div>
                      <strong>{asText(row, "symbol", "SYMBOL")} · {asText(row, "model_name", "Valuation")}</strong>
                      <p>{asText(row, "owner_agent", "Valuation Agent")} · base {asText(row, "fair_value_base", "source required")}</p>
                    </div>
                    <StatusPill status={asText(row, "status", "not_started")} />
                    <span>{asText(row, "expected_cagr_pct", "no CAGR")}</span>
                    <time>{compactDate(row.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No valuation module rows loaded yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Monte Carlo runs</h4>
              {dashboardLongTermMonteCarloRuns.length ? (
                dashboardLongTermMonteCarloRuns.map((row) => {
                  const probability = asRecord(row.probability_summary);
                  const cagrSummary = asRecord(asRecord(row.percentile_summary).cagr);
                  return (
                    <article className="source-check-row" key={`lt-mc-${asText(row, "id")}`}>
                      <div>
                        <strong>{asText(row, "symbol", "SYMBOL")} · run {asText(row, "id", "n/a")}</strong>
                        <p>
                          median CAGR {asText(cagrSummary, "p50", "n/a")} · negative CAGR {asText(probability, "negative_cagr_probability", "n/a")} · {asText(row, "simulation_count", "0")} sims
                        </p>
                      </div>
                      <StatusPill status={asText(row, "run_status", "needs_review")} />
                      <span>{asText(probability, "permanent_loss_30pct_probability", "n/a")} loss risk</span>
                      <time>{compactDate(row.created_at)}</time>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No Long-Term Monte Carlo runs yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Research update ledger</h4>
              {dashboardLongTermResearchUpdates.length ? (
                dashboardLongTermResearchUpdates.map((row) => (
                  <article className="source-check-row" key={`lt-update-${asText(row, "id")}`}>
                    <div>
                      <strong>{asText(row, "symbol", "SYMBOL")} · {asText(row, "update_kind", "update")}</strong>
                      <p>{asText(row, "note_path", "no note")} · {asText(row, "created_by", "AI OS")}</p>
                    </div>
                    <StatusPill status={asText(row, "status", "draft")} />
                    <time>{compactDate(row.created_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No long-term research update ledger rows yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Long-Term committee queue</h4>
              {dashboardLongTermCommittee.length ? (
                dashboardLongTermCommittee.map((review) => {
                  const reviewId = asText(review, "id", "");
                  const isFinal = asText(review, "decision_status") === "final";
                  const memoGenerated = asText(review, "memo_status") === "generated";
                  return (
                    <article className="source-check-row" key={`lt-committee-${reviewId}`}>
                      <div>
                        <strong>{asText(review, "symbol", "SYMBOL")} · {asText(review, "recommended_decision", "research_more")}</strong>
                        <p>
                          gaps {asArray(review, "source_gaps").length} · checklists {asText(review, "checklist_complete_count", "0")}/{asText(review, "checklist_count", "0")} · valuation {asText(review, "valuation_complete_count", "0")}/{asText(review, "valuation_model_count", "0")}
                        </p>
                      </div>
                      <StatusPill status={asText(review, "review_status", "opened")} />
                      <button
                        className="mini-action-button"
                        disabled={memoGenerated || longTermCommitteeMemoBusyId === reviewId}
                        onClick={() => void generateLongTermCommitteeMemoFromDashboard(review)}
                        type="button"
                      >
                        {longTermCommitteeMemoBusyId === reviewId ? "Memo..." : memoGenerated ? "Memo ready" : "Memo"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={longTermSpecialistBusyId === reviewId}
                        onClick={() => void dispatchLongTermSpecialistsFromDashboard(review)}
                        type="button"
                      >
                        {longTermSpecialistBusyId === reviewId ? "Dispatch..." : "Dispatch"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={!memoGenerated || isFinal || longTermCommitteeDecisionBusyId === `${reviewId}:research_more`}
                        onClick={() => void resolveLongTermCommitteeFromDashboard(review, "research_more")}
                        type="button"
                      >
                        Research
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={!memoGenerated || isFinal || longTermCommitteeDecisionBusyId === `${reviewId}:monitor`}
                        onClick={() => void resolveLongTermCommitteeFromDashboard(review, "monitor")}
                        type="button"
                      >
                        Monitor
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={!memoGenerated || isFinal || longTermCommitteeDecisionBusyId === `${reviewId}:approve_hold`}
                        onClick={() => void resolveLongTermCommitteeFromDashboard(review, "approve_hold")}
                        type="button"
                      >
                        Hold
                      </button>
                      <button
                        className="mini-action-button danger"
                        disabled={!memoGenerated || isFinal || longTermCommitteeDecisionBusyId === `${reviewId}:reject`}
                        onClick={() => void resolveLongTermCommitteeFromDashboard(review, "reject")}
                        type="button"
                      >
                        Reject
                      </button>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No Long-Term committee reviews opened yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Specialist assignments</h4>
              {dashboardLongTermSpecialists.length ? (
                dashboardLongTermSpecialists.map((assignment) => (
                  <article className="source-check-row" key={`lt-specialist-${asText(assignment, "id")}`}>
                    <div>
                      <strong>{asText(assignment, "symbol", "SYMBOL")} · {asText(assignment, "module_name", "Module")}</strong>
                      <p>{asText(assignment, "agent_name", "Agent")} · {asText(assignment, "skill_name", "skill")} · task {asText(assignment, "task_id", "n/a")}</p>
                    </div>
                    <StatusPill status={asText(assignment, "status", "queued")} />
                    <span>{asText(assignment, "source_status", "source_required")}</span>
                    <button
                      className="mini-action-button"
                      disabled={longTermSpecialistExecuteBusyId === asText(assignment, "id", "")}
                      onClick={() => void executeLongTermSpecialistFromDashboard(assignment)}
                      type="button"
                    >
                      {longTermSpecialistExecuteBusyId === asText(assignment, "id", "") ? "Running..." : "Execute"}
                    </button>
                    <time>{compactDate(assignment.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Long-Term specialist assignments dispatched yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Specialist outputs</h4>
              {dashboardLongTermSpecialistOutputs.length ? (
                dashboardLongTermSpecialistOutputs.map((output) => (
                  <article className="source-check-row" key={`lt-specialist-output-${asText(output, "id")}`}>
                    <div>
                      <strong>{asText(output, "symbol", "SYMBOL")} · {asText(output, "module_name", "Module")}</strong>
                      <p>{asText(output, "agent_name", "Agent")} · {asText(output, "note_path", "no note")}</p>
                    </div>
                    <StatusPill status={asText(output, "output_status", "draft")} />
                    <span>{asText(output, "source_status", "source_required")}</span>
                    <button
                      className="mini-action-button"
                      disabled={longTermSourceRequestBusyId === asText(output, "id", "")}
                      onClick={() => void createLongTermSourceRequestsFromDashboard(output)}
                      type="button"
                    >
                      {longTermSourceRequestBusyId === asText(output, "id", "") ? "Routing..." : "Request sources"}
                    </button>
                    <time>{compactDate(output.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Long-Term specialist outputs executed yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Source requests</h4>
              {dashboardLongTermSourceRequests.length ? (
                dashboardLongTermSourceRequests.map((request) => (
                  <article className="source-check-row" key={`lt-source-request-${asText(request, "id")}`}>
                    <div>
                      <strong>{asText(request, "symbol", "SYMBOL")} · {asText(request, "source_name", "source")}</strong>
                      <p>{asText(request, "owner_agent", "Filings and Transcript Analyst")} · {asText(request, "required_for_module", "module")} · task {asText(request, "task_id", "n/a")}</p>
                    </div>
                    <StatusPill status={asText(request, "status", "queued")} />
                    <span>{asText(request, "satisfaction_status", asText(request, "source_category", "filing"))}</span>
                    <button
                      className="mini-action-button"
                      disabled={longTermSourceCheckBusyId === asText(request, "id", "")}
                      onClick={() => void checkLongTermSourceRequestFromDashboard(request)}
                      type="button"
                    >
                      {longTermSourceCheckBusyId === asText(request, "id", "") ? "Checking..." : "Check"}
                    </button>
                    <time>{compactDate(request.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Long-Term source requests queued yet." />
              )}
            </div>
            <form className="source-document-form" onSubmit={submitLongTermSourceDocument}>
              <div className="field-grid">
                <label>
                  Source request
                  <select
                    onChange={(event) => setSourceDocumentDraft((draft) => ({ ...draft, sourceRequestId: event.target.value }))}
                    value={sourceDocumentDraft.sourceRequestId}
                  >
                    <option value="">Select queued request</option>
                    {dashboardLongTermSourceRequests.map((request) => (
                      <option key={`source-doc-request-${asText(request, "id")}`} value={asText(request, "id")}>
                        {asText(request, "symbol", "SYMBOL")} · {asText(request, "source_name", "source")} · #{asText(request, "id")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Document type
                  <select
                    onChange={(event) => setSourceDocumentDraft((draft) => ({ ...draft, documentType: event.target.value }))}
                    value={sourceDocumentDraft.documentType}
                  >
                    <option value="annual_report">Annual report</option>
                    <option value="investor_presentation">Investor presentation</option>
                    <option value="exchange_filing">Exchange filing</option>
                    <option value="conference_call_transcript">Concall transcript</option>
                    <option value="statutory_filing">Statutory filing</option>
                  </select>
                </label>
                <label>
                  Title
                  <input
                    onChange={(event) => setSourceDocumentDraft((draft) => ({ ...draft, title: event.target.value }))}
                    placeholder="Usha Martin Annual Report 2024-25"
                    value={sourceDocumentDraft.title}
                  />
                </label>
                <label>
                  Official URL
                  <input
                    onChange={(event) => setSourceDocumentDraft((draft) => ({ ...draft, sourceUrl: event.target.value }))}
                    placeholder="https://company.com/annual-report.pdf"
                    value={sourceDocumentDraft.sourceUrl}
                  />
                </label>
              </div>
              <button className="primary-button" disabled={longTermSourceDocumentBusy} type="submit">
                {longTermSourceDocumentBusy ? "Registering..." : "Register source document"}
              </button>
            </form>
            <div className="source-check-list">
              <h4>Registered source documents</h4>
              {dashboardLongTermSourceDocuments.length ? (
                dashboardLongTermSourceDocuments.map((document) => (
                  <article className="source-check-row" key={`lt-source-document-${asText(document, "id")}`}>
                    <div>
                      <strong>{asText(document, "symbol", "SYMBOL")} · {asText(document, "document_type", "document")}</strong>
                      <p>{asText(document, "document_title", "source")} · artifact {asText(document, "raw_artifact_id", "n/a")}</p>
                    </div>
                    <StatusPill status={asText(document, "provenance_status", "registered")} />
                    <span>{asText(document, "http_status", "n/a")}</span>
                    <button
                      className="mini-action-button"
                      disabled={longTermSourceExtractBusyId === asText(document, "id", "")}
                      onClick={() => void extractLongTermSourceDocumentFromDashboard(document)}
                      type="button"
                    >
                      {longTermSourceExtractBusyId === asText(document, "id", "") ? "Extracting..." : "Extract"}
                    </button>
                    <time>{compactDate(document.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No official Long-Term source documents registered yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Source extractions</h4>
              {dashboardLongTermSourceExtractions.length ? (
                dashboardLongTermSourceExtractions.map((extraction) => (
                  <article className="source-check-row" key={`lt-source-extraction-${asText(extraction, "id")}`}>
                    <div>
                      <strong>{asText(extraction, "symbol", "SYMBOL")} · {asText(extraction, "parser_name", "parser")}</strong>
                      <p>{asText(extraction, "document_title", "document")} · {asText(extraction, "extracted_chars", "0")} chars</p>
                    </div>
                    <StatusPill status={asText(extraction, "extraction_status", "extracted")} />
                    <span>{asText(extraction, "page_count", "n/a")} pages</span>
                    <time>{compactDate(extraction.extracted_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Long-Term source document text extracted yet." />
              )}
            </div>
            <div className="source-check-list">
              <h4>Source checks</h4>
              {dashboardLongTermSourceChecks.length ? (
                dashboardLongTermSourceChecks.map((check) => (
                  <article className="source-check-row" key={`lt-source-check-${asText(check, "id")}`}>
                    <div>
                      <strong>{asText(check, "symbol", "SYMBOL")} · {asText(check, "source_name", "source")}</strong>
                      <p>{asText(check, "required_for_module", "module")} · matches {asText(check, "matched_source_count", "0")}</p>
                    </div>
                    <StatusPill status={asText(check, "check_status", "missing")} />
                    <span>{asText(check, "checked_by", "Filings and Transcript Analyst")}</span>
                    <time>{compactDate(check.checked_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Long-Term source checks run yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<Building2 size={17} />} title="Client Book Exposure" action="multi-book folios">
            <div className="client-book-list">
              {dashboardClientBookExposure.length ? (
                dashboardClientBookExposure.map((row) => (
                  <article className="client-book-row" key={`${asText(row, "client_code")}-${asText(row, "book_key")}`}>
                    <div>
                      <strong>{asText(row, "client_name", "Client")}</strong>
                      <p>{asText(row, "book_name", "Book")} · {asText(row, "symbol_count", "0")} symbols</p>
                    </div>
                    <div>
                      <span>{compactInr(row.gross_exposure)}</span>
                      <small>{asText(row, "book_bias", "flat")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No client book exposure rows loaded from books.v_client_book_exposure." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<ClipboardList size={17} />} title="Book Assignment Control" action="human editable">
            <form className="book-assignment-form" onSubmit={submitBookAssignment}>
              <div className="field-grid">
                <label>
                  Position
                  <select
                    onChange={(event) => setBookAssignmentDraft((current) => ({ ...current, bookPositionId: event.target.value }))}
                    value={bookAssignmentDraft.bookPositionId}
                  >
                    <option value="">Select position</option>
                    {(snapshot?.book_positions ?? []).slice(0, 80).map((position) => (
                      <option key={asText(position, "id")} value={asText(position, "id")}>
                        {asText(position, "client_name", "Client")} · {asText(position, "symbol", "SYMBOL")} · {compactInr(position.gross_exposure)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Book
                  <select
                    onChange={(event) => {
                      const nextBook = event.target.value;
                      const nextPurpose = (snapshot?.position_purpose_options ?? []).find((option) => asText(option, "book_key") === nextBook);
                      setBookAssignmentDraft((current) => ({
                        ...current,
                        bookKey: nextBook,
                        purposeKey: nextPurpose ? asText(nextPurpose, "purpose_key") : ""
                      }));
                    }}
                    value={bookAssignmentDraft.bookKey}
                  >
                    {(snapshot?.investment_books ?? []).map((book) => (
                      <option key={asText(book, "book_key")} value={asText(book, "book_key")}>
                        {asText(book, "book_name", "Book")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Purpose
                  <select
                    onChange={(event) => setBookAssignmentDraft((current) => ({ ...current, purposeKey: event.target.value }))}
                    value={bookAssignmentDraft.purposeKey}
                  >
                    {selectedBookPurposes.map((purpose) => (
                      <option key={asText(purpose, "purpose_key")} value={asText(purpose, "purpose_key")}>
                        {asText(purpose, "purpose_name", "Purpose")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Thesis note
                  <input
                    onChange={(event) => setBookAssignmentDraft((current) => ({ ...current, thesis: event.target.value }))}
                    placeholder="Optional"
                    value={bookAssignmentDraft.thesis}
                  />
                </label>
              </div>
              <label className="wide-field">
                Exit criteria
                <textarea
                  onChange={(event) => setBookAssignmentDraft((current) => ({ ...current, exitCriteria: event.target.value }))}
                  placeholder="Optional explicit stop, target, thesis killer, or review rule"
                  rows={3}
                  value={bookAssignmentDraft.exitCriteria}
                />
              </label>
              <button
                className="primary-button"
                disabled={bookAssignmentBusy || !bookAssignmentDraft.bookPositionId || !bookAssignmentDraft.purposeKey}
                type="submit"
              >
                <Check size={16} aria-hidden="true" />
                {bookAssignmentBusy ? "Saving" : "Update assignment"}
              </button>
            </form>
          </Panel>

          <Panel className="span-6" icon={<LineChart size={17} />} title="Trade Ticket" action="manual + paper">
            <form className="trade-ticket-form" onSubmit={submitTradeTicket}>
              <div className="field-grid">
                <label>
                  Mode
                  <select
                    onChange={(event) => setTradeDraft((current) => ({ ...current, mode: event.target.value }))}
                    value={tradeDraft.mode}
                  >
                    <option value="paper">Paper</option>
                    <option value="manual">Manual actual</option>
                  </select>
                </label>
                <label>
                  Side
                  <select
                    onChange={(event) => setTradeDraft((current) => ({ ...current, side: event.target.value }))}
                    value={tradeDraft.side}
                  >
                    <option value="buy">Buy / Long</option>
                    <option value="sell">Sell / Short</option>
                    <option value="watch">Watch</option>
                    <option value="exit">Exit</option>
                  </select>
                </label>
                <label>
                  Symbol
                  <input
                    onChange={(event) => setTradeDraft((current) => ({ ...current, symbol: event.target.value }))}
                    placeholder="NSE symbol"
                    value={tradeDraft.symbol}
                  />
                </label>
                <label>
                  Quantity
                  <input
                    inputMode="decimal"
                    onChange={(event) => setTradeDraft((current) => ({ ...current, quantity: event.target.value }))}
                    placeholder="Optional"
                    value={tradeDraft.quantity}
                  />
                </label>
                <label>
                  Price
                  <input
                    inputMode="decimal"
                    onChange={(event) => setTradeDraft((current) => ({ ...current, price: event.target.value }))}
                    placeholder="Optional"
                    value={tradeDraft.price}
                  />
                </label>
                <label>
                  Book
                  <select
                    onChange={(event) => {
                      const nextBook = event.target.value;
                      const nextPurpose = (snapshot?.position_purpose_options ?? []).find((option) => asText(option, "book_key") === nextBook);
                      setTradeDraft((current) => ({
                        ...current,
                        bookKey: nextBook,
                        purposeKey: nextPurpose ? asText(nextPurpose, "purpose_key") : ""
                      }));
                    }}
                    value={tradeDraft.bookKey}
                  >
                    {(snapshot?.investment_books ?? []).map((book) => (
                      <option key={asText(book, "book_key")} value={asText(book, "book_key")}>
                        {asText(book, "book_name", "Book")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Purpose
                  <select
                    onChange={(event) => setTradeDraft((current) => ({ ...current, purposeKey: event.target.value }))}
                    value={tradeDraft.purposeKey}
                  >
                    {selectedTradePurposes.map((purpose) => (
                      <option key={asText(purpose, "purpose_key")} value={asText(purpose, "purpose_key")}>
                        {asText(purpose, "purpose_name", "Purpose")}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Client
                  <input
                    onChange={(event) => setTradeDraft((current) => ({ ...current, clientCode: event.target.value }))}
                    placeholder="Optional"
                    value={tradeDraft.clientCode}
                  />
                </label>
                <label>
                  Stop
                  <input
                    inputMode="decimal"
                    onChange={(event) => setTradeDraft((current) => ({ ...current, stopLoss: event.target.value }))}
                    placeholder="Optional"
                    value={tradeDraft.stopLoss}
                  />
                </label>
                <label>
                  Target
                  <input
                    inputMode="decimal"
                    onChange={(event) => setTradeDraft((current) => ({ ...current, targetPrice: event.target.value }))}
                    placeholder="Optional"
                    value={tradeDraft.targetPrice}
                  />
                </label>
              </div>
              <label className="wide-field">
                Thesis / setup
                <textarea
                  onChange={(event) => setTradeDraft((current) => ({ ...current, thesis: event.target.value }))}
                  placeholder="Why this trade exists, what invalidates it, and how it will be reviewed"
                  rows={3}
                  value={tradeDraft.thesis}
                />
              </label>
              <button className="primary-button" disabled={tradeTicketBusy || !tradeDraft.symbol.trim()} type="submit">
                <Plus size={16} aria-hidden="true" />
                {tradeTicketBusy ? "Recording" : "Record trade"}
              </button>
            </form>
          </Panel>

          <Panel className="span-6" icon={<DatabaseZap size={17} />} title="Broker Transaction Import Queue" action={`${asText(dashboardBrokerSummary.find((row) => asText(row, "metric") === "staged_broker_routes") ?? {}, "value", "0")} staged`}>
            <div className="broker-import-summary">
              {dashboardBrokerSummary.length ? (
                dashboardBrokerSummary.map((row) => (
                  <article className="broker-summary-row" key={asText(row, "metric")}>
                    <strong>{asText(row, "value", "0")}</strong>
                    <span>{asText(row, "metric", "metric").replace(/_/g, " ")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No broker import summary rows loaded." />
              )}
            </div>
            <button className="panel-inline-button" disabled={brokerStageBusy} onClick={() => void stageBrokerQueue()} type="button">
              {brokerStageBusy ? "Staging" : "Refresh staging"}
            </button>
            <div className="broker-queue-list">
              {dashboardBrokerQueue.length ? (
                dashboardBrokerQueue.map((row) => (
                  <article className="broker-queue-row" key={asText(row, "route_id")}>
                    <div>
                      <strong>{asText(row, "symbol", "SYMBOL")}</strong>
                      <p>{asText(row, "client_code", "client")} · {asText(row, "side", "-")} · {compactInr(row.amount)}</p>
                    </div>
                    <div>
                      <span>{asText(row, "book_name", "Book")}</span>
                      <small>{asText(row, "purpose_name", "Purpose")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No staged broker transaction routes loaded." />
              )}
            </div>
            <div className="trade-link-list">
              {dashboardTradeBookLinks.length ? (
                dashboardTradeBookLinks.map((row) => (
                  <article className="trade-link-row" key={asText(row, "id")}>
                    <div>
                      <strong>{asText(row, "symbol", "SYMBOL")}</strong>
                      <p>{asText(row, "book_name", "Book")} · {asText(row, "purpose_name", "Purpose")}</p>
                    </div>
                    <StatusPill status={asText(row, "link_type", "history")} />
                  </article>
                ))
              ) : null}
            </div>
          </Panel>

          <Panel className="span-6" icon={<ShieldCheck size={17} />} title="Broker Reconciliation" action={dashboardBrokerRecon ? `run #${asText(dashboardBrokerRecon, "id")}` : "not run"}>
            <div className="reconciliation-panel">
              {dashboardBrokerRecon ? (
                <article className="reconciliation-summary">
                  <div>
                    <strong>{asText(dashboardBrokerRecon, "total_broker_rows", "0")}</strong>
                    <span>broker rows</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardBrokerRecon, "staged_routes", "0")}</strong>
                    <span>staged routes</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardBrokerRecon, "duplicate_trade_refs", "0")}</strong>
                    <span>duplicate refs</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardBrokerRecon, "unmapped_rows", "0")}</strong>
                    <span>unmapped</span>
                  </div>
                </article>
              ) : (
                <EmptyState message="No reconciliation run loaded." />
              )}
              <button className="panel-inline-button" disabled={brokerReconBusy} onClick={() => void runBrokerRecon()} type="button">
                {brokerReconBusy ? "Reconciling" : "Run reconciliation"}
              </button>
              <div className="reconciliation-issue-list">
                {dashboardBrokerReconIssues.length ? (
                  dashboardBrokerReconIssues.map((issue) => (
                    <article className="reconciliation-issue-row" key={asText(issue, "id")}>
                      <div>
                        <strong>{asText(issue, "issue_type", "issue").replace(/_/g, " ")}</strong>
                        <p>{asText(issue, "description", "Review broker import issue.")}</p>
                      </div>
                      <SeverityBadge severity={asSeverity(issue.severity, "medium")} />
                    </article>
                  ))
                ) : (
                  <EmptyState message="No reconciliation issues are open in the latest API snapshot." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<GitBranch size={17} />} title="P2Cursor Reconciliation" action={dashboardP2CursorRecon ? `${asText(dashboardP2CursorRecon, "client_name", "Client")} · ${asText(dashboardP2CursorRecon, "status", "status")}` : "not run"}>
            <div className="reconciliation-panel">
              {dashboardP2CursorRecon ? (
                <article className="reconciliation-summary">
                  <div>
                    <strong>{asText(dashboardP2CursorRecon, "p2_position_count", "0")}</strong>
                    <span>p2 positions</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardP2CursorRecon, "comparison_position_count", "0")}</strong>
                    <span>statement positions</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardP2CursorRecon, "quantity_mismatch_symbols", "0")}</strong>
                    <span>qty mismatches</span>
                  </div>
                  <div>
                    <strong>{asText(dashboardP2CursorRecon, "stale_days", "0")}</strong>
                    <span>days stale</span>
                  </div>
                </article>
              ) : (
                <EmptyState message="No p2cursor reconciliation run loaded." />
              )}
              <button className="panel-inline-button" disabled={p2CursorReconBusy} onClick={() => void runP2CursorRecon()} type="button">
                {p2CursorReconBusy ? "Reconciling" : "Run Tushit p2cursor recon"}
              </button>
              <div className="reconciliation-issue-list">
                {dashboardP2CursorReconIssues.length ? (
                  dashboardP2CursorReconIssues.map((issue) => (
                    <article className="reconciliation-issue-row" key={asText(issue, "id")}>
                      <div>
                        <strong>{asText(issue, "symbol", asText(issue, "issue_type", "issue")).replace(/_/g, " ")}</strong>
                        <p>{asText(issue, "description", "Review p2cursor reconciliation issue.")}</p>
                      </div>
                      <SeverityBadge severity={asSeverity(issue.severity, "medium")} />
                    </article>
                  ))
                ) : (
                  <EmptyState message="No p2cursor reconciliation issues are open in the latest API snapshot." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<DatabaseZap size={17} />} title="Legacy Source Readiness" action={dashboardLegacySourceRun ? asText(dashboardLegacySourceRun, "status", "not run").replace(/_/g, " ") : "not run"}>
            <div className="reconciliation-panel">
              <article className="reconciliation-summary">
                {dashboardLegacySourceSummary.slice(0, 4).map((row) => (
                  <div key={asText(row, "metric")}>
                    <strong>{asText(row, "value", "0")}</strong>
                    <span>{asText(row, "metric", "metric").replace(/_/g, " ")}</span>
                  </div>
                ))}
              </article>
              <button className="panel-inline-button" disabled={legacySourceBusy} onClick={() => void runLegacySourceSweep()} type="button">
                {legacySourceBusy ? "Sweeping" : "Run legacy readiness sweep"}
              </button>
              <div className="reconciliation-issue-list">
                {dashboardLegacySourceIssues.length ? (
                  dashboardLegacySourceIssues.map((issue) => (
                    <article className="reconciliation-issue-row" key={asText(issue, "id")}>
                      <div>
                        <strong>{asText(issue, "source_family", "legacy")} · {asText(issue, "issue_type", "issue").replace(/_/g, " ")}</strong>
                        <p>{asText(issue, "source_ref", "source")} · {asText(issue, "recommended_action", "Review extraction readiness.")}</p>
                      </div>
                      <SeverityBadge severity={asSeverity(issue.severity, "medium")} />
                    </article>
                  ))
                ) : (
                  <EmptyState message="No legacy source readiness issues have been swept into the latest API snapshot." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<DatabaseZap size={17} />} title="P2/Algo Extraction Coverage" action={`${dashboardP2CursorExtraction.length + dashboardAlgoExtraction.length} surfaces`}>
            <div className="reconciliation-panel">
              <div className="reconciliation-issue-list">
                {dashboardP2CursorExtraction.map((row) => (
                  <article className="reconciliation-issue-row" key={`p2-${asText(row, "source_file_id")}`}>
                    <div>
                      <strong>{asText(row, "file_type", "file")} · {asText(row, "readiness_status", "status").replace(/_/g, " ")}</strong>
                      <p>{asText(row, "original_path", "p2cursor file")} · {asText(row, "staged_row_count", "0")} staged / {asText(row, "profiled_row_count", "0")} profiled</p>
                    </div>
                    <SeverityBadge severity={asText(row, "readiness_status") === "reference_profiled" ? "low" : "medium"} />
                  </article>
                ))}
                {dashboardAlgoExtraction.map((row) => (
                  <article className="reconciliation-issue-row" key={`algo-${asText(row, "database_path")}-${asText(row, "table_name")}`}>
                    <div>
                      <strong>{asText(row, "table_name", "table")} · {asText(row, "readiness_status", "status").replace(/_/g, " ")}</strong>
                      <p>{asText(row, "source_rows", "0")} source · {asText(row, "imported_rows", "0")} canonical · {asText(row, "deduplicated_rows", "0")} deduped · {asText(row, "resolved_rows", "0")} resolved</p>
                      <p>{asText(row, "resolution_mode", "unclassified").replace(/_/g, " ")} · {asText(row, "canonical_relation", "no destination")}</p>
                    </div>
                    <SeverityBadge severity={asText(row, "readiness_status") === "profiled_not_promoted" && asText(row, "source_value") === "high_value" ? "high" : asText(row, "readiness_status") === "partially_promoted" ? "medium" : "low"} />
                  </article>
                ))}
                {dashboardP2CursorExtraction.length || dashboardAlgoExtraction.length ? null : (
                  <EmptyState message="No p2cursor or algo extraction readiness rows are visible in the latest API snapshot." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<GitBranch size={17} />} title="Source Lineage" action={`${dashboardSourceArtifactLineage.length} recent rows`}>
            <div className="reconciliation-panel">
              <article className="reconciliation-summary">
                {dashboardSourceLineageSummary.slice(0, 4).map((row) => (
                  <div key={`${asText(row, "lineage_type")}-${asText(row, "source_system")}`}>
                    <strong>{asText(row, "row_count", "0")}</strong>
                    <span>{asText(row, "lineage_type", "lineage").replace(/_/g, " ")}</span>
                  </div>
                ))}
              </article>
              <div className="reconciliation-issue-list">
                {dashboardSourceArtifactLineage.length ? (
                  dashboardSourceArtifactLineage.map((row) => (
                    <article className="reconciliation-issue-row" key={asText(row, "row_ref")}>
                      <div>
                        <strong>{asText(row, "row_ref", "source row")}</strong>
                        <p>{asText(row, "source_system", "source")} · {asText(row, "symbol", asText(row, "client_code", "artifact"))} · {compactDate(row.event_at)}</p>
                      </div>
                      <StatusPill status={asText(row, "lineage_type", "lineage").replace(/_/g, " ")} />
                    </article>
                  ))
                ) : (
                  <EmptyState message="No source lineage rows returned by core.v_source_artifact_lineage." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<DatabaseZap size={17} />} title="Artifact Coverage" action={`${dashboardImportArtifactGaps.length} gaps`}>
            <div className="reconciliation-panel">
              <article className="reconciliation-summary">
                {dashboardImportArtifactCoverage.map((row) => (
                  <div key={asText(row, "import_surface")}>
                    <strong>{asText(row, "coverage_pct", "0")}%</strong>
                    <span>{asText(row, "import_surface", "surface").replace(/_/g, " ")}</span>
                  </div>
                ))}
              </article>
              <div className="reconciliation-issue-list">
                {dashboardImportArtifactGaps.length ? (
                  dashboardImportArtifactGaps.map((gap) => (
                    <article className="reconciliation-issue-row" key={asText(gap, "row_ref")}>
                      <div>
                        <strong>{asText(gap, "title", "import artifact")}</strong>
                        <p>{asText(gap, "gap_reason", "Missing raw artifact lineage.")}</p>
                      </div>
                      <StatusPill status={asText(gap, "import_surface", "gap").replace(/_/g, " ")} />
                    </article>
                  ))
                ) : (
                  <EmptyState message="All tracked import surfaces have raw-artifact lineage in core.v_import_artifact_coverage." />
                )}
              </div>
            </div>
          </Panel>

          <Panel className="span-6" icon={<ClipboardList size={17} />} title="Post-Trade Review Queue" action={`${dashboardPostTradeReviews.length} visible`}>
            <div className="post-trade-review-list">
              {dashboardPostTradeReviews.length ? (
                dashboardPostTradeReviews.map((review) => (
                  <article className="post-trade-review-row" key={asText(review, "id")}>
                    <div>
                      <strong>{asText(review, "symbol", "SYMBOL")} · {asText(review, "side", "side")}</strong>
                      <p>{asText(review, "book_name", "Book")} · {asText(review, "purpose_name", "Purpose")} · {compactDate(review.due_at)}</p>
                    </div>
                    <StatusPill status={asText(review, "review_status", "queued")} />
                  </article>
                ))
              ) : (
                <EmptyState message="No post-trade reviews yet. Record a manual or paper trade to create one." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<ShieldCheck size={17} />} title="Book Risk And Assignment Gaps" action={`${dashboardCrossBookConflicts.length} offsets`}>
            <div className="book-risk-list">
              <article className="book-risk-row calm">
                <div>
                  <strong>Risk limit checks</strong>
                  <p>
                    {asText(dashboardRiskSummary.find((row) => asText(row, "metric") === "risk_limit_breaches") ?? {}, "value", "0")} breaches ·{" "}
                    {asText(dashboardRiskSummary.find((row) => asText(row, "metric") === "risk_limit_warnings") ?? {}, "value", "0")} warnings ·{" "}
                    {asText(dashboardRiskSummary.find((row) => asText(row, "metric") === "risk_limit_checks") ?? {}, "value", "0")} checks
                  </p>
                </div>
                <button className="mini-action-button" disabled={riskRefreshBusy} onClick={() => void refreshPortfolioRiskEventsFromDashboard()} type="button">
                  {riskRefreshBusy ? "Refreshing" : "Refresh events"}
                </button>
              </article>
              {dashboardRiskLimitChecks.length ? (
                dashboardRiskLimitChecks.map((check) => (
                  <article className="book-risk-row" key={asText(check, "check_key")}>
                    <div>
                      <strong>{asText(check, "limit_name", "Risk limit")} · {asText(check, "check_status", "status")}</strong>
                      <p>{asText(check, "check_message", "Risk Agent review required.")}</p>
                    </div>
                    <SeverityBadge severity={asSeverity(check.severity, "medium")} />
                  </article>
                ))
              ) : (
                <EmptyState message="No risk limit checks loaded from risk.v_portfolio_risk_limit_checks." />
              )}
              {dashboardCrossBookConflicts.length ? (
                dashboardCrossBookConflicts.map((conflict) => (
                  <article className="book-risk-row" key={`conflict-${asText(conflict, "synthetic_id")}`}>
                    <div>
                      <strong>{asText(conflict, "symbol", "SYMBOL")} cross-book offset</strong>
                      <p>{asText(conflict, "description", "Risk Office review required.")}</p>
                    </div>
                    <SeverityBadge severity={asSeverity(conflict.severity, "high")} />
                  </article>
                ))
              ) : (
                <article className="book-risk-row calm">
                  <div>
                    <strong>No cross-book offsets yet</strong>
                    <p>Current client holdings are all mapped to Long-Term until trades or strategy positions are added.</p>
                  </div>
                  <StatusPill status="clear" />
                </article>
              )}
              {dashboardCrossBookCoordination.length ? (
                dashboardCrossBookCoordination.map((question) => (
                  <article className="book-risk-row" key={`coordination-${asText(question, "synthetic_id")}`}>
                    <div>
                      <strong>{asText(question, "symbol", "SYMBOL")} coordination question</strong>
                      <p>{asText(question, "coordination_question", "Risk Office coordination required.")}</p>
                    </div>
                    <SeverityBadge severity={asSeverity(question.severity, "medium")} />
                  </article>
                ))
              ) : null}
              {dashboardBookAssignmentGaps.length ? (
                dashboardBookAssignmentGaps.map((gap) => (
                  <article className="book-risk-row" key={`gap-${asText(gap, "book_position_id")}-${asText(gap, "gap_type")}`}>
                    <div>
                      <strong>{asText(gap, "symbol", "SYMBOL")} · {asText(gap, "gap_type", "gap").replace(/_/g, " ")}</strong>
                      <p>{asText(gap, "client_name", "Client")} · {asText(gap, "gap_description", "Needs review.")}</p>
                    </div>
                    <SeverityBadge severity={asSeverity(gap.severity, "medium")} />
                  </article>
                ))
              ) : null}
            </div>
          </Panel>

          <Panel className="span-8" icon={<DatabaseZap size={17} />} title="Control Plane" action={`${metricValue(snapshot, "mcp_enabled_tools", "57")} MCP tools`}>
            <div className="control-table">
              <div className="control-head">
                <span>Module</span>
                <span>Status</span>
                <span>Owner</span>
                <span>Next</span>
              </div>
              {dashboardModules.length ? (
                dashboardModules.map((module) => (
                  <article className="control-row" key={module.key}>
                    <div>
                      <strong>{module.name}</strong>
                      <small>{module.workspace}</small>
                    </div>
                    <StatusPill status={module.status} />
                    <span>{module.owner}</span>
                    <p>{module.nextAction}</p>
                  </article>
                ))
              ) : (
                <EmptyState message="No live control-plane rows loaded from Postgres." />
              )}
            </div>
          </Panel>

          <Panel
            className="span-4"
            icon={<ListChecks size={17} />}
            title="Blueprint v10 Coverage"
            action={`${asText(dashboardBlueprintSummary.find((row) => asText(row, "metric") === "requirements") ?? {}, "value", "0")} reqs · ${asText(latestBlueprintSync ?? {}, "status", "unsynced")}`}
          >
            <div className="employee-profile-summary">
              {dashboardBlueprintSummary.length ? (
                dashboardBlueprintSummary.map((metric) => (
                  <div className="employee-profile-metric" key={asText(metric, "metric")}>
                    <strong>{asText(metric, "value", "0")}</strong>
                    <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                  </div>
                ))
              ) : (
                <div className="employee-profile-metric">
                  <strong>0</strong>
                  <span>blueprint rows</span>
                </div>
              )}
            </div>
            <div className="source-check-list">
              {dashboardBlueprintDomains.length ? (
                dashboardBlueprintDomains.map((domain) => (
                  <article className="source-check-row" key={asText(domain, "domain_key")}>
                    <div>
                      <strong>{asText(domain, "section_number", "-")} · {asText(domain, "domain_name", "Domain")}</strong>
                      <p>{asText(domain, "objective", "No objective recorded.")}</p>
                    </div>
                    <StatusPill status={asText(domain, "status", "planned")} />
                    <span>{asText(domain, "progress_score", "0")}%</span>
                    <small>{asText(domain, "partial_count", "0")} partial · {asText(domain, "planned_count", "0")} planned</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No canonical blueprint domains loaded from the warehouse." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardBlueprintRequirements.length ? (
                dashboardBlueprintRequirements.map((requirement) => (
                  <article className="source-check-row" key={asText(requirement, "requirement_key")}>
                    <div>
                      <strong>{asText(requirement, "requirement_name", "Requirement")}</strong>
                      <p>{asText(requirement, "next_action", asText(requirement, "acceptance_criteria", "No next action recorded."))}</p>
                    </div>
                    <StatusPill status={asText(requirement, "current_status", "planned")} />
                    <span>{asText(requirement, "owner_agent", "owner")}</span>
                    <small>{asText(requirement, "mapped_object_type", "-")} · {asText(requirement, "mapped_object_status", asText(requirement, "mapped_object_found", "false"))}</small>
                  </article>
                ))
              ) : null}
            </div>
          </Panel>

          <Panel
            className="span-4"
            icon={<LineChart size={17} />}
            title="TradingView Task Queue"
            action={snapshot?.tradingview_cdp.available ? "CDP online" : "CDP gated"}
          >
            <div className="task-mini-list">
              {(snapshot?.tradingview_tasks ?? []).slice(0, 5).map((task) => (
                <article className="task-mini-row" key={asText(task, "id")}>
                  <div>
                    <strong>{asText(task, "task_title", "TradingView task")}</strong>
                    <p>{asText(task, "instruction", "Awaiting chart instruction")}</p>
                  </div>
                  <div className="task-mini-actions">
                    <StatusBadge status={asStatus(task.status, "queued")} />
                    <button
                      className="mini-action-button"
                      disabled={!snapshot?.tradingview_cdp.available || chartActionBusyId === asText(task, "id")}
                      onClick={() => void runTradingViewChartAction(task)}
                      type="button"
                    >
                      {chartActionBusyId === asText(task, "id") ? "Capturing" : "Capture"}
                    </button>
                  </div>
                </article>
              ))}
              {snapshot?.tradingview_tasks.length ? null : (
                <EmptyState message={snapshot ? "No TradingView tasks are queued in Postgres." : "Waiting for live warehouse snapshot."} />
              )}
            </div>
          </Panel>

          <Panel className="span-4" icon={<Bell size={17} />} title="TradingView Alert Inbox" action="human gated">
            <div className="alert-list">
              {dashboardTradingViewAlertRequests.length ? (
                dashboardTradingViewAlertRequests.map((request) => {
                  const approvalId = asText(request, "approval_id");
                  const approvalStatus = asText(request, "approval_status", "pending");
                  return (
                    <article className="alert-row" key={approvalId}>
                      <div>
                        <strong>{asText(request, "symbol", "SYMBOL")}</strong>
                        <span>{asText(request, "exchange", "NSE")} · {asText(request, "timeframe", "D")} · task {asText(request, "tradingview_task_id", "n/a")}</span>
                      </div>
                      <p>{asText(request, "alert_condition", asText(request, "instruction", "Review alert request"))}</p>
                      <div className="row-footer">
                        <StatusBadge status={approvalStatus === "approved" ? "approved" : approvalStatus === "rejected" ? "blocked" : "needs_review"} />
                        {approvalStatus === "pending" ? (
                          <div className="approval-actions">
                            <button
                              className="icon-button approve"
                              disabled={tradingViewAlertBusyId === `${approvalId}:approved`}
                              onClick={() => void handleResolveTradingViewAlert(approvalId, "approved")}
                              title="Approve for manual alert creation"
                              type="button"
                            >
                              <Check size={15} aria-hidden="true" />
                            </button>
                            <button
                              className="icon-button reject"
                              disabled={tradingViewAlertBusyId === `${approvalId}:rejected`}
                              onClick={() => void handleResolveTradingViewAlert(approvalId, "rejected")}
                              title="Reject alert request"
                              type="button"
                            >
                              <X size={15} aria-hidden="true" />
                            </button>
                          </div>
                        ) : (
                          <small>{asText(request, "alert_request_state", approvalStatus)}</small>
                        )}
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No TradingView alert approval requests are open." />
              )}
            </div>
          </Panel>

          <Panel className="span-4" icon={<Building2 size={17} />} title="Manual Portfolio Updates" action="staged">
            <form className="manual-form" onSubmit={stageManualHolding}>
              <div className="field-grid">
                <label>
                  Client
                  <input
                    onChange={(event) => setHoldingDraft((current) => ({ ...current, clientCode: event.target.value }))}
                    placeholder="Client code"
                    value={holdingDraft.clientCode}
                  />
                </label>
                <label>
                  Account
                  <input
                    onChange={(event) => setHoldingDraft((current) => ({ ...current, accountCode: event.target.value }))}
                    placeholder="Account code"
                    value={holdingDraft.accountCode}
                  />
                </label>
                <label>
                  Symbol
                  <input
                    onChange={(event) => setHoldingDraft((current) => ({ ...current, symbol: event.target.value }))}
                    placeholder="NSE symbol"
                    value={holdingDraft.symbol}
                  />
                </label>
                <label>
                  Qty
                  <input
                    inputMode="decimal"
                    onChange={(event) => setHoldingDraft((current) => ({ ...current, quantity: event.target.value }))}
                    placeholder="0"
                    value={holdingDraft.quantity}
                  />
                </label>
              </div>
              <button className="primary-button" disabled={holdingBusy} type="submit">
                <Plus size={16} aria-hidden="true" />
                {holdingBusy ? "Writing" : "Stage"}
              </button>
            </form>
            <div className="manual-update-list">
              {manualUpdates.length ? (
                manualUpdates.slice(0, 4).map((update) => (
                  <article className="manual-update-row" key={update.id}>
                    <div>
                      <strong>{update.symbol}</strong>
                      <span>{update.clientCode} / {update.accountCode}</span>
                    </div>
                    <span>{update.quantity}</span>
                    <StatusPill status={update.status} />
                  </article>
                ))
              ) : (
                <EmptyState message="No staged holding updates in portfolio.manual_holding_updates." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<GitBranch size={17} />} title="Data Sources" action="registry">
            <div className="source-grid">
              {dashboardSources.length ? (
                dashboardSources.map((source) => (
                  <article className="source-card" key={source.key}>
                    <div className="row-title">
                      <strong>{source.name}</strong>
                      <StatusPill status={source.status} />
                    </div>
                    <p>{source.type}</p>
                    <div className="source-meta">
                      <span>{source.provider}</span>
                      <span>{source.cadence}</span>
                      <span>{source.owner}</span>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No data-source registry rows loaded from the warehouse." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<DatabaseZap size={17} />} title="Model Endpoint Control" action="plug-in ready">
            <div className="source-check-list">
              {dashboardModelEndpoints.length ? (
                dashboardModelEndpoints.map((endpoint) => {
                  const endpointKey = asText(endpoint, "endpoint_key");
                  return (
                    <article className="source-check-row" key={endpointKey}>
                      <div>
                        <strong>{asText(endpoint, "endpoint_name", endpointKey)}</strong>
                        <p>{asText(endpoint, "provider", "provider")} / {asText(endpoint, "model_name", "model")} · {asText(endpoint, "route_name", "route")}</p>
                      </div>
                      <StatusPill status={asText(endpoint, "health_status", "unchecked")} />
                      <button
                        className="mini-action-button"
                        disabled={modelEndpointBusyId === `register:${endpointKey}`}
                        onClick={() => void handleRegisterModelEndpoint(endpoint)}
                        type="button"
                      >
                        Save
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={modelEndpointBusyId === `check:${endpointKey}`}
                        onClick={() => void handleCheckModelEndpoint(endpointKey)}
                        type="button"
                      >
                        Check
                      </button>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No model endpoints found. Run the endpoint registry migration before wiring agents to models." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<GitBranch size={17} />} title="Source Connector Control" action="secret-ref only">
            <div className="source-check-list">
              {dashboardSourceConnectors.length ? (
                dashboardSourceConnectors.map((connector) => {
                  const connectorKey = asText(connector, "connector_key");
                  return (
                    <article className="source-check-row" key={connectorKey}>
                      <div>
                        <strong>{asText(connector, "connector_name", connectorKey)}</strong>
                        <p>{asText(connector, "source_key", "source")} · {asText(connector, "access_mode", "read_only")} · {asText(connector, "owner_agent", "Data Steward")}</p>
                      </div>
                      <StatusPill status={asText(connector, "health_status", "unchecked")} />
                      <button
                        className="mini-action-button"
                        disabled={sourceConnectorBusyId === `register:${connectorKey}`}
                        onClick={() => void handleRegisterSourceConnector(connector)}
                        type="button"
                      >
                        Save
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={sourceConnectorBusyId === `check:${connectorKey}`}
                        onClick={() => void handleCheckSourceConnector(connectorKey)}
                        type="button"
                      >
                        Check
                      </button>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No source connector profiles found. Register sources before plugging them into agents." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<DatabaseZap size={17} />} title="Provider Readiness Board" action={`${asText(dashboardProviderReadinessSummary.find((row) => asText(row, "metric") === "ready_providers") ?? {}, "value", "0")} ready`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={providerReadinessBusy} onClick={() => void runProviderReadinessFromDashboard()} type="button">
                {providerReadinessBusy ? "Sweeping..." : "Run readiness sweep"}
              </button>
            </div>
            <div className="employee-profile-summary">
              {dashboardProviderReadinessSummary.length ? (
                dashboardProviderReadinessSummary.map((metric) => (
                  <div className="employee-profile-metric" key={asText(metric, "metric")}>
                    <strong>{asText(metric, "value", "0")}</strong>
                    <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                  </div>
                ))
              ) : (
                <div className="employee-profile-metric">
                  <strong>0</strong>
                  <span>readiness rows</span>
                </div>
              )}
            </div>
            <div className="source-check-list">
              {dashboardProviderReadiness.length ? (
                dashboardProviderReadiness.map((provider) => (
                  <article className="source-check-row" key={`${asText(provider, "provider_kind")}-${asText(provider, "provider_key")}`}>
                    <div>
                      <strong>{asText(provider, "provider_name", asText(provider, "provider_key", "Provider"))}</strong>
                      <p>{asText(provider, "provider_kind", "provider").replace(/_/g, " ")} · {asText(provider, "subject_name", "subject")} · {asText(provider, "next_action", "No next action recorded.")}</p>
                    </div>
                    <StatusPill status={asText(provider, "readiness_status", "unknown")} />
                    <span>{asText(provider, "owner_agent", "owner")}</span>
                    <button
                      className="mini-action-button"
                      disabled={providerAssignmentBusyId === asText(provider, "provider_key")}
                      onClick={() => void evaluateProviderAssignmentFromDashboard(provider)}
                      type="button"
                    >
                      {providerAssignmentBusyId === asText(provider, "provider_key") ? "Gating..." : "Gate"}
                    </button>
                    <small>assign {asText(provider, "assignable", "false")} · browser {asText(provider, "browser_ready", "true")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No provider readiness rows yet. Run readiness sweep after registering model endpoints and source connectors." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardProviderReadinessRuns.length ? (
                dashboardProviderReadinessRuns.map((run) => (
                  <article className="source-check-row" key={asText(run, "run_key")}>
                    <div>
                      <strong>{asText(run, "run_key", "readiness run")}</strong>
                      <p>models {asText(run, "model_checks_run", "0")} · sources {asText(run, "source_checks_run", "0")} · blocked {asText(run, "blocked_count", "0")}</p>
                    </div>
                    <StatusPill status={asText(run, "status", "unknown")} />
                    <span>{asText(run, "ready_count", "0")} ready</span>
                    <time>{compactDate(run.finished_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No readiness sweeps recorded yet." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardProviderAssignmentGates.length ? (
                dashboardProviderAssignmentGates.map((gate) => (
                  <article className="source-check-row" key={asText(gate, "gate_key")}>
                    <div>
                      <strong>{asText(gate, "provider_key", "provider")}</strong>
                      <p>{asText(gate, "requested_use", "provider assignment")} · {asText(gate, "policy_reason", asText(gate, "next_action", "No next action recorded."))}</p>
                    </div>
                    <StatusPill status={asText(gate, "assignment_status", "unknown")} />
                    <span>{asText(gate, "department_key", asText(gate, "requesting_agent", "agent"))}</span>
                    <small>policy {asText(gate, "policy_status", "-")} · allowed {asText(gate, "assignment_allowed", "false")} · inbox {asText(gate, "inbox_item_id", "-")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No provider assignment gates yet. Use Gate on a provider row before assigning it to agents." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardDepartmentProviderPolicies.length ? (
                dashboardDepartmentProviderPolicies.map((policy) => (
                  <article className="source-check-row" key={asText(policy, "policy_key")}>
                    <div>
                      <strong>{asText(policy, "policy_key", "policy")}</strong>
                      <p>{asText(policy, "department_name", asText(policy, "department_key", "department"))} · {asText(policy, "provider_kind", "provider")} · {asText(policy, "reason", "No reason recorded.")}</p>
                    </div>
                    <StatusPill status={asText(policy, "policy_status", "unknown")} />
                    <span>{asText(policy, "provider_key_pattern", "*")}</span>
                    <small>route {asText(policy, "route_or_source_pattern", "*")} · provider {asText(policy, "provider_pattern", "*")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No department provider policies loaded yet." />
              )}
            </div>
            <div className="source-check-list">
              {dashboardTaskProviderGates.length ? (
                dashboardTaskProviderGates.map((taskGate) => (
                  <article className="source-check-row" key={asText(taskGate, "task_id")}>
                    <div>
                      <strong>{asText(taskGate, "title", "Task provider gate")}</strong>
                      <p>{asText(taskGate, "owner_agent", "agent")} · gates {asText(taskGate, "provider_gate_count", "0")} · blocked {asText(taskGate, "blocked_provider_gates", "0")}</p>
                    </div>
                    <StatusPill status={asText(taskGate, "provider_gate_status", "not_checked")} />
                    <span>{asText(taskGate, "task_status", "status")}</span>
                    <small>passed {asText(taskGate, "passed_provider_gates", "0")} · approval {asText(taskGate, "approval_required_provider_gates", "0")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No task provider gates yet. New agent tasks will be checked automatically." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<Search size={17} />} title="Browser Profile Control" action="CDP / public web">
            <div className="source-check-list">
              {dashboardBrowserProfiles.length ? (
                dashboardBrowserProfiles.map((profile) => {
                  const profileKey = asText(profile, "profile_key");
                  return (
                    <article className="source-check-row" key={profileKey}>
                      <div>
                        <strong>{asText(profile, "profile_name", profileKey)}</strong>
                        <p>{asText(profile, "browser_name", "browser")} · {asText(profile, "use_case", "browser work")}</p>
                      </div>
                      <StatusPill status={asText(profile, "health_status", "unchecked")} />
                      <button
                        className="mini-action-button"
                        disabled={browserProfileBusyId === `register:${profileKey}`}
                        onClick={() => void handleRegisterBrowserProfile(profile)}
                        type="button"
                      >
                        Save
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={browserProfileBusyId === `check:${profileKey}`}
                        onClick={() => void handleCheckBrowserProfile(profileKey)}
                        type="button"
                      >
                        Check
                      </button>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No browser profiles found. Browser-dependent connectors cannot become live without profiles." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<GitBranch size={17} />} title="Browser Connector Links" action="source gates">
            <div className="source-check-list">
              {dashboardBrowserLinks.length ? (
                dashboardBrowserLinks.map((link) => {
                  const profileKey = asText(link, "profile_key");
                  const connectorKey = asText(link, "connector_key");
                  const busyKey = `${profileKey}:${connectorKey}`;
                  return (
                    <article className="source-check-row" key={busyKey}>
                      <div>
                        <strong>{connectorKey}</strong>
                        <p>{profileKey} · {asText(link, "provider", "provider")} · {asText(link, "source_key", "source")}</p>
                      </div>
                      <StatusPill status={asText(link, "profile_health_status", "unchecked")} />
                      <button
                        className="mini-action-button"
                        disabled={browserProfileBusyId === `attach:${busyKey}`}
                        onClick={() => void handleAttachBrowserProfile(profileKey, connectorKey)}
                        type="button"
                      >
                        Link
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={browserProfileBusyId === `check:${busyKey}`}
                        onClick={() => void handleCheckBrowserProfile(profileKey, connectorKey)}
                        type="button"
                      >
                        Check
                      </button>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No browser profiles are linked to source connectors yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<FlaskConical size={17} />} title="Strategy Registry" action="paper first">
            <div className="strategy-list">
              {dashboardStrategies.length ? (
                dashboardStrategies.map((strategy) => (
                  <article className="strategy-row" key={strategy.key}>
                    <div>
                      <strong>{strategy.name}</strong>
                      <p>{strategy.family} · {strategy.timeframe}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{strategy.mode}</span>
                      <SeverityBadge severity={strategy.risk} />
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No strategy registry rows loaded from the warehouse." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Sparkles size={17} />} title="Strategy Intake" action="Charlie routes">
            <form className="strategy-intake-form" onSubmit={submitStrategyIntake}>
              <div className="field-grid">
                <label>
                  Name
                  <input
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="ATR mean reversion"
                    value={strategyDraft.name}
                  />
                </label>
                <label>
                  Family
                  <select
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, family: event.target.value }))}
                    value={strategyDraft.family}
                  >
                    <option value="quant">Quant</option>
                    <option value="intraday">Intraday</option>
                    <option value="options">Options</option>
                    <option value="special_situations">Special situations</option>
                    <option value="long_term">Long-term overlay</option>
                  </select>
                </label>
                <label>
                  Universe
                  <input
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, universe: event.target.value }))}
                    placeholder="NSE, crypto, clients"
                    value={strategyDraft.universe}
                  />
                </label>
                <label>
                  Template
                  <select
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, template: event.target.value }))}
                    value={strategyDraft.template}
                  >
                    <option value="momentum">Momentum</option>
                    <option value="mean_reversion">Mean reversion</option>
                    <option value="breakout">Breakout</option>
                    <option value="low_volatility">Low volatility</option>
                  </select>
                </label>
                <label>
                  Timeframe
                  <select
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, timeframe: event.target.value }))}
                    value={strategyDraft.timeframe}
                  >
                    <option value="intraday">Intraday</option>
                    <option value="intraday_to_days">Intraday to days</option>
                    <option value="days_to_weeks">Days to weeks</option>
                    <option value="weeks_to_months">Weeks to months</option>
                    <option value="multi_year">Multi-year</option>
                  </select>
                </label>
                <label>
                  Symbols
                  <input
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, symbols: event.target.value }))}
                    placeholder="RELIANCE, NIFTY"
                    value={strategyDraft.symbols}
                  />
                </label>
                <label>
                  Asset
                  <select
                    onChange={(event) => setStrategyDraft((current) => ({ ...current, assetClass: event.target.value }))}
                    value={strategyDraft.assetClass}
                  >
                    <option value="equity">Equity</option>
                    <option value="options">Options</option>
                    <option value="crypto">Crypto</option>
                    <option value="commodity">Commodity</option>
                    <option value="multi_asset">Multi-asset</option>
                  </select>
                </label>
              </div>
              <label className="wide-field">
                Strategy idea
                <textarea
                  onChange={(event) => setStrategyDraft((current) => ({ ...current, intakeText: event.target.value }))}
                  placeholder="Describe entry, exit, risk, data needed, and what you want the agents to test."
                  rows={4}
                  value={strategyDraft.intakeText}
                />
              </label>
              <label className="wide-field">
                Constraints
                <textarea
                  onChange={(event) => setStrategyDraft((current) => ({ ...current, constraintsText: event.target.value }))}
                  placeholder="Capital, instruments, holding period, no-trade rules."
                  rows={2}
                  value={strategyDraft.constraintsText}
                />
              </label>
              <button className="primary-button" disabled={strategyIntakeBusy} type="submit">
                <Plus size={16} aria-hidden="true" />
                {strategyIntakeBusy ? "Queuing" : "Queue Strategy"}
              </button>
              <button className="secondary-button" disabled={userStrategyOptimizerBusy || !strategyDraft.intakeText.trim()} onClick={() => void runUserDefinedOptimizerFromDraft()} type="button">
                <Gauge size={16} aria-hidden="true" />
                {userStrategyOptimizerBusy ? "Optimizing" : "Queue + Optimize"}
              </button>
            </form>
          </Panel>

          <Panel className="span-7" icon={<ListChecks size={17} />} title="Strategy Template Library" action={`${dashboardStrategyTemplates.length} templates`}>
            <div className="strategy-summary-strip">
              {dashboardStrategyTemplateSummary.slice(0, 6).map((metric) => (
                <div className="strategy-summary-cell" key={asText(metric, "metric")}>
                  <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                  <strong>{asText(metric, "value", "0")}</strong>
                </div>
              ))}
              {!dashboardStrategyTemplateSummary.length ? (
                <div className="strategy-summary-cell">
                  <span>templates</span>
                  <strong>0</strong>
                </div>
              ) : null}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyTemplates.length ? (
                dashboardStrategyTemplates.map((template) => {
                  const templateKey = asText(template, "template_key");
                  const requirements = asStringArray(template, "data_requirements").slice(0, 3).join(", ");
                  return (
                    <article className="strategy-row" key={templateKey}>
                      <div>
                        <strong>{asText(template, "template_name", "Strategy template")}</strong>
                        <p>{asText(template, "template_family", "family")} · {asText(template, "asset_class", "asset")} · {asText(template, "engine_template", "engine")} · {asText(template, "default_timeframe", "tf")}</p>
                        <small>{requirements || asText(template, "description", "data requirements pending")}</small>
                      </div>
                      <div className="strategy-right">
                        <span>{asText(template, "execution_readiness", "research")}</span>
                        <small>used {asText(template, "application_count", "0")} · {asText(template, "owner_agent", "Strategy Intake Agent")}</small>
                        <button
                          className="mini-action-button"
                          disabled={Boolean(strategyTemplateBusyKey)}
                          onClick={() => void queueStrategyTemplateFromDashboard(template)}
                          type="button"
                        >
                          {strategyTemplateBusyKey === templateKey ? "Queuing" : "Queue"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No strategy templates loaded from the warehouse." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyTemplateApplications.length ? (
                dashboardStrategyTemplateApplications.map((application) => (
                  <article className="strategy-row" key={asText(application, "application_key", asText(application, "id"))}>
                    <div>
                      <strong>{asText(application, "strategy_name", "Template application")}</strong>
                      <p>{asText(application, "template_name", "template")} · {asText(application, "status", "queued")} · {asText(application, "candidate_key", "candidate pending")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(application, "execution_readiness", "research")}</span>
                      <small>{asText(application, "timeframe", "tf")} · {asText(application, "activation_gate", "paper_first")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No template applications yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Gauge size={17} />} title="User Strategy Optimizer" action={`${dashboardUserOptimizerRuns.length} runs`}>
            <div className="strategy-list compact-list">
              {dashboardUserOptimizerRuns.length ? (
                dashboardUserOptimizerRuns.map((run) => (
                  <article className="strategy-row" key={asText(run, "run_key")}>
                    <div>
                      <strong>{asText(run, "strategy_name", "User strategy")}</strong>
                      <p>{asText(run, "status", "queued")} · {asText(run, "current_stage", "intake")} · {asText(run, "requested_template", "template")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(run, "requested_timeframe", "tf")}</span>
                      <small>bt {asText(run, "backtest_run_id", "n/a")} · opt {asText(run, "optimization_run_id", "n/a")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No user-defined optimizer runs yet. Use Queue + Optimize from Strategy Intake." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<Search size={17} />} title="Strategy Discovery Agent" action={`${dashboardStrategyDiscoveryTriage.length || dashboardStrategyDiscoveryCandidates.length} candidates`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={newsIngestionBusy} onClick={() => void ingestMarketNewsFromDashboard()} type="button">
                {newsIngestionBusy ? "Ingesting News" : "Ingest News"}
              </button>
              <button className="mini-action-button" disabled={strategyDiscoverySchedulerBusy} onClick={() => void runStrategyDiscoverySchedulerFromDashboard()} type="button">
                {strategyDiscoverySchedulerBusy ? "Running Source Loop" : "Source + Discovery"}
              </button>
              <button className="mini-action-button" disabled={strategyDiscoveryBusy} onClick={() => void runStrategyDiscoveryFromDashboard()} type="button">
                {strategyDiscoveryBusy ? "Scanning" : "Run Discovery"}
              </button>
              <button className="mini-action-button" disabled={strategyDossierBusy} onClick={() => void buildStrategyDossiersFromDashboard()} type="button">
                {strategyDossierBusy ? "Building Dossiers" : "Build Dossiers"}
              </button>
              <small>{dashboardStrategyDiscoverySchedulerRuns.length ? `scheduler ${asText(dashboardStrategyDiscoverySchedulerRuns[0], "status", "ready")}` : "rss/news, research, journals, signals, components"}</small>
            </div>
            <div className="strategy-summary-strip">
              <div className="strategy-summary-cell">
                <span>scheduler</span>
                <strong>{dashboardStrategyDiscoverySchedulerRuns.length ? asText(dashboardStrategyDiscoverySchedulerRuns[0], "generated_idea_count", "0") : "0"}</strong>
              </div>
              <div className="strategy-summary-cell">
                <span>news upserted</span>
                <strong>{dashboardNewsIngestionRuns.length ? asText(dashboardNewsIngestionRuns[0], "items_upserted", "0") : "0"}</strong>
              </div>
              <div className="strategy-summary-cell">
                <span>news ideas</span>
                <strong>{dashboardNewsIngestionRuns.length ? asText(dashboardNewsIngestionRuns[0], "research_ideas_created", "0") : "0"}</strong>
              </div>
              <div className="strategy-summary-cell">
                <span>x/twitter</span>
                <strong>blocked</strong>
              </div>
              <div className="strategy-summary-cell">
                <span>dossiers</span>
                <strong>{dashboardStrategyIdeaDossierBuildRuns.length ? asText(dashboardStrategyIdeaDossierBuildRuns[0], "dossiers_upserted", String(dashboardStrategyIdeaDossiers.length)) : String(dashboardStrategyIdeaDossiers.length)}</strong>
              </div>
              <div className="strategy-summary-cell">
                <span>actions</span>
                <strong>{dashboardStrategyIdeaDossierActions.length ? asText(dashboardStrategyIdeaDossierActions[0], "action_type", "ready") : "0"}</strong>
              </div>
            </div>
            <form
              className="strategy-intake-form"
              onSubmit={(event) => {
                event.preventDefault();
                void searchStrategyDossiersFromDashboard();
              }}
            >
              <div className="field-grid">
                <label>
                  Dossier Search
                  <input
                    onChange={(event) => setStrategyDossierSearchQuery(event.target.value)}
                    placeholder="TATASTEEL optimizer committee"
                    value={strategyDossierSearchQuery}
                  />
                </label>
                <label>
                  Latest Search
                  <input
                    readOnly
                    value={
                      dashboardStrategyIdeaDossierSearchRuns.length
                        ? `${asText(dashboardStrategyIdeaDossierSearchRuns[0], "search_mode", "ready")} · ${asText(dashboardStrategyIdeaDossierSearchRuns[0], "match_count", "0")} matches`
                        : "No search runs yet"
                    }
                  />
                </label>
              </div>
              <button className="mini-action-button" disabled={strategyDossierSearchBusy || !strategyDossierSearchQuery.trim()} type="submit">
                {strategyDossierSearchBusy ? "Searching Dossiers" : "Search Dossiers"}
              </button>
              {dashboardStrategyIdeaDossierSearchRuns.length ? (
                <small>
                  {asText(dashboardStrategyIdeaDossierSearchRuns[0], "embedding_model", "embedding")} · qdrant {asText(dashboardStrategyIdeaDossierSearchRuns[0], "qdrant_available", "false")} · fallback {asText(dashboardStrategyIdeaDossierSearchRuns[0], "fallback_used", "false")}
                </small>
              ) : null}
            </form>
            <div className="strategy-list compact-list">
              {dashboardStrategyDossierSearchResultRows.length ? (
                dashboardStrategyDossierSearchResultRows.map((row, index) => (
                  <article className="strategy-row" key={`${asText(row, "dossier_key", "search-result")}-${index}`}>
                    <div>
                      <strong>{asText(row, "title", "Matched dossier")}</strong>
                      <p>{asText(row, "recommended_next_action", "review")} · {asText(row, "note_path", "no note")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "match_source", "search")} · {asText(row, "vector_score", asText(row, "lexical_score", "score"))}</span>
                      <small>{asText(row, "qdrant_index_status", "pending")} · {asText(row, "symbols", "[]")}</small>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "request_more_evidence")} type="button">
                        Evidence
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "route_quant_lab")} type="button">
                        Quant
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "route_special_situation")} type="button">
                        Special
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "open_committee_review")} type="button">
                        Committee
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "generate_committee_memo")} type="button">
                        Memo
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="Search strategy memory to recall existing dossiers before creating duplicate ideas." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyIdeaDossiers.length ? (
                dashboardStrategyIdeaDossiers.map((row) => (
                  <article className="strategy-row" key={asText(row, "dossier_key")}>
                    <div>
                      <strong>{asText(row, "title", "Strategy dossier")}</strong>
                      <p>{asText(row, "status", "active")} · {asText(row, "recommended_next_action", "review")} · {asText(row, "note_path", "no note")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "discovery_count", "0")} discoveries · {asText(row, "triage_decision_count", "0")} triage</span>
                      <small>qdrant {asText(row, "qdrant_index_status", "pending")} · broker {asText(row, "broker_order_allowed", "false")}</small>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "request_more_evidence")} type="button">
                        Evidence
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "route_quant_lab")} type="button">
                        Quant
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "route_special_situation")} type="button">
                        Special
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "open_committee_review")} type="button">
                        Committee
                      </button>
                      <button className="mini-action-button" disabled={Boolean(strategyDossierActionBusyId)} onClick={() => void runDossierActionFromDashboard(row, "generate_committee_memo")} type="button">
                        Memo
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No persistent idea dossiers yet. Build Dossiers after discovery or triage." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyIdeaDossierActions.length ? (
                dashboardStrategyIdeaDossierActions.map((row) => (
                  <article className="strategy-row" key={asText(row, "action_key", asText(row, "id"))}>
                    <div>
                      <strong>{asText(row, "action_type", "dossier action")}</strong>
                      <p>{asText(row, "dossier_title", "Dossier")} · {asText(row, "target_agent", "agent")} · {asText(row, "target_table", "target")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "status", "completed")}</span>
                      <small>broker {asText(row, "broker_order_allowed", "false")} · live {asText(row, "autonomous_live_execution_allowed", "false")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No dossier actions yet. Use Evidence, Quant, Special, Committee, or Memo from a dossier." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardLatestNewsItems.length ? (
                dashboardLatestNewsItems.map((row) => (
                  <article className="strategy-row" key={asText(row, "id")}>
                    <div>
                      <strong>{asText(row, "title", "Market news")}</strong>
                      <p>{asText(row, "source_name", "source")} · {asText(row, "topics", "topics")} · {asText(row, "published_at", asText(row, "captured_at", "captured"))}</p>
                    </div>
                    <div className="strategy-right">
                      <span>rel {asText(row, "relevance_score", "0")}</span>
                      <small>{asText(row, "symbols", "[]")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No RSS/news rows captured yet. Run Ingest News or Source + Discovery." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyDiscoveryTriageDecisions.length ? (
                dashboardStrategyDiscoveryTriageDecisions.map((row) => (
                  <article className="strategy-row" key={asText(row, "id")}>
                    <div>
                      <strong>{asText(row, "decision", "decision")} · {asText(row, "title", "discovered idea")}</strong>
                      <p>{asText(row, "routed_to_agent", "no route")} · inbox {asText(row, "inbox_status", "none")} · committee {asText(row, "committee_review_status", "none")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "decided_by", "Charlie")}</span>
                      <small>broker {asText(row, "broker_order_allowed", "false")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No Charlie/Jarvis triage decisions yet." />
              )}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyDiscoveryTriage.length ? (
                dashboardStrategyDiscoveryTriage.map((row) => {
                  const candidateId = asText(row, "id");
                  const busyPrefix = `${candidateId}:`;
                  const committeeDisabled = !asText(row, "optimization_run_id") || strategyTriageBusyId !== "" || asText(row, "triage_decision", "unreviewed") !== "unreviewed";
                  const decisionDisabled = strategyTriageBusyId !== "" || asText(row, "triage_decision", "unreviewed") !== "unreviewed";
                  return (
                  <article className="strategy-row" key={asText(row, "discovery_key")}>
                    <div>
                      <strong>{asText(row, "title", "Discovered strategy")}</strong>
                      <p>{asText(row, "source_kind", "source")} · triage {asText(row, "triage_decision", "unreviewed")} · {asText(row, "recommended_triage_action", "review")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "template", "template")} · {asText(row, "timeframe", "tf")}</span>
                      <small>opt {asText(row, "optimizer_status", "not routed")} · broker {asText(row, "broker_order_allowed", "false")}</small>
                      <button
                        className="mini-action-button"
                        disabled={decisionDisabled}
                        onClick={() => void resolveDiscoveryTriageFromDashboard(row, "request_more_evidence")}
                        type="button"
                      >
                        {strategyTriageBusyId === `${busyPrefix}request_more_evidence` ? "Routing" : "Evidence"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={decisionDisabled}
                        onClick={() => void resolveDiscoveryTriageFromDashboard(row, "route_quant_lab")}
                        type="button"
                      >
                        {strategyTriageBusyId === `${busyPrefix}route_quant_lab` ? "Routing" : "Quant"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={decisionDisabled}
                        onClick={() => void resolveDiscoveryTriageFromDashboard(row, "route_special_situation")}
                        type="button"
                      >
                        {strategyTriageBusyId === `${busyPrefix}route_special_situation` ? "Routing" : "Special"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={committeeDisabled}
                        onClick={() => void resolveDiscoveryTriageFromDashboard(row, "open_committee_review")}
                        type="button"
                      >
                        {strategyTriageBusyId === `${busyPrefix}open_committee_review` ? "Opening" : "Committee"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={decisionDisabled}
                        onClick={() => void resolveDiscoveryTriageFromDashboard(row, "reject")}
                        type="button"
                      >
                        {strategyTriageBusyId === `${busyPrefix}reject` ? "Rejecting" : "Reject"}
                      </button>
                    </div>
                  </article>
                  );
                })
              ) : (
                <EmptyState message="No automatic discovery runs yet. Run Discovery to scan research, journals, signals, and component patterns." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<ListChecks size={17} />} title="Strategy Arsenal Queue" action={`${dashboardStrategyArsenal.length} candidates`}>
            <div className="strategy-summary-strip">
              {dashboardStrategySummary.slice(0, 4).map((row) => (
                <div className="strategy-summary-cell" key={asText(row, "metric")}>
                  <span>{asText(row, "metric").replace(/_/g, " ")}</span>
                  <strong>{asText(row, "value", "0")}</strong>
                </div>
              ))}
            </div>
            <div className="strategy-list">
              {dashboardStrategyArsenal.length ? (
                dashboardStrategyArsenal.map((candidate) => (
                  <article className="strategy-row" key={asText(candidate, "candidate_key")}>
                    <div>
                      <strong>{asText(candidate, "strategy_name", "Strategy candidate")}</strong>
                      <p>
                        {asText(candidate, "strategy_family", "quant")} · {asText(candidate, "timeframe", "mixed")} · {asText(candidate, "activation_gate", "paper_first")}
                      </p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(candidate, "candidate_status", "research")}</span>
                      <small>{asText(candidate, "backtest_runs", "0")} backtests · {asText(candidate, "validation_reviews", "0")} reviews</small>
                      <button
                        className="mini-action-button"
                        disabled={strategyDslBusyId === asText(candidate, "candidate_id")}
                        onClick={() => void parseCandidateDsl(candidate)}
                        type="button"
                      >
                        {strategyDslBusyId === asText(candidate, "candidate_id") ? "Parsing" : "Parse"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={dataQualityBusyId === asText(candidate, "candidate_id")}
                        onClick={() => void checkCandidateDataQuality(candidate)}
                        type="button"
                      >
                        {dataQualityBusyId === asText(candidate, "candidate_id") ? "Checking" : "Gate"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={backtestBusyId === asText(candidate, "candidate_id")}
                        onClick={() => void runCandidateBacktest(candidate)}
                        type="button"
                      >
                        {backtestBusyId === asText(candidate, "candidate_id") ? "Running" : "Backtest"}
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={optimizeBusyId === asText(candidate, "candidate_id")}
                        onClick={() => void runCandidateOptimization(candidate)}
                        type="button"
                      >
                        {optimizeBusyId === asText(candidate, "candidate_id") ? "Optimizing" : "Optimize"}
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No strategy candidates queued yet. Submit a strategy idea to Charlie." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<DatabaseZap size={17} />} title="Strategy DSL & Data Gate" action={`${dashboardStrategyDataQualityGates.length} gates`}>
            <div className="strategy-list compact-list">
              {dashboardStrategyDslReadiness.length ? (
                dashboardStrategyDslReadiness.slice(0, 5).map((row) => (
                  <article className="strategy-row" key={asText(row, "candidate_key")}>
                    <div>
                      <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                      <p>
                        parse {asText(row, "parse_status", "not_parsed")} · data {asText(row, "data_quality_status", "not_checked")}
                      </p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "template", "template pending")}</span>
                      <small>{asText(row, "total_rows", "0")} rows · min {asText(row, "min_symbol_rows", "0")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No strategy DSL or data-quality gate rows yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<BarChart3 size={17} />} title="Quant Analytics" action={`${dashboardQuantAnalyticsRuns.length} runs`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={quantAnalyticsBusy} onClick={() => void runQuantAnalyticsFromDashboard()} type="button">
                {quantAnalyticsBusy ? "Running" : "Run Analytics"}
              </button>
            </div>
            <div className="strategy-summary-strip">
              {dashboardQuantAnalyticsRuns.slice(0, 1).map((run) => (
                <div className="strategy-summary-cell" key={asText(run, "run_key")}>
                  <span>{asText(run, "run_key", "latest run")}</span>
                  <strong>{asText(run, "status", "pending")}</strong>
                  <small>{asText(run, "quality_flags", "no flags")}</small>
                </div>
              ))}
              {dashboardQuantOptimizerRuns.slice(0, 1).map((run) => (
                <div className="strategy-summary-cell" key={`${asText(run, "run_key")}-optimizer`}>
                  <span>optimizer</span>
                  <strong>{asText(run, "candidate_count", "0")} strategies</strong>
                  <small>Sharpe {asText(run, "sharpe_proxy", "n/a")}</small>
                </div>
              ))}
            </div>
            <div className="strategy-list compact-list">
              {dashboardQuantRegimes.length || dashboardQuantFactors.length ? (
                <>
                  {dashboardQuantRegimes.slice(0, 2).map((row) => (
                    <article className="strategy-row" key={`${asText(row, "id")}-regime`}>
                      <div>
                        <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                        <p>{asText(row, "regime_label", "regime")} · {asText(row, "bars", "0")} bars</p>
                      </div>
                      <div className="strategy-right">
                        <span>regime</span>
                        <small>Return {asText(row, "total_return", "n/a")}</small>
                      </div>
                    </article>
                  ))}
                  {dashboardQuantFactors.slice(0, 2).map((row) => (
                    <article className="strategy-row" key={`${asText(row, "id")}-factor`}>
                      <div>
                        <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                        <p>{asText(row, "factor_name", "factor")} · {asText(row, "method", "proxy")}</p>
                      </div>
                      <div className="strategy-right">
                        <span>factor</span>
                        <small>Exposure {asText(row, "exposure", "n/a")}</small>
                      </div>
                    </article>
                  ))}
                </>
              ) : (
                <EmptyState message="No quant analytics run yet. Run analytics after strategy DSL and data gates." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<ShieldCheck size={17} />} title="Strategy Portfolio Risk" action={`${dashboardStrategyAllocationRuns.length} runs`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={strategyAllocationBusy} onClick={() => void runStrategyAllocationFromDashboard()} type="button">
                {strategyAllocationBusy ? "Allocating" : "Run Allocation"}
              </button>
            </div>
            <div className="strategy-summary-strip">
              {dashboardStrategyAllocationRuns.slice(0, 1).map((run) => (
                <div className="strategy-summary-cell" key={asText(run, "allocation_key")}>
                  <span>{asText(run, "allocation_key", "allocation")}</span>
                  <strong>{asText(run, "status", "draft")}</strong>
                  <small>{asText(run, "quality_flags", "no flags")}</small>
                </div>
              ))}
              {dashboardStrategyRuin.slice(0, 1).map((ruin) => (
                <div className="strategy-summary-cell" key={`${asText(ruin, "allocation_key")}-ruin`}>
                  <span>probability of ruin</span>
                  <strong>{asText(ruin, "ruin_probability", "n/a")}</strong>
                  <small>P05 {asText(ruin, "terminal_p05", "n/a")}</small>
                </div>
              ))}
            </div>
            <div className="strategy-list compact-list">
              {dashboardStrategyAllocations.length ? (
                dashboardStrategyAllocations.slice(0, 4).map((allocation) => (
                  <article className="strategy-row" key={`${asText(allocation, "allocation_key")}-${asText(allocation, "strategy_id")}`}>
                    <div>
                      <strong>{asText(allocation, "strategy_name", "Strategy")}</strong>
                      <p>{asText(allocation, "allocation_status", "paper_only")} · notional {asText(allocation, "target_notional", "0")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(allocation, "target_weight", "0")}</span>
                      <small>Risk {asText(allocation, "risk_contribution", "n/a")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No strategy portfolio allocation yet. Run allocation after quant analytics." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<ListChecks size={17} />} title="Quant Lab v2 - Retirement & Specialists" action={`${dashboardStrategyRetirement.length} reviews`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={strategyRetirementBusy} onClick={() => void runStrategyRetirementFromDashboard()} type="button">
                {strategyRetirementBusy ? "Reviewing" : "Run Retirement Review"}
              </button>
            </div>
            <div className="strategy-summary-strip">
              {dashboardStrategyRetirement.slice(0, 1).map((review) => (
                <div className="strategy-summary-cell" key={asText(review, "review_key")}>
                  <span>{asText(review, "strategy_name", "strategy")}</span>
                  <strong>{asText(review, "recommended_action", "watch")}</strong>
                  <small>{asText(review, "trigger_reasons", "no triggers")}</small>
                </div>
              ))}
              {dashboardQuantSpecialists.slice(0, 1).map((assignment) => (
                <div className="strategy-summary-cell" key={asText(assignment, "assignment_key")}>
                  <span>{asText(assignment, "specialist_agent", "specialist")}</span>
                  <strong>{asText(assignment, "status", "open")}</strong>
                  <small>{asText(assignment, "assignment_type", "review")}</small>
                </div>
              ))}
            </div>
            <div className="strategy-list compact-list">
              {dashboardQuantLabV2.length ? (
                dashboardQuantLabV2.slice(0, 5).map((row) => (
                  <article className="strategy-row" key={`${asText(row, "candidate_key")}-qlab-v2`}>
                    <div>
                      <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                      <p>
                        {asText(row, "review_status", "not reviewed")} · {asText(row, "recommended_action", "pending")} · {asText(row, "parse_status", "not_parsed")}
                      </p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "severity", "n/a")}</span>
                      <small>{asText(row, "open_assignments", "0")} open specialist tasks</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No Quant Lab v2 retirement rows yet. Run retirement review after analytics and allocation." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<CircleAlert size={17} />} title="Model Validation Agent" action={`${dashboardModelValidation.length} rows`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={modelValidationBusy} onClick={() => void runModelValidationFromDashboard()} type="button">
                {modelValidationBusy ? "Validating" : "Run Validation Sweep"}
              </button>
            </div>
            <div className="strategy-list compact-list">
              {dashboardModelValidation.length ? (
                dashboardModelValidation.slice(0, 5).map((row) => (
                  <article className="strategy-row" key={`${asText(row, "candidate_key")}-model-validation`}>
                    <div>
                      <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                      <p>{asText(row, "validation_gate_status", "pending")} · {asText(row, "decision", "no decision")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "overfit_risk", "risk n/a")}</span>
                      <small>{asText(row, "required_fixes", "no fixes")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No model-validation rows yet. Run validation after backtest/optimizer/retirement evidence." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Sparkles size={17} />} title="Trade Journal Strategy Miner" action={`${dashboardTradeJournalIdeas.length} ideas`}>
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={tradeJournalMiningBusy} onClick={() => void runTradeJournalMiningFromDashboard()} type="button">
                {tradeJournalMiningBusy ? "Mining" : "Mine Journals"}
              </button>
              <small>{dashboardTradeJournalMiningRuns.length ? asText(dashboardTradeJournalMiningRuns[0], "status", "ready") : "real journal data only"}</small>
            </div>
            <div className="strategy-list compact-list">
              {dashboardTradeJournalIdeas.length ? (
                dashboardTradeJournalIdeas.slice(0, 5).map((row) => (
                  <article className="strategy-row" key={`${asText(row, "pattern_key")}-journal-miner`}>
                    <div>
                      <strong>{asText(row, "idea_title", "Journal-mined idea")}</strong>
                      <p>{asText(row, "research_gate", "research")} · {asText(row, "next_required_action", "review")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "setup_type", "setup")} · {asText(row, "timeframe", "tf")}</span>
                      <small>{asText(row, "trade_count", "0")} rows · win {asText(row, "win_rate", "n/a")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No journal-mined strategy ideas yet. Add manual/paper/live trade rows, then mine journals." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<GitBranch size={17} />} title="Strategy Promotion Board" action={`${dashboardPromotionBoard.length} strategies`}>
            <div className="strategy-list compact-list">
              {dashboardPromotionBoard.length ? (
                dashboardPromotionBoard.slice(0, 5).map((row) => (
                  <article className="strategy-row" key={`${asText(row, "candidate_key")}-promotion`}>
                    <div>
                      <strong>{asText(row, "strategy_name", "Strategy")}</strong>
                      <p>{asText(row, "promotion_stage", "research")} · {asText(row, "next_required_action", "review")}</p>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(row, "validation_gate_status", "validation")}</span>
                      <small>broker {asText(row, "broker_order_allowed", "false")} · auto-live {asText(row, "autonomous_live_execution_allowed", "false")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No promotion-board rows yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Gauge size={17} />} title="Robustness Runs" action={`${dashboardStrategyOptimizations.length} runs`}>
            <div className="strategy-list">
              {dashboardStrategyOptimizations.length ? (
                dashboardStrategyOptimizations.map((run) => {
                  const metrics = asRecord(run.metrics);
                  return (
                    <article className="strategy-row" key={asText(run, "id")}>
                      <div>
                        <strong>{asText(run, "strategy_name", "Strategy")}</strong>
                        <p>
                          {asText(run, "optimizer_type", "optimizer")} · WF {String(metrics.best_walk_forward_consistency ?? "n/a")}
                        </p>
                      </div>
                      <div className="strategy-right">
                        <span>{asText(run, "status", "queued")}</span>
                        <small>Sharpe {String(metrics.best_walk_forward_test_sharpe ?? metrics.best_test_sharpe ?? "n/a")}</small>
                        <button
                          className="mini-action-button"
                          disabled={committeeBusyId === asText(run, "id")}
                          onClick={() => void openCommitteeReview(run)}
                          type="button"
                        >
                          {committeeBusyId === asText(run, "id") ? "Opening" : "Committee"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No optimization or walk-forward runs recorded yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<ShieldCheck size={17} />} title="Strategy Committee Gate" action={`${dashboardStrategyCommittee.length} reviews`}>
            <div className="strategy-list">
              {dashboardStrategyCommittee.length ? (
                dashboardStrategyCommittee.map((review) => {
                  const riskSummary = asRecord(review.risk_summary);
                  const killSwitch = asRecord(review.kill_switch_rules);
                  const reviewId = asText(review, "id");
                  const isFinal = asText(review, "decision_status", "pending") === "final";
                  const paperCandidate = asText(review, "recommended_decision") === "paper_monitor_candidate";
                  const paperAllowed = review.paper_monitor_allowed === true;
                  return (
                    <article className="strategy-row" key={reviewId}>
                      <div>
                        <strong>{asText(review, "strategy_name", "Strategy review")}</strong>
                        <p>
                          {asText(review, "recommended_decision", "review")} · {asText(review, "proposed_mode", "research")} · kill {String(killSwitch.max_drawdown_stop_pct ?? "n/a")}%
                        </p>
                        <small>{isFinal ? `Final: ${asText(review, "final_decision", "decided")}` : "Human decision pending"}</small>
                      </div>
                      <div className="strategy-right">
                        <SeverityBadge severity={asSeverity(review.risk_level, "high")} />
                        <small>WF {String(riskSummary.best_walk_forward_consistency ?? "n/a")} · {asText(review, "approval_status", "pending")}</small>
                        <small>{asText(review, "memo_status", "not_generated")}</small>
                        <button
                          className="mini-action-button"
                          disabled={memoBusyId === asText(review, "id")}
                          onClick={() => void generateCommitteeMemo(review)}
                          type="button"
                        >
                          {memoBusyId === asText(review, "id") ? "Writing" : "Memo"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={isFinal || committeeDecisionBusyId === `${reviewId}:retest`}
                          onClick={() => void decideCommitteeReview(review, "retest")}
                          type="button"
                        >
                          {committeeDecisionBusyId === `${reviewId}:retest` ? "Saving" : "Retest"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={isFinal || committeeDecisionBusyId === `${reviewId}:research_more`}
                          onClick={() => void decideCommitteeReview(review, "research_more")}
                          type="button"
                        >
                          {committeeDecisionBusyId === `${reviewId}:research_more` ? "Saving" : "Research"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={isFinal || committeeDecisionBusyId === `${reviewId}:reject`}
                          onClick={() => void decideCommitteeReview(review, "reject")}
                          type="button"
                        >
                          {committeeDecisionBusyId === `${reviewId}:reject` ? "Saving" : "Reject"}
                        </button>
                        {paperCandidate ? (
                          <button
                            className="mini-action-button"
                            disabled={isFinal || committeeDecisionBusyId === `${reviewId}:approve_paper_monitor`}
                            onClick={() => void decideCommitteeReview(review, "approve_paper_monitor")}
                            type="button"
                          >
                            {committeeDecisionBusyId === `${reviewId}:approve_paper_monitor` ? "Saving" : "Paper"}
                          </button>
                        ) : null}
                        {paperAllowed ? (
                          <button
                            className="mini-action-button"
                            disabled={paperMonitorBusyId === `start:${reviewId}`}
                            onClick={() => void startPaperMonitor(review)}
                            type="button"
                          >
                            {paperMonitorBusyId === `start:${reviewId}` ? "Starting" : "Start Monitor"}
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No committee reviews opened yet. Use Committee on a robustness run." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Activity size={17} />} title="Paper Monitor State" action={`${dashboardPaperMonitors.length} sessions`}>
            <div className="strategy-list">
              {dashboardPaperMonitors.length ? (
                dashboardPaperMonitors.map((session) => {
                  const metrics = asRecord(session.metrics);
                  const sessionId = asText(session, "id");
                  return (
                    <article className="strategy-row" key={sessionId}>
                      <div>
                        <strong>{asText(session, "strategy_name", "Paper strategy")}</strong>
                        <p>
                          {asText(session, "status", "ready")} · {asText(session, "heartbeat_status", "not_started")} · events {String(session.total_events ?? 0)}
                        </p>
                        <small>{session.is_stale ? "stale heartbeat" : "live execution disabled"}</small>
                      </div>
                      <div className="strategy-right">
                        <small>signals {String(metrics.last_signal_count ?? 0)}</small>
                        <button
                          className="mini-action-button"
                          disabled={paperMonitorBusyId === `heartbeat:${sessionId}` || asText(session, "status") === "stopped"}
                          onClick={() => void heartbeatPaperMonitor(session)}
                          type="button"
                        >
                          {paperMonitorBusyId === `heartbeat:${sessionId}` ? "Sending" : "Heartbeat"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={driftBusyId === sessionId}
                          onClick={() => void evaluatePaperDrift(session)}
                          type="button"
                        >
                          {driftBusyId === sessionId ? "Checking" : "Drift"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={paperMonitorBusyId === `stop:${sessionId}` || asText(session, "status") === "stopped"}
                          onClick={() => void stopPaperMonitor(session)}
                          type="button"
                        >
                          {paperMonitorBusyId === `stop:${sessionId}` ? "Stopping" : "Stop"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={killSwitchBusyId === `session:${sessionId}` || asText(session, "status") === "killed"}
                          onClick={() => void enforceKillSwitchFromSession(session)}
                          type="button"
                        >
                          {killSwitchBusyId === `session:${sessionId}` ? "Killing" : "Kill"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={executionSafetyBusyId === `request:${sessionId}` || asText(session, "status") === "killed"}
                          onClick={() => void requestLimitedLiveFromSession(session)}
                          type="button"
                        >
                          {executionSafetyBusyId === `request:${sessionId}` ? "Requesting" : "Live Req"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No approved paper monitor sessions yet. Committee approval is required first." />
              )}
            </div>
            {dashboardPaperMonitorEvents.length ? (
              <div className="activity-feed compact-feed">
                {dashboardPaperMonitorEvents.slice(0, 3).map((event) => (
                  <p key={asText(event, "id")}>
                    {asText(event, "event_type", "event")} · {asText(event, "event_status", "recorded")} · {asText(event, "strategy_name", "strategy")}
                  </p>
                ))}
              </div>
            ) : null}
          </Panel>

          <Panel className="span-5" icon={<GitBranch size={17} />} title="Live / Backtest Drift" action={`${dashboardDriftChecks.length} checks`}>
            <div className="strategy-list">
              {dashboardDriftChecks.length ? (
                dashboardDriftChecks.map((check) => {
                  const paper = asRecord(check.paper_metrics);
                  const base = asRecord(check.baseline_metrics);
                  const checkId = asText(check, "id");
                  const driftLevel = asText(check, "drift_level", "unknown");
                  const killEligible = ["warning", "breach"].includes(driftLevel);
                  return (
                    <article className="strategy-row" key={checkId}>
                      <div>
                        <strong>{asText(check, "strategy_name", "Strategy drift check")}</strong>
                        <p>
                          {driftLevel} · {asText(check, "check_status", "pending")}
                        </p>
                        <small>paper Sharpe {String(paper.sharpe ?? "n/a")} · base Sharpe {String(base.sharpe ?? "n/a")}</small>
                      </div>
                      <div className="strategy-right">
                        <span>{asText(check, "checked_by", "Model Validation")}</span>
                        <small>score {String(check.drift_score ?? 0)}</small>
                        {killEligible ? (
                          <button
                            className="mini-action-button"
                            disabled={killSwitchBusyId === `drift:${checkId}`}
                            onClick={() => void enforceKillSwitchFromDrift(check)}
                            type="button"
                          >
                            {killSwitchBusyId === `drift:${checkId}` ? "Killing" : "Kill"}
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No drift checks yet. Start a paper monitor and record heartbeats first." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<ShieldCheck size={17} />} title="Strategy Kill Switches" action={`${dashboardKillSwitchEvents.length} events`}>
            <div className="strategy-list">
              {dashboardKillSwitchEvents.length ? (
                dashboardKillSwitchEvents.map((event) => (
                  <article className="strategy-row" key={asText(event, "id")}>
                    <div>
                      <strong>{asText(event, "strategy_name", "Strategy")}</strong>
                      <p>
                        {asText(event, "trigger_source", "manual")} · {asText(event, "enforcement_status", "enforced")}
                      </p>
                      <small>{asText(event, "trigger_reason", "kill switch")}</small>
                    </div>
                    <div className="strategy-right">
                      <span>{asText(event, "enforced_by", "Risk Agent")}</span>
                      <small>live {event.live_execution_allowed ? "enabled" : "disabled"}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No kill-switch events. A breach or manual risk stop will appear here." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<LockKeyhole size={17} />} title="Execution Safety" action={dashboardExecutionControl ? asText(dashboardExecutionControl, "broker_execution_policy", "locked") : "locked"}>
            <div className="broker-import-summary">
              <article className="broker-summary-row">
                <strong>{dashboardExecutionControl?.global_execution_locked ? "Locked" : "Unlocked"}</strong>
                <span>global execution</span>
              </article>
              <article className="broker-summary-row">
                <strong>{dashboardExecutionControl?.live_broker_writes_allowed ? "Allowed" : "Disabled"}</strong>
                <span>broker writes</span>
              </article>
              <article className="broker-summary-row">
                <strong>{String(dashboardExecutionControl?.open_limited_live_requests ?? 0)}</strong>
                <span>limited-live requests</span>
              </article>
            </div>
            <p className="panel-note">{asText(dashboardExecutionControl ?? {}, "lock_reason", "Broker execution is locked by default.")}</p>
            <button className="panel-inline-button" disabled={executionSafetyBusyId === "global-kill"} onClick={() => void engageGlobalKillSwitchFromDashboard()} type="button">
              {executionSafetyBusyId === "global-kill" ? "Locking" : "Engage Global Lock"}
            </button>
            <div className="strategy-list">
              {dashboardLimitedLiveRequests.length ? (
                dashboardLimitedLiveRequests.map((request) => {
                  const requestId = asText(request, "id");
                  return (
                    <article className="strategy-row" key={requestId}>
                      <div>
                        <strong>{asText(request, "strategy_name", asText(request, "symbol", "Limited-live request"))}</strong>
                        <p>
                          {asText(request, "request_status", "pending")} · approval {asText(request, "approval_status", "pending")}
                        </p>
                        <small>max notional {String(request.max_notional ?? "n/a")} · live {request.live_execution_allowed ? "allowed" : "disabled"}</small>
                      </div>
                      <div className="strategy-right">
                        <button
                          className="mini-action-button"
                          disabled={executionSafetyBusyId === `sync:${requestId}`}
                          onClick={() => void syncLimitedLiveFromDashboard(request)}
                          type="button"
                        >
                          {executionSafetyBusyId === `sync:${requestId}` ? "Syncing" : "Sync"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={executionSafetyBusyId === `gate:${requestId}`}
                          onClick={() => void evaluateGateFromDashboard(request)}
                          type="button"
                        >
                          {executionSafetyBusyId === `gate:${requestId}` ? "Checking" : "Gate"}
                        </button>
                        <button
                          className="mini-action-button"
                          disabled={executionSafetyBusyId === `order:${requestId}`}
                          onClick={() => void createOrderIntentFromDashboard(request)}
                          type="button"
                        >
                          {executionSafetyBusyId === `order:${requestId}` ? "Creating" : "Order"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <EmptyState message="No limited-live requests. Paper monitor sessions can request review, but broker writes remain locked." />
              )}
            </div>
            {dashboardExecutionGateChecks.length ? (
              <div className="activity-feed compact-feed">
                {dashboardExecutionGateChecks.map((check) => (
                  <p key={asText(check, "id")}>
                    {asText(check, "gate_status", "blocked")} · {asText(check, "strategy_name", "request")} · {Array.isArray(check.block_reasons) ? check.block_reasons.join(", ") : "policy check"}
                  </p>
                ))}
              </div>
            ) : null}
            {dashboardOrderIntents.length ? (
              <div className="strategy-list">
                {dashboardOrderIntents.map((order) => {
                  const orderId = asText(order, "id");
                  return (
                    <article className="strategy-row" key={orderId}>
                      <div>
                        <strong>{asText(order, "symbol", "Order")} {asText(order, "side", "")}</strong>
                        <p>
                          {asText(order, "status", "pending")} · approval {asText(order, "approval_status", "pending")}
                        </p>
                        <small>notional {String(order.notional ?? "n/a")} · broker {order.broker_order_allowed ? "allowed" : "blocked"}</small>
                      </div>
                      <div className="strategy-right">
                        <button
                          className="mini-action-button"
                          disabled={executionSafetyBusyId === `order-risk:${orderId}`}
                          onClick={() => void evaluateOrderRiskFromDashboard(order)}
                          type="button"
                        >
                          {executionSafetyBusyId === `order-risk:${orderId}` ? "Checking" : "Risk"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : null}
            {dashboardOrderRiskChecks.length ? (
              <div className="activity-feed compact-feed">
                {dashboardOrderRiskChecks.map((check) => (
                  <p key={asText(check, "id")}>
                    order {asText(check, "check_status", "blocked")} · {asText(check, "symbol", "symbol")} · {Array.isArray(check.block_reasons) ? check.block_reasons.join(", ") : "risk check"}
                  </p>
                ))}
              </div>
            ) : null}
            {dashboardGlobalKillSwitchEvents.length ? (
              <div className="activity-feed compact-feed">
                {dashboardGlobalKillSwitchEvents.slice(0, 2).map((event) => (
                  <p key={asText(event, "id")}>
                    global {asText(event, "action", "engaged")} · {asText(event, "trigger_reason", "manual")}
                  </p>
                ))}
              </div>
            ) : null}
          </Panel>

          <Panel className="span-7" icon={<DatabaseZap size={17} />} title="MCP Connector Decisions" action="reviewed">
            <div className="connector-list">
              {(snapshot?.mcp_candidates ?? []).length ? (
                (snapshot?.mcp_candidates ?? [])
                  .filter((candidate) =>
                    ["tradingview", "browser_control", "strategy_development", "web_scraper", "web_search"].includes(
                      asText(candidate, "category")
                    )
                  )
                  .slice(0, 7)
                  .map((candidate) => (
                    <article className="connector-row" key={asText(candidate, "integration_key")}>
                      <div>
                        <strong>{asText(candidate, "integration_name", "MCP connector")}</strong>
                        <p>{asText(candidate, "use_case", "Connector candidate")}</p>
                      </div>
                      <div className="connector-meta">
                        <span>{asText(candidate, "trust_level", "review")}</span>
                        <StatusPill status={asText(candidate, "status", "candidate")} />
                      </div>
                    </article>
                  ))
              ) : (
                <EmptyState message="No MCP connector decisions loaded from core.mcp_integration_registry." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Landmark size={17} />} title="Research Hub" action={`${metricValue(snapshot, "research_hub_artifacts", "0")} artifacts`}>
            <div className="research-list">
              {(snapshot?.research_hub ?? []).length ? (
                (snapshot?.research_hub ?? []).slice(0, 7).map((row) => (
                  <article className="research-row" key={`${asText(row, "root_label")}-${asText(row, "artifact_family")}`}>
                    <div>
                      <strong>{asText(row, "artifact_family", "artifact")}</strong>
                      <p>{asText(row, "root_label", "local outputs")}</p>
                    </div>
                    <span>{asText(row, "artifact_count", "0")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No research artifacts loaded from core.raw_artifacts." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<Search size={17} />} title="NSE/BSE Filing Collector" action="live public filings">
            <form className="filing-collector-form" onSubmit={runFilingCollectorFromDashboard}>
              <div className="field-grid">
                <label>
                  Source
                  <select
                    value={filingCollectorDraft.source}
                    onChange={(event) => setFilingCollectorDraft((current) => ({ ...current, source: event.target.value }))}
                  >
                    <option value="all">NSE + BSE</option>
                    <option value="nse">NSE</option>
                    <option value="bse">BSE</option>
                  </select>
                </label>
                <label>
                  Limit
                  <input
                    inputMode="numeric"
                    min="1"
                    max="100"
                    type="number"
                    value={filingCollectorDraft.limit}
                    onChange={(event) => setFilingCollectorDraft((current) => ({ ...current, limit: event.target.value }))}
                  />
                </label>
                <label>
                  From
                  <input
                    type="date"
                    value={filingCollectorDraft.dateFrom}
                    onChange={(event) => setFilingCollectorDraft((current) => ({ ...current, dateFrom: event.target.value }))}
                  />
                </label>
                <label>
                  To
                  <input
                    type="date"
                    value={filingCollectorDraft.dateTo}
                    onChange={(event) => setFilingCollectorDraft((current) => ({ ...current, dateTo: event.target.value }))}
                  />
                </label>
              </div>
              <button className="primary-button" disabled={filingCollectorBusy} type="submit">
                {filingCollectorBusy ? "Collecting filings..." : "Run Filing Collector"}
              </button>
            </form>
            <div className="source-check-list">
              {dashboardFilingCollectorRuns.length ? (
                dashboardFilingCollectorRuns.map((run) => (
                  <article className="source-check-row" key={asText(run, "id")}>
                    <div>
                      <strong>{asText(run, "exchange", "Exchange")} filings</strong>
                      <p>{asText(run, "date_from")} to {asText(run, "date_to")} · {asText(run, "rows_upserted", "0")} stored · {asText(run, "events_upserted", "0")} events</p>
                    </div>
                    <StatusPill status={asText(run, "status", "unknown")} />
                    <span>{asText(run, "http_status", "-")}</span>
                    <time>{compactDate(run.finished_at ?? run.started_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No NSE/BSE collector runs recorded yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<Inbox size={17} />} title="Research Factory Queue" action={`${dashboardResearchFactoryQueue.length} lanes`}>
            <div className="source-check-list">
              {dashboardResearchFactoryQueue.length ? (
                dashboardResearchFactoryQueue.map((queue) => (
                  <article className="source-check-row" key={asText(queue, "queue_key")}>
                    <div>
                      <strong>{asText(queue, "queue_name", "Queue")}</strong>
                      <p>{asText(queue, "next_action", "Review queue.").slice(0, 140)}</p>
                    </div>
                    <StatusPill status={asText(queue, "owner_agent", "Research")} />
                    <span>{asText(queue, "open_rows", "0")} open</span>
                    <time>{compactDate(queue.latest_activity_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No research queue rows loaded from research.v_research_factory_queue_summary." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<FileText size={17} />} title="Corporate Filing Inbox" action={`${dashboardCorporateFilingInbox.length} recent`}>
            <div className="source-check-list">
              {dashboardCorporateFilingInbox.length ? (
                dashboardCorporateFilingInbox.map((filing) => (
                  <article className="source-check-row" key={`${asText(filing, "filing_id")}-${asText(filing, "event_id")}`}>
                    <div>
                      <strong>{asText(filing, "symbol", asText(filing, "company_name", "Filing"))}</strong>
                      <p>{asText(filing, "title", "Captured filing").slice(0, 140)}</p>
                    </div>
                    <StatusPill status={asText(filing, "extraction_status", asText(filing, "event_type", "captured"))} />
                    <span>{asText(filing, "filing_id", "-")}</span>
                    <time>{compactDate(filing.filed_at ?? filing.filing_created_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No captured corporate filings yet. Run the NSE/BSE collector." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<FileText size={17} />} title="Filing PDF Extractor" action="download + parse">
            <form className="filing-extractor-form" onSubmit={runFilingPdfExtractorFromDashboard}>
              <div className="field-grid">
                <label>
                  Filing ID
                  <input
                    inputMode="numeric"
                    placeholder="blank = latest"
                    value={filingExtractorDraft.filingId}
                    onChange={(event) => setFilingExtractorDraft((current) => ({ ...current, filingId: event.target.value }))}
                  />
                </label>
                <label>
                  Limit
                  <input
                    inputMode="numeric"
                    min="1"
                    max="25"
                    type="number"
                    value={filingExtractorDraft.limit}
                    onChange={(event) => setFilingExtractorDraft((current) => ({ ...current, limit: event.target.value }))}
                  />
                </label>
              </div>
              <label className="toggle-row">
                <input
                  checked={filingExtractorDraft.force}
                  type="checkbox"
                  onChange={(event) => setFilingExtractorDraft((current) => ({ ...current, force: event.target.checked }))}
                />
                Re-extract already parsed PDFs
              </label>
              <button className="primary-button" disabled={filingExtractorBusy} type="submit">
                {filingExtractorBusy ? "Extracting PDFs..." : "Run PDF Extraction"}
              </button>
            </form>
            <div className="source-check-list">
              {dashboardFilingPdfRuns.length ? (
                dashboardFilingPdfRuns.map((run) => (
                  <article className="source-check-row" key={asText(run, "id")}>
                    <div>
                      <strong>{asText(run, "symbol", asText(run, "company_name", "Filing"))}</strong>
                      <p>{asText(run, "extracted_chars", "0")} chars · {asText(run, "page_count", "0")} pages · {asText(run, "event_type_after", "unclassified")}</p>
                    </div>
                    <StatusPill status={asText(run, "status", "unknown")} />
                    <span>{asText(run, "parser_name", "-")}</span>
                    <time>{compactDate(run.finished_at ?? run.started_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No PDF extraction runs yet. Run extraction after filings are captured." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<CircleAlert size={17} />} title="Special Situations Inbox" action="demergers / mergers / buybacks">
            <div className="source-check-list">
              {dashboardSpecialSituationInbox.length ? (
                dashboardSpecialSituationInbox.map((event) => (
                  <article className="source-check-row" key={`special-${asText(event, "event_id", asText(event, "filing_id"))}`}>
                    <div>
                      <strong>{asText(event, "company_name", asText(event, "symbol", "Special situation"))}</strong>
                      <p>{asText(event, "title", "Corporate action candidate").slice(0, 180)}</p>
                    </div>
                    <StatusPill status={asText(event, "event_type", "event")} />
                    <span>{asText(event, "opportunity_score", "0")} / {asText(event, "risk_score", "0")}</span>
                    <small>{asText(event, "assigned_agent", "Special Situations Agent")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No special-situation events captured yet. Routine filings still appear in Corporate Filing Inbox." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Landmark size={17} />} title="Special Situation Terms" action="dates / prices / ratios">
            <div className="source-check-list">
              {dashboardSpecialSituationTerms.length ? (
                dashboardSpecialSituationTerms.map((term) => (
                  <article className="source-check-row" key={asText(term, "id")}>
                    <div>
                      <strong>{asText(term, "symbol", asText(term, "company_name", "Special situation"))}</strong>
                      <p>
                        {asText(term, "event_type", "event")}
                        {asText(term, "offer_price") ? ` · offer ${asText(term, "offer_price")}` : ""}
                        {asText(term, "issue_price") ? ` · issue ${asText(term, "issue_price")}` : ""}
                        {asText(term, "record_date") ? ` · record ${asText(term, "record_date")}` : ""}
                        {asText(term, "swap_ratio") ? ` · ratio ${asText(term, "swap_ratio")}` : ""}
                      </p>
                    </div>
                    <StatusPill status={asText(term, "status", "needs_review")} />
                    <span>{asText(term, "confidence", "0")}</span>
                    <button
                      className="mini-action-button"
                      disabled={specialMemoBusyId === asText(term, "id")}
                      onClick={() => void generateSpecialSituationMemoFromDashboard(asText(term, "id"))}
                      type="button"
                    >
                      {specialMemoBusyId === asText(term, "id") ? "Routing..." : "Memo"}
                    </button>
                    <time>{compactDate(term.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No structured special-situation terms extracted yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<ClipboardList size={17} />} title="Special Situation Memos" action="review routing">
            <div className="source-check-list">
              {dashboardSpecialSituationMemos.length ? (
                dashboardSpecialSituationMemos.map((memo) => (
                  <article className="source-check-row" key={asText(memo, "id")}>
                    <div>
                      <strong>{asText(memo, "memo_title", asText(memo, "symbol", "Special memo"))}</strong>
                      <p>{asText(memo, "summary", asText(memo, "note_path", "Generated memo")).slice(0, 190)}</p>
                    </div>
                    <StatusPill status={asText(memo, "memo_status", "generated")} />
                    <span>{asText(memo, "latest_spread_status", asText(memo, "approval_status", "pending"))}</span>
                    <button
                      className="mini-action-button"
                      disabled={specialSpreadBusyId === asText(memo, "id")}
                      onClick={() => void calculateSpecialSituationSpreadFromDashboard(asText(memo, "id"))}
                      type="button"
                    >
                      {specialSpreadBusyId === asText(memo, "id") ? "Checking..." : "Spread"}
                    </button>
                    <button
                      className="mini-action-button"
                      disabled={specialDecisionBusyId === `${asText(memo, "id")}:monitor` || asText(memo, "approval_status") !== "pending"}
                      onClick={() => void decideSpecialSituationFromDashboard(asText(memo, "id"), "monitor")}
                      type="button"
                    >
                      Monitor
                    </button>
                    <button
                      className="mini-action-button"
                      disabled={specialDecisionBusyId === `${asText(memo, "id")}:research_more` || asText(memo, "approval_status") !== "pending"}
                      onClick={() => void decideSpecialSituationFromDashboard(asText(memo, "id"), "research_more")}
                      type="button"
                    >
                      Research
                    </button>
                    <button
                      className="mini-action-button"
                      disabled={specialDecisionBusyId === `${asText(memo, "id")}:reject` || asText(memo, "approval_status") !== "pending"}
                      onClick={() => void decideSpecialSituationFromDashboard(asText(memo, "id"), "reject")}
                      type="button"
                    >
                      Reject
                    </button>
                    <small>{asText(memo, "note_path", "Obsidian note")}</small>
                    <time>{compactDate(memo.updated_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No event memos generated yet. Create one from extracted special-situation terms." />
              )}
            </div>
          </Panel>

          <Panel
            className="span-6"
            icon={<LineChart size={17} />}
            title="Special Situation Spread Checks"
            action="real quote only"
          >
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={eventQuoteBusy} onClick={() => void refreshEventQuotesFromDashboard()} type="button">
                {eventQuoteBusy ? "Refreshing..." : "Refresh event quotes"}
              </button>
            </div>
            <div className="source-check-list">
              {dashboardSpecialSituationSpreads.length ? (
                dashboardSpecialSituationSpreads.map((spread) => (
                  <article className="source-check-row" key={asText(spread, "id")}>
                    <div>
                      <strong>{asText(spread, "symbol", "Event")}</strong>
                      <p>
                        target {asText(spread, "target_price", "-")} · market {asText(spread, "market_price", "missing")}
                        {asText(spread, "gross_spread_pct") ? ` · spread ${asText(spread, "gross_spread_pct")}%` : ""}
                      </p>
                    </div>
                    <StatusPill status={asText(spread, "status", "pending")} />
                    <span>{asText(spread, "days_to_close", "-")}d</span>
                    <time>{compactDate(spread.created_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No spread checks yet. Run Spread from a special-situation memo." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<ShieldCheck size={17} />} title="Special Situation Decisions" action="no trade authorization">
            <div className="source-check-list">
              {dashboardSpecialSituationDecisions.length ? (
                dashboardSpecialSituationDecisions.map((decision) => (
                  <article className="source-check-row" key={asText(decision, "id")}>
                    <div>
                      <strong>{asText(decision, "symbol", "Event")} {"->"} {asText(decision, "decision", "decision")}</strong>
                      <p>{asText(decision, "decision_notes", "Decision recorded.").slice(0, 150)}</p>
                    </div>
                    <StatusPill status={asText(decision, "decision_status", "final")} />
                    <span>{asText(decision, "trade_allowed", "false") === "true" ? "trade" : "no trade"}</span>
                    <time>{compactDate(decision.created_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No Charlie decisions recorded for special situations yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<ClipboardList size={17} />} title="Today Brief" action="Open note">
            <div className="brief-list">
              {dashboardBrief.length ? (
                dashboardBrief.map((line) => (
                  <div className="brief-row" key={`${line.time}-${line.title}`}>
                    <span className={`tone-dot tone-${line.tone}`} />
                    <time>{line.time}</time>
                    <div>
                      <strong>{line.title}</strong>
                      <p>{line.detail}</p>
                    </div>
                  </div>
                ))
              ) : (
                <EmptyState message="No live brief rows yet. Run source checks, queue work, or ingest records." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Landmark size={17} />} title="Committee Room" action={`${dashboardCommitteeRoomItems.length} reviews`}>
            {dashboardCommitteeRoomItems.length ? (
              <>
                <div className="committee-room-summary">
                  {dashboardCommitteeRoomSummary.map((metric) => (
                    <div className="committee-room-metric" key={asText(metric, "metric")}>
                      <strong>{asText(metric, "value", "0")}</strong>
                      <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
                <div className="committee-room-list">
                  {dashboardCommitteeRoomItems.map((item) => {
                    const liveAllowed = asText(item, "live_execution_allowed") === "true";
                    const capitalAllowed = asText(item, "capital_action_allowed") === "true";
                    return (
                      <article className={`committee-room-row room-state-${asText(item, "room_state", "ready_for_decision")}`} key={asText(item, "committee_item_key")}>
                        <div className="committee-room-main">
                          <div className="row-title">
                            <strong>{asText(item, "title", "Committee review")}</strong>
                            <SeverityBadge severity={asSeverity(item.risk_level, "medium")} />
                          </div>
                          <p>{asText(item, "recommended_next_action", "Review evidence and record committee decision.")}</p>
                          <small>
                            {asText(item, "committee_lane", "Committee")} · {asText(item, "source_view", "source")}
                            {asText(item, "symbol") ? ` · ${asText(item, "symbol")}` : ""}
                            {asText(item, "subject_name") ? ` · ${asText(item, "subject_name")}` : ""}
                          </small>
                        </div>
                        <div className="committee-room-state">
                          <StatusPill status={asText(item, "room_state", "ready_for_decision")} />
                          <span>memo {asText(item, "memo_status", "missing")}</span>
                          <span>approval {asText(item, "approval_status", "none")}</span>
                        </div>
                        <div className="committee-room-guards">
                          <span className={liveAllowed ? "guard-on" : "guard-off"}>{liveAllowed ? "live allowed" : "live blocked"}</span>
                          <span className={capitalAllowed ? "guard-on" : "guard-off"}>{capitalAllowed ? "capital allowed" : "capital blocked"}</span>
                          <small>gaps {asText(item, "evidence_gap_count", "0")} · follow-ups {asText(item, "required_followup_count", "0")}</small>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            ) : (
              <EmptyState message="No committee rows loaded from agent.v_committee_room_items." />
            )}
          </Panel>

          <Panel
            className="span-12"
            icon={<LockKeyhole size={17} />}
            title="Approval Board"
            action={`${pendingApprovals} pending`}
          >
            {dashboardApprovalBoardItems.length ? (
              <>
                <div className="approval-board-summary">
                  {dashboardApprovalBoardSummary.map((metric) => (
                    <div className="approval-board-metric" key={asText(metric, "metric")}>
                      <strong>{asText(metric, "value", "0")}</strong>
                      <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
                <div className="approval-board-list">
                  {dashboardApprovalBoardItems.map((approval) => {
                    const approvalId = asText(approval, "approval_id");
                    const approvalStatus = asText(approval, "approval_status", "pending");
                    const liveAllowed = asText(approval, "live_execution_allowed") === "true";
                    const brokerAllowed = asText(approval, "broker_order_allowed") === "true";
                    return (
                      <article className={`approval-board-row status-${approvalStatus}`} key={approvalId}>
                        <div className="approval-board-main">
                          <div className="row-title">
                            <strong>{asText(approval, "title", "Approval")}</strong>
                            <SeverityBadge severity={asSeverity(approval.risk_level, "medium")} />
                          </div>
                          <p>{asText(approval, "recommended_next_action", asText(approval, "rationale", "Review approval evidence."))}</p>
                          <small>
                            {asText(approval, "board_lane", "General Approval")} · {asText(approval, "linked_source", "agent.approvals")}
                            {asText(approval, "symbol") ? ` · ${asText(approval, "symbol")}` : ""}
                            {asText(approval, "strategy_name") ? ` · ${asText(approval, "strategy_name")}` : ""}
                          </small>
                        </div>
                        <div className="approval-board-state">
                          <StatusPill status={approvalStatus} />
                          <span>{asText(approval, "gate_status", asText(approval, "linked_status", "no gate"))}</span>
                        </div>
                        <div className="approval-board-guards">
                          <span className={liveAllowed ? "guard-on" : "guard-off"}>{liveAllowed ? "live allowed" : "live blocked"}</span>
                          <span className={brokerAllowed ? "guard-on" : "guard-off"}>{brokerAllowed ? "broker allowed" : "broker blocked"}</span>
                          <small>risk {asText(approval, "open_risk_events", "0")} · gates {asText(approval, "blocked_gate_count", "0")}/{asText(approval, "gate_check_count", "0")}</small>
                        </div>
                        {approvalStatus === "pending" ? (
                          <div className="approval-actions">
                            <button
                              className="icon-button approve"
                              onClick={() => void handleResolveApproval(approvalId, "approved")}
                              title="Approve"
                              type="button"
                            >
                              <Check size={15} aria-hidden="true" />
                            </button>
                            <button
                              className="icon-button reject"
                              onClick={() => void handleResolveApproval(approvalId, "rejected")}
                              title="Reject"
                              type="button"
                            >
                              <X size={15} aria-hidden="true" />
                            </button>
                          </div>
                        ) : (
                          <StatusBadge status={approvalStatus === "approved" ? "approved" : "blocked"} />
                        )}
                      </article>
                    );
                  })}
                </div>
              </>
            ) : (
              <EmptyState message="No approval board rows loaded from agent.v_approval_board_items." />
            )}
          </Panel>

          <Panel className="span-8" icon={<Inbox size={17} />} title="Agent Inbox" action={`${highPriorityItems} urgent`}>
            <div className="inbox-table">
              <div className="inbox-head">
                <span>Work</span>
                <span>Owner</span>
                <span>Status</span>
                <span>Evidence</span>
                <span>Actions</span>
              </div>
              {items.length ? (
                items.map((item) => (
                  <article className="inbox-row" key={item.id}>
                    <div>
                      <strong>{item.title}</strong>
                      <p>{item.recommendedAction}</p>
                    </div>
                    <label className="inbox-owner-control">
                      <span className="sr-only">Reassign {item.title}</span>
                      <select
                        aria-label={`Reassign ${item.title}`}
                        disabled={Boolean(inboxBusyId)}
                        onChange={(event) => {
                          if (event.target.value && event.target.value !== item.agent) {
                            void handleInboxAction(item, "reassign", event.target.value);
                          }
                        }}
                        value={item.agent}
                      >
                        {!inboxAgentOptions.includes(item.agent) ? <option value={item.agent}>{item.agent}</option> : null}
                        {inboxAgentOptions.map((agentName) => (
                          <option key={agentName} value={agentName}>{agentName}</option>
                        ))}
                      </select>
                      {item.claimedBy ? <small>claimed by {item.claimedBy}</small> : null}
                    </label>
                    <div className="inbox-status-cell">
                      <StatusBadge status={item.status} />
                      {item.resolvedBy ? <small>by {item.resolvedBy}</small> : null}
                    </div>
                    <div className="evidence-stack">
                      {item.evidence.slice(0, 2).map((source) => (
                        <small key={source}>{source}</small>
                      ))}
                      <time>{item.updatedAt}</time>
                    </div>
                    <div className="inbox-actions">
                      {item.status === "queued" ? (
                        <button
                          className="icon-button"
                          disabled={Boolean(inboxBusyId)}
                          onClick={() => void handleInboxAction(item, "claim")}
                          title="Claim item"
                          type="button"
                        >
                          <UserCheck size={15} aria-hidden="true" />
                        </button>
                      ) : null}
                      {item.status !== "done" ? (
                        <button
                          className="icon-button approve"
                          disabled={Boolean(inboxBusyId)}
                          onClick={() => void handleInboxAction(item, "resolve")}
                          title="Resolve item"
                          type="button"
                        >
                          <Check size={15} aria-hidden="true" />
                        </button>
                      ) : null}
                      {item.status !== "blocked" && item.status !== "done" ? (
                        <button
                          className="icon-button reject"
                          disabled={Boolean(inboxBusyId)}
                          onClick={() => void handleInboxAction(item, "block")}
                          title="Block item"
                          type="button"
                        >
                          <X size={15} aria-hidden="true" />
                        </button>
                      ) : null}
                      {item.status === "blocked" || item.status === "done" ? (
                        <button
                          className="icon-button"
                          disabled={Boolean(inboxBusyId)}
                          onClick={() => void handleInboxAction(item, "reopen")}
                          title="Reopen item"
                          type="button"
                        >
                          <RotateCcw size={15} aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No live inbox rows in agent.inbox_items." />
              )}
            </div>
          </Panel>

          <Panel className="span-4" icon={<CircleAlert size={17} />} title="Portfolio Alerts" action="Risk view">
            <div className="alert-list">
              {dashboardAlerts.length ? (
                dashboardAlerts.map((alert) => (
                  <article className="alert-row" key={alert.id}>
                    <div>
                      <strong>{alert.symbol}</strong>
                      <span>{alert.client}</span>
                    </div>
                    <p>{alert.issue}</p>
                    <div className="row-footer">
                      <SeverityBadge severity={alert.severity} />
                      <small>{alert.owner}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No portfolio or strategy alert rows are open." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<Activity size={17} />} title="Active Signals" action="Trading desk">
            <div className="signal-list">
              {dashboardSignals.length ? (
                dashboardSignals.map((signal) => (
                  <article className="signal-row" key={signal.id}>
                    <div className="signal-symbol">
                      <strong>{signal.symbol}</strong>
                      <span>{signal.strategy}</span>
                    </div>
                    <span>{signal.timeframe}</span>
                    <span className={`direction direction-${signal.direction}`}>{signal.direction}</span>
                    <div className="confidence">
                      <div>
                        <span style={{ width: `${signal.confidence}%` }} />
                      </div>
                      <small>{signal.confidence}%</small>
                    </div>
                    <button className="row-button" type="button">
                      Review
                      <ChevronRight size={14} aria-hidden="true" />
                    </button>
                  </article>
                ))
              ) : (
                <EmptyState message="No live strategy signals in trading.signals." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<GitBranch size={17} />} title="Agent Team" action="Run log">
            <div className="agent-list">
              {dashboardAgents.length ? (
                dashboardAgents.map((agent) => (
                  <article className="agent-row" key={agent.name}>
                    <div className={`agent-state state-${agent.state}`} />
                    <div>
                      <div className="row-title">
                        <strong>{agent.name}</strong>
                        <span>{agent.costTier}</span>
                      </div>
                      <p>{agent.currentTask}</p>
                      <small>{agent.role}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No active agent profile rows loaded." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<Building2 size={17} />} title="Agent Departments" action="live roster">
            <div className="department-grid">
              {dashboardAgentDepartments.length ? (
                dashboardAgentDepartments.map((department) => (
                  <article className="department-row" key={asText(department, "department_key")}>
                    <div>
                      <strong>{asText(department, "department_name", "Department")}</strong>
                      <p>{asText(department, "mission", "Mission not recorded.")}</p>
                    </div>
                    <div className="department-meta">
                      <span>{asText(department, "lead_agent", "Lead")}</span>
                      <small>{asText(department, "active_agents", "0")} agents · {asText(department, "active_skills", "0")} skills</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No department rows loaded from agent.v_agent_departments." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<ListChecks size={17} />} title="Agent Skill Matrix" action="active + planned">
            <div className="skill-grid">
              {dashboardAgentSkills.length ? (
                dashboardAgentSkills.map((skill) => (
                  <article className="skill-row" key={asText(skill, "skill_key")}>
                    <div>
                      <strong>{asText(skill, "skill_name", "Skill")}</strong>
                      <p>{asText(skill, "risk_notes", "No risk note recorded.")}</p>
                    </div>
                    <span>{asText(skill, "skill_family", "skill")}</span>
                    <span>{asText(skill, "execution_mode", "worker")}</span>
                    <small>{asArray(skill, "primary_agents").join(", ") || asArray(skill, "assigned_agents").slice(0, 2).join(", ") || "Unassigned"}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No skill rows loaded from agent.v_agent_skill_matrix." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Building2 size={17} />} title="Live AI Office Floor" action={`${dashboardLiveOfficeRooms.length} rooms · ${dashboardLiveOfficeAgents.length} active watch`}>
            {dashboardLiveOfficeRooms.length ? (
              <>
                <div className="office-room-grid">
                  {dashboardLiveOfficeRooms.map((room) => {
                    const roomAgents = asRecordArray(room, "agents");
                    return (
                      <article className={`office-room room-state-${asText(room, "room_state", "available")}`} key={asText(room, "room_key")}>
                        <div className="office-room-heading">
                          <div>
                            <strong>{asText(room, "room_name", "Office Room")}</strong>
                            <p>{asText(room, "agent_count", "0")} employees · {asText(room, "active_agent_count", "0")} active</p>
                          </div>
                          <StatusPill status={asText(room, "room_state", "available")} />
                        </div>
                        <div className="office-room-metrics">
                          <span><strong>{asText(room, "open_task_count", "0")}</strong><small>tasks</small></span>
                          <span><strong>{asText(room, "unread_message_count", "0")}</strong><small>unread</small></span>
                          <span><strong>{asText(room, "open_risk_event_count", "0")}</strong><small>risk</small></span>
                        </div>
                        <div className="office-agent-strip">
                          {roomAgents.map((agent) => {
                            const agentName = asText(agent, "agent_name", "Agent");
                            const workTitle = asText(agent, "current_work_title", "available");
                            const detail = asText(agent, "current_work_detail", "No current work detail recorded.");
                            return (
                              <div
                                className={`office-desk agent-state-${asText(agent, "live_state", "available")}`}
                                key={`${asText(room, "room_key")}-${agentName}`}
                                style={{ borderColor: asText(agent, "color_token", "#4f46e5") }}
                                title={`${agentName}: ${workTitle}`}
                              >
                                <div className="office-agent-avatar compact" style={{ borderColor: asText(agent, "color_token", "#4f46e5") }}>
                                  <span>{agentName.slice(0, 1)}</span>
                                </div>
                                <div className="office-desk-copy">
                                  <strong>{agentName}</strong>
                                  <p>{workTitle}</p>
                                </div>
                                <div className="office-agent-popover">
                                  <strong>{agentName}</strong>
                                  <p>{detail}</p>
                                  <small>
                                    {asText(agent, "office_location", "Desk")} · tasks {asText(agent, "open_task_count", "0")} · inbox {asText(agent, "open_inbox_count", "0")} · unread {asText(agent, "unread_message_count", "0")}
                                  </small>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </article>
                    );
                  })}
                </div>
                <div className="office-activity-feed">
                  {dashboardLiveOfficeAgents.map((agent) => (
                    <article className="office-activity-row" key={asText(agent, "agent_name")}>
                      <span style={{ background: asText(agent, "color_token", "#4f46e5") }} />
                      <div>
                        <strong>{asText(agent, "agent_name", "Agent")}</strong>
                        <p>{asText(agent, "current_work_title", "Available")}</p>
                      </div>
                      <small>{asText(agent, "live_state", "available")} · workload {asText(agent, "workload_score", "0")}</small>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <EmptyState message="No live office rows loaded from agent.v_live_office_rooms." />
            )}
          </Panel>

          <Panel className="span-12" icon={<PanelLeft size={17} />} title="Employee Profiles" action={`${asText(dashboardEmployeeProfileSummary.find((row) => asText(row, "metric") === "agents") ?? {}, "value", "0")} profiles`}>
            {dashboardEmployeeProfiles.length ? (
              <>
                <div className="employee-profile-summary">
                  {dashboardEmployeeProfileSummary.map((metric) => (
                    <div className="employee-profile-metric" key={asText(metric, "metric")}>
                      <strong>{asText(metric, "value", "0")}</strong>
                      <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
                <div className="employee-profile-grid">
                  {dashboardEmployeeProfiles.map((profile) => {
                    const skills = asRecordArray(profile, "skills").slice(0, 3);
                    const tools = asRecordArray(profile, "tools").slice(0, 3);
                    const outputs = asRecordArray(profile, "recent_outputs").slice(0, 2);
                    return (
                      <article className={`employee-profile-card state-${asText(profile, "live_state", "available")}`} key={asText(profile, "agent_name")}>
                        <div className="employee-profile-heading">
                          <div className="office-agent-avatar" style={{ borderColor: asText(profile, "color_token", "#4f46e5") }}>
                            <span>{asText(profile, "agent_name", "?").slice(0, 1)}</span>
                          </div>
                          <div>
                            <strong>{asText(profile, "agent_name", "Agent")}</strong>
                            <p>{asText(profile, "display_title", "AI employee")}</p>
                            <small>{asText(profile, "department_name", "Department")} · {asText(profile, "hierarchy_level", "specialist")}</small>
                          </div>
                          <StatusPill status={asText(profile, "live_state", "available")} />
                        </div>
                        <p className="employee-profile-voice">{asText(profile, "voice_style", asText(profile, "persona", "No personality profile recorded.")).slice(0, 170)}</p>
                        <div className="employee-profile-model">
                          <span>{asText(profile, "primary_route", "route pending")}</span>
                          <small>{asText(profile, "assigned_provider", asText(profile, "route_provider", "provider"))} · {asText(profile, "assigned_model", asText(profile, "route_default_model", "model"))}</small>
                        </div>
                        <div className="employee-profile-counters">
                          <span><strong>{asText(profile, "enabled_tool_count", "0")}</strong><small>tools</small></span>
                          <span><strong>{asText(profile, "active_skill_count", "0")}</strong><small>skills</small></span>
                          <span><strong>{asText(profile, "open_task_count", "0")}</strong><small>tasks</small></span>
                          <span><strong>{asText(profile, "output_artifact_count", "0")}</strong><small>outputs</small></span>
                          <span><strong>{asText(profile, "pending_approval_count", "0")}</strong><small>approvals</small></span>
                        </div>
                        <div className="employee-profile-section">
                          <h4>Current work</h4>
                          <p>{asText(profile, "current_work_title", "Available")}</p>
                        </div>
                        <div className="employee-profile-tags">
                          {skills.map((skill) => (
                            <span key={`${asText(profile, "agent_name")}-${asText(skill, "skill_key")}`}>{asText(skill, "skill_name", "Skill")}</span>
                          ))}
                        </div>
                        <div className="employee-profile-tools">
                          {tools.map((tool) => (
                            <span key={`${asText(profile, "agent_name")}-${asText(tool, "tool_name")}`}>{asText(tool, "tool_name", "tool")} · {asText(tool, "permission_level", "read")}</span>
                          ))}
                        </div>
                        <div className="employee-profile-outputs">
                          {outputs.length ? (
                            outputs.map((output) => (
                              <small key={`${asText(profile, "agent_name")}-${asText(output, "id")}`}>{asText(output, "output_note_path", asText(output, "skill_name", "worker output"))}</small>
                            ))
                          ) : (
                            <small>No output artifacts yet.</small>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            ) : (
              <EmptyState message="No employee profile rows loaded from agent.v_employee_profiles_v1." />
            )}
          </Panel>

          <Panel className="span-12" icon={<FileText size={17} />} title="Output Artifact Registry" action={`${asText(dashboardOutputArtifactSummary.find((row) => asText(row, "metric") === "total_artifacts") ?? {}, "value", "0")} artifacts`}>
            {dashboardOutputArtifacts.length ? (
              <>
                <div className="employee-profile-summary">
                  {dashboardOutputArtifactSummary.slice(0, 8).map((metric) => (
                    <div className="employee-profile-metric" key={asText(metric, "metric")}>
                      <strong>{asText(metric, "value", "0")}</strong>
                      <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
                <div className="artifact-registry-grid">
                  <div className="source-check-list">
                    <h4>Latest office outputs</h4>
                    {dashboardOutputArtifacts.map((artifact) => (
                      <article className="source-check-row" key={asText(artifact, "artifact_key")}>
                        <div>
                          <strong>{asText(artifact, "title", "Output artifact")}</strong>
                          <p>{asText(artifact, "owner_agent", "Agent")} · {asText(artifact, "artifact_family", "artifact").replace(/_/g, " ")} · {asText(artifact, "artifact_location", "location pending")}</p>
                        </div>
                        <StatusPill status={asText(artifact, "status", "indexed")} />
                        <span>{asText(artifact, "symbol", asText(artifact, "strategy_name", asText(artifact, "department", "office")))}</span>
                        <time>{compactDate(artifact.latest_activity_at)}</time>
                      </article>
                    ))}
                  </div>
                  <div className="source-check-list">
                    <h4>Traceability gaps</h4>
                    {dashboardOutputArtifactGaps.length ? (
                      dashboardOutputArtifactGaps.map((gap) => (
                        <article className="source-check-row" key={`${asText(gap, "gap_type")}-${asText(gap, "source_id")}`}>
                          <div>
                            <strong>{asText(gap, "title", "Artifact gap")}</strong>
                            <p>{asText(gap, "gap_reason", "Needs output traceability.")}</p>
                          </div>
                          <StatusPill status={asText(gap, "status", "open")} />
                          <span>{asText(gap, "owner_agent", "owner")}</span>
                          <time>{compactDate(gap.updated_at)}</time>
                        </article>
                      ))
                    ) : (
                      <EmptyState message="No generated-output traceability gaps returned by agent.v_output_artifact_gaps." />
                    )}
                  </div>
                </div>
              </>
            ) : (
              <EmptyState message="No generated output artifacts loaded from agent.v_output_artifact_registry_v2." />
            )}
          </Panel>

          <Panel className="span-12" icon={<MessageSquareText size={17} />} title="Agent Comments" action={`${asText(dashboardAgentCommentSummary.find((row) => asText(row, "metric") === "open_comments") ?? {}, "value", "0")} open`}>
            <form className="agent-comment-form" onSubmit={createAgentCommentFromDashboard}>
              <select
                aria-label="Comment target artifact"
                onChange={(event) => setAgentCommentDraft((draft) => ({ ...draft, targetRef: event.target.value }))}
                value={agentCommentDraft.targetRef}
              >
                <option value="">Latest output artifact</option>
                {dashboardOutputArtifacts.slice(0, 24).map((artifact) => (
                  <option key={asText(artifact, "artifact_key")} value={asText(artifact, "artifact_key")}>
                    {asText(artifact, "title", "Output artifact").slice(0, 80)}
                  </option>
                ))}
              </select>
              <select
                aria-label="Comment severity"
                onChange={(event) => setAgentCommentDraft((draft) => ({ ...draft, severity: event.target.value }))}
                value={agentCommentDraft.severity}
              >
                <option value="normal">Normal</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
              <input
                aria-label="Agent comment"
                onChange={(event) => setAgentCommentDraft((draft) => ({ ...draft, body: event.target.value }))}
                placeholder="Add review note, objection, follow-up, or source gap..."
                value={agentCommentDraft.body}
              />
              <button className="mini-action-button" disabled={!agentCommentDraft.body.trim() || agentCommentBusyId === "create"} type="submit">
                {agentCommentBusyId === "create" ? "Adding..." : "Add"}
              </button>
            </form>
            {dashboardAgentComments.length ? (
              <div className="artifact-registry-grid">
                <div className="source-check-list">
                  <h4>Latest review notes</h4>
                  {dashboardAgentComments.map((comment) => (
                    <article className="source-check-row" key={`agent-comment-${asText(comment, "id")}`}>
                      <div>
                        <strong>{asText(comment, "target_title", "Comment target")}</strong>
                        <p>{asText(comment, "body", "No comment body").slice(0, 180)}</p>
                      </div>
                      <StatusPill status={asText(comment, "status", "open")} />
                      <span>{asText(comment, "severity", "normal")}</span>
                      <button
                        className="mini-action-button"
                        disabled={asText(comment, "status") === "resolved" || agentCommentBusyId === `${asText(comment, "id")}:resolved`}
                        onClick={() => void resolveAgentCommentFromDashboard(comment, "resolved")}
                        type="button"
                      >
                        {agentCommentBusyId === `${asText(comment, "id")}:resolved` ? "Closing..." : "Resolve"}
                      </button>
                    </article>
                  ))}
                </div>
                <div className="source-check-list">
                  <h4>Commented targets</h4>
                  {dashboardAgentCommentTargets.length ? (
                    dashboardAgentCommentTargets.map((target) => (
                      <article className="source-check-row" key={`${asText(target, "target_kind")}-${asText(target, "target_ref")}`}>
                        <div>
                          <strong>{asText(target, "target_title", "Target")}</strong>
                          <p>{asText(target, "target_kind", "target").replace(/_/g, " ")} · {asText(target, "target_location", asText(target, "target_ref", "ref"))}</p>
                        </div>
                        <StatusPill status={asText(target, "target_status", "commented")} />
                        <span>{asText(target, "open_comment_count", "0")} open</span>
                        <time>{compactDate(target.latest_comment_at)}</time>
                      </article>
                    ))
                  ) : (
                    <EmptyState message="No commented targets yet." />
                  )}
                </div>
              </div>
            ) : (
              <EmptyState message="No agent comments yet. Add a review note to the latest output artifact." />
            )}
          </Panel>

          <Panel className="span-7" icon={<Landmark size={17} />} title="Hedge Team Hierarchy" action="reporting lines">
            <div className="org-grid">
              {dashboardAgentOrg.length ? (
                dashboardAgentOrg.map((agent) => (
                  <article className="org-row" key={asText(agent, "agent_name")}>
                    <span style={{ background: asText(agent, "color_token", "#4f46e5") }} />
                    <div>
                      <strong>{asText(agent, "agent_name", "Agent")}</strong>
                      <p>{asText(agent, "hierarchy_level", "specialist")} · reports to {asText(agent, "reports_to_agent", "Devarsh")}</p>
                      <small>{asText(agent, "mailbox_address", "mailbox pending")}</small>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No hierarchy rows loaded from agent.v_agent_org_chart." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<MessageSquareText size={17} />} title="Agent Mailboxes" action="internal email">
            <div className="mailbox-list">
              {dashboardAgentMailboxes.length ? (
                dashboardAgentMailboxes.map((mailbox) => (
                  <article className="mailbox-row" key={asText(mailbox, "mailbox_key")}>
                    <div>
                      <strong>{asText(mailbox, "agent_name", "Agent")}</strong>
                      <p>{asText(mailbox, "address", "address pending")}</p>
                    </div>
                    <span>{asText(mailbox, "unread_count", "0")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No mailboxes loaded from agent.v_agent_mailboxes." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<Inbox size={17} />} title="Agent Messages" action="handoffs">
            <div className="message-list">
              {dashboardAgentMessages.length ? (
                dashboardAgentMessages.map((message) => (
                  <article className="message-row" key={asText(message, "id")}>
                    <div className="row-title">
                      <strong>{asText(message, "subject", "Message")}</strong>
                      <span>{asText(message, "priority", "medium")}</span>
                    </div>
                    <p>{asText(message, "from_agent", "Agent")} to {asText(message, "to_agent", "Agent")}</p>
                    <small>{asText(message, "body", "").slice(0, 140)}</small>
                    <div className="panel-action-row compact">
                      <button
                        className="mini-action-button"
                        disabled={agentMessageBusyId === `${asText(message, "id")}:acknowledge` || asText(message, "status") === "acknowledged"}
                        onClick={() => void triageAgentMessageFromDashboard(message, "acknowledge")}
                        type="button"
                      >
                        Ack
                      </button>
                      <button
                        className="mini-action-button"
                        disabled={agentMessageBusyId === `${asText(message, "id")}:create_task` || Boolean(asText(message, "generated_task_id"))}
                        onClick={() => void triageAgentMessageFromDashboard(message, "create_task")}
                        type="button"
                      >
                        Task
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <EmptyState message="No agent-to-agent messages loaded." />
              )}
            </div>
          </Panel>

          <Panel className="span-6" icon={<Gauge size={17} />} title="Agent Model Routing" action="local first">
            <div className="model-list">
              {dashboardAgentModels.length ? (
                dashboardAgentModels.map((model) => (
                  <article className="model-row" key={asText(model, "agent_name")}>
                    <div>
                      <strong>{asText(model, "agent_name", "Agent")}</strong>
                      <p>{asText(model, "assigned_model", asText(model, "route_default_model", "model"))}</p>
                    </div>
                    <span>{asText(model, "max_autonomous_cost_tier", "local")}</span>
                  </article>
                ))
              ) : (
                <EmptyState message="No model routing rows loaded from agent.v_agent_model_matrix." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Gauge size={17} />} title="Model Cost Ledger" action={`${asText(dashboardModelCostSummary.find((row) => asText(row, "metric") === "estimated_cost_today_usd") ?? {}, "value", "0")} USD today`}>
            {dashboardModelCostSummary.length ? (
              <>
                <div className="employee-profile-summary">
                  {dashboardModelCostSummary.slice(0, 8).map((metric) => (
                    <div className="employee-profile-metric" key={asText(metric, "metric")}>
                      <strong>{asText(metric, "value", "0")}</strong>
                      <span>{asText(metric, "metric", "metric").replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
                <div className="artifact-registry-grid">
                  <div className="source-check-list">
                    <h4>Agent cost caps</h4>
                    {dashboardModelCostCaps.map((cap) => (
                      <article className="source-check-row" key={asText(cap, "agent_name")}>
                        <div>
                          <strong>{asText(cap, "agent_name", "Agent")}</strong>
                          <p>{asText(cap, "primary_route", "route")} · today ${asText(cap, "cost_today_usd", "0")} / ${asText(cap, "daily_cap_usd", "0")}</p>
                        </div>
                        <StatusPill status={asText(cap, "cap_status", "ok")} />
                        <span>{asText(cap, "events_today", "0")} events</span>
                        <time>{compactDate(cap.updated_at)}</time>
                      </article>
                    ))}
                  </div>
                  <div className="source-check-list">
                    <h4>Route usage</h4>
                    {dashboardModelRouteCosts.length ? (
                      dashboardModelRouteCosts.map((route) => (
                        <article className="source-check-row" key={`${asText(route, "route_name")}-${asText(route, "provider")}-${asText(route, "model_name")}`}>
                          <div>
                            <strong>{asText(route, "route_name", "route")}</strong>
                            <p>{asText(route, "provider", "provider")} · {asText(route, "model_name", "model")} · {asText(route, "total_tokens_est", "0")} est tokens</p>
                          </div>
                          <StatusPill status={asText(route, "cost_tier", "local")} />
                          <span>${asText(route, "cost_usd", "0")}</span>
                          <time>{compactDate(route.latest_event_ts)}</time>
                        </article>
                      ))
                    ) : (
                      <EmptyState message="No model route usage rows recorded yet." />
                    )}
                  </div>
                </div>
                <div className="source-check-list">
                  <h4>Recent model usage events</h4>
                  {dashboardModelCostEvents.length ? (
                    dashboardModelCostEvents.map((event) => (
                      <article className="source-check-row" key={`model-cost-${asText(event, "id")}`}>
                        <div>
                          <strong>{asText(event, "agent_name", "Agent")} · {asText(event, "model_name", "model")}</strong>
                          <p>{asText(event, "source_kind", "source")}:{asText(event, "source_ref", "n/a")} · {asText(event, "estimate_method", "estimate")}</p>
                        </div>
                        <StatusPill status={asText(event, "cost_control_status", "ok")} />
                        <span>${asText(event, "estimated_cost_usd", asText(event, "actual_cost_usd", "0"))}</span>
                        <time>{compactDate(event.event_ts)}</time>
                      </article>
                    ))
                  ) : (
                    <EmptyState message="No model usage ledger events recorded yet." />
                  )}
                </div>
              </>
            ) : (
              <EmptyState message="No model cost ledger rows loaded from agent.v_model_cost_summary." />
            )}
          </Panel>

          <Panel className="span-12" icon={<Sparkles size={17} />} title="External Skill Stack" action="Fincept / OpenAlgo / Vibe">
            <div className="external-skill-grid">
              {dashboardExternalSkills.length ? (
                dashboardExternalSkills.map((skill) => (
                  <article className="external-skill-row" key={asText(skill, "skill_key")}>
                    <div>
                      <strong>{asText(skill, "skill_name", "Skill")}</strong>
                      <p>{asText(skill, "risk_notes", "No risk note recorded.")}</p>
                    </div>
                    <span>{asText(skill, "source_family", "source")}</span>
                    <span>{asText(skill, "direct_runtime_adapter", "planned")}</span>
                    <small>{asArray(skill, "assigned_agents").slice(0, 3).join(", ") || "Unassigned"}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No external skill rows loaded from agent.v_external_skill_stack." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<GitBranch size={17} />} title="Public Source Checks" action="SEC / NSE / BSE">
            <div className="source-check-list">
              {(snapshot?.data_source_checks ?? []).length ? (
                (snapshot?.data_source_checks ?? []).slice(0, 8).map((check, index) => (
                  <article className="source-check-row" key={`${asText(check, "source_key")}-${asText(check, "checked_at")}-${index}`}>
                    <div>
                      <strong>{asText(check, "source_key", "source")}</strong>
                      <p>{asText(check, "target_url", "target")}</p>
                    </div>
                    <StatusPill status={asText(check, "status", "unknown")} />
                    <span>{asText(check, "http_status", "-")}</span>
                    <time>{compactDate(check.checked_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No source check rows found in core.data_source_checks." />
              )}
            </div>
          </Panel>

          <Panel className="span-7" icon={<DatabaseZap size={17} />} title="Source Freshness Monitor" action="targets / staleness">
            <div className="panel-action-row">
              <button className="mini-action-button" disabled={sourceFreshnessBusy} onClick={() => void checkSourceFreshnessFromDashboard()} type="button">
                {sourceFreshnessBusy ? "Checking..." : "Run freshness check"}
              </button>
            </div>
            <div className="source-check-list">
              {dashboardSourceFreshness.length ? (
                dashboardSourceFreshness.map((source) => (
                  <article className="source-check-row" key={`${asText(source, "source_key")}-${asText(source, "created_at")}`}>
                    <div>
                      <strong>{asText(source, "source_key", "source")}</strong>
                      <p>
                        target {asText(source, "freshness_target_minutes", "-")} min · stale {asText(source, "staleness_minutes", "-")} min
                      </p>
                    </div>
                    <StatusPill status={asText(source, "status", "unknown")} />
                    <span>{asText(source, "severity", "medium")}</span>
                    <time>{compactDate(source.created_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No source freshness checks yet. Run the monitor after source checks or quote refresh." />
              )}
            </div>
          </Panel>

          <Panel className="span-5" icon={<CircleAlert size={17} />} title="Open Risk Events" action="source / system">
            <div className="source-check-list">
              {dashboardRiskEvents.length ? (
                dashboardRiskEvents.map((event) => (
                  <article className="source-check-row" key={asText(event, "id")}>
                    <div>
                      <strong>{asText(event, "title", "Risk event")}</strong>
                      <p>{asText(event, "message", asText(event, "scope_ref", "open issue")).slice(0, 150)}</p>
                    </div>
                    <StatusPill status={asText(event, "status", "new")} />
                    <span>{asText(event, "severity", "medium")}</span>
                    <time>{compactDate(event.ts)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No open risk events from risk.events." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Clock3 size={17} />} title="Scheduled Freshness Cadence" action="daemon / alerts">
            <div className="source-check-list">
              {dashboardSourceFreshnessSchedulerRuns.length ? (
                dashboardSourceFreshnessSchedulerRuns.map((run) => (
                  <article className="source-check-row" key={asText(run, "run_key")}>
                    <div>
                      <strong>{asText(run, "job_key", "source_freshness_monitor")}</strong>
                      <p>
                        checked {asText(run, "checked_count", "0")} · fresh {asText(run, "fresh_count", "0")} · issues {asText(run, "stale_or_error_count", "0")}
                      </p>
                    </div>
                    <StatusPill status={asText(run, "status", "unknown")} />
                    <span>{asText(run, "scheduler_interval_seconds", "900")}s</span>
                    <time>{compactDate(run.finished_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No scheduled freshness daemon runs recorded yet." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<Search size={17} />} title="Browser Session Checks" action="CDP / profiles">
            <div className="source-check-list">
              {dashboardBrowserChecks.length ? (
                dashboardBrowserChecks.map((check) => (
                  <article className="source-check-row" key={`${asText(check, "profile_key")}-${asText(check, "connector_key")}-${asText(check, "checked_at")}`}>
                    <div>
                      <strong>{asText(check, "profile_key", "browser profile")}</strong>
                      <p>{asText(check, "connector_key", "no connector")} · {asText(check, "browser_label", "browser")}</p>
                    </div>
                    <StatusPill status={asText(check, "status", "unknown")} />
                    <span>{asText(check, "remote_debugging_port", "-")}</span>
                    <time>{compactDate(check.checked_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No browser profile checks yet. Use Check on Browser Profile Control or Browser Connector Links." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<DatabaseZap size={17} />} title="Connector Health Ledger" action="models / sources">
            <div className="source-check-list">
              {dashboardConnectorHealthChecks.length ? (
                dashboardConnectorHealthChecks.map((check) => (
                  <article className="source-check-row" key={`${asText(check, "target_kind")}-${asText(check, "target_key")}-${asText(check, "checked_at")}`}>
                    <div>
                      <strong>{asText(check, "target_key", "target")}</strong>
                      <p>{asText(check, "target_kind", "kind")} · {asText(check, "check_name", "check")}</p>
                    </div>
                    <StatusPill status={asText(check, "status", "unknown")} />
                    <span>{asText(check, "checked_by", "Jarvis")}</span>
                    <time>{compactDate(check.checked_at)}</time>
                  </article>
                ))
              ) : (
                <EmptyState message="No connector health checks yet. Use Check on a model endpoint or source connector." />
              )}
            </div>
          </Panel>

          <Panel className="span-12" icon={<DatabaseZap size={17} />} title="Pipeline Readiness" action="no seed mode">
            <div className="pipeline-list">
              {(snapshot?.pipeline_readiness ?? []).length ? (
                (snapshot?.pipeline_readiness ?? []).map((row) => (
                  <article className="pipeline-row" key={`${asText(row, "record_class")}-${asText(row, "relation_name")}`}>
                    <div>
                      <strong>{asText(row, "area", "Pipeline area")}</strong>
                      <p>{asText(row, "relation_name", "warehouse relation")}</p>
                    </div>
                    <StatusPill status={asText(row, "record_class", "unknown")} />
                    <span>{asText(row, "row_count", "0")}</span>
                    <small>{asText(row, "interpretation", "Warehouse-backed count")}</small>
                  </article>
                ))
              ) : (
                <EmptyState message="No pipeline readiness rows loaded from the API." />
              )}
            </div>
          </Panel>
        </section>
          </>
        )}
      </main>

      {false ? (
      <aside className="right-rail">
        <section className="rail-panel assistant-panel">
          <div className="rail-heading">
            <MessageSquareText size={17} aria-hidden="true" />
            <h2>Charlie Chat</h2>
          </div>
          <div className="chat-thread">
            {chatMessages.length ? (
              chatMessages.map((message) => (
                <article className={`chat-bubble chat-${message.role}`} key={message.id}>
                  <p>{message.content}</p>
                  {message.meta ? <span>{message.meta}</span> : null}
                </article>
              ))
            ) : (snapshot?.chat_turns ?? []).length ? (
              (snapshot?.chat_turns ?? []).slice(0, 3).reverse().map((turn) => (
                <article className="chat-bubble chat-assistant" key={asText(turn, "id")}>
                  <p>{asText(turn, "assistant_message", "No response recorded.")}</p>
                  <span>{asText(turn, "model_name", "route")} · {asText(turn, "model_status", "stored")}</span>
                </article>
              ))
            ) : (
              <EmptyState message="Ask Charlie a question. Responses can suggest dashboard widgets and retrieval-backed next actions." />
            )}
          </div>
          <form className="chat-form" onSubmit={submitChat}>
            <textarea
              aria-label="Chat with Charlie"
              onChange={(event) => setChatDraft(event.target.value)}
              placeholder="Ask what to monitor, which widget to add, or what changed in portfolios..."
              rows={3}
              value={chatDraft}
            />
            <button className="primary-button" disabled={chatBusy} type="submit">
              <MessageSquareText size={15} aria-hidden="true" />
              {chatBusy ? "Thinking" : "Ask"}
            </button>
          </form>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <BarChart3 size={17} aria-hidden="true" />
            <h2>Widget Intents</h2>
            <button className="rail-action-button" disabled={widgetBusy} onClick={() => void materializeWidgets()} type="button">
              {widgetBusy ? "Working" : "Materialize"}
            </button>
          </div>
          <div className="widget-intent-list">
            {dashboardWidgetIntents.length ? (
              dashboardWidgetIntents.map((widget) => (
                <div className="widget-intent-row" key={asText(widget, "id", asText(widget, "widget_key"))}>
                  <div>
                    <strong>{asText(widget, "widget_title", "Dashboard widget")}</strong>
                    <p>
                      {asText(widget, "workspace", "command")} · {asText(widget, "widget_type", "widget")}
                      {asText(widget, "materialized_widget_id") ? ` · widget #${asText(widget, "materialized_widget_id")}` : ""}
                    </p>
                  </div>
                  <StatusPill status={asText(widget, "status", "suggested")} />
                </div>
              ))
            ) : (
              <EmptyState message="No widget intents yet. Ask Charlie to show or monitor something." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <ClipboardList size={17} aria-hidden="true" />
            <h2>Agent Jobs</h2>
            <button className="rail-action-button" disabled={agentWorkerBusy} onClick={() => void runAgentWorkers()} type="button">
              {agentWorkerBusy ? "Running" : "Run agents"}
            </button>
          </div>
          <div className="agent-job-list">
            {dashboardWorkerQueue.length ? (
              dashboardWorkerQueue.map((job) => (
                <div className="agent-job-row" key={asText(job, "task_id")}>
                  <div>
                    <strong>{asText(job, "widget_title", asText(job, "title", "Dashboard job"))}</strong>
                    <p>{asText(job, "owner_agent", "Jarvis")} · {asText(job, "suggested_skill_key", "skill")}</p>
                    {asText(job, "latest_output_note_path") ? <small>{asText(job, "latest_output_note_path")}</small> : null}
                  </div>
                  <StatusBadge status={asStatus(asText(job, "task_status", "queued"), "queued")} />
                </div>
              ))
            ) : (
              <EmptyState message="No dashboard-linked agent jobs yet." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <Activity size={17} aria-hidden="true" />
            <h2>Worker Runs</h2>
          </div>
          <div className="worker-run-list">
            {dashboardWorkerRuns.length ? (
              dashboardWorkerRuns.map((run) => (
                <div className="worker-run-row" key={asText(run, "id")}>
                  <div>
                    <strong>{asText(run, "agent_name", "Agent")}</strong>
                    <p>{asText(run, "skill_key", "skill")} · task {asText(run, "task_id", "-")}</p>
                    <small>{asText(run, "output_note_path", "No note path")}</small>
                  </div>
                  <StatusPill status={asText(run, "status", "completed")} />
                </div>
              ))
            ) : (
              <EmptyState message="No agent.worker_runs yet. Run agents after widget jobs are queued." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <Gauge size={17} aria-hidden="true" />
            <h2>System Health</h2>
          </div>
          <div className="health-list">
            {dashboardHealth.map((check) => (
              <div className="health-row" key={check.name}>
                <span className={`health-dot health-${check.status}`} />
                <div>
                  <strong>{check.name}</strong>
                  <p>{check.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <Building2 size={17} aria-hidden="true" />
            <h2>Client Folios</h2>
          </div>
          <div className="client-list">
            {dashboardClients.length ? (
              dashboardClients.map((client) => (
                <div className="client-row" key={client.code}>
                  <div>
                    <strong>{client.name}</strong>
                    <p>{client.code} · {client.lastSync}</p>
                  </div>
                  <span>{client.accounts}/{client.positions}</span>
                </div>
              ))
            ) : (
              <EmptyState message="No clients loaded from portfolio.clients." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <ListChecks size={17} aria-hidden="true" />
            <h2>Workflows</h2>
          </div>
          <div className="workflow-list">
            {dashboardWorkflows.length ? (
              dashboardWorkflows.map((workflow) => (
                <div className="workflow-row" key={workflow.key}>
                  <div>
                    <strong>{workflow.name}</strong>
                    <p>{workflow.owner}</p>
                  </div>
                  <StatusPill status={workflow.status} />
                </div>
              ))
            ) : (
              <EmptyState message="No workflow registry rows loaded." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <Landmark size={17} aria-hidden="true" />
            <h2>Fincept Bridge</h2>
          </div>
          <div className="bridge-list">
            {dashboardFincept.length ? (
              dashboardFincept.map((item) => (
                <div className="bridge-row" key={item.label}>
                  <div>
                    <strong>{item.label}</strong>
                    <p>{item.detail}</p>
                  </div>
                  <StatusPill status={item.status} />
                </div>
              ))
            ) : (
              <EmptyState message="No Fincept install rows loaded." />
            )}
          </div>
        </section>

        <section className="rail-panel">
          <div className="rail-heading">
            <Clock3 size={17} aria-hidden="true" />
            <h2>Next Runs</h2>
          </div>
          <div className="run-list">
            {dashboardRuns.length ? (
              dashboardRuns.map((workflow) => (
                <div key={asText(workflow, "workflow_key", asText(workflow, "workflow_name"))}>
                  <time>{asText(workflow, "next_run_at") ? compactDate(workflow.next_run_at) : "manual"}</time>
                  <span>{asText(workflow, "workflow_name", "Workflow")} · {asText(workflow, "schedule_hint", "on demand")}</span>
                </div>
              ))
            ) : (
              <EmptyState message="No scheduled workflow rows loaded." />
            )}
          </div>
        </section>

        <section className="rail-panel focus-panel">
          <div className="rail-heading">
            <BarChart3 size={17} aria-hidden="true" />
            <h2>Build Focus</h2>
          </div>
          <ol>
            <li>No seed fallback: dashboard displays warehouse rows only.</li>
            <li>TradingView tasks are queued in Postgres.</li>
            <li>Desktop MCP needs local CDP relaunch for chart control.</li>
            <li>Next: wire real source collectors and agent workers.</li>
          </ol>
        </section>
      </aside>
      ) : null}
    </div>
  );
}

function Panel({
  action,
  children,
  className = "",
  icon,
  title
}: {
  action?: string;
  children: React.ReactNode;
  className?: string;
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          {icon}
          <h2>{title}</h2>
        </div>
        {action ? <button type="button">{action}</button> : null}
      </div>
      {children}
    </section>
  );
}

function LiveDashboardWidget({ snapshot, widget }: { snapshot: LiveSnapshot | null; widget: LiveRow }) {
  const widgetKey = asText(widget, "widget_key");
  const title = asText(widget, "widget_title", "Dashboard widget");
  const workspace = asText(widget, "workspace", "command");
  const taskStatus = asText(widget, "task_status", "queued");

  let content: React.ReactNode;
  if (widgetKey === "portfolio_latest_positions") {
    const positions = snapshot?.latest_positions.slice(0, 5) ?? [];
    content = positions.length ? (
      <div className="widget-table">
        {positions.map((position) => (
          <div className="widget-table-row" key={`${asText(position, "account_code")}-${asText(position, "symbol")}`}>
            <div>
              <strong>{asText(position, "symbol", "SYMBOL")}</strong>
              <p>{asText(position, "display_name", asText(position, "client_code", "Client"))}</p>
            </div>
            <span>{compactNumber(position.quantity)}</span>
            <span>{compactInr(position.market_value)}</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState message="No linked latest positions exposed in this snapshot." />
    );
  } else if (widgetKey === "market_signal_monitor") {
    const signals = snapshot?.signals.slice(0, 4) ?? [];
    const alerts = snapshot?.alerts.slice(0, 3) ?? [];
    content = signals.length || alerts.length ? (
      <div className="widget-stack">
        {signals.map((signal) => (
          <div className="widget-line" key={`signal-${asText(signal, "id")}`}>
            <strong>{asText(signal, "symbol", "SYMBOL")}</strong>
            <span>{asText(signal, "strategy", "strategy")} · {asText(signal, "action", "watch")}</span>
          </div>
        ))}
        {alerts.map((alert) => (
          <div className="widget-line widget-line-warn" key={`alert-${asText(alert, "id")}`}>
            <strong>{asText(alert, "symbol", "ALERT")}</strong>
            <span>{asText(alert, "title", asText(alert, "message", "open alert"))}</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState message="No live strategy signals or alerts in the current warehouse snapshot." />
    );
  } else if (widgetKey === "strategy_lab_queue") {
    const strategies = snapshot?.strategies.slice(0, 5) ?? [];
    content = strategies.length ? (
      <div className="widget-stack">
        {strategies.map((strategy) => (
          <div className="widget-line" key={asText(strategy, "strategy_key", asText(strategy, "strategy_name"))}>
            <strong>{asText(strategy, "strategy_name", "Strategy")}</strong>
            <span>{asText(strategy, "strategy_family", "family")} · {asText(strategy, "live_mode", "research")}</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState message="No strategy registry rows available." />
    );
  } else if (widgetKey === "research_filings_inbox") {
    const research = snapshot?.research_hub.slice(0, 4) ?? [];
    const inbox = snapshot?.inbox.filter((item) => asText(item, "target_workspace") === "research").slice(0, 2) ?? [];
    content = research.length || inbox.length ? (
      <div className="widget-stack">
        {research.map((row) => (
          <div className="widget-line" key={`${asText(row, "root_label")}-${asText(row, "artifact_family")}`}>
            <strong>{asText(row, "artifact_family", "Research")}</strong>
            <span>{asText(row, "root_label", "source")} · {asText(row, "artifact_count", "0")} artifacts</span>
          </div>
        ))}
        {inbox.map((item) => (
          <div className="widget-line" key={`research-inbox-${asText(item, "id")}`}>
            <strong>{asText(item, "title", "Research task")}</strong>
            <span>{asText(item, "owner_agent", "Research")}</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState message="No research artifacts or research inbox items in this snapshot." />
    );
  } else if (widgetKey === "model_runtime_status") {
    const routes = snapshot?.model_routes.slice(0, 5) ?? [];
    content = routes.length ? (
      <div className="widget-stack">
        {routes.map((route) => (
          <div className="widget-line" key={asText(route, "route_name")}>
            <strong>{asText(route, "route_name", "route")}</strong>
            <span>{asText(route, "default_provider", "provider")} / {asText(route, "default_model", "model")}</span>
          </div>
        ))}
      </div>
    ) : (
      <EmptyState message="No model routes loaded." />
    );
  } else {
    content = (
      <div className="widget-stack">
        <div className="widget-line">
          <strong>{asText(widget, "query_ref", "snapshot")}</strong>
          <span>{asText(widget, "widget_type", "widget")} · {asText(widget, "owner_agent", "Jarvis")}</span>
        </div>
      </div>
    );
  }

  return (
    <article className={`live-widget-card widget-${asText(widget, "widget_type", "generic")}`}>
      <div className="live-widget-heading">
        <div>
          <strong>{title}</strong>
          <p>{workspace} · {asText(widget, "query_ref", "snapshot")}</p>
        </div>
        <StatusPill status={asText(widget, "status", "active")} />
      </div>
      {content}
      <div className="live-widget-footer">
        <span>Task {taskStatus}</span>
        <time>{compactDate(widget.last_refreshed_at || widget.updated_at)}</time>
      </div>
    </article>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function StatusBadge({ status }: { status: Status }) {
  return <span className={`status-badge status-${status}`}>{statusLabel[status]}</span>;
}

function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`severity-badge severity-${severity}`}>{severity}</span>;
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill status-${status}`}>{status.replace("_", " ")}</span>;
}

function ScopedCommandCenterApp({ activeWorkspace, setActiveWorkspace, setInterfaceMode }: CommandCenterAppProps) {
  const [command, setCommand] = useState("");
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandNotice, setCommandNotice] = useState("");
  const [liveStatus, setLiveStatus] = useState<"loading" | "online" | "offline">("loading");
  const [uiError, setUiError] = useState("");
  const [workspaceConfig, setWorkspaceConfig] = useState<WorkspaceConfig | null>(null);
  const [workspaceManagerOpen, setWorkspaceManagerOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const activeWorkspaceLabel = baseWorkspaces.find((workspace) => workspace.id === activeWorkspace)?.label ?? "Command Center";

  useEffect(() => {
    void fetchWorkspaceConfig().then(setWorkspaceConfig).catch(() => undefined);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = workspaceConfig?.profile.theme ?? "terminal_dark";
    root.dataset.density = workspaceConfig?.profile.density ?? "compact";
  }, [workspaceConfig]);

  const refreshScopedWorkspace = () => {
    const events: Partial<Record<WorkspaceId, string>> = {
      command: "aios:mission-control-refresh",
      system: "aios:system-health-refresh",
      portfolio: "aios:portfolio-office-refresh",
      clients: "aios:portfolio-office-refresh",
      tactical: "aios:department-terminal-refresh",
      research: "aios:research-ideas-refresh",
      ideas: "aios:research-ideas-refresh",
      arsenal: "aios:strategy-arsenal-refresh",
      models: "aios:integration-gateway-refresh",
      trading: "aios:trading-quant-risk-refresh",
      quant: "aios:trading-quant-risk-refresh",
      risk: "aios:trading-quant-risk-refresh",
      reports: "aios:reports-refresh"
    };
    if (["approvals", "agents", "departments", "tactical", "committees", "governance", "capital", "treasury"].includes(activeWorkspace)) {
      window.dispatchEvent(new Event("aios:department-terminal-refresh"));
      return;
    }
    const eventName = events[activeWorkspace];
    if (eventName) window.dispatchEvent(new Event(eventName));
  };

  const submitCommand = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanCommand = command.trim();
    if (!cleanCommand || commandBusy) return;
    const routed = routeCommand(cleanCommand);
    const title = cleanCommand.length > 74 ? `${cleanCommand.slice(0, 71)}...` : cleanCommand;
    setCommand("");
    setCommandBusy(true);
    setUiError("");
    setCommandNotice("");
    try {
      const normalized = cleanCommand.toLowerCase();
      const workspaceWidgets = workspaceConfig?.widgets.filter((widget) => String(widget.workspace ?? "") === activeWorkspace) ?? [];
      const mentionedWidget = workspaceWidgets.find((widget) => {
        const key = String(widget.widget_key ?? "").replace(/_/g, " ").toLowerCase();
        const title = String(widget.widget_title ?? "").toLowerCase();
        return normalized.includes(key) || title.split(/\s+/).filter((term) => term.length > 4).some((term) => normalized.includes(term));
      });
      const columnMatch = normalized.match(/(?:set|use|make|change).*?([123])\s*columns?/);
      if (columnMatch) {
        setWorkspaceConfig(await updateWorkspaceConfig({ actor: "Charlie Munger", column_count: Number(columnMatch[1]), profile_key: workspaceConfig?.profile.profile_key ?? "devarsh", workspace_key: activeWorkspace }));
        setCommandNotice(`Charlie changed ${activeWorkspaceLabel} to ${columnMatch[1]} columns.`);
        setLiveStatus("online");
        return;
      }
      if (mentionedWidget && /\b(hide|show|move)\b/.test(normalized)) {
        const widgetLayout = mentionedWidget.layout && typeof mentionedWidget.layout === "object" ? mentionedWidget.layout as Record<string, unknown> : {};
        const currentOrder = Number(widgetLayout.order ?? 100);
        const patch: Record<string, unknown> = /\bhide\b/.test(normalized)
          ? { status: "hidden" }
          : /\bshow\b/.test(normalized)
            ? { status: "active" }
            : { order: /\bup\b/.test(normalized) ? Math.max(0, currentOrder - 10) : currentOrder + 10 };
        await updateDashboardWidget({ actor: "Charlie Munger", widget_id: Number(mentionedWidget.id), ...patch });
        setWorkspaceConfig(await fetchWorkspaceConfig(workspaceConfig?.profile.profile_key ?? "devarsh"));
        setCommandNotice(`Charlie updated ${String(mentionedWidget.widget_title ?? "the widget")}.`);
        setLiveStatus("online");
        return;
      }
      if (["dashboard", "widget", "show", "view", "monitor", "watch"].some((term) => normalized.includes(term))) {
        const response = await sendChat({
          actor: "Devarsh",
          deterministic_only: true,
          include_client_context: false,
          message: cleanCommand,
          metadata: { source_surface: "scoped_command_center", workspace: activeWorkspace },
          privacy_class: "internal",
          session_key: "ai-office-workspace-management",
          workspace: activeWorkspace
        });
        setWorkspaceConfig(await fetchWorkspaceConfig(workspaceConfig?.profile.profile_key ?? "devarsh"));
        const created = Array.isArray(response.dashboard_widgets) ? response.dashboard_widgets.length : 0;
        setCommandNotice(created ? `Charlie materialized ${created} source-bound widget${created === 1 ? "" : "s"}.` : response.message.split("\n")[0]);
        setLiveStatus("online");
        refreshScopedWorkspace();
        return;
      }
      if (routed.agent === "Trading Desk") {
        await createTradingViewTask({
          task_title: title,
          task_type: "chart_review",
          requested_by: "Charlie Munger",
          owner_agent: "Trading Desk Agent",
          priority: routed.priority,
          symbols: extractSymbols(cleanCommand),
          instruction: cleanCommand,
          source_ref: "ai_office_scoped_command_bar",
          evidence: [{ source: "AI Office scoped command bar", workspace: activeWorkspaceLabel }],
          metadata: { routed_agent: routed.agent }
        });
      } else {
        const handoff = await createAgentMessage({
          body: cleanCommand,
          from_agent: "Charlie Munger",
          metadata: { source_surface: "scoped_command_center", workspace: activeWorkspace },
          priority: routed.priority,
          subject: title,
          thread_key: `command-${Date.now()}`,
          to_agent: routed.agent
        });
        await triageAgentMessage({
          action: "create_task",
          actor: "Jarvis",
          message_id: asText(handoff, "id"),
          priority: routed.priority,
          recommended_action: routed.recommendedAction,
          target_workspace: activeWorkspace,
          task_objective: cleanCommand,
          task_title: title
        });
      }
      setCommandNotice(`Charlie routed this assignment to ${routed.agent}; Jarvis created the durable handoff.`);
      setLiveStatus("online");
      refreshScopedWorkspace();
    } catch (reason) {
      setUiError(reason instanceof Error ? reason.message : "Command write failed");
      setLiveStatus("offline");
    } finally {
      setCommandBusy(false);
    }
  };

  let workspaceContent: ReactNode;
  if (activeWorkspace === "system") workspaceContent = <SystemHealthWorkspace onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "command") workspaceContent = <MissionControlWorkspace onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "models") workspaceContent = <IntegrationGatewayWorkspace onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "departments") workspaceContent = <DepartmentDeskWorkspace onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "tactical") workspaceContent = <DepartmentDeskWorkspace initialDepartment="tactical" onStatusChange={setLiveStatus} />;
  else if (["approvals", "agents", "committees", "governance", "capital", "treasury"].includes(activeWorkspace)) workspaceContent = <DepartmentTerminalWorkspace mode={activeWorkspace as TerminalWorkspace} onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "portfolio" || activeWorkspace === "clients") workspaceContent = <PortfolioOfficeWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "research" || activeWorkspace === "ideas") workspaceContent = <ResearchIdeasWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "arsenal") workspaceContent = <StrategyArsenalWorkspace onStatusChange={setLiveStatus} />;
  else if (activeWorkspace === "trading" || activeWorkspace === "quant" || activeWorkspace === "risk") workspaceContent = <TradingQuantRiskWorkspace mode={activeWorkspace} onStatusChange={setLiveStatus} />;
  else workspaceContent = <ReportsWorkspace onStatusChange={setLiveStatus} />;
  workspaceContent = <WorkspaceErrorBoundary workspace={activeWorkspaceLabel}>{workspaceContent}</WorkspaceErrorBoundary>;
  const activeLayout = workspaceConfig?.layouts.find((item) => item.workspace_key === activeWorkspace);
  const activeWidgets = workspaceConfig?.widgets.filter((item) => String(item.workspace ?? "") === activeWorkspace) ?? [];
  const visibleWorkspaces = new Set(
    Array.isArray(workspaceConfig?.profile.navigation?.visible)
      ? workspaceConfig.profile.navigation.visible.map(String)
      : baseWorkspaces.map((workspace) => workspace.id)
  );

  return (
    <div className={`app-shell app-shell-focused ${sidebarCollapsed ? "sidebar-is-collapsed" : ""}`}>
      <ScrollableRegionAccessibility />
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><CommandIcon size={18} aria-hidden="true" /></div><div><p>AI Office</p><span>Charlie orchestrator</span></div></div>
        <nav className="workspace-nav workspace-nav-grouped" aria-label="AI Office workspaces">
          {workspaceGroups.map((group) => <section className="workspace-nav-group" key={group.label}>
            <span>{group.label}</span>
            {group.workspaces.filter((workspaceId) => visibleWorkspaces.has(workspaceId)).map((workspaceId) => {
              const workspace = baseWorkspaces.find((item) => item.id === workspaceId);
              if (!workspace) return null;
              const Icon = workspaceIcons[workspace.id];
              return <button className={workspace.id === activeWorkspace ? "workspace-link active" : "workspace-link"} key={workspace.id} onClick={() => setActiveWorkspace(workspace.id)} type="button" title={workspace.label}><Icon size={17} aria-hidden="true" /><span>{workspace.label}</span></button>;
            })}
          </section>)}
        </nav>
        <div className="sidebar-footer"><div><span className="mini-label">Local mode</span><p>{liveStatus === "online" ? "Live DB linked" : liveStatus === "loading" ? "Connecting" : "Warehouse required"}</p></div><ShieldCheck size={18} aria-hidden="true" /></div>
      </aside>
      <main className="main">
        <header className="topbar">
          <button aria-label="Toggle sidebar" className="icon-button" onClick={() => setSidebarCollapsed((value) => !value)} type="button" title="Toggle sidebar"><PanelLeft size={18} aria-hidden="true" /></button>
          <div className="workspace-title"><span>AI Office</span><h1>{activeWorkspaceLabel}</h1></div>
          <div className="topbar-actions">
            <span className={`live-status live-${liveStatus}`}>{liveStatus === "online" ? "Live warehouse" : liveStatus === "loading" ? "Connecting" : "Warehouse offline"}</span>
            <button className="ghost-button" onClick={() => setInterfaceMode("office")} type="button"><Building2 size={16} aria-hidden="true" />Live Office</button>
            <button className="ghost-button" onClick={() => setActiveWorkspace("reports")} type="button"><Search size={16} aria-hidden="true" />Search memory</button>
            <button className="icon-button" onClick={() => setWorkspaceManagerOpen(true)} type="button" title="Customize workspace"><SlidersHorizontal size={18} aria-hidden="true" /></button>
            <button aria-label="Open approval queue" className="icon-button" onClick={() => setActiveWorkspace("approvals")} type="button" title="Approval queue"><Bell size={18} aria-hidden="true" /></button>
          </div>
        </header>
        <section className="institutional-control-strip" aria-label="Investment and execution control notice">
          <span><ShieldCheck size={14} aria-hidden="true" />Research and decision support</span>
          <span>Devarsh retains final investment authority</span>
          <strong><LockKeyhole size={13} aria-hidden="true" />Broker execution locked by default</strong>
        </section>
        <section className="command-panel" aria-label="Charlie Munger command bar">
          <div className="command-copy"><div className="jarvis-avatar"><Sparkles size={18} aria-hidden="true" /></div><div><p>Charlie Munger</p><span>Routes work through Jarvis runtime, agents, SQL, and Obsidian write-back.</span></div></div>
          <form className="command-form" onSubmit={submitCommand}><input aria-label="Command Charlie Munger" onChange={(event) => setCommand(event.target.value)} placeholder="Ask Charlie to review portfolios, research holdings, inspect signals, or open a task..." value={command}/><button className="primary-button" disabled={commandBusy} type="submit"><Plus size={16} aria-hidden="true" />{commandBusy ? "Queueing" : "Assign"}</button></form>
          {uiError ? <div className="error-strip">{uiError}</div> : null}
          {commandNotice ? <div className="success-strip">{commandNotice}</div> : null}
          <div className="quick-command-row">{quickCommands.map((quickCommand) => <button key={quickCommand} onClick={() => setCommand(quickCommand)} type="button" title={quickCommand}>{quickCommand}</button>)}</div>
        </section>
        <WorkspaceWidgetRail columns={activeLayout?.column_count ?? 2} data={workspaceConfig?.widget_data ?? {}} widgets={activeWidgets} workspaceLabel={activeWorkspaceLabel}/>
        {workspaceContent}
      </main>
      {workspaceManagerOpen && workspaceConfig ? <WorkspaceManager config={workspaceConfig} onChanged={setWorkspaceConfig} onClose={() => setWorkspaceManagerOpen(false)} workspace={activeWorkspace} /> : null}
    </div>
  );
}

function App() {
  const { activeWorkspace, interfaceMode, openCommandWorkspace, setActiveWorkspace, setInterfaceMode } = useWorkspaceRoute();

  if (interfaceMode === "office") {
    return (
      <WorkspaceErrorBoundary workspace="Live AI Office">
        <OfficeWorkspace
          activeWorkspace={activeWorkspace}
          onExit={() => setInterfaceMode("command")}
          onSelectWorkspace={openCommandWorkspace}
        />
      </WorkspaceErrorBoundary>
    );
  }

  return (
    <ScopedCommandCenterApp
      activeWorkspace={activeWorkspace}
      setActiveWorkspace={setActiveWorkspace}
      setInterfaceMode={setInterfaceMode}
    />
  );
}

export default App;
