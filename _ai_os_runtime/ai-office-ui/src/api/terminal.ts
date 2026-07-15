import type { LiveRow } from "./live";

export type TerminalWorkspace = "approvals" | "agents" | "committees" | "governance" | "capital" | "treasury" | "models";
export type CustomizableWorkspace = TerminalWorkspace | "arsenal";

export interface DepartmentTerminalSnapshot {
  generated_at: string;
  workspace: TerminalWorkspace;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  execution_control: LiveRow[];
  widgets: LiveRow[];
  summary: LiveRow[];
  primary: LiveRow[];
  secondary?: LiveRow[];
  tertiary?: LiveRow[];
  departments?: LiveRow[];
  schedules?: LiveRow[];
  committees?: LiveRow[];
}

export interface WorkspaceProfile {
  profile_id: number;
  profile_key: string;
  profile_name: string;
  owner_name: string;
  is_active: boolean;
  default_workspace: string;
  theme: "terminal_dark" | "terminal_light";
  density: "compact" | "standard";
  navigation: Record<string, unknown>;
  preferences: Record<string, unknown>;
  version: number;
  updated_at: string;
}

export interface WorkspaceLayout {
  layout_id: number;
  workspace_key: CustomizableWorkspace;
  module_order: string[];
  hidden_modules: string[];
  column_count: number;
  settings: Record<string, unknown>;
  updated_by: string;
  updated_at: string;
}

export interface WorkspaceConfig {
  profile: WorkspaceProfile;
  layouts: WorkspaceLayout[];
  widgets: LiveRow[];
  data_mode: { seed_data_allowed: boolean; source: string };
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.message || payload?.error || `HTTP ${response.status}`);
  return payload as T;
}

export function fetchDepartmentTerminal(workspace: TerminalWorkspace): Promise<DepartmentTerminalSnapshot> {
  return request(`/api/department-terminal/snapshot?workspace=${encodeURIComponent(workspace)}`);
}

export function proposeCapitalPolicy(input: Record<string, unknown>): Promise<LiveRow> {
  return request("/api/capital/policies/propose", { method: "POST", body: JSON.stringify(input) });
}

export function runCapitalAllocationAnalysis(input: Record<string, unknown>): Promise<LiveRow> {
  return request("/api/capital/analysis/run", { method: "POST", body: JSON.stringify(input) });
}

export function decideCapitalCommittee(input: Record<string, unknown>): Promise<LiveRow> {
  return request("/api/capital/committee/decision", { method: "POST", body: JSON.stringify(input) });
}

export function materializeAgentSchedules(input: { actor?: string; limit?: number } = {}): Promise<LiveRow> {
  return request("/api/agents/schedules/run", { method: "POST", body: JSON.stringify(input) });
}

export function fetchWorkspaceConfig(profileKey = "devarsh"): Promise<WorkspaceConfig> {
  return request(`/api/workspaces/config?profile_key=${encodeURIComponent(profileKey)}`);
}

export function updateWorkspaceConfig(input: Record<string, unknown>): Promise<WorkspaceConfig> {
  return request("/api/workspaces/config/update", { method: "POST", body: JSON.stringify(input) });
}

export function updateDashboardWidget(input: Record<string, unknown>): Promise<LiveRow> {
  return request("/api/dashboard/widgets/update", { method: "POST", body: JSON.stringify(input) });
}
