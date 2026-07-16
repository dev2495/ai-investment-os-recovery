UPDATE agent.local_model_registry
SET deployment_tier='experimental', machine_profiles=ARRAY[]::TEXT[],
    allowed_task_classes=ARRAY['evaluation_baseline'],
    notes='Rejected after light_v1 score 0.25; no small generative model is approved for the always-on lane.',
    updated_at=now()
WHERE model_name='gemma3:4b';

UPDATE agent.model_routes
SET default_provider='local_tools', default_model='deterministic_router_v1',
    max_cost_tier='local',
    notes='Fail-closed deterministic route. Generative work escalates to the approved MLX workhorse when available.'
WHERE route_name IN (
    'always_on_daily_driver','daily_brief','jarvis_intake','jarvis_runtime','news_curation',
    'news_event_triage','obsidian_retrieval_summary','strategy_intake','trade_journal_learning'
);
