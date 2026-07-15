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
  report_scheduler_health: LiveRow[];
  report_scheduler_invocations: LiveRow[];
  chat_turns: LiveRow[];
  blueprint_summary: LiveRow[];
  execution_control: LiveRow[];
  local_artifact_summary: LiveRow[];
  local_artifact_ingestions: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchReportsSnapshot(): Promise<ReportsSnapshot> {
  const response = await fetch(`${API_URL}/api/reports/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Reports API returned ${response.status}`);
  return response.json() as Promise<ReportsSnapshot>;
}

export async function runScheduledReports(payload: { report_key?: string; force?: boolean; actor?: string }): Promise<LiveRow> {
  const response = await fetch(`${API_URL}/api/reports/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || `Scheduled report runner returned ${response.status}`);
  return body as LiveRow;
}

export interface LocalArtifactIntake {
  local_path: string;
  title?: string;
  sensitivity: "public" | "internal" | "private" | "client_private" | "restricted";
  suggested_destination?: string;
  actor?: string;
  operator_confirmed: true;
}

export async function ingestLocalArtifact(payload: LocalArtifactIntake): Promise<{ status: string; result: LiveRow }> {
  const response = await fetch(`${API_URL}/api/artifacts/local/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || `Local artifact intake returned ${response.status}`);
  return body as { status: string; result: LiveRow };
}

export type LocalArtifactUpload = Omit<LocalArtifactIntake, "local_path" | "operator_confirmed">;

export async function uploadLocalArtifact(file: File, payload: LocalArtifactUpload): Promise<{ status: string; result: LiveRow }> {
  const query = new URLSearchParams({
    file_name: file.name,
    title: payload.title || "",
    sensitivity: payload.sensitivity,
    suggested_destination: payload.suggested_destination || "",
    actor: payload.actor || "Devarsh via Reports Terminal",
  });
  const response = await fetch(`${API_URL}/api/artifacts/local/upload?${query.toString()}`, {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || `Local artifact upload returned ${response.status}`);
  return body as { status: string; result: LiveRow };
}
