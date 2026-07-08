CREATE OR REPLACE FUNCTION books.default_book_for_trade(
    p_execution_mode TEXT,
    p_strategy_key TEXT,
    p_setup_type TEXT,
    p_timeframe TEXT
) RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_mode TEXT := lower(coalesce(p_execution_mode, ''));
    normalized_setup TEXT := lower(coalesce(p_setup_type, ''));
    normalized_timeframe TEXT := lower(coalesce(p_timeframe, ''));
BEGIN
    IF coalesce(p_strategy_key, '') <> '' THEN
        RETURN 'quant';
    END IF;
    IF normalized_mode IN ('paper', 'shadow', 'system_alert') THEN
        RETURN 'quant';
    END IF;
    IF normalized_timeframe IN ('intraday', '1m', '3m', '5m', '15m', '30m', '1h')
       OR normalized_setup LIKE '%intraday%'
       OR normalized_setup LIKE '%scalp%'
       OR normalized_setup LIKE '%breakout%'
       OR normalized_setup LIKE '%breakdown%'
       OR normalized_setup LIKE '%option%'
       OR normalized_setup LIKE '%futures%' THEN
        RETURN 'active_trading';
    END IF;
    IF normalized_setup LIKE '%earnings%'
       OR normalized_setup LIKE '%event%'
       OR normalized_setup LIKE '%swing%'
       OR normalized_setup LIKE '%sector%'
       OR normalized_setup LIKE '%hedge around%' THEN
        RETURN 'tactical';
    END IF;
    RETURN 'active_trading';
END;
$$;

CREATE OR REPLACE FUNCTION books.default_purpose_for_trade(
    p_book_key TEXT,
    p_side TEXT,
    p_setup_type TEXT,
    p_timeframe TEXT
) RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    normalized_book TEXT := lower(coalesce(p_book_key, ''));
    normalized_side TEXT := lower(coalesce(p_side, ''));
    normalized_setup TEXT := lower(coalesce(p_setup_type, ''));
    normalized_timeframe TEXT := lower(coalesce(p_timeframe, ''));
BEGIN
    IF normalized_book = 'quant' THEN
        IF normalized_setup LIKE '%mean%' OR normalized_setup LIKE '%reversion%' THEN
            RETURN 'mean_reversion';
        END IF;
        IF normalized_setup LIKE '%pair%' THEN
            RETURN 'pairs_trade';
        END IF;
        IF normalized_setup LIKE '%vol%' THEN
            RETURN 'volatility_signal';
        END IF;
        IF normalized_setup LIKE '%ml%' OR normalized_setup LIKE '%model%' THEN
            RETURN 'ml_signal';
        END IF;
        IF normalized_setup LIKE '%regime%' THEN
            RETURN 'regime_signal';
        END IF;
        RETURN 'momentum';
    END IF;

    IF normalized_book = 'tactical' THEN
        IF normalized_setup LIKE '%earnings%' THEN
            RETURN 'earnings_trade';
        END IF;
        IF normalized_setup LIKE '%sector%' THEN
            RETURN 'sector_rotation';
        END IF;
        IF normalized_setup LIKE '%event%' THEN
            RETURN 'event_driven';
        END IF;
        IF normalized_setup LIKE '%covered%' THEN
            RETURN 'covered_call_overlay';
        END IF;
        IF normalized_setup LIKE '%put%' THEN
            RETURN 'cash_secured_put';
        END IF;
        IF normalized_setup LIKE '%hedge%' THEN
            RETURN 'hedge_around_core';
        END IF;
        RETURN 'swing_trade';
    END IF;

    IF normalized_book = 'hedges' THEN
        IF normalized_setup LIKE '%tail%' THEN
            RETURN 'tail_risk_hedge';
        END IF;
        IF normalized_setup LIKE '%index%' THEN
            RETURN 'index_overlay';
        END IF;
        RETURN 'protective_hedge';
    END IF;

    IF normalized_book = 'active_trading' THEN
        IF normalized_setup LIKE '%breakdown%' OR normalized_side IN ('sell', 'short') THEN
            RETURN 'breakdown';
        END IF;
        IF normalized_setup LIKE '%breakout%' THEN
            RETURN 'breakout';
        END IF;
        IF normalized_setup LIKE '%scalp%' THEN
            RETURN 'scalping';
        END IF;
        IF normalized_setup LIKE '%vol%' THEN
            RETURN 'volatility_trade';
        END IF;
        IF normalized_setup LIKE '%option%' THEN
            RETURN 'options_directional';
        END IF;
        IF normalized_setup LIKE '%future%' THEN
            RETURN 'futures_hedge';
        END IF;
        IF normalized_setup LIKE '%event%' THEN
            RETURN 'event_risk_trade';
        END IF;
        IF normalized_timeframe IN ('intraday', '1m', '3m', '5m', '15m', '30m', '1h') THEN
            RETURN 'intraday_setup';
        END IF;
        RETURN 'intraday_setup';
    END IF;

    RETURN 'core_compounder';
END;
$$;

