BEGIN;

CREATE TABLE IF NOT EXISTS research.thesis_source_requirements (
  id BIGSERIAL PRIMARY KEY,
  requirement_key TEXT NOT NULL UNIQUE,
  section_key TEXT NOT NULL,
  section_order SMALLINT NOT NULL,
  data_point_key TEXT NOT NULL,
  requirement_label TEXT NOT NULL,
  acceptable_source_kinds TEXT[] NOT NULL,
  minimum_source_count SMALLINT NOT NULL DEFAULT 1 CHECK (minimum_source_count > 0),
  max_age_days INTEGER CHECK (max_age_days IS NULL OR max_age_days > 0),
  extraction_required BOOLEAN NOT NULL DEFAULT false,
  minimum_validation TEXT NOT NULL DEFAULT 'machine_validated'
    CHECK (minimum_validation IN ('machine_validated','human_validated')),
  is_material BOOLEAN NOT NULL DEFAULT true,
  is_required BOOLEAN NOT NULL DEFAULT true,
  is_active BOOLEAN NOT NULL DEFAULT true,
  description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_thesis_requirement_section CHECK (section_key IN (
    'company_context','thesis_change_log','moat_industry','management_governance',
    'financials_quality','valuation_scenarios','catalysts_timeline','risks_red_flags',
    'evidence_library','agent_opinions','decision_outcome')),
  UNIQUE(section_key,data_point_key)
);

CREATE TABLE IF NOT EXISTS research.thesis_source_items (
  id BIGSERIAL PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
  source_kind TEXT NOT NULL CHECK (source_kind IN (
    'official_company_page','official_ir_page','annual_report','company_filing','exchange_filing',
    'exchange_results','exchange_announcement','investor_presentation','transcript','authorized_news',
    'authorized_research','industry_source','regulatory_source','event_calendar','user_artifact',
    'specialist_opinion','validated_model','committee_record','human_decision')),
  source_system TEXT NOT NULL,
  source_identifier TEXT NOT NULL,
  source_url TEXT CHECK (source_url IS NULL OR source_url ~ '^https://'),
  source_title TEXT NOT NULL,
  publication_date DATE,
  effective_date DATE,
  captured_at TIMESTAMPTZ NOT NULL,
  capture_status TEXT NOT NULL DEFAULT 'captured'
    CHECK (capture_status IN ('planned','gated','captured','failed')),
  parser_status TEXT NOT NULL DEFAULT 'not_required'
    CHECK (parser_status IN ('not_required','pending','parsed','failed')),
  validation_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (validation_status IN ('pending','machine_validated','human_validated','rejected','superseded')),
  raw_artifact_id BIGINT REFERENCES core.raw_artifacts(id) ON DELETE SET NULL,
  source_document_id BIGINT REFERENCES portfolio.long_term_source_documents(id) ON DELETE SET NULL,
  source_extraction_id BIGINT REFERENCES portfolio.long_term_source_document_extractions(id) ON DELETE SET NULL,
  corporate_filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE SET NULL,
  fundamental_evidence_id BIGINT REFERENCES research.fundamental_evidence(id) ON DELETE SET NULL,
  local_artifact_path TEXT CHECK (
    local_artifact_path IS NULL OR local_artifact_path LIKE '/Volumes/Devarsh SSD/%'),
  content_hash TEXT,
  citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
  freshness_expires_at TIMESTAMPTZ,
  source_scope TEXT NOT NULL DEFAULT 'public' CHECK (source_scope IN ('public','user_private')),
  authorization_basis TEXT NOT NULL,
  access_status TEXT NOT NULL DEFAULT 'review_required'
    CHECK (access_status IN ('review_required','allowed','blocked')),
  terms_status TEXT NOT NULL DEFAULT 'review_required'
    CHECK (terms_status IN ('review_required','allowed','blocked')),
  robots_status TEXT NOT NULL DEFAULT 'not_applicable'
    CHECK (robots_status IN ('not_applicable','review_required','allowed','blocked')),
  cache_status TEXT NOT NULL DEFAULT 'external_ssd'
    CHECK (cache_status IN ('external_ssd','metadata_only','not_cached')),
  rate_limit_seconds INTEGER NOT NULL DEFAULT 30 CHECK (rate_limit_seconds >= 0),
  materiality TEXT NOT NULL DEFAULT 'informational'
    CHECK (materiality IN ('informational','medium','high','critical')),
  change_kind TEXT NOT NULL DEFAULT 'new' CHECK (change_kind IN ('new','revised','unchanged')),
  material_change BOOLEAN NOT NULL DEFAULT false,
  change_summary TEXT,
  section_hint TEXT,
  visibility_scope TEXT NOT NULL DEFAULT 'personal'
    CHECK (visibility_scope IN ('personal','research_team','investment_committee')),
  validated_by TEXT,
  validated_at TIMESTAMPTZ,
  validation_notes TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_thesis_item_validation_actor CHECK (
    validation_status <> 'human_validated' OR (validated_by IS NOT NULL AND validated_at IS NOT NULL)),
  UNIQUE(company_id,source_kind,source_system,source_identifier)
);

