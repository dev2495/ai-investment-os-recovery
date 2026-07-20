INSERT INTO agent.local_model_registry (
    model_name, provider, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'prism-ml/Bonsai-27B-Q1_0', 'local_openai', 'mid', ARRAY['macbook'], 8192,
    NULL, 'mid_v1', 'candidate',
    ARRAY['conversation','filing_analysis','fundamental_research','strategy_research','paper_analysis','investment_memo'],
    '/Users/devarshthakkar/Library/Application Support/AIOS/models',
    'Bonsai 27B native Q1_0 candidate served by the official PrismML custom llama.cpp Metal build. No calculation, approval, capital, or execution authority.',
    '[{"source":"prism-ml/Bonsai-27B-gguf","revision":"f10afb355f104535e3e3e98cf7ab7795c72bd292","runtime":"PrismML llama.cpp prism-b9596-9fcaed7","quantization":"Q1_0","request_model":"default_model","context_tokens":8192,"reasoning_exposed":false,"raw_prompt_stored":false,"live_execution_allowed":false}]'::jsonb
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

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'bonsai_27b_q1_local_openai', 'MacBook Bonsai 27B Q1_0', 'local_openai',
    'prism-ml/Bonsai-27B-Q1_0', 'charlie_munger_orchestration', 'tailscale_private',
    'http://100.75.156.32:11435/v1', 'macbook_m4_16gb_private', 'configured',
    8192, 3.9, 'local_plus', ARRAY['text','conversation','structured_output'], false,
    'unchecked', 'AI Runtime Engineer',
    'Private Tailscale-only candidate. Assignable only after exact mid_v1 pass; deterministic fallback remains mandatory while unavailable.',
    '{"runtime":"PrismML llama.cpp prism-b9596-9fcaed7","revision":"f10afb355f104535e3e3e98cf7ab7795c72bd292","quantization":"Q1_0","request_model":"default_model","reasoning":"off","context_tokens":8192,"live_execution_allowed":false}'::jsonb
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
