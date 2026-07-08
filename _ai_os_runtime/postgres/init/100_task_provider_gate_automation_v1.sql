CREATE OR REPLACE FUNCTION core.evaluate_task_provider_assignment_gates(
    p_task_id BIGINT,
    p_actor TEXT DEFAULT 'Jarvis',
    p_context TEXT DEFAULT 'manual'
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_task RECORD;
    v_candidate RECORD;
    v_gate JSONB;
    v_gate_ids BIGINT[] := ARRAY[]::BIGINT[];
    v_gate_payloads JSONB := '[]'::jsonb;
    v_blocked_count INTEGER := 0;
    v_approval_count INTEGER := 0;
    v_passed_count INTEGER := 0;
    v_candidate_count INTEGER := 0;
    v_overall_status TEXT := 'passed';
    v_next_status TEXT;
    v_evidence JSONB;
BEGIN
    SELECT *
    INTO v_task
    FROM agent.tasks
    WHERE id = p_task_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'task % not found', p_task_id;
    END IF;

    FOR v_candidate IN
        WITH profile_route AS (
            SELECT
                p.default_model_route,
                p.agent_name
            FROM agent.profiles p
            WHERE p.agent_name = v_task.owner_agent
            LIMIT 1
        ),
        default_model_provider AS (
            SELECT DISTINCT ON (coalesce(board.provider_key, route.default_model_route))
                'model_endpoint'::TEXT AS provider_kind,
                coalesce(
                    board.provider_key,
                    'missing_model_endpoint_for_route_' || coalesce(route.default_model_route, 'missing_default_route_' || lower(regexp_replace(v_task.owner_agent, '[^a-zA-Z0-9]+', '_', 'g')))
                ) AS provider_key,
                'owner_default_model_route'::TEXT AS source
            FROM profile_route route
            LEFT JOIN core.v_provider_readiness_board board
              ON board.provider_kind = 'model_endpoint'
             AND board.route_or_source = route.default_model_route
            UNION ALL
            SELECT
                'model_endpoint',
                'missing_default_model_route_' || lower(regexp_replace(v_task.owner_agent, '[^a-zA-Z0-9]+', '_', 'g')),
                'missing_owner_profile'
            WHERE NOT EXISTS (SELECT 1 FROM profile_route)
        ),
        evidence_providers AS (
            SELECT DISTINCT
                coalesce(nullif(elem->>'provider_kind', ''), nullif(elem->>'providerKind', ''), '') AS provider_kind,
                coalesce(nullif(elem->>'provider_key', ''), nullif(elem->>'providerKey', '')) AS provider_key,
                'task_evidence'::TEXT AS source
            FROM jsonb_array_elements(coalesce(v_task.evidence, '[]'::jsonb)) elem
            WHERE coalesce(nullif(elem->>'provider_key', ''), nullif(elem->>'providerKey', '')) IS NOT NULL
        ),
        candidates AS (
            SELECT * FROM default_model_provider
            UNION ALL
            SELECT
                CASE WHEN provider_kind = '' THEN 'unknown' ELSE provider_kind END,
                provider_key,
                source
            FROM evidence_providers
        )
        SELECT DISTINCT ON (provider_kind, provider_key)
            provider_kind,
            provider_key,
            source
        FROM candidates
        WHERE provider_key IS NOT NULL
        ORDER BY provider_kind, provider_key, source
    LOOP
        v_candidate_count := v_candidate_count + 1;
        v_gate := core.evaluate_provider_assignment_gate(
            jsonb_build_object(
                'provider_key', v_candidate.provider_key,
                'provider_kind', v_candidate.provider_kind,
                'requesting_agent', v_task.owner_agent,
                'requested_use', 'Automatic task provider gate: ' || v_task.title,
                'source_kind', 'agent_task',
                'source_ref', v_task.id::TEXT,
                'target_workspace', coalesce(v_task.source_kind, 'system'),
                'create_inbox_on_block', true,
                'actor', coalesce(nullif(p_actor, ''), 'Jarvis'),
                'evidence', jsonb_build_array(
                    jsonb_build_object('table', 'agent.tasks', 'id', v_task.id),
                    jsonb_build_object('task_source_kind', v_task.source_kind, 'task_source_ref', v_task.source_ref),
                    jsonb_build_object('provider_source', v_candidate.source, 'context', p_context)
                ),
                'metadata', jsonb_build_object(
                    'task_id', v_task.id,
                    'task_title', v_task.title,
                    'task_owner_agent', v_task.owner_agent,
                    'context', p_context,
                    'automation', 'core.evaluate_task_provider_assignment_gates'
                )
            )
        );

        v_gate_payloads := v_gate_payloads || jsonb_build_array(v_gate);
        v_gate_ids := array_append(v_gate_ids, (v_gate->>'id')::BIGINT);

        IF v_gate ? 'inbox_item_id' AND nullif(v_gate->>'inbox_item_id', '') IS NOT NULL THEN
            UPDATE agent.inbox_items
            SET task_id = v_task.id,
                updated_at = now()
            WHERE id = (v_gate->>'inbox_item_id')::BIGINT
              AND task_id IS NULL;
        END IF;

        IF coalesce(v_gate->>'assignment_status', '') = 'blocked' THEN
            v_blocked_count := v_blocked_count + 1;
        ELSIF coalesce(v_gate->>'assignment_status', '') = 'approval_required' THEN
            v_approval_count := v_approval_count + 1;
        ELSIF coalesce((v_gate->>'assignment_allowed')::BOOLEAN, false) THEN
            v_passed_count := v_passed_count + 1;
        END IF;
    END LOOP;

    IF v_candidate_count = 0 THEN
        v_overall_status := 'blocked';
        v_next_status := 'blocked';
        v_evidence := jsonb_build_array(jsonb_build_object(
            'source', 'core.evaluate_task_provider_assignment_gates',
            'task_id', v_task.id,
            'overall_status', v_overall_status,
            'reason', 'no_provider_candidates'
        ));
    ELSIF v_blocked_count > 0 THEN
        v_overall_status := 'blocked';
        v_next_status := 'blocked';
    ELSIF v_approval_count > 0 THEN
        v_overall_status := 'approval_required';
        v_next_status := 'needs_review';
    ELSE
        v_overall_status := 'passed';
        v_next_status := v_task.status;
    END IF;

    v_evidence := coalesce(v_evidence, jsonb_build_array(jsonb_build_object(
        'source', 'core.evaluate_task_provider_assignment_gates',
        'task_id', v_task.id,
        'context', p_context,
        'overall_status', v_overall_status,
        'gate_ids', v_gate_ids,
        'candidate_count', v_candidate_count,
        'blocked_count', v_blocked_count,
        'approval_required_count', v_approval_count,
        'passed_count', v_passed_count
    )));

    UPDATE agent.tasks
    SET status = CASE
            WHEN status IN ('completed', 'cancelled', 'done') THEN status
            WHEN v_next_status IS NOT NULL THEN v_next_status
            ELSE status
        END,
        evidence = coalesce(evidence, '[]'::jsonb) || v_evidence,
        updated_at = now()
    WHERE id = v_task.id;

    RETURN jsonb_build_object(
        'task_id', v_task.id,
        'task_title', v_task.title,
        'owner_agent', v_task.owner_agent,
        'context', p_context,
        'overall_status', v_overall_status,
        'next_task_status', coalesce(v_next_status, v_task.status),
        'candidate_count', v_candidate_count,
        'passed_count', v_passed_count,
        'approval_required_count', v_approval_count,
        'blocked_count', v_blocked_count,
        'gate_ids', v_gate_ids,
        'gates', v_gate_payloads
    );
END;
$$;

CREATE OR REPLACE FUNCTION agent.auto_gate_task_providers_after_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM core.evaluate_task_provider_assignment_gates(NEW.id, 'Jarvis', 'task_insert_trigger');
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    UPDATE agent.tasks
    SET status = 'blocked',
        evidence = coalesce(evidence, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
            'source', 'agent.auto_gate_task_providers_after_insert',
            'error', SQLERRM,
            'task_id', NEW.id
        )),
        updated_at = now()
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_auto_gate_task_providers_after_insert ON agent.tasks;
CREATE TRIGGER trg_auto_gate_task_providers_after_insert
AFTER INSERT ON agent.tasks
FOR EACH ROW
EXECUTE FUNCTION agent.auto_gate_task_providers_after_insert();

