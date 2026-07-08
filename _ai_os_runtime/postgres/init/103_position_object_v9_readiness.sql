ALTER TABLE books.book_positions
    ADD COLUMN IF NOT EXISTS entry_date DATE,
    ADD COLUMN IF NOT EXISTS entry_rationale TEXT,
    ADD COLUMN IF NOT EXISTS source_kind TEXT,
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS source_freshness_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS approval_state TEXT NOT NULL DEFAULT 'needs_review',
    ADD COLUMN IF NOT EXISTS approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS risk_budget_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS capital_budget_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS stop_price NUMERIC,
    ADD COLUMN IF NOT EXISTS target_price NUMERIC,
    ADD COLUMN IF NOT EXISTS time_exit_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS linked_research_note_path TEXT,
    ADD COLUMN IF NOT EXISTS linked_committee_review_key TEXT,
    ADD COLUMN IF NOT EXISTS linked_trade_journal_ref TEXT,
    ADD COLUMN IF NOT EXISTS hedge_group_key TEXT,
    ADD COLUMN IF NOT EXISTS hedge_intent TEXT,
    ADD COLUMN IF NOT EXISTS linked_hedged_position_id BIGINT REFERENCES books.book_positions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS offset_intent TEXT NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS review_state TEXT NOT NULL DEFAULT 'needs_review',
    ADD COLUMN IF NOT EXISTS v9_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_book_positions_v9_approval ON books.book_positions(approval_state, review_state);
CREATE INDEX IF NOT EXISTS idx_book_positions_v9_offset ON books.book_positions(symbol, offset_intent);
CREATE INDEX IF NOT EXISTS idx_book_positions_v9_hedge ON books.book_positions(hedge_group_key) WHERE hedge_group_key IS NOT NULL;

UPDATE books.book_positions
SET
    entry_date = coalesce(entry_date, as_of::DATE, created_at::DATE),
    entry_rationale = coalesce(nullif(entry_rationale, ''), thesis, 'Migrated position; entry rationale requires review from broker history, trade journal, or research note.'),
    source_kind = coalesce(nullif(source_kind, ''), CASE WHEN source_position_id IS NOT NULL THEN 'portfolio_position' WHEN source_trade_id IS NOT NULL THEN 'trade_activity' ELSE 'manual_or_legacy' END),
    source_ref = coalesce(nullif(source_ref, ''), coalesce(source_position_id::TEXT, source_trade_id::TEXT, id::TEXT)),
    source_freshness_at = coalesce(source_freshness_at, as_of, updated_at, created_at),
    approval_state = CASE
        WHEN approval_id IS NOT NULL THEN 'approval_linked'
        WHEN book_key IN ('active_trading', 'quant', 'tactical', 'hedges') THEN 'needs_approval'
        ELSE approval_state
    END,
    review_state = CASE
        WHEN review_state <> 'needs_review' THEN review_state
        WHEN book_key = 'long_term' THEN 'thesis_review_required'
        WHEN book_key IN ('active_trading', 'quant') THEN 'risk_review_required'
        WHEN book_key = 'hedges' THEN 'hedge_review_required'
        ELSE review_state
    END,
    risk_budget_pct = coalesce(risk_budget_pct, CASE
        WHEN book_key = 'long_term' THEN 100
        WHEN book_key = 'tactical' THEN 25
        WHEN book_key = 'quant' THEN 20
        WHEN book_key = 'active_trading' THEN 10
        WHEN book_key = 'hedges' THEN 20
        ELSE NULL
    END),
    capital_budget_pct = coalesce(capital_budget_pct, CASE
        WHEN book_key = 'long_term' THEN 80
        WHEN book_key = 'tactical' THEN 10
        WHEN book_key = 'quant' THEN 5
        WHEN book_key = 'active_trading' THEN 3
        WHEN book_key = 'cash_treasury' THEN 2
        ELSE NULL
    END),
    offset_intent = CASE
        WHEN offset_intent <> 'unknown' THEN offset_intent
        WHEN book_key = 'hedges' THEN 'hedge'
        WHEN book_key = 'tactical' AND purpose_key = 'hedge_around_core' THEN 'hedge'
        WHEN book_key IN ('quant', 'active_trading', 'tactical') THEN 'independent_alpha'
        ELSE offset_intent
    END,
    v9_metadata = v9_metadata || jsonb_build_object(
        'position_object_v9_backfilled_at', now(),
        'backfill_source', '103_position_object_v9_readiness.sql'
    )
WHERE status = 'active';

