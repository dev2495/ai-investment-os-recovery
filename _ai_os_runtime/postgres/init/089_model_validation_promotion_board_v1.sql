ALTER TABLE strategy.validation_reviews
    ADD COLUMN IF NOT EXISTS validation_key TEXT;

DROP INDEX IF EXISTS strategy.uq_validation_reviews_validation_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_validation_reviews_validation_key
    ON strategy.validation_reviews (validation_key);

CREATE OR REPLACE VIEW strategy.v_model_validation_dashboard AS
WITH latest_validation AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.validation_reviews
    ORDER BY strategy_id, updated_at DESC, created_at DESC, id DESC
),
latest_backtest AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.backtest_runs
    ORDER BY strategy_id, finished_at DESC NULLS LAST, started_at DESC, id DESC
),
latest_optimization AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.optimization_runs
    ORDER BY strategy_id, finished_at DESC NULLS LAST, started_at DESC, id DESC
),
latest_retirement AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.v_strategy_retirement_queue
    ORDER BY strategy_id, updated_at DESC, created_at DESC, id DESC
),
latest_dsl AS (
    SELECT DISTINCT ON (candidate_id)
        *
    FROM strategy.v_strategy_dsl_readiness_summary
    ORDER BY candidate_id, updated_at DESC
)
SELECT
    candidate.id AS strategy_id,
    coalesce(candidate.candidate_key, 'candidate_' || candidate.id::TEXT) AS candidate_key,
    candidate.name AS strategy_name,
    candidate.status AS candidate_status,
    candidate.validation_status,
    candidate.activation_gate,
    candidate.timeframe,
    dsl.parse_status,
    dsl.data_quality_status,
    dsl.data_quality_reasons,
    dsl.total_rows AS data_quality_rows,
    backtest.id AS latest_backtest_run_id,
    backtest.run_status AS latest_backtest_status,
    backtest.metrics AS latest_backtest_metrics,
    backtest.diagnostics AS latest_backtest_diagnostics,
    backtest.artifact_path AS latest_backtest_artifact_path,
    backtest.finished_at AS latest_backtest_finished_at,
    optimization.id AS latest_optimization_run_id,
    optimization.status AS latest_optimization_status,
    optimization.metrics AS latest_optimization_metrics,
    optimization.diagnostics AS latest_optimization_diagnostics,
    optimization.artifact_path AS latest_optimization_artifact_path,
    optimization.finished_at AS latest_optimization_finished_at,
    validation.id AS validation_review_id,
    validation.validation_key,
    validation.reviewer_agent,
    validation.review_status,
    validation.decision,
    validation.leakage_risk,
    validation.overfit_risk,
    validation.transaction_cost_notes,
    validation.sample_size_notes,
    validation.required_fixes,
    validation.issues,
    validation.evidence,
    validation.updated_at AS validation_updated_at,
    retirement.review_key AS retirement_review_key,
    retirement.recommended_action AS retirement_recommended_action,
    retirement.severity AS retirement_severity,
    retirement.trigger_reasons AS retirement_trigger_reasons,
    CASE
        WHEN backtest.id IS NULL THEN 'missing_backtest'
        WHEN dsl.parse_status IS DISTINCT FROM 'passed' THEN 'dsl_not_passed'
        WHEN dsl.data_quality_status IS DISTINCT FROM 'passed' THEN 'data_quality_not_passed'
        WHEN validation.id IS NULL THEN 'validation_missing'
        WHEN validation.decision IN ('approve_for_committee_review','approve_paper_monitor','approved','passed') THEN 'validation_passed'
        WHEN validation.decision ILIKE 'blocked%' OR validation.decision IN ('reject_or_retest','blocked_until_data_quality','blocked_until_broader_sample','blocked_until_backtest') THEN 'validation_blocking'
        ELSE 'validation_review_required'
    END AS validation_gate_status,
    CASE
        WHEN validation.id IS NULL THEN 'Model Validation Agent has not recorded a review for the latest evidence.'
        WHEN validation.decision IN ('approve_for_committee_review','approve_paper_monitor','approved','passed') THEN 'Validation is clear enough for committee review, not live execution.'
        WHEN validation.decision IS NULL THEN 'Validation review exists but no decision is recorded.'
        ELSE validation.decision
    END AS validation_gate_reason,
    false AS live_execution_allowed,
    greatest(
        coalesce(validation.updated_at, 'epoch'::timestamptz),
        coalesce(backtest.finished_at, backtest.started_at, 'epoch'::timestamptz),
        coalesce(optimization.finished_at, optimization.started_at, 'epoch'::timestamptz),
        coalesce(retirement.updated_at, 'epoch'::timestamptz),
        coalesce(candidate.updated_at, candidate.created_at)
    ) AS updated_at
FROM strategy.strategy_candidates candidate
LEFT JOIN latest_dsl dsl ON dsl.candidate_id = candidate.id
LEFT JOIN latest_backtest backtest ON backtest.strategy_id = candidate.id
LEFT JOIN latest_optimization optimization ON optimization.strategy_id = candidate.id
LEFT JOIN latest_validation validation ON validation.strategy_id = candidate.id
LEFT JOIN latest_retirement retirement ON retirement.strategy_id = candidate.id
WHERE candidate.status IN ('imported','idea','research','candidate','paper_monitor','limited_live','paused','retired')
   OR backtest.id IS NOT NULL
   OR optimization.id IS NOT NULL
   OR validation.id IS NOT NULL
   OR retirement.id IS NOT NULL;

