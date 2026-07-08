CREATE OR REPLACE VIEW core.v_source_artifact_lineage AS
SELECT
    'raw_artifact'::TEXT AS lineage_type,
    ('core.raw_artifacts:' || ra.id::TEXT) AS row_ref,
    ra.id AS row_id,
    ss.name AS source_system,
    ss.source_type,
    ss.location AS source_location,
    ss.sensitivity AS source_sensitivity,
    ra.artifact_type,
    ra.title,
    ra.source_url,
    ra.local_path,
    ra.content_hash,
    ra.mime_type,
    ra.sensitivity,
    ra.captured_at AS event_at,
    NULL::BIGINT AS import_run_id,
    NULL::BIGINT AS source_file_id,
    ra.id AS raw_artifact_id,
    NULL::TEXT AS client_code,
    NULL::TEXT AS account_code,
    NULL::TEXT AS symbol,
    NULL::TEXT AS reconciliation_status,
    jsonb_build_object(
        'table', 'core.raw_artifacts',
        'id', ra.id,
        'metadata', ra.metadata
    ) AS lineage_payload
FROM core.raw_artifacts ra
LEFT JOIN core.source_systems ss ON ss.id = ra.source_system_id

UNION ALL

SELECT
    'p2cursor_source_file'::TEXT AS lineage_type,
    ('client_data.source_files:' || sf.id::TEXT) AS row_ref,
    sf.id AS row_id,
    ss.name AS source_system,
    ss.source_type,
    ss.location AS source_location,
    sf.sensitivity AS source_sensitivity,
    sf.file_type AS artifact_type,
    coalesce(sf.original_path, sf.extracted_path) AS title,
    NULL::TEXT AS source_url,
    coalesce(sf.extracted_path, sf.original_path) AS local_path,
    sf.sha256 AS content_hash,
    sf.file_type AS mime_type,
    sf.sensitivity,
    sf.registered_at AS event_at,
    NULL::BIGINT AS import_run_id,
    sf.id AS source_file_id,
    sf.raw_artifact_id AS raw_artifact_id,
    NULL::TEXT AS client_code,
    NULL::TEXT AS account_code,
    NULL::TEXT AS symbol,
    sf.import_status AS reconciliation_status,
    jsonb_build_object(
        'table', 'client_data.source_files',
        'id', sf.id,
        'source_component_id', sf.source_component_id,
        'size_bytes', sf.size_bytes,
        'profile', sf.profile,
        'staged_rows', (SELECT count(*) FROM client_data.p2cursor_csv_rows pcr WHERE pcr.source_file_id = sf.id)
    ) AS lineage_payload
FROM client_data.source_files sf
LEFT JOIN core.source_systems ss ON ss.id = sf.source_system_id

UNION ALL

SELECT
    'attached_transaction_file'::TEXT AS lineage_type,
    ('client_data.attached_transaction_files:' || f.id::TEXT) AS row_ref,
    f.id AS row_id,
    'attached broker/client files'::TEXT AS source_system,
    f.file_kind AS source_type,
    f.source_path AS source_location,
    'client_private'::TEXT AS source_sensitivity,
    f.file_kind AS artifact_type,
    f.file_name AS title,
    NULL::TEXT AS source_url,
    f.source_path AS local_path,
    f.sha256 AS content_hash,
    NULL::TEXT AS mime_type,
    'client_private'::TEXT AS sensitivity,
    f.imported_at AS event_at,
    NULL::BIGINT AS import_run_id,
    NULL::BIGINT AS source_file_id,
    f.raw_artifact_id AS raw_artifact_id,
    f.client_code,
    NULL::TEXT AS account_code,
    NULL::TEXT AS symbol,
    'imported'::TEXT AS reconciliation_status,
    jsonb_build_object(
        'table', 'client_data.attached_transaction_files',
        'id', f.id,
        'client_name', f.client_name,
        'period_start', f.period_start,
        'period_end', f.period_end,
        'row_count', f.row_count,
        'metadata', f.metadata
    ) AS lineage_payload
