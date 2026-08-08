/**
 * AI Investment OS — Action Mutations
 *
 * Typed POST wrappers for the write endpoints, with automatic query
 * invalidation. Grouped by domain so each terminal can import just what
 * it needs. Replaces the 98 ad-hoc functions in the old live.ts god-module.
 *
 * Safety: NO execution endpoints here. Live trading, kill-switch engage,
 * and limited-live are deliberately NOT exposed as casual mutations — they
 * live in queries.ts with explicit, prominent hooks so they can't be
 * triggered accidentally.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { post } from "./client";
import type { LiveRow } from "./liveRow";

/** Common query keys to invalidate (imported from queries.ts to avoid a cycle). */
const Q = {
  missionControl: ["mission-control"],
  portfolioOffice: ["portfolio-office"],
  researchIdeas: ["research-ideas"],
  tradingQuantRisk: ["trading-quant-risk"],
  sectorIntelligence: ["sector-intelligence"],
  strategyArsenal: ["strategy-arsenal"],
  reports: ["reports"],
  office: ["office"],
  graphControl: ["graph-control"],
  zerodhaAuth: ["zerodha-auth"],
  zerodhaMarket: ["zerodha-market"],
} as const;

export function useSyncZerodhaAccount() {
  return useInvalidating<{ datasets: string[]; actor?: string }, LiveRow>(
    "/api/zerodha/sync",
    [Q.zerodhaAuth, Q.zerodhaMarket, Q.portfolioOffice, Q.tradingQuantRisk]
  );
}

export function useSyncZerodhaMarket() {
  return useInvalidating<{ modes: string[]; underlyings?: string[]; strike_pairs?: number; actor?: string }, LiveRow>(
    "/api/zerodha/market/sync",
    [Q.zerodhaMarket, Q.tradingQuantRisk, Q.office]
  );
}

/** Generic invalidating mutation factory. */
function useInvalidating<TBody, TResult = LiveRow>(
  path: string,
  invalidate: readonly (readonly string[])[]
) {
  const queryClient = useQueryClient();
  return useMutation<TResult, Error, TBody>({
    mutationFn: (body) => post<TResult>(path, body),
    onSuccess: () => {
      for (const key of invalidate) queryClient.invalidateQueries({ queryKey: key });
    },
  });
}

export function useRunOfficeOperabilityAcceptance() {
  return useInvalidating<{ run_key?: string; actor?: string }, LiveRow>(
    "/api/office/operability/acceptance/run",
    [Q.office]
  );
}

/* ============================================================
 * FUNDAMENTAL RESEARCH ACTIONS
 * ============================================================ */

export interface FundamentalCompanyIntakeInput {
  symbol?: string;
  actor?: string;
}

export function useSyncFundamentalCompanyIntake() {
  return useInvalidating<FundamentalCompanyIntakeInput, LiveRow>(
    "/api/research/fundamental-intake/sync",
    [Q.researchIdeas, Q.portfolioOffice, Q.office]
  );
}

export interface InstitutionalFundamentalFactoryInput {
  symbol: string;
  exchange: string;
  as_of: string;
  dry_run: boolean;
  actor?: string;
  run_key?: string;
}

export function useRunInstitutionalFundamentalFactory() {
  return useInvalidating<InstitutionalFundamentalFactoryInput, LiveRow>(
    "/api/research/fundamental-factory/run",
    [Q.researchIdeas, Q.portfolioOffice, Q.office, Q.reports]
  );
}

export interface SectorIntelligenceRunInput {
  index_id: number;
  as_of_date: string;
  horizon: "1D" | "1W" | "1M" | "3M" | "6M" | "1Y";
  dry_run: boolean;
  actor?: string;
}

export function useRunSectorIntelligence() {
  return useInvalidating<SectorIntelligenceRunInput, LiveRow>(
    "/api/sector-intelligence/run",
    [Q.sectorIntelligence, Q.office]
  );
}

