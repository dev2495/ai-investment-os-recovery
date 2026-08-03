/**
 * AI Investment OS — Zod Schemas
 *
 * Validates the STRUCTURE of each snapshot payload: which arrays exist,
 * metadata fields (generated_at, data_mode, etc.). Per-row data stays as
 * LiveRow because the warehouse schema is large and evolves independently —
 * strict per-row validation would break on every backend column addition.
 *
 * What this buys us:
 *   - Compile-time types for every snapshot (autocompletion, refactor safety)
 *   - Runtime validation that the API returned the expected shape (not an
 *     error object or a truncated payload)
 *   - A clean failure mode if the backend changes a snapshot's array names
 */

import { z } from "zod";
import type { LiveRow } from "./liveRow";

/** A row of unknown shape — the warehouse payload. */
const liveRow = z.record(z.unknown()) as z.ZodType<LiveRow>;

/** Reusable metadata block present on every snapshot. */
const snapshotMeta = {
  generated_at: z.string(),
  runtime_root: z.string().optional().default(""),
  vault_root: z.string().optional().default(""),
};

const dataMode = z.object({
  seed_data_allowed: z.boolean().optional().default(false),
  source: z.string().optional().default(""),
}).passthrough();

const payloadProfile = z.object({
  query_count: z.number().optional().default(0),
  row_count: z.number().optional().default(0),
}).passthrough();

const tradingViewDesktop = z.object({
  installed: z.boolean().optional().default(false),
  running: z.boolean().optional().default(false),
  version: z.string().nullable().optional(),
  bundle_id: z.string().optional(),
  automation_permission: z.boolean().optional().default(false),
  session_state: z.string().optional().default("user_managed"),
  interaction_mode: z.string().optional().default("unavailable"),
  authoritative_market_data: z.boolean().optional().default(false),
  broker_execution_allowed: z.boolean().optional().default(false),
  errors: z.array(z.string()).optional().default([]),
  next_action: z.string().optional(),
}).passthrough();

const executionControlRow = liveRow;

/* ============================================================
 * Mission Control
 * ============================================================ */
export const MissionControlSchema = z.object({
  ...snapshotMeta,
  tradingview_desktop: tradingViewDesktop.optional(),
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  metrics: z.array(liveRow).default([]),
  inbox: z.array(liveRow).default([]),
  approvals: z.array(liveRow).default([]),
  approval_summary: z.array(liveRow).default([]),
  agent_messages: z.array(liveRow).default([]),
  tasks: z.array(liveRow).default([]),
  chat_turns: z.array(liveRow).default([]),
  widget_intents: z.array(liveRow).default([]),
  dashboard_widgets: z.array(liveRow).default([]),
  agent_worker_queue: z.array(liveRow).default([]),
  agent_worker_runs: z.array(liveRow).default([]),
  task_provider_gates: z.array(liveRow).default([]),
  source_freshness: z.array(liveRow).default([]),
  filing_summary: z.array(liveRow).default([]),
  latest_filings: z.array(liveRow).default([]),
  latest_news: z.array(liveRow).default([]),
  news_brief: z.array(liveRow).default([]),
  filing_intelligence: z.array(liveRow).default([]),
  market_events: z.array(liveRow).default([]),
  market_quotes: z.array(liveRow).default([]),
  market_holidays: z.array(liveRow).default([]),
  watchlist: z.array(liveRow).default([]),
  latest_reports: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
}).passthrough();

export type MissionControl = z.infer<typeof MissionControlSchema>;

/* ============================================================
 * System Health
 * ============================================================ */
