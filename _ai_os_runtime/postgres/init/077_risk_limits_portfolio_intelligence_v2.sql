INSERT INTO books.book_risk_limits (
    book_key, limit_key, limit_name, limit_type, threshold_value, unit, severity
)
VALUES
    ('long_term', 'exit_criteria_zero', 'Exit Criteria Must Exist', 'quality_gate', 0, 'count', 'high'),
    ('long_term', 'review_due_zero', 'No Overdue Or Soon Reviews', 'quality_gate', 0, 'count', 'medium')
ON CONFLICT (book_key, limit_key) DO UPDATE SET
    limit_name = EXCLUDED.limit_name,
    limit_type = EXCLUDED.limit_type,
    threshold_value = EXCLUDED.threshold_value,
    unit = EXCLUDED.unit,
    severity = EXCLUDED.severity,
    enabled = true,
    updated_at = now();

CREATE OR REPLACE VIEW risk.v_portfolio_risk_limit_checks AS
WITH symbol_book_exposure AS (
    SELECT
        bp.client_id,
        bp.client_code,
        bp.client_name,
        bp.book_key,
        bp.book_name,
        bp.symbol,
        bp.exchange,
        count(*)::BIGINT AS position_count,
        coalesce(sum(bp.gross_exposure), 0) AS gross_exposure,
        coalesce(sum(bp.net_exposure), 0) AS net_exposure,
        max(bp.as_of) AS latest_as_of
    FROM books.v_book_positions bp
    WHERE bp.status = 'active'
    GROUP BY bp.client_id, bp.client_code, bp.client_name, bp.book_key, bp.book_name, bp.symbol, bp.exchange
),
client_book_totals AS (
    SELECT
        client_id,
        client_code,
        client_name,
        book_key,
        max(book_name) AS book_name,
        coalesce(sum(gross_exposure), 0) AS book_gross_exposure,
        coalesce(sum(net_exposure), 0) AS book_net_exposure
    FROM symbol_book_exposure
    GROUP BY client_id, client_code, client_name, book_key
),
client_totals AS (
    SELECT
        client_id,
        client_code,
        client_name,
        coalesce(sum(book_gross_exposure), 0) AS client_gross_exposure,
        coalesce(sum(book_net_exposure), 0) AS client_net_exposure
    FROM client_book_totals
    GROUP BY client_id, client_code, client_name
),
single_name_checks AS (
    SELECT
        brl.id AS limit_id,
        'books.book_risk_limits'::TEXT AS source_table,
        brl.book_key,
        sbe.book_name,
        sbe.client_id,
        sbe.client_code,
        sbe.client_name,
        sbe.symbol,
        sbe.exchange,
        'book_symbol'::TEXT AS scope_type,
        concat_ws(':', sbe.client_code, sbe.book_key, sbe.symbol) AS scope_ref,
        brl.limit_key,
        brl.limit_name,
        brl.limit_type,
        brl.threshold_value,
        brl.unit,
        brl.severity,
        round(CASE WHEN cbt.book_gross_exposure = 0 THEN 0 ELSE (sbe.gross_exposure / cbt.book_gross_exposure) * 100 END, 4) AS actual_value,
        sbe.gross_exposure AS exposure_value,
        cbt.book_gross_exposure AS denominator_value,
        sbe.latest_as_of,
        jsonb_build_object(
            'position_count', sbe.position_count,
            'gross_exposure', sbe.gross_exposure,
            'book_gross_exposure', cbt.book_gross_exposure,
            'net_exposure', sbe.net_exposure
        ) AS evidence
    FROM books.book_risk_limits brl
    JOIN symbol_book_exposure sbe ON sbe.book_key = brl.book_key
    JOIN client_book_totals cbt ON cbt.client_id IS NOT DISTINCT FROM sbe.client_id
        AND cbt.book_key = sbe.book_key
    WHERE brl.enabled
      AND brl.limit_type = 'single_name_pct'
),
quality_gate_mapping AS (
    SELECT 'missing_thesis_zero'::TEXT AS limit_key, 'thesis_needs_research'::TEXT AS gap_type
    UNION ALL SELECT 'exit_criteria_zero', 'exit_criteria_needs_review'
    UNION ALL SELECT 'review_due_zero', 'review_due_soon'
),
quality_gate_checks AS (
    SELECT
        brl.id AS limit_id,
        'books.book_risk_limits'::TEXT AS source_table,
        brl.book_key,
        ib.book_name,
        NULL::BIGINT AS client_id,
        NULL::TEXT AS client_code,
        NULL::TEXT AS client_name,
        NULL::TEXT AS symbol,
        NULL::TEXT AS exchange,
        'book_quality_gate'::TEXT AS scope_type,
        brl.book_key AS scope_ref,
        brl.limit_key,
        brl.limit_name,
        brl.limit_type,
        brl.threshold_value,
        brl.unit,
        brl.severity,
        count(gap.book_position_id)::NUMERIC AS actual_value,
        NULL::NUMERIC AS exposure_value,
        NULL::NUMERIC AS denominator_value,
        max(gap.as_of) AS latest_as_of,
        jsonb_build_object(
            'gap_type', qgm.gap_type,
            'gap_count', count(gap.book_position_id),
            'sample_symbols', coalesce(jsonb_agg(DISTINCT gap.symbol) FILTER (WHERE gap.symbol IS NOT NULL), '[]'::jsonb)
        ) AS evidence
    FROM books.book_risk_limits brl
    JOIN books.investment_books ib ON ib.book_key = brl.book_key
    JOIN quality_gate_mapping qgm ON qgm.limit_key = brl.limit_key
    LEFT JOIN books.v_book_assignment_gaps gap ON gap.book_key = brl.book_key
        AND gap.gap_type = qgm.gap_type
    WHERE brl.enabled
      AND brl.limit_type = 'quality_gate'
    GROUP BY brl.id, brl.book_key, ib.book_name, brl.limit_key, brl.limit_name,
             brl.limit_type, brl.threshold_value, brl.unit, brl.severity, qgm.gap_type
),
allocation_checks AS (
    SELECT
        NULL::BIGINT AS limit_id,
        'books.book_capital_allocations'::TEXT AS source_table,
        bca.book_key,
        ib.book_name,
        bca.client_id,
        c.client_code,
        c.display_name AS client_name,
        NULL::TEXT AS symbol,
        NULL::TEXT AS exchange,
        'client_book_allocation'::TEXT AS scope_type,
        concat_ws(':', c.client_code, bca.book_key, allocation_side.side) AS scope_ref,
        ('allocation_' || allocation_side.side || '_pct')::TEXT AS limit_key,
        CASE allocation_side.side
            WHEN 'max' THEN 'Client Book Max Allocation'
            ELSE 'Client Book Min Allocation'
        END AS limit_name,
        ('allocation_' || allocation_side.side || '_pct')::TEXT AS limit_type,
        CASE allocation_side.side
            WHEN 'max' THEN bca.max_pct
            ELSE bca.min_pct
        END AS threshold_value,
        'pct'::TEXT AS unit,
        CASE allocation_side.side WHEN 'max' THEN 'high' ELSE 'medium' END AS severity,
        round(CASE WHEN ct.client_gross_exposure = 0 THEN 0 ELSE (coalesce(cbt.book_gross_exposure, 0) / ct.client_gross_exposure) * 100 END, 4) AS actual_value,
        coalesce(cbt.book_gross_exposure, 0) AS exposure_value,
        ct.client_gross_exposure AS denominator_value,
        NULL::TIMESTAMPTZ AS latest_as_of,
        jsonb_build_object(
            'target_pct', bca.target_pct,
            'min_pct', bca.min_pct,
            'max_pct', bca.max_pct,
            'book_gross_exposure', coalesce(cbt.book_gross_exposure, 0),
            'client_gross_exposure', ct.client_gross_exposure
        ) AS evidence
    FROM books.book_capital_allocations bca
    JOIN portfolio.clients c ON c.id = bca.client_id
    JOIN books.investment_books ib ON ib.book_key = bca.book_key
    JOIN client_totals ct ON ct.client_id = bca.client_id
    LEFT JOIN client_book_totals cbt ON cbt.client_id = bca.client_id
        AND cbt.book_key = bca.book_key
    CROSS JOIN (VALUES ('max'), ('min')) AS allocation_side(side)
    WHERE bca.status = 'active'
      AND (
          (allocation_side.side = 'max' AND bca.max_pct IS NOT NULL)
          OR (allocation_side.side = 'min' AND bca.min_pct IS NOT NULL)
      )
),
combined AS (
    SELECT * FROM single_name_checks
    UNION ALL
    SELECT * FROM quality_gate_checks
    UNION ALL
    SELECT * FROM allocation_checks
)
SELECT
    md5(concat_ws('|', source_table, coalesce(limit_id::TEXT, ''), scope_type, scope_ref, limit_key)) AS check_key,
    limit_id,
    source_table,
    book_key,
    book_name,
    client_id,
    client_code,
    client_name,
    symbol,
    exchange,
    scope_type,
    scope_ref,
    limit_key,
    limit_name,
    limit_type,
    threshold_value,
    unit,
    severity,
    actual_value,
    exposure_value,
    denominator_value,
    round(CASE WHEN threshold_value IS NULL OR threshold_value = 0 THEN NULL ELSE (actual_value / threshold_value) * 100 END, 2) AS utilization_pct,
    CASE
        WHEN limit_type IN ('single_name_pct', 'allocation_max_pct') AND actual_value > threshold_value THEN 'breach'
        WHEN limit_type = 'allocation_min_pct' AND actual_value < threshold_value THEN 'breach'
        WHEN limit_type = 'quality_gate' AND actual_value > threshold_value THEN 'breach'
        WHEN limit_type = 'single_name_pct' AND actual_value >= threshold_value * 0.8 THEN 'warning'
        WHEN limit_type = 'allocation_max_pct' AND actual_value >= threshold_value * 0.9 THEN 'warning'
        ELSE 'ok'
    END AS check_status,
    CASE
        WHEN limit_type = 'single_name_pct' THEN coalesce(symbol, 'symbol') || ' is ' || round(actual_value, 2)::TEXT || '% of ' || book_name || ' for ' || coalesce(client_name, client_code, 'client')
        WHEN limit_type = 'quality_gate' THEN limit_name || ' has ' || actual_value::TEXT || ' open rows in ' || book_name
        WHEN limit_type LIKE 'allocation_%' THEN coalesce(client_name, client_code, 'Client') || ' ' || book_name || ' allocation is ' || round(actual_value, 2)::TEXT || '%'
        ELSE limit_name
    END AS check_message,
    CASE
        WHEN limit_type = 'single_name_pct' THEN 'Risk Agent should review concentration before add/buy actions in this book.'
        WHEN limit_type = 'quality_gate' THEN 'Route to Portfolio Manager / Research Analyst to close thesis, exit, or review gaps.'
        WHEN limit_type LIKE 'allocation_%' THEN 'Portfolio Manager should verify allocation intent and rebalance only after approval.'
        ELSE 'Review risk limit.'
    END AS recommended_action,
    latest_as_of,
    evidence
