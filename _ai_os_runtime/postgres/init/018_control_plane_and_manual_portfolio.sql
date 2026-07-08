CREATE TABLE IF NOT EXISTS core.control_plane_modules (
    id BIGSERIAL PRIMARY KEY,
    module_key TEXT NOT NULL UNIQUE,
    module_name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    priority TEXT NOT NULL DEFAULT 'medium',
    owner_agent TEXT NOT NULL,
    ui_workspace TEXT,
    description TEXT,
    warehouse_objects TEXT[] NOT NULL DEFAULT '{}',
    mcp_tools TEXT[] NOT NULL DEFAULT '{}',
    fincept_component TEXT,
    next_action TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_control_plane_modules_status ON core.control_plane_modules (status);
CREATE INDEX IF NOT EXISTS idx_control_plane_modules_owner ON core.control_plane_modules (owner_agent);

CREATE TABLE IF NOT EXISTS core.data_source_registry (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    provider TEXT,
    connection_mode TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'planned',
    freshness_target_minutes INTEGER,
    last_seen_at TIMESTAMPTZ,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    sensitivity TEXT NOT NULL DEFAULT 'private',
    source_system_id BIGINT REFERENCES core.source_systems(id),
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_source_registry_type ON core.data_source_registry (source_type);
CREATE INDEX IF NOT EXISTS idx_data_source_registry_status ON core.data_source_registry (status);
CREATE INDEX IF NOT EXISTS idx_data_source_registry_owner ON core.data_source_registry (owner_agent);

CREATE TABLE IF NOT EXISTS research.feed_registry (
    id BIGSERIAL PRIMARY KEY,
    feed_key TEXT NOT NULL UNIQUE,
    feed_name TEXT NOT NULL,
    feed_type TEXT NOT NULL,
    provider TEXT,
    url TEXT,
    geography TEXT,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    topics TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'planned',
    owner_agent TEXT NOT NULL DEFAULT 'News Analyst',
    source_system_id BIGINT REFERENCES core.source_systems(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feed_registry_type ON research.feed_registry (feed_type);
CREATE INDEX IF NOT EXISTS idx_feed_registry_status ON research.feed_registry (status);
CREATE INDEX IF NOT EXISTS idx_feed_registry_topics ON research.feed_registry USING GIN (topics);

CREATE TABLE IF NOT EXISTS strategy.strategy_registry (
    id BIGSERIAL PRIMARY KEY,
    strategy_key TEXT NOT NULL UNIQUE,
    strategy_name TEXT NOT NULL,
    strategy_family TEXT NOT NULL,
    timeframe TEXT,
    universe TEXT,
    status TEXT NOT NULL DEFAULT 'research',
    live_mode TEXT NOT NULL DEFAULT 'research',
    data_dependencies TEXT[] NOT NULL DEFAULT '{}',
    owner_agent TEXT NOT NULL DEFAULT 'Quant Agent',
    risk_level TEXT NOT NULL DEFAULT 'medium',
    paper_first BOOLEAN NOT NULL DEFAULT true,
    approval_required BOOLEAN NOT NULL DEFAULT true,
    fincept_component TEXT,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_registry_status ON strategy.strategy_registry (status);
CREATE INDEX IF NOT EXISTS idx_strategy_registry_family ON strategy.strategy_registry (strategy_family);
CREATE INDEX IF NOT EXISTS idx_strategy_registry_owner ON strategy.strategy_registry (owner_agent);

CREATE TABLE IF NOT EXISTS agent.workflow_registry (
    id BIGSERIAL PRIMARY KEY,
    workflow_key TEXT NOT NULL UNIQUE,
    workflow_name TEXT NOT NULL,
    workflow_type TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'planned',
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    input_sources TEXT[] NOT NULL DEFAULT '{}',
    output_targets TEXT[] NOT NULL DEFAULT '{}',
    approval_required BOOLEAN NOT NULL DEFAULT false,
    schedule_hint TEXT,
    next_run_at TIMESTAMPTZ,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workflow_registry_status ON agent.workflow_registry (status);
CREATE INDEX IF NOT EXISTS idx_workflow_registry_owner ON agent.workflow_registry (owner_agent);
CREATE INDEX IF NOT EXISTS idx_workflow_registry_type ON agent.workflow_registry (workflow_type);

CREATE TABLE IF NOT EXISTS portfolio.manual_client_intake (
    id BIGSERIAL PRIMARY KEY,
    client_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    risk_profile TEXT,
    broker TEXT,
    account_code TEXT,
    account_name TEXT,
    account_type TEXT DEFAULT 'investment',
    base_currency TEXT DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'staged',
    notes TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_manual_client_intake_code ON portfolio.manual_client_intake (client_code);
CREATE INDEX IF NOT EXISTS idx_manual_client_intake_status ON portfolio.manual_client_intake (status);

CREATE TABLE IF NOT EXISTS portfolio.manual_holding_updates (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT REFERENCES portfolio.clients(id),
    account_id BIGINT REFERENCES portfolio.accounts(id),
    client_code TEXT NOT NULL,
    account_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    quantity NUMERIC NOT NULL,
    average_price NUMERIC,
    market_price NUMERIC,
    market_value NUMERIC,
    as_of TIMESTAMPTZ NOT NULL DEFAULT now(),
    update_reason TEXT,
    status TEXT NOT NULL DEFAULT 'staged',
    source_label TEXT NOT NULL DEFAULT 'manual_user_update',
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_manual_holding_updates_status ON portfolio.manual_holding_updates (status);
CREATE INDEX IF NOT EXISTS idx_manual_holding_updates_client ON portfolio.manual_holding_updates (client_code);
CREATE INDEX IF NOT EXISTS idx_manual_holding_updates_symbol ON portfolio.manual_holding_updates (symbol);

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    ('TradingView MCP bridge', 'mcp_webhook', '_ai_os_runtime/tradingview_mcp', 'private_trading', 'planned', 'Read-only chart/signal bridge target. Broker execution remains gated.'),
    ('Zerodha live account', 'broker_api', 'external:zerodha', 'client_private', 'planned', 'Live account connector target. Start read-only for holdings, orders, and trades.'),
    ('Dhan live account', 'broker_api', 'external:dhan', 'client_private', 'planned', 'Alternative broker connector target. Start read-only for holdings, orders, and trades.'),
    ('NSE corporate filings', 'exchange_filings', 'https://www.nseindia.com/companies-listing/corporate-filings-announcements', 'public', 'planned', 'Corporate announcement feed for filings and special situations.'),
    ('BSE corporate filings', 'exchange_filings', 'https://www.bseindia.com/corporates/ann.html', 'public', 'planned', 'Corporate announcement feed for filings and special situations.'),
    ('Global market news basket', 'news_feed', 'rss-and-api-basket', 'public', 'planned', 'Curated global and India market news feeds.'),
    ('X curated watchlist', 'browser_social_feed', 'browser:x.com', 'private', 'planned', 'Browser-assisted social/news watchlist. Respect source terms and manual review.')
ON CONFLICT (name) DO UPDATE SET
    source_type = EXCLUDED.source_type,
    location = EXCLUDED.location,
    sensitivity = EXCLUDED.sensitivity,
    notes = EXCLUDED.notes;

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent, ui_workspace, description,
    warehouse_objects, mcp_tools, fincept_component, next_action, metadata
)
VALUES
    ('command_center', 'Command Center', 'workspace', 'active', 'critical', 'Charlie Munger', 'command', 'Main operating surface for routing work, approvals, briefs, and live agent state.', ARRAY['agent.inbox_items','agent.approvals','agent.workflow_registry']::TEXT[], ARRAY['ai_os_control_plane_snapshot','ai_os_list_open_tasks']::TEXT[], NULL, 'Use as the daily entry point for Charlie and Jarvis.', '{"runtime":"ai-office-ui"}'::jsonb),
    ('data_sources', 'Data Source Control', 'data', 'active', 'critical', 'Data Steward', 'system', 'Registry for broker, filings, news, legacy archives, and installed components.', ARRAY['core.data_source_registry','core.source_systems']::TEXT[], ARRAY['ai_os_control_plane_snapshot','ai_os_component_inventory']::TEXT[], NULL, 'Wire live connectors read-only after registry stabilizes.', '{}'::jsonb),
    ('client_folios', 'Client Folios', 'portfolio', 'active', 'critical', 'Portfolio Manager', 'clients', 'Client, account, holding, thesis, and manual update workflow.', ARRAY['portfolio.clients','portfolio.accounts','portfolio.positions','portfolio.manual_client_intake','portfolio.manual_holding_updates']::TEXT[], ARRAY['ai_os_upsert_client','ai_os_stage_holding_update','ai_os_apply_holding_update','ai_os_latest_positions']::TEXT[], NULL, 'Use MCP tools for new client intake and staged holdings.', '{}'::jsonb),
    ('portfolio_office', 'Portfolio Office', 'portfolio', 'active', 'critical', 'Portfolio Manager', 'portfolio', 'Cross-client exposure, drift, thesis state, and action monitoring.', ARRAY['portfolio.snapshots','portfolio.holding_theses','portfolio.v_client_control_plane']::TEXT[], ARRAY['ai_os_latest_positions','ai_os_client_3081282_summary']::TEXT[], NULL, 'Add portfolio risk and performance read models next.', '{}'::jsonb),
    ('strategy_registry', 'Strategy Registry', 'quant', 'active', 'high', 'Quant Agent', 'quant', 'Strategy inventory for intraday, swing, options, filings, and journal-derived systems.', ARRAY['strategy.strategy_registry','strategy.strategy_candidates','strategy.strategy_instances']::TEXT[], ARRAY['ai_os_control_plane_snapshot','ai_os_recent_trading_signals']::TEXT[], 'analytics-and-charting-patterns', 'Keep all new strategies paper-first until risk review.', '{}'::jsonb),
    ('research_inbox', 'Research and Filings Inbox', 'research', 'active', 'high', 'News Analyst', 'research', 'Corporate filings, exchange announcements, special situations, and curated news.', ARRAY['research.feed_registry','research.corporate_filings','research.filing_events','research.ideas']::TEXT[], ARRAY['ai_os_research_outputs','ai_os_search_obsidian_notes']::TEXT[], 'edgar-and-document-ingestion', 'Build NSE/BSE collector after control plane smoke passes.', '{}'::jsonb),
    ('trading_desk', 'Trading Desk', 'trading', 'mapped', 'high', 'Trading Desk', 'trading', 'Live signals, TradingView bridge, old algo components, and broker read-only state.', ARRAY['trading.signals','trading.ticks','trading.ohlcv']::TEXT[], ARRAY['ai_os_recent_trading_signals']::TEXT[], 'market-data-and-charting', 'Map TradingView MCP endpoints before execution wiring.', '{}'::jsonb),
    ('quant_lab', 'Quant Lab', 'quant', 'mapped', 'high', 'Quant Agent', 'quant', 'Backtests, indicators, strategy validation, and performance snapshots.', ARRAY['strategy.backtest_runs','strategy.performance_snapshots','strategy.strategy_versions']::TEXT[], ARRAY['ai_os_component_inventory','ai_os_recent_trading_signals']::TEXT[], 'quant-analytics', 'Integrate old backtest modules as quarantined adapters.', '{}'::jsonb),
    ('fincept_bridge', 'Fincept Bridge', 'component', 'installed', 'high', 'Codex', 'system', 'Local FinceptTerminal install used as a component/reference bridge, not the whole product.', ARRAY['core.external_component_installs','core.source_components']::TEXT[], ARRAY['ai_os_fincept_component_review','ai_os_fincept_install_status']::TEXT[], 'FinceptTerminal', 'Expose useful Fincept workflows as adapters after command center is stable.', '{}'::jsonb),
    ('approval_center', 'Approval Center', 'risk', 'active', 'critical', 'Risk Agent', 'risk', 'Human-gated queue for reports, strategy activation, data imports, and trade actions.', ARRAY['agent.approvals','agent.tasks']::TEXT[], ARRAY['ai_os_list_open_tasks']::TEXT[], NULL, 'Keep all execution and client-facing outputs approval-gated.', '{}'::jsonb),
    ('obsidian_graph', 'Obsidian Graph Memory', 'knowledge', 'active', 'critical', 'Knowledge Librarian', 'reports', 'Vault note index, graph links, and write-back location for durable research.', ARRAY['knowledge.obsidian_notes','knowledge.note_links','knowledge.vector_documents']::TEXT[], ARRAY['ai_os_search_obsidian_notes','ai_os_reindex_obsidian']::TEXT[], NULL, 'Reindex after every meaningful architecture/report note.', '{}'::jsonb)
ON CONFLICT (module_key) DO UPDATE SET
    module_name = EXCLUDED.module_name,
    category = EXCLUDED.category,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    owner_agent = EXCLUDED.owner_agent,
    ui_workspace = EXCLUDED.ui_workspace,
    description = EXCLUDED.description,
    warehouse_objects = EXCLUDED.warehouse_objects,
    mcp_tools = EXCLUDED.mcp_tools,
    fincept_component = EXCLUDED.fincept_component,
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO core.data_source_registry (
    source_key, source_name, source_type, provider, connection_mode, status, freshness_target_minutes,
    owner_agent, sensitivity, source_system_id, notes, metadata
)
VALUES
    ('zerodha_live', 'Zerodha live account', 'broker_api', 'Zerodha', 'api_read_only', 'planned', 5, 'Portfolio Manager', 'client_private', (SELECT id FROM core.source_systems WHERE name = 'Zerodha live account'), 'Read-only holdings, positions, orders, and trades first. No execution until separate approval workflow exists.', '{"execution_allowed":false}'::jsonb),
    ('dhan_live', 'Dhan live account', 'broker_api', 'Dhan', 'api_read_only', 'planned', 5, 'Portfolio Manager', 'client_private', (SELECT id FROM core.source_systems WHERE name = 'Dhan live account'), 'Read-only broker backup connector target.', '{"execution_allowed":false}'::jsonb),
    ('tradingview_mcp', 'TradingView MCP bridge', 'chart_signal_mcp', 'TradingView', 'mcp_webhook', 'mapped', 1, 'Trading Desk', 'private_trading', (SELECT id FROM core.source_systems WHERE name = 'TradingView MCP bridge'), 'Use for chart context and strategy alert intake.', '{"execution_allowed":false}'::jsonb),
    ('nse_filings', 'NSE corporate filings', 'exchange_filings', 'NSE', 'browser_or_http_collector', 'planned', 60, 'News Analyst', 'public', (SELECT id FROM core.source_systems WHERE name = 'NSE corporate filings'), 'Special situation source for announcements, scheme updates, demergers, mergers, and board actions.', '{}'::jsonb),
    ('bse_filings', 'BSE corporate filings', 'exchange_filings', 'BSE', 'browser_or_http_collector', 'planned', 60, 'News Analyst', 'public', (SELECT id FROM core.source_systems WHERE name = 'BSE corporate filings'), 'Special situation source for announcements and filings.', '{}'::jsonb),
    ('global_news', 'Global market news basket', 'news_feed', 'RSS/API basket', 'rss_http', 'planned', 15, 'News Analyst', 'public', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), 'Curated global macro, company, and sector feeds.', '{}'::jsonb),
    ('x_watchlist', 'X curated watchlist', 'social_browser', 'X/Twitter', 'browser_agent', 'planned', 15, 'News Analyst', 'private', (SELECT id FROM core.source_systems WHERE name = 'X curated watchlist'), 'Browser-assisted feed for curated handles and saved articles; manual review required.', '{"browser_required":true}'::jsonb),
    ('p2cursor_archive', 'p2cursor client archive', 'legacy_archive', 'local archive', 'quarantine_import', 'imported', NULL, 'Data Steward', 'client_private', (SELECT id FROM core.source_systems WHERE name = 'ps 2 cursor archive'), 'Legacy client/portfolio system used as data source and component inventory.', '{"storage":"external_ssd"}'::jsonb),
    ('algo_trading_archive', 'Algo trading terminal archive', 'legacy_trading_system', 'local repo', 'quarantine_import', 'imported', NULL, 'Data Steward', 'private_trading', (SELECT id FROM core.source_systems WHERE name = 'algo trading terminal'), 'Existing algo software provides live trading, alerts, dashboards, and strategy components.', '{"storage":"external_ssd"}'::jsonb),
    ('fincept_terminal', 'FinceptTerminal local component', 'installed_component', 'FinceptTerminal', 'local_app_bridge', 'installed', NULL, 'Codex', 'private', (SELECT id FROM core.source_systems WHERE name = 'FinceptTerminal reference repo'), 'Installed as a component/reference bridge for analytics, data adapters, and financial tooling.', '{"bridge_mode":"component_not_core"}'::jsonb)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    provider = EXCLUDED.provider,
    connection_mode = EXCLUDED.connection_mode,
    status = EXCLUDED.status,
    freshness_target_minutes = EXCLUDED.freshness_target_minutes,
    owner_agent = EXCLUDED.owner_agent,
    sensitivity = EXCLUDED.sensitivity,
    source_system_id = EXCLUDED.source_system_id,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO research.feed_registry (
    feed_key, feed_name, feed_type, provider, url, geography, symbols, topics, status, owner_agent, source_system_id, metadata
)
VALUES
    ('nse_announcements', 'NSE corporate announcements', 'exchange_announcements', 'NSE', 'https://www.nseindia.com/companies-listing/corporate-filings-announcements', 'India', ARRAY[]::TEXT[], ARRAY['filings','demerger','merger','results','board_action']::TEXT[], 'planned', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'NSE corporate filings'), '{}'::jsonb),
    ('bse_announcements', 'BSE corporate announcements', 'exchange_announcements', 'BSE', 'https://www.bseindia.com/corporates/ann.html', 'India', ARRAY[]::TEXT[], ARRAY['filings','demerger','merger','results','board_action']::TEXT[], 'planned', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'BSE corporate filings'), '{}'::jsonb),
    ('sec_edgar', 'SEC EDGAR company filings', 'regulatory_filings', 'SEC', 'https://www.sec.gov/edgar', 'Global', ARRAY[]::TEXT[], ARRAY['filings','transcripts','special_situations']::TEXT[], 'planned', 'News Analyst', NULL, '{"fincept_candidate":true}'::jsonb),
    ('global_news_rss', 'Global market RSS basket', 'news_rss', 'RSS/API basket', NULL, 'Global', ARRAY[]::TEXT[], ARRAY['macro','company_news','commodities','rates']::TEXT[], 'planned', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{}'::jsonb),
    ('x_curated_handles', 'X curated finance watchlist', 'social_browser', 'X/Twitter', 'https://x.com', 'Global', ARRAY[]::TEXT[], ARRAY['market_color','breaking_news','repo_discovery','special_situations']::TEXT[], 'planned', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'X curated watchlist'), '{"browser_required":true}'::jsonb)
ON CONFLICT (feed_key) DO UPDATE SET
    feed_name = EXCLUDED.feed_name,
    feed_type = EXCLUDED.feed_type,
    provider = EXCLUDED.provider,
    url = EXCLUDED.url,
    geography = EXCLUDED.geography,
    symbols = EXCLUDED.symbols,
    topics = EXCLUDED.topics,
    status = EXCLUDED.status,
    owner_agent = EXCLUDED.owner_agent,
    source_system_id = EXCLUDED.source_system_id,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO strategy.strategy_registry (
    strategy_key, strategy_name, strategy_family, timeframe, universe, status, live_mode, data_dependencies,
    owner_agent, risk_level, paper_first, approval_required, fincept_component, notes, metadata
)
VALUES
    ('atr_extension_intraday', 'ATR Extension Intraday', 'technical_intraday', '5m/15m', 'NIFTY, BANKNIFTY, liquid NSE equities', 'mapped', 'paper', ARRAY['trading.ohlcv','trading.signals','TradingView MCP bridge']::TEXT[], 'Quant Agent', 'high', true, true, 'technical-analysis-and-charting', 'Initial source from old algo components and TradingView alerts; paper/shadow only.', '{}'::jsonb),
    ('regime_momentum_daily', 'Regime Momentum Daily', 'technical_swing', '1D', 'NSE large and mid caps', 'research', 'research', ARRAY['trading.ohlcv','portfolio.positions','market.news_items']::TEXT[], 'Quant Agent', 'medium', true, true, 'quant-analytics', 'Long-only allocation support and watchlist generation.', '{}'::jsonb),
    ('mean_reversion_intraday', 'Mean Reversion Intraday', 'technical_intraday', '5m', 'NIFTY, BANKNIFTY, high liquidity equities', 'research', 'research', ARRAY['trading.ohlcv','trading.ticks']::TEXT[], 'Quant Agent', 'high', true, true, 'technical-analysis-and-charting', 'Needs slippage, regime filter, and kill switch before paper activation.', '{}'::jsonb),
    ('options_oi_monitor', 'FNO OI and Max Pain Monitor', 'options_monitoring', 'intraday', 'NSE index and stock options', 'mapped', 'paper', ARRAY['options_chain','trading.signals','old algo options modules']::TEXT[], 'Quant Agent', 'high', true, true, 'options-analytics', 'Use old option chain and strategy modules as adapter candidates.', '{}'::jsonb),
    ('filings_special_situations', 'Filings Special Situations', 'event_driven', 'event', 'NSE/BSE listed companies', 'planned', 'research', ARRAY['research.corporate_filings','research.filing_events','market.news_items']::TEXT[], 'Special Situations Analyst', 'medium', true, true, 'document-ingestion', 'Looks for demergers, reverse mergers, schemes, arbitrage, and corporate actions.', '{}'::jsonb),
    ('trade_journal_mining', 'Trade Journal Pattern Mining', 'behavioral_quant', 'post_trade', 'Personal and client trade history', 'planned', 'research', ARRAY['portfolio.trades','trading.trade_journals','client_data.v_client_3081282_trade_timeline']::TEXT[], 'Trade Journal Coach', 'medium', true, true, NULL, 'Extracts repeatable setup and error patterns from old trade journals and broker reports.', '{}'::jsonb)
ON CONFLICT (strategy_key) DO UPDATE SET
    strategy_name = EXCLUDED.strategy_name,
    strategy_family = EXCLUDED.strategy_family,
    timeframe = EXCLUDED.timeframe,
    universe = EXCLUDED.universe,
    status = EXCLUDED.status,
    live_mode = EXCLUDED.live_mode,
    data_dependencies = EXCLUDED.data_dependencies,
    owner_agent = EXCLUDED.owner_agent,
    risk_level = EXCLUDED.risk_level,
    paper_first = EXCLUDED.paper_first,
    approval_required = EXCLUDED.approval_required,
    fincept_component = EXCLUDED.fincept_component,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status, permission_level,
    input_sources, output_targets, approval_required, schedule_hint, notes, metadata
)
VALUES
    ('daily_portfolio_brief', 'Daily Portfolio Brief', 'portfolio_monitoring', 'Portfolio Manager', 'scheduled', 'active', 'read_only', ARRAY['portfolio.positions','portfolio.snapshots','portfolio.holding_theses']::TEXT[], ARRAY['agent.inbox_items','knowledge.obsidian_notes']::TEXT[], true, 'market close and morning pre-open', 'Produces client and cross-client drift/thesis brief.', '{}'::jsonb),
    ('strategy_monitor', 'Strategy Monitor', 'trading_monitoring', 'Trading Desk', 'stream_or_schedule', 'mapped', 'read_only', ARRAY['trading.signals','strategy.strategy_registry','TradingView MCP bridge']::TEXT[], ARRAY['agent.inbox_items','strategy.alert_events']::TEXT[], true, 'intraday continuous when bridge is online', 'Tracks live strategy alerts without broker execution.', '{}'::jsonb),
    ('news_filings_inbox', 'News and Filings Inbox', 'research_monitoring', 'News Analyst', 'scheduled', 'planned', 'read_only', ARRAY['research.feed_registry','research.corporate_filings','market.news_items']::TEXT[], ARRAY['research.ideas','agent.inbox_items','knowledge.obsidian_notes']::TEXT[], true, 'every 15 to 60 minutes by source', 'Captures NSE/BSE/global news and routes special situations.', '{}'::jsonb),
    ('trade_journal_learning', 'Trade Journal Learning', 'learning_pipeline', 'Trade Journal Coach', 'manual_or_scheduled', 'planned', 'read_only', ARRAY['portfolio.trades','trading.trade_journals','client_data.v_client_3081282_trade_timeline']::TEXT[], ARRAY['research.ideas','knowledge.obsidian_notes']::TEXT[], false, 'weekly and after import', 'Extracts strategy and behavior patterns from historical trades.', '{}'::jsonb),
    ('client_intake_holdings_update', 'Client Intake and Holdings Update', 'manual_portfolio_ops', 'Portfolio Manager', 'manual', 'active', 'write_db_manual_only', ARRAY['portfolio.manual_client_intake','portfolio.manual_holding_updates']::TEXT[], ARRAY['portfolio.clients','portfolio.accounts','portfolio.positions','agent.inbox_items']::TEXT[], true, 'on demand', 'Adds new clients and stages/applies manual holdings. No broker action.', '{}'::jsonb),
    ('fincept_component_bridge', 'Fincept Component Bridge', 'component_bridge', 'Codex', 'manual', 'installed', 'local_component', ARRAY['core.external_component_installs','core.source_components']::TEXT[], ARRAY['agent.inbox_items','knowledge.obsidian_notes']::TEXT[], true, 'on demand', 'Uses FinceptTerminal as installed analytics/data component bridge.', '{}'::jsonb),
    ('obsidian_graph_link_sweep', 'Obsidian Graph Link Sweep', 'knowledge_indexing', 'Knowledge Librarian', 'manual_or_scheduled', 'active', 'write_db_only', ARRAY['knowledge.obsidian_notes','knowledge.note_links']::TEXT[], ARRAY['knowledge.obsidian_notes','knowledge.note_links']::TEXT[], false, 'after meaningful vault writes', 'Keeps graph/search index current after Codex outputs and reports.', '{}'::jsonb)
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

INSERT INTO agent.inbox_items (title, owner_agent, status, priority, recommended_action, evidence, target_workspace)
SELECT title, owner_agent, status, priority, recommended_action, evidence, target_workspace
FROM (
    VALUES
        ('Control plane registry online', 'Jarvis', 'done', 'medium', 'Use ai_os_control_plane_snapshot to inspect modules, data sources, strategies, workflows, clients, and Fincept status.', '[{"table":"core.control_plane_modules"},{"table":"core.data_source_registry"}]'::jsonb, 'system'),
        ('Manual client and holdings workflow ready', 'Portfolio Manager', 'needs_review', 'high', 'Add clients with ai_os_upsert_client, stage holdings with ai_os_stage_holding_update, then apply after review.', '[{"table":"portfolio.manual_client_intake"},{"table":"portfolio.manual_holding_updates"}]'::jsonb, 'clients'),
        ('Fincept bridge installed as component layer', 'Codex', 'needs_review', 'medium', 'Use Fincept capabilities through adapter workflows instead of making Fincept the core application.', '[{"table":"core.external_component_installs"},{"mcp_tool":"ai_os_fincept_install_status"}]'::jsonb, 'system')
) AS seeded(title, owner_agent, status, priority, recommended_action, evidence, target_workspace)
WHERE NOT EXISTS (
    SELECT 1
    FROM agent.inbox_items existing
    WHERE existing.title = seeded.title
);

CREATE OR REPLACE VIEW core.v_control_plane_overview AS
SELECT
    module_key,
    module_name,
    category,
    status,
    priority,
    owner_agent,
    ui_workspace,
    description,
    warehouse_objects,
    mcp_tools,
    fincept_component,
    next_action,
    updated_at
FROM core.control_plane_modules
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    module_name;

CREATE OR REPLACE VIEW core.v_data_source_registry AS
SELECT
    ds.source_key,
    ds.source_name,
    ds.source_type,
    ds.provider,
    ds.connection_mode,
    ds.status,
    ds.freshness_target_minutes,
    ds.last_seen_at,
    ds.owner_agent,
    ds.sensitivity,
    ss.location AS source_location,
    ss.status AS source_system_status,
    ds.notes,
    ds.metadata,
    ds.updated_at
FROM core.data_source_registry ds
LEFT JOIN core.source_systems ss ON ss.id = ds.source_system_id
ORDER BY
    CASE ds.status
        WHEN 'active' THEN 1
        WHEN 'installed' THEN 2
        WHEN 'imported' THEN 3
        WHEN 'mapped' THEN 4
        WHEN 'planned' THEN 5
        ELSE 6
    END,
    ds.source_name;

CREATE OR REPLACE VIEW research.v_feed_registry AS
SELECT
    feed_key,
    feed_name,
    feed_type,
    provider,
    url,
    geography,
    symbols,
    topics,
    status,
    owner_agent,
    metadata,
    updated_at
FROM research.feed_registry
ORDER BY feed_type, feed_name;

CREATE OR REPLACE VIEW strategy.v_strategy_registry AS
SELECT
    strategy_key,
    strategy_name,
    strategy_family,
    timeframe,
    universe,
    status,
    live_mode,
    data_dependencies,
    owner_agent,
    risk_level,
    paper_first,
    approval_required,
    fincept_component,
    notes,
    updated_at
FROM strategy.strategy_registry
ORDER BY
    CASE status
        WHEN 'active' THEN 1
        WHEN 'mapped' THEN 2
        WHEN 'research' THEN 3
        WHEN 'planned' THEN 4
        ELSE 5
    END,
    strategy_name;

CREATE OR REPLACE VIEW agent.v_workflow_registry AS
SELECT
    workflow_key,
    workflow_name,
    workflow_type,
    owner_agent,
    trigger_type,
    status,
    permission_level,
    input_sources,
    output_targets,
    approval_required,
    schedule_hint,
    next_run_at,
    notes,
    updated_at
FROM agent.workflow_registry
ORDER BY
    CASE status
        WHEN 'active' THEN 1
        WHEN 'installed' THEN 2
        WHEN 'mapped' THEN 3
        WHEN 'planned' THEN 4
        ELSE 5
    END,
    workflow_name;

CREATE OR REPLACE VIEW portfolio.v_client_control_plane AS
WITH latest_positions AS (
    SELECT DISTINCT ON (p.account_id, p.symbol, p.exchange, p.instrument_type)
        p.id,
        p.account_id,
        p.symbol,
        p.exchange,
        p.instrument_type,
        p.quantity,
        p.market_value,
        p.unrealized_pnl,
        p.as_of
    FROM portfolio.positions p
    ORDER BY p.account_id, p.symbol, p.exchange, p.instrument_type, p.as_of DESC
),
account_rollup AS (
    SELECT
        c.id AS client_id,
        count(DISTINCT a.id) AS account_count,
        count(lp.id) AS latest_position_count,
        coalesce(sum(lp.market_value), 0) AS latest_market_value,
        max(lp.as_of) AS latest_position_at
    FROM portfolio.clients c
    LEFT JOIN portfolio.accounts a ON a.client_id = c.id
    LEFT JOIN latest_positions lp ON lp.account_id = a.id
    GROUP BY c.id
)
SELECT
    c.client_code,
    c.display_name,
    c.risk_profile,
    c.sensitivity,
    c.active,
    ar.account_count,
    ar.latest_position_count,
    ar.latest_market_value,
    ar.latest_position_at,
    (
        SELECT count(*)
        FROM portfolio.manual_holding_updates mhu
        WHERE mhu.client_code = c.client_code
          AND mhu.status = 'staged'
    ) AS staged_holding_updates,
    c.created_at
FROM portfolio.clients c
LEFT JOIN account_rollup ar ON ar.client_id = c.id
ORDER BY c.display_name;

CREATE OR REPLACE VIEW portfolio.v_manual_holding_update_queue AS
SELECT
    mhu.id,
    mhu.client_code,
    mhu.account_code,
    mhu.symbol,
    mhu.exchange,
    mhu.instrument_type,
    mhu.quantity,
    mhu.average_price,
    mhu.market_price,
    coalesce(mhu.market_value, mhu.quantity * mhu.market_price) AS effective_market_value,
    mhu.as_of,
    mhu.update_reason,
    mhu.status,
    mhu.created_by,
    mhu.created_at,
    mhu.applied_at
FROM portfolio.manual_holding_updates mhu
ORDER BY
    CASE mhu.status
        WHEN 'staged' THEN 1
        WHEN 'applied' THEN 2
        ELSE 3
    END,
    mhu.created_at DESC;

CREATE OR REPLACE VIEW core.v_control_plane_snapshot AS
SELECT 'control_modules' AS metric, count(*)::TEXT AS value FROM core.control_plane_modules
UNION ALL
SELECT 'active_modules', count(*)::TEXT FROM core.control_plane_modules WHERE status IN ('active','installed')
UNION ALL
SELECT 'data_sources', count(*)::TEXT FROM core.data_source_registry
UNION ALL
SELECT 'mapped_or_online_sources', count(*)::TEXT FROM core.data_source_registry WHERE status IN ('active','installed','imported','mapped')
UNION ALL
SELECT 'registered_strategies', count(*)::TEXT FROM strategy.strategy_registry
UNION ALL
SELECT 'paper_or_mapped_strategies', count(*)::TEXT FROM strategy.strategy_registry WHERE live_mode IN ('paper','shadow') OR status = 'mapped'
UNION ALL
SELECT 'registered_workflows', count(*)::TEXT FROM agent.workflow_registry
UNION ALL
SELECT 'active_workflows', count(*)::TEXT FROM agent.workflow_registry WHERE status IN ('active','installed')
UNION ALL
SELECT 'clients', count(*)::TEXT FROM portfolio.clients
UNION ALL
SELECT 'staged_holding_updates', count(*)::TEXT FROM portfolio.manual_holding_updates WHERE status = 'staged';
