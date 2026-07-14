UPDATE ops.workspace_profiles
SET navigation = jsonb_set(
        navigation,
        '{visible}',
        coalesce(navigation -> 'visible', '[]'::jsonb) || '"arsenal"'::jsonb,
        true
    ),
    updated_at = now()
WHERE profile_key = 'devarsh'
  AND NOT coalesce(navigation -> 'visible', '[]'::jsonb) ? 'arsenal';

INSERT INTO ops.workspace_layouts (
    profile_id, workspace_key, module_order, hidden_modules,
    column_count, settings, updated_by
)
SELECT id, 'arsenal',
       '["intake","templates","control_board","discovery_triage","promotion_gates"]'::jsonb,
       '[]'::jsonb, 2,
       '{"show_evidence":true,"show_freshness":true,"execution_lock_visible":true}'::jsonb,
       'Codex'
FROM ops.workspace_profiles
WHERE profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO UPDATE SET
    module_order = EXCLUDED.module_order,
    settings = ops.workspace_layouts.settings || EXCLUDED.settings,
    updated_by = EXCLUDED.updated_by,
    updated_at = now();

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_control_board AS
SELECT
    queue.candidate_id,
    queue.candidate_key,
    queue.strategy_name,
    queue.candidate_status,
    queue.validation_status,
    queue.activation_gate,
    queue.owner_agent,
    queue.universe,
    queue.timeframe,
    queue.strategy_family,
    queue.asset_class,
    queue.symbols,
    queue.edge_hypothesis,
    queue.intake_id,
    queue.intake_key,
    coalesce(intake.created_by, 'Legacy Import') AS created_by,
    coalesce(intake.source_kind, 'legacy_import') AS source_kind,
    intake.source_ref,
    CASE
        WHEN intake.created_by = 'Strategy Discovery Agent'
          OR intake.source_kind IN ('strategy_discovery', 'user_defined_optimizer')
            AND intake.source_ref LIKE 'strategy_discovery%'
            THEN 'system_discovery'
        WHEN intake.source_kind IN ('ai_office_dashboard', 'charlie_command', 'user_input')
          OR lower(coalesce(intake.created_by, '')) IN ('devarsh', 'charlie munger')
            THEN 'operator_submitted'
        WHEN intake.source_kind LIKE '%template%' THEN 'template_library'
        WHEN intake.source_kind LIKE '%paper%' OR intake.source_kind LIKE '%research%'
            THEN 'research_sourced'
        ELSE 'imported_or_other'
    END AS origin_type,
    discovery.id AS discovery_candidate_id,
    discovery.discovery_key,
    discovery.source_kind AS discovery_source_kind,
    discovery.source_ref AS discovery_source_ref,
    discovery.triage_decision,
    discovery.triage_status,
    promotion.parse_status,
    promotion.data_quality_status,
    queue.backtest_runs,
    queue.optimization_runs,
    queue.validation_reviews,
    promotion.latest_backtest_run_id,
    promotion.latest_optimization_run_id,
    promotion.validation_review_id,
    promotion.validation_gate_status,
    promotion.validation_gate_reason,
    promotion.validation_decision,
    promotion.required_fixes,
    promotion.committee_review_id,
    promotion.committee_review_status,
    promotion.committee_decision_status,
    promotion.paper_monitor_allowed,
    promotion.paper_monitor_session_id,
    promotion.paper_monitor_status,
    promotion.paper_heartbeat_status,
    promotion.limited_live_request_id,
    promotion.limited_live_request_status,
    promotion.limited_live_approval_status,
    promotion.promotion_stage,
    promotion.next_required_action,
    (
        coalesce(promotion.parse_status = 'passed', false)::int
      + coalesce(promotion.data_quality_status = 'passed', false)::int
      + (promotion.latest_backtest_run_id IS NOT NULL)::int
      + (promotion.latest_optimization_run_id IS NOT NULL)::int
      + coalesce(promotion.validation_gate_status = 'validation_passed', false)::int
      + coalesce(promotion.committee_decision_status IN ('approve_paper_monitor', 'approved'), false)::int
      + (promotion.paper_monitor_session_id IS NOT NULL)::int
      + coalesce(promotion.limited_live_request_status = 'limited_live_approved', false)::int
    ) AS gates_passed,
    8 AS gates_total,
    jsonb_build_object(
        'dsl_parse', coalesce(promotion.parse_status = 'passed', false),
        'data_quality', coalesce(promotion.data_quality_status = 'passed', false),
        'baseline_backtest', promotion.latest_backtest_run_id IS NOT NULL,
        'optimization', promotion.latest_optimization_run_id IS NOT NULL,
        'model_validation', coalesce(promotion.validation_gate_status = 'validation_passed', false),
        'committee', coalesce(promotion.committee_decision_status IN ('approve_paper_monitor', 'approved'), false),
        'paper_monitor', promotion.paper_monitor_session_id IS NOT NULL,
        'limited_live', coalesce(promotion.limited_live_request_status = 'limited_live_approved', false)
    ) AS gate_flags,
    false AS broker_order_allowed,
    false AS autonomous_live_execution_allowed,
    queue.open_tasks,
    queue.latest_task_at,
    greatest(queue.updated_at, promotion.updated_at, intake.updated_at) AS updated_at,
    jsonb_build_array(
        jsonb_build_object('table', 'strategy.strategy_candidates', 'id', queue.candidate_id),
        jsonb_build_object('table', 'strategy.strategy_intakes', 'id', queue.intake_id),
        CASE WHEN discovery.id IS NOT NULL
            THEN jsonb_build_object('table', 'strategy.strategy_discovery_candidates', 'id', discovery.id)
            ELSE NULL END,
        CASE WHEN promotion.validation_review_id IS NOT NULL
            THEN jsonb_build_object('table', 'strategy.validation_reviews', 'id', promotion.validation_review_id)
            ELSE NULL END
    ) AS evidence
