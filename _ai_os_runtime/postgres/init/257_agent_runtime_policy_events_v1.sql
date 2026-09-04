-- Additive policy, state, recovery and scoped replay contracts. No grants to a
-- broker, provider, shell or client workspace are introduced by this migration.
BEGIN;

CREATE TABLE IF NOT EXISTS agent.runtime_settings (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    active_heartbeat_seconds integer NOT NULL DEFAULT 15 CHECK(active_heartbeat_seconds BETWEEN 1 AND 60),
    idle_heartbeat_seconds integer NOT NULL DEFAULT 60 CHECK(idle_heartbeat_seconds BETWEEN 2 AND 300),
    lease_seconds integer NOT NULL DEFAULT 45,
    claim_mode text NOT NULL DEFAULT 'enabled' CHECK(claim_mode IN ('enabled','draining','disabled')),
    CHECK(lease_seconds BETWEEN active_heartbeat_seconds*3 AND 600)
);
INSERT INTO agent.runtime_settings DEFAULT VALUES ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS agent.agent_workspaces (
    agent_id bigint PRIMARY KEY REFERENCES agent.profiles(id),
    workspace_key text NOT NULL UNIQUE CHECK(workspace_key ~ '^[a-zA-Z0-9_.-]{1,120}$'),
    role_version integer NOT NULL DEFAULT 1 CHECK(role_version>0),
    owner_agent_id bigint REFERENCES agent.profiles(id),
    escalation_agent_id bigint REFERENCES agent.profiles(id),
    room_key text NOT NULL,
    allowed_task_classes text[] NOT NULL DEFAULT ARRAY['general'],
    allowed_scopes text[] NOT NULL DEFAULT ARRAY['internal'],
    allowed_books bigint[] NOT NULL DEFAULT '{}',
    allowed_clients bigint[] NOT NULL DEFAULT '{}',
    allowed_data_classes text[] NOT NULL DEFAULT ARRAY['public','internal'],
    denied_capabilities text[] NOT NULL DEFAULT ARRAY['broker.*','credential.*','client.pii.export','shell.production'],
    daily_token_budget bigint CHECK(daily_token_budget>=0),
    capability_status text NOT NULL DEFAULT 'PARTIAL' CHECK(capability_status IN ('UNAVAILABLE','PARTIAL','READY')),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO agent.agent_workspaces(agent_id,workspace_key,room_key)
SELECT id,agent_key,department FROM agent.profiles ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION agent.ensure_runtime_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO agent.agent_workspaces(agent_id,workspace_key,room_key,role_version)
    VALUES(NEW.id,NEW.agent_key,NEW.department,NEW.role_version) ON CONFLICT DO NOTHING;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER runtime_workspace AFTER INSERT ON agent.profiles
FOR EACH ROW EXECUTE FUNCTION agent.ensure_runtime_workspace();
-- Reuse the installed hierarchy rather than inventing new reporting lines.
DO $$ BEGIN
    IF to_regclass('agent.org_hierarchy') IS NOT NULL THEN
        EXECUTE 'UPDATE agent.agent_workspaces w SET owner_agent_id=manager.id,escalation_agent_id=manager.id
          FROM agent.profiles p JOIN agent.org_hierarchy h ON h.agent_name=p.agent_name
          JOIN agent.profiles manager ON manager.agent_name=h.reports_to_agent
          WHERE w.agent_id=p.id AND w.owner_agent_id IS NULL';
    END IF;
END $$;
ALTER TABLE agent.tasks ADD COLUMN IF NOT EXISTS book_id bigint,
    ADD COLUMN IF NOT EXISTS client_id bigint,
    ADD COLUMN IF NOT EXISTS data_class text NOT NULL DEFAULT 'internal'
        CHECK(data_class IN ('public','internal','house_confidential','client_private')),
    ADD COLUMN IF NOT EXISTS runtime_context jsonb NOT NULL DEFAULT '{}';
ALTER TABLE agent.task_leases ADD COLUMN IF NOT EXISTS policy_snapshot jsonb NOT NULL DEFAULT '{}';
ALTER TABLE agent.workers ADD COLUMN IF NOT EXISTS supported_tools text[] NOT NULL DEFAULT '{}';

CREATE OR REPLACE FUNCTION agent.runtime_policy_snapshot(p_agent bigint) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; binding jsonb; budget jsonb;
BEGIN
    SELECT jsonb_build_object('agent_id',p.id,'agent_key',p.agent_key,'agent_name',p.agent_name,
        'role',p.role_scope,'role_version',p.role_version,'policy_version',w.role_version,
        'department',p.department,'room',w.room_key,'owner_agent_id',w.owner_agent_id,
        'escalation_agent_id',w.escalation_agent_id,'permission_level',p.permission_level,
        'tools',p.default_tools,'guardrails',p.guardrails,'denied_capabilities',w.denied_capabilities,
        'allowed_task_classes',w.allowed_task_classes,'allowed_scopes',w.allowed_scopes,
        'allowed_books',w.allowed_books,'allowed_clients',w.allowed_clients,'allowed_data_classes',w.allowed_data_classes,
        'workspace_key',w.workspace_key,'daily_token_budget',w.daily_token_budget,
        'max_parallel_tasks',p.max_parallel_tasks,'default_model_route',p.default_model_route,
        'broker_write_allowed',false) INTO result
    FROM agent.profiles p JOIN agent.agent_workspaces w ON w.agent_id=p.id WHERE p.id=p_agent;
    IF result IS NULL THEN RAISE EXCEPTION 'agent has no runtime policy'; END IF;
    IF to_regclass('agent.agent_model_assignments') IS NOT NULL THEN
        EXECUTE 'SELECT jsonb_build_object(''primary_route'',primary_route,''fallback_route'',fallback_route,
          ''escalation_route'',escalation_route,''context_policy'',context_policy,''cost_policy'',cost_policy)
          FROM agent.agent_model_assignments WHERE agent_name=$1' INTO binding USING result->>'agent_name';
    END IF;
    IF to_regclass('agent.model_cost_caps') IS NOT NULL THEN
        EXECUTE 'SELECT jsonb_build_object(''daily_cap_usd'',daily_cap_usd,''monthly_cap_usd'',monthly_cap_usd,
          ''cloud_requires_approval'',cloud_requires_approval,''hard_stop_on_breach'',hard_stop_on_breach)
          FROM agent.model_cost_caps WHERE agent_name=$1' INTO budget USING result->>'agent_name';
    END IF;
    RETURN result||jsonb_build_object('model_assignment',binding,'cost_policy',budget);
