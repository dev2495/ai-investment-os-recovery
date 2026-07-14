CREATE SCHEMA IF NOT EXISTS market;

CREATE TABLE IF NOT EXISTS market.dataset_contracts (
    dataset_key TEXT PRIMARY KEY,
    source_key TEXT NOT NULL REFERENCES core.data_source_registry(source_key),
    target_relation TEXT NOT NULL,
    grain TEXT NOT NULL,
    timezone_assumption TEXT,
    price_adjustment_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (price_adjustment_status IN ('unknown', 'raw_unadjusted', 'source_adjusted_unverified', 'corporate_action_verified')),
    point_in_time_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (point_in_time_status IN ('unverified', 'partial', 'verified')),
    survivorship_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (survivorship_status IN ('unverified', 'current_universe_bias', 'partial', 'verified')),
    execution_allowed BOOLEAN NOT NULL DEFAULT false,
    research_allowed BOOLEAN NOT NULL DEFAULT true,
    limitations JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_agent TEXT NOT NULL DEFAULT 'Data Steward',
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT dataset_contracts_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(limitations))
);

CREATE TABLE IF NOT EXISTS market.market_data_import_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    batch_key TEXT NOT NULL,
    dataset_key TEXT NOT NULL REFERENCES market.dataset_contracts(dataset_key),
    source_key TEXT NOT NULL REFERENCES core.data_source_registry(source_key),
    source_system_id BIGINT REFERENCES core.source_systems(id),
    core_import_run_id BIGINT REFERENCES core.import_runs(id),
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'completed_with_warnings', 'failed')),
    source_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    source_rows BIGINT NOT NULL DEFAULT 0,
    valid_rows BIGINT NOT NULL DEFAULT 0,
    rejected_rows BIGINT NOT NULL DEFAULT 0,
    corrected_rows BIGINT NOT NULL DEFAULT 0,
    rows_touched BIGINT NOT NULL DEFAULT 0,
    rows_inserted BIGINT NOT NULL DEFAULT 0,
    warehouse_rows_after BIGINT NOT NULL DEFAULT 0,
    symbol_count INTEGER NOT NULL DEFAULT 0,
    first_ts TIMESTAMPTZ,
    last_ts TIMESTAMPTZ,
    quality_status TEXT NOT NULL DEFAULT 'not_checked'
        CHECK (quality_status IN ('not_checked', 'passed', 'passed_with_warnings', 'failed')),
    quality_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    requested_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT market_data_import_runs_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(quality_summary))
);

CREATE INDEX IF NOT EXISTS idx_market_data_import_runs_dataset
    ON market.market_data_import_runs (dataset_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_import_runs_batch
    ON market.market_data_import_runs (batch_key, created_at DESC);

ALTER TABLE market.market_data_import_runs
    ADD COLUMN IF NOT EXISTS deduplicated_rows BIGINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS market.market_data_quality_checks (
    id BIGSERIAL PRIMARY KEY,
    import_run_id BIGINT NOT NULL REFERENCES market.market_data_import_runs(id) ON DELETE CASCADE,
    check_key TEXT NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('passed', 'warning', 'failed')),
    observed_value NUMERIC,
    threshold_value NUMERIC,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by TEXT NOT NULL DEFAULT 'Data Quality Agent',
    UNIQUE (import_run_id, check_key),
    CONSTRAINT market_data_quality_checks_no_raw_secrets CHECK (NOT core.jsonb_contains_raw_secret(details))
);

