CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS strategy;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS core.raw_artifacts (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    artifact_type TEXT NOT NULL,
    title TEXT,
    source_url TEXT,
    local_path TEXT,
    content_hash TEXT,
    mime_type TEXT,
    sensitivity TEXT NOT NULL DEFAULT 'private',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE NULLS NOT DISTINCT (source_system_id, source_url, local_path, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_raw_artifacts_type ON core.raw_artifacts (artifact_type);
CREATE INDEX IF NOT EXISTS idx_raw_artifacts_captured_at ON core.raw_artifacts (captured_at DESC);

CREATE TABLE IF NOT EXISTS knowledge.obsidian_notes (
    id BIGSERIAL PRIMARY KEY,
    vault_path TEXT NOT NULL,
    note_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    note_type TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    frontmatter JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash TEXT,
    body_summary TEXT,
    last_modified_at TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_obsidian_notes_type ON knowledge.obsidian_notes (note_type);
CREATE INDEX IF NOT EXISTS idx_obsidian_notes_tags ON knowledge.obsidian_notes USING GIN (tags);

CREATE TABLE IF NOT EXISTS knowledge.note_links (
    id BIGSERIAL PRIMARY KEY,
    from_note_id BIGINT NOT NULL REFERENCES knowledge.obsidian_notes(id) ON DELETE CASCADE,
    to_note_path TEXT NOT NULL,
    link_text TEXT,
    link_type TEXT NOT NULL DEFAULT 'wikilink',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_note_links_from ON knowledge.note_links (from_note_id);
CREATE INDEX IF NOT EXISTS idx_note_links_to ON knowledge.note_links (to_note_path);

CREATE TABLE IF NOT EXISTS knowledge.vector_documents (
    id BIGSERIAL PRIMARY KEY,
    collection_name TEXT NOT NULL,
    qdrant_point_id TEXT NOT NULL,
    source_table TEXT,
    source_id TEXT,
    title TEXT,
    text_hash TEXT,
    embedding_model TEXT,
    chunk_index INTEGER,
    chunk_text_preview TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (collection_name, qdrant_point_id)
);

CREATE INDEX IF NOT EXISTS idx_vector_documents_source ON knowledge.vector_documents (source_table, source_id);

CREATE TABLE IF NOT EXISTS portfolio.clients (
    id BIGSERIAL PRIMARY KEY,
    client_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    risk_profile TEXT,
    investment_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    sensitivity TEXT NOT NULL DEFAULT 'client_private',
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE portfolio.accounts
    ADD COLUMN IF NOT EXISTS client_id BIGINT REFERENCES portfolio.clients(id);

CREATE TABLE IF NOT EXISTS portfolio.positions (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT REFERENCES portfolio.accounts(id),
    symbol TEXT NOT NULL,
    exchange TEXT,
    instrument_type TEXT,
    quantity NUMERIC,
    average_price NUMERIC,
    market_price NUMERIC,
    market_value NUMERIC,
    unrealized_pnl NUMERIC,
    as_of TIMESTAMPTZ NOT NULL,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE NULLS NOT DISTINCT (account_id, symbol, exchange, instrument_type, as_of)
);

CREATE INDEX IF NOT EXISTS idx_positions_as_of ON portfolio.positions (as_of DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON portfolio.positions (symbol);

CREATE TABLE IF NOT EXISTS portfolio.holding_theses (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    exchange TEXT,
    thesis_status TEXT NOT NULL DEFAULT 'needs_review',
    thesis_note_path TEXT,
    valuation_note_path TEXT,
    risk_note_path TEXT,
    last_reviewed_at TIMESTAMPTZ,
    next_review_due_at TIMESTAMPTZ,
    conviction_score NUMERIC,
    valuation_range JSONB NOT NULL DEFAULT '{}'::jsonb,
    risks JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE NULLS NOT DISTINCT (symbol, exchange)
);

CREATE TABLE IF NOT EXISTS research.corporate_filings (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_name TEXT NOT NULL,
    exchange TEXT,
    symbol TEXT,
    company_name TEXT,
    filing_type TEXT,
    event_type TEXT,
    title TEXT NOT NULL,
    filed_at TIMESTAMPTZ,
    source_url TEXT,
    local_path TEXT,
    content_hash TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'captured',
    extracted_text TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_name, source_url, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_corporate_filings_filed_at ON research.corporate_filings (filed_at DESC);
CREATE INDEX IF NOT EXISTS idx_corporate_filings_symbol ON research.corporate_filings (symbol);
CREATE INDEX IF NOT EXISTS idx_corporate_filings_event_type ON research.corporate_filings (event_type);

CREATE TABLE IF NOT EXISTS research.filing_events (
    id BIGSERIAL PRIMARY KEY,
    filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    thesis TEXT,
    opportunity_score NUMERIC,
    risk_score NUMERIC,
    urgency TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'new',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    assigned_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_filing_events_type ON research.filing_events (event_type);
CREATE INDEX IF NOT EXISTS idx_filing_events_status ON research.filing_events (status);

CREATE TABLE IF NOT EXISTS market.news_items (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT,
    title TEXT NOT NULL,
    publisher TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbols TEXT[] NOT NULL DEFAULT '{}',
    topics TEXT[] NOT NULL DEFAULT '{}',
    geography TEXT,
    sentiment NUMERIC,
    relevance_score NUMERIC,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE NULLS NOT DISTINCT (source_name, source_url)
);

CREATE INDEX IF NOT EXISTS idx_news_published_at ON market.news_items (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_symbols ON market.news_items USING GIN (symbols);
CREATE INDEX IF NOT EXISTS idx_news_topics ON market.news_items USING GIN (topics);

CREATE TABLE IF NOT EXISTS market.social_items (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    author_handle TEXT,
    source_url TEXT,
    title TEXT,
    body TEXT,
    posted_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbols TEXT[] NOT NULL DEFAULT '{}',
    topics TEXT[] NOT NULL DEFAULT '{}',
    relevance_score NUMERIC,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE NULLS NOT DISTINCT (source_name, source_url)
);

CREATE INDEX IF NOT EXISTS idx_social_posted_at ON market.social_items (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_symbols ON market.social_items USING GIN (symbols);

CREATE TABLE IF NOT EXISTS research.ideas (
    id BIGSERIAL PRIMARY KEY,
    idea_type TEXT NOT NULL,
    title TEXT NOT NULL,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    source_kind TEXT,
    source_ref TEXT,
    thesis TEXT,
    catalyst TEXT,
    expected_timeframe TEXT,
    opportunity_score NUMERIC,
    risk_score NUMERIC,
    status TEXT NOT NULL DEFAULT 'captured',
    owner_agent TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    output_note_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_ideas_type ON research.ideas (idea_type);
CREATE INDEX IF NOT EXISTS idx_research_ideas_status ON research.ideas (status);
CREATE INDEX IF NOT EXISTS idx_research_ideas_symbols ON research.ideas USING GIN (symbols);

CREATE TABLE IF NOT EXISTS trading.trade_journals (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    trade_id BIGINT REFERENCES portfolio.trades(id),
    journal_ts TIMESTAMPTZ,
    symbol TEXT,
    strategy TEXT,
    setup_type TEXT,
    timeframe TEXT,
    market_condition TEXT,
    entry_reason TEXT,
    exit_reason TEXT,
    rule_violations TEXT[] NOT NULL DEFAULT '{}',
    emotional_state TEXT,
    execution_quality NUMERIC,
    r_multiple NUMERIC,
    pnl NUMERIC,
    note_path TEXT,
    raw_text TEXT,
    extracted_features JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_journals_symbol ON trading.trade_journals (symbol);
CREATE INDEX IF NOT EXISTS idx_trade_journals_ts ON trading.trade_journals (journal_ts DESC);
CREATE INDEX IF NOT EXISTS idx_trade_journals_setup ON trading.trade_journals (setup_type);

CREATE TABLE IF NOT EXISTS strategy.strategy_candidates (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    source_kind TEXT,
    source_ref TEXT,
    hypothesis TEXT NOT NULL,
    universe TEXT,
    timeframe TEXT,
    entry_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    exit_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'idea',
    owner_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS strategy.backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id),
    run_status TEXT NOT NULL DEFAULT 'queued',
    data_start DATE,
    data_end DATE,
    universe TEXT,
    timeframe TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy ON strategy.backtest_runs (strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON strategy.backtest_runs (run_status);

CREATE TABLE IF NOT EXISTS agent.tasks (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority TEXT NOT NULL DEFAULT 'normal',
    approval_required BOOLEAN NOT NULL DEFAULT false,
    source_kind TEXT,
    source_ref TEXT,
    output_format TEXT,
    output_note_path TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent.tasks (status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_owner ON agent.tasks (owner_agent);

CREATE TABLE IF NOT EXISTS agent.inbox_items (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES agent.tasks(id),
    title TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    priority TEXT NOT NULL DEFAULT 'normal',
    recommended_action TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_workspace TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inbox_status ON agent.inbox_items (status);
CREATE INDEX IF NOT EXISTS idx_inbox_workspace ON agent.inbox_items (target_workspace);

CREATE TABLE IF NOT EXISTS agent.approvals (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES agent.tasks(id),
    approval_type TEXT NOT NULL,
    title TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    requested_action JSONB NOT NULL DEFAULT '{}'::jsonb,
    rationale TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON agent.approvals (status);
CREATE INDEX IF NOT EXISTS idx_approvals_type ON agent.approvals (approval_type);

CREATE TABLE IF NOT EXISTS agent.tool_registry (
    id BIGSERIAL PRIMARY KEY,
    tool_name TEXT NOT NULL UNIQUE,
    tool_type TEXT NOT NULL,
    owning_agent TEXT,
    permission_level TEXT NOT NULL DEFAULT 'read_only',
    enabled BOOLEAN NOT NULL DEFAULT true,
    description TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.model_routes (
    id BIGSERIAL PRIMARY KEY,
    route_name TEXT NOT NULL UNIQUE,
    task_class TEXT NOT NULL,
    default_provider TEXT NOT NULL,
    default_model TEXT NOT NULL,
    escalation_provider TEXT,
    escalation_model TEXT,
    max_cost_tier TEXT NOT NULL DEFAULT 'local',
    notes TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ops.browser_runs (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES agent.tasks(id),
    run_type TEXT NOT NULL,
    target_url TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    screenshot_path TEXT,
    extracted_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_browser_runs_status ON ops.browser_runs (status);
CREATE INDEX IF NOT EXISTS idx_browser_runs_target ON ops.browser_runs (target_url);

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, description, config)
VALUES
    ('obsidian_note_index', 'local_filesystem', 'Librarian Agent', 'read_only', 'Indexes vault markdown notes and note links.', '{}'::jsonb),
    ('obsidian_writeback', 'local_filesystem', 'Jarvis', 'write_with_approval', 'Writes completed reports and decisions back to structured vault folders.', '{}'::jsonb),
    ('postgres_read_model', 'database', 'Data Steward', 'read_only', 'Read-only SQL access for agents over portfolio, trading, filings, news, and task state.', '{}'::jsonb),
    ('qdrant_vector_search', 'vector_db', 'Jarvis', 'read_only', 'Semantic retrieval over notes, filings, journals, reports, and documents.', '{}'::jsonb),
    ('browser_research_runner', 'browser', 'Research Agent', 'read_only', 'Browser collection for NSE/BSE/global news and public source inspection.', '{}'::jsonb),
    ('tradingview_signal_reader', 'webhook', 'Trading Desk', 'read_only', 'Reads TradingView webhook events and old strategy signals.', '{}'::jsonb)
ON CONFLICT (tool_name) DO NOTHING;

INSERT INTO agent.model_routes (route_name, task_class, default_provider, default_model, escalation_provider, escalation_model, max_cost_tier, notes)
VALUES
    ('jarvis_intake', 'routing', 'ollama', 'qwen3:8b', 'codex_or_cloud', '', 'local', 'Cheap local model handles task classification and routing.'),
    ('daily_brief', 'summarization', 'ollama', 'qwen3:8b', 'cloud_optional', '', 'local', 'Local first; cloud only for long/complex synthesis.'),
    ('filing_analysis', 'financial_reasoning', 'ollama', 'qwen3:14b', 'codex_or_cloud', '', 'hybrid', 'Escalate when filings are long, legal-heavy, or special-situation sensitive.'),
    ('trade_journal_learning', 'pattern_extraction', 'ollama', 'qwen3:8b', 'codex_or_cloud', '', 'local', 'Extract setup, emotions, rule violations, and strategy lessons from old journals.'),
    ('coding_escalation', 'software_engineering', 'codex', 'gpt-5-codex', NULL, NULL, 'codex', 'Use Codex for implementation and verification.')
ON CONFLICT (route_name) DO NOTHING;

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
VALUES
    ('obsidian vault', 'markdown_vault', '/Volumes/Devarsh SSD/Obsidian memory ', 'private', 'active', 'Permanent memory graph and research archive.'),
    ('nse filings', 'public_web', 'https://www.nseindia.com', 'public', 'planned', 'Corporate announcements, filings, actions, results, and special situation triggers.'),
    ('bse filings', 'public_web', 'https://www.bseindia.com', 'public', 'planned', 'Corporate announcements, filings, actions, results, and special situation triggers.'),
    ('global news feeds', 'public_web_or_api', 'multiple', 'public', 'planned', 'Curated global market and company news; exact providers to be configured.'),
    ('twitter x research feed', 'public_web_or_api', 'multiple', 'public', 'planned', 'Curated social/news signal source; use official/API-compliant methods where possible.')
ON CONFLICT (name) DO NOTHING;
