export interface LiveRow {
  [key: string]: unknown;
}

export interface TradingViewCdpStatus {
  available: boolean;
  port: number;
  browser?: string;
  user_agent?: string;
  error?: string;
  next_action?: string;
}

export interface LiveSnapshot {
  generated_at: string;
  runtime_root: string;
  vault_root: string;
  tradingview_cdp: TradingViewCdpStatus;
  data_mode: {
    seed_data_allowed: boolean;
    display_policy: string;
  };
  metrics: LiveRow[];
  modules: LiveRow[];
  blueprint_summary: LiveRow[];
  blueprint_domains: LiveRow[];
  blueprint_requirements: LiveRow[];
  blueprint_sync_runs: LiveRow[];
  blueprint_v9_summary?: LiveRow[];
  blueprint_v9_domains?: LiveRow[];
  blueprint_v9_requirements?: LiveRow[];
  data_sources: LiveRow[];
  strategies: LiveRow[];
  strategy_intakes: LiveRow[];
  generated_strategy_ideas: LiveRow[];
  strategy_arsenal_queue: LiveRow[];
  strategy_arsenal_summary: LiveRow[];
  strategy_template_summary: LiveRow[];
  strategy_template_library: LiveRow[];
  strategy_template_applications: LiveRow[];
  strategy_backtest_runs: LiveRow[];
  strategy_rule_specs: LiveRow[];
  strategy_data_quality_gates: LiveRow[];
  strategy_dsl_readiness: LiveRow[];
  strategy_optimization_runs: LiveRow[];
  user_defined_optimizer_runs: LiveRow[];
  strategy_discovery_runs: LiveRow[];
  strategy_discovery_candidates: LiveRow[];
  strategy_discovery_triage_queue: LiveRow[];
  strategy_discovery_triage_decisions: LiveRow[];
  strategy_idea_dossiers: LiveRow[];
  strategy_idea_dossier_build_runs: LiveRow[];
  strategy_idea_dossier_search_runs: LiveRow[];
  strategy_idea_dossier_actions: LiveRow[];
  strategy_discovery_scheduler_runs: LiveRow[];
  news_ingestion_runs: LiveRow[];
  latest_news_items: LiveRow[];
  strategy_quant_analytics_runs: LiveRow[];
  strategy_regime_performance: LiveRow[];
  strategy_factor_attribution: LiveRow[];
  strategy_capacity_liquidity: LiveRow[];
  strategy_correlation_matrix: LiveRow[];
  strategy_portfolio_optimizer_runs: LiveRow[];
  strategy_portfolio_allocation_runs: LiveRow[];
  strategy_portfolio_allocations: LiveRow[];
  strategy_probability_of_ruin: LiveRow[];
  strategy_retirement_queue: LiveRow[];
  quant_specialist_assignments: LiveRow[];
  quant_lab_dashboard_v2: LiveRow[];
  model_validation_dashboard: LiveRow[];
  strategy_promotion_board: LiveRow[];
  trade_journal_mining_runs: LiveRow[];
  trade_journal_strategy_patterns: LiveRow[];
  trade_journal_idea_dashboard: LiveRow[];
  strategy_committee_queue: LiveRow[];
  strategy_paper_monitors: LiveRow[];
  strategy_paper_monitor_events: LiveRow[];
  strategy_drift_checks: LiveRow[];
  strategy_kill_switch_events: LiveRow[];
  execution_control: LiveRow[];
  global_kill_switch_events: LiveRow[];
  limited_live_requests: LiveRow[];
  execution_gate_checks: LiveRow[];
  order_intents: LiveRow[];
  order_risk_checks: LiveRow[];
  workflows: LiveRow[];
  agents: LiveRow[];
  agent_departments: LiveRow[];
  agent_skills: LiveRow[];
  agent_office_overview: LiveRow[];
  live_office_rooms: LiveRow[];
  live_office_agent_activity: LiveRow[];
  agent_org_chart: LiveRow[];
  agent_mailboxes: LiveRow[];
  agent_messages: LiveRow[];
  research_factory_queue_summary: LiveRow[];
  agent_models: LiveRow[];
  external_skills: LiveRow[];
  clients: LiveRow[];
  latest_positions: LiveRow[];
  investment_books: LiveRow[];
  book_positions: LiveRow[];
  position_objects_v9: LiveRow[];
  position_object_gap_summary: LiveRow[];
  position_remediation_summary: LiveRow[];
  position_remediation_queue: LiveRow[];
  long_term_theses: LiveRow[];
  long_term_coverage_summary: LiveRow[];
  long_term_coverage_queue: LiveRow[];
  long_term_thesis_checklists: LiveRow[];
  long_term_valuation_models: LiveRow[];
  long_term_monte_carlo_runs: LiveRow[];
  long_term_research_updates: LiveRow[];
  long_term_committee_queue: LiveRow[];
  long_term_specialist_assignments: LiveRow[];
  long_term_specialist_outputs: LiveRow[];
  long_term_source_requests: LiveRow[];
  long_term_source_documents: LiveRow[];
  long_term_source_document_extractions: LiveRow[];
  long_term_source_request_checks: LiveRow[];
  symbol_book_exposure: LiveRow[];
  client_book_exposure: LiveRow[];
  account_book_exposure: LiveRow[];
  strategy_book_exposure: LiveRow[];
  purpose_book_exposure: LiveRow[];
  cross_book_conflicts: LiveRow[];
  cross_book_coordination_questions: LiveRow[];
  book_assignment_gaps: LiveRow[];
  symbol_intelligence: LiveRow[];
  symbol_intelligence_v2_summary: LiveRow[];
  symbol_intelligence_v2: LiveRow[];
  symbol_intelligence_action_summary: LiveRow[];
  symbol_intelligence_actions: LiveRow[];
  portfolio_intelligence_summary: LiveRow[];
  portfolio_intelligence_v2: LiveRow[];
  risk_dashboard_summary: LiveRow[];
  risk_limit_checks: LiveRow[];
  position_purpose_options: LiveRow[];
  broker_transaction_import_summary: LiveRow[];
  broker_transaction_import_queue: LiveRow[];
  trade_book_links: LiveRow[];
  broker_reconciliation_latest: LiveRow[];
  broker_reconciliation_issues: LiveRow[];
  p2cursor_reconciliation_latest: LiveRow[];
  p2cursor_reconciliation_issues: LiveRow[];
  legacy_source_readiness_summary: LiveRow[];
  p2cursor_extraction_readiness: LiveRow[];
  algo_extraction_readiness: LiveRow[];
  legacy_source_extraction_runs: LiveRow[];
  legacy_source_extraction_issues: LiveRow[];
  source_lineage_summary: LiveRow[];
  source_artifact_lineage: LiveRow[];
  import_artifact_coverage: LiveRow[];
  import_artifact_gaps: LiveRow[];
  post_trade_reviews: LiveRow[];
  manual_updates: LiveRow[];
  signals: LiveRow[];
  alerts: LiveRow[];
  mcp_candidates: LiveRow[];
  tradingview_tasks: LiveRow[];
  tradingview_action_templates: LiveRow[];
  tradingview_alert_requests: LiveRow[];
  browser_profiles: LiveRow[];
  browser_connector_links: LiveRow[];
  browser_session_checks: LiveRow[];
  trade_activity: LiveRow[];
  paper_trade_summary: LiveRow[];
  research_hub: LiveRow[];
  filing_collector_runs: LiveRow[];
  corporate_filing_inbox: LiveRow[];
  special_situation_inbox: LiveRow[];
  filing_pdf_extraction_runs: LiveRow[];
  special_situation_terms: LiveRow[];
  special_situation_memos: LiveRow[];
  special_situation_spread_checks: LiveRow[];
  special_situation_decisions: LiveRow[];
  data_source_checks: LiveRow[];
  source_freshness: LiveRow[];
  source_freshness_scheduler_runs: LiveRow[];
  risk_events: LiveRow[];
  fincept: LiveRow[];
  inbox: LiveRow[];
  approvals: LiveRow[];
  approval_board_summary: LiveRow[];
  approval_board_items: LiveRow[];
  committee_room_summary: LiveRow[];
  committee_room_items: LiveRow[];
  employee_profile_summary: LiveRow[];
  employee_profiles: LiveRow[];
  output_artifact_summary: LiveRow[];
  output_artifact_registry: LiveRow[];
  output_artifact_gaps: LiveRow[];
  agent_comment_summary: LiveRow[];
  agent_comments: LiveRow[];
  agent_comment_targets: LiveRow[];
  model_routes: LiveRow[];
  model_endpoints: LiveRow[];
  model_cost_summary: LiveRow[];
  model_cost_events: LiveRow[];
  model_cost_caps: LiveRow[];
  model_route_costs: LiveRow[];
  source_connectors: LiveRow[];
  provider_readiness_board: LiveRow[];
  provider_readiness_summary: LiveRow[];
  provider_readiness_runs: LiveRow[];
  provider_assignment_gates: LiveRow[];
  department_provider_policy_board: LiveRow[];
  task_provider_gate_status: LiveRow[];
  connector_health_checks: LiveRow[];
  chat_turns: LiveRow[];
  widget_intents: LiveRow[];
  dashboard_widgets: LiveRow[];
  agent_jobs: LiveRow[];
  agent_worker_queue: LiveRow[];
  agent_worker_runs: LiveRow[];
  priority_tasks: LiveRow[];
  pipeline_readiness: LiveRow[];
  issues: LiveRow[];
}

