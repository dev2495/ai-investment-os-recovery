BEGIN;

INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'nanbeige/nanbeige4.2:3b-Q4_K_M', 'ollama', 'light', ARRAY['imac','macbook'], 8192,
    NULL, 'conversation_v1', 'candidate',
    ARRAY['conversation','task_intake','tool_selection','evidence_bound_summary','business_review_draft','deck_outline'],
    '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
    'Nanbeige4.2 compact agent candidate for natural conversation, governed tool intake, business-review drafts, and deck outlines. It has no calculation, research-authority, approval, capital, broker, or execution authority and is not assignable before exact-digest conversation_v1 promotion.',
    '[{"source":"https://huggingface.co/Nanbeige/Nanbeige4.2-3B","license":"Apache-2.0","architecture":"looped_transformer","ollama_tag":"nanbeige/nanbeige4.2:3b-Q4_K_M","quantization":"Q4_K_M","expected_disk_gb":2.6,"runtime_compatibility_probe_required":true,"eval_required":"conversation_v1","raw_prompt_stored":false,"capital_action_allowed":false,"live_execution_allowed":false}]'::jsonb
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
         AND agent.local_model_registry.eval_suite='conversation_v1'
        THEN agent.local_model_registry.promotion_status
        ELSE 'candidate'
    END,
    updated_at=now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES (
    'nanbeige42_local_assistant', 'conversation_governed_tools_and_business_drafts',
    'ollama', 'nanbeige/nanbeige4.2:3b-Q4_K_M',
    'openrouter', 'z-ai/glm-4.7-flash', 'local',
    'Disabled until the exact installed digest passes conversation_v1. Deterministic tools remain authoritative; business reviews and deck outlines require source evidence and independent review.',
    false
)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class,
    default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model,
    escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model,
    max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes,
    enabled=CASE
        WHEN EXISTS (
            SELECT 1 FROM agent.local_model_registry
            WHERE model_name='nanbeige/nanbeige4.2:3b-Q4_K_M'
              AND promotion_status='approved'
              AND eval_suite='conversation_v1'
              AND coalesce(last_eval_score,0) >= 0.8
        ) THEN agent.model_routes.enabled
        ELSE false
    END;

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'ollama_nanbeige42_3b_q4_imac', 'iMac Nanbeige4.2 3B Q4 candidate',
    'ollama', 'nanbeige/nanbeige4.2:3b-Q4_K_M', 'nanbeige42_local_assistant', 'local',
    'http://127.0.0.1:11434', 'imac_m1_8gb', 'configured', 8192, 2.6,
    'local', ARRAY['text','conversation','tools','structured_output','business_review_draft','deck_outline'], false,
    'unchecked', 'AI Runtime Engineer',
    'Candidate only. Requires Nanbeige-compatible Ollama runtime, exact digest capture, conversation_v1 pass, and median latency within 30 seconds before activation.',
    '{"num_parallel":1,"keep_alive":"10m","context_tokens":8192,"max_output_tokens":384,"raw_prompt_stored":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    base_url=EXCLUDED.base_url,
    deployment_target=EXCLUDED.deployment_target,
    status=CASE
        WHEN agent.model_endpoints.health_status='model_unavailable'
        THEN agent.model_endpoints.status
        ELSE EXCLUDED.status
    END,
    context_window=EXCLUDED.context_window,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=agent.model_endpoints.config || EXCLUDED.config,
    updated_at=now();

COMMIT;
