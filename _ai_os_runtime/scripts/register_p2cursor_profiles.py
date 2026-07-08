#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = RUNTIME_ROOT / "imports" / "p2cursor_profile.json"


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def jsonb_quote(value: object) -> str:
    return sql_quote(json.dumps(value, sort_keys=True)) + "::jsonb"


def build_sql(profile_path: Path) -> str:
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    statements = [
        "BEGIN;",
        """
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
    raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
    UNIQUE NULLS NOT DISTINCT (source_system_id, original_path, sha256)
);
""",
        "CREATE INDEX IF NOT EXISTS idx_source_files_type ON client_data.source_files (file_type);",
        "CREATE INDEX IF NOT EXISTS idx_source_files_status ON client_data.source_files (import_status);",
        "CREATE INDEX IF NOT EXISTS idx_source_files_sha ON client_data.source_files (sha256);",
        "ALTER TABLE client_data.source_files ADD COLUMN IF NOT EXISTS raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL;",
        "CREATE INDEX IF NOT EXISTS idx_source_files_raw_artifact ON client_data.source_files (raw_artifact_id);",
    ]

    for item in data.get("files", []):
        profile = item.get("profile", {})
        statements.append(
            f"""
INSERT INTO client_data.source_files (
    source_system_id,
    source_component_id,
    original_path,
    extracted_path,
    file_type,
    size_bytes,
    sha256,
    profile,
    import_status,
    sensitivity
)
SELECT
    ss.id,
    sc.id,
    {sql_quote(item.get("original_path"))},
    {sql_quote(item.get("relative_extracted_path") or item.get("extracted_path"))},
    {sql_quote(profile.get("kind") or item.get("suffix"))},
    {item.get("size_bytes") or "NULL"},
    {sql_quote(item.get("sha256"))},
    {jsonb_quote(profile)},
    'profiled',
    'client_private'
FROM core.source_systems ss
LEFT JOIN core.source_components sc
    ON sc.source_system_id = ss.id
    AND sc.component_name = 'client portfolio data'
WHERE ss.name = 'ps 2 cursor archive'
ON CONFLICT (source_system_id, original_path, sha256) DO UPDATE SET
    extracted_path = EXCLUDED.extracted_path,
    file_type = EXCLUDED.file_type,
    size_bytes = EXCLUDED.size_bytes,
    profile = EXCLUDED.profile,
    import_status = EXCLUDED.import_status,
    sensitivity = EXCLUDED.sensitivity,
    registered_at = now();
"""
        )

    statements.extend(
        [
            """
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
JOIN core.source_systems ss ON ss.id = sf.source_system_id
WHERE ss.name = 'ps 2 cursor archive'
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = core.raw_artifacts.metadata || EXCLUDED.metadata;

UPDATE client_data.source_files sf
SET raw_artifact_id = ra.id
FROM core.raw_artifacts ra
JOIN core.source_systems ss ON ss.id = ra.source_system_id
WHERE ss.name = 'ps 2 cursor archive'
  AND sf.source_system_id = ss.id
  AND ra.local_path = coalesce(sf.extracted_path, sf.original_path)
  AND ra.content_hash IS NOT DISTINCT FROM sf.sha256
  AND sf.raw_artifact_id IS DISTINCT FROM ra.id;
""",
            """
INSERT INTO agent.tasks (
    title,
    objective,
    owner_agent,
    status,
    priority,
    approval_required,
    source_kind,
    source_ref,
    output_format,
    evidence
)
SELECT
    'Map p2cursor client portfolio datasets',
    'Review profiled p2cursor CSV/SQLite/Excel candidates and map safe fields into portfolio/client_data staging views before importing rows.',
    'Data Steward',
    'queued',
    'high',
    true,
    'client_data.source_files',
    'ps 2 cursor archive',
    'import_mapping_plan',
    jsonb_build_array(jsonb_build_object('profile_path', '_ai_os_runtime/imports/p2cursor_profile.json'))
WHERE NOT EXISTS (
    SELECT 1
    FROM agent.tasks
    WHERE title = 'Map p2cursor client portfolio datasets'
      AND owner_agent = 'Data Steward'
      AND source_kind = 'client_data.source_files'
      AND source_ref = 'ps 2 cursor archive'
      AND status IN ('queued', 'in_progress', 'blocked')
);
""",
            "COMMIT;",
        ]
    )
    return "\n".join(statements)


def run_psql(sql: str) -> None:
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-v", "ON_ERROR_STOP=1"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)


def main() -> int:
    sql = build_sql(DEFAULT_PROFILE)
    run_psql(sql)
    data = json.loads(DEFAULT_PROFILE.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "profile_path": str(DEFAULT_PROFILE),
                "registered_files": len(data.get("files", [])),
                "target_table": "client_data.source_files",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
