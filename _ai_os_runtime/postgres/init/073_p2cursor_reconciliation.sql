CREATE TABLE IF NOT EXISTS portfolio.p2cursor_reconciliation_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    run_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    client_id BIGINT REFERENCES portfolio.clients(id),
    client_code TEXT,
    client_name TEXT,
    p2_account_id BIGINT REFERENCES portfolio.accounts(id),
    p2_account_code TEXT,
    comparison_account_id BIGINT REFERENCES portfolio.accounts(id),
    comparison_account_code TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    p2_position_count INTEGER NOT NULL DEFAULT 0,
    comparison_position_count INTEGER NOT NULL DEFAULT 0,
    matched_symbols INTEGER NOT NULL DEFAULT 0,
    p2_only_symbols INTEGER NOT NULL DEFAULT 0,
    comparison_only_symbols INTEGER NOT NULL DEFAULT 0,
    quantity_mismatch_symbols INTEGER NOT NULL DEFAULT 0,
    stale_days INTEGER,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS portfolio.p2cursor_reconciliation_issues (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES portfolio.p2cursor_reconciliation_runs(id) ON DELETE CASCADE,
    issue_key TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    client_code TEXT,
    symbol TEXT,
    p2_account_code TEXT,
    comparison_account_code TEXT,
    p2_quantity NUMERIC,
    comparison_quantity NUMERIC,
    p2_average_price NUMERIC,
    comparison_average_price NUMERIC,
    p2_as_of TIMESTAMPTZ,
    comparison_as_of TIMESTAMPTZ,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, issue_key)
);