DROP VIEW IF EXISTS books.v_cross_book_coordination_questions;
DROP VIEW IF EXISTS books.v_position_object_gap_summary;
DROP VIEW IF EXISTS books.v_position_objects_v9;

CREATE OR REPLACE VIEW books.v_position_objects_v9 AS
WITH thesis_status AS (
    SELECT
        book_position_id,
        count(*) AS thesis_count,
        bool_or(thesis_status IN ('approved', 'active')) AS has_active_thesis,
        min(review_due_at) AS next_review_due_at
    FROM books.position_theses
    GROUP BY book_position_id
),
exit_status AS (
    SELECT
        book_position_id,
        count(*) AS exit_count,
        bool_or(status = 'active') AS has_active_exit
    FROM books.exit_criteria
    GROUP BY book_position_id
),
base AS (
    SELECT
        bp.id AS book_position_id,
        bp.source_position_id,
        bp.source_trade_id,
        bp.client_id,
        c.client_code,
        c.display_name AS client_name,
        bp.account_id,
        a.account_code,
        a.broker,
        bp.symbol,
        bp.exchange,
        bp.instrument_type,
        bp.book_key,
        ib.book_name,
        ib.book_type,
        bp.purpose_key,
        pp.purpose_name,
        pp.purpose_family,
        bp.owner_agent,
        bp.strategy_key,
        bp.direction,
        bp.quantity,
        bp.average_price,
        bp.market_price,
        bp.market_value,
        bp.gross_exposure,
        bp.net_exposure,
        bp.time_horizon,
        bp.thesis,
        bp.exit_criteria,
        bp.review_frequency,
        bp.entry_date,
        bp.entry_rationale,
        bp.source_kind,
        bp.source_ref,
        bp.source_freshness_at,
        bp.approval_state,
        bp.approval_id,
        bp.risk_budget_pct,
        bp.capital_budget_pct,
        bp.stop_price,
        bp.target_price,
        bp.time_exit_at,
        bp.linked_research_note_path,
        bp.linked_committee_review_key,
        bp.linked_trade_journal_ref,
        bp.hedge_group_key,
        bp.hedge_intent,
        bp.linked_hedged_position_id,
        bp.offset_intent,
        bp.review_state,
        bp.status,
        bp.as_of,
        bp.updated_at,
        coalesce(ts.thesis_count, 0) AS thesis_count,
        coalesce(ts.has_active_thesis, false) AS has_active_thesis,
        ts.next_review_due_at,
        coalesce(es.exit_count, 0) AS exit_count,
        coalesce(es.has_active_exit, false) AS has_active_exit
    FROM books.book_positions bp
    JOIN books.investment_books ib ON ib.book_key = bp.book_key
    LEFT JOIN books.position_purposes pp ON pp.purpose_key = bp.purpose_key
    LEFT JOIN portfolio.clients c ON c.id = bp.client_id
    LEFT JOIN portfolio.accounts a ON a.id = bp.account_id
    LEFT JOIN thesis_status ts ON ts.book_position_id = bp.id
    LEFT JOIN exit_status es ON es.book_position_id = bp.id
)
SELECT
    base.*,
    array_remove(ARRAY[
        CASE WHEN purpose_key IS NULL THEN 'missing_purpose' END,
        CASE WHEN nullif(thesis, '') IS NULL THEN 'missing_thesis_text' END,
        CASE WHEN book_key = 'long_term' AND NOT has_active_thesis THEN 'long_term_thesis_not_active' END,
        CASE WHEN nullif(exit_criteria, '') IS NULL THEN 'missing_exit_criteria_text' END,
        CASE WHEN NOT has_active_exit THEN 'exit_criteria_not_active' END,
        CASE WHEN entry_date IS NULL THEN 'missing_entry_date' END,
        CASE WHEN nullif(entry_rationale, '') IS NULL THEN 'missing_entry_rationale' END,
        CASE WHEN nullif(source_kind, '') IS NULL OR nullif(source_ref, '') IS NULL THEN 'missing_source_lineage' END,
        CASE WHEN source_freshness_at IS NULL THEN 'missing_source_freshness' END,
        CASE WHEN nullif(owner_agent, '') IS NULL THEN 'missing_owner' END,
        CASE WHEN nullif(time_horizon, '') IS NULL THEN 'missing_time_horizon' END,
        CASE WHEN approval_state IN ('needs_review', 'needs_approval') AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'approval_not_linked' END,
        CASE WHEN book_key IN ('tactical', 'active_trading') AND stop_price IS NULL AND target_price IS NULL AND time_exit_at IS NULL THEN 'missing_stop_target_or_time_exit' END,
        CASE WHEN book_key = 'hedges' AND nullif(hedge_intent, '') IS NULL THEN 'missing_hedge_intent' END,
        CASE WHEN book_key = 'hedges' AND linked_hedged_position_id IS NULL THEN 'missing_linked_hedged_position' END,
        CASE WHEN offset_intent = 'unknown' AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'unknown_offset_intent' END,
        CASE WHEN risk_budget_pct IS NULL THEN 'missing_risk_budget' END,
        CASE WHEN capital_budget_pct IS NULL THEN 'missing_capital_budget' END,
        CASE WHEN next_review_due_at IS NOT NULL AND next_review_due_at <= now() THEN 'review_overdue' END
    ], NULL) AS v9_gap_types,
    cardinality(array_remove(ARRAY[
        CASE WHEN purpose_key IS NULL THEN 'missing_purpose' END,
        CASE WHEN nullif(thesis, '') IS NULL THEN 'missing_thesis_text' END,
        CASE WHEN book_key = 'long_term' AND NOT has_active_thesis THEN 'long_term_thesis_not_active' END,
        CASE WHEN nullif(exit_criteria, '') IS NULL THEN 'missing_exit_criteria_text' END,
        CASE WHEN NOT has_active_exit THEN 'exit_criteria_not_active' END,
        CASE WHEN entry_date IS NULL THEN 'missing_entry_date' END,
        CASE WHEN nullif(entry_rationale, '') IS NULL THEN 'missing_entry_rationale' END,
        CASE WHEN nullif(source_kind, '') IS NULL OR nullif(source_ref, '') IS NULL THEN 'missing_source_lineage' END,
        CASE WHEN source_freshness_at IS NULL THEN 'missing_source_freshness' END,
        CASE WHEN nullif(owner_agent, '') IS NULL THEN 'missing_owner' END,
        CASE WHEN nullif(time_horizon, '') IS NULL THEN 'missing_time_horizon' END,
        CASE WHEN approval_state IN ('needs_review', 'needs_approval') AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'approval_not_linked' END,
        CASE WHEN book_key IN ('tactical', 'active_trading') AND stop_price IS NULL AND target_price IS NULL AND time_exit_at IS NULL THEN 'missing_stop_target_or_time_exit' END,
        CASE WHEN book_key = 'hedges' AND nullif(hedge_intent, '') IS NULL THEN 'missing_hedge_intent' END,
        CASE WHEN book_key = 'hedges' AND linked_hedged_position_id IS NULL THEN 'missing_linked_hedged_position' END,
        CASE WHEN offset_intent = 'unknown' AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'unknown_offset_intent' END,
        CASE WHEN risk_budget_pct IS NULL THEN 'missing_risk_budget' END,
        CASE WHEN capital_budget_pct IS NULL THEN 'missing_capital_budget' END,
        CASE WHEN next_review_due_at IS NOT NULL AND next_review_due_at <= now() THEN 'review_overdue' END
    ], NULL)) AS v9_gap_count,
    greatest(0, round(((18 - cardinality(array_remove(ARRAY[
        CASE WHEN purpose_key IS NULL THEN 'missing_purpose' END,
        CASE WHEN nullif(thesis, '') IS NULL THEN 'missing_thesis_text' END,
        CASE WHEN book_key = 'long_term' AND NOT has_active_thesis THEN 'long_term_thesis_not_active' END,
        CASE WHEN nullif(exit_criteria, '') IS NULL THEN 'missing_exit_criteria_text' END,
        CASE WHEN NOT has_active_exit THEN 'exit_criteria_not_active' END,
        CASE WHEN entry_date IS NULL THEN 'missing_entry_date' END,
        CASE WHEN nullif(entry_rationale, '') IS NULL THEN 'missing_entry_rationale' END,
        CASE WHEN nullif(source_kind, '') IS NULL OR nullif(source_ref, '') IS NULL THEN 'missing_source_lineage' END,
        CASE WHEN source_freshness_at IS NULL THEN 'missing_source_freshness' END,
        CASE WHEN nullif(owner_agent, '') IS NULL THEN 'missing_owner' END,
        CASE WHEN nullif(time_horizon, '') IS NULL THEN 'missing_time_horizon' END,
        CASE WHEN approval_state IN ('needs_review', 'needs_approval') AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'approval_not_linked' END,
        CASE WHEN book_key IN ('tactical', 'active_trading') AND stop_price IS NULL AND target_price IS NULL AND time_exit_at IS NULL THEN 'missing_stop_target_or_time_exit' END,
        CASE WHEN book_key = 'hedges' AND nullif(hedge_intent, '') IS NULL THEN 'missing_hedge_intent' END,
        CASE WHEN book_key = 'hedges' AND linked_hedged_position_id IS NULL THEN 'missing_linked_hedged_position' END,
        CASE WHEN offset_intent = 'unknown' AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'unknown_offset_intent' END,
        CASE WHEN risk_budget_pct IS NULL THEN 'missing_risk_budget' END,
        CASE WHEN capital_budget_pct IS NULL THEN 'missing_capital_budget' END,
        CASE WHEN next_review_due_at IS NOT NULL AND next_review_due_at <= now() THEN 'review_overdue' END
    ], NULL))) * 100.0 / 18.0)::NUMERIC, 1)) AS v9_completeness_score,
    CASE
        WHEN cardinality(array_remove(ARRAY[
            CASE WHEN purpose_key IS NULL THEN 'missing_purpose' END,
            CASE WHEN book_key = 'long_term' AND NOT has_active_thesis THEN 'long_term_thesis_not_active' END,
            CASE WHEN NOT has_active_exit THEN 'exit_criteria_not_active' END,
            CASE WHEN approval_state IN ('needs_review', 'needs_approval') AND book_key IN ('tactical', 'quant', 'active_trading', 'hedges') THEN 'approval_not_linked' END
        ], NULL)) > 0 THEN 'not_decision_ready'
        WHEN review_state LIKE '%required%' THEN 'review_required'
        ELSE 'decision_ready'
    END AS v9_decision_readiness
