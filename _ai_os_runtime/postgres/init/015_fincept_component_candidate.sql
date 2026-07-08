WITH source AS (
    INSERT INTO core.source_systems (name, source_type, location, sensitivity, status, notes)
    VALUES (
        'FinceptTerminal reference repo',
        'external_git_repo',
        'https://github.com/Fincept-Corporation/FinceptTerminal',
        'public',
        'reference_candidate',
        'Public financial terminal repo reviewed as an architecture/component reference. License boundary: AGPL-3.0 plus commercial license terms; do not fork, merge, or reuse code in internal/client systems until licensing is approved.'
    )
    ON CONFLICT (name) DO UPDATE SET
        source_type = EXCLUDED.source_type,
        location = EXCLUDED.location,
        sensitivity = EXCLUDED.sensitivity,
        status = EXCLUDED.status,
        notes = EXCLUDED.notes
    RETURNING id
),
components AS (
    SELECT * FROM (
        VALUES
        (
            'native terminal shell',
            'frontend_reference',
            'fincept-qt',
            'reference_only',
            'medium',
            'mapped',
            'C++20 plus Qt6 native desktop shell with terminal-class layout patterns for dense finance workflows.',
            'ops',
            ARRAY[]::text[],
            'Reference only. License requires review before any fork, modification, or internal/client use.',
            '{"repo_component":"fincept-qt","why_it_matters":"native dense terminal UI without Electron overhead"}'::jsonb
        ),
        (
            'portfolio and equity research workbench',
            'product_reference',
            'README.md',
            'reference_only',
            'high',
            'mapped',
            'Portfolio, equity research, DCF, risk, and analytics surfaces align with the AI OS portfolio office vision.',
            'portfolio',
            ARRAY['portfolio.positions','portfolio.snapshots','research.ideas','risk.strategy_risk_reviews'],
            'Rebuild around our own schemas and data permissions. Do not copy UI/code without license clearance.',
            '{"repo_component":"portfolio_research","target":"folio_manager_dashboard"}'::jsonb
        ),
        (
            'agent catalog and local llm provider pattern',
            'agent_reference',
            'README.md',
            'reference_only',
            'high',
            'mapped',
            'Catalog of investor/trader/economic/geopolitical agents and multi-provider/local LLM pattern useful for Jarvis team design.',
            'agent',
            ARRAY['agent.agent_profiles','agent.agent_runs'],
            'Use as role inspiration only. Keep AI OS agents role-scoped and connected through our MCP tools.',
            '{"repo_component":"ai_agents","reported_agent_count":37}'::jsonb
        ),
        (
            'connector and broker integration catalog',
            'integration_reference',
            'README.md',
            'reference_only',
            'medium',
            'mapped',
            'Data connector and broker integration map for prioritizing our adapters across market data, filings, broker positions, and alerts.',
            'core',
            ARRAY['core.source_systems','trading.signals','portfolio.trades'],
            'Reference map only. Live broker/trading adapters require separate credential handling and human approval gates.',
            '{"repo_component":"connectors","reported_connector_count":"100+","reported_broker_count":16}'::jsonb
        ),
        (
            'visual workflow and MCP node editor',
            'workflow_reference',
            'README.md',
            'reference_only',
            'medium',
            'mapped',
            'Node editor plus MCP workflow pattern can inform later AI office automation UI after the data spine is stable.',
            'ops',
            ARRAY['ops.browser_runs','agent.agent_runs'],
            'Later-phase reference. Do not block foundation work on node editor cloning.',
            '{"repo_component":"node_editor_mcp","phase":"post_foundation"}'::jsonb
        )
    ) AS rows (
        component_name,
        component_type,
        source_path,
        reuse_mode,
        priority,
        status,
        description,
        target_schema,
        target_tables,
        safety_notes,
        metadata
    )
)
INSERT INTO core.source_components (
    source_system_id,
    component_name,
    component_type,
    source_path,
    reuse_mode,
    priority,
    status,
    description,
    target_schema,
    target_tables,
    safety_notes,
    metadata
)
SELECT
    source.id,
    components.component_name,
    components.component_type,
    components.source_path,
    components.reuse_mode,
    components.priority,
    components.status,
    components.description,
    components.target_schema,
    components.target_tables,
    components.safety_notes,
    components.metadata
FROM source
CROSS JOIN components
ON CONFLICT (source_system_id, component_name) DO UPDATE SET
    component_type = EXCLUDED.component_type,
    source_path = EXCLUDED.source_path,
    reuse_mode = EXCLUDED.reuse_mode,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    description = EXCLUDED.description,
    target_schema = EXCLUDED.target_schema,
    target_tables = EXCLUDED.target_tables,
    safety_notes = EXCLUDED.safety_notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();

WITH source AS (
    SELECT id FROM core.source_systems WHERE name = 'FinceptTerminal reference repo'
)
INSERT INTO core.raw_artifacts (
    source_system_id,
    artifact_type,
    title,
    source_url,
    local_path,
    content_hash,
    mime_type,
    sensitivity,
    metadata
)
SELECT
    source.id,
    'external_repo_component_review',
    'FinceptTerminal component review',
    'https://github.com/Fincept-Corporation/FinceptTerminal',
    NULL,
    'github-live-review-2026-07-01',
    'text/markdown',
    'public',
    '{
        "license_boundary":"AGPL-3.0 plus commercial license terms; reference only until license approval",
        "features":["native C++20 Qt6 terminal","embedded Python analytics","37 AI agents","100+ connectors","16 broker integrations","MCP node editor","quant lab"],
        "decision":"do_not_fork_or_merge_yet",
        "recommended_use":"architecture and component reference"
    }'::jsonb
FROM source
ON CONFLICT (source_system_id, source_url, local_path, content_hash) DO UPDATE SET
    artifact_type = EXCLUDED.artifact_type,
    title = EXCLUDED.title,
    mime_type = EXCLUDED.mime_type,
    sensitivity = EXCLUDED.sensitivity,
    metadata = EXCLUDED.metadata,
    captured_at = now();
