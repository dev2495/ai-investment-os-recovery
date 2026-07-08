ALTER TABLE strategy.committee_reviews
    ADD COLUMN IF NOT EXISTS memo_note_path TEXT,
    ADD COLUMN IF NOT EXISTS memo_status TEXT NOT NULL DEFAULT 'not_generated',
    ADD COLUMN IF NOT EXISTS memo_generated_at TIMESTAMPTZ;

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
    cr.memo_note_path,
    cr.memo_status,
    cr.memo_generated_at,
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
