CREATE TABLE IF NOT EXISTS core.legacy_source_extraction_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    run_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'completed',
    p2_source_files INTEGER NOT NULL DEFAULT 0,
    p2_csv_files INTEGER NOT NULL DEFAULT 0,
    p2_staged_rows INTEGER NOT NULL DEFAULT 0,
    p2_files_need_promotion INTEGER NOT NULL DEFAULT 0,
    algo_profiled_tables INTEGER NOT NULL DEFAULT 0,
    algo_profiled_source_rows BIGINT NOT NULL DEFAULT 0,
    algo_imported_rows BIGINT NOT NULL DEFAULT 0,
    algo_partial_tables INTEGER NOT NULL DEFAULT 0,
    algo_unpromoted_tables INTEGER NOT NULL DEFAULT 0,
    high_priority_gaps INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.legacy_source_extraction_issues (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES core.legacy_source_extraction_runs(id) ON DELETE CASCADE,
    issue_key TEXT NOT NULL,
    source_family TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    source_ref TEXT NOT NULL,
    source_rows BIGINT,
    imported_rows BIGINT,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    recommended_action TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, issue_key)
);

CREATE OR REPLACE VIEW client_data.v_p2cursor_extraction_readiness AS
WITH file_rows AS (
    SELECT
        sf.id AS source_file_id,
        sf.original_path,
        sf.extracted_path,
        sf.file_type,
        sf.size_bytes,
        sf.import_status,
        sf.registered_at,
        sf.profile,
        coalesce((sf.profile ->> 'row_count')::INTEGER, 0) AS profiled_row_count,
        coalesce(rows.staged_row_count, 0)::INTEGER AS staged_row_count,
        coalesce(jsonb_array_length(sf.profile -> 'tables'), 0) AS sqlite_table_count
    FROM client_data.source_files sf
    LEFT JOIN (
        SELECT source_file_id, count(*) AS staged_row_count
        FROM client_data.p2cursor_csv_rows
        GROUP BY source_file_id
    ) rows ON rows.source_file_id = sf.id
    JOIN core.source_systems ss ON ss.id = sf.source_system_id
    WHERE ss.name = 'ps 2 cursor archive'
)
SELECT
    source_file_id,
    original_path,
    extracted_path,
    file_type,
    size_bytes,
    import_status,
    registered_at,
    profiled_row_count,
    staged_row_count,
    sqlite_table_count,
    CASE
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count AND import_status IN ('promoted','imported','mapped') THEN 'promoted'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count THEN 'staged_needs_mapping'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = 0 THEN 'missing_staging'
        WHEN file_type = 'csv' AND profiled_row_count <> staged_row_count THEN 'staging_count_mismatch'
        WHEN file_type = 'sqlite' AND sqlite_table_count > 0 THEN 'sqlite_profiled_needs_mapping'
        WHEN file_type = 'json' THEN 'reference_profiled'
        ELSE 'profiled'
    END AS readiness_status,
    CASE
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count AND import_status IN ('promoted','imported','mapped') THEN 'No immediate action.'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count THEN 'Map staged CSV rows into client/account/trade history before treating p2cursor as trusted source.'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = 0 THEN 'Run p2cursor CSV staging for this file.'
        WHEN file_type = 'csv' AND profiled_row_count <> staged_row_count THEN 'Investigate row-count mismatch between profile and staged rows.'
        WHEN file_type = 'sqlite' AND sqlite_table_count > 0 THEN 'Review SQLite tables and decide which tables become portfolio/trade/history sources.'
        WHEN file_type = 'json' THEN 'Keep as benchmark/reference artifact; link only where needed.'
        ELSE 'Review profiled p2cursor file.'
    END AS recommended_action,
    profile
FROM file_rows
ORDER BY
    CASE
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count AND import_status IN ('promoted','imported','mapped') THEN 4
        WHEN file_type = 'json' THEN 3
        ELSE 1
    END,
    original_path;