FROM client_data.attached_transaction_files f

UNION ALL

SELECT
    'p2cursor_csv_row'::TEXT AS lineage_type,
    ('client_data.p2cursor_csv_rows:' || pcr.id::TEXT) AS row_ref,
    pcr.id AS row_id,
    ss.name AS source_system,
    ss.source_type,
    ss.location AS source_location,
    sf.sensitivity AS source_sensitivity,
    sf.file_type AS artifact_type,
    pcr.original_path AS title,
    NULL::TEXT AS source_url,
    coalesce(sf.extracted_path, pcr.original_path) AS local_path,
    pcr.row_hash AS content_hash,
    sf.file_type AS mime_type,
    sf.sensitivity,
    pcr.staged_at AS event_at,
    NULL::BIGINT AS import_run_id,
    pcr.source_file_id,
    NULL::BIGINT AS raw_artifact_id,
    pcr.row_payload ->> 'client_code' AS client_code,
    pcr.row_payload ->> 'account_code' AS account_code,
    coalesce(pcr.row_payload ->> 'symbol', pcr.row_payload ->> 'trading_symbol') AS symbol,
    pcr.import_status AS reconciliation_status,
    jsonb_build_object(
        'table', 'client_data.p2cursor_csv_rows',
        'id', pcr.id,
        'row_number', pcr.row_number,
        'source_file_id', pcr.source_file_id,
        'row_payload', pcr.row_payload
    ) AS lineage_payload
FROM client_data.p2cursor_csv_rows pcr
LEFT JOIN client_data.source_files sf ON sf.id = pcr.source_file_id
LEFT JOIN core.source_systems ss ON ss.id = sf.source_system_id

UNION ALL

SELECT
    'portfolio_position'::TEXT AS lineage_type,
    ('portfolio.positions:' || p.id::TEXT) AS row_ref,
    p.id AS row_id,
    ss.name AS source_system,
    ss.source_type,
    ss.location AS source_location,
    ss.sensitivity AS source_sensitivity,
    'position_snapshot'::TEXT AS artifact_type,
    concat_ws(' ', a.account_code, p.symbol, p.as_of::TEXT) AS title,
    NULL::TEXT AS source_url,
    ss.location AS local_path,
    NULL::TEXT AS content_hash,
    NULL::TEXT AS mime_type,
    coalesce(ss.sensitivity, 'client_private') AS sensitivity,
    p.as_of AS event_at,
    NULL::BIGINT AS import_run_id,
    NULL::BIGINT AS source_file_id,
    NULL::BIGINT AS raw_artifact_id,
    c.client_code,
    a.account_code,
    p.symbol,
    'current_position_source'::TEXT AS reconciliation_status,
    jsonb_build_object(
        'table', 'portfolio.positions',
        'id', p.id,
        'account_id', p.account_id,
        'exchange', p.exchange,
        'instrument_type', p.instrument_type,
        'quantity', p.quantity,
        'average_price', p.average_price,
        'market_price', p.market_price,
        'market_value', p.market_value,
        'payload', p.payload
    ) AS lineage_payload
FROM portfolio.positions p
LEFT JOIN portfolio.accounts a ON a.id = p.account_id
LEFT JOIN portfolio.clients c ON c.id = a.client_id
LEFT JOIN core.source_systems ss ON ss.id = p.source_system_id

UNION ALL

