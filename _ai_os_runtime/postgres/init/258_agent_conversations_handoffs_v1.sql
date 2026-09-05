-- Conversations extend canonical messages/mailboxes/committees; tasks remain in
-- agent.tasks. Rooms do not grant access or investment decision authority.
BEGIN;
CREATE TABLE IF NOT EXISTS agent.conversation_threads (
    thread_key text PRIMARY KEY CHECK(length(thread_key) BETWEEN 8 AND 120),
    room_type text NOT NULL CHECK(room_type IN ('direct','department','case','strategy','client','committee','incident','approval')),
    title text NOT NULL CHECK(length(title) BETWEEN 1 AND 240),
    runtime_scope text NOT NULL DEFAULT 'internal', book_id bigint, client_id bigint,
    data_class text NOT NULL DEFAULT 'internal' CHECK(data_class IN ('public','internal','house_confidential','client_private')),
    context jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(context)='object'),
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    retention_days integer NOT NULL DEFAULT 365 CHECK(retention_days BETWEEN 30 AND 3650),
    archived_at timestamptz
);
ALTER TABLE agent.mailboxes ADD COLUMN IF NOT EXISTS agent_id bigint REFERENCES agent.profiles(id);
UPDATE agent.mailboxes m SET agent_id=p.id FROM agent.profiles p WHERE m.agent_id IS NULL AND m.agent_name=p.agent_name;
ALTER TABLE agent.agent_messages ADD COLUMN IF NOT EXISTS conversation_key text REFERENCES agent.conversation_threads(thread_key),
    ADD COLUMN IF NOT EXISTS from_agent_id bigint REFERENCES agent.profiles(id),
    ADD COLUMN IF NOT EXISTS to_agent_id bigint REFERENCES agent.profiles(id),
    ADD COLUMN IF NOT EXISTS sender_user_id text,
    ADD COLUMN IF NOT EXISTS idempotency_key text,
    ADD COLUMN IF NOT EXISTS attachments jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS mentions bigint[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS runtime_scope text NOT NULL DEFAULT 'internal',
    ADD COLUMN IF NOT EXISTS book_id bigint, ADD COLUMN IF NOT EXISTS client_id bigint;
ALTER TABLE agent.agent_messages ADD COLUMN IF NOT EXISTS processing_status text NOT NULL DEFAULT 'pending';
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_message_request ON agent.agent_messages(conversation_key,idempotency_key)
WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_message_cursor ON agent.agent_messages(conversation_key,id);
CREATE TABLE IF NOT EXISTS agent.message_receipts (
    message_id bigint NOT NULL REFERENCES agent.agent_messages(id), reader_key text NOT NULL,
    read_at timestamptz NOT NULL DEFAULT clock_timestamp(), acknowledged_at timestamptz,
    PRIMARY KEY(message_id,reader_key)
);
CREATE TABLE IF NOT EXISTS agent.thread_cursors (
    thread_key text NOT NULL REFERENCES agent.conversation_threads(thread_key), reader_key text NOT NULL,
    last_read_id bigint NOT NULL DEFAULT 0, last_ack_id bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(thread_key,reader_key)
);
CREATE TABLE IF NOT EXISTS agent.task_handoffs (
    id bigserial PRIMARY KEY, request_key text NOT NULL UNIQUE,
    thread_key text NOT NULL REFERENCES agent.conversation_threads(thread_key),
    from_agent_id bigint NOT NULL REFERENCES agent.profiles(id), to_agent_id bigint NOT NULL REFERENCES agent.profiles(id),
    parent_task_id bigint NOT NULL REFERENCES agent.tasks(id), child_task_id bigint NOT NULL UNIQUE REFERENCES agent.tasks(id),
    question text NOT NULL, expected_output_schema jsonb NOT NULL DEFAULT '{"type":"object","required":["summary","evidence_refs","missing_data"]}',
    evidence_refs jsonb NOT NULL DEFAULT '[]', receipt_id bigint REFERENCES agent.runtime_output_receipts(id),
    state text NOT NULL DEFAULT 'REQUESTED' CHECK(state IN ('REQUESTED','ACKNOWLEDGED','ACCEPTED','REJECTED','IN_PROGRESS','RETURNED','VALIDATED','CANCELLED','FAILED')),
    runtime_scope text NOT NULL DEFAULT 'internal', book_id bigint, client_id bigint,
    due_at timestamptz, acknowledged_at timestamptz, accepted_at timestamptz, returned_at timestamptz,
    validated_at timestamptz, validated_by bigint REFERENCES agent.profiles(id),
    validation_note text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK(from_agent_id<>to_agent_id)
);
INSERT INTO agent.runtime_state_edges SELECT 'handoff',a,b FROM (VALUES
 ('REQUESTED',ARRAY['ACKNOWLEDGED','REJECTED','CANCELLED']),
 ('ACKNOWLEDGED',ARRAY['ACCEPTED','REJECTED','CANCELLED']),
 ('ACCEPTED',ARRAY['IN_PROGRESS','FAILED','CANCELLED']),
 ('IN_PROGRESS',ARRAY['RETURNED','FAILED','CANCELLED']),
 ('RETURNED',ARRAY['VALIDATED','FAILED','CANCELLED'])) t(a,states)
CROSS JOIN LATERAL unnest(states) b ON CONFLICT DO NOTHING;
INSERT INTO agent.runtime_state_edges VALUES('task','handoff_pending','queued'),('task','handoff_pending','cancelled') ON CONFLICT DO NOTHING;
CREATE OR REPLACE TRIGGER runtime_handoff_state BEFORE UPDATE ON agent.task_handoffs FOR EACH ROW
EXECUTE FUNCTION agent.guard_runtime_state('handoff','state');
ALTER TABLE agent.committee_packets ADD COLUMN IF NOT EXISTS conversation_key text REFERENCES agent.conversation_threads(thread_key),
    ADD COLUMN IF NOT EXISTS runtime_scope text NOT NULL DEFAULT 'internal',
    ADD COLUMN IF NOT EXISTS book_id bigint, ADD COLUMN IF NOT EXISTS client_id bigint;

CREATE OR REPLACE FUNCTION agent.configure_runtime_worker(p_worker uuid,p_classes text[],p_tools text[] DEFAULT '{}')
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE worker agent.workers;
BEGIN
    SELECT * INTO worker FROM agent.workers WHERE id=p_worker FOR UPDATE;
    IF NOT FOUND OR worker.status IN ('STOPPED','QUARANTINED') THEN RAISE EXCEPTION 'worker unavailable'; END IF;
    IF EXISTS(SELECT 1 FROM agent.task_leases WHERE worker_id=p_worker AND status='ACTIVE') THEN
        RAISE EXCEPTION 'worker capabilities are immutable while work is leased'; END IF;
    IF coalesce(array_length(p_classes,1),0)=0 OR cardinality(p_classes)>30 OR cardinality(p_tools)>100
      OR EXISTS(SELECT 1 FROM unnest(p_classes) value WHERE value !~ '^[a-zA-Z0-9_]{1,80}$')
      OR EXISTS(SELECT 1 FROM unnest(p_tools) value WHERE length(value) NOT BETWEEN 1 AND 100)
      OR EXISTS(SELECT 1 FROM unnest(p_tools) value WHERE value ~* '^(broker|credential)\\.') THEN
        RAISE EXCEPTION 'invalid or denied worker capability'; END IF;
    UPDATE agent.workers SET supported_task_classes=p_classes,supported_tools=coalesce(p_tools,'{}'),
        last_heartbeat_at=clock_timestamp() WHERE id=p_worker;
    RETURN jsonb_build_object('worker_id',p_worker,'supported_task_classes',p_classes,
        'supported_tools',coalesce(p_tools,'{}'),'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.append_scoped_runtime_event(
    p_event text,p_state text DEFAULT NULL,p_task bigint DEFAULT NULL,p_agent bigint DEFAULT NULL,
    p_actor_type text DEFAULT 'runtime',p_actor_id text DEFAULT NULL,p_reason text DEFAULT NULL,
    p_thread text DEFAULT NULL,p_handoff bigint DEFAULT NULL,p_committee bigint DEFAULT NULL,
    p_approval bigint DEFAULT NULL,p_research_case bigint DEFAULT NULL,p_model_route text DEFAULT NULL,
    p_model_call bigint DEFAULT NULL,p_tool_call bigint DEFAULT NULL,p_artifact_ids bigint[] DEFAULT '{}',
    p_risk_class text DEFAULT 'internal_read') RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE event_id bigint; scope_value text:='internal'; book_value bigint; client_value bigint;
BEGIN
    PERFORM pg_advisory_xact_lock(256,1);
    IF p_task IS NOT NULL THEN
        SELECT runtime_scope,book_id,client_id INTO scope_value,book_value,client_value
        FROM agent.tasks WHERE id=p_task;
        IF NOT FOUND THEN RAISE EXCEPTION 'event task not found'; END IF;
    ELSIF p_thread IS NOT NULL THEN
        SELECT runtime_scope,book_id,client_id INTO scope_value,book_value,client_value
        FROM agent.conversation_threads WHERE thread_key=p_thread;
        IF NOT FOUND THEN RAISE EXCEPTION 'event thread not found'; END IF;
    END IF;
    INSERT INTO agent.task_events(task_id,agent_id,event_type,state,reason_code,runtime_scope,book_id,client_id,
        actor_type,actor_id,thread_key,handoff_id,committee_id,approval_id,research_case_id,model_route,
        model_call_id,tool_call_id,artifact_ids,risk_class)
    VALUES(p_task,p_agent,p_event,p_state,p_reason,scope_value,book_value,client_value,p_actor_type,p_actor_id,
        p_thread,p_handoff,p_committee,p_approval,p_research_case,p_model_route,p_model_call,p_tool_call,
        coalesce(p_artifact_ids,'{}'),p_risk_class) RETURNING id INTO event_id;
    RETURN event_id;
END $$;

CREATE OR REPLACE FUNCTION agent.create_task_handoff(
    p_request text,p_thread text,p_from bigint,p_to bigint,p_parent bigint,p_question text,
    p_schema jsonb DEFAULT '{"type":"object","required":["summary","evidence_refs","missing_data"]}',
    p_evidence jsonb DEFAULT '[]') RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE existing agent.task_handoffs; parent agent.tasks; child_id bigint; handoff_id bigint;
    sender_name text; recipient_name text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_request));
    SELECT * INTO existing FROM agent.task_handoffs WHERE request_key=p_request;
    IF FOUND THEN
        IF existing.thread_key<>p_thread OR existing.from_agent_id<>p_from OR existing.to_agent_id<>p_to
          OR existing.parent_task_id<>p_parent OR existing.question<>p_question THEN
            RAISE EXCEPTION 'handoff idempotency conflict';
        END IF;
        RETURN jsonb_build_object('handoff_id',existing.id,'child_task_id',existing.child_task_id,
            'parent_task_id',existing.parent_task_id,'state',existing.state,'duplicate',true);
    END IF;
    SELECT * INTO parent FROM agent.tasks WHERE id=p_parent FOR UPDATE;
    IF NOT FOUND OR parent.runtime_protocol<>'lease_v1' OR parent.status IN ('completed','cancelled','failed') THEN
        RAISE EXCEPTION 'active managed parent task required'; END IF;
    SELECT agent_name INTO sender_name FROM agent.profiles WHERE id=p_from AND status='active';
    SELECT agent_name INTO recipient_name FROM agent.profiles WHERE id=p_to AND status='active';
    IF sender_name IS NULL OR recipient_name IS NULL OR p_from=p_to THEN RAISE EXCEPTION 'valid distinct active agents required'; END IF;
    IF NOT EXISTS(SELECT 1 FROM agent.conversation_threads WHERE thread_key=p_thread
        AND runtime_scope=parent.runtime_scope AND book_id IS NOT DISTINCT FROM parent.book_id
        AND client_id IS NOT DISTINCT FROM parent.client_id) THEN RAISE EXCEPTION 'handoff thread scope mismatch'; END IF;
    INSERT INTO agent.tasks(title,objective,owner_agent,status,priority,source_kind,source_ref,agent_id,
        runtime_protocol,runtime_state,task_class,runtime_scope,recovery_policy,book_id,client_id,data_class,runtime_context)
    VALUES('Handoff: '||left(p_question,160),p_question,recipient_name,'handoff_pending',parent.priority,
        'agent_handoff',p_request,p_to,'lease_v1','HANDING_OFF','handoff',parent.runtime_scope,
        'idempotent_read',parent.book_id,parent.client_id,parent.data_class,
        jsonb_build_object('parent_task_id',p_parent,'requested_by_agent_id',p_from)) RETURNING id INTO child_id;
    INSERT INTO agent.task_handoffs(request_key,thread_key,from_agent_id,to_agent_id,parent_task_id,child_task_id,
        question,expected_output_schema,evidence_refs,runtime_scope,book_id,client_id)
    VALUES(p_request,p_thread,p_from,p_to,p_parent,child_id,p_question,p_schema,p_evidence,
        parent.runtime_scope,parent.book_id,parent.client_id) RETURNING id INTO handoff_id;
    PERFORM agent.append_scoped_runtime_event('handoff_requested','HANDING_OFF',child_id,p_from,'agent',
        p_from::text,NULL,p_thread,handoff_id);
    RETURN jsonb_build_object('handoff_id',handoff_id,'child_task_id',child_id,'parent_task_id',p_parent,
        'state','REQUESTED','duplicate',false,'research_readiness_changed',false,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.runtime_message_receipt(p_message bigint,p_reader text,p_ack boolean DEFAULT false)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE message agent.agent_messages; receipt agent.message_receipts;
BEGIN
    SELECT * INTO message FROM agent.agent_messages WHERE id=p_message FOR SHARE;
    IF NOT FOUND OR message.conversation_key IS NULL THEN RAISE EXCEPTION 'managed message not found'; END IF;
    INSERT INTO agent.message_receipts(message_id,reader_key,acknowledged_at)
    VALUES(p_message,p_reader,CASE WHEN p_ack THEN clock_timestamp() ELSE NULL END)
    ON CONFLICT(message_id,reader_key) DO UPDATE SET acknowledged_at=coalesce(agent.message_receipts.acknowledged_at,excluded.acknowledged_at)
    RETURNING * INTO receipt;
    INSERT INTO agent.thread_cursors(thread_key,reader_key,last_read_id,last_ack_id)
    VALUES(message.conversation_key,p_reader,p_message,CASE WHEN p_ack THEN p_message ELSE 0 END)
    ON CONFLICT(thread_key,reader_key) DO UPDATE SET
        last_read_id=greatest(agent.thread_cursors.last_read_id,excluded.last_read_id),
        last_ack_id=greatest(agent.thread_cursors.last_ack_id,excluded.last_ack_id),updated_at=clock_timestamp();
    RETURN jsonb_build_object('message_id',p_message,'read_at',receipt.read_at,'acknowledged_at',receipt.acknowledged_at);
END $$;

CREATE OR REPLACE FUNCTION agent.advance_task_handoff(p_id bigint,p_action text,p_actor bigint,p_receipt bigint DEFAULT NULL,p_note text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE handoff agent.task_handoffs; state_value text; task agent.tasks; receipt agent.runtime_output_receipts;
BEGIN
    SELECT * INTO handoff FROM agent.task_handoffs WHERE id=p_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'handoff not found'; END IF;
    state_value:=CASE p_action WHEN 'acknowledge' THEN 'ACKNOWLEDGED' WHEN 'accept' THEN 'ACCEPTED'
        WHEN 'reject' THEN 'REJECTED' WHEN 'start' THEN 'IN_PROGRESS' WHEN 'return' THEN 'RETURNED'
        WHEN 'validate' THEN 'VALIDATED' WHEN 'cancel' THEN 'CANCELLED' WHEN 'fail' THEN 'FAILED' END;
    IF state_value IS NULL THEN RAISE EXCEPTION 'unsupported handoff action'; END IF;
    IF p_action IN ('acknowledge','accept','reject','start','return','fail') AND p_actor<>handoff.to_agent_id THEN
        RAISE EXCEPTION 'handoff recipient must acknowledge and own the work'; END IF;
    IF p_action='cancel' AND p_actor NOT IN (handoff.from_agent_id,handoff.to_agent_id) THEN RAISE EXCEPTION 'handoff actor denied'; END IF;
    IF p_action='validate' AND (p_actor=handoff.to_agent_id OR NOT EXISTS(
      SELECT 1 FROM agent.profiles p LEFT JOIN agent.agent_workspaces w ON w.agent_id=handoff.from_agent_id
      WHERE p.id=p_actor AND p.status='active' AND (p_actor=handoff.from_agent_id OR p_actor=w.owner_agent_id))) THEN
        RAISE EXCEPTION 'independent sender or director validation required'; END IF;
    IF handoff.state=state_value THEN RETURN jsonb_build_object('handoff_id',p_id,'state',state_value,'duplicate',true); END IF;
    IF NOT agent.runtime_transition_allowed('handoff',handoff.state,state_value) THEN RAISE EXCEPTION 'illegal handoff transition'; END IF;
    SELECT * INTO task FROM agent.tasks WHERE id=handoff.child_task_id FOR UPDATE;
    PERFORM set_config('aios.runtime_task',task.id::text,true);
    IF p_action='accept' THEN
        IF EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=task.id AND status='ACTIVE') THEN RAISE EXCEPTION 'child already leased'; END IF;
        UPDATE agent.tasks SET owner_agent=(SELECT agent_name FROM agent.profiles WHERE id=handoff.to_agent_id),
            agent_id=handoff.to_agent_id,status='queued',runtime_state='WAITING_FOR_INPUT',updated_at=clock_timestamp() WHERE id=task.id;
        INSERT INTO agent.task_dependencies(task_id,depends_on_task_id) VALUES(handoff.parent_task_id,task.id) ON CONFLICT DO NOTHING;
    ELSIF p_action='start' THEN
        IF NOT EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=task.id AND agent_id=handoff.to_agent_id
          AND status='ACTIVE' AND expires_at>clock_timestamp()) THEN RAISE EXCEPTION 'work requires a live child lease'; END IF;
    ELSIF p_action IN ('return','validate') THEN
        SELECT * INTO receipt FROM agent.runtime_output_receipts WHERE id=coalesce(p_receipt,handoff.receipt_id) AND task_id=task.id;
        IF NOT FOUND OR jsonb_array_length(receipt.evidence_refs)=0 THEN RAISE EXCEPTION 'cited output receipt required'; END IF;
        IF task.status<>'needs_review' OR EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=task.id AND status='ACTIVE') THEN
            RAISE EXCEPTION 'return requires finished work awaiting review'; END IF;
        IF p_action='validate' THEN
            IF nullif(p_note,'') IS NULL THEN RAISE EXCEPTION 'validation rationale required'; END IF;
            UPDATE agent.runtime_output_receipts SET validated_by=p_actor,validated_at=clock_timestamp() WHERE id=receipt.id;
            UPDATE agent.tasks SET status='completed',runtime_state='COMPLETED',updated_at=clock_timestamp() WHERE id=task.id;
            UPDATE agent.agent_presence SET state='COMPLETED' WHERE task_id=task.id;
        END IF;
    ELSIF p_action IN ('reject','cancel','fail') THEN
        IF task.status='handoff_pending' THEN
            UPDATE agent.tasks SET status='cancelled',runtime_state='CANCELLED' WHERE id=task.id;
        ELSIF task.status IN ('queued','in_progress','paused') THEN
            PERFORM agent.request_runtime_control(task.id,'cancel');
        END IF;
    END IF;
    UPDATE agent.task_handoffs SET state=state_value,updated_at=clock_timestamp(),
        acknowledged_at=CASE WHEN p_action='acknowledge' THEN clock_timestamp() ELSE acknowledged_at END,
        accepted_at=CASE WHEN p_action='accept' THEN clock_timestamp() ELSE accepted_at END,
        returned_at=CASE WHEN p_action='return' THEN clock_timestamp() ELSE returned_at END,
        receipt_id=coalesce(receipt.id,receipt_id),
        validated_at=CASE WHEN p_action='validate' THEN clock_timestamp() ELSE validated_at END,
        validated_by=CASE WHEN p_action='validate' THEN p_actor ELSE validated_by END,
        validation_note=CASE WHEN p_action='validate' THEN p_note ELSE validation_note END WHERE id=p_id;
    PERFORM agent.append_scoped_runtime_event('handoff_'||lower(state_value),
        CASE WHEN state_value='VALIDATED' THEN 'COMPLETED' ELSE 'HANDING_OFF' END,
        task.id,p_actor,'agent',p_actor::text,NULL,handoff.thread_key,p_id);
    RETURN jsonb_build_object('handoff_id',p_id,'child_task_id',task.id,'parent_task_id',handoff.parent_task_id,
        'state',state_value,'research_readiness_changed',false,'broker_write_allowed',false);
END $$;
COMMIT;