CREATE INDEX IF NOT EXISTS idx_p2cursor_recon_runs_client_created
    ON portfolio.p2cursor_reconciliation_runs (client_code, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_p2cursor_recon_issues_run
    ON portfolio.p2cursor_reconciliation_issues (run_id, severity, status);

CREATE OR REPLACE FUNCTION portfolio.run_p2cursor_reconciliation(
    p_actor TEXT DEFAULT 'Jarvis',
    p_client_code TEXT DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    selected_client RECORD;
    p2_account RECORD;
    comparison_account RECORD;
    inserted_run_id BIGINT;
    p2_count INTEGER := 0;
    comparison_count INTEGER := 0;
    matched_count INTEGER := 0;
    p2_only_count INTEGER := 0;
    comparison_only_count INTEGER := 0;
    quantity_mismatch_count INTEGER := 0;
    stale_day_count INTEGER := NULL;
    run_status TEXT := 'completed';
    run_notes TEXT := NULL;
BEGIN
    SELECT c.id, c.client_code, c.display_name
    INTO selected_client
    FROM portfolio.clients c
    WHERE (p_client_code IS NULL OR c.client_code = p_client_code OR c.display_name ILIKE p_client_code)
      AND EXISTS (
          SELECT 1
          FROM portfolio.accounts a
          JOIN portfolio.positions p ON p.account_id = a.id
          WHERE a.client_id = c.id
            AND (a.account_code ILIKE 'p2cursor%' OR a.broker = 'legacy_p2cursor')
      )
    ORDER BY
      CASE WHEN c.client_code = '3081832' THEN 0 ELSE 1 END,
      c.display_name
    LIMIT 1;

    IF selected_client.id IS NULL THEN
        RAISE EXCEPTION 'No p2cursor client positions found for client_code=%', coalesce(p_client_code, '<auto>');
    END IF;

    SELECT a.id, a.account_code, max(p.as_of) AS latest_as_of
    INTO p2_account
    FROM portfolio.accounts a
    JOIN portfolio.positions p ON p.account_id = a.id
    WHERE a.client_id = selected_client.id
      AND (a.account_code ILIKE 'p2cursor%' OR a.broker = 'legacy_p2cursor')
    GROUP BY a.id, a.account_code
    ORDER BY max(p.as_of) DESC NULLS LAST, a.account_code
    LIMIT 1;

    SELECT a.id, a.account_code, max(p.as_of) AS latest_as_of
    INTO comparison_account
    FROM portfolio.accounts a
    JOIN portfolio.positions p ON p.account_id = a.id
    WHERE a.client_id = selected_client.id
      AND NOT (a.account_code ILIKE 'p2cursor%' OR a.broker = 'legacy_p2cursor')
    GROUP BY a.id, a.account_code
    ORDER BY max(p.as_of) DESC NULLS LAST, a.account_code
    LIMIT 1;

    SELECT count(*)
    INTO p2_count
    FROM (
        SELECT DISTINCT p.symbol, p.exchange, p.instrument_type
        FROM portfolio.positions p
        WHERE p.account_id = p2_account.id
          AND coalesce(p.quantity, 0) <> 0
    ) rows;

    IF comparison_account.id IS NULL THEN
        run_status := 'blocked';
        run_notes := 'No non-p2cursor comparison account with positions exists for this client.';
        comparison_count := 0;
        matched_count := 0;
        p2_only_count := p2_count;
        comparison_only_count := 0;
        quantity_mismatch_count := 0;
    ELSE
        SELECT count(*)
        INTO comparison_count
        FROM (
            SELECT DISTINCT p.symbol, p.exchange, p.instrument_type
            FROM portfolio.positions p
            WHERE p.account_id = comparison_account.id
              AND coalesce(p.quantity, 0) <> 0
        ) rows;

        WITH latest_p2 AS (
            SELECT *
            FROM (
                SELECT p.*,
                       row_number() OVER (PARTITION BY p.symbol, p.exchange, p.instrument_type ORDER BY p.as_of DESC NULLS LAST, p.id DESC) AS rn
                FROM portfolio.positions p
                WHERE p.account_id = p2_account.id
                  AND coalesce(p.quantity, 0) <> 0
            ) ranked
            WHERE rn = 1
        ),
        latest_comparison AS (
            SELECT *
            FROM (
                SELECT p.*,
                       row_number() OVER (PARTITION BY p.symbol, p.exchange, p.instrument_type ORDER BY p.as_of DESC NULLS LAST, p.id DESC) AS rn
                FROM portfolio.positions p
                WHERE p.account_id = comparison_account.id
                  AND coalesce(p.quantity, 0) <> 0
            ) ranked
            WHERE rn = 1
        ),
        joined AS (
            SELECT
                coalesce(p2.symbol, cmp.symbol) AS symbol,
                p2.quantity AS p2_quantity,
                cmp.quantity AS comparison_quantity
            FROM latest_p2 p2
            FULL OUTER JOIN latest_comparison cmp
              ON cmp.symbol = p2.symbol
             AND cmp.exchange = p2.exchange
             AND cmp.instrument_type = p2.instrument_type
        )
        SELECT
            count(*) FILTER (WHERE p2_quantity IS NOT NULL AND comparison_quantity IS NOT NULL),
            count(*) FILTER (WHERE p2_quantity IS NOT NULL AND comparison_quantity IS NULL),
            count(*) FILTER (WHERE p2_quantity IS NULL AND comparison_quantity IS NOT NULL),
            count(*) FILTER (
                WHERE p2_quantity IS NOT NULL
                  AND comparison_quantity IS NOT NULL
                  AND abs(coalesce(p2_quantity, 0) - coalesce(comparison_quantity, 0)) > 0.0001
            )
        INTO matched_count, p2_only_count, comparison_only_count, quantity_mismatch_count
        FROM joined;

        IF p2_account.latest_as_of IS NOT NULL AND comparison_account.latest_as_of IS NOT NULL THEN
            stale_day_count := greatest(0, (comparison_account.latest_as_of::date - p2_account.latest_as_of::date));
        END IF;

        IF p2_only_count + comparison_only_count + quantity_mismatch_count > 0 THEN
            run_status := 'needs_review';
            run_notes := 'P2Cursor and comparison account positions differ; Data Steward review required before treating p2cursor as current truth.';
        ELSE
            run_status := 'matched';
            run_notes := 'P2Cursor and comparison account open quantities match for the latest account snapshots.';
        END IF;
    END IF;

    INSERT INTO portfolio.p2cursor_reconciliation_runs (
        run_key, client_id, client_code, client_name,
        p2_account_id, p2_account_code, comparison_account_id, comparison_account_code,
        status, p2_position_count, comparison_position_count, matched_symbols,
        p2_only_symbols, comparison_only_symbols, quantity_mismatch_symbols,
        stale_days, notes, evidence, created_by
    )
    VALUES (
        'p2cursor-recon-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS'),
        selected_client.id,
        selected_client.client_code,
        selected_client.display_name,
        p2_account.id,
        p2_account.account_code,
        comparison_account.id,
        comparison_account.account_code,
        run_status,
        p2_count,
        comparison_count,
        matched_count,
        p2_only_count,
        comparison_only_count,
        quantity_mismatch_count,
        stale_day_count,
        run_notes,
        jsonb_build_array(
            jsonb_build_object('source', 'portfolio.positions', 'account_code', p2_account.account_code, 'role', 'p2cursor'),
            jsonb_build_object('source', 'portfolio.positions', 'account_code', comparison_account.account_code, 'role', 'comparison'),
            jsonb_build_object('source', 'portfolio.trades', 'strategy', 'legacy_p2cursor_folio')
        ),
        coalesce(nullif(p_actor, ''), 'Jarvis')
    )
    RETURNING id INTO inserted_run_id;

    IF comparison_account.id IS NULL THEN
        INSERT INTO portfolio.p2cursor_reconciliation_issues (
            run_id, issue_key, issue_type, severity, client_code, p2_account_code,
            description, evidence
        )
        VALUES (
            inserted_run_id,
            'missing-comparison-account',
            'missing_comparison_account',
            'high',
            selected_client.client_code,
            p2_account.account_code,
            'No non-p2cursor comparison account exists for this client, so p2cursor positions cannot be reconciled against a current broker statement.',
            jsonb_build_array(jsonb_build_object('p2_account_code', p2_account.account_code, 'p2_position_count', p2_count))
        );
    ELSE
        WITH latest_p2 AS (
            SELECT *
            FROM (
                SELECT p.*,
                       row_number() OVER (PARTITION BY p.symbol, p.exchange, p.instrument_type ORDER BY p.as_of DESC NULLS LAST, p.id DESC) AS rn
                FROM portfolio.positions p
                WHERE p.account_id = p2_account.id
                  AND coalesce(p.quantity, 0) <> 0
            ) ranked
            WHERE rn = 1
        ),
        latest_comparison AS (
            SELECT *
            FROM (
                SELECT p.*,
                       row_number() OVER (PARTITION BY p.symbol, p.exchange, p.instrument_type ORDER BY p.as_of DESC NULLS LAST, p.id DESC) AS rn
                FROM portfolio.positions p
                WHERE p.account_id = comparison_account.id
                  AND coalesce(p.quantity, 0) <> 0
            ) ranked
            WHERE rn = 1
        ),
        joined AS (
            SELECT
                coalesce(p2.symbol, cmp.symbol) AS symbol,
                p2.quantity AS p2_quantity,
                cmp.quantity AS comparison_quantity,
                p2.average_price AS p2_average_price,
                cmp.average_price AS comparison_average_price,
                p2.as_of AS p2_as_of,
                cmp.as_of AS comparison_as_of,
                CASE
                    WHEN p2.symbol IS NOT NULL AND cmp.symbol IS NULL THEN 'missing_in_comparison'
                    WHEN p2.symbol IS NULL AND cmp.symbol IS NOT NULL THEN 'new_in_comparison'
                    WHEN abs(coalesce(p2.quantity, 0) - coalesce(cmp.quantity, 0)) > 0.0001 THEN 'quantity_mismatch'
                    ELSE NULL
                END AS issue_type
            FROM latest_p2 p2
            FULL OUTER JOIN latest_comparison cmp
              ON cmp.symbol = p2.symbol
             AND cmp.exchange = p2.exchange
             AND cmp.instrument_type = p2.instrument_type
        )
        INSERT INTO portfolio.p2cursor_reconciliation_issues (
            run_id, issue_key, issue_type, severity, client_code, symbol,
            p2_account_code, comparison_account_code, p2_quantity, comparison_quantity,
            p2_average_price, comparison_average_price, p2_as_of, comparison_as_of,
            description, evidence
        )
        SELECT
            inserted_run_id,
            lower(issue_type || '-' || symbol),
            issue_type,
            CASE issue_type
                WHEN 'quantity_mismatch' THEN 'high'
                WHEN 'missing_in_comparison' THEN 'medium'
                ELSE 'low'
            END,
            selected_client.client_code,
            symbol,
            p2_account.account_code,
            comparison_account.account_code,
            p2_quantity,
            comparison_quantity,
            p2_average_price,
            comparison_average_price,
            p2_as_of,
            comparison_as_of,
            CASE issue_type
                WHEN 'missing_in_comparison' THEN symbol || ' exists in p2cursor latest open positions but not in the comparison account.'
                WHEN 'new_in_comparison' THEN symbol || ' exists in the comparison account but not in p2cursor latest open positions.'
                WHEN 'quantity_mismatch' THEN symbol || ' quantity differs between p2cursor and the comparison account.'
            END,
            jsonb_build_array(
                jsonb_build_object('p2_account_code', p2_account.account_code, 'p2_quantity', p2_quantity, 'p2_as_of', p2_as_of),
                jsonb_build_object('comparison_account_code', comparison_account.account_code, 'comparison_quantity', comparison_quantity, 'comparison_as_of', comparison_as_of)
            )
        FROM joined
        WHERE issue_type IS NOT NULL;

        IF stale_day_count IS NOT NULL AND stale_day_count > 30 THEN
            INSERT INTO portfolio.p2cursor_reconciliation_issues (
                run_id, issue_key, issue_type, severity, client_code, p2_account_code,
                comparison_account_code, p2_as_of, comparison_as_of, description, evidence
            )
            VALUES (
                inserted_run_id,
                'stale-p2cursor-source',
                'stale_p2cursor_source',
                CASE WHEN stale_day_count > 180 THEN 'high' ELSE 'medium' END,
                selected_client.client_code,
                p2_account.account_code,
                comparison_account.account_code,
                p2_account.latest_as_of,
                comparison_account.latest_as_of,
                'P2Cursor latest position date is ' || stale_day_count::TEXT || ' days older than the comparison account.',
                jsonb_build_array(jsonb_build_object('stale_days', stale_day_count))
            )
            ON CONFLICT (run_id, issue_key) DO NOTHING;
        END IF;
    END IF;

    INSERT INTO agent.tasks (
        title, objective, owner_agent, status, priority, approval_required,
        source_kind, source_ref, output_format, evidence
    )
    VALUES (
        'P2Cursor reconciliation review #' || inserted_run_id::TEXT,
        'Review p2cursor-vs-current account reconciliation issues before using legacy p2cursor positions as current portfolio truth.',
        'Data Steward',
        CASE WHEN run_status IN ('matched') THEN 'completed' ELSE 'queued' END,
        CASE WHEN run_status IN ('blocked', 'needs_review') THEN 'high' ELSE 'medium' END,
        false,
        'portfolio.p2cursor_reconciliation_runs',
        inserted_run_id::TEXT,
        'reconciliation_review',
        jsonb_build_array(jsonb_build_object('table', 'portfolio.p2cursor_reconciliation_runs', 'id', inserted_run_id))
    );

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
    )
    SELECT
        t.id,
        'P2Cursor reconciliation ready #' || inserted_run_id::TEXT,
        'Data Steward',
        CASE WHEN run_status IN ('matched') THEN 'done' ELSE 'queued' END,
        t.priority,
        coalesce(run_notes, 'Review p2cursor reconciliation run.'),
        jsonb_build_array(jsonb_build_object('table', 'portfolio.p2cursor_reconciliation_runs', 'id', inserted_run_id)),
        'portfolio'
    FROM agent.tasks t
    WHERE t.source_kind = 'portfolio.p2cursor_reconciliation_runs'
      AND t.source_ref = inserted_run_id::TEXT
    ORDER BY t.id DESC
    LIMIT 1;

    RETURN inserted_run_id;
