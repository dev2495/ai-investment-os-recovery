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
  long_term_checklists: LiveRow[];
  long_term_valuation_models: LiveRow[];
  long_term_monte_carlo_runs: LiveRow[];
  long_term_research_updates: LiveRow[];
  committee_queue: LiveRow[];
  latest_news: LiveRow[];
  news_brief: LiveRow[];
  filing_intelligence: LiveRow[];
  market_events: LiveRow[];
  market_holidays: LiveRow[];
  feed_registry: LiveRow[];
  news_ingestion_runs: LiveRow[];
  filing_collector_runs: LiveRow[];
  filing_pdf_extraction_runs: LiveRow[];
  news_source_checks: LiveRow[];
  corporate_filings: LiveRow[];
  special_situations: LiveRow[];
  special_memos: LiveRow[];
  special_spreads: LiveRow[];
  generated_ideas: LiveRow[];
  research_papers: LiveRow[];
  paper_strategy_hypotheses: LiveRow[];
  discovery_candidates: LiveRow[];
  idea_dossiers: LiveRow[];
  output_artifacts: LiveRow[];
  watchlist: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchResearchIdeasSnapshot(): Promise<ResearchIdeasSnapshot> {
  const response = await fetch(`${API_URL}/api/research-ideas/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Research and Ideas API returned ${response.status}`);
  return response.json() as Promise<ResearchIdeasSnapshot>;
}

export interface LongTermMonteCarloRequest {
  holding_thesis_id: number;
  actor: string;
  horizon_years: number;
  simulations: number;
  seed: number;
  starting_multiple?: number;
  starting_multiple_source?: string;
  terminal_multiple_low: number;
  terminal_multiple_base: number;
  terminal_multiple_high: number;
  annual_volatility: number;
}

export async function runLongTermMonteCarlo(payload: LongTermMonteCarloRequest): Promise<LiveRow> {
  const response = await fetch(`${API_URL}/api/portfolio/long-term-thesis/monte-carlo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json() as LiveRow & { error?: string };
  if (!response.ok) throw new Error(result.error || `Monte Carlo API returned ${response.status}`);
  return result;
}

export interface ResearchPaperIngestRequest {
  title: string;
  source_key: string;
  source_url?: string;
  pdf_url?: string;
  local_path?: string;
  topics?: string[];
  actor: string;
}

export async function ingestResearchPaper(payload: ResearchPaperIngestRequest): Promise<LiveRow> {
  const response = await fetch(`${API_URL}/api/research/papers/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json() as LiveRow & { error?: string };
  if (!response.ok) throw new Error(result.error || `Research paper ingest API returned ${response.status}`);
  return result;
}

export interface PaperHypothesisRequest {
  paper_id: number;
  actor: string;
  hypotheses: Array<{
    title: string;
    edge_hypothesis: string;
    timeframe?: string;
    implementation_notes?: string;
  }>;
}

export async function createPaperHypotheses(payload: PaperHypothesisRequest): Promise<LiveRow> {
  const response = await fetch(`${API_URL}/api/research/papers/hypotheses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json() as LiveRow & { error?: string };
  if (!response.ok) throw new Error(result.error || `Paper hypothesis API returned ${response.status}`);
  return result;
}

export interface WatchlistItemInput {
  symbol: string;
  exchange?: string;
  company_name?: string;
  item_type?: "research" | "idea" | "catalyst" | "options" | "event" | "technical";
  priority?: "low" | "medium" | "high" | "critical";
  thesis?: string;
  catalyst?: string;
  invalidation?: string;
  review_on?: string;
  actor?: string;
}

export async function upsertWatchlistItem(payload: WatchlistItemInput): Promise<LiveRow> {
  const response = await fetch(`${API_URL}/api/watchlist/items/upsert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = await response.json() as LiveRow & { error?: string; message?: string };
  if (!response.ok) throw new Error(result.message || result.error || `Watchlist API returned ${response.status}`);
  return result;
}
