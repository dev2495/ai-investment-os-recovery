import type { LiveRow } from "./live";

export interface PortfolioOfficeSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  clients: LiveRow[];
  client_accounts: LiveRow[];
  latest_positions: LiveRow[];
  investment_books: LiveRow[];
  book_positions: LiveRow[];
  symbol_book_exposure: LiveRow[];
  client_book_exposure: LiveRow[];
  cross_book_conflicts: LiveRow[];
  coordination_questions: LiveRow[];
  position_gap_summary: LiveRow[];
  remediation_summary: LiveRow[];
  portfolio_intelligence: LiveRow[];
  manual_updates: LiveRow[];
  client_onboarding: LiveRow[];
  client_suitability: LiveRow[];
  account_changes: LiveRow[];
  holding_reconciliation: LiveRow[];
  p2cursor_reconciliation: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchPortfolioOfficeSnapshot(): Promise<PortfolioOfficeSnapshot> {
  const response = await fetch(`${API_URL}/api/portfolio-office/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Portfolio Office API returned ${response.status}`);
  return response.json() as Promise<PortfolioOfficeSnapshot>;
}
