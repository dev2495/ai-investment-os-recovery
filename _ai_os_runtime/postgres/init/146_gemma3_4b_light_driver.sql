INSERT INTO agent.local_model_registry (
    model_name, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES (
    'gemma3:4b', 'light', ARRAY['macbook','imac'], 8192, NULL, 'light_v1', 'candidate',
    ARRAY['routing','classification','short_summary','news_triage','tool_selection'],
    '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
    'Cross-family light candidate after Qwen3.5 2B and 4B failed evidence gates. No execution authority.',
    '[{"source":"_ai_os_runtime/config/local_models.json","runtime":"ollama","cross_family_challenger":true}]'::jsonb
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
    allowed_task_classes=ARRAY['evaluation_baseline'],
    notes='Rejected as daily driver after light_v1 score 0.50; retained as an evaluation baseline.',
    updated_at=now()
WHERE model_name='qwen3.5:4b';

UPDATE agent.model_routes
SET default_provider='ollama', default_model='gemma3:4b', max_cost_tier='local',
    notes='Gemma 3 4B cross-family candidate; exact digest and light_v1 promotion are mandatory.'
WHERE route_name IN (
    'always_on_daily_driver','daily_brief','jarvis_intake','jarvis_runtime','news_curation',
    'news_event_triage','obsidian_retrieval_summary','strategy_intake','trade_journal_learning'
);

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES (
    'ollama_gemma3_4b', 'Gemma 3 4B local daily driver candidate', 'ollama',
    'gemma3:4b', 'always_on_daily_driver', 'local', 'http://127.0.0.1:11434',
    'macbook_and_imac', 'configured', 8192, 3.3, 'local',
    ARRAY['text','vision','structured_output'], false, 'unchecked', 'AI Runtime Engineer',
    'Assignable only after light_v1 passes with the exact installed digest.',
    '{"num_parallel":1,"keep_alive":"5m","cross_family_challenger":true}'::jsonb
)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name,
    model_name=EXCLUDED.model_name,
    route_name=EXCLUDED.route_name,
    deployment_target=EXCLUDED.deployment_target,
    status=EXCLUDED.status,
    context_window=EXCLUDED.context_window,
    estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes,
    config=EXCLUDED.config,
    updated_at=now();
