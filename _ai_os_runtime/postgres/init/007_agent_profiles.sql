CREATE TABLE IF NOT EXISTS agent.profiles (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    role_scope TEXT NOT NULL,
    default_model_route TEXT REFERENCES agent.model_routes(route_name),
    default_tools TEXT[] NOT NULL DEFAULT '{}',
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    status TEXT NOT NULL DEFAULT 'active',
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_targets TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_profiles_department ON agent.profiles (department);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_status ON agent.profiles (status);

INSERT INTO agent.model_routes (
    route_name,
    task_class,
    default_provider,
    default_model,
    escalation_provider,
    escalation_model,
    max_cost_tier,
    notes,
    enabled
)
VALUES
    (
        'obsidian_retrieval_summary',
        'retrieval_summary',
        'ollama',
        'qwen3:8b',
        'cloud_optional',
        '',
        'local',
        'Summarize retrieved Obsidian notes and linked records with local-first routing.',
        true
    ),
    (
        'news_curation',
        'monitoring',
        'ollama',
        'qwen3:8b',
        'cloud_optional',
        '',
        'local',
        'Curate news/social items and create evidence-backed inbox items.',
        true
    ),
    (
        'strategy_generation',
        'quant_research',
        'ollama',
        'qwen3:14b',
        'codex_or_cloud',
        '',
        'hybrid',
        'Generate strategy hypotheses and backtest requests; escalate for implementation and hard validation.',
        true
    )
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
    agent_name,
    department,
    role_scope,
    default_model_route,
    default_tools,
    permission_level,
    status,
    guardrails,
    output_targets
)
VALUES
    (
        'Jarvis',
        'orchestration',
        'Route user work, retrieve context, choose specialist agents, manage approvals, and write durable outputs.',
        'jarvis_intake',
        ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index','obsidian_writeback'],
        'write_with_approval',
        'active',
        '{"must_route_specialist_work":true,"must_require_evidence":true,"no_live_trade_without_approval":true}'::jsonb,
        ARRAY['agent.tasks','agent.inbox_items','knowledge.obsidian_notes']
    ),
    (
        'Data Steward',
        'data',
        'Own source registry, imports, lineage, data quality, p2cursor mapping, and safe client-data views.',
        'jarvis_intake',
        ARRAY['postgres_read_model','obsidian_writeback'],
        'write_with_approval',
        'active',
        '{"no_raw_client_rows_in_chat":true,"map_before_promote":true,"lineage_required":true}'::jsonb,
        ARRAY['client_data.source_files','client_data.p2cursor_csv_rows','agent.tasks']
    ),
    (
        'Portfolio Manager',
        'portfolio',
        'Review client folios, positions, allocation drift, holding theses, and portfolio-level decisions.',
        'daily_brief',
        ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index'],
        'read_only',
        'active',
        '{"client_private":true,"separate_fact_assumption_recommendation":true}'::jsonb,
        ARRAY['portfolio.clients','portfolio.positions','research.ideas','agent.inbox_items']
    ),
    (
        'Risk Agent',
        'portfolio',
        'Monitor concentration, drawdown, liquidity, leverage, live execution gates, and approval risks.',
        'daily_brief',
        ARRAY['postgres_read_model','qdrant_vector_search'],
        'read_only',
        'active',
        '{"approval_required_for_risk_limit_change":true,"challenge_recommendations":true}'::jsonb,
        ARRAY['risk.limits','risk.events','agent.approvals']
    ),
    (
        'News Analyst',
        'research',
        'Curate global news, tag symbols/topics, score relevance, and create research inbox items.',
        'news_curation',
        ARRAY['browser_research_runner','postgres_read_model','qdrant_vector_search'],
        'read_only',
        'active',
        '{"public_sources_only_by_default":true,"source_url_required":true}'::jsonb,
        ARRAY['market.news_items','agent.inbox_items']
    ),
    (
        'Filings Analyst',
        'research',
        'Capture and analyze NSE/BSE/SEC filings, announcements, results, and corporate actions.',
        'filing_analysis',
        ARRAY['browser_research_runner','postgres_read_model','qdrant_vector_search'],
        'read_only',
        'active',
        '{"source_url_required":true,"file_before_opinion":true}'::jsonb,
        ARRAY['research.corporate_filings','research.filing_events']
    ),
    (
        'Special Situations Agent',
        'research',
        'Find arbitrage, demerger, reverse merger, buyback, delisting, restructuring, and event-driven ideas.',
        'filing_analysis',
        ARRAY['postgres_read_model','qdrant_vector_search','browser_research_runner'],
        'read_only',
        'active',
        '{"evidence_required":true,"risk_score_required":true,"no_trade_recommendation_without_pm_review":true}'::jsonb,
        ARRAY['research.ideas','research.filing_events','agent.inbox_items']
    ),
    (
        'Trade Journal Learning Agent',
        'trading',
        'Extract setup patterns, mistakes, rule violations, emotional states, and strategy lessons from trade history.',
        'trade_journal_learning',
        ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index'],
        'read_only',
        'active',
        '{"private_trading_data":true,"patterns_not_predictions":true}'::jsonb,
        ARRAY['trading.trade_journals','strategy.strategy_candidates']
    ),
    (
        'Trading Desk Agent',
        'trading',
        'Monitor TradingView signals, live strategy state, alerts, and trade explanations.',
        'daily_brief',
        ARRAY['tradingview_signal_reader','postgres_read_model'],
        'read_only',
        'active',
        '{"no_broker_execution":true,"approval_required_for_live_strategy_enablement":true}'::jsonb,
        ARRAY['trading.signals','strategy.alert_events','agent.inbox_items']
    ),
    (
        'Execution Safety Agent',
        'trading',
        'Enforce paper-first mode, live trading approvals, risk limits, and broker-action safety.',
        'daily_brief',
        ARRAY['postgres_read_model'],
        'read_only',
        'active',
        '{"live_execution_enabled":false,"approval_required_for_trade_action":true}'::jsonb,
        ARRAY['risk.limits','agent.approvals']
    ),
    (
        'Strategy Research Agent',
        'quant',
        'Turn ideas into formal strategy hypotheses, backtest requests, alpha library entries, and diagnostics.',
        'strategy_generation',
        ARRAY['postgres_read_model','qdrant_vector_search','obsidian_note_index'],
        'read_only',
        'active',
        '{"no_live_execution":true,"backtest_before_alert":true,"lookahead_checks_required":true}'::jsonb,
        ARRAY['strategy.strategy_candidates','strategy.backtest_runs']
    ),
    (
        'Model Validation Agent',
        'quant',
        'Review sample size, overfit, leakage, regime dependence, transaction cost assumptions, and robustness.',
        'strategy_generation',
        ARRAY['postgres_read_model'],
        'read_only',
        'active',
        '{"challenge_backtests":true,"transaction_costs_required":true}'::jsonb,
        ARRAY['strategy.backtest_runs','agent.inbox_items']
    ),
    (
        'Browser Research Runner',
        'data',
        'Run public-source browser collection jobs and save artifacts/screenshots with source lineage.',
        'news_curation',
        ARRAY['browser_research_runner','postgres_read_model'],
        'read_only',
        'active',
        '{"no_login_without_approval":true,"no_posting":true,"public_sources_only_by_default":true}'::jsonb,
        ARRAY['ops.browser_runs','core.raw_artifacts']
    ),
    (
        'Librarian Agent',
        'executive',
        'Index Obsidian notes, maintain links/tags, prevent duplicate memory, and write approved outputs back.',
        'obsidian_retrieval_summary',
        ARRAY['obsidian_note_index','obsidian_writeback','qdrant_vector_search'],
        'write_with_approval',
        'active',
        '{"preserve_vault_structure":true,"writeback_requires_clear_location":true}'::jsonb,
        ARRAY['knowledge.obsidian_notes','knowledge.note_links']
    )
ON CONFLICT (agent_name) DO UPDATE SET
    department = EXCLUDED.department,
    role_scope = EXCLUDED.role_scope,
    default_model_route = EXCLUDED.default_model_route,
    default_tools = EXCLUDED.default_tools,
    permission_level = EXCLUDED.permission_level,
    status = EXCLUDED.status,
    guardrails = EXCLUDED.guardrails,
    output_targets = EXCLUDED.output_targets,
    updated_at = now();
