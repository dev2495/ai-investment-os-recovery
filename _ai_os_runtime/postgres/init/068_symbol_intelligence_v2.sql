CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence AS
WITH base AS (
    SELECT *
    FROM books.v_symbol_book_exposure
),
conflicts AS (
    SELECT
        client_id,
        symbol,
        exchange,
        count(*) AS conflict_count,
        jsonb_agg(
            jsonb_build_object(
                'conflict_type', conflict_type,
                'severity', severity,
                'description', description,
                'affected_books', affected_books,
                'offset_ratio', offset_ratio
            )
            ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                     latest_as_of DESC NULLS LAST
        ) AS conflict_details
    FROM books.v_cross_book_conflicts
    GROUP BY client_id, symbol, exchange
),
gaps AS (
    SELECT
        client_code,
        symbol,
        count(*) AS gap_count,
        array_agg(DISTINCT gap_type ORDER BY gap_type) AS gap_types,
        jsonb_agg(
            jsonb_build_object(
                'gap_type', gap_type,
                'severity', severity,
                'description', gap_description,
                'owner_agent', owner_agent
            )
            ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                     gap_type
        ) AS gap_details
    FROM books.v_book_assignment_gaps
    GROUP BY client_code, symbol
),
book_details AS (
    SELECT
        client_code,
        symbol,
        exchange,
        jsonb_agg(
            jsonb_build_object(
                'book_key', book_key,
                'book_name', book_name,
                'purpose_key', purpose_key,
                'purpose_name', purpose_name,
                'owner_agent', owner_agent,
                'strategy_key', strategy_key,
                'direction', direction,
                'quantity', quantity,
                'market_value', market_value,
                'gross_exposure', gross_exposure,
                'net_exposure', net_exposure,
                'time_horizon', time_horizon,
                'thesis', thesis,
                'exit_criteria', exit_criteria,
                'as_of', as_of
            )
            ORDER BY gross_exposure DESC NULLS LAST, book_key
        ) AS book_position_details
    FROM books.v_book_positions
    WHERE status = 'active'
    GROUP BY client_code, symbol, exchange
),
thesis AS (
    SELECT DISTINCT ON (upper(symbol), exchange)
        id AS holding_thesis_id,
        upper(symbol) AS symbol,
        exchange,
        company_name,
        thesis_title,
        thesis_status,
        decision_status AS thesis_decision_status,
        thesis_summary,
        primary_owner_agent,
        checklist_count,
        checklist_complete_count,
        valuation_model_count,
        valuation_complete_count,
        valuation_status_map,
        thesis_note_path,
        next_review_due_at,
        review_frequency,
        thesis_killers,
        exit_criteria,
        long_term_gross_exposure,
        client_count AS thesis_client_count,
        clients AS thesis_clients,
        updated_at AS thesis_updated_at
    FROM portfolio.v_long_term_thesis_control
    ORDER BY upper(symbol), exchange, long_term_gross_exposure DESC NULLS LAST, updated_at DESC
),
latest_mc AS (
    SELECT DISTINCT ON (holding_thesis_id)
        holding_thesis_id,
        id AS latest_monte_carlo_run_id,
        run_status AS monte_carlo_status,
        simulation_count AS monte_carlo_simulation_count,
        seed AS monte_carlo_seed,
        start_price AS monte_carlo_start_price,
        starting_multiple AS monte_carlo_starting_multiple,
        percentile_summary -> 'cagr' ->> 'p50' AS monte_carlo_median_cagr,
        probability_summary ->> 'negative_cagr_probability' AS monte_carlo_negative_cagr_probability,
        probability_summary ->> 'permanent_loss_30pct_probability' AS monte_carlo_permanent_loss_probability,
        probability_summary ->> 'drawdown_30pct_probability' AS monte_carlo_drawdown_probability,
        warnings AS monte_carlo_warnings,
        note_path AS monte_carlo_note_path,
        created_at AS monte_carlo_created_at
    FROM portfolio.v_long_term_monte_carlo_runs
    ORDER BY holding_thesis_id, created_at DESC, id DESC
),
latest_committee AS (
    SELECT DISTINCT ON (holding_thesis_id)
        holding_thesis_id,
        id AS latest_committee_review_id,
        review_status AS latest_committee_status,
        recommended_decision,
        decision_status AS committee_decision_status,
        final_decision,
        memo_status,
        memo_note_path,
        capital_action_allowed,
        live_execution_allowed,
        updated_at AS committee_updated_at
    FROM portfolio.v_long_term_committee_queue
    ORDER BY holding_thesis_id, updated_at DESC, id DESC
),
filing_counts AS (
    SELECT
        upper(symbol) AS symbol,
        exchange,
        count(*) AS filing_count,
        count(*) FILTER (WHERE event_type IS NOT NULL AND event_type <> 'routine_filing') AS material_filing_count
    FROM research.v_corporate_filing_inbox
    WHERE symbol IS NOT NULL
    GROUP BY upper(symbol), exchange
),
latest_filing AS (
    SELECT DISTINCT ON (upper(symbol), exchange)
        upper(symbol) AS symbol,
        exchange,
        filing_id AS latest_filing_id,
        title AS latest_filing_title,
        filing_event_type AS latest_filing_event_type,
        event_type AS latest_event_type,
        urgency AS latest_filing_urgency,
        opportunity_score AS latest_filing_opportunity_score,
        risk_score AS latest_filing_risk_score,
        extraction_status AS latest_filing_extraction_status,
        source_url AS latest_filing_source_url,
        filed_at AS latest_filing_at
    FROM research.v_corporate_filing_inbox
    WHERE symbol IS NOT NULL
    ORDER BY upper(symbol), exchange, filed_at DESC NULLS LAST, filing_id DESC
),
news_symbols AS (
    SELECT
        upper(regexp_replace(symbol_item, '^[A-Z]+:', '')) AS symbol,
        count(*) AS news_count,
        max(published_at) AS latest_news_at,
        (array_agg(title ORDER BY published_at DESC NULLS LAST, captured_at DESC))[1] AS latest_news_title,
        (array_agg(source_url ORDER BY published_at DESC NULLS LAST, captured_at DESC))[1] AS latest_news_url,
        (array_agg(sentiment ORDER BY published_at DESC NULLS LAST, captured_at DESC))[1] AS latest_news_sentiment
    FROM market.v_recent_news news
    CROSS JOIN LATERAL unnest(news.symbols) AS symbol_item
    GROUP BY upper(regexp_replace(symbol_item, '^[A-Z]+:', ''))
),
signal_latest AS (
    SELECT DISTINCT ON (upper(regexp_replace(symbol, '^[A-Z]+:', '')), exchange)
        upper(regexp_replace(symbol, '^[A-Z]+:', '')) AS symbol,
        exchange,
        id AS latest_signal_id,
        strategy AS latest_signal_strategy,
        action AS latest_signal_action,
        price AS latest_signal_price,
        confidence AS latest_signal_confidence,
        status AS latest_signal_status,
        ts AS latest_signal_at
    FROM trading.v_recent_signals
    WHERE symbol IS NOT NULL
    ORDER BY upper(regexp_replace(symbol, '^[A-Z]+:', '')), exchange, ts DESC, id DESC
),
strategy_symbol AS (
    SELECT
        upper(regexp_replace(symbol_item, '^[A-Z]+:', '')) AS symbol,
        count(*) AS strategy_candidate_count,
        jsonb_agg(
            jsonb_build_object(
                'candidate_id', candidate_id,
                'candidate_key', candidate_key,
                'strategy_name', strategy_name,
                'candidate_status', candidate_status,
                'validation_status', validation_status,
                'activation_gate', activation_gate,
                'timeframe', timeframe,
                'owner_agent', owner_agent
            )
            ORDER BY updated_at DESC NULLS LAST, candidate_id DESC
        ) AS strategy_candidates
    FROM strategy.v_strategy_arsenal_queue queue
    CROSS JOIN LATERAL unnest(queue.symbols) AS symbol_item
    GROUP BY upper(regexp_replace(symbol_item, '^[A-Z]+:', ''))
),
strategy_universe AS (
    SELECT
        count(*) AS broad_strategy_candidate_count,
        jsonb_agg(
            jsonb_build_object(
                'candidate_id', candidate_id,
                'candidate_key', candidate_key,
                'strategy_name', strategy_name,
                'universe', universe,
                'candidate_status', candidate_status,
                'validation_status', validation_status,
                'activation_gate', activation_gate,
                'owner_agent', owner_agent
            )
            ORDER BY updated_at DESC NULLS LAST, candidate_id DESC
        ) FILTER (WHERE universe IS NOT NULL) AS broad_strategy_candidates
    FROM strategy.v_strategy_arsenal_queue
    WHERE symbols IS NULL OR cardinality(symbols) = 0
)
SELECT
    base.client_id,
    base.client_code,
    base.client_name,
    base.symbol,
    base.exchange,
    base.long_term_exposure,
    base.tactical_exposure,
    base.quant_exposure,
    base.active_trading_exposure,
    base.hedges_exposure,
    base.cash_treasury_exposure,
    base.gross_long,
    base.gross_short,
    base.gross_exposure,
    base.net_exposure,
    base.offset_ratio,
    base.overall_bias,
    base.active_books,
    base.purposes,
    COALESCE(conflicts.conflict_count, 0::bigint) AS conflict_count,
    COALESCE(gaps.gap_count, 0::bigint) AS gap_count,
    gaps.gap_types,
    base.latest_as_of,
    concat_ws(':', base.exchange, base.symbol) AS symbol_key,
    COALESCE(book_details.book_position_details, '[]'::jsonb) AS book_position_details,
    COALESCE(conflicts.conflict_details, '[]'::jsonb) AS conflict_details,
    COALESCE(gaps.gap_details, '[]'::jsonb) AS gap_details,
    thesis.holding_thesis_id,
    thesis.company_name,
    thesis.thesis_title,
    thesis.thesis_status,
    thesis.thesis_decision_status,
    thesis.thesis_summary,
    thesis.primary_owner_agent AS thesis_owner_agent,
    thesis.checklist_count,
    thesis.checklist_complete_count,
    thesis.valuation_model_count,
    thesis.valuation_complete_count,
    thesis.valuation_status_map,
    thesis.thesis_note_path,
    thesis.next_review_due_at,
    thesis.review_frequency,
    thesis.thesis_killers,
    thesis.exit_criteria AS thesis_exit_criteria,
    latest_mc.latest_monte_carlo_run_id,
    latest_mc.monte_carlo_status,
    latest_mc.monte_carlo_simulation_count,
    latest_mc.monte_carlo_seed,
    latest_mc.monte_carlo_start_price,
    latest_mc.monte_carlo_starting_multiple,
    latest_mc.monte_carlo_median_cagr,
    latest_mc.monte_carlo_negative_cagr_probability,
    latest_mc.monte_carlo_permanent_loss_probability,
    latest_mc.monte_carlo_drawdown_probability,
    latest_mc.monte_carlo_warnings,
    latest_mc.monte_carlo_note_path,
    latest_mc.monte_carlo_created_at,
    latest_committee.latest_committee_review_id,
    latest_committee.latest_committee_status,
    latest_committee.recommended_decision,
    latest_committee.committee_decision_status,
    latest_committee.final_decision,
    latest_committee.memo_status,
    latest_committee.memo_note_path,
    latest_committee.capital_action_allowed,
    latest_committee.live_execution_allowed,
    COALESCE(filing_counts.filing_count, 0::bigint) AS filing_count,
    COALESCE(filing_counts.material_filing_count, 0::bigint) AS material_filing_count,
    latest_filing.latest_filing_id,
    latest_filing.latest_filing_title,
    latest_filing.latest_filing_event_type,
    latest_filing.latest_event_type,
    latest_filing.latest_filing_urgency,
    latest_filing.latest_filing_opportunity_score,
    latest_filing.latest_filing_risk_score,
    latest_filing.latest_filing_extraction_status,
    latest_filing.latest_filing_source_url,
    latest_filing.latest_filing_at,
    COALESCE(news_symbols.news_count, 0::bigint) AS news_count,
    news_symbols.latest_news_at,
    news_symbols.latest_news_title,
    news_symbols.latest_news_url,
    news_symbols.latest_news_sentiment,
    signal_latest.latest_signal_id,
    signal_latest.latest_signal_strategy,
    signal_latest.latest_signal_action,
    signal_latest.latest_signal_price,
    signal_latest.latest_signal_confidence,
    signal_latest.latest_signal_status,
    signal_latest.latest_signal_at,
    COALESCE(strategy_symbol.strategy_candidate_count, 0::bigint) AS symbol_strategy_candidate_count,
    COALESCE(strategy_symbol.strategy_candidates, '[]'::jsonb) AS symbol_strategy_candidates,
    COALESCE(strategy_universe.broad_strategy_candidate_count, 0::bigint) AS broad_strategy_candidate_count,
    COALESCE(strategy_universe.broad_strategy_candidates, '[]'::jsonb) AS broad_strategy_candidates,
    array_remove(ARRAY[
        CASE WHEN COALESCE(conflicts.conflict_count, 0) > 0 THEN 'cross_book_conflict' END,
        CASE WHEN COALESCE(gaps.gap_count, 0) > 0 THEN 'assignment_or_thesis_gap' END,
        CASE WHEN thesis.holding_thesis_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'missing_long_term_thesis' END,
        CASE WHEN latest_mc.latest_monte_carlo_run_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'missing_monte_carlo' END,
        CASE WHEN latest_mc.monte_carlo_status = 'needs_review' THEN 'monte_carlo_needs_review' END,
        CASE WHEN COALESCE(filing_counts.material_filing_count, 0) > 0 THEN 'material_filing_present' END,
        CASE WHEN signal_latest.latest_signal_id IS NOT NULL THEN 'strategy_signal_present' END
    ]::text[], NULL) AS decision_flags,
    CASE
        WHEN COALESCE(conflicts.conflict_count, 0) > 0 THEN 'risk_review_required'
        WHEN thesis.holding_thesis_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'research_required'
        WHEN latest_mc.latest_monte_carlo_run_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'valuation_work_required'
        WHEN latest_mc.monte_carlo_status = 'needs_review' THEN 'committee_review_required'
        WHEN COALESCE(gaps.gap_count, 0) > 0 THEN 'data_gap_review_required'
        ELSE 'monitor'
    END AS decision_readiness,
    CASE
        WHEN COALESCE(conflicts.conflict_count, 0) > 0 THEN 'Risk Office should review cross-book exposure before any action.'
        WHEN thesis.holding_thesis_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'Create or update long-term thesis before capital decision.'
        WHEN latest_mc.latest_monte_carlo_run_id IS NULL AND COALESCE(base.long_term_exposure, 0) <> 0 THEN 'Run Long-Term Monte Carlo and valuation review.'
        WHEN latest_mc.monte_carlo_status = 'needs_review' THEN 'Committee should review Monte Carlo assumptions before capital decision.'
        WHEN COALESCE(gaps.gap_count, 0) > 0 THEN 'Resolve position purpose, exit criteria, and review gaps.'
        ELSE 'Monitor with current evidence.'
    END AS recommended_next_action
