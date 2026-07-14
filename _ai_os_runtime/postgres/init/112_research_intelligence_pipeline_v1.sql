INSERT INTO research.feed_registry (
    feed_key, feed_name, feed_type, provider, url, geography,
    symbols, topics, status, owner_agent, source_system_id, metadata
)
VALUES
    (
        'rbi_press_releases',
        'Reserve Bank of India Press Releases',
        'news_rss',
        'Reserve Bank of India',
        'https://www.rbi.org.in/pressreleases_rss.xml',
        'India',
        ARRAY[]::TEXT[],
        ARRAY['macro','monetary_policy','banking','india']::TEXT[],
        'active',
        'Macro Researcher',
        (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'),
        '{"adapter":"rss_http","cred_required":false,"source_class":"official_regulator"}'::jsonb
    ),
    (
        'federal_reserve_press',
        'Federal Reserve Press Releases',
        'news_rss',
        'Federal Reserve Board',
        'https://www.federalreserve.gov/feeds/press_all.xml',
        'United States',
        ARRAY[]::TEXT[],
        ARRAY['macro','monetary_policy','banking','united_states']::TEXT[],
        'active',
        'Macro Researcher',
        (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'),
        '{"adapter":"rss_http","cred_required":false,"source_class":"official_central_bank"}'::jsonb
    ),
    (
        'ecb_press_releases',
        'European Central Bank Releases',
        'news_rss',
        'European Central Bank',
        'https://www.ecb.europa.eu/rss/press.html',
        'Europe',
        ARRAY[]::TEXT[],
        ARRAY['macro','monetary_policy','banking','europe']::TEXT[],
        'active',
        'Macro Researcher',
        (SELECT id FROM core.source_systems WHERE name = 'Global market news basket'),
        '{"adapter":"rss_http","cred_required":false,"source_class":"official_central_bank"}'::jsonb
    )
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
    metadata = research.feed_registry.metadata || EXCLUDED.metadata,
    updated_at = now();

UPDATE agent.skills
SET status = 'active',
    execution_mode = 'scheduled_source_pipeline',
    config = config || '{
        "pipeline":"run_strategy_discovery_scheduler.py",
        "daemon_interval_seconds":3600,
        "nse_bse_enabled":true,
        "filing_pdf_extraction_enabled":true,
        "source_url_required":true,
        "autonomous_live_execution_allowed":false
    }'::jsonb,
    updated_at = now()
WHERE skill_key IN (
    'nse_bse_announcement_monitor',
    'analyze_corporate_filing',
    'corporate_action_detector',
    'global_market_news_digest',
    'news_to_dashboard_alert'
);

UPDATE agent.tool_registry
SET config = config || '{
        "source_pipeline_v1":true,
        "official_macro_feeds":["RBI","Federal Reserve","ECB"],
        "bse_adapter":"AnnSubCategoryGetData",
        "bse_pagination":true,
        "material_first_pdf_extraction":true,
        "retry_limit":3,
        "live_execution_allowed":false
    }'::jsonb
WHERE tool_name IN (
    'ai_os_run_nse_bse_filing_collector',
    'ai_os_extract_filing_pdf_text',
    'ai_os_ingest_market_news',
    'ai_os_run_strategy_discovery_scheduler'
);

UPDATE core.control_plane_modules
SET next_action = 'Monitor the hourly source-intelligence loop, investigate partial feed failures, and review source-backed agent handoffs before research promotion.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'research_inbox', 'runtime');
