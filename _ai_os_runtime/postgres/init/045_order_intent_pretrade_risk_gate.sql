CREATE TABLE IF NOT EXISTS trading.order_intents (
    id BIGSERIAL PRIMARY KEY,
    order_intent_key TEXT NOT NULL UNIQUE,
    limited_live_request_id BIGINT REFERENCES trading.limited_live_requests(id) ON DELETE SET NULL,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    instance_id BIGINT REFERENCES strategy.strategy_instances(id) ON DELETE SET NULL,
    client_code TEXT,
    account_code TEXT,
    book_key TEXT REFERENCES books.investment_books(book_key) ON DELETE SET NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    instrument_type TEXT NOT NULL DEFAULT 'equity',
    side TEXT NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'market',
    quantity NUMERIC NOT NULL,
    limit_price NUMERIC,
    notional NUMERIC,
    estimated_loss NUMERIC,
    status TEXT NOT NULL DEFAULT 'pending_approval',
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    latest_execution_gate_check_id BIGINT REFERENCES trading.execution_gate_checks(id) ON DELETE SET NULL,
    latest_order_risk_check_id BIGINT,
    gate_status TEXT NOT NULL DEFAULT 'not_checked',
    broker_order_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_by TEXT NOT NULL DEFAULT 'Devarsh',
    rationale TEXT,
    risk_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_order_intent_side CHECK (side IN ('buy', 'sell', 'short', 'cover')),
    CONSTRAINT chk_order_intent_quantity CHECK (quantity > 0),
    CONSTRAINT chk_order_intent_broker_allowed CHECK (
        broker_order_allowed = false
        OR (
            live_execution_allowed = true
            AND status = 'approved_for_broker'
            AND gate_status = 'passed'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_order_intents_status ON trading.order_intents (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_intents_request ON trading.order_intents (limited_live_request_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_intents_symbol ON trading.order_intents (symbol, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_intents_approval ON trading.order_intents (approval_id);

CREATE TABLE IF NOT EXISTS trading.order_risk_checks (
    id BIGSERIAL PRIMARY KEY,
    order_intent_id BIGINT NOT NULL REFERENCES trading.order_intents(id) ON DELETE CASCADE,
    check_key TEXT NOT NULL UNIQUE,
    check_status TEXT NOT NULL DEFAULT 'blocked',
    block_reasons TEXT[] NOT NULL DEFAULT '{}',
    warnings TEXT[] NOT NULL DEFAULT '{}',
    calculated_notional NUMERIC,
    current_daily_pnl NUMERIC,
    max_daily_loss NUMERIC,
    account_equity NUMERIC,
    current_gross_exposure NUMERIC,
    estimated_gross_exposure_after NUMERIC,
    max_leverage NUMERIC,
    estimated_leverage_after NUMERIC,
    execution_gate_check_id BIGINT REFERENCES trading.execution_gate_checks(id) ON DELETE SET NULL,
    policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_status TEXT,
    broker_order_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    checked_by TEXT NOT NULL DEFAULT 'Execution Safety Agent',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_order_risk_live_allowed CHECK (
        live_execution_allowed = false
        OR (
            check_status = 'passed'
            AND broker_order_allowed = true
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_order_risk_checks_order ON trading.order_risk_checks (order_intent_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_risk_checks_status ON trading.order_risk_checks (check_status, checked_at DESC);

ALTER TABLE trading.order_intents
    ADD CONSTRAINT fk_order_intents_latest_risk_check
    FOREIGN KEY (latest_order_risk_check_id)
    REFERENCES trading.order_risk_checks(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

CREATE OR REPLACE FUNCTION trading.create_order_intent(
    p_limited_live_request_id BIGINT,
    p_order_intent JSONB,
    p_actor TEXT DEFAULT 'Devarsh',
    p_rationale TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_request trading.limited_live_requests%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Devarsh');
    v_order JSONB := coalesce(p_order_intent, '{}'::jsonb);
    v_symbol TEXT := upper(nullif(trim(coalesce(v_order->>'symbol', v_request.symbol)), ''));
    v_side TEXT := lower(nullif(trim(coalesce(v_order->>'side', '')), ''));
    v_quantity NUMERIC := NULLIF(v_order->>'quantity', '')::NUMERIC;
    v_price NUMERIC := NULLIF(v_order->>'price', '')::NUMERIC;
    v_notional NUMERIC := NULLIF(v_order->>'notional', '')::NUMERIC;
    v_order_id BIGINT;
    v_approval_id BIGINT;
    v_order_key TEXT;
BEGIN
    SELECT * INTO v_request
    FROM trading.limited_live_requests
    WHERE id = p_limited_live_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'limited_live_request % not found', p_limited_live_request_id;
    END IF;

    v_symbol := upper(nullif(trim(coalesce(v_order->>'symbol', v_request.symbol)), ''));
    v_side := lower(nullif(trim(coalesce(v_order->>'side', '')), ''));
    v_quantity := NULLIF(v_order->>'quantity', '')::NUMERIC;
    v_price := NULLIF(v_order->>'price', '')::NUMERIC;
    v_notional := coalesce(NULLIF(v_order->>'notional', '')::NUMERIC, v_quantity * v_price);

    IF v_symbol IS NULL THEN
        RAISE EXCEPTION 'order symbol is required';
    END IF;

    IF v_side NOT IN ('buy', 'sell', 'short', 'cover') THEN
        RAISE EXCEPTION 'order side must be buy, sell, short, or cover';
    END IF;

    IF v_quantity IS NULL OR v_quantity <= 0 THEN
        RAISE EXCEPTION 'order quantity must be positive';
    END IF;

    IF v_notional IS NULL AND v_price IS NULL THEN
        RAISE EXCEPTION 'order price or notional is required for risk checks';
    END IF;

    v_order_key := 'order-intent-' || p_limited_live_request_id::TEXT || '-' || regexp_replace(lower(v_symbol), '[^a-z0-9]+', '-', 'g') || '-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    INSERT INTO agent.approvals (
        task_id,
        approval_type,
        title,
        owner_agent,
        risk_level,
        status,
        requested_action,
        rationale
    )
    VALUES (
        NULL,
        'broker_order_intent',
        'Broker order intent approval: ' || v_symbol || ' ' || v_side,
        'Execution Safety Agent',
        'critical',
        'pending',
        jsonb_build_object(
            'limited_live_request_id', p_limited_live_request_id,
            'strategy_id', v_request.strategy_id,
            'instance_id', v_request.instance_id,
            'symbol', v_symbol,
            'side', v_side,
            'quantity', v_quantity,
            'price', v_price,
            'notional', v_notional,
            'broker_order_placement', false,
            'requires_execution_gate_check', true,
            'requires_order_risk_check', true
        ),
        coalesce(nullif(trim(coalesce(p_rationale, '')), ''), 'Per-order approval request. This does not place a broker order.')
    )
    RETURNING id INTO v_approval_id;

    INSERT INTO trading.order_intents (
        order_intent_key,
        limited_live_request_id,
        strategy_id,
        instance_id,
        client_code,
        account_code,
        book_key,
        symbol,
        exchange,
        instrument_type,
        side,
        order_type,
        quantity,
        limit_price,
        notional,
        estimated_loss,
        approval_id,
        created_by,
        rationale,
        risk_summary,
        evidence
    )
    VALUES (
        v_order_key,
        v_request.id,
        v_request.strategy_id,
        v_request.instance_id,
        nullif(trim(coalesce(v_order->>'client_code', v_order->>'clientCode')), ''),
        nullif(trim(coalesce(v_order->>'account_code', v_order->>'accountCode')), ''),
        coalesce(nullif(trim(coalesce(v_order->>'book_key', v_order->>'bookKey')), ''), v_request.book_key),
        v_symbol,
        coalesce(nullif(trim(coalesce(v_order->>'exchange', '')), ''), 'NSE'),
        coalesce(nullif(trim(coalesce(v_order->>'instrument_type', v_order->>'instrumentType')), ''), 'equity'),
        v_side,
        coalesce(nullif(trim(coalesce(v_order->>'order_type', v_order->>'orderType')), ''), 'market'),
        v_quantity,
        v_price,
        v_notional,
        NULLIF(v_order->>'estimated_loss', '')::NUMERIC,
        v_approval_id,
        v_actor,
        coalesce(nullif(trim(coalesce(p_rationale, '')), ''), 'Per-order approval request.'),
        jsonb_build_object(
            'limited_live_request_status', v_request.request_status,
            'limited_live_allowed', v_request.live_execution_allowed,
            'broker_order_placement', false
        ),
        jsonb_build_array(
            jsonb_build_object('limited_live_request_id', v_request.id),
            jsonb_build_object('approval_id', v_approval_id)
        )
    )
    RETURNING id INTO v_order_id;

    INSERT INTO agent.inbox_items (
        task_id,
        title,
        owner_agent,
        status,
        priority,
        recommended_action,
        evidence,
        target_workspace
    )
    VALUES (
        NULL,
        'Per-order approval required: ' || v_symbol || ' ' || v_side,
        'Execution Safety Agent',
        'needs_review',
        'critical',
        'Review order intent, run pre-trade risk gate, and do not place a broker order unless all gates pass.',
        jsonb_build_array(
            jsonb_build_object('order_intent_id', v_order_id),
            jsonb_build_object('approval_id', v_approval_id),
            jsonb_build_object('broker_order_placement', false)
        ),
        'risk'
    );

    RETURN jsonb_build_object(
        'order_intent_id', v_order_id,
        'approval_id', v_approval_id,
        'limited_live_request_id', v_request.id,
        'status', 'pending_approval',
        'broker_order_allowed', false,
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION trading.evaluate_order_intent_risk(
    p_order_intent_id BIGINT,
    p_actor TEXT DEFAULT 'Execution Safety Agent'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_order trading.order_intents%ROWTYPE;
    v_request trading.limited_live_requests%ROWTYPE;
    v_approval agent.approvals%ROWTYPE;
    v_book_mandate books.book_mandates%ROWTYPE;
    v_gate_result JSONB;
    v_gate_check_id BIGINT;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Execution Safety Agent');
    v_reasons TEXT[] := ARRAY[]::TEXT[];
    v_warnings TEXT[] := ARRAY[]::TEXT[];
    v_notional NUMERIC;
    v_current_daily_pnl NUMERIC := 0;
    v_current_gross_exposure NUMERIC := 0;
    v_account_equity NUMERIC;
    v_max_leverage NUMERIC;
    v_leverage_after NUMERIC;
    v_gross_after NUMERIC;
    v_check_status TEXT := 'blocked';
    v_live_allowed BOOLEAN := false;
    v_check_id BIGINT;
    v_check_key TEXT;
BEGIN
    SELECT * INTO v_order
    FROM trading.order_intents
    WHERE id = p_order_intent_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'order_intent % not found', p_order_intent_id;
    END IF;

    SELECT * INTO v_request
    FROM trading.limited_live_requests
    WHERE id = v_order.limited_live_request_id;

    SELECT * INTO v_approval
    FROM agent.approvals
    WHERE id = v_order.approval_id;

    IF NOT FOUND OR v_approval.status <> 'approved' THEN
        v_reasons := array_append(v_reasons, 'per_order_approval_not_approved');
    END IF;

    v_notional := coalesce(v_order.notional, v_order.quantity * v_order.limit_price);

    IF v_notional IS NULL THEN
        v_reasons := array_append(v_reasons, 'order_notional_missing');
    END IF;

    v_gate_result := trading.evaluate_execution_gate(
        v_order.limited_live_request_id,
        v_actor,
        jsonb_build_object(
            'order_intent_id', v_order.id,
            'symbol', v_order.symbol,
            'side', v_order.side,
            'quantity', v_order.quantity,
            'price', v_order.limit_price,
            'notional', v_notional,
            'source', 'order_intent_risk_gate'
        )
    );

    v_gate_check_id := NULLIF(v_gate_result->>'execution_gate_check_id', '')::BIGINT;

    IF v_gate_result->>'gate_status' <> 'passed' THEN
        SELECT array_agg(value::TEXT)
        INTO v_reasons
        FROM (
            SELECT unnest(v_reasons) AS value
            UNION
            SELECT jsonb_array_elements_text(v_gate_result->'block_reasons') AS value
        ) reasons;
    END IF;

    IF v_request.id IS NULL THEN
        v_reasons := array_append(v_reasons, 'limited_live_request_missing');
    ELSE
        IF v_request.max_notional IS NOT NULL AND v_notional IS NOT NULL AND abs(v_notional) > v_request.max_notional THEN
            v_reasons := array_append(v_reasons, 'order_notional_exceeds_limited_live_limit');
        END IF;

        SELECT coalesce(sum(coalesce(realized_pnl, 0)), 0)
        INTO v_current_daily_pnl
        FROM trading.trade_activity_ledger
        WHERE trade_ts::date = CURRENT_DATE
          AND (v_order.account_code IS NULL OR account_code = v_order.account_code)
          AND (v_order.client_code IS NULL OR client_code = v_order.client_code);

        IF v_request.max_daily_loss IS NOT NULL
           AND (v_current_daily_pnl - coalesce(abs(v_order.estimated_loss), 0)) <= -(abs(v_request.max_daily_loss)) THEN
            v_reasons := array_append(v_reasons, 'max_daily_loss_breached');
        END IF;
    END IF;

    IF v_order.book_key IS NOT NULL THEN
        SELECT * INTO v_book_mandate
        FROM books.book_mandates
        WHERE book_key = v_order.book_key;

        v_max_leverage := v_book_mandate.max_leverage;
    END IF;

    IF v_max_leverage IS NOT NULL THEN
        SELECT ps.equity
        INTO v_account_equity
        FROM portfolio.snapshots ps
        JOIN portfolio.accounts pa ON pa.id = ps.account_id
        WHERE v_order.account_code IS NOT NULL
          AND pa.account_code = v_order.account_code
        ORDER BY ps.ts DESC
        LIMIT 1;

        SELECT coalesce(sum(gross_exposure), 0)
        INTO v_current_gross_exposure
        FROM books.v_book_positions
        WHERE (v_order.account_code IS NULL OR account_code = v_order.account_code)
          AND (v_order.client_code IS NULL OR client_code = v_order.client_code)
          AND (v_order.book_key IS NULL OR book_key = v_order.book_key)
          AND status = 'active';

        v_gross_after := coalesce(v_current_gross_exposure, 0) + coalesce(abs(v_notional), 0);

        IF v_account_equity IS NULL OR v_account_equity <= 0 THEN
            v_reasons := array_append(v_reasons, 'leverage_equity_snapshot_missing');
        ELSE
            v_leverage_after := v_gross_after / v_account_equity;
            IF v_leverage_after > v_max_leverage THEN
                v_reasons := array_append(v_reasons, 'max_leverage_exceeded');
            END IF;
        END IF;
    ELSE
        v_warnings := array_append(v_warnings, 'book_max_leverage_not_configured');
    END IF;

    IF array_length(v_reasons, 1) IS NULL THEN
        v_check_status := 'passed';
        v_live_allowed := true;
    END IF;

    v_check_key := 'order-risk-' || v_order.id::TEXT || '-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    INSERT INTO trading.order_risk_checks (
        order_intent_id,
        check_key,
        check_status,
        block_reasons,
        warnings,
        calculated_notional,
        current_daily_pnl,
        max_daily_loss,
        account_equity,
        current_gross_exposure,
        estimated_gross_exposure_after,
        max_leverage,
        estimated_leverage_after,
        execution_gate_check_id,
        policy_snapshot,
        approval_status,
        broker_order_allowed,
        live_execution_allowed,
        checked_by
    )
    VALUES (
        v_order.id,
        v_check_key,
        v_check_status,
        coalesce(v_reasons, ARRAY[]::TEXT[]),
        coalesce(v_warnings, ARRAY[]::TEXT[]),
        v_notional,
        v_current_daily_pnl,
        v_request.max_daily_loss,
        v_account_equity,
        v_current_gross_exposure,
        v_gross_after,
        v_max_leverage,
        v_leverage_after,
        v_gate_check_id,
        jsonb_build_object(
            'limited_live_request_status', v_request.request_status,
            'limited_live_request_live_allowed', v_request.live_execution_allowed,
            'execution_gate_result', v_gate_result,
            'broker_order_placement', false
        ),
        v_approval.status,
        v_live_allowed,
        v_live_allowed,
        v_actor
    )
    RETURNING id INTO v_check_id;

    UPDATE trading.order_intents
    SET latest_execution_gate_check_id = v_gate_check_id,
        latest_order_risk_check_id = v_check_id,
        gate_status = v_check_status,
        status = CASE WHEN v_check_status = 'passed' THEN 'approved_for_broker' ELSE 'blocked_by_risk' END,
        broker_order_allowed = v_live_allowed,
        live_execution_allowed = v_live_allowed,
        risk_summary = jsonb_build_object(
            'check_status', v_check_status,
            'block_reasons', coalesce(v_reasons, ARRAY[]::TEXT[]),
            'warnings', coalesce(v_warnings, ARRAY[]::TEXT[]),
            'calculated_notional', v_notional,
            'current_daily_pnl', v_current_daily_pnl,
            'max_daily_loss', v_request.max_daily_loss,
            'max_leverage', v_max_leverage,
            'estimated_leverage_after', v_leverage_after,
            'broker_order_placement', false
        ),
        updated_at = now()
    WHERE id = v_order.id;

    RETURN jsonb_build_object(
        'order_intent_id', v_order.id,
        'order_risk_check_id', v_check_id,
        'execution_gate_check_id', v_gate_check_id,
        'check_status', v_check_status,
        'block_reasons', coalesce(v_reasons, ARRAY[]::TEXT[]),
        'warnings', coalesce(v_warnings, ARRAY[]::TEXT[]),
        'broker_order_allowed', v_live_allowed,
        'live_execution_allowed', v_live_allowed
    );
END;
$$;

CREATE OR REPLACE VIEW trading.v_order_intents AS
SELECT
    oi.id,
    oi.order_intent_key,
    oi.limited_live_request_id,
    llr.request_key AS limited_live_request_key,
    oi.strategy_id,
    sc.name AS strategy_name,
    oi.instance_id,
    si.instance_name,
    oi.client_code,
    oi.account_code,
    oi.book_key,
    ib.book_name,
    oi.symbol,
    oi.exchange,
    oi.instrument_type,
    oi.side,
    oi.order_type,
    oi.quantity,
    oi.limit_price,
    oi.notional,
    oi.estimated_loss,
    oi.status,
    oi.approval_id,
    ap.status AS approval_status,
    oi.latest_execution_gate_check_id,
    oi.latest_order_risk_check_id,
    oi.gate_status,
    oi.broker_order_allowed,
    oi.live_execution_allowed,
    oi.created_by,
    oi.rationale,
    oi.risk_summary,
    oi.evidence,
    oi.created_at,
    oi.updated_at
FROM trading.order_intents oi
LEFT JOIN trading.limited_live_requests llr ON llr.id = oi.limited_live_request_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = oi.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = oi.instance_id
LEFT JOIN books.investment_books ib ON ib.book_key = oi.book_key
LEFT JOIN agent.approvals ap ON ap.id = oi.approval_id
ORDER BY oi.updated_at DESC, oi.created_at DESC;

CREATE OR REPLACE VIEW trading.v_order_risk_checks AS
SELECT
    orc.id,
    orc.order_intent_id,
    oi.order_intent_key,
    oi.symbol,
    oi.side,
    oi.book_key,
    oi.client_code,
    oi.account_code,
    orc.check_key,
    orc.check_status,
    orc.block_reasons,
    orc.warnings,
    orc.calculated_notional,
    orc.current_daily_pnl,
    orc.max_daily_loss,
    orc.account_equity,
    orc.current_gross_exposure,
    orc.estimated_gross_exposure_after,
    orc.max_leverage,
    orc.estimated_leverage_after,
    orc.execution_gate_check_id,
    orc.policy_snapshot,
    orc.approval_status,
    orc.broker_order_allowed,
    orc.live_execution_allowed,
    orc.checked_by,
    orc.checked_at
FROM trading.order_risk_checks orc
LEFT JOIN trading.order_intents oi ON oi.id = orc.order_intent_id
ORDER BY orc.checked_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_create_order_intent', 'mcp_tool', 'Execution Safety Agent', 'write_with_approval', true, 'Create a broker order intent that requires per-order approval and pre-trade risk checks. Does not place broker orders.', '{"writes":["trading.order_intents","agent.approvals","agent.inbox_items"],"broker_order_placement":false}'::jsonb),
    ('ai_os_evaluate_order_intent_risk', 'mcp_tool', 'Execution Safety Agent', 'write_with_approval', true, 'Evaluate a broker order intent against per-order approval, limited-live gate, daily loss, leverage, and global execution policy.', '{"writes":["trading.order_risk_checks","trading.execution_gate_checks"],"broker_order_placement":false}'::jsonb),
    ('ai_os_order_intents', 'mcp_tool', 'Trading Desk Agent', 'read_only', true, 'Read order intents and approval/risk status.', '{"reads":["trading.v_order_intents","trading.v_order_risk_checks"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key,
    workflow_name,
    workflow_type,
    owner_agent,
    trigger_type,
    status,
    permission_level,
    input_sources,
    output_targets,
    approval_required,
    schedule_hint,
    notes,
    metadata
)
VALUES (
    'per_order_pretrade_risk_gate',
    'Per-Order Pre-Trade Risk Gate',
    'execution_safety',
    'Execution Safety Agent',
    'manual_or_api',
    'active',
    'write_with_approval',
    ARRAY['trading.order_intents','trading.limited_live_requests','agent.approvals','books.book_mandates','portfolio.snapshots','trading.trade_activity_ledger']::TEXT[],
    ARRAY['trading.order_risk_checks','trading.execution_gate_checks','agent.inbox_items']::TEXT[],
    true,
    'before any future live broker order adapter call',
    'Per-order approval and risk gate. Current implementation audits and blocks; it does not place broker orders.',
    '{"broker_order_placement":false,"checks":["per_order_approval","limited_live","daily_loss","leverage","global_execution_policy"]}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT object_name
        FROM unnest(warehouse_objects || ARRAY[
            'trading.order_intents',
            'trading.order_risk_checks'
        ]::TEXT[]) AS object_name
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_create_order_intent',
            'ai_os_evaluate_order_intent_risk',
            'ai_os_order_intents'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Route any future broker order through per-order approval and pre-trade risk gate first.',
    updated_at = now()
WHERE module_key IN ('approval_center', 'trading_desk', 'strategy_registry');