CREATE OR REPLACE FUNCTION books.route_trade_activity_to_book(
    p_trade_id BIGINT,
    p_book_key TEXT DEFAULT NULL,
    p_purpose_key TEXT DEFAULT NULL,
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    trade_row trading.trade_activity_ledger%ROWTYPE;
    account_row portfolio.accounts%ROWTYPE;
    resolved_book_key TEXT;
    resolved_purpose_key TEXT;
    resolved_direction TEXT;
    signed_notional NUMERIC;
    inserted_id BIGINT;
BEGIN
    SELECT *
    INTO trade_row
    FROM trading.trade_activity_ledger
    WHERE id = p_trade_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'trade_activity_ledger row % not found', p_trade_id;
    END IF;

    IF coalesce(p_book_key, '') <> '' THEN
        resolved_book_key := p_book_key;
    ELSE
        resolved_book_key := books.default_book_for_trade(
            trade_row.execution_mode,
            trade_row.strategy_key,
            trade_row.setup_type,
            trade_row.timeframe
        );
    END IF;

    IF coalesce(p_purpose_key, '') <> '' THEN
        resolved_purpose_key := p_purpose_key;
    ELSE
        resolved_purpose_key := books.default_purpose_for_trade(
            resolved_book_key,
            trade_row.side,
            trade_row.setup_type,
            trade_row.timeframe
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM books.investment_books WHERE book_key = resolved_book_key) THEN
        RAISE EXCEPTION 'book % not found', resolved_book_key;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM books.position_purposes
        WHERE purpose_key = resolved_purpose_key
          AND book_key = resolved_book_key
    ) THEN
        RAISE EXCEPTION 'purpose % not valid for book %', resolved_purpose_key, resolved_book_key;
    END IF;

    IF coalesce(trade_row.account_code, '') <> '' THEN
        SELECT a.*
        INTO account_row
        FROM portfolio.accounts a
        LEFT JOIN portfolio.clients c ON c.id = a.client_id
        WHERE a.account_code = trade_row.account_code
          AND (trade_row.client_code IS NULL OR c.client_code = trade_row.client_code)
        LIMIT 1;
    END IF;

    resolved_direction := CASE
        WHEN lower(coalesce(trade_row.side, '')) IN ('sell', 'short') THEN 'short'
        WHEN lower(coalesce(trade_row.side, '')) IN ('watch') THEN 'watch'
        WHEN lower(coalesce(trade_row.side, '')) IN ('exit') THEN 'flat'
        ELSE 'long'
    END;

    signed_notional := coalesce(trade_row.quantity, 0) * coalesce(trade_row.price, 0);
    IF resolved_direction = 'short' THEN
        signed_notional := -abs(signed_notional);
    ELSIF resolved_direction = 'flat' THEN
        signed_notional := 0;
    ELSE
        signed_notional := abs(signed_notional);
    END IF;

    INSERT INTO books.book_positions (
        source_trade_id, client_id, account_id, symbol, exchange, instrument_type,
        book_key, purpose_key, owner_agent, strategy_key, direction, quantity,
        average_price, market_price, market_value, notional_exposure,
        gross_exposure, net_exposure, time_horizon, thesis, exit_criteria,
        review_frequency, status, evidence, as_of
    )
    VALUES (
        trade_row.id,
        account_row.client_id,
        account_row.id,
        upper(trade_row.symbol),
        trade_row.exchange,
        trade_row.instrument_type,
        resolved_book_key,
        resolved_purpose_key,
        CASE
            WHEN resolved_book_key = 'quant' THEN 'Quant Agent'
            WHEN resolved_book_key = 'tactical' THEN 'Tactical Portfolio Manager'
            WHEN resolved_book_key = 'hedges' THEN 'Risk Agent'
            ELSE 'Trading Desk Agent'
        END,
        trade_row.strategy_key,
        resolved_direction,
        coalesce(trade_row.quantity, 0),
        trade_row.price,
        trade_row.price,
        signed_notional,
        signed_notional,
        abs(signed_notional),
        signed_notional,
        CASE
            WHEN resolved_book_key = 'quant' THEN 'days_to_weeks'
            WHEN resolved_book_key = 'tactical' THEN 'days_to_months'
            WHEN resolved_book_key = 'hedges' THEN 'days_to_months'
            ELSE coalesce(trade_row.timeframe, 'intraday_to_days')
        END,
        coalesce(trade_row.thesis, 'Trade routed from trading.trade_activity_ledger; needs journal review and risk validation.'),
        CASE
            WHEN trade_row.stop_loss IS NOT NULL AND trade_row.target_price IS NOT NULL
                THEN 'Stop ' || trade_row.stop_loss::TEXT || '; target ' || trade_row.target_price::TEXT || '; review on signal/time exit.'
            WHEN trade_row.stop_loss IS NOT NULL
                THEN 'Stop ' || trade_row.stop_loss::TEXT || '; define target/time exit.'
            ELSE 'Needs explicit stop, target, time exit, or signal-reversal rule.'
        END,
        CASE WHEN resolved_book_key IN ('quant', 'active_trading') THEN 'daily' ELSE 'weekly' END,
        'active',
        jsonb_build_array(
            jsonb_build_object('source', 'trading.trade_activity_ledger', 'id', trade_row.id),
            jsonb_build_object('source', 'books.route_trade_activity_to_book', 'actor', p_actor)
        ),
        trade_row.trade_ts
    )
    ON CONFLICT (source_trade_id) DO UPDATE SET
        book_key = EXCLUDED.book_key,
        purpose_key = EXCLUDED.purpose_key,
        owner_agent = EXCLUDED.owner_agent,
        strategy_key = EXCLUDED.strategy_key,
        direction = EXCLUDED.direction,
        quantity = EXCLUDED.quantity,
        average_price = EXCLUDED.average_price,
        market_price = EXCLUDED.market_price,
        market_value = EXCLUDED.market_value,
        notional_exposure = EXCLUDED.notional_exposure,
        gross_exposure = EXCLUDED.gross_exposure,
        net_exposure = EXCLUDED.net_exposure,
        thesis = EXCLUDED.thesis,
        exit_criteria = EXCLUDED.exit_criteria,
        review_frequency = EXCLUDED.review_frequency,
        evidence = EXCLUDED.evidence,
        as_of = EXCLUDED.as_of,
        updated_at = now()
    RETURNING id INTO inserted_id;

    INSERT INTO books.book_assignment_audit (
        book_position_id, changed_by, change_type, new_value, rationale, evidence
    )
    VALUES (
        inserted_id,
        p_actor,
        'trade_routed_to_book',
        jsonb_build_object(
            'trade_id', trade_row.id,
            'book_key', resolved_book_key,
            'purpose_key', resolved_purpose_key,
            'direction', resolved_direction,
            'net_exposure', signed_notional
        ),
        'Trade activity routed into Portfolio Intelligence book layer.',
        jsonb_build_array(jsonb_build_object('table', 'trading.trade_activity_ledger', 'id', trade_row.id))
    );

    RETURN inserted_id;
