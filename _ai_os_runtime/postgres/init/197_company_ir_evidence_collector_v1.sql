BEGIN;

CREATE TABLE IF NOT EXISTS research.company_ir_collection_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    company_name TEXT NOT NULL,
    investor_relations_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    rows_seen INTEGER NOT NULL DEFAULT 0,
    reports_upserted INTEGER NOT NULL DEFAULT 0,
    bytes_downloaded BIGINT NOT NULL DEFAULT 0,
    started_by TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_company_ir_run_status CHECK (status IN ('started','completed','failed','dry_run')),
    CONSTRAINT chk_company_ir_run_https CHECK (investor_relations_url ~ '^https://')
);

CREATE INDEX IF NOT EXISTS idx_company_ir_collection_runs_symbol
ON research.company_ir_collection_runs (exchange, symbol, started_at DESC);

COMMENT ON TABLE research.company_ir_collection_runs IS
    'Auditable primary-source company investor-relations discovery runs. Reports remain evidence until separately normalized and reviewed; this collector never creates financial facts.';

COMMIT;
