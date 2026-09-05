-- Final additive Agent OS acceptance contracts. This migration neither enrolls
-- tasks nor enables routines, model routes, provider calls or broker writes.
BEGIN;

-- Fail before changing the schema unless every prerequisite migration attests
-- its own exact semantic version. Table-name stubs are never migration proof.
DO $prerequisites$
BEGIN
    IF to_regclass('core.schema_migrations') IS NULL
       OR to_regclass('agent.task_leases') IS NULL
       OR to_regclass('agent.agent_workspaces') IS NULL
       OR to_regclass('agent.conversation_threads') IS NULL
       OR to_regclass('agent.model_binding_versions') IS NULL
       OR to_regclass('agent.routine_definitions') IS NULL
       OR to_regclass('agent.charlie_commands') IS NULL THEN
        RAISE EXCEPTION 'Phase 2 migrations 256 through 261 must be installed in order';
    END IF;
    IF (SELECT count(*) FROM core.schema_migrations
        WHERE (migration_number,migration_key,definition_checksum_sha256) IN (
          (256,'256_agent_runtime_leases_v1','3aa19ffced26f4ac3709ade35ec13193a833249ac3f22ae71a2b228ba4d19cd5'),
          (257,'257_agent_runtime_policy_events_v1','9c02ed6de61e0d9435ed5320a31a4e60eeaaad76f70d88ac38003add031999e5'),
          (258,'258_agent_conversations_handoffs_v1','b14d772e2b8a964f40ba0fbc792454f4a0819ca1e676ff615e53925a1d55c797'),
          (259,'259_agent_model_fabric_v1','ff523f10530ee7a58e21943bb1a16ea9dc1abfaf2dbe20a55062bf46e6b41c17'),
          (260,'260_ai_os_doctor_and_routines_v1','881a28749e8a6e50268ab9ae5b8c69dfea7c6c3cb2b28c84b49485303b143384'),
          (261,'261_charlie_chief_of_staff_v1','6408acc5b8b256fbd81710471aa98345f6fc685173aedd06a3e48fa5ea5ae055')
        ))<>6 THEN
        RAISE EXCEPTION 'Phase 2 prerequisite migration ledger mismatch';
    END IF;
END
$prerequisites$;

ALTER TABLE agent.task_events
    ADD COLUMN IF NOT EXISTS entity_ids JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

-- Event metadata is deliberately operational and reference-shaped. Prompts,
-- message bodies, direct identifiers and credentials belong in scoped source
-- tables, never in the shared office stream.
CREATE OR REPLACE FUNCTION agent.runtime_event_payload_safe(payload JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE item RECORD; element JSONB; normalized_key TEXT;
BEGIN
    IF payload IS NULL THEN RETURN true; END IF;
    IF core.jsonb_contains_raw_secret(payload) THEN RETURN false; END IF;
    IF jsonb_typeof(payload)='object' THEN
        FOR item IN SELECT key,value FROM jsonb_each(payload) LOOP
            normalized_key:=lower(regexp_replace(item.key,'[^a-z0-9]+','_','g'));
            IF normalized_key IN (
                'client_name','customer_name','email','email_address','phone','phone_number',
                'address','postal_address','account_number','bank_account','pan','pan_number',
                'aadhaar','aadhaar_number','prompt','raw_prompt','message_body','raw_text',
                'transcript','cookie','session_cookie','credentials'
            ) THEN RETURN false; END IF;
            IF NOT agent.runtime_event_payload_safe(item.value) THEN RETURN false; END IF;
        END LOOP;
    ELSIF jsonb_typeof(payload)='array' THEN
        FOR element IN SELECT value FROM jsonb_array_elements(payload) LOOP
            IF NOT agent.runtime_event_payload_safe(element) THEN RETURN false; END IF;
        END LOOP;
    END IF;
    RETURN true;
END $$;

DO $event_constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='runtime_event_entity_ids_object'
          AND conrelid='agent.task_events'::regclass
    ) THEN
        ALTER TABLE agent.task_events ADD CONSTRAINT runtime_event_entity_ids_object
            CHECK (jsonb_typeof(entity_ids)='object' AND pg_column_size(entity_ids)<16384
                   AND agent.runtime_event_payload_safe(entity_ids));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='runtime_event_metadata_object'
          AND conrelid='agent.task_events'::regclass
    ) THEN
        ALTER TABLE agent.task_events ADD CONSTRAINT runtime_event_metadata_object
            CHECK (jsonb_typeof(metadata)='object' AND pg_column_size(metadata)<16384
                   AND agent.runtime_event_payload_safe(metadata));
    END IF;
