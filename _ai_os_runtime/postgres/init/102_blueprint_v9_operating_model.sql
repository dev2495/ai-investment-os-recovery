CREATE TABLE IF NOT EXISTS core.os_blueprint_versions (
    blueprint_key TEXT PRIMARY KEY,
    blueprint_name TEXT NOT NULL,
    version_label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    note_path TEXT NOT NULL,
    checklist_path TEXT NOT NULL,
    owner_agent TEXT NOT NULL DEFAULT 'Charlie Munger',
    runtime_operator TEXT NOT NULL DEFAULT 'Jarvis',
    adopted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.os_blueprint_domains (
    domain_key TEXT PRIMARY KEY,
    blueprint_key TEXT NOT NULL REFERENCES core.os_blueprint_versions(blueprint_key) ON DELETE CASCADE,
    section_number NUMERIC(6, 2) NOT NULL,
    domain_name TEXT NOT NULL,
    domain_type TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    owner_department TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'planned',
    objective TEXT NOT NULL,
    primary_workspace TEXT,
    canonical_note_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_os_blueprint_domains_blueprint ON core.os_blueprint_domains(blueprint_key);
CREATE INDEX IF NOT EXISTS idx_os_blueprint_domains_status ON core.os_blueprint_domains(status);
CREATE INDEX IF NOT EXISTS idx_os_blueprint_domains_owner ON core.os_blueprint_domains(owner_agent);

CREATE TABLE IF NOT EXISTS core.os_blueprint_requirements (
    requirement_key TEXT PRIMARY KEY,
    blueprint_key TEXT NOT NULL REFERENCES core.os_blueprint_versions(blueprint_key) ON DELETE CASCADE,
    domain_key TEXT NOT NULL REFERENCES core.os_blueprint_domains(domain_key) ON DELETE CASCADE,
    requirement_name TEXT NOT NULL,
    requirement_type TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    current_status TEXT NOT NULL DEFAULT 'planned',
    owner_agent TEXT NOT NULL,
    owner_department TEXT,
    mapped_object_type TEXT,
    mapped_object_key TEXT,
    evidence_note_path TEXT,
    acceptance_criteria TEXT NOT NULL,
    next_action TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_os_blueprint_requirements_blueprint ON core.os_blueprint_requirements(blueprint_key);
CREATE INDEX IF NOT EXISTS idx_os_blueprint_requirements_domain ON core.os_blueprint_requirements(domain_key);
CREATE INDEX IF NOT EXISTS idx_os_blueprint_requirements_status ON core.os_blueprint_requirements(current_status);
CREATE INDEX IF NOT EXISTS idx_os_blueprint_requirements_mapped ON core.os_blueprint_requirements(mapped_object_type, mapped_object_key);

INSERT INTO core.os_blueprint_versions (
    blueprint_key, blueprint_name, version_label, status, note_path, checklist_path,
    owner_agent, runtime_operator, metadata
)
VALUES (
    'investment_os_v9',
    'AI Investment OS - Institutional Master Blueprint',
    'v9.0',
    'canonical',
    'ai memory/00 AI OS/Architecture/AI Investment OS - Institutional Master Blueprint v9.0.md',
    'ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v9.0.md',
    'Charlie Munger',
    'Jarvis',
    '{
      "north_star":"full_ai_hedge_fund_operating_system",
      "primary_interface":"ai_office_gui_plus_charlie_chat",
      "human_in_control":true,
      "live_execution_default":"disabled",
      "storage_contract":"external_ssd_runtime_obsidian_memory",
      "created_from":"2026-07-07 canonical v9 docs"
    }'::jsonb
)
ON CONFLICT (blueprint_key) DO UPDATE SET
    blueprint_name = EXCLUDED.blueprint_name,
    version_label = EXCLUDED.version_label,
    status = EXCLUDED.status,
    note_path = EXCLUDED.note_path,
    checklist_path = EXCLUDED.checklist_path,
    owner_agent = EXCLUDED.owner_agent,
    runtime_operator = EXCLUDED.runtime_operator,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO core.os_blueprint_domains (
    domain_key, blueprint_key, section_number, domain_name, domain_type, owner_agent,
    owner_department, priority, status, objective, primary_workspace, canonical_note_path, metadata
)
VALUES
    ('v9_governance', 'investment_os_v9', 0, 'Canonical Docs And Governance', 'governance', 'Charlie Munger', 'orchestration', 'critical', 'active', 'Keep v9 as the source of truth and enforce evidence-based completion tracking.', 'system', 'ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v9.0.md', '{}'::jsonb),
    ('v9_foundation_runtime', 'investment_os_v9', 1, 'Foundation Runtime', 'runtime', 'Jarvis', 'runtime', 'critical', 'partial', 'Run the warehouse, queue, vector memory, API, MCP, dashboard, and model/provider gates from external SSD.', 'system', NULL, '{}'::jsonb),
    ('v9_data_spine', 'investment_os_v9', 2, 'Data Spine', 'data', 'Data Steward', 'data_engineering', 'critical', 'partial', 'Unify p2cursor, old algo systems, broker exports, manual trades, documents, filings, news, and market data into lineage-backed warehouse tables.', 'system', NULL, '{}'::jsonb),
    ('v9_multi_book_portfolio', 'investment_os_v9', 3, 'Multi-Book Portfolio Brain', 'portfolio', 'Portfolio Manager', 'portfolio', 'critical', 'partial', 'Track every exposure by book, purpose, owner, horizon, thesis, exit logic, and cross-book conflict.', 'portfolio', NULL, '{}'::jsonb),
    ('v9_long_term_office', 'investment_os_v9', 4, 'Long-Term Investing Office', 'investment_book', 'Long-Term Portfolio Manager', 'portfolio', 'high', 'partial', 'Run company research, thesis checks, valuation, Monte Carlo, and long-term committee workflow.', 'portfolio', NULL, '{}'::jsonb),
    ('v9_tactical_office', 'investment_os_v9', 5, 'Tactical Investing Office', 'investment_book', 'Tactical Portfolio Manager', 'tactical', 'high', 'planned', 'Manage catalyst, event, sector, macro, hedge, and temporary opportunity workflows.', 'portfolio', NULL, '{}'::jsonb),
    ('v9_quant_office', 'investment_os_v9', 6, 'Quantitative Strategies Office', 'investment_book', 'Head of Quant', 'quant', 'critical', 'partial', 'Generate, test, optimize, validate, allocate, monitor, and retire systematic strategies.', 'quant', NULL, '{}'::jsonb),
    ('v9_trading_desk', 'investment_os_v9', 7, 'Active Trading Desk', 'investment_book', 'Trading Desk Agent', 'trading', 'critical', 'partial', 'Support discretionary/manual/paper trading, TradingView workflows, options analysis, and trade journal review.', 'trading', NULL, '{}'::jsonb),
    ('v9_research_special_situations', 'investment_os_v9', 8, 'Research Factory And Special Situations', 'research', 'Research Director', 'research', 'critical', 'partial', 'Collect filings/news, detect corporate actions, and route arbitrage/special situation ideas with evidence.', 'research', NULL, '{}'::jsonb),
    ('v9_treasury_hedges_crypto', 'investment_os_v9', 9, 'Treasury Hedges Crypto Commodities', 'investment_book', 'Treasury Analyst', 'risk', 'high', 'planned', 'Track cash, hedges, BTC/ETH, gold, silver, commodities, and macro risk limits.', 'risk', NULL, '{}'::jsonb),
    ('v9_capital_allocation', 'investment_os_v9', 10, 'Capital Allocation Office', 'capital', 'Capital Allocation Officer', 'portfolio', 'critical', 'planned', 'Allocate capital and risk budget across books, clients, and strategies.', 'portfolio', NULL, '{}'::jsonb),
    ('v9_risk_office', 'investment_os_v9', 11, 'Risk Office', 'risk', 'Risk Agent', 'risk', 'critical', 'partial', 'Control limits, stress, VaR, expected shortfall, kill switches, execution gates, and cross-book risk.', 'risk', NULL, '{}'::jsonb),
    ('v9_client_office', 'investment_os_v9', 12, 'Client Office', 'client', 'Client Manager', 'client', 'critical', 'partial', 'Maintain client folios, transactions, buy/sell dates, suitability, reports, and action logs.', 'clients', NULL, '{}'::jsonb),
    ('v9_agent_office', 'investment_os_v9', 13, 'Agent Office And Communication', 'agent_office', 'Chief of Staff', 'orchestration', 'critical', 'partial', 'Make agents role-scoped employees with inboxes, messages, tasks, artifacts, model routes, and personalities.', 'office', NULL, '{}'::jsonb),
    ('v9_committees', 'investment_os_v9', 14, 'Committees', 'committee', 'Charlie Munger', 'orchestration', 'critical', 'partial', 'Run committee rooms with evidence packets, dissent, decisions, approvals, and follow-up tasks.', 'office', NULL, '{}'::jsonb),
    ('v9_mcp_adapters', 'investment_os_v9', 15, 'MCP And External Adapters', 'mcp', 'Jarvis', 'automation', 'critical', 'partial', 'Expose controlled read/write tools for Obsidian, SQL, browser, TradingView, documents, Fincept, brokers, and providers.', 'system', NULL, '{}'::jsonb),
    ('v9_dashboards_live_office', 'investment_os_v9', 16, 'Dashboards And Live Office', 'ui', 'Jarvis', 'software_engineering', 'critical', 'partial', 'Operate through dashboards, command center, agent office, and animated/live office views.', 'command', NULL, '{}'::jsonb),
    ('v9_reports_briefs', 'investment_os_v9', 17, 'Reports And Briefs', 'reporting', 'Document Writer Agent', 'knowledge', 'high', 'partial', 'Produce daily/weekly/monthly reports, committee memos, client-ready outputs, and system reports.', 'reports', NULL, '{}'::jsonb),
    ('v9_model_cost_controls', 'investment_os_v9', 18, 'Model And Cost Controls', 'models', 'AI Engineer', 'ai_engineering', 'critical', 'partial', 'Route local/cloud models by cost, privacy, quality, department, and approval policy.', 'system', NULL, '{}'::jsonb),
    ('v9_production_safety', 'investment_os_v9', 19, 'Production Safety', 'safety', 'Execution Safety Agent', 'risk', 'critical', 'partial', 'Keep broker execution and external actions human-gated until safety, audit, approval, and reconciliation are proven.', 'risk', NULL, '{}'::jsonb),
    ('v9_next_order', 'investment_os_v9', 20, 'Immediate Next Implementation Order', 'roadmap', 'Chief of Staff', 'orchestration', 'critical', 'active', 'Track the next real build order after v9 adoption.', 'system', 'ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v9.0.md', '{}'::jsonb)
ON CONFLICT (domain_key) DO UPDATE SET
    blueprint_key = EXCLUDED.blueprint_key,
    section_number = EXCLUDED.section_number,
    domain_name = EXCLUDED.domain_name,
    domain_type = EXCLUDED.domain_type,
    owner_agent = EXCLUDED.owner_agent,
    owner_department = EXCLUDED.owner_department,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    objective = EXCLUDED.objective,
    primary_workspace = EXCLUDED.primary_workspace,
    canonical_note_path = EXCLUDED.canonical_note_path,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO core.os_blueprint_requirements (
    requirement_key, blueprint_key, domain_key, requirement_name, requirement_type, priority,
    current_status, owner_agent, owner_department, mapped_object_type, mapped_object_key,
    evidence_note_path, acceptance_criteria, next_action, metadata
)
VALUES
    ('v9_req_blueprint_docs', 'investment_os_v9', 'v9_governance', 'Canonical v9 blueprint and checklist', 'documentation', 'critical', 'done', 'Charlie Munger', 'orchestration', 'note', 'AI Investment OS - Institutional Master Blueprint v9.0', 'ai memory/00 AI OS/Architecture/AI Investment OS - Institutional Master Blueprint v9.0.md', 'Blueprint and checklist exist in Obsidian and top-level index points to v9.', 'Keep future implementation work linked to v9.', '{}'::jsonb),
    ('v9_req_external_ssd_runtime', 'investment_os_v9', 'v9_foundation_runtime', 'External SSD runtime workspace', 'runtime', 'critical', 'partial', 'Jarvis', 'runtime', 'control_module', 'command_center', NULL, 'Runtime state lives under _ai_os_runtime on external SSD and services are startable.', 'Add backup/restore proof.', '{}'::jsonb),
    ('v9_req_postgres_warehouse', 'investment_os_v9', 'v9_foundation_runtime', 'Postgres warehouse', 'runtime', 'critical', 'partial', 'Jarvis', 'runtime', 'control_module', 'data_sources', NULL, 'Postgres stores structured portfolio, trading, research, agent, risk, and source lineage state.', 'Add restore test and schema coverage report.', '{}'::jsonb),
    ('v9_req_qdrant_memory', 'investment_os_v9', 'v9_foundation_runtime', 'Qdrant semantic memory', 'runtime', 'high', 'partial', 'Librarian Agent', 'knowledge', 'tool', 'ai_os_search_obsidian_notes', NULL, 'Qdrant-backed retrieval indexes notes, reports, documents, strategies, and journals.', 'Add scheduled reindex and drift alert.', '{}'::jsonb),
    ('v9_req_provider_gates', 'investment_os_v9', 'v9_foundation_runtime', 'Provider readiness and assignment gates', 'runtime', 'critical', 'partial', 'Risk Agent', 'risk', 'tool', 'ai_os_provider_readiness_board', 'ai memory/00 AI OS/Reports/2026-07-07-provider-readiness-board-v1.md', 'Agents can only use providers allowed by readiness and policy gates.', 'Add policy editor and simulator.', '{}'::jsonb),
    ('v9_req_p2cursor_extract', 'investment_os_v9', 'v9_data_spine', 'p2cursor extraction for clients', 'data_pipeline', 'critical', 'partial', 'Data Steward', 'data_engineering', 'data_source', 'p2cursor_archive', NULL, 'All p2cursor clients, holdings, transactions, and buy/sell dates reconciled into warehouse with lineage.', 'Complete all-client extraction and reconciliation.', '{}'::jsonb),
    ('v9_req_algo_archive', 'investment_os_v9', 'v9_data_spine', 'Old algo trading system import', 'data_pipeline', 'high', 'partial', 'Data Steward', 'data_engineering', 'data_source', 'algo_trading_archive', NULL, 'Historical strategies, price data, equity curves, alerts, and components are imported or linked with lineage.', 'Import remaining strategy artifacts and equity curves.', '{}'::jsonb),
    ('v9_req_broker_imports', 'investment_os_v9', 'v9_data_spine', 'Broker reports and trade history', 'data_pipeline', 'critical', 'partial', 'Portfolio Manager', 'portfolio', 'control_module', 'client_folios', NULL, 'Broker exports, manual trades, paper trades, old journals, and current holdings reconcile to client/account books.', 'Finish buy/sell date and journal import.', '{}'::jsonb),
    ('v9_req_market_data', 'investment_os_v9', 'v9_data_spine', 'Daily intraday options and commodity market data', 'data_pipeline', 'critical', 'partial', 'Data Steward', 'data_engineering', 'data_source', 'tradingview_mcp', NULL, 'OHLCV, options chain/OI/IV, futures basis, VIX, crypto, and commodity data are available with freshness checks.', 'Add options/commodity connector and freshness dashboard.', '{}'::jsonb),
    ('v9_req_books_schema', 'investment_os_v9', 'v9_multi_book_portfolio', 'Investment book schema', 'portfolio', 'critical', 'partial', 'Portfolio Manager', 'portfolio', 'book', 'long_term', NULL, 'Books exist for Long-Term, Tactical, Quant, Active Trading, Cash/Treasury, Hedges, and Crypto/Commodity Macro.', 'Add missing book metadata and v9 mandates.', '{}'::jsonb),
    ('v9_req_position_object', 'investment_os_v9', 'v9_multi_book_portfolio', 'Complete position object', 'portfolio', 'critical', 'partial', 'Portfolio Manager', 'portfolio', 'control_module', 'portfolio_office', NULL, 'Every exposure has book, purpose, owner, horizon, thesis/setup, evidence, exit logic, review cadence, and approval state.', 'Backfill missing purpose/thesis/exit fields.', '{}'::jsonb),
    ('v9_req_cross_book_conflicts', 'investment_os_v9', 'v9_multi_book_portfolio', 'Cross-book conflict engine', 'portfolio', 'critical', 'partial', 'Risk Agent', 'risk', 'control_module', 'portfolio_office', NULL, 'Opposing exposures are shown by symbol/client/book with hedge vs alpha intent and risk question.', 'Add action workflow for conflicts.', '{}'::jsonb),
    ('v9_req_symbol_intelligence', 'investment_os_v9', 'v9_multi_book_portfolio', 'Symbol Intelligence v2', 'dashboard', 'critical', 'partial', 'Portfolio Manager', 'portfolio', 'control_module', 'portfolio_office', NULL, 'Symbol page answers why we own/short, by book/client, with latest research, news, filings, setups, and committee notes.', 'Build full UI with links and actions.', '{}'::jsonb),
    ('v9_req_long_term_checks', 'investment_os_v9', 'v9_long_term_office', 'Long-term research checklists', 'research', 'critical', 'partial', 'Long-Term Portfolio Manager', 'portfolio', 'agent', 'Long-Term Portfolio Manager', NULL, 'Business, industry, moat, management, governance, capital allocation, financial quality, forensic, valuation, and sell-discipline checks exist.', 'Expose checklist completion and gaps in UI.', '{}'::jsonb),
    ('v9_req_long_term_monte_carlo', 'investment_os_v9', 'v9_long_term_office', 'Long-term Monte Carlo engine', 'analytics', 'high', 'partial', 'Valuation Agent', 'research', 'tool', 'ai_os_run_long_term_monte_carlo', NULL, 'Monte Carlo models growth, margins, terminal multiple, dilution, debt/cash, impairment risk, expected CAGR, and sensitivity.', 'Wire output into committee memo and UI.', '{}'::jsonb),
    ('v9_req_long_term_committee', 'investment_os_v9', 'v9_long_term_office', 'Long-Term Investment Committee', 'committee', 'high', 'partial', 'Charlie Munger', 'orchestration', 'control_module', 'approval_center', NULL, 'Committee supports reject/watchlist/starter/add/hold/trim/sell/hedge/more-research decisions with evidence.', 'Add full committee room v2.', '{}'::jsonb),
    ('v9_req_tactical_office', 'investment_os_v9', 'v9_tactical_office', 'Tactical investing workflow', 'investment_workflow', 'high', 'planned', 'Tactical Portfolio Manager', 'tactical', 'book', 'tactical', NULL, 'Catalyst, event, macro, sector, hedge, stop/target/time-exit, and overlap checks are workflow-backed.', 'Create schema, agents, and committee.', '{}'::jsonb),
    ('v9_req_strategy_arsenal', 'investment_os_v9', 'v9_quant_office', 'Strategy arsenal and idea intake', 'quant', 'critical', 'partial', 'Strategy Intake Agent', 'quant', 'control_module', 'strategy_registry', NULL, 'User and system-generated ideas enter a paper-first arsenal with hypothesis, data gate, DSL, backtest, and committee state.', 'Add visual strategy builder and intraday templates.', '{}'::jsonb),
    ('v9_req_strategy_validation', 'investment_os_v9', 'v9_quant_office', 'Strategy validation stack', 'quant', 'critical', 'partial', 'Model Validation Agent', 'quant', 'control_module', 'quant_lab', NULL, 'Backtest, optimization, walk-forward, Monte Carlo/bootstrap, regime, factor, capacity, correlation, ruin, promotion, and retirement are tracked.', 'Build dashboard v2 and paper monitor loop.', '{}'::jsonb),
    ('v9_req_tradingview_controller', 'investment_os_v9', 'v9_trading_desk', 'TradingView controller', 'browser_tool', 'critical', 'partial', 'Trading Desk Agent', 'trading', 'data_source', 'tradingview_mcp', NULL, 'Agents can open/capture charts, straddles, ratios, and alert requests with human gates.', 'Harden CDP reconnect and straddle template.', '{}'::jsonb),
    ('v9_req_trade_journal', 'investment_os_v9', 'v9_trading_desk', 'Trade journal and post-trade review', 'trading', 'high', 'partial', 'Trade Journal Learning Agent', 'trading', 'agent', 'Trade Journal Learning Agent', NULL, 'Manual, paper, and historical trades are classified by setup, process, outcome, and improvement loop.', 'Import old journals and build post-trade scoring UI.', '{}'::jsonb),
    ('v9_req_filings_news', 'investment_os_v9', 'v9_research_special_situations', 'NSE/BSE filings and news collectors', 'research_data', 'critical', 'partial', 'News Analyst', 'research', 'control_module', 'research_inbox', NULL, 'Filings/news collectors populate source-backed inboxes with freshness and attachment evidence.', 'Expand collectors and add global/social policy gates.', '{}'::jsonb),
    ('v9_req_special_detectors', 'investment_os_v9', 'v9_research_special_situations', 'Special situation detectors', 'research_workflow', 'critical', 'partial', 'Special Situations Agent', 'research', 'agent', 'Special Situations Agent', NULL, 'Buyback, demerger, reverse merger, delisting, rights, preferential, open offer, tender, arbitrage, and unusual corporate-action detectors exist.', 'Implement missing detector classifiers.', '{}'::jsonb),
    ('v9_req_treasury_crypto', 'investment_os_v9', 'v9_treasury_hedges_crypto', 'Treasury hedges crypto commodities book', 'investment_book', 'high', 'planned', 'Treasury Analyst', 'risk', 'book', 'cash_treasury', NULL, 'Cash drag, hedges, BTC/ETH, gold/silver, commodities, macro drivers, risk limits, and journals are tracked.', 'Create connectors and dashboards.', '{}'::jsonb),
    ('v9_req_capital_allocation', 'investment_os_v9', 'v9_capital_allocation', 'Capital allocation engine', 'capital', 'critical', 'planned', 'Capital Allocation Officer', 'portfolio', 'control_module', 'portfolio_office', NULL, 'Capital and risk budgets by book/client/strategy drive sizing, rebalancing, and opportunity-cost ranking.', 'Build schema and Capital Allocation dashboard.', '{}'::jsonb),
    ('v9_req_risk_engines', 'investment_os_v9', 'v9_risk_office', 'Risk engines', 'risk', 'critical', 'partial', 'Risk Agent', 'risk', 'control_module', 'approval_center', NULL, 'Concentration, liquidity, VaR, expected shortfall, stress, portfolio Monte Carlo, options tail risk, factor risk, and kill switches are tracked.', 'Add VaR/ES/stress/portfolio Monte Carlo.', '{}'::jsonb),
    ('v9_req_client_folio', 'investment_os_v9', 'v9_client_office', 'Client folio manager', 'client', 'critical', 'partial', 'Client Manager', 'client', 'control_module', 'client_folios', NULL, 'Client onboarding, holdings, transactions, NAV, book exposure, concentration, P&L, risk profile, reports, and action log are live.', 'Build Client Folio dashboard and monthly report.', '{}'::jsonb),
    ('v9_req_agent_employee_model', 'investment_os_v9', 'v9_agent_office', 'Agent employee model', 'agent_office', 'critical', 'partial', 'Chief of Staff', 'orchestration', 'control_module', 'command_center', NULL, 'Agents have profile, personality, department, manager, skills, model route, tool permissions, cost cap, inbox, tasks, and artifacts.', 'Add reliability/productivity metrics and profile pages.', '{}'::jsonb),
    ('v9_req_agent_comms', 'investment_os_v9', 'v9_agent_office', 'Agent communication layer', 'agent_office', 'critical', 'partial', 'Jarvis', 'runtime', 'control_module', 'command_center', NULL, 'Agents communicate through tasks, inbox, messages, comments, handoffs, approvals, committee reviews, artifacts, run logs, and notes.', 'Add discussion thread detail UI and task arrows.', '{}'::jsonb),
    ('v9_req_committee_rooms', 'investment_os_v9', 'v9_committees', 'Committee rooms', 'committee', 'critical', 'partial', 'Charlie Munger', 'orchestration', 'control_module', 'approval_center', NULL, 'Executive, Long-Term, Tactical, Strategy, Special Situations, Risk, Capital Allocation, Data/Tool, Client, Model, and Execution committees are represented.', 'Create missing committee workflows and minutes generator.', '{}'::jsonb),
    ('v9_req_mcp_stack', 'investment_os_v9', 'v9_mcp_adapters', 'MCP adapter stack', 'mcp', 'critical', 'partial', 'Jarvis', 'automation', 'tool', 'ai_os_control_plane_snapshot', NULL, 'Controlled tools exist for SQL, Obsidian, Qdrant, browser, TradingView, documents, Fincept, brokers, crypto, reports, approvals, and inbox.', 'Add missing importer/scraper/adapter tools.', '{}'::jsonb),
    ('v9_req_live_ai_office', 'investment_os_v9', 'v9_dashboards_live_office', 'Live AI office GUI', 'ui', 'critical', 'partial', 'Jarvis', 'software_engineering', 'control_module', 'command_center', NULL, 'GUI shows command center, dashboards, agent rooms, hover cards, tasks, committees, approvals, risk wall, activity feed, and eventually animation.', 'Build data-backed task arrows and animated office v1.', '{}'::jsonb),
    ('v9_req_reports', 'investment_os_v9', 'v9_reports_briefs', 'Reports and briefs', 'reporting', 'high', 'partial', 'Document Writer Agent', 'knowledge', 'control_module', 'obsidian_graph', NULL, 'Daily, weekly, monthly, company, strategy, committee, provider, cost, client, and system reports write back to Obsidian/PDF.', 'Schedule recurring briefs and report library.', '{}'::jsonb),
    ('v9_req_model_controls', 'investment_os_v9', 'v9_model_cost_controls', 'Model and cost controls', 'models', 'critical', 'partial', 'AI Engineer', 'ai_engineering', 'control_module', 'approval_center', NULL, 'Per-agent model routes, local daily driver, embeddings, cost ledger, quality eval, cloud approval, privacy, and department policies exist.', 'Benchmark daily driver and add eval set.', '{}'::jsonb),
    ('v9_req_execution_safety', 'investment_os_v9', 'v9_production_safety', 'Production execution safety', 'safety', 'critical', 'partial', 'Execution Safety Agent', 'risk', 'agent', 'Execution Safety Agent', NULL, 'Broker execution is disabled by default; live action requires order preview, risk check, capital check, suitability, kill switch, audit, approval, and reconciliation.', 'Build full order preview and kill switch UI.', '{}'::jsonb)
ON CONFLICT (requirement_key) DO UPDATE SET
    blueprint_key = EXCLUDED.blueprint_key,
    domain_key = EXCLUDED.domain_key,
    requirement_name = EXCLUDED.requirement_name,
    requirement_type = EXCLUDED.requirement_type,
    priority = EXCLUDED.priority,
    current_status = EXCLUDED.current_status,
    owner_agent = EXCLUDED.owner_agent,
    owner_department = EXCLUDED.owner_department,
    mapped_object_type = EXCLUDED.mapped_object_type,
    mapped_object_key = EXCLUDED.mapped_object_key,
    evidence_note_path = EXCLUDED.evidence_note_path,
    acceptance_criteria = EXCLUDED.acceptance_criteria,
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();

CREATE OR REPLACE VIEW core.v_os_blueprint_v9_requirements AS
SELECT
    requirement.requirement_key,
    requirement.requirement_name,
    requirement.requirement_type,
    requirement.priority,
    requirement.current_status,
    requirement.owner_agent,
    requirement.owner_department,
    domain.domain_key,
    domain.domain_name,
    domain.section_number,
    domain.domain_type,
    domain.primary_workspace,
    requirement.mapped_object_type,
    requirement.mapped_object_key,
    CASE
        WHEN requirement.mapped_object_type = 'control_module' THEN module.status
        WHEN requirement.mapped_object_type = 'book' THEN book.status
        WHEN requirement.mapped_object_type = 'agent' THEN profile.status
        WHEN requirement.mapped_object_type = 'tool' THEN CASE WHEN tool.enabled THEN 'enabled' ELSE 'disabled' END
        WHEN requirement.mapped_object_type = 'data_source' THEN source.status
        WHEN requirement.mapped_object_type = 'note' THEN 'note_recorded'
        ELSE NULL
    END AS mapped_object_status,
    CASE
        WHEN requirement.mapped_object_type = 'control_module' AND module.module_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'book' AND book.book_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'agent' AND profile.agent_name IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'tool' AND tool.tool_name IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'data_source' AND source.source_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'note' THEN true
        WHEN requirement.mapped_object_type IS NULL THEN false
        ELSE false
    END AS mapped_object_found,
    requirement.evidence_note_path,
    requirement.acceptance_criteria,
    requirement.next_action,
    requirement.metadata,
    requirement.updated_at
FROM core.os_blueprint_requirements requirement
JOIN core.os_blueprint_domains domain ON domain.domain_key = requirement.domain_key
LEFT JOIN core.control_plane_modules module
    ON requirement.mapped_object_type = 'control_module'
   AND module.module_key = requirement.mapped_object_key
LEFT JOIN books.investment_books book
    ON requirement.mapped_object_type = 'book'
   AND book.book_key = requirement.mapped_object_key
LEFT JOIN agent.profiles profile
    ON requirement.mapped_object_type = 'agent'
   AND profile.agent_name = requirement.mapped_object_key
LEFT JOIN agent.tool_registry tool
    ON requirement.mapped_object_type = 'tool'
   AND tool.tool_name = requirement.mapped_object_key
LEFT JOIN core.data_source_registry source
    ON requirement.mapped_object_type = 'data_source'
   AND source.source_key = requirement.mapped_object_key
WHERE requirement.blueprint_key = 'investment_os_v9';

CREATE OR REPLACE VIEW core.v_os_blueprint_v9_domains AS
SELECT
    domain.domain_key,
    domain.section_number,
    domain.domain_name,
    domain.domain_type,
    domain.owner_agent,
    domain.owner_department,
    domain.priority,
    domain.status,
    domain.objective,
    domain.primary_workspace,
    count(requirement.requirement_key)::BIGINT AS requirement_count,
    count(*) FILTER (WHERE requirement.current_status = 'done')::BIGINT AS done_count,
    count(*) FILTER (WHERE requirement.current_status = 'partial')::BIGINT AS partial_count,
    count(*) FILTER (WHERE requirement.current_status = 'planned')::BIGINT AS planned_count,
    count(*) FILTER (WHERE requirement.current_status = 'blocked')::BIGINT AS blocked_count,
    count(*) FILTER (WHERE requirement.mapped_object_found)::BIGINT AS mapped_count,
    round(
        CASE
            WHEN count(requirement.requirement_key) = 0 THEN 0
            ELSE (
                (
                    count(*) FILTER (WHERE requirement.current_status = 'done') * 100.0
                    + count(*) FILTER (WHERE requirement.current_status = 'partial') * 50.0
                ) / count(requirement.requirement_key)
            )
        END,
        1
    ) AS progress_score,
    min(requirement.next_action) FILTER (WHERE requirement.current_status <> 'done') AS next_action
FROM core.os_blueprint_domains domain
LEFT JOIN core.v_os_blueprint_v9_requirements requirement ON requirement.domain_key = domain.domain_key
WHERE domain.blueprint_key = 'investment_os_v9'
GROUP BY
    domain.domain_key,
    domain.section_number,
    domain.domain_name,
    domain.domain_type,
    domain.owner_agent,
    domain.owner_department,
    domain.priority,
    domain.status,
    domain.objective,
    domain.primary_workspace
ORDER BY domain.section_number;

CREATE OR REPLACE VIEW core.v_os_blueprint_v9_summary AS
SELECT 'domains' AS metric, count(*)::TEXT AS value, 'V9 operating-model domains tracked in the warehouse' AS interpretation
FROM core.os_blueprint_domains
WHERE blueprint_key = 'investment_os_v9'
UNION ALL
SELECT 'requirements', count(*)::TEXT, 'V9 implementation requirements tracked in the warehouse'
FROM core.os_blueprint_requirements
WHERE blueprint_key = 'investment_os_v9'
UNION ALL
SELECT 'done_requirements', count(*)::TEXT, 'Requirements marked done with evidence'
FROM core.os_blueprint_requirements
WHERE blueprint_key = 'investment_os_v9' AND current_status = 'done'
UNION ALL
SELECT 'partial_requirements', count(*)::TEXT, 'Requirements with partial runtime implementation'
FROM core.os_blueprint_requirements
WHERE blueprint_key = 'investment_os_v9' AND current_status = 'partial'
UNION ALL
SELECT 'planned_requirements', count(*)::TEXT, 'Requirements not implemented yet'
FROM core.os_blueprint_requirements
WHERE blueprint_key = 'investment_os_v9' AND current_status = 'planned'
UNION ALL
SELECT 'mapped_requirements', count(*)::TEXT, 'Requirements linked to live runtime objects'
FROM core.v_os_blueprint_v9_requirements
WHERE mapped_object_found;

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent, ui_workspace,
    description, warehouse_objects, mcp_tools, fincept_component, next_action, metadata
)
VALUES (
    'blueprint_v9_operating_model',
    'Blueprint v9 Operating Model',
    'governance',
    'active',
    'critical',
    'Charlie Munger',
    'system',
    'Machine-readable v9 hedge-fund OS blueprint coverage registry. Tracks domains, requirements, owners, mapped runtime objects, and next actions.',
    ARRAY['core.os_blueprint_versions','core.os_blueprint_domains','core.os_blueprint_requirements','core.v_os_blueprint_v9_domains','core.v_os_blueprint_v9_requirements','core.v_os_blueprint_v9_summary']::TEXT[],
    ARRAY['ai_os_blueprint_v9_summary','ai_os_blueprint_v9_requirements']::TEXT[],
    NULL,
    'Use this registry to drive implementation order and prevent gaps between the Obsidian plan and runtime.',
    '{"blueprint_key":"investment_os_v9","seed_data_allowed":false,"config_metadata":true}'::jsonb
)
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
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_blueprint_v9_summary', 'mcp_tool', 'Charlie Munger', 'read_only', true, 'Read v9 blueprint domain and coverage summary from the warehouse.', '{"reads":["core.v_os_blueprint_v9_summary","core.v_os_blueprint_v9_domains"],"blueprint_key":"investment_os_v9"}'::jsonb),
    ('ai_os_blueprint_v9_requirements', 'mcp_tool', 'Chief of Staff', 'read_only', true, 'Read v9 blueprint requirements, mapped runtime objects, acceptance criteria, and next actions.', '{"reads":["core.v_os_blueprint_v9_requirements"],"blueprint_key":"investment_os_v9"}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

