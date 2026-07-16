UPDATE agent.local_model_registry
SET promotion_status = 'rejected',
    machine_profiles = ARRAY[]::TEXT[],
    allowed_task_classes = ARRAY['evaluation_baseline'],
    notes = 'Rejected for production placement: the Ollama 9B load did not complete within the bounded M4 16GB evaluation window. Use only for an explicit future benchmark.',
    updated_at = now()
WHERE model_name = 'qwen3.5:9b';

UPDATE agent.local_model_registry
SET provider = 'mlx',
    promotion_status = 'rejected',
    machine_profiles = ARRAY[]::TEXT[],
    allowed_task_classes = ARRAY['evaluation_baseline'],
    notes = 'Pinned MLX 4-bit revision evaluated locally and rejected: mid_v1 score 0.2857. It must not answer authoritative office tasks.',
    updated_at = now()
WHERE model_name = 'DreamFoundries/Qwen3.5-9B-4bit';

UPDATE agent.local_model_registry
SET promotion_status = 'rejected',
    machine_profiles = ARRAY[]::TEXT[],
    allowed_task_classes = ARRAY['evaluation_baseline'],
    notes = 'Rejected after multimodal_v1: score 0.0, incorrect chart symbol, 222461 ms median latency, and one timeout.',
    updated_at = now()
WHERE model_name = 'gemma4:e2b';

UPDATE agent.model_routes
SET default_provider = 'local_tools',
    default_model = CASE
        WHEN route_name = 'filing_analysis' THEN 'deterministic_filings_pipeline_v1'
        WHEN route_name = 'strategy_generation' THEN 'governed_strategy_pipeline_v1'
        WHEN route_name = 'multimodal_document_analysis' THEN 'deterministic_document_extraction_v1'
        ELSE 'deterministic_router_v1'
    END,
    notes = 'Fail-closed route reconciled after local model evaluations. Generative synthesis requires a separately approved future model or an approval-gated escalation.'
WHERE route_name IN (
    'charlie_munger_orchestration',
    'filing_analysis',
    'local_heavy_reasoning',
    'local_workhorse_synthesis',
    'multimodal_document_analysis',
    'research_company_analysis',
    'strategy_generation'
);
