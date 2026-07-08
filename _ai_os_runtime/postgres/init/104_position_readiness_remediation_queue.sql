CREATE TABLE IF NOT EXISTS books.position_object_remediation_queue (
    id BIGSERIAL PRIMARY KEY,
    remediation_key TEXT NOT NULL UNIQUE,
    book_position_id BIGINT NOT NULL REFERENCES books.book_positions(id) ON DELETE CASCADE,
    gap_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    priority TEXT NOT NULL DEFAULT 'normal',
    owner_agent TEXT NOT NULL,
    skill_key TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    recommended_action TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (book_position_id, gap_type)
);

CREATE INDEX IF NOT EXISTS idx_position_remediation_status
    ON books.position_object_remediation_queue(status, severity, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_position_remediation_owner
    ON books.position_object_remediation_queue(owner_agent, status, updated_at DESC);

CREATE OR REPLACE FUNCTION books.position_gap_owner(p_gap_type TEXT, p_book_key TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_gap_type IN ('long_term_thesis_not_active', 'missing_thesis_text') THEN 'Long-Term Portfolio Manager'
        WHEN p_gap_type IN ('exit_criteria_not_active', 'missing_exit_criteria_text') THEN 'Long-Term Portfolio Manager'
        WHEN p_gap_type IN ('missing_stop_target_or_time_exit') THEN 'Trading Desk Agent'
        WHEN p_gap_type IN ('approval_not_linked') THEN 'Risk Agent'
        WHEN p_gap_type IN ('missing_hedge_intent', 'missing_linked_hedged_position') THEN 'Risk Agent'
        WHEN p_gap_type IN ('missing_source_lineage', 'missing_source_freshness') THEN 'Data Steward'
        WHEN p_gap_type IN ('review_overdue') THEN 'Portfolio Manager'
        ELSE coalesce(NULLIF(
            CASE
                WHEN p_book_key = 'long_term' THEN 'Long-Term Portfolio Manager'
                WHEN p_book_key = 'quant' THEN 'Model Validation Agent'
                WHEN p_book_key = 'active_trading' THEN 'Trading Desk Agent'
                WHEN p_book_key = 'hedges' THEN 'Risk Agent'
                ELSE 'Portfolio Manager'
            END,
            ''
        ), 'Portfolio Manager')
    END;
$$;

CREATE OR REPLACE FUNCTION books.position_gap_skill(p_gap_type TEXT, p_book_key TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_gap_type IN ('long_term_thesis_not_active', 'missing_thesis_text') THEN 'long_term_specialist_dispatch'
        WHEN p_gap_type IN ('exit_criteria_not_active', 'missing_exit_criteria_text') THEN 'long_term_portfolio_fit_review'
        WHEN p_gap_type IN ('missing_stop_target_or_time_exit') THEN 'trade_journal_learning'
        WHEN p_gap_type IN ('approval_not_linked') THEN 'execution_safety_review'
        WHEN p_gap_type IN ('missing_hedge_intent', 'missing_linked_hedged_position') THEN 'portfolio_risk_review'
        WHEN p_gap_type IN ('missing_source_lineage', 'missing_source_freshness') THEN 'data_lineage_reconciliation'
        ELSE NULL
    END;
$$;

CREATE OR REPLACE FUNCTION books.position_gap_recommended_action(
    p_gap_type TEXT,
    p_symbol TEXT,
    p_book_name TEXT,
    p_client_name TEXT
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_gap_type = 'long_term_thesis_not_active'
            THEN 'Create or refresh the source-backed long-term thesis for ' || coalesce(p_symbol, 'symbol') || ', dispatch specialists, and do not approve action until thesis is active.'
        WHEN p_gap_type = 'exit_criteria_not_active'
            THEN 'Review and activate explicit exit criteria for ' || coalesce(p_symbol, 'symbol') || ' in ' || coalesce(p_book_name, 'book') || '.'
        WHEN p_gap_type = 'missing_stop_target_or_time_exit'
            THEN 'Add stop, target, or time-exit before this short-horizon position can be decision-ready.'
        WHEN p_gap_type = 'approval_not_linked'
            THEN 'Route this non-long-term exposure through approval/risk gate before any action.'
        WHEN p_gap_type = 'missing_hedge_intent'
            THEN 'Define hedge intent, exposure being hedged, ratio, cost, and unwind rule.'
        WHEN p_gap_type = 'missing_linked_hedged_position'
            THEN 'Link the hedge to the underlying position or mark it as independent alpha.'
        WHEN p_gap_type IN ('missing_source_lineage', 'missing_source_freshness')
            THEN 'Backfill source lineage and freshness for this position from broker, p2cursor, manual entry, or import artifact.'
        ELSE 'Resolve position-object gap ' || p_gap_type || ' for ' || coalesce(p_client_name, 'client') || ' / ' || coalesce(p_symbol, 'symbol') || ' with evidence.'
    END;
$$;

CREATE OR REPLACE FUNCTION books.sync_position_object_remediation_queue(
    p_limit INTEGER DEFAULT 200,
    p_create_tasks BOOLEAN DEFAULT true,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    queue_row RECORD;
    task_row RECORD;
    synced_count INTEGER := 0;
    task_count INTEGER := 0;
    inbox_count INTEGER := 0;
BEGIN
    WITH current_gaps AS (
        SELECT
            po.book_position_id,
            gap.gap_type,
            po.symbol,
            po.book_key,
            po.book_name,
            po.client_code,
            po.client_name,
            po.account_code,
            po.v9_completeness_score,
            po.v9_decision_readiness,
            CASE
                WHEN gap.gap_type IN ('missing_purpose', 'long_term_thesis_not_active', 'exit_criteria_not_active', 'approval_not_linked') THEN 'critical'
                WHEN gap.gap_type IN ('missing_stop_target_or_time_exit', 'missing_hedge_intent', 'missing_linked_hedged_position', 'missing_source_lineage') THEN 'high'
                ELSE 'medium'
            END AS severity,
            CASE
                WHEN gap.gap_type IN ('missing_purpose', 'long_term_thesis_not_active', 'exit_criteria_not_active', 'approval_not_linked') THEN 'high'
                ELSE 'normal'
            END AS priority
        FROM books.v_position_objects_v9 po
        CROSS JOIN LATERAL unnest(po.v9_gap_types) AS gap(gap_type)
        ORDER BY
            po.v9_gap_count DESC,
            po.gross_exposure DESC NULLS LAST,
            po.book_position_id,
            gap.gap_type
        LIMIT greatest(1, coalesce(p_limit, 200))
    ),
    upserted AS (
        INSERT INTO books.position_object_remediation_queue (
            remediation_key, book_position_id, gap_type, severity, priority,
            owner_agent, skill_key, status, recommended_action, evidence, created_by
        )
        SELECT
            'position-gap:' || book_position_id::TEXT || ':' || gap_type,
            book_position_id,
            gap_type,
            severity,
            priority,
            books.position_gap_owner(gap_type, book_key),
            books.position_gap_skill(gap_type, book_key),
            'queued',
            books.position_gap_recommended_action(gap_type, symbol, book_name, client_name),
            jsonb_build_array(
                jsonb_build_object('view', 'books.v_position_objects_v9', 'book_position_id', book_position_id),
                jsonb_build_object('gap_type', gap_type, 'symbol', symbol, 'client_code', client_code, 'book_key', book_key),
                jsonb_build_object('v9_completeness_score', v9_completeness_score, 'readiness', v9_decision_readiness)
            ),
            coalesce(nullif(p_actor, ''), 'Jarvis')
        FROM current_gaps
        ON CONFLICT (book_position_id, gap_type) DO UPDATE SET
            severity = EXCLUDED.severity,
            priority = EXCLUDED.priority,
            owner_agent = EXCLUDED.owner_agent,
            skill_key = EXCLUDED.skill_key,
            recommended_action = EXCLUDED.recommended_action,
            evidence = EXCLUDED.evidence,
            status = CASE
                WHEN books.position_object_remediation_queue.status IN ('resolved', 'ignored') THEN books.position_object_remediation_queue.status
                WHEN books.position_object_remediation_queue.task_id IS NOT NULL THEN 'task_created'
                ELSE 'queued'
            END,
            updated_at = now()
        RETURNING id
    )
    SELECT count(*) INTO synced_count FROM upserted;

    IF p_create_tasks THEN
        FOR queue_row IN
            SELECT q.*, po.symbol, po.client_name, po.book_name, po.v9_gap_count
            FROM books.position_object_remediation_queue q
            JOIN books.v_position_objects_v9 po ON po.book_position_id = q.book_position_id
            WHERE q.status IN ('queued', 'task_created')
              AND q.task_id IS NULL
            ORDER BY
                CASE q.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                q.updated_at DESC,
                q.id
            LIMIT greatest(1, coalesce(p_limit, 200))
        LOOP
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                'Resolve position gap: ' || queue_row.symbol || ' / ' || replace(queue_row.gap_type, '_', ' '),
                queue_row.recommended_action,
                queue_row.owner_agent,
                'queued',
                queue_row.priority,
                false,
                'position_object_gap',
                queue_row.remediation_key,
                'position_readiness_remediation',
                queue_row.evidence
            )
            RETURNING * INTO task_row;

            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            VALUES (
                task_row.id,
                task_row.title,
                queue_row.owner_agent,
                'queued',
                queue_row.priority,
                queue_row.recommended_action,
                queue_row.evidence,
                CASE
                    WHEN queue_row.owner_agent IN ('Risk Agent', 'Execution Safety Agent') THEN 'risk'
                    WHEN queue_row.owner_agent IN ('Trading Desk Agent') THEN 'trading'
                    ELSE 'portfolio'
                END
            )
            RETURNING id INTO task_row;

            UPDATE books.position_object_remediation_queue
            SET task_id = (SELECT id FROM agent.tasks WHERE source_kind = 'position_object_gap' AND source_ref = queue_row.remediation_key ORDER BY created_at DESC LIMIT 1),
                inbox_id = task_row.id,
                status = 'task_created',
                updated_at = now()
            WHERE id = queue_row.id;

            task_count := task_count + 1;
            inbox_count := inbox_count + 1;
        END LOOP;
    END IF;

    RETURN jsonb_build_object(
        'status', 'ok',
        'synced_count', synced_count,
        'tasks_created', task_count,
        'inbox_items_created', inbox_count,
        'open_queue_count', (SELECT count(*) FROM books.position_object_remediation_queue WHERE status IN ('queued', 'task_created')),
        'actor', coalesce(nullif(p_actor, ''), 'Jarvis'),
        'created_at', now()
    );
END;
$$;

CREATE OR REPLACE VIEW books.v_position_object_remediation_queue AS
SELECT
    q.id,
    q.remediation_key,
    q.book_position_id,
    po.client_code,
    po.client_name,
    po.account_code,
    po.symbol,
    po.exchange,
    po.instrument_type,
    po.book_key,
    po.book_name,
    po.purpose_key,
    po.purpose_name,
    q.gap_type,
    q.severity,
    q.priority,
    q.owner_agent,
    q.skill_key,
    q.status,
    q.recommended_action,
    q.task_id,
    task.status AS task_status,
    q.inbox_id,
    inbox.status AS inbox_status,
    po.v9_gap_count,
    po.v9_gap_types,
    po.v9_completeness_score,
    po.v9_decision_readiness,
    q.evidence,
    q.created_by,
    q.created_at,
    q.updated_at,
    q.resolved_at
FROM books.position_object_remediation_queue q
JOIN books.v_position_objects_v9 po ON po.book_position_id = q.book_position_id
LEFT JOIN agent.tasks task ON task.id = q.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = q.inbox_id
ORDER BY
    CASE q.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE q.status WHEN 'queued' THEN 1 WHEN 'task_created' THEN 2 WHEN 'in_progress' THEN 3 WHEN 'resolved' THEN 4 ELSE 5 END,
    po.gross_exposure DESC NULLS LAST,
    q.updated_at DESC;

CREATE OR REPLACE VIEW books.v_position_object_remediation_summary AS
SELECT 'open_remediation_items' AS metric, count(*)::TEXT AS value, 'Open position-object readiness gaps routed for agent remediation' AS interpretation
FROM books.position_object_remediation_queue
WHERE status IN ('queued', 'task_created', 'in_progress')
UNION ALL
SELECT 'remediation_tasks', count(*)::TEXT, 'Tasks created from position-object readiness gaps'
FROM books.position_object_remediation_queue
WHERE task_id IS NOT NULL
UNION ALL
SELECT 'critical_remediation_items', count(*)::TEXT, 'Critical position-object gaps that block decision readiness'
FROM books.position_object_remediation_queue
WHERE status IN ('queued', 'task_created', 'in_progress') AND severity = 'critical'
UNION ALL
SELECT 'remediation_symbols', count(DISTINCT po.symbol)::TEXT, 'Distinct symbols with open position-object remediation work'
FROM books.position_object_remediation_queue q
JOIN books.v_position_objects_v9 po ON po.book_position_id = q.book_position_id
WHERE q.status IN ('queued', 'task_created', 'in_progress');

UPDATE core.os_blueprint_requirements
SET
    current_status = 'partial',
    evidence_note_path = 'ai memory/00 AI OS/Reports/2026-07-07-position-readiness-remediation-queue-v1.md',
    next_action = 'Use the remediation queue to dispatch and complete source-backed thesis and exit review work until position-object gaps reach zero.',
    metadata = metadata || jsonb_build_object(
        'warehouse_objects', jsonb_build_array('books.position_object_remediation_queue','books.v_position_object_remediation_queue','books.v_position_object_remediation_summary'),
        'updated_by_migration', '104_position_readiness_remediation_queue.sql'
    ),
    updated_at = now()
WHERE requirement_key = 'v9_req_position_object';

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_sync_position_remediation_queue', 'mcp_tool', 'Portfolio Manager', 'write_with_approval', true, 'Create or refresh position-object remediation queue items and optional agent tasks from v9 readiness gaps.', '{"function":"books.sync_position_object_remediation_queue","writes":["books.position_object_remediation_queue","agent.tasks","agent.inbox_items"],"reads":["books.v_position_objects_v9"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_position_remediation_queue', 'mcp_tool', 'Portfolio Manager', 'read_only', true, 'Read position-object remediation queue items, owner agents, tasks, and inbox state.', '{"reads":["books.v_position_object_remediation_queue"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_position_remediation_summary', 'mcp_tool', 'Chief of Staff', 'read_only', true, 'Read position-object remediation summary metrics.', '{"reads":["books.v_position_object_remediation_summary"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

