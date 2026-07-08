ALTER TABLE client_data.source_files
    ADD COLUMN IF NOT EXISTS raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL;

ALTER TABLE client_data.attached_transaction_files
    ADD COLUMN IF NOT EXISTS raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_source_files_raw_artifact
    ON client_data.source_files (raw_artifact_id);

CREATE INDEX IF NOT EXISTS idx_attached_transaction_files_raw_artifact
    ON client_data.attached_transaction_files (raw_artifact_id);

INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
SELECT DISTINCT
    'Attached file import - ' || f.file_name || ' - ' || f.file_kind AS name,
    'attached_transaction_file',
    f.source_path,
    'client_private',
    'imported',
    'User-attached transaction or option-log file registered through the AI OS import pipeline.'
FROM client_data.attached_transaction_files f
ON CONFLICT (name) DO UPDATE SET
    source_type = EXCLUDED.source_type,
    location = EXCLUDED.location,
    sensitivity = EXCLUDED.sensitivity,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes;

INSERT INTO core.raw_artifacts (
    source_system_id,
    artifact_type,
    title,
    local_path,
    content_hash,
    mime_type,
    sensitivity,
    metadata
)
SELECT
    sf.source_system_id,
    'p2cursor_' || coalesce(nullif(sf.file_type, ''), 'file'),
    split_part(sf.original_path, '/', array_length(string_to_array(sf.original_path, '/'), 1)),
    coalesce(sf.extracted_path, sf.original_path),
    sf.sha256,
    CASE lower(coalesce(sf.file_type, ''))
        WHEN 'csv' THEN 'text/csv'
        WHEN 'json' THEN 'application/json'
        WHEN 'sqlite' THEN 'application/x-sqlite3'
        ELSE 'application/octet-stream'
    END,
    sf.sensitivity,
    jsonb_build_object(
        'source_table', 'client_data.source_files',
        'source_file_id', sf.id,
        'original_path', sf.original_path,
        'extracted_path', sf.extracted_path,
        'file_type', sf.file_type,
        'size_bytes', sf.size_bytes,
        'import_status', sf.import_status,
        'profile', sf.profile
    )
FROM client_data.source_files sf
WHERE sf.source_system_id IS NOT NULL
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = core.raw_artifacts.metadata || EXCLUDED.metadata;

UPDATE client_data.source_files sf
SET raw_artifact_id = ra.id
FROM core.raw_artifacts ra
WHERE sf.source_system_id IS NOT NULL
  AND ra.source_system_id = sf.source_system_id
  AND ra.local_path = coalesce(sf.extracted_path, sf.original_path)
  AND ra.content_hash IS NOT DISTINCT FROM sf.sha256
  AND sf.raw_artifact_id IS DISTINCT FROM ra.id;

INSERT INTO core.raw_artifacts (
    source_system_id,
    artifact_type,
    title,
    local_path,
    content_hash,
    mime_type,
    sensitivity,
    metadata
)
SELECT
    ss.id,
    f.file_kind,
    f.file_name,
    f.source_path,
    f.sha256,
    CASE lower(split_part(f.file_name, '.', array_length(string_to_array(f.file_name, '.'), 1)))
        WHEN 'xls' THEN 'application/vnd.ms-excel'
        WHEN 'xlsx' THEN 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        WHEN 'csv' THEN 'text/csv'
        ELSE 'application/octet-stream'
    END,
    'client_private',
    jsonb_build_object(
        'source_table', 'client_data.attached_transaction_files',
        'attached_transaction_file_id', f.id,
        'file_kind', f.file_kind,
        'client_code', f.client_code,
        'client_name', f.client_name,
        'period_start', f.period_start,
        'period_end', f.period_end,
        'row_count', f.row_count,
        'metadata', f.metadata
    )
FROM client_data.attached_transaction_files f
JOIN core.source_systems ss
  ON ss.name = 'Attached file import - ' || f.file_name || ' - ' || f.file_kind
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = core.raw_artifacts.metadata || EXCLUDED.metadata;

UPDATE client_data.attached_transaction_files f
SET
    raw_artifact_id = ra.id,
    metadata = f.metadata || jsonb_build_object('raw_artifact_id', ra.id)
FROM core.source_systems ss
JOIN core.raw_artifacts ra
  ON ra.source_system_id = ss.id
WHERE ss.name = 'Attached file import - ' || f.file_name || ' - ' || f.file_kind
  AND ra.local_path = f.source_path
  AND ra.content_hash IS NOT DISTINCT FROM f.sha256
  AND f.raw_artifact_id IS DISTINCT FROM ra.id;

INSERT INTO core.raw_artifacts (
    source_system_id,
    artifact_type,
    title,
    local_path,
    content_hash,
    mime_type,
    sensitivity,
    metadata
)
SELECT
    ss.id,
    ss.source_type,
    ss.name,
    ss.location,
    NULL,
    CASE lower(split_part(ss.location, '.', array_length(string_to_array(ss.location, '.'), 1)))
        WHEN 'pdf' THEN 'application/pdf'
        WHEN 'xls' THEN 'application/vnd.ms-excel'
        WHEN 'xlsx' THEN 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        WHEN 'csv' THEN 'text/csv'
        ELSE 'application/octet-stream'
    END,
    ss.sensitivity,
    jsonb_build_object(
        'source_table', 'core.source_systems',
        'source_system_id', ss.id,
        'source_type', ss.source_type,
        'status', ss.status,
        'notes', ss.notes
    )
