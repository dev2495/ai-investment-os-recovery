-- Durable Charlie objectives/plans extend agent.tasks; no second task queue,
-- model call, research acceptance, approval or broker authority is created.
BEGIN;

CREATE TABLE IF NOT EXISTS agent.objectives (
    id bigserial PRIMARY KEY, objective_key text NOT NULL UNIQUE,
    understood_objective text NOT NULL, context jsonb NOT NULL DEFAULT '{}',
    affected_entities jsonb NOT NULL DEFAULT '[]', runtime_scope text NOT NULL DEFAULT 'internal',
    book_id bigint, client_id bigint, data_class text NOT NULL DEFAULT 'internal',
    created_by text NOT NULL, status text NOT NULL DEFAULT 'PLANNING'
        CHECK(status IN ('PLANNING','ACTIVE','WAITING_FOR_INPUT','WAITING_FOR_APPROVAL','COMPLETED','CANCELLED','BLOCKED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS agent.plans (
    id bigserial PRIMARY KEY, objective_id bigint NOT NULL REFERENCES agent.objectives(id), version integer NOT NULL DEFAULT 1,
    policy_classification text NOT NULL, approval_class text NOT NULL DEFAULT 'internal_draft',
    budget jsonb NOT NULL DEFAULT '{}', sources jsonb NOT NULL DEFAULT '[]', calculations jsonb NOT NULL DEFAULT '[]',
    uncertainty jsonb NOT NULL DEFAULT '[]', missing_data jsonb NOT NULL DEFAULT '[]', next_action text,
    status text NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','ACTIVE','PAUSED','WAITING_FOR_INPUT','WAITING_FOR_APPROVAL','VALIDATED','CANCELLED','BLOCKED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(objective_id,version)
);
CREATE TABLE IF NOT EXISTS agent.plan_tasks (
    plan_id bigint NOT NULL REFERENCES agent.plans(id), task_id bigint NOT NULL UNIQUE REFERENCES agent.tasks(id),
    sequence_no integer NOT NULL CHECK(sequence_no>0), assignment_reason text NOT NULL,
    PRIMARY KEY(plan_id,task_id), UNIQUE(plan_id,sequence_no)
);
CREATE TABLE IF NOT EXISTS agent.charlie_commands (
    id bigserial PRIMARY KEY, request_key text NOT NULL UNIQUE, raw_command text NOT NULL, intent text NOT NULL,
    objective_id bigint REFERENCES agent.objectives(id), plan_id bigint REFERENCES agent.plans(id),
    runtime_scope text NOT NULL DEFAULT 'internal', book_id bigint, client_id bigint,
    actor_user_id text NOT NULL, status text NOT NULL DEFAULT 'RECORDED'
        CHECK(status IN ('RECORDED','PLANNED','APPLIED','WAITING_FOR_INPUT','WAITING_FOR_SAFE_BOUNDARY','FAILED')),
    response jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS agent.task_redirects (
    id bigserial PRIMARY KEY, task_id bigint NOT NULL REFERENCES agent.tasks(id), requested_by text NOT NULL,
    prior_objective text NOT NULL, new_objective text NOT NULL, redirect_context jsonb NOT NULL DEFAULT '{}',
    status text NOT NULL CHECK(status IN ('WAITING_FOR_SAFE_BOUNDARY','APPLIED','CANCELLED')),
    requested_at timestamptz NOT NULL DEFAULT clock_timestamp(), applied_at timestamptz
);
CREATE TABLE IF NOT EXISTS agent.committee_invitations (
    id bigserial PRIMARY KEY, packet_id bigint NOT NULL REFERENCES agent.committee_packets(id),
    agent_id bigint NOT NULL REFERENCES agent.profiles(id), invited_by text NOT NULL,
    invitation_status text NOT NULL DEFAULT 'INVITED' CHECK(invitation_status IN ('INVITED','ACKNOWLEDGED','DECLINED','CANCELLED')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(packet_id,agent_id)
);
CREATE TABLE IF NOT EXISTS agent.charlie_route_policies (
    policy_key text PRIMARY KEY, runtime_scope text NOT NULL DEFAULT 'internal', book_id bigint, client_id bigint,
    routine_route_class text NOT NULL DEFAULT 'local', red_team_route_class text NOT NULL DEFAULT 'cloud_approval_required',
    public_cloud_requires_approval boolean NOT NULL DEFAULT true, created_by text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Specialist work is explicit, while broker and credential capabilities remain denied.
UPDATE agent.agent_workspaces w SET allowed_task_classes=(
    SELECT array_agg(DISTINCT value ORDER BY value)
    FROM unnest(w.allowed_task_classes||ARRAY['research','handoff']) value)
FROM agent.profiles p WHERE p.id=w.agent_id AND (
    p.department='research' OR p.agent_name IN ('Company Analyst','Industry Analyst','Forensic Accounting Agent','Valuation Agent','Research Director'));
UPDATE agent.agent_workspaces w SET allowed_task_classes=(
    SELECT array_agg(DISTINCT value ORDER BY value)
    FROM unnest(w.allowed_task_classes||ARRAY['committee','handoff']) value)
FROM agent.profiles p WHERE p.id=w.agent_id AND p.agent_name IN ('Risk Agent','Portfolio Manager','Long-Term Portfolio Manager','Charlie Munger');

CREATE OR REPLACE FUNCTION agent.ensure_runtime_workspace() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE classes text[]:=ARRAY['general'];
BEGIN
    IF NEW.department='research' OR NEW.agent_name IN ('Company Analyst','Industry Analyst','Forensic Accounting Agent','Valuation Agent','Research Director') THEN
        classes:=classes||ARRAY['research','handoff'];
    ELSIF NEW.agent_name IN ('Risk Agent','Portfolio Manager','Long-Term Portfolio Manager','Charlie Munger') THEN
        classes:=classes||ARRAY['committee','handoff'];
    END IF;
    INSERT INTO agent.agent_workspaces(agent_id,workspace_key,room_key,role_version,allowed_task_classes)
    VALUES(NEW.id,NEW.agent_key,NEW.department,NEW.role_version,classes) ON CONFLICT DO NOTHING;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION agent.create_charlie_plan(
    p_request text,p_user text,p_command text,p_intent text,p_understood text,p_context jsonb,p_entities jsonb,
    p_scope text,p_book bigint,p_client bigint,p_data_class text,p_agent bigint,p_task_title text,p_task_objective text,
    p_task_class text,p_policy text,p_approval text,p_budget jsonb DEFAULT '{}') RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE command agent.charlie_commands; objective_id bigint; plan_id bigint; task_id bigint; assignee text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_request));
    SELECT * INTO command FROM agent.charlie_commands WHERE request_key=p_request;
    IF FOUND THEN
        IF command.raw_command<>p_command OR command.actor_user_id<>p_user OR command.runtime_scope<>p_scope
          OR command.book_id IS DISTINCT FROM p_book OR command.client_id IS DISTINCT FROM p_client THEN
            RAISE EXCEPTION 'Charlie command idempotency conflict'; END IF;
        RETURN jsonb_build_object('command_id',command.id,'objective_id',command.objective_id,
        'plan_id',command.plan_id,'duplicate',true); END IF;
    INSERT INTO agent.objectives(objective_key,understood_objective,context,affected_entities,runtime_scope,
        book_id,client_id,data_class,created_by,status)
    VALUES(p_request,p_understood,p_context,p_entities,p_scope,p_book,p_client,p_data_class,p_user,'ACTIVE')
    RETURNING id INTO objective_id;
    INSERT INTO agent.plans(objective_id,policy_classification,approval_class,budget,status,next_action)
    VALUES(objective_id,p_policy,p_approval,p_budget,'ACTIVE','Await canonical task claim and evidence-backed output.')
    RETURNING id INTO plan_id;
    IF p_agent IS NOT NULL THEN
        SELECT agent_name INTO assignee FROM agent.profiles WHERE id=p_agent AND status='active';
        IF assignee IS NULL THEN RAISE EXCEPTION 'active assigned agent required'; END IF;
        INSERT INTO agent.tasks(title,objective,owner_agent,status,priority,source_kind,source_ref,agent_id,
            runtime_protocol,runtime_state,task_class,runtime_scope,recovery_policy,book_id,client_id,data_class,runtime_context)
        VALUES(p_task_title,p_task_objective,assignee,'queued','high','charlie_plan',p_request,p_agent,'lease_v1','PLANNING',
            p_task_class,p_scope,'idempotent_read',p_book,p_client,p_data_class,
            p_context||jsonb_build_object('objective_id',objective_id,'plan_id',plan_id,'paid_model_work_paused',false))
        RETURNING id INTO task_id;
        INSERT INTO agent.plan_tasks(plan_id,task_id,sequence_no,assignment_reason)
        VALUES(plan_id,task_id,1,'Charlie resolved an existing specialist identity and durable context.');
    END IF;
    INSERT INTO agent.charlie_commands(request_key,raw_command,intent,objective_id,plan_id,runtime_scope,book_id,
        client_id,actor_user_id,status)
    VALUES(p_request,p_command,p_intent,objective_id,plan_id,p_scope,p_book,p_client,p_user,'PLANNED') RETURNING * INTO command;
    PERFORM agent.append_scoped_runtime_event('plan_created','PLANNING',task_id,p_agent,'operator',p_user,NULL);
    RETURN jsonb_build_object('command_id',command.id,'objective_id',objective_id,'plan_id',plan_id,
        'task_id',task_id,'duplicate',false,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.redirect_runtime_task(p_task bigint,p_actor text,p_objective text,p_context jsonb DEFAULT '{}')
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE task agent.tasks; redirect_id bigint; active_lease boolean;
BEGIN
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND OR task.runtime_protocol<>'lease_v1' OR task.status IN ('completed','cancelled','failed') THEN
        RAISE EXCEPTION 'redirectable managed task required'; END IF;
    SELECT EXISTS(SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE' AND expires_at>clock_timestamp()) INTO active_lease;
    INSERT INTO agent.task_redirects(task_id,requested_by,prior_objective,new_objective,redirect_context,status)
    VALUES(p_task,p_actor,task.objective,p_objective,p_context,CASE WHEN active_lease THEN 'WAITING_FOR_SAFE_BOUNDARY' ELSE 'APPLIED' END)
    RETURNING id INTO redirect_id;
    IF active_lease THEN
        UPDATE agent.tasks SET control_requested='pause',runtime_context=runtime_context||jsonb_build_object(
            'pending_redirect_id',redirect_id,'pending_redirect_objective',p_objective,'pending_redirect_context',p_context),
            updated_at=clock_timestamp() WHERE id=p_task;
    ELSE
        PERFORM set_config('aios.runtime_task',p_task::text,true);
        UPDATE agent.tasks SET objective=p_objective,runtime_context=(runtime_context-'pending_redirect_id'-'pending_redirect_objective'-'pending_redirect_context')||p_context,
            updated_at=clock_timestamp() WHERE id=p_task;
        UPDATE agent.task_redirects SET applied_at=clock_timestamp() WHERE id=redirect_id;
    END IF;
    PERFORM agent.append_scoped_runtime_event('task_redirected',CASE WHEN active_lease THEN 'WAITING_FOR_SAFE_BOUNDARY' ELSE coalesce(task.runtime_state,'PLANNING') END,
        p_task,task.agent_id,'operator',p_actor,CASE WHEN active_lease THEN 'redirect_pending' ELSE 'redirect_applied' END);
    RETURN jsonb_build_object('task_id',p_task,'redirect_id',redirect_id,'applied',NOT active_lease,
        'waiting_for_safe_boundary',active_lease,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.apply_pending_runtime_redirect(p_task bigint,p_actor text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE task agent.tasks; redirect agent.task_redirects;
BEGIN
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE;
    IF NOT FOUND OR task.status NOT IN ('paused','queued','blocked') OR EXISTS(
        SELECT 1 FROM agent.task_leases WHERE task_id=p_task AND status='ACTIVE') THEN
        RAISE EXCEPTION 'redirect safe boundary not reached'; END IF;
    SELECT * INTO redirect FROM agent.task_redirects WHERE id=(task.runtime_context->>'pending_redirect_id')::bigint
        AND status='WAITING_FOR_SAFE_BOUNDARY' FOR UPDATE;
    IF NOT FOUND THEN RETURN jsonb_build_object('task_id',p_task,'applied',false,'reason','no_pending_redirect'); END IF;
    PERFORM set_config('aios.runtime_task',p_task::text,true);
    UPDATE agent.tasks SET objective=redirect.new_objective,
        runtime_context=(runtime_context-'pending_redirect_id'-'pending_redirect_objective'-'pending_redirect_context')||redirect.redirect_context,
        updated_at=clock_timestamp() WHERE id=p_task;
    UPDATE agent.task_redirects SET status='APPLIED',applied_at=clock_timestamp() WHERE id=redirect.id;
    PERFORM agent.append_scoped_runtime_event('task_redirected',coalesce(task.runtime_state,'PAUSED'),p_task,
        task.agent_id,'operator',p_actor,'redirect_applied');
    RETURN jsonb_build_object('task_id',p_task,'redirect_id',redirect.id,'applied',true,'broker_write_allowed',false);
END $$;

CREATE OR REPLACE FUNCTION agent.stop_paid_runtime_case(p_case bigint,p_actor text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE task agent.tasks; affected integer:=0;
BEGIN
    FOR task IN SELECT * FROM agent.tasks WHERE runtime_protocol='lease_v1'
        AND coalesce(runtime_context->>'research_case_id','') ~ '^[1-9][0-9]{0,17}$'
        AND (runtime_context->>'research_case_id')::bigint=p_case FOR UPDATE LOOP
        UPDATE agent.tasks SET runtime_context=runtime_context||'{"paid_model_work_paused":true}'::jsonb,
            updated_at=clock_timestamp() WHERE id=task.id;
        PERFORM agent.append_scoped_runtime_event('paid_work_stopped',coalesce(task.runtime_state,'PAUSED'),task.id,
            task.agent_id,'operator',p_actor,'case_paid_work_stopped');
        affected:=affected+1;
    END LOOP;
    RETURN jsonb_build_object('research_case_id',p_case,'tasks_affected',affected,'paid_model_work_paused',true,
        'local_work_paused',false,'broker_write_allowed',false);
END $$;

COMMIT;
