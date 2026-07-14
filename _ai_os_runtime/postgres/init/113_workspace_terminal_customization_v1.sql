CREATE TABLE IF NOT EXISTS ops.workspace_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_key TEXT NOT NULL UNIQUE,
    profile_name TEXT NOT NULL,
    owner_name TEXT NOT NULL DEFAULT 'Devarsh',
    is_active BOOLEAN NOT NULL DEFAULT true,
    default_workspace TEXT NOT NULL DEFAULT 'command',
    theme TEXT NOT NULL DEFAULT 'terminal_dark' CHECK (theme IN ('terminal_dark', 'terminal_light')),
    density TEXT NOT NULL DEFAULT 'compact' CHECK (density IN ('compact', 'standard')),
    navigation JSONB NOT NULL DEFAULT '{}'::jsonb,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops.workspace_layouts (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES ops.workspace_profiles(id) ON DELETE CASCADE,
    workspace_key TEXT NOT NULL,
    module_order JSONB NOT NULL DEFAULT '[]'::jsonb,
    hidden_modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    column_count INTEGER NOT NULL DEFAULT 2 CHECK (column_count BETWEEN 1 AND 4),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by TEXT NOT NULL DEFAULT 'Devarsh',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (profile_id, workspace_key)
);

INSERT INTO ops.workspace_profiles (
    profile_key, profile_name, owner_name, default_workspace, theme, density,
    navigation, preferences
)
VALUES (
    'devarsh',
    'Devarsh Investment Office',
    'Devarsh',
    'command',
    'terminal_dark',
    'compact',
    '{"visible":["command","approvals","agents","committees","portfolio","clients","research","ideas","trading","quant","risk","capital","treasury","models","reports","system"]}'::jsonb,
    '{"execution_lock":true,"evidence_rail":true,"freshness_clock":true,"charlie_workspace_help":true}'::jsonb
)
ON CONFLICT (profile_key) DO NOTHING;

INSERT INTO ops.workspace_layouts (profile_id, workspace_key, module_order, column_count, settings)
SELECT
    p.id,
    workspace_key,
    module_order,
    column_count,
    '{"show_evidence":true,"show_freshness":true}'::jsonb
FROM ops.workspace_profiles p
CROSS JOIN (
    VALUES
        ('approvals', '["summary","approval_queue","execution_gates"]'::jsonb, 2),
        ('agents', '["departments","agent_roster","worker_queue","messages"]'::jsonb, 2),
        ('committees', '["committee_summary","committee_rooms","followups"]'::jsonb, 2),
        ('capital', '["book_exposure","portfolio_intelligence","cross_book_conflicts"]'::jsonb, 2),
        ('treasury', '["macro_sources","market_watch","source_freshness"]'::jsonb, 2),
        ('models', '["provider_summary","model_routes","assignment_gates","usage_cost"]'::jsonb, 2)
) AS defaults(workspace_key, module_order, column_count)
WHERE p.profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO NOTHING;

CREATE OR REPLACE VIEW ops.v_workspace_terminal_config AS
SELECT
    p.id AS profile_id,
    p.profile_key,
    p.profile_name,
    p.owner_name,
    p.is_active,
    p.default_workspace,
    p.theme,
    p.density,
    p.navigation,
    p.preferences,
    p.version,
    l.id AS layout_id,
    l.workspace_key,
    l.module_order,
    l.hidden_modules,
    l.column_count,
    l.settings,
    l.updated_by,
    greatest(p.updated_at, l.updated_at) AS updated_at
FROM ops.workspace_profiles p
LEFT JOIN ops.workspace_layouts l ON l.profile_id = p.id
ORDER BY p.profile_key, l.workspace_key;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
)
VALUES
    (
        'workspace_terminal_reader',
        'dashboard_control',
        'Jarvis',
        'read_only',
        true,
        'Reads operator workspace profiles, department-terminal layouts, widgets, and live evidence panels.',
        '{"api_route":"/api/workspaces/config","view":"ops.v_workspace_terminal_config"}'::jsonb
    ),
    (
        'workspace_terminal_customizer',
        'dashboard_control',
        'Charlie Munger',
        'write_with_approval',
        true,
        'Updates operator-approved themes, density, navigation, module order, and widget layout without changing source evidence.',
        '{"api_route":"/api/workspaces/config/update","writes":["ops.workspace_profiles","ops.workspace_layouts","ops.dashboard_widgets"],"live_execution_allowed":false}'::jsonb
    )
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

INSERT INTO agent.workflow_registry (
    workflow_key, workflow_name, workflow_type, owner_agent, trigger_type, status,
    permission_level, input_sources, output_targets, approval_required,
    schedule_hint, notes, metadata
)
VALUES (
    'charlie_workspace_customization',
    'Charlie Workspace Customization',
    'interactive_operating_layer',
    'Charlie Munger',
    'chat_or_manual',
    'active',
    'write_with_approval',
    ARRAY['agent.chat_turns','ops.dashboard_widget_intents','ops.workspace_profiles']::TEXT[],
    ARRAY['ops.workspace_layouts','ops.dashboard_widgets','core.audit_log']::TEXT[],
    false,
    'on operator request',
    'Charlie proposes or applies reversible workspace and widget changes. Source data, approval state, and execution controls remain unchanged.',
    '{"operator":"Devarsh","reversible":true,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (workflow_key) DO UPDATE SET
    workflow_name = EXCLUDED.workflow_name,
    workflow_type = EXCLUDED.workflow_type,
    owner_agent = EXCLUDED.owner_agent,
    trigger_type = EXCLUDED.trigger_type,
    status = EXCLUDED.status,
    permission_level = EXCLUDED.permission_level,
    input_sources = EXCLUDED.input_sources,
    output_targets = EXCLUDED.output_targets,
    approval_required = EXCLUDED.approval_required,
    schedule_hint = EXCLUDED.schedule_hint,
    notes = EXCLUDED.notes,
    metadata = EXCLUDED.metadata,
    updated_at = now();
