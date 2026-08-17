BEGIN;

CREATE TABLE IF NOT EXISTS research.research_case_public_packets (
    id BIGSERIAL PRIMARY KEY,
    research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
    preflight_id BIGINT NOT NULL REFERENCES research.model_run_preflights(id) ON DELETE RESTRICT,
    packet_key TEXT NOT NULL UNIQUE,
    packet_version INTEGER NOT NULL CHECK (packet_version > 0),
    source_count INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
    source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    public_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    packet_hash TEXT NOT NULL CHECK (length(packet_hash)=64),
    contains_private_data BOOLEAN NOT NULL DEFAULT false CHECK (contains_private_data=false),
    contains_client_data BOOLEAN NOT NULL DEFAULT false CHECK (contains_client_data=false),
    approved_for_cloud_at TIMESTAMPTZ NOT NULL,
    approved_for_cloud_by TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (research_case_id,packet_version)
);

CREATE TABLE IF NOT EXISTS research.research_case_model_runs (
    id BIGSERIAL PRIMARY KEY,
    research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
    public_packet_id BIGINT NOT NULL REFERENCES research.research_case_public_packets(id) ON DELETE RESTRICT,
    preflight_id BIGINT NOT NULL REFERENCES research.model_run_preflights(id) ON DELETE RESTRICT,
    role_key TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    run_key TEXT NOT NULL UNIQUE,
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 3),
    status TEXT NOT NULL DEFAULT 'awaiting_dependencies'
      CHECK (status IN ('awaiting_dependencies','queued','running','completed','needs_revision','blocked','failed')),
    route_name TEXT NOT NULL REFERENCES agent.model_routes(route_name) ON DELETE RESTRICT,
    provider TEXT NOT NULL DEFAULT 'openrouter',
    model_name TEXT NOT NULL,
    prompt_hash TEXT,
    response_hash TEXT,
    artifact_path TEXT,
    artifact_hash TEXT,
    output_contract JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    cited_source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    actual_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (actual_cost_usd >= 0),
    latency_ms INTEGER,
    exception_detail TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (research_case_id,role_key,attempt)
);
CREATE INDEX IF NOT EXISTS idx_research_case_model_runs_queue
  ON research.research_case_model_runs(status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_research_case_model_runs_case
  ON research.research_case_model_runs(research_case_id,role_key,attempt DESC);

INSERT INTO agent.skills (
  skill_key,skill_name,skill_family,skill_type,owner_department,status,execution_mode,
  permission_level,input_sources,output_targets,required_tools,risk_notes,prompt_template,config
) VALUES
 ('company_research_lead_synthesis','Company research lead synthesis','investment_research','analysis','portfolio','active','governed_model_worker','read_only',ARRAY['research.research_case_public_packets','research.research_case_model_runs'],ARRAY['research.research_case_model_runs'],ARRAY['public_research','structured_output'],'Approved public packets only; facts require allowed citation IDs; no capital authority.','Synthesize specialist work into a cited company pack; separate facts, inference, scenarios and missing evidence.','{"route":"openrouter_public_lead_glm52_canary","public_packet_approval_required":true,"citation_required":true}'::jsonb),
 ('company_research_executive_summary','Company research executive summary','investment_research','analysis','research','active','governed_model_worker','read_only',ARRAY['research.research_case_public_packets','research.research_case_model_runs'],ARRAY['research.research_case_model_runs'],ARRAY['structured_output'],'Approved public packets only; concise and citation-bound.','Create a numeric investor-facing summary from accepted evidence and lead synthesis.','{"route":"openrouter_public_lead_glm52_canary","public_packet_approval_required":true,"citation_required":true}'::jsonb),
 ('company_research_independent_review','Independent company research review','investment_research','review','quant','active','governed_model_worker','read_only',ARRAY['research.research_case_public_packets','research.research_case_model_runs'],ARRAY['research.research_case_model_runs'],ARRAY['structured_output','validation'],'Approved public packets only; reviewer cannot approve capital.','Challenge citations, calculations, forecasts, contradictions and missing disconfirming evidence.','{"route":"openrouter_public_lead_deepseek_v4_pro_canary","public_packet_approval_required":true,"citation_required":true,"independent":true}'::jsonb),
 ('company_research_committee_brief','Investment committee research brief','investment_research','review','executive','active','governed_model_worker','read_only',ARRAY['research.research_case_public_packets','research.research_case_model_runs'],ARRAY['research.research_case_model_runs'],ARRAY['structured_output'],'Approved public packets only; final authority remains human.','Prepare a decision brief with disagreement, valuation limits, risks, kill conditions and a human decision ask.','{"route":"openrouter_public_lead_deepseek_v4_pro_canary","public_packet_approval_required":true,"citation_required":true,"human_decision_required":true}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
  skill_name=EXCLUDED.skill_name,status='active',execution_mode='governed_model_worker',
  permission_level='read_only',input_sources=EXCLUDED.input_sources,output_targets=EXCLUDED.output_targets,
  required_tools=EXCLUDED.required_tools,risk_notes=EXCLUDED.risk_notes,
  prompt_template=EXCLUDED.prompt_template,config=EXCLUDED.config,updated_at=now();

UPDATE agent.model_alias_registry SET status='approved_public_research',
  notes='Selected for explicitly approved public Research Case packets. Generic chat remains disabled.',
  config=config||'{"selected_role":"lead_public_company_analyst","generic_chat_enabled":false,"raw_prompt_storage":false}'::jsonb,
  updated_at=now()
WHERE alias_key='research.public.lead.glm52';
UPDATE agent.model_alias_registry SET status='approved_public_review',
  notes='Selected for explicitly approved independent review and committee packets. Generic chat remains disabled.',
  config=config||'{"selected_role":"independent_reviewer","generic_chat_enabled":false,"raw_prompt_storage":false}'::jsonb,
  updated_at=now()
WHERE alias_key='research.public.lead.deepseek_v4_pro';
UPDATE agent.model_alias_registry SET status='canary_only',updated_at=now()
WHERE alias_key='research.public.lead.qwen38_max';

INSERT INTO agent.graph_versions (
  graph_key,version,status,change_summary,source_kind,source_ref,definition_hash,
  validation_result,created_by,approved_by,approved_at
) VALUES (
  'company_research_case',3,'active',
  'Seven specialists feed lead synthesis, executive summary, independent review, committee brief and final human review.',
  'operator_authored','migration:238_governed_autonomous_research_case_v1',
  md5('company_research_case:v3:approved-public-packet:model-runs:human-decision'),
  '{"valid":true,"public_packet_approval_required":true,"private_data_egress_allowed":false,"raw_prompt_stored":false,"capital_action_allowed":false,"external_write_allowed":false,"human_review_required":true}'::jsonb,
  'Devarsh','Devarsh',now()
) ON CONFLICT (graph_key,version) DO UPDATE SET
  status='active',change_summary=EXCLUDED.change_summary,definition_hash=EXCLUDED.definition_hash,
  validation_result=EXCLUDED.validation_result,approved_by='Devarsh',approved_at=now();

INSERT INTO agent.graph_nodes (
  graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,
  approval_required,retry_limit,timeout_seconds,input_mapping,configuration,output_contract,on_error,ui_position
)
SELECT version_row.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,'draft_only',
       node.approval_required,node.retry_limit,node.timeout_seconds,'{}'::jsonb,node.configuration,node.output_contract,'request_human',node.ui_position
FROM agent.graph_versions version_row
CROSS JOIN (VALUES
 ('start','Confirm research case','start',NULL::text,NULL::text,false,0,60,'{}'::jsonb,'{"status":"confirmed"}'::jsonb,'{"x":0,"y":0}'::jsonb),
 ('company_business','Business and company economics','agent_task','Company Analyst','long_term_business_model_review',false,2,1800,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary"}'::jsonb,'{"required":["facts","analysis","citations","missing"]}'::jsonb,'{"x":-420,"y":140}'::jsonb),
 ('filings','Official filings and disclosures','agent_task','Filings and Transcript Analyst','analyze_corporate_filing',false,2,2400,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary"}'::jsonb,'{"required":["facts","analysis","citations","missing"]}'::jsonb,'{"x":-280,"y":140}'::jsonb),
 ('financials','Financial statements and quality','agent_task','Financial Statement Analyst','long_term_financial_quality_review',false,2,2400,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary","deterministic_validation_required":true}'::jsonb,'{"required":["facts","calculations","citations","missing"]}'::jsonb,'{"x":-140,"y":140}'::jsonb),
 ('management','Management and capital allocation','agent_task','Management Analyst','long_term_management_governance_review',false,2,1800,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary"}'::jsonb,'{"required":["facts","analysis","citations","risks"]}'::jsonb,'{"x":0,"y":140}'::jsonb),
 ('industry_moat','Industry, peers, TAM and moat','agent_task','Industry Analyst','long_term_industry_review',false,2,1800,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary"}'::jsonb,'{"required":["facts","analysis","citations","disconfirmers"]}'::jsonb,'{"x":140,"y":140}'::jsonb),
 ('valuation','Valuation and scenarios','agent_task','Valuation Agent','long_term_valuation_review',false,2,2400,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary","deterministic_validation_required":true}'::jsonb,'{"required":["assumptions","scenarios","citations","missing"]}'::jsonb,'{"x":280,"y":140}'::jsonb),
 ('bear_risk','Bear case and permanent-loss risk','agent_task','Bear Case Agent','long_term_bear_case_review',false,2,1800,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary"}'::jsonb,'{"required":["risks","disconfirmers","citations","missing"]}'::jsonb,'{"x":420,"y":140}'::jsonb),
 ('lead_synthesis','Lead analyst synthesis','agent_task','Long-Term Portfolio Manager','company_research_lead_synthesis',false,2,3000,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary","all_specialists_terminal":true}'::jsonb,'{"required":["summary","facts","analysis","citations","missing"]}'::jsonb,'{"x":0,"y":300}'::jsonb),
 ('executive_summary','Investor-facing executive summary','agent_task','Research Analyst','company_research_executive_summary',false,2,1200,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_glm52_canary","lead_synthesis_required":true}'::jsonb,'{"required":["summary","facts","analysis","risks","missing"]}'::jsonb,'{"x":0,"y":400}'::jsonb),
 ('independent_review','Independent research challenge','agent_task','Model Validation Agent','company_research_independent_review',false,2,2400,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_deepseek_v4_pro_canary","independent_context":true}'::jsonb,'{"required":["review_decision","blocking_findings","citation_checks","revision_requests"]}'::jsonb,'{"x":0,"y":500}'::jsonb),
 ('committee_review','Investment committee brief','agent_task','CIO Agent','company_research_committee_brief',false,1,1800,'{"source_qualified_worker_required":true,"route":"openrouter_public_lead_deepseek_v4_pro_canary","human_final_authority":true}'::jsonb,'{"required":["summary","analysis","risks","human_decision_ask"]}'::jsonb,'{"x":0,"y":600}'::jsonb),
 ('human_review','Human review of complete company pack','approval_gate','Long-Term Portfolio Manager',NULL::text,true,0,86400,'{"approval_type":"research_case_review"}'::jsonb,'{"required":["decision","rationale"]}'::jsonb,'{"x":0,"y":700}'::jsonb),
 ('end','Research case complete','end','Long-Term Portfolio Manager',NULL::text,false,0,60,'{}'::jsonb,'{"status":"complete"}'::jsonb,'{"x":0,"y":800}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,approval_required,retry_limit,timeout_seconds,configuration,output_contract,ui_position)
WHERE version_row.graph_key='company_research_case' AND version_row.version=3
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
  node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
  skill_key=EXCLUDED.skill_key,approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
  timeout_seconds=EXCLUDED.timeout_seconds,configuration=EXCLUDED.configuration,
  output_contract=EXCLUDED.output_contract,on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,enabled,label)
SELECT version_row.id,edge.from_key,edge.to_key,edge.edge_kind,edge.condition_type,edge.condition,edge.priority,true,edge.label
FROM agent.graph_versions version_row
CROSS JOIN (VALUES
 ('start','company_business','success','always','{}'::jsonb,10,'Dispatch business'),('start','filings','success','always','{}'::jsonb,20,'Dispatch filings'),
 ('start','financials','success','always','{}'::jsonb,30,'Dispatch financials'),('start','management','success','always','{}'::jsonb,40,'Dispatch management'),
 ('start','industry_moat','success','always','{}'::jsonb,50,'Dispatch industry'),('start','valuation','success','always','{}'::jsonb,60,'Dispatch valuation'),
 ('start','bear_risk','success','always','{}'::jsonb,70,'Dispatch risk'),('company_business','lead_synthesis','success','always','{}'::jsonb,100,'Business complete'),
 ('filings','lead_synthesis','success','always','{}'::jsonb,110,'Filings complete'),('financials','lead_synthesis','success','always','{}'::jsonb,120,'Financials complete'),
 ('management','lead_synthesis','success','always','{}'::jsonb,130,'Management complete'),('industry_moat','lead_synthesis','success','always','{}'::jsonb,140,'Industry complete'),
 ('valuation','lead_synthesis','success','always','{}'::jsonb,150,'Valuation complete'),('bear_risk','lead_synthesis','success','always','{}'::jsonb,160,'Risk complete'),
 ('lead_synthesis','executive_summary','success','always','{}'::jsonb,200,'Synthesis complete'),
 ('executive_summary','independent_review','success','always','{}'::jsonb,210,'Summary complete'),
 ('independent_review','committee_review','success','always','{}'::jsonb,220,'Review complete'),
 ('committee_review','human_review','success','always','{}'::jsonb,230,'Committee brief complete'),
 ('human_review','end','conditional','approved','{}'::jsonb,240,'Human approved research pack')
) AS edge(from_key,to_key,edge_kind,condition_type,condition,priority,label)
WHERE version_row.graph_key='company_research_case' AND version_row.version=3
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
  condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,priority=EXCLUDED.priority,enabled=true,label=EXCLUDED.label;

UPDATE agent.graph_versions SET status='retired'
WHERE graph_key='company_research_case' AND version<>3 AND status='active';
UPDATE agent.graph_definitions SET active_version=3,
  description='Approved public packet specialists feed lead synthesis, independent review, committee brief and final human review.',
  safety_policy=coalesce(safety_policy,'{}'::jsonb)||'{"public_packet_approval_required":true,"private_data_egress_allowed":false,"raw_prompt_stored":false,"human_review_required":true}'::jsonb,
  updated_at=now() WHERE graph_key='company_research_case';

CREATE OR REPLACE VIEW research.v_research_case_model_progress AS
SELECT run.research_case_id,run.role_key,run.agent_name,run.status,run.attempt,run.route_name,
       run.model_name,run.artifact_path,run.validation_result,run.cited_source_ids,
       run.actual_cost_usd,run.latency_ms,run.exception_detail,run.started_at,run.finished_at,run.updated_at,
       run.artifact_hash,run.output_summary
FROM research.research_case_model_runs run
WHERE run.attempt=(SELECT max(latest.attempt) FROM research.research_case_model_runs latest
                   WHERE latest.research_case_id=run.research_case_id AND latest.role_key=run.role_key);

COMMIT;