export const SystemHealthSchema = z.object({
  ...snapshotMeta,
  tradingview_desktop: tradingViewDesktop.optional(),
  storage: z.object({
    vault_mounted: z.boolean().optional().default(false),
    ollama_models_external: z.boolean().optional().default(false),
    docker_raw_external: z.boolean().optional().default(false),
    heavy_state_external: z.boolean().optional().default(false),
  }).passthrough().optional(),
  recovery: z.object({
    backup_root: z.string().optional().default(""),
    current_exists: z.boolean().optional().default(false),
    previous_exists: z.boolean().optional().default(false),
    created_at: z.string().optional(),
    format_version: z.string().optional(),
    repo_commit: z.string().optional(),
    postgres_dump_exists: z.boolean().optional().default(false),
    postgres_dump_bytes: z.number().optional().default(0),
    qdrant_snapshot_exists: z.boolean().optional().default(false),
    qdrant_snapshot_bytes: z.number().optional().default(0),
    qdrant_snapshot_name: z.string().optional(),
    vault_copy_exists: z.boolean().optional().default(false),
    vault_file_count: z.number().optional().default(0),
    checksums_exist: z.boolean().optional().default(false),
    latest_restore_drill: z.record(z.unknown()).optional(),
    backup_schedule_installed: z.boolean().optional().default(false),
    report_schedule_installed: z.boolean().optional().default(false),
    vault_bookmark_exists: z.boolean().optional().default(false),
  }).passthrough().optional(),
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  metrics: z.array(liveRow).default([]),
  blueprint_summary: z.array(liveRow).default([]),
  blueprint_domains: z.array(liveRow).default([]),
  blueprint_sync_runs: z.array(liveRow).default([]),
  data_sources: z.array(liveRow).default([]),
  data_source_checks: z.array(liveRow).default([]),
  source_freshness: z.array(liveRow).default([]),
  source_freshness_scheduler_runs: z.array(liveRow).default([]),
  runtime_daemons: z.array(liveRow).default([]),
  model_routes: z.array(liveRow).default([]),
  model_endpoints: z.array(liveRow).default([]),
  provider_readiness_summary: z.array(liveRow).default([]),
  provider_readiness_board: z.array(liveRow).default([]),
  connector_health_checks: z.array(liveRow).default([]),
  browser_session_checks: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
  report_scheduler_health: z.array(liveRow).default([]),
  pipeline_readiness: z.array(liveRow).default([]),
}).passthrough();

export type SystemHealth = z.infer<typeof SystemHealthSchema>;

/* ============================================================
 * Portfolio Office
 * ============================================================ */
export const PortfolioOfficeSchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  clients: z.array(liveRow).default([]),
  client_accounts: z.array(liveRow).default([]),
  latest_positions: z.array(liveRow).default([]),
  investment_books: z.array(liveRow).default([]),
  book_positions: z.array(liveRow).default([]),
  symbol_book_exposure: z.array(liveRow).default([]),
  client_book_exposure: z.array(liveRow).default([]),
  cross_book_conflicts: z.array(liveRow).default([]),
  coordination_questions: z.array(liveRow).default([]),
  position_gap_summary: z.array(liveRow).default([]),
  remediation_summary: z.array(liveRow).default([]),
  portfolio_intelligence: z.array(liveRow).default([]),
  manual_updates: z.array(liveRow).default([]),
  client_onboarding: z.array(liveRow).default([]),
  client_suitability: z.array(liveRow).default([]),
  account_changes: z.array(liveRow).default([]),
  holding_reconciliation: z.array(liveRow).default([]),
  cash_ledger: z.array(liveRow).default([]),
  tax_lot_summary: z.array(liveRow).default([]),
  client_nav: z.array(liveRow).default([]),
  client_performance: z.array(liveRow).default([]),
  performance_attribution: z.array(liveRow).default([]),
  client_report_delivery: z.array(liveRow).default([]),
  p2cursor_reconciliation: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
}).passthrough();

export type PortfolioOffice = z.infer<typeof PortfolioOfficeSchema>;

/* ============================================================
 * Research & Ideas
 * ============================================================ */
export const ResearchIdeasSchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  research_hub: z.array(liveRow).default([]),
  long_term_theses: z.array(liveRow).default([]),
  coverage_summary: z.array(liveRow).default([]),
  coverage_queue: z.array(liveRow).default([]),
  long_term_checklists: z.array(liveRow).default([]),
  long_term_valuation_models: z.array(liveRow).default([]),
  long_term_monte_carlo_runs: z.array(liveRow).default([]),
  long_term_research_updates: z.array(liveRow).default([]),
  committee_queue: z.array(liveRow).default([]),
  latest_news: z.array(liveRow).default([]),
  news_brief: z.array(liveRow).default([]),
  filing_intelligence: z.array(liveRow).default([]),
  market_events: z.array(liveRow).default([]),
  market_quotes: z.array(liveRow).default([]),
  market_holidays: z.array(liveRow).default([]),
  feed_registry: z.array(liveRow).default([]),
  news_ingestion_runs: z.array(liveRow).default([]),
  filing_collector_runs: z.array(liveRow).default([]),
  filing_pdf_extraction_runs: z.array(liveRow).default([]),
  news_source_checks: z.array(liveRow).default([]),
  corporate_filings: z.array(liveRow).default([]),
  special_situations: z.array(liveRow).default([]),
  special_memos: z.array(liveRow).default([]),
  special_spreads: z.array(liveRow).default([]),
  generated_ideas: z.array(liveRow).default([]),
  research_papers: z.array(liveRow).default([]),
  paper_strategy_hypotheses: z.array(liveRow).default([]),
  research_cycles: z.array(liveRow).default([]),
  discovery_candidates: z.array(liveRow).default([]),
  idea_dossiers: z.array(liveRow).default([]),
  output_artifacts: z.array(liveRow).default([]),
  watchlist: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
}).passthrough();

