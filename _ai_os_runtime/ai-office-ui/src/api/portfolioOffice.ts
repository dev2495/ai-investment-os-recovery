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
  cash_ledger: LiveRow[];
  tax_lot_summary: LiveRow[];
  client_nav: LiveRow[];
  client_performance: LiveRow[];
  performance_attribution: LiveRow[];
  client_report_delivery: LiveRow[];
  p2cursor_reconciliation: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchPortfolioOfficeSnapshot(): Promise<PortfolioOfficeSnapshot> {
  const response = await fetch(`${API_URL}/api/portfolio-office/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Portfolio Office API returned ${response.status}`);
  return response.json() as Promise<PortfolioOfficeSnapshot>;
}

async function post(path: string, body: Record<string, unknown>): Promise<LiveRow> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const payload = await response.json() as LiveRow;
  if (!response.ok) throw new Error(String(payload.error || `Portfolio Office API returned ${response.status}`));
  return payload;
}

export function stageClientCashEntry(body: Record<string, unknown>): Promise<LiveRow> {
  return post("/api/client-office/cash/stage", body);
}

export function resolveClientCashEntry(body: Record<string, unknown>): Promise<LiveRow> {
  return post("/api/client-office/cash/resolve", body);
}

export function runClientAccounting(body: Record<string, unknown>): Promise<LiveRow> {
  return post("/api/client-office/accounting/run", body);
}

export function resolveClientReportDelivery(body: Record<string, unknown>): Promise<LiveRow> {
  return post("/api/client-office/report-delivery/resolve", body);
}
