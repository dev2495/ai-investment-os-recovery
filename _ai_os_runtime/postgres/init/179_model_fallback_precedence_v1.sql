BEGIN;

UPDATE agent.model_routes
SET escalation_provider='openrouter',
    escalation_model='openai/gpt-5.6-luna',
    notes='Private iMac fallback. Deterministic tools remain authoritative; Luna escalation is separately privacy-gated and budgeted.'
WHERE route_name='nanbeige42_local_assistant';

CREATE OR REPLACE FUNCTION agent.activate_final_local_model_fleet()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    qwen9_ready BOOLEAN;
    nanbeige_ready BOOLEAN;
    qwen2_ready BOOLEAN;
    bonsai_ready BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM agent.local_model_registry registry
        JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name
        WHERE registry.model_name='mlx-community/Qwen3.5-9B-4bit'
          AND registry.promotion_status='approved'
          AND registry.eval_suite='conversation_v1'
          AND registry.last_eval_score >= 0.8
          AND endpoint.endpoint_key='local_openai_qwen35_9b_mlx_vlm'
          AND endpoint.health_status IN ('healthy','ready','active')
    ) INTO qwen9_ready;

    SELECT EXISTS (
        SELECT 1
        FROM agent.local_model_registry registry
        JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name
        WHERE registry.model_name='nanbeige/nanbeige4.2:3b-Q4_K_M'
          AND registry.promotion_status='approved'
          AND registry.eval_suite='conversation_v1'
          AND registry.last_eval_score >= 0.8
          AND endpoint.endpoint_key='nanbeige42_3b_q4_local_openai_imac'
          AND endpoint.health_status IN ('healthy','ready','active')
    ) INTO nanbeige_ready;

    SELECT EXISTS (
        SELECT 1
        FROM agent.local_model_registry registry
        JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name
        WHERE registry.model_name='mlx-community/Qwen3.5-2B-4bit'
          AND registry.promotion_status='approved'
          AND registry.eval_suite='conversation_v1'
          AND registry.last_eval_score >= 0.8
          AND endpoint.endpoint_key='local_openai_qwen35_2b_mlx_vlm_imac'
          AND endpoint.health_status IN ('healthy','ready','active')
    ) INTO qwen2_ready;

    SELECT EXISTS (
        SELECT 1
        FROM agent.local_model_registry
        WHERE model_name='prism-ml/Bonsai-27B-Q1_0'
          AND promotion_status='approved'
          AND eval_suite='conversation_v1'
          AND last_eval_score >= 0.8
    ) INTO bonsai_ready;

    IF qwen9_ready THEN
        UPDATE agent.model_routes
        SET default_provider='local_openai',
            default_model='mlx-community/Qwen3.5-9B-4bit',
            escalation_provider='openrouter',
            escalation_model='openai/gpt-5.6-luna',
            max_cost_tier='local_plus',
            notes='Qualified MacBook private conversation route. Deterministic engines retain calculations, source precedence, risk, capital, approvals, and execution.'
        WHERE route_name='charlie_munger_orchestration';
    ELSIF bonsai_ready THEN
        UPDATE agent.model_routes
        SET default_provider='local_openai',
            default_model='prism-ml/Bonsai-27B-Q1_0',
            escalation_provider='openrouter',
            escalation_model='openai/gpt-5.6-luna',
            max_cost_tier='local_plus',
            notes='Qwen3.5 primary is unavailable; evaluated Bonsai conversation rollback is active.'
        WHERE route_name='charlie_munger_orchestration';
    ELSE
        UPDATE agent.model_routes
        SET default_provider='local_tools',
            default_model='deterministic_router_v1',
            escalation_provider='openrouter',
            escalation_model='openai/gpt-5.6-luna',
            max_cost_tier='local',
            notes='No evaluated private conversation model is healthy; deterministic fail-closed route is active.'
        WHERE route_name='charlie_munger_orchestration';
    END IF;

    UPDATE agent.agent_model_assignments
    SET primary_route='charlie_munger_orchestration',
        fallback_route=CASE
          WHEN nanbeige_ready THEN 'nanbeige42_local_assistant'
          WHEN qwen2_ready THEN 'imac_qwen35_2b_private'
          WHEN bonsai_ready AND qwen9_ready THEN 'macbook_bonsai_rollback'
          ELSE NULL
        END,
        escalation_route='openrouter_luna_volume',
        cost_policy='local_first_luna_volume_terra_sol_explicit',
        max_autonomous_cost_tier='cloud_low',
        updated_at=now()
    WHERE agent_name='Charlie Munger';

    RETURN jsonb_build_object(
        'qwen9_ready', qwen9_ready,
        'nanbeige_ready', nanbeige_ready,
        'qwen2_ready', qwen2_ready,
        'bonsai_ready', bonsai_ready,
        'fallback_precedence', jsonb_build_array('nanbeige42_local_assistant','imac_qwen35_2b_private','macbook_bonsai_rollback'),
        'broker_writes_allowed', false,
        'client_private_cloud_allowed', false
    );
END;
$$;

COMMIT;