FROM base
LEFT JOIN conflicts
  ON conflicts.client_id IS NOT DISTINCT FROM base.client_id
 AND conflicts.symbol = base.symbol
 AND conflicts.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN gaps
  ON gaps.client_code IS NOT DISTINCT FROM base.client_code
 AND gaps.symbol = base.symbol
LEFT JOIN book_details
  ON book_details.client_code IS NOT DISTINCT FROM base.client_code
 AND book_details.symbol = base.symbol
 AND book_details.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN thesis
  ON thesis.symbol = upper(base.symbol)
 AND thesis.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN latest_mc ON latest_mc.holding_thesis_id = thesis.holding_thesis_id
LEFT JOIN latest_committee ON latest_committee.holding_thesis_id = thesis.holding_thesis_id
LEFT JOIN filing_counts
  ON filing_counts.symbol = upper(base.symbol)
 AND filing_counts.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN latest_filing
  ON latest_filing.symbol = upper(base.symbol)
 AND latest_filing.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN news_symbols ON news_symbols.symbol = upper(base.symbol)
LEFT JOIN signal_latest
  ON signal_latest.symbol = upper(base.symbol)
 AND signal_latest.exchange IS NOT DISTINCT FROM base.exchange
LEFT JOIN strategy_symbol ON strategy_symbol.symbol = upper(base.symbol)
CROSS JOIN strategy_universe;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'portfolio.v_symbol_intelligence',
            'portfolio.v_long_term_monte_carlo_runs',
            'portfolio.v_long_term_committee_queue',
            'research.v_corporate_filing_inbox',
            'trading.v_recent_signals',
            'strategy.v_strategy_arsenal_queue'
        ]::TEXT[]) AS obj
    ),
    next_action = 'Symbol Intelligence v2 joins book exposure, thesis, valuation, Monte Carlo, committee, filings, news, signals, and strategy context for decision review.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'research_inbox', 'data_sources');

