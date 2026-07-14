import type { LiveRow } from "./live";

export interface StrategyArsenalSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  summary: LiveRow[];
  control_board: LiveRow[];
  intakes: LiveRow[];
  discovery_triage: LiveRow[];
  templates: LiveRow[];
  discovery_runs: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchStrategyArsenalSnapshot(): Promise<StrategyArsenalSnapshot> {
  const response = await fetch(`${API_URL}/api/strategy-arsenal/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Strategy Arsenal API returned ${response.status}`);
  return response.json() as Promise<StrategyArsenalSnapshot>;
}
