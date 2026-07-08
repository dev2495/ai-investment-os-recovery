UPDATE agent.model_routes
SET default_model = 'qwen3:4b',
    notes = 'Lightweight always-on local driver for Charlie/Jarvis chat, routing, summaries, widget intents, and normal dashboard questions. Escalate heavy reasoning, coding, long filings, and critical portfolio decisions.'
WHERE route_name = 'always_on_daily_driver';

UPDATE agent.model_routes
SET default_model = 'qwen3:4b',
    notes = coalesce(notes, '') || ' Daily-driver route lowered to qwen3:4b for 24/7 local operation.'
WHERE route_name IN (
    'daily_brief',
    'jarvis_intake',
    'jarvis_runtime',
    'news_curation',
    'obsidian_retrieval_summary',
    'strategy_intake',
    'trade_journal_learning'
);

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model, escalation_provider,
    escalation_model, max_cost_tier, notes, enabled
)
VALUES
    (
        'local_workhorse_synthesis',
        'longer_local_synthesis',
        'ollama',
        'qwen3:8b',
        'codex_or_cloud',
        'frontier_on_approval',
        'local_plus',
        'On-demand local workhorse for longer summaries, research synthesis, and more complex agent outputs when qwen3:4b is too shallow.',
        true
    ),
    (
        'local_heavy_reasoning',
        'heavy_local_reasoning',
        'ollama',
        'qwen3:14b',
        'codex_or_cloud',
        'frontier_on_approval',
        'hybrid',
        'On-demand local heavy route for filings, strategy generation, and Charlie-style investment judgment. Do not keep resident by default on 16GB machines.',
        true
    )
ON CONFLICT (route_name) DO UPDATE SET
    task_class = EXCLUDED.task_class,
    default_provider = EXCLUDED.default_provider,
    default_model = EXCLUDED.default_model,
    escalation_provider = EXCLUDED.escalation_provider,
    escalation_model = EXCLUDED.escalation_model,
    max_cost_tier = EXCLUDED.max_cost_tier,
    notes = EXCLUDED.notes,
    enabled = EXCLUDED.enabled;