FROM strategy.v_strategy_arsenal_queue queue
LEFT JOIN strategy.strategy_intakes intake ON intake.id = queue.intake_id
JOIN strategy.v_strategy_promotion_board promotion ON promotion.strategy_id = queue.candidate_id
LEFT JOIN LATERAL (
    SELECT triage.*
    FROM strategy.v_strategy_discovery_triage_queue triage
    WHERE triage.optimizer_candidate_id = queue.candidate_id
       OR triage.generated_idea_id = queue.idea_id
    ORDER BY triage.created_at DESC, triage.id DESC
    LIMIT 1
) discovery ON true;

CREATE OR REPLACE VIEW strategy.v_strategy_arsenal_control_summary AS
SELECT 'total_candidates'::text AS metric, count(*)::bigint AS value,
       'All strategy candidates with a complete gate record.'::text AS interpretation
FROM strategy.v_strategy_arsenal_control_board
UNION ALL
SELECT 'operator_submitted', count(*), 'Candidates submitted by Devarsh or Charlie.'
FROM strategy.v_strategy_arsenal_control_board WHERE origin_type = 'operator_submitted'
UNION ALL
SELECT 'system_discovered', count(*), 'Candidates generated from the source-backed discovery loop.'
FROM strategy.v_strategy_arsenal_control_board WHERE origin_type = 'system_discovery'
UNION ALL
SELECT 'dsl_passed', count(*), 'Candidates with a parsed machine-testable rule specification.'
FROM strategy.v_strategy_arsenal_control_board WHERE parse_status = 'passed'
UNION ALL
SELECT 'data_quality_passed', count(*), 'Candidates with sufficient point-in-time data for the configured gate.'
FROM strategy.v_strategy_arsenal_control_board WHERE data_quality_status = 'passed'
UNION ALL
SELECT 'backtested', count(*), 'Candidates with at least one baseline backtest.'
FROM strategy.v_strategy_arsenal_control_board WHERE latest_backtest_run_id IS NOT NULL
UNION ALL
SELECT 'optimized', count(*), 'Candidates with at least one optimization run.'
FROM strategy.v_strategy_arsenal_control_board WHERE latest_optimization_run_id IS NOT NULL
UNION ALL
SELECT 'validation_passed', count(*), 'Candidates that passed the model-validation gate.'
FROM strategy.v_strategy_arsenal_control_board WHERE validation_gate_status = 'validation_passed'
UNION ALL
SELECT 'committee_pending', count(*), 'Validated candidates requiring Strategy Committee review.'
FROM strategy.v_strategy_arsenal_control_board WHERE promotion_stage = 'committee_review_required'
UNION ALL
SELECT 'paper_monitoring', count(*), 'Candidates with a paper-monitor session.'
FROM strategy.v_strategy_arsenal_control_board WHERE paper_monitor_session_id IS NOT NULL
UNION ALL
SELECT 'broker_orders_allowed', count(*), 'Must remain zero until a separately approved production execution phase.'
FROM strategy.v_strategy_arsenal_control_board WHERE broker_order_allowed IS true;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled,
    description, config
)
VALUES (
    'ai_os_strategy_arsenal_control_board', 'mcp_tool',
    'Strategy Committee Secretary', 'read_only', true,
    'Read the unified strategy lifecycle with provenance, independent gates, next safe action, and execution lock.',
    '{"reads":["strategy.v_strategy_arsenal_control_board","strategy.v_strategy_arsenal_control_summary"],"seed_data_allowed":false,"broker_order_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
