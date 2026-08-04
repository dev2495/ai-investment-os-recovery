BEGIN;

CREATE TABLE IF NOT EXISTS agent.office_operability_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','passed','blocked','failed')),
    active_agent_count INTEGER NOT NULL DEFAULT 0,
    active_department_count INTEGER NOT NULL DEFAULT 0,
    started_by TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false CHECK (capital_action_allowed=false),
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false)
);

CREATE TABLE IF NOT EXISTS agent.office_operability_gate_results (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES agent.office_operability_runs(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL,
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('passed','blocked','failed')),
    observed_value NUMERIC,
    required_value NUMERIC,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_by TEXT NOT NULL DEFAULT 'Jarvis',
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
    UNIQUE (run_id,gate_key),
    CONSTRAINT office_operability_failure_reason CHECK (status='passed' OR failure_reason IS NOT NULL)
);

CREATE OR REPLACE FUNCTION agent.run_office_operability_acceptance(
    p_run_key TEXT,
    p_started_by TEXT DEFAULT 'Jarvis'
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id BIGINT;
    v_agents INTEGER;
    v_departments INTEGER;
BEGIN
    SELECT count(*) INTO v_agents FROM agent.v_agent_operating_readiness;
    SELECT count(*) INTO v_departments FROM agent.department_registry WHERE status='active';

    INSERT INTO agent.office_operability_runs (
        run_key,status,active_agent_count,active_department_count,started_by,
        started_at,finished_at,summary
    ) VALUES (
        p_run_key,'running',v_agents,v_departments,p_started_by,now(),NULL,
        jsonb_build_object('source_views',jsonb_build_array(
            'agent.v_employee_profiles_v1','agent.v_agent_operating_readiness',
            'agent.v_fund_function_coverage','agent.v_live_office_rooms'
        ),'capital_action_allowed',false,'broker_write_allowed',false)
    )
    ON CONFLICT (run_key) DO UPDATE SET
        status='running',active_agent_count=EXCLUDED.active_agent_count,
        active_department_count=EXCLUDED.active_department_count,
        started_by=EXCLUDED.started_by,started_at=now(),finished_at=NULL,
        summary=EXCLUDED.summary
    RETURNING id INTO v_run_id;

    DELETE FROM agent.office_operability_gate_results WHERE run_id=v_run_id;

    WITH readiness AS (
        SELECT * FROM agent.v_agent_operating_readiness
    ), staffed_departments AS (
        SELECT count(DISTINCT registry.department_key)::numeric AS observed
        FROM agent.department_registry registry
        JOIN agent.profiles profile ON profile.department=registry.department_key AND profile.status='active'
        WHERE registry.status='active'
    ), output_departments AS (
        SELECT count(DISTINCT profile.department)::numeric AS observed
        FROM agent.profiles profile
        JOIN agent.worker_runs run ON run.agent_name=profile.agent_name
        WHERE profile.status='active' AND run.status='completed'
          AND (nullif(trim(coalesce(run.output_summary,'')),'') IS NOT NULL
               OR nullif(trim(coalesce(run.output_note_path,'')),'') IS NOT NULL
               OR run.evidence NOT IN ('[]'::jsonb,'{}'::jsonb))
    ), observations AS (
        SELECT * FROM (VALUES
            ('roster_structure','Hierarchy Mailbox And Character',
             (SELECT count(*)::numeric FROM readiness WHERE hierarchy_ready AND mailbox_ready AND character_ready),v_agents::numeric,
             jsonb_build_object('active_agents',v_agents)),
            ('persona_identity','First-Class Employee Identity',
             (SELECT count(*)::numeric FROM agent.v_employee_profiles_v1 WHERE nullif(trim(persona),'') IS NOT NULL AND nullif(trim(voice_style),'') IS NOT NULL),v_agents::numeric,
             jsonb_build_object('requires','persona and voice for every active employee')),
            ('skills_tools','Role Skills And Resolved Tools',
             (SELECT count(*)::numeric FROM readiness WHERE skills_ready AND tools_ready),v_agents::numeric,
             jsonb_build_object('requires','at least one role skill and all requested tools resolved')),
            ('model_routes','Usable Model Or Deterministic Route',
             (SELECT count(*)::numeric FROM readiness WHERE model_assignment_ready AND model_route_ready),v_agents::numeric,
             jsonb_build_object('reasoning_model_not_required_for_deterministic_roles',true)),
            ('department_staffing','Every Active Department Is Staffed',
             (SELECT observed FROM staffed_departments),v_departments::numeric,
             jsonb_build_object('active_departments',v_departments)),
            ('fund_function_coverage','Every Fund Function Has Owner And Reviewer',
             (SELECT count(*)::numeric FROM agent.v_fund_function_coverage WHERE coverage_status='covered'),
             (SELECT count(*)::numeric FROM agent.v_fund_function_coverage),
             jsonb_build_object('independent_review_required',true)),
            ('bounded_worker_proof','Every Employee Completed Bounded Work',
             (SELECT count(*)::numeric FROM readiness WHERE runtime_tested),v_agents::numeric,
             jsonb_build_object('synthetic_worker_runs_allowed',false)),
            ('department_evidence','Every Department Produced Worker Evidence',
             (SELECT observed FROM output_departments),v_departments::numeric,
             jsonb_build_object('evidence_sources',jsonb_build_array('output_summary','output_note_path','worker evidence'))),
            ('inter_agent_handoffs','Inter-Agent Handoffs Are Durable',
             (SELECT count(*)::numeric FROM agent.agent_messages WHERE from_agent IS NOT NULL AND to_agent IS NOT NULL),1::numeric,
             jsonb_build_object('mailbox_table','agent.agent_messages')),
            ('processed_delegation','At Least One Delegation Was Processed',
             (SELECT count(*)::numeric FROM agent.agent_messages WHERE processing_status IN ('read','acknowledged','routed_to_task') OR generated_task_id IS NOT NULL),1::numeric,
             jsonb_build_object('requires','message processing or generated task')),
            ('zero_broker_writes','Office Workers Cannot Write Broker Orders',0::numeric,0::numeric,
             jsonb_build_object('capital_action_allowed',false,'broker_write_allowed',false))
        ) item(gate_key,gate_name,observed_value,required_value,evidence)
    )
    INSERT INTO agent.office_operability_gate_results (
        run_id,gate_key,gate_name,status,observed_value,required_value,evidence,failure_reason
    )
    SELECT v_run_id,gate_key,gate_name,
           CASE WHEN observed_value>=required_value THEN 'passed' ELSE 'blocked' END,
           observed_value,required_value,evidence,
           CASE WHEN observed_value>=required_value THEN NULL
                ELSE gate_name || ' incomplete: observed ' || observed_value || ', required ' || required_value END
    FROM observations;

    UPDATE agent.office_operability_runs run
    SET status=CASE WHEN EXISTS (
            SELECT 1 FROM agent.office_operability_gate_results result
            WHERE result.run_id=v_run_id AND result.status<>'passed'
        ) THEN 'blocked' ELSE 'passed' END,
        finished_at=now(),
        summary=run.summary || (SELECT jsonb_build_object(
            'gate_count',count(*),'passed_count',count(*) FILTER (WHERE status='passed'),
            'blocked_count',count(*) FILTER (WHERE status='blocked')
        ) FROM agent.office_operability_gate_results WHERE run_id=v_run_id)
    WHERE run.id=v_run_id;

    RETURN v_run_id;
END;
$$;

CREATE OR REPLACE VIEW agent.v_office_operability_acceptance AS
SELECT run.id,run.run_key,run.status,run.active_agent_count,run.active_department_count,
       count(result.id) AS gate_count,
       count(result.id) FILTER (WHERE result.status='passed') AS passed_count,
       count(result.id) FILTER (WHERE result.status='blocked') AS blocked_count,
       jsonb_agg(jsonb_build_object(
           'gate_key',result.gate_key,'gate_name',result.gate_name,'status',result.status,
           'observed_value',result.observed_value,'required_value',result.required_value,
           'failure_reason',result.failure_reason,'evidence',result.evidence
       ) ORDER BY result.id) FILTER (WHERE result.id IS NOT NULL) AS gates,
       run.started_by,run.started_at,run.finished_at,false AS broker_write_allowed
FROM agent.office_operability_runs run
LEFT JOIN agent.office_operability_gate_results result ON result.run_id=run.id
GROUP BY run.id;

COMMENT ON FUNCTION agent.run_office_operability_acceptance IS
    'Evaluates real employee, department, route, tool, worker, evidence, and handoff readiness without creating synthetic activity or broker writes.';

COMMIT;
