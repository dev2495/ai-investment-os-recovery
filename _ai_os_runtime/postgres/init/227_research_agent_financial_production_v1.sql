BEGIN;
CREATE TABLE IF NOT EXISTS research.research_case_work_items (
 id BIGSERIAL PRIMARY KEY,research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
 work_key TEXT NOT NULL,parent_work_item_id BIGINT REFERENCES research.research_case_work_items(id) ON DELETE SET NULL,
 work_type TEXT NOT NULL CHECK(work_type IN ('plan','research','delegation','calculation','validation','revision','input_request','synthesis')),
 owner_agent TEXT NOT NULL,title TEXT NOT NULL,objective TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','ready','running','waiting_input','blocked','needs_review','completed','cancelled')),
 priority TEXT NOT NULL DEFAULT 'medium',iteration INTEGER NOT NULL DEFAULT 1 CHECK(iteration>0),
 input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
 evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,artifact_refs JSONB NOT NULL DEFAULT '[]'::jsonb,exception_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
 idempotency_key TEXT NOT NULL,task_id BIGINT REFERENCES agent.tasks(id) ON DELETE SET NULL,
 inbox_id BIGINT REFERENCES agent.inbox_items(id) ON DELETE SET NULL,worker_run_id BIGINT REFERENCES agent.worker_runs(id) ON DELETE SET NULL,
 model_decision_id BIGINT REFERENCES agent.model_call_decisions(id) ON DELETE SET NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(research_case_id,work_key,iteration),UNIQUE(idempotency_key));
CREATE INDEX IF NOT EXISTS idx_research_case_work_items_state ON research.research_case_work_items(research_case_id,status,priority,updated_at DESC);
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS lead_status TEXT NOT NULL DEFAULT 'not_started';
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS current_goal TEXT;
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS workspace_path TEXT;
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS iteration_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS decision_readiness TEXT NOT NULL DEFAULT 'evidence_debt';
ALTER TABLE research.research_cases ADD COLUMN IF NOT EXISTS last_progress_at TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS research.financial_formula_definitions (
 id BIGSERIAL PRIMARY KEY,formula_key TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>0),label TEXT NOT NULL,expression TEXT NOT NULL,
 basis JSONB NOT NULL,unit TEXT NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(formula_key,version));
CREATE TABLE IF NOT EXISTS research.financial_production_runs (
 id BIGSERIAL PRIMARY KEY,run_key TEXT NOT NULL UNIQUE,company_id BIGINT NOT NULL REFERENCES research.companies(id),
 filing_id BIGINT REFERENCES research.corporate_filings(id),parser_name TEXT NOT NULL,parser_version INTEGER NOT NULL,statement_scope TEXT NOT NULL,
 currency TEXT NOT NULL,unit TEXT NOT NULL,source_sha256 TEXT NOT NULL,source_url TEXT NOT NULL,source_path TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('running','machine_extracted','validated','human_reviewed','blocked','failed')),
 started_at TIMESTAMPTZ NOT NULL DEFAULT now(),completed_at TIMESTAMPTZ,created_by TEXT NOT NULL,summary JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS research.financial_source_facts (
 id BIGSERIAL PRIMARY KEY,production_run_id BIGINT NOT NULL REFERENCES research.financial_production_runs(id) ON DELETE CASCADE,
 company_id BIGINT NOT NULL REFERENCES research.companies(id),fact_key TEXT NOT NULL,fiscal_year INTEGER NOT NULL,period_end DATE NOT NULL,
 statement_type TEXT NOT NULL,statement_scope TEXT NOT NULL,value NUMERIC,currency TEXT NOT NULL CHECK(currency='INR'),
 unit TEXT NOT NULL CHECK(unit IN ('lakh','INR/share','percent','ratio','days')),source_page INTEGER NOT NULL CHECK(source_page>0),reported_line TEXT NOT NULL,
 extraction_status TEXT NOT NULL CHECK(extraction_status IN ('machine_extracted','validated','human_reviewed','rejected')),
 issuer_restatement BOOLEAN NOT NULL DEFAULT false,supersedes_fact_id BIGINT REFERENCES research.financial_source_facts(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(production_run_id,fact_key,fiscal_year,statement_scope));
CREATE TABLE IF NOT EXISTS research.financial_validation_checks (
 id BIGSERIAL PRIMARY KEY,production_run_id BIGINT NOT NULL REFERENCES research.financial_production_runs(id) ON DELETE CASCADE,
 check_key TEXT NOT NULL,period_end DATE,check_type TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('pass','warning','blocked','fail')),
 left_value NUMERIC,right_value NUMERIC,tolerance NUMERIC NOT NULL DEFAULT 0,explanation TEXT NOT NULL,source_pages INTEGER[] NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(production_run_id,check_key,period_end));