CREATE INDEX IF NOT EXISTS idx_thesis_items_company
  ON research.thesis_source_items(company_id,captured_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_items_review
  ON research.thesis_source_items(validation_status,parser_status,captured_at DESC)
  WHERE validation_status='pending' OR parser_status IN ('pending','failed');

CREATE TABLE IF NOT EXISTS research.thesis_source_links (
  id BIGSERIAL PRIMARY KEY,
  source_item_id BIGINT NOT NULL REFERENCES research.thesis_source_items(id) ON DELETE CASCADE,
  requirement_id BIGINT NOT NULL REFERENCES research.thesis_source_requirements(id) ON DELETE CASCADE,
  link_role TEXT NOT NULL DEFAULT 'supporting' CHECK (link_role IN ('primary','supporting','contradicting')),
  link_status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (link_status IN ('proposed','validated','rejected','superseded')),
  citation_note TEXT,
  linked_by TEXT NOT NULL,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,
  CONSTRAINT chk_thesis_link_review CHECK (
    link_status <> 'validated' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
  UNIQUE(source_item_id,requirement_id,link_role)
);

CREATE TABLE IF NOT EXISTS research.thesis_source_events (
  id BIGSERIAL PRIMARY KEY,
  source_item_id BIGINT REFERENCES research.thesis_source_items(id) ON DELETE CASCADE,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN (
    'registered','captured','parsed','validation_changed','link_proposed','link_reviewed',
    'refresh_gated','refresh_completed','brief_generated')),
  event_summary TEXT NOT NULL,
  actor TEXT NOT NULL,
  event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research.thesis_cited_briefs (
  id BIGSERIAL PRIMARY KEY,
  brief_key TEXT NOT NULL UNIQUE,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  holding_thesis_id BIGINT REFERENCES portfolio.holding_theses(id) ON DELETE SET NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_by TEXT NOT NULL,
  artifact_path TEXT NOT NULL CHECK (
    artifact_path LIKE '/Volumes/Devarsh SSD/Obsidian memory %'),
  artifact_hash TEXT NOT NULL,
  covered_requirement_count INTEGER NOT NULL DEFAULT 0 CHECK (covered_requirement_count >= 0),
  total_requirement_count INTEGER NOT NULL DEFAULT 0 CHECK (total_requirement_count >= 0),
  pending_review_count INTEGER NOT NULL DEFAULT 0 CHECK (pending_review_count >= 0),
  missing_requirement_count INTEGER NOT NULL DEFAULT 0 CHECK (missing_requirement_count >= 0),
  stale_requirement_count INTEGER NOT NULL DEFAULT 0 CHECK (stale_requirement_count >= 0),
  source_item_count INTEGER NOT NULL DEFAULT 0 CHECK (source_item_count >= 0),
  brief_status TEXT NOT NULL DEFAULT 'review_required'
    CHECK (brief_status IN ('draft','review_required','committee_ready','superseded')),
  notes TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO research.thesis_source_requirements
  (requirement_key,section_key,section_order,data_point_key,requirement_label,acceptable_source_kinds,
   minimum_source_count,max_age_days,extraction_required,minimum_validation,is_material,is_required,description)
VALUES
('company.identity','company_context',10,'identity','Legal identity and listing',ARRAY['official_company_page','official_ir_page','annual_report','exchange_filing'],1,365,false,'machine_validated',true,true,'Official identity and listed-security context.'),
('company.business_model','company_context',10,'business_model','Business model and segments',ARRAY['annual_report','investor_presentation','company_filing'],1,550,true,'human_validated',true,true,'Current products, geographies and segments with exact citation.'),
('company.current_context','company_context',10,'current_context','Current company context',ARRAY['exchange_results','exchange_announcement','authorized_news','official_ir_page'],1,120,false,'machine_validated',true,true,'Recent material context separated from historical user research.'),
('thesis.current','thesis_change_log',20,'current_statement','Current thesis statement',ARRAY['committee_record','human_decision','user_artifact'],1,NULL,false,'human_validated',true,true,'Human-owned investment thesis.'),
('thesis.changes','thesis_change_log',20,'change_log','Versioned thesis changes',ARRAY['committee_record','human_decision','specialist_opinion','user_artifact'],1,NULL,false,'human_validated',true,true,'Author, reason and evidence-linked changes.'),
('moat.position','moat_industry',30,'competitive_position','Competitive position and moat',ARRAY['annual_report','investor_presentation','industry_source','authorized_research'],2,550,true,'human_validated',true,true,'Moat claims need corroboration or contradiction.'),
('moat.industry','moat_industry',30,'industry_structure','Industry structure and cycle',ARRAY['industry_source','regulatory_source','annual_report','authorized_research'],1,365,true,'human_validated',true,true,'Structure, cycle and competitive intensity.'),
('management.track_record','management_governance',40,'track_record','Management execution track record',ARRAY['annual_report','transcript','exchange_results','investor_presentation'],2,730,true,'human_validated',true,true,'Promised versus delivered outcomes.'),
('management.governance','management_governance',40,'governance','Governance evidence',ARRAY['annual_report','company_filing','exchange_announcement','exchange_filing'],1,550,true,'human_validated',true,true,'Board, auditor, related-party and remuneration evidence.'),
('management.capital_allocation','management_governance',40,'capital_allocation','Capital allocation record',ARRAY['annual_report','exchange_results','transcript','company_filing'],2,730,true,'human_validated',true,true,'Reinvestment, leverage, distributions and acquisitions.'),
('financials.normalized','financials_quality',50,'normalized_statements','Normalized statements',ARRAY['annual_report','exchange_results','company_filing'],1,550,true,'human_validated',true,true,'Reconciled facts linked to exact pages.'),
('financials.quality','financials_quality',50,'quality','Earnings and cash-flow quality',ARRAY['annual_report','exchange_results','company_filing'],2,550,true,'human_validated',true,true,'Cash conversion, working capital and one-offs.'),
('financials.kpis','financials_quality',50,'operational_kpis','Operational KPIs',ARRAY['annual_report','investor_presentation','exchange_results'],1,550,true,'human_validated',true,true,'Defined, dated operational metrics.'),
('valuation.assumptions','valuation_scenarios',60,'assumptions','Valuation assumptions',ARRAY['validated_model','annual_report','exchange_results'],2,550,true,'human_validated',true,true,'Explicit assumptions and source anchors.'),
('valuation.scenarios','valuation_scenarios',60,'scenarios','Bear, base and bull scenarios',ARRAY['validated_model','committee_record'],1,NULL,false,'human_validated',true,true,'Dated scenarios and sensitivities.'),
('valuation.inputs','valuation_scenarios',60,'market_inputs','Fresh model inputs',ARRAY['validated_model','exchange_results','company_filing'],1,45,false,'machine_validated',true,true,'Stale inputs cannot be presented as current.'),
('catalysts.register','catalysts_timeline',70,'identified','Cited catalyst register',ARRAY['exchange_announcement','event_calendar','transcript','authorized_news'],1,180,false,'machine_validated',true,true,'Material catalysts with exact evidence.'),
('catalysts.agenda','catalysts_timeline',70,'agenda','Upcoming agenda and events',ARRAY['event_calendar','exchange_announcement','official_ir_page'],1,90,false,'machine_validated',true,true,'Results, meetings, calls and deadlines.'),
('risks.bear_case','risks_red_flags',80,'bear_case','Evidence-backed bear case',ARRAY['annual_report','company_filing','authorized_research','committee_record'],2,550,true,'human_validated',true,true,'Falsifiable bear case, not generic risks.'),
('risks.red_flags','risks_red_flags',80,'red_flags','Material red-flag changes',ARRAY['exchange_announcement','exchange_filing','authorized_news','company_filing'],1,120,false,'human_validated',true,true,'Severity and confidence require exact evidence.'),
('evidence.annual_report','evidence_library',90,'annual_report','Latest annual report',ARRAY['annual_report'],1,550,true,'human_validated',true,true,'Official report captured, parsed and explicitly validated.'),
('evidence.filings','evidence_library',90,'filings','Material filings and announcements',ARRAY['company_filing','exchange_filing','exchange_results','exchange_announcement'],1,120,true,'human_validated',true,true,'Raw unparsed filings remain coverage debt.'),
('evidence.presentations','evidence_library',90,'presentations_transcripts','Presentations and transcripts',ARRAY['investor_presentation','transcript'],1,365,true,'human_validated',false,false,'Lawfully accessed management materials.'),
('evidence.user_artifacts','evidence_library',90,'user_artifacts','User-supplied research',ARRAY['user_artifact'],1,NULL,true,'human_validated',false,false,'Historical private research requiring fresh corroboration.'),
('opinions.specialists','agent_opinions',100,'specialists','Specialist disagreement',ARRAY['specialist_opinion'],2,120,false,'human_validated',true,true,'Cited bounded views with explicit disagreement.'),
('decision.pending','decision_outcome',110,'pending_decision','Pending human decisions',ARRAY['committee_record','human_decision'],1,NULL,false,'human_validated',true,true,'Recommendation awaiting explicit human action.'),
('decision.outcome','decision_outcome',110,'decision_outcome','Decision and outcome record',ARRAY['human_decision','committee_record'],1,NULL,false,'human_validated',true,true,'Immutable decision, rationale and outcome.')
ON CONFLICT(requirement_key) DO UPDATE SET
  section_key=EXCLUDED.section_key,section_order=EXCLUDED.section_order,
  data_point_key=EXCLUDED.data_point_key,requirement_label=EXCLUDED.requirement_label,
  acceptable_source_kinds=EXCLUDED.acceptable_source_kinds,minimum_source_count=EXCLUDED.minimum_source_count,
  max_age_days=EXCLUDED.max_age_days,extraction_required=EXCLUDED.extraction_required,
  minimum_validation=EXCLUDED.minimum_validation,is_material=EXCLUDED.is_material,
  is_required=EXCLUDED.is_required,description=EXCLUDED.description,updated_at=now();

CREATE OR REPLACE VIEW research.v_thesis_source_matrix AS
WITH detail AS (
  SELECT c.id company_id,c.primary_symbol symbol,COALESCE(c.display_name,c.legal_name) company_name,
    r.id requirement_id,r.requirement_key,r.section_key,r.section_order,r.data_point_key,r.requirement_label,
    r.acceptable_source_kinds,r.minimum_source_count,r.max_age_days,r.extraction_required,
    r.minimum_validation,r.is_material,r.is_required,
    l.link_status,i.id source_item_id,i.source_kind,i.source_title,i.source_url,i.publication_date,
    i.effective_date,i.captured_at,i.parser_status,i.validation_status,i.citation_locator,
    CASE i.validation_status WHEN 'human_validated' THEN 2 WHEN 'machine_validated' THEN 1 ELSE 0 END validation_rank,
    CASE r.minimum_validation WHEN 'human_validated' THEN 2 ELSE 1 END required_rank,
    CASE WHEN i.id IS NULL THEN false WHEN i.freshness_expires_at IS NOT NULL
      THEN i.freshness_expires_at>=now() WHEN r.max_age_days IS NULL THEN true
      ELSE i.captured_at>=now()-make_interval(days=>r.max_age_days) END is_fresh
  FROM research.companies c CROSS JOIN research.thesis_source_requirements r
  LEFT JOIN research.thesis_source_links l ON l.requirement_id=r.id AND l.link_status<>'rejected'
  LEFT JOIN research.thesis_source_items i ON i.id=l.source_item_id AND i.company_id=c.id
    AND i.validation_status NOT IN ('rejected','superseded')
  WHERE c.status='active' AND r.is_active
), rolled AS (
  SELECT company_id,symbol,company_name,requirement_id,requirement_key,section_key,section_order,
    data_point_key,requirement_label,acceptable_source_kinds,minimum_source_count,max_age_days,
    extraction_required,minimum_validation,is_material,is_required,
    count(source_item_id) FILTER(WHERE source_item_id IS NOT NULL) linked_source_count,
    count(source_item_id) FILTER(WHERE link_status='validated' AND validation_rank>=required_rank
      AND (NOT extraction_required OR parser_status='parsed') AND is_fresh) covered_source_count,
    count(source_item_id) FILTER(WHERE source_item_id IS NOT NULL AND
      (link_status='proposed' OR validation_rank<required_rank OR (extraction_required AND parser_status<>'parsed')))
      pending_review_count,
    count(source_item_id) FILTER(WHERE source_item_id IS NOT NULL AND NOT is_fresh) stale_source_count,
    max(captured_at) latest_captured_at,max(publication_date) latest_publication_date,
    COALESCE(jsonb_agg(jsonb_build_object('source_item_id',source_item_id,'source_kind',source_kind,
      'source_title',source_title,'source_url',source_url,'publication_date',publication_date,
      'effective_date',effective_date,'captured_at',captured_at,'parser_status',parser_status,
      'validation_status',validation_status,'link_status',link_status,'citation_locator',citation_locator,
      'is_fresh',is_fresh) ORDER BY captured_at DESC NULLS LAST)
      FILTER(WHERE source_item_id IS NOT NULL),'[]'::jsonb) sources
  FROM detail GROUP BY company_id,symbol,company_name,requirement_id,requirement_key,section_key,
    section_order,data_point_key,requirement_label,acceptable_source_kinds,minimum_source_count,
    max_age_days,extraction_required,minimum_validation,is_material,is_required
)
SELECT rolled.*,CASE WHEN covered_source_count>=minimum_source_count THEN 'covered'
  WHEN stale_source_count>0 AND pending_review_count=0 THEN 'stale'
  WHEN linked_source_count>0 THEN 'pending_review' ELSE 'missing' END coverage_status,
  GREATEST(minimum_source_count-covered_source_count,0) coverage_debt
FROM rolled;

CREATE OR REPLACE VIEW research.v_thesis_source_pipeline_queue AS
SELECT i.id source_item_id,i.company_id,c.primary_symbol symbol,COALESCE(c.display_name,c.legal_name) company_name,
  i.source_kind,i.source_title,i.source_url,i.publication_date,i.effective_date,i.captured_at,
  i.capture_status,i.parser_status,i.validation_status,i.access_status,i.terms_status,i.robots_status,
  i.source_scope,i.materiality,i.change_kind,i.material_change,i.change_summary,i.section_hint,
  i.local_artifact_path,i.citation_locator,
  count(l.id) FILTER(WHERE l.link_status='proposed') proposed_link_count,
  count(l.id) FILTER(WHERE l.link_status='validated') validated_link_count,
  CASE WHEN i.access_status<>'allowed' OR i.terms_status<>'allowed'
      OR i.robots_status IN ('review_required','blocked') THEN 'source_review'
    WHEN i.capture_status<>'captured' THEN 'capture'
    WHEN i.parser_status='pending' THEN 'parse'
    WHEN i.parser_status='failed' THEN 'parser_exception'
    WHEN i.validation_status='pending' THEN 'validate'
    WHEN count(l.id) FILTER(WHERE l.link_status='proposed')>0 THEN 'review_links'
    ELSE 'ready' END next_gate
FROM research.thesis_source_items i JOIN research.companies c ON c.id=i.company_id
LEFT JOIN research.thesis_source_links l ON l.source_item_id=i.id
WHERE i.validation_status NOT IN ('rejected','superseded')
GROUP BY i.id,c.id;

CREATE OR REPLACE VIEW research.v_thesis_material_source_changes AS
SELECT i.id source_item_id,i.company_id,c.primary_symbol symbol,COALESCE(c.display_name,c.legal_name) company_name,
  i.source_kind,i.source_title,i.source_url,i.publication_date,i.effective_date,i.captured_at,
  i.freshness_expires_at,i.validation_status,i.materiality,i.change_kind,i.change_summary,
  i.section_hint,i.visibility_scope,i.citation_locator,
  array_remove(array_agg(DISTINCT r.requirement_key),NULL) requirement_keys
FROM research.thesis_source_items i JOIN research.companies c ON c.id=i.company_id
LEFT JOIN research.thesis_source_links l ON l.source_item_id=i.id AND l.link_status='validated'
LEFT JOIN research.thesis_source_requirements r ON r.id=l.requirement_id
WHERE i.material_change AND i.change_kind IN ('new','revised')
  AND i.validation_status IN ('machine_validated','human_validated')
  AND i.access_status='allowed' AND i.terms_status='allowed'
  AND i.robots_status NOT IN ('review_required','blocked')
  AND (i.freshness_expires_at IS NULL OR i.freshness_expires_at>=now())
GROUP BY i.id,c.id;

COMMENT ON TABLE research.thesis_source_requirements IS
'Canonical source-to-section and data-point coverage contract.';
COMMENT ON TABLE research.thesis_source_items IS
'Raw capture, parsing, validation and section linking remain distinct governed states.';
COMMIT;
