CREATE TABLE IF NOT EXISTS agent.legacy_activity_events (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    source_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    legacy_id BIGINT NOT NULL,
    event_ts TIMESTAMPTZ,
    event_kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    severity TEXT NOT NULL DEFAULT 'info',
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    production_authority BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, legacy_id)
);

CREATE INDEX IF NOT EXISTS idx_legacy_activity_events_ts
    ON agent.legacy_activity_events (event_ts DESC);

CREATE TABLE IF NOT EXISTS portfolio.legacy_cashflows (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    source_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    legacy_id BIGINT NOT NULL,
    legacy_account_id BIGINT,
    account_code TEXT,
    cashflow_ts TIMESTAMPTZ NOT NULL,
    cashflow_kind TEXT NOT NULL,
    amount NUMERIC NOT NULL,
    notes TEXT,
    symbol TEXT,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    production_authority BOOLEAN NOT NULL DEFAULT false,
    mapping_status TEXT NOT NULL DEFAULT 'archived',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, legacy_id),
    CONSTRAINT legacy_cashflows_mapping_status_check CHECK (
        mapping_status IN ('archived','demo_excluded','mapped_pending_approval','promoted')
    )
);

CREATE INDEX IF NOT EXISTS idx_legacy_cashflows_ts
    ON portfolio.legacy_cashflows (cashflow_ts DESC);

CREATE TABLE IF NOT EXISTS strategy.legacy_signal_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    source_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    legacy_id BIGINT NOT NULL,
    as_of DATE,
    run_at TIMESTAMPTZ,
    strategy_name TEXT,
    deploy_now BOOLEAN,
    regime_state TEXT,
    risk_off BOOLEAN,
    holding_count INTEGER,
    payload JSONB NOT NULL,
    research_only BOOLEAN NOT NULL DEFAULT true,
    execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, legacy_id),
    CONSTRAINT legacy_signal_snapshots_no_execution CHECK (execution_allowed = false)
);

CREATE INDEX IF NOT EXISTS idx_legacy_signal_snapshots_as_of
    ON strategy.legacy_signal_snapshots (as_of DESC, run_at DESC);

CREATE TABLE IF NOT EXISTS trading.legacy_token_map (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT NOT NULL REFERENCES core.source_systems(id),
    source_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    legacy_id BIGINT NOT NULL,
    symbol TEXT NOT NULL,
    instrument_token TEXT,
    exchange_token TEXT,
    tradingsymbol TEXT,
    exchange TEXT,
    instrument_type TEXT,
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    production_authority BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system_id, legacy_id)
);

CREATE INDEX IF NOT EXISTS idx_legacy_token_map_symbol
    ON trading.legacy_token_map (symbol, exchange);

CREATE TABLE IF NOT EXISTS core.legacy_source_table_resolutions (
    id BIGSERIAL PRIMARY KEY,
    source_system TEXT NOT NULL,
    table_name TEXT NOT NULL,
    resolution_mode TEXT NOT NULL,
    canonical_relation TEXT,
    source_value TEXT NOT NULL DEFAULT 'supporting',
    rationale TEXT NOT NULL,
    execution_allowed BOOLEAN NOT NULL DEFAULT false,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    reviewed_by TEXT NOT NULL DEFAULT 'Data Steward',
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system, table_name),
    CONSTRAINT legacy_source_resolution_mode_check CHECK (
        resolution_mode IN ('exact_promote','deduplicated_promote','governed_archive','empty_no_action')
    ),
    CONSTRAINT legacy_source_resolution_no_execution CHECK (execution_allowed = false)
);

