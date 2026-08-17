BEGIN;

CREATE TABLE IF NOT EXISTS research.research_case_source_jobs (
  id BIGSERIAL PRIMARY KEY,
  research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
  corporate_filing_id BIGINT REFERENCES research.corporate_filings(id) ON DELETE RESTRICT,
  job_kind TEXT NOT NULL CHECK (job_kind IN ('extract_official_filing','collect_verified_ir','map_user_research')),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','retry_wait','blocked','cancelled')),
  priority INTEGER NOT NULL DEFAULT 100,
  attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt BETWEEN 0 AND 5),
  max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 5),
  next_retry_at TIMESTAMPTZ,
  source_url TEXT,
  artifact_path TEXT,
  result JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_detail TEXT,
  created_by TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (research_case_id,corporate_filing_id,job_kind)
);
CREATE INDEX IF NOT EXISTS idx_research_case_source_jobs_queue
  ON research.research_case_source_jobs(status,next_retry_at,priority,id);

CREATE TABLE IF NOT EXISTS research.research_case_blockers (
  id BIGSERIAL PRIMARY KEY,
  research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
  blocker_key TEXT NOT NULL,
  stage_key TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL,
  system_action TEXT,
  user_action TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','retrying','resolved','waived')),
  severity TEXT NOT NULL DEFAULT 'high' CHECK (severity IN ('low','medium','high','critical')),
  retry_count INTEGER NOT NULL DEFAULT 0,
  next_retry_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  resolution TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (research_case_id,blocker_key)
);
CREATE INDEX IF NOT EXISTS idx_research_case_blockers_open
  ON research.research_case_blockers(research_case_id,status,severity,updated_at DESC);

CREATE TABLE IF NOT EXISTS research.imported_company_research_artifacts (
  id BIGSERIAL PRIMARY KEY,
  artifact_key TEXT NOT NULL UNIQUE,
  company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
  company_label TEXT NOT NULL,
  symbol_hint TEXT,
  artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('research_report','interactive_dashboard','financial_model','research_note','sector_report','other')),
  original_filename TEXT NOT NULL,
  local_artifact_path TEXT NOT NULL,
  extracted_text_path TEXT,
  content_hash TEXT NOT NULL CHECK (length(content_hash)=64),
  mime_type TEXT NOT NULL,
  source_collection TEXT NOT NULL,
  source_posture TEXT NOT NULL DEFAULT 'historical_user_supplied_research'
    CHECK (source_posture IN ('historical_user_supplied_research','public_primary','public_secondary')),
  entity_match_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (entity_match_status IN ('matched','pending','not_applicable','conflict')),
  parser_status TEXT NOT NULL DEFAULT 'captured'
    CHECK (parser_status IN ('captured','parsed','parse_failed','not_supported')),
  review_status TEXT NOT NULL DEFAULT 'needs_fresh_corroboration'
    CHECK (review_status IN ('needs_fresh_corroboration','reviewed_reference','rejected','accepted_with_primary_corroboration')),
  title TEXT,
  report_as_of DATE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  imported_by TEXT NOT NULL,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (content_hash,original_filename)
);
CREATE INDEX IF NOT EXISTS idx_imported_company_research_company
  ON research.imported_company_research_artifacts(company_id,review_status,imported_at DESC);

CREATE TABLE IF NOT EXISTS research.research_case_reports (
  id BIGSERIAL PRIMARY KEY,
  research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
  report_version INTEGER NOT NULL CHECK (report_version>0),
  report_status TEXT NOT NULL DEFAULT 'generated' CHECK (report_status IN ('generated','needs_revision','human_reviewed','superseded','failed')),
  as_of_date DATE NOT NULL,
  source_cutoff_at TIMESTAMPTZ,
  html_path TEXT NOT NULL,
  html_hash TEXT NOT NULL CHECK (length(html_hash)=64),
  pdf_path TEXT,
  pdf_hash TEXT,
  section_count INTEGER NOT NULL DEFAULT 0,
  citation_count INTEGER NOT NULL DEFAULT 0,
  coverage_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  generated_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (research_case_id,report_version)
);
CREATE INDEX IF NOT EXISTS idx_research_case_reports_latest ON research.research_case_reports(research_case_id,report_version DESC);

CREATE TABLE IF NOT EXISTS research.research_pack_sections (
  id BIGSERIAL PRIMARY KEY,
  research_case_id BIGINT NOT NULL REFERENCES research.research_cases(id) ON DELETE CASCADE,
  section_key TEXT NOT NULL,
  title TEXT NOT NULL,
  owner_role TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'not_started'
    CHECK (status IN ('not_started','collecting','draft','needs_revision','reviewed','blocked','complete')),
  summary TEXT,
  content JSONB NOT NULL DEFAULT '{}'::jsonb,
  citation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  coverage_gaps JSONB NOT NULL DEFAULT '[]'::jsonb,
  artifact_path TEXT,
  artifact_hash TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (research_case_id,section_key,version)
);

INSERT INTO research.research_pack_sections (research_case_id,section_key,title,owner_role,status)
SELECT case_row.id,section.section_key,section.title,section.owner_role,
       CASE WHEN case_row.status='proposed' THEN 'not_started' ELSE 'collecting' END
FROM research.research_cases case_row
CROSS JOIN (VALUES
 ('investment_conclusion','Investment conclusion and thesis evolution','lead_synthesis'),
 ('business_segments','Business, segments and unit economics','company_business'),
 ('industry_structure','Industry, Porter five forces and supply demand','industry_moat'),
 ('tam_value_chain','TAM, value chain and profit pools','industry_moat'),
 ('moat_quality','Moat and business quality','industry_moat'),
 ('management_governance','Management, governance and capital allocation','management'),
 ('financial_history','Financial history, ratios and numbers story','financials'),
 ('forecasts_valuation','Forecasts, valuation and expected return','valuation'),
 ('catalysts_risks','Catalysts, risks and disconfirmers','bear_risk'),
 ('committee_decision','Independent review and committee decision','committee_review')
) section(section_key,title,owner_role)
ON CONFLICT (research_case_id,section_key,version) DO NOTHING;

COMMIT;
