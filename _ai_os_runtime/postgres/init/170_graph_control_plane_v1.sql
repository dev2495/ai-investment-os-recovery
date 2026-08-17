BEGIN;

-- Durable, declarative execution graphs. Graph nodes may dispatch registered
-- skills and governed tasks; they never contain arbitrary SQL or shell code.
CREATE TABLE IF NOT EXISTS agent.graph_definitions (
    graph_key TEXT PRIMARY KEY,
    graph_name TEXT NOT NULL,
    graph_family TEXT NOT NULL,
    description TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','active','paused','retired')),
    active_version INTEGER,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    default_autonomy_level TEXT NOT NULL DEFAULT 'draft_only'
        CHECK (default_autonomy_level IN ('observe_only','draft_only','bounded_autonomous','human_approval','prohibited')),
    input_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.graph_versions (
    id BIGSERIAL PRIMARY KEY,
    graph_key TEXT NOT NULL REFERENCES agent.graph_definitions(graph_key) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','validated','active','retired','rejected')),
    change_summary TEXT NOT NULL,
    source_kind TEXT NOT NULL DEFAULT 'operator_authored',
    source_ref TEXT,
    definition_hash TEXT,
    validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (graph_key, version)
);

CREATE TABLE IF NOT EXISTS agent.graph_nodes (
    id BIGSERIAL PRIMARY KEY,
    graph_version_id BIGINT NOT NULL REFERENCES agent.graph_versions(id) ON DELETE CASCADE,
    node_key TEXT NOT NULL,
    node_name TEXT NOT NULL,
    node_type TEXT NOT NULL
        CHECK (node_type IN ('start','agent_task','tool_task','router','join','checkpoint','approval_gate','committee','end')),
    owner_agent TEXT,
    skill_key TEXT REFERENCES agent.skills(skill_key) ON DELETE RESTRICT,
    autonomy_level TEXT NOT NULL DEFAULT 'draft_only'
        CHECK (autonomy_level IN ('observe_only','draft_only','bounded_autonomous','human_approval','prohibited')),
    approval_required BOOLEAN NOT NULL DEFAULT false,
    retry_limit INTEGER NOT NULL DEFAULT 1 CHECK (retry_limit BETWEEN 0 AND 10),
    timeout_seconds INTEGER NOT NULL DEFAULT 900 CHECK (timeout_seconds BETWEEN 1 AND 86400),
    input_mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    on_error TEXT NOT NULL DEFAULT 'pause'
        CHECK (on_error IN ('pause','fail','route_failure','request_human')),
    ui_position JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (graph_version_id, node_key)
);

CREATE TABLE IF NOT EXISTS agent.graph_edges (
    id BIGSERIAL PRIMARY KEY,
    graph_version_id BIGINT NOT NULL REFERENCES agent.graph_versions(id) ON DELETE CASCADE,
    from_node_key TEXT NOT NULL,
    to_node_key TEXT NOT NULL,
    edge_kind TEXT NOT NULL DEFAULT 'success'
        CHECK (edge_kind IN ('success','conditional','failure','loop')),
    condition_type TEXT NOT NULL DEFAULT 'always'
        CHECK (condition_type IN ('always','state_equals','state_present','approved','rejected','node_output_equals','node_output_not_equals')),
    condition JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT true,
    label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (graph_version_id, from_node_key, to_node_key, edge_kind),
    FOREIGN KEY (graph_version_id, from_node_key)
        REFERENCES agent.graph_nodes(graph_version_id, node_key) ON DELETE CASCADE,
    FOREIGN KEY (graph_version_id, to_node_key)
        REFERENCES agent.graph_nodes(graph_version_id, node_key) ON DELETE CASCADE,
    CHECK (edge_kind <> 'loop' OR coalesce((condition->>'max_iterations')::INTEGER, 0) BETWEEN 1 AND 50)
);

CREATE TABLE IF NOT EXISTS agent.graph_runs (
    id BIGSERIAL PRIMARY KEY,
    graph_key TEXT NOT NULL REFERENCES agent.graph_definitions(graph_key) ON DELETE RESTRICT,
    graph_version_id BIGINT NOT NULL REFERENCES agent.graph_versions(id) ON DELETE RESTRICT,
    trigger_type TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    run_status TEXT NOT NULL DEFAULT 'queued'
        CHECK (run_status IN ('queued','running','waiting_approval','waiting_input','paused','completed','failed','cancelled')),
    idempotency_key TEXT,
    correlation_key TEXT,
    subject_type TEXT,
    subject_ref TEXT,
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    working_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    pending_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_runs_idempotency
    ON agent.graph_runs(idempotency_key)
    WHERE idempotency_key IS NOT NULL AND idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_graph_runs_status ON agent.graph_runs(run_status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_runs_graph ON agent.graph_runs(graph_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_runs_subject ON agent.graph_runs(subject_type, subject_ref);

CREATE TABLE IF NOT EXISTS agent.graph_node_runs (
    id BIGSERIAL PRIMARY KEY,
    graph_run_id BIGINT NOT NULL REFERENCES agent.graph_runs(id) ON DELETE CASCADE,
    graph_node_id BIGINT NOT NULL REFERENCES agent.graph_nodes(id) ON DELETE RESTRICT,
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 50),
    status TEXT NOT NULL DEFAULT 'blocked'
        CHECK (status IN ('blocked','ready','queued','running','waiting_approval','waiting_input','completed','skipped','failed','cancelled')),
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    worker_run_id BIGINT REFERENCES agent.worker_runs(id) ON DELETE SET NULL,
    message_id BIGINT REFERENCES agent.agent_messages(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    error JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (graph_run_id, graph_node_id, attempt)
);

CREATE INDEX IF NOT EXISTS idx_graph_node_runs_status ON agent.graph_node_runs(graph_run_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_graph_node_runs_task ON agent.graph_node_runs(task_id) WHERE task_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS agent.graph_edge_runs (
    id BIGSERIAL PRIMARY KEY,
    graph_run_id BIGINT NOT NULL REFERENCES agent.graph_runs(id) ON DELETE CASCADE,
    graph_edge_id BIGINT NOT NULL REFERENCES agent.graph_edges(id) ON DELETE RESTRICT,
    source_node_run_id BIGINT NOT NULL REFERENCES agent.graph_node_runs(id) ON DELETE CASCADE,
    target_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    traversal INTEGER NOT NULL DEFAULT 1 CHECK (traversal BETWEEN 1 AND 50),
    condition_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'traversed'
        CHECK (status IN ('traversed','suppressed','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (graph_run_id, graph_edge_id, source_node_run_id)
);

CREATE INDEX IF NOT EXISTS idx_graph_edge_runs_target
    ON agent.graph_edge_runs(graph_run_id, target_node_run_id, created_at);

CREATE TABLE IF NOT EXISTS agent.graph_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    graph_run_id BIGINT NOT NULL REFERENCES agent.graph_runs(id) ON DELETE CASCADE,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    checkpoint_kind TEXT NOT NULL DEFAULT 'durable',
    resume_token TEXT NOT NULL UNIQUE DEFAULT md5(random()::TEXT || clock_timestamp()::TEXT),
    state_snapshot JSONB NOT NULL,
    evidence_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.graph_events (
    id BIGSERIAL PRIMARY KEY,
    graph_run_id BIGINT NOT NULL REFERENCES agent.graph_runs(id) ON DELETE CASCADE,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info'
        CHECK (severity IN ('debug','info','warning','risk','error')),
    actor TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_graph_events_run ON agent.graph_events(graph_run_id, occurred_at, id);

CREATE TABLE IF NOT EXISTS agent.graph_change_requests (
    id BIGSERIAL PRIMARY KEY,
    graph_key TEXT NOT NULL REFERENCES agent.graph_definitions(graph_key) ON DELETE RESTRICT,
    base_version_id BIGINT REFERENCES agent.graph_versions(id) ON DELETE SET NULL,
    requested_by TEXT NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    proposed_patch JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_impact JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','needs_revision','approved','rejected','applied','cancelled')),
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    review_notes TEXT,
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    applied_version_id BIGINT REFERENCES agent.graph_versions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.autonomy_policies (
    id BIGSERIAL PRIMARY KEY,
    policy_key TEXT NOT NULL UNIQUE,
    policy_name TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    task_class TEXT NOT NULL DEFAULT '*',
    autonomy_level TEXT NOT NULL
        CHECK (autonomy_level IN ('observe_only','draft_only','bounded_autonomous','human_approval','prohibited')),
    allowed_actions TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    prohibited_actions TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    approval_threshold JSONB NOT NULL DEFAULT '{}'::jsonb,
    max_cost_inr NUMERIC NOT NULL DEFAULT 0 CHECK (max_cost_inr >= 0),
    max_runtime_seconds INTEGER NOT NULL DEFAULT 900 CHECK (max_runtime_seconds BETWEEN 1 AND 86400),
    evidence_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','paused','retired')),
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    effective_until TIMESTAMPTZ,
    created_by TEXT NOT NULL DEFAULT 'Charlie Munger',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope_type, scope_key, task_class)
);

CREATE TABLE IF NOT EXISTS agent.autonomy_evidence (
    id BIGSERIAL PRIMARY KEY,
    policy_id BIGINT REFERENCES agent.autonomy_policies(id) ON DELETE SET NULL,
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE SET NULL,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    action_class TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow','requires_approval','deny')),
    rationale TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    decided_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.correction_ledger (
    id BIGSERIAL PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE SET NULL,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    correction_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low','medium','high','critical')),
    expected_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    root_cause TEXT,
    corrective_action TEXT NOT NULL,
    prevention_change JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','in_progress','verification','verified','rejected','closed')),
    owner_agent TEXT NOT NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    change_request_id BIGINT REFERENCES agent.graph_change_requests(id) ON DELETE SET NULL,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.waiting_on_principal (
    id BIGSERIAL PRIMARY KEY,
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE CASCADE,
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE CASCADE,
    request_type TEXT NOT NULL
        CHECK (request_type IN ('approval','decision','input','clarification','credential','source_document')),
    title TEXT NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]'::jsonb,
    default_action TEXT,
    due_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','answered','approved','rejected','expired','cancelled')),
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    requested_by TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    resolution JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_waiting_on_principal_open
    ON agent.waiting_on_principal(status, due_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_correction_ledger_open
    ON agent.correction_ledger(status, severity, updated_at DESC);

CREATE OR REPLACE FUNCTION agent.validate_graph_version(p_graph_version_id BIGINT)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_count INTEGER;
    v_end_count INTEGER;
    v_node_count INTEGER;
    v_edge_count INTEGER;
    v_unreachable_count INTEGER;
    v_unbounded_loop_count INTEGER;
    v_invalid_approval_count INTEGER;
    v_valid BOOLEAN;
    v_result JSONB;
BEGIN
    SELECT count(*)::INTEGER,
           count(*) FILTER (WHERE node_type='start')::INTEGER,
           count(*) FILTER (WHERE node_type='end')::INTEGER,
           count(*) FILTER (WHERE node_type='approval_gate' AND approval_required=false)::INTEGER
    INTO v_node_count, v_start_count, v_end_count, v_invalid_approval_count
    FROM agent.graph_nodes
    WHERE graph_version_id=p_graph_version_id;

    SELECT count(*)::INTEGER,
           count(*) FILTER (
               WHERE edge_kind='loop'
                 AND coalesce((condition->>'max_iterations')::INTEGER, 0) NOT BETWEEN 1 AND 50
           )::INTEGER
    INTO v_edge_count, v_unbounded_loop_count
    FROM agent.graph_edges
    WHERE graph_version_id=p_graph_version_id AND enabled=true;

    WITH RECURSIVE reachable(node_key) AS (
        SELECT node_key
        FROM agent.graph_nodes
        WHERE graph_version_id=p_graph_version_id AND node_type='start'
        UNION
        SELECT edge.to_node_key
        FROM reachable walk
        JOIN agent.graph_edges edge
          ON edge.graph_version_id=p_graph_version_id
         AND edge.from_node_key=walk.node_key
         AND edge.enabled=true
    )
    SELECT count(*)::INTEGER
    INTO v_unreachable_count
    FROM agent.graph_nodes node
    WHERE node.graph_version_id=p_graph_version_id
      AND NOT EXISTS (SELECT 1 FROM reachable WHERE reachable.node_key=node.node_key);

    v_valid := v_node_count > 1
        AND v_start_count = 1
        AND v_end_count >= 1
        AND v_edge_count >= 1
        AND v_unreachable_count = 0
        AND v_unbounded_loop_count = 0
        AND v_invalid_approval_count = 0;

    v_result := jsonb_build_object(
        'valid', v_valid,
        'node_count', v_node_count,
        'edge_count', v_edge_count,
        'start_count', v_start_count,
        'end_count', v_end_count,
        'unreachable_node_count', v_unreachable_count,
        'unbounded_loop_count', v_unbounded_loop_count,
        'invalid_approval_gate_count', v_invalid_approval_count,
        'validated_at', now()
    );

    UPDATE agent.graph_versions
    SET validation_result=v_result,
        status=CASE WHEN v_valid AND status='draft' THEN 'validated' ELSE status END
    WHERE id=p_graph_version_id;
    RETURN v_result;
END;
$$;

CREATE OR REPLACE VIEW agent.v_graph_catalog AS
WITH version_stats AS (
    SELECT version.graph_key,version.id AS graph_version_id,version.version,
           version.status AS version_status,version.definition_hash,
           version.validation_result,
           count(DISTINCT node.id)::INTEGER AS node_count,
           count(DISTINCT edge.id)::INTEGER AS edge_count
    FROM agent.graph_versions version
    LEFT JOIN agent.graph_nodes node ON node.graph_version_id=version.id
    LEFT JOIN agent.graph_edges edge ON edge.graph_version_id=version.id AND edge.enabled=true
    GROUP BY version.graph_key,version.id,version.version,version.status,
             version.definition_hash,version.validation_result
), run_stats AS (
    SELECT graph_key,count(*)::INTEGER AS run_count,
           count(*) FILTER (WHERE run_status IN ('queued','running','waiting_approval','waiting_input','paused'))::INTEGER AS open_run_count,
           count(*) FILTER (WHERE run_status='completed')::INTEGER AS completed_run_count,
           count(*) FILTER (WHERE run_status='failed')::INTEGER AS failed_run_count,
           max(updated_at) AS latest_run_at
    FROM agent.graph_runs GROUP BY graph_key
)
SELECT definition.graph_key,definition.graph_name,definition.graph_family,
       definition.description,definition.owner_agent,definition.status,
       definition.active_version,definition.trigger_type,
       definition.default_autonomy_level,definition.input_contract,
       definition.output_contract,definition.safety_policy,definition.tags,
       stats.graph_version_id,stats.version_status,stats.definition_hash,
       stats.validation_result,coalesce(stats.node_count,0) AS node_count,
       coalesce(stats.edge_count,0) AS edge_count,
       coalesce(runs.run_count,0) AS run_count,
       coalesce(runs.open_run_count,0) AS open_run_count,
       coalesce(runs.completed_run_count,0) AS completed_run_count,
       coalesce(runs.failed_run_count,0) AS failed_run_count,
       runs.latest_run_at,definition.updated_at
FROM agent.graph_definitions definition
LEFT JOIN version_stats stats
  ON stats.graph_key=definition.graph_key AND stats.version=definition.active_version
LEFT JOIN run_stats runs ON runs.graph_key=definition.graph_key;

CREATE OR REPLACE VIEW agent.v_graph_run_status AS
SELECT run.id AS graph_run_id,run.graph_key,definition.graph_name,run.graph_version_id,
       version.version,run.trigger_type,run.triggered_by,run.run_status,
       run.correlation_key,run.subject_type,run.subject_ref,run.input_payload,
       run.working_state,run.output_payload,run.pending_decision,run.failure,
       count(node_run.id)::INTEGER AS node_run_count,
       count(node_run.id) FILTER (WHERE node_run.status='completed')::INTEGER AS completed_node_count,
       count(node_run.id) FILTER (WHERE node_run.status IN ('ready','queued','running'))::INTEGER AS active_node_count,
       count(node_run.id) FILTER (WHERE node_run.status IN ('waiting_approval','waiting_input'))::INTEGER AS waiting_node_count,
       count(node_run.id) FILTER (WHERE node_run.status='failed')::INTEGER AS failed_node_count,
       coalesce(jsonb_agg(jsonb_build_object(
           'node_run_id',node_run.id,'node_key',node.node_key,'node_name',node.node_name,
           'node_type',node.node_type,'owner_agent',node.owner_agent,'skill_key',node.skill_key,
           'attempt',node_run.attempt,'status',node_run.status,'task_id',node_run.task_id,
           'approval_id',node_run.approval_id,'updated_at',node_run.updated_at
       ) ORDER BY node_run.created_at,node_run.id) FILTER (WHERE node_run.id IS NOT NULL), '[]'::jsonb) AS nodes,
       run.started_at,run.finished_at,run.created_at,run.updated_at
FROM agent.graph_runs run
JOIN agent.graph_definitions definition ON definition.graph_key=run.graph_key
JOIN agent.graph_versions version ON version.id=run.graph_version_id
LEFT JOIN agent.graph_node_runs node_run ON node_run.graph_run_id=run.id
LEFT JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
GROUP BY run.id,definition.graph_name,version.version;

CREATE OR REPLACE VIEW agent.v_graph_node_run_detail AS
SELECT node_run.id AS graph_node_run_id,node_run.graph_run_id,run.graph_key,
       node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node_run.attempt,node_run.status,node_run.task_id,
       task.title AS task_title,task.status AS task_status,task.output_note_path,
       node_run.worker_run_id,worker.status AS worker_status,worker.output_summary,
       node_run.message_id,node_run.approval_id,approval.status AS approval_status,
       node_run.input_payload,node_run.output_payload,node_run.evidence,node_run.error,
       node_run.started_at,node_run.finished_at,node_run.created_at,node_run.updated_at
FROM agent.graph_node_runs node_run
JOIN agent.graph_runs run ON run.id=node_run.graph_run_id
JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
LEFT JOIN agent.tasks task ON task.id=node_run.task_id
LEFT JOIN agent.worker_runs worker ON worker.id=node_run.worker_run_id
LEFT JOIN agent.approvals approval ON approval.id=node_run.approval_id;

CREATE OR REPLACE VIEW agent.v_graph_edge_run_detail AS
SELECT edge_run.id AS graph_edge_run_id,edge_run.graph_run_id,
       edge_run.graph_edge_id,edge.from_node_key,edge.to_node_key,
       edge.edge_kind,edge.condition_type,edge.condition,edge.label,
       edge_run.source_node_run_id,edge_run.target_node_run_id,
       edge_run.traversal,edge_run.condition_result,edge_run.status,
       edge_run.created_at
FROM agent.graph_edge_runs edge_run
JOIN agent.graph_edges edge ON edge.id=edge_run.graph_edge_id;

CREATE OR REPLACE VIEW agent.v_autonomy_control_board AS
SELECT policy.policy_key,policy.policy_name,policy.scope_type,policy.scope_key,
       policy.task_class,policy.autonomy_level,policy.allowed_actions,
       policy.prohibited_actions,policy.approval_threshold,policy.max_cost_inr,
       policy.max_runtime_seconds,policy.evidence_requirements,policy.guardrails,
       policy.status,policy.effective_from,policy.effective_until,
       coalesce(decisions.total_decisions,0) AS total_decisions,
       coalesce(decisions.allowed_decisions,0) AS allowed_decisions,
       coalesce(decisions.approval_decisions,0) AS approval_decisions,
       coalesce(decisions.denied_decisions,0) AS denied_decisions,
       decisions.latest_decision_at,policy.updated_at
FROM agent.autonomy_policies policy
LEFT JOIN LATERAL (
    SELECT count(*)::INTEGER AS total_decisions,
           count(*) FILTER (WHERE decision='allow')::INTEGER AS allowed_decisions,
           count(*) FILTER (WHERE decision='requires_approval')::INTEGER AS approval_decisions,
           count(*) FILTER (WHERE decision='deny')::INTEGER AS denied_decisions,
           max(created_at) AS latest_decision_at
    FROM agent.autonomy_evidence evidence WHERE evidence.policy_id=policy.id
) decisions ON true;

CREATE OR REPLACE VIEW agent.v_graph_attention_queue AS
SELECT 'principal_request'::TEXT AS attention_kind,wait.id,wait.graph_run_id,
       wait.graph_node_run_id,wait.request_type AS category,wait.title,
       wait.question AS detail,wait.status,wait.requested_by AS owner_agent,
       wait.due_at,wait.created_at,wait.updated_at,
       jsonb_build_object('options',wait.options,'default_action',wait.default_action,
                          'approval_id',wait.approval_id) AS context
FROM agent.waiting_on_principal wait WHERE wait.status='open'
UNION ALL
SELECT 'correction'::TEXT,correction.id,correction.graph_run_id,
       correction.graph_node_run_id,correction.correction_type,correction.corrective_action,
       coalesce(correction.root_cause,'Root cause pending'),correction.status,
       correction.owner_agent,NULL::TIMESTAMPTZ,correction.created_at,correction.updated_at,
       jsonb_build_object('severity',correction.severity,'source_kind',correction.source_kind,
                          'source_ref',correction.source_ref,'task_id',correction.task_id,
                          'change_request_id',correction.change_request_id)
FROM agent.correction_ledger correction
WHERE correction.status IN ('open','in_progress','verification');

-- Graph runtime, model-risk, and correction skills extend existing employees;
-- they do not create duplicate agent identities.
INSERT INTO agent.skills (
    skill_key,skill_name,skill_family,skill_type,owner_department,status,
    execution_mode,permission_level,trigger_phrases,input_sources,output_targets,
    required_tools,risk_notes,prompt_template,config
)
VALUES
    ('graph_runtime_orchestration','Graph Runtime Orchestration','runtime','orchestration','runtime','active','internal_workflow','write_with_approval',ARRAY['run workflow','advance graph','resume workflow'],ARRAY['agent.graph_definitions','agent.graph_runs'],ARRAY['agent.graph_node_runs','agent.graph_events','agent.graph_checkpoints'],ARRAY['ai_os_graph_control_snapshot'],'May create governed tasks and checkpoints only. It cannot execute arbitrary code or broker orders.','Advance only validated graph versions. Stop at approval, missing evidence, prohibited action, or failed safety condition.','{"live_execution_allowed":false,"arbitrary_code_allowed":false,"checkpoint_required":true}'::jsonb),
    ('graph_change_review','Graph Change Review','runtime','governance','software','active','human_gated','write_with_approval',ARRAY['change workflow','adapt workflow','edit graph'],ARRAY['agent.graph_change_requests','agent.correction_ledger'],ARRAY['agent.graph_versions','agent.approvals'],ARRAY['ai_os_graph_control_snapshot'],'Material graph changes require review, validation, versioning, rollback data, and human approval.','Review the proposed declarative patch, safety impact, regression evidence, and rollback path before activation.','{"human_approval_required":true,"direct_active_version_mutation":false}'::jsonb),
    ('graph_correction_review','Outcome Correction Review','runtime','governance','risk','active','deterministic_tools_then_local_model','write_with_approval',ARRAY['correct outcome','why did this fail','record lesson'],ARRAY['agent.graph_runs','agent.worker_runs','agent.correction_ledger'],ARRAY['agent.correction_ledger','agent.graph_change_requests','agent.tasks'],ARRAY['ai_os_graph_control_snapshot'],'Observed outcomes never overwrite historical evidence. Corrections are append-only and verified separately.','Compare expected and observed state, identify the evidence-backed root cause, and propose the smallest reversible prevention change.','{"append_only_history":true,"independent_verification":true}'::jsonb),
    ('kronos_forecast_feature_generation','Kronos Forecast Feature Generation','quant','forecasting','quant','active','optional_model_adapter','write_with_approval',ARRAY['kronos forecast','ohlcv forecast paths','forecast features'],ARRAY['trading.ohlcv'],ARRAY['strategy.kronos_forecast_runs','strategy.kronos_forecast_paths','strategy.kronos_forecast_scores'],ARRAY['kronos_inference_adapter'],'Research-only stochastic OHLCV paths. Point-in-time data, exact model revision, costs, calibration, and independent validation are mandatory.','Generate forecast distributions and derived features only from the supplied point-in-time OHLCV window. Never turn a raw forecast into an order.','{"research_only":true,"minimum_paths":20,"model_revision_required":true,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name,skill_family=EXCLUDED.skill_family,
    skill_type=EXCLUDED.skill_type,owner_department=EXCLUDED.owner_department,
    status=EXCLUDED.status,execution_mode=EXCLUDED.execution_mode,
    permission_level=EXCLUDED.permission_level,trigger_phrases=EXCLUDED.trigger_phrases,
    input_sources=EXCLUDED.input_sources,output_targets=EXCLUDED.output_targets,
    required_tools=EXCLUDED.required_tools,risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template,config=EXCLUDED.config,updated_at=now();

INSERT INTO agent.agent_skill_map (agent_name,skill_key,proficiency,is_primary,activation_rules)
SELECT mapping.agent_name,mapping.skill_key,mapping.proficiency,mapping.is_primary,mapping.activation_rules
FROM (VALUES
    ('Jarvis','graph_runtime_orchestration','expert',true,'{"activate_on":["graph_run","checkpoint","resume"]}'::jsonb),
    ('AI Runtime Engineer','graph_runtime_orchestration','expert',true,'{"activate_on":["runtime_failure","graph_validation"]}'::jsonb),
    ('CTO Agent','graph_change_review','expert',true,'{"activate_on":["graph_change_request"]}'::jsonb),
    ('Risk Agent','graph_change_review','expert',false,'{"activate_on":["safety_impact"]}'::jsonb),
    ('Model Risk Agent','graph_correction_review','expert',true,'{"activate_on":["forecast_error","model_error"]}'::jsonb),
    ('Data Quality Risk Agent','graph_correction_review','expert',false,'{"activate_on":["data_error"]}'::jsonb),
    ('Feature Engineer','kronos_forecast_feature_generation','working',true,'{"activate_on":["approved_research_forecast"]}'::jsonb),
    ('Model Validation Agent','kronos_forecast_feature_generation','working',false,'{"activate_on":["forecast_validation"]}'::jsonb)
) AS mapping(agent_name,skill_key,proficiency,is_primary,activation_rules)
JOIN agent.profiles profile ON profile.agent_name=mapping.agent_name AND profile.status='active'
ON CONFLICT (agent_name,skill_key) DO UPDATE SET
    proficiency=EXCLUDED.proficiency,is_primary=EXCLUDED.is_primary,
    activation_rules=EXCLUDED.activation_rules,updated_at=now();

INSERT INTO agent.autonomy_policies (
    policy_key,policy_name,scope_type,scope_key,task_class,autonomy_level,
    allowed_actions,prohibited_actions,approval_threshold,max_cost_inr,
    max_runtime_seconds,evidence_requirements,guardrails,created_by
)
VALUES
    ('global_default_draft','Global Default Draft Policy','system','*','*','draft_only',ARRAY['read_verified_data','draft_analysis','create_review_task','write_internal_note'],ARRAY['live_broker_order','external_message','capital_change','delete_source_evidence'], '{}',0,900,'{"source_lineage_required":true}'::jsonb,'{"seed_data_allowed":false,"broker_writes":false}'::jsonb,'Charlie Munger'),
    ('public_research_bounded','Public Research Bounded Autonomy','data_class','public','research','bounded_autonomous',ARRAY['collect_public_source','extract_document','classify','draft_hypothesis','create_internal_task'],ARRAY['trade_recommendation','external_publish','capital_change'], '{}',25,1800,'{"source_url_required":true,"retrieved_at_required":true}'::jsonb,'{"prompt_injection_treated_as_data":true}'::jsonb,'Research Director'),
    ('internal_reversible_ops','Internal Reversible Operations','task_class','internal_ops','runtime','bounded_autonomous',ARRAY['create_task','update_task_state','checkpoint','retry_bounded','refresh_read_model'],ARRAY['delete_evidence','change_active_graph','cloud_spend_unapproved'], '{"max_retries":3}',0,1800,'{"audit_event_required":true}'::jsonb,'{"reversible_only":true}'::jsonb,'Jarvis'),
    ('client_private_review','Client Private Data Policy','data_class','client_private','*','human_approval',ARRAY['read_scoped_private_data','draft_private_analysis','create_internal_task'],ARRAY['cloud_route','cross_client_mix','external_send','capital_change'], '{"human_review":true}',0,900,'{"client_scope_required":true}'::jsonb,'{"local_only":true,"cross_client_isolation":true}'::jsonb,'Portfolio Manager'),
    ('paid_cloud_gate','Paid Cloud Model Gate','task_class','cloud_model','*','human_approval',ARRAY['prepare_redacted_prompt','estimate_cost','request_approval'],ARRAY['autonomous_cloud_call','send_client_private_data'], '{"explicit_route_selection":true,"daily_budget_required":true}',0,1800,'{"privacy_classification_required":true,"cost_estimate_required":true}'::jsonb,'{"zero_autonomous_cloud_budget":true}'::jsonb,'AI Runtime Engineer'),
    ('capital_action_gate','Capital Action Gate','task_class','capital_action','*','human_approval',ARRAY['draft_proposal','run_risk_checks','request_committee_review'],ARRAY['autonomous_rebalance','autonomous_order','silent_netting'], '{"human_decision":true,"risk_approval":true}',0,1800,'{"portfolio_context_required":true,"risk_evidence_required":true}'::jsonb,'{"separate_books":true,"opposing_exposure_flag":true}'::jsonb,'Capital Allocation Agent'),
    ('external_communication_gate','External Communication Gate','task_class','external_communication','*','human_approval',ARRAY['draft_message','request_approval'],ARRAY['send_email','send_client_report','post_social','contact_broker'], '{"named_approver":true}',0,900,'{"final_payload_hash_required":true}'::jsonb,'{"approved_channel_required":true}'::jsonb,'Compliance Agent'),
    ('broker_execution_prohibited','Broker Execution Default Prohibition','task_class','broker_execution','*','prohibited',ARRAY['draft_order_intent','run_pretrade_risk'],ARRAY['place_order','modify_order','cancel_order','authenticate_without_user'], '{"separate_future_policy_required":true}',0,300,'{"fresh_tick_required":true,"human_order_approval_required":true}'::jsonb,'{"global_execution_locked":true,"live_broker_writes_allowed":false}'::jsonb,'Execution Safety Agent')
ON CONFLICT (policy_key) DO UPDATE SET
    policy_name=EXCLUDED.policy_name,scope_type=EXCLUDED.scope_type,
    scope_key=EXCLUDED.scope_key,task_class=EXCLUDED.task_class,
    autonomy_level=EXCLUDED.autonomy_level,allowed_actions=EXCLUDED.allowed_actions,
    prohibited_actions=EXCLUDED.prohibited_actions,
    approval_threshold=EXCLUDED.approval_threshold,max_cost_inr=EXCLUDED.max_cost_inr,
    max_runtime_seconds=EXCLUDED.max_runtime_seconds,
    evidence_requirements=EXCLUDED.evidence_requirements,guardrails=EXCLUDED.guardrails,
    status='active',updated_at=now();

INSERT INTO agent.graph_definitions (
    graph_key,graph_name,graph_family,description,owner_agent,status,active_version,
    trigger_type,default_autonomy_level,input_contract,output_contract,safety_policy,tags
)
VALUES
    ('daily_office_intelligence','Daily Office Intelligence Loop','executive_operations','Parallel source, portfolio, filing, and risk review culminating in an evidence-bound Charlie brief.','Charlie Munger','active',1,'scheduled_or_manual','bounded_autonomous','{"optional":["as_of","focus_symbols"]}'::jsonb,'{"required":["brief_task","checkpoint"]}'::jsonb,'{"broker_writes":false,"client_private_local_only":true,"approval_for_capital_action":true}'::jsonb,ARRAY['daily','brief','parallel']),
    ('research_to_investment_decision','Research To Investment Decision','fundamental_research','Source intake, specialist challenge, independent risk, committee deliberation, human decision, and durable writeback.','Research Director','active',1,'manual_or_event','draft_only','{"required":["subject"],"optional":["symbol","source_ids","objective"]}'::jsonb,'{"required":["committee_packet","decision_state","research_note"]}'::jsonb,'{"source_required":true,"human_capital_decision":true,"broker_writes":false}'::jsonb,ARRAY['research','committee','human_gate']),
    ('strategy_research_lifecycle','Strategy Research Lifecycle','quant_research','Point-in-time data, feature review, backtest, validation, regimes, capacity, independent risk, committee, and paper-first promotion.','Head of Quant','active',1,'manual_or_research','draft_only','{"required":["hypothesis"],"optional":["symbols","timeframe","cost_model"]}'::jsonb,'{"required":["validation_state","committee_state","promotion_state"]}'::jsonb,'{"point_in_time_only":true,"paper_first":true,"live_execution":false,"human_promotion_gate":true}'::jsonb,ARRAY['quant','backtest','validation','paper_first']),
    ('kronos_forecast_research','Kronos Forecast Research','quant_model_research','Research-only OHLCV forecast distributions converted into validated features, never direct orders.','Feature Engineer','active',1,'manual_research','draft_only','{"required":["symbol","exchange","timeframe","as_of","lookback","horizon","path_count","model_revision"]}'::jsonb,'{"required":["forecast_run","calibration","validation"]}'::jsonb,'{"point_in_time_only":true,"minimum_paths":20,"missing_volume_rejected":true,"model_revision_pinned":true,"broker_writes":false}'::jsonb,ARRAY['kronos','forecast','model_risk','research_only'])
ON CONFLICT (graph_key) DO UPDATE SET
    graph_name=EXCLUDED.graph_name,graph_family=EXCLUDED.graph_family,
    description=EXCLUDED.description,owner_agent=EXCLUDED.owner_agent,
    status=EXCLUDED.status,active_version=EXCLUDED.active_version,
    trigger_type=EXCLUDED.trigger_type,
    default_autonomy_level=EXCLUDED.default_autonomy_level,
    input_contract=EXCLUDED.input_contract,output_contract=EXCLUDED.output_contract,
    safety_policy=EXCLUDED.safety_policy,tags=EXCLUDED.tags,updated_at=now();

INSERT INTO agent.graph_versions (
    graph_key,version,status,change_summary,source_kind,source_ref,created_by,approved_by,approved_at
)
VALUES
    ('daily_office_intelligence',1,'draft','Initial graph-native daily intelligence loop.','institutional_blueprint','graph_control_plane_v1','CTO Agent','Devarsh',now()),
    ('research_to_investment_decision',1,'draft','Initial source-to-human-decision research factory.','institutional_blueprint','graph_control_plane_v1','CTO Agent','Devarsh',now()),
    ('strategy_research_lifecycle',1,'draft','Initial point-in-time, paper-first quant lifecycle.','institutional_blueprint','graph_control_plane_v1','CTO Agent','Devarsh',now()),
    ('kronos_forecast_research',1,'draft','Initial research-only Kronos feature validation lifecycle.','kronos_review','Kronos@67b630e','CTO Agent','Devarsh',now())
ON CONFLICT (graph_key,version) DO UPDATE SET
    change_summary=EXCLUDED.change_summary,source_kind=EXCLUDED.source_kind,
    source_ref=EXCLUDED.source_ref,created_by=EXCLUDED.created_by;

-- Daily Office graph.
INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,
    autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position
)
SELECT version.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node.on_error,node.ui_position
FROM agent.graph_versions version
JOIN (VALUES
    ('start','Start daily cycle','start','Jarvis',NULL::TEXT,'bounded_autonomous',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":0}'::jsonb),
    ('source_health','Verify source freshness','agent_task','Data Quality Analyst','source_data_ingestion_review','bounded_autonomous',false,2,600,'{"priority":"high"}'::jsonb,'pause','{"x":-420,"y":140}'::jsonb),
    ('filings_news','Collect filings and news evidence','agent_task','News Analyst','nse_bse_announcement_monitor','bounded_autonomous',false,2,1200,'{"public_sources_only":true}'::jsonb,'pause','{"x":-140,"y":140}'::jsonb),
    ('portfolio_review','Review portfolios and books','agent_task','Portfolio Manager','portfolio_daily_brief','draft_only',false,1,900,'{"client_private":true,"local_only":true}'::jsonb,'request_human','{"x":140,"y":140}'::jsonb),
    ('risk_review','Run independent risk review','agent_task','Risk Agent','portfolio_concentration_check','bounded_autonomous',false,1,900,'{"independent":true}'::jsonb,'pause','{"x":420,"y":140}'::jsonb),
    ('evidence_join','Join verified evidence','join','Jarvis',NULL::TEXT,'bounded_autonomous',false,0,60,'{"join":"all_success"}'::jsonb,'pause','{"x":0,"y":300}'::jsonb),
    ('charlie_brief','Prepare Charlie brief','agent_task','Charlie Munger','daily_office_brief','draft_only',false,1,900,'{"must_cover":["portfolio","risk","approvals","filings","news","source_gaps"]}'::jsonb,'request_human','{"x":0,"y":440}'::jsonb),
    ('checkpoint','Persist daily checkpoint','checkpoint','Jarvis',NULL::TEXT,'bounded_autonomous',false,0,60,'{"checkpoint_kind":"daily_intelligence"}'::jsonb,'fail','{"x":0,"y":580}'::jsonb),
    ('end','Daily cycle complete','end','Charlie Munger',NULL::TEXT,'observe_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":700}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position)
ON version.graph_key='daily_office_intelligence' AND version.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key,autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
    timeout_seconds=EXCLUDED.timeout_seconds,configuration=EXCLUDED.configuration,
    on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,label)
SELECT version.id,edge.from_key,edge.to_key,'success','always','{}'::jsonb,edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('start','source_health',10,'Source controls'),('start','filings_news',20,'Filings and news'),
    ('start','portfolio_review',30,'Portfolio'),('start','risk_review',40,'Risk'),
    ('source_health','evidence_join',10,'Verified'),('filings_news','evidence_join',20,'Curated'),
    ('portfolio_review','evidence_join',30,'Reviewed'),('risk_review','evidence_join',40,'Challenged'),
    ('evidence_join','charlie_brief',10,'Synthesize'),('charlie_brief','checkpoint',10,'Persist'),
    ('checkpoint','end',10,'Complete')
) AS edge(from_key,to_key,priority,label)
ON version.graph_key='daily_office_intelligence' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

-- Fundamental research graph.
INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,
    autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position
)
SELECT version.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node.on_error,node.ui_position
FROM agent.graph_versions version
JOIN (VALUES
    ('start','Open research case','start','Research Director',NULL::TEXT,'draft_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":0}'::jsonb),
    ('evidence_intake','Curate source evidence','agent_task','Research Librarian','research_evidence_curation','bounded_autonomous',false,2,1800,'{"source_tiers_required":true}'::jsonb,'request_human','{"x":0,"y":120}'::jsonb),
    ('business_review','Business and moat review','agent_task','Research Analyst','company_research_note','draft_only',false,1,1800,'{}'::jsonb,'pause','{"x":-420,"y":280}'::jsonb),
    ('filings_review','Filings and governance review','agent_task','Filings Analyst','analyze_corporate_filing','draft_only',false,1,1800,'{}'::jsonb,'pause','{"x":-140,"y":280}'::jsonb),
    ('bear_case','Independent bear case','agent_task','Devils Advocate Agent','long_term_bear_case_review','draft_only',false,1,1800,'{}'::jsonb,'pause','{"x":140,"y":280}'::jsonb),
    ('valuation','Valuation review','agent_task','Valuation Analyst','long_term_valuation_review','draft_only',false,1,1800,'{"deterministic_calculation_required":true}'::jsonb,'pause','{"x":420,"y":280}'::jsonb),
    ('specialist_join','Join specialist evidence','join','Research Director',NULL::TEXT,'bounded_autonomous',false,0,60,'{"join":"all_success"}'::jsonb,'pause','{"x":0,"y":440}'::jsonb),
    ('risk_challenge','Independent portfolio and risk challenge','agent_task','Risk Agent','risk_gate_review','draft_only',false,1,1200,'{"independent":true}'::jsonb,'pause','{"x":0,"y":560}'::jsonb),
    ('committee','Investment committee deliberation','committee','Charlie Munger','tradingagents_checkpointed_committee','draft_only',false,1,1800,'{"bull_bear_required":true,"human_final_decision":true}'::jsonb,'request_human','{"x":0,"y":680}'::jsonb),
    ('human_decision','Human investment decision','approval_gate','Charlie Munger',NULL::TEXT,'human_approval',true,0,86400,'{"approval_type":"investment_decision","capital_action_allowed":false}'::jsonb,'request_human','{"x":0,"y":800}'::jsonb),
    ('writeback','Write durable research decision','agent_task','Librarian Agent','write_obsidian_note','bounded_autonomous',false,1,900,'{"append_decision_record":true}'::jsonb,'pause','{"x":0,"y":920}'::jsonb),
    ('end','Research case complete','end','Research Director',NULL::TEXT,'observe_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":1040}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position)
ON version.graph_key='research_to_investment_decision' AND version.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key,autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
    timeout_seconds=EXCLUDED.timeout_seconds,configuration=EXCLUDED.configuration,
    on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,label)
SELECT version.id,edge.from_key,edge.to_key,'success','always','{}'::jsonb,edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('start','evidence_intake',10,'Open'),('evidence_intake','business_review',10,'Business'),
    ('evidence_intake','filings_review',20,'Filings'),('evidence_intake','bear_case',30,'Challenge'),
    ('evidence_intake','valuation',40,'Valuation'),('business_review','specialist_join',10,'Business evidence'),
    ('filings_review','specialist_join',20,'Filing evidence'),('bear_case','specialist_join',30,'Bear evidence'),
    ('valuation','specialist_join',40,'Valuation evidence'),('specialist_join','risk_challenge',10,'Risk'),
    ('risk_challenge','committee',10,'Deliberate'),('committee','human_decision',10,'Decide'),
    ('human_decision','writeback',10,'Record'),('writeback','end',10,'Complete')
) AS edge(from_key,to_key,priority,label)
ON version.graph_key='research_to_investment_decision' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

-- Quant strategy lifecycle graph.
INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,
    autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position
)
SELECT version.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node.on_error,node.ui_position
FROM agent.graph_versions version
JOIN (VALUES
    ('start','Open strategy research','start','Head of Quant',NULL::TEXT,'draft_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":0}'::jsonb),
    ('hypothesis','Structure falsifiable hypothesis','agent_task','Strategy Generator','generate_strategy_hypothesis','draft_only',false,1,1200,'{"falsifiable":true,"cost_aware":true}'::jsonb,'pause','{"x":0,"y":110}'::jsonb),
    ('data_contract','Verify point-in-time data contract','agent_task','Data Steward','tradingagents_verified_data_contract','bounded_autonomous',false,2,1200,'{"point_in_time":true,"lineage_required":true}'::jsonb,'request_human','{"x":0,"y":220}'::jsonb),
    ('features','Feature engineering review','agent_task','Feature Engineer','quant_feature_engineering_review','draft_only',false,1,1800,'{"no_target_leakage":true}'::jsonb,'pause','{"x":0,"y":330}'::jsonb),
    ('backtest','Transaction-cost-aware backtest','agent_task','Backtest Engineer','queue_backtest','bounded_autonomous',false,1,3600,'{"walk_forward":true,"costs_required":true}'::jsonb,'pause','{"x":0,"y":440}'::jsonb),
    ('model_validation','Independent model validation','agent_task','Model Validation Agent','validate_strategy_model','draft_only',false,1,1800,'{"independent":true}'::jsonb,'pause','{"x":-280,"y":560}'::jsonb),
    ('regime_review','Regime stability review','agent_task','Regime Analyst','quant_regime_review','draft_only',false,1,1200,'{}'::jsonb,'pause','{"x":0,"y":560}'::jsonb),
    ('capacity_review','Capacity and liquidity review','agent_task','Capacity/Liquidity Analyst','quant_capacity_liquidity_review','draft_only',false,1,1200,'{}'::jsonb,'pause','{"x":280,"y":560}'::jsonb),
    ('validation_join','Join independent reviews','join','Head of Quant',NULL::TEXT,'bounded_autonomous',false,0,60,'{"join":"all_success"}'::jsonb,'pause','{"x":0,"y":690}'::jsonb),
    ('risk_review','Independent quant risk review','agent_task','Quant Risk Analyst','quant_risk_review','draft_only',false,1,1200,'{"independent":true}'::jsonb,'pause','{"x":0,"y":800}'::jsonb),
    ('committee','Strategy committee review','committee','Strategy Committee Secretary','strategy_committee_memo','draft_only',false,1,1800,'{"paper_first":true,"memo_required":true}'::jsonb,'request_human','{"x":0,"y":910}'::jsonb),
    ('promotion_gate','Human promotion decision','approval_gate','Charlie Munger',NULL::TEXT,'human_approval',true,0,86400,'{"approval_type":"strategy_promotion","maximum_mode":"paper_monitor"}'::jsonb,'request_human','{"x":0,"y":1020}'::jsonb),
    ('paper_monitor','Start paper monitor','agent_task','Trading Desk Agent','monitor_strategy_alerts','bounded_autonomous',false,1,900,'{"paper_only":true,"live_execution":false}'::jsonb,'pause','{"x":0,"y":1130}'::jsonb),
    ('checkpoint','Persist validation checkpoint','checkpoint','Jarvis',NULL::TEXT,'bounded_autonomous',false,0,60,'{"checkpoint_kind":"strategy_promotion"}'::jsonb,'fail','{"x":0,"y":1240}'::jsonb),
    ('end','Strategy research complete','end','Head of Quant',NULL::TEXT,'observe_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":1350}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position)
ON version.graph_key='strategy_research_lifecycle' AND version.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key,autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
    timeout_seconds=EXCLUDED.timeout_seconds,configuration=EXCLUDED.configuration,
    on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,label)
SELECT version.id,edge.from_key,edge.to_key,'success','always','{}'::jsonb,edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('start','hypothesis',10,'Hypothesis'),('hypothesis','data_contract',10,'Data'),
    ('data_contract','features',10,'Features'),('features','backtest',10,'Test'),
    ('backtest','model_validation',10,'Validate'),('backtest','regime_review',20,'Regimes'),
    ('backtest','capacity_review',30,'Capacity'),('model_validation','validation_join',10,'Model evidence'),
    ('regime_review','validation_join',20,'Regime evidence'),('capacity_review','validation_join',30,'Capacity evidence'),
    ('validation_join','risk_review',10,'Risk'),('risk_review','committee',10,'Committee'),
    ('committee','promotion_gate',10,'Human gate'),
    ('paper_monitor','checkpoint',10,'Checkpoint'),('checkpoint','end',10,'Complete')
) AS edge(from_key,to_key,priority,label)
ON version.graph_key='strategy_research_lifecycle' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

INSERT INTO agent.graph_edges (
    graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,
    condition,priority,label
)
SELECT version.id,edge.from_key,edge.to_key,'conditional',edge.condition_type,
       edge.condition,edge.priority,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('promotion_gate','paper_monitor','node_output_equals',
     '{"path":"decision","equals":"paper_monitor"}'::jsonb,10,'Start paper monitor'),
    ('promotion_gate','checkpoint','node_output_not_equals',
     '{"path":"decision","equals":"paper_monitor"}'::jsonb,20,'Record non-promotion decision')
) AS edge(from_key,to_key,condition_type,condition,priority,label)
ON version.graph_key='strategy_research_lifecycle' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

-- Kronos research adapter graph. The inference node remains unavailable until
-- an exact model revision and local adapter pass the validation gate.
INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,
    autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position
)
SELECT version.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node.on_error,node.ui_position
FROM agent.graph_versions version
JOIN (VALUES
    ('start','Open forecast research','start','Feature Engineer',NULL::TEXT,'draft_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":0}'::jsonb),
    ('input_quality','Verify OHLCV and as-of lineage','agent_task','Data Quality Analyst','tradingagents_verified_data_contract','bounded_autonomous',false,1,1200,'{"required_columns":["open","high","low","close","volume"],"reject_missing_volume":true,"point_in_time":true}'::jsonb,'request_human','{"x":0,"y":130}'::jsonb),
    ('forecast_paths','Generate forecast paths and features','tool_task','Feature Engineer','kronos_forecast_feature_generation','draft_only',false,1,3600,'{"model_variant":"mini","minimum_paths":20,"persist_paths":true,"direct_signal":false,"adapter_required":true}'::jsonb,'pause','{"x":0,"y":260}'::jsonb),
    ('calibration','Score forecast calibration','agent_task','Data Scientist','quant_data_science_review','draft_only',false,1,1800,'{"metrics":["coverage","directional_accuracy","crps","interval_width","ohlc_validity"]}'::jsonb,'pause','{"x":0,"y":390}'::jsonb),
    ('backtest','Backtest derived features after costs','agent_task','Backtest Engineer','queue_backtest','bounded_autonomous',false,1,3600,'{"raw_forecast_ordering":false,"walk_forward":true,"india_cost_model":true}'::jsonb,'pause','{"x":0,"y":520}'::jsonb),
    ('model_risk','Independent forecast model review','agent_task','Model Risk Agent','model_risk_review','draft_only',false,1,1800,'{"check_revision":true,"check_leakage":true,"check_regime_stability":true}'::jsonb,'pause','{"x":0,"y":650}'::jsonb),
    ('committee','Quant committee decision','committee','Head of Quant','head_quant_governance','draft_only',false,1,1200,'{"research_feature_only":true}'::jsonb,'request_human','{"x":0,"y":780}'::jsonb),
    ('model_decision','Human model feature decision','approval_gate','Charlie Munger',NULL::TEXT,'human_approval',true,0,86400,'{"approval_type":"model_feature_decision","maximum_scope":"research_feature","decision_question":"Choose the governed disposition for this pinned Kronos forecast feature after reviewing model-risk evidence and committee dissent."}'::jsonb,'request_human','{"x":0,"y":910}'::jsonb),
    ('end','Forecast research complete','end','Head of Quant',NULL::TEXT,'observe_only',false,0,30,'{}'::jsonb,'fail','{"x":0,"y":1040}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,on_error,ui_position)
ON version.graph_key='kronos_forecast_research' AND version.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key,autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
    timeout_seconds=EXCLUDED.timeout_seconds,configuration=EXCLUDED.configuration,
    on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,label)
SELECT version.id,edge.from_key,edge.to_key,'success','always','{}'::jsonb,10,edge.label
FROM agent.graph_versions version
JOIN (VALUES
    ('start','input_quality','Validate inputs'),('input_quality','forecast_paths','Forecast'),
    ('forecast_paths','calibration','Calibrate'),('calibration','backtest','Backtest'),
    ('backtest','model_risk','Review'),('model_risk','committee','Decide'),
    ('committee','model_decision','Human decision'),('model_decision','end','Complete')
) AS edge(from_key,to_key,label)
ON version.graph_key='kronos_forecast_research' AND version.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

-- Validate and activate only internally consistent seeded versions.
DO $$
DECLARE
    version_row RECORD;
    validation JSONB;
BEGIN
    FOR version_row IN
        SELECT id,graph_key,version FROM agent.graph_versions
        WHERE graph_key IN ('daily_office_intelligence','research_to_investment_decision','strategy_research_lifecycle','kronos_forecast_research')
          AND version=1
    LOOP
        UPDATE agent.graph_versions version
        SET definition_hash=md5(coalesce((
            SELECT string_agg(
                node.node_key || ':' || node.node_type || ':' || coalesce(node.skill_key,'')
                || ':' || node.autonomy_level || ':' || node.configuration::TEXT
                || ':' || node.output_contract::TEXT,
                '|' ORDER BY node.node_key
            )
            FROM agent.graph_nodes node WHERE node.graph_version_id=version_row.id
        ),'') || '//' || coalesce((
            SELECT string_agg(
                edge.from_node_key || '>' || edge.to_node_key || ':' || edge.edge_kind
                || ':' || edge.condition_type || ':' || edge.condition::TEXT,
                '|' ORDER BY edge.from_node_key,edge.to_node_key,edge.edge_kind
            )
            FROM agent.graph_edges edge WHERE edge.graph_version_id=version_row.id AND edge.enabled=true
        ),''))
        WHERE version.id=version_row.id;

        validation := agent.validate_graph_version(version_row.id);
        IF coalesce((validation->>'valid')::BOOLEAN,false) THEN
            UPDATE agent.graph_versions SET status='active' WHERE id=version_row.id;
        END IF;
    END LOOP;
END;
$$;

INSERT INTO agent.tool_registry (
    tool_name,tool_type,owning_agent,permission_level,enabled,description,config
)
VALUES
    ('ai_os_graph_control_snapshot','api_tool','Jarvis','read_only',true,'Read validated graph definitions, versions, nodes, edges, runs, checkpoints, autonomy decisions, corrections, and principal waits.','{"reads":["agent.v_graph_catalog","agent.v_graph_run_status","agent.v_graph_node_run_detail","agent.v_autonomy_control_board","agent.v_graph_attention_queue"],"seed_data_allowed":false}'::jsonb),
    ('ai_os_start_graph_run','api_tool','Jarvis','write_scoped',true,'Start one active validated graph version with a typed input payload and idempotency key.','{"writes":["agent.graph_runs","agent.graph_node_runs","agent.graph_events"],"arbitrary_code_allowed":false,"broker_order_allowed":false}'::jsonb),
    ('ai_os_advance_graph_run','api_tool','Jarvis','write_scoped',true,'Advance a graph through immediate nodes and governed tasks until it reaches work, an approval, input, completion, or failure.','{"writes":["agent.graph_node_runs","agent.tasks","agent.inbox_items","agent.agent_messages","agent.graph_checkpoints","agent.graph_events"],"bounded_steps":true,"broker_order_allowed":false}'::jsonb),
    ('ai_os_request_graph_change','api_tool','CTO Agent','write_with_approval',true,'Propose a versioned declarative graph change with safety impact and rollback evidence.','{"writes":["agent.graph_change_requests","agent.approvals"],"direct_activation_allowed":false,"human_approval_required":true}'::jsonb),
    ('ai_os_record_graph_correction','api_tool','Model Risk Agent','write_scoped',true,'Append an expected-versus-observed correction and route a bounded prevention task.','{"writes":["agent.correction_ledger","agent.tasks"],"append_only_history":true,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type,owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,
    description=EXCLUDED.description,config=EXCLUDED.config;

INSERT INTO core.control_plane_modules (
    module_key,module_name,category,status,priority,owner_agent,ui_workspace,
    description,warehouse_objects,mcp_tools,next_action,metadata
)
VALUES (
    'graph_control_plane','Graph Control Plane','orchestration','active','critical','Jarvis','graph-studio',
    'Versioned node-edge workflows with bounded autonomy, checkpoints, human waits, correction evidence, and immutable run history.',
    ARRAY['agent.graph_definitions','agent.graph_versions','agent.graph_nodes','agent.graph_edges','agent.graph_runs','agent.graph_node_runs','agent.graph_edge_runs','agent.graph_checkpoints','agent.graph_events','agent.autonomy_policies','agent.correction_ledger','agent.waiting_on_principal'],
    ARRAY['ai_os_graph_control_snapshot','ai_os_start_graph_run','ai_os_advance_graph_run','ai_os_request_graph_change','ai_os_record_graph_correction'],
    'Run the seeded graphs only through the governed API. Material edits create a new reviewed version.',
    '{"arbitrary_code_allowed":false,"broker_writes":false,"human_capital_decision":true,"seed_data_allowed":false}'::jsonb
)
ON CONFLICT (module_key) DO UPDATE SET
    module_name=EXCLUDED.module_name,category=EXCLUDED.category,status=EXCLUDED.status,
    priority=EXCLUDED.priority,owner_agent=EXCLUDED.owner_agent,
    ui_workspace=EXCLUDED.ui_workspace,description=EXCLUDED.description,
    warehouse_objects=EXCLUDED.warehouse_objects,mcp_tools=EXCLUDED.mcp_tools,
    next_action=EXCLUDED.next_action,metadata=EXCLUDED.metadata,updated_at=now();

COMMIT;