export type OfficeSnapshot = Pick<
  LiveSnapshot,
  | "agents"
  | "agent_messages"
  | "committee_room_items"
  | "generated_at"
  | "issues"
  | "live_office_agent_activity"
  | "live_office_rooms"
  | "priority_tasks"
  | "risk_events"
  | "source_freshness"
  | "execution_control"
> & Partial<Pick<LiveSnapshot, "long_term_committee_queue" | "strategy_committee_queue">>;

export interface AgentMessageEvidence {
  approvals: LiveRow[];
  entity: "agent_message";
  entity_id: number;
  inbox_items: LiveRow[];
  message: LiveRow;
  tasks: LiveRow[];
}

export interface CreateTradingViewTaskInput {
  task_title: string;
  task_type?: string;
  requested_by?: string;
  owner_agent?: string;
  priority?: string;
  symbols?: string[];
  exchange?: string;
  timeframe?: string;
  chart_layout?: string;
  instruction?: string;
  source_ref?: string;
  evidence?: unknown[];
  metadata?: Record<string, unknown>;
}

export interface ExecuteTradingViewChartActionInput {
  task_id?: string | number;
  task_title?: string;
  task_type?: string;
  requested_by?: string;
  owner_agent?: string;
  actor?: string;
  priority?: string;
  symbol?: string;
  symbols?: string[];
  exchange?: string;
  timeframe?: string;
  chart_layout?: string;
  instruction?: string;
  source_ref?: string;
  action?: string;
  target_url?: string;
  wait_ms?: number;
  capture_screenshot?: boolean;
  evidence?: unknown[];
  metadata?: Record<string, unknown>;
}

