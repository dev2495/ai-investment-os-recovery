CREATE OR REPLACE VIEW agent.v_committee_room_items AS
WITH strategy_items AS (
    SELECT
        ('strategy:' || review.id::TEXT) AS committee_item_key,
        'Strategy Committee'::TEXT AS committee_lane,
        'Quant / Strategy'::TEXT AS committee_scope,
        'strategy.v_strategy_committee_queue'::TEXT AS source_view,
        review.id AS source_id,
        review.review_key,
        review.strategy_id,
        NULL::BIGINT AS holding_thesis_id,
        NULL::BIGINT AS special_memo_id,
        NULL::TEXT AS symbol,
        NULL::TEXT AS exchange,
        review.strategy_name AS subject_name,
        ('Strategy committee decision: ' || coalesce(review.strategy_name, review.review_key, review.id::TEXT)) AS title,
        review.review_status,
        review.decision_status,
        review.recommended_decision,
        review.final_decision,
        review.proposed_mode,
        review.risk_level,
        review.memo_status,
        review.memo_note_path,
        review.approval_id,
        review.approval_status,
        review.decided_by,
        review.decided_at,
        review.paper_monitor_allowed,
        false::BOOLEAN AS capital_action_allowed,
        coalesce(review.live_execution_allowed, false) AS live_execution_allowed,
        cardinality(coalesce(review.committee_members, ARRAY[]::TEXT[]))::BIGINT AS member_count,
        cardinality(coalesce(review.required_evidence, ARRAY[]::TEXT[]))::BIGINT AS evidence_gap_count,
        0::BIGINT AS required_followup_count,
        review.created_by,
        review.created_at,
        review.updated_at,
        jsonb_strip_nulls(jsonb_build_object(
            'committee_members', review.committee_members,
            'required_evidence', review.required_evidence,
            'kill_switch_rules', review.kill_switch_rules,
            'risk_summary', review.risk_summary,
            'decision_notes', review.decision_notes,
            'decision_payload', review.decision_payload,
            'latest_decision_id', review.latest_decision_id,
            'latest_decision', review.latest_decision,
            'latest_decision_at', review.latest_decision_at,
            'backtest_run_id', review.backtest_run_id,
            'optimization_run_id', review.optimization_run_id,
            'validation_review_id', review.validation_review_id
        )) AS evidence
    FROM strategy.v_strategy_committee_queue review
),
long_term_items AS (
    SELECT
        ('long_term:' || review.id::TEXT) AS committee_item_key,
        'Long-Term Committee'::TEXT AS committee_lane,
        'Long-Term Investing'::TEXT AS committee_scope,
        'portfolio.v_long_term_committee_queue'::TEXT AS source_view,
        review.id AS source_id,
        review.review_key,
        NULL::BIGINT AS strategy_id,
        review.holding_thesis_id,
        NULL::BIGINT AS special_memo_id,
        review.symbol,
        review.exchange,
        coalesce(review.company_name, review.symbol) AS subject_name,
        ('Long-term committee decision: ' || coalesce(review.company_name, review.symbol, review.review_key, review.id::TEXT)) AS title,
        review.review_status,
        review.decision_status,
        review.recommended_decision,
        review.final_decision,
        NULL::TEXT AS proposed_mode,
        coalesce(review.approval_risk_level, 'high') AS risk_level,
        review.memo_status,
        review.memo_note_path,
        review.approval_id,
        review.approval_status,
        review.decided_by,
        review.decided_at,
        false::BOOLEAN AS paper_monitor_allowed,
        coalesce(review.capital_action_allowed, false) AS capital_action_allowed,
        coalesce(review.live_execution_allowed, false) AS live_execution_allowed,
        CASE
            WHEN jsonb_typeof(review.committee_members) = 'array' THEN jsonb_array_length(review.committee_members)
            ELSE 0
        END::BIGINT AS member_count,
        CASE
            WHEN jsonb_typeof(review.source_gaps) = 'array' THEN jsonb_array_length(review.source_gaps)
            ELSE 0
        END::BIGINT AS evidence_gap_count,
        CASE
            WHEN jsonb_typeof(review.required_followups) = 'array' THEN jsonb_array_length(review.required_followups)
            ELSE 0
        END::BIGINT AS required_followup_count,
        review.created_by,
        review.created_at,
        review.updated_at,
        jsonb_strip_nulls(jsonb_build_object(
            'thesis_title', review.thesis_title,
            'thesis_status', review.thesis_status,
            'thesis_decision_status', review.thesis_decision_status,
            'long_term_gross_exposure', review.long_term_gross_exposure,
            'client_count', review.client_count,
            'clients', review.clients,
            'checklist_count', review.checklist_count,
            'checklist_complete_count', review.checklist_complete_count,
            'valuation_model_count', review.valuation_model_count,
            'valuation_complete_count', review.valuation_complete_count,
            'committee_members', review.committee_members,
            'evidence_summary', review.evidence_summary,
            'source_gaps', review.source_gaps,
            'required_followups', review.required_followups,
            'proposed_action', review.proposed_action,
            'decision_notes', review.decision_notes,
            'task_id', review.task_id,
            'task_status', review.task_status
        )) AS evidence
    FROM portfolio.v_long_term_committee_queue review
),
special_items AS (
    SELECT
        ('special:' || memo.id::TEXT) AS committee_item_key,
        'Special Situation Committee'::TEXT AS committee_lane,
        'Event / Arbitrage'::TEXT AS committee_scope,
        'research.v_special_situation_memos'::TEXT AS source_view,
        memo.id AS source_id,
        ('special-memo-' || memo.id::TEXT) AS review_key,
        NULL::BIGINT AS strategy_id,
        NULL::BIGINT AS holding_thesis_id,
        memo.id AS special_memo_id,
        memo.symbol,
        memo.exchange,
        coalesce(memo.company_name, memo.symbol, memo.event_type) AS subject_name,
        coalesce(memo.memo_title, 'Special situation review: ' || coalesce(memo.company_name, memo.symbol, memo.event_type, memo.id::TEXT)) AS title,
        memo.memo_status AS review_status,
        coalesce(memo.latest_decision, memo.approval_status, 'pending') AS decision_status,
        CASE
            WHEN memo.latest_decision IS NOT NULL THEN memo.latest_decision
            WHEN memo.latest_spread_status = 'spread_available' THEN 'monitor'
            ELSE 'research_more'
        END AS recommended_decision,
        memo.latest_decision AS final_decision,
        NULL::TEXT AS proposed_mode,
        coalesce(memo.approval_risk_level, 'high') AS risk_level,
        memo.memo_status,
        memo.note_path AS memo_note_path,
        memo.approval_id,
        memo.approval_status,
        NULL::TEXT AS decided_by,
        memo.latest_decision_at AS decided_at,
        false::BOOLEAN AS paper_monitor_allowed,
        false::BOOLEAN AS capital_action_allowed,
        false::BOOLEAN AS live_execution_allowed,
        0::BIGINT AS member_count,
        (
            CASE WHEN jsonb_typeof(memo.risk_flags) = 'array' THEN jsonb_array_length(memo.risk_flags) ELSE 0 END
        )::BIGINT AS evidence_gap_count,
        (
            CASE WHEN jsonb_typeof(memo.required_followups) = 'array' THEN jsonb_array_length(memo.required_followups) ELSE 0 END
        )::BIGINT AS required_followup_count,
        memo.created_by,
        memo.created_at,
        memo.updated_at,
        jsonb_strip_nulls(jsonb_build_object(
            'event_type', memo.event_type,
            'filing_id', memo.filing_id,
            'filing_event_id', memo.filing_event_id,
            'filing_title', memo.filing_title,
            'source_name', memo.source_name,
            'source_url', memo.source_url,
            'attachment_url', memo.attachment_url,
            'summary', memo.summary,
            'extracted_terms', memo.extracted_terms,
            'risk_flags', memo.risk_flags,
            'required_followups', memo.required_followups,
            'latest_spread_check_id', memo.latest_spread_check_id,
            'latest_spread_status', memo.latest_spread_status,
            'latest_market_price', memo.latest_market_price,
            'latest_target_price', memo.latest_target_price,
            'latest_gross_spread_pct', memo.latest_gross_spread_pct,
            'latest_quote_ts', memo.latest_quote_ts,
            'latest_decision_id', memo.latest_decision_id,
            'latest_decision', memo.latest_decision,
            'task_id', memo.task_id,
            'task_status', memo.task_status
        )) AS evidence
    FROM research.v_special_situation_memos memo
),
combined AS (
    SELECT * FROM strategy_items
    UNION ALL
    SELECT * FROM long_term_items
    UNION ALL
    SELECT * FROM special_items
)
SELECT
    combined.*,
    CASE
        WHEN coalesce(decision_status, '') IN ('final','approved','rejected','committee_rejected','committee_monitor','committee_watchlist_approved','committee_hold_approved') THEN false
        WHEN final_decision IS NOT NULL THEN false
        ELSE true
    END AS decision_pending,
    CASE
        WHEN approval_status = 'pending' THEN true
        ELSE false
    END AS approval_pending,
    CASE
        WHEN memo_status IS NULL OR memo_status IN ('not_generated','pending','queued') THEN true
        ELSE false
    END AS memo_missing,
    CASE
        WHEN live_execution_allowed OR capital_action_allowed THEN 'action_allowed'
        WHEN approval_status = 'pending' THEN 'approval_pending'
        WHEN final_decision IS NOT NULL OR decision_status IN ('rejected','final','committee_rejected','committee_monitor','committee_watchlist_approved','committee_hold_approved') THEN 'decided'
        WHEN memo_status IS NULL OR memo_status IN ('not_generated','pending','queued') THEN 'memo_needed'
        WHEN evidence_gap_count > 0 OR required_followup_count > 0 THEN 'evidence_gap'
        ELSE 'ready_for_decision'
    END AS room_state,
    CASE
        WHEN live_execution_allowed THEN 'Live execution flag is true; verify separate execution gates before any action.'
        WHEN capital_action_allowed THEN 'Capital action flag is true; verify separate order/capital approval before any action.'
        WHEN approval_status = 'pending' THEN 'Human approval is pending; review evidence before deciding.'
        WHEN memo_status IS NULL OR memo_status IN ('not_generated','pending','queued') THEN 'Generate committee memo before decision.'
        WHEN evidence_gap_count > 0 OR required_followup_count > 0 THEN 'Close evidence gaps and required follow-ups before final decision.'
        WHEN final_decision IS NULL AND coalesce(decision_status, '') NOT IN ('final','approved','rejected') THEN 'Ready for committee decision workflow.'
        ELSE 'Decision recorded; monitor follow-up tasks.'
    END AS recommended_next_action,
    CASE risk_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END AS risk_rank,
    CASE
        WHEN approval_status = 'pending' THEN 1
        WHEN final_decision IS NULL AND coalesce(decision_status, '') NOT IN ('final','approved','rejected') THEN 2
        WHEN evidence_gap_count > 0 OR required_followup_count > 0 THEN 3
        ELSE 4
    END AS priority_rank,
    greatest(coalesce(updated_at, 'epoch'::timestamptz), coalesce(created_at, 'epoch'::timestamptz), coalesce(decided_at, 'epoch'::timestamptz)) AS latest_activity_at
