import type { LiveRow, TradingViewCdpStatus } from "./live";

export interface MissionControlSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  tradingview_cdp: TradingViewCdpStatus;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  metrics: LiveRow[];
  inbox: LiveRow[];
  approvals: LiveRow[];
  approval_summary: LiveRow[];
  agent_messages: LiveRow[];
  tasks: LiveRow[];
  chat_turns: LiveRow[];
  widget_intents: LiveRow[];
  dashboard_widgets: LiveRow[];
  agent_worker_queue: LiveRow[];
  agent_worker_runs: LiveRow[];
  task_provider_gates: LiveRow[];
  source_freshness: LiveRow[];
  filing_summary: LiveRow[];
  latest_filings: LiveRow[];
  latest_news: LiveRow[];
  watchlist: LiveRow[];
  latest_reports: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchMissionControlSnapshot(): Promise<MissionControlSnapshot> {
  const response = await fetch(`${API_URL}/api/mission-control/snapshot`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Mission Control API returned ${response.status}`);
  }
  return response.json() as Promise<MissionControlSnapshot>;
}

