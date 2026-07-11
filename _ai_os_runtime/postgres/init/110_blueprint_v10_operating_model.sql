CREATE TABLE IF NOT EXISTS core.os_blueprint_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    blueprint_key TEXT NOT NULL REFERENCES core.os_blueprint_versions(blueprint_key) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'started',
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    domain_count INTEGER NOT NULL DEFAULT 0,
    requirement_count INTEGER NOT NULL DEFAULT 0,
    done_count INTEGER NOT NULL DEFAULT 0,
    partial_count INTEGER NOT NULL DEFAULT 0,
    planned_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Jarvis',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_os_blueprint_sync_runs_blueprint
ON core.os_blueprint_sync_runs (blueprint_key, created_at DESC);

UPDATE core.os_blueprint_versions
SET status = 'superseded', updated_at = now()
WHERE status = 'canonical'
  AND blueprint_key <> 'investment_os_v10';

INSERT INTO core.os_blueprint_versions (
    blueprint_key, blueprint_name, version_label, status, note_path, checklist_path,
    owner_agent, runtime_operator, metadata
)
VALUES (
    'investment_os_v10',
    'AI Investment OS - Institutional Master Blueprint',
    'v10.0',
    'canonical',
    'ai memory/00 AI OS/Architecture/AI Investment OS - Institutional Master Blueprint v10.0.md',
    'ai memory/00 AI OS/Roadmap/AI Investment OS - Execution Checklist v10.0.md',
    'Charlie Munger',
    'Jarvis',
    '{
      "north_star":"full_ai_hedge_fund_operating_system",
      "primary_interface":"command_center_plus_live_ai_office_plus_charlie_chat",
      "human_in_control":true,
      "live_execution_default":"disabled",
      "storage_contract":"internal_source_external_heavy_state",
      "requirements_source":"canonical_checklist_parser",
      "seed_data_allowed":false
    }'::jsonb
)
ON CONFLICT (blueprint_key) DO UPDATE SET
    blueprint_name = EXCLUDED.blueprint_name,
    version_label = EXCLUDED.version_label,
    status = EXCLUDED.status,
    note_path = EXCLUDED.note_path,
    checklist_path = EXCLUDED.checklist_path,
    owner_agent = EXCLUDED.owner_agent,
    runtime_operator = EXCLUDED.runtime_operator,
    metadata = EXCLUDED.metadata,
    updated_at = now();

CREATE OR REPLACE VIEW core.v_os_blueprint_requirements AS
SELECT
    version.blueprint_key,
    version.version_label,
    requirement.requirement_key,
    requirement.requirement_name,
    requirement.requirement_type,
    requirement.priority,
    requirement.current_status,
    requirement.owner_agent,
    requirement.owner_department,
    domain.domain_key,
    domain.domain_name,
    domain.section_number,
    domain.domain_type,
    domain.primary_workspace,
    requirement.mapped_object_type,
    requirement.mapped_object_key,
    CASE
        WHEN requirement.mapped_object_type = 'control_module' THEN module.status
        WHEN requirement.mapped_object_type = 'book' THEN book.status
        WHEN requirement.mapped_object_type = 'agent' THEN profile.status
        WHEN requirement.mapped_object_type = 'tool' THEN CASE WHEN tool.enabled THEN 'enabled' ELSE 'disabled' END
        WHEN requirement.mapped_object_type = 'data_source' THEN source.status
        WHEN requirement.mapped_object_type = 'note' THEN 'note_recorded'
        ELSE NULL
    END AS mapped_object_status,
    CASE
        WHEN requirement.mapped_object_type = 'control_module' AND module.module_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'book' AND book.book_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'agent' AND profile.agent_name IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'tool' AND tool.tool_name IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'data_source' AND source.source_key IS NOT NULL THEN true
        WHEN requirement.mapped_object_type = 'note' THEN true
        ELSE false
    END AS mapped_object_found,
    requirement.evidence_note_path,
    requirement.acceptance_criteria,
    requirement.next_action,
    requirement.metadata,
    requirement.updated_at
