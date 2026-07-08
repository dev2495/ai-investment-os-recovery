CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence_v2 AS
WITH base AS (
    SELECT *
    FROM portfolio.v_symbol_intelligence
),
remediation AS (
    SELECT
        client_code,
        symbol,
        exchange,
        count(*) FILTER (WHERE status IN ('queued', 'task_created', 'in_progress')) AS remediation_count,
        count(*) FILTER (WHERE severity = 'critical' AND status IN ('queued', 'task_created', 'in_progress')) AS critical_remediation_count,
        count(*) FILTER (WHERE task_id IS NOT NULL AND status IN ('queued', 'task_created', 'in_progress')) AS remediation_task_count,
        jsonb_agg(
            jsonb_build_object(
                'remediation_key', remediation_key,
                'gap_type', gap_type,
                'severity', severity,
                'status', status,
                'owner_agent', owner_agent,
                'skill_key', skill_key,
                'recommended_action', recommended_action,
                'task_id', task_id,
                'task_status', task_status,
                'inbox_id', inbox_id,
                'inbox_status', inbox_status
            )
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                updated_at DESC
        ) FILTER (WHERE status IN ('queued', 'task_created', 'in_progress')) AS remediation_items
    FROM books.v_position_object_remediation_queue
    GROUP BY client_code, symbol, exchange
),
coordination AS (
    SELECT
        client_code,
        symbol,
        exchange,
        count(*) AS coordination_question_count,
        max(severity) FILTER (WHERE severity IS NOT NULL) AS max_coordination_severity,
        jsonb_agg(
            jsonb_build_object(
                'coordination_question', coordination_question,
                'severity', severity,
                'owner_agent', owner_agent,
                'gross_long', gross_long,
                'gross_short', gross_short,
                'net_exposure', net_exposure,
                'offset_ratio', offset_ratio,
                'active_books', active_books,
                'offset_intents', offset_intents
            )
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                offset_ratio DESC NULLS LAST
        ) AS coordination_items
    FROM books.v_cross_book_coordination_questions
    GROUP BY client_code, symbol, exchange
),
committees AS (
    SELECT
        upper(symbol) AS symbol,
        exchange,
        count(*) AS committee_item_count,
        count(*) FILTER (WHERE decision_pending OR approval_pending OR memo_missing) AS pending_committee_item_count,
        jsonb_agg(
            jsonb_build_object(
                'committee_item_key', committee_item_key,
                'committee_lane', committee_lane,
                'title', title,
                'review_status', review_status,
                'decision_status', decision_status,
                'recommended_decision', recommended_decision,
                'final_decision', final_decision,
                'memo_status', memo_status,
                'approval_status', approval_status,
                'room_state', room_state,
                'recommended_next_action', recommended_next_action,
                'latest_activity_at', latest_activity_at
            )
            ORDER BY priority_rank, latest_activity_at DESC NULLS LAST
        ) AS committee_items
    FROM agent.v_committee_room_items
    WHERE symbol IS NOT NULL
    GROUP BY upper(symbol), exchange
),
risk_checks AS (
    SELECT
        client_code,
        symbol,
        exchange,
        count(*) AS risk_check_count,
        count(*) FILTER (WHERE check_status = 'breach') AS risk_breach_count,
        count(*) FILTER (WHERE check_status = 'warning') AS risk_warning_count,
        jsonb_agg(
            jsonb_build_object(
                'check_key', check_key,
                'book_key', book_key,
                'limit_key', limit_key,
                'limit_name', limit_name,
                'severity', severity,
                'check_status', check_status,
                'actual_value', actual_value,
                'threshold_value', threshold_value,
                'utilization_pct', utilization_pct,
                'check_message', check_message,
                'recommended_action', recommended_action
            )
            ORDER BY
                CASE check_status WHEN 'breach' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                utilization_pct DESC NULLS LAST
        ) FILTER (WHERE check_status IN ('breach', 'warning')) AS risk_items
    FROM risk.v_portfolio_risk_limit_checks
    WHERE symbol IS NOT NULL
    GROUP BY client_code, symbol, exchange
),
dossiers AS (
    SELECT
        upper(regexp_replace(symbol_item, '^[A-Z]+:', '')) AS symbol,
        count(*) AS strategy_dossier_count,
        count(*) FILTER (WHERE latest_triage_decision IN ('route_quant_lab', 'open_committee_review', 'request_more_evidence')) AS active_strategy_dossier_count,
        jsonb_agg(
            jsonb_build_object(
                'dossier_id', id,
                'dossier_key', dossier_key,
                'title', title,
                'status', status,
                'latest_triage_decision', latest_triage_decision,
                'recommended_next_action', recommended_next_action,
                'discovery_count', discovery_count,
                'optimizer_run_count', optimizer_run_count,
                'committee_review_count', committee_review_count,
                'priority_score', priority_score,
                'risk_score', risk_score,
                'note_path', note_path,
                'updated_at', updated_at
            )
            ORDER BY priority_score DESC NULLS LAST, updated_at DESC NULLS LAST
        ) AS strategy_dossiers
    FROM strategy.v_idea_dossiers
    CROSS JOIN LATERAL unnest(symbols) symbol_item
    GROUP BY upper(regexp_replace(symbol_item, '^[A-Z]+:', ''))
)
SELECT
    base.*,
    COALESCE(remediation.remediation_count, 0::bigint) AS remediation_count,
    COALESCE(remediation.critical_remediation_count, 0::bigint) AS critical_remediation_count,
    COALESCE(remediation.remediation_task_count, 0::bigint) AS remediation_task_count,
    COALESCE(remediation.remediation_items, '[]'::jsonb) AS remediation_items,
    COALESCE(coordination.coordination_question_count, 0::bigint) AS coordination_question_count,
    coordination.max_coordination_severity,
    COALESCE(coordination.coordination_items, '[]'::jsonb) AS coordination_items,
    COALESCE(committees.committee_item_count, 0::bigint) AS committee_item_count,
    COALESCE(committees.pending_committee_item_count, 0::bigint) AS pending_committee_item_count,
    COALESCE(committees.committee_items, '[]'::jsonb) AS committee_items,
    COALESCE(risk_checks.risk_check_count, 0::bigint) AS risk_check_count,
    COALESCE(risk_checks.risk_breach_count, 0::bigint) AS risk_breach_count,
    COALESCE(risk_checks.risk_warning_count, 0::bigint) AS risk_warning_count,
    COALESCE(risk_checks.risk_items, '[]'::jsonb) AS risk_items,
    COALESCE(dossiers.strategy_dossier_count, 0::bigint) AS strategy_dossier_count,
    COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) AS active_strategy_dossier_count,
    COALESCE(dossiers.strategy_dossiers, '[]'::jsonb) AS strategy_dossiers,
    array_remove(ARRAY[
        CASE WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 'risk_breach' END,
        CASE WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 'critical_position_remediation' END,
        CASE WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 'cross_book_coordination' END,
        CASE WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 'committee_pending' END,
        CASE WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 'material_filing_present' END,
        CASE WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 'strategy_dossier_active' END,
        CASE WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 'strategy_candidate_present' END
    ], NULL::text) AS v2_decision_flags,
    CASE
        WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 'risk_blocked'
        WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 'position_remediation_required'
        WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 'cross_book_review_required'
        WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 'committee_pending'
        WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 'research_update_required'
        WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 'strategy_review_available'
        WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 'strategy_candidate_available'
        ELSE base.decision_readiness
    END AS v2_decision_state,
    CASE
        WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 'Risk Office must resolve breached limits before any capital action.'
        WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 'Complete position remediation tasks for thesis and exit criteria before approval.'
        WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 'Answer cross-book coordination question before adding, trimming, hedging, or trading.'
        WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 'Finish pending committee memo, decision, or approval.'
        WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 'Research Factory should update thesis/setup from latest material filing.'
        WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 'Review linked strategy dossier and route to Quant Lab or committee if useful.'
        WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 'Review linked strategy candidates for paper-only testing.'
        ELSE base.recommended_next_action
    END AS v2_recommended_next_action,
    CASE
        WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 1
        WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 2
        WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 3
        WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 4
        WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 5
        WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 6
        WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 7
        ELSE 8
    END AS v2_priority_rank,
    jsonb_build_object(
        'symbol_key', base.symbol_key,
        'client_code', base.client_code,
        'client_name', base.client_name,
        'symbol', base.symbol,
        'exchange', base.exchange,
        'book_exposure', jsonb_build_object(
            'long_term', base.long_term_exposure,
            'tactical', base.tactical_exposure,
            'quant', base.quant_exposure,
            'active_trading', base.active_trading_exposure,
            'hedges', base.hedges_exposure,
            'cash_treasury', base.cash_treasury_exposure,
            'gross_long', base.gross_long,
            'gross_short', base.gross_short,
            'net_exposure', base.net_exposure,
            'overall_bias', base.overall_bias
        ),
        'readiness', jsonb_build_object(
            'v1_state', base.decision_readiness,
            'v2_state', CASE
                WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 'risk_blocked'
                WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 'position_remediation_required'
                WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 'cross_book_review_required'
                WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 'committee_pending'
                WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 'research_update_required'
                WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 'strategy_review_available'
                WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 'strategy_candidate_available'
                ELSE base.decision_readiness
            END,
            'flags', array_remove(ARRAY[
                CASE WHEN COALESCE(risk_checks.risk_breach_count, 0::bigint) > 0 THEN 'risk_breach' END,
                CASE WHEN COALESCE(remediation.critical_remediation_count, 0::bigint) > 0 THEN 'critical_position_remediation' END,
                CASE WHEN COALESCE(coordination.coordination_question_count, 0::bigint) > 0 THEN 'cross_book_coordination' END,
                CASE WHEN COALESCE(committees.pending_committee_item_count, 0::bigint) > 0 THEN 'committee_pending' END,
                CASE WHEN COALESCE(base.material_filing_count, 0::bigint) > 0 THEN 'material_filing_present' END,
                CASE WHEN COALESCE(dossiers.active_strategy_dossier_count, 0::bigint) > 0 THEN 'strategy_dossier_active' END,
                CASE WHEN COALESCE(base.symbol_strategy_candidate_count, 0::bigint) > 0 THEN 'strategy_candidate_present' END
            ], NULL::text)
        ),
        'latest_evidence', jsonb_build_object(
            'news_title', base.latest_news_title,
            'news_url', base.latest_news_url,
            'filing_title', base.latest_filing_title,
            'filing_url', base.latest_filing_source_url,
            'committee_memo', base.memo_note_path,
            'thesis_note', base.thesis_note_path,
            'monte_carlo_note', base.monte_carlo_note_path
        )
    ) AS v2_decision_packet
