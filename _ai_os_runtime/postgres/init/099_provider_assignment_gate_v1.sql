CREATE TABLE IF NOT EXISTS core.provider_assignment_gate_checks (
    id BIGSERIAL PRIMARY KEY,
    gate_key TEXT NOT NULL UNIQUE,
    provider_kind TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    provider_name TEXT,
    provider TEXT,
    subject_name TEXT,
    route_or_source TEXT,
    requested_by TEXT NOT NULL DEFAULT 'Jarvis',
    requesting_agent TEXT NOT NULL DEFAULT 'Jarvis',
    requested_use TEXT NOT NULL DEFAULT 'provider assignment',
    source_kind TEXT,
    source_ref TEXT,
    target_workspace TEXT NOT NULL DEFAULT 'system',
    readiness_status TEXT NOT NULL DEFAULT 'unknown',
    provider_health_status TEXT,
    assignment_status TEXT NOT NULL DEFAULT 'blocked',
    assignment_allowed BOOLEAN NOT NULL DEFAULT false,
    assignable_snapshot BOOLEAN NOT NULL DEFAULT false,
    block_reasons TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    next_action TEXT NOT NULL DEFAULT 'Review provider readiness before assignment.',
    readiness_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    inbox_item_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_provider_assignment_passed CHECK (
        assignment_allowed = false OR assignment_status = 'passed'
    )
);