CREATE TABLE IF NOT EXISTS research.financial_ratio_results (
 id BIGSERIAL PRIMARY KEY,production_run_id BIGINT NOT NULL REFERENCES research.financial_production_runs(id) ON DELETE CASCADE,
 company_id BIGINT NOT NULL REFERENCES research.companies(id),formula_definition_id BIGINT NOT NULL REFERENCES research.financial_formula_definitions(id),
 period_end DATE NOT NULL,statement_scope TEXT NOT NULL,value NUMERIC,
 calculation_status TEXT NOT NULL CHECK(calculation_status IN ('machine_calculated','validated','human_reviewed','not_computable','blocked')),
 not_computable_reason TEXT,caveats JSONB NOT NULL DEFAULT '[]'::jsonb,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(production_run_id,formula_definition_id,period_end,statement_scope),
 CHECK((value IS NULL AND not_computable_reason IS NOT NULL) OR (value IS NOT NULL AND not_computable_reason IS NULL)));
CREATE TABLE IF NOT EXISTS research.financial_ratio_inputs (
 ratio_result_id BIGINT NOT NULL REFERENCES research.financial_ratio_results(id) ON DELETE CASCADE,input_role TEXT NOT NULL,
 fact_id BIGINT NOT NULL REFERENCES research.financial_source_facts(id),PRIMARY KEY(ratio_result_id,input_role,fact_id));
CREATE TABLE IF NOT EXISTS research.research_pack_rubric (
 section_key TEXT PRIMARY KEY,section_order INTEGER NOT NULL UNIQUE,section_name TEXT NOT NULL,completion_rule TEXT NOT NULL,
 required_outputs JSONB NOT NULL,evidence_policy TEXT NOT NULL,active BOOLEAN NOT NULL DEFAULT true);
INSERT INTO research.research_pack_rubric VALUES
('investment_synopsis',10,'Investment synopsis','Company verdict or exact evidence debt.','["verdict","reasons","what_changed","valuation","catalysts","risks","decision_ask"]','Every factual or numeric claim cites accepted evidence.',true),
('business_segments',20,'Business and segments','Business model, evolution and disclosed segments with reconciliation.','["business_model","evolution","segment_table","reconciliation"]','Do not manufacture segment ratios.',true),
('market_moat',30,'Market, competition and moat','Evidence-based industry, competition, moat and disconfirmers.','["industry","competition","moat","disconfirmers"]','Peers only on compatible verified basis.',true),
('management',40,'Management and governance','Management, governance, guidance delivery and capital allocation.','["management","governance","guidance_delivery","capital_allocation"]','Exact source, date, target and horizon required.',true),
('financial_model',50,'Historical financial model and ratios','Reconciled statements, trends, ratios, inputs and exceptions.','["statements","ratios","capital_efficiency","exceptions"]','Validated inputs and reproducible formulas required.',true),
('forecast_valuation',60,'Forecasts, scenarios and valuation','Actual, guidance, estimate and scenario separated.','["forecast_basis","scenarios","valuation","sensitivity","limits"]','No unsupported point forecast or probability.',true),
('catalysts_risks',70,'Catalysts and risks','Mechanism, timing, evidence, monitoring metric and kill condition.','["catalysts","risks","kill_conditions"]','Confidence only when methodology supports it.',true),
('evidence_appendix',80,'Primary evidence and appendices','Source register, citations, raw ledger and coverage debt.','["source_register","citations","raw_appendix","coverage_debt"]','URL, hash, date, page and status required.',true)
ON CONFLICT(section_key) DO UPDATE SET section_order=excluded.section_order,section_name=excluded.section_name,completion_rule=excluded.completion_rule,required_outputs=excluded.required_outputs,evidence_policy=excluded.evidence_policy,active=true;
COMMIT;
