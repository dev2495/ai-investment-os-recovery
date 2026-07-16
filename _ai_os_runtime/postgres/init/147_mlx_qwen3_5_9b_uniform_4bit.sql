INSERT INTO agent.local_model_registry (
    model_name, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'DreamFoundries/Qwen3.5-9B-4bit', 'mid', ARRAY['macbook'], 8192,
    NULL, 'mid_v1', 'candidate',
    ARRAY['filing_analysis','fundamental_research','strategy_research','paper_analysis','investment_memo'],
    '/Volumes/Devarsh SSD/AI OS Data/mlx/models',
    'On-demand MLX-LM affine 4-bit research candidate. Lower memory placement than the unavailable OptiQ artifact; no execution authority.',
    '[{"source":"DreamFoundries/Qwen3.5-9B-4bit","revision":"20353927abe35e90c459ee908fac8806e5edd455","runtime":"mlx-lm==0.31.3","quantization":"4-bit group-size 64","raw_prompt_stored":false}]'::jsonb
)
ON CONFLICT (model_name) DO UPDATE SET
    deployment_tier=EXCLUDED.deployment_tier,
    machine_profiles=EXCLUDED.machine_profiles,
    context_tokens=EXCLUDED.context_tokens,
    eval_suite=EXCLUDED.eval_suite,
    allowed_task_classes=EXCLUDED.allowed_task_classes,
    storage_root=EXCLUDED.storage_root,
    notes=EXCLUDED.notes,
    evidence=EXCLUDED.evidence,
    updated_at=now();

UPDATE agent.local_model_registry
SET deployment_tier='experimental', machine_profiles=ARRAY[]::TEXT[],
    allowed_task_classes=ARRAY['unavailable_artifact_baseline'], promotion_status='rejected',
    notes='OptiQ candidate unavailable after repeated pinned-shard gateway failures; partial artifact is not assignable.',
    updated_at=now()
WHERE model_name='mlx-community/Qwen3.5-9B-OptiQ-4bit';

UPDATE agent.model_routes
SET default_provider='mlx', default_model='DreamFoundries/Qwen3.5-9B-4bit',
    max_cost_tier='local_plus',
    notes='Revision-pinned MLX affine 4-bit workhorse; mid_v1 promotion is mandatory.'
WHERE default_model='mlx-community/Qwen3.5-9B-OptiQ-4bit'
   OR route_name IN ('local_workhorse_synthesis','local_heavy_reasoning');

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'mlx_qwen3_5_9b_uniform_4bit', 'MLX Qwen3.5 9B affine 4-bit workhorse', 'mlx',
    'DreamFoundries/Qwen3.5-9B-4bit', 'local_workhorse_synthesis', 'local',
    'http://127.0.0.1:11435/v1', 'macbook_m4_16gb_on_demand', 'configured',
    8192, 5.1, 'local_plus', ARRAY['text','tools','structured_output'], false,
    'unchecked', 'AI Runtime Engineer',
    'Revision-pinned MLX candidate; assignable only after mid_v1 and measured latency pass.',
    '{"runtime":"mlx-lm==0.31.3","revision":"20353927abe35e90c459ee908fac8806e5edd455","quantization":"4-bit group-size 64","prompt_cache_bytes":1073741824,"on_demand":true}'::jsonb
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
