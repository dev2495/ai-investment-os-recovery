CREATE TABLE IF NOT EXISTS agent.department_registry (
    department_key TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    mission TEXT NOT NULL,
    lead_agent TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'medium',
    core_workflows TEXT[] NOT NULL DEFAULT '{}',
    required_next_builds TEXT[] NOT NULL DEFAULT '{}',
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE agent.profiles
    ADD COLUMN IF NOT EXISTS display_title TEXT,
    ADD COLUMN IF NOT EXISTS persona TEXT,
    ADD COLUMN IF NOT EXISTS operating_style TEXT,
    ADD COLUMN IF NOT EXISTS mental_models TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS escalation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS daily_cadence TEXT,
    ADD COLUMN IF NOT EXISTS cost_policy TEXT NOT NULL DEFAULT 'local_first',
    ADD COLUMN IF NOT EXISTS human_interface TEXT;

CREATE TABLE IF NOT EXISTS agent.skills (
    id BIGSERIAL PRIMARY KEY,
    skill_key TEXT NOT NULL UNIQUE,
    skill_name TEXT NOT NULL,
    skill_family TEXT NOT NULL,
    skill_type TEXT NOT NULL DEFAULT 'analysis',
    owner_department TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    execution_mode TEXT NOT NULL DEFAULT 'worker_deterministic',
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    trigger_phrases TEXT[] NOT NULL DEFAULT '{}',
    input_sources TEXT[] NOT NULL DEFAULT '{}',
    output_targets TEXT[] NOT NULL DEFAULT '{}',
    required_tools TEXT[] NOT NULL DEFAULT '{}',
    risk_notes TEXT,
    prompt_template TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_skills_family ON agent.skills (skill_family);
CREATE INDEX IF NOT EXISTS idx_agent_skills_status ON agent.skills (status);
CREATE INDEX IF NOT EXISTS idx_agent_skills_owner_department ON agent.skills (owner_department);

CREATE TABLE IF NOT EXISTS agent.agent_skill_map (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE CASCADE,
    skill_key TEXT NOT NULL REFERENCES agent.skills(skill_key) ON DELETE CASCADE,
    proficiency TEXT NOT NULL DEFAULT 'working',
    is_primary BOOLEAN NOT NULL DEFAULT false,
    activation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_name, skill_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_skill_map_agent ON agent.agent_skill_map (agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_skill_map_skill ON agent.agent_skill_map (skill_key);

CREATE TABLE IF NOT EXISTS agent.worker_runs (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    widget_id BIGINT REFERENCES ops.dashboard_widgets(id) ON DELETE SET NULL,
    agent_name TEXT NOT NULL,
    skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE SET NULL,
    run_mode TEXT NOT NULL DEFAULT 'manual_once',
    status TEXT NOT NULL DEFAULT 'completed',
    input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_summary TEXT,
    output_note_path TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_worker_runs_task ON agent.worker_runs (task_id);
CREATE INDEX IF NOT EXISTS idx_worker_runs_agent ON agent.worker_runs (agent_name);
CREATE INDEX IF NOT EXISTS idx_worker_runs_skill ON agent.worker_runs (skill_key);
CREATE INDEX IF NOT EXISTS idx_worker_runs_created ON agent.worker_runs (created_at DESC);

INSERT INTO agent.department_registry (
    department_key, department_name, mission, lead_agent, status, priority,
    core_workflows, required_next_builds, guardrails
)
VALUES
    ('executive', 'Executive Office', 'Turn Devarsh instructions into scoped work, decisions, approvals, and daily operating briefs.', 'Charlie Munger', 'active', 'critical', ARRAY['daily_ai_office_brief','cross_department_routing','decision_review'], ARRAY['voice/chat command router','daily brief scheduler','approval summary'], '{"human_final_decision":true}'::jsonb),
    ('runtime', 'Runtime Operations', 'Keep tools, models, MCPs, widgets, queues, and worker services healthy.', 'Jarvis', 'active', 'critical', ARRAY['dashboard_widget_refresh','agent_worker_dispatch','mcp_health_monitor'], ARRAY['continuous worker daemon','tool failure retry policy','model escalation budget ledger'], '{"no_secret_exposure":true}'::jsonb),
    ('portfolio', 'Portfolio Office', 'Maintain client folios, holdings, thesis drift, allocation, long-term research, and client-level actions.', 'Portfolio Manager', 'active', 'critical', ARRAY['portfolio_daily_brief','client_holding_review','manual_holding_update_review'], ARRAY['broker read-only sync','client report generator','position thesis tracker'], '{"client_private":true}'::jsonb),
    ('research', 'Research Desk', 'Own company research, filings, special situations, news evidence, and idea generation.', 'Research Analyst', 'active', 'critical', ARRAY['company_research_note','filing_analysis','special_situation_scan'], ARRAY['NSE/BSE collector','filing PDF parser','research folder generator'], '{"source_required":true}'::jsonb),
    ('news', 'News Intelligence', 'Monitor NSE/BSE announcements, global news, Twitter/X watchlists, corporate actions, and urgency routing.', 'News Analyst', 'active', 'high', ARRAY['nse_bse_announcement_monitor','global_market_news_digest','social_watchlist_triage'], ARRAY['RSS/news collector','Twitter/X bookmark importer','corporate action classifier'], '{"source_url_required":true,"rumor_flag_required":true}'::jsonb),
    ('quant', 'Quant Lab', 'Generate, backtest, validate, and optimize strategies without allowing live execution by default.', 'Strategy Generator', 'active', 'critical', ARRAY['strategy_intake','strategy_generation','backtest_review','optimization_review'], ARRAY['local backtest runner','walk-forward harness','factor library'], '{"paper_first":true,"no_live_execution":true}'::jsonb),
    ('trading', 'Trading Desk', 'Track TradingView tasks, manual trades, paper trades, intraday alerts, and execution checklists.', 'Trading Desk Agent', 'active', 'critical', ARRAY['tradingview_chart_task','strategy_alert_monitor','manual_trade_log'], ARRAY['TradingView browser executor','alert bridge','intraday blotter'], '{"broker_execution_disabled":true}'::jsonb),
    ('risk', 'Risk and Compliance', 'Challenge recommendations, enforce approval gates, concentration limits, drawdown controls, and client-facing quality.', 'Risk Agent', 'active', 'critical', ARRAY['risk_gate_review','portfolio_concentration_check','strategy_activation_review'], ARRAY['risk limits dashboard','approval policy engine','client report QC'], '{"approval_required_for_trade_action":true}'::jsonb),
    ('data', 'Data Engineering', 'Ingest, validate, and reconcile legacy systems, broker files, OHLCV, news feeds, and research artifacts.', 'Data Steward', 'active', 'high', ARRAY['source_ingestion','data_quality_check','lineage_review'], ARRAY['source connector scheduler','data diff monitor','p2cursor reconciler'], '{"lineage_required":true}'::jsonb),
    ('knowledge', 'Knowledge and Memory', 'Keep Obsidian, Qdrant, research folders, and durable notes clean and retrievable.', 'Librarian Agent', 'active', 'high', ARRAY['obsidian_writeback','vault_index_refresh','research_folder_maintenance'], ARRAY['graph hygiene dashboard','duplicate note detector','periodic Qdrant reindex'], '{"writeback_preserves_vault":true}'::jsonb),
    ('automation', 'Automation Engineering', 'Build browser, MCP, worker, notification, and report-generation automations safely.', 'Automation Engineer', 'planned', 'medium', ARRAY['browser_task_runner','scheduled_agent_worker','notification_router'], ARRAY['worker daemon launchd','browser screenshot artifact store','alert notification channels'], '{"approval_required_for_destructive_browser_action":true}'::jsonb)
ON CONFLICT (department_key) DO UPDATE SET
    department_name = EXCLUDED.department_name,
    mission = EXCLUDED.mission,
    lead_agent = EXCLUDED.lead_agent,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    core_workflows = EXCLUDED.core_workflows,
    required_next_builds = EXCLUDED.required_next_builds,
    guardrails = EXCLUDED.guardrails,
    updated_at = now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model, escalation_provider,
    escalation_model, max_cost_tier, notes, enabled
)
VALUES
    ('research_company_analysis', 'equity_research', 'ollama', 'llama3.2:3b', 'cloud_optional', '', 'hybrid', 'Company research and filings summaries; escalate for large PDFs or deep valuation.', true),
    ('agent_worker_deterministic', 'worker', 'local_python', 'deterministic_tools', 'cloud_optional', '', 'local', 'Fast local worker path for dashboard jobs and evidence-backed status updates.', true),
    ('news_event_triage', 'news_monitoring', 'ollama', 'llama3.2:3b', 'cloud_optional', '', 'local', 'Low-cost news and filing event triage; source links required.', true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

INSERT INTO agent.profiles (
    agent_name, department, role_scope, default_model_route, default_tools,
    permission_level, status, guardrails, output_targets, display_title,
    persona, operating_style, mental_models, escalation_rules, daily_cadence,
    cost_policy, human_interface
)
VALUES
    ('Charlie Munger', 'executive', 'Chief orchestrator for capital allocation, truth-testing, task routing, and decision review.', 'charlie_munger_orchestration', ARRAY['jarvis_runtime','postgres_read_model','qdrant_vector_search','obsidian_note_index','agent_worker_dispatch'], 'write_with_approval', 'active', '{"brutal_truth":true,"no_false_precision":true,"force_inversion":true,"human_final_decision":true}'::jsonb, ARRAY['agent.tasks','agent.inbox_items','knowledge.obsidian_notes','agent.approvals'], 'Chief Investment Orchestrator', 'Blunt, rational, multidisciplinary, evidence-first. Challenges weak assumptions before giving an answer.', 'Starts with what can go wrong, separates facts from inference, forces opportunity cost and downside thinking.', ARRAY['inversion','circle_of_competence','margin_of_safety','opportunity_cost','incentives','second_order_effects','base_rates'], '{"escalate_to_cloud_for":["large legal filings","complex multi-company merger analysis","long-form client report"],"ask_human_for":["trade approval","client-facing recommendation"]}'::jsonb, 'Morning brief, market-open triage, post-market review, on-demand decision memo.', 'local_first_escalate_only_for_deep_work', 'You talk to Charlie for decisions, assignments, portfolio questions, and what the office should do next.'),
    ('Jarvis', 'runtime', 'Runtime operator that dispatches tools, tracks jobs, updates widgets, and keeps the AI Office live.', 'jarvis_runtime', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','obsidian_writeback','mcp_tool_dispatch','agent_worker_dispatch'], 'write_with_approval', 'active', '{"must_route_specialist_work":true,"must_require_evidence":true,"no_live_trade_without_approval":true}'::jsonb, ARRAY['agent.tasks','agent.inbox_items','ops.dashboard_widgets','knowledge.obsidian_notes'], 'Runtime Operator', 'Operational, concise, tool-first, low-drama. Converts intent into work records and evidence.', 'Prefers idempotent writes, explicit source refs, small verified steps, and visible dashboard state.', ARRAY['checklists','idempotency','observability','least_privilege','human_in_the_loop'], '{"escalate_to_charlie_for":["ambiguous investment decision","conflicting agent output"],"block_without_approval":["broker execution","deleting source data","posting to external sites"]}'::jsonb, 'Always-on queue watch, widget refresh, tool health, MCP availability.', 'local_first', 'Jarvis is the operator behind the UI, jobs, widgets, MCPs, and worker services.'),
    ('Research Analyst', 'research', 'Deep company research, valuation context, thesis maintenance, and evidence-backed research notes.', 'research_company_analysis', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','filing_event_reader','research_note_writer'], 'read_only', 'active', '{"source_required":true,"separate_fact_inference_opinion":true,"valuation_without_price_target_hype":true}'::jsonb, ARRAY['research.ideas','portfolio.holding_theses','knowledge.obsidian_notes','agent.inbox_items'], 'Equity Research Analyst', 'Patient, skeptical, thesis-driven. Builds research folders instead of one-off comments.', 'Maps business quality, management incentives, balance sheet risk, valuation, catalysts, and disconfirming evidence.', ARRAY['moat','unit_economics','capital_allocation','management_incentives','base_rates','variant_perception'], '{"escalate_to_charlie_for":["buy/sell decision","portfolio sizing"],"escalate_to_filings_analyst_for":["source filing extraction"]}'::jsonb, 'Update research folders when holdings, filings, or major news change.', 'local_first_escalate_for_long_reports', 'Use for company-level research and long-term holding theses.'),
    ('Portfolio Manager', 'portfolio', 'Client folio review, allocation drift, holdings updates, long-term thesis tracking, and portfolio actions.', 'daily_brief', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','portfolio_snapshot_reader'], 'read_only', 'active', '{"client_private":true,"separate_fact_assumption_recommendation":true,"no_client_output_without_review":true}'::jsonb, ARRAY['portfolio.clients','portfolio.positions','portfolio.holding_theses','agent.inbox_items'], 'Portfolio Manager', 'Practical, client-aware, risk-adjusted. Looks at the whole book before individual ideas.', 'Checks concentration, thesis age, drawdown, liquidity, tax/trade friction, client objective, and opportunity cost.', ARRAY['position_sizing','risk_budgeting','tax_awareness','thesis_drift','liquidity','portfolio_construction'], '{"escalate_to_risk_for":["concentration breach","illiquid exposure","derivatives exposure"],"escalate_to_charlie_for":["rebalance recommendation","client-facing action"]}'::jsonb, 'Pre-open portfolio brief, post-close drift review, ad hoc client update.', 'local_first', 'Use for client holdings, long-term portfolio review, and action lists.'),
    ('News Analyst', 'news', 'Curate news, exchange announcements, social watchlists, corporate actions, and urgency routing.', 'news_event_triage', ARRAY['browser_research_runner','postgres_read_model','qdrant_vector_search','news_feed_reader','source_credibility_scorer'], 'read_only', 'active', '{"public_sources_only_by_default":true,"source_url_required":true,"rumor_flag_required":true}'::jsonb, ARRAY['market.news_items','market.social_items','research.filing_events','agent.inbox_items'], 'News Intelligence Analyst', 'Fast but skeptical. Prioritizes source quality, materiality, and what action is required.', 'Tags urgency, symbol impact, source credibility, event type, and whether a specialist must review.', ARRAY['source_quality','materiality','timeliness','catalyst_mapping','rumor_vs_filing'], '{"escalate_to_filings_analyst_for":["exchange filing","corporate action"],"escalate_to_risk_for":["market-wide risk","position shock"]}'::jsonb, 'Every 15-60 minutes when collectors are enabled; manual now.', 'local_first', 'Use for NSE/BSE/global news/Twitter watchlist triage.'),
    ('Filings Analyst', 'research', 'Analyze NSE/BSE/SEC filings, results, corporate actions, and event disclosures.', 'filing_analysis', ARRAY['browser_research_runner','postgres_read_model','qdrant_vector_search','document_parser','filing_event_extractor'], 'read_only', 'active', '{"source_url_required":true,"file_before_opinion":true,"quote_less_summarize_more":true}'::jsonb, ARRAY['research.corporate_filings','research.filing_events','research.ideas','knowledge.obsidian_notes'], 'Corporate Filings Analyst', 'Precise, source-bound, legalistic. Avoids narrative until the filing facts are extracted.', 'Classifies disclosure type, dates, ratios, record dates, conditions, related parties, and actionability.', ARRAY['materiality','corporate_action_math','event_timeline','legal_conditions','minority_shareholder_risk'], '{"escalate_to_special_situations_for":["demerger","merger","buyback","open offer","delisting"],"escalate_to_charlie_for":["investment action"]}'::jsonb, 'On new filing imports or manual document requests.', 'local_first_escalate_for_large_pdf', 'Use when a filing/document must be read before an opinion.'),
    ('Special Situations Agent', 'research', 'Find and analyze arbitrage, demergers, mergers, buybacks, delistings, restructurings, and event-driven ideas.', 'filing_analysis', ARRAY['postgres_read_model','qdrant_vector_search','browser_research_runner','special_situation_screener'], 'read_only', 'active', '{"evidence_required":true,"risk_score_required":true,"no_trade_recommendation_without_pm_review":true}'::jsonb, ARRAY['research.ideas','research.filing_events','agent.inbox_items'], 'Special Situations Analyst', 'Event-driven, skeptical of headline arbitrage, obsessed with conditions and downside.', 'Builds timeline, spread, conditions, probability, capital lockup, downside, liquidity, and regulatory risk.', ARRAY['expected_value','deal_spread','path_dependency','liquidity','regulatory_risk','incentives'], '{"escalate_to_risk_for":["illiquid event","legal uncertainty"],"escalate_to_charlie_for":["capital allocation decision"]}'::jsonb, 'On corporate action filing/news, weekly special-sits scan.', 'local_first_escalate_for_deal_docs', 'Use for demerger, reverse merger, buyback, open offer, delisting, and arbitrage workflows.'),
    ('Strategy Generator', 'quant', 'Create candidate trading systems from constraints, journals, market regimes, and user ideas.', 'strategy_generation', ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','strategy_spec_writer'], 'write_with_approval', 'active', '{"hypothesis_not_recommendation":true,"evidence_required":true,"backtest_before_alert":true,"paper_first":true}'::jsonb, ARRAY['strategy.generated_ideas','strategy.strategy_candidates','agent.inbox_items'], 'Strategy Generator', 'Creative but disciplined. Produces testable hypotheses, not magical calls.', 'Defines universe, timeframe, signal, risk, invalidation, data requirements, and overfit traps.', ARRAY['hypothesis_testing','regime_awareness','transaction_costs','sample_size','falsifiability'], '{"escalate_to_backtest_engineer_for":["testable candidate"],"escalate_to_model_validation_for":["promising backtest"]}'::jsonb, 'On user strategy idea, trade journal lesson, or market pattern request.', 'local_first_escalate_for_complex_code', 'Use for new strategy ideas and variants.'),
    ('Backtest Engineer', 'quant', 'Run local backtests with explicit data lineage, costs, and reproducible artifacts.', 'strategy_backtest', ARRAY['postgres_read_model','local_python_backtester','component_inventory_reader'], 'write_with_approval', 'active', '{"no_live_execution":true,"transaction_costs_required":true,"data_lineage_required":true}'::jsonb, ARRAY['strategy.backtest_runs','strategy.performance_snapshots','agent.inbox_items'], 'Backtest Engineer', 'Mechanical and suspicious. Does not trust a result until data, assumptions, and costs are clear.', 'Checks lookahead, survivorship, missing data, slippage, brokerage, execution assumptions, and reproducibility.', ARRAY['data_lineage','lookahead_bias','slippage','transaction_costs','reproducibility'], '{"escalate_to_model_validation_for":["completed backtest"],"block_if":["no data lineage","no cost assumption"]}'::jsonb, 'On queued strategy backtest tasks.', 'local_tools_first', 'Use for running strategy tests, not for live trading.'),
    ('Model Validation Agent', 'quant', 'Challenge strategy evidence, backtests, optimizations, leakage, overfit, and robustness.', 'strategy_generation', ARRAY['postgres_read_model','strategy_validation_review','agent_inbox_writer'], 'write_with_approval', 'active', '{"challenge_backtests":true,"transaction_costs_required":true,"no_live_execution":true,"must_record_required_fixes":true}'::jsonb, ARRAY['strategy.validation_reviews','strategy.backtest_runs','agent.inbox_items'], 'Model Validation Agent', 'Adversarial reviewer. Assumes the backtest is wrong until proven otherwise.', 'Stress-tests leakage, degrees of freedom, sample size, regime splits, drawdown, and execution realism.', ARRAY['overfit_detection','walk_forward','cross_validation','regime_split','base_rates'], '{"escalate_to_risk_for":["live activation request"],"block_if":["insufficient sample","unexplained outlier"]}'::jsonb, 'After backtest/optimization results.', 'local_first', 'Use to decide whether a strategy is even worth paper monitoring.'),
    ('Optimizer Agent', 'quant', 'Run parameter search, walk-forward analysis, and robustness checks after baseline evidence.', 'strategy_optimizer', ARRAY['postgres_read_model','local_python_backtester','walk_forward_runner'], 'write_with_approval', 'active', '{"optimize_after_baseline_only":true,"walk_forward_required":true,"overfit_warning_required":true}'::jsonb, ARRAY['strategy.optimization_runs','strategy.validation_reviews','agent.inbox_items'], 'Strategy Optimizer', 'Conservative optimizer. Reduces fragility instead of maximizing headline returns.', 'Uses parameter stability, walk-forward, robustness heatmaps, and simpler-rule preference.', ARRAY['robustness','simplicity','walk_forward','parameter_stability','overfit_penalty'], '{"escalate_to_model_validation_for":["optimization complete"],"block_if":["no baseline strategy"]}'::jsonb, 'Only after a baseline strategy has evidence.', 'local_tools_first', 'Use to improve a given strategy without overfitting it.'),
    ('Trading Desk Agent', 'trading', 'Monitor TradingView, strategy alerts, manual trades, paper trades, and intraday execution checklists.', 'daily_brief', ARRAY['tradingview_signal_reader','postgres_read_model','tradingview_task_queue','trade_ledger_writer'], 'write_with_approval', 'active', '{"no_broker_execution":true,"approval_required_for_live_strategy_enablement":true,"paper_first":true}'::jsonb, ARRAY['trading.signals','strategy.alert_events','trading.trade_activity_ledger','agent.inbox_items'], 'Trading Desk Agent', 'Fast, checklist-based, execution-aware. Records what happened before explaining what it means.', 'Separates signal, setup, trigger, risk, order plan, execution, post-trade review.', ARRAY['pre_mortem','execution_checklist','risk_reward','position_sizing','post_trade_review'], '{"escalate_to_execution_safety_for":["live trade action"],"escalate_to_risk_for":["limit breach"]}'::jsonb, 'Market hours for intraday, end-of-day blotter.', 'local_first', 'Use for manual trades, paper trades, TradingView tasks, and intraday signals.'),
    ('Risk Agent', 'risk', 'Challenge portfolio and strategy risk, enforce approval gates, and prevent bad actions.', 'daily_brief', ARRAY['postgres_read_model','risk_limit_checker','approval_gate_writer'], 'read_only', 'active', '{"approval_required_for_risk_limit_change":true,"challenge_recommendations":true,"human_final_decision":true}'::jsonb, ARRAY['risk.limits','risk.events','agent.approvals','agent.inbox_items'], 'Risk Officer', 'Blunt, conservative, and independent from idea generation.', 'Checks concentration, correlation, liquidity, drawdown, leverage, event risk, and what happens if wrong.', ARRAY['inversion','loss_budget','concentration','liquidity','correlation','tail_risk'], '{"must_review":["live execution","strategy activation","client-facing recommendation"],"can_block":["missing evidence","risk limit breach"]}'::jsonb, 'Before trade/strategy activation and during daily portfolio review.', 'local_first', 'Use for approvals, red flags, and risk challenge.'),
    ('Librarian Agent', 'knowledge', 'Maintain Obsidian graph, Qdrant retrieval quality, research folders, and durable writeback.', 'obsidian_retrieval_summary', ARRAY['obsidian_note_index','obsidian_writeback','qdrant_vector_search','research_folder_writer'], 'write_with_approval', 'active', '{"preserve_vault_structure":true,"writeback_requires_clear_location":true,"no_duplicate_memory":true}'::jsonb, ARRAY['knowledge.obsidian_notes','knowledge.note_links','agent.inbox_items'], 'Knowledge Librarian', 'Organized, strict, and retrieval-focused. Makes outputs findable later.', 'Uses naming conventions, links, tags, summaries, provenance, and duplicate prevention.', ARRAY['information_architecture','retrieval_quality','linking','provenance','compression'], '{"escalate_to_jarvis_for":["unclear write location"],"block_if":["no source evidence for durable claim"]}'::jsonb, 'After every important run/report; scheduled vault index.', 'local_first', 'Use for Obsidian structure, graph hygiene, and memory quality.'),
    ('Data Steward', 'data', 'Own source registry, imports, lineage, data quality, and legacy system reconciliation.', 'jarvis_intake', ARRAY['postgres_read_model','obsidian_writeback','data_quality_checker','source_registry_writer'], 'write_with_approval', 'active', '{"no_raw_client_rows_in_chat":true,"map_before_promote":true,"lineage_required":true}'::jsonb, ARRAY['client_data.source_files','core.data_source_registry','agent.inbox_items'], 'Data Steward', 'Careful, boring in the good way. Refuses analysis until source lineage is clear.', 'Checks source, schema, row count, timestamps, missingness, duplicates, and sensitivity.', ARRAY['lineage','reconciliation','schema_drift','data_quality','privacy'], '{"escalate_to_human_for":["private client import","ambiguous mapping"],"block_if":["unknown source"]}'::jsonb, 'On every import and source connector change.', 'local_first', 'Use for p2cursor/algo imports, broker data, and data checks.'),
    ('Automation Engineer', 'automation', 'Build and monitor browser/MCP/worker automations with approval gates.', 'agent_worker_deterministic', ARRAY['mcp_tool_dispatch','browser_research_runner','agent_worker_dispatch','postgres_read_model'], 'write_with_approval', 'planned', '{"approval_required_for_destructive_browser_action":true,"no_credentials_in_logs":true}'::jsonb, ARRAY['ops.browser_runs','agent.worker_runs','agent.inbox_items'], 'Automation Engineer', 'Systems builder. Automates only after the manual path is clear and auditable.', 'Turns repeated tasks into runbooks, workers, browser adapters, and schedulers.', ARRAY['runbooks','least_privilege','observability','rollback','idempotency'], '{"escalate_to_jarvis_for":["tool failure"],"ask_human_for":["login-required browser task"]}'::jsonb, 'As workflows become repetitive.', 'local_first', 'Use later for scheduled workers, browser agents, and notification routing.')
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    display_title = EXCLUDED.display_title,
    persona = EXCLUDED.persona,
    operating_style = EXCLUDED.operating_style,
    mental_models = EXCLUDED.mental_models,
    escalation_rules = EXCLUDED.escalation_rules,
    daily_cadence = EXCLUDED.daily_cadence,
    cost_policy = EXCLUDED.cost_policy,
    human_interface = EXCLUDED.human_interface,
    updated_at = now();

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
)
VALUES
    ('route_user_request', 'Route User Request', 'orchestration', 'routing', 'executive', 'active', 'worker_or_llm', 'write_with_approval', ARRAY['assign','route','who should handle','make agents work'], ARRAY['agent.chat_turns','agent.profiles','agent.skills'], ARRAY['agent.tasks','agent.inbox_items'], ARRAY['postgres_read_model','agent_worker_dispatch'], 'Routing may create work but must not execute broker actions.', 'Convert the user instruction into bounded specialist tasks with evidence requirements.', '{"default_agent":"Charlie Munger"}'::jsonb),
    ('refresh_dashboard_widget', 'Refresh Dashboard Widget', 'runtime', 'worker', 'runtime', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['refresh widget','update dashboard','monitor this'], ARRAY['ops.dashboard_widgets','agent.tasks'], ARRAY['ops.dashboard_widgets','agent.worker_runs','agent.inbox_items'], ARRAY['postgres_read_model','agent_worker_dispatch'], 'Dashboard summaries must state source tables and stale-data limits.', 'Refresh the widget using live snapshot data and create next action if stale.', '{}'::jsonb),
    ('write_obsidian_note', 'Write Obsidian Note', 'knowledge', 'writeback', 'knowledge', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['write note','save to vault','research folder'], ARRAY['agent.worker_runs','research.ideas','portfolio.holding_theses'], ARRAY['knowledge.obsidian_notes','knowledge.note_links'], ARRAY['obsidian_writeback','obsidian_note_index'], 'Writebacks must include evidence and avoid duplicating notes.', 'Write a durable note with sources, decision status, and next action.', '{}'::jsonb),
    ('portfolio_snapshot_review', 'Portfolio Snapshot Review', 'portfolio', 'analysis', 'portfolio', 'active', 'worker_deterministic', 'read_only', ARRAY['portfolio positions','client holdings','folio review'], ARRAY['portfolio.v_latest_positions','portfolio.v_client_control_plane'], ARRAY['agent.worker_runs','agent.inbox_items','knowledge.obsidian_notes'], ARRAY['portfolio_snapshot_reader','postgres_read_model'], 'No client-facing recommendation without Charlie/Risk review.', 'Review latest positions, top exposures, missing prices, and next action.', '{}'::jsonb),
    ('portfolio_daily_brief', 'Portfolio Daily Brief', 'portfolio', 'brief', 'portfolio', 'active', 'worker_or_llm', 'read_only', ARRAY['daily portfolio brief','morning portfolio','post market portfolio'], ARRAY['portfolio.positions','market.price_quotes','research.ideas'], ARRAY['agent.inbox_items','knowledge.obsidian_notes'], ARRAY['postgres_read_model','qdrant_vector_search'], 'Must separate facts from suggested actions.', 'Produce a client and cross-client portfolio brief.', '{}'::jsonb),
    ('manual_holding_update_review', 'Manual Holding Update Review', 'portfolio', 'data_ops', 'portfolio', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['update holdings','add client','manual holding'], ARRAY['portfolio.manual_holding_updates'], ARRAY['portfolio.positions','agent.inbox_items'], ARRAY['postgres_read_model'], 'Manual holdings must keep lineage and actor.', 'Validate staged holding updates and prepare apply/reject recommendation.', '{}'::jsonb),
    ('company_research_note', 'Company Research Note', 'research', 'research', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['research company','company note','long term thesis'], ARRAY['knowledge.obsidian_notes','research.ideas','portfolio.holding_theses'], ARRAY['knowledge.obsidian_notes','research.ideas'], ARRAY['qdrant_vector_search','postgres_read_model','obsidian_writeback'], 'Must cite source tables/documents; no price-target hype.', 'Write/update a company research note with thesis, risks, catalysts, and open questions.', '{}'::jsonb),
    ('analyze_corporate_filing', 'Analyze Corporate Filing', 'filings', 'document_analysis', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['filing','annual report','results','announcement'], ARRAY['research.corporate_filings','research.filing_events'], ARRAY['research.filing_events','research.ideas','knowledge.obsidian_notes'], ARRAY['document_parser','browser_research_runner','postgres_read_model'], 'Filing source is mandatory; summarize instead of over-quoting.', 'Extract facts, dates, conditions, affected securities, and actionability from a filing.', '{}'::jsonb),
    ('detect_special_situation', 'Detect Special Situation', 'filings', 'event_analysis', 'research', 'active', 'worker_or_llm', 'read_only', ARRAY['demerger','reverse merger','buyback','open offer','delisting','arbitrage'], ARRAY['research.filing_events','market.news_items'], ARRAY['research.ideas','agent.inbox_items'], ARRAY['special_situation_screener','postgres_read_model'], 'Event ideas require downside/risk and PM review.', 'Classify special situation and create an evidence-backed idea/inbox item.', '{}'::jsonb),
    ('nse_bse_announcement_monitor', 'NSE/BSE Announcement Monitor', 'news', 'collector', 'news', 'active', 'collector_planned', 'read_only', ARRAY['nse announcement','bse announcement','exchange filing'], ARRAY['research.feed_registry','core.data_source_checks'], ARRAY['research.corporate_filings','research.filing_events','agent.inbox_items'], ARRAY['browser_research_runner','document_parser'], 'Collector must respect website terms and source URLs.', 'Poll exchange announcements, classify material items, and queue filings analysis.', '{"collector_status":"planned"}'::jsonb),
    ('corporate_action_detector', 'Corporate Action Detector', 'news', 'classification', 'news', 'active', 'worker_or_llm', 'read_only', ARRAY['corporate action','record date','dividend','split','bonus','rights'], ARRAY['research.filing_events','market.news_items'], ARRAY['research.filing_events','agent.inbox_items'], ARRAY['postgres_read_model','filing_event_extractor'], 'Must capture dates and conditions.', 'Detect corporate action type, timeline, and portfolio impact.', '{}'::jsonb),
    ('global_market_news_digest', 'Global Market News Digest', 'news', 'digest', 'news', 'active', 'collector_planned', 'read_only', ARRAY['global news','market news','macro news'], ARRAY['market.news_items','research.feed_registry'], ARRAY['market.news_items','agent.inbox_items'], ARRAY['news_feed_reader','source_credibility_scorer'], 'Must label source reliability and impacted symbols.', 'Curate global/macro news into actionable market context.', '{"collector_status":"planned"}'::jsonb),
    ('twitter_x_watchlist_triage', 'Twitter/X Watchlist Triage', 'news', 'social_monitoring', 'news', 'planned', 'collector_planned', 'read_only', ARRAY['twitter','x watchlist','bookmarks','social'], ARRAY['market.social_items'], ARRAY['market.social_items','agent.inbox_items'], ARRAY['browser_research_runner','source_credibility_scorer'], 'Rumors must be flagged and never treated as filing evidence.', 'Triage social items into rumor, source-backed news, watchlist, or ignore.', '{"requires_login_approval":true}'::jsonb),
    ('news_to_dashboard_alert', 'News To Dashboard Alert', 'news', 'routing', 'news', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['news alert','alert me','monitor news'], ARRAY['market.news_items','research.filing_events'], ARRAY['agent.inbox_items','ops.dashboard_widgets'], ARRAY['postgres_read_model','agent_inbox_writer'], 'Alerts must include source and materiality.', 'Convert material news into inbox/dashboard alerts.', '{}'::jsonb),
    ('strategy_intake_structuring', 'Strategy Intake Structuring', 'quant', 'strategy', 'quant', 'active', 'worker_or_llm', 'write_with_approval', ARRAY['define strategy','new strategy','strategy idea'], ARRAY['agent.chat_turns','trading.trade_journals','knowledge.obsidian_notes'], ARRAY['strategy.strategy_intakes','agent.tasks'], ARRAY['postgres_read_model','obsidian_note_index'], 'No live execution; paper-first.', 'Turn raw strategy text into structured specification and follow-up tasks.', '{}'::jsonb),
    ('generate_strategy_hypothesis', 'Generate Strategy Hypothesis', 'quant', 'strategy', 'quant', 'active', 'worker_or_llm', 'write_with_approval', ARRAY['generate strategy','idea generator','new setup'], ARRAY['strategy.strategy_intakes','trading.trade_journals','market.news_items'], ARRAY['strategy.generated_ideas','strategy.strategy_candidates'], ARRAY['qdrant_vector_search','postgres_read_model'], 'Hypotheses must be testable and falsifiable.', 'Generate strategy candidates with data, rules, and invalidation tests.', '{}'::jsonb),
    ('strategy_lab_review', 'Strategy Lab Review', 'quant', 'analysis', 'quant', 'active', 'worker_deterministic', 'read_only', ARRAY['strategy lab','strategy queue','quant queue'], ARRAY['strategy.v_strategy_registry','strategy.v_strategy_agent_lab'], ARRAY['agent.worker_runs','agent.inbox_items'], ARRAY['postgres_read_model'], 'No activation from review alone.', 'Summarize strategy queue, candidates, backtests, and missing validation.', '{}'::jsonb),
    ('queue_backtest', 'Queue Backtest', 'quant', 'backtest', 'quant', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['backtest','test strategy'], ARRAY['strategy.strategy_candidates','trading.ohlcv'], ARRAY['strategy.backtest_runs','agent.inbox_items'], ARRAY['local_python_backtester','postgres_read_model'], 'Requires data lineage and cost assumptions.', 'Queue or run a reproducible backtest with assumptions.', '{}'::jsonb),
    ('optimize_strategy_parameters', 'Optimize Strategy Parameters', 'quant', 'optimization', 'quant', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['optimize strategy','parameter search','walk forward'], ARRAY['strategy.backtest_runs','strategy.strategy_candidates'], ARRAY['strategy.optimization_runs','strategy.validation_reviews'], ARRAY['local_python_backtester','walk_forward_runner'], 'Must penalize overfit and prefer simple robust ranges.', 'Run parameter search and robustness diagnostics.', '{}'::jsonb),
    ('validate_strategy_model', 'Validate Strategy Model', 'quant', 'validation', 'quant', 'active', 'worker_or_llm', 'write_with_approval', ARRAY['validate strategy','review backtest','overfit'], ARRAY['strategy.backtest_runs','strategy.optimization_runs'], ARRAY['strategy.validation_reviews','agent.inbox_items'], ARRAY['strategy_validation_review','postgres_read_model'], 'Can block activation.', 'Review leakage, overfit, cost assumptions, sample size, and robustness.', '{}'::jsonb),
    ('tradingview_chart_task', 'TradingView Chart Task', 'trading', 'browser_task', 'trading', 'active', 'browser_worker_planned', 'write_with_approval', ARRAY['open chart','tradingview','straddle chart','option chart'], ARRAY['ops.tradingview_tasks','trading.signals'], ARRAY['ops.tradingview_tasks','ops.browser_runs','agent.inbox_items'], ARRAY['tradingview_desktop_controller','browser_research_runner'], 'No broker execution; destructive chart changes need approval.', 'Operate TradingView desktop/browser for chart review and artifacts.', '{"controller_status":"cdp_probe_ready"}'::jsonb),
    ('monitor_strategy_alerts', 'Monitor Strategy Alerts', 'trading', 'monitoring', 'trading', 'active', 'worker_deterministic', 'read_only', ARRAY['signals','alerts','intraday','market monitor'], ARRAY['trading.signals','strategy.alert_events'], ARRAY['agent.worker_runs','agent.inbox_items'], ARRAY['tradingview_signal_reader','postgres_read_model'], 'Alerts are not trades.', 'Summarize active signals, open alerts, and stale strategy monitors.', '{}'::jsonb),
    ('manual_trade_log', 'Manual Trade Log', 'trading', 'ledger', 'trading', 'active', 'write_api', 'write_with_approval', ARRAY['i bought','i sold','log trade','manual trade'], ARRAY['agent.chat_turns'], ARRAY['trading.trade_activity_ledger','portfolio.trades','agent.inbox_items'], ARRAY['trade_ledger_writer','postgres_read_model'], 'Manual trade facts must be captured exactly and reviewed.', 'Record manual trade details and route review.', '{}'::jsonb),
    ('paper_trade_log', 'Paper Trade Log', 'trading', 'ledger', 'trading', 'active', 'write_api', 'write_with_approval', ARRAY['paper trade','system alert trade'], ARRAY['trading.signals','strategy.alert_events'], ARRAY['trading.trade_activity_ledger','strategy.performance_snapshots'], ARRAY['trade_ledger_writer','postgres_read_model'], 'Paper trades must stay separated from actual trades.', 'Record paper trade and attach strategy evidence.', '{}'::jsonb),
    ('trade_journal_learning', 'Trade Journal Learning', 'trading', 'learning', 'trading', 'active', 'worker_or_llm', 'read_only', ARRAY['trade journal','learn from trades','mistakes'], ARRAY['trading.trade_journals','trading.trade_activity_ledger'], ARRAY['strategy.generated_ideas','knowledge.obsidian_notes'], ARRAY['qdrant_vector_search','postgres_read_model'], 'Patterns, not predictions.', 'Extract setups, errors, rule violations, and strategy lessons.', '{}'::jsonb),
    ('risk_gate_review', 'Risk Gate Review', 'risk', 'approval', 'risk', 'active', 'worker_or_llm', 'read_only', ARRAY['risk review','approve strategy','can i trade'], ARRAY['portfolio.positions','strategy.validation_reviews','trading.trade_activity_ledger'], ARRAY['agent.approvals','risk.events','agent.inbox_items'], ARRAY['risk_limit_checker','approval_gate_writer'], 'Can block high-risk actions.', 'Challenge proposed action against limits, evidence, and downside.', '{}'::jsonb),
    ('portfolio_concentration_check', 'Portfolio Concentration Check', 'risk', 'analysis', 'risk', 'active', 'worker_deterministic', 'read_only', ARRAY['concentration','exposure','risk by position'], ARRAY['portfolio.v_latest_positions'], ARRAY['risk.events','agent.worker_runs'], ARRAY['postgres_read_model','risk_limit_checker'], 'Does not recommend trades by itself.', 'Find concentrated exposures, missing prices, and risk flags.', '{}'::jsonb),
    ('source_data_ingestion_review', 'Source Data Ingestion Review', 'data', 'data_quality', 'data', 'active', 'worker_deterministic', 'write_with_approval', ARRAY['ingest data','source data','p2cursor','broker file'], ARRAY['core.data_source_registry','client_data.source_files'], ARRAY['core.import_runs','agent.inbox_items'], ARRAY['data_quality_checker','source_registry_writer'], 'Private client data requires sensitivity and lineage.', 'Review source status, row counts, quality, and next import action.', '{}'::jsonb),
    ('model_runtime_check', 'Model Runtime Check', 'runtime', 'health', 'runtime', 'active', 'worker_deterministic', 'read_only', ARRAY['model status','ollama','runtime health'], ARRAY['agent.model_routes','agent.tool_registry'], ARRAY['agent.worker_runs','agent.inbox_items'], ARRAY['postgres_read_model'], 'Do not change model routes without approval.', 'Summarize model routes, enabled tools, and runtime gaps.', '{}'::jsonb),
    ('daily_office_brief', 'Daily Office Brief', 'orchestration', 'brief', 'executive', 'active', 'worker_or_llm', 'read_only', ARRAY['daily brief','office brief','what changed'], ARRAY['portfolio.positions','trading.signals','market.news_items','agent.inbox_items'], ARRAY['knowledge.obsidian_notes','agent.inbox_items'], ARRAY['postgres_read_model','qdrant_vector_search','obsidian_writeback'], 'Must include uncertainty and next actions.', 'Create the AI office daily brief across departments.', '{}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name = EXCLUDED.skill_name,
    skill_family = EXCLUDED.skill_family,
    skill_type = EXCLUDED.skill_type,
    owner_department = EXCLUDED.owner_department,
    status = EXCLUDED.status,
    execution_mode = EXCLUDED.execution_mode,
    permission_level = EXCLUDED.permission_level,
    trigger_phrases = EXCLUDED.trigger_phrases,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    required_tools = EXCLUDED.required_tools,
    risk_notes = EXCLUDED.risk_notes,
    prompt_template = EXCLUDED.prompt_template,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Charlie Munger','route_user_request','expert',true,'{"default_for":"ambiguous decision and cross-agent routing"}'::jsonb),
    ('Charlie Munger','daily_office_brief','expert',true,'{"default_for":"daily brief and decision review"}'::jsonb),
    ('Charlie Munger','risk_gate_review','working',false,'{"uses":"force inversion before action"}'::jsonb),
    ('Jarvis','refresh_dashboard_widget','expert',true,'{"default_for":"dashboard widget jobs"}'::jsonb),
    ('Jarvis','route_user_request','expert',true,'{"uses":"create tasks and dispatch worker"}'::jsonb),
    ('Jarvis','model_runtime_check','expert',true,'{"default_for":"runtime status widget"}'::jsonb),
    ('Jarvis','write_obsidian_note','working',false,'{"uses":"approved writebacks"}'::jsonb),
    ('Portfolio Manager','portfolio_snapshot_review','expert',true,'{"widget_key":"portfolio_latest_positions"}'::jsonb),
    ('Portfolio Manager','portfolio_daily_brief','expert',true,'{"workspace":"portfolio"}'::jsonb),
    ('Portfolio Manager','manual_holding_update_review','working',false,'{"source":"manual holding queue"}'::jsonb),
    ('Research Analyst','company_research_note','expert',true,'{"workspace":"research"}'::jsonb),
    ('Research Analyst','analyze_corporate_filing','working',false,'{"uses":"filings analyst output"}'::jsonb),
    ('News Analyst','nse_bse_announcement_monitor','expert',true,'{"source":"exchange announcements"}'::jsonb),
    ('News Analyst','global_market_news_digest','expert',true,'{"source":"news feeds"}'::jsonb),
    ('News Analyst','twitter_x_watchlist_triage','working',false,'{"source":"social watchlist"}'::jsonb),
    ('News Analyst','news_to_dashboard_alert','expert',true,'{"output":"agent inbox"}'::jsonb),
    ('Filings Analyst','analyze_corporate_filing','expert',true,'{"source":"filing/document"}'::jsonb),
    ('Filings Analyst','corporate_action_detector','expert',true,'{"source":"filing event"}'::jsonb),
    ('Special Situations Agent','detect_special_situation','expert',true,'{"event_types":["demerger","merger","buyback","open_offer","delisting"]}'::jsonb),
    ('Special Situations Agent','analyze_corporate_filing','working',false,'{"uses":"for event facts"}'::jsonb),
    ('Strategy Generator','generate_strategy_hypothesis','expert',true,'{"source":"strategy idea or trade journal"}'::jsonb),
    ('Strategy Generator','strategy_intake_structuring','expert',true,'{"source":"user strategy instruction"}'::jsonb),
    ('Strategy Generator','strategy_lab_review','expert',true,'{"widget_key":"strategy_lab_queue"}'::jsonb),
    ('Strategy Intake Agent','strategy_intake_structuring','expert',true,'{"source":"user strategy instruction"}'::jsonb),
    ('Strategy Research Agent','generate_strategy_hypothesis','expert',true,'{"source":"research and journals"}'::jsonb),
    ('Backtest Engineer','queue_backtest','expert',true,'{"source":"strategy candidate"}'::jsonb),
    ('Backtest Engineer','strategy_lab_review','working',false,'{"uses":"queue review"}'::jsonb),
    ('Optimizer Agent','optimize_strategy_parameters','expert',true,'{"after":"baseline backtest"}'::jsonb),
    ('Model Validation Agent','validate_strategy_model','expert',true,'{"after":"backtest or optimization"}'::jsonb),
    ('Trading Desk Agent','monitor_strategy_alerts','expert',true,'{"widget_key":"market_signal_monitor"}'::jsonb),
    ('Trading Desk Agent','tradingview_chart_task','expert',true,'{"source":"ops.tradingview_tasks"}'::jsonb),
    ('Trading Desk Agent','manual_trade_log','expert',true,'{"source":"user manual trade"}'::jsonb),
    ('Trading Desk Agent','paper_trade_log','expert',true,'{"source":"system alert"}'::jsonb),
    ('Trade Journal Learning Agent','trade_journal_learning','expert',true,'{"source":"trade journals"}'::jsonb),
    ('Risk Agent','risk_gate_review','expert',true,'{"default_for":"approval and risk challenge"}'::jsonb),
    ('Risk Agent','portfolio_concentration_check','expert',true,'{"source":"portfolio positions"}'::jsonb),
    ('Execution Safety Agent','risk_gate_review','expert',true,'{"scope":"execution safety"}'::jsonb),
    ('Data Steward','source_data_ingestion_review','expert',true,'{"source":"data registry and imports"}'::jsonb),
    ('Data Steward','model_runtime_check','working',false,'{"uses":"runtime data quality"}'::jsonb),
    ('Librarian Agent','write_obsidian_note','expert',true,'{"default_for":"vault writeback"}'::jsonb),
    ('Librarian Agent','company_research_note','working',false,'{"uses":"folder maintenance"}'::jsonb),
    ('Browser Research Runner','nse_bse_announcement_monitor','working',false,'{"executor":"browser"}'::jsonb),
    ('Browser Research Runner','global_market_news_digest','working',false,'{"executor":"browser"}'::jsonb),
    ('Automation Engineer','refresh_dashboard_widget','working',false,'{"future":"scheduled worker daemon"}'::jsonb),
    ('Automation Engineer','tradingview_chart_task','working',false,'{"future":"browser executor"}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('agent_worker_run_once', 'agent_worker', 'Jarvis', 'write_with_approval', true, 'Claims queued dashboard-linked agent jobs, runs deterministic specialist summaries, writes Obsidian notes, and updates task/widget state.', '{"script":"_ai_os_runtime/scripts/run_agent_worker_once.py","writes":["agent.worker_runs","agent.tasks","agent.inbox_items","ops.dashboard_widgets","knowledge.obsidian_notes"],"execution_allowed":false}'::jsonb),
    ('agent_skill_matrix', 'read_model', 'Jarvis', 'read_only', true, 'Read agent skills, ownership, execution modes, and guardrails.', '{"view":"agent.v_agent_skill_matrix"}'::jsonb),
    ('news_skill_stack', 'read_model', 'News Analyst', 'read_only', true, 'Read the planned and active news/filing/social monitoring skills.', '{"view":"agent.v_news_skill_stack"}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES
    ('agent_worker_dashboard_jobs', 'Agent Worker - Dashboard Jobs', 'agent_execution', 'Jarvis', 'manual_or_scheduled', 'active', 'write_with_approval', ARRAY['agent.v_live_agent_worker_queue','ops.dashboard_widgets','agent.tasks']::TEXT[], ARRAY['agent.worker_runs','agent.inbox_items','knowledge.obsidian_notes','ops.dashboard_widgets']::TEXT[], true, 'manual now; later every 5-15 minutes via launchd', 'First live worker loop. It runs deterministic evidence-backed summaries before adding model-heavy reasoning.', '{"script":"_ai_os_runtime/scripts/run_agent_worker_once.py","api_route":"/api/agents/worker/run"}'::jsonb),
    ('news_intelligence_stack', 'News Intelligence Stack', 'news_monitoring', 'News Analyst', 'scheduled', 'mapped', 'read_only', ARRAY['research.feed_registry','market.news_items','market.social_items','research.corporate_filings']::TEXT[], ARRAY['research.filing_events','agent.inbox_items','ops.dashboard_widgets']::TEXT[], true, 'manual now; scheduled collectors after source review', 'Skill map for NSE/BSE filings, global news, social watchlists, corporate actions, and special situations.', '{"skills":["nse_bse_announcement_monitor","corporate_action_detector","global_market_news_digest","twitter_x_watchlist_triage","news_to_dashboard_alert"]}'::jsonb)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

CREATE OR REPLACE VIEW agent.v_active_agents AS
SELECT
    p.agent_name,
    p.department,
    p.role_scope,
    p.default_model_route,
    p.default_tools,
    p.permission_level,
    p.output_targets,
    p.guardrails,
    coalesce(d.department_name, initcap(p.department)) AS department_name,
    p.display_title,
    p.persona,
    p.operating_style,
    p.mental_models,
    p.escalation_rules,
    p.daily_cadence,
    p.cost_policy,
    p.human_interface,
    coalesce(skill_counts.skill_count, 0) AS skill_count,
    coalesce(skill_counts.primary_skills, '{}') AS primary_skills,
    last_run.finished_at AS latest_worker_finished_at,
    last_run.status AS latest_worker_status
FROM agent.profiles p
LEFT JOIN agent.department_registry d ON d.department_key = p.department
LEFT JOIN LATERAL (
    SELECT
        count(*)::INT AS skill_count,
        array_agg(m.skill_key ORDER BY m.skill_key) FILTER (WHERE m.is_primary) AS primary_skills
    FROM agent.agent_skill_map m
    JOIN agent.skills s ON s.skill_key = m.skill_key
    WHERE m.agent_name = p.agent_name
      AND s.status IN ('active','planned')
) skill_counts ON true
LEFT JOIN LATERAL (
    SELECT wr.finished_at, wr.status
    FROM agent.worker_runs wr
    WHERE wr.agent_name = p.agent_name
    ORDER BY wr.created_at DESC
    LIMIT 1
) last_run ON true
WHERE p.status = 'active'
ORDER BY
    CASE p.agent_name WHEN 'Charlie Munger' THEN 1 WHEN 'Jarvis' THEN 2 ELSE 3 END,
    p.department,
    p.agent_name;

CREATE OR REPLACE VIEW agent.v_agent_departments AS
SELECT
    d.department_key,
    d.department_name,
    d.mission,
    d.lead_agent,
    d.status,
    d.priority,
    d.core_workflows,
    d.required_next_builds,
    d.guardrails,
    count(p.id) FILTER (WHERE p.status = 'active') AS active_agents,
    count(s.id) FILTER (WHERE s.status = 'active') AS active_skills,
    d.updated_at
FROM agent.department_registry d
LEFT JOIN agent.profiles p ON p.department = d.department_key
LEFT JOIN agent.skills s ON s.owner_department = d.department_key
GROUP BY d.department_key
ORDER BY
    CASE d.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    d.department_name;

CREATE OR REPLACE VIEW agent.v_agent_skill_matrix AS
SELECT
    s.skill_key,
    s.skill_name,
    s.skill_family,
    s.skill_type,
    s.owner_department,
    coalesce(d.department_name, initcap(s.owner_department)) AS owner_department_name,
    s.status,
    s.execution_mode,
    s.permission_level,
    s.trigger_phrases,
    s.input_sources,
    s.output_targets,
    s.required_tools,
    s.risk_notes,
    coalesce(array_agg(m.agent_name ORDER BY m.is_primary DESC, m.agent_name) FILTER (WHERE m.agent_name IS NOT NULL), '{}') AS assigned_agents,
    coalesce(array_agg(m.agent_name ORDER BY m.agent_name) FILTER (WHERE m.is_primary), '{}') AS primary_agents,
    s.updated_at
FROM agent.skills s
LEFT JOIN agent.department_registry d ON d.department_key = s.owner_department
LEFT JOIN agent.agent_skill_map m ON m.skill_key = s.skill_key
GROUP BY s.id, d.department_name
ORDER BY
    CASE s.status WHEN 'active' THEN 1 WHEN 'planned' THEN 2 ELSE 3 END,
    s.skill_family,
    s.skill_key;

CREATE OR REPLACE VIEW agent.v_news_skill_stack AS
SELECT *
FROM agent.v_agent_skill_matrix
WHERE skill_family IN ('news','filings')
   OR skill_key IN ('analyze_corporate_filing','detect_special_situation','news_to_dashboard_alert')
ORDER BY
    CASE status WHEN 'active' THEN 1 WHEN 'planned' THEN 2 ELSE 3 END,
    skill_family,
    skill_key;

CREATE OR REPLACE VIEW agent.v_live_agent_worker_queue AS
SELECT
    j.task_id,
    j.title,
    j.objective,
    j.owner_agent,
    j.status AS task_status,
    j.priority,
    j.source_kind,
    j.source_ref,
    j.output_note_path,
    j.widget_id,
    j.widget_key,
    j.widget_title,
    j.workspace,
    j.widget_type,
    CASE
        WHEN j.widget_key = 'portfolio_latest_positions' THEN 'portfolio_snapshot_review'
        WHEN j.widget_key = 'market_signal_monitor' THEN 'monitor_strategy_alerts'
        WHEN j.widget_key = 'strategy_lab_queue' THEN 'strategy_lab_review'
        WHEN j.widget_key = 'research_filings_inbox' THEN 'analyze_corporate_filing'
        WHEN j.widget_key = 'model_runtime_status' THEN 'model_runtime_check'
        WHEN j.widget_key = 'command_daily_brief' THEN 'daily_office_brief'
        ELSE 'refresh_dashboard_widget'
    END AS suggested_skill_key,
    s.skill_name AS suggested_skill_name,
    s.skill_family AS suggested_skill_family,
    s.execution_mode AS suggested_execution_mode,
    last_run.id AS latest_worker_run_id,
    last_run.status AS latest_worker_status,
    last_run.finished_at AS latest_worker_finished_at,
    last_run.output_note_path AS latest_output_note_path,
    j.inbox_item_id,
    j.inbox_status,
    j.created_at,
    j.updated_at
FROM agent.v_dashboard_agent_jobs j
LEFT JOIN agent.skills s ON s.skill_key = CASE
        WHEN j.widget_key = 'portfolio_latest_positions' THEN 'portfolio_snapshot_review'
        WHEN j.widget_key = 'market_signal_monitor' THEN 'monitor_strategy_alerts'
        WHEN j.widget_key = 'strategy_lab_queue' THEN 'strategy_lab_review'
        WHEN j.widget_key = 'research_filings_inbox' THEN 'analyze_corporate_filing'
        WHEN j.widget_key = 'model_runtime_status' THEN 'model_runtime_check'
        WHEN j.widget_key = 'command_daily_brief' THEN 'daily_office_brief'
        ELSE 'refresh_dashboard_widget'
    END
LEFT JOIN LATERAL (
    SELECT wr.*
    FROM agent.worker_runs wr
    WHERE wr.task_id = j.task_id
    ORDER BY wr.created_at DESC
    LIMIT 1
) last_run ON true
ORDER BY
    CASE j.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE j.status WHEN 'queued' THEN 1 WHEN 'in_progress' THEN 2 WHEN 'needs_review' THEN 3 WHEN 'completed' THEN 4 ELSE 5 END,
    j.updated_at DESC;

CREATE OR REPLACE VIEW agent.v_recent_worker_runs AS
SELECT
    wr.id,
    wr.task_id,
    t.title AS task_title,
    wr.widget_id,
    w.widget_key,
    w.widget_title,
    wr.agent_name,
    p.display_title,
    p.department,
    wr.skill_key,
    s.skill_name,
    s.skill_family,
    wr.run_mode,
    wr.status,
    wr.output_summary,
    wr.output_note_path,
    wr.evidence,
    wr.started_at,
    wr.finished_at,
    wr.created_at,
    wr.updated_at
FROM agent.worker_runs wr
LEFT JOIN agent.tasks t ON t.id = wr.task_id
LEFT JOIN ops.dashboard_widgets w ON w.id = wr.widget_id
LEFT JOIN agent.profiles p ON p.agent_name = wr.agent_name
LEFT JOIN agent.skills s ON s.skill_key = wr.skill_key
ORDER BY wr.created_at DESC;