export interface ExecuteTradingViewTemplateActionInput {
  template_key: string;
  task_title?: string;
  actor?: string;
  requested_by?: string;
  owner_agent?: string;
  priority?: string;
  symbol?: string;
  symbols?: string[];
  exchange?: string;
  timeframe?: string;
  chart_layout?: string;
  instruction?: string;
  source_ref?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateInboxItemInput {
  title: string;
  owner_agent?: string;
  agent?: string;
  status?: string;
  priority?: string;
  recommended_action?: string;
  target_workspace?: string;
  actor?: string;
  evidence?: unknown[];
}

export interface CreateAgentMessageInput {
  from_agent?: string;
  to_agent: string;
  subject: string;
  body: string;
  priority?: "low" | "medium" | "high" | "critical";
  thread_key?: string;
  related_skill_key?: string;
  metadata?: Record<string, unknown>;
}

export interface TriageAgentMessageInput {
  message_id: string | number;
  action?: "mark_read" | "acknowledge" | "create_task";
  task_title?: string;
  task_objective?: string;
  priority?: "low" | "normal" | "medium" | "high" | "critical";
  recommended_action?: string;
  target_workspace?: string;
  actor?: string;
}

export interface CreateAgentCommentInput {
  target_kind: string;
  target_ref: string;
  target_title?: string;
  parent_comment_id?: string | number;
  from_agent?: string;
  to_agent?: string;
  comment_type?: string;
  severity?: string;
  status?: string;
  body: string;
  evidence?: unknown[];
  metadata?: Record<string, unknown>;
  actor?: string;
}

export interface ResolveAgentCommentInput {
  comment_id: string | number;
  status?: "acknowledged" | "resolved" | "dismissed";
  actor?: string;
  resolution_note?: string;
}

export interface RefreshPortfolioRiskEventsInput {
  actor?: string;
}

export interface RegisterModelEndpointInput {
  endpoint_key?: string;
  endpoint_name?: string;
  provider?: string;
  model_name?: string;
  route_name?: string;
  endpoint_type?: string;
  base_url?: string;
  deployment_target?: string;
  status?: string;
  context_window?: string | number;
  estimated_disk_gb?: string | number;
  cost_tier?: string;
  capabilities?: string[];
  requires_api_key?: boolean;
  secret_ref?: string;
  owner_agent?: string;
  notes?: string;
  config?: Record<string, unknown>;
  actor?: string;
}

export interface CheckModelEndpointInput {
  endpoint_key: string;
  actor?: string;
}

export interface RegisterSourceConnectorInput {
  connector_key?: string;
  connector_name?: string;
  source_key?: string;
  connector_type?: string;
  provider?: string;
  access_mode?: string;
  status?: string;
  freshness_target_minutes?: string | number;
  requires_api_key?: boolean;
  requires_browser_session?: boolean;
  secret_ref?: string;
  base_url?: string;
  owner_agent?: string;
  sensitivity?: string;
  notes?: string;
  config?: Record<string, unknown>;
  actor?: string;
}

export interface CheckSourceConnectorInput {
  connector_key: string;
  actor?: string;
}

export interface RunProviderReadinessSweepInput {
  run_key?: string;
  actor?: string;
  model_limit?: string | number;
  source_limit?: string | number;
  models_only?: boolean;
  sources_only?: boolean;
}

export interface EvaluateProviderAssignmentGateInput {
  provider_key: string;
  provider_kind?: string;
  requesting_agent?: string;
  requested_use?: string;
  source_kind?: string;
  source_ref?: string;
  target_workspace?: string;
  create_inbox_on_block?: boolean;
  evidence?: Record<string, unknown>[];
  metadata?: Record<string, unknown>;
  actor?: string;
}

export interface RegisterBrowserProfileInput {
  profile_key?: string;
  profile_name?: string;
  browser_name?: string;
  use_case?: string;
  profile_path?: string;
  remote_debugging_host?: string;
  remote_debugging_port?: string | number;
  target_base_url?: string;
  status?: string;
  owner_agent?: string;
  sensitivity?: string;
  permission_level?: string;
  notes?: string;
  config?: Record<string, unknown>;
  actor?: string;
}

export interface AttachBrowserProfileInput {
  profile_key: string;
  connector_key: string;
  actor?: string;
}

export interface CheckBrowserProfileInput {
  profile_key: string;
  connector_key?: string;
  actor?: string;
}

export interface RunFilingCollectorInput {
  source?: "nse" | "bse" | "all";
  date_from: string;
  date_to: string;
  limit?: string | number;
  actor?: string;
  dry_run?: boolean;
}

export interface RunFilingPdfExtractorInput {
  filing_id?: string | number;
  limit?: string | number;
  actor?: string;
  force?: boolean;
  dry_run?: boolean;
}

export interface GenerateSpecialSituationMemoInput {
  special_terms_id: string | number;
  actor?: string;
}

export interface GenerateLongTermThesisMemoInput {
  symbol?: string;
  exchange?: string;
  actor?: string;
}

export interface GenerateLongTermResearchPacketInput {
  holding_thesis_id?: string | number;
  symbol?: string;
  exchange?: string;
  actor?: string;
}

export interface SyncLongTermCoverageInput {
  actor?: string;
  limit?: string | number;
  create_tasks?: boolean;
}

export interface UpdateLongTermChecklistInput {
  holding_thesis_id: string | number;
  checklist_key: string;
  status?: string;
  score?: string | number;
  findings?: unknown[];
  evidence?: unknown[];
  actor?: string;
}

export interface UpdateLongTermValuationInput {
  holding_thesis_id: string | number;
  model_key: string;
  status?: string;
  fair_value_low?: string | number;
  fair_value_base?: string | number;
  fair_value_high?: string | number;
  expected_cagr_pct?: string | number;
  assumptions?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  evidence?: unknown[];
  note_path?: string;
  actor?: string;
}

export interface OpenLongTermCommitteeReviewInput {
  holding_thesis_id: string | number;
  actor?: string;
}

export interface GenerateLongTermCommitteeMemoInput {
  long_term_committee_review_id: string | number;
  actor?: string;
}

export interface ResolveLongTermCommitteeDecisionInput {
  long_term_committee_review_id: string | number;
  decision: "reject" | "research_more" | "monitor" | "approve_watchlist" | "approve_hold";
  actor?: string;
  decision_notes?: string;
}

export interface DispatchLongTermSpecialistsInput {
  holding_thesis_id?: string | number;
  long_term_committee_review_id?: string | number;
  actor?: string;
}

export interface ExecuteLongTermSpecialistInput {
  assignment_id?: string | number;
  assignment_key?: string;
  actor?: string;
}

export interface CreateLongTermSourceRequestsInput {
  specialist_output_id?: string | number;
  assignment_id?: string | number;
  holding_thesis_id?: string | number;
  limit?: string | number;
  actor?: string;
}

export interface CheckLongTermSourceRequestsInput {
  source_request_id?: string | number;
  holding_thesis_id?: string | number;
  limit?: string | number;
  actor?: string;
}

export interface RegisterLongTermSourceDocumentInput {
  source_request_id: string | number;
  title: string;
  source_url: string;
  document_type?: string;
  source_name?: string;
  local_path?: string;
  summary?: string;
  actor?: string;
}

export interface ExtractLongTermSourceDocumentInput {
  source_document_id?: string | number;
  symbol?: string;
  actor?: string;
}

export interface CalculateSpecialSituationSpreadInput {
  special_memo_id: string | number;
  actor?: string;
}

export interface RefreshEventQuotesInput {
  symbols?: string[] | string;
  limit?: string | number;
  actor?: string;
  dry_run?: boolean;
}

export interface CheckSourceFreshnessInput {
  source_key?: string;
  limit?: string | number;
  target_minutes?: string | number;
  actor?: string;
}

export interface ResolveSpecialSituationDecisionInput {
  special_memo_id: string | number;
  decision: "reject" | "monitor" | "research_more" | "committee_review";
  actor?: string;
  decision_notes?: string;
}

export interface ResolveApprovalInput {
  approval_id: string;
  status: "approved" | "rejected";
  decided_by?: string;
}

export interface ResolveTradingViewAlertRequestInput {
  approval_id: string | number;
  status: "approved" | "rejected";
  decided_by?: string;
  decision_note?: string;
}

export interface StageHoldingUpdateInput {
  client_code: string;
  account_code: string;
  symbol: string;
  quantity: string;
  exchange?: string;
  instrument_type?: string;
  average_price?: string;
  market_price?: string;
  market_value?: string;
  update_reason?: string;
  actor?: string;
}

export interface UpdateBookAssignmentInput {
  book_position_id: string;
  book_key: string;
  purpose_key: string;
  thesis?: string;
  exit_criteria?: string;
  rationale?: string;
  actor?: string;
}

export interface RecordTradeInput {
  symbol: string;
  side: string;
  quantity?: string;
  price?: string;
  client_code?: string;
  account_code?: string;
  strategy_key?: string;
  exchange?: string;
  instrument_type?: string;
  thesis?: string;
  setup_type?: string;
  timeframe?: string;
  stop_loss?: string;
  target_price?: string;
  book_key?: string;
  purpose_key?: string;
  actor?: string;
}

export interface CreateStrategyIntakeInput {
  intake_text: string;
  strategy_name?: string;
  strategy_family?: string;
  asset_class?: string;
  symbols?: string[];
  universe?: string;
  timeframe?: string;
  intent_tags?: string[];
  constraints_text?: string;
  risk_notes?: string;
  requested_outputs?: string[];
  actor?: string;
}

export interface ApplyStrategyTemplateInput {
  template_key: string;
  actor?: string;
  strategy_name?: string;
  symbols?: string[];
  universe?: string;
  timeframe?: string;
  notes?: string;
}

export interface RunStrategyBacktestInput {
  candidate_id: string | number;
  symbols?: string[];
  timeframe?: string;
  template?: "momentum" | "mean_reversion" | "breakout" | "low_volatility";
  cost_bps?: string | number;
  slippage_bps?: string | number;
  max_symbols?: string | number;
  min_rows_per_symbol?: string | number;
  min_total_rows?: string | number;
  actor?: string;
}

export interface RunStrategyOptimizationInput extends RunStrategyBacktestInput {}

export interface RunUserDefinedStrategyOptimizerInput {
  run_key?: string;
  actor?: string;
  strategy_name: string;
  intake_text: string;
  dsl_text?: string;
  asset_class?: string;
  symbols?: string[];
  universe?: string;
  timeframe?: string;
  template?: "momentum" | "mean_reversion" | "breakout" | "low_volatility";
  constraints_text?: string;
  risk_notes?: string;
  cost_bps?: string | number;
  slippage_bps?: string | number;
  max_symbols?: string | number;
  min_rows_per_symbol?: string | number;
  min_total_rows?: string | number;
}

export interface RunStrategyDiscoveryInput {
  run_key?: string;
  actor?: string;
  sources?: string;
  per_source_limit?: string | number;
  max_candidates?: string | number;
  route_top?: string | number;
}

export interface ResolveStrategyDiscoveryTriageInput {
  discovery_candidate_id: string | number;
  decision: "reject" | "request_more_evidence" | "route_quant_lab" | "route_special_situation" | "open_committee_review";
  actor?: string;
  notes?: string;
}

export interface BuildStrategyIdeaDossiersInput {
  run_key?: string;
  actor?: string;
  limit?: string | number;
  max_dossiers?: string | number;
  no_notes?: boolean;
}

export interface SearchStrategyIdeaDossiersInput {
  query: string;
  run_key?: string;
  actor?: string;
  limit?: string | number;
}

export interface RunStrategyDossierActionInput {
  dossier_id: string | number;
  action: "request_more_evidence" | "route_quant_lab" | "route_special_situation" | "open_committee_review" | "generate_committee_memo";
  run_key?: string;
  actor?: string;
  notes?: string;
}

export interface IngestMarketNewsInput {
  run_key?: string;
  actor?: string;
  feed_keys?: string;
  feed_limit?: string | number;
  per_feed?: string | number;
  timeout?: string | number;
}

export interface RunStrategyDiscoverySchedulerInput {
  run_key?: string;
  actor?: string;
  interval_seconds?: string | number;
  sources?: string;
  per_source_limit?: string | number;
  max_candidates?: string | number;
  route_top?: string | number;
  news_feed_keys?: string;
  news_feed_limit?: string | number;
  news_per_feed?: string | number;
  enable_filings?: boolean;
  filing_lookback_days?: string | number;
  filing_limit?: string | number;
  filing_timeout?: string | number;
  enable_filing_extraction?: boolean;
  filing_extraction_limit?: string | number;
  filing_extraction_timeout?: string | number;
  disable_news?: boolean;
}

export interface RunStrategyQuantAnalyticsInput {
  run_key?: string;
  strategy_ids?: Array<string | number>;
  timeframe?: string;
  limit?: string | number;
  max_symbols?: string | number;
  cost_bps?: string | number;
  slippage_bps?: string | number;
  participation_rate?: string | number;
  actor?: string;
}

export interface RunStrategyPortfolioAllocationInput {
  allocation_key?: string;
  analytics_run_key?: string;
  timeframe?: string;
  capital_base?: string | number;
  max_weight?: string | number;
  ruin_threshold_pct?: string | number;
  horizon_bars?: string | number;
  simulation_count?: string | number;
  seed?: string | number;
  actor?: string;
}

export interface RunStrategyRetirementReviewInput {
  review_key_prefix?: string;
  analytics_run_key?: string;
  allocation_key?: string;
  actor?: string;
}

export interface RunModelValidationSweepInput {
  validation_key_prefix?: string;
  actor?: string;
  limit?: string | number;
}

export interface RunTradeJournalStrategyMiningInput {
  run_key?: string;
  actor?: string;
  min_trades?: string | number;
  max_patterns?: string | number;
  allow_thin_sample?: boolean;
}

export interface ParseStrategyDslInput {
  candidate_id: string | number;
  dsl_text?: string;
  actor?: string;
}

export interface CheckStrategyDataQualityInput {
  candidate_id: string | number;
  symbols?: string[];
  timeframe?: string;
  min_rows_per_symbol?: string | number;
  min_total_rows?: string | number;
  actor?: string;
}

export interface OpenStrategyCommitteeReviewInput {
  optimization_run_id: string | number;
  actor?: string;
}

export interface GenerateStrategyCommitteeMemoInput {
  committee_review_id: string | number;
  actor?: string;
}

export interface ResolveStrategyCommitteeDecisionInput {
  committee_review_id: string | number;
  decision: "reject" | "retest" | "research_more" | "approve_paper_monitor";
  actor?: string;
  decision_notes?: string;
}

export interface StartStrategyPaperMonitorInput {
  committee_review_id: string | number;
  actor?: string;
  notes?: string;
}

export interface PaperMonitorHeartbeatInput {
  paper_monitor_session_id: string | number;
  actor?: string;
  heartbeat_status?: "ok" | "warning" | "stale" | "error" | "stopped";
  signal_count?: string | number;
  metrics?: Record<string, unknown>;
  payload?: Record<string, unknown>;
}

export interface StopStrategyPaperMonitorInput {
  paper_monitor_session_id: string | number;
  actor?: string;
  reason?: string;
}

export interface EvaluateStrategyDriftInput {
  paper_monitor_session_id: string | number;
  actor?: string;
  thresholds?: Record<string, unknown>;
}

export interface EnforceStrategyKillSwitchInput {
  paper_monitor_session_id?: string | number;
  drift_check_id?: string | number;
  actor?: string;
  trigger_reason?: string;
}

export interface EngageGlobalKillSwitchInput {
  actor?: string;
  trigger_reason?: string;
  trigger_source?: string;
}

export interface RequestLimitedLiveApprovalInput {
  strategy_id?: string | number;
  instance_id?: string | number;
  book_key?: string;
  symbol?: string;
  max_notional?: string | number;
  max_orders_per_day?: string | number;
  max_daily_loss?: string | number;
  expires_at?: string;
  actor?: string;
  rationale?: string;
}

export interface SyncLimitedLiveRequestInput {
  limited_live_request_id: string | number;
  actor?: string;
}

export interface EvaluateExecutionGateInput {
  limited_live_request_id?: string | number;
  actor?: string;
  order_intent?: Record<string, unknown>;
}

export interface CreateOrderIntentInput {
  limited_live_request_id: string | number;
  actor?: string;
  rationale?: string;
  order_intent: Record<string, unknown>;
}

export interface EvaluateOrderIntentRiskInput {
  order_intent_id: string | number;
  actor?: string;
}

export interface ChatInput {
  message: string;
  session_key?: string;
  actor?: string;
  workspace?: string;
  route_name?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatResponse {
  chat_turn: LiveRow;
  message: string;
  route: LiveRow;
  model_status: string;
  retrieval_status: string;
  retrieval_hits: LiveRow[];
  widget_intents: LiveRow[];
  materialization: LiveRow;
  dashboard_widgets: LiveRow[];
  agent_jobs: LiveRow[];
  tool_intents: LiveRow[];
  model_runtime: LiveRow;
}

const API_URL = (import.meta.env.VITE_AI_OS_API_URL || "http://127.0.0.1:8765").replace(/\/$/, "");

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || `HTTP ${response.status}`);
  }
  return payload as T;
}