FROM core.os_blueprint_versions version
JOIN core.os_blueprint_domains domain ON domain.blueprint_key = version.blueprint_key
JOIN core.os_blueprint_requirements requirement ON requirement.domain_key = domain.domain_key
LEFT JOIN core.control_plane_modules module
    ON requirement.mapped_object_type = 'control_module'
   AND module.module_key = requirement.mapped_object_key
LEFT JOIN books.investment_books book
    ON requirement.mapped_object_type = 'book'
   AND book.book_key = requirement.mapped_object_key
LEFT JOIN agent.profiles profile
    ON requirement.mapped_object_type = 'agent'
   AND profile.agent_name = requirement.mapped_object_key
LEFT JOIN agent.tool_registry tool
    ON requirement.mapped_object_type = 'tool'
   AND tool.tool_name = requirement.mapped_object_key
LEFT JOIN core.data_source_registry source
    ON requirement.mapped_object_type = 'data_source'
   AND source.source_key = requirement.mapped_object_key
WHERE version.status = 'canonical';

CREATE OR REPLACE VIEW core.v_os_blueprint_domains AS
SELECT
    version.blueprint_key,
    version.version_label,
    domain.domain_key,
    domain.section_number,
    domain.domain_name,
    domain.domain_type,
    domain.owner_agent,
    domain.owner_department,
    domain.priority,
    domain.status,
    domain.objective,
    domain.primary_workspace,
    count(requirement.requirement_key)::BIGINT AS requirement_count,
    count(*) FILTER (WHERE requirement.current_status = 'done')::BIGINT AS done_count,
    count(*) FILTER (WHERE requirement.current_status = 'partial')::BIGINT AS partial_count,
    count(*) FILTER (WHERE requirement.current_status = 'planned')::BIGINT AS planned_count,
    count(*) FILTER (WHERE requirement.current_status = 'blocked')::BIGINT AS blocked_count,
    count(*) FILTER (WHERE requirement.mapped_object_found)::BIGINT AS mapped_count,
    round(
        CASE
            WHEN count(requirement.requirement_key) = 0 THEN 0
            ELSE (
                count(*) FILTER (WHERE requirement.current_status = 'done') * 100.0
                + count(*) FILTER (WHERE requirement.current_status = 'partial') * 50.0
            ) / count(requirement.requirement_key)
        END,
        1
    ) AS progress_score,
    min(requirement.next_action) FILTER (WHERE requirement.current_status <> 'done') AS next_action
FROM core.os_blueprint_versions version
JOIN core.os_blueprint_domains domain ON domain.blueprint_key = version.blueprint_key
LEFT JOIN core.v_os_blueprint_requirements requirement ON requirement.domain_key = domain.domain_key
WHERE version.status = 'canonical'
GROUP BY
    version.blueprint_key,
    version.version_label,
    domain.domain_key,
    domain.section_number,
    domain.domain_name,
    domain.domain_type,
    domain.owner_agent,
    domain.owner_department,
    domain.priority,
    domain.status,
    domain.objective,
    domain.primary_workspace
ORDER BY domain.section_number;

