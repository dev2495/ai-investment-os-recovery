import type { LiveRow, TradingViewCdpStatus } from "./live";

export interface TradingQuantRiskSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  tradingview_cdp: TradingViewCdpStatus;
  data_mode: { seed_data_allowed: boolean; source: string };
  payload_profile: { query_count: number; row_count: number };
  quant_lab: LiveRow[];
  model_validation: LiveRow[];
  promotion_board: LiveRow[];
  strategy_committee: LiveRow[];
  paper_monitors: LiveRow[];
  drift_checks: LiveRow[];
  retirement_queue: LiveRow[];
  signals: LiveRow[];
  alerts: LiveRow[];
  tradingview_tasks: LiveRow[];
  tradingview_templates: LiveRow[];
  tradingview_template_approvals: LiveRow[];
  trade_activity: LiveRow[];
  paper_trade_summary: LiveRow[];
  risk_summary: LiveRow[];
  risk_limits: LiveRow[];
  institutional_risk_run: LiveRow[];
  institutional_risk_metrics: LiveRow[];
  institutional_stress: LiveRow[];
  institutional_liquidity: LiveRow[];
  institutional_factors: LiveRow[];
  institutional_risk_summary: LiveRow[];
  limited_live_requests: LiveRow[];
  order_intents: LiveRow[];
  execution_control: LiveRow[];
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

export async function fetchTradingQuantRiskSnapshot(): Promise<TradingQuantRiskSnapshot> {
  const response = await fetch(`${API_URL}/api/trading-quant-risk/snapshot`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Trading, Quant, and Risk API returned ${response.status}`);
  return response.json() as Promise<TradingQuantRiskSnapshot>;
}