CREATE TABLE IF NOT EXISTS trading.option_strategy_snapshots (
    ts TIMESTAMPTZ NOT NULL,
    underlying TEXT NOT NULL,
    exchange TEXT NOT NULL DEFAULT 'NSE',
    expiry DATE NOT NULL,
    strategy_type TEXT NOT NULL,
    reference_strike NUMERIC NOT NULL,
    call_price NUMERIC,
    put_price NUMERIC,
    net_premium NUMERIC,
    spot_price NUMERIC,
    implied_volatility NUMERIC,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_artifact_id BIGINT REFERENCES core.raw_artifacts(id),
    source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, underlying, expiry, strategy_type, reference_strike),
    CONSTRAINT option_strategy_snapshots_nonnegative CHECK (
        coalesce(call_price, 0) >= 0 AND coalesce(put_price, 0) >= 0
        AND coalesce(net_premium, 0) >= 0 AND coalesce(spot_price, 0) >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_option_strategy_snapshots_underlying_ts
    ON trading.option_strategy_snapshots (underlying, ts DESC);

INSERT INTO market.dataset_contracts (
    dataset_key, source_key, target_relation, grain, timezone_assumption,
    price_adjustment_status, point_in_time_status, survivorship_status,
    execution_allowed, research_allowed, limitations, owner_agent, updated_at
) VALUES
(
    'legacy_algo_daily_ohlcv', 'algo_trading_archive', 'trading.ohlcv', 'symbol x trading day',
    'source dates materialize at 00:00 UTC', 'source_adjusted_unverified', 'partial', 'current_universe_bias',
    false, true,
    '["Corporate-action adjustment provenance is not supplied by the legacy database.","Universe construction is not point-in-time complete.","Use for research and hypothesis testing with caveats; not for production capital decisions."]'::jsonb,
    'Market Data Engineer', now()
),
(
    'legacy_algo_ticks', 'algo_trading_archive', 'trading.ticks', 'symbol x source timestamp',
    'source timestamps are interpreted as UTC based on observed NSE market-hour alignment', 'raw_unadjusted', 'partial', 'partial',
    false, true,
    '["Two trading days across 14 symbols do not support broad intraday validation.","Volume and OI fields retain source semantics."]'::jsonb,
    'Market Data Engineer', now()
),
(
    'legacy_algo_straddles', 'algo_trading_archive', 'trading.option_strategy_snapshots', 'underlying x expiry x strike x timestamp',
    'source timestamps are interpreted as UTC based on observed NSE market-hour alignment', 'raw_unadjusted', 'partial', 'partial',
    false, true,
    '["Single-underlying NIFTY sample over a short interval.","No full option-chain or contract-master snapshot accompanies the source."]'::jsonb,
    'Options Data Engineer', now()
)
ON CONFLICT (dataset_key) DO UPDATE SET
    source_key = EXCLUDED.source_key,
    target_relation = EXCLUDED.target_relation,
    grain = EXCLUDED.grain,
    timezone_assumption = EXCLUDED.timezone_assumption,
    price_adjustment_status = EXCLUDED.price_adjustment_status,
    point_in_time_status = EXCLUDED.point_in_time_status,
    survivorship_status = EXCLUDED.survivorship_status,
    execution_allowed = false,
    research_allowed = EXCLUDED.research_allowed,
    limitations = EXCLUDED.limitations,
    owner_agent = EXCLUDED.owner_agent,
    updated_at = now();

CREATE OR REPLACE VIEW market.v_market_data_import_runs AS
SELECT
    run.id,
    run.run_key,
    run.batch_key,
    run.dataset_key,
    run.source_key,
    run.source_system_id,
    run.core_import_run_id,
    run.raw_artifact_id,
    run.status,
    run.source_path,
    run.source_hash,
    run.source_rows,
    run.valid_rows,
    run.rejected_rows,
    run.corrected_rows,
    run.rows_touched,
    run.rows_inserted,
    run.warehouse_rows_after,
    run.symbol_count,
    run.first_ts,
    run.last_ts,
    run.quality_status,
    run.quality_summary,
    run.error_message,
    run.started_at,
    run.finished_at,
    run.requested_by,
    run.created_at,
    contract.target_relation,
    contract.grain,
    contract.price_adjustment_status,
    contract.point_in_time_status,
    contract.survivorship_status,
    contract.execution_allowed,
    artifact.title AS artifact_title,
    artifact.local_path AS artifact_path,
    run.deduplicated_rows
FROM market.market_data_import_runs run
JOIN market.dataset_contracts contract ON contract.dataset_key = run.dataset_key
LEFT JOIN core.raw_artifacts artifact ON artifact.id = run.raw_artifact_id;

CREATE OR REPLACE VIEW market.v_market_data_quality_checks AS
SELECT
    quality.*,
    run.run_key,
    run.batch_key,
    run.dataset_key,
    run.source_key
FROM market.market_data_quality_checks quality
JOIN market.market_data_import_runs run ON run.id = quality.import_run_id;

CREATE OR REPLACE VIEW market.v_strategy_market_data_readiness AS
WITH ohlcv AS (
    SELECT
        timeframe AS dataset_scope,
        count(*)::BIGINT AS row_count,
        count(DISTINCT symbol_id)::BIGINT AS symbol_count,
        min(ts) AS first_ts,
        max(ts) AS last_ts,
        count(DISTINCT source_system_id)::BIGINT AS source_count
    FROM trading.ohlcv
    GROUP BY timeframe
),
straddles AS (
    SELECT
        'option_straddle'::TEXT AS dataset_scope,
        count(*)::BIGINT AS row_count,
        count(DISTINCT underlying)::BIGINT AS symbol_count,
        min(ts) AS first_ts,
        max(ts) AS last_ts,
        count(DISTINCT source_system_id)::BIGINT AS source_count
    FROM trading.option_strategy_snapshots
),
combined AS (
    SELECT * FROM ohlcv
    UNION ALL SELECT * FROM straddles
)
SELECT
    combined.*,
    extract(day FROM coalesce(last_ts, now()) - first_ts)::BIGINT AS history_days,
    extract(day FROM now() - last_ts)::BIGINT AS staleness_days,
    CASE
        WHEN dataset_scope = '1d' AND row_count >= 500000 AND symbol_count >= 300
             AND first_ts <= now() - interval '5 years'
            THEN 'research_ready_with_bias_audit_required'
        WHEN dataset_scope IN ('5m', '15m', '1h') AND row_count >= 100000 AND symbol_count >= 50
            THEN 'research_ready_with_bias_audit_required'
        WHEN dataset_scope = 'option_straddle' AND row_count >= 25000 AND symbol_count >= 3
            THEN 'research_ready_with_bias_audit_required'
        WHEN row_count > 0 THEN 'insufficient_depth'
        ELSE 'missing'
    END AS readiness_status,
    CASE
        WHEN dataset_scope = '1d' THEN 'Corporate-action, point-in-time universe, survivorship, and stale-tail audits remain mandatory.'
        WHEN dataset_scope = 'option_straddle' THEN 'Expand underlyings, expiries, chain context, IV/OI, and trading-day coverage.'
        ELSE 'Expand symbol and trading-day depth before strategy promotion.'
    END AS next_required_action
FROM combined;

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
        coalesce((sf.profile ->> 'row_count')::INTEGER, 0) AS profiled_row_count,
        coalesce(rows.staged_row_count, 0)::INTEGER AS staged_row_count,
        coalesce(jsonb_array_length(sf.profile -> 'tables'), 0) AS sqlite_table_count,
        sf.profile
    FROM client_data.source_files sf
    LEFT JOIN (
        SELECT source_file_id, count(*) AS staged_row_count
        FROM client_data.p2cursor_csv_rows GROUP BY source_file_id
    ) rows ON rows.source_file_id = sf.id
    JOIN core.source_systems source ON source.id = sf.source_system_id
    WHERE source.name = 'ps 2 cursor archive'
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
        WHEN import_status = 'duplicate_reference' THEN 'duplicate_reference'
        WHEN import_status = 'excluded_nonproduction' THEN 'excluded_nonproduction'
        WHEN import_status IN ('promoted', 'imported', 'mapped') THEN 'promoted'
        WHEN import_status = 'empty_profiled' THEN 'empty_profiled'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count THEN 'staged_needs_mapping'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = 0 THEN 'missing_staging'
        WHEN file_type = 'csv' AND profiled_row_count <> staged_row_count THEN 'staging_count_mismatch'
        WHEN file_type = 'sqlite' AND sqlite_table_count > 0 THEN 'sqlite_profiled_needs_mapping'
        WHEN file_type = 'json' THEN 'reference_profiled'
        ELSE 'profiled'
    END AS readiness_status,
    CASE
        WHEN import_status = 'duplicate_reference' THEN 'No promotion; rows duplicate the canonical Naval trade export.'
        WHEN import_status = 'excluded_nonproduction' THEN 'No promotion; file is an application sample, not client evidence.'
        WHEN import_status IN ('promoted', 'imported', 'mapped') THEN 'No immediate action.'
        WHEN import_status = 'empty_profiled' THEN 'No rows exist in the archived database; retain checksum evidence only.'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = profiled_row_count THEN 'Map staged CSV rows into client/account/trade history.'
        WHEN file_type = 'csv' AND profiled_row_count > 0 AND staged_row_count = 0 THEN 'Run p2cursor CSV staging for this file.'
        WHEN file_type = 'csv' AND profiled_row_count <> staged_row_count THEN 'Investigate staging row-count mismatch.'
        WHEN file_type = 'sqlite' AND sqlite_table_count > 0 THEN 'Review SQLite tables and promote or explicitly exclude each table.'
        WHEN file_type = 'json' THEN 'Keep as benchmark/reference artifact.'
        ELSE 'Review profiled p2cursor file.'
    END AS recommended_action,
    profile
FROM file_rows
ORDER BY source_file_id;

UPDATE client_data.source_files
SET import_status = CASE original_path
        WHEN 'ps 2 cursor/CARERATING_bulk_upload.csv' THEN 'duplicate_reference'
        WHEN 'ps 2 cursor/tushit_equity_bulk_upload.csv' THEN 'promoted'
        WHEN 'ps 2 cursor/naval_equity_folio_trades.csv' THEN 'promoted'
        WHEN 'ps 2 cursor/frontend/public/sample_bulk_transactions.csv' THEN 'excluded_nonproduction'
        WHEN 'ps 2 cursor/ps 2 cursor/backend/app/db.sqlite3' THEN 'empty_profiled'
        WHEN 'ps 2 cursor/ps 2 cursor/backend/app/data/benchmark_sector_weights.json' THEN 'reference_profiled'
        ELSE import_status
    END,
    profile = profile || CASE original_path
        WHEN 'ps 2 cursor/CARERATING_bulk_upload.csv' THEN '{"resolution":"duplicate_of_naval_equity_folio_trades.csv","production_rows_promoted":0}'::jsonb
        WHEN 'ps 2 cursor/tushit_equity_bulk_upload.csv' THEN '{"resolution":"promoted_to_portfolio_trades_and_positions","production_rows_promoted":12}'::jsonb
        WHEN 'ps 2 cursor/naval_equity_folio_trades.csv' THEN '{"resolution":"promoted_to_portfolio_trades_and_positions","production_rows_promoted":61}'::jsonb
        WHEN 'ps 2 cursor/frontend/public/sample_bulk_transactions.csv' THEN '{"resolution":"excluded_frontend_sample","production_rows_promoted":0}'::jsonb
        WHEN 'ps 2 cursor/ps 2 cursor/backend/app/db.sqlite3' THEN '{"resolution":"archived_database_contains_zero_business_rows","production_rows_promoted":0}'::jsonb
        ELSE '{}'::jsonb
    END
WHERE original_path IN (
    'ps 2 cursor/CARERATING_bulk_upload.csv',
    'ps 2 cursor/tushit_equity_bulk_upload.csv',
    'ps 2 cursor/naval_equity_folio_trades.csv',
    'ps 2 cursor/frontend/public/sample_bulk_transactions.csv',
    'ps 2 cursor/ps 2 cursor/backend/app/db.sqlite3',
    'ps 2 cursor/ps 2 cursor/backend/app/data/benchmark_sector_weights.json'
);

ALTER TABLE core.integration_jobs DROP CONSTRAINT IF EXISTS integration_jobs_executor_allowlist;
ALTER TABLE core.integration_jobs ADD CONSTRAINT integration_jobs_executor_allowlist CHECK (
    executor_key IN (
        'market_news_ingestion', 'filings_collection', 'tick_ohlcv_aggregation',
        'tradingview_quote_refresh', 'public_source_check', 'provider_readiness',
        'legacy_market_data_ingestion'
    )
);

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'legacy_algo_daily_bars_to_ohlcv_v1',
    'plugin_key', 'data_source:algo_trading_archive_connector',
    'dataset_key', 'legacy_algo_daily_ohlcv', 'target_relation', 'trading.ohlcv',
    'source_schema', jsonb_build_object('database', 'prices.db', 'table', 'daily_bars', 'immutable', true),
    'field_mappings', jsonb_build_object('date', 'ts', 'symbol', 'symbol_id', 'open', 'open', 'high', 'high', 'low', 'low', 'close', 'close', 'volume', 'volume'),
    'transformations', jsonb_build_array('uppercase_symbol', 'date_to_utc_midnight', 'float_epsilon_bound_normalization'),
    'primary_key_fields', jsonb_build_array('date', 'symbol'), 'timestamp_field', 'date',
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex',
    'notes', 'Research-only until dataset bias audits are completed.'
));
SELECT core.validate_integration_schema_mapping('legacy_algo_daily_bars_to_ohlcv_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'legacy_algo_ticks_to_ticks_v1',
    'plugin_key', 'data_source:algo_trading_archive_connector',
    'dataset_key', 'legacy_algo_ticks', 'target_relation', 'trading.ticks',
    'source_schema', jsonb_build_object('database', 'app.db', 'table', 'ticks', 'immutable', true),
    'field_mappings', jsonb_build_object('ts', 'ts', 'symbol', 'symbol', 'ltp', 'price', 'volume', 'volume', 'oi', 'payload.oi', 'change_pct', 'payload.change_pct'),
    'primary_key_fields', jsonb_build_array('ts', 'symbol'), 'timestamp_field', 'ts',
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('legacy_algo_ticks_to_ticks_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'legacy_algo_straddles_to_option_snapshots_v1',
    'plugin_key', 'data_source:algo_trading_archive_connector',
    'dataset_key', 'legacy_algo_straddles', 'target_relation', 'trading.option_strategy_snapshots',
    'source_schema', jsonb_build_object('database', 'app.db', 'table', 'straddle_snapshots', 'immutable', true),
    'field_mappings', jsonb_build_object('ts', 'ts', 'underlying', 'underlying', 'expiry', 'expiry', 'atm_strike', 'reference_strike', 'ce_price', 'call_price', 'pe_price', 'put_price', 'straddle', 'net_premium', 'spot', 'spot_price', 'iv_avg', 'implied_volatility'),
    'primary_key_fields', jsonb_build_array('ts', 'underlying', 'expiry', 'atm_strike'), 'timestamp_field', 'ts',
    'owner_agent', 'Options Data Engineer', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('legacy_algo_straddles_to_option_snapshots_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'p2cursor_archive_to_staging_v1',
    'plugin_key', 'data_source:p2cursor_archive_connector',
    'dataset_key', 'p2cursor_staged_rows', 'target_relation', 'client_data.p2cursor_csv_rows',
    'source_schema', jsonb_build_object('archive', 'ps 2 cursor.zip', 'resolved_files', 6),
    'field_mappings', jsonb_build_object('source_file', 'source_file_id', 'row_number', 'row_number', 'row_hash', 'row_hash', 'payload', 'payload'),
    'primary_key_fields', jsonb_build_array('source_file_id', 'row_hash'),
    'owner_agent', 'Data Steward', 'created_by', 'Codex',
    'notes', 'Canonical Tushit/Naval files promoted; duplicate and sample files explicitly excluded; archived SQLite contains zero business rows.'
));
SELECT core.validate_integration_schema_mapping('p2cursor_archive_to_staging_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'sanjana_pdf_holdings_to_positions_v1',
    'plugin_key', 'data_source:sanjana_long_term_report_2025_09_17_connector',
    'dataset_key', 'sanjana_report_positions', 'target_relation', 'portfolio.positions',
    'source_schema', jsonb_build_object('format', 'pdf_report', 'report_date', '2025-09-17'),
    'field_mappings', jsonb_build_object('symbol', 'symbol', 'quantity', 'quantity', 'average_price', 'average_price', 'report_date', 'as_of'),
    'primary_key_fields', jsonb_build_array('account_id', 'symbol', 'as_of'), 'timestamp_field', 'report_date',
    'owner_agent', 'Portfolio Data Agent', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('sanjana_pdf_holdings_to_positions_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'tushit_holdings_statement_to_positions_v1',
    'plugin_key', 'data_source:tushit_3081282_holdings_2026_07_01_connector',
    'dataset_key', 'tushit_statement_positions', 'target_relation', 'portfolio.positions',
    'source_schema', jsonb_build_object('format', 'xls_statement', 'account_code', 'tushit_3081282_statement'),
    'field_mappings', jsonb_build_object('symbol', 'symbol', 'quantity', 'quantity', 'average_price', 'average_price', 'report_as_of', 'as_of'),
    'primary_key_fields', jsonb_build_array('account_id', 'symbol', 'as_of'), 'timestamp_field', 'report_as_of',
    'owner_agent', 'Portfolio Data Agent', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('tushit_holdings_statement_to_positions_v1', 'Data Quality Agent');

SELECT core.upsert_integration_schema_mapping(jsonb_build_object(
    'mapping_key', 'tushit_transactions_statement_to_trade_staging_v1',
    'plugin_key', 'data_source:tushit_3081282_transactions_2026_h1_connector',
    'dataset_key', 'tushit_statement_transactions', 'target_relation', 'client_data.attached_broker_transactions',
    'source_schema', jsonb_build_object('format', 'xls_statement', 'account_code', 'tushit_3081282_statement'),
    'field_mappings', jsonb_build_object('trade_date', 'trade_date', 'trading_symbol', 'trading_symbol', 'side', 'side', 'quantity', 'quantity', 'net_rate', 'net_rate', 'trade_no', 'trade_no'),
    'primary_key_fields', jsonb_build_array('source_file_id', 'row_hash'), 'timestamp_field', 'trade_date',
    'owner_agent', 'Trade Reconciliation Agent', 'created_by', 'Codex'
));
SELECT core.validate_integration_schema_mapping('tushit_transactions_statement_to_trade_staging_v1', 'Data Quality Agent');

SELECT core.upsert_integration_job(jsonb_build_object(
    'job_key', 'legacy_market_data_manual_ingestion',
    'plugin_key', 'data_source:algo_trading_archive_connector',
    'job_name', 'Legacy market data ingestion and quality gate',
    'job_type', 'import', 'executor_key', 'legacy_market_data_ingestion',
    'enabled', true, 'run_mode', 'manual', 'timeout_seconds', 3600,
    'parameters', jsonb_build_object('datasets', jsonb_build_array('daily_bars', 'ticks', 'straddle_snapshots')),
    'owner_agent', 'Market Data Engineer', 'created_by', 'Codex',
    'notes', 'Reads only checksum-preserved SQLite files in external-SSD quarantine; no broker or network authority.'
));

UPDATE core.source_connector_profiles connector
SET status = 'active', health_status = 'active', last_checked_at = now(),
    last_rows_seen = CASE connector.source_key
        WHEN 'p2cursor_archive' THEN (SELECT count(*) FROM client_data.p2cursor_csv_rows)
        WHEN 'sanjana_long_term_report_2025_09_17' THEN (SELECT count(*) FROM portfolio.positions position JOIN core.source_systems source ON source.id = position.source_system_id WHERE source.name = 'Sanjana Long Term Report 2025-09-17')
        WHEN 'tushit_3081282_holdings_2026_07_01' THEN (SELECT count(*) FROM portfolio.positions position JOIN core.source_systems source ON source.id = position.source_system_id WHERE source.name = 'Tushit 3081282 Holdings Statement 2026-07-01')
        WHEN 'tushit_3081282_transactions_2026_h1' THEN (SELECT count(*) FROM client_data.attached_broker_transactions)
        ELSE connector.last_rows_seen
    END,
    last_error = NULL, updated_at = now()
WHERE connector.source_key IN (
    'p2cursor_archive', 'sanjana_long_term_report_2025_09_17',
    'tushit_3081282_holdings_2026_07_01', 'tushit_3081282_transactions_2026_h1'
);

INSERT INTO core.data_source_checks (source_key, check_name, check_type, status, rows_seen, sample_payload, checked_at)
SELECT connector.source_key, 'legacy client source mapping resolution', 'schema_mapping', 'ok', connector.last_rows_seen,
       jsonb_build_object('mapping_status', 'validated', 'seed_data', false, 'execution_allowed', false), now()
FROM core.source_connector_profiles connector
WHERE connector.source_key IN (
    'p2cursor_archive', 'sanjana_long_term_report_2025_09_17',
    'tushit_3081282_holdings_2026_07_01', 'tushit_3081282_transactions_2026_h1'
)
AND NOT EXISTS (
    SELECT 1 FROM core.data_source_checks check_row
    WHERE check_row.source_key = connector.source_key
      AND check_row.check_name = 'legacy client source mapping resolution'
      AND check_row.status = 'ok'
);

UPDATE core.data_source_registry
SET last_seen_at = now(), updated_at = now(),
    metadata = metadata || jsonb_build_object('mapping_status', 'validated', 'seed_data', false, 'execution_allowed', false)
WHERE source_key IN (
    'p2cursor_archive', 'sanjana_long_term_report_2025_09_17',
    'tushit_3081282_holdings_2026_07_01', 'tushit_3081282_transactions_2026_h1'
);

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
(
    'ai_os_market_data_readiness', 'mcp_tool', 'Market Data Engineer', 'read_only', true,
    'Read imported market-data coverage, bias contracts, quality checks, and strategy readiness.',
    '{"reads":["market.v_strategy_market_data_readiness","market.v_market_data_import_runs","market.dataset_contracts"],"execution_allowed":false}'::jsonb
),
(
    'ai_os_run_legacy_market_data_ingestion', 'mcp_tool', 'Market Data Engineer', 'write_with_approval', true,
    'Run the bounded checksum-preserved legacy market-data import and quality gate.',
    '{"executor_key":"legacy_market_data_ingestion","reads":["external_ssd_quarantine"],"writes":["trading.ohlcv","trading.ticks","trading.option_strategy_snapshots","market.market_data_import_runs"],"seed_data_allowed":false,"broker_execution_allowed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