CREATE OR REPLACE VIEW core.v_algo_extraction_readiness AS
WITH source_ids AS (
    SELECT
        max(id) FILTER (WHERE name = 'algo app db') AS algo_app_db_id,
        max(id) FILTER (WHERE name = 'algo prices db') AS algo_prices_db_id,
        max(id) FILTER (WHERE name = 'algo trades db') AS algo_trades_db_id
    FROM core.source_systems
),
destinations AS (
    SELECT 'app.db' AS database_hint, 'accounts' AS table_name, count(*)::BIGINT AS imported_rows
    FROM portfolio.accounts
    WHERE broker = 'legacy_algo'
    UNION ALL
    SELECT 'app.db', 'holdings', count(*)::BIGINT
    FROM portfolio.positions p, source_ids s
    WHERE p.source_system_id = s.algo_app_db_id
    UNION ALL
    SELECT 'app.db', 'portfolio_snapshots', count(*)::BIGINT
    FROM portfolio.snapshots
    WHERE payload ->> '__source_table' = 'app.portfolio_snapshots'
    UNION ALL
    SELECT 'app.db', 'trades', count(*)::BIGINT
    FROM portfolio.trades
    WHERE external_ref LIKE 'algo_app_trades:%'
    UNION ALL
    SELECT 'trades.db', 'trades', count(*)::BIGINT
    FROM portfolio.trades
    WHERE external_ref LIKE 'algo_trades_db:%'
    UNION ALL
    SELECT 'app.db', 'journal', count(*)::BIGINT
    FROM trading.trade_journals
    WHERE external_ref LIKE 'algo_journal:%'
    UNION ALL
    SELECT 'app.db', 'tradingview_signals', count(*)::BIGINT
    FROM trading.signals
    WHERE external_ref LIKE 'algo_tradingview_signals:%'
    UNION ALL
    SELECT 'app.db', 'ideas', count(*)::BIGINT
    FROM research.ideas
    WHERE source_kind = 'algo_app_db.ideas'
    UNION ALL
    SELECT 'app.db', 'watchlist', count(*)::BIGINT
    FROM research.ideas
    WHERE source_kind = 'algo_app_db.watchlist'
    UNION ALL
    SELECT 'prices.db', 'backtest_runs', count(*)::BIGINT
    FROM strategy.backtest_runs
    WHERE external_ref LIKE 'algo_backtest_runs:%'
    UNION ALL
    SELECT 'prices.db', 'regime_runs', count(*)::BIGINT
    FROM strategy.backtest_runs
    WHERE external_ref LIKE 'algo_regime_runs:%'
    UNION ALL
    SELECT 'app.db', 'ticks', count(*)::BIGINT
    FROM trading.ticks t, source_ids s
    WHERE t.source_system_id = s.algo_app_db_id
    UNION ALL
    SELECT 'prices.db', 'daily_bars', count(*)::BIGINT
    FROM trading.ohlcv o, source_ids s
    WHERE o.source_system_id = s.algo_prices_db_id
    UNION ALL
    SELECT 'prices.db', 'live_signals', count(*)::BIGINT
    FROM trading.signals sg, source_ids s
    WHERE sg.source_system_id = s.algo_prices_db_id
    UNION ALL
    SELECT 'prices.db', 'token_map', count(*)::BIGINT
    FROM trading.symbols
    WHERE symbol IS NOT NULL
),
profile_rows AS (
    SELECT
        stp.source_system,
        stp.database_path,
        stp.table_name,
        stp.row_count::BIGINT AS source_rows,
        stp.target_tables,
        stp.import_status,
        stp.profiled_at,
        coalesce(sum(d.imported_rows), 0)::BIGINT AS imported_rows
    FROM core.v_source_table_profiles stp
    LEFT JOIN destinations d
      ON stp.table_name = d.table_name
     AND stp.database_path ILIKE '%' || d.database_hint
    GROUP BY
        stp.source_system,
        stp.database_path,
        stp.table_name,
        stp.row_count,
        stp.target_tables,
        stp.import_status,
        stp.profiled_at
)
SELECT
    source_system,
    database_path,
    table_name,
    source_rows,
    imported_rows,
    target_tables,
    import_status,
    profiled_at,
    CASE
        WHEN coalesce(source_rows, 0) = 0 THEN 'empty_source_profiled'
        WHEN imported_rows >= source_rows THEN 'promoted'
        WHEN imported_rows > 0 THEN 'partially_promoted'
        ELSE 'profiled_not_promoted'
    END AS readiness_status,
    CASE
        WHEN table_name IN ('daily_bars','ticks','straddle_snapshots','trades','tradingview_signals','backtest_runs','regime_runs','journal','ideas','watchlist','portfolio_snapshots','holdings') THEN 'high_value'
        ELSE 'supporting'
    END AS source_value,
    CASE
        WHEN coalesce(source_rows, 0) = 0 THEN 'No import required unless the source later receives rows.'
        WHEN imported_rows >= source_rows THEN 'Imported row count covers profiled source rows.'
        WHEN imported_rows > 0 THEN 'Partial import exists; review missing rows, filters, and intended exclusions.'
        ELSE 'Map and promote this table or explicitly mark it excluded with rationale.'
    END AS recommended_action