FROM combined;

CREATE OR REPLACE VIEW agent.v_committee_room_summary AS
SELECT 'total'::TEXT AS metric, count(*)::TEXT AS value, 'All committee room items across strategy, long-term, and special situations.'::TEXT AS interpretation
FROM agent.v_committee_room_items
UNION ALL
SELECT 'decision_pending', count(*) FILTER (WHERE decision_pending)::TEXT, 'Committee items still requiring a decision workflow.'
FROM agent.v_committee_room_items
UNION ALL
SELECT 'approval_pending', count(*) FILTER (WHERE approval_pending)::TEXT, 'Committee items with pending human approval.'
FROM agent.v_committee_room_items
UNION ALL
SELECT 'memo_missing', count(*) FILTER (WHERE memo_missing)::TEXT, 'Committee items missing a generated memo.'
FROM agent.v_committee_room_items
UNION ALL
SELECT 'action_allowed', count(*) FILTER (WHERE room_state = 'action_allowed')::TEXT, 'Items whose current read model reports capital or live execution action allowed.'
FROM agent.v_committee_room_items;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_committee_room', 'mcp_tool', 'Charlie Munger', 'read_only', true, 'Read the unified committee room across Strategy Committee, Long-Term Committee, and Special Situation reviews.', '{"reads":["agent.v_committee_room_items","agent.v_committee_room_summary"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