END;
$$;

CREATE OR REPLACE FUNCTION books.update_book_position_assignment(
    p_book_position_id BIGINT,
    p_book_key TEXT,
    p_purpose_key TEXT,
    p_thesis TEXT DEFAULT NULL,
    p_exit_criteria TEXT DEFAULT NULL,
    p_actor TEXT DEFAULT 'Devarsh',
    p_rationale TEXT DEFAULT 'Manual book assignment update'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    previous_row books.book_positions%ROWTYPE;
BEGIN
    SELECT *
    INTO previous_row
    FROM books.book_positions
    WHERE id = p_book_position_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'book position % not found', p_book_position_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM books.investment_books WHERE book_key = p_book_key) THEN
        RAISE EXCEPTION 'book % not found', p_book_key;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM books.position_purposes
        WHERE purpose_key = p_purpose_key
          AND book_key = p_book_key
    ) THEN
        RAISE EXCEPTION 'purpose % not valid for book %', p_purpose_key, p_book_key;
    END IF;

    UPDATE books.book_positions
    SET book_key = p_book_key,
        purpose_key = p_purpose_key,
        thesis = coalesce(nullif(p_thesis, ''), thesis),
        exit_criteria = coalesce(nullif(p_exit_criteria, ''), exit_criteria),
        owner_agent = CASE
            WHEN p_book_key = 'long_term' THEN 'Long-Term Portfolio Manager'
            WHEN p_book_key = 'quant' THEN 'Quant Agent'
            WHEN p_book_key = 'tactical' THEN 'Tactical Portfolio Manager'
            WHEN p_book_key = 'hedges' THEN 'Risk Agent'
            WHEN p_book_key = 'cash_treasury' THEN 'Portfolio Manager'
            ELSE 'Trading Desk Agent'
        END,
        updated_at = now()
    WHERE id = p_book_position_id;

    INSERT INTO books.book_assignment_audit (
        book_position_id, changed_by, change_type, previous_value, new_value, rationale, evidence
    )
    VALUES (
        p_book_position_id,
        p_actor,
        'manual_assignment_update',
        jsonb_build_object(
            'book_key', previous_row.book_key,
            'purpose_key', previous_row.purpose_key,
            'thesis', previous_row.thesis,
            'exit_criteria', previous_row.exit_criteria
        ),
        jsonb_build_object(
            'book_key', p_book_key,
            'purpose_key', p_purpose_key,
            'thesis_updated', nullif(p_thesis, '') IS NOT NULL,
            'exit_criteria_updated', nullif(p_exit_criteria, '') IS NOT NULL
        ),
        p_rationale,
        jsonb_build_array(jsonb_build_object('table', 'books.book_positions', 'id', p_book_position_id))
    );

    RETURN p_book_position_id;
END;
$$;

CREATE OR REPLACE VIEW books.v_position_purpose_options AS
SELECT
    ib.book_key,
    ib.book_name,
    pp.purpose_key,
    pp.purpose_name,
    pp.purpose_family,
    pp.description,
    pp.default_horizon,
    pp.exit_rule_template
FROM books.investment_books ib
JOIN books.position_purposes pp ON pp.book_key = ib.book_key
WHERE ib.status = 'active'
  AND pp.status = 'active'
ORDER BY ib.book_key, pp.purpose_family, pp.purpose_key;
