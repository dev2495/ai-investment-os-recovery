BEGIN;
INSERT INTO agent.runtime_state_edges(domain,from_state,to_state) VALUES
 ('task','queued','needs_review'),('task','handoff_pending','blocked'),('task','handoff_pending','needs_review')
ON CONFLICT DO NOTHING;
-- INSERT initialization is an atomic runtime boundary. The legacy provider
-- evaluator still decides every real task's eligibility; only a zero-capability
-- synthetic lifecycle fixture has no provider dependency to evaluate.
CREATE OR REPLACE FUNCTION agent.auto_gate_task_providers_after_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior_fence text:=coalesce(current_setting('aios.runtime_task',true),''); provider_free boolean;
BEGIN
    IF NEW.runtime_protocol='lease_v1' THEN
        PERFORM set_config('aios.runtime_task',NEW.id::text,true);
    END IF;
    SELECT NEW.runtime_protocol='lease_v1' AND NEW.task_class='phase2_canary'
      AND NEW.source_kind='phase2_live_canary' AND NEW.runtime_scope='internal'
      AND NEW.client_id IS NULL AND NEW.book_id IS NULL AND NEW.data_class='public'
      AND NEW.approval_required=false AND NEW.recovery_policy='idempotent_read'
      AND NEW.runtime_context @> '{"synthetic":true,"public_fixture_only":true,"model_calls_allowed":false,"provider_calls_allowed":false,"client_writes_allowed":false,"external_writes_allowed":false,"broker_write_allowed":false}'::jsonb
      AND EXISTS(SELECT 1 FROM agent.profiles p JOIN agent.agent_workspaces w ON w.agent_id=p.id
        WHERE p.id=NEW.agent_id AND p.agent_name=NEW.owner_agent AND p.department='runtime'
        AND p.role_scope='synthetic_canary' AND p.permission_level='read_only'
        AND p.default_model_route IS NULL AND cardinality(p.default_tools)=0
        AND w.daily_token_budget=0 AND w.allowed_task_classes=ARRAY['phase2_canary']::text[]
        AND w.denied_capabilities @> ARRAY['model.*','provider.*','broker.*','external.*','client.*','credential.*']::text[])
      AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(coalesce(NEW.evidence,'[]')) e
        WHERE e ? 'provider_key' OR e ? 'providerKey') INTO provider_free;
    IF coalesce(provider_free,false) THEN
      UPDATE agent.tasks SET evidence=coalesce(evidence,'[]')||jsonb_build_array(jsonb_build_object(
        'source','agent.auto_gate_task_providers_after_insert','overall_status','not_applicable',
        'reason','governed_provider_free_synthetic_fixture','broker_write_allowed',false)) WHERE id=NEW.id;
    ELSE
      PERFORM core.evaluate_task_provider_assignment_gates(NEW.id,'Jarvis','task_insert_trigger');
    END IF;
    PERFORM set_config('aios.runtime_task',prior_fence,true);
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- PL/pgSQL rolls back the failed block, including its local fence setting.
    -- Restore only this new task's initialization authority for fail-closed state.
    IF NEW.runtime_protocol='lease_v1' THEN PERFORM set_config('aios.runtime_task',NEW.id::text,true); END IF;
    UPDATE agent.tasks SET status='blocked',evidence=coalesce(evidence,'[]')||jsonb_build_array(jsonb_build_object(
      'source','agent.auto_gate_task_providers_after_insert','reason','provider_gate_evaluation_failed','task_id',NEW.id)),
      updated_at=now() WHERE id=NEW.id;
    PERFORM set_config('aios.runtime_task',prior_fence,true);
    RETURN NEW;
END $$;
DO $$ BEGIN
 IF to_regclass('core.schema_migrations') IS NOT NULL THEN
 INSERT INTO core.schema_migrations(migration_number,migration_key,definition_checksum_sha256,description,metadata)
 VALUES(265,'265_managed_task_provider_insert_gate_v1','d47f676a1a1f8145f5753f9bc24a98a6d81d795a312e4330eb9ff769952178c7',
 'Preserve legacy provider gates inside managed insertion boundary','{"broker_write_allowed":false}') ON CONFLICT(migration_number) DO NOTHING;
 IF NOT EXISTS(SELECT 1 FROM core.schema_migrations WHERE migration_number=265
 AND migration_key='265_managed_task_provider_insert_gate_v1'
 AND definition_checksum_sha256='d47f676a1a1f8145f5753f9bc24a98a6d81d795a312e4330eb9ff769952178c7') THEN RAISE EXCEPTION 'migration 265 ledger mismatch'; END IF;
 END IF;
END $$;
COMMIT;
