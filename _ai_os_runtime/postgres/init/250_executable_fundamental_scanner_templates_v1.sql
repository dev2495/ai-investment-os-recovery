\set ON_ERROR_STOP on

BEGIN;

-- Four executable global templates use only the deterministic metrics currently
-- implemented by Research Desk. The older named frameworks remain reference-only
-- until their missing metrics and validation fixtures exist.
WITH seed(scanner_key,name,description,definition_json,definition_hash) AS (
    VALUES
    (
      'research_quality_compounders',
      'Quality compounders — executable draft',
      'High growth, return on capital, cash conversion and balance-sheet quality using only validated point-in-time Research Desk metrics.',
      '{"api_version":"aios.scanner/v1","filters":{"all":[{"metric":"revenue_cagr_5y","operator":"gte","value":8.0},{"metric":"roce_proxy","operator":"gte","value":15.0},{"metric":"cfo_pat","operator":"gte","value":75.0},{"metric":"debt_to_equity","operator":"lte","value":1.0}]},"requirements":{"minimum_data_completeness_pct":100.0,"missing_data_policy":"exclude_and_report","required_metrics":["cfo_pat","debt_to_equity","revenue_cagr_5y","roce_proxy"]},"score":{"components":[{"direction":"higher","metric":"revenue_cagr_5y","weight":0.25},{"direction":"higher","metric":"roce_proxy","weight":0.3},{"direction":"higher","metric":"cfo_pat","weight":0.25},{"direction":"lower","metric":"debt_to_equity","weight":0.2}]},"universe":{"as_of_policy":"point_in_time","countries":["IN"],"exchanges":["BSE","NSE"]}}'::jsonb,
      '29bf81c78eb103416e7a53a60325e92f7e60371489c4cf00e54fa5534ecd0cf4'
    ),
    (
      'research_cash_flow_quality',
      'Cash-flow quality — executable draft',
      'Cash conversion, free-cash-flow margin and reinvestment intensity using validated point-in-time Research Desk metrics.',
      '{"api_version":"aios.scanner/v1","filters":{"all":[{"metric":"cfo_pat","operator":"gte","value":80.0},{"metric":"fcf_margin","operator":"gte","value":5.0},{"metric":"capex_to_revenue","operator":"lte","value":25.0}]},"requirements":{"minimum_data_completeness_pct":100.0,"missing_data_policy":"exclude_and_report","required_metrics":["capex_to_revenue","cfo_pat","fcf_margin"]},"score":{"components":[{"direction":"higher","metric":"cfo_pat","weight":0.4},{"direction":"higher","metric":"fcf_margin","weight":0.4},{"direction":"lower","metric":"capex_to_revenue","weight":0.2}]},"universe":{"as_of_policy":"point_in_time","countries":["IN"],"exchanges":["BSE","NSE"]}}'::jsonb,
      'e6560bdd839500fc488ed0aefdd1a197dbe3ab60dbddf41f35d0fe34777cbcdc'
    ),
    (
      'research_earnings_margin_acceleration',
      'Earnings and margin acceleration — executable draft',
      'Five-year revenue and PAT growth with operating and PAT margin floors using validated point-in-time Research Desk metrics.',
      '{"api_version":"aios.scanner/v1","filters":{"all":[{"metric":"revenue_cagr_5y","operator":"gte","value":8.0},{"metric":"pat_cagr_5y","operator":"gte","value":10.0},{"metric":"ebitda_margin","operator":"gte","value":10.0},{"metric":"pat_margin","operator":"gte","value":5.0}]},"requirements":{"minimum_data_completeness_pct":100.0,"missing_data_policy":"exclude_and_report","required_metrics":["ebitda_margin","pat_cagr_5y","pat_margin","revenue_cagr_5y"]},"score":{"components":[{"direction":"higher","metric":"revenue_cagr_5y","weight":0.2},{"direction":"higher","metric":"pat_cagr_5y","weight":0.3},{"direction":"higher","metric":"ebitda_margin","weight":0.25},{"direction":"higher","metric":"pat_margin","weight":0.25}]},"universe":{"as_of_policy":"point_in_time","countries":["IN"],"exchanges":["BSE","NSE"]}}'::jsonb,
      '6ad30f2301feeb100838f88b2dd1b498aeae828dad4995a5f8740392d4b851d1'
    ),
    (
      'research_balance_sheet_resilience',
      'Balance-sheet resilience — executable draft',
      'Leverage, interest coverage and current-ratio floors using validated point-in-time Research Desk metrics.',
      '{"api_version":"aios.scanner/v1","filters":{"all":[{"metric":"debt_to_equity","operator":"lte","value":0.75},{"metric":"interest_coverage","operator":"gte","value":4.0},{"metric":"current_ratio","operator":"gte","value":1.2}]},"requirements":{"minimum_data_completeness_pct":100.0,"missing_data_policy":"exclude_and_report","required_metrics":["current_ratio","debt_to_equity","interest_coverage"]},"score":{"components":[{"direction":"lower","metric":"debt_to_equity","weight":0.35},{"direction":"higher","metric":"interest_coverage","weight":0.4},{"direction":"higher","metric":"current_ratio","weight":0.25}]},"universe":{"as_of_policy":"point_in_time","countries":["IN"],"exchanges":["BSE","NSE"]}}'::jsonb,
      '7f56c90aac164e1be46dd2f7252544a7028f1e6542e9e76d863a0506567d2b68'
    )
), definitions AS (
    INSERT INTO market.scanner_definitions (
        scope_key,scanner_key,name,description,owner_agent,status,tags,metadata,created_by
    )
    SELECT
        'global:public',scanner_key,name,description,'Fundamental Research Analyst','draft',
        ARRAY['template','fundamental','executable_draft']::text[],
        jsonb_build_object(
          'template_state','executable_draft',
          'copy_required',true,
          'publication_requires_human_approval',true,
          'broker_write_allowed',false,
          'external_write_allowed',false
        ),
        'migration:250'
    FROM seed
    ON CONFLICT (scope_key,scanner_key) DO UPDATE SET
        name=EXCLUDED.name,
        description=EXCLUDED.description,
        tags=EXCLUDED.tags,
        metadata=market.scanner_definitions.metadata||EXCLUDED.metadata,
        updated_at=now()
    RETURNING id,scope_key,scanner_key
)
INSERT INTO market.scanner_versions (
    scope_key,scanner_definition_id,version,api_version,dsl_version,status,
    definition_json,definition_hash,universe_config,filter_config,score_config,
    output_config,calculation_revision,source_request_text,created_by
)
SELECT
    definition.scope_key,definition.id,1,'v1','v1','draft',
    seed.definition_json,seed.definition_hash,
    seed.definition_json->'universe',seed.definition_json->'filters',seed.definition_json->'score',
    '{"missing_data_policy":"exclude_and_report","broker_write_allowed":false,"external_write_allowed":false}'::jsonb,
    'research-desk-v1',
    'Executable global template; copy into the operator workspace, inspect validation coverage, explicitly approve publication, then explicitly confirm any run.',
    'migration:250'
