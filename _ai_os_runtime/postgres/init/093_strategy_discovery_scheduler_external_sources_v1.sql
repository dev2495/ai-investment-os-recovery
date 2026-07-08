CREATE TABLE IF NOT EXISTS market.news_ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    feed_keys TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    feeds_checked INTEGER NOT NULL DEFAULT 0,
    items_seen INTEGER NOT NULL DEFAULT 0,
    items_upserted INTEGER NOT NULL DEFAULT 0,
    research_ideas_created INTEGER NOT NULL DEFAULT 0,
    inbox_items_created INTEGER NOT NULL DEFAULT 0,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    created_by TEXT NOT NULL DEFAULT 'News Analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_ingestion_runs_created
ON market.news_ingestion_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_ingestion_runs_status
ON market.news_ingestion_runs (status);

CREATE TABLE IF NOT EXISTS strategy.strategy_discovery_scheduler_runs (
    id BIGSERIAL PRIMARY KEY,
    job_key TEXT NOT NULL DEFAULT 'strategy_discovery_scheduler',
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    scheduler_interval_seconds INTEGER NOT NULL DEFAULT 3600,
    command TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    adapter_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovery_run_key TEXT,
    discovery_run_id BIGINT REFERENCES strategy.strategy_discovery_runs(id) ON DELETE SET NULL,
    discovered_count INTEGER NOT NULL DEFAULT 0,
    generated_idea_count INTEGER NOT NULL DEFAULT 0,
    optimizer_routed_count INTEGER NOT NULL DEFAULT 0,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    next_run_after TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'AI OS Agent Daemon',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_scheduler_job_time
ON strategy.strategy_discovery_scheduler_runs (job_key, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_discovery_scheduler_status
ON strategy.strategy_discovery_scheduler_runs (status);

CREATE OR REPLACE VIEW market.v_news_ingestion_runs AS
SELECT
    id,
    run_key,
    status,
    feed_keys,
    feeds_checked,
    items_seen,
    items_upserted,
    research_ideas_created,
    inbox_items_created,
    sample_payload,
    error_message,
    started_at,
    finished_at,
    duration_ms,
    created_by,
    created_at
FROM market.news_ingestion_runs
ORDER BY started_at DESC, id DESC;

CREATE OR REPLACE VIEW market.v_latest_news_items AS
SELECT
    id,
    source_name,
    source_url,
    title,
    publisher,
    author,
    published_at,
    captured_at,
    symbols,
    topics,
    geography,
    sentiment,
    relevance_score,
    raw_payload
FROM market.news_items
ORDER BY coalesce(published_at, captured_at) DESC, id DESC;

CREATE OR REPLACE VIEW strategy.v_strategy_discovery_scheduler_runs AS
SELECT
    sched.id,
    sched.job_key,
    sched.run_key,
    sched.status,
    sched.scheduler_interval_seconds,
    sched.command,
    sched.adapter_summary,
    sched.discovery_run_key,
    sched.discovery_run_id,
    disc.status AS discovery_status,
    sched.discovered_count,
    sched.generated_idea_count,
    sched.optimizer_routed_count,
    sched.output_payload,
    sched.error_message,
    sched.started_at,
    sched.finished_at,
    sched.duration_ms,
    sched.next_run_after,
    CASE
        WHEN sched.finished_at IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (now() - sched.finished_at)) / 60
    END AS minutes_since_finished,
    sched.created_by,
    sched.created_at
FROM strategy.strategy_discovery_scheduler_runs sched
LEFT JOIN strategy.strategy_discovery_runs disc ON disc.id = sched.discovery_run_id
ORDER BY sched.started_at DESC, sched.id DESC;

INSERT INTO research.feed_registry (
    feed_key, feed_name, feed_type, provider, url, geography, symbols, topics, status, owner_agent, source_system_id, metadata
)
VALUES
    ('moneycontrol_markets_rss', 'Moneycontrol Markets RSS', 'news_rss', 'Moneycontrol', 'https://www.moneycontrol.com/rss/marketreports.xml', 'India', ARRAY[]::TEXT[], ARRAY['markets','india','equities']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('moneycontrol_business_rss', 'Moneycontrol Business RSS', 'news_rss', 'Moneycontrol', 'https://www.moneycontrol.com/rss/business.xml', 'India', ARRAY[]::TEXT[], ARRAY['business','india','company_news']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('moneycontrol_ipo_rss', 'Moneycontrol IPO RSS', 'news_rss', 'Moneycontrol', 'https://www.moneycontrol.com/rss/iponews.xml', 'India', ARRAY[]::TEXT[], ARRAY['ipo','primary_market','india']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('et_markets_rss', 'Economic Times Markets RSS', 'news_rss', 'Economic Times', 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms', 'India', ARRAY[]::TEXT[], ARRAY['markets','india','macro']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('et_economy_rss', 'Economic Times Economy RSS', 'news_rss', 'Economic Times', 'https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms', 'India', ARRAY[]::TEXT[], ARRAY['economy','macro','india']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('livemint_markets_rss', 'Livemint Markets RSS', 'news_rss', 'Livemint', 'https://www.livemint.com/rss/markets', 'India', ARRAY[]::TEXT[], ARRAY['markets','india','company_news']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb),
    ('business_standard_markets_rss', 'Business Standard Markets RSS', 'news_rss', 'Business Standard', 'https://www.business-standard.com/rss/markets-106.rss', 'India', ARRAY[]::TEXT[], ARRAY['markets','india','company_news']::TEXT[], 'active', 'News Analyst', (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'), '{"adapter":"rss_http","cred_required":false}'::jsonb)
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

UPDATE research.feed_registry
SET status = 'blocked_credentials',
    metadata = metadata || '{"adapter":"browser_or_api","blocked_reason":"requires authenticated X/Twitter browser session or API credentials","cred_required":true}'::jsonb,
    updated_at = now()
WHERE feed_key = 'x_curated_handles';

UPDATE research.feed_registry
SET status = 'active',
    updated_at = now()
WHERE feed_key IN ('nse_announcements', 'bse_announcements');

UPDATE core.data_source_registry
SET status = 'active',
    notes = notes || ' RSS ingestion is active through market.news_ingestion_runs.',
    updated_at = now()
WHERE source_key = 'global_news';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_ingest_market_news', 'mcp_tool', 'News Analyst', 'write_db', true,
     'Ingest active RSS/news feeds from research.feed_registry into market.news_items and create source-backed catalyst research ideas.',
     '{"script":"_ai_os_runtime/scripts/ingest_market_news.py","reads":["research.feed_registry","trading.symbols","portfolio.positions"],"writes":["market.news_ingestion_runs","market.news_items","research.ideas","agent.inbox_items"],"seed_data_allowed":false}'::jsonb),
    ('ai_os_run_strategy_discovery_scheduler', 'mcp_tool', 'Strategy Discovery Agent', 'write_db_scheduled', true,
     'Run external source adapters and then run automatic strategy discovery on the AI OS daemon cadence.',
     '{"script":"_ai_os_runtime/scripts/run_strategy_discovery_scheduler.py","reads":["research.feed_registry","market.news_items","research.corporate_filings","strategy.generated_ideas"],"writes":["market.news_ingestion_runs","strategy.strategy_discovery_scheduler_runs","strategy.strategy_discovery_runs","strategy.strategy_discovery_candidates"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_strategy_discovery_scheduler_runs', 'mcp_tool', 'Strategy Discovery Agent', 'read_only', true,
     'Read strategy discovery scheduler runs, adapter summaries, and latest RSS/news ingestion runs.',
     '{"reads":["strategy.v_strategy_discovery_scheduler_runs","market.v_news_ingestion_runs","market.v_latest_news_items"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'market.news_ingestion_runs',
            'market.v_news_ingestion_runs',
            'market.news_items',
            'market.v_latest_news_items',
            'strategy.strategy_discovery_scheduler_runs',
            'strategy.v_strategy_discovery_scheduler_runs'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_ingest_market_news',
            'ai_os_run_strategy_discovery_scheduler',
            'ai_os_strategy_discovery_scheduler_runs'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Strategy discovery now has a scheduled adapter path; monitor adapter failures and promote only evidence-backed candidates.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'research_inbox', 'trading_desk', 'runtime');
