CREATE TABLE IF NOT EXISTS trading.execution_control_state (
    state_key TEXT PRIMARY KEY DEFAULT 'global',
    global_execution_locked BOOLEAN NOT NULL DEFAULT true,
    broker_execution_policy TEXT NOT NULL DEFAULT 'read_only_blocked',
    paper_trading_allowed BOOLEAN NOT NULL DEFAULT true,
    limited_live_allowed BOOLEAN NOT NULL DEFAULT false,
    live_broker_writes_allowed BOOLEAN NOT NULL DEFAULT false,
    lock_reason TEXT NOT NULL DEFAULT 'Default locked state. Broker writes are disabled until explicit policy, risk, and human gates pass.',
    updated_by TEXT NOT NULL DEFAULT 'Execution Safety Agent',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    CONSTRAINT chk_execution_control_live_policy CHECK (
        live_broker_writes_allowed = false
        OR (
            global_execution_locked = false
            AND limited_live_allowed = true
            AND broker_execution_policy = 'limited_live_approved'
        )
    )
);

CREATE TABLE IF NOT EXISTS trading.global_kill_switch_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    action TEXT NOT NULL DEFAULT 'engaged',
    trigger_source TEXT NOT NULL DEFAULT 'manual',
    trigger_reason TEXT NOT NULL,
    enforced_by TEXT NOT NULL DEFAULT 'Execution Safety Agent',
    risk_event_id BIGINT REFERENCES risk.events(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    affected_instances INTEGER NOT NULL DEFAULT 0,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    global_execution_locked BOOLEAN NOT NULL DEFAULT true,
    live_broker_writes_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_global_kill_switch_locks_execution CHECK (global_execution_locked = true),
    CONSTRAINT chk_global_kill_switch_live_disabled CHECK (live_broker_writes_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_global_kill_switch_created ON trading.global_kill_switch_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_global_kill_switch_action ON trading.global_kill_switch_events (action);

CREATE TABLE IF NOT EXISTS trading.limited_live_requests (
    id BIGSERIAL PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    instance_id BIGINT REFERENCES strategy.strategy_instances(id) ON DELETE SET NULL,
    book_key TEXT,
    symbol TEXT,
    requested_mode TEXT NOT NULL DEFAULT 'limited_live',
    request_status TEXT NOT NULL DEFAULT 'pending_approval',
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    max_notional NUMERIC,
    max_orders_per_day INTEGER,
    max_daily_loss NUMERIC,
    expires_at TIMESTAMPTZ,
    requested_by TEXT NOT NULL DEFAULT 'Devarsh',
    rationale TEXT,
    risk_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    gate_requirements TEXT[] NOT NULL DEFAULT ARRAY[
        'human_approval',
        'risk_approval',
        'global_execution_unlocked',
        'broker_policy_limited_live',
        'order_intent_within_limits',
        'audit_log'
    ]::TEXT[],
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_limited_live_request_live_allowed CHECK (
        live_execution_allowed = false OR request_status = 'limited_live_approved'
    )
);

CREATE INDEX IF NOT EXISTS idx_limited_live_requests_status ON trading.limited_live_requests (request_status);
CREATE INDEX IF NOT EXISTS idx_limited_live_requests_approval ON trading.limited_live_requests (approval_id);
CREATE INDEX IF NOT EXISTS idx_limited_live_requests_strategy ON trading.limited_live_requests (strategy_id);

CREATE TABLE IF NOT EXISTS trading.execution_gate_checks (
    id BIGSERIAL PRIMARY KEY,
    check_key TEXT NOT NULL UNIQUE,
    limited_live_request_id BIGINT REFERENCES trading.limited_live_requests(id) ON DELETE SET NULL,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    instance_id BIGINT REFERENCES strategy.strategy_instances(id) ON DELETE SET NULL,
    actor TEXT NOT NULL DEFAULT 'Execution Safety Agent',
    gate_status TEXT NOT NULL DEFAULT 'blocked',
    block_reasons TEXT[] NOT NULL DEFAULT '{}',
    order_intent JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    approval_status TEXT,
    global_execution_locked BOOLEAN NOT NULL DEFAULT true,
    live_broker_writes_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_execution_gate_live_allowed CHECK (
        live_execution_allowed = false
        OR (
            gate_status = 'passed'
            AND global_execution_locked = false
            AND live_broker_writes_allowed = true
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_execution_gate_checks_request ON trading.execution_gate_checks (limited_live_request_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_gate_checks_status ON trading.execution_gate_checks (gate_status, checked_at DESC);

INSERT INTO trading.execution_control_state (
    state_key,
    global_execution_locked,
    broker_execution_policy,
    paper_trading_allowed,
    limited_live_allowed,
    live_broker_writes_allowed,
    lock_reason,
    updated_by,
    evidence
)
VALUES (
    'global',
    true,
    'read_only_blocked',
    true,
    false,
    false,
    'Default locked state. Broker writes are disabled until explicit policy, risk, and human gates pass.',
    'Execution Safety Agent',
    jsonb_build_array(jsonb_build_object('source', 'migration_044_default_lock'))
)
ON CONFLICT (state_key) DO NOTHING;

CREATE OR REPLACE FUNCTION trading.engage_global_kill_switch(
    p_actor TEXT DEFAULT 'Execution Safety Agent',
    p_trigger_reason TEXT DEFAULT 'manual_global_kill_switch',
    p_trigger_source TEXT DEFAULT 'manual'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Execution Safety Agent');
    v_reason TEXT := coalesce(nullif(trim(coalesce(p_trigger_reason, '')), ''), 'manual_global_kill_switch');
    v_source TEXT := coalesce(nullif(trim(coalesce(p_trigger_source, '')), ''), 'manual');
    v_event_key TEXT;
    v_event_id BIGINT;
    v_risk_event_id BIGINT;
    v_inbox_item_id BIGINT;
    v_affected_instances INTEGER := 0;
BEGIN
    UPDATE strategy.strategy_instances
    SET status = 'killed',
        stopped_at = coalesce(stopped_at, now()),
        config = config || jsonb_build_object(
            'global_kill_switch_enforced', true,
            'global_kill_switch_reason', v_reason,
            'live_execution_allowed', false,
            'requires_separate_reapproval', true
        ),
        notes = coalesce(notes, '') || ' Global kill switch enforced: ' || v_reason
    WHERE mode IN ('live', 'limited_live')
      AND status IN ('ready', 'running');

    GET DIAGNOSTICS v_affected_instances = ROW_COUNT;

    UPDATE trading.execution_control_state
    SET global_execution_locked = true,
        broker_execution_policy = 'read_only_blocked',
        limited_live_allowed = false,
        live_broker_writes_allowed = false,
        lock_reason = v_reason,
        updated_by = v_actor,
        updated_at = now(),
        evidence = evidence || jsonb_build_object(
            'source', v_source,
            'reason', v_reason,
            'affected_instances', v_affected_instances,
            'live_broker_writes_allowed', false
        )
    WHERE state_key = 'global';

    INSERT INTO risk.events (
        scope_type,
        scope_ref,
        severity,
        status,
        title,
        message,
        evidence,
        approval_id
    )
    VALUES (
        'global_execution_safety',
        'global',
        'critical',
        'open',
        'Global execution kill switch engaged',
        'All broker write paths are locked. Limited-live approvals and live broker writes remain disabled until separate review.',
        jsonb_build_array(
            jsonb_build_object('reason', v_reason),
            jsonb_build_object('source', v_source),
            jsonb_build_object('affected_instances', v_affected_instances),
            jsonb_build_object('live_broker_writes_allowed', false)
        ),
        NULL
    )
    RETURNING id INTO v_risk_event_id;

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
        'Global execution kill switch engaged',
        'Execution Safety Agent',
        'needs_review',
        'critical',
        'Confirm broker write paths are locked, review any affected limited-live requests, and require fresh approval before reactivation.',
        jsonb_build_array(jsonb_build_object('risk_event_id', v_risk_event_id), jsonb_build_object('live_broker_writes_allowed', false)),
        'risk'
    )
    RETURNING id INTO v_inbox_item_id;

    v_event_key := 'global-kill-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS') || '-' || left(regexp_replace(lower(v_reason), '[^a-z0-9]+', '-', 'g'), 32);

    INSERT INTO trading.global_kill_switch_events (
        event_key,
        action,
        trigger_source,
        trigger_reason,
        enforced_by,
        risk_event_id,
        inbox_item_id,
        affected_instances,
        evidence,
        global_execution_locked,
        live_broker_writes_allowed
    )
    VALUES (
        v_event_key,
        'engaged',
        v_source,
        v_reason,
        v_actor,
        v_risk_event_id,
        v_inbox_item_id,
        v_affected_instances,
        jsonb_build_array(
            jsonb_build_object('global_execution_locked', true),
            jsonb_build_object('live_broker_writes_allowed', false)
        ),
        true,
        false
    )
    RETURNING id INTO v_event_id;

    RETURN jsonb_build_object(
        'global_kill_switch_event_id', v_event_id,
        'risk_event_id', v_risk_event_id,
        'inbox_item_id', v_inbox_item_id,
        'affected_instances', v_affected_instances,
        'global_execution_locked', true,
        'live_broker_writes_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION trading.request_limited_live_approval(
    p_strategy_id BIGINT DEFAULT NULL,
    p_instance_id BIGINT DEFAULT NULL,
    p_book_key TEXT DEFAULT NULL,
    p_symbol TEXT DEFAULT NULL,
    p_max_notional NUMERIC DEFAULT NULL,
    p_max_orders_per_day INTEGER DEFAULT 1,
    p_max_daily_loss NUMERIC DEFAULT NULL,
    p_expires_at TIMESTAMPTZ DEFAULT NULL,
    p_actor TEXT DEFAULT 'Devarsh',
    p_rationale TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_strategy strategy.strategy_candidates%ROWTYPE;
    v_instance strategy.strategy_instances%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Devarsh');
    v_rationale TEXT := coalesce(nullif(trim(coalesce(p_rationale, '')), ''), 'Limited-live approval request from dashboard/API.');
    v_request_key TEXT;
    v_request_id BIGINT;
    v_approval_id BIGINT;
    v_inbox_item_id BIGINT;
BEGIN
    IF p_strategy_id IS NULL AND p_instance_id IS NULL AND nullif(trim(coalesce(p_symbol, '')), '') IS NULL THEN
        RAISE EXCEPTION 'strategy_id, instance_id, or symbol is required for limited-live approval';
    END IF;

    IF p_instance_id IS NOT NULL THEN
        SELECT * INTO v_instance
        FROM strategy.strategy_instances
        WHERE id = p_instance_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'strategy instance % not found', p_instance_id;
        END IF;

        p_strategy_id := coalesce(p_strategy_id, v_instance.strategy_id);
    END IF;

    IF p_strategy_id IS NOT NULL THEN
        SELECT * INTO v_strategy
        FROM strategy.strategy_candidates
        WHERE id = p_strategy_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'strategy % not found', p_strategy_id;
        END IF;

        IF v_strategy.status IN ('blocked', 'rejected') OR v_strategy.activation_gate IN ('kill_switch_enforced', 'blocked_by_committee') THEN
            RAISE EXCEPTION 'strategy % is blocked by status/gate and cannot request limited live', p_strategy_id;
        END IF;
    END IF;

    v_request_key := 'limited-live-' || coalesce(p_strategy_id::TEXT, 'symbol-' || regexp_replace(lower(coalesce(p_symbol, 'unknown')), '[^a-z0-9]+', '-', 'g')) || '-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

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
        'limited_live_execution',
        'Limited-live execution request: ' || coalesce(v_strategy.name, p_symbol, 'strategy/symbol'),
        'Risk Agent',
        'critical',
        'pending',
        jsonb_build_object(
            'strategy_id', p_strategy_id,
            'instance_id', p_instance_id,
            'book_key', p_book_key,
            'symbol', p_symbol,
            'max_notional', p_max_notional,
            'max_orders_per_day', p_max_orders_per_day,
            'max_daily_loss', p_max_daily_loss,
            'expires_at', p_expires_at,
            'requires_global_unlock', true,
            'requires_execution_gate_check', true,
            'live_broker_writes_allowed', false
        ),
        v_rationale || ' Approval alone does not enable broker writes; global execution policy and gate checks must pass.'
    )
    RETURNING id INTO v_approval_id;

    INSERT INTO trading.limited_live_requests (
        request_key,
        strategy_id,
        instance_id,
        book_key,
        symbol,
        request_status,
        approval_id,
        max_notional,
        max_orders_per_day,
        max_daily_loss,
        expires_at,
        requested_by,
        rationale,
        risk_summary,
        live_execution_allowed
    )
    VALUES (
        v_request_key,
        p_strategy_id,
        p_instance_id,
        nullif(trim(coalesce(p_book_key, '')), ''),
        nullif(trim(coalesce(p_symbol, '')), ''),
        'pending_approval',
        v_approval_id,
        p_max_notional,
        greatest(coalesce(p_max_orders_per_day, 1), 1),
        p_max_daily_loss,
        coalesce(p_expires_at, now() + INTERVAL '7 days'),
        v_actor,
        v_rationale,
        jsonb_build_object(
            'global_execution_locked', (SELECT global_execution_locked FROM trading.execution_control_state WHERE state_key = 'global'),
            'live_broker_writes_allowed', false,
            'requires_human_and_risk_approval', true
        ),
        false
    )
    RETURNING id INTO v_request_id;

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
        'Limited-live request needs risk review #' || v_request_id::TEXT,
        'Execution Safety Agent',
        'needs_review',
        'critical',
        'Review strategy, risk limits, global execution lock, and broker policy. Do not place live orders from this request.',
        jsonb_build_array(
            jsonb_build_object('limited_live_request_id', v_request_id),
            jsonb_build_object('approval_id', v_approval_id),
            jsonb_build_object('live_broker_writes_allowed', false)
        ),
        'risk'
    )
    RETURNING id INTO v_inbox_item_id;

    RETURN jsonb_build_object(
        'limited_live_request_id', v_request_id,
        'approval_id', v_approval_id,
        'inbox_item_id', v_inbox_item_id,
        'request_status', 'pending_approval',
        'global_execution_locked', (SELECT global_execution_locked FROM trading.execution_control_state WHERE state_key = 'global'),
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION trading.sync_limited_live_request_approval(
    p_request_id BIGINT,
    p_actor TEXT DEFAULT 'Execution Safety Agent'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_request trading.limited_live_requests%ROWTYPE;
    v_approval agent.approvals%ROWTYPE;
    v_state trading.execution_control_state%ROWTYPE;
    v_new_status TEXT;
    v_live_allowed BOOLEAN := false;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Execution Safety Agent');
BEGIN
    SELECT * INTO v_request
    FROM trading.limited_live_requests
    WHERE id = p_request_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'limited_live_request % not found', p_request_id;
    END IF;

    SELECT * INTO v_approval
    FROM agent.approvals
    WHERE id = v_request.approval_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'approval % not found for limited_live_request %', v_request.approval_id, p_request_id;
    END IF;

    SELECT * INTO v_state
    FROM trading.execution_control_state
    WHERE state_key = 'global';

    IF v_approval.status = 'rejected' THEN
        v_new_status := 'rejected';
    ELSIF v_approval.status <> 'approved' THEN
        v_new_status := 'pending_approval';
    ELSIF now() > v_request.expires_at THEN
        v_new_status := 'expired';
    ELSIF v_state.global_execution_locked OR v_state.live_broker_writes_allowed IS DISTINCT FROM true OR v_state.broker_execution_policy <> 'limited_live_approved' THEN
        v_new_status := 'approved_but_global_locked';
    ELSE
        v_new_status := 'limited_live_approved';
        v_live_allowed := true;
    END IF;

    UPDATE trading.limited_live_requests
    SET request_status = v_new_status,
        live_execution_allowed = v_live_allowed,
        risk_summary = risk_summary || jsonb_build_object(
            'approval_status', v_approval.status,
            'global_execution_locked', v_state.global_execution_locked,
            'broker_execution_policy', v_state.broker_execution_policy,
            'live_broker_writes_allowed', v_state.live_broker_writes_allowed,
            'synced_by', v_actor,
            'synced_at', now()
        ),
        updated_at = now()
    WHERE id = v_request.id;

    RETURN jsonb_build_object(
        'limited_live_request_id', v_request.id,
        'approval_id', v_request.approval_id,
        'approval_status', v_approval.status,
        'request_status', v_new_status,
        'global_execution_locked', v_state.global_execution_locked,
        'broker_execution_policy', v_state.broker_execution_policy,
        'live_execution_allowed', v_live_allowed
    );
END;
$$;

CREATE OR REPLACE FUNCTION trading.evaluate_execution_gate(
    p_limited_live_request_id BIGINT DEFAULT NULL,
    p_actor TEXT DEFAULT 'Execution Safety Agent',
    p_order_intent JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_request trading.limited_live_requests%ROWTYPE;
    v_state trading.execution_control_state%ROWTYPE;
    v_approval agent.approvals%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Execution Safety Agent');
    v_order JSONB := coalesce(p_order_intent, '{}'::jsonb);
    v_notional NUMERIC;
    v_reasons TEXT[] := ARRAY[]::TEXT[];
    v_gate_status TEXT := 'blocked';
    v_live_allowed BOOLEAN := false;
    v_check_id BIGINT;
    v_check_key TEXT;
BEGIN
    SELECT * INTO v_state
    FROM trading.execution_control_state
    WHERE state_key = 'global';

    IF v_state.global_execution_locked THEN
        v_reasons := array_append(v_reasons, 'global_execution_locked');
    END IF;

    IF v_state.live_broker_writes_allowed IS DISTINCT FROM true THEN
        v_reasons := array_append(v_reasons, 'live_broker_writes_disabled');
    END IF;

    IF v_state.broker_execution_policy <> 'limited_live_approved' THEN
        v_reasons := array_append(v_reasons, 'broker_policy_not_limited_live_approved');
    END IF;

    IF p_limited_live_request_id IS NULL THEN
        v_reasons := array_append(v_reasons, 'limited_live_request_required');
    ELSE
        SELECT * INTO v_request
        FROM trading.limited_live_requests
        WHERE id = p_limited_live_request_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'limited_live_request % not found', p_limited_live_request_id;
        END IF;

        SELECT * INTO v_approval
        FROM agent.approvals
        WHERE id = v_request.approval_id;

        IF NOT FOUND OR v_approval.status <> 'approved' THEN
            v_reasons := array_append(v_reasons, 'human_risk_approval_not_approved');
        END IF;

        IF v_request.request_status <> 'limited_live_approved' THEN
            v_reasons := array_append(v_reasons, 'limited_live_request_not_active');
        END IF;

        IF now() > v_request.expires_at THEN
            v_reasons := array_append(v_reasons, 'limited_live_request_expired');
        END IF;

        v_notional := coalesce(
            NULLIF(v_order->>'notional', '')::NUMERIC,
            NULLIF(v_order->>'quantity', '')::NUMERIC * NULLIF(v_order->>'price', '')::NUMERIC
        );

        IF v_request.max_notional IS NOT NULL AND v_notional IS NOT NULL AND abs(v_notional) > v_request.max_notional THEN
            v_reasons := array_append(v_reasons, 'order_notional_exceeds_request_limit');
        END IF;
    END IF;

    IF array_length(v_reasons, 1) IS NULL THEN
        v_gate_status := 'passed';
        v_live_allowed := true;
    END IF;

    v_check_key := 'execution-gate-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    INSERT INTO trading.execution_gate_checks (
        check_key,
        limited_live_request_id,
        strategy_id,
        instance_id,
        actor,
        gate_status,
        block_reasons,
        order_intent,
        policy_snapshot,
        approval_id,
        approval_status,
        global_execution_locked,
        live_broker_writes_allowed,
        live_execution_allowed
    )
    VALUES (
        v_check_key,
        p_limited_live_request_id,
        v_request.strategy_id,
        v_request.instance_id,
        v_actor,
        v_gate_status,
        coalesce(v_reasons, ARRAY[]::TEXT[]),
        v_order,
        jsonb_build_object(
            'broker_execution_policy', v_state.broker_execution_policy,
            'paper_trading_allowed', v_state.paper_trading_allowed,
            'limited_live_allowed', v_state.limited_live_allowed,
            'live_broker_writes_allowed', v_state.live_broker_writes_allowed
        ),
        v_request.approval_id,
        v_approval.status,
        v_state.global_execution_locked,
        v_state.live_broker_writes_allowed,
        v_live_allowed
    )
    RETURNING id INTO v_check_id;

    RETURN jsonb_build_object(
        'execution_gate_check_id', v_check_id,
        'limited_live_request_id', p_limited_live_request_id,
        'gate_status', v_gate_status,
        'block_reasons', coalesce(v_reasons, ARRAY[]::TEXT[]),
        'global_execution_locked', v_state.global_execution_locked,
        'live_broker_writes_allowed', v_state.live_broker_writes_allowed,
        'live_execution_allowed', v_live_allowed
    );
END;
$$;

CREATE OR REPLACE VIEW trading.v_execution_control_state AS
SELECT
    ecs.state_key,
    ecs.global_execution_locked,
    ecs.broker_execution_policy,
    ecs.paper_trading_allowed,
    ecs.limited_live_allowed,
    ecs.live_broker_writes_allowed,
    ecs.lock_reason,
    ecs.updated_by,
    ecs.updated_at,
    ecs.evidence,
    (SELECT count(*) FROM trading.limited_live_requests llr WHERE llr.request_status IN ('pending_approval', 'approved_but_global_locked', 'limited_live_approved')) AS open_limited_live_requests,
    (SELECT count(*) FROM trading.execution_gate_checks egc WHERE egc.gate_status = 'blocked') AS blocked_gate_checks,
    (SELECT max(created_at) FROM trading.global_kill_switch_events) AS latest_global_kill_switch_at
FROM trading.execution_control_state ecs
WHERE ecs.state_key = 'global';

CREATE OR REPLACE VIEW trading.v_global_kill_switch_events AS
SELECT
    gkse.id,
    gkse.event_key,
    gkse.action,
    gkse.trigger_source,
    gkse.trigger_reason,
    gkse.enforced_by,
    gkse.risk_event_id,
    re.status AS risk_event_status,
    gkse.inbox_item_id,
    gkse.affected_instances,
    gkse.evidence,
    gkse.global_execution_locked,
    gkse.live_broker_writes_allowed,
    gkse.created_at
FROM trading.global_kill_switch_events gkse
LEFT JOIN risk.events re ON re.id = gkse.risk_event_id
ORDER BY gkse.created_at DESC;

CREATE OR REPLACE VIEW trading.v_limited_live_requests AS
SELECT
    llr.id,
    llr.request_key,
    llr.strategy_id,
    sc.name AS strategy_name,
    llr.instance_id,
    si.instance_name,
    llr.book_key,
    llr.symbol,
    llr.requested_mode,
    llr.request_status,
    llr.approval_id,
    ap.status AS approval_status,
    llr.max_notional,
    llr.max_orders_per_day,
    llr.max_daily_loss,
    llr.expires_at,
    llr.requested_by,
    llr.rationale,
    llr.risk_summary,
    llr.gate_requirements,
    llr.live_execution_allowed,
    llr.created_at,
    llr.updated_at
FROM trading.limited_live_requests llr
LEFT JOIN strategy.strategy_candidates sc ON sc.id = llr.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = llr.instance_id
LEFT JOIN agent.approvals ap ON ap.id = llr.approval_id
ORDER BY llr.updated_at DESC, llr.created_at DESC;

CREATE OR REPLACE VIEW trading.v_execution_gate_checks AS
SELECT
    egc.id,
    egc.check_key,
    egc.limited_live_request_id,
    llr.request_key,
    egc.strategy_id,
    sc.name AS strategy_name,
    egc.instance_id,
    si.instance_name,
    egc.actor,
    egc.gate_status,
    egc.block_reasons,
    egc.order_intent,
    egc.policy_snapshot,
    egc.approval_id,
    egc.approval_status,
    egc.global_execution_locked,
    egc.live_broker_writes_allowed,
    egc.live_execution_allowed,
    egc.checked_at
FROM trading.execution_gate_checks egc
LEFT JOIN trading.limited_live_requests llr ON llr.id = egc.limited_live_request_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = egc.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = egc.instance_id
ORDER BY egc.checked_at DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_execution_control_state', 'mcp_tool', 'Execution Safety Agent', 'read_only', true, 'Read global execution lock, broker policy, and limited-live safety state.', '{"reads":["trading.v_execution_control_state"]}'::jsonb),
    ('ai_os_engage_global_kill_switch', 'mcp_tool', 'Execution Safety Agent', 'write_with_approval', true, 'Engage the global execution kill switch and block all broker write paths.', '{"writes":["trading.global_kill_switch_events","risk.events","agent.inbox_items"],"live_broker_writes_allowed":false}'::jsonb),
    ('ai_os_request_limited_live_approval', 'mcp_tool', 'Risk Agent', 'write_with_approval', true, 'Create a limited-live approval request. Approval alone does not enable broker writes.', '{"writes":["trading.limited_live_requests","agent.approvals","agent.inbox_items"],"live_broker_writes_allowed":false}'::jsonb),
    ('ai_os_sync_limited_live_approval', 'mcp_tool', 'Execution Safety Agent', 'write_with_approval', true, 'Sync limited-live request status from human/risk approval and current global execution policy.', '{"writes":["trading.limited_live_requests"]}'::jsonb),
    ('ai_os_evaluate_execution_gate', 'mcp_tool', 'Execution Safety Agent', 'write_with_approval', true, 'Evaluate a proposed order intent against limited-live request, risk approval, and global broker policy.', '{"writes":["trading.execution_gate_checks"],"broker_order_placement":false}'::jsonb)
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
    'execution_safety_gate',
    'Execution Safety Gate',
    'execution_safety',
    'Execution Safety Agent',
    'manual_or_api',
    'active',
    'write_with_approval',
    ARRAY['trading.limited_live_requests','agent.approvals','trading.execution_control_state']::TEXT[],
    ARRAY['trading.execution_gate_checks','risk.events','agent.inbox_items']::TEXT[],
    true,
    'before any future broker write adapter is allowed',
    'Global lock and limited-live gate. Current state remains broker-write disabled.',
    '{"live_broker_writes_allowed":false,"broker_order_placement":false}'::jsonb
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
SET status = 'active',
    warehouse_objects = ARRAY(
        SELECT DISTINCT object_name
        FROM unnest(warehouse_objects || ARRAY[
            'trading.execution_control_state',
            'trading.global_kill_switch_events',
            'trading.limited_live_requests',
            'trading.execution_gate_checks'
        ]::TEXT[]) AS object_name
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_execution_control_state',
            'ai_os_engage_global_kill_switch',
            'ai_os_request_limited_live_approval',
            'ai_os_sync_limited_live_approval',
            'ai_os_evaluate_execution_gate'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Use global lock and limited-live gate before any future broker write adapter.',
    updated_at = now()
WHERE module_key IN ('approval_center', 'trading_desk', 'strategy_registry');
