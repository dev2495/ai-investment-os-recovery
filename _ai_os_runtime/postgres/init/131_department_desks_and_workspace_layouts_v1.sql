BEGIN;

UPDATE ops.workspace_profiles
SET navigation = jsonb_set(
        coalesce(navigation, '{}'::jsonb),
        '{visible}',
        '["command","approvals","agents","departments","committees","governance","portfolio","clients","research","ideas","arsenal","trading","quant","risk","capital","treasury","models","reports","system"]'::jsonb,
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
    layout.workspace_key,
    layout.module_order,
    '[]'::jsonb,
    layout.column_count,
    '{"show_evidence":true,"show_freshness":true,"operator_configurable":true}'::jsonb,
    'migration_131'
FROM ops.workspace_profiles p
CROSS JOIN (
    VALUES
        ('command', '["brief","gates","delegations","inbox","approvals","widgets","queue","freshness"]'::jsonb, 2),
        ('approvals', '["summary","approval_queue","execution_gates"]'::jsonb, 2),
        ('agents', '["office_command","roster","schedules","committees","worker_queue","mail"]'::jsonb, 2),
        ('departments', '["mandate","manager","team","queue","schedules","mail","history","cost"]'::jsonb, 2),
        ('committees', '["summary","committee_rooms","followups"]'::jsonb, 2),
        ('governance', '["summary","policies","architecture","safety"]'::jsonb, 2),
        ('portfolio', '["clients","books","positions","exposure","coordination","readiness"]'::jsonb, 2),
        ('clients', '["folios","accounts","positions","reconciliation","manual_updates"]'::jsonb, 2),
        ('research', '["theses","filings","news","papers","special_situations","outputs"]'::jsonb, 2),
        ('ideas', '["pipeline","dossiers","hypotheses","research_tasks"]'::jsonb, 2),
        ('arsenal', '["intake","templates","candidates","data","backtest","optimizer","committee","paper"]'::jsonb, 2),
        ('trading', '["signals","tradingview","journals","paper_monitors","execution_gates"]'::jsonb, 2),
        ('quant', '["validation","optimization","allocation","promotion","drift"]'::jsonb, 2),
        ('risk', '["limits","events","stress","monte_carlo","conflicts","execution"]'::jsonb, 2),
        ('capital', '["policy","analysis","committee"]'::jsonb, 2),
        ('treasury', '["watchlist","macro_news","freshness"]'::jsonb, 2),
        ('models', '["sources","models","routes","assignments","privacy","cost","escalations"]'::jsonb, 2),
        ('reports', '["outputs","schedules","runs","lineage","gaps"]'::jsonb, 2),
        ('system', '["health","sources","workers","storage","backup","recovery"]'::jsonb, 2)
) AS layout(workspace_key, module_order, column_count)
WHERE p.profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO UPDATE SET
    module_order = CASE
        WHEN ops.workspace_layouts.module_order = '[]'::jsonb THEN EXCLUDED.module_order
        ELSE ops.workspace_layouts.module_order
    END,
    settings = ops.workspace_layouts.settings || EXCLUDED.settings,
    updated_at = now();

COMMIT;