END $$;

CREATE OR REPLACE FUNCTION agent.guard_runtime_dependency() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Serializes edge insertion, including two concurrent opposite edges.
    PERFORM pg_advisory_xact_lock(257,1);
    IF NEW.task_id=NEW.depends_on_task_id OR EXISTS(
        WITH RECURSIVE parents(id) AS (SELECT NEW.depends_on_task_id UNION
          SELECT d.depends_on_task_id FROM agent.task_dependencies d JOIN parents p ON d.task_id=p.id)
        SELECT 1 FROM parents WHERE id=NEW.task_id) THEN RAISE EXCEPTION 'task dependency cycle denied'; END IF;
    IF EXISTS(SELECT 1 FROM agent.tasks t JOIN agent.tasks p ON p.id=NEW.depends_on_task_id
        WHERE t.id=NEW.task_id AND (t.runtime_scope<>p.runtime_scope
          OR t.book_id IS DISTINCT FROM p.book_id OR t.client_id IS DISTINCT FROM p.client_id)) THEN
        RAISE EXCEPTION 'cross-scope dependency denied';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER runtime_dependency BEFORE INSERT OR UPDATE ON agent.task_dependencies
FOR EACH ROW EXECUTE FUNCTION agent.guard_runtime_dependency();

CREATE TABLE IF NOT EXISTS agent.runtime_state_edges (
    domain text NOT NULL, from_state text NOT NULL, to_state text NOT NULL,
    PRIMARY KEY(domain,from_state,to_state)
);
INSERT INTO agent.runtime_state_edges
SELECT 'task',a,b FROM (VALUES
 ('queued',ARRAY['in_progress','paused','cancelled','blocked']),
 ('in_progress',ARRAY['queued','needs_review','completed','blocked','failed','paused','cancelled']),
 ('paused',ARRAY['queued','cancelled']),('blocked',ARRAY['queued','needs_review','cancelled']),
 ('needs_review',ARRAY['completed','blocked','cancelled']),('completed',ARRAY['completed']),
 ('failed',ARRAY['queued','cancelled']),('cancelled',ARRAY['cancelled'])) t(a,states)