export type ResearchIdeas = z.infer<typeof ResearchIdeasSchema>;

/* ============================================================
 * Trading, Quant, Risk
 * ============================================================ */
export const TradingQuantRiskSchema = z.object({
  ...snapshotMeta,
  tradingview_desktop: tradingViewDesktop.optional(),
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  quant_lab: z.array(liveRow).default([]),
  model_validation: z.array(liveRow).default([]),
  promotion_board: z.array(liveRow).default([]),
  strategy_committee: z.array(liveRow).default([]),
  paper_monitors: z.array(liveRow).default([]),
  drift_checks: z.array(liveRow).default([]),
  retirement_queue: z.array(liveRow).default([]),
  signals: z.array(liveRow).default([]),
  alerts: z.array(liveRow).default([]),
  tradingview_tasks: z.array(liveRow).default([]),
  tradingview_templates: z.array(liveRow).default([]),
  tradingview_template_approvals: z.array(liveRow).default([]),
  trade_activity: z.array(liveRow).default([]),
  paper_trade_summary: z.array(liveRow).default([]),
  paper_positions: z.array(liveRow).default([]),
  paper_monitor_performance: z.array(liveRow).default([]),
  risk_summary: z.array(liveRow).default([]),
  risk_limits: z.array(liveRow).default([]),
  institutional_risk_run: z.array(liveRow).default([]),
  institutional_risk_metrics: z.array(liveRow).default([]),
  institutional_stress: z.array(liveRow).default([]),
  institutional_liquidity: z.array(liveRow).default([]),
  institutional_factors: z.array(liveRow).default([]),
  institutional_risk_summary: z.array(liveRow).default([]),
  limited_live_requests: z.array(liveRow).default([]),
  order_intents: z.array(liveRow).default([]),
  options_surface: z.array(liveRow).default([]),
  option_chain: z.array(liveRow).default([]),
  option_oi_change: z.array(liveRow).default([]),
  option_trade_log: z.array(liveRow).default([]),
  broker_snapshots: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
}).passthrough();

export type TradingQuantRisk = z.infer<typeof TradingQuantRiskSchema>;

/* ============================================================
 * Strategy Arsenal
 * ============================================================ */
export const StrategyArsenalSchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  summary: z.array(liveRow).default([]),
  discovery_governance: z.array(liveRow).default([]),
  control_board: z.array(liveRow).default([]),
  intakes: z.array(liveRow).default([]),
  discovery_triage: z.array(liveRow).default([]),
  templates: z.array(liveRow).default([]),
  discovery_runs: z.array(liveRow).default([]),
  user_optimizer_runs: z.array(liveRow).default([]),
  quant_analytics_runs: z.array(liveRow).default([]),
  strategy_regime_performance: z.array(liveRow).default([]),
  strategy_factor_attribution: z.array(liveRow).default([]),
  strategy_capacity_liquidity: z.array(liveRow).default([]),
  strategy_correlation_matrix: z.array(liveRow).default([]),
  strategy_portfolio_optimizer_runs: z.array(liveRow).default([]),
  strategy_portfolio_allocation_runs: z.array(liveRow).default([]),
  strategy_portfolio_allocations: z.array(liveRow).default([]),
  strategy_retirement_queue: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
}).passthrough();

export type StrategyArsenal = z.infer<typeof StrategyArsenalSchema>;

/* ============================================================
 * Reports
 * ============================================================ */
