CREATE TABLE IF NOT EXISTS strategy.drift_checks (
    id BIGSERIAL PRIMARY KEY,
    paper_monitor_session_id BIGINT NOT NULL REFERENCES strategy.paper_monitor_sessions(id) ON DELETE CASCADE,
    strategy_id BIGINT NOT NULL REFERENCES strategy.strategy_candidates(id) ON DELETE CASCADE,
    instance_id BIGINT REFERENCES strategy.strategy_instances(id) ON DELETE SET NULL,
    baseline_backtest_run_id BIGINT REFERENCES strategy.backtest_runs(id) ON DELETE SET NULL,
    baseline_optimization_run_id BIGINT REFERENCES strategy.optimization_runs(id) ON DELETE SET NULL,
    check_status TEXT NOT NULL DEFAULT 'pending',
    drift_level TEXT NOT NULL DEFAULT 'unknown',
    drift_score NUMERIC,
    baseline_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    paper_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    findings TEXT[] NOT NULL DEFAULT '{}',
    risk_event_id BIGINT REFERENCES risk.events(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    checked_by TEXT NOT NULL DEFAULT 'Model Validation Agent',
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_strategy_drift_live_disabled CHECK (live_execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_drift_checks_session ON strategy.drift_checks (paper_monitor_session_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_checks_strategy ON strategy.drift_checks (strategy_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_checks_level ON strategy.drift_checks (drift_level);

CREATE OR REPLACE FUNCTION strategy.evaluate_paper_backtest_drift(
    p_paper_monitor_session_id BIGINT,
    p_actor TEXT DEFAULT 'Model Validation Agent',
    p_thresholds JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_session strategy.paper_monitor_sessions%ROWTYPE;
    v_strategy strategy.strategy_candidates%ROWTYPE;
    v_backtest strategy.backtest_runs%ROWTYPE;
    v_opt strategy.optimization_runs%ROWTYPE;
    v_perf strategy.performance_snapshots%ROWTYPE;
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Model Validation Agent');
    v_thresholds JSONB := coalesce(p_thresholds, '{}'::jsonb);
    v_min_heartbeats INT := coalesce(NULLIF(v_thresholds->>'min_heartbeats', '')::INT, 1);
    v_sharpe_warn_delta NUMERIC := coalesce(NULLIF(v_thresholds->>'sharpe_warn_delta', '')::NUMERIC, -1.0);
    v_return_warn_delta NUMERIC := coalesce(NULLIF(v_thresholds->>'return_warn_delta', '')::NUMERIC, -0.03);
    v_max_stale_minutes INT;
    v_kill_drawdown_pct NUMERIC;
    v_baseline_sharpe NUMERIC;
    v_baseline_return NUMERIC;
    v_baseline_drawdown NUMERIC;
    v_paper_sharpe NUMERIC;
    v_paper_return NUMERIC;
    v_paper_pnl NUMERIC;
    v_paper_drawdown NUMERIC;
    v_heartbeat_events INT := 0;
    v_is_stale BOOLEAN := false;
    v_findings TEXT[] := ARRAY[]::TEXT[];
    v_drift_level TEXT := 'ok';
    v_check_status TEXT := 'completed';
    v_drift_score NUMERIC := 0;
    v_baseline_metrics JSONB;
    v_paper_metrics JSONB;
    v_risk_event_id BIGINT;
    v_inbox_item_id BIGINT;
BEGIN
    SELECT * INTO v_session
    FROM strategy.paper_monitor_sessions
    WHERE id = p_paper_monitor_session_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'paper_monitor_session_id % not found', p_paper_monitor_session_id;
    END IF;

    IF v_session.live_execution_allowed IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'drift check blocked because live execution flag is not false';
    END IF;

    SELECT * INTO v_strategy
    FROM strategy.strategy_candidates
    WHERE id = v_session.strategy_id;

    SELECT * INTO v_opt
    FROM strategy.optimization_runs
    WHERE strategy_id = v_session.strategy_id
    ORDER BY finished_at DESC NULLS LAST, started_at DESC, id DESC
    LIMIT 1;

    SELECT * INTO v_backtest
    FROM strategy.backtest_runs
    WHERE strategy_id = v_session.strategy_id
    ORDER BY finished_at DESC NULLS LAST, started_at DESC, id DESC
    LIMIT 1;

    SELECT * INTO v_perf
    FROM strategy.performance_snapshots
    WHERE instance_id = v_session.instance_id
    ORDER BY ts DESC
    LIMIT 1;

    SELECT count(*)::INT INTO v_heartbeat_events
    FROM strategy.paper_monitor_events
    WHERE session_id = v_session.id
      AND event_type = 'heartbeat';

    v_max_stale_minutes := coalesce(NULLIF(v_thresholds->>'max_stale_minutes', '')::INT, v_session.max_stale_minutes, 30);
    v_is_stale := v_session.status = 'running'
        AND v_session.last_heartbeat_at IS NOT NULL
        AND v_session.last_heartbeat_at < now() - make_interval(mins => v_max_stale_minutes);

    v_baseline_sharpe := coalesce(
        NULLIF(v_opt.metrics->>'best_walk_forward_test_sharpe', '')::NUMERIC,
        NULLIF(v_opt.metrics->>'best_test_sharpe', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'sharpe', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'sharpe_estimate', '')::NUMERIC
    );
    v_baseline_return := coalesce(
        NULLIF(v_opt.metrics->>'best_walk_forward_test_return', '')::NUMERIC,
        NULLIF(v_opt.metrics->>'best_test_total_return', '')::NUMERIC,
        NULLIF(v_opt.metrics->>'best_total_return', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'total_return', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'cagr_pct', '')::NUMERIC / 100.0
    );
    v_baseline_drawdown := coalesce(
        NULLIF(v_opt.metrics->>'best_max_drawdown', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'max_drawdown', '')::NUMERIC,
        NULLIF(v_backtest.metrics->>'max_dd_pct', '')::NUMERIC / 100.0
    );

    v_paper_sharpe := coalesce(
        NULLIF(v_perf.sharpe::TEXT, '')::NUMERIC,
        NULLIF(v_session.metrics->>'sharpe', '')::NUMERIC
    );
    v_paper_return := coalesce(
        NULLIF(v_perf.metrics->>'total_return', '')::NUMERIC,
        NULLIF(v_session.metrics->>'total_return', '')::NUMERIC
    );
    v_paper_pnl := coalesce(
        NULLIF(v_perf.pnl::TEXT, '')::NUMERIC,
        NULLIF(v_session.metrics->>'pnl', '')::NUMERIC
    );
    v_paper_drawdown := coalesce(
        NULLIF(v_perf.max_drawdown::TEXT, '')::NUMERIC,
        NULLIF(v_session.metrics->>'max_drawdown', '')::NUMERIC
    );

    v_kill_drawdown_pct := NULLIF(v_session.kill_switch_rules->>'max_drawdown_stop_pct', '')::NUMERIC;

    IF v_heartbeat_events < v_min_heartbeats THEN
        v_drift_level := 'insufficient_data';
        v_check_status := 'needs_more_paper_history';
        v_findings := array_append(v_findings, 'Not enough paper heartbeat events for drift judgement.');
    END IF;

    IF v_baseline_sharpe IS NULL AND v_baseline_return IS NULL AND v_baseline_drawdown IS NULL THEN
        v_drift_level := 'insufficient_data';
        v_check_status := 'missing_baseline';
        v_findings := array_append(v_findings, 'No usable backtest or optimization baseline metrics found.');
    END IF;

    IF v_is_stale THEN
        v_drift_level := CASE WHEN v_drift_level = 'ok' THEN 'warning' ELSE v_drift_level END;
        v_findings := array_append(v_findings, 'Paper monitor heartbeat is stale.');
        v_drift_score := v_drift_score + 1;
    END IF;

    IF v_paper_sharpe IS NOT NULL AND v_baseline_sharpe IS NOT NULL AND (v_paper_sharpe - v_baseline_sharpe) < v_sharpe_warn_delta THEN
        v_drift_level := 'warning';
        v_findings := array_append(v_findings, 'Paper Sharpe is materially below baseline.');
        v_drift_score := v_drift_score + abs(v_paper_sharpe - v_baseline_sharpe);
    END IF;

    IF v_paper_return IS NOT NULL AND v_baseline_return IS NOT NULL AND (v_paper_return - v_baseline_return) < v_return_warn_delta THEN
        v_drift_level := 'warning';
        v_findings := array_append(v_findings, 'Paper return is materially below baseline.');
        v_drift_score := v_drift_score + abs(v_paper_return - v_baseline_return) * 10;
    END IF;

    IF v_paper_drawdown IS NOT NULL AND v_kill_drawdown_pct IS NOT NULL AND v_paper_drawdown <= -(abs(v_kill_drawdown_pct) / 100.0) THEN
        v_drift_level := 'breach';
        v_findings := array_append(v_findings, 'Paper drawdown breached committee kill-switch threshold.');
        v_drift_score := v_drift_score + 10;
    ELSIF v_paper_drawdown IS NOT NULL AND v_baseline_drawdown IS NOT NULL AND v_paper_drawdown < (v_baseline_drawdown * 1.25) THEN
        v_drift_level := CASE WHEN v_drift_level = 'breach' THEN 'breach' ELSE 'warning' END;
        v_findings := array_append(v_findings, 'Paper drawdown is worse than baseline drawdown tolerance.');
        v_drift_score := v_drift_score + abs(v_paper_drawdown - v_baseline_drawdown) * 10;
    END IF;

    IF v_paper_sharpe IS NULL AND v_paper_return IS NULL AND v_paper_drawdown IS NULL AND v_drift_level = 'ok' THEN
        v_drift_level := 'insufficient_data';
        v_check_status := 'missing_paper_metrics';
        v_findings := array_append(v_findings, 'No paper performance metrics available yet.');
    END IF;

    IF array_length(v_findings, 1) IS NULL THEN
        v_findings := ARRAY['Paper monitor remains within available baseline tolerance.']::TEXT[];
    END IF;

    v_baseline_metrics := jsonb_build_object(
        'backtest_run_id', v_backtest.id,
        'optimization_run_id', v_opt.id,
        'sharpe', v_baseline_sharpe,
        'total_return', v_baseline_return,
        'max_drawdown', v_baseline_drawdown
    );
    v_paper_metrics := jsonb_build_object(
        'sharpe', v_paper_sharpe,
        'total_return', v_paper_return,
        'pnl', v_paper_pnl,
        'max_drawdown', v_paper_drawdown,
        'heartbeat_events', v_heartbeat_events,
        'is_stale', v_is_stale
    );

    IF v_drift_level IN ('warning', 'breach') THEN
        SELECT id INTO v_risk_event_id
        FROM risk.events
        WHERE scope_type = 'strategy_paper_monitor'
          AND scope_ref = v_session.session_key
          AND status IN ('new', 'open', 'monitor')
        ORDER BY ts DESC
        LIMIT 1;

        IF v_risk_event_id IS NULL THEN
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
                'strategy_paper_monitor',
                v_session.session_key,
                CASE WHEN v_drift_level = 'breach' THEN 'critical' ELSE 'high' END,
                'open',
                'Paper/backtest drift: ' || coalesce(v_strategy.name, 'strategy ' || v_session.strategy_id::TEXT),
                'Paper monitor drift requires Model Validation and Risk review. Live execution remains disabled.',
                jsonb_build_array(
                    jsonb_build_object('paper_monitor_session_id', v_session.id),
                    jsonb_build_object('strategy_id', v_session.strategy_id),
                    jsonb_build_object('drift_level', v_drift_level),
                    jsonb_build_object('live_execution_allowed', false)
                ),
                NULL
            )
            RETURNING id INTO v_risk_event_id;
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
            'Review paper/backtest drift: ' || coalesce(v_strategy.name, 'strategy ' || v_session.strategy_id::TEXT),
            CASE WHEN v_drift_level = 'breach' THEN 'Risk Agent' ELSE 'Model Validation Agent' END,
            'needs_review',
            CASE WHEN v_drift_level = 'breach' THEN 'critical' ELSE 'high' END,
            'Review paper performance against baseline and decide whether to stop, retest, or continue paper monitoring. Live execution remains disabled.',
            jsonb_build_array(
                jsonb_build_object('paper_monitor_session_id', v_session.id),
                jsonb_build_object('risk_event_id', v_risk_event_id),
                jsonb_build_object('findings', v_findings),
                jsonb_build_object('live_execution_allowed', false)
            ),
            'quant'
        )
        RETURNING id INTO v_inbox_item_id;
    END IF;

    INSERT INTO strategy.drift_checks (
        paper_monitor_session_id,
        strategy_id,
        instance_id,
        baseline_backtest_run_id,
        baseline_optimization_run_id,
        check_status,
        drift_level,
        drift_score,
        baseline_metrics,
        paper_metrics,
        thresholds,
        findings,
        risk_event_id,
        inbox_item_id,
        live_execution_allowed,
        checked_by
    )
    VALUES (
        v_session.id,
        v_session.strategy_id,
        v_session.instance_id,
        v_backtest.id,
        v_opt.id,
        v_check_status,
        v_drift_level,
        v_drift_score,
        v_baseline_metrics,
        v_paper_metrics,
        jsonb_build_object(
            'min_heartbeats', v_min_heartbeats,
            'sharpe_warn_delta', v_sharpe_warn_delta,
            'return_warn_delta', v_return_warn_delta,
            'max_stale_minutes', v_max_stale_minutes,
            'kill_drawdown_pct', v_kill_drawdown_pct
        ),
        v_findings,
        v_risk_event_id,
        v_inbox_item_id,
        false,
        v_actor
    );

    RETURN jsonb_build_object(
        'paper_monitor_session_id', v_session.id,
        'strategy_id', v_session.strategy_id,
        'drift_level', v_drift_level,
        'check_status', v_check_status,
        'drift_score', v_drift_score,
        'findings', v_findings,
        'risk_event_id', v_risk_event_id,
        'inbox_item_id', v_inbox_item_id,
        'baseline_metrics', v_baseline_metrics,
        'paper_metrics', v_paper_metrics,
        'live_execution_allowed', false
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_drift_monitor_checks AS
SELECT
    dc.id,
    dc.paper_monitor_session_id,
    pms.session_key,
    dc.strategy_id,
    sc.name AS strategy_name,
    dc.instance_id,
    si.instance_name,
    dc.baseline_backtest_run_id,
    dc.baseline_optimization_run_id,
    dc.check_status,
    dc.drift_level,
    dc.drift_score,
    dc.baseline_metrics,
    dc.paper_metrics,
    dc.thresholds,
    dc.findings,
    dc.risk_event_id,
    re.status AS risk_event_status,
    dc.inbox_item_id,
    dc.live_execution_allowed,
    dc.checked_by,
    dc.checked_at
FROM strategy.drift_checks dc
LEFT JOIN strategy.paper_monitor_sessions pms ON pms.id = dc.paper_monitor_session_id
LEFT JOIN strategy.strategy_candidates sc ON sc.id = dc.strategy_id
LEFT JOIN strategy.strategy_instances si ON si.id = dc.instance_id
LEFT JOIN risk.events re ON re.id = dc.risk_event_id
ORDER BY dc.checked_at DESC;