SELECT
    'p2cursor_reconciliation_issue'::TEXT AS lineage_type,
    ('portfolio.p2cursor_reconciliation_issues:' || i.id::TEXT) AS row_ref,
    i.id AS row_id,
    'p2cursor reconciliation'::TEXT AS source_system,
    i.issue_type AS source_type,
    'portfolio.p2cursor_reconciliation_issues'::TEXT AS source_location,
    'client_private'::TEXT AS source_sensitivity,
    'reconciliation_issue'::TEXT AS artifact_type,
    i.issue_key AS title,
    NULL::TEXT AS source_url,
    NULL::TEXT AS local_path,
    NULL::TEXT AS content_hash,
    NULL::TEXT AS mime_type,
    'client_private'::TEXT AS sensitivity,
    i.created_at AS event_at,
    NULL::BIGINT AS import_run_id,
    NULL::BIGINT AS source_file_id,
    NULL::BIGINT AS raw_artifact_id,
    i.client_code,
    coalesce(i.p2_account_code, i.comparison_account_code) AS account_code,
    i.symbol,
    i.status AS reconciliation_status,
    jsonb_build_object(
        'table', 'portfolio.p2cursor_reconciliation_issues',
        'id', i.id,
        'run_id', i.run_id,
        'severity', i.severity,
        'description', i.description,
        'p2_quantity', i.p2_quantity,
        'comparison_quantity', i.comparison_quantity,
        'evidence', i.evidence
    ) AS lineage_payload
FROM portfolio.p2cursor_reconciliation_issues i;

CREATE OR REPLACE VIEW core.v_source_lineage_summary AS
SELECT
    lineage_type,
    coalesce(source_system, 'unknown') AS source_system,
    coalesce(source_type, 'unknown') AS source_type,
    coalesce(sensitivity, source_sensitivity, 'unknown') AS sensitivity,
    count(*) AS row_count,
    count(*) FILTER (WHERE raw_artifact_id IS NOT NULL) AS raw_artifact_rows,
    count(*) FILTER (WHERE source_file_id IS NOT NULL) AS source_file_rows,
    min(event_at) AS first_seen_at,
    max(event_at) AS latest_seen_at,
    count(*) FILTER (WHERE reconciliation_status IN ('open', 'needs_review', 'staged', 'profiled')) AS open_or_staged_rows
FROM core.v_source_artifact_lineage
GROUP BY lineage_type, coalesce(source_system, 'unknown'), coalesce(source_type, 'unknown'), coalesce(sensitivity, source_sensitivity, 'unknown');

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent, ui_workspace, description,
    warehouse_objects, mcp_tools, next_action, metadata
)
VALUES (
    'source_lineage',
    'Source Lineage And Artifact Visibility',
    'data',
    'active',
    'critical',
    'Data Steward',
    'system',
    'Read model that traces raw artifacts, legacy source files, attached broker files, p2cursor rows, portfolio positions, and reconciliation issues.',
    ARRAY['core.v_source_artifact_lineage','core.v_source_lineage_summary']::TEXT[],
    ARRAY['ai_os_source_lineage','ai_os_source_lineage_summary']::TEXT[],
    'Use this before marking any import or dashboard row production-ready.',
    '{"blueprint_requirement":"Every client, holding, transaction, trade, strategy, source, and report is traceable."}'::jsonb
)
ON CONFLICT (module_key) DO UPDATE SET
    module_name = EXCLUDED.module_name,
    category = EXCLUDED.category,
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    owner_agent = EXCLUDED.owner_agent,
    ui_workspace = EXCLUDED.ui_workspace,
    description = EXCLUDED.description,
    warehouse_objects = EXCLUDED.warehouse_objects,
    mcp_tools = EXCLUDED.mcp_tools,
    next_action = EXCLUDED.next_action,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_source_lineage', 'mcp_tool', 'Data Steward', 'read_only', true, 'List source lineage rows across artifacts, source files, positions, and reconciliation issues.', '{"reads":["core.v_source_artifact_lineage"]}'::jsonb),
    ('ai_os_source_lineage_summary', 'mcp_tool', 'Data Steward', 'read_only', true, 'Summarize source lineage coverage by source and row type.', '{"reads":["core.v_source_lineage_summary"]}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE agent.skills
SET
    input_sources = ARRAY(
        SELECT DISTINCT item
        FROM unnest(input_sources || ARRAY['core.v_source_artifact_lineage','core.v_source_lineage_summary']::TEXT[]) AS item
    ),
    updated_at = now()
WHERE skill_key IN ('source-data-ingestion-review', 'p2cursor_reconciliation', 'broker_import_reconciliation');