CREATE OR REPLACE VIEW agent.v_task_provider_gate_status AS
WITH latest_task_gates AS (
    SELECT DISTINCT ON (gate.source_ref, gate.provider_kind, gate.provider_key)
        gate.*
    FROM core.provider_assignment_gate_checks gate
    WHERE gate.source_kind = 'agent_task'
      AND gate.source_ref ~ '^[0-9]+$'
    ORDER BY gate.source_ref, gate.provider_kind, gate.provider_key, gate.created_at DESC, gate.id DESC
),
aggregated AS (
    SELECT
        source_ref::BIGINT AS task_id,
        count(*) AS provider_gate_count,
        count(*) FILTER (WHERE assignment_status = 'passed' AND assignment_allowed) AS passed_provider_gates,
        count(*) FILTER (WHERE assignment_status = 'approval_required') AS approval_required_provider_gates,
        count(*) FILTER (WHERE assignment_status = 'blocked') AS blocked_provider_gates,
        max(created_at) AS latest_provider_gate_at,
        jsonb_agg(
            jsonb_build_object(
                'id', id,
                'provider_kind', provider_kind,
                'provider_key', provider_key,
                'assignment_status', assignment_status,
                'assignment_allowed', assignment_allowed,
                'readiness_status', readiness_status,
                'inbox_item_id', inbox_item_id,
                'next_action', next_action
            )
            ORDER BY created_at DESC, id DESC
        ) AS provider_gate_evidence
    FROM latest_task_gates
    GROUP BY source_ref::BIGINT
)
SELECT
    task.id AS task_id,
    task.title,
    task.owner_agent,
    task.status AS task_status,
    coalesce(aggregated.provider_gate_count, 0) AS provider_gate_count,
    coalesce(aggregated.passed_provider_gates, 0) AS passed_provider_gates,
    coalesce(aggregated.approval_required_provider_gates, 0) AS approval_required_provider_gates,
    coalesce(aggregated.blocked_provider_gates, 0) AS blocked_provider_gates,
    CASE
        WHEN coalesce(aggregated.blocked_provider_gates, 0) > 0 THEN 'blocked'
        WHEN coalesce(aggregated.approval_required_provider_gates, 0) > 0 THEN 'approval_required'
        WHEN coalesce(aggregated.provider_gate_count, 0) > 0 THEN 'passed'
        ELSE 'not_checked'
    END AS provider_gate_status,
    aggregated.latest_provider_gate_at,
    coalesce(aggregated.provider_gate_evidence, '[]'::jsonb) AS provider_gate_evidence