INSERT INTO core.legacy_source_table_resolutions (
    source_system, table_name, resolution_mode, canonical_relation, source_value, rationale, evidence
)
VALUES
    ('algo app db','accounts','exact_promote','portfolio.accounts','high_value','Legacy accounts remain lineage-bearing source accounts; no execution authority is inherited.','[{"source":"app.db.accounts"}]'::jsonb),
    ('algo app db','agent_events','governed_archive','agent.legacy_activity_events','supporting','Historical runtime telemetry is preserved for audit and learning without entering the current agent event stream.','[{"source":"app.db.agent_events"}]'::jsonb),
    ('algo app db','cashflows','governed_archive','portfolio.legacy_cashflows','high_value','Legacy cashflows are preserved without affecting client NAV until account and client mapping is explicitly approved.','[{"source":"app.db.cashflows"}]'::jsonb),
    ('algo app db','holdings','exact_promote','portfolio.positions','high_value','Legacy holdings are promoted with source-system lineage and remain separate from current broker truth.','[{"source":"app.db.holdings"}]'::jsonb),
    ('algo app db','ideas','exact_promote','research.ideas','high_value','Legacy ideas are research evidence and do not create positions or orders.','[{"source":"app.db.ideas"}]'::jsonb),
    ('algo app db','journal','exact_promote','trading.trade_journals','high_value','Legacy journal entries are retained as immutable learning evidence.','[{"source":"app.db.journal"}]'::jsonb),
    ('algo app db','option_chain_snapshots','empty_no_action',NULL,'high_value','The profiled source table is empty; no import is required.','[{"source":"app.db.option_chain_snapshots"}]'::jsonb),
    ('algo app db','portfolio_snapshots','exact_promote','portfolio.snapshots','high_value','Legacy portfolio snapshots are historical observations, not current marks.','[{"source":"app.db.portfolio_snapshots"}]'::jsonb),
    ('algo app db','saved_strategies','empty_no_action',NULL,'high_value','The profiled source table is empty; no import is required.','[{"source":"app.db.saved_strategies"}]'::jsonb),
    ('algo app db','straddle_snapshots','deduplicated_promote','trading.option_strategy_snapshots','high_value','Validated straddle observations are canonicalized by timestamp, underlying, expiry, strategy, and strike.','[{"dataset_key":"legacy_algo_straddles"}]'::jsonb),
    ('algo app db','strangle_snapshots','empty_no_action',NULL,'high_value','The profiled source table is empty; no import is required.','[{"source":"app.db.strangle_snapshots"}]'::jsonb),
    ('algo app db','ticks','deduplicated_promote','trading.ticks','high_value','All valid source ticks are represented by a canonical timestamp and symbol row; duplicates remain counted in import evidence.','[{"dataset_key":"legacy_algo_ticks"}]'::jsonb),
    ('algo app db','trades','exact_promote','portfolio.trades','high_value','Legacy app trades are historical executions with source-scoped external references.','[{"source":"app.db.trades"}]'::jsonb),
    ('algo app db','tradingview_signals','exact_promote','trading.signals','high_value','Legacy TradingView signals are retained as source evidence and cannot bypass approvals.','[{"source":"app.db.tradingview_signals"}]'::jsonb),
    ('algo app db','watchlist','exact_promote','research.ideas','high_value','Legacy watchlist names are retained as research ideas only.','[{"source":"app.db.watchlist"}]'::jsonb),
    ('algo prices db','backtest_runs','exact_promote','strategy.backtest_runs','high_value','Legacy backtest results are evidence with original diagnostics and are not promotion approvals.','[{"source":"prices.db.backtest_runs"}]'::jsonb),
    ('algo prices db','daily_bars','deduplicated_promote','trading.ohlcv','high_value','Validated daily bars are canonicalized by symbol, date, and timeframe with quality evidence.','[{"dataset_key":"legacy_algo_daily_ohlcv"}]'::jsonb),
    ('algo prices db','live_signals','governed_archive','strategy.legacy_signal_snapshots','high_value','Dated generated books are preserved as research-only signal snapshots with execution disabled.','[{"source":"prices.db.live_signals"}]'::jsonb),
    ('algo prices db','regime_runs','exact_promote','strategy.backtest_runs','high_value','Legacy regime runs are preserved in backtest evidence and do not represent live state.','[{"source":"prices.db.regime_runs"}]'::jsonb),
    ('algo prices db','token_map','governed_archive','trading.legacy_token_map','supporting','Legacy broker token mappings are preserved but cannot become current routing truth without refresh.','[{"source":"prices.db.token_map"}]'::jsonb),
    ('algo trades db','trades','exact_promote','portfolio.trades','high_value','The standalone trade journal record is retained with source-scoped lineage.','[{"source":"trades.db.trades"}]'::jsonb)
