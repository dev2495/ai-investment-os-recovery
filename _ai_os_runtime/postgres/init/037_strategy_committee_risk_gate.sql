CREATE TABLE IF NOT EXISTS strategy.committee_reviews (
    id BIGSERIAL PRIMARY KEY,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    backtest_run_id BIGINT REFERENCES strategy.backtest_runs(id) ON DELETE SET NULL,
    optimization_run_id BIGINT REFERENCES strategy.optimization_runs(id) ON DELETE SET NULL,
    validation_review_id BIGINT REFERENCES strategy.validation_reviews(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    review_key TEXT NOT NULL UNIQUE,
    review_status TEXT NOT NULL DEFAULT 'needs_review',
    recommended_decision TEXT NOT NULL DEFAULT 'retest',
    proposed_mode TEXT NOT NULL DEFAULT 'research',
    risk_level TEXT NOT NULL DEFAULT 'high',
    committee_members TEXT[] NOT NULL DEFAULT ARRAY['Charlie Munger','Risk Agent','Model Validation Agent','Portfolio Manager','Strategy Committee Secretary']::TEXT[],
    required_evidence TEXT[] NOT NULL DEFAULT ARRAY['baseline_backtest','optimizer','walk_forward','monte_carlo','model_validation','risk_limits']::TEXT[],
    kill_switch_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_notes TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Strategy Committee Secretary',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_committee_reviews_optimization
ON strategy.committee_reviews (optimization_run_id)
WHERE optimization_run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_committee_reviews_status ON strategy.committee_reviews (review_status);
CREATE INDEX IF NOT EXISTS idx_committee_reviews_strategy ON strategy.committee_reviews (strategy_id);

CREATE OR REPLACE FUNCTION strategy.open_strategy_committee_review(
    p_optimization_run_id BIGINT,
    p_actor TEXT DEFAULT 'Strategy Committee Secretary'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_opt strategy.optimization_runs%ROWTYPE;
    v_strategy strategy.strategy_candidates%ROWTYPE;
    v_validation_id BIGINT;
    v_existing_id BIGINT;
    v_approval_id BIGINT;
    v_review_id BIGINT;
    v_risk_event_id BIGINT;
    v_best_sharpe NUMERIC;
    v_consistency NUMERIC;
    v_heatmap_rows INT;
    v_recommended_decision TEXT;
    v_risk_level TEXT;
    v_review_key TEXT;
BEGIN
    SELECT * INTO v_opt
    FROM strategy.optimization_runs
    WHERE id = p_optimization_run_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'optimization_run_id % not found', p_optimization_run_id;
    END IF;

    SELECT * INTO v_strategy
    FROM strategy.strategy_candidates
    WHERE id = v_opt.strategy_id;

    SELECT id INTO v_existing_id
    FROM strategy.committee_reviews
    WHERE optimization_run_id = p_optimization_run_id
    LIMIT 1;

    IF v_existing_id IS NOT NULL THEN
        RETURN (
            SELECT jsonb_build_object(
                'committee_review_id', cr.id,
                'approval_id', cr.approval_id,
                'review_status', cr.review_status,
                'recommended_decision', cr.recommended_decision,
                'existing', true
            )
            FROM strategy.committee_reviews cr
            WHERE cr.id = v_existing_id
        );
    END IF;

    SELECT id INTO v_validation_id
    FROM strategy.validation_reviews
    WHERE optimization_run_id = p_optimization_run_id
    ORDER BY created_at DESC
    LIMIT 1;

    v_best_sharpe := NULLIF(v_opt.metrics->>'best_walk_forward_test_sharpe', '')::NUMERIC;
    v_consistency := NULLIF(v_opt.metrics->>'best_walk_forward_consistency', '')::NUMERIC;
    v_heatmap_rows := COALESCE(jsonb_array_length(COALESCE(v_opt.diagnostics->'heatmap_rows', '[]'::jsonb)), 0);

    IF COALESCE(v_best_sharpe, -999) <= 0 OR COALESCE(v_consistency, 0) < 0.5 THEN
        v_recommended_decision := 'reject_or_retest';
        v_risk_level := 'high';
    ELSE
        v_recommended_decision := 'paper_monitor_candidate';
        v_risk_level := 'medium';
    END IF;

    v_review_key := 'committee-review-opt-' || p_optimization_run_id::TEXT;

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
        'strategy_committee_review',
        'Strategy committee decision: ' || COALESCE(v_strategy.name, 'strategy ' || v_opt.strategy_id::TEXT),
        'Charlie Munger',
        v_risk_level,
        'pending',
        jsonb_build_object(
            'strategy_id', v_opt.strategy_id,
            'optimization_run_id', p_optimization_run_id,
            'recommended_decision', v_recommended_decision,
            'proposed_mode', CASE WHEN v_recommended_decision = 'paper_monitor_candidate' THEN 'paper' ELSE 'research' END,
            'live_execution_allowed', false,
            'human_decision_required', true
        ),
        'Committee must approve reject/retest/paper-monitor decision. Live execution remains disabled.'
    )
    RETURNING id INTO v_approval_id;

    INSERT INTO strategy.committee_reviews (
        strategy_id,
        backtest_run_id,
        optimization_run_id,
        validation_review_id,
        approval_id,
        review_key,
        review_status,
        recommended_decision,
        proposed_mode,
        risk_level,
        kill_switch_rules,
        risk_summary,
        decision_notes,
        created_by
    )
    VALUES (
        v_opt.strategy_id,
        v_opt.backtest_run_id,
        p_optimization_run_id,
        v_validation_id,
        v_approval_id,
        v_review_key,
        'needs_review',
        v_recommended_decision,
        CASE WHEN v_recommended_decision = 'paper_monitor_candidate' THEN 'paper' ELSE 'research' END,
        v_risk_level,
        jsonb_build_object(
            'daily_loss_limit_pct', 1.0,
            'max_drawdown_stop_pct', 3.0,
            'max_open_positions', 5,
            'disable_on_data_gap', true,
            'disable_on_model_validation_reject', true,
            'requires_manual_reenable', true
        ),
        jsonb_build_object(
            'best_walk_forward_test_sharpe', v_best_sharpe,
            'best_walk_forward_consistency', v_consistency,
            'heatmap_rows', v_heatmap_rows,
            'optimizer_status', v_opt.status,
            'warnings', COALESCE(v_opt.diagnostics->'warnings', '[]'::jsonb),
            'live_execution_allowed', false
        ),
        CASE
            WHEN v_recommended_decision = 'paper_monitor_candidate'
                THEN 'Eligible only for paper monitoring after human approval. Live execution remains blocked.'
            ELSE 'Recommended reject or retest. Evidence does not support paper monitoring.'
        END,
        COALESCE(NULLIF(trim(p_actor), ''), 'Strategy Committee Secretary')
    )
    RETURNING id INTO v_review_id;

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
        'strategy',
        COALESCE(v_strategy.name, v_opt.strategy_id::TEXT),
        v_risk_level,
        'open',
        'Strategy committee gate opened',
        'Strategy cannot move beyond research without committee decision and explicit human approval.',
        jsonb_build_array(
            jsonb_build_object('strategy_id', v_opt.strategy_id),
            jsonb_build_object('optimization_run_id', p_optimization_run_id),
            jsonb_build_object('committee_review_id', v_review_id)
        ),
        v_approval_id
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
        'Committee review required: ' || COALESCE(v_strategy.name, 'strategy ' || v_opt.strategy_id::TEXT),
        'Strategy Committee Secretary',
        'needs_review',
        'critical',
        'Prepare committee memo. Decide reject, retest, or paper-monitor. Live execution remains disabled.',
        jsonb_build_array(
            jsonb_build_object('committee_review_id', v_review_id),
            jsonb_build_object('approval_id', v_approval_id),
            jsonb_build_object('risk_event_id', v_risk_event_id)
        ),
        'quant'
    );

    RETURN jsonb_build_object(
        'committee_review_id', v_review_id,
        'approval_id', v_approval_id,
        'risk_event_id', v_risk_event_id,
        'review_status', 'needs_review',
        'recommended_decision', v_recommended_decision,
        'risk_level', v_risk_level,
        'existing', false
    );
END;
$$;

CREATE OR REPLACE VIEW strategy.v_strategy_committee_queue AS
SELECT
    cr.id,
    cr.review_key,
    cr.strategy_id,
    sc.name AS strategy_name,
    cr.backtest_run_id,
    cr.optimization_run_id,
    cr.validation_review_id,
    cr.approval_id,
    cr.review_status,
    cr.recommended_decision,
    cr.proposed_mode,
    cr.risk_level,
    cr.committee_members,
    cr.required_evidence,
    cr.kill_switch_rules,
    cr.risk_summary,
    cr.decision_notes,
    ap.status AS approval_status,
    ap.decided_by,
    ap.decided_at,
    cr.created_by,
    cr.created_at,
    cr.updated_at
FROM strategy.committee_reviews cr
LEFT JOIN strategy.strategy_candidates sc ON sc.id = cr.strategy_id
LEFT JOIN agent.approvals ap ON ap.id = cr.approval_id
ORDER BY
    CASE cr.risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    cr.created_at DESC;
