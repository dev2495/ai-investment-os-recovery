BEGIN;

UPDATE ops.workspace_profiles
SET navigation = jsonb_set(
        coalesce(navigation, '{}'::jsonb),
        '{visible}',
        CASE
            WHEN coalesce(navigation -> 'visible', '[]'::jsonb) ? 'tactical'
                THEN navigation -> 'visible'
            ELSE coalesce(navigation -> 'visible', '[]'::jsonb) || '"tactical"'::jsonb
        END,
        true
    ),
    version = version + 1,
    updated_at = now()
WHERE profile_key = 'devarsh';

INSERT INTO ops.workspace_layouts (
    profile_id,
    workspace_key,
    module_order,
    hidden_modules,
    column_count,
    settings,
    updated_by
)
SELECT
    p.id,
    'tactical',
    '["mandate","manager","team","queue","schedules","mail","history","cost"]'::jsonb,
    '[]'::jsonb,
    2,
    '{"show_evidence":true,"show_freshness":true,"operator_configurable":true,"department_key":"tactical"}'::jsonb,
    'migration_137'
FROM ops.workspace_profiles p
WHERE p.profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO UPDATE SET
    settings = ops.workspace_layouts.settings || EXCLUDED.settings,
    updated_at = now();

COMMIT;
