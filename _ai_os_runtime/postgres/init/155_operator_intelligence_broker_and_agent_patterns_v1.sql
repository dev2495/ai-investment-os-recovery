BEGIN;

CREATE TABLE IF NOT EXISTS research.watchlists (
    id BIGSERIAL PRIMARY KEY,
    watchlist_key TEXT NOT NULL UNIQUE,
    watchlist_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    owner_agent TEXT NOT NULL DEFAULT 'Research Director',
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research.watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    watchlist_id BIGINT NOT NULL REFERENCES research.watchlists(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    company_name TEXT,
    item_type TEXT NOT NULL DEFAULT 'research',
    status TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'medium',
    thesis TEXT,
    catalyst TEXT,
    invalidation TEXT,
    review_on DATE,
    owner_agent TEXT NOT NULL DEFAULT 'Company Analyst',
    source_kind TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (watchlist_id, exchange, symbol, item_type)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_items_active
    ON research.watchlist_items (status, priority, updated_at DESC);

CREATE OR REPLACE VIEW research.v_watchlist_board AS
SELECT item.id, list.watchlist_key, list.watchlist_name, list.purpose,
       item.symbol, item.exchange, item.company_name, item.item_type,
       item.status, item.priority, item.thesis, item.catalyst,
       item.invalidation, item.review_on, item.owner_agent,
       item.source_kind, item.source_ref, item.created_by,
       item.evidence, item.metadata, item.created_at, item.updated_at
FROM research.watchlist_items item
JOIN research.watchlists list ON list.id=item.watchlist_id
WHERE list.status='active'
ORDER BY CASE item.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
         item.review_on NULLS LAST, item.updated_at DESC;

CREATE TABLE IF NOT EXISTS trading.option_chain_snapshots (
    id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    provider TEXT NOT NULL,
    source_connector_key TEXT NOT NULL,
    exchange TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry DATE NOT NULL,
    strike NUMERIC NOT NULL,
    option_type TEXT NOT NULL CHECK (option_type IN ('CE','PE')),
    instrument_token TEXT,
    trading_symbol TEXT NOT NULL,
    spot_price NUMERIC,
    last_price NUMERIC,
    bid_price NUMERIC,
    ask_price NUMERIC,
    volume NUMERIC,
    open_interest NUMERIC,
    implied_volatility NUMERIC,
    delta NUMERIC,
    gamma NUMERIC,
    theta NUMERIC,
    vega NUMERIC,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_hash TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, observed_at, exchange, underlying, expiry, strike, option_type)
);

CREATE INDEX IF NOT EXISTS idx_option_chain_latest
    ON trading.option_chain_snapshots (underlying, expiry, observed_at DESC);

CREATE OR REPLACE VIEW trading.v_latest_option_chain AS
WITH latest AS (
    SELECT provider, exchange, underlying, expiry, max(observed_at) AS observed_at
    FROM trading.option_chain_snapshots
    GROUP BY provider, exchange, underlying, expiry
)
SELECT chain.*
FROM trading.option_chain_snapshots chain
JOIN latest USING(provider, exchange, underlying, expiry, observed_at)
ORDER BY chain.underlying, chain.expiry, chain.strike, chain.option_type;

CREATE OR REPLACE VIEW trading.v_options_surface_summary AS
SELECT provider, exchange, underlying, expiry, observed_at,
       count(*) AS contract_count,
       count(*) FILTER (WHERE option_type='CE') AS call_count,
       count(*) FILTER (WHERE option_type='PE') AS put_count,
       min(strike) AS min_strike, max(strike) AS max_strike,
       max(spot_price) AS spot_price,
       sum(open_interest) FILTER (WHERE option_type='CE') AS call_open_interest,
       sum(open_interest) FILTER (WHERE option_type='PE') AS put_open_interest,
       avg(implied_volatility) AS average_iv,
       false AS broker_write_allowed
FROM trading.v_latest_option_chain
GROUP BY provider, exchange, underlying, expiry, observed_at
ORDER BY observed_at DESC, underlying, expiry;

INSERT INTO ops.report_schedules (
    report_key, report_name, report_family, cadence, owner_agent, skill_key,
    target_folder, approval_required, enabled, source_views, description, config
) VALUES (
    'daily_investment_letter', 'Daily Investment Office Letter', 'daily_letter', 'daily',
    'Charlie Munger', 'daily_office_brief', 'ai memory/00 AI OS/Briefs/Daily',
    false, true,
    ARRAY['portfolio.v_portfolio_intelligence_v2','research.v_corporate_filing_inbox','market.news_items','research.v_watchlist_board','strategy.v_open_alerts','risk.v_portfolio_risk_limit_checks'],
    'One source-backed morning letter covering portfolios, watchlists, filings, news, ideas, strategies, options readiness, risk, and decisions requiring attention.',
    '{"run_after_local":"08:20","capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (report_key) DO UPDATE SET
    report_name=EXCLUDED.report_name, report_family=EXCLUDED.report_family,
    cadence=EXCLUDED.cadence, owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key, target_folder=EXCLUDED.target_folder,
    approval_required=EXCLUDED.approval_required, enabled=EXCLUDED.enabled,
    source_views=EXCLUDED.source_views, description=EXCLUDED.description,
    config=EXCLUDED.config, updated_at=now();

UPDATE core.data_source_registry
SET connection_mode='api_read_only', freshness_target_minutes=5,
    owner_agent='Portfolio Manager',
    notes='Primary broker adapter for read-only holdings, positions, orders, trades, funds, quotes, instruments, derivatives, and MCX. Daily interactive login is required by Zerodha; broker writes remain disabled.',
    metadata=metadata || '{"primary_broker_adapter":true,"execution_allowed":false,"credential_state":"required","datasets":["holdings","positions","orders","trades","funds"],"market_scope":["NSE","BSE","NFO","BFO","MCX"],"manual_daily_login_required":true}'::jsonb,
    updated_at=now()
WHERE source_key='zerodha_live';

UPDATE core.data_source_registry
SET notes='Optional secondary read-only broker source. Zerodha is primary because the operator already has an account.',
    metadata=metadata || '{"primary_broker_adapter":false,"execution_allowed":false}'::jsonb,
    updated_at=now()
WHERE source_key='dhan_live';

UPDATE core.source_connector_profiles
SET connector_type='broker_api_read_only', access_mode='read_only',
    freshness_target_minutes=5, requires_api_key=true,
    requires_browser_session=true, base_url='https://api.kite.trade',
    health_status=CASE WHEN secret_ref IS NULL THEN 'needs_secret' ELSE health_status END,
    last_error=CASE WHEN secret_ref IS NULL THEN 'Set the Zerodha API key and secret in the protected iMac environment, then complete the daily interactive login.' ELSE last_error END,
    notes='Primary GET-only Zerodha adapter. Login is interactive once daily; password or TOTP automation is intentionally prohibited. Order endpoints are absent.',
    config='{"datasets":["holdings","positions","orders","trades","funds"],"execution_allowed":false,"manual_daily_login_required":true,"secret_env_refs":["AI_OS_ZERODHA_API_KEY","AI_OS_ZERODHA_API_SECRET"],"access_token_keychain_service":"ai-os-zerodha-access-token"}'::jsonb,
    updated_at=now()
WHERE connector_key='zerodha_live_connector';

ALTER TABLE core.integration_jobs DROP CONSTRAINT IF EXISTS integration_jobs_executor_allowlist;
ALTER TABLE core.integration_jobs ADD CONSTRAINT integration_jobs_executor_allowlist CHECK (
    executor_key IN ('market_news_ingestion','filings_collection','tick_ohlcv_aggregation',
        'tradingview_quote_refresh','public_source_check','provider_readiness',
        'legacy_market_data_ingestion','dhan_read_sync','zerodha_read_sync')
);

INSERT INTO core.integration_jobs (
    job_key, plugin_key, job_name, job_type, executor_key, schedule_cron,
    timezone, enabled, run_mode, overlap_policy, timeout_seconds, parameters,
    approval_required, owner_agent, notes
) VALUES (
    'zerodha_read_snapshot_5m', 'data_source:zerodha_live_connector',
    'Zerodha read-only account snapshot', 'poll', 'zerodha_read_sync', '*/5 * * * 1-5',
    'Asia/Kolkata', false, 'manual_or_schedule', 'skip', 120,
    '{"datasets":["holdings","positions","orders","trades","funds"],"broker_write_allowed":false}'::jsonb,
    false, 'Data Engineering Agent',
    'Enable only after API credentials and the current daily access token pass a live GET-only health check.'
)
ON CONFLICT (job_key) DO UPDATE SET
    plugin_key=EXCLUDED.plugin_key, executor_key=EXCLUDED.executor_key,
    schedule_cron=EXCLUDED.schedule_cron, enabled=false,
    parameters=EXCLUDED.parameters, notes=EXCLUDED.notes, updated_at=now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES
    ('openrouter_research_fast','public_research_summary','openrouter','z-ai/glm-4.7-flash',NULL,NULL,'cloud_low','Explicit public/internal research only; ZDR and monthly cap required.',true),
    ('openrouter_research_deep','deep_research_synthesis','openrouter','minimax/minimax-m3','openrouter','z-ai/glm-5.2','cloud_medium','Explicit public/internal deep research only; ZDR and monthly cap required.',true),
    ('openrouter_research_review','independent_research_review','openrouter','moonshotai/kimi-k2.6',NULL,NULL,'cloud_medium','Explicit public/internal second opinion only; ZDR and monthly cap required.',true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class, default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model, escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model, max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes, enabled=true;

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, cost_tier, capabilities,
    requires_api_key, secret_ref, health_status, owner_agent, notes, config
) VALUES
    ('openrouter_glm_4_7_flash', 'OpenRouter GLM 4.7 Flash economical research', 'openrouter',
     'z-ai/glm-4.7-flash', 'openrouter_research_fast', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_explicit_request', 'configured', 200000,
     'cloud_low', ARRAY['text','structured_outputs','research_summary'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Cheapest approved public/internal research candidate. Client-private prompts are blocked.',
     '{"budget_inr_monthly":500,"approval_required":true,"zdr_required":true,"raw_prompt_storage":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_minimax_m3', 'OpenRouter MiniMax M3 research synthesis', 'openrouter',
     'minimax/minimax-m3', 'openrouter_research_deep', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_explicit_request', 'configured', 1048576,
     'cloud_medium', ARRAY['text','structured_outputs','long_context','research_synthesis'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Deep public/internal research candidate. Client-private prompts are blocked.',
     '{"budget_inr_monthly":1250,"approval_required":true,"zdr_required":true,"raw_prompt_storage":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_kimi_k2_6', 'OpenRouter Kimi K2.6 independent research review', 'openrouter',
     'moonshotai/kimi-k2.6', 'openrouter_research_review', 'cloud_api',
     'https://openrouter.ai/api/v1', 'cloud_on_explicit_request', 'configured', 262144,
     'cloud_medium', ARRAY['text','structured_outputs','independent_review'], true, NULL,
     'needs_secret', 'AI Runtime Engineer',
     'Independent public/internal research review candidate. Client-private prompts are blocked.',
     '{"budget_inr_monthly":750,"approval_required":true,"zdr_required":true,"raw_prompt_storage":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name, model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name, base_url=EXCLUDED.base_url,
    context_window=EXCLUDED.context_window, cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    status=CASE WHEN agent.model_endpoints.secret_ref IS NULL THEN 'configured' ELSE agent.model_endpoints.status END,
    health_status=CASE WHEN agent.model_endpoints.secret_ref IS NULL THEN 'needs_secret' ELSE agent.model_endpoints.health_status END,
    notes=EXCLUDED.notes, config=EXCLUDED.config, updated_at=now();

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
) VALUES
    ('tradingagents_structured_debate', 'Structured Bull Bear Research Debate', 'tradingagents', 'multi_agent_review', 'research', 'active', 'internal_workflow', 'read_only', ARRAY['bull bear debate','research debate','challenge thesis'], ARRAY['research evidence packet','market/news/fundamental/technical analyst outputs'], ARRAY['agent.agent_messages','knowledge.obsidian_notes','agent.approvals'], ARRAY['agent_mailbox_router','postgres_read_model'], 'Debate produces a recommendation proposal only. Evidence, portfolio fit, risk, and human approval remain mandatory.', 'Run bounded bull and bear rounds, then require a structured research-manager synthesis with claims tied to supplied evidence.', '{"source_repo":"https://github.com/TauricResearch/TradingAgents","license":"Apache-2.0","adoption":"pattern","evidence":["tradingagents/graph/setup.py","tradingagents/agents/schemas.py"]}'::jsonb),
    ('alpha_view_contract', 'Point-In-Time Alpha View Contract', 'ai_hedge_fund', 'alpha_model_contract', 'quant', 'active', 'deterministic_contract', 'read_only', ARRAY['alpha view','signal conviction','point in time'], ARRAY['point-in-time market and filing data'], ARRAY['trading.signals','strategy.generated_ideas'], ARRAY['postgres_read_model','data_quality_gate'], 'An alpha view cannot size or execute a position. Abstention is distinct from a neutral view.', 'Return a bounded conviction, thesis, timestamp, evidence, and abstention state. Portfolio construction and risk remain deterministic.', '{"source_repo":"https://github.com/virattt/ai-hedge-fund","license":"MIT","adoption":"pattern","evidence":["v2/signals/base.py","v2/portfolio/construction.py"]}'::jsonb),
    ('single_pipeline_replay_contract', 'Single Backtest Paper Live Pipeline Contract', 'ai_hedge_fund', 'strategy_governance', 'quant', 'active', 'deterministic_contract', 'read_only', ARRAY['same backtest and live path','paper promotion'], ARRAY['strategy specification','point-in-time data','broker state'], ARRAY['strategy.backtest_runs','trading.trade_activity_ledger','agent.approvals'], ARRAY['local_python_backtester','risk_limit_checker'], 'Live remains opt-in and locked. The same strategy semantics must be replayable in backtest and paper modes before promotion.', 'Separate alpha views, portfolio construction, hard risk, execution adapter, and immutable ledger. Fail loudly when held positions cannot be priced.', '{"source_repo":"https://github.com/virattt/ai-hedge-fund","license":"MIT","adoption":"pattern","evidence":["v2/pipeline/run_cycle.py","VISION.md"]}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name, skill_family=EXCLUDED.skill_family,
    skill_type=EXCLUDED.skill_type, owner_department=EXCLUDED.owner_department,
    status=EXCLUDED.status, execution_mode=EXCLUDED.execution_mode,
    permission_level=EXCLUDED.permission_level, trigger_phrases=EXCLUDED.trigger_phrases,
    input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets,
    required_tools=EXCLUDED.required_tools, risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template, config=EXCLUDED.config, updated_at=now();

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type,
    status, permission_level, input_sources, output_targets,
    approval_required, schedule_hint, notes, metadata
) VALUES
    ('structured_investment_debate','Structured Investment Debate','research_committee','Research Director','manual_or_agent','active','read_only',ARRAY['research.v_corporate_filing_inbox','market.news_items','portfolio.holding_theses','trading.ohlcv'],ARRAY['agent.agent_messages','knowledge.obsidian_notes','agent.approvals'],true,'on thesis, idea, or material event','Analyst facts feed bull/bear challenge, research-manager synthesis, portfolio fit, independent risk, and human decision. No order path.','{"source_pattern":"TradingAgents","max_debate_rounds":2,"structured_outputs":true,"broker_order_allowed":false}'::jsonb),
    ('point_in_time_alpha_cycle','Point-In-Time Alpha Research Cycle','quant_research','Quant Research Lead','manual_or_scheduled','active','read_only',ARRAY['market.dataset_contracts','trading.ohlcv','research.corporate_filings'],ARRAY['trading.signals','strategy.backtest_runs','strategy.validation_reviews','trading.trade_activity_ledger'],true,'research and paper schedules only','One semantic pipeline for point-in-time views, deterministic blending, risk clamps, paper execution, and immutable records.','{"source_pattern":"ai-hedge-fund-v2","stages":["data","alpha_views","portfolio_construction","risk","paper_execution","ledger"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name=EXCLUDED.workflow_name, workflow_type=EXCLUDED.workflow_type,
    owner_agent=EXCLUDED.owner_agent, trigger_type=EXCLUDED.trigger_type,
    status=EXCLUDED.status, permission_level=EXCLUDED.permission_level,
    input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets,
    approval_required=EXCLUDED.approval_required, schedule_hint=EXCLUDED.schedule_hint,
    notes=EXCLUDED.notes, metadata=EXCLUDED.metadata, updated_at=now();

CREATE OR REPLACE VIEW agent.v_external_skill_stack AS
SELECT s.skill_key, s.skill_name, s.skill_family AS source_family,
       s.skill_type, s.owner_department,
       dr.department_name AS owner_department_name, s.status,
       s.execution_mode, s.permission_level, s.required_tools, s.risk_notes,
       s.config ->> 'source_repo' AS source_repo,
       s.config ->> 'local_path' AS local_path,
       s.config ->> 'direct_runtime_adapter' AS direct_runtime_adapter,
       array_remove(array_agg(DISTINCT asm.agent_name ORDER BY asm.agent_name), NULL) AS assigned_agents,
       s.updated_at
FROM agent.skills s
LEFT JOIN agent.department_registry dr ON dr.department_key=s.owner_department
LEFT JOIN agent.agent_skill_map asm ON asm.skill_key=s.skill_key
WHERE s.skill_family IN ('fincept','openalgo','vibe_trading','tradingagents','ai_hedge_fund')
GROUP BY s.skill_key,s.skill_name,s.skill_family,s.skill_type,s.owner_department,
         dr.department_name,s.status,s.execution_mode,s.permission_level,
         s.required_tools,s.risk_notes,s.config,s.updated_at;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_zerodha_read_snapshot','script_adapter','Data Engineering Agent','write_db_manual_only',true,'Fetch Zerodha holdings, positions, orders, trades, and funds with GET-only calls and append immutable snapshots. Daily interactive login and protected credentials are required.','{"script":"_ai_os_runtime/scripts/sync_zerodha_read_only.py","writes":["trading.broker_read_snapshots","core.connector_health_checks"],"broker_write_allowed":false,"execution_allowed":false}'),
    ('ai_os_watchlist_upsert','api_write','Research Director','write_db_manual_only',true,'Create or update a source-linked research, idea, catalyst, or options watchlist item.','{"endpoint":"/api/watchlist/items/upsert","writes":["research.watchlists","research.watchlist_items"],"broker_write_allowed":false}')
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type, owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level, enabled=EXCLUDED.enabled,
    description=EXCLUDED.description, config=EXCLUDED.config;

WITH list AS (
    INSERT INTO research.watchlists (
        watchlist_key, watchlist_name, purpose, owner_agent, created_by, metadata
    ) VALUES (
        'system_market_watchlist', 'System Market Watchlist',
        'Real instruments already registered for market data, paper monitoring, commodities, and crypto research.',
        'Trading Desk', 'Data Migration',
        '{"source":"trading.instrument_watchlist","seed_data":false,"broker_write_allowed":false}'::jsonb
    )
    ON CONFLICT (watchlist_key) DO UPDATE SET
        watchlist_name=EXCLUDED.watchlist_name, purpose=EXCLUDED.purpose,
        status='active', updated_at=now()
    RETURNING id
)
INSERT INTO research.watchlist_items (
    watchlist_id, symbol, exchange, company_name, item_type, status, priority,
    thesis, catalyst, invalidation, owner_agent, source_kind, source_ref,
    created_by, evidence, metadata
)
SELECT
    list.id,
    regexp_replace(source.normalized_symbol, '^(NSE|BSE|MCX):', ''),
    CASE
        WHEN coalesce(source.metadata->>'exchange','') <> '' THEN upper(source.metadata->>'exchange')
        WHEN source.provider_symbol LIKE 'NSE:%' THEN 'NSE'
        WHEN source.provider_symbol LIKE 'BSE:%' THEN 'BSE'
        WHEN source.provider_symbol LIKE 'MCX:%' THEN 'MCX'
        ELSE 'CRYPTO'
    END,
    source.base_asset,
    CASE WHEN source.instrument_type IN ('future','option') THEN 'options' ELSE 'technical' END,
    'active',
    CASE WHEN source.metadata->>'priority'='core' THEN 'high' ELSE 'medium' END,
    source.target_use,
    source.metadata->>'notes',
    NULL,
    source.owner_agent,
    'legacy_watchlist',
    'trading.instrument_watchlist:' || source.id,
    'Data Migration',
    jsonb_build_array(jsonb_build_object('table','trading.instrument_watchlist','id',source.id,'original_status',source.status)),
    source.metadata || jsonb_build_object('venue_key',source.venue_key,'asset_class',source.asset_class,'execution_allowed',false)
FROM trading.instrument_watchlist source
CROSS JOIN list
ON CONFLICT (watchlist_id,exchange,symbol,item_type) DO UPDATE SET
    priority=EXCLUDED.priority, thesis=EXCLUDED.thesis, catalyst=EXCLUDED.catalyst,
    owner_agent=EXCLUDED.owner_agent, source_kind=EXCLUDED.source_kind,
    source_ref=EXCLUDED.source_ref, evidence=EXCLUDED.evidence,
    metadata=EXCLUDED.metadata, updated_at=now();

COMMIT;
