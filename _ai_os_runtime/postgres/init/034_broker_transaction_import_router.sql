CREATE TABLE IF NOT EXISTS books.broker_transaction_import_routes (
    id BIGSERIAL PRIMARY KEY,
    broker_transaction_id BIGINT NOT NULL REFERENCES client_data.attached_broker_transactions(id) ON DELETE CASCADE,
    recommended_book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE RESTRICT,
    recommended_purpose_key TEXT NOT NULL REFERENCES books.position_purposes(purpose_key) ON DELETE RESTRICT,
    route_reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'staged',
    affects_active_exposure BOOLEAN NOT NULL DEFAULT false,
    trade_activity_id BIGINT REFERENCES trading.trade_activity_ledger(id) ON DELETE SET NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broker_transaction_id)
);

CREATE TABLE IF NOT EXISTS books.trade_book_links (
    id BIGSERIAL PRIMARY KEY,
    trade_activity_id BIGINT NOT NULL REFERENCES trading.trade_activity_ledger(id) ON DELETE CASCADE,
    broker_transaction_id BIGINT REFERENCES client_data.attached_broker_transactions(id) ON DELETE SET NULL,
    book_position_id BIGINT REFERENCES books.book_positions(id) ON DELETE SET NULL,
    book_key TEXT NOT NULL REFERENCES books.investment_books(book_key) ON DELETE RESTRICT,
    purpose_key TEXT NOT NULL REFERENCES books.position_purposes(purpose_key) ON DELETE RESTRICT,
    link_type TEXT NOT NULL DEFAULT 'history_evidence',
    affects_active_exposure BOOLEAN NOT NULL DEFAULT false,
    route_reason TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (trade_activity_id, broker_transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_broker_routes_status ON books.broker_transaction_import_routes (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_broker_routes_book ON books.broker_transaction_import_routes (recommended_book_key, recommended_purpose_key);
CREATE INDEX IF NOT EXISTS idx_trade_book_links_book ON books.trade_book_links (book_key, purpose_key, affects_active_exposure);

CREATE OR REPLACE FUNCTION books.default_book_for_broker_transaction(
    p_instrument_type TEXT,
    p_exchange TEXT,
    p_symbol TEXT,
    p_side TEXT
) RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    instrument TEXT := lower(coalesce(p_instrument_type, ''));
    exchange_value TEXT := upper(coalesce(p_exchange, ''));
    symbol_value TEXT := upper(coalesce(p_symbol, ''));
BEGIN
    IF instrument LIKE '%option%' OR exchange_value IN ('NSEF', 'NFO', 'BFO') OR symbol_value LIKE '% O %' THEN
        RETURN 'active_trading';
    END IF;
    IF instrument LIKE '%future%' OR symbol_value LIKE '% FUT%' THEN
        RETURN 'active_trading';
    END IF;
    RETURN 'long_term';
END;
$$;

CREATE OR REPLACE FUNCTION books.default_purpose_for_broker_transaction(
    p_book_key TEXT,
    p_instrument_type TEXT,
    p_side TEXT,
    p_symbol TEXT
) RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    book_value TEXT := lower(coalesce(p_book_key, ''));
    instrument TEXT := lower(coalesce(p_instrument_type, ''));
    side_value TEXT := upper(coalesce(p_side, ''));
BEGIN
    IF book_value = 'active_trading' THEN
        IF instrument LIKE '%option%' THEN
            RETURN 'options_directional';
        END IF;
        IF side_value IN ('S', 'SELL', 'SHORT') THEN
            RETURN 'breakdown';
        END IF;
        RETURN 'intraday_setup';
    END IF;
    IF book_value = 'long_term' THEN
        RETURN 'core_compounder';
    END IF;
    RETURN books.default_purpose_for_trade(book_value, side_value, NULL, NULL);
END;
$$;

CREATE OR REPLACE FUNCTION books.stage_broker_transaction_imports(
    p_limit INTEGER DEFAULT 250,
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_count INTEGER;
BEGIN
    WITH candidates AS (
        SELECT
            bt.id,
            books.default_book_for_broker_transaction(bt.instrument_type, bt.exchange, bt.trading_symbol, bt.side) AS book_key,
            bt.instrument_type,
            bt.side,
            bt.trading_symbol,
            bt.exchange
        FROM client_data.attached_broker_transactions bt
        LEFT JOIN books.broker_transaction_import_routes existing ON existing.broker_transaction_id = bt.id
        WHERE existing.id IS NULL
        ORDER BY bt.trade_date DESC NULLS LAST, bt.id DESC
        LIMIT greatest(1, least(coalesce(p_limit, 250), 2000))
    ),
    inserted AS (
        INSERT INTO books.broker_transaction_import_routes (
            broker_transaction_id, recommended_book_key, recommended_purpose_key,
            route_reason, status, affects_active_exposure, evidence
        )
        SELECT
            c.id,
            c.book_key,
            books.default_purpose_for_broker_transaction(c.book_key, c.instrument_type, c.side, c.trading_symbol),
            CASE
                WHEN c.book_key = 'active_trading' THEN 'Broker option/futures-like transaction classified as active trading history by default.'
                ELSE 'Broker equity transaction classified as long-term history by default; active exposure remains sourced from holdings.'
            END,
            'staged',
            false,
            jsonb_build_array(
                jsonb_build_object('table', 'client_data.attached_broker_transactions', 'id', c.id),
                jsonb_build_object('actor', p_actor, 'mode', 'history_only_default')
            )
        FROM candidates c
        RETURNING id
    )
    SELECT count(*) INTO inserted_count FROM inserted;

    RETURN inserted_count;
END;
$$;

CREATE OR REPLACE FUNCTION books.promote_broker_transaction_route(
    p_route_id BIGINT,
    p_affects_active_exposure BOOLEAN DEFAULT false,
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    route_row books.broker_transaction_import_routes%ROWTYPE;
    bt client_data.attached_broker_transactions%ROWTYPE;
    inserted_trade_id BIGINT;
    routed_book_position_id BIGINT;
BEGIN
    SELECT *
    INTO route_row
    FROM books.broker_transaction_import_routes
    WHERE id = p_route_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'broker transaction route % not found', p_route_id;
    END IF;

    SELECT *
    INTO bt
    FROM client_data.attached_broker_transactions
    WHERE id = route_row.broker_transaction_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'broker transaction % not found', route_row.broker_transaction_id;
    END IF;

    IF route_row.trade_activity_id IS NOT NULL THEN
        RETURN route_row.trade_activity_id;
    END IF;

    INSERT INTO trading.trade_activity_ledger (
        activity_type, execution_mode, source_kind, source_ref,
        client_code, account_code, strategy_key, symbol, exchange,
        instrument_type, side, quantity, price, trade_ts, status,
        thesis, setup_type, timeframe, realized_pnl, fees, tags, evidence, payload, created_by
    )
    VALUES (
        'broker_transaction',
        'broker_import',
        'broker_statement',
        'attached_broker_transaction:' || bt.id::TEXT,
        bt.client_code,
        NULL,
        NULL,
        upper(bt.trading_symbol),
        bt.exchange,
        bt.instrument_type,
        CASE WHEN upper(bt.side) IN ('S', 'SELL') THEN 'sell' ELSE 'buy' END,
        bt.quantity,
        coalesce(bt.net_rate, bt.market_rate),
        (bt.trade_date::TEXT || ' ' || coalesce(bt.trade_time::TEXT, '00:00:00'))::TIMESTAMPTZ,
        'recorded',
        'Imported broker transaction history. Use as evidence for buy/sell dates and trade journal review.',
        CASE
            WHEN route_row.recommended_book_key = 'active_trading' THEN 'broker_active_trade_history'
            ELSE 'broker_long_term_history'
        END,
        CASE
            WHEN route_row.recommended_book_key = 'active_trading' THEN 'intraday_to_days'
            ELSE 'years'
        END,
        NULL,
        abs(coalesce(bt.amount, 0)) - abs(coalesce(bt.net_rate, bt.market_rate, 0) * coalesce(bt.quantity, 0)),
        ARRAY['broker_import','history_only']::TEXT[],
        jsonb_build_array(
            jsonb_build_object('table', 'client_data.attached_broker_transactions', 'id', bt.id),
            jsonb_build_object('table', 'books.broker_transaction_import_routes', 'id', route_row.id)
        ),
        bt.payload,
        p_actor
    )
    RETURNING id INTO inserted_trade_id;

    IF p_affects_active_exposure THEN
        routed_book_position_id := books.route_trade_activity_to_book(
            inserted_trade_id,
            route_row.recommended_book_key,
            route_row.recommended_purpose_key,
            p_actor
        );
    END IF;

    INSERT INTO books.trade_book_links (
        trade_activity_id, broker_transaction_id, book_position_id, book_key,
        purpose_key, link_type, affects_active_exposure, route_reason,
        created_by, evidence
    )
    VALUES (
        inserted_trade_id,
        bt.id,
        routed_book_position_id,
        route_row.recommended_book_key,
        route_row.recommended_purpose_key,
        CASE WHEN p_affects_active_exposure THEN 'active_exposure' ELSE 'history_evidence' END,
        p_affects_active_exposure,
        route_row.route_reason,
        p_actor,
        jsonb_build_array(
            jsonb_build_object('table', 'trading.trade_activity_ledger', 'id', inserted_trade_id),
            jsonb_build_object('table', 'client_data.attached_broker_transactions', 'id', bt.id)
        )
    );

    UPDATE books.broker_transaction_import_routes
    SET status = 'promoted',
        affects_active_exposure = p_affects_active_exposure,
        trade_activity_id = inserted_trade_id,
        reviewed_by = p_actor,
        reviewed_at = now(),
        updated_at = now()
    WHERE id = route_row.id;

    RETURN inserted_trade_id;
END;
$$;

CREATE OR REPLACE VIEW books.v_broker_transaction_import_queue AS
SELECT
    r.id AS route_id,
    r.broker_transaction_id,
    r.status,
    r.affects_active_exposure,
    r.recommended_book_key AS book_key,
    ib.book_name,
    r.recommended_purpose_key AS purpose_key,
    pp.purpose_name,
    r.route_reason,
    bt.client_code,
    bt.client_name,
    bt.trade_date,
    bt.trade_time,
    bt.exchange,
    bt.trading_symbol AS symbol,
    bt.side,
    bt.quantity,
    coalesce(bt.net_rate, bt.market_rate) AS price,
    bt.amount,
    bt.instrument_type,
    bt.expiry_date,
    bt.option_type,
    bt.strike_price,
    bt.trade_no,
    r.trade_activity_id,
    r.created_at,
    r.updated_at
FROM books.broker_transaction_import_routes r
JOIN client_data.attached_broker_transactions bt ON bt.id = r.broker_transaction_id
JOIN books.investment_books ib ON ib.book_key = r.recommended_book_key
LEFT JOIN books.position_purposes pp ON pp.purpose_key = r.recommended_purpose_key
ORDER BY
    CASE r.status WHEN 'staged' THEN 1 WHEN 'promoted' THEN 2 ELSE 3 END,
    bt.trade_date DESC NULLS LAST,
    bt.trade_time DESC NULLS LAST,
    r.id DESC;

CREATE OR REPLACE VIEW books.v_broker_transaction_import_summary AS
SELECT 'attached_broker_transactions' AS metric, count(*)::TEXT AS value,
       'Parsed broker transaction rows available for routing.' AS interpretation
FROM client_data.attached_broker_transactions
UNION ALL
SELECT 'staged_broker_routes', count(*)::TEXT,
       'Broker rows classified into candidate books but not yet promoted into trade ledger.'
FROM books.broker_transaction_import_routes
WHERE status = 'staged'
UNION ALL
SELECT 'promoted_broker_routes', count(*)::TEXT,
       'Broker rows promoted into trading.trade_activity_ledger.'
FROM books.broker_transaction_import_routes
WHERE status = 'promoted'
UNION ALL
SELECT 'broker_history_trade_links', count(*)::TEXT,
       'Broker imported trades linked to books as history evidence only.'
FROM books.trade_book_links
WHERE broker_transaction_id IS NOT NULL
  AND affects_active_exposure = false
UNION ALL
SELECT 'broker_active_exposure_links', count(*)::TEXT,
       'Broker imported trades explicitly allowed to affect active book exposure.'
FROM books.trade_book_links
WHERE broker_transaction_id IS NOT NULL
  AND affects_active_exposure = true;

CREATE OR REPLACE VIEW books.v_trade_book_links AS
SELECT
    tbl.id,
    tbl.trade_activity_id,
    tbl.broker_transaction_id,
    tbl.book_position_id,
    tbl.book_key,
    ib.book_name,
    tbl.purpose_key,
    pp.purpose_name,
    tbl.link_type,
    tbl.affects_active_exposure,
    tbl.route_reason,
    t.client_code,
    t.account_code,
    t.strategy_key,
    t.symbol,
    t.exchange,
    t.instrument_type,
    t.side,
    t.quantity,
    t.price,
    t.trade_ts,
    t.status AS trade_status,
    tbl.created_by,
    tbl.created_at
FROM books.trade_book_links tbl
JOIN trading.trade_activity_ledger t ON t.id = tbl.trade_activity_id
JOIN books.investment_books ib ON ib.book_key = tbl.book_key
LEFT JOIN books.position_purposes pp ON pp.purpose_key = tbl.purpose_key
ORDER BY tbl.created_at DESC, tbl.id DESC;
