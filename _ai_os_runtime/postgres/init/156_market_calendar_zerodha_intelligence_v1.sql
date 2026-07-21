BEGIN;

CREATE TABLE IF NOT EXISTS market.zerodha_instrument_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'started',
    exchange_scope TEXT[] NOT NULL DEFAULT '{}',
    rows_seen BIGINT NOT NULL DEFAULT 0,
    rows_upserted BIGINT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_by TEXT NOT NULL DEFAULT 'Market Data Engineer'
);

CREATE TABLE IF NOT EXISTS market.zerodha_instruments (
    instrument_token BIGINT PRIMARY KEY,
    exchange_token BIGINT,
    trading_symbol TEXT NOT NULL,
    name TEXT,
    last_price NUMERIC,
    expiry DATE,
    strike NUMERIC,
    tick_size NUMERIC,
    lot_size INTEGER,
    instrument_type TEXT,
    segment TEXT,
    exchange TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_zerodha_instruments_lookup
    ON market.zerodha_instruments (exchange, trading_symbol, active);
CREATE INDEX IF NOT EXISTS idx_zerodha_instruments_options
    ON market.zerodha_instruments (name, expiry, strike, instrument_type)
    WHERE active AND instrument_type IN ('CE', 'PE');

CREATE TABLE IF NOT EXISTS market.market_calendar_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    rows_seen BIGINT NOT NULL DEFAULT 0,
    rows_upserted BIGINT NOT NULL DEFAULT 0,
    target_url TEXT,
    http_status INTEGER,
    sample_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Corporate Events Analyst'
);

CREATE TABLE IF NOT EXISTS market.corporate_event_calendar (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    symbol TEXT NOT NULL,
    company_name TEXT,
    event_date DATE NOT NULL,
    event_type TEXT NOT NULL,
    purpose TEXT,
    description TEXT,
    source_url TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_key, exchange, symbol, event_date, event_type, purpose)
);

CREATE INDEX IF NOT EXISTS idx_corporate_event_calendar_upcoming
    ON market.corporate_event_calendar (event_date, event_type, symbol);

CREATE TABLE IF NOT EXISTS market.exchange_holidays (
    id BIGSERIAL PRIMARY KEY,
    exchange TEXT NOT NULL,
    segment TEXT NOT NULL,
    holiday_date DATE NOT NULL,
    holiday_name TEXT NOT NULL,
    session_status TEXT NOT NULL DEFAULT 'closed',
    source_url TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'official_exchange_circular',
    notes TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exchange, segment, holiday_date)
);

INSERT INTO market.exchange_holidays (
    exchange, segment, holiday_date, holiday_name, session_status, source_url, notes
)
SELECT 'NSE', 'equity_and_fo', item.holiday_date::date, item.holiday_name,
       'closed', 'https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf',
       CASE WHEN item.holiday_date='2026-11-10' THEN 'Muhurat trading timings are announced separately by NSE.'
            ELSE 'Official NSE 2026 trading holiday circular.' END
FROM jsonb_to_recordset(
    '[{"holiday_date":"2026-01-26","holiday_name":"Republic Day"},
      {"holiday_date":"2026-03-03","holiday_name":"Holi"},
      {"holiday_date":"2026-03-26","holiday_name":"Shri Ram Navami"},
      {"holiday_date":"2026-03-31","holiday_name":"Shri Mahavir Jayanti"},
      {"holiday_date":"2026-04-03","holiday_name":"Good Friday"},
      {"holiday_date":"2026-04-14","holiday_name":"Dr. Baba Saheb Ambedkar Jayanti"},
      {"holiday_date":"2026-05-01","holiday_name":"Maharashtra Day"},
      {"holiday_date":"2026-05-28","holiday_name":"Bakri Id"},
      {"holiday_date":"2026-06-26","holiday_name":"Muharram"},
      {"holiday_date":"2026-09-14","holiday_name":"Ganesh Chaturthi"},
      {"holiday_date":"2026-10-02","holiday_name":"Mahatma Gandhi Jayanti"},
      {"holiday_date":"2026-10-20","holiday_name":"Dussehra"},
      {"holiday_date":"2026-11-10","holiday_name":"Diwali-Balipratipada"},
      {"holiday_date":"2026-11-24","holiday_name":"Guru Nanak Jayanti"},
      {"holiday_date":"2026-12-25","holiday_name":"Christmas"}]'::jsonb
) AS item(holiday_date text, holiday_name text)
ON CONFLICT (exchange, segment, holiday_date) DO UPDATE SET
    holiday_name=EXCLUDED.holiday_name,
    session_status=EXCLUDED.session_status,
    source_url=EXCLUDED.source_url,
    source_kind='official_exchange_circular',
    notes=EXCLUDED.notes,
    captured_at=now();