FROM profile_rows
ORDER BY
    CASE
        WHEN coalesce(source_rows, 0) = 0 THEN 4
        WHEN imported_rows >= source_rows THEN 3
        WHEN imported_rows > 0 THEN 2
        ELSE 1
    END,
    source_rows DESC NULLS LAST,
    database_path,
    table_name;

CREATE OR REPLACE VIEW core.v_legacy_source_readiness_summary AS
SELECT 'p2_source_files' AS metric, count(*)::TEXT AS value, 'P2Cursor files profiled from external SSD archive' AS interpretation
FROM client_data.v_p2cursor_extraction_readiness
UNION ALL
SELECT 'p2_staged_rows', coalesce(sum(staged_row_count), 0)::TEXT, 'P2Cursor CSV rows staged into client_data.p2cursor_csv_rows'
FROM client_data.v_p2cursor_extraction_readiness
UNION ALL
SELECT 'p2_needs_mapping_files', count(*)::TEXT, 'P2Cursor files that still need mapping/promotion or staging review'
FROM client_data.v_p2cursor_extraction_readiness
WHERE readiness_status NOT IN ('promoted','reference_profiled')
UNION ALL
SELECT 'algo_profiled_tables', count(*)::TEXT, 'Old algo SQLite tables profiled from external SSD'
FROM core.v_algo_extraction_readiness
UNION ALL
SELECT 'algo_source_rows', coalesce(sum(source_rows), 0)::TEXT, 'Rows visible in profiled old algo SQLite tables'
FROM core.v_algo_extraction_readiness
UNION ALL
SELECT 'algo_imported_rows', coalesce(sum(imported_rows), 0)::TEXT, 'Rows promoted into AI OS destination tables where mapped'
FROM core.v_algo_extraction_readiness
UNION ALL
SELECT 'algo_partial_tables', count(*)::TEXT, 'Old algo tables with partial promoted coverage'
FROM core.v_algo_extraction_readiness
WHERE readiness_status = 'partially_promoted'
UNION ALL
SELECT 'algo_unpromoted_high_value_tables', count(*)::TEXT, 'High-value old algo tables with source rows but no promoted destination rows'
FROM core.v_algo_extraction_readiness
WHERE readiness_status = 'profiled_not_promoted'
  AND source_value = 'high_value';

CREATE OR REPLACE VIEW core.v_legacy_source_extraction_runs AS
SELECT *
FROM core.legacy_source_extraction_runs
ORDER BY created_at DESC
LIMIT 20;

CREATE OR REPLACE VIEW core.v_legacy_source_extraction_issues AS
SELECT
    i.id,
    i.run_id,
    r.run_key,
    i.issue_key,
    i.source_family,
    i.issue_type,
    i.severity,
    i.status,
    i.source_ref,
    i.source_rows,
    i.imported_rows,
    i.owner_agent,
    i.recommended_action,
    i.evidence,
    i.created_at,
    i.updated_at
FROM core.legacy_source_extraction_issues i
JOIN core.legacy_source_extraction_runs r ON r.id = i.run_id
ORDER BY
    r.created_at DESC,
    CASE i.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    i.id DESC;