CROSS JOIN LATERAL unnest(states) b ON CONFLICT DO NOTHING;
INSERT INTO agent.runtime_state_edges
SELECT domain,a,b FROM (VALUES
 ('worker','IDLE',ARRAY['RUNNING','STALE','STOPPED','QUARANTINED']),
 ('worker','RUNNING',ARRAY['IDLE','STALE','STOPPED','QUARANTINED']),
 ('worker','STALE',ARRAY['IDLE','RUNNING','STOPPED','QUARANTINED']),
 ('lease','ACTIVE',ARRAY['RELEASED','EXPIRED']),
 ('step','none',ARRAY['started','recorded']),('step','started',ARRAY['recorded','uncertain']),
 ('step','uncertain',ARRAY['recorded']),
 ('approval','pending',ARRAY['approved','rejected','cancelled','expired']),
 ('model_call','queued',ARRAY['running','blocked','cancelled']),
 ('model_call','running',ARRAY['completed','failed','blocked','uncertain']),
 ('tool_call','queued',ARRAY['running','blocked','cancelled']),
 ('tool_call','running',ARRAY['completed','failed','blocked','uncertain']),
 ('routine','queued',ARRAY['running','blocked','cancelled']),
 ('routine','running',ARRAY['completed','failed','blocked','uncertain']),
 ('execution','NO_ACTION',ARRAY['PROPOSED']),('execution','PROPOSED',ARRAY['SIMULATED','REJECTED','CANCELLED']),
 ('execution','SIMULATED',ARRAY['RISK_CHECKED','REJECTED','CANCELLED']),
 ('execution','RISK_CHECKED',ARRAY['POLICY_CHECKED','REJECTED','CANCELLED']),
 ('execution','POLICY_CHECKED',ARRAY['AWAITING_APPROVAL','REJECTED','CANCELLED'])
) t(domain,a,states) CROSS JOIN LATERAL unnest(states) b ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION agent.runtime_transition_allowed(p_domain text,p_from text,p_to text)
RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT p_from IS NOT DISTINCT FROM p_to OR EXISTS(SELECT 1 FROM agent.runtime_state_edges
        WHERE domain=p_domain AND from_state=p_from AND to_state=p_to)
$$;
CREATE OR REPLACE FUNCTION agent.guard_runtime_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE domain text:=TG_ARGV[0]; old_state text; new_state text;
BEGIN
    IF domain='task' AND to_jsonb(OLD)->>'runtime_protocol'<>'lease_v1' THEN RETURN NEW; END IF;
    old_state:=to_jsonb(OLD)->>TG_ARGV[1]; new_state:=to_jsonb(NEW)->>TG_ARGV[1];
    IF NOT agent.runtime_transition_allowed(domain,old_state,new_state) THEN
        RAISE EXCEPTION 'illegal % state transition: % -> %',domain,old_state,new_state;
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER runtime_task_state BEFORE UPDATE ON agent.tasks FOR EACH ROW
EXECUTE FUNCTION agent.guard_runtime_state('task','status');
CREATE OR REPLACE TRIGGER runtime_worker_state BEFORE UPDATE ON agent.workers FOR EACH ROW
EXECUTE FUNCTION agent.guard_runtime_state('worker','status');
CREATE OR REPLACE TRIGGER runtime_lease_state BEFORE UPDATE ON agent.task_leases FOR EACH ROW
EXECUTE FUNCTION agent.guard_runtime_state('lease','status');
CREATE OR REPLACE TRIGGER runtime_step_state BEFORE UPDATE ON agent.task_steps FOR EACH ROW
EXECUTE FUNCTION agent.guard_runtime_state('step','side_effect_status');

CREATE OR REPLACE FUNCTION agent.configure_lease_clock() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE config agent.runtime_settings;
BEGIN
    SELECT * INTO config FROM agent.runtime_settings;
    IF TG_OP='INSERT' OR NEW.heartbeat_at IS DISTINCT FROM OLD.heartbeat_at THEN
        NEW.expires_at:=NEW.heartbeat_at+make_interval(secs=>config.lease_seconds);
    END IF;
    IF TG_OP='UPDATE' AND NEW.policy_snapshot IS DISTINCT FROM OLD.policy_snapshot THEN
        RAISE EXCEPTION 'lease policy snapshot is immutable';
    END IF;
    IF TG_OP='INSERT' THEN NEW.policy_snapshot:=agent.runtime_policy_snapshot(NEW.agent_id); END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER runtime_lease_clock BEFORE INSERT OR UPDATE ON agent.task_leases
FOR EACH ROW EXECUTE FUNCTION agent.configure_lease_clock();