END;
$$;

CREATE OR REPLACE VIEW portfolio.v_p2cursor_reconciliation_latest AS
SELECT *
FROM portfolio.p2cursor_reconciliation_runs
ORDER BY created_at DESC
LIMIT 20;

CREATE OR REPLACE VIEW portfolio.v_p2cursor_reconciliation_issues AS
SELECT
    i.id,
    i.run_id,
    r.run_key,
    i.issue_key,
    i.issue_type,
    i.severity,
    i.status,
    i.client_code,
    r.client_name,
    i.symbol,
    i.p2_account_code,
    i.comparison_account_code,
    i.p2_quantity,
    i.comparison_quantity,
    i.p2_average_price,
    i.comparison_average_price,
    i.p2_as_of,
    i.comparison_as_of,
    i.description,
    i.owner_agent,
    i.evidence,
    i.created_at,
    i.updated_at
FROM portfolio.p2cursor_reconciliation_issues i
JOIN portfolio.p2cursor_reconciliation_runs r ON r.id = i.run_id
ORDER BY
    r.created_at DESC,
    CASE i.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    i.id DESC;

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources, output_targets,
    required_tools, risk_notes, prompt_template, config
)
VALUES (
    'p2cursor_reconciliation',
    'P2Cursor Client Reconciliation',
    'data_quality',
    'reconciliation',
    'data',
    'active',
    'worker_deterministic',
    'write_db',
    ARRAY['p2cursor reconciliation','reconcile p2cursor','legacy folio reconciliation','p2cursor buy sell dates'],
    ARRAY['portfolio.positions','portfolio.accounts','portfolio.clients','portfolio.trades'],
    ARRAY['portfolio.p2cursor_reconciliation_runs','portfolio.p2cursor_reconciliation_issues','agent.inbox_items'],
    ARRAY['postgres_read_model','ai_os_run_p2cursor_reconciliation'],
    'P2Cursor is legacy evidence. Reconcile against current broker/current statement rows before treating it as current truth.',
    'Compare legacy p2cursor open positions with the latest current account positions for the same client. Summarize mismatches, stale source gaps, and safe next action.',
    '{"dashboard_view":"portfolio.v_p2cursor_reconciliation_latest","issue_view":"portfolio.v_p2cursor_reconciliation_issues"}'::JSONB
)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name = EXCLUDED.skill_name,
    skill_family = EXCLUDED.skill_family,
    skill_type = EXCLUDED.skill_type,
    owner_department = EXCLUDED.owner_department,
    status = EXCLUDED.status,
    execution_mode = EXCLUDED.execution_mode,
    permission_level = EXCLUDED.permission_level,
    trigger_phrases = EXCLUDED.trigger_phrases,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    required_tools = EXCLUDED.required_tools,
    risk_notes = EXCLUDED.risk_notes,
    prompt_template = EXCLUDED.prompt_template,
    config = EXCLUDED.config,
    updated_at = now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Data Steward', 'p2cursor_reconciliation', 'expert', true, '{"default_for":"p2cursor reconciliation"}'::JSONB),
    ('Portfolio Manager', 'p2cursor_reconciliation', 'working', false, '{"default_for":"client folio history review"}'::JSONB)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_run_p2cursor_reconciliation',
    'api_write',
    'Data Steward',
    'write_db',
    true,
    'Run p2cursor-vs-current account reconciliation for a client.',
    '{"api_route":"/api/p2cursor-reconciliation/run","source_tables":["portfolio.positions","portfolio.accounts","portfolio.clients"],"destination_tables":["portfolio.p2cursor_reconciliation_runs","portfolio.p2cursor_reconciliation_issues"]}'::JSONB
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
