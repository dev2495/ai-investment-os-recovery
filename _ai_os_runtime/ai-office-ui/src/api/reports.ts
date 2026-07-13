import type { LiveRow } from "./live";

export interface ReportsSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  artifact_summary: LiveRow[];
  artifacts: LiveRow[];
  artifact_gaps: LiveRow[];
  worker_runs: LiveRow[];
  research_hub: LiveRow[];
  raw_artifacts: LiveRow[];
  lineage_summary: LiveRow[];
  artifact_lineage: LiveRow[];
  import_coverage: LiveRow[];
  report_schedules: LiveRow[];
  report_runs: LiveRow[];
  chat_turns: LiveRow[];
  blueprint_summary: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchReportsSnapshot(): Promise<ReportsSnapshot> {
  const response = await fetch(`${API_URL}/api/reports/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Reports API returned ${response.status}`);
  return response.json() as Promise<ReportsSnapshot>;
}
