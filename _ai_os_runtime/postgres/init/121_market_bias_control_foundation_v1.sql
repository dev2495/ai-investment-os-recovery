CREATE TABLE IF NOT EXISTS market.corporate_actions (
    id BIGSERIAL PRIMARY KEY,
    action_key TEXT NOT NULL UNIQUE,
    symbol_id BIGINT REFERENCES trading.symbols(id),
    symbol TEXT NOT NULL,
    exchange TEXT,
    action_type TEXT NOT NULL,
    announcement_date DATE,
    ex_date DATE,
    record_date DATE,
    effective_date DATE,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE SET NULL,
    source_event_id BIGINT REFERENCES research.filing_events(id) ON DELETE SET NULL,
    source_url TEXT,
    terms JSONB NOT NULL DEFAULT '{}'::jsonb,
    verification_status TEXT NOT NULL DEFAULT 'detected'
        CHECK (verification_status IN ('detected', 'needs_review', 'verified', 'rejected')),
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT corporate_actions_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(terms))
);

CREATE INDEX IF NOT EXISTS idx_corporate_actions_symbol_date
ON market.corporate_actions (symbol, coalesce(effective_date, record_date, announcement_date) DESC);

CREATE TABLE IF NOT EXISTS market.corporate_action_adjustment_factors (
    id BIGSERIAL PRIMARY KEY,
    corporate_action_id BIGINT NOT NULL REFERENCES market.corporate_actions(id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id),
    effective_date DATE NOT NULL,
    price_factor NUMERIC NOT NULL CHECK (price_factor > 0),
    volume_factor NUMERIC NOT NULL DEFAULT 1 CHECK (volume_factor > 0),
    factor_method TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (status IN ('pending_review', 'verified', 'applied', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (corporate_action_id, symbol_id, effective_date),
    CONSTRAINT corporate_action_factors_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(evidence))
);

CREATE TABLE IF NOT EXISTS market.universe_memberships (
    id BIGSERIAL PRIMARY KEY,
    universe_key TEXT NOT NULL,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id),
    valid_from DATE NOT NULL,
    valid_to DATE,
    membership_status TEXT NOT NULL DEFAULT 'observed',
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_ref TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'observed'
        CHECK (verification_status IN ('observed', 'verified', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (universe_key, symbol_id, valid_from),
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT universe_memberships_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(evidence))
);

CREATE INDEX IF NOT EXISTS idx_universe_memberships_point_in_time
ON market.universe_memberships (universe_key, valid_from, valid_to, symbol_id);

CREATE OR REPLACE FUNCTION market.sync_corporate_actions_from_filings(p_limit INTEGER DEFAULT 5000)
RETURNS TABLE (rows_touched BIGINT, verified_rows BIGINT)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH source_rows AS (
        SELECT
            filing.id AS filing_id,
            event.id AS event_id,
            upper(coalesce(nullif(event.symbol, ''), filing.symbol)) AS symbol,
            filing.exchange,
            CASE
                WHEN event.event_type <> 'board_action' THEN event.event_type
                WHEN lower(filing.title) ~ 'bonus' THEN 'bonus'
                WHEN lower(filing.title) ~ 'split|sub-division' THEN 'split'
                WHEN lower(filing.title) ~ 'dividend' THEN 'dividend'
                ELSE 'record_date_notice'
            END AS action_type,
            filing.filed_at::date AS announcement_date,
            CASE WHEN terms.ex_date ~ '^\d{4}-\d{2}-\d{2}$' THEN terms.ex_date::date END AS ex_date,
            CASE WHEN terms.record_date ~ '^\d{4}-\d{2}-\d{2}$' THEN terms.record_date::date END AS record_date,
            filing.source_system_id,
            filing.source_url,
            event.opportunity_score,
            event.risk_score,
            event.status AS event_status,
            terms.id AS terms_id,
            terms.raw_terms,
            terms.confidence
        FROM research.filing_events event
        JOIN research.corporate_filings filing ON filing.id = event.filing_id
        LEFT JOIN LATERAL (
            SELECT special.*
            FROM research.special_situation_terms special
            WHERE special.filing_event_id = event.id OR special.filing_id = filing.id
            ORDER BY special.updated_at DESC, special.id DESC
            LIMIT 1
        ) terms ON true
        WHERE coalesce(event.symbol, filing.symbol) IS NOT NULL
          AND (
              event.event_type IN (
                  'reverse_merger', 'demerger', 'merger', 'scheme_arrangement',
                  'buyback', 'open_offer', 'delisting', 'rights_issue',
                  'preferential_allotment', 'asset_sale', 'pledge_change',
                  'arbitrage_watch'
              )
              OR (
                  event.event_type = 'board_action'
                  AND lower(filing.title) ~ 'dividend|bonus|split|sub-division|record date|book closure'
              )
          )
        ORDER BY filing.filed_at DESC, event.id DESC
        LIMIT greatest(1, p_limit)
    ), upserted AS (
        INSERT INTO market.corporate_actions (
            action_key, symbol_id, symbol, exchange, action_type,
            announcement_date, ex_date, record_date, effective_date,
            source_system_id, source_filing_id, source_event_id, source_url,
            terms, verification_status, updated_at
        )
        SELECT
            'filing:' || source.filing_id || ':event:' || source.event_id,
            symbol.id,
            source.symbol,
            source.exchange,
            source.action_type,
            source.announcement_date,
            source.ex_date,
            source.record_date,
            coalesce(source.ex_date, source.record_date),
            source.source_system_id,
            source.filing_id,
            source.event_id,
            source.source_url,
            jsonb_strip_nulls(jsonb_build_object(
                'special_terms_id', source.terms_id,
                'raw_terms', source.raw_terms,
                'confidence', source.confidence,
                'opportunity_score', source.opportunity_score,
                'risk_score', source.risk_score,
                'event_status', source.event_status,
                'source', 'research.filing_events'
            )),
            CASE WHEN source.terms_id IS NOT NULL AND source.confidence >= 0.8 THEN 'needs_review' ELSE 'detected' END,
            now()
        FROM source_rows source
        LEFT JOIN LATERAL (
            SELECT candidate.id
            FROM trading.symbols candidate
            WHERE upper(candidate.symbol) = source.symbol
              AND (source.exchange IS NULL OR candidate.exchange = source.exchange)
            ORDER BY candidate.active DESC, candidate.id
            LIMIT 1
        ) symbol ON true
        ON CONFLICT (action_key) DO UPDATE SET
            symbol_id = coalesce(EXCLUDED.symbol_id, market.corporate_actions.symbol_id),
            action_type = EXCLUDED.action_type,
            announcement_date = EXCLUDED.announcement_date,
            ex_date = coalesce(EXCLUDED.ex_date, market.corporate_actions.ex_date),
            record_date = coalesce(EXCLUDED.record_date, market.corporate_actions.record_date),
            effective_date = coalesce(EXCLUDED.effective_date, market.corporate_actions.effective_date),
            source_url = EXCLUDED.source_url,
            terms = EXCLUDED.terms,
            updated_at = now()
        RETURNING verification_status
    )
    SELECT count(*)::BIGINT, count(*) FILTER (WHERE verification_status = 'verified')::BIGINT
    FROM upserted;
END;
$$;

CREATE OR REPLACE VIEW market.v_ohlcv_adjusted AS
SELECT
    ohlcv.ts,
    ohlcv.symbol_id,
    ohlcv.timeframe,
    ohlcv.open AS raw_open,
    ohlcv.high AS raw_high,
    ohlcv.low AS raw_low,
    ohlcv.close AS raw_close,
    ohlcv.volume AS raw_volume,
    ohlcv.open * factors.price_factor AS adjusted_open,
    ohlcv.high * factors.price_factor AS adjusted_high,
    ohlcv.low * factors.price_factor AS adjusted_low,
    ohlcv.close * factors.price_factor AS adjusted_close,
    ohlcv.volume * factors.volume_factor AS adjusted_volume,
    factors.price_factor,
    factors.volume_factor,
    factors.factor_count,
    ohlcv.source_system_id
FROM trading.ohlcv ohlcv
CROSS JOIN LATERAL (
    SELECT
        coalesce(exp(sum(ln(factor.price_factor)) FILTER (
            WHERE factor.effective_date > ohlcv.ts::date
        )), 1)::NUMERIC AS price_factor,
        coalesce(exp(sum(ln(factor.volume_factor)) FILTER (
            WHERE factor.effective_date > ohlcv.ts::date
        )), 1)::NUMERIC AS volume_factor,
        count(*) FILTER (WHERE factor.effective_date > ohlcv.ts::date)::INTEGER AS factor_count
    FROM market.corporate_action_adjustment_factors factor
    WHERE factor.symbol_id = ohlcv.symbol_id
      AND factor.status IN ('verified', 'applied')
) factors;

INSERT INTO market.universe_memberships (
    universe_key, symbol_id, valid_from, membership_status,
    source_system_id, source_ref, verification_status, evidence
)
SELECT
    'LEGACY_ALGO_CURRENT_SNAPSHOT',
    symbol.id,
    current_date,
    'active_current_snapshot',
    source.id,
    'legacy_algo_symbol_snapshot:' || current_date,
    'observed',
    jsonb_build_array(jsonb_build_object(
        'source', 'trading.symbols',
        'captured_at', now(),
        'limitation', 'Current snapshot only; no historical membership is inferred.'
    ))
FROM trading.symbols symbol
JOIN core.source_systems source ON source.name = 'algo trading terminal'
WHERE symbol.exchange = 'NSE' AND symbol.active = true
ON CONFLICT (universe_key, symbol_id, valid_from) DO NOTHING;

SELECT * FROM market.sync_corporate_actions_from_filings(5000);

CREATE OR REPLACE VIEW market.v_market_bias_control_readiness AS
SELECT
    'corporate_actions'::TEXT AS control_key,
    count(*)::BIGINT AS observed_rows,
    count(*) FILTER (WHERE symbol_id IS NOT NULL)::BIGINT AS mapped_rows,
    count(*) FILTER (WHERE verification_status = 'verified')::BIGINT AS verified_rows,
    (SELECT count(*) FROM market.corporate_action_adjustment_factors WHERE status IN ('verified', 'applied'))::BIGINT AS applied_rows,
    CASE
        WHEN count(*) = 0 THEN 'missing'
        WHEN count(*) FILTER (WHERE verification_status = 'verified') = count(*)
             AND (SELECT count(*) FROM market.corporate_action_adjustment_factors WHERE status IN ('verified', 'applied')) > 0
            THEN 'verified'
        ELSE 'needs_verification'
    END AS readiness_status,
    'Review detected filing events, verify dates/ratios, then approve factors before adjusted OHLCV is used.'::TEXT AS next_required_action
FROM market.corporate_actions
UNION ALL
SELECT
    'point_in_time_universe',
    count(*)::BIGINT,
    count(*)::BIGINT,
    count(*) FILTER (WHERE verification_status = 'verified')::BIGINT,
    count(*) FILTER (WHERE valid_to IS NOT NULL)::BIGINT,
    CASE
        WHEN count(*) = 0 THEN 'missing'
        WHEN count(DISTINCT valid_from) >= 12
             AND count(*) FILTER (WHERE verification_status = 'verified') = count(*)
            THEN 'verified'
        ELSE 'current_snapshot_only'
    END,
    'Ingest dated index and tradable-universe constituent history; do not backfill current members into past periods.'
FROM market.universe_memberships;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_market_bias_control_readiness', 'market_data_quality', 'Data Quality Agent',
    'read_only', true,
    'Reads corporate-action adjustment and point-in-time universe readiness without mutating raw OHLCV.',
    '{"reads":["market.v_market_bias_control_readiness","market.corporate_actions","market.universe_memberships","market.v_ohlcv_adjusted"],"execution_allowed":false,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
