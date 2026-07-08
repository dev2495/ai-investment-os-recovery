CREATE OR REPLACE VIEW core.v_source_component_inventory AS
SELECT
    ss.name AS source_system,
    scf.component_name,
    count(*) AS file_count,
    sum(scf.size_bytes) AS total_size_bytes,
    array_agg(DISTINCT scf.language ORDER BY scf.language) AS languages,
    min(scf.registered_at) AS first_registered_at,
    max(scf.registered_at) AS last_registered_at
FROM core.source_code_files scf
JOIN core.source_systems ss ON ss.id = scf.source_system_id
GROUP BY ss.name, scf.component_name
ORDER BY ss.name, scf.component_name;

CREATE OR REPLACE VIEW core.v_source_requirements AS
SELECT
    ss.name AS source_system,
    sr.package_manager,
    sr.package_name,
    sr.version_spec,
    bool_or(sr.dev_dependency) AS appears_as_dev_dependency,
    count(*) AS references_count,
    array_agg(DISTINCT sr.component_name ORDER BY sr.component_name) AS components
FROM core.source_requirements sr
JOIN core.source_systems ss ON ss.id = sr.source_system_id
GROUP BY ss.name, sr.package_manager, sr.package_name, sr.version_spec
ORDER BY ss.name, sr.package_manager, sr.package_name;

CREATE OR REPLACE VIEW core.v_source_table_profiles AS
SELECT
    ss.name AS source_system,
    stp.database_path,
    stp.table_name,
    stp.row_count,
    stp.target_tables,
    stp.import_status,
    stp.profiled_at
FROM core.source_table_profiles stp
JOIN core.source_systems ss ON ss.id = stp.source_system_id
ORDER BY ss.name, stp.database_path, stp.table_name;

CREATE OR REPLACE VIEW core.v_algo_import_summary AS
SELECT 'portfolio_accounts' AS metric, count(*)::bigint AS value FROM portfolio.accounts
UNION ALL SELECT 'portfolio_positions', count(*)::bigint FROM portfolio.positions
UNION ALL SELECT 'portfolio_snapshots', count(*)::bigint FROM portfolio.snapshots
UNION ALL SELECT 'portfolio_trades', count(*)::bigint FROM portfolio.trades
UNION ALL SELECT 'trade_journals', count(*)::bigint FROM trading.trade_journals
UNION ALL SELECT 'trading_signals', count(*)::bigint FROM trading.signals
UNION ALL SELECT 'ticks', count(*)::bigint FROM trading.ticks
UNION ALL SELECT 'ohlcv', count(*)::bigint FROM trading.ohlcv
UNION ALL SELECT 'research_ideas', count(*)::bigint FROM research.ideas
UNION ALL SELECT 'strategy_candidates', count(*)::bigint FROM strategy.strategy_candidates
UNION ALL SELECT 'backtest_runs', count(*)::bigint FROM strategy.backtest_runs;
