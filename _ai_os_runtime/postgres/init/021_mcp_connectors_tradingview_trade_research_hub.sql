CREATE TABLE IF NOT EXISTS core.mcp_integration_registry (
    id BIGSERIAL PRIMARY KEY,
    integration_key TEXT NOT NULL UNIQUE,
    integration_name TEXT NOT NULL,
    category TEXT NOT NULL,
    provider TEXT,
    repo_url TEXT,
    docs_url TEXT,
    install_mode TEXT NOT NULL DEFAULT 'candidate',
    status TEXT NOT NULL DEFAULT 'candidate',
    priority TEXT NOT NULL DEFAULT 'medium',
    trust_level TEXT NOT NULL DEFAULT 'needs_review',
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    requires_api_key BOOLEAN NOT NULL DEFAULT false,
    requires_browser_session BOOLEAN NOT NULL DEFAULT false,
    cost_profile TEXT NOT NULL DEFAULT 'free_or_local',
    owner_agent TEXT NOT NULL DEFAULT 'Jarvis',
    use_case TEXT,
    selected_for_phase TEXT,
    risk_notes TEXT,
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_integration_registry_category ON core.mcp_integration_registry (category);
CREATE INDEX IF NOT EXISTS idx_mcp_integration_registry_status ON core.mcp_integration_registry (status);
CREATE INDEX IF NOT EXISTS idx_mcp_integration_registry_priority ON core.mcp_integration_registry (priority);

CREATE TABLE IF NOT EXISTS ops.tradingview_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_title TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'chart_review',
    requested_by TEXT NOT NULL DEFAULT 'Devarsh',
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    status TEXT NOT NULL DEFAULT 'queued',
    symbols TEXT[] NOT NULL DEFAULT '{}',
    exchange TEXT,
    timeframe TEXT,
    chart_layout TEXT,
    instruction TEXT NOT NULL,
    source_ref TEXT,
    browser_run_id BIGINT REFERENCES ops.browser_runs(id),
    extracted_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    output_note_path TEXT,
    result_summary TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tradingview_tasks_status ON ops.tradingview_tasks (status);
CREATE INDEX IF NOT EXISTS idx_tradingview_tasks_symbols ON ops.tradingview_tasks USING GIN (symbols);
CREATE INDEX IF NOT EXISTS idx_tradingview_tasks_created ON ops.tradingview_tasks (created_at DESC);

CREATE TABLE IF NOT EXISTS trading.trade_activity_ledger (
    id BIGSERIAL PRIMARY KEY,
    activity_type TEXT NOT NULL DEFAULT 'trade',
    execution_mode TEXT NOT NULL DEFAULT 'manual_actual',
    source_kind TEXT NOT NULL DEFAULT 'manual',
    source_ref TEXT,
    client_code TEXT,
    account_code TEXT,
    strategy_key TEXT,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    side TEXT NOT NULL,
    quantity NUMERIC,
    price NUMERIC,
    trade_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'recorded',
    thesis TEXT,
    setup_type TEXT,
    timeframe TEXT,
    stop_loss NUMERIC,
    target_price NUMERIC,
    realized_pnl NUMERIC,
    fees NUMERIC,
    source_signal_id BIGINT REFERENCES trading.signals(id),
    alert_event_id BIGINT REFERENCES strategy.alert_events(id),
    tags TEXT[] NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_activity_symbol_ts ON trading.trade_activity_ledger (symbol, trade_ts DESC);
CREATE INDEX IF NOT EXISTS idx_trade_activity_mode ON trading.trade_activity_ledger (execution_mode);
CREATE INDEX IF NOT EXISTS idx_trade_activity_status ON trading.trade_activity_ledger (status);
CREATE INDEX IF NOT EXISTS idx_trade_activity_strategy ON trading.trade_activity_ledger (strategy_key);

CREATE TABLE IF NOT EXISTS core.data_source_checks (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL,
    check_name TEXT NOT NULL,
    check_type TEXT NOT NULL DEFAULT 'http',
    target_url TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    latency_ms INTEGER,
    rows_seen BIGINT,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_source_checks_key_time ON core.data_source_checks (source_key, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_data_source_checks_status ON core.data_source_checks (status);

CREATE OR REPLACE VIEW core.v_mcp_integration_registry AS
SELECT
    integration_key,
    integration_name,
    category,
    provider,
    repo_url,
    docs_url,
    install_mode,
    status,
    priority,
    trust_level,
    permission_level,
    requires_api_key,
    requires_browser_session,
    cost_profile,
    owner_agent,
    use_case,
    selected_for_phase,
    risk_notes,
    evidence_refs,
    config,
    updated_at
FROM core.mcp_integration_registry
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    category,
    integration_name;

CREATE OR REPLACE VIEW ops.v_tradingview_tasks AS
SELECT
    id,
    task_title,
    task_type,
    requested_by,
    owner_agent,
    status,
    symbols,
    exchange,
    timeframe,
    chart_layout,
    instruction,
    source_ref,
    browser_run_id,
    extracted_artifact_id,
    output_note_path,
    result_summary,
    evidence,
    metadata,
    created_at,
    updated_at,
    completed_at
FROM ops.tradingview_tasks
ORDER BY
    CASE status
        WHEN 'queued' THEN 1
        WHEN 'running' THEN 2
        WHEN 'needs_review' THEN 3
        WHEN 'done' THEN 4
        ELSE 5
    END,
    created_at DESC;

CREATE OR REPLACE VIEW trading.v_trade_activity_ledger AS
SELECT
    id,
    activity_type,
    execution_mode,
    source_kind,
    source_ref,
    client_code,
    account_code,
    strategy_key,
    symbol,
    exchange,
    instrument_type,
    side,
    quantity,
    price,
    trade_ts,
    status,
    thesis,
    setup_type,
    timeframe,
    stop_loss,
    target_price,
    realized_pnl,
    fees,
    tags,
    evidence,
    created_by,
    created_at,
    updated_at
FROM trading.trade_activity_ledger
ORDER BY trade_ts DESC, id DESC;

CREATE OR REPLACE VIEW trading.v_paper_trade_summary AS
SELECT
    coalesce(strategy_key, 'unassigned') AS strategy_key,
    symbol,
    count(*) AS trade_count,
    min(trade_ts) AS first_trade_ts,
    max(trade_ts) AS last_trade_ts,
    sum(coalesce(realized_pnl, 0)) AS realized_pnl,
    avg(price) FILTER (WHERE price IS NOT NULL) AS average_price,
    array_agg(DISTINCT status ORDER BY status) AS statuses
FROM trading.trade_activity_ledger
WHERE execution_mode IN ('paper', 'shadow', 'system_alert_paper')
GROUP BY coalesce(strategy_key, 'unassigned'), symbol
ORDER BY last_trade_ts DESC;

CREATE OR REPLACE VIEW research.v_research_hub_summary AS
SELECT
    coalesce(metadata->>'root_label', 'unknown') AS root_label,
    coalesce(metadata->>'artifact_family', artifact_type) AS artifact_family,
    count(*) AS artifact_count,
    max(captured_at) AS latest_captured_at,
    max((metadata->>'last_modified_at')::timestamptz) FILTER (WHERE metadata ? 'last_modified_at') AS latest_source_modified_at
FROM core.raw_artifacts
WHERE artifact_type IN ('ai_research_output', 'ai_dashboard_output', 'ai_model_output')
GROUP BY coalesce(metadata->>'root_label', 'unknown'), coalesce(metadata->>'artifact_family', artifact_type)
ORDER BY latest_captured_at DESC, root_label, artifact_family;

CREATE OR REPLACE VIEW core.v_recent_data_source_checks AS
SELECT DISTINCT ON (source_key, check_name)
    source_key,
    check_name,
    check_type,
    target_url,
    status,
    http_status,
    latency_ms,
    rows_seen,
    sample_payload,
    error_message,
    checked_at
FROM core.data_source_checks
ORDER BY source_key, check_name, checked_at DESC;

INSERT INTO core.mcp_integration_registry (
    integration_key, integration_name, category, provider, repo_url, docs_url, install_mode, status,
    priority, trust_level, permission_level, requires_api_key, requires_browser_session, cost_profile,
    owner_agent, use_case, selected_for_phase, risk_notes, evidence_refs, config
)
VALUES
    ('official_fetch', 'Official MCP Fetch Server', 'web_fetch', 'Model Context Protocol', 'https://github.com/modelcontextprotocol/servers', 'https://github.com/modelcontextprotocol/servers', 'npx_or_uvx', 'approved_candidate', 'high', 'reference', 'web_read', false, false, 'free_or_local', 'Browser Research Runner', 'Fetch and convert public web pages into LLM-friendly text.', 'phase_1_browser_research', 'Read-only, but public web content can carry prompt injection. Store artifacts before analysis.', ARRAY['https://github.com/modelcontextprotocol/servers'], '{"package":"@modelcontextprotocol/server-fetch"}'::jsonb),
    ('official_filesystem', 'Official MCP Filesystem Server', 'filesystem', 'Model Context Protocol', 'https://github.com/modelcontextprotocol/servers', 'https://github.com/modelcontextprotocol/servers', 'npx', 'approved_candidate', 'high', 'reference', 'scoped_filesystem', false, false, 'free_or_local', 'Knowledge Librarian', 'Scoped file reads/writes for approved folders only.', 'phase_1_local_ops', 'Must be restricted to the external SSD vault/runtime roots.', ARRAY['https://github.com/modelcontextprotocol/servers'], '{"allowed_roots":["/Volumes/Devarsh SSD/Obsidian memory "],"package":"@modelcontextprotocol/server-filesystem"}'::jsonb),
    ('official_git', 'Official MCP Git Server', 'code_repo', 'Model Context Protocol', 'https://github.com/modelcontextprotocol/servers', 'https://github.com/modelcontextprotocol/servers', 'uvx', 'approved_candidate', 'medium', 'reference', 'repo_read', false, false, 'free_or_local', 'Coding Lead Agent', 'Inspect cloned source components, diffs, commits, and code history.', 'phase_2_component_ops', 'Keep write operations disabled unless a repo task explicitly needs them.', ARRAY['https://github.com/modelcontextprotocol/servers'], '{"package":"mcp-server-git"}'::jsonb),
    ('playwright_mcp', 'Microsoft Playwright MCP', 'browser_control', 'Microsoft', 'https://github.com/microsoft/playwright-mcp', 'https://github.com/microsoft/playwright-mcp', 'npx', 'approved_candidate', 'critical', 'trusted_vendor', 'browser_read_capture', false, true, 'free_or_local', 'Browser Research Runner', 'Control browser pages, capture accessibility snapshots/screenshots, open TradingView/NSE/BSE pages.', 'phase_1_browser_research', 'Browser sessions can expose logged-in data. Use separate browser profile and record every run in ops.browser_runs.', ARRAY['https://github.com/microsoft/playwright-mcp'], '{"package":"@playwright/mcp","preferred_for":["tradingview_ui","nse_bse_pages","dashboard_qa"]}'::jsonb),
    ('firecrawl_mcp', 'Firecrawl MCP Server', 'web_scraper', 'Firecrawl', 'https://github.com/firecrawl/firecrawl-mcp-server', 'https://github.com/firecrawl/firecrawl-mcp-server', 'npx', 'candidate', 'high', 'vendor_api', 'web_search_extract', true, false, 'paid_or_free_tier', 'News Analyst', 'Search, scrape, crawl, and extract web content where plain fetch is weak.', 'phase_2_news_filings', 'Requires API key and external service. Use for public sources only and keep payloads in core.raw_artifacts.', ARRAY['https://github.com/firecrawl/firecrawl-mcp-server'], '{"package":"firecrawl-mcp"}'::jsonb),
    ('tavily_mcp', 'Tavily MCP Server', 'web_search', 'Tavily', 'https://github.com/tavily-ai/tavily-mcp', 'https://github.com/tavily-ai/tavily-mcp', 'npx_or_docker', 'candidate', 'high', 'vendor_api', 'web_search_extract', true, false, 'paid_or_free_tier', 'News Analyst', 'Real-time search, extract, map, and crawl for market/news discovery.', 'phase_2_news_filings', 'Requires API key. Search output needs source validation before it reaches investment conclusions.', ARRAY['https://github.com/tavily-ai/tavily-mcp'], '{}'::jsonb),
    ('tradingview_data_mcp_candidate', 'TradingView Data MCP Candidate', 'tradingview', 'atilaahmettaner', 'https://github.com/atilaahmettaner/tradingview-mcp', 'https://github.com/atilaahmettaner/tradingview-mcp', 'self_host_review', 'candidate_review', 'critical', 'needs_code_review', 'market_data_read', false, false, 'free_or_local', 'Trading Desk Agent', 'Evaluate for real-time market data, technical analysis, screeners, and backtesting workflows.', 'phase_1_tradingview_bridge', 'Do code/security review before installing. Broker execution remains disabled.', ARRAY['github_api:search/repositories?q=tradingview+mcp'], '{"language":"Python","license":"MIT","stars_seen":3346}'::jsonb),
    ('tradingview_desktop_mcp_candidate', 'TradingView Desktop Automation MCP Candidate', 'tradingview', 'tradesdontlie', 'https://github.com/tradesdontlie/tradingview-mcp', 'https://github.com/tradesdontlie/tradingview-mcp', 'self_host_review', 'candidate_review', 'high', 'needs_license_review', 'browser_desktop_control', false, true, 'free_or_local', 'Trading Desk Agent', 'Evaluate for desktop TradingView chart workflow automation and chart analysis.', 'phase_1_tradingview_bridge', 'License was not asserted in GitHub API result. Treat as read-only reference until reviewed.', ARRAY['github_api:search/repositories?q=tradingview+mcp'], '{"language":"JavaScript","license":"NOASSERTION","stars_seen":4096}'::jsonb),
    ('pinescript_mcp_candidate', 'PineScript MCP Candidate', 'strategy_development', 'cklose2000', 'https://github.com/cklose2000/pinescript-mcp-server', 'https://github.com/cklose2000/pinescript-mcp-server', 'self_host_review', 'candidate_review', 'medium', 'needs_code_review', 'code_assist', false, false, 'free_or_local', 'Quant Agent', 'Assist Pine Script strategy drafting/checking before TradingView tests.', 'phase_2_strategy_lab', 'Use for syntax/help only; all strategy activation stays paper-first.', ARRAY['github_api:search/repositories?q=%22TradingView%22+%22Model+Context+Protocol%22'], '{"stars_seen":102}'::jsonb),
    ('sec_edgar_direct_api', 'SEC EDGAR Direct API Adapter', 'filings', 'SEC', NULL, 'https://www.sec.gov/search-filings/edgar-application-programming-interfaces', 'custom_adapter', 'approved_candidate', 'medium', 'official_api', 'public_data_read', false, false, 'free_public', 'News Analyst', 'US filings, company facts, and filing history for global research.', 'phase_2_news_filings', 'Must use compliant User-Agent and rate limits.', ARRAY['https://www.sec.gov/search-filings/edgar-application-programming-interfaces'], '{"auth_required":false,"bulk_available":true}'::jsonb),
    ('nse_bse_filings_browser_adapter', 'NSE/BSE Filings Browser Adapter', 'filings', 'NSE/BSE', NULL, 'https://www.nseindia.com/companies-listing/corporate-filings-announcements', 'custom_playwright_adapter', 'approved_candidate', 'critical', 'official_source', 'browser_read_capture', false, true, 'free_public', 'News Analyst', 'Capture India corporate announcements, filings, schemes, demergers, reverse mergers, and board actions.', 'phase_2_news_filings', 'Prefer official pages. Store raw source evidence and avoid brittle hidden endpoints until tested.', ARRAY['https://www.nseindia.com/companies-listing/corporate-filings-announcements','https://www.bseindia.com/corporates/ann.html'], '{"targets":["research.corporate_filings","research.filing_events"]}'::jsonb),
    ('fincept_terminal_sidecar', 'FinceptTerminal Sidecar MCP/Component Bridge', 'finance_terminal', 'Fincept', 'https://github.com/Fincept-Corporation/FinceptTerminal', NULL, 'local_sidecar', 'installed', 'high', 'local_component', 'local_app_bridge', false, false, 'free_or_local', 'Codex', 'Use installed Fincept components for analytics, charting patterns, options, data connectors, and MCP tool ideas.', 'phase_1_component_reuse', 'Fincept is a component library/sidecar. AI OS warehouse remains source of truth.', ARRAY['ai memory/00 AI OS/Architecture/FinceptTerminal Installed Component.md'], '{"local_root":"_ai_os_runtime/external_components/FinceptTerminal"}'::jsonb)
ON CONFLICT (integration_key) DO UPDATE SET
    integration_name = EXCLUDED.integration_name,
    category = EXCLUDED.category,
    provider = EXCLUDED.provider,
    repo_url = EXCLUDED.repo_url,
    docs_url = EXCLUDED.docs_url,
    install_mode = EXCLUDED.install_mode,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    trust_level = EXCLUDED.trust_level,
    permission_level = EXCLUDED.permission_level,
    requires_api_key = EXCLUDED.requires_api_key,
    requires_browser_session = EXCLUDED.requires_browser_session,
    cost_profile = EXCLUDED.cost_profile,
    owner_agent = EXCLUDED.owner_agent,
    use_case = EXCLUDED.use_case,
    selected_for_phase = EXCLUDED.selected_for_phase,
    risk_notes = EXCLUDED.risk_notes,
    evidence_refs = EXCLUDED.evidence_refs,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_mcp_candidate_shortlist', 'mcp_tool', 'Jarvis', 'read_only', true, 'Read approved/candidate external MCP integrations with priority, risk, and use case.', '{"reads":["core.mcp_integration_registry"]}'::jsonb),
    ('ai_os_create_tradingview_task', 'mcp_tool', 'Trading Desk Agent', 'write_with_approval', true, 'Queue an auditable TradingView chart/screener/browser task for later MCP/browser execution.', '{"writes":["ops.tradingview_tasks","agent.inbox_items"]}'::jsonb),
    ('ai_os_update_tradingview_task', 'mcp_tool', 'Trading Desk Agent', 'write_with_approval', true, 'Update a TradingView task with status, evidence, artifact, browser run, or output note.', '{"writes":["ops.tradingview_tasks"]}'::jsonb),
    ('ai_os_tradingview_tasks', 'mcp_tool', 'Trading Desk Agent', 'read_only', true, 'List queued/completed TradingView chart and screener tasks.', '{"reads":["ops.tradingview_tasks"]}'::jsonb),
    ('ai_os_record_manual_trade', 'mcp_tool', 'Trading Desk Agent', 'write_db_manual_only', true, 'Record a manual actual trade in the local trade activity ledger without broker execution.', '{"writes":["trading.trade_activity_ledger"]}'::jsonb),
    ('ai_os_record_paper_trade', 'mcp_tool', 'Quant Agent', 'write_db_manual_only', true, 'Record a paper/shadow trade or system alert outcome for strategy backtracking.', '{"writes":["trading.trade_activity_ledger"]}'::jsonb),
    ('ai_os_trade_activity', 'mcp_tool', 'Trading Desk Agent', 'read_only', true, 'Read manual, paper, shadow, and alert trade activity.', '{"reads":["trading.trade_activity_ledger","trading.v_paper_trade_summary"]}'::jsonb),
    ('ai_os_refresh_research_hub', 'mcp_tool', 'Knowledge Librarian', 'write_db_manual_only', true, 'Refresh indexed Codex/Claude/cowork research reports and dashboards into the research hub.', '{"runs":["scripts/inventory_ai_research_outputs.py"],"writes":["core.raw_artifacts"]}'::jsonb),
    ('ai_os_research_hub_summary', 'mcp_tool', 'Research Lead', 'read_only', true, 'Read one-place research hub counts by source and artifact family.', '{"reads":["research.v_research_hub_summary"]}'::jsonb),
    ('ai_os_run_public_data_source_check', 'mcp_tool', 'Data Steward', 'write_db_manual_only', true, 'Run public source connectivity checks for SEC/NSE/BSE and store results.', '{"runs":["scripts/check_public_data_sources.py"],"writes":["core.data_source_checks"]}'::jsonb),
    ('ai_os_data_source_checks', 'mcp_tool', 'Data Steward', 'read_only', true, 'Read latest data-source connectivity checks.', '{"reads":["core.v_recent_data_source_checks"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_mcp_candidate_shortlist',
            'ai_os_run_public_data_source_check',
            'ai_os_data_source_checks'
        ]::TEXT[]) AS tool
    ),
    warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'core.mcp_integration_registry',
            'core.data_source_checks'
        ]::TEXT[]) AS obj
    ),
    updated_at = now()
