BEGIN;

INSERT INTO agent.skills (
    skill_key, skill_name, skill_family, skill_type, owner_department, status,
    execution_mode, permission_level, trigger_phrases, input_sources,
    output_targets, required_tools, risk_notes, prompt_template, config
) VALUES
    (
        'tradingagents_verified_data_contract',
        'Verified Research Data Access Contract',
        'tradingagents', 'data_contract', 'data', 'active',
        'deterministic_contract', 'read_only',
        ARRAY['verify research data','data access contract','point in time source check'],
        ARRAY['source registry','event-time records','ingestion-time records','market calendar'],
        ARRAY['core.data_quality_runs','strategy.validation_reviews','agent.inbox_items'],
        ARRAY['postgres_read_model','data_quality_gate'],
        'Never accept a provider payload without source, as-of, availability-time, symbol, market, and freshness evidence. External provider breadth does not override licensing or privacy policy.',
        'Validate source identity, availability time, exchange-qualified symbol, benchmark mapping, freshness, and look-ahead boundaries before exposing data to an analyst or backtest.',
        '{"source_repo":"https://github.com/TauricResearch/TradingAgents","license":"Apache-2.0","adoption":"pattern","version_reviewed":"0.3.1","upstream_features":["verified_data_access_contract","provider_registry","fred","polymarket","alpha_vantage_lookahead_filter"],"broker_order_allowed":false}'::jsonb
    ),
    (
        'tradingagents_resilient_graph_runtime',
        'Resilient Checkpointed Agent Runtime',
        'tradingagents', 'agent_runtime', 'runtime', 'active',
        'internal_workflow', 'write_with_approval',
        ARRAY['resume agent workflow','recover committee','agent retry budget'],
        ARRAY['agent workflow state','typed node output','checkpoint metadata','retry budget'],
        ARRAY['agent.worker_runs','core.runtime_daemon_heartbeats','agent.inbox_items'],
        ARRAY['agent_worker_dispatch','postgres_read_model'],
        'Recovery may resume evidence-bound research work only. A changed graph shape, exhausted retry budget, or mismatched as-of packet must stop for review. No broker-order path.',
        'Checkpoint typed stage outputs, validate graph shape before resume, bound retries, preserve the original evidence packet, and fail closed to a human-review inbox item.',
        '{"source_repo":"https://github.com/TauricResearch/TradingAgents","license":"Apache-2.0","adoption":"pattern","version_reviewed":"0.3.1","upstream_features":["graph_router_crash_safety","graph_shape_aware_resume","configurable_retry_budget","ci_gate"],"broker_order_allowed":false}'::jsonb
    )
ON CONFLICT (skill_key) DO UPDATE SET
    skill_name=EXCLUDED.skill_name, skill_family=EXCLUDED.skill_family,
    skill_type=EXCLUDED.skill_type, owner_department=EXCLUDED.owner_department,
    status=EXCLUDED.status, execution_mode=EXCLUDED.execution_mode,
    permission_level=EXCLUDED.permission_level, trigger_phrases=EXCLUDED.trigger_phrases,
    input_sources=EXCLUDED.input_sources, output_targets=EXCLUDED.output_targets,
    required_tools=EXCLUDED.required_tools, risk_notes=EXCLUDED.risk_notes,
    prompt_template=EXCLUDED.prompt_template, config=EXCLUDED.config, updated_at=now();

INSERT INTO agent.agent_skill_map (agent_name, skill_key, proficiency, is_primary, activation_rules)
VALUES
    ('Data Steward','tradingagents_verified_data_contract','expert',false,'{"use_for":"external research provider and point-in-time source validation"}'::jsonb),
    ('Head of Quant','tradingagents_verified_data_contract','working',false,'{"use_for":"backtest input and benchmark validation"}'::jsonb),
    ('Automation Engineer','tradingagents_resilient_graph_runtime','expert',false,'{"use_for":"checkpoint and retry controls"}'::jsonb),
    ('Jarvis','tradingagents_resilient_graph_runtime','working',false,'{"use_for":"recoverable orchestration only"}'::jsonb)
ON CONFLICT (agent_name, skill_key) DO UPDATE SET
    proficiency=EXCLUDED.proficiency, is_primary=EXCLUDED.is_primary,
    activation_rules=EXCLUDED.activation_rules, updated_at=now();

UPDATE agent.skills
SET config = coalesce(config, '{}'::jsonb) || jsonb_build_object(
        'version_reviewed', '0.3.1',
        'upstream_correctness_controls', jsonb_build_array(
            'verified_data_access_contract',
            'alpha_vantage_lookahead_filter',
            'graph_router_crash_safety',
            'graph_shape_aware_checkpoint_resume',
            'configurable_retry_budget',
            'ci_gate'
        )
    ),
    updated_at=now()
WHERE skill_key IN (
    'tradingagents_checkpointed_committee',
    'tradingagents_outcome_reflection',
    'tradingagents_point_in_time_benchmarking'
);

UPDATE agent.workflow_registry
SET metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'source_pattern', 'TradingAgents 0.3.1',
        'verified_data_access_required', true,
        'graph_shape_resume_check_required', true,
        'retry_budget_required', true,
        'broker_order_allowed', false
    ),
    notes = 'Independent analysis, bounded bull/bear debate, independent risk challenge, typed decision, resumable state, verified data access, shape-safe recovery, and bounded retries. Human review is required; no order path.',
    updated_at=now()
WHERE workflow_key='checkpointed_research_committee';

UPDATE research.research_papers
SET title='TradingAgents 0.3.1 multi-agent research framework',
    metadata=coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
        'upstream_version_reviewed', '0.3.1',
        'upstream_reviewed_at', now(),
        'correctness_controls', jsonb_build_array(
            'verified_data_access_contract',
            'lookahead_filtering',
            'crash_safe_graph_router',
            'graph_shape_aware_resume',
            'retry_budget',
            'ci_gate'
        )
    ),
    updated_at=now()
WHERE source_url='https://raw.githubusercontent.com/TauricResearch/TradingAgents/main/README.md';

COMMIT;