CREATE INDEX IF NOT EXISTS idx_provider_assignment_gate_created
ON core.provider_assignment_gate_checks (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_provider_assignment_gate_provider
ON core.provider_assignment_gate_checks (provider_kind, provider_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_provider_assignment_gate_status
ON core.provider_assignment_gate_checks (assignment_status, created_at DESC);

CREATE OR REPLACE FUNCTION core.evaluate_provider_assignment_gate(p_payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_provider RECORD;
    v_gate_id BIGINT;
    v_inbox_id BIGINT;
    v_provider_key TEXT := btrim(coalesce(p_payload->>'provider_key', p_payload->>'providerKey', ''));
    v_provider_kind TEXT := btrim(coalesce(p_payload->>'provider_kind', p_payload->>'providerKind', ''));
    v_requested_by TEXT := nullif(btrim(coalesce(p_payload->>'requested_by', p_payload->>'requestedBy', p_payload->>'actor', 'Jarvis')), '');
    v_requesting_agent TEXT := nullif(btrim(coalesce(p_payload->>'requesting_agent', p_payload->>'requestingAgent', p_payload->>'agent', 'Jarvis')), '');
    v_requested_use TEXT := nullif(btrim(coalesce(p_payload->>'requested_use', p_payload->>'requestedUse', p_payload->>'use_case', p_payload->>'useCase', 'provider assignment')), '');
    v_source_kind TEXT := nullif(btrim(coalesce(p_payload->>'source_kind', p_payload->>'sourceKind', '')), '');
    v_source_ref TEXT := nullif(btrim(coalesce(p_payload->>'source_ref', p_payload->>'sourceRef', '')), '');
    v_target_workspace TEXT := nullif(btrim(coalesce(p_payload->>'target_workspace', p_payload->>'targetWorkspace', 'system')), '');
    v_create_inbox BOOLEAN := coalesce((p_payload->>'create_inbox_on_block')::BOOLEAN, (p_payload->>'createInboxOnBlock')::BOOLEAN, true);
    v_assignment_status TEXT := 'blocked';
    v_assignment_allowed BOOLEAN := false;
    v_readiness_status TEXT := 'not_found';
    v_health_status TEXT;
    v_assignable BOOLEAN := false;
    v_provider_found BOOLEAN := false;
    v_block_reasons TEXT[] := ARRAY[]::TEXT[];
    v_next_action TEXT := 'Provider not found. Register and health-check the provider before assignment.';
    v_readiness_snapshot JSONB := '{}'::jsonb;
    v_gate_key TEXT;
BEGIN
    IF v_provider_key = '' THEN
        RAISE EXCEPTION 'provider_key is required';
    END IF;

    v_requested_by := coalesce(v_requested_by, 'Jarvis');
    v_requesting_agent := coalesce(v_requesting_agent, 'Jarvis');
    v_requested_use := coalesce(v_requested_use, 'provider assignment');
    v_target_workspace := coalesce(v_target_workspace, 'system');
    v_gate_key := 'provider-gate-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS') || '-' || substr(md5(random()::TEXT || clock_timestamp()::TEXT), 1, 8);

    SELECT board.*
    INTO v_provider
    FROM core.v_provider_readiness_board board
    WHERE board.provider_key = v_provider_key
      AND (v_provider_kind = '' OR board.provider_kind = v_provider_kind)
    ORDER BY
        CASE board.readiness_status
            WHEN 'ready' THEN 1
            WHEN 'approval_required' THEN 2
            ELSE 3
        END,
        board.id
    LIMIT 1;

    IF FOUND THEN
        v_provider_found := true;
        v_provider_kind := v_provider.provider_kind;
        v_readiness_status := v_provider.readiness_status;
        v_health_status := v_provider.health_status;
        v_assignable := coalesce(v_provider.assignable, false);
        v_next_action := coalesce(v_provider.next_action, 'Review provider readiness before assignment.');
        v_readiness_snapshot := jsonb_build_object(
            'provider_kind', v_provider.provider_kind,
            'provider_key', v_provider.provider_key,
            'provider_name', v_provider.provider_name,
            'provider', v_provider.provider,
            'subject_name', v_provider.subject_name,
            'route_or_source', v_provider.route_or_source,
            'provider_type', v_provider.provider_type,
            'status', v_provider.status,
            'health_status', v_provider.health_status,
            'readiness_status', v_provider.readiness_status,
            'assignable', v_provider.assignable,
            'requires_api_key', v_provider.requires_api_key,
            'has_secret_ref', v_provider.has_secret_ref,
            'requires_browser_session', v_provider.requires_browser_session,
            'browser_ready', v_provider.browser_ready,
            'cost_tier', v_provider.cost_tier,
            'owner_agent', v_provider.owner_agent,
            'last_checked_at', v_provider.last_checked_at,
            'last_error', v_provider.last_error,
            'next_action', v_provider.next_action
        );

        IF v_provider.readiness_status = 'ready' AND coalesce(v_provider.assignable, false) THEN
            v_assignment_status := 'passed';
            v_assignment_allowed := true;
            v_next_action := 'Provider assignment allowed for this requested use.';
        ELSIF v_provider.readiness_status = 'approval_required' THEN
            v_assignment_status := 'approval_required';
            v_assignment_allowed := false;
            v_block_reasons := ARRAY['approval_required']::TEXT[];
            v_next_action := 'Provider requires explicit approval/cost policy before assignment.';
        ELSE
            v_assignment_status := 'blocked';
            v_assignment_allowed := false;
            v_block_reasons := ARRAY[v_provider.readiness_status]::TEXT[];
        END IF;
    ELSE
        v_provider_kind := coalesce(nullif(v_provider_kind, ''), 'unknown');
        v_block_reasons := ARRAY['provider_not_found']::TEXT[];
    END IF;

    INSERT INTO core.provider_assignment_gate_checks (
        gate_key,
        provider_kind,
        provider_key,
        provider_name,
        provider,
        subject_name,
        route_or_source,
        requested_by,
        requesting_agent,
        requested_use,
        source_kind,
        source_ref,
        target_workspace,
        readiness_status,
        provider_health_status,
        assignment_status,
        assignment_allowed,
        assignable_snapshot,
        block_reasons,
        next_action,
        readiness_snapshot,
        evidence,
        metadata
    )
    VALUES (
        v_gate_key,
        v_provider_kind,
        v_provider_key,
        CASE WHEN v_provider_found THEN v_provider.provider_name ELSE NULL END,
        CASE WHEN v_provider_found THEN v_provider.provider ELSE NULL END,
        CASE WHEN v_provider_found THEN v_provider.subject_name ELSE NULL END,
        CASE WHEN v_provider_found THEN v_provider.route_or_source ELSE NULL END,
        v_requested_by,
        v_requesting_agent,
        v_requested_use,
        v_source_kind,
        v_source_ref,
        v_target_workspace,
        v_readiness_status,
        v_health_status,
        v_assignment_status,
        v_assignment_allowed,
        v_assignable,
        v_block_reasons,
        v_next_action,
        v_readiness_snapshot,
        coalesce(p_payload->'evidence', '[]'::jsonb),
        coalesce(p_payload->'metadata', '{}'::jsonb)
    )
    RETURNING id INTO v_gate_id;

    IF NOT v_assignment_allowed AND v_create_inbox THEN
        INSERT INTO agent.inbox_items (
            title,
            owner_agent,
            status,
            priority,
            recommended_action,
            evidence,
            target_workspace
        )
        VALUES (
            CASE
                WHEN v_assignment_status = 'approval_required' THEN 'Provider assignment needs approval: ' || v_provider_key
                ELSE 'Provider assignment blocked: ' || v_provider_key
            END,
            CASE
                WHEN v_provider_found THEN coalesce(v_provider.owner_agent, 'Jarvis')
                ELSE 'Jarvis'
            END,
            CASE
                WHEN v_assignment_status = 'approval_required' THEN 'needs_review'
                ELSE 'blocked'
            END,
            CASE
                WHEN v_assignment_status = 'approval_required' THEN 'high'
                ELSE 'normal'
            END,
            v_next_action,
            jsonb_build_array(
                jsonb_build_object('table', 'core.provider_assignment_gate_checks', 'id', v_gate_id),
                jsonb_build_object('provider_key', v_provider_key, 'provider_kind', v_provider_kind, 'assignment_status', v_assignment_status),
                jsonb_build_object('requested_use', v_requested_use, 'requesting_agent', v_requesting_agent, 'requested_by', v_requested_by)
            ),
            v_target_workspace
        )
        RETURNING id INTO v_inbox_id;

        UPDATE core.provider_assignment_gate_checks
        SET inbox_item_id = v_inbox_id,
            updated_at = now()
        WHERE id = v_gate_id;
    END IF;

    RETURN (
        SELECT row_to_json(result_row)::jsonb
        FROM (
            SELECT
                gate.id,
                gate.gate_key,
                gate.provider_kind,
                gate.provider_key,
                gate.provider_name,
                gate.provider,
                gate.subject_name,
                gate.route_or_source,
                gate.requested_by,
                gate.requesting_agent,
                gate.requested_use,
                gate.source_kind,
                gate.source_ref,
                gate.target_workspace,
                gate.readiness_status,
                gate.provider_health_status,
                gate.assignment_status,
                gate.assignment_allowed,
                gate.assignable_snapshot,
                gate.block_reasons,
                gate.next_action,
                gate.inbox_item_id,
                gate.readiness_snapshot,
                gate.evidence,
                gate.metadata,
                gate.created_at,
                gate.updated_at
            FROM core.provider_assignment_gate_checks gate
            WHERE gate.id = v_gate_id
        ) result_row
    );
END;
$$;

CREATE OR REPLACE VIEW core.v_provider_assignment_gate_checks AS
SELECT
    gate.id,
    gate.gate_key,
    gate.provider_kind,
    gate.provider_key,
    gate.provider_name,
    gate.provider,
    gate.subject_name,
    gate.route_or_source,
    gate.requested_by,
    gate.requesting_agent,
    gate.requested_use,
    gate.source_kind,
    gate.source_ref,
    gate.target_workspace,
    gate.readiness_status,
    gate.provider_health_status,
    gate.assignment_status,
    gate.assignment_allowed,
    gate.assignable_snapshot,
    gate.block_reasons,
    gate.next_action,
    gate.inbox_item_id,
    inbox.status AS inbox_status,
    gate.readiness_snapshot,
    gate.evidence,
    gate.metadata,
    gate.created_at,
    gate.updated_at
FROM core.provider_assignment_gate_checks gate
LEFT JOIN agent.inbox_items inbox ON inbox.id = gate.inbox_item_id
ORDER BY gate.created_at DESC, gate.id DESC;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_evaluate_provider_assignment_gate', 'mcp_tool', 'Jarvis', 'write_db_manual_only', true,
     'Evaluate whether a model endpoint or data-source connector can be assigned to an agent task. Blocks missing secrets, browser failures, inactive connectors, and approval-required providers.',
     '{"function":"core.evaluate_provider_assignment_gate","reads":["core.v_provider_readiness_board"],"writes":["core.provider_assignment_gate_checks","agent.inbox_items"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_provider_assignment_gates', 'mcp_tool', 'Jarvis', 'read_only', true,
     'Read recent provider assignment gate checks and resulting inbox blocks.',
     '{"reads":["core.v_provider_assignment_gate_checks"],"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type = EXCLUDED.tool_type,
    owning_agent = EXCLUDED.owning_agent,
    permission_level = EXCLUDED.permission_level,
    enabled = EXCLUDED.enabled,
    description = EXCLUDED.description,
    config = EXCLUDED.config;

UPDATE core.control_plane_modules
SET warehouse_objects = ARRAY(
        SELECT DISTINCT obj
        FROM unnest(warehouse_objects || ARRAY[
            'core.provider_assignment_gate_checks',
            'core.v_provider_assignment_gate_checks'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_evaluate_provider_assignment_gate',
            'ai_os_provider_assignment_gates'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Evaluate provider assignment gates before letting agents use model endpoints or data-source connectors.',
    updated_at = now()
WHERE module_key IN ('data_sources', 'runtime', 'automation');