FROM base;

CREATE OR REPLACE VIEW books.v_position_object_gap_summary AS
SELECT
    gap_type,
    count(*)::BIGINT AS position_count,
    count(DISTINCT client_code)::BIGINT AS client_count,
    count(DISTINCT symbol)::BIGINT AS symbol_count,
    round(avg(v9_completeness_score)::NUMERIC, 1) AS avg_completeness_score,
    CASE
        WHEN gap_type IN ('missing_purpose', 'long_term_thesis_not_active', 'exit_criteria_not_active', 'approval_not_linked') THEN 'critical'
        WHEN gap_type IN ('missing_stop_target_or_time_exit', 'missing_hedge_intent', 'missing_linked_hedged_position', 'missing_source_lineage') THEN 'high'
        ELSE 'medium'
    END AS severity,
    min(owner_agent) AS owner_agent
FROM books.v_position_objects_v9
CROSS JOIN LATERAL unnest(v9_gap_types) AS gap(gap_type)
GROUP BY gap_type
ORDER BY
    CASE
        WHEN gap_type IN ('missing_purpose', 'long_term_thesis_not_active', 'exit_criteria_not_active', 'approval_not_linked') THEN 1
        WHEN gap_type IN ('missing_stop_target_or_time_exit', 'missing_hedge_intent', 'missing_linked_hedged_position', 'missing_source_lineage') THEN 2
        ELSE 3
    END,
    position_count DESC,
    gap_type;