FROM combined;

CREATE OR REPLACE VIEW risk.v_portfolio_risk_dashboard_summary AS
SELECT 'risk_limit_checks' AS metric, count(*)::TEXT AS value, 'Total evaluated portfolio risk limit checks' AS interpretation
FROM risk.v_portfolio_risk_limit_checks
UNION ALL
SELECT 'risk_limit_breaches', count(*)::TEXT, 'Current breached risk limits'
FROM risk.v_portfolio_risk_limit_checks
WHERE check_status = 'breach'
UNION ALL
SELECT 'risk_limit_warnings', count(*)::TEXT, 'Current warning-level risk limits'
FROM risk.v_portfolio_risk_limit_checks
WHERE check_status = 'warning'
UNION ALL
SELECT 'critical_breaches', count(*)::TEXT, 'Critical breached checks requiring Risk Agent review'
FROM risk.v_portfolio_risk_limit_checks
WHERE check_status = 'breach' AND severity = 'critical'
UNION ALL
SELECT 'open_risk_events', count(*)::TEXT, 'Open risk.events rows'
FROM risk.events
WHERE status IN ('new', 'acknowledged')
UNION ALL
SELECT 'portfolio_assignment_gaps', count(*)::TEXT, 'Book-assignment gaps feeding risk quality gates'
FROM books.v_book_assignment_gaps;