WHERE module_key IN ('data_sources', 'command_center');

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_create_tradingview_task',
            'ai_os_update_tradingview_task',
            'ai_os_tradingview_tasks',
            'ai_os_record_manual_trade',
            'ai_os_record_paper_trade',
            'ai_os_trade_activity'
        ]::TEXT[]) AS tool
    ),
    warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'ops.tradingview_tasks',
            'trading.trade_activity_ledger'
        ]::TEXT[]) AS obj
    ),
    updated_at = now()
WHERE module_key IN ('trading_desk', 'strategy_registry', 'quant_lab');

UPDATE core.control_plane_modules
SET mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_refresh_research_hub',
            'ai_os_research_hub_summary'
        ]::TEXT[]) AS tool
    ),
    warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'research.v_research_hub_summary',
            'core.raw_artifacts'
        ]::TEXT[]) AS obj
    ),
    updated_at = now()
WHERE module_key IN ('research_inbox', 'obsidian_graph');

UPDATE core.data_source_registry
SET status = 'mapped',
    connection_mode = 'mcp_or_browser_task',
    notes = 'TradingView work is now represented by auditable ops.tradingview_tasks. Execution can be handled by reviewed TradingView MCP or Playwright browser adapter.',
    metadata = metadata || '{"task_table":"ops.tradingview_tasks","execution_allowed":false}'::jsonb,
    updated_at = now()
