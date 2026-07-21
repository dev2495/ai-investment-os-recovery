BEGIN;

INSERT INTO research.feed_registry (
    feed_key, feed_name, feed_type, provider, url, geography, symbols, topics,
    status, owner_agent, source_system_id, metadata
)
VALUES
    (
        'soic_substack', 'SOIC investment research', 'investor_blog_rss',
        'SOIC', 'https://soic.substack.com/feed', 'India', ARRAY[]::TEXT[],
        ARRAY['long_term_investing','industry_research','management','mental_models']::TEXT[],
        'active', 'Social/Twitter Triage Agent',
        (SELECT id FROM core.source_systems WHERE name='Global market news basket'),
        '{"adapter":"rss_http","cred_required":false,"claim_policy":"corroborate_before_investment_use","source_class":"followed_investor"}'::jsonb
    ),
    (
        'safal_niveshak_rss', 'Safal Niveshak', 'investor_blog_rss',
        'Safal Niveshak', 'https://www.safalniveshak.com/feed/', 'India', ARRAY[]::TEXT[],
        ARRAY['value_investing','behavior','mental_models','company_research']::TEXT[],
        'active', 'Social/Twitter Triage Agent',
        (SELECT id FROM core.source_systems WHERE name='Global market news basket'),
        '{"adapter":"rss_http","cred_required":false,"claim_policy":"corroborate_before_investment_use","source_class":"followed_investor"}'::jsonb
    )
ON CONFLICT (feed_key) DO UPDATE SET
    feed_name=EXCLUDED.feed_name, feed_type=EXCLUDED.feed_type,
    provider=EXCLUDED.provider, url=EXCLUDED.url, geography=EXCLUDED.geography,
    symbols=EXCLUDED.symbols, topics=EXCLUDED.topics, status=EXCLUDED.status,
    owner_agent=EXCLUDED.owner_agent, source_system_id=EXCLUDED.source_system_id,
    metadata=EXCLUDED.metadata, updated_at=now();

INSERT INTO agent.workflow_schedules (
    schedule_key, workflow_key, owner_agent, skill_key, schedule_name,
    cadence_seconds, priority, enabled, approval_required, next_run_at, metadata
)
VALUES
    ('options-surface-monitor','trading_monitor_cycle_v2','Options Analyst',
     'options_iv_greeks_review','Options chain, OI, Greeks and structure monitor',
     900,'high',true,false,now()+interval '2 minutes',
     '{"underlyings":["NIFTY","BANKNIFTY"],"paper_only":true,"broker_order_allowed":false}'::jsonb),
    ('volatility-regime-monitor','trading_monitor_cycle_v2','Volatility Agent',
     'volatility_regime_review','Volatility surface and regime monitor',
     1800,'high',true,false,now()+interval '4 minutes',
     '{"term_structure":true,"skew":true,"paper_only":true}'::jsonb),
    ('technical-scanner-monitor','trading_monitor_cycle_v2','Technical Analyst',
     'technical_market_analysis','Multi-timeframe technical scanner',
     900,'high',true,false,now()+interval '3 minutes',
     '{"timeframes":["5m","15m","1h","1d"],"requires_price_confirmation":true,"broker_order_allowed":false}'::jsonb),
    ('curated-news-monitor','research_factory_cycle_v2','News Analyst',
     'global_market_news_digest','Curated news and materiality monitor',
     900,'high',true,false,now()+interval '5 minutes',
     '{"source_url_required":true,"rumor_label_required":true}'::jsonb),
    ('followed-investor-monitor','research_factory_cycle_v2','Social/Twitter Triage Agent',
     'social_watchlist_triage','Followed investors and research blogs monitor',
     3600,'medium',true,false,now()+interval '8 minutes',
     '{"feeds":["soic_substack","safal_niveshak_rss"],"corroboration_required":true,"capital_action_allowed":false}'::jsonb)
ON CONFLICT (schedule_key) DO UPDATE SET
    workflow_key=EXCLUDED.workflow_key, owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key, schedule_name=EXCLUDED.schedule_name,
    cadence_seconds=EXCLUDED.cadence_seconds, priority=EXCLUDED.priority,
    enabled=EXCLUDED.enabled, approval_required=EXCLUDED.approval_required,
    metadata=EXCLUDED.metadata, updated_at=now();

COMMIT;
