BEGIN;

CREATE TABLE IF NOT EXISTS sector_intelligence.market_history_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    taxonomy_node_id BIGINT NOT NULL REFERENCES sector_intelligence.taxonomy_nodes(id) ON DELETE RESTRICT,
    provider TEXT NOT NULL DEFAULT 'Zerodha',
    interval TEXT NOT NULL,
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    member_count INTEGER NOT NULL DEFAULT 0,
    completed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    rows_written INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    requested_by TEXT NOT NULL,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT chk_sector_history_dates CHECK (date_to >= date_from),
    CONSTRAINT chk_sector_history_status CHECK (status IN ('started','completed','partial','failed')),
    CONSTRAINT chk_sector_history_no_broker_writes CHECK (broker_write_allowed = false)
);

CREATE TABLE IF NOT EXISTS sector_intelligence.market_history_sync_items (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES sector_intelligence.market_history_sync_runs(id) ON DELETE CASCADE,
    symbol_id BIGINT NOT NULL REFERENCES trading.symbols(id) ON DELETE RESTRICT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    rows_written INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT chk_sector_history_item_status CHECK (status IN ('queued','running','completed','failed')),
    CONSTRAINT chk_sector_history_item_no_broker_writes CHECK (broker_write_allowed = false),
    UNIQUE (run_id, symbol_id)
);

CREATE INDEX IF NOT EXISTS idx_sector_history_runs_node
ON sector_intelligence.market_history_sync_runs (taxonomy_node_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sector_history_items_run
ON sector_intelligence.market_history_sync_items (run_id, status, symbol);

CREATE OR REPLACE VIEW sector_intelligence.v_market_history_sync_control AS
SELECT run.id AS run_id, run.run_key, node.taxonomy_key, node.node_name,
       run.provider, run.interval, run.date_from, run.date_to, run.status,
       run.member_count, run.completed_count, run.failed_count, run.rows_written,
       run.error_message, run.requested_by, run.started_at, run.finished_at,
       run.broker_write_allowed
FROM sector_intelligence.market_history_sync_runs run
JOIN sector_intelligence.taxonomy_nodes node ON node.id=run.taxonomy_node_id;

COMMIT;
