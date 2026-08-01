BEGIN;

INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES
    (
      'mlx-community/Qwen3.5-9B-4bit', 'local_openai', 'mid', ARRAY['macbook'], 8192,
      NULL, 'conversation_v1', 'candidate',
      ARRAY['conversation','task_intake','tool_selection','evidence_bound_summary'],
      '/Users/devarshthakkar/Library/Application Support/AIOS/models',
      'Pinned MLX-VLM Qwen3.5 9B for private conversation, task intake, and tool selection only. It passed conversation_v1 but failed mid_v1, so deterministic engines retain research calculation, source precedence, risk, approval, capital, and execution authority.',
      '[{"source":"https://huggingface.co/mlx-community/Qwen3.5-9B-4bit","revision":"8b2b98c00a6b4d291155e4890773ca8f769aee53","runtime":"mlx-vlm==0.6.6","quantization":"4-bit group-size 64; unquantized KV cache","disk_bytes":5970210415,"conversation_v1_score":1.0,"conversation_v1_hard_failures":0,"mid_v1_score":0.7143,"mid_v1_allowed":false,"license":"Apache-2.0","raw_prompt_stored":false,"live_execution_allowed":false}]'::jsonb
    ),
    (
      'mlx-community/Qwen3.5-2B-4bit', 'local_openai', 'light', ARRAY['imac'], 8192,
      NULL, 'conversation_v1', 'candidate',
      ARRAY['conversation','task_intake','tool_selection','evidence_bound_summary'],
      '/Volumes/Devarsh SSD/AI OS Data/mlx/models',
      'Pinned MLX-VLM Qwen3.5 2B candidate for the always-on iMac fallback. It has no research, calculation, approval, capital, or execution authority.',
      '[{"source":"https://huggingface.co/mlx-community/Qwen3.5-2B-4bit","revision":"674aaa7240b91e8012fcad5d791b7dfe5ba90207","runtime":"mlx-vlm==0.6.6","quantization":"4-bit group-size 64; unquantized KV cache","disk_bytes":1742261128,"license":"Apache-2.0","raw_prompt_stored":false,"live_execution_allowed":false}]'::jsonb
    )
