BEGIN;

UPDATE agent.model_endpoints
SET status='disabled',
    health_status='superseded',
    last_error='Stock Ollama does not ship the Nanbeige4.2 architecture. Replaced by the pinned isolated local_openai runtime.',
    updated_at=now()
WHERE endpoint_key='ollama_nanbeige42_3b_q4_imac';

INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'nanbeige/nanbeige4.2:3b-Q4_K_M', 'local_openai', 'light', ARRAY['imac'], 8192,
    NULL, 'conversation_v1', 'candidate',
    ARRAY['conversation','task_intake','tool_selection','evidence_bound_summary','business_review_draft','deck_outline'],
    '/Volumes/Devarsh SSD/AI OS Data/models/nanbeige42-runtime',
    'Nanbeige4.2 compact assistant served by its pinned official llama.cpp fork on loopback only. It has no calculation, research-authority, approval, capital, broker, or execution authority.',
    '[{"source":"https://huggingface.co/Nanbeige/Nanbeige4.2-3B","model_revision":"f56ec5a9650268aa098496734743c25ea778bd2d","runtime_source":"https://github.com/Nanbeige/llama.cpp/tree/nanbeige42","runtime_revision":"c6640a1c0cf7b38df342b67021a3900b04d092e7","license":"Apache-2.0","quantization":"Q4_K_M","request_model":"nanbeige/nanbeige4.2:3b-Q4_K_M","eval_required":"conversation_v1","raw_prompt_stored":false,"capital_action_allowed":false,"live_execution_allowed":false}]'::jsonb
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
    'local_openai', 'nanbeige/nanbeige4.2:3b-Q4_K_M',
    'openrouter', 'z-ai/glm-4.7-flash', 'local',
    'Private iMac loopback assistant. Deterministic tools remain authoritative; cloud escalation is separately consented and budgeted.',
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
    'nanbeige42_3b_q4_local_openai_imac', 'iMac Nanbeige4.2 3B Q4 isolated',
    'local_openai', 'nanbeige/nanbeige4.2:3b-Q4_K_M', 'nanbeige42_local_assistant', 'local',
    'http://127.0.0.1:11436/v1', 'imac_m1_8gb', 'configured', 8192, 2.6,
    'local', ARRAY['text','conversation','tools','structured_output','business_review_draft','deck_outline'], false,
    'unchecked', 'AI Runtime Engineer',
    'Loopback-only pinned Nanbeige llama.cpp service. It must pass conversation_v1 before assignment.',
    '{"request_model":"nanbeige/nanbeige4.2:3b-Q4_K_M","runtime":"Nanbeige llama.cpp","runtime_revision":"c6640a1c0cf7b38df342b67021a3900b04d092e7","model_revision":"f56ec5a9650268aa098496734743c25ea778bd2d","quantization":"Q4_K_M","num_parallel":1,"context_tokens":8192,"max_output_tokens":384,"raw_prompt_stored":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    endpoint_type=EXCLUDED.endpoint_type,
    base_url=EXCLUDED.base_url,
    deployment_target=EXCLUDED.deployment_target,
    context_window=EXCLUDED.context_window,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=agent.model_endpoints.config || EXCLUDED.config,
    status=CASE
        WHEN agent.model_endpoints.health_status IN ('healthy','eval_failed','runtime_failed')
        THEN agent.model_endpoints.status
        ELSE EXCLUDED.status
    END,
    updated_at=now();

COMMIT;
