INSERT INTO agent.local_model_registry (
    model_name, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'mlx-community/Qwen3.5-9B-OptiQ-4bit', 'mid', ARRAY['macbook'], 8192,
    NULL, 'mid_v1', 'candidate',
    ARRAY['filing_analysis','fundamental_research','strategy_research','paper_analysis','investment_memo'],
    '/Volumes/Devarsh SSD/AI OS Data/mlx/models',
    'On-demand Apple MLX research workhorse. Mixed 4/8-bit quantization, bounded 4096-token KV cache, no execution authority.',
    '[{"source":"mlx-community/Qwen3.5-9B-OptiQ-4bit","revision":"06cb56002678b3f0904d78b087faf63ce4b7024b","runtime":"mlx-lm==0.31.3","raw_prompt_stored":false}]'::jsonb
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
    allowed_task_classes=ARRAY['ollama_backend_baseline'],
    notes='Rejected for MacBook production placement after unbounded tensor-load latency in the Ollama multimodal package.',
    updated_at=now()
WHERE model_name='qwen3.5:9b';

UPDATE agent.model_routes
SET default_provider='mlx',
    default_model='mlx-community/Qwen3.5-9B-OptiQ-4bit',
    max_cost_tier='local_plus',
    notes='On-demand MLX workhorse; exact revision and mid_v1 promotion are mandatory.'
WHERE route_name IN (
    'local_workhorse_synthesis','local_heavy_reasoning','filings_analysis','filing_analysis',
    'research_company_analysis','strategy_generation','fundamental_research',
    'research_paper_analysis','investment_memo','portfolio_analysis'
);

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'mlx_qwen3_5_9b_optiq_4bit', 'MLX Qwen3.5 9B OptiQ workhorse', 'mlx',
    'mlx-community/Qwen3.5-9B-OptiQ-4bit', 'local_workhorse_synthesis', 'local',
    'http://127.0.0.1:11435/v1', 'macbook_m4_16gb_on_demand', 'configured',
    8192, 8.2, 'local_plus', ARRAY['text','tools','structured_output'], false,
    'unchecked', 'AI Runtime Engineer',
    'Revision-pinned MLX candidate. Assignable only after mid_v1 and backend latency gates pass.',
    '{"runtime":"mlx-lm==0.31.3","revision":"06cb56002678b3f0904d78b087faf63ce4b7024b","max_kv_size":4096,"prompt_cache":"public_static_prefix_only","on_demand":true}'::jsonb
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