END
$event_constraints$;

-- Complete the bounded taxonomy used by runtime control and future producer
-- adapters. Existing event names remain unchanged for compatibility.
INSERT INTO agent.runtime_event_types(event_type,category) VALUES
 ('worker_registered','worker'),('worker_heartbeat','worker'),('worker_stale','worker'),
 ('task_created','task'),('dependency_added','task'),('task_paused','task'),
 ('task_resumed','task'),('task_cancelled','task'),
 ('approval_requested','approval'),('approval_updated','approval'),
 ('tool_call_started','tool'),('tool_call_completed','tool'),('tool_call_failed','tool'),
 ('execution_state_changed','execution'),('rollout_state_changed','system')
ON CONFLICT(event_type) DO NOTHING;

-- New producers use the v2 appender to populate complete typed fields. The old
-- function below remains an exact compatibility adapter for installed callers.
CREATE OR REPLACE FUNCTION agent.append_scoped_runtime_event_v2(
    p_event text,p_state text DEFAULT NULL,p_task bigint DEFAULT NULL,p_agent bigint DEFAULT NULL,
    p_actor_type text DEFAULT 'runtime',p_actor_id text DEFAULT NULL,p_reason text DEFAULT NULL,
    p_thread text DEFAULT NULL,p_handoff bigint DEFAULT NULL,p_committee bigint DEFAULT NULL,
    p_approval bigint DEFAULT NULL,p_research_case bigint DEFAULT NULL,p_model_route text DEFAULT NULL,
    p_model_call bigint DEFAULT NULL,p_tool_call bigint DEFAULT NULL,p_artifact_ids bigint[] DEFAULT '{}',
    p_risk_class text DEFAULT 'internal_read',p_entity_ids jsonb DEFAULT '{}',p_metadata jsonb DEFAULT '{}',
    p_worker uuid DEFAULT NULL,p_lease bigint DEFAULT NULL,p_step bigint DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE event_id bigint; scope_value text:='internal'; book_value bigint; client_value bigint;
BEGIN
    IF jsonb_typeof(coalesce(p_entity_ids,'{}'))<>'object'
       OR jsonb_typeof(coalesce(p_metadata,'{}'))<>'object'
       OR pg_column_size(coalesce(p_entity_ids,'{}'))>=16384
       OR pg_column_size(coalesce(p_metadata,'{}'))>=16384
       OR NOT agent.runtime_event_payload_safe(coalesce(p_entity_ids,'{}'))
       OR NOT agent.runtime_event_payload_safe(coalesce(p_metadata,'{}')) THEN
        RAISE EXCEPTION 'runtime event payload is unsafe or unbounded';
    END IF;
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
    IF p_lease IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM agent.task_leases lease
        WHERE lease.id=p_lease
          AND (p_task IS NULL OR lease.task_id=p_task)
          AND (p_agent IS NULL OR lease.agent_id=p_agent)
          AND (p_worker IS NULL OR lease.worker_id=p_worker)
    ) THEN RAISE EXCEPTION 'event lease producer scope mismatch'; END IF;
    IF p_step IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM agent.task_steps step
        WHERE step.id=p_step AND (p_task IS NULL OR step.task_id=p_task)
          AND (p_lease IS NULL OR step.lease_id=p_lease)
    ) THEN RAISE EXCEPTION 'event step producer scope mismatch'; END IF;
    INSERT INTO agent.task_events(
        task_id,agent_id,worker_id,lease_id,step_id,event_type,state,reason_code,runtime_scope,book_id,client_id,
        actor_type,actor_id,thread_key,handoff_id,committee_id,approval_id,research_case_id,
        model_route,model_call_id,tool_call_id,artifact_ids,risk_class,entity_ids,metadata
    ) VALUES (
        p_task,p_agent,p_worker,p_lease,p_step,p_event,p_state,p_reason,scope_value,book_value,client_value,
        p_actor_type,p_actor_id,p_thread,p_handoff,p_committee,p_approval,p_research_case,
        p_model_route,p_model_call,p_tool_call,coalesce(p_artifact_ids,'{}'),p_risk_class,
        coalesce(p_entity_ids,'{}'),coalesce(p_metadata,'{}')
    ) RETURNING id INTO event_id;
    RETURN event_id;