WHERE source_key = 'tradingview_mcp';

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
SELECT 'staged_holding_updates', count(*)::TEXT FROM portfolio.manual_holding_updates WHERE status = 'staged'
UNION ALL
SELECT 'mcp_enabled_tools', count(*)::TEXT FROM agent.tool_registry WHERE enabled = true
UNION ALL
SELECT 'mcp_external_candidates', count(*)::TEXT FROM core.mcp_integration_registry
UNION ALL
SELECT 'approved_mcp_candidates', count(*)::TEXT FROM core.mcp_integration_registry WHERE status IN ('approved_candidate', 'installed')
UNION ALL
SELECT 'tradingview_tasks', count(*)::TEXT FROM ops.tradingview_tasks
UNION ALL
SELECT 'trade_activity_rows', count(*)::TEXT FROM trading.trade_activity_ledger
UNION ALL
SELECT 'research_hub_artifacts', count(*)::TEXT FROM core.raw_artifacts WHERE artifact_type IN ('ai_research_output', 'ai_dashboard_output', 'ai_model_output')
UNION ALL
SELECT 'data_source_checks', count(*)::TEXT FROM core.data_source_checks
UNION ALL
SELECT 'browser_runs', count(*)::TEXT FROM ops.browser_runs
UNION ALL
SELECT 'mcp_audit_events', count(*)::TEXT FROM agent.mcp_audit_log;
