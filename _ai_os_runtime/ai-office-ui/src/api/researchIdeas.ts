import type { LiveRow } from "./live";

export interface ResearchIdeasSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  research_hub: LiveRow[];
  long_term_theses: LiveRow[];
  coverage_summary: LiveRow[];
  coverage_queue: LiveRow[];
  committee_queue: LiveRow[];
  latest_news: LiveRow[];
  corporate_filings: LiveRow[];
  special_situations: LiveRow[];
  special_memos: LiveRow[];
  special_spreads: LiveRow[];
  generated_ideas: LiveRow[];
  discovery_candidates: LiveRow[];
  idea_dossiers: LiveRow[];
  output_artifacts: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchResearchIdeasSnapshot(): Promise<ResearchIdeasSnapshot> {
  const response = await fetch(`${API_URL}/api/research-ideas/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Research and Ideas API returned ${response.status}`);
  return response.json() as Promise<ResearchIdeasSnapshot>;
}