CREATE OR REPLACE VIEW market.v_upcoming_corporate_events AS
WITH latest_positions AS (
    SELECT DISTINCT ON (upper(symbol)) upper(symbol) AS symbol
    FROM portfolio.positions
    ORDER BY upper(symbol), as_of DESC
), active_watchlist AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM research.v_watchlist_board
    WHERE status='active'
)
SELECT event.id, event.source_key, event.exchange, event.symbol, event.company_name,
       event.event_date, event.event_type, event.purpose, event.description,
       event.source_url, event.captured_at,
       (position.symbol IS NOT NULL) AS in_portfolio,
       (watch.symbol IS NOT NULL) AS on_watchlist,
       CASE WHEN position.symbol IS NOT NULL THEN 'portfolio'
            WHEN watch.symbol IS NOT NULL THEN 'watchlist' ELSE 'market' END AS relevance_scope
FROM market.corporate_event_calendar event
LEFT JOIN latest_positions position ON position.symbol=upper(event.symbol)
LEFT JOIN active_watchlist watch ON watch.symbol=upper(event.symbol)
WHERE event.event_date >= current_date
ORDER BY event.event_date,
         CASE WHEN position.symbol IS NOT NULL THEN 0 WHEN watch.symbol IS NOT NULL THEN 1 ELSE 2 END,
         event.symbol;

CREATE OR REPLACE VIEW market.v_upcoming_exchange_holidays AS
SELECT id, exchange, segment, holiday_date, holiday_name, session_status,
       source_url, source_kind, notes, captured_at,
       (holiday_date-current_date) AS days_away
FROM market.exchange_holidays
WHERE holiday_date >= current_date
ORDER BY holiday_date, exchange, segment;

CREATE OR REPLACE VIEW market.v_curated_news_brief AS
WITH current_symbols AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM portfolio.positions
    WHERE as_of >= (SELECT max(as_of)-interval '1 day' FROM portfolio.positions)
    UNION
    SELECT DISTINCT upper(symbol)
    FROM research.v_watchlist_board WHERE status='active'
), enriched AS (
    SELECT news.*,
           ARRAY(
               SELECT symbol FROM current_symbols
               WHERE symbol=ANY(news.symbols)
                  OR symbol=ANY(regexp_split_to_array(upper(news.title),'[^A-Z0-9&]+'))
               ORDER BY symbol
           ) AS matched_symbols,
           CASE WHEN news.source_name ILIKE 'NSE%' OR news.source_name ILIKE 'BSE%'
                     OR news.source_name ILIKE 'RBI%' OR news.source_name ILIKE 'ECB%'
                     OR news.source_name ILIKE 'Federal Reserve%' THEN 0.25 ELSE 0 END AS official_source_bonus,
           CASE WHEN coalesce(news.published_at,news.captured_at)>news.captured_at+interval '6 hours'
                THEN news.captured_at ELSE coalesce(news.published_at,news.captured_at) END AS effective_published_at
    FROM market.news_items news
), ranked AS (
    SELECT enriched.*,
           least(1.0,coalesce(relevance_score,0.35)+official_source_bonus
               +CASE WHEN cardinality(matched_symbols)>0 THEN 0.35 ELSE 0 END
               +CASE WHEN effective_published_at>=now()-interval '24 hours' THEN 0.10 ELSE 0 END
           ) AS materiality_score
    FROM enriched
)
SELECT id, source_name, source_url, title, publisher, published_at, captured_at,
       effective_published_at, symbols, topics, matched_symbols, geography,
       sentiment, relevance_score, materiality_score,
       CASE
           WHEN cardinality(matched_symbols)>0
               THEN 'Tagged to a current holding or watchlist symbol: '||array_to_string(matched_symbols,', ')||'.'
           WHEN official_source_bonus>0
               THEN 'Official-source macro or market information; review for portfolio-wide effects.'
           WHEN topics && ARRAY['ipo','earnings','corporate_action','markets']::text[]
               THEN 'Potential catalyst or market-structure item requiring analyst triage.'
           ELSE 'Fresh market intelligence retained for relevance screening.'
       END AS why_it_matters,
       CASE WHEN cardinality(matched_symbols)>0 THEN 'Company Analyst'
            WHEN official_source_bonus>0 THEN 'Macro Analyst' ELSE 'News Analyst' END AS owner_agent
