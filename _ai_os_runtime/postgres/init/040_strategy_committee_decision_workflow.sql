ALTER TABLE strategy.committee_reviews
    ADD COLUMN IF NOT EXISTS final_decision TEXT,
    ADD COLUMN IF NOT EXISTS decision_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS paper_monitor_allowed BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS decision_payload JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS strategy.committee_decisions (
    id BIGSERIAL PRIMARY KEY,
    committee_review_id BIGINT NOT NULL REFERENCES strategy.committee_reviews(id) ON DELETE CASCADE,
    strategy_id BIGINT REFERENCES strategy.strategy_candidates(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'final',
    decision_notes TEXT,
    paper_monitor_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    decided_by TEXT NOT NULL DEFAULT 'Devarsh',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_committee_decisions_review ON strategy.committee_decisions (committee_review_id);
CREATE INDEX IF NOT EXISTS idx_committee_decisions_strategy ON strategy.committee_decisions (strategy_id);
CREATE INDEX IF NOT EXISTS idx_committee_decisions_decision ON strategy.committee_decisions (decision);

CREATE OR REPLACE FUNCTION strategy.resolve_strategy_committee_decision(
    p_committee_review_id BIGINT,
    p_decision TEXT,
    p_actor TEXT DEFAULT 'Devarsh',
    p_decision_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_review strategy.committee_reviews%ROWTYPE;
    v_strategy strategy.strategy_candidates%ROWTYPE;
    v_decision TEXT := lower(trim(coalesce(p_decision, '')));
    v_actor TEXT := coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Devarsh');
    v_notes TEXT := nullif(trim(coalesce(p_decision_notes, '')), '');
    v_decision_id BIGINT;
    v_instance_id BIGINT;
    v_inbox_owner TEXT;
    v_inbox_action TEXT;
    v_review_status TEXT;
    v_candidate_status TEXT;
    v_validation_status TEXT;
    v_activation_gate TEXT;
    v_approval_status TEXT;
    v_risk_status TEXT;
    v_paper_allowed BOOLEAN := false;
BEGIN
    IF v_decision NOT IN ('reject', 'retest', 'research_more', 'approve_paper_monitor') THEN
        RAISE EXCEPTION 'decision must be reject, retest, research_more, or approve_paper_monitor';
    END IF;

    SELECT * INTO v_review
    FROM strategy.committee_reviews
    WHERE id = p_committee_review_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'committee_review_id % not found', p_committee_review_id;
    END IF;

    IF v_review.decision_status = 'final' THEN
        RAISE EXCEPTION 'committee_review_id % already has final decision %', p_committee_review_id, v_review.final_decision;
    END IF;

    IF coalesce(v_review.memo_status, 'not_generated') <> 'generated' THEN
        RAISE EXCEPTION 'committee memo must be generated before a final decision';
    END IF;

    SELECT * INTO v_strategy
    FROM strategy.strategy_candidates
    WHERE id = v_review.strategy_id
    FOR UPDATE;

    IF v_decision = 'approve_paper_monitor' AND v_review.recommended_decision <> 'paper_monitor_candidate' THEN
        RAISE EXCEPTION 'paper monitor approval is blocked because recommended_decision is %', v_review.recommended_decision;
    END IF;

    IF v_decision = 'reject' THEN
        v_review_status := 'rejected';
        v_candidate_status := 'rejected';
        v_validation_status := 'committee_rejected';
        v_activation_gate := 'blocked_by_committee';
        v_approval_status := 'rejected';
        v_risk_status := 'closed';
        v_inbox_owner := 'Strategy Generator';
        v_inbox_action := 'Archive or rewrite this strategy. Committee rejected the current evidence package.';
    ELSIF v_decision = 'retest' THEN
        v_review_status := 'retest_required';
        v_candidate_status := 'research';
        v_validation_status := 'committee_retest_required';
        v_activation_gate := 'committee_retest_required';
        v_approval_status := 'rejected';
        v_risk_status := 'open';
        v_inbox_owner := 'Backtest Engineer';
        v_inbox_action := 'Rerun the strategy with revised rules, stronger data checks, and fresh validation. No paper or live activation.';
    ELSIF v_decision = 'research_more' THEN
        v_review_status := 'research_required';
        v_candidate_status := 'research';
        v_validation_status := 'committee_research_required';
        v_activation_gate := 'committee_research_required';
        v_approval_status := 'rejected';
        v_risk_status := 'open';
        v_inbox_owner := 'Strategy Research Agent';
        v_inbox_action := 'Gather more evidence and comparable strategy research before another committee decision. No paper or live activation.';
    ELSE
        v_review_status := 'paper_monitor_approved';
        v_candidate_status := 'paper';
        v_validation_status := 'committee_paper_approved';
        v_activation_gate := 'paper_monitor_approved';
        v_approval_status := 'approved';
        v_risk_status := 'monitor';
        v_paper_allowed := true;
        v_inbox_owner := 'Trading Desk Agent';
        v_inbox_action := 'Configure paper monitoring only. Live broker execution remains disabled and requires a separate future approval.';
    END IF;

    INSERT INTO strategy.committee_decisions (
        committee_review_id,
        strategy_id,
        approval_id,
        decision,
        decision_status,
        decision_notes,
        paper_monitor_allowed,
        live_execution_allowed,
        decided_by,
        evidence
    )
    VALUES (
        v_review.id,
        v_review.strategy_id,
        v_review.approval_id,
        v_decision,
        'final',
        v_notes,
        v_paper_allowed,
        false,
        v_actor,
        jsonb_build_array(
            jsonb_build_object('committee_review_id', v_review.id),
            jsonb_build_object('memo_note_path', v_review.memo_note_path),
            jsonb_build_object('recommended_decision', v_review.recommended_decision),
            jsonb_build_object('human_decision_required', true),
            jsonb_build_object('live_execution_allowed', false)
        )
    )
    RETURNING id INTO v_decision_id;

    UPDATE strategy.committee_reviews
    SET review_status = v_review_status,
        final_decision = v_decision,
        decision_status = 'final',
        paper_monitor_allowed = v_paper_allowed,
        live_execution_allowed = false,
        decision_notes = coalesce(v_notes, decision_notes),
        decision_payload = jsonb_build_object(
            'committee_decision_id', v_decision_id,
            'decision', v_decision,
            'paper_monitor_allowed', v_paper_allowed,
            'live_execution_allowed', false,
            'decided_by', v_actor,
            'decided_at', now()
        ),
        decided_by = v_actor,
        decided_at = now(),
        updated_at = now()
    WHERE id = v_review.id;

    UPDATE agent.approvals
    SET status = v_approval_status,
        decided_by = v_actor,
        decided_at = now()
    WHERE id = v_review.approval_id
      AND status = 'pending';

    UPDATE strategy.strategy_candidates
    SET status = v_candidate_status,
        validation_status = v_validation_status,
        activation_gate = v_activation_gate,
        updated_at = now()
    WHERE id = v_review.strategy_id;

    UPDATE risk.events
    SET status = v_risk_status,
        message = coalesce(message, '') || ' Committee decision: ' || v_decision || '. Live execution remains disabled.'
    WHERE approval_id = v_review.approval_id;

    IF v_paper_allowed THEN
        INSERT INTO strategy.strategy_instances (
            strategy_id,
            version_id,
            source_component_id,
            instance_name,
            mode,
            timeframe,
            universe,
            status,
            config,
            notes
        )
        VALUES (
            v_review.strategy_id,
            NULL,
            NULL,
            coalesce(v_strategy.candidate_key, 'strategy-' || v_review.strategy_id::TEXT) || '-paper-monitor-review-' || v_review.id::TEXT,
            'paper',
            v_strategy.timeframe,
            v_strategy.universe,
            'ready',
            jsonb_build_object(
                'committee_review_id', v_review.id,
                'committee_decision_id', v_decision_id,
                'live_execution_allowed', false,
                'requires_separate_live_approval', true,
                'kill_switch_rules', v_review.kill_switch_rules
            ),
            'Paper monitor approved by committee decision. Live execution remains disabled.'
        )
        ON CONFLICT (instance_name) DO UPDATE
        SET mode = 'paper',
            status = 'ready',
            config = EXCLUDED.config,
            notes = EXCLUDED.notes
        RETURNING id INTO v_instance_id;
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
        'Strategy committee decision: ' || coalesce(v_strategy.name, 'strategy ' || v_review.strategy_id::TEXT) || ' -> ' || v_decision,
        v_inbox_owner,
        'needs_review',
        CASE WHEN v_paper_allowed THEN 'critical' ELSE 'high' END,
        v_inbox_action,
        jsonb_build_array(
            jsonb_build_object('committee_review_id', v_review.id),
            jsonb_build_object('committee_decision_id', v_decision_id),
            jsonb_build_object('strategy_id', v_review.strategy_id),
            jsonb_build_object('paper_monitor_instance_id', v_instance_id),
            jsonb_build_object('live_execution_allowed', false)
        ),
        'quant'
    );

    RETURN jsonb_build_object(
        'committee_review_id', v_review.id,
        'committee_decision_id', v_decision_id,
        'strategy_id', v_review.strategy_id,
        'approval_id', v_review.approval_id,
        'decision', v_decision,
        'review_status', v_review_status,
        'approval_status', v_approval_status,
        'strategy_status', v_candidate_status,
        'activation_gate', v_activation_gate,
        'paper_monitor_allowed', v_paper_allowed,
        'paper_monitor_instance_id', v_instance_id,
        'live_execution_allowed', false
    );
END;
$$;

DROP VIEW IF EXISTS strategy.v_strategy_committee_queue;

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
    cr.final_decision,
    cr.decision_status,
    cr.paper_monitor_allowed,
    cr.live_execution_allowed,
    cr.decision_payload,
    cr.memo_note_path,
    cr.memo_status,
    cr.memo_generated_at,
    ap.status AS approval_status,
    ap.decided_by,
    ap.decided_at,
    latest_decision.id AS latest_decision_id,
    latest_decision.decision AS latest_decision,
    latest_decision.created_at AS latest_decision_at,
    cr.created_by,
    cr.created_at,
    cr.updated_at
FROM strategy.committee_reviews cr
LEFT JOIN strategy.strategy_candidates sc ON sc.id = cr.strategy_id
LEFT JOIN agent.approvals ap ON ap.id = cr.approval_id
LEFT JOIN LATERAL (
    SELECT cd.id, cd.decision, cd.created_at
    FROM strategy.committee_decisions cd
    WHERE cd.committee_review_id = cr.id
    ORDER BY cd.created_at DESC
    LIMIT 1
) latest_decision ON true
ORDER BY
    CASE cr.risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    cr.created_at DESC;