-- Preserve the tested lease implementation as an internal compatibility adapter.
DO $$ BEGIN
 IF to_regprocedure('agent.claim_runtime_task_base(uuid,bigint,bigint,text,boolean)') IS NULL THEN
    ALTER FUNCTION agent.claim_runtime_task(uuid,bigint,bigint,text,boolean) RENAME TO claim_runtime_task_base;
 END IF;
 IF to_regprocedure('agent.heartbeat_runtime_lease_base(uuid,bigint,text,uuid,text)') IS NULL THEN
    ALTER FUNCTION agent.heartbeat_runtime_lease(uuid,bigint,text,uuid,text) RENAME TO heartbeat_runtime_lease_base;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION agent.claim_runtime_task(p_worker uuid,p_task bigint,p_agent bigint,p_token_hash text,p_committee_reclaim boolean DEFAULT false)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE policy agent.agent_workspaces; task agent.tasks; result jsonb; config agent.runtime_settings;
BEGIN
    SELECT * INTO config FROM agent.runtime_settings;
    IF config.claim_mode<>'enabled' THEN RETURN '{}'; END IF;
    PERFORM 1 FROM agent.workers WHERE id=p_worker FOR UPDATE;
    PERFORM 1 FROM agent.profiles WHERE id=p_agent FOR UPDATE;
    SELECT * INTO policy FROM agent.agent_workspaces WHERE agent_id=p_agent FOR SHARE;
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE SKIP LOCKED;
    IF NOT FOUND OR policy.agent_id IS NULL THEN RETURN '{}'; END IF;
    IF NOT(task.task_class=ANY(policy.allowed_task_classes)) OR NOT(task.runtime_scope=ANY(policy.allowed_scopes))
      OR NOT(task.data_class=ANY(policy.allowed_data_classes))
      OR (task.book_id IS NOT NULL AND NOT(task.book_id=ANY(policy.allowed_books)))
      OR (task.client_id IS NOT NULL AND NOT(task.client_id=ANY(policy.allowed_clients))) THEN RETURN '{}'; END IF;
    result:=agent.claim_runtime_task_base(p_worker,p_task,p_agent,p_token_hash,p_committee_reclaim);
    IF result='{}'::jsonb THEN RETURN result; END IF;
    RETURN result||jsonb_build_object('heartbeat_seconds',config.active_heartbeat_seconds,
        'policy_version',policy.role_version,'idle_heartbeat_seconds',config.idle_heartbeat_seconds);
