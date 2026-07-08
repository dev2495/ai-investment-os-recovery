UPDATE agent.model_routes
SET default_provider = 'ollama',
    default_model = 'llama3.2:3b',
    escalation_provider = 'codex_or_cloud',
    escalation_model = 'frontier_on_approval',
    max_cost_tier = 'local_plus',
    notes = 'Always-on local driver switched to llama3.2:3b after direct Ollama test completed in about 5 seconds. qwen3:4b was installed but timed out over 120 seconds on this machine, so keep it out of the 24/7 path.',
    enabled = true
WHERE route_name = 'always_on_daily_driver';

UPDATE agent.model_routes
SET default_provider = 'ollama',
    default_model = 'llama3.2:3b',
    escalation_provider = coalesce(nullif(escalation_provider, ''), 'codex_or_cloud'),
    escalation_model = coalesce(nullif(escalation_model, ''), 'frontier_on_approval'),
    notes = coalesce(notes, '') || ' Local light route switched to llama3.2:3b after qwen3:4b latency timeout test; use heavier Qwen/Codex routes only on explicit escalation.'
WHERE route_name IN (
    'daily_brief',
    'jarvis_intake',
    'jarvis_runtime',
    'news_curation',
    'obsidian_retrieval_summary',
    'strategy_intake',
    'trade_journal_learning'
);