CREATE OR REPLACE FUNCTION core.run_legacy_source_extraction_readiness(
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_run_id BIGINT;
    p2_files INTEGER := 0;
    p2_csv_files INTEGER := 0;
    p2_rows INTEGER := 0;
    p2_needs INTEGER := 0;
    algo_tables INTEGER := 0;
    algo_rows BIGINT := 0;
    algo_imported BIGINT := 0;
    algo_partial INTEGER := 0;
    algo_unpromoted INTEGER := 0;
    high_gaps INTEGER := 0;
    run_status TEXT := 'completed';
    run_notes TEXT := 'Legacy source extraction readiness sweep completed.';
BEGIN
    SELECT
        count(*),
        count(*) FILTER (WHERE file_type = 'csv'),
        coalesce(sum(staged_row_count), 0),
        count(*) FILTER (WHERE readiness_status NOT IN ('promoted','reference_profiled'))
    INTO p2_files, p2_csv_files, p2_rows, p2_needs
    FROM client_data.v_p2cursor_extraction_readiness;

    SELECT
        count(*),
        coalesce(sum(source_rows), 0),
        coalesce(sum(imported_rows), 0),
        count(*) FILTER (WHERE readiness_status = 'partially_promoted'),
        count(*) FILTER (WHERE readiness_status = 'profiled_not_promoted' AND source_rows > 0),
        count(*) FILTER (WHERE readiness_status IN ('profiled_not_promoted','partially_promoted') AND source_value = 'high_value' AND source_rows > 0)
    INTO algo_tables, algo_rows, algo_imported, algo_partial, algo_unpromoted, high_gaps
    FROM core.v_algo_extraction_readiness;

    IF p2_needs > 0 OR high_gaps > 0 THEN
        run_status := 'needs_review';
        run_notes := 'P2Cursor and/or old algo extraction has unmapped, partially promoted, or unpromoted source surfaces. Data Steward review required before treating all legacy data as complete.';
    END IF;

    INSERT INTO core.legacy_source_extraction_runs (
        run_key, status, p2_source_files, p2_csv_files, p2_staged_rows,
        p2_files_need_promotion, algo_profiled_tables, algo_profiled_source_rows,
        algo_imported_rows, algo_partial_tables, algo_unpromoted_tables,
        high_priority_gaps, notes, evidence, created_by
    )
    VALUES (
        'legacy-source-readiness-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS'),
        run_status,
        p2_files,
        p2_csv_files,
        p2_rows,
        p2_needs,
        algo_tables,
        algo_rows,
        algo_imported,
        algo_partial,
        algo_unpromoted,
        high_gaps,
        run_notes,
        jsonb_build_array(
            jsonb_build_object('view', 'client_data.v_p2cursor_extraction_readiness'),
            jsonb_build_object('view', 'core.v_algo_extraction_readiness'),
            jsonb_build_object('view', 'core.v_legacy_source_readiness_summary')
        ),
        coalesce(nullif(p_actor, ''), 'Jarvis')
    )
    RETURNING id INTO inserted_run_id;

    INSERT INTO core.legacy_source_extraction_issues (
        run_id, issue_key, source_family, issue_type, severity,
        source_ref, source_rows, imported_rows, recommended_action, evidence
    )
    SELECT
        inserted_run_id,
        'p2cursor:' || source_file_id::TEXT || ':' || readiness_status,
        'p2cursor',
        readiness_status,
        CASE readiness_status
            WHEN 'missing_staging' THEN 'high'
            WHEN 'staging_count_mismatch' THEN 'high'
            WHEN 'sqlite_profiled_needs_mapping' THEN 'medium'
            ELSE 'medium'
        END,
        original_path,
        profiled_row_count,
        staged_row_count,
        recommended_action,
        jsonb_build_array(
            jsonb_build_object('source_file_id', source_file_id),
            jsonb_build_object('file_type', file_type),
            jsonb_build_object('import_status', import_status)
        )
    FROM client_data.v_p2cursor_extraction_readiness
    WHERE readiness_status NOT IN ('promoted','reference_profiled');

    INSERT INTO core.legacy_source_extraction_issues (
        run_id, issue_key, source_family, issue_type, severity,
        source_ref, source_rows, imported_rows, recommended_action, evidence
    )
    SELECT
        inserted_run_id,
        'algo:' || md5(database_path || ':' || table_name || ':' || readiness_status),
        'old_algo',
        readiness_status,
        CASE
            WHEN source_value = 'high_value' AND readiness_status = 'profiled_not_promoted' AND source_rows > 1000 THEN 'high'
            WHEN source_value = 'high_value' AND readiness_status IN ('profiled_not_promoted','partially_promoted') THEN 'medium'
            ELSE 'low'
        END,
        database_path || ':' || table_name,
        source_rows,
        imported_rows,
        recommended_action,
        jsonb_build_array(
            jsonb_build_object('source_system', source_system),
            jsonb_build_object('database_path', database_path),
            jsonb_build_object('table_name', table_name),
            jsonb_build_object('target_tables', target_tables),
            jsonb_build_object('source_value', source_value)
        )
    FROM core.v_algo_extraction_readiness
    WHERE source_rows > 0
      AND readiness_status IN ('profiled_not_promoted','partially_promoted');

    INSERT INTO agent.tasks (
        title, objective, owner_agent, status, priority, approval_required,
        source_kind, source_ref, output_format, evidence
    )
    VALUES (
        'Legacy source extraction readiness review #' || inserted_run_id::TEXT,
        'Review p2cursor and old algo extraction gaps before treating legacy source coverage as complete for client history, strategy research, and live dashboards.',
        'Data Steward',
        CASE WHEN run_status = 'completed' THEN 'completed' ELSE 'queued' END,
        CASE WHEN high_gaps > 0 THEN 'high' ELSE 'medium' END,
        false,
        'core.legacy_source_extraction_runs',
        inserted_run_id::TEXT,
        'legacy_source_readiness_review',
        jsonb_build_array(jsonb_build_object('table', 'core.legacy_source_extraction_runs', 'id', inserted_run_id))
    );

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
    )
    SELECT
        t.id,
        'Legacy source extraction readiness #' || inserted_run_id::TEXT,
        'Data Steward',
        CASE WHEN run_status = 'completed' THEN 'done' ELSE 'queued' END,
        t.priority,
        run_notes,
        jsonb_build_array(jsonb_build_object('table', 'core.legacy_source_extraction_runs', 'id', inserted_run_id)),
        'data'
    FROM agent.tasks t
    WHERE t.source_kind = 'core.legacy_source_extraction_runs'
      AND t.source_ref = inserted_run_id::TEXT
    ORDER BY t.id DESC
    LIMIT 1;

    RETURN inserted_run_id;
