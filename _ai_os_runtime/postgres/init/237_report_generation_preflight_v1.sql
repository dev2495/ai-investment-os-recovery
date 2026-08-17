BEGIN;

CREATE TABLE IF NOT EXISTS research.report_generation_preflights (
  id bigserial PRIMARY KEY,
  preflight_key text NOT NULL UNIQUE,
  holding_thesis_id bigint NOT NULL,
  requested_by text NOT NULL,
  source_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_boundary text NOT NULL CHECK (data_boundary IN ('local_ssd_only')),
  estimated_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
  hard_max_cost_usd numeric(14,6) NOT NULL DEFAULT 0 CHECK (hard_max_cost_usd >= estimated_cost_usd),
  estimated_duration_seconds integer NOT NULL CHECK (estimated_duration_seconds > 0),
  model_invocation boolean NOT NULL DEFAULT false,
  external_egress boolean NOT NULL DEFAULT false,
  status text NOT NULL CHECK (status IN ('pending_confirmation','approved','completed','expired','failed')) DEFAULT 'pending_confirmation',
  approved_by text,
  approved_at timestamptz,
  artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  expires_at timestamptz NOT NULL DEFAULT now() + interval '30 minutes',
  CHECK ((model_invocation=false) AND (external_egress=false))
);

CREATE INDEX IF NOT EXISTS report_generation_preflights_thesis_status_idx
  ON research.report_generation_preflights (holding_thesis_id,status,created_at DESC);

COMMIT;