END $$;

CREATE OR REPLACE FUNCTION agent.append_scoped_runtime_event(
    p_event text,p_state text DEFAULT NULL,p_task bigint DEFAULT NULL,p_agent bigint DEFAULT NULL,
    p_actor_type text DEFAULT 'runtime',p_actor_id text DEFAULT NULL,p_reason text DEFAULT NULL,
    p_thread text DEFAULT NULL,p_handoff bigint DEFAULT NULL,p_committee bigint DEFAULT NULL,
    p_approval bigint DEFAULT NULL,p_research_case bigint DEFAULT NULL,p_model_route text DEFAULT NULL,
    p_model_call bigint DEFAULT NULL,p_tool_call bigint DEFAULT NULL,p_artifact_ids bigint[] DEFAULT '{}',
    p_risk_class text DEFAULT 'internal_read'
) RETURNS bigint LANGUAGE sql AS $$
SELECT agent.append_scoped_runtime_event_v2(
    p_event,p_state,p_task,p_agent,p_actor_type,p_actor_id,p_reason,p_thread,p_handoff,
    p_committee,p_approval,p_research_case,p_model_route,p_model_call,p_tool_call,
    p_artifact_ids,p_risk_class,'{}'::jsonb,'{}'::jsonb)
$$;

CREATE OR REPLACE VIEW agent.v_runtime_events_v1 AS
SELECT event.id AS event_id,event.event_type,event.occurred_at,event.recorded_at,
       event.actor_type,event.actor_id,event.agent_id,event.worker_id,event.task_id,event.lease_id,
       event.step_id AS task_step_id,event.thread_key AS thread_id,event.handoff_id,
       event.committee_id,event.approval_id,event.research_case_id,event.entity_ids,
       event.book_id,event.client_id,event.model_route,event.model_call_id,
       event.tool_call_id,event.artifact_ids,event.state AS status,event.risk_class,
       event.runtime_scope,event.reason_code,event.metadata
FROM agent.task_events event
WHERE agent.runtime_event_payload_safe(event.entity_ids)
  AND agent.runtime_event_payload_safe(event.metadata);
COMMENT ON VIEW agent.v_runtime_events_v1 IS
    'Secret/PII-safe bounded event projection. Callers must still authorize runtime_scope, book_id and client_id before returning rows.';

CREATE TABLE IF NOT EXISTS agent.event_retention_policies (
    policy_key TEXT PRIMARY KEY,
    hot_days INTEGER NOT NULL CHECK(hot_days BETWEEN 365 AND 3650),
    checkpoint_interval_events INTEGER NOT NULL CHECK(checkpoint_interval_events BETWEEN 1000 AND 1000000),
    original_events_append_only BOOLEAN NOT NULL DEFAULT true,
    automatic_delete_enabled BOOLEAN NOT NULL DEFAULT false,
    archive_restore_receipt_required BOOLEAN NOT NULL DEFAULT true,
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK(original_events_append_only AND NOT automatic_delete_enabled AND archive_restore_receipt_required)
);
INSERT INTO agent.event_retention_policies(
    policy_key,hot_days,checkpoint_interval_events,updated_by
) VALUES ('runtime_events_v1',365,10000,'Phase 2 migration 262')
ON CONFLICT(policy_key) DO NOTHING;

CREATE OR REPLACE FUNCTION agent.reject_event_retention_policy_edit()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'event retention policy changes require a versioned migration'; END $$;
CREATE OR REPLACE TRIGGER event_retention_policy_immutable
    BEFORE UPDATE OR DELETE ON agent.event_retention_policies
    FOR EACH ROW EXECUTE FUNCTION agent.reject_event_retention_policy_edit();

