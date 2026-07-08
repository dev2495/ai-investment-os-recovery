CREATE OR REPLACE VIEW research.v_ai_output_inventory AS
SELECT
    ra.id AS artifact_id,
    ss.name AS source_system,
    ra.artifact_type,
    ra.title,
    ra.local_path,
    ra.source_url,
    ra.mime_type,
    ra.content_hash,
    ra.sensitivity,
    ra.captured_at,
    ra.metadata ->> 'root_label' AS root_label,
    ra.metadata ->> 'artifact_family' AS artifact_family,
    ra.metadata ->> 'company_or_topic' AS company_or_topic,
    NULLIF(ra.metadata ->> 'size_bytes', '')::BIGINT AS size_bytes,
    ra.metadata ->> 'last_modified_at' AS source_last_modified_at,
    ra.metadata ->> 'summary' AS summary
FROM core.raw_artifacts ra
JOIN core.source_systems ss ON ss.id = ra.source_system_id
WHERE ss.name = 'AI generated research outputs'
   OR ra.artifact_type LIKE 'ai_research_%'
   OR ra.artifact_type LIKE 'ai_dashboard_%'
   OR ra.artifact_type LIKE 'ai_model_%';

CREATE INDEX IF NOT EXISTS idx_raw_artifacts_ai_output_family
    ON core.raw_artifacts ((metadata ->> 'artifact_family'))
    WHERE artifact_type LIKE 'ai_%';
