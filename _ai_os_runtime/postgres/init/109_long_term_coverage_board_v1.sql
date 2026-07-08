CREATE TABLE IF NOT EXISTS portfolio.long_term_coverage_queue (
    id BIGSERIAL PRIMARY KEY,
    coverage_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    gap_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    priority TEXT NOT NULL DEFAULT 'normal',
    priority_score NUMERIC NOT NULL DEFAULT 0,
    owner_agent TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    status TEXT NOT NULL DEFAULT 'queued',
    recommended_action TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (symbol, exchange, gap_type)
);

CREATE INDEX IF NOT EXISTS idx_long_term_coverage_queue_status
    ON portfolio.long_term_coverage_queue (status, severity, priority_score DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_long_term_coverage_queue_symbol
    ON portfolio.long_term_coverage_queue (symbol, exchange, status);

CREATE OR REPLACE FUNCTION portfolio.long_term_coverage_gap_action(
    p_gap_type TEXT,
    p_symbol TEXT,
    p_exchange TEXT
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_gap_type = 'missing_thesis_container'
            THEN 'Generate the source-backed long-term thesis memo for ' || coalesce(p_exchange, 'NSE') || ':' || coalesce(p_symbol, 'symbol') || ', then dispatch specialist modules. No capital action is authorized.'
        WHEN p_gap_type = 'checklist_incomplete'
            THEN 'Complete business model, moat, management, governance, capital allocation, financial quality, forensic, and bear-case checklist rows for ' || coalesce(p_symbol, 'symbol') || ' with source evidence.'
        WHEN p_gap_type = 'valuation_incomplete'
            THEN 'Complete valuation modules for ' || coalesce(p_symbol, 'symbol') || ' with explicit assumptions, fair-value range, and expected-CAGR evidence.'
        WHEN p_gap_type = 'monte_carlo_missing'
            THEN 'Run Long-Term Monte Carlo for ' || coalesce(p_symbol, 'symbol') || ' after assumptions are documented; route output into the committee packet.'
        WHEN p_gap_type = 'exit_criteria_missing'
            THEN 'Write explicit exit criteria and thesis-killer conditions for ' || coalesce(p_symbol, 'symbol') || ' before any committee approval.'
        WHEN p_gap_type = 'committee_decision_not_ready'
            THEN 'Route ' || coalesce(p_symbol, 'symbol') || ' through Long-Term Investment Committee after packet, checklist, valuation, bear case, and Monte Carlo evidence are ready.'
        ELSE 'Resolve long-term coverage gap ' || coalesce(p_gap_type, 'unknown') || ' for ' || coalesce(p_symbol, 'symbol') || ' with evidence.'
    END;
$$;

CREATE OR REPLACE VIEW portfolio.v_long_term_coverage_candidates AS
WITH latest_mc AS (
    SELECT
        holding_thesis_id,
        count(*) AS run_count,
        max(created_at) AS latest_monte_carlo_at,
        max(note_path) FILTER (WHERE note_path IS NOT NULL) AS latest_monte_carlo_note
    FROM portfolio.long_term_monte_carlo_runs
    WHERE run_status = 'completed'
    GROUP BY holding_thesis_id
),
control AS (
    SELECT
        id AS holding_thesis_id,
        symbol,
        coalesce(nullif(exchange, ''), 'NSE') AS exchange,
        company_name,
        thesis_status,
        decision_status,
        primary_owner_agent,
        checklist_count,
        checklist_complete_count,
        valuation_model_count,
        valuation_complete_count,
        exit_criteria,
        thesis_note_path,
        long_term_gross_exposure,
        long_term_net_exposure,
        client_count,
        clients,
        next_review_due_at
    FROM portfolio.v_long_term_thesis_control
    WHERE symbol IS NOT NULL
      AND coalesce(long_term_gross_exposure, 0) > 0
)
SELECT
    lower('lt-coverage:' || control.exchange || ':' || control.symbol || ':' || gap.gap_type) AS coverage_key,
    control.symbol,
    control.exchange,
    control.holding_thesis_id,
    control.company_name,
    control.thesis_status,
    control.decision_status,
    control.primary_owner_agent,
    gap.gap_type,
    gap.severity,
    CASE gap.severity
        WHEN 'critical' THEN 'high'
        WHEN 'high' THEN 'high'
        ELSE 'normal'
    END AS priority,
    (coalesce(control.long_term_gross_exposure, 0) +
        CASE gap.severity WHEN 'critical' THEN 100000000 WHEN 'high' THEN 50000000 ELSE 10000000 END -
        gap.gap_rank
    )::NUMERIC AS priority_score,
    gap.owner_agent,
    portfolio.long_term_coverage_gap_action(gap.gap_type, control.symbol, control.exchange) AS recommended_action,
    control.long_term_gross_exposure,
    control.long_term_net_exposure,
    control.client_count,
    control.clients,
    control.checklist_count,
    control.checklist_complete_count,
    control.valuation_model_count,
    control.valuation_complete_count,
    latest_mc.run_count AS monte_carlo_run_count,
    latest_mc.latest_monte_carlo_at,
    latest_mc.latest_monte_carlo_note,
    control.thesis_note_path,
    control.next_review_due_at,
    jsonb_build_array(
        jsonb_build_object('view', 'portfolio.v_long_term_thesis_control', 'holding_thesis_id', control.holding_thesis_id, 'symbol', control.symbol, 'exchange', control.exchange),
        jsonb_build_object('gross_exposure', control.long_term_gross_exposure, 'client_count', control.client_count),
        jsonb_build_object('checklist_complete', control.checklist_complete_count, 'checklist_total', control.checklist_count),
        jsonb_build_object('valuation_complete', control.valuation_complete_count, 'valuation_total', control.valuation_model_count),
        jsonb_build_object('monte_carlo_run_count', coalesce(latest_mc.run_count, 0))
    ) AS evidence
FROM control
LEFT JOIN latest_mc ON latest_mc.holding_thesis_id = control.holding_thesis_id
CROSS JOIN LATERAL (
    VALUES
        (
            CASE WHEN control.holding_thesis_id IS NULL THEN 'missing_thesis_container' END,
            1,
            'critical',
            'Long-Term Portfolio Manager'
        ),
        (
            CASE
                WHEN control.holding_thesis_id IS NOT NULL
                 AND (coalesce(control.checklist_count, 0) = 0 OR coalesce(control.checklist_complete_count, 0) < coalesce(control.checklist_count, 0))
                THEN 'checklist_incomplete'
            END,
            2,
            'critical',
            'Long-Term Portfolio Manager'
        ),
        (
            CASE
                WHEN control.holding_thesis_id IS NOT NULL
                 AND (coalesce(control.valuation_model_count, 0) = 0 OR coalesce(control.valuation_complete_count, 0) < coalesce(control.valuation_model_count, 0))
                THEN 'valuation_incomplete'
            END,
            3,
            'high',
            'Valuation Agent'
        ),
        (
            CASE
                WHEN control.holding_thesis_id IS NOT NULL
                 AND coalesce(latest_mc.run_count, 0) = 0
                THEN 'monte_carlo_missing'
            END,
            4,
            'high',
            'Quant Risk Analyst'
        ),
        (
            CASE
                WHEN control.holding_thesis_id IS NOT NULL
                 AND length(trim(coalesce(control.exit_criteria, ''))) < 20
                THEN 'exit_criteria_missing'
            END,
            5,
            'high',
            'Long-Term Portfolio Manager'
        ),
        (
            CASE
                WHEN control.holding_thesis_id IS NOT NULL
                 AND coalesce(control.decision_status, 'research_required') IN ('research_required','committee_research_required','committee_review_open')
                THEN 'committee_decision_not_ready'
            END,
            6,
            'medium',
            'Long-Term Portfolio Manager'
        )
) AS gap(gap_type, gap_rank, severity, owner_agent)
WHERE gap.gap_type IS NOT NULL
ORDER BY priority_score DESC, control.long_term_gross_exposure DESC NULLS LAST, control.symbol, gap.gap_rank;

CREATE OR REPLACE FUNCTION portfolio.sync_long_term_coverage_queue(
    p_limit INTEGER DEFAULT 100,
    p_create_tasks BOOLEAN DEFAULT true,
    p_actor TEXT DEFAULT 'Jarvis'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    queue_row RECORD;
    synced_count INTEGER := 0;
    resolved_count INTEGER := 0;
    task_count INTEGER := 0;
    inbox_count INTEGER := 0;
    v_task_id BIGINT;
    v_inbox_id BIGINT;
BEGIN
    WITH candidates AS (
        SELECT *
        FROM portfolio.v_long_term_coverage_candidates
        ORDER BY priority_score DESC, long_term_gross_exposure DESC NULLS LAST
        LIMIT greatest(1, coalesce(p_limit, 100))
    ),
    upserted AS (
        INSERT INTO portfolio.long_term_coverage_queue (
            coverage_key, symbol, exchange, holding_thesis_id, gap_type,
            severity, priority, priority_score, owner_agent, status,
            recommended_action, evidence, created_by
        )
        SELECT
            coverage_key,
            symbol,
            exchange,
            holding_thesis_id,
            gap_type,
            severity,
            priority,
            priority_score,
            owner_agent,
            'queued',
            recommended_action,
            evidence,
            coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Jarvis')
        FROM candidates
        ON CONFLICT (coverage_key) DO UPDATE SET
            holding_thesis_id = EXCLUDED.holding_thesis_id,
            severity = EXCLUDED.severity,
            priority = EXCLUDED.priority,
            priority_score = EXCLUDED.priority_score,
            owner_agent = EXCLUDED.owner_agent,
            recommended_action = EXCLUDED.recommended_action,
            evidence = EXCLUDED.evidence,
            status = CASE
                WHEN portfolio.long_term_coverage_queue.status IN ('resolved','ignored') THEN portfolio.long_term_coverage_queue.status
                WHEN portfolio.long_term_coverage_queue.task_id IS NOT NULL THEN 'task_created'
                ELSE 'queued'
            END,
            resolved_at = NULL,
            updated_at = now()
        RETURNING id
    )
    SELECT count(*) INTO synced_count FROM upserted;

    WITH active_candidate_keys AS (
        SELECT coverage_key
        FROM portfolio.v_long_term_coverage_candidates
    ),
    marked AS (
        UPDATE portfolio.long_term_coverage_queue queue
        SET status = 'resolved',
            resolved_at = now(),
            updated_at = now()
        WHERE queue.status NOT IN ('resolved','ignored')
          AND NOT EXISTS (
              SELECT 1
              FROM active_candidate_keys candidate
              WHERE candidate.coverage_key = queue.coverage_key
          )
        RETURNING id
    )
    SELECT count(*) INTO resolved_count FROM marked;

    IF p_create_tasks THEN
        FOR queue_row IN
            SELECT *
            FROM portfolio.long_term_coverage_queue
            WHERE status IN ('queued','task_created')
              AND task_id IS NULL
            ORDER BY
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                priority_score DESC,
                updated_at DESC
            LIMIT greatest(1, coalesce(p_limit, 100))
        LOOP
            INSERT INTO agent.tasks (
                title, objective, owner_agent, status, priority, approval_required,
                source_kind, source_ref, output_format, evidence
            )
            VALUES (
                'Long-Term coverage gap: ' || queue_row.symbol || ' / ' || replace(queue_row.gap_type, '_', ' '),
                queue_row.recommended_action,
                queue_row.owner_agent,
                'queued',
                queue_row.priority,
                false,
                'long_term_coverage_gap',
                queue_row.coverage_key,
                'long_term_coverage_remediation',
                queue_row.evidence
            )
            RETURNING id INTO v_task_id;

            INSERT INTO agent.inbox_items (
                task_id, title, owner_agent, status, priority,
                recommended_action, evidence, target_workspace
            )
            VALUES (
                v_task_id,
                'Long-Term coverage gap: ' || queue_row.symbol || ' / ' || replace(queue_row.gap_type, '_', ' '),
                queue_row.owner_agent,
                'queued',
                queue_row.priority,
                queue_row.recommended_action,
                queue_row.evidence,
                CASE
                    WHEN queue_row.owner_agent IN ('Valuation Agent', 'Quant Risk Analyst') THEN 'research'
                    ELSE 'portfolio'
                END
            )
            RETURNING id INTO v_inbox_id;

            UPDATE portfolio.long_term_coverage_queue
            SET task_id = v_task_id,
                inbox_id = v_inbox_id,
                status = 'task_created',
                updated_at = now()
            WHERE id = queue_row.id;

            task_count := task_count + 1;
            inbox_count := inbox_count + 1;
        END LOOP;
    END IF;

    RETURN jsonb_build_object(
        'status', 'ok',
        'candidate_count', (SELECT count(*) FROM portfolio.v_long_term_coverage_candidates),
        'synced_count', synced_count,
        'resolved_count', resolved_count,
        'tasks_created', task_count,
        'inbox_items_created', inbox_count,
        'open_queue_count', (
            SELECT count(*)
            FROM portfolio.long_term_coverage_queue
            WHERE status IN ('queued','task_created','in_progress')
        ),
        'actor', coalesce(nullif(trim(coalesce(p_actor, '')), ''), 'Jarvis'),
        'created_at', now()
    );
END;
$$;

CREATE OR REPLACE VIEW portfolio.v_long_term_coverage_queue AS
SELECT
    queue.id,
    queue.coverage_key,
    queue.symbol,
    queue.exchange,
    queue.holding_thesis_id,
    thesis.company_name,
    thesis.thesis_status,
    thesis.decision_status,
    queue.gap_type,
    queue.severity,
    queue.priority,
    queue.priority_score,
    queue.owner_agent,
    queue.status,
    queue.recommended_action,
    queue.task_id,
    task.status AS task_status,
    queue.inbox_id,
    inbox.status AS inbox_status,
    control.long_term_gross_exposure,
    control.long_term_net_exposure,
    control.client_count,
    control.clients,
    control.checklist_count,
    control.checklist_complete_count,
    control.valuation_model_count,
    control.valuation_complete_count,
    mc.run_count AS monte_carlo_run_count,
    mc.latest_monte_carlo_at,
    control.thesis_note_path,
    control.next_review_due_at,
    queue.evidence,
    queue.created_by,
    queue.created_at,
    queue.updated_at,
    queue.resolved_at
FROM portfolio.long_term_coverage_queue queue
LEFT JOIN portfolio.holding_theses thesis ON thesis.id = queue.holding_thesis_id
LEFT JOIN portfolio.v_long_term_thesis_control control
  ON control.symbol = queue.symbol
 AND coalesce(nullif(control.exchange, ''), 'NSE') = queue.exchange
 AND (queue.holding_thesis_id IS NULL OR control.id IS NOT DISTINCT FROM queue.holding_thesis_id)
LEFT JOIN (
    SELECT
        holding_thesis_id,
        count(*) AS run_count,
        max(created_at) AS latest_monte_carlo_at
    FROM portfolio.long_term_monte_carlo_runs
    WHERE run_status = 'completed'
    GROUP BY holding_thesis_id
) mc ON mc.holding_thesis_id = queue.holding_thesis_id
LEFT JOIN agent.tasks task ON task.id = queue.task_id
LEFT JOIN agent.inbox_items inbox ON inbox.id = queue.inbox_id
ORDER BY
    CASE queue.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    CASE queue.status WHEN 'queued' THEN 1 WHEN 'task_created' THEN 2 WHEN 'in_progress' THEN 3 WHEN 'resolved' THEN 4 ELSE 5 END,
    queue.priority_score DESC,
    queue.updated_at DESC;

CREATE OR REPLACE VIEW portfolio.v_long_term_coverage_summary AS
SELECT 'open_coverage_items' AS metric, count(*)::TEXT AS value, 'Open Long-Term coverage gaps across thesis, checklist, valuation, Monte Carlo, exit criteria, and committee readiness.' AS interpretation
FROM portfolio.long_term_coverage_queue
WHERE status IN ('queued','task_created','in_progress')
UNION ALL
SELECT 'critical_coverage_items', count(*)::TEXT, 'Critical Long-Term coverage gaps that block research and committee readiness.'
FROM portfolio.long_term_coverage_queue
WHERE status IN ('queued','task_created','in_progress') AND severity = 'critical'
UNION ALL
SELECT 'coverage_symbols', count(DISTINCT symbol)::TEXT, 'Distinct symbols with open Long-Term coverage gaps.'
FROM portfolio.long_term_coverage_queue
WHERE status IN ('queued','task_created','in_progress')
UNION ALL
SELECT 'missing_thesis_symbols', count(DISTINCT symbol)::TEXT, 'Long-Term exposure symbols without a thesis container.'
FROM portfolio.long_term_coverage_queue
WHERE status IN ('queued','task_created','in_progress') AND gap_type = 'missing_thesis_container'
UNION ALL
SELECT 'coverage_tasks', count(*)::TEXT, 'Agent tasks created from Long-Term coverage gaps.'
FROM portfolio.long_term_coverage_queue
WHERE task_id IS NOT NULL
UNION ALL
SELECT 'candidate_gap_count', count(*)::TEXT, 'Current live Long-Term coverage candidates from portfolio.v_long_term_thesis_control.'
FROM portfolio.v_long_term_coverage_candidates;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_sync_long_term_coverage_queue', 'mcp_tool', 'Long-Term Portfolio Manager', 'write_with_approval', true, 'Create or refresh Long-Term coverage queue items and optional agent tasks from live long-term exposure and thesis evidence gaps.', '{"function":"portfolio.sync_long_term_coverage_queue","writes":["portfolio.long_term_coverage_queue","agent.tasks","agent.inbox_items"],"reads":["portfolio.v_long_term_thesis_control","portfolio.v_long_term_monte_carlo_runs"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_long_term_coverage_queue', 'mcp_tool', 'Long-Term Portfolio Manager', 'read_only', true, 'Read Long-Term coverage queue items, owner agents, tasks, and inbox state.', '{"reads":["portfolio.v_long_term_coverage_queue"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('ai_os_long_term_coverage_summary', 'mcp_tool', 'Charlie Munger', 'read_only', true, 'Read Long-Term coverage summary metrics across thesis, checklist, valuation, Monte Carlo, exit criteria, and committee readiness.', '{"reads":["portfolio.v_long_term_coverage_summary"],"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent,
    ui_workspace, description, warehouse_objects, mcp_tools, fincept_component,
    next_action, metadata
)
VALUES (
    'long-term-coverage-board',
    'Long-Term Coverage Board',
    'portfolio',
    'active',
    'high',
    'Long-Term Portfolio Manager',
    'portfolio',
    'Systematic coverage board that turns all material Long-Term book exposure into thesis, checklist, valuation, Monte Carlo, exit-criteria, and committee-readiness work.',
    ARRAY['portfolio.long_term_coverage_queue','portfolio.v_long_term_coverage_candidates','portfolio.v_long_term_coverage_queue','portfolio.v_long_term_coverage_summary']::TEXT[],
    ARRAY['ai_os_sync_long_term_coverage_queue','ai_os_long_term_coverage_queue','ai_os_long_term_coverage_summary']::TEXT[],
    NULL,
    'Run the sync after holdings import or research updates, then complete queued gaps by exposure priority before approving any Long-Term decision.',
    '{"seed_data_allowed":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (module_key) DO UPDATE SET
    module_name = EXCLUDED.module_name,
    category = EXCLUDED.category,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    owner_agent = EXCLUDED.owner_agent,
    ui_workspace = EXCLUDED.ui_workspace,
    description = EXCLUDED.description,
    warehouse_objects = EXCLUDED.warehouse_objects,
    mcp_tools = EXCLUDED.mcp_tools,
    fincept_component = EXCLUDED.fincept_component,
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();