FROM base
LEFT JOIN remediation
    ON NOT remediation.client_code IS DISTINCT FROM base.client_code
    AND remediation.symbol = base.symbol
    AND NOT remediation.exchange IS DISTINCT FROM base.exchange
LEFT JOIN coordination
    ON NOT coordination.client_code IS DISTINCT FROM base.client_code
    AND coordination.symbol = base.symbol
    AND NOT coordination.exchange IS DISTINCT FROM base.exchange
LEFT JOIN committees
    ON committees.symbol = upper(base.symbol)
    AND NOT committees.exchange IS DISTINCT FROM base.exchange
LEFT JOIN risk_checks
    ON NOT risk_checks.client_code IS DISTINCT FROM base.client_code
    AND risk_checks.symbol = base.symbol
    AND NOT risk_checks.exchange IS DISTINCT FROM base.exchange
LEFT JOIN dossiers
    ON dossiers.symbol = upper(base.symbol);

CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence_v2_summary AS
SELECT 'symbol_rows' AS metric, count(*)::text AS value, 'Client-symbol rows in Symbol Intelligence v2' AS interpretation
FROM portfolio.v_symbol_intelligence_v2
UNION ALL
SELECT 'symbols', count(DISTINCT symbol)::text, 'Distinct symbols covered by Symbol Intelligence v2'
FROM portfolio.v_symbol_intelligence_v2
UNION ALL
SELECT 'critical_remediation_rows', count(*)::text, 'Rows where critical position remediation must be completed before decision'
FROM portfolio.v_symbol_intelligence_v2
WHERE critical_remediation_count > 0
UNION ALL
SELECT 'risk_blocked_rows', count(*)::text, 'Rows blocked by portfolio risk limit breaches'
FROM portfolio.v_symbol_intelligence_v2
WHERE risk_breach_count > 0
UNION ALL
SELECT 'committee_pending_rows', count(*)::text, 'Rows with pending committee memo, decision, or approval'
FROM portfolio.v_symbol_intelligence_v2
WHERE pending_committee_item_count > 0
UNION ALL
SELECT 'strategy_linked_rows', count(*)::text, 'Rows with linked strategy candidates or dossiers'
FROM portfolio.v_symbol_intelligence_v2
WHERE symbol_strategy_candidate_count > 0 OR strategy_dossier_count > 0;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'ai_os_symbol_intelligence_v2',
        'mcp_tool',
        'Charlie Munger',
        'read_only',
        true,
        'Read Symbol Intelligence v2 decision packets with book exposure, remediation, committees, risk, news, filings, and strategy links.',
        '{"reads":["portfolio.v_symbol_intelligence_v2","portfolio.v_symbol_intelligence_v2_summary"],"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_symbol_intelligence_v2_summary',
        'mcp_tool',
        'Portfolio Manager',
        'read_only',
        true,
        'Read Symbol Intelligence v2 coverage and decision-state summary metrics.',
        '{"reads":["portfolio.v_symbol_intelligence_v2_summary"],"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE
SET tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