export interface SectorIntelligenceImportInput {
  package: Record<string, unknown>;
  persist: boolean;
  actor?: string;
}

export function useImportSectorIntelligencePackage() {
  return useInvalidating<SectorIntelligenceImportInput, LiveRow>(
    "/api/sector-intelligence/import",
    [Q.sectorIntelligence, Q.office]
  );
}

export interface SectorAcceptanceInput {
  taxonomy_node_id: number;
  as_of_date: string;
  run_key?: string;
  actor?: string;
}

export function useRunSectorAcceptance() {
  return useInvalidating<SectorAcceptanceInput, LiveRow>(
    "/api/sector-intelligence/acceptance/run",
    [Q.sectorIntelligence, Q.office]
  );
}

export interface InstitutionalOptionsAnalyticsInput {
  underlying: string;
  exchange: "NFO" | "BFO";
  expiry_date: string;
  as_of: string;
  model: "black_scholes_merton" | "black_76";
  filters: {
    max_age_seconds: number;
    max_spread_bps: number;
    min_open_interest: number;
    min_volume: number;
  };
  dry_run: boolean;
  actor?: string;
}

export function useRunInstitutionalOptionsAnalytics() {
  return useInvalidating<InstitutionalOptionsAnalyticsInput, LiveRow>(
    "/api/options/institutional-analytics/run",
    [Q.tradingQuantRisk, Q.office]
  );
}

export interface OptionAcceptanceInput {
  exchange: "NFO" | "BFO";
  underlying: string;
  expiry_date: string;
  window_start: string;
  window_end: string;
  run_key?: string;
  actor?: string;
}

export function useRunOptionAcceptance() {
  return useInvalidating<OptionAcceptanceInput, LiveRow>(
    "/api/options/institutional-analytics/acceptance/run",
    [Q.tradingQuantRisk, Q.office]
  );
}

export interface InstitutionalOptionsMaterializeInput {
  limit: number;
  interval_seconds: number;
  actor?: string;
}

export function useMaterializeInstitutionalOptions() {
  return useInvalidating<InstitutionalOptionsMaterializeInput, LiveRow>(
    "/api/options/institutional-analytics/materialize",
    [Q.tradingQuantRisk, Q.office]
  );
}

export interface OptionValuationPolicyInput {
  policy_key: string;
  provider: string;
  exchange: "NFO" | "BFO";
  underlying: string;
  model_family: "black_scholes_merton" | "black_76";
  risk_free_rate: number;
  dividend_yield: number;
  rate_source: string;
  rate_source_timestamp: string;
  dividend_source: string;
  dividend_source_timestamp: string;
  source_artifact_ref: string;
  effective_from: string;
  expires_at: string;
  actor?: string;
}

export function useUpsertOptionValuationPolicy() {
  return useInvalidating<OptionValuationPolicyInput, LiveRow>(
    "/api/options/valuation-policy/upsert",
    [Q.tradingQuantRisk, Q.office]
  );
}

export interface LongTermMonteCarloInput {
  holding_thesis_id: number;
  actor?: string;
  horizon_years: number;
  simulations: number;
  seed?: number;
  starting_multiple?: number;
  starting_multiple_source?: string;
  terminal_multiple_low: number;
  terminal_multiple_base: number;
  terminal_multiple_high: number;
  annual_volatility: number;
}

export function useRunMonteCarlo() {
  return useInvalidating<LongTermMonteCarloInput>(
    "/api/portfolio/long-term-thesis/monte-carlo",
    [Q.researchIdeas, Q.portfolioOffice]
  );
}

export interface LongTermThesisMemoInput {
  holding_thesis_id?: number;
  symbol?: string;
  exchange?: string;
  actor?: string;
  force?: boolean;
}

export function useGenerateThesisMemo() {
  return useInvalidating<LongTermThesisMemoInput, LiveRow>(
    "/api/portfolio/long-term-thesis/memo",
    [Q.researchIdeas]
  );
}

