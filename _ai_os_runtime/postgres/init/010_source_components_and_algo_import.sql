CREATE TABLE IF NOT EXISTS core.source_code_files (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    component_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    extracted_path TEXT,
    file_type TEXT,
    size_bytes BIGINT,
    sha256 TEXT,
    language TEXT,
    purpose TEXT,
    reuse_status TEXT NOT NULL DEFAULT 'candidate',
    sensitivity TEXT NOT NULL DEFAULT 'private',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_system_id, source_path, sha256)
);

CREATE INDEX IF NOT EXISTS idx_source_code_files_component ON core.source_code_files (component_name);
CREATE INDEX IF NOT EXISTS idx_source_code_files_reuse ON core.source_code_files (reuse_status);
CREATE INDEX IF NOT EXISTS idx_source_code_files_language ON core.source_code_files (language);

CREATE TABLE IF NOT EXISTS core.source_requirements (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    component_name TEXT,
    source_path TEXT NOT NULL,
    package_manager TEXT NOT NULL,
    package_name TEXT NOT NULL,
    version_spec TEXT,
    dev_dependency BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_system_id, source_path, package_manager, package_name, version_spec, dev_dependency)
);

CREATE INDEX IF NOT EXISTS idx_source_requirements_package ON core.source_requirements (package_name);
CREATE INDEX IF NOT EXISTS idx_source_requirements_manager ON core.source_requirements (package_manager);

CREATE TABLE IF NOT EXISTS core.source_table_profiles (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    database_path TEXT NOT NULL,
    table_name TEXT NOT NULL,
    row_count BIGINT,
    columns_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    target_tables TEXT[] NOT NULL DEFAULT '{}',
    import_status TEXT NOT NULL DEFAULT 'profiled',
    profiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_system_id, database_path, table_name)
);

CREATE INDEX IF NOT EXISTS idx_source_table_profiles_status ON core.source_table_profiles (import_status);

ALTER TABLE portfolio.trades
    ADD COLUMN IF NOT EXISTS external_ref TEXT;

DROP INDEX IF EXISTS portfolio.uq_portfolio_trades_external_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_trades_external_ref
ON portfolio.trades (source_system_id, external_ref);

ALTER TABLE trading.signals
    ADD COLUMN IF NOT EXISTS external_ref TEXT;

DROP INDEX IF EXISTS trading.uq_trading_signals_external_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_trading_signals_external_ref
ON trading.signals (source_system_id, external_ref);

ALTER TABLE trading.trade_journals
    ADD COLUMN IF NOT EXISTS external_ref TEXT;

DROP INDEX IF EXISTS trading.uq_trade_journals_external_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_trade_journals_external_ref
ON trading.trade_journals (source_system_id, external_ref);

ALTER TABLE strategy.backtest_runs
    ADD COLUMN IF NOT EXISTS external_ref TEXT,
    ADD COLUMN IF NOT EXISTS source_system_id BIGINT REFERENCES core.source_systems(id);

DROP INDEX IF EXISTS strategy.uq_backtest_runs_external_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_backtest_runs_external_ref
ON strategy.backtest_runs (source_system_id, external_ref);

DROP INDEX IF EXISTS research.uq_research_ideas_source_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_research_ideas_source_ref
ON research.ideas (source_kind, source_ref);