CREATE OR REPLACE VIEW books.v_portfolio_intelligence_v2 AS
SELECT
    'portfolio_overview'::TEXT AS section,
    'gross_book_exposure'::TEXT AS item_key,
    'Gross Book Exposure'::TEXT AS item_name,
    round(coalesce(sum(gross_exposure), 0), 2)::TEXT AS item_value,
    'Gross exposure across active book positions.'::TEXT AS interpretation,
    jsonb_build_object('source', 'books.book_positions') AS payload
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT
    'portfolio_overview',
    'net_book_exposure',
    'Net Book Exposure',
    round(coalesce(sum(net_exposure), 0), 2)::TEXT,
    'Net exposure across active book positions.',
    jsonb_build_object('source', 'books.book_positions')
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT
    'risk',
    'risk_limit_breaches',
    'Risk Limit Breaches',
    count(*)::TEXT,
    'Breached checks from risk.v_portfolio_risk_limit_checks.',
    jsonb_build_object('source', 'risk.v_portfolio_risk_limit_checks')
FROM risk.v_portfolio_risk_limit_checks
WHERE check_status = 'breach'
UNION ALL
SELECT
    'risk',
    'critical_breaches',
    'Critical Breaches',
    count(*)::TEXT,
    'Critical breached checks requiring independent risk review.',
    jsonb_build_object('source', 'risk.v_portfolio_risk_limit_checks')
