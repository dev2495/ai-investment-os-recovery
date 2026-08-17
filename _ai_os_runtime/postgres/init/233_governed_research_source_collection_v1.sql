BEGIN;

CREATE TABLE IF NOT EXISTS research.source_provider_policies (
  provider_key TEXT PRIMARY KEY,
  provider_name TEXT NOT NULL,
  provider_class TEXT NOT NULL CHECK (provider_class IN ('primary','secondary','authorized_news')),
  hostname_pattern TEXT NOT NULL,
  source_system TEXT NOT NULL UNIQUE,
  default_source_kind TEXT NOT NULL,
  access_mode TEXT NOT NULL CHECK (access_mode IN ('explicit_public_url','official_registry')),
  robots_check_required BOOLEAN NOT NULL DEFAULT true,
  terms_basis TEXT NOT NULL,
  minimum_interval_seconds INTEGER NOT NULL DEFAULT 60 CHECK (minimum_interval_seconds >= 0),
  maximum_bytes INTEGER NOT NULL DEFAULT 12582912 CHECK (maximum_bytes BETWEEN 1024 AND 52428800),
  cache_ttl_hours INTEGER NOT NULL DEFAULT 168 CHECK (cache_ttl_hours > 0),
  primary_corroboration_required BOOLEAN NOT NULL DEFAULT false,
  private_data_allowed BOOLEAN NOT NULL DEFAULT false,
  is_active BOOLEAN NOT NULL DEFAULT true,
  reviewed_by TEXT NOT NULL,
  reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO research.source_provider_policies
  (provider_key,provider_name,provider_class,hostname_pattern,source_system,default_source_kind,
   access_mode,robots_check_required,terms_basis,minimum_interval_seconds,maximum_bytes,cache_ttl_hours,
   primary_corroboration_required,private_data_allowed,reviewed_by,notes)
VALUES
  ('usha_ir','Usha Martin investor relations','primary','(^|\.)ushamartin\.com$','official_ushamartin_ir',
   'official_ir_page','official_registry',true,'Public issuer HTTPS; no authentication or access-control bypass.',
   30,26214400,24,false,false,'AI OS Source Steward','Issuer-owned facts; exact document/page citation still required.'),
  ('bse','BSE India','primary','(^|\.)bseindia\.com$','official_bse',
   'exchange_filing','official_registry',true,'Public exchange HTTPS; no authentication or access-control bypass.',
   45,26214400,24,false,false,'AI OS Source Steward','Exchange filing source; issuer identity and document date must be retained.'),
  ('nse','NSE India','primary','(^|\.)nseindia\.com$','official_nse',
   'exchange_filing','official_registry',true,'Public exchange HTTPS; no authentication or access-control bypass.',
   45,26214400,24,false,false,'AI OS Source Steward','Exchange filing source; issuer identity and document date must be retained.'),
  ('valuepickr','ValuePickr public forum','secondary','(^|\.)valuepickr\.com$','authorized_valuepickr_public',
   'authorized_research','explicit_public_url',true,'Public, unauthenticated pages only; no login, paywall, cookie or bulk-thread bypass.',
   90,8388608,168,true,false,'AI OS Source Steward','Attributable community research. Hypotheses and claims require primary corroboration.'),
  ('substack','Public Substack posts','secondary','(^|\.)substack\.com$','authorized_substack_public',
   'authorized_research','explicit_public_url',true,'Free public posts only; no paid post, email gate, login, cookie or access-control bypass.',
   90,8388608,168,true,false,'AI OS Source Steward','Attributable author research. Hypotheses and claims require primary corroboration.')
ON CONFLICT(provider_key) DO UPDATE SET
  provider_name=EXCLUDED.provider_name,provider_class=EXCLUDED.provider_class,
  hostname_pattern=EXCLUDED.hostname_pattern,source_system=EXCLUDED.source_system,
  default_source_kind=EXCLUDED.default_source_kind,access_mode=EXCLUDED.access_mode,
  robots_check_required=EXCLUDED.robots_check_required,terms_basis=EXCLUDED.terms_basis,
  minimum_interval_seconds=EXCLUDED.minimum_interval_seconds,maximum_bytes=EXCLUDED.maximum_bytes,
  cache_ttl_hours=EXCLUDED.cache_ttl_hours,
  primary_corroboration_required=EXCLUDED.primary_corroboration_required,
  private_data_allowed=EXCLUDED.private_data_allowed,reviewed_by=EXCLUDED.reviewed_by,
  reviewed_at=now(),notes=EXCLUDED.notes,updated_at=now();

CREATE TABLE IF NOT EXISTS research.source_collection_candidates (
  id BIGSERIAL PRIMARY KEY,
  candidate_key TEXT NOT NULL UNIQUE,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  provider_key TEXT NOT NULL REFERENCES research.source_provider_policies(provider_key),
  requested_url TEXT NOT NULL CHECK (requested_url ~ '^https://'),
  canonical_url TEXT NOT NULL CHECK (canonical_url ~ '^https://'),
  source_title TEXT,
  author_name TEXT,
  publication_date DATE,
  discovered_by TEXT NOT NULL,
  discovery_method TEXT NOT NULL CHECK (discovery_method IN ('operator','agent_search','official_registry','user_supplied')),
  explicit_collection_scope BOOLEAN NOT NULL DEFAULT false,
  candidate_status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (candidate_status IN ('proposed','ready','captured','duplicate','blocked','failed','superseded')),
  review_notes TEXT,
  last_attempt_at TIMESTAMPTZ,
  next_allowed_at TIMESTAMPTZ,
  captured_source_item_id BIGINT REFERENCES research.thesis_source_items(id) ON DELETE SET NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(company_id,provider_key,canonical_url)
);

CREATE INDEX IF NOT EXISTS idx_source_candidates_queue
  ON research.source_collection_candidates(candidate_status,next_allowed_at,created_at);

CREATE TABLE IF NOT EXISTS research.source_collection_captures (
  id BIGSERIAL PRIMARY KEY,
  candidate_id BIGINT NOT NULL REFERENCES research.source_collection_candidates(id) ON DELETE CASCADE,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  capture_status TEXT NOT NULL CHECK (capture_status IN ('started','captured','not_modified','duplicate','blocked','failed')),
  requested_url TEXT NOT NULL,
  final_url TEXT,
  http_status INTEGER,
  content_type TEXT,
  response_bytes BIGINT CHECK (response_bytes IS NULL OR response_bytes >= 0),
  content_sha256 TEXT CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
  raw_artifact_path TEXT CHECK (raw_artifact_path IS NULL OR raw_artifact_path LIKE '/Volumes/Devarsh SSD/%'),
  text_artifact_path TEXT CHECK (text_artifact_path IS NULL OR text_artifact_path LIKE '/Volumes/Devarsh SSD/%'),
  receipt_path TEXT CHECK (receipt_path IS NULL OR receipt_path LIKE '/Volumes/Devarsh SSD/%'),
  robots_url TEXT,
  robots_status TEXT NOT NULL CHECK (robots_status IN ('not_checked','allowed','blocked','unavailable')),
  access_control_encountered BOOLEAN NOT NULL DEFAULT false,
  parser_status TEXT NOT NULL DEFAULT 'pending' CHECK (parser_status IN ('pending','parsed','not_applicable','failed')),
  duplicate_of_capture_id BIGINT REFERENCES research.source_collection_captures(id) ON DELETE SET NULL,
  error_code TEXT,
  error_detail TEXT,
  collector_version TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_source_capture_sha ON research.source_collection_captures(content_sha256)
  WHERE capture_status IN ('captured','duplicate');

CREATE TABLE IF NOT EXISTS research.source_collection_exceptions (
  id BIGSERIAL PRIMARY KEY,
  candidate_id BIGINT REFERENCES research.source_collection_candidates(id) ON DELETE CASCADE,
  capture_id BIGINT REFERENCES research.source_collection_captures(id) ON DELETE SET NULL,
  exception_code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  exception_summary TEXT NOT NULL,
  remediation TEXT NOT NULL,
  exception_status TEXT NOT NULL DEFAULT 'open' CHECK (exception_status IN ('open','resolved','waived')),
  retryable BOOLEAN NOT NULL DEFAULT false,
  retry_after TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolution_notes TEXT
);

CREATE TABLE IF NOT EXISTS research.source_claim_candidates (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT NOT NULL REFERENCES research.companies(id) ON DELETE CASCADE,
  source_item_id BIGINT NOT NULL REFERENCES research.thesis_source_items(id) ON DELETE CASCADE,
  requirement_id BIGINT REFERENCES research.thesis_source_requirements(id) ON DELETE SET NULL,
  claim_text TEXT NOT NULL,
  claim_kind TEXT NOT NULL CHECK (claim_kind IN ('historical_fact','current_fact','management_guidance','estimate','opinion','hypothesis')),
  citation_locator JSONB NOT NULL DEFAULT '{}'::jsonb,
  primary_corroboration_required BOOLEAN NOT NULL,
  acceptance_status TEXT NOT NULL DEFAULT 'draft'
    CHECK (acceptance_status IN ('draft','needs_primary','corroborated','validated','rejected','superseded')),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT
);

CREATE TABLE IF NOT EXISTS research.source_claim_corroborations (
  id BIGSERIAL PRIMARY KEY,
  claim_id BIGINT NOT NULL REFERENCES research.source_claim_candidates(id) ON DELETE CASCADE,
  primary_source_item_id BIGINT NOT NULL REFERENCES research.thesis_source_items(id) ON DELETE CASCADE,
  citation_locator JSONB NOT NULL,
  corroboration_status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (corroboration_status IN ('proposed','validated','contradicted','rejected')),
  linked_by TEXT NOT NULL,
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  notes TEXT,
  UNIQUE(claim_id,primary_source_item_id)
);

CREATE OR REPLACE VIEW research.v_source_collection_queue AS
SELECT c.id candidate_id,co.primary_symbol symbol,coalesce(co.display_name,co.legal_name) company_name,
  p.provider_key,p.provider_name,p.provider_class,p.primary_corroboration_required,
  c.canonical_url,c.source_title,c.author_name,c.publication_date,c.discovery_method,
  c.explicit_collection_scope,c.candidate_status,c.last_attempt_at,c.next_allowed_at,
  c.captured_source_item_id,
  count(e.id) FILTER (WHERE e.exception_status='open') open_exception_count,
  CASE
    WHEN NOT c.explicit_collection_scope THEN 'explicit_scope_required'
    WHEN c.candidate_status IN ('blocked','failed') THEN 'repair_exception'
    WHEN c.next_allowed_at IS NOT NULL AND c.next_allowed_at>now() THEN 'cooldown'
    WHEN c.candidate_status='captured' THEN 'captured'
    ELSE 'ready'
  END action_state
FROM research.source_collection_candidates c
JOIN research.companies co ON co.id=c.company_id
JOIN research.source_provider_policies p ON p.provider_key=c.provider_key
LEFT JOIN research.source_collection_exceptions e ON e.candidate_id=c.id
GROUP BY c.id,co.id,p.provider_key;

CREATE OR REPLACE VIEW research.v_source_claim_acceptance AS
SELECT cl.id claim_id,co.primary_symbol symbol,cl.claim_kind,cl.claim_text,cl.acceptance_status,
  cl.primary_corroboration_required,src.source_kind source_kind,src.source_title,src.source_url,
  count(cr.id) FILTER (WHERE cr.corroboration_status='validated') validated_primary_count,
  count(cr.id) FILTER (WHERE cr.corroboration_status='contradicted') contradiction_count,
  CASE
    WHEN cl.acceptance_status='rejected' THEN 'rejected'
    WHEN count(cr.id) FILTER (WHERE cr.corroboration_status='contradicted')>0 THEN 'contradicted'
    WHEN cl.primary_corroboration_required AND count(cr.id) FILTER (WHERE cr.corroboration_status='validated')=0
      THEN 'secondary_only_not_accepted_fact'
    WHEN cl.acceptance_status IN ('validated','corroborated') THEN 'eligible_for_human_review'
    ELSE 'draft'
  END presentation_gate
FROM research.source_claim_candidates cl
JOIN research.companies co ON co.id=cl.company_id
JOIN research.thesis_source_items src ON src.id=cl.source_item_id
LEFT JOIN research.source_claim_corroborations cr ON cr.claim_id=cl.id
GROUP BY cl.id,co.id,src.id;

COMMENT ON TABLE research.source_provider_policies IS
'Explicit provider allowlist. Secondary research remains attributable and primary-corroboration gated.';
COMMENT ON TABLE research.source_collection_candidates IS
'One explicitly scoped public URL per candidate; this is not a broad crawler or scraping queue.';
COMMENT ON TABLE research.source_claim_candidates IS
'Extracted secondary claims are drafts until primary corroboration and review gates pass.';

COMMIT;
