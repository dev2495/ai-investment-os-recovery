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
  strategyArsenal: ["strategy-arsenal"],
  reports: ["reports"],
  office: ["office"],
} as const;

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

/* ============================================================
 * FUNDAMENTAL RESEARCH ACTIONS
 * ============================================================ */

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
  holding_thesis_id: number;
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
  checklist_id: number;
  status?: string;
  notes?: string;
  actor?: string;
}

export function useUpdateChecklist() {
  return useInvalidating<UpdateChecklistInput, LiveRow>(
    "/api/portfolio/long-term-thesis/checklist",
    [Q.researchIdeas]
  );
}

export interface UpdateValuationInput {
  valuation_model_id: number;
  model_type?: string;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  notes?: string;
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
  intake_id: number;
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
  intake_id: number;
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
  intake_id: number;
  parameters?: Record<string, unknown>;
  data_source?: string;
  actor?: string;
}

export function useRunUserOptimizer() {
  return useInvalidating<UserOptimizerInput, LiveRow>(
    "/api/strategy/user-defined-optimizer/run",
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
  strategy_id: number;
  actor?: string;
}

export function useStartPaperMonitor() {
  return useInvalidating<PaperMonitorInput, LiveRow>(
    "/api/strategy/paper-monitor/start",
    [Q.tradingQuantRisk]
  );
}

/* ============================================================
 * TRADING ACTIONS (manual + paper — NOT live execution)
 * ============================================================ */

export interface ManualTradeInput {
  symbol: string;
  exchange?: string;
  side: "buy" | "sell";
  quantity: number;
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

/* ============================================================
 * PORTFOLIO ACTIONS
 * ============================================================ */

export interface HoldingUpdateInput {
  client_id?: number;
  symbol: string;
  exchange?: string;
  quantity?: number;
  average_cost?: number;
  book_key?: string;
  purpose?: string;
  thesis_id?: number;
  horizon?: string;
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
