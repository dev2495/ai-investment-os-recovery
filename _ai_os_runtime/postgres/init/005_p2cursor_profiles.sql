CREATE TABLE IF NOT EXISTS client_data.source_files (
    id BIGSERIAL PRIMARY KEY,
    source_system_id BIGINT REFERENCES core.source_systems(id),
    source_component_id BIGINT REFERENCES core.source_components(id),
    original_path TEXT NOT NULL,
    extracted_path TEXT,
    file_type TEXT,
    size_bytes BIGINT,
    sha256 TEXT,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    import_status TEXT NOT NULL DEFAULT 'profiled',
    sensitivity TEXT NOT NULL DEFAULT 'client_private',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_system_id, original_path, sha256)
);

CREATE INDEX IF NOT EXISTS idx_source_files_type ON client_data.source_files (file_type);
CREATE INDEX IF NOT EXISTS idx_source_files_status ON client_data.source_files (import_status);
CREATE INDEX IF NOT EXISTS idx_source_files_sha ON client_data.source_files (sha256);