FROM seed
JOIN definitions definition
  ON definition.scope_key='global:public' AND definition.scanner_key=seed.scanner_key
ON CONFLICT (scope_key,scanner_definition_id,version) DO NOTHING;

DO $template_guard$
DECLARE
    executable_count integer;
BEGIN
    SELECT count(*) INTO executable_count
    FROM market.scanner_definitions definition
    JOIN market.scanner_versions version
      ON version.scanner_definition_id=definition.id
     AND version.scope_key=definition.scope_key
    WHERE definition.scope_key='global:public'
      AND definition.scanner_key IN (
        'research_quality_compounders',
        'research_cash_flow_quality',
        'research_earnings_margin_acceleration',
        'research_balance_sheet_resilience'
      )
      AND version.version=1
      AND version.status='draft'
      AND version.definition_json->>'api_version'='aios.scanner/v1'
      AND market.scanner_dsl_is_safe(version.definition_json);

    IF executable_count <> 4 THEN
        RAISE EXCEPTION 'migration 250 executable scanner template count mismatch: %', executable_count;
    END IF;

    IF EXISTS (
        SELECT 1 FROM market.scanner_runs run
        JOIN market.scanner_versions version ON version.id=run.scanner_version_id
        JOIN market.scanner_definitions definition ON definition.id=version.scanner_definition_id
        WHERE definition.created_by='migration:250'
    ) OR EXISTS (
        SELECT 1 FROM market.scanner_alerts alert
        JOIN market.scanner_versions version ON version.id=alert.scanner_version_id
        JOIN market.scanner_definitions definition ON definition.id=version.scanner_definition_id
        WHERE definition.created_by='migration:250'
    ) OR EXISTS (
        SELECT 1 FROM market.scanner_schedules schedule
        JOIN market.scanner_versions version ON version.id=schedule.scanner_version_id
        JOIN market.scanner_definitions definition ON definition.id=version.scanner_definition_id
        WHERE definition.created_by='migration:250' AND schedule.enabled
    ) THEN
        RAISE EXCEPTION 'migration 250 must not run, alert, schedule or publish a scanner';
    END IF;
END
$template_guard$;

INSERT INTO core.schema_migrations (
    migration_number,migration_key,definition_checksum_sha256,description,metadata
)
VALUES (
    250,
    '250_executable_fundamental_scanner_templates_v1',
    '9c1de4f75ae85aa0925b5417b57d4fcc4b6929c86c4a1f1ff86b2b9f3f6ed962',
    'Copy-only executable Research Desk scanner templates using the supported deterministic PIT metric library',
    '{"templates":4,"publication_started":false,"scanner_runs_started":false,"alerts_created":false,"schedules_enabled":false,"broker_write_allowed":false,"external_write_allowed":false}'::jsonb
)
ON CONFLICT (migration_number) DO NOTHING;

COMMIT;