export const ReportsSchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  artifact_summary: z.array(liveRow).default([]),
  artifacts: z.array(liveRow).default([]),
  artifact_gaps: z.array(liveRow).default([]),
  worker_runs: z.array(liveRow).default([]),
  research_hub: z.array(liveRow).default([]),
  raw_artifacts: z.array(liveRow).default([]),
  lineage_summary: z.array(liveRow).default([]),
  artifact_lineage: z.array(liveRow).default([]),
  import_coverage: z.array(liveRow).default([]),
  report_schedules: z.array(liveRow).default([]),
  report_runs: z.array(liveRow).default([]),
  report_scheduler_health: z.array(liveRow).default([]),
  report_scheduler_invocations: z.array(liveRow).default([]),
  chat_turns: z.array(liveRow).default([]),
  blueprint_summary: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
  local_artifact_summary: z.array(liveRow).default([]),
  local_artifact_ingestions: z.array(liveRow).default([]),
}).passthrough();

export type Reports = z.infer<typeof ReportsSchema>;

/* ============================================================
 * Integration Gateway
 * ============================================================ */
export const IntegrationGatewaySchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  summary: z.array(liveRow).default([]),
  plugins: z.array(liveRow).default([]),
  schema_mappings: z.array(liveRow).default([]),
  jobs: z.array(liveRow).default([]),
  model_routes: z.array(liveRow).default([]),
  model_runtime_summary: z.array(liveRow).default([]),
  model_route_control: z.array(liveRow).default([]),
  model_privacy_policies: z.array(liveRow).default([]),
  model_agent_assignments: z.array(liveRow).default([]),
  model_call_decisions: z.array(liveRow).default([]),
  model_escalations: z.array(liveRow).default([]),
  provider_readiness: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
  market_data_readiness: z.array(liveRow).default([]),
  market_data_contracts: z.array(liveRow).default([]),
  market_data_imports: z.array(liveRow).default([]),
  market_data_quality: z.array(liveRow).default([]),
  market_bias_readiness: z.array(liveRow).default([]),
}).passthrough();

export type IntegrationGateway = z.infer<typeof IntegrationGatewaySchema>;

/* ============================================================
 * Department Terminal
 * ============================================================ */
export const DepartmentTerminalSchema = z.object({
  generated_at: z.string(),
  workspace: z.string(),
  data_mode: dataMode.optional(),
  payload_profile: payloadProfile.optional(),
  execution_control: z.array(executionControlRow).default([]),
  widgets: z.array(liveRow).default([]),
  summary: z.array(liveRow).default([]),
  primary: z.array(liveRow).default([]),
  secondary: z.array(liveRow).optional().default([]),
  tertiary: z.array(liveRow).optional().default([]),
  departments: z.array(liveRow).optional().default([]),
  schedules: z.array(liveRow).optional().default([]),
  committees: z.array(liveRow).optional().default([]),
  worker_history: z.array(liveRow).optional().default([]),
  cost_quality: z.array(liveRow).optional().default([]),
  followups: z.array(liveRow).optional().default([]),
  constitutions: z.array(liveRow).optional().default([]),
  discussion: z.array(liveRow).optional().default([]),
}).passthrough();

export type DepartmentTerminal = z.infer<typeof DepartmentTerminalSchema>;

/* ============================================================
 * Graph Control Plane
 * ============================================================ */
export const GraphControlSnapshotSchema = z.object({
  ...snapshotMeta,
  data_mode: dataMode.optional(),
  graphs: z.array(liveRow).default([]),
  nodes: z.array(liveRow).default([]),
  edges: z.array(liveRow).default([]),
  runs: z.array(liveRow).default([]),
  node_runs: z.array(liveRow).default([]),
  edge_runs: z.array(liveRow).default([]),
  checkpoints: z.array(liveRow).default([]),
  events: z.array(liveRow).default([]),
  autonomy: z.array(liveRow).default([]),
  autonomy_evidence: z.array(liveRow).default([]),
  attention: z.array(liveRow).default([]),
  change_requests: z.array(liveRow).default([]),
  corrections: z.array(liveRow).default([]),
  waiting: z.array(liveRow).default([]),
  kronos_runs: z.array(liveRow).default([]),
  kronos_adapter: z.array(liveRow).default([]),
  issues: z.array(liveRow).default([]),
}).passthrough();

export type GraphControlSnapshot = z.infer<typeof GraphControlSnapshotSchema>;

/* ============================================================
 * Live Office (the 3D office data source)
 * ============================================================ */
