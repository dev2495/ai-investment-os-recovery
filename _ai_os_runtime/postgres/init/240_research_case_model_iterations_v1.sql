BEGIN;

ALTER TABLE research.research_case_model_runs
  ADD COLUMN IF NOT EXISTS iteration integer NOT NULL DEFAULT 1;
ALTER TABLE research.research_case_model_runs
  DROP CONSTRAINT IF EXISTS research_case_model_runs_research_case_id_role_key_attempt_key;
ALTER TABLE research.research_case_model_runs
  DROP CONSTRAINT IF EXISTS research_case_model_runs_iteration_check;
ALTER TABLE research.research_case_model_runs
  ADD CONSTRAINT research_case_model_runs_iteration_check CHECK (iteration >= 1 AND iteration <= 20);
CREATE UNIQUE INDEX IF NOT EXISTS uq_research_case_model_runs_iteration
  ON research.research_case_model_runs(research_case_id, role_key, iteration, attempt);
CREATE INDEX IF NOT EXISTS idx_research_case_model_runs_iteration_status
  ON research.research_case_model_runs(research_case_id, iteration, status, role_key);

COMMIT;
