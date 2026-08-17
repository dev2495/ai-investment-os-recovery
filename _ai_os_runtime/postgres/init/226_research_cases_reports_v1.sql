BEGIN;

CREATE TABLE IF NOT EXISTS research.research_cases (
    id BIGSERIAL PRIMARY KEY,
    case_key TEXT NOT NULL UNIQUE,
    request_text TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'company'
        CHECK (entity_type IN ('company','ticker','idea')),
    entity_key TEXT NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (resolution_status IN ('needs_input','proposed','confirmed')),
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
    ticker TEXT,
    exchange TEXT,
    company_name TEXT,
    owner_agent TEXT NOT NULL DEFAULT 'Long-Term Portfolio Manager',
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low','normal','medium','high','critical')),
    horizon TEXT NOT NULL DEFAULT '3-5 years',
    mandate TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed','active','collecting','review','blocked','completed','cancelled')),
    work_plan JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_plan JSONB NOT NULL DEFAULT '[]'::jsonb,
    budget JSONB NOT NULL DEFAULT '{}'::jsonb,
    data_boundary JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    exception_count INTEGER NOT NULL DEFAULT 0 CHECK (exception_count >= 0),
    graph_run_id BIGINT REFERENCES agent.graph_runs(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    cooldown_until TIMESTAMPTZ,
    proposed_by TEXT NOT NULL,
    confirmed_by TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_research_cases_idempotency
    ON research.research_cases(idempotency_key)
    WHERE status NOT IN ('cancelled','completed');
CREATE INDEX IF NOT EXISTS idx_research_cases_company
    ON research.research_cases(company_id,status,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_cases_thesis
    ON research.research_cases(holding_thesis_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS research.research_case_agent_runs (
    id BIGSERIAL PRIMARY KEY,
    research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
    role_key TEXT NOT NULL,
    agent_name TEXT NOT NULL REFERENCES agent.profiles(agent_name) ON DELETE RESTRICT,
    skill_key TEXT NOT NULL REFERENCES agent.skills(skill_key) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'queued',
    graph_node_run_id BIGINT REFERENCES agent.graph_node_runs(id) ON DELETE SET NULL,
    task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
    inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifacts JSONB NOT NULL DEFAULT '[]'::jsonb,
    disagreements JSONB NOT NULL DEFAULT '[]'::jsonb,
    exceptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (research_case_id,role_key)
);

CREATE INDEX IF NOT EXISTS idx_research_case_agent_runs_status
    ON research.research_case_agent_runs(research_case_id,status,updated_at DESC);

CREATE TABLE IF NOT EXISTS research.research_case_evidence (
    id BIGSERIAL PRIMARY KEY,
    research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
    evidence_id BIGINT REFERENCES research.fundamental_evidence(id) ON DELETE SET NULL,
    source_item_id BIGINT REFERENCES research.thesis_source_items(id) ON DELETE SET NULL,
    source_kind TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    source_url TEXT,
    local_artifact_path TEXT,
    publication_date DATE,
    effective_date DATE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    parser_status TEXT NOT NULL DEFAULT 'pending',
    validation_status TEXT NOT NULL DEFAULT 'pending',
    citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (research_case_id,dedupe_key)
);

CREATE TABLE IF NOT EXISTS research.research_case_events (
    id BIGSERIAL PRIMARY KEY,
    research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL DEFAULT 'recorded',
    event_summary TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_case_events
    ON research.research_case_events(research_case_id,occurred_at DESC,id DESC);

CREATE TABLE IF NOT EXISTS research.thesis_reports (
    id BIGSERIAL PRIMARY KEY,
    report_key TEXT NOT NULL UNIQUE,
    holding_thesis_id BIGINT NOT NULL REFERENCES portfolio.holding_theses(id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
    report_version INTEGER NOT NULL CHECK (report_version > 0),
    report_format TEXT NOT NULL DEFAULT 'html' CHECK (report_format IN ('html','pdf')),
    report_status TEXT NOT NULL DEFAULT 'generated'
        CHECK (report_status IN ('generated','human_reviewed','superseded','failed')),
    as_of_date DATE NOT NULL,
    source_cutoff_at TIMESTAMPTZ,
    artifact_path TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    coverage_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    caveats JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_by TEXT NOT NULL,
    human_reviewed_by TEXT,
    human_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (holding_thesis_id,report_version)
);

CREATE INDEX IF NOT EXISTS idx_thesis_reports_latest
    ON research.thesis_reports(holding_thesis_id,created_at DESC,id DESC);

INSERT INTO agent.graph_definitions (
    graph_key,graph_name,graph_family,description,owner_agent,status,active_version,
    trigger_type,default_autonomy_level,input_contract,output_contract,safety_policy,tags
) VALUES (
    'company_research_case','Company Research Case','long_term_research',
    'Explicitly started, bounded multi-lane company research with source and human-review gates.',
    'Long-Term Portfolio Manager','active',1,'manual','draft_only',
    '{"required":["research_case_id","entity_key","mandate","horizon"],"optional":["ticker","exchange","company_name","holding_thesis_id","source_plan","budget","data_boundary"]}'::jsonb,
    '{"required":["cited_artifacts","coverage_snapshot","exceptions","human_decision_brief"]}'::jsonb,
    '{"private_data_egress_allowed":false,"broker_write_allowed":false,"client_write_allowed":false,"external_write_allowed":false,"authorized_sources_only":true,"human_review_required":true,"capital_action_allowed":false,"live_execution_allowed":false}'::jsonb,
    ARRAY['research-case','long-term','source-governed','human-review']
) ON CONFLICT (graph_key) DO UPDATE SET
    graph_name=EXCLUDED.graph_name,description=EXCLUDED.description,owner_agent=EXCLUDED.owner_agent,
    status='active',active_version=1,input_contract=EXCLUDED.input_contract,
    output_contract=EXCLUDED.output_contract,safety_policy=EXCLUDED.safety_policy,
    tags=EXCLUDED.tags,updated_at=now();

INSERT INTO agent.graph_versions (
    graph_key,version,status,change_summary,source_kind,source_ref,definition_hash,
    validation_result,created_by,approved_by,approved_at
) VALUES (
    'company_research_case',1,'active',
    'Initial seven-lane source-governed company research case with explicit start and human-review gate.',
    'operator_authored','migration:226_research_cases_reports_v1',
    md5('company_research_case:v1:seven_lanes:human_gate'),
    '{"valid":true,"validated_contracts":true,"capital_action_allowed":false,"external_write_allowed":false}'::jsonb,
    'Devarsh','Devarsh',now()
) ON CONFLICT (graph_key,version) DO UPDATE SET
    status='active',change_summary=EXCLUDED.change_summary,definition_hash=EXCLUDED.definition_hash,
    validation_result=EXCLUDED.validation_result,approved_by='Devarsh',approved_at=now();

INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,
    approval_required,retry_limit,timeout_seconds,configuration,output_contract,on_error,ui_position
)
SELECT version.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,node.approval_required,node.retry_limit,node.timeout_seconds,
       node.configuration,node.output_contract,node.on_error,node.ui_position
FROM agent.graph_versions version
CROSS JOIN (VALUES
    ('start','Confirm research case','start',NULL::text,NULL::text,'draft_only',false,0,60,'{}'::jsonb,'{"status":"confirmed"}'::jsonb,'pause','{"x":0,"y":0}'::jsonb),
    ('company_business','Company and business model','agent_task','Company Analyst','long_term_business_model_review','draft_only',false,2,1800,'{"priority":"medium","objective":"Build a cited company and business-model artifact. Use authorized sources only; preserve dates, locators, freshness and missing evidence."}'::jsonb,'{"required":["artifact","citations","missing_data"]}'::jsonb,'request_human','{"x":-420,"y":140}'::jsonb),
    ('filings','Filings and first-party evidence','agent_task','Filings and Transcript Analyst','analyze_corporate_filing','draft_only',false,2,2400,'{"priority":"high","objective":"Inventory and parse only authorized official filings, annual reports, company or exchange announcements and user-supplied artifacts. Never mark extracted before parse validation."}'::jsonb,'{"required":["source_inventory","parser_status","citations","exceptions"]}'::jsonb,'request_human','{"x":-280,"y":140}'::jsonb),
    ('financials','Financial statements and quality','agent_task','Financial Statement Analyst','long_term_financial_quality_review','draft_only',false,2,2400,'{"priority":"high","objective":"Normalize comparable financial facts with as-reported lineage, formulas, scope and units. Return not-computable states for unsupported metrics."}'::jsonb,'{"required":["artifact","facts","formulas","citations","quality_flags"]}'::jsonb,'request_human','{"x":-140,"y":140}'::jsonb),
    ('management','Management, governance and allocation','agent_task','Management Analyst','long_term_management_governance_review','draft_only',false,2,1800,'{"priority":"high","objective":"Build cited management, governance and capital-allocation evidence, including disconfirming evidence and unresolved red flags."}'::jsonb,'{"required":["artifact","citations","red_flags","missing_data"]}'::jsonb,'request_human','{"x":0,"y":140}'::jsonb),
    ('industry_moat','Industry structure and moat','agent_task','Industry Analyst','long_term_industry_review','draft_only',false,2,1800,'{"priority":"medium","objective":"Build a cited industry, competition and moat artifact using official or authorized sources; separate facts, inference and unknowns."}'::jsonb,'{"required":["artifact","citations","disconfirming_evidence"]}'::jsonb,'request_human','{"x":140,"y":140}'::jsonb),
    ('valuation','Valuation and scenarios','agent_task','Valuation Agent','long_term_valuation_review','draft_only',false,1,1800,'{"priority":"medium","objective":"Create valuation work only from validated inputs. Label actual, guidance, external estimate and model scenario separately; provide ranges, sensitivity and unavailable gates."}'::jsonb,'{"required":["assumptions","provenance","scenarios","sensitivity","validation_status"]}'::jsonb,'request_human','{"x":280,"y":140}'::jsonb),
    ('bear_risk','Bear case and permanent-loss risk','agent_task','Bear Case Agent','long_term_bear_case_review','draft_only',false,2,1800,'{"priority":"high","objective":"Build the adversarial case with cited thesis killers, governance or accounting risks, uncertainty and explicit missing evidence."}'::jsonb,'{"required":["artifact","citations","thesis_killers","exceptions"]}'::jsonb,'request_human','{"x":420,"y":140}'::jsonb),
    ('synthesis','Join cited specialist work','join','Long-Term Portfolio Manager',NULL::text,'draft_only',false,0,300,'{}'::jsonb,'{"required":["all_lanes_terminal"]}'::jsonb,'pause','{"x":0,"y":300}'::jsonb),
    ('human_review','Human review of thesis brief','approval_gate','Long-Term Portfolio Manager',NULL::text,'human_approval',true,0,86400,'{"priority":"high","approval_type":"research_case_review","risk_level":"medium","objective":"Review the cited research-case brief, coverage debt, disagreements, assumptions and caveats. This gate authorizes no capital, broker, client or external action."}'::jsonb,'{"required":["decision","rationale"]}'::jsonb,'request_human','{"x":0,"y":440}'::jsonb),
    ('end','Research case complete','end','Long-Term Portfolio Manager',NULL::text,'draft_only',false,0,60,'{}'::jsonb,'{"status":"complete"}'::jsonb,'pause','{"x":0,"y":580}'::jsonb)
) AS node(node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,approval_required,retry_limit,timeout_seconds,configuration,output_contract,on_error,ui_position)
WHERE version.graph_key='company_research_case' AND version.version=1
  AND NOT EXISTS (
    SELECT 1 FROM agent.graph_nodes existing
    WHERE existing.graph_version_id=version.id
      AND existing.node_key=node.node_key
  );

INSERT INTO agent.graph_edges (
    graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,priority,enabled,label
)
SELECT version.id,edge.from_key,edge.to_key,edge.edge_kind,edge.condition_type,edge.condition,
       edge.priority,true,edge.label
FROM agent.graph_versions version
CROSS JOIN (VALUES
    ('start','company_business','success','always','{}'::jsonb,10,'Dispatch company lane'),
    ('start','filings','success','always','{}'::jsonb,20,'Dispatch filings lane'),
    ('start','financials','success','always','{}'::jsonb,30,'Dispatch financial lane'),
    ('start','management','success','always','{}'::jsonb,40,'Dispatch stewardship lane'),
    ('start','industry_moat','success','always','{}'::jsonb,50,'Dispatch industry lane'),
    ('start','valuation','success','always','{}'::jsonb,60,'Dispatch valuation lane'),
    ('start','bear_risk','success','always','{}'::jsonb,70,'Dispatch bear lane'),
    ('company_business','synthesis','success','always','{}'::jsonb,100,'Company complete'),
    ('filings','synthesis','success','always','{}'::jsonb,110,'Filings complete'),
    ('financials','synthesis','success','always','{}'::jsonb,120,'Financials complete'),
    ('management','synthesis','success','always','{}'::jsonb,130,'Stewardship complete'),
    ('industry_moat','synthesis','success','always','{}'::jsonb,140,'Industry complete'),
    ('valuation','synthesis','success','always','{}'::jsonb,150,'Valuation complete'),
    ('bear_risk','synthesis','success','always','{}'::jsonb,160,'Bear case complete'),
    ('synthesis','human_review','success','always','{}'::jsonb,200,'Request human review'),
    ('human_review','end','conditional','approved','{}'::jsonb,210,'Human approved research brief')
) AS edge(from_key,to_key,edge_kind,condition_type,condition,priority,label)
WHERE version.graph_key='company_research_case' AND version.version=1
  AND NOT EXISTS (
    SELECT 1 FROM agent.graph_edges existing
    WHERE existing.graph_version_id=version.id
      AND existing.from_node_key=edge.from_key
      AND existing.to_node_key=edge.to_key
  );


-- Version 2 prevents generic transport workers from being mistaken for source-qualified
-- company research. Seven lanes are durably dispatched to review queues and only advance
-- after a worker returns case-scoped, cited, validated evidence stored on the external SSD.
INSERT INTO agent.graph_versions (
    graph_key,version,status,change_summary,source_kind,source_ref,definition_hash,
    validation_result,created_by,approved_by,approved_at
) VALUES (
    'company_research_case',2,'active',
    'Require source-qualified worker assignment and case-scoped citation validation before research lanes advance.',
    'operator_authored','migration:226_research_cases_reports_v1',
    md5('company_research_case:v2:source_qualified_worker_gate'),
    '{"valid":true,"validated_contracts":true,"generic_worker_blocked":true,"company_scoped_citations_required":true,"capital_action_allowed":false,"external_write_allowed":false}'::jsonb,
    'Devarsh','Devarsh',now()
) ON CONFLICT (graph_key,version) DO UPDATE SET
    status='active',change_summary=EXCLUDED.change_summary,definition_hash=EXCLUDED.definition_hash,
    validation_result=EXCLUDED.validation_result,approved_by='Devarsh',approved_at=now();

INSERT INTO agent.graph_nodes (
    graph_version_id,node_key,node_name,node_type,owner_agent,skill_key,autonomy_level,
    approval_required,retry_limit,timeout_seconds,input_mapping,configuration,
    output_contract,on_error,ui_position
)
SELECT v2.id,node.node_key,node.node_name,node.node_type,node.owner_agent,node.skill_key,
       node.autonomy_level,
       CASE WHEN node.node_key IN ('company_business','filings','financials','management','industry_moat','valuation','bear_risk')
            THEN true ELSE node.approval_required END,
       node.retry_limit,node.timeout_seconds,node.input_mapping,
       CASE WHEN node.node_key IN ('company_business','filings','financials','management','industry_moat','valuation','bear_risk')
            THEN node.configuration || '{"source_qualified_worker_required":true,"generic_worker_receipt_satisfies_lane":false,"company_scoped_citations_required":true,"external_ssd_artifact_required":true}'::jsonb
            ELSE node.configuration END,
       node.output_contract,node.on_error,node.ui_position
FROM agent.graph_versions v1
JOIN agent.graph_nodes node ON node.graph_version_id=v1.id
JOIN agent.graph_versions v2 ON v2.graph_key=v1.graph_key AND v2.version=2
WHERE v1.graph_key='company_research_case' AND v1.version=1
ON CONFLICT (graph_version_id,node_key) DO UPDATE SET
    node_name=EXCLUDED.node_name,node_type=EXCLUDED.node_type,owner_agent=EXCLUDED.owner_agent,
    skill_key=EXCLUDED.skill_key,autonomy_level=EXCLUDED.autonomy_level,
    approval_required=EXCLUDED.approval_required,retry_limit=EXCLUDED.retry_limit,
    timeout_seconds=EXCLUDED.timeout_seconds,input_mapping=EXCLUDED.input_mapping,
    configuration=EXCLUDED.configuration,output_contract=EXCLUDED.output_contract,
    on_error=EXCLUDED.on_error,ui_position=EXCLUDED.ui_position;

INSERT INTO agent.graph_edges (
    graph_version_id,from_node_key,to_node_key,edge_kind,condition_type,condition,
    priority,enabled,label
)
SELECT v2.id,edge.from_node_key,edge.to_node_key,edge.edge_kind,edge.condition_type,
       edge.condition,edge.priority,edge.enabled,edge.label
FROM agent.graph_versions v1
JOIN agent.graph_edges edge ON edge.graph_version_id=v1.id
JOIN agent.graph_versions v2 ON v2.graph_key=v1.graph_key AND v2.version=2
WHERE v1.graph_key='company_research_case' AND v1.version=1
ON CONFLICT (graph_version_id,from_node_key,to_node_key,edge_kind) DO UPDATE SET
    condition_type=EXCLUDED.condition_type,condition=EXCLUDED.condition,
    priority=EXCLUDED.priority,enabled=EXCLUDED.enabled,label=EXCLUDED.label;

UPDATE agent.graph_versions SET status='retired'
WHERE graph_key='company_research_case' AND version<>2 AND status='active';

UPDATE agent.graph_definitions SET active_version=2,updated_at=now()
WHERE graph_key='company_research_case';

COMMIT;
