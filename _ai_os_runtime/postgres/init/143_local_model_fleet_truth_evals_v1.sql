CREATE TABLE IF NOT EXISTS agent.local_model_registry (
    model_name TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'ollama',
    deployment_tier TEXT NOT NULL CHECK (deployment_tier IN ('light','mid','retrieval','specialist','rollback','experimental')),
    machine_profiles TEXT[] NOT NULL DEFAULT '{}',
    context_tokens INTEGER NOT NULL CHECK (context_tokens > 0),
    vector_dimensions INTEGER,
    eval_suite TEXT NOT NULL,
    promotion_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (promotion_status IN ('candidate','evaluating','approved','rejected','rollback_only','held','retired')),
    allowed_task_classes TEXT[] NOT NULL DEFAULT '{}',
    storage_root TEXT NOT NULL,
    model_digest TEXT,
    last_eval_run_key TEXT,
    last_eval_score NUMERIC,
    last_eval_at TIMESTAMPTZ,
    notes TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent.local_model_eval_runs (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL UNIQUE,
    model_name TEXT NOT NULL REFERENCES agent.local_model_registry(model_name) ON DELETE RESTRICT,
    suite_name TEXT NOT NULL,
    runtime_provider TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','passed','failed','error')),
    score NUMERIC NOT NULL DEFAULT 0,
    hard_failure_count INTEGER NOT NULL DEFAULT 0,
    median_latency_ms INTEGER,
    artifact_path TEXT NOT NULL,
    model_digest TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT chk_local_eval_no_capital CHECK (capital_action_allowed=false),
    CONSTRAINT chk_local_eval_no_execution CHECK (live_execution_allowed=false)
);

CREATE TABLE IF NOT EXISTS agent.local_model_eval_results (
    id BIGSERIAL PRIMARY KEY,
    run_key TEXT NOT NULL REFERENCES agent.local_model_eval_runs(run_key) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    category TEXT,
    passed BOOLEAN NOT NULL,
    latency_ms INTEGER,
    failures JSONB NOT NULL DEFAULT '[]'::JSONB,
    hard_failures JSONB NOT NULL DEFAULT '[]'::JSONB,
    response_hash TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_key, case_id)
);

CREATE TABLE IF NOT EXISTS agent.response_evidence_ledger (
    id BIGSERIAL PRIMARY KEY,
    chat_turn_id BIGINT NOT NULL UNIQUE REFERENCES agent.chat_turns(id) ON DELETE CASCADE,
    evidence_status TEXT NOT NULL
        CHECK (evidence_status IN ('deterministic_source_snapshot','source_backed_unverified','unverified','conflicted')),
    response_hash TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    route_name TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    source_refs JSONB NOT NULL DEFAULT '[]'::JSONB,
    missing_evidence JSONB NOT NULL DEFAULT '[]'::JSONB,
    verification_checks JSONB NOT NULL DEFAULT '{}'::JSONB,
    verifier_agent TEXT NOT NULL DEFAULT 'Evidence Verification Agent',
    raw_prompt_stored BOOLEAN NOT NULL DEFAULT false,
    capital_action_allowed BOOLEAN NOT NULL DEFAULT false,
    live_execution_allowed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_response_ledger_no_prompt CHECK (raw_prompt_stored=false),
    CONSTRAINT chk_response_ledger_no_capital CHECK (capital_action_allowed=false),
    CONSTRAINT chk_response_ledger_no_execution CHECK (live_execution_allowed=false)
);