FROM core.source_systems ss
WHERE ss.status = 'imported'
  AND ss.location IS NOT NULL
  AND ss.location <> ''
  AND ss.source_type IN (
      'pdf_report',
      'broker_statement',
      'broker_transaction_statement'
  )
  AND NOT EXISTS (
      SELECT 1
      FROM core.raw_artifacts existing
      WHERE existing.source_system_id = ss.id
        AND existing.local_path = ss.location
  )
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = core.raw_artifacts.metadata || EXCLUDED.metadata;

CREATE OR REPLACE VIEW core.v_import_artifact_coverage AS
SELECT
    'client_data.source_files' AS import_surface,
    count(*)::BIGINT AS total_rows,
    count(raw_artifact_id)::BIGINT AS linked_rows,
    (count(*) - count(raw_artifact_id))::BIGINT AS missing_rows,
    CASE WHEN count(*) = 0 THEN 100::NUMERIC ELSE round((count(raw_artifact_id)::NUMERIC / count(*)::NUMERIC) * 100, 2) END AS coverage_pct,
    'p2cursor profiled files' AS description
FROM client_data.source_files
UNION ALL
SELECT
    'client_data.attached_transaction_files',
    count(*)::BIGINT,
    count(raw_artifact_id)::BIGINT,
    (count(*) - count(raw_artifact_id))::BIGINT,
    CASE WHEN count(*) = 0 THEN 100::NUMERIC ELSE round((count(raw_artifact_id)::NUMERIC / count(*)::NUMERIC) * 100, 2) END,
    'user-attached broker and option log files'
FROM client_data.attached_transaction_files
UNION ALL
SELECT
    'core.source_systems.imported_file_locations',
    count(*)::BIGINT,
    count(ra.id)::BIGINT,
    (count(*) - count(ra.id))::BIGINT,
    CASE WHEN count(*) = 0 THEN 100::NUMERIC ELSE round((count(ra.id)::NUMERIC / count(*)::NUMERIC) * 100, 2) END,
    'imported PDF/broker file source systems'
FROM core.source_systems ss
LEFT JOIN core.raw_artifacts ra
  ON ra.source_system_id = ss.id
 AND ra.local_path = ss.location
WHERE ss.status = 'imported'
  AND ss.location IS NOT NULL
  AND ss.location <> ''
  AND ss.source_type IN (
      'pdf_report',
      'broker_statement',
      'broker_transaction_statement',
      'attached_transaction_file'
  );

CREATE OR REPLACE VIEW core.v_import_artifact_gaps AS
SELECT
    'client_data.source_files' AS import_surface,
    ('client_data.source_files:' || sf.id::TEXT) AS row_ref,
    split_part(sf.original_path, '/', array_length(string_to_array(sf.original_path, '/'), 1)) AS title,
    coalesce(sf.extracted_path, sf.original_path) AS source_path,
    sf.sha256 AS content_hash,
    'missing raw_artifact_id on p2cursor profiled file' AS gap_reason
FROM client_data.source_files sf
WHERE sf.raw_artifact_id IS NULL
UNION ALL
SELECT
    'client_data.attached_transaction_files',
    ('client_data.attached_transaction_files:' || f.id::TEXT),
    f.file_name,
    f.source_path,
    f.sha256,
    'missing raw_artifact_id on attached transaction file'
FROM client_data.attached_transaction_files f
WHERE f.raw_artifact_id IS NULL
UNION ALL
SELECT
    'core.source_systems.imported_file_locations',
    ('core.source_systems:' || ss.id::TEXT),
    ss.name,
    ss.location,
    NULL::TEXT,
    'missing core.raw_artifacts row for imported file source system'
FROM core.source_systems ss
WHERE ss.status = 'imported'
  AND ss.location IS NOT NULL
  AND ss.location <> ''
  AND ss.source_type IN (
      'pdf_report',
      'broker_statement',
      'broker_transaction_statement',
      'attached_transaction_file'
  )
  AND NOT EXISTS (
      SELECT 1
      FROM core.raw_artifacts ra
      WHERE ra.source_system_id = ss.id
        AND ra.local_path = ss.location
  );

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_import_artifact_coverage', 'mcp_tool', 'Data Steward', 'read_only', true, 'Show raw-artifact coverage across current import surfaces.', '{"reads":["core.v_import_artifact_coverage"]}'::jsonb),
    ('ai_os_import_artifact_gaps', 'mcp_tool', 'Data Steward', 'read_only', true, 'List imported files that still lack raw-artifact lineage.', '{"reads":["core.v_import_artifact_gaps"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE agent.skills
SET input_sources = (
    SELECT ARRAY(
        SELECT DISTINCT item
        FROM unnest(input_sources || ARRAY['core.v_import_artifact_coverage','core.v_import_artifact_gaps']::TEXT[]) AS item
        ORDER BY item
    )
)
WHERE skill_key IN ('source_data_ingestion_review', 'p2cursor_reconciliation_review', 'attached_trade_history_review');
