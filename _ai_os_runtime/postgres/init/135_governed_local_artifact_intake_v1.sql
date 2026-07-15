BEGIN;

CREATE TABLE IF NOT EXISTS core.local_artifact_ingestions (
    id BIGSERIAL PRIMARY KEY,
    ingestion_key TEXT NOT NULL UNIQUE,
    run_key TEXT NOT NULL,
    raw_artifact_id BIGINT NOT NULL REFERENCES core.raw_artifacts(id) ON DELETE RESTRICT,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    source_path TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    extracted_text_path TEXT,
    file_name TEXT NOT NULL,
    file_extension TEXT,
    artifact_family TEXT NOT NULL,
    mime_type TEXT,
    content_hash TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL DEFAULT 'local_artifact_v1',
    status TEXT NOT NULL CHECK (status IN ('profiled','extracted','registered','failed')),
    promotion_status TEXT NOT NULL CHECK (promotion_status IN ('needs_mapping','needs_review','promoted','excluded','blocked')),
    suggested_destination TEXT,
    table_profiles JSONB NOT NULL DEFAULT '[]'::jsonb,
    row_count BIGINT,
    sheet_count INTEGER,
    page_count INTEGER,
    image_width INTEGER,
    image_height INTEGER,
    extracted_chars BIGINT,
    text_preview TEXT,
    sensitivity TEXT NOT NULL DEFAULT 'private' CHECK (sensitivity IN ('public','internal','private','client_private','restricted')),
    error_message TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    seen_count INTEGER NOT NULL DEFAULT 1 CHECK (seen_count > 0),
    created_by TEXT NOT NULL DEFAULT 'Data Steward',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_local_artifact_ingestions_status
ON core.local_artifact_ingestions (promotion_status, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_local_artifact_ingestions_hash
ON core.local_artifact_ingestions (content_hash, parser_version);

WITH ranked AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY owner_agent, source_kind, source_ref
               ORDER BY id
           ) AS duplicate_rank
    FROM agent.tasks
    WHERE status IN ('queued', 'in_progress', 'blocked')
      AND source_kind = 'core.local_artifact_ingestions'
      AND source_ref IS NOT NULL
)
UPDATE agent.tasks task
SET status = 'cancelled',
    updated_at = now(),
    evidence = task.evidence || jsonb_build_array(jsonb_build_object(
        'reason', 'superseded duplicate local-artifact review task',
        'migration', '135_governed_local_artifact_intake_v1'
    ))
FROM ranked
WHERE task.id = ranked.id
  AND ranked.duplicate_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_tasks_open_local_artifact
ON agent.tasks (owner_agent, source_kind, source_ref)
WHERE status IN ('queued', 'in_progress', 'blocked')
  AND source_kind = 'core.local_artifact_ingestions'
  AND source_ref IS NOT NULL;

CREATE OR REPLACE VIEW core.v_local_artifact_ingestion_queue AS
SELECT
    ingestion.id,
    ingestion.ingestion_key,
    ingestion.run_key,
    ingestion.raw_artifact_id,
    ingestion.task_id,
    ingestion.source_path,
    ingestion.stored_path,
    ingestion.extracted_text_path,
    ingestion.file_name,
    ingestion.file_extension,
    ingestion.artifact_family,
    ingestion.mime_type,
    ingestion.content_hash,
    ingestion.file_size_bytes,
    ingestion.parser_name,
    ingestion.parser_version,
    ingestion.status,
    ingestion.promotion_status,
    ingestion.suggested_destination,
    ingestion.table_profiles,
    ingestion.row_count,
    ingestion.sheet_count,
    ingestion.page_count,
    ingestion.image_width,
    ingestion.image_height,
    ingestion.extracted_chars,
    ingestion.text_preview,
    ingestion.sensitivity,
    ingestion.error_message,
    ingestion.first_seen_at,
    ingestion.last_seen_at,
    ingestion.seen_count,
    ingestion.created_by,
    ingestion.created_at,
    ingestion.updated_at,
    task.status AS task_status,
    task.owner_agent,
    false AS capital_action_allowed,
    false AS live_execution_allowed
FROM core.local_artifact_ingestions ingestion
LEFT JOIN agent.tasks task ON task.id = ingestion.task_id;

CREATE OR REPLACE VIEW core.v_local_artifact_ingestion_summary AS
SELECT 'total_ingestions'::text AS metric, count(*)::bigint AS value,
       'Unique checksum-backed local files registered through the governed intake.'::text AS interpretation
FROM core.local_artifact_ingestions
UNION ALL
SELECT 'needs_mapping', count(*), 'Tabular files requiring an explicit destination mapping.'
FROM core.local_artifact_ingestions WHERE promotion_status = 'needs_mapping'
UNION ALL
SELECT 'needs_review', count(*), 'Documents and images requiring human classification or review.'
FROM core.local_artifact_ingestions WHERE promotion_status = 'needs_review'
UNION ALL
SELECT 'failed', count(*), 'Files retained with parser failure evidence.'
FROM core.local_artifact_ingestions WHERE status = 'failed'
UNION ALL
SELECT 'tabular_files', count(*), 'CSV and spreadsheet files with bounded schema profiles.'
FROM core.local_artifact_ingestions WHERE artifact_family = 'tabular'
UNION ALL
SELECT 'documents', count(*), 'PDF, DOCX, and text documents with extracted or registered evidence.'
FROM core.local_artifact_ingestions WHERE artifact_family = 'document'
UNION ALL
SELECT 'images', count(*), 'Screenshot and image artifacts with dimensions and immutable bytes.'
FROM core.local_artifact_ingestions WHERE artifact_family = 'image';

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled,
    description, config
)
VALUES
(
    'ai_os_ingest_local_artifact', 'mcp_tool', 'Data Steward',
    'operator_confirmed_file_read', true,
    'Copy an operator-confirmed local spreadsheet, document, or screenshot to immutable external storage and create a bounded parser profile. Never promotes investment or trading rows automatically.',
    '{"writes":["core.raw_artifacts","core.local_artifact_ingestions","agent.tasks"],"allowed_formats":["csv","xls","xlsx","pdf","docx","txt","md","json","png","jpg","jpeg","webp"],"operator_confirmation_required":true,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
),
(
    'ai_os_local_artifact_ingestions', 'mcp_tool', 'Data Steward',
    'read_only', true,
    'Read checksum, parser, schema profile, destination, task, and promotion state for governed local-file intake.',
    '{"reads":["core.v_local_artifact_ingestion_summary","core.v_local_artifact_ingestion_queue"],"raw_file_content_exposed":false}'::jsonb
)
ON CONFLICT (tool_name) DO UPDATE SET
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

COMMIT;
