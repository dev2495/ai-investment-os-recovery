CREATE TABLE IF NOT EXISTS core.governance_documents (
    document_key TEXT PRIMARY KEY,
    document_type TEXT NOT NULL,
    title TEXT NOT NULL,
    policy_statement TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    approval_required BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft', 'active', 'retired')),
    version INTEGER NOT NULL DEFAULT 1,
    controls JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.architecture_decisions (
    id BIGSERIAL PRIMARY KEY,
    decision_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    decision_status TEXT NOT NULL DEFAULT 'accepted' CHECK (decision_status IN ('proposed', 'accepted', 'superseded', 'rejected')),
    context TEXT NOT NULL,
    decision TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    consequences JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_agent TEXT NOT NULL DEFAULT 'Jarvis',
    approved_by TEXT,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    supersedes_decision_id BIGINT REFERENCES core.architecture_decisions(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.architecture_change_requests (
    id BIGSERIAL PRIMARY KEY,
    change_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    change_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    proposed_change TEXT NOT NULL,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_consequences JSONB NOT NULL DEFAULT '[]'::jsonb,
    blast_radius TEXT NOT NULL DEFAULT 'bounded',
    rollback_plan TEXT NOT NULL,
    requested_by TEXT NOT NULL DEFAULT 'Devarsh',
    owner_agent TEXT NOT NULL DEFAULT 'Jarvis',
    status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval', 'approved', 'rejected', 'implemented', 'cancelled')),
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE SET NULL,
    decision_id BIGINT REFERENCES core.architecture_decisions(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_architecture_changes_status ON core.architecture_change_requests (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_architecture_changes_approval ON core.architecture_change_requests (approval_id);

INSERT INTO core.governance_documents (
    document_key, document_type, title, policy_statement, owner_agent,
    approval_required, status, controls, evidence
)
VALUES
    ('evidence_standard', 'operating_standard', 'Evidence Standard', 'Every market, portfolio, code, agent, or operational claim must identify a source, command, dataset, note, or live check. Unsupported claims are hypotheses, not facts.', 'Knowledge Librarian', true, 'active', '["source_lineage","timestamp","owner","confidence","reproducibility"]'::jsonb, '[{"source":"AGENTS.md"}]'::jsonb),
    ('production_data_boundary', 'data_policy', 'Production and Test Data Boundary', 'Production views reject seed data. Test and synthetic records must carry an explicit environment marker and cannot enter production portfolio, research, risk, or execution read models.', 'Data Quality Analyst', true, 'active', '["seed_data_allowed=false","environment_label_required","production_read_models"]'::jsonb, '[{"source":"scoped API data_mode contracts"}]'::jsonb),
    ('investment_human_control_notice', 'operator_notice', 'Investment Decision and Human Control Notice', 'The system provides research, monitoring, analysis, and decision support. Devarsh retains final investment authority. No agent may autonomously commit capital or represent analysis as guaranteed financial advice.', 'Charlie Munger', true, 'active', '["human_final_authority","no_guarantees","source_disclosure"]'::jsonb, '[{"source":"AI Investment OS blueprint v10.0"}]'::jsonb),
    ('broker_execution_constitution', 'safety_constitution', 'Broker Execution Safety Constitution', 'Broker writes are disabled by default. Every live order requires an explicit order intent, bounded risk checks, current human approval, an unlocked global policy, and a broker adapter separately authorized for limited live use.', 'Execution Safety Agent', true, 'active', '["default_lock","order_intent","pretrade_risk","human_approval","kill_switch","audit"]'::jsonb, '[{"table":"trading.execution_control_state"},{"table":"trading.order_intents"}]'::jsonb),
    ('architecture_decision_template', 'template', 'Architecture Decision Record Template', 'Record context, decision, alternatives, consequences, owner, approval, evidence, rollback implications, and superseded decisions before material architecture changes are implemented.', 'CTO Agent', false, 'active', '["context","decision","alternatives","consequences","approval","evidence"]'::jsonb, '[]'::jsonb),
    ('committee_minutes_template', 'template', 'Committee Minutes Template', 'Record agenda, participants, evidence reviewed, independent challenges, conflicts, decision, dissent, conditions, owner, due date, and follow-up verification for every material committee decision.', 'Committee Secretary Agent', false, 'active', '["agenda","participants","evidence","challenge","decision","dissent","followups"]'::jsonb, '[]'::jsonb),
    ('cloud_escalation_policy', 'model_policy', 'Cloud Model Escalation Policy', 'Local models are the default. Cloud escalation requires a declared task class, cost ceiling, privacy classification, provider readiness, and human approval whenever sensitive client data or a paid high-cost route is involved.', 'AI Engineering Lead', true, 'active', '["local_first","cost_ceiling","privacy_gate","provider_readiness","approval"]'::jsonb, '[{"table":"agent.model_routes"}]'::jsonb),
    ('external_message_policy', 'communications_policy', 'External Message Approval Policy', 'No agent may send client, broker, exchange, social, email, or public communication without a preview, named human approver, approved channel, immutable audit event, and retained final payload.', 'Compliance Agent', true, 'active', '["preview","human_approval","channel_allowlist","audit","retention"]'::jsonb, '[]'::jsonb),
    ('data_deletion_policy', 'data_policy', 'Data Deletion Approval Policy', 'Production data is never silently deleted. Deletion requires scope preview, retention check, backup evidence, named approval, immutable audit, and a reversible quarantine stage unless law or security response requires immediate containment.', 'Data Steward', true, 'active', '["scope_preview","retention","backup","approval","quarantine","audit"]'::jsonb, '[]'::jsonb),
    ('secrets_management_policy', 'security_policy', 'Secrets Management Policy', 'Credentials stay outside source control, prompts, notes, logs, and audit payloads. Connectors use named credential references, least privilege, rotation evidence, and redacted health checks.', 'MCP Integration Engineer', true, 'active', '["no_plaintext_secrets","credential_references","least_privilege","rotation","redaction"]'::jsonb, '[]'::jsonb),
    ('incident_response_runbook', 'runbook', 'AI OS Incident Response Runbook', 'Contain risk first, preserve evidence, engage the relevant kill switch, identify affected data and clients, restore from verified recovery points, document root cause, and require approval before service or execution is re-enabled.', 'Risk Agent', true, 'active', '["contain","preserve_evidence","kill_switch","assess","restore","postmortem","reapproval"]'::jsonb, '[{"note":"External SSD and AI OS Runtime Recovery Runbook"}]'::jsonb)
ON CONFLICT (document_key) DO UPDATE SET
    document_type = EXCLUDED.document_type,
    title = EXCLUDED.title,
    policy_statement = EXCLUDED.policy_statement,
    owner_agent = EXCLUDED.owner_agent,
    approval_required = EXCLUDED.approval_required,
    status = EXCLUDED.status,
    controls = EXCLUDED.controls,
    evidence = EXCLUDED.evidence,
    version = greatest(core.governance_documents.version, EXCLUDED.version),
    updated_at = now();

CREATE OR REPLACE FUNCTION core.prevent_audit_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'agent.mcp_audit_log is append-only; % is prohibited', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS trg_mcp_audit_append_only ON agent.mcp_audit_log;
CREATE TRIGGER trg_mcp_audit_append_only
BEFORE UPDATE OR DELETE ON agent.mcp_audit_log
FOR EACH ROW EXECUTE FUNCTION core.prevent_audit_mutation();

CREATE OR REPLACE FUNCTION core.request_architecture_change(
    p_title TEXT,
    p_change_type TEXT,
    p_objective TEXT,
    p_proposed_change TEXT,
    p_rollback_plan TEXT,
    p_actor TEXT DEFAULT 'Devarsh',
    p_owner_agent TEXT DEFAULT 'Jarvis',
    p_blast_radius TEXT DEFAULT 'bounded',
    p_alternatives JSONB DEFAULT '[]'::jsonb,
    p_expected_consequences JSONB DEFAULT '[]'::jsonb,
    p_evidence JSONB DEFAULT '[]'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_key TEXT;
    v_task_id BIGINT;
    v_inbox_id BIGINT;
    v_approval_id BIGINT;
    v_change_id BIGINT;
BEGIN
    IF nullif(trim(coalesce(p_title, '')), '') IS NULL
       OR nullif(trim(coalesce(p_objective, '')), '') IS NULL
       OR nullif(trim(coalesce(p_proposed_change, '')), '') IS NULL
       OR nullif(trim(coalesce(p_rollback_plan, '')), '') IS NULL THEN
        RAISE EXCEPTION 'title, objective, proposed_change, and rollback_plan are required';
    END IF;

    v_key := 'arch-change-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS') || '-' ||
        left(regexp_replace(lower(trim(p_title)), '[^a-z0-9]+', '-', 'g'), 48);

    INSERT INTO agent.tasks (title, objective, owner_agent, status, priority, approval_required, source_kind, source_ref, evidence)
    VALUES (p_title, p_objective, p_owner_agent, 'needs_review',
            CASE WHEN p_blast_radius IN ('system_wide', 'execution', 'client_data') THEN 'critical' ELSE 'high' END,
            true, 'architecture_change', v_key, coalesce(p_evidence, '[]'::jsonb))
    RETURNING id INTO v_task_id;

    INSERT INTO agent.approvals (task_id, approval_type, title, owner_agent, risk_level, status, requested_action, rationale)
    VALUES (v_task_id, 'architecture_change', 'Architecture change: ' || p_title, 'Charlie Munger',
            CASE WHEN p_blast_radius IN ('system_wide', 'execution', 'client_data') THEN 'critical' ELSE 'high' END,
            'pending', jsonb_build_object('change_key', v_key, 'change_type', p_change_type, 'blast_radius', p_blast_radius,
                'proposed_change', p_proposed_change, 'rollback_plan', p_rollback_plan), p_objective)
    RETURNING id INTO v_approval_id;

    INSERT INTO agent.inbox_items (task_id, title, owner_agent, status, priority, recommended_action, evidence, target_workspace)
    VALUES (v_task_id, 'Review architecture change: ' || p_title, 'Charlie Munger', 'needs_review',
            CASE WHEN p_blast_radius IN ('system_wide', 'execution', 'client_data') THEN 'critical' ELSE 'high' END,
            'Review evidence, alternatives, blast radius, and rollback plan before deciding.',
            jsonb_build_array(jsonb_build_object('approval_id', v_approval_id), jsonb_build_object('change_key', v_key)), 'governance')
    RETURNING id INTO v_inbox_id;

    INSERT INTO core.architecture_change_requests (
        change_key, title, change_type, objective, proposed_change, alternatives,
        expected_consequences, blast_radius, rollback_plan, requested_by,
        owner_agent, task_id, inbox_item_id, approval_id, evidence
    ) VALUES (
        v_key, trim(p_title), coalesce(nullif(trim(p_change_type), ''), 'system_change'), trim(p_objective),
        trim(p_proposed_change), coalesce(p_alternatives, '[]'::jsonb), coalesce(p_expected_consequences, '[]'::jsonb),
        coalesce(nullif(trim(p_blast_radius), ''), 'bounded'), trim(p_rollback_plan),
        coalesce(nullif(trim(p_actor), ''), 'Devarsh'), coalesce(nullif(trim(p_owner_agent), ''), 'Jarvis'),
        v_task_id, v_inbox_id, v_approval_id, coalesce(p_evidence, '[]'::jsonb)
    ) RETURNING id INTO v_change_id;

    RETURN jsonb_build_object('change_id', v_change_id, 'change_key', v_key, 'task_id', v_task_id,
        'inbox_item_id', v_inbox_id, 'approval_id', v_approval_id, 'status', 'pending_approval',
        'live_execution_allowed', false);
END;
$$;

CREATE OR REPLACE FUNCTION core.sync_architecture_change(p_change_id BIGINT, p_actor TEXT DEFAULT 'Jarvis')
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_change core.architecture_change_requests%ROWTYPE;
    v_approval agent.approvals%ROWTYPE;
    v_decision_id BIGINT;
    v_status TEXT;
BEGIN
    SELECT * INTO v_change FROM core.architecture_change_requests WHERE id = p_change_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'architecture change % not found', p_change_id; END IF;
    SELECT * INTO v_approval FROM agent.approvals WHERE id = v_change.approval_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'approval for architecture change % not found', p_change_id; END IF;

    v_status := CASE v_approval.status WHEN 'approved' THEN 'approved' WHEN 'rejected' THEN 'rejected' ELSE 'pending_approval' END;
    IF v_status = 'approved' THEN
        INSERT INTO core.architecture_decisions (
            decision_key, title, decision_status, context, decision, alternatives,
            consequences, owner_agent, approved_by, approval_id, evidence, decided_at
        ) VALUES (
            'adr-' || v_change.change_key, v_change.title, 'accepted', v_change.objective,
            v_change.proposed_change, v_change.alternatives, v_change.expected_consequences,
            v_change.owner_agent, v_approval.decided_by, v_approval.id, v_change.evidence, v_approval.decided_at
        ) ON CONFLICT (decision_key) DO UPDATE SET
            decision_status = EXCLUDED.decision_status,
            decision = EXCLUDED.decision,
            consequences = EXCLUDED.consequences,
            approved_by = EXCLUDED.approved_by,
            decided_at = EXCLUDED.decided_at,
            updated_at = now()
        RETURNING id INTO v_decision_id;
    END IF;

    UPDATE core.architecture_change_requests
    SET status = v_status, decision_id = coalesce(v_decision_id, decision_id), updated_at = now()
    WHERE id = p_change_id;
    UPDATE agent.tasks SET status = CASE v_status WHEN 'approved' THEN 'approved' WHEN 'rejected' THEN 'blocked' ELSE status END, updated_at = now()
    WHERE id = v_change.task_id;
    UPDATE agent.inbox_items SET status = CASE v_status WHEN 'approved' THEN 'resolved' WHEN 'rejected' THEN 'closed' ELSE status END, updated_at = now()
    WHERE id = v_change.inbox_item_id;

    RETURN jsonb_build_object('change_id', p_change_id, 'status', v_status, 'approval_status', v_approval.status,
        'decision_id', coalesce(v_decision_id, v_change.decision_id), 'synced_by', p_actor, 'live_execution_allowed', false);
END;
$$;

CREATE OR REPLACE VIEW core.v_architecture_change_board AS
SELECT
    change.id,
    change.change_key,
    change.title,
    change.change_type,
    change.objective,
    change.proposed_change,
    change.alternatives,
    change.expected_consequences,
    change.blast_radius,
    change.rollback_plan,
    change.requested_by,
    change.owner_agent,
    change.status,
    change.task_id,
    task.status AS task_status,
    change.inbox_item_id,
    change.approval_id,
    approval.status AS approval_status,
    approval.decided_by,
    approval.decided_at,
    change.decision_id,
    change.evidence,
    change.created_at,
    change.updated_at,
    false AS live_execution_allowed
FROM core.architecture_change_requests change
LEFT JOIN agent.tasks task ON task.id = change.task_id
LEFT JOIN agent.approvals approval ON approval.id = change.approval_id;

CREATE OR REPLACE VIEW core.v_production_safety_readiness AS
WITH execution AS (
    SELECT * FROM trading.execution_control_state WHERE state_key = 'global'
), audit_guard AS (
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'agent.mcp_audit_log'::regclass
          AND tgname = 'trg_mcp_audit_append_only'
          AND NOT tgisinternal
    ) AS enabled
)
SELECT * FROM (
    SELECT 'broker_default_lock'::text AS check_key, 'Broker execution disabled by default'::text AS title,
           CASE WHEN global_execution_locked AND NOT live_broker_writes_allowed THEN 'passed' ELSE 'failed' END AS status,
           'critical'::text AS severity, 'Execution Safety Agent'::text AS owner_agent,
           jsonb_build_object('global_execution_locked', global_execution_locked, 'live_broker_writes_allowed', live_broker_writes_allowed, 'policy', broker_execution_policy) AS evidence,
           CASE WHEN global_execution_locked AND NOT live_broker_writes_allowed THEN 'Maintain the lock until every limited-live gate is deliberately implemented and approved.' ELSE 'Engage the global kill switch immediately.' END AS next_action,
           updated_at AS checked_at FROM execution
    UNION ALL
    SELECT 'order_preview_contract', 'Order intent preview before broker action',
           CASE WHEN to_regclass('trading.order_intents') IS NOT NULL AND to_regclass('trading.order_risk_checks') IS NOT NULL THEN 'passed' ELSE 'failed' END,
           'critical', 'Execution Safety Agent', jsonb_build_object('order_intents', to_regclass('trading.order_intents'), 'risk_checks', to_regclass('trading.order_risk_checks')),
           'Require an order intent and risk-check record for every proposed live order.', now()
    UNION ALL
    SELECT 'human_order_approval', 'Human approval before any live order',
           CASE WHEN EXISTS (SELECT 1 FROM agent.approvals WHERE approval_type = 'broker_order_intent') OR to_regprocedure('trading.create_order_intent(bigint,jsonb,text,text)') IS NOT NULL THEN 'passed' ELSE 'failed' END,
           'critical', 'Charlie Munger', jsonb_build_object('approval_type', 'broker_order_intent', 'function', to_regprocedure('trading.create_order_intent(bigint,jsonb,text,text)')),
           'Never interpret strategy, memo, or committee approval as per-order approval.', now()
    UNION ALL
    SELECT 'global_kill_switch', 'Global kill switch backend enforcement',
           CASE WHEN to_regprocedure('trading.engage_global_kill_switch(text,text,text)') IS NOT NULL THEN 'passed' ELSE 'failed' END,
           'critical', 'Risk Agent', jsonb_build_object('function', to_regprocedure('trading.engage_global_kill_switch(text,text,text)')),
           'Keep the kill switch visible and test it only through a rollback-safe drill.', now()
    UNION ALL
    SELECT 'immutable_audit', 'Append-only operational audit log', CASE WHEN enabled THEN 'passed' ELSE 'failed' END,
           'high', 'Compliance Agent', jsonb_build_object('trigger_enabled', enabled, 'table', 'agent.mcp_audit_log'),
           'Investigate immediately if the append-only trigger is absent or disabled.', now() FROM audit_guard
    UNION ALL
    SELECT 'production_data_boundary', 'Production data and seed-data separation',
           CASE WHEN EXISTS (SELECT 1 FROM core.governance_documents WHERE document_key = 'production_data_boundary' AND status = 'active') THEN 'passed' ELSE 'failed' END,
           'high', 'Data Quality Analyst', jsonb_build_object('seed_data_allowed', false, 'policy_key', 'production_data_boundary'),
           'Reject unlabeled synthetic or seed records from production read models.', now()
    UNION ALL
    SELECT 'secrets_policy', 'Secrets stay outside code, prompts, notes, and logs',
           CASE WHEN EXISTS (SELECT 1 FROM core.governance_documents WHERE document_key = 'secrets_management_policy' AND status = 'active') THEN 'policy_active' ELSE 'failed' END,
           'high', 'MCP Integration Engineer', jsonb_build_object('policy_key', 'secrets_management_policy'),
           'Add automated repository and audit-payload secret scanning before marking fully enforced.', now()
) controls;

CREATE OR REPLACE VIEW core.v_governance_control_summary AS
SELECT 'active_policies'::text AS metric, count(*)::text AS value, 'Active governance policies and templates'::text AS interpretation
FROM core.governance_documents WHERE status = 'active'
UNION ALL
SELECT 'pending_architecture_changes', count(*)::text, 'Material architecture changes awaiting a human decision'
FROM core.architecture_change_requests WHERE status = 'pending_approval'
UNION ALL
SELECT 'accepted_architecture_decisions', count(*)::text, 'Approved architecture decisions retained in the decision log'
FROM core.architecture_decisions WHERE decision_status = 'accepted'
UNION ALL
SELECT 'production_safety_failures', count(*) FILTER (WHERE status = 'failed')::text, 'Live production-safety controls requiring remediation'
FROM core.v_production_safety_readiness
UNION ALL
SELECT 'immutable_audit_events', count(*)::text, 'Append-only API and MCP audit events'
FROM agent.mcp_audit_log;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_governance_control_board', 'mcp_tool', 'Compliance Agent', 'read_only', true, 'Read policies, architecture decisions, change requests, and live production-safety controls.', '{"reads":["core.governance_documents","core.v_architecture_change_board","core.v_production_safety_readiness"]}'::jsonb),
    ('ai_os_request_architecture_change', 'mcp_tool', 'CTO Agent', 'write_with_approval', true, 'Create a material architecture change request with task, inbox, rollback plan, and human approval.', '{"writes":["core.architecture_change_requests","agent.tasks","agent.inbox_items","agent.approvals"],"live_execution_allowed":false}'::jsonb),
    ('ai_os_sync_architecture_change', 'mcp_tool', 'Jarvis', 'write_with_approval', true, 'Synchronize a decided architecture-change approval into the immutable decision log.', '{"writes":["core.architecture_change_requests","core.architecture_decisions"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE ops.workspace_profiles
SET navigation = jsonb_set(
        navigation,
        '{visible}',
        CASE
            WHEN coalesce(navigation -> 'visible', '[]'::jsonb) @> '["governance"]'::jsonb THEN navigation -> 'visible'
            ELSE coalesce(navigation -> 'visible', '[]'::jsonb) || '"governance"'::jsonb
        END
    ),
    updated_at = now()
WHERE profile_key = 'devarsh';

INSERT INTO ops.workspace_layouts (profile_id, workspace_key, module_order, column_count, settings, updated_by)
SELECT id, 'governance', '["summary","policies","architecture_changes","safety_controls","audit"]'::jsonb, 2,
       '{"show_evidence":true,"show_freshness":true,"human_control_notice":true}'::jsonb, 'Jarvis'
FROM ops.workspace_profiles WHERE profile_key = 'devarsh'
ON CONFLICT (profile_id, workspace_key) DO NOTHING;

INSERT INTO agent.mcp_audit_log (
    tool_name, action_type, permission_level, actor, status, target_table,
    target_id, request_payload, result_payload
) SELECT
    'migration_123_governance_control_plane', 'install_governance_controls', 'system_migration',
    'Jarvis', 'success', 'core.governance_documents', 'v1',
    '{"seed_data_allowed":false}'::jsonb,
    '{"append_only_audit":true,"broker_execution_allowed":false,"live_execution_allowed":false}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM agent.mcp_audit_log
    WHERE tool_name = 'migration_123_governance_control_plane'
      AND target_table = 'core.governance_documents'
      AND target_id = 'v1'
);