INSERT INTO agent.local_model_registry (
    model_name, deployment_tier, machine_profiles, context_tokens,
    vector_dimensions, eval_suite, promotion_status, allowed_task_classes,
    storage_root, notes, evidence
) VALUES
    ('qwen3.5:2b', 'light', ARRAY['macbook','imac'], 8192, NULL, 'light_v1', 'candidate',
     ARRAY['routing','classification','short_summary','news_triage','tool_selection'],
     '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'Always-on daily driver. Concurrency one; no autonomous capital or execution authority.',
     '[{"source":"_ai_os_runtime/config/local_models.json","license_review_required":false}]'::jsonb),
    ('qwen3.5:9b', 'mid', ARRAY['macbook'], 16384, NULL, 'mid_v1', 'candidate',
     ARRAY['filing_analysis','fundamental_research','strategy_research','paper_analysis','investment_memo'],
     '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'On-demand local research workhorse. Not an arithmetic, risk, backtest, or execution authority.',
     '[{"source":"_ai_os_runtime/config/local_models.json"}]'::jsonb),
    ('qwen3-embedding:0.6b', 'retrieval', ARRAY['macbook','imac'], 8192, 1024, 'retrieval_v1', 'candidate',
     ARRAY['embedding','semantic_search','deterministic_similarity_rerank'],
     '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'Versioned Qdrant collections must pass retrieval comparison before alias promotion.',
     '[{"source":"_ai_os_runtime/config/local_models.json"}]'::jsonb),
    ('gemma4:e2b', 'specialist', ARRAY['macbook-specialist'], 8192, NULL, 'multimodal_v1', 'candidate',
     ARRAY['document_vision','chart_reading','scanned_pdf','audio_document'],
     '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'Installed specialist candidate; not assignable until a multimodal evidence suite is implemented and passed.',
     '[{"source":"_ai_os_runtime/config/local_models.json"}]'::jsonb),
    ('llama3.2:3b', 'rollback', ARRAY['macbook'], 4096, NULL, 'legacy_baseline_v1', 'rollback_only',
     ARRAY['legacy_comparison'], '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'Retained only for measured rollback and comparison.', '[]'::jsonb),
    ('mxbai-embed-large', 'rollback', ARRAY['macbook'], 512, 1024, 'legacy_retrieval_v1', 'rollback_only',
     ARRAY['legacy_embedding_comparison'], '/Volumes/Devarsh SSD/AI OS Data/ollama/models',
     'Retained until the Qwen3 embedding reindex and retrieval evaluation pass.', '[]'::jsonb)
ON CONFLICT (model_name) DO UPDATE SET
    deployment_tier=EXCLUDED.deployment_tier,
    machine_profiles=EXCLUDED.machine_profiles,
    context_tokens=EXCLUDED.context_tokens,
    vector_dimensions=EXCLUDED.vector_dimensions,
    eval_suite=EXCLUDED.eval_suite,
    allowed_task_classes=EXCLUDED.allowed_task_classes,
    storage_root=EXCLUDED.storage_root,
    notes=EXCLUDED.notes,
    evidence=EXCLUDED.evidence,
    updated_at=now();

INSERT INTO agent.model_routes (
    route_name, task_class, default_provider, default_model,
    escalation_provider, escalation_model, max_cost_tier, notes, enabled
) VALUES
    ('always_on_daily_driver', 'routing_and_routine_work', 'ollama', 'qwen3.5:2b',
     'local_workhorse', 'qwen3.5:9b', 'local',
     'Approved light route only. Truth contract, privacy gate, and exact model evaluation are mandatory.', true),
    ('local_workhorse_synthesis', 'investment_research_synthesis', 'ollama', 'qwen3.5:9b',
     'codex_or_cloud', 'frontier_on_approval', 'local_plus',
     'On-demand local research workhorse for filings, papers, strategies, and investment memos.', true),
    ('local_heavy_reasoning', 'bounded_local_reasoning', 'ollama', 'qwen3.5:9b',
     'codex_or_cloud', 'frontier_on_approval', 'local_plus',
     'The 9B workhorse is the maximum approved normal local route on the 16GB Mac; heavier work must escalate.', true),
    ('multimodal_document_analysis', 'multimodal_document_analysis', 'ollama', 'gemma4:e2b',
     'codex_or_cloud', 'multimodal_frontier_on_approval', 'local_plus',
     'Candidate-only specialist route until multimodal evaluation passes.', true),
    ('local_embedding_retrieval', 'embedding', 'ollama', 'qwen3-embedding:0.6b',
     NULL, NULL, 'local',
     'Embedding route for versioned Qdrant collections and deterministic similarity reranking.', true)
ON CONFLICT (route_name) DO UPDATE SET
    task_class=EXCLUDED.task_class,
    default_provider=EXCLUDED.default_provider,
    default_model=EXCLUDED.default_model,
    escalation_provider=EXCLUDED.escalation_provider,
    escalation_model=EXCLUDED.escalation_model,
    max_cost_tier=EXCLUDED.max_cost_tier,
    notes=EXCLUDED.notes,
    enabled=EXCLUDED.enabled;

UPDATE agent.model_routes
SET default_provider='ollama', default_model='qwen3.5:2b', max_cost_tier='local',
    notes=coalesce(notes,'') || ' Routed to evaluated Qwen3.5 2B light fleet.'
WHERE route_name IN (
    'daily_brief','jarvis_intake','jarvis_runtime','news_curation',
    'news_event_triage','obsidian_retrieval_summary','strategy_intake','trade_journal_learning'
);

UPDATE agent.model_routes
SET default_provider='ollama', default_model='qwen3.5:9b', max_cost_tier='local_plus',
    notes=coalesce(notes,'') || ' Routed to evaluated Qwen3.5 9B local research workhorse.'
WHERE route_name IN (
    'filings_analysis','filing_analysis','research_company_analysis','strategy_generation',
    'fundamental_research','research_paper_analysis','investment_memo','portfolio_analysis'
);

INSERT INTO agent.model_endpoints (
    endpoint_key, endpoint_name, provider, model_name, route_name, endpoint_type,
    base_url, deployment_target, status, context_window, estimated_disk_gb,
    cost_tier, capabilities, requires_api_key, health_status, owner_agent, notes, config
) VALUES
    ('ollama_qwen3_5_2b', 'Qwen3.5 2B local daily driver', 'ollama', 'qwen3.5:2b', 'always_on_daily_driver', 'local',
     'http://127.0.0.1:11434', 'macbook_and_imac', 'configured', 8192, 2.7, 'local',
     ARRAY['text','tools','thinking','vision'], false, 'unchecked', 'AI Runtime Engineer',
     'Assignable only after light_v1 passes.', '{"num_parallel":1,"keep_alive":"5m"}'::jsonb),
    ('ollama_qwen3_5_9b', 'Qwen3.5 9B local research workhorse', 'ollama', 'qwen3.5:9b', 'local_workhorse_synthesis', 'local',
     'http://127.0.0.1:11434', 'macbook_m4_16gb', 'configured', 16384, 6.6, 'local_plus',
     ARRAY['text','tools','thinking','vision'], false, 'unchecked', 'AI Runtime Engineer',
     'On-demand; assignable only after mid_v1 passes.', '{"num_parallel":1,"keep_alive":"0"}'::jsonb),
    ('ollama_qwen3_embedding_0_6b', 'Qwen3 Embedding 0.6B', 'ollama', 'qwen3-embedding:0.6b', 'local_embedding_retrieval', 'local',
     'http://127.0.0.1:11434', 'macbook_and_imac', 'configured', 8192, 0.7, 'local',
     ARRAY['embedding','retrieval'], false, 'unchecked', 'Knowledge Systems Engineer',
     'Versioned 1024-dimensional collections; alias promotion requires retrieval_v1.', '{"vector_dimensions":1024}'::jsonb),
    ('ollama_gemma4_e2b', 'Gemma 4 E2B document specialist', 'ollama', 'gemma4:e2b', 'multimodal_document_analysis', 'local',
     'http://127.0.0.1:11434', 'macbook_m4_16gb_on_demand', 'configured', 8192, 7.2, 'local_plus',
     ARRAY['text','image','audio','thinking'], false, 'unchecked', 'Document Intelligence Agent',
     'Candidate-only until multimodal_v1 is implemented and passes.', '{"num_parallel":1,"keep_alive":"0"}'::jsonb)
ON CONFLICT (endpoint_key) DO UPDATE SET
    endpoint_name=EXCLUDED.endpoint_name, provider=EXCLUDED.provider,
    model_name=EXCLUDED.model_name, route_name=EXCLUDED.route_name,
    endpoint_type=EXCLUDED.endpoint_type, base_url=EXCLUDED.base_url,
    deployment_target=EXCLUDED.deployment_target, status=EXCLUDED.status,
    context_window=EXCLUDED.context_window, estimated_disk_gb=EXCLUDED.estimated_disk_gb,
    cost_tier=EXCLUDED.cost_tier, capabilities=EXCLUDED.capabilities,
    notes=EXCLUDED.notes, config=EXCLUDED.config, updated_at=now();

CREATE OR REPLACE VIEW agent.v_local_model_fleet AS
SELECT registry.model_name, registry.deployment_tier, registry.machine_profiles,
       registry.context_tokens, registry.vector_dimensions, registry.eval_suite,
       registry.promotion_status, registry.allowed_task_classes,
       registry.last_eval_run_key, registry.last_eval_score, registry.last_eval_at,
       endpoint.endpoint_key, endpoint.health_status, endpoint.last_checked_at,
       endpoint.last_latency_ms, endpoint.last_error,
       CASE
           WHEN registry.promotion_status='approved' AND endpoint.health_status IN ('configured','healthy','ready','active') THEN 'assignable'
           WHEN registry.promotion_status='approved' THEN 'approved_endpoint_unready'
           WHEN registry.promotion_status='rollback_only' THEN 'rollback_only'
           ELSE 'evaluation_required'
       END AS runtime_status,
       false AS capital_action_allowed,
       false AS live_execution_allowed
FROM agent.local_model_registry registry
LEFT JOIN agent.model_endpoints endpoint ON endpoint.model_name=registry.model_name;

INSERT INTO agent.tool_registry (
    tool_name, tool_type, owning_agent, permission_level, enabled, description, config
) VALUES
    ('ai_os_local_model_fleet', 'mcp_tool', 'AI Runtime Engineer', 'read_only', true,
     'Read exact local model versions, promotion state, latest eval, endpoint health, machine placement, and task scope.',
     '{"reads":["agent.v_local_model_fleet","agent.local_model_eval_runs","agent.local_model_eval_results"],"raw_prompts_exposed":false}'::jsonb),
    ('ai_os_response_evidence_ledger', 'mcp_tool', 'Evidence Verification Agent', 'read_only', true,
     'Read source envelope, evidence status, missing evidence, response hash, and verification checks for persisted model responses.',
     '{"reads":["agent.response_evidence_ledger"],"raw_prompts_exposed":false,"live_execution_allowed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET
    tool_type=EXCLUDED.tool_type, owning_agent=EXCLUDED.owning_agent,
    permission_level=EXCLUDED.permission_level, enabled=EXCLUDED.enabled,
    description=EXCLUDED.description, config=EXCLUDED.config;
