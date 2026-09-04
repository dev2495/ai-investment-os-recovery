-- Phase 2: extend canonical agent identities/tasks; never create a second queue.
-- No private data, provider calls, credentials, broker or market writes.
BEGIN;

ALTER TABLE agent.profiles
    ADD COLUMN IF NOT EXISTS agent_key text,
    ADD COLUMN IF NOT EXISTS role_version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS max_parallel_tasks integer NOT NULL DEFAULT 1;
UPDATE agent.profiles SET agent_key='agent_'||id WHERE agent_key IS NULL;
ALTER TABLE agent.profiles ALTER COLUMN agent_key SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_machine_key ON agent.profiles(agent_key);

CREATE OR REPLACE FUNCTION agent.ensure_machine_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND NEW.agent_key IS DISTINCT FROM OLD.agent_key THEN
        RAISE EXCEPTION 'agent machine identity is immutable';
    END IF;
    NEW.agent_key := coalesce(NEW.agent_key,'agent_'||NEW.id);
    IF NEW.role_version < 1 OR NEW.max_parallel_tasks NOT BETWEEN 1 AND 4 THEN
        RAISE EXCEPTION 'invalid role version or parallel task limit';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER agent_machine_identity
    BEFORE INSERT OR UPDATE ON agent.profiles FOR EACH ROW EXECUTE FUNCTION agent.ensure_machine_identity();

