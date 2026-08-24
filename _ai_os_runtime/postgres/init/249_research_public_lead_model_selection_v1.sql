\set ON_ERROR_STOP on

BEGIN;

-- The user authorized a cost-aware public-company research routing decision.
-- DeepSeek V4 Flash handles high-volume specialist work through the existing
-- enabled route. The lead/review route below is enabled only when the local
-- canary ledger contains a completed, structured-output-valid DeepSeek V4 Pro
-- result. No secret, raw response or private evidence is stored here.
WITH selected AS (
    SELECT id
    FROM research.public_model_canary_runs
    WHERE candidate_route = 'openrouter_public_lead_deepseek_v4_pro_canary'
      AND status = 'completed'
      AND coalesce((score->>'structured_output_valid')::boolean, false)
    ORDER BY updated_at DESC, id DESC
    LIMIT 1
), marked AS (
    UPDATE research.public_model_canary_runs canary
    SET selected_for_role = (canary.id = (SELECT id FROM selected)),
        updated_at = now()
    WHERE canary.candidate_route IN (
        'openrouter_public_lead_glm52_canary',
        'openrouter_public_lead_deepseek_v4_pro_canary'
    )
    RETURNING id
)
INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
)
SELECT
    'openrouter_public_lead_deepseek_v4_pro',
    'public_company_lead_analysis',
    'openrouter',
    'deepseek/deepseek-v4-pro-0813',
    NULL,
    NULL,
    'cloud_medium',
    'Public-only lead, synthesis and independent-review route. Enabled only after a successful local canary and explicit user selection; ZDR and per-run approval remain mandatory.',
    EXISTS (SELECT 1 FROM selected)
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;

DO $route_guard$
BEGIN
    IF EXISTS (
        SELECT 1 FROM agent.model_routes route
        WHERE route.route_name = 'openrouter_public_lead_deepseek_v4_pro'
          AND route.enabled
    ) AND NOT EXISTS (
        SELECT 1 FROM research.public_model_canary_runs canary
        WHERE canary.candidate_route = 'openrouter_public_lead_deepseek_v4_pro_canary'
          AND canary.status = 'completed'
          AND canary.selected_for_role
          AND coalesce((canary.score->>'structured_output_valid')::boolean, false)
    ) THEN
        RAISE EXCEPTION 'public lead route cannot be enabled without a selected successful canary';
    END IF;
END
$route_guard$;

INSERT INTO core.schema_migrations (
    migration_number, migration_key, definition_checksum_sha256, description, metadata
)
VALUES (
    249,
    '249_research_public_lead_model_selection_v1',
    'eb1b33bf9ffd28d87c1e3b57b67a106d4fc41247ad3f4f58ec6a1a2ad544bae7',
    'Canary-gated cost-aware public-company research model routing',
    '{"public_only":true,"zdr_required":true,"private_data_egress_allowed":false,"broker_write_allowed":false,"specialists":"deepseek-v4-flash","lead":"deepseek-v4-pro"}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

DO $migration_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.schema_migrations
        WHERE migration_number = 249
          AND migration_key = '249_research_public_lead_model_selection_v1'
          AND definition_checksum_sha256 = 'eb1b33bf9ffd28d87c1e3b57b67a106d4fc41247ad3f4f58ec6a1a2ad544bae7'
    ) THEN
        RAISE EXCEPTION 'migration 249 ledger mismatch';
    END IF;
END
$migration_guard$;

COMMIT;