CREATE OR REPLACE VIEW books.v_cross_book_coordination_questions AS
WITH exposure AS (
    SELECT
        e.*,
        array_agg(DISTINCT po.offset_intent ORDER BY po.offset_intent) FILTER (WHERE po.offset_intent IS NOT NULL) AS offset_intents,
        min(po.owner_agent) AS first_owner_agent
    FROM books.v_symbol_book_exposure e
    JOIN books.v_position_objects_v9 po
      ON po.client_id IS NOT DISTINCT FROM e.client_id
     AND po.symbol = e.symbol
     AND po.exchange IS NOT DISTINCT FROM e.exchange
    GROUP BY
        e.client_id, e.client_code, e.client_name, e.symbol, e.exchange,
        e.long_term_exposure, e.tactical_exposure, e.quant_exposure,
        e.active_trading_exposure, e.hedges_exposure, e.cash_treasury_exposure,
        e.gross_long, e.gross_short, e.gross_exposure, e.net_exposure,
        e.book_count, e.active_books, e.purposes, e.latest_as_of,
        e.offset_ratio, e.overall_bias
)
SELECT
    row_number() OVER (ORDER BY offset_ratio DESC NULLS LAST, gross_exposure DESC NULLS LAST, client_name, symbol) AS synthetic_id,
    client_id,
    client_code,
    client_name,
    symbol,
    exchange,
    gross_long,
    gross_short,
    net_exposure,
    offset_ratio,
    overall_bias,
    active_books,
    purposes,
    coalesce(offset_intents, ARRAY[]::TEXT[]) AS offset_intents,
    CASE
        WHEN gross_short > 0 AND gross_long > 0 AND NOT coalesce(offset_intents, ARRAY[]::TEXT[]) && ARRAY['hedge']::TEXT[]
            THEN 'Is this offset an intentional hedge, independent alpha, or unnecessary self-canceling exposure?'
        WHEN gross_short > 0 AND gross_long > 0 AND offset_ratio >= 0.9
            THEN 'The short side offsets nearly the whole long exposure. Should the strategy exclude this core holding or keep the hedge?'
        WHEN gross_short > 0 AND gross_long > 0
            THEN 'Confirm hedge ratio, holding period, cost, and which book owns the decision.'
        ELSE 'No opposing exposure requiring coordination.'
    END AS coordination_question,
    CASE
        WHEN gross_short > 0 AND gross_long > 0 AND offset_ratio >= 0.9 THEN 'critical'
        WHEN gross_short > 0 AND gross_long > 0 AND offset_ratio >= 0.5 THEN 'high'
        WHEN gross_short > 0 AND gross_long > 0 THEN 'medium'
        ELSE 'low'
    END AS severity,
    coalesce(first_owner_agent, 'Risk Agent') AS owner_agent,
    latest_as_of
