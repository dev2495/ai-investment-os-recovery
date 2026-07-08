CREATE OR REPLACE VIEW agent.v_approval_board_items AS
WITH latest_strategy AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        id AS linked_record_id,
        strategy_name,
        review_status,
        recommended_decision,
        proposed_mode,
        risk_summary,
        memo_status,
        memo_note_path,
        live_execution_allowed,
        updated_at
    FROM strategy.v_strategy_committee_queue
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, updated_at DESC NULLS LAST, id DESC
),
latest_long_term AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        id AS linked_record_id,
        symbol,
        company_name,
        thesis_title,
        review_status,
        recommended_decision,
        decision_status,
        memo_status,
        memo_note_path,
        source_gaps,
        capital_action_allowed,
        live_execution_allowed,
        updated_at
    FROM portfolio.v_long_term_committee_queue
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, updated_at DESC NULLS LAST, id DESC
),
latest_limited_live AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        id AS linked_record_id,
        strategy_name,
        symbol,
        requested_mode,
        request_status,
        max_notional,
        max_daily_loss,
        expires_at,
        gate_requirements,
        live_execution_allowed,
        updated_at
    FROM trading.v_limited_live_requests
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, updated_at DESC NULLS LAST, id DESC
),
latest_order AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        id AS linked_record_id,
        order_intent_key,
        client_code,
        account_code,
        book_key,
        symbol,
        exchange,
        side,
        order_type,
        quantity,
        notional,
        estimated_loss,
        status AS order_status,
        gate_status,
        broker_order_allowed,
        live_execution_allowed,
        updated_at
    FROM trading.v_order_intents
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, updated_at DESC NULLS LAST, id DESC
),
latest_tradingview AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        tradingview_task_id AS linked_record_id,
        symbol,
        exchange,
        timeframe,
        chart_layout,
        instruction,
        alert_condition,
        alert_request_state,
        task_status,
        task_created_at AS updated_at
    FROM ops.v_tradingview_alert_requests
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, task_created_at DESC NULLS LAST, tradingview_task_id DESC
),
latest_special AS (
    SELECT DISTINCT ON (approval_id)
        approval_id,
        id AS linked_record_id,
        event_type,
        symbol,
        company_name,
        filing_title,
        memo_status,
        note_path,
        latest_spread_status,
        latest_gross_spread_pct,
        latest_decision,
        updated_at
    FROM research.v_special_situation_memos
    WHERE approval_id IS NOT NULL
    ORDER BY approval_id, updated_at DESC NULLS LAST, id DESC
),
risk_rollup AS (
    SELECT
        approval_id,
        count(*) FILTER (WHERE status IN ('new','acknowledged'))::BIGINT AS open_risk_events,
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'severity', severity,
                'status', status,
                'title', title,
                'scope_type', scope_type,
                'scope_ref', scope_ref,
                'ts', ts
            )
            ORDER BY ts DESC
        ) FILTER (WHERE status IN ('new','acknowledged')) AS risk_events
    FROM risk.events
    WHERE approval_id IS NOT NULL
    GROUP BY approval_id
),
gate_rollup AS (
    SELECT
        approval_id,
        count(*)::BIGINT AS gate_check_count,
        count(*) FILTER (WHERE gate_status <> 'allowed')::BIGINT AS blocked_gate_count,
        max(checked_at) AS latest_gate_check_at,
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'gate_status', gate_status,
                'block_reasons', block_reasons,
                'live_execution_allowed', live_execution_allowed,
                'checked_at', checked_at
            )
            ORDER BY checked_at DESC
        ) AS gate_checks
    FROM trading.v_execution_gate_checks
    WHERE approval_id IS NOT NULL
    GROUP BY approval_id
)
SELECT
    approval.id AS approval_id,
    approval.task_id,
    approval.approval_type,
    CASE
        WHEN latest_order.approval_id IS NOT NULL THEN 'Order Intent'
        WHEN latest_limited_live.approval_id IS NOT NULL THEN 'Limited Live'
        WHEN latest_strategy.approval_id IS NOT NULL THEN 'Strategy Committee'
        WHEN latest_long_term.approval_id IS NOT NULL THEN 'Long-Term Committee'
        WHEN latest_special.approval_id IS NOT NULL THEN 'Special Situation'
        WHEN latest_tradingview.approval_id IS NOT NULL THEN 'TradingView'
        WHEN approval.approval_type ILIKE '%trade%' THEN 'Trade Action'
        ELSE 'General Approval'
    END AS board_lane,
    approval.title,
    approval.owner_agent,
    approval.risk_level,
    approval.status AS approval_status,
    approval.requested_action,
    approval.rationale,
    approval.decided_by,
    approval.decided_at,
    approval.created_at,
    task.status AS task_status,
    task.owner_agent AS task_owner_agent,
    coalesce(
        latest_order.symbol,
        latest_limited_live.symbol,
        latest_long_term.symbol,
        latest_special.symbol,
        latest_tradingview.symbol
    ) AS symbol,
    coalesce(
        latest_order.exchange,
        latest_tradingview.exchange
    ) AS exchange,
    coalesce(latest_strategy.strategy_name, latest_limited_live.strategy_name) AS strategy_name,
    latest_order.client_code,
    latest_order.account_code,
    latest_order.book_key,
    coalesce(
        latest_order.linked_record_id,
        latest_limited_live.linked_record_id,
        latest_strategy.linked_record_id,
        latest_long_term.linked_record_id,
        latest_special.linked_record_id,
        latest_tradingview.linked_record_id
    ) AS linked_record_id,
    CASE
        WHEN latest_order.approval_id IS NOT NULL THEN 'trading.v_order_intents'
        WHEN latest_limited_live.approval_id IS NOT NULL THEN 'trading.v_limited_live_requests'
        WHEN latest_strategy.approval_id IS NOT NULL THEN 'strategy.v_strategy_committee_queue'
        WHEN latest_long_term.approval_id IS NOT NULL THEN 'portfolio.v_long_term_committee_queue'
        WHEN latest_special.approval_id IS NOT NULL THEN 'research.v_special_situation_memos'
        WHEN latest_tradingview.approval_id IS NOT NULL THEN 'ops.v_tradingview_alert_requests'
        ELSE 'agent.approvals'
    END AS linked_source,
    coalesce(
        latest_order.order_status,
        latest_limited_live.request_status,
        latest_strategy.review_status,
        latest_long_term.review_status,
        latest_special.memo_status,
        latest_tradingview.alert_request_state,
        task.status
    ) AS linked_status,
    coalesce(latest_order.gate_status, latest_tradingview.task_status) AS gate_status,
    coalesce(latest_order.broker_order_allowed, false) AS broker_order_allowed,
    coalesce(
        latest_order.live_execution_allowed,
        latest_limited_live.live_execution_allowed,
        latest_strategy.live_execution_allowed,
        latest_long_term.live_execution_allowed,
        false
    ) AS live_execution_allowed,
    coalesce(risk_rollup.open_risk_events, 0)::BIGINT AS open_risk_events,
    coalesce(gate_rollup.gate_check_count, 0)::BIGINT AS gate_check_count,
    coalesce(gate_rollup.blocked_gate_count, 0)::BIGINT AS blocked_gate_count,
    CASE
        WHEN approval.status = 'pending' AND coalesce(risk_rollup.open_risk_events, 0) > 0 THEN 'Review open risk events before deciding.'
        WHEN approval.status = 'pending' AND latest_order.approval_id IS NOT NULL THEN 'Per-order human approval required; broker placement remains disabled unless all gates pass.'
        WHEN approval.status = 'pending' AND latest_limited_live.approval_id IS NOT NULL THEN 'Review limited-live request, then sync execution gates after decision.'
        WHEN approval.status = 'pending' AND latest_strategy.approval_id IS NOT NULL THEN 'Use Strategy Committee decision workflow before any paper/live mode change.'
        WHEN approval.status = 'pending' AND latest_long_term.approval_id IS NOT NULL THEN 'Use Long-Term Committee workflow; capital action still requires a separate approval.'
        WHEN approval.status = 'pending' AND latest_special.approval_id IS NOT NULL THEN 'Use special-situation decision workflow; no trade is authorized from memo approval alone.'
        WHEN approval.status = 'pending' THEN 'Approve or reject after checking evidence and downside.'
        WHEN approval.status = 'approved' THEN 'Approved; verify linked workflow sync and execution guards before action.'
        WHEN approval.status = 'rejected' THEN 'Rejected; preserve rationale and close follow-up tasks.'
        ELSE 'Monitor approval state.'
    END AS recommended_next_action,
    CASE approval.risk_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END AS risk_rank,
    CASE approval.status
        WHEN 'pending' THEN 1
        WHEN 'approved' THEN 2
        WHEN 'rejected' THEN 3
        ELSE 4
    END AS status_rank,
    greatest(
        approval.created_at,
        coalesce(task.updated_at, 'epoch'::timestamptz),
        coalesce(latest_order.updated_at, 'epoch'::timestamptz),
        coalesce(latest_limited_live.updated_at, 'epoch'::timestamptz),
        coalesce(latest_strategy.updated_at, 'epoch'::timestamptz),
        coalesce(latest_long_term.updated_at, 'epoch'::timestamptz),
        coalesce(latest_special.updated_at, 'epoch'::timestamptz),
        coalesce(latest_tradingview.updated_at, 'epoch'::timestamptz),
        coalesce(gate_rollup.latest_gate_check_at, 'epoch'::timestamptz)
    ) AS latest_activity_at,
    jsonb_strip_nulls(jsonb_build_object(
        'approval', jsonb_build_object('table', 'agent.approvals', 'id', approval.id),
        'task', CASE WHEN task.id IS NOT NULL THEN jsonb_build_object('table', 'agent.tasks', 'id', task.id, 'status', task.status) END,
        'linked_source', CASE
            WHEN latest_order.approval_id IS NOT NULL THEN jsonb_build_object('table', 'trading.order_intents', 'id', latest_order.linked_record_id)
            WHEN latest_limited_live.approval_id IS NOT NULL THEN jsonb_build_object('table', 'trading.limited_live_requests', 'id', latest_limited_live.linked_record_id)
            WHEN latest_strategy.approval_id IS NOT NULL THEN jsonb_build_object('view', 'strategy.v_strategy_committee_queue', 'id', latest_strategy.linked_record_id)
            WHEN latest_long_term.approval_id IS NOT NULL THEN jsonb_build_object('view', 'portfolio.v_long_term_committee_queue', 'id', latest_long_term.linked_record_id)
            WHEN latest_special.approval_id IS NOT NULL THEN jsonb_build_object('view', 'research.v_special_situation_memos', 'id', latest_special.linked_record_id)
            WHEN latest_tradingview.approval_id IS NOT NULL THEN jsonb_build_object('view', 'ops.v_tradingview_alert_requests', 'tradingview_task_id', latest_tradingview.linked_record_id)
        END,
        'risk_events', coalesce(risk_rollup.risk_events, '[]'::jsonb),
        'gate_checks', coalesce(gate_rollup.gate_checks, '[]'::jsonb),
        'order', CASE WHEN latest_order.approval_id IS NOT NULL THEN jsonb_build_object(
            'side', latest_order.side,
            'quantity', latest_order.quantity,
            'notional', latest_order.notional,
            'estimated_loss', latest_order.estimated_loss
        ) END,
        'limited_live', CASE WHEN latest_limited_live.approval_id IS NOT NULL THEN jsonb_build_object(
            'max_notional', latest_limited_live.max_notional,
            'max_daily_loss', latest_limited_live.max_daily_loss,
            'expires_at', latest_limited_live.expires_at,
            'gate_requirements', latest_limited_live.gate_requirements
        ) END,
        'strategy', CASE WHEN latest_strategy.approval_id IS NOT NULL THEN jsonb_build_object(
            'recommended_decision', latest_strategy.recommended_decision,
            'proposed_mode', latest_strategy.proposed_mode,
            'memo_status', latest_strategy.memo_status,
            'memo_note_path', latest_strategy.memo_note_path,
            'risk_summary', latest_strategy.risk_summary
        ) END,
        'long_term', CASE WHEN latest_long_term.approval_id IS NOT NULL THEN jsonb_build_object(
            'company_name', latest_long_term.company_name,
            'thesis_title', latest_long_term.thesis_title,
            'recommended_decision', latest_long_term.recommended_decision,
            'memo_status', latest_long_term.memo_status,
            'memo_note_path', latest_long_term.memo_note_path,
            'source_gaps', latest_long_term.source_gaps,
            'capital_action_allowed', latest_long_term.capital_action_allowed
        ) END,
        'special_situation', CASE WHEN latest_special.approval_id IS NOT NULL THEN jsonb_build_object(
            'event_type', latest_special.event_type,
            'company_name', latest_special.company_name,
            'filing_title', latest_special.filing_title,
            'latest_spread_status', latest_special.latest_spread_status,
            'latest_gross_spread_pct', latest_special.latest_gross_spread_pct,
            'latest_decision', latest_special.latest_decision
        ) END,
        'tradingview', CASE WHEN latest_tradingview.approval_id IS NOT NULL THEN jsonb_build_object(
            'timeframe', latest_tradingview.timeframe,
            'chart_layout', latest_tradingview.chart_layout,
            'instruction', latest_tradingview.instruction,
            'alert_condition', latest_tradingview.alert_condition
        ) END
    )) AS evidence