export function fetchLiveSnapshot(): Promise<LiveSnapshot> {
  return requestJson<LiveSnapshot>("/api/snapshot");
}

export function fetchOfficeSnapshot(): Promise<OfficeSnapshot> {
  return requestJson<OfficeSnapshot>("/api/office/snapshot");
}

export function fetchAgentMessageEvidence(messageId: string | number): Promise<AgentMessageEvidence> {
  return requestJson<AgentMessageEvidence>(`/api/evidence/agent-message/${encodeURIComponent(String(messageId))}`);
}

export function createTradingViewTask(input: CreateTradingViewTaskInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/tradingview/tasks", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function executeTradingViewChartAction(input: ExecuteTradingViewChartActionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/tradingview/chart-actions", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function executeTradingViewTemplateAction(input: ExecuteTradingViewTemplateActionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/tradingview/template-actions", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createInboxItem(input: CreateInboxItemInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/inbox/items", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createAgentMessage(input: CreateAgentMessageInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/agents/messages", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function triageAgentMessage(input: TriageAgentMessageInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/agents/messages/triage", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createAgentComment(input: CreateAgentCommentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/agents/comments", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveAgentComment(input: ResolveAgentCommentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/agents/comments/resolve", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function refreshPortfolioRiskEvents(input: RefreshPortfolioRiskEventsInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/risk/portfolio/refresh-events", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function registerModelEndpoint(input: RegisterModelEndpointInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/models/endpoints/register", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkModelEndpoint(input: CheckModelEndpointInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/models/endpoints/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function registerSourceConnector(input: RegisterSourceConnectorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/data-sources/connectors/register", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkSourceConnector(input: CheckSourceConnectorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/data-sources/connectors/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runProviderReadinessSweep(input: RunProviderReadinessSweepInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/providers/readiness/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function evaluateProviderAssignmentGate(input: EvaluateProviderAssignmentGateInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/providers/assignment-gate/evaluate", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function registerBrowserProfile(input: RegisterBrowserProfileInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/browser/profiles/register", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function attachBrowserProfile(input: AttachBrowserProfileInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/browser/connectors/attach-profile", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkBrowserProfile(input: CheckBrowserProfileInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/browser/profiles/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runFilingCollector(input: RunFilingCollectorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/filings/collect", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runFilingPdfExtractor(input: RunFilingPdfExtractorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/filings/extract-pdfs", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function generateSpecialSituationMemo(input: GenerateSpecialSituationMemoInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/special-situations/memo", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function generateLongTermThesisMemo(input: GenerateLongTermThesisMemoInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-thesis/memo", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function generateLongTermResearchPacket(input: GenerateLongTermResearchPacketInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-thesis/research-packet", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function syncLongTermCoverage(input: SyncLongTermCoverageInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-coverage/sync", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function updateLongTermChecklist(input: UpdateLongTermChecklistInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-thesis/checklist", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function updateLongTermValuation(input: UpdateLongTermValuationInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-thesis/valuation", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function openLongTermCommitteeReview(input: OpenLongTermCommitteeReviewInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-committee/open", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function generateLongTermCommitteeMemo(input: GenerateLongTermCommitteeMemoInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-committee/memo", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveLongTermCommitteeDecision(input: ResolveLongTermCommitteeDecisionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-committee/decision", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function dispatchLongTermSpecialists(input: DispatchLongTermSpecialistsInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-specialists/dispatch", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function executeLongTermSpecialist(input: ExecuteLongTermSpecialistInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-specialists/execute", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createLongTermSourceRequests(input: CreateLongTermSourceRequestsInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-source-requests/create", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkLongTermSourceRequests(input: CheckLongTermSourceRequestsInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-source-requests/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function registerLongTermSourceDocument(input: RegisterLongTermSourceDocumentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-source-documents/register", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function extractLongTermSourceDocument(input: ExtractLongTermSourceDocumentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/long-term-source-documents/extract", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function calculateSpecialSituationSpread(input: CalculateSpecialSituationSpreadInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/special-situations/spread", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function refreshEventQuotes(input: RefreshEventQuotesInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/special-situations/refresh-quotes", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkSourceFreshness(input: CheckSourceFreshnessInput = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/data-sources/freshness/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveSpecialSituationDecision(input: ResolveSpecialSituationDecisionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/research/special-situations/decision", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveApproval(input: ResolveApprovalInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/approvals/resolve", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveTradingViewAlertRequest(input: ResolveTradingViewAlertRequestInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/tradingview/alert-requests/resolve", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function stageHoldingUpdate(input: StageHoldingUpdateInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/holding-updates/stage", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function updateBookAssignment(input: UpdateBookAssignmentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/book-assignments", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function syncPositionReadinessRemediation(input: {
  actor?: string;
  limit?: number;
  create_tasks?: boolean;
  createTasks?: boolean;
}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/portfolio/position-readiness/remediate", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function routeSymbolIntelligenceAction(input: {
  action_type?: string;
  actionType?: string;
  actor?: string;
  client_code?: string;
  clientCode?: string;
  exchange?: string;
  notes?: string;
  symbol: string;
}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/symbol-intelligence/actions", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createStrategyIntake(input: CreateStrategyIntakeInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/intakes", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function applyStrategyTemplate(input: ApplyStrategyTemplateInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/templates/apply", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyBacktest(input: RunStrategyBacktestInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/backtests/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function parseStrategyDsl(input: ParseStrategyDslInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/dsl/parse", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function checkStrategyDataQuality(input: CheckStrategyDataQualityInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/data-quality/check", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyOptimization(input: RunStrategyOptimizationInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/optimizations/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runUserDefinedStrategyOptimizer(input: RunUserDefinedStrategyOptimizerInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/user-defined-optimizer/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyDiscovery(input: RunStrategyDiscoveryInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/discovery/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveStrategyDiscoveryTriage(input: ResolveStrategyDiscoveryTriageInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/discovery/triage/resolve", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function buildStrategyIdeaDossiers(input: BuildStrategyIdeaDossiersInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/idea-dossiers/build", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function searchStrategyIdeaDossiers(input: SearchStrategyIdeaDossiersInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/idea-dossiers/search", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyDossierAction(input: RunStrategyDossierActionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/idea-dossiers/action", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function ingestMarketNews(input: IngestMarketNewsInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/market/news/ingest", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyDiscoveryScheduler(input: RunStrategyDiscoverySchedulerInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/discovery/scheduler/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyQuantAnalytics(input: RunStrategyQuantAnalyticsInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/quant-analytics/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyPortfolioAllocation(input: RunStrategyPortfolioAllocationInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/portfolio-allocation/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runStrategyRetirementReview(input: RunStrategyRetirementReviewInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/retirement/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runModelValidationSweep(input: RunModelValidationSweepInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/model-validation/sweep", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runTradeJournalStrategyMining(input: RunTradeJournalStrategyMiningInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/trade-journal-mining/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function openStrategyCommitteeReview(input: OpenStrategyCommitteeReviewInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/committee/open", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function generateStrategyCommitteeMemo(input: GenerateStrategyCommitteeMemoInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/committee/memo", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function resolveStrategyCommitteeDecision(input: ResolveStrategyCommitteeDecisionInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/committee/decision", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function startStrategyPaperMonitor(input: StartStrategyPaperMonitorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/paper-monitor/start", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function recordPaperMonitorHeartbeat(input: PaperMonitorHeartbeatInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/paper-monitor/heartbeat", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function stopStrategyPaperMonitor(input: StopStrategyPaperMonitorInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/paper-monitor/stop", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function evaluateStrategyDrift(input: EvaluateStrategyDriftInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/drift/evaluate", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function enforceStrategyKillSwitch(input: EnforceStrategyKillSwitchInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/strategy/kill-switch/enforce", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function engageGlobalKillSwitch(input: EngageGlobalKillSwitchInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/global-kill-switch/engage", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function requestLimitedLiveApproval(input: RequestLimitedLiveApprovalInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/limited-live/request", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function syncLimitedLiveRequest(input: SyncLimitedLiveRequestInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/limited-live/sync", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function evaluateExecutionGate(input: EvaluateExecutionGateInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/gate/evaluate", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function createOrderIntent(input: CreateOrderIntentInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/order-intents/create", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function evaluateOrderIntentRisk(input: EvaluateOrderIntentRiskInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/execution/order-intents/evaluate-risk", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function recordManualTrade(input: RecordTradeInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/trades/manual", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function recordPaperTrade(input: RecordTradeInput): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/trades/paper", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function stageBrokerTransactions(input: {
  actor?: string;
  limit?: number;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/broker-transactions/stage", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runBrokerReconciliation(input: {
  actor?: string;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/broker-reconciliation/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runP2CursorReconciliation(input: {
  actor?: string;
  client_code?: string;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/p2cursor-reconciliation/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runLegacySourceReadiness(input: {
  actor?: string;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/legacy-source-readiness/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function sendChat(input: ChatInput): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function materializeDashboardWidgets(input: {
  actor?: string;
  include_existing?: boolean;
  limit?: number;
  session_key?: string;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/dashboard/widgets/materialize", {
    body: JSON.stringify(input),
    method: "POST"
  });
}

export function runAgentWorker(input: {
  actor?: string;
  include_completed?: boolean;
  limit?: number;
} = {}): Promise<LiveRow> {
  return requestJson<LiveRow>("/api/agents/worker/run", {
    body: JSON.stringify(input),
    method: "POST"
  });
}