ON CONFLICT (model_name) DO UPDATE SET
    provider=EXCLUDED.provider,
    deployment_tier=EXCLUDED.deployment_tier,
    machine_profiles=EXCLUDED.machine_profiles,
    context_tokens=EXCLUDED.context_tokens,
    eval_suite=EXCLUDED.eval_suite,
    allowed_task_classes=EXCLUDED.allowed_task_classes,
    storage_root=EXCLUDED.storage_root,
    notes=EXCLUDED.notes,
    evidence=EXCLUDED.evidence,
    promotion_status=CASE
      WHEN agent.local_model_registry.last_eval_score >= 0.8
       AND agent.local_model_registry.promotion_status='approved'
      THEN 'approved'
      WHEN agent.local_model_registry.last_eval_score IS NOT NULL
      THEN agent.local_model_registry.promotion_status
      ELSE 'candidate'
    END,
    updated_at=now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES
    ('macbook_qwen35_9b_private','private_conversation_and_tool_intake','local_openai','mlx-community/Qwen3.5-9B-4bit','openrouter','openai/gpt-5.6-luna','local_plus','MacBook M4 private Qwen3.5 conversation route. Research, arithmetic, source precedence, and capital decisions remain tool-owned.',true),
    ('imac_qwen35_2b_private','always_on_private_conversation_and_tool_intake','local_openai','mlx-community/Qwen3.5-2B-4bit','openrouter','openai/gpt-5.6-luna','local','iMac M1 private fallback. Evaluation approval is mandatory before assignment.',true),
    ('macbook_bonsai_rollback','private_conversation_rollback','local_openai','prism-ml/Bonsai-27B-Q1_0','openrouter','openai/gpt-5.6-luna','local_plus','Known conversation-only rollback route; no research authority.',true),
    ('openrouter_terra_research','deep_public_internal_research_and_synthesis','openrouter','openai/gpt-5.6-terra','openrouter','openai/gpt-5.6-sol','cloud_medium','Explicit operator selection only. No client-private context; ZDR and global budget gates apply.',true),
    ('openrouter_sol_review','rare_frontier_committee_review','openrouter','openai/gpt-5.6-sol',NULL,NULL,'frontier','Rare explicit independent review. No client-private context; ZDR and global budget gates apply.',true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class,
    default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model,
    escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model,
    max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes,
    enabled=EXCLUDED.enabled;

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES
    ('local_openai_qwen35_9b_mlx_vlm','MacBook Qwen3.5 9B MLX-VLM','local_openai','mlx-community/Qwen3.5-9B-4bit','macbook_qwen35_9b_private','tailscale_private','http://100.75.156.32:11436/v1','macbook_m4_16gb_private','configured',8192,5.95,'local_plus',ARRAY['text','conversation','tools','structured_output'],false,'unchecked','AI Runtime Engineer','Conversation-only qualification endpoint; Bonsai remains available as rollback.','{"runtime":"MLX-VLM","runtime_version":"0.6.6","model_revision":"8b2b98c00a6b4d291155e4890773ca8f769aee53","request_model":"/Users/devarshthakkar/Library/Application Support/AIOS/models/qwen3.5-9b-4bit-8b2b98c","max_output_tokens":1200,"enable_thinking":false,"kv_cache_quantization":false,"max_kv_size":8192,"apc_enabled":true,"raw_prompt_stored":false,"live_execution_allowed":false}'::jsonb),
    ('local_openai_qwen35_2b_mlx_vlm_imac','iMac Qwen3.5 2B MLX-VLM','local_openai','mlx-community/Qwen3.5-2B-4bit','imac_qwen35_2b_private','local','http://127.0.0.1:11436/v1','imac_m1_8gb_ssd','configured',8192,1.72,'local',ARRAY['text','conversation','tools','structured_output'],false,'unchecked','AI Runtime Engineer','Always-on candidate stored on the external SSD; one concurrent request and 4K KV window.','{"runtime":"MLX-VLM","runtime_version":"0.6.6","model_revision":"674aaa7240b91e8012fcad5d791b7dfe5ba90207","request_model":"/Volumes/Devarsh SSD/AI OS Data/mlx/models/qwen3.5-2b-4bit-674aaa7","max_output_tokens":600,"enable_thinking":false,"kv_cache_quantization":false,"max_kv_size":4096,"raw_prompt_stored":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    endpoint_type=EXCLUDED.endpoint_type,
    base_url=EXCLUDED.base_url,
    deployment_target=EXCLUDED.deployment_target,
    status=CASE WHEN agent.model_endpoints.health_status='healthy' THEN agent.model_endpoints.status ELSE EXCLUDED.status END,
    context_window=EXCLUDED.context_window,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();

INSERT INTO agent.model_cost_rates (
    provider, model_name, cost_tier, input_usd_per_1m_tokens,
    output_usd_per_1m_tokens, rate_source, status, effective_at, notes, metadata
)
SELECT row_values.*
FROM (
    VALUES
      ('openrouter','openai/gpt-5.6-terra','cloud_medium',1.25::numeric,7.50::numeric,'openrouter_promo_2026_08_02','active','2026-08-02T00:00:00Z'::timestamptz,'Explicit deep research route under the shared hard cap.','{"zdr":true,"data_collection":"deny","autonomous_eligible":false,"source":"https://openrouter.ai/openai/gpt-5.6-terra"}'::jsonb),
      ('openrouter','openai/gpt-5.6-sol','frontier',5.00::numeric,30.00::numeric,'openrouter_2026_08_02','active','2026-08-02T00:00:00Z'::timestamptz,'Rare frontier review route under the shared hard cap.','{"zdr":true,"data_collection":"deny","autonomous_eligible":false,"source":"https://openrouter.ai/openai/gpt-5.6-sol"}'::jsonb)
) AS row_values(provider,model_name,cost_tier,input_usd_per_1m_tokens,output_usd_per_1m_tokens,rate_source,status,effective_at,notes,metadata)
WHERE NOT EXISTS (
    SELECT 1 FROM agent.model_cost_rates current_rate
    WHERE current_rate.provider=row_values.provider
      AND current_rate.model_name=row_values.model_name
      AND current_rate.effective_at=row_values.effective_at
);

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, secret_ref, health_status,
    owner_agent, notes, config
) VALUES
    ('openrouter_gpt_5_6_terra','OpenRouter GPT-5.6 Terra','openrouter','openai/gpt-5.6-terra','openrouter_terra_research','cloud','https://openrouter.ai/api/v1','managed_cloud','configured',1000000,0,'cloud_medium',ARRAY['text','tools','structured_output','deep_research'],true,'AI_OS_OPENROUTER_API_KEY','configured','AI Runtime Engineer','Explicit deep route using the existing gateway credential.','{"zdr":true,"data_collection":"deny","reasoning_effort":"medium","raw_prompt_stored":false,"client_data_allowed":false,"live_execution_allowed":false}'::jsonb),
    ('openrouter_gpt_5_6_sol','OpenRouter GPT-5.6 Sol','openrouter','openai/gpt-5.6-sol','openrouter_sol_review','cloud','https://openrouter.ai/api/v1','managed_cloud','configured',1000000,0,'frontier',ARRAY['text','tools','structured_output','frontier_review'],true,'AI_OS_OPENROUTER_API_KEY','configured','AI Runtime Engineer','Rare explicit review route using the existing gateway credential.','{"zdr":true,"data_collection":"deny","reasoning_effort":"high","raw_prompt_stored":false,"client_data_allowed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    cost_tier=EXCLUDED.cost_tier,
    capabilities=EXCLUDED.capabilities,
    secret_ref=EXCLUDED.secret_ref,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();

UPDATE agent.model_routes
SET enabled=false,
    notes=coalesce(notes,'') || ' Superseded by the GPT-5.6 Terra/Sol ladder on 2026-08-02.'
WHERE route_name IN ('openrouter_research_deep','openrouter_research_review');

UPDATE agent.agent_model_assignments
SET escalation_route='openrouter_luna_volume',
    cost_policy='local_first_luna_volume_terra_sol_explicit',
    max_autonomous_cost_tier='cloud_low',
    escalation_triggers=ARRAY['local_unavailable','local_eval_blocked','public_internal_volume','operator_selected_cloud'],
    notes='Private and client context stays local. Luna is capped volume. Terra and Sol require explicit selection and never receive client-private data.',
    updated_at=now()
WHERE agent_name='Charlie Munger';

CREATE OR REPLACE FUNCTION agent.activate_final_local_model_fleet()
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    qwen9_ready BOOLEAN;
    qwen2_ready BOOLEAN;
    bonsai_ready BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM agent.local_model_registry registry
        JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name
        WHERE registry.model_name='mlx-community/Qwen3.5-9B-4bit'
          AND registry.promotion_status='approved'
          AND registry.eval_suite='conversation_v1'
          AND registry.last_eval_score >= 0.8
          AND endpoint.endpoint_key='local_openai_qwen35_9b_mlx_vlm'
          AND endpoint.health_status IN ('healthy','ready','active')
    ) INTO qwen9_ready;

    SELECT EXISTS (
        SELECT 1 FROM agent.local_model_registry registry
        JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name
        WHERE registry.model_name='mlx-community/Qwen3.5-2B-4bit'
          AND registry.promotion_status='approved'
          AND registry.eval_suite='conversation_v1'
          AND registry.last_eval_score >= 0.8
          AND endpoint.endpoint_key='local_openai_qwen35_2b_mlx_vlm_imac'
          AND endpoint.health_status IN ('healthy','ready','active')
    ) INTO qwen2_ready;

    SELECT EXISTS (
        SELECT 1 FROM agent.local_model_registry
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
            notes='Activated only after exact-revision conversation_v1 promotion and endpoint health verification. Research and calculations remain tool-owned.'
        WHERE route_name='charlie_munger_orchestration';
    ELSIF bonsai_ready THEN
        UPDATE agent.model_routes
        SET default_provider='local_openai',
            default_model='prism-ml/Bonsai-27B-Q1_0',
            max_cost_tier='local_plus',
            notes='Qwen3.5 qualification incomplete; retaining the evaluated Bonsai conversation rollback.'
        WHERE route_name='charlie_munger_orchestration';
    ELSE
        UPDATE agent.model_routes
        SET default_provider='local_tools',
            default_model='deterministic_router_v1',
            max_cost_tier='local',
            notes='No evaluated private conversation model is healthy; deterministic fail-closed route is active.'
        WHERE route_name='charlie_munger_orchestration';
    END IF;

    UPDATE agent.agent_model_assignments
    SET primary_route='charlie_munger_orchestration',
        fallback_route=CASE
          WHEN qwen2_ready THEN 'imac_qwen35_2b_private'
          WHEN bonsai_ready AND qwen9_ready THEN 'macbook_bonsai_rollback'
          ELSE fallback_route
        END,
        escalation_route='openrouter_luna_volume',
        updated_at=now()
    WHERE agent_name='Charlie Munger';

    RETURN jsonb_build_object(
        'qwen9_ready',qwen9_ready,
        'qwen2_ready',qwen2_ready,
        'bonsai_ready',bonsai_ready,
        'broker_writes_allowed',false,
        'client_private_cloud_allowed',false
    );
END;
$$;

COMMIT;