export interface ResearchPacketInput {
  holding_thesis_id: number;
  actor?: string;
}

export function useGenerateResearchPacket() {
  return useInvalidating<ResearchPacketInput, LiveRow>(
    "/api/portfolio/long-term-thesis/research-packet",
    [Q.researchIdeas]
  );
}

export interface UpdateChecklistInput {
  holding_thesis_id: number;
  checklist_key: string;
  status?: string;
  score?: number;
  findings?: unknown[];
  evidence?: unknown[];
  actor?: string;
}

export function useUpdateChecklist() {
  return useInvalidating<UpdateChecklistInput, LiveRow>(
    "/api/portfolio/long-term-thesis/checklist",
    [Q.researchIdeas]
  );
}

export interface UpdateValuationInput {
  holding_thesis_id: number;
  model_key: string;
  status?: string;
  fair_value_low?: number;
  fair_value_base?: number;
  fair_value_high?: number;
  expected_cagr_pct?: number;
  assumptions?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  evidence?: unknown[];
  note_path?: string;
  actor?: string;
}

export function useUpdateValuation() {
  return useInvalidating<UpdateValuationInput, LiveRow>(
    "/api/portfolio/long-term-thesis/valuation",
    [Q.researchIdeas]
  );
}

export interface DispatchSpecialistsInput {
  holding_thesis_id: number;
  specialist_modules?: string[];
  actor?: string;
}

export function useDispatchSpecialists() {
  return useInvalidating<DispatchSpecialistsInput, LiveRow>(
    "/api/portfolio/long-term-specialists/dispatch",
    [Q.researchIdeas]
  );
}

export interface CommitteeReviewInput {
  holding_thesis_id: number;
  actor?: string;
}

export function useOpenLongTermCommittee() {
  return useInvalidating<CommitteeReviewInput, LiveRow>(
    "/api/portfolio/long-term-committee/open",
    [Q.researchIdeas, Q.office]
  );
}

export interface ResolveCommitteeInput {
  review_id: number;
  decision: string;
  notes?: string;
  actor?: string;
}

export function useResolveLongTermCommittee() {
  return useInvalidating<ResolveCommitteeInput, LiveRow>(
    "/api/portfolio/long-term-committee/decision",
    [Q.researchIdeas, Q.office]
  );
}

export function useResolveStrategyCommittee() {
  return useInvalidating<{ committee_review_id: number; decision: string; notes?: string; actor?: string }, LiveRow>(
    "/api/strategy/committee/decision",
    [Q.strategyArsenal, Q.tradingQuantRisk, Q.office]
  );
}

export function useResolveSpecialSituationDecision() {
  return useInvalidating<{ special_memo_id: number; decision: string; notes?: string; actor?: string }, LiveRow>(
    "/api/research/special-situations/decision",
    [Q.researchIdeas, Q.office]
  );
}

export interface WatchlistInput {
  symbol: string;
  exchange?: string;
  company_name?: string;
  item_type?: string;
  priority?: string;
  thesis?: string;
  catalyst?: string;
  invalidation?: string;
  review_on?: string;
  actor?: string;
}

export function useUpsertWatchlist() {
  return useInvalidating<WatchlistInput, LiveRow>(
    "/api/watchlist/items/upsert",
    [Q.researchIdeas, Q.missionControl]
  );
}

/* ============================================================
 * QUANT & STRATEGY ACTIONS
 * ============================================================ */

export interface StrategyIntakeInput {
  intake_text: string;
  strategy_name: string;
  strategy_family?: string;
  asset_class?: string;
  symbols?: string[];
  universe?: string;
  timeframe?: string;
  intent_tags?: string[];
  constraints_text?: string;
  risk_notes?: string;
  requested_outputs?: string[];
  source_kind?: string;
  source_ref?: string;
  actor?: string;
}