FROM agent.approvals approval
LEFT JOIN agent.tasks task ON task.id = approval.task_id
LEFT JOIN latest_strategy ON latest_strategy.approval_id = approval.id
LEFT JOIN latest_long_term ON latest_long_term.approval_id = approval.id
LEFT JOIN latest_limited_live ON latest_limited_live.approval_id = approval.id
LEFT JOIN latest_order ON latest_order.approval_id = approval.id
LEFT JOIN latest_tradingview ON latest_tradingview.approval_id = approval.id
LEFT JOIN latest_special ON latest_special.approval_id = approval.id
LEFT JOIN risk_rollup ON risk_rollup.approval_id = approval.id
LEFT JOIN gate_rollup ON gate_rollup.approval_id = approval.id;

CREATE OR REPLACE VIEW agent.v_approval_board_summary AS
SELECT
    'total'::TEXT AS metric,
    count(*)::TEXT AS value,
    'All approval records visible to the unified board.'::TEXT AS interpretation
FROM agent.v_approval_board_items
UNION ALL
SELECT
    'pending',
    count(*) FILTER (WHERE approval_status = 'pending')::TEXT,
    'Approvals waiting for human decision.'
FROM agent.v_approval_board_items
UNION ALL
SELECT
    'high_or_critical_pending',
    count(*) FILTER (WHERE approval_status = 'pending' AND risk_level IN ('critical','high'))::TEXT,
    'High-risk pending decisions that should be reviewed first.'
FROM agent.v_approval_board_items
UNION ALL
SELECT
    'live_execution_allowed',
    count(*) FILTER (WHERE live_execution_allowed)::TEXT,
    'Linked approvals whose current read model reports live execution allowed.'
FROM agent.v_approval_board_items
UNION ALL
SELECT
    'broker_order_allowed',
    count(*) FILTER (WHERE broker_order_allowed)::TEXT,
    'Order approvals whose current order gate reports broker order allowed.'
FROM agent.v_approval_board_items;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_approval_board', 'mcp_tool', 'Risk Agent', 'read_only', true, 'Read the unified approval board across agent approvals, strategy committee, long-term committee, TradingView, special situations, limited-live, orders, risk events, and execution gates.', '{"reads":["agent.v_approval_board_items","agent.v_approval_board_summary"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