FROM ranked
WHERE effective_published_at>=now()-interval '7 days'
ORDER BY materiality_score DESC, effective_published_at DESC, id DESC;

CREATE OR REPLACE VIEW research.v_filing_intelligence_brief AS
WITH latest_positions AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM portfolio.positions
    WHERE as_of >= (SELECT max(as_of)-interval '1 day' FROM portfolio.positions)
), active_watchlist AS (
    SELECT DISTINCT upper(symbol) AS symbol
    FROM research.v_watchlist_board WHERE status='active'
)
SELECT filing.filing_id, filing.source_name, filing.exchange, filing.symbol,
       filing.company_name, filing.title, filing.filing_type,
       coalesce(filing.event_type,filing.filing_event_type,'routine_filing') AS event_type,
       filing.filed_at, filing.source_url, filing.attachment_url,
       filing.extraction_status, filing.pdf_page_count, filing.opportunity_score,
       filing.risk_score, filing.urgency, filing.event_status,
       (position.symbol IS NOT NULL) AS in_portfolio,
       (watch.symbol IS NOT NULL) AS on_watchlist,
       CASE
           WHEN coalesce(filing.event_type,filing.filing_event_type) IN
                ('merger','demerger','reverse_merger','scheme_arrangement','open_offer',
                 'buyback','delisting','rights_issue','preferential_allotment','insolvency')
               THEN 'Potential special situation. Extract terms, timeline, approvals, entitlement, spread, and failure conditions.'
           WHEN lower(filing.title) LIKE '%financial result%'
               THEN 'Results filing. Compare growth, margins, cash conversion, leverage, guidance, and thesis deltas.'
           WHEN lower(filing.title) LIKE '%board meeting%'
               THEN 'Scheduled board event. Monitor the stated agenda and follow-up exchange submission.'
           WHEN lower(filing.title) LIKE '%order%' OR lower(filing.title) LIKE '%contract%'
               THEN 'Operating catalyst. Verify size, counterparty, execution period, margins, and cancellation terms.'
           ELSE 'Corporate disclosure captured. Review materiality against the investment thesis and risk register.'
       END AS why_it_matters,
       CASE WHEN filing.extraction_status IN ('extracted','indexed') AND filing.pdf_page_count>0
            THEN 'Document text is available for evidence-backed analyst review.'
            ELSE 'Headline classification only; PDF extraction is required before a substantive conclusion.' END AS evidence_state,
       CASE WHEN position.symbol IS NOT NULL THEN 'critical'
            WHEN watch.symbol IS NOT NULL THEN 'high'
            WHEN coalesce(filing.opportunity_score,0)>=0.7 OR coalesce(filing.risk_score,0)>=0.7 THEN 'high'
            ELSE coalesce(filing.urgency,'normal') END AS priority
FROM research.v_corporate_filing_inbox filing
LEFT JOIN latest_positions position ON position.symbol=upper(filing.symbol)
LEFT JOIN active_watchlist watch ON watch.symbol=upper(filing.symbol)
ORDER BY CASE WHEN position.symbol IS NOT NULL THEN 0 WHEN watch.symbol IS NOT NULL THEN 1 ELSE 2 END,
         greatest(coalesce(filing.opportunity_score,0),coalesce(filing.risk_score,0)) DESC,
         filing.filed_at DESC NULLS LAST;

ALTER TABLE core.integration_jobs DROP CONSTRAINT IF EXISTS integration_jobs_executor_allowlist;
ALTER TABLE core.integration_jobs ADD CONSTRAINT integration_jobs_executor_allowlist CHECK (
    executor_key IN ('market_news_ingestion','filings_collection','tick_ohlcv_aggregation',
        'tradingview_quote_refresh','public_source_check','provider_readiness',
        'legacy_market_data_ingestion','dhan_read_sync','zerodha_read_sync',
        'zerodha_market_sync','market_calendar_refresh')
);

