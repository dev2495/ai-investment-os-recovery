CREATE TABLE IF NOT EXISTS strategy.kill_switch_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    paper_monitor_session_id BIGINT REFERENCES strategy.paper_monitor_sessions(id) ON DELETE SET NULL,
    drift_check_id BIGINT REFERENCES strategy.drift_checks(id) ON DELETE SET NULL,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    instance_id BIGINT REFERENCES strategy.strategy_instances(id) ON DELETE SET NULL,
    trigger_source TEXT NOT NULL DEFAULT 'manual',
    trigger_reason TEXT NOT NULL,
    enforcement_status TEXT NOT NULL DEFAULT 'enforced',
    action_taken TEXT NOT NULL DEFAULT 'paper_monitor_stopped',
    enforced_by TEXT NOT NULL DEFAULT 'Risk Agent',
    risk_event_id BIGINT REFERENCES risk.events(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    enforced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_kill_switch_live_disabled CHECK (live_execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_kill_switch_events_session ON strategy.kill_switch_events (paper_monitor_session_id);
CREATE INDEX IF NOT EXISTS idx_kill_switch_events_drift ON strategy.kill_switch_events (drift_check_id);
CREATE INDEX IF NOT EXISTS idx_kill_switch_events_strategy ON strategy.kill_switch_events (strategy_id);
CREATE INDEX IF NOT EXISTS idx_kill_switch_events_status ON strategy.kill_switch_events (enforcement_status);

CREATE OR REPLACE FUNCTION strategy.enforce_strategy_kill_switch(
    p_paper_monitor_session_id BIGINT DEFAULT NULL,
    p_drift_check_id BIGINT DEFAULT NULL,
    p_actor TEXT DEFAULT 'Risk Agent',
    p_trigger_reason TEXT DEFAULT 'manual_kill_switch'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_session strategy.paper_monitor_sessions%ROWTYPE;
    v_drift strategy.drift_checks%ROWTYPE;
    v_strategy strategy.strategy_candidates%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Risk Agent');
    v_reason TEXT := coalesce(nullif(trim(coalesce(p_trigger_reason, '')), ''), 'manual_kill_switch');
    v_event_key TEXT;
    v_kill_event_id BIGINT;
    v_stop_result JSONB;
    v_risk_event_id BIGINT;
    v_inbox_item_id BIGINT;
    v_action_taken TEXT := 'paper_monitor_stopped';
BEGIN
    IF p_paper_monitor_session_id IS NULL AND p_drift_check_id IS NULL THEN
        RAISE EXCEPTION 'paper_monitor_session_id or drift_check_id is required';
    END IF;

    IF p_drift_check_id IS NOT NULL THEN
        SELECT * INTO v_drift
        FROM strategy.drift_checks
        WHERE id = p_drift_check_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'drift_check_id % not found', p_drift_check_id;
        END IF;

        IF v_drift.live_execution_allowed IS DISTINCT FROM false THEN
            RAISE EXCEPTION 'kill switch blocked because drift check live_execution_allowed is not false';
        END IF;

        p_paper_monitor_session_id := coalesce(p_paper_monitor_session_id, v_drift.paper_monitor_session_id);
    END IF;

    SELECT * INTO v_session
    FROM strategy.paper_monitor_sessions
    WHERE id = p_paper_monitor_session_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper_monitor_session_id % not found', p_paper_monitor_session_id;
    END IF;

    IF v_session.live_execution_allowed IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'kill switch blocked because paper monitor live_execution_allowed is not false';
    END IF;

    SELECT * INTO v_strategy
    FROM strategy.strategy_candidates
    WHERE id = v_session.strategy_id
    FOR UPDATE;

    v_event_key := 'kill-switch-session-' || v_session.id::TEXT || '-reason-' || left(regexp_replace(lower(v_reason), '[^a-z0-9]+', '-', 'g'), 48);

    IF v_session.status <> 'stopped' THEN
        v_stop_result := strategy.stop_paper_monitor(v_session.id, v_actor, 'kill_switch:' || v_reason);
    ELSE
        v_action_taken := 'already_stopped';
    END IF;

    UPDATE strategy.paper_monitor_sessions
    SET status = 'killed',
        heartbeat_status = 'stopped',
        live_execution_allowed = false,
        notes = coalesce(notes, '') || ' Kill switch enforced: ' || v_reason,
        updated_at = now()
    WHERE id = v_session.id;

    UPDATE strategy.strategy_instances
    SET status = 'killed',
        stopped_at = coalesce(stopped_at, now()),
        config = config || jsonb_build_object(
            'paper_monitor_status', 'killed',
            'kill_switch_enforced', true,
            'kill_switch_reason', v_reason,
            'live_execution_allowed', false,
            'requires_separate_reapproval', true
        ),
        notes = coalesce(notes, '') || ' Kill switch enforced: ' || v_reason
    WHERE id = v_session.instance_id;

    UPDATE strategy.strategy_candidates
    SET status = 'blocked',
        activation_gate = 'kill_switch_enforced',
        validation_status = 'kill_switch_review_required',
        updated_at = now()
    WHERE id = v_session.strategy_id;

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
        'strategy_kill_switch',
        v_session.session_key,
        'critical',
        'open',
        'Strategy kill switch enforced: ' || coalesce(v_strategy.name, 'strategy ' || v_session.strategy_id::TEXT),
        'Paper monitor stopped and strategy promotion blocked. Live execution remains disabled.',
        jsonb_build_array(
            jsonb_build_object('paper_monitor_session_id', v_session.id),
            jsonb_build_object('drift_check_id', p_drift_check_id),
            jsonb_build_object('strategy_id', v_session.strategy_id),
            jsonb_build_object('reason', v_reason),
            jsonb_build_object('live_execution_allowed', false)
        ),
        NULL
    )
    RETURNING id INTO v_risk_event_id;

    IF p_drift_check_id IS NOT NULL THEN
        UPDATE strategy.drift_checks
        SET risk_event_id = coalesce(risk_event_id, v_risk_event_id)
        WHERE id = p_drift_check_id;
    END IF;

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
        'Kill switch review required: ' || coalesce(v_strategy.name, 'strategy ' || v_session.strategy_id::TEXT),
        'Execution Safety Agent',
        'needs_review',
        'critical',
        'Confirm paper monitor stopped, block any promotion, and require retest plus committee approval before reactivation.',
        jsonb_build_array(
            jsonb_build_object('paper_monitor_session_id', v_session.id),
            jsonb_build_object('drift_check_id', p_drift_check_id),
            jsonb_build_object('risk_event_id', v_risk_event_id),
            jsonb_build_object('live_execution_allowed', false)
        ),
        'risk'
    )
    RETURNING id INTO v_inbox_item_id;

    INSERT INTO strategy.kill_switch_events (
        event_key,
        paper_monitor_session_id,
        drift_check_id,
        strategy_id,
        instance_id,
        trigger_source,
        trigger_reason,
        enforcement_status,
        action_taken,
        enforced_by,
        risk_event_id,
        inbox_item_id,
        evidence,
        live_execution_allowed
    )
    VALUES (
        v_event_key,
        v_session.id,
        p_drift_check_id,
        v_session.strategy_id,
        v_session.instance_id,
        CASE WHEN p_drift_check_id IS NULL THEN 'manual' ELSE 'drift_monitor' END,
        v_reason,
        'enforced',
        v_action_taken,
        v_actor,
        v_risk_event_id,
        v_inbox_item_id,
        jsonb_build_array(
            jsonb_build_object('paper_monitor_session_id', v_session.id),
            jsonb_build_object('drift_check_id', p_drift_check_id),
            jsonb_build_object('stop_result', v_stop_result),
            jsonb_build_object('live_execution_allowed', false)
        ),
        false
    )
    ON CONFLICT (event_key) DO UPDATE
    SET enforcement_status = 'enforced',
        action_taken = EXCLUDED.action_taken,
        enforced_by = EXCLUDED.enforced_by,
        risk_event_id = EXCLUDED.risk_event_id,
        inbox_item_id = EXCLUDED.inbox_item_id,
        evidence = EXCLUDED.evidence,
        live_execution_allowed = false,
        enforced_at = now()
    RETURNING id INTO v_kill_event_id;

    RETURN jsonb_build_object(
        'kill_switch_event_id', v_kill_event_id,
        'paper_monitor_session_id', v_session.id,
        'drift_check_id', p_drift_check_id,
        'strategy_id', v_session.strategy_id,
        'instance_id', v_session.instance_id,
        'enforcement_status', 'enforced',
        'action_taken', v_action_taken,
        'risk_event_id', v_risk_event_id,
        'inbox_item_id', v_inbox_item_id,
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_kill_switch_events AS
SELECT
    kse.id,
    kse.event_key,
    kse.paper_monitor_session_id,
    pms.session_key,
    kse.drift_check_id,
    kse.strategy_id,
    sc.name AS strategy_name,
    kse.instance_id,
    si.instance_name,
    kse.trigger_source,
    kse.trigger_reason,
    kse.enforcement_status,
    kse.action_taken,
    kse.enforced_by,
    kse.risk_event_id,
    re.status AS risk_event_status,
    kse.inbox_item_id,
    kse.evidence,
    kse.live_execution_allowed,
    kse.enforced_at
FROM strategy.kill_switch_events kse
LEFT JOIN strategy.paper_monitor_sessions pms ON pms.id = kse.paper_monitor_session_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = kse.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = kse.instance_id
LEFT JOIN risk.events re ON re.id = kse.risk_event_id
ORDER BY kse.enforced_at DESC;