FROM exposure
WHERE gross_long > 0 AND gross_short > 0;

CREATE OR REPLACE VIEW books.v_portfolio_intelligence_summary AS
SELECT 'investment_books' AS metric, count(*)::TEXT AS value, 'Configured portfolio books' AS interpretation
FROM books.investment_books
UNION ALL
SELECT 'book_positions', count(*)::TEXT, 'Live positions assigned to investment books'
FROM books.book_positions
UNION ALL
SELECT 'booked_clients', count(DISTINCT client_id)::TEXT, 'Clients with at least one book-assigned position'
FROM books.book_positions
WHERE client_id IS NOT NULL
UNION ALL
SELECT 'gross_book_exposure', round(coalesce(sum(gross_exposure), 0), 2)::TEXT, 'Gross exposure across all books'
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT 'net_book_exposure', round(coalesce(sum(net_exposure), 0), 2)::TEXT, 'Net exposure across all books'
FROM books.book_positions
WHERE status = 'active'
UNION ALL
SELECT 'cross_book_conflicts', count(*)::TEXT, 'Open live cross-book offset conflicts'
FROM books.v_cross_book_conflicts
UNION ALL
SELECT 'book_assignment_gaps', count(*)::TEXT, 'Positions or controls that still need purpose, thesis, exit, or review completion'
FROM books.v_book_assignment_gaps
UNION ALL
SELECT 'position_object_v9_gap_rows', coalesce(sum(v9_gap_count), 0)::TEXT, 'Institutional position-object missing fields across active positions'
FROM books.v_position_objects_v9
UNION ALL
SELECT 'position_object_v9_avg_score', round(coalesce(avg(v9_completeness_score), 0), 1)::TEXT, 'Average v9 position-object completeness score'
FROM books.v_position_objects_v9;

UPDATE core.os_blueprint_requirements
SET
    current_status = 'partial',
    evidence_note_path = 'ai memory/00 AI OS/Reports/2026-07-07-position-object-v9-readiness-v1.md',
    mapped_object_type = 'control_module',
    mapped_object_key = 'portfolio_office',
    next_action = 'Backfill missing thesis, exit, stop/target, approval, hedge links, and review fields until v9 gap count is zero.',
    metadata = metadata || jsonb_build_object(
        'warehouse_objects', jsonb_build_array('books.v_position_objects_v9','books.v_position_object_gap_summary','books.v_cross_book_coordination_questions'),
        'updated_by_migration', '103_position_object_v9_readiness.sql'
    ),
    updated_at = now()
WHERE requirement_key = 'v9_req_position_object';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_position_objects_v9', 'mcp_tool', 'Portfolio Manager', 'read_only', true, 'Read v9 institutional position objects with completeness scores and gap types.', '{"reads":["books.v_position_objects_v9"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_position_object_gap_summary', 'mcp_tool', 'Risk Agent', 'read_only', true, 'Read summary of missing v9 position-object fields by gap type.', '{"reads":["books.v_position_object_gap_summary"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_cross_book_coordination_questions', 'mcp_tool', 'Risk Agent', 'read_only', true, 'Read cross-book offset coordination questions for opposing exposures.', '{"reads":["books.v_cross_book_coordination_questions"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