CREATE OR REPLACE VIEW core.v_os_blueprint_summary AS
WITH canonical AS (
    SELECT blueprint_key, version_label
    FROM core.os_blueprint_versions
    WHERE status = 'canonical'
    LIMIT 1
), requirement_counts AS (
    SELECT
        count(*)::BIGINT AS requirements,
        count(*) FILTER (WHERE current_status = 'done')::BIGINT AS done_requirements,
        count(*) FILTER (WHERE current_status = 'partial')::BIGINT AS partial_requirements,
        count(*) FILTER (WHERE current_status = 'planned')::BIGINT AS planned_requirements,
        count(*) FILTER (WHERE current_status = 'blocked')::BIGINT AS blocked_requirements,
        count(*) FILTER (WHERE mapped_object_found)::BIGINT AS mapped_requirements
    FROM core.v_os_blueprint_requirements
)
SELECT 'blueprint_version'::TEXT AS metric, canonical.version_label::TEXT AS value, 'Canonical operating-model version'::TEXT AS interpretation
FROM canonical
UNION ALL
SELECT 'domains', count(*)::TEXT, 'Canonical operating-model domains tracked in the warehouse'
FROM core.v_os_blueprint_domains
UNION ALL
SELECT 'requirements', requirements::TEXT, 'Canonical checklist requirements tracked in the warehouse' FROM requirement_counts
UNION ALL
SELECT 'done_requirements', done_requirements::TEXT, 'Requirements marked done with evidence' FROM requirement_counts
UNION ALL
SELECT 'partial_requirements', partial_requirements::TEXT, 'Requirements with partial runtime implementation' FROM requirement_counts
UNION ALL
SELECT 'planned_requirements', planned_requirements::TEXT, 'Requirements not implemented yet' FROM requirement_counts
UNION ALL
SELECT 'blocked_requirements', blocked_requirements::TEXT, 'Requirements explicitly blocked by an external dependency' FROM requirement_counts
UNION ALL
SELECT 'mapped_requirements', mapped_requirements::TEXT, 'Requirements linked to live runtime objects' FROM requirement_counts
UNION ALL
SELECT 'progress_score',
       CASE WHEN requirements = 0 THEN '0.0'
            ELSE round((done_requirements * 100.0 + partial_requirements * 50.0) / requirements, 1)::TEXT END,
       'Weighted completion: done=100%, partial=50%, planned/blocked=0%'
FROM requirement_counts;

CREATE OR REPLACE VIEW core.v_os_blueprint_sync_runs AS
SELECT
    run.id,
    run.run_key,
    run.blueprint_key,
    version.version_label,
    run.status,
    run.source_path,
    run.source_sha256,
    run.domain_count,
    run.requirement_count,
    run.done_count,
    run.partial_count,
    run.planned_count,
    run.error_message,
    run.started_at,
    run.finished_at,
    run.created_by,
    run.created_at
FROM core.os_blueprint_sync_runs run
JOIN core.os_blueprint_versions version ON version.blueprint_key = run.blueprint_key
ORDER BY run.created_at DESC;

INSERT INTO core.control_plane_modules (
    module_key, module_name, category, status, priority, owner_agent, ui_workspace,
    description, warehouse_objects, mcp_tools, fincept_component, next_action, metadata
)
VALUES (
    'blueprint_v10_operating_model',
    'Blueprint v10 Operating Model',
    'governance',
    'active',
    'critical',
    'Charlie Munger',
    'system',
    'Parser-backed canonical v10 coverage registry with every checklist item, owner, status, source line, evidence metadata, and auditable sync run.',
    ARRAY['core.os_blueprint_versions','core.os_blueprint_domains','core.os_blueprint_requirements','core.os_blueprint_sync_runs','core.v_os_blueprint_domains','core.v_os_blueprint_requirements','core.v_os_blueprint_summary','core.v_os_blueprint_sync_runs']::TEXT[],
    ARRAY['ai_os_blueprint_summary','ai_os_blueprint_requirements']::TEXT[],
    NULL,
    'Use the canonical registry to select work, attach evidence, and prevent Markdown/runtime drift.',
    '{"blueprint_key":"investment_os_v10","seed_data_allowed":false,"source":"canonical_checklist_parser"}'::jsonb
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
    ('ai_os_blueprint_summary', 'mcp_tool', 'Charlie Munger', 'read_only', true, 'Read canonical AI Investment OS blueprint progress and domain coverage.', '{"reads":["core.v_os_blueprint_summary","core.v_os_blueprint_domains","core.v_os_blueprint_sync_runs"],"canonical_only":true}'::jsonb),
    ('ai_os_blueprint_requirements', 'mcp_tool', 'Jarvis', 'read_only', true, 'Read canonical blueprint requirements with owners, status, source line, mapped objects, evidence, acceptance criteria, and next action.', '{"reads":["core.v_os_blueprint_requirements"],"canonical_only":true}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;
