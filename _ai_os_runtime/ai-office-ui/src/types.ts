export type Severity = "low" | "medium" | "high" | "critical";

export type Status = "queued" | "running" | "needs_review" | "approved" | "blocked" | "done";

export type WorkspaceId =
  | "command"
  | "approvals"
  | "agents"
  | "committees"
  | "portfolio"
  | "clients"
  | "research"
  | "ideas"
  | "trading"
  | "quant"
  | "risk"
  | "capital"
  | "treasury"
  | "models"
  | "reports"
  | "system";

export interface Workspace {
  id: WorkspaceId;
  label: string;
  count?: number;
}

export interface Metric {
  label: string;
  value: string;
  delta: string;
  tone: "neutral" | "good" | "warn" | "bad";
}

export interface BriefLine {
  time: string;
  title: string;
  detail: string;
  tone: "neutral" | "good" | "warn" | "bad";
}

export interface InboxItem {
  id: string;
  title: string;
  agent: string;
  status: Status;
  priority: Severity;
  evidence: string[];
  recommendedAction: string;
  updatedAt: string;
}

export interface ApprovalItem {
  id: string;
  title: string;
  owner: string;
  type: "client_report" | "trade_action" | "data_import" | "system_change";
  risk: Severity;
  status: "pending" | "approved" | "rejected";
  summary: string;
}

export interface PortfolioAlert {
  id: string;
  client: string;
  symbol: string;
  issue: string;
  severity: Severity;
  owner: string;
}

export interface SignalItem {
  id: string;
  symbol: string;
  strategy: string;
  timeframe: string;
  direction: "long" | "short" | "watch";
  confidence: number;
  state: "new" | "reviewing" | "ignored" | "approved";
}

export interface AgentStatus {
  name: string;
  role: string;
  state: "idle" | "running" | "waiting" | "blocked";
  currentTask: string;
  costTier: "local" | "hybrid" | "codex";
}

export interface HealthCheck {
  name: string;
  status: "online" | "degraded" | "offline";
  detail: string;
}

export interface ControlModule {
  key: string;
  name: string;
  status: "active" | "installed" | "mapped" | "planned";
  priority: Severity;
  owner: string;
  workspace: string;
  nextAction: string;
}

export interface DataSourceItem {
  key: string;
  name: string;
  type: string;
  provider: string;
  status: "installed" | "imported" | "mapped" | "planned";
  cadence: string;
  owner: string;
}

export interface StrategyRegistryItem {
  key: string;
  name: string;
  family: string;
  mode: "paper" | "research";
  status: "mapped" | "research" | "planned";
  timeframe: string;
  owner: string;
  risk: Severity;
}

export interface WorkflowItem {
  key: string;
  name: string;
  status: "active" | "installed" | "mapped" | "planned";
  owner: string;
  permission: string;
}

export interface FinceptBridgeItem {
  label: string;
  status: "installed" | "mapped" | "planned";
  detail: string;
}

export interface ClientControlItem {
  code: string;
  name: string;
  accounts: number;
  positions: number;
  staged: number;
  lastSync: string;
}

export interface ManualUpdateItem {
  id: string;
  clientCode: string;
  accountCode: string;
  symbol: string;
  quantity: string;
  status: "staged" | "applied";
  source: string;
  asOf: string;
}
