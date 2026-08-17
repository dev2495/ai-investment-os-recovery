BEGIN;

CREATE TABLE IF NOT EXISTS research.model_run_preflights (
    id BIGSERIAL PRIMARY KEY,
    preflight_key TEXT NOT NULL UNIQUE,
    research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    request_kind TEXT NOT NULL CHECK (request_kind IN ('research_case','report','canary')),
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'awaiting_approval' CHECK (status IN ('awaiting_approval','approved','rejected','expired','completed','blocked')),
    public_only BOOLEAN NOT NULL DEFAULT true,
    private_data_egress_allowed BOOLEAN NOT NULL DEFAULT false,
    external_write_allowed BOOLEAN NOT NULL DEFAULT false,
    broker_write_allowed BOOLEAN NOT NULL DEFAULT false,
    source_count INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
    document_count INTEGER NOT NULL DEFAULT 0 CHECK (document_count >= 0),
    cached_document_count INTEGER NOT NULL DEFAULT 0 CHECK (cached_document_count >= 0),
    estimated_storage_bytes BIGINT NOT NULL DEFAULT 0 CHECK (estimated_storage_bytes >= 0),
    estimated_duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (estimated_duration_seconds >= 0),
    estimated_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    hard_max_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (hard_max_cost_usd >= 0),
    exchange_rate_inr_per_usd NUMERIC NOT NULL DEFAULT 0 CHECK (exchange_rate_inr_per_usd >= 0),
    rate_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    run_plan JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    block_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    approval_id BIGINT UNIQUE REFERENCES agent.approvals(id) ON DELETE SET NULL,
    approval_expires_at TIMESTAMPTZ,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_preflight_no_private_egress CHECK (private_data_egress_allowed=false),
    CONSTRAINT chk_preflight_no_external_writes CHECK (external_write_allowed=false),
    CONSTRAINT chk_preflight_no_broker_writes CHECK (broker_write_allowed=false)
);
CREATE INDEX IF NOT EXISTS idx_model_run_preflights_case ON research.model_run_preflights (research_case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_run_preflights_status ON research.model_run_preflights (status, created_at DESC);

CREATE TABLE IF NOT EXISTS research.model_run_receipts (
    id BIGSERIAL PRIMARY KEY,
    receipt_key TEXT NOT NULL UNIQUE,
    preflight_id BIGINT NOT NULL REFERENCES research.model_run_preflights(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    route_name TEXT NOT NULL REFERENCES agent.model_routes(route_name) ON DELETE RESTRICT,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    data_boundary TEXT NOT NULL CHECK (data_boundary IN ('public_only','public_redacted')),
    prompt_hash TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
    actual_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    latency_ms INTEGER,
    outcome_status TEXT NOT NULL CHECK (outcome_status IN ('completed','failed','blocked','cached')),
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_receipt_no_prompt CHECK (length(prompt_hash)=64)
);
CREATE INDEX IF NOT EXISTS idx_model_run_receipts_preflight ON research.model_run_receipts (preflight_id, created_at DESC);

CREATE TABLE IF NOT EXISTS research.public_model_canary_runs (
    id BIGSERIAL PRIMARY KEY,
    canary_key TEXT NOT NULL UNIQUE,
    preflight_id BIGINT REFERENCES research.model_run_preflights(id) ON DELETE SET NULL,
    candidate_route TEXT NOT NULL REFERENCES agent.model_routes(route_name) ON DELETE RESTRICT,
    candidate_model TEXT NOT NULL,
    packet_key TEXT NOT NULL,
    packet_source_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    packet_public_only BOOLEAN NOT NULL DEFAULT true,
    status TEXT NOT NULL DEFAULT 'configured' CHECK (status IN ('configured','awaiting_approval','running','completed','failed','blocked')),
    scoring_rubric JSONB NOT NULL,
    score JSONB NOT NULL DEFAULT '{}'::jsonb,
    selected_for_role BOOLEAN NOT NULL DEFAULT false,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_canary_public_only CHECK (packet_public_only=true)
);
CREATE INDEX IF NOT EXISTS idx_public_model_canary_runs_candidate ON research.public_model_canary_runs (candidate_route, created_at DESC);

INSERT INTO agent.model_cost_caps (agent_name,daily_cap_usd,monthly_cap_usd,max_cost_tier,cloud_requires_approval,autonomous_cloud_allowed,hard_stop_on_breach,alert_threshold_pct,notes,evidence,updated_by)
SELECT profile.agent_name,0.50,15.00,'cloud_medium',true,false,true,80,
       'Approval-gated public-model ceiling. Private, broker, client and external-write work remains blocked from cloud.',
       jsonb_build_array(jsonb_build_object('migration','235_governed_research_model_runtime_v1','coverage','all_active_agents')),
       'AI Runtime Engineer'
FROM agent.profiles profile WHERE profile.status='active'
ON CONFLICT (agent_name) DO UPDATE SET
  daily_cap_usd=CASE WHEN agent.model_cost_caps.daily_cap_usd>0 THEN agent.model_cost_caps.daily_cap_usd ELSE EXCLUDED.daily_cap_usd END,
  monthly_cap_usd=CASE WHEN agent.model_cost_caps.monthly_cap_usd>0 THEN agent.model_cost_caps.monthly_cap_usd ELSE EXCLUDED.monthly_cap_usd END,
  max_cost_tier=CASE WHEN agent.model_cost_caps.max_cost_tier IN ('cloud_medium','frontier') THEN agent.model_cost_caps.max_cost_tier ELSE 'cloud_medium' END,
  cloud_requires_approval=true,autonomous_cloud_allowed=false,hard_stop_on_breach=true,
  notes=concat_ws(' ',nullif(agent.model_cost_caps.notes,''),'Migration 235 requires an explicit preflight approval for every cloud research or report run.'),
  evidence=coalesce(agent.model_cost_caps.evidence,'[]'::jsonb)||EXCLUDED.evidence,updated_by='AI Runtime Engineer',updated_at=now();

INSERT INTO agent.model_cost_rates (provider,model_name,cost_tier,input_usd_per_1m_tokens,output_usd_per_1m_tokens,rate_source,status,effective_at,notes,metadata) VALUES
 ('openrouter','deepseek/deepseek-v4-flash-0731','cloud_low',0.140000,0.280000,'openrouter_models_api_2026_08_14','active','2026-08-14 00:00:00+00','Pinned public extraction candidate.','{"catalog_checked_at":"2026-08-14","public_only":true}'::jsonb),
 ('openrouter','google/gemini-3.7-flash','cloud_medium',0.375000,1.875000,'openrouter_models_api_2026_08_14','active','2026-08-14 00:00:00+00','Pinned multimodal public-document candidate.','{"catalog_checked_at":"2026-08-14","public_only":true}'::jsonb),
 ('openrouter','z-ai/glm-5.2','cloud_medium',0.630000,1.980000,'openrouter_models_api_2026_08_14','active','2026-08-14 00:00:00+00','Lead analyst canary candidate.','{"catalog_checked_at":"2026-08-14","public_only":true}'::jsonb),
 ('openrouter','deepseek/deepseek-v4-pro-0813','cloud_medium',0.435000,0.870000,'openrouter_models_api_2026_08_14','active','2026-08-14 00:00:00+00','Lead analyst canary candidate.','{"catalog_checked_at":"2026-08-14","public_only":true}'::jsonb),
 ('openrouter','qwen/qwen3.8-max','frontier',2.000000,6.000000,'openrouter_models_api_2026_08_14','active','2026-08-14 00:00:00+00','Lead analyst canary candidate; xhigh reasoning reserve.','{"catalog_checked_at":"2026-08-14","public_only":true}'::jsonb)
ON CONFLICT (provider,model_name,effective_at) DO UPDATE SET cost_tier=EXCLUDED.cost_tier,input_usd_per_1m_tokens=EXCLUDED.input_usd_per_1m_tokens,output_usd_per_1m_tokens=EXCLUDED.output_usd_per_1m_tokens,rate_source=EXCLUDED.rate_source,status=EXCLUDED.status,notes=EXCLUDED.notes,metadata=EXCLUDED.metadata,updated_at=now();

INSERT INTO agent.model_routes (route_name,task_class,default_provider,default_model,escalation_provider,escalation_model,max_cost_tier,notes,enabled) VALUES
 ('openrouter_public_extract_flash','public_document_extraction_canary','openrouter','deepseek/deepseek-v4-flash-0731','openrouter','google/gemini-3.7-flash','cloud_low','Canary-only public extraction route. Disabled until a preflight, explicit approval and candidate promotion pass.',false),
 ('openrouter_public_multimodal_gemini','public_document_multimodal_canary','openrouter','google/gemini-3.7-flash','openrouter','deepseek/deepseek-v4-pro-0813','cloud_medium','Canary-only public multimodal route. Disabled until a preflight, explicit approval and candidate promotion pass.',false),
 ('openrouter_public_lead_glm52_canary','public_company_lead_canary','openrouter','z-ai/glm-5.2','openrouter','deepseek/deepseek-v4-pro-0813','cloud_medium','Lead analyst candidate: GLM 5.2. Public bounded packet only; disabled pending canary scoring.',false),
 ('openrouter_public_lead_deepseek_v4_pro_canary','public_company_lead_canary','openrouter','deepseek/deepseek-v4-pro-0813','openrouter','z-ai/glm-5.2','cloud_medium','Lead analyst candidate: DeepSeek V4 Pro 0813. Public bounded packet only; disabled pending canary scoring.',false),
 ('openrouter_public_lead_qwen38_max_canary','public_company_lead_canary','openrouter','qwen/qwen3.8-max','openrouter','deepseek/deepseek-v4-pro-0813','frontier','Lead analyst candidate: Qwen 3.8 Max. Public bounded packet only; disabled pending canary scoring.',false)
ON CONFLICT (route_name) DO UPDATE SET task_class=EXCLUDED.task_class,default_provider=EXCLUDED.default_provider,default_model=EXCLUDED.default_model,escalation_provider=EXCLUDED.escalation_provider,escalation_model=EXCLUDED.escalation_model,max_cost_tier=EXCLUDED.max_cost_tier,notes=EXCLUDED.notes,enabled=false;

INSERT INTO agent.model_alias_registry (alias_key,route_name,provider_binding,model_binding,secret_ref,data_boundary,approval_required,fallback_alias,escalation_alias,status,notes,config) VALUES
 ('research.public.extractor','openrouter_public_extract_flash','openrouter','deepseek/deepseek-v4-flash-0731','AI_OS_OPENROUTER_API_KEY','public_only',true,'local.private.default','research.public.multimodal','canary_only','Public extraction candidate; not executable through generic chat.','{"zdr_required":true,"data_collection":"deny","public_only":true}'::jsonb),
 ('research.public.multimodal','openrouter_public_multimodal_gemini','openrouter','google/gemini-3.7-flash','AI_OS_OPENROUTER_API_KEY','public_only',true,'research.public.extractor','research.public.lead.glm52','canary_only','Public multimodal candidate; not executable through generic chat.','{"zdr_required":true,"data_collection":"deny","public_only":true}'::jsonb),
 ('research.public.lead.glm52','openrouter_public_lead_glm52_canary','openrouter','z-ai/glm-5.2','AI_OS_OPENROUTER_API_KEY','public_only',true,'research.public.lead.deepseek_v4_pro','research.public.lead.qwen38_max','canary_only','GLM 5.2 lead analyst candidate.','{"zdr_required":true,"data_collection":"deny","public_only":true,"role":"lead_public_company_analyst"}'::jsonb),
 ('research.public.lead.deepseek_v4_pro','openrouter_public_lead_deepseek_v4_pro_canary','openrouter','deepseek/deepseek-v4-pro-0813','AI_OS_OPENROUTER_API_KEY','public_only',true,'research.public.lead.glm52','research.public.lead.qwen38_max','canary_only','DeepSeek V4 Pro lead analyst candidate.','{"zdr_required":true,"data_collection":"deny","public_only":true,"role":"lead_public_company_analyst"}'::jsonb),
 ('research.public.lead.qwen38_max','openrouter_public_lead_qwen38_max_canary','openrouter','qwen/qwen3.8-max','AI_OS_OPENROUTER_API_KEY','public_only',true,'research.public.lead.deepseek_v4_pro','local.private.default','canary_only','Qwen 3.8 Max candidate held pending: no verified OpenRouter ZDR endpoint.','{"zdr_required":true,"data_collection":"deny","public_only":true,"zdr_endpoint_verified":false,"role":"lead_public_company_analyst"}'::jsonb)
ON CONFLICT (alias_key) DO UPDATE SET route_name=EXCLUDED.route_name,provider_binding=EXCLUDED.provider_binding,model_binding=EXCLUDED.model_binding,secret_ref=EXCLUDED.secret_ref,data_boundary=EXCLUDED.data_boundary,approval_required=true,fallback_alias=EXCLUDED.fallback_alias,escalation_alias=EXCLUDED.escalation_alias,status='canary_only',notes=EXCLUDED.notes,config=EXCLUDED.config,updated_at=now();

CREATE OR REPLACE VIEW research.v_model_run_cost_receipts AS
SELECT p.id AS preflight_id,p.preflight_key,p.request_kind,p.status,p.requested_by,p.research_case_id,p.holding_thesis_id,p.source_count,p.document_count,p.cached_document_count,p.estimated_storage_bytes,p.estimated_duration_seconds,p.estimated_cost_usd,p.hard_max_cost_usd,p.exchange_rate_inr_per_usd,p.approval_id,p.approved_by,p.approved_at,coalesce(r.receipt_count,0)::integer AS receipt_count,coalesce(r.actual_cost_usd,0)::numeric AS actual_cost_usd,coalesce(r.total_prompt_tokens,0)::bigint AS total_prompt_tokens,coalesce(r.total_completion_tokens,0)::bigint AS total_completion_tokens,p.block_reasons,p.run_plan,p.data_boundary,p.created_at,p.completed_at
FROM research.model_run_preflights p LEFT JOIN LATERAL (SELECT count(*) AS receipt_count,sum(actual_cost_usd) AS actual_cost_usd,sum(prompt_tokens) AS total_prompt_tokens,sum(completion_tokens) AS total_completion_tokens FROM research.model_run_receipts x WHERE x.preflight_id=p.id) r ON true;

INSERT INTO agent.tool_registry (tool_name,tool_type,owning_agent,permission_level,enabled,description,config) VALUES
 ('research_model_run_preflight','mcp_tool','AI Runtime Engineer','read_only',true,'Estimate public research/report model cost, data scope, cache savings and hard stop before creating an explicit approval; no model invocation.','{"reads":["research.model_run_preflights","agent.model_cost_rates","agent.model_cost_caps"],"cloud_execution":false,"raw_prompt_exposed":false,"broker_writes":false}'::jsonb),
 ('research_model_canary_control','mcp_tool','AI Runtime Engineer','read_only',true,'Configure and score public bounded model canaries. Execution remains disabled until explicit approval and promotion.','{"reads":["research.public_model_canary_runs","research.model_run_preflights"],"public_only":true,"cloud_execution":false,"raw_prompt_exposed":false}'::jsonb)
ON CONFLICT (tool_name) DO UPDATE SET owning_agent=EXCLUDED.owning_agent,permission_level=EXCLUDED.permission_level,enabled=EXCLUDED.enabled,description=EXCLUDED.description,config=EXCLUDED.config;

COMMIT;
