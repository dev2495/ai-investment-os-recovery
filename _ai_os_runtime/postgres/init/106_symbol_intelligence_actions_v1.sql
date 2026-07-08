CREATE TABLE IF NOT EXISTS portfolio.symbol_intelligence_actions (
    id BIGSERIAL PRIMARY KEY,
    action_key TEXT UNIQUE NOT NULL,
    client_code TEXT,
    client_name TEXT,
    symbol TEXT NOT NULL,
    exchange TEXT,
    action_type TEXT NOT NULL,
    action_status TEXT NOT NULL DEFAULT 'task_created',
    owner_agent TEXT NOT NULL,
    target_workspace TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'high',
    task_id BIGINT REFERENCES agent.tasks(id),
    inbox_id BIGINT REFERENCES agent.inbox_items(id),
    source_view TEXT NOT NULL DEFAULT 'portfolio.v_symbol_intelligence_v2',
    decision_state TEXT,
    recommended_action TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_symbol_intelligence_actions_symbol
    ON portfolio.symbol_intelligence_actions (symbol, exchange, action_type, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_symbol_intelligence_actions_owner
    ON portfolio.symbol_intelligence_actions (owner_agent, action_status, created_at DESC);

CREATE OR REPLACE FUNCTION portfolio.route_symbol_intelligence_action(
    p_client_code TEXT,
    p_symbol TEXT,
    p_exchange TEXT DEFAULT 'NSE',
    p_action_type TEXT DEFAULT 'refresh_thesis',
    p_actor TEXT DEFAULT 'Charlie Munger',
    p_notes TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    symbol_row RECORD;
    action_day TEXT := to_char(now() AT TIME ZONE 'UTC', 'YYYYMMDD');
    clean_symbol TEXT := upper(NULLIF(trim(p_symbol), ''));
    clean_exchange TEXT := upper(COALESCE(NULLIF(trim(p_exchange), ''), 'NSE'));
    clean_action TEXT := lower(COALESCE(NULLIF(trim(p_action_type), ''), 'refresh_thesis'));
    action_key_value TEXT;
    owner_value TEXT;
    workspace_value TEXT;
    priority_value TEXT;
    title_value TEXT;
    objective_value TEXT;
    recommended_value TEXT;
    task_row RECORD;
    inbox_row RECORD;
    action_row RECORD;
BEGIN
    IF clean_symbol IS NULL THEN
        RAISE EXCEPTION 'symbol is required';
    END IF;

    SELECT *
    INTO symbol_row
    FROM portfolio.v_symbol_intelligence_v2
    WHERE symbol = clean_symbol
      AND exchange IS NOT DISTINCT FROM clean_exchange
      AND (p_client_code IS NULL OR p_client_code = '' OR client_code = p_client_code)
    ORDER BY v2_priority_rank, gross_exposure DESC NULLS LAST
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'symbol intelligence row not found for %.%', clean_exchange, clean_symbol;
    END IF;

    action_key_value := concat_ws(':', 'symbol-action', COALESCE(symbol_row.client_code, 'portfolio'), clean_exchange, clean_symbol, clean_action, action_day);

    owner_value := CASE clean_action
        WHEN 'refresh_thesis' THEN 'Long-Term Portfolio Manager'
        WHEN 'review_exit_criteria' THEN 'Long-Term Portfolio Manager'
        WHEN 'route_risk_review' THEN 'Chief Risk Officer'
        WHEN 'route_research_update' THEN 'Research Director'
        WHEN 'route_quant_review' THEN 'Strategy Research Agent'
        WHEN 'route_trading_review' THEN 'Trading Desk Agent'
        WHEN 'request_committee_review' THEN 'Strategy Committee Secretary'
        WHEN 'prepare_tradingview' THEN 'Trading Desk Agent'
        ELSE 'Jarvis'
    END;

    workspace_value := CASE clean_action
        WHEN 'refresh_thesis' THEN 'long_term'
        WHEN 'review_exit_criteria' THEN 'long_term'
        WHEN 'route_risk_review' THEN 'risk'
        WHEN 'route_research_update' THEN 'research'
        WHEN 'route_quant_review' THEN 'quant'
        WHEN 'route_trading_review' THEN 'trading'
        WHEN 'request_committee_review' THEN 'committee'
        WHEN 'prepare_tradingview' THEN 'trading'
        ELSE 'command'
    END;

    priority_value := CASE
        WHEN clean_action = 'route_risk_review' OR COALESCE(symbol_row.risk_breach_count, 0) > 0 THEN 'critical'
        WHEN COALESCE(symbol_row.critical_remediation_count, 0) > 0 THEN 'high'
        ELSE 'normal'
    END;

    title_value := CASE clean_action
        WHEN 'refresh_thesis' THEN 'Refresh thesis from Symbol Intelligence: ' || clean_symbol
        WHEN 'review_exit_criteria' THEN 'Review exit criteria from Symbol Intelligence: ' || clean_symbol
        WHEN 'route_risk_review' THEN 'Risk review from Symbol Intelligence: ' || clean_symbol
        WHEN 'route_research_update' THEN 'Research update from Symbol Intelligence: ' || clean_symbol
        WHEN 'route_quant_review' THEN 'Quant review from Symbol Intelligence: ' || clean_symbol
        WHEN 'route_trading_review' THEN 'Trading setup review from Symbol Intelligence: ' || clean_symbol
        WHEN 'request_committee_review' THEN 'Committee review request from Symbol Intelligence: ' || clean_symbol
        WHEN 'prepare_tradingview' THEN 'Prepare TradingView workflow from Symbol Intelligence: ' || clean_symbol
        ELSE 'Symbol Intelligence action: ' || clean_symbol
    END;

    objective_value := CASE clean_action
        WHEN 'refresh_thesis' THEN 'Use the Symbol Intelligence v2 packet to refresh the long-term thesis, attach latest evidence, and keep capital action blocked until thesis is source-backed.'
        WHEN 'review_exit_criteria' THEN 'Use the Symbol Intelligence v2 packet to review and activate explicit exit criteria for the current book position.'
        WHEN 'route_risk_review' THEN 'Review risk breaches, warnings, concentration, and book exposure before any add, trim, hedge, or trade action.'
        WHEN 'route_research_update' THEN 'Review latest filing/news/catalyst evidence and update the research packet or special-situation workflow.'
        WHEN 'route_quant_review' THEN 'Review linked strategy candidates/dossiers and decide whether to route to paper-only Quant Lab testing.'
        WHEN 'route_trading_review' THEN 'Review active trading setup, signals, chart evidence needs, and paper/manual trade journal requirements.'
        WHEN 'request_committee_review' THEN 'Prepare committee evidence packet from Symbol Intelligence v2 and route to the right committee without approving live action.'
        WHEN 'prepare_tradingview' THEN 'Prepare TradingView chart/snapshot workflow request for this symbol; do not change alerts or orders without approval.'
        ELSE 'Review Symbol Intelligence v2 packet and propose the next safe action.'
    END;

    recommended_value := CASE clean_action
        WHEN 'refresh_thesis' THEN 'Refresh thesis and dispatch long-term specialists if source coverage is incomplete.'
        WHEN 'review_exit_criteria' THEN 'Activate or revise exit criteria, thesis killers, review cadence, and monitoring variables.'
        WHEN 'route_risk_review' THEN COALESCE((symbol_row.risk_items -> 0 ->> 'recommended_action'), 'Risk Office should review exposure before capital action.')
        WHEN 'route_research_update' THEN 'Research Factory should process latest filing/news/catalyst evidence and write back to Obsidian.'
        WHEN 'route_quant_review' THEN 'Quant Lab should evaluate linked candidates/dossiers for paper-only testing.'
        WHEN 'route_trading_review' THEN 'Trading Desk should review setup and journal requirements before any manual/paper trade.'
        WHEN 'request_committee_review' THEN 'Committee Secretary should prepare evidence packet, dissent, and follow-up actions.'
        WHEN 'prepare_tradingview' THEN 'Prepare chart/snapshot workflow; TradingView CDP must be available before execution.'
        ELSE symbol_row.v2_recommended_next_action
    END;

    INSERT INTO portfolio.symbol_intelligence_actions (
        action_key, client_code, client_name, symbol, exchange, action_type,
        owner_agent, target_workspace, priority, decision_state,
        recommended_action, evidence, notes, created_by, updated_at
    )
    VALUES (
        action_key_value, symbol_row.client_code, symbol_row.client_name, clean_symbol,
        clean_exchange, clean_action, owner_value, workspace_value, priority_value,
        symbol_row.v2_decision_state, recommended_value,
        jsonb_build_array(
            jsonb_build_object('view', 'portfolio.v_symbol_intelligence_v2'),
            jsonb_build_object('client_code', symbol_row.client_code, 'symbol', clean_symbol, 'exchange', clean_exchange),
            jsonb_build_object('v2_decision_state', symbol_row.v2_decision_state, 'flags', symbol_row.v2_decision_flags),
            jsonb_build_object('risk_breach_count', symbol_row.risk_breach_count, 'critical_remediation_count', symbol_row.critical_remediation_count),
            jsonb_build_object('decision_packet', symbol_row.v2_decision_packet)
        ),
        p_notes,
        p_actor,
        now()
    )
    ON CONFLICT (action_key) DO UPDATE
    SET action_status = CASE
            WHEN portfolio.symbol_intelligence_actions.task_id IS NOT NULL THEN portfolio.symbol_intelligence_actions.action_status
            ELSE EXCLUDED.action_status
        END,
        owner_agent = EXCLUDED.owner_agent,
        target_workspace = EXCLUDED.target_workspace,
        priority = EXCLUDED.priority,
        decision_state = EXCLUDED.decision_state,
        recommended_action = EXCLUDED.recommended_action,
        evidence = EXCLUDED.evidence,
        notes = COALESCE(EXCLUDED.notes, portfolio.symbol_intelligence_actions.notes),
        updated_at = now()
    RETURNING * INTO action_row;

    IF action_row.task_id IS NULL THEN
        INSERT INTO agent.tasks (
            title, objective, owner_agent, status, priority, approval_required,
            source_kind, source_ref, output_format, evidence
        )
        VALUES (
            title_value, objective_value, owner_value, 'queued', priority_value,
            clean_action IN ('route_risk_review', 'request_committee_review'),
            'symbol_intelligence_action', action_key_value, 'symbol_action',
            action_row.evidence
        )
        RETURNING * INTO task_row;

        INSERT INTO agent.inbox_items (
            task_id, title, owner_agent, status, priority, recommended_action,
            evidence, target_workspace
        )
        VALUES (
            task_row.id, title_value, owner_value, 'queued', priority_value,
            recommended_value, action_row.evidence, workspace_value
        )
        RETURNING * INTO inbox_row;

        UPDATE portfolio.symbol_intelligence_actions
        SET task_id = task_row.id,
            inbox_id = inbox_row.id,
            action_status = 'task_created',
            updated_at = now()
        WHERE id = action_row.id
        RETURNING * INTO action_row;
    END IF;

    RETURN jsonb_build_object(
        'status', 'ok',
        'action_id', action_row.id,
        'action_key', action_row.action_key,
        'action_type', action_row.action_type,
        'client_code', action_row.client_code,
        'symbol', action_row.symbol,
        'exchange', action_row.exchange,
        'owner_agent', action_row.owner_agent,
        'target_workspace', action_row.target_workspace,
        'priority', action_row.priority,
        'task_id', action_row.task_id,
        'inbox_id', action_row.inbox_id,
        'recommended_action', action_row.recommended_action
    );
END;
$$;

CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence_actions AS
SELECT
    action.id,
    action.action_key,
    action.client_code,
    action.client_name,
    action.symbol,
    action.exchange,
    action.action_type,
    action.action_status,
    action.owner_agent,
    action.target_workspace,
    action.priority,
    action.task_id,
    task.status AS task_status,
    action.inbox_id,
    inbox.status AS inbox_status,
    action.decision_state,
    action.recommended_action,
    action.evidence,
    action.notes,
    action.created_by,
    action.created_at,
    action.updated_at
FROM portfolio.symbol_intelligence_actions action
LEFT JOIN agent.tasks task ON task.id = action.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = action.inbox_id;

CREATE OR REPLACE VIEW portfolio.v_symbol_intelligence_action_summary AS
SELECT 'total_actions' AS metric, count(*)::text AS value, 'Symbol Intelligence actions routed into agent work' AS interpretation
FROM portfolio.symbol_intelligence_actions
UNION ALL
SELECT 'open_tasks', count(*)::text, 'Symbol Intelligence actions with queued, active, or blocked tasks'
FROM portfolio.v_symbol_intelligence_actions
WHERE task_status IN ('queued', 'in_progress', 'blocked') OR task_status IS NULL
UNION ALL
SELECT 'critical_actions', count(*)::text, 'Critical Symbol Intelligence actions'
FROM portfolio.symbol_intelligence_actions
WHERE priority = 'critical'
UNION ALL
SELECT 'distinct_symbols', count(DISTINCT symbol)::text, 'Distinct symbols with routed Symbol Intelligence actions'
FROM portfolio.symbol_intelligence_actions;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    (
        'ai_os_route_symbol_intelligence_action',
        'mcp_tool',
        'Charlie Munger',
        'write_with_approval',
        true,
        'Route a Symbol Intelligence v2 row into the correct agent task and inbox workflow.',
        '{"function":"portfolio.route_symbol_intelligence_action","writes":["portfolio.symbol_intelligence_actions","agent.tasks","agent.inbox_items"],"reads":["portfolio.v_symbol_intelligence_v2"],"live_execution_allowed":false}'::jsonb
    ),
    (
        'ai_os_symbol_intelligence_actions',
        'mcp_tool',
        'Jarvis',
        'read_only',
        true,
        'Read Symbol Intelligence actions routed into agent tasks and inboxes.',
        '{"reads":["portfolio.v_symbol_intelligence_actions","portfolio.v_symbol_intelligence_action_summary"],"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE
SET tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