END $$;
CREATE OR REPLACE FUNCTION agent.heartbeat_runtime_lease(p_worker uuid,p_lease bigint,p_token_hash text,p_request uuid,p_state text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb;
BEGIN
    result:=agent.heartbeat_runtime_lease_base(p_worker,p_lease,p_token_hash,p_request,p_state);
    RETURN result||jsonb_build_object('next_heartbeat_seconds',(SELECT active_heartbeat_seconds FROM agent.runtime_settings));
END $$;
REVOKE ALL ON FUNCTION agent.claim_runtime_task_base(uuid,bigint,bigint,text,boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION agent.heartbeat_runtime_lease_base(uuid,bigint,text,uuid,text) FROM PUBLIC;

CREATE OR REPLACE FUNCTION agent.idle_runtime_worker(p_worker uuid) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE worker agent.workers; config agent.runtime_settings;
BEGIN
    SELECT * INTO worker FROM agent.workers WHERE id=p_worker FOR UPDATE;
    IF NOT FOUND OR worker.status IN ('STOPPED','QUARANTINED') THEN RAISE EXCEPTION 'worker unavailable'; END IF;
    SELECT * INTO config FROM agent.runtime_settings;
    IF EXISTS(SELECT 1 FROM agent.task_leases WHERE worker_id=p_worker AND status='ACTIVE') THEN
        RAISE EXCEPTION 'active workers must heartbeat their owned lease'; END IF;
    UPDATE agent.workers SET last_heartbeat_at=clock_timestamp(),status=CASE
        WHEN shutdown_requested OR config.claim_mode<>'enabled' THEN 'STOPPED' ELSE 'IDLE' END WHERE id=p_worker;
    RETURN jsonb_build_object('worker_id',p_worker,'shutdown_requested',worker.shutdown_requested OR config.claim_mode<>'enabled',
        'next_heartbeat_seconds',config.idle_heartbeat_seconds,'broker_write_allowed',false);
END $$;

CREATE TABLE IF NOT EXISTS agent.runtime_output_receipts (
    id bigserial PRIMARY KEY, task_id bigint NOT NULL REFERENCES agent.tasks(id),
    lease_id bigint NOT NULL REFERENCES agent.task_leases(id), step_id bigint REFERENCES agent.task_steps(id),
    output_key text NOT NULL CHECK(length(output_key) BETWEEN 1 AND 200),
    artifact_ref text NOT NULL CHECK(length(artifact_ref) BETWEEN 1 AND 240),
    content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
    evidence_refs jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(evidence_refs)='array'),
    validated_by bigint REFERENCES agent.profiles(id), validated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(task_id,output_key)
);
CREATE OR REPLACE FUNCTION agent.record_runtime_receipt(p_worker uuid,p_lease bigint,p_token_hash text,
    p_step bigint,p_key text,p_ref text,p_hash text,p_evidence jsonb DEFAULT '[]') RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE lease agent.task_leases; receipt agent.runtime_output_receipts;
BEGIN
    lease:=agent.assert_runtime_lease(p_worker,p_lease,p_token_hash);
    IF p_step IS NOT NULL AND NOT EXISTS(SELECT 1 FROM agent.task_steps WHERE id=p_step AND lease_id=p_lease) THEN
        RAISE EXCEPTION 'receipt step ownership mismatch'; END IF;
    INSERT INTO agent.runtime_output_receipts(task_id,lease_id,step_id,output_key,artifact_ref,content_hash,evidence_refs)
    VALUES(lease.task_id,p_lease,p_step,p_key,p_ref,p_hash,p_evidence) ON CONFLICT(task_id,output_key) DO NOTHING;
    SELECT * INTO receipt FROM agent.runtime_output_receipts WHERE task_id=lease.task_id AND output_key=p_key;
    IF receipt.content_hash<>p_hash OR receipt.artifact_ref<>p_ref THEN RAISE EXCEPTION 'receipt identity conflict'; END IF;
    UPDATE agent.task_steps SET side_effect_status='recorded',receipt_ref='runtime_receipt:'||receipt.id,
        finished_at=clock_timestamp() WHERE id=p_step;
    PERFORM agent.append_runtime_event(lease.task_id,lease.agent_id,p_worker,p_lease,'artifact_recorded','WRITING');
    RETURN jsonb_build_object('receipt_id',receipt.id,'artifact_ref',receipt.artifact_ref,'content_hash',receipt.content_hash);
END $$;
CREATE OR REPLACE FUNCTION agent.reconcile_runtime_receipts(p_task bigint) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE task agent.tasks; receipt agent.runtime_output_receipts;
BEGIN
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND OR task.runtime_protocol<>'lease_v1' OR task.status<>'blocked'
      OR EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE') THEN
        RAISE EXCEPTION 'only a blocked released task can be reconciled'; END IF;
    SELECT * INTO receipt FROM agent.runtime_output_receipts WHERE task_id=p_task ORDER BY id DESC LIMIT 1;
    IF NOT FOUND OR EXISTS(SELECT 1 FROM agent.task_steps WHERE task_id=p_task AND side_effect_status IN ('started','uncertain')) THEN
        RAISE EXCEPTION 'unresolved side effect receipt'; END IF;
    PERFORM set_config('aios.runtime_task',p_task::text,true);
    UPDATE agent.tasks SET status='needs_review',runtime_state='WAITING_FOR_APPROVAL',
        output_note_path=receipt.artifact_ref,updated_at=clock_timestamp() WHERE id=p_task;
    PERFORM agent.append_runtime_event(p_task,task.agent_id,NULL,NULL,'receipt_reconciled','WAITING_FOR_APPROVAL');
    RETURN jsonb_build_object('task_id',p_task,'status','needs_review','receipt_id',receipt.id,'replayed_work',false);
END $$;

-- PG remains the only replay authority. Store typed references, not prompts or PII.
ALTER TABLE agent.task_events ADD COLUMN IF NOT EXISTS recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ADD COLUMN IF NOT EXISTS runtime_scope text NOT NULL DEFAULT 'internal',
    ADD COLUMN IF NOT EXISTS book_id bigint, ADD COLUMN IF NOT EXISTS client_id bigint,
    ADD COLUMN IF NOT EXISTS actor_type text NOT NULL DEFAULT 'runtime',
    ADD COLUMN IF NOT EXISTS actor_id text, ADD COLUMN IF NOT EXISTS step_id bigint,
    ADD COLUMN IF NOT EXISTS thread_key text, ADD COLUMN IF NOT EXISTS handoff_id bigint,
    ADD COLUMN IF NOT EXISTS committee_id bigint, ADD COLUMN IF NOT EXISTS approval_id bigint,
    ADD COLUMN IF NOT EXISTS research_case_id bigint, ADD COLUMN IF NOT EXISTS model_route text,
    ADD COLUMN IF NOT EXISTS model_call_id bigint, ADD COLUMN IF NOT EXISTS tool_call_id bigint,
    ADD COLUMN IF NOT EXISTS artifact_ids bigint[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS risk_class text NOT NULL DEFAULT 'internal_read';
CREATE TABLE IF NOT EXISTS agent.runtime_event_types (
    event_type text PRIMARY KEY, category text NOT NULL
);
INSERT INTO agent.runtime_event_types SELECT e,c FROM (VALUES
 ('task',ARRAY['task_claimed','state_changed','step_started','control_requested','lease_released','lease_expired','task_redirected','task_validated','artifact_recorded','receipt_reconciled']),
 ('message',ARRAY['thread_created','message_sent','message_read','message_acknowledged']),
 ('handoff',ARRAY['handoff_requested','handoff_acknowledged','handoff_accepted','handoff_rejected','handoff_in_progress','handoff_returned','handoff_validated','handoff_cancelled','handoff_failed']),
 ('committee',ARRAY['committee_opened','committee_invited','committee_position','committee_closed']),
 ('plan',ARRAY['plan_created','plan_updated','paid_work_stopped']),
 ('model',ARRAY['binding_tested','binding_promoted','binding_disabled','binding_rolled_back','model_call_started','model_call_completed','model_call_failed']),
 ('routine',ARRAY['routine_enabled','routine_paused','routine_started','routine_completed','routine_failed']),
 ('system',ARRAY['doctor_completed','safe_fix_completed','policy_denied','runtime_draining','event_checkpoint'])
) t(c,events) CROSS JOIN LATERAL unnest(events) e ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION agent.type_runtime_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE task agent.tasks;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM agent.runtime_event_types WHERE event_type=NEW.event_type) THEN
        RAISE EXCEPTION 'unknown runtime event type'; END IF;
    IF NEW.task_id IS NOT NULL THEN
        SELECT * INTO task FROM agent.tasks WHERE id=NEW.task_id;
        NEW.runtime_scope:=task.runtime_scope; NEW.book_id:=task.book_id; NEW.client_id:=task.client_id;
    END IF;
    IF NEW.reason_code IS NOT NULL AND NEW.reason_code !~ '^[a-zA-Z0-9_.-]{1,120}$' THEN
        RAISE EXCEPTION 'event reason must be a bounded code, not free text'; END IF;
    IF NEW.actor_type NOT IN ('runtime','worker','agent','operator','routine') OR
       NEW.risk_class NOT IN ('internal_read','internal_draft','approval_required') THEN RAISE EXCEPTION 'invalid event class'; END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER runtime_event_contract BEFORE INSERT ON agent.task_events
FOR EACH ROW EXECUTE FUNCTION agent.type_runtime_event();
CREATE INDEX IF NOT EXISTS idx_runtime_events_scope_cursor ON agent.task_events(runtime_scope,id);
CREATE TABLE IF NOT EXISTS agent.event_checkpoints (
    id bigserial PRIMARY KEY, runtime_scope text NOT NULL,
    through_event_id bigint NOT NULL, snapshot jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
COMMENT ON TABLE agent.event_checkpoints IS 'Compacted read projections; original events remain append-only. Deletion/retention requires a separate approved archive/restore procedure.';
CREATE OR REPLACE FUNCTION agent.checkpoint_runtime_events(p_scope text DEFAULT 'internal') RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE checkpoint_id bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(256,1);
    INSERT INTO agent.event_checkpoints(runtime_scope,through_event_id,snapshot)
    SELECT p_scope,coalesce((SELECT max(id) FROM agent.task_events),0),jsonb_build_object('tasks',
        coalesce(jsonb_agg(jsonb_build_object('id',id,'status',status,'state',runtime_state)),'[]'))
    FROM agent.tasks WHERE runtime_protocol='lease_v1' AND runtime_scope=p_scope AND client_id IS NULL AND book_id IS NULL
    RETURNING id INTO checkpoint_id;
    RETURN checkpoint_id;
END $$;
COMMIT;
