BEGIN;

INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'qwen3:4b', 'ollama', 'light', ARRAY['imac'], 8192,
    NULL, 'conversation_v1', 'candidate',
    ARRAY['conversation','task_intake','tool_selection','evidence_bound_summary'],
    '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
    'Always-on iMac assistant. It may converse, intake tasks, select allowlisted tools, and summarize supplied evidence. It has no calculation, research-authority, capital, approval, broker, or execution authority.',
    '[{"source":"https://ollama.com/library/qwen3:4b","model_tag":"qwen3:4b","expected_disk_gb":2.5,"license":"Apache-2.0","eval_required":"conversation_v1","approved_digest":"359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7","raw_prompt_stored":false,"live_execution_allowed":false}]'::jsonb
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
    'imac_basic_assistant_qwen3', 'conversation_and_governed_tool_intake',
    'ollama', 'qwen3:4b', 'openrouter', 'z-ai/glm-4.7-flash', 'local',
    'Always-on private iMac fallback. Assignable only after exact conversation_v1 promotion. Tools validate all arguments; no investment or execution authority.',
    true
)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class,
    default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model,
    escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model,
    max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes,
    enabled=true;

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'ollama_qwen3_4b_imac', 'iMac Qwen3 4B always-on assistant',
    'ollama', 'qwen3:4b', 'imac_basic_assistant_qwen3', 'local',
    'http://127.0.0.1:11434', 'imac_m1_8gb', 'configured', 8192, 2.5,
    'local', ARRAY['text','conversation','tools','structured_output'], false,
    'unchecked', 'AI Runtime Engineer',
    'Assignable only after conversation_v1 passes for the installed digest. Concurrency one and 8K context.',
    '{"num_parallel":1,"keep_alive":"10m","raw_prompt_stored":false,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    base_url=EXCLUDED.base_url,
    deployment_target=EXCLUDED.deployment_target,
    status=EXCLUDED.status,
    context_window=EXCLUDED.context_window,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();

COMMIT;
