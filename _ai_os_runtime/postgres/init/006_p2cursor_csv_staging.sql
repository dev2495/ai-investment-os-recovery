CREATE TABLE IF NOT EXISTS client_data.p2cursor_csv_rows (
    id BIGSERIAL PRIMARY KEY,
    source_file_id BIGINT REFERENCES client_data.source_files(id),
    original_path TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    row_hash TEXT NOT NULL,
    row_payload JSONB NOT NULL,
    import_status TEXT NOT NULL DEFAULT 'staged',
    staged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_file_id, row_number, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_p2cursor_csv_rows_file ON client_data.p2cursor_csv_rows (source_file_id);
CREATE INDEX IF NOT EXISTS idx_p2cursor_csv_rows_hash ON client_data.p2cursor_csv_rows (row_hash);