CREATE OR REPLACE VIEW strategy.v_strategy_promotion_board AS
WITH latest_committee AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.committee_reviews
    ORDER BY strategy_id, updated_at DESC, created_at DESC, id DESC
),
latest_paper AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM strategy.paper_monitor_sessions
    ORDER BY strategy_id, updated_at DESC, created_at DESC, id DESC
),
latest_limited_live AS (
    SELECT DISTINCT ON (strategy_id)
        *
    FROM trading.v_limited_live_requests
    ORDER BY strategy_id, updated_at DESC, created_at DESC, id DESC
)
SELECT
    validation.strategy_id,
    validation.candidate_key,
    validation.strategy_name,
    validation.candidate_status,
    validation.validation_status,
    validation.activation_gate,
    validation.parse_status,
    validation.data_quality_status,
    validation.latest_backtest_run_id,
    validation.latest_optimization_run_id,
    validation.validation_review_id,
    validation.validation_gate_status,
    validation.validation_gate_reason,
    validation.decision AS validation_decision,
    validation.required_fixes,
    validation.retirement_recommended_action,
    validation.retirement_trigger_reasons,
    committee.id AS committee_review_id,
    committee.review_key AS committee_review_key,
    committee.review_status AS committee_review_status,
    committee.recommended_decision AS committee_recommended_decision,
    committee.proposed_mode AS committee_proposed_mode,
    committee.decision_status AS committee_decision_status,
    committee.paper_monitor_allowed,
    committee.live_execution_allowed AS committee_live_execution_allowed,
    paper.id AS paper_monitor_session_id,
    paper.session_key AS paper_monitor_session_key,
    paper.status AS paper_monitor_status,
    paper.heartbeat_status AS paper_heartbeat_status,
    paper.last_heartbeat_at AS paper_last_heartbeat_at,
    limited.id AS limited_live_request_id,
    limited.request_key AS limited_live_request_key,
    limited.request_status AS limited_live_request_status,
    limited.approval_status AS limited_live_approval_status,
    limited.max_notional,
    limited.max_daily_loss,
    limited.live_execution_allowed AS limited_live_execution_allowed,
    CASE
        WHEN validation.latest_backtest_run_id IS NULL THEN 'backtest_required'
        WHEN validation.validation_gate_status IN ('missing_backtest','dsl_not_passed','data_quality_not_passed','validation_missing','validation_blocking') THEN validation.validation_gate_status
        WHEN committee.id IS NULL THEN 'committee_review_required'
        WHEN committee.decision_status = 'pending' THEN 'committee_pending'
        WHEN committee.paper_monitor_allowed IS true AND paper.id IS NULL THEN 'paper_monitor_ready'
        WHEN paper.id IS NOT NULL AND paper.status IN ('ready','running','active') AND limited.id IS NULL THEN 'paper_monitor_running'
        WHEN limited.id IS NOT NULL AND limited.request_status <> 'limited_live_approved' THEN 'limited_live_pending_or_blocked'
        WHEN limited.id IS NOT NULL AND limited.live_execution_allowed IS true THEN 'limited_live_approved_but_still_human_gated'
        ELSE 'research_or_retest'
    END AS promotion_stage,
    CASE
        WHEN validation.latest_backtest_run_id IS NULL THEN 'Run a deterministic backtest before validation or committee.'
        WHEN validation.validation_gate_status = 'dsl_not_passed' THEN 'Repair strategy DSL before promotion.'
        WHEN validation.validation_gate_status = 'data_quality_not_passed' THEN 'Pass data-quality gate before promotion.'
        WHEN validation.validation_gate_status = 'validation_missing' THEN 'Run Model Validation Agent review.'
        WHEN validation.validation_gate_status = 'validation_blocking' THEN 'Resolve model-validation required fixes.'
        WHEN committee.id IS NULL THEN 'Open Strategy Committee review after validation.'
        WHEN committee.decision_status = 'pending' THEN 'Committee decision still pending.'
        WHEN committee.paper_monitor_allowed IS true AND paper.id IS NULL THEN 'Start paper monitor if Devarsh approves.'
        WHEN paper.id IS NOT NULL AND limited.id IS NULL THEN 'Paper monitoring running or ready; limited-live requires separate risk approval.'
        WHEN limited.id IS NOT NULL AND limited.request_status <> 'limited_live_approved' THEN 'Limited-live request is pending, rejected, expired, or globally locked.'
        ELSE 'Review current strategy state.'
    END AS next_required_action,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed,
    validation.updated_at
FROM strategy.v_model_validation_dashboard validation
LEFT JOIN latest_committee committee ON committee.strategy_id = validation.strategy_id
LEFT JOIN latest_paper paper ON paper.strategy_id = validation.strategy_id
LEFT JOIN latest_limited_live limited ON limited.strategy_id = validation.strategy_id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_run_model_validation_sweep', 'mcp_tool', 'Model Validation Agent', 'write_with_approval', true,
     'Run deterministic model-validation reviews from latest strategy evidence. This does not approve live execution.',
     '{"script":"_ai_os_runtime/scripts/run_model_validation_sweep.py","writes":["strategy.validation_reviews"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_model_validation_dashboard', 'mcp_tool', 'Model Validation Agent', 'read_only', true,
     'Read model validation dashboard rows and promotion-board gate status.',
     '{"reads":["strategy.v_model_validation_dashboard","strategy.v_strategy_promotion_board"]}'::jsonb),
    ('ai_os_strategy_promotion_board', 'mcp_tool', 'Strategy Committee Secretary', 'read_only', true,
     'Read strategy promotion board from backtest, DSL, validation, committee, paper, and limited-live gates.',
     '{"reads":["strategy.v_strategy_promotion_board"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