END;
$$;

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources, output_targets,
    required_tools, risk_notes, prompt_template, config
)
VALUES (
    'legacy_source_extraction_readiness',
    'Legacy Source Extraction Readiness',
    'data_quality',
    'source_readiness',
    'data',
    'active',
    'worker_deterministic',
    'write_db',
    ARRAY['legacy source readiness','p2cursor extraction readiness','old algo extraction readiness','harden p2cursor','harden old algo'],
    ARRAY['client_data.source_files','client_data.p2cursor_csv_rows','core.source_table_profiles'],
    ARRAY['core.legacy_source_extraction_runs','core.legacy_source_extraction_issues','agent.inbox_items'],
    ARRAY['postgres_read_model','ai_os_run_legacy_source_readiness'],
    'Legacy systems are evidence sources, not current truth. Promote only mapped rows with lineage and reconciliation.',
    'Audit p2cursor and old algo source coverage. Separate profiled, staged, promoted, partial, and unmapped surfaces. Queue Data Steward actions for incomplete coverage.',
    '{"summary_view":"core.v_legacy_source_readiness_summary","p2_view":"client_data.v_p2cursor_extraction_readiness","algo_view":"core.v_algo_extraction_readiness","issue_view":"core.v_legacy_source_extraction_issues"}'::JSONB
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
    ('Data Steward', 'legacy_source_extraction_readiness', 'expert', true, '{"default_for":"legacy source hardening"}'::JSONB),
    ('Jarvis', 'legacy_source_extraction_readiness', 'working', false, '{"routes_to":"Data Steward"}'::JSONB)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency = EXCLUDED.proficiency,
    is_primary = EXCLUDED.is_primary,
    activation_rules = EXCLUDED.activation_rules,
    updated_at = now();

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'ai_os_legacy_source_readiness',
        'mcp_read',
        'Data Steward',
        'read_db',
        true,
        'Read p2cursor and old algo extraction readiness summary, file/table status, and extraction issues.',
        '{"views":["core.v_legacy_source_readiness_summary","client_data.v_p2cursor_extraction_readiness","core.v_algo_extraction_readiness","core.v_legacy_source_extraction_issues"]}'::JSONB
    ),
    (
        'ai_os_run_legacy_source_readiness',
        'api_write',
        'Data Steward',
        'write_db',
        true,
        'Run a legacy source extraction readiness sweep and queue Data Steward review items.',
        '{"api_route":"/api/legacy-source-readiness/run","destination_tables":["core.legacy_source_extraction_runs","core.legacy_source_extraction_issues","agent.inbox_items"]}'::JSONB
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

