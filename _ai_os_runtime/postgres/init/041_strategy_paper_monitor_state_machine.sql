CREATE TABLE IF NOT EXISTS strategy.paper_monitor_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key TEXT NOT NULL UNIQUE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    instance_id BIGINT NOT NULL REFERENCES strategy.strategy_instances(id) ON DELETE CASCADE,
    committee_review_id BIGINT REFERENCES strategy.committee_reviews(id) ON DELETE SET NULL,
    committee_decision_id BIGINT REFERENCES strategy.committee_decisions(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    monitor_mode TEXT NOT NULL DEFAULT 'paper',
    owner_agent TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    started_by TEXT,
    stopped_by TEXT,
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    heartbeat_status TEXT NOT NULL DEFAULT 'not_started',
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    max_stale_minutes INTEGER NOT NULL DEFAULT 30,
    kill_switch_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_paper_monitor_mode CHECK (monitor_mode = 'paper'),
    CONSTRAINT chk_paper_monitor_live_disabled CHECK (live_execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_paper_monitor_sessions_strategy ON strategy.paper_monitor_sessions (strategy_id);
CREATE INDEX IF NOT EXISTS idx_paper_monitor_sessions_status ON strategy.paper_monitor_sessions (status);
CREATE INDEX IF NOT EXISTS idx_paper_monitor_sessions_heartbeat ON strategy.paper_monitor_sessions (last_heartbeat_at DESC);

CREATE TABLE IF NOT EXISTS strategy.paper_monitor_events (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES strategy.paper_monitor_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL DEFAULT 'recorded',
    symbol TEXT,
    timeframe TEXT,
    signal_count INTEGER,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Trading Desk Agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_paper_monitor_events_session ON strategy.paper_monitor_events (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_paper_monitor_events_type ON strategy.paper_monitor_events (event_type);

CREATE OR REPLACE FUNCTION strategy.start_paper_monitor(
    p_committee_review_id BIGINT,
    p_actor TEXT DEFAULT 'Trading Desk Agent',
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_review strategy.committee_reviews%ROWTYPE;
    v_decision strategy.committee_decisions%ROWTYPE;
    v_instance strategy.strategy_instances%ROWTYPE;
    v_session_id BIGINT;
    v_session_key TEXT;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Trading Desk Agent');
    v_notes TEXT := nullif(trim(coalesce(p_notes, '')), '');
BEGIN
    SELECT * INTO v_review
    FROM strategy.committee_reviews
    WHERE id = p_committee_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'committee_review_id % not found', p_committee_review_id;
    END IF;

    IF v_review.decision_status <> 'final'
       OR v_review.final_decision <> 'approve_paper_monitor'
       OR v_review.paper_monitor_allowed IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'paper monitor cannot start until committee final_decision is approve_paper_monitor';
    END IF;

    IF v_review.live_execution_allowed IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'paper monitor requires live_execution_allowed=false';
    END IF;

    SELECT * INTO v_decision
    FROM strategy.committee_decisions
    WHERE committee_review_id = v_review.id
      AND decision = 'approve_paper_monitor'
    ORDER BY created_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper monitor committee decision row not found for review %', v_review.id;
    END IF;

    SELECT * INTO v_instance
    FROM strategy.strategy_instances
    WHERE strategy_id = v_review.strategy_id
      AND mode = 'paper'
      AND config->>'committee_review_id' = v_review.id::TEXT
    ORDER BY id DESC
    LIMIT 1
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper strategy instance not found for committee_review_id %', v_review.id;
    END IF;

    IF coalesce((v_instance.config->>'live_execution_allowed')::BOOLEAN, false) IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'paper strategy instance has live execution enabled; blocked';
    END IF;

    v_session_key := 'paper-monitor-review-' || v_review.id::TEXT || '-strategy-' || v_review.strategy_id::TEXT;

    INSERT INTO strategy.paper_monitor_sessions (
        session_key,
        strategy_id,
        instance_id,
        committee_review_id,
        committee_decision_id,
        status,
        monitor_mode,
        owner_agent,
        started_by,
        started_at,
        last_heartbeat_at,
        heartbeat_status,
        live_execution_allowed,
        kill_switch_rules,
        metrics,
        notes
    )
    VALUES (
        v_session_key,
        v_review.strategy_id,
        v_instance.id,
        v_review.id,
        v_decision.id,
        'running',
        'paper',
        'Trading Desk Agent',
        v_actor,
        now(),
        now(),
        'ok',
        false,
        v_review.kill_switch_rules,
        jsonb_build_object('signals_seen', 0, 'paper_trades_recorded', 0, 'live_execution_allowed', false),
        coalesce(v_notes, 'Paper monitor started from approved committee decision. Live execution remains disabled.')
    )
    ON CONFLICT (session_key) DO UPDATE
    SET status = 'running',
        started_by = EXCLUDED.started_by,
        started_at = coalesce(strategy.paper_monitor_sessions.started_at, now()),
        last_heartbeat_at = now(),
        heartbeat_status = 'ok',
        live_execution_allowed = false,
        kill_switch_rules = EXCLUDED.kill_switch_rules,
        notes = EXCLUDED.notes,
        updated_at = now()
    RETURNING id INTO v_session_id;

    UPDATE strategy.strategy_instances
    SET status = 'running',
        started_at = coalesce(started_at, now()),
        stopped_at = NULL,
        last_heartbeat_at = now(),
        config = config || jsonb_build_object(
            'paper_monitor_session_id', v_session_id,
            'paper_monitor_status', 'running',
            'live_execution_allowed', false,
            'requires_separate_live_approval', true
        ),
        notes = 'Paper monitor running. Live execution remains disabled.'
    WHERE id = v_instance.id;

    UPDATE strategy.strategy_candidates
    SET status = 'paper',
        activation_gate = 'paper_monitor_running',
        updated_at = now()
    WHERE id = v_review.strategy_id;

    INSERT INTO strategy.paper_monitor_events (
        session_id,
        event_type,
        event_status,
        metrics,
        payload,
        created_by
    )
    VALUES (
        v_session_id,
        'started',
        'recorded',
        jsonb_build_object('live_execution_allowed', false),
        jsonb_build_object('committee_review_id', v_review.id, 'strategy_id', v_review.strategy_id, 'instance_id', v_instance.id),
        v_actor
    );

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
        'Paper monitor started: strategy ' || v_review.strategy_id::TEXT,
        'Trading Desk Agent',
        'needs_review',
        'high',
        'Monitor paper signals and record heartbeats. Do not place live orders.',
        jsonb_build_array(
            jsonb_build_object('paper_monitor_session_id', v_session_id),
            jsonb_build_object('committee_review_id', v_review.id),
            jsonb_build_object('live_execution_allowed', false)
        ),
        'trading'
    );

    RETURN jsonb_build_object(
        'paper_monitor_session_id', v_session_id,
        'strategy_id', v_review.strategy_id,
        'instance_id', v_instance.id,
        'committee_review_id', v_review.id,
        'status', 'running',
        'heartbeat_status', 'ok',
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION strategy.record_paper_monitor_heartbeat(
    p_session_id BIGINT,
    p_actor TEXT DEFAULT 'Trading Desk Agent',
    p_heartbeat_status TEXT DEFAULT 'ok',
    p_signal_count INTEGER DEFAULT 0,
    p_metrics JSONB DEFAULT '{}'::jsonb,
    p_payload JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_session strategy.paper_monitor_sessions%ROWTYPE;
    v_status TEXT := lower(trim(coalesce(p_heartbeat_status, 'ok')));
    v_signal_count INTEGER := greatest(coalesce(p_signal_count, 0), 0);
    v_metrics JSONB := coalesce(p_metrics, '{}'::jsonb);
    v_payload JSONB := coalesce(p_payload, '{}'::jsonb);
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Trading Desk Agent');
    v_event_id BIGINT;
BEGIN
    IF v_status NOT IN ('ok', 'warning', 'stale', 'error', 'stopped') THEN
        RAISE EXCEPTION 'heartbeat_status must be ok, warning, stale, error, or stopped';
    END IF;

    SELECT * INTO v_session
    FROM strategy.paper_monitor_sessions
    WHERE id = p_session_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper_monitor_session_id % not found', p_session_id;
    END IF;

    IF v_session.live_execution_allowed IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'paper monitor heartbeat blocked because live execution is not false';
    END IF;

    IF v_session.status NOT IN ('running', 'ready') THEN
        RAISE EXCEPTION 'paper monitor session % is not running or ready', p_session_id;
    END IF;

    INSERT INTO strategy.paper_monitor_events (
        session_id,
        event_type,
        event_status,
        symbol,
        timeframe,
        signal_count,
        metrics,
        payload,
        created_by
    )
    VALUES (
        v_session.id,
        'heartbeat',
        v_status,
        nullif(v_payload->>'symbol', ''),
        nullif(v_payload->>'timeframe', ''),
        v_signal_count,
        v_metrics,
        v_payload || jsonb_build_object('live_execution_allowed', false),
        v_actor
    )
    RETURNING id INTO v_event_id;

    UPDATE strategy.paper_monitor_sessions
    SET status = CASE WHEN v_status = 'stopped' THEN 'stopped' ELSE 'running' END,
        last_heartbeat_at = now(),
        heartbeat_status = v_status,
        metrics = metrics || v_metrics || jsonb_build_object(
            'last_signal_count', v_signal_count,
            'last_event_id', v_event_id,
            'live_execution_allowed', false
        ),
        updated_at = now()
    WHERE id = v_session.id;

    UPDATE strategy.strategy_instances
    SET last_heartbeat_at = now(),
        status = CASE WHEN v_status = 'stopped' THEN 'stopped' ELSE 'running' END,
        config = config || jsonb_build_object('last_paper_monitor_event_id', v_event_id, 'live_execution_allowed', false)
    WHERE id = v_session.instance_id;

    INSERT INTO strategy.performance_snapshots (
        ts,
        instance_id,
        trades_count,
        win_rate,
        expectancy,
        pnl,
        max_drawdown,
        sharpe,
        exposure,
        metrics
    )
    VALUES (
        now(),
        v_session.instance_id,
        NULLIF(v_metrics->>'trades_count', '')::INTEGER,
        NULLIF(v_metrics->>'win_rate', '')::NUMERIC,
        NULLIF(v_metrics->>'expectancy', '')::NUMERIC,
        NULLIF(v_metrics->>'pnl', '')::NUMERIC,
        NULLIF(v_metrics->>'max_drawdown', '')::NUMERIC,
        NULLIF(v_metrics->>'sharpe', '')::NUMERIC,
        NULLIF(v_metrics->>'exposure', '')::NUMERIC,
        v_metrics || jsonb_build_object('paper_monitor_session_id', v_session.id, 'live_execution_allowed', false)
    )
    ON CONFLICT (ts, instance_id) DO NOTHING;

    RETURN jsonb_build_object(
        'paper_monitor_session_id', v_session.id,
        'paper_monitor_event_id', v_event_id,
        'strategy_id', v_session.strategy_id,
        'instance_id', v_session.instance_id,
        'heartbeat_status', v_status,
        'signal_count', v_signal_count,
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE FUNCTION strategy.stop_paper_monitor(
    p_session_id BIGINT,
    p_actor TEXT DEFAULT 'Trading Desk Agent',
    p_reason TEXT DEFAULT 'manual_stop'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_session strategy.paper_monitor_sessions%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Trading Desk Agent');
    v_reason TEXT := coalesce(nullif(trim(coalesce(p_reason, '')), ''), 'manual_stop');
    v_event_id BIGINT;
BEGIN
    SELECT * INTO v_session
    FROM strategy.paper_monitor_sessions
    WHERE id = p_session_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper_monitor_session_id % not found', p_session_id;
    END IF;

    UPDATE strategy.paper_monitor_sessions
    SET status = 'stopped',
        stopped_by = v_actor,
        stopped_at = now(),
        heartbeat_status = 'stopped',
        live_execution_allowed = false,
        notes = coalesce(notes, '') || ' Stop reason: ' || v_reason,
        updated_at = now()
    WHERE id = v_session.id;

    UPDATE strategy.strategy_instances
    SET status = 'stopped',
        stopped_at = now(),
        config = config || jsonb_build_object('paper_monitor_status', 'stopped', 'live_execution_allowed', false)
    WHERE id = v_session.instance_id;

    INSERT INTO strategy.paper_monitor_events (
        session_id,
        event_type,
        event_status,
        payload,
        created_by
    )
    VALUES (
        v_session.id,
        'stopped',
        'recorded',
        jsonb_build_object('reason', v_reason, 'live_execution_allowed', false),
        v_actor
    )
    RETURNING id INTO v_event_id;

    RETURN jsonb_build_object(
        'paper_monitor_session_id', v_session.id,
        'paper_monitor_event_id', v_event_id,
        'strategy_id', v_session.strategy_id,
        'instance_id', v_session.instance_id,
        'status', 'stopped',
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_paper_monitor_sessions AS
SELECT
    pms.id,
    pms.session_key,
    pms.strategy_id,
    sc.name AS strategy_name,
    sc.candidate_key,
    pms.instance_id,
    si.instance_name,
    pms.committee_review_id,
    pms.committee_decision_id,
    pms.status,
    pms.monitor_mode,
    pms.owner_agent,
    pms.started_by,
    pms.stopped_by,
    pms.started_at,
    pms.stopped_at,
    pms.last_heartbeat_at,
    pms.heartbeat_status,
    CASE
        WHEN pms.status = 'running' AND pms.last_heartbeat_at < now() - make_interval(mins => pms.max_stale_minutes) THEN true
        ELSE false
    END AS is_stale,
    pms.live_execution_allowed,
    pms.max_stale_minutes,
    pms.kill_switch_rules,
    pms.metrics,
    latest_event.id AS latest_event_id,
    latest_event.event_type AS latest_event_type,
    latest_event.event_status AS latest_event_status,
    latest_event.created_at AS latest_event_at,
    event_counts.total_events,
    event_counts.heartbeat_events,
    pms.notes,
    pms.created_at,
    pms.updated_at
FROM strategy.paper_monitor_sessions pms
LEFT JOIN strategy.strategy_candidates sc ON sc.id = pms.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = pms.instance_id
LEFT JOIN LATERAL (
    SELECT pme.id, pme.event_type, pme.event_status, pme.created_at
    FROM strategy.paper_monitor_events pme
    WHERE pme.session_id = pms.id
    ORDER BY pme.created_at DESC
    LIMIT 1
) latest_event ON true
LEFT JOIN LATERAL (
    SELECT
        count(*)::INT AS total_events,
        count(*) FILTER (WHERE event_type = 'heartbeat')::INT AS heartbeat_events
    FROM strategy.paper_monitor_events pme
    WHERE pme.session_id = pms.id
) event_counts ON true
ORDER BY
    CASE pms.status WHEN 'running' THEN 1 WHEN 'ready' THEN 2 WHEN 'paused' THEN 3 WHEN 'stopped' THEN 4 ELSE 5 END,
    pms.updated_at DESC;

CREATE OR REPLACE VIEW strategy.v_paper_monitor_events AS
SELECT
    pme.id,
    pme.session_id,
    pms.session_key,
    pms.strategy_id,
    sc.name AS strategy_name,
    pme.event_type,
    pme.event_status,
    pme.symbol,
    pme.timeframe,
    pme.signal_count,
    pme.metrics,
    pme.payload,
    pme.created_by,
    pme.created_at
FROM strategy.paper_monitor_events pme
JOIN strategy.paper_monitor_sessions pms ON pms.id = pme.session_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = pms.strategy_id
ORDER BY pme.created_at DESC;

