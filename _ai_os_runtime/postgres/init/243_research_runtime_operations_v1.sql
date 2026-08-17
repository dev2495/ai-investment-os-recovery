BEGIN;

CREATE TABLE IF NOT EXISTS research.company_research_monitor_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('running','completed','partial','failed')),
  followed_count INTEGER NOT NULL DEFAULT 0,
  filing_updates INTEGER NOT NULL DEFAULT 0,
  news_updates INTEGER NOT NULL DEFAULT 0,
  case_updates INTEGER NOT NULL DEFAULT 0,
  source_jobs_queued INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  errors JSONB NOT NULL DEFAULT '[]'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  created_by TEXT NOT NULL DEFAULT 'Company Research Monitor',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS research.company_research_updates (
  id BIGSERIAL PRIMARY KEY,
  update_key TEXT NOT NULL UNIQUE,
  watchlist_item_id BIGINT NOT NULL REFERENCES research.watchlist_items(id) ON DELETE CASCADE,
  research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
  company_id BIGINT REFERENCES research.companies(id) ON DELETE SET NULL,
  exchange TEXT NOT NULL,
  symbol TEXT NOT NULL,
  company_name TEXT NOT NULL,
  update_type TEXT NOT NULL CHECK (update_type IN ('filing','news','case_event','thesis_change','catalyst','risk','freshness')),
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_identifier TEXT NOT NULL,
  source_url TEXT,
  effective_at TIMESTAMPTZ NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  materiality TEXT NOT NULL DEFAULT 'medium' CHECK (materiality IN ('low','medium','high','critical')),
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence>=0 AND confidence<=1)),
  decision_impact TEXT NOT NULL DEFAULT 'review' CHECK (decision_impact IN ('none','monitor','review','reunderwrite')),
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','reviewed','dismissed','superseded')),
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_company_research_updates_feed
  ON research.company_research_updates(status,materiality,effective_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS idx_company_research_updates_company
  ON research.company_research_updates(exchange,symbol,effective_at DESC,id DESC);

CREATE TABLE IF NOT EXISTS research.research_runtime_repair_requests (
  id BIGSERIAL PRIMARY KEY,
  request_key TEXT NOT NULL UNIQUE,
  research_case_id BIGINT REFERENCES research.research_cases(id) ON DELETE SET NULL,
  issue_type TEXT NOT NULL CHECK (issue_type IN ('source_collection','extraction','model_contract','valuation','report_render','monitoring','chat_context','other')),
  title TEXT NOT NULL,
  observed_failure TEXT NOT NULL,
  diagnosis TEXT NOT NULL,
  proposed_change JSONB NOT NULL,
  allowed_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
  test_plan JSONB NOT NULL,
  rollback_plan TEXT NOT NULL,
  planning_route TEXT NOT NULL DEFAULT 'coding_escalation',
  coding_route TEXT NOT NULL DEFAULT 'cloud_complex_glm',
  estimated_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (estimated_cost_usd>=0),
  hard_max_cost_usd NUMERIC NOT NULL DEFAULT 0 CHECK (hard_max_cost_usd>=estimated_cost_usd),
  approval_id BIGINT REFERENCES agent.approvals(id) ON DELETE RESTRICT,
  status TEXT NOT NULL DEFAULT 'awaiting_approval'
    CHECK (status IN ('awaiting_approval','approved','queued','running','completed','failed','rejected','cancelled')),
  patch_artifact_path TEXT,
  patch_hash TEXT,
  verification JSONB NOT NULL DEFAULT '{}'::jsonb,
  external_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (external_write_allowed=false),
  broker_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (broker_write_allowed=false),
  client_write_allowed BOOLEAN NOT NULL DEFAULT false CHECK (client_write_allowed=false),
  requested_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_research_runtime_repairs_status
  ON research.research_runtime_repair_requests(status,updated_at DESC,id DESC);

INSERT INTO agent.skills (
  skill_key,skill_name,skill_family,skill_type,owner_department,status,execution_mode,
  permission_level,input_sources,output_targets,required_tools,risk_notes,prompt_template,config
) VALUES
 ('research_runtime_repair_plan','Research runtime repair planner','software_engineering','planning','software','active','governed_model_worker','read_only',
  ARRAY['research.research_case_blockers','research.research_case_source_jobs','research.research_case_model_runs','core.runtime_daemon_heartbeats'],
  ARRAY['research.research_runtime_repair_requests'],ARRAY['repo_read','test_read','structured_output'],
  'Planning is read-only. It cannot edit source, run broker/client writes or expose private evidence.',
  'Diagnose the exact failure, identify the smallest bounded path scope, propose tests and rollback. Never claim repair before observable verification.',
  '{"route":"coding_escalation","human_approval_required":true,"code_write_allowed":false,"private_data_egress_allowed":false}'::jsonb),
 ('research_runtime_repair_execute','Research runtime coding repair','software_engineering','implementation','software','active','human_gated','write_with_approval',
  ARRAY['research.research_runtime_repair_requests','approved local repository scope'],
  ARRAY['approved repository paths','SSD patch artifacts','research.research_runtime_repair_requests'],ARRAY['repo_scoped_edit','tests','git_diff'],
  'Requires approved repair request. Path allowlist is mandatory. No secrets, private evidence, deployment, external writes, broker or client mutations.',
  'Apply only the approved patch scope, run the approved tests, write a local diff artifact and stop for human review on any scope expansion.',
  '{"route":"cloud_complex_glm","planner_route":"coding_escalation","human_approval_required":true,"path_allowlist_required":true,"auto_deploy_allowed":false,"private_data_egress_allowed":false}'::jsonb)
ON CONFLICT (skill_key) DO UPDATE SET
  skill_name=EXCLUDED.skill_name,status='active',execution_mode=EXCLUDED.execution_mode,
  permission_level=EXCLUDED.permission_level,input_sources=EXCLUDED.input_sources,
  output_targets=EXCLUDED.output_targets,required_tools=EXCLUDED.required_tools,
  risk_notes=EXCLUDED.risk_notes,prompt_template=EXCLUDED.prompt_template,
  config=EXCLUDED.config,updated_at=now();

CREATE OR REPLACE VIEW research.v_company_research_update_feed AS
SELECT update_row.id,update_row.update_key,update_row.research_case_id,update_row.company_id,
       update_row.exchange,update_row.symbol,update_row.company_name,update_row.update_type,
       update_row.title,update_row.summary,update_row.source_kind,update_row.source_identifier,
       update_row.source_url,update_row.effective_at,update_row.captured_at,
       update_row.materiality,update_row.confidence,update_row.decision_impact,
       update_row.status,update_row.evidence,update_row.metadata,
       '/research/cases?case_id='||update_row.research_case_id AS case_href,
       CASE WHEN thesis.id IS NOT NULL THEN '/fundamental/theses?thesis_id='||thesis.id ELSE NULL END AS thesis_href
FROM research.company_research_updates update_row
LEFT JOIN research.research_cases case_row ON case_row.id=update_row.research_case_id
LEFT JOIN portfolio.holding_theses thesis ON thesis.id=case_row.holding_thesis_id;

COMMIT;
