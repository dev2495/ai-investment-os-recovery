BEGIN;

INSERT INTO research.watchlists (
    watchlist_key,
    watchlist_name,
    purpose,
    status,
    owner_agent,
    created_by,
    metadata
)
VALUES (
    'company_research_following',
    'Followed company research',
    'Official filings, authorized news, catalysts, thesis changes and review dates for approved Research Cases',
    'active',
    'Research Director',
    'AI OS migration 242',
    jsonb_build_object(
        'filings_refresh_hours', 24,
        'news_refresh_hours', 6,
        'private_data_allowed', false,
        'external_writes_allowed', false
    )
)
ON CONFLICT (watchlist_key) DO UPDATE
SET watchlist_name = EXCLUDED.watchlist_name,
    purpose = EXCLUDED.purpose,
    status = 'active',
    owner_agent = EXCLUDED.owner_agent,
    metadata = research.watchlists.metadata || EXCLUDED.metadata,
    updated_at = now();

WITH target_watchlist AS (
    SELECT id
    FROM research.watchlists
    WHERE watchlist_key = 'company_research_following'
), approved_cases AS (
    SELECT DISTINCT ON (upper(coalesce(exchange, 'NSE')), upper(ticker))
        id,
        upper(coalesce(exchange, 'NSE')) AS exchange,
        upper(ticker) AS symbol,
        company_name,
        priority,
        mandate,
        owner_agent,
        status,
        created_at,
        updated_at
    FROM research.research_cases
    WHERE status IN ('collecting', 'active', 'review', 'blocked', 'completed')
      AND ticker IS NOT NULL
      AND btrim(ticker) <> ''
    ORDER BY upper(coalesce(exchange, 'NSE')), upper(ticker), updated_at DESC, id DESC
)
INSERT INTO research.watchlist_items (
    watchlist_id,
    symbol,
    exchange,
    company_name,
    item_type,
    status,
    priority,
    thesis,
    review_on,
    owner_agent,
    source_kind,
    source_ref,
    created_by,
    evidence,
    metadata,
    created_at,
    updated_at
)
SELECT
    w.id,
    c.symbol,
    c.exchange,
    c.company_name,
    'research_case',
    'active',
    CASE WHEN c.priority IN ('low', 'normal', 'medium', 'high', 'critical') THEN c.priority ELSE 'medium' END,
    c.mandate,
    current_date + 30,
    c.owner_agent,
    'research_case',
    'research_case:' || c.id,
    'AI OS migration 242',
    '[]'::jsonb,
    jsonb_build_object(
        'research_case_id', c.id,
        'case_status', c.status,
        'followed_since', c.created_at,
        'filings_refresh_hours', 24,
        'news_refresh_hours', 6,
        'monitoring_enabled', true
    ),
    c.created_at,
    now()
FROM approved_cases c
CROSS JOIN target_watchlist w
ON CONFLICT (watchlist_id, exchange, symbol, item_type) DO UPDATE
SET company_name = EXCLUDED.company_name,
    status = 'active',
    priority = EXCLUDED.priority,
    thesis = EXCLUDED.thesis,
    owner_agent = EXCLUDED.owner_agent,
    source_kind = EXCLUDED.source_kind,
    source_ref = EXCLUDED.source_ref,
    metadata = research.watchlist_items.metadata || EXCLUDED.metadata,
    updated_at = now();

CREATE OR REPLACE VIEW research.v_company_research_monitoring AS
SELECT
    wi.id AS watchlist_item_id,
    wi.exchange,
    wi.symbol,
    wi.company_name,
    wi.priority,
    wi.created_at AS followed_since,
    wi.review_on AS next_review_on,
    rc.id AS research_case_id,
    rc.status AS research_case_status,
    rc.decision_readiness,
    rc.last_progress_at,
    filing.id AS latest_filing_id,
    filing.title AS latest_filing_title,
    filing.filed_at AS latest_filing_at,
    filing.source_url AS latest_filing_url,
    filing.extraction_status AS latest_filing_extraction_status,
    news.id AS latest_news_id,
    news.title AS latest_news_title,
    coalesce(news.published_at, news.captured_at) AS latest_news_at,
    news.source_url AS latest_news_url,
    event.event_type AS latest_case_event_type,
    event.occurred_at AS latest_case_event_at,
    wi.metadata AS monitoring_policy
FROM research.watchlist_items wi
JOIN research.watchlists w
  ON w.id = wi.watchlist_id
 AND w.watchlist_key = 'company_research_following'
LEFT JOIN LATERAL (
    SELECT c.*
    FROM research.research_cases c
    WHERE upper(coalesce(c.exchange, 'NSE')) = upper(wi.exchange)
      AND upper(c.ticker) = upper(wi.symbol)
      AND c.status IN ('collecting', 'active', 'review', 'blocked', 'completed')
    ORDER BY c.updated_at DESC, c.id DESC
    LIMIT 1
) rc ON true
LEFT JOIN LATERAL (
    SELECT f.*
    FROM research.corporate_filings f
    WHERE upper(coalesce(f.exchange, wi.exchange)) = upper(wi.exchange)
      AND upper(f.symbol) = upper(wi.symbol)
    ORDER BY coalesce(f.filed_at, f.created_at) DESC, f.id DESC
    LIMIT 1
) filing ON true
LEFT JOIN LATERAL (
    SELECT n.*
    FROM market.news_items n
    WHERE upper(wi.symbol) = ANY (
        SELECT upper(s) FROM unnest(n.symbols) AS s
    )
    ORDER BY coalesce(n.published_at, n.captured_at) DESC, n.id DESC
    LIMIT 1
) news ON true
LEFT JOIN LATERAL (
    SELECT e.*
    FROM research.research_case_events e
    WHERE e.research_case_id = rc.id
    ORDER BY e.occurred_at DESC, e.id DESC
    LIMIT 1
) event ON true
WHERE wi.status = 'active';

COMMENT ON VIEW research.v_company_research_monitoring IS
'Bounded operator view of approved followed companies, their latest case state, official filing, authorized news and durable event. Proposed/unapproved cases are excluded.';

COMMIT;