CREATE TABLE IF NOT EXISTS agent.workers (
    id uuid PRIMARY KEY,
    node_name text NOT NULL CHECK(length(node_name) BETWEEN 1 AND 120),
    process_id integer NOT NULL CHECK(process_id>0),
    runtime_version text NOT NULL CHECK(length(runtime_version) BETWEEN 1 AND 120),
    supported_task_classes text[] NOT NULL DEFAULT ARRAY['general'],
    max_parallel_tasks integer NOT NULL DEFAULT 1 CHECK(max_parallel_tasks BETWEEN 1 AND 4),
    status text NOT NULL DEFAULT 'IDLE' CHECK(status IN ('IDLE','RUNNING','STALE','STOPPED','QUARANTINED')),
    shutdown_requested boolean NOT NULL DEFAULT false,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE agent.tasks
    ADD COLUMN IF NOT EXISTS agent_id bigint REFERENCES agent.profiles(id),
    ADD COLUMN IF NOT EXISTS runtime_protocol text NOT NULL DEFAULT 'legacy' CHECK(runtime_protocol IN ('legacy','lease_v1')),
    ADD COLUMN IF NOT EXISTS runtime_state text,
    ADD COLUMN IF NOT EXISTS task_class text NOT NULL DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS recovery_policy text NOT NULL DEFAULT 'manual' CHECK(recovery_policy IN ('manual','idempotent_read')),
    ADD COLUMN IF NOT EXISTS recovery_limit integer NOT NULL DEFAULT 2 CHECK(recovery_limit BETWEEN 0 AND 5),
    ADD COLUMN IF NOT EXISTS control_requested text CHECK(control_requested IN ('pause','cancel')),
    ADD COLUMN IF NOT EXISTS runtime_scope text NOT NULL DEFAULT 'internal';
UPDATE agent.tasks task SET agent_id=profile.id FROM agent.profiles profile
    WHERE task.agent_id IS NULL AND profile.agent_name=task.owner_agent;
CREATE INDEX IF NOT EXISTS idx_runtime_tasks_agent ON agent.tasks(agent_id,status);

CREATE TABLE IF NOT EXISTS agent.task_leases (
    id bigserial PRIMARY KEY,
    task_id bigint NOT NULL REFERENCES agent.tasks(id),
    agent_id bigint NOT NULL REFERENCES agent.profiles(id),
    worker_id uuid NOT NULL REFERENCES agent.workers(id),
    token_hash text NOT NULL CHECK(token_hash ~ '^[0-9a-f]{64}$'),
    attempt integer NOT NULL CHECK(attempt>0),
    status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','RELEASED','EXPIRED')),
    claimed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    released_at timestamptz,
    recovery_reason text,
    UNIQUE(task_id,attempt)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_active_lease ON agent.task_leases(task_id) WHERE status='ACTIVE';
CREATE INDEX IF NOT EXISTS idx_worker_active_leases ON agent.task_leases(worker_id,status,expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_active_leases ON agent.task_leases(agent_id,status);

CREATE TABLE IF NOT EXISTS agent.task_steps (
    id bigserial PRIMARY KEY,
    task_id bigint NOT NULL REFERENCES agent.tasks(id),
    lease_id bigint NOT NULL REFERENCES agent.task_leases(id),
    step_key text NOT NULL CHECK(length(step_key) BETWEEN 1 AND 100),
    state text NOT NULL,
    side_effect_status text NOT NULL DEFAULT 'none' CHECK(side_effect_status IN ('none','started','recorded','uncertain')),
    receipt_ref text CHECK(length(receipt_ref)<=240),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    UNIQUE(task_id,lease_id,step_key)
);
CREATE TABLE IF NOT EXISTS agent.task_dependencies (
    task_id bigint NOT NULL REFERENCES agent.tasks(id),
    depends_on_task_id bigint NOT NULL REFERENCES agent.tasks(id),
    PRIMARY KEY(task_id,depends_on_task_id),
    CHECK(task_id<>depends_on_task_id)
);
CREATE TABLE IF NOT EXISTS agent.agent_presence (
    agent_id bigint PRIMARY KEY REFERENCES agent.profiles(id),
    worker_id uuid NOT NULL REFERENCES agent.workers(id),
    task_id bigint REFERENCES agent.tasks(id),
    state text NOT NULL,
    last_heartbeat_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS agent.task_events (
    id bigserial PRIMARY KEY,
    task_id bigint REFERENCES agent.tasks(id),
    agent_id bigint REFERENCES agent.profiles(id),
    worker_id uuid REFERENCES agent.workers(id),
    lease_id bigint REFERENCES agent.task_leases(id),
    event_type text NOT NULL,
    state text,
    reason_code text,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON agent.task_events(task_id,id);
CREATE TABLE IF NOT EXISTS agent.worker_heartbeats (
    worker_id uuid NOT NULL REFERENCES agent.workers(id),
    request_key uuid NOT NULL,
    lease_id bigint REFERENCES agent.task_leases(id),
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    response jsonb NOT NULL,
    PRIMARY KEY(worker_id,request_key)
);

CREATE OR REPLACE FUNCTION agent.append_runtime_event(
    p_task bigint,p_agent bigint,p_worker uuid,p_lease bigint,p_event text,p_state text,p_reason text DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE event_id bigint;
BEGIN
    -- Serialize allocation until commit, so a replay cursor cannot skip an earlier
    -- uncommitted event. Four bounded workers are the initial deployment target.
    PERFORM pg_advisory_xact_lock(256,1);
    INSERT INTO agent.task_events(task_id,agent_id,worker_id,lease_id,event_type,state,reason_code)
    VALUES(p_task,p_agent,p_worker,p_lease,p_event,p_state,p_reason) RETURNING id INTO event_id;
    RETURN event_id;
END $$;
CREATE OR REPLACE FUNCTION agent.reject_runtime_event_edit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'runtime events are append-only'; END $$;
CREATE OR REPLACE TRIGGER runtime_event_immutable BEFORE UPDATE OR DELETE ON agent.task_events
    FOR EACH ROW EXECUTE FUNCTION agent.reject_runtime_event_edit();

CREATE OR REPLACE FUNCTION agent.guard_managed_task_write() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE managed boolean;
BEGIN
    managed := OLD.runtime_protocol='lease_v1' OR NEW.runtime_protocol='lease_v1';
    IF managed AND (
        NEW.status IS DISTINCT FROM OLD.status OR NEW.agent_id IS DISTINCT FROM OLD.agent_id
        OR NEW.owner_agent IS DISTINCT FROM OLD.owner_agent OR NEW.runtime_state IS DISTINCT FROM OLD.runtime_state
        OR NEW.output_note_path IS DISTINCT FROM OLD.output_note_path OR NEW.evidence IS DISTINCT FROM OLD.evidence
        OR NEW.runtime_protocol IS DISTINCT FROM OLD.runtime_protocol
    ) AND coalesce(current_setting('aios.runtime_task',true),'')<>NEW.id::text THEN
        RAISE EXCEPTION 'managed task requires a fenced runtime operation';
    END IF;
    RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER managed_task_write BEFORE UPDATE ON agent.tasks
    FOR EACH ROW EXECUTE FUNCTION agent.guard_managed_task_write();

CREATE OR REPLACE FUNCTION agent.register_runtime_worker(
    p_id uuid,p_node text,p_pid integer,p_version text,p_parallel integer DEFAULT 1
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE worker agent.workers;
BEGIN
    INSERT INTO agent.workers(id,node_name,process_id,runtime_version,max_parallel_tasks)
    VALUES(p_id,p_node,p_pid,p_version,p_parallel) ON CONFLICT(id) DO NOTHING;
    SELECT * INTO worker FROM agent.workers WHERE id=p_id FOR UPDATE;
    IF worker.node_name<>p_node OR worker.process_id<>p_pid OR worker.runtime_version<>p_version
        OR worker.status IN ('STOPPED','QUARANTINED') THEN
        RAISE EXCEPTION 'worker identity cannot be reused by a different process';
    END IF;
    UPDATE agent.workers SET last_heartbeat_at=clock_timestamp(),status=CASE
        WHEN EXISTS(SELECT 1 FROM agent.task_leases WHERE worker_id=p_id AND status='ACTIVE') THEN 'RUNNING' ELSE 'IDLE' END
        WHERE id=p_id RETURNING * INTO worker;
    RETURN jsonb_build_object('worker_id',worker.id,'status',worker.status,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.claim_runtime_task(
    p_worker uuid,p_task bigint,p_agent bigint,p_token_hash text,p_committee_reclaim boolean DEFAULT false
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE worker agent.workers; profile agent.profiles; task agent.tasks; lease agent.task_leases;
BEGIN
    -- All lease operations use worker -> profile -> task -> lease lock order.
    SELECT * INTO worker FROM agent.workers WHERE id=p_worker FOR UPDATE;
    IF NOT FOUND OR worker.status IN ('STOPPED','QUARANTINED','STALE') OR worker.shutdown_requested
        OR worker.last_heartbeat_at<clock_timestamp()-interval '180 seconds' THEN RETURN '{}'::jsonb; END IF;
    SELECT * INTO profile FROM agent.profiles WHERE id=p_agent FOR UPDATE;
    IF NOT FOUND OR profile.status<>'active' THEN RETURN '{}'::jsonb; END IF;
    IF (SELECT count(*) FROM agent.task_leases WHERE worker_id=p_worker AND status='ACTIVE')>=worker.max_parallel_tasks
        OR (SELECT count(*) FROM agent.task_leases WHERE agent_id=p_agent AND status='ACTIVE')>=profile.max_parallel_tasks
        THEN RETURN '{}'::jsonb; END IF;
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE SKIP LOCKED;
    IF NOT FOUND THEN RETURN '{}'::jsonb; END IF;
    IF task.control_requested IS NOT NULL OR NOT(task.task_class=ANY(worker.supported_task_classes))
        OR (task.status<>'queued' AND NOT(p_committee_reclaim AND task.source_kind='committee_packet_position'
            AND task.status IN ('needs_review','blocked') AND task.runtime_protocol='legacy'))
        OR EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE')
        OR EXISTS(SELECT 1 FROM agent.task_dependencies dep JOIN agent.tasks parent ON parent.id=dep.depends_on_task_id
            WHERE dep.task_id=p_task AND parent.status<>'completed')
        OR (task.approval_required AND NOT EXISTS(SELECT 1 FROM agent.approvals WHERE task_id=p_task AND status='approved'))
        THEN RETURN '{}'::jsonb; END IF;
    -- Enrolment must not bypass the old dispatcher by routing arbitrary tasks.
    IF task.owner_agent<>profile.agent_name AND task.owner_agent<>'Jarvis' THEN RETURN '{}'::jsonb; END IF;
    PERFORM set_config('aios.runtime_task',p_task::text,true);
    UPDATE agent.tasks SET agent_id=p_agent,owner_agent=profile.agent_name,runtime_protocol='lease_v1',
        runtime_state='CLAIMING_TASK',status='in_progress',updated_at=clock_timestamp() WHERE id=p_task;
    INSERT INTO agent.task_leases(task_id,agent_id,worker_id,token_hash,attempt,expires_at)
    VALUES(p_task,p_agent,p_worker,p_token_hash,
        (SELECT coalesce(max(attempt),0)+1 FROM agent.task_leases WHERE task_id=p_task),
        clock_timestamp()+interval '45 seconds') RETURNING * INTO lease;
    UPDATE agent.workers SET status='RUNNING',last_heartbeat_at=clock_timestamp() WHERE id=p_worker;
    INSERT INTO agent.agent_presence(agent_id,worker_id,task_id,state) VALUES(p_agent,p_worker,p_task,'CLAIMING_TASK')
    ON CONFLICT(agent_id) DO UPDATE SET worker_id=excluded.worker_id,task_id=excluded.task_id,
        state=excluded.state,last_heartbeat_at=clock_timestamp();
    PERFORM agent.append_runtime_event(p_task,p_agent,p_worker,lease.id,'task_claimed','CLAIMING_TASK');
    RETURN jsonb_build_object('id',p_task,'task_id',p_task,'agent_id',p_agent,'worker_id',p_worker,
        'lease_id',lease.id,'attempt',lease.attempt,'state','CLAIMING_TASK','status','in_progress',
        'expires_at',lease.expires_at,'heartbeat_seconds',15,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.assert_runtime_lease(p_worker uuid,p_lease bigint,p_token_hash text)
RETURNS agent.task_leases LANGUAGE plpgsql AS $$
DECLARE lease agent.task_leases; owner_id bigint; task_id_value bigint; worker agent.workers;
BEGIN
    SELECT agent_id,task_id INTO owner_id,task_id_value FROM agent.task_leases WHERE id=p_lease AND worker_id=p_worker;
    IF NOT FOUND THEN RAISE EXCEPTION 'lease ownership lost'; END IF;
    SELECT * INTO worker FROM agent.workers WHERE id=p_worker FOR UPDATE;
    PERFORM 1 FROM agent.profiles WHERE id=owner_id FOR UPDATE;
    PERFORM 1 FROM agent.tasks WHERE id=task_id_value FOR UPDATE;
    SELECT * INTO lease FROM agent.task_leases WHERE id=p_lease FOR UPDATE;
    IF lease.status<>'ACTIVE' OR lease.token_hash IS DISTINCT FROM p_token_hash OR lease.expires_at<=clock_timestamp()
        OR worker.status IN ('STALE','STOPPED','QUARANTINED') THEN
        RAISE EXCEPTION 'lease ownership lost';
    END IF;
    PERFORM set_config('aios.runtime_task',lease.task_id::text,true);
    RETURN lease;
END $$;

CREATE OR REPLACE FUNCTION agent.runtime_active_state(p_state text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT p_state=ANY(ARRAY['PLANNING','ACQUIRING_SOURCE','READING','PARSING','EXTRACTING','CALCULATING',
        'ANALYZING','WRITING','CALLING_TOOL','WAITING_FOR_TOOL','HANDING_OFF','IN_GROUP_ROOM','IN_COMMITTEE',
        'SIMULATING','EXECUTING_ALLOWED_INTERNAL_ACTION','RECONCILING','VALIDATING','RETRYING'])
$$;

CREATE OR REPLACE FUNCTION agent.heartbeat_runtime_lease(
    p_worker uuid,p_lease bigint,p_token_hash text,p_request uuid,p_state text DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE lease agent.task_leases; prior agent.worker_heartbeats; result jsonb; state_value text; task agent.tasks;
BEGIN
    lease := agent.assert_runtime_lease(p_worker,p_lease,p_token_hash);
    SELECT * INTO prior FROM agent.worker_heartbeats WHERE worker_id=p_worker AND request_key=p_request;
    IF FOUND THEN
        IF prior.lease_id<>p_lease THEN RAISE EXCEPTION 'heartbeat request key belongs to another lease'; END IF;
        RETURN prior.response || jsonb_build_object('duplicate',true);
    END IF;
    SELECT * INTO task FROM agent.tasks WHERE id=lease.task_id;
    state_value := coalesce(p_state,task.runtime_state);
    IF p_state IS NOT NULL AND NOT agent.runtime_active_state(p_state) THEN
        RAISE EXCEPTION 'heartbeat cannot claim a terminal, blocked or unowned state';
    END IF;
    -- Rapid new IDs cannot produce unbounded persistence or extend ownership.
    IF EXISTS(SELECT 1 FROM agent.worker_heartbeats WHERE worker_id=p_worker
        AND accepted_at>clock_timestamp()-interval '1 second') THEN
            RETURN jsonb_build_object('accepted',false,'reason','heartbeat_rate_limited',
                'lease_id',lease.id,'state',task.runtime_state,'control_requested',task.control_requested,
                'shutdown_requested',(SELECT shutdown_requested FROM agent.workers WHERE id=p_worker),
                'expires_at',lease.expires_at,'next_heartbeat_seconds',15,'broker_write_allowed',false);
    END IF;
    UPDATE agent.task_leases SET heartbeat_at=clock_timestamp(),expires_at=clock_timestamp()+interval '45 seconds'
        WHERE id=lease.id RETURNING * INTO lease;
    UPDATE agent.workers SET last_heartbeat_at=clock_timestamp(),status='RUNNING' WHERE id=p_worker;
    UPDATE agent.tasks SET runtime_state=state_value,updated_at=clock_timestamp() WHERE id=lease.task_id;
    UPDATE agent.agent_presence SET state=state_value,last_heartbeat_at=clock_timestamp()
        WHERE agent_id=lease.agent_id AND task_id=lease.task_id;
    IF state_value IS DISTINCT FROM task.runtime_state THEN
        PERFORM agent.append_runtime_event(lease.task_id,lease.agent_id,p_worker,lease.id,'state_changed',state_value);
    END IF;
    result := jsonb_build_object('accepted',true,'server_time',clock_timestamp(),'lease_id',lease.id,
        'state',state_value,'expires_at',lease.expires_at,'control_requested',task.control_requested,
        'shutdown_requested',(SELECT shutdown_requested FROM agent.workers WHERE id=p_worker),
        'next_heartbeat_seconds',15,'broker_write_allowed',false);
    INSERT INTO agent.worker_heartbeats(worker_id,request_key,lease_id,response) VALUES(p_worker,p_request,p_lease,result);
    RETURN result;
END $$;

CREATE OR REPLACE FUNCTION agent.record_runtime_step(
    p_worker uuid,p_lease bigint,p_token_hash text,p_step text,p_state text,p_side_effect boolean DEFAULT false
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE lease agent.task_leases; step agent.task_steps;
BEGIN
    lease := agent.assert_runtime_lease(p_worker,p_lease,p_token_hash);
    IF NOT agent.runtime_active_state(p_state) THEN RAISE EXCEPTION 'invalid active step state'; END IF;
    IF EXISTS(SELECT 1 FROM agent.tasks WHERE id=lease.task_id AND control_requested IS NOT NULL) THEN
        RAISE EXCEPTION 'task control pending at safe boundary';
    END IF;
    INSERT INTO agent.task_steps(task_id,lease_id,step_key,state,side_effect_status)
    VALUES(lease.task_id,p_lease,p_step,p_state,CASE WHEN p_side_effect THEN 'started' ELSE 'none' END)
    ON CONFLICT(task_id,lease_id,step_key) DO NOTHING RETURNING * INTO step;
    IF step.id IS NULL THEN RAISE EXCEPTION 'step already started; inspect its receipt before replay'; END IF;
    UPDATE agent.tasks SET runtime_state=p_state,updated_at=clock_timestamp() WHERE id=lease.task_id;
    UPDATE agent.agent_presence SET state=p_state,last_heartbeat_at=clock_timestamp()
        WHERE agent_id=lease.agent_id AND task_id=lease.task_id;
    PERFORM agent.append_runtime_event(lease.task_id,lease.agent_id,p_worker,p_lease,'step_started',p_state);
    RETURN jsonb_build_object('step_id',step.id,'state',p_state,'side_effect_status',step.side_effect_status);
END $$;

CREATE OR REPLACE FUNCTION agent.finish_runtime_lease(
    p_worker uuid,p_lease bigint,p_token_hash text,p_outcome text,p_receipt text DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE lease agent.task_leases; state_value text; task_status text;
BEGIN
    lease := agent.assert_runtime_lease(p_worker,p_lease,p_token_hash);
    IF p_outcome NOT IN ('needs_review','blocked','failed','paused','cancelled') THEN
        RAISE EXCEPTION 'worker cannot self-validate completed research';
    END IF;
    IF p_outcome='needs_review' AND nullif(p_receipt,'') IS NULL THEN RAISE EXCEPTION 'output receipt required'; END IF;
    state_value := CASE p_outcome WHEN 'needs_review' THEN 'WAITING_FOR_APPROVAL' ELSE upper(p_outcome) END;
    task_status := p_outcome;
    -- Preserve the graph engine's completed status after its own existing receipt
    -- transaction. Runtime success is still not Research/committee acceptance.
    UPDATE agent.tasks SET status=CASE WHEN status='completed' AND p_outcome='needs_review' THEN status ELSE task_status END,
        runtime_state=state_value,updated_at=clock_timestamp() WHERE id=lease.task_id;
    IF p_receipt IS NOT NULL THEN
        UPDATE agent.task_steps SET side_effect_status=CASE WHEN side_effect_status='started' THEN 'recorded' ELSE side_effect_status END,
            receipt_ref=p_receipt,finished_at=clock_timestamp() WHERE lease_id=p_lease AND finished_at IS NULL;
    END IF;
    UPDATE agent.task_leases SET status='RELEASED',released_at=clock_timestamp(),recovery_reason=p_outcome WHERE id=p_lease;
    UPDATE agent.workers SET status=CASE WHEN EXISTS(SELECT 1 FROM agent.task_leases WHERE worker_id=p_worker AND status='ACTIVE')
        THEN 'RUNNING' ELSE 'IDLE' END,last_heartbeat_at=clock_timestamp() WHERE id=p_worker;
    UPDATE agent.agent_presence SET state=state_value,last_heartbeat_at=clock_timestamp() WHERE task_id=lease.task_id;
    PERFORM agent.append_runtime_event(lease.task_id,lease.agent_id,p_worker,p_lease,'lease_released',state_value,p_outcome);
    RETURN jsonb_build_object('task_id',lease.task_id,'state',state_value,'lease_status','RELEASED','broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.request_runtime_control(p_task bigint,p_action text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE task agent.tasks;
BEGIN
    IF p_action NOT IN ('pause','cancel','resume') THEN RAISE EXCEPTION 'unsupported task control'; END IF;
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND OR task.runtime_protocol<>'lease_v1' THEN RAISE EXCEPTION 'task is not managed by lease runtime'; END IF;
    PERFORM set_config('aios.runtime_task',p_task::text,true);
    IF p_action='resume' THEN
        IF task.status<>'paused' OR EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE') THEN
            RAISE EXCEPTION 'only a safely paused task can resume';
        END IF;
        IF EXISTS(SELECT 1 FROM agent.task_steps WHERE task_id=p_task AND side_effect_status<>'none') THEN
            RAISE EXCEPTION 'task has side effects; reconcile receipts before resuming';
        END IF;
        UPDATE agent.tasks SET control_requested=NULL,status='queued',runtime_state='RETRYING',updated_at=clock_timestamp() WHERE id=p_task;
    ELSE
        IF task.status NOT IN ('queued','in_progress','paused') THEN RAISE EXCEPTION 'task is not controllable'; END IF;
        UPDATE agent.tasks SET control_requested=p_action,updated_at=clock_timestamp() WHERE id=p_task;
        IF NOT EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE') THEN
            UPDATE agent.tasks SET status=CASE p_action WHEN 'pause' THEN 'paused' ELSE 'cancelled' END,
                runtime_state=CASE p_action WHEN 'pause' THEN 'PAUSED' ELSE 'CANCELLED' END WHERE id=p_task;
        END IF;
    END IF;
    PERFORM agent.append_runtime_event(p_task,task.agent_id,NULL,NULL,'control_requested',task.runtime_state,p_action);
    RETURN jsonb_build_object('task_id',p_task,'action',p_action,'applies_at','next_safe_boundary','broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.reap_runtime_leases(p_limit integer DEFAULT 20)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE candidate record; lease agent.task_leases; task agent.tasks; state_value text; reason text;
    expired_count integer:=0; requeued_count integer:=0; blocked_count integer:=0;
BEGIN
    FOR candidate IN SELECT id,worker_id,agent_id,task_id FROM agent.task_leases
        WHERE status='ACTIVE' AND expires_at<=clock_timestamp() ORDER BY expires_at,id LIMIT greatest(1,least(p_limit,100)) LOOP
        PERFORM 1 FROM agent.workers WHERE id=candidate.worker_id FOR UPDATE SKIP LOCKED;
        IF NOT FOUND THEN CONTINUE; END IF;
        PERFORM 1 FROM agent.profiles WHERE id=candidate.agent_id FOR UPDATE SKIP LOCKED;
        IF NOT FOUND THEN CONTINUE; END IF;
        SELECT * INTO task FROM agent.tasks WHERE id=candidate.task_id FOR UPDATE SKIP LOCKED;
        IF NOT FOUND THEN CONTINUE; END IF;
        SELECT * INTO lease FROM agent.task_leases WHERE id=candidate.id AND status='ACTIVE'
            AND expires_at<=clock_timestamp() FOR UPDATE SKIP LOCKED;
        IF NOT FOUND THEN CONTINUE; END IF;
        PERFORM set_config('aios.runtime_task',task.id::text,true);
        IF task.status IN ('completed','needs_review') AND task.output_note_path IS NOT NULL THEN
            state_value:='WAITING_FOR_APPROVAL'; reason:='output_persisted_before_worker_loss';
        ELSIF task.control_requested IS NOT NULL THEN
            state_value:=CASE task.control_requested WHEN 'pause' THEN 'PAUSED' ELSE 'CANCELLED' END;
            reason:='control_applied_after_worker_loss';
        ELSIF task.recovery_policy='idempotent_read' AND lease.attempt<=task.recovery_limit
            AND task.output_note_path IS NULL
            AND NOT EXISTS(SELECT 1 FROM agent.task_steps WHERE task_id=task.id AND side_effect_status<>'none') THEN
            state_value:='RETRYING'; reason:='expired_idempotent_read'; requeued_count:=requeued_count+1;
        ELSE
            state_value:='BLOCKED'; reason:='receipt_reconciliation_required'; blocked_count:=blocked_count+1;
        END IF;
        UPDATE agent.task_leases SET status='EXPIRED',released_at=clock_timestamp(),recovery_reason=reason WHERE id=lease.id;
        UPDATE agent.tasks SET runtime_state=state_value,status=CASE state_value
            WHEN 'RETRYING' THEN 'queued' WHEN 'WAITING_FOR_APPROVAL' THEN task.status
            WHEN 'PAUSED' THEN 'paused' WHEN 'CANCELLED' THEN 'cancelled' ELSE 'blocked' END,
            updated_at=clock_timestamp() WHERE id=task.id;
        UPDATE agent.agent_presence SET state=state_value,last_heartbeat_at=clock_timestamp() WHERE task_id=task.id;
        UPDATE agent.workers SET status='STALE' WHERE id=lease.worker_id AND last_heartbeat_at<=clock_timestamp()-interval '45 seconds';
        PERFORM agent.append_runtime_event(task.id,lease.agent_id,lease.worker_id,lease.id,'lease_expired',state_value,reason);
        expired_count:=expired_count+1;
    END LOOP;
    RETURN jsonb_build_object('expired',expired_count,'requeued',requeued_count,'blocked',blocked_count,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE VIEW agent.v_runtime_presence AS
SELECT profile.id agent_id,profile.agent_key,profile.agent_name,profile.department,profile.display_title,
    profile.role_version,profile.max_parallel_tasks,
    CASE WHEN live.id IS NOT NULL AND live.expires_at>clock_timestamp() AND worker.status='RUNNING' THEN task.runtime_state
        WHEN live.id IS NOT NULL THEN 'STALE'
        WHEN presence.state IN ('BLOCKED','WAITING_FOR_APPROVAL','FAILED','PAUSED','CANCELLED') THEN presence.state
        WHEN worker.last_heartbeat_at>clock_timestamp()-interval '180 seconds' AND worker.status='IDLE' THEN 'IDLE'
        ELSE 'OFFLINE' END state,
    (live.id IS NOT NULL AND live.expires_at>clock_timestamp() AND worker.status='RUNNING') has_live_lease,
    live.id lease_id,live.task_id,live.worker_id,live.expires_at,worker.last_heartbeat_at,
    coalesce(active.lease_count,0)::integer active_lease_count,
    task.control_requested,false broker_write_allowed
FROM agent.profiles profile
LEFT JOIN agent.agent_presence presence ON presence.agent_id=profile.id
LEFT JOIN LATERAL(SELECT * FROM agent.task_leases WHERE agent_id=profile.id AND status='ACTIVE' ORDER BY id DESC LIMIT 1) live ON true
LEFT JOIN agent.workers worker ON worker.id=coalesce(live.worker_id,presence.worker_id)
LEFT JOIN agent.tasks task ON task.id=live.task_id
LEFT JOIN LATERAL(SELECT count(*) lease_count FROM agent.task_leases WHERE agent_id=profile.id AND status='ACTIVE') active ON true;

COMMENT ON TABLE agent.task_leases IS 'Fenced ownership of canonical agent.tasks. Tokens are hashes. Expiry never authorizes replay of unreceipted writes or paid calls.';
COMMENT ON VIEW agent.v_runtime_presence IS 'Shared-safe metadata only. A configured profile or old task status is never proof of an active worker.';
COMMIT;