ON CONFLICT (source_system, table_name) DO UPDATE SET
    resolution_mode = EXCLUDED.resolution_mode,
    canonical_relation = EXCLUDED.canonical_relation,
    source_value = EXCLUDED.source_value,
    rationale = EXCLUDED.rationale,
    execution_allowed = EXCLUDED.execution_allowed,
    evidence = EXCLUDED.evidence,
    reviewed_by = EXCLUDED.reviewed_by,
    reviewed_at = now();

UPDATE core.source_table_profiles profile
SET database_path = source.location,
    target_tables = CASE
        WHEN resolution.canonical_relation IS NULL THEN '{}'::text[]
        ELSE ARRAY[resolution.canonical_relation]
    END,
    profiled_at = now()
FROM core.source_systems source
JOIN core.legacy_source_table_resolutions resolution
  ON resolution.source_system = source.name
WHERE profile.source_system_id = source.id
  AND profile.table_name = resolution.table_name
  AND (
      profile.database_path IS DISTINCT FROM source.location
      OR profile.target_tables IS DISTINCT FROM CASE
          WHEN resolution.canonical_relation IS NULL THEN '{}'::text[]
          ELSE ARRAY[resolution.canonical_relation]
      END
  );

CREATE OR REPLACE VIEW core.v_algo_extraction_readiness AS
WITH source_ids AS (
    SELECT
        max(id) FILTER (WHERE name = 'algo app db') AS algo_app_db_id,
        max(id) FILTER (WHERE name = 'algo prices db') AS algo_prices_db_id
    FROM core.source_systems
),
latest_market_runs AS (
    SELECT DISTINCT ON (dataset_key)
        dataset_key,
        source_rows,
        valid_rows,
        rejected_rows,
        deduplicated_rows,
        rows_touched,
        warehouse_rows_after,
        status,
        quality_status,
        source_hash,
        id AS import_run_id
    FROM market.market_data_import_runs
    WHERE status IN ('completed','completed_with_warnings')
    ORDER BY dataset_key, id DESC
),
destinations AS (
    SELECT 'algo app db' source_system, 'accounts' table_name, count(*)::bigint imported_rows, 0::bigint deduplicated_rows, 0::bigint rejected_rows
    FROM portfolio.accounts WHERE broker = 'legacy_algo'
    UNION ALL SELECT 'algo app db','agent_events',count(*),0,0 FROM agent.legacy_activity_events event, source_ids source WHERE event.source_system_id = source.algo_app_db_id
    UNION ALL SELECT 'algo app db','cashflows',count(*),0,0 FROM portfolio.legacy_cashflows flow, source_ids source WHERE flow.source_system_id = source.algo_app_db_id
    UNION ALL SELECT 'algo app db','holdings',count(*),0,0 FROM portfolio.positions position, source_ids source WHERE position.source_system_id = source.algo_app_db_id
    UNION ALL SELECT 'algo app db','ideas',count(*),0,0 FROM research.ideas WHERE source_kind = 'algo_app_db.ideas'
    UNION ALL SELECT 'algo app db','journal',count(*),0,0 FROM trading.trade_journals WHERE external_ref LIKE 'algo_journal:%'
    UNION ALL SELECT 'algo app db','portfolio_snapshots',count(*),0,0 FROM portfolio.snapshots WHERE payload ->> '__source_table' = 'app.portfolio_snapshots'
    UNION ALL SELECT 'algo app db','trades',count(*),0,0 FROM portfolio.trades WHERE external_ref LIKE 'algo_app_trades:%'
    UNION ALL SELECT 'algo app db','tradingview_signals',count(*),0,0 FROM trading.signals WHERE external_ref LIKE 'algo_tradingview_signals:%'
    UNION ALL SELECT 'algo app db','watchlist',count(*),0,0 FROM research.ideas WHERE source_kind = 'algo_app_db.watchlist'
    UNION ALL SELECT 'algo prices db','backtest_runs',count(*),0,0 FROM strategy.backtest_runs WHERE external_ref LIKE 'algo_backtest_runs:%'
    UNION ALL SELECT 'algo prices db','live_signals',count(*),0,0 FROM strategy.legacy_signal_snapshots signal, source_ids source WHERE signal.source_system_id = source.algo_prices_db_id
    UNION ALL SELECT 'algo prices db','regime_runs',count(*),0,0 FROM strategy.backtest_runs WHERE external_ref LIKE 'algo_regime_runs:%'
    UNION ALL SELECT 'algo prices db','token_map',count(*),0,0 FROM trading.legacy_token_map token, source_ids source WHERE token.source_system_id = source.algo_prices_db_id
    UNION ALL SELECT 'algo trades db','trades',count(*),0,0 FROM portfolio.trades WHERE external_ref LIKE 'algo_trades_db:%'
    UNION ALL SELECT 'algo app db','straddle_snapshots',coalesce(rows_touched,0),coalesce(deduplicated_rows,0),coalesce(rejected_rows,0) FROM latest_market_runs WHERE dataset_key = 'legacy_algo_straddles'
    UNION ALL SELECT 'algo app db','ticks',coalesce(rows_touched,0),coalesce(deduplicated_rows,0),coalesce(rejected_rows,0) FROM latest_market_runs WHERE dataset_key = 'legacy_algo_ticks'
    UNION ALL SELECT 'algo prices db','daily_bars',coalesce(rows_touched,0),coalesce(deduplicated_rows,0),coalesce(rejected_rows,0) FROM latest_market_runs WHERE dataset_key = 'legacy_algo_daily_ohlcv'
),
profile_rows AS (
    SELECT
        profile.source_system,
        profile.database_path,
        profile.table_name,
        profile.row_count::bigint AS source_rows,
        profile.target_tables,
        profile.import_status,
        profile.profiled_at,
        resolution.resolution_mode,
        resolution.canonical_relation,
        resolution.source_value,
        resolution.rationale,
        resolution.evidence AS resolution_evidence,
        coalesce(destination.imported_rows, 0)::bigint AS imported_rows,
        coalesce(destination.deduplicated_rows, 0)::bigint AS deduplicated_rows,
        coalesce(destination.rejected_rows, 0)::bigint AS rejected_rows
    FROM core.v_source_table_profiles profile
    LEFT JOIN core.legacy_source_table_resolutions resolution
      ON resolution.source_system = profile.source_system
     AND resolution.table_name = profile.table_name
    LEFT JOIN destinations destination
      ON destination.source_system = profile.source_system
     AND destination.table_name = profile.table_name
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
        WHEN coalesce(source_rows, 0) = 0 AND resolution_mode = 'empty_no_action' THEN 'empty_source_profiled'
        WHEN imported_rows + deduplicated_rows + rejected_rows >= source_rows AND resolution_mode = 'deduplicated_promote' THEN 'promoted_deduplicated'
        WHEN imported_rows >= source_rows AND resolution_mode = 'governed_archive' THEN 'archived_governed'
        WHEN imported_rows >= source_rows AND resolution_mode = 'exact_promote' THEN 'promoted'
        WHEN imported_rows > 0 OR deduplicated_rows > 0 OR rejected_rows > 0 THEN 'partially_promoted'
        ELSE 'profiled_not_promoted'
    END AS readiness_status,
    coalesce(source_value, 'supporting') AS source_value,
    CASE
        WHEN resolution_mode IS NULL THEN 'Classify this source table before promotion.'
        WHEN coalesce(source_rows, 0) = 0 AND resolution_mode = 'empty_no_action' THEN 'No import required unless the source later receives rows.'
        WHEN imported_rows + deduplicated_rows + rejected_rows >= source_rows THEN rationale
        WHEN imported_rows > 0 OR deduplicated_rows > 0 OR rejected_rows > 0 THEN 'Complete the governed destination import and reconcile remaining source rows.'
        ELSE 'Run the governed legacy importer for the approved destination.'
    END AS recommended_action,
    deduplicated_rows,
    rejected_rows,
    imported_rows + deduplicated_rows + rejected_rows AS resolved_rows,
    resolution_mode,
    canonical_relation,
    resolution_evidence
FROM profile_rows
ORDER BY
    CASE
        WHEN coalesce(source_rows, 0) = 0 THEN 5
        WHEN imported_rows + deduplicated_rows + rejected_rows >= source_rows THEN 4
        WHEN imported_rows > 0 OR deduplicated_rows > 0 OR rejected_rows > 0 THEN 2
        ELSE 1
    END,
    source_rows DESC NULLS LAST,
    database_path,
    table_name;

CREATE OR REPLACE VIEW core.v_legacy_source_readiness_summary AS
SELECT 'p2_source_files' AS metric, count(*)::text AS value, 'P2Cursor files profiled from external SSD archive' AS interpretation
FROM client_data.v_p2cursor_extraction_readiness
UNION ALL SELECT 'p2_staged_rows', coalesce(sum(staged_row_count), 0)::text, 'P2Cursor CSV rows staged into client_data.p2cursor_csv_rows' FROM client_data.v_p2cursor_extraction_readiness
UNION ALL SELECT 'p2_needs_mapping_files', count(*)::text, 'P2Cursor files that still need mapping, promotion, or staging review' FROM client_data.v_p2cursor_extraction_readiness WHERE readiness_status NOT IN ('promoted','reference_profiled','duplicate_reference','excluded_nonproduction','empty_profiled')
UNION ALL SELECT 'algo_profiled_tables', count(*)::text, 'Old algo SQLite tables profiled from external SSD' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_source_rows', coalesce(sum(source_rows), 0)::text, 'Rows visible in profiled old algo SQLite tables' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_canonical_rows', coalesce(sum(imported_rows), 0)::text, 'Rows in canonical or governed archive destinations' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_deduplicated_rows', coalesce(sum(deduplicated_rows), 0)::text, 'Valid duplicate source observations represented by canonical destination rows' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_rejected_rows', coalesce(sum(rejected_rows), 0)::text, 'Source rows rejected by explicit quality rules' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_resolved_rows', coalesce(sum(resolved_rows), 0)::text, 'Source rows accounted for by promotion, governed archival, deduplication, or rejection' FROM core.v_algo_extraction_readiness
UNION ALL SELECT 'algo_partial_tables', count(*)::text, 'Old algo tables with partial resolved coverage' FROM core.v_algo_extraction_readiness WHERE readiness_status = 'partially_promoted'
UNION ALL SELECT 'algo_unpromoted_high_value_tables', count(*)::text, 'High-value old algo tables with source rows and no resolved destination' FROM core.v_algo_extraction_readiness WHERE readiness_status = 'profiled_not_promoted' AND source_value = 'high_value';

CREATE OR REPLACE FUNCTION core.refresh_legacy_source_profile_statuses()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    WITH updates AS (
        SELECT
            source.id AS source_system_id,
            readiness.table_name,
            readiness.database_path,
            CASE readiness.readiness_status
                WHEN 'promoted' THEN 'promoted'
                WHEN 'promoted_deduplicated' THEN 'promoted_deduplicated'
                WHEN 'archived_governed' THEN 'archived_governed'
                WHEN 'empty_source_profiled' THEN 'empty_profiled'
                WHEN 'partially_promoted' THEN 'partially_promoted'
                ELSE 'profiled'
            END AS import_status
        FROM core.v_algo_extraction_readiness readiness
        JOIN core.source_systems source ON source.name = readiness.source_system
    )
    UPDATE core.source_table_profiles profile
    SET import_status = updates.import_status,
        profiled_at = now()
    FROM updates
    WHERE profile.source_system_id = updates.source_system_id
      AND profile.database_path = updates.database_path
      AND profile.table_name = updates.table_name
      AND profile.import_status IS DISTINCT FROM updates.import_status;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$;

CREATE OR REPLACE FUNCTION core.run_legacy_source_extraction_readiness(
    p_actor TEXT DEFAULT 'Jarvis'
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    inserted_run_id BIGINT;
    inserted_task_id BIGINT;
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
    run_notes TEXT := 'Legacy source extraction readiness sweep completed with all governed terminal outcomes accounted for.';
BEGIN
    SELECT
        count(*),
        count(*) FILTER (WHERE file_type = 'csv'),
        coalesce(sum(staged_row_count), 0),
        count(*) FILTER (
            WHERE readiness_status NOT IN (
                'promoted','reference_profiled','duplicate_reference',
                'excluded_nonproduction','empty_profiled'
            )
        )
    INTO p2_files, p2_csv_files, p2_rows, p2_needs
    FROM client_data.v_p2cursor_extraction_readiness;

    SELECT
        count(*),
        coalesce(sum(source_rows), 0),
        coalesce(sum(imported_rows), 0),
        count(*) FILTER (WHERE readiness_status = 'partially_promoted'),
        count(*) FILTER (WHERE readiness_status = 'profiled_not_promoted' AND source_rows > 0),
        count(*) FILTER (
            WHERE readiness_status IN ('profiled_not_promoted','partially_promoted')
              AND source_value = 'high_value'
              AND source_rows > 0
        )
    INTO algo_tables, algo_rows, algo_imported, algo_partial, algo_unpromoted, high_gaps
    FROM core.v_algo_extraction_readiness;

    IF p2_needs > 0 OR high_gaps > 0 THEN
        run_status := 'needs_review';
        run_notes := 'One or more legacy source surfaces lack a governed terminal outcome. Data Steward review is required.';
    END IF;

    INSERT INTO core.legacy_source_extraction_runs (
        run_key, status, p2_source_files, p2_csv_files, p2_staged_rows,
        p2_files_need_promotion, algo_profiled_tables, algo_profiled_source_rows,
        algo_imported_rows, algo_partial_tables, algo_unpromoted_tables,
        high_priority_gaps, notes, evidence, created_by
    ) VALUES (
        'legacy-source-readiness-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS'),
        run_status, p2_files, p2_csv_files, p2_rows, p2_needs,
        algo_tables, algo_rows, algo_imported, algo_partial, algo_unpromoted,
        high_gaps, run_notes,
        jsonb_build_array(
            jsonb_build_object('view', 'client_data.v_p2cursor_extraction_readiness'),
            jsonb_build_object('view', 'core.v_algo_extraction_readiness'),
            jsonb_build_object('view', 'core.v_legacy_source_readiness_summary'),
            jsonb_build_object('terminal_p2_statuses', jsonb_build_array(
                'promoted','reference_profiled','duplicate_reference',
                'excluded_nonproduction','empty_profiled'
            ))
        ),
        coalesce(nullif(p_actor, ''), 'Jarvis')
    ) RETURNING id INTO inserted_run_id;

    INSERT INTO core.legacy_source_extraction_issues (
        run_id, issue_key, source_family, issue_type, severity,
        source_ref, source_rows, imported_rows, recommended_action, evidence
    )
    SELECT
        inserted_run_id,
        'p2cursor:' || source_file_id::text || ':' || readiness_status,
        'p2cursor', readiness_status,
        CASE readiness_status
            WHEN 'missing_staging' THEN 'high'
            WHEN 'staging_count_mismatch' THEN 'high'
            ELSE 'medium'
        END,
        original_path, profiled_row_count, staged_row_count,
        recommended_action,
        jsonb_build_array(
            jsonb_build_object('source_file_id', source_file_id),
            jsonb_build_object('file_type', file_type),
            jsonb_build_object('import_status', import_status)
        )
    FROM client_data.v_p2cursor_extraction_readiness
    WHERE readiness_status NOT IN (
        'promoted','reference_profiled','duplicate_reference',
        'excluded_nonproduction','empty_profiled'
    );

    INSERT INTO core.legacy_source_extraction_issues (
        run_id, issue_key, source_family, issue_type, severity,
        source_ref, source_rows, imported_rows, recommended_action, evidence
    )
    SELECT
        inserted_run_id,
        'algo:' || md5(database_path || ':' || table_name || ':' || readiness_status),
        'old_algo', readiness_status,
        CASE
            WHEN source_value = 'high_value' AND readiness_status = 'profiled_not_promoted' AND source_rows > 1000 THEN 'high'
            WHEN source_value = 'high_value' THEN 'medium'
            ELSE 'low'
        END,
        database_path || ':' || table_name,
        source_rows, imported_rows, recommended_action,
        jsonb_build_array(
            jsonb_build_object('source_system', source_system),
            jsonb_build_object('resolution_mode', resolution_mode),
            jsonb_build_object('resolved_rows', resolved_rows),
            jsonb_build_object('deduplicated_rows', deduplicated_rows),
            jsonb_build_object('rejected_rows', rejected_rows)
        )
    FROM core.v_algo_extraction_readiness
    WHERE source_rows > 0
      AND readiness_status IN ('profiled_not_promoted','partially_promoted');

    INSERT INTO agent.tasks (
        title, objective, owner_agent, status, priority, approval_required,
        source_kind, source_ref, output_format, evidence
    ) VALUES (
        'Legacy source extraction readiness review #' || inserted_run_id::text,
        'Verify governed terminal outcomes for P2Cursor and old algo sources before using legacy evidence in client, research, or strategy workflows.',
        'Data Steward',
        CASE WHEN run_status = 'completed' THEN 'completed' ELSE 'queued' END,
        CASE WHEN high_gaps > 0 THEN 'high' ELSE 'medium' END,
        false, 'core.legacy_source_extraction_runs', inserted_run_id::text,
        'legacy_source_readiness_review',
        jsonb_build_array(jsonb_build_object('table', 'core.legacy_source_extraction_runs', 'id', inserted_run_id))
    ) RETURNING id INTO inserted_task_id;

    INSERT INTO agent.inbox_items (
        task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace
    ) VALUES (
        inserted_task_id,
        'Legacy source extraction readiness #' || inserted_run_id::text,
        'Data Steward',
        CASE WHEN run_status = 'completed' THEN 'done' ELSE 'queued' END,
        CASE WHEN high_gaps > 0 THEN 'high' ELSE 'medium' END,
        run_notes,
        jsonb_build_array(jsonb_build_object('table', 'core.legacy_source_extraction_runs', 'id', inserted_run_id)),
        'data'
    );

    RETURN inserted_run_id;
END;
$$;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES (
    'ai_os_legacy_source_resolution_board',
    'mcp_read',
    'Data Steward',
    'read_db',
    true,
    'Read per-table legacy source resolution modes, canonical counts, deduplication, rejection, and remaining gaps.',
    '{"view":"core.v_algo_extraction_readiness","execution_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