FROM agent.tasks task
LEFT JOIN aggregated ON aggregated.task_id = task.id;

INSERT INTO agent.tool_registry (tool_name, tool_type, owning_agent, permission_level, enabled, description, config)
VALUES
    ('ai_os_evaluate_task_provider_gates', 'mcp_tool', 'Jarvis', 'write_db_manual_only', true,
     'Evaluate model/data-source provider gates for a specific agent task and update task status if blocked or approval-gated.',
     '{"function":"core.evaluate_task_provider_assignment_gates","reads":["agent.tasks","agent.profiles","core.v_provider_readiness_board"],"writes":["core.provider_assignment_gate_checks","agent.tasks","agent.inbox_items"],"live_execution_allowed":false,"seed_data_allowed":false}'::jsonb),
    ('ai_os_task_provider_gate_status', 'mcp_tool', 'Jarvis', 'read_only', true,
     'Read task-level provider gate status so agent workers cannot bypass model/data-source readiness controls.',
     '{"reads":["agent.v_task_provider_gate_status"],"live_execution_allowed":false}'::jsonb)
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
            'agent.trg_auto_gate_task_providers_after_insert',
            'core.evaluate_task_provider_assignment_gates',
            'agent.v_task_provider_gate_status'
        ]::TEXT[]) AS obj
    ),
    mcp_tools = ARRAY(
        SELECT DISTINCT tool
        FROM unnest(mcp_tools || ARRAY[
            'ai_os_evaluate_task_provider_gates',
            'ai_os_task_provider_gate_status'
        ]::TEXT[]) AS tool
    ),
    next_action = 'Task creation and worker execution must pass provider gates before agent work runs.',
    updated_at = now()
WHERE module_key IN ('runtime', 'automation', 'data_sources');