export const OfficeSnapshotSchema = z.object({
  generated_at: z.string(),
  agents: z.array(liveRow).default([]),
  agent_messages: z.array(liveRow).default([]),
  committee_room_items: z.array(liveRow).default([]),
  issues: z.array(liveRow).default([]),
  live_office_agent_activity: z.array(liveRow).default([]),
  live_office_rooms: z.array(liveRow).default([]),
  priority_tasks: z.array(liveRow).default([]),
  risk_events: z.array(liveRow).default([]),
  source_freshness: z.array(liveRow).default([]),
  execution_control: z.array(executionControlRow).default([]),
  long_term_committee_queue: z.array(liveRow).optional().default([]),
  strategy_committee_queue: z.array(liveRow).optional().default([]),
  graph_runs: z.array(liveRow).optional().default([]),
  graph_node_runs: z.array(liveRow).optional().default([]),
  graph_attention: z.array(liveRow).optional().default([]),
}).passthrough();

export type OfficeSnapshot = z.infer<typeof OfficeSnapshotSchema>;

/* ============================================================
 * Evidence
 * ============================================================ */
export const EntityEvidenceSchema = z.object({
  entity_kind: z.string(),
  entity_key: z.string(),
  generated_at: z.string(),
  record: liveRow,
  groups: z.array(z.object({
    key: z.string(),
    label: z.string(),
    records: z.array(liveRow).default([]),
  })).default([]),
}).passthrough();

export type EntityEvidence = z.infer<typeof EntityEvidenceSchema>;

/* ============================================================
 * Chat (Charlie)
 * ============================================================ */
export const ChatResponseSchema = z.object({
  chat_turn: liveRow,
  message: z.string().default(""),
  assistant_identity: liveRow.optional().default({} as LiveRow),
  conversation_mode: z.string().optional().default("orchestrator"),
  route: liveRow.optional().default({} as LiveRow),
  model_status: z.string().default(""),
  retrieval_status: z.string().default(""),
  retrieval_hits: z.array(liveRow).default([]),
  widget_intents: z.array(liveRow).default([]),
  materialization: liveRow.optional().default({} as LiveRow),
  dashboard_widgets: z.array(liveRow).default([]),
  agent_jobs: z.array(liveRow).default([]),
  tool_intents: z.array(liveRow).default([]),
  model_runtime: liveRow.optional().default({} as LiveRow),
}).passthrough();

export type ChatResponse = z.infer<typeof ChatResponseSchema>;

/* ============================================================
 * Workspace Config
 * ============================================================ */
export const WorkspaceConfigSchema = z.object({
  profile: z.object({
    profile_id: z.number(),
    profile_key: z.string(),
    profile_name: z.string(),
    owner_name: z.string(),
    is_active: z.boolean(),
    default_workspace: z.string(),
    theme: z.string(),
    density: z.string(),
    navigation: z.record(z.unknown()).optional().default({}),
    preferences: z.record(z.unknown()).optional().default({}),
    version: z.number(),
    updated_at: z.string(),
  }).passthrough(),
  layouts: z.array(liveRow).default([]),
  widgets: z.array(liveRow).default([]),
  widget_data: z.record(z.array(liveRow)).optional().default({}),
  data_mode: dataMode.optional(),
}).passthrough();

export type WorkspaceConfig = z.infer<typeof WorkspaceConfigSchema>;

/* ============================================================
 * Schema registry — used by query hooks to validate on fetch.
 * ============================================================ */
export const SNAPSHOT_SCHEMAS = {
  missionControl: MissionControlSchema,
  systemHealth: SystemHealthSchema,
  portfolioOffice: PortfolioOfficeSchema,
  researchIdeas: ResearchIdeasSchema,
  tradingQuantRisk: TradingQuantRiskSchema,
  strategyArsenal: StrategyArsenalSchema,
  reports: ReportsSchema,
  integrationGateway: IntegrationGatewaySchema,
  office: OfficeSnapshotSchema,
  graphControl: GraphControlSnapshotSchema,
} as const;

export type SnapshotKey = keyof typeof SNAPSHOT_SCHEMAS;

/**
 * Validate a snapshot payload. On validation failure, logs a warning and
 * returns the raw payload (better to show stale/wonky data than a blank
 * screen). In dev, surfaces the error prominently.
 */
export function validateSnapshot<T extends z.ZodTypeAny>(
  schema: T,
  payload: unknown,
  label: string
): z.infer<T> {
  const result = schema.safeParse(payload);
  if (result.success) return result.data;
  // Validation failed — log and fall back to raw payload cast to the type.
  // This is deliberate: the backend is the source of truth and we don't want
  // a schema drift to blank the UI.
  if (import.meta.env.DEV) {
    console.warn(`[aios] snapshot "${label}" failed validation:`, result.error.issues.slice(0, 5));
  }
  return payload as z.infer<T>;
}