UPDATE core.data_source_registry
SET notes='Primary read-only broker and market-data adapter for account snapshots, daily instruments, quotes, bounded historical candles, derivatives and MCX. Daily interactive login remains required; order writes are absent.',
    metadata=metadata||'{"datasets":["holdings","positions","orders","trades","funds","instruments","quotes","historical_candles","option_chain_snapshots"],"instrument_cache_retains_expired_contracts":true,"execution_allowed":false}'::jsonb,
    updated_at=now()
WHERE source_key='zerodha_live';

UPDATE core.source_connector_profiles
SET config=config||'{"market_data":["instruments","quotes","historical_candles","option_chain_snapshots"],"instrument_cache_retains_expired_contracts":true,"option_greeks_source":"not_provided_by_kite","execution_allowed":false}'::jsonb,
    notes='Primary GET-only Zerodha account and market-data adapter. Daily instrument dumps are cached so expired derivative history is not lost. IV and Greeks remain null until a validated calculation engine is installed.',
    updated_at=now()
WHERE connector_key='zerodha_live_connector';

INSERT INTO core.integration_jobs (
    job_key,plugin_key,job_name,job_type,executor_key,schedule_cron,timezone,
    enabled,run_mode,overlap_policy,timeout_seconds,parameters,approval_required,owner_agent,notes
) VALUES
    ('zerodha_market_snapshot_5m','data_source:zerodha_live_connector',
     'Zerodha read-only market snapshot','poll','zerodha_market_sync','*/5 * * * 1-5',
     'Asia/Kolkata',false,'manual_or_schedule','skip',180,
     '{"modes":["quotes","options"],"underlyings":["NIFTY","BANKNIFTY"],"broker_write_allowed":false}'::jsonb,
     false,'Market Data Engineer','Enable after the daily Zerodha access token passes a GET-only health check.'),
    ('nse_market_calendar_daily','data_source:nse_filings_connector',
     'NSE corporate event calendar refresh','import','market_calendar_refresh','10 7 * * *',
     'Asia/Kolkata',true,'manual_or_schedule','skip',120,
     '{"lookback_days":1,"lookahead_days":45,"source":"nse_event_calendar"}'::jsonb,
     false,'Corporate Events Analyst','Official NSE event-calendar refresh; no broker credential is used.')
ON CONFLICT (job_key) DO UPDATE SET
    executor_key=EXCLUDED.executor_key,schedule_cron=EXCLUDED.schedule_cron,
    enabled=EXCLUDED.enabled,parameters=EXCLUDED.parameters,notes=EXCLUDED.notes,updated_at=now();

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config)
VALUES
    ('ai_os_refresh_market_calendar','mcp_tool','Corporate Events Analyst','network_read',true,
     'Refresh official NSE board-meeting and result dates into the durable warehouse.',
     '{"runs":["scripts/collect_market_calendar.py"],"writes":["market.market_calendar_runs","market.corporate_event_calendar"],"execution_allowed":false}'::jsonb),
    ('ai_os_upcoming_market_events','mcp_tool','Corporate Events Analyst','read_only',true,
     'Read upcoming result, board, corporate-action and holiday events with portfolio/watchlist relevance.',
     '{"reads":["market.v_upcoming_corporate_events","market.v_upcoming_exchange_holidays"]}'::jsonb),
    ('ai_os_zerodha_market_read','mcp_tool','Market Data Engineer','broker_read',true,
     'Read and cache Zerodha instruments, quotes, bounded historical candles and option-chain snapshots.',
     '{"runs":["scripts/sync_zerodha_market_data.py"],"writes":["market.zerodha_instruments","market.price_quotes","trading.ohlcv","trading.option_chain_snapshots"],"broker_write_allowed":false}'::jsonb),
    ('ai_os_curated_news_brief','mcp_tool','News Analyst','read_only',true,
     'Read ranked source-linked news with holding/watchlist impact and deterministic why-it-matters labels.',
     '{"reads":["market.v_curated_news_brief"],"llm_required":false}'::jsonb),
    ('ai_os_filing_intelligence_brief','mcp_tool','Filings Analyst','read_only',true,
     'Read filing intelligence with materiality, evidence state, and required analysis.',
     '{"reads":["research.v_filing_intelligence_brief"],"llm_required":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