CREATE TABLE IF NOT EXISTS agent.runtime_rollout_history (
    id BIGSERIAL PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE CHECK(length(request_key) BETWEEN 8 AND 160),
    prior_mode TEXT NOT NULL CHECK(prior_mode IN ('enabled','draining','disabled')),
    requested_mode TEXT NOT NULL CHECK(requested_mode IN ('enabled','draining','disabled')),
    actor TEXT NOT NULL CHECK(length(actor) BETWEEN 1 AND 160),
    active_leases INTEGER NOT NULL CHECK(active_leases>=0),
    expired_unreaped_leases INTEGER NOT NULL CHECK(expired_unreaped_leases>=0),
    queued_managed_tasks INTEGER NOT NULL CHECK(queued_managed_tasks>=0),
    reason_code TEXT NOT NULL CHECK(reason_code ~ '^[a-zA-Z0-9_.-]{1,120}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK(NOT broker_write_allowed)
);
CREATE OR REPLACE FUNCTION agent.reject_runtime_rollout_edit()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'runtime rollout history is append-only'; END $$;
CREATE OR REPLACE TRIGGER runtime_rollout_history_immutable
    BEFORE UPDATE OR DELETE ON agent.runtime_rollout_history
    FOR EACH ROW EXECUTE FUNCTION agent.reject_runtime_rollout_edit();

-- Snapshot every applicable immutable Model Fabric version. A later head change
-- therefore cannot rewrite the policy stored on an existing lease.
CREATE OR REPLACE FUNCTION agent.current_model_binding_snapshot(p_agent bigint)
RETURNS JSONB LANGUAGE sql STABLE AS $$
SELECT coalesce(jsonb_agg(jsonb_build_object(
    'binding_key',version.binding_key,'version_id',version.id,'version',version.version,
    'task_class',version.task_class,'primary_route',version.primary_route,
    'fallback_routes',version.fallback_routes,'fallback_policy',version.fallback_policy,
    'reasoning_profile',version.reasoning_profile,'context_budget',version.context_budget,
    'max_output_tokens',version.max_output_tokens,'privacy_classes',version.privacy_classes
) ORDER BY version.binding_key,version.task_class),'[]'::jsonb)
FROM agent.profiles profile
JOIN agent.model_binding_versions version ON
    (version.selector_kind='agent' AND version.selector_value=ANY(ARRAY[profile.agent_key,profile.agent_name,profile.id::text]))
 OR (version.selector_kind='role' AND version.selector_value=ANY(ARRAY[profile.role_scope,profile.department]))
JOIN agent.model_binding_heads head ON head.binding_key=version.binding_key
    AND head.version_id=version.id AND head.enabled
WHERE profile.id=p_agent
$$;

CREATE OR REPLACE FUNCTION agent.runtime_policy_snapshot(p_agent bigint) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; binding jsonb; budget jsonb; fabric jsonb;
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
    fabric:=agent.current_model_binding_snapshot(p_agent);
    RETURN result||jsonb_build_object('model_assignment',binding,'cost_policy',budget,'model_fabric_bindings',fabric);
END $$;

-- Replace the migration-257 wrapper with the same contract plus the rollout
-- lock. Mode changes and claims can no longer pass one another in flight.
CREATE OR REPLACE FUNCTION agent.claim_runtime_task(
    p_worker uuid,p_task bigint,p_agent bigint,p_token_hash text,p_committee_reclaim boolean DEFAULT false
) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE policy agent.agent_workspaces; task agent.tasks; result jsonb; config agent.runtime_settings; lease_policy jsonb;
BEGIN
    PERFORM pg_advisory_xact_lock(262,1);
    SELECT * INTO config FROM agent.runtime_settings WHERE singleton FOR SHARE;
    IF config.claim_mode<>'enabled' THEN RETURN '{}'; END IF;
    PERFORM 1 FROM agent.workers WHERE id=p_worker FOR UPDATE;
    PERFORM 1 FROM agent.profiles WHERE id=p_agent FOR UPDATE;
    SELECT * INTO policy FROM agent.agent_workspaces WHERE agent_id=p_agent FOR SHARE;
    SELECT * INTO task FROM agent.tasks WHERE id=p_task FOR UPDATE SKIP LOCKED;
    IF NOT FOUND OR policy.agent_id IS NULL THEN RETURN '{}'; END IF;
    IF policy.role_version<>(SELECT role_version FROM agent.profiles WHERE id=p_agent) THEN RETURN '{}'; END IF;
    IF NOT(task.task_class=ANY(policy.allowed_task_classes)) OR NOT(task.runtime_scope=ANY(policy.allowed_scopes))
      OR NOT(task.data_class=ANY(policy.allowed_data_classes))
      OR (task.book_id IS NOT NULL AND NOT(task.book_id=ANY(policy.allowed_books)))
      OR (task.client_id IS NOT NULL AND NOT(task.client_id=ANY(policy.allowed_clients))) THEN RETURN '{}'; END IF;
    result:=agent.claim_runtime_task_base(p_worker,p_task,p_agent,p_token_hash,p_committee_reclaim);
    IF result='{}'::jsonb THEN RETURN result; END IF;
    SELECT policy_snapshot INTO STRICT lease_policy FROM agent.task_leases
    WHERE id=(result->>'lease_id')::bigint;
    RETURN result||jsonb_build_object('heartbeat_seconds',config.active_heartbeat_seconds,
        'policy_version',policy.role_version,'idle_heartbeat_seconds',config.idle_heartbeat_seconds,
        'model_fabric_bindings',lease_policy->'model_fabric_bindings');
END $$;

CREATE OR REPLACE FUNCTION agent.set_runtime_claim_mode(
    p_request TEXT,p_expected TEXT,p_requested TEXT,p_actor TEXT,p_reason TEXT
) RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE settings agent.runtime_settings; prior agent.runtime_rollout_history;
    live_count INTEGER; unreaped_count INTEGER; queued_count INTEGER; history_id BIGINT;
BEGIN
    IF p_request IS NULL OR length(p_request) NOT BETWEEN 8 AND 160
       OR p_requested NOT IN ('enabled','draining','disabled')
       OR p_expected NOT IN ('enabled','draining','disabled')
       OR p_actor IS NULL OR length(p_actor) NOT BETWEEN 1 AND 160
       OR p_reason IS NULL OR p_reason !~ '^[a-zA-Z0-9_.-]{1,120}$' THEN
        RAISE EXCEPTION 'invalid bounded rollout request';
    END IF;
    PERFORM pg_advisory_xact_lock(262,1);
    SELECT * INTO prior FROM agent.runtime_rollout_history WHERE request_key=p_request;
    IF FOUND THEN
        IF prior.prior_mode<>p_expected OR prior.requested_mode<>p_requested
           OR prior.actor<>p_actor OR prior.reason_code<>p_reason THEN
            RAISE EXCEPTION 'rollout request key payload mismatch';
        END IF;
        RETURN jsonb_build_object('rollout_id',prior.id,'prior_mode',prior.prior_mode,
            'claim_mode',prior.requested_mode,'active_leases',prior.active_leases,
            'expired_unreaped_leases',prior.expired_unreaped_leases,
            'queued_managed_tasks',prior.queued_managed_tasks,'duplicate',true,
            'no_change',prior.prior_mode=prior.requested_mode,
            'broker_write_allowed',false);
    END IF;
    SELECT * INTO settings FROM agent.runtime_settings WHERE singleton FOR UPDATE;
    IF settings.claim_mode<>p_expected THEN RAISE EXCEPTION 'runtime rollout state changed'; END IF;
    SELECT count(*) INTO live_count FROM agent.task_leases
      WHERE status='ACTIVE' AND expires_at>clock_timestamp();
    SELECT count(*) INTO unreaped_count FROM agent.task_leases
      WHERE status='ACTIVE' AND expires_at<=clock_timestamp();
    SELECT count(*) INTO queued_count FROM agent.tasks
      WHERE runtime_protocol='lease_v1' AND status='queued';
    IF p_expected=p_requested THEN
        INSERT INTO agent.runtime_rollout_history(
            request_key,prior_mode,requested_mode,actor,active_leases,
            expired_unreaped_leases,queued_managed_tasks,reason_code
        ) VALUES(p_request,p_expected,p_requested,p_actor,live_count,
            unreaped_count,queued_count,p_reason) RETURNING id INTO history_id;
        RETURN jsonb_build_object('rollout_id',history_id,'prior_mode',p_expected,
            'claim_mode',p_requested,'active_leases',live_count,
            'expired_unreaped_leases',unreaped_count,
            'queued_managed_tasks',queued_count,'no_change',true,
            'duplicate',false,'broker_write_allowed',false);
    END IF;
    IF (p_expected,p_requested) NOT IN (
        ('enabled','draining'),('draining','disabled'),('draining','enabled'),('disabled','enabled')
    ) THEN RAISE EXCEPTION 'illegal runtime rollout transition'; END IF;
    IF p_requested='disabled' AND (live_count>0 OR unreaped_count>0) THEN
        RAISE EXCEPTION 'runtime must drain and reap all active leases before disable';
    END IF;
    UPDATE agent.runtime_settings SET claim_mode=p_requested WHERE singleton;
    INSERT INTO agent.runtime_rollout_history(
        request_key,prior_mode,requested_mode,actor,active_leases,
        expired_unreaped_leases,queued_managed_tasks,reason_code
    ) VALUES(p_request,settings.claim_mode,p_requested,p_actor,live_count,
        unreaped_count,queued_count,p_reason) RETURNING id INTO history_id;
    PERFORM agent.append_scoped_runtime_event_v2(
        'rollout_state_changed',upper(p_requested),NULL,NULL,'operator',p_actor,p_reason,
        NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'{}','internal_read',
        jsonb_build_object('rollout_id',history_id),
        jsonb_build_object('request_key',p_request,'prior_mode',settings.claim_mode,
                           'requested_mode',p_requested));
    RETURN jsonb_build_object('rollout_id',history_id,'prior_mode',settings.claim_mode,
        'claim_mode',p_requested,'active_leases',live_count,
        'expired_unreaped_leases',unreaped_count,'queued_managed_tasks',queued_count,
        'duplicate',false,'broker_write_allowed',false);
END $$;
REVOKE ALL ON FUNCTION agent.set_runtime_claim_mode(TEXT,TEXT,TEXT,TEXT,TEXT) FROM PUBLIC;

CREATE OR REPLACE FUNCTION agent.runtime_cutover_status()
RETURNS JSONB LANGUAGE sql STABLE AS $$
SELECT jsonb_build_object(
    'claim_mode',(SELECT claim_mode FROM agent.runtime_settings WHERE singleton),
    'active_leases',(SELECT count(*) FROM agent.task_leases WHERE status='ACTIVE' AND expires_at>statement_timestamp()),
    'expired_unreaped_leases',(SELECT count(*) FROM agent.task_leases WHERE status='ACTIVE' AND expires_at<=statement_timestamp()),
    'managed_queued_tasks',(SELECT count(*) FROM agent.tasks WHERE runtime_protocol='lease_v1' AND status='queued'),
    'legacy_open_tasks',(SELECT count(*) FROM agent.tasks WHERE runtime_protocol='legacy' AND status IN ('queued','in_progress','blocked','needs_review')),
    'uncertain_steps',(SELECT count(*) FROM agent.task_steps WHERE side_effect_status='uncertain'),
    'broker_write_allowed',false
)
$$;

CREATE OR REPLACE VIEW agent.v_agent_runtime_workspace_snapshot AS
SELECT profile.id AS agent_id,profile.agent_key,profile.agent_name,profile.display_title,
       profile.department,profile.role_scope,profile.role_version,profile.permission_level,
       profile.max_parallel_tasks,workspace.workspace_key,workspace.role_version AS policy_version,
       workspace.owner_agent_id,workspace.escalation_agent_id,workspace.room_key,
       workspace.allowed_task_classes,workspace.allowed_scopes,workspace.allowed_books,
       workspace.allowed_clients,workspace.allowed_data_classes,workspace.denied_capabilities,
       workspace.daily_token_budget,workspace.capability_status,profile.default_model_route,
       profile.default_tools,profile.guardrails,profile.status,
       agent.current_model_binding_snapshot(profile.id) AS model_fabric_bindings,
       agent.runtime_policy_snapshot(profile.id) AS current_claim_snapshot,
       (workspace.role_version=profile.role_version) AS policy_version_current,
       false AS broker_write_allowed
FROM agent.profiles profile
JOIN agent.agent_workspaces workspace ON workspace.agent_id=profile.id
WHERE profile.status='active';

CREATE OR REPLACE VIEW agent.v_desk_operating_status_v1 AS
WITH desks AS (
  SELECT department.department_key,department.department_name,department.status,
         count(DISTINCT profile.id) FILTER(WHERE profile.status='active')::INTEGER AS active_agents,
         count(DISTINCT workspace.agent_id) FILTER(
             WHERE profile.status='active' AND workspace.role_version=profile.role_version
         )::INTEGER AS policy_snapshots,
         count(DISTINCT profile.id) FILTER(
             WHERE profile.status='active' AND workspace.capability_status='READY'
               AND workspace.role_version=profile.role_version
         )::INTEGER AS policy_ready,
         count(DISTINCT profile.id) FILTER(WHERE profile.status='active' AND coalesce(capability.tools_ready,false))::INTEGER AS tools_ready,
         count(DISTINCT profile.id) FILTER(WHERE profile.status='active' AND presence.has_live_lease)::INTEGER AS live_agents,
         coalesce(array_agg(DISTINCT missing.missing_tool) FILTER(WHERE missing.missing_tool IS NOT NULL),'{}') AS missing_tools
  FROM agent.department_registry department
  LEFT JOIN agent.profiles profile ON profile.department=department.department_key
  LEFT JOIN agent.agent_workspaces workspace ON workspace.agent_id=profile.id
  LEFT JOIN agent.v_agent_capability_readiness capability ON capability.agent_name=profile.agent_name
  LEFT JOIN agent.v_runtime_presence presence ON presence.agent_id=profile.id
  LEFT JOIN LATERAL unnest(coalesce(capability.missing_tools,'{}')) missing(missing_tool) ON true
  GROUP BY department.department_key,department.department_name,department.status
)
SELECT desks.*,
       CASE
         WHEN status<>'active' OR active_agents=0 THEN 'UNAVAILABLE'
         WHEN policy_snapshots<active_agents OR policy_ready<active_agents OR tools_ready<active_agents THEN 'PARTIAL'
         WHEN live_agents=0 THEN 'IDLE'
         ELSE 'READY'
       END AS operating_status,
       false AS broker_write_allowed
FROM desks;
COMMENT ON VIEW agent.v_desk_operating_status_v1 IS
    'READY requires current role-policy versions, complete tool readiness and a live lease. No desk is labelled complete.';

INSERT INTO core.schema_migrations(
    migration_number,migration_key,definition_checksum_sha256,description,metadata
) VALUES (
    262,'262_agent_os_acceptance_contracts_v1',
    'b83040fb45be68f0ec96f2c57360ec561ef00c35376ad6cda7401cbf41e5470c',
    'Complete event, rollout, workspace and truthful desk-status contracts',
    '{"auto_delete_events":false,"auto_enable":false,"broker_write_allowed":false}'::jsonb
) ON CONFLICT(migration_number) DO NOTHING;

DO $acceptance_guard$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM core.schema_migrations
        WHERE migration_number=262
          AND migration_key='262_agent_os_acceptance_contracts_v1'
          AND definition_checksum_sha256='b83040fb45be68f0ec96f2c57360ec561ef00c35376ad6cda7401cbf41e5470c'
    ) THEN RAISE EXCEPTION 'migration 262 ledger mismatch'; END IF;
    IF EXISTS(
        SELECT 1 FROM agent.v_desk_operating_status_v1
        WHERE operating_status NOT IN ('IDLE','UNAVAILABLE','PARTIAL','READY')
    ) THEN RAISE EXCEPTION 'invalid desk operating status'; END IF;
END
$acceptance_guard$;

COMMIT;
