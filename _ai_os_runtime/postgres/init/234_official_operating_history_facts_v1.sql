BEGIN;

CREATE TABLE IF NOT EXISTS research.official_operating_history_facts (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  source_item_id BIGINT NOT NULL REFERENCES research.thesis_source_items(id) ON DELETE RESTRICT,
  metric_key TEXT NOT NULL,
  metric_label TEXT NOT NULL,
  metric_group TEXT NOT NULL CHECK (metric_group IN ('profitability','balance_sheet','working_capital','volume')),
  fiscal_year INTEGER NOT NULL CHECK (fiscal_year BETWEEN 1900 AND 2200),
  period_end DATE NOT NULL,
  value_numeric NUMERIC NOT NULL,
  unit TEXT NOT NULL,
  currency TEXT,
  consolidation_scope TEXT NOT NULL DEFAULT 'consolidated'
    CHECK (consolidation_scope IN ('consolidated','standalone','segment')),
  fact_basis TEXT NOT NULL,
  source_locator JSONB NOT NULL,
  extraction_status TEXT NOT NULL CHECK (extraction_status IN ('machine_extracted','validated','human_reviewed','rejected')),
  validation_status TEXT NOT NULL CHECK (validation_status IN ('pending','machine_validated','human_validated','rejected')),
  validation_notes TEXT,
  parser_version TEXT NOT NULL,
  extracted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(company_id,metric_key,fiscal_year,consolidation_scope,source_item_id)
);

CREATE INDEX IF NOT EXISTS idx_official_operating_history_company
  ON research.official_operating_history_facts(company_id,metric_group,metric_key,fiscal_year);

CREATE TABLE IF NOT EXISTS research.official_operating_history_checks (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  source_item_id BIGINT NOT NULL REFERENCES research.thesis_source_items(id) ON DELETE RESTRICT,
  fiscal_year INTEGER NOT NULL,
  check_key TEXT NOT NULL,
  check_status TEXT NOT NULL CHECK (check_status IN ('pass','fail','blocked')),
  observed_value NUMERIC,
  expected_value NUMERIC,
  tolerance NUMERIC,
  check_detail TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  parser_version TEXT NOT NULL,
  UNIQUE(company_id,source_item_id,fiscal_year,check_key)
);

CREATE OR REPLACE VIEW research.v_official_operating_history AS
SELECT f.id,c.primary_symbol symbol,f.metric_group,f.metric_key,f.metric_label,f.fiscal_year,
  f.period_end,f.value_numeric,f.unit,f.currency,f.consolidation_scope,f.fact_basis,
  f.source_locator,f.extraction_status,f.validation_status,f.validation_notes,
  s.source_title,s.source_url,s.publication_date,s.captured_at,s.content_hash,
  count(ch.id) FILTER (WHERE ch.check_status='fail') OVER (PARTITION BY f.company_id,f.source_item_id,f.fiscal_year) failed_check_count,
  count(ch.id) FILTER (WHERE ch.check_status='blocked') OVER (PARTITION BY f.company_id,f.source_item_id,f.fiscal_year) blocked_check_count
FROM research.official_operating_history_facts f
JOIN research.companies c ON c.id=f.company_id
JOIN research.thesis_source_items s ON s.id=f.source_item_id
LEFT JOIN research.official_operating_history_checks ch
  ON ch.company_id=f.company_id AND ch.source_item_id=f.source_item_id AND ch.fiscal_year=f.fiscal_year;

COMMENT ON TABLE research.official_operating_history_facts IS
'Issuer-published operating, profitability and working-capital time series with source-item and row/year locators.';

COMMIT;