FROM risk.v_portfolio_risk_limit_checks
WHERE check_status = 'breach' AND severity = 'critical'
UNION ALL
SELECT
    'concentration',
    'top_symbol_concentration',
    coalesce(symbol, 'No symbols'),
    coalesce(round(actual_value, 2)::TEXT || '%', '0%'),
    coalesce(check_message, 'No single-name checks available.'),
    evidence || jsonb_build_object('source', 'risk.v_portfolio_risk_limit_checks')
FROM risk.v_portfolio_risk_limit_checks
WHERE limit_type = 'single_name_pct'
ORDER BY section, item_key;

CREATE OR REPLACE FUNCTION risk.refresh_portfolio_risk_events(p_actor TEXT DEFAULT 'Risk Agent')
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_inserted BIGINT := 0;
BEGIN
    INSERT INTO risk.events (
        limit_id, scope_type, scope_ref, severity, status, title, message, evidence
    )
    SELECT
        NULL,
        check_row.scope_type,
        check_row.scope_ref,
        check_row.severity,
        'new',
        check_row.limit_name || ' breach',
        check_row.check_message || ' Recommended action: ' || check_row.recommended_action,
        jsonb_build_array(
            check_row.evidence || jsonb_build_object(
                'check_key', check_row.check_key,
                'source_limit_id', check_row.limit_id,
                'source_limit_table', check_row.source_table,
                'limit_key', check_row.limit_key,
                'actual_value', check_row.actual_value,
                'threshold_value', check_row.threshold_value,
                'check_status', check_row.check_status,
                'refreshed_by', p_actor
            )
        )
    FROM risk.v_portfolio_risk_limit_checks check_row
    WHERE check_row.check_status = 'breach'
      AND NOT EXISTS (
          SELECT 1
          FROM risk.events existing
          WHERE existing.status IN ('new', 'acknowledged')
            AND existing.scope_type IS NOT DISTINCT FROM check_row.scope_type
            AND existing.scope_ref IS NOT DISTINCT FROM check_row.scope_ref
            AND existing.title = check_row.limit_name || ' breach'
      );

    GET DIAGNOSTICS v_inserted = ROW_COUNT;

    RETURN jsonb_build_object(
        'inserted_events', v_inserted,
        'breach_count', (SELECT count(*) FROM risk.v_portfolio_risk_limit_checks WHERE check_status = 'breach'),
        'warning_count', (SELECT count(*) FROM risk.v_portfolio_risk_limit_checks WHERE check_status = 'warning'),
        'refreshed_by', p_actor,
        'refreshed_at', now(),
        'live_execution_allowed', false
    );
END;
$$;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_portfolio_risk_limit_checks', 'mcp_tool', 'Risk Agent', 'read_only', true, 'Read current portfolio risk limit checks across books, clients, symbols, and allocations.', '{"reads":["risk.v_portfolio_risk_limit_checks","risk.v_portfolio_risk_dashboard_summary"]}'::jsonb),
    ('ai_os_refresh_portfolio_risk_events', 'mcp_tool', 'Risk Agent', 'write_with_approval', true, 'Materialize current breached portfolio risk limit checks into risk.events without duplicate open events.', '{"function":"risk.refresh_portfolio_risk_events","writes":["risk.events"],"reads":["risk.v_portfolio_risk_limit_checks"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_portfolio_intelligence_v2', 'mcp_tool', 'Portfolio Manager', 'read_only', true, 'Read Portfolio Intelligence v2 summary with exposure, concentration, and risk metrics.', '{"reads":["books.v_portfolio_intelligence_v2","risk.v_portfolio_risk_limit_checks"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET
    warehouse_objects = (
        SELECT ARRAY(
            SELECT DISTINCT item
            FROM unnest(warehouse_objects || ARRAY['risk.v_portfolio_risk_limit_checks','risk.v_portfolio_risk_dashboard_summary','books.v_portfolio_intelligence_v2']::TEXT[]) AS item
            ORDER BY item
        )
    ),
    mcp_tools = (
        SELECT ARRAY(
            SELECT DISTINCT item
            FROM unnest(mcp_tools || ARRAY['ai_os_portfolio_risk_limit_checks','ai_os_refresh_portfolio_risk_events','ai_os_portfolio_intelligence_v2']::TEXT[]) AS item
            ORDER BY item
        )
    ),
    next_action = 'Use live portfolio risk checks before strategy activation, sizing, rebalancing, or client-facing recommendation.',
    updated_at = now()
WHERE module_key IN ('portfolio_office', 'risk_office', 'agent_office');