export function useCreateStrategyIntake() {
  return useInvalidating<StrategyIntakeInput, LiveRow>(
    "/api/strategy/intakes",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface BacktestInput {
  candidate_id: number;
  start_date?: string;
  end_date?: string;
  parameters?: Record<string, unknown>;
  actor?: string;
}

export function useRunBacktest() {
  return useInvalidating<BacktestInput, LiveRow>(
    "/api/strategy/backtests/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface OptimizationInput {
  candidate_id: number;
  parameter_space?: Record<string, unknown>;
  walk_forward?: boolean;
  actor?: string;
}

export function useRunOptimization() {
  return useInvalidating<OptimizationInput, LiveRow>(
    "/api/strategy/optimizations/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface UserOptimizerInput {
  strategy_name: string;
  intake_text: string;
  asset_class?: string;
  universe?: string;
  timeframe?: string;
  template?: string;
  symbols?: string[];
  dsl_text?: string;
  constraints_text?: string;
  risk_notes?: string;
  cost_bps?: number;
  slippage_bps?: number;
  max_symbols?: number;
  min_rows_per_symbol?: number;
  min_total_rows?: number;
  actor?: string;
}

export function useRunUserOptimizer() {
  return useInvalidating<UserOptimizerInput, LiveRow>(
    "/api/strategy/user-defined-optimizer/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface QuantAnalyticsInput {
  strategy_ids?: number[];
  timeframe?: string;
  limit?: number;
  max_symbols?: number;
  cost_bps?: number;
  slippage_bps?: number;
  participation_rate?: number;
  actor?: string;
}

export function useRunQuantAnalytics() {
  return useInvalidating<QuantAnalyticsInput, LiveRow>(
    "/api/strategy/quant-analytics/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface StrategyPortfolioAllocationInput {
  capital_base?: number;
  max_weight?: number;
  ruin_threshold_pct?: number;
  horizon_bars?: number;
  simulation_count?: number;
  analytics_run_key?: string;
  timeframe?: string;
  actor?: string;
}

export function useRunStrategyPortfolioAllocation() {
  return useInvalidating<StrategyPortfolioAllocationInput, LiveRow>(
    "/api/strategy/portfolio-allocation/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface StrategyRetirementInput {
  analytics_run_key?: string;
  allocation_key?: string;
  review_key_prefix?: string;
  actor?: string;
}

export function useRunStrategyRetirementReview() {
  return useInvalidating<StrategyRetirementInput, LiveRow>(
    "/api/strategy/retirement/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface DiscoveryInput {
  theme?: string;
  universe?: string;
  actor?: string;
}

export function useRunDiscovery() {
  return useInvalidating<DiscoveryInput, LiveRow>(
    "/api/strategy/discovery/run",
    [Q.strategyArsenal]
  );
}

export interface ResolveDiscoveryTriageInput {
  discovery_candidate_id: number;
  decision: "reject" | "request_more_evidence" | "route_quant_lab" | "route_special_situation" | "open_committee_review";
  notes: string;
  actor?: string;
}

export function useResolveDiscoveryTriage() {
  return useInvalidating<ResolveDiscoveryTriageInput, LiveRow>(
    "/api/strategy/discovery/triage/resolve",
    [Q.strategyArsenal, Q.tradingQuantRisk, Q.office]
  );
}

export interface JournalMiningInput {
  actor?: string;
  lookback_days?: number;
}

export function useRunJournalMining() {
  return useInvalidating<JournalMiningInput, LiveRow>(
    "/api/strategy/trade-journal-mining/run",
    [Q.strategyArsenal, Q.tradingQuantRisk]
  );
}

export interface ModelValidationInput {
  backtest_id: number;
  actor?: string;
}

export function useRunModelValidation() {
  return useInvalidating<ModelValidationInput, LiveRow>(
    "/api/strategy/model-validation/sweep",
    [Q.tradingQuantRisk, Q.strategyArsenal]
  );
}

export interface PaperMonitorInput {
  committee_review_id: number;
  actor?: string;
}

export function useStartPaperMonitor() {
  return useInvalidating<PaperMonitorInput, LiveRow>(
    "/api/strategy/paper-monitor/start",
    [Q.tradingQuantRisk]
  );
}

export function useRunBrokerReconciliation() {
  return useInvalidating<{ actor?: string }, LiveRow>(
    "/api/broker-reconciliation/run",
    [Q.portfolioOffice, Q.missionControl]
  );
}

export function useRunP2CursorReconciliation() {
  return useInvalidating<{ actor?: string; client_code?: string }, LiveRow>(
    "/api/p2cursor-reconciliation/run",
    [Q.portfolioOffice, Q.missionControl]
  );
}

/* ============================================================
 * TRADING ACTIONS (manual + paper — NOT live execution)
 * ============================================================ */

export interface ManualTradeInput {
  symbol: string;
  exchange?: string;
  instrument_type?: "equity" | "future" | "option" | string;
  option_type?: "CE" | "PE";
  strike?: number;
  expiry_date?: string;
  strategy_name?: string;
  setup_type?: string;
  tags?: string[];
  side: "buy" | "sell";
  quantity: number;
  quantity_unit?: "units" | "lots";
  lot_count?: number;
  lot_size?: number;
  contract_quantity?: number;
  price: number;
  trade_date?: string;
  book_key?: string;
  purpose?: string;
  thesis?: string;
  notes?: string;
  actor?: string;
}

export function useRecordManualTrade() {
  return useInvalidating<ManualTradeInput, LiveRow>(
    "/api/trades/manual",
    [Q.portfolioOffice, Q.tradingQuantRisk]
  );
}

export interface PaperTradeInput extends ManualTradeInput {
  strategy_id?: number;
}

export function useRecordPaperTrade() {
  return useInvalidating<PaperTradeInput, LiveRow>(
    "/api/trades/paper",
    [Q.tradingQuantRisk]
  );
}


export interface TradingViewDesktopInput {
  symbol: string;
  exchange?: string;
  timeframe?: string;
  target_url?: string;
  actor?: string;
}

export function useOpenTradingViewDesktop() {
  return useInvalidating<TradingViewDesktopInput, LiveRow>(
    "/api/tradingview/desktop/open",
    [Q.tradingQuantRisk]
  );
}

export interface TradingViewTemplateInput extends TradingViewDesktopInput {
  template_key: string;
  parameters?: Record<string, unknown>;
}

export function useRunTradingViewTemplate() {
  return useInvalidating<TradingViewTemplateInput, LiveRow>(
    "/api/tradingview/template-actions",
    [Q.tradingQuantRisk, Q.office]
  );
}

/* ============================================================
 * PORTFOLIO ACTIONS
 * ============================================================ */

export interface ClientOnboardingInput {
  client_code: string;
  display_name: string;
  risk_profile: string;
  objectives: string[];
  constraints?: string[];
  investment_horizon: string;
  liquidity_needs?: string;
  risk_tolerance: string;
  risk_capacity: string;
  suitability_status: "needs_review" | "suitable" | "conditionally_suitable" | "unsuitable";
  suitability_notes?: string;
  source_evidence: Array<string | Record<string, unknown>>;
  account?: {
    account_code: string;
    account_name?: string;
    account_type?: string;
    broker?: string;
    base_currency?: string;
    external_account_ref?: string;
  };
  actor?: string;
}

export function useStageClientOnboarding() {
  return useInvalidating<ClientOnboardingInput, LiveRow>(
    "/api/client-office/onboarding/stage",
    [Q.portfolioOffice, Q.office, Q.missionControl]
  );
}

export interface HoldingUpdateInput {
  client_code: string;
  account_code: string;
  symbol: string;
  exchange?: string;
  quantity?: number;
  average_price?: number;
  market_price?: number;
  market_value?: number;
  instrument_type?: string;
  as_of?: string;
  update_reason: string;
  payload?: Record<string, unknown>;
  actor?: string;
}

export function useStageHoldingUpdate() {
  return useInvalidating<HoldingUpdateInput, LiveRow>(
    "/api/portfolio/holding-updates/stage",
    [Q.portfolioOffice, Q.office]
  );
}

export function useRefreshPortfolioRisk() {
  return useInvalidating<{ actor?: string }, LiveRow>(
    "/api/risk/portfolio/refresh-events",
    [Q.tradingQuantRisk, Q.portfolioOffice, Q.office]
  );
}

export function useRunInstitutionalRisk() {
  return useInvalidating<{ actor?: string; as_of?: string }, LiveRow>(
    "/api/risk/institutional/run",
    [Q.tradingQuantRisk, Q.portfolioOffice]
  );
}

/* ============================================================
 * RESEARCH / FILINGS / NEWS
 * ============================================================ */

export interface FilingCollectorInput {
  symbols?: string[];
  exchange?: string;
  actor?: string;
}

export function useRunFilingCollector() {
  return useInvalidating<FilingCollectorInput, LiveRow>(
    "/api/research/filings/collect",
    [Q.researchIdeas]
  );
}

export interface NewsIngestInput {
  source_key?: string;
  actor?: string;
}

export function useIngestMarketNews() {
  return useInvalidating<NewsIngestInput, LiveRow>(
    "/api/market/news/ingest",
    [Q.researchIdeas, Q.missionControl]
  );
}

export interface PaperIngestInput {
  title: string;
  source_key: string;
  source_url?: string;
  pdf_url?: string;
  local_path?: string;
  topics?: string[];
  actor?: string;
}

export function useIngestResearchPaper() {
  return useInvalidating<PaperIngestInput, LiveRow>(
    "/api/research/papers/ingest",
    [Q.researchIdeas]
  );
}

export interface ResearchSourceIngestInput {
  title?: string;
  source_url?: string;
  pasted_text?: string;
  source_key?: "web" | "blog" | "github" | "manual";
  source_kind?: string;
  research_objective: string;
  hypothesis?: string;
  hypothesis_title?: string;
  target_universe?: string;
  timeframe?: string;
  topics?: string[];
  asset_classes?: string[];
  desired_outputs?: string[];
  priority?: "low" | "medium" | "high" | "critical";
  actor?: string;
}

export function useIngestResearchSource() {
  return useInvalidating<ResearchSourceIngestInput, LiveRow>(
    "/api/research/sources/ingest",
    [Q.researchIdeas, Q.strategyArsenal, Q.office, Q.missionControl]
  );
}

/* ============================================================
 * SPECIAL SITUATIONS
 * ============================================================ */

export interface SpecialMemoInput {
  symbol: string;
  situation_type?: string;
  actor?: string;
}

export function useGenerateSpecialMemo() {
  return useInvalidating<SpecialMemoInput, LiveRow>(
    "/api/research/special-situations/memo",
    [Q.researchIdeas]
  );
}

/* ============================================================
 * MACRO
 * ============================================================ */

export function useIngestMacroData() {
  return useInvalidating<{ actor?: string; source_key?: string }, LiveRow>(
    "/api/market/news/ingest",
    [Q.researchIdeas]
  );
}

export function useCheckSourceFreshness() {
  return useInvalidating<{ actor?: string; source_keys?: string[] }, LiveRow>(
    "/api/data-sources/freshness/check",
    [Q.missionControl, Q.researchIdeas]
  );
}

/* ============================================================
 * COMMITTEES
 * ============================================================ */

export interface CommitteePacketInput {
  committee_key: string;
  subject: string;
  context?: Record<string, unknown>;
  actor?: string;
}

export function useOpenCommitteePacket() {
  return useInvalidating<CommitteePacketInput, LiveRow>(
    "/api/committees/packets/open",
    [Q.office, Q.researchIdeas]
  );
}

export function useSynthesizeCommittee() {
  return useInvalidating<{ session_id: number; actor?: string }, LiveRow>(
    "/api/committees/synthesize",
    [Q.office, Q.researchIdeas]
  );
}

export function useRecordCommitteeDecision() {
  return useInvalidating<{ session_id: number; decision: string; notes?: string; actor?: string }, LiveRow>(
    "/api/committees/human-decision",
    [Q.office, Q.researchIdeas]
  );
}

/* ============================================================
 * GOVERNANCE — architecture change requests (the stack control surface)
 *
 * These let Charlie (or you) propose changes to the system itself — new
 * agents, new screens, new model routes, new integrations. Every change
 * is gated through the architecture-change-request ledger so nothing
 * mutates the stack without a recorded decision.
 * ============================================================ */

export interface ArchitectureChangeInput {
  title: string;
  change_type: "new_agent" | "new_screen" | "new_model_route" | "new_integration" | "new_workflow" | "config_change" | "screen_reorg" | "other";
  description: string;
  rationale?: string;
  risk_level?: "low" | "medium" | "high";
  proposed_by?: string;
  metadata?: Record<string, unknown>;
}

export function useProposeArchitectureChange() {
  return useInvalidating<ArchitectureChangeInput, LiveRow>(
    "/api/governance/architecture-changes/request",
    [Q.missionControl, Q.office]
  );
}

export function useSyncArchitectureChange() {
  return useInvalidating<{ change_id: number; status?: string; notes?: string; actor?: string }, LiveRow>(
    "/api/governance/architecture-changes/sync",
    [Q.missionControl, Q.office]
  );
}

/* ============================================================
 * WORKSPACE + WIDGET CONFIG — let you (or Charlie) reorganize screens
 *
 * The terminal functions registry is a static default; these endpoints
 * persist per-profile overrides — custom screens, widget arrangements,
 * column counts, hidden modules. Talking to Charlie about "add a screen
 * for X" or "move risk to the top" routes through here.
 * ============================================================ */

export interface WorkspaceConfigUpdate {
  profile_key?: string;
  default_workspace?: string;
  theme?: string;
  density?: string;
  navigation?: Record<string, unknown>;
  preferences?: Record<string, unknown>;
}

export function useUpdateWorkspaceConfig() {
  return useInvalidating<WorkspaceConfigUpdate, LiveRow>(
    "/api/workspaces/config/update",
    [Q.missionControl]
  );
}

export interface WidgetUpdateInput {
  widget_key?: string;
  workspace_key?: string;
  module_key?: string;
  title?: string;
  visible?: boolean;
  order?: number;
  size?: "sm" | "md" | "lg" | "xl";
  settings?: Record<string, unknown>;
}

export function useUpdateDashboardWidget() {
  return useInvalidating<WidgetUpdateInput, LiveRow>(
    "/api/dashboard/widgets/update",
    [Q.missionControl, Q.office]
  );
}

export function useMaterializeWidgets() {
  return useInvalidating<{ actor?: string; include_existing?: boolean; limit?: number }, LiveRow>(
    "/api/dashboard/widgets/materialize",
    [Q.missionControl, Q.office]
  );
}

/* ============================================================
 * AGENT MESSAGE / TASK / DELEGATION — let Charlie dispatch work
 * ============================================================ */

export interface CreateAgentMessageInput {
  to_agent: string;
  message: string;
  subject?: string;
  priority?: "low" | "medium" | "high" | "critical";
  workspace?: string;
  metadata?: Record<string, unknown>;
}

export function useCreateAgentMessage() {
  return useInvalidating<CreateAgentMessageInput, LiveRow>(
    "/api/agents/messages",
    [Q.office, Q.missionControl]
  );
}

export function useDelegateAgentTask() {
  return useInvalidating<{
    to_agent: string;
    objective: string;
    subject?: string;
    priority?: "low" | "medium" | "high" | "critical";
    workspace?: string;
    actor?: string;
  }, LiveRow>(
    "/api/agents/delegate",
    [Q.office, Q.missionControl]
  );
}

export function useRunAgentWorker() {
  return useInvalidating<{ actor?: string; limit?: number; agent_key?: string }, LiveRow>(
    "/api/agents/worker/run",
    [Q.office, Q.missionControl]
  );
}

export function useMaterializeAgentSchedules() {
  return useInvalidating<{ actor?: string; limit?: number }, LiveRow>(
    "/api/agents/schedules/run",
    [Q.office, Q.missionControl]
  );
}

/* ============================================================
 * GRAPH CONTROL PLANE
 * ============================================================ */

export interface StartGraphRunInput {
  graph_key: string;
  input_payload: Record<string, unknown>;
  actor?: string;
  trigger_type?: string;
  subject_type?: string;
  subject_ref?: string;
  correlation_key?: string;
  idempotency_key?: string;
  max_steps?: number;
}

const GRAPH_INVALIDATIONS = [Q.graphControl, Q.office, Q.missionControl] as const;

export function useStartGraphRun() {
  return useInvalidating<StartGraphRunInput, LiveRow>(
    "/api/graphs/runs/start",
    GRAPH_INVALIDATIONS
  );
}

export function useAdvanceGraphRun() {
  return useInvalidating<{ graph_run_id: number; actor?: string; max_steps?: number }, LiveRow>(
    "/api/graphs/runs/advance",
    GRAPH_INVALIDATIONS
  );
}

export function useAdvanceActiveGraphRuns() {
  return useInvalidating<{ actor?: string; limit?: number; max_steps?: number }, LiveRow>(
    "/api/graphs/runs/advance-active",
    GRAPH_INVALIDATIONS
  );
}

export function usePauseGraphRun() {
  return useInvalidating<{ graph_run_id: number; actor?: string; reason: string }, LiveRow>(
    "/api/graphs/runs/pause",
    GRAPH_INVALIDATIONS
  );
}

export function useResumeGraphRun() {
  return useInvalidating<{ graph_run_id: number; actor?: string }, LiveRow>(
    "/api/graphs/runs/resume",
    GRAPH_INVALIDATIONS
  );
}

export function useCancelGraphRun() {
  return useInvalidating<{ graph_run_id: number; actor?: string; reason: string }, LiveRow>(
    "/api/graphs/runs/cancel",
    GRAPH_INVALIDATIONS
  );
}

export function useResolveGraphWait() {
  return useInvalidating<{ wait_id: number; actor?: string; resolution: Record<string, unknown> }, LiveRow>(
    "/api/graphs/waits/resolve",
    GRAPH_INVALIDATIONS
  );
}

export function useResolveGraphDecision() {
  return useInvalidating<{ approval_id: number; decision: string; rationale: string; actor?: string }, LiveRow>(
    "/api/graphs/decisions",
    GRAPH_INVALIDATIONS
  );
}

export function useRequestGraphChange() {
  return useInvalidating<{
    graph_key: string;
    title: string;
    rationale: string;
    proposed_patch: Record<string, unknown>;
    safety_impact: Record<string, unknown>;
    actor?: string;
  }, LiveRow>("/api/graphs/change-requests", GRAPH_INVALIDATIONS);
}

export function useRecordGraphCorrection() {
  return useInvalidating<{
    source_kind?: string;
    source_ref?: string;
    graph_run_id?: number;
    graph_node_run_id?: number;
    correction_type?: string;
    severity: "low" | "medium" | "high" | "critical";
    expected_state?: Record<string, unknown>;
    observed_state?: Record<string, unknown>;
    root_cause?: string;
    corrective_action: string;
    prevention_change?: Record<string, unknown>;
    owner_agent?: string;
    actor?: string;
  }, LiveRow>("/api/graphs/corrections", GRAPH_INVALIDATIONS);
}
