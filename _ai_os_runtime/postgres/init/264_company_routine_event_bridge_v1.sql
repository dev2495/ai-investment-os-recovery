BEGIN;
-- A durable outbox is the recovery boundary between a database event and SSD.
CREATE TABLE IF NOT EXISTS agent.company_routine_outputs (
  run_key text PRIMARY KEY REFERENCES agent.routine_runs(run_key),
  update_id bigint NOT NULL UNIQUE REFERENCES research.company_research_updates(id),
  event_hash text NOT NULL UNIQUE CHECK(event_hash ~ '^[0-9a-f]{64}$'),
  artifact jsonb NOT NULL CHECK(NOT core.jsonb_contains_raw_secret(artifact)),
  artifact_status text NOT NULL DEFAULT 'pending' CHECK(artifact_status IN ('pending','stored')),
  projection_status text NOT NULL DEFAULT 'pending' CHECK(projection_status IN ('pending','projected')),
  managed_note_path text NOT NULL CHECK(managed_note_path ~ '^00 AI OS/Managed/Company Updates/[0-9a-f]{64}\.md$'),
  managed_block text NOT NULL DEFAULT 'aios-company-update-v1' CHECK(managed_block='aios-company-update-v1'),
  created_at timestamptz NOT NULL DEFAULT now(),
  stored_at timestamptz,
  broker_write_allowed boolean NOT NULL DEFAULT false CHECK(NOT broker_write_allowed)
);
CREATE OR REPLACE FUNCTION agent.protect_company_routine_snapshot()
RETURNS trigger LANGUAGE plpgsql SET search_path=agent,pg_temp AS $$
BEGIN
  IF NEW.run_key IS DISTINCT FROM OLD.run_key OR NEW.update_id IS DISTINCT FROM OLD.update_id
    OR NEW.event_hash IS DISTINCT FROM OLD.event_hash OR NEW.artifact IS DISTINCT FROM OLD.artifact
    OR NEW.managed_note_path IS DISTINCT FROM OLD.managed_note_path THEN
    RAISE EXCEPTION 'company routine event snapshot is immutable';
  END IF;
  RETURN NEW;
END $$;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='agent.company_routine_outputs'::regclass AND tgname='company_routine_snapshot_immutable') THEN
  CREATE TRIGGER company_routine_snapshot_immutable BEFORE UPDATE ON agent.company_routine_outputs
  FOR EACH ROW EXECUTE FUNCTION agent.protect_company_routine_snapshot();
 END IF;
END $$;


CREATE OR REPLACE FUNCTION agent.materialize_company_routine_events(p_limit integer DEFAULT 20)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=agent,research,core,pg_temp AS $$
DECLARE item record; receipt jsonb; event_id text; body jsonb; count_created integer:=0;
BEGIN
  -- Serialize materialization; the existing daemon is the sole scheduling authority.
  PERFORM pg_advisory_xact_lock(hashtext('company_routine_event_bridge_v1'));
  IF NOT EXISTS (SELECT 1 FROM agent.routine_definitions WHERE routine_key='research_company_change_monitor' AND control_state='enabled') THEN RETURN 0; END IF;
  FOR item IN
    SELECT u.* FROM research.company_research_updates u
    JOIN research.watchlist_items w ON w.id=u.watchlist_item_id
    JOIN research.watchlists l ON l.id=w.watchlist_id
    WHERE l.watchlist_key='company_research_following' AND l.status='active' AND w.status='active'
      AND upper(w.symbol)=upper(u.symbol) AND upper(w.exchange)=upper(u.exchange)
      AND coalesce(w.metadata->>'monitoring_enabled',w.metadata->>'automatic_collection','true')='true'
      AND u.source_kind IN ('corporate_filing','authorized_public_news','research_case_event')
      AND u.source_identifier IS NOT NULL AND jsonb_array_length(u.evidence)>0
      AND NOT EXISTS(SELECT 1 FROM agent.company_routine_outputs o WHERE o.update_id=u.id)
    ORDER BY u.id LIMIT greatest(1,least(100,p_limit))
  LOOP
    event_id:=encode(sha256(convert_to('research.company_research_updates:'||item.id::text||':'||item.update_key,'UTF8')),'hex');
    body:=jsonb_build_object('source_table','research.company_research_updates','update_id',item.id,
      'event_hash',event_id,'symbol',item.symbol,'exchange',item.exchange,'event_type',item.update_type,
      'source_identifier',item.source_identifier,'source_url',item.source_url,'title',item.title,
      'summary',item.summary,'evidence',item.evidence,'effective_at',item.effective_at,
      'decision_impact',item.decision_impact,'human_decision_required',true,
      'authorized_stored_source_only',true,'model_calls',0,'broker_write_allowed',false);
    receipt:=agent.start_routine_run('research_company_change_monitor','event',event_id,
      'research_company_change_monitor:'||event_id,body,'Company Research Monitor',false);
    INSERT INTO agent.company_routine_outputs(run_key,update_id,event_hash,artifact,managed_note_path)
    VALUES(receipt->>'run_key',item.id,event_id,body,'00 AI OS/Managed/Company Updates/'||event_id||'.md')
    ON CONFLICT DO NOTHING;
    count_created:=count_created+1;
  END LOOP;
  RETURN count_created;
END $$;

CREATE OR REPLACE FUNCTION agent.complete_company_routine_artifact(p_run_key text,p_path text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=agent,pg_temp AS $$
DECLARE output agent.company_routine_outputs; receipt jsonb;
BEGIN
  SELECT * INTO output FROM agent.company_routine_outputs WHERE run_key=p_run_key FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown company routine output'; END IF;
  IF output.artifact_status='stored' THEN RETURN jsonb_build_object('duplicate',true,'run_key',p_run_key); END IF;
  IF p_path <> '/Volumes/Devarsh SSD/AI OS Data/artifacts/routines/research_company_change_monitor/'||p_run_key||'.json' THEN RAISE EXCEPTION 'unexpected artifact destination'; END IF;
  receipt:=agent.finish_routine_run(p_run_key,'completed','Stored followed-company update; human decision remains pending',
    jsonb_build_array(jsonb_build_object('source_table','research.company_research_updates','id',output.update_id)),p_path,p_hash,NULL);
  UPDATE agent.company_routine_outputs SET artifact_status='stored',stored_at=clock_timestamp() WHERE run_key=p_run_key;
  RETURN receipt;
END $$;
REVOKE ALL ON agent.company_routine_outputs FROM PUBLIC;
REVOKE ALL ON FUNCTION agent.materialize_company_routine_events(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION agent.complete_company_routine_artifact(text,text,text) FROM PUBLIC;
INSERT INTO core.schema_migrations(migration_number,migration_key,definition_checksum_sha256,description,metadata)
VALUES(264,'264_company_routine_event_bridge_v1',encode(sha256(convert_to('264_company_routine_event_bridge_v1','UTF8')),'hex'),
 'Durable authorized company-event routine outbox and managed projection contract',
 '{"auto_enable":false,"model_calls":0,"broker_write_allowed":false}') ON CONFLICT(migration_number) DO NOTHING;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM core.schema_migrations WHERE migration_number=264
   AND migration_key='264_company_routine_event_bridge_v1'
   AND definition_checksum_sha256=encode(sha256(convert_to('264_company_routine_event_bridge_v1','UTF8')),'hex')) THEN
  RAISE EXCEPTION 'migration 264 ledger mismatch';
 END IF;
END $$;
COMMIT;
