INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'Qwen/Qwen3-8B-MLX-4bit', 'mlx', 'mid', ARRAY['macbook'], 8192,
    NULL, 'mid_v1', 'candidate',
    ARRAY['conversation','filing_analysis','fundamental_research','strategy_research','paper_analysis','investment_memo'],
    '/Users/devarshthakkar/Library/Application Support/AIOS/models',
    'Official revision-pinned Qwen3 8B MLX 4-bit candidate for Charlie conversation and bounded synthesis. No calculation, approval, capital, or execution authority.',
    '[{"source":"Qwen/Qwen3-8B-MLX-4bit","revision":"383413e909f3bc5303ce195ebbdf0339c5a1a2a3","runtime":"mlx-lm==0.31.3","quantization":"4-bit","request_model":"default_model","raw_prompt_stored":false,"live_execution_allowed":false}]'::jsonb
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
    updated_at=now();

UPDATE agent.model_routes
SET default_provider='mlx',
    default_model='Qwen/Qwen3-8B-MLX-4bit',
    max_cost_tier='local_plus',
    notes='Private MacBook MLX route. Exact mid_v1 promotion is mandatory; deterministic fallback remains active.'
WHERE route_name IN ('charlie_munger_orchestration','local_workhorse_synthesis','local_heavy_reasoning');

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'mlx_qwen3_8b_official_4bit', 'MacBook Charlie Qwen3 8B MLX 4-bit', 'mlx',
    'Qwen/Qwen3-8B-MLX-4bit', 'charlie_munger_orchestration', 'tailscale_private',
    'http://100.75.156.32:11435/v1', 'macbook_m4_16gb_private', 'configured',
    8192, 4.4, 'local_plus', ARRAY['text','conversation','structured_output'], false,
    'unchecked', 'AI Runtime Engineer',
    'Private Tailscale-only model endpoint. Assignable only after exact mid_v1 pass; deterministic fallback applies while the MacBook is unavailable.',
    '{"runtime":"mlx-lm==0.31.3","revision":"383413e909f3bc5303ce195ebbdf0339c5a1a2a3","quantization":"4-bit","request_model":"default_model","prompt_cache_bytes":536870912,"live_execution_allowed":false}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
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
